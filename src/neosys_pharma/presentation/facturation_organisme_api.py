"""Préparation et documents organismes, CSRF et permissions P1 inchangés."""
from datetime import date,datetime,time,timedelta,timezone
from uuid import UUID
from typing import Literal
from fastapi import APIRouter,Depends,Query,Response
from pydantic import Field
from sqlalchemy import select,func,exists
from sqlalchemy.orm import aliased
from neosys_pharma.presentation import vente_api,creance_api
from neosys_pharma.presentation.stock_api import execute
from neosys_pharma.application.facturation_organisme_service import FacturationOrganismeService,emission_isolee_autorisee
from neosys_pharma.application.stock_service import serial
from neosys_pharma.infrastructure.facturation_organisme_models import (
    PreparationOrganismeModel,VersionPreparationOrganismeModel,SelectionVersionPreparationModel,DocumentOrganismeModel,RegroupementDocumentsModel,MembreRegroupementModel,EngagementCreanceModel)
from neosys_pharma.infrastructure.creance_models import CreanceOrganismeModel,VersionDossierCreanceModel
from neosys_pharma.infrastructure.vente_models import VenteModel
from neosys_pharma.infrastructure.client_models import OrganismePriseEnChargeModel
from neosys_pharma.infrastructure.prise_en_charge_models import RealisationPriseEnChargeModel

POLICY={
 'documents_activation':'tiers_payant.document.consulter','documents_preparations_liste':'tiers_payant.document.consulter',
 'documents_preparation_creer':'tiers_payant.document.preparer','documents_preparation_lire':'tiers_payant.document.consulter',
 'documents_preparation_modifier':'tiers_payant.document.preparer','documents_preparation_abandonner':'tiers_payant.document.preparer',
 'documents_preparation_valider':'tiers_payant.document.valider','documents_preparation_emettre':'tiers_payant.document.emettre',
 'documents_preparation_pdf':'tiers_payant.document.consulter','documents_pdf':'tiers_payant.document.consulter',
 'documents_regrouper':'tiers_payant.document.regrouper','documents_regroupement_lire':'tiers_payant.document.consulter',
 'documents_regroupements_liste':'tiers_payant.document.consulter','documents_regroupement_pdf':'tiers_payant.document.consulter','documents_historique':'tiers_payant.document.consulter',
 'documents_creances_rechercher':'tiers_payant.creance.consulter'}
POLICY['documents_regroupements_liste']='tiers_payant.document.consulter'
POLICY['documents_organismes_liste']='tiers_payant.document.consulter'
vente_api.POLICY.update(POLICY)
router=APIRouter(prefix='/api/tiers-payants/organisations/{organisation_id}/documents',tags=['Documents organismes'],dependencies=[Depends(vente_api.contexte)])


def service(s=Depends(vente_api.service)):return FacturationOrganismeService(s.stock,s.site)


def mutate(s,data,kind,action):
    return execute(lambda:s.stock.operation(data.cle,'P5C2:'+kind,data.model_dump(mode='json',exclude={'cle'}),action))


class Selection(vente_api.Input):
    creance_id:UUID
    revision:int=Field(strict=True,ge=1)
class Creation(vente_api.Mutation):
    genre:Literal['BORDEREAU','FACTURE']
    organisme_id:UUID
    convention_id:UUID
    presentation_id:UUID|None=None
    date_debut:date
    date_fin:date
    selection:list[Selection]=Field(min_length=1,max_length=100)
    motif:str=Field(min_length=1,max_length=2000)
class Modification(vente_api.Revision):
    selection:list[Selection]=Field(max_length=100)
    motif:str=Field(min_length=1,max_length=2000)
class Action(vente_api.Revision):motif:str=Field(min_length=1,max_length=2000)
class Emission(Action):
    reference:str=Field(min_length=1,max_length=80)
    reference_validation:str=Field(min_length=1,max_length=200)
class Regroupement(vente_api.Mutation):
    genre:Literal['RECAPITULATIF','LOT']
    ids:list[UUID]=Field(min_length=1,max_length=100)
    motif:str=Field(min_length=1,max_length=2000)


