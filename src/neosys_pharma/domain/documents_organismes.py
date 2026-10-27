"""Sommes documentaires exactes en XAF ; aucun taux ni arrondi ajouté."""
from collections.abc import Iterable


def total_xaf(montants: Iterable[int]) -> int:
    values = list(montants)
    if any(type(value) is not int or value < 0 for value in values):
        raise ValueError("Montants documentaires en XAF entiers non négatifs requis.")
    total = sum(values)
    if total > 9_223_372_036_854_775_807:
        raise ValueError("Total documentaire hors capacité entière 64 bits.")
    return total
