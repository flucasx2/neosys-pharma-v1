"""Historique tarifaire isolé par organisation et unité commerciale."""
from datetime import date
from decimal import Decimal
from uuid import UUID
from sqlalchemy import CheckConstraint, ForeignKey, ForeignKeyConstraint, String, UniqueConstraint, Uuid, Numeric, Date
from sqlalchemy.orm import Mapped, mapped_column
from neosys_pharma.infrastructure.database import Base

class RegimeTVAModel(Base):
    __tablename__ = 'tarification_tva'
    __table_args__ = (CheckConstraint('taux >= 0 AND taux <= 100', name='ck_tva_taux'), CheckConstraint('fin IS NULL OR fin >= debut', name='ck_tva_periode'))
    id_regime: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    organisation_id: Mapped[UUID] = mapped_column(ForeignKey('organisations.id_organisation'), index=True)
    code: Mapped[str] = mapped_column(String(80), index=True)
    nom: Mapped[str] = mapped_column(String(200))
    taux: Mapped[Decimal] = mapped_column(Numeric(7,4))
    debut: Mapped[date] = mapped_column(Date)
    fin: Mapped[date | None] = mapped_column(Date)


class TarifReferenceModel(Base):
    __tablename__ = "tarification_references"
    __table_args__ = (
        ForeignKeyConstraint(["conditionnement_id", "organisation_id"], ["catalogue_conditionnements.id_conditionnement", "catalogue_conditionnements.organisation_id"], name="fk_tarif_references_conditionnement_org"),
        CheckConstraint("fin IS NULL OR fin >= debut", name="ck_tarif_references_periode"),
        CheckConstraint("montant_ht IS NULL OR montant_ht >= 0", name="ck_tarif_references_montant"),
    )
    id_tarif: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    organisation_id: Mapped[UUID] = mapped_column(ForeignKey("organisations.id_organisation"), index=True)
    conditionnement_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    montant_ht: Mapped[Decimal] = mapped_column(Numeric(16,4))
    devise: Mapped[str] = mapped_column(String(3))
    debut: Mapped[date] = mapped_column(Date)
    fin: Mapped[date | None] = mapped_column(Date)
    provenance: Mapped[str | None] = mapped_column(String(500))


class ParametrageTarifSiteModel(Base):
    __tablename__ = "tarification_sites"
    __table_args__ = (
        ForeignKeyConstraint(["site_id", "organisation_id"], ["sites.id_site", "sites.organisation_id"], name="fk_tarif_sites_site"),
        CheckConstraint("fin IS NULL OR fin >= debut", name="ck_tarif_sites_periode"),
        CheckConstraint("montant_ht IS NULL OR montant_ht >= 0", name="ck_tarif_sites_montant"),
        CheckConstraint("(montant_ht IS NOT NULL AND coefficient IS NULL) OR (montant_ht IS NULL AND coefficient IS NOT NULL AND coefficient >= 0)", name="ck_tarif_sites_regle"),
    )
    id_tarif: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    organisation_id: Mapped[UUID] = mapped_column(ForeignKey("organisations.id_organisation"), index=True)
    site_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    montant_ht: Mapped[Decimal | None] = mapped_column(Numeric(16,4))
    coefficient: Mapped[Decimal | None] = mapped_column(Numeric(8,4))
    devise: Mapped[str] = mapped_column(String(3))
    debut: Mapped[date] = mapped_column(Date)
    fin: Mapped[date | None] = mapped_column(Date)
    provenance: Mapped[str | None] = mapped_column(String(500))


