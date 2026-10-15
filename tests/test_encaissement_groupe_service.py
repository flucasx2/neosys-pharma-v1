"""Contrôles ciblés du service et du contrat API introduits en 3.3."""
from decimal import Decimal
from uuid import uuid4

import pytest
from sqlalchemy import select, func

from test_caisse import raw_client, account, ready, post, db, root, stocks, category, rule
from test_vente import create, line, act
from neosys_pharma.domain.stock import ConflitStock
from neosys_pharma.application.encaissement_groupe_service import repartir_allocations
from neosys_pharma.domain.organisation.permissions_systeme import permission_id
from neosys_pharma.infrastructure.securite_models import RoleModel, RolePermissionModel
from neosys_pharma.infrastructure.vente_models import VenteModel
from neosys_pharma.infrastructure.caisse_models import (
    EncaissementModel, PeriodeCaisseSiteModel,
)
from neosys_pharma.infrastructure.encaissement_groupe_models import (
    VentilationEncaissementModel, AllocationReglementModel, VenteEncaisseeModel,
)


def groupe_root(a):
    return root(a) + '/encaissements-groupes'


def enable_group(monkeypatch):
    from neosys_pharma.presentation import encaissement_groupe_api
    monkeypatch.setattr(encaissement_groupe_api, 'GROUPED_ENCASHMENT_ENABLED', True)


def grant_group_role(c, a, code='caisse.encaisser.groupe'):
    gen = db(c); session = next(gen)
    try:
        role = session.scalar(select(RoleModel).where(
            RoleModel.organisation_id == a['org'], RoleModel.code == 'CATALOGUE'))
        if not session.scalar(select(RolePermissionModel).where(
                RolePermissionModel.role_id == role.id_role,
                RolePermissionModel.permission_id == permission_id(code))):
            session.add(RolePermissionModel(role_id=role.id_role,
                permission_id=permission_id(code)))
        session.commit()
    finally:
        gen.close()


def second_sale(c, a, prepared, session_id):
    product, pack, product_id = prepared[2], prepared[3], prepared[4]
    sale = line(c, a, create(c, a, product_id), product, pack, 3)
    sale = act(c, a, sale, 'valider')
    return act(c, a, sale, 'transmettre', caisse_id=prepared[5])


def set_common_recipient(c, a, sale_ids):
    gen = db(c); session = next(gen)
    try:
        for sale_id in sale_ids:
            from uuid import UUID
            sale = session.get(VenteModel, UUID(str(sale_id)))
            sale.destinataire = {'nom': 'Client Groupe'}
        session.commit()
    finally:
        gen.close()


def test_repartition_exacte_et_paiement_individuel_ancre():
    sale_a, sale_b, line_a, line_b = [uuid4() for _ in range(4)]
    rows = repartir_allocations(
        [{'mode': 'CARTE', 'montant': Decimal(101), 'rendu': Decimal(0), 'vente_ancree': sale_a},
         {'mode': 'ESPECES', 'montant': Decimal(100), 'rendu': Decimal(0)}],
        [{'vente_id': str(sale_a), 'ligne_id': str(line_a), 'montant': Decimal(101)},
         {'vente_id': str(sale_b), 'ligne_id': str(line_b), 'montant': Decimal(100)}])
    assert sum(x['montant'] for x in rows if x['vente_id'] == sale_a) == 101
    assert sum(x['montant'] for x in rows if x['vente_id'] == sale_b) == 100
    with pytest.raises(ConflitStock):
        repartir_allocations([{'mode': 'ESPECES', 'montant': Decimal(200), 'rendu': Decimal(0),
                              'vente_ancree': sale_a}],
            [{'vente_id': str(sale_a), 'ligne_id': str(line_a), 'montant': Decimal(101)},
             {'vente_id': str(sale_b), 'ligne_id': str(line_b), 'montant': Decimal(100)}])


def test_parcours_ferme_par_defaut_et_double_permission(raw_client, account):
    c, a = raw_client, account
    prepared = ready(c, a, q=3)
    other = second_sale(c, a, prepared, prepared[1]['id'])
    set_common_recipient(c, a, [prepared[0]['id'], other['id']])
    payload = {'session_id': prepared[1]['id'], 'revision_session': prepared[1]['revision'],
               'ventes': [{'vente_id': prepared[0]['id'], 'revision': prepared[0]['revision']},
                          {'vente_id': other['id'], 'revision': other['revision']}],
               'identite_commune_confirmee': True}
    response = c.post(groupe_root(a) + '/previsualiser', json=payload)
    assert response.status_code == 404


