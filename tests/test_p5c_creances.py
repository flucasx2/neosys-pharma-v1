"""P5-C.1 : données fictives ; le garde natif précède les fixtures destructrices."""
from datetime import date
from uuid import UUID,uuid4
from copy import deepcopy
import pytest
from sqlalchemy import select,update,func
from sqlalchemy.exc import DBAPIError
from test_stock import raw_client,account,db,login
from test_p4p5_groupe_organismes import cible_isolee
from test_p5b_3_encaissement_prise_en_charge import _prepare,_post
from test_p5a_tiers_payants import root
from test_caisse import final
from test_regularisation import grant45,ret
from neosys_pharma.domain.configuration_convention import configuration_validee,verifier_preuve
from neosys_pharma.domain.creances import controle_administratif,ENGAGEMENTS
from neosys_pharma.domain.organisation.permissions_systeme import permission_id,P5C_PERMISSIONS
from neosys_pharma.infrastructure.securite_models import RoleModel,RolePermissionModel
from neosys_pharma.infrastructure.tiers_payants_models import ConfigurationConventionModel,AdhesionOrganismeModel
from neosys_pharma.infrastructure.creance_models import CreanceOrganismeModel,VersionDossierCreanceModel
pytest_plugins=('test_vente',)


def definition():
    return {'regime':None,'mode_verification':'IDENTIFICATION','types_beneficiaires':['TITULAIRE'],
        'champs':[{'code':'MAT','libelle':'Matricule','type':'TEXTE','format':None,'obligatoire':True},
            {'code':'DOS','libelle':'Dossier facturation','type':'TEXTE','format':None,'obligatoire':True,'finalite':'FACTURATION'}],
        'justificatifs':[{'code':'ATTEST','libelle':'Attestation pour facture','obligatoire':True,'groupe_alternative':None,'finalite':'FACTURATION'}]}


def post(c,a,path,body,status=200,key=None):
    return _post(c,root(a)+'/creances'+path,{'cle':str(key or uuid4()),**body},status)


def prepare(c,a,configured=True):
    sale,session,profile,loyalty,bene,product,payers=_prepare(c,a)
    gen=db(c);s=next(gen)
    try:
        role=s.scalar(select(RoleModel).where(RoleModel.organisation_id==a['org'],RoleModel.code=='CATALOGUE'))
        for code in [x[0] for x in P5C_PERMISSIONS]+['tiers_payant.adhesion.gerer']:
            s.add(RolePermissionModel(role_id=role.id_role,permission_id=permission_id(code)))
        rows=s.scalars(select(AdhesionOrganismeModel).where(AdhesionOrganismeModel.organisation_id==a['org'])).all()
        ads=[(str(x.id),x.revision) for x in rows]
        if configured:
            for x in rows:s.add(ConfigurationConventionModel(organisation_id=a['org'],convention_id=x.convention_id,
                schema_version=1,definition=definition(),auteur_id=a['user']))
        s.commit()
    finally:gen.close()
    login(c,a)
    if configured:
        for ident,revision in ads:
            _post(c,root(a)+f"/ventes/{sale['id']}/verifications",{'cle':str(uuid4()),'adhesion_id':ident,
                'revision_adhesion':revision,'beneficiaire_id':str(bene),'source':'IDENTIFICATION','reference':'FICTIF-FIN',
                'resultat':'CONFIRME','motif':'Droits contrôlés','date_verification':str(date.today()),'date_fin':str(date.today()),
                'valeurs':{'MAT':'123'},'documents':[]},201)
    prefix=root(a)+f"/ventes/{sale['id']}/prise-en-charge"
    simulation=_post(c,prefix+'/simuler',{'beneficiaire_id':str(bene)},200)
    assert simulation['statut']=='CALCUL_ADMISSIBLE_PROVISOIRE',simulation
    calc=_post(c,prefix+'/confirmer',{'cle':str(uuid4()),'revision':sale['revision'],'beneficiaire_id':str(bene)},201)
    return sale,session,calc


def realise(c,a,sale,session,calc):
    enc=final(c,a,sale,session,reglements=[{'mode':'ESPECES','montant':calc['part_client_xaf']}])
    sources=c.get(root(a)+'/creances/sources');assert sources.status_code==200,sources.text
    return sources.json()['items'][0],enc


def complete(claim):
    return {x['id']:{'valeurs':{'DOS':'DOS-FICTIF'},'documents':[{'code':'ATTEST','reference':'ATT-FICTIVE','verifie':True}]} for x in claim['exigences']}


