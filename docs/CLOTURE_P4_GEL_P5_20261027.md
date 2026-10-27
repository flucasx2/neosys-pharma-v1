# Clôture P4, gel P5 et continuité documentaire — 27 octobre 2026

> **Décision du propriétaire — références Git du 27 octobre 2026.** Publication : `origin/main` attendu à `2910cc60e8c8287a587ce8ff8e3f48c95be1ba39`. `main` local conservé à `fe53c42dc89d79618290b182aae29b01d8cb42d6`, aucune synchronisation autorisée. La différence est acceptée comme anomalie connue ; l'ancien audit reste inchangé avec son échec conservé. Adaptation ciblée proposée pour contrôler séparément les deux SHA, à autoriser avant application. Les preuves locales sont acceptées. Préparation du plan de commits uniquement : aucun commit, intégration, merge ou push autorisé à cette étape.

Mise à jour : 2026-10-27T13:44:16, Africa/Lagos, Codex.

**GO technique local du périmètre candidat ; NO-GO intégration/publication avant décision sur les références et autorisations distinctes. Aucun GO de fusion/déploiement.** P4 est accepté humainement dans son périmètre ; il n'est ni fusionné ni déployé. P5 historique reste incomplet, gelé, non accepté globalement. Ce rapport ne rouvre pas la recette P4 et ne conditionne pas sa clôture à une validation exhaustive P5.

## 1. Bilan et résultats vérifiés

Le [rapport technique consolidé](STABILISATION_GLOBALE_P4_20261027.md) est la référence unique des bilans complets, versions, sources, preuves et limites. Il conserve l'échec initial de fixture et sa reproduction au lieu de les remplacer par les essais corrigés. Les [matrices préalables](MATRICE_STABILISATION_GLOBALE_P4_20261025.md) restent conservées.

Chromium : 20/20 scénarios réels sur PostgreSQL jetable, par trois segments de dépendance. Contrôles CI locaux : 48/48 prérequis, 51/51 P4-05 ; gardes8/8. Les suites prérequis complètes sont terminées ; PostgreSQL17 P4-05 corrigée est terminée. La présence d'un résultat partiel dans les autres logs ne vaut pas réussite. Les sous-tests ne sont pas ajoutés aux nombres de tests principaux.

Aucune nouvelle campagne exploratoire P5 lancée pour cette mission. Les suites déjà en cours contiennent historiquement des tests P5 : on les laisse terminer sans retrait de tests. Aucun changement de règle financière accepté en recette : les treize candidats touchent seulement les tests/fixtures ; la comparaison de tous les fichiers suivis des deux arbres ne trouve aucune différence de production, migration, permission ou dépendance. Les assertions historiques sont conservées, sauf un ancien sélecteur de carte remplacé par des contrôles plus stricts d'identité et de montant. Source : `.audit-publication/global-stabilization/results/whole-candidate-audit-linux20.json`.

## 2. Isolation des composants historiques P5

Analyse statique des arbres publiables `c88151d4d5e899c564c8cddb6a8760de3f99875a` et `37ed8350bf840e676fc3f4f3cd4fb6f30601c45f`. Elle ne certifie pas les configurations ni droits des bases conservées : aucune connexion à ces bases.

| Composants présents | Dépendance / possibilité de gel | Décision minimale |
|---|---|---|
| Moyens configurables, fournisseurs, confirmations immuables, cartes clients, bilan import catalogue, adaptations CI issus de l'historique mixte | Utilisés par les flux P4/B01–B04 ; l'origine du commit ne définit pas une frontière fonctionnelle | Conserver. Aucun retrait de modèles, snapshots, contrats API ou migrations |
| P5-A organismes/bénéficiaires ; P5-CONF conventions/régimes/droits ; P5-B calculs et réalisations | `vente_service.py` vérifie les droits pour une vente avec tiers ; `caisse_service.py` importe les calculs et crée les réalisations ; P4-05 `regularisation_service.py` utilise les modèles de prise en charge | Dépendances techniques à conserver. Ne pas modifier CNAMGS/mutuelles/organismes, ni activer de nouveaux usages non validés |
| Imports bénéficiaires et configuration P5 | Interfaces et routes présentes, permissions explicites ; pas de preuve d'un interrupteur global | Gel de développement et d'usage non validé ; ne pas annoncer une neutralisation technique automatique |
| P5-C1 créances/dossiers et contrôle administratif | Consomme les réalisations, routes enregistrées dans `app.py`, droits `tiers_payant.creance.*` ; pas de garde global d'inactivité démontré | Peut rester sans utilisation autorisée, mais inactivité absolue non certifiée. Aucun changement de droits ou de données dans cette mission |
| P5-C2 préparations, versions, engagements et PDF de recette | Routes présentes. `emission_isolee_autorisee` exige CI, marqueur, confirmation, PostgreSQL loopback et base jetable préfixée ; l'émission ordinaire est refusée. Cela ne désactive pas toutes les opérations préparatoires | Conserver garde fermé hors recette ; aucune activation, numérotation fiscale ou acceptation P5 déduite des tests |
| Finalisation groupée P4-C avec extensions organismes historiques | `_grouped_encashment_enabled` vérifie flag, CI, confirmation et base `neosys_browser` loopback ; scénario Chromium utilise ce contexte jetable. Ce n'est pas une autorisation d'activation en exploitation | Conserver les gardes et les résultats de recette P4 ; pas de modification d'activation |
| Seize journaux de preuve exclus | Absents des historiques publiables contrôlés ; certains chemins historiques existent dans le checkout B04 conservé | Maintenir l'exclusion. Ne pas copier en bloc docs/ ou l'archive d'audit dans les commits |

