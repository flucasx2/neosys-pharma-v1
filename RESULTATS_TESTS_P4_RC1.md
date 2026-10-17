# Résultats des contrôles P4 — préparation RC1

## Synthèse

Le travail local est sur `work/p4-rc1-corrections`, basé sur PR #7 `a4b524e5d5956c9d65b02622452e874e11b3ac88`. Les tests Python locaux ont été exécutés avec Python 3.14.8 et `TZ=UTC`. Aucun PostgreSQL natif ni Chromium n'est installé ou accessible; aucune migration n'a été exécutée sur une base partagée ou conservée.

**Décision : NO-GO pour P4-RC1.** Les corrections locales passent les tests SQLite ciblés, mais les tests PostgreSQL natifs et la recette Chromium doivent encore être exécutés.

## Matrice des scénarios

| Contrôle | Résultat | Preuve / motif |
|---|---|---|
| Contrôles CI PR #6 | Réussi historiquement | Run `38271053293` : synthèse CI, SQLite, PostgreSQL et Chromium réussis selon le statut CI consulté. |
| Suite SQLite PR #7 | Réussie historiquement | Run `38689222971` : job `sqlite` réussi. |
| PostgreSQL 17 PR #7 | Échec historique diagnostiqué | Run `38689222971`, job `postgres` : répétitions de `DuplicateFunction` sur `eg32_claim` lorsque l'installateur était invoqué deux fois. |
| PostgreSQL 18 concurrence PR #7 | Échec historique diagnostiqué | Run `38689222971`, job `CI / concurrence PostgreSQL 18 - P4.6` : aucun deuxième backend en attente d'un verrou n'a été observé; le test ne prouvait pas la contention entre connexions indépendantes. |
| Chromium PR #7 | Échec historique; cause non vérifiée | Run `38689222971`, job `browser` : tous les parcours P1, P2, P3, P4.2 et P4.3 consignés comme réussis; `tests/browser_caisse.py:27` n'a pas trouvé « Utiliser cette session ». Le log ne contient pas les réponses HTTP ni l'état de session nécessaires à une cause racine. |
| `compileall` Python | Réussi | `TZ=UTC .venv/bin/python -m compileall -q src tests migrations`. |
| Tests de domaine, persistance, migration et service d'encaissement groupé | Réussi | `TZ=UTC .venv/bin/pytest -q tests/test_encaissement_groupe_domaine.py tests/test_encaissement_groupe_persistance.py tests/test_encaissement_groupe_migration.py tests/test_encaissement_groupe_service.py tests/test_regularisation.py::test_retours_partiels_cumulatifs_quarantaine_remboursement_fidelite tests/test_regularisation.py::test_rollback_remboursement_et_non_contournement tests/test_caisse.py::test_encaissement_mixte_atomique_recu_et_rejeu` : **40 passed**. |
| Migration Alembic complète SQLite | Réussie | Incluse dans les tests ciblés : montée jusqu'à la tête `eg34a2026`, vérification `alembic check`, downgrade à `a46c001d2026`, réapplication jusqu'à `head`, puis nouveau `alembic check`. Base temporaire SQLite du test, aucun fichier conservé. |
| Fidélité avec deux clients distincts | Réussie localement sur SQLite | Incluse dans les 40 tests : comptes distincts associés à deux ventes, ventilation par compte, points calculés par vente et reçus sans compte commun fictif. |
| Retours individuels / remboursement / fidélité | Réussis localement sur SQLite | Tests ciblés de retours partiels cumulatifs, remboursement, rollback du remboursement et encaissement individuel mixte. |
| Contrainte `eg32_claim` répétable sur PostgreSQL | Non exécuté; test ajouté | La vérification unitaire SQL confirme les `CREATE OR REPLACE` et le nettoyage des triggers. Le test runtime PostgreSQL dédié utilise la base temporaire prévue mais attend une CI ou un serveur natif. |
| Migration PostgreSQL `eg33a2026` et `eg34a2026` | Non exécutée | Aucun serveur PostgreSQL natif ni `pg_ctl`/`psql` n'est disponible dans Work. |
| Tests réels de concurrence PostgreSQL | Non exécutés | Les scénarios utilisent désormais deux clients HTTP et exigent un backend PostgreSQL distinct en attente de verrou; ils doivent tourner sur PostgreSQL natif. |
| Retours/remboursements groupés et compensation multi-clients | Non exécutés sur PostgreSQL | Tests préparés dans `tests/test_encaissement_groupe_3_4_postgresql.py`, non lancés car le garde de base jetable exige PostgreSQL. |
| Chromium après instrumentations | Non exécuté localement | Aucun exécutable Chromium disponible. L'installation Playwright précédente a échoué sur une archive navigateur corrompue. Aucune nouvelle CI n'a été déclenchée sans publication autorisée. |
| P4.4 / P4.5 complet, clôtures X/Z et totalité des PDFs historiques | Non relancés | La validation historique PR #6 est conservée; seules les régressions ciblées ci-dessus ont été exécutées. Aucun parcours de vente/préparation n'a été modifié par ces corrections. |

## Détails de diagnostic

- **403 retour** : le contrôle partagé de la route `finance_solde` exige `caisse.remboursement.demander`; le fixture avait seulement `vente.retour.gerer`. Le test ajoute explicitement la permission prévue dans son rôle de recette. Le code d'autorisation et les rôles de production restent inchangés.
- **Concurrence** : le nouveau test conserve l'exécution parallèle et vérifie un état `active / Lock` sur un backend autre que celui de la première transaction. Ce correctif de test ne vaut pas preuve de contention tant que le test n'a pas tourné sur PostgreSQL natif.
- **Chromium** : le test garde l'assertion et récoltera `POST /sessions`, l'utilisateur connecté et `GET /sessions` si le bouton manque. Le diagnostic n'est pas encore exécuté; l'absence du bouton n'est pas corrigée artificiellement.

## Environnement / sécurité

- Python local : `3.14.8`.
- `GROUPED_ENCASHMENT_ENABLED=False` conservé.
- PostgreSQL natif et Chromium : indisponibles localement.
- Aucun push, commit, PR, migration sur base conservée, fusion ou déploiement.
- La branche locale contient les changements et les deux rapports; aucun commit local n'a été créé.
