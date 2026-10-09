"""Politique fermée P3 : permissions et périmètres vérifiés aussi en HTTP direct."""
from datetime import date
from uuid import UUID
from typing import Literal
from fastapi import APIRouter,Depends,HTTPException,Request,Query
from pydantic import BaseModel,ConfigDict,Field
from sqlalchemy import select,or_,func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from neosys_pharma.presentation.authentification_api import utilisateur_courant,jour_courant
from neosys_pharma.infrastructure.securite_models import UtilisateurModel
from neosys_pharma.infrastructure.database import get_db_session
from neosys_pharma.infrastructure.securite_repository import SqlAlchemySecuriteRepository
from neosys_pharma.application.controle_acces import ControleAcces
from neosys_pharma.application.stock_service import StockService,serial,ident
from neosys_pharma.infrastructure.stock_models import *
from neosys_pharma.infrastructure.organisation_models import EmplacementModel,SiteModel
from neosys_pharma.infrastructure.catalogue_models import ConditionnementModel,ProduitModel,ReferenceProduitModel
from neosys_pharma.domain.stock import ConflitStock
from neosys_pharma.domain.catalogue import texte

POLICY={
 'stocks':('stock.consulter',),'lots':('stock.consulter','stock.gerer','stock.reserver'),'lot_creer':('stock.gerer',),'mouvements':('stock.consulter',),'entree':('stock.gerer',),'sortie':('stock.gerer',),
 'reservation_creer':('stock.reserver',),'reservation_lire':('stock.reserver',),'reservation_liberer':('stock.reserver',),'reservation_consommer':('stock.reserver',),
 'transferts':('stock.consulter','stock.transferer','stock.transfert.valider','stock.transfert.recevoir'),'transfert_lire':('stock.consulter','stock.transferer','stock.transfert.valider','stock.transfert.recevoir'),
 'demande_creer':('stock.transferer',),'interne':('stock.transferer',),'demande_valider':('stock.transfert.valider',),'demande_annuler':('stock.transfert.valider',),'demande_expedier':('stock.transferer',),'demande_recevoir':('stock.transfert.recevoir',),
 'inventaires':('stock.inventaire.gerer','stock.inventaire.compter','stock.inventaire.valider'),'inventaire_lire':('stock.inventaire.gerer','stock.inventaire.compter','stock.inventaire.valider'),
 'inventaire_creer':('stock.inventaire.gerer',),'participant_creer':('stock.inventaire.gerer',),'comptage':('stock.inventaire.compter',),'inventaire_valider':('stock.inventaire.valider',),'inventaire_annuler':('stock.inventaire.gerer',),
 'motifs':('stock.inventaire.gerer','stock.inventaire.compter','stock.inventaire.valider'),'motif_creer':('stock.inventaire.gerer',),'contextes':('stock.consulter','stock.gerer','stock.reserver','stock.transferer','stock.transfert.valider','stock.transfert.recevoir','stock.inventaire.gerer','stock.inventaire.compter','stock.inventaire.valider'),
}

def stock_context(request:Request,organisation_id:UUID,user=Depends(utilisateur_courant),session:Session=Depends(get_db_session)):
    try:
        site=UUID(request.headers.get('X-Site-ID',''));controle=ControleAcces(SqlAlchemySecuriteRepository(session),user,jour_courant())
        permissions=POLICY.get(request.scope['route'].name,())
        if not permissions:raise PermissionError('Opération Stock non autorisée.')
        authorized=[]
        for p in permissions:
            try:controle.organisation(p,organisation_id,site);authorized.append(p)
            except PermissionError:pass
        if not authorized:raise PermissionError('Permission Stock et affectation au site requises.')
        location=request.headers.get('X-Emplacement-ID')
        if location:
            effective=next((p for p in authorized if controle.droits.autorise(user.id_utilisateur,site,p,jour_courant(),UUID(location))),None)
            if not effective:raise PermissionError('Emplacement courant non autorisé.')
            controle.verifier(effective,site,UUID(location))
        request.state.stock_site=site;request.state.stock_controle=controle;request.state.stock_permissions=authorized
    except (ValueError,PermissionError) as exc:raise HTTPException(403,str(exc) or 'Contexte Stock requis.') from exc

