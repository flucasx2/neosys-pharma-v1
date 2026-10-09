"""Invariants P2, HTTP directs, import volumineux et absence de stock implicite."""
from datetime import date
from decimal import Decimal
from uuid import UUID,uuid4
import pytest
from sqlalchemy import select,func
from test_p1_vertical import raw_client
from test_authentification import account,db,login
from test_catalogue import grant,root,post,basic
from neosys_pharma.domain.tarification import TarifReference,ParametrageTarifSite,RegimeTVA


def setup(c,a):
    grant(c,a);login(c,a);cat,data,prod=basic(c,a)
    return cat,data,prod,prod['conditionnements'][0]['id_conditionnement']


def test_classifications_compositions_substitutions_unicode_et_regles(raw_client,account):
    c,a=raw_client,account;cat,data,prod,pid=setup(c,a)
    ids={}
    for typ,key in [('natures','id_nature'),('modes','id_mode'),('principes','id_principe'),('classes','id_classe'),('groupes','id_groupe')]:
        row=post(c,a,'/'+typ,{'code':' été-ß ', 'nom':' éphémère çà œuf '})
        assert row['code']=='ÉTÉ-SS' and row['nom']=='ÉPHÉMÈRE ÇÀ ŒUF';ids[typ]=row[key]
        assert post(c,a,'/'+typ,{'code':'ÉTÉ-SS','nom':'Doublon'},409)
        assert c.put(root(a)+f'/{typ}/{row[key]}',json={'code':row['code'],'nom':'référentiel modifié'}).status_code==200
    second=post(c,a,'/principes',{'code':'P2','nom':'Deuxième principe'})
    for ident,dose in [(ids['principes'],'500 mg'),(second['id_principe'],None)]:
        row=post(c,a,f'/produits/{prod["id_produit"]}/compositions',{'principe_id':ident,'dosage':dose})
        assert row['dosage']==('500 mg' if dose else None)
    classification=post(c,a,f'/produits/{prod["id_produit"]}/classifications',{'classe_id':ids['classes']})
    substitution=post(c,a,f'/produits/{prod["id_produit"]}/substitutions',{'groupe_id':ids['groupes']})
    assert c.put(root(a)+f'/substitutions/{substitution["id_substitution"]}',json={'groupe_id':ids['groupes'],'actif':False}).status_code==200
    assert c.put(root(a)+f'/categories/{cat["id_categorie"]}',json={'code':'med','nom':'médicaments','gestion_lot':True,'gestion_peremption':True,'fefo':True}).status_code==200
    data.pop('premier_conditionnement');data.update(nature_id=ids['natures'],mode_delivrance_id=ids['modes'],fefo=False,description='été ß œuf')
    r=c.put(root(a)+f'/produits/{prod["id_produit"]}',json=data)
    assert r.status_code==200,r.text
    result=r.json();assert result['description']=='été ß œuf'
    assert len(result['compositions'])==2 and len(result['classifications'])==1 and len(result['substitutions'])==1
    assert result['regles_effectives']=={'gestion_lot':True,'gestion_peremption':True,'fefo':False,'promotion_autorisee':False}
    assert c.post(root(a)+f'/produits/{prod["id_produit"]}/classifications',json={'classe_id':ids['classes']}).status_code==409
    assert c.post(root(a)+f'/produits/{prod["id_produit"]}/compositions',json={'principe_id':str(uuid4())}).status_code==404
    assert c.put(root(a)+f'/produits/{prod["id_produit"]}',json={**data,'regime_tva_code':'INCONNU'}).status_code==404


@pytest.mark.parametrize('value',['-1','NaN','Infinity','0.00001','1000000000000'])
def test_montants_invalides(value):
    with pytest.raises(ValueError):TarifReference(organisation_id=uuid4(),conditionnement_id=uuid4(),montant_ht=value,devise='XAF',debut=date(2026,1,1))


