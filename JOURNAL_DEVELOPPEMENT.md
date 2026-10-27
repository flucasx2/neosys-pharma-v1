A completer.

## 18 octobre 2026 — P5-CONF.1a

Source antérieure récupérée : `JOURNAL_DEVELOPPEMENT(1).md`, dont le seul contenu était la première ligne ci-dessus. Aucun historique détaillé n'a été reconstitué.

- Réception et vérification du bundle complet au commit Windows `5ad489ccb2ccac4c511cda9b1a87104245ddab28`. Travail dans une nouvelle copie locale sur `feat/p5-administration-tiers-payants`.
- Sous-lot livré : administration autonome des organismes, CRUD sans suppression physique, filtres/recherche/pagination, permission explicite non attribuée, révisions/idempotence/audit. Réutilisation des modèles P4-B/P5-A.
- Migration additive `20261018_01` après `20261017_03` (permission seule). Migration préparatoire `20261017_04` non appliquée.
- Patch préparatoire examiné : applicable après normalisation des fins de ligne, mais configuration non raccordée à la vente, contrôles de format/imports/pièces encore incomplets. Différé au prochain sous-lot.
- Validation : 24 tests Python réussis, 1 migration PostgreSQL P4-B ignorée, 1 avertissement de dépréciation; 20 assertions DOM réussies avec HTTP simulé. Pas de PostgreSQL natif ni Chromium exécutable dans Work.
- La revue a corrigé l'état de lecture seule immédiatement après révocation du droit. Les tests ont été ajustés au nouveau nombre de permissions et à la comparaison persistée des conventions.
- Recette générale toujours suspendue. Procédure ciblée : `docs/RECETTE_P5_CONF_1A.md`. Détail : `docs/RESULTATS_P5_CONF_1A.md`. Registre : `docs/REGISTRE_NON_CONFORMITES_P5.md`.
- Prochaine tranche : configuration/documentation versionnée et interfaces de conventions/droits, puis raccordement explicite aux snapshots de vente. Aucun automatisme de confirmation de droits et aucun développement de facturation P5-C.
- Aucun accès Windows, base conservée, push, PR, fusion, activation groupée ou déploiement.


## Complément documentaire fourni — consolidation du 18 octobre 2026

Source : archive de consolidation fournie le 19 octobre ; faits historiques rapportés, pas de nouvelle exécution Work. Le texte suivant est conservé sans remplacer les entrées précédentes.

# JOURNAL_DEVELOPPEMENT — NeoSys Pharma V1

**Mise à jour : 18 octobre 2026**
**Statut : recette humaine interrompue à la demande du responsable projet.**

## Historique consolidé

| Module | Travaux / résultat connu | Suite |
|---|---|---|
| P1 | Organisation, utilisateurs, rôles et permissions déjà réalisés | Préserver |
| P2 | Catalogue, tarifs et catégories existants | Préserver et vérifier intégration fidélité |
| P4 | Vente, clients, encaissements individuels et multiples ; audits antérieurs conservés | Ne pas relancer les audits |
| P5-A | Référentiels organismes, conventions, droits, priorités | Vérifier intégration UI avant recette |
| P5-B | Moteur, intégration vente/encaissement ; tests ciblés rapportés | Recette humaine non clôturée |
| P5-C | Créances, factures, bordereaux et règlements organismes | Développement futur |
| P0/P3/P6–P11 | Référentiel UML conservé | Suivre plan modulaire |

## Recette du 18 octobre 2026 — encaissement multiple

- Capture 194 : deux tickets en attente de 33 800 et 67 600 FCFA.
- Capture 195 : deux tickets sélectionnés ; total 101 400 FCFA ; espèces 90 000, carte 10 000, Airtel Money 500 ; reste 900 FCFA.
- Capture 196 : Airtel Money 1 400 ; total ventilé 101 400 ; reste 0 FCFA.
- Capture 197 : message « 2 ticket(s) encaissé(s) avec succès » ; aucun ticket en attente.
- **Limite** : captures UI uniquement ; pas de vérification indépendante de base, journaux, tickets ou écritures.
- **Décision** : arrêter ici la recette, préserver les preuves, ne pas déclarer P4/P5 intégralement validés.

