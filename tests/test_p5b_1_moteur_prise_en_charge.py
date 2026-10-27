"""Tests unitaires ciblés du calcul tiers payant P5-B.1."""
from dataclasses import replace
from datetime import date, datetime, timezone
from uuid import uuid4

import pytest

from neosys_pharma.application.prise_en_charge_service import SimulationPriseEnChargeService
from neosys_pharma.domain.prise_en_charge import (
    CalculateurPriseEnCharge,
    CodeBlocage,
    CodeEtape,
    ConventionCalcul,
    DecisionDroits,
    DemandeCalculPriseEnCharge,
    EvaluationDroits,
    LigneVenteCalcul,
    ModeArrondi,
    ParametragePrioriteCalcul,
    PrioriteCalcul,
    RegleCouverture,
    StatutCalcul,
)


AS_OF = date(2026, 10, 17)


def payer(*, rate=(1, 1), cap=None, products=(), categories=(), excluded_products=(), excluded_categories=(), rounding=None, rank=1, role="PRINCIPAL", rights=DecisionDroits.CONFIRMES, rights_reason=None, convention_status="ACTIVE", convention_from=date(2026, 1, 1), convention_to=None, rights_from=date(2026, 1, 1), rights_to=None, missing_convention=False, missing_rights=False, rule_code="R1"):
    org_id, organism_id, convention_id = uuid4(), uuid4(), uuid4()
    rule = RegleCouverture(
        rule_code, rate[0], rate[1], cap, tuple(products), tuple(categories), rounding,
    )
    contract = ConventionCalcul(
        convention_id, org_id, organism_id, "CTR", 1, convention_from,
        convention_to, convention_status, "REF-CTR", (rule,),
        tuple(excluded_products), tuple(excluded_categories),
    )
    verified = rights != DecisionDroits.A_VERIFIER
    evaluation = EvaluationDroits(
        decision=rights,
        beneficiaire_id=uuid4(),
        adhesion_id=uuid4() if rights != DecisionDroits.NON_COUVERT else None,
        revision=1 if rights != DecisionDroits.NON_COUVERT else None,
        date_debut=rights_from if rights != DecisionDroits.NON_COUVERT else None,
        date_fin=rights_to,
        statut_adhesion="ACTIVE",
        relation_beneficiaire_verifiee=True,
        date_lien_debut=rights_from if rights == DecisionDroits.CONFIRMES else None,
        date_lien_fin=rights_to,
        reference_verification="VERIF-1" if verified else None,
        droits_verifies_le=datetime(2026, 10, 17, tzinfo=timezone.utc) if verified else None,
        motif=rights_reason or ("Vérification fictive" if rights != DecisionDroits.CONFIRMES else None),
    )
    return org_id, PrioriteCalcul(
        organism_id, org_id, rank, role,
        None if missing_convention else contract,
        None if missing_rights else evaluation,
    )


def request(payers, amounts=(1000,), *, beneficiary_id=None, product_ids=None, categories=None, at=AS_OF, config_active=True, config_from=date(2026, 1, 1), config_to=None, config_org=None):
    org_id = config_org or payers[0][1].organisation_id
    lines = tuple(
        LigneVenteCalcul(uuid4(), org_id, amount,
                         product_ids[i] if product_ids else uuid4(),
                         categories[i] if categories else "CAT")
        for i, amount in enumerate(amounts)
    )
    config = ParametragePrioriteCalcul(
        uuid4(), org_id, 1, 1, config_from, config_to, config_active,
        tuple(replace(entry, organisation_id=org_id,
                      convention=(replace(entry.convention, organisation_id=org_id) if entry.convention else None),
                      droits=(replace(entry.droits, beneficiaire_id=beneficiary_id)
                              if entry.droits and beneficiary_id is not None else entry.droits))
              for _, entry in payers),
    )
    return DemandeCalculPriseEnCharge(uuid4(), org_id, uuid4(), beneficiary_id, at, lines, config)


def calculate(req):
    return CalculateurPriseEnCharge().calculer(req)


def confirmed_payer(*args, **kwargs):
    return payer(rights=DecisionDroits.CONFIRMES, *args, **kwargs)


def test_organisme_principal_seul_couvre_exactement_le_total():
    org_id, p = confirmed_payer()
    result = calculate(request([(org_id, p)], beneficiary_id=p.droits.beneficiaire_id))
    assert result.statut == StatutCalcul.ADMISSIBLE
    assert result.total_organismes_xaf == 1000
    assert result.part_client_xaf == 0
    assert result.lignes[0].parts_organismes_xaf == ((p.organisme_id, 1000),)


