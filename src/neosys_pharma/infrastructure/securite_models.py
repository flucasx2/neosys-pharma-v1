from datetime import date
from uuid import UUID

from sqlalchemy import CheckConstraint, Computed, Date, ForeignKey, ForeignKeyConstraint, String, UniqueConstraint, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from neosys_pharma.infrastructure.database import Base


class UtilisateurModel(Base):
    __tablename__ = "utilisateurs"
    __table_args__ = (
        UniqueConstraint("organisation_id", "identifiant", name="uq_utilisateur_identifiant"),
        UniqueConstraint("id_utilisateur", "organisation_id", name="uq_utilisateur_organisation"),
    )
    id_utilisateur: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    organisation_id: Mapped[UUID] = mapped_column(ForeignKey("organisations.id_organisation"), index=True)
    identifiant: Mapped[str] = mapped_column(String(80))
    nom: Mapped[str] = mapped_column(String(200))
    email: Mapped[str | None] = mapped_column(String(254))
    actif: Mapped[bool] = mapped_column(default=True)


class AffectationSiteModel(Base):
    __tablename__ = "affectations_site"
    __table_args__ = (
        ForeignKeyConstraint(["utilisateur_id", "organisation_id"], ["utilisateurs.id_utilisateur", "utilisateurs.organisation_id"], name="fk_affectation_utilisateur_organisation"),
        ForeignKeyConstraint(["site_id", "organisation_id"], ["sites.id_site", "sites.organisation_id"], name="fk_affectation_site_organisation"),
        UniqueConstraint("utilisateur_id", "site_id", "date_debut", name="uq_affectation_site_debut"),
        UniqueConstraint("id_affectation_site", "site_id", name="uq_affectation_site_parent"),
        UniqueConstraint("id_affectation_site", "organisation_id", name="uq_affectation_organisation"),
        CheckConstraint("date_fin IS NULL OR date_fin >= date_debut", name="ck_affectation_periode"),
    )
    id_affectation_site: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    utilisateur_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    site_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    organisation_id: Mapped[UUID] = mapped_column(Uuid)
    date_debut: Mapped[date] = mapped_column(Date)
    date_fin: Mapped[date | None] = mapped_column(Date)
    actif: Mapped[bool] = mapped_column(default=True)


class AffectationEmplacementModel(Base):
    __tablename__ = "affectations_emplacement"
    __table_args__ = (
        ForeignKeyConstraint(["affectation_site_id", "site_id"], ["affectations_site.id_affectation_site", "affectations_site.site_id"], name="fk_emplacement_affectation_site"),
        ForeignKeyConstraint(["emplacement_id", "site_id"], ["emplacements.id_emplacement", "emplacements.site_id"], name="fk_emplacement_meme_site"),
    )
    affectation_site_id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    emplacement_id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    site_id: Mapped[UUID] = mapped_column(Uuid)


class RoleModel(Base):
    __tablename__ = "roles"
    __table_args__ = (
        CheckConstraint("(type_role = 'SYSTEME' AND organisation_id IS NULL) OR (type_role = 'PERSONNALISE' AND organisation_id IS NOT NULL)", name="ck_role_portee"),
        UniqueConstraint("scope_id", "code", name="uq_role_scope_code"),
        UniqueConstraint("id_role", "scope_id", name="uq_role_scope"),
    )
    id_role: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    organisation_id: Mapped[UUID | None] = mapped_column(ForeignKey("organisations.id_organisation"), index=True)
    scope_id: Mapped[str] = mapped_column(String(40), Computed("CASE WHEN organisation_id IS NULL THEN 'systeme' ELSE CAST(organisation_id AS VARCHAR) END", persisted=True))
    code: Mapped[str] = mapped_column(String(80))
    nom: Mapped[str] = mapped_column(String(200))
    type_role: Mapped[str] = mapped_column(String(20))
    actif: Mapped[bool] = mapped_column(default=True)


class PermissionModel(Base):
    __tablename__ = "permissions"
    id_permission: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    code: Mapped[str] = mapped_column(String(120), unique=True)
    nom: Mapped[str] = mapped_column(String(200))


class AffectationRoleModel(Base):
    __tablename__ = "affectations_role"
    __table_args__ = (
        ForeignKeyConstraint(["affectation_site_id", "organisation_id"], ["affectations_site.id_affectation_site", "affectations_site.organisation_id"], name="fk_role_affectation_organisation"),
        ForeignKeyConstraint(["role_id", "role_scope"], ["roles.id_role", "roles.scope_id"], name="fk_affectation_role_scope"),
        CheckConstraint("role_scope = 'systeme' OR role_scope = CAST(organisation_id AS VARCHAR)", name="ck_affectation_role_organisation"),
    )
    affectation_site_id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    role_id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    organisation_id: Mapped[UUID] = mapped_column(Uuid)
    role_scope: Mapped[str] = mapped_column(String(40))


class RolePermissionModel(Base):
    __tablename__ = "roles_permissions"
    role_id: Mapped[UUID] = mapped_column(ForeignKey("roles.id_role"), primary_key=True)
    permission_id: Mapped[UUID] = mapped_column(ForeignKey("permissions.id_permission"), primary_key=True)
