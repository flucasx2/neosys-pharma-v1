"""Plafonds explicites et décisions de remise dans la transaction Vente/P3."""
from datetime import datetime,timezone
from decimal import Decimal
from sqlalchemy import select
from neosys_pharma.domain.remises import calculer,montant_remise
from neosys_pharma.domain.stock import ConflitStock
from neosys_pharma.infrastructure.vente_models import PlafondRemiseModel,DemandeRemiseModel,VenteModel
from neosys_pharma.infrastructure.securite_repository import SqlAlchemySecuriteRepository
from neosys_pharma.application.securite_service import SecuriteService
from neosys_pharma.application.controle_acces import ControleAcces
from neosys_pharma.infrastructure.securite_models import RoleModel,UtilisateurModel
from neosys_pharma.application.stock_service import serial

class RemisesService:
    def finance(self,v,exclude=None):
        return calculer([x for x in self.lignes(v) if x.actif],[x for x in self.stock.lignes(DemandeRemiseModel,vente_id=v.id) if x.id!=exclude])

    def eligible(self,v,r):
        requests=[x for x in self.stock.lignes(DemandeRemiseModel,vente_id=v.id) if x.ligne_id!=r.ligne_id and (r.ligne_id is None or x.ligne_id is not None)]
        finance=calculer([x for x in self.lignes(v) if x.actif],requests)
        if r.ligne_id:return Decimal(finance['lignes'][str(r.ligne_id)]['ttc_initial'])
        return sum((Decimal(x['ttc_initial'])-Decimal(x['remise_ligne']) for x in finance['lignes'].values()),Decimal(0))

    def plafond_applicable(self,v,approver,r,amount,eligible):
        repo=SqlAlchemySecuriteRepository(self.s);user=repo.utilisateur(approver)
        if not user or user.organisation_id!=self.org:raise PermissionError('Responsable hors organisation.')
        ControleAcces(repo,user,self.stock.jour).verifier('vente.remise.autoriser',v.site_id,v.emplacement_id)
        rights=SecuriteService(repo).droits(approver,v.site_id,self.stock.jour)
        candidates=[]
        checked_amount=amount;checked_base=eligible
        if r.ligne_id is None:
            before=self.finance(v)
            individual=Decimal(before['totaux']['remise_ligne'])
            checked_amount+=individual;checked_base=Decimal(before['totaux']['ttc_initial'])
        for right in rights:
            if not right.autorise('vente.remise.autoriser',v.emplacement_id):continue
            for role in repo.roles_affectation(right.affectation_site_id):
                if not role.actif or not any(p.code=='vente.remise.autoriser' for p in repo.permissions_role(role.id_role)):continue
                cap=self.s.scalar(select(PlafondRemiseModel).where(PlafondRemiseModel.organisation_id==self.org,PlafondRemiseModel.role_id==role.id_role,PlafondRemiseModel.actif.is_(True)))
                if not cap:continue
                if r.type=='POURCENTAGE' and cap.max_pourcentage is None:continue
                if r.type=='MONTANT_XAF' and cap.max_montant_xaf is None:continue
                if cap.max_pourcentage is not None and (Decimal(r.valeur)>cap.max_pourcentage if r.type=='POURCENTAGE' else amount*100>eligible*cap.max_pourcentage):continue
                if cap.max_pourcentage is not None and checked_amount*100>checked_base*cap.max_pourcentage:continue
                if cap.max_montant_xaf is not None and checked_amount>cap.max_montant_xaf:continue
                candidates.append(cap)
        if not candidates:raise ValueError('Aucun plafond applicable configuré ou remise supérieure aux plafonds du responsable.')
        return sorted(candidates,key=lambda x:str(x.id))[0]

    def configurer_plafond(self,data):
        role=self.s.get(RoleModel,data['role_id'])
        if not role or not role.actif or role.organisation_id not in (None,self.org):raise PermissionError('Rôle incompatible avec l’organisation.')
        repo=SqlAlchemySecuriteRepository(self.s)
        if not any(p.code=='vente.remise.autoriser' for p in repo.permissions_role(role.id_role)):raise ValueError('Le rôle doit déjà posséder vente.remise.autoriser ; aucun droit implicite ajouté.')
        cap=self.s.scalar(select(PlafondRemiseModel).where(PlafondRemiseModel.organisation_id==self.org,PlafondRemiseModel.role_id==role.id_role))
        if data.get('revision',0)!=(cap.revision if cap else 0):raise ConflitStock('Plafond modifié : actualiser.')
        if not cap:cap=self.stock.ajouter(PlafondRemiseModel,role_id=role.id_role,max_pourcentage=data.get('max_pourcentage'),max_montant_xaf=data.get('max_montant_xaf'))
        else:cap.revision+=1
        cap.max_pourcentage=data.get('max_pourcentage');cap.max_montant_xaf=data.get('max_montant_xaf');cap.actif=data['actif']
        # Invalidate authorizations and pending financial bases, retaining complete audit.
        for v in self.s.scalars(select(VenteModel).where(VenteModel.organisation_id==self.org,VenteModel.etat.in_(['PREPARATION','EN_ATTENTE','VALIDEE_PREPARATION','TRANSMISE']))):
            if not any(r.statut in ('DEMANDEE','AUTORISEE') for r in self.stock.lignes(DemandeRemiseModel,vente_id=v.id)):continue
            previous=v.etat;self.invalider_remises(v);v.revision+=1
            if v.etat in ('VALIDEE_PREPARATION','TRANSMISE'):v.etat='PREPARATION';v.caisse_id=None
            self.evenement(v,'PLAFOND_MODIFIE',plafond=serial(cap),avant=previous,apres=v.etat)
        return serial(cap)

    def decider_remise(self,v,key,data,approver=None,local=False):
        self.editable(v);self.revision(v,data['revision']);r=self.stock.obtenir(DemandeRemiseModel,key)
        if r.vente_id!=v.id:raise PermissionError('Demande d’une autre préparation.')
        if r.statut!='DEMANDEE' or r.revision_vente!=v.revision:raise ConflitStock('Demande obsolète ou déjà décidée.')
        approver=approver or self.stock.user
        before=self.finance(v);eligible=self.eligible(v,r);amount=montant_remise(r.type,r.valeur,eligible)
        cap=self.plafond_applicable(v,approver,r,amount,eligible) if data['autoriser'] else None
        # A refusal still requires the approver's contextual P1 permission.
        repo=SqlAlchemySecuriteRepository(self.s);user=repo.utilisateur(approver)
        if not user or user.organisation_id!=self.org:raise PermissionError('Responsable hors organisation.')
        ControleAcces(repo,user,self.stock.jour).verifier('vente.remise.autoriser',v.site_id,v.emplacement_id)
        for other in self.stock.lignes(DemandeRemiseModel,vente_id=v.id):
            if other.id==r.id:continue
            if data['autoriser'] and (other.statut=='DEMANDEE' or (other.statut=='AUTORISEE' and (other.ligne_id==r.ligne_id or (r.ligne_id is not None and other.ligne_id is None)))):
                other.statut='INVALIDEE';self.evenement(v,'REMISE_INVALIDEE',demande_id=other.id)
        r.statut='AUTORISEE' if data['autoriser'] else 'REFUSEE'
        v.revision+=1
        if not data['autoriser']:
            # A refusal changes workflow revision, not the financial base of the other requests.
            for pending in self.stock.lignes(DemandeRemiseModel,vente_id=v.id):
                if pending.statut=='DEMANDEE':pending.revision_vente=v.revision
        r.autorisation={'auteur_id':str(approver),'approbateur_nom':user.nom,'demandeur_id':str(r.auteur_id),'date':datetime.now(timezone.utc).isoformat(),'motif':data['justification'],'local':local,'plafond':serial(cap) if cap else None,'eligible_ttc':str(eligible),'remise_xaf':str(amount),'avant':before,'apres':self.finance(v),'revision':v.revision}
        finance=self.finance(v)
        for line in self.lignes(v):
            if line.actif:line.remise_appliquee={'montants':finance['lignes'][str(line.id)],'demandes':[str(x.id) for x in self.stock.lignes(DemandeRemiseModel,vente_id=v.id) if x.statut=='AUTORISEE' and x.ligne_id in (None,line.id)]}
        self.evenement(v,'REMISE_'+r.statut,demande_id=r.id,autorisation=r.autorisation)
        self.s.flush();return serial(r)
