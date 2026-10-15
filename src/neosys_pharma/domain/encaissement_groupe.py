"""Modèle métier P4-C pour les dossiers d'encaissement groupé.

Les écritures financières restent par vente. Ce module valide les montants et les
ventilations sans piloter de transaction ni remplacer le circuit P4.5.
"""
from dataclasses import dataclass, replace
from decimal import Decimal
from enum import StrEnum
import re
from uuid import UUID

from neosys_pharma.domain.caisse import MODES, francs


class EtatDossierEncaissementGroupe(StrEnum):
    BROUILLON = "BROUILLON"
    FINALISE = "FINALISE"
    ABANDONNE = "ABANDONNE"


ETATS_FINAUX = frozenset({EtatDossierEncaissementGroupe.FINALISE, EtatDossierEncaissementGroupe.ABANDONNE})


def transition_dossier(source, destination):
    source = EtatDossierEncaissementGroupe(source)
    destination = EtatDossierEncaissementGroupe(destination)
    if source != EtatDossierEncaissementGroupe.BROUILLON or destination not in ETATS_FINAUX:
        raise ValueError("Un dossier ne peut être finalisé ou abandonné qu'à partir d'un brouillon.")
    return destination


@dataclass(frozen=True)
class DossierEncaissementGroupe:
    dossier_id: UUID
    organisation_id: UUID
    site_id: UUID
    session_id: UUID
    auteur_id: UUID
    etat: EtatDossierEncaissementGroupe = EtatDossierEncaissementGroupe.BROUILLON
    revision: int = 1
    cle_idempotence: str | None = None
    empreinte_requete: str | None = None

    def __post_init__(self):
        if self.revision < 1:
            raise ValueError("Révision positive requise.")
        object.__setattr__(self, "etat", EtatDossierEncaissementGroupe(self.etat))
        if (self.cle_idempotence is None) != (self.empreinte_requete is None):
            raise ValueError("La clé d’idempotence et son empreinte sont indissociables.")
        if self.cle_idempotence is not None and not self.cle_idempotence.strip():
            raise ValueError("La clé d’idempotence ne peut pas être vide.")
        if self.cle_idempotence is not None and len(self.cle_idempotence) > 200:
            raise ValueError("La clé d’idempotence dépasse 200 caractères.")
        if self.cle_idempotence is not None and not re.fullmatch(r"[0-9a-f]{64}", self.empreinte_requete):
            raise ValueError("L’empreinte de requête doit être un SHA-256 hexadécimal.")
        if self.etat == EtatDossierEncaissementGroupe.FINALISE and self.cle_idempotence is None:
            raise ValueError("Un dossier finalisé porte la clé et l’empreinte de la requête.")
        if self.etat != EtatDossierEncaissementGroupe.FINALISE and self.cle_idempotence is not None:
            raise ValueError("La clé d’idempotence de finalisation n’existe qu’après finalisation.")

    def transitionner(self, destination, *, cle_idempotence=None, empreinte_requete=None):
        destination = EtatDossierEncaissementGroupe(destination)
        if destination == EtatDossierEncaissementGroupe.FINALISE:
            if not cle_idempotence or not empreinte_requete:
                raise ValueError("La finalisation exige une clé d’idempotence et une empreinte.")
        elif cle_idempotence is not None or empreinte_requete is not None:
            raise ValueError("La clé d’idempotence n’est acceptée qu’à la finalisation.")
        return replace(
            self,
            etat=transition_dossier(self.etat, destination),
            revision=self.revision + 1,
            cle_idempotence=cle_idempotence,
            empreinte_requete=empreinte_requete,
        )


@dataclass(frozen=True)
class VenteGroupe:
    vente_id: UUID
    ordre: int
    revision: int
    montant_du: Decimal

    def __post_init__(self):
        if self.ordre < 1 or self.revision < 1:
            raise ValueError("Ordre de ticket et révision positifs requis.")
        object.__setattr__(self, "montant_du", francs(self.montant_du, zero=True))