## Journal des écarts et améliorations

| ID | Nature | Objet | État |
|---|---|---|---|
| REC-01 | Observation antérieure | Rafraîchissement pour débloquer le groupé | À diagnostiquer |
| REC-02 | Observation antérieure | Session / droits incohérents affichés | À diagnostiquer |
| REC-03 | Demande | Simplifier parcours groupé | Parcours plus simple observé ; validation complète non attestée |
| REC-04 | Règle validée | Rendu espèces automatique | À vérifier en recette dédiée |
| REC-05 | Observation | UI de gestion des organismes non trouvée | Intégration à vérifier |
| REC-06 | Demande | Supprimer libellés techniques des écrans métier | À vérifier |
| REC-07 | Observation | Barème parapharmacie 1 point/1000 FCFA configuré | Acquisition réelle à vérifier |
| REC-08 | Demande | Identifiant carte virtuelle généré | À développer/vérifier |
| REC-09 | Demande | Numéro et code-barres carte physique, impression et scan | À développer/vérifier |
| REC-10 | Demande | Clôture X/Z et fidélité | Recette reportée |
| REC-11 | Observation | 2 tickets / 101 400 FCFA, reste 900 puis 0 | Confirmé visuellement |
| REC-12 | Observation | Succès UI, file d’attente vide | Confirmé visuellement |
| REC-13 | Contrôle | Atomicité, allocations, idempotence et reçu par vente | Non vérifié par captures |
| REC-14 | Proposition | Désactivation bouton si reste non nul / aucun ticket | À confirmer techniquement |
| P5-FAC-01 | Exigence validée | Continuité des données couverture → créances et factures | À intégrer P5-C |

## Instructions de développement

Conserver les invariants P4 : une vente / au plus un encaissement, règlements multiples, session de caisse, absence de double encaissement, historiques, retours, clôtures et fidélité. Le ticket récapitulatif ne crée pas de paiement supplémentaire.

Conserver P5 : droits et conventions vérifiés, ordre principal puis complémentaires multiples, reliquat par ligne, parts figées et traçables, refus explicites. Les dossiers de créance et facturation doivent réutiliser les snapshots, documents et références de couverture.

Tests automatiques sur bases jetables, puis recette humaine réelle et validation explicite par module. Aucun merge, publication, migration sur base conservée ou déploiement sans autorisation.

## Documents et preuves

- `NeoSys_Pharma_Referentiel_UML_Complet_2026-10-18.pdf` : référentiel 21 pages conservé + nouvel addendum illustré.
- `REPRISE_NEOSYS_PHARMA.md` : consignes de continuité.
- `captures_recette_encaissement_multiple/` : quatre captures originales.


## 19 octobre 2026 — P5-CONF.1b, incrément conventions et preuves

