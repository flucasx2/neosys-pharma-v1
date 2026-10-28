"""P5-B.2 HTTP/SQL intégration ciblée sur SQLite isolé, sans preuve PG native."""
from p5_coordination_fixtures import conditions_v1
pytest_plugins = ("test_vente",)
from datetime import date, datetime, timezone
from uuid import uuid4

from sqlalchemy import select, func, text
from sqlalchemy.exc import DBAPIError
import pytest

from test_vente import setup, line, create, post, root as vente_root
from test_stock import db
from neosys_pharma.domain.organisation.permissions_systeme import permission_id
from neosys_pharma.infrastructure.securite_models import RoleModel, RolePermissionModel
from neosys_pharma.infrastructure.client_models import OrganismePriseEnChargeModel
from neosys_pharma.infrastructure.tiers_payants_models import (
    AdhesionBeneficiaireModel, AdhesionOrganismeModel, BeneficiaireCouvertureModel,
    ConventionOrganismeModel, ParametragePrioriteTiersPayantModel,
    PrioriteOrganismeModel,
)
from neosys_pharma.infrastructure.prise_en_charge_models import (
    CalculPriseEnChargeVenteModel, LigneCalculPriseEnChargeModel,
    PartCalculPriseEnChargeModel, EtapeCalculPriseEnChargeModel,
)


@pytest.mark.parametrize("mode", ["PRISE_EN_CHARGE", "CNAMGS"])
def test_simulation_et_confirmation_persistent_idempotent_et_immuable(raw_client, account, mode):
    client, acc = raw_client, account
    product, pack, post_id, till_id = setup(client, acc)
    sale = line(client, acc, create(client, acc, post_id, mode=mode), product, pack)
    day = date.today()
    organisme_id, convention_id = uuid4(), uuid4()
    beneficiary_id, adhesion_id, config_id = uuid4(), uuid4(), uuid4()
    gen = db(client)
    session = next(gen)
    try:
        role = session.scalar(select(RoleModel).where(
            RoleModel.organisation_id == acc["org"], RoleModel.code == "CATALOGUE"))
        for code in ("tiers_payant.consulter", "tiers_payant.adhesion.consulter"):
            if not session.scalar(select(RolePermissionModel).where(
                RolePermissionModel.role_id == role.id_role,
                RolePermissionModel.permission_id == permission_id(code))):
                session.add(RolePermissionModel(role_id=role.id_role, permission_id=permission_id(code)))
        session.add(OrganismePriseEnChargeModel(
            id=organisme_id, organisation_id=acc["org"], code="ORG-TEST", nom="Organisme fictif", actif=True, revision=1))
        session.add(ConventionOrganismeModel(
            id=convention_id, organisation_id=acc["org"], organisme_id=organisme_id,
            code="CONV-TEST", version=1, reference_contractuelle="REF-TEST",
            date_debut=day, date_fin=None, statut="ACTIVE", conditions=conditions_v1([organisme_id]),
            extensions_p5b={"schema_version": 1,
                "baremes": [{"code": "BASE", "taux_numerateur": 80,
                    "taux_denominateur": 100, "plafond_ligne_xaf": None,
                    "produits_ids": [], "categories_ids": [], "arrondi": "PLANCHER"}],
                "exclusions": {"produits_ids": [], "categories_ids": []}},
            auteur_id=acc["user"]))
        session.add(BeneficiaireCouvertureModel(
            id=beneficiary_id, organisation_id=acc["org"], client_id=None,
            nom="Bénéficiaire fictif", date_naissance=None, reference_externe="BEN-TEST",
            actif=True, revision=1, auteur_id=acc["user"]))
        session.flush()
        session.add(AdhesionOrganismeModel(
            id=adhesion_id, organisation_id=acc["org"], convention_id=convention_id,
            titulaire_id=beneficiary_id, reference_adhesion="ADH-TEST", date_debut=day,
            date_fin=None, statut="ACTIVE", droits_statut="CONFIRMES",
            reference_verification_droits="VERIF-TEST", droits_verifies_le=datetime.now(timezone.utc),
            revision=1, auteur_id=acc["user"]))
        session.flush()
        session.add(AdhesionBeneficiaireModel(
            id=uuid4(), organisation_id=acc["org"], adhesion_id=adhesion_id,
            beneficiaire_id=beneficiary_id, relation="TITULAIRE", date_debut=day, date_fin=None))
        session.add(ParametragePrioriteTiersPayantModel(
            id=config_id, organisation_id=acc["org"], version=1, date_debut=day,
            date_fin=None, statut="ACTIVE", motif="Recette fictive", auteur_id=acc["user"]))
        session.flush()
        session.add(PrioriteOrganismeModel(
            id=uuid4(), organisation_id=acc["org"], parametrage_id=config_id,
            organisme_id=organisme_id, convention_id=convention_id, rang=1, role="PRINCIPAL"))
        session.commit()
    finally:
        gen.close()

    prefix = f"/api/tiers-payants/organisations/{acc['org']}/ventes/{sale['id']}/prise-en-charge"
    simulated = client.post(prefix + "/simuler", json={"beneficiaire_id": str(beneficiary_id)})
    assert simulated.status_code == 200, simulated.text
    result = simulated.json()
    assert result["statut"] == "CALCUL_ADMISSIBLE_PROVISOIRE"
    assert result["total_xaf"] == int(sale["totaux"]["ttc"])
    assert result["total_organismes_xaf"] + result["part_client_xaf"] == result["total_xaf"]
    assert result["simulation_seulement"] and not result["creance_creee"]
    gen = db(client); session = next(gen)
    try:
        assert session.scalar(select(func.count()).select_from(CalculPriseEnChargeVenteModel)) == 0
    finally: gen.close()

    valid = post(client, acc, f"/{sale['id']}/valider", {"revision": sale["revision"]}, 200)
    transmitted = post(client, acc, f"/{sale['id']}/transmettre", {"revision": valid["revision"], "caisse_id": till_id}, 200)
    key = str(uuid4())
    body = {"cle": key, "revision": transmitted["revision"], "beneficiaire_id": str(beneficiary_id)}
    confirmed = client.post(prefix + "/confirmer", json=body)
    assert confirmed.status_code == 201, confirmed.text
    snapshot = confirmed.json()
    assert snapshot["total_xaf"] == int(sale["totaux"]["ttc"])
    assert snapshot["total_organismes_xaf"] + snapshot["part_client_xaf"] == snapshot["total_xaf"]
    assert client.post(prefix + "/confirmer", json=body).json() == snapshot
    assert client.get(prefix).json()["snapshot_hash"] == snapshot["snapshot_hash"]
    other_key = dict(body, cle=str(uuid4()))
    assert client.post(prefix + "/confirmer", json=other_key).status_code == 409
    changed_content = dict(body, beneficiaire_id=str(uuid4()))
    assert client.post(prefix + "/confirmer", json=changed_content).status_code == 409

    gen = db(client); session = next(gen)
    try:
        assert session.scalar(select(func.count()).select_from(CalculPriseEnChargeVenteModel)) == 1
        assert session.scalar(select(func.count()).select_from(LigneCalculPriseEnChargeModel)) == len(sale["lignes"])
        assert session.scalar(select(func.count()).select_from(PartCalculPriseEnChargeModel)) == 2 * len(sale["lignes"])
        assert session.scalar(select(func.count()).select_from(EtapeCalculPriseEnChargeModel)) == len(sale["lignes"])
        with pytest.raises(DBAPIError):
            session.execute(text("UPDATE tiers_payant_calculs_vente SET part_client_xaf=0"))
            session.commit()
        session.rollback()
    finally: gen.close()
