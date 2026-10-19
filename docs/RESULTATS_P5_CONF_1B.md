# Résultats — P5-CONF.1b

## Verdict et base

**Livraison locale partielle, prête pour revue du code ; NO-GO pour clôturer P5-CONF.1b.** Les validations PostgreSQL natives, Chromium et humaines ne sont pas exécutées dans Work. Plusieurs fonctions contractuelles restent hors de cet incrément : voir les limites explicites dans `P5_CONF_1B.md`.

Bundle fourni et vérifié : historique complet, branche `recette/p5-conf-1a`, HEAD `40c8fb27cca0c9b532d2536e8bb542930dab4452`, après `3186bdf`. Nouvelle copie isolée `neosys-p5-conf1b-work` et branche `feat/p5-conf-1b-conventions-baremes`. Le poste Windows et les bases conservées n'ont pas été utilisés.

Les résultats antérieurs de recette P5-CONF.1a (24 Python, 1 ignoré, 20 assertions DOM et 20 Chromium, contrôle ciblé de permissions réussi) sont rapportés par le responsable dans la mission. L'acceptation avec réserve OBS-P5-UI-01 est conservée. Ils ne sont pas annoncés comme réexécutés ici. Le patch préparatoire n'a pas été appliqué.

## Fonctionnalités effectivement implémentées

- Administration intégrée à la fiche organisme : conventions/version/périodes/statut, régime embarqué, barèmes/exclusions, formulaires de champs et justificatifs.
- Réutilisation du moteur P5-B pour les fractions exactes, plafonds par ligne et arrondis explicites ; refus des clauses inconnues et barèmes potentiellement recouvrants.
- Bénéficiaires indépendants de la fidélité, adhésions/titulaire/ayants droit, décisions de droits avec révisions, consultation et paramétrage des priorités P5-A.
- Vérification manuelle par vente, adhésion, bénéficiaire, convention/configuration et révision ; pièces cumulatives/alternatives, champs typés et formats ; aucune confirmation automatique des droits.
- Preuve absente, périmée ou obsolète : calcul bloqué pour les conventions nouvellement configurées. Preuve d'une autre vente non réutilisée. Organisme configuré inactif : nouveau calcul bloqué. Refus prouvé conservé comme refus, pas confondu avec une donnée manquante.
- Métadonnées et références documentaires, régime, identité, auteur/date, vente et lignes historiques intégrés au snapshot financier. Pas d'ajout de facture ou de créance P5-C, pas de document binaire.
- Atomicité de création convention/configuration/audit/idempotence ; immuabilité structurelle ; protection contre les doubles clics, conflits et erreurs réseau côté interface.

## Contrôles exécutés

Python **3.14.8**, Node **24.19.0**, jsdom **30.1.3** ; dépendances installées hors dépôt. Les tests Python utilisent uniquement SQLite en mémoire ou fichiers temporaires. Les tests HTTP appellent réellement FastAPI et SQLAlchemy ; ils ne sont pas des tests navigateur. Aucune base conservée n'a été ouverte.

Commande de campagne ciblée :

```sh
TZ=Africa/Libreville PYTHONPATH=src:tests:<site-packages-3.14> python3.14 -m pytest -q \
 tests/test_p5_conf_conventions.py tests/test_p5_conf1b_migration.py \
 tests/test_p5b_1_moteur_prise_en_charge.py tests/test_p5b_2_integration_vente.py \
 tests/test_p5b_3_encaissement_prise_en_charge.py tests/test_p5a_tiers_payants.py
```

**55 passed, 1 skipped, 1 warning — 48,16 secondes.** La suite complète de plusieurs centaines de tests P1–P4 n'a pas été relancée. Le seul test ignoré est `test_postgresql_migration_contraintes_et_contention_reelle`, car `TEST_P5CONF1B_DATABASE_URL` n'est pas fourni. Ce test ignoré ne valide pas PostgreSQL.

| Contrôle | Exécution / résultat | Portée réelle |
|---|---|---|
| Nouveaux contrats et API | 15 cas pytest réussis dans la campagne | Versions/périodes, erreurs, idempotence, lecture seule, 401/403, CSRF, preuve par vente, révisions/refus/expiration, snapshots et rollback après insertion convention |
| Migration et protections de cible | 2 tests réussis | Chaîne Alembic, upgrade/check/downgrade/remontée SQLite, conservation organisme P4-B fictif, triggers et refus downgrade avec données, refus des noms protégés |
| Régressions P5-A/B | 38 tests réussis | Moteur séquentiel et invariants, priorités, droits, snapshots, encaissement individuel, retours et fidélité couverts par les tests existants sélectionnés |
| Nouvelle UI | 38 assertions DOM réussies | HTML et modules applicatifs réels ; authentification et réponses HTTP simulées. Contrats de catalogue, saisie, rejeu, conflits, bénéficiaire explicite, droits et changement de site |
| Chromium | Échec au lancement, aucun scénario exécuté | Archive téléchargée invalide puis exécutable absent. Scénario fourni avec origine localhost compatible crypto.randomUUID |
| PostgreSQL natif | Non exécuté | Binaire 16.2 obtenu, mais démarrage non privilégié impossible dans cet environnement. PostgreSQL 18.6 Windows non accessible |
| PowerShell | Script préparé, non exécuté | Work n'exécute pas le script Windows. Il reste à vérifier localement |
| Contrôles statiques | node --check, compilation Python et Git diff --check | Syntaxe et cohérence ; pas une preuve native ou humaine |

