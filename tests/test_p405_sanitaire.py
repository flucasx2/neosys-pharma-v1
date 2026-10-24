"""S01 : décisions HTTP/ORM, données exclusivement fictives et jetables."""
from datetime import date,timedelta
from uuid import UUID
import pytest
from sqlalchemy import select,func
from test_regularisation import raw_client,account,setup45,ret,final,post,root,db
from neosys_pharma.infrastructure.stock_models import LotModel,MouvementStockModel,StockEmplacementModel
from neosys_pharma.infrastructure.catalogue_models import ProduitModel,CategorieProduitModel
from neosys_pharma.infrastructure.regularisation_models import QuarantaineModel,DecisionQuarantaineModel


def snapshot(c):
    gen=db(c);s=next(gen)
    try:
        return ([tuple(row) for row in s.execute(select(StockEmplacementModel.id,StockEmplacementModel.physique,StockEmplacementModel.reserve).order_by(StockEmplacementModel.id))],
                s.scalar(select(func.count()).select_from(MouvementStockModel)))
    finally:gen.close()


@pytest.mark.parametrize('required,expiry,release,status',[
    (True,None,True,422),(True,30,True,200),(True,-1,True,422),
    (False,None,True,200),(False,-1,True,422),(True,None,False,200),
    (None,None,True,422),(True,0,True,200),
])
def test_peremption_a_la_decision_http(raw_client,account,required,expiry,release,status):
    c,a=raw_client,account;sale,session,product,pack,*_=setup45(c,a)
    receipt=final(c,a,sale,session);returned=ret(c,a,receipt)
    q=c.get(root(a)+'/stock/quarantaine').json()['items'][0]
    # Évolution du référentiel après la vente : le lot historique reste traçable.
    gen=db(c);s=next(gen)
    try:
        product_row=s.get(ProduitModel,UUID(product));product_row.gestion_peremption=required
        if required is None:
            s.get(CategorieProduitModel,product_row.categorie_id).gestion_peremption=True
        balance=s.get(StockEmplacementModel,UUID(q['stock_id'])) if 'stock_id' in q else s.get(StockEmplacementModel,s.scalar(select(QuarantaineModel)).stock_id)
        s.get(LotModel,balance.lot_id).peremption=None if expiry is None else date.today()+timedelta(days=expiry)
        s.commit()
    finally:gen.close()
    before=snapshot(c)
    result=post(c,a,f'/stock/quarantaine/{q["id"]}/decision',{
        'liberer':release,'identite_conforme':True,'lot_conforme':True,
        'integrite_conforme':True,'conservation_conforme':True,
        'justification':'Contrôle sanitaire synthétique'},status if status!=200 else 200)
    gen=db(c);s=next(gen)
    try:
        state=s.get(QuarantaineModel,UUID(q['id'])).etat
        decisions=s.scalar(select(func.count()).select_from(DecisionQuarantaineModel))
        if status==422:
            assert state=='EN_CONTROLE' and decisions==0
            assert snapshot(c)==before
        else:
            assert state==('LIBEREE' if release else 'REFUSEE') and decisions==1
            if release:
                after=snapshot(c)
                assert sum(row[1] for row in after[0])==sum(row[1] for row in before[0])+1
                assert after[1]==before[1]+1
            else:assert snapshot(c)==before
    finally:gen.close()
