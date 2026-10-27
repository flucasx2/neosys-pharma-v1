# B03 — Vérification des moyens de paiement à la caisse

## Clôture B03 validée

Le propriétaire a validé les corrections A1, A2 et A3 ainsi que leur recette
humaine, puis autorisé le commit local sur `dev/codex-docker` avec le message
`fix(p4): aligner les choix de paiement sur les moyens actifs`. Les sections
ci-dessous conservent la chronologie de l'audit et des vérifications techniques.

Résultats conservés : 58 assertions JavaScript, 37 tests serveur SQLite réussis,
puis rejeu A3 réussi. La préparation PostgreSQL B03 et sa recette humaine sont
décrites dans `docs/RECETTE_B03_ISOLEE.md`. La migration et l'initialisation du
PostgreSQL jetable ont été vérifiées ; la suite automatisée PostgreSQL native,
notamment concurrence, verrouillage et contention, n'a pas été exécutée. La recette
humaine validée ne lève pas cette limite.

Amélioration ultérieure : rendre le libellé F10 plus explicite sur la finalisation
de l'encaissement et le distinguer de la confirmation indépendante non espèces.
Ce point de rédaction reste ouvert ; aucun changement du libellé, du raccourci
ou des règles financières n'est inclus dans la clôture B03.

Le commit inclut uniquement les deux fichiers d'interface corrigés, leurs trois
fichiers de tests et les deux documents B03. `compose.b03-recette.yaml` reste une
configuration locale non suivie ; `.secrets/`, les identifiants fictifs et toute
donnée de base sont exclus. Les deux conteneurs B03 et leurs données tmpfs sont
conservés sans arrêt ni nettoyage. Aucun push, merge ou travail B04 autorisé.

## Corrections autorisées A1, A2 et A3 — 21 octobre 2026

Les éléments de l'audit initial ci-dessous sont conservés comme preuves avant
correction. La présente section décrit l'état corrigé, à valider par le propriétaire.
Branche et commit de référence inchangés ; aucun commit, push ou merge.

### Corrections et fichiers modifiés

- `src/neosys_pharma/presentation/web/caisse.js` : A1, `cashPaymentChoices`
  ne construit le moyen natif ESPÈCES que si sa famille est active et si les espèces
  sont demandées. Les autres choix proviennent exclusivement des fournisseurs du
  serveur : famille compatible et active, fournisseur actif, identifiant présent.
  Aucun repli générique non espèces.
- Même fichier : A2, `cashPay` ne construit le champ espèces que lorsque la famille
  est active ; le payload n'ajoute pas d'espèces si ce champ n'était pas autorisé.
  Sans choix actif ni confirmation historique, ouverture refusée avec message
  explicite. Les confirmations historiques restent affichées, sans modification,
  et leur acceptation demeure décidée par le serveur B01. À chaque nouvelle
  ouverture, la configuration actuellement chargée est relue. Aucun calcul
  financier ajouté ; le rendu et la validation finale restent ceux du serveur.
- `src/neosys_pharma/presentation/web/encaissement_groupe.js` : les options
  réutilisent toujours la fonction commune. L'ajout d'une ligne sans choix actif
  affiche le même message, sans créer artificiellement une ligne espèces. Les
  lignes historiques déjà présentes et le verrou de finalisation sont conservés.
- `tests/test_regularisation.py` : A3, le helper `refund` accepte des identifiants
  explicites de fournisseur cible et d'origine, sans les deviner ni modifier ses
  appels existants sans identifiant. Aucun changement du service de remboursement.
- `tests/test_p5b_3_encaissement_prise_en_charge.py` : le remboursement CARTE utilise
  explicitement le fournisseur de la confirmation pour la cible ET pour l'origine.
  C'est une restitution historique exacte, sans substitution. Toutes les assertions
  de montants, fidélité, clôtures, historique et absence de double encaissement
  restent présentes. Les substitutions vers une autre identité active restent
  exercées séparément par les tests B01, avec leur permission spécifique.
- `tests/b03_payment_choices_unit.cjs` : nouvelles régressions sur les fonctions
  applicatives réelles (VM Node), composants et transport HTTP simulés, sans base.
- `docs/RAPPORT_B03.md` : présent complément et recette limitée aux corrections.

### Vérifications après correction

