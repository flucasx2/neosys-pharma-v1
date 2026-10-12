"""Edition documentaire atomique ; aucune mutation des quantités ou des finances."""
from datetime import datetime, timezone
from uuid import uuid4
import hashlib
from sqlalchemy import select
from neosys_pharma.infrastructure.vente_models import DocumentPreparationModel
from neosys_pharma.infrastructure.organisation_models import OrganisationModel,SiteModel,EmplacementModel
from neosys_pharma.infrastructure.securite_models import UtilisateurModel
from neosys_pharma.infrastructure.stock_models import StockEmplacementModel,LotModel
from neosys_pharma.infrastructure.regularisation_pdf import document_pdf
from neosys_pharma.application.caisse_service import serial

class DocumentPreparationService:
    def __init__(self,vente):self.vente=vente;self.s=vente.s;self.stock=vente.stock;self.org=vente.org
    def liste(self,v,page,size):
        q=select(DocumentPreparationModel).where(DocumentPreparationModel.organisation_id==self.org,DocumentPreparationModel.vente_id==v.id).order_by(DocumentPreparationModel.revision_vente.desc())
        total,rows=self.stock.repo.paginer(q,page,size)
        return {'items':[{k:v for k,v in serial(x).items() if k!='instantane'} for x in rows],'total':total,'page':page,'page_size':size}
    def editer(self,key,revision):
        v=self.vente.obtenir(key,'vente.consulter');self.vente.revision(v,revision)
        existing=self.s.scalar(select(DocumentPreparationModel).filter_by(organisation_id=self.org,vente_id=v.id,revision_vente=v.revision))
        if existing:return serial(existing)
        data=self.vente.detail(v);doc_id=uuid4();now=datetime.now(timezone.utc)
        org=self.s.get(OrganisationModel,self.org);site=self.s.get(SiteModel,v.site_id);user=self.s.get(UtilisateurModel,self.stock.user)
        location=self.s.get(EmplacementModel,v.emplacement_id)
        lines=[];allocations=[]
        for l in data['lignes']:
            lines.append([l['designation'],l['conditionnement'],l['reference'] or '—',l['quantite']])
            for r in l['reservations']:
                for a in r['allocations']:
                    b=self.stock.obtenir(StockEmplacementModel,a['stock_id']);lot=self.stock.obtenir(LotModel,b.lot_id)
                    allocations.append([l['designation']+' / '+l['conditionnement'],lot.numero or 'SANS LOT',lot.peremption.strftime('%d/%m/%Y') if lot.peremption else 'NON APPLICABLE',a['quantite'],r['statut']])
        snapshot={'titre':'PRÉPARATION — NON ACQUITTÉE','organisation':org.nom_commercial,'site':site.nom,'reference':str(doc_id),'date':now.isoformat(),'responsable':user.nom if user else None,'vente':data,'sections':[
            {'titre':'Identification','colonnes':['Vente / révision','Emplacement / état','Auteur / appel'],'lignes':[[str(v.id)+' / '+str(v.revision),location.nom+' / '+v.etat,(user.nom if user else 'IDENTITÉ NON DISPONIBLE')+' / '+(data['numero_appel'] or 'NON ATTRIBUÉ')]]},
            {'titre':'Produits à préparer — ne vaut pas reçu de paiement','colonnes':['Désignation','Conditionnement','Référence','Quantité'],'lignes':lines},
            {'titre':'Allocations enregistrées à cette révision — disponibilité non garantie ultérieurement','colonnes':['Produit / conditionnement','Lot','Péremption','Quantité','Réservation'],'lignes':allocations}]}
        pdf=document_pdf(snapshot)
        row=self.stock.ajouter(DocumentPreparationModel,id=doc_id,vente_id=v.id,revision_vente=v.revision,auteur_id=self.stock.user,date=now,instantane=snapshot,pdf=pdf,pdf_sha256=hashlib.sha256(pdf).hexdigest())
        self.vente.evenement(v,'DOCUMENT_PREPARATION',document_id=doc_id,revision=v.revision,pdf_sha256=row.pdf_sha256)
        return serial(row)
    def obtenir(self,key):
        d=self.stock.obtenir(DocumentPreparationModel,key)
        self.vente.obtenir(d.vente_id,'vente.consulter')
        return d
