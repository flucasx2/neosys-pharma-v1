"""Chaîne additive, données P4-B, contraintes et downgrade conservateur."""
import os
from uuid import uuid4
import pytest
import sqlalchemy as sa
from sqlalchemy.orm import Session
from alembic import command
from alembic.config import Config
from neosys_pharma.infrastructure.config import get_settings
from neosys_pharma.infrastructure.organisation_models import OrganisationModel
from neosys_pharma.infrastructure.client_models import OrganismePriseEnChargeModel
from neosys_pharma.infrastructure.caisse_models import MoyenPaiementModel


def cycle(url,monkeypatch):
    monkeypatch.setenv('DATABASE_URL',url);get_settings.cache_clear();cfg=Config('alembic.ini');engine=sa.create_engine(url)
    try:
        command.upgrade(cfg,'20261019_01')
        org,payer=uuid4(),uuid4()
        with Session(engine) as s:
            s.add(OrganisationModel(id_organisation=org,nom_commercial='Fictive',raison_sociale='Fictive',actif=True));s.flush()
            s.add(OrganismePriseEnChargeModel(id=payer,organisation_id=org,code='P4B',nom='Historique fictif',actif=True,revision=1));s.commit()
        before_checks={row['sqltext'] for row in sa.inspect(engine).get_check_constraints('caisse_confirmations')}
        command.upgrade(cfg,'20261019_02');command.check(cfg)
        assert before_checks <= {row['sqltext'] for row in sa.inspect(engine).get_check_constraints('caisse_confirmations')}
        with Session(engine) as s:assert s.get(OrganismePriseEnChargeModel,payer).nom=='Historique fictif'
        inspector=sa.inspect(engine)
        assert 'fk_confirmation_moyen_org_mode' in {x['name'] for x in inspector.get_foreign_keys('caisse_confirmations')}
        assert 'ck_confirmation_moyen_libelle' in {x['name'] for x in inspector.get_check_constraints('caisse_confirmations')}
        command.downgrade(cfg,'20261019_01');command.upgrade(cfg,'20261019_02')
        with Session(engine) as s:
            s.add(MoyenPaiementModel(organisation_id=org,code='MOBILE_QA',libelle='Fournisseur fictif',mode='MOBILE_MONEY',actif=True,revision=1));s.commit()
        with pytest.raises(RuntimeError,match='conserver'):command.downgrade(cfg,'20261019_01')
        with Session(engine) as s:assert s.scalar(sa.select(sa.func.count()).select_from(MoyenPaiementModel))==1
    finally:engine.dispose();get_settings.cache_clear()


def test_migration_moyens_additive_sqlite(tmp_path,monkeypatch):
    cycle('sqlite+pysqlite:///'+str(tmp_path/'moyens.db'),monkeypatch)


def test_migration_moyens_postgresql_natif(monkeypatch):
    url=os.getenv('TEST_CONSOLIDATION_MIGRATION_URL')
    if not url:pytest.skip('PostgreSQL natif jetable absent ; aucune substitution SQLite.')
    parsed=sa.engine.make_url(url)
    if parsed.get_backend_name()!='postgresql' or not (parsed.database or '').startswith('neosys_consolidation_migrations_') or os.getenv('CONSOLIDATION_CONFIRM_DATABASE')!=parsed.database:
        raise RuntimeError('Base native neuve neosys_consolidation_migrations_* confirmée requise.')
    engine=sa.create_engine(url)
    try:
        with engine.connect() as c:
            assert c.scalar(sa.text('select current_database()'))==parsed.database
            assert c.scalar(sa.text("select shobj_description(oid,'pg_database') from pg_database where datname=current_database()"))=='NEOSYS_CONSOLIDATION_MIGRATIONS_DISPOSABLE'
            assert not sa.inspect(c).get_table_names(),'Base non vide refusée.'
    finally:engine.dispose()
    cycle(url,monkeypatch)
