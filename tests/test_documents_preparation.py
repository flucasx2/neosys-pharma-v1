"""P4.6.3 PDF historiques, isolation, cycles et concurrence ciblée."""
from io import BytesIO
from uuid import UUID,uuid4
from datetime import datetime,timezone
import hashlib,os
from concurrent.futures import ThreadPoolExecutor
import pytest
from pypdf import PdfReader
from sqlalchemy import select,text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session
from test_vente import raw_client,account,db,setup,create,line,root,stocks
from neosys_pharma.infrastructure.vente_models import DocumentPreparationModel
from neosys_pharma.infrastructure.organisation_models import SiteModel
from neosys_pharma.application.stock_service import StockService
from neosys_pharma.application.vente_service import VenteService
from neosys_pharma.application.document_preparation_service import DocumentPreparationService

def edition(c,a,v,key=None):
    r=c.post(root(a)+f'/{v["id"]}/documents',json={'cle':str(key or uuid4()),'revision':v['revision']})
    assert r.status_code==201,r.text;return r.json()

def test_documents_revisions_octets_historique_immutabilite(raw_client,account,tmp_path):
    c,a=raw_client,account;prod,pack,pid,_=setup(c,a);v=line(c,a,create(c,a,pid),prod,pack,2)
    before=stocks(c,a);key=uuid4();d=edition(c,a,v,key)
    assert edition(c,a,v,key)==d and edition(c,a,v)['id']==d['id']
    path=root(a)+f'/documents/{d["id"]}/pdf';p=c.get(path)
    assert p.status_code==200 and hashlib.sha256(p.content).hexdigest()==d['pdf_sha256']
    txt=''.join(x.extract_text() for x in PdfReader(BytesIO(p.content)).pages)
    assert 'PRÉPARATION — NON ACQUITTÉE' in txt and v['lignes'][0]['designation'] in txt
    assert 'Allocations' in txt and 'ACTIVE' in txt
    (tmp_path/'preparation.pdf').write_bytes(p.content)
    assert c.get(root(a)+f'/{v["id"]}').json()==v and stocks(c,a)==before
    gen=db(c);s=next(gen)
    try:
        s.get(SiteModel,a['site']).nom='SITE MODIFIÉ APRÈS ÉDITION';s.commit()
        for query in ('UPDATE vente_documents_preparation SET revision_vente=999','DELETE FROM vente_documents_preparation'):
            with pytest.raises(DBAPIError):s.execute(text(query));s.commit()
            s.rollback()
    finally:gen.close()
    v=line(c,a,v,prod,pack,1);new=edition(c,a,v)
    assert new['id']!=d['id'] and c.get(path).content==p.content
    listed=c.get(root(a)+f'/{v["id"]}/documents',params={'page_size':1}).json()
    assert listed['total']==2 and len(listed['items'])==1
    assert 'instantane' not in listed['items'][0] and 'pdf' not in listed['items'][0]
    c.headers.pop('X-CSRF-Token')
    assert c.post(root(a)+f'/{v["id"]}/documents',json={'cle':str(uuid4()),'revision':v['revision']}).status_code==403
    c.headers['X-Site-ID']=str(a['other']);assert c.get(path).status_code==403

def test_document_revision_obsolete_et_rollback_pdf(raw_client,account,monkeypatch):
    c,a=raw_client,account;prod,pack,pid,_=setup(c,a);v=line(c,a,create(c,a,pid),prod,pack,1)
    path=root(a)+f'/{v["id"]}/documents';before=stocks(c,a)
    assert c.post(path,json={'cle':str(uuid4()),'revision':1}).status_code==409
    def fail(_):raise ValueError('Génération PDF indisponible')
    monkeypatch.setattr('neosys_pharma.application.document_preparation_service.document_pdf',fail)
    assert c.post(path,json={'cle':str(uuid4()),'revision':v['revision']}).status_code==422
    assert c.get(path).json()['total']==0 and stocks(c,a)==before

def test_migration_document_preparation_cycle(tmp_path,monkeypatch):
    from alembic import command
    from alembic.config import Config
    from neosys_pharma.infrastructure.config import get_settings
    url=os.getenv('TEST_MIGRATION_DATABASE_URL',f'sqlite:///{tmp_path / "documents.db"}')
    monkeypatch.setenv('DATABASE_URL',url);get_settings.cache_clear();cfg=Config('alembic.ini')
    try:
        command.upgrade(cfg,'head');command.check(cfg)
        command.downgrade(cfg,'f22f6abb13c5');command.upgrade(cfg,'head');command.check(cfg)
    finally:get_settings.cache_clear()

def test_editions_concurrentes_postgresql(raw_client,account):
    c,a=raw_client,account;prod,pack,pid,_=setup(c,a);v=line(c,a,create(c,a,pid),prod,pack,1)
    gen=db(c);s=next(gen);engine=s.get_bind();gen.close()
    if engine.dialect.name!='postgresql':pytest.skip('Concurrence réelle PostgreSQL')
    def worker(_):
        with Session(engine) as session:
            stock=StockService(session,a['org'],a['user'],lambda *args:None);vente=VenteService(stock,a['site'])
            return stock.operation(uuid4(),'P46:DOCUMENT',{},lambda:DocumentPreparationService(vente).editer(UUID(v['id']),v['revision']))['id']
    with ThreadPoolExecutor(max_workers=2) as pool:ids=list(pool.map(worker,[0,1]))
    assert ids[0]==ids[1] and c.get(root(a)+f'/{v["id"]}/documents').json()['total']==1