def test_principal_et_deux_secondaires_appliquent_les_taux_au_solde_successif():
    b = uuid4()
    a, primary = confirmed_payer(rate=(30, 100), rank=1, role="PRINCIPAL")
    _, second = confirmed_payer(rate=(1, 2), rank=2, role="SECONDAIRE")
    _, third = confirmed_payer(rate=(1, 1), rank=3, role="SECONDAIRE")
    result = calculate(request([(a, primary), (a, second), (a, third)], beneficiary_id=b))
    assert [stage.montant_couvert_xaf for stage in result.lignes[0].etapes] == [300, 350, 350]
    assert result.part_client_xaf == 0
    assert sum(amount for _, amount in result.lignes[0].parts_organismes_xaf) == 1000


def test_plafond_principal_transmet_le_solde_au_secondaire():
    org_id, primary = confirmed_payer(rate=(1, 1), cap=400, role="PRINCIPAL")
    _, secondary = confirmed_payer(rate=(1, 2), rank=2, role="SECONDAIRE")
    result = calculate(request([(org_id, primary), (org_id, secondary)], beneficiary_id=uuid4()))
    assert [step.montant_couvert_xaf for step in result.lignes[0].etapes] == [400, 300]
    assert result.part_client_xaf == 300


def test_plusieurs_plafonds_successifs_ne_couvrent_jamais_plus_que_le_restant():
    org_id, primary = confirmed_payer(cap=200, role="PRINCIPAL")
    _, secondary = confirmed_payer(cap=100, rank=2, role="SECONDAIRE")
    _, tertiary = confirmed_payer(rate=(1, 2), rank=3, role="SECONDAIRE")
    result = calculate(request([(org_id, primary), (org_id, secondary), (org_id, tertiary)], beneficiary_id=uuid4()))
    assert [step.montant_couvert_xaf for step in result.lignes[0].etapes] == [200, 100, 350]
    assert result.part_client_xaf == 350


def test_exclusion_contractuelle_est_tracee_et_secondaire_peut_couvrir():
    product = uuid4()
    org_id, primary = confirmed_payer(excluded_products=(product,), role="PRINCIPAL")
    _, secondary = confirmed_payer(products=(product,), rank=2, role="SECONDAIRE")
    req = request([(org_id, primary), (org_id, secondary)], beneficiary_id=uuid4(), product_ids=[product])
    result = calculate(req)
    assert result.statut == StatutCalcul.ADMISSIBLE
    assert result.lignes[0].etapes[0].code == CodeEtape.EXCLUSION_CONTRACTUELLE
    assert result.lignes[0].etapes[0].montant_couvert_xaf == 0
    assert result.total_organismes_xaf == 1000


def test_convention_expiree_est_tracee_puis_le_secondaire_est_applique():
    org_id, expired = confirmed_payer(convention_to=date(2026, 10, 16), role="PRINCIPAL")
    _, secondary = confirmed_payer(role="SECONDAIRE", rank=2)
    result = calculate(request([(org_id, expired), (org_id, secondary)], beneficiary_id=uuid4()))
    assert result.lignes[0].etapes[0].code == CodeEtape.CONVENTION_HORS_PERIODE
    assert result.total_organismes_xaf == 1000


@pytest.mark.parametrize("decision", [DecisionDroits.A_VERIFIER, None])
def test_droits_incomplets_bloquent_globalement_la_prise_en_charge(decision):
    org_id, p = confirmed_payer(role="PRINCIPAL")
    if decision is None:
        p = replace(p, droits=None)
    else:
        p = replace(p, droits=replace(p.droits, decision=decision))
    result = calculate(request([(org_id, p)], beneficiary_id=uuid4()))
    assert result.statut == StatutCalcul.BLOQUE
    assert result.total_organismes_xaf is None and result.part_client_xaf is None
    assert result.blocages[0].code == CodeBlocage.DROITS_NON_VERIFIABLES
    assert not result.snapshot.persistance_financiere_autorisee


def test_adhesion_confirmee_sans_preuve_est_inverifiable():
    org_id, p = confirmed_payer()
    p = replace(p, droits=replace(p.droits, reference_verification=None))
    result = calculate(request([(org_id, p)], beneficiary_id=uuid4()))
    assert result.statut == StatutCalcul.BLOQUE
    assert result.blocages[0].code == CodeBlocage.DROITS_NON_VERIFIABLES


