"""Contrat CI P405 : service et base marqués, aucune exclusion du test."""
from pathlib import Path
import unittest
class P405Workflow(unittest.TestCase):
    def setUp(self):self.text=(Path(__file__).resolve().parents[2]/'.github/workflows/tests.yml').read_text(encoding='utf-8')
    def test_specific_migration_database_and_marker(self):
        for part in ["CREATE DATABASE neosys_p405_migrations","COMMENT ON DATABASE neosys_p405_migrations IS 'NEOSYS_P405_MIGRATIONS_DISPOSABLE'",'TEST_P405_MIGRATION_DATABASE_URL:','P405_CONFIRM_DATABASE: neosys_p405_migrations']:
            self.assertIn(part,self.text)
        self.assertIn('TEST_MIGRATION_DATABASE_URL:',self.text)
    def test_p405_js_is_scheduled(self):
        self.assertIn('node tests/p405_finance_ui.cjs',self.text);self.assertIn('node tests/p405_navigation_retour.cjs',self.text)
    def test_full_native_matrix_and_no_ignore(self):
        postgres=self.text.split('\n  postgres:\n',1)[1].split('\n  browser:\n',1)[0]
        self.assertIn('postgresql: [17, 18]',postgres);self.assertIn('run: pytest -q',postgres);self.assertNotIn('--ignore',postgres)
