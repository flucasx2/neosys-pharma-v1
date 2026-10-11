"""Recette P4.5 Chromium exclusivement clavier, données synthétiques."""
import json
from pathlib import Path
from playwright.sync_api import sync_playwright,expect
f=json.loads(Path('/tmp/p1-browser-fixture.json').read_text());Path('qa').mkdir(exist_ok=True)
with sync_playwright() as p:
    browser=p.chromium.launch();context=browser.new_context(viewport={'width':1600,'height':1050},accept_downloads=True);page=context.new_page();errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
    def fill(target,value):target.focus();page.keyboard.press('Control+A');page.keyboard.insert_text(str(value))
    def activate(target):target.focus();page.keyboard.press('Enter')
    def modal():return page.locator('dialog[open]')
    def save():activate(modal().get_by_role('button',name='Enregistrer',exact=True));expect(modal()).to_have_count(0)
    def select(target,value):
        target.focus();opts=target.locator('option').all();index=next(i for i,o in enumerate(opts) if o.get_attribute('value')==value);page.keyboard.press('Home')
        for _ in range(index):page.keyboard.press('ArrowDown')
        page.keyboard.press('Tab')
    def tab(value):select(page.locator('#finance-genre'),value);expect(page.locator('#finance-rows')).to_be_visible()
    def logout():
        activate(page.get_by_role('button',name='Se déconnecter',exact=True));expect(page.locator('#login-panel')).to_be_visible();expect(page.locator('#app-shell')).to_be_hidden()
    def login(user):
        page.goto('http://127.0.0.1:8000/#administration/finance');expect(page.locator('#login-panel')).to_be_visible();fill(page.locator('#login-form [name=organisation_id]'),f['organisation_id']);fill(page.locator('#login-form [name=identifiant]'),user);fill(page.locator('#login-form [name=password]'),f['password']);activate(page.locator('#login-form button'));expect(page.locator('#app-shell')).to_be_visible();activate(page.locator('#nav-finance'));expect(page.locator('#finance-panel')).to_be_visible();expect(page.get_by_role('button',name='F12 · Actualiser',exact=True)).to_be_visible()
    login('caisse.qa');activate(page.locator('#nav-encaissement'));expect(page.get_by_role('button',name='F2 · Ouvrir une session',exact=True)).to_be_visible();page.keyboard.press('Alt+Shift+Digit2');select(modal().locator('[name=caisse_id]'),f['p4_caisse']);fill(modal().locator('[name=fond_initial]'),1000);save()
    activate(page.locator('#nav-finance'));expect(page.locator('#finance-session option').filter(has_text='OUVERTE')).to_have_count(1);select(page.locator('#finance-session'),page.locator('#finance-session option').filter(has_text='OUVERTE').get_attribute('value'));page.keyboard.press('Alt+Shift+Digit4');save();expect(page.locator('#finance-rows')).to_contain_text('X')
    with page.expect_download() as download:activate(page.get_by_role('button',name='PDF historique',exact=True).first)
    download.value.save_as('qa/p45-x.pdf');page.screenshot(path='qa/p45-cloture-x.png',full_page=True)
    activate(page.get_by_role('button',name='Nouveau transfert',exact=True));select(modal().locator('[name=coffre_id]'),f['p45_coffre']);fill(modal().locator('[name=montant]'),100);fill(modal().locator('[name=justification]'),'Dépôt réel de recette');save();tab('transferts');expect(page.locator('#finance-rows')).to_contain_text('DEMANDE')
    activate(page.get_by_role('button',name='Autoriser',exact=True));fill(modal().locator('[name=justification]'),'Autorisation habilitée');save();activate(page.get_by_role('button',name='Expédier',exact=True));fill(modal().locator('[name=justification]'),'Dérogation habilitée et auditée');save();expect(page.locator('#finance-rows')).to_contain_text('EN_TRANSIT');page.screenshot(path='qa/p45-fonds-transit.png',full_page=True)
    activate(page.get_by_role('button',name='Confirmer réception',exact=True));fill(modal().locator('[name=justification]'),'Même personne refusée');activate(modal().get_by_role('button',name='Enregistrer',exact=True));expect(modal().locator('.creation-dialog-error')).to_contain_text('différents');page.on('dialog',lambda d:d.accept());page.keyboard.press('Escape')
    logout();login('responsable.p45.qa');tab('transferts');activate(page.get_by_role('button',name='Confirmer réception',exact=True));fill(modal().locator('[name=justification]'),'Réception comptée par responsable distinct');save();expect(page.locator('#finance-rows')).to_contain_text('RECU')
    with page.expect_download() as download:activate(page.get_by_role('button',name='Justificatif PDF',exact=True))
    download.value.save_as('qa/p45-transfert.pdf')
    logout();login('caisse.qa');tab('ventes');expect(page.get_by_role('button',name='Créer un retour',exact=True)).not_to_have_count(0);activate(page.get_by_role('button',name='Créer un retour',exact=True).first);fill(modal().locator('[name=q_0]'),1);fill(modal().locator('[name=justification]'),'Produit remis pour contrôle');save();tab('quarantaine');expect(page.locator('#finance-rows')).to_contain_text('EN_CONTROLE');expect(page.locator('#finance-rows')).to_contain_text('vendable 0');page.screenshot(path='qa/p45-quarantaine.png',full_page=True)
    tab('retours');activate(page.get_by_role('button',name='Demander remboursement',exact=True).first);fill(modal().locator('[name=justification]'),'Remboursement historique par moyens originaux');save();tab('remboursements');activate(page.get_by_role('button',name='Autoriser',exact=True).first);fill(modal().locator('[name=justification]'),'Responsable habilité valide');save();activate(page.get_by_role('button',name='Confirmer exécution',exact=True).first)
    for field in modal().locator('input[name^=ref_]').all():fill(field,'REMBOURSEMENT-P45-QA')
    for field in modal().locator('textarea[name^=preuve_]').all():fill(field,'Justificatif indépendant de restitution constatée')
    fill(modal().locator('[name=justification]'),'Restitution effective');modal().locator('[name=confirme]').focus();page.keyboard.press('Space');save();expect(page.locator('#finance-rows')).to_contain_text('EXECUTE');page.screenshot(path='qa/p45-remboursement.png',full_page=True)
    with page.expect_download() as download:activate(page.get_by_role('button',name='Justificatif PDF',exact=True).first)
    download.value.save_as('qa/p45-remboursement.pdf')
    page.keyboard.press('Alt+Shift+Digit8');fill(modal().locator('[name=justification]'),'Z prématurée');modal().locator('[name=confirme]').focus();page.keyboard.press('Space');activate(modal().get_by_role('button',name='Enregistrer',exact=True));expect(modal().locator('.creation-dialog-error')).to_contain_text('Fermer toutes');page.keyboard.press('Escape')
    activate(page.locator('#nav-encaissement'));activate(page.get_by_role('button',name='Fermer ma session',exact=True));# Take the exact displayed server amount, no invented count.
    expected=page.locator('#cash-sessions').inner_text();import re
    n=re.search(r'Espèces attendues ([\d\s\u202f\xa0]+) FCFA',expected);assert n,expected
    fill(modal().locator('[name=comptage_final]'),re.sub(r'\D','',n.group(1)));fill(modal().locator('[name=justification]'),'Fin de service comptée');save()
    activate(page.locator('#nav-finance'));page.keyboard.press('Alt+Shift+Digit8');fill(modal().locator('[name=justification]'),'Clôture après contrôles');modal().locator('[name=confirme]').focus();page.keyboard.press('Space');save();tab('clotures');expect(page.locator('#finance-rows')).to_contain_text('Z');expect(page.locator('#finance-period')).to_contain_text('Période Z 2');page.screenshot(path='qa/p45-cloture-z.png',full_page=True)
    with page.expect_download() as download:activate(page.locator('#finance-rows tr').filter(has_text='Z').get_by_role('button',name='PDF historique',exact=True).first)
    download.value.save_as('qa/p45-z.pdf')
    logout();login('caisse.lecture.qa');expect(page.get_by_role('button',name='F8 · Clôture Z',exact=True)).to_have_count(0);expect(page.get_by_role('button',name='Nouveau transfert',exact=True)).to_have_count(0);page.screenshot(path='qa/p45-lecture-seule.png',full_page=True)
    assert not errors,errors;browser.close();print('P4.5 Chromium clavier : X/PDF, transferts/séparation/transit/réception, retour/quarantaine, remboursement/PDF, Z prématurée/fermée, nouvelle période et lecture seule : OK')