- `node tests/b03_payment_choices_unit.cjs` : **58 assertions réussies**. Espèces
  actives/inactives, MOBILE MONEY sans fournisseur, fournisseur actif/inactif,
  famille désactivée avec fournisseur actif, fournisseur incompatible/sans ID,
  état vide, rendu des options et ajout de ligne groupés, payload espèces,
  permission de modale, actualisation/désactivation/réactivation, conservation
  et transmission des confirmations historiques. Le champ espèces ne réapparaît
  pas via une donnée injectée dans le callback de sauvegarde.
- `node --check` sur `caisse.js` et `encaissement_groupe.js` : réussi.
- Régression pytest, même sélection de sept entrées détaillée dans l'audit initial :
  **37 passed, 0 failed, 0 skipped**, **148,83 s**, code de sortie 0.
  Un avertissement préexistant de dépréciation Starlette/httpx.
  Les 16 cas B01 et les quatre cas fournisseurs sont conservés ; le scénario
  CARTE auparavant en échec atteint maintenant ses assertions finales de montants,
  clôture Z, fidélité, unicité de réalisation et compensations de retour.
- Après mise en forme finale du helper, rejeu isolé de
  `tests/test_p5b_3_encaissement_prise_en_charge.py::test_encaissement_part_client_multi_organismes_receipt_loyalty_and_returns` :
  **1 passed**, **14,25 s**, code de sortie 0, même avertissement préexistant.
  Ce rejeu est compris dans les 37 cas distincts précédents.
- `git diff --check` final : réussi. Branche `dev/codex-docker` et HEAD
  `05478570a713f635029f570b3f7bf9bed0cdf200` inchangés. Les six fichiers listés
  ci-dessus constituent tout le périmètre modifié/ajouté.

La sélection pytest et l'isolation sont identiques à celles détaillées dans
l'audit initial : conteneur existant de tests, réseau désactivé, système de fichiers
en lecture seule, `/tmp` éphémère, sources/tests montés en lecture seule, SQLite en
mémoire imposée pour les deux URL. Aucun secret, PostgreSQL, migration, bootstrap,
service Compose ou volume conservé utilisé.

### Limites et recette humaine courte

PostgreSQL natif, concurrence et verrouillage natifs restent non validés. Les
nouveaux tests UI utilisent des composants simulés, pas un navigateur réel ; les
suites DOM jsdom de B01/B02 n'ont pas été relancées. Une fenêtre déjà ouverte
pendant une modification distante conserve son état jusqu'à sa prochaine ouverture ;
les contrôles serveur restent l'autorité et refusent une cible devenue inactive.
Les lacunes de tests serveur spécifiques identifiées dans l'audit initial restent
ouvertes et ne font pas l'objet d'un changement de règles dans cette correction.

Recette uniquement sur environnement jetable autorisé, avec données fictives :

1. Activer MOBILE MONEY sans fournisseur : aucun choix générique dans la
   confirmation ni dans une nouvelle ligne groupée. Créer/activer un fournisseur :
   son nom apparaît. Le désactiver, puis désactiver sa famille : il disparaît des
   nouveaux choix dans les deux cas après actualisation.
2. Désactiver ESPÈCES puis actualiser : aucun champ espèces dans un nouvel
   encaissement individuel. Sans aucun moyen ni confirmation, message explicite ;
   l'ajout groupé ne crée aucune ligne. Réactiver et actualiser : espèces proposées.
3. Conserver une confirmation antérieure, désactiver son moyen et actualiser :
   confirmation toujours lisible, tentative soumise au refus serveur B01 ; comparer
   les reçus historiques. Ne pas activer le groupé hors de sa recette autorisée.
4. Sur une vente fictive CARTE, restituer sur le fournisseur historique exact ;
   vérifier les montants et clôtures. Une substitution utilise une autre identité
   active et exige la permission spécifique, comme en B01.

Arrêt après B03, en attente de validation. B04 non commencé.

## Audit initial avant correction

Audit du 21 octobre 2026 sur `dev/codex-docker`, référence et HEAD
`05478570a713f635029f570b3f7bf9bed0cdf200`. Checkout propre avant intervention.
Seul ce rapport est ajouté ; aucune correction applicative ou modification de test.

## Conclusion

Les contrôles serveur examinés conservent les règles B01/B02 : famille active,
fournisseur explicite et actif pour les nouveaux paiements non espèces, permissions,
confirmations, montants et historique. Deux anomalies d'interface sont reproduites.
La conformité fonctionnelle complète de B03 ne peut donc pas être prononcée.
Les corrections éventuelles attendent l'autorisation du propriétaire.

