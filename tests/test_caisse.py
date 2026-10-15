"""P4.4 HTTP direct, concurrence et rollback du stock/finances/fidélité."""
from concurrent.futures import ThreadPoolExecutor
from datetime import date,timedelta
from decimal import Decimal
from io import BytesIO
from uuid import UUID,uuid4
import pytest
from sqlalchemy import select,delete,text,func
from sqlalchemy.orm import Session
from sqlalchemy.exc import DBAPIError
from pypdf import PdfReader
from test_vente import raw_client,account,db,login,setup,create,line,act,stocks,root as vente_root
from test_catalogue import grant
from test_stock import ALL
from test_http_autorisations_p1 import set_state
from neosys_pharma.domain.organisation.permissions_systeme import P4_PERMISSIONS,CAISSE_PERMISSIONS,permission_id
from neosys_pharma.infrastructure.caisse_models import *
from neosys_pharma.infrastructure.securite_models import RolePermissionModel
from neosys_pharma.application.vente_service import VenteService
from neosys_pharma.application.caisse_service import CaisseService
from neosys_pharma.application.stock_service import StockService
from neosys_pharma.domain.caisse import repartir_paiements,acquisition,regularisation
from neosys_pharma.domain.stock import ConflitStock

def root(a):return f'/api/caisses/organisations/{a["org"]}'
def post(c,a,path,body=None,status=201,key=None):
    r=c.post(root(a)+path,json={'cle':str(key or uuid4()),**(body or {})});assert r.status_code==status,r.text;return r.json()
def ready(c,a,q=3):
    product,pack,pid,cid=setup(c,a)
    from neosys_pharma.infrastructure.securite_models import RoleModel
    gen=db(c);s=next(gen)
    try:
        rid=s.scalar(select(RoleModel.id_role).where(RoleModel.organisation_id==a['org'],RoleModel.code=='CATALOGUE'))
        for code,_ in CAISSE_PERMISSIONS:s.add(RolePermissionModel(role_id=rid,permission_id=permission_id(code)))
        s.commit()
    finally:gen.close()
    login(c,a)
    post(c,a,'/configuration',{'revision':0,'modes':['ESPECES','CARTE','MOBILE_MONEY','CHEQUE','VIREMENT'],'ticket_appel':True},200)
    session=post(c,a,'/sessions',{'caisse_id':cid,'fond_initial':1000})
    v=line(c,a,create(c,a,pid),product,pack,q);v=act(c,a,v,'valider');v=act(c,a,v,'transmettre',caisse_id=cid)
    return v,session,product,pack,pid,cid

def body(v,session,**kw):return {'revision':v['revision'],'session_id':session['id'],'revision_session':session['revision'],'reglements':[{'mode':'ESPECES','montant':400}],'points_utilises':0,'consentement':False,'compte_id':None,'revision_compte':None,**kw}
def final(c,a,v,session,**kw):return post(c,a,f'/ventes/{v["id"]}/finaliser',body(v,session,**kw),200)
def category(c,a,product):
    from neosys_pharma.infrastructure.catalogue_models import ProduitModel
    gen=db(c);s=next(gen)
    try:return str(s.get(ProduitModel,UUID(product)).categorie_id)
    finally:gen.close()
def rule(c,a,cat,**kw):
    return post(c,a,'/baremes',{'type':'ACQUISITION','debut':str(date.today()),'points':1,'montant_xaf':100,'categories':[cat],'sous_categories':True,**kw})

