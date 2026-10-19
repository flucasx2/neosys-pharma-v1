"""Calcul pur et traçable des couvertures tiers payant (P5-B.1).

Les données reçues sont des snapshots validés par la couche appelante. Aucun
accès aux tables, aucune écriture financière et aucune création de créance ne
sont effectués ici.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from enum import StrEnum
from fractions import Fraction
from hashlib import sha256
import json
from typing import Any
from uuid import UUID


class StatutCalcul(StrEnum):
    ADMISSIBLE = "CALCUL_ADMISSIBLE_PROVISOIRE"
    BLOQUE = "BLOQUE"


class CodeBlocage(StrEnum):
    PRIORITES_ABSENTES = "PRIORITES_ABSENTES"
    PRIORITES_INVALIDES = "PRIORITES_INVALIDES"
    PRIORITES_HORS_PERIODE = "PRIORITES_HORS_PERIODE"
    CONVENTION_MANQUANTE = "CONVENTION_MANQUANTE_OU_INVERIFIABLE"
    CONVENTION_INCOHERENTE = "CONVENTION_INCOHERENTE"
    REGLE_MANQUANTE = "REGLE_CONVENTION_MANQUANTE"
    REGLES_AMBIGUES = "REGLES_CONVENTION_AMBIGUES"
    DONNEES_LIGNE_INCOMPLETES = "DONNEES_LIGNE_INCOMPLETES"
    DROITS_NON_VERIFIABLES = "DROITS_NON_VERIFIABLES"
    ARRONDI_NON_DEFINI = "ARRONDI_NON_DEFINI"
    PERIMETRE_INCOHERENT = "PERIMETRE_ORGANISATION_INCOHERENT"


class DecisionDroits(StrEnum):
    CONFIRMES = "CONFIRMES"
    REFUSES = "REFUSES"
    SUSPENDUS = "SUSPENDUS"
    NON_COUVERT = "NON_COUVERT"
    A_VERIFIER = "A_VERIFIER"


class ModeArrondi(StrEnum):
    """Modes acceptés seulement s'ils sont expressément inscrits au contrat."""

    PLANCHER = "PLANCHER"
    PLAFOND = "PLAFOND"
    DEMI_SUP = "DEMI_SUP"


class CodeEtape(StrEnum):
    APPLIQUE = "APPLIQUE"
    BENEFICIAIRE_ABSENT = "BENEFICIAIRE_ABSENT"
    CONVENTION_INACTIVE = "CONVENTION_INACTIVE"
    CONVENTION_HORS_PERIODE = "CONVENTION_HORS_PERIODE"
    DROITS_REFUSES = "DROITS_REFUSES"
    DROITS_SUSPENDUS = "DROITS_SUSPENDUS"
    BENEFICIAIRE_NON_COUVERT = "BENEFICIAIRE_NON_COUVERT"
    DROITS_HORS_PERIODE = "DROITS_HORS_PERIODE"
    ADHESION_INACTIVE = "ADHESION_INACTIVE"
    ADHESION_SUSPENDUE = "ADHESION_SUSPENDUE"
    EXCLUSION_CONTRACTUELLE = "EXCLUSION_CONTRACTUELLE"


def _xaf(value: int, field: str, *, zero: bool = True) -> None:
    if isinstance(value, bool) or not isinstance(value, int) or value < (0 if zero else 1):
        raise ValueError(f"{field} doit être un montant entier XAF positif ou nul.")


@dataclass(frozen=True, slots=True)
class LigneVenteCalcul:
    """Montant net historique fourni par P4 après prix/remises/TVA."""

    ligne_id: UUID
    organisation_id: UUID
    net_xaf: int
    produit_id: UUID | None = None
    categorie_id: str | None = None

    def __post_init__(self) -> None:
        _xaf(self.net_xaf, "net_xaf")


