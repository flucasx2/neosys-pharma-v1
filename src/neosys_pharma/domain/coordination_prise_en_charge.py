"""Clauses V1 de coordination, indépendantes du nom des organismes."""
from dataclasses import replace
import json
from uuid import UUID


def valider_conditions(conditions):
    """Schéma 1 lisible; schéma 2 explicite pour toute nouvelle confirmation."""
    if not isinstance(conditions, dict):
        raise ValueError("Conditions contractuelles invalides.")
    if not conditions or conditions == {"schema_version": 1}:
        if conditions and type(conditions["schema_version"]) is not int:
            raise ValueError("Version de conditions invalide.")
        return None
    if (set(conditions) != {"schema_version", "coordination"}
            or type(conditions["schema_version"]) is not int or conditions["schema_version"] != 2):
        raise ValueError("Version ou champs des conditions non pris en charge.")
    clause = conditions["coordination"]
    if not isinstance(clause, dict) or set(clause) != {"ordres", "traitements_solde"}:
        raise ValueError("Coordination contractuelle incomplète.")
    policies = clause["traitements_solde"]
    if (not isinstance(policies, dict) or set(policies) != {"DROITS", "REFUS", "EXCLUSION", "PLAFOND", "ECART"}
            or any(value not in ("CLIENT", "SUIVANT", "BLOQUER") for value in policies.values())):
        raise ValueError("Traitements explicites des droits, exclusions, plafonds et écarts requis.")
    orders = clause["ordres"]
    if not isinstance(orders, list) or not 1 <= len(orders) <= 100:
        raise ValueError("De 1 à 100 ordres contractuels requis.")
    for order in orders:
        if not isinstance(order, dict) or set(order) != {"beneficiaires_ids", "organismes_ids"}:
            raise ValueError("Sélecteur d'ordre invalide.")
        for field in ("beneficiaires_ids", "organismes_ids"):
            values = order[field]
            if not isinstance(values, list) or any(not isinstance(value, str) for value in values):
                raise ValueError("Liste d'identifiants requise.")
            try:
                parsed = [UUID(value) for value in values]
            except ValueError as exc:
                raise ValueError("Identifiant contractuel invalide.") from exc
            if len(set(parsed)) != len(parsed) or any(str(value) != raw for value, raw in zip(parsed, values)):
                raise ValueError("Identifiants canoniques uniques requis.")
        if not 1 <= len(order["organismes_ids"]) <= 2:
            raise ValueError("Un principal et au plus un complémentaire sont permis en V1.")
    return json.dumps(clause, sort_keys=True, separators=(",", ":"))


def ordonner_v1(request):
    config = request.parametrage
    if request.beneficiaire_id is None or config is None:
        raise ValueError("Bénéficiaire et paramétrage vérifiables requis.")
    entries = config.priorites
    if (not 1 <= len(entries) <= 2 or sum(p.role == "PRINCIPAL" for p in entries) != 1
            or any(p.role not in ("PRINCIPAL", "SECONDAIRE") for p in entries)
            or len({p.organisme_id for p in entries}) != len(entries)
            or sorted(p.rang for p in entries) != list(range(1, len(entries) + 1))
            or any(p.role == "PRINCIPAL" and p.rang != 1 for p in entries)):
        raise ValueError("Exactement un principal au rang 1 et au plus un complémentaire requis.")
    by_organisme = {}
    candidates = None
    for entry in entries:
        convention = entry.convention
        if convention is None or convention.coordination_json is None:
            raise ValueError("Clauses de coordination et de solde obligatoires absentes.")
        if (convention.statut != "ACTIVE" or request.date_calcul < convention.date_debut
                or (convention.date_fin and request.date_calcul > convention.date_fin)):
            raise ValueError("Convention inactive ou hors période: confirmation interdite.")
        clause = json.loads(convention.coordination_json)
        # Revalider également les DTO construits sans projection SQL.
        valider_conditions({"schema_version": 2, "coordination": clause})
        by_organisme[str(entry.organisme_id)] = entry
        exact = [order for order in clause["ordres"] if str(request.beneficiaire_id) in order["beneficiaires_ids"]]
        matching = exact or [order for order in clause["ordres"] if not order["beneficiaires_ids"]]
        allowed = {tuple(order["organismes_ids"]) for order in matching}
        candidates = allowed if candidates is None else candidates & allowed
    candidates = {order for order in (candidates or ()) if set(order) == set(by_organisme)}
    if len(candidates) != 1:
        raise ValueError("Combinaison absente, non autorisée ou ambiguë entre les conventions.")
    order = next(iter(candidates))
    priorities = tuple(replace(by_organisme[key], rang=index,
                               role="PRINCIPAL" if index == 1 else "SECONDAIRE")
                       for index, key in enumerate(order, start=1))
    return replace(request, parametrage=replace(config, priorites=priorities))
