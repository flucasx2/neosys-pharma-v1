"""P4.5 HTTP : refus par défaut, même transaction/idempotence et protection CSRF P1."""
from uuid import UUID
from neosys_pharma.domain.stock import ConflitStock
from decimal import Decimal
from typing import Literal
from fastapi import APIRouter,Depends,Request,Query,Response,HTTPException
from pydantic import Field
from sqlalchemy import select
from neosys_pharma.presentation.vente_api import POLICY,contexte,Mutation,Revision,Input
from neosys_pharma.presentation.caisse_api import service as cash_service,Mode,locations,page
from neosys_pharma.presentation.stock_api import execute
from neosys_pharma.application.regularisation_service import RegularisationService
from neosys_pharma.application.caisse_service import serial
from neosys_pharma.infrastructure.regularisation_models import *
from neosys_pharma.infrastructure.caisse_models import SessionCaisseModel,PeriodeCaisseSiteModel,ConfirmationReglementModel,EncaissementModel,ReglementModel,EvenementCaisseModel
from neosys_pharma.infrastructure.organisation_models import CoffreModel,EmplacementModel
from neosys_pharma.infrastructure.stock_models import StockEmplacementModel,LotModel
from neosys_pharma.infrastructure.vente_models import VenteModel,ReservationVenteModel,LigneVenteModel
from neosys_pharma.infrastructure.stock_models import AllocationReservationModel,ReservationStockModel
POLICY.update({'finance_contexte':('caisse.cloture.consulter','caisse.cloture.z','caisse.cloture.x','caisse.fonds.gerer','caisse.ecart.reconnaitre','caisse.transfert.demander','caisse.transfert.autoriser','caisse.transfert.expedier','caisse.transfert.recevoir','caisse.remboursement.demander','caisse.remboursement.autoriser','caisse.remboursement.executer'),
 'finance_ventes':('vente.retour.gerer','caisse.cloture.consulter'),'finance_solde':'caisse.remboursement.demander','finance_liste':'caisse.cloture.consulter','finance_fonds':'caisse.fonds.gerer','finance_transfert':'caisse.transfert.demander','finance_transfert_action':('caisse.transfert.autoriser','caisse.transfert.expedier','caisse.transfert.recevoir'),
 'finance_x':'caisse.cloture.x','finance_z':'caisse.cloture.z','finance_ecart':'caisse.ecart.reconnaitre','finance_retour':'vente.retour.gerer','finance_retournable':'vente.retour.gerer','finance_remboursement':'caisse.remboursement.demander','finance_refund_action':('caisse.remboursement.autoriser','caisse.remboursement.executer'),
 'finance_quarantaine':'stock.quarantaine.consulter','finance_controle':'stock.quarantaine.decider','finance_pdf':'caisse.cloture.consulter','finance_pending':'caisse.cloture.consulter'})
router=APIRouter(prefix='/api/regularisations/organisations/{organisation_id}',tags=['Clôtures, fonds et retours'],dependencies=[Depends(contexte)])
def service(c=Depends(cash_service)):return RegularisationService(c)
def mutation(s,d,kind,action):return execute(lambda:s.stock.operation(d.cle,'P4.5:'+kind,d.model_dump(mode='json',exclude={'cle'}),action))
class Motif(Revision):justification:str=Field(min_length=1,max_length=2000)
class Fonds(Motif):
    session_id:UUID
    sens:Literal['ENTREE','SORTIE']
    montant:Decimal=Field(gt=0,max_digits=18,decimal_places=0)
class Transfert(Motif):
    session_id:UUID
    coffre_id:UUID
    sens:Literal['CAISSE_COFFRE','COFFRE_CAISSE']
    montant:Decimal=Field(gt=0,max_digits=18,decimal_places=0)
class X(Revision):session_id:UUID
class Z(Mutation):
    periode_id:UUID
    justification:str=Field(min_length=1,max_length=2000)
class LigneRetour(Input):
    ligne_id:UUID
    stock_id:UUID
    quantite:int=Field(strict=True,gt=0,le=1_000_000_000)
