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
    # Les anciens scénarios financiers choisissent désormais un moyen créé
    # explicitement par leur utilisateur de recette, sans seed applicatif.
    if path.endswith('/confirmations') and body and body.get('mode')!='ESPECES' and 'moyen_id' not in body and status==201:
        mode=body['mode'];code='RECETTE_'+mode
        moyens=c.get(root(a)+'/contexte').json()['configuration']['moyens']
        moyen=next((m for m in moyens if m['code']==code),None)
        if moyen is None:
            moyen=post(c,a,'/moyens',{'code':code,'libelle':'Recette '+mode,'mode':mode})
        body={**body,'moyen_id':moyen['id']}
    r=c.post(root(a)+path,json={'cle':str(key or uuid4()),**(body or {})});assert r.status_code==status,r.text;return r.json()
def ready(c,a,q=3,*,configure=True):
    product,pack,pid,cid=setup(c,a)
    from neosys_pharma.infrastructure.catalogue_models import ProduitModel,NatureMedicamentModel
    gen=db(c);s=next(gen)
    try:
        nature=s.scalar(select(NatureMedicamentModel).where(
            NatureMedicamentModel.organisation_id==a['org'],NatureMedicamentModel.code=='COSMETIQUE'))
        if not nature:
            nature=NatureMedicamentModel(id_nature=uuid4(),organisation_id=a['org'],code='COSMETIQUE',nom='Cosmétique',actif=True)
            s.add(nature);s.flush()
        s.get(ProduitModel,UUID(product)).nature_id=nature.id_nature;s.commit()
    finally:gen.close()
    from neosys_pharma.infrastructure.securite_models import RoleModel
    gen=db(c);s=next(gen)
    try:
        rid=s.scalar(select(RoleModel.id_role).where(RoleModel.organisation_id==a['org'],RoleModel.code=='CATALOGUE'))
        for code,_ in CAISSE_PERMISSIONS:s.add(RolePermissionModel(role_id=rid,permission_id=permission_id(code)))
        s.commit()
    finally:gen.close()
    login(c,a)
    if configure:
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
# P4-C.3a : brouillons, révisions, règlements et ventilations sans finalisation.
def groupe_post(client, account, path, body, status=200):
    response = client.post(root(account) + "/groupes" + path, json=body)
    assert response.status_code == status, response.text
    return response.json()


def groupe_put(client, account, path, body, status=200):
    response = client.put(root(account) + "/groupes" + path, json=body)
    assert response.status_code == status, response.text
    return response.json()


def prepare_group_for_sale(client, account, sale, session):
    draft = groupe_post(client, account, "", {"cle": str(uuid4()), "session_id": session["id"]}, 201)
    group_id = draft["dossier"]["id"]
    draft = groupe_put(client, account, f"/{group_id}/ventes", {
        "cle": str(uuid4()), "revision": draft["dossier"]["revision"],
        "ventes": [{"vente_id": sale["id"], "revision": sale["revision"]}],
    })
    due = Decimal(draft["ventes"][0]["montant_du"])
    draft = groupe_put(client, account, f"/{group_id}/reglements", {
        "cle": str(uuid4()), "revision": draft["dossier"]["revision"],
        "reglements": [{"mode": "ESPECES", "montant": str(due)}],
    })
    allocations = client.get(root(account) + f"/groupes/{group_id}/allocations/proposition", params={
        "revision": draft["dossier"]["revision"],
    }).json()
    draft = groupe_put(client, account, f"/{group_id}/allocations", {
        "cle": str(uuid4()), "revision": draft["dossier"]["revision"],
        "allocations": allocations,
    })
    return group_id, draft


