# P5-CONF.1a — Administration autonome des organismes

## Base vérifiée et portée

Le bundle fourni contient l'historique complet et la branche `feat/p5-administration-tiers-payants` au commit exact `5ad489ccb2ccac4c511cda9b1a87104245ddab28`. Copie isolée : `neosys-p5-conf-work`. Le poste Windows n'est pas accessible et n'a pas été modifié. Les quatre fichiers non suivis visibles sur la capture restent hors bundle et sont à préserver : archive d'inspection, deux patches P5-B et script de connexion locale.

Ce premier sous-lot livre NC-P5-01 au niveau code/API/DOM : Administration → Organismes de prise en charge, liste paginée, recherche code/nom, filtre actif/inactif, création, consultation, modification avec révision et activation/désactivation. Aucune fiche client ni adhésion fidélité n'est nécessaire. Aucun écran incomplet de convention ou de vérification n'est présenté comme opérationnel.

## Réutilisation et garanties

- Modèle P4-B `OrganismePriseEnChargeModel`, même table et mêmes identifiants. Pas de duplication de référentiel.
- Service `TiersPayantsService`, journal append-only `tiers_payant_evenements`, transaction/idempotence `StockService.operation`, verrou d'organisation existant et contraintes d'unicité réutilisés.
- Consultation avec `tiers_payant.consulter` ou `tiers_payant.organisme.gerer`. Mutation avec la nouvelle permission `tiers_payant.organisme.gerer`. Aucune affectation à un rôle n'est ajoutée automatiquement.
- Organisation/site/emplacement et CSRF contrôlés par les dépendances existantes. Les organismes sont communs à l'organisation; le site reste un contexte d'autorisation, pas une surcharge du référentiel.
- PUT exige la révision et un booléen strict. Clé identique/contenu identique restitue le résultat, contenu différent ou révision périmée produit un conflit. Audit auteur/avant/après dans la même transaction.
- Pas de suppression d'organisme. Les conventions historiques ne sont pas réécrites lors du renommage/de la désactivation. Les règles P5-A existantes refusent une nouvelle convention pour un organisme inactif.
- Le parcours historique `/api/clients/.../organismes` et ses permissions sont conservés pour compatibilité. La nouvelle administration ne dépend pas de cette route. Les nouvelles créations y sont immédiatement disponibles pour association client lorsqu'elles sont actives.
- Interface : libellés métier, navigation/clavier natifs, erreurs visibles, double clic bloqué, même clé conservée après une erreur réseau pour la même saisie, protection contre les réponses tardives d'un autre contexte et révocation des droits reflétée immédiatement.

## Migration additive

`20261018_01_p5_conf_organismes.py`, parent `20261017_03` : ajoute uniquement la permission d'administration autonome. Pas de changement aux colonnes ou données financières. Le downgrade refuse de retirer une permission encore liée à un rôle; les affectations doivent être retirées explicitement au préalable. La révision préparatoire `20261017_04` n'est pas intégrée. Un futur lot de configuration devra se rebaser sur la nouvelle tête Alembic, sans créer deux têtes ni appliquer le patch préparatoire tel quel.

## Examen du patch préparatoire

Le patch fourni a été inspecté sans application. `git apply --check --cached` sur l'index du commit de départ échoue sur trois fichiers modifiés. La normalisation LF d'une copie temporaire du patch permet le même contrôle : compatibilité textuelle confirmée après correction des fins de ligne, pas validation fonctionnelle.

Éléments réutilisables pour une prochaine tranche : configuration versionnée, mode LISTE/EXTERNE/MIXTE, structure de champs/justificatifs, FK organisationnelles, audit et journal d'idempotence existant. Points restant à traiter :

1. Aucun raccordement du formulaire et de sa version aux réponses de vérification, au snapshot de vente ou à P5-C. La configuration seule ne prouve aucun droit.
2. Pas d'import Excel/CSV ni de validation des valeurs d'un bénéficiaire. Les types/obligations ne couvrent pas encore les contrôles de format demandés.
3. Le test de migration préparatoire crée des tables minimales en mémoire; il ne valide pas la chaîne Alembic complète ni PostgreSQL natif. Il n'active pas explicitement les FK SQLite.
4. Les modèles d'entrée utilisent `bool` non strict; la validation du domaine après coercition ne suffit pas à rejeter tous les booléens textuels. Tester à la frontière HTTP.
5. Une nouvelle version peut commencer le jour courant : il faut vérifier son effet sur les opérations déjà commencées dans la journée et figer la version choisie dans leur snapshot. Ne pas déduire une politique rétroactive.
6. Les champs inconnus au niveau racine du validateur de domaine ne sont pas explicitement rejetés (la couche Pydantic les rejette). Conserver un contrat explicite pour tous les appels, y compris hors HTTP.

Le patch est donc **différé**, sans importer de fonctionnalités partiellement raccordées dans ce sous-lot.

## Tests réellement exécutés

Python 3.14.8. SQLite en mémoire ou fichiers `tmp_path` propres aux tests; aucune base conservée et aucune URL PostgreSQL utilisée.

