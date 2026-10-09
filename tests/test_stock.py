"""P3 : HTTP réel, journal, inventaires actifs, FEFO et concurrence PostgreSQL."""
from concurrent.futures import ThreadPoolExecutor
from datetime import date,timedelta
from uuid import UUID,uuid4
import pytest
from sqlalchemy import select,update,delete,text,func
from sqlalchemy.exc import DBAPIError,IntegrityError
from sqlalchemy.orm import Session
from test_p1_vertical import raw_client
from test_authentification import account,db,login
from test_catalogue import grant,basic
from neosys_pharma.domain.stock import quantite,verifier_stock,perime,ConflitStock
from neosys_pharma.domain.organisation.permissions_systeme import P3_PERMISSIONS,permission_id
from neosys_pharma.domain.organisation.securite import AffectationSite,AffectationRole,AffectationEmplacement
from neosys_pharma.infrastructure.securite_repository import SqlAlchemySecuriteRepository
from neosys_pharma.infrastructure.securite_models import RoleModel,RolePermissionModel,AffectationSiteModel,AffectationEmplacementModel
from neosys_pharma.infrastructure.stock_models import *
from neosys_pharma.application.stock_service import StockService

ALL=tuple(x[0] for x in P3_PERMISSIONS)+('catalogue.consulter','catalogue.gerer')
def root(a):return f'/api/stock/organisations/{a["org"]}'
def post(c,a,path,data=None,status=201):
    response=c.post(root(a)+path,json={'cle':str(uuid4()),**(data or {})});assert response.status_code==status,response.text;return response.json()
def init(c,a,flags=False):
    grant(c,a,ALL);login(c,a);cat,body,p=basic(c,a)
    if flags:
        assert c.put(f'/api/catalogue/organisations/{a["org"]}/categories/{cat["id_categorie"]}',json={'code':'med','nom':'Médicaments','gestion_lot':True,'gestion_peremption':True,'fefo':True}).status_code==200
    return p['conditionnements'][0]['id_conditionnement']
def lot(c,a,pack,number=None,day=None):return post(c,a,'/lots',{'conditionnement_id':pack,'numero':number,'peremption':day})
def entry(c,a,l,q,loc=None,kind='ENTREE',status=201):return post(c,a,'/mouvements',{'lot_id':l,'emplacement_id':str(loc or a['location']),'quantite':q,'origine':'Recette P3','justification':'Quantité physique constatée','type':kind},status)
def reserve(c,a,pack,q,**kwargs):return post(c,a,'/reservations',{'conditionnement_id':pack,'emplacement_id':str(a['location']),'quantite':q,'origine':'Préparation future P4',**kwargs})
def stocks(c,a):return c.get(root(a)+'/stocks').json()['items']
def assign(c,a,locations,site=None):
    gen=db(c);s=next(gen);repo=SqlAlchemySecuriteRepository(s)
    try:
        role=s.scalar(select(RoleModel).where(RoleModel.organisation_id==a['org'],RoleModel.code=='CATALOGUE'))
        if site:
            aff=AffectationSite(utilisateur_id=a['user'],site_id=site,date_debut=date.today());repo.ajouter(aff);repo.ajouter(AffectationRole(affectation_site_id=aff.id_affectation_site,role_id=role.id_role));aid=aff.id_affectation_site
        else:aid=s.scalar(select(AffectationSiteModel.id_affectation_site).where(AffectationSiteModel.utilisateur_id==a['user'],AffectationSiteModel.site_id==a['site']))
        for loc in locations:repo.ajouter(AffectationEmplacement(affectation_site_id=aid,emplacement_id=loc))
        s.commit()
    finally:gen.close()

@pytest.mark.parametrize('q',[0,-1,True,1.2,1_000_000_001])
def test_quantites_entieres_et_invariants(q):
    with pytest.raises(ValueError):quantite(q)
    with pytest.raises(ConflitStock):verifier_stock(3,4)
    assert verifier_stock(8,3)==5
    assert not perime(date.today(),date.today())

def test_reservations_multi_lots_liberation_consommation_et_idempotence(raw_client,account):
    c,a=raw_client,account;pack=init(c,a,True)
    today=date.today();l1=lot(c,a,pack,'LOT-é-01',str(today));l2=lot(c,a,pack,'LOT-02',str(today+timedelta(days=30)))
    entry(c,a,l1['id'],5);entry(c,a,l2['id'],7)
    r=reserve(c,a,pack,8);assert [x['quantite'] for x in r['allocations']]==[5,3]
    assert sum(x['physique'] for x in stocks(c,a))==12 and sum(x['reserve'] for x in stocks(c,a))==8
    post(c,a,'/reservations',{'conditionnement_id':pack,'emplacement_id':str(a['location']),'quantite':5,'origine':'test'},409)
    post(c,a,f'/reservations/{r["id"]}/liberer',status=200);assert sum(x['reserve'] for x in stocks(c,a))==0
    r=reserve(c,a,pack,8);key=str(uuid4());body={'cle':key}
    assert c.post(root(a)+f'/reservations/{r["id"]}/consommer',json=body).status_code==200
    assert c.post(root(a)+f'/reservations/{r["id"]}/consommer',json=body).status_code==200
    assert sum(x['physique'] for x in stocks(c,a))==4
    post(c,a,f'/reservations/{r["id"]}/consommer',status=409)
    moves=c.get(root(a)+'/mouvements',params={'page_size':100}).json()['items'];assert sum(x['delta_physique'] for x in moves)==4
    assert {x['type'] for x in moves}>={'ENTREE','RESERVATION','LIBERATION','CONSOMMATION'}
    assert all(x['auteur_id']==str(a['user']) and x['operation_id'] for x in moves)

