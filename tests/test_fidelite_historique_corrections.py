"""NC-P4-FID-004 / CLI-005 : données fictives, aucune recette conservée.

La fixture HTTP existante utilise SQLite mémoire par défaut. Pour ce module,
aucune URL de base externe n'est autorisée : les lectures ajoutées ne valident
ni les migrations ni la concurrence PostgreSQL.
"""
from decimal import Decimal
from types import SimpleNamespace
from uuid import UUID, uuid4

import pytest
from sqlalchemy import delete, select

from test_vente import raw_client, account, db, login, create
from test_caisse import ready, post, root, final, category, rule, body
from test_clients_p4b import root as clients_root
from test_vente import line, act
from neosys_pharma.application.caisse_service import CaisseService, serial
from neosys_pharma.domain.organisation.permissions_systeme import permission_id
from neosys_pharma.infrastructure.catalogue_models import ProduitModel, NatureMedicamentModel
from neosys_pharma.infrastructure.caisse_models import (
    CompteFideliteModel, EncaissementModel, JournalFideliteModel,
    ReglementModel, MouvementCaisseModel,
)
from neosys_pharma.infrastructure.vente_models import VenteModel
from neosys_pharma.infrastructure.stock_models import MouvementStockModel, StockEmplacementModel, ReservationStockModel
from neosys_pharma.infrastructure.prise_en_charge_models import CalculPriseEnChargeVenteModel, LigneCalculPriseEnChargeModel, PartCalculPriseEnChargeModel, RealisationPriseEnChargeModel
from neosys_pharma.infrastructure.securite_models import RoleModel, RolePermissionModel


@pytest.fixture(autouse=True)
def refuse_external_database(monkeypatch):
    # Ce module ne permet pas de rediriger la fixture destructive vers une base.
    monkeypatch.delenv('TEST_DATABASE_URL', raising=False)
    monkeypatch.delenv('DATABASE_URL', raising=False)


def allow_clients(c, a):
    gen=db(c); session=next(gen)
    try:
        role=session.scalar(select(RoleModel).where(RoleModel.organisation_id==a['org'], RoleModel.code=='CATALOGUE'))
        for code in ('client.consulter','client.gerer'):
            if not session.get(RolePermissionModel,(role.id_role,permission_id(code))):
                session.add(RolePermissionModel(role_id=role.id_role, permission_id=permission_id(code)))
        session.commit()
    finally:gen.close()


def change_nature(c,a,product,code):
    gen=db(c); session=next(gen)
    try:
        product=session.get(ProduitModel,UUID(product))
        if code is None:product.nature_id=None
        else:
            nature=session.scalar(select(NatureMedicamentModel).where(NatureMedicamentModel.organisation_id==a['org'], NatureMedicamentModel.code==code))
            if not nature:
                nature=NatureMedicamentModel(id_nature=uuid4(),organisation_id=a['org'],code=code,nom=code,actif=True)
                session.add(nature);session.flush()
            product.nature_id=nature.id_nature
        session.commit()
    finally:gen.close()


def financial_state(c):
    gen=db(c); session=next(gen)
    try:
        return {model.__tablename__:sorted([
            repr((serial(row),getattr(row,'pdf',None))) for row in session.scalars(select(model))
        ]) for model in (VenteModel,CompteFideliteModel,EncaissementModel,JournalFideliteModel,
                         ReglementModel,MouvementCaisseModel,MouvementStockModel,StockEmplacementModel,ReservationStockModel,
                         CalculPriseEnChargeVenteModel,LigneCalculPriseEnChargeModel,
                         PartCalculPriseEnChargeModel,RealisationPriseEnChargeModel)}
    finally:gen.close()


