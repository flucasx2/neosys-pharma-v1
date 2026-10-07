"""Recette HTTP P1 : aucune interface ni dérogation à require_access.

Les collections opérationnelles d'organisation sont agrégées sur les sites
consultables. Les actions contextuelles exigent le site fourni ; postes et
caisses exigent aussi une AffectationEmplacement. Les routes administratives
exigent une habilitation effective dans le site d'administration, sans donner
un accès opérationnel automatique dans le site administré.
"""
from datetime import timedelta
from uuid import uuid4

import pytest
from sqlalchemy import delete, select, func

from test_p1_vertical import raw_client
from test_authentification import account, db, login, PASSWORD, BASE
from neosys_pharma.domain.organisation.securite import (
    AffectationSite, AffectationRole, AffectationEmplacement, Role, TypeRole, RolePermission,
)
from neosys_pharma.domain.organisation.permissions_systeme import role_id, permission_id
from neosys_pharma.infrastructure.securite_repository import SqlAlchemySecuriteRepository
from neosys_pharma.infrastructure.securite_models import (
    AffectationSiteModel, AffectationRoleModel, AffectationEmplacementModel, UtilisateurModel, RoleModel, RolePermissionModel,
)
from neosys_pharma.infrastructure.organisation_models import (
    OrganisationModel, SiteModel, EmplacementModel, PosteVenteModel, CaisseModel, CoffreModel,
)
from neosys_pharma.infrastructure.authentification_models import CredentialModel, SessionModel
from neosys_pharma.presentation.acces import require_access
from neosys_pharma.presentation.authentification_api import jour_courant

# Independent acceptance cases, not generated from the implementation's matrix.
# method, route, aggregate collection, location-scoped
ROUTES = [
    ('GET', '/organisations', True, False),
    ('GET', '/organisations/{org}/sites', True, False),
    ('POST', '/organisations/{org}/sites', False, False),
    ('GET', '/sites/{site}/emplacements', False, False),
    ('POST', '/sites/{site}/emplacements', False, False),
    ('GET', '/emplacements/{location}/postes-vente', False, True),
    ('POST', '/emplacements/{location}/postes-vente', False, True),
    ('GET', '/emplacements/{location}/caisses', False, True),
    ('POST', '/emplacements/{location}/caisses', False, True),
    ('GET', '/sites/{site}/coffres', False, False),
    ('POST', '/sites/{site}/coffres', False, False),
    ('GET', '/administration/organisations/{org}/sites', False, False),
    ('GET', '/administration/sites/{site}/emplacements', False, False),
    ('POST', '/administration/sites/{site}/emplacements', False, False),
]
MODELS = (OrganisationModel, SiteModel, EmplacementModel, PosteVenteModel, CaisseModel, CoffreModel, UtilisateurModel, RoleModel, RolePermissionModel, AffectationSiteModel, AffectationRoleModel, AffectationEmplacementModel, CredentialModel, SessionModel)


def counts(client):
    gen=db(client);session=next(gen)
    try:return tuple(session.scalar(select(func.count()).select_from(model)) for model in MODELS)
    finally:gen.close()


def send(client, account, row, index=0):
    method, template, _, _ = row
    body={'code':f'HTTP-{index}', 'nom':f'Recette HTTP {index}'}
    if template.endswith('/sites'):
        body['premier_emplacement']={'code':'INITIAL','nom':'Premier emplacement HTTP'}
    return client.request(method, BASE+template.format(**account), json=body if method=='POST' else None)


