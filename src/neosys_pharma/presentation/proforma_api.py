"""API proforma : mêmes affectations P1, mutations atomiques et CSRF ; aucun stock à l'émission."""
from uuid import UUID
from typing import Literal
from fastapi import APIRouter,Depends,Request,Query,HTTPException,Response
from pydantic import Field
from sqlalchemy import select
from neosys_pharma.presentation import vente_api as vente
from neosys_pharma.application.proforma_service import ProformaService,version_serial
from neosys_pharma.infrastructure.proforma_models import ProformaModel,VersionProformaModel,EvenementProformaModel
from neosys_pharma.infrastructure.organisation_models import EmplacementModel
from neosys_pharma.presentation.stock_api import execute
from neosys_pharma.application.stock_service import serial

vente.POLICY.update({'proformas_liste':'proforma.consulter','proforma_creer':'proforma.gerer','proforma_detail':'proforma.consulter','proforma_historique':'proforma.consulter','proforma_ligne':'proforma.gerer','proforma_retirer':'proforma.gerer','proforma_destinataire':'proforma.gerer','proforma_emettre':'proforma.emettre','proforma_version':'proforma.gerer','proforma_reprendre':'proforma.reprendre','proforma_pdf_route':'proforma.consulter','proforma_parametrage':'proforma.consulter','proforma_configurer':'proforma.parametrer','proforma_remise':'vente.remise.demander','proforma_decision':'vente.remise.autoriser','proforma_locale':'vente.remise.demander','proforma_conditionnements':('proforma.consulter','proforma.gerer'),'proforma_contextes':('proforma.consulter','proforma.gerer')})
router=APIRouter(prefix='/api/proformas/organisations/{organisation_id}',tags=['Proformas'],dependencies=[Depends(vente.contexte)])

def service(base=Depends(vente.service)):return ProformaService(base.stock,base.site)
class Creation(vente.Mutation):
    emplacement_id:UUID
    destinataire:vente.Destinataire
    mode:Literal['SANS_TIERS','PRISE_EN_CHARGE','CNAMGS','MUTUELLE','CNAMGS_MUTUELLE','CREDIT']='SANS_TIERS'
    vente_id:UUID|None=None
    revision_vente:int|None=Field(default=None,strict=True,ge=1)
class Destinataire(vente.Revision):destinataire:vente.Destinataire
class Reprise(vente.Revision):poste_id:UUID
class Parametrage(vente.Mutation):
    revision:int=Field(default=0,strict=True,ge=0)
    duree_jours:int=Field(strict=True,ge=1,le=3650)

def version(s,key,permission):return execute(lambda:s.obtenir(key,permission))
def mutate(s,d,kind,fn):return vente.mutation(s,d,'PROFORMA:'+kind,fn)

@router.get('/contextes')
def proforma_contextes(request:Request,s=Depends(service)):return vente.vente_contexte(request,s)
@router.get('/conditionnements')
def proforma_conditionnements(q:str=Query('',max_length=200),page:int=Query(1,ge=1),page_size:int=Query(20,ge=1,le=100),s=Depends(service)):return vente.vente_conditionnements(q,page,page_size,s)
@router.get('/parametrage')
def proforma_parametrage(s=Depends(service)):return s.parametrage()
@router.post('/parametrage')
def proforma_configurer(data:Parametrage,s=Depends(service)):return mutate(s,data,'PARAMETRAGE',lambda:s.configurer(data.model_dump()))
@router.get('')
def proformas_liste(q:str=Query('',max_length=200),page:int=Query(1,ge=1),page_size:int=Query(20,ge=1,le=100),s=Depends(service)):
    allowed=[]
    for loc in s.s.scalars(select(EmplacementModel).where(EmplacementModel.site_id==s.site)):
        try:s.stock.emplacement(loc.id_emplacement,'proforma.consulter');allowed.append(loc.id_emplacement)
        except PermissionError:pass
    query=select(ProformaModel).where(ProformaModel.organisation_id==s.org,ProformaModel.site_id==s.site,ProformaModel.emplacement_id.in_(allowed))
    term=s.stock.repo.terme(q)
    if term:
        # Recipient from JSON uses portable SQLAlchemy extraction; escape user wildcards.
        recipient=select(VersionProformaModel.proforma_id).where(VersionProformaModel.organisation_id==s.org,s.stock.repo.upper(VersionProformaModel.destinataire['nom'].as_string()).contains(term,autoescape=True))
        query=query.where(s.stock.repo.upper(ProformaModel.reference).contains(term,autoescape=True)|ProformaModel.id.in_(recipient))
    total,rows=s.stock.repo.paginer(query.order_by(ProformaModel.cree_le.desc(),ProformaModel.id),page,page_size)
    items=[]
    for p in rows:
        latest=s.s.scalar(select(VersionProformaModel).where(VersionProformaModel.proforma_id==p.id).order_by(VersionProformaModel.numero.desc()))
        items.append({**serial(p),'version':version_serial(latest)})
    return {'items':items,'total':total,'page':page,'page_size':page_size}
@router.post('',status_code=201)
def proforma_creer(data:Creation,s=Depends(service)):
    execute(lambda:s.stock.emplacement(data.emplacement_id,'proforma.gerer'))
    if data.vente_id and data.revision_vente is None:raise HTTPException(422,'Révision de préparation obligatoire.')
    if data.vente_id:execute(lambda:vente.VenteService(s.stock,s.site).obtenir(data.vente_id,'vente.consulter'))
    return mutate(s,data,'CREER',lambda:s.creer(data.model_dump()))
