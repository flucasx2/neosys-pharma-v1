# Recette humaine unique P4/P5 — cahier évolutif

État : préparation progressive, **non ouverte à acceptation**. Aucun scénario ci-dessous n'est déclaré accepté. La décision du 19/10 remplace les demandes de recettes intermédiaires ; les anciens cahiers restent des sources de scénarios, sans demander de nouvel environnement pour chaque incrément.

Une seule branche candidate et une instance isolée seront préparées après stabilisation. Employer exclusivement des données fictives. Aucune migration sur les bases conservées, aucun flag financier activé sans validation technique préalable. Les résultats PostgreSQL et Chromium réels sont des prérequis, pas des remplaçants de l'acceptation humaine.

| ID | Jeu et actions dans l'application | Résultats attendus | État |
|---|---|---|---|
| INT-01 | Deux clients fictifs, un compte fidélité chacun ; deux ventes de cosmétiques et conventions vérifiées. Confirmer les couvertures, transmettre, sélectionner ensemble. | Chaque ticket conserve son TTC et son bénéficiaire ; le montant à encaisser est la somme des parts clients. | API/SQLite testé ; recette réelle non exécutée |
| INT-02 | Payer le groupe par carte confirmée et espèces avec surplus ; calculer le rendu et vérifier les allocations. | Rendu sur espèces uniquement ; aucune allocation manuelle modifiée sans validation ; total net égal aux parts clients. | API/DOM partiellement testé ; native/Chromium requis |
| INT-03 | Finaliser INT-02, consulter les reçus individuels et collectif puis le X. | Références reliées, TTC/parts clients/organismes lisibles, points par client uniquement sur ses lignes payées ; aucun double mouvement. | API/SQLite testé ; recette réelle non exécutée |
| INT-04 | Retourner partiellement la première vente, rembourser puis rejouer la demande. | Plafond remboursable respecté ; aucun double remboursement ; autre vente/compte/reçu inchangé ; compensation traçable. | API/SQLite testé ; recette réelle non exécutée |
| INT-05 | Modifier le nom d'une caisse habilitée et consulter un reçu émis auparavant ; tenter avec un profil non autorisé. | Nom courant modifié, audit, ancien PDF identique ; refus hors droits/périmètre. | Tests API ciblés ; navigateur/recette non exécutés |
| INT-06 | Créer une carte virtuelle depuis Clients puis Caisse ; rejouer et rechercher l'identifiant. | Identifiant serveur unique ; une seule carte par opération ; code physique encore obligatoire. | API/DOM testé ; recette réelle non exécutée |
| INT-07 | Parcours individuel : espèces supérieures à la part client ; confirmer puis consulter reçu et caisse. | Rendu exact, caisse créditée du net ; reçu et couverture conservés. | API/DOM testé ; recette réelle non exécutée |
| INT-08 | Configurer conventions/versions/droits/preuves selon les scénarios de RECETTE_P5_CONF_1B.md. | Aucun droit confirmé par simple saisie ; preuves conformes et snapshots immuables. | Preuves antérieures conservées ; native/recette ouvertes |
| INT-09 | Configurer Airtel/Moov, encaisser chacun, rembourser sur le fournisseur initial puis essayer une substitution sans permission. | Identités et libellés distincts, montants X/Z exacts, substitution refusée. | API/DOM testé ; natif/recette non exécutés |
| INT-10 | Créer/associer un numéro visible et un code-barres distinct, rechercher chacun, imprimer puis réimprimer et opposer la carte. | Même compte, doublons croisés refusés, même PDF historique, carte opposée non proposée au scan. | API/DOM/SQLite testé ; natif/matériel/recette non exécutés |
| INT-11 | Importer une liste CSV et un XLSX fictifs avec deux références texte, prévisualiser puis confirmer et réimporter. | Personnes/provenances créées une seule fois, zéros conservés, aucune adhésion ou droit confirmé. | API/DOM/SQLite testé ; natif/recette non exécutés |
| INT-12 | Essayer doublons, formule Excel, référence déjà saisie manuellement, ligne invalide et contexte changé. | Erreurs explicites, aucune fusion ni écriture partielle ; rattachement existant uniquement par identifiant/révision. | API/DOM testé ; natif/recette non exécutés |
| INT-13 | Plafonds consommables et P5-C. | Scénarios à compléter après implémentation et arbitrages ; aucun résultat présumé. | Non livré |

Réutiliser également les scénarios historiques de sessions, X/Z, retours successifs, accès multisite et fidélité dans RECETTE_HUMAINE_P5_B.md et les documents P4. Préparer ultérieurement un inventaire unique de données, rôles, conventions, états attendus et procès-verbal, sans effacer les réserves antérieures.

## Ajout P5-C.1 / P5-FAC-02 — campagne finale seulement

Préparer trois organismes fictifs, des conventions à périodes valides avec droits confirmés, un champ d'identification FINANCIERE obligatoire et une référence/pièce FACTURATION obligatoire. Donner séparément les quatre permissions Créances à des profils fictifs, sans modifier les utilisateurs réels.

