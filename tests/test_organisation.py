import pytest

from neosys_pharma.domain.organisation.entities import Organisation, Site


def test_creer_organisation_valide() -> None:
    organisation = Organisation(
        nom_commercial="Grande Pharmacie des Forestiers",
        raison_sociale="Grande Pharmacie des Forestiers SARL",
    )

    assert organisation.id_organisation is not None
    assert organisation.nom_commercial == "Grande Pharmacie des Forestiers"
    assert organisation.actif is True


def test_nom_commercial_obligatoire() -> None:
    with pytest.raises(ValueError, match="nom commercial"):
        Organisation(
            nom_commercial="   ",
            raison_sociale="Pharmacie Test SARL",
        )


def test_raison_sociale_obligatoire() -> None:
    with pytest.raises(ValueError, match="raison sociale"):
        Organisation(
            nom_commercial="Pharmacie Test",
            raison_sociale="   ",
        )

def test_creer_site_valide() -> None:
    organisation = Organisation(
        nom_commercial="NeoPharma",
        raison_sociale="NeoPharma SARL",
    )

    site = Site(
        organisation_id=organisation.id_organisation,
        code="libreville-centre",
        nom="Libreville Centre",
    )

    assert site.id_site is not None
    assert site.organisation_id == organisation.id_organisation
    assert site.code == "LIBREVILLE-CENTRE"
    assert site.actif is True


def test_code_site_obligatoire() -> None:
    organisation = Organisation(
        nom_commercial="NeoPharma",
        raison_sociale="NeoPharma SARL",
    )

    with pytest.raises(ValueError, match="code du site"):
        Site(
            organisation_id=organisation.id_organisation,
            code="   ",
            nom="Libreville Centre",
        )


def test_nom_site_obligatoire() -> None:
    organisation = Organisation(
        nom_commercial="NeoPharma",
        raison_sociale="NeoPharma SARL",
    )

    with pytest.raises(ValueError, match="nom du site"):
        Site(
            organisation_id=organisation.id_organisation,
            code="LBV01",
            nom="   ",
        )
