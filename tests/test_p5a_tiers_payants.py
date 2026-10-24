"""P5-A: référentiel, périodes, adhésions distinctes et priorités contrôlées."""
from datetime import date, datetime, timedelta, timezone
from uuid import uuid4

import pytest
from sqlalchemy import select
from sqlalchemy.exc import DBAPIError

from test_stock import raw_client, account, db, login
from test_catalogue import grant
from test_clients_p4b import root as clients_root
from neosys_pharma.infrastructure.tiers_payants_models import EvenementTiersPayantModel
from neosys_pharma.domain.tiers_payants import EntreePriorite, RolePriorite, verifier_periode, verifier_priorites


def root(a):
    return f'/api/tiers-payants/organisations/{a["org"]}'


def post(c, a, path, body, status=201):
    response = c.post(root(a) + path, json={"cle": str(uuid4()), **body})
    assert response.status_code == status, response.text
    return response.json() if response.content else None


def enable_permissions(c, a):
    # Existing P4-B endpoint /clients/.../organismes stays protected by client.gerer.
    grant(c, a, ("client.consulter", "client.gerer") + tuple(code for code, _ in (
        ("tiers_payant.consulter", ""),
        ("tiers_payant.convention.gerer", ""),
        ("tiers_payant.adhesion.consulter", ""),
        ("tiers_payant.adhesion.gerer", ""),
        ("tiers_payant.priorites.gerer", ""),
    )))


def payer(c, a, code):
    response = c.post(clients_root(a) + "/organismes", json={
        "cle": str(uuid4()), "code": code, "nom": "Payer " + code,
    })
    assert response.status_code == 201, response.text
    return response.json()


def convention(c, a, organism, code, start, end):
    return post(c, a, "/conventions", {
        "organisme_id": organism["id"], "code": code,
        "reference_contractuelle": "CTR-" + code,
        "date_debut": start.isoformat(), "date_fin": end.isoformat() if end else None,
        "conditions": {"reference": "conditions-fictives-v1"},
        "extensions_p5b": {"plafonds": [], "exclusions": [], "baremes": []},
    })


