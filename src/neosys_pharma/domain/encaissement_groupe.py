"""P4.6/3.2 : identités et invariants, sans finalisation ni prise en charge P5."""
from dataclasses import dataclass, field, replace
from decimal import Decimal
from enum import StrEnum
from typing import Mapping
from types import MappingProxyType
from uuid import UUID, uuid4
from neosys_pharma.domain.caisse import francs


class EtatDossierGroupe(StrEnum):
    BROUILLON = 'BROUILLON'
    EN_REGLEMENT = 'EN_REGLEMENT'
    ENCAISSE = 'ENCAISSE'
    ANNULE = 'ANNULE'


def _uuid(*values):
    if any(not isinstance(v, UUID) for v in values):
        raise ValueError('Identifiants UUID internes obligatoires.')


def _positive(value):
    if type(value) is not int or value < 1:
        raise ValueError('Révision et ordre strictement positifs requis.')


@dataclass(frozen=True, kw_only=True)
class SelectionGroupe:
    vente_id: UUID
    revision_vente: int
    ordre: int
    compte_id: UUID | None = None
    revision_compte: int | None = None
    id: UUID = field(default_factory=uuid4)

    def __post_init__(self):
        _uuid(self.id, self.vente_id)
        _positive(self.revision_vente)
        _positive(self.ordre)
        if self.compte_id is None and self.revision_compte is not None:
            raise ValueError('Révision de fidélité sans compte interdit.')
        if self.compte_id is not None:
            _uuid(self.compte_id)
            _positive(self.revision_compte)


@dataclass(frozen=True, kw_only=True)
class DossierEncaissementGroupe:
    organisation_id: UUID
    site_id: UUID
    emplacement_id: UUID
    caisse_id: UUID
    session_id: UUID
    auteur_id: UUID
    selections: tuple[SelectionGroupe, ...]
    empreinte_selection: str
    compte_id: UUID | None = None
    revision: int = 1
    etat: EtatDossierGroupe = EtatDossierGroupe.BROUILLON
    id: UUID = field(default_factory=uuid4)

    def __post_init__(self):
        _uuid(self.id, self.organisation_id, self.site_id, self.emplacement_id,
              self.caisse_id, self.session_id, self.auteur_id)
        if self.compte_id is not None:
            _uuid(self.compte_id)
        _positive(self.revision)
        if not isinstance(self.etat, EtatDossierGroupe):
            raise ValueError('État de dossier explicite requis.')
        if len(self.empreinte_selection) != 64 or any(c not in '0123456789abcdef' for c in self.empreinte_selection):
            raise ValueError('Empreinte SHA256 canonique obligatoire.')
        selections = tuple(self.selections)
        if len(selections) < 2 or any(not isinstance(s, SelectionGroupe) for s in selections):
            raise ValueError('Au moins deux ventes requises pour un groupe.')
        if len({s.vente_id for s in selections}) != len(selections) or len({s.ordre for s in selections}) != len(selections):
            raise ValueError('Une vente et un ordre ne peuvent apparaître deux fois.')
        object.__setattr__(self, 'selections', selections)

    def changer_selection(self, selections, empreinte):
        if self.etat != EtatDossierGroupe.BROUILLON:
            raise ValueError('Sélection figée après début des règlements.')
        return replace(self, selections=tuple(selections), empreinte_selection=empreinte, revision=self.revision + 1)

    def transition(self, etat, *, paiements_acquis_resolus=False):
        transitions = {
            EtatDossierGroupe.BROUILLON: {EtatDossierGroupe.EN_REGLEMENT, EtatDossierGroupe.ENCAISSE, EtatDossierGroupe.ANNULE},
            EtatDossierGroupe.EN_REGLEMENT: {EtatDossierGroupe.ENCAISSE, EtatDossierGroupe.ANNULE},
        }
        if etat not in transitions.get(self.etat, set()):
            raise ValueError('Transition de dossier interdite.')
        if etat == EtatDossierGroupe.ANNULE and self.etat == EtatDossierGroupe.EN_REGLEMENT and not paiements_acquis_resolus:
            raise ValueError('Les paiements acquis doivent être résolus avec preuve.')
        return replace(self, etat=etat, revision=self.revision + 1)


def _freeze(value):
    if isinstance(value, Mapping):
        return MappingProxyType({k: _freeze(v) for k, v in value.items()})
    if isinstance(value, (list, tuple)):
        return tuple(_freeze(v) for v in value)
    return value


