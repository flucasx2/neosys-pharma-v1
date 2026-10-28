# Registre — recette suspendue, mise en conformité P5

Date : 18 octobre 2026. Base locale 5ad489c. Les observations de la mission sont conservées; seules les preuves exécutées ci-dessous permettent de qualifier le sous-lot.

| ID | Module / priorité | Constat et dépendances | État après P5-CONF.1a |
|---|---|---|---|
| NC-P5-01 | Administration / haute | Organismes accessibles seulement depuis une fiche client | Écran autonome et API implémentés; tests HTTP et DOM réussis. Chromium/PostgreSQL/recette humaine en attente. Non clos métier. |
| NC-P5-02 | Référentiel / haute | Régimes, conventions, barèmes, seuils, plafonds et périodes administrables | Conventions et règles explicites P5-A/B réutilisables. Interface et concepts manquants ouverts; pas de calcul contractuel inventé. |
| NC-P5-03 | Droits / haute | Modes liste/externe/mixte, champs typés et contrôles de format | Patch préparatoire inspecté, non intégré. Import Excel/CSV et validation de valeurs restent ouverts. |
| NC-P5-04 | Adhésions / haute | Titulaire/ayant droit, dates, régimes, plafonds individuels et encours | Bénéficiaires/adhésions P5-A existants conservés. Interface et plafonds/cumuls restent ouverts selon contrats. |
| NC-P5-05 | Justificatifs / haute | Exigences simples/cumulatives/alternatives et référence de vérification humaine | Aucune saisie ne confirme automatiquement les droits. Configuration et enregistrement des preuves à raccorder à la vente. Aucun secret de portail stocké. |
| NC-P5-06 | Facturation / haute | Continuité des documents, versions et parts vers P5-C | Snapshots financiers existants conservés; dossier documentaire et créances/factures restent à traiter dans les lots autorisés. |
| OBS-CAT-01 | Catalogue / haute | Import PharmaGabon terminé, produits non retrouvés | Signalé, non reproduit ici; vérifier filtres/périmètres et rapport d'import avant correction. |
| OBS-ORG-01 | Structure / normale | Modifier l'intitulé d'une caisse | Signalé, reporté; préserver ses références historiques. |
| OBS-CAI-01 | Caisse / haute | Paramétrage autonome Airtel Money, Moov Money et autres moyens | Signalé, reporté; dépend des moyens autorisés et confirmations existants. |
| OBS-CAI-02 | Caisse / haute | Rendu automatique | Signalé, reporté; espèces uniquement, contrôles financiers à préserver. |
| OBS-CAI-03 | Caisse / haute | Simplifier encaissement groupé | Signalé, reporté; ne pas modifier l'orchestration financière ni activer le flag. |
| OBS-FID-01 | Fidélité / normale | Identifiant carte virtuelle automatique | Signalé, reporté; unicité et idempotence à préserver. |
| OBS-FID-02 | Fidélité / normale | Carte physique par numéro/code-barres | Signalé, reporté; format/symbologie à confirmer selon référentiel. |
| OBS-UI-01 | Présentation / normale | Retirer les mentions de phases | Le nouvel écran n'en contient pas; nettoyage des autres écrans reporté. |
| OBS-VENTE-01 | Vente / haute | Libellés de modes génériques | Signalé, reporté; compatibilité des valeurs et historiques à préserver. |
| OBS-FAC-01 | P5-C / haute | Informations de facturation par organisme | À traiter avec NC-P5-06; ne pas développer la facturation dans ce sous-lot. |

Les priorités sont un ordre de traitement technique proposé, pas une nouvelle règle métier. Aucune observation hors périmètre n'a été corrigée sans reproduction. La suspension de la recette humaine générale du 18/10 reste effective; la recette ciblée ci-jointe est une procédure à exécuter après préparation autorisée de l'environnement.


## Mise à jour du 19 octobre 2026 — P5-CONF.1b

Les lignes précédentes décrivent la livraison du 18/10. La mission actuelle confirme l'acceptation P5-CONF.1a, réserve ergonomique maintenue. Les résultats Windows sont rapportés par le responsable ; ils ne sont pas présentés comme exécutés dans Work.

