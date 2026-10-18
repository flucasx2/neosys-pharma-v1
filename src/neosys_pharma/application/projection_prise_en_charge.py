"""Projection stricte des référentiels P5-A vers les DTO P5-B.1.

Les documents JSON ne sont jamais interprétés de façon permissive. Le schéma
pris en charge est versionné ici; toute clé inconnue arrête la projection.
"""
from __future__ import annotations

from datetime import date
from uuid import UUID
from decimal import Decimal

from sqlalchemy import select

from neosys_pharma.domain.prise_en_charge import (
    ConventionCalcul, DecisionDroits, DemandeCalculPriseEnCharge,
    EvaluationDroits, LigneVenteCalcul, ModeArrondi, ParametragePrioriteCalcul,
    PrioriteCalcul, RegleCouverture,
)
from neosys_pharma.infrastructure.catalogue_models import ProduitModel
from neosys_pharma.infrastructure.tiers_payants_models import (
    AdhesionBeneficiaireModel, AdhesionOrganismeModel, BeneficiaireCouvertureModel,
    ConventionOrganismeModel, ParametragePrioriteTiersPayantModel,
    PrioriteOrganismeModel,
)
from neosys_pharma.infrastructure.vente_models import LigneVenteModel, VenteModel


class RegleConventionInvalide(ValueError):
    pass


def _keys(value, allowed, label):
    if not isinstance(value, dict) or set(value) - set(allowed):
        raise RegleConventionInvalide(f"{label}: structure inconnue ou ambiguë.")


def _uuid_list(value, label):
    if not isinstance(value, list) or any(not isinstance(x, str) for x in value):
        raise RegleConventionInvalide(f"{label}: liste d'identifiants requise.")
    try:
        result = tuple(UUID(x) for x in value)
    except (ValueError, TypeError) as exc:
        raise RegleConventionInvalide(f"{label}: identifiant invalide.") from exc
    if len(set(result)) != len(result):
        raise RegleConventionInvalide(f"{label}: identifiant dupliqué.")
    return result


def projeter_convention(row: ConventionOrganismeModel) -> ConventionCalcul:
    """Schéma pris en charge dans `extensions_p5b`, version 1.

    `conditions` est réservé à la portée contractuelle et doit être vide ou
    contenir seulement `schema_version: 1`; il n'est pas calculé par P5-B.2.
    """
    conditions = row.conditions or {}
    _keys(conditions, {"schema_version"}, "conditions")
    if conditions and conditions.get("schema_version") != 1:
        raise RegleConventionInvalide("Version de conditions non prise en charge.")
    data = row.extensions_p5b or {}
    _keys(data, {"schema_version", "baremes", "exclusions"}, "extensions_p5b")
    if data.get("schema_version") != 1:
        raise RegleConventionInvalide("extensions_p5b.schema_version doit valoir 1.")
    if set(data) != {"schema_version", "baremes", "exclusions"}:
        raise RegleConventionInvalide("Le schéma P5-B.2 exige baremes et exclusions explicites.")
    exclusions = data["exclusions"]
    _keys(exclusions, {"produits_ids", "categories_ids"}, "exclusions")
    if set(exclusions) != {"produits_ids", "categories_ids"}:
        raise RegleConventionInvalide("Les deux listes d'exclusions doivent être explicites.")
    categories = exclusions["categories_ids"]
    if not isinstance(categories, list) or any(not isinstance(x, str) or not x.strip() for x in categories):
        raise RegleConventionInvalide("exclusions.categories_ids invalide.")
    baremes = data["baremes"]
    if not isinstance(baremes, list):
        raise RegleConventionInvalide("baremes doit être une liste.")
    rules = []
    for item in baremes:
        _keys(item, {"code", "taux_numerateur", "taux_denominateur", "plafond_ligne_xaf", "produits_ids", "categories_ids", "arrondi"}, "barème")
        required = {"code", "taux_numerateur", "taux_denominateur", "produits_ids", "categories_ids", "arrondi"}
        if not required <= set(item) or not isinstance(item["categories_ids"], list) or any(not isinstance(x, str) or not x.strip() for x in item["categories_ids"]):
            raise RegleConventionInvalide("Champs ou sélecteurs de barème incomplets.")
        rounding = item["arrondi"]
        try:
            rules.append(RegleCouverture(
                code=item["code"], taux_numerateur=item["taux_numerateur"],
                taux_denominateur=item["taux_denominateur"],
                plafond_ligne_xaf=item.get("plafond_ligne_xaf"),
                produits_ids=_uuid_list(item["produits_ids"], "barème.produits_ids"),
                categories_ids=tuple(item["categories_ids"]),
                arrondi=ModeArrondi(rounding) if rounding is not None else None,
            ))
        except (TypeError, ValueError) as exc:
            raise RegleConventionInvalide(f"Barème invalide: {exc}") from exc
    return ConventionCalcul(
        convention_id=row.id, organisation_id=row.organisation_id,
        organisme_id=row.organisme_id, code=row.code, version=row.version,
        date_debut=row.date_debut, date_fin=row.date_fin, statut=row.statut,
        reference_contractuelle=row.reference_contractuelle,
        baremes=tuple(rules),
        exclusions_produits=_uuid_list(exclusions["produits_ids"], "exclusions.produits_ids"),
        exclusions_categories=tuple(categories),
    )


