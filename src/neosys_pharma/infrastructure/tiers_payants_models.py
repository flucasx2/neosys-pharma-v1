"""P5-A persistence. P4-B payor and client tables remain the source identities."""
from datetime import date, datetime, timezone
from uuid import UUID, uuid4

from sqlalchemy import (
    Boolean, CheckConstraint, Date, DateTime, ForeignKeyConstraint, Index, JSON,
    String, UniqueConstraint, Uuid, event, DDL, text,
)
from sqlalchemy.orm import Mapped, mapped_column

from neosys_pharma.infrastructure.database import Base
from neosys_pharma.infrastructure.vente_models import EntiteVente


def now():
    return datetime.now(timezone.utc)


class ConventionOrganismeModel(EntiteVente, Base):
    __tablename__ = "tiers_payant_conventions"
    __table_args__ = (
        UniqueConstraint("id", "organisation_id", name="uq_tp_convention_org"),
        UniqueConstraint("organisation_id", "organisme_id", "code", "version", name="uq_tp_convention_version"),
        ForeignKeyConstraint(["organisme_id", "organisation_id"], ["organismes_prise_en_charge.id", "organismes_prise_en_charge.organisation_id"], name="fk_tp_convention_organisme_org"),
        ForeignKeyConstraint(["auteur_id", "organisation_id"], ["utilisateurs.id_utilisateur", "utilisateurs.organisation_id"], name="fk_tp_convention_auteur_org"),
        CheckConstraint("version > 0", name="ck_tp_convention_version"),
        CheckConstraint("date_fin IS NULL OR date_fin >= date_debut", name="ck_tp_convention_periode"),
        CheckConstraint("length(trim(code)) > 0", name="ck_tp_convention_code"),
        CheckConstraint("statut IN ('ACTIVE','INACTIVE')", name="ck_tp_convention_statut"),
        Index("ix_tp_convention_organisme_periode", "organisation_id", "organisme_id", "date_debut", "date_fin"),
    )
    organisme_id: Mapped[UUID] = mapped_column(Uuid)
    code: Mapped[str] = mapped_column(String(80))
    version: Mapped[int] = mapped_column()
    reference_contractuelle: Mapped[str | None] = mapped_column(String(200))
    date_debut: Mapped[date] = mapped_column(Date)
    date_fin: Mapped[date | None] = mapped_column(Date)
    statut: Mapped[str] = mapped_column(String(20), default="ACTIVE")
    conditions: Mapped[dict] = mapped_column(JSON, default=dict)
    extensions_p5b: Mapped[dict] = mapped_column(JSON, default=dict)
    auteur_id: Mapped[UUID] = mapped_column(Uuid)
    cree_le: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class BeneficiaireCouvertureModel(EntiteVente, Base):
    __tablename__ = "tiers_payant_beneficiaires"
    __table_args__ = (
        UniqueConstraint("id", "organisation_id", name="uq_tp_beneficiaire_org"),
        ForeignKeyConstraint(["client_id", "organisation_id"], ["clients.id", "clients.organisation_id"], name="fk_tp_beneficiaire_client_org"),
        ForeignKeyConstraint(["auteur_id", "organisation_id"], ["utilisateurs.id_utilisateur", "utilisateurs.organisation_id"], name="fk_tp_beneficiaire_auteur_org"),
        CheckConstraint("revision > 0", name="ck_tp_beneficiaire_revision"),
        CheckConstraint("length(trim(nom)) > 0", name="ck_tp_beneficiaire_nom"),
        Index("ix_tp_beneficiaire_client", "organisation_id", "client_id"),
    )
    client_id: Mapped[UUID | None] = mapped_column(Uuid)
    nom: Mapped[str] = mapped_column(String(200))
    date_naissance: Mapped[date | None] = mapped_column(Date)
    reference_externe: Mapped[str | None] = mapped_column(String(200))
    actif: Mapped[bool] = mapped_column(Boolean, default=True)
    revision: Mapped[int] = mapped_column(default=1)
    auteur_id: Mapped[UUID] = mapped_column(Uuid)
    cree_le: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class AdhesionOrganismeModel(EntiteVente, Base):
    __tablename__ = "tiers_payant_adhesions"
    __table_args__ = (
        UniqueConstraint("id", "organisation_id", name="uq_tp_adhesion_org"),
        UniqueConstraint("id", "organisation_id", "convention_id", name="uq_tp_adhesion_convention_scope"),
        UniqueConstraint("organisation_id", "reference_adhesion", "date_debut", name="uq_tp_adhesion_reference_debut"),
        ForeignKeyConstraint(["convention_id", "organisation_id"], ["tiers_payant_conventions.id", "tiers_payant_conventions.organisation_id"], name="fk_tp_adhesion_convention_org"),
        ForeignKeyConstraint(["titulaire_id", "organisation_id"], ["tiers_payant_beneficiaires.id", "tiers_payant_beneficiaires.organisation_id"], name="fk_tp_adhesion_titulaire_org"),
        ForeignKeyConstraint(["auteur_id", "organisation_id"], ["utilisateurs.id_utilisateur", "utilisateurs.organisation_id"], name="fk_tp_adhesion_auteur_org"),
        CheckConstraint("date_fin IS NULL OR date_fin >= date_debut", name="ck_tp_adhesion_periode"),
        CheckConstraint("statut IN ('ACTIVE','INACTIVE','SUSPENDUE')", name="ck_tp_adhesion_statut"),
        CheckConstraint("droits_statut IN ('A_VERIFIER','CONFIRMES','REFUSES','SUSPENDUS')", name="ck_tp_adhesion_droits"),
        CheckConstraint("droits_statut = 'A_VERIFIER' OR (reference_verification_droits IS NOT NULL AND droits_verifies_le IS NOT NULL)", name="ck_tp_adhesion_droits_preuve"),
        CheckConstraint("revision > 0", name="ck_tp_adhesion_revision"),
        Index("ix_tp_adhesion_convention_periode", "organisation_id", "convention_id", "date_debut", "date_fin"),
    )
    convention_id: Mapped[UUID] = mapped_column(Uuid)
    titulaire_id: Mapped[UUID] = mapped_column(Uuid)
    reference_adhesion: Mapped[str] = mapped_column(String(200))
    date_debut: Mapped[date] = mapped_column(Date)
    date_fin: Mapped[date | None] = mapped_column(Date)
    statut: Mapped[str] = mapped_column(String(20), default="ACTIVE")
    droits_statut: Mapped[str] = mapped_column(String(20), default="A_VERIFIER")
    reference_verification_droits: Mapped[str | None] = mapped_column(String(200))
    droits_verifies_le: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    revision: Mapped[int] = mapped_column(default=1)
    auteur_id: Mapped[UUID] = mapped_column(Uuid)
    cree_le: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class AdhesionBeneficiaireModel(EntiteVente, Base):
    __tablename__ = "tiers_payant_adhesion_beneficiaires"
    __table_args__ = (
        UniqueConstraint("adhesion_id", "beneficiaire_id", name="uq_tp_adhesion_beneficiaire"),
        ForeignKeyConstraint(["adhesion_id", "organisation_id"], ["tiers_payant_adhesions.id", "tiers_payant_adhesions.organisation_id"], name="fk_tp_lien_adhesion_org"),
        ForeignKeyConstraint(["beneficiaire_id", "organisation_id"], ["tiers_payant_beneficiaires.id", "tiers_payant_beneficiaires.organisation_id"], name="fk_tp_lien_beneficiaire_org"),
        CheckConstraint("relation IN ('TITULAIRE','AYANT_DROIT','AUTRE')", name="ck_tp_lien_relation"),
        CheckConstraint("date_fin IS NULL OR date_fin >= date_debut", name="ck_tp_lien_periode"),
        Index("ix_tp_lien_beneficiaire", "organisation_id", "beneficiaire_id"),
    )
    adhesion_id: Mapped[UUID] = mapped_column(Uuid)
    beneficiaire_id: Mapped[UUID] = mapped_column(Uuid)
    relation: Mapped[str] = mapped_column(String(20))
    date_debut: Mapped[date] = mapped_column(Date)
    date_fin: Mapped[date | None] = mapped_column(Date)