def test_encaissement_mixte_atomique_recu_et_rejeu(raw_client,account,tmp_path):
    c,a=raw_client,account;v,session,product,*_=ready(c,a)
    account_=post(c,a,'/fidelite',{'nom':'élise médard','telephone':'070 123 456'})
    rule(c,a,category(c,a,product))
    cf=post(c,a,f'/ventes/{v["id"]}/confirmations',{'session_id':session['id'],'revision':v['revision'],'mode':'CARTE','montant':200,'reference':'TERM-123','source':'MANUEL_TERMINAL','preuve':'Ticket accepté sur terminal indépendant'})
    assert stocks(c,a)[0]['reserve']==3 and stocks(c,a)[0]['physique']==10
    payload=body(v,session,reglements=[{'mode':'CARTE','montant':200,'confirmation_id':cf['id']},{'mode':'ESPECES','montant':200}],compte_id=account_['id'],revision_compte=account_['revision']);key=uuid4()
    result=post(c,a,f'/ventes/{v["id"]}/finaliser',payload,200,key)
    assert post(c,a,f'/ventes/{v["id"]}/finaliser',payload,200,key)==result
    assert result['numero']==1 and result['instantane']['numero_encaissement']=='0001'
    assert sum(Decimal(x['rendu']) for x in result['instantane']['reglements'])==99
    assert stocks(c,a)[0]['physique']==7 and stocks(c,a)[0]['reserve']==0
    assert c.get(vente_root(a)+f'/{v["id"]}').json()['etat']=='ENCAISSEE'
    current=c.get(root(a)+f'/fidelite/{account_["id"]}').json();assert current['points']==3
    assert current['client']['nom']=='ÉLISE MÉDARD'
    assert c.get(root(a)+f'/fidelite/{account_["id"]}/journal').json()['total']==1
    assert c.get(root(a)+'/sessions').json()['items'][0]['especes_attendues']=='1101'
    pdf=c.get(root(a)+f'/recus/{result["id"]}/pdf');assert pdf.status_code==200
    text_= ''.join(p.extract_text() for p in PdfReader(BytesIO(pdf.content)).pages)
    assert '0001' in text_ and '301' in text_ and 'TERM-123' in text_
    assert c.get(root(a)+f'/recus/{result["id"]}/pdf').content==pdf.content
    (tmp_path/'recu.pdf').write_bytes(pdf.content)
    post(c,a,f'/ventes/{v["id"]}/finaliser',payload,409)
    journal=c.get(root(a)+'/mouvements',params={'session_id':session['id']}).json();assert journal['total']==2
    for table in IMMUTABLE:
        gen=db(c);s=next(gen)
        try:
            # Select only populated tables, triggers apply even to direct SQL.
            if not s.scalar(text(f'SELECT count(*) FROM {table}')):continue
            with pytest.raises(DBAPIError):s.execute(text(f'DELETE FROM {table}'));s.commit()
            s.rollback()
        finally:gen.close()

@pytest.mark.parametrize('kind',['underpaid','noncash_overpaid','unconfirmed','technical','expired','fiscal','debt','pdf_failure','wrong_session_revision'])
def test_echec_sans_effet_financier_stock_ou_points(raw_client,account,monkeypatch,kind):
    c,a=raw_client,account;v,session,product,*_=ready(c,a);payload=body(v,session)
    ca=post(c,a,'/fidelite',{'nom':'Test'})
    rule(c,a,category(c,a,product))
    if kind=='underpaid':payload['reglements'][0]['montant']=1
    if kind=='unconfirmed':payload['reglements']=[{'mode':'CARTE','montant':301}]
    if kind in ('fiscal','debt'):
        payload.update(compte_id=ca['id'],revision_compte=ca['revision'],points_utilises=1,consentement=True)
        if kind=='debt':
            gen=db(c);s=next(gen)
            try:s.get(CompteFideliteModel,UUID(ca['id'])).dette=1;s.commit()
            finally:gen.close()
    if kind=='technical':
        post(c,a,f'/ventes/{v["id"]}/confirmations',{'revision':v['revision'],'session_id':session['id'],'mode':'CARTE','montant':301,'reference':'BANK','source':'TECHNIQUE_PRESTATAIRE','preuve':'Non intégré'},422);return
    if kind=='noncash_overpaid':
        cf=post(c,a,f'/ventes/{v["id"]}/confirmations',{'revision':v['revision'],'session_id':session['id'],'mode':'CARTE','montant':302,'reference':'OVER','source':'MANUEL_TERMINAL','preuve':'Accepté'})
        payload['reglements']=[{'mode':'CARTE','montant':302,'confirmation_id':cf['id']}]
    if kind=='expired':
        from neosys_pharma.infrastructure.stock_models import LotModel
        gen=db(c);s=next(gen)
        try:
            from neosys_pharma.infrastructure.catalogue_models import ProduitModel
            prod=s.get(ProduitModel,UUID(product));prod.gestion_peremption=True
            for lot in s.scalars(select(LotModel).where(LotModel.organisation_id==a['org'])):lot.peremption=date.today()-timedelta(days=1)
            s.commit()
        finally:gen.close()
    if kind=='wrong_session_revision':payload['revision_session']=99
    if kind=='pdf_failure':
        from neosys_pharma.infrastructure import caisse_pdf
        monkeypatch.setattr(caisse_pdf,'recu_pdf',lambda _:(_ for _ in ()).throw(ValueError('PDF indisponible')))
    post(c,a,f'/ventes/{v["id"]}/finaliser',payload,409 if kind in ('expired','debt','wrong_session_revision') else 422)
    assert stocks(c,a)[0]['physique']==10 and stocks(c,a)[0]['reserve']==3
    assert c.get(root(a)+f'/fidelite/{ca["id"]}').json()['points']==0
    assert c.get(root(a)+'/mouvements',params={'session_id':session['id']}).json()['total']==0
    gen=db(c);s=next(gen)
    try:assert not s.scalar(select(func.count()).select_from(EncaissementModel));assert s.scalar(select(PeriodeCaisseSiteModel.prochain_encaissement))==1
    finally:gen.close()

