# P4.6 — Guide opérateur et recette humaine globale

P4.1–P4.5 sont fusionnés dans main `e8c1367`. P4.6 complète le comptoir sans changer les règles financières, le stock ou les droits implicites. PR #6 Draft : ne pas fusionner ni déployer pendant la recette.

## Données fictives et précautions

Utiliser exclusivement une base neuve dédiée `neosys_p46_recette_*` (PostgreSQL) ou un fichier SQLite absolu `neosys_p46_recette_*.db`. Jamais `neosys_pharma_v1`. Le script refuse les autres noms et une base non vide, ne supprime ni n’écrase de données. Les migrations sont décrites dans le cadrage avant leur exécution. Les seeds créent uniquement des stocks physiquement déclarés fictifs et des affectations explicites ; aucun prix conseillé n’est transformé en coût historique.

Exemple Linux/WSL, depuis le dépôt avec son environnement Python 3.14 et les dépendances installées :

```bash
python scripts/recette_comptoir.py \
  --database-url sqlite:////tmp/neosys_p46_recette_humaine.db \
  --confirmer-base-jetable
DATABASE_URL=sqlite:////tmp/neosys_p46_recette_humaine.db \
  AUTH_COOKIE_SECURE=false python -m uvicorn neosys_pharma.presentation.app:app --host 127.0.0.1 --port 8000
```

Pour PostgreSQL, créer d’abord une base vide dédiée dans une instance de test, puis fournir son URL au même script et au serveur. Les fixtures historiques utilisent `/tmp` : sous Windows, exécuter ce parcours dans WSL. Aucun besoin d’accès à la base métier Windows. Ne pas publier les identités de connexion contenues dans `/tmp/p1-browser-fixture.json` ; le mot de passe est généré aléatoirement pour la recette.

Acteurs fictifs explicitement affectés : `vente.qa` (préparation), `responsable.qa` (remises), `caisse.qa` (caisse), `responsable.p45.qa` (responsable distinct), `vente.lecture.qa` et `caisse.lecture.qa` (consultation). La configuration des moyens de paiement et du ticket d’appel doit être choisie explicitement dans la caisse ; aucun moyen actif implicite.

## Guide au comptoir

- Préparation : rechercher un dossier par UUID, désignation ou référence historique ; filtrer par état, dates UTC inclusives, emplacement/caisse autorisés. Le compteur concerne tous les résultats, la page n’en affiche que quinze. « Effacer les filtres » remet la première page. Actualiser conserve les critères.
- Ajouter/scanner : choisir le conditionnement commercial exact et la quantité ; consulter le stock réel. Remises ligne puis globale soumises à l’autorisation existante. Valider ne transmet pas et transmettre n’encaisse pas.
- Transmission : vérifier le numéro d’appel. Si le ticket est activé, ouvrir les exemplaires CLIENT et PANIER DE PRÉPARATION. Une réimpression n’attribue aucun nouveau numéro.
- Document : « Éditer la préparation PDF » conserve l’édition de la révision courante. « Éditions historiques » ouvre les octets d’origine, avec SHA-256. Une édition indique « PRÉPARATION — NON ACQUITTÉE » : elle n’est ni un reçu ni une garantie de disponibilité future. Les révisions anciennes non éditées ne sont pas reconstituées.
- Historique : consulter les événements paginés, leur date, auteur et transition/motif. Une édition documentaire ne change pas la révision commerciale.
- Caisse : rechercher la préparation par numéro d’appel ou référence, choisir la session compatible, confirmer les règlements acquis et encaisser intégralement. Rechercher ensuite le reçu par numéro, UUID ou produit historique. Actualiser relit le dossier sélectionné, notamment après une modification distante.
- Clavier : raccourcis P4 existants F1–F12 et alternatives Alt+Maj ; Tab/Maj+Tab et Entrée pour filtres, dossiers, historique et documents ; Échap pour fermer les modales, avec confirmation d’abandon si saisies. Les filtres se valident par « Rechercher » ou Entrée.

## Recette d’une journée fictive

| Étape | Vérification attendue |
| --- | --- |
| 1. Ouverture | Session et fond constaté, site/emplacement/caisse corrects ; observateur sans mutation |
| 2. Préparation | Scanner, plusieurs conditionnements/lignes, erreur conservant les saisies, stock réellement réservé |
| 3. Remises | Locale puis distante ; cumul et plafonds existants ; modification d’une ligne invalidant l’autorisation |
| 4. Attente/reprise | Dossier retrouvable avec filtres, critères et contexte conservés après actualisation |
| 5. Documents | Édition à une révision, modification puis nouvelle édition ; ancien PDF inchangé, longues désignations et allocations lisibles |
| 6. Transmission | Numéro d’appel, tickets CLIENT/PANIER, réimpression sans mutation ; option désactivée refusée côté API |
| 7. Encaissement | File recherchable, session compatible, paiement mixte avec preuve, erreur/rollback, reçu retrouvé sans F5 |
| 8. Fidélité | Acquisition après paiement ; aucune utilisation monétaire de points ; titulaire choisi explicitement |
| 9. Fonds | Demande/autorisation/expédition/réception distinctes, transit, solde réel, double réception refusée |
| 10. Retour | Quantités historiques, remboursement partiel puis complémentaire, preuve et moyens originaux, dette/compensation de points |
| 11. Quarantaine | Présence non vendable, réservation interdite ; décision sanitaire habilitée, jamais réintégration automatique |
| 12. X/Z | X sans fermeture ; Z prématurée refusée ; sessions fermées/dossiers résolus/écarts reconnus avant Z et nouvelle période |
| 13. Sécurité | Autre organisation/site/emplacement refusé, 401/403/CSRF, consultation seule ; pagination et recherches sans fuite de compteurs |

Consigner pour chaque étape : acteur, données fictives, résultat, capture/référence de document et anomalie éventuelle. L’acceptation métier reste humaine. Pas de crédit, tiers payant, P5, paiement monétaire en points ni validation fiscale implicite.

## Recette automatisée finale

Tests ciblés `test_comptoir.py` et `test_documents_preparation.py`, puis non-régression Vente/Caisse/Régularisations/Proformas/Remises. Le nouveau parcours est intégré aux fichiers `browser_p4.py` et `browser_caisse.py` déjà obligatoires : aucun nouveau parcours silencieusement ignoré par le contrôleur CI de main. Cycle Alembic sur base jetable ; tests PostgreSQL de concurrence d’édition. Une recette complète GitHub éventuelle nécessite l’autorisation explicite sur le HEAD final ; les jobs Draft ignorés ne valent pas validation complète.

Contrôle DOM ciblé reproductible (distinct de Chromium) :

```bash
npm install --prefix /tmp/neosys_p46_jsdom jsdom@30.1.2 --no-audit --no-fund
NODE_PATH=/tmp/neosys_p46_jsdom/node_modules node tests/dom_comptoir.cjs
```

Les résultats locaux ne remplacent pas PostgreSQL/Chromium. Dans l’environnement de développement de cette livraison, Chromium n’a pas démarré et PostgreSQL n’était pas installé : les parcours enrichis et le test concurrent de création de document sont prêts mais non validés ici. Aucune capture navigateur P4.6 n’est donc annoncée comme recette réussie. Les confirmations/fonds/retours/quarantaine existants doivent faire partie de la recette humaine globale, pas être redéveloppés.
