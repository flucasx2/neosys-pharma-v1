# B03 — Proposition de recette humaine jetable

Clôture : recette humaine A1/A2 et corrections A1/A2/A3 validées par le
propriétaire. Les indications de recette « à effectuer » plus bas décrivent la
procédure suivie ; elles restent disponibles pour reproduction après autorisation.
L'environnement et ses données temporaires sont conservés, sans nettoyage.
La suite automatisée PostgreSQL native (concurrence/verrouillage) n'a pas été
exécutée. L'amélioration rédactionnelle du libellé F10 est reportée, sans changement
de comportement dans B03 ; voir `docs/RAPPORT_B03.md`.

Statut : **environnement préparé après autorisation explicite du propriétaire**.
Les commandes proposées plus bas sont conservées pour traçabilité ; ne pas les
rejouer sur cet environnement déjà initialisé. Aucun nettoyage autorisé/exécuté.
Checkout : `D:\Projets_Python\NeoSys_Pharma_Dev`, branche `dev/codex-docker`,
HEAD `05478570a713f635029f570b3f7bf9bed0cdf200`, corrections B03 non commitées.

## Résultat réel de la préparation du 21 octobre 2026

- Deux conteneurs actifs : `neosys-pharma-b03-recette-app-1` (`1ae8ef53bf39`),
  `neosys-pharma-b03-recette-test-db-1` (`a4082410121d`, healthy).
  App n'a pas de healthcheck Docker dans la procédure : son fonctionnement est
  contrôlé directement par HTTP.
- `http://127.0.0.1:8003/` : HTTP 200 et formulaire de connexion ; `/health` : `ok`.
- Base réelle vérifiée avant migration : `neosys_docker_test`, utilisateur
  `neosys_test`, hôte `test-db`, adresse `172.21.0.2` sur le réseau B03 interne.
  Schéma public initialement vide. Le contrôle d'adresse initial a refusé le
  suffixe PostgreSQL `/32` ; comparaison normalisée avec `host(inet_server_addr())`
  puis revalidation avant toute migration. Aucun changement de destination.
- `alembic upgrade head` réussi : révision `20261019_06`, égale à la tête du
  checkout. `migrations/env.py` utilise les Settings alimentés par l'entrypoint
  inchangé du rôle tests, avec cible vérifiée vers le nouveau serveur B03.
- Les trois seeds prévus ont réussi, chacun une seule fois. Contrôle SQL final
  en lecture seule : **1 organisation, 5 ventes transmises, 0 fournisseur,
  0 confirmation, 0 encaissement**. Aucun paiement effectué ni test financier lancé.
- Organisation synthétique : `50c91609-c3be-46c1-a94c-4c0d01ae130d`.
  Compte de recette : `caisse.qa`. Caisse : `Caisse P4`.
  Vente fictive utilisable : `178a0a19-7638-48df-83f9-8c931ad2853b`.
- Connexion remise dans `.secrets/b03-connexion.txt` uniquement, avec URL,
  organisation, compte et mot de passe **synthétique** du seed. Aucun mot de passe
  affiché dans le chat ou les logs ; fichier ignoré par Git, ACL limitée au compte
  Windows courant et SYSTEM. La saisie interactive de remplacement décrite dans
  la proposition n'a pas été nécessaire. La copie Docker depuis tmpfs a échoué
  sans effet sur la base ; transfert par sortie directement redirigée vers ce
  fichier privé, sans affichage. Ne pas joindre ce fichier au rapport ou à Git.
- Projet principal inchangé : `neosys-pharma-dev-app-1` (`1d05b1290dae`) et
  `neosys-pharma-dev-db-1` (`a334ec625935`) toujours healthy, mêmes identifiants
  qu'avant préparation ; aucune commande de cycle de vie ou SQL ne les a ciblés.
- Aucun volume de données créé/monté ; PostgreSQL est en tmpfs. Aucun port
  PostgreSQL publié. Réseaux B03 distincts des réseaux principaux. Secret B03
  distinct, aucun secret de développement fourni à la recette. Le modèle Compose
  et les environnements réels ont été vérifiés sans URL héritée/variable PG de
  redirection ni flag d'activation CI/P4/P5.

