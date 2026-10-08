from dataclasses import replace
from uuid import UUID, uuid4
from datetime import timedelta

import pytest
from sqlalchemy import select, func
from sqlalchemy.exc import IntegrityError
from test_p1_vertical import raw_client
from test_authentification import account, db, login
from test_http_autorisations_p1 import set_state
from neosys_pharma.domain.catalogue import CategorieProduit, Conditionnement, Produit, ReferenceProduit, TypeReference, verifier_hierarchie
from neosys_pharma.domain.organisation.securite import Role, TypeRole, RolePermission, AffectationRole
from neosys_pharma.domain.organisation.permissions_systeme import permission_id
from neosys_pharma.infrastructure.securite_repository import SqlAlchemySecuriteRepository
from neosys_pharma.infrastructure.securite_models import AffectationSiteModel, AffectationEmplacementModel, RolePermissionModel
from neosys_pharma.infrastructure.catalogue_models import ProduitModel, ReferenceProduitModel, ConditionnementModel, CategorieProduitModel
from neosys_pharma.infrastructure.organisation_models import OrganisationModel
from neosys_pharma.infrastructure.catalogue_repository import SqlAlchemyCatalogueRepository
from neosys_pharma.application.catalogue_service import CatalogueService


def grant(c, a, permissions=('catalogue.consulter', 'catalogue.gerer')):
    gen = db(c); session = next(gen)
    try:
        repo = SqlAlchemySecuriteRepository(session)
        role = Role(code='CATALOGUE', nom='Catalogue explicite', type_role=TypeRole.PERSONNALISE, organisation_id=a['org'])
        repo.ajouter(role)
        for code in permissions:
            repo.ajouter(RolePermission(role_id=role.id_role, permission_id=permission_id(code)))
        aid = session.scalar(select(AffectationSiteModel.id_affectation_site).where(AffectationSiteModel.utilisateur_id == a['user']))
        repo.ajouter(AffectationRole(affectation_site_id=aid, role_id=role.id_role))
        session.commit()
    finally:
        gen.close()


def root(a):
    return f'/api/catalogue/organisations/{a["org"]}'


def post(c, a, path, body, status=201):
    r = c.post(root(a)+path, json=body)
    assert r.status_code == status, r.text
    return r.json()


def basic(c, a):
    category = post(c, a, '/categories', {'code':'med', 'nom':'Médicaments'})
    form = post(c, a, '/formes', {'code':'cp', 'nom':'Comprimé'})
    lab = post(c, a, '/laboratoires', {'code':'lab', 'nom':'Laboratoire test'})
    data = {'nom':'Produit test', 'categorie_id':category['id_categorie'], 'forme_id':form['id_forme'], 'laboratoire_id':lab['id_laboratoire'], 'premier_conditionnement':{'code':'B20', 'libelle':'Boîte de 20'}}
    product = post(c, a, '/produits', data)
    return category, data, product


def test_domaine_uuid_references_et_cycles():
    org = uuid4()
    ref = ReferenceProduit(organisation_id=org, conditionnement_id=uuid4(), type_reference=TypeReference.CIP7, valeur=' 0012345 ')
    assert ref.valeur == '0012345' and ref.id_reference != ref.conditionnement_id
    with pytest.raises(ValueError):
        Conditionnement(organisation_id=org, produit_id=uuid4(), code=' ', libelle='Boîte')
    with pytest.raises(ValueError):
        CategorieProduit(organisation_id=org, code='x', nom='X', id_categorie=org, parent_id=org)
    top = CategorieProduit(organisation_id=org, code='top', nom='Racine')
    child = CategorieProduit(organisation_id=org, code='child', nom='Enfant', parent_id=top.id_categorie)
    rows = {top.id_categorie:top, child.id_categorie:child}
    with pytest.raises(ValueError, match='Cycle'):
        verifier_hierarchie(replace(top, parent_id=child.id_categorie), rows.get)
    with pytest.raises(ValueError, match='autre organisation'):
        verifier_hierarchie(replace(child, organisation_id=uuid4()), rows.get)


