"""Les documents utilisent le même périmètre que l'écran, sans fausse valeur."""
import csv
import io
from datetime import date, timedelta
from decimal import Decimal
from uuid import uuid4
from zipfile import ZipFile
from xml.etree import ElementTree as ET
import pytest
from pypdf import PdfReader
from sqlalchemy import select,delete
from test_stock import raw_client,account,init,root,lot,entry,reserve,post,inventory,db,grant,login
from neosys_pharma.infrastructure.securite_models import RoleModel,RolePermissionModel,AffectationEmplacementModel
from neosys_pharma.domain.organisation.permissions_systeme import permission_id
from neosys_pharma.domain.etats import CoutHistorique,CoutsIndisponibles,valoriser,synthese

GENRES=('stocks','valorisation','mouvements','peremptions','inventaire','ecarts','comptabilite')

def report(c,a,kind='stocks',**params):
    response=c.get(root(a)+'/etats/'+kind,params=params);assert response.status_code==200,response.text;return response.json()

def restrict(c,a,permissions):
    gen=db(c);s=next(gen)
    try:
        role=s.scalar(select(RoleModel).where(RoleModel.organisation_id==a['org'],RoleModel.code=='CATALOGUE'))
        s.execute(delete(RolePermissionModel).where(RolePermissionModel.role_id==role.id_role,RolePermissionModel.permission_id.not_in([permission_id(p) for p in permissions])));s.commit()
    finally:gen.close()

@pytest.mark.parametrize('kind',GENRES)
@pytest.mark.parametrize('format',(None,'csv','xlsx','pdf'))
def test_etats_http_401_403_et_comptage_aveugle(raw_client,account,kind,format):
    c,a=raw_client,account;path=root(a)+'/etats/'+kind+('/export' if format else '');params={'format':format} if format else {}
    assert c.get(path,params=params).status_code==401
    pack=init(c,a);restrict(c,a,('stock.inventaire.compter',))
    assert c.get(path,params=params).status_code==403
    restrict(c,a,());assert c.get(path,params=params).status_code==403

@pytest.mark.parametrize('kind',GENRES)
@pytest.mark.parametrize('format',(None,'csv','xlsx','pdf'))
def test_isolation_emplacement_site_organisation_tous_formats(raw_client,account,kind,format):
    c,a=raw_client,account;pack=init(c,a);path=root(a)+'/etats/'+kind+('/export' if format else '');params={'format':format} if format else {}
    assert c.get(path,params={**params,'emplacement_id':str(uuid4())}).status_code==403
    for loc in (a['denied'],a['other_location']):assert c.get(path,params={**params,'emplacement_id':str(loc)}).status_code==403
    assert c.get(path,headers={'X-Site-ID':str(uuid4())},params=params).status_code==403
    assert c.get(path.replace(str(a['org']),str(uuid4())),params=params).status_code==403
    assert c.get(path,headers={'X-Emplacement-ID':str(uuid4())},params=params).status_code==403
    gen=db(c);s=next(gen)
    try:s.execute(delete(AffectationEmplacementModel));s.commit()
    finally:gen.close()
    assert c.get(path,params=params).status_code==403

def test_stocks_pagination_recherche_peremption_et_valorisation_inconnue(raw_client,account):
    c,a=raw_client,account;pack=init(c,a)
    today=date.today()
    for i in range(6):
        l=lot(c,a,pack,'LOT-é-'+str(i),str(today+timedelta(days=i-2)));entry(c,a,l['id'],i+1)
    reserve(c,a,pack,2)
    r=report(c,a,page=2,page_size=2);assert r['total']==6 and len(r['items'])==2
    assert r['synthese']['totaux_quantites']=={'physique':21,'reserve':2,'vendable':19}
    assert report(c,a,q='lot-É-3')['total']==1
    r=report(c,a,'valorisation');assert r['synthese']['total_valorisation'] is None and r['synthese']['lignes_non_valorisables']==6
    assert all(x['cout_unitaire'] is None and x['montant'] is None and x['devise'] is None for x in r['items'])
    r=report(c,a,'peremptions',reference=str(today),horizon=1);assert r['total']==4
    assert [x['etat_peremption'] for x in r['items']].count('PÉRIMÉ')==2
    assert c.get(root(a)+'/etats/mouvements',params={'debut':'2026-04-02','fin':'2026-04-01'}).status_code==422
    assert c.get(root(a)+'/etats/peremptions',params={'horizon':-1}).status_code==422
    assert c.get(root(a)+'/etats/inconnu').status_code==422
    assert report(c,a,'mouvements',debut=str(today),fin=str(today))['total']==8
    assert report(c,a,'mouvements',debut=str(today+timedelta(days=1)))['total']==0

