"""P4 incrément 1 : API protégée, refus par défaut et CSRF P1 inchangé."""
from decimal import Decimal
from uuid import UUID
from typing import Literal
from fastapi import APIRouter,Depends,Request,HTTPException,Query
from pydantic import BaseModel,ConfigDict,Field
from sqlalchemy import select
from sqlalchemy.orm import Session
from neosys_pharma.presentation.authentification_api import utilisateur_courant,jour_courant
from neosys_pharma.infrastructure.database import get_db_session
from neosys_pharma.infrastructure.securite_repository import SqlAlchemySecuriteRepository
from neosys_pharma.application.controle_acces import ControleAcces
from neosys_pharma.application.stock_service import StockService
from neosys_pharma.application.vente_service import VenteService
from neosys_pharma.infrastructure.vente_models import VenteModel,EvenementVenteModel
from neosys_pharma.presentation.stock_api import execute
from neosys_pharma.application.stock_service import serial

POLICY={'ventes_liste':'vente.consulter','vente_detail':'vente.consulter','vente_creer':'vente.preparer','ligne_enregistrer':'vente.preparer','ligne_retirer':'vente.preparer','vente_attendre':'vente.preparer','vente_reprendre':'vente.preparer','vente_valider':'vente.valider','vente_transmettre':'vente.transmettre','vente_annuler':'vente.annuler','remise_demander':'vente.remise.demander','remise_decider':'vente.remise.autoriser','vente_historique':'vente.consulter','vente_client_affecter':'vente.preparer'}

def contexte(request:Request,organisation_id:UUID,user=Depends(utilisateur_courant),session:Session=Depends(get_db_session)):
    try:
        site=UUID(request.headers.get('X-Site-ID',''))
        permission=POLICY.get(request.scope['route'].name)
        if not permission:raise PermissionError('Opération Vente non autorisée.')
        control=ControleAcces(SqlAlchemySecuriteRepository(session),user,jour_courant())
        permissions=permission if isinstance(permission,tuple) else (permission,)
        for candidate in permissions:
            try:control.organisation(candidate,organisation_id,site);permission=candidate;break
            except PermissionError:pass
        else:raise PermissionError('Permission Vente requise.')
        loc=request.headers.get('X-Emplacement-ID')
        if loc:control.verifier(permission,site,UUID(loc))
        request.state.vente_site=site;request.state.vente_controle=control;request.state.vente_permission=permission
    except (ValueError,PermissionError) as e:raise HTTPException(403,str(e) or 'Contexte Vente requis.') from e

router=APIRouter(prefix='/api/ventes/organisations/{organisation_id}',tags=['Ventes - préparation'],dependencies=[Depends(contexte)])

def service(request:Request,organisation_id:UUID,user=Depends(utilisateur_courant),session:Session=Depends(get_db_session)):
    def access(permission,site,loc=None):
        if site!=request.state.vente_site:raise PermissionError('Site différent du contexte courant.')
        current=request.headers.get('X-Emplacement-ID')
        if loc and current and str(loc)!=current:raise PermissionError('Emplacement différent du contexte courant.')
        request.state.vente_controle.verifier(permission,site,loc)
    return VenteService(StockService(session,organisation_id,user.id_utilisateur,access,jour_courant()),request.state.vente_site)

class Input(BaseModel):model_config=ConfigDict(extra='forbid',str_strip_whitespace=True)
class Mutation(Input):cle:UUID
class Revision(Mutation):revision:int=Field(strict=True,ge=1)
class Destinataire(Input):
    nom:str=Field(min_length=1,max_length=200)
    telephone:str|None=Field(default=None,max_length=80)
    adresse:str|None=Field(default=None,max_length=1000)
class Creation(Mutation):
    emplacement_id:UUID
    poste_id:UUID
    mode:Literal['SANS_TIERS','CNAMGS','MUTUELLE','CNAMGS_MUTUELLE','CREDIT']='SANS_TIERS'
    client_id:UUID|None=None
    destinataire:Destinataire|None=None
