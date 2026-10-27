# P5-CONF.1b — Conventions configurées et preuves de vente

Date : 19 octobre 2026. Base : `40c8fb27cca0c9b532d2536e8bb542930dab4452`, branche fournie `recette/p5-conf-1a`, historique complet du bundle vérifié. Développement isolé sur `feat/p5-conf-1b-conventions-baremes`. Aucun accès au poste Windows ni à ses bases.

Cette livraison implémente un incrément exploitable de P5-CONF.1b. Elle ne clôture pas l'ensemble du périmètre : plafonds individuels/périodiques consommables, imports, majorations et sélection automatique multirégime restent ouverts. La recette humaine est indispensable.

## Sources et écarts ciblés

Référentiel complet du 18/10/2026 (section 7.6 et P5-FAC-01), mission du 19/10 et code du bundle. Les documents du dossier de consolidation sont conservés dans les documents de continuité. Les décisions confirmées principale facultative / priorités communes à l'organisation prévalent sur les anciens paragraphes encore marqués à arbitrer.

| Fonctionnalité | Existant constaté | Manquant à la base | Travail livré | Risque / statut |
|---|---|---|---|---|
| [V] Organismes autonomes | P5-CONF.1a accepté, avec réserve UI | Aucune reprise nécessaire | Références réutilisées, accès aux conventions depuis la fiche | Acceptation antérieure rapportée, pas de nouvelle clôture |
| [R,V] Conventions | Modèle immuable, versions, périodes, API et audit P5-A | Administration graphique | Liste paginée, consultation, création et nouvelle version avec contrôle de version attendue | Version active de même code non chevauchante ; convention ouverte ne peut être remplacée silencieusement |
| [R,DEM] Régimes | Aucun objet dédié dans le calcul | Identité du régime attachée à la convention | Valeur code/libellé figée avec chaque convention configurée | Un régime par version ; routage automatique selon plusieurs régimes non implémenté |
| [V] Barèmes | Projection stricte P5-B : fraction exacte, arrondi, plafond par ligne, produit/catégorie/exclusions | Saisie métier | Formulaire sans JSON technique, plusieurs règles disjointes, recherche catalogue sous sa permission | Aucun taux ou arrondi implicite ; catégorie exacte, sans extension automatique aux sous-catégories |
| [R,A] Plafonds individuels/périodiques | Pas de registre de consommation | Règles de période/cumul/annulation non définies | Clauses inconnues refusées ; seul plafond par ligne existant exposé | Non livré, aucune consommation financière simulée |
| [V] Bénéficiaires et droits | Entités P5-A distinctes de fidélité ; adhésions/titulaire/ayants droit ; révision | Écrans | Recherche, création, adhésions, décision de droits et référence explicites, suspension | Pas d'import CSV/Excel ; données de liste saisies manuellement |
| [V,DEM] Modes et justificatifs | Patch préparatoire non intégré, pas de preuve liée à la vente | Configuration et preuve versionnées | LISTE / IDENTIFICATION / EXTERNE / MIXTE, champs typés, formats explicites, pièces cumulatives ou alternatives | Vérification humaine déclarée ; aucune connexion à un portail |
| [V] P5-FAC-01 | Snapshots financiers P5-B immuables | Identité/régime/preuves documentaires | Dossier documentaire figé par vente/bénéficiaire dans les snapshots, référence et auteur conservés | Métadonnées uniquement, pas de stockage des scans ni facturation P5-C |
| [V] Principal et complémentaires | Ordre P5-A, principal facultatif, moteur séquentiel | Paramétrage graphique | Ordre explicite de plusieurs organismes via les priorités existantes | Pas de libre réordonnancement par vendeur ; limites de chargement UI ci-dessous |
| [OBS] OBS-P5-UI-01 | Messages de confirmation persistants signalés | Correction ergonomique indépendante | Observation conservée ouverte ; pas de réécriture de l'écran accepté | Non bloquant pour le lot, non déclaré résolu |

## Modèle UML et persistance

| Entité / objet | Champs significatifs | Relations et garanties |
|---|---|---|
| OrganismePriseEnCharge existant | id, organisation, code, nom, actif, révision | 1 → 0..* ConventionOrganisme ; aucune duplication |
| ConventionOrganisme existante | code/version, période inclusive, statut, conditions, extensions | Immuable ; version/code/organisation/organisme uniques ; P5-B reste calculateur unique |
| ConfigurationConvention (nouvelle) | id, organisation, convention, schema_version=1, définition, auteur, création | Convention 1 → 0..1 configuration ; création atomique avec la convention ; FK organisationnelles ; immuable |
| Régime (valeur embarquée) | code, libellé | Configuration 1 → 0..1 régime ; pas de nouvelle identité globale ou de calcul multirégime inventé |
| Champ / document requis (valeurs embarquées) | code, libellé, type, obligatoire, format / groupe alternatif | Configuration 1 → 0..* champs et documents ; codes uniques ; schéma strict |
| Adhésion / lien bénéficiaire existants | convention, titulaire, période, révision, droits, relation | Réutilisés ; clé composite additive id/organisation/convention protège les preuves |
| VérificationConvention (nouvelle) | vente/site, configuration/convention, adhésion/révision, bénéficiaire, source, référence, résultat, motif, période, valeurs/pièces, auteur | Vente 1 → 0..* preuves ; FK vers configuration, adhésion compatible, lien bénéficiaire, vente/site/organisation et auteur ; immuable |
| Snapshot financier existant | étapes, montants, snapshot_droits, hash | Chaque étape conserve `dossier_documentaire_json` canonique si une preuve configurée existe ; historique non recalculé |