class Retour(Mutation):
    encaissement_id:UUID
    lignes:list[LigneRetour]=Field(min_length=1,max_length=1000)
    justification:str=Field(min_length=1,max_length=2000)
class Controle(Mutation):
    liberer:bool
    identite_conforme:bool
    lot_conforme:bool
    integrite_conforme:bool
    conservation_conforme:bool
    justification:str=Field(min_length=1,max_length=2000)
class ReglementRetour(Input):
    moyen_id:UUID|None=None
    moyen_origine_id:UUID|None=None
    mode:Mode
    mode_origine:Mode|None=None
    montant:Decimal=Field(gt=0,max_digits=18,decimal_places=0)
class Remboursement(Motif):
    session_id:UUID
    retour_id:UUID|None=None
    confirmation_id:UUID|None=None
    remplace_id:UUID|None=None
    reglements:list[ReglementRetour]=Field(min_length=1,max_length=20)
class Preuve(Input):
    reference:str|None=Field(default=None,max_length=200)
    preuve:str|None=Field(default=None,max_length=2000)
class Execution(Motif):preuves:list[Preuve]=Field(default_factory=list,max_length=20)
class Annulation(Motif):
    attestation_absence_restitution:bool=Field(strict=True)
    restitution_externe_incertaine:bool=Field(strict=True)

POLICY['finance_annulation']='caisse.remboursement.annuler'
POLICY['finance_contexte']+=('caisse.remboursement.annuler',)
POLICY['finance_liste']={genre:('caisse.cloture.consulter','vente.retour.gerer') if genre=='retours' else
    ('caisse.cloture.consulter','caisse.remboursement.annuler') if genre=='remboursements' else 'caisse.cloture.consulter'
    for genre in ('clotures','transferts','retours','remboursements','mouvements')}
POLICY['finance_pdf']={genre:('vente.retour.gerer','caisse.cloture.consulter') if genre=='retours' else 'caisse.cloture.consulter'
    for genre in ('clotures','remboursements','transferts','retours')}

@router.get('/contexte')
def finance_contexte(request:Request,s=Depends(service)):
    p=request.state.vente_permission;ids=locations(s.cash,p)
    period=s.s.scalar(select(PeriodeCaisseSiteModel).filter_by(organisation_id=s.org,site_id=s.site,etat='OUVERTE'))
    return {'periode':serial(period) if period else None,'sessions':[s.cash.session_detail(x) for x in s.stock.lignes(SessionCaisseModel,site_id=s.site) if x.emplacement_id in ids],'coffres':[{'id':str(x.id_coffre),'nom':x.nom,'solde':str(s.solde_coffre(x.id_coffre))} for x in s.s.scalars(select(CoffreModel).where(CoffreModel.site_id==s.site,CoffreModel.actif.is_(True)))],'modes':s.cash.config()['modes'],'moyens':s.cash.config()['moyens']}
@router.get('/{genre}')
def finance_liste(request:Request,genre:Literal['clotures','transferts','retours','remboursements','mouvements'],page_:int=Query(1,alias='page',ge=1),page_size:int=Query(20,ge=1,le=100),s=Depends(service)):
    cls={'clotures':ClotureModel,'transferts':TransfertFondsModel,'retours':RetourVenteModel,'remboursements':RemboursementModel,'mouvements':MouvementFinancierModel}[genre]
    q=select(cls).where(cls.organisation_id==s.org,cls.site_id==s.site)
    permission=request.state.vente_permission
    if permission=='vente.retour.gerer' and genre!='retours':raise HTTPException(403,'Consultation financière non autorisée.')
    if permission=='caisse.remboursement.annuler' and genre!='remboursements':raise HTTPException(403,'Consultation limitée aux demandes de remboursement.')
    ids=locations(s.cash,permission);sessions=select(SessionCaisseModel.id).where(SessionCaisseModel.organisation_id==s.org,SessionCaisseModel.emplacement_id.in_(ids))
    if genre=='retours':q=q.join(EncaissementModel,EncaissementModel.id==RetourVenteModel.encaissement_id).join(VenteModel,VenteModel.id==EncaissementModel.vente_id).where(VenteModel.emplacement_id.in_(ids))
    elif genre=='clotures':q=q.where((cls.type=='Z')|(cls.session_id.in_(sessions)))
    elif genre=='mouvements':q=q.where(cls.session_id.is_(None)|cls.session_id.in_(sessions))
    else:q=q.where(cls.session_id.in_(sessions))
    def item(row):
        result=serial(row)
        if genre=='retours':result['document_disponible']=bool(s.stock.lignes(DocumentRetourModel,retour_id=row.id))
        if genre=='remboursements':result['annulations']=[serial(x) for x in s.stock.lignes(AnnulationRemboursementModel,remboursement_id=row.id)]
        return result
    return page(s.cash,q.order_by(cls.date.desc(),cls.id),page_,page_size,item)
