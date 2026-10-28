"""P5-C.2 : tests HTTP réels / SQL temporaires ; émission SQLite simulée explicitement."""
from copy import deepcopy
from datetime import date
from uuid import UUID,uuid4
from io import BytesIO
import pytest
from sqlalchemy import select,func,update
from sqlalchemy.exc import DBAPIError
from pypdf import PdfReader
from test_stock import raw_client,account,db,login
from test_p4p5_groupe_organismes import cible_isolee
from test_p5c_creances import prepare,realise,post as claim_post,complete
from test_p5a_tiers_payants import root
from test_vente import create,line,act
from test_p5b_3_encaissement_prise_en_charge import _post
from test_caisse import root as cash_root
from test_regularisation import grant45,ret
from neosys_pharma.domain.organisation.permissions_systeme import permission_id,P5C2_PERMISSIONS
from neosys_pharma.infrastructure.securite_models import RoleModel,RolePermissionModel
from neosys_pharma.infrastructure.tiers_payants_models import VerificationConventionModel
from neosys_pharma.application.stock_service import serial
from neosys_pharma.infrastructure.facturation_organisme_models import (
    PreparationOrganismeModel,VersionPreparationOrganismeModel,DocumentOrganismeModel,EngagementCreanceModel,LigneDocumentOrganismeModel,RegroupementDocumentsModel)
pytest_plugins=('test_vente',)


def post(c,a,path,body,status=200,key=None):return _post(c,root(a)+'/documents'+path,{'cle':str(key or uuid4()),**body},status)


def validate_claim(c,a,claim):
    x=claim_post(c,a,f"/{claim['id']}/complements",{'revision':claim['dossier']['revision'],'complements':complete(claim),'motif':'Pièces de recette'})
    return claim_post(c,a,f"/{claim['id']}/verifier",{'revision':x['dossier']['revision'],'conforme':True,'motif':'Dossier vérifié'})


def ready(c,a,second=False):
    sale,session,calc=prepare(c,a);real,enc=realise(c,a,sale,session,calc)
    claims=claim_post(c,a,'',{'realisation_id':real['id']},201)['creances'];claim=validate_claim(c,a,claims[0]);result=[claim]
    gen=db(c);s=next(gen)
    try:
        role=s.scalar(select(RoleModel).where(RoleModel.organisation_id==a['org'],RoleModel.code=='CATALOGUE'))
        for code,_ in P5C2_PERMISSIONS:s.add(RolePermissionModel(role_id=role.id_role,permission_id=permission_id(code)))
        proof_rows=[serial(x) for x in s.scalars(select(VerificationConventionModel).where(VerificationConventionModel.vente_id==UUID(sale['id'])))]
        s.commit()
    finally:gen.close()
    login(c,a)
    if second:
        product=sale['lignes'][0]
        v=line(c,a,create(c,a,sale['poste_id'],mode='MUTUELLE',client_id=sale['client_id']),product['produit_id'],product['conditionnement_id'],3)
        v=act(c,a,v,'valider');v=act(c,a,v,'transmettre',caisse_id=session['caisse_id'])
        for proof in proof_rows:
            data={k:proof[k] for k in ('adhesion_id','beneficiaire_id','revision_adhesion','source','reference','resultat','motif','date_verification','date_fin','valeurs','documents')}
            _post(c,root(a)+f"/ventes/{v['id']}/verifications",{'cle':str(uuid4()),**data},201)
        calculated=_post(c,root(a)+f"/ventes/{v['id']}/prise-en-charge/confirmer",{'cle':str(uuid4()),'revision':v['revision'],'beneficiaire_id':calc['beneficiaire_id']},201)
        session2=c.get(cash_root(a)+'/sessions').json()['items'][0]
        real2,_=realise(c,a,v,session2,calculated)
        cc=claim_post(c,a,'',{'realisation_id':real2['id']},201)['creances']
        result.append(validate_claim(c,a,next(x for x in cc if x['organisme_id']==claim['organisme_id'])))
    return result,claims,enc


def body(claims,genre='FACTURE',presentation_id=None):
    return {'genre':genre,'organisme_id':claims[0]['organisme_id'],'convention_id':claims[0]['snapshot']['lignes'][0]['etape']['convention_id'],
        'date_debut':str(date.today()),'date_fin':str(date.today()),'selection':[{'creance_id':x['id'],'revision':x['dossier']['revision']} for x in claims],
        'presentation_id':presentation_id,'motif':'Préparation fictive contrôlée'}