def test_fefo_peremption_derogation_permission_trace_et_regles_catalogue(raw_client,account):
    c,a=raw_client,account;pack=init(c,a,True)
    post(c,a,'/lots',{'conditionnement_id':pack},422)
    past=lot(c,a,pack,'PÉRIMÉ',str(date.today()-timedelta(days=1)));early=lot(c,a,pack,'PROCHE',str(date.today()+timedelta(days=10)));late=lot(c,a,pack,'TARDIF',str(date.today()+timedelta(days=90)))
    for l in (past,early,late):entry(c,a,l['id'],10)
    post(c,a,'/sorties',{'conditionnement_id':pack,'emplacement_id':str(a['location']),'quantite':1,'lot_id':past['id'],'origine':'Test'},409)
    post(c,a,'/reservations',{'conditionnement_id':pack,'emplacement_id':str(a['location']),'quantite':1,'lot_id':late['id'],'origine':'Test'},422)
    gen=db(c);s=next(gen)
    try:
        role=s.scalar(select(RoleModel).where(RoleModel.code=='CATALOGUE'));rid=role.id_role;s.execute(delete(RolePermissionModel).where(RolePermissionModel.role_id==rid,RolePermissionModel.permission_id==permission_id('stock.fefo.deroger')));s.commit()
    finally:gen.close()
    post(c,a,'/reservations',{'conditionnement_id':pack,'emplacement_id':str(a['location']),'quantite':1,'lot_id':late['id'],'origine':'Test','justification':'Client exige ce lot'},403)
    gen=db(c);s=next(gen)
    try:s.add(RolePermissionModel(role_id=rid,permission_id=permission_id('stock.fefo.deroger')));s.commit()
    finally:gen.close()
    r=reserve(c,a,pack,1,lot_id=late['id'],justification='Choix explicite autorisé')
    gen=db(c);s=next(gen)
    try:
        trace=s.scalar(select(DerogationFEFOModel));assert trace.justification=='Choix explicite autorisé' and trace.proposition[0]['lot_id']==early['id'] and trace.choix[0]['lot_id']==late['id']
        # Expiry after reservation must be checked again at consumption (server date).
        s.execute(update(LotModel).where(LotModel.id==UUID(late['id'])).values(peremption=date.today()-timedelta(days=1)));s.commit()
    finally:gen.close()
    post(c,a,f'/reservations/{r["id"]}/consommer',status=409);post(c,a,f'/reservations/{r["id"]}/liberer',status=200)
    assert any(x['alerte']=='PÉRIMÉ' for x in stocks(c,a))

def test_stock_ne_provient_pas_du_catalogue_pagination_et_journal_immuable(raw_client,account):
    c,a=raw_client,account;pack=init(c,a);assert stocks(c,a)==[]
    l=lot(c,a,pack);assert stocks(c,a)==[]
    for i in range(3):entry(c,a,l['id'],2)
    row=stocks(c,a)[0];assert row['vendable']==row['physique']-row['reserve']==6
    result=c.get(root(a)+'/mouvements',params={'page_size':2,'page':2}).json();assert result['total']==3 and len(result['items'])==1
    assert c.get(root(a)+'/stocks',params={'q':'Produit test'}).json()['total']==1
    for statement in ('UPDATE stock_mouvements SET delta_physique=100','DELETE FROM stock_mouvements'):
        gen=db(c);s=next(gen)
        try:
            with pytest.raises(DBAPIError):s.execute(text(statement));s.commit()
            s.rollback()
        finally:gen.close()
    assert c.put(root(a)+'/mouvements/'+result['items'][0]['id'],json={}).status_code==404
    entry(c,a,l['id'],-7,kind='CORRECTION',status=409);entry(c,a,l['id'],-1,kind='CORRECTION')
    assert stocks(c,a)[0]['physique']==5

