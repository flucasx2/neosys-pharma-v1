"""C06 : projection/PDF X/Z, sans modification des écritures ni des soldes."""
from decimal import Decimal
from io import BytesIO
from uuid import UUID,uuid4
from types import SimpleNamespace
from datetime import datetime,timezone
import pytest
from pypdf import PdfReader
from sqlalchemy import select,func
from test_regularisation import raw_client,account,setup45,final,ret,current,close,post,root,db
from test_p405_regressions import finish_refund
from neosys_pharma.infrastructure.caisse_models import MouvementCaisseModel,ReglementModel,MouvementCaisseGroupeModel,ReglementGroupeModel
from neosys_pharma.infrastructure.regularisation_models import MouvementFinancierModel,RetourVenteModel,TransfertFondsModel
from neosys_pharma.infrastructure.stock_models import MouvementStockModel
from neosys_pharma.application.etats_caisse_presentation import detail_flux


def financial_counts(c):
    gen=db(c);s=next(gen)
    try:return {cls.__tablename__:s.scalar(select(func.count()).select_from(cls)) for cls in (MouvementCaisseModel,MouvementCaisseGroupeModel,MouvementFinancierModel,MouvementStockModel)}
    finally:gen.close()


def test_x_brut_rendu_nets_fonds_transit_et_demande_non_executee(raw_client,account):
    c,a=raw_client,account;sale,session,*rest=setup45(c,a);coffre=rest[-1]
    receipt=final(c,a,sale,session)
    for sense,amount in [('ENTREE',100),('SORTIE',40)]:
        post(c,a,'/fonds',{'session_id':session['id'],'revision':current(c,a,session)['revision'],'sens':sense,'montant':amount,'justification':'Fonds fictifs C06'})
    transfer=post(c,a,'/transferts',{'session_id':session['id'],'revision':current(c,a,session)['revision'],'coffre_id':coffre,'sens':'CAISSE_COFFRE','montant':100,'justification':'Transit fictif C06'})
    transfer=post(c,a,f'/transferts/{transfer["id"]}/autoriser',{'revision':transfer['revision'],'justification':'Accord fictif'},200)
    post(c,a,f'/transferts/{transfer["id"]}/expedier',{'revision':transfer['revision'],'justification':'Dérogation responsable fictive'},200)
    returned=ret(c,a,receipt,1)
    post(c,a,'/remboursements',{'retour_id':returned['id'],'session_id':session['id'],'revision':current(c,a,session)['revision'],'reglements':[{'mode':'ESPECES','montant':100}],'justification':'Demande non exécutée'})
    before=current(c,a,session);counts=financial_counts(c);assert before['especes_attendues']=='1261'
    key=uuid4();payload={'session_id':session['id'],'revision':before['revision']}
    x=post(c,a,'/clotures/x',payload,key=key);d=x['instantane']['detail_flux']
    assert d['totaux']=={'brut_recu':'400','rendu':'99','net_regle':'301','remboursements_executes':'0','fonds_entrees':'100','fonds_sorties':'40'}
    assert len(d['encaissements'])==1 and d['encaissements'][0]['source']=='INDIVIDUEL'
    assert d['remboursements']==[] and len(d['retours_information'])==1
    assert d['transferts'][0]['etat']=='EN_TRANSIT'
    assert [(m['cible'],m['montant_signe']) for m in d['transferts'][0]['ecritures']]==[('CAISSE','-100')]
    assert x['instantane']['session']=={**before,'nets_par_mode':x['instantane']['session']['nets_par_mode'],'nets_par_moyen':x['instantane']['session']['nets_par_moyen']}
    assert post(c,a,'/clotures/x',payload,key=key)==x
    assert current(c,a,session)==before and financial_counts(c)==counts
    pdf=c.get(root(a)+f'/documents/clotures/{x["id"]}/pdf').content
    text=' '.join(p.extract_text() for p in PdfReader(BytesIO(pdf)).pages)
    assert 'Brut reçu' in text and 'Rendu monnaie' in text and 'EN_TRANSIT' in text and '1261' in text


