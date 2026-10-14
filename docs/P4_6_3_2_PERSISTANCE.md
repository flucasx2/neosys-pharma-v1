# P4.6 — Étape 3.2 : domaine, persistance et migration préparée

Statut : **implémentée localement pour revue, non publiée, parcours groupé non activé**.
Base fonctionnelle : conception 3.1 validée. Aucun endpoint de finalisation groupée, aucune modification d’interface, aucun service P5.

## Contrôle préalable

Branche locale : `feat/p4-6-comptoir`. Les différences P4.6 existantes ont été examinées et conservées. La vérification inverse du patch ergonomique réussit ; il n’a pas été réappliqué. L’état du poste Windows ne peut pas être inspecté depuis cet espace : le vérificateur de l’étape 3.1 demeure la procédure côté Windows.

Les SHA256 de `caisse.js`, `proforma.js`, `index.html` et `style.css` sont identiques avant/après l’étape 3.2. Aucun écran ni raccourci validé n’est modifié.

## Livré

- Entités de domaine immuables : dossier, sélection, ventilation par vente et allocation par ligne.
- États explicites et refus des transitions invalides ; annulation d’un dossier en règlement exige résolution explicite des paiements acquis. Ce contrôle de domaine ne remplace pas la vérification des preuves du futur service applicatif.
- Instantanés de ventilation profondément immuables, montants entiers XAF et égalité HT + TVA = TTC historique.
- Validateur exact de la matrice : somme par règlement, par vente et par ligne, refus des doublons et des associations hors encaissement/organisation.
- Repository limité à son organisation, création/lecture/modification de sélection avant paiement, insertion des ventilations/allocations. Aucun commit implicite, octroi d’accès, paiement, consommation de stock ou calcul de fidélité dans le repository.
- Cinq tables : `caisse_dossiers_groupes`, `caisse_selections_groupes`, `caisse_ventilations`, `caisse_allocations_reglements`, `caisse_ventes_encaissees` (registre technique).
- Extensions compatibles des encaissements et confirmations historiques : portée individuelle ou groupée, explicite et exclusive ; liens de ventilation facultatifs sur les retours.
- Permission système `caisse.encaisser.groupe`, sans création de rôle ni affectation automatique. Seul le catalogue versionné est étendu ; les règles P1 d’autorisation ne sont pas modifiées.

## Garantie contre le double encaissement

Un registre unique par UUID de vente est commun au lien historique `Encaissement.vente_id` et au lien nouveau `Ventilation.vente_id`.

Avant insertion d’un encaissement individuel ou d’une ventilation, un trigger réclame le même couple vente/encaissement. Une représentation supplémentaire du **même** encaissement individuel est acceptée sans mise à jour du registre. Un encaissement différent est refusé, dans les deux ordres d’insertion. Le registre est immuable et possède une clé étrangère différée vers l’encaissement.

PostgreSQL verrouille aussi la vente avec `FOR UPDATE` dans cette réclamation, en complément de la clé primaire du registre. Les services futurs continueront d’utiliser le verrou organisationnel et l’idempotence existants ; cette étape ne remplace pas leurs garanties applicatives.

À la migration, les seules données ajoutées au registre sont les UUID des liens historiques déjà avérés. Aucun montant, allocation, reçu ou mouvement historique n’est inventé ou réécrit.

## Contraintes de portée et financières

Clés étrangères composites : organisation, appartenance de la caisse à l’emplacement, emplacement au site, allocation au même règlement/encaissement/ventilation et à la ligne de sa vente. Unicités de sélection, d’ordre, de vente encaissée et d’allocation.

PostgreSQL : contrôles différés au commit sur le nombre de ventes du groupe, la correspondance sélection/ventilations, les contextes, les sommes des ventilations/règlements/allocations. Les totaux intermédiaires peuvent être incomplets dans la transaction, mais pas au commit. Les liens financiers sont immuables, la sélection est figée après début des règlements et les dossiers terminaux ne sont pas modifiables.

SQLite : contraintes structurelles, registre commun, immuabilité et protections de sélection/contexte ; pas de déclencheurs de contrainte différés pour toutes les sommes. Le validateur de domaine couvre la matrice exacte par ligne ; son appel depuis le service de finalisation sera ajouté en 3.3. Les tests SQLite ne sont pas présentés comme preuve de concurrence PostgreSQL.

