"""P4.4 : refus serveur par défaut, affectations P1 et CSRF existants."""
import re
from datetime import date
from decimal import Decimal
from uuid import UUID
from typing import Literal
from fastapi import APIRouter,Depends,Request,Query,Response,HTTPException
from pydantic import Field
from sqlalchemy import select,func
from neosys_pharma.presentation.vente_api import POLICY,contexte,service as vente_service,Input,Mutation,Revision
from neosys_pharma.presentation.stock_api import execute
from neosys_pharma.application.caisse_service import CaisseService,serial
from neosys_pharma.infrastructure.caisse_models import *
from neosys_pharma.infrastructure.vente_models import VenteModel
from neosys_pharma.infrastructure.organisation_models import EmplacementModel,CaisseModel,OrganisationModel,SiteModel
from neosys_pharma.infrastructure.catalogue_models import CategorieProduitModel
POLICY.update({
 'caisse_contexte':('caisse.consulter','caisse.encaisser','caisse.session.gerer','caisse.parametrer','fidelite.parametrer','fidelite.gerer'),
 'caisse_moyen_creer':'caisse.parametrer','caisse_moyen_modifier':'caisse.parametrer','caisse_renommer':'caisse.parametrer','caisse_config':'caisse.parametrer','caisse_sessions':'caisse.consulter','caisse_ouvrir':'caisse.session.gerer','caisse_fermer':'caisse.session.gerer',
 'caisse_attente':'caisse.consulter','caisse_vente':'caisse.consulter','caisse_confirmer':'caisse.paiement.confirmer','caisse_rapprocher':'caisse.paiement.confirmer','caisse_finaliser':'caisse.encaisser',
 'caisse_recus':'caisse.consulter','caisse_recu':'caisse.consulter','caisse_recu_pdf':'caisse.consulter','caisse_appel_pdf':'vente.consulter','caisse_mouvements':'caisse.consulter',
 'fidelite_recherche':'fidelite.consulter','fidelite_detail':'fidelite.consulter','fidelite_journal':'fidelite.consulter','fidelite_ventes':'fidelite.consulter','fidelite_creer':'fidelite.gerer','fidelite_carte':'fidelite.gerer','fidelite_code_barres':'fidelite.gerer','fidelite_impression':'fidelite.gerer','fidelite_carte_pdf':'fidelite.gerer','fidelite_opposer':'fidelite.gerer',
 'fidelite_baremes':'fidelite.parametrer','fidelite_bareme':'fidelite.parametrer','fidelite_clore':'fidelite.parametrer'})
router=APIRouter(prefix='/api/caisses/organisations/{organisation_id}',tags=['Encaissement et fidélité'],dependencies=[Depends(contexte)])
def service(v=Depends(vente_service)):return CaisseService(v)
def mutation(s,d,kind,fn):return execute(lambda:s.stock.operation(d.cle,'P4.4:'+kind,d.model_dump(mode='json',exclude={'cle'}),fn))
Mode=Literal['ESPECES','CARTE','MOBILE_MONEY','CHEQUE','VIREMENT']
class Config(Mutation):
    revision:int=Field(strict=True,ge=0)
    modes:list[Mode]=Field(max_length=5)
    ticket_appel:bool=False
class Ouverture(Mutation):
    caisse_id:UUID
    fond_initial:Decimal=Field(ge=0,max_digits=18,decimal_places=0)
class Fermeture(Revision):
    comptage_final:Decimal=Field(ge=0,max_digits=18,decimal_places=0)
    justification:str=Field(min_length=1,max_length=2000)
class Confirmation(Revision):
    moyen_id:UUID|None=None
    session_id:UUID
    mode:Mode
    montant:Decimal=Field(gt=0,max_digits=18,decimal_places=0)
    reference:str=Field(min_length=1,max_length=200)
    source:Literal['MANUEL_TERMINAL','MANUEL_JUSTIFICATIF','TECHNIQUE_PRESTATAIRE']
    preuve:str=Field(min_length=1,max_length=2000)
class Rapprochement(Revision):
    session_id:UUID
    justification:str=Field(min_length=1,max_length=2000)
class Paiement(Input):
    mode:Mode
    montant:Decimal=Field(gt=0,max_digits=18,decimal_places=0)
    confirmation_id:UUID|None=None
class Finalisation(Revision):
    session_id:UUID
    revision_session:int=Field(strict=True,ge=1)
    reglements:list[Paiement]=Field(max_length=20)
    compte_id:UUID|None=None
    revision_compte:int|None=Field(default=None,strict=True,ge=1)
    points_utilises:int=Field(default=0,strict=True,ge=0)
    consentement:bool=False
