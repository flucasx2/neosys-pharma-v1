"""Une transaction unique P4/P3, sans appels HTTP ni commit intermédiaire."""
from decimal import Decimal
from uuid import UUID
from fastapi.encoders import jsonable_encoder
from sqlalchemy import select
from neosys_pharma.domain.vente import EtatVente,ModeVente,LigneVente,transition,remise_valide
from neosys_pharma.domain.stock import ConflitStock
from neosys_pharma.infrastructure.vente_models import VenteModel,LigneVenteModel,ReservationVenteModel,DemandeRemiseModel,EvenementVenteModel
from neosys_pharma.infrastructure.organisation_models import PosteVenteModel,CaisseModel
from neosys_pharma.infrastructure.catalogue_models import ProduitModel,ReferenceProduitModel
from neosys_pharma.infrastructure.stock_models import ReservationStockModel
from neosys_pharma.application.stock_service import serial
from neosys_pharma.application.catalogue_service import CatalogueService
from neosys_pharma.application.tarification_service import TarificationService
from neosys_pharma.infrastructure.catalogue_repository import SqlAlchemyCatalogueRepository

from neosys_pharma.application.remises_service import RemisesService

class VenteService(RemisesService):
    def __init__(self,stock,site):
        self.stock=stock;self.s=stock.s;self.org=stock.org;self.site=site
        self.tarifs=TarificationService(CatalogueService(SqlAlchemyCatalogueRepository(self.s)))

    def obtenir(self,key,permission):
        v=self.stock.obtenir(VenteModel,key)
        if v.site_id!=self.site:raise PermissionError('Vente hors du site courant.')
        self.stock.emplacement(v.emplacement_id,permission)
        return v

    def lignes(self,v):return self.stock.lignes(LigneVenteModel,vente_id=v.id)

    def evenement(self,v,type,**data):
        self.stock.ajouter(EvenementVenteModel,vente_id=v.id,auteur_id=self.stock.user,type=type,donnees=jsonable_encoder({**data, "operation_id":str(self.stock.op)}))

    def editable(self,v):
        if v.etat!='PREPARATION':raise ConflitStock('Reprendre la préparation avant modification ; vente terminale non modifiable.')

    def revision(self,v,expected):
        if v.revision!=expected:raise ConflitStock('Préparation modifiée : actualiser avant de poursuivre.')

    def creer(self,data):
        loc=self.stock.emplacement(data['emplacement_id'],'vente.preparer')
        if loc.site_id!=self.site:raise PermissionError('Emplacement hors du site courant.')
        poste=self.s.get(PosteVenteModel,data['poste_id'])
        if not poste or not poste.actif or poste.emplacement_id!=loc.id_emplacement:raise PermissionError('Poste de vente incompatible ou inactif.')
        if data['mode']=='CREDIT':self.stock.access('vente.credit',self.site,loc.id_emplacement)
        v=self.stock.ajouter(VenteModel,site_id=self.site,emplacement_id=loc.id_emplacement,poste_id=poste.id_poste_vente,vendeur_id=self.stock.user,mode=data['mode'],destinataire=data.get('destinataire',{}))
        self.evenement(v,'CREATION',mode=v.mode,poste_id=v.poste_id)
        return self.detail(v)

    def liberer_ligne(self,line):
        for link in self.stock.lignes(ReservationVenteModel,ligne_id=line.id):
            r=self.stock.obtenir(ReservationStockModel,link.reservation_id)
            if r.statut=='ACTIVE':self.stock.terminer_reservation(r.id,permission='stock.reserver',interne=True)

    def invalider_remises(self,v):
        for line in self.lignes(v):line.remise_appliquee=None
        for r in self.stock.lignes(self.remise_model,vente_id=v.id):
            if r.statut in ('DEMANDEE','AUTORISEE'):
                r.statut='INVALIDEE';self.evenement(v,'REMISE_INVALIDEE',demande_id=r.id,revision=v.revision)

    def ajouter_ligne(self,v,data):
        self.editable(v);self.revision(v,data['revision'])
        pack,_=self.stock.conditionnement(data['conditionnement_id'])
        if pack.produit_id!=data['produit_id']:raise PermissionError('Produit et conditionnement incompatibles.')
        tarif=self.tarifs.resoudre(self.org,self.site,pack.id_conditionnement,self.stock.jour)
        line=LigneVente(pack.produit_id,pack.id_conditionnement,data['quantite'],tarif)
        if data.get('ligne_id'):
            row=self.stock.obtenir(LigneVenteModel,data['ligne_id'])
            if row.vente_id!=v.id:raise PermissionError('Ligne d’une autre préparation.')
            self.liberer_ligne(row)
        else:row=self.stock.ajouter(LigneVenteModel,vente_id=v.id,produit_id=pack.produit_id,conditionnement_id=pack.id_conditionnement,quantite=data['quantite'],designation='',conditionnement='',instantane_tarif={},montants={})
        ref=self.s.scalar(select(ReferenceProduitModel.valeur).where(ReferenceProduitModel.organisation_id==self.org,ReferenceProduitModel.conditionnement_id==pack.id_conditionnement,ReferenceProduitModel.actif.is_(True)).order_by(ReferenceProduitModel.id_reference))
        row.actif=True;row.produit_id=pack.produit_id;row.conditionnement_id=pack.id_conditionnement;row.quantite=data['quantite']
        row.designation=self.s.get(ProduitModel,pack.produit_id).nom;row.conditionnement=pack.libelle;row.reference=ref
        row.instantane_tarif=jsonable_encoder(tarif,custom_encoder={Decimal:str});row.montants=line.montants();row.remise_appliquee=None
        result=self.stock.reserver(dict(conditionnement_id=pack.id_conditionnement,emplacement_id=v.emplacement_id,quantite=row.quantite,origine='VENTE:'+str(v.id)+':'+str(row.id),lot_id=data.get('lot_id'),justification=data.get('justification')))
        self.stock.ajouter(ReservationVenteModel,ligne_id=row.id,reservation_id=UUID(result['id']))
        self.invalider_remises(v);v.revision+=1
        self.evenement(v,'LIGNE_ENREGISTREE',ligne_id=row.id,quantite=row.quantite,instantane=row.instantane_tarif,montants=row.montants)
        self.s.flush();return self.detail(v)

    def supprimer_ligne(self,v,line_id,expected):
        self.editable(v);self.revision(v,expected)
        row=self.stock.obtenir(LigneVenteModel,line_id)
        if row.vente_id!=v.id:raise PermissionError('Ligne d’une autre préparation.')
        self.liberer_ligne(row)
        # Conserver la ligne et ses liens comme historique ; zéro n'est jamais une ligne commerciale.
        row.actif=False
        self.invalider_remises(v);v.revision+=1
        self.evenement(v,'LIGNE_RETIRÉE',ligne_id=row.id)
        return self.detail(v)

    def changer_etat(self,v,target,data):
        self.revision(v,data['revision']);transition(v.etat,target)
        if target=='VALIDEE_PREPARATION':
            if v.mode!='SANS_TIERS':raise ValueError('Règles de tiers payant ou crédit indisponibles : préparation non validable.')
            rows=[r for r in self.lignes(v) if r.actif]
            if not rows:raise ValueError('Au moins une ligne commerciale est obligatoire.')
            if any(r.statut in ('DEMANDEE',) for r in self.stock.lignes(self.remise_model,vente_id=v.id)):raise ValueError('Demande de remise en attente : validation interdite.')
            for row in rows:
                links=self.stock.lignes(ReservationVenteModel,ligne_id=row.id)
                active=[self.stock.obtenir(ReservationStockModel,x.reservation_id) for x in links if self.stock.obtenir(ReservationStockModel,x.reservation_id).statut=='ACTIVE']
                if sum(sum(a['quantite'] for a in self.stock.reservation_detail(r)['allocations']) for r in active)!=row.quantite:raise ConflitStock('Réservation absente ou incomplète : reprendre la ligne.')
                # Les tarifs figés doivent encore correspondre à ceux en vigueur à validation.
                if jsonable_encoder(self.tarifs.resoudre(self.org,self.site,row.conditionnement_id,self.stock.jour),custom_encoder={Decimal:str})!=row.instantane_tarif:raise ConflitStock('Tarif modifié : actualiser explicitement la ligne avant validation.')
                for r in active:
                    for a in self.stock.reservation_detail(r)['allocations']:
                        from neosys_pharma.infrastructure.stock_models import StockEmplacementModel,LotModel
                        from neosys_pharma.domain.stock import perime
                        b=self.stock.obtenir(StockEmplacementModel,a['stock_id']);lot=self.stock.obtenir(LotModel,b.lot_id);_,rules=self.stock.conditionnement(lot.conditionnement_id)
                        if rules['gestion_peremption'] and (lot.peremption is None or perime(lot.peremption,self.stock.jour)):raise ConflitStock('Lot réservé périmé : réallouer avant validation.')
        if target=='TRANSMISE':
            caisse=self.s.get(CaisseModel,data.get('caisse_id'))
            if not caisse or not caisse.actif or caisse.emplacement_id!=v.emplacement_id:raise PermissionError('Caisse autorisée du même emplacement requise.')
            v.caisse_id=caisse.id_caisse
            from neosys_pharma.application.caisse_service import CaisseService
            CaisseService(self).appel(v)
        if target=='ANNULEE':
            if not data.get('justification'):raise ValueError('Motif d’annulation obligatoire.')
            for r in self.lignes(v):self.liberer_ligne(r)
            self.invalider_remises(v)
        previous=v.etat;v.etat=target;v.revision+=1
        if target in ('EN_ATTENTE','PREPARATION'):
            # Workflow-only transitions preserve the unchanged financial base.
            for pending in self.stock.lignes(self.remise_model,vente_id=v.id):
                if pending.statut=='DEMANDEE':pending.revision_vente=v.revision
        self.evenement(v,'TRANSITION',avant=previous,apres=target,justification=data.get('justification'),caisse_id=v.caisse_id,instantane_financier=self.finance(v))
        return self.detail(v)

    def verifier_ligne_remise(self,v,line_id):
        line=self.stock.obtenir(LigneVenteModel,line_id)
        if line.vente_id!=v.id or not line.actif:raise PermissionError('Ligne de remise incompatible.')

    def demander_remise(self,v,data):
        self.editable(v);self.revision(v,data['revision']);value=remise_valide(data['type'],data['valeur'])
        line_id=data.get('ligne_id')
        if line_id:self.verifier_ligne_remise(v,line_id)
        r=self.stock.ajouter(self.remise_model,vente_id=v.id,ligne_id=line_id,type=data['type'],valeur=value,revision_vente=v.revision,auteur_id=self.stock.user,justification=data['justification'])
        from neosys_pharma.domain.remises import montant_remise
        if any(x.id!=r.id and x.ligne_id==line_id and x.statut=='DEMANDEE' for x in self.stock.lignes(self.remise_model,vente_id=v.id)):raise ConflitStock('Une demande est déjà en attente pour cette portée.')
        montant_remise(r.type,r.valeur,self.eligible(v,r))
        self.evenement(v,'REMISE_DEMANDEE',demande=serial(r));return serial(r)

    def detail(self,v):
        from neosys_pharma.infrastructure.caisse_models import AppelVenteModel,ParametrageCaisseModel
        call=self.s.scalar(select(AppelVenteModel).filter_by(organisation_id=self.org,vente_id=v.id))
        config=self.s.scalar(select(ParametrageCaisseModel).filter_by(organisation_id=self.org))
        rows=[r for r in self.lignes(v) if r.actif]
        finance=self.finance(v);totals=finance['totaux']
        return {**serial(v),'numero_appel':str(call.numero).zfill(4) if call else None,'periode_appel_id':str(call.periode_id) if call else None,'ticket_appel_active':config.ticket_appel if config else False,'lignes':[{**serial(r),'montants_appliques':finance['lignes'][str(r.id)],'reservations':[self.stock.reservation_detail(self.stock.obtenir(ReservationStockModel,x.reservation_id)) for x in self.stock.lignes(ReservationVenteModel,ligne_id=r.id)]} for r in rows],'totaux':totals,'part_client':totals['ttc'] if v.mode=='SANS_TIERS' else None,'prise_en_charge_disponible':v.mode=='SANS_TIERS','remises':[serial(r) for r in self.stock.lignes(self.remise_model,vente_id=v.id)]}