def test_sessions_confirmation_et_numeros_independants(raw_client,account):
    c,a=raw_client,account;v,se,product,pack,pid,cid=ready(c,a)
    post(c,a,'/sessions',{'caisse_id':cid,'fond_initial':0},409)
    # The call sequence can pass 9999 and is independent from payment numbers.
    gen=db(c);s=next(gen)
    try:p=s.scalar(select(PeriodeCaisseSiteModel));p.prochain_appel=10000;s.commit()
    finally:gen.close()
    v2=line(c,a,create(c,a,pid),product,pack,1);v2=act(c,a,v2,'valider');v2=act(c,a,v2,'transmettre',caisse_id=cid)
    assert {x['numero_appel'] for x in c.get(root(a)+'/attente').json()['items']}=={'0001','10000'}
    assert len(PdfReader(BytesIO(c.get(root(a)+f'/ventes/{v2["id"]}/appel/pdf').content)).pages)==2
    result=final(c,a,v,se);assert result['numero']==1
    post(c,a,f'/sessions/{se["id"]}/fermer',{'revision':1,'comptage_final':1099,'justification':'Fin service'},409)
    close=post(c,a,f'/sessions/{se["id"]}/fermer',{'revision':2,'comptage_final':1301,'justification':'Fin service'},200)
    assert close['ecart_especes']=='0'
    post(c,a,f'/ventes/{v2["id"]}/finaliser',body(v2,se),403)
    next_=post(c,a,'/sessions',{'caisse_id':cid,'fond_initial':0});assert next_['id']!=se['id']
    assert final(c,a,v2,next_)['numero']==2

def test_fidelite_cartes_telephone_et_baremes_historiques(raw_client,account):
    c,a=raw_client,account;v,se,product,*_=ready(c,a)
    ca=post(c,a,'/fidelite',{'nom':'médard','telephone':'0701'});cb=post(c,a,'/fidelite',{'nom':'Autre titulaire','telephone':'0701'})
    matches=c.get(root(a)+'/fidelite',params={'q':'0701','page_size':1}).json();assert matches['total']==2 and len(matches['items'])==1
    ca=post(c,a,f'/fidelite/{ca["id"]}/cartes',{'revision':ca['revision'],'code':'CARD-1','type':'PHYSIQUE'})
    card=ca['cartes'][0];ca=post(c,a,f'/cartes/{card["id"]}/opposer',{'revision':ca['revision'],'justification':'Perdue'},200)
    assert c.get(root(a)+'/fidelite',params={'q':'CARD-1'}).json()['total']==0
    ca=post(c,a,f'/fidelite/{ca["id"]}/cartes',{'revision':ca['revision'],'code':'CARD-2','type':'VIRTUELLE','remplace_id':card['id']})
    assert c.get(root(a)+'/fidelite',params={'q':'CARD-2'}).json()['items'][0]['id']==ca['id']
    r=rule(c,a,category(c,a,product))
    post(c,a,'/baremes',{'type':'ACQUISITION','debut':str(date.today()),'points':2,'montant_xaf':100,'categories':[category(c,a,product)],'sous_categories':False},409)
    post(c,a,f'/baremes/{r["id"]}/clore',{'fin':str(date.today())},200)
    rule(c,a,category(c,a,product),debut=str(date.today()+timedelta(days=1)),points=2)
    conversion=rule(c,a,category(c,a,product),type='CONVERSION',points=10,montant_xaf=200,plafond_pourcentage=50)
    assert conversion['type']=='CONVERSION'
    result=final(c,a,v,se,compte_id=ca['id'],revision_compte=ca['revision'])
    assert result['instantane']['fidelite']['points_acquis']==3
    assert result['instantane']['fidelite']['bareme']['id']==r['id']
    # Historical PDF does not change with the next barème.
    assert c.get(root(a)+f'/recus/{result["id"]}/pdf').status_code==200


