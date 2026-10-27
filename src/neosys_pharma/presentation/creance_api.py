"""Créances et versions administratives P5-C.1, sans émission de facture."""
from uuid import UUID
from typing import Literal
from fastapi import APIRouter, Depends, Query
from pydantic import Field
from sqlalchemy import select
from neosys_pharma.presentation import vente_api
from neosys_pharma.presentation.stock_api import execute
from neosys_pharma.application.stock_service import serial
from neosys_pharma.application.creance_service import CreanceService
from neosys_pharma.infrastructure.creance_models import CreanceOrganismeModel,VersionDossierCreanceModel
from neosys_pharma.infrastructure.prise_en_charge_models import RealisationPriseEnChargeModel
from neosys_pharma.infrastructure.vente_models import VenteModel
from neosys_pharma.infrastructure.organisation_models import EmplacementModel

vente_api.POLICY.update({
    'creances_sources':'tiers_payant.creance.consulter','creances_liste':'tiers_payant.creance.consulter',
    'creance_detail':'tiers_payant.creance.consulter','creance_historique':'tiers_payant.creance.consulter',
    'creances_constituer':'tiers_payant.creance.constituer','creance_completer':'tiers_payant.creance.completer',
    'creance_verifier':'tiers_payant.creance.verifier','creance_engagement':'tiers_payant.creance.verifier'})
router=APIRouter(prefix='/api/tiers-payants/organisations/{organisation_id}/creances',tags=['Créances organismes'],dependencies=[Depends(vente_api.contexte)])


def service(s=Depends(vente_api.service)):return CreanceService(s.stock,s.site)


def mutate(s,data,kind,action):
    return execute(lambda:s.stock.operation(data.cle,'P5C1:'+kind,data.model_dump(mode='json',exclude={'cle'}),action))


def perimetre(s):
    ids=[]
    for row in s.s.scalars(select(EmplacementModel).where(EmplacementModel.site_id==s.site)):
        try:s.stock.access('tiers_payant.creance.consulter',s.site,row.id_emplacement);ids.append(row.id_emplacement)
        except PermissionError:pass
    return ids


@router.get('/sources',name='creances_sources')
def sources(page:int=Query(1,ge=1),page_size:int=Query(25,ge=1,le=100),s=Depends(service)):
    q=select(RealisationPriseEnChargeModel).join(VenteModel,VenteModel.id==RealisationPriseEnChargeModel.vente_id).where(
        RealisationPriseEnChargeModel.organisation_id==s.org,RealisationPriseEnChargeModel.site_id==s.site,
        VenteModel.emplacement_id.in_(perimetre(s))).order_by(RealisationPriseEnChargeModel.realisee_le.desc(),RealisationPriseEnChargeModel.id)
    total,rows=s.stock.repo.paginer(q,page,page_size)
    return {'items':[serial(x) for x in rows],'total':total,'page':page,'page_size':page_size}


@router.get('',name='creances_liste')
def liste(organisme_id:UUID|None=None,page:int=Query(1,ge=1),page_size:int=Query(25,ge=1,le=100),s=Depends(service)):
    q=select(CreanceOrganismeModel).join(VenteModel,VenteModel.id==CreanceOrganismeModel.vente_id).where(
        CreanceOrganismeModel.organisation_id==s.org,CreanceOrganismeModel.site_id==s.site,VenteModel.emplacement_id.in_(perimetre(s)))
    if organisme_id:q=q.where(CreanceOrganismeModel.organisme_id==organisme_id)
    total,rows=s.stock.repo.paginer(q.order_by(CreanceOrganismeModel.cree_le.desc(),CreanceOrganismeModel.id),page,page_size)
    return execute(lambda:{'items':[s.detail(x.id) for x in rows],'total':total,'page':page,'page_size':page_size})


class Constitution(vente_api.Mutation):realisation_id:UUID
class Complement(vente_api.Revision):
    complements:dict=Field(default_factory=dict)
    motif:str=Field(min_length=1,max_length=2000)
class Verification(vente_api.Revision):
    conforme:bool=Field(strict=True)
    motif:str=Field(min_length=1,max_length=2000)
class Engagement(vente_api.Revision):operation:Literal['PRESENTER','GENERER_FACTURE','VALIDER_FACTURE','EMETTRE_FACTURE']


@router.post('',status_code=201,name='creances_constituer')
def constituer(data:Constitution,s=Depends(service)):
    execute(lambda:s.source(data.realisation_id)) # Recontrôle du périmètre avant tout rejeu.
    return mutate(s,data,'CONSTITUER',lambda:s.constituer(data.realisation_id))


@router.get('/{ident}',name='creance_detail')
def detail(ident:UUID,s=Depends(service)):return execute(lambda:s.detail(ident))


@router.get('/{ident}/historique',name='creance_historique')
def historique(ident:UUID,page:int=Query(1,ge=1),page_size:int=Query(25,ge=1,le=100),s=Depends(service)):
    execute(lambda:s.obtenir(ident))
    total,rows=s.stock.repo.paginer(select(VersionDossierCreanceModel).where(VersionDossierCreanceModel.creance_id==ident,
        VersionDossierCreanceModel.organisation_id==s.org).order_by(VersionDossierCreanceModel.revision.desc()),page,page_size)
    return {'items':[serial(x) for x in rows],'total':total,'page':page,'page_size':page_size}


@router.post('/{ident}/complements',name='creance_completer')
def completer(ident:UUID,data:Complement,s=Depends(service)):
    execute(lambda:s.obtenir(ident,'tiers_payant.creance.completer'))
    return mutate(s,data,'COMPLETER:'+str(ident),lambda:s.completer(ident,data.revision,data.complements,data.motif))


@router.post('/{ident}/verifier',name='creance_verifier')
def verifier(ident:UUID,data:Verification,s=Depends(service)):
    execute(lambda:s.obtenir(ident,'tiers_payant.creance.verifier'))
    return mutate(s,data,'VERIFIER:'+str(ident),lambda:s.verifier(ident,data.revision,data.motif,data.conforme))


@router.post('/{ident}/controle-engagement',name='creance_engagement')
def engagement(ident:UUID,data:Engagement,s=Depends(service)):
    execute(lambda:s.autoriser_engagement(ident,data.revision,data.operation))
    def action():
        result=s.autoriser_engagement(ident,data.revision,data.operation)
        s.tiers._audit('CREANCE',ident,'ENGAGEMENT_CONTROLE',result)
        return result
    return mutate(s,data,'ENGAGEMENT:'+str(ident),action)