- P5-CONF.1a accepté par le responsable avec réserve OBS-P5-UI-01 ; résultats Windows 24 tests Python/1 ignoré et 20 assertions DOM/Chromium rapportés dans la nouvelle mission. Bundle complet vérifié à `40c8fb27cca0c9b532d2536e8bb542930dab4452` (après `3186bdf`), nouvelle copie et branche `feat/p5-conf-1b-conventions-baremes`.
- Administration des conventions/régimes embarqués/barèmes existants, bénéficiaires/adhésions/droits, priorités et preuves de vente raccordée aux services réels. Aucun second calculateur.
- Migration additive `20261019_01` après `20261018_01` ; configurations et preuves immuables, FK organisationnelles et liens de vente/bénéficiaire. Pas de migration sur une base conservée.
- Champs/justificatifs obligatoires ou alternatifs, contrôle humain externe déclaré, preuve par vente/bénéficiaire/révision. Métadonnées figées pour P5-FAC-01 ; pas de créance ou facture P5-C.
- Anomalies d'intégration corrigées : libellé produit API `nom`, désignation historique de ligne pour le snapshot, sélection explicite du bénéficiaire/résultat ; nouvelle adhésion à un organisme inactif refusée.
- Résultats et limites exacts : `docs/RESULTATS_P5_CONF_1B.md`. Recette Windows et PostgreSQL jetable : `docs/RECETTE_P5_CONF_1B.md`. Registre existant conservé et complété.
- Plafonds périodiques/individuels consommables, majorations et montants fixes non définis, imports, automatisme multirégime et amélioration des sélecteurs volumineux non livrés. Pas de clôture de P5-CONF.1b ni d'acceptation humaine présumée.
- Aucun accès Windows, publication GitHub, PR, fusion, déploiement ou activation groupée. Les bases P5-CONF.1a/P5-B sont explicitement protégées.

## 19 octobre 2026 — nouvelle méthode et consolidation P4/P5 01

Recettes humaines intermédiaires suspendues ; développement par incréments et recette consolidée finale autorisés. Base P5-CONF.1b vérifiée, pas de reconstruction. Groupe avec organismes : part client seulement, réalisations et fidélité par vente, allocations et remboursements conservés, reçus reliés. Résultats : docs/RESULTATS_P4_P5_01.md. PostgreSQL/Chromium restent non validés ; aucune activation, publication ou base conservée touchée.

## 19 octobre 2026 — consolidation P4/P5 02

- Rendu individuel : la borne HTML empêchait la remise d'espèces supérieure au dû ; correction et test des mouvements nets. Brouillon groupé : proposition explicite du rendu exclusivement espèces, sans toucher à la ventilation manuelle.
- Défaut reproduit en DOM : modifications locales de règlement/ventilation pouvaient laisser la finalisation autorisée sur l'ancien état enregistré. Blocage, message et absence d'appel financier testés avant/après correction.
- Renommage contrôlé de caisse, audit et conflit de libellé, PDF historiques conservés ; identifiant automatique des cartes virtuelles et compatibilité des cartes physiques existantes.
- Résultats : 13 tests Python réussis / 71 désélectionnés ; 19 assertions DOM groupe et 10 formulaires. PostgreSQL/Chromium non exécutés. Détails docs/RESULTATS_P4_P5_02.md.
- Lanceur PostgreSQL neuf et marqué préparé, non exécuté. Aucun effacement de base automatique, aucune modification distante ou Windows.
- Cahier unique docs/RECETTE_CONSOLIDEE_P4_P5.md en cours. Plafonds consommables non codés ; questions contractuelles dans docs/ARBITRAGES_PLAFONDS_P5.md, à trancher avant leurs compteurs.
- P4/P5 non clos. Restent fournisseurs électroniques distincts, cartes physiques numéro/code-barres, imports, sélecteurs volumineux, plafonds et P5-C. Pas d'activation ni d'acceptation humaine présumée.

## 19 octobre 2026 — consolidation 03, moyens configurables

Base ef1256bf et ZIP/bundle revérifiés sans appliquer de patch. Catalogue organisationnel de moyens, identités de fournisseurs figées sur confirmations, UI Caisse/Régularisations/groupe, reçus et X/Z par fournisseur. Remboursements plafonnés par origine ; substitution entre deux fournisseurs sous permission. Migration additive 20261019_02 ; aucune base conservée. Défauts reproduits : solde de retour sans allocations groupées, sélection de restitution perdue au clonage, CHECK anonymes à préserver dans le batch SQLite. Corrections et preuves : docs/RESULTATS_P4_P5_03.md. 12 tests ciblés réussis ; migration 1 réussi/1 natif ignoré ; 36 assertions DOM. PostgreSQL/Chromium non exécutés. Règle historique d'unicité des références par famille conservée et limite explicitée. Poursuite autonome des tâches indépendantes, aucune recette humaine intermédiaire.

