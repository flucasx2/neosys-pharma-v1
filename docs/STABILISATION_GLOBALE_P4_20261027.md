# Stabilisation globale P4 — 27 octobre 2026

> **Décision du propriétaire — références Git du 27 octobre 2026.** Publication : `origin/main` attendu à `2910cc60e8c8287a587ce8ff8e3f48c95be1ba39`. `main` local conservé à `fe53c42dc89d79618290b182aae29b01d8cb42d6`, aucune synchronisation autorisée. La différence est acceptée comme anomalie connue ; l'ancien audit reste inchangé avec son échec conservé. Adaptation ciblée proposée pour contrôler séparément les deux SHA, à autoriser avant application. Les preuves locales sont acceptées. Préparation du plan de commits uniquement : aucun commit, intégration, merge ou push autorisé à cette étape.

Mise à jour : 2026-10-27T13:44:16, Africa/Lagos.

**Vérifications locales requises réussies ; intégration/commits à autoriser explicitement.** Aucun nouveau commit, SHA de branche, push ou workflow GitHub manuel. Le checkout reste `dev/codex-docker`. P4 conserve son acceptation humaine ; les fonctionnalités P5 historiques restent présentes et non entièrement validées.

## Références préservées

Prérequis : `c88151d4d5e899c564c8cddb6a8760de3f99875a`. P4-05 : `37ed8350bf840e676fc3f4f3cd4fb6f30601c45f`. Main distant et base GitHub : `2910cc60e8c8287a587ce8ff8e3f48c95be1ba39`. Main local : `fe53c42dc89d79618290b182aae29b01d8cb42d6` (dernier mouvement reflog du10octobre). Le contrôle d'égalité reste en échec explicite ; aucune synchronisation effectuée. Voir le bilan de clôture pour cette différence de références et les décisions attendues.

La dernière lecture GitHub confirme les deux PR ouvertes en Draft : PR14 vers main ; PR15 vers les prérequis. Les références originales `codex/p5-phase0-conception` et `codex/p4-05-retours-caisse` sont conservées. Preuve : [remote-references-20261027.json](D:/Projets_Python/NeoSys_Pharma_Dev/.audit-publication/global-stabilization/results/remote-references-20261027.json). Aucun changement de la PR13 ni import de ses migrations ou de son ancien modèle groupé.

## Correctifs locaux préparés

Les patches concernent13 fichiers de tests/fixture :

- `tests/browser_p1.py`
- `tests/browser_p2.py`
- `tests/browser_p2_complete.py`
- `tests/browser_p3.py`
- `tests/browser_etats_p3.py`
- `tests/browser_p4.py`
- `tests/browser_proforma.py`
- `tests/browser_caisse.py`
- `tests/browser_regularisation.py`
- `tests/browser_clients.py`
- `tests/fidelite_historique_ui.cjs`
- `tests/seed_browser_caisse.py`
- `tests/test_p5c2_migration.py`

La proposition séparée de configuration concerne seulement `.github/workflows/tests.yml`, budget du job PostgreSQL de20 à30minutes. Le périmètre total proposé pour intégration est donc14 fichiers. Aucun fichier de production, permission, migration, dépendance ou configuration d’exploitation n’est modifié.

