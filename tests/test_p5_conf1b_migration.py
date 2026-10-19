"""Migration additive ; le contrôle PostgreSQL exige une base vide marquée."""
from datetime import date
from uuid import uuid4, UUID
from concurrent.futures import ThreadPoolExecutor
from threading import Event, Barrier
import os
import time
import pytest
import sqlalchemy as sa
from sqlalchemy.orm import Session
from alembic import command
from alembic.config import Config
from neosys_pharma.infrastructure.config import get_settings
from neosys_pharma.infrastructure.organisation_models import OrganisationModel
from neosys_pharma.infrastructure.securite_models import UtilisateurModel
from neosys_pharma.infrastructure.client_models import OrganismePriseEnChargeModel
from neosys_pharma.infrastructure.tiers_payants_models import ConfigurationConventionModel


def cible_postgresql(url, confirmation, marker):
    parsed=sa.engine.make_url(url)
    if parsed.get_backend_name()!='postgresql' or not parsed.database or not parsed.database.startswith('neosys_p5conf1b_'):
        raise RuntimeError('Seule une base PostgreSQL jetable neosys_p5conf1b_* est admise.')
    if confirmation!=parsed.database or not marker or not marker.startswith('NEOSYS_P5CONF1B_DISPOSABLE_'):
        raise RuntimeError('Nom et marqueur jetables explicites requis.')
    return parsed


def preparer_migration(url, monkeypatch):
    monkeypatch.setenv('DATABASE_URL',url);get_settings.cache_clear()
    engine=sa.create_engine(url)
    cfg=Config('alembic.ini')
    command.upgrade(cfg,'20261018_01')
    org,user,payer=uuid4(),uuid4(),uuid4()
    with Session(engine) as s:
        s.add(OrganisationModel(id_organisation=org,nom_commercial='QA',raison_sociale='QA',actif=True));s.flush()
        s.add(UtilisateurModel(id_utilisateur=user,organisation_id=org,identifiant='qa',nom='QA',actif=True))
        s.add(OrganismePriseEnChargeModel(id=payer,organisation_id=org,code='P4B-QA',nom='Historique fictif',revision=1,actif=True));s.commit()
    command.upgrade(cfg,'20261019_01');command.upgrade(cfg,'head');command.check(cfg)
    with Session(engine) as s:
        assert s.get(OrganismePriseEnChargeModel,payer).nom=='Historique fictif'
    inspector=sa.inspect(engine)
    fks=inspector.get_foreign_keys('tiers_payant_verifications_convention')
    assert {'fk_tp_verif_configuration_scope','fk_tp_verif_adhesion_org','fk_tp_verif_vente_site_org','fk_tp_verif_lien_beneficiaire'} <= {x['name'] for x in fks}
    # Le downgrade est possible avant saisie, sans supprimer le référentiel historique.
    command.downgrade(cfg,'20261018_01');command.upgrade(cfg,'head')
    return engine,cfg,org,user,payer


def test_migration_additive_sqlite_et_garde_fous_downgrade(tmp_path,monkeypatch):
    engine,cfg,org,user,payer=preparer_migration('sqlite+pysqlite:///'+str(tmp_path/'conf.db'),monkeypatch)
    try:
        from test_p5_conf_conventions import body
        from neosys_pharma.application.stock_service import StockService
        from neosys_pharma.application.tiers_payants_service import TiersPayantsService
        from neosys_pharma.application.configuration_convention_service import ConfigurationConventionService
        p=body({'id':payer,'revision':1});p['date_debut']=date.fromisoformat(p['date_debut']);p['date_fin']=date.fromisoformat(p['date_fin'])
        with Session(engine) as s:
            stock=StockService(s,org,user,lambda *a:None,date.today())
            result=stock.operation(uuid4(),'QA',{},lambda:ConfigurationConventionService(TiersPayantsService(stock)).creer(p))
            ident=UUID(result['configuration']['id'])
        for sql in ("UPDATE tiers_payant_configurations_convention SET schema_version=2","DELETE FROM tiers_payant_configurations_convention"):
            with engine.connect() as conn:
                with pytest.raises(sa.exc.DBAPIError):conn.execute(sa.text(sql));conn.commit()
                conn.rollback()
        with pytest.raises(RuntimeError,match='conserver'):command.downgrade(cfg,'20261018_01')
        with Session(engine) as s:assert s.get(ConfigurationConventionModel,ident) is not None
    finally:engine.dispose();get_settings.cache_clear()


