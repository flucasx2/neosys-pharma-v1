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
    print("Parcours Web P1, doublons, contexte et affichage mobile : OK")