def emit(c,a,draft,monkeypatch,reference):
    from neosys_pharma.application import facturation_organisme_service as module
    # Cette substitution est limitée aux tests SQLite, pas une preuve du garde natif.
    gen=db(c);session=next(gen)
    try:is_sqlite=session.get_bind().dialect.name=='sqlite'
    finally:gen.close()
    if is_sqlite:monkeypatch.setattr(module,'emission_isolee_autorisee',lambda stock:True)
    else:
        monkeypatch.setenv('CI','true');monkeypatch.setenv('P5C2_DISPOSABLE_EMISSION','1')
    ident=draft['preparation']['id']
    verified=post(c,a,f'/preparations/{ident}/valider',{'revision':draft['version']['revision'],'motif':'Contrôle du groupe'})
    key=uuid4();data={'revision':verified['version']['revision'],'reference':reference,'reference_validation':'PROTOCOLE-FICTIF','motif':'Émission isolée fictive'}
    output=post(c,a,f'/preparations/{ident}/emettre',data,key=key)
    assert post(c,a,f'/preparations/{ident}/emettre',data,key=key)==output
    return output


def test_regroupement_multi_creances_bordereau_facture_pdf_historique(raw_client,account,monkeypatch,tmp_path):
    c,a=raw_client,account;claims,_,enc=ready(c,a,True)
    from neosys_pharma.infrastructure.caisse_models import EncaissementModel,MouvementCaisseModel,JournalFideliteModel
    from neosys_pharma.infrastructure.stock_models import MouvementStockModel
    def finance_counts():
        gen=db(c);s=next(gen)
        try:return [s.scalar(select(func.count()).select_from(cls)) for cls in (EncaissementModel,MouvementCaisseModel,JournalFideliteModel,MouvementStockModel)]
        finally:gen.close()
    initial_finance=finance_counts()
    key=uuid4();payload=body(claims,'BORDEREAU');draft=post(c,a,'/preparations',payload,201,key)
    assert post(c,a,'/preparations',payload,201,key)==draft
    ident=draft['preparation']['id'];assert draft['document'] is None
    preview=c.get(root(a)+f'/documents/preparations/{ident}/previsualisation.pdf',params={'revision':1})
    assert preview.status_code==200,preview.text
    (tmp_path/'brouillon-organisme.pdf').write_bytes(preview.content)
    text=''.join(p.extract_text() for p in PdfReader(BytesIO(preview.content)).pages)
    assert 'BROUILLON' in text and 'NON EMIS' in text and str(sum(x['montant_xaf'] for x in claims)) in text
    post(c,a,'/preparations',payload,409)
    emitted=emit(c,a,draft,monkeypatch,'BOR/TEST/001');doc=emitted['document'];assert doc['total_xaf']==sum(x['montant_xaf'] for x in claims)
    assert all(line['montant_xaf']==c.get(root(a)+f"/creances/{line['reference']}").json()['solde_effectif_xaf']
        for line in emitted['document']['snapshot']['lignes'])
    (tmp_path/'bordereau-organisme-recette.pdf').write_bytes(c.get(root(a)+f"/documents/emis/{emitted['document']['id']}/pdf").content)
    invoice=post(c,a,'/preparations',body(claims,'FACTURE',ident),201)
    invoice=emit(c,a,invoice,monkeypatch,'FAC/TEST/001');doc=invoice['document']
    assert doc['snapshot']['presentation_id']==emitted['document']['id']
    pdf=c.get(root(a)+f"/documents/emis/{doc['id']}/pdf");assert pdf.status_code==200
    assert c.get(root(a)+f"/documents/emis/{doc['id']}/pdf").content==pdf.content
    text=''.join(p.extract_text() for p in PdfReader(BytesIO(pdf.content)).pages)
    assert 'FACTURE ORGANISME' in text and 'RECETTE ISOLEE' in text and 'FAC/TEST/001' in text
    (tmp_path/'facture-organisme-recette.pdf').write_bytes(pdf.content)
    assert all(c.get(root(a)+f"/creances/{x['id']}").json()['dossier']['etat']=='FACTURE' for x in claims)
    post(c,a,'/preparations',body(claims),409)
    recap=post(c,a,'/regroupements',{'genre':'RECAPITULATIF','ids':[doc['id']],'motif':'Envoi facultatif'},201)
    lot=post(c,a,'/regroupements',{'genre':'LOT','ids':[recap['id']],'motif':'Lot facultatif'},201)
    assert recap['total_xaf']==lot['total_xaf']==doc['total_xaf']
    for name,record in [('recapitulatif',recap),('lot',lot)]:
        (tmp_path/(name+'-organisme-recette.pdf')).write_bytes(c.get(root(a)+f"/documents/regroupements/{record['id']}/pdf").content)
    assert finance_counts()==initial_finance
    # Les libellés courants ne réécrivent jamais une pièce déjà émise.
    from neosys_pharma.infrastructure.organisation_models import OrganisationModel
    from sqlalchemy import delete
    gen=db(c);s=next(gen)
    try:
        s.get(OrganisationModel,a['org']).nom_commercial='Pharmacie fictive renommée';s.commit()
        with pytest.raises(DBAPIError,match='emis|émis'):
            s.execute(delete(EngagementCreanceModel).where(EngagementCreanceModel.preparation_id==UUID(invoice['preparation']['id'])));s.commit()
        s.rollback()
    finally:gen.close()
    assert c.get(root(a)+f"/documents/emis/{doc['id']}/pdf").content==pdf.content
    assert c.get(root(a)+'/documents/regroupements',params={'page_size':1}).json()['total']==2
    assert c.get(root(a)+'/documents/preparations',params={'creance_id':claims[0]['id']}).json()['total']==2
    assert c.get(root(a)+'/documents/regroupements',params={'document_id':doc['id']}).json()['total']==2
    assert c.get(root(a)+'/documents/regroupements',params={'document_id':str(uuid4())}).json()['total']==0
    post(c,a,'/regroupements',{'genre':'RECAPITULATIF','ids':[doc['id']],'motif':'Doublon'},409)
    history=c.get(root(a)+f'/documents/preparations/{ident}/historique').json()
    assert [x['etat'] for x in history['items']]==['EMISE','VALIDEE','PREPARATION']


