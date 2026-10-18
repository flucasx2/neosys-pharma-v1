"""P4 incrément 1 : appels HTTP, transaction P3/P4 et refus financiers explicites."""
from concurrent.futures import ThreadPoolExecutor
from datetime import date
from decimal import Decimal
from uuid import UUID, uuid4
import pytest
from sqlalchemy import select, delete, text,func
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session
from test_stock import raw_client, account, db, login, lot, entry, stocks, ALL, post as stock_post
from test_catalogue import grant, basic, post as catalogue_post
from test_http_autorisations_p1 import set_state
from neosys_pharma.domain.organisation.permissions_systeme import P4_PERMISSIONS, permission_id
from neosys_pharma.domain.vente import transition, remise_valide, LigneVente
from neosys_pharma.infrastructure.organisation_models import PosteVenteModel,CaisseModel
from neosys_pharma.infrastructure.securite_models import RoleModel,RolePermissionModel
from neosys_pharma.application.stock_service import StockService
from neosys_pharma.application.vente_service import VenteService
from neosys_pharma.domain.stock import ConflitStock


def root(a):return f'/api/ventes/organisations/{a["org"]}'
def post(c,a,path,body=None,status=201):
    r=c.post(root(a)+path,json={'cle':str(uuid4()),**(body or {})});assert r.status_code==status,r.text;return r.json()
def setup(c,a):
    grant(c,a,ALL+tuple(x[0] for x in P4_PERMISSIONS));login(c,a)
    _,_,product=basic(c,a);pack=product['conditionnements'][0]['id_conditionnement']
    catalogue_post(c,a,'/tarification/references',{'conditionnement_id':pack,'montant_ht':'100.25','devise':'XAF','debut':str(date.today())})
    gen=db(c);s=next(gen);pid,cid=uuid4(),uuid4()
    try:
        s.add_all([PosteVenteModel(id_poste_vente=pid,emplacement_id=a['location'],code='P4',nom='Préparation'),CaisseModel(id_caisse=cid,emplacement_id=a['location'],code='C4',nom='Caisse')]);s.commit()
    finally:gen.close()
    l=lot(c,a,pack);entry(c,a,l['id'],10)
    return product['id_produit'],pack,str(pid),str(cid)
def create(c,a,pid,**kwargs):return post(c,a,'',{'emplacement_id':str(a['location']),'poste_id':pid,**kwargs})
def line(c,a,v,product,pack,q=3,**kwargs):return post(c,a,f'/{v["id"]}/lignes',{'revision':v['revision'],'produit_id':product,'conditionnement_id':pack,'quantite':q,**kwargs})
def act(c,a,v,name,**kwargs):return post(c,a,f'/{v["id"]}/{name}',{'revision':v['revision'],**kwargs},200)


def test_preparation_transmission_annulation_atomiques_et_journal(raw_client,account):
    c,a=raw_client,account;prod,pack,pid,cid=setup(c,a)
    v=create(c,a,pid);v=line(c,a,v,prod,pack)
    assert Decimal(v['totaux']['ttc'])==Decimal('301')
    assert stocks(c,a)[0]['physique']==10 and stocks(c,a)[0]['reserve']==3
    reservation=v['lignes'][0]['reservations'][0]['id']
    for endpoint in ('liberer','consommer'):stock_post(c,a,f'/reservations/{reservation}/{endpoint}',status=409)
    v=act(c,a,v,'attendre');v=act(c,a,v,'reprendre');v=act(c,a,v,'valider')
    post(c,a,f'/{v["id"]}/transmettre',{'revision':v['revision'],'caisse_id':str(uuid4())},403)
    v=act(c,a,v,'transmettre',caisse_id=cid);assert v['etat']=='TRANSMISE' and stocks(c,a)[0]['reserve']==3
    v=act(c,a,v,'annuler',justification='Client parti');assert v['etat']=='ANNULEE' and stocks(c,a)[0]['reserve']==0 and stocks(c,a)[0]['physique']==10
    post(c,a,f'/{v["id"]}/reprendre',{'revision':v['revision']},422)
    history=c.get(root(a)+f'/{v["id"]}/historique',params={'page_size':2}).json();assert history['total']>=6 and len(history['items'])==2
    assert all(e['donnees']['operation_id'] for e in history['items'])
    for sql in ('UPDATE vente_evenements SET type=\'FAUX\'','DELETE FROM vente_evenements'):
        gen=db(c);s=next(gen)
        try:
            with pytest.raises(DBAPIError):s.execute(text(sql));s.commit()
            s.rollback()
        finally:gen.close()