def test_p5a_referentiel_adhesion_multi_beneficiaires_priorites_et_historique(raw_client, account):
    c, a = raw_client, account
    enable_permissions(c, a)
    login(c, a)
    start, end = date.today(), date.today() + timedelta(days=365)

    primary, second_a, second_b = (payer(c, a, code) for code in ("GENERIC-A", "GENERIC-B", "GENERIC-C"))
    contracts = [
        convention(c, a, primary, "A", start, None),
        convention(c, a, second_a, "B", start, None),
        convention(c, a, second_b, "C", start, None),
    ]
    assert [item["version"] for item in contracts] == [1, 1, 1]

    holder = post(c, a, "/beneficiaires", {"nom": "Titulaire Fictif", "reference_externe": "BEN-1"})
    covered = post(c, a, "/beneficiaires", {"nom": "Bénéficiaire Fictif", "reference_externe": "BEN-2"})
    membership = post(c, a, "/adhesions", {
        "convention_id": contracts[0]["id"], "titulaire_id": holder["id"],
        "beneficiaire_ids": [covered["id"]], "reference_adhesion": "ADH-2026-001",
        "date_debut": start.isoformat(), "date_fin": end.isoformat(),
        "droits_statut": "A_VERIFIER",
    })
    assert membership["titulaire_id"] == holder["id"]
    assert {item["beneficiaire_id"] for item in membership["beneficiaires"]} == {holder["id"], covered["id"]}
    assert {item["relation"] for item in membership["beneficiaires"]} == {"TITULAIRE", "AYANT_DROIT"}
    assert membership["droits_statut"] == "A_VERIFIER"
    verified_at = datetime.now(timezone.utc).isoformat()
    verified = c.put(root(a) + f"/adhesions/{membership['id']}", json={
        "cle": str(uuid4()), "revision": membership["revision"], "date_fin": end.isoformat(),
        "statut": "ACTIVE", "droits_statut": "CONFIRMES",
        "reference_verification_droits": "VERIF-FICTIVE-01", "droits_verifies_le": verified_at,
    })
    assert verified.status_code == 200, verified.text
    assert verified.json()["revision"] == membership["revision"] + 1
    assert verified.json()["droits_statut"] == "CONFIRMES"
    stale = c.put(root(a) + f"/adhesions/{membership['id']}", json={
        "cle": str(uuid4()), "revision": membership["revision"], "date_fin": end.isoformat(),
        "statut": "ACTIVE", "droits_statut": "A_VERIFIER",
    })
    assert stale.status_code == 409

    ordered = [
        {"organisme_id": primary["id"], "convention_id": contracts[0]["id"], "rang": 1, "role": "PRINCIPAL"},
        {"organisme_id": second_a["id"], "convention_id": contracts[1]["id"], "rang": 2, "role": "SECONDAIRE"},
        {"organisme_id": second_b["id"], "convention_id": contracts[2]["id"], "rang": 3, "role": "SECONDAIRE"},
    ]
    next_start = start + timedelta(days=181)
    first = post(c, a, "/priorites", {
        "date_debut": start.isoformat(), "date_fin": None,
        "motif": "Paramétrage initial fictif", "priorites": ordered,
    })
    assert [item["rang"] for item in first["priorites"]] == [1, 2, 3]
    assert [item["role"] for item in first["priorites"]] == ["PRINCIPAL", "SECONDAIRE", "SECONDAIRE"]

    next_end = end
    second = post(c, a, "/priorites", {
        "date_debut": next_start.isoformat(), "date_fin": next_end.isoformat(),
        "motif": "Nouvelle version fictive", "priorites": ordered,
    })
    assert second["version"] == first["version"] + 1
    history = c.get(root(a) + "/priorites").json()["items"]
    previous = next(item for item in history if item["id"] == first["id"])
    assert previous["date_fin"] == (next_start - timedelta(days=1)).isoformat()
    assert c.get(root(a) + "/conventions").json()["total"] == 3
    assert c.get(root(a) + "/adhesions").json()["total"] == 1

    gen = db(c); session = next(gen)
    try:
        events = session.scalars(select(EvenementTiersPayantModel).where(EvenementTiersPayantModel.organisation_id == a["org"])).all()
        assert any(event.type == "PARAMETRAGE_PRIORITE_CLOTURE" for event in events)
        assert any(event.type == "ADHESION_DROITS_MODIFIES" for event in events)
        with pytest.raises(DBAPIError):
            session.query(EvenementTiersPayantModel).delete()
            session.commit()
        session.rollback()
    finally:
        gen.close()


def test_p5a_refuse_les_operations_sans_permissions_et_les_organisations_hors_scope(raw_client, account):
    c, a = raw_client, account
    login(c, a)
    assert c.get(root(a) + "/conventions").status_code == 403
    assert c.post(root(a) + "/beneficiaires", json={"cle": str(uuid4()), "nom": "Refus"}).status_code == 403
    wrong_org = {**a, "org": uuid4()}
    assert c.get(root(wrong_org) + "/beneficiaires").status_code == 403


def test_p5a_rejette_periodes_chevauchantes_et_priorites_invalides(raw_client, account):
    c, a = raw_client, account
    enable_permissions(c, a); login(c, a)
    today, end = date.today(), date.today() + timedelta(days=90)
    org = payer(c, a, "NO-OVERLAP")
    convention(c, a, org, "CONTRAT", today, end)
    post(c, a, "/conventions", {
        "organisme_id": org["id"], "code": "CONTRAT", "date_debut": today.isoformat(),
        "date_fin": end.isoformat(), "conditions": {}, "extensions_p5b": {},
    }, 422)
    other = payer(c, a, "NO-PRIORITY")
    contract = convention(c, a, other, "CONTRAT-2", today, end)
    invalid = [{"organisme_id": other["id"], "convention_id": contract["id"], "rang": 2, "role": "PRINCIPAL"}]
    post(c, a, "/priorites", {
        "date_debut": today.isoformat(), "date_fin": end.isoformat(),
        "motif": "Rang discontinu", "priorites": invalid,
    }, 422)