| ID | Reproduction / cause | Gravité / module | État, correction et preuve |
|---|---|---|---|
| NC-P5-01 | Administration autonome reçue et acceptée en recette précédente | Haute / organismes | Accepté avec réserve OBS-P5-UI-01 selon décision du 19/10. Code accepté réutilisé |
| OBS-P5-UI-01 | Messages de confirmation redondants ou persistants pendant la recette | Normale / UI | Ouvert, non bloquant, pas de correction de l'écran accepté dans ce lot |
| NC-P5-02 | API de conventions sans administration complète | Haute / conventions | Conventions/régimes embarqués/barèmes par ligne administrables ; tests ciblés. Plafonds périodiques, majorations et montants fixes ouverts ; recette réelle non exécutée |
| NC-P5-03 | Champs et modes de vérification non raccordés | Haute / droits | Schéma strict et preuves manuelles LISTE/IDENTIFICATION/EXTERNE/MIXTE implémentés et testés ; imports non livrés |
| NC-P5-04 | Bénéficiaires/adhésions sans écrans ni plafonds individuels | Haute / adhésions | Recherche/création/adhésion/décision sur droits réutilisent P5-A ; plafonds consommables et édition d'identité restent ouverts |
| NC-P5-05 | Pièces absentes ou preuve d'une autre vente pourraient être réutilisées | Haute / vérification | Preuve par vente/bénéficiaire/révision, champs/alternatives/périodes contrôlés, refus explicites ; tests API et DOM. Native/recette humaine requises avant clôture |
| P5-FAC-01 / NC-P5-06 | Continuité documentaire vers P5-C | Haute / snapshots | Métadonnées, identité/régime, pièces/références/auteur et données historiques de lignes figées dans le snapshot ; aucun document binaire ni facture. Couverture partielle, non clos globalement |
| CONF-INT-01 | Enrichissement du snapshot utilisait un attribut `ProduitModel.designation` absent : test de simulation en erreur | Bloquante / projection nouvelle | Corrigé par `LigneVenteModel.designation`, valeur historique ; test de confirmation avec dossier documentaire |
| CONF-UI-01 | Recherche catalogue utilisait `designation` au lieu du contrat réel `nom` | Haute / sélecteurs | Corrigé ; assertion DOM sur le nom de produit reçu de l'API |
| CONF-UI-02 | Choix du bénéficiaire non explicitement renseigné dans le nouveau formulaire | Haute / preuve | Option initiale vide obligatoire, résultat également explicite ; tests DOM et validation UUID serveur |
| CONF-INT-02 | La création P5-A d'adhésion ne vérifiait pas le statut de l'organisme | Haute / adhésions | Contrôle serveur ajouté et test dédié ; historiques préservés |
| CONF-ENV-01 | Binaire Python 3.14 préexistant termine par Bus error avant tests | Environnement / Work | Installation séparée de CPython 3.14.8 fonctionnelle ; aucun fichier applicatif modifié pour contourner |
| CONF-ENV-02 | Binaires PostgreSQL 16.2 exécutables, mais création d'un cluster sous utilisateur non privilégié impossible : chown invalide et runuser cannot set groups | Bloquante pour preuve native / environnement | Aucun serveur ni base de tests PostgreSQL démarré ; script Windows gardé et test natif fournis, non exécutés. PostgreSQL 18.6 cible non vérifié |
| CONF-ENV-03 | Téléchargement Chromium : archive tronquée, puis exécutable absent | Bloquante pour navigateur / environnement | Test préparé sur origine localhost sécurisée ; aucun scénario Chromium exécuté |
| CONF-LIM-01 | Certains sélecteurs limités aux 100 premières références ; preuve demandant identifiant de vente | Normale / ergonomie | Ouvert avant généralisation aux gros référentiels ; listes principales paginées ; limites signalées dans la documentation |

Les autres observations catalogue, caisse, encaissement groupé et fidélité restent ouvertes comme précédemment. Aucun succès DOM ou SQLite n'est une clôture métier ou une preuve de concurrence PostgreSQL.

## Consolidation P4/P5 — lot 01, 19/10

- GROUP-P5-01 : ventes avec organismes refusées par le service groupé ; correction codée et tests SQLite/API/DOM réussis. Réalisations et fidélité par vente ; native et navigateur non vérifiés. État : partiellement vérifié, activation interdite.
- Les recettes humaines intermédiaires sont suspendues par décision actuelle. Les observations et réserves historiques restent conservées pour la recette unique.
- Les plafonds individuels/périodiques, les fournisseurs de paiement distincts, les cartes physiques à double identifiant et P5-C restent des travaux à terminer, sans clôture annoncée.