def test_tarifs_priorite_site_conditionnement_historique_tva_et_dates(raw_client,account):
    c,a=raw_client,account;cat,data,prod,pid=setup(c,a)
    other=post(c,a,f'/produits/{prod["id_produit"]}/conditionnements',{'code':'B60','libelle':'Boîte 60'})
    first=post(c,a,'/tarification/references',{'conditionnement_id':pid,'montant_ht':'1000','devise':'XAF','debut':'2026-01-01','fin':'2026-06-30'})
    post(c,a,'/tarification/references',{'conditionnement_id':pid,'montant_ht':'1200','devise':'XAF','debut':'2026-07-01'})
    assert c.post(root(a)+'/tarification/references',json={'conditionnement_id':pid,'montant_ht':999,'devise':'XAF','debut':'2026-06-30'}).status_code==422
    def price(day='2026-03-01',pack=pid,**params):
        r=c.get(root(a)+f'/prix/{pack}',params={'jour':day,**params});assert r.status_code==200,r.text;return r.json()
    assert price()['origine']=='REFERENCE' and Decimal(price()['montant_ht'])==1000
    assert Decimal(price('2026-07-01')['montant_ht'])==1200
    assert not price('2025-12-31')['disponible'] and not price(pack=other['id_conditionnement'])['disponible']
    common={'site_id':str(a['site']),'devise':'XAF','debut':'2026-02-01','fin':'2026-05-31'}
    general=post(c,a,'/tarification/sites',{**common,'coefficient':'1.1'})
    assert price()['origine']=='SITE' and Decimal(price()['montant_ht'])==1100
    category=post(c,a,'/tarification/categories',{**common,'categorie_id':cat['id_categorie'],'coefficient':'1.2'})
    assert price()['origine']=='CATEGORIE_SITE' and Decimal(price()['montant_ht'])==1200
    product=post(c,a,'/tarification/produits',{**common,'produit_id':prod['id_produit'],'conditionnement_id':pid,'montant_ht':'1300'})
    assert price()['origine']=='PRODUIT_SITE' and Decimal(price()['montant_ht'])==1300
    assert not price(pack=other['id_conditionnement'])['disponible'] # priority coefficient requires its own reference
    post(c,a,'/tarification/tva',{'code':'tva','nom':'Régime daté','taux':'18','debut':'2026-01-01','fin':'2026-06-30'})
    post(c,a,'/tarification/tva',{'code':'tva','nom':'Régime daté','taux':'20','debut':'2026-07-01'})
    data.pop('premier_conditionnement');data['regime_tva_code']='tva'
    assert c.put(root(a)+f'/produits/{prod["id_produit"]}',json=data).status_code==200
    assert Decimal(price()['montant_ttc'])==1534 and Decimal(price()['taux_tva'])==18
    assert price()['debut']=='2026-02-01' and price()['fin']=='2026-05-31'
    assert Decimal(price('2026-07-01')['montant_ttc'])==1440 and Decimal(price('2026-07-01')['taux_tva'])==20
    # Direct calls cannot view or mutate a site without an effective assignment.
    assert c.get(root(a)+f'/prix/{pid}',params={'site_id':str(a['other'])}).status_code==403
    assert c.get(root(a)+'/tarification/sites',params={'site_id':str(a['other'])}).status_code==403
    assert c.post(root(a)+'/tarification/sites',json={**common,'site_id':str(a['other']),'montant_ht':'5'}).status_code==403
    # History is immutable apart from an explicit one-time end-date closure.
    current=c.get(root(a)+'/tarification/references').json()['items'][0]
    assert c.put(root(a)+f'/tarification/references/{current["id_tarif"]}/cloture',json={'fin':'2026-12-31'}).status_code==200
    assert c.put(root(a)+f'/tarification/references/{current["id_tarif"]}/cloture',json={'fin':'2026-08-31'}).status_code==422
    post(c,a,'/tarification/references',{'conditionnement_id':pid,'montant_ht':1400,'devise':'XAF','debut':'2027-01-01'})
    history=c.get(root(a)+'/tarification/references',params={'page_size':1,'page':3}).json()
    assert history['total']==3 and history['items'][0]['id_tarif']==first['id_tarif']
    assert c.post(root(a)+'/tarification/sites',json={**common,'coefficient':1,'montant_ht':2}).status_code==422
    assert c.post(root(a)+'/tarification/references',json={'conditionnement_id':other['id_conditionnement'],'coefficient':2,'devise':'XAF','debut':'2026-01-01'}).status_code==422


