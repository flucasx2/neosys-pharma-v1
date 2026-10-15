"""Vérifications métier ciblées de l’étape 3.4 sur SQLite embarqué.

Ces tests ne valident pas la concurrence PostgreSQL native; ils vérifient
les allocations de retour/remboursement et le rollback applicatif.
"""
from decimal import Decimal
from uuid import UUID, uuid4

import pytest
from sqlalchemy import select, func

from test_caisse import raw_client, account, ready, post, db, root, stocks, category, rule
from test_vente import create, line, act
from test_encaissement_groupe_service import enable_group, groupe_root
from neosys_pharma.domain.organisation.permissions_systeme import (
    permission_id, REGULARISATION_PERMISSIONS,
)
from neosys_pharma.infrastructure.securite_models import RoleModel, RolePermissionModel
from neosys_pharma.infrastructure.vente_models import VenteModel
from neosys_pharma.infrastructure.caisse_models import (
    CompteFideliteModel, EncaissementModel, JournalFideliteModel,
    MouvementCaisseModel, PeriodeCaisseSiteModel, ReglementModel,
)
from neosys_pharma.infrastructure.encaissement_groupe_models import (
    VentilationEncaissementModel, AllocationReglementModel,
)
from neosys_pharma.infrastructure.regularisation_models import (
    CompensationRetourModel, RemboursementModel,
)


def grant_test_permissions(c, a):
    permissions = {'caisse.encaisser.groupe'} | {code for code, _ in REGULARISATION_PERMISSIONS}
    gen = db(c); session = next(gen)
    try:
        role = session.scalar(select(RoleModel).where(
            RoleModel.organisation_id == a['org'], RoleModel.code == 'CATALOGUE'))
        for code in permissions:
            if not session.scalar(select(RolePermissionModel).where(
                    RolePermissionModel.role_id == role.id_role,
                    RolePermissionModel.permission_id == permission_id(code))):
                session.add(RolePermissionModel(role_id=role.id_role,
                    permission_id=permission_id(code)))
        session.commit()
    finally:
        gen.close()


def create_two_sales(c, a, prepared):
    product, pack, product_id, cash_id = prepared[2], prepared[3], prepared[4], prepared[5]
    other = line(c, a, create(c, a, product_id), product, pack, 3)
    other = act(c, a, other, 'valider')
    other = act(c, a, other, 'transmettre', caisse_id=cash_id)
    gen = db(c); session = next(gen)
    try:
        for ident in (prepared[0]['id'], other['id']):
            session.get(VenteModel, UUID(str(ident))).destinataire = {'nom': 'Client groupe'}
        session.commit()
    finally:
        gen.close()
    return other


def prepare_group(c, a, monkeypatch):
    prepared = ready(c, a, q=3)
    other = create_two_sales(c, a, prepared)
    loyalty = post(c, a, '/fidelite', {'nom': 'Fidélité groupée'})
    rule(c, a, category(c, a, prepared[2]))
    grant_test_permissions(c, a)
    enable_group(monkeypatch)
    body = {'cle': str(uuid4()), 'session_id': prepared[1]['id'],
        'revision_session': prepared[1]['revision'], 'ventes': [
            {'vente_id': prepared[0]['id'], 'revision': prepared[0]['revision']},
            {'vente_id': other['id'], 'revision': other['revision']}],
        'compte_id': loyalty['id'], 'revision_compte': loyalty['revision'],
        'identite_commune_confirmee': True}
    response = c.post(groupe_root(a), json=body)
    assert response.status_code == 201, response.text
    dossier = response.json()
    confirmation_body = {'cle': str(uuid4()), 'revision': dossier['revision'],
        'revision_session': prepared[1]['revision'], 'session_id': prepared[1]['id'],
        'mode': 'CARTE', 'montant': 200, 'reference': 'TERM-3.4',
        'source': 'MANUEL_TERMINAL', 'preuve': 'Terminal autonome accepté'}
    confirmation_response = c.post(groupe_root(a) + '/' + dossier['id'] + '/confirmations',
                                   json=confirmation_body)
    assert confirmation_response.status_code == 201, confirmation_response.text
    confirmation = confirmation_response.json()
    finalisation = {'cle': str(uuid4()), 'revision': dossier['revision'] + 1,
        'empreinte': dossier['empreinte_selection'], 'session_id': prepared[1]['id'],
        'revision_session': prepared[1]['revision'], 'ventes': body['ventes'],
        'compte_id': loyalty['id'], 'revision_compte': loyalty['revision'],
        'reglements': [{'mode': 'CARTE', 'montant': 200, 'confirmation_id': confirmation['id']},
                       {'mode': 'ESPECES', 'montant': 500}]}
    return prepared, other, loyalty, dossier, finalisation