**Aucune exclusion de code supplémentaire imposée pour les deux PR existantes.** Une éventuelle branche P4 strictement débarrassée des fonctions P5 est un autre périmètre, contraire à la reconstruction déjà abandonnée s'il implique de retirer les dépendances. Les candidats fonctionnels à extraire seraient les routes/écrans C1/C2 et imports/configurations exclusivement P5, après analyse de graphe modèles/migrations/permissions et autorisation distincte. Ne pas supprimer leurs migrations ou réécrire les vingt commits mixtes pour réaliser cette séparation. Rien de cela n'est appliqué ici.

La conservation du code est compatible avec le gel demandé ; elle ne vaut pas certification de sécurité de toute activation P5. Si le propriétaire exige une interdiction technique totale d'accès aux routes P5 plutôt qu'un gel opérationnel, un périmètre distinct de désactivation devra être approuvé ; aucune modification métier ou permission n'est faite par anticipation.

## 3. Périmètre technique candidat à intégrer

Treize fichiers de tests/fixtures :

- `tests/browser_p1.py`
- `tests/browser_p2.py`
- `tests/browser_p2_complete.py`
- `tests/browser_p3.py`
- `tests/browser_etats_p3.py`
- `tests/browser_p4.py`
- `tests/browser_proforma.py`
- `tests/browser_caisse.py`
- `tests/browser_regularisation.py`
- `tests/browser_clients.py`
- `tests/fidelite_historique_ui.cjs`
- `tests/seed_browser_caisse.py`
- `tests/test_p5c2_migration.py`

Plus `.github/workflows/tests.yml` : une seule ligne proposée, budget du job PostgreSQL20→30minutes. Les annotations GitHub prouvent le dépassement de20minutes ; aucun allongement du focus Playwright. Patches alternatifs par branche dans `.audit-publication/global-stabilization`, SHA de base et hashes tracés. Aucun patch appliqué aux branches de publication ni commit créé.

Les deux patches de tests ne doivent pas être appliqués successivement sur le même arbre. Après autorisation, propager les changements communs par une intégration Git standard préservant l'historique, en conservant le test Alembic spécifique P4-05 et les commits propres. Aucun nouveau commit sans validation finale de périmètre.

## 4. Documents actualisés et conservation

| Document | Mise à jour |
|---|---|
| JOURNAL_DEVELOPPEMENT.md | Entrée datée ajoutée ; tous les octets précédents conservés ; PROGRESS précédent archivé intégralement dans cette entrée |
| PROGRESS.md | État courant, IA/date, résultats et limites, P4 non fusionné, gel P5, blocages et prochaines décisions |
| REPRISE_NEOSYS_PHARMA.md | Nouvelle section courante prioritaire ; ancien guide conservé intégralement, anciennes poursuites P5 explicitement remplacées |
| AGENTS.md | Politique documentaire cumulative ajoutée après les protections existantes, sans retirer de règle |
| README.md | Renvoi initial vers l'état courant, mention des jalons historiques et protections avant commandes |
| STABILISATION_GLOBALE_P4_20261027.md | Rapport courant consolidé, pas une réécriture des preuves antérieures |
| CLOTURE_P4_GEL_P5_20261027.md | Présent bilan de décision, isolation, inventaire et différences |