@pytest.mark.parametrize('nature,expected,points',[
    ('COSMETIQUE','ELIGIBLE',3),(None,'NATURE_ABSENTE',0),
    ('MEDICAMENT','NATURE_NON_ADMISE',0),('COSMÉTIQUES','NATURE_NON_ADMISE',0),
])
def test_information_serveur_et_gain_identique_sans_requalification(raw_client,account,nature,expected,points):
    c,a=raw_client,account; sale,se,product,*_=ready(c,a)
    titulaire=post(c,a,'/fidelite',{'nom':'Titulaire fictif'})
    rule(c,a,category(c,a,product));change_nature(c,a,product,nature)
    before=financial_state(c)
    url=root(a)+f'/ventes/{sale["id"]}/fidelite'
    response=c.get(url);assert response.status_code==200,response.text
    info=response.json()
    assert info['points_acquis'] is None and info['phase']=='AVANT_ENCAISSEMENT'
    assert info['lignes'][0]['code']==expected
    assert info['eligible_paye']==('301' if points else '0')
    assert financial_state(c)==before  # Le diagnostic ne crédite ni ne réserve.
    result=final(c,a,sale,se,compte_id=titulaire['id'],revision_compte=titulaire['revision'])
    assert result['instantane']['fidelite']['points_acquis']==points
    assert result['instantane']['client_id'] is None
    # SQLite relit DateTime sans offset ; comparer deux lectures persistées,
    # tout en exigeant l'identité intégrale du snapshot de la finalisation.
    frozen=c.get(root(a)+f'/recus/{result["id"]}').json()
    assert frozen['instantane']==result['instantane']
    before=financial_state(c)
    paid=c.get(url).json()
    assert paid['phase']=='ENCAISSEE' and paid['source']=='SNAPSHOT_ENCAISSEMENT'
    assert paid['points_acquis']==points and paid['lignes']==[]
    assert paid['code']==('ACQUISITION_CONFIRMEE' if points else 'ASSIETTE_NULLE')
    assert c.get(root(a)+f'/recus/{result["id"]}').json()==frozen
    assert financial_state(c)==before


def test_snapshot_zero_non_recalcule_apres_changement_catalogue(raw_client,account):
    c,a=raw_client,account;sale,se,product,*_=ready(c,a)
    titular=post(c,a,'/fidelite',{'nom':'Titulaire fictif'})
    rule(c,a,category(c,a,product));change_nature(c,a,product,'MEDICAMENT')
    enc=final(c,a,sale,se,compte_id=titular['id'],revision_compte=titular['revision'])
    pdf=c.get(root(a)+f'/recus/{enc["id"]}/pdf').content
    change_nature(c,a,product,'COSMETIQUE')
    before=financial_state(c)
    info=c.get(root(a)+f'/ventes/{sale["id"]}/fidelite').json()
    assert info['code']=='ASSIETTE_NULLE' and info['points_acquis']==0
    assert 'aucune réévaluation' in info['motif']
    assert c.get(root(a)+f'/recus/{enc["id"]}/pdf').content==pdf
    assert financial_state(c)==before


@pytest.mark.parametrize('with_rule,expected',[(False,'BAREME_ABSENT'),(True,'SEUIL_NON_ATTEINT')])
def test_motif_acquisition_nulle_absence_bareme_ou_seuil(raw_client,account,with_rule,expected):
    c,a=raw_client,account;sale,se,product,*_=ready(c,a)
    titulaire=post(c,a,'/fidelite',{'nom':'Titulaire fictif'})
    if with_rule:rule(c,a,category(c,a,product),montant_xaf=1000)
    enc=final(c,a,sale,se,compte_id=titulaire['id'],revision_compte=titulaire['revision'])
    before=financial_state(c)
    info=c.get(root(a)+f'/ventes/{sale["id"]}/fidelite').json()
    assert info['code']==expected and info['points_acquis']==0
    assert financial_state(c)==before


