# Verrous Linux CPython 3.14 / x86_64

Résolution réelle avec uv 0.9.5 depuis PyPI, sans conteneur ni installation
applicative. runtime.lock contient 39 paquets ; tests.lock en contient 48.
Chaque paquet est épinglé et dispose de SHA-256. Le verrou tests contraint les
versions communes au verrou runtime. Les wheels sont exigées, sans compilation
implicite de dépendances. Les empreintes peuvent couvrir plusieurs distributions
publiées d'un même paquet ; la cible de résolution reste Linux x86_64/Python 3.14.

Commandes de reproduction avec l'outil épinglé dans lock-tools.txt :

```powershell
uv pip compile pyproject.toml requirements/build.in --python-version 3.14 --python-platform x86_64-unknown-linux-gnu --generate-hashes --only-binary :all: --no-managed-python --output-file requirements/runtime.lock
uv pip compile pyproject.toml requirements/build.in --extra dev --constraint requirements/runtime.lock --python-version 3.14 --python-platform x86_64-unknown-linux-gnu --generate-hashes --only-binary :all: --no-managed-python --output-file requirements/tests.lock
```

build.in ajoute setuptools et tzdata pour le packaging et ZoneInfo. Les commandes
ci-dessus sans contrainte temporelle servent aux mises à jour : elles peuvent
sélectionner de nouvelles versions. Pour reproduire l'installation, consommer les
verrous versionnés avec --require-hashes, comme dans le Dockerfile.

La résolution et les vérifications d'artefacts ne prouvent pas que l'installation,
le build du projet ou les tests passent : ils seront vérifiés en Phase 2 autorisée.
Le Python Windows local est 3.15 ; aucune exécution Python Linux n'a eu lieu.
