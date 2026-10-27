# Registre des exigences — P5-C

| ID | Exigence | Réalisation / preuve | Limite |
|---|---|---|---|
| P5-C1-01 | Source financière réellement confirmée uniquement | `CreanceService.source`, FK réalisation ; test avant/après encaissement | Pas de constitution depuis simulation |
| P5-C1-02 | Créance distincte par organisme, détail historique | UNIQUE réalisation/organisme, snapshot lignes/parts/étapes ; somme testée sur trois organismes | Aucune facture créée |
| P5-C1-03 | Idempotence et transaction | registre P3, verrou organisation, rejeux et rollback provoqué testés | Preuve de contention native préparée, non exécutée localement |
| P5-C1-04 | Isolation et immuabilité | FK composites, permissions dédiées, triggers et tests API/SQL | Validation native requise |
| P5-C1-05 | Retours et corrections auditables | retour consultable, engagement bloqué, montant initial inchangé | Écritures compensatoires de créance à développer séparément |
| P5-FAC-01 | Continuité documentaire P5-A/B vers créance | configurations et preuves figées réutilisées, sans ressaisie financière | Pas de génération de bordereau |
| P5-FAC-02.1–3 | Saisie comptoir partielle sans affaiblir les droits | finalité explicite ; legacy FINANCIERE ; vente avec pièces FACTURATION absentes testée | Une condition financière manquante reste bloquante |
| P5-FAC-02.4–6 | Module de contrôle, compléments, permissions | écran intégré Créances, formulaires, versions, auteur, contrôle distinct | Chromium local indisponible ; DOM simulé exécuté |
| P5-FAC-02.7–8 | Montants immuables, créance incomplète suivie | test des versions, conservation du hash, refus de changer une preuve financière | Aucun recalcul silencieux |
| P5-FAC-02.9 | Refus serveur d'engagement incomplet | quatre intentions testées : présentation, génération, validation, émission | Le futur module de facturation doit appeler ce garde dans sa transaction ; il n'est pas encore développé |
| P5-FAC-02.10–11 | États et séparation des snapshots | deux journaux immuables ; FACTURE réservé | Aucun passage artificiel à FACTURE |
| P5-FAC-02.12 | Non-régression comptoir, créance, garde | tests Python/API + DOM et régressions ciblées | Campagne humaine consolidée future |

## P5-C.2 — contrôle et documents (19/10/2026)

| Exigence | Livré / preuve locale | Réserve |
|---|---|---|
| P5-FAC-02.1–3 | Contrôles financiers au comptoir inchangés, compléments P5-C.1 réutilisés ; non-régression P5-B.3 | Pas d'assouplissement des droits/conventions |
| P5-FAC-02.4–6 | Recherche serveur paginée, anomalies, compléments/contrôle C1, sélection éligible ; DOM 27 assertions | Chromium et parcours réel natif non exécutés |
| P5-FAC-02.7–8/11 | Snapshots financiers conservés ; préparation et versions distinctes ; cycle migration avec vraie créance C1 fictive | PostgreSQL natif à valider |
| P5-FAC-02.9 | Garde C1 réutilisé dans transaction de préparation, prévisualisation, validation et émission ; dossier modifié après validation refusé | Émission production fermée, protocole de recette seulement |
| P5-FAC-02.10 | Passage FACTURE par version append-only lors de l'émission test ; aucune modification du montant | Régularisations/avoirs non livrés |
| P5-FAC-02.12 | Incomplet/refus/révision/permissions/CSRF/retours/rollback/idempotence testés sur SQLite | Les tests natifs ignorés ne valident pas la concurrence |
| P5-C2-01 | Bordereau multi-créances, un organisme/convention/site, préparation/abandon/retrait, référence unique de recette | Politique définitive et période contractuelle à arbitrer |
| P5-C2-02 | Facture liée ou indépendante du bordereau, PDF figé et sha, identité/auteur/période/détail/total | Conformité fiscale non attestée ; émission hors contexte jetable refusée |
| P5-C2-03 | Récapitulatif et lot facultatifs, membres uniques, liens consultables depuis créance | Représentations/rejets/agrégations intersites non implémentés |
| P5-C2-04 | Retour avant engagement ou après facture bloque les regroupements ; historique conservé | Aucune compensation silencieuse ; dossiers concernés bloqués jusqu'au sous-lot de régularisation |
| P5-C2-05 | Permissions explicites, FK organisationnelles, révisions, audit, unicité et immuabilité | Validation native et charge/concurrence requises |

Les lignes P5-C.1 ci-dessus sont conservées comme état de livraison historique ; les mentions de futur module sont actualisées par cette section. Référentiel détaillé et UML technique : P5_C_2_DOCUMENTS_ORGANISMES.md.