class Ligne(Revision):
    ligne_id:UUID|None=None
    produit_id:UUID
    conditionnement_id:UUID
    quantite:int=Field(strict=True,gt=0,le=1_000_000_000)
    lot_id:UUID|None=None
    justification:str|None=Field(default=None,min_length=1,max_length=2000)
class Action(Revision):
    caisse_id:UUID|None=None
    justification:str|None=Field(default=None,min_length=1,max_length=2000)
class ClientAffectation(Revision):
    client_id:UUID|None=None
class Remise(Revision):
    ligne_id:UUID|None=None
    type:Literal['POURCENTAGE','MONTANT_XAF']
    valeur:Decimal=Field(gt=0,max_digits=18,decimal_places=2)
    justification:str=Field(min_length=1,max_length=2000)
class Decision(Revision):
    autoriser:bool
    justification:str=Field(min_length=1,max_length=2000)

def vente(s,request,key):return execute(lambda:s.obtenir(key,request.state.vente_permission))
def mutation(s,data,type,action):return execute(lambda:s.stock.operation(data.cle,'P4:'+type,data.model_dump(exclude={'cle'}),action))

@router.post('',status_code=201)
def vente_creer(data:Creation,s=Depends(service)):
    execute(lambda:s.stock.emplacement(data.emplacement_id,'vente.preparer'))
    if data.mode=='CREDIT':execute(lambda:s.stock.access('vente.credit',s.site,data.emplacement_id))
    return mutation(s,data,'CREER',lambda:s.creer({**data.model_dump(),'destinataire':data.destinataire.model_dump() if data.destinataire else {}}))
@router.get('')
def ventes_liste(request:Request,page:int=Query(1,ge=1),page_size:int=Query(25,ge=1,le=100),s=Depends(service)):
    from neosys_pharma.infrastructure.organisation_models import EmplacementModel
    allowed=[]
    for loc in s.s.scalars(select(EmplacementModel).where(EmplacementModel.site_id==s.site)):
        try:s.stock.emplacement(loc.id_emplacement,'vente.consulter');allowed.append(loc.id_emplacement)
        except PermissionError:pass
    query=select(VenteModel).where(VenteModel.organisation_id==s.org,VenteModel.site_id==s.site,VenteModel.emplacement_id.in_(allowed)).order_by(VenteModel.cree_le.desc(),VenteModel.id)
    total,rows=s.stock.repo.paginer(query,page,page_size)
    return {'items':[serial(v) for v in rows],'total':total,'page':page,'page_size':page_size}
class Plafond(Mutation):
    role_id:UUID
    revision:int=Field(default=0,strict=True,ge=0)
    max_pourcentage:Decimal|None=Field(default=None,gt=0,le=100,max_digits=5,decimal_places=2)
    max_montant_xaf:Decimal|None=Field(default=None,gt=0,max_digits=18,decimal_places=2)
    actif:bool=True
class Locale(Decision):
    identifiant:str=Field(min_length=1,max_length=80)
    password:str=Field(min_length=1,max_length=128,repr=False)

POLICY.update({'vente_contexte':('vente.consulter','vente.preparer','vente.remise.autoriser','vente.remise.parametrer'),'vente_conditionnements':('vente.consulter','vente.preparer'),'vente_stock':'stock.consulter','plafonds_liste':'vente.remise.parametrer','plafond_enregistrer':'vente.remise.parametrer','remises_attente':'vente.remise.autoriser','remise_locale':'vente.remise.demander'})