def construire_demande(session, vente_id: UUID, organisation_id: UUID, site_id: UUID,
                       date_calcul: date, beneficiaire_id: UUID | None,
                       net_par_ligne: dict[UUID, int] | None = None) -> DemandeCalculPriseEnCharge:
    sale = session.scalar(select(VenteModel).where(
        VenteModel.id == vente_id, VenteModel.organisation_id == organisation_id,
        VenteModel.site_id == site_id,
    ))
    if not sale:
        raise PermissionError("Vente hors organisation/site ou absente.")
    beneficiary = None
    if beneficiaire_id:
        beneficiary = session.scalar(select(BeneficiaireCouvertureModel).where(
            BeneficiaireCouvertureModel.id == beneficiaire_id,
            BeneficiaireCouvertureModel.organisation_id == organisation_id,
            BeneficiaireCouvertureModel.actif.is_(True),
        ))
        if not beneficiary:
            raise PermissionError("Bénéficiaire inactif, hors organisation ou absent.")
    line_rows = list(session.scalars(select(LigneVenteModel).where(
        LigneVenteModel.vente_id == sale.id,
        LigneVenteModel.organisation_id == organisation_id,
        LigneVenteModel.actif.is_(True),
    ).order_by(LigneVenteModel.id)))
    products = {line.produit_id: session.get(ProduitModel, line.produit_id) for line in line_rows}
    lines_list = []
    for line in line_rows:
        # Les montants bruts de LigneVenteModel précèdent l'arrondi commercial
        # P4; le service transmet son finance() TTC net autoritaire.
        raw_net = (net_par_ligne or {}).get(line.id, line.montants["ttc"])
        net = Decimal(str(raw_net))
        if net != net.to_integral_value() or net < 0:
            raise RegleConventionInvalide("Le montant TTC net d'une ligne n'est pas un entier XAF non négatif.")
        lines_list.append(LigneVenteCalcul(
            ligne_id=line.id, organisation_id=organisation_id,
            net_xaf=int(net), produit_id=line.produit_id,
            categorie_id=str(products[line.produit_id].categorie_id) if products.get(line.produit_id) else None,
        ))
    lines = tuple(lines_list)
    config = session.scalar(select(ParametragePrioriteTiersPayantModel).where(
        ParametragePrioriteTiersPayantModel.organisation_id == organisation_id,
        ParametragePrioriteTiersPayantModel.statut == "ACTIVE",
        ParametragePrioriteTiersPayantModel.date_debut <= date_calcul,
        (ParametragePrioriteTiersPayantModel.date_fin.is_(None)) | (ParametragePrioriteTiersPayantModel.date_fin >= date_calcul),
    ).order_by(ParametragePrioriteTiersPayantModel.version.desc()))
    if config is None:
        return DemandeCalculPriseEnCharge(sale.id, organisation_id, site_id, beneficiary.id if beneficiary else None, date_calcul, lines, None)
    priorities = []
    for priority in session.scalars(select(PrioriteOrganismeModel).where(
        PrioriteOrganismeModel.organisation_id == organisation_id,
        PrioriteOrganismeModel.parametrage_id == config.id,
    ).order_by(PrioriteOrganismeModel.rang)):
        convention_row = session.scalar(select(ConventionOrganismeModel).where(
            ConventionOrganismeModel.id == priority.convention_id,
            ConventionOrganismeModel.organisation_id == organisation_id,
            ConventionOrganismeModel.organisme_id == priority.organisme_id,
        ))
        convention = projeter_convention(convention_row) if convention_row else None
        rights = None
        if beneficiary is not None:
            matched = session.execute(select(AdhesionOrganismeModel, AdhesionBeneficiaireModel).join(
                AdhesionBeneficiaireModel,
                (AdhesionBeneficiaireModel.adhesion_id == AdhesionOrganismeModel.id)
                & (AdhesionBeneficiaireModel.organisation_id == AdhesionOrganismeModel.organisation_id),
            ).where(
                AdhesionOrganismeModel.organisation_id == organisation_id,
                AdhesionOrganismeModel.convention_id == priority.convention_id,
                AdhesionBeneficiaireModel.beneficiaire_id == beneficiary.id,
            )).all()
            if len(matched) > 1:
                raise RegleConventionInvalide("Plusieurs adhésions couvrent le bénéficiaire pour la même convention.")
            if not matched:
                rights = EvaluationDroits(DecisionDroits.A_VERIFIER, beneficiary.id, motif="Aucune adhésion vérifiable pour cette convention.")
            else:
                adhesion, link = matched[0]
                status_map = {"CONFIRMES": DecisionDroits.CONFIRMES, "REFUSES": DecisionDroits.REFUSES, "SUSPENDUS": DecisionDroits.SUSPENDUS}
                decision = status_map.get(adhesion.droits_statut, DecisionDroits.A_VERIFIER)
                rights = EvaluationDroits(
                    decision, beneficiary.id, adhesion.id, adhesion.revision,
                    adhesion.date_debut, adhesion.date_fin, adhesion.statut,
                    True, link.date_debut, link.date_fin,
                    adhesion.reference_verification_droits, adhesion.droits_verifies_le,
                    "Droits vérifiés P5-A" if decision != DecisionDroits.A_VERIFIER else "Droits à vérifier.",
                )
        priorities.append(PrioriteCalcul(priority.organisme_id, organisation_id, priority.rang, priority.role, convention, rights))
    return DemandeCalculPriseEnCharge(
        sale.id, organisation_id, site_id, beneficiary.id if beneficiary else None,
        date_calcul, lines,
        ParametragePrioriteCalcul(config.id, organisation_id, config.version, config.version,
                                  config.date_debut, config.date_fin, config.statut == "ACTIVE", tuple(priorities)),
    )
