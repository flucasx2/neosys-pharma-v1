"""Garde les deux versions natives obligatoires et leurs bases jetables qualifiées."""
from pathlib import Path
import sys
import unittest
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'ci'))
from policy import verdict


class ConsolidationWorkflowTest(unittest.TestCase):
    def setUp(self):
        self.workflow=(ROOT/'.github/workflows/tests.yml').read_text()
        self.postgres=self.workflow.split('\n  postgres:\n',1)[1].split('\n  browser:\n',1)[0]

    def test_matrice_native_et_aucune_exclusion_de_tests(self):
        self.assertRegex(self.postgres,r'postgresql: \[17, 18\]')
        self.assertIn('fail-fast: false',self.postgres)
        self.assertIn('image: postgres:${{ matrix.postgresql }}',self.postgres)
        self.assertIn('run: pytest -q',self.postgres)
        self.assertNotIn('--ignore',self.postgres)

    def test_noms_confirmations_et_marqueurs_restent_coherents(self):
        for name,marker,confirmation in (
            ('neosys_p4p5_ci','NEOSYS_P4P5_DISPOSABLE','P4P5_CONFIRM_DATABASE'),
            ('neosys_consolidation_migrations_ci','NEOSYS_CONSOLIDATION_MIGRATIONS_DISPOSABLE','CONSOLIDATION_CONFIRM_DATABASE'),
            ('neosys_p5conf1b_ci','NEOSYS_P5CONF1B_DISPOSABLE_CI','P5CONF1B_CONFIRM_DATABASE'),
            ('neosys_p5c_migrations_ci','NEOSYS_P5C_DISPOSABLE','P5C_CONFIRM_DATABASE'),
            ('neosys_p5c2_migrations_ci','NEOSYS_P5C2_DISPOSABLE','P5C2_CONFIRM_DATABASE')):
            self.assertIn(f'/{name}',self.postgres)
            self.assertIn(f"COMMENT ON DATABASE {name} IS '{marker}'",self.postgres)
            self.assertIn(f'{confirmation}: {name}',self.postgres)
        self.assertIn('P5CONF1B_MARKER: NEOSYS_P5CONF1B_DISPOSABLE_CI',self.postgres)

    def test_synthese_ne_passe_pas_si_matrice_echoue_ou_ignoree(self):
        self.assertIn('needs: [changes, sqlite, postgres, browser]',self.workflow)
        sha='a'*40
        for result in ('failure','skipped','cancelled'):
            state,_=verdict(True,{'sqlite':'success','postgres':result,'browser':'success'},sha,sha,sha)
            self.assertNotEqual(state,'success')
        self.assertIn('needs.postgres.result',self.workflow)

    def test_simulation_et_parcours_reel_restent_distingues(self):
        browser=self.workflow.split('\n  browser:\n',1)[1].split('\n  result:\n',1)[0]
        self.assertIn('HTTP simulated, no financial evidence',browser)
        self.assertIn('node tests/creances_ui.cjs --chromium',browser)
        self.assertIn('node tests/facturation_organisme_ui.cjs --chromium',browser)
        self.assertIn('python .ci-control/ci/browser.py',browser)
        self.assertIn("GROUPED_ENCASHMENT_ENABLED: 'true'",browser)
        self.assertIn('POSTGRES_DB: neosys_browser',browser)

if __name__=='__main__':unittest.main()