@dataclass(frozen=True, slots=True)
class RegleCouverture:
    """Règle déclarative par ligne, projetée depuis une convention.

    Le taux est une fraction exacte (ex. 80/100). Le plafond pris en charge
    est limité à chaque ligne; les plafonds périodiques/cumulés ne sont pas
    interprétés dans P5-B.1 faute de règle métier définie.
    """

    code: str
    taux_numerateur: int
    taux_denominateur: int
    plafond_ligne_xaf: int | None = None
    produits_ids: tuple[UUID, ...] = ()
    categories_ids: tuple[str, ...] = ()
    arrondi: ModeArrondi | None = None

    def __post_init__(self) -> None:
        if not self.code.strip():
            raise ValueError("Le code du barème est obligatoire.")
        if (isinstance(self.taux_numerateur, bool) or not isinstance(self.taux_numerateur, int)
                or isinstance(self.taux_denominateur, bool) or not isinstance(self.taux_denominateur, int)
                or self.taux_denominateur <= 0 or self.taux_numerateur < 0
                or self.taux_numerateur > self.taux_denominateur):
            raise ValueError("Le taux doit être une fraction entière comprise entre 0 et 1.")
        if self.plafond_ligne_xaf is not None:
            _xaf(self.plafond_ligne_xaf, "plafond_ligne_xaf")
        if not isinstance(self.arrondi, (ModeArrondi, type(None))):
            raise ValueError("Mode d'arrondi contractuel invalide.")

    @property
    def fraction_taux(self) -> Fraction:
        return Fraction(self.taux_numerateur, self.taux_denominateur)


@dataclass(frozen=True, slots=True)
class ConventionCalcul:
    convention_id: UUID
    organisation_id: UUID
    organisme_id: UUID
    code: str
    version: int
    date_debut: date
    date_fin: date | None
    statut: str
    reference_contractuelle: str | None
    baremes: tuple[RegleCouverture, ...]
    exclusions_produits: tuple[UUID, ...] = ()
    exclusions_categories: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if self.version < 1 or not self.code.strip():
            raise ValueError("Une convention calculable exige un code et une version positive.")
        if self.date_fin is not None and self.date_fin < self.date_debut:
            raise ValueError("La période de convention est inversée.")
        if self.statut not in ("ACTIVE", "INACTIVE"):
            raise ValueError("Le statut de convention doit être ACTIVE ou INACTIVE.")


@dataclass(frozen=True, slots=True)
class EvaluationDroits:
    """Résultat explicite de la vérification d'adhésion/droits du bénéficiaire.

    `NON_COUVERT` signifie que l'absence d'adhésion a été vérifiée. L'absence
    d'une évaluation (None dans `PrioriteCalcul`) signifie au contraire que la
    source est incomplète et bloque le calcul.
    """

    decision: DecisionDroits
    beneficiaire_id: UUID | None
    adhesion_id: UUID | None = None
    revision: int | None = None
    date_debut: date | None = None
    date_fin: date | None = None
    statut_adhesion: str = "ACTIVE"
    relation_beneficiaire_verifiee: bool | None = None
    date_lien_debut: date | None = None
    date_lien_fin: date | None = None
    reference_verification: str | None = None
    droits_verifies_le: datetime | None = None
    motif: str | None = None
    dossier_documentaire_json: str | None = None


@dataclass(frozen=True, slots=True)
class PrioriteCalcul:
    organisme_id: UUID
    organisation_id: UUID
    rang: int
    role: str
    convention: ConventionCalcul | None
    droits: EvaluationDroits | None


@dataclass(frozen=True, slots=True)
class ParametragePrioriteCalcul:
    parametrage_id: UUID
    organisation_id: UUID
    version: int
    revision: int
    date_debut: date
    date_fin: date | None
    actif: bool
    priorites: tuple[PrioriteCalcul, ...]

    def __post_init__(self) -> None:
        if self.version < 1 or self.revision < 1:
            raise ValueError("La version et la révision du paramétrage doivent être positives.")
        if self.date_fin is not None and self.date_fin < self.date_debut:
            raise ValueError("La période de priorité est inversée.")


