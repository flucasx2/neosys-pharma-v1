"""D03/D04 : HTTP/ORM réels, données fictives et courses PostgreSQL natives."""
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from io import BytesIO
from decimal import Decimal
from uuid import UUID,uuid4
import pytest
from pypdf import PdfReader
from sqlalchemy import select,func,text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session
from test_regularisation import raw_client,account,setup45,final,ret,current,close,post,root,db,login
from test_caisse import post as cash_post,root as cash_root
from test_vente import create,line,act
from neosys_pharma.infrastructure.regularisation_models import (
    RetourVenteModel,DocumentRetourModel,QuarantaineModel,RemboursementModel,
    AnnulationRemboursementModel,PieceFinanciereModel,PreuveRemboursementModel,MouvementFinancierModel,
)
from neosys_pharma.infrastructure.caisse_models import MouvementCaisseModel,SessionCaisseModel
from neosys_pharma.infrastructure.stock_models import MouvementStockModel
from neosys_pharma.infrastructure.securite_models import RolePermissionModel,RoleModel
from neosys_pharma.domain.organisation.permissions_systeme import permission_id
from neosys_pharma.domain.stock import ConflitStock
from neosys_pharma.application.regularisation_service import RegularisationService
from neosys_pharma.application.caisse_service import CaisseService
from neosys_pharma.application.stock_service import StockService
from neosys_pharma.application.vente_service import VenteService


def counts(c):
    gen=db(c);s=next(gen)
    try:return {cls.__tablename__:s.scalar(select(func.count()).select_from(cls)) for cls in
        (RetourVenteModel,DocumentRetourModel,QuarantaineModel,AnnulationRemboursementModel,
         PieceFinanciereModel,PreuveRemboursementModel,MouvementFinancierModel,MouvementCaisseModel,MouvementStockModel)}
    finally:gen.close()


def permissions(c,a,keep):
    gen=db(c);s=next(gen)
    try:
        roles=select(RoleModel.id_role).where(RoleModel.organisation_id==a['org'])
        s.execute(RolePermissionModel.__table__.delete().where(RolePermissionModel.role_id.in_(roles),
            RolePermissionModel.permission_id.not_in([permission_id(p) for p in keep])))
        rid=s.scalar(select(RoleModel.id_role).where(RoleModel.organisation_id==a['org'],RoleModel.code=='CATALOGUE'))
        for code in keep:
            if s.get(RolePermissionModel,(rid,permission_id(code))) is None:
                s.add(RolePermissionModel(role_id=rid,permission_id=permission_id(code)))
        s.commit()
    finally:gen.close()
    login(c,a)


def requested(c,a,*,authorize=False,creation_key=None):
    sale,session,*_=setup45(c,a);receipt=final(c,a,sale,session);returned=ret(c,a,receipt,3)
    request=post(c,a,'/remboursements',{'retour_id':returned['id'],'session_id':session['id'],
        'revision':current(c,a,session)['revision'],'reglements':[{'mode':'ESPECES','montant':301}],
        'justification':'Restitution synthétique D04'},key=creation_key)
    if authorize:request=post(c,a,f'/remboursements/{request["id"]}/autoriser',
        {'revision':request['revision'],'justification':'Accord responsable'},200)
    return session,receipt,returned,request


def cancellation(request,**changes):
    return {'revision':request['revision'],'justification':'Client choisit une autre restitution',
        'attestation_absence_restitution':True,'restitution_externe_incertaine':False,**changes}


