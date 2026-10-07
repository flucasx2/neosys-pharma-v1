"""Installation neuve et accès HTTP réels, sans override d'autorisation."""
from contextlib import contextmanager
from datetime import date
from dataclasses import replace
import pytest
from sqlalchemy import select, func, delete
from test_p1_vertical import raw_client
from neosys_pharma.application.bootstrap_service import BootstrapService, InstallationInitiale
from neosys_pharma.application.securite_service import SecuriteService
from neosys_pharma.infrastructure import bootstrap
from neosys_pharma.infrastructure.database import Base, get_db_session
from neosys_pharma.infrastructure.passwords import passwords
from neosys_pharma.infrastructure.organisation_models import OrganisationModel, SiteModel, EmplacementModel
from neosys_pharma.infrastructure.securite_models import UtilisateurModel, AffectationSiteModel, AffectationEmplacementModel, AffectationRoleModel, RoleModel, RolePermissionModel
from neosys_pharma.infrastructure.authentification_models import CredentialModel
from neosys_pharma.domain.organisation.entities import Organisation, Site, Emplacement
from neosys_pharma.domain.organisation.permissions_systeme import PERMISSIONS, role_id, permission_id

PASSWORD='Phrase de test bootstrap 2026!'
DATA=InstallationInitiale(nom_commercial=' NeoPharma ',raison_sociale='NeoPharma SARL',site_code=' lbv ',site_nom='Libreville',emplacement_code=' reserve ',emplacement_nom='Réserve',identifiant=' Alice ',utilisateur_nom='Alice')


@contextmanager
def db(client):
    gen=client.app.dependency_overrides[get_db_session]()
    try:
        yield next(gen)
    finally:
        gen.close()


def counts(session):
    return {table.name:session.scalar(select(func.count()).select_from(table)) for table in Base.metadata.sorted_tables}


def run(session, data=DATA, repo=None, password=PASSWORD):
    return BootstrapService(repo or bootstrap.SqlAlchemyBootstrapRepository(session),passwords).initialiser(data,password,date.today())


def objects(session):
    return [session.scalar(select(model)) for model in (OrganisationModel,SiteModel,EmplacementModel,UtilisateurModel,AffectationSiteModel,AffectationEmplacementModel,AffectationRoleModel,CredentialModel)]


def connect(client,result,site):
    response=client.post('/api/auth/login',headers={'X-NeoSys-Request':'1'},json={'organisation_id':str(result.organisation_id),'identifiant':result.identifiant,'password':PASSWORD})
    assert response.status_code==200,response.text
    client.headers.update({'X-CSRF-Token':response.json()['csrf_token'],'X-Site-ID':str(site)})


def test_bootstrap_hierarchie_hash_et_droits_explicites(raw_client):
    with db(raw_client) as session:
        before=counts(session)
        result=run(session)
        org,site,location,user,assignment,location_link,role_link,credential=objects(session)
        assert org.id_organisation==result.organisation_id==site.organisation_id==user.organisation_id
        assert location.site_id==site.id_site==assignment.site_id==location_link.site_id
        assert assignment.utilisateur_id==user.id_utilisateur
        assert assignment.id_affectation_site==location_link.affectation_site_id==role_link.affectation_site_id
        assert location_link.emplacement_id==location.id_emplacement
        assert role_link.role_id==role_id('GESTION_ORGANISATION')
        assert credential.utilisateur_id==user.id_utilisateur
        assert credential.password_hash.startswith('$argon2id$') and PASSWORD not in credential.password_hash
        assert passwords.verifier(credential.password_hash,PASSWORD)
        assert result.identifiant=='alice' and result.site_code=='LBV' and result.emplacement_code=='RESERVE'
        after=counts(session)
        for name in ('roles','permissions','roles_permissions'):
            assert before[name]==after[name]
        for name in ('organisations','sites','emplacements','utilisateurs','affectations_site','affectations_emplacement','affectations_role','auth_credentials'):
            assert after[name]==1
        service=SecuriteService(bootstrap.SqlAlchemyBootstrapRepository(session).securite)
        for code,_ in PERMISSIONS:
            assert service.autorise(user.id_utilisateur,site.id_site,code,date.today(),location.id_emplacement)
        # Removing the normal role association removes every grant, even for the initial account.
        session.execute(delete(AffectationRoleModel));session.commit()
        assert not service.autorise(user.id_utilisateur,site.id_site,'organisation.gerer',date.today(),location.id_emplacement)


