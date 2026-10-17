# Corrections prioritaires P4 — préparation RC1

## Périmètre et base

Travail local isolé sur `work/p4-rc1-corrections`, à partir du SHA immuable PR #7 `a4b524e5d5956c9d65b02622452e874e11b3ac88`. PR #6 (`1ddc8c3ea1d37c3b307d57ad48a7e3ee8db44c28`) est un ancêtre de PR #7. Aucune base conservée n'a été utilisée. Aucun push, PR, fusion ou déploiement n'a été effectué. Le flag `GROUPED_ENCASHMENT_ENABLED` reste `False`.

## Causes établies et changements

### Installation répétée de `eg32_claim`

La migration PostgreSQL et le hook `Base.metadata.after_create` installent les mêmes fonctions et triggers. La seconde installation exécutait `CREATE FUNCTION eg32_claim()` et PostgreSQL refusait la fonction déjà présente.

`guard_sql()` rend maintenant l'installation répétable avec `CREATE OR REPLACE FUNCTION` et en supprimant chaque trigger correspondant avant de le recréer. Le déclencheur `eg32_claim`, son verrouillage de vente et le registre unique `caisse_ventes_encaissees` restent intacts. Un contrôle unitaire vérifie que chaque trigger créé a un `DROP TRIGGER` préalable; un test PostgreSQL dédié réexécutera réellement le script d'installation.

### Fidélité d'un groupe avec plusieurs clients

Le modèle précédent ne portait qu'un compte fidélité commun au dossier et le service calculait les points sur l'agrégat. Les retours groupés résolvaient aussi le titulaire à partir de l'encaissement global. Cela ne respecte pas la règle métier selon laquelle chaque vente peut avoir un client différent.

Les sélections de vente et les ventilations portent désormais un compte et sa révision par vente. Le service valide l'association et calcule les points à la limite de chaque vente; la régularisation retrouve le compte à partir de la ventilation de la vente retournée. Les clients sans fidélité restent sans compte attribué. Une migration additive `eg33a2026` ajoute les relations et reprend l'ancien compte pour les sélections et ventilations existantes.

Le test local multi-client a ensuite exposé l'unicité historique `(encaissement_id, type)` du journal : elle interdisait plusieurs écritures d'acquisition pour des comptes distincts dans le même encaissement. La migration `eg34a2026` la remplace par une unicité `(encaissement_id, type, compte_id)`. Les journaux des ventes distinctes restent séparés; les compensations de retour continuent d'être reliées à chaque retour et restent idempotentes via `fidelite_compensations_retour.retour_id`. Les downgrades `eg33a2026` et `eg34a2026` refusent maintenant de retirer des données ou contraintes lorsqu'il existe une fidélité par vente ou plusieurs comptes par encaissement qui ne pourraient pas être représentés par le schéma antérieur.

### Preuve de concurrence PostgreSQL

L'ancien test utilisait le même `TestClient` pour les deux appels. Il ne garantissait donc pas deux contextes HTTP indépendants ni l'observation d'une vraie attente de verrou PostgreSQL. Les tests sont corrigés pour utiliser un second `TestClient`, recopier le contexte d'authentification, comparer les backends PostgreSQL et attendre explicitement un second backend actif en `wait_event_type='Lock'`, avec délais bornés. Le code conserve les scénarios simultanés et ne les remplace pas par des appels séquentiels.

Ces tests corrigés n'ont pas encore été exécutés : aucun serveur PostgreSQL natif n'est accessible dans cet environnement.

### 403 du solde d'un retour

La route `finance_solde` exige `caisse.remboursement.demander` dans la politique HTTP. Le fixture PostgreSQL du scénario de retour accordait `vente.retour.gerer` mais pas cette permission nécessaire à la consultation du solde remboursable. Le refus survient au contrôle d'accès; il ne révèle pas une permission métier à élargir.

Le fixture de ce seul scénario accorde explicitement les deux permissions nécessaires. Aucun rôle, utilisateur ou catalogue de permissions de production n'est modifié.

### Bouton « Utiliser cette session » dans Chromium

Le journal CI disponible montre que la session a été enregistrée puis que l'assertion du bouton a échoué, mais ne contient ni réponse HTTP ni état de la session. Il ne permet donc pas de distinguer une session absente de `GET /sessions`, une erreur de rafraîchissement, un état inattendu ou un `caissier_id` différent de l'utilisateur courant. La cause exacte n'est pas démontrée et aucune correction du fonctionnement de caisse n'est introduite.

Le test conserve l'assertion et inclut désormais, en cas d'échec, la réponse de création, l'identifiant utilisateur et le résultat de `GET /sessions`. Ces éléments permettront de localiser la cause au prochain run Chromium. Aucun navigateur Chromium exécutable n'est disponible ici; la recette n'a pas été rejouée.

## Préservation PR #6 / PR #7

PR #7 descend de PR #6; l'historique est linéaire et les fonctions P4 de PR #6 sont présentes dans la base de travail. Les corrections locales ne changent pas le comptoir, les PDF historiques, les écrans de vente/préparation, l'encaissement individuel, les permissions de production ni les règles de remboursement et de clôture. Les seuls changements d'interface sont une instrumentation diagnostique du test Chromium, sans changement de comportement utilisateur.

## Risques résiduels

- Les migrations `eg33a2026` et `eg34a2026` ont seulement été exercées avec SQLite local. Leur application, backfill, contraintes, réversibilité et compatibilité PostgreSQL restent à confirmer sur une base PostgreSQL jetable.
- La concurrence PostgreSQL réelle et l'observation de contention restent non vérifiées.
- Les retours partiels et compensations multi-clients sont couverts par un scénario PostgreSQL préparé, mais pas encore exécuté. Les parcours historiques individuels ont été vérifiés sur SQLite.
- La cause Chromium de la session ouverte reste indéterminée jusqu'à la collecte des nouveaux diagnostics dans Chromium.
- P4-RC1 ne peut pas être déclaré prêt tant que ces contrôles ne sont pas passés. L'encaissement groupé reste désactivé.
