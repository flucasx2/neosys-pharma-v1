"""Historique synthétique B04 conservé par MIG-01/MIG-02, cible dédiée vérifiée."""
import os
from datetime import datetime,timezone
from hashlib import sha256
from uuid import UUID,uuid4
import pytest
from sqlalchemy import create_engine,MetaData,select,text,Uuid
from sqlalchemy.engine import make_url
from alembic import command
from alembic.config import Config
from test_p405_documents_annulation import raw_client,account,requested,db
from neosys_pharma.infrastructure.database import Base
from neosys_pharma.infrastructure.config import get_settings
from neosys_pharma.infrastructure.montant_xaf import MontantXAF
from neosys_pharma.domain.organisation.permissions_systeme import permission_id


def target(engine):
    # Contrôle répété avant fixture et avant suppression de son propre schéma.
    with engine.connect() as sql:
        if engine.dialect.name=='postgresql':
            sql.execute(text('SET TRANSACTION READ ONLY'))
            assert sql.scalar(text('show transaction_read_only'))=='on'
            assert sql.execute(text('select current_database(),current_user')).one()==('neosys_p405_migrations','neosys_test')
            assert sql.scalar(text("select shobj_description(oid,'pg_database') from pg_database where datname=current_database()"))=='NEOSYS_P405_MIGRATIONS_DISPOSABLE'


def typed_metadata(engine):
    metadata=MetaData();metadata.reflect(engine)
    # SQLite reflète Uuid en CHAR : restituer seulement le codec de binding,
    # sans changer le schéma historique ni lui ajouter de colonnes récentes.
    for name,table in metadata.tables.items():
        if name not in Base.metadata.tables:continue
        for col in table.columns:
            original=Base.metadata.tables[name].c.get(col.name)
            if original is not None and isinstance(original.type,(Uuid,MontantXAF)):col.type=original.type.copy()
    return metadata


def reset_disposable_schema(engine):
    target(engine)
    if engine.dialect.name=='postgresql':
        # Une fixture de migrations depuis zéro doit retirer aussi ses fonctions
        # de triggers. Identité/marqueur/compte vérifiés juste avant ce DDL.
        with engine.begin() as sql:
            sql.execute(text('DROP SCHEMA public CASCADE'))
            sql.execute(text('CREATE SCHEMA public AUTHORIZATION neosys_test'))
    else:
        metadata=MetaData();metadata.reflect(engine);metadata.drop_all(engine)


def test_migrations_preservent_historique_et_refusent_perte_document(raw_client,account,tmp_path,monkeypatch):
    c,a=raw_client,account;_,receipt,returned,refund=requested(c,a)
    url=os.getenv('TEST_MIGRATION_DATABASE_URL',f'sqlite:///{tmp_path / "p405-history.db"}')
    if not url.startswith('sqlite'):
        parsed=make_url(url)
        assert parsed.host=='test-db' and parsed.database=='neosys_p405_migrations' and parsed.username=='neosys_test'
    engine=create_engine(url);target(engine)
    # Réinitialisation de cette seule base de migrations marquée : les autres
    # campagnes peuvent y avoir laissé leurs propres fixtures de catalogue.
    reset_disposable_schema(engine)
    monkeypatch.setenv('DATABASE_URL',url);get_settings.cache_clear();cfg=Config('alembic.ini')
    try:
        command.upgrade(cfg,'head')
        with engine.connect() as sql:assert sql.scalar(text('SELECT count(*) FROM organisations'))==0
        command.downgrade(cfg,'20261019_06')
        old=typed_metadata(engine)
        gen=db(c);source=next(gen)
        try:
            with engine.begin() as dest:
                paid=[]
                for table in old.sorted_tables:
                    if table.name not in Base.metadata.tables:continue
                    origin=Base.metadata.tables[table.name]
                    existing={tuple(row) for row in dest.execute(select(*table.primary_key.columns))}
                    for row in source.execute(select(origin)).mappings():
                        if table.name=='permissions' and row['id_permission']==permission_id('caisse.remboursement.annuler'):continue
                        if table.name=='roles_permissions' and row['permission_id']==permission_id('caisse.remboursement.annuler'):continue
                        values={col.name:row[col.name] for col in table.columns if col.computed is None}
                        if table.name=='ventes' and values['etat']=='ENCAISSEE':
                            # Respecter les triggers payés : charger les enfants
                            # avant la transition finale, sans désactiver de garde.
                            paid.append(values['id']);values['etat']='TRANSMISE'
                        key=tuple(values[col.name] for col in table.primary_key.columns)
                        if key not in existing:dest.execute(table.insert().values(**values));existing.add(key)
                for sale_id in paid:
                    dest.execute(old.tables['ventes'].update().where(old.tables['ventes'].c.id==sale_id).values(etat='ENCAISSEE'))
        finally:gen.close()
        def history():
            with engine.connect() as sql:
                return {name:[tuple(r) for r in sql.execute(old.tables[name].select().order_by(old.tables[name].c.id))]
                    for name in ('ventes','vente_lignes','vente_retours','finance_remboursements','caisse_encaissements','stock_mouvements')}
        before=history()
        command.upgrade(cfg,'head');command.check(cfg)
        assert history()==before
        with engine.connect() as sql:
            assert sql.scalar(text('SELECT count(*) FROM vente_documents_retour'))==0
            assert sql.scalar(text('SELECT count(*) FROM finance_annulations_remboursement'))==0
            assert sql.scalar(text("SELECT count(*) FROM roles_permissions rp JOIN permissions p ON p.id_permission=rp.permission_id WHERE p.code='caisse.remboursement.annuler'"))==0
        # Le retour ancien reste sans pièce après montée/descente/remontée.
        command.downgrade(cfg,'20261019_06');command.upgrade(cfg,'head');assert history()==before
        metadata=typed_metadata(engine)
        with engine.begin() as sql:
            sql.execute(metadata.tables['vente_documents_retour'].insert().values(
                id=UUID(returned['document']['id']),organisation_id=a['org'],retour_id=UUID(returned['id']),
                auteur_id=a['user'],instantane={'fixture':'document protégé'},pdf=b'%PDF-fictif',
                pdf_sha256=sha256(b'%PDF-fictif').hexdigest(),date=datetime.now(timezone.utc)))
        with pytest.raises(RuntimeError,match='documents de retour à conserver'):command.downgrade(cfg,'20261019_06')
        with engine.connect() as sql:assert sql.scalar(text('SELECT count(*) FROM vente_documents_retour'))==1
        command.upgrade(cfg,'head')
        with engine.begin() as sql:
            sql.execute(metadata.tables['finance_remboursements'].update().where(metadata.tables['finance_remboursements'].c.id==UUID(refund['id'])).values(etat='ANNULE',revision=2))
            sql.execute(metadata.tables['finance_annulations_remboursement'].insert().values(
                id=uuid4(),organisation_id=a['org'],remboursement_id=UUID(refund['id']),auteur_id=a['user'],
                justification='Fixture annulation protégée',attestation_absence_restitution=True,
                revision_avant=1,revision_apres=2,instantane={},date=datetime.now(timezone.utc)))
        with pytest.raises(RuntimeError,match='annulations et remplacements historiques'):command.downgrade(cfg,'20261022_01')
    finally:
        # Fin de fixture : supprimer exclusivement le schéma synthétique dédié.
        reset_disposable_schema(engine)
        engine.dispose();get_settings.cache_clear()
