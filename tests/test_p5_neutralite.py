"""Acceptation ciblée V1 préparée, aucune exécution autorisée par cette livraison."""
from copy import deepcopy
from dataclasses import replace
from datetime import date
import json
from uuid import uuid4

import pytest

from p5_coordination_fixtures import conditions_v1
from test_p5b_1_moteur_prise_en_charge import confirmed_payer, request, calculate
from neosys_pharma.domain.coordination_prise_en_charge import valider_conditions
from neosys_pharma.domain.prise_en_charge import DecisionDroits, ModeArrondi, StatutCalcul


def demande(*, count=2, amount=1000, cap=None, rounding=ModeArrondi.DEMI_SUP):
    beneficiary = uuid4()
    payers = [confirmed_payer(rate=(80, 100), cap=cap, rounding=rounding)]
    if count >= 2:
        payers.append(confirmed_payer(rate=(50, 100), rank=2, role="SECONDAIRE", rounding=rounding))
    if count == 3:
        payers.append(confirmed_payer(rank=3, role="SECONDAIRE"))
    req = request(payers, amounts=(amount,), beneficiary_id=beneficiary)
    ids = [p.organisme_id for p in req.parametrage.priorites]
    entries = []
    for index, p in enumerate(req.parametrage.priorites):
        conditions = conditions_v1(ids[:2], ecart="SUIVANT" if index < count-1 else "CLIENT")
        entries.append(replace(p, convention=replace(p.convention,
            coordination_json=valider_conditions(conditions))))
    return replace(req, exiger_v1=True, parametrage=replace(req.parametrage, priorites=tuple(entries)))


def modifier(req, index, **changes):
    entries = list(req.parametrage.priorites)
    entries[index] = replace(entries[index], **changes)
    return replace(req, parametrage=replace(req.parametrage, priorites=tuple(entries)))


def politique(req, index, event, action):
    p = req.parametrage.priorites[index]
    clause = json.loads(p.convention.coordination_json)
    clause["traitements_solde"][event] = action
    return modifier(req, index, convention=replace(p.convention,
        coordination_json=valider_conditions({"schema_version": 2, "coordination": clause})))


@pytest.mark.parametrize("count,covered,client", [(1, 800, 200), (2, 900, 100)])
def test_principal_et_complementaire_facultatif(count, covered, client):
    result = calculate(demande(count=count))
    assert result.statut == StatutCalcul.ADMISSIBLE
    assert (result.total_organismes_xaf, result.part_client_xaf) == (covered, client)


def test_inversion_selon_beneficiaire_autorisee_par_les_deux_conventions():
    req = demande()
    first, second = req.parametrage.priorites
    entries = []
    for p in (first, second):
        clause = json.loads(p.convention.coordination_json)
        clause["ordres"].append({"beneficiaires_ids": [str(req.beneficiaire_id)],
            "organismes_ids": [str(second.organisme_id), str(first.organisme_id)]})
        clause["traitements_solde"]["ECART"] = "SUIVANT" if p == second else "CLIENT"
        entries.append(replace(p, convention=replace(p.convention,
            coordination_json=valider_conditions({"schema_version": 2, "coordination": clause}))))
    result = calculate(replace(req, parametrage=replace(req.parametrage, priorites=tuple(entries))))
    assert result.statut == StatutCalcul.ADMISSIBLE
    stages = result.lignes[0].etapes
    assert [(s.organisme_id, s.rang, s.role, s.montant_couvert_xaf) for s in stages] == [
        (second.organisme_id, 1, "PRINCIPAL", 500), (first.organisme_id, 2, "SECONDAIRE", 400)]
    assert result.part_client_xaf == 100


def test_inversion_refusee_si_une_convention_ne_lautorise_pas():
    req = demande()
    p, second = req.parametrage.priorites
    clause = json.loads(p.convention.coordination_json)
    clause["ordres"] = [{"beneficiaires_ids": [],
        "organismes_ids": [str(second.organisme_id), str(p.organisme_id)]}]
    req = modifier(req, 0, convention=replace(p.convention,
        coordination_json=valider_conditions({"schema_version": 2, "coordination": clause})))
    assert calculate(req).statut == StatutCalcul.BLOQUE


@pytest.mark.parametrize("roles", [("SECONDAIRE", "SECONDAIRE"), ("PRINCIPAL", "PRINCIPAL")])
def test_absence_ou_plusieurs_principaux(roles):
    req = demande()
    for i, role in enumerate(roles):
        req = modifier(req, i, role=role)
    assert calculate(req).statut == StatutCalcul.BLOQUE


