"""Alembic sur fichiers SQLite neufs dans tmp_path, jamais une base conservée."""
from pathlib import Path
from uuid import UUID
import hashlib
import pytest
from sqlalchemy import create_engine, MetaData, select, inspect, text
from alembic import command
from alembic.config import Config
from neosys_pharma.infrastructure.config import get_settings
from neosys_pharma.infrastructure.database import Base
from neosys_pharma.infrastructure.encaissement_groupe_sql_v1 import guard_sql
from test_caisse import raw_client, account, ready, final, db
from test_encaissement_groupe_persistance import eg32_garde_base


def cfg_for(monkeypatch, path):
    assert path.name.startswith('neosys_eg32_jetable_') and not path.exists()
    monkeypatch.setenv('DATABASE_URL',f'sqlite+pysqlite:///{path}');get_settings.cache_clear()
    return Config('alembic.ini')


def test_cycle_neuf_contraintes_et_permissions(monkeypatch,tmp_path):
    cfg=cfg_for(monkeypatch,tmp_path/'neosys_eg32_jetable_cycle.db')
    try:
        command.upgrade(cfg,'head');command.check(cfg)
        engine=create_engine(get_settings().database_url)
        checks={x['sqltext'] for x in inspect(engine).get_check_constraints('caisse_reglements')}
        assert any('rendu >= 0' in c for c in checks) and any("mode='ESPECES'" in c for c in checks)
        with engine.connect() as c:
            assert c.scalar(text("SELECT count(*) FROM roles_permissions rp JOIN permissions p ON p.id_permission=rp.permission_id WHERE p.code='caisse.encaisser.groupe'"))==0
        engine.dispose();command.downgrade(cfg,'a46c001d2026');command.upgrade(cfg,'head');command.check(cfg)
    finally:get_settings.cache_clear()


def test_installateur_postgresql_repetable():
    statements = guard_sql('postgresql')
    creates = [s for s in statements if s.startswith(('CREATE TRIGGER ', 'CREATE CONSTRAINT TRIGGER '))]
    drops = {s.split()[4] for s in statements if s.startswith('DROP TRIGGER IF EXISTS ')}
    assert creates
    for statement in creates:
        parts = statement.split()
        trigger = parts[3] if parts[:3] == ['CREATE', 'CONSTRAINT', 'TRIGGER'] else parts[2]
        assert trigger in drops
    assert any(s.startswith('CREATE OR REPLACE FUNCTION eg32_claim') for s in statements)


def test_downgrade_refuse_nouvelles_donnees(raw_client,account,monkeypatch,tmp_path):
    from test_encaissement_groupe_persistance import sample
    from neosys_pharma.infrastructure.encaissement_groupe_repository import SqlAlchemyEncaissementGroupeRepository
    from sqlalchemy.orm import Session
    v,w,se,d,s,gen=sample(raw_client,account)
    try:source={table.name:[dict(r) for r in s.execute(select(table)).mappings()] for table in Base.metadata.sorted_tables}
    finally:gen.close()
    cfg=cfg_for(monkeypatch,tmp_path/'neosys_eg32_jetable_refus.db')
    try:
        command.upgrade(cfg,'head');engine=create_engine(get_settings().database_url)
        target_meta=MetaData();target_meta.reflect(engine)
        with engine.begin() as conn:
            for table in Base.metadata.sorted_tables:
                target=target_meta.tables[table.name]
                for col in target.c:col.type=table.c[col.name].type
                for row in source[table.name]:
                    values={k:n for k,n in row.items() if target.c[k].computed is None}
                    conn.execute(target.insert().prefix_with('OR IGNORE').values(**values))
        with Session(engine) as session:
            SqlAlchemyEncaissementGroupeRepository(session,d.organisation_id).ajouter_dossier(d);session.commit()
        with pytest.raises(ValueError,match='Downgrade refusé'):command.downgrade(cfg,'a46c001d2026')
        with engine.connect() as c:assert c.scalar(text('SELECT count(*) FROM caisse_dossiers_groupes'))==1
        engine.dispose()
    finally:get_settings.cache_clear()


def test_historique_fictif_pdf_et_journaux_inchanges(raw_client,account,monkeypatch,tmp_path):
    c,a=raw_client,account;v,se,*_=ready(c,a,q=1);receipt=final(c,a,v,se)
    gen=db(c);s=next(gen)
    try:source={table.name:[dict(r) for r in s.execute(select(table)).mappings()] for table in Base.metadata.sorted_tables}
    finally:gen.close()
    path=tmp_path/'neosys_eg32_jetable_historique.db';cfg=cfg_for(monkeypatch,path)
    try:
        command.upgrade(cfg,'a46c001d2026');engine=create_engine(get_settings().database_url)
        old=MetaData();old.reflect(engine)
        with engine.begin() as conn:
            # Charger uniquement des données créées par les fixtures SQLite mémoire.
            for table in Base.metadata.sorted_tables:
                if table.name not in old.tables:continue
                target=old.tables[table.name]
                for col in target.c:
                    if col.name in table.c:col.type=table.c[col.name].type
                for row in source[table.name]:
                    values={k:n for k,n in row.items() if k in target.c and target.c[k].computed is None}
                    if table.name=='permissions' and values['code']=='caisse.encaisser.groupe':continue
                    if table.name=='ventes' and values['etat']=='ENCAISSEE':values['etat']='TRANSMISE'
                    conn.execute(target.insert().prefix_with('OR IGNORE').values(**values))
            conn.execute(text("UPDATE ventes SET etat='ENCAISSEE' WHERE id=:id"),{'id':UUID(v['id']).hex})
        financial=['caisse_encaissements','caisse_reglements','caisse_mouvements','fidelite_journal','caisse_evenements']
        def snapshot():
            with engine.connect() as conn:
                return {name:list(conn.execute(text('SELECT '+','.join(col.name for col in old.tables[name].c)+' FROM '+name+' ORDER BY id'))) for name in financial}
        before=snapshot();pdf=before['caisse_encaissements'][0][list(old.tables['caisse_encaissements'].c.keys()).index('pdf')]
        digest=hashlib.sha256(pdf).hexdigest()
        command.upgrade(cfg,'head');command.check(cfg)
        assert snapshot()==before and hashlib.sha256(snapshot()['caisse_encaissements'][0][list(old.tables['caisse_encaissements'].c.keys()).index('pdf')]).hexdigest()==digest
        with engine.connect() as conn:
            assert conn.scalar(text('SELECT count(*) FROM caisse_ventes_encaissees'))==1
            assert conn.scalar(text('SELECT count(*) FROM caisse_ventilations'))==0
        command.downgrade(cfg,'a46c001d2026');assert snapshot()==before
        command.upgrade(cfg,'head');assert snapshot()==before;engine.dispose()
    finally:get_settings.cache_clear()
