"""Recette finale P2 : casse métier, exceptions, dates et historique exacts."""
from decimal import Decimal
from uuid import UUID

import pytest
from sqlalchemy import select
from test_p1_vertical import raw_client
from test_authentification import account, db, login
from test_catalogue import grant, root, post, basic
from neosys_pharma.domain.catalogue import texte
from neosys_pharma.infrastructure.catalogue_models import ProduitModel, ReferenceProduitModel
from neosys_pharma.infrastructure.import_catalogue_models import LigneImportCatalogueModel


@pytest.mark.parametrize('value,expected', [
    ('médicaments', 'MÉDICAMENTS'),
    ('comprimé pelliculé', 'COMPRIMÉ PELLICULÉ'),
    ('réserve générale', 'RÉSERVE GÉNÉRALE'),
    ('solution buvable pédiatrique', 'SOLUTION BUVABLE PÉDIATRIQUE'),
    ('antibiotiques à usage systémique', 'ANTIBIOTIQUES À USAGE SYSTÉMIQUE'),
    ('  e\u0301te\u0301 œuf çà ß  ', 'ÉTÉ ŒUF ÇÀ SS'),
])
def test_libelles_unicode_majuscules_canoniques(value, expected):
    assert texte(value, 200) == expected


def test_normalisation_http_persistance_et_exceptions(raw_client, account):
    c, a = raw_client, account
    grant(c, a); login(c, a)
    category, body, product = basic(c, a)
    for typ, key in [('categories', 'id_categorie'), ('formes', 'id_forme'),
                     ('laboratoires', 'id_laboratoire'), ('natures', 'id_nature'),
                     ('modes', 'id_mode'), ('principes', 'id_principe'),
                     ('classes', 'id_classe'), ('groupes', 'id_groupe')]:
        row = post(c, a, '/' + typ, {'code': 'e\u0301te\u0301', 'nom': 'antibiotiques à usage systémique'})
        assert row['code'] == 'ÉTÉ' and row['nom'] == 'ANTIBIOTIQUES À USAGE SYSTÉMIQUE'
        # Canonically equivalent composed/decomposed codes cannot create duplicates.
        post(c, a, '/' + typ, {'code': 'été', 'nom': 'Doublon'}, 409)
        response = c.put(root(a) + f'/{typ}/{row[key]}', json={'code': 'ÉTÉ', 'nom': 'comprimé pelliculé'})
        assert response.status_code == 200 and response.json()['nom'] == 'COMPRIMÉ PELLICULÉ'
    body.pop('premier_conditionnement')
    description = 'Solution pédiatrique : conserver à 5 °C. Dosage 5 mg/mL, avis du médecin.'
    body.update(nom='solution buvable pédiatrique', description=description)
    response = c.put(root(a) + f'/produits/{product["id_produit"]}', json=body)
    assert response.status_code == 200
    assert response.json()['description'] == description
    assert response.json()['nom'] == 'SOLUTION BUVABLE PÉDIATRIQUE'
    packaging = post(c, a, f'/produits/{product["id_produit"]}/conditionnements',
                     {'code': 'b', 'libelle': 'boîte à délivrer fermée'})
    assert packaging['libelle'] == 'BOÎTE À DÉLIVRER FERMÉE'
    reference = post(c, a, f'/conditionnements/{packaging["id_conditionnement"]}/references',
                     {'type_reference': 'HISTORIQUE', 'valeur': '00MixedCase-é-µg/mL'})
    assert reference['valeur'] == '00MixedCase-é-µg/mL'
    # SQL, rather than CSS or response formatting, proves normalization before persistence.
    gen = db(c); session = next(gen)
    try:
        persisted = session.get(ProduitModel, UUID(product['id_produit']))
        assert persisted.nom == 'SOLUTION BUVABLE PÉDIATRIQUE' and persisted.description == description
        assert session.get(ReferenceProduitModel, UUID(reference['id_reference'])).valeur == reference['valeur']
    finally:
        gen.close()


