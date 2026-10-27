"""P5-B.3 : encaissement de la part client et retours sur une base de test."""
from datetime import date, datetime, timezone
from decimal import Decimal
from uuid import UUID, uuid4

from pypdf import PdfReader
from io import BytesIO
from sqlalchemy import func, select
import pytest

pytest_plugins = ("test_vente",)

from test_authentification import db
from test_caisse import post as cash_post, root as cash_root
from test_caisse import category, final as final_cash, ready as ready_cash, rule
from test_regularisation import current as current_session, grant45, post as regularisation_post, ret as create_return, refund
from test_stock import entry, stocks
from test_vente import act, create, line, setup, post as sale_post
from neosys_pharma.domain.organisation.permissions_systeme import permission_id
from neosys_pharma.infrastructure.caisse_models import (
    ClientFideliteModel, CompteFideliteModel, EncaissementModel,
    JournalFideliteModel, MouvementCaisseModel,
)
from neosys_pharma.infrastructure.client_models import ClientModel
from neosys_pharma.infrastructure.prise_en_charge_models import (
    CalculPriseEnChargeVenteModel, LigneCalculPriseEnChargeModel,
    RealisationPriseEnChargeModel,
)
from neosys_pharma.infrastructure.securite_models import RoleModel, RolePermissionModel
from neosys_pharma.infrastructure.tiers_payants_models import (
    AdhesionBeneficiaireModel, AdhesionOrganismeModel,
    BeneficiaireCouvertureModel, ConventionOrganismeModel,
    ParametragePrioriteTiersPayantModel, PrioriteOrganismeModel,
)