@router.get('/activation',name='documents_activation')
def activation(s=Depends(service)):
    return {'emission_recette_autorisee':execute(lambda:emission_isolee_autorisee(s.stock)),
        'emission_production_autorisee':False,'motif':'Numérotation et conformité fiscale à valider ; émission de recette isolée uniquement.'}


@router.get('/organismes',name='documents_organismes_liste')
def organismes(q:str=Query('',max_length=200),page:int=Query(1,ge=1),page_size:int=Query(25,ge=1,le=100),s=Depends(service)):
    c=CreanceOrganismeModel;o=OrganismePriseEnChargeModel
    sources=select(c.organisme_id).join(VenteModel,VenteModel.id==c.vente_id).where(c.organisation_id==s.org,c.site_id==s.site,
        VenteModel.emplacement_id.in_(creance_api.perimetre(s.creances)))
    query=select(o).where(o.organisation_id==s.org,o.id.in_(sources))
    if q.strip():
        value=q.strip().replace('\\','\\\\').replace('%','\\%').replace('_','\\_')
        query=query.where(o.nom.ilike('%'+value+'%',escape='\\')|o.code.ilike('%'+value+'%',escape='\\'))
    total,rows=s.stock.repo.paginer(query.order_by(o.nom,o.id),page,page_size)
    return {'items':[serial(x) for x in rows],'total':total,'page':page,'page_size':page_size}


@router.get('/creances',name='documents_creances_rechercher')
def rechercher(organisme_id:UUID|None=None,statut:Literal['A_COMPLETER','A_CONTROLER','VALIDE_POUR_FACTURATION','EN_ANOMALIE','FACTURE']|None=None,
        date_debut:date|None=None,date_fin:date|None=None,page:int=Query(1,ge=1),page_size:int=Query(25,ge=1,le=100),s=Depends(service)):
    if date_fin==date.max or (date_debut and date_fin and date_fin<date_debut):
        from fastapi import HTTPException
        raise HTTPException(422,'Période inversée.')
    c=CreanceOrganismeModel;v=VersionDossierCreanceModel;r=RealisationPriseEnChargeModel
    latest=select(func.max(v.revision)).where(v.creance_id==c.id,v.organisation_id==s.org).correlate(c).scalar_subquery()
    q=select(c).join(VenteModel,VenteModel.id==c.vente_id).join(r,r.id==c.realisation_id).join(v,(v.creance_id==c.id)&(v.revision==latest)).where(
        c.organisation_id==s.org,c.site_id==s.site,VenteModel.emplacement_id.in_(creance_api.perimetre(s.creances)))
    if organisme_id:q=q.where(c.organisme_id==organisme_id)
    if date_debut:q=q.where(r.realisee_le>=datetime.combine(date_debut,time.min,tzinfo=timezone.utc))
    if date_fin:q=q.where(r.realisee_le<datetime.combine(date_fin+timedelta(days=1),time.min,tzinfo=timezone.utc))
    ordered=q.order_by(c.cree_le.desc(),c.id)
    if statut:
        # Le statut effectif dépend des écritures compensatoires; un simple
        # EXISTS(retour) continuerait à masquer les retours déjà régularisés.
        candidates=s.s.scalars(ordered).all()
        rows=[row for row in candidates if s.creances.detail(row.id)['etat_effectif']==statut]
        total=len(rows);rows=rows[(page-1)*page_size:page*page_size]
    else:
        total,rows=s.stock.repo.paginer(ordered,page,page_size)
    def result():
        items=[]
        for row in rows:
            engagements=s.s.scalars(select(EngagementCreanceModel).where(EngagementCreanceModel.creance_id==row.id,EngagementCreanceModel.organisation_id==s.org)).all()
            items.append(s.creances.detail(row.id)|{'engagements':[serial(x) for x in engagements],
                'organisme':serial(s.creances.tiers._organisme(row.organisme_id))})
        return {'items':items,'total':total,'page':page,'page_size':page_size,'periode':'UTC réalisation'}
    return execute(result)


