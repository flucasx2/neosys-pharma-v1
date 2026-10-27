# Suivi du projet — NeoSys Pharma V1

Dernière mise à jour : 2026-10-27T14:02:19 (Africa/Lagos, UTC+1). Dernière IA : Codex.

## État courant

- Phase : préparation finale du plan d’intégration P4/P4-05 ; campagnes locales acceptées, autorisation de commits attendue.
- P4 : périmètre métier accepté en recette humaine selon la décision du propriétaire ; aucune nouvelle recette humaine ouverte. P4-05 couvre retours, annulations, réception et états de caisse. Non fusionné, non déployé.
- P5 : développement historique gelé, validation incomplète ; conservation du code et des commits, aucune activation ni nouvelle validation fonctionnelle exhaustive demandée pour clôturer P4.
- Checkout exclusif : `dev/codex-docker`, HEAD `b223ca2c86fe93bac811f3d6e146034dff3c8acf` ; correctifs techniques préparés hors arbre suivi, aucun nouveau commit.
- Base GitHub et `origin/main` : `2910cc60e8c8287a587ce8ff8e3f48c95be1ba39`. `main` local : `fe53c42dc89d79618290b182aae29b01d8cb42d6`, dernier mouvement au 10 octobre selon reflog ; aucune synchronisation effectuée. Différence officiellement acceptée comme anomalie connue. L'ancien audit reste inchangé avec son échec ; le contrôle distinct des deux SHA est proposé, pas appliqué.
- PR #14 : `codex/p4-prerequis-b04`, `c88151d4d5e899c564c8cddb6a8760de3f99875a`, Draft vers `main`. PR #15 : `codex/p4-05-retours-caisse-publication`, `37ed8350bf840e676fc3f4f3cd4fb6f30601c45f`, Draft vers les prérequis. Dernière lecture distante : voir le rapport de stabilisation ; les références locales restent inchangées.

## Vérifications et blocages

Les résultats exacts, mises à jour et preuves sont centralisés dans le [rapport consolidé](docs/STABILISATION_GLOBALE_P4_20261027.md), sans additionner les campagnes qui se recouvrent.

- Chromium réel : 20/20 scénarios, en trois segments dépendants sur bases PostgreSQL jetables ; pas une exécution monolithique GitHub.
- Prérequis complets : SQLite 571 réussis/37 ignorés ; PostgreSQL 17 et 18 chacun 605 réussis/2 ignorés.
- P4-05 PostgreSQL 17 corrigée : 671 réussis/2 ignorés. SQLite P4-05 finale : 629 réussis/44 ignorés, code de sortie0 et XML complet. PostgreSQL 18 P4-05 également terminée, code0 et serveur stable : 671 passed, 2 skipped, 1 warning, 17 subtests passed in 6891.86s (1:54:51).
- Politique CI : 48/48 prérequis, 51/51 P4-05 ; gardes : 8/8. Ces contrôles locaux ne valident pas les futurs SHA distants.
- Cause Caisse démontrée : sélecteur d'un dialogue obsolète ; synchronisations de callbacks, configuration de harnais et nature du produit synthétique corrigées dans les candidats. Aucun changement financier.
- Cycle de migration : fixture de période dépendant du jour courant, corrigée et régression de changement de jour reproduite ; règles de période conservées.
- GitHub : dernières campagnes complètes non vertes ; dépassements explicites de la limite PostgreSQL de 20 minutes. Proposition CI séparée 20→30 minutes, non intégrée.
- PR #13 : inchangée ; ne pas importer ses migrations ou son ancien encaissement groupé.

## Prochaines actions autorisées

1. Toutes les suites locales requises sont terminées, réussies et acceptées par le propriétaire. Conserver les preuves ; aucune nouvelle campagne exploratoire. Présenter le plan final de commits et l’adaptation proposée de l’audit pour autorisation avant exécution.
2. Lire [l'isolation P5 et le bilan de clôture](docs/CLOTURE_P4_GEL_P5_20261027.md) ; conserver les dépendances techniques, ne pas activer P5.
3. Présenter les corrections et les documents au propriétaire, puis arrêter les développements. Intégration, commits, push et opérations GitHub attendent les autorisations distinctes.

## Protections

Lire AGENTS.md avant toute action. Aucune connexion aux bases PostgreSQL Windows conservées, ni modification de P405R2, des ports 8001/8003/8004/8005 ou de C0/C1/C2/CFINAL. Aucun secret réel lu, affiché ou versionné ; aucune migration de base conservée. Aucun merge, déploiement ou nouveau P5.

L'état précédent de PROGRESS.md et ses décisions sont conservés intégralement dans JOURNAL_DEVELOPPEMENT.md, entrée du 27 octobre 2026. Les rapports historiques restent inchangés.
