from dataclasses import asdict, replace
from datetime import date
from typing import Protocol
from uuid import UUID

from neosys_pharma.domain.organisation.entities import Organisation, Site, Emplacement
from neosys_pharma.domain.organisation.securite import (
    AffectationEmplacement, AffectationRole, AffectationSite, DroitsAffectation,
    Permission, Role, RolePermission, TypeRole, Utilisateur,
)


class SecuriteRepository(Protocol):
    def organisation(self, identifiant: UUID) -> Organisation | None: ...
    def site(self, identifiant: UUID) -> Site | None: ...
    def emplacement(self, identifiant: UUID) -> Emplacement | None: ...
    def utilisateur(self, identifiant: UUID) -> Utilisateur | None: ...
    def affectation(self, identifiant: UUID) -> AffectationSite | None: ...
    def role(self, identifiant: UUID) -> Role | None: ...
    def permission(self, identifiant: UUID) -> Permission | None: ...
    def utilisateurs(self, organisation_id: UUID) -> list[Utilisateur]: ...
    def roles(self, organisation_id: UUID) -> list[Role]: ...
    def permissions(self) -> list[Permission]: ...
    def affectations(self, utilisateur_id: UUID) -> list[AffectationSite]: ...
    def roles_affectation(self, identifiant: UUID) -> list[Role]: ...
    def emplacements_affectation(self, identifiant: UUID) -> list[Emplacement]: ...
    def permissions_role(self, identifiant: UUID) -> list[Permission]: ...
    def ajouter(self, entite) -> None: ...
    def enregistrer(self) -> None: ...
    def mettre_a_jour(self, entite) -> None: ...
    def remplacer_liens(self, classe, parent_champ: str, parent_id: UUID, liens: list) -> None: ...


def obligatoire(entite, nom):
    if entite is None:
        raise LookupError(f"{nom} introuvable.")
    return entite


