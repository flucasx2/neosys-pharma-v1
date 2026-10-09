"""Chromium P2 complet : associations, prix datés, conseils et import sans F5."""
import json
from pathlib import Path
from playwright.sync_api import sync_playwright,expect
fixture=json.loads(Path('/tmp/p1-browser-fixture.json').read_text())
with sync_playwright() as p:
    browser=p.chromium.launch();page=browser.new_page(viewport={'width':1440,'height':1000})
    errors=[];documents=[];page.on('pageerror',lambda e:errors.append(str(e)))
    page.goto('http://127.0.0.1:8000')
    def login(user):
        for k,v in {'organisation_id':fixture['organisation_id'],'identifiant':user,'password':fixture['password']}.items():page.locator(f'#login-form [name="{k}"]').fill(v)
        page.locator('#login-form button').click();expect(page.locator('#app-shell')).to_be_visible();page.locator('#nav-catalogue').click()
    def fill(form,values):
        for k,v in values.items():form.locator(f'[name="{k}"]').fill(v)
    def save(modal):
        modal.get_by_role('button',name='Enregistrer',exact=True).click();expect(modal).not_to_be_visible();expect(page.locator('#catalogue-message')).to_contain_text('Enregistrement réussi')
    def shot(name):
        page.evaluate('document.activeElement?.blur();window.scrollTo({top:0,behavior:"instant"})');page.screenshot(path='qa/'+name,full_page=True)
    login('catalogue.qa');expect(page.locator('#catalogue-count')).to_contain_text('58 résultats');initial_context=page.evaluate('[document.getElementById("organisations").value,document.getElementById("sites").value,document.getElementById("emplacements").value]')
    page.on('request',lambda r:documents.append(r.url) if r.resource_type=='document' else None)
    page.locator('#catalogue-data-disclosure summary').click()
    meta=page.locator('#catalogue-data-modal')
    def reference(typ,code,nom):
        page.locator('#catalogue-data-type').select_option(typ);page.locator('#catalogue-data-create').click();fill(meta,{'code':code,'nom':nom});save(meta)
        return page.locator('#catalogue-data-selected option').filter(has_text=nom.upper()).get_attribute('value')
    nature=reference('natures','N-QA','Nature explicite QA');mode=reference('modes','M-QA','Délivrance explicite QA')
    principe=reference('principes','P-QA','Principe actif QA');classe=reference('classes','C-QA','Classe thérapeutique QA');groupe=reference('groupes','G-QA','Groupe de substitution QA')
    # Dated TVA created through the same accessible modal workflow.
    page.locator('#p2-tab-tarification').click();page.locator('#p2-tarif-type').select_option('tva');page.locator('#p2-tarif-new').click();tarif=page.locator('#p2-tarif-modal')
    fill(tarif,{'code':'TVA-QA','nom':'TVA QA','taux':'18','debut':'2026-01-01'});save(tarif)
    page.locator('#p2-tab-produits').click();page.locator('#catalogue-search').fill('Produit QA modifié');expect(page.locator('#catalogue-products tr')).to_have_count(1)
    page.locator('#catalogue-products button').filter(has_text='Modifier').click();product=page.locator('#catalogue-product-modal')
    expect(page.locator('#catalogue-list-panel')).to_be_visible();product.locator('[name="nature_id"]').select_option(nature);product.locator('[name="mode_delivrance_id"]').select_option(mode);product.locator('[name="regime_tva_code"]').select_option('TVA-QA');product.locator('[name="gestion_lot"]').select_option('true');save(product)
    page.locator('#catalogue-products button').filter(has_text='Consulter').click();expect(page.locator('#catalogue-classification')).to_contain_text('NATURE EXPLICITE QA')
    # Updating category rules refreshes the consulted product and its derived context.
    category_id=page.evaluate('catalogueState.detail.categorie_id')
    page.locator('#catalogue-data-type').select_option('categories');page.locator('#catalogue-data-selected').select_option(category_id);page.locator('#catalogue-data-edit').click()
    meta.locator('[name="fefo"]').check();save(meta)
    expect(page.locator('#p2-regles')).to_contain_text('FEFO : oui (catégorie)')
    expect(page.locator('#catalogue-product-description')).to_have_text('Brouillon fiche conservé')
    association=page.locator('#p2-association-modal')
    for typ,ident,dosage in [('compositions',principe,'500 mg'),('classifications',classe,None),('substitutions',groupe,None)]:
        page.locator(f'[data-p2-association="{typ}"]').click();association.locator('[name="association_id"]').select_option(ident)
        if dosage:association.locator('[name="dosage"]').fill(dosage)
        save(association);expect(page.locator('#p2-'+typ)).not_to_contain_text('Aucune association')
    # Nested active-ingredient creation updates and selects the new entry.
    page.locator('[data-p2-association="compositions"]').click();association.locator('[data-catalogue-create]').click();fill(meta,{'code':'P2-QA','nom':'Deuxième principe QA'});save(meta)
    expect(association).to_be_visible();expect(association.locator('[name="association_id"] option:checked')).to_have_text('DEUXIÈME PRINCIPE QA');save(association)
    expect(page.locator('#p2-compositions li')).to_have_count(2)
    page.locator('#p2-compositions li').first.get_by_role('button',name='Modifier').click();association.locator('[name="dosage"]').fill('250 mg');save(association);expect(page.locator('#p2-compositions')).to_contain_text('250 mg')
    def new_tarif(button,values,regle=None):
        page.locator("#p2-tab-tarification" if button=="#p2-tarif-new" else "#p2-tab-produits").click();page.locator(button).click()
        if regle:tarif.locator('[name="regle"]').select_option(regle)
        fill(tarif,values);save(tarif);page.locator("#p2-tab-produits").click()
    new_tarif('#p2-tarif-reference',{'valeur':'100','devise':'XAF','debut':'2026-01-01'})
    page.locator('#p2-prix-date').fill('2026-10-08');page.locator('#p2-prix-refresh').click();expect(page.locator('#p2-prix-resultat')).to_contain_text('Origine : Tarif de référence');expect(page.locator('#p2-prix-resultat')).to_contain_text('118,00')
    page.locator('#p2-tab-tarification').click();page.locator('#p2-tarif-type').select_option('sites');new_tarif('#p2-tarif-new',{'valeur':'1.2','devise':'XAF','debut':'2026-01-01'},'coefficient');expect(page.locator('#p2-prix-resultat')).to_contain_text('Origine : Paramètres du site')
    page.locator('#p2-tab-tarification').click();page.locator('#p2-tarif-type').select_option('categories');new_tarif('#p2-tarif-new',{'valeur':'1.3','devise':'XAF','debut':'2026-01-01'},'coefficient');expect(page.locator('#p2-prix-resultat')).to_contain_text('Origine : Catégorie principale / site')
    new_tarif('#p2-tarif-produit',{'valeur':'140','devise':'XAF','debut':'2026-01-01'});expect(page.locator('#p2-prix-resultat')).to_contain_text('165,20 XAF TTC');expect(page.locator('#p2-prix-resultat')).to_contain_text('Origine : Produit / conditionnement / site')
    # Conflicting periods keep the popup and user input.
    page.locator('#p2-tarif-produit').click();fill(tarif,{'valeur':'150','devise':'XAF','debut':'2026-10-01'});tarif.get_by_role('button',name='Enregistrer',exact=True).click();expect(tarif.locator('[role="alert"]')).to_contain_text('Chevauchement');expect(tarif.locator('[name="valeur"]')).to_have_value('150')
    page.once('dialog',lambda d:d.accept());tarif.get_by_role('button',name='Annuler',exact=True).click()
    page.locator('#p2-tab-tarification').click();page.locator('#p2-tarif-type').select_option('produits');expect(page.locator('#p2-tarif-history tr')).to_have_count(1);expect(page.locator('#p2-tarif-history')).to_contain_text('140,00');page.locator('#p2-tarif-history button').click();cloture=page.locator('#p2-cloture-modal');fill(cloture,{'fin':'2026-12-31'});save(cloture)
    new_tarif('#p2-tarif-produit',{'valeur':'150','devise':'XAF','debut':'2027-01-01'});page.locator('#p2-tab-tarification').click();page.locator('#p2-tarif-load').click();expect(page.locator('#p2-tarif-history tr')).to_have_count(2);expect(page.locator('#p2-tarif-history')).to_contain_text('31/12/2026');expect(page.locator('#p2-tarif-history')).to_contain_text('01/01/2027')
    page.locator('#p2-tab-tarification').click();shot('p2-tarification-historique.png');page.locator('#p2-tab-produits').click();page.locator('#p2-prix-date').fill('2027-01-01');page.locator('#p2-prix-refresh').click();expect(page.locator('#p2-prix-resultat')).to_contain_text('177,00 XAF TTC')
    shot('p2-fiche-composition-prix.png')
    # A delayed response for an older date must not overwrite the new-date price.
    page.evaluate("""async()=>{
      const original=catalogueRequest;
      catalogueRequest=async function(path,...args){if(path.includes('/prix/')&&path.includes('jour=2026-10-08'))await new Promise(resolve=>setTimeout(resolve,600));return original(path,...args);};
      try{document.getElementById('p2-prix-date').value='2026-10-08';const old=p2Prix();document.getElementById('p2-prix-date').value='2027-01-01';await Promise.all([old,p2Prix()]);}finally{catalogueRequest=original;}
    }""")
    expect(page.locator('#p2-prix-resultat')).to_contain_text('177,00 XAF TTC')
    page.evaluate("""async()=>{
      const original=catalogueRequest;
      catalogueRequest=async function(path,...args){if(path.includes('/prix/')&&path.includes('jour=2026-10-08')){await new Promise(resolve=>setTimeout(resolve,300));throw new Error('Erreur de contexte ancien');}return original(path,...args);};
      try{document.getElementById('p2-prix-date').value='2026-10-08';const old=p2Prix();document.getElementById('p2-prix-date').value='2027-01-01';await Promise.all([old,p2Prix()]);}finally{catalogueRequest=original;}
    }""")
    expect(page.locator('#p2-prix-resultat')).to_contain_text('177,00 XAF TTC')
    # Import preview, mapping, missing required defaults and idempotent rerun.
    csv='CIP;Quantite;Description;DCI;PrixAchat;PrixVente\n0012345;999;NOM SOURCE;DCI BRUTE NON DÉDUITE;100;180\n7654321;1500;Nouveau catalogue importé;;20;30\nBAD;1;Ligne invalide;;1;2\n'
    page.locator('#p2-tab-import').click();expect(page.locator('#catalogue-message')).to_have_text('');page.locator('#p2-import-form [name="fichier"]').set_input_files({'name':'PharmaGabon-QA.csv','mimeType':'text/csv','buffer':csv.encode('utf-8')})
    expect(page.locator('#p2-import-mapping select')).to_have_count(6);page.locator('#p2-import-form button').click();expect(page.locator('#p2-import-message')).to_contain_text('3 lignes');expect(page.locator('#p2-import-rows')).to_contain_text('INVALIDE');shot('p2-import-previsualisation.png')
    page.locator('#p2-import-run').click();expect(page.locator('#catalogue-message')).to_contain_text('Import terminé');expect(page.locator('#p2-import-rows')).to_contain_text('catégorie et libellé')
    # Preserve current search; unknown products need an explicit commercial-unit label.
    category=page.locator('#p2-import-category option').nth(1).get_attribute('value');page.locator('#p2-import-category').select_option(category);page.locator('#p2-import-pack').fill('Unité commerciale fournie')
    page.locator('#p2-import-run').click();expect(page.locator('#p2-import-message')).to_contain_text('IMPORTE : 2');expect(page.locator('#catalogue-search')).to_have_value('Produit QA modifié');expect(page.locator('#catalogue-count')).to_contain_text('1 résultat')
    expect(page.locator('#p2-compositions li')).to_have_count(2);expect(page.locator('#p2-prix-resultat')).to_contain_text('177,00 XAF TTC');expect(page.locator('#p2-conseils')).to_contain_text('180,00 XAF')
    # Source prices have not overwritten the reference price (100) or product/site rule.
    page.locator('#p2-tab-tarification').click();page.locator('#p2-tarif-type').select_option('references');expect(page.locator('#p2-tarif-history tr')).to_have_count(1);expect(page.locator('#p2-tarif-history')).to_contain_text('100,00')
    page.locator('#p2-tarif-history button').click();fill(cloture,{'fin':'2026-12-31'});save(cloture)
    page.locator('#p2-tab-produits').click();page.locator('#p2-conseils button').click();conseil=page.locator('#p2-conseil-modal');fill(conseil,{'debut':'2027-01-01'})
    conseil.get_by_role('button',name='Enregistrer',exact=True).click();expect(conseil).to_be_visible() # explicit checkbox required
    conseil.locator('[name="confirmer"]').check();save(conseil);expect(page.locator('#p2-tarif-history tr')).to_have_count(2)
    expect(page.locator('#p2-prix-resultat')).to_contain_text('177,00 XAF TTC') # higher-priority product rule remains
    page.locator('#p2-tab-import').click();page.locator('#p2-import-form button').click();expect(page.locator('#p2-import-message')).to_contain_text('EXISTANT : 2');page.locator('#p2-import-run').click();expect(page.locator('#p2-import-message')).to_contain_text('IMPORTE : 2')
    expect(page.locator('#module-title')).to_have_text('Import catalogue');shot('p2-import-rapport.png')
    # Paginated advice review and explicit multi-selection validation from the global table.
    page.locator('#p2-tab-conseils').click();page.locator('#p2-conseils-search').fill('7654321');expect(page.locator('#p2-conseils-rows tr')).to_have_count(1)
    page.locator('#p2-conseils-rows input').check();page.locator('#p2-conseils-apply').click()
    expect(conseil).to_be_visible();expect(conseil.locator('#p2-conseil-modal-p2-conseil-summary')).to_contain_text('30,00 XAF')
    fill(conseil,{'debut':'2027-01-01'});conseil.locator('[name="confirmer"]').check();save(conseil)
    shot('p2-conseils-validation.png')
    page.locator('#p2-tab-import').click()
    with page.expect_download() as download:page.locator('#p2-import-export').click()
    assert download.value.suggested_filename=='rapport-import.csv'
    page.locator('#p2-tab-produits').click();page.locator('#catalogue-back').click();page.locator('#catalogue-search').fill('7654321');expect(page.locator('#catalogue-products tr')).to_have_count(1);expect(page.locator('#catalogue-products')).to_contain_text('NOUVEAU CATALOGUE IMPORTÉ')
    page.locator('#catalogue-search').fill('');expect(page.locator('#catalogue-count')).to_contain_text('59 résultats')
    page.locator('#p2-tab-tarification').click();page.locator('#p2-tarif-type').select_option('references');expect(page.locator('#p2-tarif-new')).to_be_disabled();expect(page.locator('#p2-tarif-message')).to_contain_text('Consultez un produit');page.locator('#p2-tab-produits').click()
    page.set_viewport_size({'width':390,'height':844});assert not page.evaluate('document.documentElement.scrollWidth>innerWidth');shot('p2-complet-mobile.png');page.set_viewport_size({'width':1440,'height':1000})
    page.locator('#logout-button').click();login('catalogue.lecture.qa');expect(page.locator('#p2-tarif-new')).to_be_hidden();expect(page.locator('#p2-import-form')).to_be_hidden();expect(page.locator('#p2-import-options')).to_be_hidden()
    page.locator('#p2-tab-produits').click();page.locator('#catalogue-search').fill('Produit QA modifié');expect(page.locator('#catalogue-products tr')).to_have_count(1);page.locator('#catalogue-products button').click();expect(page.locator('#p2-compositions li')).to_have_count(2)
    expect(page.locator('#p2-compositions button')).to_have_count(0);expect(page.locator('#p2-conseils button')).to_have_count(0);expect(page.locator('#p2-tarif-produit')).to_be_hidden();shot('p2-complet-lecture-seule.png')
    csrf=next(x['value'] for x in page.context.cookies() if x['name']=='neosys_csrf');headers={'X-Site-ID':fixture['site_id'],'X-CSRF-Token':csrf};root='http://127.0.0.1:8000/api/catalogue/organisations/'+fixture['organisation_id']
    for endpoint in ['/imports/previsualisation','/conseils/appliquer','/tarification/sites','/principes']:
        assert page.request.post(root+endpoint,headers=headers,data={}).status==403
    page.evaluate('p2NewTarif("sites")');expect(tarif).not_to_be_visible()
    assert not documents,documents;assert page.evaluate('[document.getElementById("organisations").value,document.getElementById("sites").value,document.getElementById("emplacements").value]')==initial_context
    assert not errors,errors
    browser.close();print('P2 complet Chromium : compositions/classifications, priorités, TVA, historique, import, réimport, validation des conseils, modales et lecture seule : OK')
