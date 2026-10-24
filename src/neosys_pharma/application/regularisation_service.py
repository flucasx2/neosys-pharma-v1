"""P4.5 : clôtures et compensations sous le même verrou transactionnel P3/P4."""
from decimal import Decimal
from uuid import uuid4
from hashlib import sha256
from sqlalchemy import select,func
from fastapi.encoders import jsonable_encoder
from neosys_pharma.application.caisse_service import serial
from neosys_pharma.application.etats_caisse_presentation import detail_flux,sections_flux
from neosys_pharma.application.stock_service import ident
from neosys_pharma.domain.caisse import francs,MODES
from neosys_pharma.domain.stock import ConflitStock,perime
from neosys_pharma.infrastructure.caisse_models import *
from neosys_pharma.infrastructure.regularisation_models import *
from neosys_pharma.infrastructure.vente_models import VenteModel,LigneVenteModel,ReservationVenteModel
from neosys_pharma.infrastructure.stock_models import StockEmplacementModel,LotModel,AllocationReservationModel,ReservationStockModel
from neosys_pharma.infrastructure.organisation_models import CoffreModel,SiteModel,OrganisationModel
from neosys_pharma.infrastructure.securite_models import UtilisateurModel
from neosys_pharma.infrastructure.prise_en_charge_models import (
    LigneCalculPriseEnChargeModel, RealisationPriseEnChargeModel,
)

