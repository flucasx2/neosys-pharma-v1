"""Contrôles ciblés P4-B : fiche indépendante, associations génériques et compatibilité fidélité."""
from uuid import uuid4

from sqlalchemy import select

from test_vente import raw_client, account, db, login, setup as setup_vente, create, line as vente_line, act as vente_act, root as vente_root
from test_catalogue import grant
from neosys_pharma.domain.organisation.permissions_systeme import permission_id
from neosys_pharma.infrastructure.securite_models import RoleModel, RolePermissionModel


def root(a):return f'/api/clients/organisations/{a["org"]}'


def post(c,a,path,body,status=201):
    response=c.post(root(a)+path,json={'cle':str(uuid4()),**body})
    assert response.status_code==status,response.text
    return response.json() if response.content else None


def grant_client(c,a):
    grant(c,a,('client.consulter','client.gerer','fidelite.gerer','fidelite.consulter'))


def test_fiche_client_independante_et_plusieurs_organismes(raw_client,account):
    c,a=raw_client,account;grant_client(c,a);login(c,a)
    client=post(c,a,'',{'nom':'Alice Exemple','telephone':'070 123 456','courriel':'ALICE@example.test'})
    assert client['nom']=='Alice Exemple' and client['fidelite'] is None and client['organismes']==[]
    assert c.get(root(a)).json()['total']==1
    main=post(c,a,'/organismes',{'code':'ORG-PRINCIPAL','nom':'Organisme principal'})
    extra=post(c,a,'/organismes',{'code':'ORG-COMPLEMENT','nom':'Organisme complémentaire'})
    first=post(c,a,f'/{client["id"]}/organismes',{'organisme_id':main['id'],'role':'PRINCIPAL','reference':'REF-1'})
    second=post(c,a,f'/{client["id"]}/organismes',{'organisme_id':extra['id'],'role':'COMPLEMENTAIRE','reference':'REF-2'})
    assert {x['role'] for x in first['organismes']}=={'PRINCIPAL'}
    assert {x['role'] for x in second['organismes']}=={'PRINCIPAL','COMPLEMENTAIRE'}
    post(c,a,f'/{client["id"]}/organismes',{'organisme_id':extra['id'],'role':'PRINCIPAL'},422)
    detail=c.get(root(a)+f'/{client["id"]}')
    assert detail.status_code==200,detail.text
    assert detail.json().get('fidelite') is None


def test_permissions_client_non_attribuees_par_defaut(raw_client,account):
    c,a=raw_client,account;login(c,a)
    assert c.get(root(a)).status_code==403
    assert c.post(root(a),json={'cle':str(uuid4()),'nom':'Interdit'}).status_code==403


def test_adhesion_fidelite_optionnelle_et_compatibilite_du_compte(raw_client,account):
    c,a=raw_client,account;grant_client(c,a);login(c,a)
    client=post(c,a,'',{'nom':'Cliente Fidélité','telephone':'070 222 333'})
    enrolled=post(c,a,f'/{client["id"]}/fidelite',{})
    assert enrolled['client']['nom']=='Cliente Fidélité'
    updated=c.put(root(a)+f'/{client["id"]}',json={'cle':str(uuid4()),'revision':1,'nom':'Cliente Renommée','telephone':'070 222 334','courriel':None,'actif':True})
    assert updated.status_code==200,updated.text
    assert updated.json()['fidelite']['compte_id']==enrolled['id']
    assert c.get(f'/api/caisses/organisations/{a["org"]}/fidelite/{enrolled["id"]}').json()['client']['nom']=='Cliente Renommée'


def test_preparation_peut_referencer_une_fiche_client_et_historique_scoped(raw_client,account):
    c,a=raw_client,account;product,pack,post_id,_=setup_vente(c,a)
    gen=db(c);s=next(gen)
    try:
        role=s.scalar(select(RoleModel).where(RoleModel.organisation_id==a['org'],RoleModel.code=='CATALOGUE'))
        s.add_all([RolePermissionModel(role_id=role.id_role,permission_id=permission_id('client.consulter')),RolePermissionModel(role_id=role.id_role,permission_id=permission_id('client.gerer'))]);s.commit()
    finally:gen.close()
    client=post(c,a,'',{'nom':'Client Vente'})
    sale=create(c,a,post_id,client_id=client['id'])
    assert sale['client_id']==client['id']
    history=c.get(root(a)+f'/{client["id"]}/ventes')
    assert history.status_code==200,history.text
    assert history.json()['total']==1 and history.json()['items'][0]['id']==sale['id']