def test_connexion_et_acces_serveur_sans_privilege_implicite(raw_client):
    with db(raw_client) as session:
        result=run(session)
        org,site,location,user,*_=objects(session)
        site_id,location_id=site.id_site,location.id_emplacement
        repo=bootstrap.SqlAlchemyBootstrapRepository(session)
        other=Site(organisation_id=org.id_organisation,code='OW',nom='Owendo')
        denied=Emplacement(site_id=site_id,code='C',nom='Comptoir')
        repo.ajouter(other);repo.ajouter(denied);repo.enregistrer()
        other_id,denied_id=other.id_site,denied.id_emplacement
    c=raw_client
    assert c.get('/api/organisation/organisations').status_code==401
    assert c.post('/api/bootstrap').status_code==404
    connect(c,result,site_id)
    assert c.get('/api/auth/me').status_code==200
    assert c.get('/api/organisation/organisations').json()[0]['id_organisation']==str(result.organisation_id)
    path=f'/api/organisation/emplacements/{location_id}/postes-vente'
    assert c.post(path,json={'code':'P1','nom':'Comptoir'}).status_code==201
    assert c.get(f'/api/organisation/emplacements/{denied_id}/postes-vente').status_code==403
    assert c.get(f'/api/organisation/sites/{other_id}/coffres',headers={'X-Site-ID':str(other_id)}).status_code==403
    with db(c) as session:
        session.execute(delete(RolePermissionModel).where(RolePermissionModel.role_id==role_id('GESTION_ORGANISATION'),RolePermissionModel.permission_id==permission_id('organisation.gerer')))
        session.commit()
    assert c.get(path).status_code==200
    assert c.post(path,json={'code':'P2','nom':'Interdit'}).status_code==403
    with db(c) as session:
        session.execute(delete(AffectationEmplacementModel));session.commit()
    assert c.get(path).status_code==403
    assert c.post('/api/auth/logout').status_code==204
    assert c.get('/api/auth/me').status_code==401


def test_rollback_complet_meme_apres_ecriture_credential(raw_client):
    class Echec(bootstrap.SqlAlchemyBootstrapRepository):
        def definir_password(self,user_id,encoded):
            super().definir_password(user_id,encoded)
            self.db.flush()
            raise RuntimeError('Échec injecté après toutes les écritures')
    with db(raw_client) as session:
        before=counts(session)
        with pytest.raises(RuntimeError):run(session,repo=Echec(session))
        assert counts(session)==before
        assert run(session).identifiant=='alice'


def test_refus_second_bootstrap(raw_client):
    with db(raw_client) as session:
        run(session);before=counts(session)
        with pytest.raises(ValueError,match='déjà'):
            run(session,replace(DATA,identifiant='second'))
        assert counts(session)==before


def test_refus_structure_existante_sans_compte(raw_client):
    with db(raw_client) as session:
        repo=bootstrap.SqlAlchemyBootstrapRepository(session)
        repo.ajouter(Organisation(nom_commercial='Existante',raison_sociale='SARL'));repo.enregistrer()
        before=counts(session)
        with pytest.raises(ValueError,match='déjà'):run(session)
        assert counts(session)==before


@pytest.mark.parametrize('error',['role_absent','role_inactif','permissions_incompletes','password_court','nom_vide'])
def test_catalogue_et_validation_sans_initialisation_partielle(raw_client,error):
    with db(raw_client) as session:
        if error=='role_absent':
            session.execute(delete(RolePermissionModel).where(RolePermissionModel.role_id==role_id('GESTION_ORGANISATION')))
            session.execute(delete(RoleModel).where(RoleModel.id_role==role_id('GESTION_ORGANISATION')))
        elif error=='role_inactif':
            session.get(RoleModel,role_id('GESTION_ORGANISATION')).actif=False
        elif error=='permissions_incompletes':
            session.execute(delete(RolePermissionModel).where(RolePermissionModel.role_id==role_id('GESTION_ORGANISATION')))
        session.commit();before=counts(session)
        with pytest.raises(ValueError):
            run(session,replace(DATA,utilisateur_nom='') if error=='nom_vide' else DATA,password='court' if error=='password_court' else PASSWORD)
        assert counts(session)==before


