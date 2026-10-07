"""La preuve d'identité ne confère aucun droit métier."""
from dataclasses import dataclass
from datetime import datetime
from uuid import UUID


class IdentiteNonAuthentifiee(Exception):
    pass


@dataclass(frozen=True, kw_only=True)
class SessionAuthentifiee:
    utilisateur_id: UUID
    expiration: datetime
    empreinte: str

    def valide(self, maintenant: datetime) -> bool:
        return maintenant < self.expiration


def valider_mot_de_passe(value: str) -> None:
    if not 12 <= len(value) <= 128:
        raise ValueError('Le mot de passe doit contenir entre 12 et 128 caractères.')