def test_historique_carte_caisse_preparation_deduplication_et_pagination(raw_client,account):
    c,a=raw_client,account;sale,se,product,pack,pid,cid=ready(c,a);allow_clients(c,a)
    ca=post(c,a,'/fidelite',{'nom':'Titulaire A fictif'})
    cb=post(c,a,'/fidelite',{'nom':'Titulaire B fictif'})
    client_id=ca['client']['profil_client_id']
    first=final(c,a,sale,se,compte_id=ca['id'],revision_compte=ca['revision'])
    assert first['instantane']['client_id'] is None
    assert first['instantane']['fidelite']['points']==0  # Pas de barème ; lien valable.
    second=line(c,a,create(c,a,pid,client_id=client_id),product,pack)
    second=act(c,a,act(c,a,second,'valider'),'transmettre',caisse_id=cid)
    current=c.get(root(a)+f'/fidelite/{ca["id"]}').json()
    current_session=c.get(root(a)+'/sessions').json()['items'][0]
    final(c,a,second,current_session,compte_id=ca['id'],revision_compte=current['revision'])
    third=create(c,a,pid,client_id=client_id)  # Préparation sans carte ni règlement.
    create(c,a,pid,client_id=cb['client']['profil_client_id'])
    before=financial_state(c)
    url=clients_root(a)+f'/{client_id}/ventes'
    pages=[c.get(url,params={'page':i,'page_size':1}).json() for i in (1,2,3)]
    assert all(p['total']==3 and len(p['items'])==1 for p in pages)
    items={p['items'][0]['id']:p['items'][0] for p in pages}
    assert set(items)=={sale['id'],second['id'],third['id']}
    assert items[sale['id']]['origines_rattachement']==['FIDELITE_CAISSE']
    assert items[second['id']]['origines_rattachement']==['PREPARATION','FIDELITE_CAISSE']
    assert items[third['id']]['origines_rattachement']==['PREPARATION']
    assert c.get(url,params={'page':4,'page_size':1}).json()['items']==[]
    other=c.get(clients_root(a)+f'/{cb["client"]["profil_client_id"]}/ventes').json()
    assert other['total']==1 and all(x['id'] not in items for x in other['items'])
    assert financial_state(c)==before


@pytest.mark.parametrize('removed',[
    'fidelite.consulter','vente.consulter','client.consulter','caisse.consulter',
])
def test_permissions_distinctes_historique_et_recu(raw_client,account,removed):
    c,a=raw_client,account;sale,se,product,pack,pid,cid=ready(c,a);allow_clients(c,a)
    ca=post(c,a,'/fidelite',{'nom':'Titulaire A fictif'})
    enc=final(c,a,sale,se,compte_id=ca['id'],revision_compte=ca['revision'])
    profile=ca['client']['profil_client_id'];prepared=create(c,a,pid,client_id=profile)
    gen=db(c);session=next(gen)
    try:
        session.execute(delete(RolePermissionModel).where(RolePermissionModel.permission_id==permission_id(removed)))
        session.commit()
    finally:gen.close()
    before=financial_state(c)
    r=c.get(clients_root(a)+f'/{profile}/ventes')
    if removed=='client.consulter':assert r.status_code==403
    elif removed=='vente.consulter':assert r.status_code==200 and r.json()['total']==0
    elif removed=='fidelite.consulter':
        assert r.status_code==200 and r.json()['total']==1
        assert r.json()['items'][0]['id']==prepared['id']
        assert r.json()['items'][0]['origines_rattachement']==['PREPARATION']
    else:
        assert r.status_code==200 and r.json()['total']==2
        assert all('recu_id' not in x for x in r.json()['items'])
        assert c.get(root(a)+f'/recus/{enc["id"]}/pdf').status_code==403
    if removed in ('fidelite.consulter','caisse.consulter'):
        assert c.get(root(a)+f'/ventes/{sale["id"]}/fidelite').status_code==403
    assert financial_state(c)==before


def test_refus_organisation_site_emplacement_et_non_authentifie(raw_client,account):
    c,a=raw_client,account;sale,se,*_=ready(c,a);allow_clients(c,a)
    ca=post(c,a,'/fidelite',{'nom':'Titulaire fictif'})
    final(c,a,sale,se,compte_id=ca['id'],revision_compte=ca['revision'])
    url=clients_root(a)+f'/{ca["client"]["profil_client_id"]}/ventes'
    info_url=root(a)+f'/ventes/{sale["id"]}/fidelite'
    before=financial_state(c)
    assert c.get(url.replace(str(a['org']),str(uuid4()))).status_code==403
    assert c.get(info_url.replace(str(a['org']),str(uuid4()))).status_code==403
    c.headers['X-Site-ID']=str(a['other'])
    assert c.get(url).status_code==403
    assert c.get(info_url).status_code==403
    c.headers['X-Site-ID']=str(a['site']);c.headers['X-Emplacement-ID']=str(a['denied'])
    assert c.get(url).status_code==403
    assert c.get(info_url).status_code==403
    c.headers['X-Emplacement-ID']=str(a['location'])
    assert c.get(url).json()['total']==1
    c.cookies.clear()
    assert c.get(url).status_code==401
    assert c.get(info_url).status_code==401
    assert financial_state(c)==before


