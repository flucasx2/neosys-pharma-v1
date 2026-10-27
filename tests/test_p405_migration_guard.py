"""Gardes purs, aucun SQL et aucune URL héritée du poste."""
import unittest
from p405_migration_guard import DATABASE,ROLE,MARKER,validate_url,validate_server

def url(host='test-db',database=DATABASE,role=ROLE,port=5432):
    return f'postgresql+psycopg://{role}:fixture-only@{host}:{port}/{database}'
def ci(value):return {'GITHUB_ACTIONS':'true','CI':'true','P405_CONFIRM_DATABASE':DATABASE,'TEST_P405_MIGRATION_DATABASE_URL':value}
class Guards(unittest.TestCase):
    def test_local_fixed_target(self):validate_url(url(),{})
    def test_ci_explicit_fixed_target(self):
        value=url('localhost');validate_url(value,ci(value))
    def test_localhost_without_ci_refused(self):
        with self.assertRaises(ValueError):validate_url(url('localhost'),{})
    def test_each_ci_attestation_required(self):
        value=url('localhost')
        for key in ci(value):
            env=ci(value);env.pop(key)
            with self.subTest(key=key),self.assertRaises(ValueError):validate_url(value,env)
    def test_conserved_databases_refused_before_sql(self):
        for database in ['neosys_browser','neosys_pharma_v1','neosys_docker_dev','neosys_restore_verify','neosys_migration']:
            value=url('localhost',database)
            with self.subTest(database=database),self.assertRaises(ValueError):validate_url(value,ci(value))
    def test_other_hosts_ports_roles_refused(self):
        for value in [url('127.0.0.1'),url('db'),url('host.docker.internal'),url(port=5433),url(role='neosys_dev')]:
            with self.subTest(value=value),self.assertRaises(ValueError):validate_url(value,ci(value))
    def test_query_override_and_fragment_refused(self):
        for value in [url()+'?host=elsewhere',url()+'#host',url().replace('postgresql+psycopg','postgresql')]:
            with self.assertRaises(ValueError):validate_url(value,{})
    def test_server_identity_and_marker_are_required(self):
        validate_server(DATABASE,ROLE,MARKER,'on')
        for values in [('neosys_browser',ROLE,MARKER,'on'),(DATABASE,'neosys_dev',MARKER,'on'),(DATABASE,ROLE,None,'on'),(DATABASE,ROLE,MARKER,'off')]:
            with self.assertRaises(ValueError):validate_server(*values)