def test_rollback_revision_idempotence_et_retrait(raw_client,account):
    c,a=raw_client,account;prod,pack,pid,_=setup(c,a);v=line(c,a,create(c,a,pid),prod,pack)
    row=v['lignes'][0];body={'cle':str(uuid4()),'revision':v['revision'],'ligne_id':row['id'],'produit_id':prod,'conditionnement_id':pack,'quantite':11}
    assert c.post(root(a)+f'/{v["id"]}/lignes',json=body).status_code==409
    current=c.get(root(a)+f'/{v["id"]}').json();assert current==v and stocks(c,a)[0]['reserve']==3
    body['quantite']=4
    r=c.post(root(a)+f'/{v["id"]}/lignes',json=body);assert r.status_code==201,r.text
    assert c.post(root(a)+f'/{v["id"]}/lignes',json=body).json()==r.json()
    assert stocks(c,a)[0]['reserve']==4
    post(c,a,f'/{v["id"]}/lignes',{'revision':v['revision'],'produit_id':prod,'conditionnement_id':pack,'quantite':1},409)
    v=r.json();v=post(c,a,f'/{v["id"]}/lignes/{row["id"]}/retirer',{'revision':v['revision']},200)
    assert v['lignes']==[] and stocks(c,a)[0]['reserve']==0
    post(c,a,f'/{v["id"]}/valider',{'revision':v['revision']},422)


@pytest.mark.parametrize('type,value',[('POURCENTAGE','10'),('MONTANT_XAF','25')])
def test_remises_demande_refus_non_contournement(raw_client,account,type,value):
    c,a=raw_client,account;prod,pack,pid,_=setup(c,a);v=line(c,a,create(c,a,pid),prod,pack)
    request=post(c,a,f'/{v["id"]}/remises',{'revision':v['revision'],'type':type,'valeur':value,'justification':'Demande client'})
    assert c.get(root(a)+f'/{v["id"]}').json()['totaux']==v['totaux']
    post(c,a,f'/{v["id"]}/valider',{'revision':v['revision']},422)
    post(c,a,f'/{v["id"]}/remises/{request["id"]}/decision',{'revision':v['revision'],'autoriser':True,'justification':'Responsable'},422)
    post(c,a,f'/{v["id"]}/remises/{request["id"]}/decision',{'revision':v['revision'],'autoriser':False,'justification':'Politique non configurée'},200)
    v=c.get(root(a)+f'/{v["id"]}').json()
    assert act(c,a,v,'valider')['etat']=='VALIDEE_PREPARATION'


@pytest.mark.parametrize('state',['inactive','expired','future','no_assignment','no_role','no_permission','no_location','split_assignments'])
def test_affectations_p1_exigees_http(raw_client,account,state):
    c,a=raw_client,account;prod,pack,pid,_=setup(c,a);v=create(c,a,pid);set_state(c,a,state)
    assert c.get(root(a)+f'/{v["id"]}').status_code==403
    post(c,a,f'/{v["id"]}/lignes',{'revision':1,'produit_id':prod,'conditionnement_id':pack,'quantite':1},403)


def test_401_403_csrf_et_lecture_seule(raw_client,account):
    c,a=raw_client,account
    assert c.get(root(a)).status_code==401 and c.post(root(a),json={}).status_code==401
    prod,pack,pid,_=setup(c,a);v=create(c,a,pid)
    gen=db(c);s=next(gen)
    try:s.execute(delete(RolePermissionModel).where(RolePermissionModel.permission_id.in_([permission_id(code) for code,_ in P4_PERMISSIONS if code!='vente.consulter'])));s.commit()
    finally:gen.close()
    assert c.get(root(a)+f'/{v["id"]}').status_code==200
    for path in ('',f'/{v["id"]}/lignes',f'/{v["id"]}/remises',f'/{v["id"]}/valider',f'/{v["id"]}/annuler'):
        post(c,a,path,{},403)
    c.headers.pop('X-CSRF-Token');post(c,a,'',{},403)
    assert c.get(root({'org':uuid4()})).status_code==403
    c.headers['X-Site-ID']=str(a['other']);assert c.get(root(a)+f'/{v["id"]}').status_code==403