@router.get('/contextes')
def vente_contexte(request:Request,s=Depends(service)):
    from neosys_pharma.infrastructure.organisation_models import EmplacementModel,PosteVenteModel,CaisseModel
    result=[]
    for loc in s.s.scalars(select(EmplacementModel).where(EmplacementModel.site_id==s.site,EmplacementModel.actif.is_(True))):
        try:s.stock.emplacement(loc.id_emplacement,request.state.vente_permission)
        except PermissionError:continue
        result.append({'id':str(loc.id_emplacement),'nom':loc.nom,'postes':[{'id':str(p.id_poste_vente),'nom':p.nom} for p in s.s.scalars(select(PosteVenteModel).where(PosteVenteModel.emplacement_id==loc.id_emplacement,PosteVenteModel.actif.is_(True)))],'caisses':[{'id':str(p.id_caisse),'nom':p.nom} for p in s.s.scalars(select(CaisseModel).where(CaisseModel.emplacement_id==loc.id_emplacement,CaisseModel.actif.is_(True)))]})
    return {'emplacements':result}

@router.get('/conditionnements')
def vente_conditionnements(q:str=Query('',max_length=200),page:int=Query(1,ge=1),page_size:int=Query(20,ge=1,le=100),s=Depends(service)):
    from neosys_pharma.presentation.stock_api import conditionnements
    return conditionnements(q=q,page=page,page_size=page_size,s=s.stock)

@router.get('/stocks')
def vente_stock(emplacement_id:UUID,conditionnement_id:UUID,page:int=Query(1,ge=1),page_size:int=Query(20,ge=1,le=100),s=Depends(service)):
    from neosys_pharma.infrastructure.stock_models import StockEmplacementModel,LotModel
    execute(lambda:s.stock.emplacement(emplacement_id,'stock.consulter'));execute(lambda:s.stock.conditionnement(conditionnement_id))
    q=select(StockEmplacementModel).join(LotModel,LotModel.id==StockEmplacementModel.lot_id).where(StockEmplacementModel.organisation_id==s.org,StockEmplacementModel.emplacement_id==emplacement_id,LotModel.conditionnement_id==conditionnement_id)
    total,rows=s.stock.repo.paginer(q.order_by(StockEmplacementModel.id),page,page_size)
    from sqlalchemy import func
    physique,reserve=s.s.execute(select(func.coalesce(func.sum(StockEmplacementModel.physique),0),func.coalesce(func.sum(StockEmplacementModel.reserve),0)).join(LotModel,LotModel.id==StockEmplacementModel.lot_id).where(StockEmplacementModel.organisation_id==s.org,StockEmplacementModel.emplacement_id==emplacement_id,LotModel.conditionnement_id==conditionnement_id)).one()
    return {'items':[{**serial(b),'vendable':b.physique-b.reserve,'lot':s.stock.obtenir(LotModel,b.lot_id).numero,'peremption':s.stock.obtenir(LotModel,b.lot_id).peremption} for b in rows],'total':total,'page':page,'page_size':page_size,'totaux':{'physique':physique,'reserve':reserve,'vendable':physique-reserve}}

@router.get('/plafonds')
def plafonds_liste(s=Depends(service)):
    from neosys_pharma.infrastructure.vente_models import PlafondRemiseModel
    from neosys_pharma.infrastructure.securite_models import RoleModel
    from neosys_pharma.infrastructure.securite_repository import SqlAlchemySecuriteRepository
    repo=SqlAlchemySecuriteRepository(s.s)
    roles=[{'id':str(r.id_role),'nom':r.nom} for r in s.s.scalars(select(RoleModel).where(RoleModel.actif.is_(True),(RoleModel.organisation_id==s.org)|(RoleModel.organisation_id.is_(None)))) if any(p.code=='vente.remise.autoriser' for p in repo.permissions_role(r.id_role))]
    return {'items':[serial(r) for r in s.stock.lignes(PlafondRemiseModel)],'roles':roles}

@router.post('/plafonds',status_code=201)
def plafond_enregistrer(data:Plafond,s=Depends(service)):
    if data.max_pourcentage is None and data.max_montant_xaf is None:raise HTTPException(422,'Au moins un plafond explicite est obligatoire.')
    return mutation(s,data,'PLAFOND',lambda:s.configurer_plafond(data.model_dump()))