class Client(Mutation):
    nom:str=Field(min_length=1,max_length=200)
    telephone:str|None=Field(default=None,max_length=80)
class Carte(Revision):
    code_barres:str|None=Field(default=None,min_length=1,max_length=80)
    code:str|None=Field(default=None,min_length=1,max_length=200)
    type:Literal['PHYSIQUE','VIRTUELLE']
    remplace_id:UUID|None=None
class Opposition(Revision):justification:str=Field(min_length=1,max_length=2000)
class Bareme(Mutation):
    type:Literal['ACQUISITION','CONVERSION']
    debut:date
    fin:date|None=None
    points:int=Field(strict=True,gt=0,le=1_000_000_000)
    montant_xaf:Decimal=Field(gt=0,max_digits=18,decimal_places=0)
    categories:list[UUID]=Field(min_length=1,max_length=1000)
    sous_categories:bool
    plafond_xaf:Decimal|None=Field(default=None,ge=0,max_digits=18,decimal_places=0)
    plafond_pourcentage:Decimal|None=Field(default=None,ge=0,le=100,max_digits=5,decimal_places=2)
    paiement_integral:bool=False
class Cloture(Mutation):fin:date

def locations(s,permission):
    allowed=[]
    for l in s.s.scalars(select(EmplacementModel).where(EmplacementModel.site_id==s.site,EmplacementModel.actif.is_(True))):
        try:s.stock.emplacement(l.id_emplacement,permission);allowed.append(l.id_emplacement)
        except PermissionError:pass
    return allowed

def page(s,q,page,size,convert=serial):
    total,rows=s.stock.repo.paginer(q,page,size)
    return {'items':[convert(x) for x in rows],'total':total,'page':page,'page_size':size}

@router.get('/contexte')
def caisse_contexte(request:Request,s=Depends(service)):
    ids=locations(s,request.state.vente_permission)
    return {'caisses':[{'id':str(c.id_caisse),'nom':c.nom,'emplacement_id':str(c.emplacement_id)} for c in s.s.scalars(select(CaisseModel).where(CaisseModel.emplacement_id.in_(ids),CaisseModel.actif.is_(True)))],'configuration':s.config(),'fiscalite_fidelite':{'validee':False,'utilisation_disponible':False},'categories':[{'id':str(c.id_categorie),'nom':c.nom} for c in s.s.scalars(select(CategorieProduitModel).where(CategorieProduitModel.organisation_id==s.org))]}
@router.post('/configuration')
def caisse_config(d:Config,s=Depends(service)):return mutation(s,d,'CONFIG',lambda:s.configurer(d.model_dump(exclude={'cle'})))
@router.get('/sessions')
def caisse_sessions(page_:int=Query(1,alias='page',ge=1),page_size:int=Query(25,ge=1,le=100),s=Depends(service)):
    q=select(SessionCaisseModel).where(SessionCaisseModel.organisation_id==s.org,SessionCaisseModel.site_id==s.site,SessionCaisseModel.emplacement_id.in_(locations(s,'caisse.consulter'))).order_by(SessionCaisseModel.ouvert_le.desc(),SessionCaisseModel.id)
    return page(s,q,page_,page_size,s.session_detail)
@router.post('/sessions',status_code=201)
def caisse_ouvrir(d:Ouverture,s=Depends(service)):
    execute(lambda:s.caisse(d.caisse_id,'caisse.session.gerer'))
    return mutation(s,d,'OUVRIR',lambda:s.ouvrir(d.model_dump(exclude={'cle'})))
@router.post('/sessions/{key}/fermer')
def caisse_fermer(key:UUID,d:Fermeture,s=Depends(service)):
    execute(lambda:s.session(key,'caisse.session.gerer'))
    return mutation(s,d,'FERMER:'+str(key),lambda:s.fermer(key,d.model_dump()))
@router.get('/attente')
def caisse_attente(page_:int=Query(1,alias='page',ge=1),page_size:int=Query(25,ge=1,le=100),s=Depends(service)):
    q=select(VenteModel).where(VenteModel.organisation_id==s.org,VenteModel.site_id==s.site,VenteModel.emplacement_id.in_(locations(s,'caisse.consulter')),VenteModel.etat=='TRANSMISE').order_by(VenteModel.cree_le,VenteModel.id)
    def item(v):
        a=s.s.scalar(select(AppelVenteModel).filter_by(organisation_id=s.org,vente_id=v.id))
        return serial(v)|{'numero_appel':str(a.numero).zfill(4) if a else None,'net_ttc':s.vente.finance(v)['totaux']['ttc']}
    return page(s,q,page_,page_size,item)