## 19 octobre 2026 — consolidation 04, cartes physiques

Numéro/code-barres indépendants, registre d'identifiants unique en base avec reprise des anciens numéros, association contrôlée avant premier document, recherche/scan, PDF figé et réimpression autorisée/auditée. Migration additive 20261019_03 après 20261019_02 ; aucune base conservée touchée. 8 tests ciblés réussis, 1 natif ignoré, 56 désélectionnés ; 17 assertions DOM formulaires, 7 fournisseurs et 19 groupe. Détails et limites techniques d'impression dans docs/RESULTATS_P4_P5_04.md. PostgreSQL/Chromium/matériel non exécutés ; pas de clôture ni d'acceptation humaine présumée.

## 19 octobre 2026 — consolidation 05, bilan import catalogue

Faux message « Import terminé » reproduit sur un inconnu non créé (catégorie/conditionnement manquants) ; fin de pagination confondue avec réussite. Bilan final relit les compteurs serveur, distingue lignes bloquées/ignorées et produits réellement importés. Aucun changement aux prix/stock. Tests : API fictive 1 réussi, régressions import 2 réussies/26 désélectionnées, 6 assertions DOM ; ancien p2.js fait échouer le test, correctif le fait passer. CSV et base réels indisponibles : cause exacte Windows non démontrée, OBS-CAT-01 reste partiellement ouverte. Détails docs/RESULTATS_P4_P5_05.md.

## 19 octobre 2026 — consolidation 06, listes de bénéficiaires

Import CSV/XLSX réel, prévisualisation et confirmation explicite atomique, réutilisation des personnes P5-A. Provenance par organisme/référence, réimport idempotent, rattachement explicite par UUID/révision, aucun rapprochement par nom ni confirmation de droits. Migration additive 20261019_04. Dépendances openpyxl 3.1.5/defusedxml 0.7.1 vérifiées sous Python 3.14.8. Résultats : 11 tests ciblés réussis/1 natif ignoré/12 désélectionnés ; sélection intégrée 19 réussis/4 natifs ignorés. DOM import 10 et conventions 38 réussis ; autres scénarios conservés. Détails docs/RESULTATS_P4_P5_06.md. Les décisions de plafonds sont isolées ; aucune consommation inventée. P5-C autorisé comme suite, pas encore implémenté dans ces quatre incréments. Recette humaine unique inchangée ; aucune attente d'acceptation intermédiaire.

## 19 octobre 2026 — consolidation 07, compatibilité et CI préparée

Noms de champs historiques de confirmation/remboursement conservés, assertions DOM supplémentaires. Ancien test migration P5-CONF.1b réellement en échec sur le jalon dépassé : passage au head avant command.check, cycle et assertions conservés, test repassé. Troncature du numéro de carte long reproduite puis corrigée sans perte d'identifiant ; 4 tests cartes réussis. CI locale préparée : PostgreSQL 17/18, bases marquées séparées, tests natifs non exclus et synthèse conservatrice ; 48 tests du contrôleur réussis. Aucun run distant, aucune preuve native/Chromium réelle. État global et suite autorisée : docs/ETAT_P4_P5_03_07.md. P5-C reste à développer ; aucune recette humaine intermédiaire requise.

## 19/10/2026 — P5-C.1, créances et P5-FAC-02

Base exacte ba570569 récupérée par bundles dans une copie isolée après disparition du worktree initial. Constitution par organisme depuis les réalisations confirmées, journal financier immuable, versions administratives, permissions, écran intégré et garde d'engagement avant facturation. Migration additive 20261019_05. Résultats et limites : docs/RESULTATS_P5_C_1.md. Aucune publication ni migration conservée ; pas d'activation du groupe ; pas de recette humaine intermédiaire. Les régularisations de créances et modules de facturation ne sont pas simulés.