def preview(c,a,content,**kwargs):
    return post(c,a,'/imports/previsualisation',{'contenu':content,'nom_fichier':'PharmaGabon.csv','source':'PharmaGabon',**kwargs})


def test_import_mapping_erreurs_reprise_reimport_et_validation_expresse(raw_client,account):
    c,a=raw_client,account;cat,data,prod,pid=setup(c,a)
    post(c,a,f'/conditionnements/{pid}/references',{'type_reference':'CIP7','valeur':'0012345'})
    original=post(c,a,'/tarification/references',{'conditionnement_id':pid,'montant_ht':'99','devise':'XAF','debut':'2026-01-01','fin':'2026-09-30'})
    content='Code;Nom;DCI;Quantite;PA;PV\n0012345;désignation source;PARACETAMOL;5000;10,5;123\n0012346;inconnu à créer;;999;12;24\nBAD;invalide;;5;1;2\n0012347;;DCI;0;1;2\n0012346;dupliqué;;;1;2\n'
    mapping={'CIP':'Code','Description':'Nom','DCI':'DCI','Quantite':'Quantite','PrixAchat':'PA','PrixVente':'PV'}
    job=preview(c,a,content,mapping=mapping)
    report=c.get(root(a)+f'/imports/{job["id_import"]}',params={'page_size':2}).json()
    assert report['total']==5 and len(report['items'])==2 and report['compteurs']=={'EXISTANT':1,'INCONNU':1,'INVALIDE':3}
    def lot(id,**attrs):
        return c.post(root(a)+f'/imports/{id}/lots',json={'mode':'catalogue','devise':'XAF','taille':100,**attrs})
    assert lot(job['id_import']).status_code==200 # missing unknown-product defaults remain reported, never invented
    assert c.get(root(a)+f'/imports/{job["id_import"]}').json()['items'][1]['erreurs']
    assert lot(job['id_import'],categorie_id=cat['id_categorie'],conditionnement_libelle='Unité commerciale fournie').status_code==200
    assert c.get(root(a)+'/produits').json()['total']==2
    assert c.get(root(a)+f'/produits/{prod["id_produit"]}').json()['nom']=='PRODUIT TEST'
    quote=c.get(root(a)+'/conseils',params={'conditionnement_id':pid}).json()['items'][0]
    assert quote['prix_vente_conseille']=='123.0000' and quote['prix_achat_indicatif']=='10.5000' and quote['dci_brute']=='PARACETAMOL'
    assert c.get(root(a)+'/tarification/references').json()['total']==1
    assert c.get(root(a)+f'/prix/{pid}',params={'jour':'2026-09-01'}).json()['montant_ht']=='99.00'
    repeated=preview(c,a,content,mapping=mapping)
    assert lot(repeated['id_import'],categorie_id=cat['id_categorie'],conditionnement_libelle='Unité commerciale fournie').status_code==200
    assert c.get(root(a)+'/conseils').json()['total']==2 and c.get(root(a)+'/produits').json()['total']==2
    approve={'ids':[quote['id_conseil']],'debut':'2026-10-01','niveau':'reference','base_prix':'HT','confirmer':False}
    assert c.post(root(a)+'/conseils/appliquer',json=approve).status_code==422
    approve['confirmer']=True
    assert c.post(root(a)+'/conseils/appliquer',json=approve).status_code==200
    assert c.post(root(a)+'/conseils/appliquer',json=approve).status_code==200
    assert c.get(root(a)+'/tarification/references').json()['total']==2
    assert c.get(root(a)+f'/prix/{pid}',params={'jour':'2026-10-01'}).json()['montant_ht']=='123.00'
    assert lot(repeated['id_import'],categorie_id=cat['id_categorie'],conditionnement_libelle='Unité commerciale fournie').status_code==200
    assert c.get(root(a)+'/tarification/references').json()['total']==2
    assert 'Quantite' not in c.get(root(a)+f'/produits/{prod["id_produit"]}').json()
    export=c.get(root(a)+f'/imports/{job["id_import"]}/rapport.csv')
    assert export.status_code==200 and 'INVALIDE' in export.text and 'PrixVenteConseille' in export.text
    assert c.get(root(a)+f'/imports/{uuid4()}').status_code==404
    assert c.post(root(a)+'/conseils/appliquer',json={**approve,'ids':[str(uuid4())]}).status_code==404