| Cause démontrée | Correction et validation |
|---|---|
| Le dialogue d’administration des moyens n’a pas les cases attendues par l’ancien sélecteur ESPECES. | Naviguer vers les familles, conserver les espèces actives et créer explicitement le moyen CARTE QA. Les paiements individuels/groupés utilisent son UUID réel. Le focus de30s n’est pas augmenté. |
| La fixture fidélité JS omet modes/moyens ; le produit synthétique Caisse n’a pas de nature. | Compléter seulement la configuration du harnais et la nature COSMETIQUE de ce produit de test. Les assertions de points, dette, rendu et permissions restent actives. |
| Les tests lisent la connexion, les formulaires ou les grilles avant la fin des callbacks. | Attendre les vrais états de fin de traitement et réponses HTTP, puis exécuter les assertions historiques. Les erreurs volontaires et les quantités conservées sont toujours vérifiées. Aucun délai fixe n’est ajouté pour masquer le problème. |
| Le remboursement attend mode_CARTE=CARTE alors que le moyen nommé utilise mode_0=CARTE:UUID. | Contrôler la famille, le libellé CARTE QA, l’UUID et le montant du moyen historique renvoyé par le serveur, sa sélection exacte et les espèces séparées. Cette seule assertion de sélecteur est remplacée par des contrôles plus stricts ; les autres assertions sont conservées. |
| Le cycle de migration crée une réalisation un jour puis construit son payload avec date.today() un autre jour. | Ancrer date_debut=date_fin au jour UTC exact de la réalisation. L’ancienne fixture échoue de façon déterministe avec un générateur passé au lendemain ; les deux tests SQLite corrigés passent sur chaque branche et les quatre cycles natifs17/18 passent sans skip. Aucun filtrage métier n’est élargi. |
| Trois jobs GitHub dépassent leur limite globale20minutes. | Annotations explicites de dépassement ; matrice fail-fast:false. Proposition d’une seule ligne20→30minutes, distincte du délai Playwright. Les contrôles48/51 et les huit gardes repassent. Aucun workflow n’est publié ou déclenché. |

Patches applicables aux deux SHA exacts : [prerequis-selected.patch](D:/Projets_Python/NeoSys_Pharma_Dev/.audit-publication/global-stabilization/prerequis-selected.patch) et [p405-selected.patch](D:/Projets_Python/NeoSys_Pharma_Dev/.audit-publication/global-stabilization/p405-selected.patch). La compatibilité Alembic propre à P4-05 est conservée dans son test de migration. Proposition CI séparée : [patch prérequis](D:/Projets_Python/NeoSys_Pharma_Dev/.audit-publication/global-stabilization/proposals/pg-timeout30/prerequis.patch) et [patch P4-05](D:/Projets_Python/NeoSys_Pharma_Dev/.audit-publication/global-stabilization/proposals/pg-timeout30/p405.patch).

## Résultats

| Campagne | Bilan |
|---|---|
| Chromium réel, backend/PostgreSQL17 jetables |20/20 scénarios réussis, hashes des scripts exécutés vérifiés |
| Contrôles CI, fichiers sélectionnés + proposition de budget |48/48 prérequis ;51/51 P4-05 |
| Gardes P4-05 |8/8 |
| Régression de changement de jour — SQLite | Ancienne fixture :1 échec attendu et identifié ; après correction :2/2 sur chaque branche |
| Cycle de migration corrigé — PostgreSQL natif17/18 |4/4, sans skip |
| SQLite finale — prérequis | 571 passed, 37 skipped, 1 warning, 3 subtests passed in 3975.70s (1:06:15) |
| SQLite finale — P4-05 | 629 passed, 44 skipped, 1 warning, 17 subtests passed in 4638.41s (1:17:18) |
| PG17 prérequis — suite initiale complète | 605 passed, 2 skipped, 1 warning, 3 subtests passed in 5146.64s (1:25:46) |
| PG17 P4-05 — suite initiale, avant correction de fixture | 1 failed, 669 passed, 2 skipped, 1 warning, 17 subtests passed in 5789.16s (1:36:29) |
| PG17 P4-05 — suite corrigée complète | 671 passed, 2 skipped, 1 warning, 17 subtests passed in 8168.55s (2:16:08) |
| PG18 prérequis — suite complète | 605 passed, 2 skipped, 1 warning, 3 subtests passed in 7132.81s (1:58:52) |
| PG18 P4-05 — suite corrigée complète | 671 passed, 2 skipped, 1 warning, 17 subtests passed in 6891.86s (1:54:51) |

Les20 parcours Chromium sont exécutés en trois segments de dépendance sur des bases neuves : P1→P2→P2 complet ; P3→États ; P4→Proforma→Caisse→Régularisation→Clients. Cette couverture ne constitue ni une exécution monolithique GitHub ni une nouvelle recette humaine. Les interceptions/fautes réseau historiques des scénarios sont conservées ; les finalisations financières vérifiées utilisent le vrai backend et les vrais comptes. Preuve : [all-browsers-selected20.json](D:/Projets_Python/NeoSys_Pharma_Dev/.audit-publication/global-stabilization/results/all-browsers-selected20.json).