@dataclass(frozen=True, slots=True)
class DemandeCalculPriseEnCharge:
    vente_id: UUID
    organisation_id: UUID
    site_id: UUID
    beneficiaire_id: UUID | None
    date_calcul: date
    lignes: tuple[LigneVenteCalcul, ...]
    parametrage: ParametragePrioriteCalcul | None


@dataclass(frozen=True, slots=True)
class BlocageCalcul:
    code: CodeBlocage
    message: str
    ligne_id: UUID | None = None
    organisme_id: UUID | None = None


@dataclass(frozen=True, slots=True)
class EtapeCalcul:
    rang: int
    organisme_id: UUID
    role: str
    convention_id: UUID | None
    convention_version: int | None
    adhesion_id: UUID | None
    adhesion_revision: int | None
    base_initiale_xaf: int
    base_eligible_xaf: int
    montant_couvert_xaf: int
    reste_apres_xaf: int
    code: str
    regle_code: str | None
    snapshot_convention: tuple[tuple[str, Any], ...]
    snapshot_droits: tuple[tuple[str, Any], ...]


@dataclass(frozen=True, slots=True)
class LigneResultatCalcul:
    ligne_id: UUID
    net_xaf: int
    etapes: tuple[EtapeCalcul, ...]
    parts_organismes_xaf: tuple[tuple[UUID, int], ...]
    part_client_xaf: int | None


@dataclass(frozen=True, slots=True)
class SnapshotCalculPriseEnCharge:
    vente_id: UUID
    organisation_id: UUID
    site_id: UUID
    beneficiaire_id: UUID | None
    date_calcul: date
    moteur_version: str
    parametrage_id: UUID | None
    parametrage_version: int | None
    parametrage_revision: int | None
    lignes: tuple[LigneResultatCalcul, ...]
    hash_contenu: str
    simulation_seulement: bool = True
    persistance_financiere_autorisee: bool = False

    def en_json(self) -> dict[str, Any]:
        return _to_json(self)


@dataclass(frozen=True, slots=True)
class ResultatCalculPriseEnCharge:
    statut: StatutCalcul
    total_net_xaf: int
    total_organismes_xaf: int | None
    part_client_xaf: int | None
    lignes: tuple[LigneResultatCalcul, ...]
    blocages: tuple[BlocageCalcul, ...]
    snapshot: SnapshotCalculPriseEnCharge
    vente_comptant_alternative_possible: bool
    consentement_client_requis: bool


def _json_value(value: Any) -> Any:
    if isinstance(value, UUID):
        return str(value)
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    if isinstance(value, StrEnum):
        return value.value
    if hasattr(value, "__dataclass_fields__"):
        return {key: _json_value(getattr(value, key)) for key in value.__dataclass_fields__}
    if isinstance(value, dict):
        return {str(k): _json_value(v) for k, v in sorted(value.items(), key=lambda x: str(x[0]))}
    if isinstance(value, (tuple, list)):
        return [_json_value(item) for item in value]
    return value


def _to_json(value: Any) -> Any:
    return _json_value(value)


def _arrondir(valeur: Fraction, mode: ModeArrondi | None) -> int:
    entier, reste = divmod(valeur.numerator, valeur.denominator)
    if reste == 0:
        return entier
    if mode is None:
        raise ArithmeticError("ARRONDI_NON_DEFINI")
    if mode == ModeArrondi.PLANCHER:
        return entier
    if mode == ModeArrondi.PLAFOND:
        return entier + 1
    if mode == ModeArrondi.DEMI_SUP:
        return entier + (1 if reste * 2 >= valeur.denominator else 0)
    raise ArithmeticError("ARRONDI_NON_DEFINI")