def test_parcours_catalogue_conditionnements_references_recherche_et_modification(raw_client, account):
    c, a = raw_client, account; grant(c,a); assert login(c,a).status_code == 200
    category, data, product = basic(c,a)
    second = post(c,a,f'/produits/{product["id_produit"]}/conditionnements',{'code':'B60','libelle':'Boîte de 60'})
    first = product['conditionnements'][0]['id_conditionnement']
    reference = post(c,a,f'/conditionnements/{first}/references',{'type_reference':'CIP7','valeur':'0012345'})
    post(c,a,f'/conditionnements/{first}/references',{'type_reference':'HISTORIQUE','valeur':'OLD-55'})
    post(c,a,f'/conditionnements/{second["id_conditionnement"]}/references',{'type_reference':'CIP13','valeur':'0000123456789'})
    duplicate = c.post(root(a)+f'/conditionnements/{second["id_conditionnement"]}/references',json={'type_reference':'CIP7','valeur':'0012345'})
    assert duplicate.status_code == 409
    assert c.get(root(a)+'/produits',params={'q':'OLD-55'}).json()['items'][0]['id_produit'] == product['id_produit']
    assert c.get(root(a)+'/produits',params={'q':'absent'}).json()['items'] == []
    data.pop('premier_conditionnement');data['nom']='Produit modifié'
    updated = c.put(root(a)+f'/produits/{product["id_produit"]}',json=data)
    assert updated.status_code == 200 and updated.json()['nom'] == 'PRODUIT MODIFIÉ'
    assert len(updated.json()['conditionnements']) == 2
    assert sum(len(x['references']) for x in updated.json()['conditionnements']) == 3
    r = c.put(root(a)+f'/references/{reference["id_reference"]}',json={'type_reference':'CIP7','valeur':'0012345','actif':False})
    assert r.status_code == 200 and r.json()['valeur'] == '0012345' and not r.json()['actif']
    assert c.get(root(a)+'/produits',params={'q':'0012345'}).json()['items']
    assert c.post(root(a)+'/produits',json=data).status_code == 422
    assert c.post(root(a)+'/produits',json={**data,'premier_conditionnement':{'code':'X','libelle':'X'},'cip7':'1234567'}).status_code == 422


def test_categories_hierarchie_et_rollback_sur_cycle(raw_client, account):
    c,a=raw_client,account;grant(c,a);login(c,a)
    top, data, product=basic(c,a)
    child=post(c,a,'/categories',{'code':'child','nom':'Enfant','parent_id':top['id_categorie']})
    leaf=post(c,a,'/categories',{'code':'leaf','nom':'Feuille','parent_id':child['id_categorie']})
    data.pop('premier_conditionnement');data['categorie_id']=leaf['id_categorie']
    r=c.put(root(a)+f'/produits/{product["id_produit"]}',json=data)
    assert [x['id_categorie'] for x in r.json()['categories']] == [leaf['id_categorie'],child['id_categorie'],top['id_categorie']]
    assert c.put(root(a)+f'/categories/{top["id_categorie"]}',json={'code':'med','nom':'Racine','parent_id':leaf['id_categorie']}).status_code==422
    assert next(x for x in c.get(root(a)+'/categories').json() if x['id_categorie']==top['id_categorie'])['parent_id'] is None
    assert c.post(root(a)+'/categories',json={'code':' MED ','nom':'Doublon'}).status_code==409


@pytest.mark.parametrize('state',['unauthenticated','no_permission','no_assignment','wrong_site','inactive','expired','future','no_role','missing_csrf','invalid_csrf','no_location'])
def test_toutes_routes_catalogue_refusent_http_direct(raw_client,account,state):
    c,a=raw_client,account
    if state!='unauthenticated':
        grant(c,a);login(c,a)
        if state=='no_permission':
            gen=db(c);session=next(gen)
            try:
                from sqlalchemy import delete
                session.execute(delete(RolePermissionModel).where(RolePermissionModel.permission_id.in_([permission_id('catalogue.consulter'),permission_id('catalogue.gerer')])));session.commit()
            finally:gen.close()
        elif state in ('missing_csrf','invalid_csrf'):
            c.headers.pop('X-CSRF-Token')
            if state=='invalid_csrf':c.headers['X-CSRF-Token']='incorrect'
        else:
            set_state(c,a,state)
            if state=='no_location':c.headers['X-Emplacement-ID']=str(a['location'])
    paths=c.get('/openapi.json').json()['paths']
    for template,methods in paths.items():
        if not template.startswith('/api/catalogue/'):continue
        path=template.replace('{organisation_id}',str(a['org'])).replace('{identifiant}',str(uuid4()))
        for method in methods:
            if state in ('missing_csrf','invalid_csrf') and method=='get':continue
            r=c.request(method,path,json={} if method!='get' else None)
            assert r.status_code==(401 if state=='unauthenticated' else 403),(state,method,path,r.text)
    gen=db(c);session=next(gen)
    try:assert session.scalar(select(func.count()).select_from(ProduitModel))==0
    finally:gen.close()


