"""Cycle Alembic P4-C sur SQLite temporaire et PostgreSQL natif CI explicitement jetable."""
import os
from pathlib import Path
from uuid import uuid4

import pytest
import sqlalchemy as sa
from alembic import command
from alembic.config import Config
from alembic.script import ScriptDirectory

from neosys_pharma.infrastructure.config import get_settings
from neosys_pharma.infrastructure.database import Base


ROOT = Path(__file__).resolve().parents[1]
P4C_TABLES = {
    "caisse_encaissements_groupes",
    "caisse_encaissements_groupes_ventes",
    "caisse_reglements_groupes",
    "caisse_allocations_reglements_groupes",
    "caisse_mouvements_groupes",
}
PROTECTED_DATABASES = {"neosys_pharma_v1", "neosys_p46_recette_20261012"}


def _seed_existing_client(engine):
    organisation_id, client_id = uuid4(), uuid4()
    organisations = sa.table(
        "organisations",
        sa.column("id_organisation", sa.Uuid()),
        sa.column("nom_commercial", sa.String()),
        sa.column("raison_sociale", sa.String()),
        sa.column("logo", sa.String()),
        sa.column("coordonnees", sa.String()),
        sa.column("informations_legales", sa.String()),
        sa.column("actif", sa.Boolean()),
    )
    clients = sa.table(
        "clients",
        sa.column("id", sa.Uuid()),
        sa.column("organisation_id", sa.Uuid()),
        sa.column("nom", sa.String()),
        sa.column("telephone", sa.String()),
        sa.column("courriel", sa.String()),
        sa.column("actif", sa.Boolean()),
        sa.column("revision", sa.Integer()),
    )
    with engine.begin() as connection:
        connection.execute(
            sa.insert(organisations).values(
                id_organisation=organisation_id,
                nom_commercial="P4-C Migration QA",
                raison_sociale="P4-C Migration QA",
                logo=None,
                coordonnees=None,
                informations_legales=None,
                actif=True,
            )
        )
        connection.execute(
            sa.insert(clients).values(
                id=client_id,
                organisation_id=organisation_id,
                nom="Client conservé",
                telephone="070000001",
                courriel=None,
                actif=True,
                revision=1,
            )
        )
    return organisation_id, client_id


def _migration_cycle(url, monkeypatch, *, expected_database=None):
    parsed = sa.engine.make_url(url)
    assert parsed.database not in PROTECTED_DATABASES
    if expected_database:
        assert parsed.drivername.startswith("postgresql+psycopg")
        assert parsed.database == expected_database
        assert parsed.username == "neosys_test"
        assert parsed.host == "localhost" and parsed.port == 5432

    monkeypatch.setenv("DATABASE_URL", url)
    get_settings.cache_clear()
    engine = sa.create_engine(url)
    cfg = Config(str(ROOT / "alembic.ini"))
    try:
        if expected_database:
            with engine.connect() as connection:
                assert connection.scalar(sa.text("SELECT current_database()")) == expected_database
                assert int(connection.scalar(sa.text("SHOW server_version_num"))) >= 120000
                assert sa.inspect(connection).get_table_names() == [], "La base PostgreSQL jetable doit être neuve."

        command.upgrade(cfg, "20261015_01")
        organisation_id, client_id = _seed_existing_client(engine)
        command.upgrade(cfg, "head")
        with engine.connect() as connection:
            inspector = sa.inspect(connection)
            assert P4C_TABLES <= set(inspector.get_table_names())
            assert connection.scalar(sa.text("SELECT version_num FROM alembic_version")) == ScriptDirectory.from_config(cfg).get_current_head()
            assert connection.execute(
                sa.text("SELECT nom FROM clients WHERE id=:id AND organisation_id=:org").bindparams(
                    sa.bindparam("id", type_=sa.Uuid()), sa.bindparam("org", type_=sa.Uuid())
                ),
                {"id": client_id, "org": organisation_id},
            ).scalar_one() == "Client conservé"
            assert any(
                constraint.get("column_names") == ["vente_id"]
                for constraint in inspector.get_unique_constraints("caisse_encaissements")
            ), "L'unicité historique d'un encaissement par vente doit rester effective."
            dossier_constraints = inspector.get_check_constraints("caisse_encaissements_groupes")
            assert {"ck_enc_groupe_idempotence", "ck_enc_groupe_empreinte_sha256"} <= {
                constraint.get("name") for constraint in dossier_constraints
            }
            assert any(
                constraint.get("name") == "uq_enc_groupe_idempotence_org"
                and constraint.get("column_names") == ["organisation_id", "cle_idempotence"]
                for constraint in inspector.get_unique_constraints("caisse_encaissements_groupes")
            )
            member_fks = inspector.get_foreign_keys("caisse_encaissements_groupes_ventes")
            assert any(
                fk.get("name") == "fk_enc_groupe_vente_vente_site"
                and fk.get("referred_table") == "ventes"
                and fk.get("constrained_columns") == ["vente_id", "organisation_id", "site_id"]
                for fk in member_fks
            )
            for table_name in P4C_TABLES:
                assert set(Base.metadata.tables[table_name].columns.keys()) <= {
                    column["name"] for column in inspector.get_columns(table_name)
                }, f"Colonnes ORM absentes de la migration : {table_name}"
            group_fks = inspector.get_foreign_keys("caisse_encaissements_groupes")
            assert {"fk_enc_groupe_session_site", "fk_encaissement_groupe_periode_site"} <= {
                fk.get("name") for fk in group_fks
            }
            payment_fks = inspector.get_foreign_keys("caisse_reglements_groupes")
            assert any(fk.get("referred_table") == "caisse_confirmations" for fk in payment_fks)
            assert any(
                constraint.get("column_names") == ["confirmation_id"]
                for constraint in inspector.get_unique_constraints("caisse_reglements_groupes")
            ), "Une confirmation ne peut apparaître qu'une fois dans les règlements groupés."

        command.downgrade(cfg, "20261015_01")
        with engine.connect() as connection:
            inspector = sa.inspect(connection)
            assert not (P4C_TABLES & set(inspector.get_table_names()))
            assert connection.execute(
                sa.text("SELECT nom FROM clients WHERE id=:id AND organisation_id=:org").bindparams(
                    sa.bindparam("id", type_=sa.Uuid()), sa.bindparam("org", type_=sa.Uuid())
                ),
                {"id": client_id, "org": organisation_id},
            ).scalar_one() == "Client conservé"
        command.upgrade(cfg, "head")
        with engine.connect() as connection:
            assert P4C_TABLES <= set(sa.inspect(connection).get_table_names())
    finally:
        engine.dispose()
        get_settings.cache_clear()


def test_migration_p4c_cycle_sur_base_sqlite_temporaire(tmp_path, monkeypatch):
    url = f"sqlite+pysqlite:///{tmp_path / 'p4c-migration.sqlite3'}"
    _migration_cycle(url, monkeypatch)


def test_migration_p4c_postgresql_natif_sur_base_jetable(monkeypatch):
    url = os.getenv("TEST_P4C_MIGRATION_DATABASE_URL")
    if not url or os.getenv("P4C_CI_DISPOSABLE_DATABASE") != "1":
        pytest.skip("Base PostgreSQL P4-C non explicitement jetable : migration native non exécutée.")
    parsed = sa.engine.make_url(url)
    assert parsed.database == "neosys_p4c_migration", "Refus : base PostgreSQL hors cible jetable dédiée."
    _migration_cycle(url, monkeypatch, expected_database="neosys_p4c_migration")
