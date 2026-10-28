"""Contrat HTTP de la projection REG-02 ; tests préparés sur fixtures jetables."""
from datetime import date,timedelta
from uuid import UUID,uuid4
import pytest
from sqlalchemy import func,select
from test_stock import raw_client,account,db,login
from test_regularisation import grant45,ret
from test_p5c2_facturation import ready,body,post,emit
from neosys_pharma.domain.organisation.permissions_systeme import P5C2_PERMISSIONS
from test_p5c_creances import post as claim_post
from test_p5a_tiers_payants import root
from neosys_pharma.domain.organisation.permissions_systeme import permission_id
from neosys_pharma.infrastructure.securite_models import (RoleModel,RolePermissionModel,
    AffectationSiteModel,AffectationRoleModel,AffectationEmplacementModel)
from neosys_pharma.infrastructure.creance_models import CreanceOrganismeModel,CompensationCreanceOrganismeModel
from neosys_pharma.infrastructure.facturation_organisme_models import (
    EngagementCreanceModel,VersionPreparationOrganismeModel,DocumentOrganismeModel)
from neosys_pharma.infrastructure.stock_models import OperationStockModel
from neosys_pharma.infrastructure.tiers_payants_models import EvenementTiersPayantModel


def rapprochement(c,a,claim):
    return c.get(root(a)+f"/creances/{claim['id']}/rapprochement")


def grant_document_permissions(c,a):
    gen=db(c);s=next(gen)
    try:
        role=s.scalar(select(RoleModel).where(RoleModel.organisation_id==a['org'],RoleModel.code=='CATALOGUE'))
        for code,_ in P5C2_PERMISSIONS:
            key=(role.id_role,permission_id(code))
            if s.get(RolePermissionModel,key) is None:
                s.add(RolePermissionModel(role_id=key[0],permission_id=key[1]))
        s.commit()
    finally:gen.close()
    login(c,a)


def test_projection_sans_engagement_et_preparation_non_emise(raw_client,account):
    c,a=raw_client,account;claims,_,_=ready(c,a);grant45(c,a);claim=claims[0]
    models=(CreanceOrganismeModel,CompensationCreanceOrganismeModel,EngagementCreanceModel,
        VersionPreparationOrganismeModel,DocumentOrganismeModel,OperationStockModel,EvenementTiersPayantModel)
    def counts():
        gen=db(c);s=next(gen)
        try:return [s.scalar(select(func.count()).select_from(model)) for model in models]
        finally:gen.close()
    before=counts()
    result=rapprochement(c,a,claim)
    assert counts()==before
    assert result.status_code==200,result.text
    data=result.json()
    assert data['creance']['montant_initial_xaf']==claim['montant_xaf']
    assert data['creance']['solde_effectif_xaf']==claim['solde_effectif_xaf']
    assert 'SANS_ENGAGEMENT' in data['etats_projection']
    assert data['engagements']==[] and data['documents_originaux']==[]
    draft=post(c,a,'/preparations',body([claim]),201)
    after_fixture=counts()
    prepared=rapprochement(c,a,claim).json()
    assert counts()==after_fixture
    assert 'PREPARATION_NON_EMISE' in prepared['etats_projection']
    assert prepared['engagements'][0]['preparation']['id']==draft['preparation']['id']
    assert prepared['documents_originaux']==[]
    before_read=counts()
    assert rapprochement(c,a,claim).status_code==200
    assert counts()==before_read


@pytest.mark.parametrize('action',['validation','retrait','abandon'])
def test_projection_preparation_validee_et_engagement_libere(raw_client,account,action):
    c,a=raw_client,account;claims,_,_=ready(c,a);grant45(c,a);claim=claims[0]
    draft=post(c,a,'/preparations',body([claim]),201);ident=draft['preparation']['id']
    if action=='validation':
        post(c,a,f'/preparations/{ident}/valider',{'revision':1,'motif':'Validation de recette'})
        data=rapprochement(c,a,claim).json()
        assert 'PREPARATION_NON_EMISE' in data['etats_projection']
        assert data['engagements'][0]['version_courante']['etat']=='VALIDEE'
    elif action=='retrait':
        post(c,a,f'/preparations/{ident}/selection',{'revision':1,'selection':[],
            'motif':'Retrait de recette'})
    else:
        post(c,a,f'/preparations/{ident}/abandonner',{'revision':1,'motif':'Abandon de recette'})
    if action!='validation':
        data=rapprochement(c,a,claim).json()
        assert data['engagements']==[]
        assert 'PREPARATION_NON_EMISE' not in data['etats_projection']
        assert 'SANS_ENGAGEMENT' in data['etats_projection']


