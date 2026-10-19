"""Finitions indépendantes : identifiant virtuel, nom de caisse et rendu espèces."""
from uuid import uuid4,UUID
from decimal import Decimal
import pytest
from sqlalchemy import select,func
from test_stock import raw_client,account,db
from test_caisse import ready,root,post,final
from test_p4p5_groupe_organismes import cible_isolee
from neosys_pharma.infrastructure.caisse_models import EvenementCaisseModel,SessionCaisseModel,CarteFideliteModel
from neosys_pharma.infrastructure.organisation_models import CaisseModel

pytest_plugins=('test_vente',)


def test_carte_virtuelle_automatique_idempotente_et_compatibilite_physique(raw_client,account):
    c,a=raw_client,account;ready(c,a)
    customer=post(c,a,'/fidelite',{'nom':'Titulaire cartes fictives'})
    key=uuid4();data={'revision':customer['revision'],'type':'VIRTUELLE'}
    card=post(c,a,f"/fidelite/{customer['id']}/cartes",data,key=key)
    assert len(card['cartes'])==1
    generated=card['cartes'][0]['code'];assert generated.startswith('V-') and len(generated)==34
    assert post(c,a,f"/fidelite/{customer['id']}/cartes",data,key=key)==card
    assert c.post(root(a)+f"/fidelite/{customer['id']}/cartes",json={'cle':str(uuid4()),**data}).status_code==409
    # Le code reste unique entre cartes physiques et virtuelles, sans perdre les zéros.
    assert c.post(root(a)+f"/fidelite/{customer['id']}/cartes",json={'cle':str(uuid4()),'revision':card['revision'],'type':'PHYSIQUE','code':generated}).status_code==409
    assert c.post(root(a)+f"/fidelite/{customer['id']}/cartes",json={'cle':str(uuid4()),'revision':card['revision'],'type':'PHYSIQUE'}).status_code==422
    physical=post(c,a,f"/fidelite/{customer['id']}/cartes",{'revision':card['revision'],'type':'PHYSIQUE','code':'000012345'})
    assert any(row['code']=='000012345' for row in physical['cartes'])
    found=c.get(root(a)+'/fidelite',params={'q':'000012345'}).json()
    assert any(row['id']==customer['id'] for row in found['items'])


def test_renommer_caisse_permission_conflit_audit_et_historique(raw_client,account):
    c,a=raw_client,account;sale,session,*_=ready(c,a)
    receipt=final(c,a,sale,session)
    before=c.get(root(a)+f"/recus/{receipt['id']}/pdf").content
    gen=db(c);s=next(gen)
    try:
        till=s.get(CaisseModel,UUID(session['caisse_id']));old=till.nom;code=till.code
        session_revision=s.get(SessionCaisseModel,UUID(session['id'])).revision
    finally:gen.close()
    route=root(a)+f"/caisses/{session['caisse_id']}/libelle";payload={'cle':str(uuid4()),'nom_attendu':old,'nom':'Caisse comptoir fictive'}
    response=c.put(route,json=payload);assert response.status_code==200,response.text
    assert c.put(route,json=payload).json()==response.json()
    assert c.put(route,json=payload|{'cle':str(uuid4())}).status_code==409
    assert c.put(route,json=payload,headers={'X-Site-ID':str(a['other'])}).status_code==403
    assert c.put(route,json=payload,headers={'X-Emplacement-ID':str(a['denied'])}).status_code==403
    assert c.get(root(a)+f"/recus/{receipt['id']}/pdf").content==before
    gen=db(c);s=next(gen)
    try:
        row=s.get(CaisseModel,UUID(session['caisse_id']));assert row.nom=='Caisse comptoir fictive' and row.code==code
        assert s.get(SessionCaisseModel,UUID(session['id'])).revision==session_revision
        assert s.scalar(select(func.count()).select_from(EvenementCaisseModel).where(EvenementCaisseModel.type=='CAISSE_RENOMMEE'))==1
    finally:gen.close()


def test_rendu_reel_especes(raw_client,account):
    c,a=raw_client,account;sale,session,*_=ready(c,a)
    due=Decimal(sale['totaux']['ttc'])
    receipt=final(c,a,sale,session,reglements=[{'mode':'ESPECES','montant':str(due+200)}])
    payments=receipt['instantane']['reglements']
    assert len(payments)==1 and payments[0]['mode']=='ESPECES'
    assert Decimal(payments[0]['rendu'])==200
    assert Decimal(receipt['total_xaf'])==due
    assert c.get(root(a)+'/sessions').json()['items'][0]['especes_attendues']==str(Decimal(1000)+due)