@router.get('/ventes/{key}')
def caisse_vente(key:UUID,s=Depends(service)):
    v=execute(lambda:s.vente.obtenir(key,'caisse.consulter'))
    receipt=s.s.scalar(select(EncaissementModel).where(EncaissementModel.vente_id==v.id,EncaissementModel.organisation_id==s.org))
    coverage=(receipt.instantane.get('prise_en_charge') if receipt else
              execute(lambda:s.prise_en_charge_detail_optionnelle(v)))
    return execute(lambda:s.vente.detail(v))|{'prise_en_charge':coverage,'confirmations':[serial(c) for c in s.stock.lignes(ConfirmationReglementModel,vente_id=v.id)]}
@router.post('/ventes/{key}/confirmations',status_code=201)
def caisse_confirmer(key:UUID,d:Confirmation,s=Depends(service)):
    execute(lambda:s.vente.obtenir(key,'caisse.paiement.confirmer'));execute(lambda:s.session(d.session_id,'caisse.paiement.confirmer'))
    return mutation(s,d,'CONFIRMER:'+str(key),lambda:s.confirmer(key,d.model_dump()))
@router.post('/ventes/{key}/confirmations/{confirmation_id}/rapprocher')
def caisse_rapprocher(key:UUID,confirmation_id:UUID,d:Rapprochement,s=Depends(service)):
    execute(lambda:s.vente.obtenir(key,'caisse.paiement.confirmer'));execute(lambda:s.session(d.session_id,'caisse.paiement.confirmer'))
    return mutation(s,d,'RAPPROCHER:'+str(confirmation_id),lambda:s.rapprocher(key,confirmation_id,d.model_dump()))
@router.post('/ventes/{key}/finaliser')
def caisse_finaliser(key:UUID,d:Finalisation,s=Depends(service)):
    execute(lambda:s.vente.obtenir(key,'caisse.encaisser'));execute(lambda:s.session(d.session_id,'caisse.encaisser'))
    if d.compte_id:execute(lambda:s.compte(d.compte_id))
    if d.points_utilises:execute(lambda:s.stock.access('fidelite.utiliser',s.site,s.vente.obtenir(key,'caisse.encaisser').emplacement_id))
    return mutation(s,d,'FINALISER:'+str(key),lambda:s.finaliser(key,d.model_dump()))

def recu(s,key):
    e=s.stock.obtenir(EncaissementModel,key);s.vente.obtenir(e.vente_id,'caisse.consulter');return e
@router.get('/recus')
def caisse_recus(page_:int=Query(1,alias='page',ge=1),page_size:int=Query(25,ge=1,le=100),s=Depends(service)):
    q=select(EncaissementModel).join(VenteModel,VenteModel.id==EncaissementModel.vente_id).where(EncaissementModel.organisation_id==s.org,VenteModel.site_id==s.site,VenteModel.emplacement_id.in_(locations(s,'caisse.consulter'))).order_by(EncaissementModel.date.desc(),EncaissementModel.id)
    return page(s,q,page_,page_size,s.recu)
@router.get('/recus/{key}')
def caisse_recu(key:UUID,s=Depends(service)):return execute(lambda:s.recu(recu(s,key)))
@router.get('/recus/{key}/pdf')
def caisse_recu_pdf(key:UUID,s=Depends(service)):
    e=execute(lambda:recu(s,key));return Response(e.pdf,media_type='application/pdf',headers={'Content-Disposition':f'inline; filename="recu-{e.numero:04d}.pdf"'})
@router.get('/ventes/{key}/appel/pdf')
def caisse_appel_pdf(key:UUID,s=Depends(service)):
    v=execute(lambda:s.vente.obtenir(key,'vente.consulter'))
    if not s.config()['ticket_appel']:raise HTTPException(409,'Ticket d’appel désactivé par la pharmacie.')
    a=s.s.scalar(select(AppelVenteModel).filter_by(organisation_id=s.org,vente_id=v.id))
    if not a:raise HTTPException(409,'Aucun numéro d’appel attribué.')
    from neosys_pharma.infrastructure.caisse_pdf import appel_pdf
    return Response(appel_pdf(s.s.get(OrganisationModel,s.org).nom_commercial,s.s.get(SiteModel,s.site).nom,v,{'affichage':str(a.numero).zfill(4)}),media_type='application/pdf')