def _prepare(c, a):
    product, pack, post_id, till_id = setup(c, a)
    # Le test utilise une vente > 1 000 XAF afin d'observer le barème approuvé
    # 1 point / 1 000 XAF, tout en conservant le prix catalogue du test P4.
    gen = db(c); s = next(gen)
    try:
        from neosys_pharma.infrastructure.stock_models import LotModel
        stock_lot = s.scalar(select(LotModel).where(
            LotModel.organisation_id == a["org"],
            LotModel.conditionnement_id == UUID(pack)))
    finally:
        gen.close()
    entry(c, a, str(stock_lot.id), 30)
    profile_id, fidelity_client_id, account_id = uuid4(), uuid4(), uuid4()
    gen = db(c); s = next(gen)
    try:
        from neosys_pharma.infrastructure.catalogue_models import NatureMedicamentModel, ProduitModel
        from neosys_pharma.infrastructure.securite_models import RolePermissionModel
        nature = s.scalar(select(NatureMedicamentModel).where(
            NatureMedicamentModel.organisation_id == a["org"],
            NatureMedicamentModel.code == "COSMETIQUE"))
        if not nature:
            nature = NatureMedicamentModel(id_nature=uuid4(), organisation_id=a["org"],
                code="COSMETIQUE", nom="Cosmétique fictif", actif=True)
            s.add(nature); s.flush()
        s.get(ProduitModel, UUID(product)).nature_id = nature.id_nature
        s.add(ClientModel(id=profile_id, organisation_id=a["org"], nom="Client fictif",
                          telephone=None, actif=True, revision=1))
        s.flush()
        s.add(ClientFideliteModel(id=fidelity_client_id, organisation_id=a["org"],
            nom="Client fictif", telephone=None, profil_client_id=profile_id))
        s.add(CompteFideliteModel(id=account_id, organisation_id=a["org"],
            client_id=fidelity_client_id, points=0, dette=0, revision=1))
        role = s.scalar(select(RoleModel).where(
            RoleModel.organisation_id == a["org"], RoleModel.code == "CATALOGUE"))
        from neosys_pharma.domain.organisation.permissions_systeme import CAISSE_PERMISSIONS
        for permission in [code for code, _ in CAISSE_PERMISSIONS] + [
                "tiers_payant.consulter", "tiers_payant.adhesion.consulter"]:
            if not s.scalar(select(RolePermissionModel).where(
                RolePermissionModel.role_id == role.id_role,
                RolePermissionModel.permission_id == permission_id(permission))):
                s.add(RolePermissionModel(role_id=role.id_role,
                    permission_id=permission_id(permission)))
        s.commit()
    finally:
        gen.close()

    cash_post(c, a, "/configuration", {"revision": 0,
        "modes": ["ESPECES", "CARTE", "MOBILE_MONEY", "CHEQUE", "VIREMENT"],
        "ticket_appel": False}, 200)
    session = cash_post(c, a, "/sessions", {"caisse_id": till_id, "fond_initial": 1000})
    sale = line(c, a, create(c, a, post_id, mode="MUTUELLE", client_id=str(profile_id)),
                product, pack, 20)
    sale = act(c, a, sale, "valider")
    sale = act(c, a, sale, "transmettre", caisse_id=till_id)

    day = date.today(); beneficiary_id = uuid4(); config_id = uuid4()
    payer_ids, contract_ids, adhesion_ids = [uuid4() for _ in range(3)], [uuid4() for _ in range(3)], [uuid4() for _ in range(3)]
    gen = db(c); s = next(gen)
    try:
        from neosys_pharma.infrastructure.client_models import OrganismePriseEnChargeModel
        names = ("Principal fictif", "Secondaire fictif A", "Secondaire fictif B")
        for i, (payer_id, contract_id, adhesion_id, name) in enumerate(
            zip(payer_ids, contract_ids, adhesion_ids, names, strict=True)):
            s.add(OrganismePriseEnChargeModel(id=payer_id, organisation_id=a["org"],
                code=f"P5B3-{i}", nom=name, actif=True, revision=1))
            s.add(ConventionOrganismeModel(id=contract_id, organisation_id=a["org"],
                organisme_id=payer_id, code=f"P5B3-CONV-{i}", version=1,
                reference_contractuelle=f"P5B3-REF-{i}", date_debut=day,
                date_fin=None, statut="ACTIVE", conditions={"schema_version": 1},
                extensions_p5b={"schema_version": 1,
                    "baremes": [{"code": "BASE", "taux_numerateur": 20,
                        "taux_denominateur": 100, "plafond_ligne_xaf": None,
                        "produits_ids": [], "categories_ids": [], "arrondi": "PLANCHER"}],
                    "exclusions": {"produits_ids": [], "categories_ids": []}},
                auteur_id=a["user"]))
        s.add(BeneficiaireCouvertureModel(id=beneficiary_id, organisation_id=a["org"],
            client_id=profile_id, nom="Bénéficiaire fictif", date_naissance=None,
            reference_externe="B3-BEN", actif=True, revision=1, auteur_id=a["user"]))
        s.flush()
        for contract_id, adhesion_id in zip(contract_ids, adhesion_ids, strict=True):
            s.add(AdhesionOrganismeModel(id=adhesion_id, organisation_id=a["org"],
                convention_id=contract_id, titulaire_id=beneficiary_id,
                reference_adhesion=f"B3-ADH-{adhesion_id.hex[:6]}", date_debut=day,
                date_fin=None, statut="ACTIVE", droits_statut="CONFIRMES",
                reference_verification_droits="B3-VERIF", droits_verifies_le=datetime.now(timezone.utc),
                revision=1, auteur_id=a["user"]))
            s.flush()
            s.add(AdhesionBeneficiaireModel(id=uuid4(), organisation_id=a["org"],
                adhesion_id=adhesion_id, beneficiaire_id=beneficiary_id,
                relation="TITULAIRE", date_debut=day, date_fin=None))
        s.add(ParametragePrioriteTiersPayantModel(id=config_id,
            organisation_id=a["org"], version=1, date_debut=day, date_fin=None,
            statut="ACTIVE", motif="Recette P5-B.3", auteur_id=a["user"]))
        s.flush()
        for rank, (payer_id, contract_id) in enumerate(zip(payer_ids, contract_ids, strict=True), 1):
            s.add(PrioriteOrganismeModel(id=uuid4(), organisation_id=a["org"],
                parametrage_id=config_id, organisme_id=payer_id,
                convention_id=contract_id, rang=rank,
                role="PRINCIPAL" if rank == 1 else "SECONDAIRE"))
        s.commit()
    finally:
        gen.close()
    return sale, session, profile_id, account_id, beneficiary_id, product, payer_ids


def _post(c, path, body, status):
    response = c.post(path, json=body)
    assert response.status_code == status, response.text
    return response.json()


