"""Recette P4-B au clavier : clients, fidélité, organismes, historique et préparation."""
import json
import re
from pathlib import Path

from playwright.sync_api import expect, sync_playwright

fixture = json.loads(Path('/tmp/p1-browser-fixture.json').read_text())
url = 'http://127.0.0.1:8000'
Path('qa').mkdir(exist_ok=True)

with sync_playwright() as playwright:
    browser = playwright.chromium.launch()
    context = browser.new_context(viewport={'width': 1600, 'height': 1050})
    page = context.new_page()
    page_errors = []
    page.on('pageerror', lambda error: page_errors.append(str(error)))

    def type_field(locator, value):
        locator.focus()
        page.keyboard.press('Control+A')
        if value:
            page.keyboard.type(str(value))
        else:
            page.keyboard.press('Backspace')

    def activate(locator):
        locator.focus()
        page.keyboard.press('Enter')

    def choose(locator, value):
        locator.focus()
        page.keyboard.press('Home')
        values = locator.locator('option').evaluate_all('(options) => options.map(option => option.value)')
        assert value in values, (value, values)
        for _ in range(values.index(value)):
            page.keyboard.press('ArrowDown')
        page.keyboard.press('Tab')

    def login(target, username):
        target.goto(url)
        form = target.locator('#login-form')
        for name, value in [('organisation_id', fixture['organisation_id']), ('identifiant', username), ('password', fixture['password'])]:
            form.locator('[name=' + name + ']').focus()
            target.keyboard.type(value)
        form.locator('button').focus()
        target.keyboard.press('Enter')
        expect(target.locator('#app-shell')).to_be_visible()

    def wait_clients():
        expect(page.locator('#clients-rows')).to_have_attribute('aria-busy', 'false')

    def filter_clients(value):
        with page.expect_response(lambda response: '/api/clients/organisations/' in response.url and ('?q=' in response.url or '&q=' in response.url)):
            type_field(page.locator('#clients-search'), value)
        expect(page.locator('#clients-rows')).to_have_attribute('aria-busy', 'false')

    def open_client(name):
        activate(page.get_by_role('button', name='Consulter ' + name, exact=True))
        expect(page.locator('#clients-detail')).to_be_visible()

    def modal():
        return page.locator('dialog[open]').last

    def save_modal():
        activate(modal().get_by_role('button', name='Enregistrer', exact=True))
        expect(page.locator('dialog[open]')).to_have_count(0)

    login(page, 'clients.qa')
    activate(page.locator('#nav-clients'))
    expect(page.locator('#clients-panel')).to_be_visible()
    wait_clients()

    # Search by name, phone and exact profile UUID.
    filter_clients('Historique P4B QA')
    expect(page.locator('#clients-rows tr')).to_have_count(1)
    filter_clients('070987654')
    expect(page.locator('#clients-rows tr')).to_have_count(1)
    filter_clients(fixture['p4b_history_client'])
    expect(page.locator('#clients-rows tr')).to_have_count(1)
    filter_clients('')

    # Create a profile independently of loyalty, then edit it.
    activate(page.get_by_role('button', name='+ Nouvelle fiche', exact=True))
    type_field(modal().locator('[name=nom]'), 'Cliente P4B Nouvelle')
    type_field(modal().locator('[name=telephone]'), '070 123 456')
    type_field(modal().locator('[name=courriel]'), 'NOUVELLE@example.test')
    save_modal()
    expect(page.locator('#clients-name')).to_have_text('Cliente P4B Nouvelle')
    expect(page.locator('#clients-loyalty')).to_contain_text('n’adhère pas')
    client_id = re.search(r'[0-9a-f-]{36}', page.locator('#clients-contact').inner_text()).group(0)
    page.screenshot(path='qa/p4b-client-independant.png', full_page=True)

    activate(page.get_by_role('button', name='Modifier', exact=True))
    type_field(modal().locator('[name=nom]'), 'Cliente P4B Modifiée')
    save_modal()
    expect(page.locator('#clients-name')).to_have_text('Cliente P4B Modifiée')

    # Optional loyalty enrollment and one physical card.
    activate(page.get_by_role('button', name='Proposer l’adhésion', exact=True))
    expect(page.locator('#clients-loyalty')).to_contain_text('Compte fidélité')
    activate(page.get_by_role('button', name='+ Carte de fidélité', exact=True))
    type_field(modal().locator('[name=code]'), 'P4B-CARTE-QA')
    choose(modal().locator('[name=type]'), 'PHYSIQUE')
    save_modal()
    expect(page.locator('#clients-loyalty')).to_contain_text('P4B-CARTE-QA')

    # Create and associate both primary and complementary coverage organizations.
    page.locator('#clients-organism-add summary').click()
    create_organism = page.locator('#clients-organism-create')
    type_field(create_organism.locator('[name=code]'), 'P4B-PRINCIPAL')
    type_field(create_organism.locator('[name=nom]'), 'Organisme principal QA')
    create_organism.get_by_role('button', name='Créer un organisme', exact=True).click()
    expect(page.locator('#clients-message')).to_contain_text('Organisme créé')
    organism_select = page.locator('#clients-organism-form [name=organisme_id]')
    principal_option = organism_select.locator('option').filter(has_text='Organisme principal QA')
    expect(principal_option).to_have_count(1)
    principal_id = principal_option.get_attribute('value')
    choose(organism_select, principal_id)
    assert organism_select.input_value() == principal_id
    choose(page.locator('#clients-organism-form [name=role]'), 'PRINCIPAL')
    type_field(page.locator('#clients-organism-form [name=reference]'), 'REF-P4B-1')
    with page.expect_response(lambda response: response.request.method == 'POST' and '/organismes' in response.url) as association_response:
        page.locator('#clients-organism-form button').click()
    assert association_response.value.status == 201, association_response.value.text()
    expect(page.locator('#clients-organisms')).to_contain_text('Organisme principal QA')

    create_organism = page.locator('#clients-organism-create')
    type_field(create_organism.locator('[name=code]'), 'P4B-COMPLEMENT')
    type_field(create_organism.locator('[name=nom]'), 'Organisme complémentaire QA')
    assert create_organism.locator('[name=code]').input_value() == 'P4B-COMPLEMENT'
    assert create_organism.locator('[name=nom]').input_value() == 'Organisme complémentaire QA'
    with page.expect_response(lambda response: response.request.method == 'POST' and response.url.endswith('/organismes'), timeout=5000) as complementary_response:
        create_organism.get_by_role('button', name='Créer un organisme', exact=True).click()
    assert complementary_response.value.status == 201, complementary_response.value.text()
    expect(page.locator('#clients-message')).to_contain_text('Organisme créé')
    select = page.locator('#clients-organism-form [name=organisme_id]')
    complementary_option = select.locator('option').filter(has_text='Organisme complémentaire QA')
    expect(complementary_option).to_have_count(1)
    complementary = complementary_option.get_attribute('value')
    choose(select, complementary)
    choose(page.locator('#clients-organism-form [name=role]'), 'COMPLEMENTAIRE')
    type_field(page.locator('#clients-organism-form [name=reference]'), 'REF-P4B-2')
    page.locator('#clients-organism-form button').click()
    expect(page.locator('#clients-organisms')).to_contain_text('Organisme complémentaire QA')
    expect(page.locator('#clients-organisms')).to_contain_text('Complémentaire')
    page.screenshot(path='qa/p4b-organismes.png', full_page=True)

    # View a seeded sale in history, scoped to the current organization/site.
    activate(page.locator('#nav-clients'))
    wait_clients()
    filter_clients('Historique P4B QA')
    open_client('Historique P4B QA')
    expect(page.locator('#clients-history')).to_contain_text(fixture['p4b_history_sale'][:8])
    expect(page.locator('#clients-history')).to_contain_text('PREPARATION')
    page.screenshot(path='qa/p4b-historique-client.png', full_page=True)

    # Explicitly attach and remove a client from an editable preparation.
    activate(page.locator('#nav-vente'))
    expect(page.locator('#vente-panel')).to_be_visible()
    expect(page.locator('#p4-list')).to_have_attribute('aria-busy', 'false')
    target_sale = page.locator('#p4-list button').filter(has_text=fixture['p4b_selectable_sale'][:8])
    activate(target_sale)
    expect(page.locator('#p4-client')).to_be_visible()
    type_field(page.locator('#p4-client-search'), 'Cliente P4B Modifiée')
    expect(page.locator('#p4-client-results button')).to_have_count(1)
    activate(page.locator('#p4-client-results button').first)
    expect(page.locator('#p4-client-selected')).to_contain_text('Cliente P4B Modifiée')
    expect(page.locator('#p4-client-remove')).to_be_visible()
    activate(page.locator('#p4-client-remove'))
    expect(page.locator('#p4-client-selected')).to_contain_text('Aucun client sélectionné')
    expect(page.locator('#p4-client-remove')).to_be_hidden()
    page.screenshot(path='qa/p4b-selection-client-preparation.png', full_page=True)

    # Reader role cannot open the client module or bypass its API permission.
    readonly = browser.new_context(viewport={'width': 1600, 'height': 1050})
    readonly_page = readonly.new_page()
    login(readonly_page, 'clients.lecture.qa')
    expect(readonly_page.locator('#nav-clients')).to_be_hidden()
    status = readonly_page.evaluate('''async (org) => (await fetch(`/api/clients/organisations/${org}`)).status''', fixture['organisation_id'])
    assert status == 403, status
    assert not page_errors, page_errors
    browser.close()
    print('P4-B Chromium : recherche nom/téléphone/UUID, création indépendante, modification, fidélité/cartes, organismes principal/complémentaire, historique, sélection/retrait en préparation, autorisations : OK')
