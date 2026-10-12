from types import SimpleNamespace as NS
from decimal import Decimal
from concurrent.futures import ThreadPoolExecutor
from uuid import UUID,uuid4
import pytest
from sqlalchemy import select,delete
from sqlalchemy.orm import Session
from test_vente import raw_client,account,setup,create,line,act,post,root,db
from neosys_pharma.domain.remises import calculer,repartir,montant_remise
from neosys_pharma.infrastructure.securite_models import RoleModel,RolePermissionModel
from neosys_pharma.domain.organisation.permissions_systeme import permission_id
from neosys_pharma.application.vente_service import VenteService
from neosys_pharma.application.stock_service import StockService
from neosys_pharma.domain.stock import ConflitStock


def cap(c,a,role=None,**kwargs):
    if not role:
        gen=db(c);s=next(gen)
        try:role=str(s.scalar(select(RoleModel.id_role).where(RoleModel.code=='CATALOGUE')))
        finally:gen.close()
    return post(c,a,'/plafonds',{'role_id':role,'max_pourcentage':'20','max_montant_xaf':'1000',**kwargs})
def request(c,a,v,**kwargs):return post(c,a,f'/{v["id"]}/remises',{'revision':v['revision'],'type':'POURCENTAGE','valeur':'10','justification':'Geste commercial',**kwargs})
def decide(c,a,v,r,status=200,**kwargs):return post(c,a,f'/{v["id"]}/remises/{r["id"]}/decision',{'revision':v['revision'],'autoriser':True,'justification':'Contrôle responsable',**kwargs},status)
def current(c,a,v):return c.get(root(a)+f'/{v["id"]}').json()


def test_calcul_ttc_cumul_repartition_tva_et_arrondis():
    rows=[NS(id='a',montants={'ttc':'1000'},instantane_tarif={'taux_tva':'18'}),NS(id='b',montants={'ttc':'2000'},instantane_tarif={'taux_tva':'0'})]
    requests=[NS(statut='AUTORISEE',ligne_id='a',type='POURCENTAGE',valeur=10),NS(statut='AUTORISEE',ligne_id=None,type='POURCENTAGE',valeur=10)]
    x=calculer(rows,requests);assert x['totaux']['ttc']=='2610' and x['totaux']['remise_globale']=='290'
    assert x['lignes']['a']['ttc']=='810' and x['lignes']['b']['ttc']=='1800'
    assert Decimal(x['totaux']['ht'])+Decimal(x['totaux']['tva'])==Decimal(x['totaux']['ttc'])
    assert repartir(1,{'b':Decimal(1),'a':Decimal(1)})=={'b':0,'a':1}
    for amount in range(100):assert sum(repartir(amount,{'a':Decimal(1),'b':Decimal(3),'c':Decimal(7)}).values())==amount
    requests[0].statut='DEMANDEE';assert calculer(rows,requests)['totaux']['ttc']=='2700'
    requests[0].statut='AUTORISEE';requests[1].valeur=100;assert calculer(rows,requests)['totaux']['ttc']=='0'

@pytest.mark.parametrize('kind,value,eligible',[('MONTANT_XAF',11,10),('MONTANT_XAF',-1,10),('POURCENTAGE',101,10),('POURCENTAGE','NaN',10)])
def test_remises_hors_eligible_refusees(kind,value,eligible):
    with pytest.raises(ValueError):montant_remise(kind,value,eligible)


def test_plafonds_cumul_snapshot_invalidation_et_validation(raw_client,account):
    c,a=raw_client,account;prod,pack,pid,_=setup(c,a);v=line(c,a,create(c,a,pid),prod,pack,3)
    r=request(c,a,v,ligne_id=v['lignes'][0]['id']);decide(c,a,v,r,422)
    cap(c,a);v=current(c,a,v);assert v['remises'][0]['statut']=='DEMANDEE'
    d=decide(c,a,v,r);assert d['statut']=='AUTORISEE'
    v=current(c,a,v);assert v['totaux']['ttc']=='271';assert v['lignes'][0]['remise_appliquee']
    r=request(c,a,v);assert current(c,a,v)['totaux']['ttc']=='271'
    decide(c,a,v,r);v=current(c,a,v);assert v['totaux']['ttc']=='244'
    assert act(c,a,v,'valider')['etat']=='VALIDEE_PREPARATION'
    v=current(c,a,v);v=act(c,a,v,'reprendre');v=line(c,a,v,prod,pack,2,ligne_id=v['lignes'][0]['id'])
    assert all(r['statut']=='INVALIDEE' for r in v['remises']) and v['totaux']['ttc']=='201'


