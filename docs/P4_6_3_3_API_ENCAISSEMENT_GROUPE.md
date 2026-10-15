# P4.6 — Étape 3.3 : services et API d’encaissement groupé

## État de livraison

Cette étape ajoute les services applicatifs et les contrats HTTP adossés aux entités, dépôts, contraintes et à la migration `eg32a2026` de l’étape 3.2. Elle ne modifie pas l’interface utilisateur et n’active pas le parcours pour les utilisateurs : `GROUPED_ENCASHMENT_ENABLED` vaut `False` par défaut. L’activation en test est isolée au processus de test.

Chaque route groupée exige `caisse.encaisser` via la politique HTTP et vérifie aussi `caisse.encaisser.groupe` sur la caisse et le périmètre de chaque vente. Aucun rôle n’est affecté à cette permission par cette livraison.

## Contrats HTTP

Préfixe : `/api/caisses/organisations/{organisation_id}`. Les mutations portent une clé UUID `cle` pour la déduplication. Les objets JSON refusent les propriétés non documentées.

| Méthode et route | Objet principal | Résultat |
|---|---|---|
| `POST /encaissements-groupes/previsualiser` | `session_id`, `revision_session`, `ventes[]` (`vente_id`, `revision`), `identite_commune_confirmee`; `compte_id` et `revision_compte` facultatifs | total et empreinte de sélection; aucune mutation persistée |
| `POST /encaissements-groupes` | même sélection, `cle` | dossier `BROUILLON` et révisions retenues |
| `GET /encaissements-groupes/{id}` | — | état, révisions, ventes, référence du reçu éventuel |
| `PUT /encaissements-groupes/{id}/selection` | `cle`, `revision`, `revision_session`, `ventes[]`, attestation d’identité | nouvelle sélection; autorisée seulement en `BROUILLON` |
| `POST /encaissements-groupes/{id}/confirmations` | `cle`, révisions, session, moyen non espèces, montant, référence, source, preuve | confirmation d’acquisition externe, sans appeler de prestataire |
| `POST /encaissements-groupes/{id}/confirmations/{confirmation_id}/rapprocher` | `cle`, session, révisions, justification | rapprochement explicite de la confirmation à la session |
| `POST /encaissements-groupes/{id}/finaliser` | `cle`, `revision`, `empreinte`, session/révision, `ventes[]`, `reglements[]`, compte/révision facultatifs | un reçu groupé et ses ventilations de vente |
| `POST /encaissements-groupes/{id}/annuler` | `cle`, `revision`, justification | annulation; les paiements acquis doivent avoir été restitués |

Les règlements acceptent `ESPECES`, `CARTE`, `MOBILE_MONEY`, `CHEQUE` ou `VIREMENT`; les moyens non espèces requièrent une confirmation acquise et compatible. Les sources `TECHNIQUE_PRESTATAIRE` sont refusées : aucun acquéreur bancaire n’est intégré. Espèces et confirmations restent dans les modes autorisés par la configuration caisse.

## Sélection, identité et ventilation

- Un dossier contient de 2 à 20 ventes distinctes, transmises, non encaissées, de mode `SANS_TIERS`, liées à la même organisation, au site, à l’emplacement, à la caisse et à la session autorisés.
- La révision de chaque vente et celle de la session sont contrôlées à la création et à la finalisation. La sélection est figée dès la première confirmation externe.
- Une attestation explicite d’identité commune est requise. Les destinataires non vides doivent être identiques après normalisation; sinon, un compte fidélité commun doit être choisi et sa révision vérifiée.
- Les montants de chaque vente sont recalculés avec les règles P4.5/P4.6 existantes. Aucun rabais de groupe n’est créé. Le montant final inclut les remises et taxes existantes.
- Les paiements individuels antérieurs restent attachés à leur vente. Les paiements groupés et les espèces sont ventilés au prorata des lignes TTC nettes, en FCFA entiers, avec départage déterministe des restes. Les sommes par règlement et par vente doivent être exactes. Un excédent espèces devient le rendu caisse; un excédent non espèces est refusé.

## Finalisation atomique

Toutes les mutations passent par `StockService.operation` : verrou organisationnel partagé, clé d’idempotence, transaction SQLAlchemy, commit unique ou rollback complet. La finalisation relit et valide les ventes, remises, réservations, confirmations, paiements, ventilations et allocations; crée le reçu et les mouvements; écrit la fidélité acquise selon le barème applicable; consomme les réservations; fait évoluer les ventes et le dossier; incrémente les séquences et la révision de caisse une seule fois.

Les contraintes 3.2 et le registre commun des ventes encaissées protègent également le parcours individuel contre une seconde finalisation, y compris en cas d’appel concurrent. Les lecteurs de reçus, les retours/remboursements, les mouvements, les journaux fidélité et les clôtures utilisent les liens de ventilation pour retrouver les ventes du reçu groupé. Un retour exige `ventilation_id` afin de ne jamais mélanger les ventes et les budgets de remboursement d’un groupe. Les clôtures de session et Z bloquent tant qu’un dossier groupé est encore ouvert.

## Erreurs et rejeu

- `404` : parcours non activé, dossier absent dans l’organisation ou reçu sans ventilation.
- `403` : permission absente ou ressource hors périmètre.
- `409` : révision, état, session ou confirmation concurrents; vente déjà encaissée; allocation incompatible; dossier non résolu avant fermeture.
- `422` : contrat invalide, paiement insuffisant/surpayé sans espèces, confirmation non valide, identité absente ou retour groupé sans ventilation.

Une même clé `cle` et une charge identique rejouent le résultat enregistré. La réutilisation d’une clé avec une charge différente est refusée par le mécanisme commun d’idempotence.

## Intégration et validation

La livraison s’appuie sur les modèles et la migration 3.2 déjà intégrés dans le dépôt. Elle ne contient pas une copie ou une nouvelle version de la migration. Ne pas appliquer de migration sur les bases métier ou de recette conservées. Le ZIP fournit les nouveaux fichiers et un patch des adaptations 3.3 aux fichiers existants; l’intégration se fait sur le même état de branche que l’étape 3.2.

Tests ciblés exécutés :

- nouveaux tests de répartition, permissions, fermeture de session, confirmations non espèces, idempotence, reçu unique, allocations, lecture du reçu, retour par vente et protection contre le double encaissement;
- régression critique de l’encaissement individuel `test_encaissement_mixte_atomique_recu_et_rejeu`;
- compilation Python et `git diff --check`.

Aucune campagne complète ni validation PostgreSQL native n’a été lancée. La validation de concurrence PostgreSQL reste à faire sur une base jetable identifiée explicitement avant toute activation. Garder le parcours fermé et n’affecter aucune permission à un rôle avant validation métier et technique.

## Risques résiduels et travaux avant activation

1. Exécuter les scénarios de concurrence et de rollback sur une base PostgreSQL jetable, avec deux transactions individuelles/groupées concurrentes sur les mêmes ventes.
2. Faire relire les règles de partage des règlements et de remboursement par vente, en particulier les cas avec paiements individuels déjà confirmés et retours partiels.
3. Valider avec les lecteurs P4.5 les exports et clôtures Z de recette, y compris les comptages de ventes ventilées et les reçus historiques.
4. Faire une revue de permissions, de traces d’audit et de reprise opérationnelle, puis décider séparément de l’affectation de la permission et de l’activation du parcours.

Les connecteurs de paiement, l’utilisation de points en paiement groupé et les fonctionnalités P5 ne sont pas pris en charge par cette étape.