def _stage_zero(priority: PrioriteCalcul, line: LigneVenteCalcul, remaining: int, code: CodeEtape) -> EtapeCalcul:
    convention = priority.convention
    snapshot = ()
    if convention is not None:
        snapshot = (
            ("code", convention.code), ("version", convention.version),
            ("statut", convention.statut), ("date_debut", convention.date_debut),
            ("date_fin", convention.date_fin), ("reference", convention.reference_contractuelle),
            ("exclusions_produits", convention.exclusions_produits),
            ("exclusions_categories", convention.exclusions_categories),
            ("baremes", tuple((rule.code, rule.taux_numerateur, rule.taux_denominateur,
                               rule.plafond_ligne_xaf, rule.produits_ids,
                               rule.categories_ids, rule.arrondi) for rule in convention.baremes)),
        )
    rights = priority.droits
    rights_snapshot = () if rights is None else (
        ("decision", rights.decision), ("beneficiaire_id", rights.beneficiaire_id),
        ("adhesion_id", rights.adhesion_id), ("revision", rights.revision),
        ("statut_adhesion", rights.statut_adhesion), ("date_debut", rights.date_debut),
        ("date_fin", rights.date_fin), ("date_lien_debut", rights.date_lien_debut),
        ("date_lien_fin", rights.date_lien_fin),
        ("reference_verification", rights.reference_verification),
        ("droits_verifies_le", rights.droits_verifies_le), ("motif", rights.motif),
    )
    if rights and rights.dossier_documentaire_json is not None:
        rights_snapshot += (("dossier_documentaire_json", rights.dossier_documentaire_json),)
    return EtapeCalcul(
        priority.rang, priority.organisme_id, priority.role,
        convention.convention_id if convention else None,
        convention.version if convention else None,
        priority.droits.adhesion_id if priority.droits else None,
        priority.droits.revision if priority.droits else None,
        line.net_xaf, remaining, 0, remaining, code.value, None,
        snapshot, rights_snapshot,
    )


def _montant_regle(regle: RegleCouverture, restant: int) -> int:
    montant = _arrondir(Fraction(restant) * regle.fraction_taux, regle.arrondi)
    if regle.plafond_ligne_xaf is not None:
        montant = min(montant, regle.plafond_ligne_xaf)
    return min(restant, montant)


def _selecteur_correspond(regle: RegleCouverture, line: LigneVenteCalcul) -> bool:
    if regle.produits_ids and line.produit_id not in regle.produits_ids:
        return False
    if regle.categories_ids and line.categorie_id not in regle.categories_ids:
        return False
    return True


