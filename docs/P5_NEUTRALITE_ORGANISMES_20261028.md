# P5 — Neutralité des organismes, correction locale du 28 octobre 2026

Statut : code et tests préparés par Codex, non exécutés, non intégrés. Autorisation explicite du propriétaire pour les six corrections locales ; aucune autorisation de tests sur bases, migration réelle, commit, push ou déploiement.

## Base et périmètre

Checkout exclusif `dev/codex-docker`, HEAD `b223ca2c86fe93bac811f3d6e146034dff3c8acf`. Changements utilisateur préexistants préservés. Cette mission lève le gel P5 uniquement pour la neutralité ciblée ; elle ne rouvre ni P4 ni P5-C. Les décisions du 27 octobre restent historiques et applicables hors de ce périmètre.

## Règles préparées

- Mode `PRISE_EN_CHARGE` accepté par les nouvelles ventes/proformas et proposé dans l'écran de vente. Les anciens modes restent acceptés par l'API et lisibles, sans conversion des données. L'émission financière des proformas avec tiers reste interdite comme auparavant.
- Les nouvelles confirmations, y compris celles de ventes ouvertes sous un ancien mode, exigent des clauses V1 : exactement un principal au rang 1, au plus un complémentaire, organismes uniques et rangs contigus. Les configurations historiques plus larges restent lisibles ; leur absence de conformité bloque une nouvelle confirmation.
- Les conventions portent l'autorisation des ordres, jamais la fiche organisme. Le paramétrage organisationnel existant fournit le couple organisme/convention et les affiliations existantes fournissent les droits vérifiés.
- Le serveur détermine l'ordre par intersection des ordres autorisés par toutes les conventions sélectionnées. Dans chaque convention, un sélecteur explicite du bénéficiaire prime sur le sélecteur général. Une intersection vide ou plusieurs ordres possibles bloquent le calcul ; aucun choix arbitraire ni ordre envoyé par le vendeur.
- Une convention inactive ou hors période ne peut autoriser une nouvelle confirmation. Droits inconnus, preuves manquantes, ambiguïtés d'adhésion et incohérences organisationnelles restent bloquants.
- Refus, autres situations de droits non applicables (dont expiration), exclusions, plafonds atteints et écarts résiduels ont chacun un traitement explicite. `CLIENT` réserve le solde au client et termine l'intervention sur ce solde ; `SUIVANT` poursuit avec le complémentaire autorisé ; `BLOQUER` refuse le calcul concerné. Un `SUIVANT` sans organisme suivant et avec solde positif bloque. Aucune valeur financière de traitement n'est attribuée par défaut en production.
- Le calcul exact des taux, les arrondis contractuels et le plafond par ligne existants sont réutilisés. Conservation du total vérifiée par le moteur avant confirmation. Les plafonds périodiques consommables restent exclus, sans compteurs nouveaux.
- Les étapes figent les clauses, organismes, rangs, rôles effectifs, conventions/versions, droits/révisions, barèmes et parts. La persistance des parts utilise désormais le rang effectif de l'étape, et non l'ordre lexical des UUID. La simulation d'une vente encaissée ou annulée est refusée : consultation du snapshot historique uniquement. Consultation historique et contraintes d'immutabilité conservées ; aucune réécriture des snapshots déjà enregistrés.

## Contrat de configuration

Les routes existantes POST `/conventions` et `/conventions-configurees` acceptent `conditions.schema_version = 2`. Les permissions existantes de gestion des conventions restent obligatoires. Le schéma 1 reste lisible et créable pour la transition, mais ne suffit pas pour confirmer une nouvelle prise en charge.

Exemple structurel (remplacer les symboles par les UUID canoniques des organismes/bénéficiaires enregistrés) :

```json
{
  "schema_version": 2,
  "coordination": {
    "ordres": [
      {"beneficiaires_ids": [], "organismes_ids": ["UUID_A", "UUID_B"]},
      {"beneficiaires_ids": ["UUID_BENEFICIAIRE"], "organismes_ids": ["UUID_B", "UUID_A"]}
    ],
    "traitements_solde": {
      "REFUS": "BLOQUER",
      "DROITS": "BLOQUER",
      "EXCLUSION": "SUIVANT",
      "PLAFOND": "SUIVANT",
      "ECART": "CLIENT"
    }
  }
}
```