def counts(c, cls):
    gen = db(c); session = next(gen)
    try:
        return session.scalar(select(func.count()).select_from(cls))
    finally:
        gen.close()


def test_retour_groupé_remboursement_par_allocation_et_compensation_unique(
        raw_client, account, monkeypatch):
    c, a = raw_client, account
    prepared, other, loyalty, dossier, finalisation = prepare_group(c, a, monkeypatch)
    group_path = groupe_root(a)
    paid = c.post(group_path + '/' + dossier['id'] + '/finaliser', json=finalisation)
    assert paid.status_code == 200, paid.text
    receipt = paid.json()
    first_vent = receipt['ventilations'][0]

    finance_root = '/api/regularisations/organisations/' + str(a['org'])
    returnable = c.get(finance_root + '/recus/' + receipt['id'] + '/retournable',
        params={'ventilation_id': first_vent['ventilation_id']})
    assert returnable.status_code == 200, returnable.text
    rows = returnable.json()['lignes']
    assert sum(x['quantite_restante'] for x in rows) == 3
    returned = c.post(finance_root + '/retours', json={'cle': str(uuid4()),
        'encaissement_id': receipt['id'], 'ventilation_id': first_vent['ventilation_id'],
        'lignes': [{'ligne_id': x['ligne_id'], 'stock_id': x['stock_id'], 'quantite': x['quantite_restante']} for x in rows],
        'justification': 'Retour intégral de cette vente uniquement'})
    assert returned.status_code == 201, returned.text
    retour = returned.json()
    assert retour['montant'] == '301'

    balance = c.get(finance_root + '/retours/' + retour['id'] + '/solde')
    assert balance.status_code == 200, balance.text
    by_mode = balance.json()['disponible_par_mode']
    assert by_mode['CARTE'] == '100'
    assert by_mode['ESPECES'] == '201'

    bad = c.post(finance_root + '/remboursements', json={'cle': str(uuid4()),
        'session_id': prepared[1]['id'], 'revision': 2, 'retour_id': retour['id'],
        'reglements': [{'mode': 'CARTE', 'montant': 101},
                       {'mode': 'ESPECES', 'montant': 200}],
        'justification': 'Tentative au-delà de la part carte de cette vente'})
    assert bad.status_code == 409
    assert counts(c, RemboursementModel) == 0

    request = c.post(finance_root + '/remboursements', json={'cle': str(uuid4()),
        'session_id': prepared[1]['id'], 'revision': 2, 'retour_id': retour['id'],
        'reglements': [{'mode': 'CARTE', 'montant': 100},
                       {'mode': 'ESPECES', 'montant': 201}],
        'justification': 'Remboursement selon les règlements alloués'})
    assert request.status_code == 201, request.text
    refund = request.json()
    repeated = c.post(finance_root + '/remboursements', json={'cle': str(uuid4()),
        'session_id': prepared[1]['id'], 'revision': 2, 'retour_id': retour['id'],
        'reglements': [{'mode': 'CARTE', 'montant': 100},
                       {'mode': 'ESPECES', 'montant': 201}],
        'justification': 'Deuxième demande en doublon'})
    assert repeated.status_code == 409
    assert counts(c, RemboursementModel) == 1

    authorized = c.post(finance_root + '/remboursements/' + refund['id'] + '/autoriser',
        json={'cle': str(uuid4()), 'revision': refund['revision'],
              'justification': 'Contrôle du remboursement'})
    assert authorized.status_code == 200, authorized.text
    refund = authorized.json()
    executed = c.post(finance_root + '/remboursements/' + refund['id'] + '/executer',
        json={'cle': str(uuid4()), 'revision': refund['revision'],
              'justification': 'Restitution exécutée', 'preuves': [
                  {'reference': 'REFUND-CARD-34', 'preuve': 'Terminal confirmé'},
                  {'reference': None, 'preuve': None}]})
    assert executed.status_code == 200, executed.text

    gen = db(c); session = next(gen)
    try:
        assert session.get(CompteFideliteModel, UUID(loyalty['id'])).points == 3
        assert session.scalar(select(func.count()).select_from(CompensationRetourModel)) == 1
        assert session.scalar(select(func.count()).select_from(JournalFideliteModel)
            .where(JournalFideliteModel.type.in_(('ACQUISITION', 'REVOCATION')))) == 2
        vents = session.scalars(select(VentilationEncaissementModel).order_by(VentilationEncaissementModel.id)).all()
        assert len(vents) == 2
        second = next(x for x in vents if x.vente_id == UUID(other['id']))
        allocations = session.scalars(select(AllocationReglementModel).where(
            AllocationReglementModel.ventilation_id == second.id)).all()
        assert sum((x.montant_net for x in allocations), Decimal(0)) == Decimal(301)
        assert session.scalar(select(func.count()).select_from(MouvementCaisseModel)) == 2
    finally:
        gen.close()


