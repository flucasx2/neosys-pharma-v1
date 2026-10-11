# P4.4 — Encaissement et fidélité : cadrage pour validation métier

Statut : préparation documentaire uniquement. Branche feat/p4-vente-caisse, PR #4 Draft. Aucune migration, API financière ou interface d'encaissement ajoutée par ce cadrage. P4.3 fonctionnellement validé ; contrôles complémentaires décrits dans docs/P4.md. P4.5/P4.6/P5 non commencés.

## Sources et articulation

Référentiel UML V1 actualisé du 10 octobre 2026, P1/P2/P3 et P4.1–P4.3 implémentés, décisions de validation P4 et de fidélité. Le référentiel décrit Vente, Encaissement, Reglement, ModePaiement, SessionCaisse, MouvementCaisse, MouvementCoffre, TransfertFonds, ClotureX et ClotureZSite. La fidélité n'y est pas structurée : les concepts proposés ci-dessous traduisent les décisions récentes et doivent être validés comme extension, sans attribuer au PDF des classes qui n'y figurent pas.

La « validation de vente » consommant le stock désigne la finalisation financière après encaissement effectif. VALIDEE_PREPARATION et TRANSMISE ne consomment pas le physique. Proforma reste une offre sans réservation supplémentaire, mouvement physique, paiement ou créance.

## Périmètre confirmé

- Encaisser une Vente transmise à une caisse autorisée du même emplacement, dans une SessionCaisse ouverte appartenant à cette caisse et à son caissier. Changement de caissier : fermeture puis nouvelle session conformément à l'UML.
- Vente 1 → 0..1 Encaissement ; Encaissement 1 → 1..* Reglement ; Encaissement appartient à une SessionCaisse. Modes et montants, montants remis et monnaie éventuelle sont explicites, jamais confondus avec le net réglé.
- Plusieurs règlements pour une vente, reçu historique et mouvements de caisse immuables appropriés au mode. Distinguer les règlements électroniques du tiroir espèces.
- Consommation atomique des réservations P3 après paiement effectif. Revalidation des droits, état/révision, remises, quantité réservée, disponibilité et règles de lot/péremption avant finalisation. Un échec ne laisse ni vente encaissée, ni sortie partielle, ni points modifiés.
- Crédit et CNAMGS/mutuelle/combiné restent non finalisables. Aucun moteur P5, créance, frais, taux ou plafond financier inventé.
- Deux séquences distinctes appel/encaissement, partagées par le site, quatre chiffres, liées à Vente et à une période Z ; UUID permanent indépendant. Réinitialisation uniquement à la clôture Z effective, jamais à minuit ou à une clôture de session. P4.4 prépare ce rattachement ; P4.5 implémente la clôture Z conformément au découpage existant.
- Ticket d'appel facultatif et paramétrable par pharmacie, deux exemplaires client/panier ; ticket de préparation et reçu imprimables. Une réimpression ne crée ni numéro ni opération financière supplémentaires.
- Identification client à la caisse par carte physique, virtuelle ou téléphone. Solde et utilisation des points uniquement à la caisse ; aucune utilisation/crédit lors de préparation, transmission ou proforma.
- Acquisition et conversion indépendantes, datées et historisées, catégories éligibles configurables. Aucun barème de production par défaut, en particulier aucun seuil hérité du prototype.
- Crédit après encaissement réussi, débit des points utilisés dans la même transaction financière, pas de double attribution. Historique immuable ; régularisations futures par événements compensatoires, sans réécrire la vente ni supprimer le journal.

## Architecture proposée, sans réalisation financière

Réutiliser Vente/LigneVente, les instantanés P2, les réservations P3 et les affectations P1. Ajouter les seules entités UML nécessaires à P4.4. Ne pas dupliquer Caisse/Coffre/PosteVente ni créer un second panier ou une seconde comptabilité de stock.

