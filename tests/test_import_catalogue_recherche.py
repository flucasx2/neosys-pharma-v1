"""Reproduction ciblée : fin de lots ne signifie pas création des inconnus."""
from sqlalchemy import select,func
from test_p2_complete import raw_client,account,setup,preview
from test_catalogue import root
from test_authentification import db
from test_p4p5_groupe_organismes import cible_isolee
from neosys_pharma.infrastructure.stock_models import StockEmplacementModel
pytest_plugins=('test_vente',)


def test_import_inconnu_bloque_puis_recherche_par_cip_et_nom(raw_client,account):
    c,a=raw_client,account;cat,*_=setup(c,a)
    job=preview(c,a,'CIP;Quantite;Description;PrixAchat;PrixVente\n0009876;9999;Produit fictif PharmaGabon;100;200\n')
    route=root(a)+f'/imports/{job["id_import"]}/lots'
    response=c.post(route,json={'mode':'catalogue','devise':'XAF'});assert response.status_code==200,response.text
    assert response.json()['termine'] is True # fin de pagination, pas réussite financière/catalogue
    report=c.get(root(a)+f'/imports/{job["id_import"]}').json();assert report['compteurs']=={'INCONNU':1}
    assert c.get(root(a)+'/produits',params={'q':'0009876'}).json()['total']==0
    response=c.post(route,json={'mode':'catalogue','devise':'XAF','categorie_id':cat['id_categorie'],'conditionnement_libelle':'Unité commerciale fictive'});assert response.status_code==200,response.text
    report=c.get(root(a)+f'/imports/{job["id_import"]}').json();assert report['compteurs']=={'IMPORTE':1}
    for query in ('0009876','Produit fictif PharmaGabon'):
        result=c.get(root(a)+'/produits',params={'q':query}).json();assert result['total']==1
        assert result['items'][0]['id_produit']==report['items'][0]['produit_id']
    gen=db(c);s=next(gen)
    try:assert s.scalar(select(func.count()).select_from(StockEmplacementModel))==0
    finally:gen.close()