def test_import_conseils_seuls_inconnus_ignores_pas_composition_ni_tarif(raw_client,account):
    c,a=raw_client,account;cat,data,prod,pid=setup(c,a)
    post(c,a,f'/conditionnements/{pid}/references',{'type_reference':'CIP7','valeur':'0012345'})
    content='CIP;Description;DCI;PrixAchat;PrixVente;Quantite\n0012345;Nouveau nom;DCI BRUTE INCONNUE;15;20;900\n0012346;Inconnu;;12;24;0\n'
    job=preview(c,a,content)
    r=c.post(root(a)+f'/imports/{job["id_import"]}/lots',json={'mode':'conseils','devise':'XAF'})
    assert r.status_code==200,r.text
    assert c.get(root(a)+'/produits').json()['total']==1
    prod=c.get(root(a)+f'/produits/{prod["id_produit"]}').json();assert not prod['compositions'] and prod['nom']=='PRODUIT TEST'
    assert c.get(root(a)+'/tarification/references').json()['total']==0
    assert c.get(root(a)+f'/imports/{job["id_import"]}').json()['compteurs']=={'CONSEIL':1,'IGNORE':1}


def test_import_3500_references_batches_pagination_reimport_sans_doublon(raw_client,account):
    c,a=raw_client,account;cat,data,prod,pid=setup(c,a)
    content='CIP;Quantite;Description;DCI;PrixAchat;PrixVente\n'+''.join(f'{i:07d};900;référence {i}; ;10;20\n' for i in range(3500))
    for repetition in range(2):
        job=preview(c,a,content)
        for offset in range(0,3500,200):
            r=c.post(root(a)+f'/imports/{job["id_import"]}/lots',json={'offset':offset,'taille':200,'mode':'catalogue','categorie_id':cat['id_categorie'],'conditionnement_libelle':'UNITÉ FOURNIE','devise':'XAF'})
            assert r.status_code==200,r.text
        assert c.get(root(a)+f'/imports/{job["id_import"]}',params={'page':70}).json()['compteurs']=={'IMPORTE':3500}
        result=c.get(root(a)+'/produits',params={'page':2,'page_size':100}).json()
        assert result['total']==3501 and len(result['items'])==100
    assert c.get(root(a)+'/conseils').json()['total']==3500
    assert c.get(root(a)+'/tarification/references').json()['total']==0


@pytest.mark.parametrize('body',[{'mapping':{'CIP':'CIP','Description':'CIP'}},{'mapping':{'CIP':'Absent','Description':'Description'}},{'contenu':'CIP;Description\n'},{'contenu':'CIP;CIP;Description\n1;2;X\n'}])
def test_previsualisation_invalide(raw_client,account,body):
    c,a=raw_client,account;grant(c,a);login(c,a)
    data={'contenu':'CIP;Description\n0012345;TEST\n','nom_fichier':'test.csv','source':'TEST',**body}
    assert c.post(root(a)+'/imports/previsualisation',json=data).status_code==422


def test_lecture_seule_refuse_toutes_mutations_p2_http_direct(raw_client,account):
    c,a=raw_client,account;grant(c,a,('catalogue.consulter',));login(c,a)
    paths=c.get('/openapi.json').json()['paths']
    for template,methods in paths.items():
        if not template.startswith('/api/catalogue/'):continue
        path=template.replace('{organisation_id}',str(a['org'])).replace('{identifiant}',str(uuid4())).replace('{type_tarif}','sites')
        for method in methods:
            if method=='get':continue
            assert c.request(method,path,json={}).status_code==403,(method,path)