def test_plafond_depasse_ou_desactive_et_droits(raw_client,account):
    c,a=raw_client,account;prod,pack,pid,_=setup(c,a);config=cap(c,a,max_pourcentage='5');v=line(c,a,create(c,a,pid),prod,pack);r=request(c,a,v);decide(c,a,v,r,422)
    cap(c,a,revision=config['revision'],actif=False);v=current(c,a,v);decide(c,a,v,r,422)
    gen=db(c);s=next(gen)
    try:s.execute(delete(RolePermissionModel).where(RolePermissionModel.permission_id==permission_id('vente.remise.parametrer')));s.commit()
    finally:gen.close()
    post(c,a,'/plafonds',{},403)
    post(c,a,f'/{v["id"]}/remises',{'revision':v['revision'],'type':'MONTANT_XAF','valeur':'9999','justification':'Trop','ligne_id':v['lignes'][0]['id']},422)


def manager(c,a):
    from neosys_pharma.domain.organisation.securite import Role,RolePermission,TypeRole,Utilisateur
    from neosys_pharma.infrastructure.securite_repository import SqlAlchemySecuriteRepository
    from neosys_pharma.infrastructure.provisionnement import provisionner
    from test_authentification import PASSWORD
    gen=db(c);s=next(gen)
    try:
        repo=SqlAlchemySecuriteRepository(s);role=Role(organisation_id=a['org'],code='APPROVER',nom='Responsable',type_role=TypeRole.PERSONNALISE);repo.ajouter(role)
        for p in ('vente.consulter','vente.remise.autoriser'):repo.ajouter(RolePermission(role_id=role.id_role,permission_id=permission_id(p)))
        s.commit();user=Utilisateur(organisation_id=a['org'],identifiant='responsable',nom='Responsable réel');provisionner(s,user,[a['site']],[a['location']],[role.id_role],PASSWORD)
        return user.id_utilisateur,role.id_role
    finally:gen.close()


def test_autorisation_locale_propre_identite_sans_changer_session(raw_client,account):
    from test_authentification import PASSWORD
    c,a=raw_client,account;prod,pack,pid,_=setup(c,a);user,role=manager(c,a);cap(c,a,str(role));v=line(c,a,create(c,a,pid),prod,pack);r=request(c,a,v)
    token=c.cookies.get('neosys_session')
    body={'revision':v['revision'],'autoriser':True,'justification':'Présence du responsable','identifiant':'responsable','password':'incorrect'}
    post(c,a,f'/{v["id"]}/remises/{r["id"]}/locale',body,401)
    body['password']=PASSWORD;d=post(c,a,f'/{v["id"]}/remises/{r["id"]}/locale',body,200)
    assert d['autorisation']['auteur_id']==str(user) and d['auteur_id']==str(a['user'])
    assert d['autorisation']['local'] and d['autorisation']['approbateur_nom']=='Responsable réel'
    assert c.cookies.get('neosys_session')==token and c.get('/api/auth/me').json()['utilisateur']['id_utilisateur']==str(a['user'])
    assert PASSWORD not in str(d) and 'password' not in str(d)