def _validate_priority_list(request: DemandeCalculPriseEnCharge) -> tuple[BlocageCalcul, ...]:
    if len({line.ligne_id for line in request.lignes}) != len(request.lignes):
        return (BlocageCalcul(CodeBlocage.DONNEES_LIGNE_INCOMPLETES, "Une ligne de vente apparaît plusieurs fois dans la demande."),)
    config = request.parametrage
    if config is None:
        return (BlocageCalcul(CodeBlocage.PRIORITES_ABSENTES, "Aucun paramétrage de priorité daté n'est disponible."),)
    if (config.organisation_id != request.organisation_id
            or any(line.organisation_id != request.organisation_id for line in request.lignes)
            or any(p.organisation_id != request.organisation_id for p in config.priorites)):
        return (BlocageCalcul(CodeBlocage.PERIMETRE_INCOHERENT, "Les données ne relèvent pas toutes de la même organisation."),)
    if not config.actif or request.date_calcul < config.date_debut or (config.date_fin and request.date_calcul > config.date_fin):
        return (BlocageCalcul(CodeBlocage.PRIORITES_HORS_PERIODE, "Le paramétrage de priorité n'est pas actif à la date du calcul."),)
    priorities = config.priorites
    if not priorities:
        return (BlocageCalcul(CodeBlocage.PRIORITES_ABSENTES, "Le paramétrage ne contient aucun organisme ordonné."),)
    ranks = [p.rang for p in priorities]
    if sorted(ranks) != list(range(1, len(priorities) + 1)) or len(set(p.organisme_id for p in priorities)) != len(priorities):
        return (BlocageCalcul(CodeBlocage.PRIORITES_INVALIDES, "Les rangs doivent être contigus et les organismes uniques."),)
    principals = [p for p in priorities if p.role == "PRINCIPAL"]
    if len(principals) > 1 or (principals and principals[0].rang != 1) or any(p.role not in ("PRINCIPAL", "SECONDAIRE") for p in priorities):
        return (BlocageCalcul(CodeBlocage.PRIORITES_INVALIDES, "Le rôle principal ou secondaire ne respecte pas l'ordre configuré."),)
    for priority in priorities:
        convention = priority.convention
        if convention is None:
            return (BlocageCalcul(CodeBlocage.CONVENTION_MANQUANTE, "Une convention référencée n'a pas pu être chargée.", organisme_id=priority.organisme_id),)
        if (convention.organisation_id != request.organisation_id
                or convention.organisme_id != priority.organisme_id):
            return (BlocageCalcul(CodeBlocage.CONVENTION_INCOHERENTE, "La convention ne correspond pas à l'organisme et à l'organisation configurés.", organisme_id=priority.organisme_id),)
        convention = priority.convention
        convention_applies = (
            convention is not None and convention.statut == "ACTIVE"
            and convention.date_debut <= request.date_calcul
            and (convention.date_fin is None or request.date_calcul <= convention.date_fin)
        )
        if priority.droits is None and convention_applies and request.beneficiaire_id is not None:
            return (BlocageCalcul(CodeBlocage.DROITS_NON_VERIFIABLES, "Les droits du bénéficiaire n'ont pas pu être vérifiés.", organisme_id=priority.organisme_id),)
        rights = priority.droits
        if rights is None:
            continue
        if rights.decision == DecisionDroits.A_VERIFIER and convention_applies and request.beneficiaire_id is not None:
            return (BlocageCalcul(CodeBlocage.DROITS_NON_VERIFIABLES, "Les droits sont encore à vérifier.", organisme_id=priority.organisme_id),)
        if rights.decision == DecisionDroits.CONFIRMES and convention_applies and request.beneficiaire_id is not None and (
            rights.adhesion_id is None or rights.revision is None or rights.revision < 1
            or rights.date_debut is None or rights.reference_verification is None
            or not rights.reference_verification.strip() or rights.droits_verifies_le is None
            or rights.relation_beneficiaire_verifiee is not True
            or rights.date_lien_debut is None
            or rights.statut_adhesion not in ("ACTIVE", "INACTIVE", "SUSPENDUE")
            or (rights.date_fin is not None and rights.date_debut is not None and rights.date_fin < rights.date_debut)
            or (rights.date_lien_fin is not None and rights.date_lien_debut is not None and rights.date_lien_fin < rights.date_lien_debut)
        ):
            return (BlocageCalcul(CodeBlocage.DROITS_NON_VERIFIABLES, "La preuve, la période ou le lien bénéficiaire de l'adhésion est incomplet.", organisme_id=priority.organisme_id),)
        if (convention_applies and request.beneficiaire_id is not None
                and rights.decision in (DecisionDroits.REFUSES, DecisionDroits.SUSPENDUS, DecisionDroits.NON_COUVERT)
                and (not (rights.motif and rights.motif.strip())
                     or not (rights.reference_verification and rights.reference_verification.strip())
                     or rights.droits_verifies_le is None)):
            return (BlocageCalcul(CodeBlocage.DROITS_NON_VERIFIABLES, "Une décision de non-éligibilité doit conserver son motif, sa référence et sa date de vérification.", organisme_id=priority.organisme_id),)
        if (rights.decision != DecisionDroits.A_VERIFIER and rights.beneficiaire_id != request.beneficiaire_id
                and request.beneficiaire_id is not None and convention_applies):
            return (BlocageCalcul(CodeBlocage.DROITS_NON_VERIFIABLES, "L'évaluation des droits concerne un autre bénéficiaire.", organisme_id=priority.organisme_id),)
        if (rights.decision in (DecisionDroits.CONFIRMES, DecisionDroits.REFUSES, DecisionDroits.SUSPENDUS, DecisionDroits.NON_COUVERT)
                and convention_applies and request.beneficiaire_id is not None
                and rights.droits_verifies_le is not None
                and rights.droits_verifies_le.date() > request.date_calcul):
            return (BlocageCalcul(CodeBlocage.DROITS_NON_VERIFIABLES, "Les droits ont été vérifiés après la date du calcul et ne peuvent justifier celui-ci rétroactivement.", organisme_id=priority.organisme_id),)
    adhesion_ids = [
        p.droits.adhesion_id for p in config.priorites
        if p.droits is not None and p.droits.decision == DecisionDroits.CONFIRMES
        and p.droits.adhesion_id is not None
    ]
    if len(adhesion_ids) != len(set(adhesion_ids)):
        return (BlocageCalcul(CodeBlocage.DROITS_NON_VERIFIABLES, "Une même adhésion est référencée par plusieurs rangs de prise en charge."),)
    return ()


