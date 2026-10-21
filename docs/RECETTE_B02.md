# B02 — Administration des moyens de paiement

## Réutilisation et périmètre

- Entrée « Moyens de paiement » dans Encaissement & Fidélité.
- Composants existants : cashModal, creation_dialogs, stockField, stockText, cashButton, compact-table et table-scroll.
- GET /api/caisses/organisations/{organisation}/contexte ; POST /configuration ; POST /moyens ; PUT /moyens/{id}.
- Permission caisse.parametrer, clés de mutation, révisions, relecture après mutation, contrôle du contexte et erreurs serveur conservés.
- Aucun changement de modèle, migration, règle B01, encaissement, remboursement ou autre module P4/P5.

## Changements

Une seule entrée ouvre deux sections : les cinq familles avec leur état, puis les moyens explicitement créés avec nom, code, famille, état et action Modifier. Un moyen actif dont la famille est inactive est signalé. Aucun exemple n’est créé automatiquement. Le moyen natif ESPÈCES reste représenté dans les familles.

La création et la modification réutilisent les formulaires et endpoints existants. Une case de confirmation explicite est obligatoire pour désactiver une famille précédemment active ou un moyen précédemment actif. La configuration vide n’est jamais remplacée par une valeur par défaut côté interface. Après enregistrement et relecture réussie, la liste est réouverte sans message de réussite persistant. Les erreurs restent dans la fenêtre existante.

## Vérifications

- tests/b02_payment_admin_ui.cjs : 22 assertions DOM et HTTP simulé réussies (HTML, composants de modale et requêtes réels ; transport simulé).
- tests/moyens_paiement_ui.cjs : 9 assertions DOM fournisseurs et HTTP simulé B01 réussies.
- node --check src/neosys_pharma/presentation/web/caisse.js : réussi.
- git diff --check : réussi.
- Image neosys-pharma-dev-tests inspectée dans un conteneur --network none, sans secret, montage ni base : Node absent. Tests JavaScript exécutés sur le poste avec jsdom 26.1.0 temporaire. Aucun pytest ni service test-db démarré.
- Pas de validation visuelle dans un navigateur réel, ni de mutation de base pour cette préparation. La recette ci-dessous reste humaine.

## Recette humaine exacte

1. Ouvrir http://localhost:8001/ et se connecter à l’organisation à vérifier avec caisse.parametrer. Aller dans « Encaissement & Fidélité », puis « Moyens de paiement ».
2. Vérifier les deux sections et les cinq familles. Pour une organisation jamais configurée, ESPÈCES est active. Si une configuration existe déjà, son état doit être respecté : ne pas la réinitialiser pour cette recette.
3. Cliquer « Nouveau moyen de paiement ». Saisir code AIRTEL_MONEY, nom AIRTEL MONEY, famille MOBILE MONEY, laisser Actif coché puis Enregistrer. Vérifier la ligne, sans identifiant technique affiché.
4. Créer de même MOOV_MONEY / MOOV MONEY / MOBILE MONEY. Vérifier deux lignes distinctes.
5. « Modifier les familles » : cocher MOBILE MONEY et enregistrer. Réouvrir cette fenêtre, décocher MOBILE MONEY et tenter d’enregistrer sans confirmation : erreur explicite. Cocher la confirmation puis enregistrer. Vérifier la famille inactive et la mention sur les moyens actifs. Réactiver ensuite la famille.
6. « Modifier » AIRTEL MONEY : décocher Actif. Sans confirmation, vérifier le refus ; confirmer et enregistrer, vérifier Inactif. Réactiver ensuite le moyen. Modifier également son nom puis vérifier le code et la famille conservés.
7. Pour tester l’état vide uniquement dans une organisation où cela est approprié : désactiver toutes les familles avec confirmation. Vérifier « Aucun moyen de paiement actif ». Actualiser le navigateur, revenir à cette vue et vérifier qu’ESPÈCES reste inactive. Rétablir manuellement la configuration voulue.
8. Après chaque type de modification, actualiser le navigateur et vérifier les états et noms conservés. Aucun message de réussite persistant ne doit être nécessaire pour lire la liste.
9. Avec un compte sans caisse.parametrer, vérifier l’absence de l’entrée et des actions de paramétrage. Le refus HTTP 403 est couvert par le transport simulé ; le serveur reste l’autorité des permissions.

