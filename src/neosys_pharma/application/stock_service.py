"""Services réutilisables par P4 ; aucune vente, commande ou réception fournisseur ici."""
import hashlib,json
from datetime import date
from uuid import UUID,uuid4
from sqlalchemy import select,func
from fastapi.encoders import jsonable_encoder
from neosys_pharma.domain.stock import quantite, verifier_stock, perime, ordre_fefo, ecart_inventaire, ConflitStock
from neosys_pharma.domain.catalogue import texte
from neosys_pharma.infrastructure.stock_models import *
from neosys_pharma.infrastructure.catalogue_models import ConditionnementModel,ProduitModel,CategorieProduitModel,ReferenceProduitModel
from neosys_pharma.infrastructure.organisation_models import EmplacementModel,SiteModel
from neosys_pharma.infrastructure.securite_models import UtilisateurModel
from neosys_pharma.infrastructure.stock_repository import StockRepository


def ident(value): return UUID(str(value))

def serial(row):
    return jsonable_encoder({c.name:getattr(row,c.name) for c in row.__table__.columns if c.name!='cle'})

class StockService:
    def __init__(self,session,org,user,access,jour=None):
        self.s=session;self.repo=StockRepository(session);self.org=org;self.user=user;self.access=access;self.jour=jour or date.today()

    def obtenir(self,cls,key): return self.repo.obtenir(cls,ident(key),self.org)
    def ajouter(self,cls,**values): return self.repo.ajouter(cls(organisation_id=self.org,**values))
    def lignes(self,cls,**filters): return self.repo.lignes(cls,self.org,**filters)

    def operation(self,key,kind,body,action):
        fingerprint=hashlib.sha256(json.dumps(jsonable_encoder({'action':kind,'body':body}),sort_keys=True,ensure_ascii=False).encode()).hexdigest()
        try:
            self.repo.verrouiller(self.org)
            previous=self.s.scalar(select(OperationStockModel).where(OperationStockModel.organisation_id==self.org,OperationStockModel.cle==key))
            if previous:
                if previous.auteur_id!=self.user or previous.empreinte!=fingerprint: raise ConflitStock('Clé d’idempotence déjà utilisée pour une autre opération.')
                # Action-level scope must also be checked by the API before replay.
                self.s.rollback();return previous.resultat
            self.op=key
            result=jsonable_encoder(action())
            self.ajouter(OperationStockModel,cle=key,empreinte=fingerprint,resultat=result,auteur_id=self.user)
            self.s.commit();return result
        except Exception:
            self.s.rollback();raise

    def emplacement(self,key,permission):
        row=self.s.get(EmplacementModel,ident(key))
        site=self.s.get(SiteModel,row.site_id) if row else None
        if not row or not site or site.organisation_id!=self.org or not row.actif or not site.actif: raise PermissionError('Emplacement non autorisé ou inactif.')
        if permission:self.access(permission,site.id_site,row.id_emplacement)
        return row

    def conditionnement(self,key,operation=True):
        row=self.s.get(ConditionnementModel,ident(key))
        if not row or row.organisation_id!=self.org:raise PermissionError('Conditionnement d’une autre organisation ou absent.')
        product=self.s.get(ProduitModel,row.produit_id);category=self.s.get(CategorieProduitModel,product.categorie_id)
        if operation and (not row.actif or not product.actif):raise ValueError('Produit ou conditionnement inactif.')
        return row,{k:getattr(product,k) if getattr(product,k) is not None else getattr(category,k) for k in ('gestion_lot','gestion_peremption','fefo')}

    def creer_lot(self,data):
        pack,rules=self.conditionnement(data['conditionnement_id']);numero=data.get('numero') or None;expiry=data.get('peremption')
        if rules['gestion_lot'] and not numero:raise ValueError('Numéro de lot obligatoire selon le catalogue.')
        if rules['gestion_peremption'] and not expiry:raise ValueError('Date de péremption obligatoire selon le catalogue.')
        if not numero and expiry:raise ValueError('Un lot daté nécessite un numéro explicite.')
        return serial(self.ajouter(LotModel,conditionnement_id=pack.id_conditionnement,numero=numero,cle='LOT:'+numero if numero else 'SANS_LOT',peremption=expiry,auteur_id=self.user))

    def balance(self,lot,location):
        row=self.s.scalar(select(StockEmplacementModel).filter_by(organisation_id=self.org,lot_id=lot.id,emplacement_id=location.id_emplacement))
        return row or self.ajouter(StockEmplacementModel,lot_id=lot.id,site_id=location.site_id,emplacement_id=location.id_emplacement,physique=0,reserve=0)

    def mouvement(self,balance,physical,reserved,kind,origin,reason=None):
        verifier_stock(balance.physique+physical,balance.reserve+reserved)
        balance.physique+=physical;balance.reserve+=reserved
        move=self.ajouter(MouvementStockModel,stock_id=balance.id,sequence=self.repo.sequence(self.org)+1,type=kind,delta_physique=physical,delta_reserve=reserved,physique_apres=balance.physique,reserve_apres=balance.reserve,origine=origin,operation_id=self.op,auteur_id=self.user,justification=reason)
        return move

    def entree(self,data):
        loc=self.emplacement(data['emplacement_id'],'stock.gerer');lot=self.obtenir(LotModel,data['lot_id']);self.conditionnement(lot.conditionnement_id)
        kind=data.get('type','ENTREE');q=quantite(data['quantite'],signee=kind in ('AJUSTEMENT','CORRECTION'))
        if q<0:
            # Les corrections négatives sont sélectionnées explicitement ; elles ne contournent pas FEFO.
            result=self.sortie({**data,'conditionnement_id':lot.conditionnement_id,'quantite':-q,'lot_id':lot.id},kind)
            return result
        return serial(self.mouvement(self.balance(lot,loc),q,0,kind,data['origine'],data.get('justification')))

    def disponibles(self,pack,loc):
        rows=self.s.execute(select(StockEmplacementModel,LotModel).join(LotModel,StockEmplacementModel.lot_id==LotModel.id).where(StockEmplacementModel.organisation_id==self.org,StockEmplacementModel.emplacement_id==loc.id_emplacement,LotModel.conditionnement_id==pack)).all()
        return sorted(rows,key=lambda x:ordre_fefo(x[1]))

    def reserver(self,data,permission='stock.reserver',reservation=None):
        loc=self.emplacement(data['emplacement_id'],permission);pack,rules=self.conditionnement(data['conditionnement_id']);q=quantite(data['quantite'])
        candidates=[(b,l) for b,l in self.disponibles(pack.id_conditionnement,loc) if b.physique>b.reserve and (not rules['gestion_peremption'] or (l.peremption is not None and not perime(l.peremption,self.jour)))]
        def allocate(rows):
            remaining=q;result=[]
            for b,l in rows:
                take=min(remaining,b.physique-b.reserve)
                if take>0:result.append((b,l,take));remaining-=take
                if not remaining:break
            if remaining:raise ConflitStock(f'Stock vendable insuffisant ou périmé : manque {remaining} unité(s).')
            return result
        proposed=allocate(candidates);chosen=proposed
        if data.get('lot_id'):
            chosen=allocate([(b,l) for b,l in candidates if l.id==ident(data['lot_id'])])
        bypass=rules['fefo'] and [(l.id,n) for b,l,n in chosen]!=[(l.id,n) for b,l,n in proposed]
        if bypass:
            self.access('stock.fefo.deroger',loc.site_id,loc.id_emplacement)
            if not data.get('justification'):raise ValueError('Dérogation FEFO : justification obligatoire.')
        reservation=reservation or self.ajouter(ReservationStockModel,origine=data['origine'],auteur_id=self.user)
        for balance,lot,n in chosen:
            self.ajouter(AllocationReservationModel,reservation_id=reservation.id,stock_id=balance.id,quantite=n)
            self.mouvement(balance,0,n,'RESERVATION',data['origine'],data.get('justification'))
        if bypass:self.ajouter(DerogationFEFOModel,reservation_id=reservation.id,auteur_id=self.user,justification=data['justification'],proposition=[{'lot_id':str(l.id),'quantite':n} for b,l,n in proposed],choix=[{'lot_id':str(l.id),'quantite':n} for b,l,n in chosen])
        return self.reservation_detail(reservation)

    def reservation_detail(self,row):
        allocations=[]
        for x in self.lignes(AllocationReservationModel,reservation_id=row.id):
            b=self.obtenir(StockEmplacementModel,x.stock_id);l=self.obtenir(LotModel,b.lot_id)
            allocations.append({**serial(x),'lot':l.numero,'emplacement_id':str(b.emplacement_id)})
        return {**serial(row),'allocations':allocations}

    def reservation_scope(self,key,permission):
        row=self.obtenir(ReservationStockModel,key)
        for line in self.lignes(AllocationReservationModel,reservation_id=row.id):self.emplacement(self.obtenir(StockEmplacementModel,line.stock_id).emplacement_id,permission)
        return row

    def terminer_reservation(self,key,consume=False,kind='CONSOMMATION',permission='stock.reserver',interne=False):
        row=self.reservation_scope(key,permission)
        if not interne and self.s.scalar(select(TransfertStockModel.id).where(TransfertStockModel.reservation_id==row.id)):raise ConflitStock('Réservation pilotée par un transfert ; utiliser son workflow.')
        if row.statut!='ACTIVE':raise ConflitStock('Réservation déjà terminée.')
        for line in self.lignes(AllocationReservationModel,reservation_id=row.id):
            b=self.obtenir(StockEmplacementModel,line.stock_id);lot=self.obtenir(LotModel,b.lot_id);pack,rules=self.conditionnement(lot.conditionnement_id)
            if consume and rules['gestion_peremption'] and (lot.peremption is None or perime(lot.peremption,self.jour)):raise ConflitStock('Lot réservé devenu périmé : libérer et réallouer.')
            self.mouvement(b,-line.quantite if consume else 0,-line.quantite,kind if consume else 'LIBERATION',row.origine)
        row.statut='CONSOMMEE' if consume else 'LIBEREE';self.s.flush();return self.reservation_detail(row)

    def sortie(self,data,kind='SORTIE'):
        loc=self.emplacement(data['emplacement_id'],'stock.gerer')
        reserved=self.reserver(data,'stock.gerer')
        return self.terminer_reservation(reserved['id'],True,kind,'stock.gerer',True)

    def creer_demande(self,data):
        source=self.emplacement(data['source_id'],'stock.transferer');dest=self.emplacement(data['destination_id'],None)
        if source.id_emplacement==dest.id_emplacement:raise ValueError('Deux emplacements distincts requis.')
        if source.site_id==dest.site_id:self.emplacement(dest.id_emplacement,'stock.transferer')
        for line in data['lignes']:self.conditionnement(line['conditionnement_id']);quantite(line['quantite'])
        return serial(self.ajouter(DemandeTransfertModel,source_id=source.id_emplacement,destination_id=dest.id_emplacement,source_site_id=source.site_id,destination_site_id=dest.site_id,lignes=jsonable_encoder(data['lignes']),justification=data['justification'],auteur_id=self.user))

    def demande_scope(self,key,permission,destination=False):
        d=self.obtenir(DemandeTransfertModel,key);self.emplacement(d.destination_id if destination else d.source_id,permission);return d

    def valider_demande(self,key,permission="stock.transfert.valider"):
        d=self.demande_scope(key,permission)
        if d.statut!='DEMANDEE':raise ConflitStock('Demande déjà traitée.')
        combined=self.ajouter(ReservationStockModel,origine='Transfert '+str(d.id),auteur_id=self.user)
        # Allocation directe dans la réservation commune : la trace FEFO reste immuable.
        for line in d.lignes:
            self.reserver({**line,'emplacement_id':d.source_id,'origine':combined.origine,'justification':d.justification},permission,combined)
        t=self.ajouter(TransfertStockModel,demande_id=d.id,reservation_id=combined.id,valide_par=self.user)
        totals={}
        for a in self.lignes(AllocationReservationModel,reservation_id=combined.id):
            lot=self.obtenir(StockEmplacementModel,a.stock_id).lot_id;totals[lot]=totals.get(lot,0)+a.quantite
        for lot,q in totals.items():self.ajouter(LigneTransfertStockModel,transfert_id=t.id,lot_id=lot,quantite=q,recue=0)
        d.statut='VALIDEE';self.s.flush();return self.transfert_detail(d)

    def expedier(self,key,kind="EXPEDITION"):
        d=self.demande_scope(key,'stock.transferer')
        if d.statut!='VALIDEE':raise ConflitStock('Valider la demande avant expédition.')
        t=self.s.scalar(select(TransfertStockModel).where(TransfertStockModel.demande_id==d.id))
        self.terminer_reservation(t.reservation_id,True,kind,'stock.transferer',True)
        t.expedie_par=self.user;t.expedie_le=now();d.statut='EXPEDIEE';self.s.flush();return self.transfert_detail(d)

    def recevoir(self,key,data,permission="stock.transfert.recevoir",kind="RECEPTION"):
        d=self.demande_scope(key,permission,True)
        if d.statut not in ('EXPEDIEE','RECEPTION_PARTIELLE'):raise ConflitStock('Aucune expédition disponible à recevoir.')
        dest=self.emplacement(d.destination_id,permission);t=self.s.scalar(select(TransfertStockModel).where(TransfertStockModel.demande_id==d.id))
        ids=set()
        for entry in data['lignes']:
            lid=ident(entry['ligne_id'])
            if lid in ids:raise ValueError('Ligne de réception dupliquée.')
            ids.add(lid);line=self.obtenir(LigneTransfertStockModel,lid)
            if line.transfert_id!=t.id:raise PermissionError('Ligne d’un autre transfert.')
            q=quantite(entry['quantite'])
            if line.recue+q>line.quantite:raise ConflitStock('Réception supérieure à la quantité expédiée.')
            lot=self.obtenir(LotModel,line.lot_id);self.mouvement(self.balance(lot,dest),q,0,kind,'Transfert '+str(d.id),data.get('justification'));line.recue+=q
        ecarts=[{'ligne_id':str(l.id),'manquant':l.quantite-l.recue} for l in self.lignes(LigneTransfertStockModel,transfert_id=t.id) if l.quantite!=l.recue]
        if data.get('cloturer') and ecarts and not data.get('justification'):raise ValueError('Clôture avec écart : justification obligatoire.')
        self.ajouter(ReceptionTransfertModel,transfert_id=t.id,lignes=jsonable_encoder(data['lignes']),ecarts=ecarts,justification=data.get('justification'),auteur_id=self.user)
        d.statut='ECART_CLOTURE' if ecarts and data.get('cloturer') else 'RECEPTION_PARTIELLE' if ecarts else 'RECUE';self.s.flush();return self.transfert_detail(d)

    def transfert_interne(self,data):
        source=self.emplacement(data['source_id'],'stock.transferer');dest=self.emplacement(data['destination_id'],'stock.transferer')
        if source.site_id!=dest.site_id:raise ValueError('Transfert interne : même site requis.')
        d=self.creer_demande(data);self.valider_demande(d['id'],'stock.transferer');self.expedier(d['id'],'TRANSFERT_SORTIE')
        t=self.transfert_detail(self.obtenir(DemandeTransfertModel,d['id']))
        return self.recevoir(d['id'],{'lignes':[{'ligne_id':l['id'],'quantite':l['quantite']} for l in t['lignes']],'cloturer':True,'justification':data['justification']},'stock.transferer','TRANSFERT_ENTREE')

    def transfert_detail(self,d):
        t=self.s.scalar(select(TransfertStockModel).where(TransfertStockModel.demande_id==d.id))
        lines=[]
        for x in self.lignes(LigneTransfertStockModel,transfert_id=t.id) if t else []:
            l=self.obtenir(LotModel,x.lot_id);p=self.s.get(ConditionnementModel,l.conditionnement_id);prod=self.s.get(ProduitModel,p.produit_id)
            lines.append({**serial(x),'lot':l.numero,'produit':prod.nom+' · '+p.libelle})
        if not t:
            for x in d.lignes:
                p,_=self.conditionnement(x['conditionnement_id'],False);prod=self.s.get(ProduitModel,p.produit_id);lines.append({**x,'produit':prod.nom+' · '+p.libelle})
        return {**serial(d),'transfert':serial(t) if t else None,'lignes':lines,'receptions':[serial(x) for x in self.lignes(ReceptionTransfertModel,transfert_id=t.id)] if t else []}

    def creer_inventaire(self,data,site):
        if data['type']=='COMPLET':
            # Complet pour les emplacements explicitement retenus ; aucune zone implicite d'un autre périmètre.
            if any(z.get('conditionnement_ids') for z in data['zones']):raise ValueError('Un inventaire complet ne filtre pas les conditionnements.')
        inventory=self.ajouter(InventaireModel,site_id=site,nom=texte(data['nom'],200),type=data['type'],snapshot_sequence=self.repo.sequence(self.org),auteur_id=self.user)
        stocks=set()
        for z in data['zones']:
            loc=self.emplacement(z['emplacement_id'],'stock.inventaire.gerer')
            if loc.site_id!=site:raise PermissionError('Zone d’un autre site.')
            zone=self.ajouter(ZoneInventaireModel,inventaire_id=inventory.id,emplacement_id=loc.id_emplacement,site_id=site,nom=texte(z['nom'],200))
            query=select(StockEmplacementModel).join(LotModel,LotModel.id==StockEmplacementModel.lot_id).where(StockEmplacementModel.emplacement_id==loc.id_emplacement,StockEmplacementModel.organisation_id==self.org)
            if z.get('conditionnement_ids'):
                for pid in z['conditionnement_ids']:self.conditionnement(pid)
                query=query.where(LotModel.conditionnement_id.in_([ident(x) for x in z['conditionnement_ids']]))
            rows=list(self.s.scalars(query))
            if not rows:raise ValueError('Zone sans stock enregistré : enregistrer les lots/emplacements avant la photographie.')
            for b in rows:
                if b.id in stocks:raise ValueError('Un stock ne peut appartenir à deux zones de cet inventaire.')
                overlap=self.s.scalar(select(LigneInventaireModel.id).join(ZoneInventaireModel,ZoneInventaireModel.id==LigneInventaireModel.zone_id).join(InventaireModel,InventaireModel.id==ZoneInventaireModel.inventaire_id).where(LigneInventaireModel.stock_id==b.id,InventaireModel.statut=='OUVERT',InventaireModel.id!=inventory.id))
                if overlap:raise ConflitStock('Stock déjà photographié dans un inventaire ouvert : valider ou annuler celui-ci avant une nouvelle photographie.')
                stocks.add(b.id);self.ajouter(LigneInventaireModel,zone_id=zone.id,stock_id=b.id,theorique=b.physique)
        return self.inventaire_detail(inventory,manage=True)

    def inventaire_scope(self,key,permission):
        row=self.obtenir(InventaireModel,key)
        for z in self.lignes(ZoneInventaireModel,inventaire_id=row.id):self.emplacement(z.emplacement_id,permission)
        return row

    def participant(self,zone_id,user_id):
        z=self.obtenir(ZoneInventaireModel,zone_id);inv=self.obtenir(InventaireModel,z.inventaire_id)
        self.emplacement(z.emplacement_id,'stock.inventaire.gerer')
        if inv.statut!='OUVERT':raise ConflitStock('Inventaire clôturé.')
        user=self.s.get(UtilisateurModel,ident(user_id))
        if not user or user.organisation_id!=self.org or not user.actif:raise PermissionError('Participant incompatible.')
        return serial(self.ajouter(ParticipantZoneInventaireModel,zone_id=z.id,utilisateur_id=user.id_utilisateur))

    def compter(self,key,data):
        line=self.obtenir(LigneInventaireModel,key);zone=self.obtenir(ZoneInventaireModel,line.zone_id);inv=self.obtenir(InventaireModel,zone.inventaire_id)
        self.emplacement(zone.emplacement_id,'stock.inventaire.compter')
        if not any(p.utilisateur_id==self.user for p in self.lignes(ParticipantZoneInventaireModel,zone_id=zone.id)):raise PermissionError('Affectation explicite à cette zone requise.')
        if inv.statut!='OUVERT':raise ConflitStock('Inventaire déjà validé.')
        q=data['quantite']
        if isinstance(q,bool) or not isinstance(q,int) or not 0<=q<=1_000_000_000:raise ValueError('Comptage entier positif ou nul requis.')
        if line.compte is not None and not data.get('justification'):raise ValueError('Recomptage : justification obligatoire.')
        if data.get('motif_id'):self.obtenir(MotifEcartInventaireModel,data['motif_id'])
        seq=self.repo.sequence(self.org)
        self.ajouter(ComptageInventaireModel,ligne_id=line.id,quantite=q,sequence=seq,auteur_id=self.user,justification=data.get('justification'))
        line.compte=q;line.comptage_sequence=seq;line.motif_id=data.get('motif_id');line.justification=data.get('justification');self.s.flush()
        return {'id':str(line.id),'compte':q,'nombre_comptages':len(self.lignes(ComptageInventaireModel,ligne_id=line.id))}

    def ecart(self,line,inv):
        moves=self.s.scalar(select(func.coalesce(func.sum(MouvementStockModel.delta_physique),0)).where(MouvementStockModel.stock_id==line.stock_id,MouvementStockModel.sequence>inv.snapshot_sequence,MouvementStockModel.sequence<=line.comptage_sequence))
        return ecart_inventaire(line.theorique,moves,line.compte)

    def valider_inventaire(self,key):
        inv=self.inventaire_scope(key,'stock.inventaire.valider')
        if inv.statut!='OUVERT':raise ConflitStock('Inventaire déjà validé.')
        for z in self.lignes(ZoneInventaireModel,inventaire_id=inv.id):
            for line in self.lignes(LigneInventaireModel,zone_id=z.id):
                if line.compte is None:raise ValueError('Toutes les lignes nécessitent un comptage.')
                line.ecart=self.ecart(line,inv)
                if line.ecart:
                    if not line.motif_id or not line.justification:raise ValueError('Chaque écart exige un motif et une justification de comptage.')
                    self.mouvement(self.obtenir(StockEmplacementModel,line.stock_id),line.ecart,0,'AJUSTEMENT_INVENTAIRE','Inventaire '+str(inv.id),line.justification)
        inv.statut='VALIDE';inv.valide_par=self.user;inv.valide_le=now();self.s.flush();return self.inventaire_detail(inv,True)

    def inventaire_detail(self,inv,reveal=False,manage=False,selected_zone=None,line_page=1,line_size=25):
        result={**serial(inv),'zones':[]}
        first=True
        if not reveal:result.pop('snapshot_sequence',None)
        for zone in self.lignes(ZoneInventaireModel,inventaire_id=inv.id):
            participants=self.lignes(ParticipantZoneInventaireModel,zone_id=zone.id)
            if not reveal and not manage and not any(x.utilisateur_id==self.user for x in participants):continue
            self.emplacement(zone.emplacement_id,'stock.inventaire.valider' if reveal else 'stock.inventaire.gerer' if manage else 'stock.inventaire.compter')
            rows=[]
            active=(zone.id==selected_zone) if selected_zone else first
            first=False
            total=self.s.scalar(select(func.count()).select_from(LigneInventaireModel).where(LigneInventaireModel.zone_id==zone.id))
            query=select(LigneInventaireModel).where(LigneInventaireModel.zone_id==zone.id).order_by(LigneInventaireModel.id).offset((line_page-1)*line_size).limit(line_size)
            for line in list(self.s.scalars(query)) if active else []:
                b=self.obtenir(StockEmplacementModel,line.stock_id);lot=self.obtenir(LotModel,b.lot_id);pack=self.s.get(ConditionnementModel,lot.conditionnement_id);prod=self.s.get(ProduitModel,pack.produit_id)
                row={**serial(line),'produit':prod.nom,'conditionnement':pack.libelle,'lot':lot.numero,'peremption':str(lot.peremption) if lot.peremption else None,'comptages':[serial(x) for x in self.lignes(ComptageInventaireModel,ligne_id=line.id)]}
                if reveal:row['ecart_calcule']=self.ecart(line,inv) if line.compte is not None else None
                else:
                    for field in ('theorique','ecart','stock_id','comptage_sequence'):row.pop(field,None)
                    for c in row['comptages']:c.pop('sequence',None)
                rows.append(row)
            result['zones'].append({**serial(zone),'participants':[serial(x) for x in participants],'lignes':rows,'total':total,'page':line_page if active else 1,'active':active})
        return result
