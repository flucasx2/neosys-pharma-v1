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