def test_adhesion_inactive_ou_lien_beneficiaire_hors_periode_ne_couvre_pas():
    org_id, p = confirmed_payer(role="PRINCIPAL")
    inactive = replace(p, droits=replace(p.droits, statut_adhesion="INACTIVE"))
    result = calculate(request([(org_id, inactive)], beneficiary_id=uuid4()))
    assert result.statut == StatutCalcul.ADMISSIBLE
    assert result.lignes[0].etapes[0].code == CodeEtape.ADHESION_INACTIVE
    expired_link = replace(p, droits=replace(p.droits, date_lien_fin=date(2026, 10, 16)))
    result = calculate(request([(org_id, expired_link)], beneficiary_id=uuid4()))
    assert result.lignes[0].etapes[0].code == CodeEtape.DROITS_HORS_PERIODE


def test_refus_connu_est_trace_et_le_solde_reste_a_la_charge_client():
    org_id, p = payer(rights=DecisionDroits.REFUSES, rights_reason="Refus confirmé", role="PRINCIPAL")
    result = calculate(request([(org_id, p)], beneficiary_id=uuid4()))
    assert result.statut == StatutCalcul.ADMISSIBLE
    assert result.part_client_xaf == 1000 and result.total_organismes_xaf == 0
    assert result.lignes[0].etapes[0].code == CodeEtape.DROITS_REFUSES


def test_suspension_connue_ne_se_confond_pas_avec_une_information_manquante():
    org_id, p = payer(rights=DecisionDroits.SUSPENDUS, rights_reason="Droit suspendu", role="PRINCIPAL")
    result = calculate(request([(org_id, p)], beneficiary_id=uuid4()))
    assert result.statut == StatutCalcul.ADMISSIBLE
    assert result.lignes[0].etapes[0].code == CodeEtape.DROITS_SUSPENDUS
    assert result.part_client_xaf == 1000


def test_priorites_peuvent_commencer_par_des_secondaires_sans_principal():
    org_id, secondary_one = confirmed_payer(rate=(1, 2), role="SECONDAIRE", rank=1)
    _, secondary_two = confirmed_payer(rate=(1, 1), role="SECONDAIRE", rank=2)
    result = calculate(request([(org_id, secondary_one), (org_id, secondary_two)], beneficiary_id=uuid4()))
    assert result.statut == StatutCalcul.ADMISSIBLE
    assert [line.montant_couvert_xaf for line in result.lignes[0].etapes] == [500, 500]


def test_absence_de_couverture_verifiee_ne_cree_pas_de_creance_et_met_le_restant_client():
    org_id, p = payer(rights=DecisionDroits.NON_COUVERT, rights_reason="Aucune adhésion active", role="PRINCIPAL")
    result = calculate(request([(org_id, p)], beneficiary_id=uuid4()))
    assert result.statut == StatutCalcul.ADMISSIBLE
    assert result.lignes[0].etapes[0].code == CodeEtape.BENEFICIAIRE_NON_COUVERT
    assert result.total_organismes_xaf == 0 and result.part_client_xaf == 1000


def test_conventions_de_couverture_differente_par_ligne():
    cat_a, cat_b = "CAT-A", "CAT-B"
    org_id, payer_a = confirmed_payer(categories=(cat_a,), excluded_categories=(cat_b,), role="PRINCIPAL")
    _, payer_b = confirmed_payer(categories=(cat_b,), excluded_categories=(cat_a,), rank=2, role="SECONDAIRE")
    result = calculate(request([(org_id, payer_a), (org_id, payer_b)], amounts=(700, 300),
                               categories=(cat_a, cat_b), beneficiary_id=uuid4()))
    assert result.statut == StatutCalcul.ADMISSIBLE
    assert result.lignes[0].parts_organismes_xaf == ((payer_a.organisme_id, 700),)
    assert result.lignes[1].parts_organismes_xaf == ((payer_b.organisme_id, 300),)
    assert result.part_client_xaf == 0


def test_beneficiaire_absent_est_trace_sans_transferer_les_parts_entre_lignes():
    org_id, p = confirmed_payer(role="PRINCIPAL")
    result = calculate(request([(org_id, p)], beneficiary_id=None))
    assert result.statut == StatutCalcul.ADMISSIBLE
    assert result.lignes[0].etapes[0].code == CodeEtape.BENEFICIAIRE_ABSENT
    assert result.part_client_xaf == 1000


