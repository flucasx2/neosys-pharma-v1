"""ScÃ©narios PostgreSQL natif 3.4 complÃ©mentaires.

Ces tests sont volontairement refusÃ©s hors de la base locale dÃ©diÃ©e
neosys_p46_validation_34_temp. Ils doivent Ãªtre lancÃ©s par le script Windows
fourni, aprÃ¨s crÃ©ation vÃ©rifiÃ©e et migration de cette base.
"""
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeout
from decimal import Decimal
from threading import Event, Lock
from time import monotonic, sleep
from uuid import UUID, uuid4
import os

import pytest
from sqlalchemy import create_engine, select, func, text
from sqlalchemy.engine import make_url

from test_caisse import raw_client, account, ready, post, db, root, stocks, category, rule
from test_vente import create, line, act
from test_encaissement_groupe_service import (
    groupe_root, enable_group, grant_group_role, second_sale, set_common_recipient,
)
from neosys_pharma.application.caisse_service import CaisseService
from neosys_pharma.application.encaissement_groupe_service import EncaissementGroupeService
from neosys_pharma.infrastructure.caisse_models import (
    EncaissementModel, ReglementModel, MouvementCaisseModel,
    JournalFideliteModel, PeriodeCaisseSiteModel,
    SessionCaisseModel,
)
from neosys_pharma.infrastructure.encaissement_groupe_models import (
    VenteEncaisseeModel, VentilationEncaissementModel, AllocationReglementModel,
)
from neosys_pharma.infrastructure.regularisation_models import (
    CompensationRetourModel, RemboursementModel,
)
from neosys_pharma.infrastructure.vente_models import VenteModel


DATABASE_NAME = 'neosys_p46_validation_34_concurrence_temp'


@pytest.fixture(scope='session', autouse=True)
def verifier_postgresql_jetable():
    url = os.getenv('DATABASE_URL', '')
    if not url or os.getenv('EG34_CONFIRM_DATABASE') != DATABASE_NAME:
        pytest.fail('Tests refusÃ©s : DATABASE_URL et EG34_CONFIRM_DATABASE doivent viser la base jetable 3.4.')
    parsed = make_url(url)
    if (parsed.get_backend_name() != 'postgresql'
            or parsed.database != DATABASE_NAME
            or parsed.host not in ('localhost', '127.0.0.1', '::1')):
        pytest.fail('Tests refusÃ©s : PostgreSQL local et base neosys_p46_validation_34_temp requis.')
    engine = create_engine(url, connect_args={'connect_timeout': 5})
    try:
        with engine.connect() as conn:
            identity = conn.execute(text(
                "SELECT current_database(), current_user, inet_server_addr()::text, "
                "inet_server_port(), current_setting('server_version_num')::int, "
                "current_setting('lock_timeout'), current_setting('statement_timeout')"
            )).one()
            assert identity[0] == DATABASE_NAME
            assert identity[4] >= 180000, f'PostgreSQL 18+ requis, serveur dÃ©tectÃ©: {identity[4]}'
            assert identity[5] != '0' and identity[6] != '0', 'DÃ©lais SQL bornÃ©s requis.'
            versions = conn.execute(text('SELECT version_num FROM alembic_version')).scalars().all()
            assert versions == ['eg32a2026'], f'Migration attendue absente ou head inattendu: {versions}'
            print('PostgreSQL 3.4:', identity)
    finally:
        engine.dispose()


