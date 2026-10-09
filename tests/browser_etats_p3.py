"""États réels après le parcours P3 : navigation, filtres, exports et droits."""
import json
from pathlib import Path
from playwright.sync_api import sync_playwright,expect
f=json.loads(Path('/tmp/p1-browser-fixture.json').read_text())
with sync_playwright() as p:
    browser=p.chromium.launch();page=browser.new_page(viewport={'width':1440,'height':1000});errors=[];documents=[]
    page.on('pageerror',lambda e:errors.append(str(e)));page.goto('http://127.0.0.1:8000')
    def login(name):
        for k,v in {'organisation_id':f['organisation_id'],'identifiant':name,'password':f['password']}.items():page.locator(f'#login-form [name="{k}"]').fill(v)
        page.locator('#login-form button').click();expect(page.locator('#app-shell')).to_be_visible();page.locator('#nav-stock').click();expect(page.locator('#stock-rows')).to_have_attribute('aria-busy','false')
    def ready():expect(page.locator('#etats-rows')).to_have_attribute('aria-busy','false')
    def kind(value):
        with page.expect_response(lambda r:'/etats/'+value+'?' in r.url):page.locator('#etats-type').select_option(value)
        ready()
    def apply():
        with page.expect_response(lambda r:'/etats/' in r.url and '/export' not in r.url):page.locator('#etats-filters button').click()
        ready()
    def shot(name):page.screenshot(path='qa/'+name,full_page=True)
    login('stock.qa');page.on('request',lambda r:documents.append(r.url) if r.resource_type=='document' else None)
    page.locator('[data-stock-view="etats"]').click();expect(page.locator('#etats-panel')).to_be_visible();expect(page.locator('#etats-summary')).to_contain_text('30 résultat(s)');ready()
    expect(page.locator('#etats-rows tr')).to_have_count(25)
    page.locator('#etats-next').click();expect(page.locator('#etats-page')).to_have_text('Page 2 sur 2');expect(page.locator('#etats-rows tr')).to_have_count(5)
    page.locator('#etats-search').fill('LOT-P3-01');apply();expect(page.locator('#etats-rows tr')).to_have_count(2);shot('p3-etats-stocks.png')
    for fmt in ('pdf','xlsx','csv'):
        with page.expect_download() as event:page.locator(f'[data-etats-export="{fmt}"]').click()
        download=event.value;download.save_as('qa/etats-stocks.'+fmt);assert Path('qa/etats-stocks.'+fmt).stat().st_size>0
    kind('valorisation');expect(page.locator('#etats-summary')).to_contain_text('2 ligne(s) non valorisable(s)');expect(page.locator('#etats-summary')).to_contain_text('indisponible');expect(page.locator('#etats-rows')).to_contain_text('Coût historique absent');shot('p3-etats-valorisation.png')
    page.locator('#etats-search').fill('');apply();kind('mouvements');expect(page.locator('#etats-rows')).to_contain_text('Recette');shot('p3-etats-mouvements.png')
    page.locator('#etats-start').fill('2030-01-01');page.locator('#etats-end').fill('2020-01-01');apply();expect(page.locator('#etats-message')).to_contain_text('précéder');expect(page.locator('[data-etats-export="pdf"]')).to_be_disabled();page.locator('#etats-start').fill('');page.locator('#etats-end').fill('');apply()
    kind('inventaire');expect(page.locator('#etats-message')).to_contain_text('Choisir un inventaire');page.locator('#etats-inventory').select_option(index=1);apply();expect(page.locator('#etats-summary')).to_contain_text('VALIDE');expect(page.locator('#etats-rows')).to_contain_text('-1');shot('p3-etats-pv-inventaire.png')
    with page.expect_download() as event:page.locator('[data-etats-export="pdf"]').click()
    event.value.save_as('qa/etats-pv-inventaire.pdf')
    kind('ecarts');expect(page.locator('#etats-summary')).to_contain_text('non valorisable');shot('p3-etats-ecarts.png')
    kind('peremptions');expect(page.locator('#etats-rows')).to_contain_text('LOT-P3-01');shot('p3-etats-peremptions.png')
    kind('comptabilite');expect(page.locator('#etats-rows')).to_contain_text('AUCUNE ÉCRITURE');shot('p3-etats-comptabilite.png')
    page.set_viewport_size({'width':390,'height':844});shot('p3-etats-mobile.png');assert not page.evaluate('document.documentElement.scrollWidth>innerWidth');page.set_viewport_size({'width':1440,'height':1000})
    page.locator('#sites').select_option(f['p3_other_site']);expect(page.locator('#etats-summary')).to_contain_text('1 résultat(s)');expect(page.locator('#etats-rows')).not_to_contain_text('PAG-P3-')
    page.locator('#logout-button').click();login('stock.lecture.qa');page.locator('[data-stock-view="etats"]').click();ready();expect(page.locator('#etats-panel')).to_be_visible()
    assert page.locator('#etats-type option[value="inventaire"]').get_attribute('hidden') is not None
    r=page.request.get('http://127.0.0.1:8000/api/stock/organisations/'+f['organisation_id']+'/etats/inventaire/export?format=csv',headers={'X-Site-ID':f['site_id']});assert r.status==403,r.text()
    page.locator('#logout-button').click();login('stock.compteur.qa');expect(page.locator('[data-stock-view="etats"]')).to_be_hidden()
    assert not documents,documents;assert not errors,errors
    browser.close();print('P3 États Chromium : pagination, recherche, PDF/Excel/CSV, coûts absents, journal, PV/écarts, péremptions, comptabilité, sites, lecture seule et comptage aveugle : OK')