def test_plusieurs_complementaires_refuses_en_v1():
    assert calculate(demande(count=3)).statut == StatutCalcul.BLOQUE


@pytest.mark.parametrize("event", ["DROITS", "REFUS", "EXCLUSION", "PLAFOND", "ECART"])
def test_clauses_manquantes_refusees(event):
    req = demande(count=1)
    clause = json.loads(req.parametrage.priorites[0].convention.coordination_json)
    del clause["traitements_solde"][event]
    with pytest.raises(ValueError):
        valider_conditions({"schema_version": 2, "coordination": clause})


@pytest.mark.parametrize("cause", ["expire", "refus", "exclusion"])
@pytest.mark.parametrize("action", ["CLIENT", "BLOQUER", "SUIVANT"])
def test_droits_refus_exclusions_traitement_explicite(cause, action):
    req = demande(count=1)
    p = req.parametrage.priorites[0]
    if cause == "expire":
        req = modifier(req, 0, droits=replace(p.droits, date_fin=date(2026, 1, 2)))
    elif cause == "refus":
        req = modifier(req, 0, droits=replace(p.droits, decision=DecisionDroits.REFUSES, motif="Refus contractuel fictif"))
    else:
        req = modifier(req, 0, convention=replace(p.convention,
            exclusions_produits=(req.lignes[0].produit_id,)))
    req = politique(req, 0, "EXCLUSION" if cause == "exclusion" else "REFUS" if cause == "refus" else "DROITS", action)
    result = calculate(req)
    assert result.statut == (StatutCalcul.ADMISSIBLE if action == "CLIENT" else StatutCalcul.BLOQUE)
    if action == "CLIENT":
        assert result.total_organismes_xaf == 0 and result.part_client_xaf == 1000


@pytest.mark.parametrize("event,cap", [("PLAFOND", 100), ("ECART", None)])
def test_solde_bloque_sans_transfert_automatique(event, cap):
    req = politique(demande(count=1, cap=cap), 0, event, "BLOQUER")
    result = calculate(req)
    assert result.statut == StatutCalcul.BLOQUE and result.part_client_xaf is None


def test_plafond_contractuel_transmis_au_complementaire():
    result = calculate(demande(cap=100))
    assert result.total_organismes_xaf == 550 and result.part_client_xaf == 450


@pytest.mark.parametrize("amount", [1, 3, 17, 999, 1001])
def test_arrondis_conservation_total(amount):
    result = calculate(demande(amount=amount))
    assert result.statut == StatutCalcul.ADMISSIBLE
    assert result.total_organismes_xaf + result.part_client_xaf == amount
    assert all(s.montant_couvert_xaf <= s.base_eligible_xaf for s in result.lignes[0].etapes)


def test_nouvelle_confirmation_exige_clauses_meme_pour_ancien_mode():
    req = demande(count=1)
    p = req.parametrage.priorites[0]
    assert calculate(modifier(req, 0, convention=replace(p.convention, coordination_json=None))).statut == StatutCalcul.BLOQUE


def test_snapshot_fige_apres_changement_contractuel():
    req = demande()
    result = calculate(req)
    saved = deepcopy(result.snapshot.en_json())
    changed = calculate(politique(req, 0, "ECART", "BLOQUER"))
    assert changed.statut == StatutCalcul.BLOQUE
    assert result.snapshot.en_json() == saved
    assert "coordination_json" in str(saved)
    assert [(s.rang, s.convention_version) for s in result.lignes[0].etapes] == [(1, 1), (2, 1)]


def test_ordres_ambigus_bloquent_sans_choix_arbitraire():
    req = demande()
    entries = []
    for p in req.parametrage.priorites:
        clause = json.loads(p.convention.coordination_json)
        clause["ordres"].append({"beneficiaires_ids": [], "organismes_ids":
            list(reversed(clause["ordres"][0]["organismes_ids"]))})
        entries.append(replace(p, convention=replace(p.convention,
            coordination_json=valider_conditions({"schema_version": 2, "coordination": clause}))))
    assert calculate(replace(req, parametrage=replace(req.parametrage, priorites=tuple(entries)))).statut == StatutCalcul.BLOQUE


def test_arrondi_fractionnaire_non_defini_bloque():
    result = calculate(demande(count=1, amount=1, rounding=None))
    assert result.statut == StatutCalcul.BLOQUE and result.part_client_xaf is None


def test_convention_expiree_ne_peut_pas_autoriser_la_coordination():
    req = demande(count=1)
    p = req.parametrage.priorites[0]
    req = modifier(req, 0, convention=replace(p.convention, date_fin=date(2026, 1, 2)))
    assert calculate(req).statut == StatutCalcul.BLOQUE