@router.get('/remises-attente')
def remises_attente(page:int=Query(1,ge=1),page_size:int=Query(25,ge=1,le=100),s=Depends(service)):
    from neosys_pharma.infrastructure.vente_models import DemandeRemiseModel
    from neosys_pharma.infrastructure.organisation_models import EmplacementModel
    allowed=[]
    for loc in s.s.scalars(select(EmplacementModel).where(EmplacementModel.site_id==s.site)):
        try:s.stock.emplacement(loc.id_emplacement,'vente.remise.autoriser');allowed.append(loc.id_emplacement)
        except PermissionError:pass
    query=select(DemandeRemiseModel).join(VenteModel,VenteModel.id==DemandeRemiseModel.vente_id).where(DemandeRemiseModel.organisation_id==s.org,DemandeRemiseModel.statut=='DEMANDEE',VenteModel.site_id==s.site,VenteModel.emplacement_id.in_(allowed)).order_by(DemandeRemiseModel.id)
    total,rows=s.stock.repo.paginer(query,page,page_size)
    return {'items':[{'demande':serial(r),'vente':s.detail(s.obtenir(r.vente_id,'vente.remise.autoriser'))} for r in rows],'total':total,'page':page,'page_size':page_size}

@router.post('/{vente_id}/remises/{demande_id}/locale')
def remise_locale(vente_id:UUID,demande_id:UUID,data:Locale,request:Request,s=Depends(service)):
    from neosys_pharma.infrastructure.authentification_repository import SqlAlchemyAuthRepository
    from neosys_pharma.application.authentification_service import empreinte
    from neosys_pharma.infrastructure.passwords import passwords
    from neosys_pharma.presentation.authentification_api import maintenant
    v=vente(s,request,vente_id);repo=SqlAlchemyAuthRepository(s.s)
    for key,maximum in [('ip:'+str(request.client.host),60),('compte:'+str(s.org)+':'+data.identifiant.strip().lower(),10)]:
        if not repo.tentative(empreinte(key),maintenant(),maximum=maximum):raise HTTPException(429,'Trop de tentatives. Réessayez dans cinq minutes.')
    approver=repo.utilisateur_login(s.org,data.identifiant.strip().lower())
    encoded=repo.password_hash(approver.id_utilisateur) if approver else None
    valid=passwords.verifier(encoded,data.password)
    if not approver or not valid or not approver.actif or not repo.organisation_active(s.org):raise HTTPException(401,'Authentification du responsable refusée.')
    execute(lambda:ControleAcces(repo.securite,approver,jour_courant()).verifier('vente.remise.autoriser',v.site_id,v.emplacement_id))
    body=data.model_dump(exclude={'cle','password','identifiant'});body['approbateur_id']=str(approver.id_utilisateur)
    return execute(lambda:s.stock.operation(data.cle,'P4:LOCALE:'+str(demande_id),body,lambda:s.decider_remise(s.obtenir(vente_id,'vente.remise.demander'),demande_id,data.model_dump(exclude={'password','identifiant'}),approver.id_utilisateur,local=True)))

@router.get('/{vente_id}')
def vente_detail(vente_id:UUID,request:Request,s=Depends(service)):return execute(lambda:s.detail(vente(s,request,vente_id)))
@router.put('/{vente_id}/client')
def vente_client_affecter(vente_id:UUID,data:ClientAffectation,request:Request,s=Depends(service)):
    # Selecting a profile requires both the preparation permission and client consultation.
    try:request.state.vente_controle.organisation('client.consulter',s.org,s.site)
    except PermissionError as e:raise HTTPException(403,'Permission client.consulter requise.') from e
    v=vente(s,request,vente_id)
    return mutation(s,data,'CLIENT:'+str(vente_id),lambda:s.affecter_client(v,data.client_id,data.revision))
@router.get('/{vente_id}/historique')
def vente_historique(vente_id:UUID,request:Request,page:int=Query(1,ge=1),page_size:int=Query(25,ge=1,le=100),s=Depends(service)):
    v=vente(s,request,vente_id)
    q=select(EvenementVenteModel).where(EvenementVenteModel.vente_id==v.id,EvenementVenteModel.organisation_id==s.org).order_by(EvenementVenteModel.date,EvenementVenteModel.id)
    total,rows=s.stock.repo.paginer(q,page,page_size);return {'items':[serial(r) for r in rows],'total':total,'page':page,'page_size':page_size}