Ouvrir le fichier d'accès local, puis suivre la recette courte ci-dessous dans
une fenêtre privée dédiée au port 8003. **Ne pas arrêter/recréer PostgreSQL B03** :
son tmpfs serait perdu. Aucun nettoyage n'est programmé. Le serveur Uvicorn a
été démarré explicitement après les seeds ; il reste actif dans app.

Cette préparation confirme la migration et les données synthétiques sur le
PostgreSQL B03 ; elle ne remplace pas une validation de concurrence native ou
la recette humaine A1/A2, qui reste à effectuer par le propriétaire.

## Inspection et choix

Le Compose actuel fournit `test-db` sur tmpfs et le rôle Docker `tests` cible
exclusivement `test-db:5432/neosys_docker_test`, compte `neosys_test`.
Les seeds navigateur existants fournissent organisation, droits, produit, stock,
caisse et cinq ventes transmises. Uvicorn sert l'interface réelle.
`ci/browser.py` n'est pas lancé : il migre automatiquement et exécute d'autres
parcours. Le Compose de développement n'est ni fusionné ni modifié : même avec
un autre nom de projet, il référence explicitement le volume persistant existant.

Ressources observées en lecture seule : app actuelle sur `127.0.0.1:8001`, db
actuelle sans port PostgreSQL publié ; image de tests `02920248d821` disponible.
Aucun listener 8003 trouvé lors de l'inspection. Disponibilité et absence de noms
en collision à revérifier avant exécution ; en cas de collision, arrêt sans suppression.

## Destination exacte proposée

| Ressource | Destination / effet |
|---|---|
| Projet Compose | `neosys-pharma-b03-recette` |
| Conteneurs nouveaux | `neosys-pharma-b03-recette-test-db-1`, `neosys-pharma-b03-recette-app-1` |
| PostgreSQL jetable | Hôte Docker `test-db`, port interne 5432, base `neosys_docker_test`, compte `neosys_test` ; autre serveur que la base persistante |
| Données PostgreSQL | tmpfs `/var/lib/postgresql`, perdues à l'arrêt du conteneur ; aucun volume nommé/anonyme de données |
| Réseaux nouveaux | `neosys-pharma-b03-recette_testing` interne ; `neosys-pharma-b03-recette_frontend` pour publication HTTP de app |
| Navigateur | `http://127.0.0.1:8003/` ; port PostgreSQL non publié |
| Fichier Compose proposé | `D:\Projets_Python\NeoSys_Pharma_Dev\compose.b03-recette.yaml` |
| Secret neuf | `.secrets/b03-test-db-password.txt`, non suivi, distinct des secrets existants, jamais affiché ; monté sous le nom attendu `test_db_password` |
| Données synthétiques | Organisation navigateur neuve, comptes QA, stock fictif et ventes issues des seeds existants ; aucun fournisseur MOBILE MONEY initial |
| Fixture privée | `/tmp/p1-browser-fixture.json` dans app, tmpfs, jamais affichée/copîée : contient un mot de passe synthétique |

App utilise l'image de tests existante, le rôle **tests** et son entrypoint
inchangé. Elle ne reçoit aucun secret de développement. Ses sources, tests,
migrations et configuration Alembic sont montés seuls en lecture seule, jamais
le checkout entier ni `.env`. Aucun flag CI/P4/P5 n'est activé. Aucun pytest n'est lancé.

## Configuration proposée, non créée

Contenu exact envisagé pour `compose.b03-recette.yaml` :

