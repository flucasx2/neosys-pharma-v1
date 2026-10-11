"""P4.5 fixtures synthétiques jetables : affectations explicites, aucun accès implicite."""
import json
from pathlib import Path
from uuid import UUID,uuid4
from sqlalchemy import select
from neosys_pharma.infrastructure.database import SessionLocal
from neosys_pharma.infrastructure.securite_models import RoleModel,RolePermissionModel
from neosys_pharma.infrastructure.organisation_models import CoffreModel
from neosys_pharma.infrastructure.securite_repository import SqlAlchemySecuriteRepository
from neosys_pharma.infrastructure.provisionnement import provisionner
from neosys_pharma.domain.organisation.securite import Role,RolePermission,TypeRole,Utilisateur
from neosys_pharma.domain.organisation.permissions_systeme import REGULARISATION_PERMISSIONS,CAISSE_PERMISSIONS,permission_id
f=json.loads(Path('/tmp/p1-browser-fixture.json').read_text());org,site,loc=[UUID(f[k]) for k in ('organisation_id','site_id','location_id')]
with SessionLocal() as s:
    rid=s.scalar(select(RoleModel.id_role).where(RoleModel.organisation_id==org,RoleModel.code=='caisse.qa'))
    for code,label in REGULARISATION_PERMISSIONS:s.add(RolePermissionModel(role_id=rid,permission_id=permission_id(code)))
    read=s.scalar(select(RoleModel.id_role).where(RoleModel.organisation_id==org,RoleModel.code=='caisse.lecture.qa'))
    for code in ('caisse.cloture.consulter','stock.quarantaine.consulter'):s.add(RolePermissionModel(role_id=read,permission_id=permission_id(code)))
    coffre=CoffreModel(id_coffre=uuid4(),site_id=site,code='COFFRE-P45-QA',nom='Coffre de recette P4.5');s.add(coffre);s.commit();f['p45_coffre']=str(coffre.id_coffre)
    repo=SqlAlchemySecuriteRepository(s);r=Role(organisation_id=org,code='responsable.p45.qa',nom='Responsable P4.5 QA',type_role=TypeRole.PERSONNALISE);repo.ajouter(r)
    for code in ('organisation.consulter',)+tuple(x for x,n in CAISSE_PERMISSIONS+REGULARISATION_PERMISSIONS):repo.ajouter(RolePermission(role_id=r.id_role,permission_id=permission_id(code)))
    s.commit();u=Utilisateur(organisation_id=org,identifiant='responsable.p45.qa',nom='Responsable de recette P4.5');provisionner(s,u,[site],[loc],[r.id_role],f['password'])
Path('/tmp/p1-browser-fixture.json').write_text(json.dumps(f))