def test_garde_fou_refuse_bases_conservees_et_marqueur_manquant():
    for name in ('neosys_pharma_v1','neosys_p46_recette_20261012','neosys_p5conf1a_recette_temp','neosys_p5b_validation_temp'):
        with pytest.raises(RuntimeError):cible_postgresql('postgresql+psycopg://localhost/'+name,name,'NEOSYS_P5CONF1B_DISPOSABLE_QA')
    with pytest.raises(RuntimeError):cible_postgresql('sqlite:///neosys_p5conf1b_qa','neosys_p5conf1b_qa','NEOSYS_P5CONF1B_DISPOSABLE_QA')
    with pytest.raises(RuntimeError):cible_postgresql('postgresql+psycopg://localhost/neosys_p5conf1b_qa','neosys_p5conf1b_qa','')


def test_postgresql_migration_contraintes_et_contention_reelle(monkeypatch):
    url=os.getenv('TEST_P5CONF1B_DATABASE_URL')
    if not url:pytest.skip('PostgreSQL jetable P5-CONF.1b non fourni ; pas de substitution SQLite.')
    marker=os.getenv('P5CONF1B_MARKER');parsed=cible_postgresql(url,os.getenv('P5CONF1B_CONFIRM_DATABASE'),marker)
    probe=sa.create_engine(url)
    try:
        with probe.connect() as c:
            assert c.scalar(sa.text('select current_database()'))==parsed.database
            assert c.scalar(sa.text("select shobj_description(oid,'pg_database') from pg_database where datname=current_database()"))==marker
            assert not sa.inspect(c).get_table_names(), 'Base préexistante non vide : aucune migration exécutée.'
            print('PostgreSQL natif :',c.scalar(sa.text('select version()')),parsed.database)
    finally:probe.dispose()
    engine,cfg,org,user,payer=preparer_migration(url,monkeypatch)
    from neosys_pharma.application.stock_service import StockService
    from neosys_pharma.application.tiers_payants_service import TiersPayantsService
    from neosys_pharma.application.configuration_convention_service import ConfigurationConventionService
    from neosys_pharma.domain.stock import ConflitStock
    from test_p5_conf_conventions import body
    data=body({'id':payer,'revision':1});data['date_debut']=date.fromisoformat(data['date_debut']);data['date_fin']=date.fromisoformat(data['date_fin'])
    held,release,second_ready=Event(),Event(),Event();pids={}
    def worker(first):
        with Session(engine) as s:
            s.execute(sa.text("SET LOCAL lock_timeout='8s'"));s.execute(sa.text("SET LOCAL statement_timeout='10s'"))
            pids[first]=s.scalar(sa.text('select pg_backend_pid()'))
            stock=StockService(s,org,user,lambda *a:None,date.today())
            def action():
                if first:
                    held.set()
                    if not release.wait(8):raise TimeoutError('Fin de contention non signalée.')
                return ConfigurationConventionService(TiersPayantsService(stock)).creer(data)
            if not first:second_ready.set()
            try:return stock.operation(uuid4(),'QA-CONVENTION',{},action)
            except ConflitStock:return 'CONFLIT'
    pool=ThreadPoolExecutor(max_workers=2)
    try:
        one=pool.submit(worker,True);assert held.wait(5)
        two=pool.submit(worker,False);assert second_ready.wait(5)
        assert pids[True]!=pids[False]
        deadline=time.monotonic()+5;blocked=False
        while time.monotonic()<deadline:
            with engine.connect() as c:
                blocked=pids[True] in c.scalar(sa.text('select pg_blocking_pids(:pid)'),{'pid':pids[False]})
            if blocked:break
            time.sleep(.05)
        assert blocked,'Aucune contention PostgreSQL démontrée.'
        release.set();assert isinstance(one.result(timeout=12),dict);assert two.result(timeout=12)=='CONFLIT'
        with Session(engine) as s:assert s.scalar(sa.select(sa.func.count()).select_from(ConfigurationConventionModel))==1
        with engine.begin() as c:
            with pytest.raises(sa.exc.DBAPIError):
                with c.begin_nested():c.execute(sa.text('UPDATE tiers_payant_configurations_convention SET schema_version=2'))
            with pytest.raises(sa.exc.DBAPIError):
                with c.begin_nested():c.execute(sa.text('DELETE FROM tiers_payant_configurations_convention'))
        for values in ({'organisation_id':org,'convention_id':uuid4(),'schema_version':1},
                       {'organisation_id':uuid4(),'convention_id':UUID(one.result()['id']),'schema_version':1}):
            with Session(engine) as s:
                with pytest.raises(sa.exc.IntegrityError):
                    s.add(ConfigurationConventionModel(id=uuid4(),definition={},auteur_id=user,**values));s.commit()
                s.rollback()
        print('Deux connexions indépendantes, verrou bloquant observé, une version et un conflit contrôlé ; FK invalides refusées.')
    finally:
        release.set();pool.shutdown(wait=True,cancel_futures=True);engine.dispose();get_settings.cache_clear()
    # La base et ses preuves sont conservées ; aucune suppression automatique.
