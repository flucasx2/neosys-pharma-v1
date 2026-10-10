"""Parcours P4 entièrement au clavier, y compris approbations dans deux sessions."""
import json
from pathlib import Path
from playwright.sync_api import sync_playwright,expect
f=json.loads(Path('/tmp/p1-browser-fixture.json').read_text());url='http://127.0.0.1:8000';Path('qa').mkdir(exist_ok=True)
with sync_playwright() as p:
    browser=p.chromium.launch();operator=browser.new_context(viewport={'width':1600,'height':1000});page=operator.new_page();errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
    def key_activate(locator):locator.focus();page.keyboard.press('Enter')
    def type_field(locator,value):locator.focus();page.keyboard.press('Control+A');page.keyboard.type(str(value))
    def choice(locator,value):
        # Native select driven through Home/ArrowDown/Enter, never select_option.
        locator.focus();page.keyboard.press('Home');values=locator.locator('option').evaluate_all('(xs)=>xs.map(x=>x.value)');assert value in values,(value,values)
        for _ in range(values.index(value)):page.keyboard.press('ArrowDown')
        page.keyboard.press('Tab')
    def login(page_,name):
        page_.goto(url);form=page_.locator('#login-form')
        for field,value in [('organisation_id',f['organisation_id']),('identifiant',name),('password',f['password'])]:
            form.locator('[name='+field+']').focus();page_.keyboard.type(value)
        form.locator('button').focus();page_.keyboard.press('Enter');expect(page_.locator('#app-shell')).to_be_visible()
        page_.locator('#nav-vente').focus();page_.keyboard.press('Enter');expect(page_.locator('#p4-list')).to_have_attribute('aria-busy','false')
    def modal():return page.locator('dialog[open]').last
    def save():key_activate(modal().get_by_role('button',name='Enregistrer',exact=True));expect(page.locator('dialog[open]')).to_have_count(0)
    def shortcut(n):page.keyboard.press('Alt+Shift+Digit'+str(n))
    def shot(name):page.screenshot(path='qa/'+name,full_page=True)
    login(page,'vente.qa');shortcut(2);expect(modal()).to_be_visible();page.keyboard.press('Escape');expect(page.locator('dialog[open]')).to_have_count(0);shortcut(2);expect(modal()).to_be_visible();expect(modal().locator('[name=mode]')).to_be_focused()
    choice(modal().locator('[name=mode]'),'SANS_TIERS');choice(modal().locator('[name=emplacement_id]'),f['location_id']);choice(modal().locator('[name=poste_id]'),f['p4_poste']);save()
    # Scanner unique barcode selects internal product/pack IDs and focuses quantity.
    shortcut(3);type_field(modal().locator('[name=recherche]'),'8812345678901');page.keyboard.press('Enter');expect(modal().locator('[name=quantite]')).to_be_focused();type_field(modal().locator('[name=quantite]'),'3');save();expect(page.locator('#p4-lines tr')).to_have_count(1);expect(page.locator('#p4-totals')).to_contain_text('300 FCFA')
    shortcut(5);expect(modal()).to_contain_text('physique 30');shot('p4-stock-lots.png');page.keyboard.press('Escape');expect(page.locator('dialog[open]')).to_have_count(0)
    # Partial designation with several packs requires explicit choice.
    shortcut(3);type_field(modal().locator('[name=recherche]'),'préparation vente');page.keyboard.press('Enter');expect(modal().locator('[name=conditionnement_id]')).to_be_focused();choice(modal().locator('[name=conditionnement_id]'),f['p4_pack']);type_field(modal().locator('[name=quantite]'),'2');save();expect(page.locator('#p4-lines tr')).to_have_count(2)
    # Edit error preserves quantity, cancel warns before discarding.
    page.locator('#p4-lines tr').first.focus();shortcut(4);expect(modal().locator('[name=quantite]')).to_have_value('3');type_field(modal().locator('[name=quantite]'),'999');key_activate(modal().get_by_role('button',name='Enregistrer',exact=True));expect(modal().locator('.creation-dialog-error')).to_be_visible();expect(modal().locator('[name=quantite]')).to_have_value('999')
    page.once('dialog',lambda d:d.accept());page.keyboard.press('Escape');expect(page.locator('dialog[open]')).to_have_count(0)
    page.locator('#p4-lines tr').last.focus();page.keyboard.press('Delete');save();expect(page.locator('#p4-lines tr')).to_have_count(1)
    # Line authorization local: manager enters own password, operator remains signed in.
    shortcut(6);type_field(modal().locator('[name=valeur]'),'10');type_field(modal().locator('[name=justification]'),'Demande ligne au clavier');save();expect(page.locator('#p4-totals')).to_contain_text('300 FCFA')
    shortcut(0);expect(page.locator('#p4-message')).to_contain_text('attente')
    key_activate(page.get_by_role('button',name='Autorisation locale du responsable',exact=True));type_field(modal().locator('[name=identifiant]'),'responsable.qa');type_field(modal().locator('[name=password]'),'incorrect');choice(modal().locator('[name=autoriser]'),'true');type_field(modal().locator('[name=justification]'),'Contrôle local du responsable');key_activate(modal().get_by_role('button',name='Enregistrer',exact=True));expect(modal().locator('.creation-dialog-error')).to_contain_text('refusée');expect(page.locator('#identity-name')).to_contain_text('vente.qa');expect(modal().locator('[name=password]')).to_have_value('');type_field(modal().locator('[name=password]'),f['password']);save();expect(page.locator('#p4-totals')).to_contain_text('270 FCFA');expect(page.locator('#p4-discounts')).to_contain_text('responsable.qa');shot('p4-remise-ligne-autorisee.png')
    # Global request is approved remotely from an independent browser session.
    shortcut(7);type_field(modal().locator('[name=valeur]'),'10');type_field(modal().locator('[name=justification]'),'Demande globale distante');save()
    manager_context=browser.new_context();manager_page=manager_context.new_page();login(manager_page,'responsable.qa');manager_page.get_by_role('button',name='Examiner / décider').focus();manager_page.keyboard.press('Enter');dialog=manager_page.locator('dialog[open]');select=dialog.locator('[name=autoriser]');select.focus();manager_page.keyboard.press('Home');manager_page.keyboard.press('ArrowDown');manager_page.keyboard.press('Tab');dialog.locator('[name=justification]').focus();manager_page.keyboard.type('Validation distante du responsable');dialog.get_by_role('button',name='Enregistrer',exact=True).focus();manager_page.keyboard.press('Enter');expect(manager_page.locator('dialog[open]')).to_have_count(0);manager_page.screenshot(path='qa/p4-autorisation-distante.png',full_page=True)
    key_activate(page.get_by_role('button',name='F12 · Actualiser',exact=True));expect(page.locator('#p4-totals')).to_contain_text('243 FCFA');shot('p4-preparation-remises-cumulees.png')
    shortcut(8);expect(page.locator('#p4-title')).to_contain_text('EN_ATTENTE');shortcut(9);expect(page.locator('#p4-title')).to_contain_text('PREPARATION');shortcut(0);expect(page.locator('#p4-title')).to_contain_text('VALIDEE_PREPARATION')
    page.keyboard.press('Alt+Shift+Minus');choice(modal().locator('[name=caisse_id]'),f['p4_caisse']);save();expect(page.locator('#p4-title')).to_contain_text('TRANSMISE');shot('p4-transmission-sans-encaissement.png')
    # Limits UI and keyboard cancellation, then readonly direct backend refusal.
    key_activate(page.get_by_role('button',name='Plafonds de remise',exact=True));expect(modal()).to_contain_text('Au moins un plafond');expect(modal().locator('[name=actif]')).to_be_checked();shot('p4-plafonds.png');page.keyboard.press('Escape')
    readonly=browser.new_context();rp=readonly.new_page();login(rp,'vente.lecture.qa');expect(rp.get_by_role('button',name='F2 · Nouvelle préparation',exact=True)).to_have_count(0);rp.locator('#p4-list button').first.focus();rp.keyboard.press('Enter');expect(rp.locator('#p4-current')).to_be_visible();expect(rp.get_by_role('button',name='F3 · Ajouter',exact=True)).to_have_count(0)
    status=rp.evaluate('''async org=>{const csrf=document.cookie.split('; ').find(x=>x.startsWith('neosys_csrf=')).split('=')[1];return (await fetch('/api/ventes/organisations/'+org,{method:'POST',headers:{'Content-Type':'application/json','X-CSRF-Token':decodeURIComponent(csrf),'X-Site-ID':document.querySelector('#sites').value},body:'{}'})).status}''',f['organisation_id']);assert status==403
    rp.screenshot(path='qa/p4-lecture-seule.png',full_page=True)
    assert not errors,errors;browser.close();print('P4.2 Chromium clavier : modes, scanner, conditionnements, stocks, lignes/erreur/annulation, remises locales/distantes/cumul, attente/reprise/validation/transmission, plafonds et lecture seule : OK')
