"""Extension P4/P5 : une réalisation et un encaissement par vente, jamais le brut en caisse."""
from datetime import date, datetime, timezone
from decimal import Decimal
from io import BytesIO
from uuid import UUID, uuid4
import os
import pytest
from pypdf import PdfReader
from sqlalchemy import select, func, create_engine, inspect, text
from test_stock import raw_client, account, db, stocks
from test_caisse import groupe_post, groupe_put, post as cash_post, root as cash_root, rule, category
from test_vente import create, line, act
from test_p5b_3_encaissement_prise_en_charge import _prepare, _post, _refund_idempotent
from test_regularisation import grant45, ret, current, post as reg_post
from neosys_pharma.infrastructure.client_models import ClientModel
from neosys_pharma.infrastructure.caisse_models import ClientFideliteModel, CompteFideliteModel, EncaissementModel, MouvementCaisseGroupeModel, JournalFideliteModel
from neosys_pharma.infrastructure.tiers_payants_models import BeneficiaireCouvertureModel, AdhesionOrganismeModel, AdhesionBeneficiaireModel, ConventionOrganismeModel
from neosys_pharma.infrastructure.prise_en_charge_models import RealisationPriseEnChargeModel

pytest_plugins=('test_vente',)


@pytest.fixture(autouse=True)
def cible_isolee():
    url=os.getenv('TEST_DATABASE_URL','sqlite+pysqlite://')
    if url.startswith('sqlite'):return
    # Les fixtures historiques suppriment leurs tables. Elles ne peuvent entrer
    # ici que dans une base neuve, marquée, explicitement créée pour ce fichier.
    from sqlalchemy.engine import make_url
    p=make_url(url);marker=os.getenv('P4P5_CONFIRM_DATABASE')
    if p.get_backend_name()!='postgresql' or not p.database.startswith('neosys_p4p5_') or marker!=p.database:
        raise RuntimeError('Base PostgreSQL jetable neosys_p4p5_* et confirmation exacte requises.')
    engine=create_engine(url)
    try:
        with engine.connect() as c:
            assert c.scalar(text('select current_database()'))==marker
            assert c.scalar(text("select shobj_description(oid,'pg_database') from pg_database where datname=current_database()"))=='NEOSYS_P4P5_DISPOSABLE'
            assert not inspect(c).get_table_names(),'Base non vide : fixtures destructrices refusées.'
    finally:engine.dispose()


def prepare(c,a,covered_second=True):
    sale,session,profile,loyalty,beneficiary,product,payers=_prepare(c,a)
    gen=db(c);s=next(gen);client2,legacy2,loyalty2,bene2=uuid4(),uuid4(),uuid4(),uuid4()
    try:
        s.add(ClientModel(id=client2,organisation_id=a['org'],nom='Second client fictif',actif=True,revision=1));s.flush()
        s.add(ClientFideliteModel(id=legacy2,organisation_id=a['org'],nom='Second client fictif',profil_client_id=client2))
        s.add(CompteFideliteModel(id=loyalty2,organisation_id=a['org'],client_id=legacy2,points=0,dette=0,revision=1))
        if covered_second:
            s.add(BeneficiaireCouvertureModel(id=bene2,organisation_id=a['org'],client_id=client2,nom='Second bénéficiaire fictif',actif=True,revision=1,auteur_id=a['user']));s.flush()
            for contract in s.scalars(select(ConventionOrganismeModel).where(ConventionOrganismeModel.organisation_id==a['org'])):
                adhesion=AdhesionOrganismeModel(organisation_id=a['org'],convention_id=contract.id,titulaire_id=bene2,
                    reference_adhesion='SECOND-'+contract.code,date_debut=date.today(),date_fin=None,statut='ACTIVE',droits_statut='CONFIRMES',
                    reference_verification_droits='QA-SECOND',droits_verifies_le=datetime.now(timezone.utc),revision=1,auteur_id=a['user'])
                s.add(adhesion);s.flush();s.add(AdhesionBeneficiaireModel(organisation_id=a['org'],adhesion_id=adhesion.id,beneficiaire_id=bene2,relation='TITULAIRE',date_debut=date.today()))
        s.commit()
    finally:gen.close()
    second=line(c,a,create(c,a,sale['poste_id'],mode='MUTUELLE' if covered_second else 'SANS_TIERS',client_id=str(client2)),
                product,sale['lignes'][0]['conditionnement_id'],10)
    second=act(c,a,second,'valider');second=act(c,a,second,'transmettre',caisse_id=session['caisse_id'])
    def confirm(sale,bid):
        return _post(c,f"/api/tiers-payants/organisations/{a['org']}/ventes/{sale['id']}/prise-en-charge/confirmer",
                     {'cle':str(uuid4()),'revision':sale['revision'],'beneficiaire_id':str(bid)},201)
    first_calc=confirm(sale,beneficiary);second_calc=confirm(second,bene2) if covered_second else None
    return (sale,second),session,(loyalty,loyalty2),(first_calc,second_calc),product


