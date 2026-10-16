"""Recette Chromium P4.4/P4-C.4 : caisse individuelle, groupée et fidélité par vente."""
import json
from pathlib import Path
from playwright.sync_api import sync_playwright,expect
f=json.loads(Path('/tmp/p1-browser-fixture.json').read_text());url='http://127.0.0.1:8000';Path('qa').mkdir(exist_ok=True)
with sync_playwright() as p:
    browser=p.chromium.launch();context=browser.new_context(viewport={'width':1600,'height':1050},accept_downloads=True);page=context.new_page();errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
    def activate(l):l.focus();page.keyboard.press('Enter')
    def fill(l,v):l.focus();page.keyboard.press('Control+A');page.keyboard.type(str(v))
    def choose(l,v):
        l.focus();page.keyboard.press('Home');values=l.locator('option').evaluate_all('(xs)=>xs.map(x=>x.value)');assert v in values
        for _ in range(values.index(v)):page.keyboard.press('ArrowDown')
        page.keyboard.press('Tab')
    def login(pg,user):
        pg.goto(url)
        for name,value in [('organisation_id',f['organisation_id']),('identifiant',user),('password',f['password'])]:pg.locator('#login-form [name='+name+']').focus();pg.keyboard.type(value)
        pg.locator('#login-form button').focus();pg.keyboard.press('Enter');expect(pg.locator('#app-shell')).to_be_visible();pg.locator('#nav-encaissement').focus();pg.keyboard.press('Enter');expect(pg.locator('#cash-panel')).to_be_visible();expect(pg.get_by_role('button',name='F12 · Actualiser',exact=True)).to_be_visible()
    def modal():return page.locator('dialog[open]').last
    def save():activate(modal().get_by_role('button',name='Enregistrer',exact=True));expect(page.locator('dialog[open]')).to_have_count(0);expect(page.locator('#cash-panel')).to_have_attribute('aria-busy','false')
    def shot(name):page.screenshot(path='qa/'+name,full_page=True)
    login(page,'caisse.qa')
    activate(page.get_by_role('button',name='Moyens de paiement',exact=True));
    for code in ['ESPECES','CARTE']:
        modal().locator('[name='+code+']').focus();page.keyboard.press('Space')
    save()
    page.keyboard.press('Alt+Shift+Digit2');expect(modal()).to_be_visible();page.keyboard.press('Escape');expect(page.locator('dialog[open]')).to_have_count(0)
    page.keyboard.press('Alt+Shift+Digit2');choose(modal().locator('[name=caisse_id]'),f['p4_caisse']);fill(modal().locator('[name=fond_initial]'),1000);save();expect(page.get_by_role('button',name='Utiliser cette session',exact=True)).to_be_visible()
    # P4-C.4 : interactions visuelles avec réponses groupe simulées. Aucune
    # finalisation ni réussite financière n'est simulée côté navigateur.
    from uuid import uuid4
    from urllib.parse import urlparse
    grouped = {'id': str(uuid4()), 'revision': 1, 'etat': 'BROUILLON', 'ventes': [], 'reglements': [], 'allocations': []}
    group_session = page.evaluate("async()=> (await cashRequest('/sessions?page=1&page_size=10')).items.find(x=>x.etat==='OUVERTE').id")
    fake_confirmation = str(uuid4()); sales_cache = {}
    def mock_group(route):
        request = route.request; path = urlparse(request.url).path.split('/groupes', 1)[1]
        body = request.post_data_json if request.post_data else {}
        if request.method == 'GET' and path == '/activation':
            route.fulfill(json={'finalisation_active':False}); return
        if request.method == 'POST' and path == '':
            grouped.update({'revision':1,'etat':'BROUILLON','session_id':group_session,'ventes':[],'reglements':[],'allocations':[]})
            route.fulfill(status=201,json={'dossier':{'id':grouped['id'],'revision':1,'etat':'BROUILLON','session_id':group_session},'ventes':[],'reglements':[],'allocations':[],'totaux':{'du_xaf':'0','net_regle_xaf':'0','alloue_xaf':'0','reste_xaf':'0','allocation_valide':False}}); return
        if request.method == 'PUT' and path.endswith('/ventes'):
            grouped['ventes']=[{'vente_id':row['vente_id'],'revision_vente':row['revision'],'montant_du':str(sales_cache[row['vente_id']]['totaux']['ttc']),'ordre':i+1} for i,row in enumerate(body['ventes'])]; grouped['revision']+=1
        elif request.method == 'PUT' and path.endswith('/reglements'):
            grouped['reglements']=[{**row,'id':str(uuid4()),'ordre':i+1} for i,row in enumerate(body['reglements'])]; grouped['revision']+=1
        elif request.method == 'PUT' and path.endswith('/allocations'):
            grouped['allocations']=body['allocations']; grouped['revision']+=1
        elif request.method == 'POST' and path.endswith('/abandonner'):
            grouped['etat']='ABANDONNE'; grouped['revision']+=1
        elif request.method == 'GET' and path.endswith('/allocations/proposition'):
            rest={row['vente_id']:int(row['montant_du']) for row in grouped['ventes']}; out=[]
            for payment in grouped['reglements']:
                amount=int(payment['montant'])-int(payment.get('rendu',0))
                for sale in grouped['ventes']:
                    allocated=min(amount,rest[sale['vente_id']])
                    if allocated: out.append({'reglement_id':payment['id'],'vente_id':sale['vente_id'],'montant':str(allocated)}); rest[sale['vente_id']]-=allocated; amount-=allocated
                    if not amount: break
            route.fulfill(json=out); return
        elif request.method == 'POST' and path.endswith('/finaliser'):
            route.fulfill(status=503,json={'detail':'Finalisation désactivée.'}); return
        due=sum(int(row['montant_du']) for row in grouped['ventes']); net=sum(int(row['montant'])-int(row.get('rendu',0)) for row in grouped['reglements']); allocated=sum(int(row['montant']) for row in grouped['allocations'])
        data={'dossier':{'id':grouped['id'],'revision':grouped['revision'],'etat':grouped['etat'],'session_id':group_session},'ventes':grouped['ventes'],'reglements':grouped['reglements'],'allocations':grouped['allocations'],'totaux':{'du_xaf':str(due),'net_regle_xaf':str(net),'alloue_xaf':str(allocated),'reste_xaf':str(due-net),'allocation_valide':bool(grouped['allocations']) and allocated==net==due}}
        route.fulfill(status=201 if request.method=='POST' else 200,json=data)
    def add_mock_confirmation(route):
        response=route.fetch(); data=response.json(); sale_id=urlparse(route.request.url).path.rsplit('/',1)[-1]; sales_cache[sale_id]=data
        if sale_id==f['p44_vente_0']: data['confirmations']=[{'id':fake_confirmation,'mode':'CARTE','montant':'50','reference':'CARTE-MOCK-C44'}]
        route.fulfill(response=response,json=data)
    page.on('dialog',lambda dialog:dialog.accept())
    # ``*`` ne traverse pas les slashs de sous-routes Playwright : utiliser
    # ``**`` après /groupes pour intercepter aussi /{id}/ventes, /allocations…
    page.route('**/api/caisses/organisations/*/groupes**',mock_group)
    page.route('**/api/caisses/organisations/*/ventes/*',add_mock_confirmation)
    activate(page.get_by_role('button',name='Encaissement multiple',exact=True)); expect(page.locator('#cash-group-sales tr')).to_have_count(6)
    for count,sale_id in enumerate([f['p44_vente_0'],f['p44_vente_1']],start=1):
        page.get_by_role('checkbox',name='Sélectionner la vente '+sale_id[:8]).check()
        expect(page.locator('#cash-group-selected-total')).to_contain_text(f'{count} ticket(s)')
    activate(page.get_by_role('button',name='Créer un brouillon groupé',exact=True)); expect(page.locator('#cash-group-status')).to_contain_text('BROUILLON')
    no_client_loyalty=page.locator('#cash-group-loyalty-'+f['p44_vente_0']);eligible_loyalty=page.locator('#cash-group-loyalty-'+f['p44_vente_1'])
    expect(no_client_loyalty).to_contain_text('Aucun client associé');expect(no_client_loyalty.locator('input')).to_have_count(0)
    expect(eligible_loyalty).to_contain_text('Cliente fidélité A');expect(eligible_loyalty.get_by_role('checkbox')).to_be_visible()
    activate(page.get_by_role('button',name='Ajouter un règlement',exact=True)); page.locator('[aria-label="Mode règlement 1"]').select_option('CARTE'); page.locator('[aria-label="Montant règlement 1"]').fill('50'); page.locator('[aria-label="Confirmation règlement 1"]').select_option(fake_confirmation)
    activate(page.get_by_role('button',name='Ajouter un règlement',exact=True)); page.locator('[aria-label="Mode règlement 2"]').select_option('ESPECES'); page.locator('[aria-label="Montant règlement 2"]').fill(str(2*int(f['p44_total'])-50))
    activate(page.get_by_role('button',name='Enregistrer les règlements',exact=True)); expect(page.locator('#cash-group-panel')).to_have_attribute('aria-busy','false')
    assert len(grouped['ventes']) == 2 and len(grouped['reglements']) == 2, f"Réponse simulée inattendue avant ventilation: {grouped}"
    page.evaluate("window.__groupConfirmMessages=[]; window.confirm=(message)=>{window.__groupConfirmMessages.push(message); return true;}")
    activate(page.get_by_role('button',name='Proposer et enregistrer la ventilation automatique',exact=True))
    # Observe the rendered result; evaluating a polling predicate violates the app CSP.
    expect(page.locator('#cash-group-allocation-status')).to_contain_text('ventilation équilibrée')
    assert grouped['allocations'], f"La proposition simulée n'a pas été enregistrée: {grouped}"
    allocation = page.locator('#cash-group-allocation-body input').first; original_allocation = int(allocation.input_value()); allocation.fill(str(original_allocation-1)); activate(page.get_by_role('button',name='Enregistrer la ventilation manuelle',exact=True)); expect(page.locator('#cash-message')).to_contain_text('Ventilation invalide')
    allocation.fill(str(original_allocation)); activate(page.get_by_role('button',name='Enregistrer la ventilation manuelle',exact=True)); expect(page.locator('#cash-group-allocation-status')).to_contain_text('ventilation équilibrée')
    expect(page.locator('#cash-group-finalise')).to_be_disabled(); expect(page.locator('#cash-group-payments')).to_contain_text('CARTE'); shot('p4c4-brouillon-groupe.png')
    activate(page.get_by_role('button',name='Abandonner le brouillon',exact=True)); expect(page.locator('#cash-group-status')).to_contain_text('ABANDONNE')
    activate(page.get_by_role('button',name='Encaissement simple',exact=True)); expect(page.locator('#cash-group-selected-total')).to_contain_text('0 ticket(s)'); expect(page.locator('#cash-waiting').locator('xpath=ancestor::article[1]')).to_be_visible()
    page.unroute('**/api/caisses/organisations/*/groupes**'); page.unroute('**/api/caisses/organisations/*/ventes/*')
    # Recette PostgreSQL jetable : finalisation réelle via P4-C.3. Le premier
    # essai est refusé au transport; la reprise après rechargement doit rejouer
    # exactement la même clé et afficher les reçus réels du backend.
    activate(page.get_by_role('button',name='Encaissement multiple',exact=True))
    for sale_id in [f['p44_vente_1'],f['p44_vente_2'],f['p44_vente_3']]:
        page.get_by_role('checkbox',name='Sélectionner la vente '+sale_id[:8]).check()
    expect(page.locator('#cash-group-selected-total')).to_contain_text('3 ticket(s)')
    activate(page.get_by_role('button',name='Créer un brouillon groupé',exact=True)); expect(page.locator('#cash-group-status')).to_contain_text('BROUILLON')
    expect(page.locator('#cash-group-draft-sales tr')).to_have_count(3)
    first_loyalty=page.locator('#cash-group-loyalty-'+f['p44_vente_1']);third_loyalty=page.locator('#cash-group-loyalty-'+f['p44_vente_3']);blocked_loyalty=page.locator('#cash-group-loyalty-'+f['p44_vente_2'])
    expect(first_loyalty).to_contain_text('Cliente fidélité A');expect(third_loyalty).to_contain_text('Cliente fidélité A')
    expect(blocked_loyalty).to_contain_text('dette');expect(blocked_loyalty.locator('input')).to_have_count(0)
    first_loyalty.get_by_role('checkbox').check();third_loyalty.get_by_role('checkbox').check()
    due=3*int(f['p44_total']);first_payment=due//2
    activate(page.get_by_role('button',name='Ajouter un règlement',exact=True));page.locator('[aria-label="Montant règlement 1"]').fill(str(first_payment))
    activate(page.get_by_role('button',name='Ajouter un règlement',exact=True));page.locator('[aria-label="Montant règlement 2"]').fill(str(due-first_payment))
    activate(page.get_by_role('button',name='Enregistrer les règlements',exact=True));activate(page.get_by_role('button',name='Proposer et enregistrer la ventilation automatique',exact=True));expect(page.locator('#cash-group-allocation-status')).to_contain_text('ventilation équilibrée')
    expect(page.locator('#cash-group-finalise')).to_be_enabled();assert 'autorisé' in page.locator('#cash-group-finalisation-note').inner_text()
    finalise_calls=[];finalise_payloads=[]
    def fail_first_finalisation(route):
        finalise_payloads.append(route.request.post_data_json);finalise_calls.append(route.request.post_data_json['cle'])
        if len(finalise_calls)==1: route.fulfill(status=503,json={'detail':'Refus de transport simulé pour recette idempotence.'})
        elif len(finalise_calls)==2: route.fulfill(status=409,json={'detail':'Révision modifiée par un autre opérateur.'})
        else: route.continue_()
    page.route('**/api/caisses/organisations/*/groupes/*/finaliser',fail_first_finalisation)
    page.locator('#cash-group-finalise').evaluate('(button)=>{button.click();button.click()}')
    expect(page.locator('#cash-message')).to_contain_text('Refus de transport simulé')
    assert len(finalise_calls)==1
    dossier_id=page.locator('#cash-group-resume-id').input_value()
    page.reload();expect(page.locator('#app-shell')).to_be_visible();activate(page.get_by_role('button',name='Utiliser cette session',exact=True));activate(page.get_by_role('button',name='Encaissement multiple',exact=True))
    expect(page.locator('#cash-group-resume-id')).to_have_value(dossier_id)
    activate(page.get_by_role('button',name='Consulter le dossier',exact=True));expect(page.locator('#cash-group-status')).to_contain_text('BROUILLON')
    activate(page.locator('#cash-group-finalise'));expect(page.locator('#cash-message')).to_contain_text('modification concurrente');assert len(finalise_calls)==2
    activate(page.locator('#cash-group-finalise'));expect(page.locator('#cash-group-status')).to_contain_text('FINALISE');assert len(finalise_calls)==3 and len(set(finalise_calls))==1
    expected_fidelity=[{'vente_id':f['p44_vente_1'],'compte_id':f['p44_account_a']},{'vente_id':f['p44_vente_3'],'compte_id':f['p44_account_a']}]
    for payload in finalise_payloads:
        assert [{key:item[key] for key in ('vente_id','compte_id')} for item in payload['fidelite']]==expected_fidelity
        assert all(item['revision_compte']==f['p44_account_a_revision'] for item in payload['fidelite'])
    assert all(payload==finalise_payloads[0] for payload in finalise_payloads)
    expect(page.locator('#cash-group-receipts')).to_be_visible();expect(page.locator('#cash-group-receipt-actions button')).to_have_count(4)
    receipt_labels=page.locator('#cash-group-receipt-actions button').all_inner_texts()
    points_per_sale=int(f['p44_total'])//100
    assert sum(f'{points_per_sale} point(s) · Cliente fidélité A' in label for label in receipt_labels)==2
    assert any('sans fidélité' in label for label in receipt_labels)
    accounts=page.evaluate('''async ids=>Promise.all(ids.map(async id=>await cashRequest('/fidelite/'+id)))''',[f['p44_account_a'],f['p44_account_b']])
    assert accounts[0]['points']==2*points_per_sale and accounts[1]['points']==0 and accounts[1]['dette']=='1'
    with page.expect_response('**/groupes/*/recu.pdf') as group_pdf_response: activate(page.get_by_role('button',name='Ouvrir le reçu collectif',exact=True))
    assert group_pdf_response.value.status==200 and group_pdf_response.value.headers.get('content-type','').startswith('application/pdf')
    individual_receipt=page.locator('#cash-group-receipt-actions button').nth(1)
    with page.expect_response('**/recus/*/pdf') as individual_pdf_response: activate(individual_receipt)
    assert individual_pdf_response.value.status==200 and individual_pdf_response.value.headers.get('content-type','').startswith('application/pdf')
    page.unroute('**/api/caisses/organisations/*/groupes/*/finaliser')
    activate(page.get_by_role('button',name='Encaissement simple',exact=True))
    row=page.locator('#cash-waiting tr').filter(has_text=f['p44_vente_0'][:8]);activate(row.get_by_role('button'));expect(page.locator('#cash-title')).to_contain_text(f['p44_vente_0'][:8]);shot('p44-caisse-preparation.png')
    activate(page.get_by_role('button',name='Nouveau client',exact=True));fill(modal().locator('[name=nom]'),'élise fidélité');fill(modal().locator('[name=telephone]'),'070123456');save();expect(page.locator('#cash-selected-client')).to_contain_text('ÉLISE FIDÉLITÉ')
    activate(page.get_by_role('button',name='Ajouter / remplacer une carte',exact=True));fill(modal().locator('[name=code]'),'FIDELITE-QA-44');save()
    activate(page.get_by_role('button',name='Retirer la sélection',exact=True));page.keyboard.press('Alt+Shift+Digit3');fill(page.locator('#cash-client-search'),'FIDELITE-QA-44');expect(page.locator('#cash-clients button')).to_have_count(1);activate(page.locator('#cash-clients button'));expect(page.locator('#cash-selected-client')).to_contain_text('0 points')
    page.keyboard.press('Alt+Shift+Digit6');choose(modal().locator('[name=mode]'),'CARTE');fill(modal().locator('[name=montant]'),50);fill(modal().locator('[name=reference]'),'TERM-P44-QA');fill(modal().locator('[name=preuve]'),'Ticket terminal accepté vérifié au clavier');save()
    page.keyboard.press('Alt+Shift+Digit0');fill(modal().locator('[name=especes]'),1);modal().locator('[name=confirme]').focus();page.keyboard.press('Space');activate(modal().get_by_role('button',name='Enregistrer',exact=True));expect(modal().locator('.creation-dialog-error')).to_contain_text('intégralement');expect(modal().locator('[name=especes]')).to_have_value('1');shot('p44-reglement-erreur.png')
    modal().locator('[data-confirmation]').focus();page.keyboard.press('Space');fill(modal().locator('[name=especes]'),200);save();expect(page.locator('#cash-title')).to_contain_text('ENCAISSEE');expect(page.locator('#cash-receipt-summary')).to_contain_text('Points acquis 1');shot('p44-encaissement-fidelite.png')
    with page.expect_download() as dl:activate(page.get_by_role('button',name='Télécharger le reçu PDF',exact=True))
    dl.value.save_as('qa/p44-recu.pdf')
    activate(page.get_by_role('button',name='Barèmes fidélité',exact=True));expect(modal()).to_contain_text('ACQUISITION');shot('p44-baremes.png');page.keyboard.press('Escape')
    activate(page.get_by_role('button',name='Fermer ma session',exact=True));fill(modal().locator('[name=comptage_final]'),1000+3*int(f['p44_total'])+int(f['p44_total'])-50);fill(modal().locator('[name=justification]'),'Fin de service recette');save()
    readonly=browser.new_context();rp=readonly.new_page();rp.on('pageerror',lambda e:errors.append(str(e)));login(rp,'caisse.lecture.qa');expect(rp.get_by_role('button',name='F2 · Ouvrir une session',exact=True)).to_have_count(0);expect(rp.get_by_role('button',name='Moyens de paiement',exact=True)).to_have_count(0);rp.locator('#cash-waiting tr').filter(has_text=f['p44_vente_4'][:8]).get_by_role('button').focus();rp.keyboard.press('Enter');expect(rp.locator('#cash-sale')).to_be_visible();expect(rp.get_by_role('button',name='F10 · Encaisser intégralement',exact=True)).to_have_count(0)
    status=rp.evaluate('''async org=>{const csrf=document.cookie.split('; ').find(x=>x.startsWith('neosys_csrf=')).split('=')[1];return (await fetch('/api/caisses/organisations/'+org+'/sessions',{method:'POST',headers:{'Content-Type':'application/json','X-CSRF-Token':decodeURIComponent(csrf),'X-Site-ID':document.querySelector('#sites').value},body:'{}'})).status}''',f['organisation_id']);assert status==403
    rp.screenshot(path='qa/p44-lecture-seule.png',full_page=True);assert not errors,errors;browser.close();print('P4.4/P4-C.4 Chromium : parcours individuel, groupé et fidélité par vente : OK')