def _preparer(c, a, monkeypatch):
    enable_group(monkeypatch)
    prepared = ready(c, a, q=3)
    other = second_sale(c, a, prepared, prepared[1]['id'])
    set_common_recipient(c, a, [prepared[0]['id'], other['id']])
    loyalty = post(c, a, '/fidelite', {'nom': 'FidÃ©litÃ© validation native 3.4'})
    rule(c, a, category(c, a, prepared[2]))
    grant_group_role(c, a)
    grant_group_role(c, a, 'vente.retour.gerer')
    selection = [
        {'vente_id': prepared[0]['id'], 'revision': prepared[0]['revision']},
        {'vente_id': other['id'], 'revision': other['revision']},
    ]
    body = {
        'cle': str(uuid4()), 'session_id': prepared[1]['id'],
        'revision_session': prepared[1]['revision'], 'ventes': selection,
        'compte_id': loyalty['id'], 'revision_compte': loyalty['revision'],
        'identite_commune_confirmee': True,
    }
    response = c.post(groupe_root(a), json=body)
    assert response.status_code == 201, response.text
    dossier = response.json()
    finalisation = {
        'cle': str(uuid4()), 'revision': dossier['revision'],
        'empreinte': dossier['empreinte_selection'],
        'session_id': prepared[1]['id'], 'revision_session': prepared[1]['revision'],
        'ventes': selection, 'compte_id': loyalty['id'],
        'revision_compte': loyalty['revision'],
        'reglements': [{'mode': 'ESPECES', 'montant': 602}],
    }
    return prepared, other, loyalty, dossier, finalisation, body


def _deux_requetes_concurrentes(c, requests, monkeypatch):
    """Maintient la premiÃ¨re transaction ouverte jusqu'Ã  observer l'autre en attente PG."""
    first_entered = Event()
    release_first = Event()
    once_lock = Lock()
    held = {'value': False}
    original = EncaissementGroupeService._fidelite_groupe

    def hold_first_transaction(service, *args, **kwargs):
        should_hold = False
        with once_lock:
            if not held['value']:
                held['value'] = True
                should_hold = True
        if should_hold:
            first_entered.set()
            if not release_first.wait(timeout=10):
                raise TimeoutError('barriÃ¨re de transaction PostgreSQL expirÃ©e')
        return original(service, *args, **kwargs)

    monkeypatch.setattr(EncaissementGroupeService, '_fidelite_groupe', hold_first_transaction)
    executor = ThreadPoolExecutor(max_workers=2)
    first = executor.submit(c.post, requests[0][0], json=requests[0][1])
    second = None
    try:
        assert first_entered.wait(timeout=5), 'la premiÃ¨re transaction nâ€™a pas atteint le point de synchronisation'
        second = executor.submit(c.post, requests[1][0], json=requests[1][1])
        engine = create_engine(os.environ['DATABASE_URL'], connect_args={'connect_timeout': 5})
        try:
            deadline = monotonic() + 5
            waiting = False
            while monotonic() < deadline:
                with engine.connect() as conn:
                    waiting = bool(conn.execute(text(
                        "SELECT count(*) FROM pg_stat_activity WHERE datname=current_database() "
                        "AND pid <> pg_backend_pid() AND wait_event_type='Lock'"
                    )).scalar())
                if waiting:
                    break
                sleep(0.05)
        finally:
            engine.dispose()
        release_first.set()
        if not waiting:
            pytest.fail('Aucune seconde connexion en attente de verrou PostgreSQL observÃ©e; concurrence non dÃ©montrÃ©e.')
        return [first.result(timeout=25), second.result(timeout=25)]
    except FutureTimeout:
        pytest.fail('RequÃªte concurrente bloquÃ©e au-delÃ  de 25 secondes; vÃ©rifier statement_timeout PostgreSQL.')
    finally:
        release_first.set()
        executor.shutdown(wait=False, cancel_futures=True)


def _count(c, model, where=None):
    gen = db(c)
    session = next(gen)
    try:
        query = select(func.count()).select_from(model)
        if where is not None:
            query = query.where(where)
        return session.scalar(query)
    finally:
        gen.close()


def _creer_second_dossier(c, a, finalisation, selection_body):
    response = c.post(groupe_root(a), json=selection_body | {'cle': str(uuid4())})
    assert response.status_code == 201, response.text
    dossier = response.json()
    payload = {
        'cle': str(uuid4()), 'revision': dossier['revision'],
        'empreinte': dossier['empreinte_selection'],
        'session_id': finalisation['session_id'],
        'revision_session': finalisation['revision_session'],
        'ventes': finalisation['ventes'], 'compte_id': finalisation['compte_id'],
        'revision_compte': finalisation['revision_compte'],
        'reglements': [{'mode': 'ESPECES', 'montant': 602}],
    }
    return dossier, payload


