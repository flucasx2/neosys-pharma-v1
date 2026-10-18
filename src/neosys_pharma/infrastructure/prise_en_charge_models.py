"""Snapshots financiers P5-B.2, append-only et sans création de créances P5-C."""
from datetime import date, datetime, timezone
from uuid import UUID, uuid4

from sqlalchemy import (CheckConstraint, Date, DateTime, ForeignKeyConstraint, Index,
                        Integer, JSON, String, UniqueConstraint, Uuid, event, DDL, text)
from sqlalchemy.orm import Mapped, mapped_column

from neosys_pharma.infrastructure.database import Base


def now():
    return datetime.now(timezone.utc)


class CalculPriseEnChargeVenteModel(Base):
    __tablename__ = "tiers_payant_calculs_vente"
    __table_args__ = (
        UniqueConstraint("id", "organisation_id", name="uq_tp_calc_org"),
        UniqueConstraint("id", "vente_id", "organisation_id", name="uq_tp_calc_vente_org"),
        UniqueConstraint("vente_id", name="uq_tp_calc_vente_unique"),
        UniqueConstraint("snapshot_hash", name="uq_tp_calc_snapshot_hash"),
        ForeignKeyConstraint(["organisation_id"], ["organisations.id_organisation"]),
        ForeignKeyConstraint(["vente_id", "organisation_id", "site_id"], ["ventes.id", "ventes.organisation_id", "ventes.site_id"], name="fk_tp_calc_vente_site_org"),
        ForeignKeyConstraint(["beneficiaire_id", "organisation_id"], ["tiers_payant_beneficiaires.id", "tiers_payant_beneficiaires.organisation_id"], name="fk_tp_calc_benef_org"),
        ForeignKeyConstraint(["parametrage_id", "organisation_id"], ["tiers_payant_parametrages_priorite.id", "tiers_payant_parametrages_priorite.organisation_id"], name="fk_tp_calc_priorite_org"),
        ForeignKeyConstraint(["auteur_id", "organisation_id"], ["utilisateurs.id_utilisateur", "utilisateurs.organisation_id"], name="fk_tp_calc_auteur_org"),
        CheckConstraint("revision_vente > 0 AND parametrage_version > 0", name="ck_tp_calc_revisions"),
        CheckConstraint("total_xaf >= 0 AND total_organismes_xaf >= 0 AND part_client_xaf >= 0", name="ck_tp_calc_montants"),
        CheckConstraint("total_xaf = total_organismes_xaf + part_client_xaf", name="ck_tp_calc_equilibre"),
        CheckConstraint("length(snapshot_hash) = 64", name="ck_tp_calc_hash_sha256"),
        Index("ix_tp_calc_org_site", "organisation_id", "site_id", "date_calcul"),
    )
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    vente_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    organisation_id: Mapped[UUID] = mapped_column(Uuid, nullable=False, index=True)
    site_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    beneficiaire_id: Mapped[UUID | None] = mapped_column(Uuid)
    date_calcul: Mapped[date] = mapped_column(Date, nullable=False)
    revision_vente: Mapped[int] = mapped_column(Integer, nullable=False)
    parametrage_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    parametrage_version: Mapped[int] = mapped_column(Integer, nullable=False)
    moteur_version: Mapped[str] = mapped_column(String(40), nullable=False)
    snapshot_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    total_xaf: Mapped[int] = mapped_column(Integer, nullable=False)
    total_organismes_xaf: Mapped[int] = mapped_column(Integer, nullable=False)
    part_client_xaf: Mapped[int] = mapped_column(Integer, nullable=False)
    snapshot: Mapped[dict] = mapped_column(JSON, nullable=False)
    auteur_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    confirme_le: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now, nullable=False)


class LigneCalculPriseEnChargeModel(Base):
    __tablename__ = "tiers_payant_calculs_lignes"
    __table_args__ = (
        UniqueConstraint("id", "organisation_id", name="uq_tp_calc_ligne_org"),
        UniqueConstraint("id", "calcul_id", "organisation_id", name="uq_tp_calc_ligne_parent_org"),
        UniqueConstraint("calcul_id", "ligne_vente_id", name="uq_tp_calc_ligne_vente"),
        ForeignKeyConstraint(["calcul_id", "vente_id", "organisation_id"], ["tiers_payant_calculs_vente.id", "tiers_payant_calculs_vente.vente_id", "tiers_payant_calculs_vente.organisation_id"], name="fk_tp_calc_ligne_entete"),
        ForeignKeyConstraint(["ligne_vente_id", "vente_id", "organisation_id"], ["vente_lignes.id", "vente_lignes.vente_id", "vente_lignes.organisation_id"], name="fk_tp_calc_ligne_vente"),
        CheckConstraint("net_xaf >= 0 AND part_client_xaf >= 0 AND total_organismes_xaf >= 0 AND net_xaf = part_client_xaf + total_organismes_xaf", name="ck_tp_calc_ligne_equilibre"),
    )
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    calcul_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    vente_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    ligne_vente_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    organisation_id: Mapped[UUID] = mapped_column(Uuid, nullable=False, index=True)
    net_xaf: Mapped[int] = mapped_column(Integer, nullable=False)
    part_client_xaf: Mapped[int] = mapped_column(Integer, nullable=False)
    total_organismes_xaf: Mapped[int] = mapped_column(Integer, nullable=False)


