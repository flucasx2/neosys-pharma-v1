"""Chaîne jusqu'à 20261019_05 ; base native neuve marquée, jamais une base conservée."""
import os
import pytest
import sqlalchemy as sa
from sqlalchemy.orm import Session
from alembic import command
from alembic.config import Config
from uuid import uuid4
from neosys_pharma.infrastructure.config import get_settings
from neosys_pharma.infrastructure.organisation_models import OrganisationModel
from neosys_pharma.infrastructure.client_models import OrganismePriseEnChargeModel
from neosys_pharma.infrastructure import creance_models


def cycle(url,monkeypatch):
    monkeypatch.setenv('DATABASE_URL',url);get_settings.cache_clear();engine=sa.create_engine(url);cfg=Config('alembic.ini')
    try:
        command.upgrade(cfg,'20261019_04');org,payer=uuid4(),uuid4()
        with Session(engine) as s:
            s.add(OrganisationModel(id_organisation=org,nom_commercial='Fictive',raison_sociale='Fictive',actif=True));s.flush()
            s.add(OrganismePriseEnChargeModel(id=payer,organisation_id=org,code='P4B',nom='Historique fictif',actif=True,revision=1));s.commit()
        command.upgrade(cfg,'20261019_05');command.upgrade(cfg,'head');command.check(cfg)
        # Alembic utilise son propre moteur ; relire le schéma avec une connexion neuve.
        engine.dispose()
        i=sa.inspect(engine)
        assert 'uq_tp_creance_source' in {x['name'] for x in i.get_unique_constraints('tiers_payant_creances')}
        assert 'fk_tp_creance_realisation_scope' in {x['name'] for x in i.get_foreign_keys('tiers_payant_creances')}
        assert 'uq_tp_creance_revision' in {x['name'] for x in i.get_unique_constraints('tiers_payant_creances_versions')}
        with Session(engine) as s:assert s.get(OrganismePriseEnChargeModel,payer).nom=='Historique fictif'
        command.downgrade(cfg,'20261019_04');command.upgrade(cfg,'head');command.check(cfg)
        with Session(engine) as s:assert s.get(OrganismePriseEnChargeModel,payer).revision==1
    finally:engine.dispose();get_settings.cache_clear()


def test_migration_p5c_sqlite(tmp_path,monkeypatch):cycle('sqlite+pysqlite:///'+str(tmp_path/'creances.db'),monkeypatch)


def test_migration_p5c_postgresql(monkeypatch):
    url=os.getenv('TEST_P5C_MIGRATION_URL')
    if not url:pytest.skip('Base PostgreSQL native jetable P5-C absente.')
    p=sa.engine.make_url(url)
    if p.get_backend_name()!='postgresql' or not (p.database or '').startswith('neosys_p5c_migrations_') or os.getenv('P5C_CONFIRM_DATABASE')!=p.database:
        raise RuntimeError('Base neuve neosys_p5c_migrations_* et confirmation exacte requises.')
    engine=sa.create_engine(url)
    try:
        with engine.connect() as c:
            assert c.scalar(sa.text('select current_database()'))==p.database
            assert c.scalar(sa.text("select shobj_description(oid,'pg_database') from pg_database where datname=current_database()"))=='NEOSYS_P5C_DISPOSABLE'
            assert not sa.inspect(c).get_table_names(),'Base préexistante non vide refusée.'
            print('PostgreSQL natif',c.scalar(sa.text('select version()')),p.database)
    finally:engine.dispose()
    cycle(url,monkeypatch)
