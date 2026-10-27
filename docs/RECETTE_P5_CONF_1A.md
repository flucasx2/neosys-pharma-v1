# Intégration et recette — Administration autonome des organismes

## Intégration locale

Base obligatoire : commit `5ad489ccb2ccac4c511cda9b1a87104245ddab28`. Le patch livré ne contient que le sous-lot P5-CONF.1a et ses documents/tests. Ne pas appliquer en plus le patch préparatoire `p5-conf-1.patch`.

Préserver la copie Windows actuelle et ses fichiers non suivis. Exemple PowerShell, depuis le dépôt Windows, vers un nouveau worktree dont le chemin n'existe pas :

```powershell
git worktree add -b recette/p5-conf-1a ..\NeoSys_P5_CONF_1A 5ad489ccb2ccac4c511cda9b1a87104245ddab28
cd ..\NeoSys_P5_CONF_1A
git apply --check C:\chemin\p5-conf-1a.patch
git am C:\chemin\p5-conf-1a.patch
```

Créer son environnement Python 3.14 et installer le projet avec ses dépendances de test. Installer jsdom pour les tests DOM; installer Playwright et son Chromium pour exécuter le même scénario avec `--chromium`. Ces tests UI utilisent des réponses HTTP simulées; la recette manuelle ci-dessous vérifie le vrai backend.

Ne pas réutiliser les bases conservées, y compris `neosys_p5b_validation_temp` et `neosys_p5b_pytest_temp` si elles contiennent les travaux à conserver. Sur une instance PostgreSQL locale isolée, vérifier l'identité du serveur et l'absence de la base proposée `neosys_p5conf1a_recette_temp` avant de la créer. Ne pas la recréer si elle existe. Vérifier `current_database()` et le serveur avant toute migration.

Après cette vérification seulement, définir `DATABASE_URL` vers cette base fraîche, puis exécuter :

```powershell
python -m alembic upgrade 20261018_01
python -m alembic current
```

Initialiser uniquement cette base neuve selon la procédure bootstrap P1 du README. Ne jamais relancer le bootstrap sur une base déjà initialisée. Démarrer l'application avec les instructions existantes du dépôt. Aucune activation de l'encaissement groupé n'est nécessaire.

## Permissions à attribuer explicitement dans l'instance fictive

- Gestionnaire : `tiers_payant.organisme.gerer` et affectations site/emplacement compatibles.
- Lecteur : `tiers_payant.consulter` sans permission de gestion.
- Utilisateur interdit : aucune de ces deux permissions.
- Un utilisateur/site d'une seconde organisation fictive pour le contrôle d'isolation.

La migration n'accorde ces permissions à personne. Le rôle système de gestion d'organisation ne reçoit pas implicitement la nouvelle permission; utiliser les mécanismes existants de rôle personnalisé et d'affectation.

## Scénarios dans l'application réelle

| Étape | Action | Résultat attendu |
|---|---|---|
| 1 | Se connecter comme gestionnaire, Administration → Organismes de prise en charge | Liste visible sans ouvrir Clients ni Fidélité. |
| 2 | Nouvel organisme, code `QA-ALPHA`, nom `Assureur Alpha QA`, Enregistrer | Fiche active créée et visible dans la liste. Aucun client/compte fidélité créé. |
| 3 | Rechercher `ALPHA`, puis filtrer Actifs | Organisme retrouvé; pagination utilisable. |
| 4 | Modifier le nom en `Assureur Alpha modifié QA` | Modification enregistrée, même identifiant, révision augmentée et audit avant/après. |
| 5 | Ouvrir la fiche dans deux onglets; enregistrer dans le premier, puis dans le second | Le second reçoit un conflit et doit recharger; aucune correction silencieuse. |
| 6 | Passer le statut Inactif, puis filtrer Inactifs | Organisme conservé dans l'administration; absent des nouvelles associations client actives. Les conventions/historiques ne sont pas supprimés. |
| 7 | Réactiver et ouvrir une fiche client existante | Le même organisme redevient disponible à l'association; aucune nouvelle identité organisme. |
| 8 | Avec le lecteur, consulter la fiche | Champs en lecture seule, aucune action de gestion disponible. Un appel direct de mutation doit être refusé. |
| 9 | Avec l'utilisateur interdit / autre organisation ou site non affecté | Menu ou accès refusé; pas de données d'une autre organisation. |
| 10 | Simuler une perte de réponse lors de création dans l'environnement de test; réessayer la même saisie | Même clé côté navigateur, un seul organisme. Conserver la trace réseau; ne pas faire ce test sur une vraie opération. |
| 11 | Changer de site ou se déconnecter pendant le chargement | Aucune réponse tardive du précédent contexte ne réaffiche ses données. |
| 12 | Vérifier une convention/vente historique associée avant et après renommage | Snapshot financier historique inchangé; la fiche référentielle actuelle peut afficher le nouveau nom. |

Consigner identifiants fictifs, date, SHA testé, utilisateur/rôle, site, résultat, code HTTP et capture utile. Aucun identifiant ou mot de passe de portail externe ne doit être saisi.

## Limite explicite de cette recette

Ce sous-lot ne permet pas encore de paramétrer toutes les conventions, barèmes, imports de bénéficiaires, règles de justificatifs et preuves dans l'interface. Ne pas tenter de reprendre la recette P5-B complète sur la seule base de cet écran. La validation du sous-lot n'est ni la clôture de P5, ni une autorisation de commencer P5-C.

## Commandes de contrôle ciblé sous PowerShell

Depuis le nouveau worktree, avec Python 3.14 et Node disponibles :

```powershell
py -3.14 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
.\.venv\Scripts\python.exe -m pytest -q tests/test_p5_conf_organismes.py tests/test_p5a_tiers_payants.py
```

Pour éviter de modifier les dépendances du dépôt, installer les outils JavaScript dans un dossier de contrôle séparé :

```powershell
$qaNode = Join-Path $env:TEMP "neosys-p5conf1a-node"
npm install --prefix $qaNode jsdom@30.1.3 playwright@1.62.1
$env:NODE_PATH = Join-Path $qaNode "node_modules"
node tests/organismes_ui.cjs
node (Join-Path $qaNode "node_modules/playwright/cli.js") install chromium
node tests/organismes_ui.cjs --chromium
```

L'installation du navigateur nécessite un accès réseau et de l'espace disque. Un échec d'installation ne valide aucun scénario Chromium. Les fixtures d'autorisation dépendent du jour courant : aligner l'horloge de l'environnement de contrôle sur celle de l'application (Libreville), surtout près de minuit.