def test_brouillon_groupe_multi_ventes_allocations_et_abandon(raw_client, account):
    client, a = raw_client, account
    from neosys_pharma.presentation.encaissement_groupe_api import (
        GROUPED_ENCASHMENT_ENABLED,
        router as grouped_router,
    )
    assert GROUPED_ENCASHMENT_ENABLED is False
    assert any(route.path.endswith("/{dossier_id}/finaliser") for route in grouped_router.routes)
    first, session, product, pack, post_id, caisse_id = ready(client, a, q=3)
    assert client.get(root(a) + "/groupes/activation").json() == {"finalisation_active": False}
    second = line(client, a, create(client, a, post_id), product, pack, q=2)
    second = act(client, a, second, "valider")
    second = act(client, a, second, "transmettre", caisse_id=caisse_id)

    key = str(uuid4())
    dossier = groupe_post(client, a, "", {"cle": key, "session_id": session["id"]}, 201)
    assert groupe_post(client, a, "", {"cle": key, "session_id": session["id"]}, 201) == dossier
    conflict = client.post(root(a) + "/groupes", json={
        "cle": key, "session_id": str(uuid4()),
    })
    assert conflict.status_code == 409
    assert dossier["dossier"]["etat"] == "BROUILLON"
    initial_revision = dossier["dossier"]["revision"]

    dossier_id = dossier["dossier"]["id"]
    dossier = groupe_put(client, a, f"/{dossier_id}/ventes", {
        "cle": str(uuid4()), "revision": initial_revision,
        "ventes": [
            {"vente_id": first["id"], "revision": first["revision"]},
            {"vente_id": second["id"], "revision": second["revision"]},
        ],
    })
    stale = client.put(root(a) + f"/groupes/{dossier_id}/ventes", json={
        "cle": str(uuid4()), "revision": initial_revision, "ventes": [],
    })
    assert stale.status_code == 409
    due = sum(Decimal(row["montant_du"]) for row in dossier["ventes"])
    dossier = groupe_put(client, a, f"/{dossier_id}/reglements", {
        "cle": str(uuid4()), "revision": dossier["dossier"]["revision"],
        "reglements": [{"mode": "ESPECES", "montant": str(due)}],
    })
    suggestion = client.get(root(a) + f"/groupes/{dossier_id}/allocations/proposition",
                            params={"revision": dossier["dossier"]["revision"]})
    assert suggestion.status_code == 200, suggestion.text
    allocations = suggestion.json()
    assert [Decimal(row["montant"]) for row in allocations] == [
        Decimal(row["montant_du"]) for row in dossier["ventes"]
    ]
    assert sum(Decimal(row["montant"]) for row in allocations) == due

    dossier = groupe_put(client, a, f"/{dossier_id}/allocations", {
        "cle": str(uuid4()), "revision": dossier["dossier"]["revision"],
        "allocations": allocations,
    })
    assert dossier["totaux"]["allocation_valide"] is True
    assert Decimal(dossier["totaux"]["reste_xaf"]) == 0

    wrong = [dict(row) for row in allocations]
    wrong[0]["montant"] = str(Decimal(wrong[0]["montant"]) - 1)
    response = client.put(root(a) + f"/groupes/{dossier_id}/allocations", json={
        "cle": str(uuid4()), "revision": dossier["dossier"]["revision"],
        "allocations": wrong,
    })
    assert response.status_code == 422

    # Les brouillons et leurs allocations n'ont ni encaissé les ventes ni écrit en caisse.
    assert client.get(root(a) + f"/groupes/{dossier_id}").json()["dossier"]["etat"] == "BROUILLON"
    assert client.get(root(a) + "/mouvements", params={"session_id": session["id"]}).json()["total"] == 0
    gen = db(client)
    s = next(gen)
    try:
        assert s.scalar(select(EncaissementModel.id).where(
            EncaissementModel.vente_id.in_([UUID(first["id"]), UUID(second["id"])])
        )) is None
        assert s.scalar(select(MouvementCaisseModel.id).where(
            MouvementCaisseModel.session_id == UUID(session["id"])
        )) is None
    finally:
        gen.close()

    disabled = client.post(root(a) + f"/groupes/{dossier_id}/finaliser", json={
        "cle": str(uuid4()), "revision": dossier["dossier"]["revision"],
        "revision_session": session["revision"], "fidelite": [],
    })
    assert disabled.status_code == 503

    abandoned = groupe_post(client, a, f"/{dossier_id}/abandonner", {
        "cle": str(uuid4()), "revision": dossier["dossier"]["revision"],
    })
    assert abandoned["dossier"]["etat"] == "ABANDONNE"
    assert client.get(root(a) + f"/groupes/{dossier_id}").status_code == 200


def test_activation_groupe_reservee_a_la_recette_jetable(monkeypatch):
    from neosys_pharma.presentation.encaissement_groupe_api import _grouped_encashment_enabled

    monkeypatch.setenv("GROUPED_ENCASHMENT_ENABLED", "true")
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://user:password@localhost/neosys_browser")
    monkeypatch.setenv("CI", "false")
    monkeypatch.setenv("P4C4_CI_DISPOSABLE_DATABASE", "1")
    assert _grouped_encashment_enabled() is False
    monkeypatch.setenv("CI", "true")
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://user:password@localhost/neosys_pharma_v1")
    assert _grouped_encashment_enabled() is False
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://user:password@localhost/neosys_browser")
    monkeypatch.delenv("P4C4_CI_DISPOSABLE_DATABASE")
    assert _grouped_encashment_enabled() is False
    monkeypatch.setenv("P4C4_CI_DISPOSABLE_DATABASE", "1")
    assert _grouped_encashment_enabled() is True
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://user:password@db.example/neosys_browser")
    assert _grouped_encashment_enabled() is False
    monkeypatch.setenv("GROUPED_ENCASHMENT_ENABLED", "false")
    assert _grouped_encashment_enabled() is False


def test_brouillon_refuse_vente_deja_encaissee(raw_client, account):
    client, a = raw_client, account
    sale, session, *_ = ready(client, a, q=1)
    post(client, a, f"/ventes/{sale['id']}/finaliser", {
        "revision": sale["revision"], "session_id": session["id"],
        "revision_session": session["revision"],
        "reglements": [{"mode": "ESPECES", "montant": sale["totaux"]["ttc"]}],
        "points_utilises": 0, "consentement": False,
        "compte_id": None, "revision_compte": None,
    }, 200)
    paid_sale = client.get(vente_root(a) + f"/{sale['id']}").json()
    draft = groupe_post(client, a, "", {"cle": str(uuid4()), "session_id": session["id"]}, 201)
    result = groupe_put(client, a, f"/{draft['dossier']['id']}/ventes", {
        "cle": str(uuid4()), "revision": draft["dossier"]["revision"],
        "ventes": [{"vente_id": sale["id"], "revision": paid_sale["revision"]}],
    }, 409)
    assert "Seules les ventes transmises sont admissibles." == result["detail"]


