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
