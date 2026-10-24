# Résultats P5-C.1 — 19 octobre 2026

## Périmètre et continuité

Base `ba570569bb7063bf587ffac45c3eceff58dea93b`, arbre `b5c3af66c556c76bbf47ef859253b8c541e4e676`. Après interruption, le worktree initial et ses ajouts P5-C.1 non commités étaient indisponibles. La livraison 03–07 a été récupérée ; SHA-256 du ZIP vérifié : `1ab8ec031b09a9c5f649fbbb8dc51b4c68fb0887295fecc992dbc8f57d881ac5`. Bundles P5-CONF.1a puis 01–02 puis 03–07 vérifiés et importés dans une nouvelle copie isolée. Aucun patch alternatif n'a été appliqué. Les sources P4/P5-A/B proviennent ainsi des objets Git exacts ; aucun module antérieur n'a été reconstruit.

Les ajouts P5-C.1 ont été repris dans cette copie et **les résultats ci-dessous ont été réellement exécutés sur cette copie**, avec Python 3.14.8 installé dans un répertoire temporaire indépendant. Les premiers résultats de l'exécution interrompue ne sont pas utilisés comme preuve de cette livraison.

## Livré

- Deux journaux SQLAlchemy append-only : créance financière par organisme et versions du dossier administratif.
- Constitution atomique, exacte, idempotente depuis une réalisation confirmée P5-B, avec lignes/parts/étapes et preuves historiques.
- API de liste, sources, détail, historique, complément, vérification, contrôle informatif d'engagement ; contexte et permissions explicites.
- Module Créances intégré au shell existant : constitution, consultation, compléments typés, pièces référencées/vérifiées, motifs, validation et historique ; protection double clic/rejeu/contexte.
- P5-FAC-02 dans la configuration des conventions : finalité financière par défaut historique ; complétude différée uniquement si explicitement administrative.
- Garde serveur partagé pour les futurs engagements ; les factures/bordereaux/règlements ne sont pas implémentés.
- Retours consultables et blocage de l'engagement, sans recalcul de créance ou de règlement P4.
- Migration additive `20261019_05` après `20261019_04`, sans attribution de permissions.

## Contrôles exécutés

| Contrôle | Résultat réel | Portée |
|---|---|---|
| Campagne ciblée Python/API/SQL/migrations | **30 passed, 7 skipped**, 1 avertissement, 39,90 s | P5-C, conventions P5-CONF.1b, P5-B.3, groupes avec organismes, migration de configuration |
| Refus du downgrade avec créances présentes (contrôle supplémentaire distinct) | **1 passed**, 1 avertissement, 3,30 s | Copie SQLite fictive ; trois créances conservées |
| Recontrôle ciblé des contraintes après renforcement des assertions FK | **1 passed**, 1 avertissement, 2,98 s | Organisme de contrôle distinct pour éviter que UNIQUE masque une erreur de FK |
| Politique CI | **48 tests réussis**, 3,096 s | Matrice 17/18, bases marquées, synthèse obligatoire, nouveau parcours préparé |
| Module Créances DOM | **23 assertions réussies** | HTML et JavaScript réels, authentification et HTTP simulés |
| Module Conventions DOM | **38 assertions réussies** | Non-régression, HTTP simulé |
| Migration Alembic | Réussie dans la campagne ciblée SQLite temporaire | Chaîne jusqu'à 20261019_05, command.check, FK/UNIQUE, retour à 04 puis montée, conservation organisme P4-B fictif |
| Syntaxe JS et git diff --check | Réussis | Aucun parcours Chromium implicite |

Les logs de cette campagne historique sont conservés séparément et exclus de l’historique de publication P4 ; ils ne sont pas des pièces jointes publiques ni une validation complète de P5. Le contrôle supplémentaire du refus de downgrade avec créances existantes est réussi ; son résultat est enregistré dans `downgrade.log`. Les 30 + 1 tests ci-dessus sont deux exécutions distinctes, sans addition de campagnes redondantes.

Les tests applicatifs vérifient : absence de source avant encaissement, refus d'une simple confirmation de calcul comme source, trois créances pour trois organismes, somme exacte, rejeu même/nouvelle clé sans duplication, séparation finance/administration, rejet des champs financiers modifiés, états/révisions, historique, contrôles d'engagement incomplet/non vérifié, retours, contrôle d'accès, CSRF, triggers immuables et FK/uniquité. Un échec provoqué après insertion de la deuxième créance annule toutes les créations ; une nouvelle tentative aboutit ensuite.

## Anomalies pendant développement

- L'ancienne copie n'était plus disponible : récupération exacte par bundles, sans annoncer que ses fichiers non commités avaient survécu.
- Un test de migration lisait des contraintes avec une connexion mise en cache avant une migration effectuée par un autre moteur. La requête de définition SQL et une connexion neuve confirmaient la présence des contraintes. Le moteur d'inspection est désormais renouvelé après migration ; toutes les assertions de contraintes sont conservées.
- Les états de simulation restent les codes P5-B réels (`CALCUL_ADMISSIBLE_PROVISOIRE`), sans renommer le métier pour le nouveau test.

## Contrôles non exécutés

**PostgreSQL natif : non exécuté.** Aucun Docker/Podman, `postgres` ou `initdb` utilisable n'a été trouvé dans cette reprise. Aucune base conservée n'a été consultée ou migrée. Les sept tests ignorés de la campagne sont : deux courses P5-C, une migration native P5-C, trois courses groupe/individuel existantes et la migration native P5-CONF.1b. Ils ne constituent pas des réussites.

Les nouvelles courses ouvrent deux sessions indépendantes, vérifient des PID distincts et démontrent le blocage avec `pg_blocking_pids` avant libération du verrou ; attentes et transactions bornées. Scénarios : double constitution d'une même réalisation, deux compléments à la même révision. Le cycle natif de migration exige un nom, une confirmation exacte, un marqueur PostgreSQL et une base vide. Les tests d'API natifs réutilisent le garde `neosys_p4p5_*` et son marqueur. SQLite ne prouve pas ces garanties natives.

**Chromium : non exécuté.** Playwright est disponible, mais pas son navigateur. La tentative d'installation dans un cache neuf a échoué sur des archives de 0 MiB/tronquées (`End of central directory record signature not found`). Aucun test de bout en bout avec FastAPI/PostgreSQL n'est déclaré réussi. Le test `creances_ui.cjs --chromium` est préparé dans la CI et reste explicitement un test HTTP simulé.

**GitHub Actions : non déclenché, aucune publication.** La configuration 17/18 existante est complétée avec une base de migration P5-C neuve, sans neutraliser de test ni changer les dépendances de synthèse.

## Limites fonctionnelles et verdict

**Livraison locale implémentée et testée sur SQLite/DOM ; validation technique native partielle.** Pas de GO pour activer la fonctionnalité financière en production. La revue du code peut commencer, puis les preuves natives et Chromium doivent être obtenues dans un environnement autorisé. Aucune recette humaine intermédiaire n'est demandée ; la campagne consolidée est enrichie pour la fin des développements.

Le futur module de facturation devra impérativement appeler le garde dans chaque transaction d'engagement. Aucun test ne prétend vérifier une émission de facture qui n'existe pas encore. Les créances concernées par des retours restent gelées avant engagement jusqu'au registre compensatoire dédié. Les dossiers historiques sans configuration documentaire figée restent non facturables en attente d'une reprise explicite. Les plafonds consommables et l'incident réel PharmaGabon restent ouverts. Aucun changement de règle P4 de stock, fidélité, remboursement, encaissement ou clôture ; aucune activation du groupe, publication ou migration conservée.
