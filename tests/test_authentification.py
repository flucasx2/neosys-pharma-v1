from datetime import date, datetime, timedelta, timezone
from uuid import UUID, uuid4
import pytest
from sqlalchemy import select
from test_p1_vertical import raw_client
from neosys_pharma.infrastructure.database import get_db_session
from neosys_pharma.infrastructure.organisation_repository import SqlAlchemyOrganisationRepository
from neosys_pharma.infrastructure.securite_repository import SqlAlchemySecuriteRepository
from neosys_pharma.infrastructure.authentification_repository import SqlAlchemyAuthRepository
from neosys_pharma.infrastructure.authentification_models import CredentialModel, SessionModel
from neosys_pharma.infrastructure.securite_models import UtilisateurModel, AffectationSiteModel, RoleModel
from neosys_pharma.infrastructure.provisionnement import provisionner
from neosys_pharma.domain.organisation.entities import Organisation, Site, Emplacement
from neosys_pharma.domain.organisation.securite import Utilisateur, Role, TypeRole, RolePermission, AffectationSite, AffectationRole, AffectationEmplacement
from neosys_pharma.domain.organisation.permissions_systeme import role_id, permission_id
from neosys_pharma.infrastructure.passwords import passwords
from neosys_pharma.application.authentification_service import AuthentificationService, empreinte
from neosys_pharma.domain.organisation.authentification import SessionAuthentifiee, valider_mot_de_passe

PASSWORD='Phrase de test isolée 2026!'
BASE='/api/organisation'


def db(client):
    return client.app.dependency_overrides[get_db_session]()


@pytest.fixture
def account(raw_client):
    gen=db(raw_client);session=next(gen)
    try:
        org=Organisation(nom_commercial='Pharma test',raison_sociale='Pharma SARL')
        site=Site(organisation_id=org.id_organisation,code='LBV',nom='Libreville')
        other=Site(organisation_id=org.id_organisation,code='OW',nom='Owendo')
        allowed=Emplacement(site_id=site.id_site,code='R',nom='Réserve')
        denied=Emplacement(site_id=site.id_site,code='C',nom='Comptoir non autorisé')
        other_location=Emplacement(site_id=other.id_site,code='R',nom='Réserve Owendo')
        repo=SqlAlchemyOrganisationRepository(session)
        for item in (org,site,other,allowed,denied,other_location):repo.ajouter(item)
        user=Utilisateur(organisation_id=org.id_organisation,identifiant='alice',nom='Alice')
        provisionner(session,user,[site.id_site],[allowed.id_emplacement],[role_id('GESTION_ORGANISATION')],PASSWORD)
        return {'org':org.id_organisation,'site':site.id_site,'other':other.id_site,'location':allowed.id_emplacement,'denied':denied.id_emplacement,'other_location':other_location.id_emplacement,'user':user.id_utilisateur}
    finally:gen.close()


def login(client,a,password=PASSWORD,identifiant='alice'):
    response=client.post('/api/auth/login',headers={'X-NeoSys-Request':'1'},json={'organisation_id':str(a['org']),'identifiant':identifiant,'password':password})
    if response.status_code==200:
        client.headers['X-CSRF-Token']=response.json()['csrf_token']
        client.headers['X-Site-ID']=str(a['site'])
    return response


def test_hashes_et_session_domaine():
    first=passwords.hacher(PASSWORD);second=passwords.hacher(PASSWORD)
    assert first.startswith('$argon2id$') and first!=second and PASSWORD not in first
    assert passwords.verifier(first,PASSWORD)
    assert not passwords.verifier(first,'incorrect')
    assert not passwords.verifier(None,PASSWORD)
    for value in ('court','a'*129):
        with pytest.raises(ValueError):valider_mot_de_passe(value)
    now=datetime.now(timezone.utc)
    session=SessionAuthentifiee(utilisateur_id=uuid4(),empreinte='x',expiration=now)
    assert not session.valide(now)
    assert session.valide(now-timedelta(seconds=1))