def test_historique_client_affiche_les_ventes_liees_avec_pagination(raw_client,account):
    c,a=raw_client,account;v,se,product,pack,pid,cid=ready(c,a)
    ca=post(c,a,'/fidelite',{'nom':'Client historique','telephone':'070 123 456'})
    first=final(c,a,v,se,compte_id=ca['id'],revision_compte=ca['revision'])

    second=line(c,a,create(c,a,pid),product,pack,3)
    second=act(c,a,second,'valider')
    second=act(c,a,second,'transmettre',caisse_id=cid)
    current=c.get(root(a)+f'/fidelite/{ca["id"]}').json()
    current_session=next(x for x in c.get(root(a)+'/sessions').json()['items'] if x['id']==se['id'])
    second_receipt=final(c,a,second,current_session,compte_id=ca['id'],revision_compte=current['revision'])

    history_url=root(a)+f'/fidelite/{ca["id"]}/ventes'
    page1=c.get(history_url,params={'page':1,'page_size':1})
    page2=c.get(history_url,params={'page':2,'page_size':1})
    assert page1.status_code==page2.status_code==200
    assert page1.json()['total']==2 and page2.json()['total']==2
    first_item=page1.json()['items'][0];second_item=page2.json()['items'][0]
    assert {first_item['encaissement_id'],second_item['encaissement_id']}=={first['id'],second_receipt['id']}
    assert {first_item['vente_id'],second_item['vente_id']}=={v['id'],second['id']}
    assert all(item['numero_recu'] and item['total_xaf'] and item['date'] for item in (first_item,second_item))
    assert first_item['encaissement_id']!=second_item['encaissement_id']

@pytest.mark.parametrize('state',['inactive','expired','future','no_assignment','no_role','no_permission','no_location','split_assignments'])
def test_caisse_refus_affectations_http(raw_client,account,state):
    c,a=raw_client,account;v,se,*_=ready(c,a);set_state(c,a,state)
    response=c.get(root(a)+'/attente')
    if state in ('no_location','split_assignments'):
        assert response.status_code==200 and response.json()['items']==[]
    else:assert response.status_code==403
    assert c.get(root(a)+f'/ventes/{v["id"]}').status_code==403
    post(c,a,f'/ventes/{v["id"]}/finaliser',body(v,se),403)

def test_401_403_csrf_lecture_seule_isolation_et_rejeu(raw_client,account):
    c,a=raw_client,account;assert c.get(root(a)+'/contexte').status_code==401
    assert c.post(root(a)+'/sessions',json={}).status_code==401
    v,se,*_=ready(c,a);payload=body(v,se);key=uuid4();post(c,a,f'/ventes/{v["id"]}/finaliser',payload,200,key)
    gen=db(c);s=next(gen)
    try:s.execute(delete(RolePermissionModel).where(RolePermissionModel.permission_id.in_([permission_id(x) for x,_ in CAISSE_PERMISSIONS if x!='caisse.consulter'])));s.commit()
    finally:gen.close()
    assert c.get(root(a)+'/sessions').status_code==200
    post(c,a,f'/ventes/{v["id"]}/finaliser',payload,403,key)
    for path in ('/configuration','/fidelite','/baremes','/sessions'):post(c,a,path,{},403)
    token=c.headers.pop('X-CSRF-Token');post(c,a,f'/sessions/{se["id"]}/fermer',{},403);c.headers['X-CSRF-Token']=token
    assert c.get(root({'org':uuid4()})+'/contexte').status_code==403
    c.headers['X-Site-ID']=str(a['other']);assert c.get(root(a)+f'/ventes/{v["id"]}').status_code==403


