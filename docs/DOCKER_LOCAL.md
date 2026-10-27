# Docker local — mise en service

La construction app/tests et la mise en service de db/app ont été autorisées.
Les images ont été construites avec succès et la base Docker dédiée a été migrée
jusqu'à 20261019_06 après vérification de sa cible et de son schéma vide.
Le bootstrap reste une saisie interactive de l'utilisateur. Aucun service de tests
n'a été lancé. Branche : `dev/codex-docker`. Les commandes Compose utilisent
`-p neosys-pharma-dev` et `--env-file .env.docker.example` (fichier sans secret).

## Images et dépendances

Cible fixée : linux/amd64, CPython 3.14 classique, glibc.
Manifestes réellement consultés le 20 octobre 2026 via imagetools inspect :

| Image | Version du manifeste | Digest linux/amd64 épinglé |
|---|---|---|
| python:3.14-slim-bookworm | 3.14.8-slim-bookworm | sha256:a66d3a463d0be3cc537c269b0d3418746dda512417a975559a0eaa8a6406baaf |
| postgres:18 | 18.6 | sha256:885953109528ad3dfc90362b1a6f50a78620b5315be19f187753d267e484dc5b |

Index multi-plateformes observés :
- Python : sha256:48b13b003dda20b16f9442b8475aa05fe21bf6579a8c881db92ffb4d8fd20f83
- PostgreSQL : sha256:74935e72241653ca55e0414067e6d8763aceb8a810eb51b452253ec3dcfc4336

Les digests employés sont ceux des manifestes amd64, pas des attestations.
Les images épinglées ont été téléchargées lors de la mise en service autorisée.
Les verrous runtime/tests sont résolus, hachés
et alignés ; voir requirements/README.md. Aucun paquet système non verrouillé
n'est installé par apt pendant le build.

Les 48 wheels du verrou tests ont été téléchargées avec pip --no-deps,
--require-hashes, --only-binary et les tags CPython 3.14/manylinux x86_64.
Leurs SHA-256 correspondent aussi aux 39 entrées runtime. --no-deps évite que pip
sous Windows réévalue les marqueurs système du graphe Linux déjà résolu par uv.
Ce contrôle confirme la disponibilité et l'intégrité des artefacts, pas leur
installation ou exécution. Outils et wheels restent dans .codex-tools-download/,
ignoré par Git et exclu du contexte Docker.

## Architecture et isolation

app expose uniquement 127.0.0.1:8001:8000. Uvicorn écoute sur 0.0.0.0:8000 dans
le conteneur. Le code src est monté en lecture seule et rechargé ; dépendances et
migrations nécessitent une reconstruction lors de leur évolution. /health teste
HTTP seulement, pas la connexion PostgreSQL ni le schéma Alembic.

Réseau interne development : app, db. Réseau interne testing : tests, test-db.
Réseau frontend non interne : app uniquement, nécessaire pour la publication
HTTP sous Docker Desktop. La publication a été vérifiée sur 127.0.0.1:8001
(réponses 200 de / et /health). PYTHONPATH pointe vers le src monté pour que les
modifications du code soient réellement chargées sans reconstruction.
Aucun port PostgreSQL publié, aucun socket Docker monté, aucun accès aux fichiers
PostgreSQL Windows, aucun réseau hôte. tests ne reçoit ni le secret de db ni un
montage du code hôte complet. Son seul secret est test_db_password. Le modèle
Compose n'hérite ni DATABASE_URL ni TEST_DATABASE_URL du shell.

Ces contrôles portent sur le Compose fourni. Un opérateur pouvant modifier les
réseaux, ajouter des secrets ou contourner l'entrypoint peut changer ces garanties.
Le port PostgreSQL n'est pas publié ; seule la publication HTTP est active.

## Secrets

Aucun mot de passe dans .env.docker.example, Dockerfile ou Compose. Les secrets
Compose sont deux fichiers distincts ignorés par Git et par le contexte Docker :
.secrets/dev-db-password.txt et .secrets/test-db-password.txt. Les serveurs utilisent
POSTGRES_PASSWORD_FILE ; l'application lit uniquement son secret autorisé.

La commande prepare_secrets.py génère deux valeurs aléatoires différentes,
ne les affiche jamais et refuse d'écraser les fichiers existants. Elle a été
exécutée pendant la mise en service, sans affichage des valeurs. Sous Windows,
protéger le dossier par les ACL du compte utilisateur :
les modes POSIX ne remplacent pas les ACL NTFS. Les secrets Compose locaux sont des
fichiers montés, pas un coffre chiffré ; le propriétaire du poste peut les lire.
Ne jamais afficher leurs contenus ou les archiver avec les preuves de recette.