class PartCalculPriseEnChargeModel(Base):
    __tablename__ = "tiers_payant_calculs_parts"
    __table_args__ = (
        ForeignKeyConstraint(["ligne_calcul_id", "organisation_id"], ["tiers_payant_calculs_lignes.id", "tiers_payant_calculs_lignes.organisation_id"], name="fk_tp_calc_part_ligne_org"),
        ForeignKeyConstraint(["organisme_id", "organisation_id"], ["organismes_prise_en_charge.id", "organismes_prise_en_charge.organisation_id"], name="fk_tp_calc_part_organisme_org"),
        CheckConstraint("montant_xaf >= 0", name="ck_tp_calc_part_nonnegative"),
        CheckConstraint("(type_part = 'CLIENT' AND organisme_id IS NULL) OR (type_part = 'ORGANISME' AND organisme_id IS NOT NULL)", name="ck_tp_calc_part_type"),
        Index("uq_tp_part_client", "ligne_calcul_id", unique=True, sqlite_where=text("type_part = 'CLIENT'"), postgresql_where=text("type_part = 'CLIENT'")),
        Index("uq_tp_part_organisme", "ligne_calcul_id", "organisme_id", unique=True, sqlite_where=text("type_part = 'ORGANISME'"), postgresql_where=text("type_part = 'ORGANISME'")),
        Index("ix_tp_calc_part_ligne", "organisation_id", "ligne_calcul_id"),
    )
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    ligne_calcul_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    organisation_id: Mapped[UUID] = mapped_column(Uuid, nullable=False, index=True)
    type_part: Mapped[str] = mapped_column(String(20), nullable=False)
    organisme_id: Mapped[UUID | None] = mapped_column(Uuid)
    montant_xaf: Mapped[int] = mapped_column(Integer, nullable=False)
    rang: Mapped[int | None] = mapped_column(Integer)


class EtapeCalculPriseEnChargeModel(Base):
    __tablename__ = "tiers_payant_calculs_etapes"
    __table_args__ = (
        ForeignKeyConstraint(["ligne_calcul_id", "organisation_id"], ["tiers_payant_calculs_lignes.id", "tiers_payant_calculs_lignes.organisation_id"], name="fk_tp_calc_etape_ligne_org"),
        ForeignKeyConstraint(["convention_id", "organisation_id"], ["tiers_payant_conventions.id", "tiers_payant_conventions.organisation_id"], name="fk_tp_calc_etape_convention_org"),
        ForeignKeyConstraint(["adhesion_id", "organisation_id"], ["tiers_payant_adhesions.id", "tiers_payant_adhesions.organisation_id"], name="fk_tp_calc_etape_adhesion_org"),
        UniqueConstraint("ligne_calcul_id", "rang", name="uq_tp_calc_etape_rang"),
        ForeignKeyConstraint(["organisme_id", "organisation_id"], ["organismes_prise_en_charge.id", "organismes_prise_en_charge.organisation_id"], name="fk_tp_calc_etape_organisme_org"),
        CheckConstraint("rang > 0 AND base_initiale_xaf >= 0 AND base_eligible_xaf >= 0 AND montant_couvert_xaf >= 0 AND reste_apres_xaf >= 0", name="ck_tp_calc_etape_values"),
        Index("ix_tp_calc_etape_line", "organisation_id", "ligne_calcul_id", "rang"),
    )
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    ligne_calcul_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    organisation_id: Mapped[UUID] = mapped_column(Uuid, nullable=False, index=True)
    organisme_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    rang: Mapped[int] = mapped_column(Integer, nullable=False)
    role: Mapped[str] = mapped_column(String(20), nullable=False)
    convention_id: Mapped[UUID | None] = mapped_column(Uuid)
    convention_version: Mapped[int | None] = mapped_column(Integer)
    adhesion_id: Mapped[UUID | None] = mapped_column(Uuid)
    adhesion_revision: Mapped[int | None] = mapped_column(Integer)
    base_initiale_xaf: Mapped[int] = mapped_column(Integer, nullable=False)
    base_eligible_xaf: Mapped[int] = mapped_column(Integer, nullable=False)
    montant_couvert_xaf: Mapped[int] = mapped_column(Integer, nullable=False)
    reste_apres_xaf: Mapped[int] = mapped_column(Integer, nullable=False)
    code: Mapped[str] = mapped_column(String(80), nullable=False)
    regle_code: Mapped[str | None] = mapped_column(String(80))
    snapshot_convention: Mapped[dict] = mapped_column(JSON, nullable=False)
    snapshot_droits: Mapped[dict] = mapped_column(JSON, nullable=False)