@router.post('/fonds',status_code=201)
def finance_fonds(d:Fonds,s=Depends(service)):
    execute(lambda:s.cash.session(d.session_id,'caisse.fonds.gerer'));return mutation(s,d,'FONDS',lambda:s.fonds(d.model_dump()))
@router.post('/transferts',status_code=201)
def finance_transfert(d:Transfert,s=Depends(service)):
    execute(lambda:s.cash.session(d.session_id,'caisse.transfert.demander'));return mutation(s,d,'TRANSFERT',lambda:s.transfert(d.model_dump()))
@router.post('/transferts/{key}/{action}')
def finance_transfert_action(key:UUID,action:Literal['autoriser','expedier','recevoir','annuler'],d:Motif,s=Depends(service)):
    p={'autoriser':'caisse.transfert.autoriser','annuler':'caisse.transfert.autoriser','expedier':'caisse.transfert.expedier','recevoir':'caisse.transfert.recevoir'}[action]
    execute(lambda:s.dossier(TransfertFondsModel,key,p));return mutation(s,d,'TRANSFERT:'+str(key)+':'+action,lambda:s.transfert_action(key,d.model_dump(),action))
@router.post('/clotures/x',status_code=201)
def finance_x(d:X,s=Depends(service)):
    execute(lambda:s.cash.session(d.session_id,'caisse.cloture.x'));return mutation(s,d,'X',lambda:s.cloture_x(d.model_dump()))
@router.post('/clotures/z',status_code=201)
def finance_z(d:Z,s=Depends(service)):
    execute(lambda:s.access('caisse.cloture.z'));return mutation(s,d,'Z',lambda:s.cloture_z(d.model_dump()))
@router.post('/sessions/{key}/ecart',status_code=201)
def finance_ecart(key:UUID,d:Motif,s=Depends(service)):
    execute(lambda:s.cash.session(key,'caisse.ecart.reconnaitre'));return mutation(s,d,'ECART:'+str(key),lambda:s.ecart(key,d.model_dump()))
@router.get('/recus/{key}/retournable')
def finance_retournable(key:UUID,s=Depends(service)):
    def get():
        enc=s.stock.obtenir(EncaissementModel,key);v=s.vente.obtenir(enc.vente_id,'vente.retour.gerer');result=[]
        for line in s.vente.lignes(v):
            if not line.actif:continue
            for link in s.stock.lignes(ReservationVenteModel,ligne_id=line.id):
                if s.stock.obtenir(ReservationStockModel,link.reservation_id).statut!='CONSOMMEE':continue
                for alloc in s.stock.lignes(AllocationReservationModel,reservation_id=link.reservation_id):
                    b=s.stock.obtenir(StockEmplacementModel,alloc.stock_id);lot=s.stock.obtenir(LotModel,b.lot_id)
                    used=sum(x.quantite for x in s.stock.lignes(LigneRetourVenteModel,ligne_id=line.id,stock_id=b.id))
                    result.append({'ligne_id':str(line.id),'stock_id':str(b.id),'designation':line.designation,'conditionnement':line.conditionnement,'lot':lot.numero,'peremption':str(lot.peremption) if lot.peremption else None,'quantite_restante':alloc.quantite-used})
        return {'encaissement':serial(enc),'lignes':result}
    return execute(get)
