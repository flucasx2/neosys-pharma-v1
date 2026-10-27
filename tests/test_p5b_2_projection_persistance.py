"""Tests ciblés de la projection stricte P5-A -> P5-B.1."""
from datetime import date
from types import SimpleNamespace
from uuid import uuid4

import pytest

from neosys_pharma.application.projection_prise_en_charge import (
    RegleConventionInvalide, projeter_convention,
)
from neosys_pharma.application.prise_en_charge_persistante_service import _xaf_value
from neosys_pharma.domain.prise_en_charge import ModeArrondi


def convention(**changes):
    row = dict(
        id=uuid4(), organisation_id=uuid4(), organisme_id=uuid4(), code="CTR-A",
        version=3, date_debut=date(2026, 1, 1), date_fin=None, statut="ACTIVE",
        reference_contractuelle="REF-3", conditions={"schema_version": 1},
        extensions_p5b={
            "schema_version": 1,
            "baremes": [{"code": "BASE", "taux_numerateur": 80,
                         "taux_denominateur": 100, "plafond_ligne_xaf": 9000,
                         "produits_ids": [], "categories_ids": ["CAT-A"],
                         "arrondi": "PLANCHER"}],
            "exclusions": {"produits_ids": [], "categories_ids": ["CAT-X"]},
        },
    )
    row.update(changes)
    return SimpleNamespace(**row)


def test_projection_stricte_conserve_versions_taux_plafond_et_exclusions():
    result = projeter_convention(convention())
    assert result.version == 3
    assert result.baremes[0].fraction_taux.numerator == 4
    assert result.baremes[0].plafond_ligne_xaf == 9000
    assert result.baremes[0].arrondi is ModeArrondi.PLANCHER
    assert result.exclusions_categories == ("CAT-X",)


@pytest.mark.parametrize("field, value", [
    ("conditions", {"reference": "legacy-untyped"}),
    ("extensions_p5b", {"schema_version": 1, "baremes": [], "exclusions": {}, "plafond_global": 100}),
    ("extensions_p5b", {"schema_version": 2, "baremes": [], "exclusions": {"produits_ids": [], "categories_ids": []}}),
])
def test_projection_refuse_clause_inconnue_ou_version_non_supportee(field, value):
    with pytest.raises(RegleConventionInvalide):
        projeter_convention(convention(**{field: value}))


def test_projection_refuse_une_regle_incomplete_et_arrondi_inconnu():
    row = convention()
    row.extensions_p5b["baremes"][0]["arrondi"] = "ARRONDI_NON_CONTRACTUEL"
    with pytest.raises(RegleConventionInvalide):
        projeter_convention(row)


def test_montants_vente_convertis_uniquement_si_xaf_entiers():
    assert _xaf_value("1234") == 1234
    with pytest.raises(ValueError):
        _xaf_value("1234.5")
