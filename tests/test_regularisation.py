"""P4.5 : appels HTTP directs, stock isolé, clôtures et pièces historiques."""
from uuid import UUID,uuid4
from decimal import Decimal
from concurrent.futures import ThreadPoolExecutor
from io import BytesIO
import os
import pytest
from sqlalchemy import select,text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session
from pypdf import PdfReader
from test_authentification import PASSWORD
from test_caisse import raw_client,account,ready,final,root as cash_root,post as cash_post,db,login,stocks,create,line,act,rule,category
from neosys_pharma.infrastructure.securite_models import RoleModel,RolePermissionModel
from neosys_pharma.infrastructure.organisation_models import CoffreModel
from neosys_pharma.domain.organisation.permissions_systeme import REGULARISATION_PERMISSIONS,permission_id
from neosys_pharma.infrastructure.regularisation_models import *
from neosys_pharma.infrastructure.caisse_models import *
from neosys_pharma.application.regularisation_service import RegularisationService
from neosys_pharma.application.caisse_service import CaisseService
from neosys_pharma.application.vente_service import VenteService
from neosys_pharma.application.stock_service import StockService
from neosys_pharma.domain.stock import ConflitStock

def root(a):return '/api/regularisations/organisations/'+str(a['org'])
def post(c,a,path,data,status=201,key=None):
    r=c.post(root(a)+path,json={'cle':str(key or uuid4()),**data});assert r.status_code==status,r.text;return r.json()
def grant45(c,a):
    gen=db(c);s=next(gen)
    try:
        rid=s.scalar(select(RoleModel.id_role).where(RoleModel.organisation_id==a['org'],RoleModel.code=='CATALOGUE'))
        for p,_ in REGULARISATION_PERMISSIONS:s.add(RolePermissionModel(role_id=rid,permission_id=permission_id(p)))
        coffre=CoffreModel(id_coffre=uuid4(),site_id=a['site'],code='COFFRE',nom='Coffre de recette');s.add(coffre);s.commit();return str(coffre.id_coffre)
    finally:gen.close()
def setup45(c,a,q=3):
    v,session,prod,pack,pid,cid=ready(c,a,q);coffre=grant45(c,a);login(c,a);return v,session,prod,pack,pid,cid,coffre
def current(c,a,s):return next(x for x in c.get(root(a)+'/contexte').json()['sessions'] if x['id']==s['id'])
def close(c,a,s,count=None):
    s=current(c,a,s);return cash_post(c,a,f'/sessions/{s["id"]}/fermer',{'revision':s['revision'],'comptage_final':count if count is not None else s['especes_attendues'],'justification':'Comptage constaté'},200)
def ret(c,a,e,q=1,status=201,key=None):
    data=c.get(root(a)+f'/recus/{e["id"]}/retournable');assert data.status_code==200,data.text
    row=data.json()['lignes'][0];return post(c,a,'/retours',{'encaissement_id':e['id'],'lignes':[{'ligne_id':row['ligne_id'],'stock_id':row['stock_id'],'quantite':q}],'justification':'Retour client reçu physiquement'},status,key)
def refund(c,a,r,s,mode='ESPECES'):
    s=current(c,a,s);d=post(c,a,'/remboursements',{'retour_id':r['id'],'session_id':s['id'],'revision':s['revision'],'reglements':[{'mode':mode,'montant':r['montant']}],'justification':'Remboursement historique'})
    d=post(c,a,f'/remboursements/{d["id"]}/autoriser',{'revision':d['revision'],'justification':'Responsable habilité'},200)
    return post(c,a,f'/remboursements/{d["id"]}/executer',{'revision':d['revision'],'justification':'Montant remis au titulaire','preuves':[{'reference':'REF-QA','preuve':'Restitution vérifiée'}]},200)

def test_x_z_annulation_sequences_et_pdf_historiques(raw_client,account,tmp_path):
    c,a=raw_client,account;v,s,prod,pack,pid,cid,_=setup45(c,a);e=final(c,a,v,s)
    pending=line(c,a,create(c,a,pid),prod,pack,2)
    x=post(c,a,'/clotures/x',{'session_id':s['id'],'revision':current(c,a,s)['revision']})
    assert current(c,a,s)['etat']=='OUVERTE'
    period=c.get(root(a)+'/contexte').json()['periode'];payload={'periode_id':period['id'],'justification':'Fin de journée'}
    post(c,a,'/clotures/z',payload,409);close(c,a,s);key=uuid4();z=post(c,a,'/clotures/z',payload,201,key)
    assert post(c,a,'/clotures/z',payload,201,key)==z
    post(c,a,'/clotures/z',payload,409)
    assert stocks(c,a)[0]['reserve']==0
    assert pending['id'] in z['instantane']['preparations_annulees']
    p=c.get(root(a)+'/contexte').json()['periode'];assert p['numero']==period['numero']+1 and p['prochain_appel']==p['prochain_encaissement']==1
    for doc in (x,z):
        path=f'/documents/clotures/{doc["id"]}/pdf';pdf=c.get(root(a)+path);assert pdf.status_code==200
        assert c.get(root(a)+path).content==pdf.content
        text_=''.join(p.extract_text() for p in PdfReader(BytesIO(pdf.content)).pages);assert 'Page' in text_ and 'Responsable' in text_
        (tmp_path/f'{doc["type"]}.pdf').write_bytes(pdf.content)

