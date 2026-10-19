"""Administration autonome : HTTP, droits explicites, audit et compatibilité P4-B."""
from uuid import UUID, uuid4
from datetime import date
import pytest
from sqlalchemy import select, func
from test_stock import raw_client, account, db, login
from test_catalogue import grant
from neosys_pharma.infrastructure.client_models import ClientModel, OrganismePriseEnChargeModel
from neosys_pharma.infrastructure.tiers_payants_models import EvenementTiersPayantModel
from neosys_pharma.domain.tiers_payants import normaliser_identite_organisme

MANAGE = 'tiers_payant.organisme.gerer'
def root(a): return f'/api/tiers-payants/organisations/{a["org"]}/organismes'


def test_admin_organisme_autonome_revision_idempotence_audit_et_compatibilite(raw_client, account):
    c,a=raw_client,account
    grant(c,a,(MANAGE,'client.consulter','client.gerer')); login(c,a)
    body={'cle':str(uuid4()),'code':' qa-organisme ','nom':' Organisme QA '}
    response=c.post(root(a),json=body);assert response.status_code==201,response.text
    org=response.json();assert org['code']=='QA-ORGANISME' and org['nom']=='Organisme QA'
    assert c.post(root(a),json=body).json()==org
    assert c.post(root(a),json=body|{'nom':'Autre'}).status_code==409
    assert c.post(root(a),json=body|{'cle':str(uuid4())}).status_code==409
    assert c.get(root(a),params={'q':'qa-organisme'}).json()['total']==1
    assert c.get(root(a),params={'q':'%'}).json()['total']==0  # literal search
    change={'cle':str(uuid4()),'revision':1,'code':'QA-ORGANISME','nom':'Nom modifié','actif':False}
    response=c.put(root(a)+'/'+org['id'],json=change);assert response.status_code==200,response.text
    assert response.json()['revision']==2
    assert c.put(root(a)+'/'+org['id'],json=change).json()==response.json()
    assert c.put(root(a)+'/'+org['id'],json=change|{'cle':str(uuid4())}).status_code==409
    assert c.get(root(a),params={'actif':False}).json()['total']==1
    assert c.get(root(a),params={'actif':True}).json()['total']==0
    assert c.get(f'/api/clients/organisations/{a["org"]}/organismes').json()['total']==0
    change.update(cle=str(uuid4()),revision=2,actif=True)
    assert c.put(root(a)+'/'+org['id'],json=change).status_code==200
    assert c.get(f'/api/clients/organisations/{a["org"]}/organismes').json()['items'][0]['id']==org['id']
    gen=db(c);s=next(gen)
    try:
        assert s.scalar(select(func.count()).select_from(ClientModel))==0
        assert s.scalar(select(func.count()).select_from(OrganismePriseEnChargeModel))==1
        events=s.scalars(select(EvenementTiersPayantModel).where(EvenementTiersPayantModel.entite_id==UUID(org['id'])).order_by(EvenementTiersPayantModel.date)).all()
        assert len(events)==3  # replays and failed writes create no duplicate audit
        assert events[1].donnees['avant']['nom']=='Organisme QA'
        assert events[1].donnees['apres']['nom']=='Nom modifié'
        assert all(event.auteur_id==a['user'] for event in events)
    finally:gen.close()


def test_admin_organisme_permissions_perimetres_csrf_et_lecture_seule(raw_client, account):
    c,a=raw_client,account
    assert c.get(root(a)).status_code==401
    login(c,a)
    assert c.get(root(a)).status_code==403
    assert c.post(root(a),json={'cle':str(uuid4()),'code':'A','nom':'A'}).status_code==403
    grant(c,a,('tiers_payant.consulter',));login(c,a)
    assert c.get(root(a)).status_code==200
    assert c.post(root(a),json={'cle':str(uuid4()),'code':'A','nom':'A'}).status_code==403
    assert c.put(root(a)+'/'+str(uuid4()),json={'cle':str(uuid4()),'revision':1,'code':'A','nom':'A','actif':True}).status_code==403
    assert c.get(root(a),headers={'X-Site-ID':str(a['other'])}).status_code==403
    assert c.get(root(a),headers={'X-Emplacement-ID':str(a['denied'])}).status_code==403
    assert c.get(root(a).replace(str(a['org']),str(uuid4()))).status_code==403


