from uuid import UUID,uuid4
from datetime import date,timedelta
from concurrent.futures import ThreadPoolExecutor
import pytest
from sqlalchemy import text,select,delete,func
from sqlalchemy.orm import Session
from sqlalchemy.exc import DBAPIError
from test_vente import raw_client,account,setup,create,line,act,db
from test_stock import stocks,root as stock_root
from test_remises import cap
from test_catalogue import post as catalogue_post
from neosys_pharma.application.proforma_service import ProformaService
from neosys_pharma.application.stock_service import StockService
from neosys_pharma.infrastructure.proforma_models import ProformaModel,VersionProformaModel
from neosys_pharma.domain.stock import ConflitStock
from neosys_pharma.domain.organisation.permissions_systeme import permission_id
from neosys_pharma.infrastructure.securite_models import RolePermissionModel


def root(a):return f'/api/proformas/organisations/{a["org"]}'
def post(c,a,path,body=None,status=201):
    r=c.post(root(a)+path,json={'cle':str(uuid4()),**(body or {})});assert r.status_code==status,r.text;return r.json()
def new(c,a,**kw):return post(c,a,'',{'emplacement_id':str(a['location']),'destinataire':{'nom':'CLIENT ÉTÉ','adresse':'Libreville'},**kw})
def add(c,a,v,prod,pack,q=3,**kw):return post(c,a,f'/versions/{v["id"]}/lignes',{'revision':v['revision'],'produit_id':prod,'conditionnement_id':pack,'quantite':q,**kw})
def action(c,a,v,name,**kw):return post(c,a,f'/versions/{v["id"]}/{name}',{'revision':v['revision'],**kw},201 if name in ('nouvelle-version','reprendre') else 200)
def current(c,a,v):return c.get(root(a)+f'/versions/{v["id"]}').json()
def pdf(c,a,v):return c.get(root(a)+f'/versions/{v["id"]}/pdf')


def test_proforma_versions_pdf_historique_reprise_tarifs_et_aucun_stock(raw_client,account,tmp_path):
    c,a=raw_client,account;prod,pack,pid,_=setup(c,a)
    before=stocks(c,a);journal=c.get(stock_root(a)+'/mouvements').json()['total']
    v=add(c,a,new(c,a),prod,pack,3);v=action(c,a,v,'emettre')
    assert v['etat']=='EMISE' and v['valide_jusqu_au']==str(date.today()+timedelta(days=30))
    data=pdf(c,a,v);assert data.status_code==200 and data.content.startswith(b'%PDF')
    (tmp_path/'proforma.pdf').write_bytes(data.content)
    assert stocks(c,a)==before and c.get(stock_root(a)+'/mouvements').json()['total']==journal
    for sql in ("UPDATE proforma_versions SET destinataire='{}'","DELETE FROM proforma_versions","UPDATE proforma_lignes SET quantite=999","DELETE FROM proforma_lignes","DELETE FROM proforma_evenements"):
        gen=db(c);s=next(gen)
        try:
            with pytest.raises(DBAPIError):s.execute(text(sql));s.commit()
            s.rollback()
        finally:gen.close()
    catalogue_post(c,a,'/tarification/produits',{'site_id':str(a['site']),'produit_id':prod,'conditionnement_id':pack,'montant_ht':'125','devise':'XAF','debut':str(date.today())})
    assert pdf(c,a,v).content==data.content
    v2=action(c,a,v,'nouvelle-version');assert v2['numero']==2 and v2['reference']==v['reference'] and v2['totaux']['ttc']=='375'
    v2=action(c,a,v2,'emettre');assert pdf(c,a,v2).content!=data.content
    assert len(c.get(root(a)+f'/{v["proforma_id"]}').json()['versions'])==2
    sale=action(c,a,v,'reprendre',poste_id=pid);assert sale['totaux']['ttc']=='375' and stocks(c,a)[0]['reserve']==3
    assert current(c,a,v)['totaux']['ttc']=='301' and pdf(c,a,v).content==data.content
    # Replay does not create a second preparation/reservation.
    body={'cle':str(uuid4()),'revision':v['revision'],'poste_id':pid}
    first=c.post(root(a)+f'/versions/{v["id"]}/reprendre',json=body);again=c.post(root(a)+f'/versions/{v["id"]}/reprendre',json=body)
    assert first.json()==again.json() and stocks(c,a)[0]['reserve']==6