def test_transfert_interne_atomique_et_refus_destination_non_affectee(raw_client,account):
    c,a=raw_client,account;pack=init(c,a);l=lot(c,a,pack);entry(c,a,l['id'],10)
    body={'source_id':str(a['location']),'destination_id':str(a['denied']),'justification':'Réapprovisionnement','lignes':[{'conditionnement_id':pack,'quantite':4}]}
    post(c,a,'/transferts-internes',body,403);assert stocks(c,a)[0]['physique']==10
    assign(c,a,[a['denied']]);t=post(c,a,'/transferts-internes',body);assert t['statut']=='RECUE'
    rows=stocks(c,a);assert sorted(x['physique'] for x in rows)==[4,6] and sum(x['reserve'] for x in rows)==0
    post(c,a,'/transferts-internes',{**body,'lignes':[{'conditionnement_id':pack,'quantite':100}]},409)
    assert sorted(x['physique'] for x in stocks(c,a))==[4,6]

def test_transfert_intersite_reception_partielle_ecart_sans_stock_anticipe(raw_client,account):
    c,a=raw_client,account;pack=init(c,a);l=lot(c,a,pack);entry(c,a,l['id'],12)
    body={'source_id':str(a['location']),'destination_id':str(a['other_location']),'justification':'Besoin du site Owendo','lignes':[{'conditionnement_id':pack,'quantite':8}]}
    d=post(c,a,'/transferts',body);assert stocks(c,a)[0]['reserve']==0
    d=post(c,a,f'/transferts/{d["id"]}/valider',status=200);assert stocks(c,a)[0]['reserve']==8 and stocks(c,a)[0]['physique']==12
    post(c,a,f'/reservations/{d["transfert"]["reservation_id"]}/liberer',status=409)
    post(c,a,f'/transferts/{d["id"]}/expedier',status=200);assert stocks(c,a)[0]['physique']==4
    receive={'lignes':[{'ligne_id':d['lignes'][0]['id'],'quantite':5}]}
    post(c,a,f'/transferts/{d["id"]}/recevoir',receive,403)
    assign(c,a,[a['other_location']],a['other']);c.headers['X-Site-ID']=str(a['other']);assert stocks(c,a)==[]
    d=post(c,a,f'/transferts/{d["id"]}/recevoir',receive,200);assert d['statut']=='RECEPTION_PARTIELLE' and stocks(c,a)[0]['physique']==5
    post(c,a,f'/transferts/{d["id"]}/recevoir',{'lignes':[],'cloturer':True},422)
    d=post(c,a,f'/transferts/{d["id"]}/recevoir',{'lignes':[],'cloturer':True,'justification':'3 unités manquantes constatées'},200)
    assert d['statut']=='ECART_CLOTURE' and d['receptions'][-1]['ecarts'][0]['manquant']==3
    assert stocks(c,a)[0]['physique']==5
    post(c,a,f'/transferts/{d["id"]}/recevoir',receive,409)

def test_annulation_transfert_libere_sans_sortie(raw_client,account):
    c,a=raw_client,account;pack=init(c,a);l=lot(c,a,pack);entry(c,a,l['id'],7)
    d=post(c,a,'/transferts',{'source_id':str(a['location']),'destination_id':str(a['other_location']),'justification':'Besoin','lignes':[{'conditionnement_id':pack,'quantite':5}]})
    post(c,a,f'/transferts/{d["id"]}/valider',status=200)
    post(c,a,f'/transferts/{d["id"]}/annuler',{'justification':'Besoin annulé'},200)
    assert stocks(c,a)[0]['reserve']==0 and stocks(c,a)[0]['physique']==7

def inventory(c,a,pack):return post(c,a,'/inventaires',{'nom':'Inventaire réserve','type':'PARTIEL','zones':[{'nom':'Zone A','emplacement_id':str(a['location']),'conditionnement_ids':[pack]}]})

def test_inventaire_aveugle_recomptage_mouvements_avant_et_apres_validation(raw_client,account):
    c,a=raw_client,account;pack=init(c,a);l=lot(c,a,pack);entry(c,a,l['id'],10)
    inv=inventory(c,a,pack);z=inv['zones'][0];line=z['lignes'][0]
    # Creator response is blind, despite having broader permissions elsewhere.
    assert 'theorique' not in line
    post(c,a,f'/lignes-inventaire/{line["id"]}/comptages',{'quantite':10},403)
    post(c,a,f'/zones/{z["id"]}/participants',{'utilisateur_id':str(a['user'])})
    motif=post(c,a,'/motifs',{'code':'écart','nom':'écart de comptage'})
    entry(c,a,l['id'],5)
    post(c,a,f'/lignes-inventaire/{line["id"]}/comptages',{'quantite':12,'motif_id':motif['id'],'justification':'Casse constatée'})
    post(c,a,f'/lignes-inventaire/{line["id"]}/comptages',{'quantite':13},422)
    post(c,a,f'/lignes-inventaire/{line["id"]}/comptages',{'quantite':13,'motif_id':motif['id'],'justification':'Recomptage confirmé'})
    entry(c,a,l['id'],4)
    before=c.get(root(a)+f'/inventaires/{inv["id"]}').json()['zones'][0]['lignes'][0];assert before['ecart_calcule']==-2 and len(before['comptages'])==2
    post(c,a,f'/inventaires/{inv["id"]}/valider',status=200);assert stocks(c,a)[0]['physique']==17
    assert c.get(root(a)+'/mouvements').json()['items'][0]['type']=='AJUSTEMENT_INVENTAIRE'
    post(c,a,f'/inventaires/{inv["id"]}/valider',status=409)
    post(c,a,f'/lignes-inventaire/{line["id"]}/comptages',{'quantite':17,'justification':'Tardif'},409)