## Scénarios et preuves

| Scénario | Constat | Preuve et portée |
|---|---|---|
| 1. ESPÈCES actif | Conforme dans les cas exécutés | B01 : configuration initiale espèces seule, finalisation réussie ; fonction JS : choix ESPECES avec identifiant fournisseur nul. |
| 2. MOBILE MONEY explicitement créé et actif | Conforme pour ce cas ; anomalie du cas sans fournisseur | `test_moyens_paiement.py` exerce deux fournisseurs distincts ; fonction JS retourne `MOBILE_MONEY:air` pour un fournisseur actif. Voir A1. |
| 3. Moyen désactivé | Refus serveur couvert en individuel et groupé | B01 : confirmation puis finalisation refusées après désactivation ; test groupé : 409, aucune écriture d'encaissement, puis succès après réactivation. Le filtre JS retire le fournisseur inactif. |
| 4. Famille désactivée | Contrôles serveur présents ; couverture partielle | `CaisseService.confirmer` et `finaliser`, `EncaissementGroupeService.remplacer_reglements` et finalisation contrôlent les familles. B01 couvre les espèces désactivées en individuel et groupé. JS retire un fournisseur actif si sa famille est absente de `modes`. La finalisation MOBILE MONEY avec fournisseur actif/famille désactivée n'a pas de cas dédié dans la sélection exécutée. Voir A2. |
| 5. Règles individuelles | Cas ciblés réussis, scénario prise en charge incomplet | Paiement mixte, rejeu, rollback, quatre familles non espèces sans rendu et exclusion des médicaments réussis. Le scénario prise en charge atteint le remboursement puis échoue sur un payload de test sans fournisseur (A3). |
| 6. Groupé | Contraintes communes retrouvées et cas ciblés couverts | Fournisseurs distincts, allocations, désactivation entre préparation et finalisation, réactivation, libellé historique et espèces désactivées. Finalisation toujours verrouillée hors recette autorisée. |
| 7. Historique | Conforme dans les cas exécutés | PDF espèces identique après désactivation ; libellés de confirmation/reçus figés après renommage ; remboursements attachés à leurs identités historiques. |
| 8. Permissions serveur | Individuel testé, groupé inspecté | Test HTTP 401/403/CSRF, isolation et rejeu après révocation ; politique API confirmation `caisse.paiement.confirmer`, finalisation `caisse.encaisser`. Groupé : POLICY et contrôles de session/emplacement côté services ; révocation spécifique au groupé non rejouée dans cette sélection. |
| 9. Remboursements B01 | Conforme dans les cas exécutés | Suite B01 complète : origine historique désactivée avant demande/après autorisation, retour/acquis, espèces, substitutions actives et permission revérifiée, preuves, audit et idempotence. |

## Anomalies reproduites

### A1 — Famille non espèces proposée sans fournisseur explicite

Fichier : `src/neosys_pharma/presentation/web/caisse.js:51`, fonction
`cashPaymentChoices`, utilisée par `cashConfirm` (ligne 52) et le groupé
`encaissement_groupe.js:471`.

Reproduction Node 24.22.0 : extraction et exécution de la fonction réelle dans
`node:vm`, sans réécriture de son corps, avec :

```json
{"modes":["MOBILE_MONEY"],"moyens":[]}
```

Résultat observé :

```json
[{"key":"MOBILE_MONEY","mode":"MOBILE_MONEY","moyen_id":null,"libelle":"MOBILE MONEY"}]
```

Attendu B01 : aucun choix non espèces sans fournisseur explicitement créé.
La branche de repli générique est appliquée à toutes les familles, alors que seul
le moyen natif espèces peut ne pas avoir de fournisseur. La confirmation transmet
ce choix nul ; `CaisseService.confirmer` le refuse. Aucun contournement financier
serveur démontré. Impact : choix trompeur et parcours voué au refus.

Contrôles voisins exécutés : espèces seule → un choix natif ; fournisseur actif →
choix avec son ID ; fournisseur inactif → liste vide ; famille inactive et
fournisseur actif → liste vide. Le test DOM existant `moyens_paiement_ui.cjs`
ne couvre pas la famille active sans fournisseur.

