"""Contrats configurés, preuves par vente, isolation et snapshots historiques."""
from copy import deepcopy
from datetime import date, datetime, timedelta, timezone
from uuid import UUID, uuid4
import pytest
from sqlalchemy import select, text
from sqlalchemy.exc import DBAPIError
from test_stock import raw_client, account, db, login
from test_catalogue import grant
from test_p5a_tiers_payants import root, post
from test_vente import setup, create, line, act
from neosys_pharma.domain.configuration_convention import configuration_validee, verifier_preuve
from neosys_pharma.infrastructure.tiers_payants_models import ConfigurationConventionModel
from neosys_pharma.infrastructure.securite_models import RoleModel, RolePermissionModel
from neosys_pharma.domain.organisation.permissions_systeme import permission_id


def definition():
    return {'regime': {'code':'GENERAL', 'libelle':'Régime général fictif'},
        'mode_verification':'EXTERNE', 'types_beneficiaires':['TITULAIRE','AYANT_DROIT'],
        'champs':[{'code':'MATRICULE','libelle':'Matricule','type':'TEXTE','obligatoire':True,'format':'CHIFFRES'}],
        'justificatifs':[{'code':'CARTE','libelle':'Carte','obligatoire':True,'groupe_alternative':'IDENTITE'},
                         {'code':'ATTESTATION','libelle':'Attestation','obligatoire':True,'groupe_alternative':'IDENTITE'},
                         {'code':'ORDONNANCE','libelle':'Ordonnance','obligatoire':True,'groupe_alternative':None}]}


def body(organism):
    return {'organisme_id':organism['id'],'revision_organisme':organism['revision'],
        'version_attendue':0,'code':'CONTRAT','reference_contractuelle':'Contrat QA',
        'date_debut':str(date.today()),'date_fin':str(date.today()+timedelta(days=30)),'statut':'ACTIVE',
        'extensions_p5b':{'schema_version':1,'baremes':[{'code':'BASE','taux_numerateur':80,'taux_denominateur':100,
            'produits_ids':[],'categories_ids':[],'plafond_ligne_xaf':100,'arrondi':'PLANCHER'}],
            'exclusions':{'produits_ids':[],'categories_ids':[]}}, 'configuration':definition()}


def organism(c,a):
    codes=('tiers_payant.organisme.gerer','tiers_payant.convention.gerer','tiers_payant.consulter',
               'tiers_payant.adhesion.gerer','tiers_payant.adhesion.consulter','tiers_payant.priorites.gerer')
    gen=db(c);session=next(gen)
    try:
        role=session.scalar(select(RoleModel).where(RoleModel.organisation_id==a['org'],RoleModel.code=='CATALOGUE'))
        if role:
            for code in codes:
                if not session.scalar(select(RolePermissionModel).where(RolePermissionModel.role_id==role.id_role,RolePermissionModel.permission_id==permission_id(code))):
                    session.add(RolePermissionModel(role_id=role.id_role,permission_id=permission_id(code)))
            session.commit()
    finally:gen.close()
    if not role:grant(c,a,codes)
    login(c,a)
    return post(c,a,'/organismes',{'code':'QA','nom':'Organisme QA'})