L'entrypoint refuse le .env applicatif, tout DATABASE_URL/TEST_*_URL hérité, les
paramètres PG*, un mot de passe passé directement par environnement, un rôle ou
chemin de secret inattendu, ainsi qu'un secret vide/placeholder. Il effectue ces
contrôles avant lecture du secret puis tout import applicatif, connexion ou
commande. DATABASE_URL est construite uniquement vers db ou test-db ; le secret
est encodé dans l'URL sans affichage. exec et --entrypoint peuvent contourner ce
contrôle : ne pas les employer pour les opérations de base.

## Conservation du développement

Le volume externe nommé neosys_pharma_dev_pgdata doit être créé explicitement
après autorisation. Compose refuse le démarrage s'il manque. Il ne gère pas son
cycle de suppression, y compris lors de la suppression des ressources Compose.
Le volume a été créé après confirmation de son absence. Ne jamais employer down -v, volume rm
ou les purges de volumes. Un volume externe ne protège pas contre un administrateur
qui le supprime directement : prévoir sauvegarde et restauration avant migration.

PostgreSQL 18 monte ce volume sur /var/lib/postgresql. Ne jamais monter les données
Windows. test-db utilise tmpfs : données perdues à son arrêt. Modifier un fichier
secret ne change pas le mot de passe d'un cluster déjà initialisé ; prévoir une
rotation explicite et autorisée si nécessaire.

## Tests et recette humaine

La cible tests exécute initialement les fixtures SQLite uniquement et rejette les
URL de tests héritées. Les suites PostgreSQL natives optionnelles restent ignorées
sans leurs paramètres. Aucun garde-fou P4/P5 changé. Leur orchestration de bases
jetables, commentaires et confirmations reste une phase séparée. Chromium et Node
ne sont pas encore installés. Ne pas annoncer de couverture native complète.

Les migrations et le bootstrap restent manuels. Aucun n'est lancé par l'entrypoint.
La recette humaine conservera ses données dans db, avec bootstrap une fois sur base
vide migrée. Les seeds navigateur ne doivent jamais viser cette base persistante.
L'émission P5-C.2 reste limitée aux bases jetables selon les règles existantes.
Le message du bootstrap mentionne encore 8000 ; l'adresse humaine sera 8001.

## Contrôles statiques reproductibles

```powershell
python -B docker/check_static.py
docker compose -p neosys-pharma-dev --env-file .env.docker.example --profile test config --quiet
git diff --check
```

check_static.py ne lit aucun secret et n'importe pas l'application. Il teste le
garde avec des valeurs synthétiques, vérifie les réseaux, secrets, ports, volume
externe et verrous, et simule des URL héritées dans l'environnement du sous-processus
Compose. Le JSON reste en mémoire et n'est pas affiché.

## Construction (déjà réalisée)

```powershell
Set-Location -LiteralPath 'D:\Projets_Python\NeoSys_Pharma_Dev'
python -B docker/check_static.py
docker compose -p neosys-pharma-dev --env-file .env.docker.example --profile test config --quiet
docker compose -p neosys-pharma-dev --env-file .env.docker.example --profile test build app tests
```

Ces commandes ne démarrent pas les services et ne créent pas de volume.
L'installation des dépendances hachées et le packaging ont réussi pour app/tests.

## Préparation initiale (déjà réalisée)

Historique : ne pas régénérer les secrets ni recréer l'installation existante.

```powershell
python docker/prepare_secrets.py
docker volume create --label com.neosys.purpose=development-preserved neosys_pharma_dev_pgdata
docker compose -p neosys-pharma-dev --env-file .env.docker.example up -d db
docker compose -p neosys-pharma-dev --env-file .env.docker.example run --rm --no-deps app check-target
```

Les migrations ont ensuite été appliquées explicitement à neosys_docker_dev.
Ne pas lancer les tests avant leur autorisation.

## Utilisation quotidienne

Depuis le dossier du projet, démarrer ou reprendre sans réinitialiser les données :

```powershell
docker compose -p neosys-pharma-dev --env-file .env.docker.example up -d --wait db app
```

Arrêter proprement les deux services, en conservant conteneurs et volume :

```powershell
docker compose -p neosys-pharma-dev --env-file .env.docker.example stop app db
```

État et redémarrage :

```powershell
docker compose -p neosys-pharma-dev --env-file .env.docker.example ps
docker compose -p neosys-pharma-dev --env-file .env.docker.example restart db app
```

Le bootstrap interactif est réservé à la première installation, sur base migrée
vide, et demande le mot de passe sans affichage :

```powershell
docker compose -p neosys-pharma-dev --env-file .env.docker.example run --rm --no-deps app python -m neosys_pharma.infrastructure.bootstrap
```

Ouvrir http://127.0.0.1:8001 et saisir l'UUID d'organisation affiché par le bootstrap,
l'identifiant choisi et le mot de passe. Ne pas transmettre ce mot de passe dans
le chat. Ne jamais réexécuter le bootstrap pour une mise à jour de code.