### A2 — Espèces toujours proposées dans l'encaissement individuel

Fichier : `src/neosys_pharma/presentation/web/caisse.js:53`, `cashPay`.
Le champ `especes` est construit sans consultation de la configuration ; les
confirmations sont également affichées sans filtrage de disponibilité courante.

Reproduction : exécution du corps réel de `cashPay` dans Node VM, état de vente
100 FCFA, session présente, aucune confirmation, `configuration.modes=[]` ;
rafraîchissement fidélité et composants de formulaire simulés, noms des champs
créés capturés. Résultat : `fields=["especes","confirme"]`.

Attendu : ne pas proposer les espèces comme nouveau paiement lorsqu'elles sont
désactivées. Le serveur refuse correctement une tentative de finalisation dans
cette configuration (test B01), mais l'interface permet de préparer la tentative.
Le rendu navigateur réel n'a pas été exercé dans cette reproduction.

### A3 — Test de remboursement CARTE incompatible avec B01

Échec reproduit dans
`tests/test_p5b_3_encaissement_prise_en_charge.py:295`, appel
`refund(c, a, second, session, mode="CARTE")`.
Le helper `tests/test_regularisation.py:44` envoie
`reglements=[{"mode":"CARTE","montant":"514"}]` sans `moyen_id`.
Le serveur répond HTTP 422 : « Sélection explicite du moyen de remboursement
requise. », alors que le helper attend HTTP 201.

Diagnostic : attente/donnée de test non alignée sur B01, qui impose un fournisseur
explicite pour un nouveau remplacement non espèces. Le scénario utilise désormais
une confirmation CARTE avec fournisseur explicite grâce au helper de caisse.
L'absence de fournisseur dans le remboursement ne représente donc plus cette
identité. Ce refus ne prouve pas une anomalie métier serveur ; il empêche la
validation complète de la fin de ce scénario. Aucun helper ni garde corrigé.

## Architecture examinée

- `presentation/web/caisse.js` : contexte chargé du serveur, choix et confirmation,
  encaissement individuel et payload de finalisation.
- `presentation/web/encaissement_groupe.js` : choix communs, confirmations filtrées
  par famille et fournisseur, montants, allocations et disponibilité du verrou.
- `presentation/caisse_api.py`, `presentation/encaissement_groupe_api.py` :
  permissions et validations avant mutation/rejeu.
- `application/caisse_service.py` : configuration effective, fournisseur et
  périmètre organisationnel, preuve indépendante, contrôles à la finalisation.
- `application/encaissement_groupe_service.py` : contrôles à l'enregistrement des
  règlements et à nouveau à la finalisation.
- `application/regularisation_service.py` et tests B01 : historique et substitution.

L'interface consomme bien le référentiel serveur (`configuration.modes/moyens`) et
transmet les identités des fournisseurs ; elle ne crée aucun fournisseur en base.
Elle effectue aussi des calculs/précontrôles de présentation existants (rendu,
totaux, allocations), revérifiés côté serveur. A1 constitue toutefois un repli
local incompatible avec le référentiel B01 ; A2 n'utilise pas ce référentiel pour
la disponibilité des espèces. Aucun calcul financier n'a été modifié.

## Vérification et isolation

Image existante : `neosys-pharma-dev-tests:latest`, ID court `02920248d821`.
Conteneur `docker run --rm --network none --read-only --tmpfs /tmp`, aucun secret,
aucun volume PostgreSQL, sources et tests du checkout montés en lecture seule.
`DATABASE_URL` et `TEST_DATABASE_URL` explicitement `sqlite+pysqlite://`,
`PYTHONPATH=/opt/neosys/src`. Aucun environnement TEST_* du poste transmis.
Commande directe Python dans l'image, comme au contrôle final B02, sans lancer
l'entrypoint Compose qui requiert un secret et configure une URL PostgreSQL.

La fixture réelle `test_p1_vertical.raw_client` utilise SQLite en mémoire,
`StaticPool`, clés étrangères activées, crée les tables puis les supprime à la fin.
Ces suppressions concernent uniquement la base éphémère du conteneur.
Aucun service `db`, `app` ou `test-db` démarré/recréé/arrêté par cet audit.
Aucune migration, aucun bootstrap ni accès PostgreSQL.

Sélection pytest :