def test_validation_inventaire_rollback_si_stock_reserve_et_compteur_aveugle(raw_client,account):
    c,a=raw_client,account;pack=init(c,a);l=lot(c,a,pack);entry(c,a,l['id'],10);inv=inventory(c,a,pack);zone=inv['zones'][0];line=zone['lignes'][0]
    post(c,a,f'/zones/{zone["id"]}/participants',{'utilisateur_id':str(a['user'])});m=post(c,a,'/motifs',{'code':'C','nom':'Casse'})
    post(c,a,f'/lignes-inventaire/{line["id"]}/comptages',{'quantite':2,'motif_id':m['id'],'justification':'Casse'});reserve(c,a,pack,8)
    post(c,a,f'/inventaires/{inv["id"]}/valider',status=409);assert stocks(c,a)[0]['physique']==10
    gen=db(c);s=next(gen)
    try:
        role=s.scalar(select(RoleModel).where(RoleModel.code=='CATALOGUE'));s.execute(delete(RolePermissionModel).where(RolePermissionModel.role_id==role.id_role,RolePermissionModel.permission_id!=permission_id('stock.inventaire.compter')));s.commit()
    finally:gen.close()
    blind=c.get(root(a)+f'/inventaires/{inv["id"]}').json()['zones'][0]['lignes'][0]
    assert not {'theorique','ecart','stock_id','comptage_sequence','ecart_calcule'} & blind.keys()
    assert 'sequence' not in blind['comptages'][0]
    assert c.get(root(a)+'/stocks').status_code==403
    post(c,a,f'/inventaires/{inv["id"]}/valider',status=403)

@pytest.mark.parametrize('path',['/stocks','/lots','/mouvements','/sorties','/reservations','/transferts','/transferts-internes','/inventaires','/motifs'])
def test_routes_mutation_401_403_csrf_independantes_interface(raw_client,account,path):
    c,a=raw_client,account
    assert c.post(root(a)+path,json={}).status_code==401
    grant(c,a,('stock.consulter',));login(c,a)
    assert c.post(root(a)+path,json={}).status_code==403
    assert c.get(root(a)+'/stocks').status_code==200
    c.headers.pop('X-CSRF-Token');assert c.post(root(a)+path,json={}).status_code==403

def test_isolation_organisation_site_emplacement_et_contexte(raw_client,account):
    c,a=raw_client,account;pack=init(c,a);l=lot(c,a,pack)
    entry(c,a,l['id'],1,a['denied'],status=403);entry(c,a,l['id'],1,a['other_location'],status=403)
    assert c.get(root({'org':uuid4()})+'/stocks').status_code==403
    c.headers['X-Emplacement-ID']=str(a['denied']);assert c.get(root(a)+'/stocks').status_code==403
    c.headers.pop('X-Emplacement-ID');assert c.get(root(a)+'/stocks',params={'emplacement_id':str(a['denied'])}).status_code==403

def test_concurrence_postgresql_pas_de_surreservation(raw_client,account):
    c,a=raw_client,account;pack=init(c,a);l=lot(c,a,pack);entry(c,a,l['id'],10)
    gen=db(c);session=next(gen);engine=session.get_bind();gen.close()
    if engine.dialect.name!='postgresql':pytest.skip('Verrou transactionnel PostgreSQL avec deux connexions réelles')
    def worker():
        with Session(engine) as s:
            service=StockService(s,a['org'],a['user'],lambda *args:None)
            try:
                service.operation(uuid4(),'RESERVER',{},lambda:service.reserver({'emplacement_id':a['location'],'conditionnement_id':pack,'quantite':7,'origine':'Test concurrent'}));return 'ok'
            except ConflitStock:return 'insuffisant'
    with ThreadPoolExecutor(max_workers=2) as pool:assert sorted(pool.map(lambda _:worker(),range(2)))==['insuffisant','ok']
    assert stocks(c,a)[0]['reserve']==7