## 19/10/2026 — P5-C.2, documents organismes

P5-C.1 b8ddf845 et son arbre vérifiés via livraison/bundle ; branche isolée work/p5-c-2-facturation créée, aucun patch réappliqué. Préparations versionnées, engagements exclusifs, contrôles FAC-02, bordereaux/factures de recette, PDF historiques en base, récapitulatifs/lots facultatifs, permissions/API/écran intégré. Migration additive 20261019_06 (huit tables), après 05. Émission de production fermée faute de politique fiscale/numérotation et preuves natives ; garde explicite de recette jetable côté serveur. Retour post-facture accepté dans un récapitulatif reproduit puis corrigé, garde aussi appliqué au lot. Campagne ciblée 24 réussis/9 natifs ignorés ; contrôles ultérieurs 64 bits/migration 2 réussis/1 ignoré, traçabilité 2 réussis, nominal final 1 réussi, 48 tests de politique et 27 assertions DOM C2 réussis. Chromium absent. Aucun test natif ni run GitHub exécuté. Voir docs/RESULTATS_P5_C_2.md ; les campagnes successives ne sont pas additionnées en tests distincts. La campagne humaine unique est enrichie, sans demande de validation intermédiaire.


## 27 octobre 2026 — stabilisation globale et décision de clôture P4 / gel P5

Entrée par Codex à 2026-10-27T12:49:14 (Africa/Lagos). Décision du propriétaire : finaliser P4/P4-05 ; conserver les développements historiques P5 et leurs commits, geler toute poursuite/activation, ne pas demander une validation exhaustive P5 pour clôturer P4. P4 reste accepté humainement dans son périmètre ; aucune fusion ni aucun déploiement réalisé.

Chromium réel : 20/20 scénarios réussis en trois segments dépendants. SQLite prérequis : 571 réussis/37 ignorés ; PostgreSQL 17 et 18 prérequis : 605 réussis/2 ignorés chacun ; PostgreSQL 17 P4-05 corrigée : 671 réussis/2 ignorés. SQLite et PG18 P4-05 encore en cours à cette entrée. CI locale48/51, gardes8/8. Résultats exacts, sous-tests, causes et limites : [rapport consolidé](docs/STABILISATION_GLOBALE_P4_20261027.md) ; cet état ne vaut pas validation GitHub des futurs SHA.

Causes démontrées : dialogue de paiement/ancien sélecteur, attentes prématurées de callbacks, configuration de fixture et nature manquante du produit synthétique ; période de migration basée sur date.today() après changement de jour ; dépassement GitHub du budget PG20minutes. Candidats : 13 fichiers de tests/fixtures et proposition séparée d'une ligne CI20→30minutes. Aucune règle financière, permission, migration ou dépendance modifiée.

PR #14 : `codex/p4-prerequis-b04`, `c88151d4d5e899c564c8cddb6a8760de3f99875a`, Draft vers `main`. PR #15 : `codex/p4-05-retours-caisse-publication`, `37ed8350bf840e676fc3f4f3cd4fb6f30601c45f`, Draft vers les prérequis. Dernière lecture distante : voir le rapport de stabilisation ; les références locales restent inchangées.

Main : `2910cc60e8c8287a587ce8ff8e3f48c95be1ba39` ; checkout `dev/codex-docker` à `b223ca2c86fe93bac811f3d6e146034dff3c8acf`. Les SHA de publication n'ont pas changé. PR13 inchangée. Les anciens rapports sont conservés. Le bilan [CLOTURE_P4_GEL_P5_20261027.md](docs/CLOTURE_P4_GEL_P5_20261027.md) qualifie l'isolation et les contradictions documentaires.

