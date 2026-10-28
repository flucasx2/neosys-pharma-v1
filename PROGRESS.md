# Suivi du projet — NeoSys Pharma V1

Dernière mise à jour : 2026-10-28. Dernière IA : Codex.

## État courant

- Préparation P5 Neutralité dans le worktree `codex/p5-neutralite-organismes`, basé sur `origin/main` `3ca0eebe9e3756aca77ba8ac6d9e991a92c13c93`.
- Le checkout utilisateur `dev/codex-docker` reste à `b223ca2c86fe93bac811f3d6e146034dff3c8acf`, non modifié.
- P4 #14 et #15 sont fusionnées dans `origin/main` (`13af7dc` puis `3ca0eeb`). Leurs preuves et le bilan P4 restent conservés.
- P5 Neutralité transféré de façon ciblée ; migration additive `20261028_01`, parent `20261022_02` (tête P4 conservée). Aucun commit ni publication.

## Résultats déjà vérifiés dans le checkout source

- Après correction de l’assertion UTC : suite SQLite ciblée effective 82 réussis / 0 échoué / 6 ignorés ; PostgreSQL ciblé 46 réussis / 0 échoué / 1 ignoré.
- `tests/test_p5_neutralite_integration.py` : 6 réussis sur SQLite et 6 sur PostgreSQL. Cycle de migration PostgreSQL vérifié séparément.
- Ces résultats précèdent le transfert et ne valident pas la nouvelle base `origin/main`. Aucun test avec base n’a été lancé dans ce worktree.
- Détail et limites : `docs/P5_NEUTRALITE_ORGANISMES_20261028.md` ; décisions cumulatives : `JOURNAL_DEVELOPPEMENT.md` et `REPRISE_NEOSYS_PHARMA.md`.

## Blocages et suite

Les vérifications statiques autorisées sont en cours. Avant tests sur ce worktree, il faut une autorisation spécifique pour les bases jetables. P5 reste ciblé et n’est pas déclaré globalement accepté. Aucune campagne complète P4/P5, aucun commit, push, merge, déploiement ou opération GitHub.

## Protections

Aucune connexion aux bases conservées, environnements 8001/8003/8004/8005, P405R2, C0/C1/C2/CFINAL ou volume de développement. Secrets non consultés ni copiés. Les fusions P4 #14/#15 et la distinction entre `origin/main` et `main` local restent documentées.