@pytest.mark.parametrize('quantity',[1,3])
def test_document_reception_immuable_permissions_et_sans_effet(raw_client,account,quantity):
    c,a=raw_client,account;sale,session,*_=setup45(c,a);receipt=final(c,a,sale,session)
    returned=ret(c,a,receipt,quantity);path=root(a)+f'/documents/retours/{returned["id"]}/pdf'
    pdf=c.get(path);assert pdf.status_code==200
    assert pdf.headers['etag']=='"'+returned['document']['pdf_sha256']+'"'
    text='\n'.join(p.extract_text() for p in PdfReader(BytesIO(pdf.content)).pages)
    assert 'NE VAUT PAS REMBOURSEMENT' in text and 'quarantaine' in text
    q=c.get(root(a)+'/stock/quarantaine').json()['items'][0]
    post(c,a,f'/stock/quarantaine/{q["id"]}/decision',{'liberer':True,'identite_conforme':True,
        'lot_conforme':True,'integrite_conforme':True,'conservation_conforme':True,'justification':'Contrôle fictif conforme'},200)
    assert c.get(path).content==pdf.content
    close(c,a,session)
    before=counts(c)
    permissions(c,a,('organisation.consulter','vente.retour.gerer'))
    assert c.get(path).content==pdf.content
    listed=c.get(root(a)+'/retours');assert listed.status_code==200 and listed.json()['items'][0]['document_disponible']
    assert c.get(root(a)+'/remboursements').status_code==403
    assert c.get(root({'org':uuid4()})+f'/documents/retours/{returned["id"]}/pdf').status_code==403
    assert counts(c)==before
    permissions(c,a,('organisation.consulter','caisse.cloture.consulter'));assert c.get(path).content==pdf.content
    permissions(c,a,('organisation.consulter',));assert c.get(path).status_code==403


@pytest.mark.parametrize('failure',['pdf','audit'])
def test_document_et_reception_rollback_atomique(raw_client,account,monkeypatch,failure):
    c,a=raw_client,account;sale,session,*_=setup45(c,a);receipt=final(c,a,sale,session);before=counts(c)
    if failure=='pdf':monkeypatch.setattr('neosys_pharma.infrastructure.regularisation_pdf.document_pdf',lambda _:(_ for _ in ()).throw(ValueError('PDF indisponible')))
    else:monkeypatch.setattr(RegularisationService,'trace',lambda *args,**kwargs:(_ for _ in ()).throw(ValueError('Audit indisponible')))
    ret(c,a,receipt,1,422);assert counts(c)==before


def test_document_montant_nul_et_rejeu_reception(raw_client,account):
    from neosys_pharma.infrastructure.tarification_models import TarifReferenceModel
    c,a=raw_client,account;sale,session,product,pack,pid,cid,*_=setup45(c,a)
    act(c,a,sale,'annuler',justification='Fixture avant vente de faible montant')
    gen=db(c);s=next(gen)
    try:s.scalar(select(TarifReferenceModel)).montant_ht=Decimal('0.25');s.commit()
    finally:gen.close()
    sale=line(c,a,create(c,a,pid),product,pack,3);sale=act(c,a,sale,'valider');sale=act(c,a,sale,'transmettre',caisse_id=cid)
    assert sale['totaux']['ttc']=='1';receipt=final(c,a,sale,session,reglements=[{'mode':'ESPECES','montant':1}])
    key=uuid4();returned=ret(c,a,receipt,key=key);assert returned['montant']=='0'
    assert ret(c,a,receipt,key=key)==returned
    assert counts(c)['vente_documents_retour']==1
    assert c.get(root(a)+f'/documents/retours/{returned["id"]}/pdf').status_code==200


def test_retour_historique_sans_piece_aucun_backfill(raw_client,account):
    c,a=raw_client,account;sale,session,*_=setup45(c,a);receipt=final(c,a,sale,session)
    gen=db(c);s=next(gen);rid=uuid4()
    try:s.add(RetourVenteModel(id=rid,organisation_id=a['org'],encaissement_id=UUID(receipt['id']),site_id=a['site'],auteur_id=a['user'],montant=0,justification='Historique fictif',instantane={}));s.commit()
    finally:gen.close()
    before=counts(c);assert c.get(root(a)+f'/documents/retours/{rid}/pdf').status_code==409
    assert counts(c)==before and not c.get(root(a)+'/retours').json()['items'][0]['document_disponible']