@pytest.mark.parametrize("product,category,expected", [
    (None, "CAT", CodeBlocage.DONNEES_LIGNE_INCOMPLETES),
    (uuid4(), None, CodeBlocage.DONNEES_LIGNE_INCOMPLETES),
])
def test_attribut_deligibilite_absent_bloque(product, category, expected):
    org_id, p = confirmed_payer(products=(uuid4(),), categories=("X",), role="PRINCIPAL")
    result = calculate(request([(org_id, p)], beneficiary_id=uuid4(), product_ids=[product], categories=[category]))
    assert result.statut == StatutCalcul.BLOQUE
    assert result.blocages[0].code == expected


def test_taux_fractionnaire_sans_arrondi_contractuel_bloque():
    org_id, p = confirmed_payer(rate=(1, 2), role="PRINCIPAL")
    result = calculate(request([(org_id, p)], amounts=(101,), beneficiary_id=uuid4()))
    assert result.statut == StatutCalcul.BLOQUE
    assert result.blocages[0].code == CodeBlocage.ARRONDI_NON_DEFINI


def test_arrondi_explicitement_contractuel_est_applique_exactement():
    org_id, p = confirmed_payer(rate=(1, 2), rounding=ModeArrondi.DEMI_SUP, role="PRINCIPAL")
    result = calculate(request([(org_id, p)], amounts=(101,), beneficiary_id=uuid4()))
    assert result.statut == StatutCalcul.ADMISSIBLE
    assert result.total_organismes_xaf == 51 and result.part_client_xaf == 50


def test_absence_de_regle_et_baremes_ambigus_bloquent():
    org_id, p = confirmed_payer(products=(uuid4(),), role="PRINCIPAL")
    no_match = calculate(request([(org_id, p)], beneficiary_id=uuid4(), product_ids=[uuid4()]))
    assert no_match.statut == StatutCalcul.BLOQUE
    assert no_match.blocages[0].code == CodeBlocage.REGLE_MANQUANTE

    rule = p.convention.baremes[0]
    duplicate_contract = replace(p.convention, baremes=(rule, replace(rule, code="R2")))
    duplicate_payer = replace(p, convention=duplicate_contract)
    ambiguous = calculate(request([(org_id, duplicate_payer)], beneficiary_id=uuid4(), product_ids=[rule.produits_ids[0]]))
    assert ambiguous.statut == StatutCalcul.BLOQUE
    assert ambiguous.blocages[0].code == CodeBlocage.REGLES_AMBIGUES


def test_ligne_incalculable_bloque_toute_la_prise_en_charge_de_la_vente():
    org_id, p = confirmed_payer(categories=("CAT-A",), role="PRINCIPAL")
    req = request([(org_id, p)], amounts=(200, 300), categories=("CAT-A", "CAT-B"), beneficiary_id=uuid4())
    result = calculate(req)
    assert result.statut == StatutCalcul.BLOQUE
    assert result.total_organismes_xaf is None and result.part_client_xaf is None
    assert any(item.ligne_id == req.lignes[1].ligne_id and item.code == CodeBlocage.REGLE_MANQUANTE for item in result.blocages)
    assert result.snapshot.simulation_seulement


def test_convention_absente_est_un_blocage_explicitement_identifie():
    org_id, p = confirmed_payer(role="PRINCIPAL")
    p = replace(p, convention=None)
    result = calculate(request([(org_id, p)], beneficiary_id=uuid4()))
    assert result.statut == StatutCalcul.BLOQUE
    assert result.blocages[0].code == CodeBlocage.CONVENTION_MANQUANTE


def test_organismes_dupliques_et_hors_perimetre_sont_refuses():
    org_id, p = confirmed_payer(role="PRINCIPAL")
    duplicate = replace(p, rang=2, role="SECONDAIRE")
    invalid = calculate(request([(org_id, p), (org_id, duplicate)], beneficiary_id=uuid4()))
    assert invalid.statut == StatutCalcul.BLOQUE
    assert invalid.blocages[0].code == CodeBlocage.PRIORITES_INVALIDES

    foreign_request = request([(org_id, p)], beneficiary_id=uuid4())
    foreign_config = replace(
        foreign_request.parametrage,
        priorites=(replace(foreign_request.parametrage.priorites[0], organisation_id=uuid4()),),
    )
    foreign = calculate(replace(foreign_request, parametrage=foreign_config))
    assert foreign.statut == StatutCalcul.BLOQUE
    assert foreign.blocages[0].code == CodeBlocage.PERIMETRE_INCOHERENT