def test_fac02_distinction_finance_administration_legacy_et_formats():
    config=configuration_validee(definition());verifier_preuve(config,{'MAT':'123'},[],'IDENTIFICATION','REF')
    with pytest.raises(ValueError,match='Matricule'):verifier_preuve(config,{},[],'IDENTIFICATION','REF')
    legacy=deepcopy(config);del legacy['champs'][1]['finalite']
    with pytest.raises(ValueError,match='Dossier'):verifier_preuve(legacy,{'MAT':'123'},[],'IDENTIFICATION','REF')
    req=[{'id':'C','definition':config,'valeurs':{'MAT':'123'},'documents':[],'source':'IDENTIFICATION','reference':'REF'}]
    assert controle_administratif(req,{})
    assert controle_administratif(req,{'C':{'valeurs':{'DOS':'REF'}}})
    assert controle_administratif(req,complete({'exigences':req}))==[]
    for payload in ({'UNKNOWN':{}},{'C':{'documents':{}}},{'C':{'valeurs':{'MAT':'autre titulaire'}}}):
        with pytest.raises(ValueError):controle_administratif(req,payload)
    invalid=deepcopy(config);invalid['champs'][0]['finalite']='INVENTEE'
    with pytest.raises(ValueError):configuration_validee(invalid)


def test_constitution_confirmee_idempotence_et_controle_facturation(raw_client,account):
    c,a=raw_client,account;sale,session,calc=prepare(c,a)
    assert c.get(root(a)+'/creances/sources').json()['total']==0
    post(c,a,'',{'realisation_id':calc['id']},404)
    real,enc=realise(c,a,sale,session,calc)
    key=uuid4();body={'realisation_id':real['id']};result=post(c,a,'',body,201,key)
    assert post(c,a,'',body,201,key)==result
    again=post(c,a,'',body,201)
    assert {x['id'] for x in again['creances']}=={x['id'] for x in result['creances']}
    assert len(result['creances'])==2
    assert sum(x['montant_xaf'] for x in result['creances'])==calc['total_organismes_xaf']
    claim=result['creances'][0];ident=claim['id'];assert claim['exigences']
    assert claim['etat_effectif']=='A_COMPLETER' and not claim['facturable']
    for operation in ENGAGEMENTS:post(c,a,f'/{ident}/controle-engagement',{'revision':1,'operation':operation},409)
    post(c,a,f'/{ident}/verifier',{'revision':1,'conforme':True,'motif':'Refus incomplet'},409)
    second=post(c,a,f'/{ident}/complements',{'revision':1,'complements':complete(claim),'motif':'Pièces ajoutées'})
    assert second['dossier']['revision']==2 and second['etat_effectif']=='A_CONTROLER' and not second['facturable']
    post(c,a,f'/{ident}/complements',{'revision':1,'complements':{},'motif':'Périmé'},409)
    third=post(c,a,f'/{ident}/verifier',{'revision':2,'conforme':True,'motif':'Dossier contrôlé'})
    assert third['facturable'] and third['snapshot_hash']==claim['snapshot_hash']
    for operation in ENGAGEMENTS:assert post(c,a,f'/{ident}/controle-engagement',{'revision':3,'operation':operation})['controle_seulement']
    history=c.get(root(a)+f'/creances/{ident}/historique').json()
    assert [x['revision'] for x in history['items']]==[3,2,1] and history['items'][-1]['complements']=={}
    fourth=post(c,a,f'/{ident}/complements',{'revision':3,'complements':{},'motif':'Reprise'})
    assert not fourth['facturable'] and fourth['montant_xaf']==claim['montant_xaf']


def test_retours_bloquent_engagement_sans_recalculer_creances(raw_client,account):
    c,a=raw_client,account;sale,session,calc=prepare(c,a);real,enc=realise(c,a,sale,session,calc)
    claim=post(c,a,'',{'realisation_id':real['id']},201)['creances'][0];ident=claim['id']
    post(c,a,f'/{ident}/complements',{'revision':1,'complements':complete(claim),'motif':'Pièces reçues'})
    post(c,a,f'/{ident}/verifier',{'revision':2,'conforme':True,'motif':'Contrôlé'})
    grant45(c,a);ret(c,a,enc,1)
    current=c.get(root(a)+f'/creances/{ident}').json()
    assert current['etat_effectif']=='EN_ANOMALIE' and not current['facturable'] and current['retours']
    assert current['snapshot']==claim['snapshot'] and current['montant_xaf']==claim['montant_xaf']
    for operation in ENGAGEMENTS:post(c,a,f'/{ident}/controle-engagement',{'revision':3,'operation':operation},409)