@pytest.mark.parametrize('authorize',[False,True])
def test_annulation_budget_rejeu_remplacement_et_z(raw_client,account,authorize):
    c,a=raw_client,account;session,receipt,returned,request=requested(c,a,authorize=authorize)
    pdfpath=root(a)+f'/documents/retours/{returned["id"]}/pdf';pdf=c.get(pdfpath).content
    before=counts(c);s_before=current(c,a,session);key=uuid4();payload=cancellation(request)
    result=post(c,a,f'/remboursements/{request["id"]}/annuler',payload,200,key)
    assert result['etat']=='ANNULE' and result['reglements']==request['reglements']
    assert result['justification']==request['justification'] and result['revision']==request['revision']+1
    assert post(c,a,f'/remboursements/{request["id"]}/annuler',payload,200,key)==result
    post(c,a,f'/remboursements/{request["id"]}/annuler',cancellation(result),409)
    post(c,a,f'/remboursements/{request["id"]}/autoriser',{'revision':result['revision'],'justification':'Terminal'},409)
    assert current(c,a,session)==s_before
    after=counts(c);assert after=={**before,'finance_annulations_remboursement':1}
    budget=c.get(root(a)+f'/retours/{returned["id"]}/solde').json()
    assert not budget['deja_demande'] and budget['remplace_id']==request['id']
    assert sum(Decimal(x['montant']) for x in budget['disponible_par_moyen'])==301
    body={'retour_id':returned['id'],'session_id':session['id'],'revision':s_before['revision'],
          'justification':'Remplacement explicite','reglements':[{'mode':'ESPECES','montant':301}]}
    post(c,a,'/remboursements',body,409)
    post(c,a,'/remboursements',{**body,'remplace_id':str(uuid4())},409)
    replacement=post(c,a,'/remboursements',{**body,'remplace_id':request['id']})
    assert replacement['remplace_id']==request['id']
    post(c,a,'/remboursements',{**body,'remplace_id':request['id']},409)
    # Annuler la demande de remplacement ne rembourse toujours pas le retour.
    post(c,a,f'/remboursements/{replacement["id"]}/annuler',cancellation(replacement),200)
    close(c,a,session);period=c.get(root(a)+'/contexte').json()['periode']
    post(c,a,'/clotures/z',{'periode_id':period['id'],'justification':'Retour toujours impayé'},409)
    assert c.get(pdfpath).content==pdf


@pytest.mark.parametrize('changes,status',[
    ({'attestation_absence_restitution':False},422),({'restitution_externe_incertaine':True},409),
    ({'justification':'   '},422),({'revision':999},409),
])
def test_refus_annulation_sans_effet(raw_client,account,changes,status):
    c,a=raw_client,account;_,_,_,request=requested(c,a);before=counts(c)
    post(c,a,f'/remboursements/{request["id"]}/annuler',cancellation(request,**changes),status)
    assert counts(c)==before


@pytest.mark.parametrize('artifact',['piece','preuve','mouvement'])
def test_refus_annulation_si_trace_execution(raw_client,account,artifact):
    c,a=raw_client,account;session,_,_,request=requested(c,a);gen=db(c);s=next(gen)
    try:
        common={'id':uuid4(),'organisation_id':a['org']}
        if artifact=='piece':row=PieceFinanciereModel(**common,remboursement_id=UUID(request['id']),auteur_id=a['user'],instantane={},pdf=b'fiction',pdf_sha256='0'*64)
        elif artifact=='preuve':row=PreuveRemboursementModel(**common,remboursement_id=UUID(request['id']),mode='CARTE',reference='TRACE-FICTIVE',preuve='À diagnostiquer')
        else:row=MouvementFinancierModel(**common,site_id=a['site'],session_id=UUID(session['id']),coffre_id=None,mode='ESPECES',montant=-1,type='REMBOURSEMENT',origine=UUID(request['id']),auteur_id=a['user'],justification='Trace fictive incohérente')
        s.add(row);s.commit()
    finally:gen.close()
    before=counts(c);post(c,a,f'/remboursements/{request["id"]}/annuler',cancellation(request),409);assert counts(c)==before


