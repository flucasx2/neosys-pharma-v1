> Instruction courante du 19/10 : poursuivre les incréments P4/P5 sans recette humaine intermédiaire. Recette consolidée après complétude technique. Les anciennes demandes d'attente de recette ci-dessous sont historiques et remplacées par cette décision.

> Reprise courante au 19 octobre 2026 : P5-CONF.1a accepté avec réserve ; livraison locale partielle P5-CONF.1b. Voir la dernière section et `docs/RESULTATS_P5_CONF_1B.md`. Les sections historiques restent conservées.

# NeoSys Pharma V1 — Dossier de continuité

> Actualisation du 18 octobre 2026 : la section 8 complète et remplace les instructions de prochaine action des sections 6 et 7. Les informations historiques ci-dessous sont conservées; elles ne constituent pas une preuve d'accès à Windows depuis Work.

**Dernière mise à jour historique :** 17 octobre 2026
**Objectif :** permettre la reprise du développement et des recettes sans perdre les décisions ni recommencer les travaux validés.

## 1. Objectif du logiciel

Développer une application professionnelle complète de gestion de pharmacie et parapharmacie, adaptée notamment aux besoins du Gabon.

Architecture : Python, FastAPI, PostgreSQL, SQLAlchemy, Alembic, organisation en couches `domain`, `application`, `infrastructure`, `presentation`.

Dépôt GitHub privé : `flucasx2/neosys-pharma-v1`.

Ce projet n'est pas un simple prototype ou une démonstration.

## 2. Méthode de travail obligatoire

- Respecter le cahier des charges et le référentiel UML consolidé.
- Conserver les modules et décisions déjà validés.
- Développer module par module.
- Effectuer les tests automatisés puis les tests humains sur l'application réelle.
- Corriger les anomalies et obtenir une validation explicite avant de clôturer un module.
- Ne jamais modifier une base conservée ou publier sur GitHub sans autorisation appropriée.
- Ne jamais reconstruire des travaux existants sans vérifier les branches, commits et patches.

## 3. État du développement

**P1 :** organisation, sites, emplacements, utilisateurs, rôles, permissions et authentification.

**P2 :** catalogue et tarification.

**P4 :** vente, caisse, clients et encaissement groupé. Conserver les résultats des audits et recettes antérieurs. Vérifier séparément les éventuelles intégrations encore en attente.

**P5-A :** référentiel des organismes, conventions, bénéficiaires et droits.

**P5-B :** moteur de prise en charge, calcul des parts organismes et clients, intégration vente et encaissement. Les tests techniques ciblés P5-B.2 et P5-B.3 ont réussi dans l'environnement local ; la recette humaine reste à effectuer.

**P5-C :** créances, bordereaux, factures et règlements des organismes, à traiter après validation de P5-B.

## 4. Environnement de recette actuel

Répertoire : `D:\Projets_Python\NeoSys_Pharma_P5B_Recette`

Base application : `neosys_p5b_validation_temp`

Base de tests automatisés : `neosys_p5b_pytest_temp`

PostgreSQL : `localhost:5432`

Migration Alembic observée : `20261017_03`

Organisation initialisée : Pharmacie 3 étoiles

Site : `PH3E` — Agence de Libreville

Emplacement : `EMP01` — Réserve 01

Utilisateur : `francis`

Identifiant de l'organisation : `2348606d-89d6-4a1b-956b-0ee3c9a67761`

Application locale : `http://127.0.0.1:8000/`

L'initialisation a affiché « Initialisation terminée ».

Les mots de passe ne doivent jamais être conservés dans ce document.

## 5. Derniers tests connus

- `tests/test_p5b_2_integration_vente.py` : 1 test réussi.
- `tests/test_p5b_3_encaissement_prise_en_charge.py` : 2 tests réussis.
- Avertissement de dépréciation Starlette sans échec de ces tests.
- Connexion PostgreSQL confirmée.
- Base de recette initialisée avec une organisation et un utilisateur.

Ces résultats ne remplacent pas une recette humaine complète.

## 6. Prochaine action (instruction historique, remplacée par la section 8)

Ouvrir l'application locale, se connecter avec l'organisation et l'utilisateur initialisés, puis commencer la recette humaine P5-B.