```sh
TZ=Africa/Libreville PYTHONPATH=src:tests:<site-packages-3.14> python3.14 -m pytest -q \
 tests/test_p5_conf_organismes.py tests/test_clients_p4b.py \
 tests/test_p5a_tiers_payants.py tests/test_p5b_2_integration_vente.py \
 tests/test_p5b_3_encaissement_prise_en_charge.py
```

Résultat final : **24 passed, 1 skipped, 1 warning**, 15,09 s. Le test ignoré est la migration PostgreSQL P4-B exigeant sa base jetable dédiée. L'avertissement concerne la dépréciation httpx/Starlette. Le cycle Alembic nouvellement ajouté exécute upgrade `20261017_03` → `20261018_01`, `alembic check`, conservation d'un organisme fictif, absence de droit attribué, downgrade et upgrade.

Tests nouveaux : 10 cas pytest (dont 5 entrées invalides paramétrées), couvrant CRUD, révision, idempotence, unicité, audit, absence de client, compatibilité P4-B, conservation convention, refus d'accès anonyme/lecture seule/autre organisation/site/emplacement, CSRF, booléen strict et migration.

```sh
NODE_PATH=<installation-jsdom>/node_modules node tests/organismes_ui.cjs
```

**20 assertions DOM réussies**, HTML et JavaScript réels, réponses HTTP simulées. Ces assertions ne prouvent pas une recette de bout en bout. `node --check` et `git diff --check` réussis.

`node tests/organismes_ui.cjs --chromium` : **bloqué avant les scénarios**, exécutable Playwright Chromium absent. Le même scénario est prêt à être exécuté avec un navigateur installé. Aucun test Chromium réussi n'est annoncé.

PostgreSQL natif : **non exécuté**; aucun psql/postgres/Docker accessible. Les tests SQLite ne prouvent pas les courses natives. La migration additive et les éditions concurrentes devront être validées sur une base exclusivement jetable.

## Échecs rencontrés et traitement

- Trois refus 403 initiaux : les fixtures utilisent la date du système (Europe/Berlin, déjà le 19), le serveur la date de Libreville (encore le 18). Runner relancé avec `TZ=Africa/Libreville`; aucune règle d'autorisation modifiée.
- Comparaison test POST/GET de convention : SQLite restitue un datetime sans fuseau après relecture. Le test compare désormais la représentation persistée GET avant et après édition, en entier; la conservation n'est pas affaiblie.
- Le cycle historique P5-A attendait cinq permissions après `upgrade head`. Assertion adaptée à six (cinq historiques + nouvelle permission), avec test distinct de non-attribution. Aucune migration historique réécrite.
- Revue UI : les champs sont désormais désactivés immédiatement si le droit de gestion est révoqué tout en conservant la lecture; assertion DOM ajoutée.

## Sources documentaires et limites

Référentiel fourni du 18/10/2026, section P5, addendum P5-FAC-01 et écran B. Les sections anciennes mentionnent encore une portée organisation/site à arbitrer; la décision confirmée dans cette conversation prévaut : priorités communes à l'organisation, principale facultative. Aucun calcul financier changé.

Les documents de continuité disponibles ont été repris dans le dépôt, avec ajout daté. `JOURNAL_DEVELOPPEMENT(1).md` contenait uniquement « A completer. » : aucun journal antérieur détaillé n'a été reconstitué. Les résultats Windows mentionnés dans le dossier de reprise restent des résultats rapportés, pas des exécutions de cette intervention.

**Livraison locale du sous-lot P5-CONF.1a, prête pour revue; P5-CONF.1 complet et recette humaine non validés.** Configuration des régimes/conventions/barèmes dans l'interface, contrôles externes et documents requis dans la vente restent à développer. P5-C n'est pas commencé; le parcours groupé n'est pas activé. Aucun push, PR, fusion ou déploiement.

## Fichiers livrés

- `src/neosys_pharma/application/tiers_payants_service.py`
- `src/neosys_pharma/domain/organisation/permissions_systeme.py`
- `src/neosys_pharma/domain/tiers_payants.py`
- `src/neosys_pharma/presentation/tiers_payants_api.py`
- `src/neosys_pharma/presentation/web/index.html`
- `src/neosys_pharma/presentation/web/shell.js`
- `src/neosys_pharma/presentation/web/organismes.js`
- `migrations/versions/20261018_01_p5_conf_organismes.py`
- `tests/test_p5_conf_organismes.py`
- `tests/test_p5a_tiers_payants.py`
- `tests/organismes_ui.cjs`
- `docs/RESULTATS_P5_CONF_1A.md`
- `docs/RECETTE_P5_CONF_1A.md`
- `docs/REGISTRE_NON_CONFORMITES_P5.md`
- `JOURNAL_DEVELOPPEMENT.md`
- `REPRISE_NEOSYS_PHARMA.md`

Environnement JavaScript observé : Node 24.19.0, jsdom 30.1.3 et Playwright 1.62.1 (bibliothèque disponible, navigateur absent). Les dépendances de contrôle sont installées hors dépôt; aucun verrou de dépendances applicatives modifié.