def test_annulation_session_fermee_et_permission_distincte(raw_client,account):
    c,a=raw_client,account;session,_,_,request=requested(c,a)
    # État historique fermé : injecté seulement dans la fixture, fermeture ordinaire
    # refuse encore les demandes actives ; aucune réouverture/écriture de caisse.
    gen=db(c);s=next(gen)
    try:
        row=s.get(SessionCaisseModel,UUID(session['id']));row.etat='FERMEE';row.comptage_final=1301;s.commit()
    finally:gen.close()
    permissions(c,a,('organisation.consulter','caisse.remboursement.annuler','vente.retour.gerer'))
    assert c.get(root(a)+'/remboursements').status_code==200
    before=counts(c);result=post(c,a,f'/remboursements/{request["id"]}/annuler',cancellation(request),200)
    assert result['etat']=='ANNULE' and counts(c)=={**before,'finance_annulations_remboursement':1}
    permissions(c,a,('organisation.consulter','caisse.remboursement.autoriser'))
    post(c,a,f'/remboursements/{request["id"]}/annuler',cancellation(result),403)


def test_execute_terminal_et_journaux_sql_proteges(raw_client,account):
    c,a=raw_client,account;session,_,_,request=requested(c,a,authorize=True)
    executed=post(c,a,f'/remboursements/{request["id"]}/executer',
        {'revision':request['revision'],'justification':'Remis fictivement','preuves':[{}]},200)
    before=counts(c);post(c,a,f'/remboursements/{request["id"]}/annuler',cancellation(executed),409)
    assert counts(c)==before
    gen=db(c);s=next(gen)
    try:
        doc=s.scalar(select(DocumentRetourModel));doc.pdf=b'changed'
        with pytest.raises(DBAPIError):s.commit()
        s.rollback()
    finally:gen.close()


def test_remplacement_execute_budget_et_z_resolus(raw_client,account):
    c,a=raw_client,account;session,_,returned,request=requested(c,a)
    path=root(a)+f'/documents/retours/{returned["id"]}/pdf';pdf=c.get(path).content
    post(c,a,f'/remboursements/{request["id"]}/annuler',cancellation(request),200)
    replacement=post(c,a,'/remboursements',{'retour_id':returned['id'],'remplace_id':request['id'],
        'session_id':session['id'],'revision':current(c,a,session)['revision'],
        'reglements':[{'mode':'ESPECES','montant':301}],'justification':'Remplacement explicite'})
    approved=post(c,a,f'/remboursements/{replacement["id"]}/autoriser',{'revision':replacement['revision'],'justification':'Autorisé'},200)
    result=post(c,a,f'/remboursements/{replacement["id"]}/executer',{'revision':approved['revision'],'justification':'Remis','preuves':[{}]},200)
    post(c,a,f'/remboursements/{result["id"]}/annuler',cancellation(result),409)
    assert current(c,a,session)['especes_attendues']=='1000' and c.get(path).content==pdf
    gen=db(c);s=next(gen)
    try:
        for cls,field,value in ((AnnulationRemboursementModel,'justification','Faux'),(RemboursementModel,'etat','DEMANDE')):
            row=s.scalar(select(cls).where(cls.remboursement_id==UUID(request['id']))) if cls is AnnulationRemboursementModel else s.get(cls,UUID(request['id']))
            setattr(row,field,value)
            with pytest.raises(DBAPIError):s.commit()
            s.rollback()
    finally:gen.close()
    close(c,a,session);period=c.get(root(a)+'/contexte').json()['periode']
    post(c,a,'/clotures/z',{'periode_id':period['id'],'justification':'Retour effectivement remboursé'})