def test_ecart_conserve_et_reconnaissance_obligatoire(raw_client,account):
    c,a=raw_client,account;v,s,*_=setup45(c,a);close(c,a,s,999)
    period=c.get(root(a)+'/contexte').json()['periode'];p={'periode_id':period['id'],'justification':'Fin'}
    post(c,a,'/clotures/z',p,409)
    post(c,a,f'/sessions/{s["id"]}/ecart',{'revision':current(c,a,s)['revision'],'justification':'Écart constaté et reconnu'})
    z=post(c,a,'/clotures/z',p);assert z['instantane']['sessions'][0]['ecart_especes']=='-1'

def test_fonds_transfert_separation_transit_double_reception(raw_client,account):
    c,a=raw_client,account;v,s,*rest=setup45(c,a);coffre=rest[-1]
    post(c,a,'/fonds',{'session_id':s['id'],'revision':s['revision'],'sens':'SORTIE','montant':1001,'justification':'Sortie excessive'},409)
    t=post(c,a,'/transferts',{'session_id':s['id'],'revision':s['revision'],'coffre_id':coffre,'sens':'CAISSE_COFFRE','montant':100,'justification':'Dépôt sécurisé'})
    assert c.get(root(a)+f'/documents/transferts/{t["id"]}/pdf').status_code==409
    post(c,a,f'/transferts/{t["id"]}/recevoir',{'revision':t['revision'],'justification':'Sans expédition'},409)
    t=post(c,a,f'/transferts/{t["id"]}/autoriser',{'revision':t['revision'],'justification':'Autorisation'},200)
    t=post(c,a,f'/transferts/{t["id"]}/expedier',{'revision':t['revision'],'justification':'Dérogation habilitée tracée'},200)
    context=c.get(root(a)+'/contexte').json();assert context['coffres'][0]['solde']=='0' and current(c,a,s)['especes_attendues']=='900'
    post(c,a,f'/transferts/{t["id"]}/recevoir',{'revision':t['revision'],'justification':'Même expéditeur'},403)
    # Independent approver/receiver identity; provisioned through explicit P1 assignments.
    from neosys_pharma.infrastructure.provisionnement import provisionner
    from neosys_pharma.infrastructure.securite_repository import SqlAlchemySecuriteRepository
    from neosys_pharma.domain.organisation.securite import Utilisateur
    gen=db(c);dbs=next(gen)
    try:
        rid=dbs.scalar(select(RoleModel.id_role).where(RoleModel.organisation_id==a['org'],RoleModel.code=='CATALOGUE'));u=Utilisateur(organisation_id=a['org'],identifiant='receveur',nom='Receveur');provisionner(dbs,u,[a['site']],[a['location']],[rid],PASSWORD)
    finally:gen.close()
    r=login(c,a,identifiant='receveur');assert r.status_code==200,r.text
    csrf=c.cookies.get('neosys_csrf');c.headers['X-CSRF-Token']=csrf
    key=uuid4();payload={'revision':t['revision'],'justification':'Fonds reçus et comptés'};t=post(c,a,f'/transferts/{t["id"]}/recevoir',payload,200,key)
    assert t['etat']=='RECU';assert post(c,a,f'/transferts/{t["id"]}/recevoir',payload,200,key)==t
    receipt=c.get(root(a)+f'/documents/transferts/{t["id"]}/pdf');assert receipt.status_code==200 and receipt.content.startswith(b'%PDF')
    assert c.get(root(a)+f'/documents/transferts/{t["id"]}/pdf').content==receipt.content
    post(c,a,f'/transferts/{t["id"]}/recevoir',{'revision':t['revision'],'justification':'Double réception'},409)
    assert c.get(root(a)+'/contexte').json()['coffres'][0]['solde']=='100'