def test_connexion_erreurs_cookies_identite_et_deconnexion(raw_client,account):
    c,a=raw_client,account
    assert c.get(BASE+'/organisations').status_code==401
    assert login(c,a,password='incorrect').status_code==401
    assert login(c,a,identifiant='absent').status_code==401
    response=login(c,a)
    assert response.status_code==200,response.text
    cookie=response.headers.get_list('set-cookie')[0]
    assert 'HttpOnly' in cookie and 'SameSite=strict' in cookie
    assert PASSWORD not in response.text and 'password_hash' not in response.text
    assert c.get('/api/auth/me').json()['utilisateur']['id_utilisateur']==str(a['user'])
    assert c.get(BASE+'/organisations').status_code==200
    gen=db(c);session=next(gen)
    try:
        credential=session.get(CredentialModel,a['user'])
        assert PASSWORD not in credential.password_hash
        token=c.cookies.get('neosys_session')
        row=session.get(SessionModel,empreinte(token))
        assert row and token not in row.empreinte
    finally:gen.close()
    assert c.post('/api/auth/logout').status_code==204
    assert c.get('/api/auth/me').status_code==401
    c.cookies.set('neosys_session',token)
    assert c.get(BASE+'/organisations').status_code==401


def test_sites_emplacements_filtrage_et_protection_serveur(raw_client,account):
    c,a=raw_client,account;assert login(c,a).status_code==200
    org=str(a['org']);site=str(a['site']);loc=str(a['location'])
    sites=c.get(f'{BASE}/organisations/{org}/sites')
    assert sites.status_code==200,sites.text
    assert [s['id_site'] for s in sites.json()]==[site]
    locations=c.get(f'{BASE}/sites/{site}/emplacements').json()
    assert [e['id_emplacement'] for e in locations]==[loc]
    assert c.get(f'{BASE}/emplacements/{loc}/caisses').status_code==200
    assert c.post(f'{BASE}/emplacements/{loc}/caisses',json={'code':'C','nom':'Caisse'}).status_code==201
    for item in (a['denied'],a['other_location']):
        assert c.get(f'{BASE}/emplacements/{item}/caisses').status_code==403
        assert c.post(f'{BASE}/emplacements/{item}/caisses',json={'code':'X','nom':'X'}).status_code==403
    c.headers['X-Site-ID']=str(a['other'])
    assert c.get(f'{BASE}/sites/{a["other"]}/coffres').status_code==403
    assert c.get(f'{BASE}/sites/{site}/coffres').status_code==403
    c.headers['X-Site-ID']=site
    c.headers['X-Emplacement-ID']=str(a['denied'])
    assert c.post(f'{BASE}/sites/{site}/coffres',json={'code':'X','nom':'X'}).status_code==403
    del c.headers['X-Emplacement-ID']
    assert c.get(f'{BASE}/organisations/{uuid4()}/utilisateurs').status_code==403
    assert c.post(BASE+'/organisations',json={}).status_code==403


@pytest.mark.parametrize('state',['sans_affectation','inactive','expiree','future','role_inactif','user_inactif','org_inactive'])
def test_etats_revoquent_les_droits_immediatement(raw_client,account,state):
    c,a=raw_client,account;assert login(c,a).status_code==200
    gen=db(c);session=next(gen)
    try:
        assignment=session.scalar(select(AffectationSiteModel).where(AffectationSiteModel.utilisateur_id==a['user']))
        if state in ('sans_affectation','inactive'):assignment.actif=False
        elif state=='expiree':assignment.date_debut=date(2020,1,1);assignment.date_fin=date(2021,1,1)
        elif state=='future':assignment.date_debut=date(2099,1,1)
        elif state=='role_inactif':session.get(RoleModel,role_id('GESTION_ORGANISATION')).actif=False
        elif state=='user_inactif':session.get(UtilisateurModel,a['user']).actif=False
        else:
            from neosys_pharma.infrastructure.organisation_models import OrganisationModel
            session.get(OrganisationModel,a['org']).actif=False
        session.commit()
    finally:gen.close()
    assert c.get(f'{BASE}/sites/{a["site"]}/coffres').status_code==(401 if state in ('user_inactif','org_inactive') else 403)
    if state=='user_inactif':assert login(c,a).status_code==401
    elif state not in ('org_inactive',):assert c.get('/api/auth/me').json()['contextes']==[]


