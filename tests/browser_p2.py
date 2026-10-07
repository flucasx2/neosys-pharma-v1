"""Catalogue Chromium réel : créations/modifications visibles sans reload."""
import json
from pathlib import Path
from playwright.sync_api import sync_playwright, expect

fixture=json.loads(Path('/tmp/p1-browser-fixture.json').read_text())
with sync_playwright() as p:
    browser=p.chromium.launch()
    page=browser.new_page(viewport={'width':1440,'height':1000})
    errors=[];documents=[]
    page.on('pageerror',lambda error:errors.append(str(error)))
    page.goto('http://127.0.0.1:8000')
    def login(identifiant):
        for name,value in {'organisation_id':fixture['organisation_id'],'identifiant':identifiant,'password':fixture['password']}.items():page.locator(f'#login-form [name="{name}"]').fill(value)
        page.locator('#login-form button').click();expect(page.locator('#app-shell')).to_be_visible()
    def fill(form,values):
        for name,value in values.items():form.locator(f'[name="{name}"]').fill(value)
    def submit(form):
        form.locator('button').click();expect(page.locator('#catalogue-message')).to_contain_text('Enregistrement réussi')
        expect(page.locator('#catalogue-operation')).to_be_enabled()
    login('catalogue.qa')
    expect(page.locator('#nav-administration')).to_be_hidden()  # No organization/security permissions.
    page.locator('#nav-catalogue').click();expect(page.locator('#catalogue-operation')).to_be_enabled()
    page.on('request',lambda request:documents.append(request.url) if request.resource_type=='document' else None)
    meta=page.locator('#catalogue-data-form')
    fill(meta,{'code':'MED-QA','nom':'Médicaments QA'});submit(meta)
    expect(page.locator('#catalogue-category option')).to_contain_text(['Choisir une catégorie','Médicaments QA'])
    parent=page.locator('#catalogue-category option').last.get_attribute('value')
    fill(meta,{'code':'ANTAL-QA','nom':'Antalgiques QA'});page.locator('#catalogue-parent').select_option(parent);submit(meta)
    child=page.locator('#catalogue-category option').filter(has_text='Antalgiques QA').get_attribute('value')
    page.locator('#catalogue-data-type').select_option('formes');fill(meta,{'code':'CP-QA','nom':'Comprimé QA'});submit(meta)
    page.locator('#catalogue-data-type').select_option('laboratoires');fill(meta,{'code':'LAB-QA','nom':'Laboratoire QA'});submit(meta)
    product=page.locator('#catalogue-product-form')
    fill(product,{'nom':'Produit QA <script>','description':'Produit indépendant de ses unités commerciales','premier_code':'B20','premier_libelle':'Boîte QA de 20'})
    page.locator('#catalogue-category').select_option(child)
    page.locator('#catalogue-forme').select_option(label='Comprimé QA');page.locator('#catalogue-laboratoire').select_option(label='Laboratoire QA');submit(product)
    expect(page.locator('#catalogue-products')).to_contain_text('Produit QA <script>')
    expect(page.locator('#catalogue-products script')).to_have_count(0)
    expect(page.locator('#catalogue-detail')).to_be_visible()
    expect(page.locator('#catalogue-ancestors')).to_have_text('Catégorie et parents : Médicaments QA → Antalgiques QA')
    expect(page.locator('#catalogue-packagings')).to_contain_text('Boîte QA de 20')
    packaging=page.locator('#catalogue-packaging-form')
    page.locator('#catalogue-packaging-selected').select_option('');fill(packaging,{'code':'B60','libelle':'Boîte QA de 60'});submit(packaging)
    expect(page.locator('#catalogue-packagings > li')).to_have_count(2)
    ref=page.locator('#catalogue-reference-form')
    page.locator('#catalogue-reference-packaging').select_option(label='Boîte QA de 20')
    fill(ref,{'valeur':'0012345'});submit(ref)
    expect(page.locator('#catalogue-packagings')).to_contain_text('CIP7 : 0012345')
    page.locator('#catalogue-reference-packaging').select_option(label='Boîte QA de 20')
    page.locator('#catalogue-reference-selected').select_option('');ref.locator('[name="type_reference"]').select_option('HISTORIQUE');fill(ref,{'valeur':'ANCIEN-QA'});submit(ref)
    expect(page.locator('#catalogue-packagings')).to_contain_text('HISTORIQUE : ANCIEN-QA')
    page.locator('#catalogue-reference-packaging').select_option(label='Boîte QA de 60')
    ref.locator('[name="type_reference"]').select_option('CIP7');fill(ref,{'valeur':'0012345'});ref.locator('button').click()
    expect(page.locator('#catalogue-message')).to_contain_text('déjà utilisé')
    expect(page.locator('#catalogue-packagings > li')).to_have_count(2)
    fill(ref,{'valeur':'0012346'});submit(ref)
    page.locator('#catalogue-reference-packaging').select_option(label='Boîte QA de 60')
    page.locator('#catalogue-reference-selected').select_option(label='CIP7 : 0012346');fill(ref,{'valeur':'0012347'});submit(ref)
    expect(page.locator('#catalogue-packagings')).to_contain_text('CIP7 : 0012347')
    product.locator('[name="nom"]').fill('Produit QA modifié');submit(product)
    expect(page.locator('#catalogue-products')).to_contain_text('Produit QA modifié')
    page.locator('#catalogue-packaging-selected').select_option(label='Boîte QA de 60');fill(packaging,{'libelle':'Boîte QA de 60 modifiée'});submit(packaging)
    expect(page.locator('#catalogue-packagings')).to_contain_text('Boîte QA de 60 modifiée')
    page.locator('#catalogue-search').fill('ANCIEN-QA');expect(page.locator('#catalogue-products tr')).to_have_count(1)
    page.locator('#catalogue-search').fill('absent');expect(page.locator('#catalogue-products tr')).to_have_count(0)
    page.locator('#catalogue-search').fill('')
    page.locator('#catalogue-data-type').select_option('categories');page.locator('#catalogue-data-selected').select_option(parent);page.locator('#catalogue-parent').select_option(child);meta.locator('button').click()
    expect(page.locator('#catalogue-message')).to_contain_text('Cycle')
    assert documents==[],documents
    root='http://127.0.0.1:8000/api/catalogue/organisations/'+fixture['organisation_id']
    assert page.request.post(root+'/categories',headers={'X-Site-ID':fixture['site_id']},data={'code':'FORGE','nom':'Sans CSRF'}).status==403
    Path('qa').mkdir(exist_ok=True);page.screenshot(path='qa/p2-catalogue-desktop.png',full_page=True)
    page.set_viewport_size({'width':390,'height':844})
    assert not page.evaluate('document.documentElement.scrollWidth>innerWidth')
    page.screenshot(path='qa/p2-catalogue-mobile.png',full_page=True)
    page.set_viewport_size({'width':1440,'height':1000});page.locator('#logout-button').click();expect(page.locator('#login-panel')).to_be_visible()
    login('catalogue.lecture.qa');page.locator('#nav-catalogue').click()
    expect(page.locator('#catalogue-products')).to_contain_text('Produit QA modifié')
    expect(product).to_be_hidden();expect(meta).to_be_hidden()
    csrf=next(cookie['value'] for cookie in page.context.cookies() if cookie['name']=='neosys_csrf')
    assert page.request.post(root+'/categories',headers={'X-Site-ID':fixture['site_id'],'X-CSRF-Token':csrf},data={'code':'FORGE','nom':'Lecture seule'}).status==403
    page.locator('#logout-button').click();expect(page.locator('#login-panel')).to_be_visible()
    login('gestion.qa');expect(page.locator('#nav-catalogue')).to_be_hidden()
    assert page.request.get(root+'/produits',headers={'X-Site-ID':fixture['site_id']}).status==403
    assert not errors,errors
    browser.close()
    print('P2 Catalogue : hiérarchie, produits, conditionnements et références sans reload, modifications, recherche, isolation des permissions, CSRF, bureau/mobile : OK')