@pytest.mark.parametrize('amount,expected',[(106500,106),(999,0),(1000,1)])
def test_assiette_commune_arrondi_et_part_client_exacte(amount,expected):
    sale=SimpleNamespace(id=uuid4());product_id=uuid4();line_id=uuid4();nature_id=uuid4();cat_id=uuid4()
    line_=SimpleNamespace(id=line_id,produit_id=product_id,actif=True,designation='Cosmétique fictif')
    product=SimpleNamespace(nature_id=nature_id,categorie_id=cat_id)
    nature=SimpleNamespace(code='COSMETIQUE')
    service=CaisseService.__new__(CaisseService)
    service.s=SimpleNamespace(get=lambda model,key:{product_id:product,nature_id:nature}.get(key))
    service.vente=SimpleNamespace(lignes=lambda v:[line_])
    service.categorie_eligible=lambda cid,rule:cid==cat_id
    service.bareme=lambda kind:SimpleNamespace(points=1,montant_xaf=Decimal(1000))
    # serial concerne le barème ORM ; seul ce bord de sortie est substitué.
    from unittest.mock import patch
    account_=SimpleNamespace(points=0,dette=0,revision=1)
    finance={'lignes':{str(line_id):{'ttc':'200000'}}}
    with patch('neosys_pharma.application.caisse_service.serial',return_value={'points':1,'montant_xaf':'1000'}):
        gain=service.gagner(sale,account_,finance,{line_id:amount})
    assert gain['points_acquis']==expected and gain['eligible_paye']==str(amount)
    assert account_.points==expected


def test_categorie_hors_bareme_expliquee_sans_acquisition(raw_client,account):
    c,a=raw_client,account;sale,se,product,*_=ready(c,a)
    from test_catalogue import post as catalogue_post
    outside=catalogue_post(c,a,'/categories',{'code':'AUTRE','nom':'Autre catégorie fictive'})
    rule(c,a,outside['id_categorie'])
    info=c.get(root(a)+f'/ventes/{sale["id"]}/fidelite').json()
    assert info['lignes'][0]['code']=='CATEGORIE_NON_ADMISE'
    assert info['eligible_paye']=='0' and info['points_acquis'] is None
    # Aucun encaissement : le barème de test est sans incidence sur un historique.


def test_information_apres_encaissement_sans_compte(raw_client,account):
    c,a=raw_client,account;sale,se,*_=ready(c,a)
    result=final(c,a,sale,se)
    before=financial_state(c)
    info=c.get(root(a)+f'/ventes/{sale["id"]}/fidelite').json()
    assert result['compte_id'] is None and result['instantane']['fidelite'] is None
    assert info['code']=='SANS_FIDELITE' and info['points_acquis']==0
    assert financial_state(c)==before


def test_diagnostic_p5_limite_a_la_part_client_sans_modifier_snapshot(raw_client,account):
    from test_p5b_3_encaissement_prise_en_charge import _prepare, _post
    c,a=raw_client,account
    sale,se,profile,compte,beneficiary,product,payers=_prepare(c,a)
    calc=_post(c,f'/api/tiers-payants/organisations/{a["org"]}/ventes/{sale["id"]}/prise-en-charge/confirmer',{
        'cle':str(uuid4()),'revision':sale['revision'],'beneficiaire_id':str(beneficiary)},201)
    rule(c,a,category(c,a,product),montant_xaf=1000)
    before=financial_state(c)
    r=c.get(root(a)+f'/ventes/{sale["id"]}/fidelite')
    assert r.status_code==200,r.text
    info=r.json()
    assert Decimal(info['eligible_paye'])==calc['part_client_xaf']
    assert info['lignes'][0]['montant_client_eligible_xaf']==calc['part_client_xaf']
    assert calc['total_xaf']==calc['part_client_xaf']+calc['total_organismes_xaf']
    assert info['points_acquis'] is None and financial_state(c)==before