| ID | Opérations dans l'application | Attendu |
|---|---|---|
| C1-01 | Vendre avec droits valides, référence/pièce de facturation encore absente ; confirmer puis encaisser la part client | Vente autorisée, contrôle financier maintenu ; pas de créance depuis la seule simulation |
| C1-02 | Créances → Réalisations à constituer → constituer puis recommencer | Une créance positive par organisme, références exactes ; aucun doublon |
| C1-03 | Consulter la créance puis tenter une validation sans complément | A_COMPLETER ; refus serveur de validation/engagement ; montants inchangés |
| C1-04 | Compléter la référence et la pièce, indiquer le contrôle et le motif, enregistrer | A_CONTROLER ; nouvelle version signée par l'auteur ; preuve financière non éditable |
| C1-05 | Agent habilité → Valider pour facturation | VALIDE_POUR_FACTURATION ; aucune facture créée ; génération future encore hors module |
| C1-06 | Corriger un complément, consulter l'historique, essayer une révision périmée | Versions précédentes intactes, nouveau contrôle requis ; conflit explicite |
| C1-07 | Retourner partiellement la vente et consulter chaque créance | EN_ANOMALIE effectif, retour lié ; engagement bloqué jusqu'à régularisation, aucune réduction silencieuse |
| C1-08 | Essayer sans permission, depuis autre site/emplacement, double clic et réponse réseau perdue | Refus de périmètre ; aucune double écriture ; même clé pour rejeu identique |
| C1-09 | Consulter une réalisation historique sans exigences documentaires figées | Créance suivie, non facturable ; aucune reconstitution arbitraire des clauses |

Ces scénarios restent **non exécutés humainement**. Les états proposés pour la facturation, présentations et règlements devront être vérifiés lors de leurs incréments dédiés. L'ancien INT-13 demeure historique ; P5-C.1 est désormais livré localement avec les réserves natives de RESULTATS_P5_C_1.md.

## Documents organismes — scénarios C2 pour la campagne finale

**Non exécutés humainement.** À intégrer à la campagne unique P4/P5, sur données fictives et base jetable préparée par un responsable. Les documents d'émission de ce lot sont des pièces de recette sans validité fiscale ; aucune émission réelle n'est ouverte. Préparer deux agents explicitement habilités, un agent sans droit documentaire, deux sites, deux organismes, une convention par organisme, deux ventes confirmées et deux créances complètes d'un même organisme, une créance incomplète et un retour. Les conditions financières indispensables restent vérifiées avant vente ; seules les pièces FACTURATION peuvent être complétées ensuite.

| ID | Actions utilisateur | Résultat attendu |
|---|---|---|
| C2-01 | Créances → Préparer bordereaux et factures ; rechercher organisme par nom/code, période et statut, parcourir les pages | Résultats du site/emplacements autorisés seulement ; anomalies lisibles, sélection incomplète indisponible |
| C2-02 | Ouvrir une créance incomplète, compléter et faire vérifier par agent habilité via l'écran C1 | Nouvelle version administrative, montants source identiques ; aucun document émis automatiquement |
| C2-03 | Sélectionner deux créances éligibles, choisir Bordereau et période, préparer | Total exact, état PREPARATION, aucun numéro définitif ; seconde préparation incompatible refusée |
| C2-04 | Télécharger la prévisualisation puis retirer une créance, consulter historique et abandonner | BROUILLON NON EMIS ; validation précédente invalidée ; engagements libérés, versions conservées |
| C2-05 | Reprendre/valider une préparation, modifier ensuite un dossier administratif depuis un autre poste | Validation/émission sur ancienne révision refusée ; rechargement et nouvelle vérification requis |
| C2-06 | Dans la seule CI/native jetable autorisée, émettre le bordereau puis préparer une facture liée, émettre avec références de recette | Contrôles serveur revérifiés, références uniques, snapshot/PDF figés, créances FACTURE ; aucune écriture de caisse/stock/fidélité supplémentaire |
| C2-07 | Rejouer une émission identique après perte de réponse, double-cliquer, utiliser une référence existante ou deux agents sur une créance | Même résultat pour même clé/contenu ; une seule émission/ligne, conflits explicites, pas de double facturation |
| C2-08 | Télécharger une pièce émise, renommer l'organisme/pharmacie fictive puis retélécharger | Même identité historique, mêmes octets et SHA ; pas de réécriture silencieuse |
| C2-09 | Depuis Créance consulter documents liés, créer un récapitulatif de factures puis un lot | Liens complets, total exact, niveaux facultatifs ; doublons et mélange d'organismes refusés |
| C2-10 | Retourner une vente avant engagement, puis faire un autre retour après facture de recette | Émission/récap/lot concernés bloqués jusqu'à régularisation explicite ; documents antérieurs inchangés |
| C2-11 | Essayer sans permission, autre site/emplacement, session révoquée, champ client d'activation ou CSRF manquant | Refus serveur sans écriture ; aucun contournement par bouton ou rejeu |
| C2-12 | Ouvrir sur environnement ordinaire ou enlever un marqueur de recette | Émission indisponible et refus serveur ; production toujours false |

Les prérequis natifs/Chromium et les arbitrages sont consignés dans RESULTATS_P5_C_2.md. Les anciennes mentions « facturation hors module » de C1 décrivent son état historique ; l'émission réelle reste bloquée même après cette implémentation documentaire.
