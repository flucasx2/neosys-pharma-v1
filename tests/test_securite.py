from datetime import date
from uuid import UUID, uuid4

import pytest
from sqlalchemy.exc import IntegrityError

from test_p1_vertical import client, raw_client, structure
from neosys_pharma.domain.organisation.securite import (
    AffectationSite, AffectationEmplacement, AffectationRole, Role, TypeRole, Utilisateur,
)
from neosys_pharma.infrastructure.database import get_db_session
from neosys_pharma.infrastructure.securite_models import AffectationSiteModel, AffectationEmplacementModel, AffectationRoleModel, RoleModel
from neosys_pharma.infrastructure.securite_repository import SqlAlchemySecuriteRepository
from neosys_pharma.application.securite_service import SecuriteService

BASE = '/api/organisation'


def post(client, path, data):
    response = client.post(BASE + path, json=data)
    assert response.status_code == 201, response.text
    return response.json()


def setup(client):
    org, site = structure(client)
    location = client.get(f'{BASE}/sites/{site}/emplacements').json()[0]['id_emplacement']
    user = post(client, f'/organisations/{org}/utilisateurs', {'identifiant': ' Alice ', 'nom': ' Alice Pharma '})['id_utilisateur']
    assignment = post(client, f'/utilisateurs/{user}/affectations', {'site_id': site, 'date_debut': '2026-01-01'})['id_affectation_site']
    roles = client.get(f'{BASE}/organisations/{org}/roles').json()
    permissions = client.get(f'{BASE}/permissions').json()
    return org, site, location, user, assignment, roles, permissions


def put(client, path, ids):
    return client.put(BASE + path, json={'ids': ids})


def resulting(client, user, site, jour='2026-10-07'):
    response = client.get(f'{BASE}/utilisateurs/{user}/sites/{site}/permissions', params={'jour': jour})
    assert response.status_code == 200, response.text
    return response.json()


@pytest.mark.parametrize('day,active', [('2025-12-31', False), ('2026-01-01', True), ('2026-12-31', True), ('2027-01-01', False)])
def test_periode_inclusive(day, active):
    assignment = AffectationSite(utilisateur_id=uuid4(), site_id=uuid4(), date_debut=date(2026, 1, 1), date_fin=date(2026, 12, 31))
    assert assignment.effective(date.fromisoformat(day)) is active
    assignment.actif = False
    assert not assignment.effective(date.fromisoformat(day))


def test_invariants_domaine():
    org, site = uuid4(), uuid4()
    user = Utilisateur(organisation_id=org, identifiant=' Alice ', nom=' Alice ')
    assert user.identifiant == 'alice' and user.nom == 'Alice'
    with pytest.raises(ValueError):
        Utilisateur(organisation_id=None, identifiant='a', nom='A')
    with pytest.raises(ValueError):
        Role(code='x', nom='X', type_role=TypeRole.PERSONNALISE)
    with pytest.raises(ValueError):
        Role(code='x', nom='X', type_role=TypeRole.SYSTEME, organisation_id=org)
    with pytest.raises(ValueError):
        AffectationSite(utilisateur_id=user.id_utilisateur, site_id=site, date_debut=date(2026, 1, 2), date_fin=date(2026, 1, 1))
    assignment = AffectationSite(utilisateur_id=user.id_utilisateur, site_id=site, date_debut=date(2026, 1, 1))
    link = AffectationEmplacement(affectation_site_id=assignment.id_affectation_site, emplacement_id=uuid4())
    link.valider_site(assignment, site)
    with pytest.raises(ValueError):
        link.valider_site(assignment, uuid4())
    role = Role(code='x', nom='X', type_role=TypeRole.PERSONNALISE, organisation_id=org)
    link_role = AffectationRole(affectation_site_id=assignment.id_affectation_site, role_id=role.id_role)
    link_role.valider_organisation(role, org)
    with pytest.raises(ValueError):
        link_role.valider_organisation(role, uuid4())


