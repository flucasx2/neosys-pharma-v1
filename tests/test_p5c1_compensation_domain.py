from uuid import uuid4

import pytest

from neosys_pharma.domain.compensation_creance import organisme_unique


def test_retour_a_un_seul_payeur_est_attribuable():
    organisme = uuid4()
    assert organisme_unique([(organisme, 700)], 250, 700) == organisme


def test_retour_multi_organismes_reste_ambigu():
    with pytest.raises(ValueError, match="multi-organismes"):
        organisme_unique([(uuid4(), 300), (uuid4(), 400)], 250, 700)


def test_retour_refuse_si_ventilation_historique_incoherente():
    with pytest.raises(ValueError, match="différentes du total"):
        organisme_unique([(uuid4(), 300)], 250, 700)


def test_part_nulle_sans_part_organisme_ne_cree_pas_de_compensation():
    assert organisme_unique([], 0, 0) is None