def set_state(client, a, state):
    gen=db(client);session=next(gen)
    try:
        assignment=session.scalar(select(AffectationSiteModel).where(AffectationSiteModel.utilisateur_id==a['user']))
        aid=assignment.id_affectation_site
        if state=='inactive':assignment.actif=False
        elif state=='expired':assignment.date_debut=jour_courant()-timedelta(days=10);assignment.date_fin=jour_courant()-timedelta(days=1)
        elif state=='future':assignment.date_debut=jour_courant()+timedelta(days=2)
        elif state in ('no_location','split_assignments'):
            session.execute(delete(AffectationEmplacementModel).where(AffectationEmplacementModel.affectation_site_id==aid))
            if state=='split_assignments':
                repo=SqlAlchemySecuriteRepository(session)
                second=AffectationSite(utilisateur_id=a['user'],site_id=a['site'],date_debut=jour_courant()-timedelta(days=1))
                repo.ajouter(second)
                repo.ajouter(AffectationEmplacement(affectation_site_id=second.id_affectation_site,emplacement_id=a['location']))
        elif state in ('consult_only','manage_only'):
            session.execute(delete(AffectationRoleModel).where(AffectationRoleModel.affectation_site_id==aid))
            repo=SqlAlchemySecuriteRepository(session)
            role=Role(code='LIMITED',nom='Droit explicite limité',type_role=TypeRole.PERSONNALISE,organisation_id=a['org'])
            repo.ajouter(role)
            code='organisation.consulter' if state=='consult_only' else 'organisation.gerer'
            repo.ajouter(RolePermission(role_id=role.id_role,permission_id=permission_id(code)))
            repo.ajouter(AffectationRole(affectation_site_id=aid,role_id=role.id_role))
        elif state in ('no_role', 'no_permission', 'no_assignment'):
            session.execute(delete(AffectationRoleModel).where(AffectationRoleModel.affectation_site_id==aid))
            if state=='no_assignment':
                session.execute(delete(AffectationEmplacementModel).where(AffectationEmplacementModel.affectation_site_id==aid))
                session.delete(assignment)
            elif state=='no_permission':
                # Same name as a powerful system role, but only an unrelated permission.
                repo=SqlAlchemySecuriteRepository(session)
                role=Role(code='GESTION_ORGANISATION',nom="Gestion de l'organisation",type_role=TypeRole.PERSONNALISE,organisation_id=a['org'])
                repo.ajouter(role)
                repo.ajouter(RolePermission(role_id=role.id_role,permission_id=permission_id('role.consulter')))
                repo.ajouter(AffectationRole(affectation_site_id=aid,role_id=role.id_role))
        elif state=='wrong_site':
            assignment.actif=False
            repo=SqlAlchemySecuriteRepository(session)
            other=AffectationSite(utilisateur_id=a['user'],site_id=a['other'],date_debut=jour_courant())
            repo.ajouter(other)
            repo.ajouter(AffectationRole(affectation_site_id=other.id_affectation_site,role_id=role_id('GESTION_ORGANISATION')))
            repo.ajouter(AffectationEmplacement(affectation_site_id=other.id_affectation_site,emplacement_id=a['other_location']))
        elif state=='inclusive_period':assignment.date_debut=assignment.date_fin=jour_courant()
        session.commit()
    finally:gen.close()


@pytest.mark.parametrize('state', ['unauthenticated','no_role','no_permission','no_assignment','wrong_site','inactive','expired','future','no_location','split_assignments','consult_only','manage_only','compatible','inclusive_period'])
def test_recette_http_structure_et_equipements(raw_client, account, state):
    c,a=raw_client,account
    assert require_access not in c.app.dependency_overrides
    if state!='unauthenticated':
        assert login(c,a).status_code==200
        set_state(c,a,state)
    initial_counts=counts(c)
    for index,row in enumerate(ROUTES):
        method,template,aggregate,location_scoped=row
        allowed=state in ('compatible','inclusive_period') or (state in ('no_location','split_assignments') and not location_scoped) or (state=='wrong_site' and aggregate) or (state=='consult_only' and method=='GET' and not template.startswith('/administration')) or (state=='manage_only' and method=='POST')
        expected=(201 if method=='POST' else 200) if allowed else (401 if state=='unauthenticated' else 403)
        before=counts(c)
        response=send(c,a,row,index)
        assert response.status_code==expected,(state,method,template,response.text)
        if expected in (401,403):assert counts(c)==before,('Une requête refusée a écrit en base',state,template)
        if state=='wrong_site' and method=='GET' and template=='/organisations/{org}/sites':
            assert [s['id_site'] for s in response.json()]==[str(a['other'])]
    if state in ('unauthenticated','no_role','no_permission','no_assignment','inactive','expired','future'):
        assert counts(c)==initial_counts