def test_convention_version_barèmes_revision_idempotence_et_isolation(raw_client, account):
    c,a=raw_client,account;org=organism(c,a);payload=body(org);key=str(uuid4())
    response=c.post(root(a)+'/conventions-configurees',json={'cle':key,**payload})
    assert response.status_code==201,response.text
    row=response.json();assert row['version']==1 and row['configuration']['definition']==definition()
    assert c.post(root(a)+'/conventions-configurees',json={'cle':key,**payload}).json()==row
    assert c.post(root(a)+'/conventions-configurees',json={'cle':key,**payload,'code':'AUTRE'}).status_code==409
    persisted=c.get(root(a)+'/conventions/'+row['id']).json()
    assert persisted['configuration']['definition']==row['configuration']['definition']
    assert persisted['configuration']['id']==row['configuration']['id']
    # A stale version is a conflict; a genuine overlapping next version is a validation error.
    assert post(c,a,'/conventions-configurees',payload,409)
    assert post(c,a,'/conventions-configurees',payload|{'version_attendue':1},422)
    future=payload|{'version_attendue':1,'date_debut':str(date.today()+timedelta(days=31)), 'date_fin':None}
    second=post(c,a,'/conventions-configurees',future)
    assert second['version']==2
    assert c.get(root(a)+'/conventions/'+row['id']).json()==persisted
    assert post(c,a,'/conventions-configurees',payload|{'code':'NOUVEAU','revision_organisme':99},409)
    assert c.get(root(a)+'/conventions/'+str(uuid4())).status_code==404
    assert c.get(root(a).replace(str(a['org']),str(uuid4()))+'/conventions/'+row['id']).status_code==403
    gen=db(c);s=next(gen)
    try:
        for sql in ('UPDATE tiers_payant_configurations_convention SET schema_version=2','DELETE FROM tiers_payant_configurations_convention'):
            with pytest.raises(DBAPIError):s.execute(text(sql));s.commit()
            s.rollback()
    finally:gen.close()


@pytest.mark.parametrize('change', ['taux','plafond','arrondi','doublon','inconnu','produit','regime','bool','conditions'])
def test_configuration_invalide_sans_ecriture_partielle(raw_client, account, change):
    c,a=raw_client,account;p=body(organism(c,a));rule=p['extensions_p5b']['baremes'][0]
    if change=='taux':rule['taux_numerateur']=101
    elif change=='plafond':rule['plafond_ligne_xaf']=-1
    elif change=='arrondi':rule['arrondi']='IMPLICITE'
    elif change=='doublon':p['extensions_p5b']['baremes'].append(dict(rule,code='CONCURRENT'))
    elif change=='inconnu':p['extensions_p5b']['plafond_annuel']=1000
    elif change=='produit':rule['produits_ids']=[str(uuid4())]
    elif change=='regime':p['configuration']['regime']['inconnu']=1
    elif change=='bool':p['configuration']['champs'][0]['obligatoire']='true'
    elif change=='conditions':p['conditions']={'schema_version':True}
    post(c,a,'/conventions-configurees',p,422)
    assert c.get(root(a)+'/conventions').json()['total']==0


def test_preuve_types_formats_alternatives_et_pas_de_confirmation_implicite():
    config=configuration_validee(definition())
    docs=[{'code':c,'reference':'QA-'+c,'verifie':True} for c in ('ATTESTATION','ORDONNANCE')]
    verifier_preuve(config,{'MATRICULE':'123'},docs,'EXTERNE','PORTAIL-QA')
    for values,documents,source in [({},docs,'EXTERNE'),({'MATRICULE':'ABC'},docs,'EXTERNE'),
            ({'MATRICULE':'123'},docs[:1],'EXTERNE'),({'MATRICULE':'123'},docs,'LISTE'),
            ({'MATRICULE':'123'},docs+[docs[0]],'EXTERNE')]:
        with pytest.raises(ValueError):verifier_preuve(config,values,documents,source,'QA')