def test_adhesion_ne_peut_pas_etre_reutilisee_sur_deux_rangs():
    org_id, primary = confirmed_payer(role="PRINCIPAL")
    _, secondary = confirmed_payer(role="SECONDAIRE", rank=2)
    secondary = replace(secondary, droits=replace(secondary.droits, adhesion_id=primary.droits.adhesion_id))
    result = calculate(request([(org_id, primary), (org_id, secondary)], beneficiary_id=uuid4()))
    assert result.statut == StatutCalcul.BLOQUE
    assert result.blocages[0].code == CodeBlocage.DROITS_NON_VERIFIABLES


def test_entier_xaf_et_invariant_sont_verifies_pour_chaque_ligne():
    with pytest.raises(ValueError, match="entier XAF"):
        LigneVenteCalcul(uuid4(), uuid4(), 1.25)  # type: ignore[arg-type]
    org_id, primary = confirmed_payer(rate=(1, 2), cap=121, role="PRINCIPAL")
    _, secondary = confirmed_payer(rate=(1, 1), cap=40, rank=2, role="SECONDAIRE")
    result = calculate(request([(org_id, primary), (org_id, secondary)], amounts=(1200,), beneficiary_id=uuid4()))
    line = result.lignes[0]
    assert sum(xaf for _, xaf in line.parts_organismes_xaf) + line.part_client_xaf == line.net_xaf
    assert all(0 <= step.montant_couvert_xaf <= step.base_eligible_xaf for step in line.etapes)


def test_ligne_dupliquee_est_rejetee_pour_eviter_une_double_couverture():
    org_id, p = confirmed_payer(role="PRINCIPAL")
    req = request([(org_id, p)], beneficiary_id=uuid4())
    duplicate_line = replace(req.lignes[0], net_xaf=500)
    result = calculate(replace(req, lignes=(req.lignes[0], duplicate_line)))
    assert result.statut == StatutCalcul.BLOQUE
    assert result.blocages[0].code == CodeBlocage.DONNEES_LIGNE_INCOMPLETES


def test_snapshot_historique_est_immuable_et_la_nouvelle_priorite_ne_le_recalcule_pas():
    org_id, original = confirmed_payer(rate=(1, 2), rounding=ModeArrondi.PLANCHER, role="PRINCIPAL")
    req = request([(org_id, original)], amounts=(1000,), beneficiary_id=uuid4())
    engine = CalculateurPriseEnCharge()
    old = engine.calculer(req)
    old_snapshot_json = old.snapshot.en_json()
    changed_contract = replace(original.convention, baremes=(replace(original.convention.baremes[0], taux_numerateur=1, taux_denominateur=1),))
    original_entry = req.parametrage.priorites[0]
    changed = replace(original_entry, convention=replace(changed_contract, organisation_id=req.organisation_id))
    new_config = replace(req.parametrage, version=2, revision=2, priorites=(changed,))
    new = engine.calculer(replace(req, parametrage=new_config))
    assert old.snapshot.en_json() == old_snapshot_json
    assert old.snapshot.parametrage_version == 1 and new.snapshot.parametrage_version == 2
    assert old.total_organismes_xaf == 500 and new.total_organismes_xaf == 1000


def test_vente_comptant_alternative_exige_un_accord_explicite_et_ne_finalise_rien():
    org_id, p = confirmed_payer(role="PRINCIPAL")
    p = replace(p, droits=replace(p.droits, decision=DecisionDroits.A_VERIFIER))
    result = calculate(request([(org_id, p)], beneficiary_id=uuid4()))
    service = SimulationPriseEnChargeService()
    denied = service.evaluer_accord_comptant(result, consentement_explicite_client=False)
    accepted = service.evaluer_accord_comptant(result, consentement_explicite_client=True)
    assert not denied.consentement_obtenu and not denied.possible
    assert accepted.consentement_obtenu and accepted.possible
    assert accepted.calcul_reference_hash == result.snapshot.hash_contenu
    assert result.snapshot.simulation_seulement and not result.snapshot.persistance_financiere_autorisee


def test_config_priorite_hors_periode_bloque_la_prise_en_charge():
    org_id, p = confirmed_payer(role="PRINCIPAL")
    result = calculate(request([(org_id, p)], beneficiary_id=uuid4(), config_to=date(2026, 10, 16)))
    assert result.statut == StatutCalcul.BLOQUE
    assert result.blocages[0].code == CodeBlocage.PRIORITES_HORS_PERIODE