def test_admin_organisme_refus_champs_et_organisation_etrangere(raw_client, account):
    c,a=raw_client,account;grant(c,a,(MANAGE,));login(c,a)
    for payload in [{'code':'  ','nom':'Nom'}, {'code':'A','nom':'  '}, {'code':'A','nom':'N','droits_statut':'CONFIRMES'}, {'code':'A','nom':'N\x00'}]:
        assert c.post(root(a),json={'cle':str(uuid4()),**payload}).status_code==422
    body={'cle':str(uuid4()),'code':'A','nom':'Nom'}
    token=c.headers.pop('X-CSRF-Token')
    assert c.post(root(a),json=body).status_code==403
    c.headers['X-CSRF-Token']=token
    other_id=uuid4();foreign_id=uuid4()
    from neosys_pharma.infrastructure.organisation_models import OrganisationModel
    gen=db(c);s=next(gen)
    try:
        s.add(OrganisationModel(id_organisation=other_id,nom_commercial='Autre QA',raison_sociale='Autre QA',actif=True));s.flush()
        s.add(OrganismePriseEnChargeModel(id=foreign_id,organisation_id=other_id,code='ETRANGER',nom='Confidentiel QA'));s.commit()
    finally:gen.close()
    assert c.get(root(a)).json()['total']==0
    assert c.get(root(a)+'/'+str(foreign_id)).status_code==404
    assert c.put(root(a)+'/'+str(foreign_id),json=body|{'revision':1,'actif':True}).status_code==404
    row=c.post(root(a),json=body).json()
    assert c.put(root(a)+'/'+row['id'],json=body|{'cle':str(uuid4()),'revision':1,'actif':'false'}).status_code==422
    assert c.get(root(a),params={'page_size':101}).status_code==422


@pytest.mark.parametrize('code,nom',[('', 'A'),('A',''),('A'*81,'N'),('A','N'*201),('A\nB','N')])
def test_identite_organisme_invalide(code,nom):
    with pytest.raises(ValueError):normaliser_identite_organisme(code,nom)


def test_permission_migration_additive_conserve_organisme(tmp_path,monkeypatch):
    from alembic import command
    from alembic.config import Config
    import sqlalchemy as sa
    from neosys_pharma.infrastructure.config import get_settings
    from neosys_pharma.domain.organisation.permissions_systeme import permission_id
    url=f'sqlite+pysqlite:///{tmp_path / "conf-organismes.db"}'
    monkeypatch.setenv('DATABASE_URL',url);get_settings.cache_clear();cfg=Config('alembic.ini')
    engine=sa.create_engine(url)
    try:
        command.upgrade(cfg,'20261017_03')
        org_id,payer_id=uuid4().hex,uuid4().hex
        with engine.begin() as s:
            s.execute(sa.text('INSERT INTO organisations(id_organisation,nom_commercial,raison_sociale,actif) VALUES (:id,\'QA\',\'QA\',1)'),{'id':org_id})
            s.execute(sa.text('INSERT INTO organismes_prise_en_charge(id,organisation_id,code,nom,actif,revision) VALUES (:id,:org,\'QA\',\'Historique QA\',1,1)'),{'id':payer_id,'org':org_id})
        command.upgrade(cfg,'20261018_01');command.check(cfg)
        with engine.connect() as s:
            assert s.scalar(sa.text('SELECT nom FROM organismes_prise_en_charge WHERE id=:id'),{'id':payer_id})=='Historique QA'
            assert s.scalar(sa.text('SELECT count(*) FROM permissions WHERE code=:code'),{'code':MANAGE})==1
            assert s.scalar(sa.text('SELECT count(*) FROM roles_permissions WHERE permission_id=:id'),{'id':permission_id(MANAGE).hex})==0
        command.downgrade(cfg,'20261017_03')
        with engine.connect() as s:
            assert s.scalar(sa.text('SELECT count(*) FROM organismes_prise_en_charge'))==1
            assert s.scalar(sa.text('SELECT count(*) FROM permissions WHERE code=:code'),{'code':MANAGE})==0
        command.upgrade(cfg,'20261018_01')
    finally:engine.dispose();get_settings.cache_clear()


def test_desactivation_conserve_convention_et_refuse_nouvelle_version(raw_client, account):
    c,a=raw_client,account
    grant(c,a,(MANAGE,'tiers_payant.convention.gerer'));login(c,a)
    row=c.post(root(a),json={'cle':str(uuid4()),'code':'ORG','nom':'Original QA'}).json()
    base=root(a).removesuffix('/organismes')
    payload={'cle':str(uuid4()),'organisme_id':row['id'],'code':'C1','date_debut':date.today().isoformat(),'conditions':{},'extensions_p5b':{}}
    response=c.post(base+'/conventions',json=payload);assert response.status_code==201,response.text
    historical=c.get(base+'/conventions').json()['items']
    response=c.put(root(a)+'/'+row['id'],json={'cle':str(uuid4()),'revision':1,'code':'ORG','nom':'Renommé QA','actif':False})
    assert response.status_code==200,response.text
    assert c.get(base+'/conventions').json()['items']==historical
    assert c.post(base+'/conventions',json=payload|{'cle':str(uuid4()),'code':'C2'}).status_code==422
    assert c.delete(root(a)+'/'+row['id']).status_code==405