## Migration préparée

Révision **`eg32a2026`**, parent **`a46c001d2026`** :
`migrations/versions/eg32a2026_encaissement_groupe_persistance.py`.

- Définitions de tables SQL figées, sans import des modèles ORM évolutifs pour créer les tables.
- DDL de protections dans `encaissement_groupe_sql_v1.py`, versionné à figer après validation ; toute évolution publiée devra employer une nouvelle version/migration.
- Ajouts de tables, colonnes et contraintes, registre des anciennes identités, permission dédiée. Aucun UPDATE des anciens encaissements, reçus, règlements ou journaux.
- Les anciens individuels restent lisibles et finalisables après migration ; aucune ventilation financière rétroactive fabriquée.
- Les reconstructions SQLite restaurent explicitement les CHECK historiques et les triggers d’immuabilité.
- Le downgrade refuse de supprimer des dossiers, ventilations ou allocations nouvelles. Les anciens individuels seuls restent compatibles avec le retour au parent, sur une base jetable.

**Ne pas installer ce patch de persistance dans l’application de recette conservée avant autorisation de la stratégie de migration.** Les modèles étendus attendent les nouvelles colonnes. Une base restée à `a46c001d2026` doit continuer à utiliser son code compatible existant. Le lanceur Windows précédent exige volontairement ce head ; son évolution ne sera décidée qu’après autorisation.

Aucune migration n’a été appliquée à `neosys_pharma_v1`, `neosys_p46_recette_20261012` ou une autre base conservée. Seuls des fichiers SQLite neufs `neosys_eg32_jetable_*`/`eg32-schema-jetable.db`, SQLite mémoire et PostgreSQL embarqué mémoire ont été utilisés ici.

## Tests ciblés et résultats

Résultats cumulés des contrôles distincts (sans compter les répétitions nécessaires après corrections) :

| Contrôle | Résultat |
| --- | --- |
| Domaine : états, snapshots, XAF, matrice et associations | 15 tests réussis |
| Repository et SQLite mémoire : portée, sélection, double encaissement, immuabilité | 5 tests réussis |
| Protection des bases de test | 6 tests réussis |
| Alembic SQLite : cycle/check, refus du downgrade, historique/PDF/journaux | 3 tests réussis |
| Encaissement individuel mixte/idempotence existant, ciblé car ses modèles sont étendus | 1 test réussi |
| PostgreSQL embarqué : schéma neuf, doublons dans les deux sens, sommes au commit/rollback, immuabilité, contexte, permission non attribuée | 7 scénarios réussis |
| PostgreSQL embarqué : upgrade d’un historique fictif au parent, ancien encaissement/règlement/PDF inchangés | 1 scénario réussi |
| Compilation Python, `git diff --check`, hashes des interfaces | Réussis |

Total : **30 tests Python ciblés distincts**, plus **8 scénarios SQL PostgreSQL embarqués**.

`upgrade → check → downgrade → upgrade → check` exécuté sur SQLite neuf. Test de compatibilité sur une copie reconstruite uniquement à partir des fixtures fictives : PDF historique identique octet pour octet, journaux et règlements inchangés, registre ajouté, aucune ventilation historique fabriquée. Les données de recette humaine n’ont pas été copiées ou modifiées.

Le moteur SQL embarqué est **PostgreSQL 18.6 / PGlite 0.5.9 (WASM)**, en mémoire, avec extension btree_gist. Le SQL Alembic PostgreSQL et les fonctions/triggers ont réellement été exécutés, pas seulement compilés. Ce n’est **pas** une recette sur serveur PostgreSQL natif 17/18 ni une validation multi-connexions.

Un avertissement de dépréciation Starlette/httpx est présent, sans échec. Les fixtures financières existantes utilisées par ces tests s’exécutent seulement sur mémoire ou une base jetable explicitement confirmée ; la garde refuse notamment les deux bases conservées du projet. Aucun test complet ni Chromium n’a été relancé : les fichiers UI n’ont pas changé.

## Risques et travaux suivants