Autorisations actuelles : terminer les campagnes existantes, analyse et préparation locale, mises à jour cumulatives de suivi. Non autorisés à ce stade : intégration des candidats, commits, push, opérations GitHub, merge, déploiement et activation P5. Préserver toutes bases conservées, ports8001/8003/8004/8005, P405R2 et C0/C1/C2/CFINAL. Arrêter les développements après le bilan consolidé.

### Conservation intégrale de PROGRESS.md avant actualisation

Le texte suivant était l'état courant précédent ; ses incertitudes et actions sont historiques et remplacées par le bilan ci-dessus.

<details><summary>État précédent de PROGRESS.md, conservé sans modification</summary>

# 📁 Suivi du Projet : NeoSys Pharma V1

> Mise à jour : **27 octobre 2026 à 11 h 16 (Libreville, UTC+1)**. Basé sur les échanges, rapports partagés et PR GitHub contrôlées. L'activité locale de Codex non publiée reste inconnue.

## 📌 État Actuel
- **Dernière IA utilisée :** Codex (développement sur Windows) ; ChatGPT (supervision et revue).
- **Dernière mise à jour :** 27/10/2026, 11 h 16 (UTC+1).
- **Phase en cours :** stabilisation globale des tests Chromium pour clôturer l'intégration P4.
- **État métier :** P4 accepté dans le périmètre de recette V1, mais non fusionné dans `main`.
- **P5 :** code historique partiellement présent dans les prérequis, **pas entièrement validé**.
- **Dépôt :** `flucasx2/neosys-pharma-v1` (privé).
- **`main` :** `2910cc60e8c8287a587ce8ff8e3f48c95be1ba39`.
- **PR #14 — prérequis mixtes P4/P5 :** [Draft → main](https://github.com/flucasx2/neosys-pharma-v1/pull/14), SHA `c88151d4d5e899c564c8cddb6a8760de3f99875a`.
- **PR #15 — finalisation P4-05 :** [Draft → branche #14](https://github.com/flucasx2/neosys-pharma-v1/pull/15), SHA `37ed8350bf840e676fc3f4f3cd4fb6f30601c45f`.

## 🎯 Objectif de la Session Précédente
- [x] Publier deux PR Draft avec historique nettoyé, sans les 16 journaux de preuve P5.
- [x] Corriger les sept blocages historiques de tests/migrations avant publication.
- [x] Corriger les harnais UI `cashPay` et `cgRenderReview` (JSDOM et Chromium ciblés).
- [x] Actualiser `browser_p2_complete.py` pour l'import CSV partiel réel (2 lignes importées, 1 invalide après reprise).
- [x] Lancer les deux CI complètes sur les SHA publiés et localiser le nouveau blocage navigateur.
- [ ] Produire **la matrice exhaustive de tous les scénarios Chromium** et un plan de stabilisation consolidé (mission Codex confiée ; livrable local non vérifié).
- [ ] Diagnostiquer le sélecteur caisse `[name=ESPECES]` et les autres scénarios encore masqués par l'arrêt précoce.
- [ ] Obtenir des CI complètes vertes avant toute fusion.

## 🏗️ Architecture & Fichiers Clés Modifiés Récemment
Architecture : **Python/FastAPI, SQLAlchemy, Alembic, PostgreSQL, Web JavaScript**, tests pytest, JSDOM et Playwright/Chromium, GitHub Actions. Séparation domaine/application/infrastructure/présentation.

- `tests/finitions_caisse_ui.cjs` : initialisation du contexte de caisse et tests de confirmation/rendu monnaie.
- `tests/groupe_organismes_ui.cjs` : chargement complet des fonctions financières de `caisse.js` avant l'encaissement groupé.
- `tests/browser_p2_complete.py` : assertions d'un bilan d'importation partielle et compteurs du rapport serveur.
- `tests/browser_caisse.py` : **blocage actuel**, ligne 24 ; le test attend un moyen `ESPECES` dans un dialogue ouvert.
- `caisse.js`, `encaissement_groupe.js` : modules de référence à examiner pour le diagnostic, **pas de changement métier récent autorisé**.
- `.github/workflows/tests.yml` : contrôle des changements, SQLite, PostgreSQL 17/18, Chromium et synthèse. Draft automatique = contrôles légers ; CI complète par `workflow_dispatch`.
- Documents historiques de recette : `docs/PROCES_VERBAL_RECETTE_P4_05.md`, `docs/CHECKPOINT_P405R2_CFINAL.md` (emplacements à vérifier dans le checkout).