class SecuriteService:
    def __init__(self, repository: SecuriteRepository):
        self.repo = repository

    def creer_utilisateur(self, utilisateur: Utilisateur) -> Utilisateur:
        obligatoire(self.repo.organisation(utilisateur.organisation_id), "Organisation")
        self.repo.ajouter(utilisateur)
        self.repo.enregistrer()
        return utilisateur

    def creer_affectation(self, affectation: AffectationSite) -> AffectationSite:
        utilisateur = obligatoire(self.repo.utilisateur(affectation.utilisateur_id), "Utilisateur")
        site = obligatoire(self.repo.site(affectation.site_id), "Site")
        if site.organisation_id != utilisateur.organisation_id:
            raise ValueError("Le site et l'utilisateur doivent appartenir à la même organisation.")
        self.repo.ajouter(affectation)
        self.repo.enregistrer()
        return affectation

    def creer_role(self, role: Role, permission_ids: list[UUID]) -> Role:
        if role.type_role != TypeRole.PERSONNALISE:
            raise ValueError("Les rôles système sont définis par le catalogue versionné.")
        obligatoire(self.repo.organisation(role.organisation_id), "Organisation")
        permissions = [obligatoire(self.repo.permission(identifiant), "Permission") for identifiant in set(permission_ids)]
        self.repo.ajouter(role)
        for permission in permissions:
            self.repo.ajouter(RolePermission(role_id=role.id_role, permission_id=permission.id_permission))
        self.repo.enregistrer()
        return role

    def definir_permissions(self, role_id: UUID, permission_ids: list[UUID]) -> Role:
        role = obligatoire(self.repo.role(role_id), "Rôle")
        if role.type_role != TypeRole.PERSONNALISE:
            raise ValueError("Les permissions des rôles système ne sont pas modifiables ici.")
        for identifiant in set(permission_ids):
            obligatoire(self.repo.permission(identifiant), "Permission")
        liens = [RolePermission(role_id=role_id, permission_id=identifiant) for identifiant in set(permission_ids)]
        self.repo.remplacer_liens(RolePermission, "role_id", role_id, liens)
        self.repo.enregistrer()
        return role

    def definir_emplacements(self, affectation_id: UUID, emplacement_ids: list[UUID]) -> AffectationSite:
        affectation = obligatoire(self.repo.affectation(affectation_id), "Affectation")
        liens = []
        for identifiant in set(emplacement_ids):
            emplacement = obligatoire(self.repo.emplacement(identifiant), "Emplacement")
            lien = AffectationEmplacement(affectation_site_id=affectation_id, emplacement_id=identifiant)
            lien.valider_site(affectation, emplacement.site_id)
            liens.append(lien)
        self.repo.remplacer_liens(AffectationEmplacement, "affectation_site_id", affectation_id, liens)
        self.repo.enregistrer()
        return affectation

    def definir_roles(self, affectation_id: UUID, role_ids: list[UUID]) -> AffectationSite:
        affectation = obligatoire(self.repo.affectation(affectation_id), "Affectation")
        utilisateur = obligatoire(self.repo.utilisateur(affectation.utilisateur_id), "Utilisateur")
        liens = []
        for identifiant in set(role_ids):
            role = obligatoire(self.repo.role(identifiant), "Rôle")
            lien = AffectationRole(affectation_site_id=affectation_id, role_id=identifiant)
            lien.valider_organisation(role, utilisateur.organisation_id)
            liens.append(lien)
        self.repo.remplacer_liens(AffectationRole, "affectation_site_id", affectation_id, liens)
        self.repo.enregistrer()
        return affectation

    def modifier_utilisateur(self, identifiant: UUID, *, nom: str, email: str | None, actif: bool) -> Utilisateur:
        utilisateur = obligatoire(self.repo.utilisateur(identifiant), "Utilisateur")
        modifie = replace(utilisateur, nom=nom, email=email, actif=actif)
        self.repo.mettre_a_jour(modifie)
        self.repo.enregistrer()
        return modifie

    def modifier_affectation(self, identifiant: UUID, *, date_debut: date, date_fin: date | None, actif: bool) -> AffectationSite:
        affectation = obligatoire(self.repo.affectation(identifiant), "Affectation")
        modifie = replace(affectation, date_debut=date_debut, date_fin=date_fin, actif=actif)
        self.repo.mettre_a_jour(modifie)
        self.repo.enregistrer()
        return modifie

    def droits(self, utilisateur_id: UUID, site_id: UUID, jour: date) -> list[DroitsAffectation]:
        utilisateur = obligatoire(self.repo.utilisateur(utilisateur_id), "Utilisateur")
        site = obligatoire(self.repo.site(site_id), "Site")
        if utilisateur.organisation_id != site.organisation_id:
            raise ValueError("Le site et l'utilisateur doivent appartenir à la même organisation.")
        organisation = obligatoire(self.repo.organisation(utilisateur.organisation_id), "Organisation")
        if not utilisateur.actif or not site.actif or not organisation.actif:
            return []
        resultats = []
        for affectation in self.repo.affectations(utilisateur_id):
            if affectation.site_id != site_id or not affectation.effective(jour):
                continue
            codes = frozenset(permission.code for role in self.repo.roles_affectation(affectation.id_affectation_site)
                              if role.actif for permission in self.repo.permissions_role(role.id_role))
            emplacements = frozenset(emplacement.id_emplacement for emplacement in self.repo.emplacements_affectation(affectation.id_affectation_site)
                                    if emplacement.actif and emplacement.site_id == site_id)
            resultats.append(DroitsAffectation(affectation_site_id=affectation.id_affectation_site,
                                              permissions=codes, emplacements=emplacements))
        return resultats

    def autorise(self, utilisateur_id: UUID, site_id: UUID, permission: str, jour: date, emplacement_id: UUID | None = None) -> bool:
        return any(droit.autorise(permission, emplacement_id) for droit in self.droits(utilisateur_id, site_id, jour))

    def permissions_resultantes(self, utilisateur_id: UUID, site_id: UUID, jour: date) -> dict:
        droits = self.droits(utilisateur_id, site_id, jour)
        ids = set().union(*(droit.emplacements for droit in droits)) if droits else set()
        return {"utilisateur_id": utilisateur_id, "site_id": site_id, "date": jour,
                "permissions_site": sorted(set().union(*(droit.permissions for droit in droits))) if droits else [],
                "affectations_effectives": [droit.affectation_site_id for droit in droits],
                "emplacements": [{"id_emplacement": identifiant,
                                  "nom": self.repo.emplacement(identifiant).nom,
                                  "permissions": sorted(set().union(*(droit.permissions for droit in droits if identifiant in droit.emplacements)))}
                                 for identifiant in sorted(ids, key=str)]}

    def details_affectation(self, affectation: AffectationSite) -> dict:
        return {**asdict(affectation), "site_nom": self.repo.site(affectation.site_id).nom,
                "roles": [asdict(role) for role in self.repo.roles_affectation(affectation.id_affectation_site)],
                "emplacements": [asdict(emplacement) for emplacement in self.repo.emplacements_affectation(affectation.id_affectation_site)]}
