# Intégration et recette humaine — P5-CONF.1b

## Préserver l'environnement accepté

Le projet Windows `D:\Projets_Python\NeoSys_P5_CONF_1A` et la base `neosys_p5conf1a_recette_temp` sont conservés. Ne pas leur appliquer ce lot ou une migration sans autorisation distincte. Préserver également les bases P5-B, `neosys_pharma_v1` et `neosys_p46_recette_20261012`.

Base obligatoire du patch : `40c8fb27cca0c9b532d2536e8bb542930dab4452`. Depuis le dépôt contenant ce commit, utiliser un nouveau worktree et un chemin absent :

```powershell
git status --short
git show --no-patch 40c8fb27cca0c9b532d2536e8bb542930dab4452
git worktree add -b recette/p5-conf-1b ..\NeoSys_P5_CONF_1B 40c8fb27cca0c9b532d2536e8bb542930dab4452
cd ..\NeoSys_P5_CONF_1B
git apply --check C:\livraison\p5-conf-1b.patch
git am C:\livraison\p5-conf-1b.patch
py -3.14 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
```

Ne pas appliquer en plus le patch préparatoire `p5-conf-1.patch`, ni rejouer le patch accepté P5-CONF.1a.

## Contrôles automatisés locaux

La commande suivante utilise uniquement les bases SQLite propres aux tests si `TEST_DATABASE_URL` est absent. Vérifier également l'absence d'une configuration PostgreSQL de tests héritée ; ne jamais mettre une base conservée dans une variable de tests.

```powershell
.\.venv\Scripts\python.exe -m pytest -q tests/test_p5_conf_conventions.py tests/test_p5_conf1b_migration.py tests/test_p5b_1_moteur_prise_en_charge.py tests/test_p5b_2_integration_vente.py tests/test_p5b_3_encaissement_prise_en_charge.py tests/test_p5a_tiers_payants.py
$qaNode = Join-Path $env:TEMP 'neosys-p5conf1b-node'
npm install --prefix $qaNode jsdom@30.1.3 playwright@1.62.1
$env:NODE_PATH = Join-Path $qaNode 'node_modules'
node tests/conventions_ui.cjs
node (Join-Path $qaNode 'node_modules/playwright/cli.js') install chromium
node tests/conventions_ui.cjs --chromium
```

Le navigateur utilise l'origine `http://localhost:8765/`, compatible avec `crypto.randomUUID()`. Les réponses HTTP de ce test sont simulées. Ce succès éventuel ne remplace pas les étapes avec le vrai serveur ci-dessous.

## PostgreSQL natif — base dédiée aux tests automatisés

Prérequis : PostgreSQL local, `psql` dans PATH, rôle autorisé à créer une base, Python 3.14 avec le projet installé. Utiliser pgpass ou `PGPASSWORD` local ; ne transmettre aucun mot de passe dans la conversation.

Le script inspecte l'identité du serveur et refuse une base déjà existante. Première exécution en lecture seule :

```powershell
.\scripts\recette_p5conf1b_postgresql.ps1 -PgHost 127.0.0.1 -PgPort 5432 -PgUser postgres -DatabaseName neosys_p5conf1b_auto_20261019
```

Après vérification du serveur affiché, autoriser explicitement la création de cette seule base fraîche :

```powershell
.\scripts\recette_p5conf1b_postgresql.ps1 -PgHost 127.0.0.1 -PgPort 5432 -PgUser postgres -DatabaseName neosys_p5conf1b_auto_20261019 -CreerBaseJetable -Python .\.venv\Scripts\python.exe
```

Le test exige l'URL dédiée `TEST_P5CONF1B_DATABASE_URL`, le nom exact `P5CONF1B_CONFIRM_DATABASE` et le marqueur `P5CONF1B_MARKER` concordant avec le commentaire de base. Il refuse une base non vide avant migration. La commande vérifie la chaîne complète, la conservation d'un organisme P4-B fictif, Alembic check, un downgrade à vide et une remontée, les triggers/FK, puis une course réelle entre deux transactions. Le blocage est observé par `pg_blocking_pids`, les PID sont distincts, et les attentes sont bornées. Résultat attendu : un succès et un conflit, une seule configuration. Une erreur ou un test ignoré n'est pas un succès. Conserver la sortie exacte et la version serveur.

Le script ne supprime rien. Après le test, la base contient des preuves fictives et ne peut plus être réutilisée par ce script : choisir un nouveau nom pour une nouvelle exécution. Ne jamais définir `TEST_DATABASE_URL` vers une base conservée : les fixtures historiques peuvent supprimer leurs tables. Le contrôle natif fourni évite ces fixtures.

## Instance distincte pour la recette humaine

Créer une **autre** base neuve, par exemple `neosys_p5conf1b_humaine_20261019`, après vérification du serveur et de son absence. Ne pas réutiliser la base automatisée ni une base conservée. Définir `DATABASE_URL` vers cette seule base ; vérifier `current_database()` et appliquer `alembic upgrade 20261019_01`. Initialiser une seule fois selon le bootstrap P1 du README, puis démarrer l'application selon ce même README. Ne pas activer l'encaissement groupé.