```yaml
name: neosys-pharma-b03-recette
services:
  test-db:
    image: postgres:18@sha256:885953109528ad3dfc90362b1a6f50a78620b5315be19f187753d267e484dc5b
    platform: linux/amd64
    environment:
      POSTGRES_USER: neosys_test
      POSTGRES_DB: neosys_docker_test
      POSTGRES_PASSWORD_FILE: /run/secrets/test_db_password
    secrets: [test_db_password]
    tmpfs: [/var/lib/postgresql]
    networks: [testing]
    healthcheck:
      test: [CMD-SHELL, "pg_isready -U neosys_test -d neosys_docker_test"]
      interval: 5s
      timeout: 5s
      retries: 12
  app:
    image: neosys-pharma-dev-tests:latest
    platform: linux/amd64
    environment:
      NEOSYS_DOCKER_ROLE: tests
      ENVIRONMENT: b03-recette-jetable
      AUTH_COOKIE_SECURE: "false"
      PYTHONPATH: /opt/neosys/src
      POSTGRES_PASSWORD_FILE: /run/secrets/test_db_password
    secrets: [test_db_password]
    command: [python, -c, "import time; time.sleep(2147483647)"]
    read_only: true
    tmpfs: [/tmp]
    volumes:
      - ./src:/opt/neosys/src:ro
      - ./tests:/opt/neosys/tests:ro
      - ./migrations:/opt/neosys/migrations:ro
      - ./alembic.ini:/opt/neosys/alembic.ini:ro
    ports: ["127.0.0.1:8003:8000"]
    networks: [frontend, testing]
    depends_on:
      test-db:
        condition: service_healthy
    init: true
networks:
  frontend:
  testing:
    internal: true
secrets:
  test_db_password:
    file: ./.secrets/b03-test-db-password.txt
```

## Commandes proposées après autorisation seulement

PowerShell, exclusivement depuis le checkout. Création du secret neuf sans
écrasement ni affichage, puis écriture du fichier Compose présenté ci-dessus.
Ne pas reprendre une ressource préexistante portant ces noms.

```powershell
$b03Secret = Join-Path (Get-Location) '.secrets/b03-test-db-password.txt'
if (Test-Path -LiteralPath $b03Secret) { throw 'Secret B03 déjà présent : arrêter et vérifier.' }
[IO.Directory]::CreateDirectory((Split-Path -Parent $b03Secret)) | Out-Null
$b03Bytes = [byte[]]::new(32)
[Security.Cryptography.RandomNumberGenerator]::Fill($b03Bytes)
[IO.File]::WriteAllText($b03Secret, [Convert]::ToBase64String($b03Bytes))
Remove-Variable b03Bytes
$b03Compose = @('-p','neosys-pharma-b03-recette','--env-file','.env.docker.example','-f','compose.b03-recette.yaml')
docker compose @b03Compose config --quiet
docker compose @b03Compose up -d --no-build --pull never test-db app
docker compose @b03Compose exec -T app python docker/entrypoint.py check-target
```

Effets : création de deux conteneurs, deux réseaux et d'une base PostgreSQL neuve
en mémoire par l'image PostgreSQL. App attend, sans migration ni bootstrap au démarrage.
Pas de reconstruction/pull ni de changement des conteneurs de développement.
Vérifier chaque code de sortie avant la commande suivante.

Avant toute écriture de schéma, contrôle SQL strict de la cible et de sa vacuité :

```powershell
docker compose @b03Compose exec -T app python docker/entrypoint.py python -c "from neosys_pharma.infrastructure.database import engine; from sqlalchemy import text,inspect; c=engine.connect(); assert (c.execute(text('select current_database(), current_user')).one()) == ('neosys_docker_test','neosys_test'); assert not inspect(c).get_table_names(schema='public'); print('Cible B03 neuve verifiee'); c.close()"
docker compose @b03Compose exec -T app python docker/entrypoint.py alembic upgrade head
docker compose @b03Compose exec -T app python docker/entrypoint.py python tests/seed_browser.py
docker compose @b03Compose exec -T app python docker/entrypoint.py python tests/seed_browser_p4.py
docker compose @b03Compose exec -T app python docker/entrypoint.py python tests/seed_browser_caisse.py
```

Effets : migrations uniquement de cette base neuve, puis bootstrap synthétique
et données caisse explicitement autorisés par la présente procédure. Les trois
seeds s'exécutent une seule fois, dans le même conteneur conservant `/tmp`.
Les autres seeds/parcours navigateur ne sont pas exécutés. Aucun secret affiché.