Pour fidélité, propositions à valider : Client, CarteFidelite (supports physique/virtuel associés à une identité, sans deux soldes), CompteFidelite, BaremeAcquisitionPoints, BaremeConversionPoints, eligibilités de catégories et MouvementFidelite immuable. Le client est identifié par UUID interne ; carte/téléphone servent au rapprochement contrôlé, pas de clé primaire. Portée du compte et gestion des téléphones partagés restent à décider. Les associations futures restent des points d'intégration, sans développer un package clients autonome ou P5.

Chaque règle appliquée est figée : versions des barèmes, catégories retenues, assiette, points consommés/acquis, réduction FCFA, calculs et arrondis, identité de l'acteur et contexte site/emplacement/session. Aucun recalcul de l'historique avec les paramètres courants. Les périodes incompatibles sont refusées ; clôture explicite avant remplacement de période.

Une commande applicative de finalisation, idempotente et transactionnelle, relit/verrouille la vente, la session, les réservations et le compte fidélité, valide les droits et règles approuvées, conserve les règlements, consomme P3, débite/crédite les points, attribue le numéro d'encaissement, inscrit les mouvements/événements puis marque ENCAISSEE. Contraintes d'unicité et idempotence empêchent deux encaissements ou deux crédits pour la même vente. La hiérarchie des verrous reste cohérente avec P3 ; aucune substitution générale des fondations.

Un prestataire bancaire externe ne participe pas à la transaction PostgreSQL. Si une intégration est retenue, confirmation externe vérifiée et idempotente, état intermédiaire explicite, puis transaction locale de finalisation ; reprises et rapprochements tracés. Ne pas présenter plusieurs appels indépendants vente/stock/caisse/points comme une opération atomique. Une carte saisie comme règlement confirmé via un terminal indépendant ne constitue pas une intégration acquéreur.

Les lectures de solde ne constituent pas une réservation de points. Deux caisses utilisant le même compte sont sérialisées ; solde insuffisant au commit → refus sans effet partiel. Une version obsolète du barème, une autorisation invalidée ou une session fermée exige actualisation. La course avec une future clôture Z doit empêcher une finalisation dans une période fermée et une libération concurrente des réservations en cours.

L'impression survient après commit : échec d'imprimante → reçu disponible à réimprimer, sans annuler l'encaissement ni le reproduire.

## Décisions métier bloquantes avant implémentation financière

| Sujet | Décision attendue | Option de travail proposée, non appliquée |
|---|---|---|
| Moyens de paiement | Liste initiale (espèces, carte, mobile money, chèque, virement...), confirmation requise, référence obligatoire, annulation d'un paiement échoué | Référentiel configurable ; commencer uniquement avec les modes explicitement validés, sans intégration bancaire implicite |
| Règlements multiples | Exiger le paiement intégral ou admettre un paiement partiel ? Monnaie uniquement en espèces ? Trop-perçu, avance et devises ? | Paiement intégral XAF ; monnaie sur espèces uniquement ; aucun avoir/dépôt ou conversion de devise implicite |
| Ordre fidélité/remises et TVA | Fidélité réduction du TTC ou moyen de paiement ? Après remises autorisées ? Répartition par ligne éligible et incidence HT/TVA ? | Remises P4.2 d'abord ; proposition de réduction TTC répartie sur les lignes éligibles, à confirmer avec le traitement fiscal applicable. Aucun choix fiscal automatique |
| Assiette d'acquisition | TTC éligible avant/après fidélité ? Part réglée par points incluse ? Acquisition par panier ou par ligne ? | Montant éligible effectivement payé après remises et réduction fidélité, agrégé au panier ; exclusion de la valeur financée par points proposée |
| Arrondis et fractions | Points entiers/fractionnaires ? Arrondi d'acquisition ? Restes monétaires conservés entre achats ? Conversion par blocs ou prorata ? | Points entiers, arrondi inférieur d'acquisition sans report de reste, conversion par blocs définis ; répartition FCFA déterministe P4.2 si fidélité = réduction |
| Barèmes et cumul | Valeurs acquisition/conversion, portée organisation/site, périodes et priorité si plusieurs règles ; catégories parentes/sous-catégories ; cumul avec remises | Aucun barème par défaut ; règle unique applicable par portée/date ; inclusion des sous-catégories à confirmer, sans moteur P9 |
| Compte et identité | Solde commun organisation ou par site ? Téléphone normalisé, unique ou partagé ? Carte perdue, opposition, remplacement, comptes existants ? | Compte partagé organisation proposé, utilisable seulement sur sites autorisés ; carte remplacée conserve le compte. Aucun compte réel créé pendant le cadrage |
| Utilisation et limites | Minimum de points, plafond de réduction, paiement intégral en points, catégories exclues, consentement client et droits d'utilisation | Valeurs configurables uniquement après validation ; bloquer l'utilisation sans barème applicable et sans solde suffisant ; aucun seuil inventé |
| Expiration et régularisations P4.5 | Points expirables ? Retour partiel après utilisation/crédit, annulation de règlement, points acquis déjà dépensés, solde négatif ou blocage ? | Journal compensatoire lié à la vente/ligne ; figer les barèmes d'origine ; restitution/révocation et traitement d'un solde insuffisant restent à décider, sans fonctionnalité P4.5 |
| Session de caisse | Fond d'ouverture, clôture/changement de caissier, comptage par mode, écarts et habilitations, session unique par caisse ? | Une session ouverte par caisse ; fond et comptage explicites. Circuit d'écart et contrôle avant changement à valider, sans seuil automatique |
| Numérotation et reçus | Moment d'attribution du numéro d'appel (validation ou transmission), dépassement 9999, paramètres ticket et contenu client | Attribution à transmission proposée ; blocage explicite au-delà de 9999 proposé, sans modulo/recyclage ; réinitialisation seulement après Z |