## Consolidation P4/P5 — lot 02, 19/10

| ID | Cause ou demande | État et preuve |
|---|---|---|
| OBS-ORG-01 | Modifier le nom d'une caisse sans réécrire les historiques | Implémenté et vérifié API/SQLite : nom attendu, permission, périmètre, idempotence/audit et PDF inchangé. Navigateur natif non vérifié |
| OBS-FID-01 | Identifiant virtuel non généré | Serveur UUID préfixé, deux formulaires adaptés ; API et DOM réussis, unicité/idempotence couvertes. Native/Chromium ouverts |
| OBS-CAI-02 | Borne du formulaire individuel empêchant les espèces supérieures au dû | Corrigé, rendu/net vérifiés. Groupe : proposition explicite de rendu, pas d'automatisme à chaque frappe. Pas de clôture globale de l'observation |
| GROUP-UI-02 | Finalisation possible malgré un règlement/une ventilation localement modifié sans enregistrement | Reproduit par un test DOM en échec puis corrigé : comparaison à l'état serveur, blocage du bouton et de l'appel, message. Pas de changement financier backend |
| OBS-UI-01 | Libellés techniques | Nettoyage ponctuel Clients/confirmations ; nettoyage global ouvert |
| OBS-FID-02 | Numéro visible et code-barres physiques distincts, impression | Non implémenté ; ne pas assimiler la compatibilité de l'ancien code unique à ce périmètre |
| OBS-CAI-01 | Fournisseurs de paiement indépendants | Non implémenté ; MOBILE_MONEY existant n'est pas une configuration autonome Airtel/Moov |
| CAP-P5-01 | Consommation périodique/individuelle | Non implémentée, décisions nécessaires consignées dans ARBITRAGES_PLAFONDS_P5.md |

Les limites d'environnement CONF-ENV-02/03 subsistent. Les tests natifs préparés ne sont pas des résultats réussis. Les imports, sélecteurs volumineux et P5-C restent ouverts. La recette unique est préparée progressivement, sans demande d'acceptation intermédiaire.

## Consolidation 03 — moyens de paiement

- OBS-CAI-01 : implémenté avec catalogue organisationnel, fournisseurs distincts et confirmations figées ; tests API/DOM réussis, natif et navigateur ouverts.
- PAY-03-01 : lecteur du solde d'un retour ignorait les allocations groupées ; même budget partagé avec le service et test groupe réussis.
- PAY-UI-03 : valeur de restitution perdue au clonage de formulaire ; reproduit en DOM, defaultSelected corrigé, origines distinctes conservées.
- PAY-MIG-03 : CHECK historiques anonymes risquant d'être omis par batch SQLite ; expressions conservées et test de migration dédié.
- PAY-LIM-03 : références externes identiques refusées entre fournisseurs d'une même famille par contrainte historique ; aucun affaiblissement. Pas de connecteur de paiement.

## Consolidation 04 — cartes

- OBS-FID-02 : numéro visible/code-barres indépendants, registre commun unique et reprise des anciennes cartes ; recherche/scan et document PDF figé/réimpression sous fidelite.gerer implémentés, tests API/SQLite/DOM réussis. Validation native/navigateur et matérielle ouverte.
- CARD-04-01 : les collisions croisées numéro↔barcode sont protégées par le même index unique en base, pas par deux contraintes indépendantes insuffisantes.
- CARD-LIM-04 : PDF technique A4 paysage Code 128 ; vieux numéros non imprimables restent consultables et peuvent recevoir un code-barres avant première émission. Le scan matériel ne fait pas partie des preuves Work.

## Consolidation 05 — catalogue

OBS-CAT-01 partiellement ouverte : faux succès de fin de lots reproduit et corrigé ; recherche CIP/nom prouvée sur données fictives après reprise. L'incident réel n'est pas reproduit faute du rapport et CSV Windows. Aucune correction arbitraire du stock, de la normalisation ou des prix.

## Consolidation 06 — import de bénéficiaires