Cet exemple illustre la syntaxe ; il ne définit aucune politique contractuelle universelle. Chaque convention doit autoriser l'ordre retenu et définir sa propre conduite. La dernière convention ne peut demander `SUIVANT` sur un solde positif. La position dans `organismes_ids` détermine le rôle effectif ; les références de convention proviennent exclusivement du paramétrage serveur. Un bénéficiaire ne crée aucun droit par son seul référencement dans un sélecteur : les vérifications d'affiliation restent requises.

L'administration des clauses nouvelles passe par l'API autorisée. L'éditeur graphique existant ne les saisit pas ; il conserve `conditions` lors de la préparation d'une nouvelle version. Une nouvelle convention créée sans clauses demeure non confirmable. Aucun calcul n'a été ajouté en JavaScript.

## Migration proposée, non appliquée

`20261028_01_p5_mode_generique.py`, parent `20261019_06` : élargissement des CHECK `ck_vente_mode` et `ck_proforma_mode` sur `ventes` et `proforma_versions`, avec conservation de toutes les anciennes valeurs. Aucun UPDATE de données, nouvelle table, rôle permanent ou permission. Sur SQLite, les triggers des tables reconstruites et ceux qui les référencent sont sauvegardés puis réinstallés à définition identique ; le test préparé compare leurs définitions avant/après upgrade et downgrade. Les clauses réutilisent le JSON versionné existant ; aucune colonne supplémentaire n'est nécessaire. Le downgrade vérifie les deux tables avant toute modification et refuse en présence d'une opération au mode générique. Les contraintes de cardinalité V1 sont applicatives pour préserver les configurations historiques.

## Tests préparés et limites de preuve

- `tests/test_p5_neutralite.py` : principal seul/deux organismes, inversion par bénéficiaire, désaccord entre conventions, cardinalités invalides, clauses absentes, expiration/refus/exclusion avec trois conduites, plafonds/écarts, arrondis et snapshots.
- `tests/test_p5_neutralite_integration.py` : paiement sans organisme, lecture de proformas nouvelles/historiques, inversion autorisée/refusée côté HTTP, rangs SQL, finalisation et conservation du snapshot.
- `tests/test_p5_neutralite_migration.py` : cycle SQLite jetable explicite, CHECK historiques/génériques et refus de downgrade occupé. Aucun URL de poste repris par ce cycle.
- Intégration P5-B.2 paramétrée en modes générique et CNAMGS ; les assertions existantes de persistance/idempotence/immutabilité restent présentes.
- Fixture P5-B.3 ramenée à deux organismes V1, clauses synthétiques explicites. Les nombres de créances/organismes attendus dans les tests consommateurs P5-C sont adaptés de trois à deux ; aucun code P5-C modifié. Le cycle C2 passe au head avant `command.check`, tout en conservant ses jalons, contrôles et refus.
- Tests de permissions vente étendus au nouveau mode. Tests de conventions raccordés aux clauses explicites et à un principal.

Aucun test (y compris SQLite), collect-only, import applicatif ou migration n'a été exécuté. Les vérifications de syntaxe ne valent ni acceptation métier ni validation SQL/PostgreSQL. Les rapports de tests antérieurs ne valident pas ces modifications. Les tests existants de simulation historique restent conservés, y compris leurs comportements antérieurs, sans autoriser une nouvelle confirmation dépourvue des clauses V1.

## Décisions et validations encore nécessaires

Faire valider les clauses réelles de chaque convention : ordres par bénéficiaire, traitements de refus/droits/exclusions/plafonds/écarts, notamment `CLIENT` qui termine la coordination du solde. Cette livraison propose une sémantique explicite et conservatrice ; elle ne renseigne aucune donnée contractuelle réelle.

La création d'un éditeur graphique des clauses et les compteurs périodiques sont hors de cette livraison. Les tests PostgreSQL, contraintes/migrations réelles et recette devront être autorisés sur une cible jetable identifiée et protégée. Aucun service test, base conservée ou environnement de développement n'a été démarré ni modifié.

Arrêt après livraison : attendre validation, autorisation distincte d'exécution des tests et autorisations Git. Aucune stabilisation globale P4, activation P5-C ou opération GitHub.

## Fichiers du lot local

Les fichiers AGENTS.md, README.md et les autres fichiers non suivis déjà présents ne font pas partie des modifications de cette mission. Les ajouts dans les documents de continuité conservent leur contenu utilisateur antérieur.

