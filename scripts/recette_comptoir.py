"""Préparer une recette humaine P4.6 exclusivement sur une base dédiée jetable."""
import argparse
import os
from pathlib import Path
import subprocess
import sys
from sqlalchemy.engine import make_url

ROOT=Path(__file__).resolve().parents[1]

def verifier_base(url):
    parsed=make_url(url)
    if parsed.get_backend_name()=='sqlite':
        path=Path(parsed.database or '')
        if not path.is_absolute() or not path.name.startswith('neosys_p46_recette_') or path.suffix!='.db':
            raise ValueError('Fichier SQLite absolu neosys_p46_recette_*.db obligatoire.')
        if path.exists():raise ValueError('La recette exige un fichier neuf ; aucune donnée existante écrasée.')
    elif parsed.get_backend_name()=='postgresql':
        if not (parsed.database or '').startswith('neosys_p46_recette_'):
            raise ValueError('Base PostgreSQL isolée neosys_p46_recette_* obligatoire.')
        from sqlalchemy import create_engine,inspect
        engine=create_engine(url)
        try:
            if inspect(engine).get_table_names():raise ValueError('La base doit être vide ; aucune donnée existante écrasée.')
        finally:engine.dispose()
    else:raise ValueError('SQLite ou PostgreSQL requis.')

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--database-url',required=True)
    parser.add_argument('--confirmer-base-jetable',action='store_true',required=True)
    args=parser.parse_args();verifier_base(args.database_url)
    env=os.environ.copy();env['DATABASE_URL']=args.database_url;env['AUTH_COOKIE_SECURE']='false'
    subprocess.run([sys.executable,'-m','alembic','upgrade','head'],cwd=ROOT,env=env,check=True)
    for seed in ('seed_browser.py','seed_browser_p4.py','seed_browser_caisse.py','seed_browser_regularisation.py'):
        subprocess.run([sys.executable,'tests/'+seed],cwd=ROOT,env=env,check=True)
    print('Recette fictive préparée. Identités et mot de passe aléatoire dans /tmp/p1-browser-fixture.json ; ne pas publier ce fichier.')

if __name__=='__main__':main()
