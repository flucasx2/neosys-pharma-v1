"""Parcours navigateur contre un serveur de test isolé (lancé par la CI)."""
from pathlib import Path
from playwright.sync_api import sync_playwright, expect


def remplir(form, valeurs):
    for nom, valeur in valeurs.items():
        form.locator(f'[name="{nom}"]').fill(valeur)


with sync_playwright() as p:
    browser = p.chromium.launch()
    page = browser.new_page(viewport={"width": 1440, "height": 1000})
    erreurs = []
    page.on("pageerror", lambda erreur: erreurs.append(str(erreur)))
    page.goto("http://127.0.0.1:8000")
    page.locator("details").filter(has=page.locator("#organisation-form")).locator("summary").click()
    form = page.locator("#organisation-form")
    remplir(form, {"nom_commercial": "NeoPharma navigateur", "raison_sociale": "NeoPharma SARL",
                   "site_code": "LBV-QA", "site_nom": "Libreville QA",
                   "emplacement_code": "RES-QA", "emplacement_nom": "Réserve QA"})
    form.locator("button").click()
    expect(page.locator("#organisations option:checked")).to_have_text("NeoPharma navigateur")
    expect(page.locator('#sites option').filter(has_text="LBV-QA")).to_have_count(1)
    page.locator("#sites").select_option(label="LBV-QA · Libreville QA")
    expect(page.locator("#emplacements")).to_contain_text("RES-QA · Réserve QA")
    page.locator("#equipement-emplacement").select_option(label="RES-QA · Réserve QA")
    for form_id, code, nom, liste in (
        ("poste-form", "P-QA", "Poste QA", "postes-list"),
        ("caisse-form", "C-QA", "Caisse QA", "caisses-list"),
        ("coffre-form", "F-QA", "Coffre QA", "coffres-list"),
    ):
        page.locator("details").filter(has=page.locator(f"#{form_id}")).locator("summary").click()
        form = page.locator(f"#{form_id}")
        remplir(form, {"code": code, "nom": nom})
        expect(form.locator("button")).to_be_enabled()
        form.locator("button").click()
        expect(page.locator(f"#{liste}")).to_contain_text(f"{code} · {nom}")
    # Le doublon doit produire une erreur visible, sans deuxième ligne.
    form = page.locator("#poste-form")
    remplir(form, {"code": "p-qa", "nom": "Doublon"})
    form.locator("button").click()
    expect(page.locator("#message")).to_contain_text("Code déjà utilisé")
    expect(page.locator("#postes-list li")).to_have_count(1)
    # Un utilisateur, deux sites, des droits contextualisés et un rôle personnalisé.
    page.locator("details").filter(has=page.locator("#site-form")).locator("summary").click()
    remplir(page.locator("#site-form"), {"code":"OW-QA", "nom":"Owendo QA", "emplacement_code":"R-OW", "emplacement_nom":"Réserve Owendo"})
    page.locator("#site-form button").click()
    expect(page.locator("#security-new-site option").filter(has_text="Owendo QA")).to_have_count(1)
    page.locator("details").filter(has=page.locator("#security-user-create")).locator("summary").click()
    remplir(page.locator("#security-user-create"), {"identifiant":"alice.qa", "nom":"Alice QA", "email":"alice@example.test"})
    page.locator("#security-user-create button").click()
    expect(page.locator("#security-user option:checked")).to_contain_text("Alice QA")
    page.locator("details").filter(has=page.locator("#security-assignment-create")).locator("summary").click()
    def assigner(site):
        form = page.locator("#security-assignment-create")
        page.locator("#security-new-site").select_option(label=site)
        remplir(form, {"date_debut":"2026-01-01"})
        form.locator("button").click()
        expect(page.locator("#security-scope-help")).to_contain_text(site)
    assigner("Libreville QA")
    page.locator("#security-location-checks label").filter(has_text="Réserve QA").locator("input").check()
    page.locator("#security-locations button").click()
    expect(page.locator("#security-location-checks input")).to_be_checked()
    page.locator("#security-role-checks label").filter(has_text="Observateur").locator("input").check()
    page.locator("#security-roles button").click()
    expect(page.locator("#security-role-checks label").filter(has_text="Observateur").locator("input")).to_be_checked()
    page.locator("#security-preview-date").fill("2026-10-07")
    page.locator("#security-preview button").click()
    expect(page.locator("#security-result")).to_contain_text("organisation.consulter")
    expect(page.locator("#security-result")).to_contain_text("Réserve QA")
    assigner("Owendo QA")
    page.locator("#security-preview button").click()
    expect(page.locator("#security-result")).to_contain_text("Aucune permission effective")
    expect(page.locator("#security-result")).not_to_contain_text("organisation.consulter")
    remplir(page.locator("#security-role-create"), {"code":"LOCAL-QA", "nom":"Gestion locale QA"})
    page.locator("#security-new-permissions label").filter(has_text="(affectation.gerer)").locator("input").check()
    page.locator("#security-role-create button").click()
    expect(page.locator("#security-role-selected option").filter(has_text="Gestion locale QA")).to_have_count(1)
    page.locator("#security-assignment").select_option(label="Owendo QA · 2026-01-01 → sans fin")
    page.locator("#security-role-checks label").filter(has_text="Gestion locale QA").locator("input").check()
    page.locator("#security-roles button").click()
    expect(page.locator("#security-role-checks label").filter(has_text="Gestion locale QA").locator("input")).to_be_checked()
    page.locator("#security-location-checks label").filter(has_text="Réserve Owendo").locator("input").check()
    page.locator("#security-locations button").click()
    expect(page.locator("#security-location-checks input")).to_be_checked()
    page.locator("#security-preview button").click()
    expect(page.locator("#security-result")).to_contain_text("affectation.gerer")
    expect(page.locator("#security-result")).to_contain_text("Réserve Owendo")
    page.locator("#security-role-selected").select_option(label="Observateur · SYSTEME")
    expect(page.locator("#security-role-edit fieldset")).to_be_disabled()
    # Return to the first site to retain the equipment checks below.
    page.locator("#sites").select_option(label="LBV-QA · Libreville QA")
    page.locator("#equipement-emplacement").select_option(label="RES-QA · Réserve QA")
    expect(page.locator("#postes-list")).to_contain_text("P-QA")
    Path("qa").mkdir(exist_ok=True)
    page.screenshot(path="qa/p1-desktop.png", full_page=True)
    page.set_viewport_size({"width": 390, "height": 844})
    assert not page.evaluate("document.documentElement.scrollWidth > innerWidth"), "Débordement mobile"
    page.screenshot(path="qa/p1-mobile.png", full_page=True)
    page.locator("#sites").select_option("")
    expect(page.locator("#poste-form button")).to_be_disabled()
    expect(page.locator("#caisse-form button")).to_be_disabled()
    expect(page.locator("#coffre-form button")).to_be_disabled()
    expect(page.locator("#postes-list")).not_to_contain_text("P-QA")
    assert not erreurs, erreurs
    browser.close()
    print("Parcours Web P1, utilisateurs multi-sites, droits, doublons et affichage mobile : OK")