router=APIRouter(prefix='/api/stock/organisations/{organisation_id}',tags=['Stock & Inventaire'],dependencies=[Depends(stock_context)])

class Input(BaseModel):model_config=ConfigDict(extra='forbid',str_strip_whitespace=True)
class Mutation(Input):cle:UUID
class Justifie(Mutation):justification:str=Field(min_length=1,max_length=2000)
class LotInput(Mutation):
    conditionnement_id:UUID
    numero:str | None=Field(default=None,min_length=1,max_length=100)
    peremption:date | None=None
class MouvementInput(Justifie):
    lot_id:UUID
    emplacement_id:UUID
    quantite:int=Field(strict=True,ge=-1_000_000_000,le=1_000_000_000)
    type:Literal['ENTREE','AJUSTEMENT','CORRECTION']='ENTREE'
    origine:str=Field(min_length=1,max_length=200)
class ReservationInput(Mutation):
    conditionnement_id:UUID
    emplacement_id:UUID
    quantite:int=Field(strict=True,gt=0,le=1_000_000_000)
    origine:str=Field(min_length=1,max_length=200)
    lot_id:UUID | None=None
    justification:str | None=Field(default=None,min_length=1,max_length=2000)
class LigneDemande(Input):
    conditionnement_id:UUID
    quantite:int=Field(strict=True,gt=0,le=1_000_000_000)
    lot_id:UUID | None=None
class DemandeInput(Justifie):
    source_id:UUID
    destination_id:UUID
    lignes:list[LigneDemande]=Field(min_length=1,max_length=100)
class LigneReception(Input):
    ligne_id:UUID
    quantite:int=Field(strict=True,gt=0,le=1_000_000_000)
class ReceptionInput(Mutation):
    lignes:list[LigneReception]=Field(max_length=100)
    cloturer:bool=False
    justification:str | None=Field(default=None,min_length=1,max_length=2000)
class ZoneInput(Input):
    nom:str=Field(min_length=1,max_length=200)
    emplacement_id:UUID
    conditionnement_ids:list[UUID]=Field(default_factory=list,max_length=200)
class InventaireInput(Mutation):
    nom:str=Field(min_length=1,max_length=200)
    type:Literal['COMPLET','PARTIEL','TOURNANT']
    zones:list[ZoneInput]=Field(min_length=1,max_length=100)
class ParticipantInput(Mutation):utilisateur_id:UUID
class CompteInput(Mutation):
    quantite:int=Field(strict=True,ge=0,le=1_000_000_000)
    motif_id:UUID | None=None
    justification:str | None=Field(default=None,min_length=1,max_length=2000)
class MotifInput(Mutation):
    code:str=Field(min_length=1,max_length=80)
    nom:str=Field(min_length=1,max_length=200)


def service(request:Request,organisation_id:UUID,user=Depends(utilisateur_courant),session:Session=Depends(get_db_session)):
    def access(p,site,loc=None):
        if site!=request.state.stock_site:raise PermissionError('Site différent du contexte courant.')
        current=request.headers.get('X-Emplacement-ID')
        if loc and current and str(loc)!=current:raise PermissionError('Emplacement différent du contexte courant.')
        request.state.stock_controle.verifier(p,site,loc)
    return StockService(session,organisation_id,user.id_utilisateur,access,jour_courant())


def execute(action):
    try:return action()
    except PermissionError as exc:raise HTTPException(403,str(exc)) from exc
    except LookupError as exc:raise HTTPException(404,str(exc)) from exc
    except ConflitStock as exc:raise HTTPException(409,str(exc)) from exc
    except ValueError as exc:raise HTTPException(422,str(exc)) from exc
    except IntegrityError as exc:raise HTTPException(409,'Conflit de contrainte ou entité déjà enregistrée.') from exc


def mutate(s,data,kind,action):return execute(lambda:s.operation(data.cle,kind,data.model_dump(exclude={'cle'}),action))

def locations(s,permission,site):
    result=[]
    for row in s.s.scalars(select(EmplacementModel).where(EmplacementModel.site_id==site)):
        try:s.emplacement(row.id_emplacement,permission);result.append(row.id_emplacement)
        except PermissionError:pass
    return result