class ParametragePrioriteTiersPayantModel(EntiteVente, Base):
    __tablename__ = "tiers_payant_parametrages_priorite"
    __table_args__ = (
        UniqueConstraint("id", "organisation_id", name="uq_tp_priorite_org"),
        UniqueConstraint("organisation_id", "version", name="uq_tp_priorite_version"),
        UniqueConstraint("organisation_id", "date_debut", name="uq_tp_priorite_debut"),
        ForeignKeyConstraint(["auteur_id", "organisation_id"], ["utilisateurs.id_utilisateur", "utilisateurs.organisation_id"], name="fk_tp_priorite_auteur_org"),
        CheckConstraint("version > 0", name="ck_tp_priorite_version"),
        CheckConstraint("date_fin IS NULL OR date_fin >= date_debut", name="ck_tp_priorite_periode"),
        CheckConstraint("statut IN ('ACTIVE','INACTIVE')", name="ck_tp_priorite_statut"),
        CheckConstraint("length(trim(motif)) > 0", name="ck_tp_priorite_motif"),
    )
    version: Mapped[int] = mapped_column()
    date_debut: Mapped[date] = mapped_column(Date)
    date_fin: Mapped[date | None] = mapped_column(Date)
    statut: Mapped[str] = mapped_column(String(20))
    motif: Mapped[str] = mapped_column(String(2000))
    auteur_id: Mapped[UUID] = mapped_column(Uuid)
    cree_le: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class PrioriteOrganismeModel(EntiteVente, Base):
    __tablename__ = "tiers_payant_priorites"
    __table_args__ = (
        UniqueConstraint("parametrage_id", "rang", name="uq_tp_priorite_rang"),
        UniqueConstraint("parametrage_id", "organisme_id", name="uq_tp_priorite_organisme"),
        ForeignKeyConstraint(["parametrage_id", "organisation_id"], ["tiers_payant_parametrages_priorite.id", "tiers_payant_parametrages_priorite.organisation_id"], name="fk_tp_priorite_entete_org"),
        ForeignKeyConstraint(["organisme_id", "organisation_id"], ["organismes_prise_en_charge.id", "organismes_prise_en_charge.organisation_id"], name="fk_tp_priorite_organisme_org"),
        ForeignKeyConstraint(["convention_id", "organisation_id"], ["tiers_payant_conventions.id", "tiers_payant_conventions.organisation_id"], name="fk_tp_priorite_convention_org"),
        CheckConstraint("rang > 0", name="ck_tp_priorite_rang"),
        CheckConstraint("role IN ('PRINCIPAL','SECONDAIRE')", name="ck_tp_priorite_role"),
        CheckConstraint("role != 'PRINCIPAL' OR rang = 1", name="ck_tp_principal_premier"),
        Index("uq_tp_priorite_principal", "parametrage_id", unique=True,
              postgresql_where=text("role = 'PRINCIPAL'"), sqlite_where=text("role = 'PRINCIPAL'")),
        Index("ix_tp_priorite_parametrage", "organisation_id", "parametrage_id", "rang"),
    )
    parametrage_id: Mapped[UUID] = mapped_column(Uuid)
    organisme_id: Mapped[UUID] = mapped_column(Uuid)
    convention_id: Mapped[UUID] = mapped_column(Uuid)
    rang: Mapped[int] = mapped_column()
    role: Mapped[str] = mapped_column(String(20))


