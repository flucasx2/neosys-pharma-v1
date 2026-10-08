"""Prix HT décimaux datés ; aucune vente ni prix conseillé implicite."""
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from uuid import UUID, uuid4
from neosys_pharma.domain.catalogue import texte


def decimal_valide(value, *, maximum=Decimal('999999999999.9999')):
    value = Decimal(str(value))
    if not value.is_finite() or value < 0 or value > maximum or value != value.quantize(Decimal('.0001')):
        raise ValueError('Valeur décimale positive, au plus quatre décimales, requise.')
    return value


def periode(debut, fin):
    if fin is not None and fin < debut:
        raise ValueError('La fin de période précède son début.')


def chevauche(a, b):
    return a.debut <= (b.fin or date.max) and b.debut <= (a.fin or date.max)


@dataclass(kw_only=True)
class RegimeTVA:
    organisation_id: UUID
    code: str
    nom: str
    taux: Decimal
    debut: date
    fin: date | None = None
    id_regime: UUID = field(default_factory=uuid4)

    def __post_init__(self):
        self.code, self.nom = texte(self.code, 80), texte(self.nom, 200)
        self.taux = decimal_valide(self.taux, maximum=Decimal('100'))
        periode(self.debut, self.fin)


@dataclass(kw_only=True)
class TarifReference:
    organisation_id: UUID
    conditionnement_id: UUID
    montant_ht: Decimal
    devise: str
    debut: date
    fin: date | None = None
    provenance: str | None = None
    id_tarif: UUID = field(default_factory=uuid4)

    def __post_init__(self):
        self.montant_ht = decimal_valide(self.montant_ht)
        self.devise = texte(self.devise, 3)
        if len(self.devise) != 3 or not self.devise.isascii() or not self.devise.isalpha():
            raise ValueError('Code devise ISO à trois lettres requis.')
        periode(self.debut, self.fin)
        if self.provenance is not None:
            self.provenance = texte(self.provenance, 500, code=False)


@dataclass(kw_only=True)
class RegleTarifSite:
    organisation_id: UUID
    site_id: UUID
    devise: str
    debut: date
    montant_ht: Decimal | None = None
    coefficient: Decimal | None = None
    fin: date | None = None
    provenance: str | None = None
    id_tarif: UUID = field(default_factory=uuid4)

    def __post_init__(self):
        # A fixed HT amount OR an explicitly configured reference-price multiplier.
        if (self.montant_ht is None) == (self.coefficient is None):
            raise ValueError('Choisir un montant HT fixe ou un coefficient du tarif de référence.')
        if self.montant_ht is not None:
            self.montant_ht = decimal_valide(self.montant_ht)
        if self.coefficient is not None:
            self.coefficient = decimal_valide(self.coefficient, maximum=Decimal('1000'))
        self.devise = texte(self.devise, 3)
        if len(self.devise) != 3 or not self.devise.isascii() or not self.devise.isalpha():
            raise ValueError('Code devise ISO à trois lettres requis.')
        periode(self.debut, self.fin)
        if self.provenance is not None:
            self.provenance = texte(self.provenance, 500, code=False)


@dataclass(kw_only=True)
class ParametrageTarifSite(RegleTarifSite):
    pass


@dataclass(kw_only=True)
class TarifCategorieSite(RegleTarifSite):
    categorie_id: UUID


@dataclass(kw_only=True)
class TarifProduitSite(RegleTarifSite):
    produit_id: UUID
    conditionnement_id: UUID