def test_tarif_tva_periodes_et_coefficient_sans_reference():
    with pytest.raises(ValueError):RegimeTVA(organisation_id=uuid4(),code='TVA',nom='TVA',taux=101,debut=date.today())
    with pytest.raises(ValueError):TarifReference(organisation_id=uuid4(),conditionnement_id=uuid4(),montant_ht=1,devise='XAF',debut=date(2026,2,1),fin=date(2026,1,1))
    with pytest.raises(ValueError):ParametrageTarifSite(organisation_id=uuid4(),site_id=uuid4(),devise='XAF',debut=date.today())


def test_isolation_classifications_conseils_imports_et_fks_sql(raw_client,account):
    from neosys_pharma.infrastructure.organisation_models import OrganisationModel,SiteModel
    from neosys_pharma.infrastructure.catalogue_models import NatureMedicamentModel,ProduitModel
    from neosys_pharma.infrastructure.tarification_models import ParametrageTarifSiteModel
    from sqlalchemy.exc import IntegrityError
    c,a=raw_client,account;cat,data,prod,pid=setup(c,a)
    gen=db(c);session=next(gen)
    try:
        org=uuid4();nature=uuid4();site=uuid4()
        session.add(OrganisationModel(id_organisation=org,nom_commercial='AUTRE',raison_sociale='AUTRE',actif=True));session.flush()
        session.add_all([NatureMedicamentModel(id_nature=nature,organisation_id=org,code='N',nom='AUTRE',actif=True),SiteModel(id_site=site,organisation_id=org,code='X',nom='AUTRE',actif=True)]);session.commit()
        for row in [ProduitModel(id_produit=uuid4(),organisation_id=a['org'],categorie_id=UUID(cat['id_categorie']),nature_id=nature,nom='INTERDIT',actif=True),ParametrageTarifSiteModel(id_tarif=uuid4(),organisation_id=a['org'],site_id=site,devise='XAF',montant_ht=1,debut=date(2026,1,1))]:
            session.add(row)
            with pytest.raises(IntegrityError):session.flush()
            session.rollback()
    finally:gen.close()
    data.pop('premier_conditionnement');assert c.put(root(a)+f'/produits/{prod["id_produit"]}',json={**data,'nature_id':str(nature)}).status_code==404
    job=preview(c,a,'CIP;Description\n0012345;TEST\n')
    assert c.get(root({**a,'org':org})+f'/imports/{job["id_import"]}').status_code==403
    assert c.get(root(a)+f'/imports/{uuid4()}/rapport.csv').status_code==404
    assert c.get(root({**a,'org':org})+'/conseils').status_code==403


def test_validation_conseils_transactionnelle_et_ttc_date(raw_client,account):
    c,a=raw_client,account;cat,data,prod,pid=setup(c,a)
    post(c,a,f'/conditionnements/{pid}/references',{'type_reference':'CIP7','valeur':'0012345'})
    post(c,a,'/tarification/tva',{'code':'TVA','nom':'TVA','taux':18,'debut':'2026-01-01','fin':'2026-12-31'})
    data.pop('premier_conditionnement');data['regime_tva_code']='TVA';assert c.put(root(a)+f'/produits/{prod["id_produit"]}',json=data).status_code==200
    job=preview(c,a,'CIP;Description;PrixVente\n0012345;PRODUIT;1180\n')
    assert c.post(root(a)+f'/imports/{job["id_import"]}/lots',json={'mode':'conseils','devise':'XAF'}).status_code==200
    quote=c.get(root(a)+'/conseils').json()['items'][0]
    body={'ids':[quote['id_conseil']],'debut':'2026-01-01','fin':'2026-12-31','niveau':'reference','base_prix':'TTC','confirmer':True}
    assert c.post(root(a)+'/conseils/appliquer',json={**body,'ids':[quote['id_conseil'],str(uuid4())]}).status_code==404
    assert c.get(root(a)+'/tarification/references').json()['total']==0
    assert c.post(root(a)+'/conseils/appliquer',json={**body,'fin':None}).status_code==422
    assert c.post(root(a)+'/conseils/appliquer',json=body).status_code==200
    price=c.get(root(a)+f'/prix/{pid}',params={'jour':'2026-06-01'}).json();assert price['montant_ht']=='1000.00' and price['montant_ttc']=='1180.00'


