"""Préparations historisées, engagements et pièces immuables organismes."""
from datetime import date, datetime
from uuid import UUID
from sqlalchemy import (CheckConstraint, Date, DateTime, ForeignKeyConstraint, Integer,
    JSON, LargeBinary, BigInteger, String, UniqueConstraint, Uuid, DDL, event)
from sqlalchemy.orm import Mapped, mapped_column
from neosys_pharma.infrastructure.database import Base
from neosys_pharma.infrastructure.vente_models import EntiteVente
from neosys_pharma.infrastructure.caisse_models import now, org_fk, scoped, immutable_sql


class PreparationOrganismeModel(EntiteVente, Base):
    __tablename__='tiers_payant_preparations_documents'
    __table_args__=scoped('tp_preparation_doc',org_fk('site_id','sites','id_site'),
        org_fk('organisme_id','organismes_prise_en_charge'),org_fk('convention_id','tiers_payant_conventions'),
        org_fk('auteur_id','utilisateurs','id_utilisateur'),org_fk('presentation_id','tiers_payant_preparations_documents'),
        UniqueConstraint('id','organisation_id','genre',name='uq_tp_preparation_doc_genre'),
        CheckConstraint("genre IN ('BORDEREAU','FACTURE')",name='ck_tp_preparation_doc_genre'),
        CheckConstraint('date_fin >= date_debut',name='ck_tp_preparation_doc_periode'))
    site_id:Mapped[UUID]=mapped_column(Uuid,index=True)
    organisme_id:Mapped[UUID]=mapped_column(Uuid,index=True)
    convention_id:Mapped[UUID]=mapped_column(Uuid)
    presentation_id:Mapped[UUID|None]=mapped_column(Uuid,nullable=True)
    genre:Mapped[str]=mapped_column(String(20))
    date_debut:Mapped[date]=mapped_column(Date)
    date_fin:Mapped[date]=mapped_column(Date)
    auteur_id:Mapped[UUID]=mapped_column(Uuid)
    cree_le:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=now)


class VersionPreparationOrganismeModel(EntiteVente,Base):
    __tablename__='tiers_payant_versions_preparations'
    __table_args__=scoped('tp_version_preparation',org_fk('preparation_id','tiers_payant_preparations_documents'),
        org_fk('auteur_id','utilisateurs','id_utilisateur'),UniqueConstraint('preparation_id','revision',name='uq_tp_version_preparation_revision'),
        CheckConstraint('revision > 0',name='ck_tp_version_preparation_revision'),
        CheckConstraint("etat IN ('PREPARATION','VALIDEE','ABANDONNEE','EMISE')",name='ck_tp_version_preparation_etat'))
    preparation_id:Mapped[UUID]=mapped_column(Uuid,index=True)
    revision:Mapped[int]=mapped_column(Integer)
    etat:Mapped[str]=mapped_column(String(20))
    selection:Mapped[list]=mapped_column(JSON)
    motif:Mapped[str]=mapped_column(String(2000))
    auteur_id:Mapped[UUID]=mapped_column(Uuid)
    cree_le:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=now)


class EngagementCreanceModel(EntiteVente,Base):
    """Réservation explicite ; suppression permise uniquement avant émission."""
    __tablename__='tiers_payant_engagements_creances'
    __table_args__=scoped('tp_engagement_creance',org_fk('creance_id','tiers_payant_creances'),
        ForeignKeyConstraint(['preparation_id','organisation_id','genre'],['tiers_payant_preparations_documents.id','tiers_payant_preparations_documents.organisation_id','tiers_payant_preparations_documents.genre']),
        UniqueConstraint('creance_id','genre',name='uq_tp_engagement_creance_genre'))
    preparation_id:Mapped[UUID]=mapped_column(Uuid,index=True)
    creance_id:Mapped[UUID]=mapped_column(Uuid,index=True)
    genre:Mapped[str]=mapped_column(String(20))


class DocumentOrganismeModel(EntiteVente,Base):
    __tablename__='tiers_payant_documents_emis'
    __table_args__=scoped('tp_document_emis',
        ForeignKeyConstraint(['preparation_id','organisation_id','genre'],['tiers_payant_preparations_documents.id','tiers_payant_preparations_documents.organisation_id','tiers_payant_preparations_documents.genre']),
        org_fk('site_id','sites','id_site'),org_fk('organisme_id','organismes_prise_en_charge'),org_fk('auteur_id','utilisateurs','id_utilisateur'),
        UniqueConstraint('preparation_id',name='uq_tp_document_emis_preparation'),
        UniqueConstraint('organisation_id','genre','reference',name='uq_tp_document_emis_reference'),
        UniqueConstraint('id','organisation_id','genre',name='uq_tp_document_emis_genre'),
        CheckConstraint('total_xaf > 0 AND length(pdf_sha256)=64',name='ck_tp_document_emis_total_hash'))
    preparation_id:Mapped[UUID]=mapped_column(Uuid)
    site_id:Mapped[UUID]=mapped_column(Uuid,index=True)
    organisme_id:Mapped[UUID]=mapped_column(Uuid,index=True)
    genre:Mapped[str]=mapped_column(String(20))
    reference:Mapped[str]=mapped_column(String(80))
    reference_validation:Mapped[str]=mapped_column(String(200))
    total_xaf:Mapped[int]=mapped_column(BigInteger)
    snapshot:Mapped[dict]=mapped_column(JSON)
    pdf:Mapped[bytes]=mapped_column(LargeBinary)
    pdf_sha256:Mapped[str]=mapped_column(String(64))
    auteur_id:Mapped[UUID]=mapped_column(Uuid)
    emis_le:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=now)