def test_dossiers_incomplets_modifies_retours_refuses_et_retrait(raw_client,account):
    c,a=raw_client,account;claims,allclaims,enc=ready(c,a)
    # Simulation : aucune créance sélectionnable, UUID source n'est pas une créance.
    bad=body(claims);bad['selection'][0]['creance_id']=claims[0]['realisation_id'];post(c,a,'/preparations',bad,404)
    post(c,a,'/preparations',body([allclaims[1]]),409)
    wrong=body(claims);wrong['organisme_id']=allclaims[1]['organisme_id'];post(c,a,'/preparations',wrong,422)
    draft=post(c,a,'/preparations',body(claims),201);ident=draft['preparation']['id']
    empty=post(c,a,f'/preparations/{ident}/selection',{'revision':1,'selection':[],'motif':'Retrait du dossier'})
    post(c,a,f'/preparations/{ident}/valider',{'revision':empty['version']['revision'],'motif':'Vide'},422)
    other=post(c,a,'/preparations',body(claims),201)
    post(c,a,f'/preparations/{ident}/selection',{'revision':1,'selection':[],'motif':'Périmé'},409)
    post(c,a,f"/preparations/{other['preparation']['id']}/abandonner",{'revision':1,'motif':'Abandon'},200)
    again=post(c,a,'/preparations',body(claims),201);ident=again['preparation']['id']
    claim_post(c,a,f"/{claims[0]['id']}/complements",{'revision':claims[0]['dossier']['revision'],'complements':{},'motif':'Pièce à reprendre'})
    post(c,a,f'/preparations/{ident}/valider',{'revision':1,'motif':'Révision documentaire périmée'},409)
    grant45(c,a);ret(c,a,enc,1)
    search=c.get(root(a)+'/documents/creances',params={'statut':'EN_ANOMALIE'});assert search.status_code==200,search.text
    assert search.json()['total']==2
    assert c.get(root(a)+'/documents/creances',params={'statut':'VALIDE_POUR_FACTURATION'}).json()['total']==0
    post(c,a,f'/preparations/{ident}/valider',{'revision':1,'motif':'Retour non compensé'},409)