def test_deux_dossiers_groupes_concurrents_meme_vente(raw_client, account, monkeypatch):
    c, a = raw_client, account
    prepared, other, loyalty, first, payload_a, create_body = _preparer(c, a, monkeypatch)
    second, payload_b = _creer_second_dossier(c, a, payload_a, create_body)
    path_a = groupe_root(a) + '/' + first['id'] + '/finaliser'
    path_b = groupe_root(a) + '/' + second['id'] + '/finaliser'
    results = _deux_requetes_concurrentes(c, [(path_a, payload_a), (path_b, payload_b)], monkeypatch)
    assert sorted(r.status_code for r in results) == [200, 409], [r.text for r in results]
    assert _count(c, EncaissementModel) == 1
    assert _count(c, VenteEncaisseeModel) == 2
    assert _count(c, ReglementModel) == 1
    assert _count(c, MouvementCaisseModel) == 1
    assert c.get(root(a) + '/fidelite/' + loyalty['id']).json()['points'] == 6
    assert stocks(c, a)[0]['physique'] == 4 and stocks(c, a)[0]['reserve'] == 0


def test_encaissement_individuel_contre_groupe_meme_vente(raw_client, account, monkeypatch):
    c, a = raw_client, account
    prepared, other, loyalty, dossier, group_payload, _ = _preparer(c, a, monkeypatch)
    individual_path = root(a) + '/ventes/' + prepared[0]['id'] + '/finaliser'
    individual_payload = {
        'cle': str(uuid4()), 'revision': prepared[0]['revision'],
        'session_id': prepared[1]['id'], 'revision_session': prepared[1]['revision'],
        'reglements': [{'mode': 'ESPECES', 'montant': 301}],
        'points_utilises': 0, 'consentement': False,
    }
    group_path = groupe_root(a) + '/' + dossier['id'] + '/finaliser'
    results = _deux_requetes_concurrentes(c, [(group_path, group_payload), (individual_path, individual_payload)], monkeypatch)
    assert sum(r.status_code in (200, 201) for r in results) == 1, [r.text for r in results]
    assert sum(r.status_code == 409 for r in results) == 1, [r.text for r in results]
    group_won = results[1].status_code == 200
    assert _count(c, EncaissementModel) == 1
    assert _count(c, VenteEncaisseeModel) == (2 if group_won else 1)
    assert _count(c, ReglementModel) == (1 if group_won else 1)
    assert _count(c, MouvementCaisseModel) == 1
    assert c.get(root(a) + '/fidelite/' + loyalty['id']).json()['points'] == (6 if group_won else 0)
    assert stocks(c, a)[0]['physique'] == (4 if group_won else 7)
    assert stocks(c, a)[0]['reserve'] == (0 if group_won else 3)


def test_finalisations_simultanees_meme_dossier_meme_cle(raw_client, account, monkeypatch):
    c, a = raw_client, account
    prepared, other, loyalty, dossier, payload, _ = _preparer(c, a, monkeypatch)
    path = groupe_root(a) + '/' + dossier['id'] + '/finaliser'
    results = _deux_requetes_concurrentes(c, [(path, payload), (path, payload)], monkeypatch)
    assert [r.status_code for r in results] == [200, 200], [r.text for r in results]
    assert results[0].json() == results[1].json()
    assert _count(c, EncaissementModel) == 1
    assert _count(c, ReglementModel) == 1
    assert _count(c, MouvementCaisseModel) == 1
    assert _count(c, VenteEncaisseeModel) == 2
    assert c.get(root(a) + '/fidelite/' + loyalty['id']).json()['points'] == 6


