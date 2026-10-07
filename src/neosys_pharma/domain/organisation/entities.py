from dataclasses import dataclass
from uuid import UUID, uuid4


@dataclass
class Organisation:
    nom_commercial: str
    raison_sociale: str
    logo: str | None = None
    coordonnees: str | None = None
    informations_legales: str | None = None
    actif: bool = True
    id_organisation: UUID | None = None

    def __post_init__(self) -> None:
        self.nom_commercial = self.nom_commercial.strip()
        self.raison_sociale = self.raison_sociale.strip()

        if not self.nom_commercial:
            raise ValueError("Le nom commercial est obligatoire.")

        if not self.raison_sociale:
            raise ValueError("La raison sociale est obligatoire.")

        if self.id_organisation is None:
            self.id_organisation = uuid4()

@dataclass
class Site:
    organisation_id: UUID
    code: str
    nom: str
    adresse: str | None = None
    telephone: str | None = None
    email: str | None = None
    actif: bool = True
    id_site: UUID | None = None

    def __post_init__(self) -> None:
        self.code = self.code.strip().upper()
        self.nom = self.nom.strip()

        if not self.code:
            raise ValueError("Le code du site est obligatoire.")

        if not self.nom:
            raise ValueError("Le nom du site est obligatoire.")

        if self.id_site is None:
            self.id_site = uuid4()


@dataclass
class Emplacement:
    site_id: UUID
    code: str
    nom: str
    actif: bool = True
    id_emplacement: UUID | None = None

    def __post_init__(self) -> None:
        self.code = self.code.strip().upper()
        self.nom = self.nom.strip()
        if not isinstance(self.site_id, UUID):
            raise ValueError("Le site de l'emplacement est obligatoire.")
        if not self.code:
            raise ValueError("Le code de l'emplacement est obligatoire.")
        if not self.nom:
            raise ValueError("Le nom de l'emplacement est obligatoire.")
        if self.id_emplacement is None:
            self.id_emplacement = uuid4()