def test_brouillon_confirme_reglement_non_especes(raw_client, account):
    client, a = raw_client, account
    first, session, product, pack, post_id, caisse_id = ready(client, a, q=3)
    second = line(client, a, create(client, a, post_id), product, pack, q=2)
    second = act(client, a, second, "valider")
    second = act(client, a, second, "transmettre", caisse_id=caisse_id)
    confirmation = post(client, a, f"/ventes/{first['id']}/confirmations", {
        "session_id": session["id"], "revision": first["revision"],
        "mode": "CARTE", "montant": 200, "reference": "TERMINAL-GROUPE-1",
        "source": "MANUEL_TERMINAL", "preuve": "Paiement autorisé par le terminal indépendant",
    })
    draft = groupe_post(client, a, "", {
        "cle": str(uuid4()), "session_id": session["id"],
    }, 201)
    dossier_id = draft["dossier"]["id"]
    draft = groupe_put(client, a, f"/{dossier_id}/ventes", {
        "cle": str(uuid4()), "revision": draft["dossier"]["revision"],
        "ventes": [
            {"vente_id": first["id"], "revision": first["revision"]},
            {"vente_id": second["id"], "revision": second["revision"]},
        ],
    })
    due = sum(Decimal(row["montant_du"]) for row in draft["ventes"])
    draft = groupe_put(client, a, f"/{dossier_id}/reglements", {
        "cle": str(uuid4()), "revision": draft["dossier"]["revision"],
        "reglements": [
            {"mode": "CARTE", "montant": 200, "confirmation_id": confirmation["id"]},
            {"mode": "ESPECES", "montant": str(due - 200)},
        ],
    })
    proposal = client.get(root(a) + f"/groupes/{dossier_id}/allocations/proposition", params={
        "revision": draft["dossier"]["revision"],
    })
    assert proposal.status_code == 200, proposal.text
    proposed = proposal.json()
    assert len(proposed) >= 2
    assert sum(Decimal(row["montant"]) for row in proposed) == due
    saved = groupe_put(client, a, f"/{dossier_id}/allocations", {
        "cle": str(uuid4()), "revision": draft["dossier"]["revision"],
        "allocations": proposed,
    })
    assert saved["totaux"]["allocation_valide"] is True


