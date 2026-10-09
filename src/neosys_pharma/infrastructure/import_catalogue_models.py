from datetime import datetime
from decimal import Decimal
from uuid import UUID
from sqlalchemy import ForeignKey, ForeignKeyConstraint, String, UniqueConstraint, Uuid, Numeric, JSON, DateTime
from sqlalchemy.orm import Mapped, mapped_column
from neosys_pharma.infrastructure.database import Base


class ImportCatalogueModel(Base):
    __tablename__ = 'catalogue_imports'
    id_import: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    organisation_id: Mapped[UUID] = mapped_column(ForeignKey('organisations.id_organisation'), index=True)
    utilisateur_id: Mapped[UUID] = mapped_column(ForeignKey('utilisateurs.id_utilisateur'))
    nom_fichier: Mapped[str] = mapped_column(String(250))
    source: Mapped[str] = mapped_column(String(200))
    empreinte: Mapped[str] = mapped_column(String(64))
    mapping: Mapped[dict] = mapped_column(JSON)
    options: Mapped[dict | None] = mapped_column(JSON)
    cree_le: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    total: Mapped[int] = mapped_column()
    __table_args__ = (UniqueConstraint('id_import','organisation_id',name='uq_import_parent'),)


class LigneImportCatalogueModel(Base):
    __tablename__ = 'catalogue_import_lignes'
    id_ligne: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    organisation_id: Mapped[UUID] = mapped_column(ForeignKey('organisations.id_organisation'), index=True)
    import_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    numero: Mapped[int] = mapped_column()
    donnees: Mapped[dict] = mapped_column(JSON)
    erreurs: Mapped[list] = mapped_column(JSON)
    statut: Mapped[str] = mapped_column(String(30))
    produit_id: Mapped[UUID | None] = mapped_column(Uuid)
    conditionnement_id: Mapped[UUID | None] = mapped_column(Uuid)
    __table_args__ = (UniqueConstraint('import_id','numero',name='uq_import_numero'),ForeignKeyConstraint(['import_id','organisation_id'],['catalogue_imports.id_import','catalogue_imports.organisation_id'],name='fk_ligne_import_org'))


class ConseilTarifSourceModel(Base):
    __tablename__ = 'catalogue_conseils_tarifs'
    id_conseil: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    organisation_id: Mapped[UUID] = mapped_column(ForeignKey('organisations.id_organisation'), index=True)
    conditionnement_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    import_id: Mapped[UUID] = mapped_column(Uuid)
    empreinte_ligne: Mapped[str] = mapped_column(String(64))
    source: Mapped[str] = mapped_column(String(200))
    cip7: Mapped[str] = mapped_column(String(7))
    dci_brute: Mapped[str | None] = mapped_column(String(2000))
    prix_achat_indicatif: Mapped[Decimal | None] = mapped_column(Numeric(16,4))
    prix_vente_conseille: Mapped[Decimal | None] = mapped_column(Numeric(16,4))
    devise: Mapped[str] = mapped_column(String(3))
    releve_le: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    __table_args__ = (UniqueConstraint('organisation_id','empreinte_ligne',name='uq_conseil_source_ligne'),ForeignKeyConstraint(['conditionnement_id','organisation_id'],['catalogue_conditionnements.id_conditionnement','catalogue_conditionnements.organisation_id'],name='fk_conseil_conditionnement_org'),ForeignKeyConstraint(['import_id','organisation_id'],['catalogue_imports.id_import','catalogue_imports.organisation_id'],name='fk_conseil_import_org'))
