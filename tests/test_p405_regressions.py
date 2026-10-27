"""P4-05 A–D : parcours existants sur fixtures fictives exclusivement."""
from decimal import Decimal
from uuid import UUID,uuid4
import pytest
from sqlalchemy import select
from test_caisse import db
from test_caisse import raw_client,account,ready,final,post as cash_post,root as cash_root,groupe_post,groupe_put,line,create,act
from test_regularisation import grant45,ret,current,close,post,root


def finish_refund(c,a,s,returned,rows):
    payload={'retour_id':returned['id'],'session_id':s['id'],
             'revision':current(c,a,s)['revision'],'reglements':rows,'justification':'Retour fictif P4-05'}
    key=uuid4();request=post(c,a,'/remboursements',payload,key=key)
    assert post(c,a,'/remboursements',payload,key=key)==request
    approved=post(c,a,f'/remboursements/{request["id"]}/autoriser',
                  {'revision':request['revision'],'justification':'Accord fictif'},200)
    data={'revision':approved['revision'],'justification':'Restitution synthétique',
          'preuves':[{'reference':'P405-'+str(i),'preuve':'Terminal fictif'} for i in range(len(rows))]}
    key=uuid4();result=post(c,a,f'/remboursements/{request["id"]}/executer',data,200,key)
    assert post(c,a,f'/remboursements/{request["id"]}/executer',data,200,key)==result
    post(c,a,f'/remboursements/{request["id"]}/executer',data,409)
    return result


@pytest.mark.parametrize('mode',['CARTE','MOBILE_MONEY','CHEQUE','VIREMENT'])
def test_retour_total_identite_historique_inactive(raw_client,account,mode):
    c,a=raw_client,account;v,s,*_=ready(c,a);grant45(c,a)
    provider=cash_post(c,a,'/moyens',{'code':'ORIGINE_P405','libelle':'Origine historique fictive','mode':mode})
    confirmation=cash_post(c,a,f'/ventes/{v["id"]}/confirmations',{
        'revision':v['revision'],'session_id':s['id'],'mode':mode,'moyen_id':provider['id'],
        'montant':301,'reference':'P405-ORIGINE','source':
        'MANUEL_JUSTIFICATIF' if mode in ('CHEQUE','VIREMENT') else 'MANUEL_TERMINAL','preuve':'Fictive'})
    receipt=final(c,a,v,s,reglements=[{'mode':mode,'montant':301,'confirmation_id':confirmation['id']}])
    path=cash_root(a)+f'/recus/{receipt["id"]}/pdf';original=c.get(path).content
    assert c.put(cash_root(a)+f'/moyens/{provider["id"]}',json={
        'cle':str(uuid4()),'revision':provider['revision'],'libelle':'Renommé après vente','actif':False}).status_code==200
    returned=ret(c,a,receipt,3)
    budget=c.get(root(a)+f'/retours/{returned["id"]}/solde').json()
    assert budget['disponible_par_moyen'][0]['moyen_id']==provider['id']
    excessive={'retour_id':returned['id'],'session_id':s['id'],'revision':current(c,a,s)['revision'],
        'justification':'Excès refusé','reglements':[{'mode':mode,'moyen_id':provider['id'],
        'moyen_origine_id':provider['id'],'montant':302}]}
    post(c,a,'/remboursements',excessive,409)
    result=finish_refund(c,a,s,returned,[{'mode':mode,'moyen_id':provider['id'],
        'moyen_origine_id':provider['id'],'montant':301}])
    assert result['etat']=='EXECUTE' and c.get(path).content==original
    x=post(c,a,'/clotures/x',{'session_id':s['id'],'revision':current(c,a,s)['revision']})
    detail=x['instantane']['detail_flux']
    assert detail['encaissements'][0]['libelle']=='Origine historique fictive'
    assert detail['totaux']['net_regle']==detail['totaux']['remboursements_executes']=='301'
    assert current(c,a,s)['especes_attendues']=='1000'
    ret(c,a,receipt,1,409)