def test_export_complet_formats_metadonnees_accents_nombres_et_formules(raw_client,account):
    c,a=raw_client,account;pack=init(c,a)
    for i in range(30):
        l=lot(c,a,pack,'=HYPERLINK("dangereux") '+str(i),str(date.today()+timedelta(days=1)));entry(c,a,l['id'],1)
    assert len(report(c,a,page_size=2)['items'])==2
    path=root(a)+'/etats/stocks/export'
    csv_response=c.get(path,params={'format':'csv'});assert csv_response.status_code==200
    rows=list(csv.DictReader(io.StringIO(csv_response.content.decode('utf-8-sig')),delimiter=';'))
    assert len(rows)==30 and rows[0]['lot'].startswith("'=") and rows[0]['physique']=='1'
    assert rows[0]['organisation_id']==str(a['org']) and csv_response.headers['X-Report-Rows']=='30'
    x=c.get(path,params={'format':'xlsx'});assert x.status_code==200
    with ZipFile(io.BytesIO(x.content)) as z:
        for name in z.namelist():ET.fromstring(z.read(name))
        data=z.read('xl/worksheets/sheet2.xml').decode();assert 'autoFilter' in data and 'state="frozen"' in data and 'SUBTOTAL(109' in data and 't="inlineStr"' in data and '=HYPERLINK' in data
        summary=z.read('xl/worksheets/sheet1.xml').decode();assert 'INDISPONIBLE' in summary
    pdf=c.get(path,params={'format':'pdf'});assert pdf.status_code==200
    doc=PdfReader(io.BytesIO(pdf.content));text='\n'.join(p.extract_text() for p in doc.pages)
    assert 'État des stocks' in text and 'Page 1 /' in text and str(a['org']) not in text
    assert doc.pages and pdf.headers['X-Report-Reference'] in text
    assert c.get(path,params={'format':'exe'}).status_code==422

def test_inventaire_pv_ecarts_mouvements_reconciliation_et_lecture_seule(raw_client,account):
    c,a=raw_client,account;pack=init(c,a);l=lot(c,a,pack);entry(c,a,l['id'],10);inv=inventory(c,a,pack);zone=inv['zones'][0];line=zone['lignes'][0]
    post(c,a,f'/zones/{zone["id"]}/participants',{'utilisateur_id':str(a['user'])})
    motif=post(c,a,'/motifs',{'code':'C','nom':'Casse'})
    entry(c,a,l['id'],3)
    post(c,a,f'/lignes-inventaire/{line["id"]}/comptages',{'quantite':12,'motif_id':motif['id'],'justification':'Une unité cassée'})
    entry(c,a,l['id'],5)
    before=report(c,a,'inventaire',inventaire_id=inv['id']);row=before['items'][0]
    assert row['theorique']==10 and row['theorique_au_comptage']==13 and row['ecart']==-1 and before['inventaire']['statut']=='OUVERT'
    assert c.get(root(a)+'/etats/inventaire',params={'inventaire_id':inv['id'],'q':'test'}).status_code==422
    post(c,a,f'/inventaires/{inv["id"]}/valider',status=200)
    after=report(c,a,'ecarts',inventaire_id=inv['id']);assert after['items'][0]['ecart']==-1 and after['inventaire']['statut']=='VALIDE'
    assert after['synthese']['total_valorisation'] is None
    candidates=report(c,a,'comptabilite');assert any(x['type']=='AJUSTEMENT_INVENTAIRE' for x in candidates['items'])
    assert all(x['montant'] is None and 'AUCUNE ÉCRITURE' in x['statut_comptable'] for x in candidates['items'])
    restrict(c,a,('stock.consulter',))
    for kind in ('inventaire','ecarts'):
        for fmt in (None,'pdf','csv','xlsx'):
            assert c.get(root(a)+'/etats/'+kind+('/export' if fmt else ''),params={'inventaire_id':inv['id'],**({'format':fmt} if fmt else {})}).status_code==403
    assert report(c,a)['items'][0]['physique']==17

def test_contrat_couts_provenance_zero_reel_et_totaux_incomplets():
    org,stock=uuid4(),uuid4()
    unknown=valoriser(CoutsIndisponibles(),org,stock,5);assert unknown['montant'] is None
    class CoutValide:
        def obtenir(self,*args):return CoutHistorique(Decimal('12.50'),'XAF','MÉTHODE VALIDÉE EN TEST','PIÈCE TEST')
    real=valoriser(CoutValide(),org,stock,-2);assert real['montant']=='-25.00'
    assert synthese([real])['total_valorisation']=='-25.00'
    assert synthese([real,unknown])['total_valorisation'] is None
    assert valoriser(CoutValide(),org,stock,0)['montant']=='0.00'
    assert synthese([])['total_valorisation'] is None
    with pytest.raises(ValueError):CoutHistorique(Decimal('-1'),'XAF','FIFO','Facture')
    with pytest.raises(ValueError):CoutHistorique(Decimal('NaN'),'XAF','FIFO','Facture')

def test_extraction_trop_grande_refuse_sans_document_partiel(raw_client,account,monkeypatch):
    from neosys_pharma.application import etats_service
    c,a=raw_client,account;pack=init(c,a)
    for i in range(3):entry(c,a,lot(c,a,pack,'LOT-'+str(i))['id'],1)
    monkeypatch.setattr(etats_service,'MAX_LIGNES',2)
    for suffix in ('','/export?format=csv','/export?format=xlsx','/export?format=pdf'):
        response=c.get(root(a)+'/etats/stocks'+suffix);assert response.status_code==422 and 'Aucun export partiel' in response.json()['detail']
    assert report(c,a,q='LOT-1')['total']==1

def test_peremption_absente_uniquement_si_suivi_requis(raw_client,account):
    c,a=raw_client,account;pack=init(c,a);entry(c,a,lot(c,a,pack)['id'],3)
    assert report(c,a,'peremptions')['total']==0
    assert report(c,a,'valorisation')['synthese']['total_valorisation'] is None