def test_frontieres_tarifaires_tva_et_provenance_sans_ecrasement(raw_client, account):
    c, a = raw_client, account
    grant(c, a); login(c, a)
    category, body, product = basic(c, a)
    pack = product['conditionnements'][0]['id_conditionnement']
    ref = post(c, a, '/tarification/references', {'conditionnement_id': pack,
        'montant_ht': '10.015', 'devise': 'XAF', 'debut': '2026-01-01',
        'provenance': 'Source Mixte : référence validée'})
    tax = post(c, a, '/tarification/tva', {'code': 'tva', 'nom': 'régime général',
        'taux': '18', 'debut': '2026-01-01', 'fin': '2026-06-30'})
    post(c, a, '/tarification/tva', {'code': 'TVA', 'nom': 'nouvelle période',
        'taux': '20', 'debut': '2026-07-01'})
    body.pop('premier_conditionnement'); body['regime_tva_code'] = 'tva'
    assert c.put(root(a) + f'/produits/{product["id_produit"]}', json=body).status_code == 200
    def price(day):
        response = c.get(root(a) + f'/prix/{pack}', params={'jour': day})
        assert response.status_code == 200
        return response.json()
    june, july = price('2026-06-30'), price('2026-07-01')
    assert june['tarif_id'] == ref['id_tarif'] and june['regime_tva']['id_regime'] == tax['id_regime']
    assert june['regle']['provenance'] == 'Source Mixte : référence validée'
    assert (Decimal(june['montant_ht']), Decimal(june['montant_tva']), Decimal(june['montant_ttc'])) == (Decimal('10.02'), Decimal('1.80'), Decimal('11.82'))
    assert june['fin'] == '2026-06-30' and july['debut'] == '2026-07-01'
    assert Decimal(july['montant_ttc']) == Decimal('12.02')
    # A one-day rule covers exactly its inclusive day, then falls back to reference.
    special = post(c, a, '/tarification/produits', {'site_id': str(a['site']),
        'produit_id': product['id_produit'], 'conditionnement_id': pack, 'montant_ht': '9',
        'devise': 'XAF', 'debut': '2026-06-30', 'fin': '2026-06-30'})
    assert price('2026-06-30')['tarif_id'] == special['id_tarif']
    assert price('2026-06-29')['tarif_id'] == price('2026-07-01')['tarif_id'] == ref['id_tarif']
    assert c.put(root(a) + f'/tarification/produits/{special["id_tarif"]}/cloture', json={'fin': '2026-07-01'}).status_code == 422
    history = c.get(root(a) + '/tarification/references').json()['items']
    assert history[0]['montant_ht'] == '10.0150' and history[0]['fin'] is None


def test_libelles_historiques_recherchables_sans_recriture_sql(raw_client, account):
    c, a = raw_client, account
    grant(c, a); login(c, a)
    category, body, product = basic(c, a)
    gen = db(c); session = next(gen)
    try:
        row = session.get(ProduitModel, UUID(product['id_produit']))
        row.nom = 'éphémère historique'
        row.description = 'Commentaire conservé : mg/mL.'
        session.commit()
    finally:
        gen.close()
    for query in ('éphémère', 'ÉPHÉMÈRE', 'e\u0301phe\u0301me\u0300re'):
        result = c.get(root(a) + '/produits', params={'q': query}).json()
        assert result['total'] == 1 and result['items'][0]['nom'] == 'ÉPHÉMÈRE HISTORIQUE'
    detail = c.get(root(a) + '/produits/' + product['id_produit']).json()
    assert detail['description'] == 'Commentaire conservé : mg/mL.'
    gen = db(c); session = next(gen)
    try:
        assert session.get(ProduitModel, UUID(product['id_produit'])).nom == 'éphémère historique'
    finally:
        gen.close()


def test_import_conserve_source_distincte_du_catalogue_normalise(raw_client, account):
    c, a = raw_client, account
    grant(c, a); login(c, a)
    category, body, product = basic(c, a)
    description = 'Solution buvable pédiatrique'
    preview = post(c, a, '/imports/previsualisation', {'contenu':
        f'CIP;Quantite;Description;DCI;PrixVente\n0019999;1234;{description};DCI non déduite;55\n',
        'nom_fichier': 'Source.csv', 'source': 'Source Mixte'})
    ident = preview['id_import']
    before = c.get(root(a) + f'/imports/{ident}').json()['items'][0]
    assert before['donnees']['Description'] == description and before['statut'] == 'INCONNU'
    post(c, a, f'/imports/{ident}/lots', {'mode': 'catalogue', 'categorie_id': category['id_categorie'],
        'conditionnement_libelle': 'unité indépendante', 'devise': 'XAF'}, 200)
    after = c.get(root(a) + f'/imports/{ident}').json()['items'][0]
    assert after['donnees'] == before['donnees'] and after['statut'] == 'IMPORTE'
    result = c.get(root(a) + '/produits', params={'q': '0019999'}).json()['items'][0]
    assert result['nom'] == description.upper()
    assert c.get(root(a) + '/tarification/references').json()['total'] == 0
    quote = c.get(root(a) + '/conseils').json()['items'][0]
    assert quote['source'] == 'Source Mixte' and Decimal(quote['prix_vente_conseille']) == 55
    gen = db(c); session = next(gen)
    try:
        line = session.scalar(select(LigneImportCatalogueModel).where(LigneImportCatalogueModel.import_id == UUID(ident)))
        assert line.donnees['Description'] == description and line.donnees['Quantite'] == '1234'
    finally:
        gen.close()