class RegularisationService:
    def __init__(self,cash):
        self.cash=cash;self.stock=cash.stock;self.s=cash.s;self.org=cash.org;self.site=cash.site;self.vente=cash.vente
    def access(self,p,loc=None):self.stock.access(p,self.site,loc)
    def revision(self,row,data):
        if row.revision!=data['revision']:raise ConflitStock('Dossier modifié : actualiser.')
    def trace(self,type,**data):self.cash.trace('P4.5:'+type,**data)
    def dossier(self,cls,key,p):
        row=self.stock.obtenir(cls,key)
        if row.site_id!=self.site:raise PermissionError('Dossier hors du site courant.')
        self.cash.session(row.session_id,p)
        return row
    def coffre(self,key,p):
        self.access(p);row=self.s.get(CoffreModel,ident(key))
        if not row or row.site_id!=self.site or not row.actif:raise PermissionError('Coffre absent, inactif ou hors site.')
        return row
    def solde_coffre(self,key):
        return self.s.scalar(select(func.coalesce(func.sum(MouvementFinancierModel.montant),0)).where(MouvementFinancierModel.organisation_id==self.org,MouvementFinancierModel.coffre_id==ident(key)))
    def mouvement(self,type,origine,montant,reason,session=None,coffre=None,mode='ESPECES'):
        return self.stock.ajouter(MouvementFinancierModel,site_id=self.site,session_id=session.id if session else None,coffre_id=coffre.id_coffre if coffre else None,mode=mode,montant=montant,type=type,origine=origine,auteur_id=self.stock.user,justification=reason)
    def fonds(self,data):
        session=self.cash.session(data['session_id'],'caisse.fonds.gerer',True);self.revision(session,data)
        amount=francs(data['montant'])
        if data['sens']=='SORTIE':
            amount=-amount
            if Decimal(self.cash.session_detail(session)['especes_attendues'])+amount<0:raise ConflitStock('Espèces insuffisantes.')
        m=self.mouvement('FONDS_'+data['sens'],self.stock.op,amount,data['justification'],session=session);session.revision+=1
        self.trace('FONDS',mouvement=serial(m));return serial(m)
    def transfert(self,data):
        session=self.cash.session(data['session_id'],'caisse.transfert.demander');self.revision(session,data)
        if session.etat!='OUVERTE':raise ConflitStock('Session ouverte requise.')
        coffre=self.coffre(data['coffre_id'],'caisse.transfert.demander')
        row=self.stock.ajouter(TransfertFondsModel,site_id=self.site,session_id=session.id,coffre_id=coffre.id_coffre,sens=data['sens'],montant=francs(data['montant']),demandeur_id=self.stock.user,justification=data['justification'])
        self.trace('TRANSFERT_DEMANDE',dossier=serial(row));return serial(row)
    def transfert_action(self,key,data,action):
        permission={'autoriser':'caisse.transfert.autoriser','expedier':'caisse.transfert.expedier','recevoir':'caisse.transfert.recevoir','annuler':'caisse.transfert.autoriser'}[action]
        row=self.dossier(TransfertFondsModel,key,permission);self.revision(row,data)
        session=self.cash.session(row.session_id,permission);coffre=self.coffre(row.coffre_id,permission)
        if session.etat!='OUVERTE' and action!='annuler':raise ConflitStock('Session fermée : transfert incompatible.')
        if action=='autoriser':
            if row.etat!='DEMANDE':raise ConflitStock('Demande déjà traitée.')
            row.autorisateur_id=self.stock.user;row.etat='AUTORISE'
        elif action=='annuler':
            if row.etat not in ('DEMANDE','AUTORISE'):raise ConflitStock('Fonds expédiés : annulation interdite.')
            row.etat='ANNULE'
        elif action=='expedier':
            if row.etat!='AUTORISE':raise ConflitStock('Autorisation préalable requise.')
            if row.autorisateur_id==self.stock.user:
                self.access('caisse.transfert.deroger',session.emplacement_id);self.trace('DEROGATION_SEPARATION',transfert_id=row.id,justification=data['justification'])
            if row.sens=='CAISSE_COFFRE':
                self.cash.session(session.id,permission,True)
                if Decimal(self.cash.session_detail(session)['especes_attendues'])<row.montant:raise ConflitStock('Espèces insuffisantes.')
                self.mouvement('TRANSFERT_EXPEDIE',row.id,-row.montant,data['justification'],session=session)
            else:
                if self.solde_coffre(coffre.id_coffre)<row.montant:raise ConflitStock('Fonds du coffre insuffisants.')
                self.mouvement('TRANSFERT_EXPEDIE',row.id,-row.montant,data['justification'],coffre=coffre)
            row.expediteur_id=self.stock.user;row.etat='EN_TRANSIT';session.revision+=1
        else:
            if row.etat!='EN_TRANSIT':raise ConflitStock('Transfert non expédié ou déjà reçu.')
            if row.expediteur_id==self.stock.user:raise PermissionError('Expéditeur et réceptionnaire doivent être différents.')
            if row.sens=='CAISSE_COFFRE':self.mouvement('TRANSFERT_RECU',row.id,row.montant,data['justification'],coffre=coffre)
            else:
                self.cash.session(session.id,permission,True);self.mouvement('TRANSFERT_RECU',row.id,row.montant,data['justification'],session=session)
            row.receptionnaire_id=self.stock.user;row.etat='RECU';session.revision+=1
        row.revision+=1;document=None
        if action=='recevoir':
            import base64
            names={k:self.s.get(UtilisateurModel,value).nom for k,value in [('demandeur',row.demandeur_id),('autorisateur',row.autorisateur_id),('expediteur',row.expediteur_id),('receptionnaire',row.receptionnaire_id)] if value}
            snapshot,pdf,digest=self.document('TRANSFERT DE FONDS CONFIRMÉ',row.id,[{'titre':'Circuit et montant','colonnes':['Sens','Caisse / session','Coffre','Montant FCFA'],'lignes':[[row.sens,str(session.id),coffre.nom,str(row.montant)]]},{'titre':'Responsables et preuve de réception','colonnes':['Intervenant','Identité'],'lignes':list(names.items())+[['Justification',data['justification']]]}])
            document={'instantane':snapshot,'pdf_base64':base64.b64encode(pdf).decode(),'pdf_sha256':digest}
        self.trace('TRANSFERT_'+action.upper(),dossier=serial(row),justification=data['justification'],document=document);return serial(row)
    def ecart(self,key,data):
        session=self.cash.session(key,'caisse.ecart.reconnaitre');self.revision(session,data)
        if session.etat!='FERMEE':raise ConflitStock('Reconnaissance après comptage et fermeture.')
        row=self.stock.ajouter(ReconnaissanceEcartModel,session_id=session.id,auteur_id=self.stock.user,ecart=Decimal(self.cash.session_detail(session)['ecart_especes']),justification=data['justification'])
        self.trace('ECART_RECONNU',ecart=serial(row));return serial(row)
    def document(self,title,reference,sections):
        org=self.s.get(OrganisationModel,self.org);site=self.s.get(SiteModel,self.site);user=self.s.get(UtilisateurModel,self.stock.user)
        data={'titre':title,'reference':str(reference),'organisation':org.nom_commercial,'site':site.nom,'date':now().isoformat(),'responsable':user.nom if user else None,'sections':sections}
        from neosys_pharma.infrastructure.regularisation_pdf import document_pdf
        pdf=document_pdf(data);return data,pdf,sha256(pdf).hexdigest()
    def session_summary(self,session):
        payments=self.s.scalars(select(MouvementCaisseModel).where(MouvementCaisseModel.organisation_id==self.org,MouvementCaisseModel.session_id==session.id)).all()
        grouped=self.stock.lignes(MouvementCaisseGroupeModel,session_id=session.id)
        extras=self.stock.lignes(MouvementFinancierModel,session_id=session.id)
        modes={mode:str(sum((m.montant_net for m in payments if m.mode==mode),Decimal(0))+sum((m.montant_net for m in grouped if m.mode==mode),Decimal(0))+sum((m.montant for m in extras if m.mode==mode),Decimal(0))) for mode in MODES}
        identities={}
        def add(mode,mid,label,value):
            key=mode+':'+(str(mid) if mid else 'HISTORIQUE')
            if key not in identities:identities[key]={'mode':mode,'moyen_id':str(mid) if mid else None,'libelle':label or mode,'montant_net':Decimal(0)}
            identities[key]['montant_net']+=value
        def confirmed(mode,confirmation_id,value):
            cf=self.stock.obtenir(ConfirmationReglementModel,confirmation_id) if confirmation_id else None
            add(mode,cf.moyen_id if cf else None,cf.moyen_libelle if cf else mode,value)
        for movement in payments:
            payment=self.stock.obtenir(ReglementModel,movement.reglement_id)
            confirmed(movement.mode,payment.confirmation_id,movement.montant_net)
        for movement in grouped:
            payment=self.stock.obtenir(ReglementGroupeModel,movement.reglement_id)
            confirmed(movement.mode,payment.confirmation_id,movement.montant_net)
        for movement in extras:
            if movement.type=='REMBOURSEMENT':
                refund=self.stock.obtenir(RemboursementModel,movement.origine)
                for payment in refund.reglements:
                    if payment['mode']==movement.mode:add(payment['mode'],payment.get('moyen_id'),payment.get('moyen_libelle'),-Decimal(payment['montant']))
            elif movement.type=='ACQUIS_RESTITUE':
                refund=self.stock.obtenir(RemboursementModel,movement.origine)
                cf=self.stock.obtenir(ConfirmationReglementModel,refund.confirmation_id)
                confirmed(cf.mode,cf.id,movement.montant)
            else:add(movement.mode,None,movement.mode,movement.montant)
        for mode in MODES:
            if sum((row['montant_net'] for row in identities.values() if row['mode']==mode),Decimal(0))!=Decimal(modes[mode]):
                raise ConflitStock('Totaux par moyen incompatibles avec les mouvements de caisse.')
        return self.cash.session_detail(session)|{'nets_par_mode':modes,'nets_par_moyen':{key:{**row,'montant_net':str(row['montant_net'])} for key,row in sorted(identities.items())}}

    def cloture_x(self,data):
        session=self.cash.session(data['session_id'],'caisse.cloture.x');self.revision(session,data)
        if self.stock.lignes(SessionClotureeZModel,session_id=session.id):raise ConflitStock('Session déjà incluse dans une clôture Z historique.')
        p=self.cash.periode();key=uuid4();summary=self.session_summary(session);flux=detail_flux(self,[session])
        snap,pdf,digest=self.document('ÉTAT X — CAISSE',key,[{'titre':'Session et comptage','colonnes':['Session','État','Fond initial','Espèces attendues','Comptées','Écart'],'lignes':[[str(session.id),session.etat,str(session.fond_initial),summary['especes_attendues'],str(session.comptage_final) if session.comptage_final is not None else 'NON COMPTÉ',summary['ecart_especes'] or 'NON COMPTÉ']]},{'titre':'Mouvements nets par moyen','colonnes':['Moyen','Montant FCFA'],'lignes':[[r['libelle']+' / '+r['mode'],r['montant_net']] for r in summary['nets_par_moyen'].values()]}]+sections_flux(flux))
        snap['session']=summary;snap['detail_flux']=flux
        row=self.stock.ajouter(ClotureModel,id=key,site_id=self.site,session_id=session.id,periode_id=p.id,type='X',auteur_id=self.stock.user,instantane=snap,pdf=pdf,pdf_sha256=digest)
        self.trace('ETAT_X',document_id=row.id);return serial(row)
    def unresolved(self):
        query=select(ConfirmationReglementModel).join(VenteModel,VenteModel.id==ConfirmationReglementModel.vente_id).where(ConfirmationReglementModel.organisation_id==self.org,VenteModel.site_id==self.site)
        result=[]
        for c in self.s.scalars(query):
            if self.stock.lignes(ReglementModel,confirmation_id=c.id):continue
            group_reglements=self.stock.lignes(ReglementGroupeModel,confirmation_id=c.id)
            if group_reglements:
                group=self.stock.obtenir(EncaissementGroupeModel,group_reglements[0].dossier_id)
                if group.etat=='FINALISE':continue
                if group.etat=='ABANDONNE':continue
            refunded=self.stock.lignes(RemboursementModel,confirmation_id=c.id,etat='EXECUTE')
            if not refunded:result.append(c)
        return result
    def cloture_z(self,data):
        self.access('caisse.cloture.z');p=self.cash.periode()
        if p.id!=ident(data['periode_id']):raise ConflitStock('Période déjà clôturée ou modifiée.')
        sessions=self.stock.lignes(SessionCaisseModel,site_id=self.site)
        if any(s.etat=='OUVERTE' for s in sessions):raise ConflitStock('Fermer toutes les sessions du site avant Z.')
        if self.unresolved():raise ConflitStock('Paiements acquis non finalisés : rapprochement ou restitution confirmée obligatoire.')
        if any(t.etat not in ('RECU','ANNULE') for t in self.stock.lignes(TransfertFondsModel,site_id=self.site)):raise ConflitStock('Transferts de fonds non résolus.')
        if any(r.etat not in ('EXECUTE','ANNULE') for r in self.stock.lignes(RemboursementModel,site_id=self.site)):raise ConflitStock('Remboursements non exécutés.')
        # An obligation cannot silently disappear merely because no refund request exists yet.
        for r in self.stock.lignes(RetourVenteModel,site_id=self.site):
            if r.montant and not self.stock.lignes(RemboursementModel,retour_id=r.id,etat='EXECUTE'):raise ConflitStock('Retour à rembourser avant Z.')
        previous={x.session_id for x in self.stock.lignes(SessionClotureeZModel)};sessions=[s for s in sessions if s.id not in previous]
        for session in sessions:
            ecart=Decimal(self.cash.session_detail(session)['ecart_especes'])
            recognized=self.stock.lignes(ReconnaissanceEcartModel,session_id=session.id)
            if ecart and (not recognized or recognized[0].ecart!=ecart):raise ConflitStock('Écart non reconnu et justifié.')
        cancelled=[]
        for v in self.stock.lignes(VenteModel,site_id=self.site):
            if v.etat in ('ENCAISSEE','ANNULEE'):continue
            # Site-scoped Z permission authorizes the complete site operation, not an implicit work assignment.
            for line in self.vente.lignes(v):
                for link in self.stock.lignes(ReservationVenteModel,ligne_id=line.id):
                    reservation=self.stock.obtenir(ReservationStockModel,link.reservation_id)
                    if reservation.statut!='ACTIVE':continue
                    for allocation in self.stock.lignes(AllocationReservationModel,reservation_id=reservation.id):
                        balance=self.stock.obtenir(StockEmplacementModel,allocation.stock_id)
                        if balance.site_id!=self.site:raise PermissionError('Réservation étrangère au site clôturé.')
                    # The explicitly checked site-wide Z permission delegates this exact
                    # cancellation only; no P3 permission is granted to the operator.
                    self.stock.terminer_reservation(reservation.id,permission=None,interne=True)
            self.vente.invalider_remises(v);before=v.etat;v.etat='ANNULEE';v.revision+=1
            self.vente.evenement(v,'ANNULATION_Z',avant=before,periode_id=p.id,justification=data['justification']);cancelled.append(str(v.id))
        encs=self.stock.lignes(EncaissementModel,periode_id=p.id)
        totals={m:Decimal(0) for m in MODES};means={}
        for session in sessions:
            summary=self.session_summary(session)
            for mode,val in summary['nets_par_mode'].items():totals[mode]+=Decimal(val)
            for code,detail in summary['nets_par_moyen'].items():
                if code not in means:means[code]=detail|{'montant_net':Decimal(0)}
                means[code]['montant_net']+=Decimal(detail['montant_net'])
        flux=detail_flux(self,sessions)
        key=uuid4();snap,pdf,digest=self.document('CLÔTURE Z — SITE',key,[{'titre':'Période Z '+str(p.numero),'colonnes':['Ventes encaissées','Préparations annulées','Sessions fermées'],'lignes':[[len(encs),len(cancelled),len(sessions)]]},{'titre':'Mouvements nets par moyen','colonnes':['Moyen','Montant FCFA'],'lignes':[[r['libelle']+' / '+r['mode'],str(r['montant_net'])] for r in means.values()]},{'titre':'Comptages et écarts conservés','colonnes':['Session','Attendu','Compté','Écart'],'lignes':[[str(s.id),self.cash.session_detail(s)['especes_attendues'],str(s.comptage_final),self.cash.session_detail(s)['ecart_especes']] for s in sessions]}]+sections_flux(flux))
        snap.update(detail_flux=flux,nets_par_mode={m:str(v) for m,v in totals.items()},nets_par_moyen={k:{**v,'montant_net':str(v['montant_net'])} for k,v in means.items()},periode_z=p.numero,preparations_annulees=cancelled,sessions=[self.session_summary(s) for s in sessions],justification=data['justification'],etat='EFFECTIVE')
        row=self.stock.ajouter(ClotureModel,id=key,site_id=self.site,session_id=None,periode_id=p.id,type='Z',auteur_id=self.stock.user,instantane=snap,pdf=pdf,pdf_sha256=digest)
        for session in sessions:self.stock.ajouter(SessionClotureeZModel,session_id=session.id,cloture_id=row.id)
        p.etat='CLOTUREE';self.s.flush()
        next_=self.stock.ajouter(PeriodeCaisseSiteModel,site_id=self.site,numero=p.numero+1)
        self.trace('CLOTURE_Z',cloture_id=row.id,ancienne_periode=p.id,nouvelle_periode=next_.id);return serial(row)
    def retour(self,data):
        enc=self.stock.obtenir(EncaissementModel,data['encaissement_id']);v=self.vente.obtenir(enc.vente_id,'vente.retour.gerer')
        rows=[];seen=set();amount=Decimal(0);gross_amount=0;organisme_amount=0
        snapshots={x['id']:x for x in enc.instantane['lignes'] if x['actif']}
        realization=self.s.scalar(select(RealisationPriseEnChargeModel).where(
            RealisationPriseEnChargeModel.encaissement_id==enc.id,
            RealisationPriseEnChargeModel.organisation_id==self.org,
        ))
        client_paid_by_line={}
        if realization:
            calc_lines=self.stock.lignes(LigneCalculPriseEnChargeModel,calcul_id=realization.calcul_id)
            client_paid_by_line={row.ligne_vente_id:row.part_client_xaf for row in calc_lines}
            if not client_paid_by_line:raise ConflitStock('Ventilation client/organisme absente : retour financier bloqué.')
        for entry in data['lignes']:
            line=self.stock.obtenir(LigneVenteModel,entry['ligne_id']);balance=self.stock.obtenir(StockEmplacementModel,entry['stock_id'])
            if line.vente_id!=v.id or not line.actif or line.id not in [ident(x) for x in snapshots]:raise PermissionError('Ligne étrangère à la vente encaissée.')
            self.stock.emplacement(balance.emplacement_id,'vente.retour.gerer')
            if balance.site_id!=self.site:raise PermissionError('Retour hors site.')
            refs={x.reservation_id for x in self.stock.lignes(ReservationVenteModel,ligne_id=line.id) if self.stock.obtenir(ReservationStockModel,x.reservation_id).statut=='CONSOMMEE'}
            allocations=[x for rid in refs for x in self.stock.lignes(AllocationReservationModel,reservation_id=rid,stock_id=balance.id)]
            available=sum(x.quantite for x in allocations)
            old=self.stock.lignes(LigneRetourVenteModel,ligne_id=line.id)
            used=sum(x.quantite for x in old if x.stock_id==balance.id)
            staged=sum(x['quantite'] for x in rows if x['line'].id==line.id)
            if entry['quantite']>available-used or (line.id,balance.id) in seen:raise ConflitStock('Quantité de lot déjà retournée ou non vendue.')
            n=sum(x.quantite for x in old)+staged;q=entry['quantite']
            if n+q>line.quantite:raise ConflitStock('Quantité supérieure au solde retournable.')
            hist=snapshots[str(line.id)];ttc=int(Decimal(str(hist['montants_appliques']['ttc'])));tva=int(Decimal(str(hist['montants_appliques']['tva'])))
            net=(ttc*(n+q)//line.quantite)-(ttc*n//line.quantite);tax=(tva*(n+q)//line.quantite)-(tva*n//line.quantite)
            client_line_total=client_paid_by_line.get(line.id,ttc)
            client_before=client_line_total*n//line.quantite
            client_after=client_line_total*(n+q)//line.quantite
            client_return=client_after-client_before
            org_return=net-client_return
            rows.append({'line':line,'balance':balance,'quantite':q,'montant':Decimal(client_return),
                'instantane':{'designation':hist['designation'],'conditionnement':hist['conditionnement'],
                    'quantite':q,'ttc':str(net),'part_client_xaf':client_return,
                    'part_organismes_xaf':org_return,'tva':str(tax),'ht':str(net-tax),
                    'quantite_cumulee':n+q,'historique':hist}})
            amount+=client_return;gross_amount+=net;organisme_amount+=org_return;seen.add((line.id,balance.id))
        snapshot={'vente_id':str(v.id),'numero_encaissement':enc.instantane['numero_encaissement'],
            'lignes':[r['instantane'] for r in rows],
            'prise_en_charge':({'realisation_id':str(realization.id),
                'calcul_id':str(realization.calcul_id),'montant_client_xaf':int(amount),
                'montant_organismes_xaf':organisme_amount,'montant_ttc_xaf':gross_amount}
                if realization else None)}
        ret=self.stock.ajouter(RetourVenteModel,encaissement_id=enc.id,site_id=self.site,auteur_id=self.stock.user,
            montant=amount,montant_ttc_xaf=gross_amount,montant_organismes_xaf=organisme_amount,
            justification=data['justification'],instantane=snapshot)
        for r in rows:
            line=self.stock.ajouter(LigneRetourVenteModel,retour_id=ret.id,ligne_id=r['line'].id,stock_id=r['balance'].id,quantite=r['quantite'],montant=r['montant'],instantane=r['instantane'])
            self.stock.ajouter(QuarantaineModel,ligne_retour_id=line.id,stock_id=r['balance'].id,quantite=r['quantite'])
        group=self.s.scalar(select(EncaissementGroupeVenteModel).where(EncaissementGroupeVenteModel.organisation_id==self.org,EncaissementGroupeVenteModel.encaissement_id==enc.id))
        group_reference=self.stock.obtenir(EncaissementGroupeModel,group.dossier_id).reference if group else None
        provenance={'retour_id':str(ret.id),'vente_id':str(v.id),'encaissement_id':str(enc.id),
            'numero_encaissement':enc.instantane['numero_encaissement'],'date_reception':ret.date.isoformat(),
            'justification':data['justification'],'client_historique':enc.instantane.get('client') or (enc.instantane.get('fidelite') or {}).get('client'),
            'groupe_id':str(group.dossier_id) if group else None,'reference_groupe':group_reference,'etat_reception':'EN_CONTROLE',
            'montant_client_xaf':str(amount),'montant_ttc_xaf':gross_amount}
        physical=[]
        for r in rows:
            lot=self.stock.obtenir(LotModel,r['balance'].lot_id)
            physical.append({**r['instantane'],'ligne_id':str(r['line'].id),'stock_id':str(r['balance'].id),
                'lot':lot.numero,'peremption':str(lot.peremption) if lot.peremption else None})
        snap,pdf,digest=self.document('RÉCEPTION DE RETOUR — NE VAUT PAS REMBOURSEMENT',ret.id,[
            {'titre':'Réception physique en quarantaine — contrôle sanitaire à effectuer','colonnes':['Vente','Encaissement original','Retour'],
             'lignes':[[str(v.id),enc.instantane['numero_encaissement']+(' / '+group_reference if group_reference else ''),str(ret.id)]]},
            {'titre':'Produits reçus — prix historiques','colonnes':['Produit / conditionnement','Lot / péremption','Quantité','HT FCFA','TVA FCFA','TTC FCFA'],
             'lignes':[[r['designation']+' / '+r['conditionnement'],(r['lot'] or 'SANS LOT')+' / '+(r['peremption'] or 'NON RENSEIGNÉE'),r['quantite'],r['ht'],r['tva'],r['ttc']] for r in physical]},
            {'titre':'Motif et portée du document','colonnes':['Justification','Remboursable au client FCFA','Statut'],
             'lignes':[[data['justification'],str(amount),'Réception uniquement ; aucune conformité sanitaire ou restitution attestée']]}])
        snap.update(provenance=provenance,lignes=physical)
        doc=self.stock.ajouter(DocumentRetourModel,retour_id=ret.id,auteur_id=self.stock.user,instantane=snap,pdf=pdf,pdf_sha256=digest)
        self.trace('RETOUR_QUARANTAINE',retour=serial(ret),document_id=doc.id,pdf_sha256=digest)
        return serial(ret)|{'document':serial(doc)}
    def retour_scope(self,key,p):
        ret=self.stock.obtenir(RetourVenteModel,key);enc=self.stock.obtenir(EncaissementModel,ret.encaissement_id);self.vente.obtenir(enc.vente_id,p);return ret,enc
    def controle(self,key,data):
        q=self.stock.obtenir(QuarantaineModel,key);b=self.stock.obtenir(StockEmplacementModel,q.stock_id);self.stock.emplacement(b.emplacement_id,'stock.quarantaine.decider')
        if b.site_id!=self.site:raise PermissionError('Quarantaine hors site.')
        if q.etat!='EN_CONTROLE':raise ConflitStock('Décision sanitaire déjà définitive.')
        checks={k:data[k] for k in ('identite_conforme','lot_conforme','integrite_conforme','conservation_conforme')}
        lot=self.stock.obtenir(LotModel,b.lot_id)
        _,rules=self.stock.conditionnement(lot.conditionnement_id,operation=data['liberer'])
        checks['peremption_conforme']=bool(
            (lot.peremption is not None and not perime(lot.peremption,self.stock.jour))
            or (lot.peremption is None and not rules['gestion_peremption'])
        )
        if data['liberer']:
            if not all(checks.values()):raise ValueError('Contrôles sanitaires non satisfaits : remise en vente interdite.')
            self.stock.mouvement(b,q.quantite,0,'RETOUR_LIBERE',str(q.ligne_retour_id),data['justification']);q.etat='LIBEREE'
        else:
            q.etat='REFUSEE'
        decision=self.stock.ajouter(DecisionQuarantaineModel,quarantaine_id=q.id,auteur_id=self.stock.user,decision=q.etat,controles=checks,justification=data['justification'])
        self.trace('DECISION_SANITAIRE',decision=serial(decision));return serial(q)
    def budget_reglements(self,enc):
        """Soldes réservés par identité de moyen, y compris allocations groupées."""
        paid={}
        def add(mode,confirmation_id,amount):
            cf=self.stock.obtenir(ConfirmationReglementModel,confirmation_id) if confirmation_id else None
            mid=str(cf.moyen_id) if cf and cf.moyen_id else None
            key=(mode,mid)
            if key not in paid:paid[key]={'mode':mode,'moyen_id':mid,'libelle':cf.moyen_libelle if cf and cf.moyen_id else mode,'montant':Decimal(0)}
            paid[key]['montant']+=amount
        link=self.s.scalar(select(EncaissementGroupeVenteModel).where(EncaissementGroupeVenteModel.organisation_id==self.org,EncaissementGroupeVenteModel.encaissement_id==enc.id))
        if link:
            for allocation in self.stock.lignes(AllocationReglementGroupeModel,dossier_id=link.dossier_id,vente_id=link.vente_id):
                payment=self.stock.obtenir(ReglementGroupeModel,allocation.reglement_id)
                add(payment.mode,payment.confirmation_id,allocation.montant)
        else:
            for payment in self.stock.lignes(ReglementModel,encaissement_id=enc.id):add(payment.mode,payment.confirmation_id,payment.montant-payment.rendu)
        returnids={r.id for r in self.stock.lignes(RetourVenteModel,encaissement_id=enc.id)}
        for old in self.stock.lignes(RemboursementModel):
            if old.retour_id in returnids and old.etat!='ANNULE':
                for payment in old.reglements:
                    key=(payment.get('mode_origine',payment['mode']),payment.get('moyen_origine_id'))
                    if key not in paid:raise ConflitStock('Origine historique de remboursement incohérente.')
                    paid[key]['montant']-=Decimal(payment['montant'])
        return paid

    def moyen_remboursement(self,payment):
        """L'exception ne concerne que l'identité historique, jamais une substitution."""
        mode=payment['mode'];mid=payment.get('moyen_id')
        historique=(mode,mid)==(payment.get('mode_origine') or mode,payment.get('moyen_origine_id'))
        famille_active=mode in self.cash.config()['modes']
        if not historique and not famille_active:raise ValueError('Moyen de remboursement non activé.')
        target=self.cash.moyen(mode,mid,actif=not historique)
        if mode=='ESPECES' and mid:raise ValueError('Les espèces ne portent pas de fournisseur.')
        return target, historique and (not famille_active or (target is not None and not target.actif))

    def remboursement(self,data):
        session=self.cash.session(data['session_id'],'caisse.remboursement.demander');self.revision(session,data)
        if session.etat!='OUVERTE':raise ConflitStock('Session ouverte requise.')
        if bool(data.get('retour_id'))==bool(data.get('confirmation_id')):raise ValueError('Retour ou paiement acquis unique requis.')
        if data.get('retour_id'):
            ret,enc=self.retour_scope(data['retour_id'],'caisse.remboursement.demander');amount=ret.montant
            paid=self.budget_reglements(enc)
        else:
            confirmation=self.stock.obtenir(ConfirmationReglementModel,data['confirmation_id']);self.vente.obtenir(confirmation.vente_id,'caisse.remboursement.demander')
            if (self.stock.lignes(ReglementModel,confirmation_id=confirmation.id)
                    or any(self.stock.obtenir(EncaissementGroupeModel,row.dossier_id).etat=='FINALISE'
                           for row in self.stock.lignes(ReglementGroupeModel,confirmation_id=confirmation.id))):
                raise ConflitStock('Paiement déjà encaissé : utiliser un retour de vente.')
            amount=confirmation.montant;mid=str(confirmation.moyen_id) if confirmation.moyen_id else None
            paid={(confirmation.mode,mid):{'mode':confirmation.mode,'moyen_id':mid,'libelle':confirmation.moyen_libelle or confirmation.mode,'montant':amount}}
        source={'retour_id':data.get('retour_id')} if data.get('retour_id') else {'confirmation_id':data['confirmation_id']}
        previous=self.stock.lignes(RemboursementModel,**source)
        if any(old.etat!='ANNULE' for old in previous):raise ConflitStock('Remboursement déjà demandé ou exécuté.')
        replacement=data.get('remplace_id')
        if previous:
            latest=next((old for old in previous if not any(other.remplace_id==old.id for other in previous)),None)
            if not latest or replacement!=latest.id:raise ConflitStock('Désigner explicitement la dernière demande annulée à remplacer.')
        elif replacement:raise ConflitStock('Aucune demande annulée de cette source à remplacer.')
        planned=[]
        for row in data['reglements']:
            mode=row['mode'];original=row.get('mode_origine') or mode;value=francs(row['montant'])
            mid=str(row['moyen_id']) if row.get('moyen_id') else None
            origin_id=str(row['moyen_origine_id']) if row.get('moyen_origine_id') else None
            target,_=self.moyen_remboursement({'mode':mode,'moyen_id':mid,'mode_origine':original,'moyen_origine_id':origin_id})
            if mode!='ESPECES' and not mid and (mode,None) not in paid:
                raise ValueError('Sélection explicite du moyen de remboursement requise.')
            if (original,origin_id)!=(mode,mid):self.access('caisse.remboursement.substituer',session.emplacement_id)
            budget=paid.get((original,origin_id))
            if not budget or value>budget['montant']:raise ConflitStock('Remboursement supérieur au règlement original disponible pour ce moyen.')
            budget['montant']-=value
            planned.append({'mode':mode,'mode_origine':original,'montant':str(value),
                'moyen_id':mid,'moyen_origine_id':origin_id,'moyen_libelle':target.libelle if target else mode,'moyen_origine_libelle':budget['libelle']})
        if sum((Decimal(r['montant']) for r in planned),Decimal(0))!=amount:raise ValueError('Remboursement intégral du retour ou paiement acquis requis ; répartir les moyens.')
        row=self.stock.ajouter(RemboursementModel,site_id=self.site,retour_id=data.get('retour_id'),confirmation_id=data.get('confirmation_id'),remplace_id=replacement,session_id=session.id,montant=amount,reglements=planned,demandeur_id=self.stock.user,justification=data['justification'])
        self.trace('REMBOURSEMENT_DEMANDE',dossier=serial(row));return serial(row)
    def refund_scope(self,key,p):
        r=self.dossier(RemboursementModel,key,p)
        if r.retour_id:self.retour_scope(r.retour_id,p)
        else:self.vente.obtenir(self.stock.obtenir(ConfirmationReglementModel,r.confirmation_id).vente_id,p)
        return r
    def annuler_remboursement(self,key,data):
        row=self.refund_scope(key,'caisse.remboursement.annuler');self.revision(row,data)
        if row.etat not in ('DEMANDE','AUTORISE'):raise ConflitStock('Seule une demande non exécutée peut être annulée.')
        reason=(data.get('justification') or '').strip()
        if not reason or data.get('attestation_absence_restitution') is not True:
            raise ValueError('Justification et attestation responsable d’absence de restitution requises.')
        if data.get('restitution_externe_incertaine') is not False:
            raise ConflitStock('Restitution externe incertaine : vérifier la preuve, annulation interdite.')
        if (self.stock.lignes(PieceFinanciereModel,remboursement_id=row.id)
                or self.stock.lignes(PreuveRemboursementModel,remboursement_id=row.id)
                or self.stock.lignes(MouvementFinancierModel,origine=row.id)
                or self.stock.lignes(AnnulationRemboursementModel,remboursement_id=row.id)):
            raise ConflitStock('Pièce, preuve ou mouvement lié : annulation interdite, diagnostic requis.')
        before=serial(row);row.etat='ANNULE';row.revision+=1
        event=self.stock.ajouter(AnnulationRemboursementModel,remboursement_id=row.id,auteur_id=self.stock.user,
            justification=reason,attestation_absence_restitution=True,revision_avant=before['revision'],
            revision_apres=row.revision,instantane={'avant':before,'apres':serial(row),'restitution_externe_incertaine':False})
        self.trace('REMBOURSEMENT_ANNULE',annulation=serial(event))
        return serial(row)
    def refund_action(self,key,data,action):
        permission='caisse.remboursement.autoriser' if action=='autoriser' else 'caisse.remboursement.executer'
        row=self.refund_scope(key,permission);self.revision(row,data)
        session=self.cash.session(row.session_id,permission,action=='executer')
        if session.etat!='OUVERTE':raise ConflitStock('Session fermée : remboursement incompatible.')
        if any((p['mode'],p.get('moyen_id'))!=(p['mode_origine'],p.get('moyen_origine_id')) for p in row.reglements):self.access('caisse.remboursement.substituer',session.emplacement_id)
        row.revision+=1
        if action=='autoriser':
            if row.etat!='DEMANDE':raise ConflitStock('Remboursement déjà autorisé ou exécuté.')
            row.etat='AUTORISE';row.autorisateur_id=self.stock.user
        else:
            if row.etat!='AUTORISE':raise ConflitStock('Autorisation préalable requise.')
            proofs=data['preuves']
            if len(proofs)!=len(row.reglements):raise ValueError('Une preuve par règlement de remboursement requise.')
            desactives=[]
            for payment,proof in zip(row.reglements,proofs,strict=True):
                _,desactive=self.moyen_remboursement(payment)
                if desactive:desactives.append(payment)
                if payment['mode']!='ESPECES' and (not (proof.get('reference') or '').strip() or not (proof.get('preuve') or '').strip()):raise ValueError('Référence et preuve externe obligatoires ; aucun prestataire simulé.')
            for payment,proof in zip(row.reglements,proofs,strict=True):
                if payment['mode']!='ESPECES':self.stock.ajouter(PreuveRemboursementModel,remboursement_id=row.id,mode=payment['mode'],reference=proof['reference'].strip(),preuve=proof['preuve'].strip())
            cash=sum((Decimal(x['montant']) for x in row.reglements if x['mode']=='ESPECES'),Decimal(0))
            if cash>Decimal(self.cash.session_detail(session)['especes_attendues']):raise ConflitStock('Espèces insuffisantes pour rembourser.')
            if row.confirmation_id and self.stock.lignes(ReglementModel,confirmation_id=row.confirmation_id):raise ConflitStock('Paiement encaissé entre-temps : restitution interdite.')
            if row.confirmation_id:
                cf=self.stock.obtenir(ConfirmationReglementModel,row.confirmation_id)
                self.mouvement('ACQUIS_RESTITUE',row.id,cf.montant,data['justification'],session=session,mode=cf.mode)
            for mode in MODES:
                value=sum((Decimal(x['montant']) for x in row.reglements if x['mode']==mode),Decimal(0))
                if value:self.mouvement('REMBOURSEMENT',row.id,-value,data['justification'],session=session,mode=mode)
            if row.retour_id:self.compenser(row.retour_id)
            row.etat='EXECUTE';session.revision+=1
            source=[]
            if row.retour_id:
                ret=self.stock.obtenir(RetourVenteModel,row.retour_id);enc=self.stock.obtenir(EncaissementModel,ret.encaissement_id)
                source=[{'titre':'Vente et retour historiques','colonnes':['Vente originale','Encaissement / période Z','Retour'],'lignes':[[str(enc.vente_id),enc.instantane['numero_encaissement']+' / '+str(enc.instantane['periode_z']),str(ret.id)]]},{'titre':'Produits retournés — montants après remises','colonnes':['Produit / conditionnement','Quantité','HT FCFA','TVA FCFA','TTC FCFA'],'lignes':[[l['designation']+' / '+l['conditionnement'],l['quantite'],l['ht'],l['tva'],l['ttc']] for l in ret.instantane['lignes']]}]
            else:source=[{'titre':'Paiement acquis restitué','colonnes':['Vente','Confirmation originale','Référence'],'lignes':[[str(cf.vente_id),str(cf.id),cf.reference]]}]
            snap,pdf,digest=self.document('REMBOURSEMENT CONFIRMÉ',row.id,source+[{'titre':'Règlements restitués','colonnes':['Moyen original','Moyen restitué','Montant FCFA','Référence','Preuve'],'lignes':[[p.get('moyen_origine_libelle',p['mode_origine']),p.get('moyen_libelle',p['mode']),p['montant'],proof.get('reference') or 'REMIS EN ESPÈCES',proof.get('preuve') or data['justification']] for p,proof in zip(row.reglements,proofs,strict=True)]}])
            snap.update(dossier=serial(row),preuves=proofs,justification=data['justification'])
            self.stock.ajouter(PieceFinanciereModel,remboursement_id=row.id,auteur_id=self.stock.user,instantane=snap,pdf=pdf,pdf_sha256=digest)
            if desactives:
                self.trace('REMBOURSEMENT_HISTORIQUE_MOYEN_DESACTIVE',dossier=serial(row),
                           moyens_desactives=desactives,preuves=proofs,justification=data['justification'])
        self.trace('REMBOURSEMENT_'+action.upper(),dossier=serial(row),justification=data['justification']);return serial(row)
    def compenser(self,key):
        ret=self.stock.obtenir(RetourVenteModel,key);enc=self.stock.obtenir(EncaissementModel,ret.encaissement_id)
        if not enc.compte_id:return
        gain=enc.instantane.get('fidelite') or {};total=int(Decimal(gain.get('eligible_paye','0')))
        if not total:return
        current=self.stock.obtenir(CompteFideliteModel,enc.compte_id)
        ids={r.id for r in self.stock.lignes(RetourVenteModel,encaissement_id=enc.id) if r.id==ret.id or self.stock.lignes(RemboursementModel,retour_id=r.id,etat='EXECUTE')}
        eligible={ident(x['ligne_id']) for x in gain['lignes']}
        base=sum(int(l.instantane.get('part_client_xaf',l.montant)) for r in ids
                 for l in self.stock.lignes(LigneRetourVenteModel,retour_id=r) if l.ligne_id in eligible)
        cumulative=int(gain['points_acquis'])*base//total
        previous=sum(x.points_revoques for r in ids if r!=ret.id for x in self.stock.lignes(CompensationRetourModel,retour_id=r))
        revoke=cumulative-previous;restore=0
        usages=self.stock.lignes(JournalFideliteModel,encaissement_id=enc.id,type='UTILISATION')
        if usages:
            used=sum(-x.delta_points for x in usages)
            historic=usages[0].details.get('base_eligible_historique')
            line_ids=usages[0].details.get('lignes_eligibles')
            if not historic or not line_ids:raise ConflitStock('Base historique de points utilisés manquante : régularisation impossible sans inventer une règle.')
            usedbase=sum(int(l.instantane.get('part_client_xaf',l.montant)) for r in ids
                         for l in self.stock.lignes(LigneRetourVenteModel,retour_id=r) if str(l.ligne_id) in line_ids)
            restored_before=sum(x.points_restitues for r in ids if r!=ret.id for x in self.stock.lignes(CompensationRetourModel,retour_id=r))
            restore=used*usedbase//int(Decimal(str(historic)))-restored_before
        debt_paid=min(current.dette,restore);current.dette-=debt_paid
        available=current.points+restore-debt_paid;take=min(revoke,available);debt=revoke-take
        current.points=available-take;current.dette+=debt;current.revision+=1
        details={'retour_id':str(ret.id),'points_restitues':restore,'dette_compensee':debt_paid,'points_revoques':revoke,'base_retour_cumulee':str(base),'base_historique':str(total),'bareme_historique':gain.get('bareme'),'dette_creee':debt}
        acquisition_=self.stock.lignes(JournalFideliteModel,encaissement_id=enc.id,type='ACQUISITION')
        journal=self.stock.ajouter(JournalFideliteModel,compte_id=current.id,encaissement_id=None,auteur_id=self.stock.user,type='COMPENSATION' if restore else 'REVOCATION',delta_points=restore-debt_paid-take,delta_dette=debt-debt_paid,compensation_de=acquisition_[0].id if acquisition_ else None,details=details)
        self.stock.ajouter(CompensationRetourModel,retour_id=ret.id,compte_id=current.id,journal_id=journal.id,points_restitues=restore,points_revoques=revoke,dette_creee=debt,details=details)