def test_parcours_droits_roles_et_perimetres(client):
    org, site, location, user, assignment, roles, permissions = setup(client)
    assert resulting(client, user, site)['permissions_site'] == []
    custom = post(client, f'/organisations/{org}/roles', {'code': ' local ', 'nom': 'Gestion locale', 'permission_ids': [permissions[0]['id_permission']]})
    observer = next(r for r in roles if r['code'] == 'OBSERVATEUR')
    assert custom['code'] == 'LOCAL' and custom['type_role'] == 'PERSONNALISE'
    assert put(client, f'/affectations/{assignment}/roles', [observer['id_role'], custom['id_role'], custom['id_role']]).status_code == 200
    expected = sorted({p['code'] for p in observer['permissions']} | {permissions[0]['code']})
    assert resulting(client, user, site)['permissions_site'] == expected
    assert resulting(client, user, site)['emplacements'] == []
    assert put(client, f'/affectations/{assignment}/emplacements', [location, location]).status_code == 200
    assert resulting(client, user, site)['emplacements'][0]['permissions'] == expected
    assert put(client, f'/roles/{custom["id_role"]}/permissions', [permissions[1]['id_permission']]).status_code == 200
    assert permissions[0]['code'] not in resulting(client, user, site)['permissions_site']
    # Idempotent replacement, revocation, unknown IDs leave old grants untouched.
    for _ in range(2):
        assert put(client, f'/affectations/{assignment}/roles', [custom['id_role']]).status_code == 200
    assert put(client, f'/affectations/{assignment}/roles', [uuid4().hex]).status_code == 404
    assert resulting(client, user, site)['permissions_site'] == [permissions[1]['code']]
    assert put(client, f'/roles/{custom["id_role"]}/permissions', []).status_code == 200
    assert resulting(client, user, site)['permissions_site'] == []
    assert put(client, f'/roles/{observer["id_role"]}/permissions', []).status_code == 422
    assert client.post(f'{BASE}/permissions', json={'code': 'admin'}).status_code == 405
    assert client.get('/static/securite.js').status_code == 200
    assert 'Permissions résultantes' in client.get('/').text


def test_cloisonnement_organisations_et_sites(client):
    org, site, location, user, assignment, roles, permissions = setup(client)
    other_org, other_site = structure(client)
    same_org_site = post(client, f'/organisations/{org}/sites', {'code': 'SECOND', 'nom': 'Second', 'premier_emplacement': {'code': 'R', 'nom': 'Réserve'}})['id_site']
    other_location = client.get(f'{BASE}/sites/{same_org_site}/emplacements').json()[0]['id_emplacement']
    foreign_role = post(client, f'/organisations/{other_org}/roles', {'code': 'LOCAL', 'nom': 'Autre'})
    assert client.post(f'{BASE}/utilisateurs/{user}/affectations', json={'site_id': other_site, 'date_debut': '2026-01-01'}).status_code == 422
    assert put(client, f'/affectations/{assignment}/emplacements', [location]).status_code == 200
    assert put(client, f'/affectations/{assignment}/emplacements', [other_location]).status_code == 422
    assert client.get(f'{BASE}/utilisateurs/{user}/affectations').json()[0]['emplacements'][0]['id_emplacement'] == location
    observer = next(r for r in roles if r['code'] == 'OBSERVATEUR')
    assert put(client, f'/affectations/{assignment}/roles', [observer['id_role']]).status_code == 200
    assert put(client, f'/affectations/{assignment}/roles', [foreign_role['id_role']]).status_code == 422
    assert len(resulting(client, user, site)['permissions_site']) == 3
    assert client.get(f'{BASE}/utilisateurs/{user}/sites/{other_site}/permissions').status_code == 422
    post(client, f'/utilisateurs/{user}/affectations', {'site_id': same_org_site, 'date_debut': '2026-01-01'})
    assert resulting(client, user, same_org_site)['permissions_site'] == []
    assert foreign_role['id_role'] not in {r['id_role'] for r in client.get(f'{BASE}/organisations/{org}/roles').json()}
    assert client.post(f'{BASE}/organisations/{org}/utilisateurs', json={'identifiant':'ALICE', 'nom':'Autre'}).status_code == 409
    assert post(client, f'/organisations/{other_org}/utilisateurs', {'identifiant':'alice', 'nom':'Autre'})
    assert client.post(f'{BASE}/organisations/{org}/roles', json={'code':'BAD', 'nom':'X', 'type_role':'SYSTEME'}).status_code == 422
    assert client.post(f'{BASE}/organisations/{org}/utilisateurs', json={'identifiant':'bad', 'nom':'X', 'is_admin':True}).status_code == 422