@router.get('/contextes')
def contextes(request:Request,s=Depends(service)):
    current=request.state.stock_site;perms=request.state.stock_permissions
    locs=set()
    for p in perms:locs.update(locations(s,p,current))
    destinations=select(EmplacementModel).join(SiteModel,SiteModel.id_site==EmplacementModel.site_id).where(SiteModel.organisation_id==s.org,EmplacementModel.actif.is_(True),SiteModel.actif.is_(True))
    # Seules les permissions du workflow transfert permettent le choix d'une destination intersite.
    if not any(p.startswith('stock.transfert') or p=='stock.transferer' for p in perms):destinations=destinations.where(EmplacementModel.id_emplacement.in_(locs))
    return {'site_id':current,'utilisateur_id':s.user,'emplacements':[{'id':str(x.id_emplacement),'nom':x.nom,'site_id':str(x.site_id)} for x in s.s.scalars(select(EmplacementModel).where(EmplacementModel.id_emplacement.in_(locs)))],'destinations':[{'id':str(x.id_emplacement),'nom':x.nom,'site_id':str(x.site_id)} for x in s.s.scalars(destinations)]}


@router.get('/stocks')
def stocks(request:Request,q:str=Query('',max_length=200),page:int=Query(1,ge=1),page_size:int=Query(25,ge=1,le=100),emplacement_id:UUID | None=None,conditionnement_id:UUID | None=None,s=Depends(service)):
    allowed=locations(s,'stock.consulter',request.state.stock_site)
    if emplacement_id:
        execute(lambda:s.emplacement(emplacement_id,'stock.consulter'));allowed=[emplacement_id]
    query=select(StockEmplacementModel).join(LotModel,LotModel.id==StockEmplacementModel.lot_id).join(ConditionnementModel,ConditionnementModel.id_conditionnement==LotModel.conditionnement_id).join(ProduitModel,ProduitModel.id_produit==ConditionnementModel.produit_id).where(StockEmplacementModel.organisation_id==s.org,StockEmplacementModel.emplacement_id.in_(allowed))
    if conditionnement_id:query=query.where(LotModel.conditionnement_id==conditionnement_id)
    if q:
        refs=select(ReferenceProduitModel.id_reference).where(ReferenceProduitModel.conditionnement_id==ConditionnementModel.id_conditionnement,ReferenceProduitModel.valeur.contains(q,autoescape=True)).exists()
        query=query.where(or_(func.upper(ProduitModel.nom).contains(q.upper(),autoescape=True),LotModel.numero.contains(q,autoescape=True),refs))
    total,rows=s.repo.paginer(query.order_by(ProduitModel.nom,StockEmplacementModel.id),page,page_size)
    result=[]
    for b in rows:
        lot=s.obtenir(LotModel,b.lot_id);pack,rules=s.conditionnement(lot.conditionnement_id,False);prod=s.s.get(ProduitModel,pack.produit_id);loc=s.s.get(EmplacementModel,b.emplacement_id)
        expired=bool(rules['gestion_peremption'] and (lot.peremption is None or lot.peremption<s.jour))
        result.append({**serial(b),'vendable':b.physique-b.reserve,'sortie_autorisee':not expired,'alerte':'PÉRIMÉ' if expired else 'RUPTURE' if b.physique==b.reserve else None,'produit':prod.nom,'conditionnement':pack.libelle,'conditionnement_id':str(pack.id_conditionnement),'emplacement':loc.nom,'lot':lot.numero,'peremption':str(lot.peremption) if lot.peremption else None})
    return {'items':result,'total':total,'page':page,'page_size':page_size}

@router.get('/lots')
def lots(conditionnement_id:UUID,page:int=Query(1,ge=1),page_size:int=Query(25,ge=1,le=100),s=Depends(service)):
    execute(lambda:s.conditionnement(conditionnement_id));total,rows=s.repo.paginer(select(LotModel).where(LotModel.organisation_id==s.org,LotModel.conditionnement_id==conditionnement_id).order_by(LotModel.peremption,LotModel.id),page,page_size)
    return {'items':[serial(x) for x in rows],'total':total}

@router.post('/lots',status_code=201)
def lot_creer(data:LotInput,s=Depends(service)):return mutate(s,data,'LOT',lambda:s.creer_lot(data.model_dump()))