def test_meme_cle_concurrente_contenus_differents(raw_client, account, monkeypatch):
    c, a = raw_client, account
    prepared, other, loyalty, dossier, payload, _ = _preparer(c, a, monkeypatch)
    changed = dict(payload)
    changed['reglements'] = [{'mode': 'ESPECES', 'montant': 700}]
    path = groupe_root(a) + '/' + dossier['id'] + '/finaliser'
    results = _deux_requetes_concurrentes(c, [(path, payload), (path, changed)], monkeypatch)
    assert sorted(r.status_code for r in results) == [200, 409], [r.text for r in results]
    assert _count(c, EncaissementModel) == 1
    assert _count(c, VenteEncaisseeModel) == 2
    assert _count(c, ReglementModel) == 1
    assert _count(c, MouvementCaisseModel) == 1


def test_rollback_integral_apres_mutation_stock_avant_commit(raw_client, account, monkeypatch):
    c, a = raw_client, account
    prepared, other, loyalty, dossier, payload, _ = _preparer(c, a, monkeypatch)
    original = CaisseService.consommer_reservations
    calls = {'count': 0}

    def consume_then_fail(service, sale):
        original(service, sale)
        calls['count'] += 1
        if calls['count'] == 1:
            raise ValueError('Ã‰chec volontaire avant commit PostgreSQL')

    monkeypatch.setattr(CaisseService, 'consommer_reservations', consume_then_fail)
    response = c.post(groupe_root(a) + '/' + dossier['id'] + '/finaliser', json=payload)
    assert response.status_code == 422, response.text
    assert stocks(c, a)[0]['physique'] == 10 and stocks(c, a)[0]['reserve'] == 6
    assert c.get(root(a) + '/fidelite/' + loyalty['id']).json()['points'] == 0
    assert _count(c, EncaissementModel) == 0
    assert _count(c, ReglementModel) == 0
    assert _count(c, MouvementCaisseModel) == 0
    assert _count(c, VenteEncaisseeModel) == 0
    gen = db(c)
    session = next(gen)
    try:
        assert session.scalar(select(PeriodeCaisseSiteModel.prochain_encaissement)) == 1
        assert session.get(VenteModel, UUID(prepared[0]['id'])).etat == 'TRANSMISE'
        assert session.get(VenteModel, UUID(other['id'])).etat == 'TRANSMISE'
    finally:
        gen.close()


def _session_revision(c, session_id):
    gen = db(c)
    session = next(gen)
    try:
        return session.get(SessionCaisseModel, UUID(session_id)).revision
    finally:
        gen.close()