def _refund_idempotent(c, a, ret, session_id, mode):
    route = f"/api/regularisations/organisations/{a['org']}"
    context = c.get(route + "/contexte").json()
    session = next(row for row in context["sessions"] if row["id"] == session_id)
    draft = regularisation_post(c, a, "/remboursements", {
        "retour_id": ret["id"], "session_id": session_id,
        "revision": session["revision"],
        "reglements": [{"mode": mode, "montant": ret["montant"]}],
        "justification": "Remboursement fictif P5-B.3"})
    approved = regularisation_post(c, a, f"/remboursements/{draft['id']}/autoriser", {
        "revision": draft["revision"], "justification": "Autorisation recette fictive"}, 200)
    body = {"revision": approved["revision"], "justification": "Règlement fictif remis",
        "preuves": [{"reference": "P5B3-REFUND", "preuve": "Preuve fictive vérifiée"}]}
    key = uuid4()
    result = regularisation_post(c, a, f"/remboursements/{draft['id']}/executer",
                                 body, 200, key=key)
    assert regularisation_post(c, a, f"/remboursements/{draft['id']}/executer",
                               body, 200, key=key) == result
    return result


def test_encaissement_part_client_multi_organismes_receipt_loyalty_and_returns(raw_client, account, monkeypatch):
    c, a = raw_client, account
    sale, session, profile_id, account_id, beneficiary_id, product, payer_ids = _prepare(c, a)
    pending = c.get(cash_root(a) + f"/ventes/{sale['id']}")
    assert pending.status_code == 200 and pending.json()["prise_en_charge"] is None
    prefix = f"/api/tiers-payants/organisations/{a['org']}/ventes/{sale['id']}/prise-en-charge"
    calc = _post(c, prefix + "/confirmer", {
        "cle": str(uuid4()), "revision": sale["revision"],
        "beneficiaire_id": str(beneficiary_id)}, 201)
    assert calc["total_organismes_xaf"] + calc["part_client_xaf"] == calc["total_xaf"]
    assert len(calc["snapshot"]["lignes"]) == 1

    # Barème métier demandé : 1 point pour 1 000 XAF, et cosmétiques seulement.
    rule(c, a, category(c, a, product), points=1, montant_xaf=1000)
    due = int(calc["part_client_xaf"])
    assert due > 1000
    card_amount = due // 2
    confirmation = cash_post(c, a, f"/ventes/{sale['id']}/confirmations", {
        "revision": sale["revision"], "session_id": session["id"],
        "mode": "CARTE", "montant": card_amount, "reference": "P5B3-CARTE",
        "source": "MANUEL_TERMINAL", "preuve": "Acceptation terminal fictif"})
    cash_post(c, a, f"/ventes/{sale['id']}/confirmations/{confirmation['id']}/rapprocher", {
        "revision": sale["revision"], "session_id": session["id"],
        "justification": "Rapprochement fictif confirmé"}, 200)
    idem_key = uuid4()
    final_body = {
        "revision": sale["revision"], "session_id": session["id"],
        "revision_session": session["revision"],
        "reglements": [{"mode": "CARTE", "montant": card_amount,
                        "confirmation_id": confirmation["id"]},
                       {"mode": "ESPECES", "montant": due-card_amount}],
        "compte_id": str(account_id), "revision_compte": 1,
        "points_utilises": 0, "consentement": False}
    from neosys_pharma.infrastructure import caisse_pdf
    original_pdf = caisse_pdf.recu_pdf
    monkeypatch.setattr(caisse_pdf, "recu_pdf", lambda _: (_ for _ in ()).throw(RuntimeError("PDF fictif indisponible")))
    with pytest.raises(RuntimeError, match="PDF fictif indisponible"):
        cash_post(c, a, f"/ventes/{sale['id']}/finaliser", final_body, 200, idem_key)
    assert c.get(cash_root(a) + f"/ventes/{sale['id']}").json()["etat"] == "TRANSMISE"
    assert sum(x["physique"] for x in stocks(c, a)) == 40
    assert sum(x["reserve"] for x in stocks(c, a)) == 20
    gen = db(c); s = next(gen)
    try:
        assert s.scalar(select(func.count()).select_from(EncaissementModel).where(
            EncaissementModel.vente_id == UUID(sale["id"]))) == 0
        assert s.scalar(select(func.count()).select_from(RealisationPriseEnChargeModel).where(
            RealisationPriseEnChargeModel.vente_id == UUID(sale["id"]))) == 0
        assert s.scalar(select(func.count()).select_from(MouvementCaisseModel).where(
            MouvementCaisseModel.session_id == UUID(session["id"]))) == 0
        assert s.get(CompteFideliteModel, account_id).points == 0
    finally:
        gen.close()
    monkeypatch.setattr(caisse_pdf, "recu_pdf", original_pdf)
    receipt = cash_post(c, a, f"/ventes/{sale['id']}/finaliser", final_body, 200, idem_key)
    assert cash_post(c, a, f"/ventes/{sale['id']}/finaliser", final_body,
                     200, idem_key) == receipt
    assert int(receipt["total_xaf"]) == due
    assert int(receipt["instantane"]["totaux"]["ttc"]) == calc["total_xaf"]
    snapshot = receipt["instantane"]["prise_en_charge"]
    assert snapshot["part_client_xaf"] == due
    assert snapshot["total_organismes_xaf"] == calc["total_organismes_xaf"]
    assert sum(x["montant_xaf"] for x in snapshot["organismes"]) == calc["total_organismes_xaf"]
    assert {UUID(x["organisme_id"]) for x in snapshot["organismes"]} == set(payer_ids)
    pdf = c.get(cash_root(a) + f"/recus/{receipt['id']}/pdf")
    assert pdf.status_code == 200
    pdf_text = " ".join(page.extract_text() or "" for page in PdfReader(BytesIO(pdf.content)).pages)
    assert "Part client encaissée" in pdf_text and "Parts organismes" in pdf_text
    for payer in snapshot["organismes"]:
        assert payer["nom"] in pdf_text

    gen = db(c); s = next(gen)
    try:
        enc = s.get(EncaissementModel, UUID(receipt["id"]))
        realization = s.scalar(select(RealisationPriseEnChargeModel).where(
            RealisationPriseEnChargeModel.vente_id == UUID(sale["id"])))
        assert enc.total_xaf == due and realization is not None
        assert realization.total_xaf == calc["total_xaf"]
        assert realization.part_client_xaf == due
        assert realization.total_organismes_xaf == calc["total_organismes_xaf"]
        assert s.scalar(select(func.count()).select_from(EncaissementModel).where(
            EncaissementModel.vente_id == UUID(sale["id"]))) == 1
        assert s.scalar(select(func.coalesce(func.sum(MouvementCaisseModel.montant_net), 0)).where(
            MouvementCaisseModel.session_id == UUID(session["id"]))) == due
        assert s.scalar(select(func.count()).select_from(JournalFideliteModel).where(
            JournalFideliteModel.encaissement_id == UUID(receipt["id"]),
            JournalFideliteModel.type == "ACQUISITION")) == 1
    finally:
        gen.close()
    assert c.get(cash_root(a) + "/fidelite/" + str(account_id)).json()["points"] == due // 1000
    assert c.post(cash_root(a) + f"/ventes/{sale['id']}/finaliser",
                  json={"cle": str(uuid4()), **final_body}).status_code == 409

    # Simule un point déjà consommé dans l'historique avant les retours.
    # L'utilisation fiscale demeure bloquée par P4; cette ligne représente
    # un journal legacy et vérifie le chemin de régularisation conservateur.
    gen = db(c); s = next(gen)
    try:
        fidelity_account = s.get(CompteFideliteModel, account_id)
        spent = min(fidelity_account.points, 1)
        fidelity_account.points -= spent
        line_ids = [str(row.ligne_vente_id) for row in s.scalars(select(LigneCalculPriseEnChargeModel).where(
            LigneCalculPriseEnChargeModel.calcul_id == UUID(calc["id"]))) ]
        s.add(JournalFideliteModel(id=uuid4(), organisation_id=a["org"],
            compte_id=account_id, encaissement_id=UUID(receipt["id"]),
            auteur_id=a["user"], type="UTILISATION", delta_points=-spent,
            delta_dette=0, details={"base_eligible_historique": str(due),
                "lignes_eligibles": line_ids}))
        s.commit()
    finally:
        gen.close()

    grant45(c, a)
    updated_session = current_session(c, a, session)
    x_report = regularisation_post(c, a, "/clotures/x", {
        "session_id": session["id"], "revision": updated_session["revision"]})
    by_mode = x_report["instantane"]["session"]["nets_par_mode"]
    assert int(by_mode["CARTE"]) == card_amount
    assert int(by_mode["ESPECES"]) == due - card_amount
    idempotency = uuid4()
    first = create_return(c, a, receipt, 10, key=idempotency)
    assert create_return(c, a, receipt, 10, key=idempotency) == first
    assert int(first["montant"]) == due // 2
    assert int(first["montant"]) + first["montant_organismes_xaf"] == first["montant_ttc_xaf"]
    _refund_idempotent(c, a, first, session["id"], "ESPECES")
    second = create_return(c, a, receipt, 10)
    # Restitution sur le fournisseur historique exact, sans substitution.
    assert confirmation["moyen_id"] is not None
    refund(c, a, second, session, mode="CARTE",
           moyen_id=confirmation["moyen_id"], moyen_origine_id=confirmation["moyen_id"])
    loyalty = c.get(cash_root(a) + f"/fidelite/{account_id}").json()
    assert loyalty["points"] == 0 and loyalty["dette"] == 0
    closed_session = current_session(c, a, session)
    cash_post(c, a, f"/sessions/{session['id']}/fermer", {
        "revision": closed_session["revision"],
        "comptage_final": closed_session["especes_attendues"],
        "justification": "Comptage fictif après remboursements P5-B.3"}, 200)
    period = c.get(f"/api/regularisations/organisations/{a['org']}/contexte").json()["periode"]
    z_report = regularisation_post(c, a, "/clotures/z", {
        "periode_id": period["id"], "justification": "Clôture fictive P5-B.3"})
    z_session = next(row for row in z_report["instantane"]["sessions"]
                     if row["id"] == session["id"])
    assert int(z_session["nets_par_mode"]["CARTE"]) == 0
    assert int(z_session["nets_par_mode"]["ESPECES"]) == 0
    gen = db(c); s = next(gen)
    try:
        from neosys_pharma.infrastructure.regularisation_models import CompensationRetourModel
        assert s.scalar(select(func.count()).select_from(RealisationPriseEnChargeModel).where(
            RealisationPriseEnChargeModel.vente_id == UUID(sale["id"]))) == 1
        assert s.scalar(select(func.count()).select_from(JournalFideliteModel).where(
            JournalFideliteModel.encaissement_id == UUID(receipt["id"]),
            JournalFideliteModel.type == "ACQUISITION")) == 1
        assert s.scalar(select(func.count()).select_from(CompensationRetourModel).where(
            CompensationRetourModel.organisation_id == a["org"])) == 2
    finally:
        gen.close()