def test_projection_documents_originaux_et_reglement_non_verifiable(raw_client,account,monkeypatch):
    c,a=raw_client,account;claims,_,_=ready(c,a);grant45(c,a);claim=claims[0]
    draft=post(c,a,'/preparations',body([claim],'BORDEREAU'),201)
    bordereau=emit(c,a,draft,monkeypatch,'BOR/REG02/001')
    first=rapprochement(c,a,claim).json()
    assert 'BORDEREAU_EMIS' in first['etats_projection']
    assert first['documents_originaux'][0]['document']['id']==bordereau['document']['id']
    invoice=post(c,a,'/preparations',body([claim],'FACTURE',draft['preparation']['id']),201)
    facture=emit(c,a,invoice,monkeypatch,'FAC/REG02/001')
    final=rapprochement(c,a,claim).json()
    assert 'FACTURE_EMISE' in final['etats_projection']
    assert 'REGLEMENT_NON_VERIFIABLE' in final['etats_projection']
    assert any(x['document']['id']==facture['document']['id'] for x in final['documents_originaux'])
    assert any(x['code']=='REGLEMENT_NON_VERIFIABLE' for x in final['motifs_blocage'])
    assert all('montant_regle_xaf' not in x['document'] for x in final['documents_originaux'])
    assert final['creance']['montant_initial_xaf']==claim['montant_xaf']


@pytest.mark.parametrize('single_payeur,expected',[(True,'CERTAINE'),(False,'VENTILATION_AMBIGUE')])
def test_projection_retour_certain_ou_ventilation_ambigue(raw_client,account,single_payeur,expected):
    from test_p5c_creances import prepare,realise,post as claim_post
    c,a=raw_client,account;sale,session,calc=prepare(c,a,single_payeur=single_payeur)
    real,enc=realise(c,a,sale,session,calc)
    claims=claim_post(c,a,'',{'realisation_id':real['id']},201)['creances']
    claim=claims[0];grant45(c,a);grant_document_permissions(c,a);returned=ret(c,a,enc,1)
    response=rapprochement(c,a,claim)
    assert response.status_code==200,response.text
    data=response.json()
    item=next(x for x in data['retours'] if x['retour_id']==returned['id'])
    assert item['ventilation']==expected
    if expected=='CERTAINE':
        assert item['montant_certain_xaf']>0 and item['preuve_historique']['lignes']
    else:
        assert item['montant_certain_xaf'] is None
        assert 'VENTILATION_AMBIGUE' in data['etats_projection']
        assert any(x['code']=='VENTILATION_AMBIGUE' for x in data['motifs_blocage'])


def test_projection_compensations_existantes_et_pagination(raw_client,account):
    from test_p5c_creances import prepare,realise
    c,a=raw_client,account;sale,session,calc=prepare(c,a,single_payeur=True)
    real,enc=realise(c,a,sale,session,calc)
    claims=claim_post(c,a,'',{'realisation_id':real['id']},201)['creances'];claim=claims[0]
    grant45(c,a);grant_document_permissions(c,a);returned=ret(c,a,enc,1)
    claim_post(c,a,f"/{claim['id']}/compensations-retour",{'retour_id':returned['id'],
        'motif':'Compensation historique REG-01'},200)
    data=rapprochement(c,a,claim).json()
    item=next(x for x in data['retours'] if x['retour_id']==returned['id'])
    assert item['compensation_existante']['retour_id']==returned['id']
    assert data['compensations'][0]['montant_xaf']==item['montant_certain_xaf']
    listing=c.get(root(a)+'/creances/rapprochements',params={'page':1,'page_size':1})
    assert listing.status_code==200 and listing.json()['page_size']==1
    assert len(listing.json()['items'])==1 and listing.json()['total']>=1


