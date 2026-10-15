"""Transaction finale P4/P3. Les confirmations externes ne consomment aucun stock."""
import hashlib,re
from datetime import date
from decimal import Decimal
from uuid import UUID
from sqlalchemy import select,func
from fastapi.encoders import jsonable_encoder
from neosys_pharma.application.stock_service import ident
from neosys_pharma.domain.caisse import MODES,francs,repartir_paiements,acquisition,RegleFiscaleFidelite
from neosys_pharma.domain.catalogue import texte
from neosys_pharma.domain.stock import ConflitStock
from neosys_pharma.infrastructure.caisse_models import *
from neosys_pharma.infrastructure.organisation_models import CaisseModel,OrganisationModel,SiteModel
from neosys_pharma.infrastructure.catalogue_models import ProduitModel,CategorieProduitModel
from neosys_pharma.infrastructure.vente_models import ReservationVenteModel
from neosys_pharma.infrastructure.client_models import ClientModel
from neosys_pharma.infrastructure.stock_models import ReservationStockModel

def serial(row):
    return jsonable_encoder({c.name:getattr(row,c.name) for c in row.__table__.columns if c.name!='pdf'},custom_encoder={Decimal:str})

class CaisseService:
    def __init__(self,vente):
        self.vente=vente;self.stock=vente.stock;self.s=vente.s;self.org=vente.org;self.site=vente.site

    def trace(self,type,**data):
        self.stock.ajouter(EvenementCaisseModel,auteur_id=self.stock.user,type=type,donnees=jsonable_encoder({**data,'operation_id':str(self.stock.op)}))

    def periode(self):
        p=self.s.scalar(select(PeriodeCaisseSiteModel).filter_by(organisation_id=self.org,site_id=self.site,etat='OUVERTE'))
        if not p:
            if self.stock.lignes(PeriodeCaisseSiteModel,site_id=self.site):raise ConflitStock('Ouvrir une période après clôture Z effective ; aucun reset implicite.')
            p=self.stock.ajouter(PeriodeCaisseSiteModel,site_id=self.site)
        return p

    def appel(self,v):
        a=self.s.scalar(select(AppelVenteModel).filter_by(organisation_id=self.org,vente_id=v.id))
        if not a:
            p=self.periode();a=self.stock.ajouter(AppelVenteModel,vente_id=v.id,periode_id=p.id,numero=p.prochain_appel);p.prochain_appel+=1
        return serial(a)|{'affichage':str(a.numero).zfill(4)}

    def config(self):
        row=self.s.scalar(select(ParametrageCaisseModel).filter_by(organisation_id=self.org))
        return serial(row) if row else {'modes':[],'ticket_appel':False,'revision':0}

    def configurer(self,data):
        row=self.s.scalar(select(ParametrageCaisseModel).filter_by(organisation_id=self.org))
        if data['revision']!=(row.revision if row else 0):raise ConflitStock('Configuration modifiée : actualiser.')
        if len(set(data['modes']))!=len(data['modes']) or any(x not in MODES for x in data['modes']):raise ValueError('Moyens de paiement invalides.')
        before=serial(row) if row else None
        if row:row.modes=data['modes'];row.ticket_appel=data['ticket_appel'];row.revision+=1
        else:row=self.stock.ajouter(ParametrageCaisseModel,modes=data['modes'],ticket_appel=data['ticket_appel'])
        self.trace('PARAMETRAGE',avant=before,apres=serial(row));return serial(row)

    def caisse(self,key,permission):
        row=self.s.get(CaisseModel,ident(key))
        if not row or not row.actif:raise PermissionError('Caisse absente ou inactive.')
        loc=self.stock.emplacement(row.emplacement_id,permission)
        if loc.site_id!=self.site:raise PermissionError('Caisse hors du site courant.')
        return row,loc

    def session(self,key,permission,active=False):
        row=self.stock.obtenir(SessionCaisseModel,key)
        self.caisse(row.caisse_id,permission)
        if active and (row.etat!='OUVERTE' or row.caissier_id!=self.stock.user):raise PermissionError('Session ouverte du caissier courant requise.')
        return row

    def ouvrir(self,data):
        caisse,loc=self.caisse(data['caisse_id'],'caisse.session.gerer')
        if self.stock.lignes(SessionCaisseModel,caisse_id=caisse.id_caisse,etat='OUVERTE'):raise ConflitStock('Une session est déjà ouverte : la fermer avant changement de caissier.')
        row=self.stock.ajouter(SessionCaisseModel,caisse_id=caisse.id_caisse,site_id=self.site,emplacement_id=loc.id_emplacement,caissier_id=self.stock.user,fond_initial=francs(data['fond_initial'],True))
        self.trace('SESSION_OUVERTE',session=serial(row));return self.session_detail(row)

    def session_detail(self,row):
        cash=self.s.scalar(select(func.coalesce(func.sum(MouvementCaisseModel.montant_net),0)).where(MouvementCaisseModel.session_id==row.id,MouvementCaisseModel.organisation_id==self.org,MouvementCaisseModel.mode=='ESPECES'))
        from neosys_pharma.infrastructure.regularisation_models import MouvementFinancierModel
        extras=self.s.scalar(select(func.coalesce(func.sum(MouvementFinancierModel.montant),0)).where(MouvementFinancierModel.session_id==row.id,MouvementFinancierModel.organisation_id==self.org,MouvementFinancierModel.mode=='ESPECES'))
        expected=row.fond_initial+cash+extras
        return serial(row)|{'especes_attendues':str(expected),'ecart_especes':str(row.comptage_final-expected) if row.comptage_final is not None else None}

    def fermer(self,key,data):
        row=self.session(key,'caisse.session.gerer',True)
        if row.revision!=data['revision']:raise ConflitStock('Session modifiée : actualiser.')
        from neosys_pharma.infrastructure.regularisation_models import TransfertFondsModel,RemboursementModel
        if any(x.etat not in ('RECU','ANNULE') for x in self.stock.lignes(TransfertFondsModel,session_id=row.id)) or any(x.etat!='EXECUTE' for x in self.stock.lignes(RemboursementModel,session_id=row.id)):raise ConflitStock('Résoudre les transferts et remboursements avant fermeture.')
        row.comptage_final=francs(data['comptage_final'],True);row.ferme_le=now();row.etat='FERMEE';row.revision+=1
        self.trace('SESSION_FERMEE',session=self.session_detail(row),justification=data['justification']);return self.session_detail(row)

    def verifier_vente(self,key,session,revision,permission='caisse.encaisser'):
        v=self.vente.obtenir(key,permission);self.vente.revision(v,revision)
        if v.etat!='TRANSMISE' or v.caisse_id!=session.caisse_id or v.emplacement_id!=session.emplacement_id:raise ConflitStock('Préparation transmise à cette caisse requise.')
        if v.mode!='SANS_TIERS':raise ValueError('Crédit et tiers payant non finalisables.')
        return v

    def confirmer(self,key,data):
        session=self.session(data['session_id'],'caisse.paiement.confirmer',True)
        v=self.verifier_vente(key,session,data['revision'],'caisse.paiement.confirmer')
        if data['mode']=='ESPECES' or data['mode'] not in self.config()['modes']:raise ValueError('Moyen non espèces actif requis.')
        if data['source']=='TECHNIQUE_PRESTATAIRE':raise ValueError('Aucun prestataire bancaire intégré : confirmation technique indisponible.')
        if data['mode'] in ('CARTE','MOBILE_MONEY') and data['source']!='MANUEL_TERMINAL':raise ValueError('Confirmation manuelle du terminal indépendant requise.')
        if data['mode'] in ('CHEQUE','VIREMENT') and data['source']!='MANUEL_JUSTIFICATIF':raise ValueError('Confirmation du justificatif requise.')
        ref=data['reference'].strip()
        if not ref or not data['preuve'].strip():raise ValueError('Référence vérifiable et preuve de confirmation obligatoires.')
        row=self.stock.ajouter(ConfirmationReglementModel,vente_id=v.id,session_id=session.id,revision_vente=v.revision,mode=data['mode'],montant=francs(data['montant']),reference=ref,source=data['source'],preuve=data['preuve'],auteur_id=self.stock.user)
        self.trace('PAIEMENT_CONFIRME',confirmation=serial(row));return serial(row)

    def rapprocher(self,key,confirmation_id,data):
        session=self.session(data['session_id'],'caisse.paiement.confirmer',True)
        v=self.verifier_vente(key,session,data['revision'],'caisse.paiement.confirmer')
        confirmation=self.stock.obtenir(ConfirmationReglementModel,confirmation_id)
        if confirmation.vente_id!=v.id:raise PermissionError('Confirmation d’une autre vente.')
        if self.stock.lignes(ReglementModel,confirmation_id=confirmation.id):raise ConflitStock('Paiement déjà utilisé.')
        self.trace('PAIEMENT_RAPPROCHE',confirmation_id=confirmation.id,vente_id=v.id,session_id=session.id,revision_vente=v.revision,justification=data['justification'])
        return serial(confirmation)|{'revision_rapprochee':v.revision,'session_rapprochee':str(session.id)}

    def rapprochement_compatible(self,confirmation,v,session):
        if confirmation.vente_id!=v.id:return False
        if confirmation.session_id==session.id and confirmation.revision_vente==v.revision:return True
        for event in self.stock.lignes(EvenementCaisseModel,type='PAIEMENT_RAPPROCHE'):
            d=event.donnees
            if d.get('confirmation_id')==str(confirmation.id) and d.get('vente_id')==str(v.id) and d.get('session_id')==str(session.id) and d.get('revision_vente')==v.revision:return True
        return False

    def compte(self,key,permission='fidelite.consulter'):
        self.stock.access(permission,self.site,None)
        row=self.stock.obtenir(CompteFideliteModel,key)
        client=self.stock.obtenir(ClientFideliteModel,row.client_id)
        return serial(row)|{'client':serial(client),'cartes':[serial(c) for c in self.stock.lignes(CarteFideliteModel,compte_id=row.id)],'utilisation_disponible':False,'motif_blocage':'Règle fiscale fidélité non validée.'}

    def creer_compte(self,data):
        phone=re.sub(r'[\s().-]','',data['telephone']) if data.get('telephone') else None
        profile=self.stock.ajouter(ClientModel,nom=texte(data['nom'],200),telephone=phone)
        client=self.stock.ajouter(ClientFideliteModel,nom=profile.nom,telephone=phone,profil_client_id=profile.id)
        row=self.stock.ajouter(CompteFideliteModel,client_id=client.id)
        self.trace('COMPTE_CREE',client=serial(client),compte_id=row.id)
        return self.compte(row.id,'fidelite.gerer')

    def creer_compte_pour_client(self,client_id):
        profile=self.stock.obtenir(ClientModel,client_id)
        if not profile.actif:raise ValueError('Une fiche client inactive ne peut pas adhérer à la fidélité.')
        old=self.s.scalar(select(ClientFideliteModel).filter_by(organisation_id=self.org,profil_client_id=profile.id))
        if old:raise ValueError('Cette fiche client possède déjà un compte fidélité.')
        client=self.stock.ajouter(ClientFideliteModel,nom=profile.nom,telephone=profile.telephone,profil_client_id=profile.id)
        row=self.stock.ajouter(CompteFideliteModel,client_id=client.id)
        self.trace('COMPTE_CREE',client=serial(client),profil_client_id=profile.id,compte_id=row.id)
        return self.compte(row.id,'fidelite.gerer')

    def carte(self,key,data):
        row=self.stock.obtenir(CompteFideliteModel,key)
        if row.revision!=data['revision']:raise ConflitStock('Compte modifié : actualiser.')
        old=None
        if data.get('remplace_id'):
            old=self.stock.obtenir(CarteFideliteModel,data['remplace_id'])
            if old.compte_id!=row.id:raise PermissionError('Carte d’un autre compte.')
            if old.etat=='REMPLACEE':raise ConflitStock('Carte déjà remplacée.')
            old.etat='REMPLACEE'
        card=self.stock.ajouter(CarteFideliteModel,compte_id=row.id,code=data['code'].strip(),type=data['type'],remplace_id=old.id if old else None)
        row.revision+=1;self.trace('CARTE_CREEE',carte=serial(card));return self.compte(row.id,'fidelite.gerer')

    def opposer(self,key,data):
        card=self.stock.obtenir(CarteFideliteModel,key);row=self.stock.obtenir(CompteFideliteModel,card.compte_id)
        if row.revision!=data['revision'] or card.etat!='ACTIVE':raise ConflitStock('Carte ou compte modifié.')
        card.etat='OPPOSEE';row.revision+=1
        self.trace('CARTE_OPPOSEE',carte=serial(card),justification=data['justification']);return self.compte(row.id,'fidelite.gerer')

    def bareme(self,kind):
        rows=self.s.scalars(select(BaremeFideliteModel).where(BaremeFideliteModel.organisation_id==self.org,BaremeFideliteModel.type==kind,BaremeFideliteModel.debut<=self.stock.jour,(BaremeFideliteModel.fin.is_(None))|(BaremeFideliteModel.fin>=self.stock.jour))).all()
        if len(rows)>1:raise ConflitStock('Barèmes actifs incompatibles.')
        return rows[0] if rows else None

    def ajouter_bareme(self,data):
        if data['fin'] and data['fin']<data['debut']:raise ValueError('Fin antérieure au début.')
        if len(set(data['categories']))!=len(data['categories']) or not data['categories']:raise ValueError('Catégories éligibles explicites obligatoires.')
        for cid in data['categories']:
            category=self.s.get(CategorieProduitModel,ident(cid))
            if not category or category.organisation_id!=self.org:raise PermissionError('Catégorie hors organisation.')
        if data['type']=='CONVERSION' and data['plafond_xaf'] is None and data['plafond_pourcentage'] is None:raise ValueError('Plafond de réduction explicite obligatoire.')
        end=data['fin'] or date.max
        for old in self.stock.lignes(BaremeFideliteModel,type=data['type']):
            if old.debut<=end and (old.fin or date.max)>=data['debut']:raise ConflitStock('Périodes inclusives chevauchantes : clôturer explicitement le barème précédent.')
        row=self.stock.ajouter(BaremeFideliteModel,**{**data,'categories':[str(x) for x in data['categories']]})
        self.trace('BAREME_CREE',bareme=serial(row));return serial(row)

    def clore_bareme(self,key,data):
        row=self.stock.obtenir(BaremeFideliteModel,key)
        if row.fin is not None:raise ConflitStock('Barème déjà clôturé.')
        # Ne pas retirer une date déjà utilisée dans un encaissement historique.
        if data['fin']<row.debut or data['fin']<self.stock.jour:raise ValueError('Clôture antérieure au début ou à la date courante interdite.')
        row.fin=data['fin'];self.trace('BAREME_CLOTURE',bareme=serial(row));return serial(row)

    def categorie_eligible(self,cid,bareme):
        seen=set()
        while cid and cid not in seen:
            seen.add(cid)
            if str(cid) in bareme.categories:return True
            if not bareme.sous_categories:return False
            category=self.s.get(CategorieProduitModel,cid)
            if not category or category.organisation_id!=self.org:return False
            cid=category.parent_id
        return False

    def gagner(self,v,compte,finance):
        rule=self.bareme('ACQUISITION')
        if not rule:return {'points':0,'motif':'Aucun barème d’acquisition applicable.'}
        eligible=[]
        for row in self.vente.lignes(v):
            if row.actif and self.categorie_eligible(self.s.get(ProduitModel,row.produit_id).categorie_id,rule):
                eligible.append({'ligne_id':str(row.id),'ttc_paye':str(finance['lignes'][str(row.id)]['ttc'])})
        base=sum((Decimal(x['ttc_paye']) for x in eligible),Decimal(0))
        points=acquisition(base,rule.points,rule.montant_xaf)
        # Une éventuelle dette est compensée avant disponibilité de nouveaux points.
        compensation=min(points,compte.dette);compte.dette-=compensation;compte.points+=points-compensation;compte.revision+=1
        details={'bareme':serial(rule),'eligible_paye':str(base),'lignes':eligible,'points_acquis':points,'dette_compensee':compensation,'fractions_reportees':False}
        return details|{'solde':compte.points,'dette':compte.dette}

    def finaliser(self,key,data):
        session=self.session(data['session_id'],'caisse.encaisser',True)
        v=self.verifier_vente(key,session,data['revision'])
        if session.revision!=data['revision_session']:raise ConflitStock('Session modifiée : actualiser.')
        if data['points_utilises']:
            if not data['consentement']:raise ValueError('Consentement explicite du titulaire obligatoire.')
            self.stock.access('fidelite.utiliser',self.site,v.emplacement_id)
            if not data.get('compte_id'):raise ValueError('Compte fidélité obligatoire.')
            account=self.stock.obtenir(CompteFideliteModel,data['compte_id'])
            if account.dette:raise ConflitStock('Dette de points : nouvelle utilisation interdite.')
            RegleFiscaleFidelite().verifier_utilisation()
        requests=self.stock.lignes(self.vente.remise_model,vente_id=v.id)
        if any(r.statut=='DEMANDEE' for r in requests):raise ConflitStock('Remise en attente : encaissement interdit.')
        from neosys_pharma.domain.remises import montant_remise
        for r in requests:
            if r.statut=='AUTORISEE':
                eligible=self.vente.eligible(v,r);cap=self.vente.plafond_applicable(v,ident(r.autorisation['auteur_id']),r,montant_remise(r.type,r.valeur,eligible),eligible)
                if str(cap.id)!=r.autorisation['plafond']['id'] or cap.revision!=r.autorisation['plafond']['revision']:raise ConflitStock('Autorisation de remise à revalider.')
        finance=self.vente.finance(v);total=francs(finance['totaux']['ttc'],True)
        payments=[];used=set()
        for row in data['reglements']:
            if row['mode'] not in self.config()['modes']:raise ValueError('Moyen de paiement non activé.')
            montant=francs(row['montant']);confirmation=None
            if row['mode']!='ESPECES':
                if not row.get('confirmation_id'):raise ValueError('Confirmation indépendante obligatoire avant encaissement.')
                confirmation=self.stock.obtenir(ConfirmationReglementModel,row['confirmation_id'])
                if confirmation.id in used:raise ValueError('Confirmation utilisée plusieurs fois.')
                used.add(confirmation.id)
                if not self.rapprochement_compatible(confirmation,v,session) or confirmation.mode!=row['mode'] or confirmation.montant!=montant:raise ConflitStock('Confirmation incompatible ou préparation modifiée : rapprocher le paiement.')
                if self.stock.lignes(ReglementModel,confirmation_id=confirmation.id):raise ConflitStock('Confirmation déjà consommée.')
            elif row.get('confirmation_id'):raise ValueError('Référence de paiement non espèces incompatible avec espèces.')
            payments.append({'mode':row['mode'],'montant':montant,'confirmation_id':confirmation.id if confirmation else None,'confirmation':serial(confirmation) if confirmation else None})
        payments=repartir_paiements(total,payments)
        from neosys_pharma.infrastructure.regularisation_models import RemboursementModel
        if any(self.stock.lignes(RemboursementModel,confirmation_id=c,etat='EXECUTE') for c in used):raise ConflitStock('Paiement déjà restitué.')
        if any(self.stock.lignes(RemboursementModel,confirmation_id=c) for c in used):raise ConflitStock('Restitution demandée : paiement indisponible pour encaissement.')
        pending={c.id for c in self.stock.lignes(ConfirmationReglementModel,vente_id=v.id) if not self.stock.lignes(ReglementModel,confirmation_id=c.id) and not self.stock.lignes(RemboursementModel,confirmation_id=c.id,etat='EXECUTE')}
        if pending!=used:raise ConflitStock('Tous les paiements acquis confirmés doivent être rapprochés et intégrés ; ne pas laisser de règlement orphelin.')
        compte=None
        if data.get('compte_id'):
            self.stock.access('fidelite.consulter',self.site,v.emplacement_id)
            compte=self.stock.obtenir(CompteFideliteModel,data['compte_id'])
            if data['revision_compte']!=compte.revision:raise ConflitStock('Compte fidélité modifié : actualiser et reconfirmer le titulaire.')
        # Revalidation des réservations et des péremptions dans la même transaction.
        for row in self.vente.lignes(v):
            if not row.actif:continue
            links=self.stock.lignes(ReservationVenteModel,ligne_id=row.id)
            active=[self.stock.obtenir(ReservationStockModel,x.reservation_id) for x in links if self.stock.obtenir(ReservationStockModel,x.reservation_id).statut=='ACTIVE']
            if sum(sum(a['quantite'] for a in self.stock.reservation_detail(r)['allocations']) for r in active)!=row.quantite:raise ConflitStock('Réservation incomplète.')
            for reservation in active:self.stock.terminer_reservation(reservation.id,True,'VENTE','caisse.encaisser',True)
        p=self.periode();numero=p.prochain_encaissement;p.prochain_encaissement+=1
        org=self.s.get(OrganisationModel,self.org);site=self.s.get(SiteModel,self.site)
        snapshot=self.vente.detail(v)|{'organisation':org.nom_commercial,'site':site.nom,'date':now().isoformat(),'numero_encaissement':str(numero).zfill(4),'periode_z':p.numero,'reglements':jsonable_encoder(payments,custom_encoder={Decimal:str}),'caissier_id':str(self.stock.user),'fidelite':None,'etat':'ENCAISSEE'}
        gain=self.gagner(v,compte,finance) if compte else None
        if compte:snapshot['fidelite']=gain|{'client':serial(self.stock.obtenir(ClientFideliteModel,compte.client_id))}
        from neosys_pharma.infrastructure.caisse_pdf import recu_pdf
        pdf=recu_pdf(snapshot)
        enc=self.stock.ajouter(EncaissementModel,vente_id=v.id,session_id=session.id,periode_id=p.id,numero=numero,total_xaf=total,compte_id=compte.id if compte else None,instantane=snapshot,pdf=pdf,pdf_sha256=hashlib.sha256(pdf).hexdigest())
        if compte and 'bareme' in gain:
            self.stock.ajouter(JournalFideliteModel,compte_id=compte.id,encaissement_id=enc.id,auteur_id=self.stock.user,type='ACQUISITION',delta_points=gain['points_acquis']-gain['dette_compensee'],delta_dette=-gain['dette_compensee'],details=gain)
        for row in payments:
            payment=self.stock.ajouter(ReglementModel,encaissement_id=enc.id,mode=row['mode'],montant=row['montant'],rendu=row['rendu'],confirmation_id=row['confirmation_id'])
            self.stock.ajouter(MouvementCaisseModel,session_id=session.id,reglement_id=payment.id,auteur_id=self.stock.user,mode=payment.mode,montant_net=payment.montant-payment.rendu)
        v.etat='ENCAISSEE';v.revision+=1;session.revision+=1
        self.vente.evenement(v,'ENCAISSEMENT',encaissement_id=enc.id,numero=numero,totaux=finance['totaux'],pdf_sha256=enc.pdf_sha256)
        self.trace('VENTE_ENCAISSEE',vente_id=v.id,encaissement_id=enc.id,session_id=session.id)
        self.s.flush();return self.recu(enc)

    def recu(self,enc):return serial(enc)