def test_vente_preuves_bloquantes_revision_refus_snapshot_et_non_reutilisation(raw_client, account):
    c,a=raw_client,account;product,pack,poste,caisse=setup(c,a)
    org=organism(c,a);contract=post(c,a,'/conventions-configurees',body(org))
    beneficiary=post(c,a,'/beneficiaires',{'nom':'Bénéficiaire QA'})
    membership=post(c,a,'/adhesions',{'convention_id':contract['id'],'titulaire_id':beneficiary['id'],
        'beneficiaire_ids':[beneficiary['id']],'reference_adhesion':'QA-ADH','date_debut':str(date.today()),
        'date_fin':contract['date_fin'],'droits_statut':'CONFIRMES','reference_verification_droits':'DROITS-QA',
        'droits_verifies_le':datetime.now(timezone.utc).isoformat()})
    post(c,a,'/priorites',{'date_debut':str(date.today()),'date_fin':contract['date_fin'],'motif':'QA',
        'priorites':[{'organisme_id':org['id'],'convention_id':contract['id'],'rang':1,'role':'SECONDAIRE'}]})
    sale=line(c,a,create(c,a,poste,mode='MUTUELLE'),product,pack)
    prefix=root(a)+'/ventes/'+sale['id'];calc=prefix+'/prise-en-charge'
    assert c.post(calc+'/simuler',json={'beneficiaire_id':beneficiary['id']}).json()['statut']=='BLOQUE'
    proof={'cle':str(uuid4()),'adhesion_id':membership['id'],'beneficiaire_id':beneficiary['id'],
        'revision_adhesion':1,'source':'EXTERNE','reference':'PORTAIL-QA','resultat':'CONFIRME','motif':'Documents vus',
        'date_verification':str(date.today()),'date_fin':str(date.today()),'valeurs':{'MATRICULE':'123'},
        'documents':[{'code':x,'reference':'QA-'+x,'verifie':True} for x in ('CARTE','ORDONNANCE')]}
    assert c.post(prefix+'/verifications',json=proof|{'documents':[]}).status_code==422
    response=c.post(prefix+'/verifications',json=proof);assert response.status_code==201,response.text
    assert c.post(prefix+'/verifications',json=proof).json()==response.json()
    assert c.post(prefix+'/verifications',json=proof|{'motif':'Autre'}).status_code==409
    simulated=c.post(calc+'/simuler',json={'beneficiaire_id':beneficiary['id']}).json()
    assert simulated['statut']=='CALCUL_ADMISSIBLE_PROVISOIRE',simulated
    assert simulated['total_organismes_xaf']==100
    inactive={'cle':str(uuid4()),'revision':1,'code':org['code'],'nom':org['nom'],'actif':False}
    assert c.put(root(a)+'/organismes/'+org['id'],json=inactive).status_code==200
    assert c.post(calc+'/simuler',json={'beneficiaire_id':beneficiary['id']}).json()['statut']=='BLOQUE'
    assert c.put(root(a)+'/organismes/'+org['id'],json=inactive|{'cle':str(uuid4()),'revision':2,'actif':True}).status_code==200

    gen=db(c);s=next(gen)
    try:
        from neosys_pharma.application.stock_service import StockService
        from neosys_pharma.application.prise_en_charge_persistante_service import PriseEnChargePersistanteService
        tomorrow=StockService(s,a['org'],a['user'],lambda *args:None,date.today()+timedelta(days=1))
        assert PriseEnChargePersistanteService(tomorrow,a['site']).simuler(UUID(sale['id']),UUID(beneficiary['id']))['statut']=='BLOQUE'
    finally:gen.close()
    other=line(c,a,create(c,a,poste,mode='MUTUELLE'),product,pack)
    assert c.post(root(a)+'/ventes/'+other['id']+'/prise-en-charge/simuler',json={'beneficiaire_id':beneficiary['id']}).json()['statut']=='BLOQUE'
    # Une nouvelle révision de droits invalide la preuve précédente, même si le compte reste confirmé.
    changed=c.put(root(a)+'/adhesions/'+membership['id'],json={'cle':str(uuid4()),'revision':1,
        'date_fin':contract['date_fin'],'statut':'ACTIVE','droits_statut':'CONFIRMES',
        'reference_verification_droits':'DROITS-QA-2','droits_verifies_le':datetime.now(timezone.utc).isoformat()})
    assert changed.status_code==200,changed.text
    assert c.post(calc+'/simuler',json={'beneficiaire_id':beneficiary['id']}).json()['statut']=='BLOQUE'
    assert c.post(prefix+'/verifications',json=proof|{'cle':str(uuid4())}).status_code==409
    proof.update(cle=str(uuid4()),revision_adhesion=2)
    assert c.post(prefix+'/verifications',json=proof|{'date_verification':str(date.today()+timedelta(days=1))}).status_code==422
    assert c.post(prefix+'/verifications',json=proof).status_code==201
    refused=proof|{'cle':str(uuid4()),'resultat':'REFUSE','valeurs':{},'documents':[],'motif':'Autorisation refusée'}
    assert c.post(prefix+'/verifications',json=refused).status_code==201
    no_cover=c.post(calc+'/simuler',json={'beneficiaire_id':beneficiary['id']}).json()
    assert no_cover['total_organismes_xaf']==0 and 'DROITS_REFUSES' in str(no_cover)
    proof['cle']=str(uuid4())
    assert c.post(prefix+'/verifications',json=proof).status_code==201
    assert c.post(prefix+'/verifications',json=proof|{'cle':str(uuid4()),'beneficiaire_id':str(uuid4())}).status_code==422
    assert c.post(prefix+'/verifications',json=proof,headers={'X-Site-ID':str(a['other'])}).status_code==403
    sale=act(c,a,sale,'valider');sale=act(c,a,sale,'transmettre',caisse_id=caisse)
    confirmed=c.post(calc+'/confirmer',json={'cle':str(uuid4()),'revision':sale['revision'],'beneficiaire_id':beneficiary['id']})
    assert confirmed.status_code==201,confirmed.text
    snapshot=confirmed.json()['snapshot']
    assert 'dossier_documentaire_json' in str(snapshot)
    assert 'PORTAIL-QA' in str(snapshot) and 'ORDONNANCE' in str(snapshot)
    assert product in str(snapshot) and 'lignes_vente' in str(snapshot)
    assert c.post(prefix+'/verifications',json=proof|{'cle':str(uuid4())}).status_code==409
    assert c.get(calc).json()['snapshot']==snapshot
    assert c.get(prefix+'/verifications').json()['total']==4
    gen=db(c);s=next(gen)
    try:
        for sql in ('UPDATE tiers_payant_verifications_convention SET motif=\'FAUX\'', 'DELETE FROM tiers_payant_verifications_convention'):
            with pytest.raises(DBAPIError):s.execute(text(sql));s.commit()
            s.rollback()
    finally:gen.close()