L'utilisateur choisit ensuite lui-même un mot de passe neuf pour `caisse.qa`
dans son terminal interactif, sans le transmettre au chat. La commande suivante
ne lit pas le mot de passe de la fixture ; elle n'affiche que l'UUID d'organisation.

```powershell
docker compose @b03Compose exec app python docker/entrypoint.py python -c "from getpass import getpass; from sqlalchemy import select; from neosys_pharma.infrastructure.database import SessionLocal; from neosys_pharma.infrastructure.securite_models import UtilisateurModel; from neosys_pharma.infrastructure.authentification_repository import SqlAlchemyAuthRepository; from neosys_pharma.infrastructure.passwords import passwords; s=SessionLocal(); u=s.scalar(select(UtilisateurModel).where(UtilisateurModel.identifiant=='caisse.qa')); p=getpass('Mot de passe jetable caisse.qa : '); assert p==getpass('Confirmation : '); SqlAlchemyAuthRepository(s).definir_password(u.id_utilisateur,passwords.hacher(p)); s.commit(); print('Organisation :',u.organisation_id); s.close()"
docker compose @b03Compose exec -d app python docker/entrypoint.py python -m uvicorn neosys_pharma.presentation.app:app --host 0.0.0.0 --port 8000
```

Effet : serveur HTTP réel démarré après préparation explicite ; connexion humaine
avec l'UUID affiché, `caisse.qa` et le mot de passe saisi. Aucun contournement des
permissions HTTP ; les droits du compte sont ceux du seed existant.

## Recette visuelle courte

Ouvrir `http://127.0.0.1:8003/` dans une fenêtre privée dédiée (éviter les cookies
de l'application sur 8001), se connecter, aller à Encaissement & Fidélité, ouvrir
une session sur Caisse P4 et sélectionner une vente transmise fictive.
Ne finaliser aucun encaissement : cette recette vérifie la disponibilité des formulaires.

1. **MOBILE MONEY seule, sans fournisseur** : administration des moyens, familles
   MOBILE MONEY active, toutes les autres inactives. Confirmer les désactivations.
   Actualiser F12 et réouvrir les actions. « Confirmation indépendante » doit
   annoncer l'absence de moyen non espèces actif, sans option générique ; le nouvel
   encaissement annonce l'absence de moyen actif.
2. **ESPÈCES inactive avec MOBILE MONEY utilisable** : créer explicitement
   `MM_B03` / `Mobile Money B03`, famille MOBILE MONEY, actif. Actualiser. La
   confirmation propose ce fournisseur ; le formulaire d'encaissement ne présente
   pas de champ espèces. Fermer les formulaires sans enregistrer de confirmation.
3. **Aucun moyen actif** : désactiver aussi MOBILE MONEY avec confirmation.
   Actualiser : message explicite à l'encaissement et aucune nouvelle confirmation
   possible ; ne pas confondre conservation de fournisseur et famille active.
4. **ESPÈCES + fournisseur actif** : réactiver les deux familles, conserver MM_B03
   actif, actualiser. Le champ espèces réapparaît à l'encaissement ; la confirmation
   non espèces propose Mobile Money B03. Ce sont deux parcours distincts existants,
   pas un nouveau sélecteur unique : les espèces n'exigent pas de confirmation externe.

## Fin de recette proposée, à autoriser également

```powershell
docker compose @b03Compose down
```

Supprime uniquement les deux conteneurs et les deux réseaux du projet B03 ; détruit
les données tmpfs de recette. Aucun `-v`, aucune commande volume, aucun impact sur
le projet `neosys-pharma-dev`. Aucun arrêt/nettoyage ne sera exécuté sans accord.
Le secret local et le fichier Compose restent sur disque ; leur éventuelle
suppression sera proposée séparément, sans lecture du secret.

La recette humaine et les tests financiers n'ont pas été exécutés pendant cette
préparation. Aucune donnée de l'organisation conservée n'a été consultée ou modifiée.
