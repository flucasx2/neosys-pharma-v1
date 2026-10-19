# Incrément 07 — compatibilité et préparation CI

Base : abc2b397cb104aaa10c9a7316117700b3cbb1e6f. Corrections locales après revue ciblée des parcours déjà présents ; aucun workflow distant exécuté, aucune migration nouvelle.

## Causes et corrections

1. Les noms de champs des nouveaux fournisseurs pouvaient casser les sélecteurs Chromium historiques. Le champ de confirmation conserve name=mode et ses valeurs CARTE/etc. pour les moyens génériques. Le formulaire de remboursement conserve montant_ESPECES et mode_CARTE lorsqu'il n'y a pas de fournisseur ; les origines configurées utilisent des contrôles indépendants. Assertions DOM supplémentaires, aucun test Chromium supprimé ou modifié pour masquer cette incompatibilité. Les scénarios réels restent à exécuter.
2. La CI PostgreSQL utilisait neosys_test, tandis que le garde-fou des modules de consolidation exige neosys_p4p5_* + confirmation exacte + marqueur. Le refus était donc prévisible et justifié. La CI préparée utilise une base API neuve neosys_p4p5_ci et des bases séparées pour Alembic et P5-CONF.1b, avec noms/confirmations/commentaires correspondants. Les garde-fous ne sont pas retirés.
3. Le job postgres devient une matrice **17 et 18**, fail-fast=false. La suite entière reste pytest -q, aucun --ignore ajouté. La synthèse dépend du résultat agrégé postgres ; échec/annulation/ignorance obligatoire ne peut produire un statut final vert selon les tests de politique. Les deux jobs impliquent davantage de temps runner lors de la publication future, sans coût distant engagé ici.
4. Les nouveaux scénarios DOM et trois variantes Chromium à HTTP simulé sont prévus dans le job browser (Node 24, jsdom 30.1.3, Playwright Node/Python 1.58.0 cohérents). Le parcours réel existant FastAPI/PostgreSQL via ci/browser.py reste exécuté séparément. Ne pas assimiler ces simulations à une validation financière.
5. Échec **réellement reproduit** de l'ancien test de migration P5-CONF.1b : command.check était appelé sur 20261019_01 alors qu'un nouveau head existe (Target database is not up to date). Le test conserve la montée par l'ancienne version et les données historiques, monte jusqu'au head avant vérification, puis exécute toujours son cycle descendant/remontant et ses assertions d'immuabilité. Aucune assertion de données ou de rollback retirée.
6. Défaut reproduit du premier document de carte : numéro visible de 180 caractères tronqué à 100, malgré un code-barres court valide. Le rendu utilise des paragraphes avec retour à la ligne, sans troncature des identifiants ou noms. Test en échec avant correction, puis réussi ; PDF figé et réimpression conservés.

## Résultats observés

- Contrôleur CI et 4 nouveaux tests de cohérence : **48 tests unittest réussis**, Python 3.14.8, 4.169 s. Un ResourceWarning d'un test HTTP 403 local simulé ; aucun appel GitHub réel.
- YAML parsé, matrice 17/18 et Python embarqué vérifiés syntaxiquement localement. Aucun actionlint ni runner GitHub exécuté ; ce contrôle n'est pas une validation d'exécution Actions.
- Test P5-CONF.1b reproduit avant correction : **1 failed** (2.86 s) ; après correction **1 passed, 1 warning — 4.77 s**, SQLite temporaire.
- Cartes/document et immuabilité après correction de troncature : **4 passed, 1 warning — 6.37 s** ; le cas long échouait avant correction. Ce sont des tests locaux, pas du matériel d'impression.
- DOM fournisseurs **9 assertions**, formulaires **17**, groupe **19**, après conservation des sélecteurs historiques. Les tests déjà exécutés dans l'incrément 06 restent documentés séparément : import catalogue 6, import bénéficiaires 10, conventions 38 (HTTP simulé).
- node --check et git diff --check réussis. Pas de nouvelle campagne historique complète.

La validation intégrée de 06 avait donné 19 passed/4 skips ; les contrôles ciblés de 07 la complètent sans être additionnés comme des tests uniques supplémentaires. Aucun résultat PostgreSQL ou Chromium réel n'est annoncé ici.

## Future exécution, après autorisation de publication uniquement

Publier la branche autorisée, puis utiliser la **version de tests.yml de cette branche**, pas le contrôleur main ancien. En workflow_dispatch, renseigner target_branch=work/p4-p5-consolidation et expected_sha=<SHA distant exact publié>. Ne pas lancer une commande avec un SHA local non publié et ne pas reconstruire l'historique automatiquement. La politique vérifie la distinction entre SHA applicatif et contrôleur.

Une PR prête pour revue déclenchera les contrôles selon la politique existante ; aucune PR/push/dispatch n'est autorisé par cette livraison. L'activation groupée de test reste limitée à l'ancien contexte browser jetable neosys_browser, CI et marqueur explicites. Aucune valeur par défaut serveur changée.
