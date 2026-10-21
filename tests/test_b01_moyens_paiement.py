"""B01 : configuration organisationnelle, sans toucher aux bases conservées."""
from uuid import uuid4
import pytest

from sqlalchemy import select

from test_caisse import raw_client, account, db, ready, root, post, final, body
from test_regularisation import grant45, ret, current, post as finance_post
from neosys_pharma.infrastructure.caisse_models import EvenementCaisseModel


def config(c, a, modes):
    revision = c.get(root(a)+'/contexte').json()['configuration']['revision']
    return post(c, a, '/configuration', {'revision':revision, 'modes':modes}, 200)


def test_especes_seules_initialement_et_desactivation_sans_reactivation_implicite(raw_client, account):
    c, a = raw_client, account
    v, s, *_ = ready(c, a, configure=False)
    initial = c.get(root(a)+'/contexte').json()['configuration']
    assert initial['modes'] == ['ESPECES']
    assert initial['moyens'] == []  # aucun fournisseur non espèces automatique
    config(c, a, [])
    assert c.get(root(a)+'/contexte').json()['configuration']['modes'] == []
    post(c, a, f'/ventes/{v["id"]}/finaliser', body(v, s), 422)
    config(c, a, ['ESPECES'])
    receipt = final(c, a, v, s)
    pdf = c.get(root(a)+f'/recus/{receipt["id"]}/pdf').content
    config(c, a, [])
    assert c.get(root(a)+f'/recus/{receipt["id"]}/pdf').content == pdf
    assert receipt['instantane']['reglements'][0]['mode'] == 'ESPECES'


def test_nouveau_paiement_non_especes_exige_creation_et_choix_explicites(raw_client, account):
    c, a = raw_client, account
    v, s, *_ = ready(c, a)
    data = {'cle':str(uuid4()), 'revision':v['revision'], 'session_id':s['id'],
            'mode':'CARTE', 'montant':100, 'reference':'B01-CARTE',
            'source':'MANUEL_TERMINAL', 'preuve':'Terminal de recette fictif'}
    assert c.post(root(a)+f'/ventes/{v["id"]}/confirmations', json=data).status_code == 422
    m = post(c, a, '/moyens', {'code':'CARTE_B01', 'libelle':'Carte B01', 'mode':'CARTE'})
    cf = c.post(root(a)+f'/ventes/{v["id"]}/confirmations', json={**data, 'cle':str(uuid4()), 'moyen_id':m['id']})
    assert cf.status_code == 201, cf.text
    cf = cf.json()
    assert c.put(root(a)+f'/moyens/{m["id"]}', json={'cle':str(uuid4()), 'revision':1,
                 'libelle':'Carte renommée', 'actif':False}).status_code == 200
    assert c.post(root(a)+f'/ventes/{v["id"]}/confirmations', json={**data,
        'cle':str(uuid4()), 'reference':'B01-INTERDIT', 'moyen_id':m['id']}).status_code == 409
    post(c, a, f'/ventes/{v["id"]}/finaliser', body(v, s, reglements=[
        {'mode':'CARTE', 'montant':100, 'confirmation_id':cf['id']},
        {'mode':'ESPECES', 'montant':300}]), 409)
    assert cf['moyen_libelle'] == 'Carte B01'
    gen = db(c); sql = next(gen)
    try:
        events = list(sql.scalars(select(EvenementCaisseModel).where(
            EvenementCaisseModel.organisation_id == a['org'],
            EvenementCaisseModel.type == 'MOYEN_PAIEMENT_CONFIGURE')))
        assert len(events) == 2
        assert all(e.auteur_id == a['user'] and e.donnees['operation_id'] for e in events)
        modification = next(e for e in events if e.donnees['avant'] is not None)
        assert modification.donnees['avant']['actif'] is True
        assert modification.donnees['apres']['actif'] is False
    finally:
        gen.close()


