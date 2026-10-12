# P4.6 — Finalisation opérationnelle du comptoir

Base : main `e8c13675801afcc97c5a6d2fce844350b009c74d`, P4.1–P4.5 fusionnés et acceptés. Branche dédiée : `feat/p4-6-comptoir`, PR Draft, sans fusion ni déploiement.

## Exigences et critères d’acceptation

1. P4.6.1 : recherche serveur sur UUID, désignations/références historiques de lignes et numéros d’appel/encaissement. Filtres état, dates inclusives UTC, emplacement et caisse ; pagination stable et limitée à 100. Recherche et filtres conservés après actualisation ; changement de site réinitialise le dossier sélectionné. Pas de chargement intégral dans le DOM.
2. P4.6.2 : numéro d’appel et période visibles après transmission ; ticket facultatif accessible avec `vente.consulter`, deux exemplaires CLIENT/PANIER identifiés. Télécharger/réimprimer ne modifie ni séquence, ni réservation, ni vente.
3. P4.6.3 : document détaillé « PRÉPARATION — NON ACQUITTÉE » : identité pharmacie/site, vente, révision, auteur, date, lignes/conditionnements/quantités, allocations réelles, pagination. Aucun coût, paiement ou lot fictif.
4. P4.6.4 : historique paginé accessible, messages d’erreur compréhensibles, actualisation du dossier courant, focus clavier et filtres préservés. Les actions simples utilisent les modales existantes.
5. P4.6.5 : guide opérateur et recette humaine complète sur données fictives, avec préparateur, caissier, responsable distinct et observateur explicitement affectés.

## Invariants

Permissions P1 et affectations effectives, isolation organisation/site/emplacement, CSRF, 401/403, révisions et idempotence restent obligatoires au backend. Les recherches sont filtrées avant comptage/pagination. Aucun accès implicite, aucun changement des calculs, états et transactions P4.1–P4.5. Réservations conservées à transmission ; consommation uniquement à encaissement atomique. Pas de crédit, tiers payant, utilisation monétaire des points, P5, connecteur bancaire simulé ou écriture comptable définitive.

## Architecture et reproductibilité historique

Les recherches sont des lectures, avec sous-requêtes EXISTS pour les lignes et numéros : plusieurs lignes/allocations ne dupliquent pas les ventes. Paramètres bornés et dates validées. Les filtres d’équipement doivent recontrôler l’affectation, jamais élargir le contexte.

Garantie du document de préparation définie avant implémentation : une édition conserve son UUID, organisation, vente, révision, auteur/date, instantané et octets PDF avec SHA-256. Une seule édition par vente/révision, protégée par contrainte unique et verrou transactionnel P3. Réimprimer une édition rend les mêmes octets, même après changement du catalogue, du site, de l’utilisateur ou de la vente. Une nouvelle révision produit une nouvelle édition ; aucune réécriture. Le document ne garantit ni paiement ni disponibilité future. Les anciennes révisions sans édition ne sont pas reconstruites artificiellement.

Migration additive prévue avant exécution : table `vente_documents_preparation`, clés composites organisation/vente/auteur, unicité vente/révision, triggers UPDATE/DELETE interdits SQLite/PostgreSQL. Pas de permission nouvelle ni attribution automatique. Downgrade retire uniquement cette table et ses triggers ; tests sur bases jetables uniquement. Les index de recherche supplémentaires seront ajoutés seulement si justifiés.

L’édition est une mutation documentaire autorisée avec `vente.consulter`, protégée par CSRF et idempotence ; elle ne modifie pas la révision ni le stock. Les téléchargements historiques sont des GET protégés.

## Tests et livraison

Tests ciblés HTTP : recherche littérale/accents, filtres, périodes inclusives, pagination/dédoublonnage, isolation et 401/403. Documents : octets/SHA identiques, désignations longues, allocations réelles, immuabilité SQL, révisions et concurrence PostgreSQL, rollback PDF. Cycles Alembic upgrade/check/downgrade/upgrade exclusivement jetables. Chromium : parcours comptoir au clavier et recherche conservée après mutation, lecture seule et documents. Ne pas multiplier les recettes complètes GitHub ; validation finale exacte soumise à autorisation.

Le workflow post-fusion `38263311083` a réussi (42 tests politique, SQLite 374 réussis/21 ignorés). PostgreSQL/Chromium y sont ignorés ; ce contrôle ne remplace pas la recette complète source `38240291387` sur `2974563`.

## Bilan de développement

P4.6.1–P4.6.5 implémentés sur la PR #6 Draft. Les recherches utilisent les valeurs historiques des lignes ; EXISTS empêche leur duplication. Les numéros sont recherchés exactement, les UUID par préfixe hexadécimal d’au moins huit caractères. Les caractères `%` et `_` restent littéraux. Les dates concernent la création des préparations et l’encaissement des reçus, avec bornes UTC explicites.

Les documents de préparation ne peuvent être nouvellement édités pour une vente ENCAISSEE/ANNULEE : seuls les documents déjà conservés restent consultables. L’éditeur et le préparateur sont identifiés séparément dans l’instantané. Aucune révision commerciale, quantité ou séquence n’est modifiée par l’édition. Les téléchargements portent un ETag SHA-256 et ne sont pas mis en cache publiquement.

P4.6.4 : grille compacte des préparations, historique paginé et actualisation du dossier sélectionné à la caisse. Un retour réseau obsolète après changement de contexte est écarté. Les anciennes éditions restent immuables.

Vérifications locales : tests ciblés Vente/Caisse/Documents/Recherche, Régularisations/Proformas/Remises ; cycles Alembic SQLite réussis ; 42 tests de politique CI réussis. Contrôle DOM réel avec jsdom : envoi de recherche, conservation après refresh, édition/fermeture de modale et dossier caisse resynchronisé. PDF QA à 40 longues désignations rendu et contrôlé sur quatre pages, en-têtes répétés et allocations lisibles.

Limites de cette exécution : PostgreSQL absent de l’environnement ; les tests de concurrence PostgreSQL restent à exécuter sur une base jetable. Téléchargement Playwright Chromium invalide, puis navigateur Chrome officiel téléchargé mais démarrage terminé par SIGSEGV ; aucun parcours Chromium local n’est présenté comme réussi. Les parcours obligatoires existants P4.2/P4.4 sont enrichis avec les vérifications P4.6. Aucune recette complète GitHub manuelle lancée. La validation technique complète et la recette métier humaine finale restent nécessaires avant fusion.