```text
python -m pytest -q -ra -p no:cacheprovider
  tests/test_b01_moyens_paiement.py
  tests/test_moyens_paiement.py
  tests/test_caisse.py::test_encaissement_mixte_atomique_recu_et_rejeu
  tests/test_caisse.py::test_echec_sans_effet_financier_stock_ou_points
  tests/test_caisse.py::test_401_403_csrf_lecture_seule_isolation_et_rejeu
  tests/test_caisse.py::test_moyens_non_especes_confirmes_et_sans_rendu
  tests/test_p5b_3_encaissement_prise_en_charge.py
```

Résultat : **36 passed, 1 failed, 0 skipped**, en **141,47 s**, code de sortie 1.
Un avertissement préexistant Starlette/httpx. Échec : scénario de prise en charge
multi-organismes, au remboursement CARTE décrit en A3. Les 16 cas B01, les quatre
cas `test_moyens_paiement.py` et les autres cas sélectionnés sont réussis. Le
scénario en échec franchit notamment le paiement et le reçu avant ce refus, mais
ne doit pas être compté comme validé de bout en bout.

JavaScript : cinq cas de `cashPaymentChoices` et reproduction `cashPay` exécutés
sur le code réel avec Node VM ; deux anomalies ci-dessus observées. Syntaxe
`node --check` réussie pour `caisse.js` et `encaissement_groupe.js`.
Les suites DOM existantes n'ont pas été rejouées : jsdom absent du runtime Node
du checkout ; aucune dépendance installée pour cet audit.

## Limites et couverture à compléter

- Aucun test PostgreSQL natif : concurrence, verrouillage et comportement natif
  des contraintes ne sont pas validés par SQLite. Aucune base conservée consultée.
- Pas de navigateur réel ni de paiement externe ; transports financiers manuels
  et preuves restent ceux de B01.
- Ajouter, après autorisation, des tests explicites de famille MOBILE MONEY
  désactivée avec fournisseur actif : confirmation, individuel, enregistrement du
  groupé et désactivation après préparation avant finalisation.
- Compléter les tests de révocation de `caisse.paiement.confirmer` et de
  `caisse.encaisser` pour le groupé, ainsi que la couverture UI des états sans
  fournisseur/sans moyen actif et des changements de configuration pendant une
  fenêtre ouverte. Aucun défaut serveur n'est déduit de ces absences de tests.
- Les tests groupés existants activent le booléen API uniquement dans leur fixture
  isolée ; aucun garde d'activation de l'application n'a été modifié.

## Recette humaine proposée

À effectuer uniquement dans un environnement de recette jetable autorisé, avec
des ventes et utilisateurs fictifs ; ne pas adapter cette recette aux bases
PostgreSQL conservées dans le cadre de B03.

1. Avec `caisse.encaisser`, vérifier les espèces actives : paiement exact, excédent
   avec rendu espèces, reçu et rejeu sans double mouvement.
2. Activer MOBILE MONEY sans fournisseur : constater A1. Créer ensuite un moyen
   fictif explicitement ; vérifier son nom dans les choix et son identité dans la
   confirmation indépendante, avec référence/preuve, puis le paiement mixte.
3. Désactiver le fournisseur avant confirmation puis entre confirmation et
   finalisation : vérifier les refus, l'absence d'encaissement et la conservation
   de la confirmation acquise. Réactiver pour terminer le dossier autorisé.
4. Refaire avec famille inactive/fournisseur actif, puis espèces inactives :
   constater A2 et le refus serveur. Vérifier aussi la configuration vide après
   rechargement, sans réactivation implicite.
5. Dans la seule orchestration groupée jetable déjà autorisée, refaire avec deux
   ventes et deux fournisseurs : allocations, désactivation après préparation,
   refus sans écriture puis succès après réactivation. Conserver le verrou P4.
6. Retirer les permissions avec des comptes fictifs : vérifier le refus des appels
   directs de confirmation et finalisation individuelle/groupée, y compris rejeu.
7. Renommer/désactiver après paiement : comparer les PDF et libellés historiques.
   Rembourser sur l'origine exacte avec autorisation/preuves et audit B01 ; vérifier
   qu'une substitution inactive ou sans permission reste refusée à l'exécution.

Contrôle final : `git diff --check` réussi ; branche et HEAD inchangés ; seul
`docs/RAPPORT_B03.md` est non suivi dans le checkout.

Arrêt après ce rapport B03. Aucun commit, push, merge ou travail B04.