def test_finalisation_groupe_atomique_reçus_mouvements_fidelite_et_rejeu(
    raw_client, account, monkeypatch, tmp_path
):
    from neosys_pharma.presentation import encaissement_groupe_api

    monkeypatch.setattr(encaissement_groupe_api, "GROUPED_ENCASHMENT_ENABLED", True)
    client, a = raw_client, account
    first, session, product, pack, post_id, caisse_id = ready(client, a, q=3)
    second = line(client, a, create(client, a, post_id), product, pack, q=2)
    second = act(client, a, second, "valider")
    second = act(client, a, second, "transmettre", caisse_id=caisse_id)
    account_row = post(client, a, "/fidelite", {"nom": "Cliente du groupe"})
    rule(client, a, category(client, a, product))
    confirmation = post(client, a, f"/ventes/{first['id']}/confirmations", {
        "session_id": session["id"], "revision": first["revision"],
        "mode": "CARTE", "montant": 200, "reference": "GROUPE-TERM-01",
        "source": "MANUEL_TERMINAL", "preuve": "Autorisé par le terminal indépendant",
    })

    draft = groupe_post(client, a, "", {"cle": str(uuid4()), "session_id": session["id"]}, 201)
    group_id = draft["dossier"]["id"]
    draft = groupe_put(client, a, f"/{group_id}/ventes", {
        "cle": str(uuid4()), "revision": draft["dossier"]["revision"],
        "ventes": [
            {"vente_id": first["id"], "revision": first["revision"]},
            {"vente_id": second["id"], "revision": second["revision"]},
        ],
    })
    due = sum(Decimal(row["montant_du"]) for row in draft["ventes"])
    assert due == Decimal(502)
    draft = groupe_put(client, a, f"/{group_id}/reglements", {
        "cle": str(uuid4()), "revision": draft["dossier"]["revision"],
        "reglements": [
            {"mode": "CARTE", "montant": 200, "confirmation_id": confirmation["id"]},
            {"mode": "ESPECES", "montant": 350, "rendu": 48},
        ],
    })
    payments = {row["mode"]: row for row in draft["reglements"]}
    first_sale, second_sale = draft["ventes"]
    allocations = [
        {"reglement_id": payments["CARTE"]["id"], "vente_id": first_sale["vente_id"], "montant": "200"},
        {"reglement_id": payments["ESPECES"]["id"], "vente_id": first_sale["vente_id"], "montant": "101"},
        {"reglement_id": payments["ESPECES"]["id"], "vente_id": second_sale["vente_id"], "montant": "201"},
    ]
    draft = groupe_put(client, a, f"/{group_id}/allocations", {
        "cle": str(uuid4()), "revision": draft["dossier"]["revision"],
        "allocations": allocations,
    })
    assert draft["totaux"]["allocation_valide"] is True

    payload = {
        "cle": str(uuid4()),
        "revision": draft["dossier"]["revision"],
        "revision_session": session["revision"],
        "fidelite": [{"vente_id": first["id"], "compte_id": account_row["id"],
                      "revision_compte": account_row["revision"]}],
    }
    first_result = groupe_post(client, a, f"/{group_id}/finaliser", payload, 200)
    assert first_result["dossier"]["etat"] == "FINALISE"
    assert len(first_result["resultat"]["recus_individuels"]) == 2
    assert first_result["resultat"]["recu_collectif"]["reference"].startswith("G-")
    replay = client.post(root(a) + f"/groupes/{group_id}/finaliser", json=payload)
    assert replay.status_code == 200 and replay.json() == first_result
    changed = {**payload, "revision_session": session["revision"] + 1}
    assert client.post(root(a) + f"/groupes/{group_id}/finaliser", json=changed).status_code == 409

    assert client.get(vente_root(a) + f"/{first['id']}").json()["etat"] == "ENCAISSEE"
    assert client.get(vente_root(a) + f"/{second['id']}").json()["etat"] == "ENCAISSEE"
    assert stocks(client, a)[0]["physique"] == 5 and stocks(client, a)[0]["reserve"] == 0
    assert client.get(root(a) + f"/fidelite/{account_row['id']}").json()["points"] == 3
    assert client.get(root(a) + "/sessions").json()["items"][0]["especes_attendues"] == "1302"

    movements = client.get(root(a) + "/mouvements", params={"session_id": session["id"]}).json()
    assert movements["total"] == 2 and all(row["source"] == "GROUPE" for row in movements["items"])
    group_pdf = client.get(root(a) + f"/groupes/{group_id}/recu.pdf")
    assert group_pdf.status_code == 200
    (tmp_path / "recu-groupe.pdf").write_bytes(group_pdf.content)
    text_pdf = "".join(page.extract_text() for page in PdfReader(BytesIO(group_pdf.content)).pages)
    assert first_result["resultat"]["recu_collectif"]["reference"] in text_pdf
    assert first["id"] in text_pdf and second["id"] in text_pdf

    from neosys_pharma.infrastructure.securite_models import RoleModel
    gen = db(client)
    permission_session = next(gen)
    try:
        role_id = permission_session.scalar(select(RoleModel.id_role).where(
            RoleModel.organisation_id == a['org'], RoleModel.code == 'CATALOGUE'
        ))
        for permission in (
            'caisse.cloture.consulter', 'caisse.cloture.x', 'caisse.cloture.z',
            'vente.retour.gerer',
            'caisse.remboursement.demander', 'caisse.remboursement.autoriser',
            'caisse.remboursement.executer',
        ):
            permission_key = permission_id(permission)
            if not permission_session.scalar(select(RolePermissionModel.role_id).where(
                RolePermissionModel.role_id == role_id,
                RolePermissionModel.permission_id == permission_key,
            )):
                permission_session.add(RolePermissionModel(
                    role_id=role_id, permission_id=permission_key
                ))
        permission_session.commit()
    finally:
        gen.close()
    login(client, a)
    finance_root = f"/api/regularisations/organisations/{a['org']}"
    x_response = client.post(finance_root + "/clotures/x", json={
        "cle": str(uuid4()), "session_id": session["id"],
        "revision": session["revision"] + 1,
    })
    assert x_response.status_code == 201, x_response.text
    x = x_response.json()
    assert x["instantane"]["session"]["nets_par_mode"] == {
        "ESPECES": "302", "CARTE": "200", "MOBILE_MONEY": "0", "CHEQUE": "0", "VIREMENT": "0",
    }

    encaissement_first = next(
        row for row in first_result["resultat"]["recus_individuels"]
        if row["vente_id"] == first["id"]
    )
    rejected_external_refund = client.post(finance_root + "/remboursements", json={
        "cle": str(uuid4()), "confirmation_id": confirmation["id"],
        "session_id": session["id"], "revision": session["revision"] + 1,
        "reglements": [{"mode": "CARTE", "montant": "200"}],
        "justification": "Une vente encaissée doit passer par un retour.",
    })
    assert rejected_external_refund.status_code == 409

    returnable = client.get(finance_root + f"/recus/{encaissement_first['id']}/retournable")
    assert returnable.status_code == 200, returnable.text
    returned_line = returnable.json()["lignes"][0]
    refund_url = finance_root + "/remboursements"

    # La vente 1 a 301 FCFA ventilés : 200 carte et 101 espèces.
    # La restitution doit suivre ces allocations et plafonner chaque retour.
    first_return_response = client.post(finance_root + "/retours", json={
        "cle": str(uuid4()), "encaissement_id": encaissement_first["id"],
        "lignes": [{"ligne_id": returned_line["ligne_id"],
                    "stock_id": returned_line["stock_id"], "quantite": 1}],
        "justification": "Premier retour partiel sur la vente du dossier groupé.",
    })
    assert first_return_response.status_code == 201, first_return_response.text
    first_return = first_return_response.json()
    assert first_return["montant"] == "100"
    denied_substitution = client.post(refund_url, json={
        "cle": str(uuid4()), "retour_id": first_return["id"],
        "session_id": session["id"], "revision": session["revision"] + 1,
        "reglements": [{"mode": "ESPECES", "mode_origine": "CARTE", "montant": "100"}],
        "justification": "Substitution sans permission.",
    })
    assert denied_substitution.status_code == 403

    def refund_return(returned, payments, proof_rows):
        payments = [{**p,
                     **({'moyen_id':confirmation['moyen_id']} if p['mode']=='CARTE' else {}),
                     **({'moyen_origine_id':confirmation['moyen_id']} if p.get('mode_origine')=='CARTE' else {})}
                    for p in payments]
        session_now = next(row for row in client.get(root(a) + "/sessions").json()["items"]
                           if row["id"] == session["id"])
        refund_payload = {
            "cle": str(uuid4()), "retour_id": returned["id"],
            "session_id": session["id"], "revision": session_now["revision"],
            "reglements": payments,
            "justification": "Restitution selon les règlements alloués à la vente.",
        }
        refund = client.post(refund_url, json=refund_payload)
        assert refund.status_code == 201, refund.text
        assert client.post(refund_url, json=refund_payload).json() == refund.json()
        authorized = client.post(finance_root + f"/remboursements/{refund.json()['id']}/autoriser", json={
            "cle": str(uuid4()), "revision": refund.json()["revision"],
            "justification": "Allocations du reçu collectif vérifiées.",
        })
        assert authorized.status_code == 200, authorized.text
        execution_payload = {
            "cle": str(uuid4()), "revision": authorized.json()["revision"],
            "justification": "Restitution effectivement remise.",
            "preuves": proof_rows,
        }
        executed = client.post(finance_root + f"/remboursements/{refund.json()['id']}/executer", json=execution_payload)
        assert executed.status_code == 200, executed.text
        session_revision_after_execution = next(
            row["revision"] for row in client.get(root(a) + "/sessions").json()["items"]
            if row["id"] == session["id"]
        )
        assert client.post(
            finance_root + f"/remboursements/{refund.json()['id']}/executer",
            json=execution_payload,
        ).json() == executed.json()
        session_revision_after_replay = next(
            row["revision"] for row in client.get(root(a) + "/sessions").json()["items"]
            if row["id"] == session["id"]
        )
        assert session_revision_after_replay == session_revision_after_execution
        pdf = client.get(finance_root + f"/documents/remboursements/{refund.json()['id']}/pdf")
        assert pdf.status_code == 200 and pdf.content.startswith(b"%PDF")
        return executed.json()

    refund_return(first_return, [
        {"mode": "CARTE", "mode_origine": "CARTE", "montant": "100"},
    ], [{"reference": "RETOUR-GROUPE-CARTE-1", "preuve": "Remboursement carte vérifié."}])
    first_partial_points = client.get(root(a) + f"/fidelite/{account_row['id']}").json()["points"]
    first_receipt = next(
        row for row in first_result["resultat"]["recus_individuels"]
        if row["vente_id"] == first["id"]
    )
    first_gain = first_receipt["instantane"]["fidelite"]
    points_revoques_cumules = (
        int(first_gain["points_acquis"]) * 100 // int(first_gain["eligible_paye"])
    )
    assert first_partial_points == int(first_gain["points_acquis"]) - points_revoques_cumules

    # Deuxième retour partiel, testé contre le reliquat réel de chaque moyen.
    second_return = client.post(finance_root + "/retours", json={
        "cle": str(uuid4()), "encaissement_id": encaissement_first["id"],
        "lignes": [{"ligne_id": returned_line["ligne_id"],
                    "stock_id": returned_line["stock_id"], "quantite": 2}],
        "justification": "Solde du retour partiel sur la première vente.",
    })
    assert second_return.status_code == 201, second_return.text
    second_return_data = second_return.json()
    assert second_return_data["montant"] == "201"
    session_before_overallocation = next(
        row for row in client.get(root(a) + "/sessions").json()["items"]
        if row["id"] == session["id"]
    )
    over_allocated = client.post(refund_url, json={
        "cle": str(uuid4()), "retour_id": second_return_data["id"],
        "session_id": session["id"], "revision": session_before_overallocation["revision"],
        "reglements": [{"mode": "CARTE", "mode_origine": "CARTE", "moyen_id":confirmation['moyen_id'], "moyen_origine_id":confirmation['moyen_id'], "montant": "201"}],
        "justification": "Montant carte supérieur à l'allocation de la vente.",
    })
    assert over_allocated.status_code == 409
    refund_return(second_return_data, [
        {"mode": "CARTE", "mode_origine": "CARTE", "montant": "100"},
        {"mode": "ESPECES", "mode_origine": "ESPECES", "montant": "101"},
    ], [
        {"reference": "RETOUR-GROUPE-CARTE-2", "preuve": "Remboursement carte vérifié."}, {},
    ])
    assert client.get(root(a) + f"/fidelite/{account_row['id']}").json()["points"] == 0
    assert next(row for row in client.get(root(a) + "/sessions").json()["items"]
                if row["id"] == session["id"])["especes_attendues"] == "1201"
    assert client.get(vente_root(a) + f"/{second['id']}").json()["etat"] == "ENCAISSEE"

    # Le retour de la deuxième vente du même groupe respecte son allocation espèces.
    second_receipt = next(
        row for row in first_result["resultat"]["recus_individuels"]
        if row["vente_id"] == second["id"]
    )
    second_returnable = client.get(finance_root + f"/recus/{second_receipt['id']}/retournable")
    assert second_returnable.status_code == 200, second_returnable.text
    second_line = second_returnable.json()["lignes"][0]
    third_return = client.post(finance_root + "/retours", json={
        "cle": str(uuid4()), "encaissement_id": second_receipt["id"],
        "lignes": [{"ligne_id": second_line["ligne_id"],
                    "stock_id": second_line["stock_id"], "quantite": 1}],
        "justification": "Retour partiel sur la deuxième vente du groupe.",
    })
    assert third_return.status_code == 201, third_return.text
    assert third_return.json()["montant"] == "100"
    from neosys_pharma.infrastructure.securite_models import RoleModel
    from neosys_pharma.infrastructure.caisse_models import EvenementCaisseModel
    gen = db(client); permission_session = next(gen)
    try:
        role_id = permission_session.scalar(select(RoleModel.id_role).where(
            RoleModel.organisation_id == a['org'], RoleModel.code == 'CATALOGUE'
        ))
        permission_session.add(RolePermissionModel(
            role_id=role_id,
            permission_id=permission_id('caisse.remboursement.substituer'),
        ))
        permission_session.commit()
    finally:
        gen.close()
    login(client, a)
    substituted_refund = refund_return(third_return.json(), [
        {"mode": "CARTE", "mode_origine": "ESPECES", "montant": "100"},
    ], [{"reference": "SUBSTITUTION-GROUPE", "preuve": "Substitution autorisée et confirmée."}])
    gen = db(client); audit_session = next(gen)
    try:
        substitution_events = audit_session.scalars(select(EvenementCaisseModel).where(
            EvenementCaisseModel.organisation_id == a['org'],
            EvenementCaisseModel.type == 'P4.5:REMBOURSEMENT_DEMANDE',
        )).all()
        substitution_event = next(
            (event for event in substitution_events
             if event.donnees['dossier']['id'] == substituted_refund['id']),
            None,
        )
        assert substitution_event is not None
        assert substitution_event.donnees['dossier']['reglements'][0] == {
            'mode': 'CARTE', 'mode_origine': 'ESPECES', 'montant': '100',
            'moyen_id':confirmation['moyen_id'], 'moyen_origine_id':None,
            'moyen_libelle':'Recette CARTE', 'moyen_origine_libelle':'ESPECES',
        }
    finally:
        gen.close()

    # Z agrège les mouvements groupés et les remboursements, sans double compter les ventes.
    current_session = next(row for row in client.get(root(a) + "/sessions").json()["items"]
                           if row["id"] == session["id"])
    closed = client.post(root(a) + f"/sessions/{session['id']}/fermer", json={
        "cle": str(uuid4()), "revision": current_session["revision"],
        "comptage_final": current_session["especes_attendues"],
        "justification": "Comptage de fin de session après remboursements groupés.",
    })
    assert closed.status_code == 200, closed.text
    period = client.get(finance_root + "/contexte").json()["periode"]
    z = client.post(finance_root + "/clotures/z", json={
        "cle": str(uuid4()), "periode_id": period["id"],
        "justification": "Clôture après encaissement et retours du dossier groupé.",
    })
    assert z.status_code == 201, z.text
    z_snapshot = z.json()["instantane"]
    assert z_snapshot["sessions"][0]["nets_par_mode"] == {
        "ESPECES": "201", "CARTE": "-100", "MOBILE_MONEY": "0", "CHEQUE": "0", "VIREMENT": "0",
    }
    assert z_snapshot["sections"][0]["lignes"][0][0] == 2
    assert z_snapshot["sessions"][0]["especes_attendues"] == "1201"
    assert client.get(vente_root(a) + f"/{second['id']}").json()["etat"] == "ENCAISSEE"
    assert client.post(finance_root + f"/clotures/z", json={
        "cle": str(uuid4()), "periode_id": period["id"],
        "justification": "Double clôture interdite.",
    }).status_code == 409