@pytest.mark.parametrize('state',['inactive','expired','future','no_assignment','no_role','no_permission','no_location','split_assignments'])
def test_affectation_effective_exigee_pour_chaque_mutation_contextuelle(raw_client,account,state):
    from test_http_autorisations_p1 import set_state
    c,a=raw_client,account;pack=init(c,a);l=lot(c,a,pack);entry(c,a,l['id'],10)
    r=reserve(c,a,pack,1);inv=inventory(c,a,pack);z=inv['zones'][0];line=z['lignes'][0]
    d=post(c,a,'/transferts',{'source_id':str(a['location']),'destination_id':str(a['other_location']),'justification':'Test sécurité','lignes':[{'conditionnement_id':pack,'quantite':1}]})
    set_state(c,a,state)
    cases=[('/mouvements',{'lot_id':l['id'],'emplacement_id':str(a['location']),'quantite':1,'origine':'Test','justification':'Test'}),('/reservations',{'conditionnement_id':pack,'emplacement_id':str(a['location']),'quantite':1,'origine':'Test'}),(f'/reservations/{r["id"]}/consommer',{}),(f'/reservations/{r["id"]}/liberer',{}),(f'/transferts/{d["id"]}/valider',{}),(f'/transferts/{d["id"]}/expedier',{}),(f'/transferts/{d["id"]}/recevoir',{'lignes':[]}),(f'/transferts/{d["id"]}/annuler',{'justification':'Test'}),('/inventaires',{'nom':'Test','type':'COMPLET','zones':[{'nom':'Zone','emplacement_id':str(a['location'])}]}),(f'/zones/{z["id"]}/participants',{'utilisateur_id':str(a['user'])}),(f'/lignes-inventaire/{line["id"]}/comptages',{'quantite':10}),(f'/inventaires/{inv["id"]}/valider',{})]
    for path,body in cases:post(c,a,path,body,403)
    gen=db(c);s=next(gen)
    try:
        assert s.scalar(select(func.sum(StockEmplacementModel.physique)))==10
        assert s.scalar(select(func.sum(StockEmplacementModel.reserve)))==1
        assert s.scalar(select(InventaireModel.statut))=='OUVERT'
    finally:gen.close()


def test_transfert_fefo_multiligne_trace_immuable_et_mouvements_internes(raw_client,account):
    c,a=raw_client,account;pack=init(c,a,True);assign(c,a,[a['denied']])
    for number,days in [('PROCHE',10),('TARDIF',30)]:
        l=lot(c,a,pack,number,str(date.today()+timedelta(days=days)));entry(c,a,l['id'],10)
    late=l
    t=post(c,a,'/transferts-internes',{'source_id':str(a['location']),'destination_id':str(a['denied']),'justification':'Dérogation autorisée tracée','lignes':[{'conditionnement_id':pack,'quantite':2,'lot_id':late['id']},{'conditionnement_id':pack,'quantite':3}]})
    assert t['statut']=='RECUE' and sum(x['quantite'] for x in t['lignes'])==5
    gen=db(c);s=next(gen)
    try:
        trace=s.scalar(select(DerogationFEFOModel));assert str(trace.reservation_id)==t['transfert']['reservation_id']
        assert trace.choix==[{'lot_id':late['id'],'quantite':2}]
        with pytest.raises(DBAPIError):s.execute(update(DerogationFEFOModel).values(justification='Remplacement interdit'));s.commit()
        s.rollback()
        assert set(s.scalars(select(MouvementStockModel.type)))>={'TRANSFERT_SORTIE','TRANSFERT_ENTREE'}
    finally:gen.close()


def test_inventaire_multizone_pagine_et_contexte_consultation_restraint(raw_client,account):
    c,a=raw_client,account;pack=init(c,a);assign(c,a,[a['denied']])
    # Actual entries only; catalogue and inventory never synthesize physical quantities.
    for n in range(31):
        l=lot(c,a,pack,'PAG-'+str(n));entry(c,a,l['id'],1)
        if n==0:entry(c,a,l['id'],2,a['denied'])
    selected=c.get(root(a)+'/lots',params={'conditionnement_id':pack,'page_size':2,'selected_lot_id':l['id']}).json();assert len(selected['items'])==2 and selected['selection']['id']==l['id']
    assert c.get(root(a)+'/lots',params={'conditionnement_id':pack,'q':'pag-30'}).json()['total']==1
    inv=post(c,a,'/inventaires',{'nom':'Inventaire complet','type':'COMPLET','zones':[{'nom':'Réserve','emplacement_id':str(a['location'])},{'nom':'Comptoir','emplacement_id':str(a['denied'])}]})
    assert sum(len(z['lignes']) for z in inv['zones'])==25
    assert sorted(z['total'] for z in inv['zones'])==[1,31]
    first=next(z for z in inv['zones'] if z['total']==31);second=next(z for z in inv['zones'] if z['total']==1)
    resp=c.get(root(a)+f'/inventaires/{inv["id"]}',params={'zone_id':first['id'],'page':2}).json()
    assert sum(len(z['lignes']) for z in resp['zones'])==6
    resp=c.get(root(a)+f'/inventaires/{inv["id"]}',params={'zone_id':second['id']}).json()
    assert sum(len(z['lignes']) for z in resp['zones'])==1
    assert c.get(root(a)+'/stocks',params={'page_size':101}).status_code==422
    gen=db(c);s=next(gen)
    try:
        role=s.scalar(select(RoleModel).where(RoleModel.code=='CATALOGUE'));s.execute(delete(RolePermissionModel).where(RolePermissionModel.role_id==role.id_role,RolePermissionModel.permission_id!=permission_id('stock.consulter')));s.commit()
    finally:gen.close()
    context=c.get(root(a)+'/contextes').json()
    assert set(x['id'] for x in context['destinations'])=={str(a['location']),str(a['denied'])}
    assert str(a['other_location']) not in {x['id'] for x in context['destinations']}


