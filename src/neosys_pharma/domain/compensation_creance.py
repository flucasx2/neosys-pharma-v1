"""Règles conservatrices de ventilation des retours sur créances."""


def organisme_unique(parts, montant_retour, total_historique):
    """Retourne le payeur certain d'une ligne, ou None sans part à compenser."""
    if isinstance(montant_retour, bool) or not isinstance(montant_retour, int) or montant_retour < 0:
        raise ValueError("Part organismes du retour invalide.")
    if isinstance(total_historique, bool) or not isinstance(total_historique, int) or total_historique < 0:
        raise ValueError("Total organismes historique invalide.")
    payeurs = [(ident, montant) for ident, montant in parts if montant > 0]
    if sum(montant for _, montant in payeurs) != total_historique:
        raise ValueError("Parts P5-B différentes du total organismes historique.")
    if montant_retour == 0:
        return None
    if len(payeurs) != 1:
        raise ValueError("Part retournée multi-organismes ou sans payeur unique.")
    ident, montant = payeurs[0]
    if montant != total_historique or montant_retour > montant:
        raise ValueError("Part retournée incompatible avec la ventilation P5-B historique.")
    return ident
