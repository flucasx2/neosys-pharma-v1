"""Cible MIG P405 fixe : Docker local ou service jetable GitHub Actions explicite."""
import os
from urllib.parse import urlsplit,unquote
DATABASE='neosys_p405_migrations'
ROLE='neosys_test'
MARKER='NEOSYS_P405_MIGRATIONS_DISPOSABLE'

def validate_url(value,environment=None):
    env=os.environ if environment is None else environment
    parsed=urlsplit(value)
    if parsed.scheme!='postgresql+psycopg' or parsed.username!=ROLE or unquote(parsed.path.lstrip('/'))!=DATABASE:
        raise ValueError('Cible MIG P405 non autorisée')
    if parsed.port!=5432 or not parsed.password or parsed.query or parsed.fragment:
        raise ValueError('Paramètres MIG P405 refusés')
    if parsed.hostname=='test-db':return
    ci=(parsed.hostname=='localhost' and env.get('GITHUB_ACTIONS')=='true' and env.get('CI')=='true'
        and env.get('P405_CONFIRM_DATABASE')==DATABASE and env.get('TEST_P405_MIGRATION_DATABASE_URL')==value)
    if not ci:raise ValueError('Orchestration MIG P405 absente ou hôte interdit')

def validate_server(database,role,marker,read_only):
    if (database,role,marker,read_only)!=(DATABASE,ROLE,MARKER,'on'):
        raise ValueError('Identité SQL MIG P405 ou transaction read-only refusée')