@dataclass(frozen=True, kw_only=True)
class VentilationEncaissement:
    organisation_id: UUID
    encaissement_id: UUID
    vente_id: UUID
    revision_vente: int
    montant_ht: Decimal
    montant_tva: Decimal
    net_ttc: Decimal
    instantane: Mapping
    remise_ligne: Decimal = Decimal(0)
    remise_globale: Decimal = Decimal(0)
    compte_id: UUID | None = None
    revision_compte: int | None = None
    id: UUID = field(default_factory=uuid4)

    def __post_init__(self):
        _uuid(self.id, self.organisation_id, self.encaissement_id, self.vente_id)
        _positive(self.revision_vente)
        if self.compte_id is None and self.revision_compte is not None:
            raise ValueError('Révision de fidélité sans compte interdit.')
        if self.compte_id is not None:
            _uuid(self.compte_id)
            _positive(self.revision_compte)
        if not isinstance(self.instantane, Mapping) or not self.instantane:
            raise ValueError('Instantané historique obligatoire.')
        object.__setattr__(self, 'instantane', _freeze(self.instantane))
        for name in ('montant_ht', 'montant_tva', 'net_ttc', 'remise_ligne', 'remise_globale'):
            object.__setattr__(self, name, francs(getattr(self, name), True))
        if self.montant_ht + self.montant_tva != self.net_ttc:
            raise ValueError('HT + TVA doit correspondre au TTC historique.')


@dataclass(frozen=True, kw_only=True)
class AllocationReglement:
    organisation_id: UUID
    encaissement_id: UUID
    reglement_id: UUID
    ventilation_id: UUID
    vente_id: UUID
    ligne_vente_id: UUID
    montant_net: Decimal
    id: UUID = field(default_factory=uuid4)

    def __post_init__(self):
        _uuid(self.id, self.organisation_id, self.encaissement_id, self.reglement_id,
              self.ventilation_id, self.vente_id, self.ligne_vente_id)
        object.__setattr__(self, 'montant_net', francs(self.montant_net))


def verifier_allocations(ventilations, allocations, montants_reglements: Mapping[UUID, Decimal],
                         montants_lignes: Mapping[tuple[UUID, UUID], Decimal]):
    """Valider une matrice historisée, sans calculer ou modifier un paiement."""
    ventilations = tuple(ventilations)
    if not ventilations or len({v.id for v in ventilations}) != len(ventilations) or len({v.vente_id for v in ventilations}) != len(ventilations):
        raise ValueError('Ventilations de ventes distinctes obligatoires.')
    scope = {(v.organisation_id, v.encaissement_id) for v in ventilations}
    if len(scope) != 1:
        raise ValueError('Encaissement et organisation uniques requis.')
    parents = {v.id: v for v in ventilations}
    seen, paid, lines, sales = set(), {}, {}, {}
    for a in allocations:
        v = parents.get(a.ventilation_id)
        if not v or (a.organisation_id, a.encaissement_id) not in scope or a.vente_id != v.vente_id:
            raise ValueError('Allocation hors de sa vente ou de son encaissement.')
        key = (a.reglement_id, a.ventilation_id, a.ligne_vente_id)
        if key in seen or a.reglement_id not in montants_reglements or (a.vente_id, a.ligne_vente_id) not in montants_lignes:
            raise ValueError('Allocation dupliquée ou référence inconnue.')
        seen.add(key)
        paid[a.reglement_id] = paid.get(a.reglement_id, Decimal(0)) + a.montant_net
        lines[(a.vente_id, a.ligne_vente_id)] = lines.get((a.vente_id, a.ligne_vente_id), Decimal(0)) + a.montant_net
        sales[a.vente_id] = sales.get(a.vente_id, Decimal(0)) + a.montant_net
    if any(paid.get(k, Decimal(0)) != francs(n, True) for k, n in montants_reglements.items()):
        raise ValueError('Allocation différente du règlement net.')
    if any(k[0] not in {v.vente_id for v in ventilations} or lines.get(k, Decimal(0)) != francs(n, True) for k, n in montants_lignes.items()):
        raise ValueError('Allocation différente du net historique de ligne.')
    if any(sales.get(v.vente_id, Decimal(0)) != v.net_ttc for v in ventilations):
        raise ValueError('Allocation différente du net historique de vente.')
    return True