def test_retours_successifs_groupe_mixte_conservent_allocations_et_pdfs(raw_client,account,monkeypatch):
    import neosys_pharma.presentation.encaissement_groupe_api as api
    # Instance HTTP de test uniquement ; garde de production inchangé.
    monkeypatch.setattr(api,'GROUPED_ENCASHMENT_ENABLED',True)
    c,a=raw_client,account;v,s,product,pack,pid,cid=ready(c,a);grant45(c,a)
    act(c,a,v,'annuler',justification='Préparation de fixture remplacée avant paiement')
    # Référentiel synthétique avant les nouvelles ventes : aucun historique réel.
    from neosys_pharma.infrastructure.tarification_models import TarifReferenceModel
    gen=db(c);sql=next(gen)
    try:
        tariff=sql.scalar(select(TarifReferenceModel).where(TarifReferenceModel.conditionnement_id==UUID(pack)))
        tariff.montant_ht=Decimal('11266.6667');sql.commit()
    finally:gen.close()
    v=line(c,a,create(c,a,pid),product,pack,3)
    v=act(c,a,v,'valider');v=act(c,a,v,'transmettre',caisse_id=cid)
    second=line(c,a,create(c,a,pid),product,pack,6)
    second=act(c,a,second,'valider');second=act(c,a,second,'transmettre',caisse_id=cid)
    assert Decimal(v['totaux']['ttc'])==33800 and Decimal(second['totaux']['ttc'])==67600
    confirmations=[]
    for sale,mode,code,amount in [(v,'CARTE','CARTE_P405',10000),(second,'MOBILE_MONEY','AIRTEL_P405',1400)]:
        provider=cash_post(c,a,'/moyens',{'code':code,'mode':mode,'libelle':code})
        confirmations.append(cash_post(c,a,f'/ventes/{sale["id"]}/confirmations',{
            'revision':sale['revision'],'session_id':s['id'],'mode':mode,'moyen_id':provider['id'],
            'montant':amount,'reference':code,'source':'MANUEL_TERMINAL','preuve':'Fictive'}))
    d=groupe_post(c,a,'',{'cle':str(uuid4()),'session_id':s['id']},201);gid=d['dossier']['id']
    d=groupe_put(c,a,f'/{gid}/ventes',{'cle':str(uuid4()),'revision':d['dossier']['revision'],
        'ventes':[{'vente_id':x['id'],'revision':x['revision']} for x in (v,second)]})
    d=groupe_put(c,a,f'/{gid}/reglements',{'cle':str(uuid4()),'revision':d['dossier']['revision'],
        'reglements':[{'mode':cf['mode'],'montant':cf['montant'],'confirmation_id':cf['id']} for cf in confirmations]
        +[{'mode':'ESPECES','montant':90500}]})
    payments={x['mode']:x for x in d['reglements']}
    allocations=[{'reglement_id':payments[mode]['id'],'vente_id':sale['id'],'montant':amount}
        for sale,mode,amount in [(v,'CARTE',10000),(v,'ESPECES',23800),
                                (second,'ESPECES',66200),(second,'MOBILE_MONEY',1400)]]
    d=groupe_put(c,a,f'/{gid}/allocations',{'cle':str(uuid4()),'revision':d['dossier']['revision'],'allocations':allocations})
    result=groupe_post(c,a,f'/{gid}/finaliser',{'cle':str(uuid4()),'revision':d['dossier']['revision'],
        'revision_session':s['revision'],'fidelite':[]})
    original=c.get(cash_root(a)+f'/groupes/{gid}').json()
    receipts=result['resultat']['recus_individuels']
    pdfs={r['id']:c.get(cash_root(a)+f'/recus/{r["id"]}/pdf').content for r in receipts}
    collective_path=cash_root(a)+f'/groupes/{gid}/recu.pdf'
    collective=c.get(collective_path);assert collective.status_code==200
    assert current(c,a,s)['especes_attendues']=='91000'
    assert Decimal(original['totaux']['brut_recu_xaf'])==101900
    assert Decimal(original['totaux']['rendu_xaf'])==500
    assert Decimal(original['totaux']['net_regle_xaf'])==101400
    for receipt in receipts:
        for index in range(3 if receipt['vente_id']==v['id'] else 6):
            returned=ret(c,a,receipt)
            # Seuls les nets réellement alloués à cette vente financent le retour.
            budget=c.get(root(a)+f'/retours/{returned["id"]}/solde').json()
            remaining=Decimal(returned['montant']);rows=[]
            for source in budget['disponible_par_moyen']:
                amount=min(remaining,Decimal(source['montant']))
                if amount:
                    rows.append({'mode':source['mode'],'moyen_id':source['moyen_id'],
                        'moyen_origine_id':source['moyen_id'],'montant':str(amount)})
                    remaining-=amount
            assert remaining==0
            finish_refund(c,a,s,returned,rows)
        ret(c,a,receipt,1,409)
    assert current(c,a,s)['especes_attendues']=='1000'
    assert c.get(cash_root(a)+f'/groupes/{gid}').json()==original
    assert all(c.get(cash_root(a)+f'/recus/{r["id"]}/pdf').content==pdfs[r['id']] for r in receipts)
    assert c.get(collective_path).content==collective.content
    x=post(c,a,'/clotures/x',{'session_id':s['id'],'revision':current(c,a,s)['revision']})
    assert all(Decimal(amount)==0 for amount in x['instantane']['session']['nets_par_mode'].values())
    close(c,a,s);period=c.get(root(a)+'/contexte').json()['periode']
    z=post(c,a,'/clotures/z',{'periode_id':period['id'],'justification':'Fin fictive P405'})
    assert z['instantane']['nets_par_mode']==x['instantane']['session']['nets_par_mode']
    detail=z['instantane']['detail_flux']
    assert len(detail['encaissements'])==3 and all(r['source']=='GROUPE' for r in detail['encaissements'])
    assert detail['totaux']['brut_recu']=='101900' and detail['totaux']['rendu']=='500'
    assert detail['totaux']['net_regle']==detail['totaux']['remboursements_executes']=='101400'
    assert detail==x['instantane']['detail_flux']
    import os
    if os.getenv('P405_C06_PDF_QA')=='1':
        from pathlib import Path
        for name,document in [('x',x),('z',z)]:
            pdf=c.get(root(a)+f'/documents/clotures/{document["id"]}/pdf').content
            Path('/results/c06-groupe-'+name+'.pdf').write_bytes(pdf)