@pytest.mark.parametrize('missing',['cle','revision','justification','attestation_absence_restitution','restitution_externe_incertaine'])
def test_champs_annulation_obligatoires_et_csrf(raw_client,account,missing):
    c,a=raw_client,account;_,_,_,request=requested(c,a);before=counts(c)
    payload={'cle':str(uuid4()),**cancellation(request)};payload.pop(missing)
    assert c.post(root(a)+f'/remboursements/{request["id"]}/annuler',json=payload).status_code==422
    assert counts(c)==before
    c.headers.pop('X-CSRF-Token',None)
    assert c.post(root(a)+f'/remboursements/{request["id"]}/annuler',json={'cle':str(uuid4()),**cancellation(request)}).status_code==403


def test_document_multilot_et_aucune_ecriture_commerciale(raw_client,account):
    from test_stock import lot,entry
    c,a=raw_client,account;sale,session,product,pack,pid,cid,*_=setup45(c,a)
    act(c,a,sale,'annuler',justification='Fixture multilot avant paiement')
    other=lot(c,a,pack,'P405-LOT-SECOND');entry(c,a,other['id'],5)
    sale=line(c,a,create(c,a,pid),product,pack,12);sale=act(c,a,sale,'valider');sale=act(c,a,sale,'transmettre',caisse_id=cid)
    receipt=final(c,a,sale,session,reglements=[{'mode':'ESPECES','montant':1500}])
    details=c.get(root(a)+f'/recus/{receipt["id"]}/retournable').json()['lignes']
    assert len(details)==2
    before=counts(c)
    result=post(c,a,'/retours',{'encaissement_id':receipt['id'],'justification':'Réception de deux lots',
        'lignes':[{'ligne_id':d['ligne_id'],'stock_id':d['stock_id'],'quantite':d['quantite_restante']} for d in details]})
    assert len(result['document']['instantane']['lignes'])==2
    assert sum(x['quantite'] for x in result['document']['instantane']['lignes'])==12
    assert counts(c)['stock_mouvements']==before['stock_mouvements']


@pytest.mark.parametrize('grouped',[False,True])
def test_confirmation_annulee_disponible_sans_reacquisition(raw_client,account,monkeypatch,grouped):
    c,a=raw_client,account;sale,session,product,pack,pid,cid,*_=setup45(c,a)
    cf=cash_post(c,a,f'/ventes/{sale["id"]}/confirmations',{'session_id':session['id'],
        'revision':sale['revision'],'mode':'CARTE','montant':100,'reference':'D04-ACQUIS',
        'source':'MANUEL_TERMINAL','preuve':'Confirmation fictive existante'})
    request=post(c,a,'/remboursements',{'confirmation_id':cf['id'],'session_id':session['id'],
        'revision':session['revision'],'reglements':[{'mode':'CARTE','moyen_id':cf['moyen_id'],
        'moyen_origine_id':cf['moyen_id'],'montant':100}],'justification':'Demande abandonnée avant restitution'})
    post(c,a,f'/remboursements/{request["id"]}/annuler',cancellation(request),200)
    pending=c.get(root(a)+'/paiements/non-finalises').json()
    assert len(pending)==1 and pending[0]['id']==cf['id'] and pending[0]['remplace_id']==request['id']
    if grouped:
        from test_caisse import groupe_post,groupe_put
        import neosys_pharma.presentation.encaissement_groupe_api as api
        monkeypatch.setattr(api,'GROUPED_ENCASHMENT_ENABLED',True)
        second=line(c,a,create(c,a,pid),product,pack,2);second=act(c,a,second,'valider');second=act(c,a,second,'transmettre',caisse_id=cid)
        draft=groupe_post(c,a,'',{'cle':str(uuid4()),'session_id':session['id']},201);gid=draft['dossier']['id']
        draft=groupe_put(c,a,f'/{gid}/ventes',{'cle':str(uuid4()),'revision':draft['dossier']['revision'],
            'ventes':[{'vente_id':v['id'],'revision':v['revision']} for v in (sale,second)]})
        draft=groupe_put(c,a,f'/{gid}/reglements',{'cle':str(uuid4()),'revision':draft['dossier']['revision'],
            'reglements':[{'mode':'CARTE','montant':100,'confirmation_id':cf['id']},{'mode':'ESPECES','montant':402}]})
        proposal=c.get(cash_root(a)+f'/groupes/{gid}/allocations/proposition',params={'revision':draft['dossier']['revision']}).json()
        draft=groupe_put(c,a,f'/{gid}/allocations',{'cle':str(uuid4()),'revision':draft['dossier']['revision'],'allocations':proposal})
        result=groupe_post(c,a,f'/{gid}/finaliser',{'cle':str(uuid4()),'revision':draft['dossier']['revision'],
            'revision_session':current(c,a,session)['revision'],'fidelite':[]})
        assert result['dossier']['etat']=='FINALISE'
    else:
        receipt=final(c,a,sale,current(c,a,session),reglements=[{'mode':'CARTE','montant':100,'confirmation_id':cf['id']},{'mode':'ESPECES','montant':201}])
        assert receipt['total_xaf']=='301'
    assert not c.get(root(a)+'/paiements/non-finalises').json()