def test_finalisation_groupe_rollback_apres_creation_des_reçus(raw_client, account, monkeypatch):
    from neosys_pharma.presentation import encaissement_groupe_api

    monkeypatch.setattr(encaissement_groupe_api, "GROUPED_ENCASHMENT_ENABLED", True)
    client, a = raw_client, account
    first, session, product, pack, post_id, caisse_id = ready(client, a, q=3)
    second = line(client, a, create(client, a, post_id), product, pack, q=2)
    second = act(client, a, second, "valider")
    second = act(client, a, second, "transmettre", caisse_id=caisse_id)
    draft = groupe_post(client, a, "", {"cle": str(uuid4()), "session_id": session["id"]}, 201)
    group_id = draft["dossier"]["id"]
    draft = groupe_put(client, a, f"/{group_id}/ventes", {
        "cle": str(uuid4()), "revision": draft["dossier"]["revision"],
        "ventes": [
            {"vente_id": first["id"], "revision": first["revision"]},
            {"vente_id": second["id"], "revision": second["revision"]},
        ],
    })
    due = sum(Decimal(row["montant_du"]) for row in draft["ventes"])
    draft = groupe_put(client, a, f"/{group_id}/reglements", {
        "cle": str(uuid4()), "revision": draft["dossier"]["revision"],
        "reglements": [{"mode": "ESPECES", "montant": str(due)}],
    })
    proposal = client.get(root(a) + f"/groupes/{group_id}/allocations/proposition", params={
        "revision": draft["dossier"]["revision"],
    }).json()
    draft = groupe_put(client, a, f"/{group_id}/allocations", {
        "cle": str(uuid4()), "revision": draft["dossier"]["revision"],
        "allocations": proposal,
    })
    payload = {
        "cle": str(uuid4()), "revision": draft["dossier"]["revision"],
        "revision_session": session["revision"], "fidelite": [],
    }
    stale_session = client.post(root(a) + f"/groupes/{group_id}/finaliser", json={
        **payload, "cle": str(uuid4()), "revision_session": session["revision"] + 1,
    })
    assert stale_session.status_code == 409
    assert client.post(root({**a, "org": str(uuid4())}) + f"/groupes/{group_id}/finaliser",
                       json=payload).status_code == 403
    original_site = client.headers["X-Site-ID"]
    client.headers["X-Site-ID"] = str(a["other"])
    assert client.post(root(a) + f"/groupes/{group_id}/finaliser", json=payload).status_code == 403
    client.headers["X-Site-ID"] = original_site

    def fail_group_pdf(_):
        raise RuntimeError("Échec de rendu injecté après les reçus individuels.")

    from neosys_pharma.infrastructure import caisse_pdf
    monkeypatch.setattr(caisse_pdf, "recu_groupe_pdf", fail_group_pdf)
    with pytest.raises(RuntimeError, match="Échec de rendu injecté"):
        client.post(root(a) + f"/groupes/{group_id}/finaliser", json=payload)

    unchanged = client.get(root(a) + f"/groupes/{group_id}").json()
    assert unchanged["dossier"]["etat"] == "BROUILLON"
    assert all(client.get(vente_root(a) + f"/{sale_id}").json()["etat"] == "TRANSMISE"
               for sale_id in (first["id"], second["id"]))
    assert stocks(client, a)[0]["physique"] == 10 and stocks(client, a)[0]["reserve"] == 5
    movements = client.get(root(a) + "/mouvements", params={"session_id": session["id"]}).json()
    assert movements["total"] == 0

    monkeypatch.undo()
    monkeypatch.setattr(encaissement_groupe_api, "GROUPED_ENCASHMENT_ENABLED", True)
    result = client.post(root(a) + f"/groupes/{group_id}/finaliser", json=payload)
    assert result.status_code == 200, result.text
    assert result.json()["dossier"]["etat"] == "FINALISE"


