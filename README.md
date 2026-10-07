# NeoSys Pharma V1

FastAPI / Python 3.14 / PostgreSQL / SQLAlchemy / Alembic.

## P1 : premier incrément vertical

L'écran `/` permet de créer une organisation avec son premier site et son
premier emplacement, puis d'ajouter des sites et des emplacements. Chaque
création de structure est atomique. Les entités Organisation et Site du commit
45ebdbb sont conservées. Les API sont documentées dans `/docs`.

Installation : `python -m pip install -e '.[dev]'`.
Configurer `DATABASE_URL` dans un `.env` local à partir de `.env.example`.
Sur la base de **développement uniquement**, appliquer `alembic upgrade head`,
puis lancer `uvicorn neosys_pharma.presentation.app:app --host 127.0.0.1 --port 8000`.
Les migrations ne sont jamais exécutées automatiquement au démarrage.

Cet incrément ne comporte pas encore d'authentification : utilisation locale
de développement uniquement. Ne pas déployer en démonstration/production ni
exposer sur le réseau avant l'intégration Utilisateur / rôles / permissions.

## Validation

`pytest -q` : domaine, parcours API, persistance, unicité, validation,
rollback et migrations (upgrade/check/downgrade/upgrade sur base jetable).
Par défaut les nouveaux tests utilisent SQLite, clés étrangères activées.
La CI exécute également ces tests sur un PostgreSQL 17 jetable.
Les variables `TEST_DATABASE_URL` et `TEST_MIGRATION_DATABASE_URL` sont
réservées à des bases **jetables** : les tests suppriment leurs tables.

## Architecture et suite

Voir [docs/P1.md](docs/P1.md). Prochain incrément : PosteVente, Caisse et Coffre,
puis Utilisateur, AffectationSite, AffectationEmplacement, Role et Permission.
