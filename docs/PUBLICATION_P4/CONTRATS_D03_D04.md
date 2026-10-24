# Contrats P4-05 acceptés

## D03 — Réception physique de retour

Le reçu autonome atteste la réception en quarantaine et ne vaut pas remboursement. Retour, lignes, quarantaine, PDF, empreinte et audit sont atomiques. Le document utilise les prix et identités historiques ; il est immuable et réimprimable sans régénération. Les anciens retours sans pièce restent tels quels, sans backfill implicite. Les permissions existantes de consultation/gestion de retour déterminent son accès, sans session de caisse supplémentaire imposée au vendeur autorisé.

## D04 — Annulation de demande non exécutée

Seuls DEMANDE et AUTORISE sont annulables. EXECUTE et ANNULE sont terminaux. La permission caisse.remboursement.annuler est explicite et jamais attribuée implicitement. Justification, attestation du responsable, révision et clé d’idempotence sont obligatoires. L’incertitude sur une restitution externe interdit l’annulation. Toute pièce, preuve, écriture ou remboursement lié interdit l’annulation.

Une annulation après fermeture est possible au responsable habilité sans mouvement de caisse. Le budget réservé est libéré une fois ; l’historique reste intact. Un remplacement exige une nouvelle demande explicitement liée. Annuler la demande ne supprime jamais une obligation de restitution bloquant le Z normal. Aucun remboursement exécuté ne peut être annulé.

## Autres corrections du même lot

S01 applique les règles P3 de conditionnement et de péremption à la libération sanitaire. U01 protège générations, contextes, erreurs, modales clonées et reprises GET sans rejouer une mutation. C06 présente les écritures historiques X/Z en distinguant brut, rendu, net, remboursements exécutés, fonds, transferts, attendu, compté et écart ; aucun nouveau calcul métier de solde ou écriture financière.

## Migrations

Chaîne additive : 20261019_06 → 20261022_01 → 20261022_02. MIG-01 ajoute les documents de retour immuables. MIG-02 ajoute l’état terminal d’annulation, le remplacement, les gardes d’intégrité et la permission non attribuée. Un downgrade destructeur d’historique est refusé. Les dix migrations entre la tête actuelle de main et 20261019_06 sont des prérequis existants à examiner séparément, pas des migrations nouvellement conçues dans ce lot.
