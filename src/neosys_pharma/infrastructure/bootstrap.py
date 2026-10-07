"""python -m neosys_pharma.infrastructure.bootstrap ; jamais exposé en HTTP."""
import sys
from datetime import datetime
from getpass import getpass
from zoneinfo import ZoneInfo
from sqlalchemy import select, text, inspect
from sqlalchemy.exc import SQLAlchemyError
from alembic.config import Config
from alembic.migration import MigrationContext
from alembic.script import ScriptDirectory
from neosys_pharma.application.bootstrap_service import BootstrapService, InstallationInitiale
from neosys_pharma.domain.organisation.entities import Organisation, Site, Emplacement
from neosys_pharma.domain.organisation.permissions_systeme import PERMISSIONS
from neosys_pharma.infrastructure.database import SessionLocal, Base
from neosys_pharma.infrastructure.organisation_repository import SqlAlchemyOrganisationRepository
from neosys_pharma.infrastructure.securite_repository import SqlAlchemySecuriteRepository
from neosys_pharma.infrastructure.authentification_repository import SqlAlchemyAuthRepository
from neosys_pharma.infrastructure.securite_models import RoleModel
from neosys_pharma.infrastructure.passwords import passwords


CATALOGUE_TABLES={'permissions','roles','roles_permissions','auth_tentatives','auth_sessions'}


def verrouiller_installation(session):
    if session.bind.dialect.name == 'postgresql':
        # Shared by both local provisioning commands; released by commit/rollback.
        session.execute(text('SELECT pg_advisory_xact_lock(1789043121)'))


class SqlAlchemyBootstrapRepository:
    def __init__(self, session):
        self.db=session
        self.structure=SqlAlchemyOrganisationRepository(session)
        self.securite=SqlAlchemySecuriteRepository(session)
        self.auth=SqlAlchemyAuthRepository(session)

    def verifier_base_vide(self):
        verrouiller_installation(self.db)
        # Seeded system catalogue and unsuccessful login counters are not an installation.
        for table in Base.metadata.sorted_tables:
            if table.name not in CATALOGUE_TABLES and self.db.scalar(select(table).limit(1)) is not None:
                raise ValueError('Bootstrap refusé : la base contient déjà une structure ou un compte. Utilisez le provisionnement explicite si nécessaire.')
        if self.db.scalar(select(RoleModel.id_role).where(RoleModel.type_role != 'SYSTEME').limit(1)):
            raise ValueError('Bootstrap refusé : un rôle personnalisé existe déjà.')

    def role_initial(self):
        model=self.db.scalar(select(RoleModel).where(RoleModel.code=='GESTION_ORGANISATION',RoleModel.type_role=='SYSTEME',RoleModel.organisation_id.is_(None)))
        if model is None:
            raise ValueError('Catalogue système absent : appliquez alembic upgrade head avant le bootstrap.')
        role=self.securite.role(model.id_role)
        if not role.actif:
            raise ValueError('Le rôle système initial doit être actif.')
        expected={code for code,_ in PERMISSIONS}
        if not expected.issubset({p.code for p in self.securite.permissions_role(role.id_role)}):
            raise ValueError('Catalogue système incomplet : le rôle initial ne possède pas les permissions P1 attendues.')
        return role

    def ajouter(self, entite):
        if isinstance(entite,(Organisation,Site,Emplacement)):
            self.structure.ajouter(entite)
        else:
            self.securite.ajouter(entite)

    def definir_password(self, utilisateur_id, encoded):
        self.auth.definir_password(utilisateur_id,encoded)

    def enregistrer(self):
        self.db.commit()

    def annuler(self):
        self.db.rollback()


def verifier_migrations(session):
    current=MigrationContext.configure(session.connection()).get_current_heads()
    expected=ScriptDirectory.from_config(Config('alembic.ini')).get_heads()
    if set(current)!=set(expected):
        raise ValueError('Base non migrée à jour : exécutez alembic upgrade head avant le bootstrap.')
    required={'organisations','sites','emplacements','utilisateurs','auth_credentials'}
    if not required.issubset(set(inspect(session.connection()).get_table_names())):
        raise ValueError('Schéma incomplet : appliquez les migrations avant le bootstrap.')


def lire(label, maximum):
    value=input(label+' : ').strip()
    if not value or len(value)>maximum:
        raise ValueError(f'{label} doit contenir entre 1 et {maximum} caractères.')
    return value


def main():
    try:
        with SessionLocal() as session:
            verifier_migrations(session)
            repo=SqlAlchemyBootstrapRepository(session)
            # Preflight before asking for personal information; rechecked under lock at write time.
            repo.verifier_base_vide()
            repo.role_initial()
            session.rollback()
            data=InstallationInitiale(
                nom_commercial=lire('Nom commercial de l’organisation',200),
                raison_sociale=lire('Raison sociale',200),
                site_code=lire('Code du premier site',80),site_nom=lire('Nom du premier site',200),
                emplacement_code=lire('Code du premier emplacement',80),emplacement_nom=lire('Libellé du premier emplacement',200),
                identifiant=lire('Identifiant du premier utilisateur',80),utilisateur_nom=lire('Nom du premier utilisateur',200))
            password=getpass('Mot de passe (12–128 caractères) : ')
            if password!=getpass('Confirmation du mot de passe : '):
                raise ValueError('Les mots de passe ne correspondent pas.')
            result=BootstrapService(repo,passwords).initialiser(data,password,datetime.now(ZoneInfo('Africa/Libreville')).date())
            print('Initialisation terminée.')
            print('Organisation (écran de connexion) :',result.organisation_id)
            print('Identifiant utilisateur :',result.identifiant)
            print('Site / emplacement :',result.site_code,'/',result.emplacement_code)
            print('Interface locale : http://127.0.0.1:8000/')
        return 0
    except (ValueError,EOFError,KeyboardInterrupt) as exc:
        print(str(exc) or 'Bootstrap annulé ; aucune initialisation enregistrée.',file=sys.stderr)
        return 1
    except SQLAlchemyError:
        # Do not emit SQL parameters, connection strings or password hashes.
        print('Initialisation refusée : vérifiez la connexion PostgreSQL et les migrations. Aucune initialisation enregistrée.',file=sys.stderr)
        return 1


if __name__=='__main__':
    raise SystemExit(main())
