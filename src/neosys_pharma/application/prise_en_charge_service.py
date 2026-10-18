"""Cas d'usage de simulation tiers payant (P5-B.1).

L'adaptateur qui l'utilise fournit des snapshots lus dans le même périmètre
organisationnel. La lecture/persistance SQL des résultats appartient à P5-B.2.
"""
from neosys_pharma.domain.prise_en_charge import (
    CalculateurPriseEnCharge,
    DecisionVenteComptant,
    DemandeCalculPriseEnCharge,
    ResultatCalculPriseEnCharge,
    evaluer_alternative_comptant,
)


class SimulationPriseEnChargeService:
    """Orchestre le calcul provisoire sans créer d'écriture métier définitive."""

    def __init__(self, moteur: CalculateurPriseEnCharge | None = None):
        self.moteur = moteur or CalculateurPriseEnCharge()

    def simuler(self, demande: DemandeCalculPriseEnCharge) -> ResultatCalculPriseEnCharge:
        return self.moteur.calculer(demande)

    @staticmethod
    def evaluer_accord_comptant(
        resultat: ResultatCalculPriseEnCharge, *, consentement_explicite_client: bool,
    ) -> DecisionVenteComptant:
        return evaluer_alternative_comptant(
            resultat,
            consentement_explicite_client=consentement_explicite_client,
        )