def test_role_personnalise_plusieurs_roles_sans_role_magique(raw_client,account):
    c,a=raw_client,account
    gen=db(c);session=next(gen)
    try:
        repo=SqlAlchemySecuriteRepository(session)
        user=Utilisateur(organisation_id=a['org'],identifiant='lecture',nom='Lecture')
        role=Role(code='GESTION_ORGANISATION',nom='Un nom ne donne aucun droit',type_role=TypeRole.PERSONNALISE,organisation_id=a['org'])
        repo.ajouter(role)
        repo.ajouter(RolePermission(role_id=role.id_role,permission_id=permission_id('organisation.consulter')))
        provisionner(session,user,[a['site']],[a['location']],[role.id_role,role_id('OBSERVATEUR')],PASSWORD)
    finally:gen.close()
    assert login(c,a,identifiant='lecture').status_code==200
    me=c.get('/api/auth/me').json()
    assert set(me['contextes'][0]['permissions_site'])=={'organisation.consulter','utilisateur.consulter','role.consulter'}
    assert c.get(f'{BASE}/emplacements/{a["location"]}/caisses').status_code==200
    assert c.post(f'{BASE}/emplacements/{a["location"]}/caisses',json={'code':'X','nom':'X'}).status_code==403
    assert c.post(f'{BASE}/organisations/{a["org"]}/utilisateurs',json={'identifiant':'hacker','nom':'Hacker'}).status_code==403


def test_csrf_origine_expiration_et_reinitialisation_password(raw_client,account):
    c,a=raw_client,account;assert login(c,a).status_code==200
    old_token=c.cookies.get('neosys_session')
    csrf=c.headers.pop('X-CSRF-Token')
    path=f'{BASE}/sites/{a["site"]}/coffres'
    assert c.post(path,json={'code':'F','nom':'F'}).status_code==403
    c.headers['X-CSRF-Token']=csrf
    assert c.post(path,json={'code':'F','nom':'F'},headers={'Origin':'https://evil.test'}).status_code==403
    assert c.put(f'/api/auth/utilisateurs/{a["user"]}/password',json={'password':'court'}).status_code==422
    assert 'court' not in c.put(f'/api/auth/utilisateurs/{a["user"]}/password',json={'password':'court'}).text
    assert c.put(f'/api/auth/utilisateurs/{a["user"]}/password',json={'password':PASSWORD+' nouveau'}).status_code==204
    assert c.get('/api/auth/me').status_code==401
    assert login(c,a,password=PASSWORD+' nouveau').status_code==200
    new_token=c.cookies.get('neosys_session');assert old_token!=new_token
    gen=db(c);session=next(gen)
    try:
        row=session.get(SessionModel,empreinte(new_token));row.creation=datetime(2020,1,1,tzinfo=timezone.utc);row.expiration=datetime(2020,1,2,tzinfo=timezone.utc);session.commit()
    finally:gen.close()
    assert c.get('/api/auth/me').status_code==401


def test_login_limite_tentatives_et_pas_de_csrf_login(raw_client,account):
    c,a=raw_client,account
    assert c.post('/api/auth/login',json={'organisation_id':str(a['org']),'identifiant':'alice','password':PASSWORD}).status_code==403
    for _ in range(10):assert login(c,a,password='incorrect').status_code==401
    response=login(c,a)
    assert response.status_code==429 and response.headers['retry-after']=='300'


