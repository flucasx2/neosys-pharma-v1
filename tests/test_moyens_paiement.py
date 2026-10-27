"""Moyens distincts : confirmations, encaissement, retours et X/Z, sur données fictives."""
from uuid import UUID,uuid4
from decimal import Decimal
from io import BytesIO
import pytest
from sqlalchemy import select
from pypdf import PdfReader
from test_stock import raw_client,account,db
from test_caisse import ready,final,root,post,groupe_post,groupe_put
from test_regularisation import grant45,ret,current,close,post as rpost,root as rroot
from test_p4p5_groupe_organismes import cible_isolee
from neosys_pharma.infrastructure.caisse_models import ConfirmationReglementModel,EncaissementModel
from neosys_pharma.infrastructure.securite_models import RolePermissionModel
from neosys_pharma.domain.organisation.permissions_systeme import permission_id
pytest_plugins=('test_vente',)

def moyen(c,a,code):return post(c,a,'/moyens',{'code':code,'mode':'MOBILE_MONEY','libelle':code.replace('_',' ').title()})
def confirmation(c,a,v,s,m,amount,ref):
    return post(c,a,f'/ventes/{v["id"]}/confirmations',{'revision':v['revision'],'session_id':s['id'],'mode':'MOBILE_MONEY','moyen_id':m['id'],'montant':str(amount),'source':'MANUEL_TERMINAL','reference':ref,'preuve':'Validation fictive sur terminal indépendant'})
def label_pdf(c,a,receipt):return ''.join(p.extract_text() for p in PdfReader(BytesIO(c.get(root(a)+f'/recus/{receipt["id"]}/pdf').content)).pages)

def test_moyens_identites_revisions_permissions_et_confirmations(raw_client,account):
    c,a=raw_client,account;v,s,*_=ready(c,a)
    m=moyen(c,a,'AIRTEL_MONEY');n=moyen(c,a,'MOOV_MONEY')
    config=c.get(root(a)+'/contexte').json()['configuration'];assert {x['id'] for x in config['moyens']}=={m['id'],n['id']}
    post(c,a,'/moyens',{'code':'AIRTEL_MONEY','mode':'MOBILE_MONEY','libelle':'Doublon'},409)
    assert c.post(root(a)+'/moyens',json={'cle':str(uuid4()),'code':'AUTRE','libelle':'Autre','mode':'MOBILE_MONEY'},headers={'X-Site-ID':str(a['other'])}).status_code==403
    cf=confirmation(c,a,v,s,m,100,'AIR-001')
    route=root(a)+f'/moyens/{m["id"]}';data={'cle':str(uuid4()),'revision':1,'libelle':'Libellé modifié','actif':False}
    assert c.put(route,json=data).status_code==200
    assert c.put(route,json=data).status_code==200
    assert c.put(route,json=data|{'cle':str(uuid4())}).status_code==409
    confirmation(c,a,v,s,n,100,'MOOV-001')
    post(c,a,f'/ventes/{v["id"]}/confirmations',{'revision':v['revision'],'session_id':s['id'],'mode':'MOBILE_MONEY','montant':1,'source':'MANUEL_TERMINAL','reference':'SANS-CHOIX','preuve':'fictive'},422)
    post(c,a,f'/ventes/{v["id"]}/confirmations',{'revision':v['revision'],'session_id':s['id'],'mode':'MOBILE_MONEY','moyen_id':m['id'],'montant':1,'source':'MANUEL_TERMINAL','reference':'INACTIF','preuve':'fictive'},409)
    assert cf['moyen_libelle']=='Airtel Money'
    # La contrainte historique de référence par famille n'est pas affaiblie.
    post(c,a,f'/ventes/{v["id"]}/confirmations',{'revision':v['revision'],'session_id':s['id'],'mode':'MOBILE_MONEY','moyen_id':n['id'],'montant':1,'source':'MANUEL_TERMINAL','reference':'AIR-001','preuve':'fictive'},409)