@router.get('/mouvements')
def mouvements(request:Request,stock_id:UUID | None=None,page:int=Query(1,ge=1),page_size:int=Query(25,ge=1,le=100),s=Depends(service)):
    allowed=locations(s,'stock.consulter',request.state.stock_site)
    query=select(MouvementStockModel).join(StockEmplacementModel,StockEmplacementModel.id==MouvementStockModel.stock_id).where(MouvementStockModel.organisation_id==s.org,StockEmplacementModel.emplacement_id.in_(allowed))
    if stock_id:
        balance=execute(lambda:s.obtenir(StockEmplacementModel,stock_id));execute(lambda:s.emplacement(balance.emplacement_id,'stock.consulter'));query=query.where(MouvementStockModel.stock_id==stock_id)
    total,rows=s.repo.paginer(query.order_by(MouvementStockModel.sequence.desc()),page,page_size)
    result=[]
    for x in rows:
        b=s.obtenir(StockEmplacementModel,x.stock_id);lot=s.obtenir(LotModel,b.lot_id);pack=s.s.get(ConditionnementModel,lot.conditionnement_id);prod=s.s.get(ProduitModel,pack.produit_id);loc=s.s.get(EmplacementModel,b.emplacement_id);author=s.s.get(UtilisateurModel,x.auteur_id)
        result.append({**serial(x),'produit':prod.nom+' · '+pack.libelle,'lot':lot.numero,'emplacement':loc.nom,'auteur':author.nom})
    return {'items':result,'total':total}

@router.post('/mouvements',status_code=201)
def entree(data:MouvementInput,s=Depends(service)):
    execute(lambda:s.emplacement(data.emplacement_id,'stock.gerer'))
    return mutate(s,data,'MOUVEMENT',lambda:s.entree(data.model_dump()))

@router.post('/sorties',status_code=201)
def sortie(data:ReservationInput,s=Depends(service)):
    execute(lambda:s.emplacement(data.emplacement_id,'stock.gerer'));return mutate(s,data,'SORTIE',lambda:s.sortie(data.model_dump()))

@router.post('/reservations',status_code=201)
def reservation_creer(data:ReservationInput,s=Depends(service)):
    execute(lambda:s.emplacement(data.emplacement_id,'stock.reserver'));return mutate(s,data,'RESERVER',lambda:s.reserver(data.model_dump()))

@router.get('/reservations/{reservation_id}')
def reservation_lire(reservation_id:UUID,s=Depends(service)):return execute(lambda:s.reservation_detail(s.reservation_scope(reservation_id,'stock.reserver')))

@router.post('/reservations/{reservation_id}/liberer')
def reservation_liberer(reservation_id:UUID,data:Mutation,s=Depends(service)):
    execute(lambda:s.reservation_scope(reservation_id,'stock.reserver'));return mutate(s,data,'LIBERER:'+str(reservation_id),lambda:s.terminer_reservation(reservation_id))

@router.post('/reservations/{reservation_id}/consommer')
def reservation_consommer(reservation_id:UUID,data:Mutation,s=Depends(service)):
    execute(lambda:s.reservation_scope(reservation_id,'stock.reserver'));return mutate(s,data,'CONSOMMER:'+str(reservation_id),lambda:s.terminer_reservation(reservation_id,True))

@router.get('/transferts')
def transferts(request:Request,page:int=Query(1,ge=1),page_size:int=Query(25,ge=1,le=100),s=Depends(service)):
    allowed=set()
    for p in request.state.stock_permissions:allowed.update(locations(s,p,request.state.stock_site))
    query=select(DemandeTransfertModel).where(DemandeTransfertModel.organisation_id==s.org,or_(DemandeTransfertModel.source_id.in_(allowed),DemandeTransfertModel.destination_id.in_(allowed)))
    total,rows=s.repo.paginer(query.order_by(DemandeTransfertModel.date.desc(),DemandeTransfertModel.id),page,page_size)
    return {'items':[serial(x) for x in rows],'total':total}

