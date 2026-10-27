# Incrément 05 — bilan fiable de l'import catalogue

Base : ac4010c, après les moyens de paiement et les cartes. Périmètre : défaut reproduit de message final, sans changer la création de produits, les prix ou le stock. Aucune migration.

## Reproduction et correction

Avec un CSV fictif au format PharmaGabon contenant un CIP inconnu, le lot retourne termine=true lorsque la pagination est terminée. Sans catégorie/libellé de conditionnement, la ligne reste INCONNU, avec une erreur explicite dans le rapport. L'interface affichait néanmoins « Import terminé — catalogue actualisé depuis le serveur. ». En mode conseils seuls, un inconnu est volontairement ignoré et aucun produit n'est créé.

Le test DOM du vrai gestionnaire du bouton échoue sur le p2.js du commit ac4010c avec « Faux succès malgré une ligne inconnue non créée ». Après correction, il distingue les lignes réellement importées, conseils, ignorées, invalides et à reprendre. Le rapport serveur est relu ; une erreur de lecture ne produit pas de message de réussite. La reprise utilise toujours les mêmes services et règles P2.

Un test API sur CSV fictif confirme : inconnu non créé sans catégorie/conditionnement, puis même import repris avec valeurs explicites ; produit retrouvé par CIP7 conservant ses zéros et par désignation, aucun stock ajouté malgré Quantite=9999. Les règles de conseils fournisseur sont inchangées.

**Limite : le CSV réel et la base Windows de l'incident ne sont pas accessibles. Le faux bilan est démontré et corrigé ; il n'est pas présenté comme la cause exacte prouvée de l'incident PharmaGabon.** OBS-CAT-01 reste partiellement ouverte jusqu'à contrôle du rapport réel, de son mode, des erreurs et du périmètre.

## Résultats réels

- tests/test_import_catalogue_recherche.py : **1 passed, 1 warning — 3.36 s**, SQLite fictif.
- tests/test_p2_complete.py -k 'import_mapping or import_conseils_seuls' : **2 passed, 26 deselected, 1 warning — 4.04 s**. Pas de relance volumétrique de 3 500 références.
- tests/import_catalogue_resultat_ui.cjs : **6 assertions DOM**, HTTP et shell simulés ; source applicative complète. Contre-preuve avec P2_SOURCE_FILE pointant sur le fichier antérieur : échec attendu ; source corrigée : réussite.
- node --check p2.js réussi. Aucun PostgreSQL, Chromium, CSV réel ou recette Windows exécuté.

Fichiers : presentation/web/p2.js, les deux tests cités et continuité. Pas de droits, ventes historiques, tarifs ou migrations modifiés. Pas de publication ou base conservée.
