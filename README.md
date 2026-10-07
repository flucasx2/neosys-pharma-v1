# NeoSys Pharma V1

FastAPI / Python 3.14 / PostgreSQL / SQLAlchemy / Alembic.

## P1 : premier incrément vertical

L'écran `/` propose la connexion, puis un tableau de bord et un shell avec sidebar.
Le module Administration comporte cinq vues pour la structure, les équipements,
les utilisateurs, les affectations et les rôles/permissions autorisés. Organisation, Site et Emplacement
restent indépendants ; leur création atomique demeure un cas d'usage applicatif.
Une installation vide s'initialise avec `python -m neosys_pharma.infrastructure.bootstrap`,
après migration, avec ses affectations explicites. Le provisionnement local
d'une structure existante reste disponible. L'onboarding HTTP de nouvelles organisations est
réservé à P0. Les entités du commit 45ebdbb sont conservées et les API sont
documentées dans `/docs`.

Installation : `python -m pip install -e '.[dev]'`.
Configurer `DATABASE_URL` dans un `.env` local à partir de `.env.example`.
Sur la base de **développement uniquement**, appliquer `alembic upgrade head`,
puis initialiser une **base vide** avec
`python -m neosys_pharma.infrastructure.bootstrap` et lancer `uvicorn neosys_pharma.presentation.app:app --host 127.0.0.1 --port 8000`.
Les migrations ne sont jamais exécutées automatiquement au démarrage.

Connexion HTTP et contrôle d'accès sont intégrés. Provisionner le premier compte
local avec le bootstrap interactif ; conserver l'UUID d'organisation affiché
pour la connexion. Voir [la procédure exacte](docs/P1.md#base-postgresql-de-développement-vide--première-connexion). Pour HTTP loopback
uniquement : AUTH_COOKIE_SECURE=false ; garder true sous HTTPS. Aucun mot de passe
n'est créé par migration. Aucun déploiement démonstration/production n'est effectué.

## Validation

`pytest -q` : domaine, parcours API, persistance, unicité, validation,
rollback et migrations (upgrade/check/downgrade/upgrade sur base jetable).
Par défaut les nouveaux tests utilisent SQLite, clés étrangères activées.
La CI exécute également ces tests sur un PostgreSQL 17 jetable.
Les variables `TEST_DATABASE_URL` et `TEST_MIGRATION_DATABASE_URL` sont
réservées à des bases **jetables** : les tests suppriment leurs tables.

## Architecture et suite

Voir [docs/P1.md](docs/P1.md). Organisation/Site/Emplacement restent des entités
indépendantes ; le parcours de création atomique relève de l'application.
P1 inclut maintenant l’authentification, les sessions révocables et le contrôle des
droits sur les API et l’interface.

L'incrément P1 comprend aussi les utilisateurs, leurs affectations à plusieurs
sites, les emplacements autorisés, les rôles système/personnalisés et l'aperçu des
permissions résultantes. Appliquer `alembic upgrade head` dans une base de
**développement** avant de lancer l'interface. Les règles et limites actuelles
(notamment le provisionnement initial et les exigences d'exploitation) sont décrites dans
[docs/P1.md](docs/P1.md).

## P2 : Catalogue de base (première tranche)

La section **Catalogue** permet de gérer produits, catégories hiérarchiques,
formes pharmaceutiques, laboratoires, conditionnements et références multiples.
Appliquer la migration additive `20261007_05` sur votre base de développement,
puis attribuer **explicitement** `catalogue.consulter` et `catalogue.gerer` par
un rôle et une affectation P1. Aucun rôle existant ne reçoit ces droits par défaut.
Voir [docs/P2.md](docs/P2.md) pour la recette, les routes et le périmètre de revue.
La tarification et les autres classifications P2 ne sont pas encore livrées.