def test_legacy_non_configure_reste_non_facturable(raw_client,account):
    c,a=raw_client,account;sale,session,calc=prepare(c,a,False);real,_=realise(c,a,sale,session,calc)
    claim=post(c,a,'',{'realisation_id':real['id']},201)['creances'][0]
    assert claim['dossier']['anomalies']==['EXIGENCES_DOCUMENTAIRES_NON_DEFINIES']
    post(c,a,f"/{claim['id']}/verifier",{'revision':1,'conforme':True,'motif':'Sans règles'},409)


def test_permissions_csrf_isolation_et_immutabilite(raw_client,account):
    c,a=raw_client,account;sale,session,calc=prepare(c,a);real,_=realise(c,a,sale,session,calc)
    claim=post(c,a,'',{'realisation_id':real['id']},201)['creances'][0];ident=UUID(claim['id'])
    gen=db(c);s=next(gen)
    try:
        role=s.scalar(select(RoleModel).where(RoleModel.organisation_id==a['org'],RoleModel.code=='CATALOGUE'))
        grant=s.get(RolePermissionModel,(role.id_role,permission_id('tiers_payant.creance.verifier')));s.delete(grant);s.commit()
        for cls,field,value in [(CreanceOrganismeModel,'montant_xaf',1),(VersionDossierCreanceModel,'etat','FACTURE')]:
            with pytest.raises(DBAPIError):s.execute(update(cls).values(**{field:value}));s.commit()
            s.rollback()
    finally:gen.close()
    post(c,a,f'/{ident}/verifier',{'revision':1,'conforme':False,'motif':'Sans droit'},403)
    assert c.get(root(a)+f'/creances/{ident}',headers={'X-Site-ID':str(uuid4())}).status_code==403
    assert c.get(root(a).replace(str(a['org']),str(uuid4()))+f'/creances/{ident}').status_code==403
    token=c.headers.pop('X-CSRF-Token',None)
    try:assert c.post(root(a)+'/creances',json={'cle':str(uuid4()),'realisation_id':real['id']}).status_code==403
    finally:
        if token:c.headers['X-CSRF-Token']=token


def test_rollback_constitution_complete(raw_client,account,monkeypatch):
    c,a=raw_client,account;sale,session,calc=prepare(c,a);real,_=realise(c,a,sale,session,calc)
    from neosys_pharma.application.creance_service import CreanceService
    original=CreanceService._version;calls=[]
    def fail(self,*args,**kw):
        calls.append(1);result=original(self,*args,**kw)
        if len(calls)==2:raise ValueError('Échec provoqué après la deuxième créance')
        return result
    with monkeypatch.context() as m:
        m.setattr(CreanceService,'_version',fail);post(c,a,'',{'realisation_id':real['id']},422)
    assert c.get(root(a)+'/creances').json()['total']==0
    assert len(post(c,a,'',{'realisation_id':real['id']},201)['creances'])==2


@pytest.mark.parametrize('operation',['constitution','revision'])
def test_concurrence_postgresql_reelle(raw_client,account,operation):
    from sqlalchemy.orm import Session
    from sqlalchemy import text
    from threading import Event
    from concurrent.futures import ThreadPoolExecutor
    import time
    from neosys_pharma.application.creance_service import CreanceService
    from neosys_pharma.application.stock_service import StockService
    from neosys_pharma.domain.stock import ConflitStock
    gen=db(raw_client);s=next(gen);engine=s.get_bind();gen.close()
    if engine.dialect.name!='postgresql':pytest.skip('PostgreSQL natif absent ; SQLite ne prouve pas la concurrence.')
    c,a=raw_client,account;sale,session,calc=prepare(c,a);real,_=realise(c,a,sale,session,calc)
    claim=post(c,a,'',{'realisation_id':real['id']},201)['creances'][0] if operation=='revision' else None
    held,release,started=Event(),Event(),Event();pids={}
    def worker(first):
        with Session(engine) as s:
            s.execute(text("SET LOCAL statement_timeout='10s'"));s.execute(text("SET LOCAL lock_timeout='8s'"))
            pids[first]=s.scalar(text('select pg_backend_pid()'))
            stock=StockService(s,a['org'],a['user'],lambda *args:None,date.today())
            if not first:started.set()
            def action():
                if first:
                    held.set()
                    if not release.wait(8):raise TimeoutError('Contention non libérée')
                app=CreanceService(stock,a['site'])
                return app.constituer(UUID(real['id'])) if not claim else app.completer(UUID(claim['id']),1,complete(claim),'Complément concurrent')
            try:return stock.operation(uuid4(),'P5C1:TEST',{'source':real['id']},action)
            except ConflitStock:return 'CONFLIT'
    pool=ThreadPoolExecutor(max_workers=2)
    try:
        one=pool.submit(worker,True);assert held.wait(5)
        two=pool.submit(worker,False);assert started.wait(5)
        assert pids[True]!=pids[False]
        blocked=False;deadline=time.monotonic()+5
        while time.monotonic()<deadline:
            with engine.connect() as probe:blocked=pids[True] in probe.scalar(text('select pg_blocking_pids(:pid)'),{'pid':pids[False]})
            if blocked:break
            time.sleep(.05)
        assert blocked,'Contention native non observée'
        release.set();r1=one.result(timeout=12);r2=two.result(timeout=12)
        if claim:assert r2=='CONFLIT' and r1['dossier']['revision']==2
        else:assert {x['id'] for x in r1['creances']}=={x['id'] for x in r2['creances']}
        with Session(engine) as s:
            assert s.scalar(select(func.count()).select_from(CreanceOrganismeModel))==2
            assert s.scalar(select(func.count()).select_from(VersionDossierCreanceModel))==(3 if claim else 2)
    finally:release.set();pool.shutdown(wait=True,cancel_futures=True)