def test_retours_partiels_successifs_remboursement_fidelite_et_trace(
        raw_client, account, monkeypatch):
    c, a = raw_client, account
    prepared, other, loyalty, dossier, payload, _ = _preparer(c, a, monkeypatch)
    group_path = groupe_root(a) + '/' + dossier['id'] + '/finaliser'
    paid = c.post(group_path, json=payload)
    assert paid.status_code == 200, paid.text
    receipt = paid.json()
    target = receipt['ventilations'][0]
    other_vente_id = UUID(other['id'])
    finance = '/api/regularisations/organisations/' + str(a['org'])

    for index in range(3):
        returnable = c.get(finance + '/recus/' + receipt['id'] + '/retournable', params={
            'ventilation_id': target['ventilation_id']})
        assert returnable.status_code == 200, returnable.text
        row = next(line for line in returnable.json()['lignes'] if line['quantite_restante'] > 0)
        returned = c.post(finance + '/retours', json={
            'cle': str(uuid4()), 'encaissement_id': receipt['id'],
            'ventilation_id': target['ventilation_id'],
            'lignes': [{'ligne_id': row['ligne_id'], 'stock_id': row['stock_id'], 'quantite': 1}],
            'justification': f'Retour partiel successif {index + 1}',
        })
        assert returned.status_code == 201, returned.text
        retour = returned.json()
        assert retour['ventilation_id'] == target['ventilation_id']

        balance = c.get(finance + '/retours/' + retour['id'] + '/solde')
        assert balance.status_code == 200, balance.text
        available = balance.json()['disponible_par_mode']
        payments = [{'mode': mode, 'montant': amount}
                    for mode, amount in available.items() if Decimal(amount) > 0]
        assert sum((Decimal(x['montant']) for x in payments), Decimal(0)) <= Decimal(retour['montant'])
        assert payments, 'Le retour doit produire un montant effectivement remboursable.'
        revision = _session_revision(c, prepared[1]['id'])
        refund_body = {
            'cle': str(uuid4()), 'session_id': prepared[1]['id'], 'revision': revision,
            'retour_id': retour['id'], 'reglements': payments,
            'justification': f'Remboursement selon les allocations retour {index + 1}',
        }
        over_limit = dict(refund_body)
        over_limit['cle'] = str(uuid4())
        over_limit['reglements'] = [dict(x) for x in payments]
        over_limit['reglements'][0]['montant'] = str(Decimal(over_limit['reglements'][0]['montant']) + 1)
        rejected = c.post(finance + '/remboursements', json=over_limit)
        assert rejected.status_code in (409, 422), rejected.text
        assert _count(c, RemboursementModel) == index
        refund_response = c.post(finance + '/remboursements', json=refund_body)
        assert refund_response.status_code == 201, refund_response.text
        refund = refund_response.json()
        replay = c.post(finance + '/remboursements', json=refund_body)
        assert replay.status_code == 201 and replay.json() == refund

        authorized = c.post(finance + '/remboursements/' + refund['id'] + '/autoriser', json={
            'cle': str(uuid4()), 'revision': refund['revision'],
            'justification': 'Autorisation ciblÃ©e Ã©tape 3.4',
        })
        assert authorized.status_code == 200, authorized.text
        refund = authorized.json()
        executed = c.post(finance + '/remboursements/' + refund['id'] + '/executer', json={
            'cle': str(uuid4()), 'revision': refund['revision'],
            'justification': 'ExÃ©cution ciblÃ©e Ã©tape 3.4',
            'preuves': [{'reference': None if p['mode'] == 'ESPECES' else f'REF-{index}-{i}',
                         'preuve': None if p['mode'] == 'ESPECES' else 'Terminal confirmÃ©'}
                        for i, p in enumerate(payments)],
        })
        assert executed.status_code == 200, executed.text
        points = c.get(root(a) + '/fidelite/' + loyalty['id']).json()['points']
        assert 3 <= points <= 6, f'Une vente ne peut pas compenser les points de lâ€™autre: {points}'

    assert c.get(root(a) + '/fidelite/' + loyalty['id']).json()['points'] == 3
    assert _count(c, CompensationRetourModel) == 3
    assert _count(c, RemboursementModel, RemboursementModel.etat == 'EXECUTE') == 3
    gen = db(c)
    session = next(gen)
    try:
        journal = session.scalars(select(JournalFideliteModel).where(
            JournalFideliteModel.compte_id == UUID(loyalty['id']),
            JournalFideliteModel.type.in_(('ACQUISITION', 'REVOCATION')))).all()
        assert len(journal) == 4
        assert sum(x.delta_points for x in journal) == 3
    finally:
        gen.close()
    assert c.get(root(a) + '/recus/' + receipt['id']).status_code == 200
    assert c.get(root(a) + '/recus/' + receipt['id'] + '/pdf').content.startswith(b'%PDF')
    gen = db(c)
    session = next(gen)
    try:
        second = session.scalar(select(VentilationEncaissementModel).where(
            VentilationEncaissementModel.encaissement_id == UUID(receipt['id']),
            VentilationEncaissementModel.vente_id == other_vente_id))
        allocations = session.scalars(select(AllocationReglementModel).where(
            AllocationReglementModel.ventilation_id == second.id)).all()
        assert sum((x.montant_net for x in allocations), Decimal(0)) == Decimal(301)
        assert session.scalar(select(func.count()).select_from(MouvementCaisseModel)) == 1
    finally:
        gen.close()