def test_ancienne_cle_creation_ne_reactive_pas_demande_annulee(raw_client,account):
    c,a=raw_client,account;key=uuid4();session,_,returned,request=requested(c,a,creation_key=key)
    post(c,a,f'/remboursements/{request["id"]}/annuler',cancellation(request),200)
    payload={'retour_id':returned['id'],'session_id':session['id'],'revision':current(c,a,session)['revision'],
        'reglements':[{'mode':'ESPECES','montant':301}],'justification':'Restitution synthétique D04'}
    assert post(c,a,'/remboursements',payload,key=key)==request
    listed=c.get(root(a)+'/remboursements').json()['items'];assert len(listed)==1 and listed[0]['etat']=='ANNULE'
    assert not c.get(root(a)+f'/retours/{returned["id"]}/solde').json()['deja_demande']


def test_annulation_rollback_audit_conserve_reservation(raw_client,account,monkeypatch):
    c,a=raw_client,account;_,_,returned,request=requested(c,a);before=counts(c)
    monkeypatch.setattr(RegularisationService,'trace',lambda *args,**kwargs:(_ for _ in ()).throw(ValueError('Audit indisponible')))
    post(c,a,f'/remboursements/{request["id"]}/annuler',cancellation(request),422)
    assert counts(c)==before and c.get(root(a)+f'/retours/{returned["id"]}/solde').json()['deja_demande']


