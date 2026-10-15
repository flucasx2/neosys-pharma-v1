# P4.6 — Encaissement : ergonomie en deux panneaux

Cette étape réorganise uniquement l’interface existante. Aucun changement de modèle, API, permission, migration ou calcul financier. Le correctif Proformas et les autres corrections locales P4.6 sont conservés.

## Parcours

1. Ouvrir **Encaissement & Fidélité** avec un compte explicitement habilité.
2. Ouvrir une session ou déplier **Sessions de caisse & journaux**, puis choisir sa session ouverte. La caisse et la session sont affichées en haut ; organisation, site et emplacement restent dans le contexte opérationnel existant.
3. Rechercher un appel, une référence ou un produit dans la file de gauche. Les critères supplémentaires sont dépliables ; recherche et pagination restent exécutées côté serveur.
4. Sélectionner une préparation. À droite : numéro d’appel, lignes, conditionnements, quantités, montant dû, identification contrôlée du titulaire et règlements.
5. **Simple** sélectionne un seul moyen : espèces ou confirmation non espèces existante. **Multiple** permet de retenir plusieurs confirmations et des espèces. Ces modes concernent les moyens d’une seule vente, jamais un encaissement groupé de tickets.
6. F6 / Alt+Maj+6 conserve la confirmation indépendante non espèces, avec référence et preuve. Aucun connecteur bancaire n’est simulé.
7. F10 / Alt+Maj+0 ouvre la confirmation finale existante, préremplie depuis le panneau. Vérifier les règlements et le titulaire, puis confirmer explicitement. L’indication de répartition est indicative : le serveur reste décisionnaire, notamment pour le rendu de monnaie.
8. Après succès : montant effectivement encaissé à l’origine, confirmation, reçu PDF et impression ; les actions de paiement et le panneau de saisie disparaissent.

Les barèmes, comptes, cartes, oppositions, historiques, rapprochements et journaux restent accessibles avec leurs permissions existantes. L’acquisition de points conserve les règles existantes ; leur utilisation monétaire reste bloquée. Les paramètres et créations simples utilisent les modales existantes.

## Conservation et sécurité

- Aucune requête financière lors d’une simple sélection ou saisie.
- Répartition conservée pendant une actualisation du même dossier, de la même révision et de la même session. Changer de dossier/révision/session la réinitialise pour éviter le réemploi de données périmées.
- Erreur d’enregistrement : la modale reste ouverte avec ses saisies et sa clé d’idempotence existante.
- Les réponses tardives d’une sélection ne remplacent pas une sélection plus récente ; une recherche fidélité antérieure ne s’applique pas au nouveau dossier.
- En lecture seule, aucun formulaire de règlement ni action d’encaissement. Les contrôles backend P1–P4 restent inchangés.
- Sur écran étroit, les deux panneaux passent en une colonne.

## Validation locale de cette étape

- `tests/dom_encaissement_panneaux.cjs` : 19 contrôles, incluant répartition mixte, confirmation, erreur, révisions, lecture seule, reçu et refus de double paiement.
- `tests/browser_encaissement_panneaux.cjs` : Chromium, fichiers HTML/CSS/JS réels, HTTP simulé et données fictives ; sélection, session, saisie mixte, confirmation au clavier, annulation, conservation des filtres, reçu et responsive. Il s’agit d’un test UI ciblé, pas d’une recette PostgreSQL complète.
- Tests DOM Proformas (19 assertions), navigation caisse et comptoir conservés.
- Tests backend ciblés `test_caisse.py` : encaissement mixte atomique, échecs sans effet financier et HTTP 401/403/CSRF, en SQLite isolé.

Aucun GitHub Actions ni publication Git. La recette humaine sur Windows reste nécessaire pour valider l’ergonomie avec les comptes et préparations existants.
