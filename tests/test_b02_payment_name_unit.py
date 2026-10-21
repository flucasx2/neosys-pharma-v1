"""Validation B02 existante du nom : aucun moteur ni accès de base."""
from types import SimpleNamespace
from unittest.mock import Mock
from uuid import uuid4

import pytest

from neosys_pharma.application.caisse_service import CaisseService


@pytest.mark.parametrize('libelle', ['', '   ', '\t \n'])
@pytest.mark.parametrize('key', [None, uuid4()])
def test_nom_vide_refuse_avant_acces_base(libelle, key):
    service = CaisseService.__new__(CaisseService)
    service.stock = SimpleNamespace(access=Mock(), obtenir=Mock(), ajouter=Mock())
    service.site = 'site-simule'
    service.trace = Mock()
    with pytest.raises(ValueError, match='Libellé de moyen invalide'):
        service.definir_moyen({'libelle': libelle}, key)
    service.stock.obtenir.assert_not_called()
    service.stock.ajouter.assert_not_called()
    service.trace.assert_not_called()