def _controle_eligibilite(priority: PrioriteCalcul, request: DemandeCalculPriseEnCharge) -> CodeEtape | None:
    convention, rights = priority.convention, priority.droits
    assert convention is not None
    if request.beneficiaire_id is None:
        return CodeEtape.BENEFICIAIRE_ABSENT
    if not convention.date_debut <= request.date_calcul or (convention.date_fin and request.date_calcul > convention.date_fin):
        return CodeEtape.CONVENTION_HORS_PERIODE
    if convention.statut != "ACTIVE":
        return CodeEtape.CONVENTION_INACTIVE
    if rights is None:
        # The request validator emits a blocking diagnostic for an applicable
        # contract with missing rights, so this is defensive only.
        return None
    if rights.decision == DecisionDroits.REFUSES:
        return CodeEtape.DROITS_REFUSES
    if rights.decision == DecisionDroits.SUSPENDUS:
        return CodeEtape.DROITS_SUSPENDUS
    if rights.decision == DecisionDroits.NON_COUVERT:
        return CodeEtape.BENEFICIAIRE_NON_COUVERT
    if rights.beneficiaire_id != request.beneficiaire_id:
        return None
    if rights.statut_adhesion == "INACTIVE":
        return CodeEtape.ADHESION_INACTIVE
    if rights.statut_adhesion == "SUSPENDUE":
        return CodeEtape.ADHESION_SUSPENDUE
    if rights.date_debut is None or request.date_calcul < rights.date_debut or (rights.date_fin and request.date_calcul > rights.date_fin):
        return CodeEtape.DROITS_HORS_PERIODE
    if rights.date_lien_debut is None or request.date_calcul < rights.date_lien_debut or (rights.date_lien_fin and request.date_calcul > rights.date_lien_fin):
        return CodeEtape.DROITS_HORS_PERIODE
    return None