def test_contraintes_source_et_organisation(raw_client,account):
    c,a=raw_client,account;sale,session,calc=prepare(c,a);real,_=realise(c,a,sale,session,calc)
    claim=post(c,a,'',{'realisation_id':real['id']},201)['creances'][0]
    gen=db(c);s=next(gen)
    try:
        row=s.get(CreanceOrganismeModel,UUID(claim['id']));values={col.name:getattr(row,col.name) for col in row.__table__.columns}
        with pytest.raises(DBAPIError,match='UNIQUE|unique'):
            s.execute(CreanceOrganismeModel.__table__.insert().values(values|{'id':uuid4()}));s.commit()
        s.rollback()
        # Éviter que UNIQUE masque une erreur de FK : autre organisme du même périmètre.
        from neosys_pharma.infrastructure.client_models import OrganismePriseEnChargeModel
        payer=uuid4();s.add(OrganismePriseEnChargeModel(id=payer,organisation_id=a['org'],code='FK-QA',nom='Contrôle FK fictif',actif=True,revision=1));s.commit()
        for changes in ({'site_id':uuid4()},{'organisation_id':uuid4()},{'realisation_id':uuid4()}):
            with pytest.raises(DBAPIError,match='FOREIGN KEY|foreign key'):
                s.execute(CreanceOrganismeModel.__table__.insert().values(values|changes|{'id':uuid4(),'organisme_id':payer}));s.commit()
            s.rollback()
        version=s.scalar(select(VersionDossierCreanceModel).where(VersionDossierCreanceModel.creance_id==UUID(claim['id'])))
        data={col.name:getattr(version,col.name) for col in version.__table__.columns}
        with pytest.raises(DBAPIError,match='UNIQUE|unique'):
            s.execute(VersionDossierCreanceModel.__table__.insert().values(data|{'id':uuid4()}));s.commit()
        s.rollback()
        assert s.scalar(select(func.count()).select_from(CreanceOrganismeModel))==2
    finally:gen.close()


def test_downgrade_refuse_sur_creances_existantes(raw_client,account,tmp_path,monkeypatch):
    """Copie SQLite locale des données fictives, sans toucher à la base du fixture."""
    import sqlite3
    from alembic import command
    from alembic.config import Config
    from neosys_pharma.infrastructure.config import get_settings
    c,a=raw_client,account
    gen=db(c);s=next(gen);engine=s.get_bind();gen.close()
    if engine.dialect.name!='sqlite':pytest.skip('Copie SQLite spécifique ; cycle natif couvert séparément.')
    sale,session,calc=prepare(c,a);real,_=realise(c,a,sale,session,calc)
    post(c,a,'',{'realisation_id':real['id']},201)
    path=tmp_path/'downgrade-fictif.db'
    with engine.connect() as connection:
        destination=sqlite3.connect(path)
        try:connection.connection.driver_connection.backup(destination)
        finally:destination.close()
    monkeypatch.setenv('DATABASE_URL','sqlite+pysqlite:///'+str(path));get_settings.cache_clear()
    try:
        cfg=Config('alembic.ini');command.stamp(cfg,'20261019_05')
        with pytest.raises(RuntimeError,match='conserver'):command.downgrade(cfg,'20261019_04')
        with sqlite3.connect(path) as probe:assert probe.execute('select count(*) from tiers_payant_creances').fetchone()[0]==2
    finally:get_settings.cache_clear()