L'inventaire daté des fichiers de suivi est conservé dans `.audit-publication/global-stabilization/results/documentation-inventory-20261027.json`. Architecture et modules : README, P1/P2/P3/P4, B01, documents P5-A/B/CONF/C1/C2. Roadmap et arbitrages : ETAT_P4_P5_03_07, RECETTE_CONSOLIDEE_P4_P5, ARBITRAGES_PLAFONDS_P5, REGISTRE_EXIGENCES_P5_C et REGISTRE_NON_CONFORMITES_P5. Recettes/validation : rapports B03/B04, P4-05 et rapports de stabilisation/intégration. Leurs jalons et preuves restent historiques ; aucun cahier métier n'est réécrit pour déclarer P5 terminé.

Diff documentaire depuis l'état observé avant mise à jour : `.audit-publication/global-stabilization/documentation-closure.patch`. Pour PROGRESS et les rapports initialement non suivis, ce diff de fichiers est nécessaire : `git diff` seul ne les montre pas. Les instantanés initiaux et leurs hashes restent dans l'audit local ; ils ne sont pas des fichiers de preuve à publier.

## 5. Contradictions documentaires qualifiées

- Ancien PROGRESS : cause Caisse inconnue, matrice non vérifiée, scénarios masqués. Remplacé par les preuves locales ; texte précédent conservé au journal.
- Ancien guide de reprise : poursuivre P5/C1/C2 et lancer des recettes anciennes. Remplacé par la décision de gel du27octobre ; toutes les sections historiques restent lisibles.
- README contient des descriptions de jalons P1/P2 et une ancienne phrase annonçant l'absence de P3. Le renvoi courant précise leur caractère historique ; il ne faut pas l'interpréter comme inventaire actuel.
- `docs/ETAT_P4_P5_03_07.md` indique que P5-C n'existait pas à ce jalon ; C1/C2 ont été ajoutés ensuite. Conserver les deux preuves temporelles, sans présenter l'une comme l'état courant.
- `docs/DOCKER_LOCAL.md` décrit la mise en service de développement du20octobre et l'absence de tests à cette étape. Les campagnes d'audit ultérieures, distinctes, ne modifient pas cette observation passée.
- `docs/CI.md` décrit PostgreSQL20minutes. La proposition30minutes n'est pas encore intégrée ; le document n'est pas changé pour annoncer une configuration future déjà effective.
- Les fichiers de recette P405R2 cités par l'ancien suivi ne sont pas tous présents dans ce checkout. Absence locale ne signifie pas suppression de preuve : ne pas reconstruire ni toucher aux checkpoints pour combler ce manque.
- Les anciens rapports d'intégration publient d'anciens SHA valides à leurs dates. Les nouveaux candidats n'ont aucun SHA de commit ; ne pas leur attribuer ceux des anciennes PR comme validation GitHub de leur contenu.
- `main` local vaut `fe53c42dc89d79618290b182aae29b01d8cb42d6`, dernier mouvement au10octobre selon reflog ; `origin/main` et la base GitHub PR14 valent `2910cc60e8c8287a587ce8ff8e3f48c95be1ba39`. Les branches de publication sont conformes. Le contrôle local d'égalité a échoué et reste en échec explicite ; aucune référence n'est modifiée ou synchronisée. La revue automatique a refusé l'adaptation de l'audit qui aurait accepté cette différence, pour éviter de masquer une divergence. Faire préciser la politique de référence locale avant une opération Git d'intégration/publication.

## 6. Autorisations et point d'arrêt

Autorisé : campagnes locales existantes sur bases jetables, diagnostic et préparation de candidats, mises à jour documentaires présentes. Aucune connexion aux bases conservées, aucune intervention sur P405R2,8001/8003/8004/8005,C0/C1/C2/CFINAL. Aucun secret réel lu ni copié. Les historiques publiables et fichiers candidats ont passé Gitleaks sans détection ; les seize journaux privés restent exclus.

Restent à autoriser après consolidation : intégration et commits du périmètre technique/documentaire exact ; publication standard des futures têtes ; campagnes GitHub complètes sur leurs SHA exacts ; opérations de revue/fusion séparées. Aucune activation P5, aucun changement de règle de prise en charge, aucun déploiement autorisé.

À la fin de ce bilan, arrêter les développements. Le succès local permettra un GO de préparation à la publication, pas une fusion automatique : les deux PR restent Draft, PR15 vise la branche PR14. PR13 inchangée. Vérifier les références distantes avant toute future publication ; ne pas lancer de workflow manuel sans accord.
