"""Identités, affectations et RBAC contextualisé ; aucun raccourci de privilège."""
from dataclasses import dataclass, field
from datetime import date
from enum import StrEnum
from uuid import UUID, uuid4


def uuid_obligatoire(value: UUID, label: str) -> None:
    if not isinstance(value, UUID):
        raise ValueError(f"{label} est obligatoire.")


def texte_obligatoire(value: str, label: str) -> str:
    value = value.strip()
    if not value:
        raise ValueError(f"{label} est obligatoire.")
    return value


@dataclass(kw_only=True)
class Utilisateur:
    organisation_id: UUID
    identifiant: str
    nom: str
    email: str | None = None
    actif: bool = True
    id_utilisateur: UUID = field(default_factory=uuid4)

    def __post_init__(self) -> None:
        uuid_obligatoire(self.organisation_id, "L'organisation")
        self.identifiant = texte_obligatoire(self.identifiant, "L'identifiant").lower()
        self.nom = texte_obligatoire(self.nom, "Le nom")


@dataclass(kw_only=True)
class AffectationSite:
    utilisateur_id: UUID
    site_id: UUID
    date_debut: date
    date_fin: date | None = None
    actif: bool = True
    id_affectation_site: UUID = field(default_factory=uuid4)

    def __post_init__(self) -> None:
        uuid_obligatoire(self.utilisateur_id, "L'utilisateur")
        uuid_obligatoire(self.site_id, "Le site")
        if self.date_fin is not None and self.date_fin < self.date_debut:
            raise ValueError("La fin de période précède son début.")

    def effective(self, jour: date) -> bool:
        return self.actif and self.date_debut <= jour and (self.date_fin is None or jour <= self.date_fin)


@dataclass(frozen=True, kw_only=True)
class AffectationEmplacement:
    affectation_site_id: UUID
    emplacement_id: UUID

    def valider_site(self, affectation: AffectationSite, emplacement_site_id: UUID) -> None:
        if self.affectation_site_id != affectation.id_affectation_site or affectation.site_id != emplacement_site_id:
            raise ValueError("L'emplacement doit appartenir au même site que l'affectation.")


class TypeRole(StrEnum):
    SYSTEME = "SYSTEME"
    PERSONNALISE = "PERSONNALISE"


@dataclass(kw_only=True)
class Role:
    code: str
    nom: str
    type_role: TypeRole
    organisation_id: UUID | None = None
    actif: bool = True
    id_role: UUID = field(default_factory=uuid4)

    def __post_init__(self) -> None:
        self.code = texte_obligatoire(self.code, "Le code du rôle").upper()
        self.nom = texte_obligatoire(self.nom, "Le nom du rôle")
        self.type_role = TypeRole(self.type_role)
        if self.type_role == TypeRole.SYSTEME and self.organisation_id is not None:
            raise ValueError("Un rôle système n'appartient pas à une organisation.")
        if self.type_role == TypeRole.PERSONNALISE:
            uuid_obligatoire(self.organisation_id, "L'organisation du rôle personnalisé")


@dataclass(frozen=True, kw_only=True)
class Permission:
    code: str
    nom: str
    id_permission: UUID


@dataclass(frozen=True, kw_only=True)
class AffectationRole:
    affectation_site_id: UUID
    role_id: UUID

    def valider_organisation(self, role: Role, organisation_id: UUID) -> None:
        if self.role_id != role.id_role:
            raise ValueError("Rôle incohérent.")
        if role.type_role == TypeRole.PERSONNALISE and role.organisation_id != organisation_id:
            raise ValueError("Le rôle personnalisé appartient à une autre organisation.")


@dataclass(frozen=True, kw_only=True)
class RolePermission:
    role_id: UUID
    permission_id: UUID


@dataclass(frozen=True, kw_only=True)
class DroitsAffectation:
    affectation_site_id: UUID
    permissions: frozenset[str]
    emplacements: frozenset[UUID]

    def autorise(self, permission: str, emplacement_id: UUID | None = None) -> bool:
        return permission in self.permissions and (emplacement_id is None or emplacement_id in self.emplacements)
