# Résultats — P5-B.1

## Référence et périmètre

- Base : `recette/p5a-postgresql` au commit exact `ebbe37e7fa241e9b29e3a9eb83c53635bf3f8e15` (parent `2910cc60e8c8287a587ce8ff8e3f48c95be1ba39`).
- Branche locale isolée : `feat/p5-b-moteur-prise-en-charge`.
- Aucun changement à `main`, aux migrations, aux bases conservées, à l'interface ou aux services P4.
- Aucun endpoint n'est activé et aucun calcul définitif ou créance n'est persisté.

## Matrice des exigences

| Exigence | Résultat | Preuve |
|---|---|---|
| Réutiliser les organismes, conventions, adhésions et priorités P5-A | Couvert par projection typée des identités P5-A, sans nouvelle entité SQL | `domain/prise_en_charge.py`, tests P5-B.1 |
| Priorité principale facultative et secondaires successifs | Couvert, ordre strict par rang | Tests principal seul, principal + deux secondaires, secondaires sans principal |
| Vérifier organisation, convention, dates et droits | Couvert dans les snapshots de calcul; données absentes ou incohérentes bloquent | Tests périmètre, convention absente/expirée, preuve de droits et périodes |
| Refus ou non-couverture explicitement vérifiés | Tracés comme étapes non éligibles; la séquence continue | Tests refus, suspension et bénéficiaire non couvert |
| Taux et plafonds explicitement fournis | Couvert pour fraction exacte et plafond **par ligne** | Tests taux successifs, principal plafonné et plusieurs plafonds |
| Exclusions contractuelles explicites | Couvert et tracé | Test exclusion principale suivie par secondaire |
| Arrondis XAF | Aucun arrondi implicite; blocage si fraction sans clause | Tests fraction sans arrondi et arrondi explicite |
| Calcul différencié par ligne et solde client | Couvert; invariant contrôlé pour chaque ligne | Tests de plusieurs lignes, plafonds et sommes |
| Blocage global si une ligne est incalculable | Couvert, totaux financiers du résultat indisponibles | Test ligne sans règle dans une vente multiligne |
| Prévention de doubles couvertures / entrées répétées | Couvert par consommation successive du solde, unicité des organismes/adhésions/IDs de lignes | Tests plafonds, organisme/adhésion/ligne dupliqués et bornes d'allocation |
| Snapshot historique à l'ordre et aux versions utilisées | Structures immuables, version/révision, étapes et hash déterministe | Test changement de priorité sans modification du snapshot existant |
| Vente comptant après blocage et accord explicite | Décision vérifiée uniquement; aucune finalisation P4 | Test consentement requis/obtenu et marqueur de simulation |
| API, persistance définitive, créances, remboursement | Reportés conformément à la limite P5-B.1 | Aucun endpoint, migration ni write-model ajouté |

## Contrôles exécutés

| Commande / contrôle | Résultat |
|---|---|
| Python 3.14.8 — `pytest -q tests/test_p5b_1_moteur_prise_en_charge.py` | **30 réussis** |
| Python 3.14.8 — `pytest -q tests/test_p5a_tiers_payants.py` | **5 réussis**, 1 avertissement de dépréciation `Starlette TestClient`/`httpx` |
| Python 3.14.8 — `pytest -q tests/test_clients_p4b.py tests/test_encaissement_groupe_domain.py tests/test_encaissement_groupe_persistance.py tests/test_caisse.py` | **57 réussis, 7 ignorés, 3 sous-tests réussis**, 1 avertissement de dépréciation |
| `compileall` des modules P5-B.1 | Réussi |

Les 7 tests ignorés de la suite de régression conditionnent les migrations P4-B/P4-C PostgreSQL jetables ou la concurrence PostgreSQL native (`Deux connexions PostgreSQL requises`). Aucune base PostgreSQL n'a été utilisée ou modifiée. Chromium n'a pas été exécuté : aucun changement d'interface n'est inclus dans cet incrément.

La suite de migration P5-A incluse dans `test_p5a_tiers_payants.py` a été exécutée sur son SQLite temporaire de test et a réussi. Elle ne valide pas PostgreSQL natif.

## Arbitrages techniques restant avant P5-B.2

1. P5-A ne définit pas encore de schéma de barèmes dans `conditions`/`extensions_p5b`. P5-B.1 n'interprète donc pas de JSON arbitraire; il expose des objets typés et bloque toute clause manquante ou ambiguë.
2. Seul le plafond par ligne est représenté. Les plafonds de période, cumuls, franchises, priorités entre barèmes chevauchants, mode et assiette d'autres formes de prestations ne sont pas inventés.
3. Pour un résultat fractionnaire en XAF, la confirmation est bloquée à moins qu'un mode d'arrondi figure explicitement dans la règle fournie. Les valeurs possibles du DTO ne définissent pas un arrondi par défaut.
4. Le client comptant alternatif est une décision contrôlée par consentement; P5-B.1 ne transforme pas cette décision en vente P4.

## Suites avant P5-B.2

- Valider/formaliser la projection des règles de convention P5-A vers les objets de calcul typés.
- Ajouter des tests d'intégration avec modèles P5-A et isolation organisationnelle.
- Définir les tables et contraintes additives pour snapshots, étapes et répartitions immuables.
- Lier la confirmation à la vente en gardant le calcul et l'écriture dans la transaction métier appropriée.

P5-B.1 est livré comme moteur pur testé. **Cela ne valide ni une prise en charge persistée, ni une intégration opérationnelle dans le parcours de vente.**