def test_z_refund_execute_comptage_ecart_et_x_immuable(raw_client,account):
    c,a=raw_client,account;sale,session,*_=setup45(c,a);receipt=final(c,a,sale,session)
    x=post(c,a,'/clotures/x',{'session_id':session['id'],'revision':current(c,a,session)['revision']})
    pdfpath=root(a)+f'/documents/clotures/{x["id"]}/pdf';original=c.get(pdfpath).content
    returned=ret(c,a,receipt,3);finish_refund(c,a,session,returned,[{'mode':'ESPECES','montant':301}])
    close(c,a,session,1005)
    post(c,a,f'/sessions/{session["id"]}/ecart',{'revision':current(c,a,session)['revision'],'justification':'Écart physique fictif accepté'})
    counts=financial_counts(c);before=current(c,a,session);period=c.get(root(a)+'/contexte').json()['periode'];key=uuid4()
    payload={'periode_id':period['id'],'justification':'Fin fictive C06'}
    z=post(c,a,'/clotures/z',payload,key=key);d=z['instantane']['detail_flux']
    assert d['totaux']['net_regle']=='301' and d['totaux']['remboursements_executes']=='301'
    assert z['instantane']['nets_par_mode']['ESPECES']=='0'
    assert z['instantane']['sessions'][0]['especes_attendues']=='1000'
    assert z['instantane']['sessions'][0]['comptage_final']=='1005'
    assert z['instantane']['sessions'][0]['ecart_especes']=='5'
    assert post(c,a,'/clotures/z',payload,key=key)==z and financial_counts(c)==counts
    assert current(c,a,session)==before and c.get(pdfpath).content==original
    assert x['instantane']['detail_flux']['totaux']['remboursements_executes']=='0'
    pdf=c.get(root(a)+f'/documents/clotures/{z["id"]}/pdf').content
    text=' '.join(p.extract_text() for p in PdfReader(BytesIO(pdf)).pages)
    assert 'Remboursements exécutés' in text and '1005' in text
    # Le Z suivant ne reprend aucune session déjà clôturée, ni ses anciens règlements.
    next_period=c.get(root(a)+'/contexte').json()['periode']
    next_z=post(c,a,'/clotures/z',{'periode_id':next_period['id'],'justification':'Période vide fictive'})
    assert next_z['instantane']['detail_flux']['encaissements']==[]
    assert next_z['instantane']['detail_flux']['totaux']['net_regle']=='0'


@pytest.mark.parametrize('amount',['0','9007199254740993'])
def test_projection_exacte_sans_flottant_et_historique_inconnu(amount):
    # Projection pure de montants historiques, y compris hors précision IEEE-754.
    sid,mid,pid=uuid4(),uuid4(),uuid4();date=datetime(2026,10,23,tzinfo=timezone.utc)
    payment=SimpleNamespace(id=pid,confirmation_id=None,montant=Decimal(amount),rendu=Decimal(0))
    movement=SimpleNamespace(id=mid,session_id=sid,reglement_id=pid,mode='ESPECES',montant_net=Decimal(amount),date=date)
    class Stock:
        def lignes(self,cls,**filters):return [movement] if cls is MouvementCaisseModel else []
        def obtenir(self,cls,key):assert cls is ReglementModel and key==pid;return payment
    result=detail_flux(SimpleNamespace(stock=Stock()),[SimpleNamespace(id=sid)])
    assert result['totaux']['brut_recu']==result['totaux']['net_regle']==amount
    assert result['encaissements'][0]['libelle']=='ESPECES'


def test_transfert_deux_jambes_et_acquis_restitue_separes():
    sid,tid=uuid4(),uuid4();date=datetime(2026,10,23,tzinfo=timezone.utc)
    def m(type,amount,session=sid,origin=None):return SimpleNamespace(id=uuid4(),session_id=session,coffre_id=None if session else uuid4(),type=type,montant=Decimal(amount),origine=origin or uuid4(),mode='CARTE' if 'RESTITUE' in type or type=='REMBOURSEMENT' else 'ESPECES',date=date,auteur_id=uuid4(),justification='Fictive')
    debit=m('TRANSFERT_EXPEDIE','-10',origin=tid);credit=m('TRANSFERT_RECU','10',session=None,origin=tid)
    acquired=m('ACQUIS_RESTITUE','20');refund=m('REMBOURSEMENT','-20')
    transfer=SimpleNamespace(id=tid,session_id=sid,coffre_id=uuid4(),sens='CAISSE_COFFRE',etat='RECU',montant=Decimal(10))
    class Stock:
        def lignes(self,cls,**filters):
            if cls is MouvementFinancierModel:return [debit,credit] if 'origine' in filters else [debit,acquired,refund]
            if cls is TransfertFondsModel:return [transfer]
            return []
    d=detail_flux(SimpleNamespace(stock=Stock()),[SimpleNamespace(id=sid)])
    assert d['totaux']['net_regle']=='0' and d['totaux']['remboursements_executes']=='20'
    assert len(d['acquis_restitues'])==1 and d['acquis_restitues'][0]['montant_signe']=='20'
    assert {m['cible']:m['montant_signe'] for m in d['transferts'][0]['ecritures']}=={'CAISSE':'-10','COFFRE':'10'}
    assert d['autres']==[]