class TarifCategorieSiteModel(Base):
    __tablename__ = "tarification_categories"
    __table_args__ = (
        ForeignKeyConstraint(["site_id", "organisation_id"], ["sites.id_site", "sites.organisation_id"], name="fk_tarif_categories_site"),
        ForeignKeyConstraint(["categorie_id", "organisation_id"], ["catalogue_categories.id_categorie", "catalogue_categories.organisation_id"], name="fk_tarif_categories_categorie_org"),
        CheckConstraint("fin IS NULL OR fin >= debut", name="ck_tarif_categories_periode"),
        CheckConstraint("montant_ht IS NULL OR montant_ht >= 0", name="ck_tarif_categories_montant"),
        CheckConstraint("(montant_ht IS NOT NULL AND coefficient IS NULL) OR (montant_ht IS NULL AND coefficient IS NOT NULL AND coefficient >= 0)", name="ck_tarif_categories_regle"),
    )
    id_tarif: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    organisation_id: Mapped[UUID] = mapped_column(ForeignKey("organisations.id_organisation"), index=True)
    site_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    categorie_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    montant_ht: Mapped[Decimal | None] = mapped_column(Numeric(16,4))
    coefficient: Mapped[Decimal | None] = mapped_column(Numeric(8,4))
    devise: Mapped[str] = mapped_column(String(3))
    debut: Mapped[date] = mapped_column(Date)
    fin: Mapped[date | None] = mapped_column(Date)
    provenance: Mapped[str | None] = mapped_column(String(500))


class TarifProduitSiteModel(Base):
    __tablename__ = "tarification_produits"
    __table_args__ = (
        ForeignKeyConstraint(["site_id", "organisation_id"], ["sites.id_site", "sites.organisation_id"], name="fk_tarif_produits_site"),
        ForeignKeyConstraint(["produit_id", "organisation_id"], ["catalogue_produits.id_produit", "catalogue_produits.organisation_id"], name="fk_tarif_produits_produit_org"),
        ForeignKeyConstraint(["conditionnement_id", "organisation_id"], ["catalogue_conditionnements.id_conditionnement", "catalogue_conditionnements.organisation_id"], name="fk_tarif_produits_conditionnement_org"),
        ForeignKeyConstraint(["conditionnement_id", "produit_id", "organisation_id"], ["catalogue_conditionnements.id_conditionnement", "catalogue_conditionnements.produit_id", "catalogue_conditionnements.organisation_id"], name="fk_tarif_pack_produit_org"),
        CheckConstraint("fin IS NULL OR fin >= debut", name="ck_tarif_produits_periode"),
        CheckConstraint("montant_ht IS NULL OR montant_ht >= 0", name="ck_tarif_produits_montant"),
        CheckConstraint("(montant_ht IS NOT NULL AND coefficient IS NULL) OR (montant_ht IS NULL AND coefficient IS NOT NULL AND coefficient >= 0)", name="ck_tarif_produits_regle"),
    )
    id_tarif: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    organisation_id: Mapped[UUID] = mapped_column(ForeignKey("organisations.id_organisation"), index=True)
    site_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    produit_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    conditionnement_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    montant_ht: Mapped[Decimal | None] = mapped_column(Numeric(16,4))
    coefficient: Mapped[Decimal | None] = mapped_column(Numeric(8,4))
    devise: Mapped[str] = mapped_column(String(3))
    debut: Mapped[date] = mapped_column(Date)
    fin: Mapped[date | None] = mapped_column(Date)
    provenance: Mapped[str | None] = mapped_column(String(500))


# PostgreSQL enforces non-overlap even for direct SQL writes. SQLite uses the
# service invariant and organisation write lock; no vendor-specific emulation.
from sqlalchemy import event, DDL, column, func
from sqlalchemy.dialects.postgresql import ExcludeConstraint

event.listen(Base.metadata, 'before_create', DDL('CREATE EXTENSION IF NOT EXISTS btree_gist').execute_if(dialect='postgresql'))
for model, keys in (
    (RegimeTVAModel, ('organisation_id','code')),
    (TarifReferenceModel, ('organisation_id','conditionnement_id')),
    (ParametrageTarifSiteModel, ('organisation_id','site_id')),
    (TarifCategorieSiteModel, ('organisation_id','site_id','categorie_id')),
    (TarifProduitSiteModel, ('organisation_id','site_id','produit_id','conditionnement_id')),
):
    model.__table__.append_constraint(ExcludeConstraint(
        *((column(k), '=') for k in keys),
        (func.daterange(column('debut'), column('fin'), '[]'), '&&'),
        using='gist', name='ex_' + model.__tablename__ + '_periode',
    ).ddl_if(dialect='postgresql'))