def test_idempotence_ne_reutilise_pas_une_cle_avec_dautres_donnees(raw_client,account):
    c,a=raw_client,account;pack=init(c,a);l=lot(c,a,pack);key=str(uuid4())
    body={'cle':key,'lot_id':l['id'],'emplacement_id':str(a['location']),'quantite':5,'origine':'Document A','justification':'Entrée constatée'}
    first=c.post(root(a)+'/mouvements',json=body);assert first.status_code==201
    assert c.post(root(a)+'/mouvements',json=body).json()==first.json()
    assert c.post(root(a)+'/mouvements',json={**body,'quantite':6}).status_code==409
    assert stocks(c,a)[0]['physique']==5


def test_inventaires_ouverts_non_recouvrants_annulation_tracee_sans_variation(raw_client,account):
    c,a=raw_client,account;pack=init(c,a);l=lot(c,a,pack);entry(c,a,l['id'],10)
    inv=inventory(c,a,pack)
    post(c,a,'/inventaires',{'nom':'Chevauchement','type':'COMPLET','zones':[{'nom':'Zone','emplacement_id':str(a['location'])}]},409)
    post(c,a,f'/inventaires/{inv["id"]}/annuler',{'justification':'Périmètre à reprendre'},200)
    assert stocks(c,a)[0]['physique']==10
    audit=c.get(root(a)+f'/inventaires/{inv["id"]}').json()['annulation'];assert audit['justification']=='Périmètre à reprendre' and audit['auteur_id']==str(a['user'])
    assert inventory(c,a,pack)['statut']=='OUVERT'
    post(c,a,f'/inventaires/{inv["id"]}/valider',status=409)
    gen=db(c);s=next(gen)
    try:assert s.scalar(select(func.count()).select_from(OperationStockModel).where(OperationStockModel.empreinte.is_not(None)))>0
    finally:gen.close()


@pytest.mark.parametrize('kind',['ENTREE_IDEMPOTENTE','SORTIE','TRANSFERT_INTERNE'])
def test_concurrence_postgresql_mutations_et_double_envoi(raw_client,account,kind):
    c,a=raw_client,account;pack=init(c,a);l=lot(c,a,pack);entry(c,a,l['id'],10);assign(c,a,[a['denied']])
    gen=db(c);session=next(gen);engine=session.get_bind();gen.close()
    if engine.dialect.name!='postgresql':pytest.skip('Deux transactions PostgreSQL indépendantes')
    common=uuid4()
    def worker():
        with Session(engine) as s:
            service=StockService(s,a['org'],a['user'],lambda *args:None)
            if kind=='ENTREE_IDEMPOTENTE':
                data={'lot_id':l['id'],'emplacement_id':a['location'],'quantite':3,'origine':'Double envoi','justification':'Entrée réelle unique'};action=lambda:service.entree(data);key=common
            elif kind=='SORTIE':
                data={'conditionnement_id':pack,'emplacement_id':a['location'],'quantite':7,'origine':'Sortie concurrente'};action=lambda:service.sortie(data);key=uuid4()
            else:
                data={'source_id':a['location'],'destination_id':a['denied'],'justification':'Transfert concurrent','lignes':[{'conditionnement_id':pack,'quantite':7}]};action=lambda:service.transfert_interne(data);key=uuid4()
            try:service.operation(key,kind,data,action);return 'ok'
            except ConflitStock:return 'insuffisant'
    with ThreadPoolExecutor(max_workers=2) as pool:results=sorted(pool.map(lambda _:worker(),range(2)))
    if kind=='ENTREE_IDEMPOTENTE':assert results==['ok','ok'] and sum(r['physique'] for r in stocks(c,a))==13
    else:
        assert results==['insuffisant','ok']
        source=next(r for r in stocks(c,a) if r['emplacement_id']==str(a['location']));assert source['physique']==3 and source['reserve']==0
        if kind=='TRANSFERT_INTERNE':assert sum(r['physique'] for r in stocks(c,a))==10