def test_rejeu_meme_cle_autre_contenu_est_refuse(raw_client, account, monkeypatch):
    c, a = raw_client, account
    prepared, other, loyalty, dossier, finalisation = prepare_group(c, a, monkeypatch)
    path = groupe_root(a) + '/' + dossier['id'] + '/finaliser'
    result = c.post(path, json=finalisation)
    assert result.status_code == 200, result.text
    changed = dict(finalisation)
    changed['reglements'] = [{'mode': 'ESPECES', 'montant': 602}]
    conflict = c.post(path, json=changed)
    assert conflict.status_code == 409
    assert counts(c, EncaissementModel) == 1


def test_rollback_apres_mutations_avant_commit(raw_client, account, monkeypatch):
    c, a = raw_client, account
    prepared, other, loyalty, dossier, finalisation = prepare_group(c, a, monkeypatch)
    from neosys_pharma.application.caisse_service import CaisseService
    original = CaisseService.consommer_reservations
    calls = {'count': 0}
    def consume_then_fail(service, sale):
        original(service, sale)
        calls['count'] += 1
        if calls['count'] == 1:
            raise ValueError('Échec volontaire de validation avant commit')
    monkeypatch.setattr(CaisseService, 'consommer_reservations', consume_then_fail)
    path = groupe_root(a) + '/' + dossier['id'] + '/finaliser'
    failed = c.post(path, json=finalisation)
    assert failed.status_code == 422
    assert stocks(c, a)[0]['physique'] == 10
    assert stocks(c, a)[0]['reserve'] == 6
    assert c.get(root(a) + '/fidelite/' + loyalty['id']).json()['points'] == 0
    assert counts(c, EncaissementModel) == 0
    assert counts(c, ReglementModel) == 0
    assert counts(c, MouvementCaisseModel) == 0
    gen = db(c); session = next(gen)
    try:
        assert session.scalar(select(PeriodeCaisseSiteModel.prochain_encaissement)) == 1
        assert session.get(VenteModel, UUID(prepared[0]['id'])).etat == 'TRANSMISE'
    finally:
        gen.close()