- NC-P5-03/04 : import CSV/XLSX de personnes ajouté, rattachement explicite aux personnes existantes, provenance et reimport ; API/SQLite/DOM réussis. Les adhésions/droits restent des étapes distinctes. L'édition de masse et les modifications de données déjà importées restent contrôlées/non automatiques.
- IMP-06-01 : références Excel numériques refusées, zéros non reconstruits ; formules/colonnes de droits interdites, feuilles multiples explicites, limites de ressources et XML protégé.
- IMP-06-02 : une ligne invalide ou un échec après la première création annule tout l'import ; tests de rollback réussis sous SQLite, pas de preuve native.
- ENV : PostgreSQL natif, Chromium et matériel non exécutés. La sélection intégrée se termine par 19 réussis et 4 ignorés, qui ne lèvent pas les réserves natives.
- CAP-P5-01 : arbitrages toujours attendus, aucune consommation de plafonds codée. P5-C demeure autorisé pour la suite et non livré dans 03–06.

## Consolidation 07 — contrôles de compatibilité

- COMPAT-07-01 : sélecteurs Chromium historiques name=mode, montant_ESPECES et mode_CARTE conservés pour les moyens génériques ; 9 assertions DOM fournisseurs, navigateur réel non exécuté.
- CI-07-01 : cible native générique incompatible avec garde-fous nouveaux ; CI 17/18 sur bases explicitement marquées préparée, sans supprimer de tests, vérifiée localement (48 tests de politique) mais non exécutée à distance.
- MIG-07-01 : ancien command.check sur révision intermédiaire échouait réellement ; montée jusqu'au head avant check et cycle de préservation maintenu, test repassé.
- CARD-07-01 : numéro visible long tronqué sur PDF, test rouge puis correctif de retour à la ligne, 4 tests cartes réussis. Matériel non vérifié.

## P5-C.1 / P5-FAC-02 — 19/10/2026

- C1-ENV-01 — Ouvert : PostgreSQL natif non exécuté dans cette reprise ; courses et migration protégées préparées, aucun ignoré présenté comme réussi.
- C1-ENV-02 — Ouvert : Chromium absent ; installation échouée (ZIP tronqué), 23 assertions DOM Créances et 38 Conventions avec HTTP simulé seulement. Recette finale consolidée maintenue.
- C1-REG-01 — Incrément 1 préparé localement : registre append-only de compensation par créance/retour, allocation uniquement si la part P5-B identifie un payeur unique ; source et snapshot initiaux inchangés. Multi-organismes, historiques incomplets, créances engagées/présentées/facturées restent bloqués. Tests préparés, base jamais exécutée ; statut ouvert jusqu'à recette technique ciblée.
- C1-LEG-01 — Ouvert : réalisation historique sans exigences documentaires figées non facturable ; reprise administrative à définir explicitement, sans prendre des clauses courantes pour historiques.
- C1-FAC-02 — Implémenté localement : champs/pièces FACTURATION facultatifs au comptoir, droits/finance toujours obligatoires ; compléments versionnés et contrôle distinct avant engagement. Facturation effective reste hors P5-C.1 et devra appeler le garde transactionnel.
- C1-MIG-01 — Corrigé dans le test : inspection SQLite périmée après migration externe ; connexion d'inspection renouvelée, assertions conservées.
- CONTINUITE-C1 — Worktree initial disparu ; base exacte récupérée par les bundles et ajouts repris dans une copie isolée. Bundle complet et patch de cette livraison exportés pour récupération.

L'incident réel PharmaGabon reste ouvert faute de reproduction avec son fichier réel. CAP-P5-01 (plafonds consommables) reste ouvert ; aucune règle de période, consommation ou restitution inventée. Les réserves antérieures P4/P5 ne sont pas levées par les seuls tests SQLite/DOM de cet incrément.

## P5-C.2 — 19/10/2026