def test_migration_p3_additive_retour_p2_preserve_catalogue_et_permissions(tmp_path,monkeypatch):
    import os
    from alembic import command
    from alembic.config import Config
    from sqlalchemy import create_engine,inspect
    from neosys_pharma.infrastructure.config import get_settings
    from neosys_pharma.infrastructure.organisation_repository import SqlAlchemyOrganisationRepository
    from neosys_pharma.infrastructure.catalogue_repository import SqlAlchemyCatalogueRepository
    from neosys_pharma.application.catalogue_service import CatalogueService
    from neosys_pharma.domain.organisation.entities import Organisation,Site,Emplacement
    from neosys_pharma.domain.organisation.securite import Utilisateur
    from neosys_pharma.domain.catalogue import CategorieProduit,Produit,Conditionnement,ReferenceProduit,TypeReference
    from neosys_pharma.infrastructure.securite_models import PermissionModel
    from neosys_pharma.infrastructure.catalogue_models import ProduitModel
    url=os.getenv('TEST_MIGRATION_DATABASE_URL',f'sqlite:///{tmp_path / "p3-migration.db"}')
    monkeypatch.setenv('DATABASE_URL',url);get_settings.cache_clear();cfg=Config('alembic.ini');engine=None
    try:
        command.upgrade(cfg,'6bc8179d433e');engine=create_engine(url)
        with Session(engine) as s:
            organisation=Organisation(nom_commercial='Migration P3',raison_sociale='Migration P3');site=Site(organisation_id=organisation.id_organisation,code='P3',nom='Site P3');location=Emplacement(site_id=site.id_site,code='R',nom='Réserve P3');user=Utilisateur(organisation_id=organisation.id_organisation,identifiant='migration-p3',nom='Utilisateur migration P3')
            orgrepo=SqlAlchemyOrganisationRepository(s)
            for x in (organisation,site,location):orgrepo.ajouter(x)
            SqlAlchemySecuriteRepository(s).ajouter(user);s.commit()
            catalogue=CatalogueService(SqlAlchemyCatalogueRepository(s));cat=CategorieProduit(organisation_id=organisation.id_organisation,code='ÉTÉ',nom='Catégorie existante');catalogue.enregistrer(cat)
            produit=Produit(organisation_id=organisation.id_organisation,nom='Produit existant',categorie_id=cat.id_categorie,description='Commentaire historique en casse naturelle.');pack=Conditionnement(organisation_id=organisation.id_organisation,produit_id=produit.id_produit,code='B20',libelle='Boîte existante');catalogue.enregistrer(produit,nouveau=True,premier_conditionnement=pack)
            catalogue.enregistrer(ReferenceProduit(organisation_id=organisation.id_organisation,conditionnement_id=pack.id_conditionnement,type_reference=TypeReference.HISTORIQUE,valeur='00MixedCase-P3'))
        command.upgrade(cfg,'head');command.check(cfg)
        with Session(engine) as s:
            assert s.scalar(select(func.count()).select_from(StockEmplacementModel))==0
            assert s.scalar(select(func.count()).select_from(RolePermissionModel).where(RolePermissionModel.permission_id.in_([permission_id(p) for p,n in P3_PERMISSIONS])))==0
            service=StockService(s,organisation.id_organisation,user.id_utilisateur,lambda *args:None)
            l=service.operation(uuid4(),'LOT',{},lambda:service.creer_lot({'conditionnement_id':pack.id_conditionnement,'numero':None,'peremption':None}))
            service.operation(uuid4(),'ENTREE',{},lambda:service.entree({'lot_id':l['id'],'emplacement_id':location.id_emplacement,'quantite':2,'origine':'Migration isolée','justification':'Vérification trace'}))
            assert s.scalar(select(func.count()).select_from(MouvementStockModel))==1
            with pytest.raises(DBAPIError):s.execute(text('DELETE FROM stock_mouvements'));s.commit()
            s.rollback()
        command.downgrade(cfg,'6bc8179d433e');assert 'stock_mouvements' not in inspect(engine).get_table_names()
        with Session(engine) as s:
            assert s.get(ProduitModel,produit.id_produit).description=='Commentaire historique en casse naturelle.'
            assert s.scalar(select(PermissionModel).where(PermissionModel.code=='catalogue.consulter')) is not None
        command.upgrade(cfg,'head');command.check(cfg)
        with Session(engine) as s:
            assert s.scalar(select(func.count()).select_from(StockEmplacementModel))==0
            from neosys_pharma.infrastructure.catalogue_models import ReferenceProduitModel
            assert s.scalar(select(ReferenceProduitModel.valeur).where(ReferenceProduitModel.conditionnement_id==pack.id_conditionnement))=='00MixedCase-P3'
    finally:
        if engine:engine.dispose()
        get_settings.cache_clear()


