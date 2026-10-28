"""Préservation réelle d'une créance P5-C.1 avant/après la migration additive."""
import os
from uuid import UUID,uuid4
from datetime import date,datetime,timezone,timedelta
import pytest
import sqlalchemy as sa
from sqlalchemy.orm import Session,sessionmaker
from fastapi.testclient import TestClient
from alembic import command
from alembic.config import Config
from neosys_pharma.infrastructure.config import get_settings
from neosys_pharma.infrastructure.database import get_db_session
from neosys_pharma.presentation.app import create_app
from neosys_pharma.infrastructure.creance_models import CompensationCreanceOrganismeModel,CreanceOrganismeModel
from neosys_pharma.infrastructure.prise_en_charge_models import RealisationPriseEnChargeModel
from neosys_pharma.application.stock_service import StockService
from neosys_pharma.application.facturation_organisme_service import FacturationOrganismeService
from test_authentification import account as account_fixture
from test_p5c_creances import prepare,realise,post as claim_post
from test_p5c2_facturation import validate_claim,body


def cycle(url,monkeypatch):
    monkeypatch.setenv('DATABASE_URL',url);monkeypatch.setenv('AUTH_COOKIE_SECURE','false');get_settings.cache_clear()
    engine=sa.create_engine(url);cfg=Config('alembic.ini')
    if url.startswith('sqlite'):
        @sa.event.listens_for(engine,'connect')
        def fk(c,_):c.execute('pragma foreign_keys=ON')
    try:
        command.upgrade(cfg,'20261019_05')
        factory=sessionmaker(engine)
        # Le catalogue de sécurité est déjà installé par les migrations P1/P4/P5.
        app=create_app()
        def sessions():
            with factory() as s:yield s
        app.dependency_overrides[get_db_session]=sessions
        # Current application code reads the REG-01 compensation register even
        # while this test stages a legacy 20261019_05 row. Provide only its
        # empty ORM table during fixture creation, then remove it before the
        # actual migration upgrade so 20261028_02 still creates it normally.
        compensation_table=CompensationCreanceOrganismeModel.__table__
        assert not sa.inspect(engine).has_table(compensation_table.name)
        compensation_table.create(engine)
        try:
            with TestClient(app) as c:
                a=account_fixture.__wrapped__(c);sale,session,calc=prepare(c,a);real,_=realise(c,a,sale,session,calc)
                claim=validate_claim(c,a,claim_post(c,a,'',{'realisation_id':real['id']},201)['creances'][0])
                instant=datetime.fromisoformat(real['realisee_le'])
                realisation_day=instant.astimezone(timezone.utc).date() if instant.tzinfo else instant.date()
        finally:
            compensation_table.drop(engine)
        command.upgrade(cfg,'20261019_06')
        command.upgrade(cfg,'head');command.check(cfg);engine.dispose()
        with factory() as s:
            assert s.get(CreanceOrganismeModel,UUID(claim['id'])).snapshot_hash==claim['snapshot_hash']
            assert s.get(RealisationPriseEnChargeModel,UUID(real['id'])).total_organismes_xaf==real['total_organismes_xaf']
        command.downgrade(cfg,'20261019_05');command.upgrade(cfg,'head');command.check(cfg)
        with factory() as s:
            stock=StockService(s,a['org'],a['user'],lambda *args:None,date.today());data=body([claim])
            data['organisme_id']=UUID(data['organisme_id']);data['convention_id']=UUID(data['convention_id'])
            data['date_debut']=data['date_fin']=realisation_day
            result=stock.operation(uuid4(),'MIGRATION:PREPARER',{'test':'fictif'},lambda:FacturationOrganismeService(stock,a['site']).creer(data))
            assert result['version']['etat']=='PREPARATION'
        with pytest.raises(RuntimeError,match='conserver'):command.downgrade(cfg,'20261019_05')
        with factory() as s:assert s.get(CreanceOrganismeModel,UUID(claim['id'])).snapshot_hash==claim['snapshot_hash']
    finally:engine.dispose();get_settings.cache_clear()


def test_migration_p5c2_sqlite(tmp_path,monkeypatch):cycle('sqlite+pysqlite:///'+str(tmp_path/'historique.db'),monkeypatch)


def test_migration_p5c2_native(monkeypatch):
    url=os.getenv('TEST_P5C2_MIGRATION_URL')
    if not url:pytest.skip('Base PostgreSQL native neuve P5-C.2 absente.')
    parsed=sa.engine.make_url(url)
    if parsed.get_backend_name()!='postgresql' or not (parsed.database or '').startswith('neosys_p5c2_migrations_') or os.getenv('P5C2_CONFIRM_DATABASE')!=parsed.database:
        raise RuntimeError('Base neuve neosys_p5c2_migrations_* confirmée exactement requise.')
    engine=sa.create_engine(url)
    try:
        with engine.connect() as c:
            assert c.scalar(sa.text('select current_database()'))==parsed.database
            assert c.scalar(sa.text("select shobj_description(oid,'pg_database') from pg_database where datname=current_database()"))=='NEOSYS_P5C2_DISPOSABLE'
            assert not sa.inspect(c).get_table_names(),'Base préexistante non vide refusée.'
            print(c.scalar(sa.text('select version()')),parsed.database)
    finally:engine.dispose()
    cycle(url,monkeypatch)


def test_migration_p5c2_sqlite_changement_jour_utc(tmp_path,monkeypatch):
    # Le générateur de payload passe au lendemain, la réalisation reste historique.
    import test_p5c2_facturation as fixtures
    tomorrow=date.today()+timedelta(days=1)
    class Tomorrow(date):
        @classmethod
        def today(cls):return tomorrow
    monkeypatch.setattr(fixtures,'date',Tomorrow)
    cycle('sqlite+pysqlite:///'+str(tmp_path/'historique-changement-jour.db'),monkeypatch)