@router.post('/retours',status_code=201)
def finance_retour(d:Retour,s=Depends(service)):
    enc=execute(lambda:s.stock.obtenir(EncaissementModel,d.encaissement_id));execute(lambda:s.vente.obtenir(enc.vente_id,'vente.retour.gerer'));return mutation(s,d,'RETOUR',lambda:s.retour(d.model_dump()))
@router.get('/stock/quarantaine')
def finance_quarantaine(page_:int=Query(1,alias='page',ge=1),page_size:int=Query(20,ge=1,le=100),s=Depends(service)):
    ids=locations(s.cash,'stock.quarantaine.consulter');q=select(QuarantaineModel).join(StockEmplacementModel,StockEmplacementModel.id==QuarantaineModel.stock_id).where(QuarantaineModel.organisation_id==s.org,StockEmplacementModel.site_id==s.site,StockEmplacementModel.emplacement_id.in_(ids)).order_by(QuarantaineModel.id)
    def item(row):
        line=s.stock.obtenir(LigneRetourVenteModel,row.ligne_retour_id);b=s.stock.obtenir(StockEmplacementModel,row.stock_id);lot=s.stock.obtenir(LotModel,b.lot_id)
        return serial(row)|{'designation':line.instantane['designation'],'conditionnement':line.instantane['conditionnement'],'emplacement_id':str(b.emplacement_id),'lot':lot.numero,'peremption':str(lot.peremption) if lot.peremption else None,'presence_physique':row.quantite if row.etat!='LIBEREE' else 0,'vendable':0}
    return page(s.cash,q,page_,page_size,item)
@router.post('/stock/quarantaine/{key}/decision')
def finance_controle(key:UUID,d:Controle,s=Depends(service)):
    q=execute(lambda:s.stock.obtenir(QuarantaineModel,key));b=execute(lambda:s.stock.obtenir(StockEmplacementModel,q.stock_id));execute(lambda:s.stock.emplacement(b.emplacement_id,'stock.quarantaine.decider'));return mutation(s,d,'QUALITE:'+str(key),lambda:s.controle(key,d.model_dump()))
@router.post('/remboursements',status_code=201)
def finance_remboursement(d:Remboursement,s=Depends(service)):
    execute(lambda:s.cash.session(d.session_id,'caisse.remboursement.demander'))
    if d.retour_id:execute(lambda:s.retour_scope(d.retour_id,'caisse.remboursement.demander'))
    if d.confirmation_id:
        c=execute(lambda:s.stock.obtenir(ConfirmationReglementModel,d.confirmation_id));execute(lambda:s.vente.obtenir(c.vente_id,'caisse.remboursement.demander'))
    return mutation(s,d,'REMBOURSEMENT',lambda:s.remboursement(d.model_dump()))
@router.post('/remboursements/{key}/annuler')
def finance_annulation(key:UUID,d:Annulation,s=Depends(service)):
    execute(lambda:s.refund_scope(key,'caisse.remboursement.annuler'))
    return mutation(s,d,'REMBOURSEMENT:'+str(key)+':annuler',lambda:s.annuler_remboursement(key,d.model_dump()))
@router.post('/remboursements/{key}/{action}')
def finance_refund_action(key:UUID,action:Literal['autoriser','executer'],d:Execution,s=Depends(service)):
    execute(lambda:s.refund_scope(key,'caisse.remboursement.'+action));return mutation(s,d,'REMBOURSEMENT:'+str(key)+':'+action,lambda:s.refund_action(key,d.model_dump(),action))