- `JOURNAL_DEVELOPPEMENT.md`
- `PROGRESS.md`
- `REPRISE_NEOSYS_PHARMA.md`
- `docs/ARBITRAGES_PLAFONDS_P5.md`
- `docs/P5_CONF_1B.md`
- `docs/P5_NEUTRALITE_ORGANISMES_20261028.md`
- `docs/REGISTRE_NON_CONFORMITES_P5.md`
- `migrations/versions/20261028_01_p5_mode_generique.py`
- `src/neosys_pharma/application/configuration_convention_service.py`
- `src/neosys_pharma/application/prise_en_charge_persistante_service.py`
- `src/neosys_pharma/application/projection_prise_en_charge.py`
- `src/neosys_pharma/application/tiers_payants_service.py`
- `src/neosys_pharma/domain/coordination_prise_en_charge.py`
- `src/neosys_pharma/domain/prise_en_charge.py`
- `src/neosys_pharma/domain/vente.py`
- `src/neosys_pharma/infrastructure/proforma_models.py`
- `src/neosys_pharma/infrastructure/vente_models.py`
- `src/neosys_pharma/presentation/proforma_api.py`
- `src/neosys_pharma/presentation/tiers_payants_api.py`
- `src/neosys_pharma/presentation/vente_api.py`
- `src/neosys_pharma/presentation/web/conventions.js`
- `src/neosys_pharma/presentation/web/vente.js`
- `tests/p5_coordination_fixtures.py`
- `tests/test_p5_conf_conventions.py`
- `tests/test_p5_neutralite.py`
- `tests/test_p5_neutralite_integration.py`
- `tests/test_p5_neutralite_migration.py`
- `tests/test_p5b_2_integration_vente.py`
- `tests/test_p5b_3_encaissement_prise_en_charge.py`
- `tests/test_p5c2_facturation.py`
- `tests/test_p5c2_migration.py`
- `tests/test_p5c_creances.py`
- `tests/test_vente.py`

## Vérifications statiques effectivement réalisées

Le 28 octobre 2026 : analyse AST de 24 fichiers Python du lot (syntaxe valide, sans import applicatif), `node --check` sur vente.js et conventions.js sans erreur, `git diff --check` sans erreur. Graphe des révisions lu statiquement : tête unique 20261028_01. Ce contrôle n'exécute aucun code Alembic. Git reste sur dev/codex-docker au HEAD initial. Les avertissements CRLF de Git concernent des documents déjà modifiés ; aucun changement de branche, index ou commit. Aucun test ni migration exécuté.
## Mise à jour — résultats ciblés du 28 octobre 2026

Après autorisation, le test `test_inversion_controlee_serveur_et_rangs_persistes[False]` a été corrigé uniquement dans son assertion de `confirme_le`, puis rejoué : 1 réussi sur SQLite. Le fichier `tests/test_p5_neutralite_integration.py` a réussi 6/6 sur SQLite et 6/6 sur PostgreSQL. La normalisation UTC est limitée à la valeur d’horodatage ; les autres champs du snapshot sont comparés strictement.

Résultat effectif des suites ciblées exécutées dans le checkout source : SQLite 82 réussis, 0 échoué, 6 ignorés ; PostgreSQL 46 réussis, 0 échoué, 1 ignoré. Les migrations SQLite étaient incluses dans la suite ciblée. Le cycle PostgreSQL `20261019_06` → `20261028_01`, contrôles Alembic, contraintes, triggers, valeurs historiques et refus de downgrade avec opérations génériques a également été vérifié sur base jetable marquée.

Ces résultats précèdent le transfert sur `origin/main` `3ca0eebe`. Ils ne constituent pas des tests du nouveau worktree ; aucun test avec base n’a été exécuté pendant ce transfert.

## Préparation sur `origin/main` — 28 octobre 2026

Le transfert dans le worktree `codex/p5-neutralite-organismes` raccorde `20261028_01` à `20261022_02`, tête P4-05 présente dans `origin/main` à `3ca0eebe`. Le parent initial `20261019_06` aurait laissé deux têtes Alembic et a été corrigé uniquement dans cette nouvelle migration ; les révisions P4 existantes restent intactes. La migration P5 est additive. Le test `tests/test_p5c2_migration.py` reste identique à `origin/main`, y compris le changement de jour UTC. Les contrôles de ce worktree sont statiques seulement ; aucun test ni aucune migration avec base n’y a été exécuté.