def draft(c,a,sales,session):
    d=groupe_post(c,a,'',{'cle':str(uuid4()),'session_id':session['id']},201);ident=d['dossier']['id']
    d=groupe_put(c,a,f'/{ident}/ventes',{'cle':str(uuid4()),'revision':d['dossier']['revision'],
        'ventes':[{'vente_id':s['id'],'revision':s['revision']} for s in sales]})
    return ident,d


def fund(c,a,ident,d,sales,session):
    due=int(Decimal(d['totaux']['du_xaf']))
    confirmation=cash_post(c,a,f"/ventes/{sales[0]['id']}/confirmations",{'session_id':session['id'],'revision':sales[0]['revision'],
        'mode':'CARTE','montant':300,'reference':'P4P5-CARTE','source':'MANUEL_TERMINAL','preuve':'Terminal fictif accepté'})
    cash_post(c,a,f"/ventes/{sales[0]['id']}/confirmations/{confirmation['id']}/rapprocher",{'session_id':session['id'],'revision':sales[0]['revision'],'justification':'Rapprochement fictif'},200)
    d=groupe_put(c,a,f'/{ident}/reglements',{'cle':str(uuid4()),'revision':d['dossier']['revision'],
        'reglements':[{'mode':'CARTE','montant':300,'confirmation_id':confirmation['id']},{'mode':'ESPECES','montant':due-300+50,'rendu':50}]})
    payments={p['mode']:p['id'] for p in d['reglements']};allocations=[]
    for sale,card in zip(d['ventes'],(200,100),strict=True):
        allocations += [{'vente_id':sale['vente_id'],'reglement_id':payments['CARTE'],'montant':card},
                       {'vente_id':sale['vente_id'],'reglement_id':payments['ESPECES'],'montant':int(Decimal(sale['montant_du']))-card}]
    return groupe_put(c,a,f'/{ident}/allocations',{'cle':str(uuid4()),'revision':d['dossier']['revision'],'allocations':allocations})


