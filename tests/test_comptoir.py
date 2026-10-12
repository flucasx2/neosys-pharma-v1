"""P4.6 lectures HTTP : filtres avant pagination, sécurité et absence d’effets."""
from datetime import date, timedelta
from uuid import uuid4
from sqlalchemy import delete, select
from test_caisse import raw_client, account, ready, final, root as cash_root
from test_vente import create, line, act, root, db, stocks
from neosys_pharma.infrastructure.securite_models import RolePermissionModel
from neosys_pharma.domain.organisation.permissions_systeme import permission_id
from io import BytesIO
from pypdf import PdfReader

def test_ticket_preparateur_sans_effet_et_deux_exemplaires(raw_client,account):
    c,a=raw_client,account;v,se,*_=ready(c,a)
    path=cash_root(a)+f'/ventes/{v["id"]}/appel/pdf'
    before=c.get(root(a)+f'/{v["id"]}').json()
    assert before['numero_appel']=='0001' and before['ticket_appel_active']
    p=c.get(path);assert p.status_code==200
    text=''.join(x.extract_text() for x in PdfReader(BytesIO(p.content)).pages)
    assert 'CLIENT' in text and 'PANIER DE PRÉPARATION' in text
    for _ in range(2):assert c.get(path).status_code==200
    assert c.get(root(a)+f'/{v["id"]}').json()==before
    gen=db(c);s=next(gen)
    try:
        s.execute(delete(RolePermissionModel).where(RolePermissionModel.permission_id!=permission_id('vente.consulter')));s.commit()
    finally:gen.close()
    assert c.get(path).status_code==200
    assert c.get(cash_root(a)+'/contexte').status_code==403

def test_recherche_pagination_et_filtrage_litteral(raw_client, account):
    c,a=raw_client,account;v,se,prod,pack,pid,cid=ready(c,a)
    b=line(c,a,create(c,a,pid),prod,pack,1)
    for term in (v['id'],v['id'][:8],v['lignes'][0]['designation'].lower()):
        r=c.get(root(a),params={'q':term,'page_size':1});assert r.status_code==200,r.text
        assert r.json()['total']==(2 if term==v['lignes'][0]['designation'].lower() else 1)
        assert len(r.json()['items'])==1
    assert c.get(root(a),params={'q':'%'}).json()['total']==0
    assert c.get(root(a),params={'etat':'PREPARATION'}).json()['items'][0]['id']==b['id']
    assert c.get(root(a),params={'etat':'FAUX'}).status_code==422
    assert c.get(root(a),params={'debut':'2026-02-02','fin':'2026-01-01'}).status_code==422
    assert c.get(root(a),params={'debut':str(date.today()),'fin':str(date.today())}).json()['total']==2
    assert c.get(root(a),params={'fin':str(date.today()-timedelta(days=1))}).json()['total']==0
    assert c.get(root(a),params={'page_size':101}).status_code==422
    assert c.get(cash_root(a)+'/attente',params={'q':'0001','caisse_id':cid}).json()['items'][0]['id']==v['id']
    assert c.get(cash_root(a)+'/attente',params={'q':b['id']}).json()['total']==0
    paid=final(c,a,v,se)
    for term in ('0001',paid['id'],v['id'],v['lignes'][0]['designation']):
        r=c.get(cash_root(a)+'/recus',params={'q':term,'caisse_id':cid});assert r.status_code==200,r.text
        assert r.json()['total']==1
    assert c.get(cash_root(a)+'/recus',params={'etat':'TRANSMISE'}).json()['total']==0

def test_recherches_refus_contextes_et_consultation_seule(raw_client, account):
    c,a=raw_client,account
    for path in (root(a),cash_root(a)+'/attente',cash_root(a)+'/recus'):
        assert c.get(path,params={'q':'0001'}).status_code==401
    v,se,prod,pack,pid,cid=ready(c,a)
    for path in (root(a),cash_root(a)+'/attente',cash_root(a)+'/recus'):
        for key in ('emplacement_id','caisse_id'):
            assert c.get(path,params={key:str(uuid4())}).status_code==403
        assert c.get(path.replace(str(a['org']),str(uuid4())),params={'q':v['id']}).status_code==403
    gen=db(c);s=next(gen)
    try:
        keep=[permission_id('vente.consulter'),permission_id('caisse.consulter')]
        s.execute(delete(RolePermissionModel).where(RolePermissionModel.permission_id.not_in(keep)));s.commit()
    finally:gen.close()
    for path in (root(a),cash_root(a)+'/attente',cash_root(a)+'/recus'):
        assert c.get(path,params={'q':'0001'}).status_code==200
    assert c.post(root(a),json={}).status_code==403
    c.headers['X-Site-ID']=str(a['other'])
    assert c.get(root(a),params={'q':v['id']}).status_code==403
