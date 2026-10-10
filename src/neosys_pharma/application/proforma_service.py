"""Offres sans stock, versions immuables et reprise Vente/P3 dans une seule transaction."""
import hashlib
from datetime import datetime,timezone
from decimal import Decimal
from uuid import UUID
from sqlalchemy import select,func
from fastapi.encoders import jsonable_encoder
from neosys_pharma.application.vente_service import VenteService
from neosys_pharma.application.stock_service import serial
from neosys_pharma.domain.vente import LigneVente
from neosys_pharma.domain.proforma import validite
from neosys_pharma.domain.stock import ConflitStock
from neosys_pharma.infrastructure.proforma_models import ProformaModel,VersionProformaModel,LigneProformaModel,DemandeRemiseProformaModel,EvenementProformaModel,ParametrageProformaModel
from neosys_pharma.infrastructure.organisation_models import SiteModel,OrganisationModel
from neosys_pharma.infrastructure.catalogue_models import ProduitModel,ReferenceProduitModel


def version_serial(v):
    return jsonable_encoder({c.name:getattr(v,c.name) for c in v.__table__.columns if c.name!='pdf'})

class ProformaService(VenteService):
    remise_model=DemandeRemiseProformaModel

    def obtenir(self,key,permission):
        v=self.stock.obtenir(VersionProformaModel,key)
        if v.site_id!=self.site:raise PermissionError('Proforma hors du site courant.')
        self.stock.emplacement(v.emplacement_id,permission)
        return v

    def proforma(self,key,permission):
        p=self.stock.obtenir(ProformaModel,key)
        if p.site_id!=self.site:raise PermissionError('Proforma hors du site courant.')
        self.stock.emplacement(p.emplacement_id,permission)
        return p

    def lignes(self,v):return self.stock.lignes(LigneProformaModel,version_id=v.id)

    def editable(self,v):
        if v.etat!='BROUILLON':raise ConflitStock('Version émise immuable : créer une nouvelle version.')

    def evenement(self,v,type,**data):
        self.stock.ajouter(EvenementProformaModel,proforma_id=v.proforma_id,version_id=v.id,auteur_id=self.stock.user,type=type,donnees=jsonable_encoder({**data,'operation_id':str(self.stock.op)}))

    def detail(self,v):
        p=self.stock.obtenir(ProformaModel,v.proforma_id)
        if v.etat=='EMISE':return {**version_serial(v),'reference':p.reference,'lignes':v.instantane['lignes'],'remises':v.instantane['remises'],'totaux':v.instantane['totaux'],'expiree':self.stock.jour>v.valide_jusqu_au}
        finance=self.finance(v)
        return {**version_serial(v),'reference':p.reference,'lignes':[{**serial(l),'montants_appliques':finance['lignes'][str(l.id)]} for l in self.lignes(v) if l.actif],'remises':[serial(r) for r in self.stock.lignes(self.remise_model,vente_id=v.id)],'totaux':finance['totaux'],'expiree':False}

    def creer(self,data):
        loc=self.stock.emplacement(data['emplacement_id'],'proforma.gerer')
        if loc.site_id!=self.site:raise PermissionError('Emplacement hors site.')
        if data.get('mode')=='CREDIT':self.stock.access('vente.credit',self.site,loc.id_emplacement)
        site=self.s.get(SiteModel,self.site)
        sequence=self.s.scalar(select(func.coalesce(func.max(ProformaModel.sequence),0)).where(ProformaModel.site_id==self.site))+1
        # UUID site suffix prevents ambiguity across pharmacies having the same site code.
        reference=f'PF-{site.code}-{str(site.id_site).replace("-","")[:8].upper()}-{sequence:06d}'
        p=self.stock.ajouter(ProformaModel,site_id=self.site,emplacement_id=loc.id_emplacement,reference=reference,sequence=sequence,auteur_id=self.stock.user)
        v=self.stock.ajouter(VersionProformaModel,proforma_id=p.id,site_id=self.site,emplacement_id=loc.id_emplacement,numero=1,auteur_id=self.stock.user,destinataire=data['destinataire'],mode=data.get('mode','SANS_TIERS'))
        self.evenement(v,'CREATION',reference=reference)
        if data.get('vente_id'):
            sale=VenteService(self.stock,self.site);source=sale.obtenir(data['vente_id'],'vente.consulter')
            sale.revision(source,data['revision_vente'])
            if source.emplacement_id!=v.emplacement_id:raise PermissionError('Préparation d’un autre emplacement.')
            v.mode=source.mode
            mapping={}
            for line in sale.lignes(source):
                if line.actif:
                    result=self.ajouter_ligne(v,{'revision':v.revision,'produit_id':line.produit_id,'conditionnement_id':line.conditionnement_id,'quantite':line.quantite})
                    mapping[str(line.id)]=next(x.id for x in self.lignes(v) if x.id not in mapping.values())
            # Discounts become requests, never an implicit reuse of authorization.
            self.copier_demandes(v,source,sale,mapping)
            self.evenement(v,'DEPUIS_PREPARATION',vente_id=source.id,revision=source.revision,reservations_inchangees=True)
        return self.detail(v)

    def copier_demandes(self,target,source,service,mapping):
        for r in service.stock.lignes(service.remise_model,vente_id=source.id):
            if r.statut not in ('AUTORISEE','DEMANDEE'):continue
            self.stock.access('vente.remise.demander',target.site_id,target.emplacement_id)
            self.stock.ajouter(self.remise_model,vente_id=target.id,ligne_id=mapping.get(str(r.ligne_id)),type=r.type,valeur=r.valeur,revision_vente=target.revision,auteur_id=self.stock.user,justification='À revalider : '+r.justification)

    def ajouter_ligne(self,v,data):
        self.editable(v);self.revision(v,data['revision'])
        pack,_=self.stock.conditionnement(data['conditionnement_id'])
        if pack.produit_id!=data['produit_id']:raise PermissionError('Produit/conditionnement incompatibles.')
        tarif=self.tarifs.resoudre(self.org,self.site,pack.id_conditionnement,self.stock.jour)
        commercial=LigneVente(pack.produit_id,pack.id_conditionnement,data['quantite'],tarif)
        if data.get('ligne_id'):
            row=self.stock.obtenir(LigneProformaModel,data['ligne_id'])
            if row.version_id!=v.id:raise PermissionError('Ligne d’une autre version.')
        else:row=self.stock.ajouter(LigneProformaModel,version_id=v.id,produit_id=pack.produit_id,conditionnement_id=pack.id_conditionnement,quantite=data['quantite'],designation='',conditionnement='',instantane_tarif={},montants={})
        row.actif=True;row.quantite=data['quantite'];row.produit_id=pack.produit_id;row.conditionnement_id=pack.id_conditionnement
        row.designation=self.s.get(ProduitModel,pack.produit_id).nom;row.conditionnement=pack.libelle
        row.reference=self.s.scalar(select(ReferenceProduitModel.valeur).where(ReferenceProduitModel.organisation_id==self.org,ReferenceProduitModel.conditionnement_id==pack.id_conditionnement,ReferenceProduitModel.actif.is_(True)).order_by(ReferenceProduitModel.id_reference))
        row.instantane_tarif=jsonable_encoder(tarif,custom_encoder={Decimal:str});row.montants=commercial.montants();self.invalider_remises(v);v.revision+=1
        self.evenement(v,'LIGNE_ENREGISTREE',ligne=serial(row));return self.detail(v)

    def supprimer_ligne(self,v,line_id,expected):
        self.editable(v);self.revision(v,expected);row=self.stock.obtenir(LigneProformaModel,line_id)
        if row.version_id!=v.id:raise PermissionError('Ligne d’une autre version.')
        row.actif=False;self.invalider_remises(v);v.revision+=1;self.evenement(v,'LIGNE_RETIRÉE',ligne_id=row.id);return self.detail(v)

    def destinataire(self,v,data):
        self.editable(v);self.revision(v,data['revision']);v.destinataire=data['destinataire'];v.revision+=1
        for pending in self.stock.lignes(self.remise_model,vente_id=v.id):
            if pending.statut=='DEMANDEE':pending.revision_vente=v.revision
        self.evenement(v,'DESTINATAIRE_MODIFIE',destinataire=v.destinataire);return self.detail(v)

    def parametrage(self):
        row=self.s.scalar(select(ParametrageProformaModel).where(ParametrageProformaModel.site_id==self.site,ParametrageProformaModel.organisation_id==self.org))
        return serial(row) if row else {'duree_jours':30,'revision':0}

    def configurer(self,data):
        row=self.s.scalar(select(ParametrageProformaModel).where(ParametrageProformaModel.site_id==self.site,ParametrageProformaModel.organisation_id==self.org))
        if data['revision']!=(row.revision if row else 0):raise ConflitStock('Paramétrage modifié : actualiser.')
        validite(self.stock.jour,data['duree_jours'])
        if not row:row=self.stock.ajouter(ParametrageProformaModel,site_id=self.site,duree_jours=data['duree_jours'])
        else:row.duree_jours=data['duree_jours'];row.revision+=1
        return serial(row)

    def emettre(self,v,data):
        self.editable(v);self.revision(v,data['revision'])
        if v.mode!='SANS_TIERS':raise ValueError('Répartition tiers payant/crédit indisponible : émission financière interdite.')
        rows=[x for x in self.lignes(v) if x.actif]
        if not rows:raise ValueError('Au moins une ligne obligatoire.')
        if not v.destinataire.get('nom'):raise ValueError('Destinataire obligatoire.')
        requests=self.stock.lignes(self.remise_model,vente_id=v.id)
        if any(r.statut=='DEMANDEE' for r in requests):raise ValueError('Remise en attente : émission interdite.')
        for row in rows:
            self.stock.conditionnement(row.conditionnement_id)
            if jsonable_encoder(self.tarifs.resoudre(self.org,self.site,row.conditionnement_id,self.stock.jour),custom_encoder={Decimal:str})!=row.instantane_tarif:raise ConflitStock('Tarif modifié : actualiser les lignes avant émission.')
        for r in requests:
            if r.statut!='AUTORISEE':continue
            eligible=self.eligible(v,r)
            from neosys_pharma.domain.remises import montant_remise
            cap=self.plafond_applicable(v,UUID(r.autorisation['auteur_id']),r,montant_remise(r.type,r.valeur,eligible),eligible)
            if str(cap.id)!=r.autorisation['plafond']['id'] or cap.revision!=r.autorisation['plafond']['revision']:raise ConflitStock('Autorisation de remise à revalider.')
        p=self.stock.obtenir(ProformaModel,v.proforma_id);org=self.s.get(OrganisationModel,self.org);site=self.s.get(SiteModel,self.site)
        v.emis_le=datetime.now(timezone.utc);v.valide_jusqu_au=validite(self.stock.jour,self.parametrage()['duree_jours'])
        snapshot=self.detail(v)
        snapshot.update({'organisation':{'nom':org.nom_commercial,'raison_sociale':org.raison_sociale,'coordonnees':org.coordonnees,'informations_legales':org.informations_legales},'site':{'nom':site.nom,'code':site.code,'adresse':site.adresse,'telephone':site.telephone,'email':site.email},'emis_le':v.emis_le.isoformat(),'valide_jusqu_au':v.valide_jusqu_au.isoformat(),'etat':'EMISE','devise':'XAF','reference':p.reference})
        from neosys_pharma.infrastructure.proforma_pdf import proforma_pdf
        v.instantane=snapshot;v.pdf=proforma_pdf(snapshot);v.pdf_sha256=hashlib.sha256(v.pdf).hexdigest();v.revision+=1
        self.evenement(v,'EMISSION',reference=p.reference,numero=v.numero,pdf_sha256=v.pdf_sha256,totaux=snapshot['totaux'])
        self.s.flush();v.etat='EMISE';self.s.flush();return self.detail(v)

    def nouvelle_version(self,source,data):
        self.revision(source,data['revision'])
        if source.etat!='EMISE':raise ValueError('Émettre la version courante avant de créer une nouvelle version.')
        if self.s.scalar(select(VersionProformaModel.id).where(VersionProformaModel.proforma_id==source.proforma_id,VersionProformaModel.etat=='BROUILLON')):raise ConflitStock('Un brouillon existe déjà pour cette proforma.')
        number=self.s.scalar(select(func.max(VersionProformaModel.numero)).where(VersionProformaModel.proforma_id==source.proforma_id))+1
        target=self.stock.ajouter(VersionProformaModel,proforma_id=source.proforma_id,site_id=source.site_id,emplacement_id=source.emplacement_id,numero=number,auteur_id=self.stock.user,destinataire=source.destinataire,mode=source.mode)
        mapping={}
        for row in self.lignes(source):
            if row.actif:
                result=self.ajouter_ligne(target,{'revision':target.revision,'produit_id':row.produit_id,'conditionnement_id':row.conditionnement_id,'quantite':row.quantite})
                mapping[str(row.id)]=next(x.id for x in self.lignes(target) if x.id not in mapping.values())
        self.copier_demandes(target,source,self,mapping);self.evenement(target,'NOUVELLE_VERSION',source_version_id=source.id);return self.detail(target)

    def reprendre(self,source,data):
        self.revision(source,data['revision'])
        if source.etat!='EMISE':raise ValueError('Seule une version émise peut être reprise.')
        # Expiration concerns the offer, not its use as a template with all current prices.
        sale=VenteService(self.stock,self.site)
        result=sale.creer({'emplacement_id':source.emplacement_id,'poste_id':data['poste_id'],'mode':source.mode,'destinataire':source.destinataire})
        v=sale.obtenir(UUID(result['id']),'vente.preparer');mapping={}
        for row in self.lignes(source):
            if not row.actif:continue
            result=sale.ajouter_ligne(v,{'revision':v.revision,'produit_id':row.produit_id,'conditionnement_id':row.conditionnement_id,'quantite':row.quantite})
            mapping[row.id]=str(next(x.id for x in sale.lignes(v) if str(x.id) not in mapping.values()))
        # Requests must be approved again against current quantities, prices and caps.
        for r in self.stock.lignes(self.remise_model,vente_id=source.id):
            if r.statut=='AUTORISEE':
                self.stock.access('vente.remise.demander',source.site_id,source.emplacement_id)
                sale.demander_remise(v,{'revision':v.revision,'ligne_id':UUID(mapping[r.ligne_id]) if r.ligne_id else None,'type':r.type,'valeur':r.valeur,'justification':'Proforma '+self.stock.obtenir(ProformaModel,source.proforma_id).reference+' : '+r.justification})
        sale.evenement(v,'REPRISE_PROFORMA',proforma_id=source.proforma_id,version_id=source.id,reference=self.stock.obtenir(ProformaModel,source.proforma_id).reference,prix_recalcules=True,remises_a_reautoriser=True)
        self.evenement(source,'REPRISE_PREPARATION',vente_id=v.id,version_id=source.id)
        return sale.detail(v)
