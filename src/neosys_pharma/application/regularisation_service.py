"""P4.5 : clôtures et compensations sous le même verrou transactionnel P3/P4."""
from decimal import Decimal
from uuid import uuid4
from hashlib import sha256
from sqlalchemy import select,func
from fastapi.encoders import jsonable_encoder
from neosys_pharma.application.caisse_service import serial
from neosys_pharma.application.stock_service import ident
from neosys_pharma.domain.caisse import francs,MODES
from neosys_pharma.domain.stock import ConflitStock,perime
from neosys_pharma.infrastructure.caisse_models import *
from neosys_pharma.infrastructure.regularisation_models import *
from neosys_pharma.infrastructure.vente_models import VenteModel,LigneVenteModel,ReservationVenteModel
from neosys_pharma.infrastructure.stock_models import StockEmplacementModel,LotModel,AllocationReservationModel,ReservationStockModel
from neosys_pharma.infrastructure.organisation_models import CoffreModel,SiteModel,OrganisationModel
from neosys_pharma.infrastructure.securite_models import UtilisateurModel

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
        extras=self.stock.lignes(MouvementFinancierModel,session_id=session.id)
        modes={mode:str(sum((m.montant_net for m in payments if m.mode==mode),Decimal(0))+sum((m.montant for m in extras if m.mode==mode),Decimal(0))) for mode in MODES}
        return self.cash.session_detail(session)|{'nets_par_mode':modes}
    def cloture_x(self,data):
        session=self.cash.session(data['session_id'],'caisse.cloture.x');self.revision(session,data)
        if self.stock.lignes(SessionClotureeZModel,session_id=session.id):raise ConflitStock('Session déjà incluse dans une clôture Z historique.')
        p=self.cash.periode();key=uuid4();summary=self.session_summary(session)
        snap,pdf,digest=self.document('ÉTAT X — CAISSE',key,[{'titre':'Session et comptage','colonnes':['Session','État','Fond initial','Espèces attendues','Comptées','Écart'],'lignes':[[str(session.id),session.etat,str(session.fond_initial),summary['especes_attendues'],str(session.comptage_final) if session.comptage_final is not None else 'NON COMPTÉ',summary['ecart_especes'] or 'NON COMPTÉ']]},{'titre':'Mouvements nets par moyen','colonnes':['Moyen','Montant FCFA'],'lignes':list(summary['nets_par_mode'].items())}])
        snap['session']=summary
        row=self.stock.ajouter(ClotureModel,id=key,site_id=self.site,session_id=session.id,periode_id=p.id,type='X',auteur_id=self.stock.user,instantane=snap,pdf=pdf,pdf_sha256=digest)
        self.trace('ETAT_X',document_id=row.id);return serial(row)
    def unresolved(self):
        query=select(ConfirmationReglementModel).join(VenteModel,VenteModel.id==ConfirmationReglementModel.vente_id).where(ConfirmationReglementModel.organisation_id==self.org,VenteModel.site_id==self.site)
        result=[]
        for c in self.s.scalars(query):
            if self.stock.lignes(ReglementModel,confirmation_id=c.id):continue
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
        if any(r.etat!='EXECUTE' for r in self.stock.lignes(RemboursementModel,site_id=self.site)):raise ConflitStock('Remboursements non exécutés.')
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
        totals={m:Decimal(0) for m in MODES}
        for session in sessions:
            summary=self.session_summary(session)
            for mode,val in summary['nets_par_mode'].items():totals[mode]+=Decimal(val)
        key=uuid4();snap,pdf,digest=self.document('CLÔTURE Z — SITE',key,[{'titre':'Période Z '+str(p.numero),'colonnes':['Ventes encaissées','Préparations annulées','Sessions fermées'],'lignes':[[len(encs),len(cancelled),len(sessions)]]},{'titre':'Mouvements nets par moyen','colonnes':['Moyen','Montant FCFA'],'lignes':[[m,str(v)] for m,v in totals.items()]},{'titre':'Comptages et écarts conservés','colonnes':['Session','Attendu','Compté','Écart'],'lignes':[[str(s.id),self.cash.session_detail(s)['especes_attendues'],str(s.comptage_final),self.cash.session_detail(s)['ecart_especes']] for s in sessions]}])
        snap.update(periode_z=p.numero,preparations_annulees=cancelled,sessions=[self.session_summary(s) for s in sessions],justification=data['justification'],etat='EFFECTIVE')
        row=self.stock.ajouter(ClotureModel,id=key,site_id=self.site,session_id=None,periode_id=p.id,type='Z',auteur_id=self.stock.user,instantane=snap,pdf=pdf,pdf_sha256=digest)
        for session in sessions:self.stock.ajouter(SessionClotureeZModel,session_id=session.id,cloture_id=row.id)
        p.etat='CLOTUREE';self.s.flush()
        next_=self.stock.ajouter(PeriodeCaisseSiteModel,site_id=self.site,numero=p.numero+1)
        self.trace('CLOTURE_Z',cloture_id=row.id,ancienne_periode=p.id,nouvelle_periode=next_.id);return serial(row)
    def retour(self,data):
        enc=self.stock.obtenir(EncaissementModel,data['encaissement_id']);v=self.vente.obtenir(enc.vente_id,'vente.retour.gerer')
        rows=[];seen=set();amount=Decimal(0);snapshots={x['id']:x for x in enc.instantane['lignes'] if x['actif']}
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
            rows.append({'line':line,'balance':balance,'quantite':q,'montant':Decimal(net),'instantane':{'designation':hist['designation'],'conditionnement':hist['conditionnement'],'quantite':q,'ttc':str(net),'tva':str(tax),'ht':str(net-tax),'quantite_cumulee':n+q,'historique':hist}});amount+=net;seen.add((line.id,balance.id))
        ret=self.stock.ajouter(RetourVenteModel,encaissement_id=enc.id,site_id=self.site,auteur_id=self.stock.user,montant=amount,justification=data['justification'],instantane={'vente_id':str(v.id),'numero_encaissement':enc.instantane['numero_encaissement'],'lignes':[r['instantane'] for r in rows]})
        for r in rows:
            line=self.stock.ajouter(LigneRetourVenteModel,retour_id=ret.id,ligne_id=r['line'].id,stock_id=r['balance'].id,quantite=r['quantite'],montant=r['montant'],instantane=r['instantane'])
            self.stock.ajouter(QuarantaineModel,ligne_retour_id=line.id,stock_id=r['balance'].id,quantite=r['quantite'])
        self.trace('RETOUR_QUARANTAINE',retour=serial(ret));return serial(ret)
    def retour_scope(self,key,p):
        ret=self.stock.obtenir(RetourVenteModel,key);enc=self.stock.obtenir(EncaissementModel,ret.encaissement_id);self.vente.obtenir(enc.vente_id,p);return ret,enc
    def controle(self,key,data):
        q=self.stock.obtenir(QuarantaineModel,key);b=self.stock.obtenir(StockEmplacementModel,q.stock_id);self.stock.emplacement(b.emplacement_id,'stock.quarantaine.decider')
        if b.site_id!=self.site:raise PermissionError('Quarantaine hors site.')
        if q.etat!='EN_CONTROLE':raise ConflitStock('Décision sanitaire déjà définitive.')
        checks={k:data[k] for k in ('identite_conforme','lot_conforme','integrite_conforme','conservation_conforme')}
        lot=self.stock.obtenir(LotModel,b.lot_id);checks['peremption_conforme']=bool(lot.peremption is None or not perime(lot.peremption,self.stock.jour))
        if data['liberer']:
            self.stock.conditionnement(lot.conditionnement_id)
            if not all(checks.values()):raise ValueError('Contrôles sanitaires non satisfaits : remise en vente interdite.')
            self.stock.mouvement(b,q.quantite,0,'RETOUR_LIBERE',str(q.ligne_retour_id),data['justification']);q.etat='LIBEREE'
        else:q.etat='REFUSEE'
        decision=self.stock.ajouter(DecisionQuarantaineModel,quarantaine_id=q.id,auteur_id=self.stock.user,decision=q.etat,controles=checks,justification=data['justification'])
        self.trace('DECISION_SANITAIRE',decision=serial(decision));return serial(q)
    def remboursement(self,data):
        session=self.cash.session(data['session_id'],'caisse.remboursement.demander');self.revision(session,data)
        if session.etat!='OUVERTE':raise ConflitStock('Session ouverte requise.')
        if bool(data.get('retour_id'))==bool(data.get('confirmation_id')):raise ValueError('Retour ou paiement acquis unique requis.')
        if data.get('retour_id'):
            ret,enc=self.retour_scope(data['retour_id'],'caisse.remboursement.demander');amount=ret.montant
            # Reserve original-mode budgets across all requested dossiers, including concurrent requests.
            paid={m:sum((r.montant-r.rendu for r in self.stock.lignes(ReglementModel,encaissement_id=enc.id) if r.mode==m),Decimal(0)) for m in MODES}
            returnids={r.id for r in self.stock.lignes(RetourVenteModel,encaissement_id=enc.id)}
            for old in self.stock.lignes(RemboursementModel):
                if old.retour_id in returnids:
                    for p in old.reglements:
                        original=p.get('mode_origine',p['mode']);paid[original]-=Decimal(p['montant'])
        else:
            confirmation=self.stock.obtenir(ConfirmationReglementModel,data['confirmation_id']);self.vente.obtenir(confirmation.vente_id,'caisse.remboursement.demander')
            if self.stock.lignes(ReglementModel,confirmation_id=confirmation.id):raise ConflitStock('Paiement déjà encaissé : utiliser un retour de vente.')
            amount=confirmation.montant;paid={m:amount if m==confirmation.mode else Decimal(0) for m in MODES}
        planned=[]
        for row in data['reglements']:
            mode=row['mode'];original=row.get('mode_origine') or mode;value=francs(row['montant'])
            if mode not in self.cash.config()['modes']:raise ValueError('Moyen de remboursement non activé.')
            if original!=mode:self.access('caisse.remboursement.substituer',session.emplacement_id)
            if value>paid[original]:raise ConflitStock('Remboursement supérieur au règlement original disponible.')
            paid[original]-=value;planned.append({'mode':mode,'mode_origine':original,'montant':str(value)})
        if sum((Decimal(r['montant']) for r in planned),Decimal(0))!=amount:raise ValueError('Remboursement intégral du retour ou paiement acquis requis ; répartir les moyens.')
        row=self.stock.ajouter(RemboursementModel,site_id=self.site,retour_id=data.get('retour_id'),confirmation_id=data.get('confirmation_id'),session_id=session.id,montant=amount,reglements=planned,demandeur_id=self.stock.user,justification=data['justification'])
        self.trace('REMBOURSEMENT_DEMANDE',dossier=serial(row));return serial(row)
    def refund_scope(self,key,p):
        r=self.dossier(RemboursementModel,key,p)
        if r.retour_id:self.retour_scope(r.retour_id,p)
        else:self.vente.obtenir(self.stock.obtenir(ConfirmationReglementModel,r.confirmation_id).vente_id,p)
        return r
    def refund_action(self,key,data,action):
        permission='caisse.remboursement.autoriser' if action=='autoriser' else 'caisse.remboursement.executer'
        row=self.refund_scope(key,permission);self.revision(row,data)
        session=self.cash.session(row.session_id,permission,action=='executer')
        if session.etat!='OUVERTE':raise ConflitStock('Session fermée : remboursement incompatible.')
        if any(p['mode']!=p['mode_origine'] for p in row.reglements):self.access('caisse.remboursement.substituer',session.emplacement_id)
        row.revision+=1
        if action=='autoriser':
            if row.etat!='DEMANDE':raise ConflitStock('Remboursement déjà autorisé ou exécuté.')
            row.etat='AUTORISE';row.autorisateur_id=self.stock.user
        else:
            if row.etat!='AUTORISE':raise ConflitStock('Autorisation préalable requise.')
            proofs=data['preuves']
            if len(proofs)!=len(row.reglements):raise ValueError('Une preuve par règlement de remboursement requise.')
            for payment,proof in zip(row.reglements,proofs,strict=True):
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
            snap,pdf,digest=self.document('REMBOURSEMENT CONFIRMÉ',row.id,source+[{'titre':'Règlements restitués','colonnes':['Moyen original','Moyen restitué','Montant FCFA','Référence','Preuve'],'lignes':[[p['mode_origine'],p['mode'],p['montant'],proof.get('reference') or 'REMIS EN ESPÈCES',proof.get('preuve') or data['justification']] for p,proof in zip(row.reglements,proofs,strict=True)]}])
            snap.update(dossier=serial(row),preuves=proofs,justification=data['justification'])
            self.stock.ajouter(PieceFinanciereModel,remboursement_id=row.id,auteur_id=self.stock.user,instantane=snap,pdf=pdf,pdf_sha256=digest)
        self.trace('REMBOURSEMENT_'+action.upper(),dossier=serial(row),justification=data['justification']);return serial(row)
    def compenser(self,key):
        ret=self.stock.obtenir(RetourVenteModel,key);enc=self.stock.obtenir(EncaissementModel,ret.encaissement_id)
        if not enc.compte_id:return
        gain=enc.instantane.get('fidelite') or {};total=int(Decimal(gain.get('eligible_paye','0')))
        if not total:return
        current=self.stock.obtenir(CompteFideliteModel,enc.compte_id)
        ids={r.id for r in self.stock.lignes(RetourVenteModel,encaissement_id=enc.id) if r.id==ret.id or self.stock.lignes(RemboursementModel,retour_id=r.id,etat='EXECUTE')}
        eligible={ident(x['ligne_id']) for x in gain['lignes']}
        base=sum(int(l.montant) for r in ids for l in self.stock.lignes(LigneRetourVenteModel,retour_id=r) if l.ligne_id in eligible)
        cumulative=int(gain['points_acquis'])*base//total
        previous=sum(x.points_revoques for r in ids if r!=ret.id for x in self.stock.lignes(CompensationRetourModel,retour_id=r))
        revoke=cumulative-previous;restore=0
        usages=self.stock.lignes(JournalFideliteModel,encaissement_id=enc.id,type='UTILISATION')
        if usages:
            used=sum(-x.delta_points for x in usages)
            historic=usages[0].details.get('base_eligible_historique')
            line_ids=usages[0].details.get('lignes_eligibles')
            if not historic or not line_ids:raise ConflitStock('Base historique de points utilisés manquante : régularisation impossible sans inventer une règle.')
            usedbase=sum(int(l.montant) for r in ids for l in self.stock.lignes(LigneRetourVenteModel,retour_id=r) if str(l.ligne_id) in line_ids)
            restored_before=sum(x.points_restitues for r in ids if r!=ret.id for x in self.stock.lignes(CompensationRetourModel,retour_id=r))
            restore=used*usedbase//int(Decimal(str(historic)))-restored_before
        debt_paid=min(current.dette,restore);current.dette-=debt_paid
        available=current.points+restore-debt_paid;take=min(revoke,available);debt=revoke-take
        current.points=available-take;current.dette+=debt;current.revision+=1
        details={'retour_id':str(ret.id),'points_restitues':restore,'dette_compensee':debt_paid,'points_revoques':revoke,'base_retour_cumulee':str(base),'base_historique':str(total),'bareme_historique':gain.get('bareme'),'dette_creee':debt}
        acquisition_=self.stock.lignes(JournalFideliteModel,encaissement_id=enc.id,type='ACQUISITION')
        journal=self.stock.ajouter(JournalFideliteModel,compte_id=current.id,encaissement_id=None,auteur_id=self.stock.user,type='COMPENSATION' if restore else 'REVOCATION',delta_points=restore-debt_paid-take,delta_dette=debt-debt_paid,compensation_de=acquisition_[0].id if acquisition_ else None,details=details)
        self.stock.ajouter(CompensationRetourModel,retour_id=ret.id,compte_id=current.id,journal_id=journal.id,points_restitues=restore,points_revoques=revoke,dette_creee=debt,details=details)