@router.post('/{vente_id}/lignes',status_code=201)
def ligne_enregistrer(vente_id:UUID,data:Ligne,request:Request,s=Depends(service)):
    v=vente(s,request,vente_id)
    execute(lambda:s.stock.emplacement(v.emplacement_id,'stock.reserver'))
    return mutation(s,data,'LIGNE:'+str(vente_id),lambda:s.ajouter_ligne(s.obtenir(vente_id,'vente.preparer'),data.model_dump()))
@router.post('/{vente_id}/lignes/{ligne_id}/retirer')
def ligne_retirer(vente_id:UUID,ligne_id:UUID,data:Revision,request:Request,s=Depends(service)):
    vente(s,request,vente_id);return mutation(s,data,'RETIRER:'+str(vente_id)+':'+str(ligne_id),lambda:s.supprimer_ligne(s.obtenir(vente_id,'vente.preparer'),ligne_id,data.revision))

def action(s,request,key,data,target):
    vente(s,request,key)
    return mutation(s,data,target+':'+str(key),lambda:s.changer_etat(s.obtenir(key,request.state.vente_permission),target,data.model_dump()))
@router.post('/{vente_id}/attendre')
def vente_attendre(vente_id:UUID,data:Action,request:Request,s=Depends(service)):return action(s,request,vente_id,data,'EN_ATTENTE')
@router.post('/{vente_id}/reprendre')
def vente_reprendre(vente_id:UUID,data:Action,request:Request,s=Depends(service)):return action(s,request,vente_id,data,'PREPARATION')
@router.post('/{vente_id}/valider')
def vente_valider(vente_id:UUID,data:Action,request:Request,s=Depends(service)):
    current=vente(s,request,vente_id)
    if current.mode not in ('SANS_TIERS','CREDIT'):
        try:request.state.vente_controle.verifier('tiers_payant.consulter',s.site,current.emplacement_id)
        except PermissionError as exc:raise HTTPException(403,'Permission tiers_payant.consulter requise pour valider cette préparation.') from exc
    return mutation(s,data,'VALIDEE:'+str(vente_id),lambda:s.changer_etat(s.obtenir(vente_id,'vente.valider'),'VALIDEE_PREPARATION',data.model_dump()))
@router.post('/{vente_id}/transmettre')
def vente_transmettre(vente_id:UUID,data:Action,request:Request,s=Depends(service)):
    current=vente(s,request,vente_id)
    if current.mode not in ('SANS_TIERS','CREDIT'):
        try:request.state.vente_controle.verifier('tiers_payant.consulter',s.site,current.emplacement_id)
        except PermissionError as exc:raise HTTPException(403,'Permission tiers_payant.consulter requise pour transmettre cette préparation.') from exc
    return action(s,request,vente_id,data,'TRANSMISE')
@router.post('/{vente_id}/annuler')
def vente_annuler(vente_id:UUID,data:Action,request:Request,s=Depends(service)):return action(s,request,vente_id,data,'ANNULEE')
@router.post('/{vente_id}/remises',status_code=201)
def remise_demander(vente_id:UUID,data:Remise,request:Request,s=Depends(service)):
    vente(s,request,vente_id);return mutation(s,data,'REMISE:'+str(vente_id),lambda:s.demander_remise(s.obtenir(vente_id,'vente.remise.demander'),data.model_dump()))
@router.post('/{vente_id}/remises/{demande_id}/decision')
def remise_decider(vente_id:UUID,demande_id:UUID,data:Decision,request:Request,s=Depends(service)):
    vente(s,request,vente_id);return mutation(s,data,'DECISION:'+str(demande_id),lambda:s.decider_remise(s.obtenir(vente_id,'vente.remise.autoriser'),demande_id,data.model_dump()))
