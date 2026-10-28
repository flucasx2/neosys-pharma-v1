# Plafonds consommables — décisions nécessaires avant implémentation

Le principal facultatif, les secondaires multiples ordonnés au niveau organisation et la transmission du reliquat après plafonnement sont déjà validés. Ils ne sont pas remis en discussion. Les plafonds par ligne déjà explicitement définis continuent d'être calculés par le moteur existant.

La consommation individuelle/périodique n'est pas implémentée par ces incréments. Les éléments suivants doivent être fixés contractuellement avant de créer des compteurs et engagements financiers. Aucune valeur par défaut ne doit rendre admissible une convention ambiguë.

| Sujet | Décision nécessaire | Risque sans décision |
|---|---|---|
| Période | Année/mois civils, période contractuelle ou fenêtre glissante ? Date de départ et fuseau applicables ? | Remise à zéro erronée des droits |
| Titulaire du compteur | Bénéficiaire individuel, famille/titulaire, adhésion ou convention ? Un compteur partagé entre plusieurs adhésions ? | Double consommation ou transfert abusif de droits |
| Assiette | Montant couvert réellement par cet organisme, base éligible ou dépenses client ? Plafonds par produit/catégorie et cumul global ? | Plafond appliqué à la mauvaise somme |
| Engagement | Réserver à la confirmation du snapshot, consommer à l'encaissement, ou autre événement contractuel ? Durée/libération des réservations ? | Double disponibilité ou droits bloqués par un abandon |
| Retours | Restitution possible ou non ? Crédit de la période d'origine ou actuelle ? Retour après expiration ? | Droits artificiellement recréés |
| Annulation | Libération intégrale d'un engagement non encaissé ; traitement d'un encaissement déjà réalisé et d'une créance présentée ? | Décalage caisse, droits et créances |
| Plafonds successifs | Lorsque plusieurs plafonds d'un même organisme se croisent, quelle hiérarchie et quels compteurs sont débités ? | Double débit du même montant |
| Révision de convention | Report des consommations existantes vers une nouvelle version ? Compteur partagé ou distinct selon la clause ? | Modification rétroactive ou remise à zéro abusive |
| Régime | Quel choix explicite parmi plusieurs régimes admissibles ? Qui peut le sélectionner et quelles preuves ? | Choix arbitraire du régime le plus favorable |

Exemple à arbitrer : organisme A limité à 50 000 XAF par année ; 40 000 déjà consommés ; nouveau calcul admissible de 20 000. Avec un compteur portant sur les montants réellement couverts, A couvre au plus 10 000 et le reliquat va au secondaire selon sa convention. Un retour de 5 000 après changement d'année peut soit reconstituer 5 000 sur l'ancienne période, soit ne rien reconstituer ; créditer automatiquement l'année courante serait une nouvelle règle, non validée.

Choix techniques proposés après arbitrage : journal append-only des réservations/consommations/restitutions, références de vente/ligne/snapshot et opération idempotente, verrouillage déterministe des compteurs, aucune modification des anciens snapshots. Il s'agit d'une proposition technique ; elle ne tranche aucune règle contractuelle du tableau.

Les développements indépendants peuvent continuer. Le calcul confirmé d'une clause de plafond non interprétable doit rester refusé ; ne pas contourner ce refus pour commencer P5-C.


## Décision courante du 28 octobre 2026 — périmètre neutralité V1

Pour les nouvelles confirmations V1, les anciennes formulations principal facultatif/secondaires multiples/transmission systématique du reliquat sont remplacées par un principal obligatoire, au plus un complémentaire et une conduite contractuelle explicite. Un plafond par ligne atteint déclenche la politique PLAFOND ; un reliquat hors plafond déclenche ECART. CLIENT, SUIVANT et BLOQUER doivent être définis dans chaque convention ; aucun transfert automatique. Les compteurs périodiques et les arbitrages du tableau restent hors de la correction. Voir [contrat et limites](P5_NEUTRALITE_ORGANISMES_20261028.md). Préparé, non testé et non appliqué sur une base ; aucune décision historique supprimée.