def test_medicaments_ne_generent_aucun_point_meme_si_un_bareme_est_actif(raw_client, account):
    c, a = raw_client, account
    sale, session, product, *_ = ready_cash(c, a)
    account_row = cash_post(c, a, "/fidelite", {"nom": "Titulaire fictif médicament"})
    rule(c, a, category(c, a, product), points=1, montant_xaf=1000)
    gen = db(c); s = next(gen)
    try:
        from neosys_pharma.infrastructure.catalogue_models import NatureMedicamentModel, ProduitModel
        nature = s.scalar(select(NatureMedicamentModel).where(
            NatureMedicamentModel.organisation_id == a["org"],
            NatureMedicamentModel.code == "MEDICAMENT"))
        if not nature:
            nature = NatureMedicamentModel(id_nature=uuid4(), organisation_id=a["org"],
                code="MEDICAMENT", nom="Médicament fictif", actif=True)
            s.add(nature); s.flush()
        s.get(ProduitModel, UUID(product)).nature_id = nature.id_nature
        s.commit()
    finally:
        gen.close()
    final_cash(c, a, sale, session, compte_id=account_row["id"],
               revision_compte=account_row["revision"])
    assert c.get(cash_root(a) + f"/fidelite/{account_row['id']}").json()["points"] == 0