@pytest.mark.parametrize('covered_second',[False,True])
def test_groupe_organismes_parts_clients_multicomptes_retour_x_et_idempotence(raw_client,account,monkeypatch,covered_second):
    from neosys_pharma.presentation import encaissement_groupe_api
    monkeypatch.setattr(encaissement_groupe_api,'GROUPED_ENCASHMENT_ENABLED',True) # exclusivement l'application fictive de test
    c,a=raw_client,account;sales,session,accounts,calculs,product=prepare(c,a,covered_second)
    rule(c,a,category(c,a,product),points=1,montant_xaf=1000)
    ident,d=draft(c,a,sales,session)
    dues=[calc['part_client_xaf'] if calc else int(sale['totaux']['ttc']) for sale,calc in zip(sales,calculs,strict=True)]
    assert [int(x['montant_du']) for x in d['ventes']]==dues
    d=fund(c,a,ident,d,sales,session)
    payload={'cle':str(uuid4()),'revision':d['dossier']['revision'],'revision_session':session['revision'],
        'fidelite':[{'vente_id':sale['id'],'compte_id':str(acct),'revision_compte':1} for sale,acct in zip(sales,accounts,strict=True)]}
    result=groupe_post(c,a,f'/{ident}/finaliser',payload)
    assert groupe_post(c,a,f'/{ident}/finaliser',payload)==result
    assert c.post(cash_root(a)+f'/groupes/{ident}/finaliser',json=payload|{'revision_session':99}).status_code==409
    receipts={r['vente_id']:r for r in result['resultat']['recus_individuels']}
    for sale,due,calc,acct in zip(sales,dues,calculs,accounts,strict=True):
        receipt=receipts[sale['id']]
        assert int(receipt['total_xaf'])==due
        assert sum(Decimal(x['montant']) for x in receipt['instantane']['reglements'])==due
        assert int(receipt['instantane']['totaux']['ttc'])==int(sale['totaux']['ttc'])
        if calc:assert receipt['instantane']['prise_en_charge']['calcul_id']==calc['id']
        assert c.get(cash_root(a)+f'/fidelite/{acct}').json()['points']==due//1000
    assert sum(x['physique'] for x in stocks(c,a))==10 and sum(x['reserve'] for x in stocks(c,a))==0
    gen=db(c);s=next(gen)
    try:
        assert s.scalar(select(func.count()).select_from(EncaissementModel))==2
        assert s.scalar(select(func.count()).select_from(RealisationPriseEnChargeModel))==1+int(covered_second)
        assert s.scalar(select(func.count()).select_from(MouvementCaisseGroupeModel))==2
        assert s.scalar(select(func.sum(MouvementCaisseGroupeModel.montant_net)))==sum(dues)
    finally:gen.close()
    pdf=c.get(cash_root(a)+f'/groupes/{ident}/recu.pdf');assert pdf.status_code==200
    text_pdf=' '.join(p.extract_text() for p in PdfReader(BytesIO(pdf.content)).pages)
    assert 'Parts organismes' in text_pdf and 'Parts clients encaissées' in text_pdf
    grant45(c,a);se=current(c,a,session)
    x=reg_post(c,a,'/clotures/x',{'session_id':session['id'],'revision':se['revision']})
    assert int(x['instantane']['session']['nets_par_mode']['CARTE'])==300
    assert int(x['instantane']['session']['nets_par_mode']['ESPECES'])==sum(dues)-300
    receipt=receipts[sales[0]['id']];returned=ret(c,a,receipt,10)
    assert int(returned['montant'])==dues[0]//2
    _refund_idempotent(c,a,returned,session['id'],'ESPECES')
    assert c.get(cash_root(a)+f'/fidelite/{accounts[1]}').json()['points']==dues[1]//1000
    assert c.get(cash_root(a)+f"/recus/{receipts[sales[1]['id']]['id']}/pdf").status_code==200


def test_rollback_groupe_organismes_integral_avant_commit(raw_client,account,monkeypatch):
    from neosys_pharma.presentation import encaissement_groupe_api
    from neosys_pharma.infrastructure import caisse_pdf
    monkeypatch.setattr(encaissement_groupe_api,'GROUPED_ENCASHMENT_ENABLED',True)
    c,a=raw_client,account;sales,session,accounts,calcs,product=prepare(c,a,True)
    rule(c,a,category(c,a,product),points=1,montant_xaf=1000)
    ident,d=draft(c,a,sales,session);d=fund(c,a,ident,d,sales,session)
    payload={'cle':str(uuid4()),'revision':d['dossier']['revision'],'revision_session':session['revision'],
        'fidelite':[{'vente_id':sale['id'],'compte_id':str(acct),'revision_compte':1} for sale,acct in zip(sales,accounts,strict=True)]}
    original=caisse_pdf.recu_groupe_pdf
    monkeypatch.setattr(caisse_pdf,'recu_groupe_pdf',lambda _:(_ for _ in ()).throw(RuntimeError('Échec collectif provoqué')))
    with pytest.raises(RuntimeError,match='collectif'):groupe_post(c,a,f'/{ident}/finaliser',payload)
    for sale in sales:assert c.get(cash_root(a)+f"/ventes/{sale['id']}").json()['etat']=='TRANSMISE'
    gen=db(c);s=next(gen)
    try:
        for model in (EncaissementModel,RealisationPriseEnChargeModel,MouvementCaisseGroupeModel,JournalFideliteModel):
            assert s.scalar(select(func.count()).select_from(model))==0
        assert all(s.get(CompteFideliteModel,acct).points==0 for acct in accounts)
    finally:gen.close()
    assert sum(x['physique'] for x in stocks(c,a))==40 and sum(x['reserve'] for x in stocks(c,a))==30
    monkeypatch.setattr(caisse_pdf,'recu_groupe_pdf',original)
    assert groupe_post(c,a,f'/{ident}/finaliser',payload)['dossier']['etat']=='FINALISE'


