"""Contrat P4 : préparation, transmission et encaissement sont distincts."""
from dataclasses import dataclass
from decimal import Decimal
from enum import StrEnum
from uuid import UUID

class EtatVente(StrEnum):
    PREPARATION='PREPARATION'
    EN_ATTENTE='EN_ATTENTE'
    VALIDEE_PREPARATION='VALIDEE_PREPARATION'
    TRANSMISE='TRANSMISE'
    ENCAISSEE='ENCAISSEE'
    ANNULEE='ANNULEE'

class ModeVente(StrEnum):
    SANS_TIERS='SANS_TIERS'
    PRISE_EN_CHARGE='PRISE_EN_CHARGE'
    CNAMGS='CNAMGS'
    MUTUELLE='MUTUELLE'
    CNAMGS_MUTUELLE='CNAMGS_MUTUELLE'
    CREDIT='CREDIT'

TRANSITIONS={
    EtatVente.PREPARATION:{EtatVente.EN_ATTENTE,EtatVente.VALIDEE_PREPARATION,EtatVente.ANNULEE},
    EtatVente.EN_ATTENTE:{EtatVente.PREPARATION,EtatVente.ANNULEE},
    EtatVente.VALIDEE_PREPARATION:{EtatVente.PREPARATION,EtatVente.TRANSMISE,EtatVente.ANNULEE},
    EtatVente.TRANSMISE:{EtatVente.ANNULEE},
    EtatVente.ENCAISSEE:set(),EtatVente.ANNULEE:set(),
}

def transition(source,destination):
    if destination not in TRANSITIONS[EtatVente(source)]:
        raise ValueError('Transition de préparation interdite.')

@dataclass(frozen=True)
class LigneVente:
    produit_id:UUID
    conditionnement_id:UUID
    quantite:int
    tarif:dict

    def __post_init__(self):
        if type(self.quantite) is not int or self.quantite<=0:raise ValueError('Quantité commerciale positive requise.')
        if not self.tarif.get('disponible'):raise ValueError('Tarif applicable indisponible.')
        if self.tarif['devise']!='XAF':raise ValueError('Seuls les tarifs XAF sont utilisables dans cet incrément ; aucune conversion inventée.')

    def montants(self):
        # Réutiliser les montants unitaires déjà arrondis par P2, sans second moteur fiscal.
        return {k:str(Decimal(str(self.tarif['montant_'+k]))*self.quantite) for k in ('ht','tva','ttc')}

@dataclass(frozen=True)
class Vente:
    id:UUID
    organisation_id:UUID
    site_id:UUID
    emplacement_id:UUID
    poste_id:UUID
    etat:EtatVente
    mode:ModeVente


def remise_valide(type_remise,valeur):
    valeur=Decimal(str(valeur))
    if not valeur.is_finite() or valeur<=0:raise ValueError('Remise positive et finie requise.')
    if type_remise=='POURCENTAGE' and valeur>100:raise ValueError('Un pourcentage ne peut dépasser 100 %.')
    if type_remise not in ('POURCENTAGE','MONTANT_XAF'):raise ValueError('Type de remise inconnu.')
    if type_remise=='MONTANT_XAF' and valeur!=valeur.quantize(Decimal('.01')):raise ValueError('Montant : deux décimales au maximum.')
    return valeur