def test_proforma_remises_autorisations_historiques_et_reprise_revalidation(raw_client,account):
    c,a=raw_client,account;prod,pack,pid,_=setup(c,a);config=cap(c,a)
    v=add(c,a,new(c,a),prod,pack)
    r=post(c,a,f'/versions/{v["id"]}/remises',{'revision':v['revision'],'type':'POURCENTAGE','valeur':'10','justification':'Offre commerciale'})
    post(c,a,f'/versions/{v["id"]}/emettre',{'revision':v['revision']},422)
    post(c,a,f'/versions/{v["id"]}/remises/{r["id"]}/decision',{'revision':v['revision'],'autoriser':True,'justification':'Responsable'},200)
    v=current(c,a,v);assert v['totaux']['ttc']=='271';v=action(c,a,v,'emettre');content=pdf(c,a,v).content
    cap(c,a,revision=config['revision'],max_pourcentage='5')
    assert current(c,a,v)['totaux']['ttc']=='271' and pdf(c,a,v).content==content
    sale=action(c,a,v,'reprendre',poste_id=pid)
    assert sale['totaux']['ttc']=='301' and sale['remises'][0]['statut']=='DEMANDEE' and sale['remises'][0]['autorisation'] is None
    act(c,a,sale,'annuler',justification='Fin test')


def test_proforma_brouillon_montants_permissions_csrf_et_contextes(raw_client,account):
    c,a=raw_client,account
    assert c.get(root(a)).status_code==401 and c.post(root(a),json={}).status_code==401
    prod,pack,pid,_=setup(c,a);v=new(c,a)
    assert pdf(c,a,v).status_code==409
    post(c,a,f'/versions/{v["id"]}/lignes',{'revision':1,'produit_id':str(uuid4()),'conditionnement_id':pack,'quantite':1},403)
    v=add(c,a,v,prod,pack,9999);assert stocks(c,a)[0]['reserve']==0  # Offer does not require availability.
    v=action(c,a,v,'emettre')
    post(c,a,f'/versions/{v["id"]}/reprendre',{'revision':v['revision'],'poste_id':pid},409)
    assert stocks(c,a)[0]['reserve']==0
    token=c.headers.pop('X-CSRF-Token');post(c,a,'',{},403);c.headers['X-CSRF-Token']=token
    assert c.get(root({'org':uuid4()})).status_code==403
    c.headers['X-Emplacement-ID']=str(a['denied']);assert pdf(c,a,v).status_code==403;c.headers['X-Emplacement-ID']=str(a['location'])
    gen=db(c);s=next(gen)
    try:s.execute(delete(RolePermissionModel).where(RolePermissionModel.permission_id.in_([permission_id(x) for x in ('proforma.gerer','proforma.emettre','proforma.reprendre','proforma.parametrer')])));s.commit()
    finally:gen.close()
    assert pdf(c,a,v).status_code==200
    for path in ('',f'/versions/{v["id"]}/lignes',f'/versions/{v["id"]}/emettre',f'/versions/{v["id"]}/reprendre','/parametrage'):post(c,a,path,{},403)


