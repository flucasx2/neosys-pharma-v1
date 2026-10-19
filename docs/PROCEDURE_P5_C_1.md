# Reprise et validation P5-C.1

## Intégration locale

Ne pas remplacer le dossier Windows. Vérifier d'abord `git status --short`, branche et SHA. Depuis une copie isolée contenant `ba570569bb7063bf587ffac45c3eceff58dea93b`, importer le bundle puis créer un worktree sur son commit final. Alternative exclusive : vérifier `git apply --check p5-c-1.patch` puis appliquer ce seul patch sur la base exacte. Ne pas cumuler bundle et patch, ni deux patchs alternatifs. Le manifeste de livraison donne les SHA, les arbres et les empreintes. Le bundle livré contient l'historique complet.

Installer Python 3.14 et les dépendances du `pyproject.toml`. Ne pas exécuter Alembic sur une URL héritée d'un environnement métier. Vérifier les variables et l'identité d'une nouvelle base avant toute migration. Les nouvelles permissions doivent être attribuées uniquement dans les profils fictifs de test, selon les procédures P1 ; aucune attribution automatique dans la migration.

## Tests locaux ciblés

Dans un terminal de tests neuf, forcer explicitement SQLite pour cette première campagne (elle ne constitue aucune preuve PostgreSQL). Les contrôles natifs utilisent ensuite le script dédié.

```powershell
$env:TEST_DATABASE_URL = "sqlite+pysqlite://"
python -m pytest -q -rs tests/test_p5c_creances.py tests/test_p5c_migration.py tests/test_p5_conf_conventions.py tests/test_p5b_3_encaissement_prise_en_charge.py tests/test_p4p5_groupe_organismes.py tests/test_p5_conf1b_migration.py
python -m unittest discover -s ci/tests -q
npm install --prefix .qa-p5c --no-audit --no-fund jsdom@30.1.3 playwright@1.58.0
$env:NODE_PATH = "$PWD\.qa-p5c\node_modules"
node tests/creances_ui.cjs
node tests/conventions_ui.cjs
```

Avec un Chromium installé correspondant à Playwright : `node tests/creances_ui.cjs --chromium`. Ces tests simulent explicitement HTTP ; ils ne remplacent pas un parcours complet FastAPI/PostgreSQL.

## PostgreSQL natif local jetable

Choisir un suffixe neuf à chaque lancement. Le script refuse tout nom déjà présent, exige l'URL locale de maintenance `/postgres`, affiche version/identité serveur et demande le suffixe avant création. Le compte nécessite CREATE DATABASE. Fournir les identifiants par variable locale sécurisée, jamais dans une conversation ou un fichier versionné.

```powershell
# P5C_ADMIN_URL à définir dans votre environnement local, vers localhost et /postgres.
python scripts/recette_p5c_postgresql.py --suffixe rc1_20261019
```

Deux bases sont créées : `neosys_p4p5_p5c_<suffixe>` (tests API/concurrence) et `neosys_p5c_migrations_<suffixe>` (migration). Les marqueurs et confirmations sont transmis par le script. Aucune base n'est supprimée automatiquement. Si une création partielle échoue, choisir ensuite un autre suffixe ; ne jamais supprimer automatiquement la première. Les fixtures créent/suppriment leurs tables **uniquement** après contrôle de base neuve et marquée. Une base conservée n'est jamais une cible acceptable.

La recette doit rendre les deux courses P5-C et les trois courses P4/P5 existantes réellement exécutées, avec PID distincts et contention observée ; la migration native doit monter jusqu'à 20261019_05 et préserver l'organisme fictif. Conserver les logs et versions. Les ignorés restent des validations manquantes. Le test de copie SQLite de refus du downgrade est naturellement ignoré sur PostgreSQL ; il ne doit pas être confondu avec une course manquante.

## CI ultérieure — autorisation distincte obligatoire

La configuration est préparée, sans lancement distant. Après autorisation de publication, sélectionner le workflow **de cette branche** (pas une ancienne version de main), et renseigner `target_branch` avec la branche publiée et `expected_sha` avec son SHA distant exact. Vérifier l'identité des arbres si le commit est reproduit. La matrice PostgreSQL 17/18 crée une nouvelle base de migration `neosys_p5c_migrations_ci`, marquée `NEOSYS_P5C_DISPOSABLE`, avec confirmation exacte ; les tests API utilisent la base marquée existante `neosys_p4p5_ci` propre au service CI.

La synthèse existante exige SQLite, PostgreSQL et navigateur ; aucune dépendance obligatoire supprimée. Le parcours Créances Chromium préparé est **simulé** ; les parcours réels P4/P5 historiques restent distincts. Un parcours humain final P5-C avec données fictives reste à exécuter dans la campagne consolidée, sans activation de l'encaissement groupé hors contexte autorisé.
