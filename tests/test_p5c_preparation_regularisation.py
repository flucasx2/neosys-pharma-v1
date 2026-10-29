"""Contrat HTTP préparé pour REG-02 Étape 2 ; non exécuté sans recette jetable autorisée."""
from copy import deepcopy
from uuid import UUID,uuid4

import pytest
from sqlalchemy import func,select

from test_stock import raw_client,account,db,login
from test_p5a_tiers_payants import root
import test_p5c2_facturation as p5c2_fixtures
from test_p5c2_facturation import ready,body,post,emit,validate_claim
from test_p5c_creances import prepare,realise,post as claim_post
from test_regularisation import grant45,ret
from neosys_pharma.domain.organisation.permissions_systeme import P5C2_PERMISSIONS,permission_id
from neosys_pharma.domain.stock import ConflitStock
from neosys_pharma.infrastructure.securite_models import RoleModel,RolePermissionModel
from neosys_pharma.infrastructure.creance_models import CreanceOrganismeModel,CompensationCreanceOrganismeModel
from neosys_pharma.infrastructure.facturation_organisme_models import (
    EngagementCreanceModel,VersionPreparationOrganismeModel,DocumentOrganismeModel,
)
from neosys_pharma.infrastructure.tiers_payants_models import EvenementTiersPayantModel
from neosys_pharma.infrastructure.stock_models import OperationStockModel

pytest_plugins=('test_vente',)


def regulariser(c,a,preparation,claim,returned,action='RETIRER',revision=1,key=None,status=200):
    response=c.post(root(a)+f"/documents/preparations/{preparation['preparation']['id']}/regulariser-retour",
        json={'cle':str(key or uuid4()),'creance_id':claim['id'],'retour_id':returned['id'],
            'revision':revision,'action':action,'motif':'Régularisation REG-02 après retour confirmé'})
    assert response.status_code==status,response.text
    return response


def single_ready(c,a):
    sale,session,calc=prepare(c,a,single_payeur=True)
    real,enc=realise(c,a,sale,session,calc)
    claims=claim_post(c,a,'',{'realisation_id':real['id']},201)['creances']
    claim=validate_claim(c,a,claims[0])
    gen=db(c);s=next(gen)
    try:
        role=s.scalar(select(RoleModel).where(RoleModel.organisation_id==a['org'],RoleModel.code=='CATALOGUE'))
        for code,_ in P5C2_PERMISSIONS:
            key=(role.id_role,permission_id(code))
            if s.get(RolePermissionModel,key) is None:
                s.add(RolePermissionModel(role_id=key[0],permission_id=key[1]))
        s.commit()
    finally:
        gen.close()
    grant45(c,a);login(c,a)
    return claim,enc


def tracked_counts(c):
    models=(CreanceOrganismeModel,CompensationCreanceOrganismeModel,EngagementCreanceModel,
        VersionPreparationOrganismeModel,DocumentOrganismeModel,OperationStockModel,EvenementTiersPayantModel)
    gen=db(c);s=next(gen)
    try:
        return {model.__tablename__:s.scalar(select(func.count()).select_from(model)) for model in models}
    finally:
        gen.close()


