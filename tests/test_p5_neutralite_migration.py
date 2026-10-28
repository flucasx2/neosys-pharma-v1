"""Migration préparée pour fichier SQLite jetable explicite, sans URL héritée."""
import importlib.util
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4
import pytest
import sqlalchemy as sa
from alembic import command
from alembic.config import Config
from neosys_pharma.infrastructure.config import get_settings


def test_cycle_additif_preserve_modes_historiques(tmp_path, monkeypatch):
    url = "sqlite+pysqlite:///" + (tmp_path / "neutralite_jetable.db").as_posix()
    monkeypatch.setenv("DATABASE_URL", url)
    get_settings.cache_clear()
    engine = sa.create_engine(url)
    modes_historiques = ("SANS_TIERS", "CNAMGS", "MUTUELLE", "CNAMGS_MUTUELLE", "CREDIT")

    def triggers():
        with engine.connect() as connection:
            return dict(connection.execute(sa.text(
                "SELECT name, sql FROM sqlite_master WHERE type='trigger'"
            )).all())

    def mode_checks():
        result = {}
        for table, name in (("ventes", "ck_vente_mode"), ("proforma_versions", "ck_proforma_mode")):
            checks = {c["name"]: c["sqltext"] for c in sa.inspect(engine).get_check_constraints(table)}
            result[name] = checks[name]
        return result

    def insert_vente(mode):
        ident = str(uuid4())
        with engine.begin() as connection:
            connection.execute(sa.text(
                "INSERT INTO ventes (site_id, emplacement_id, poste_id, vendeur_id, etat, mode, "
                "destinataire, revision, cree_le, id, organisation_id) "
                "VALUES (:site, :emplacement, :poste, :vendeur, 'PREPARATION', :mode, '{}', 1, "
                "'2026-10-28T00:00:00+00:00', :id, :organisation)"
            ), {
                "site": str(uuid4()), "emplacement": str(uuid4()), "poste": str(uuid4()),
                "vendeur": str(uuid4()), "mode": mode, "id": ident,
                "organisation": str(uuid4()),
            })
        return ident

    def vente_modes(*identifiants):
        with engine.connect() as connection:
            return dict(connection.execute(sa.text(
                "SELECT id, mode FROM ventes WHERE id IN :identifiants"
            ).bindparams(sa.bindparam("identifiants", expanding=True)),
                {"identifiants": list(identifiants)},
            ).all())

    def revision():
        with engine.connect() as connection:
            return connection.scalar(sa.text("SELECT version_num FROM alembic_version"))

    try:
        cfg = Config("alembic.ini")
        command.upgrade(cfg, "20261022_02")

        # Le point de comparaison est la tête P4 déjà intégrée : les triggers P4-05
        # font partie de l'empreinte protégée et ne sont pas confondus avec P5.
        triggers_p4 = triggers()
        assert "proforma_versions_update_immutable" in triggers_p4
        checks_p4 = mode_checks()
        assert revision() == "20261022_02"
        for definition in checks_p4.values():
            assert all(mode in definition for mode in modes_historiques)
            assert "PRISE_EN_CHARGE" not in definition

        historique_id = insert_vente("SANS_TIERS")
        valeurs_historiques = vente_modes(historique_id)
        assert valeurs_historiques == {historique_id: "SANS_TIERS"}

        command.upgrade(cfg, "20261028_01")
        assert revision() == "20261028_01"
        assert triggers() == triggers_p4
        checks_p5 = mode_checks()
        for definition in checks_p5.values():
            assert all(mode in definition for mode in (*modes_historiques, "PRISE_EN_CHARGE"))
        assert vente_modes(historique_id) == valeurs_historiques
        # Alembic check is valid only at the current graph head. The P5-C1
        # additive migration follows neutrality in this checkout.
        command.upgrade(cfg, "head")
        assert revision() == "20261028_02"
        command.check(cfg)
        command.downgrade(cfg, "20261028_01")
        assert revision() == "20261028_01"

        generique_id = insert_vente("PRISE_EN_CHARGE")
        avant_refus = (revision(), triggers(), mode_checks(), vente_modes(historique_id, generique_id))
        with pytest.raises(RuntimeError, match="opérations génériques"):
            command.downgrade(cfg, "20261022_02")
        assert (revision(), triggers(), mode_checks(), vente_modes(historique_id, generique_id)) == avant_refus

        # Après retrait de l'opération générique, le downgrade sûr doit rendre
        # exactement l'état P4 de référence, y compris les triggers et la ligne historique.
        with engine.begin() as connection:
            connection.execute(sa.text("DELETE FROM ventes WHERE id=:id"), {"id": generique_id})
        command.downgrade(cfg, "20261022_02")
        assert revision() == "20261022_02"
        assert triggers() == triggers_p4
        assert mode_checks() == checks_p4
        assert vente_modes(historique_id) == valeurs_historiques

        command.upgrade(cfg, "20261028_01")
        assert revision() == "20261028_01"
        assert triggers() == triggers_p4
        assert vente_modes(historique_id) == valeurs_historiques
        command.upgrade(cfg, "head")
        assert revision() == "20261028_02"
        command.check(cfg)
    finally:
        engine.dispose()
        get_settings.cache_clear()


@pytest.mark.parametrize("table_occupee", ["ventes", "proforma_versions"])
def test_downgrade_refuse_une_operation_generique_sans_mutation(monkeypatch, table_occupee):
    path = Path(__file__).resolve().parents[1] / "migrations/versions/20261028_01_p5_mode_generique.py"
    spec = importlib.util.spec_from_file_location("migration_neutralite", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    queries = []
    def execute(statement):
        sql = str(statement)
        queries.append(sql)
        return SimpleNamespace(first=lambda: (1,) if f"FROM {table_occupee} " in sql else None)
    monkeypatch.setattr(module, "op", SimpleNamespace(get_bind=lambda: SimpleNamespace(execute=execute)))
    with pytest.raises(RuntimeError, match="opérations génériques"):
        module.downgrade()
    assert queries and all("SELECT" in sql and "PRISE_EN_CHARGE" in sql for sql in queries)
