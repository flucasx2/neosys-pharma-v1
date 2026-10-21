"""B04 : rendu serveur exact, HTTP et allocations ; fixtures SQLite isolées."""
from decimal import Decimal
from uuid import uuid4
import pytest
from neosys_pharma.domain.caisse import repartir_paiements
from neosys_pharma.domain.encaissement_groupe import (
    calculer_rendu_groupe, ReglementGroupe, VenteGroupe, repartir_automatiquement,
)
from test_caisse import (
    raw_client, account, ready, final, post, root, body, groupe_post, groupe_put,
    line, create, act,
)


@pytest.mark.parametrize("due,rows,change", [
    (7000, [{"mode":"ESPECES","montant":7000}], 0),
    (7000, [{"mode":"ESPECES","montant":10000}], 3000),
    (101400, [{"mode":"ESPECES","montant":90500}, {"mode":"CARTE","montant":10000}, {"mode":"MOBILE_MONEY","montant":1400}], 500),
    (7000, [{"mode":"CARTE","montant":7000}], 0),
    (7000, [{"mode":"ESPECES","montant":5000}, {"mode":"ESPECES","montant":5000}], 3000),
    (999999999999999900, [{"mode":"ESPECES","montant":"999999999999999999"}], 99),
])
def test_reference_exacte_simple_et_groupe(due, rows, change):
    for calculated in (repartir_paiements(due,rows), calculer_rendu_groupe(due,rows)):
        assert sum(Decimal(x['rendu']) for x in calculated)==change
        assert sum(Decimal(x['montant'])-x['rendu'] for x in calculated)==due
        assert all(not x['rendu'] for x in calculated if x['mode']!='ESPECES')
    assert all('rendu' not in row for row in rows)


@pytest.mark.parametrize("rows", [
    [{"mode":"CARTE","montant":7001}],
    [{"mode":"CARTE","montant":7001},{"mode":"ESPECES","montant":10000}],
    [{"mode":"MOBILE_MONEY","montant":7001},{"mode":"ESPECES","montant":1}],
])
def test_excedent_non_especes_refuse(rows):
    for calculate in (repartir_paiements,calculer_rendu_groupe):
        with pytest.raises(ValueError): calculate(7000,rows)


def test_insuffisant_brouillon_non_finalisable_et_fcfa_invalides():
    rows=calculer_rendu_groupe(7000,[{'mode':'ESPECES','montant':6000}])
    assert rows[0]['rendu']==0
    with pytest.raises(ValueError): repartir_paiements(7000,rows)
    with pytest.raises(ValueError): repartir_automatiquement([VenteGroupe(uuid4(),1,1,7000)],[ReglementGroupe(uuid4(),1,'ESPECES',6000)])
    for amount in ('1.5','NaN','Infinity','-1'):
        with pytest.raises(ValueError): calculer_rendu_groupe(7000,[{'mode':'ESPECES','montant':amount}])
    with pytest.raises(ValueError,match='net positif'):
        calculer_rendu_groupe(7000,[{'mode':'CARTE','montant':7000},{'mode':'ESPECES','montant':100}])


def test_allocations_reference_deux_tickets():
    sales=[VenteGroupe(uuid4(),1,1,33800),VenteGroupe(uuid4(),2,1,67600)]
    rows=calculer_rendu_groupe(101400,[{'mode':'ESPECES','montant':90500},{'mode':'CARTE','montant':10000},{'mode':'MOBILE_MONEY','montant':1400}])
    payments=[ReglementGroupe(uuid4(),i+1,r['mode'],r['montant'],r['rendu'],None if r['mode']=='ESPECES' else uuid4()) for i,r in enumerate(rows)]
    allocations=repartir_automatiquement(sales,payments)
    for sale in sales: assert sum(a.montant for a in allocations if a.vente_id==sale.vente_id)==sale.montant_du
    assert sum(a.montant for a in allocations if a.reglement_id==payments[0].reglement_id)==90000


@pytest.mark.parametrize('cash,expected,status', [(301,0,200),(1000,699,200),(300,0,422)])
def test_simple_http_rendu_autoritaire_rejeu(raw_client,account,cash,expected,status):
    c,a=raw_client,account
    sale,session,*_=ready(c,a)
    payload=body(sale,session,reglements=[{'mode':'ESPECES','montant':cash}]);key=uuid4()
    result=post(c,a,f"/ventes/{sale['id']}/finaliser",payload,status,key)
    if status==200:
        assert Decimal(result['instantane']['reglements'][0]['rendu'])==expected
        assert post(c,a,f"/ventes/{sale['id']}/finaliser",payload,status,key)==result
        assert c.get(root(a)+f"/recus/{result['id']}/pdf").status_code==200


def test_groupe_serveur_recalcule_rendu_et_totaux(raw_client,account):
    c,a=raw_client,account
    first,session,product,pack,pid,cid=ready(c,a)
    second=line(c,a,create(c,a,pid),product,pack,2)
    second=act(c,a,second,'valider');second=act(c,a,second,'transmettre',caisse_id=cid)
    d=groupe_post(c,a,'',{'cle':str(uuid4()),'session_id':session['id']},201)
    gid=d['dossier']['id']
    d=groupe_put(c,a,f'/{gid}/ventes',{'cle':str(uuid4()),'revision':d['dossier']['revision'],'ventes':[{'vente_id':v['id'],'revision':v['revision']} for v in (first,second)]})
    # Le client omet le rendu : le serveur doit calculer 48, et non accepter 0.
    d=groupe_put(c,a,f'/{gid}/reglements',{'cle':str(uuid4()),'revision':d['dossier']['revision'],'reglements':[{'mode':'ESPECES','montant':550,'rendu':0}]})
    assert d['reglements'][0]['rendu']=='48'
    assert d['totaux']['brut_recu_xaf']=='550'
    assert d['totaux']['rendu_xaf']=='48'
    assert d['totaux']['net_regle_xaf']=='502'
    assert d['totaux']['reste_xaf']=='0'