def preparations_accessibles(s):
    p=PreparationOrganismeModel;v=VersionPreparationOrganismeModel
    locations=[]
    for loc in creance_api.perimetre(s.creances):
        try:s.stock.access('tiers_payant.document.consulter',s.site,loc);locations.append(loc)
        except PermissionError:pass
    disallowed=exists(select(SelectionVersionPreparationModel.id).join(v,v.id==SelectionVersionPreparationModel.version_id).join(CreanceOrganismeModel,
        CreanceOrganismeModel.id==SelectionVersionPreparationModel.creance_id).join(VenteModel,VenteModel.id==CreanceOrganismeModel.vente_id).where(
        v.preparation_id==p.id,~VenteModel.emplacement_id.in_(locations)))
    return select(p.id).where(p.organisation_id==s.org,p.site_id==s.site,~disallowed)


@router.get('/preparations',name='documents_preparations_liste')
def preparations(organisme_id:UUID|None=None,genre:Literal['BORDEREAU','FACTURE']|None=None,creance_id:UUID|None=None,
        page:int=Query(1,ge=1),page_size:int=Query(25,ge=1,le=100),s=Depends(service)):
    p=PreparationOrganismeModel
    q=select(p).where(p.id.in_(preparations_accessibles(s)))
    if organisme_id:q=q.where(p.organisme_id==organisme_id)
    if genre:q=q.where(p.genre==genre)
    if creance_id:
        q=q.where(exists(select(SelectionVersionPreparationModel.id).join(VersionPreparationOrganismeModel,VersionPreparationOrganismeModel.id==SelectionVersionPreparationModel.version_id).where(VersionPreparationOrganismeModel.preparation_id==p.id,SelectionVersionPreparationModel.creance_id==creance_id)))
    total,rows=s.stock.repo.paginer(q.order_by(p.cree_le.desc(),p.id),page,page_size)
    return execute(lambda:{'items':[s.detail(x.id) for x in rows],'total':total,'page':page,'page_size':page_size})


@router.post('/preparations',status_code=201,name='documents_preparation_creer')
def creer(data:Creation,s=Depends(service)):
    # Les droits sur chaque source précèdent également un rejeu idempotent.
    execute(lambda:s.stock.access('tiers_payant.document.consulter',s.site))
    for item in data.selection:
        claim=execute(lambda:s.creances.obtenir(item.creance_id))
        execute(lambda:s.creances.vente(claim.vente_id,'tiers_payant.document.preparer'))
        execute(lambda:s.creances.vente(claim.vente_id,'tiers_payant.document.consulter'))
    return mutate(s,data,'CREER',lambda:s.creer(data.model_dump(exclude={'cle'})))


@router.get('/preparations/{ident}',name='documents_preparation_lire')
def lire(ident:UUID,s=Depends(service)):return execute(lambda:s.detail(ident))


@router.post('/preparations/{ident}/selection',name='documents_preparation_modifier')
def modifier(ident:UUID,data:Modification,s=Depends(service)):
    execute(lambda:s.obtenir(ident,'tiers_payant.document.preparer'))
    for item in data.selection:
        claim=execute(lambda:s.creances.obtenir(item.creance_id))
        execute(lambda:s.creances.vente(claim.vente_id,'tiers_payant.document.preparer'))
    return mutate(s,data,'MODIFIER:'+str(ident),lambda:s.modifier(ident,data.revision,[x.model_dump() for x in data.selection],data.motif))


@router.post('/preparations/{ident}/abandonner',name='documents_preparation_abandonner')
def abandonner(ident:UUID,data:Action,s=Depends(service)):
    execute(lambda:s.obtenir(ident,'tiers_payant.document.preparer'))
    return mutate(s,data,'ABANDONNER:'+str(ident),lambda:s.abandonner(ident,data.revision,data.motif))


@router.post('/preparations/{ident}/valider',name='documents_preparation_valider')
def valider(ident:UUID,data:Action,s=Depends(service)):
    execute(lambda:s.obtenir(ident,'tiers_payant.document.valider'))
    return mutate(s,data,'VALIDER:'+str(ident),lambda:s.valider(ident,data.revision,data.motif))


