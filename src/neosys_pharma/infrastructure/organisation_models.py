from uuid import UUID

from sqlalchemy import ForeignKey, String, UniqueConstraint, Uuid, Index
from sqlalchemy.orm import Mapped, mapped_column

from neosys_pharma.infrastructure.database import Base


class OrganisationModel(Base):
    __tablename__ = "organisations"
    id_organisation: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    nom_commercial: Mapped[str] = mapped_column(String(200))
    raison_sociale: Mapped[str] = mapped_column(String(200))
    logo: Mapped[str | None] = mapped_column(String(1000))
    coordonnees: Mapped[str | None] = mapped_column(String(2000))
    informations_legales: Mapped[str | None] = mapped_column(String(2000))
    actif: Mapped[bool] = mapped_column(default=True)


class SiteModel(Base):
    __tablename__ = "sites"
    __table_args__ = (UniqueConstraint("organisation_id", "code", name="uq_site_organisation_code"),
                      UniqueConstraint("id_site", "organisation_id", name="uq_site_organisation_parent"))
    id_site: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    organisation_id: Mapped[UUID] = mapped_column(ForeignKey("organisations.id_organisation"), index=True)
    code: Mapped[str] = mapped_column(String(80))
    nom: Mapped[str] = mapped_column(String(200))
    adresse: Mapped[str | None] = mapped_column(String(1000))
    telephone: Mapped[str | None] = mapped_column(String(80))
    email: Mapped[str | None] = mapped_column(String(254))
    actif: Mapped[bool] = mapped_column(default=True)


class EmplacementModel(Base):
    __tablename__ = "emplacements"
    __table_args__ = (UniqueConstraint("site_id", "code", name="uq_emplacement_site_code"),
                      UniqueConstraint("id_emplacement", "site_id", name="uq_emplacement_site_parent"))
    id_emplacement: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    site_id: Mapped[UUID] = mapped_column(ForeignKey("sites.id_site"), index=True)
    code: Mapped[str] = mapped_column(String(80))
    nom: Mapped[str] = mapped_column(String(200))
    actif: Mapped[bool] = mapped_column(default=True)


class PosteVenteModel(Base):
    __tablename__ = "postes_vente"
    __table_args__ = (UniqueConstraint("emplacement_id", "code", name="uq_poste_emplacement_code"), Index("uq_poste_id_emplacement", "id_poste_vente", "emplacement_id", unique=True),)
    id_poste_vente: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    emplacement_id: Mapped[UUID] = mapped_column(ForeignKey("emplacements.id_emplacement"), index=True)
    code: Mapped[str] = mapped_column(String(80))
    nom: Mapped[str] = mapped_column(String(200))
    actif: Mapped[bool] = mapped_column(default=True)


class CaisseModel(Base):
    __tablename__ = "caisses"
    __table_args__ = (UniqueConstraint("emplacement_id", "code", name="uq_caisse_emplacement_code"), Index("uq_caisse_id_emplacement", "id_caisse", "emplacement_id", unique=True),)
    id_caisse: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    emplacement_id: Mapped[UUID] = mapped_column(ForeignKey("emplacements.id_emplacement"), index=True)
    code: Mapped[str] = mapped_column(String(80))
    nom: Mapped[str] = mapped_column(String(200))
    actif: Mapped[bool] = mapped_column(default=True)


class CoffreModel(Base):
    __tablename__ = "coffres"
    __table_args__ = (UniqueConstraint("site_id", "code", name="uq_coffre_site_code"),)
    id_coffre: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    site_id: Mapped[UUID] = mapped_column(ForeignKey("sites.id_site"), index=True)
    code: Mapped[str] = mapped_column(String(80))
    nom: Mapped[str] = mapped_column(String(200))
    actif: Mapped[bool] = mapped_column(default=True)