def test_concurrence_postgresql_finalisation_groupe_meme_cle(raw_client, account):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier
    from sqlalchemy.orm import Session
    from neosys_pharma.infrastructure.caisse_models import EncaissementGroupeModel
    from neosys_pharma.application.encaissement_groupe_service import EncaissementGroupeService

    client, a = raw_client, account
    sale, session, _, _, _, _ = ready(client, a, q=3)
    draft = groupe_post(client, a, "", {"cle": str(uuid4()), "session_id": session["id"]}, 201)
    group_id = draft["dossier"]["id"]
    draft = groupe_put(client, a, f"/{group_id}/ventes", {
        "cle": str(uuid4()), "revision": draft["dossier"]["revision"],
        "ventes": [{"vente_id": sale["id"], "revision": sale["revision"]}],
    })
    due = Decimal(draft["ventes"][0]["montant_du"])
    draft = groupe_put(client, a, f"/{group_id}/reglements", {
        "cle": str(uuid4()), "revision": draft["dossier"]["revision"],
        "reglements": [{"mode": "ESPECES", "montant": str(due)}],
    })
    proposal = client.get(root(a) + f"/groupes/{group_id}/allocations/proposition", params={
        "revision": draft["dossier"]["revision"],
    }).json()
    draft = groupe_put(client, a, f"/{group_id}/allocations", {
        "cle": str(uuid4()), "revision": draft["dossier"]["revision"], "allocations": proposal,
    })
    request_key = uuid4()
    data = {"revision": draft["dossier"]["revision"], "revision_session": session["revision"], "fidelite": []}
    gen = db(client)
    db_session = next(gen)
    engine = db_session.get_bind()
    db_session.close()
    gen.close()
    if engine.dialect.name != "postgresql":
        pytest.skip("Deux connexions PostgreSQL natives requises pour ce contrôle.")
    start = Barrier(2)

    def finalize(_):
        with Session(engine) as independent:
            independent.execute(text("SET statement_timeout = '8s'"))
            start.wait(timeout=5)
            stock = StockService(independent, a["org"], a["user"], lambda *args: None)
            cash = CaisseService(VenteService(stock, a["site"]))
            grouped = EncaissementGroupeService(cash)
            try:
                return stock.operation(
                    request_key, "P4C:BROUILLON:FINALISER:" + group_id, data,
                    lambda: grouped.finaliser(UUID(group_id), data, request_key),
                )
            except ConflitStock as exc:
                return {"conflit": str(exc)}

    with ThreadPoolExecutor(max_workers=2) as pool:
        first, second = pool.map(finalize, range(2))
    assert first == second and "resultat" in first
    with Session(engine) as verify:
        assert verify.scalar(select(func.count()).select_from(EncaissementModel).where(
            EncaissementModel.vente_id == UUID(sale["id"])
        )) == 1
        assert verify.scalar(select(func.count()).select_from(MouvementCaisseGroupeModel).where(
            MouvementCaisseGroupeModel.dossier_id == UUID(group_id)
        )) == 1
        assert verify.get(EncaissementGroupeModel, UUID(group_id)).etat == "FINALISE"