Les saisies de recette ci-dessus sont des actions humaines explicites. Aucun script de préparation ne les applique à la base conservée. Les parcours financiers historiques et de substitution restent ceux de B01 et ne sont pas modifiés par B02.


## Correctif des deux anomalies de recette

- Nom : la valeur `libelle` retournée par le serveur devient aussi la valeur par défaut du champ. Elle résiste au clonage et au `form.reset()` de la modale existante. Les noms vides ou composés d’espaces sont rejetés avant requête ; le rejet serveur existant reste inchangé.
- Tableau : styles réservés à `.cash-payment-admin-table`, cellules espacées, en-têtes alignés, colonnes à largeur maîtrisée et noms longs avec retour à la ligne. Sur écran étroit, le conteneur `table-scroll` existant permet le défilement horizontal.
- Tests : 30 assertions DOM/HTTP simulé B02, 9 assertions B01, 6 cas de validation serveur (création/modification, nom vide/espaces/blancs) réussis. Les 6 cas serveur sont exécutés dans l’image Docker de tests, réseau désactivé, sans secret ni accès de base. Syntaxe JavaScript et diff vérifiés. Le rendu visuel reste à vérifier humainement.
- Reprise : recharger http://localhost:8001/, ouvrir « Moyens de paiement », modifier AIRTEL_MONEY et vérifier « AIRTEL MONEY GABON » prérempli. Enregistrer sans modifier le nom et réouvrir. Vérifier le refus d’un nom vide ou rempli d’espaces, puis la lisibilité d’un nom long et le défilement horizontal en réduisant la fenêtre.

## Contrôle final ciblé des permissions B02

- Réutilisation de `test_permissions_referentiel_et_configuration` B01 : création directe refusée (403), renommage seul refusé (403), désactivation refusée (403), modification des familles refusée (403). Le référentiel relu reste identique après les tentatives.
- Réutilisation de `b02_payment_admin_ui.cjs` : absence du bouton d’administration dans la navigation sans `caisse.parametrer`, impossibilité d’ouvrir les formulaires de création/modification/familles, aucune requête supplémentaire. Le refus HTTP simulé existant reste couvert.
- Exécution de ce contrôle : 32 assertions DOM/HTTP simulé réussies ; test HTTP réel FastAPI `test_permissions_referentiel_et_configuration` : 1 passed, 1 warning (dépréciation Starlette/httpx).
- Le test HTTP utilise les fixtures existantes et leurs vrais contrôles d’accès, dans un conteneur `neosys-pharma-dev-tests` sans réseau ni secret. `DATABASE_URL` et `TEST_DATABASE_URL` sont explicitement `sqlite+pysqlite://`. Les sources et tests sont montés en lecture seule ; seules les tables SQLite éphémères sont créées puis supprimées par la fixture. Aucun PostgreSQL ni volume conservé accessible. Aucun garde-fou d’autorisation remplacé.
- `git diff --check` réussi. Aucune modification applicative supplémentaire pour ce contrôle. Aucun commit, push ou merge ; B03 non commencé. Limite : ce contrôle ne constitue pas une exécution PostgreSQL native ; l’authentification et les permissions sont exercées via TestClient, et l’interface via DOM simulé.


## Clôture B02

Recette humaine et contrôles ciblés validés par le propriétaire du projet. Les tests PostgreSQL natifs n’ont pas été exécutés. Le contrôle avant commit a restauré à l’identique les trois fonctions de cartes de fidélité supprimées accidentellement pendant l’édition B02 ; ces fonctions restent hors du diff final. Aucun secret ni fichier temporaire inclus. B03 non commencé.
