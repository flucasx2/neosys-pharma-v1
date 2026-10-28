# Suivi du projet — NeoSys Pharma V1

Dernière mise à jour : 2026-10-28. Dernière IA : Codex.

## État courant

- Travail ciblé P5-C1 / REG-01 dans le worktree `codex/p5-c1-regularisation`, branche issue du commit `origin/main` `69d02c479e20836e8b152f37eadffc7d01ac4c53` (fusion P5 Neutralité #17 confirmée).
- Ajout local préparé : registre compensatoire append-only pour les retours non engagés présentant une ventilation historique par organisme univoque; migration additive `20261028_02` après `20261028_01`. P5-C2 consomme le solde effectif dans les snapshots et lignes documentaires.
- Fichiers/fonctionnement et cas toujours bloqués : `docs/P5_C1_REGULARISATION_20261028.md`.
- Aucune migration n'a été appliquée et aucun test avec base n'a été exécuté. Tests domaine/API/migration préparés; le Python système ne fournit ni pytest ni alembic. Validation SQLite/PostgreSQL reste requise.

## Vérifications et limites

- Pas de changement P4. Montant/snapshot initial de créance conservé; pas de report automatique client.
- Cas multi-organismes, historiques incomplets/incohérents, créances engagées/présentées/facturées, avoirs fiscaux, rejets et annulations documentaires restent bloqués.
- Aucune connexion aux bases conservées, environnements 8001/8003/8004/8005, P405R2, C0/C1/C2/CFINAL ou volume de développement. Secrets non consultés.
- P4 #14/#15 et leur base Git sont conservés; aucun commit, push, merge ou déploiement.

## Suite autorisée

Attendre une autorisation distincte avant recette technique sur bases jetables. Ne pas lancer de campagne générale P4/P5. Les preuves et les décisions précédentes sont archivées dans `JOURNAL_DEVELOPPEMENT.md`; continuité dans `REPRISE_NEOSYS_PHARMA.md`.