def test_retours_partiels_cumulatifs_quarantaine_remboursement_fidelite(raw_client,account):
    c,a=raw_client,account;v,s,prod,*_=setup45(c,a)
    account_=cash_post(c,a,'/fidelite',{'nom':'Titulaire QA'});rule(c,a,category(c,a,prod));e=final(c,a,v,s,compte_id=account_['id'],revision_compte=account_['revision'])
    original=c.get(cash_root(a)+f'/recus/{e["id"]}/pdf').content
    amounts=[]
    for i in range(3):
        r=ret(c,a,e);amounts.append(Decimal(r['montant']));assert stocks(c,a)[0]['physique']==7
        refund(c,a,r,s)
    assert sum(amounts)==301 and amounts==[Decimal(100),Decimal(100),Decimal(101)]
    assert c.get(cash_root(a)+f'/fidelite/{account_["id"]}').json()['points']==0
    assert c.get(cash_root(a)+f'/fidelite/{account_["id"]}/journal').json()['total']==4
    ret(c,a,e,1,409);assert c.get(cash_root(a)+f'/recus/{e["id"]}/pdf').content==original
    q=c.get(root(a)+'/stock/quarantaine').json()['items'];assert len(q)==3 and all(x['vendable']==0 for x in q)
    data={'liberer':True,'identite_conforme':True,'lot_conforme':True,'integrite_conforme':False,'conservation_conforme':True,'justification':'Emballage ouvert'}
    post(c,a,f'/stock/quarantaine/{q[0]["id"]}/decision',data,422)
    data['liberer']=False;post(c,a,f'/stock/quarantaine/{q[0]["id"]}/decision',data,200)
    data.update(liberer=True,integrite_conforme=True)
    post(c,a,f'/stock/quarantaine/{q[0]["id"]}/decision',data,409)
    post(c,a,f'/stock/quarantaine/{q[1]["id"]}/decision',data,200);assert stocks(c,a)[0]['physique']==8
    post(c,a,f'/stock/quarantaine/{q[1]["id"]}/decision',data,409)

def test_paiement_acquis_restitution_preuve_et_blocage_z(raw_client,account):
    c,a=raw_client,account;v,s,*_=setup45(c,a)
    cf=cash_post(c,a,f'/ventes/{v["id"]}/confirmations',{'session_id':s['id'],'revision':v['revision'],'mode':'CARTE','montant':100,'reference':'ACQUIS-QA','source':'MANUEL_TERMINAL','preuve':'Terminal accepté'})
    r=post(c,a,'/remboursements',{'confirmation_id':cf['id'],'session_id':s['id'],'revision':s['revision'],'reglements':[{'mode':'CARTE','montant':100}],'justification':'Client abandonne'})
    r=post(c,a,f'/remboursements/{r["id"]}/autoriser',{'revision':r['revision'],'justification':'Autorisé'},200)
    post(c,a,f'/remboursements/{r["id"]}/executer',{'revision':r['revision'],'justification':'Sans preuve','preuves':[{}]},422)
    post(c,a,f'/remboursements/{r["id"]}/executer',{'revision':r['revision'],'justification':'Preuve vide','preuves':[{'reference':'  ','preuve':' \t '}]},422)
    r=post(c,a,f'/remboursements/{r["id"]}/executer',{'revision':r['revision'],'justification':'Restitution constatée','preuves':[{'reference':'ANNULATION-TPE','preuve':'Preuve indépendante vérifiée'}]},200)
    assert c.get(root(a)+'/paiements/non-finalises').json()==[]
    pdf=c.get(root(a)+f'/documents/remboursements/{r["id"]}/pdf');assert pdf.status_code==200 and b'%PDF' in pdf.content
    post(c,a,f'/remboursements/{r["id"]}/executer',{'revision':r['revision'],'justification':'Double','preuves':[{}]},409)
    close(c,a,s);p=c.get(root(a)+'/contexte').json()['periode'];post(c,a,'/clotures/z',{'periode_id':p['id'],'justification':'Paiement restitué'})