1. Concurrence native à deux connexions PostgreSQL, cycle Alembic PostgreSQL en ligne et `alembic check` natif restent à exécuter sur une **nouvelle base jetable autorisée**. PGlite ne démontre pas ces propriétés de concurrence.
2. Les services/API groupés, les vérifications conjointes `caisse.encaisser` ET `caisse.encaisser.groupe`, les confirmations/rapprochements et leur cycle transactionnel sont l’étape 3.3. Aucun client ne peut utiliser un nouveau parcours groupé à ce stade.
3. Les lecteurs P4.5 (retours, remboursements, fidélité, Z, reçus) devront interpréter les groupes avant leur activation. Leurs colonnes historiques et leurs règles actuelles ne sont pas remplacées ici.
4. Le contrôle des montants exacts par ligne est fourni dans le domaine ; il doit être intégré obligatoirement dans la future finalisation. Les triggers différés vérifient les sommes par encaissement, vente et règlement.
5. Déploiement de code et évolution de schéma devront être coordonnés. Ne pas lancer automatiquement `alembic upgrade head` sur un environnement existant.

P5 : pas d’organisme, couverture, créance, taux ou part client fictive. Les ventilations et leurs instantanés laissent les identifiants et montants par vente/ligne nécessaires à une extension ultérieure.

## Instructions d’intégration et de livraison

L’archive est destinée à une revue/intégration ultérieure dans le dépôt `feat/p4-6-comptoir`, à partir de la base de travail `8c8138bf7202136d6e0b9e33e3cd157e4b48922f`. Elle contient le patch des trois fichiers suivis étendus et les nouveaux fichiers de l’étape 3.2 avec leurs chemins de dépôt. Vérifier le `git status` et conserver une sauvegarde locale avant toute intégration ; ne pas écraser les modifications d’une autre étape.

Après extraction à la racine d’une copie de travail correspondant à cette base, examiner puis appliquer le patch fourni avec `git apply --check etape3_2.patch`, puis `git apply etape3_2.patch`. Les nouveaux fichiers sont livrés avec leurs chemins `docs/`, `migrations/versions/`, `src/` et `tests/`. En cas de divergence ou de patch partiellement présent, arrêter et réconcilier manuellement ; ne pas utiliser `--reject` ni remplacer les fichiers sans revue.

La révision `eg32a2026` dépend de `a46c001d2026`. Son application est réservée à une base PostgreSQL jetable dédiée après autorisation distincte de validation native. Ne pas lancer `alembic upgrade head` sur la recette conservée ou une base métier. La migration n’active aucun endpoint groupé ; l’étape 3.3 et l’adaptation des lecteurs P4.5 restent nécessaires avant toute activation.

Les contrôles déjà réussis sont ceux consignés dans « Tests ciblés et résultats ». Ils ne sont pas relancés pour cette livraison. La suite native PostgreSQL, notamment les essais de concurrence à deux connexions, devra être planifiée séparément sur une base jetable explicitement identifiée.

## Fichiers de cette étape seulement

Modifiés :
- `src/neosys_pharma/domain/organisation/permissions_systeme.py` (permission dédiée uniquement).
- `src/neosys_pharma/infrastructure/caisse_models.py`.
- `src/neosys_pharma/infrastructure/regularisation_models.py`.

Ajoutés :
- `src/neosys_pharma/domain/encaissement_groupe.py`.
- `src/neosys_pharma/infrastructure/encaissement_groupe_models.py`.
- `src/neosys_pharma/infrastructure/encaissement_groupe_repository.py`.
- `src/neosys_pharma/infrastructure/encaissement_groupe_sql_v1.py`.
- La migration `eg32a2026_encaissement_groupe_persistance.py`.
- `tests/test_encaissement_groupe_domaine.py`.
- `tests/test_encaissement_groupe_persistance.py`.
- `tests/test_encaissement_groupe_migration.py`.
- `tests/postgresql_embarque_encaissement_groupe.cjs`.
- `tests/postgresql_embarque_migration_historique.cjs`.
- Ce document.

Aucun commit, push, GitHub Actions, fusion ou déploiement. Arrêt pour validation de l’étape 3.2.