class EvenementTiersPayantModel(EntiteVente, Base):
    __tablename__ = "tiers_payant_evenements"
    __table_args__ = (
        ForeignKeyConstraint(["auteur_id", "organisation_id"], ["utilisateurs.id_utilisateur", "utilisateurs.organisation_id"], name="fk_tp_event_auteur_org"),
        CheckConstraint("length(trim(type)) > 0", name="ck_tp_event_type"),
        Index("ix_tp_event_entity", "organisation_id", "entite_type", "entite_id", "date"),
    )
    entite_type: Mapped[str] = mapped_column(String(50))
    entite_id: Mapped[UUID] = mapped_column(Uuid)
    type: Mapped[str] = mapped_column(String(80))
    donnees: Mapped[dict] = mapped_column(JSON)
    auteur_id: Mapped[UUID] = mapped_column(Uuid)
    date: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)



class ConfigurationConventionModel(EntiteVente, Base):
    """Une configuration immuable par version de convention, créée atomiquement."""
    __tablename__ = "tiers_payant_configurations_convention"
    __table_args__ = (
        UniqueConstraint("convention_id", "organisation_id", name="uq_tp_conf_convention"),
        UniqueConstraint("id", "organisation_id", "convention_id", name="uq_tp_conf_scope"),
        ForeignKeyConstraint(["convention_id", "organisation_id"], ["tiers_payant_conventions.id", "tiers_payant_conventions.organisation_id"], name="fk_tp_conf_convention_org"),
        ForeignKeyConstraint(["auteur_id", "organisation_id"], ["utilisateurs.id_utilisateur", "utilisateurs.organisation_id"], name="fk_tp_conf_auteur_org"),
        CheckConstraint("schema_version = 1", name="ck_tp_conf_schema"),
    )
    convention_id: Mapped[UUID] = mapped_column(Uuid)
    schema_version: Mapped[int] = mapped_column(default=1)
    definition: Mapped[dict] = mapped_column(JSON)
    auteur_id: Mapped[UUID] = mapped_column(Uuid)
    cree_le: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class VerificationConventionModel(EntiteVente, Base):
    __tablename__ = "tiers_payant_verifications_convention"
    __table_args__ = (
        ForeignKeyConstraint(["configuration_id", "organisation_id", "convention_id"], ["tiers_payant_configurations_convention.id", "tiers_payant_configurations_convention.organisation_id", "tiers_payant_configurations_convention.convention_id"], name="fk_tp_verif_configuration_scope"),
        ForeignKeyConstraint(["adhesion_id", "organisation_id", "convention_id"], ["tiers_payant_adhesions.id", "tiers_payant_adhesions.organisation_id", "tiers_payant_adhesions.convention_id"], name="fk_tp_verif_adhesion_org"),
        ForeignKeyConstraint(["adhesion_id", "beneficiaire_id"], ["tiers_payant_adhesion_beneficiaires.adhesion_id", "tiers_payant_adhesion_beneficiaires.beneficiaire_id"], name="fk_tp_verif_lien_beneficiaire"),
        ForeignKeyConstraint(["vente_id", "organisation_id", "site_id"], ["ventes.id", "ventes.organisation_id", "ventes.site_id"], name="fk_tp_verif_vente_site_org"),
        ForeignKeyConstraint(["beneficiaire_id", "organisation_id"], ["tiers_payant_beneficiaires.id", "tiers_payant_beneficiaires.organisation_id"], name="fk_tp_verif_benef_org"),
        ForeignKeyConstraint(["auteur_id", "organisation_id"], ["utilisateurs.id_utilisateur", "utilisateurs.organisation_id"], name="fk_tp_verif_auteur_org"),
        CheckConstraint("revision_adhesion > 0", name="ck_tp_verif_revision"),
        CheckConstraint("resultat IN ('CONFIRME','REFUSE')", name="ck_tp_verif_resultat"),
        CheckConstraint("source IN ('LISTE','IDENTIFICATION','EXTERNE')", name="ck_tp_verif_source"),
        CheckConstraint("date_fin >= date_verification", name="ck_tp_verif_periode"),
        Index("ix_tp_verif_benef_adhesion", "organisation_id", "beneficiaire_id", "adhesion_id", "cree_le"),
    )
    vente_id: Mapped[UUID] = mapped_column(Uuid)
    site_id: Mapped[UUID] = mapped_column(Uuid)
    configuration_id: Mapped[UUID] = mapped_column(Uuid)
    convention_id: Mapped[UUID] = mapped_column(Uuid)
    adhesion_id: Mapped[UUID] = mapped_column(Uuid)
    beneficiaire_id: Mapped[UUID] = mapped_column(Uuid)
    revision_adhesion: Mapped[int] = mapped_column()
    source: Mapped[str] = mapped_column(String(20))
    reference: Mapped[str] = mapped_column(String(200))
    resultat: Mapped[str] = mapped_column(String(20))
    motif: Mapped[str] = mapped_column(String(1000))
    date_verification: Mapped[date] = mapped_column(Date)
    date_fin: Mapped[date] = mapped_column(Date)
    valeurs: Mapped[dict] = mapped_column(JSON)
    documents: Mapped[list] = mapped_column(JSON)
    auteur_id: Mapped[UUID] = mapped_column(Uuid)
    cree_le: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)

for _model in (ConventionOrganismeModel, PrioriteOrganismeModel, EvenementTiersPayantModel, ConfigurationConventionModel, VerificationConventionModel):
    _table = _model.__tablename__
    for action in ("UPDATE", "DELETE"):
        event.listen(
            _model.__table__, "after_create",
            DDL(f"CREATE TRIGGER {_table}_{action.lower()}_immutable BEFORE {action} ON {_table} BEGIN SELECT RAISE(ABORT, 'Référentiel Tiers Payant versionné immuable'); END").execute_if(dialect="sqlite"),
        )
    event.listen(
        _model.__table__, "after_create",
        DDL(f"CREATE OR REPLACE FUNCTION {_table}_immutable() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN RAISE EXCEPTION 'Référentiel Tiers Payant versionné immuable'; END $$").execute_if(dialect="postgresql"),
    )
    event.listen(
        _model.__table__, "after_create",
        DDL(f"CREATE TRIGGER {_table}_immutable BEFORE UPDATE OR DELETE ON {_table} FOR EACH ROW EXECUTE FUNCTION {_table}_immutable()").execute_if(dialect="postgresql"),
    )