def test_fonds_idempotence_transfert_annule_et_obligation_retour(raw_client,account):
    c,a=raw_client,account;v,s,*_=ready(c,a);coffre=grant45(c,a)
    data={'session_id':s['id'],'revision':s['revision'],'sens':'ENTREE','montant':100,'justification':'Apport fictif'}
    key=uuid4();entry=post(c,a,'/fonds',data,key=key)
    assert post(c,a,'/fonds',data,key=key)==entry and current(c,a,s)['especes_attendues']=='1100'
    t=post(c,a,'/transferts',{'session_id':s['id'],'revision':current(c,a,s)['revision'],
        'coffre_id':coffre,'sens':'CAISSE_COFFRE','montant':100,'justification':'Projet fictif'})
    cancelled=post(c,a,f'/transferts/{t["id"]}/annuler',{'revision':t['revision'],'justification':'Avant expédition'},200)
    assert cancelled['etat']=='ANNULE' and current(c,a,s)['especes_attendues']=='1100'
    post(c,a,f'/transferts/{t["id"]}/expedier',{'revision':cancelled['revision'],'justification':'Interdit'},409)
    receipt=final(c,a,v,current(c,a,s));returned=ret(c,a,receipt,3)
    close(c,a,s);period=c.get(root(a)+'/contexte').json()['periode']
    post(c,a,'/clotures/z',{'periode_id':period['id'],'justification':'Retour non remboursé'},409)
    # Une demande financière ne peut pas démarrer dans la session fermée.
    post(c,a,'/remboursements',{'retour_id':returned['id'],'session_id':s['id'],
        'revision':current(c,a,s)['revision'],'reglements':[{'mode':'ESPECES','montant':301}],
        'justification':'Session fermée'},409)


def test_x_idempotent_sans_revision_et_relecture_apres_z(raw_client,account):
    c,a=raw_client,account;v,s,*_=ready(c,a);grant45(c,a)
    before=current(c,a,s);payload={'session_id':s['id'],'revision':before['revision']};key=uuid4()
    x=post(c,a,'/clotures/x',payload,key=key)
    assert post(c,a,'/clotures/x',payload,key=key)==x and current(c,a,s)==before
    path=root(a)+f'/documents/clotures/{x["id"]}/pdf';pdf=c.get(path).content
    close(c,a,s);period=c.get(root(a)+'/contexte').json()['periode']
    post(c,a,'/clotures/z',{'periode_id':period['id'],'justification':'Période du site'})
    assert c.get(path).content==pdf
    post(c,a,'/clotures/x',{'session_id':s['id'],'revision':current(c,a,s)['revision']},409)


def test_abandon_groupe_conserve_confirmation_a_resoudre(raw_client,account):
    c,a=raw_client,account;v,s,*_=ready(c,a);grant45(c,a)
    cf=cash_post(c,a,f'/ventes/{v["id"]}/confirmations',{'session_id':s['id'],
        'revision':v['revision'],'mode':'CARTE','montant':100,'reference':'ABANDON-P405',
        'source':'MANUEL_TERMINAL','preuve':'Fictive'})
    d=groupe_post(c,a,'',{'cle':str(uuid4()),'session_id':s['id']},201);gid=d['dossier']['id']
    d=groupe_put(c,a,f'/{gid}/ventes',{'cle':str(uuid4()),'revision':d['dossier']['revision'],
        'ventes':[{'vente_id':v['id'],'revision':v['revision']}]})
    d=groupe_put(c,a,f'/{gid}/reglements',{'cle':str(uuid4()),'revision':d['dossier']['revision'],
        'reglements':[{'mode':'CARTE','montant':100,'confirmation_id':cf['id']},
                      {'mode':'ESPECES','montant':201}]})
    d=groupe_post(c,a,f'/{gid}/abandonner',{'cle':str(uuid4()),'revision':d['dossier']['revision']})
    assert d['dossier']['etat']=='ABANDONNE' and not d['reglements']
    assert [row['id'] for row in c.get(root(a)+'/paiements/non-finalises').json()]==[cf['id']]
    close(c,a,s);period=c.get(root(a)+'/contexte').json()['periode']
    post(c,a,'/clotures/z',{'periode_id':period['id'],'justification':'Acquis toujours non résolu'},409)
