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