Les bilans pytest ne cumulent pas les subtests avec les tests principaux. Les suites avec fixtures PostgreSQL incluent aussi du domaine pur et des cycles explicitement SQLite ; les validations natives sont distinguées. Les anciens bilans SQLite570/628 restent des résultats de la suite initiale, pas ceux des fichiers finaux. Les skips historiques sont qualifiés : contrôles natifs indisponibles en SQLite, CSV de recette externe, ou copie spécifique SQLite dont le cycle natif est distinct ; aucun skip ajouté pour obtenir du vert.

La première suite P4-05 PG17 a terminé avec1 échec/669 réussis : le seul échec était le cycle SQLite de migration ci-dessus. Lecture seule de son fichier jetable : réalisation du26octobre20:10:09.629474UTC, période construite ensuite avec la date du27. Le service a correctement refusé la sélection. L’échec et sa reproduction sont conservés, sans les requalifier en réussite de suite complète. Preuves : [observed-original-realisation.json](D:/Projets_Python/NeoSys_Pharma_Dev/.audit-publication/global-stabilization/results/migration-day-boundary/observed-original-realisation.json), [p405-before.log](D:/Projets_Python/NeoSys_Pharma_Dev/.audit-publication/global-stabilization/results/migration-day-boundary/p405-before.log), [complete.json](D:/Projets_Python/NeoSys_Pharma_Dev/.audit-publication/global-stabilization/results/migration-day-native/complete.json).

Les logs GitHub montrent aussi des résumés pytest réussis dans deux jobs annulés à20minutes. Ils restent des jobs annulés. Seul le job PostgreSQL17 P4-05 du run40221480958 est success sur le SHA original. Preuve structurée : [github-pg-timeouts-20261027.json](D:/Projets_Python/NeoSys_Pharma_Dev/.audit-publication/global-stabilization/results/github-pg-timeouts-20261027.json).

## Audit et protections

Comparaison intégrale avec les archives Git des arbres validés :311 fichiers suivis côtéprérequis et328 côtéP4-05 ; seuls les13 fichiers sélectionnés de tests diffèrent, aucun fichier supplémentaire. Les assertions sont contrôlées par AST et les patches par index Git temporaires, sans modifier l’index actif. Preuve : [whole-candidate-audit-linux20.json](D:/Projets_Python/NeoSys_Pharma_Dev/.audit-publication/global-stabilization/results/whole-candidate-audit-linux20.json).

Gitleaks8.30.1 : zéro détection dans les fichiers sélectionnés et les deux historiques publiables précédemment audités (135/140 commits, références inchangées). Les seize journaux exclus ne sont pas réintroduits. Aucun fichier.env réel ni secret Compose n’est versionné. Les preuves d’audit restent hors du périmètre de publication.

Aucune intervention sur les bases PostgreSQL Windows conservées, P405R2, ports8001/8003/8004/8005 ou sauvegardes C0/C1/C2/CFINAL. Les tests utilisent des instances Docker jetables, réseaux internes sans port PostgreSQL publié, rôles dédiés et marqueurs/vacuité vérifiés avant migration. Les seuls nettoyages concernent ces projets d’audit terminés, sans suppression de volume conservé ni purge globale.

## Intégration et suite à donner

Faire valider le périmètre technique14 fichiers et les sept documents de suivi explicitement listés dans docs/CLOTURE_P4_GEL_P5_20261027.md avant toute intégration ou commit. Clarifier le contrôle des références locales/distantes sans synchronisation automatique. Les campagnes locales sont terminées lorsque le verdict en tête le confirme ; ne pas les relancer sans cause démontrée. Après autorisation distincte, préparer des commits séparés pour tests, configuration CI et documentation, puis propager aux P4-05 par intégration Git standard avec résolution explicite de la compatibilité de migration. Conserver tous les commits existants et la base PR15→PR14, sans duplication des correctifs communs ni réécriture d’historique. P5 historique gelé et incomplet ; arrêter les développements après ce bilan.

Aucun push automatique. Une autorisation distincte restera nécessaire pour publier les nouvelles têtes, puis pour les éventuelles campagnes manuelles sur leurs SHA distants exacts. Aucun GO de fusion ou passage Ready for Review avant réussite de tous les jobs obligatoires sur ces SHA.
