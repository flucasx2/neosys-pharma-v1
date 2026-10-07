from typing import Protocol
from uuid import UUID

from neosys_pharma.domain.organisation.entities import Emplacement, Site
from neosys_pharma.domain.organisation.equipements import Caisse, Coffre, PosteVente


class EquipementRepository(Protocol):
    def emplacement(self, identifiant: UUID) -> Emplacement | None: ...
    def site(self, identifiant: UUID) -> Site | None: ...
    def ajouter(self, entite: PosteVente | Caisse | Coffre) -> None: ...
    def enregistrer(self) -> None: ...


class EquipementService:
    def __init__(self, repository: EquipementRepository):
        self.repository = repository

    def creer(self, equipement: PosteVente | Caisse | Coffre):
        if isinstance(equipement, Coffre):
            if self.repository.site(equipement.site_id) is None:
                raise LookupError("Site introuvable.")
        elif self.repository.emplacement(equipement.emplacement_id) is None:
            raise LookupError("Emplacement introuvable.")
        self.repository.ajouter(equipement)
        self.repository.enregistrer()
        return equipement
