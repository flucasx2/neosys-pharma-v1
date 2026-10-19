"""Recette native sur DEUX bases neuves locales ; aucune suppression de base.

P5C_ADMIN_URL=postgresql://...@localhost:5432/postgres (rôle CREATE DATABASE).
Lancer : python scripts/recette_p5c_postgresql.py --suffixe rc1_20261019
"""
import argparse
import os
import re
import subprocess
import sys
import psycopg
from psycopg import sql
from sqlalchemy.engine import make_url


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--suffixe',required=True)
    args=parser.parse_args()
    if not re.fullmatch(r'[a-z0-9_]{1,24}',args.suffixe):parser.error('Suffixe neuf : a-z, 0-9, _ (24 caractères maximum).')
    url=make_url(os.environ.get('P5C_ADMIN_URL',''))
    if url.get_backend_name()!='postgresql' or url.database!='postgres' or url.host not in ('localhost','127.0.0.1','::1'):
        parser.error('URL PostgreSQL locale de maintenance /postgres exclusivement ; aucune URL métier acceptée.')
    names={'neosys_p4p5_p5c_'+args.suffixe:'NEOSYS_P4P5_DISPOSABLE','neosys_p5c_migrations_'+args.suffixe:'NEOSYS_P5C_DISPOSABLE'}
    pg=url.set(drivername='postgresql').render_as_string(hide_password=False)
    with psycopg.connect(pg,autocommit=True) as c:
        identity=c.execute('select version(), current_database(), current_user, inet_server_addr(), inet_server_port()').fetchone()
        print('Serveur natif / maintenance / rôle / adresse / port :',identity)
        assert identity[1]=='postgres'
        existing=c.execute('select datname from pg_database where datname=ANY(%s)',(list(names),)).fetchall()
        if existing:raise RuntimeError('Base préexistante refusée : '+repr(existing))
        print('Deux bases absentes :',', '.join(names))
        confirmation=input('Recopiez le suffixe pour autoriser uniquement leur création : ')
        if confirmation!=args.suffixe:raise RuntimeError('Création non confirmée.')
        # Aucune opération DROP DATABASE, même après un échec.
        for name,marker in names.items():
            c.execute(sql.SQL('CREATE DATABASE {}').format(sql.Identifier(name)))
            c.execute(sql.SQL('COMMENT ON DATABASE {} IS {}').format(sql.Identifier(name),sql.Literal(marker)))
    app,migration=names
    env=os.environ.copy()
    env.update(TEST_DATABASE_URL=url.set(drivername='postgresql+psycopg',database=app).render_as_string(hide_password=False),
        P4P5_CONFIRM_DATABASE=app,TEST_P5C_MIGRATION_URL=url.set(drivername='postgresql+psycopg',database=migration).render_as_string(hide_password=False),P5C_CONFIRM_DATABASE=migration)
    tests=['tests/test_p5c_creances.py','tests/test_p5c_migration.py','tests/test_p5b_3_encaissement_prise_en_charge.py','tests/test_p4p5_groupe_organismes.py']
    return subprocess.run([sys.executable,'-m','pytest','-q','-rs',*tests],env=env,timeout=900).returncode


if __name__=='__main__':raise SystemExit(main())