def test_concurrence_postgresql_encaissement_individuel_contre_groupe(raw_client, account):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier
    from sqlalchemy.orm import Session
    from neosys_pharma.application.encaissement_groupe_service import EncaissementGroupeService

    client, a = raw_client, account
    sale, session, _, _, _, _ = ready(client, a, q=3)
    draft = groupe_post(client, a, "", {"cle": str(uuid4()), "session_id": session["id"]}, 201)
    group_id = draft["dossier"]["id"]
    draft = groupe_put(client, a, f"/{group_id}/ventes", {
        "cle": str(uuid4()), "revision": draft["dossier"]["revision"],
        "ventes": [{"vente_id": sale["id"], "revision": sale["revision"]}],
    })
    due = Decimal(draft["ventes"][0]["montant_du"])
    draft = groupe_put(client, a, f"/{group_id}/reglements", {
        "cle": str(uuid4()), "revision": draft["dossier"]["revision"],
        "reglements": [{"mode": "ESPECES", "montant": str(due)}],
    })
    proposal = client.get(root(a) + f"/groupes/{group_id}/allocations/proposition", params={
        "revision": draft["dossier"]["revision"],
    }).json()
    draft = groupe_put(client, a, f"/{group_id}/allocations", {
        "cle": str(uuid4()), "revision": draft["dossier"]["revision"], "allocations": proposal,
    })
    group_data = {"revision": draft["dossier"]["revision"], "revision_session": session["revision"], "fidelite": []}
    individual_data = {
        "revision": sale["revision"], "session_id": session["id"],
        "revision_session": session["revision"],
        "reglements": [{"mode": "ESPECES", "montant": str(due)}],
        "compte_id": None, "revision_compte": None, "points_utilises": 0, "consentement": False,
    }
    gen = db(client)
    db_session = next(gen)
    engine = db_session.get_bind()
    db_session.close()
    gen.close()
    if engine.dialect.name != "postgresql":
        pytest.skip("Deux connexions PostgreSQL natives requises pour ce contrôle.")
    start = Barrier(2)

    def run_group():
        with Session(engine) as independent:
            independent.execute(text("SET statement_timeout = '8s'"))
            start.wait(timeout=5)
            stock = StockService(independent, a["org"], a["user"], lambda *args: None)
            grouped = EncaissementGroupeService(CaisseService(VenteService(stock, a["site"])))
            try:
                stock.operation(uuid4(), "P4C:FINALISER", group_data,
                    lambda: grouped.finaliser(UUID(group_id), group_data, uuid4()))
                return "groupe"
            except ConflitStock:
                return "conflit"

    def run_individual():
        with Session(engine) as independent:
            independent.execute(text("SET statement_timeout = '8s'"))
            start.wait(timeout=5)
            stock = StockService(independent, a["org"], a["user"], lambda *args: None)
            cash = CaisseService(VenteService(stock, a["site"]))
            try:
                stock.operation(uuid4(), "P4.4:FINALISER:" + sale["id"], individual_data,
                    lambda: cash.finaliser(UUID(sale["id"]), individual_data))
                return "individuel"
            except ConflitStock:
                return "conflit"

    with ThreadPoolExecutor(max_workers=2) as pool:
        outcomes = sorted([pool.submit(run_group), pool.submit(run_individual)], key=lambda future: id(future))
        results = [future.result(timeout=12) for future in outcomes]
    assert sorted(results).count("conflit") == 1
    assert len(set(results) & {"groupe", "individuel"}) == 1
    assert client.get(vente_root(a) + f"/{sale['id']}").json()["etat"] == "ENCAISSEE"