def test_p5a_domain_rejects_bad_period_duplicate_ranks_and_two_primary_payers():
    today = date.today()
    with pytest.raises(ValueError, match="date de fin"):
        verifier_periode(today, today - timedelta(days=1))
    one, two = uuid4(), uuid4()
    with pytest.raises(ValueError, match="séquentiels"):
        verifier_priorites([EntreePriorite(one, uuid4(), 2, RolePriorite.PRINCIPAL)])
    with pytest.raises(ValueError, match="qu'une fois"):
        verifier_priorites([
            EntreePriorite(one, uuid4(), 1, RolePriorite.PRINCIPAL),
            EntreePriorite(one, uuid4(), 2, RolePriorite.SECONDAIRE),
        ])
    with pytest.raises(ValueError, match="qu'un organisme principal"):
        verifier_priorites([
            EntreePriorite(one, uuid4(), 1, RolePriorite.PRINCIPAL),
            EntreePriorite(two, uuid4(), 2, RolePriorite.PRINCIPAL),
        ])
    with pytest.raises(ValueError, match="premier rang"):
        verifier_priorites([
            EntreePriorite(one, uuid4(), 1, RolePriorite.SECONDAIRE),
            EntreePriorite(two, uuid4(), 2, RolePriorite.PRINCIPAL),
        ])