def test_selection_client_dans_preparation_et_verrouillage_apres_etat_final(raw_client,account):
    c,a=raw_client,account;product,pack,post_id,_=setup_vente(c,a)
    sale=create(c,a,post_id)
    denied=c.put(vente_root(a)+f'/{sale["id"]}/client',json={'cle':str(uuid4()),'revision':sale['revision'],'client_id':None})
    assert denied.status_code==403
    gen=db(c);s=next(gen)
    try:
        role=s.scalar(select(RoleModel).where(RoleModel.organisation_id==a['org'],RoleModel.code=='CATALOGUE'))
        for code in ('client.consulter','client.gerer'):
            s.add(RolePermissionModel(role_id=role.id_role,permission_id=permission_id(code)))
        s.commit()
    finally:gen.close()
    login(c,a)
    client=post(c,a,'',{'nom':'Sélection explicite'})
    assert c.get(root(a),params={'q':client['id']}).json()['items'][0]['id']==client['id']
    response=c.put(vente_root(a)+f'/{sale["id"]}/client',json={'cle':str(uuid4()),'revision':sale['revision'],'client_id':client['id']})
    assert response.status_code==200,response.text
    assigned=response.json();assert assigned['client_id']==client['id'] and assigned['client']['nom']=='Sélection explicite'
    cleared=c.put(vente_root(a)+f'/{sale["id"]}/client',json={'cle':str(uuid4()),'revision':assigned['revision'],'client_id':None})
    assert cleared.status_code==200 and cleared.json()['client_id'] is None
    final=c.put(vente_root(a)+f'/{sale["id"]}/client',json={'cle':str(uuid4()),'revision':cleared.json()['revision'],'client_id':client['id']})
    assert final.status_code==200
    prepared=vente_line(c,a,final.json(),product,pack)
    waiting=vente_act(c,a,prepared,'attendre')
    refused=c.put(vente_root(a)+f'/{sale["id"]}/client',json={'cle':str(uuid4()),'revision':waiting['revision'],'client_id':None})
    assert refused.status_code==409


def test_migration_relie_les_titulaires_fidelite_existants_sans_fusion(tmp_path,monkeypatch):
    import sqlalchemy as sa
    from alembic import command
    from alembic.config import Config
    from neosys_pharma.infrastructure.config import get_settings
    org_id,loyalty_id=uuid4(),uuid4()
    url=f'sqlite+pysqlite:///{tmp_path / "p4b-backfill.db"}'
    monkeypatch.setenv('DATABASE_URL',url);get_settings.cache_clear()
    engine=sa.create_engine(url);cfg=Config('alembic.ini')
    try:
        command.upgrade(cfg,'f22f6abb13c5')
        org=sa.table('organisations',sa.column('id_organisation',sa.Uuid()),sa.column('nom_commercial',sa.String()),sa.column('raison_sociale',sa.String()),sa.column('logo',sa.String()),sa.column('coordonnees',sa.String()),sa.column('informations_legales',sa.String()),sa.column('actif',sa.Boolean()))
        legacy=sa.table('fidelite_clients',sa.column('id',sa.Uuid()),sa.column('organisation_id',sa.Uuid()),sa.column('nom',sa.String()),sa.column('telephone',sa.String()))
        with engine.begin() as conn:
            conn.execute(sa.insert(org).values(id_organisation=org_id,nom_commercial='Test',raison_sociale='Test',logo=None,coordonnees=None,informations_legales=None,actif=True))
            conn.execute(sa.insert(legacy).values(id=loyalty_id,organisation_id=org_id,nom='Titulaire existant',telephone='070123456'))
        command.upgrade(cfg,'head')
        with engine.connect() as conn:
            query=sa.text('SELECT c.nom,c.telephone,f.profil_client_id FROM fidelite_clients f JOIN clients c ON c.id=f.profil_client_id WHERE f.id=:id').bindparams(sa.bindparam('id',type_=sa.Uuid()))
            result=conn.execute(query,{'id':loyalty_id}).one()
        assert result.nom=='Titulaire existant' and result.telephone=='070123456'
        assert result.profil_client_id is not None
    finally:
        engine.dispose();get_settings.cache_clear()


