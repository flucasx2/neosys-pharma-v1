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

POLICY={'ventes_liste':'vente.consulter','vente_detail':'vente.consulter','vente_creer':'vente.preparer','ligne_enregistrer':'vente.preparer','ligne_retirer':'vente.preparer','vente_attendre':'vente.preparer','vente_reprendre':'vente.preparer','vente_valider':'vente.valider','vente_transmettre':'vente.transmettre','vente_annuler':'vente.annuler','remise_demander':'vente.remise.demander','remise_decider':'vente.remise.autoriser','vente_historique':'vente.consulter'}

def contexte(request:Request,organisation_id:UUID,user=Depends(utilisateur_courant),session:Session=Depends(get_db_session)):
    try:
        site=UUID(request.headers.get('X-Site-ID',''))
        permission=POLICY.get(request.scope['route'].name)
        if not permission:raise PermissionError('Opération Vente non autorisée.')
        control=ControleAcces(SqlAlchemySecuriteRepository(session),user,jour_courant());control.organisation(permission,organisation_id,site)
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
@router.get('/{vente_id}')
def vente_detail(vente_id:UUID,request:Request,s=Depends(service)):return execute(lambda:s.detail(vente(s,request,vente_id)))
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
def vente_valider(vente_id:UUID,data:Action,request:Request,s=Depends(service)):return action(s,request,vente_id,data,'VALIDEE_PREPARATION')
@router.post('/{vente_id}/transmettre')
def vente_transmettre(vente_id:UUID,data:Action,request:Request,s=Depends(service)):return action(s,request,vente_id,data,'TRANSMISE')
@router.post('/{vente_id}/annuler')
def vente_annuler(vente_id:UUID,data:Action,request:Request,s=Depends(service)):return action(s,request,vente_id,data,'ANNULEE')
@router.post('/{vente_id}/remises',status_code=201)
def remise_demander(vente_id:UUID,data:Remise,request:Request,s=Depends(service)):
    vente(s,request,vente_id);return mutation(s,data,'REMISE:'+str(vente_id),lambda:s.demander_remise(s.obtenir(vente_id,'vente.remise.demander'),data.model_dump()))
@router.post('/{vente_id}/remises/{demande_id}/decision')
def remise_decider(vente_id:UUID,demande_id:UUID,data:Decision,request:Request,s=Depends(service)):
    vente(s,request,vente_id);return mutation(s,data,'DECISION:'+str(demande_id),lambda:s.decider_remise(s.obtenir(vente_id,'vente.remise.autoriser'),demande_id,data.model_dump()))
