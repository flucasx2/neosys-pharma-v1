"""GET d'appel depuis Préparation : vendeur seul, PDF et absence de mutation.

Uniquement les fixtures jetables de la suite ; aucune connexion à la recette B04.
"""
from io import BytesIO
from uuid import uuid4

import pytest
from pypdf import PdfReader
from sqlalchemy import delete, select

from test_caisse import raw_client, account, db, ready, final, post, root
from test_vente import root as vente_root, create
from neosys_pharma.domain.organisation.securite import Role, TypeRole, RolePermission, AffectationRole
from neosys_pharma.domain.organisation.permissions_systeme import permission_id
from neosys_pharma.infrastructure.securite_models import AffectationSiteModel, AffectationRoleModel
from neosys_pharma.infrastructure.securite_repository import SqlAlchemySecuriteRepository
from neosys_pharma.infrastructure.caisse_models import ParametrageCaisseModel
from neosys_pharma.infrastructure.database import Base


def seller_only(c, a, permission='vente.consulter'):
    gen=db(c); s=next(gen)
    try:
        assignments=list(s.scalars(select(AffectationSiteModel.id_affectation_site).where(
            AffectationSiteModel.utilisateur_id==a['user'])))
        s.execute(delete(AffectationRoleModel).where(AffectationRoleModel.affectation_site_id.in_(assignments)))
        repo=SqlAlchemySecuriteRepository(s)
        role=Role(code='B04_APPEL',nom='Lecture vendeur B04',type_role=TypeRole.PERSONNALISE,organisation_id=a['org'])
        repo.ajouter(role)
        repo.ajouter(RolePermission(role_id=role.id_role,permission_id=permission_id(permission)))
        assignment=s.scalar(select(AffectationSiteModel.id_affectation_site).where(
            AffectationSiteModel.utilisateur_id==a['user'],AffectationSiteModel.site_id==a['site']))
        repo.ajouter(AffectationRole(affectation_site_id=assignment,role_id=role.id_role))
        s.commit()
    finally: gen.close()


def snapshot(c):
    gen=db(c); s=next(gen)
    try:
        # Toutes les colonnes, y compris séquences, révisions, PDF et historique.
        tables=[t for t in Base.metadata.sorted_tables if t.name.startswith(('vente','caisse','stock','encaissement'))]
        return {t.name:sorted(repr(tuple(row)) for row in s.execute(select(t))) for t in tables}
    finally: gen.close()


@pytest.mark.parametrize('paid',[False,True],ids=['transmise','reimpression-encaissee'])
def test_preparation_ticket_vendeur_sans_session_et_sans_effet(raw_client,account,paid):
    c,a=raw_client,account
    sale,session,*_=ready(c,a)
    if paid: final(c,a,sale,session)
    session=c.get(root(a)+'/sessions').json()['items'][0]
    post(c,a,f'/sessions/{session["id"]}/fermer',{'revision':session['revision'],
         'comptage_final':session['especes_attendues'],'justification':'Recette vendeur sans session'},200)
    seller_only(c,a)
    assert c.get(root(a)+'/sessions').status_code==403
    context=c.get(vente_root(a)+'/contextes'); assert context.status_code==200
    assert context.json()['ticket_appel'] is True
    detail=c.get(vente_root(a)+f'/{sale["id"]}'); assert detail.status_code==200
    assert detail.json()['numero_appel']=='0001'
    assert detail.json()['etat']==('ENCAISSEE' if paid else 'TRANSMISE')
    before=snapshot(c)
    for _ in range(2):
        response=c.get(root(a)+f'/ventes/{sale["id"]}/appel/pdf')
        assert response.status_code==200 and response.headers['content-type']=='application/pdf'
        pages=PdfReader(BytesIO(response.content)).pages
        assert len(pages)==2
        assert 'CLIENT' in pages[0].extract_text()
        assert 'PANIER DE PRÉPARATION' in pages[1].extract_text()
        assert '0001' in pages[0].extract_text() and '0001' in pages[1].extract_text()
        assert 'ne vaut pas reçu de paiement' in pages[0].extract_text().lower()
    assert snapshot(c)==before


@pytest.mark.parametrize('reason',['disabled','missing','permission'])
def test_ticket_refus_sans_mutation(raw_client,account,reason):
    c,a=raw_client,account; sale,session,product,pack,pid,cid=ready(c,a)
    if reason=='missing': sale=create(c,a,pid)  # Vente sans attribution, sans altérer le journal immuable.
    gen=db(c); s=next(gen)
    try:
        if reason=='disabled':
            s.scalar(select(ParametrageCaisseModel).where(ParametrageCaisseModel.organisation_id==a['org'])).ticket_appel=False
        s.commit()
    finally: gen.close()
    seller_only(c,a,'organisation.consulter' if reason=='permission' else 'vente.consulter')
    before=snapshot(c)
    response=c.get(root(a)+f'/ventes/{sale["id"]}/appel/pdf')
    assert response.status_code==(403 if reason=='permission' else 409),response.text
    assert snapshot(c)==before
    if reason=='disabled': assert c.get(vente_root(a)+'/contextes').json()['ticket_appel'] is False
    if reason=='missing': assert c.get(vente_root(a)+f'/{sale["id"]}').json().get('numero_appel') is None
    assert c.get(f'/api/caisses/organisations/{uuid4()}/ventes/{sale["id"]}/appel/pdf').status_code==403
    assert c.get(root(a)+f'/ventes/{sale["id"]}/appel/pdf',headers={'X-Site-ID':str(a['other'])}).status_code==403
