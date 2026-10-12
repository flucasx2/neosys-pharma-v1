"""Le générateur de recette refuse une base métier et les données existantes."""
import importlib.util
from pathlib import Path
import pytest

spec=importlib.util.spec_from_file_location('recette_comptoir',Path(__file__).resolve().parents[1]/'scripts/recette_comptoir.py')
module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)

@pytest.mark.parametrize('url',[
    'postgresql+psycopg://localhost/neosys_pharma_v1',
    'sqlite:///neosys_pharma_v1.db',
    'sqlite:////tmp/base_metier.db',
    'mysql://localhost/neosys_p46_recette_test',
])
def test_refus_base_metier_avant_connexion(url):
    with pytest.raises(ValueError):module.verifier_base(url)

def test_fichier_neuf_uniquement(tmp_path):
    p=tmp_path/'neosys_p46_recette_test.db';url='sqlite:///'+str(p)
    module.verifier_base(url);assert not p.exists()
    p.write_bytes(b'DONNEES A PRESERVER')
    with pytest.raises(ValueError):module.verifier_base(url)
    assert p.read_bytes()==b'DONNEES A PRESERVER'