def test_migration_sur_catalogue_existant_preserve_textes_et_references(tmp_path,monkeypatch):
    from alembic import command
    from alembic.config import Config
    from sqlalchemy import create_engine,text
    from neosys_pharma.infrastructure.config import get_settings
    url=f'sqlite:///{tmp_path / "existing-p2.db"}'
    monkeypatch.setenv('DATABASE_URL',url);get_settings.cache_clear();config=Config('alembic.ini')
    try:
        command.upgrade(config,'20261007_05');engine=create_engine(url)
        with engine.begin() as cx:
            # Raw UUID strings are the SQLite UUID encoding.
            org=uuid4().hex;cat=uuid4().hex;prod=uuid4().hex;pack=uuid4().hex
            cx.execute(text('INSERT INTO organisations (id_organisation,nom_commercial,raison_sociale,actif) VALUES (:o,\'TEST\',\'TEST\',1)'),{'o':org})
            cx.execute(text('INSERT INTO catalogue_categories (id_categorie,organisation_id,code,nom,actif) VALUES (:c,:o,\'C\',\'été œuf\',1)'),{'c':cat,'o':org})
            cx.execute(text('INSERT INTO catalogue_produits (id_produit,organisation_id,categorie_id,nom,description,actif) VALUES (:p,:o,:c,\'éphémère\',\'Commentaire historique : 5 mg/mL.\',1)'),{'p':prod,'o':org,'c':cat})
            cx.execute(text('INSERT INTO catalogue_conditionnements (id_conditionnement,organisation_id,produit_id,code,libelle,actif) VALUES (:k,:o,:p,\'B\',\'boîte\',1)'),{'k':pack,'o':org,'p':prod})
            cx.execute(text('INSERT INTO catalogue_references (id_reference,organisation_id,conditionnement_id,type_reference,valeur,actif) VALUES (:r,:o,:k,\'HISTORIQUE\',\'00MixedCase\',1)'),{'r':uuid4().hex,'o':org,'k':pack})
        command.upgrade(config,'head');command.check(config)
        with engine.connect() as cx:
            assert cx.execute(text('SELECT nom FROM catalogue_produits')).scalar()=='éphémère'
            assert cx.execute(text('SELECT nom,gestion_lot FROM catalogue_categories')).first()==('été œuf',0)
            assert cx.execute(text('SELECT valeur FROM catalogue_references')).scalar()=='00MixedCase'
            assert cx.execute(text('SELECT description FROM catalogue_produits')).scalar()=='Commentaire historique : 5 mg/mL.'
        command.downgrade(config,'20261007_05');command.upgrade(config,'head');command.check(config)
        engine.dispose()
    finally:get_settings.cache_clear()


@pytest.mark.parametrize("type_tarif",["references","sites","categories","produits","tva"])
def test_postgresql_exclusion_periodes_meme_appel_sql_direct(raw_client,account,type_tarif):
    from neosys_pharma.infrastructure.tarification_models import TarifReferenceModel
    from sqlalchemy.exc import IntegrityError
    c,a=raw_client,account;cat,data,prod,pid=setup(c,a)
    gen=db(c);session=next(gen)
    try:
        if session.bind.dialect.name!='postgresql':pytest.skip('Contrainte native PostgreSQL')
        from neosys_pharma.application.tarification_service import TARIFS
        from neosys_pharma.infrastructure.catalogue_repository import MODELES
        model=MODELES[TARIFS[type_tarif]]
        attrs={'organisation_id':a['org']}
        if type_tarif=='tva':attrs.update(code='TVA',nom='TVA',taux=18)
        else:
            attrs.update(montant_ht=100,devise='XAF')
            if type_tarif!='references':attrs['site_id']=a['site']
            if type_tarif in ('references','produits'):attrs['conditionnement_id']=UUID(pid)
            if type_tarif=='produits':attrs['produit_id']=UUID(prod['id_produit'])
            if type_tarif=='categories':attrs['categorie_id']=UUID(cat['id_categorie'])
        key='id_regime' if type_tarif=='tva' else 'id_tarif'
        for debut,fin in [(date(2026,1,1),date(2026,6,30)),(date(2026,7,1),None)]:
            session.add(model(**attrs,**{key:uuid4()},debut=debut,fin=fin));session.commit()
        session.add(model(**attrs,**{key:uuid4()},debut=date(2026,6,30)))
        with pytest.raises(IntegrityError):session.flush()
        session.rollback()
    finally:gen.close()