@router.get('/{proforma_id}')
def proforma_detail(proforma_id:UUID,s=Depends(service)):
    p=execute(lambda:s.proforma(proforma_id,'proforma.consulter'))
    versions=s.s.scalars(select(VersionProformaModel).where(VersionProformaModel.proforma_id==p.id).order_by(VersionProformaModel.numero.desc()))
    return {**serial(p),'versions':[version_serial(v) for v in versions]}
@router.get('/{proforma_id}/historique')
def proforma_historique(proforma_id:UUID,page:int=Query(1,ge=1),page_size:int=Query(25,ge=1,le=100),s=Depends(service)):
    p=execute(lambda:s.proforma(proforma_id,'proforma.consulter'));query=select(EvenementProformaModel).where(EvenementProformaModel.proforma_id==p.id,EvenementProformaModel.organisation_id==s.org).order_by(EvenementProformaModel.date,EvenementProformaModel.id)
    total,rows=s.stock.repo.paginer(query,page,page_size);return {'items':[serial(x) for x in rows],'total':total,'page':page,'page_size':page_size}
@router.get('/versions/{version_id}')
def proforma_detail(version_id:UUID,s=Depends(service)):return execute(lambda:s.detail(version(s,version_id,'proforma.consulter')))
@router.get('/versions/{version_id}/pdf')
def proforma_pdf_route(version_id:UUID,s=Depends(service)):
    v=version(s,version_id,'proforma.consulter')
    if v.etat!='EMISE':raise HTTPException(409,'Émettre la version avant téléchargement.')
    p=s.stock.obtenir(ProformaModel,v.proforma_id)
    return Response(v.pdf,media_type='application/pdf',headers={'Content-Disposition':f'inline; filename="proforma-{p.id}-v{v.numero}.pdf"','X-Document-SHA256':v.pdf_sha256})
@router.post('/versions/{version_id}/lignes',status_code=201)
def proforma_ligne(version_id:UUID,data:vente.Ligne,s=Depends(service)):
    version(s,version_id,'proforma.gerer');return mutate(s,data,'LIGNE:'+str(version_id),lambda:s.ajouter_ligne(version(s,version_id,'proforma.gerer'),data.model_dump()))
@router.post('/versions/{version_id}/lignes/{ligne_id}/retirer')
def proforma_retirer(version_id:UUID,ligne_id:UUID,data:vente.Revision,s=Depends(service)):
    version(s,version_id,'proforma.gerer');return mutate(s,data,'RETIRER:'+str(ligne_id),lambda:s.supprimer_ligne(version(s,version_id,'proforma.gerer'),ligne_id,data.revision))
@router.post('/versions/{version_id}/destinataire')
def proforma_destinataire(version_id:UUID,data:Destinataire,s=Depends(service)):
    version(s,version_id,'proforma.gerer');return mutate(s,data,'DESTINATAIRE:'+str(version_id),lambda:s.destinataire(version(s,version_id,'proforma.gerer'),data.model_dump()))
@router.post('/versions/{version_id}/emettre')
def proforma_emettre(version_id:UUID,data:vente.Revision,s=Depends(service)):
    version(s,version_id,'proforma.emettre');return mutate(s,data,'EMETTRE:'+str(version_id),lambda:s.emettre(version(s,version_id,'proforma.emettre'),data.model_dump()))
@router.post('/versions/{version_id}/nouvelle-version',status_code=201)
def proforma_version(version_id:UUID,data:vente.Revision,s=Depends(service)):
    version(s,version_id,'proforma.gerer');return mutate(s,data,'VERSION:'+str(version_id),lambda:s.nouvelle_version(version(s,version_id,'proforma.gerer'),data.model_dump()))
@router.post('/versions/{version_id}/reprendre',status_code=201)
def proforma_reprendre(version_id:UUID,data:Reprise,s=Depends(service)):
    v=version(s,version_id,'proforma.reprendre');execute(lambda:s.stock.emplacement(v.emplacement_id,'vente.preparer'));execute(lambda:s.stock.emplacement(v.emplacement_id,'stock.reserver'))
    return mutate(s,data,'REPRENDRE:'+str(version_id),lambda:s.reprendre(version(s,version_id,'proforma.reprendre'),data.model_dump()))
@router.post('/versions/{version_id}/remises',status_code=201)
def proforma_remise(version_id:UUID,data:vente.Remise,s=Depends(service)):
    version(s,version_id,'proforma.gerer');execute(lambda:s.stock.emplacement(s.obtenir(version_id,'proforma.gerer').emplacement_id,'vente.remise.demander'))
    return mutate(s,data,'REMISE:'+str(version_id),lambda:s.demander_remise(version(s,version_id,'proforma.gerer'),data.model_dump()))
@router.post('/versions/{version_id}/remises/{demande_id}/decision')
def proforma_decision(version_id:UUID,demande_id:UUID,data:vente.Decision,s=Depends(service)):
    version(s,version_id,'proforma.consulter');return mutate(s,data,'DECISION:'+str(demande_id),lambda:s.decider_remise(version(s,version_id,'vente.remise.autoriser'),demande_id,data.model_dump()))
@router.post('/versions/{version_id}/remises/{demande_id}/locale')
def proforma_locale(version_id:UUID,demande_id:UUID,data:vente.Locale,request:Request,s=Depends(service)):
    version(s,version_id,'proforma.gerer');return vente.remise_locale(version_id,demande_id,data,request,s)
