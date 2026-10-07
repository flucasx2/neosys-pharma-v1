import os
from uuid import uuid4

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event, inspect, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from neosys_pharma.domain.organisation.entities import Emplacement, Organisation, Site
from neosys_pharma.application.organisation_service import OrganisationService
from neosys_pharma.infrastructure.database import Base, get_db_session
from neosys_pharma.infrastructure.organisation_repository import SqlAlchemyOrganisationRepository
from neosys_pharma.presentation.app import create_app


@pytest.fixture
def client():
    url = os.getenv("TEST_DATABASE_URL", "sqlite+pysqlite://")
    options = {"connect_args": {"check_same_thread": False}, "poolclass": StaticPool} if url.startswith("sqlite") else {}
    engine = create_engine(url, **options)
    if url.startswith("sqlite"):
        @event.listens_for(engine, "connect")
        def foreign_keys(connection, _):
            connection.execute("PRAGMA foreign_keys=ON")
    # TEST_DATABASE_URL must designate a disposable database, never a live one.
    Base.metadata.create_all(engine)
    factory = sessionmaker(engine)
    app = create_app()
    def sessions():
        with factory() as session:
            yield session
    app.dependency_overrides[get_db_session] = sessions
    with TestClient(app) as test_client:
        yield test_client
    Base.metadata.drop_all(engine)
    engine.dispose()


def organisation_payload():
    return {"nom_commercial": " NeoPharma ", "raison_sociale": "NeoPharma SARL",
            "premier_site": {"code": "lbv", "nom": "Libreville", "premier_emplacement": {"code": "reserve", "nom": "Réserve"}}}


def structure(client):
    response = client.post("/api/organisation/organisations", json=organisation_payload())
    assert response.status_code == 201, response.text
    org = response.json()["id_organisation"]
    sites = client.get(f"/api/organisation/organisations/{org}/sites").json()
    return org, sites[0]["id_site"]


def test_parcours_vertical_et_doublons(client):
    org, site = structure(client)
    assert client.get("/api/organisation/organisations").json()[0]["nom_commercial"] == "NeoPharma"
    path = f"/api/organisation/sites/{site}/emplacements"
    assert client.get(path).json()[0]["code"] == "RESERVE"
    assert client.post(path, json={"code": "comptoir", "nom": "Comptoir"}).status_code == 201
    assert client.post(path, json={"code": " COMPTOIR ", "nom": "Autre"}).status_code == 409
    assert len(client.get(path).json()) == 2
    new_site = {"code": "owendo", "nom": "Owendo", "premier_emplacement": {"code": "reserve", "nom": "Réserve"}}
    sites_path = f"/api/organisation/organisations/{org}/sites"
    assert client.post(sites_path, json=new_site).status_code == 201
    assert client.post(sites_path, json=new_site).status_code == 409
    assert len(client.get(sites_path).json()) == 2


def test_parents_absents_validation_et_interface(client):
    assert client.post(f"/api/organisation/sites/{uuid4()}/emplacements", json={"code": "r", "nom": "Réserve"}).status_code == 404
    payload = organisation_payload()
    del payload["premier_site"]
    assert client.post("/api/organisation/organisations", json=payload).status_code == 422
    payload = organisation_payload()
    payload["premier_site"]["premier_emplacement"]["code"] = "   "
    assert client.post("/api/organisation/organisations", json=payload).status_code == 422
    assert client.get("/api/organisation/organisations").json() == []
    assert client.get("/").status_code == 200
    assert "Créer une organisation" in client.get("/").text
    assert client.get("/static/app.js").status_code == 200


@pytest.mark.parametrize("champ", ["code", "nom"])
def test_emplacement_champs_obligatoires(champ):
    data = {"site_id": uuid4(), "code": "r", "nom": "Réserve", champ: "  "}
    with pytest.raises(ValueError):
        Emplacement(**data)


def test_emplacement_normalisation():
    emplacement = Emplacement(site_id=uuid4(), code=" reserve ", nom=" Réserve ")
    assert emplacement.code == "RESERVE"
    assert emplacement.nom == "Réserve"
    assert emplacement.id_emplacement is not None
    with pytest.raises(ValueError):
        Emplacement(site_id=None, code="r", nom="Réserve")


def test_hierarchie_incoherente_avant_ecriture():
    class Repository:
        def ajouter(self, _):
            pytest.fail("Aucune écriture ne doit être tentée")
    org = Organisation(nom_commercial="Neo", raison_sociale="Neo SARL")
    site = Site(organisation_id=uuid4(), code="lbv", nom="Libreville")
    emplacement = Emplacement(site_id=site.id_site, code="r", nom="Réserve")
    with pytest.raises(ValueError, match="incohérente"):
        OrganisationService(Repository()).creer_organisation(org, site, emplacement)


def test_rollback_transaction_complet():
    engine = create_engine("sqlite+pysqlite://")
    Base.metadata.create_all(engine)
    with sessionmaker(engine)() as session:
        repo = SqlAlchemyOrganisationRepository(session)
        org = Organisation(nom_commercial="Neo", raison_sociale="Neo SARL")
        site = Site(organisation_id=org.id_organisation, code="lbv", nom="Libreville")
        repo.ajouter(org)
        repo.ajouter(site)
        repo.ajouter(Emplacement(site_id=site.id_site, code="r", nom="Réserve"))
        with pytest.raises(ValueError):
            repo.ajouter(Emplacement(site_id=site.id_site, code="r", nom="Doublon"))
        assert repo.organisation(org.id_organisation) is None
        assert repo.site(site.id_site) is None
    engine.dispose()


def test_migration_upgrade_check_downgrade(tmp_path, monkeypatch):
    url = os.getenv("TEST_MIGRATION_DATABASE_URL", f"sqlite+pysqlite:///{tmp_path / 'migration.db'}")
    monkeypatch.setenv("DATABASE_URL", url)
    from neosys_pharma.infrastructure.config import get_settings
    get_settings.cache_clear()
    config = Config("alembic.ini")
    try:
        command.upgrade(config, "head")
        engine = create_engine(url)
        assert set(inspect(engine).get_table_names()) >= {"organisations", "sites", "emplacements"}
        command.check(config)
        # Existing hierarchy survives an equipment-only rollback and re-upgrade.
        org = Organisation(nom_commercial="Migration", raison_sociale="Migration SARL")
        site = Site(organisation_id=org.id_organisation, code="MIG", nom="Site existant")
        emplacement = Emplacement(site_id=site.id_site, code="RES", nom="Réserve existante")
        with sessionmaker(engine)() as session:
            OrganisationService(SqlAlchemyOrganisationRepository(session)).creer_organisation(org, site, emplacement)
        command.downgrade(config, "20261007_01")
        assert "caisses" not in inspect(engine).get_table_names()
        with sessionmaker(engine)() as session:
            assert SqlAlchemyOrganisationRepository(session).emplacement(emplacement.id_emplacement) == emplacement
        command.upgrade(config, "head")
        command.check(config)
        # This is an isolated test DB; never run this on existing data.
        command.downgrade(config, "29485f21585c")
        assert "organisations" not in inspect(engine).get_table_names()
        command.upgrade(config, "head")
        engine.dispose()
    finally:
        get_settings.cache_clear()