def test_consultation_sans_mutation_et_permission_site_sans_emplacement(raw_client,account):
    c,a=raw_client,account;grant(c,a,('catalogue.consulter',));login(c,a);set_state(c,a,'no_location')
    assert c.get(root(a)+'/produits').status_code==200
    assert c.post(root(a)+'/categories',json={'code':'X','nom':'X'}).status_code==403
    c.headers['X-Emplacement-ID']=str(a['other_location'])
    assert c.get(root(a)+'/produits').status_code==403


def test_isolation_http_et_contraintes_sql_references(raw_client,account):
    c,a=raw_client,account;grant(c,a);login(c,a);cat,data,prod=basic(c,a)
    gen=db(c);session=next(gen)
    try:
        other=uuid4();foreign_cat=uuid4();foreign_prod=uuid4();foreign_pack=uuid4()
        session.add(OrganisationModel(id_organisation=other,nom_commercial='Autre',raison_sociale='Autre',actif=True));session.flush()
        session.add(CategorieProduitModel(id_categorie=foreign_cat,organisation_id=other,code='MED',nom='Autre',actif=True));session.flush()
        session.add(ProduitModel(id_produit=foreign_prod,organisation_id=other,categorie_id=foreign_cat,nom='Autre',actif=True));session.flush()
        session.add(ConditionnementModel(id_conditionnement=foreign_pack,organisation_id=other,produit_id=foreign_prod,code='B20',libelle='Autre',actif=True));session.commit()
        for invalid in [ProduitModel(id_produit=uuid4(),organisation_id=a['org'],categorie_id=foreign_cat,nom='Interdit',actif=True),ConditionnementModel(id_conditionnement=uuid4(),organisation_id=a['org'],produit_id=foreign_prod,code='X',libelle='Interdit',actif=True),ReferenceProduitModel(id_reference=uuid4(),organisation_id=a['org'],conditionnement_id=foreign_pack,type_reference='CIP7',valeur='1234567',actif=True)]:
            session.add(invalid)
            with pytest.raises(IntegrityError):session.flush()
            session.rollback()
        repo=SqlAlchemyCatalogueRepository(session);service=CatalogueService(repo)
        item=Produit(organisation_id=a['org'],nom='Sans conditionnement',categorie_id=UUID(cat['id_categorie']))
        with pytest.raises(ValueError,match='premier conditionnement'):service.enregistrer(item)
        assert repo.obtenir(Produit,item.id_produit,a['org']) is None
        first=prod['conditionnements'][0]['id_conditionnement']
        # Same type/value across organizations is legal; both UUIDs stay distinct.
        for org,pid in ((a['org'],UUID(first)),(other,foreign_pack)):
            service.enregistrer(ReferenceProduit(organisation_id=org,conditionnement_id=pid,type_reference='CIP7',valeur='0012345'))
    finally:gen.close()
    assert c.get(root({**a,'org':other})+'/produits').status_code==403
    assert c.get(root(a)+f'/produits/{foreign_prod}').status_code==404
    assert len(c.get(root(a)+'/produits').json()['items'])==1
    assert c.post(root(a)+'/produits',json={**data,'categorie_id':str(foreign_cat)}).status_code==404
    assert c.post(root(a)+f'/conditionnements/{foreign_pack}/references',json={'type_reference':'CIP7','valeur':'5555555'}).status_code==404


def test_migration_catalogue_retour_p1_conserve_droits(tmp_path,monkeypatch):
    import os
    from alembic import command
    from alembic.config import Config
    from sqlalchemy import create_engine,inspect,text
    from neosys_pharma.infrastructure.config import get_settings
    url=os.getenv('TEST_MIGRATION_DATABASE_URL',f'sqlite+pysqlite:///{tmp_path / "p2.db"}')
    monkeypatch.setenv('DATABASE_URL',url);get_settings.cache_clear();cfg=Config('alembic.ini')
    try:
        command.upgrade(cfg,'head');command.check(cfg);engine=create_engine(url)
        with engine.connect() as connection:
            before=connection.execute(text('SELECT role_id, permission_id FROM roles_permissions ORDER BY role_id, permission_id')).all()
            assert connection.execute(text("SELECT count(*) FROM roles_permissions JOIN permissions ON permissions.id_permission=roles_permissions.permission_id WHERE permissions.code LIKE 'catalogue.%'")).scalar()==0
        command.downgrade(cfg,'20261007_04')
        assert not any(name.startswith('catalogue_') for name in inspect(engine).get_table_names())
        with engine.connect() as connection:
            assert connection.execute(text('SELECT role_id, permission_id FROM roles_permissions ORDER BY role_id, permission_id')).all()==before
            assert connection.execute(text('SELECT count(*) FROM permissions')).scalar()==7
        command.upgrade(cfg,'head');command.check(cfg)
        assert set(inspect(engine).get_table_names()) >= {'catalogue_produits','catalogue_conditionnements','catalogue_references'}
        engine.dispose()
    finally:get_settings.cache_clear()