@pytest.mark.parametrize('blocage', ['fournisseur', 'famille', 'especes'])
def test_substitution_exige_permission_et_remplacement_actif(raw_client, account, blocage):
    from neosys_pharma.infrastructure.securite_models import RolePermissionModel
    from neosys_pharma.domain.organisation.permissions_systeme import permission_id
    c, a = raw_client, account
    v, s, *_ = ready(c, a)
    grant45(c, a)
    original = post(c, a, '/moyens', {'code':'ORIGINE', 'libelle':'Origine', 'mode':'CARTE'})
    cf = post(c, a, f'/ventes/{v["id"]}/confirmations', {
        'revision':v['revision'], 'session_id':s['id'], 'mode':'CARTE', 'moyen_id':original['id'],
        'montant':100, 'source':'MANUEL_TERMINAL', 'reference':'SUB-B01', 'preuve':'Fictive'})
    target = None if blocage=='especes' else post(c, a, '/moyens',
        {'code':'CIBLE', 'libelle':'Cible', 'mode':'CARTE'})
    request = {'confirmation_id':cf['id'], 'session_id':s['id'], 'revision':s['revision'],
        'justification':'Substitution fictive', 'reglements':[{'mode':'CARTE' if target else 'ESPECES',
            'moyen_id':target['id'] if target else None, 'mode_origine':'CARTE',
            'moyen_origine_id':original['id'], 'montant':100}]}
    def revoke(code):
        gen = db(c); sql = next(gen)
        try:
            pid = permission_id(code)
            roles = list(sql.scalars(select(RolePermissionModel.role_id).where(RolePermissionModel.permission_id==pid)))
            sql.execute(RolePermissionModel.__table__.delete().where(RolePermissionModel.permission_id==pid))
            sql.commit()
            return roles
        finally:
            gen.close()
    def restore(code, roles):
        gen = db(c); sql = next(gen)
        try:
            for role in roles:
                sql.add(RolePermissionModel(role_id=role, permission_id=permission_id(code)))
            sql.commit()
        finally:
            gen.close()
    roles = revoke('caisse.remboursement.substituer')
    finance_post(c, a, '/remboursements', request, 403)
    restore('caisse.remboursement.substituer', roles)
    revision = 1
    def active(value):
        nonlocal revision
        if blocage=='fournisseur':
            assert c.put(root(a)+f'/moyens/{target["id"]}', json={'cle':str(uuid4()),
                'revision':revision, 'libelle':'Cible', 'actif':value}).status_code == 200
            revision += 1
        else:
            config(c, a, ['ESPECES','CARTE'] if value else (['CARTE'] if blocage=='especes' else ['ESPECES']))
    active(False)
    refus = 409 if blocage=='fournisseur' else 422
    finance_post(c, a, '/remboursements', request, refus)
    active(True)
    refund = finance_post(c, a, '/remboursements', request)
    refund = finance_post(c, a, f'/remboursements/{refund["id"]}/autoriser',
        {'revision':refund['revision'], 'justification':'Accord fictif'}, 200)
    execution = {'revision':refund['revision'], 'justification':'Exécution fictive',
        'preuves':[{'reference':'SUB-RETOUR', 'preuve':'Preuve fictive'}]}
    active(False)
    finance_post(c, a, f'/remboursements/{refund["id"]}/executer', execution, refus)
    active(True)
    roles = revoke('caisse.remboursement.substituer')
    finance_post(c, a, f'/remboursements/{refund["id"]}/executer', execution, 403)
    restore('caisse.remboursement.substituer', roles)
    roles = revoke('caisse.remboursement.executer')
    finance_post(c, a, f'/remboursements/{refund["id"]}/executer', execution, 403)
    restore('caisse.remboursement.executer', roles)
    result = finance_post(c, a, f'/remboursements/{refund["id"]}/executer', execution, 200)
    assert result['etat'] == 'EXECUTE'
    gen = db(c); sql = next(gen)
    try:
        assert not sql.scalar(select(EvenementCaisseModel).where(EvenementCaisseModel.type ==
            'P4.5:REMBOURSEMENT_HISTORIQUE_MOYEN_DESACTIVE'))
    finally:
        gen.close()


def test_remboursement_historique_especes_desactivees(raw_client, account):
    c, a = raw_client, account
    v, s, *_ = ready(c, a)
    grant45(c, a)
    receipt = final(c, a, v, s)
    returned = ret(c, a, receipt)
    refund = finance_post(c, a, '/remboursements', {
        'retour_id':returned['id'], 'session_id':s['id'], 'revision':current(c,a,s)['revision'],
        'reglements':[{'mode':'ESPECES', 'montant':returned['montant']}], 'justification':'Recette B01'})
    refund = finance_post(c, a, f'/remboursements/{refund["id"]}/autoriser',
                          {'revision':refund['revision'], 'justification':'Autorisation fictive'}, 200)
    config(c, a, [])
    execution = {'revision':refund['revision'], 'justification':'Restitution fictive', 'preuves':[{}]}
    result = finance_post(c, a, f'/remboursements/{refund["id"]}/executer', execution, 200)
    assert result['etat'] == 'EXECUTE'
    assert c.get(root(a)+'/contexte').json()['configuration']['modes'] == []
    gen = db(c); sql = next(gen)
    try:
        event = sql.scalar(select(EvenementCaisseModel).where(EvenementCaisseModel.type ==
            'P4.5:REMBOURSEMENT_HISTORIQUE_MOYEN_DESACTIVE'))
        assert event.donnees['moyens_desactives'][0]['mode'] == 'ESPECES'
    finally:
        gen.close()