def test_emission_fermee_par_defaut_permissions_csrf(raw_client,account):
    c,a=raw_client,account;claims,_,_=ready(c,a);draft=post(c,a,'/preparations',body(claims),201);ident=draft['preparation']['id']
    active=c.get(root(a)+'/documents/activation').json();assert active['emission_production_autorisee'] is False and active['emission_recette_autorisee'] is False
    valid=post(c,a,f'/preparations/{ident}/valider',{'revision':1,'motif':'Contrôle'})
    post(c,a,f'/preparations/{ident}/emettre',{'revision':valid['version']['revision'],'reference':'TEST/001','reference_validation':'QA','motif':'Fermé'},403)
    assert c.get(root(a)+'/documents/preparations').json()['total']==1
    assert c.get(root(a)+'/documents/preparations',headers={'X-Site-ID':str(uuid4())}).status_code==403
    assert c.get(root(a)+f'/documents/preparations/{ident}',headers={'X-Emplacement-ID':str(a['denied'])}).status_code==403
    assert c.get(root(a).replace(str(a['org']),str(uuid4()))+'/documents/preparations').status_code==403
    gen=db(c);s=next(gen)
    try:
        role=s.scalar(select(RoleModel).where(RoleModel.organisation_id==a['org'],RoleModel.code=='CATALOGUE'))
        s.delete(s.get(RolePermissionModel,(role.id_role,permission_id('tiers_payant.document.valider'))));s.commit()
    finally:gen.close()
    post(c,a,f'/preparations/{ident}/valider',{'revision':2,'motif':'Sans droit'},403)
    token=c.headers.pop('X-CSRF-Token',None)
    try:assert c.post(root(a)+'/documents/preparations',json={'cle':str(uuid4()),**body(claims)}).status_code==403
    finally:
        if token:c.headers['X-CSRF-Token']=token


def test_rollback_pdf_immuabilite_et_reference_unique(raw_client,account,monkeypatch):
    c,a=raw_client,account;claims,_,_=ready(c,a,True)
    one=post(c,a,'/preparations',body([claims[0]]),201);two=post(c,a,'/preparations',body([claims[1]]),201)
    first=emit(c,a,one,monkeypatch,'FAC/UNIQUE')
    second=post(c,a,f"/preparations/{two['preparation']['id']}/valider",{'revision':1,'motif':'Contrôle'})
    post(c,a,f"/preparations/{two['preparation']['id']}/emettre",{'revision':2,'reference':'FAC/UNIQUE','reference_validation':'QA','motif':'Doublon'},409)
    from neosys_pharma.application import facturation_organisme_service as mod
    original=mod.FacturationOrganismeService._version
    def fail(self,row,revision,etat,selection,motif):
        if etat=='EMISE':raise ValueError('Échec provoqué après document et lignes')
        return original(self,row,revision,etat,selection,motif)
    with monkeypatch.context() as m:
        m.setattr(mod.FacturationOrganismeService,'_version',fail)
        post(c,a,f"/preparations/{two['preparation']['id']}/emettre",{'revision':2,'reference':'FAC/ROLLBACK','reference_validation':'QA','motif':'Panne fictive'},422)
    gen=db(c);s=next(gen)
    try:
        assert s.scalar(select(func.count()).select_from(DocumentOrganismeModel))==1
        for cls,values in ((DocumentOrganismeModel,{'reference':'FAC/ALTERATION'}),(LigneDocumentOrganismeModel,{'montant_xaf':5}),(VersionPreparationOrganismeModel,{'motif':'Altération'})):
            with pytest.raises(DBAPIError,match='immuable'):s.execute(update(cls).values(**values));s.commit()
            s.rollback()
    finally:gen.close()
    assert c.get(root(a)+f"/creances/{claims[1]['id']}").json()['dossier']['etat']=='VALIDE_POUR_FACTURATION'