@pytest.mark.parametrize('competitor',['meme_dossier','autre_dossier','individuel'])
def test_contention_native_groupe_organismes(raw_client,account,competitor):
    """Deux connexions réelles bloquées simultanément, jamais un scénario séquentiel."""
    from concurrent.futures import ThreadPoolExecutor
    from threading import Event
    import time
    from sqlalchemy.orm import Session
    from neosys_pharma.application.stock_service import StockService
    from neosys_pharma.application.caisse_service import CaisseService
    from neosys_pharma.application.vente_service import VenteService
    from neosys_pharma.application.encaissement_groupe_service import EncaissementGroupeService
    from neosys_pharma.domain.stock import ConflitStock
    c,a=raw_client,account
    gen=db(c);session_db=next(gen);engine=session_db.get_bind();gen.close()
    if engine.dialect.name!='postgresql':pytest.skip('Contention PostgreSQL native non exécutée ; SQLite ne vaut pas preuve.')
    sales,session,accounts,calcs,product=prepare(c,a,True)
    def fund_cash(ident,d):
        d=groupe_put(c,a,f'/{ident}/reglements',{'cle':str(uuid4()),'revision':d['dossier']['revision'],
            'reglements':[{'mode':'ESPECES','montant':int(Decimal(d['totaux']['du_xaf']))}]})
        proposal=c.get(cash_root(a)+f'/groupes/{ident}/allocations/proposition',params={'revision':d['dossier']['revision']}).json()
        return groupe_put(c,a,f'/{ident}/allocations',{'cle':str(uuid4()),'revision':d['dossier']['revision'],'allocations':proposal})
    ident,d=draft(c,a,sales,session);d=fund_cash(ident,d)
    group_data={'revision':d['dossier']['revision'],'revision_session':session['revision'],'fidelite':[]}
    other_id,other_data=ident,group_data
    if competitor=='autre_dossier':
        other_id,other_draft=draft(c,a,sales,session);other_draft=fund_cash(other_id,other_draft)
        other_data={'revision':other_draft['dossier']['revision'],'revision_session':session['revision'],'fidelite':[]}
    key=uuid4();held,release,ready=Event(),Event(),Event();pids={}
    def worker(first):
        with Session(engine) as s:
            s.execute(text("SET LOCAL statement_timeout='10s'"));s.execute(text("SET LOCAL lock_timeout='8s'"))
            pids[first]=s.scalar(text('select pg_backend_pid()'))
            stock=StockService(s,a['org'],a['user'],lambda *args:None,date.today())
            cash=CaisseService(VenteService(stock,a['site']))
            grouped=EncaissementGroupeService(cash)
            if not first:ready.set()
            def action():
                if first:
                    held.set()
                    if not release.wait(8):raise TimeoutError('Contention non libérée')
                if not first and competitor=='individuel':
                    data={'session_id':UUID(session['id']),'revision_session':session['revision'],'revision':sales[0]['revision'],
                        'reglements':[{'mode':'ESPECES','montant':calcs[0]['part_client_xaf']}],
                        'points_utilises':0,'consentement':False,'compte_id':None,'revision_compte':None}
                    return cash.finaliser(UUID(sales[0]['id']),data)
                return grouped.finaliser(UUID(ident if first else other_id),group_data if first else other_data,key)
            try:
                # Identical request/key for the simultaneous replay, otherwise a distinct operation.
                opkey=key if first or competitor=='meme_dossier' else uuid4()
                return stock.operation(opkey,'P4P5:GROUPE',group_data if first else other_data,action)
            except ConflitStock:return 'CONFLIT'
    pool=ThreadPoolExecutor(max_workers=2)
    try:
        first=pool.submit(worker,True);assert held.wait(5)
        second=pool.submit(worker,False);assert ready.wait(5)
        assert pids[True]!=pids[False]
        blocked=False;deadline=time.monotonic()+5
        while time.monotonic()<deadline:
            with engine.connect() as s:blocked=pids[True] in s.scalar(text('select pg_blocking_pids(:pid)'),{'pid':pids[False]})
            if blocked:break
            time.sleep(.05)
        assert blocked,'Contention réelle non observée'
        release.set();result=first.result(timeout=12);other=second.result(timeout=12)
        assert isinstance(result,dict)
        assert other==result if competitor=='meme_dossier' else other=='CONFLIT'
        with Session(engine) as s:
            assert s.scalar(select(func.count()).select_from(EncaissementModel))==2
            assert s.scalar(select(func.count()).select_from(RealisationPriseEnChargeModel))==2
            assert s.scalar(select(func.sum(MouvementCaisseGroupeModel.montant_net)))==sum(x['part_client_xaf'] for x in calcs)
    finally:release.set();pool.shutdown(wait=True,cancel_futures=True)
