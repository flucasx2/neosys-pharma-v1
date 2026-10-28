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
        assert 'tiers_payant_compensations_creances' in i.get_table_names()
        assert 'uq_tp_compensation_creance_retour' in {x['name'] for x in i.get_unique_constraints('tiers_payant_compensations_creances')}
        assert {'ck_tp_compensation_creance_montant','ck_tp_compensation_creance_hash'} <= {
            x['name'] for x in i.get_check_constraints('tiers_payant_compensations_creances')}
        if engine.dialect.name=='sqlite':
            with engine.connect() as c:
                names={x[0] for x in c.execute(sa.text(
                    "SELECT name FROM sqlite_master WHERE type='trigger' AND tbl_name='tiers_payant_compensations_creances'"))}
            assert {'tiers_payant_compensations_creances_update_immutable',
                    'tiers_payant_compensations_creances_delete_immutable'} <= names
        elif engine.dialect.name=='postgresql':
            with engine.connect() as c:
                names={x[0] for x in c.execute(sa.text(
                    "SELECT tgname FROM pg_trigger WHERE tgrelid=to_regclass(:table) AND NOT tgisinternal"),
                    {'table':'tiers_payant_compensations_creances'})}
            assert 'tiers_payant_compensations_creances_immutable' in names
        with Session(engine) as s:assert s.get(OrganismePriseEnChargeModel,payer).nom=='Historique fictif'
        command.downgrade(cfg,'20261019_04');command.upgrade(cfg,'head');command.check(cfg)
        with Session(engine) as s:assert s.get(OrganismePriseEnChargeModel,payer).revision==1
        if engine.dialect.name=='sqlite':
            from sqlalchemy.exc import DBAPIError
            with engine.connect() as c:
                c.exec_driver_sql('PRAGMA foreign_keys=OFF')
                c.execute(sa.text(f"INSERT INTO tiers_payant_compensations_creances "
                    "(id,organisation_id,creance_id,retour_id,montant_xaf,snapshot,snapshot_hash,motif,auteur_id,cree_le) "
                    "VALUES (:id,:org,:creance,:retour,10,'{}',:hash,'preuve jetable',:auteur,'2026-10-28T00:00:00+00:00')"),
                    {'id':str(uuid4()),'org':str(org),'creance':str(uuid4()),'retour':str(uuid4()),
                     'hash':'a'*64,'auteur':str(uuid4())})
                c.commit()
                with pytest.raises(DBAPIError):
                    c.execute(sa.text(f"UPDATE tiers_payant_compensations_creances SET montant_xaf=11"));c.commit()
                c.rollback()
                with pytest.raises(DBAPIError):
                    c.execute(sa.text(f"DELETE FROM tiers_payant_compensations_creances"));c.commit()
                c.rollback()
            with pytest.raises(RuntimeError,match='Downgrade refusé'):
                command.downgrade(cfg,'20261028_01')
        elif engine.dialect.name=='postgresql':
            from sqlalchemy.exc import DBAPIError
            with engine.connect() as c:
                triggers={x[0] for x in c.execute(sa.text(
                    "SELECT tgname FROM pg_trigger WHERE tgrelid=to_regclass(:table) AND NOT tgisinternal"),
                    {'table':'tiers_payant_compensations_creances'})}
            assert 'tiers_payant_compensations_creances_immutable' in triggers
            # Ce témoin invalide les FK uniquement pendant l'insertion; il
            # permet de vérifier les triggers immuables sans créer de faux
            # dossier métier dans les tables P4/P5 parentes.
            values={'id':str(uuid4()),'org':str(org),'creance':str(uuid4()),'retour':str(uuid4()),
                'hash':'b'*64,'auteur':str(uuid4())}
            with engine.begin() as c:
                c.execute(sa.text('SET session_replication_role = replica'))
                c.execute(sa.text("INSERT INTO tiers_payant_compensations_creances "
                    "(id,organisation_id,creance_id,retour_id,montant_xaf,snapshot,snapshot_hash,motif,auteur_id,cree_le) "
                    "VALUES (:id,:org,:creance,:retour,10,'{}'::json,:hash,'preuve jetable',:auteur,'2026-10-28T00:00:00+00:00')"),values)
                c.execute(sa.text('SET session_replication_role = origin'))
            for statement in (
                "UPDATE tiers_payant_compensations_creances SET montant_xaf=11",
                "DELETE FROM tiers_payant_compensations_creances",
            ):
                with pytest.raises(DBAPIError):
                    with engine.begin() as c:c.execute(sa.text(statement))
            with pytest.raises(RuntimeError,match='Downgrade refusé'):
                command.downgrade(cfg,'20261028_01')
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
