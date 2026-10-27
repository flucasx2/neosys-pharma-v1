# Reprise et exécution P5-C.2

## Récupération sans double application

La livraison contient le bundle complet, le patch incrémental binaire, son SHA-256, un manifeste et des PDF fictifs. Vérifier les empreintes avant utilisation. Ne pas remplacer le dossier Windows ni changer sa branche sans examiner `git status`, `git log` et les fichiers non commités.

Option recommandée dans un répertoire isolé :

```powershell
git clone --branch work/p5-c-2-facturation .\P5_C_2.bundle .\NeoSys_P5C2_Isole
cd NeoSys_P5C2_Isole
git log -2 --oneline
git merge-base --is-ancestor b8ddf845695f1e82a8d1cbcf0b06e42824bf2133 HEAD
```

Alternative exclusive : dans une copie propre au commit C1 exact, `git apply --check p5-c-2.patch` puis `git apply p5-c-2.patch`. Ne jamais appliquer le patch dans la copie déjà récupérée du bundle. La vérification Work compare l'arbre obtenu par application dans un index jetable à celui du commit livré.

## Dépendances et contrôles locaux sans base conservée

Installer Python 3.14 et `python -m pip install -e '.[dev]'` dans un venv isolé. Les exemples suivants sont destinés à un terminal de test neuf, sans variables de base héritées. Ne pas lancer l'application sur l'URL d'une base conservée.

```powershell
$env:TEST_DATABASE_URL = 'sqlite+pysqlite://'
Remove-Item Env:TEST_P5C2_MIGRATION_URL -ErrorAction SilentlyContinue
Remove-Item Env:TEST_P5C_MIGRATION_URL -ErrorAction SilentlyContinue
python -m pytest -q -rs tests/test_p5c2_facturation.py tests/test_p5c2_migration.py tests/test_p5c_creances.py tests/test_p5c_migration.py tests/test_p5b_3_encaissement_prise_en_charge.py tests/test_p4p5_groupe_organismes.py
python -m unittest discover -s ci/tests -q
npm install --prefix .qa-p5c2 --no-audit --no-fund jsdom@30.1.3 playwright@1.58.0
$env:NODE_PATH = "$PWD\.qa-p5c2\node_modules"
node tests/facturation_organisme_ui.cjs
node tests/creances_ui.cjs
node tests/conventions_ui.cjs
```

Les contrôles natifs seront ignorés dans cette campagne SQLite : c'est attendu, sans constituer une réussite native. Avec le binaire Playwright correspondant installé : `node tests/facturation_organisme_ui.cjs --chromium`. Cette variante conserve HTTP simulé.

## Recette PostgreSQL native protégée

Préparer un serveur PostgreSQL local de test et un rôle autorisé à créer des bases. Définir `P5C2_ADMIN_URL` dans l'environnement sécurisé local vers PostgreSQL localhost et la seule base de maintenance `/postgres`. Ne jamais inscrire le mot de passe dans le dépôt ou la conversation.

```powershell
python scripts/recette_p5c2_postgresql.py --suffixe rc2_20261019
```

Le script affiche identité/version/port/rôle, vérifie que les deux noms sont absents puis demande de recopier le suffixe. Il crée uniquement :

- `neosys_p4p5_p5c2_<suffixe>` : tables/tests API et courses, marqueur `NEOSYS_P4P5_DISPOSABLE`.
- `neosys_p5c2_migrations_<suffixe>` : chaîne Alembic et préservation historique, marqueur `NEOSYS_P5C2_DISPOSABLE`.

Aucun DROP DATABASE. En cas de création partielle, conserver les bases et choisir un nouveau suffixe pour la tentative suivante. Toute suppression nécessite une autorisation distincte. Les fixtures réinitialisent les tables uniquement dans les bases de test explicitement confirmées et marquées ; elles ne doivent jamais viser une base à préserver. Les tests d'émission activent le garde de recette uniquement dans leur portée et vérifient la base réelle. Les tests natifs ne doivent pas rester ignorés dans le résultat attendu. Conserver logs et `select version()`.

Le script exécute la migration C2 jusqu'à 06 et la préservation d'une créance C1 fictive, ainsi que les scénarios C2/C1/P5-B.3/groupe. Le test de migration C1 séparé exige sa propre base neuve : ne pas réutiliser la base de migration C2 ; la CI provisionne les deux.

## GitHub Actions — seulement après autorisation

Aucun workflow distant n'a été déclenché. Après autorisation, publier la branche technique livrée, vérifier son SHA et sélectionner **le workflow de cette branche** dans Actions, pas une ancienne version de main. Paramètres manuels : `target_branch=work/p5-c-2-facturation`, `expected_sha=<SHA distant exact de 40 caractères>` ; champ « Use workflow from » = cette même branche.

Le workflow conserve Python 3.14, SQLite complet, matrice PostgreSQL 17/18, navigateur et synthèse ; ajoute la base neuve `neosys_p5c2_migrations_ci` et le scénario UI C2. Les tests API natifs utilisent `neosys_p4p5_ci` marquée. Aucun flag d'émission global de production ajouté. Lire les résultats/skips sur le SHA applicatif exact ; la préparation locale et les 48 tests de politique ne prouvent pas un run GitHub réussi.

## Consultation dans l'application isolée

Installer les migrations uniquement sur une nouvelle base jetable identifiée. Les permissions nouvelles n'ont aucune attribution implicite : créer des utilisateurs fictifs explicitement habilités selon P1, dans cette base seulement. Réutiliser un dossier C1 complet et vérifié, puis ouvrir Créances → Préparer bordereaux et factures. La prévisualisation est marquée BROUILLON ; l'émission reste indisponible hors garde CI/native jetable. Les PDF émis lors des tests ne sont jamais des factures fiscales.

Consulter les arbitrages dans P5_C_2_DOCUMENTS_ORGANISMES.md et les non-conformités. Ne pas lever l'interdiction d'émission pour effectuer une recette sur une base conservée. La campagne humaine reste unique, différée jusqu'à la consolidation ; aucun accord intermédiaire demandé.