def test_modifications_et_doublon_reference_preservent_etat(raw_client,account):
    c,a=raw_client,account;grant(c,a);login(c,a);cat,data,prod=basic(c,a)
    for path,id_field in (('categories','id_categorie'),('formes','id_forme'),('laboratoires','id_laboratoire')):
        row=c.get(root(a)+'/'+path).json()[0]
        result=c.put(root(a)+f'/{path}/{row[id_field]}',json={'code':row['code'],'nom':row['nom']+' modifié','actif':False})
        assert result.status_code==200 and result.json()[id_field]==row[id_field] and not result.json()['actif']
    pid=prod['conditionnements'][0]['id_conditionnement']
    one=post(c,a,f'/conditionnements/{pid}/references',{'type_reference':'CIP7','valeur':'0012345'})
    two=post(c,a,f'/conditionnements/{pid}/references',{'type_reference':'CIP7','valeur':'0012346'})
    assert c.put(root(a)+f'/references/{two["id_reference"]}',json={'type_reference':'CIP7','valeur':'0012345'}).status_code==409
    detail=c.get(root(a)+f'/produits/{prod["id_produit"]}').json()
    assert sorted(r['valeur'] for r in detail['conditionnements'][0]['references'])==['0012345','0012346']
    assert c.put(root(a)+f'/conditionnements/{pid}',json={'code':'B20','libelle':'Autre','produit_id':str(uuid4())}).status_code==422
    assert c.put(root(a)+f'/references/{one["id_reference"]}',json={'type_reference':'CIP7','valeur':'0012345','conditionnement_id':str(uuid4())}).status_code==422


def test_permission_gestion_ne_confere_pas_consultation(raw_client,account):
    c,a=raw_client,account;grant(c,a,('catalogue.gerer',));login(c,a)
    post(c,a,'/categories',{'code':'X','nom':'Gestion explicite'})
    assert c.get(root(a)+'/categories').status_code==403
    assert c.get(root(a)+'/produits').status_code==403


def test_reparentages_concurrents_postgresql_ne_creent_pas_cycle(raw_client,account):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier
    c,a=raw_client,account
    gen=db(c);session=next(gen)
    try:
        if session.bind.dialect.name!='postgresql':pytest.skip('Verrou de hiérarchie PostgreSQL')
    finally:gen.close()
    grant(c,a);login(c,a)
    x=post(c,a,'/categories',{'code':'A','nom':'A'})
    y=post(c,a,'/categories',{'code':'B','nom':'B'})
    start=Barrier(2)
    def reparent(item,other):
        gen=db(c);session=next(gen)
        try:
            service=CatalogueService(SqlAlchemyCatalogueRepository(session))
            category=CategorieProduit(organisation_id=a['org'],id_categorie=UUID(item['id_categorie']),parent_id=UUID(other['id_categorie']),code=item['code'],nom=item['nom'])
            start.wait(timeout=10)
            try:service.enregistrer(category);return 'ok'
            except ValueError:return 'cycle'
        finally:gen.close()
    with ThreadPoolExecutor(max_workers=2) as pool:
        tasks=[pool.submit(reparent,x,y),pool.submit(reparent,y,x)]
        assert sorted(task.result(timeout=20) for task in tasks)==['cycle','ok']
    rows=c.get(root(a)+'/categories').json()
    assert sum(row['parent_id'] is not None for row in rows)==1


def test_liste_paginee_milliers_produits_sans_chargement_details(raw_client, account):
    from sqlalchemy import insert, event
    c, a = raw_client, account; grant(c, a); login(c, a)
    cat, data, prod = basic(c, a)
    gen = db(c); session = next(gen)
    try:
        produits = [dict(id_produit=uuid4(), organisation_id=a['org'], categorie_id=UUID(cat['id_categorie']), nom=f'Référence {i:04d}', actif=True) for i in range(1200)]
        session.execute(insert(ProduitModel), produits)
        session.execute(insert(ConditionnementModel), [dict(id_conditionnement=uuid4(), organisation_id=a['org'], produit_id=p['id_produit'], code='B', libelle='Boîte', actif=True) for p in produits])
        session.commit()
        queries = []
        def capture(conn, cursor, statement, params, context, many): queries.append(statement)
        event.listen(session.bind, 'before_cursor_execute', capture)
        try:
            result = SqlAlchemyCatalogueRepository(session).rechercher_produits(a['org'], '', 2, 25)
            assert result['total'] == 1201 and len(result['items']) == 25
            assert len(queries) == 2  # constant query count, independent of catalogue size
            assert not any(isinstance(entity, ProduitModel) for entity in session.identity_map.values())
        finally: event.remove(session.bind, 'before_cursor_execute', capture)
    finally: gen.close()
    first = c.get(root(a)+'/produits').json()
    second = c.get(root(a)+'/produits', params={'page': 2}).json()
    assert first['total'] == second['total'] == 1201
    assert len(first['items']) == len(second['items']) == 25
    assert not ({x['id_produit'] for x in first['items']} & {x['id_produit'] for x in second['items']})
    assert c.get(root(a)+'/produits', params={'page': 999}).json()['items'] == []
    assert len(c.get(root(a)+'/produits', params={'page_size': 100}).json()['items']) == 100