@pytest.mark.parametrize('race',['annuler_executer','double_annulation','meme_cle','double_retour','double_controle','fonds_remboursement','remplacement'])
def test_courses_d03_d04_postgresql(raw_client,account,race):
    c,a=raw_client,account
    if race=='double_retour':
        sale,session,*_=setup45(c,a);receipt=final(c,a,sale,session)
        detail=c.get(root(a)+f'/recus/{receipt["id"]}/retournable').json()['lignes'][0]
    else:session,receipt,returned,request=requested(c,a,authorize=True)
    if race=='double_controle':q=c.get(root(a)+'/stock/quarantaine').json()['items'][0]
    if race=='remplacement':post(c,a,f'/remboursements/{request["id"]}/annuler',cancellation(request),200)
    session_revision=current(c,a,session)['revision'];shared_key=uuid4();barrier=Barrier(2);backends=[]
    gen=db(c);s=next(gen);engine=s.bind;gen.close()
    if engine.dialect.name!='postgresql':pytest.skip('Deux transactions PostgreSQL natives requises D03/D04')
    def worker(index):
        with Session(engine) as sql:
            backends.append(sql.scalar(text('SELECT pg_backend_pid()')));barrier.wait(timeout=15)
            stock=StockService(sql,a['org'],a['user'],lambda *args:None)
            service=RegularisationService(CaisseService(VenteService(stock,a['site'])))
            def action():
                if race=='double_retour':return service.retour({'encaissement_id':UUID(receipt['id']),
                    'lignes':[{'ligne_id':UUID(detail['ligne_id']),'stock_id':UUID(detail['stock_id']),'quantite':3}],
                    'justification':'Retour total concurrent'})
                if race=='double_controle':return service.controle(UUID(q['id']),{'liberer':True,
                    'identite_conforme':True,'lot_conforme':True,'integrite_conforme':True,
                    'conservation_conforme':True,'justification':'Décision concurrente'})
                if race=='remplacement':return service.remboursement({'retour_id':UUID(returned['id']),
                    'remplace_id':UUID(request['id']),'session_id':UUID(session['id']),'revision':session_revision,
                    'reglements':[{'mode':'ESPECES','montant':301}],'justification':'Remplacement concurrent'})
                if race=='fonds_remboursement':
                    if index:return service.refund_action(UUID(request['id']),{'revision':request['revision'],'justification':'Remise concurrente','preuves':[{}]},'executer')
                    return service.fonds({'session_id':UUID(session['id']),'revision':session_revision,
                        'sens':'SORTIE','montant':1200,'justification':'Retrait concurrent'})
                if race=='annuler_executer' and index:
                    return service.refund_action(UUID(request['id']),{'revision':request['revision'],'justification':'Course fictive','preuves':[{}]},'executer')
                return service.annuler_remboursement(UUID(request['id']),cancellation(request))
            try:stock.operation(shared_key if race=='meme_cle' else uuid4(),'D04:RACE',{'worker':0 if race=='meme_cle' else index},action);return 'ok'
            except (ValueError,PermissionError,ConflitStock,DBAPIError):return 'refus'
    with ThreadPoolExecutor(max_workers=2) as pool:assert sorted(pool.map(worker,[0,1]))==(['ok','ok'] if race=='meme_cle' else ['ok','refus'])
    assert len(set(backends))==2
    gen=db(c);s=next(gen)
    try:
        if race=='double_retour':
            assert s.scalar(select(func.count()).select_from(DocumentRetourModel))==1
            assert s.scalar(select(func.count()).select_from(RetourVenteModel))==1
            assert s.scalar(select(func.count()).select_from(QuarantaineModel))==1
            return
        if race=='double_controle':
            assert s.get(QuarantaineModel,UUID(q['id'])).etat=='LIBEREE'
            assert s.scalar(select(func.count()).select_from(MouvementStockModel).where(MouvementStockModel.type=='RETOUR_LIBERE'))==1
            return
        if race=='remplacement':
            assert s.scalar(select(func.count()).select_from(RemboursementModel))==2
            assert s.scalar(select(func.count()).select_from(RemboursementModel).where(RemboursementModel.etat!='ANNULE'))==1
            return
        if race=='fonds_remboursement':
            service=RegularisationService(CaisseService(VenteService(StockService(s,a['org'],a['user'],lambda *args:None),a['site'])))
            assert service.cash.session_detail(s.get(SessionCaisseModel,UUID(session['id'])))['especes_attendues'] in ('101','1000')
            assert s.scalar(select(func.count()).select_from(MouvementFinancierModel))==1
            return
        row=s.get(RemboursementModel,UUID(request['id']))
        assert row.etat in ('ANNULE','EXECUTE')
        assert s.scalar(select(func.count()).select_from(AnnulationRemboursementModel))==(row.etat=='ANNULE')
        assert s.scalar(select(func.count()).select_from(PieceFinanciereModel))==(row.etat=='EXECUTE')
        assert s.scalar(select(func.count()).select_from(DocumentRetourModel))==1
    finally:gen.close()