def test_projection_exige_permission_document_et_isole_site_organisation(raw_client,account):
    c,a=raw_client,account;claims,_,_=ready(c,a);grant45(c,a);claim=claims[0]
    gen=db(c);s=next(gen)
    try:
        role=s.scalar(select(RoleModel).where(RoleModel.organisation_id==a['org'],RoleModel.code=='CATALOGUE'))
        grant=s.get(RolePermissionModel,(role.id_role,permission_id('tiers_payant.document.consulter')))
        s.delete(grant);s.commit()
    finally:gen.close()
    login(c,a)
    assert rapprochement(c,a,claim).status_code==403
    assert c.get(root(a).replace(str(a['org']),str(UUID(int=1)))+
        f"/creances/{claim['id']}/rapprochement").status_code==403
    assert c.get(root(a)+f"/creances/{claim['id']}/rapprochement",
        headers={'X-Site-ID':str(UUID(int=1))}).status_code==403
    assert c.get(root(a)+f"/creances/{claim['id']}/rapprochement",
        headers={'X-Emplacement-ID':str(a['denied'])}).status_code==403
    assert c.get(root(a)+'/creances/rapprochements',
        headers={'X-Emplacement-ID':str(a['denied'])}).status_code==403


@pytest.mark.parametrize('permission_retained',[
    'caisse.cloture.consulter','vente.retour.gerer',None])
def test_projection_p4_accepte_une_permission_de_lecture_retour(
        raw_client,account,permission_retained):
    c,a=raw_client,account;claims,_,_=ready(c,a);grant45(c,a);claim=claims[0]
    from neosys_pharma.domain.organisation.permissions_systeme import permission_id
    gen=db(c);s=next(gen)
    try:
        role=s.scalar(select(RoleModel).where(RoleModel.organisation_id==a['org'],RoleModel.code=='CATALOGUE'))
        for code in ('caisse.cloture.consulter','vente.retour.gerer'):
            if code!=permission_retained:
                grant=s.get(RolePermissionModel,(role.id_role,permission_id(code)))
                if grant:s.delete(grant)
        s.commit()
    finally:gen.close()
    login(c,a)
    response=rapprochement(c,a,claim)
    assert response.status_code==(403 if permission_retained is None else 200),response.text
    listing=c.get(root(a)+'/creances/rapprochements',params={'page_size':1})
    assert listing.status_code==(403 if permission_retained is None else 200),listing.text


@pytest.mark.parametrize('missing_permission',[
    'tiers_payant.creance.consulter','tiers_payant.document.consulter'])
def test_projection_refuse_absence_permission_p5_obligatoire(raw_client,account,missing_permission):
    c,a=raw_client,account;claims,_,_=ready(c,a);grant45(c,a);claim=claims[0]
    gen=db(c);s=next(gen)
    try:
        role=s.scalar(select(RoleModel).where(RoleModel.organisation_id==a['org'],RoleModel.code=='CATALOGUE'))
        grant=s.get(RolePermissionModel,(role.id_role,permission_id(missing_permission)))
        s.delete(grant);s.commit()
    finally:gen.close()
    login(c,a)
    assert rapprochement(c,a,claim).status_code==403
    assert c.get(root(a)+'/creances/rapprochements').status_code==403


def test_projection_ne_combine_pas_les_permissions_entre_emplacements(raw_client,account):
    c,a=raw_client,account;claims,_,_=ready(c,a);grant45(c,a);claim=claims[0]
    gen=db(c);s=next(gen)
    try:
        catalogue=s.scalar(select(RoleModel).where(RoleModel.organisation_id==a['org'],RoleModel.code=='CATALOGUE'))
        p4_ids=[permission_id(code) for code in ('caisse.cloture.consulter','vente.retour.gerer')]
        for ident in p4_ids:
            grant=s.get(RolePermissionModel,(catalogue.id_role,ident))
            if grant:s.delete(grant)
        p4_role=RoleModel(id_role=uuid4(),organisation_id=a['org'],code='REG02_P4_ONLY',
            nom='Droits P4 isolés',type_role='PERSONNALISE')
        s.add(p4_role);s.flush()
        for ident in p4_ids:s.add(RolePermissionModel(role_id=p4_role.id_role,permission_id=ident))
        second_id=uuid4()
        s.add(AffectationSiteModel(id_affectation_site=second_id,utilisateur_id=a['user'],
            site_id=a['site'],organisation_id=a['org'],date_debut=date.today()-timedelta(days=1),actif=True))
        s.flush()
        role_scope=s.scalar(select(RoleModel.scope_id).where(RoleModel.id_role==p4_role.id_role))
        s.add(AffectationRoleModel(affectation_site_id=second_id,role_id=p4_role.id_role,
            organisation_id=a['org'],role_scope=role_scope))
        s.add(AffectationEmplacementModel(affectation_site_id=second_id,
            emplacement_id=a['denied'],site_id=a['site']))
        s.commit()
    finally:gen.close()
    login(c,a)
    assert rapprochement(c,a,claim).status_code==403
    assert c.get(root(a)+'/creances/rapprochements').status_code==403