@pytest.mark.parametrize('mode',['CNAMGS','MUTUELLE','CNAMGS_MUTUELLE','CREDIT'])
def test_modes_financiers_sans_permission_tiers_restant_non_validables(raw_client,account,mode):
    c,a=raw_client,account;prod,pack,pid,_=setup(c,a);v=line(c,a,create(c,a,pid,mode=mode),prod,pack)
    assert v['part_client'] is None and not v['prise_en_charge_disponible']
    post(c,a,f'/{v["id"]}/valider',{'revision':v['revision']},403 if mode!='CREDIT' else 422)


def test_preparation_et_transmission_tiers_requiert_permission_referentiel(raw_client,account):
    c,a=raw_client,account
    prod,pack,pid,cid=setup(c,a)
    v=line(c,a,create(c,a,pid,mode='MUTUELLE'),prod,pack)
    assert c.post(root(a)+f'/{v["id"]}/valider',json={'cle':str(uuid4()),'revision':v['revision']}).status_code==403
    gen=db(c);s=next(gen)
    try:
        role=s.scalar(select(RoleModel).where(RoleModel.organisation_id==a['org'],RoleModel.code=='CATALOGUE'))
        s.add(RolePermissionModel(role_id=role.id_role,permission_id=permission_id('tiers_payant.consulter')));s.commit()
    finally:gen.close()
    validated=post(c,a,f'/{v["id"]}/valider',{'revision':v['revision']},200)
    transmitted=post(c,a,f'/{v["id"]}/transmettre',{'revision':validated['revision'],'caisse_id':cid},200)
    assert transmitted['etat']=='TRANSMISE'


def test_concurrence_postgresql_vente_et_stock(raw_client,account):
    c,a=raw_client,account;prod,pack,pid,_=setup(c,a);v=create(c,a,pid)
    gen=db(c);s=next(gen);engine=s.get_bind();gen.close()
    if engine.dialect.name!='postgresql':pytest.skip('Deux connexions PostgreSQL requises')
    def worker():
        with Session(engine) as session:
            stock=StockService(session,a['org'],a['user'],lambda *args:None);service=VenteService(stock,a['site'])
            try:
                stock.operation(uuid4(),'P4:LIGNE',{},lambda:service.ajouter_ligne(service.obtenir(UUID(v['id']),'vente.preparer'),dict(revision=1,produit_id=UUID(prod),conditionnement_id=UUID(pack),quantite=7)))
                return 'ok'
            except ConflitStock:return 'conflit'
    with ThreadPoolExecutor(max_workers=2) as pool:assert sorted(pool.map(lambda _:worker(),range(2)))==['conflit','ok']
    assert stocks(c,a)[0]['reserve']==7 and len(c.get(root(a)+f'/{v["id"]}').json()['lignes'])==1


@pytest.mark.parametrize('kind,value',[('POURCENTAGE',101),('POURCENTAGE',0),('MONTANT_XAF','NaN'),('MONTANT_XAF','0.001')])
def test_invariants_remise(kind,value):
    with pytest.raises(ValueError):remise_valide(kind,value)
    with pytest.raises(ValueError):transition('PREPARATION','ENCAISSEE')


def test_references_internes_tarif_change_et_remise_invalidee(raw_client,account):
    c,a=raw_client,account;prod,pack,pid,_=setup(c,a);v=create(c,a,pid)
    post(c,a,f'/{v["id"]}/lignes',{'revision':1,'produit_id':str(uuid4()),'conditionnement_id':pack,'quantite':1},403)
    v=line(c,a,v,prod,pack)
    d=post(c,a,f'/{v["id"]}/remises',{'revision':v['revision'],'ligne_id':v['lignes'][0]['id'],'type':'POURCENTAGE','valeur':'5','justification':'Ligne'})
    v=line(c,a,v,prod,pack,4,ligne_id=v['lignes'][0]['id']);assert v['remises'][0]['statut']=='INVALIDEE'
    catalogue_post(c,a,'/tarification/produits',{'site_id':str(a['site']),'produit_id':prod,'conditionnement_id':pack,'montant_ht':'125','devise':'XAF','debut':str(date.today())})
    post(c,a,f'/{v["id"]}/valider',{'revision':v['revision']},409)
    v=line(c,a,v,prod,pack,4,ligne_id=v['lignes'][0]['id']);assert v['lignes'][0]['instantane_tarif']['origine']=='PRODUIT_SITE'
    assert act(c,a,v,'valider')['etat']=='VALIDEE_PREPARATION'