def test_configuration_permissions_csrf_lecture_seule(raw_client,account):
    c,a=raw_client,account
    assert c.get(root(a)+'/conventions/'+str(uuid4())).status_code==401
    login(c,a);assert c.post(root(a)+'/conventions-configurees',json={}).status_code==403
    grant(c,a,('tiers_payant.consulter',));login(c,a)
    assert c.get(root(a)+'/conventions/'+str(uuid4())).status_code==404
    assert c.post(root(a)+'/conventions-configurees',json={}).status_code==403
    org=organism(c,a);token=c.headers.pop('X-CSRF-Token')
    assert c.post(root(a)+'/conventions-configurees',json={'cle':str(uuid4()),**body(org)}).status_code==403
    c.headers['X-CSRF-Token']=token


def test_organisme_inactif_refuse_nouvelle_adhesion(raw_client,account):
    c,a=raw_client,account;org=organism(c,a);contract=post(c,a,'/conventions-configurees',body(org))
    beneficiary=post(c,a,'/beneficiaires',{'nom':'QA sans fidélité'})
    assert c.put(root(a)+'/organismes/'+org['id'],json={'cle':str(uuid4()),'revision':1,'code':org['code'],'nom':org['nom'],'actif':False}).status_code==200
    post(c,a,'/adhesions',{'convention_id':contract['id'],'titulaire_id':beneficiary['id'],
        'beneficiaire_ids':[beneficiary['id']],'reference_adhesion':'QA-INACTIVE','date_debut':str(date.today()),
        'date_fin':contract['date_fin']},422)
    assert c.get(root(a)+'/conventions/'+contract['id']).status_code==200


def test_creation_configuration_rollback_et_reprise_sans_orphelin(raw_client,account):
    from sqlalchemy import event
    c,a=raw_client,account;p=body(organism(c,a));key=str(uuid4())
    def fail(*args):raise ValueError('Échec provoqué après insertion convention')
    event.listen(ConfigurationConventionModel,'before_insert',fail)
    try:assert c.post(root(a)+'/conventions-configurees',json={'cle':key,**p}).status_code==422
    finally:event.remove(ConfigurationConventionModel,'before_insert',fail)
    assert c.get(root(a)+'/conventions').json()['total']==0
    success=c.post(root(a)+'/conventions-configurees',json={'cle':key,**p})
    assert success.status_code==201,success.text
    assert success.json()['version']==1
    assert c.get(root(a)+'/conventions').json()['total']==1