@pytest.mark.parametrize('validated',[False,True])
def test_regularisation_retire_une_creance_et_preserve_les_autres(raw_client,account,validated,monkeypatch):
    c,a=raw_client,account
    # Une réalisation mono-organisme rend le retour de la créance cible certain;
    # la seconde créance reste issue d'une réalisation indépendante.
    monkeypatch.setattr(p5c2_fixtures,'prepare',lambda client,account:prepare(client,account,single_payeur=True))
    claims,_,enc=p5c2_fixtures.ready(c,a,second=True)
    assert len(claims)==2 and claims[0]['organisme_id']==claims[1]['organisme_id']
    preparation=post(c,a,'/preparations',body(claims),201)
    initial_selection=deepcopy(preparation['version']['selection'])
    revision=1
    if validated:
        preparation=post(c,a,f"/preparations/{preparation['preparation']['id']}/valider",
            {'revision':1,'motif':'Préparation contrôlée'},200)
        revision=preparation['version']['revision']
    grant45(c,a);returned=ret(c,a,enc,1)
    target,sibling=claims
    response=regulariser(c,a,preparation,target,returned,revision=revision,key=uuid4())
    assert response.status_code==200,response.text
    result=response.json()
    assert result['action']=='RETIRER'
    assert result['preparation']['version']['revision']==revision+1
    assert result['preparation']['version']['etat']=='PREPARATION'
    assert [x['creance_id'] for x in result['preparation']['version']['selection']]==[sibling['id']]
    assert result['creance']['montant_xaf']==target['montant_xaf']
    assert result['creance']['snapshot']==target['snapshot']
    assert result['creance']['solde_effectif_xaf']==target['montant_xaf']-returned['montant_organismes_xaf']
    sibling_after=c.get(root(a)+f"/creances/{sibling['id']}").json()
    assert sibling_after['montant_xaf']==sibling['montant_xaf']
    assert sibling_after['snapshot']==sibling['snapshot']
    if result['creance']['solde_effectif_xaf']>0:
        next_preparation=post(c,a,'/preparations',body([result['creance']]),201)
        assert next_preparation['version']['selection'][0]['creance_id']==target['id']
    gen=db(c);s=next(gen)
    try:
        engagements=s.scalars(select(EngagementCreanceModel).where(
            EngagementCreanceModel.preparation_id==UUID(preparation['preparation']['id']))).all()
        assert {str(x.creance_id) for x in engagements}=={sibling['id']}
        history=s.scalars(select(VersionPreparationOrganismeModel).where(
            VersionPreparationOrganismeModel.preparation_id==UUID(preparation['preparation']['id']))
            .order_by(VersionPreparationOrganismeModel.revision)).all()
        assert len(history)==revision+1
        assert history[0].selection==initial_selection
    finally:
        gen.close()


@pytest.mark.parametrize('action,expected_state,expected_selection',[
    ('RETIRER','PREPARATION',[]),('ABANDONNER','ABANDONNEE',None),
])
def test_regularisation_derniere_creance_ou_abandon_libere_engagement(
        raw_client,account,action,expected_state,expected_selection):
    c,a=raw_client,account;claim,enc=single_ready(c,a)
    preparation=post(c,a,'/preparations',body([claim]),201);returned=ret(c,a,enc,1)
    response=regulariser(c,a,preparation,claim,returned,action=action)
    assert response.status_code==200,response.text
    payload=response.json();version=payload['preparation']['version']
    assert version['etat']==expected_state
    if expected_selection is not None:assert version['selection']==expected_selection
    else:assert version['selection']==preparation['version']['selection']
    assert payload['creance']['solde_effectif_xaf']==claim['montant_xaf']-returned['montant_organismes_xaf']
    gen=db(c);s=next(gen)
    try:
        assert s.scalar(select(func.count()).select_from(EngagementCreanceModel).where(
            EngagementCreanceModel.creance_id==UUID(claim['id'])))==0
    finally:
        gen.close()


def test_regularisation_totale_garde_solde_initial_et_refuse_nouvelle_selection_nulle(raw_client,account):
    c,a=raw_client,account;claim,enc=single_ready(c,a)
    preparation=post(c,a,'/preparations',body([claim]),201);returned=ret(c,a,enc,20)
    assert returned['montant_organismes_xaf']==claim['montant_xaf']
    response=regulariser(c,a,preparation,claim,returned)
    assert response.status_code==200,response.text
    current=response.json()['creance']
    assert current['montant_xaf']==claim['montant_xaf']
    assert current['snapshot']==claim['snapshot']
    assert current['solde_effectif_xaf']==0
    post(c,a,'/preparations',body([claim]),409)


def test_regularisation_compensation_existante_refusee_sans_mutation(raw_client,account):
    c,a=raw_client,account;claim,enc=single_ready(c,a);returned=ret(c,a,enc,1)
    claim_post(c,a,f"/{claim['id']}/compensations-retour",{
        'retour_id':returned['id'],'motif':'Compensation REG-01 antérieure'},200)
    preparation=post(c,a,'/preparations',body([claim]),201)
    before=tracked_counts(c);key=uuid4()
    duplicate=regulariser(c,a,preparation,claim,returned,key=key,status=409)
    assert duplicate.status_code==409
    assert tracked_counts(c)==before