def cli(monkeypatch,client):
    monkeypatch.setattr(bootstrap,'SessionLocal',lambda:db(client))
    monkeypatch.setattr(bootstrap,'verifier_migrations',lambda session:None)
    entries=iter(['NeoPharma','Neo SARL','lbv','Libreville','r','Réserve','alice','Alice'])
    monkeypatch.setattr('builtins.input',lambda prompt:next(entries))
    monkeypatch.setattr(bootstrap,'getpass',lambda prompt:PASSWORD)


def test_commande_interactive_sortie_et_refus_precoce(raw_client,monkeypatch,capsys):
    cli(monkeypatch,raw_client)
    assert bootstrap.main()==0
    out=capsys.readouterr().out
    with db(raw_client) as session:
        org=session.scalar(select(OrganisationModel))
        assert str(org.id_organisation) in out
    assert 'alice' in out and 'LBV / R' in out
    assert PASSWORD not in out and '$argon2' not in out
    monkeypatch.setattr('builtins.input',lambda prompt:pytest.fail('Le refus doit précéder les saisies'))
    assert bootstrap.main()==1
    assert 'déjà' in capsys.readouterr().err


def test_commande_confirmation_incorrecte(raw_client,monkeypatch,capsys):
    cli(monkeypatch,raw_client)
    answers=iter([PASSWORD,'autre'])
    monkeypatch.setattr(bootstrap,'getpass',lambda prompt:next(answers))
    with db(raw_client) as session:before=counts(session)
    assert bootstrap.main()==1
    assert PASSWORD not in capsys.readouterr().err
    with db(raw_client) as session:assert counts(session)==before


def test_preflight_refuse_schema_non_migre(raw_client):
    with db(raw_client) as session:
        with pytest.raises(ValueError,match='migrée'):
            bootstrap.verifier_migrations(session)


def test_concurrence_postgresql_un_seul_bootstrap(raw_client):
    from concurrent.futures import ThreadPoolExecutor
    from sqlalchemy.orm import sessionmaker
    with db(raw_client) as session:engine=session.get_bind()
    if engine.dialect.name!='postgresql':pytest.skip('Verrou transactionnel PostgreSQL')
    factory=sessionmaker(engine)
    def initialise(index):
        with factory() as session:
            try:
                run(session,replace(DATA,identifiant=f'compte{index}'))
                return 'ok'
            except ValueError as exc:
                assert 'déjà' in str(exc)
                return 'refus'
    with ThreadPoolExecutor(max_workers=2) as pool:
        assert sorted(pool.map(initialise,[1,2]))==['ok','refus']
    with db(raw_client) as session:
        assert counts(session)['utilisateurs']==counts(session)['organisations']==1


def test_commande_sur_schema_migre_depuis_base_vide(tmp_path,monkeypatch,capsys):
    from alembic import command
    from alembic.config import Config
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from neosys_pharma.infrastructure.config import get_settings
    url=f"sqlite+pysqlite:///{tmp_path / 'bootstrap.db'}"
    monkeypatch.setenv('DATABASE_URL',url)
    get_settings.cache_clear()
    engine=create_engine(url)
    try:
        command.upgrade(Config('alembic.ini'),'head')
        factory=sessionmaker(engine)
        monkeypatch.setattr(bootstrap,'SessionLocal',factory)
        entries=iter(['NeoPharma','Neo SARL','lbv','Libreville','r','Réserve','alice','Alice'])
        monkeypatch.setattr('builtins.input',lambda prompt:next(entries))
        monkeypatch.setattr(bootstrap,'getpass',lambda prompt:PASSWORD)
        assert bootstrap.main()==0
        assert 'Organisation (écran de connexion)' in capsys.readouterr().out
        with factory() as session:
            assert counts(session)['auth_credentials']==1
            bootstrap.verifier_migrations(session)
        command.check(Config('alembic.ini'))
        assert bootstrap.main()==1
        assert 'déjà' in capsys.readouterr().err
    finally:
        engine.dispose()
        get_settings.cache_clear()
