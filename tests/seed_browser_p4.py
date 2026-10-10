"""Recette P4 isolée : stock physique explicitement saisi, droits explicitement affectés."""
import json
from pathlib import Path
from uuid import UUID,uuid4
from datetime import date,timedelta
from neosys_pharma.infrastructure.database import SessionLocal
from neosys_pharma.infrastructure.securite_repository import SqlAlchemySecuriteRepository
from neosys_pharma.infrastructure.catalogue_repository import SqlAlchemyCatalogueRepository
from neosys_pharma.application.catalogue_service import CatalogueService
from neosys_pharma.application.tarification_service import TarificationService
from neosys_pharma.infrastructure.provisionnement import provisionner
from neosys_pharma.domain.organisation.securite import Role,RolePermission,TypeRole,Utilisateur
from neosys_pharma.domain.organisation.permissions_systeme import P4_PERMISSIONS,permission_id
from neosys_pharma.domain.catalogue import CategorieProduit,Produit,Conditionnement,ReferenceProduit,TypeReference
from neosys_pharma.domain.tarification import TarifReference,TarifProduitSite
from neosys_pharma.infrastructure.organisation_models import PosteVenteModel,CaisseModel
from neosys_pharma.infrastructure.vente_models import PlafondRemiseModel
from neosys_pharma.application.stock_service import StockService
f=json.loads(Path('/tmp/p1-browser-fixture.json').read_text());org,site,loc=[UUID(f[k]) for k in ('organisation_id','site_id','location_id')]
with SessionLocal() as s:
    repo=SqlAlchemySecuriteRepository(s);roles={};users={}
    for name,perms in [('vente.qa',tuple(p for p,n in P4_PERMISSIONS if p!='vente.remise.autoriser')+('stock.reserver','stock.consulter','organisation.consulter')),('responsable.qa',('vente.consulter','vente.remise.autoriser','proforma.consulter','organisation.consulter')),('vente.lecture.qa',('vente.consulter','proforma.consulter','organisation.consulter'))]:
        r=Role(organisation_id=org,code=name,nom=name,type_role=TypeRole.PERSONNALISE);repo.ajouter(r)
        for p in perms:repo.ajouter(RolePermission(role_id=r.id_role,permission_id=permission_id(p)))
        s.commit();u=Utilisateur(organisation_id=org,identifiant=name,nom=name);provisionner(s,u,[site],[loc],[r.id_role],f['password']);roles[name]=r.id_role;users[name]=u.id_utilisateur
    # Configuration only for this explicit test approver role, never default production caps.
    s.add(PlafondRemiseModel(organisation_id=org,role_id=roles['responsable.qa'],max_pourcentage=20,max_montant_xaf=1000));s.commit()
    catalogue=CatalogueService(SqlAlchemyCatalogueRepository(s));cat=CategorieProduit(organisation_id=org,code='P4-QA',nom='Préparation P4');catalogue.enregistrer(cat)
    prod=Produit(organisation_id=org,nom='Préparation vente QA P4',categorie_id=cat.id_categorie);pack=Conditionnement(organisation_id=org,produit_id=prod.id_produit,code='P4-B20',libelle='Boîte de 20 P4')
    catalogue.enregistrer(prod,nouveau=True,premier_conditionnement=pack)
    catalogue.enregistrer(ReferenceProduit(organisation_id=org,conditionnement_id=pack.id_conditionnement,type_reference=TypeReference.CIP7,valeur='8812345'))
    catalogue.enregistrer(ReferenceProduit(organisation_id=org,conditionnement_id=pack.id_conditionnement,type_reference=TypeReference.EAN,valeur='8812345678901'))
    second=Conditionnement(organisation_id=org,produit_id=prod.id_produit,code='P4-B60',libelle='Boîte de 60 P4');catalogue.enregistrer(second)
    tarifs=TarificationService(catalogue)
    for p in [pack,second]:
        tarifs.enregistrer(TarifReference(organisation_id=org,conditionnement_id=p.id_conditionnement,montant_ht=100,devise='XAF',debut=date.today()))
        # Isolate this QA product from site coefficients configured by P2 browser tests.
        tarifs.enregistrer(TarifProduitSite(organisation_id=org,site_id=site,produit_id=prod.id_produit,conditionnement_id=p.id_conditionnement,montant_ht=100,devise='XAF',debut=date.today()-timedelta(days=1),provenance='Recette isolée P4'))
    poste,caisse=uuid4(),uuid4();s.add_all([PosteVenteModel(id_poste_vente=poste,emplacement_id=loc,code='P4-QA',nom='Poste préparation P4'),CaisseModel(id_caisse=caisse,emplacement_id=loc,code='P4-QA',nom='Caisse P4')]);s.commit()
    stock=StockService(s,org,users['vente.qa'],lambda *args:None)
    for p in [pack,second]:
        l=stock.operation(uuid4(),'LOT',{},lambda:stock.creer_lot({'conditionnement_id':p.id_conditionnement}))
        stock.operation(uuid4(),'ENTREE',{},lambda:stock.entree({'lot_id':l['id'],'emplacement_id':loc,'quantite':30,'origine':'Stock physique recette P4','justification':'Quantités saisies explicitement pour les tests'}))
    f.update(p4_product=str(prod.id_produit),p4_pack=str(pack.id_conditionnement),p4_poste=str(poste),p4_caisse=str(caisse))
Path('/tmp/p1-browser-fixture.json').write_text(json.dumps(f))