def test_deux_fournisseurs_recu_remboursement_et_clotures(raw_client,account):
    c,a=raw_client,account;v,s,*_=ready(c,a);grant45(c,a)
    m=moyen(c,a,'AIRTEL_MONEY');n=moyen(c,a,'MOOV_MONEY')
    one=confirmation(c,a,v,s,m,100,'AIR-001');two=confirmation(c,a,v,s,n,100,'MOOV-001')
    receipt=final(c,a,v,s,reglements=[{'mode':'MOBILE_MONEY','montant':100,'confirmation_id':one['id']},{'mode':'MOBILE_MONEY','montant':100,'confirmation_id':two['id']},{'mode':'ESPECES','montant':200}])
    pdf=c.get(root(a)+f'/recus/{receipt["id"]}/pdf').content
    assert {'Airtel Money','Moov Money'}<=set(x['confirmation']['moyen_libelle'] for x in receipt['instantane']['reglements'] if x['confirmation'])
    text=label_pdf(c,a,receipt);assert 'Airtel Money' in text and 'Moov Money' in text
    returned=ret(c,a,receipt);amount=returned['montant'];assert Decimal(amount)<=100
    budget=c.get(rroot(a)+f'/retours/{returned["id"]}/solde').json()
    assert {x['moyen_id'] for x in budget['disponible_par_moyen']}=={None,m['id'],n['id']}
    # Substitution entre fournisseurs d'une même famille exige aussi la permission.
    gen=db(c);sql=next(gen)
    try:
        sql.execute(RolePermissionModel.__table__.delete().where(RolePermissionModel.permission_id==permission_id('caisse.remboursement.substituer')));sql.commit()
    finally:gen.close()
    body={'retour_id':returned['id'],'session_id':s['id'],'revision':current(c,a,s)['revision'],'justification':'Restitution fictive','reglements':[{'mode':'MOBILE_MONEY','mode_origine':'MOBILE_MONEY','moyen_id':n['id'],'moyen_origine_id':m['id'],'montant':amount}]}
    rpost(c,a,'/remboursements',body,403)
    body['reglements'][0]['moyen_id']=m['id'];refund=rpost(c,a,'/remboursements',body)
    key=uuid4();approved=rpost(c,a,f'/remboursements/{refund["id"]}/autoriser',{'revision':refund['revision'],'justification':'Accord fictif'},200)
    done={'revision':approved['revision'],'justification':'Restitution constatée','preuves':[{'reference':'AIR-RET-001','preuve':'Terminal fictif'}]}
    result=rpost(c,a,f'/remboursements/{refund["id"]}/executer',done,200,key)
    assert rpost(c,a,f'/remboursements/{refund["id"]}/executer',done,200,key)==result
    assert c.get(root(a)+f'/recus/{receipt["id"]}/pdf').content==pdf
    x=rpost(c,a,'/clotures/x',{'session_id':s['id'],'revision':current(c,a,s)['revision']})
    means=x['instantane']['session']['nets_par_moyen']
    assert Decimal(means['MOBILE_MONEY:'+m['id']]['montant_net'])==100-Decimal(amount)
    assert Decimal(means['MOBILE_MONEY:'+n['id']]['montant_net'])==100
    close(c,a,s);period=c.get(rroot(a)+'/contexte').json()['periode']
    z=rpost(c,a,'/clotures/z',{'periode_id':period['id'],'justification':'Fin fictive'})
    assert z['instantane']['nets_par_moyen']==means