def test_preparation_multiligne_remises_correspondance_uuid_et_stock_inchange(raw_client,account):
    from test_remises import request,decide,current as sale_current
    from test_vente import post as sale_post
    c,a=raw_client,account;prod,pack,pid,_=setup(c,a);cap(c,a)
    sale=line(c,a,create(c,a,pid),prod,pack,1)
    removed=sale['lignes'][0]['id']
    sale=line(c,a,sale,prod,pack,2);sale=line(c,a,sale,prod,pack,3)
    sale=sale_post(c,a,f'/{sale["id"]}/lignes/{removed}/retirer',{'revision':sale['revision']},200)
    source_rows={row['quantite']:row['id'] for row in sale['lignes']}
    # Same product/pack appears twice: only the internal line identity distinguishes discounts.
    for quantity,kind,value in [(2,'POURCENTAGE','10'),(3,'MONTANT_XAF','5')]:
        sale=sale_current(c,a,sale)
        r=request(c,a,sale,ligne_id=source_rows[quantity],type=kind,valeur=value)
        decide(c,a,sale,r)
    sale=sale_current(c,a,sale);r=request(c,a,sale,valeur='5');decide(c,a,sale,r)
    sale=sale_current(c,a,sale);before=stocks(c,a);journal=c.get(stock_root(a)+'/mouvements').json()['total']
    v=new(c,a,vente_id=sale['id'],revision_vente=sale['revision'])
    assert len(v['lignes'])==2 and len(v['remises'])==3
    target_rows={row['id']:row['quantite'] for row in v['lignes']}
    observed={(target_rows.get(r['ligne_id']),r['type'],str(r['valeur'])) for r in v['remises']}
    from decimal import Decimal
    assert {(q,k,Decimal(value)) for q,k,value in observed}=={(2,'POURCENTAGE',Decimal(10)),(3,'MONTANT_XAF',Decimal(5)),(None,'POURCENTAGE',Decimal(5))}
    assert all(r['statut']=='DEMANDEE' and r['autorisation'] is None for r in v['remises'])
    assert not set(target_rows).intersection(source_rows.values())
    post(c,a,f'/versions/{v["id"]}/emettre',{'revision':v['revision']},422)
    other=add(c,a,new(c,a),prod,pack,1)
    post(c,a,f'/versions/{v["id"]}/remises',{'revision':v['revision'],'ligne_id':other['lignes'][0]['id'],'type':'MONTANT_XAF','valeur':'1','justification':'Autre version interdite'},403)
    post(c,a,f'/versions/{v["id"]}/remises',{'revision':v['revision'],'ligne_id':source_rows[2],'type':'MONTANT_XAF','valeur':'1','justification':'Ligne vente interdite'},404)
    for r in sorted(v['remises'],key=lambda r:r['ligne_id'] is None):
        v=current(c,a,v)
        copied=next(x for x in v['remises'] if x['id']==r['id'])
        # An individual approval invalidates pending requests whose financial base changed.
        if copied['statut']=='INVALIDEE':
            copied=post(c,a,f'/versions/{v["id"]}/remises',{'revision':v['revision'],'ligne_id':r['ligne_id'],'type':r['type'],'valeur':r['valeur'],'justification':'Nouvelle demande sur base actualisée'})
        post(c,a,f'/versions/{v["id"]}/remises/{copied["id"]}/decision',{'revision':v['revision'],'autoriser':True,'justification':'Revalidation indépendante'},200)
    v=action(c,a,current(c,a,v),'emettre');content=pdf(c,a,v).content
    assert v['totaux']==sale['totaux']
    assert sale_current(c,a,sale)==sale and stocks(c,a)==before
    assert c.get(stock_root(a)+'/mouvements').json()['total']==journal
    assert pdf(c,a,v).content==content


def test_validite_recherche_pagination_preparation_source(raw_client,account):
    c,a=raw_client,account;prod,pack,pid,_=setup(c,a)
    post(c,a,'/parametrage',{'revision':0,'duree_jours':45},200)
    sale=line(c,a,create(c,a,pid),prod,pack);before=stocks(c,a)
    v=new(c,a,vente_id=sale['id'],revision_vente=sale['revision']);assert stocks(c,a)==before
    v=action(c,a,v,'emettre');assert v['valide_jusqu_au']==str(date.today()+timedelta(days=45))
    new(c,a);r=c.get(root(a),params={'q':'été','page_size':1}).json();assert r['total']==2 and len(r['items'])==1
    assert c.get(root(a),params={'q':v['reference']}).json()['total']==1
    assert c.get(root(a),params={'q':'%'}).json()['total']==0


def test_numerotation_et_versions_concurrentes_postgresql(raw_client,account):
    c,a=raw_client,account;prod,pack,pid,_=setup(c,a)
    gen=db(c);s=next(gen);engine=s.get_bind();gen.close()
    if engine.dialect.name!='postgresql':pytest.skip('Concurrence PostgreSQL')
    def worker(_):
        with Session(engine) as s:
            stock=StockService(s,a['org'],a['user'],lambda *args:None);service=ProformaService(stock,a['site'])
            return stock.operation(uuid4(),'PF:CREER',{},lambda:service.creer({'emplacement_id':a['location'],'destinataire':{'nom':'Concurrent'}}))
    with ThreadPoolExecutor(max_workers=4) as pool:rows=list(pool.map(worker,range(4)))
    assert len({x['reference'] for x in rows})==4
    v=add(c,a,rows[0],prod,pack);v=action(c,a,v,'emettre')
    def version_worker(_):
        with Session(engine) as s:
            stock=StockService(s,a['org'],a['user'],lambda *args:None);service=ProformaService(stock,a['site'])
            try:stock.operation(uuid4(),'PF:VERSION',{},lambda:service.nouvelle_version(service.obtenir(UUID(v['id']),'proforma.gerer'),{'revision':v['revision']}));return 'ok'
            except ConflitStock:return 'conflit'
    with ThreadPoolExecutor(max_workers=2) as pool:assert sorted(pool.map(version_worker,range(2)))==['conflit','ok']