def test_decision_distante_session_responsable_et_permission_locale(raw_client,account):
    from starlette.testclient import TestClient
    from test_authentification import login,PASSWORD
    c,a=raw_client,account;prod,pack,pid,_=setup(c,a);user,role=manager(c,a);cap(c,a,str(role));v=line(c,a,create(c,a,pid),prod,pack);r=request(c,a,v)
    with TestClient(c.app) as remote:
        login(remote,{**a,'user':user},identifiant='responsable')
        pending=remote.get(root(a)+'/remises-attente').json();assert pending['total']==1
        decide(remote,a,v,r);assert current(c,a,v)['totaux']['ttc']=='271'
    v=current(c,a,v);r=request(c,a,v)
    post(c,a,f'/{v["id"]}/remises/{r["id"]}/locale',{'revision':v['revision'],'autoriser':True,'justification':'Sans droit','identifiant':'alice','password':PASSWORD},422)
    # Alice has authorization permission but no configured cap for her own role.


def test_concurrence_decisions_une_seule_autorisation(raw_client,account):
    c,a=raw_client,account;prod,pack,pid,_=setup(c,a);cap(c,a);v=line(c,a,create(c,a,pid),prod,pack);r=request(c,a,v)
    gen=db(c);s=next(gen);engine=s.get_bind();gen.close()
    if engine.dialect.name!='postgresql':pytest.skip('Concurrence PostgreSQL réelle')
    def worker():
        with Session(engine) as s:
            stock=StockService(s,a['org'],a['user'],lambda *args:None);service=VenteService(stock,a['site'])
            try:
                stock.operation(uuid4(),'P4:DECISION',{},lambda:service.decider_remise(service.obtenir(UUID(v['id']),'vente.remise.autoriser'),UUID(r['id']),{'revision':v['revision'],'autoriser':True,'justification':'Concurrence'}));return 'ok'
            except ConflitStock:return 'conflit'
    with ThreadPoolExecutor(max_workers=2) as pool:assert sorted(pool.map(lambda _:worker(),range(2)))==['conflit','ok']
    assert current(c,a,v)['totaux']['ttc']=='271'


def test_cumul_ne_contourne_pas_le_plafond_et_revocation(raw_client,account):
    c,a=raw_client,account;prod,pack,pid,_=setup(c,a);config=cap(c,a);v=line(c,a,create(c,a,pid),prod,pack);r=request(c,a,v,ligne_id=v['lignes'][0]['id'],valeur='20');decide(c,a,v,r);v=current(c,a,v)
    r=request(c,a,v,valeur='20');decide(c,a,v,r,422);assert current(c,a,v)['totaux']['ttc']=='241'
    # Updating an authorization limit invalidates previously authorized amounts.
    cap(c,a,revision=config['revision'],max_pourcentage='30');v=current(c,a,v)
    assert v['totaux']['remise_ligne']=='0' and all(r['statut']=='INVALIDEE' for r in v['remises'])

@pytest.mark.parametrize('state',['inactive','expired','future','no_assignment','no_location','split_assignments'])
def test_approbateur_affectation_effective_et_aucun_acces_implicite(raw_client,account,state):
    from test_http_autorisations_p1 import set_state
    c,a=raw_client,account;prod,pack,pid,_=setup(c,a);cap(c,a);v=line(c,a,create(c,a,pid),prod,pack);r=request(c,a,v);set_state(c,a,state);decide(c,a,v,r,403)


def test_recherche_pagination_et_stock_scopes_p4(raw_client,account):
    c,a=raw_client,account;prod,pack,pid,_=setup(c,a)
    assert c.get(root(a)+'/conditionnements',params={'q':'pr'}).json()['total']==0
    assert c.get(root(a)+'/conditionnements',params={'q':'produit','page_size':1}).json()['items'][0]['produit_id']==prod
    r=c.get(root(a)+'/stocks',params={'emplacement_id':str(a['location']),'conditionnement_id':pack}).json();assert r['totaux']=={'physique':10,'reserve':0,'vendable':10}
    assert c.get(root(a)+'/stocks',params={'emplacement_id':str(a['denied']),'conditionnement_id':pack}).status_code==403
    assert c.get(root({'org':uuid4()})+'/conditionnements',params={'q':'produit'}).status_code==403


