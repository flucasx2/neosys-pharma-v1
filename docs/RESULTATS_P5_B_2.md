# Résultats — P5-B.2

## Référence de travail

- P5-A : `ebbe37e7fa241e9b29e3a9eb83c53635bf3f8e15`.
- P5-B.1 réutilisé sans réimplémentation : `b05b8b4c920858cc90749d91c6519a40a4d850b0`.
- Branche locale : `feat/p5-b-moteur-prise-en-charge`.
- Aucun changement de `main`, push, PR, déploiement ou base conservée.

## Fonction livrée

- Projection stricte des conventions P5-A vers le moteur pur P5-B.1, avec schéma contractuel documenté et refus des clés / versions inconnues.
- Calcul à partir du TTC net P4 autoritaire après remises, plutôt que des montants unitaires bruts des lignes.
- Simulation sans écriture et confirmation sur vente transmise dans la transaction idempotente P4.
- Snapshots immuables avec total, parts par ligne/organisme, étapes, versions P5-A, preuve d'adhésion, auteur, révision P4 et hash.
- Routes API de simulation, confirmation et consultation; panneau intégré à la préparation P4 permettant de sélectionner distinctement un bénéficiaire, simuler et confirmer.
- Autorisation P4 de préparer/transmettre un mode organisme limitée à la permission `tiers_payant.consulter`; le crédit reste bloqué.
- Migration additive `20261017_02`, contrainte composite ligne/vente/organisation, contraintes XAF, unicité par vente, FKs d'organisation et triggers d'immuabilité.
- Aucun appel de remboursement, clôture, fidélité, caisse ou création de créance n'est ajouté à la simulation/confirmation.

## Contrôles réellement exécutés

| Contrôle | Résultat |
|---|---|
| Suite ciblée P5-B.1, P5-B.2, P5-A et régressions P4 | `125 passed, 8 skipped, 1 warning, 3 subtests passed` en 76,27 s. Commande : `pytest -q tests/test_p5b_1_moteur_prise_en_charge.py tests/test_p5b_2_projection_persistance.py tests/test_p5b_2_integration_vente.py tests/test_p5a_tiers_payants.py tests/test_vente.py tests/test_clients_p4b.py tests/test_encaissement_groupe_domain.py tests/test_encaissement_groupe_persistance.py tests/test_caisse.py`. Python 3.14.8. |
| Contrôle ciblé après les dernières contraintes de migration | `3 passed, 1 warning` en 6,34 s. Il couvre la montée/descente migrationnelle P5-A/P5-B.2, le contrôle de permission P4 et le parcours API de confirmation. |
| Parcours HTTP P4/P5-B.2 avec SQLite de test | Simulation sans écritures, confirmation, allocations/étapes, consultation, rejeu identique, conflit de clé avec contenu différent et immuabilité vérifiés par `tests/test_p5b_2_integration_vente.py`. Ce test n'est pas une preuve PostgreSQL. |
| Migration P4-B/P4-C/P5-A/P5-B.2 sur SQLite temporaire | Montée/descente, FK/check/unique, triggers d'immuabilité et conservation d'un organisme P4-B fictif vérifiés. |
| Régressions P4 vente, caisse, clients P4-B et encaissement groupé | Incluses dans la suite ciblée ci-dessus; les assertions concernées sont passées. |
| Syntaxe Python et JavaScript | `compileall` ciblé avec Python 3.14.8 et `node --check src/neosys_pharma/presentation/web/vente.js` réussis après les derniers changements. `git diff --check` réussi. |
| PostgreSQL natif | **Non exécuté** : aucun serveur, client PostgreSQL, `pg_ctl`, Docker ou Podman disponible dans Work |
| Chromium/E2E navigateur | **Non exécuté** : aucun Chromium/Chrome ou suite Playwright de navigateur disponible; le JavaScript a seulement reçu une vérification syntaxique |

Les 8 tests ignorés dans la suite ciblée sont les contrôles explicitement réservés à PostgreSQL natif (migrations P4-B/P4-C et scénarios de concurrence vente/caisse). Les tests SQLite valident le parcours applicatif et les migrations sur un moteur de test; ils ne valident ni verrous `FOR UPDATE`, ni concurrence interconnexion PostgreSQL, ni triggers PostgreSQL. Aucune base persistante n'a été ciblée; le parcours d'intégration a utilisé une base SQLite temporaire.

## Anomalies révélées et corrigées

1. La FK des snapshots vers les lignes P4 nécessitait une clé unique composite exacte. Ajout de `uq_ligne_vente_vente_org` de façon additive; les tests P4 ont alors pu insérer des lignes normalement.
2. La projection utilisait le TTC brut d'une ligne, avant l'arrondi commercial P4. Elle consomme maintenant `VenteService.finance()` et rejette toute valeur non entière XAF.
3. Les snapshots de certaines étapes contenaient UUID/dates non sérialisables par le JSON SQLAlchemy. Ils sont désormais convertis en JSON canonique avant insertion.
4. Le test d'une permission additionnelle réutilisait un helper qui recréait un rôle déjà existant; l'ajout de permission est fait directement sur le rôle test existant.

## Limites et décisions requises

- L'encaissement final P4 continue de refuser les modes organismes. Ce lot confirme et fige le calcul, mais ne comptabilise pas une créance organisme et ne règle pas la part client. Il ne doit donc pas être présenté comme un encaissement tiers pleinement opérationnel.
- L'acquisition/régularisation des points sur montants payés par organismes n'est pas définie par P4-A/P5-B.2; la fidélité est laissée inchangée et ce chemin devra rester bloqué jusqu'à une décision métier.
- Les plafonds cumulatifs/périodiques, franchises, clauses contractuelles génériques non typées et cumuls de barèmes restent refusés/bloqués.
- Une recette PostgreSQL jetable et Chromium sont des gates avant acceptation finale de P5-B.2. Les étapes P5-C de créances, factures, bordereaux et règlements restent hors périmètre.
- La vérification Chromium n'a pas été exécutée : aucune instance/binaire Chromium/Chrome n'était disponible. Il n'y a donc pas de preuve visuelle ou navigateur du nouveau panneau de vente.

## Statut

Le code local couvre la projection, le calcul/snapshot et le parcours API/vente, mais **P5-B.2 n'est pas prêt pour recette financière finale** sans PostgreSQL natif, recette Chromium et décision/implémentation ultérieure du règlement de la part client et du traitement des parts organisme. P5-C n'a pas commencé.