def test_periodes_et_desactivation_retirent_les_droits(client):
    org, site, location, user, assignment, roles, _ = setup(client)
    assert put(client, f'/affectations/{assignment}/roles', [roles[0]['id_role']]).status_code == 200
    path = f'{BASE}/affectations/{assignment}'
    assert client.put(path, json={'date_debut':'2026-01-01','date_fin':'2026-12-31','actif':True}).status_code == 200
    assert resulting(client, user, site, '2026-01-01')['permissions_site']
    assert resulting(client, user, site, '2026-12-31')['permissions_site']
    assert resulting(client, user, site, '2027-01-01')['permissions_site'] == []
    assert client.put(path, json={'date_debut':'2026-01-01','actif':False}).status_code == 200
    assert resulting(client, user, site)['permissions_site'] == []
    assert client.put(path, json={'date_debut':'2026-01-01','actif':True}).status_code == 200
    assert client.put(f'{BASE}/utilisateurs/{user}', json={'nom':'Alice','actif':False}).status_code == 200
    assert resulting(client, user, site)['permissions_site'] == []


def test_pas_de_combinaison_des_perimetres_entre_affectations(client):
    org, site, location, user, assignment, roles, permissions = setup(client)
    second = post(client, f'/utilisateurs/{user}/affectations', {'site_id': site, 'date_debut':'2026-02-01'})['id_affectation_site']
    assert put(client, f'/affectations/{assignment}/roles', [roles[0]['id_role']]).status_code == 200
    assert put(client, f'/affectations/{second}/emplacements', [location]).status_code == 200
    # Permission exists on one assignment, location on another: no authorization.
    sessions = client.app.dependency_overrides[get_db_session]()
    session = next(sessions)
    try:
        service = SecuriteService(SqlAlchemySecuriteRepository(session))
        code = roles[0]['permissions'][0]['code']
        assert service.autorise(UUID(user), UUID(site), code, date(2026,10,7))
        assert not service.autorise(UUID(user), UUID(site), code, date(2026,10,7), UUID(location))
    finally:
        sessions.close()
    assert resulting(client, user, site)['emplacements'][0]['permissions'] == []


def test_contraintes_sql_protegent_meme_hors_service(client):
    org, site, location, user, assignment, roles, _ = setup(client)
    other_org, other_site = structure(client)
    other_location = client.get(f'{BASE}/sites/{other_site}/emplacements').json()[0]['id_emplacement']
    foreign_role = post(client, f'/organisations/{other_org}/roles', {'code':'X','nom':'X'})['id_role']
    sessions = client.app.dependency_overrides[get_db_session]()
    session = next(sessions)
    try:
        invalid = [
            AffectationSiteModel(id_affectation_site=uuid4(), utilisateur_id=UUID(user), site_id=UUID(other_site), organisation_id=UUID(org), date_debut=date(2026,1,1), actif=True),
            AffectationEmplacementModel(affectation_site_id=UUID(assignment), emplacement_id=UUID(other_location), site_id=UUID(site)),
            AffectationRoleModel(affectation_site_id=UUID(assignment),role_id=UUID(foreign_role),organisation_id=UUID(org),role_scope='systeme'),
            AffectationRoleModel(affectation_site_id=UUID(assignment),role_id=UUID(foreign_role),organisation_id=UUID(org),role_scope=session.get(RoleModel, UUID(foreign_role)).scope_id),
        ]
        for model in invalid:
            session.add(model)
            with pytest.raises(IntegrityError):
                session.flush()
            session.rollback()
    finally:
        sessions.close()
