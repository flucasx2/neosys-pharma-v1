from typing import Protocol
from uuid import UUID

from neosys_pharma.domain.organisation.entities import Emplacement, Organisation, Site


class OrganisationRepository(Protocol):
    def organisation(self, identifiant: UUID) -> Organisation | None: ...
    def site(self, identifiant: UUID) -> Site | None: ...
    def ajouter(self, entite: Organisation | Site | Emplacement) -> None: ...
    def enregistrer(self) -> None: ...


class OrganisationService:
    def __init__(self, repository: OrganisationRepository):
        self.repository = repository

    def creer_organisation(self, organisation: Organisation, site: Site, emplacement: Emplacement) -> Organisation:
        if site.organisation_id != organisation.id_organisation or emplacement.site_id != site.id_site:
            raise ValueError("La hiérarchie organisation/site/emplacement est incohérente.")
        for entite in (organisation, site, emplacement):
            self.repository.ajouter(entite)
        self.repository.enregistrer()
        return organisation

    def creer_site(self, site: Site, emplacement: Emplacement) -> Site:
        organisation = self.repository.organisation(site.organisation_id)
        if organisation is None:
            raise LookupError("Organisation introuvable.")
        if emplacement.site_id != site.id_site:
            raise ValueError("L'emplacement doit appartenir au site.")
        self.repository.ajouter(site)
        self.repository.ajouter(emplacement)
        self.repository.enregistrer()
        return site

    def creer_emplacement(self, emplacement: Emplacement) -> Emplacement:
        site = self.repository.site(emplacement.site_id)
        if site is None:
            raise LookupError("Site introuvable.")
        self.repository.ajouter(emplacement)
        self.repository.enregistrer()
        return emplacement
