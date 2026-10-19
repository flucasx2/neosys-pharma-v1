# Incrément 04 — cartes physiques, identifiants indépendants et documents

Base : 0af2686 (incrément 03), branche work/p4-p5-consolidation. Aucun changement aux règles de points, à leur conversion fiscale ou aux calculs de prise en charge.

## Réalisé

- code demeure le numéro visible historique ; code_barres est une valeur facultative indépendante, réservée aux cartes physiques. Aucun zéro initial supprimé, pas de conversion numérique ni de changement silencieux de casse.
- Registre partagé fidelite_cartes_identifiants, clé primaire (organisation_id, valeur). Les triggers enregistrent le numéro et le code-barres. Un code-barres ne peut être le numéro ou le code-barres d'une autre carte, même en cas d'insertion concurrente : la contrainte SQL porte sur un espace de noms unique. Les doublons d'une même carte numéro=code-barres ne créent qu'une entrée.
- Numéros historiques repris à la migration. Recherche/scan par numéro ou code-barres ; seules les cartes actives sont proposées. Opposition/remplacement conservent les identifiants réservés et l'historique.
- Association d'un code-barres à une ancienne carte physique active avant le premier document, sous révision du compte et audit. Une identité existante n'est pas réécrite ; association unique, pas de remplacement silencieux de code-barres.
- Préparation d'un document de carte, puis consultation/réimpression des mêmes octets PDF. Le premier tirage fige organisation, titulaire, numéro et code-barres. Un document unique par carte, hash SHA-256, auteur, date et snapshot immuables ; chaque nouvelle demande possède son audit et son idempotence. Le document ne donne pas le droit d'utiliser une carte opposée ; son état est contrôlé par l'application lors de la recherche.
- Écrans Clients et Caisse complétés : champs distincts, association avant impression et boutons d'impression/réimpression. Les champs physiques sont désactivés pour une carte virtuelle. Aucune permission attribuée : les mutations et documents sont réservés à fidelite.gerer dans le contexte autorisé.

L'impression produit un document A4 paysage avec Code 128 de la valeur exacte, pas un connecteur d'imprimante. Valeur imprimable ASCII de 1 à 80 caractères, format technique explicitement refusé si trop large/non imprimable ; les anciens numéros plus longs restent stockés et recherchables. Associer d'abord un code-barres imprimable dans ce cas. Aucune lecture par scanner matériel ni impression physique n'est prétendue testée. L'audit trace la préparation/réimpression demandée, pas la sortie physique effective d'une imprimante.

## API et migration

Création existante de carte : code_barres facultatif en plus de code. POST /api/caisses/organisations/{org}/fidelite/cartes/{id}/code-barres : cle, revision du compte, code_barres. POST .../{id}/impressions : cle ; retourne le document/hachage sans binaire. GET .../{id}/pdf : document préparé uniquement, permission fidelite.gerer. Cartes opposées/remplacées refusées à la nouvelle préparation d'impression.

Migration additive **20261019_03**, parent **20261019_02** : code_barres nullable, registre d'alias avec FK organisationnelle, documents de carte avec FK organisationnelles carte/auteur, unicité par carte et triggers d'immuabilité. Les CHECK historiques sont explicitement conservés en SQLite. Les points/comptes/numéros existants ne sont pas réécrits. Downgrade possible tant qu'aucun code-barres ni document nouveau n'est à conserver ; refus sinon, sans suppression de ces données.

Les triggers d'identité interdisent la modification des numéros et la suppression des cartes, l'ajout d'un alias forgé, le remplacement d'un code-barres ou son ajout après le premier document. Ils laissent les transitions P4 d'opposition/remplacement sur etat s'exécuter. Le registre est alimenté en base, pas seulement par une vérification préalable vulnérable aux courses.

## Tests réellement exécutés

Python 3.14.8 / SQLite jetable :

```sh
TZ=Africa/Libreville PYTHONPATH=src:tests:<site-packages-3.14> python3.14 -m pytest -q tests/test_cartes_identifiants.py tests/test_p4_finitions.py tests/test_caisse.py tests/test_clients_p4b.py tests/test_consolidation_migrations.py -k 'cartes_identifiants or carte_virtuelle or cartes_telephone or adhesion_fidelite_optionnelle or migration_moyens or migration_cartes'
```

**8 passed, 1 skipped, 56 deselected, 1 warning — 18.56 s.** Le skip est PostgreSQL natif absent. Le warning httpx/TestClient est connu. Trois nouveaux cas API cartes ; compatibilité carte virtuelle, fidélité facultative, cartes historiques ; migration moyens et migration cartes avec conservation d'un numéro 00000123, de son compte et de 4 points fictifs, cycle downgrade/upgrade et immuabilité/downgrade conservateur. Une assertion supplémentaire sur la modification SQL du code-barres après document est vérifiée séparément dans le test d'immuabilité ; **1 passed, 1 warning — 4.07 s**, sans additionner ce rejeu comme un test unique supplémentaire.

DOM : **17 assertions formulaires**, **7 fournisseurs**, **19 groupe**, HTTP et hôte des modales simulés. Vérification des champs physiques séparés, suppression de leur envoi pour une carte virtuelle, récapitulatif de document. JavaScript syntaxiquement valide.

Le chemin natif de test_consolidation_migrations.py est étendu aux deux cycles : moyens puis reprise des cartes. Le lanceur API natif inclut désormais les 3 cas cartes (16 tests attendus au total). PostgreSQL natif, Chromium et scripts PowerShell restent **non exécutés**. Les garanties de concurrence du registre sont structurelles ici ; elles ne sont pas présentées comme un test natif réussi.

## Suite

OBS-FID-02 implémentée sous réserve de PostgreSQL, Chromium et recette consolidée. Poursuivre la reproduction de l'import catalogue puis les imports de bénéficiaires indépendants des plafonds consommables. Aucun push, PR, activation financière ou migration sur base conservée.
