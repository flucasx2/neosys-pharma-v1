"""Contrat proforma : offre datée, versions historiques, aucune opération financière."""
from dataclasses import dataclass
from datetime import date,timedelta
from uuid import UUID

@dataclass(frozen=True)
class Proforma:
    id:UUID
    reference:str
    site_id:UUID

@dataclass(frozen=True)
class VersionProforma:
    proforma_id:UUID
    numero:int
    etat:str
    revision:int

@dataclass(frozen=True)
class LigneProforma:
    produit_id:UUID
    conditionnement_id:UUID
    quantite:int

    def __post_init__(self):
        if type(self.quantite) is not int or self.quantite<=0:raise ValueError('Quantité entière positive requise.')

def validite(jour:date,duree:int):
    if type(duree) is not int or not 1<=duree<=3650:raise ValueError('Durée de validité comprise entre 1 et 3650 jours.')
    return jour+timedelta(days=duree)