Ces propositions facilitent la validation mais ne constituent pas des règles implémentées. La fidélité sans paramètres applicables n'attribuera ni points ni réduction automatiquement ; décider si la vente peut continuer sans fidélité après confirmation explicite.

## Autorisations et interface prévues

Permissions candidates, à finaliser puis ajouter par migration additive : caisse.consulter/ouvrir/encaisser/fermer, caisse.mouvement.autoriser, fidelite.consulter/utiliser/parametrer et habilitations de régularisation futures. Elles réutilisent les rôles/permissions/affectations P1, sans is_admin ni droit du créateur. Contrôles 401/403/CSRF sur chaque mutation ; portée organisation/site/emplacement identique à l'écran et aux reçus/exportations.

Écran dédié d'encaissement : session, file des ventes transmises, détail figé, identification client, solde et réduction proposée, ventilation des règlements, confirmation explicite puis reçu. Raccourcis contextuels F1–F12 avec alternatives navigateur, scanner, Tab/Maj+Tab/flèches/Entrée/Échap et focus restitué ; aucune action financière déclenchée par une simple recherche ou consultation du solde. Les dialogues simples concernent ouverture/identification/saisies adaptées ; l'encaissement conserve un écran dédié.

## Validation prévue après décisions

- Calculs TTC/HT/TVA, cumul remises/fidélité, taux multiples, barèmes datés, périodes, conversion et arrondis ; catégories non éligibles, configuration absente, quantité/prix/règle modifiés.
- HTTP directs : droits et affectations, organisation/site/emplacement/session/client incompatibles, lecture seule, CSRF, crédit/tiers payant interdits, demande de remise non autorisée.
- PostgreSQL : deux caisses sur la même vente et sur le même compte, session fermée pendant paiement, finalisation concurrente avec Z, doublons de règlements/confirmation/numérotation, reprise après panne et rollback stock/caisse/points complet.
- Idempotence : double clic, réponse perdue, même clé et payload différent, impression échouée ; ni double vente, ni double sortie, ni double débit/crédit de points.
- Migrations additives sur bases jetables et données P1/P2/P3/P4.1–P4.3 conservées ; aucune base utilisateur modifiée.
- Chromium sans souris : session, client/carte/téléphone, points, règlements multiples, erreurs, actualisation, reçu et lecture seule ; non-régression proformas.

Arrêt requis après présentation de ce cadrage. Aucun développement financier P4.4 avant validation des décisions ci-dessus. PR #4 reste Draft, sans fusion ni déploiement.