@pytest.mark.parametrize('params', [{'page': 0}, {'page': -1}, {'page': 1_000_001}, {'page_size': 0}, {'page_size': 101}, {'q': 'x'*201}])
def test_parametres_pagination_bornes(raw_client, account, params):
    c, a = raw_client, account; grant(c, a); login(c, a)
    assert c.get(root(a)+'/produits', params=params).status_code == 422


def test_recherche_sql_litterale_references_secondaires_et_resume_unique(raw_client, account):
    c, a = raw_client, account; grant(c, a); login(c, a)
    cat, data, prod = basic(c, a)
    first = prod['conditionnements'][0]['id_conditionnement']
    second = post(c, a, f'/produits/{prod["id_produit"]}/conditionnements', {'code': 'B60', 'libelle': 'Boîte de 60'})
    for pid, typ, value, active in [(first, 'CIP7', '0001234', True), (first, 'HISTORIQUE', 'Ancien-%_\\-A', False), (second['id_conditionnement'], 'GTIN', 'SECOND-0001234', True)]:
        post(c, a, f'/conditionnements/{pid}/references', {'type_reference': typ, 'valeur': value, 'actif': active})
    for term in ['pRODUIT', '0001234', 'second-', 'ancien-%_\\-a']:
        result = c.get(root(a)+'/produits', params={'q': term, 'page_size': 1}).json()
        assert result['total'] == 1 and len(result['items']) == 1
        row = result['items'][0]
        assert row['id_produit'] == prod['id_produit'] and row['nombre_conditionnements'] == 2
        assert (row['categorie'], row['forme'], row['laboratoire']) == ('MÉDICAMENTS', 'COMPRIMÉ', 'LABORATOIRE TEST')
        assert row['reference'] == '0001234' and row['conditionnement'] == 'BOÎTE DE 20'
        assert 'conditionnements' not in row  # details fetched only on demand
    assert c.get(root(a)+'/produits', params={'q': '%'}).json()['total'] == 1
    assert c.get(root(a)+'/produits', params={'q': 'absent_%'}).json()['total'] == 0
    # Stable order when names are identical; products without optional classifications/references stay visible.
    other = post(c, a, '/produits', {'nom': 'Produit test', 'categorie_id': cat['id_categorie'], 'premier_conditionnement': {'code': 'X', 'libelle': 'Unité'}})
    ids = [c.get(root(a)+'/produits', params={'page': i, 'page_size': 1}).json()['items'][0]['id_produit'] for i in (1, 2)]
    assert ids == sorted([prod['id_produit'], other['id_produit']])
    blank = next(x for x in c.get(root(a)+'/produits').json()['items'] if x['id_produit'] == other['id_produit'])
    assert blank['reference'] is None and blank['forme'] is None and blank['laboratoire'] is None


def test_reference_affichee_appartient_au_conditionnement_affiche(raw_client, account):
    c, a = raw_client, account; grant(c, a); login(c, a)
    cat, data, prod = basic(c, a)
    second = post(c, a, f'/produits/{prod["id_produit"]}/conditionnements', {'code': 'B60', 'libelle': 'Boîte de 60'})
    post(c, a, f'/conditionnements/{second["id_conditionnement"]}/references', {'type_reference': 'CIP13', 'valeur': 'SECONDAIRE'})
    result = c.get(root(a)+'/produits', params={'q': 'secondaire'}).json()
    assert result['total'] == 1
    assert result['items'][0]['conditionnement'] == 'BOÎTE DE 20'
    assert result['items'][0]['reference'] is None  # Never pair B60's reference with B20.
    detail = c.get(root(a)+f'/produits/{prod["id_produit"]}').json()
    assert detail['conditionnements'][1]['references'][0]['valeur'] == 'SECONDAIRE'