def test_toutes_routes_metier_exigent_authentification(raw_client,account):
    c,a=raw_client,account
    paths=c.get('/openapi.json').json()['paths']
    replacements={'organisation_id':a['org'],'site_id':a['site'],'emplacement_id':a['location'],'utilisateur_id':a['user'],'affectation_id':uuid4(),'role_id':uuid4()}
    for template,methods in paths.items():
        if not template.startswith(BASE):continue
        path=template
        for key,value in replacements.items():path=path.replace('{'+key+'}',str(value))
        for method in methods:
            response=c.request(method.upper(),path,json={} if method!='get' else None)
            assert response.status_code==401,(method,path,response.text)


def test_identite_sans_affectation_et_rotation_session(raw_client,account):
    c,a=raw_client,account
    gen=db(c);session=next(gen)
    try:
        user=Utilisateur(organisation_id=a['org'],identifiant='sans',nom='Sans affectation')
        repo=SqlAlchemySecuriteRepository(session);repo.ajouter(user)
        AuthentificationService(SqlAlchemyAuthRepository(session),passwords).definir_password(user.id_utilisateur,PASSWORD)
    finally:gen.close()
    assert login(c,a,identifiant='sans').status_code==200
    assert c.get('/api/auth/me').json()['contextes']==[]
    assert c.get(BASE+'/organisations').status_code==403
    old=c.cookies.get('neosys_session')
    assert login(c,a,identifiant='sans').status_code==200
    assert c.cookies.get('neosys_session')!=old
    gen=db(c);session=next(gen)
    try:assert session.get(SessionModel,empreinte(old)) is None
    finally:gen.close()


def test_cookie_secure_en_https(raw_client,account,monkeypatch):
    from neosys_pharma.infrastructure.config import get_settings
    monkeypatch.setenv('AUTH_COOKIE_SECURE','true');get_settings.cache_clear()
    raw_client.base_url='https://testserver'
    response=login(raw_client,account)
    assert response.status_code==200
    assert all('Secure' in cookie for cookie in response.headers.get_list('set-cookie'))
    assert raw_client.get('/api/auth/me').status_code==200


def test_structure_administrable_sans_acces_operationnel_et_affectation_explicite(raw_client,account):
    c,a=raw_client,account;assert login(c,a).status_code==200
    admin=BASE+'/administration'
    site=c.post(f'{BASE}/organisations/{a["org"]}/sites',json={
        'code':'LBV02','nom':'Site Test 02','premier_emplacement':{'code':'R02','nom':'Réserve 02'}}).json()['id_site']
    assert site not in [s['id_site'] for s in c.get(f'{BASE}/organisations/{a["org"]}/sites').json()]
    assert site in [s['id_site'] for s in c.get(f'{admin}/organisations/{a["org"]}/sites').json()]
    locations=c.get(f'{admin}/sites/{site}/emplacements').json();loc=locations[0]['id_emplacement']
    assert c.get(f'{BASE}/sites/{site}/coffres',headers={'X-Site-ID':site}).status_code==403
    assert site not in [s['site_id'] for s in c.get('/api/auth/me').json()['contextes']]
    assignment=c.post(f'{admin}/utilisateurs/{a["user"]}/affectations',json={'site_id':site,'date_debut':date.today().isoformat()})
    assert assignment.status_code==201,assignment.text
    aid=assignment.json()['id_affectation_site']
    assert site not in [s['site_id'] for s in c.get('/api/auth/me').json()['contextes']]
    assert c.put(f'{admin}/affectations/{aid}/roles',json={'ids':[str(role_id('GESTION_ORGANISATION'))]}).status_code==200
    contexts=c.get('/api/auth/me').json()['contextes'];ctx=next(s for s in contexts if s['site_id']==site)
    assert ctx['emplacements']==[]
    assert c.get(f'{BASE}/emplacements/{loc}/caisses',headers={'X-Site-ID':site}).status_code==403
    assert c.put(f'{admin}/affectations/{aid}/emplacements',json={'ids':[loc]}).status_code==200
    assert c.get(f'{BASE}/emplacements/{loc}/caisses',headers={'X-Site-ID':site}).status_code==200
    new=c.post(f'{admin}/sites/{site}/emplacements',json={'code':'C02','nom':'Comptoir 02'})
    assert new.status_code==201,new.text
    newloc=new.json()['id_emplacement']
    assert newloc in [e['id_emplacement'] for e in c.get(f'{admin}/sites/{site}/emplacements').json()]
    assert newloc not in [e['id_emplacement'] for e in c.get(f'{BASE}/sites/{site}/emplacements',headers={'X-Site-ID':site}).json()]
    assert c.get(f'{BASE}/emplacements/{newloc}/caisses',headers={'X-Site-ID':site}).status_code==403
    assert c.put(f'{admin}/affectations/{aid}/emplacements',json={'ids':[loc,newloc]}).status_code==200
    assert c.get(f'{BASE}/emplacements/{newloc}/caisses',headers={'X-Site-ID':site}).status_code==200