## 🚧 Problèmes / Bugs en suspens
1. **Chromium Caisse :** `tests/browser_caisse.py:24`, `Locator.focus: Timeout 30000ms exceeded`, recherche `dialog[open] [name=ESPECES]` ; la cause exacte n'est **pas encore établie** (dialogue, configuration, permission, fixture, sélecteur, erreur réelle).
2. **Dernière CI complète non valide :** [run #14 — 40221467927](https://github.com/flucasx2/neosys-pharma-v1/actions/runs/40221467927) : SQLite OK, browser échec, PostgreSQL 17/18 annulés, synthèse échec. [run #15 — 40221480958](https://github.com/flucasx2/neosys-pharma-v1/actions/runs/40221480958) : SQLite OK, PostgreSQL 17 OK, PostgreSQL 18 annulé, browser échec, synthèse échec.
3. **Scénarios masqués :** le job Chromium s'arrête au premier échec ; les parcours ultérieurs ne sont pas tous attestés.
4. **PR #13 historique** : modèle concurrent d'encaissement groupé `eg32/eg33/eg34` ; ne pas fusionner/cherry-pick globalement ses migrations.
5. **Reportés à fin V1 :** clôture Z forcée/exceptionnelle, tickets 80 mm, harmonisation et pagination de PDF ; ne pas les présenter comme déjà livrés.

## 🚀 Prochaines Étapes Immédiates
1. Rechercher dans les dossiers locaux de Codex la **matrice globale Chromium** et le **plan de stabilisation** éventuellement déjà produits.
2. Inventorier tous les tests, dépendances, fixtures, seeds et états de données ; distinguer scénarios indépendants et séquentiels.
3. Reproduire sur navigateur réel et PostgreSQL **jetable** le blocage `browser_caisse.py:24` ; recueillir DOM, réseau et configuration des moyens de paiement ; démontrer la cause.
4. Préparer une **seule série de corrections groupées** des tests/harnais. Tout changement métier, financier, de permissions ou migration requiert un accord distinct.
5. Faire une campagne de stabilisation complète avant nouveau push, puis CI complète sur les nouveaux SHA (SQLite, PostgreSQL 17/18, Chromium et synthèse).
6. Revoir puis éventuellement fusionner **#14 avant #15**, uniquement sur autorisation explicite et après succès de tous les contrôles obligatoires.

## 🛡️ Protections non négociables
- Ne pas toucher aux bases conservées, environnements **8001/8003/8004/8005**, sauvegardes **C0/C1/C2/CFINAL**, pièces P405R2 ni aux données financières de recette.
- Bases de tests : PostgreSQL **jetable, nommé, vérifié vide et isolé** ; jamais les bases Windows conservées.
- Aucun push, force-push, merge, déploiement, migration réelle ni nouveau P5 sans autorisation explicite.
- PR #14 et #15 maintenues **Draft** ; pas de « GO merge » sur une suite partielle ou des jobs annulés.

</details>


### 27 octobre 2026, 13 h 02 — complément de consolidation

SQLite P4-05 finale terminée : 629 tests réussis, 44 ignorés historiques, 17 sous-tests séparés ; code de sortie0, XML complet. PostgreSQL18 P4-05 reste en cours. Les contrôles de conservation documentaire et Gitleaks des sept documents ont réussi (zéro détection).

Différence de références constatée : main local fe53c42dc89d79618290b182aae29b01d8cb42d6 (dernier mouvement reflog du10octobre), origin/main et base GitHub2910cc60e8c8287a587ce8ff8e3f48c95be1ba39. Aucun mouvement Git effectué. Le contrôle d’égalité reste en échec explicite ; la revue automatique a refusé une adaptation de l’audit pour accepter cette différence, au motif du risque de masquer une divergence. Aucune tentative de contournement, aucune intégration/publication autorisée par ce complément. Les deux PR sont confirmées ouvertes en Draft aux SHA attendus ; PR15 vise toujours PR14.


## 27 octobre 2026 — bilan local final P4 et arrêt des développements

Horodatage : 2026-10-27T13:43:16 (Africa/Lagos), Codex. Toutes les suites locales requises sont terminées avec succès et codes de sortie0 ; stabilité des serveurs natifs vérifiée. Résultats non additionnés entre campagnes :

- sqlite-final/prerequis : 571 passed, 37 skipped, 1 warning, 3 subtests passed in 3975.70s (1:06:15)
- sqlite-final/p405 : 629 passed, 44 skipped, 1 warning, 17 subtests passed in 4638.41s (1:17:18)
- fullpg17r2/prerequis : 605 passed, 2 skipped, 1 warning, 3 subtests passed in 5146.64s (1:25:46)
- fullpg17r3/p405 : 671 passed, 2 skipped, 1 warning, 17 subtests passed in 8168.55s (2:16:08)
- fullpg18r2/prerequis : 605 passed, 2 skipped, 1 warning, 3 subtests passed in 7132.81s (1:58:52)
- fullpg18r2/p405 : 671 passed, 2 skipped, 1 warning, 17 subtests passed in 6891.86s (1:54:51)

Chromium20/20, CI48/51, gardes8/8 conservés. Les tests ignorés historiques sont qualifiés dans le rapport ; aucune assertion affaiblie, aucun skip ajouté. P4 reste accepté humainement, non fusionné/non déployé ; P5 historique gelé et incomplet. Les développements s’arrêtent ici. Les branches publiables restent aux SHA c88151d4d5e899c564c8cddb6a8760de3f99875a et37ed8350bf840e676fc3f4f3cd4fb6f30601c45f, sans nouveau commit ni push.

GO technique local du périmètre candidat, pas autorisation d’intégration/publication. Le contrôle d’égalité main local/origin reste en échec explicite et nécessite une décision de référence ; aucune synchronisation effectuée. Attendre les autorisations pour intégrer/committer, publier puis opérations GitHub. Ne pas relancer une recette P5 exhaustive pour clôturer P4. Voir docs/CLOTURE_P4_GEL_P5_20261027.md et docs/STABILISATION_GLOBALE_P4_20261027.md.


## 27 octobre 2026 — décision du propriétaire sur les références Git

Horodatage : 2026-10-27T14:02:19 (Africa/Lagos), Codex. Référence officielle de publication : origin/main à2910cc60e8c8287a587ce8ff8e3f48c95be1ba39 ; main local conservé àfe53c42dc89d79618290b182aae29b01d8cb42d6, interdiction de modification/réinitialisation/fusion/synchronisation automatique. La divergence devient une anomalie connue et documentée. Les preuves locales du candidat sont acceptées ; périmètre13 tests/fixtures, une ligne CI et documents de suivi, sans changement métier/migrations/règles financières ; P5 historique conservé et gelé.

Lecture GitHub à nouveau effectuée : main distant attendu, PR14 ouverte Draft sur main attendu, PR15 ouverte Draft sur la branche des prérequis ; SHA inchangés. Autorisation courante limitée à finaliser la préparation et proposer les commits et contrôles. L’ancien audit reste inchangé et son échec est conservé ; une adaptation ciblée contrôlant séparément les deux références est proposée, pas appliquée. Aucun commit, merge, push, déploiement ou intervention sur les environnements conservés. Attendre l’autorisation du plan avant exécution.