class LigneDocumentOrganismeModel(EntiteVente,Base):
    __tablename__='tiers_payant_lignes_documents_emis'
    __table_args__=scoped('tp_ligne_document',org_fk('creance_id','tiers_payant_creances'),
        ForeignKeyConstraint(['document_id','organisation_id','genre'],['tiers_payant_documents_emis.id','tiers_payant_documents_emis.organisation_id','tiers_payant_documents_emis.genre']),
        UniqueConstraint('creance_id','genre',name='uq_tp_ligne_document_creance_genre'),CheckConstraint('montant_xaf > 0',name='ck_tp_ligne_document_montant'))
    document_id:Mapped[UUID]=mapped_column(Uuid,index=True)
    creance_id:Mapped[UUID]=mapped_column(Uuid,index=True)
    genre:Mapped[str]=mapped_column(String(20))
    montant_xaf:Mapped[int]=mapped_column(Integer)


class RegroupementDocumentsModel(EntiteVente,Base):
    __tablename__='tiers_payant_regroupements_documents'
    __table_args__=scoped('tp_regroupement_doc',org_fk('site_id','sites','id_site'),org_fk('organisme_id','organismes_prise_en_charge'),org_fk('auteur_id','utilisateurs','id_utilisateur'),
        CheckConstraint("genre IN ('RECAPITULATIF','LOT')",name='ck_tp_regroupement_doc_genre'),
        CheckConstraint('total_xaf > 0 AND length(pdf_sha256)=64',name='ck_tp_regroupement_doc_total_hash'))
    site_id:Mapped[UUID]=mapped_column(Uuid,index=True)
    organisme_id:Mapped[UUID]=mapped_column(Uuid,index=True)
    genre:Mapped[str]=mapped_column(String(20))
    total_xaf:Mapped[int]=mapped_column(BigInteger)
    snapshot:Mapped[dict]=mapped_column(JSON)
    pdf:Mapped[bytes]=mapped_column(LargeBinary)
    pdf_sha256:Mapped[str]=mapped_column(String(64))
    auteur_id:Mapped[UUID]=mapped_column(Uuid)
    cree_le:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=now)


class MembreRegroupementModel(EntiteVente,Base):
    __tablename__='tiers_payant_membres_regroupements'
    __table_args__=scoped('tp_membre_regroupement',org_fk('regroupement_id','tiers_payant_regroupements_documents'),
        org_fk('document_id','tiers_payant_documents_emis'),org_fk('recapitulatif_id','tiers_payant_regroupements_documents'),
        CheckConstraint('(document_id IS NULL) <> (recapitulatif_id IS NULL)',name='ck_tp_membre_regroupement_type'),
        UniqueConstraint('document_id',name='uq_tp_membre_facture'),UniqueConstraint('recapitulatif_id',name='uq_tp_membre_recapitulatif'))
    regroupement_id:Mapped[UUID]=mapped_column(Uuid,index=True)
    document_id:Mapped[UUID|None]=mapped_column(Uuid,nullable=True)
    recapitulatif_id:Mapped[UUID|None]=mapped_column(Uuid,nullable=True)


IMMUTABLE=(PreparationOrganismeModel,VersionPreparationOrganismeModel,DocumentOrganismeModel,
    LigneDocumentOrganismeModel,RegroupementDocumentsModel,MembreRegroupementModel)
for model in IMMUTABLE:
    for dialect in ('sqlite','postgresql'):
        for statement in immutable_sql(model.__tablename__,dialect):
            event.listen(model.__table__,'after_create',DDL(statement).execute_if(dialect=dialect))

class SelectionVersionPreparationModel(EntiteVente,Base):
    """Index relationnel du snapshot de sélection pour filtrer les listes par emplacement."""
    __tablename__='tiers_payant_selections_versions_documents'
    __table_args__=scoped('tp_selection_version',org_fk('version_id','tiers_payant_versions_preparations'),
        org_fk('creance_id','tiers_payant_creances'),UniqueConstraint('version_id','creance_id',name='uq_tp_selection_version_creance'))
    version_id:Mapped[UUID]=mapped_column(Uuid,index=True)
    creance_id:Mapped[UUID]=mapped_column(Uuid,index=True)

for dialect in ('sqlite','postgresql'):
    for statement in immutable_sql(SelectionVersionPreparationModel.__tablename__,dialect):
        event.listen(SelectionVersionPreparationModel.__table__,'after_create',DDL(statement).execute_if(dialect=dialect))


def engagement_guard_sql(dialect):
    table='tiers_payant_engagements_creances'
    if dialect=='sqlite':
        return [f"CREATE TRIGGER tp_engagement_update BEFORE UPDATE ON {table} BEGIN SELECT RAISE(ABORT, 'Engagement non modifiable'); END",
            f"CREATE TRIGGER tp_engagement_delete BEFORE DELETE ON {table} WHEN EXISTS (SELECT 1 FROM tiers_payant_documents_emis d WHERE d.preparation_id=OLD.preparation_id) BEGIN SELECT RAISE(ABORT, 'Document emis : engagement irreversible'); END"]
    return ["CREATE OR REPLACE FUNCTION tp_engagement_guard() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN IF TG_OP='UPDATE' OR EXISTS (SELECT 1 FROM tiers_payant_documents_emis d WHERE d.preparation_id=OLD.preparation_id) THEN RAISE EXCEPTION 'Engagement emis ou modification interdite'; END IF; RETURN OLD; END $$",
        f"CREATE TRIGGER tp_engagement_guard BEFORE UPDATE OR DELETE ON {table} FOR EACH ROW EXECUTE FUNCTION tp_engagement_guard()"]

for dialect in ('sqlite','postgresql'):
    for statement in engagement_guard_sql(dialect):
        event.listen(EngagementCreanceModel.__table__,'after_create',DDL(statement).execute_if(dialect=dialect))
