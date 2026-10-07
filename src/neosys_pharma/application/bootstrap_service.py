"""Orchestration locale : les entités restent indépendantes et les droits explicites."""
from dataclasses import dataclass
from datetime import date
from typing import Protocol
from uuid import UUID
from neosys_pharma.domain.organisation.entities import Organisation, Site, Emplacement
from neosys_pharma.domain.organisation.securite import Utilisateur, AffectationSite, AffectationEmplacement, AffectationRole, Role, TypeRole


@dataclass(frozen=True, kw_only=True)
class InstallationInitiale:
    nom_commercial: str
    raison_sociale: str
    site_code: str
    site_nom: str
    emplacement_code: str
    emplacement_nom: str
    identifiant: str
    utilisateur_nom: str


@dataclass(frozen=True)
class ConnexionInitiale:
    organisation_id: UUID
    identifiant: str
    site_code: str
    emplacement_code: str


class BootstrapRepository(Protocol):
    def verifier_base_vide(self) -> None: ...
    def role_initial(self) -> Role: ...
    def ajouter(self, entite) -> None: ...
    def definir_password(self, utilisateur_id: UUID, encoded: str) -> None: ...
    def enregistrer(self) -> None: ...
    def annuler(self) -> None: ...


class BootstrapService:
    def __init__(self, repository: BootstrapRepository, passwords):
        self.repo, self.passwords = repository, passwords

    def initialiser(self, data: InstallationInitiale, password: str, jour: date) -> ConnexionInitiale:
        try:
            self.repo.verifier_base_vide()
            role=self.repo.role_initial()
            if role.type_role != TypeRole.SYSTEME or not role.actif:
                raise ValueError('Le rôle système initial doit être actif.')
            org=Organisation(nom_commercial=data.nom_commercial,raison_sociale=data.raison_sociale)
            site=Site(organisation_id=org.id_organisation,code=data.site_code,nom=data.site_nom)
            location=Emplacement(site_id=site.id_site,code=data.emplacement_code,nom=data.emplacement_nom)
            user=Utilisateur(organisation_id=org.id_organisation,identifiant=data.identifiant,nom=data.utilisateur_nom)
            assignment=AffectationSite(utilisateur_id=user.id_utilisateur,site_id=site.id_site,date_debut=jour)
            # Validate every value and hash before the first domain write.
            encoded=self.passwords.hacher(password)
            for item in (org,site,location,user,assignment,
                         AffectationEmplacement(affectation_site_id=assignment.id_affectation_site,emplacement_id=location.id_emplacement),
                         AffectationRole(affectation_site_id=assignment.id_affectation_site,role_id=role.id_role)):
                self.repo.ajouter(item)
            self.repo.definir_password(user.id_utilisateur,encoded)
            self.repo.enregistrer()
            return ConnexionInitiale(org.id_organisation,user.identifiant,site.code,location.code)
        except Exception:
            self.repo.annuler()
            raise
