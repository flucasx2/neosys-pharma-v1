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
    gestion_lot: Mapped[bool] = mapped_column(default=False)
    gestion_peremption: Mapped[bool] = mapped_column(default=False)
    fefo: Mapped[bool] = mapped_column(default=False)
    promotion_autorisee: Mapped[bool] = mapped_column(default=False)
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
        ForeignKeyConstraint(["nature_id", "organisation_id"], ["catalogue_natures.id_nature", "catalogue_natures.organisation_id"], name="fk_produit_nature_org"),
        ForeignKeyConstraint(["mode_delivrance_id", "organisation_id"], ["catalogue_modes.id_mode", "catalogue_modes.organisation_id"], name="fk_produit_mode_org"),
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
    nature_id: Mapped[UUID | None] = mapped_column(Uuid)
    mode_delivrance_id: Mapped[UUID | None] = mapped_column(Uuid)
    regime_tva_code: Mapped[str | None] = mapped_column(String(80))
    gestion_lot: Mapped[bool | None] = mapped_column()
    gestion_peremption: Mapped[bool | None] = mapped_column()
    fefo: Mapped[bool | None] = mapped_column()
    promotion_autorisee: Mapped[bool | None] = mapped_column()
    description: Mapped[str | None] = mapped_column(String(2000))
    actif: Mapped[bool] = mapped_column(default=True)


class ConditionnementModel(Base):
    __tablename__ = "catalogue_conditionnements"
    __table_args__ = (
        UniqueConstraint("id_conditionnement", "produit_id", "organisation_id", name="uq_conditionnement_produit_parent"),
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


class NatureMedicamentModel(Base):
    __tablename__ = "catalogue_natures"
    __table_args__ = (UniqueConstraint("id_nature", "organisation_id", name="uq_nature_parent"), UniqueConstraint("organisation_id", "code", name="uq_nature_code"))
    id_nature: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    organisation_id: Mapped[UUID] = mapped_column(ForeignKey("organisations.id_organisation"), index=True)
    code: Mapped[str] = mapped_column(String(80))
    nom: Mapped[str] = mapped_column(String(200))
    actif: Mapped[bool] = mapped_column(default=True)


class PrincipeActifModel(Base):
    __tablename__ = "catalogue_principes"
    __table_args__ = (UniqueConstraint("id_principe", "organisation_id", name="uq_principe_parent"), UniqueConstraint("organisation_id", "code", name="uq_principe_code"))
    id_principe: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    organisation_id: Mapped[UUID] = mapped_column(ForeignKey("organisations.id_organisation"), index=True)
    code: Mapped[str] = mapped_column(String(80))
    nom: Mapped[str] = mapped_column(String(200))
    actif: Mapped[bool] = mapped_column(default=True)


class ClasseTherapeutiqueModel(Base):
    __tablename__ = "catalogue_classes"
    __table_args__ = (UniqueConstraint("id_classe", "organisation_id", name="uq_classe_parent"), UniqueConstraint("organisation_id", "code", name="uq_classe_code"))
    id_classe: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    organisation_id: Mapped[UUID] = mapped_column(ForeignKey("organisations.id_organisation"), index=True)
    code: Mapped[str] = mapped_column(String(80))
    nom: Mapped[str] = mapped_column(String(200))
    actif: Mapped[bool] = mapped_column(default=True)


class GroupeSubstitutionModel(Base):
    __tablename__ = "catalogue_groupes"
    __table_args__ = (UniqueConstraint("id_groupe", "organisation_id", name="uq_groupe_parent"), UniqueConstraint("organisation_id", "code", name="uq_groupe_code"))
    id_groupe: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    organisation_id: Mapped[UUID] = mapped_column(ForeignKey("organisations.id_organisation"), index=True)
    code: Mapped[str] = mapped_column(String(80))
    nom: Mapped[str] = mapped_column(String(200))
    actif: Mapped[bool] = mapped_column(default=True)


class ModeDelivranceModel(Base):
    __tablename__ = "catalogue_modes"
    __table_args__ = (UniqueConstraint("id_mode", "organisation_id", name="uq_mode_parent"), UniqueConstraint("organisation_id", "code", name="uq_mode_code"))
    id_mode: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    organisation_id: Mapped[UUID] = mapped_column(ForeignKey("organisations.id_organisation"), index=True)
    code: Mapped[str] = mapped_column(String(80))
    nom: Mapped[str] = mapped_column(String(200))
    actif: Mapped[bool] = mapped_column(default=True)


class CompositionProduitModel(Base):
    __tablename__ = "catalogue_compositions"
    __table_args__ = (
        UniqueConstraint("produit_id", "principe_id", name="uq_composition_association"),
        ForeignKeyConstraint(["produit_id", "organisation_id"], ["catalogue_produits.id_produit", "catalogue_produits.organisation_id"], name="fk_composition_produit_org"),
        ForeignKeyConstraint(["principe_id", "organisation_id"], ["catalogue_principes.id_principe", "catalogue_principes.organisation_id"], name="fk_composition_principe_org"),
    )
    id_composition: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    organisation_id: Mapped[UUID] = mapped_column(ForeignKey("organisations.id_organisation"), index=True)
    produit_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    principe_id: Mapped[UUID] = mapped_column(Uuid)
    actif: Mapped[bool] = mapped_column(default=True)
    dosage: Mapped[str | None] = mapped_column(String(200))


class ClassificationProduitModel(Base):
    __tablename__ = "catalogue_classifications"
    __table_args__ = (
        UniqueConstraint("produit_id", "classe_id", name="uq_classification_association"),
        ForeignKeyConstraint(["produit_id", "organisation_id"], ["catalogue_produits.id_produit", "catalogue_produits.organisation_id"], name="fk_classification_produit_org"),
        ForeignKeyConstraint(["classe_id", "organisation_id"], ["catalogue_classes.id_classe", "catalogue_classes.organisation_id"], name="fk_classification_classe_org"),
    )
    id_classification: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    organisation_id: Mapped[UUID] = mapped_column(ForeignKey("organisations.id_organisation"), index=True)
    produit_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    classe_id: Mapped[UUID] = mapped_column(Uuid)
    actif: Mapped[bool] = mapped_column(default=True)


class SubstitutionProduitModel(Base):
    __tablename__ = "catalogue_substitutions"
    __table_args__ = (
        UniqueConstraint("produit_id", "groupe_id", name="uq_substitution_association"),
        ForeignKeyConstraint(["produit_id", "organisation_id"], ["catalogue_produits.id_produit", "catalogue_produits.organisation_id"], name="fk_substitution_produit_org"),
        ForeignKeyConstraint(["groupe_id", "organisation_id"], ["catalogue_groupes.id_groupe", "catalogue_groupes.organisation_id"], name="fk_substitution_groupe_org"),
    )
    id_substitution: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    organisation_id: Mapped[UUID] = mapped_column(ForeignKey("organisations.id_organisation"), index=True)
    produit_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    groupe_id: Mapped[UUID] = mapped_column(Uuid)
    actif: Mapped[bool] = mapped_column(default=True)