def test_regularisation_mutation_complete_rejouable_avec_meme_cle(raw_client,account):
    c,a=raw_client,account;claim,enc=single_ready(c,a)
    preparation=post(c,a,'/preparations',body([claim]),201);returned=ret(c,a,enc,1);key=uuid4()
    first=regulariser(c,a,preparation,claim,returned,key=key)
    assert first.status_code==200,first.text
    before=tracked_counts(c)
    replay=regulariser(c,a,preparation,claim,returned,key=key)
    assert replay.status_code==200,replay.text
    assert replay.json()==first.json()
    assert tracked_counts(c)==before


def test_regularisation_rollback_integral_apres_liberation_forcee(raw_client,account,monkeypatch):
    c,a=raw_client,account;claim,enc=single_ready(c,a)
    preparation=post(c,a,'/preparations',body([claim]),201);returned=ret(c,a,enc,1)
    preparation_id=UUID(preparation['preparation']['id']);claim_id=UUID(claim['id']);key=uuid4()
    def state():
        gen=db(c);s=next(gen)
        try:
            versions=[(str(x.id),x.revision,x.etat,x.selection,x.motif) for x in s.scalars(
                select(VersionPreparationOrganismeModel).where(
                    VersionPreparationOrganismeModel.preparation_id==preparation_id,
                    VersionPreparationOrganismeModel.organisation_id==a['org'])
                .order_by(VersionPreparationOrganismeModel.revision))]
            engagements=[(str(x.id),str(x.creance_id),x.genre) for x in s.scalars(
                select(EngagementCreanceModel).where(
                    EngagementCreanceModel.preparation_id==preparation_id,
                    EngagementCreanceModel.organisation_id==a['org']))]
            compensations=[(str(x.id),str(x.retour_id),x.montant_xaf,x.snapshot,x.snapshot_hash)
                for x in s.scalars(select(CompensationCreanceOrganismeModel).where(
                    CompensationCreanceOrganismeModel.creance_id==claim_id,
                    CompensationCreanceOrganismeModel.organisation_id==a['org']))]
            events=[(str(x.id),x.entite_type,str(x.entite_id),x.type,x.donnees) for x in s.scalars(
                select(EvenementTiersPayantModel).where(
                    EvenementTiersPayantModel.organisation_id==a['org'],
                    EvenementTiersPayantModel.entite_id.in_([preparation_id,claim_id])))]
            row=s.get(CreanceOrganismeModel,claim_id)
            operation=s.scalar(select(OperationStockModel).where(
                OperationStockModel.organisation_id==a['org'],OperationStockModel.cle==key))
            return {'versions':versions,'engagements':engagements,'compensations':compensations,
                'events':events,'initial':(row.montant_xaf,row.snapshot,row.snapshot_hash),
                'operation':operation}
        finally:
            gen.close()
    before=state();before_counts=tracked_counts(c)
    from neosys_pharma.application.creance_service import CreanceService
    def fail_after_release(self,*args,**kwargs):
        raise ConflitStock('Échec volontaire après la libération de l’engagement.')
    with monkeypatch.context() as patcher:
        patcher.setattr(CreanceService,'regulariser_retour',fail_after_release)
        failed=regulariser(c,a,preparation,claim,returned,key=key,status=409)
    assert failed.status_code==409
    assert state()==before
    assert tracked_counts(c)==before_counts
    assert state()['operation'] is None
    current=c.get(root(a)+f"/creances/{claim['id']}").json()
    assert current['montant_xaf']==claim['montant_xaf'] and current['compensations']==[]


def test_regularisation_revision_obsolete_refuse_sans_mutation(raw_client,account):
    c,a=raw_client,account;claim,enc=single_ready(c,a)
    preparation=post(c,a,'/preparations',body([claim]),201)
    post(c,a,f"/preparations/{preparation['preparation']['id']}/valider",
        {'revision':1,'motif':'Validation préalable'})
    returned=ret(c,a,enc,1);before=tracked_counts(c)
    stale=regulariser(c,a,preparation,claim,returned,revision=1,status=409)
    assert stale.status_code==409
    assert tracked_counts(c)==before