def test_p5a_migration_is_additive_and_round_trips_on_temporary_sqlite(tmp_path, monkeypatch):
    import sqlalchemy as sa
    from alembic import command
    from alembic.config import Config
    from neosys_pharma.infrastructure.config import get_settings

    url = f"sqlite+pysqlite:///{tmp_path / 'p5a-migration-temp.db'}"
    monkeypatch.setenv("DATABASE_URL", url)
    get_settings.cache_clear()
    engine = sa.create_engine(url)
    cfg = Config("alembic.ini")
    org_id, payor_id = uuid4(), uuid4()
    try:
        command.upgrade(cfg, "20261015_02")
        org = sa.table("organisations", sa.column("id_organisation", sa.Uuid()),
            sa.column("nom_commercial", sa.String()), sa.column("raison_sociale", sa.String()),
            sa.column("logo", sa.String()), sa.column("coordonnees", sa.String()),
            sa.column("informations_legales", sa.String()), sa.column("actif", sa.Boolean()))
        payors = sa.table("organismes_prise_en_charge", sa.column("id", sa.Uuid()),
            sa.column("organisation_id", sa.Uuid()), sa.column("code", sa.String()),
            sa.column("nom", sa.String()), sa.column("actif", sa.Boolean()),
            sa.column("revision", sa.Integer()))
        with engine.begin() as conn:
            conn.execute(sa.insert(org).values(id_organisation=org_id, nom_commercial="Test", raison_sociale="Test",
                logo=None, coordonnees=None, informations_legales=None, actif=True))
            conn.execute(sa.insert(payors).values(id=payor_id, organisation_id=org_id, code="P4B-EXISTANT",
                nom="Organisme historique", actif=True, revision=1))

        command.upgrade(cfg, "head")
        inspector = sa.inspect(engine)
        assert {"tiers_payant_conventions", "tiers_payant_beneficiaires", "tiers_payant_adhesions",
                "tiers_payant_adhesion_beneficiaires", "tiers_payant_parametrages_priorite",
                "tiers_payant_priorites", "tiers_payant_evenements",
                "tiers_payant_calculs_vente", "tiers_payant_calculs_lignes",
                "tiers_payant_calculs_parts", "tiers_payant_calculs_etapes",
                "tiers_payant_realisations"}.issubset(set(inspector.get_table_names()))
        convention_fks = inspector.get_foreign_keys("tiers_payant_conventions")
        assert any(fk["name"] == "fk_tp_convention_organisme_org" and fk["constrained_columns"] == ["organisme_id", "organisation_id"] for fk in convention_fks)
        membership_fks = inspector.get_foreign_keys("tiers_payant_adhesion_beneficiaires")
        assert {"fk_tp_lien_adhesion_org", "fk_tp_lien_beneficiaire_org"} <= {fk["name"] for fk in membership_fks}
        priority_checks = inspector.get_check_constraints("tiers_payant_priorites")
        assert {"ck_tp_priorite_rang", "ck_tp_principal_premier"} <= {check["name"] for check in priority_checks}
        assert any(unique["name"] == "uq_tp_priorite_rang" for unique in inspector.get_unique_constraints("tiers_payant_priorites"))
        assert any(index["name"] == "uq_tp_priorite_principal" and index["unique"] for index in inspector.get_indexes("tiers_payant_priorites"))
        assert any(unique["name"] == "uq_tp_calc_vente_unique" for unique in inspector.get_unique_constraints("tiers_payant_calculs_vente"))
        calc_checks = inspector.get_check_constraints("tiers_payant_calculs_vente")
        assert {"ck_tp_calc_montants", "ck_tp_calc_equilibre"} <= {check["name"] for check in calc_checks}
        calc_fks = inspector.get_foreign_keys("tiers_payant_calculs_vente")
        assert any(fk["name"] == "fk_tp_calc_vente_site_org" and fk["constrained_columns"] == ["vente_id", "organisation_id", "site_id"] for fk in calc_fks)
        realization_fks = inspector.get_foreign_keys("tiers_payant_realisations")
        assert {"fk_tp_realisation_vente", "fk_tp_realisation_encaissement",
                "fk_tp_realisation_calcul"} <= {fk["name"] for fk in realization_fks}
        realization_uniques = inspector.get_unique_constraints("tiers_payant_realisations")
        assert {"uq_tp_realisation_vente", "uq_tp_realisation_encaissement",
                "uq_tp_realisation_calcul"} <= {item["name"] for item in realization_uniques}
        realization_checks = inspector.get_check_constraints("tiers_payant_realisations")
        assert {"ck_tp_realisation_amounts", "ck_tp_realisation_balance"} <= {
            item["name"] for item in realization_checks}
        with engine.connect() as conn:
            triggers = {row[0] for row in conn.execute(sa.text("SELECT name FROM sqlite_master WHERE type='trigger'"))}
        assert {"tiers_payant_calculs_vente_update_immutable", "tiers_payant_calculs_vente_delete_immutable"} <= triggers
        assert {"tiers_payant_realisations_update_immutable",
                "tiers_payant_realisations_delete_immutable"} <= triggers
        assert {"montant_ttc_xaf", "montant_organismes_xaf"} <= {
            column["name"] for column in inspector.get_columns("vente_retours")}
        with engine.connect() as conn:
            assert conn.execute(sa.select(payors.c.nom).where(payors.c.id == payor_id)).scalar_one() == "Organisme historique"
            from neosys_pharma.domain.organisation.permissions_systeme import PERMISSIONS
            assert set(conn.execute(sa.text("SELECT code FROM permissions WHERE code LIKE 'tiers_payant.%'")).scalars()) == {code for code, _ in PERMISSIONS if code.startswith('tiers_payant.')}

        command.downgrade(cfg, "20261015_02")
        assert "tiers_payant_conventions" not in sa.inspect(engine).get_table_names()
        with engine.connect() as conn:
            assert conn.execute(sa.select(sa.func.count()).select_from(payors).where(payors.c.id == payor_id)).scalar_one() == 1
        command.upgrade(cfg, "head")
    finally:
        engine.dispose()
        get_settings.cache_clear()
