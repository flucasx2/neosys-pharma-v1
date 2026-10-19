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