def test_especes_desactivees_refusees_a_finalisation_groupe(raw_client, account, monkeypatch):
    from test_caisse import groupe_put, groupe_post, create, line, act
    from test_p4p5_groupe_organismes import draft
    import neosys_pharma.presentation.encaissement_groupe_api as api
    monkeypatch.setattr(api, 'GROUPED_ENCASHMENT_ENABLED', True)
    c, a = raw_client, account
    v, s, product, pack, pid, cid = ready(c, a)
    second = line(c, a, create(c, a, pid), product, pack, 2)
    second = act(c, a, second, 'valider')
    second = act(c, a, second, 'transmettre', caisse_id=cid)
    ident, d = draft(c, a, (v, second), s)
    d = groupe_put(c, a, f'/{ident}/reglements', {'cle':str(uuid4()),
        'revision':d['dossier']['revision'], 'reglements':[{'mode':'ESPECES', 'montant':d['totaux']['du_xaf']}]})
    proposal = c.get(root(a)+f'/groupes/{ident}/allocations/proposition',
                     params={'revision':d['dossier']['revision']}).json()
    d = groupe_put(c, a, f'/{ident}/allocations', {'cle':str(uuid4()),
        'revision':d['dossier']['revision'], 'allocations':proposal})
    config(c, a, [])
    payload = {'cle':str(uuid4()), 'revision':d['dossier']['revision'],
               'revision_session':s['revision'], 'fidelite':[]}
    groupe_post(c, a, f'/{ident}/finaliser', payload, 422)
    config(c, a, ['ESPECES'])
    result = groupe_post(c, a, f'/{ident}/finaliser', payload)
    assert len(result['resultat']['recus_individuels']) == 2


def test_permissions_referentiel_et_configuration(raw_client, account):
    from neosys_pharma.infrastructure.securite_models import RolePermissionModel
    from neosys_pharma.domain.organisation.permissions_systeme import permission_id
    c, a = raw_client, account
    ready(c, a)
    m = post(c, a, '/moyens', {'code':'B01', 'libelle':'Fictif', 'mode':'CARTE'})
    gen = db(c); sql = next(gen)
    try:
        sql.execute(RolePermissionModel.__table__.delete().where(
            RolePermissionModel.permission_id == permission_id('caisse.parametrer')))
        sql.commit()
    finally:
        gen.close()
    post(c, a, '/moyens', {'code':'REFUSE', 'libelle':'Fictif', 'mode':'CARTE'}, 403)
    assert c.put(root(a)+f'/moyens/{m["id"]}', json={'cle':str(uuid4()),
        'revision':1, 'libelle':'Interdit', 'actif':False}).status_code == 403
    post(c, a, '/configuration', {'revision':1, 'modes':[]}, 403)


