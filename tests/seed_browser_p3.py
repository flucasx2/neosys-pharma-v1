"""Comptes de recette P3 explicitement affectés, sans enrichir les rôles P1/P2."""
import json
from pathlib import Path
from uuid import UUID
from neosys_pharma.infrastructure.database import SessionLocal
from neosys_pharma.infrastructure.securite_repository import SqlAlchemySecuriteRepository
from neosys_pharma.infrastructure.organisation_repository import SqlAlchemyOrganisationRepository
from neosys_pharma.infrastructure.catalogue_repository import SqlAlchemyCatalogueRepository
from neosys_pharma.application.catalogue_service import CatalogueService
from neosys_pharma.infrastructure.provisionnement import provisionner
from neosys_pharma.domain.organisation.entities import Site,Emplacement
from neosys_pharma.domain.organisation.securite import Utilisateur,Role,RolePermission,TypeRole
from neosys_pharma.domain.organisation.permissions_systeme import permission_id,P3_PERMISSIONS
from neosys_pharma.domain.catalogue import CategorieProduit,Produit,Conditionnement,ReferenceProduit,TypeReference

fixture=json.loads(Path('/tmp/p1-browser-fixture.json').read_text());org,site,location=(UUID(fixture[key]) for key in ('organisation_id','site_id','location_id'))
with SessionLocal() as s:
    repo=SqlAlchemyOrganisationRepository(s);dest=Emplacement(site_id=site,code='DEST-P3',nom='Destination interne P3');other=Site(organisation_id=org,code='SITE-P3',nom='Site destination P3');otherloc=Emplacement(site_id=other.id_site,code='R-P3',nom='Réserve intersite P3')
    for x in (dest,other,otherloc):repo.ajouter(x)
    s.commit();security=SqlAlchemySecuriteRepository(s);users={}
    for username,permissions in [('stock.qa',tuple(p for p,n in P3_PERMISSIONS)+('organisation.consulter',)),('stock.lecture.qa',('stock.consulter','organisation.consulter')),('stock.compteur.qa',('stock.inventaire.compter',))]:
        role=Role(organisation_id=org,code=username,nom=username,type_role=TypeRole.PERSONNALISE);security.ajouter(role)
        for p in permissions:security.ajouter(RolePermission(role_id=role.id_role,permission_id=permission_id(p)))
        s.commit();user=Utilisateur(organisation_id=org,identifiant=username,nom=username)
        provisionner(s,user,[site,other.id_site] if username=='stock.qa' else [site],[location,dest.id_emplacement,otherloc.id_emplacement] if username=='stock.qa' else [location],[role.id_role],fixture['password']);users[username]=str(user.id_utilisateur)
    catalogue=CatalogueService(SqlAlchemyCatalogueRepository(s));cat=CategorieProduit(organisation_id=org,code='P3-QA',nom='Stock QA P3',gestion_lot=True,gestion_peremption=True,fefo=True);catalogue.enregistrer(cat)
    prod=Produit(organisation_id=org,nom='Stock QA P3',categorie_id=cat.id_categorie);pack=Conditionnement(organisation_id=org,produit_id=prod.id_produit,code='B20-P3',libelle='Boîte de 20')
    catalogue.enregistrer(prod,nouveau=True,premier_conditionnement=pack);catalogue.enregistrer(ReferenceProduit(organisation_id=org,conditionnement_id=pack.id_conditionnement,type_reference=TypeReference.CIP7,valeur='9912345'))
    fixture.update(p3_pack=str(pack.id_conditionnement),p3_destination=str(dest.id_emplacement),p3_other_site=str(other.id_site),p3_other_location=str(otherloc.id_emplacement),p3_users=users)
Path('/tmp/p1-browser-fixture.json').write_text(json.dumps(fixture))