Vérifier les scénarios de prise en charge, les parts organismes et client, les exclusions, les droits, les priorités et le comportement de l'encaissement.

Documenter les anomalies sans altérer les données historiques.

## 7. Instruction à tout nouvel assistant (complétée par la section 8)

Reprendre à partir de cet état. Demander uniquement les informations manquantes nécessaires, consulter le dépôt et les documents de référence, puis poursuivre la recette humaine P5-B.

Ne pas recommencer les audits P1–P4, ne pas recréer la base, ne pas relancer le bootstrap sur une base déjà initialisée et ne pas annoncer une validation humaine qui n'a pas été effectuée.

Vérifier l'état Git réel avant toute modification ou publication.

## 8. Reprise après suspension de la recette — 18 octobre 2026

Source documentaire historique : `REPRISE_NEOSYS_PHARMA(2).md`. Les résultats Windows des sections précédentes sont rapportés par ce document; Work ne les a pas réexécutés sur Windows.

État Windows reçu et vérifié par bundle : `feat/p5-administration-tiers-payants`, commit `5ad489ccb2ccac4c511cda9b1a87104245ddab28`. Les fichiers non suivis montrés dans la capture sont à conserver et ne font pas partie du bundle. Le patch préparatoire `p5-conf-1.patch` ne fait pas partie de l'état intégré.

Le développement reprend par incréments de mise en conformité, avec le référentiel UML complet du 18/10 et les décisions confirmées. Les priorités restent organisationnelles; aucun organisme principal n'est obligatoire. La recette humaine générale est suspendue.

Sous-lot P5-CONF.1a : Administration → Organismes de prise en charge, réutilisant le modèle existant, avec permission `tiers_payant.organisme.gerer`, audit, édition par révision et rejeu idempotent. Migration `20261018_01` (parent `20261017_03`) limitée au catalogue de permission. Aucune attribution implicite, aucun changement financier.

Preuves Work : 24 tests ciblés réussis, 1 test natif ignoré, 20 assertions DOM avec HTTP simulé. PostgreSQL natif et Chromium ne sont pas validés dans Work. Les rapports, les limites du patch préparatoire et la recette ciblée sont dans `docs/RESULTATS_P5_CONF_1A.md`, `docs/REGISTRE_NON_CONFORMITES_P5.md` et `docs/RECETTE_P5_CONF_1A.md`.

Prochaine action : revue et intégration du sous-lot dans une copie isolée, tests natifs et recette du nouvel écran sur base neuve explicitement jetable. Ne pas migrer les deux bases Windows citées en section 4. Après validation, poursuivre les configurations/documentations et leur raccordement aux ventes; ne pas assimiler cet écran à la clôture de P5 ou au démarrage de P5-C.


## Reprise au 19 octobre 2026 — après l'incrément P5-CONF.1b

Base exacte fournie : branche `recette/p5-conf-1a`, HEAD `40c8fb27cca0c9b532d2536e8bb542930dab4452`, parent applicatif `3186bdf`. Développement dans Work sur `feat/p5-conf-1b-conventions-baremes`, sans modification Windows ou distante.

Le lot local ajoute les conventions configurées, leurs régimes descriptifs et barèmes calculés par P5-B, les écrans de bénéficiaires/adhésions/droits/priorités, les preuves documentaires par vente et leur snapshot immuable. Migration `20261019_01` après `20261018_01`. Le patch préparatoire initial n'a pas été appliqué automatiquement.

Prochaine action : intégrer dans un nouveau worktree et une nouvelle instance PostgreSQL jetable selon `docs/RECETTE_P5_CONF_1B.md`, exécuter le contrôle natif et Chromium puis la recette humaine ciblée. Ne pas reconstruire les versions acceptées. Les travaux restants et arbitrages figurent dans `docs/P5_CONF_1B.md`. L'absence de preuve native/Chromium reste bloquante pour l'acceptation.

Protections supplémentaires : `D:\Projets_Python\NeoSys_P5_CONF_1A` et `neosys_p5conf1a_recette_temp` sont conservés ; pas de migration, suppression, réinitialisation ou réutilisation destructive sans nouvelle autorisation. Bases P5-B, `neosys_pharma_v1` et `neosys_p46_recette_20261012` également protégées. Le script natif refuse toute base préexistante.