def test_tarif_modifie_brouillon_et_invalidation_plafond_cible(raw_client,account):
    c,a=raw_client,account;prod,pack,pid,_=setup(c,a);config=cap(c,a);v=add(c,a,new(c,a),prod,pack)
    r=post(c,a,f'/versions/{v["id"]}/remises',{'revision':v['revision'],'type':'POURCENTAGE','valeur':'10','justification':'Offre'})
    post(c,a,f'/versions/{v["id"]}/remises/{r["id"]}/decision',{'revision':v['revision'],'autoriser':True,'justification':'Autoriser'},200)
    v=current(c,a,v);cap(c,a,revision=config['revision'],max_pourcentage='5');v=current(c,a,v)
    assert v['remises'][0]['statut']=='INVALIDEE' and v['totaux']['ttc']=='301'
    catalogue_post(c,a,'/tarification/produits',{'site_id':str(a['site']),'produit_id':prod,'conditionnement_id':pack,'montant_ht':'150','devise':'XAF','debut':str(date.today())})
    post(c,a,f'/versions/{v["id"]}/emettre',{'revision':v['revision']},409)
    v=add(c,a,v,prod,pack,3,ligne_id=v['lignes'][0]['id']);assert v['totaux']['ttc']=='450';assert action(c,a,v,'emettre')['etat']=='EMISE'


def test_reprise_multiligne_insuffisante_rollback_complet(raw_client,account):
    from neosys_pharma.infrastructure.vente_models import VenteModel
    c,a=raw_client,account;prod,pack,pid,_=setup(c,a);v=add(c,a,new(c,a),prod,pack,7);v=add(c,a,v,prod,pack,7);v=action(c,a,v,'emettre')
    before=stocks(c,a);journal=c.get(stock_root(a)+'/mouvements').json()['total']
    post(c,a,f'/versions/{v["id"]}/reprendre',{'revision':v['revision'],'poste_id':pid},409)
    assert stocks(c,a)==before and c.get(stock_root(a)+'/mouvements').json()['total']==journal
    gen=db(c);s=next(gen)
    try:assert s.scalar(select(func.count()).select_from(VenteModel))==0
    finally:gen.close()


def test_proforma_locale_et_historique_remise_immutables(raw_client,account):
    from test_remises import manager
    from test_authentification import PASSWORD
    c,a=raw_client,account;prod,pack,pid,_=setup(c,a);user,role=manager(c,a);cap(c,a,str(role));v=add(c,a,new(c,a),prod,pack)
    r=post(c,a,f'/versions/{v["id"]}/remises',{'revision':v['revision'],'type':'MONTANT_XAF','valeur':'25','justification':'Offre locale'})
    d=post(c,a,f'/versions/{v["id"]}/remises/{r["id"]}/locale',{'revision':v['revision'],'autoriser':True,'justification':'Responsable présent','identifiant':'responsable','password':PASSWORD},200)
    assert d['autorisation']['auteur_id']==str(user) and c.get('/api/auth/me').json()['utilisateur']['id_utilisateur']==str(a['user'])
    v=action(c,a,current(c,a,v),'emettre')
    gen=db(c);s=next(gen)
    try:
        for sql in ("UPDATE proforma_demandes_remise SET statut='REFUSEE'","DELETE FROM proforma_demandes_remise","INSERT INTO proforma_lignes SELECT * FROM proforma_lignes"):
            with pytest.raises(DBAPIError):s.execute(text(sql));s.commit()
            s.rollback()
    finally:gen.close()
    assert current(c,a,v)['totaux']['ttc']=='276'