def test_concurrence_postgresql_deux_dossiers_meme_vente(raw_client, account):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier
    from sqlalchemy.orm import Session
    from neosys_pharma.application.encaissement_groupe_service import EncaissementGroupeService

    client, a = raw_client, account
    sale, session, _, _, _, _ = ready(client, a, q=3)
    group_a, draft_a = prepare_group_for_sale(client, a, sale, session)
    group_b, draft_b = prepare_group_for_sale(client, a, sale, session)
    pending = [
        (group_a, {"revision": draft_a["dossier"]["revision"],
                   "revision_session": session["revision"], "fidelite": []}),
        (group_b, {"revision": draft_b["dossier"]["revision"],
                   "revision_session": session["revision"], "fidelite": []}),
    ]
    gen = db(client)
    db_session = next(gen)
    engine = db_session.get_bind()
    db_session.close()
    gen.close()
    if engine.dialect.name != "postgresql":
        pytest.skip("Deux connexions PostgreSQL natives requises pour ce contrôle.")
    start = Barrier(2)

    def finalize(item):
        group_id, data = item
        key = uuid4()
        with Session(engine) as independent:
            independent.execute(text("SET statement_timeout = '8s'"))
            start.wait(timeout=5)
            stock = StockService(independent, a["org"], a["user"], lambda *args: None)
            grouped = EncaissementGroupeService(CaisseService(VenteService(stock, a["site"])))
            try:
                stock.operation(key, "P4C:FINALISER:" + group_id, data,
                    lambda: grouped.finaliser(UUID(group_id), data, key))
                return group_id
            except ConflitStock:
                return "conflit"

    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(finalize, item) for item in pending]
        results = [future.result(timeout=12) for future in futures]
    assert sum(result != "conflit" for result in results) == 1
    assert client.get(vente_root(a) + f"/{sale['id']}").json()["etat"] == "ENCAISSEE"