def test_refus_identifiants_valides_sans_permission_et_corps_financier_forge(raw_client,account):
    from test_authentification import PASSWORD
    c,a=raw_client,account;prod,pack,pid,_=setup(c,a);v=line(c,a,create(c,a,pid),prod,pack);r=request(c,a,v)
    gen=db(c);s=next(gen)
    try:s.execute(delete(RolePermissionModel).where(RolePermissionModel.permission_id==permission_id('vente.remise.autoriser')));s.commit()
    finally:gen.close()
    post(c,a,f'/{v["id"]}/remises/{r["id"]}/locale',{'revision':v['revision'],'autoriser':True,'justification':'Refus attendu','identifiant':'alice','password':PASSWORD},403)
    post(c,a,f'/{v["id"]}/lignes',{'revision':v['revision'],'produit_id':prod,'conditionnement_id':pack,'quantite':1,'remise_appliquee':{'ttc':'0'}},422)
    assert current(c,a,v)['totaux']['ttc']=='301'


def test_refus_preserve_les_autres_demandes_sans_changement_financier(raw_client,account):
    c,a=raw_client,account;prod,pack,pid,_=setup(c,a);cap(c,a);v=line(c,a,create(c,a,pid),prod,pack)
    first=request(c,a,v,ligne_id=v['lignes'][0]['id']);other=request(c,a,v)
    decide(c,a,v,first,autoriser=False);v=current(c,a,v)
    assert v['totaux']['remise_ligne']=='0' and v['totaux']['remise_globale']=='0'
    pending=next(r for r in v['remises'] if r['id']==other['id'])
    assert pending['statut']=='DEMANDEE' and pending['revision_vente']==v['revision']
    decide(c,a,v,pending);assert current(c,a,v)['totaux']['ttc']=='271'


def test_attente_reprise_preserve_la_base_des_demandes(raw_client,account):
    c,a=raw_client,account;prod,pack,pid,_=setup(c,a);cap(c,a);v=line(c,a,create(c,a,pid),prod,pack)
    r=request(c,a,v);v=act(c,a,v,'attendre');v=act(c,a,v,'reprendre')
    assert v['totaux']['ttc']=='301'
    pending=next(x for x in v['remises'] if x['id']==r['id'])
    assert pending['statut']=='DEMANDEE' and pending['revision_vente']==v['revision']
    decide(c,a,v,pending);assert current(c,a,v)['totaux']['ttc']=='271'


def test_plafond_cible_transmission_reservations_et_annulation(raw_client,account):
    from test_stock import stocks
    c,a=raw_client,account;prod,pack,pid,cid=setup(c,a)
    own=cap(c,a);_,role=manager(c,a);other=cap(c,a,str(role))
    v=line(c,a,create(c,a,pid),prod,pack,2);r=request(c,a,v);decide(c,a,v,r)
    v=current(c,a,v);v=act(c,a,v,'valider');v=act(c,a,v,'transmettre',caisse_id=cid)
    reservations=[x['id'] for l in v['lignes'] for x in l['reservations']]
    cap(c,a,str(role),revision=other['revision'],max_pourcentage='30')
    assert current(c,a,v)==v  # unrelated cap: no revision/state/amount changes
    cap(c,a,revision=own['revision'])  # same values: no financial invalidation
    assert current(c,a,v)==v
    cap(c,a,revision=own['revision'],max_pourcentage='5')
    changed=current(c,a,v)
    assert changed['etat']=='PREPARATION' and changed['caisse_id'] is None
    assert changed['totaux']['remise_globale']=='0' and changed['revision']==v['revision']+1
    assert [x['id'] for l in changed['lignes'] for x in l['reservations']]==reservations
    assert stocks(c,a)[0]['reserve']==2
    stale=post(c,a,f'/{v["id"]}/transmettre',{'revision':v['revision'],'caisse_id':cid},409)
    act(c,a,changed,'annuler',justification='Revalidation abandonnée')
    assert stocks(c,a)[0]['reserve']==0 and stocks(c,a)[0]['physique']==10
    history=c.get(root(a)+f'/{v["id"]}/historique').json()['items']
    assert any(e['type']=='PLAFOND_MODIFIE' and e['donnees']['reservations_conservees'] for e in history)