def test_csv_pharmagabon_fourni_complet_sur_base_jetable(raw_client,account):
    import os,csv
    from pathlib import Path
    path=os.getenv('P2_CSV_TEST_FILE')
    if not path:pytest.skip('CSV fourni disponible uniquement dans le workspace de recette')
    content=Path(path).read_text(encoding='utf-8-sig')
    with open(path,encoding='utf-8-sig',newline='') as stream:rows=list(csv.DictReader(stream,delimiter=';'))
    c,a=raw_client,account;cat,data,prod,pid=setup(c,a)
    job=preview(c,a,content)
    report=c.get(root(a)+f'/imports/{job["id_import"]}').json()
    assert report['total']==len(rows) and report['compteurs']=={'INCONNU':len(rows)}
    for offset in range(0,len(rows),200):
        r=c.post(root(a)+f'/imports/{job["id_import"]}/lots',json={'offset':offset,'taille':200,'mode':'catalogue','categorie_id':cat['id_categorie'],'conditionnement_libelle':'UNITÉ COMMERCIALE À COMPLÉTER EXPLICITEMENT','devise':'XAF'})
        assert r.status_code==200,r.text
    assert c.get(root(a)+'/produits').json()['total']==len(rows)+1
    assert c.get(root(a)+'/conseils').json()['total']==len(rows)
    assert c.get(root(a)+'/tarification/references').json()['total']==0


@pytest.mark.parametrize('content',['CIP;Description\n0012345;"inachevé\n','CIP;Description\n0012345;TEST;champ en trop\n'])
def test_csv_structure_invalide_signalee(raw_client,account,content):
    c,a=raw_client,account;grant(c,a);login(c,a)
    r=c.post(root(a)+'/imports/previsualisation',json={'contenu':content,'nom_fichier':'test.csv','source':'TEST'})
    if 'inachevé' in content:assert r.status_code==422
    else:
        assert r.status_code==201
        report=c.get(root(a)+f'/imports/{r.json()["id_import"]}').json()
        assert report['compteurs']=={'INVALIDE':1} and 'Nombre de champs' in report['items'][0]['erreurs'][0]


def test_conseils_recherche_pagination_et_options_de_reprise(raw_client,account):
    c,a=raw_client,account;cat,data,prod,pid=setup(c,a)
    content='CIP;Description;PrixVente\n0000001;été premier;12\n0000002;été deuxième;15\n0000003;troisième;20\n'
    job=preview(c,a,content)
    config={'mode':'catalogue','devise':'xaf','categorie_id':cat['id_categorie'],'conditionnement_libelle':'UNITÉ EXPLICITE'}
    assert c.post(root(a)+f'/imports/{job["id_import"]}/lots',json=config).status_code==200
    advice=c.get(root(a)+'/conseils',params={'q':'été','page':2,'page_size':1}).json()
    assert advice['total']==2 and len(advice['items'])==1 and advice['items'][0]['designation'].startswith('ÉTÉ')
    assert c.get(root(a)+'/conseils',params={'q':'0000003'}).json()['total']==1
    options=c.get(root(a)+f'/imports/{job["id_import"]}').json()['options']
    assert options=={'mode':'catalogue','devise':'XAF','enrichir_designation':False,'categorie_id':cat['id_categorie'],'conditionnement_libelle':'UNITÉ EXPLICITE'}
    assert c.post(root(a)+f'/imports/{job["id_import"]}/lots',json={**config,'mode':'conseils'}).status_code==422