| ID | Constat / cause | État et preuve |
|---|---|---|
| C2-ENV-01 | PostgreSQL natif, conteneurs et binaires serveur indisponibles | Ouvert bloquant pour garanties natives ; 2 courses C2 + migration protégées préparées. Aucun test ignoré compté réussi |
| C2-ENV-02 | Playwright sans binaire Chromium | Ouvert ; lancement échoué, 27 assertions DOM avec HTTP simulé réussies ; pas d'E2E financier navigateur |
| C2-FISC-01 | Politique définitive de numérotation et mentions fiscales non définies | Ouvert bloquant production ; émission réservée à CI/native jetable, références manuelles uniques et marquage non fiscal |
| C2-CONTRAT-01 | Période et regroupements multiconventions/intersites insuffisamment spécifiés | Restriction conservatrice à un site/version de convention, période UTC explicite ; à arbitrer avant généralisation |
| C2-JSON-01 | UUID bruts dans le snapshot de récapitulatif non sérialisables | Corrigé par encodage JSON explicite ; nominal facture/récap/lot réussi |
| C2-RETOUR-01 | Retour post-facture laissait créer un récapitulatif | Reproduit 201 au lieu de 409 ; contrôle des retours propagé au récapitulatif et au lot, deux tests verts et PDF initial inchangé |
| C2-TOTAL-01 | Total multi-créances pouvait dépasser INTEGER 32 bits | BIGINT + somme exacte bornée ; test 3 milliards et contrôle Alembic réussis sous SQLite, natif ouvert |
| C1-REG-01 | Compensations de créances, avoirs, annulations documentaires/rejets | Incrément 1 préparé : retours non engagés avec ventilation historique univoque seulement ; avoirs, annulations documentaires/rejets et cas ambigus toujours bloqués ; recette technique ciblée requise |
| C2-TEST-01 | Fixture de migration réinstallait un catalogue déjà migré | Correction limitée au test ; aucune permission automatique ni règle métier retirée |

OBS-CAT-01 (incident réel PharmaGabon) et CAP-P5-01 (plafonds consommables non arbitrés) restent ouverts. Les contrôles C2 ne lèvent aucune réserve historique non couverte. Aucun push, migration conservée, déploiement ou activation de l'encaissement groupé.

## Corrections ciblées fidélité / historique — 20 octobre 2026

| ID | Constat / intervention | État et réserves |
|---|---|---|
| NC-P4-FID-004 | Nature COSMETIQUE et catégorie admise restent obligatoires. Lecture serveur explicative, assiette commune au gain, distinction titulaire/éligibilité/attribution ; motifs figés après paiement sans réévaluation du catalogue | Préparé localement, non intégré/non clos humain. 19 nouveaux tests Python (avec CLI-005) réussis ; aucun reclassement du lecteur ni crédit de 0004. La cause exacte sur données humaines reste à confirmer en lecture seule |
| NC-P4-CLI-005 | Historique par client préparé OU compte explicitement enregistré à l'encaissement, relié au profil ; EXISTS, pagination SQL, origines et permissions cumulées | Préparé localement, non intégré/non clos humain. Pas de modification de ventes.client_id ; liens réels de 0004 non consultés |
| FID-VAL-01 | Chromium téléchargé invalide, aucun serveur PostgreSQL/Docker/Podman local disponible | Non exécutés ; DOM simulé et HTTP SQLite ne valent pas preuve PostgreSQL/E2E. Aucune activation groupée hors contexte existant autorisé |
| FID-REG-01 | Ancien test de remboursement groupé, ligne 907 de test_caisse.py : attendu strict ignorant quatre champs de fournisseurs d'audit | Échec reproduit à l'identique au parent 9c273a94 intact. Test et règles financières non modifiés ; correction distincte à autoriser. Sélection de régressions : 25 réussies, 1 échouée |

Rapport et protocole limité : `CORRECTIONS_P4_FID_004_CLI_005.md`. Pas de migration. Les anomalies et arbitrages précédents restent inchangés.


## 28 octobre 2026 — neutralité des organismes, correction préparée

| ID | Écart | Traitement local | Statut |
|---|---|---|---|
| P5-NEUT-01 | Modes vente/proforma nominatifs | Mode générique additif, anciens modes conservés | Préparé, non testé |
| P5-NEUT-02 | Priorité organisationnelle sans choix contractuel bénéficiaire | Intersection des ordres autorisés par conventions et bénéficiaire, cardinalité V1 | Préparé, non testé |
| P5-NEUT-03 | Solde automatiquement imputé au client | Clauses explicites REFUS/DROITS/EXCLUSION/PLAFOND/ECART, blocage conservateur | Préparé, non testé |
| P5-NEUT-04 | Rangs des parts reconstruits selon UUID | Persistance du rang effectivement calculé | Préparé, non testé |

Détails, tests et limites : [livraison ciblée](P5_NEUTRALITE_ORGANISMES_20261028.md). Aucun écart déclaré clos ; autorisation d'exécution des tests et validation contractuelle attendues. Historique conservé.