@router.get('/mouvements')
def caisse_mouvements(session_id:UUID,page_:int=Query(1,alias='page',ge=1),page_size:int=Query(25,ge=1,le=100),s=Depends(service)):
    execute(lambda:s.session(session_id,'caisse.consulter'))
    ordinary=[serial(row)|{'source':'INDIVIDUEL'} for row in s.stock.lignes(MouvementCaisseModel,session_id=session_id)]
    grouped=[serial(row)|{'source':'GROUPE'} for row in s.stock.lignes(MouvementCaisseGroupeModel,session_id=session_id)]
    items=sorted(ordinary+grouped,key=lambda row:(row['date'],row['id']))
    start=(page_-1)*page_size
    return {'items':items[start:start+page_size],'total':len(items),'page':page_,'page_size':page_size}
@router.get('/fidelite')
def fidelite_recherche(q:str=Query('',min_length=3,max_length=200),page_:int=Query(1,alias='page',ge=1),page_size:int=Query(20,ge=1,le=100),s=Depends(service)):
    term=s.stock.repo.terme(q);phone=re.sub(r'[\s().-]','',q)
    cards=select(CarteFideliteModel.compte_id).where(CarteFideliteModel.organisation_id==s.org,CarteFideliteModel.id.in_(select(IdentifiantCarteFideliteModel.carte_id).where(IdentifiantCarteFideliteModel.organisation_id==s.org,IdentifiantCarteFideliteModel.valeur==q)),CarteFideliteModel.etat=='ACTIVE')
    query=select(CompteFideliteModel).join(ClientFideliteModel,ClientFideliteModel.id==CompteFideliteModel.client_id).where(CompteFideliteModel.organisation_id==s.org,(s.stock.repo.upper(ClientFideliteModel.nom).contains(term,autoescape=True))|(ClientFideliteModel.telephone==phone)|(CompteFideliteModel.id.in_(cards))).order_by(ClientFideliteModel.nom,CompteFideliteModel.id)
    return page(s,query,page_,page_size,lambda r:s.compte(r.id))
@router.post('/fidelite',status_code=201)
def fidelite_creer(d:Client,s=Depends(service)):return mutation(s,d,'CLIENT',lambda:s.creer_compte(d.model_dump()))
@router.get('/fidelite/{key}')
def fidelite_detail(key:UUID,s=Depends(service)):return execute(lambda:s.compte(key))
@router.get('/fidelite/{key}/journal')
def fidelite_journal(key:UUID,page_:int=Query(1,alias='page',ge=1),page_size:int=Query(25,ge=1,le=100),s=Depends(service)):
    execute(lambda:s.compte(key))
    from neosys_pharma.infrastructure.regularisation_models import CompensationRetourModel,RetourVenteModel
    return page(s,select(JournalFideliteModel).outerjoin(CompensationRetourModel,CompensationRetourModel.journal_id==JournalFideliteModel.id).outerjoin(RetourVenteModel,RetourVenteModel.id==CompensationRetourModel.retour_id).join(EncaissementModel,EncaissementModel.id==func.coalesce(JournalFideliteModel.encaissement_id,RetourVenteModel.encaissement_id)).join(VenteModel,VenteModel.id==EncaissementModel.vente_id).where(JournalFideliteModel.organisation_id==s.org,JournalFideliteModel.compte_id==key,VenteModel.site_id==s.site,VenteModel.emplacement_id.in_(locations(s,'fidelite.consulter'))).order_by(JournalFideliteModel.date,JournalFideliteModel.id),page_,page_size)
@router.get('/fidelite/{key}/ventes')
def fidelite_ventes(key:UUID,page_:int=Query(1,alias='page',ge=1),page_size:int=Query(25,ge=1,le=100),s=Depends(service)):
    """Historique des ventes encaissées et explicitement liées au compte fidélité."""
    execute(lambda:s.compte(key))
    q=(select(EncaissementModel)
       .join(VenteModel,VenteModel.id==EncaissementModel.vente_id)
       .where(EncaissementModel.organisation_id==s.org,
              EncaissementModel.compte_id==key,
              VenteModel.site_id==s.site,
              VenteModel.emplacement_id.in_(locations(s,'fidelite.consulter')))
       .order_by(EncaissementModel.date.desc(),EncaissementModel.id.desc()))
    def item(encaissement):
        vente=s.s.get(VenteModel,encaissement.vente_id)
        return {'vente_id':str(vente.id),'encaissement_id':str(encaissement.id),
                'numero_recu':str(encaissement.numero).zfill(4),
                'date':encaissement.date.isoformat(),'total_xaf':str(encaissement.total_xaf),
                'mode_vente':vente.mode}
    return page(s,q,page_,page_size,item)