class CalculateurPriseEnCharge:
    """Calcule une simulation immuable et globale pour une vente."""

    VERSION = "p5-b.1/1"

    def calculer(self, request: DemandeCalculPriseEnCharge) -> ResultatCalculPriseEnCharge:
        if not request.lignes:
            raise ValueError("Une vente doit contenir au moins une ligne à calculer.")
        for line in request.lignes:
            _xaf(line.net_xaf, "net_xaf")
        total = sum(line.net_xaf for line in request.lignes)
        blockers = list(_validate_priority_list(request))
        if blockers:
            return self._result(request, total, (), tuple(blockers))

        config = request.parametrage
        assert config is not None
        priorities = tuple(sorted(config.priorites, key=lambda entry: entry.rang))
        line_results: list[LigneResultatCalcul] = []
        for line in request.lignes:
            remaining = line.net_xaf
            stages: list[EtapeCalcul] = []
            shares: dict[UUID, int] = {}
            line_blocked = False
            for priority in priorities:
                convention = priority.convention
                assert convention is not None
                ineligible = _controle_eligibilite(priority, request)
                if ineligible is not None:
                    stages.append(_stage_zero(priority, line, remaining, ineligible))
                    continue
                if remaining == 0:
                    stages.append(_stage_zero(priority, line, remaining, CodeEtape.APPLIQUE))
                    continue
                if line.produit_id is None and (convention.exclusions_produits or any(rule.produits_ids for rule in convention.baremes)):
                    blockers.append(BlocageCalcul(CodeBlocage.DONNEES_LIGNE_INCOMPLETES, "L'identifiant produit est requis pour appliquer les exclusions ou barèmes contractuels.", line.ligne_id, priority.organisme_id))
                    line_blocked = True
                    break
                if line.categorie_id is None and (convention.exclusions_categories or any(rule.categories_ids for rule in convention.baremes)):
                    blockers.append(BlocageCalcul(CodeBlocage.DONNEES_LIGNE_INCOMPLETES, "La catégorie est requise pour appliquer les exclusions ou barèmes contractuels.", line.ligne_id, priority.organisme_id))
                    line_blocked = True
                    break
                if line.produit_id in convention.exclusions_produits or line.categorie_id in convention.exclusions_categories:
                    stages.append(_stage_zero(priority, line, remaining, CodeEtape.EXCLUSION_CONTRACTUELLE))
                    continue
                matches = []
                for rule in convention.baremes:
                    if _selecteur_correspond(rule, line):
                        matches.append(rule)
                if len(matches) == 0:
                    blockers.append(BlocageCalcul(CodeBlocage.REGLE_MANQUANTE, "La convention ne définit pas de règle applicable à cette ligne et aucune exclusion explicite ne la couvre.", line.ligne_id, priority.organisme_id))
                    line_blocked = True
                    break
                if len(matches) > 1:
                    blockers.append(BlocageCalcul(CodeBlocage.REGLES_AMBIGUES, "Plusieurs barèmes de la convention s'appliquent à cette ligne.", line.ligne_id, priority.organisme_id))
                    line_blocked = True
                    break
                rule = matches[0]
                try:
                    amount = _montant_regle(rule, remaining)
                except ArithmeticError:
                    blockers.append(BlocageCalcul(CodeBlocage.ARRONDI_NON_DEFINI, "Le taux produit une fraction de XAF et la convention ne définit pas l'arrondi.", line.ligne_id, priority.organisme_id))
                    line_blocked = True
                    break
                base = remaining
                remaining -= amount
                shares[priority.organisme_id] = shares.get(priority.organisme_id, 0) + amount
                stages.append(EtapeCalcul(
                    priority.rang, priority.organisme_id, priority.role, convention.convention_id,
                    convention.version, priority.droits.adhesion_id if priority.droits else None,
                    priority.droits.revision if priority.droits else None,
                    line.net_xaf, base, amount, remaining, CodeEtape.APPLIQUE.value,
                    rule.code,
                    (("code", convention.code), ("version", convention.version),
                     ("reference", convention.reference_contractuelle),
                     ("taux_numerateur", rule.taux_numerateur),
                     ("taux_denominateur", rule.taux_denominateur),
                     ("plafond_ligne_xaf", rule.plafond_ligne_xaf),
                     ("arrondi", rule.arrondi.value if rule.arrondi else None),
                     ("exclusions_produits", convention.exclusions_produits),
                     ("exclusions_categories", convention.exclusions_categories),
                     ("baremes", tuple((item.code, item.taux_numerateur, item.taux_denominateur,
                                        item.plafond_ligne_xaf, item.produits_ids,
                                        item.categories_ids, item.arrondi) for item in convention.baremes))),
                    _stage_zero(priority, line, remaining, CodeEtape.APPLIQUE).snapshot_droits,
                ))
            line_results.append(LigneResultatCalcul(
                line.ligne_id, line.net_xaf, tuple(stages),
                tuple(sorted(shares.items(), key=lambda item: str(item[0]))),
                None if line_blocked else remaining,
            ))

        if blockers:
            return self._result(request, total, tuple(line_results), tuple(blockers))
        # Contrôle de l'invariant sur les entiers XAF avant de qualifier le calcul admissible.
        for line_result in line_results:
            covered = sum(amount for _, amount in line_result.parts_organismes_xaf)
            if covered + (line_result.part_client_xaf or 0) != line_result.net_xaf:
                return self._result(request, total, tuple(line_results), (
                    BlocageCalcul(CodeBlocage.PERIMETRE_INCOHERENT, "L'invariant financier de la ligne n'est pas satisfait.", line_result.ligne_id),
                ))
        return self._result(request, total, tuple(line_results), ())

    def _result(self, request, total, lines, blockers):
        blocked = bool(blockers)
        covered_total = None if blocked else sum(sum(amount for _, amount in line.parts_organismes_xaf) for line in lines)
        client_total = None if blocked else sum(line.part_client_xaf or 0 for line in lines)
        config = request.parametrage
        snapshot_without_hash = {
            "vente_id": request.vente_id, "organisation_id": request.organisation_id,
            "site_id": request.site_id, "beneficiaire_id": request.beneficiaire_id,
            "date_calcul": request.date_calcul, "moteur_version": self.VERSION,
            "parametrage_id": config.parametrage_id if config else None,
            "parametrage_version": config.version if config else None,
            "parametrage_revision": config.revision if config else None,
            "lignes": lines, "blocages": blockers,
        }
        payload = json.dumps(_json_value(snapshot_without_hash), ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        snapshot = SnapshotCalculPriseEnCharge(
            request.vente_id, request.organisation_id, request.site_id, request.beneficiaire_id,
            request.date_calcul, self.VERSION,
            config.parametrage_id if config else None,
            config.version if config else None,
            config.revision if config else None,
            lines, sha256(payload.encode("utf-8")).hexdigest(),
        )
        return ResultatCalculPriseEnCharge(
            StatutCalcul.BLOQUE if blocked else StatutCalcul.ADMISSIBLE,
            total, covered_total, client_total, lines, blockers, snapshot,
            vente_comptant_alternative_possible=blocked,
            consentement_client_requis=blocked,
        )


@dataclass(frozen=True, slots=True)
class DecisionVenteComptant:
    possible: bool
    consentement_requis: bool
    consentement_obtenu: bool
    calcul_reference_hash: str
    message: str


def evaluer_alternative_comptant(
    resultat: ResultatCalculPriseEnCharge, *, consentement_explicite_client: bool,
) -> DecisionVenteComptant:
    """Décision seulement : ne crée ni vente, ni paiement, ni créance."""
    possible = resultat.statut == StatutCalcul.BLOQUE and resultat.vente_comptant_alternative_possible
    consentement_obtenu = possible and consentement_explicite_client
    return DecisionVenteComptant(
        possible=consentement_obtenu,
        consentement_requis=possible,
        consentement_obtenu=consentement_obtenu,
        calcul_reference_hash=resultat.snapshot.hash_contenu,
        message=("Le client a explicitement accepté une vente comptant distincte."
                 if possible and consentement_explicite_client else
                 "Une vente comptant distincte nécessite l'accord explicite du client."
                 if possible else "Aucune alternative comptant n'est proposée pour ce calcul."),
    )