def test_emplacement_autre_site_et_en_tete_forge_refuses(raw_client, account):
    c,a=raw_client,account;assert login(c,a).status_code==200
    initial=counts(c)
    for index,row in enumerate(ROUTES):
        if row[2]:continue  # Organization collections have no location scope.
        response=c.request(row[0], BASE+row[1].format(**a),
            headers={'X-Emplacement-ID':str(a['other_location'])},
            json={'code':f'FORGE-{index}','nom':'Interdit','premier_emplacement':{'code':'R','nom':'R'}} if row[0]=='POST' and row[1].endswith('/sites') else {'code':f'FORGE-{index}','nom':'Interdit'} if row[0]=='POST' else None)
        assert response.status_code==403,(row,response.text)
    for index,row in enumerate(r for r in ROUTES if r[3]):
        forged={**a,'location':a['other_location']}
        assert send(c,forged,row,index).status_code==403
    assert counts(c)==initial


def mutations(a, assignment):
    today=jour_courant().isoformat()
    cases=[(method,BASE+path.format(**a), {'code':f'CSRF-{index}','nom':'Refus CSRF','premier_emplacement':{'code':'R','nom':'R'}} if path.endswith('/sites') else {'code':f'CSRF-{index}','nom':'Refus CSRF'}) for index,(method,path,_,_) in enumerate(ROUTES) if method=='POST']
    for prefix in ('', '/administration'):
        cases.extend([
            ('POST',f'{BASE}{prefix}/utilisateurs/{a["user"]}/affectations',{'site_id':str(a['site']),'date_debut':today}),
            ('PUT',f'{BASE}{prefix}/affectations/{assignment}',{'date_debut':today,'actif':True}),
            ('PUT',f'{BASE}{prefix}/affectations/{assignment}/roles',{'ids':[str(role_id('GESTION_ORGANISATION'))]}),
            ('PUT',f'{BASE}{prefix}/affectations/{assignment}/emplacements',{'ids':[str(a['location'])]}),
        ])
    cases.extend([
        ('POST',f'{BASE}/organisations/{a["org"]}/utilisateurs',{'identifiant':'csrf','nom':'CSRF'}),
        ('PUT',f'{BASE}/utilisateurs/{a["user"]}',{'nom':'Alice','actif':True}),
        ('POST',f'{BASE}/organisations/{a["org"]}/roles',{'code':'CSRF','nom':'CSRF','permission_ids':[]}),
        ('PUT',f'{BASE}/roles/{role_id("GESTION_ORGANISATION")}/permissions',{'ids':[]}),
        ('PUT',f'/api/auth/utilisateurs/{a["user"]}/password',{'password':PASSWORD+' nouveau'}),
        ('POST','/api/auth/logout',None),
    ])
    return cases


@pytest.mark.parametrize('csrf', ['missing','invalid'])
def test_toutes_mutations_directes_exigent_csrf(raw_client, account, csrf):
    c,a=raw_client,account;assert login(c,a).status_code==200
    gen=db(c);session=next(gen)
    try:aid=session.scalar(select(AffectationSiteModel.id_affectation_site).where(AffectationSiteModel.utilisateur_id==a['user']))
    finally:gen.close()
    initial=counts(c)
    c.headers.pop('X-CSRF-Token')
    if csrf=='invalid':c.headers['X-CSRF-Token']='jeton-invalide'
    for method,path,body in mutations(a,aid):
        response=c.request(method,path,json=body)
        assert response.status_code==403,(csrf,method,path,response.text)
    assert counts(c)==initial
    assert c.get('/api/auth/me').status_code==200  # Refused logout/password reset had no effect.


@pytest.mark.parametrize('revoke', ['logout','password'])
def test_sessions_revoquees_refusent_toutes_routes_http(raw_client, account, revoke):
    c,a=raw_client,account;assert login(c,a).status_code==200
    token=c.cookies.get('neosys_session')
    password=PASSWORD
    if revoke=='logout':assert c.post('/api/auth/logout').status_code==204
    else:
        password=PASSWORD+' changé'
        assert c.put(f'/api/auth/utilisateurs/{a["user"]}/password',json={'password':password}).status_code==204
    # Replay the revoked cookie through direct HTTP, not a UI logout state.
    c.cookies.set('neosys_session',token)
    for index,row in enumerate(ROUTES):
        response=send(c,a,row,index)
        assert response.status_code==401,(revoke,row,response.text)
        assert response.headers['www-authenticate']=='Session'
    assert c.get('/api/auth/me').status_code==401
    c.cookies.clear()
    assert login(c,a,password=password).status_code==200
    assert c.get(f'{BASE}/emplacements/{a["location"]}/caisses').status_code==200