Créer explicitement les affectations et rôles fictifs :

- Responsable conventions : `tiers_payant.consulter`, `tiers_payant.convention.gerer` ; ajouter `catalogue.consulter` pour les sélecteurs de produits/catégories.
- Responsable droits : `tiers_payant.consulter`, `tiers_payant.adhesion.consulter`, `tiers_payant.adhesion.gerer`, `vente.consulter` ; droits de préparation/transmission séparés si nécessaire.
- Responsable priorités : `tiers_payant.consulter`, `tiers_payant.priorites.gerer`.
- Lecteur : permissions de consultation requises, sans gestion.
- Utilisateur interdit et seconde organisation/site fictifs pour l'isolation.

Aucun droit n'est attribué automatiquement par la migration.

## Scénarios sur l'application réelle

| ID | Actions à effectuer | Résultat attendu |
|---|---|---|
| C01 | Administration → Organismes, consulter un organisme actif, Conventions et droits | Écran rattaché au bon organisme ; fiche autonome acceptée conservée |
| C02 | Nouvelle convention, référence QA, période finie, régime code/libellé, mode EXTERNE, types titulaire/ayant droit | Saisie possible sans fiche fidélité |
| C03 | Barème QA : taux 80/100, plafond par ligne 2 000 XAF, arrondi inférieur explicite ; catégories/produits ou tous | Valeurs enregistrées exactement ; aucun calcul JavaScript |
| C04 | Champ MATRICULE, texte obligatoire, format chiffres ; carte OU attestation dans groupe IDENTITE ; ordonnance obligatoire sans groupe | Définition conservée avec la version |
| C05 | Consulter puis préparer version 2, période après fin de version 1 | Historique intact ; nouvelle version distincte ; tentative de chevauchement refusée |
| C06 | Deux opérateurs créent une même nouvelle version à partir du même historique | Conflit explicite pour l'opération perdante, pas de doublon |
| C07 | Tenter taux >100 %, plafond négatif, barèmes recouvrants ou produit étranger | Refus ; aucune convention/configuration partiellement créée |
| C08 | Bénéficiaires et adhésions : créer titulaire et ayant droit fictifs ; rechercher puis les associer à la convention | Adhésion créée avec droits À vérifier ; aucune fidélité requise |
| C09 | Modifier les droits : CONFIRMES, référence et date/heure réelles du contrôle fictif | Révision augmentée, audit ; confirmation refusée si preuve P5-A manque |
| C10 | Priorités : premier organisme éventuellement complémentaire, puis deux autres complémentaires avec conventions valides ; enregistrer dates/motif | Ordre commun à l'organisation, principale facultative ; anciennes ventes inchangées |
| C11 | Préparer une vente prise en charge, noter son identifiant, choisir le bénéficiaire et simuler sans preuve documentaire | Calcul bloqué pour les nouvelles conventions configurées ; aucune créance |
| C12 | Vérifications et justificatifs : charger cette vente, choisir convention/adhésion/bénéficiaire ; omettre ordonnance ou matricule | Refus métier ; aucun statut de droit confirmé implicitement |
| C13 | Fournir matricule numérique, carte ou attestation + ordonnance, références fictives, cases effectivement contrôlées, résultat explicite et période valide | Preuve immuable enregistrée, auteur et référence traçables ; aucune requête à un portail externe |
| C14 | Relancer simulation, transmettre et confirmer via le parcours de vente existant | Calcul serveur selon l'ordre ; snapshot avec régime/bénéficiaire/références et parts ; pas de créance P5-C créée |
| C15 | Encaisser la part client selon P5-B existant, consulter le snapshot et le reçu | Parts financières historiques conservées ; dossier documentaire consultable depuis la prise en charge. Le PDF existant n'est pas enrichi de pièces médicales |
| C16 | Autre vente du même bénéficiaire, ou modification des droits après une preuve | La preuve de la première vente / de l'ancienne révision ne valide pas la seconde opération |
| C17 | Déclarer un refus explicite, motif/référence et aucune pièce favorable ; simuler | Refus tracé, suite selon conventions ; pas de transformation silencieuse en droits confirmés |
| C18 | Rejeu même saisie après perte de réponse, double clic ; puis clé identique avec contenu différent par API | Une écriture au rejeu ; contenu différent refusé ; pas de succès financier inventé côté navigateur |
| C19 | Lecteur, utilisateur interdit, mauvaise organisation/site/emplacement, CSRF absent | Consultation ou refus selon droits ; mutations non autorisées refusées côté serveur |
| C20 | Désactiver organisme puis tenter une nouvelle adhésion ou preuve | Refus des nouvelles opérations ; conventions et preuves antérieures conservées |
| C21 | Changer de site / se déconnecter pendant un chargement | Aucune donnée tardive du précédent contexte réaffichée |

Consigner pour chaque ligne : SHA réellement appliqué, organisation/site, rôle, données fictives, code HTTP, résultat, capture et anomalies. La recette complète P5-B et les observations hors périmètre restent ouvertes ; aucun scénario de ce cahier ne vaut acceptation définitive sans votre exécution.
