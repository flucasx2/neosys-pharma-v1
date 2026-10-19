"""Numéro et code-barres : espace de noms unique et document historique."""
from uuid import uuid4,UUID
from io import BytesIO
from hashlib import sha256
import pytest
from sqlalchemy import select,func,text
from sqlalchemy.exc import DBAPIError
from pypdf import PdfReader
from test_stock import raw_client,account,db
from test_caisse import ready,post,root
from test_p4p5_groupe_organismes import cible_isolee
from neosys_pharma.infrastructure.caisse_models import IdentifiantCarteFideliteModel,CarteFideliteModel,DocumentCarteFideliteModel,EvenementCaisseModel
pytest_plugins=('test_vente',)

def test_numero_barcode_independants_doublons_scan_et_compte(raw_client,account):
    c,a=raw_client,account;ready(c,a)
    account_=post(c,a,'/fidelite',{'nom':'Titulaire fictif'});revision=account_['revision']
    payload={'revision':revision,'type':'PHYSIQUE','code':'0000123','code_barres':'SCAN-000987'};key=uuid4()
    row=post(c,a,f'/fidelite/{account_["id"]}/cartes',payload,key=key)
    assert post(c,a,f'/fidelite/{account_["id"]}/cartes',payload,key=key)==row
    card=row['cartes'][0];assert card['code']=='0000123' and card['code_barres']=='SCAN-000987'
    for query in ('0000123','SCAN-000987'):
        found=c.get(root(a)+'/fidelite',params={'q':query}).json();assert [r['id'] for r in found['items']]==[account_['id']]
    for code,barcode in [('SCAN-000987',None),('ANOTHER','0000123'),('THIRD','SCAN-000987')]:
        post(c,a,f'/fidelite/{account_["id"]}/cartes',{'revision':row['revision'],'type':'PHYSIQUE','code':code,'code_barres':barcode},409)
    post(c,a,f'/fidelite/{account_["id"]}/cartes',{'revision':row['revision'],'type':'VIRTUELLE','code_barres':'INTERDIT'},422)
    # Opposition préserve le registre : l'identifiant ne devient pas réutilisable.
    post(c,a,f'/cartes/{card["id"]}/opposer',{'revision':row['revision'],'justification':'Carte égarée fictive'},200)
    assert not c.get(root(a)+'/fidelite',params={'q':card['code_barres']}).json()['items']
    current=c.get(root(a)+f'/fidelite/{account_["id"]}').json()
    post(c,a,f'/fidelite/{account_["id"]}/cartes',{'revision':current['revision'],'type':'PHYSIQUE','code':'SCAN-000987'},409)


def test_association_avant_impression_reimpression_et_immutabilite(raw_client,account):
    c,a=raw_client,account;ready(c,a)
    acc=post(c,a,'/fidelite',{'nom':'Titulaire historique fictif'})
    acc=post(c,a,f'/fidelite/{acc["id"]}/cartes',{'revision':acc['revision'],'type':'PHYSIQUE','code':'VISIBLE-001'})
    card=acc['cartes'][0];route=f'/fidelite/cartes/{card["id"]}'
    acc=post(c,a,route+'/code-barres',{'revision':acc['revision'],'code_barres':'0000001234567'},200)
    post(c,a,route+'/code-barres',{'revision':acc['revision'],'code_barres':'REMPLACEMENT'},409)
    key=uuid4();document=post(c,a,route+'/impressions',{},200,key)
    assert post(c,a,route+'/impressions',{},200,key)==document
    again=post(c,a,route+'/impressions',{},200)
    assert again['id']==document['id']
    response=c.get(root(a)+route+'/pdf');assert response.status_code==200
    assert sha256(response.content).hexdigest()==document['pdf_sha256']
    extracted=''.join(p.extract_text() for p in PdfReader(BytesIO(response.content)).pages)
    assert 'VISIBLE-001' in extracted and '0000001234567' in extracted and 'TITULAIRE HISTORIQUE' in extracted
    assert c.get(root(a)+route+'/pdf').content==response.content
    gen=db(c);s=next(gen)
    try:
        assert s.scalar(select(func.count()).select_from(DocumentCarteFideliteModel))==1
        assert s.scalar(select(func.count()).select_from(EvenementCaisseModel).where(EvenementCaisseModel.type=='CARTE_DOCUMENT_DEMANDE'))==2
        for statement in ('UPDATE fidelite_cartes SET code=\'AUTRE\'', "UPDATE fidelite_cartes SET code_barres='CHANGE'",'DELETE FROM fidelite_cartes_identifiants','DELETE FROM fidelite_cartes_documents'):
            with pytest.raises(DBAPIError):s.execute(text(statement));s.commit()
            s.rollback()
    finally:gen.close()
    assert c.get(root(a)+route+'/pdf',headers={'X-Site-ID':str(a['other'])}).status_code==403


def test_premier_document_bloque_association_tardive_et_alias_forge(raw_client,account):
    c,a=raw_client,account;ready(c,a)
    acc=post(c,a,'/fidelite',{'nom':'Fictif'})
    acc=post(c,a,f'/fidelite/{acc["id"]}/cartes',{'revision':acc['revision'],'type':'PHYSIQUE','code':'LEGACY-001'})
    card=acc['cartes'][0];post(c,a,f'/fidelite/cartes/{card["id"]}/impressions',{},200)
    post(c,a,f'/fidelite/cartes/{card["id"]}/code-barres',{'revision':acc['revision'],'code_barres':'TROP-TARD'},409)
    gen=db(c);s=next(gen)
    try:
        s.add(IdentifiantCarteFideliteModel(organisation_id=a['org'],carte_id=UUID(card['id']),valeur='ALIAS-FORGE'))
        with pytest.raises(DBAPIError):s.commit()
        s.rollback()
    finally:gen.close()