def test_groupe_fournisseurs_allocations_et_refus_inactif(raw_client,account,monkeypatch):
    from test_vente import create,line,act
    from test_p4p5_groupe_organismes import draft
    import neosys_pharma.presentation.encaissement_groupe_api as api
    monkeypatch.setattr(api,'GROUPED_ENCASHMENT_ENABLED',True)
    c,a=raw_client,account;v,s,product,pack,pid,cid=ready(c,a);grant45(c,a)
    second=line(c,a,create(c,a,pid),product,pack,3);second=act(c,a,second,'valider');second=act(c,a,second,'transmettre',caisse_id=cid)
    m=moyen(c,a,'AIRTEL_MONEY');n=moyen(c,a,'MOOV_MONEY')
    one=confirmation(c,a,v,s,m,100,'AIR-G');two=confirmation(c,a,second,s,n,100,'MOOV-G')
    ident,d=draft(c,a,(v,second),s);due=Decimal(d['totaux']['du_xaf'])
    d=groupe_put(c,a,f'/{ident}/reglements',{'cle':str(uuid4()),'revision':d['dossier']['revision'],'reglements':[{'mode':'MOBILE_MONEY','montant':100,'confirmation_id':one['id']},{'mode':'MOBILE_MONEY','montant':100,'confirmation_id':two['id']},{'mode':'ESPECES','montant':str(due-200)}]})
    assert {r['confirmation']['moyen_id'] for r in d['reglements'] if r['confirmation']}=={m['id'],n['id']}
    proposal=c.get(root(a)+f'/groupes/{ident}/allocations/proposition',params={'revision':d['dossier']['revision']}).json()
    d=groupe_put(c,a,f'/{ident}/allocations',{'cle':str(uuid4()),'revision':d['dossier']['revision'],'allocations':proposal})
    assert c.put(root(a)+f'/moyens/{m["id"]}',json={'cle':str(uuid4()),'revision':1,'libelle':m['libelle'],'actif':False}).status_code==200
    payload={'cle':str(uuid4()),'revision':d['dossier']['revision'],'revision_session':s['revision'],'fidelite':[]}
    groupe_post(c,a,f'/{ident}/finaliser',payload,409)
    gen=db(c);sql=next(gen)
    try:assert not sql.scalar(select(EncaissementModel.id))
    finally:gen.close()
    assert c.put(root(a)+f'/moyens/{m["id"]}',json={'cle':str(uuid4()),'revision':2,'libelle':'Airtel nouveau nom','actif':True}).status_code==200
    result=groupe_post(c,a,f'/{ident}/finaliser',payload)
    receipt=next(r for r in result['resultat']['recus_individuels'] if r['vente_id']==v['id'])
    assert 'Airtel Money' in label_pdf(c,a,receipt) # Libellé de confirmation figé avant le renommage.
    returned=ret(c,a,receipt)
    budget=c.get(rroot(a)+f'/retours/{returned["id"]}/solde').json()
    assert sum(Decimal(r['montant']) for r in budget['disponible_par_moyen'])==Decimal(receipt['total_xaf'])
    assert {r['moyen_id'] for r in budget['disponible_par_moyen']}=={m['id'],n['id'],None}
    x=rpost(c,a,'/clotures/x',{'session_id':s['id'],'revision':current(c,a,s)['revision']})
    assert x['instantane']['session']['nets_par_mode']['MOBILE_MONEY']=='200'


def test_fk_moyen_refuse_mauvaise_famille_et_organisation(raw_client,account):
    from sqlalchemy.exc import IntegrityError
    from neosys_pharma.infrastructure.caisse_models import MoyenPaiementModel
    from neosys_pharma.infrastructure.organisation_models import OrganisationModel
    c,a=raw_client,account;v,s,*_=ready(c,a)
    card=post(c,a,'/moyens',{'code':'CARTE_QA','mode':'CARTE','libelle':'Carte fictive'})
    gen=db(c);sql=next(gen)
    try:
        foreign=uuid4();provider=uuid4()
        sql.add(OrganisationModel(id_organisation=foreign,nom_commercial='Autre fictive',raison_sociale='Autre fictive',actif=True));sql.flush()
        sql.add(MoyenPaiementModel(id=provider,organisation_id=foreign,mode='MOBILE_MONEY',code='AUTRE',libelle='Autre organisme',actif=True,revision=1));sql.commit()
        for ident in (UUID(card['id']),provider):
            sql.add(ConfirmationReglementModel(organisation_id=a['org'],vente_id=UUID(v['id']),session_id=UUID(s['id']),revision_vente=v['revision'],mode='MOBILE_MONEY',moyen_id=ident,moyen_libelle='Fictive',montant=10,reference='FK-'+str(ident),source='MANUEL_TERMINAL',preuve='Fictive',auteur_id=a['user']))
            with pytest.raises(IntegrityError):sql.commit()
            sql.rollback()
    finally:gen.close()