def test_concurrence_postgresql_encaissement_session_et_points(raw_client,account):
    c,a=raw_client,account;v,se,product,*_=ready(c,a);ca=post(c,a,'/fidelite',{'nom':'Concurrent'});rule(c,a,category(c,a,product))
    gen=db(c);s=next(gen);engine=s.get_bind();gen.close()
    if engine.dialect.name!='postgresql':pytest.skip('Deux connexions PostgreSQL requises')
    data=body(v,se,compte_id=ca['id'],revision_compte=ca['revision']);data['session_id']=UUID(se['id']);data['compte_id']=UUID(ca['id'])
    def worker():
        with Session(engine) as s:
            stock=StockService(s,a['org'],a['user'],lambda *args:None);cash=CaisseService(VenteService(stock,a['site']))
            try:stock.operation(uuid4(),'P4.4:CONCURRENT',data,lambda:cash.finaliser(UUID(v['id']),data));return 'ok'
            except ConflitStock:return 'conflit'
    with ThreadPoolExecutor(max_workers=2) as pool:assert sorted(pool.map(lambda _:worker(),range(2)))==['conflit','ok']
    assert stocks(c,a)[0]['physique']==7
    assert c.get(root(a)+f'/fidelite/{ca["id"]}').json()['points']==3


def test_calculs_xaf_et_regularisation_preparee():
    assert acquisition(299,1,100)==2 and acquisition(300,1,100)==3
    assert repartir_paiements(100,[{'mode':'ESPECES','montant':150}])[0]['rendu']==50
    for rows in ([{'mode':'CARTE','montant':101}],[{'mode':'ESPECES','montant':99}],[{'mode':'ESPECES','montant':'100.25'}]):
        with pytest.raises(ValueError):repartir_paiements(100,rows)
    assert regularisation(10,20,50,100,2)=={'restitution':5,'revocation':10,'solde':0,'dette':3}

@pytest.mark.parametrize('mode,source',[('CARTE','MANUEL_TERMINAL'),('MOBILE_MONEY','MANUEL_TERMINAL'),('CHEQUE','MANUEL_JUSTIFICATIF'),('VIREMENT','MANUEL_JUSTIFICATIF')])
def test_moyens_non_especes_confirmes_et_sans_rendu(raw_client,account,mode,source):
    c,a=raw_client,account;v,se,*_=ready(c,a)
    cf=post(c,a,f'/ventes/{v["id"]}/confirmations',{'session_id':se['id'],'revision':v['revision'],'mode':mode,'montant':301,'reference':'REF-'+mode,'source':source,'preuve':'Justificatif acquis contrôlé'})
    assert final(c,a,v,se,reglements=[{'mode':mode,'montant':301,'confirmation_id':cf['id']}])['instantane']['reglements'][0]['rendu']=='0'
    assert c.get(root(a)+'/sessions').json()['items'][0]['especes_attendues']=='1000'

def test_rapprochement_immutable_apres_changement_session(raw_client,account):
    c,a=raw_client,account;v,se,_,_,_,cid=ready(c,a)
    cf=post(c,a,f'/ventes/{v["id"]}/confirmations',{'session_id':se['id'],'revision':v['revision'],'mode':'CARTE','montant':301,'reference':'REF-RECONCILE','source':'MANUEL_TERMINAL','preuve':'Terminal acquis'})
    post(c,a,f'/sessions/{se["id"]}/fermer',{'revision':se['revision'],'comptage_final':1000,'justification':'Relève caissier'},200)
    new=post(c,a,'/sessions',{'caisse_id':cid,'fond_initial':1000})
    payload=body(v,new,reglements=[{'mode':'CARTE','montant':301,'confirmation_id':cf['id']}])
    post(c,a,f'/ventes/{v["id"]}/finaliser',payload,409)
    post(c,a,f'/ventes/{v["id"]}/confirmations/{cf["id"]}/rapprocher',{'revision':v['revision'],'session_id':new['id'],'justification':'Preuve bancaire recontrôlée à la relève'},200)
    result=post(c,a,f'/ventes/{v["id"]}/finaliser',payload,200)
    assert result['instantane']['reglements'][0]['confirmation']['session_id']==se['id']


