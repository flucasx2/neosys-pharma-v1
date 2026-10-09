"""Invariants P3 indépendants du transport HTTP et de la persistance."""
from datetime import date
from enum import StrEnum

class TypeMouvement(StrEnum):
    ENTREE='ENTREE'
    SORTIE='SORTIE'
    AJUSTEMENT='AJUSTEMENT'
    CORRECTION='CORRECTION'
    RESERVATION='RESERVATION'
    LIBERATION='LIBERATION'
    CONSOMMATION='CONSOMMATION'
    TRANSFERT_SORTIE='TRANSFERT_SORTIE'
    TRANSFERT_ENTREE='TRANSFERT_ENTREE'
    EXPEDITION='EXPEDITION'
    RECEPTION='RECEPTION'
    AJUSTEMENT_INVENTAIRE='AJUSTEMENT_INVENTAIRE'

class ConflitStock(ValueError):
    pass


def quantite(value, *, signee=False):
    if isinstance(value,bool) or not isinstance(value,int) or abs(value)>1_000_000_000 or (value==0 if signee else value<=0):
        raise ValueError('Quantité entière '+('non nulle' if signee else 'strictement positive')+' requise (maximum 1 milliard).')
    return value


def verifier_stock(physique, reserve):
    if reserve<0 or physique<reserve:
        raise ConflitStock('Stock insuffisant : physique ≥ réservé ≥ 0 requis.')
    return physique-reserve


def perime(peremption: date | None, jour: date):
    # La date de péremption est inclusive, sans comparaison d'heures/timezones.
    return peremption is not None and peremption<jour


def ordre_fefo(lot):
    return (lot.peremption or date.max,str(lot.id))


def ecart_inventaire(snapshot, mouvements_avant_comptage, compte):
    return compte-(snapshot+mouvements_avant_comptage)