@pytest.mark.parametrize('genre',['BORDEREAU','FACTURE'])
def test_regularisation_refuse_document_emis(raw_client,account,monkeypatch,genre):
    c,a=raw_client,account;claims,_,enc=ready(c,a)
    claim=claims[0];preparation=post(c,a,'/preparations',body([claim],genre),201)
    emit(c,a,preparation,monkeypatch,f'{genre}/REG02/STEP2/001')
    grant45(c,a);returned=ret(c,a,enc,1);before=tracked_counts(c)
    response=regulariser(c,a,preparation,claim,returned,revision=3,status=409)
    assert response.status_code==409
    assert tracked_counts(c)==before

def test_regularisation_refuse_ventilation_historique_ambigue(raw_client,account):
    c,a=raw_client,account;claims,_,enc=ready(c,a);claim=claims[0]
    preparation=post(c,a,'/preparations',body([claim]),201)
    grant45(c,a);ambiguous=ret(c,a,enc,1);before=tracked_counts(c)
    response=regulariser(c,a,preparation,claim,ambiguous,status=409)
    assert response.status_code==409
    assert tracked_counts(c)==before


def test_regularisation_refuse_engagement_et_document_emis_dans_une_autre_preparation(
        raw_client,account,monkeypatch):
    c,a=raw_client,account;claim,enc=single_ready(c,a)
    bordereau=post(c,a,'/preparations',body([claim],'BORDEREAU'),201)
    emit(c,a,bordereau,monkeypatch,'BOR/REG02/STEP2/OTHER')
    facture=post(c,a,'/preparations',
        body([claim],'FACTURE',bordereau['preparation']['id']),201)
    returned=ret(c,a,enc,1);before=tracked_counts(c)
    response=regulariser(c,a,facture,claim,returned,revision=1,status=409)
    assert response.status_code==409
    assert tracked_counts(c)==before
    gen=db(c);s=next(gen)
    try:
        assert s.scalar(select(func.count()).select_from(EngagementCreanceModel).where(
            EngagementCreanceModel.creance_id==UUID(claim['id'])))==2
        assert s.scalar(select(func.count()).select_from(DocumentOrganismeModel))==1
        assert s.scalar(select(func.count()).select_from(CompensationCreanceOrganismeModel))==0
    finally:
        gen.close()


@pytest.mark.parametrize('missing_permission',[
    'tiers_payant.document.preparer','tiers_payant.creance.regulariser'])
def test_regularisation_exige_les_deux_permissions_et_isole_le_site(
        raw_client,account,missing_permission):
    c,a=raw_client,account;claim,enc=single_ready(c,a)
    preparation=post(c,a,'/preparations',body([claim]),201);returned=ret(c,a,enc,1)
    gen=db(c);s=next(gen)
    try:
        role=s.scalar(select(RoleModel).where(RoleModel.organisation_id==a['org'],RoleModel.code=='CATALOGUE'))
        link=s.get(RolePermissionModel,(role.id_role,permission_id(missing_permission)))
        if link:s.delete(link)
        s.commit()
    finally:
        gen.close()
    login(c,a);before=tracked_counts(c)
    denied=regulariser(c,a,preparation,claim,returned,status=403)
    assert denied.status_code==403
    assert tracked_counts(c)==before


def test_regularisation_isole_site_organisation_et_emplacement(raw_client,account):
    c,a=raw_client,account;claim,enc=single_ready(c,a)
    preparation=post(c,a,'/preparations',body([claim]),201);returned=ret(c,a,enc,1)
    before=tracked_counts(c)
    for header,value in (('X-Site-ID',str(UUID(int=1))),('X-Emplacement-ID',str(a['denied']))):
        previous=c.headers.get(header)
        c.headers[header]=value
        try:
            denied=regulariser(c,a,preparation,claim,returned,status=403)
            assert denied.status_code==403
            assert tracked_counts(c)==before
        finally:
            if previous is None:c.headers.pop(header,None)
            else:c.headers[header]=previous
    wrong_org=root(a).replace(str(a['org']),str(UUID(int=2)))
    denied=c.post(wrong_org+f"/documents/preparations/{preparation['preparation']['id']}/regulariser-retour",
        json={'cle':str(uuid4()),'creance_id':claim['id'],'retour_id':returned['id'],
              'revision':1,'action':'RETIRER','motif':'Mauvaise organisation'})
    assert denied.status_code==403
    assert tracked_counts(c)==before
