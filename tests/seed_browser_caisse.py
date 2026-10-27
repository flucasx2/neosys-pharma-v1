"""Données synthétiques indépendantes pour encaissement P4.4, jamais en production."""
import json
from pathlib import Path
from uuid import UUID,uuid4
from datetime import date
from neosys_pharma.infrastructure.database import SessionLocal
from neosys_pharma.infrastructure.securite_repository import SqlAlchemySecuriteRepository
from neosys_pharma.infrastructure.provisionnement import provisionner
from neosys_pharma.domain.organisation.securite import Role,RolePermission,TypeRole,Utilisateur
from neosys_pharma.domain.organisation.permissions_systeme import CAISSE_PERMISSIONS,P4_PERMISSIONS,permission_id
from neosys_pharma.application.stock_service import StockService
from neosys_pharma.application.vente_service import VenteService
from neosys_pharma.application.caisse_service import CaisseService
from neosys_pharma.application.stock_service import serial as stock_serial
from neosys_pharma.infrastructure.catalogue_models import ProduitModel,NatureMedicamentModel
from sqlalchemy import select
from neosys_pharma.infrastructure.caisse_models import CompteFideliteModel
from neosys_pharma.infrastructure.client_models import ClientModel
f=json.loads(Path('/tmp/p1-browser-fixture.json').read_text());org,site,loc=[UUID(f[k]) for k in ('organisation_id','site_id','location_id')]
with SessionLocal() as s:
    # Produit synthétique admissible à la fidélité : aucune règle métier modifiée.
    nature=s.scalar(select(NatureMedicamentModel).where(
        NatureMedicamentModel.organisation_id==org,NatureMedicamentModel.code=='COSMETIQUE'))
    if nature is None:
        nature=NatureMedicamentModel(id_nature=uuid4(),organisation_id=org,code='COSMETIQUE',nom='Cosmétique QA',actif=True)
        s.add(nature);s.flush()
    product=s.get(ProduitModel,UUID(f['p4_product']))
    assert product.organisation_id==org
    product.nature_id=nature.id_nature;s.commit()
    assert product.nature_id==nature.id_nature and nature.code=='COSMETIQUE'
    repo=SqlAlchemySecuriteRepository(s);users={}
    for name,permissions in [('caisse.qa',tuple(p for p,n in CAISSE_PERMISSIONS)+('organisation.consulter','vente.consulter')),('caisse.lecture.qa',('organisation.consulter','caisse.consulter','fidelite.consulter'))]:
        r=Role(organisation_id=org,code=name,nom=name,type_role=TypeRole.PERSONNALISE);repo.ajouter(r)
        for code in permissions:repo.ajouter(RolePermission(role_id=r.id_role,permission_id=permission_id(code)))
        s.commit();u=Utilisateur(organisation_id=org,identifiant=name,nom=name);provisionner(s,u,[site],[loc],[r.id_role],f['password']);users[name]=u.id_utilisateur
    stock=StockService(s,org,users['caisse.qa'],lambda *a:None);vente=VenteService(stock,site);cash=CaisseService(vente)
    client_a=stock.operation(uuid4(),'QA:CLIENT',{},lambda:stock_serial(stock.ajouter(ClientModel,nom='Cliente fidélité A',telephone='070111111')))
    client_b=stock.operation(uuid4(),'QA:CLIENT',{},lambda:stock_serial(stock.ajouter(ClientModel,nom='Client fidélité B',telephone='070222222')))
    account_a=stock.operation(uuid4(),'QA:FIDELITE',{},lambda:cash.creer_compte_pour_client(UUID(client_a['id'])))
    account_b=stock.operation(uuid4(),'QA:FIDELITE',{},lambda:cash.creer_compte_pour_client(UUID(client_b['id'])))
    # Le modèle n'a pas d'état actif sur le compte; une dette constitue le cas
    # d'inadmissibilité métier testé par le moteur P4.5/P4-C.3.
    blocked=s.get(CompteFideliteModel,UUID(account_b['id']));blocked.dette=1;blocked.revision+=1;s.commit()
    f.update(p44_client_a=client_a['id'],p44_client_b=client_b['id'],p44_account_a=account_a['id'],p44_account_b=account_b['id'],p44_account_a_revision=account_a['revision'])
    for i in range(5):
        client_id=client_a['id'] if i in (1,3) else client_b['id'] if i==2 else None
        v=stock.operation(uuid4(),'QA:CREER',{},lambda:vente.creer({'emplacement_id':loc,'poste_id':UUID(f['p4_poste']),'mode':'SANS_TIERS','client_id':UUID(client_id) if client_id else None}))
        v=stock.operation(uuid4(),'QA:LIGNE',{},lambda:vente.ajouter_ligne(vente.obtenir(v['id'],'vente.preparer'),{'revision':v['revision'],'produit_id':UUID(f['p4_product']),'conditionnement_id':UUID(f['p4_pack']),'quantite':1}))
        v=stock.operation(uuid4(),'QA:VALIDER',{},lambda:vente.changer_etat(vente.obtenir(v['id'],'vente.valider'),'VALIDEE_PREPARATION',{'revision':v['revision']}))
        v=stock.operation(uuid4(),'QA:TRANSMETTRE',{},lambda:vente.changer_etat(vente.obtenir(v['id'],'vente.transmettre'),'TRANSMISE',{'revision':v['revision'],'caisse_id':UUID(f['p4_caisse'])}))
        f['p44_vente_'+str(i)]=v['id'];f['p44_total']=v['totaux']['ttc']
    cat=s.get(ProduitModel,UUID(f['p4_product'])).categorie_id
    stock.operation(uuid4(),'QA:BAREME',{},lambda:cash.ajouter_bareme({'type':'ACQUISITION','debut':date.today(),'fin':None,'points':1,'montant_xaf':100,'categories':[cat],'sous_categories':True,'plafond_xaf':None,'plafond_pourcentage':None,'paiement_integral':False}))
Path('/tmp/p1-browser-fixture.json').write_text(json.dumps(f))