@router.post('/fidelite/{key}/cartes',status_code=201)
def fidelite_carte(key:UUID,d:Carte,s=Depends(service)):
    execute(lambda:s.compte(key,'fidelite.gerer'))
    return mutation(s,d,'CARTE:'+str(key),lambda:s.carte(key,d.model_dump()))
@router.post('/cartes/{key}/opposer')
def fidelite_opposer(key:UUID,d:Opposition,s=Depends(service)):
    row=execute(lambda:s.stock.obtenir(CarteFideliteModel,key));execute(lambda:s.compte(row.compte_id,'fidelite.gerer'))
    return mutation(s,d,'OPPOSER:'+str(key),lambda:s.opposer(key,d.model_dump()))
@router.get('/baremes')
def fidelite_baremes(page_:int=Query(1,alias='page',ge=1),page_size:int=Query(25,ge=1,le=100),s=Depends(service)):
    return page(s,select(BaremeFideliteModel).where(BaremeFideliteModel.organisation_id==s.org).order_by(BaremeFideliteModel.debut.desc(),BaremeFideliteModel.id),page_,page_size)
@router.post('/baremes',status_code=201)
def fidelite_bareme(d:Bareme,s=Depends(service)):return mutation(s,d,'BAREME',lambda:s.ajouter_bareme(d.model_dump(exclude={'cle'})))
@router.post('/baremes/{key}/clore')
def fidelite_clore(key:UUID,d:Cloture,s=Depends(service)):
    execute(lambda:s.stock.obtenir(BaremeFideliteModel,key))
    return mutation(s,d,'BAREME_CLORE:'+str(key),lambda:s.clore_bareme(key,d.model_dump()))


class NomCaisse(Mutation):
    nom_attendu: str = Field(min_length=1, max_length=200)
    nom: str = Field(min_length=1, max_length=200)


@router.put('/caisses/{key}/libelle')
def caisse_renommer(key:UUID,d:NomCaisse,s=Depends(service)):
    execute(lambda:s.caisse(key,'caisse.parametrer'))
    return mutation(s,d,'RENOMMER_CAISSE:'+str(key),lambda:s.renommer_caisse(key,d.model_dump()))


class CreationMoyen(Mutation):
    code:str=Field(min_length=1,max_length=80)
    libelle:str=Field(min_length=1,max_length=200)
    mode:Literal['CARTE','MOBILE_MONEY','CHEQUE','VIREMENT']
    actif:bool=True
class ModificationMoyen(Revision):
    libelle:str=Field(min_length=1,max_length=200)
    actif:bool

@router.post('/moyens',status_code=201)
def caisse_moyen_creer(d:CreationMoyen,s=Depends(service)):
    return mutation(s,d,'MOYEN_CREER',lambda:s.definir_moyen(d.model_dump()))

@router.put('/moyens/{key}')
def caisse_moyen_modifier(key:UUID,d:ModificationMoyen,s=Depends(service)):
    return mutation(s,d,'MOYEN_MODIFIER:'+str(key),lambda:s.definir_moyen(d.model_dump(),key))


class CodeBarresCarte(Revision):
    code_barres:str=Field(min_length=1,max_length=80)

@router.post('/fidelite/cartes/{key}/code-barres')
def fidelite_code_barres(key:UUID,d:CodeBarresCarte,s=Depends(service)):
    return mutation(s,d,'CARTE_BARRES:'+str(key),lambda:s.associer_code_barres(key,d.model_dump()))

@router.post('/fidelite/cartes/{key}/impressions')
def fidelite_impression(key:UUID,d:Mutation,s=Depends(service)):
    return mutation(s,d,'CARTE_DOCUMENT:'+str(key),lambda:s.imprimer_carte(key))

@router.get('/fidelite/cartes/{key}/pdf')
def fidelite_carte_pdf(key:UUID,s=Depends(service)):
    def get():
        card=s.stock.obtenir(CarteFideliteModel,key);s.compte(card.compte_id,'fidelite.gerer')
        rows=s.stock.lignes(DocumentCarteFideliteModel,carte_id=card.id)
        if not rows:raise LookupError('Préparer le document de carte avant consultation.')
        return Response(rows[0].pdf,media_type='application/pdf',headers={'Content-Disposition':'inline; filename="carte-fidelite.pdf"'})
    return execute(get)