Migration additive `20261019_01` après `20261018_01` : deux tables, contraintes et index, clé composite supplémentaire sur les adhésions. Triggers UPDATE/DELETE immuables pour PostgreSQL et SQLite. Aucune migration historique réécrite, aucune permission nouvelle ou affectation implicite. Le downgrade vérifie l'absence de configurations/preuves avant suppression ; toute présence provoque un refus conservateur.

## Contrats applicatifs

Préfixe : `/api/tiers-payants/organisations/{organisation_id}`.

| Opération | Route | Permissions serveur |
|---|---|---|
| Créer convention + configuration atomiques | POST `/conventions-configurees` | `tiers_payant.convention.gerer` |
| Consulter version et configuration | GET `/conventions/{id}` | `tiers_payant.consulter` ou `tiers_payant.convention.gerer` |
| Rechercher bénéficiaires | GET `/beneficiaires?q=...` | `tiers_payant.adhesion.consulter` |
| Filtrer adhésions | GET `/adhesions?convention_id=...&q=...` | `tiers_payant.adhesion.consulter` |
| Enregistrer preuve immuable de vente | POST `/ventes/{id}/verifications` | `tiers_payant.adhesion.gerer` ET `vente.consulter`, dans le contexte et l'emplacement de la vente |
| Consulter preuves | GET `/ventes/{id}/verifications` | `tiers_payant.adhesion.consulter` ET `vente.consulter` |

Les routes de création/gestion de bénéficiaires, adhésions, droits et priorités P5-A sont réutilisées. Les mutations utilisent la transaction et la clé d'idempotence existantes de `StockService.operation` ; la clé est conservée au rejeu réseau d'une saisie identique. Le verrou d'organisation sérialise les mutations ; révision organisme, version attendue et révision adhésion détectent les conflits. Le refus 409 ne provoque aucun écrasement silencieux. CSRF et contrôles organisation/site/emplacement restent actifs.

Configuration : régime facultatif, types de bénéficiaires explicites, modes limités aux valeurs documentées, champs TEXTE/ENTIER/DATE, formats CHIFFRES/ALPHANUMERIQUE facultatifs pour TEXTE. Les pièces obligatoires sans groupe sont cumulatives ; chaque groupe alternatif exige au moins une pièce effectivement contrôlée. Le résultat de preuve et son bénéficiaire nécessitent un choix explicite dans l'interface. La période de preuve est saisie explicitement, comprise dans les périodes de convention/adhésion/lien. Aucune durée n'est déduite arbitrairement.

La preuve ne confirme jamais les droits P5-A implicitement. Un changement de révision d'adhésion impose une nouvelle preuve. Une preuve ne s'applique ni à une autre vente, ni à un autre bénéficiaire, ni à une autre convention. La dernière preuve enregistrée prévaut ; une preuve expirée ne réactive pas une ancienne preuve favorable. Un refus contractuel prouvé est tracé, tandis qu'une information manquante bloque le calcul. Les preuves sont refusées après confirmation financière de la vente.

Les conventions historiques sans configuration conservent leur interprétation P5-B et leur snapshot. L'interface ne les convertit pas automatiquement : les clauses historiques non calculables doivent être reprises explicitement. Les nouvelles conventions configurées sont validées par `projeter_convention`, puis calculées par le moteur existant. Un champ financier inconnu ou des barèmes potentiellement recouvrants sont refusés.

## Limites et décisions nécessaires

- [A] Plafonds individuels/périodiques, consommation et restitution : période, unité de cumul, compteur partagé ou non, ordre, franchises et effets des retours à définir avant un registre transactionnel. Aucun compteur provisoire n'est présenté comme définitif.
- [A] Montants fixes, majorations selon affection, exceptions prioritaires et groupes autres que la catégorie exacte : règles de combinaison manquantes ; non ajoutés au calcul. Les clauses non prises en charge restent bloquantes.
- [A] Remplacement d'une convention active sans fin : les versions existantes sont immuables. Pas de fermeture rétroactive automatique. La présente interface crée des versions non chevauchantes ; définir une politique de succession et de migration des adhésions/priorités avant d'étendre ce cas.
- [P] Le régime est figé par convention ; plusieurs conventions d'un organisme sont possibles, mais le paramétrage P5-A sélectionne une convention à chaque rang. Pas de sélection automatique de régime selon le bénéficiaire dans cet incrément.
- [DEM restant] Import nominatif CSV/Excel, édition d'identité des bénéficiaires, plafonds individuels et pièces numérisées non livrés. Les titulaires/ayants droit et vérifications manuelles sont disponibles.
- Les listes administratives de conventions, bénéficiaires et adhésions sont paginées. Certains sélecteurs de création et de preuve chargent au maximum 100 références ; au-delà, poursuivre leur recherche/pagination avant généralisation. Cette limite d'interface n'est pas une limite métier à deux organismes. Le moteur et les priorités existants sont conservés.
- L'écran de preuves se trouve dans l'administration ; il demande l'identifiant de vente, avec préremplissage de la vente courante si elle est ouverte dans l'application. Un raccourci vendeur et une recherche métier des ventes restent à améliorer après recette. Les règles de préparation et de caisse n'ont pas été réécrites.
- Pas de connexion externe, pas d'identifiants de portail, pas de scan médical stocké. Politique de conservation des documents binaires et autorisations dédiées à définir avec P5-C ; les références présentes sont protégées par les permissions vente/tiers payant.

La fermeture de ces limites et la validation PostgreSQL/Chromium/humaine conditionnent la clôture de P5-CONF.1b. Le présent incrément ne valide ni P5-B complet ni P5-C.