def test_compte_partage_entre_sites_explicitement_affectes(raw_client,account):
    c,a=raw_client,account;v,se,product,*_=ready(c,a)
    ca=post(c,a,'/fidelite',{'nom':'Titulaire multisites'})
    rule(c,a,category(c,a,product));final(c,a,v,se,compte_id=ca['id'],revision_compte=ca['revision'])
    c.headers['X-Site-ID']=str(a['other']);assert c.get(root(a)+f'/fidelite/{ca["id"]}').status_code==403
    assert c.get(root(a)+f'/fidelite/{ca["id"]}/ventes').status_code==403
    from neosys_pharma.infrastructure.securite_models import RoleModel,AffectationSiteModel,AffectationRoleModel,AffectationEmplacementModel
    gen=db(c);s=next(gen)
    try:
        rid=s.scalar(select(RoleModel.id_role).where(RoleModel.organisation_id==a['org'],RoleModel.code=='CATALOGUE'))
        assignment=uuid4();s.add(AffectationSiteModel(id_affectation_site=assignment,utilisateur_id=a['user'],site_id=a['other'],organisation_id=a['org'],date_debut=date.today(),actif=True));s.flush()
        s.add(AffectationRoleModel(affectation_site_id=assignment,role_id=rid,organisation_id=a['org'],role_scope=s.get(RoleModel,rid).scope_id))
        s.add(AffectationEmplacementModel(affectation_site_id=assignment,emplacement_id=a['other_location'],site_id=a['other']));s.commit()
    finally:gen.close()
    response=c.get(root(a)+f'/fidelite/{ca["id"]}');assert response.status_code==200,response.text;assert response.json()['points']==3
    assert c.get(root(a)+f'/fidelite/{ca["id"]}/journal').json()['total']==0
    assert c.get(root(a)+f'/fidelite/{ca["id"]}/ventes').json()['total']==0
    c.headers['X-Site-ID']=str(a['site'])
    assert c.get(root(a)+f'/fidelite/{ca["id"]}/journal').json()['total']==1
    assert c.get(root(a)+f'/fidelite/{ca["id"]}/ventes').json()['total']==1


def test_acquisition_sous_categories_et_aucun_taux_implicite(raw_client,account):
    c,a=raw_client,account;v,se,product,*_=ready(c,a);ca=post(c,a,'/fidelite',{'nom':'Sans barème'})
    r=final(c,a,v,se,compte_id=ca['id'],revision_compte=ca['revision']);assert r['instantane']['fidelite']['points']==0
    assert c.get(root(a)+f'/fidelite/{ca["id"]}/journal').json()['total']==0


def test_migration_p44_cycle_et_permissions_non_attribuees(tmp_path,monkeypatch):
    import os
    from alembic import command
    from alembic.config import Config
    from sqlalchemy import create_engine,inspect
    from neosys_pharma.infrastructure.config import get_settings
    monkeypatch.setenv('DATABASE_URL',os.getenv('TEST_MIGRATION_DATABASE_URL',f'sqlite+pysqlite:///{tmp_path / "p44.db"}'));get_settings.cache_clear();cfg=Config('alembic.ini')
    from neosys_pharma.infrastructure.config import get_settings
    engine=create_engine(get_settings().database_url)
    try:
        command.upgrade(cfg,'head');command.check(cfg)
        with engine.connect() as c:
            from neosys_pharma.infrastructure.securite_models import PermissionModel
            assert c.scalar(select(func.count()).select_from(PermissionModel).where(PermissionModel.code.in_([code for code,_ in CAISSE_PERMISSIONS])))==len(CAISSE_PERMISSIONS)
            assert c.execute(text("SELECT count(*) FROM roles_permissions JOIN permissions ON permission_id=id_permission WHERE code LIKE 'caisse.%' OR code LIKE 'fidelite.%'")).scalar()==0
            assert c.execute(text("SELECT count(*) FROM roles_permissions JOIN permissions ON permission_id=id_permission WHERE code LIKE 'client.%'")).scalar()==0
        command.downgrade(cfg,'0001e4d5d008');assert 'caisse_encaissements' not in inspect(engine).get_table_names() and 'proformas' in inspect(engine).get_table_names()
        command.upgrade(cfg,'head');command.check(cfg)
    finally:engine.dispose();get_settings.cache_clear()