@pytest.mark.parametrize('rates',[(18,),(0,10,18)],ids=['taux-unique','taux-mixtes'])
def test_pdf_longues_designations_entetes_pagination_et_tva(tmp_path,rates):
    from io import BytesIO
    from pypdf import PdfReader
    from neosys_pharma.infrastructure.proforma_pdf import proforma_pdf
    row={'reference':'8812345','designation':'MÉDICAMENT PÉDIATRIQUE À LIBÉRATION PROLONGÉE - DÉSIGNATION LONGUE POUR CONTRÔLE DE MISE EN PAGE','conditionnement':'BOÎTE DE 20 COMPRIMÉS PELLICULÉS','quantite':3,'instantane_tarif':{'montant_ttc':'118','taux_tva':'18'},'montants_appliques':{'ttc_initial':'354','remise_ligne':'0','remise_globale':'0','ttc':'354','ht':'300','tva':'54'}}
    snapshot={'organisation':{'nom':'PHARMACIE DE RECETTE','raison_sociale':'PHARMACIE TEST','coordonnees':'Libreville - Gabon','informations_legales':'DOCUMENT DE TEST'},'site':{'code':'LBV','nom':'Site de test','adresse':'Libreville','telephone':'01000000','email':None},'destinataire':{'nom':'Élodie - destinataire de recette','adresse':'Libreville'},'reference':'PF-LBV-TEST-000001','numero':1,'emis_le':'2026-10-10T20:00:00+00:00','valide_jusqu_au':'2026-11-09','lignes':[row for _ in range(50)],'totaux':{'ttc_initial':'17700','remise_ligne':'0','remise_globale':'0','ttc':'17700','ht':'15000','tva':'2700'}}
    from copy import deepcopy
    from decimal import Decimal
    for index in range(50):
        r=deepcopy(row);rate=rates[index%len(rates)]
        r['instantane_tarif']={'montant_ttc':str(100+rate),'taux_tva':str(rate)}
        r['montants_appliques'].update(ttc_initial=str(300+3*rate),ttc=str(300+3*rate),ht='300',tva=str(3*rate))
        r['designation']=f"LIGNE {index+1:03d} - "+r['designation'];snapshot['lignes'][index]=r
    for key in snapshot['totaux']:
        snapshot['totaux'][key]=str(sum(Decimal(r['montants_appliques'][key]) for r in snapshot['lignes']))
    data=proforma_pdf(snapshot);reader=PdfReader(BytesIO(data));assert len(reader.pages)>2
    for index,page in enumerate(reader.pages):
        content=page.extract_text();assert 'PHARMACIE DE RECETTE' in content and f'Page {index+1}' in content
        if 'MÉDICAMENT' in content:assert 'Conditionnement' in content
    content='\n'.join(p.extract_text() for p in reader.pages);assert '09/11/2026' in content
    for rate in rates:
        rows=[r for r in snapshot['lignes'] if r['instantane_tarif']['taux_tva']==str(rate)]
        base=sum(int(r['montants_appliques']['ht']) for r in rows);tax=sum(int(r['montants_appliques']['tva']) for r in rows)
        money=lambda n:format(n,',').replace(',',' ')+' FCFA'
        assert f'TVA {rate} % : base HT {money(base)} ; taxe {money(tax)}' in content
    for index in range(50):assert f'LIGNE {index+1:03d}' in content
    # Scratch-only fixture for rendered PDF review, never customer financial data.
    (tmp_path/'proforma-longue.pdf').write_bytes(data)


def test_proforma_approbation_distante_effective(raw_client,account):
    from test_remises import manager
    from test_catalogue import grant
    from test_authentification import login
    from starlette.testclient import TestClient
    c,a=raw_client,account;prod,pack,pid,_=setup(c,a);user,role=manager(c,a)
    gen=db(c);s=next(gen)
    try:s.add(RolePermissionModel(role_id=role,permission_id=permission_id('proforma.consulter')));s.commit()
    finally:gen.close()
    cap(c,a,str(role));v=add(c,a,new(c,a),prod,pack)
    r=post(c,a,f'/versions/{v["id"]}/remises',{'revision':v['revision'],'type':'POURCENTAGE','valeur':'10','justification':'Demande distante'})
    with TestClient(c.app) as remote:
        login(remote,{**a,'user':user},identifiant='responsable')
        post(remote,a,f'/versions/{v["id"]}/remises/{r["id"]}/decision',{'revision':v['revision'],'autoriser':True,'justification':'Responsable distant'},200)
        post(remote,a,f'/versions/{v["id"]}/lignes',{},403)
    assert current(c,a,v)['totaux']['ttc']=='271' and stocks(c,a)[0]['reserve']==0