@router.post('/preparations/{ident}/emettre',name='documents_preparation_emettre')
def emettre(ident:UUID,data:Emission,s=Depends(service)):
    execute(lambda:s.obtenir(ident,'tiers_payant.document.emettre'))
    return mutate(s,data,'EMETTRE:'+str(ident),lambda:s.emettre(ident,data.revision,data.reference,data.reference_validation,data.motif))


@router.get('/preparations/{ident}/previsualisation.pdf',name='documents_preparation_pdf')
def previsualiser(ident:UUID,revision:int=Query(ge=1),s=Depends(service)):
    def action():
        pdf=s.previsualiser(ident,revision)
        # GET ne valide ni ne publie la préparation ; libérer le verrou de lecture.
        s.s.rollback()
        return pdf
    return Response(execute(action),media_type='application/pdf',headers={'Content-Disposition':'inline; filename="brouillon-organisme.pdf"'})


@router.get('/preparations/{ident}/historique',name='documents_historique')
def historique(ident:UUID,page:int=Query(1,ge=1),page_size:int=Query(25,ge=1,le=100),s=Depends(service)):
    execute(lambda:s.obtenir(ident))
    total,rows=s.stock.repo.paginer(select(VersionPreparationOrganismeModel).where(VersionPreparationOrganismeModel.preparation_id==ident,
        VersionPreparationOrganismeModel.organisation_id==s.org).order_by(VersionPreparationOrganismeModel.revision.desc()),page,page_size)
    return {'items':[serial(x) for x in rows],'total':total,'page':page,'page_size':page_size}


@router.get('/emis/{ident}/pdf',name='documents_pdf')
def pdf(ident:UUID,s=Depends(service)):
    return Response(execute(lambda:s.document(ident).pdf),media_type='application/pdf',headers={'Content-Disposition':'inline; filename="document-organisme-recette.pdf"'})


@router.get('/regroupements',name='documents_regroupements_liste')
def regroupements(genre:Literal['RECAPITULATIF','LOT']|None=None,organisme_id:UUID|None=None,document_id:UUID|None=None,
        page:int=Query(1,ge=1),page_size:int=Query(25,ge=1,le=100),s=Depends(service)):
    g=RegroupementDocumentsModel;m=MembreRegroupementModel;child=aliased(MembreRegroupementModel);d=DocumentOrganismeModel
    hidden=exists(select(m.id).outerjoin(child,child.regroupement_id==m.recapitulatif_id).join(d,(d.id==m.document_id)|(d.id==child.document_id)).where(
        m.regroupement_id==g.id,~d.preparation_id.in_(preparations_accessibles(s))))
    q=select(g).where(g.organisation_id==s.org,g.site_id==s.site,~hidden)
    if genre:q=q.where(g.genre==genre)
    if organisme_id:q=q.where(g.organisme_id==organisme_id)
    if document_id:
        q=q.where(exists(select(m.id).outerjoin(child,child.regroupement_id==m.recapitulatif_id).where(m.regroupement_id==g.id,(m.document_id==document_id)|(child.document_id==document_id))))
    total,rows=s.stock.repo.paginer(q.order_by(g.cree_le.desc(),g.id),page,page_size)
    return execute(lambda:{'items':[s.document_info(s.regroupement(x.id)) for x in rows],'total':total,'page':page,'page_size':page_size})


@router.post('/regroupements',status_code=201,name='documents_regrouper')
def regrouper(data:Regroupement,s=Depends(service)):
    for ident in data.ids:execute(lambda:s.document(ident) if data.genre=='RECAPITULATIF' else s.regroupement(ident))
    return mutate(s,data,'REGROUPER',lambda:s.regrouper(data.genre,data.ids,data.motif))


@router.get('/regroupements/{ident}',name='documents_regroupement_lire')
def regroupement(ident:UUID,s=Depends(service)):return execute(lambda:s.document_info(s.regroupement(ident)))


@router.get('/regroupements/{ident}/pdf',name='documents_regroupement_pdf')
def regroupement_pdf(ident:UUID,s=Depends(service)):
    return Response(execute(lambda:s.regroupement(ident).pdf),media_type='application/pdf')