@pytest.mark.parametrize('source', ['retour', 'acquis'])
@pytest.mark.parametrize('desactivation', ['fournisseur', 'famille'])
@pytest.mark.parametrize('avant_demande', [True, False])
def test_remboursement_historique_moyen_desactive_audite(raw_client, account, source, desactivation, avant_demande):
    c, a = raw_client, account
    v, s, *_ = ready(c, a)
    grant45(c, a)
    m = post(c, a, '/moyens', {'code':'TPE_B01', 'libelle':'TPE B01', 'mode':'CARTE'})
    cf = post(c, a, f'/ventes/{v["id"]}/confirmations', {
        'revision':v['revision'], 'session_id':s['id'], 'mode':'CARTE', 'moyen_id':m['id'],
        'montant':100, 'source':'MANUEL_TERMINAL', 'reference':'B01-REMBOURSEMENT', 'preuve':'Fictive'})
    from neosys_pharma.infrastructure.caisse_models import ConfirmationReglementModel
    from neosys_pharma.application.caisse_service import serial
    from uuid import UUID
    gen = db(c); sql = next(gen)
    try:
        historique = serial(sql.get(ConfirmationReglementModel, UUID(cf['id'])))
    finally:
        gen.close()
    amount = '100';origin = {'confirmation_id':cf['id']}
    if source == 'retour':
        receipt = final(c, a, v, s, reglements=[{'mode':'CARTE', 'montant':100, 'confirmation_id':cf['id']},
            {'mode':'ESPECES', 'montant':300}])
        pdf = c.get(root(a)+f'/recus/{receipt["id"]}/pdf').content
        returned = ret(c, a, receipt)
        amount = returned['montant'];origin = {'retour_id':returned['id']}
    route = root(a)+f'/moyens/{m["id"]}'
    def disable():
        if desactivation == 'fournisseur':
            assert c.put(route, json={'cle':str(uuid4()), 'revision':1, 'libelle':'Nouveau nom', 'actif':False}).status_code == 200
        else:
            config(c, a, ['ESPECES'])
    if avant_demande:
        disable()
    request = {**origin, 'session_id':s['id'], 'revision':current(c,a,s)['revision'],
        'reglements':[{'mode':'CARTE', 'moyen_id':m['id'], 'moyen_origine_id':m['id'], 'montant':amount}],
        'justification':'Restitution fictive'}
    from decimal import Decimal
    over = {**request, 'reglements':[{**request['reglements'][0], 'montant':str(Decimal(amount)+1)}]}
    finance_post(c, a, '/remboursements', over, 409)
    refund = finance_post(c, a, '/remboursements', request)
    execution = {'revision':refund['revision'], 'justification':'Preuve fictive',
                 'preuves':[{'reference':'B01-RETOUR', 'preuve':'Terminal fictif'}]}
    finance_post(c, a, f'/remboursements/{refund["id"]}/executer', execution, 409)
    refund = finance_post(c, a, f'/remboursements/{refund["id"]}/autoriser',
        {'revision':refund['revision'], 'justification':'Accord fictif'}, 200)
    if not avant_demande:
        disable()
    execution = {'revision':refund['revision'], 'justification':'Preuve fictive',
                 'preuves':[{'reference':'B01-RETOUR', 'preuve':'Terminal fictif'}]}
    finance_post(c, a, f'/remboursements/{refund["id"]}/executer', {**execution, 'preuves':[{}]}, 422)
    gen = db(c); sql = next(gen)
    try:
        assert not sql.scalar(select(EvenementCaisseModel).where(EvenementCaisseModel.type ==
            'P4.5:REMBOURSEMENT_HISTORIQUE_MOYEN_DESACTIVE'))
    finally:
        gen.close()
    key = uuid4()
    result = finance_post(c, a, f'/remboursements/{refund["id"]}/executer', execution, 200, key)
    assert finance_post(c, a, f'/remboursements/{refund["id"]}/executer', execution, 200, key) == result
    assert result['reglements'][0]['moyen_origine_libelle'] == 'TPE B01'
    assert result['reglements'][0]['moyen_libelle'] == (
        'Nouveau nom' if avant_demande and desactivation=='fournisseur' else 'TPE B01')
    context = c.get(root(a)+'/contexte').json()['configuration']
    if desactivation == 'fournisseur':
        assert next(x for x in context['moyens'] if x['id']==m['id'])['actif'] is False
    else:
        assert 'CARTE' not in context['modes']
    if source == 'retour':
        assert c.get(root(a)+f'/recus/{receipt["id"]}/pdf').content == pdf
    gen = db(c); sql = next(gen)
    try:
        assert serial(sql.get(ConfirmationReglementModel, UUID(cf['id']))) == historique
        events = list(sql.scalars(select(EvenementCaisseModel).where(EvenementCaisseModel.type ==
            'P4.5:REMBOURSEMENT_HISTORIQUE_MOYEN_DESACTIVE')))
        assert len(events) == 1
        event = events[0]
        assert event.auteur_id == a['user'] and event.donnees['operation_id']
        assert event.donnees['dossier']['demandeur_id'] == str(a['user'])
        assert event.donnees['dossier']['autorisateur_id'] == str(a['user'])
        assert event.donnees['justification'] == execution['justification']
        assert event.donnees['preuves'] == execution['preuves']
        assert event.donnees['moyens_desactives'][0]['moyen_id'] == m['id']
        assert event.donnees['dossier']['etat'] == 'EXECUTE'
    finally:
        gen.close()
