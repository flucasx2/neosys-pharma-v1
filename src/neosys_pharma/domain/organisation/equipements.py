"""Identités de configuration P1 ; opérations de caisse réservées à P4."""
from dataclasses import dataclass, field
from uuid import UUID, uuid4


def _valider(parent_id: UUID, code: str, nom: str) -> tuple[str, str]:
    if not isinstance(parent_id, UUID):
        raise ValueError("Le rattachement de l'équipement est obligatoire.")
    code, nom = code.strip().upper(), nom.strip()
    if not code:
        raise ValueError("Le code est obligatoire.")
    if not nom:
        raise ValueError("Le nom est obligatoire.")
    return code, nom


@dataclass(kw_only=True)
class PosteVente:
    emplacement_id: UUID
    code: str
    nom: str
    actif: bool = True
    id_poste_vente: UUID = field(default_factory=uuid4)

    def __post_init__(self) -> None:
        self.code, self.nom = _valider(self.emplacement_id, self.code, self.nom)


@dataclass(kw_only=True)
class Caisse:
    emplacement_id: UUID
    code: str
    nom: str
    actif: bool = True
    id_caisse: UUID = field(default_factory=uuid4)

    def __post_init__(self) -> None:
        self.code, self.nom = _valider(self.emplacement_id, self.code, self.nom)


@dataclass(kw_only=True)
class Coffre:
    site_id: UUID
    code: str
    nom: str
    actif: bool = True
    id_coffre: UUID = field(default_factory=uuid4)

    def __post_init__(self) -> None:
        self.code, self.nom = _valider(self.site_id, self.code, self.nom)