P5-CONF.1a est accepté selon la mission du responsable, avec OBS-P5-UI-01 ouverte. La recette générale demeure distincte de la recette ciblée de cette nouvelle livraison ; P5-B complet et P5-C ne sont pas déclarés validés. Aucune publication ou poursuite automatique après cette livraison.


## Suite autorisée — consolidation P4/P5

Branche Work `work/p4-p5-consolidation` depuis `1cc86cee`. P5-CONF.1b présent et sauvegardé ; aucun accès Windows. Priorité à P4 puis P5-CONF/B puis P5-C. Lot 01 : encaissement groupé avec parts clients et organismes, tests ciblés détaillés dans docs/RESULTATS_P4_P5_01.md. Garder le flag fermé et les bases conservées intactes. Les plafonds périodiques exigent un arbitrage avant consommation ; la recette humaine finale est reportée, pas supprimée.

## Reprise après consolidation 02

Branche locale work/p4-p5-consolidation, premier commit ed208094e65594528c0039ce3c91893fa0b3a107 ; deuxième incrément décrit dans docs/RESULTATS_P4_P5_02.md. La branche part de P5-CONF.1b déjà présent, aucun patch ancien à réappliquer.

Poursuivre les travaux indépendants par incréments sans nouvelle recette humaine intermédiaire. Le cahier unique est docs/RECETTE_CONSOLIDEE_P4_P5.md. Les plafonds consommables exigent les décisions de docs/ARBITRAGES_PLAFONDS_P5.md avant tout compteur. Les interfaces P5-C doivent réutiliser les réalisations/snapshots et leurs versions, pas les convertir en créances définitives avant traitement transactionnel.

Les contrôles locaux récents sont SQLite/DOM uniquement. scripts/recette_p4p5_postgresql.ps1 prépare une base neuve marquée et 9 tests ; il ne valide pas les migrations Alembic, qui ont leur lanceur P5-CONF.1b séparé. Aucune base conservée à réutiliser ; pas de lancement PostgreSQL/Chromium attesté. Ne pas activer la finalisation groupée.

## Suite après consolidation 03

Moyens configurables et fournisseurs distincts implémentés : rapport docs/RESULTATS_P4_P5_03.md. Migration courante 20261019_02 après 20261019_01, non exécutée sur base conservée. Ne pas réintroduire des valeurs Airtel/Moov dans MODES : les fournisseurs sont des identités de catalogue, la famille reste MOBILE_MONEY. Les règlements retrouvent l'identité immuable via leur confirmation ; le remboursement explicite source/cible. Limite de références identiques entre fournisseurs conservée volontairement. La validation native/Chromium reste ouverte ; ne pas activer le groupe.

## Suite après consolidation 04

Migration courante 20261019_03 : cartes physiques et registre partagé numéro/code-barres, documents immuables. Le numéro historique n'est ni renommé ni supprimé. On peut associer une fois un code-barres avant le premier document, puis remplacer la carte selon P4 si nécessaire ; ne pas réécrire les identifiants historiques. Rapports docs/RESULTATS_P4_P5_03.md et 04.md ; recette unique toujours différée. Prochaines tâches indépendantes : reproduction PharmaGabon et import bénéficiaires ; les plafonds attendent les arbitrages documentés avant leurs compteurs. Groupe fermé, pas de base conservée.

Consolidation 05 : bilan de l'import catalogue corrigé sans migration ; voir docs/RESULTATS_P4_P5_05.md. Ne pas confondre termine (fin de parcours des lots) avec IMPORTE (création/enrichissement effectif). Ne pas prétendre avoir réparé l'import réel sans son rapport/CSV. Poursuivre les imports de bénéficiaires sous identité de source explicite, sans création automatique de droits.

## Reprise après les incréments 03–06

Base conservée ef1256bf, branche work/p4-p5-consolidation. Trois commits déjà créés : 0af2686 moyens, ac4010c cartes, 84405ed bilan catalogue ; import bénéficiaires décrit dans docs/RESULTATS_P4_P5_06.md. Migration courante 20261019_04 (02 moyens, 03 cartes, 04 import). Recette native et Chromium toujours non exécutée ; ne pas activer le groupe. Rapports par incrément et recette unique mis à jour.

