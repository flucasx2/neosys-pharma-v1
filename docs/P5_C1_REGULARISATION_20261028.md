# P5-C1 / REG-01 — Incrément 1 (28 octobre 2026)

## Périmètre implémenté localement

- Nouvelle écriture `tiers_payant_compensations_creances`, append-only, liée à une créance, un retour P4, un auteur et une organisation. Unicité créance/retour, montant positif, hash, contraintes organisationnelles et triggers d'immutabilité.
- Endpoint C1 sous permission `tiers_payant.creance.regulariser`, exécution dans l'opération idempotente et le verrou organisationnel existants, audit de l'écriture.
- Compensation calculée à partir du montant P4 du retour et de la part historique P5-B. L'allocation est admise uniquement si les parties P5-B prouvent un seul organisme positif représentant tout le total organismes de la ligne, et si les totaux du détail et du snapshot P4 concordent.
- Montant/snapshot de créance d'origine inchangés. Le détail retourne le total compensé et le solde effectif, défini comme montant d'origine moins écritures compensatoires.
- Validation et engagements demeurent bloqués tant qu'une ventilation est ambiguë ou qu'une compensation attendue est absente. Les dossiers engagés, présentés ou facturés refusent la compensation.
- P5-C2 utilise le solde effectif dans les sélections, snapshots et lignes de bordereau/facture; les regroupements refusent encore toute compensation manquante ou ambiguë.

## Cas toujours bloqués / décisions métier

- Retour multi-organismes : le retour P4 ne ventile pas sa part agrégée entre payeurs; aucun prorata ni règle d'arrondi n'est inventé.
- Retour historique avec colonnes ou lignes ventilées absentes, ou montants incohérents : blocage et revue manuelle.
- Créance déjà engagée, présentée, ou document facturé : traitement documentaire/avoir hors incrément.
- Une annulation P4 d'une demande de remboursement ne renverse pas le retour physique/financier; aucun contre-mouvement automatique.
- Avoirs fiscaux, annulations/rejets documentaires, règlements organismes et nouvelles présentations hors périmètre.
- Une annulation de vente P4 avant encaissement ne crée pas de réalisation P5-B et ne donne pas lieu à créance compensable.
- Les anciennes opérations génériques CNAMGS sans réalisation P5-B ne sont pas converties ni réécrites.

## Tests préparés et preuves

- Domaine : attribution payeur unique, refus multi-organismes/incohérent, montant nul sans part organisme.
- HTTP/C1 : refus sans écriture pour un retour multi-organismes; conservation du snapshot/montant et maintien du blocage d'engagement.
- Migration : assertions de table, unicité, checks, triggers et refus de downgrade avec écriture présente prévus dans le cycle déjà protégé; la migration PostgreSQL suit le garde jetable existant.
- Contrôles locaux : `git diff --check`, compilation syntaxique et tête Alembic statique réussis. Le lancement pytest et `alembic heads` avec le Python système a été bloqué, faute des paquets `pytest`/`alembic`; aucun test avec base ni migration n'a été exécuté.

La recette technique ciblée doit encore vérifier le chemin nominal à payeur unique, les refus d'engagement, les montants C2 et les triggers sous SQLite et PostgreSQL jetables. Aucun commit, push, merge ou déploiement.