def test_401_403_csrf_scope_et_journaux_immutables(raw_client,account):
    c,a=raw_client,account;v,s,*_=setup45(c,a);e=final(c,a,v,s);r=ret(c,a,e)
    assert c.get(root({'org':uuid4()})+'/contexte').status_code==403
    c.headers['X-Site-ID']=str(a['other'])
    assert c.get(root(a)+f'/recus/{e["id"]}/retournable').status_code==403
    assert c.get(root(a)+'/stock/quarantaine').status_code==403
    c.headers['X-Site-ID']=str(a['site'])
    gen=db(c);dbs=next(gen)
    try:
        for table in ('vente_retours','vente_lignes_retour'):
            with pytest.raises(DBAPIError):dbs.execute(text(f'DELETE FROM {table}'));dbs.commit()
            dbs.rollback()
        rid=dbs.scalar(select(RoleModel.id_role).where(RoleModel.organisation_id==a['org'],RoleModel.code=='CATALOGUE'))
        dbs.execute(RolePermissionModel.__table__.delete().where(RolePermissionModel.role_id==rid,RolePermissionModel.permission_id.in_([permission_id(p) for p,_ in REGULARISATION_PERMISSIONS])));dbs.commit()
    finally:gen.close()
    login(c,a);post(c,a,'/retours',{'encaissement_id':e['id'],'lignes':[],'justification':'Interdit'},403)
    assert c.get(root(a)+'/contexte').status_code==403
    c.headers.pop('X-CSRF-Token',None);assert c.post(root(a)+'/fonds',json={}).status_code==403
    c.cookies.clear();assert c.get(root(a)+'/contexte').status_code==401

@pytest.mark.parametrize('fail',['pdf','funds','fiscal','duplicate'])
def test_rollback_remboursement_et_non_contournement(raw_client,account,monkeypatch,fail):
    c,a=raw_client,account;v,s,prod,*_=setup45(c,a);ca=cash_post(c,a,'/fidelite',{'nom':'Dette QA'});rule(c,a,category(c,a,prod));e=final(c,a,v,s,compte_id=ca['id'],revision_compte=ca['revision']);r=ret(c,a,e,3)
    s=current(c,a,s);d=post(c,a,'/remboursements',{'retour_id':r['id'],'session_id':s['id'],'revision':s['revision'],'reglements':[{'mode':'ESPECES','montant':r['montant']}],'justification':'Retour total'})
    d=post(c,a,f'/remboursements/{d["id"]}/autoriser',{'revision':d['revision'],'justification':'Autorisé'},200)
    if fail=='funds':post(c,a,'/fonds',{'session_id':s['id'],'revision':s['revision'],'sens':'SORTIE','montant':1200,'justification':'Dépôt séparé'})
    if fail=='pdf':monkeypatch.setattr('neosys_pharma.infrastructure.regularisation_pdf.document_pdf',lambda _:(_ for _ in ()).throw(ValueError('PDF indisponible')))
    if fail=='fiscal':
        # Acquisition remains valid; points redemption cannot bypass the fiscal guard through refund endpoints.
        payload={'cle':str(uuid4()),'revision':d['revision'],'justification':'Interdit','preuves':[{}],'points_utilises':1};assert c.post(root(a)+f'/remboursements/{d["id"]}/executer',json=payload).status_code==422
    elif fail=='duplicate':
        post(c,a,'/remboursements',{'retour_id':r['id'],'session_id':s['id'],'revision':s['revision'],'reglements':[{'mode':'ESPECES','montant':r['montant']}],'justification':'Doublon'},409)
    else:post(c,a,f'/remboursements/{d["id"]}/executer',{'revision':d['revision'],'justification':'Essai refusé','preuves':[{}]},422 if fail=='pdf' else 409)
    assert c.get(cash_root(a)+f'/fidelite/{ca["id"]}').json()['points']==3
    assert stocks(c,a)[0]['physique']==7
    assert next(x for x in c.get(root(a)+'/remboursements').json()['items'] if x['id']==d['id'])['etat']=='AUTORISE'

def test_dette_points_et_quarantaine_non_reservable(raw_client,account):
    c,a=raw_client,account;v,s,prod,pack,pid,*_=setup45(c,a);ca=cash_post(c,a,'/fidelite',{'nom':'Dette historique'});rule(c,a,category(c,a,prod));e=final(c,a,v,s,compte_id=ca['id'],revision_compte=ca['revision'])
    # A compensated historical use is represented explicitly, not a live monetary redemption.
    gen=db(c);dbs=next(gen)
    try:
        account_=dbs.get(CompteFideliteModel,UUID(ca['id']));account_.points=0;dbs.commit()
    finally:gen.close()
    r=ret(c,a,e,3);refund(c,a,r,s)
    ca_=c.get(cash_root(a)+f'/fidelite/{ca["id"]}').json();assert ca_['dette']==3 and ca_['points']==0
    # Physical quarantine contains 3; the only reservable stock remains 7.
    v2=create(c,a,pid);from test_vente import post as vente_post
    vente_post(c,a,f'/{v2["id"]}/lignes',{'revision':v2['revision'],'produit_id':prod,'conditionnement_id':pack,'quantite':8},409)
    assert stocks(c,a)[0]['physique']==7 and stocks(c,a)[0]['reserve']==0