Après l'ajout du garde-fou organisme inactif, le scénario documentaire de vente a été réexécuté seul : **1 passed, 1 warning — 16,53 secondes**. Il vérifie également l'expiration, la révision, le refus, l'absence de réutilisation et la confirmation du snapshot. Ce rejeu n'est pas ajouté au nombre de tests uniques de la campagne.

Avertissement : dépréciation Starlette/httpx dans les dépendances de test, sans échec. Les fixtures et l'application utilisent des dates journalières ; le fuseau de test a été aligné sur Libreville.

## Défauts détectés et corrections

1. Le premier appel aux tests ne démarrait pas : ancien binaire Python 3.14 terminant par Bus error, y compris `--version`. Un runtime 3.14.8 séparé a été installé ; aucune adaptation métier.
2. Deux fixtures nouvelles recréaient un rôle de test déjà créé par `setup`, provoquant une erreur d'unicité. Les tests complètent explicitement les permissions du rôle existant sans changer la politique applicative. L'écart UTC des datetimes restitués par SQLite a été traité par comparaison de la représentation persistée avant/après.
3. Le test DOM a détecté une sélection de bénéficiaire non renseignée. Le formulaire impose désormais une option vide initiale et un choix explicite, ainsi que pour le résultat de vérification ; les assertions restent présentes.
4. L'enrichissement documentaire utilisait `ProduitModel.designation`, attribut absent, provoquant une erreur réelle de simulation. La correction utilise la désignation historique de la **ligne de vente**. La recherche catalogue utilise le contrat existant `nom`. Les tests de snapshot et de libellé catalogue couvrent ces cas.
5. La création P5-A d'adhésion ne contrôlait pas l'organisme inactif. Un refus serveur explicite et son test sont ajoutés ; aucun historique supprimé. Les preuves et nouveaux calculs de conventions configurées refusent également un organisme inactif.
6. Les booléens contractuels, champs et codes documentaires sont contrôlés strictement ; un `schema_version: true` n'est pas accepté comme version numérique 1. Les pièces inconnues, dupliquées ou non vérifiées ne satisfont pas une obligation.

Les exécutions intermédiaires en échec ne sont pas masquées : elles ont révélé les défauts ci-dessus, corrigés avant la campagne finale. Aucune assertion métier n'a été supprimée pour obtenir un succès.

## PostgreSQL et navigateur : blocages et contrôle préparé

Les exécutables PostgreSQL natifs 16.2 ont été extraits d'un paquet distribuant des binaires. `postgres --version` fonctionne. La création d'un répertoire de cluster sous un compte non privilégié échoue (`chown: Invalid argument` ; `runuser: cannot set groups: Operation not permitted`). Aucun contournement du refus PostgreSQL de fonctionner en root n'a été tenté. Aucun serveur PostgreSQL ni base n'a donc été créé. Ce n'est pas une validation PostgreSQL embarquée ou native.

Le script `scripts/recette_p5conf1b_postgresql.ps1` refuse une base préexistante, inspecte le serveur, crée exclusivement une base neuve préfixée, la marque et lance le test natif dédié. Le test utilise deux connexions indépendantes, observe la contention avec `pg_blocking_pids`, borne les attentes et vérifie un succès / un conflit / une configuration. Il contrôle les migrations, FK invalides et triggers sur cette cible. **Ces contrôles restent non exécutés ici.** Aucun drop automatique de base ni fixture historique `drop_all` n'est utilisé par ce chemin.

Le téléchargement Playwright Chromium Headless Shell 151, build 1234, échoue sur une archive tronquée ; le lancement de `tests/conventions_ui.cjs --chromium` échoue avant les scénarios. Le test DOM a réussi ; ce résultat ne remplace ni Chromium, ni le vrai backend PostgreSQL.

## Avant acceptation

Exécuter PostgreSQL 18.6 jetable, le scénario Chromium fourni, puis les 21 scénarios de recette réelle de `RECETTE_P5_CONF_1B.md`. Traiter les limites de sélecteurs et l'ergonomie de preuve par identifiant avant généralisation. Arbitrer les plafonds/cumuls, règles non supportées et succession des conventions ouvertes. Maintenir les réserves antérieures ; ne pas commencer P5-C à partir de ce seul incrément.

Aucun push, PR, merge, modification de main, migration sur base conservée, déploiement ou activation groupée. Le drapeau groupé conserve son défaut désactivé.

## Fichiers créés ou modifiés (20)

- `JOURNAL_DEVELOPPEMENT.md`
- `REPRISE_NEOSYS_PHARMA.md`
- `docs/P5_CONF_1B.md`
- `docs/RESULTATS_P5_CONF_1B.md`
- `docs/RECETTE_P5_CONF_1B.md`
- `docs/REGISTRE_NON_CONFORMITES_P5.md`
- `migrations/versions/20261019_01_p5_conf_conventions.py`
- `scripts/recette_p5conf1b_postgresql.ps1`
- `src/neosys_pharma/application/configuration_convention_service.py`
- `src/neosys_pharma/application/projection_prise_en_charge.py`
- `src/neosys_pharma/application/tiers_payants_service.py`
- `src/neosys_pharma/domain/configuration_convention.py`
- `src/neosys_pharma/domain/prise_en_charge.py`
- `src/neosys_pharma/infrastructure/tiers_payants_models.py`
- `src/neosys_pharma/presentation/tiers_payants_api.py`
- `src/neosys_pharma/presentation/web/index.html`
- `src/neosys_pharma/presentation/web/conventions.js`
- `tests/conventions_ui.cjs`
- `tests/test_p5_conf1b_migration.py`
- `tests/test_p5_conf_conventions.py`