@dataclass(frozen=True)
class ReglementGroupe:
    reglement_id: UUID
    ordre: int
    mode: str
    montant: Decimal
    rendu: Decimal = Decimal(0)
    confirmation_id: UUID | None = None

    def __post_init__(self):
        montant = francs(self.montant)
        rendu = francs(self.rendu, zero=True)
        if self.ordre < 1:
            raise ValueError("Ordre de règlement positif requis.")
        if self.mode not in MODES:
            raise ValueError("Moyen de règlement inconnu.")
        if rendu >= montant:
            raise ValueError("Le montant net d'un règlement doit être positif.")
        if self.mode == "ESPECES":
            if self.confirmation_id is not None:
                raise ValueError("Un règlement espèces ne porte pas de confirmation externe.")
        else:
            if rendu or self.confirmation_id is None:
                raise ValueError("Confirmation obligatoire et aucun rendu pour un règlement non espèces.")
        object.__setattr__(self, "montant", montant)
        object.__setattr__(self, "rendu", rendu)

    @property
    def montant_net(self):
        return self.montant - self.rendu


@dataclass(frozen=True)
class AllocationReglement:
    reglement_id: UUID
    vente_id: UUID
    montant: Decimal

    def __post_init__(self):
        object.__setattr__(self, "montant", francs(self.montant))


def _ordonner(ventes, reglements):
    sales = sorted(ventes, key=lambda row: row.ordre)
    payments = sorted(reglements, key=lambda row: row.ordre)
    if not sales:
        raise ValueError("Un dossier groupé contient au moins un ticket.")
    if len({row.vente_id for row in sales}) != len(sales) or len({row.ordre for row in sales}) != len(sales):
        raise ValueError("Tickets ou ordre des tickets dupliqués.")
    if len({row.reglement_id for row in payments}) != len(payments) or len({row.ordre for row in payments}) != len(payments):
        raise ValueError("Règlements ou ordre des règlements dupliqués.")
    due = sum((row.montant_du for row in sales), Decimal(0))
    noncash = sum((row.montant for row in payments if row.mode != "ESPECES"), Decimal(0))
    if noncash > due:
        raise ValueError("Un excédent non espèces est interdit.")
    if sum((row.montant_net for row in payments), Decimal(0)) != due:
        raise ValueError("Le net des règlements doit couvrir exactement les tickets.")
    return sales, payments


def repartir_automatiquement(ventes, reglements):
    """Ventile par ordre des tickets, puis par ordre des lignes de règlement."""
    sales, payments = _ordonner(ventes, reglements)
    restant = {sale.vente_id: sale.montant_du for sale in sales}
    allocations = []
    for payment in payments:
        disponible = payment.montant_net
        for sale in sales:
            montant = min(disponible, restant[sale.vente_id])
            if montant:
                allocations.append(AllocationReglement(payment.reglement_id, sale.vente_id, montant))
                restant[sale.vente_id] -= montant
                disponible -= montant
            if not disponible:
                break
        if disponible:
            raise ValueError("Le règlement dépasse les montants dus.")
    valider_allocations(sales, payments, allocations)
    return tuple(allocations)


def valider_allocations(ventes, reglements, allocations):
    """Valide une ventilation manuelle sans la rééquilibrer ni la corriger."""
    sales, payments = _ordonner(ventes, reglements)
    sale_ids = {row.vente_id for row in sales}
    payment_ids = {row.reglement_id for row in payments}
    allocated_by_sale = {sale_id: Decimal(0) for sale_id in sale_ids}
    allocated_by_payment = {payment_id: Decimal(0) for payment_id in payment_ids}
    pairs = set()
    for allocation in allocations:
        pair = (allocation.reglement_id, allocation.vente_id)
        if allocation.reglement_id not in payment_ids or allocation.vente_id not in sale_ids:
            raise ValueError("Allocation liée à un règlement ou ticket étranger au dossier.")
        if pair in pairs:
            raise ValueError("Une paire règlement/ticket ne peut être ventilée deux fois.")
        pairs.add(pair)
        allocated_by_sale[allocation.vente_id] += francs(allocation.montant)
        allocated_by_payment[allocation.reglement_id] += francs(allocation.montant)
    for sale in sales:
        if allocated_by_sale[sale.vente_id] != sale.montant_du:
            raise ValueError("Chaque ticket doit être couvert exactement par ses allocations.")
    for payment in payments:
        if allocated_by_payment[payment.reglement_id] != payment.montant_net:
            raise ValueError("Les allocations d'un règlement doivent égaler son montant net.")
    return True
