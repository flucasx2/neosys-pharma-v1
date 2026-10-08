"""Chromium P2 : grille paginée, créations modales, droits et saisies conservées."""
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
    def submit(form,modal=None):
        form.locator('button[type="submit"]' if modal else 'button:not([type="button"])').click()
        if modal:expect(page.locator(modal)).not_to_be_visible()
        expect(page.locator('#catalogue-message')).to_contain_text('Enregistrement réussi')
        expect(page.locator('#security-operation')).to_be_enabled()
    def new_meta(typ,values,parent=None):
        page.locator('#catalogue-data-type').select_option(typ);page.locator('#catalogue-data-create').click()
        expect(meta_dialog).to_be_visible();fill(meta,values)
        if parent:meta.locator('[name="parent_id"]').select_option(parent)
        submit(meta,'#catalogue-data-modal')
        return page.locator('#catalogue-data-selected option').filter(has_text=values['nom']).get_attribute('value')
    def screenshot(name):
        page.evaluate('document.activeElement?.blur();window.scrollTo({top:0,behavior:"instant"})')
        page.screenshot(path='qa/'+name,full_page=True)
    Path('qa').mkdir(exist_ok=True)
    login('catalogue.qa');expect(page.locator('#nav-administration')).to_be_hidden()
    page.locator('#nav-catalogue').click();expect(page.locator('#catalogue-count')).to_contain_text('0 résultat')
    page.on('request',lambda request:documents.append(request.url) if request.resource_type=='document' else None)
    meta=page.locator('#catalogue-data-modal-form');meta_dialog=page.locator('#catalogue-data-modal')
    popup=page.locator('#catalogue-product-modal');create=page.locator('#catalogue-product-modal-form')
    product=page.locator('#catalogue-product-form')
    page.locator('#catalogue-create').click();expect(popup).to_be_visible();expect(page.locator('#catalogue-list-panel')).to_be_visible()
    expect(create.locator('[name="nom"]')).to_be_focused()
    # Native dialog keyboard confinement and explicit close/Escape cancellation.
    for _ in range(20):
        page.keyboard.press('Tab')
        assert page.evaluate('document.activeElement.closest("dialog")?.id')=='catalogue-product-modal'
    popup.get_by_role('button',name='Annuler',exact=True).click();expect(popup).not_to_be_visible();expect(page.locator('#catalogue-create')).to_be_focused()
    page.locator('#catalogue-create').click();fill(create,{'nom':'Brouillon à préserver'})
    page.once('dialog',lambda dialog:dialog.dismiss());page.keyboard.press('Escape')
    expect(popup).to_be_visible();expect(create.locator('[name="nom"]')).to_have_value('Brouillon à préserver')
    page.once('dialog',lambda dialog:dialog.accept());popup.get_by_role('button',name='Fermer la fenêtre').click()
    expect(popup).not_to_be_visible();expect(page.locator('#catalogue-products tr')).to_have_count(0)
    page.locator('#catalogue-data-disclosure summary').click()
    parent=new_meta('categories',{'code':'MED-QA','nom':'Médicaments QA'})
    child=new_meta('categories',{'code':'ANTAL-QA','nom':'Antalgiques QA'},parent)
    form_id=new_meta('formes',{'code':'CP-QA','nom':'Comprimé QA'})
    lab_id=new_meta('laboratoires',{'code':'LAB-QA','nom':'Laboratoire QA'})
    # Duplicate metadata stays open and preserves values; cancellation warns.
    page.locator('#catalogue-data-create').click();fill(meta,{'code':'LAB-QA','nom':'Doublon conservé'})
    meta.get_by_role('button',name='Enregistrer',exact=True).click();expect(meta_dialog.locator('[role="alert"]')).to_contain_text('déjà utilisé')
    expect(meta_dialog).to_be_visible();expect(meta.locator('[name="nom"]')).to_have_value('Doublon conservé')
    page.once('dialog',lambda dialog:dialog.accept());meta.get_by_role('button',name='Annuler',exact=True).click()
    page.locator('#catalogue-create').click();fill(create,{'nom':'Produit QA <script>','description':'Produit indépendant de ses unités commerciales','premier_code':'B20','premier_libelle':'Boîte QA de 20'})
    create.locator('[name="categorie_id"]').select_option(child);create.locator('[name="forme_id"]').select_option(form_id);create.locator('[name="laboratoire_id"]').select_option(lab_id)
    # Nested reference creation must preserve the complete product draft and select the result.
    create.locator('[data-catalogue-create="categories"]').click();fill(meta,{'code':'NEST-QA','nom':'Sous-catégorie depuis produit'})
    meta.locator('[name="parent_id"]').select_option(child);submit(meta,'#catalogue-data-modal')
    expect(popup).to_be_visible();expect(create.locator('[name="nom"]')).to_have_value('Produit QA <script>')
    expect(create.locator('[name="premier_code"]')).to_have_value('B20');expect(create.locator('[name="categorie_id"] option:checked')).to_have_text('Sous-catégorie depuis produit')
    expect(create.locator('[name="forme_id"]')).to_have_value(form_id)
    screenshot('p2-modal-produit-desktop.png')
    page.set_viewport_size({'width':390,'height':844})
    assert not page.evaluate('document.documentElement.scrollWidth>innerWidth')
    footer=popup.locator('.creation-dialog-footer');expect(footer).to_be_in_viewport()
    create.locator('[name="premier_libelle"]').scroll_into_view_if_needed();expect(footer).to_be_in_viewport()
    screenshot('p2-modal-produit-mobile.png');page.set_viewport_size({'width':1440,'height':1000})
    # If POST succeeds but the refresh fails, retry refresh without a second POST.
    posts=[]
    def track_product(request):
        if request.method=='POST' and request.url.endswith('/produits'):posts.append(request.url)
    page.on('request',track_product)
    page.route('**/api/catalogue/organisations/*/produits?*',lambda route:route.abort())
    create.get_by_role('button',name='Enregistrer',exact=True).click()
    expect(popup.locator('[role="alert"]')).to_contain_text('Enregistrement effectué')
    expect(create.locator('[name="nom"]')).to_have_value('Produit QA <script>')
    page.unroute('**/api/catalogue/organisations/*/produits?*')
    create.get_by_role('button',name='Réessayer l’actualisation',exact=True).click();expect(popup).not_to_be_visible()
    expect(page.locator('#catalogue-list-panel')).to_be_visible();assert len(posts)==1,posts
    page.remove_listener('request',track_product)
    expect(page.locator('#catalogue-products')).to_contain_text('Produit QA <script>');expect(page.locator('#catalogue-products script')).to_have_count(0)
    page.locator('#catalogue-products button').filter(has_text='Modifier').click()
    expect(page.locator('#catalogue-ancestors')).to_contain_text('Médicaments QA → Antalgiques QA → Sous-catégorie depuis produit')
    page.locator('#catalogue-packaging-create').click()
    pack_modal=page.locator('#catalogue-packaging-modal');pack_new=page.locator('#catalogue-packaging-modal-form')
    fill(pack_new,{'code':'B20','libelle':'Erreur conservée'});pack_new.get_by_role('button',name='Enregistrer',exact=True).click()
    expect(pack_modal.locator('[role="alert"]')).to_contain_text('déjà utilisé');expect(pack_new.locator('[name="libelle"]')).to_have_value('Erreur conservée')
    fill(pack_new,{'code':'B60','libelle':'Boîte QA de 60'});submit(pack_new,'#catalogue-packaging-modal')
    expect(page.locator('#catalogue-packagings > li')).to_have_count(2)
    ref_new=page.locator('#catalogue-reference-modal-form')
    def add_reference(packaging,typ,value):
        page.locator('#catalogue-reference-packaging').select_option(label=packaging);page.locator('#catalogue-reference-create').click()
        ref_new.locator('[name="type_reference"]').select_option(typ);fill(ref_new,{'valeur':value});submit(ref_new,'#catalogue-reference-modal')
    add_reference('Boîte QA de 20','CIP7','0012345');add_reference('Boîte QA de 20','HISTORIQUE','ANCIEN-QA')
    add_reference('Boîte QA de 60','CIP7','0012346')
    page.locator('#catalogue-reference-packaging').select_option(label='Boîte QA de 60');page.locator('#catalogue-reference-selected').select_option(label='CIP7 : 0012346')
    ref=page.locator('#catalogue-reference-form');fill(ref,{'valeur':'0012347'});submit(ref)
    product.locator('[name="nom"]').fill('Produit QA modifié');submit(product)
    # Creating a laboratory from an existing edit must not discard unsaved product fields.
    product.locator('[name="description"]').fill('Brouillon fiche conservé')
    product.locator('[data-catalogue-create="laboratoires"]').click();fill(meta,{'code':'LAB-NEST','nom':'Laboratoire depuis fiche'})
    submit(meta,'#catalogue-data-modal');expect(product.locator('[name="description"]')).to_have_value('Brouillon fiche conservé')
    expect(product.locator('[name="laboratoire_id"] option:checked')).to_have_text('Laboratoire depuis fiche');submit(product)
    packaging=page.locator('#catalogue-packaging-form');page.locator('#catalogue-packaging-selected').select_option(label='Boîte QA de 60')
    fill(packaging,{'libelle':'Boîte QA de 60 modifiée'});submit(packaging)
    page.locator('#catalogue-back').click();expect(page.locator('#catalogue-products')).to_contain_text('2 conditionnements')
    page.locator('#catalogue-search').fill('ANCIEN-QA');expect(page.locator('#catalogue-count')).to_contain_text('1 résultat')
    page.locator('#catalogue-search').fill('absent');expect(page.locator('#catalogue-products tr')).to_have_count(0)
    page.locator('#catalogue-search').fill('');expect(page.locator('#catalogue-count')).to_contain_text('1 résultat')
    # Hierarchy rejection in an edit modal, without losing inputs.
    page.locator('#catalogue-data-type').select_option('categories');page.locator('#catalogue-data-selected').select_option(parent);page.locator('#catalogue-data-edit').click()
    meta.locator('[name="parent_id"]').select_option(child);meta.get_by_role('button',name='Enregistrer',exact=True).click()
    expect(meta_dialog.locator('[role="alert"]')).to_contain_text('Cycle')
    page.once('dialog',lambda dialog:dialog.accept());meta.get_by_role('button',name='Annuler',exact=True).click()
    root='http://127.0.0.1:8000/api/catalogue/organisations/'+fixture['organisation_id']
    assert page.request.post(root+'/categories',headers={'X-Site-ID':fixture['site_id']},data={'code':'FORGE','nom':'Sans CSRF'}).status==403
    csrf=next(cookie['value'] for cookie in page.context.cookies() if cookie['name']=='neosys_csrf');headers={'X-Site-ID':fixture['site_id'],'X-CSRF-Token':csrf}
    for i in range(55):
        result=page.request.post(root+'/produits',headers=headers,data={'nom':f'Catalogue QA {i:03d}','categorie_id':child,'forme_id':form_id,'premier_conditionnement':{'code':'B20','libelle':'Boîte de 20'}})
        assert result.status==201,result.text()
        if i==54:
            pid=result.json()['conditionnements'][0]['id_conditionnement'];assert page.request.post(root+f'/conditionnements/{pid}/references',headers=headers,data={'type_reference':'GTIN','valeur':'PAGE-TROIS-QA'}).status==201
    page.locator('#nav-catalogue').click();expect(page.locator('#catalogue-count')).to_contain_text('56 résultats');expect(page.locator('#catalogue-products tr')).to_have_count(25)
    first_ids=page.locator('#catalogue-products tr').evaluate_all('(rows)=>rows.map(r=>r.dataset.productId)')
    page.locator('#catalogue-next').click();expect(page.locator('#catalogue-page')).to_have_text('Page 2 sur 3')
    second_ids=page.locator('#catalogue-products tr').evaluate_all('(rows)=>rows.map(r=>r.dataset.productId)');assert not set(first_ids)&set(second_ids)
    # Successful creation preserves the current page, size and search filter.
    page.locator('#catalogue-create').click();fill(create,{'nom':'ZZZ Produit paginé','premier_code':'B','premier_libelle':'Unité'});create.locator('[name="categorie_id"]').select_option(child)
    submit(create,'#catalogue-product-modal');expect(page.locator('#catalogue-count')).to_contain_text('57 résultats');expect(page.locator('#catalogue-page')).to_have_text('Page 2 sur 3')
    page.locator('#catalogue-next').click();expect(page.locator('#catalogue-page')).to_have_text('Page 3 sur 3');expect(page.locator('#catalogue-products tr')).to_have_count(7)
    page.locator('#catalogue-search').fill('page-trois-qa');expect(page.locator('#catalogue-count')).to_contain_text('1 résultat');expect(page.locator('#catalogue-products')).to_contain_text('Catalogue QA 054')
    page.locator('#catalogue-create').click();fill(create,{'nom':'Produit hors filtre','premier_code':'B','premier_libelle':'Unité'});create.locator('[name="categorie_id"]').select_option(child)
    submit(create,'#catalogue-product-modal');expect(page.locator('#catalogue-search')).to_have_value('page-trois-qa');expect(page.locator('#catalogue-count')).to_contain_text('1 résultat')
    page.locator('#catalogue-search').fill('Produit QA modifié');expect(page.locator('#catalogue-products')).to_contain_text('2 conditionnements')
    page.locator('#catalogue-products button').filter(has_text='Consulter').click();expect(product).to_be_hidden();expect(page.locator('#catalogue-packagings > li')).to_have_count(2)
    screenshot('p2-produit-detail.png');page.locator('#catalogue-back').click();expect(page.locator('#catalogue-search')).to_have_value('Produit QA modifié')
    page.locator('#catalogue-search').fill('');expect(page.locator('#catalogue-count')).to_contain_text('58 résultats')
    page.locator('#catalogue-page-size').select_option('50');expect(page.locator('#catalogue-products tr')).to_have_count(50)
    page.locator('#catalogue-page-size').select_option('25');expect(page.locator('#catalogue-products tr')).to_have_count(25)
    page.locator('#catalogue-data-disclosure summary').click();screenshot('p2-catalogue-desktop.png')
    page.set_viewport_size({'width':390,'height':844});assert not page.evaluate('document.documentElement.scrollWidth>innerWidth');screenshot('p2-catalogue-mobile.png')
    page.set_viewport_size({'width':1440,'height':1000});page.locator('#logout-button').click();expect(page.locator('#login-panel')).to_be_visible();expect(product.locator('[name="nom"]')).to_have_value('')
    login('catalogue.lecture.qa');page.locator('#nav-catalogue').click();expect(page.locator('#catalogue-count')).to_contain_text('58 résultats')
    expect(page.locator('#catalogue-create')).to_be_hidden();expect(page.locator('#catalogue-products button').filter(has_text='Modifier')).to_have_count(0)
    page.locator('#catalogue-search').fill('ancien-qa');expect(page.locator('#catalogue-count')).to_contain_text('1 résultat');page.locator('#catalogue-products button').click()
    expect(product).to_be_hidden();expect(page.locator('#catalogue-edit')).to_be_hidden();expect(page.locator('#catalogue-packaging-create')).to_be_hidden()
    expect(page.locator('#catalogue-classification')).to_contain_text('Laboratoire depuis fiche');screenshot('p2-catalogue-readonly.png')
    # Even a forged frontend entry point cannot open a creation modal; HTTP writes still fail.
    page.evaluate('catalogueNewProduct()');expect(popup).not_to_be_visible()
    csrf=next(cookie['value'] for cookie in page.context.cookies() if cookie['name']=='neosys_csrf')
    for endpoint,data in [('/categories',{'code':'FORGE','nom':'Interdit'}),('/produits',{'nom':'Interdit','categorie_id':child,'premier_conditionnement':{'code':'X','libelle':'X'}})]:
        assert page.request.post(root+endpoint,headers={'X-Site-ID':fixture['site_id'],'X-CSRF-Token':csrf},data=data).status==403
    assert documents==[],documents
    page.locator('#logout-button').click();expect(page.locator('#login-panel')).to_be_visible();login('gestion.qa');expect(page.locator('#nav-catalogue')).to_be_hidden()
    assert page.request.get(root+'/produits',headers={'X-Site-ID':fixture['site_id']}).status==403
    assert not errors,errors
    browser.close()
    print('P2 Chromium : modales, clavier/focus, abandon confirmé, erreurs/saisies conservées, référentiels imbriqués, refresh sans reload, pagination et lecture seule : OK')
