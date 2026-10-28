"""Scénarios HTTP/SQL à exécuter seulement après autorisation de cible jetable."""
from datetime import datetime, timezone
from uuid import uuid4
import pytest
from sqlalchemy import select
from test_stock import raw_client, account, db
from test_p5b_3_encaissement_prise_en_charge import _prepare
from test_caisse import ready, final
from test_proforma import new, current
from test_vente import setup
from neosys_pharma.infrastructure.prise_en_charge_models import PartCalculPriseEnChargeModel

pytest_plugins = ("test_vente",)


def instantane_confirmation_utc(payload):
    confirme_le = datetime.fromisoformat(payload["confirme_le"])
    if confirme_le.tzinfo is None:
        # SQLite retire l'offset d'un DateTime(timezone=True) ; le modèle
        # initialise confirme_le avec datetime.now(timezone.utc).
        confirme_le = confirme_le.replace(tzinfo=timezone.utc)
    return {**payload, "confirme_le": confirme_le.astimezone(timezone.utc)}


def test_sans_organisme_paiement_integral_client(raw_client, account):
    sale, session, *_ = ready(raw_client, account)
    assert sale["mode"] == "SANS_TIERS"
    result = final(raw_client, account, sale, session,
                   reglements=[{"mode": "ESPECES", "montant": sale["totaux"]["ttc"]}])
    assert result


@pytest.mark.parametrize("mode", ["PRISE_EN_CHARGE", "CNAMGS", "CNAMGS_MUTUELLE"])
def test_proforma_modes_generique_et_historiques_lisibles(raw_client, account, mode):
    setup(raw_client, account)
    version = new(raw_client, account, mode=mode)
    assert current(raw_client, account, version)["mode"] == mode


@pytest.mark.parametrize("refusee", [False, True])
def test_inversion_controlee_serveur_et_rangs_persistes(raw_client, account, refusee):
    c, a = raw_client, account
    sale, session, _, _, beneficiary, _, payers = _prepare(c, a, inversion=True, inversion_refusee=refusee)
    prefix = f"/api/tiers-payants/organisations/{a['org']}/ventes/{sale['id']}/prise-en-charge"
    body = {"cle": str(uuid4()), "revision": sale["revision"], "beneficiaire_id": str(beneficiary)}
    response = c.post(prefix + "/confirmer", json=body)
    if refusee:
        assert response.status_code == 422, response.text
        assert c.get(prefix).json() is None
        return
    assert response.status_code == 201, response.text
    confirmed = response.json()
    stages = confirmed["snapshot"]["lignes"][0]["etapes"]
    assert [(s["organisme_id"], s["rang"], s["role"]) for s in stages] == [
        (str(payers[1]), 1, "PRINCIPAL"), (str(payers[0]), 2, "SECONDAIRE")]
    gen = db(c); sql = next(gen)
    try:
        parts = sql.scalars(select(PartCalculPriseEnChargeModel).where(
            PartCalculPriseEnChargeModel.organisation_id == a["org"],
            PartCalculPriseEnChargeModel.type_part == "ORGANISME")).all()
        assert {part.organisme_id: part.rang for part in parts} == {payers[1]: 1, payers[0]: 2}
    finally:
        gen.close()
    final(c, a, sale, session, reglements=[{"mode": "ESPECES", "montant": confirmed["part_client_xaf"]}])
    assert instantane_confirmation_utc(c.get(prefix).json()) == instantane_confirmation_utc(confirmed)
    assert c.post(prefix + "/simuler", json={"beneficiaire_id": str(beneficiary)}).status_code == 422
    assert c.post(prefix + "/confirmer", json=dict(body, cle=str(uuid4()))).status_code in (409, 422)
    assert instantane_confirmation_utc(c.get(prefix).json()) == instantane_confirmation_utc(confirmed)