def test_administration_exige_permissions_et_organisation_sans_bypass(raw_client,account):
    c,a=raw_client,account;assert login(c,a).status_code==200
    admin=BASE+'/administration'
    assert c.get(f'{admin}/organisations/{uuid4()}/sites').status_code==403
    assert c.get(f'{admin}/sites/{uuid4()}/emplacements').status_code==403
    gen=db(c);session=next(gen)
    try:
        foreign_org=Organisation(nom_commercial='Autre organisation',raison_sociale='Autre SARL')
        foreign_site=Site(organisation_id=foreign_org.id_organisation,code='FOREIGN',nom='Hors organisation')
        repo=SqlAlchemyOrganisationRepository(session)
        repo.ajouter(foreign_org);repo.ajouter(foreign_site);session.commit()
    finally:gen.close()
    assert c.get(f'{admin}/sites/{foreign_site.id_site}/emplacements').status_code==403
    assert c.post(f'{admin}/utilisateurs/{a["user"]}/affectations',json={'site_id':str(foreign_site.id_site),'date_debut':date.today().isoformat()}).status_code==403
    c.headers['X-Emplacement-ID']=str(a['denied'])
    assert c.get(f'{admin}/sites/{a["other"]}/emplacements').status_code==403
    del c.headers['X-Emplacement-ID']
    # An explicit location context must not bypass its own permission check.
    csrf=c.headers.pop('X-CSRF-Token')
    assert c.post(f'{admin}/utilisateurs/{a["user"]}/affectations',json={'site_id':str(a['other']),'date_debut':date.today().isoformat()}).status_code==403
    c.headers['X-CSRF-Token']=csrf
    gen=db(c);session=next(gen)
    try:
        repo=SqlAlchemySecuriteRepository(session)
        reader=Utilisateur(organisation_id=a['org'],identifiant='observer',nom='Observateur')
        provisionner(session,reader,[a['site']],[a['location']],[role_id('OBSERVATEUR')],PASSWORD)
    finally:gen.close()
    assert login(c,a,identifiant='observer').status_code==200
    assert c.get(f'{admin}/organisations/{a["org"]}/sites').status_code==403
    assert c.get(f'{admin}/sites/{a["other"]}/emplacements').status_code==403
    assert c.post(f'{admin}/utilisateurs/{reader.id_utilisateur}/affectations',json={'site_id':str(a['other']),'date_debut':date.today().isoformat()}).status_code==403
    # Neither a familiar role name nor affectation.gerer alone gives structure-wide administration.
    gen=db(c);session=next(gen)
    try:
        repo=SqlAlchemySecuriteRepository(session)
        limited=Role(code='LIMITED',nom='Gestion limitée',type_role=TypeRole.PERSONNALISE,organisation_id=a['org'])
        repo.ajouter(limited);repo.ajouter(RolePermission(role_id=limited.id_role,permission_id=permission_id('affectation.gerer')))
        assignment=repo.affectations(reader.id_utilisateur)[0]
        repo.ajouter(AffectationRole(affectation_site_id=assignment.id_affectation_site,role_id=limited.id_role));session.commit()
    finally:gen.close()
    assert c.post(f'{admin}/utilisateurs/{reader.id_utilisateur}/affectations',json={'site_id':str(a['other']),'date_debut':date.today().isoformat()}).status_code==403