def test_recherche_unicode_et_identifiants_externes_non_transformes(raw_client,account):
    from neosys_pharma.infrastructure.catalogue_models import ProduitModel,ConditionnementModel
    c,a=raw_client,account;pack=init(c,a);l=lot(c,a,pack,'LoT-é-œ-%_');entry(c,a,l['id'],1)
    gen=db(c);s=next(gen)
    try:
        product=s.get(ProduitModel,s.get(ConditionnementModel,UUID(pack)).produit_id);product.nom='ÉTÉ ŒUF';s.commit()
    finally:gen.close()
    assert c.get(root(a)+'/stocks',params={'q':'e\u0301te\u0301 œuf'}).json()['total']==1
    assert c.get(root(a)+'/stocks',params={'q':'lot-É-Œ-%_'}).json()['total']==1
    assert c.get(root(a)+'/stocks',params={'q':'ABSENT%'}).json()['total']==0
    assert stocks(c,a)[0]['lot']=='LoT-é-œ-%_'
    assert c.get(root(a)+'/conditionnements',params={'q':'été œuf'}).json()['total']==1


def test_permission_validation_dun_autre_emplacement_ne_revele_pas_le_theorique(raw_client,account):
    from neosys_pharma.domain.organisation.securite import Role,TypeRole,RolePermission
    c,a=raw_client,account;pack=init(c,a);l=lot(c,a,pack);entry(c,a,l['id'],10);inv=inventory(c,a,pack)
    gen=db(c);s=next(gen)
    try:
        role=s.scalar(select(RoleModel).where(RoleModel.code=='CATALOGUE'));s.execute(delete(RolePermissionModel).where(RolePermissionModel.role_id==role.id_role,RolePermissionModel.permission_id!=permission_id('stock.inventaire.gerer')))
        repo=SqlAlchemySecuriteRepository(s);r=Role(organisation_id=a['org'],code='VALIDER_AILLEURS',nom='Valider ailleurs',type_role=TypeRole.PERSONNALISE);repo.ajouter(r);repo.ajouter(RolePermission(role_id=r.id_role,permission_id=permission_id('stock.inventaire.valider')))
        aff=AffectationSite(utilisateur_id=a['user'],site_id=a['site'],date_debut=date.today()-timedelta(days=1));repo.ajouter(aff);repo.ajouter(AffectationRole(affectation_site_id=aff.id_affectation_site,role_id=r.id_role));repo.ajouter(AffectationEmplacement(affectation_site_id=aff.id_affectation_site,emplacement_id=a['denied']));s.commit()
    finally:gen.close()
    c.headers['X-Emplacement-ID']=str(a['location'])
    response=c.get(root(a)+f'/inventaires/{inv["id"]}');assert response.status_code==200,response.text
    assert 'theorique' not in response.json()['zones'][0]['lignes'][0] and 'snapshot_sequence' not in response.json()
    post(c,a,f'/inventaires/{inv["id"]}/valider',status=403)


def test_routes_actions_objets_refusees_sans_session_et_en_lecture_seule(raw_client,account):
    c,a=raw_client,account;k=str(uuid4())
    paths=[f'/reservations/{k}/liberer',f'/reservations/{k}/consommer',f'/transferts/{k}/valider',f'/transferts/{k}/expedier',f'/transferts/{k}/recevoir',f'/transferts/{k}/annuler',f'/zones/{k}/participants',f'/lignes-inventaire/{k}/comptages',f'/inventaires/{k}/valider',f'/inventaires/{k}/annuler']
    for path in paths:assert c.post(root(a)+path,json={}).status_code==401
    grant(c,a,('stock.consulter',));login(c,a)
    for path in paths:assert c.post(root(a)+path,json={}).status_code==403


def test_inventaire_initial_suivi_zero_sans_stock_fictif_et_sans_remise_a_zero(raw_client,account):
    c,a=raw_client,account;pack=init(c,a);l=lot(c,a,pack);assert stocks(c,a)==[]
    body={'lot_id':l['id'],'emplacement_id':str(a['location']),'justification':'Préparation inventaire initial'}
    post(c,a,'/stocks',body);assert stocks(c,a)[0]['physique']==0 and stocks(c,a)[0]['reserve']==0
    assert c.get(root(a)+'/mouvements').json()['total']==0
    inv=inventory(c,a,pack);z=inv['zones'][0];line=z['lignes'][0];post(c,a,f'/zones/{z["id"]}/participants',{'utilisateur_id':str(a['user'])});m=post(c,a,'/motifs',{'code':'INITIAL','nom':'Comptage initial'})
    post(c,a,f'/lignes-inventaire/{line["id"]}/comptages',{'quantite':3,'motif_id':m['id'],'justification':'Trois boîtes physiquement constatées'});post(c,a,f'/inventaires/{inv["id"]}/valider',status=200)
    assert stocks(c,a)[0]['physique']==3
    post(c,a,'/stocks',{**body,'emplacement_id':str(a['denied'])},403)
    post(c,a,'/stocks',body);assert stocks(c,a)[0]['physique']==3
    assert c.get(root(a)+'/mouvements').json()['total']==1
    entry(c,a,l['id'],1,a['denied'],status=403)
