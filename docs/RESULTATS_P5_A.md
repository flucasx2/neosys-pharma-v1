# NeoSys Pharma V1 — Rapport de livraison P5-A

## Synthèse

P5-A ajoute les fondations locales du référentiel des tiers payants sur la branche `feat/p5-a-tiers-payants`, issue du `main` observé au SHA `2910cc60e8c8287a587ce8ff8e3f48c95be1ba39`. Les organismes génériques et associations clients P4-B sont réutilisés. Aucune règle P4 de vente, stock, caisse, remboursement ou fidélité n'a été changée.

**État : prêt pour revue locale, pas encore validé PostgreSQL natif. P5-B ne doit pas commencer avant cette validation et l'arbitrage des décisions ouvertes ci-dessous.**

## Matrice des écarts

| Domaine | État avant P5-A | Réutilisé / ajouté | Reporté |
|---|---|---|---|
| Organismes payeurs | P4-B fournit `organismes_prise_en_charge` et `clients_organismes_prise_en_charge` | Tables réutilisées sans copie; FK organisationnelles P5-A | Aucun nouveau catalogue d'organismes |
| Conventions | Absent | Versions datées, statut, référence, conditions déclaratives immuables | Interprétation des plafonds, exclusions et barèmes (P5-B) |
| Bénéficiaire / titulaire | Le client P4-B ne modélise pas ces rôles de couverture | Bénéficiaire distinct du client; titulaire séparé; plusieurs bénéficiaires par adhésion; adhésion avec droits, dates, référence et révision | Vérification en ligne auprès d'un tiers |
| Priorités | P4-B décrit le rôle du client lié à un organisme, pas l'ordre contractuel | Paramétrage versionné à portée organisation, rangs ordonnés, principal optionnel unique au rang 1, secondaires | Surcharge par site et application aux calculs de vente |
| Permissions / audit | P4-B permissions clients et système de rôles existants | Cinq permissions dédiées, aucun octroi par défaut, événements sensibles append-only | Écran d'administration |
| Calcul et historique de prise en charge | Non implémenté | Aucun calcul ajouté | Répartition, arrondis, plafonds, exclusions, parts, créances, snapshots de vente (P5-B/P5-C) |

## Modèle logique

Le diagramme détaillé et les contraintes métier sont dans [P5_A_TIERS_PAYANTS.md](P5_A_TIERS_PAYANTS.md). Les entités introduites sont `ConventionOrganisme`, `BeneficiaireCouverture`, `AdhesionOrganisme`, `AdhesionBeneficiaire`, `ParametragePrioriteTiersPayant`, `PrioriteOrganisme` et `EvenementTiersPayant`.

Les liens composites incluent `organisation_id` pour empêcher les références croisées entre organisations. Les conditions conventionnelles restent des données déclaratives JSON; aucun moteur ne les interprète.

## Migration

- Nouvelle révision : `20261017_01`, dépendance directe `20261015_02`.
- Migration additive : sept tables, clés étrangères organisationnelles, index, contraintes `CHECK`/`UNIQUE`, permissions dédiées et protections append-only.
- Le downgrade retire les tables et permissions P5-A. Il ne doit être utilisé que dans une base jetable ou après archivage explicite des données P5-A.
- Aucune migration n'a été appliquée à PostgreSQL, aux bases réelles, de démonstration ou de recette.

## Vérifications exécutées

Environnement : Python 3.14.8, tests sur SQLite temporaire uniquement.

Commande ciblée :

```text
python -m pytest -q tests/test_p5a_tiers_payants.py tests/test_clients_p4b.py tests/test_encaissement_groupe_domain.py tests/test_encaissement_groupe_persistance.py
18 passed, 2 skipped, 3 subtests passed
```

Les tests couvrent les créations et consultations, adhésion multibénéficiaire, actualisation des droits avec contrôle de révision, ordres principal/secondaires, versions de priorités et audit, permissions, validation des périodes, vérification des FK composites et des contraintes de priorité par inspection du schéma SQLite, et migration aller-retour avec conservation d'un organisme P4-B fictif. Les tests de domaine/persistance P4-C ciblés ont également passé.

Les deux tests ignorés sont gardés par les protections existantes et nécessitent des bases PostgreSQL jetables dédiées : migration P4-B (`neosys_p4b_migration`) et migration P4-C (`neosys_p4c_migration`). Aucun test PostgreSQL natif n'a été exécuté. Chromium n'a pas été exécuté : aucune interface graphique n'est incluse dans P5-A.

Contrôles statiques exécutés : `compileall`, `git diff --check`, `alembic heads` et revue de la filiation Alembic. Une seule tête est présente, `20261017_01`.

Un test de migration P4-C contenait une attente fixe sur l'ancien head `20261015_02`; elle a été remplacée par une assertion sur le head Alembic courant afin que le test P4 vérifie toujours l'état migré complet.

## Fichiers P5-A

- `src/neosys_pharma/domain/tiers_payants.py`
- `src/neosys_pharma/infrastructure/tiers_payants_models.py`
- `src/neosys_pharma/application/tiers_payants_service.py`
- `src/neosys_pharma/presentation/tiers_payants_api.py`
- `migrations/versions/20261017_01_p5a_tiers_payants.py`
- `tests/test_p5a_tiers_payants.py`
- `docs/P5_A_TIERS_PAYANTS.md`

Fichiers d'intégration modifiés : `migrations/env.py`, `src/neosys_pharma/domain/organisation/permissions_systeme.py`, `src/neosys_pharma/presentation/app.py`. Régression de test P4-C ajustée : `tests/test_encaissement_groupe_persistance.py`.

## Décisions confirmées et risques résiduels

1. Confirmé : l'organisme principal est facultatif; plusieurs secondaires peuvent être ordonnés seuls. S'il existe, le principal est au rang 1. Confirmé également : le paramétrage V1 est commun à l'organisation et n'a pas de surcharge par site. Le modèle P5-A suit ces décisions.
2. Le contenu `conditions` / `extensions_p5b` n'a pas de schéma métier détaillé et ne doit pas être utilisé pour calculer une vente avant P5-B.
3. La compatibilité PostgreSQL native des contraintes, triggers et migration doit être exécutée sur une base explicitement jetable avant de considérer le lot prêt à alimenter P5-B.
4. Il n'existe pas d'interface d'administration P5-A. Les bénéficiaires sont créés et listés; les adhésions peuvent être créées, consultées et actualisées avec contrôle de révision. Les conventions et priorités sont créées sous forme de versions.

## Verdict

**P5-A est implémenté et ses contrôles ciblés SQLite passent. Pas encore GO pour P5-B** : exécuter la migration et les contraintes sur PostgreSQL natif jetable. Aucune publication GitHub n'est incluse.
