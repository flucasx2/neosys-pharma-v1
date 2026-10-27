# P5-B.1 — Moteur métier de prise en charge

## Portée

Ce module calcule une **simulation provisoire par vente et par ligne** à partir des instantanés métier fournis par l'application. Il n'écrit aucune donnée, ne crée aucune créance, ne finalise pas une vente et ne modifie aucun résultat historique. L'intégration persistante des résultats relève de P5-B.2.

Les identités P5-A restent les sources : organisme, convention versionnée, paramétrage daté, adhésion, titulaire et bénéficiaires couverts. Le service P5-B.1 reçoit leur projection typée (`ConventionCalcul`, `ParametragePrioriteCalcul`, `EvaluationDroits`) plutôt que de relire ou dupliquer les tables SQLAlchemy.

## Règles appliquées

1. Le paramétrage doit être actif à la date du calcul, appartenir à l'organisation de la vente, avoir des rangs contigus et des organismes distincts. Un principal est facultatif; s'il est présent, il occupe le rang 1. Les autres rangs sont parcourus dans l'ordre.
2. Une convention référencée mais absente ou incohérente bloque le calcul. Une convention inactive ou hors période est tracée comme non applicable et la séquence continue.
3. Un bénéficiaire `A_VERIFIER`, une preuve manquante, une adhésion invalide, un lien bénéficiaire non vérifié ou des droits appartenant à un autre bénéficiaire bloquent la vente entière. Un refus, une suspension ou une absence de couverture **explicitement vérifiés et justifiés** sont tracés comme non-éligibles; les organismes suivants sont évalués.
4. Les règles applicables sont exclusivement celles fournies dans un snapshot de convention validé. Une exclusion contractuelle explicite est tracée et permet de poursuivre. L'absence de règle applicable sans exclusion explicite, plusieurs règles applicables ou un attribut de ligne requis manquant bloquent la prise en charge de toute la vente.
5. Chaque taux s'applique au solde encore admissible de la ligne. Le montant calculé est limité au solde restant et, si le contrat le définit explicitement, au plafond **par ligne**. Les plafonds par période, cumuls, franchises et priorités entre barèmes chevauchants ne sont pas interprétés.
6. Les taux sont des fractions entières exactes. Aucun flottant binaire n'est utilisé. Si le produit d'un taux et du solde produit une fraction de XAF, le moteur bloque faute d'arrondi contractuel. `PLANCHER`, `PLAFOND` et `DEMI_SUP` sont acceptés seulement si l'un d'eux est présent dans la règle explicite.
7. Chaque étape conserve le rang, le rôle, la convention/version, l'adhésion/révision, la base initiale, le solde avant/après, la part couverte et les termes contractuels appliqués ou la raison d'inapplicabilité.
8. Pour un calcul admissible, chaque ligne satisfait `parts organismes + part client = net XAF`. Une partie bloquée rend indisponibles les totaux financiers de la vente; aucune créance n'est produite.
9. L'alternative comptant est seulement évaluée comme une décision et requiert le consentement explicite du client. Cette fonction ne crée ni vente, ni règlement, ni écriture P4.

## Contrat de données du moteur

`RegleCouverture` décrit un taux comme `taux_numerateur / taux_denominateur`, un sélecteur produit et/ou catégorie (intersection lorsque les deux sont précisés), un éventuel `plafond_ligne_xaf`, et un arrondi optionnel. Les exclusions explicites peuvent viser les produits ou catégories. Les montants d'entrée sont les nets historiques de lignes calculés par P4; le moteur ne recalcule ni prix, ni remise, ni taxe.

P5-A stocke `conditions` et `extensions_p5b` comme JSON déclaratif et ne fixe pas encore leur schéma de barèmes. P5-B.1 **ne déduit pas** la signification de clés JSON arbitraires. L'adaptateur à venir devra convertir uniquement les clauses contractuelles validées vers ces objets typés et refuser toute structure inconnue ou ambiguë.

## API Python

- Domaine : `neosys_pharma.domain.prise_en_charge.CalculateurPriseEnCharge`.
- Entrée : `DemandeCalculPriseEnCharge`, lignes, paramétrage ordonné, conventions et résultats vérifiés des droits.
- Sortie : `ResultatCalculPriseEnCharge`, étapes détaillées, erreurs métier codées et `SnapshotCalculPriseEnCharge` canonique/haché.
- Application : `neosys_pharma.application.prise_en_charge_service.SimulationPriseEnChargeService`.

Le snapshot porte l'identité de vente/organisation/site/bénéficiaire, la date de calcul, la version et révision du paramétrage, les résultats détaillés et un SHA-256 déterministe. Les champs `simulation_seulement=True` et `persistance_financiere_autorisee=False` empêchent de confondre le calcul provisoire avec une écriture financière.

## Suite prévue en P5-B.2

Définir et valider le schéma de projection des conventions, ajouter une lecture cohérente des versions P5-A, persister un snapshot de calcul immuable lié à la vente et à ses lignes, puis traiter la confirmation dans la transaction métier autorisée. La persistance ne devra pas recalculer les snapshots existants après un changement de priorité ou de convention.