@router.get('/documents/{genre}/{key}/pdf')
def finance_pdf(request:Request,genre:Literal['clotures','remboursements','transferts','retours'],key:UUID,s=Depends(service)):
    def get():
        if genre=='retours':
            s.retour_scope(key,request.state.vente_permission)
            rows=s.stock.lignes(DocumentRetourModel,retour_id=key)
            if not rows:raise ConflitStock('Retour historique sans pièce : aucun document créé à la consultation.')
            row=rows[0]
            return Response(row.pdf,media_type='application/pdf',headers={'Content-Disposition':f'inline; filename="retour-{key}.pdf"','ETag':'"'+row.pdf_sha256+'"'})
        s.access('caisse.cloture.consulter')
        if genre=='clotures':
            row=s.stock.obtenir(ClotureModel,key)
            if row.site_id!=s.site:raise PermissionError('Document hors site.')
            if row.session_id:s.cash.session(row.session_id,'caisse.cloture.consulter')
        elif genre=='transferts':
            import base64
            s.dossier(TransfertFondsModel,key,'caisse.cloture.consulter')
            events=s.stock.lignes(EvenementCaisseModel,type='P4.5:TRANSFERT_RECEVOIR')
            document=next((e.donnees.get('document') for e in events if e.donnees.get('dossier',{}).get('id')==str(key)),None)
            if not document:raise ConflitStock('Justificatif disponible après réception confirmée.')
            return Response(base64.b64decode(document['pdf_base64']),media_type='application/pdf',headers={'Content-Disposition':f'inline; filename="transfert-{key}.pdf"'})
        else:
            s.refund_scope(key,'caisse.cloture.consulter');rows=s.stock.lignes(PieceFinanciereModel,remboursement_id=key)
            if not rows:raise ConflitStock('Document disponible après remboursement confirmé.')
            row=rows[0]
        return Response(row.pdf,media_type='application/pdf',headers={'Content-Disposition':f'inline; filename="{genre}-{key}.pdf"'})
    return execute(get)
@router.get('/paiements/non-finalises')
def finance_pending(s=Depends(service)):
    def get():
        ids=locations(s.cash,'caisse.cloture.consulter');result=[]
        for c in s.unresolved():
            if s.stock.obtenir(VenteModel,c.vente_id).emplacement_id not in ids:continue
            previous=s.stock.lignes(RemboursementModel,confirmation_id=c.id)
            latest=next((old for old in previous if old.etat=='ANNULE' and not any(other.remplace_id==old.id for other in previous)),None)
            result.append(serial(c)|{'remplace_id':str(latest.id) if latest else None})
        return result
    return execute(get)

@router.get('/ventes/encaisses')
def finance_ventes(request:Request,q:str=Query('',max_length=200),page_:int=Query(1,alias='page',ge=1),page_size:int=Query(20,ge=1,le=100),s=Depends(service)):
    ids=locations(s.cash,request.state.vente_permission)
    query=select(EncaissementModel).join(VenteModel,VenteModel.id==EncaissementModel.vente_id).where(EncaissementModel.organisation_id==s.org,VenteModel.site_id==s.site,VenteModel.emplacement_id.in_(ids))
    if q:
        query=query.where(VenteModel.id.in_(select(LigneVenteModel.vente_id).where(LigneVenteModel.organisation_id==s.org,s.stock.repo.upper(LigneVenteModel.designation).contains(s.stock.repo.terme(q),autoescape=True))))
    return page(s.cash,query.order_by(EncaissementModel.date.desc(),EncaissementModel.id),page_,page_size)
@router.get('/retours/{key}/solde')
def finance_solde(key:UUID,s=Depends(service)):
    ret,enc=execute(lambda:s.retour_scope(key,'caisse.remboursement.demander'))
    paid=execute(lambda:s.budget_reglements(enc))
    modes={mode:str(sum((row['montant'] for row in paid.values() if row['mode']==mode),Decimal(0))) for mode in ('ESPECES','CARTE','MOBILE_MONEY','CHEQUE','VIREMENT')}
    previous=s.stock.lignes(RemboursementModel,retour_id=ret.id)
    latest=next((old for old in previous if old.etat=='ANNULE' and not any(other.remplace_id==old.id for other in previous)),None)
    return {'montant':str(ret.montant),'disponible_par_mode':modes,'disponible_par_moyen':[{**row,'montant':str(row['montant'])} for row in paid.values()],'deja_demande':any(row.etat!='ANNULE' for row in previous),'remplace_id':str(latest.id) if latest else None}