@router.get('/transferts/{demande_id}')
def transfert_lire(demande_id:UUID,request:Request,s=Depends(service)):
    def action():
        d=s.obtenir(DemandeTransfertModel,demande_id)
        for p in request.state.stock_permissions:
            for dest in (False,True):
                try:s.demande_scope(d.id,p,dest);return s.transfert_detail(d)
                except PermissionError:pass
        raise PermissionError('Transfert hors périmètre affecté.')
    return execute(action)

@router.post('/transferts',status_code=201)
def demande_creer(data:DemandeInput,s=Depends(service)):
    execute(lambda:s.emplacement(data.source_id,'stock.transferer'));return mutate(s,data,'DEMANDE',lambda:s.creer_demande(data.model_dump()))

@router.post('/transferts-internes',status_code=201)
def interne(data:DemandeInput,s=Depends(service)):
    for key in (data.source_id,data.destination_id):execute(lambda:s.emplacement(key,'stock.transferer'))
    return mutate(s,data,'INTERNE',lambda:s.transfert_interne(data.model_dump()))

@router.post('/transferts/{demande_id}/valider')
def demande_valider(demande_id:UUID,data:Mutation,s=Depends(service)):
    execute(lambda:s.demande_scope(demande_id,'stock.transfert.valider'));return mutate(s,data,'VALIDER:'+str(demande_id),lambda:s.valider_demande(demande_id))

@router.post('/transferts/{demande_id}/expedier')
def demande_expedier(demande_id:UUID,data:Mutation,s=Depends(service)):
    execute(lambda:s.demande_scope(demande_id,'stock.transferer'));return mutate(s,data,'EXPEDIER:'+str(demande_id),lambda:s.expedier(demande_id))

@router.post('/transferts/{demande_id}/annuler')
def demande_annuler(demande_id:UUID,data:Justifie,s=Depends(service)):
    execute(lambda:s.demande_scope(demande_id,'stock.transfert.valider'))
    def action():
        d=s.demande_scope(demande_id,'stock.transfert.valider')
        if d.statut not in ('DEMANDEE','VALIDEE'):raise ConflitStock('Annulation interdite après expédition.')
        t=s.s.scalar(select(TransfertStockModel).where(TransfertStockModel.demande_id==d.id))
        if t:s.terminer_reservation(t.reservation_id,False,permission='stock.transfert.valider',interne=True)
        d.statut='ANNULEE';d.justification+='\nAnnulation : '+data.justification;s.s.flush();return s.transfert_detail(d)
    return mutate(s,data,'ANNULER:'+str(demande_id),action)

@router.post('/transferts/{demande_id}/recevoir')
def demande_recevoir(demande_id:UUID,data:ReceptionInput,s=Depends(service)):
    execute(lambda:s.demande_scope(demande_id,'stock.transfert.recevoir',True));return mutate(s,data,'RECEVOIR:'+str(demande_id),lambda:s.recevoir(demande_id,data.model_dump()))

@router.get('/inventaires')
def inventaires(request:Request,page:int=Query(1,ge=1),page_size:int=Query(25,ge=1,le=100),s=Depends(service)):
    query=select(InventaireModel).where(InventaireModel.organisation_id==s.org,InventaireModel.site_id==request.state.stock_site)
    if request.state.stock_permissions==['stock.inventaire.compter']:
        query=query.where(select(ParticipantZoneInventaireModel.id).join(ZoneInventaireModel,ZoneInventaireModel.id==ParticipantZoneInventaireModel.zone_id).where(ZoneInventaireModel.inventaire_id==InventaireModel.id,ParticipantZoneInventaireModel.utilisateur_id==s.user).exists())
    allowed=set()
    for p in request.state.stock_permissions:allowed.update(locations(s,p,request.state.stock_site))
    query=query.where(select(ZoneInventaireModel.id).where(ZoneInventaireModel.inventaire_id==InventaireModel.id,ZoneInventaireModel.emplacement_id.in_(allowed)).exists())
    total,rows=s.repo.paginer(query.order_by(InventaireModel.date.desc(),InventaireModel.id),page,page_size)
    return {'items':[serial(x) for x in rows],'total':total}

@router.post('/inventaires',status_code=201)
def inventaire_creer(data:InventaireInput,request:Request,s=Depends(service)):
    for z in data.zones:execute(lambda:s.emplacement(z.emplacement_id,'stock.inventaire.gerer'))
    return mutate(s,data,'INVENTAIRE',lambda:s.creer_inventaire(data.model_dump(),request.state.stock_site))