class RealisationPriseEnChargeModel(Base):
    """Part organismes définitivement constatée lors du reçu client.

    Ce registre ne facture ni ne règle les organismes. Il constitue le point
    d'entrée immuable et transactionnel que P5-C transformera en créances.
    """
    __tablename__ = "tiers_payant_realisations"
    __table_args__ = (
        UniqueConstraint("id", "organisation_id", name="uq_tp_realisation_org"),
        UniqueConstraint("vente_id", name="uq_tp_realisation_vente"),
        UniqueConstraint("encaissement_id", name="uq_tp_realisation_encaissement"),
        UniqueConstraint("calcul_id", name="uq_tp_realisation_calcul"),
        ForeignKeyConstraint(["organisation_id"], ["organisations.id_organisation"]),
        ForeignKeyConstraint(["vente_id", "organisation_id", "site_id"],
                             ["ventes.id", "ventes.organisation_id", "ventes.site_id"],
                             name="fk_tp_realisation_vente"),
        ForeignKeyConstraint(["encaissement_id", "vente_id", "organisation_id"],
                             ["caisse_encaissements.id", "caisse_encaissements.vente_id", "caisse_encaissements.organisation_id"],
                             name="fk_tp_realisation_encaissement"),
        ForeignKeyConstraint(["calcul_id", "vente_id", "organisation_id"],
                             ["tiers_payant_calculs_vente.id", "tiers_payant_calculs_vente.vente_id", "tiers_payant_calculs_vente.organisation_id"],
                             name="fk_tp_realisation_calcul"),
        CheckConstraint("total_xaf > 0 AND total_organismes_xaf > 0 AND part_client_xaf >= 0", name="ck_tp_realisation_amounts"),
        CheckConstraint("total_xaf = total_organismes_xaf + part_client_xaf", name="ck_tp_realisation_balance"),
        Index("ix_tp_realisation_org_site", "organisation_id", "site_id", "realisee_le"),
    )
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    vente_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    encaissement_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    calcul_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    organisation_id: Mapped[UUID] = mapped_column(Uuid, nullable=False, index=True)
    site_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    total_xaf: Mapped[int] = mapped_column(Integer, nullable=False)
    total_organismes_xaf: Mapped[int] = mapped_column(Integer, nullable=False)
    part_client_xaf: Mapped[int] = mapped_column(Integer, nullable=False)
    realisee_le: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now, nullable=False)
    snapshot: Mapped[dict] = mapped_column(JSON, nullable=False)


_IMMUTABLE = (CalculPriseEnChargeVenteModel, LigneCalculPriseEnChargeModel,
              PartCalculPriseEnChargeModel, EtapeCalculPriseEnChargeModel,
              RealisationPriseEnChargeModel)
for _model in _IMMUTABLE:
    _table = _model.__tablename__
    for _action in ("UPDATE", "DELETE"):
        event.listen(_model.__table__, "after_create",
                     DDL(f"CREATE TRIGGER {_table}_{_action.lower()}_immutable BEFORE {_action} ON {_table} BEGIN SELECT RAISE(ABORT, 'Snapshot financier P5-B immuable'); END").execute_if(dialect="sqlite"))
    event.listen(_model.__table__, "after_create",
                 DDL(f"CREATE OR REPLACE FUNCTION {_table}_immutable() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN RAISE EXCEPTION 'Snapshot financier P5-B immuable'; END $$").execute_if(dialect="postgresql"))
    event.listen(_model.__table__, "after_create",
                 DDL(f"CREATE TRIGGER {_table}_immutable BEFORE UPDATE OR DELETE ON {_table} FOR EACH ROW EXECUTE FUNCTION {_table}_immutable()").execute_if(dialect="postgresql"))
