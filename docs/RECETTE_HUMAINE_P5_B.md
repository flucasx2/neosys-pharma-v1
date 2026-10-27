# Cahier de recette humaine — P5-B

À exécuter uniquement sur environnement isolé et base jetable, avec comptes et
données fictifs. Ne pas activer de règlement tiers en production. Les montants
attendus sont en XAF entiers.

| ID | Scénario | Résultat attendu |
|---|---|---|
| B-01 | Créer une vente comptant P4, la préparer, transmettre et encaisser | Parcours P4 individuel inchangé, reçu individuel et mouvements inchangés. |
| B-02 | Créer une vente en mode organisme, saisir deux lignes et associer un bénéficiaire distinct du client | La sélection est explicite; aucun changement au total TTC ou à l'identité historique de la vente. |
| B-03 | Simuler avec convention v1 et priorité v1 valides, principal puis deux secondaires | Parts visibles par ligne et organisme; chaque part est bornée par le solde restant; total organismes + client = total net. Aucune créance ni écriture de caisse. |
| B-04 | Faire varier un plafond explicite par ligne puis simuler | Les secondaires reçoivent seulement le solde après le plafond; snapshot de simulation précédent demeure inchangé. |
| B-05 | Retirer l'arrondi d'un barème fractionnaire | Simulation bloquée avec le code d'arrondi; aucun résultat partiel n'est confirmé. |
| B-06 | Ajouter une clé JSON inconnue, une période expirée ou une clause de plafond cumulatif non prise en charge | Refus explicite et aucun montant financier confirmé; ne pas contourner le refus. |
| B-07 | Droit A_VERIFIER ou relation bénéficiaire non valide | Blocage global du calcul; pas de ventilation partielle persistée. |
| B-08 | Droit REFUSES/SUSPENDUS avec preuve d'adhésion | Décision tracée comme inéligible; l'organisme suivant est évalué selon l'ordre configuré. |
| B-09 | Confirmer une simulation admissible avant transmission | Refus; aucun snapshot définitif. |
| B-10 | Transmettre avec permission tiers payant, confirmer le snapshot avec la même clé et le même contenu | Une seule ligne d'en-tête et ses lignes/parts/étapes; deuxième appel rend le résultat initial. |
| B-11 | Rejouer la clé avec autre bénéficiaire ou révision | Conflit idempotence; snapshot initial inchangé. |
| B-12 | Confirmer la même vente avec une nouvelle clé, puis tenter SQL UPDATE/DELETE | Conflit unicité; snapshots append-only, le changement SQL est refusé. |
| B-13 | Sélectionner un bénéficiaire d'une autre organisation ou consulter depuis un autre site | Refus 403/404, sans fuite du snapshot. |
| B-14 | Ouvrir le panneau depuis une vente sans `tiers_payant.consulter` ou sans `tiers_payant.adhesion.consulter` | Panneau masqué et endpoints protégés; aucun élargissement de permission. |
| B-15 | Après snapshot confirmé, ouvrir la vente tiers dans la caisse et régler uniquement sa part client | Le total de vente historique reste inchangé; paiement et reçu portent la part client; les parts organismes sont distinctes; une réalisation organisme immuable est écrite dans la transaction du reçu. Aucun bordereau, facture ou règlement organisme n'est créé. |
| B-16 | Encaissement individuel sans organisme et reçus historiques | Aucun changement sur le parcours comptant; vérifier totaux par mode, mouvement de caisse et clôtures X/Z. |
| B-17 | Vente transmise en mode organisme sans snapshot confirmé | La caisse affiche la vente, indique que la prise en charge doit être confirmée, et ne propose pas l'encaissement client. |
| B-18 | Une vente de 2 005 XAF avec un principal et deux secondaires à 20 % chacun | Calcul séquentiel exact attendu : 401, 320 et 256 XAF organisme, puis 1 028 XAF client. Vérifier que les fractions restent des XAF entiers et que le total est équilibré. |
| B-19 | Encaisser 1 028 XAF par carte (514) et espèces (514) après confirmation de la carte | Un seul encaissement de 1 028 XAF; le total de vente reste à 2 005 XAF; aucun mouvement n'est créé pour les 977 XAF organismes; session et reçu affichent les mêmes parts. |
| B-20 | Même scénario avec un barème acquisition de 1 point / 1 000 XAF et une ligne cosmétique admissible | Un point est acquis à la vente encaissée (part client 1 028 XAF), contre deux si la part organisme était à tort comptée. Répéter l'appel avec la même clé : aucune deuxième acquisition. |
| B-21 | Remplacer la nature de produit par médicament ou une nature inconnue, avec le même barème | Aucun point acquis, même si le client règle une part. Aucun médicament ni produit non explicitement cosmétique ne génère de fidélité. |
| B-22 | Retourner 10 puis 10 unités d'une ligne de 20 unités; rembourser chaque retour par son mode d'origine | Chaque retour conserve TTC, part client et part organismes. Les remboursements cumulés ne dépassent ni les paiements d'origine ni la part client remboursable. Les parts organismes restent en attente des écritures P5-C. |
| B-23 | Consommer auparavant les points du reçu (journal historique fictif), puis retourner intégralement la vente en deux opérations | L'historique n'est pas supprimé; chaque retour crée une compensation une seule fois; le solde reste non négatif et la dette de points ne dépasse pas la révocation nette calculée. |
| B-24 | Rejouer le finalisateur avec la même clé, puis avec une nouvelle clé; rejouer le retour avec sa clé | Même clé et même contenu rendent le reçu initial. Nouvelle clé ne crée aucun deuxième encaissement. Le retour rejoué ne crée pas de second dossier ni de double compensation. |
| B-25 | Encaisser un groupe P4 comptant de plusieurs ventes pendant la recette | Parcours groupé comptant inchangé. Les ventes tierces ne sont pas encore acceptées par le moteur de groupe; ne pas contourner son refus et ne pas activer le flag. |
| B-26 | Provoquer une erreur de génération du PDF après calcul confirmé, puis retenter avec la même clé | Aucun encaissement, mouvement, consommation de stock, point ou réalisation organisme ne subsiste après rollback; la reprise identique crée un seul reçu et un seul mouvement complet. |

Consigner pour chaque ligne l'identifiant fictif de vente, l'organisation/site,
les versions P5-A, la révision, le code d'erreur éventuel, la clé
d'idempotence utilisée, les montants détaillés et les captures nécessaires.
Ne jamais mettre dans le compte rendu des noms ou données réels de patients.

**Critère de recette P5-B complet :** tous les scénarios autorisés sont réussis,
les snapshots sont vérifiables, et une décision métier distincte valide le
traitement des parts organisme, les créances, remboursements, retours et points
de fidélité avant d'activer l'encaissement final tiers.

## Limites et précautions P5-B.3

- La part organisme encaissée est conservée dans un registre immuable par vente,
  lié à l'encaissement et au calcul. P5-C devra transformer ce registre en
  créances et documents de facturation selon ses propres règles.
- Les retours clients P4 remboursent uniquement la part client; le retour garde
  aussi le TTC historique et la part organisme. Le traitement comptable du
  remboursement dû par chaque organisme reste à livrer dans P5-C.
- Le moteur de groupe P4 continue de refuser les ventes en mode tiers. Les
  encaissements groupés comptant restent couverts par le parcours existant;
  l'extension multivente avec parts organismes nécessite une adaptation P5-C
  atomique distincte.
- Le barème de fidélité demeure celui configuré dans l'application. Avant
  activation métier, vérifier qu'il est paramétré à 1 point par 1 000 XAF.