@router.get('/inventaires/{inventaire_id}')
def inventaire_lire(inventaire_id:UUID,request:Request,zone_id:UUID | None=None,page:int=Query(1,ge=1),page_size:int=Query(25,ge=1,le=100),s=Depends(service)):
    def action():
        inv=s.obtenir(InventaireModel,inventaire_id)
        if inv.site_id!=request.state.stock_site:raise PermissionError('Inventaire d’un autre site.')
        reveal='stock.inventaire.valider' in request.state.stock_permissions;manage='stock.inventaire.gerer' in request.state.stock_permissions
        if zone_id:
            zone=s.obtenir(ZoneInventaireModel,zone_id)
            if zone.inventaire_id!=inv.id:raise PermissionError('Zone d’un autre inventaire.')
        result=s.inventaire_detail(inv,reveal,manage,zone_id,page,page_size)
        if not result['zones']:raise PermissionError('Aucune zone affectée accessible.')
        return result
    return execute(action)

@router.post('/zones/{zone_id}/participants',status_code=201)
def participant_creer(zone_id:UUID,data:ParticipantInput,s=Depends(service)):
    execute(lambda:s.emplacement(s.obtenir(ZoneInventaireModel,zone_id).emplacement_id,'stock.inventaire.gerer'))
    def action():
        user=s.s.get(UtilisateurModel,data.utilisateur_id);z=s.obtenir(ZoneInventaireModel,zone_id);loc=s.emplacement(z.emplacement_id,None)
        if not user or user.organisation_id!=s.org:raise PermissionError('Participant d’une autre organisation.')
        ControleAcces(SqlAlchemySecuriteRepository(s.s),user,s.jour).verifier('stock.inventaire.compter',loc.site_id,loc.id_emplacement)
        return s.participant(zone_id,data.utilisateur_id)
    return mutate(s,data,'PARTICIPANT:'+str(zone_id),action)

@router.post('/lignes-inventaire/{ligne_id}/comptages',status_code=201)
def comptage(ligne_id:UUID,data:CompteInput,s=Depends(service)):
    line=execute(lambda:s.obtenir(LigneInventaireModel,ligne_id));execute(lambda:s.emplacement(s.obtenir(ZoneInventaireModel,line.zone_id).emplacement_id,'stock.inventaire.compter'))
    return mutate(s,data,'COMPTER:'+str(ligne_id),lambda:s.compter(ligne_id,data.model_dump()))

@router.post('/inventaires/{inventaire_id}/valider')
def inventaire_valider(inventaire_id:UUID,data:Mutation,s=Depends(service)):
    execute(lambda:s.inventaire_scope(inventaire_id,'stock.inventaire.valider'));return mutate(s,data,'INVENTAIRE_VALIDER:'+str(inventaire_id),lambda:s.valider_inventaire(inventaire_id))

@router.post('/inventaires/{inventaire_id}/annuler')
def inventaire_annuler(inventaire_id:UUID,data:Justifie,s=Depends(service)):
    execute(lambda:s.inventaire_scope(inventaire_id,'stock.inventaire.gerer'))
    def action():
        inv=s.inventaire_scope(inventaire_id,'stock.inventaire.gerer')
        if inv.statut!='OUVERT':raise ConflitStock('Inventaire déjà clôturé.')
        inv.statut='ANNULE';s.s.flush();return s.inventaire_detail(inv,manage=True)
    return mutate(s,data,'ANNULER_INVENTAIRE:'+str(inventaire_id),action)

@router.get('/motifs')
def motifs(s=Depends(service)):return [serial(x) for x in s.lignes(MotifEcartInventaireModel)]

@router.post('/motifs',status_code=201)
def motif_creer(data:MotifInput,s=Depends(service)):return mutate(s,data,'MOTIF',lambda:serial(s.ajouter(MotifEcartInventaireModel,code=texte(data.code,80),nom=texte(data.nom,200))))

POLICY.update({'conditionnements':POLICY['contextes'],'reservations':('stock.reserver',),'participants_disponibles':('stock.inventaire.gerer',)})