def test_migration_p4b_postgresql_natif_sur_base_jetable_dediee(monkeypatch):
    """Cycle/backfill PostgreSQL exécuté uniquement avec l'URL dédiée de la CI jetable."""
    import os
    import pytest
    import sqlalchemy as sa
    from alembic import command
    from alembic.config import Config
    from alembic.script import ScriptDirectory
    from neosys_pharma.infrastructure.config import get_settings

    url = os.getenv('TEST_P4B_MIGRATION_DATABASE_URL')
    if not url or os.getenv('P4B_CI_DISPOSABLE_DATABASE') != '1':
        pytest.skip('Base PostgreSQL éphémère CI non explicitement autorisée : migration native P4-B non exécutée.')
    parsed = sa.engine.make_url(url)
    assert parsed.drivername.startswith('postgresql+psycopg'), 'Cette recette exige PostgreSQL natif via psycopg.'
    assert parsed.database == 'neosys_p4b_migration', 'Refus : seule la base CI jetable dédiée est autorisée.'
    assert parsed.username == 'neosys_test' and parsed.host == 'localhost' and parsed.port == 5432, 'Refus : serveur PostgreSQL différent du service CI jetable.'
    assert parsed.database not in {'neosys_pharma_v1', 'neosys_p46_recette_20261012'}

    monkeypatch.setenv('DATABASE_URL', url)
    get_settings.cache_clear()
    engine = sa.create_engine(url)
    cfg = Config('alembic.ini')
    org_id, loyalty_id = uuid4(), uuid4()
    try:
        with engine.connect() as connection:
            assert connection.scalar(sa.text('SELECT current_database()')) == 'neosys_p4b_migration'
            assert int(connection.scalar(sa.text('SHOW server_version_num'))) >= 120000
            assert not sa.inspect(connection).get_table_names(), 'La base dédiée doit être neuve et vide.'

        command.upgrade(cfg, 'f22f6abb13c5')
        org = sa.table(
            'organisations', sa.column('id_organisation', sa.Uuid()),
            sa.column('nom_commercial', sa.String()), sa.column('raison_sociale', sa.String()),
            sa.column('logo', sa.String()), sa.column('coordonnees', sa.String()),
            sa.column('informations_legales', sa.String()), sa.column('actif', sa.Boolean()),
        )
        legacy = sa.table(
            'fidelite_clients', sa.column('id', sa.Uuid()), sa.column('organisation_id', sa.Uuid()),
            sa.column('nom', sa.String()), sa.column('telephone', sa.String()),
        )
        with engine.begin() as connection:
            connection.execute(sa.insert(org).values(
                id_organisation=org_id, nom_commercial='P4-B QA', raison_sociale='P4-B QA',
                logo=None, coordonnees=None, informations_legales=None, actif=True,
            ))
            connection.execute(sa.insert(legacy).values(
                id=loyalty_id, organisation_id=org_id, nom='Titulaire PostgreSQL', telephone='070123456',
            ))

        command.upgrade(cfg, 'head')
        with engine.connect() as connection:
            result = connection.execute(sa.text(
                'SELECT c.nom, c.telephone, f.profil_client_id '
                'FROM fidelite_clients f JOIN clients c ON c.id=f.profil_client_id WHERE f.id=:id'
            ), {'id': loyalty_id}).one()
            assert (result.nom, result.telephone) == ('Titulaire PostgreSQL', '070123456')
            assert result.profil_client_id is not None
            assert connection.scalar(sa.text('SELECT version_num FROM alembic_version')) == \
                ScriptDirectory.from_config(cfg).get_current_head()
    finally:
        engine.dispose()
        get_settings.cache_clear()
