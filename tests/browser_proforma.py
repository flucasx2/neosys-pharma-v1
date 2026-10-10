"""P4.3 intégralement au clavier : versions, PDF figé, reprise aux tarifs courants et readonly."""
import json
from pathlib import Path
from datetime import date,timedelta
from uuid import UUID,uuid4
from playwright.sync_api import sync_playwright,expect
from sqlalchemy import select
from neosys_pharma.infrastructure.database import SessionLocal
from neosys_pharma.infrastructure.tarification_models import TarifProduitSiteModel
from neosys_pharma.application.catalogue_service import CatalogueService
from neosys_pharma.application.tarification_service import TarificationService
from neosys_pharma.infrastructure.catalogue_repository import SqlAlchemyCatalogueRepository
from neosys_pharma.domain.tarification import TarifProduitSite
f=json.loads(Path('/tmp/p1-browser-fixture.json').read_text());url='http://127.0.0.1:8000';Path('qa').mkdir(exist_ok=True)
with sync_playwright() as p:
    browser=p.chromium.launch();context=browser.new_context(viewport={'width':1600,'height':1000});page=context.new_page();errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
    def activate(locator):locator.focus();page.keyboard.press('Enter')
    def field(locator,value):locator.focus();page.keyboard.press('Control+A');page.keyboard.type(str(value))
    def choice(locator,value):
        locator.focus();page.keyboard.press('Home');values=locator.locator('option').evaluate_all('(xs)=>xs.map(x=>x.value)');assert value in values
        for _ in range(values.index(value)):page.keyboard.press('ArrowDown')
        page.keyboard.press('Tab')
    def login(name):
        page.goto(url);form=page.locator('#login-form')
        for name_,value in [('organisation_id',f['organisation_id']),('identifiant',name),('password',f['password'])]:field(form.locator('[name='+name_+']'),value)
        activate(form.locator('button'));expect(page.locator('#app-shell')).to_be_visible();activate(page.locator('#nav-proforma'));expect(page.locator('#proforma-panel')).to_be_visible();expect(page.locator('#pf-list')).to_have_attribute('aria-busy','false')
    def modal():return page.locator('dialog[open]').last
    def save():
        activate(modal().get_by_role('button',name='Enregistrer',exact=True));expect(page.locator('dialog[open]')).to_have_count(0);expect(page.locator('#proforma-panel')).to_have_attribute('aria-busy','false')
    def shortcut(key):expect(page.locator('#proforma-panel')).to_have_attribute('aria-busy','false');page.keyboard.press('Alt+Shift+'+key)
    def api(path,method='GET',body=None):return page.evaluate("""async ({path,method,body})=>{const r=await authFetch(proformaRoot()+path,{method,body:body?JSON.stringify(body):undefined});return {status:r.status,body:await r.json()};}""",{'path':path,'method':method,'body':body})
    def inventory():return page.evaluate("""async()=>{const r=await authFetch(venteRoot()+`/stocks?emplacement_id=${authState.emplacement||document.querySelector('#emplacements').value}&conditionnement_id="""+f['p4_pack']+"""`);return (await r.json()).totaux;}""")
    login('vente.qa');before=inventory()
    shortcut('Digit2');page.keyboard.press('Escape');expect(page.locator('dialog[open]')).to_have_count(0)
    shortcut('Digit2');choice(modal().locator('[name=emplacement_id]'),f['location_id']);field(modal().locator('[name=nom]'),'Client Élodie');save();expect(page.locator('#pf-title')).to_contain_text('BROUILLON')
    shortcut('Digit3');field(modal().locator('[name=recherche]'),'8812345678901');page.keyboard.press('Enter');expect(modal().locator('[name=quantite]')).to_be_focused();field(modal().locator('[name=quantite]'),'3');save();expect(page.locator('#pf-totals')).to_contain_text('300 FCFA');assert inventory()==before
    shortcut('Digit4');field(modal().locator('[name=quantite]'),'0');activate(modal().get_by_role('button',name='Enregistrer',exact=True));expect(modal()).to_be_visible();expect(modal().locator('[name=quantite]')).to_have_value('0');page.once('dialog',lambda d:d.accept());page.keyboard.press('Escape');expect(page.locator('dialog[open]')).to_have_count(0)
    shortcut('Digit7');field(modal().locator('[name=valeur]'),'10');field(modal().locator('[name=justification]'),'Proforma remise TTC');save();shortcut('Digit0');save_error=modal();activate(save_error.get_by_role('button',name='Enregistrer',exact=True));expect(save_error.locator('.creation-dialog-error')).to_contain_text('attente');page.keyboard.press('Escape');expect(page.locator('dialog[open]')).to_have_count(0)
    activate(page.get_by_role('button',name='Autorisation locale du responsable',exact=True));field(modal().locator('[name=identifiant]'),'responsable.qa');field(modal().locator('[name=password]'),f['password']);choice(modal().locator('[name=autoriser]'),'true');field(modal().locator('[name=justification]'),'Validation offre');save();expect(page.locator('#pf-totals')).to_contain_text('270 FCFA')
    shortcut('Digit0');save();expect(page.locator('#pf-title')).to_contain_text('EMISE');assert inventory()==before
    v1=page.evaluate('proformaState.current');ref=v1['reference']
    with page.expect_download() as download:activate(page.locator('#pf-download'))
    file=Path('qa/proforma-historique-v1.pdf');download.value.save_as(file);bytes1=file.read_bytes();assert bytes1.startswith(b'%PDF')
    page.screenshot(path='qa/p4-proforma-emise.png',full_page=True)
    # Change only disposable QA pricing. Historical PDF must remain byte-identical.
    with SessionLocal() as s:
        old=s.scalar(select(TarifProduitSiteModel).where(TarifProduitSiteModel.conditionnement_id==UUID(f['p4_pack']),TarifProduitSiteModel.site_id==UUID(f['site_id'])))
        tariffs=TarificationService(CatalogueService(SqlAlchemyCatalogueRepository(s)))
        tariffs.cloturer(TarifProduitSite,old.id_tarif,UUID(f['organisation_id']),date.today()-timedelta(days=1))
        tariffs.enregistrer(TarifProduitSite(organisation_id=UUID(f['organisation_id']),site_id=UUID(f['site_id']),produit_id=UUID(f['p4_product']),conditionnement_id=UUID(f['p4_pack']),montant_ht=125,devise='XAF',debut=date.today(),provenance='Recette proforma : tarif modifié'))
    shortcut('Digit8');save();expect(page.locator('#pf-title')).to_contain_text('Version 2');expect(page.locator('#pf-totals')).to_contain_text('375 FCFA');expect(page.locator('#pf-discounts')).to_contain_text('DEMANDEE');assert inventory()==before
    # Refuse copied discount, then emit a new version at current full price.
    activate(page.get_by_role('button',name='Autorisation locale du responsable',exact=True));field(modal().locator('[name=identifiant]'),'responsable.qa');field(modal().locator('[name=password]'),f['password']);choice(modal().locator('[name=autoriser]'),'false');field(modal().locator('[name=justification]'),'Nouvelle offre sans remise');save();shortcut('Digit0');save();v2=page.evaluate('proformaState.current');assert v2['reference']==ref
    choice(page.locator('#pf-versions'),v1['id']);expect(page.locator('#pf-title')).to_contain_text('Version 1');expect(page.locator('#pf-totals')).to_contain_text('270 FCFA')
    with page.expect_download() as download:activate(page.locator('#pf-download'))
    download.value.save_as('/tmp/proforma-v1-again.pdf');assert Path('/tmp/proforma-v1-again.pdf').read_bytes()==bytes1
    # Headless Chromium cannot render native PDF navigation (ERR_ABORTED).
    # Check the real keyboard action, tab opening and authenticated historical PDF bytes.
    with page.expect_popup() as opened, page.expect_response(lambda r:'/versions/'+v1['id']+'/pdf' in r.url) as preview:
        activate(page.locator('#pf-pdf'))
    assert preview.value.status==200 and preview.value.body()==bytes1
    opened.value.close()
    page.screenshot(path='qa/p4-proforma-historique.png',full_page=True)
    shortcut('Digit9');choice(modal().locator('[name=poste_id]'),f['p4_poste']);save();expect(page.locator('#vente-panel')).to_be_visible();expect(page.locator('#p4-totals')).to_contain_text('375 FCFA');expect(page.locator('#p4-discounts')).to_contain_text('DEMANDEE');page.screenshot(path='qa/p4-proforma-reprise.png',full_page=True)
    activate(page.locator('#nav-proforma'));expect(page.locator('#pf-list')).to_have_attribute('aria-busy','false');shortcut('KeyR');field(page.locator('#pf-search'),'Élodie');expect(page.locator('#pf-list tr')).to_have_count(1)
    activate(page.locator('#logout-button'));login('vente.lecture.qa');expect(page.get_by_role('button',name='F2 · Nouvelle proforma')).to_have_count(0);activate(page.locator('#pf-list').get_by_role('button',name='Consulter').first);expect(page.locator('#pf-title')).to_contain_text('EMISE');shortcut('Digit8');expect(page.locator('dialog[open]')).to_have_count(0)
    assert api('/versions/'+v2['id']+'/nouvelle-version','POST',{'cle':str(uuid4()),'revision':v2['revision']})['status']==403
    page.screenshot(path='qa/p4-proforma-lecture-seule.png',full_page=True);assert not errors,errors;browser.close()
print('P4.3 Chromium clavier : proforma sans stock, remise autorisée, versions immuables, PDF historique fidèle, prix recalculés à la reprise et lecture seule : OK')
