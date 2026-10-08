"""Identités du catalogue, sans stock ni conversion automatique de boîte."""
from dataclasses import dataclass, field
from enum import StrEnum
from uuid import UUID, uuid4


def texte(value: str, maximum: int, *, code=True) -> str:
    value = value.strip().upper() if code else value.strip()
    if not value or len(value) > maximum:
        raise ValueError(f"Texte obligatoire, au plus {maximum} caractères.")
    return value


def parent(value: UUID):
    if not isinstance(value, UUID):
        raise ValueError("Identifiant UUID de parent requis.")


@dataclass(kw_only=True)
class CategorieProduit:
    organisation_id: UUID
    code: str
    nom: str
    gestion_lot: bool = False
    gestion_peremption: bool = False
    fefo: bool = False
    promotion_autorisee: bool = False
    parent_id: UUID | None = None
    actif: bool = True
    id_categorie: UUID = field(default_factory=uuid4)

    def __post_init__(self):
        parent(self.organisation_id)
        self.code, self.nom = texte(self.code, 80, code=True), texte(self.nom, 200)
        if self.parent_id == self.id_categorie:
            raise ValueError("Une catégorie ne peut pas être son propre parent.")


@dataclass(kw_only=True)
class FormePharmaceutique:
    organisation_id: UUID
    code: str
    nom: str
    actif: bool = True
    id_forme: UUID = field(default_factory=uuid4)

    def __post_init__(self):
        parent(self.organisation_id)
        self.code, self.nom = texte(self.code, 80, code=True), texte(self.nom, 200)


@dataclass(kw_only=True)
class Laboratoire:
    organisation_id: UUID
    code: str
    nom: str
    actif: bool = True
    id_laboratoire: UUID = field(default_factory=uuid4)

    def __post_init__(self):
        parent(self.organisation_id)
        self.code, self.nom = texte(self.code, 80, code=True), texte(self.nom, 200)


@dataclass(kw_only=True)
class Produit:
    organisation_id: UUID
    nom: str
    categorie_id: UUID
    forme_id: UUID | None = None
    laboratoire_id: UUID | None = None
    nature_id: UUID | None = None
    mode_delivrance_id: UUID | None = None
    regime_tva_code: str | None = None
    gestion_lot: bool | None = None
    gestion_peremption: bool | None = None
    fefo: bool | None = None
    promotion_autorisee: bool | None = None
    description: str | None = None
    actif: bool = True
    id_produit: UUID = field(default_factory=uuid4)

    def __post_init__(self):
        parent(self.organisation_id)
        parent(self.categorie_id)
        self.nom = texte(self.nom, 200)
        if self.regime_tva_code:
            self.regime_tva_code = texte(self.regime_tva_code, 80)
        if self.description is not None:
            self.description = self.description.strip().upper() or None
            if self.description and len(self.description) > 2000:
                raise ValueError("Description trop longue.")


@dataclass(kw_only=True)
class Conditionnement:
    organisation_id: UUID
    produit_id: UUID
    code: str
    libelle: str
    actif: bool = True
    id_conditionnement: UUID = field(default_factory=uuid4)

    def __post_init__(self):
        parent(self.organisation_id)
        parent(self.produit_id)
        self.code, self.libelle = texte(self.code, 80, code=True), texte(self.libelle, 200)


class TypeReference(StrEnum):
    CIP7 = "CIP7"
    CIP13 = "CIP13"
    EAN = "EAN"
    GTIN = "GTIN"
    HISTORIQUE = "HISTORIQUE"


@dataclass(kw_only=True)
class ReferenceProduit:
    organisation_id: UUID
    conditionnement_id: UUID
    type_reference: TypeReference
    valeur: str
    actif: bool = True
    id_reference: UUID = field(default_factory=uuid4)

    def __post_init__(self):
        parent(self.organisation_id)
        parent(self.conditionnement_id)
        self.type_reference = TypeReference(self.type_reference)
        # Strings preserve leading zeros and historical references verbatim.
        self.valeur = texte(self.valeur, 200, code=False)


def verifier_hierarchie(categorie: CategorieProduit, obtenir):
    vus = {categorie.id_categorie}
    current = categorie.parent_id
    while current:
        if current in vus:
            raise ValueError("Cycle dans la hiérarchie des catégories.")
        vus.add(current)
        ancestor = obtenir(current)
        if not ancestor:
            raise LookupError("Catégorie parente introuvable.")
        if ancestor.organisation_id != categorie.organisation_id:
            raise ValueError("Catégorie parente d'une autre organisation.")
        current = ancestor.parent_id


@dataclass(kw_only=True)
class NatureMedicament:
    organisation_id: UUID
    code: str
    nom: str
    actif: bool = True
    id_nature: UUID = field(default_factory=uuid4)

    def __post_init__(self):
        parent(self.organisation_id)
        self.code, self.nom = texte(self.code, 80), texte(self.nom, 200)


@dataclass(kw_only=True)
class PrincipeActif:
    organisation_id: UUID
    code: str
    nom: str
    actif: bool = True
    id_principe: UUID = field(default_factory=uuid4)

    def __post_init__(self):
        parent(self.organisation_id)
        self.code, self.nom = texte(self.code, 80), texte(self.nom, 200)


@dataclass(kw_only=True)
class ClasseTherapeutique:
    organisation_id: UUID
    code: str
    nom: str
    actif: bool = True
    id_classe: UUID = field(default_factory=uuid4)

    def __post_init__(self):
        parent(self.organisation_id)
        self.code, self.nom = texte(self.code, 80), texte(self.nom, 200)


@dataclass(kw_only=True)
class GroupeSubstitution:
    organisation_id: UUID
    code: str
    nom: str
    actif: bool = True
    id_groupe: UUID = field(default_factory=uuid4)

    def __post_init__(self):
        parent(self.organisation_id)
        self.code, self.nom = texte(self.code, 80), texte(self.nom, 200)


@dataclass(kw_only=True)
class ModeDelivrance:
    organisation_id: UUID
    code: str
    nom: str
    actif: bool = True
    id_mode: UUID = field(default_factory=uuid4)

    def __post_init__(self):
        parent(self.organisation_id)
        self.code, self.nom = texte(self.code, 80), texte(self.nom, 200)


@dataclass(kw_only=True)
class CompositionProduit:
    organisation_id: UUID
    produit_id: UUID
    principe_id: UUID
    dosage: str | None = None
    actif: bool = True
    id_composition: UUID = field(default_factory=uuid4)

    def __post_init__(self):
        parent(self.organisation_id)
        parent(self.produit_id)
        parent(self.principe_id)
        if self.dosage is not None:
            self.dosage = texte(self.dosage, 200, code=False)


@dataclass(kw_only=True)
class ClassificationProduit:
    organisation_id: UUID
    produit_id: UUID
    classe_id: UUID
    actif: bool = True
    id_classification: UUID = field(default_factory=uuid4)


@dataclass(kw_only=True)
class SubstitutionProduit:
    organisation_id: UUID
    produit_id: UUID
    groupe_id: UUID
    actif: bool = True
    id_substitution: UUID = field(default_factory=uuid4)