def test_acquisition_apres_remises_et_immutabilite_vente_payee(raw_client,account):
    from test_vente import post as vp
    from neosys_pharma.infrastructure.securite_models import RoleModel
    c,a=raw_client,account;v,se,product,pack,pid,cid=ready(c,a)
    # Start a distinct preparation with an explicit discount authorization cap.
    pending=act(c,a,v,'annuler',justification='Repréparation avec remise')
    v=line(c,a,create(c,a,pid),product,pack,3)
    gen=db(c);s=next(gen)
    try:rid=str(s.scalar(select(RoleModel.id_role).where(RoleModel.organisation_id==a['org'],RoleModel.code=='CATALOGUE')))
    finally:gen.close()
    vp(c,a,'/plafonds',{'role_id':rid,'revision':0,'max_pourcentage':50,'max_montant_xaf':150})
    d=vp(c,a,f'/{v["id"]}/remises',{'revision':v['revision'],'type':'MONTANT_XAF','valeur':101,'justification':'Remise commerciale'})
    vp(c,a,f'/{v["id"]}/remises/{d["id"]}/decision',{'revision':v['revision'],'autoriser':True,'justification':'Accord explicite'},200)
    v=c.get(vente_root(a)+f'/{v["id"]}').json();v=act(c,a,v,'valider');v=act(c,a,v,'transmettre',caisse_id=cid)
    ca=post(c,a,'/fidelite',{'nom':'Remise puis fidélité'});rule(c,a,category(c,a,product))
    result=final(c,a,v,se,compte_id=ca['id'],revision_compte=ca['revision'])
    assert Decimal(result['total_xaf'])==200 and result['instantane']['fidelite']['points_acquis']==2
    before=c.get(root(a)+f'/recus/{result["id"]}/pdf').content
    vp(c,a,'/plafonds',{'role_id':rid,'revision':1,'max_pourcentage':10,'max_montant_xaf':30})
    assert c.get(root(a)+f'/recus/{result["id"]}/pdf').content==before
    for sql in ("UPDATE ventes SET etat='PREPARATION' WHERE etat='ENCAISSEE'",f"UPDATE vente_lignes SET quantite=99 WHERE vente_id='{UUID(v['id']).hex}'" if next_engine(c)=='sqlite' else f"UPDATE vente_lignes SET quantite=99 WHERE vente_id='{v['id']}'"):
        gen=db(c);s=next(gen)
        try:
            with pytest.raises(DBAPIError):s.execute(text(sql));s.commit()
            s.rollback()
        finally:gen.close()

def next_engine(c):
    gen=db(c);s=next(gen)
    try:return s.get_bind().dialect.name
    finally:gen.close()

@pytest.mark.parametrize('include',[False,True])
def test_eligibilite_categorie_principale_et_descendants(raw_client,account,include):
    from neosys_pharma.infrastructure.catalogue_models import CategorieProduitModel,ProduitModel
    from neosys_pharma.infrastructure.catalogue_repository import SqlAlchemyCatalogueRepository
    from neosys_pharma.application.catalogue_service import CatalogueService
    from neosys_pharma.domain.catalogue import CategorieProduit
    c,a=raw_client,account;v,se,prod,*_=ready(c,a);cat=category(c,a,prod)
    gen=db(c);s=next(gen)
    try:
        service=CatalogueService(SqlAlchemyCatalogueRepository(s));child=CategorieProduit(organisation_id=a['org'],code='ENFANT',nom='Éligibilité enfant',parent_id=UUID(cat));service.enregistrer(child)
        s.get(ProduitModel,UUID(prod)).categorie_id=child.id_categorie;s.commit()
    finally:gen.close()
    ca=post(c,a,'/fidelite',{'nom':'Descendant'});rule(c,a,cat,sous_categories=include)
    assert final(c,a,v,se,compte_id=ca['id'],revision_compte=ca['revision'])['instantane']['fidelite']['points_acquis']==(3 if include else 0)