def test_modification_apres_validation_bloque_emission_et_listes_paginees(raw_client,account,monkeypatch):
    c,a=raw_client,account;claims,others,enc=ready(c,a)
    draft=post(c,a,'/preparations',body(claims),201);ident=draft['preparation']['id']
    post(c,a,f'/preparations/{ident}/valider',{'revision':1,'motif':'Contrôle explicite'})
    changed=claim_post(c,a,f"/{claims[0]['id']}/complements",{'revision':3,'complements':{},'motif':'Pièce retirée'})
    from neosys_pharma.application import facturation_organisme_service as module
    monkeypatch.setattr(module,'emission_isolee_autorisee',lambda stock:True)
    post(c,a,f'/preparations/{ident}/emettre',{'revision':2,'reference':'INTERDITE','reference_validation':'QA','motif':'Dossier invalide'},409)
    preview=c.get(root(a)+f'/documents/preparations/{ident}/previsualisation.pdf',params={'revision':2})
    assert preview.status_code==409,preview.text
    data=c.get(root(a)+'/documents/creances',params={'statut':'A_COMPLETER','organisme_id':claims[0]['organisme_id'],'page_size':1}).json()
    assert data['total']==1 and len(data['items'])==1 and data['items'][0]['id']==claims[0]['id']
    assert c.get(root(a)+'/documents/creances',params={'date_debut':'2099-01-01'}).json()['total']==0
    assert c.get(root(a)+'/documents/creances',params={'date_fin':'9999-12-31'}).status_code==422
    refs=c.get(root(a)+'/documents/organismes',params={'q':'fictif','page_size':1}).json()
    assert refs['total']==2 and len(refs['items'])==1
    assert c.get(root(a)+'/documents/organismes',params={'q':'inexistant'}).json()['total']==0


@pytest.mark.parametrize('operation',['preparer','emettre'])
def test_deux_operateurs_postgresql_native(raw_client,account,monkeypatch,operation):
    from threading import Event
    from concurrent.futures import ThreadPoolExecutor
    import time
    from sqlalchemy.orm import Session
    from sqlalchemy import text
    from neosys_pharma.application.stock_service import StockService
    from neosys_pharma.application.facturation_organisme_service import FacturationOrganismeService
    from neosys_pharma.domain.stock import ConflitStock
    gen=db(raw_client);session=next(gen);engine=session.get_bind();gen.close()
    if engine.dialect.name!='postgresql':pytest.skip('Deux transactions PostgreSQL natives indispensables ; non substituées par SQLite.')
    c,a=raw_client,account;claims,_,_=ready(c,a)
    from neosys_pharma.domain.organisation.securite import Utilisateur
    from neosys_pharma.infrastructure.provisionnement import provisionner
    from neosys_pharma.infrastructure.securite_repository import SqlAlchemySecuriteRepository
    from neosys_pharma.application.controle_acces import ControleAcces
    from test_authentification import PASSWORD
    second_author=uuid4()
    with Session(engine) as s:
        role=s.scalar(select(RoleModel).where(RoleModel.organisation_id==a['org'],RoleModel.code=='CATALOGUE'))
        provisionner(s,Utilisateur(id_utilisateur=second_author,organisation_id=a['org'],identifiant='agent-concurrent',nom='Second agent fictif'),
            [a['site']],[a['location']],[role.id_role],PASSWORD)
    payload=body(claims);payload['organisme_id']=UUID(payload['organisme_id']);payload['convention_id']=UUID(payload['convention_id'])
    payload['date_debut']=date.fromisoformat(payload['date_debut']);payload['date_fin']=date.fromisoformat(payload['date_fin'])
    ident=None
    if operation=='emettre':
        draft=post(c,a,'/preparations',body(claims),201);ident=UUID(draft['preparation']['id'])
        post(c,a,f'/preparations/{ident}/valider',{'revision':1,'motif':'Contrôle'})
        monkeypatch.setenv('CI','true');monkeypatch.setenv('P5C2_DISPOSABLE_EMISSION','1')
    held,release,started=Event(),Event(),Event();pids={}
    def worker(first):
        with Session(engine) as s:
            s.execute(text("SET LOCAL lock_timeout='8s'"));s.execute(text("SET LOCAL statement_timeout='10s'"))
            pids[first]=s.scalar(text('select pg_backend_pid()'))
            author=a['user'] if first else second_author
            repo=SqlAlchemySecuriteRepository(s);control=ControleAcces(repo,repo.utilisateur(author),date.today())
            stock=StockService(s,a['org'],author,control.verifier,date.today())
            if not first:started.set()
            def action():
                if first:
                    held.set()
                    if not release.wait(8):raise TimeoutError('Verrou non libéré')
                app=FacturationOrganismeService(stock,a['site'])
                return app.creer(payload) if ident is None else app.emettre(ident,2,'FAC/CONCURRENCE','PROTOCOLE-FICTIF','Émission concurrente')
            try:return stock.operation(uuid4(),'P5C2:CONCURRENCE',{'op':operation},action)
            except ConflitStock:return 'CONFLIT'
    pool=ThreadPoolExecutor(max_workers=2)
    try:
        one=pool.submit(worker,True);assert held.wait(5)
        two=pool.submit(worker,False);assert started.wait(5)
        assert pids[True]!=pids[False];blocked=False;deadline=time.monotonic()+5
        while time.monotonic()<deadline:
            with engine.connect() as probe:blocked=pids[True] in probe.scalar(text('select pg_blocking_pids(:pid)'),{'pid':pids[False]})
            if blocked:break
            time.sleep(.05)
        assert blocked,'Contention réelle non observée'
        release.set();assert isinstance(one.result(timeout=12),dict);assert two.result(timeout=12)=='CONFLIT'
        with Session(engine) as s:
            assert s.scalar(select(func.count()).select_from(PreparationOrganismeModel))==1
            assert s.scalar(select(func.count()).select_from(DocumentOrganismeModel))==(1 if ident else 0)
            if ident:assert s.scalar(select(func.count()).select_from(LigneDocumentOrganismeModel))==1
    finally:release.set();pool.shutdown(wait=True,cancel_futures=True)