def test_finalisation_atomique_recu_unique_et_rejeu(raw_client, account, monkeypatch):
    c, a = raw_client, account
    prepared = ready(c, a, q=3)
    other = second_sale(c, a, prepared, prepared[1]['id'])
    set_common_recipient(c, a, [prepared[0]['id'], other['id']])
    loyalty = post(c, a, '/fidelite', {'nom': 'Compte groupe'})
    rule(c, a, category(c, a, prepared[2]))
    group_path = groupe_root(a)
    create_body = {'cle': str(uuid4()), 'session_id': prepared[1]['id'],
        'revision_session': prepared[1]['revision'], 'ventes': [
            {'vente_id': prepared[0]['id'], 'revision': prepared[0]['revision']},
            {'vente_id': other['id'], 'revision': other['revision']}],
        'identite_commune_confirmee': True, 'compte_id': loyalty['id'],
        'revision_compte': loyalty['revision']}
    response = c.post(group_path, json=create_body)
    assert response.status_code == 404
    enable_group(monkeypatch)
    denied = c.post(group_path, json=create_body)
    assert denied.status_code == 403
    grant_group_role(c, a)
    dossier = c.post(group_path, json=create_body)
    assert dossier.status_code == 201, dossier.text
    dossier = dossier.json();key = uuid4()
    close_before_final = c.post(root(a) + '/sessions/' + prepared[1]['id'] + '/fermer', json={
        'cle': str(uuid4()), 'revision': prepared[1]['revision'], 'comptage_final': 0,
        'justification': 'Test ciblé dossier ouvert'})
    assert close_before_final.status_code == 409
    confirmation_body = {'cle': str(uuid4()), 'revision': dossier['revision'],
        'revision_session': prepared[1]['revision'], 'session_id': prepared[1]['id'],
        'mode': 'CARTE', 'montant': 200, 'reference': 'TERM-GROUPE-1',
        'source': 'MANUEL_TERMINAL', 'preuve': 'Reçu du terminal autonome'}
    invalid = dict(confirmation_body, cle=str(uuid4()), source='TECHNIQUE_PRESTATAIRE')
    assert c.post(group_path + '/' + dossier['id'] + '/confirmations', json=invalid).status_code == 422
    confirmation = c.post(group_path + '/' + dossier['id'] + '/confirmations', json=confirmation_body)
    assert confirmation.status_code == 201, confirmation.text
    confirmation = confirmation.json()
    assert c.post(group_path + '/' + dossier['id'] + '/confirmations', json=confirmation_body).json() == confirmation
    payload = {'cle': str(key), 'revision': dossier['revision'] + 1,
        'empreinte': dossier['empreinte_selection'], 'session_id': prepared[1]['id'],
        'revision_session': prepared[1]['revision'], 'ventes': create_body['ventes'],
        'compte_id': loyalty['id'], 'revision_compte': loyalty['revision'],
        'reglements': [{'mode': 'CARTE', 'montant': 200, 'confirmation_id': confirmation['id']},
                       {'mode': 'ESPECES', 'montant': 500}]}
    result = c.post(group_path + '/' + dossier['id'] + '/finaliser', json=payload)
    assert result.status_code == 200, result.text
    result = result.json()
    assert result['type_encaissement'] == 'GROUPE'
    assert len(result['ventilations']) == 2
    assert sum(Decimal(x['net_ttc']) for x in result['ventilations']) == Decimal(result['total_xaf'])
    assert sum(Decimal(x['rendu']) for x in result['instantane']['reglements']) == 98
    current_loyalty = c.get(root(a) + '/fidelite/' + loyalty['id']).json()
    assert current_loyalty['points'] == 6
    assert c.get(root(a) + '/fidelite/' + loyalty['id'] + '/journal').json()['total'] == 1
    assert c.post(group_path + '/' + dossier['id'] + '/finaliser', json=payload).json() == result
    receipt = c.get(root(a) + '/recus/' + result['id'])
    assert receipt.status_code == 200
    listed_receipts = c.get(root(a) + '/recus').json()['items']
    assert any(item['id'] == result['id'] for item in listed_receipts)
    pdf = c.get(root(a) + '/recus/' + result['id'] + '/pdf')
    assert pdf.status_code == 200 and pdf.content.startswith(b'%PDF')
    individual_path = '/ventes/' + prepared[0]['id'] + '/finaliser'
    assert c.post(root(a) + individual_path, json={
        'cle': str(uuid4()), 'revision': prepared[0]['revision'],
        'session_id': prepared[1]['id'], 'revision_session': prepared[1]['revision'],
        'reglements': [{'mode': 'ESPECES', 'montant': 301}], 'points_utilises': 0,
        'consentement': False}).status_code == 409
    retour_root = '/api/regularisations/organisations/' + str(a['org'])
    grant_group_role(c, a, 'vente.retour.gerer')
    assert c.get(retour_root + '/recus/' + result['id'] + '/retournable').status_code == 422
    returnable = c.get(retour_root + '/recus/' + result['id'] + '/retournable', params={
        'ventilation_id': result['ventilations'][0]['ventilation_id']})
    assert returnable.status_code == 200
    returnable = returnable.json()
    assert returnable['vente_id'] == result['ventilations'][0]['vente_id']
    first_line = returnable['lignes'][0]
    returned = c.post(retour_root + '/retours', json={
        'cle': str(uuid4()), 'encaissement_id': result['id'],
        'ventilation_id': result['ventilations'][0]['ventilation_id'],
        'lignes': [{'ligne_id': first_line['ligne_id'], 'stock_id': first_line['stock_id'], 'quantite': 1}],
        'justification': 'Retour rattaché à la vente ventilée'})
    assert returned.status_code == 201, returned.text
    assert returned.json()['ventilation_id'] == result['ventilations'][0]['ventilation_id']
    assert stocks(c, a)[0]['reserve'] == 0 and stocks(c, a)[0]['physique'] == 4
    gen = db(c); session = next(gen)
    try:
        assert session.scalar(select(func.count()).select_from(EncaissementModel)) == 1
        assert session.scalar(select(func.count()).select_from(VentilationEncaissementModel)) == 2
        assert session.scalar(select(func.count()).select_from(VenteEncaisseeModel)) == 2
        assert session.scalar(select(PeriodeCaisseSiteModel.prochain_encaissement)) == 2
    finally:
        gen.close()