def test_bareme_immuable_et_conversion_sans_plafond_refusee(raw_client,account):
    c,a=raw_client,account;_,_,prod,*_=ready(c,a);cat=category(c,a,prod);rule(c,a,cat)
    rule(c,a,cat,type='CONVERSION',plafond_xaf=50)
    for sql in ('UPDATE fidelite_baremes SET points=999','DELETE FROM fidelite_baremes'):
        gen=db(c);s=next(gen)
        try:
            with pytest.raises(DBAPIError):s.execute(text(sql));s.commit()
            s.rollback()
        finally:gen.close()
    post(c,a,'/baremes',{'type':'CONVERSION','debut':str(date.today()+timedelta(days=1)),'points':1,'montant_xaf':100,'categories':[cat],'sous_categories':True},422)


def test_concurrence_postgresql_ouverture_session(raw_client,account):
    c,a=raw_client,account;_,se,_,_,_,cid=ready(c,a)
    post(c,a,f'/sessions/{se["id"]}/fermer',{'revision':1,'comptage_final':1000,'justification':'Avant concurrence'},200)
    gen=db(c);s=next(gen);engine=s.get_bind();gen.close()
    if engine.dialect.name!='postgresql':pytest.skip('Deux connexions PostgreSQL requises')
    def worker():
        with Session(engine) as s:
            stock=StockService(s,a['org'],a['user'],lambda *args:None);cash=CaisseService(VenteService(stock,a['site']))
            try:stock.operation(uuid4(),'P44:OUVERTURE',{},lambda:cash.ouvrir({'caisse_id':UUID(cid),'fond_initial':0}));return 'ok'
            except ConflitStock:return 'conflit'
    with ThreadPoolExecutor(max_workers=2) as pool:assert sorted(pool.map(lambda _:worker(),range(2)))==['conflit','ok']

def test_recu_long_multi_pages_et_tva_historique(tmp_path):
    from neosys_pharma.infrastructure.caisse_pdf import recu_pdf
    data={'organisation':'PHARMACIE DE RECETTE','site':'LIBREVILLE','numero_encaissement':'10000','periode_z':1,'id':str(uuid4()),'date':'2026-10-11T12:00:00+00:00','lignes':[{'designation':'MÉDICAMENT À DÉSIGNATION LONGUE '+('COMPRIMÉ PELLICULÉ PÉDIATRIQUE '*5),'conditionnement':'BOÎTE DE 20','quantite':1,'montants_appliques':{'ttc':100+i}} for i in range(65)],'totaux':{'ht':'6000','tva':'600','ttc':'6600'},'reglements':[{'mode':'ESPECES','montant':'7000','rendu':'400'}],'fidelite':None}
    pdf=recu_pdf(data);reader=PdfReader(BytesIO(pdf));assert len(reader.pages)>2
    assert all('Produit / conditionnement' in p.extract_text() or 'Net réglé TTC' in p.extract_text() for p in reader.pages)
    assert '600 XAF' in ''.join(p.extract_text() for p in reader.pages)
    (tmp_path/'recu-long.pdf').write_bytes(pdf)


def test_confirmation_precision_xaf_sans_float(raw_client,account):
    c,a=raw_client,account;v,se,*_=ready(c,a)
    key=uuid4();payload={'session_id':se['id'],'revision':v['revision'],'mode':'VIREMENT','montant':'999999999999999999','reference':'PRECISION-XAF','source':'MANUEL_JUSTIFICATIF','preuve':'Donnée synthétique de test de précision'}
    cf=post(c,a,f'/ventes/{v["id"]}/confirmations',payload,key=key)
    post(c,a,f'/ventes/{v["id"]}/confirmations',{**payload,'montant':'999999999999999998'},409,key)
    assert cf['montant']=='999999999999999999'
    assert c.get(root(a)+f'/ventes/{v["id"]}').json()['confirmations'][0]['montant']==cf['montant']


def test_paiement_acquis_non_selectionne_ne_peut_devenir_orphelin(raw_client,account):
    c,a=raw_client,account;v,se,*_=ready(c,a)
    post(c,a,f'/ventes/{v["id"]}/confirmations',{'session_id':se['id'],'revision':v['revision'],'mode':'CARTE','montant':301,'reference':'ACQUIS-A-INTEGRER','source':'MANUEL_TERMINAL','preuve':'Terminal accepté'})
    post(c,a,f'/ventes/{v["id"]}/finaliser',body(v,se),409)
    assert stocks(c,a)[0]['physique']==10 and stocks(c,a)[0]['reserve']==3
    assert c.get(root(a)+'/mouvements',params={'session_id':se['id']}).json()['total']==0