@router.get('/conditionnements')
def conditionnements(q:str=Query('',max_length=200),page:int=Query(1,ge=1),page_size:int=Query(20,ge=1,le=100),s=Depends(service)):
    query=select(ConditionnementModel).join(ProduitModel,ProduitModel.id_produit==ConditionnementModel.produit_id).where(ConditionnementModel.organisation_id==s.org,ConditionnementModel.actif.is_(True),ProduitModel.actif.is_(True))
    if q:
        refs=select(ReferenceProduitModel.id_reference).where(ReferenceProduitModel.conditionnement_id==ConditionnementModel.id_conditionnement,ReferenceProduitModel.valeur.contains(q,autoescape=True)).exists()
        query=query.where(or_(func.upper(ProduitModel.nom).contains(q.upper(),autoescape=True),refs))
    total,rows=s.repo.paginer(query.order_by(ProduitModel.nom,ConditionnementModel.id_conditionnement),page,page_size)
    return {'items':[{'id':str(x.id_conditionnement),'nom':s.s.get(ProduitModel,x.produit_id).nom+' · '+x.libelle} for x in rows],'total':total}

@router.get('/reservations')
def reservations(request:Request,statut:str | None=None,page:int=Query(1,ge=1),page_size:int=Query(25,ge=1,le=100),s=Depends(service)):
    allowed=locations(s,'stock.reserver',request.state.stock_site)
    query=select(ReservationStockModel).where(ReservationStockModel.organisation_id==s.org,select(AllocationReservationModel.id).join(StockEmplacementModel,StockEmplacementModel.id==AllocationReservationModel.stock_id).where(AllocationReservationModel.reservation_id==ReservationStockModel.id,StockEmplacementModel.emplacement_id.in_(allowed)).exists())
    if statut:query=query.where(ReservationStockModel.statut==statut)
    total,rows=s.repo.paginer(query.order_by(ReservationStockModel.cree_le.desc(),ReservationStockModel.id),page,page_size)
    return {'items':[s.reservation_detail(x) for x in rows],'total':total}

@router.get('/participants-disponibles')
def participants_disponibles(emplacement_id:UUID,q:str=Query('',max_length=200),page:int=Query(1,ge=1),page_size:int=Query(25,ge=1,le=100),s=Depends(service)):
    loc=execute(lambda:s.emplacement(emplacement_id,'stock.inventaire.gerer'))
    # Pagination SQL sur utilisateurs possédant une affectation Site/Role/Permission effective.
    from neosys_pharma.infrastructure.securite_models import AffectationSiteModel,AffectationEmplacementModel,AffectationRoleModel,RoleModel,RolePermissionModel,PermissionModel
    ids=select(AffectationSiteModel.utilisateur_id).join(AffectationEmplacementModel,AffectationEmplacementModel.affectation_site_id==AffectationSiteModel.id_affectation_site).join(AffectationRoleModel,AffectationRoleModel.affectation_site_id==AffectationSiteModel.id_affectation_site).join(RoleModel,RoleModel.id_role==AffectationRoleModel.role_id).join(RolePermissionModel,RolePermissionModel.role_id==RoleModel.id_role).join(PermissionModel,PermissionModel.id_permission==RolePermissionModel.permission_id).where(AffectationSiteModel.site_id==loc.site_id,AffectationEmplacementModel.emplacement_id==loc.id_emplacement,AffectationSiteModel.actif.is_(True),AffectationSiteModel.date_debut<=s.jour,or_(AffectationSiteModel.date_fin.is_(None),AffectationSiteModel.date_fin>=s.jour),RoleModel.actif.is_(True),PermissionModel.code=='stock.inventaire.compter')
    query=select(UtilisateurModel).where(UtilisateurModel.organisation_id==s.org,UtilisateurModel.actif.is_(True),UtilisateurModel.id_utilisateur.in_(ids))
    if q:query=query.where(or_(UtilisateurModel.nom.contains(q,autoescape=True),UtilisateurModel.identifiant.contains(q,autoescape=True)))
    total,rows=s.repo.paginer(query.order_by(UtilisateurModel.nom,UtilisateurModel.id_utilisateur),page,page_size)
    return {'items':[{'id':str(x.id_utilisateur),'nom':x.nom+' · '+x.identifiant} for x in rows],'total':total}
