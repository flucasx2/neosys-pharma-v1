"""Comptes Catalogue explicites sur la base navigateur CI, après recette P1."""
import json
from pathlib import Path
from uuid import UUID
from neosys_pharma.infrastructure.database import SessionLocal
from neosys_pharma.infrastructure.securite_repository import SqlAlchemySecuriteRepository
from neosys_pharma.infrastructure.provisionnement import provisionner
from neosys_pharma.domain.organisation.securite import Utilisateur, Role, RolePermission, TypeRole
from neosys_pharma.domain.organisation.permissions_systeme import permission_id

fixture=json.loads(Path('/tmp/p1-browser-fixture.json').read_text())
org,site,location=(UUID(fixture[key]) for key in ('organisation_id','site_id','location_id'))
with SessionLocal() as session:
    repo=SqlAlchemySecuriteRepository(session)
    for identifiant,permissions in [('catalogue.qa',('catalogue.consulter','catalogue.gerer')),('catalogue.lecture.qa',('catalogue.consulter',))]:
        role=Role(organisation_id=org,code=identifiant,nom=identifiant,type_role=TypeRole.PERSONNALISE)
        repo.ajouter(role)
        for code in permissions:repo.ajouter(RolePermission(role_id=role.id_role,permission_id=permission_id(code)))
        session.commit()
        user=Utilisateur(organisation_id=org,identifiant=identifiant,nom=identifiant)
        provisionner(session,user,[site],[location],[role.id_role],fixture['password'])