def test_conditions_activation_et_gardes_serveur_non_contournables(raw_client,account,monkeypatch):
    c,a=raw_client,account;claims,_,_=ready(c,a)
    # Le client ne peut pas fournir un drapeau dans le corps de création.
    post(c,a,'/preparations',body(claims)|{'activer':True},422)
    monkeypatch.setenv('CI','true');monkeypatch.setenv('P5C2_DISPOSABLE_EMISSION','1')
    # Les flags seuls ne suffisent pas : un moteur SQLite n'est jamais une base native autorisée.
    gen=db(c);s=next(gen)
    try:backend=s.get_bind().dialect.name
    finally:gen.close()
    if backend=='sqlite':assert c.get(root(a)+'/documents/activation').json()['emission_recette_autorisee'] is False
    else:
        monkeypatch.delenv('P4P5_CONFIRM_DATABASE',raising=False)
        assert c.get(root(a)+'/documents/activation').json()['emission_recette_autorisee'] is False


@pytest.mark.parametrize('niveau',['RECAPITULATIF','LOT'])
def test_retour_apres_facture_interdit_regroupement(raw_client,account,monkeypatch,niveau):
    c,a=raw_client,account;claims,_,enc=ready(c,a)
    draft=post(c,a,'/preparations',body(claims),201);issued=emit(c,a,draft,monkeypatch,'FAC/RETOUR')
    doc=issued['document'];source=doc['id']
    if niveau=='LOT':source=post(c,a,'/regroupements',{'genre':'RECAPITULATIF','ids':[source],'motif':'Avant retour'},201)['id']
    original=c.get(root(a)+f"/documents/emis/{doc['id']}/pdf").content
    grant45(c,a);ret(c,a,enc,1)
    error=post(c,a,'/regroupements',{'genre':niveau,'ids':[source],'motif':'Après retour non régularisé'},409)
    assert 'retour' in error['detail'].lower()
    assert c.get(root(a)+f"/documents/emis/{doc['id']}/pdf").content==original


def test_rejeu_refuse_apres_revocation_lecture_documents(raw_client,account):
    c,a=raw_client,account;claims,_,_=ready(c,a);key=uuid4();payload=body(claims)
    draft=post(c,a,'/preparations',payload,201,key)
    gen=db(c);s=next(gen)
    try:
        role=s.scalar(select(RoleModel).where(RoleModel.organisation_id==a['org'],RoleModel.code=='CATALOGUE'))
        s.delete(s.get(RolePermissionModel,(role.id_role,permission_id('tiers_payant.document.consulter'))));s.commit()
    finally:gen.close()
    post(c,a,'/preparations',payload,403,key)
    post(c,a,f"/preparations/{draft['preparation']['id']}/valider",{'revision':1,'motif':'Lecture révoquée'},403)


def test_sommes_documentaires_64_bits_sans_flottants():
    from neosys_pharma.domain.documents_organismes import total_xaf
    assert total_xaf([1_500_000_000,1_500_000_000])==3_000_000_000
    for values in ([True],[1.5],[-1],[9_223_372_036_854_775_807,1]):
        with pytest.raises(ValueError):total_xaf(values)
    from sqlalchemy import BigInteger
    assert isinstance(DocumentOrganismeModel.__table__.c.total_xaf.type,BigInteger)
    assert isinstance(RegroupementDocumentsModel.__table__.c.total_xaf.type,BigInteger)