def test_csrf_credit_et_decision_permissions_independantes(raw_client,account):
    c,a=raw_client,account;prod,pack,pid,_=setup(c,a);v=line(c,a,create(c,a,pid),prod,pack)
    d=post(c,a,f'/{v["id"]}/remises',{'revision':v['revision'],'type':'MONTANT_XAF','valeur':'1','justification':'Client'})
    token=c.headers.pop('X-CSRF-Token');post(c,a,'',{'emplacement_id':str(a['location']),'poste_id':pid},403);c.headers['X-CSRF-Token']=token
    gen=db(c);s=next(gen)
    try:s.execute(delete(RolePermissionModel).where(RolePermissionModel.permission_id.in_([permission_id('vente.credit'),permission_id('vente.remise.autoriser'),permission_id('stock.reserver')])));s.commit()
    finally:gen.close()
    post(c,a,'',{'emplacement_id':str(a['location']),'poste_id':pid,'mode':'CREDIT'},403)
    post(c,a,f'/{v["id"]}/remises/{d["id"]}/decision',{'revision':v['revision'],'autoriser':False,'justification':'Sans autorisation'},403)
    post(c,a,f'/{v["id"]}/lignes',{'revision':v['revision'],'produit_id':prod,'conditionnement_id':pack,'quantite':1},403)


def test_migration_p4_additive_cycle_et_aucun_droit_implicite(tmp_path,monkeypatch):
    import os
    from alembic import command
    from alembic.config import Config
    from sqlalchemy import create_engine,inspect
    from neosys_pharma.infrastructure.config import get_settings
    url=os.getenv('TEST_MIGRATION_DATABASE_URL',f'sqlite+pysqlite:///{tmp_path / "p4.db"}')
    monkeypatch.setenv('DATABASE_URL',url);get_settings.cache_clear();cfg=Config('alembic.ini');engine=create_engine(url)
    try:
        command.upgrade(cfg,'head');command.check(cfg)
        with engine.connect() as conn:
            from neosys_pharma.infrastructure.securite_models import PermissionModel
            codes=[code for code,_ in P4_PERMISSIONS if code.startswith('vente.')]
            assert conn.scalar(select(func.count()).select_from(PermissionModel).where(PermissionModel.code.in_(codes)))==len(codes)
            assert conn.execute(text("SELECT count(*) FROM roles_permissions JOIN permissions ON permissions.id_permission=roles_permissions.permission_id WHERE permissions.code LIKE 'vente.%'")).scalar()==0
            assert conn.execute(text("SELECT count(*) FROM permissions WHERE code LIKE 'proforma.%'")).scalar()==5
            assert conn.execute(text("SELECT count(*) FROM roles_permissions JOIN permissions ON permissions.id_permission=roles_permissions.permission_id WHERE permissions.code LIKE 'proforma.%'")).scalar()==0
            before=conn.execute(text('SELECT sequence, delta_physique FROM stock_mouvements ORDER BY sequence')).all()
        command.downgrade(cfg,'6bf467c26d78')
        assert 'proformas' not in inspect(engine).get_table_names() and 'ventes' in inspect(engine).get_table_names()
        command.upgrade(cfg,'head');command.check(cfg)
        command.downgrade(cfg,'2b3c30f2b213')
        assert 'ventes' not in inspect(engine).get_table_names()
        with engine.connect() as conn:
            assert conn.execute(text('SELECT sequence, delta_physique FROM stock_mouvements ORDER BY sequence')).all()==before
        command.upgrade(cfg,'head');command.check(cfg)
    finally:engine.dispose();get_settings.cache_clear()


def test_annulation_multiligne_liberation_unique_transaction(raw_client,account):
    c,a=raw_client,account;prod,pack,pid,_=setup(c,a);v=line(c,a,create(c,a,pid),prod,pack,2);v=line(c,a,v,prod,pack,3)
    assert stocks(c,a)[0]['reserve']==5
    v=act(c,a,v,'annuler',justification='Annulation de tout le panier')
    assert stocks(c,a)[0]['reserve']==0
    assert all(r['statut']=='LIBEREE' for l in v['lignes'] for r in l['reservations'])
    from test_stock import root as stock_root
    movements=c.get(stock_root(a)+'/mouvements').json()['items']
    assert sum(m['delta_reserve'] for m in movements)==0
    assert len([m for m in movements if m['type']=='LIBERATION'])==2