@pytest.mark.parametrize('state',['inactive','expired','future','no_assignment','no_role','no_permission','no_location'])
def test_refus_affectations_p45_http(raw_client,account,state):
    c,a=raw_client,account;v,s,*_=setup45(c,a)
    from test_http_autorisations_p1 import set_state
    set_state(c,a,state)
    post(c,a,'/fonds',{'session_id':s['id'],'revision':s['revision'],'sens':'ENTREE','montant':1,'justification':'Interdit'},403)

@pytest.mark.parametrize('race',['z_checkout','return','refund','z_duplicate'])
def test_concurrence_postgresql_p45(raw_client,account,race):
    c,a=raw_client,account;v,session,*_=setup45(c,a);gen=db(c);dbs=next(gen);engine=dbs.bind;gen.close()
    if engine.dialect.name!='postgresql':pytest.skip('Concurrence réelle PostgreSQL')
    period=c.get(root(a)+'/contexte').json()['periode'];e=None;r=None;d=None
    if race in ('return','refund'):e=final(c,a,v,session)
    if race=='refund':
        r=ret(c,a,e,3);s=current(c,a,session);d=post(c,a,'/remboursements',{'retour_id':r['id'],'session_id':s['id'],'revision':s['revision'],'reglements':[{'mode':'ESPECES','montant':r['montant']}],'justification':'Retour concurrent'});d=post(c,a,f'/remboursements/{d["id"]}/autoriser',{'revision':d['revision'],'justification':'Autorisé'},200)
    if race=='z_duplicate':close(c,a,session)
    if race=='return':info=c.get(root(a)+f'/recus/{e["id"]}/retournable').json()['lignes'][0]
    def worker(i):
        with Session(engine) as dbs:
            stock=StockService(dbs,a['org'],a['user'],lambda *args:None);vente=VenteService(stock,a['site']);cash=CaisseService(vente);service=RegularisationService(cash)
            def action():
                if race=='return':return service.retour({'encaissement_id':UUID(e['id']),'lignes':[{'ligne_id':UUID(info['ligne_id']),'stock_id':UUID(info['stock_id']),'quantite':3}],'justification':'Retour concurrent'})
                if race=='refund':return service.refund_action(UUID(d['id']),{'revision':d['revision'],'justification':'Restitution réelle','preuves':[{}]},'executer')
                if race=='z_duplicate' or i==0:return service.cloture_z({'periode_id':UUID(period['id']),'justification':'Z concurrente'})
                return cash.finaliser(UUID(v['id']),{'revision':v['revision'],'session_id':UUID(session['id']),'revision_session':session['revision'],'reglements':[{'mode':'ESPECES','montant':400}],'points_utilises':0,'consentement':False,'compte_id':None,'revision_compte':None})
            try:stock.operation(uuid4(),'RACE:'+race,{'worker':i},action);return 'ok'
            except (ValueError,PermissionError,DBAPIError,ConflitStock):return 'refus'
    with ThreadPoolExecutor(max_workers=2) as pool:results=list(pool.map(worker,[0,1]))
    assert sorted(results)==['ok','refus']
    if race=='z_checkout':assert c.get(cash_root(a)+f'/ventes/{v["id"]}').json()['etat']=='ENCAISSEE'
    if race=='return':assert len(c.get(root(a)+'/retours').json()['items'])==1
    if race=='refund':assert current(c,a,session)['especes_attendues']=='1000'

def test_migration_p45_cycle_permissions_et_integrite(tmp_path,monkeypatch):
    from alembic import command
    from alembic.config import Config
    from sqlalchemy import create_engine
    from neosys_pharma.infrastructure.config import get_settings
    url=os.getenv('TEST_MIGRATION_DATABASE_URL',f'sqlite:///{tmp_path / "p45.db"}');monkeypatch.setenv('DATABASE_URL',url);get_settings.cache_clear();cfg=Config('alembic.ini')
    try:
        command.upgrade(cfg,'head');command.check(cfg)
        with create_engine(url).connect() as dbs:
            assert dbs.scalar(text("SELECT count(*) FROM permissions WHERE code='caisse.cloture.z'"))==1
            assert dbs.scalar(text("SELECT count(*) FROM roles_permissions rp JOIN permissions p ON p.id_permission=rp.permission_id WHERE p.code='caisse.cloture.z'"))==0
        command.downgrade(cfg,'c3f86f44c4cd');command.upgrade(cfg,'head');command.check(cfg)
    finally:get_settings.cache_clear()
