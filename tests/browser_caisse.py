"""P4.4 Chromium au clavier : sessions, paiements acquis, fidélité, erreurs et lecture seule."""
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
    created_session=[None]
    def capture_session(response):
        if response.request.method=='POST' and response.url.endswith('/sessions'):
            try:created_session[0]=response.json()
            except Exception:pass
    page.on('response',capture_session)
    page.keyboard.press('Alt+Shift+Digit2');choose(modal().locator('[name=caisse_id]'),f['p4_caisse']);fill(modal().locator('[name=fond_initial]'),1000);save()
    use_session=page.get_by_role('button',name='Utiliser cette session',exact=True)
    if not use_session.count():
        organisation=page.evaluate('authState.me.organisation.id_organisation')
        user=page.evaluate('authState.me.utilisateur.id_utilisateur')
        sessions_response=page.request.get(url+'/api/caisses/organisations/'+organisation+'/sessions?page=1&page_size=10',headers={'X-Site-ID':f['site_id']})
        listed=sessions_response.json() if sessions_response.ok else {'http':sessions_response.status,'body':sessions_response.text()}
        raise AssertionError(f'Bouton Utiliser cette session absent; POST={created_session[0]!r}; user courant={user}; GET sessions={listed!r}')
    expect(use_session).to_be_visible()
    row=page.locator('#cash-waiting tr').filter(has_text=f['p44_vente_0'][:8]);activate(row.get_by_role('button'));expect(page.locator('#cash-title')).to_contain_text(f['p44_vente_0'][:8]);shot('p44-caisse-preparation.png')
    queue=page.locator('#cash-queue-filters [name=q]');fill(queue,f['p44_vente_0'][:8])
    activate(page.locator('#cash-queue-filters').get_by_role('button',name='Rechercher',exact=True));expect(page.locator('#cash-waiting tr')).to_have_count(1)
    activate(page.get_by_role('button',name='F12 · Actualiser',exact=True));expect(queue).to_have_value(f['p44_vente_0'][:8]);shot('p46-file-caisse-filtre.png')
    activate(page.get_by_role('button',name='Nouveau client',exact=True));fill(modal().locator('[name=nom]'),'élise fidélité');fill(modal().locator('[name=telephone]'),'070123456');save();expect(page.locator('#cash-selected-client')).to_contain_text('ÉLISE FIDÉLITÉ')
    activate(page.get_by_role('button',name='Ajouter / remplacer une carte',exact=True));fill(modal().locator('[name=code]'),'FIDELITE-QA-44');save()
    activate(page.get_by_role('button',name='Retirer la sélection',exact=True));page.keyboard.press('Alt+Shift+Digit3');fill(page.locator('#cash-client-search'),'FIDELITE-QA-44');expect(page.locator('#cash-clients button')).to_have_count(1);activate(page.locator('#cash-clients button'));expect(page.locator('#cash-selected-client')).to_contain_text('0 points')
    page.keyboard.press('Alt+Shift+Digit6');choose(modal().locator('[name=mode]'),'CARTE');fill(modal().locator('[name=montant]'),50);fill(modal().locator('[name=reference]'),'TERM-P44-QA');fill(modal().locator('[name=preuve]'),'Ticket terminal accepté vérifié au clavier');save()
    page.keyboard.press('Alt+Shift+Digit0');fill(modal().locator('[name=especes]'),1);modal().locator('[name=confirme]').focus();page.keyboard.press('Space');activate(modal().get_by_role('button',name='Enregistrer',exact=True));expect(modal().locator('.creation-dialog-error')).to_contain_text('intégralement');expect(modal().locator('[name=especes]')).to_have_value('1');shot('p44-reglement-erreur.png')
    modal().locator('[data-confirmation]').focus();page.keyboard.press('Space');fill(modal().locator('[name=especes]'),200);save();expect(page.locator('#cash-title')).to_contain_text('ENCAISSEE');expect(page.locator('#cash-receipt-summary')).to_contain_text('Points acquis 1');shot('p44-encaissement-fidelite.png')
    with page.expect_download() as dl:activate(page.get_by_role('button',name='Télécharger le reçu PDF',exact=True))
    dl.value.save_as('qa/p44-recu.pdf')
    receipts=page.locator('#cash-history-filters [name=q]');fill(receipts,f['p44_vente_0'][:8])
    activate(page.locator('#cash-history-filters').get_by_role('button',name='Rechercher',exact=True));expect(page.locator('#cash-history button')).to_have_count(1)
    expect(queue).to_have_value(f['p44_vente_0'][:8]);shot('p46-recu-recherche.png')
    activate(page.get_by_role('button',name='Barèmes fidélité',exact=True));expect(modal()).to_contain_text('ACQUISITION');shot('p44-baremes.png');page.keyboard.press('Escape')
    activate(page.get_by_role('button',name='Fermer ma session',exact=True));fill(modal().locator('[name=comptage_final]'),int(f['p44_total'])-50+1000);fill(modal().locator('[name=justification]'),'Fin de service recette');save()
    readonly=browser.new_context();rp=readonly.new_page();rp.on('pageerror',lambda e:errors.append(str(e)));login(rp,'caisse.lecture.qa');expect(rp.get_by_role('button',name='F2 · Ouvrir une session',exact=True)).to_have_count(0);expect(rp.get_by_role('button',name='Moyens de paiement',exact=True)).to_have_count(0);rp.locator('#cash-waiting tr').filter(has_text=f['p44_vente_1'][:8]).get_by_role('button').focus();rp.keyboard.press('Enter');expect(rp.locator('#cash-sale')).to_be_visible();expect(rp.get_by_role('button',name='F10 · Encaisser intégralement',exact=True)).to_have_count(0)
    status=rp.evaluate('''async org=>{const csrf=document.cookie.split('; ').find(x=>x.startsWith('neosys_csrf=')).split('=')[1];return (await fetch('/api/caisses/organisations/'+org+'/sessions',{method:'POST',headers:{'Content-Type':'application/json','X-CSRF-Token':decodeURIComponent(csrf),'X-Site-ID':document.querySelector('#sites').value},body:'{}'})).status}''',f['organisation_id']);assert status==403
    rp.screenshot(path='qa/p44-lecture-seule.png',full_page=True);assert not errors,errors;browser.close();print('P4.4 Chromium intégralement au clavier : sessions, modes, paiements mixtes/erreur, compte/carte, acquisition, reçu, lecture seule et 403 : OK')
