"""Règles de base des organismes payeurs ; aucun calcul de couverture P5-B."""
from dataclasses import dataclass
from datetime import date
from enum import StrEnum
from uuid import UUID


class StatutDroits(StrEnum):
    A_VERIFIER = "A_VERIFIER"
    CONFIRMES = "CONFIRMES"
    REFUSES = "REFUSES"
    SUSPENDUS = "SUSPENDUS"


class RolePriorite(StrEnum):
    PRINCIPAL = "PRINCIPAL"
    SECONDAIRE = "SECONDAIRE"


def verifier_periode(date_debut: date, date_fin: date | None) -> None:
    if date_fin is not None and date_fin < date_debut:
        raise ValueError("La date de fin doit être égale ou postérieure à la date de début.")


@dataclass(frozen=True, slots=True)
class EntreePriorite:
    organisme_id: UUID
    convention_id: UUID
    rang: int
    role: RolePriorite


def verifier_priorites(entrees: list[EntreePriorite]) -> None:
    """Valide l'ordre contractuel sans choisir la conduite d'un calcul P5-B."""
    if not entrees:
        raise ValueError("Une configuration doit contenir au moins un organisme.")
    ranks = sorted(item.rang for item in entrees)
    if ranks != list(range(1, len(entrees) + 1)):
        raise ValueError("Les rangs doivent être uniques et séquentiels à partir de 1.")
    if len({item.organisme_id for item in entrees}) != len(entrees):
        raise ValueError("Un organisme ne peut apparaître qu'une fois dans un même ordre.")
    principals = [item for item in entrees if item.role == RolePriorite.PRINCIPAL]
    if len(principals) > 1:
        raise ValueError("Une configuration ne peut contenir qu'un organisme principal au maximum.")
    if principals and principals[0].rang != 1:
        raise ValueError("L'organisme principal, lorsqu'il est défini, doit être au premier rang.")
