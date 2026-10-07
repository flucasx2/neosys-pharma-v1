"""Les FK composées protègent aussi les écritures SQL inter-organisations."""
from uuid import UUID
from sqlalchemy import CheckConstraint, ForeignKey, ForeignKeyConstraint, String, UniqueConstraint, Uuid
from sqlalchemy.orm import Mapped, mapped_column
from neosys_pharma.infrastructure.database import Base


class CategorieProduitModel(Base):
    __tablename__ = "catalogue_categories"
    __table_args__ = (
        UniqueConstraint("id_categorie", "organisation_id", name="uq_categorie_parent"),
        UniqueConstraint("organisation_id", "code", name="uq_categorie_code"),
        ForeignKeyConstraint(["parent_id", "organisation_id"], ["catalogue_categories.id_categorie", "catalogue_categories.organisation_id"], name="fk_categorie_parent_org"),
        CheckConstraint("parent_id IS NULL OR parent_id <> id_categorie", name="ck_categorie_parent"),
    )
    id_categorie: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    organisation_id: Mapped[UUID] = mapped_column(ForeignKey("organisations.id_organisation"), index=True)
    parent_id: Mapped[UUID | None] = mapped_column(Uuid)
    code: Mapped[str] = mapped_column(String(80))
    nom: Mapped[str] = mapped_column(String(200))
    actif: Mapped[bool] = mapped_column(default=True)


class FormePharmaceutiqueModel(Base):
    __tablename__ = "catalogue_formes"
    __table_args__ = (UniqueConstraint("id_forme", "organisation_id", name="uq_forme_parent"), UniqueConstraint("organisation_id", "code", name="uq_forme_code"))
    id_forme: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    organisation_id: Mapped[UUID] = mapped_column(ForeignKey("organisations.id_organisation"), index=True)
    code: Mapped[str] = mapped_column(String(80))
    nom: Mapped[str] = mapped_column(String(200))
    actif: Mapped[bool] = mapped_column(default=True)


class LaboratoireModel(Base):
    __tablename__ = "catalogue_laboratoires"
    __table_args__ = (UniqueConstraint("id_laboratoire", "organisation_id", name="uq_laboratoire_parent"), UniqueConstraint("organisation_id", "code", name="uq_laboratoire_code"))
    id_laboratoire: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    organisation_id: Mapped[UUID] = mapped_column(ForeignKey("organisations.id_organisation"), index=True)
    code: Mapped[str] = mapped_column(String(80))
    nom: Mapped[str] = mapped_column(String(200))
    actif: Mapped[bool] = mapped_column(default=True)


class ProduitModel(Base):
    __tablename__ = "catalogue_produits"
    __table_args__ = (
        UniqueConstraint("id_produit", "organisation_id", name="uq_produit_parent"),
        ForeignKeyConstraint(["categorie_id", "organisation_id"], ["catalogue_categories.id_categorie", "catalogue_categories.organisation_id"], name="fk_produit_categorie_org"),
        ForeignKeyConstraint(["forme_id", "organisation_id"], ["catalogue_formes.id_forme", "catalogue_formes.organisation_id"], name="fk_produit_forme_org"),
        ForeignKeyConstraint(["laboratoire_id", "organisation_id"], ["catalogue_laboratoires.id_laboratoire", "catalogue_laboratoires.organisation_id"], name="fk_produit_laboratoire_org"),
    )
    id_produit: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    organisation_id: Mapped[UUID] = mapped_column(ForeignKey("organisations.id_organisation"), index=True)
    categorie_id: Mapped[UUID] = mapped_column(Uuid)
    forme_id: Mapped[UUID | None] = mapped_column(Uuid)
    laboratoire_id: Mapped[UUID | None] = mapped_column(Uuid)
    nom: Mapped[str] = mapped_column(String(200))
    description: Mapped[str | None] = mapped_column(String(2000))
    actif: Mapped[bool] = mapped_column(default=True)


class ConditionnementModel(Base):
    __tablename__ = "catalogue_conditionnements"
    __table_args__ = (
        UniqueConstraint("id_conditionnement", "organisation_id", name="uq_conditionnement_parent"),
        UniqueConstraint("produit_id", "code", name="uq_conditionnement_code"),
        ForeignKeyConstraint(["produit_id", "organisation_id"], ["catalogue_produits.id_produit", "catalogue_produits.organisation_id"], name="fk_conditionnement_produit_org"),
    )
    id_conditionnement: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    organisation_id: Mapped[UUID] = mapped_column(ForeignKey("organisations.id_organisation"), index=True)
    produit_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    code: Mapped[str] = mapped_column(String(80))
    libelle: Mapped[str] = mapped_column(String(200))
    actif: Mapped[bool] = mapped_column(default=True)


class ReferenceProduitModel(Base):
    __tablename__ = "catalogue_references"
    __table_args__ = (
        UniqueConstraint("organisation_id", "type_reference", "valeur", name="uq_reference_org_type_valeur"),
        ForeignKeyConstraint(["conditionnement_id", "organisation_id"], ["catalogue_conditionnements.id_conditionnement", "catalogue_conditionnements.organisation_id"], name="fk_reference_conditionnement_org"),
        CheckConstraint("type_reference IN ('CIP7','CIP13','EAN','GTIN','HISTORIQUE')", name="ck_reference_type"),
    )
    id_reference: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    organisation_id: Mapped[UUID] = mapped_column(ForeignKey("organisations.id_organisation"), index=True)
    conditionnement_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    type_reference: Mapped[str] = mapped_column(String(20))
    valeur: Mapped[str] = mapped_column(String(200))
    actif: Mapped[bool] = mapped_column(default=True)