L'import de personnes ne crée pas d'adhésion ou de droits ; poursuivre les liens de couverture existants explicitement. Import modifié sur une référence connue = revue contrôlée, pas d'écrasement. XLSX nécessite les dépendances pyproject mises à jour. Les bases Windows et recettes conservées restent protégées.

La mission courante autorise ensuite P5-C : les anciennes consignes « ne pas commencer P5-C » des sous-lots antérieurs ne sont plus une interdiction générale. Il n'est pas encore livré ici. Réutiliser les réalisations/snapshots confirmés et les documents P5-FAC-01 ; ne pas fabriquer de facture ou créance à partir d'une simulation. Les arbitrages de compteurs plafonds restent préalables à leur implémentation uniquement, pas une raison de reconstruire P4 ni de bloquer les tâches indépendantes. Ne demander aucune recette humaine intermédiaire.

## Reprise après consolidation 07

CI préparée localement : postgres en matrice 17/18, base API neosys_p4p5_ci marquée, migrations et P5-CONF.1b séparées. Ne pas lancer le contrôleur main ancien pour cette branche ; après autorisation de publication, sélectionner son tests.yml et son SHA distant exact. Aucune exécution Actions à ce stade. Sélecteurs historiques Chromium conservés ; scénarios simulés explicitement séparés des parcours réels. 48 tests de politique réussis ; le défaut de test de migration et la troncature du numéro PDF ont été reproduits et corrigés. Voir docs/RESULTATS_P4_P5_07.md et ETAT_P4_P5_03_07.md pour la suite, sans refaire les audits acceptés.

## Reprise après P5-C.1

Copie isolée de travail : branche `work/p5-c-1-creances`, base ba570569bb7063bf587ffac45c3eceff58dea93b. Lire `docs/P5_C_1_CREANCES_UML.md`, `docs/RESULTATS_P5_C_1.md`, le registre des exigences P5-C et les non-conformités. Nouvelle tête Alembic 20261019_05. Réutiliser le commit/bundle et ne pas reconstruire les modules P4/P5-A/B. Patch incrémental uniquement sur ba570569 ; ne pas l'appliquer avec un autre export alternatif de même contenu. Aucun push autorisé. Avant facturation, appeler le garde serveur DANS la transaction ; compléter les ajustements compensatoires de retours avant de pouvoir engager ces créances. Plafonds consommables non arbitrés et incident réel PharmaGabon ouverts. Campagne humaine unique à la fin des développements ; obtenir les preuves PostgreSQL et Chromium manquantes.

## Reprise après P5-C.2

Branche locale `work/p5-c-2-facturation` depuis `b8ddf845695f1e82a8d1cbcf0b06e42824bf2133`. Retrouver le SHA final dans le manifeste de livraison et le bundle complet ; ne pas appliquer le patch en plus du bundle. Migration tête `20261019_06` après 05, uniquement sur base jetable neuve. Lire docs/P5_C_2_DOCUMENTS_ORGANISMES.md, RESULTATS_P5_C_2.md et PROCEDURE_P5_C_2.md. Les nouvelles permissions n'ont pas d'attributions implicites.

La préparation documentaire, les contrôles serveur, l'historique et les PDF de recette existent. L'émission de production reste fermée ; références de recette manuelles uniquement en contexte PostgreSQL CI jetable marqué et confirmé, aucune numérotation fiscale inventée. Un retour bloque émission et nouveaux regroupements, y compris après facture ; aucun avoir ni montant source réécrit. Représentations/rejets et règlements restent à traiter séparément. Ne pas confondre les PDF d'exemple fictifs du ZIP avec une facture exploitable fiscalement.

Avant toute clôture : exécuter tests natifs de migration/contraintes/concurrence et navigateur réel, arbitrer numérotation/conformité/période. Le workflow 17/18 et le script local sont préparés sans publication. PharmaGabon réel et plafonds consommables restent ouverts. Ne demander aucune recette humaine intermédiaire ; conserver/enrichir la campagne unique finale. Aucun changement de vente/caisse, aucune activation du groupe ni base conservée autorisée par cette livraison.
