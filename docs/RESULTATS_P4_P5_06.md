# Incrément 06 — import CSV/XLSX des bénéficiaires

Base : 84405ed (après 03, 04 et 05), branche work/p4-p5-consolidation. L'import réutilise TiersPayantsService.creer_beneficiaire et les autorisations P5-A ; pas de second registre de personnes, pas de moteur de droits.

## Livré

Prévisualisation sans écriture, contrôle de toutes les lignes puis confirmation atomique. La provenance est propre à l'organisation, à l'organisme de liste et à sa référence ; aucune personne n'est fusionnée par son nom. Une personne existante peut être rattachée explicitement par UUID et révision, après vérification de l'identité. Une référence manuelle déjà présente sans provenance exige ce rapprochement explicite. Le réimport identique ne duplique ni personne ni origine ; une modification de contenu sur une référence importée est refusée pour revue, sans écraser l'historique.

Création de personnes indépendantes ; client_id reste facultatif et doit désigner une fiche active de la même organisation. Ni fiche client, ni fidélité, ni adhésion, ni droit, ni créance ne sont créés implicitement. Les liens titulaire/ayant droit et les droits sont gérés ensuite par les opérations existantes d'adhésion. Aucun statut CONFIRMES n'est accepté comme colonne importée.

CSV UTF-8/BOM, séparateur point-virgule ou virgule. Excel XLSX uniquement, feuille à préciser s'il y en a plusieurs ; formules refusées, références numériques refusées pour ne pas fabriquer les zéros manquants. Dates ISO ou dates Excel natives. Limites de ressources explicites : 4 Mo compressés/fichier, 32 Mo décompressés pour XLSX, 5 000 lignes par fichier, 2 000 entrées ZIP. Scinder les listes plus grandes ; ces limites protègent l'import atomique et ne sont pas des plafonds de droits. Pas d'exécution de macro, d'évaluation de formule ou de connexion à un organisme externe. Dépendances ajoutées : openpyxl >=3.1.5,<4 et defusedxml >=0.7.1,<1.

Administration → Organismes → Conventions et droits → Bénéficiaires : fichier, feuille, modèle CSV, prévisualisation paginée par 50 dans le DOM et accord explicite. Fichier/feuille/contexte modifié invalide la prévisualisation. Un rejeu réseau identique conserve la clé d'idempotence ; la mémoire de reprise n'utilise pas le fichier base64 entier comme clé de cache. Les montants financiers ne sont pas simulés par l'interface.

## API et persistance

Préfixe /api/tiers-payants/organisations/{organisation_id}.

- POST /imports/beneficiaires/previsualiser : cle, organisme_id, nom_fichier, format CSV/XLSX, contenu_base64, feuille facultative. Permission tiers_payant.adhesion.gerer et contexte existants ; aucune mutation.
- POST /imports/beneficiaires/confirmer : mêmes champs, empreinte_attendue du fichier et confirmer=true. Transaction/idempotence StockService.operation, revalidation des personnes/révisions, source et empreinte ; aucune écriture si une ligne bloque.

Colonnes exactes : reference_externe et nom obligatoires ; date_naissance, client_id, beneficiaire_id et revision_beneficiaire facultatives. Une révision positive est obligatoire lorsqu'un bénéficiaire existant est désigné. Autres colonnes refusées, notamment les droits.

Migration additive **20261019_04** après **20261019_03** : table tiers_payant_origines_import_beneficiaires, unicité (organisation, organisme, référence), FK organisationnelles vers organisme, bénéficiaire et auteur ; empreintes fichier/ligne, données sources typées et auteur figés. Triggers UPDATE/DELETE immuables ; downgrade refusé si des provenances existent. Aucune ancienne migration réécrite. Pas de fichier binaire nominatif conservé ; les données utiles et empreintes sont conservées avec les permissions existantes.

Revue technique complémentaire : le lecteur du solde de remboursement utilise maintenant execute pour traduire aussi ses conflits métier en erreur HTTP contrôlée. Aucun calcul de remboursement changé par cette enveloppe.

## Résultats réellement exécutés

Python **3.14.8**, SQLite temporaire. openpyxl **3.1.5** et defusedxml **0.7.1** effectivement importés dans le runtime de tests. Aucune campagne historique complète relancée.

Commande ciblée import/migrations et régressions P5-CONF :

```sh
TZ=Africa/Libreville PYTHONPATH=src:tests:<dependances-import>:<site-packages-3.14> python3.14 -m pytest -q tests/test_import_beneficiaires.py tests/test_consolidation_migrations.py tests/test_p5_conf_conventions.py -k 'import or migration_moyens or migration_cartes or preuve_types or organisme_inactif or configuration_permissions'
```

**11 passed, 1 skipped, 12 deselected, 1 warning — 27.89 s.** Import, reimport/rejeu, blocage global, références déjà présentes sans fusion, panne après la première personne et rollback, autorisations/contexte, droits interdits, Excel nombres/formules/feuilles, migrations additives et régressions de preuve/organisme inactif.

Validation intégrée ciblée des six modules nouveaux/affectés (moyens, cartes, import bénéficiaires, recherche catalogue, migrations, groupe avec organismes) : **19 passed, 4 skipped, 1 warning — 43.33 s**. Les 4 skips : contrôle Alembic PostgreSQL natif et les 3 courses groupe/groupe/individuel natives. Ils ne sont pas des validations réussies. Les sélections intermédiaires chevauchent ce lancement et ne doivent pas être additionnées en tests uniques.

DOM : 10 assertions nouvelles d'import (FileReader et application réels, HTTP simulé) ; 38 assertions de conventions/préuves existantes réussies après évolution. Les autres scénarios ciblés sont conservés : 17 formulaires, 7 fournisseurs, 19 groupe et 6 import catalogue. Aucun résultat Chromium annoncé. Syntaxe JavaScript et git diff --check vérifiés.

Scripts natifs préparés, **non exécutés** : recette_p4p5_postgresql.ps1 ajoute les 5 tests import (21 tests API/domaine/rollback/concurrence attendus sur base neuve marquée) ; recette_consolidation_migrations.ps1 étend le contrôle aux migrations jusqu'à 20261019_04 et à leurs cycles/contraintes. Le test de migration emploie Alembic, les autres fixtures create_all/drop_all ; ne jamais les confondre ni les lancer sur une base conservée. Le contrôle natif ne valide pas encore une course entre deux imports concurrents ; l'unicité et le verrou d'organisation sont structurels ici.

## État

Implémenté/testé localement, validation PostgreSQL et Chromium encore ouverte. Ni P4 ni P5 ne sont déclarés clos. Ancien CSV PharmaGabon et scanner matériel non disponibles. Les plafonds périodiques/individuels restent volontairement non implémentés avant les décisions consignées ; les règles déjà validées de principal facultatif et d'ordre organisationnel sont conservées.

P5-C reste le prochain chantier autorisé, distinct de cet import : réutiliser les réalisations et snapshots définitifs, les retours et allocations, sans traiter une simulation comme une créance et sans perdre les documents P5-FAC-01. Aucun bordereau, facture ou règlement organisme n'est présenté comme livré par les incréments 03–06. Aucun déploiement, publication, activation du groupe ou accès à une base conservée.

Après l'enveloppe HTTP du lecteur de solde : le cas groupe/fournisseurs/allocations est rejoué seul, **1 passed, 1 warning — 5.92 s**. Ce rejeu n'est pas additionné au total intégré.
