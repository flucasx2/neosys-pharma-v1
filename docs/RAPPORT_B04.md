# B04 — Rendu monnaie en encaissement simple et multiple

## Périmètre et environnement

Travail sur `dev/codex-docker`, à partir de
`4f91780b4a557640b0b42769b0a25f9e6da708a4` (B03). État initial : seul
`compose.b03-recette.yaml` était non suivi. Aucun commit, push, merge ou changement
de branche. Ce fichier Compose n'a été ni modifié, ni supprimé, ni ajouté à Git.
Aucune connexion aux PostgreSQL Windows, de développement ou de recette B03 ;
aucune migration, aucun bootstrap et aucune suppression de volume. Les conteneurs
B03 n'ont reçu aucune commande. Aucun autre bloc engagé.

## Audit et modifications

- **Simple** : `repartir_paiements` calculait déjà le rendu en `Decimal`, refusait
  le surpaiement non espèces et exigeait la couverture intégrale. Ces règles et
  le service de finalisation sont réutilisés sans modification. La fenêtre de
  confirmation existante affiche désormais en temps réel le solde client à régler,
  le total reçu, le rendu monnaie, le net encaissé et le reste à répartir, selon
  les confirmations cochées et les espèces saisies.
- **Groupé** : le modèle possède déjà `montant`, `rendu` et les allocations nettes.
  La finalisation exigeait déjà un net égal au dû, mais l'enregistrement dépendait
  du rendu fourni par le navigateur. `calculer_rendu_groupe` calcule maintenant ce
  rendu côté serveur lors du remplacement des règlements, avant toute suppression
  ou écriture. Un rendu espèces transmis est recalculé ; un rendu non espèces
  non nul est refusé. Les excédents non espèces sont refusés même avec des espèces.
- L'API du dossier expose aussi `brut_recu_xaf` et `rendu_xaf`, avec les totaux nets
  et alloués existants. Aucune migration et aucun changement du modèle financier.
- L'interface groupée recalcule automatiquement l'aperçu et le rendu de ses lignes.
  Le récapitulatif affiche les cinq informations financières essentielles. Les
  tickets restent à gauche et les règlements à droite sur écran large, puis les
  colonnes s'empilent sur petit écran. Les boutons de suppression, « + Mode de
  paiement » et « Valider l'encaissement » sont conservés/explicités. Les étapes
  de brouillon et d'enregistrement des allocations restent explicites.
- Les droits, sessions, contrôles des moyens actifs/fournisseurs explicites,
  confirmations indépendantes, idempotence, allocations, mouvements, reçus,
  historique, fidélité, stock et P5 gardent leurs contrôles existants. Une
  confirmation est représentée une seule fois dans la somme des règlements ;
  le service garde le refus des confirmations dupliquées ou déjà consommées.
- Serveur : `Decimal` et francs entiers. Navigateur : entiers exacts JavaScript,
  avec refus des montants/sommes hors de `Number.MAX_SAFE_INTEGER`, sans arrondi
  silencieux. Le serveur reste l'autorité et les allocations finales portent
  uniquement sur le net.

## Tests exécutés

Commande serveur, dans un projet Docker B04 distinct :

```powershell
docker compose -p neosys-pharma-b04-tests -f compose.yaml --profile test run --rm --no-deps --build tests python -m pytest -q -rs -p no:cacheprovider tests/test_b04_rendu.py tests/test_encaissement_groupe_domain.py tests/test_caisse.py tests/test_b01_moyens_paiement.py tests/test_moyens_paiement.py tests/test_p5b_3_encaissement_prise_en_charge.py
```

Le runner de tests existant refuse les URL héritées et fixe `TEST_DATABASE_URL`
à `sqlite+pysqlite://`. Les fixtures créent et détruisent uniquement leurs bases
SQLite en mémoire dans le conteneur jetable. `--no-deps` ne démarre aucun service
PostgreSQL. Seul le secret de tests est monté par Compose ; aucune valeur de secret
n'est affichée. L'image B04 porte un nom distinct de celles de B03/développement.

Résultat serveur : **87 passed, 5 skipped, 3 subtests passed**, en **293,55 s**,
code de sortie **0**. Un avertissement de dépréciation Starlette/httpx préexistant.

Les cinq tests ignorés dans `tests/test_caisse.py` sont :

- `test_concurrence_postgresql_encaissement_session_et_points` (ligne 236, deux connexions PostgreSQL requises) ;
- `test_concurrence_postgresql_ouverture_session` (ligne 386) ;
- `test_concurrence_postgresql_finalisation_groupe_meme_cle` (ligne 1059) ;
- `test_concurrence_postgresql_encaissement_individuel_contre_groupe` (ligne 1128) ;
- `test_concurrence_postgresql_deux_dossiers_meme_vente` (ligne 1187).

Les numéros désignent les appels `pytest.skip` de la version testée.

Vérifications JavaScript :

```powershell
node tests/b04_rendu_unit.cjs
node tests/b03_payment_choices_unit.cjs
node --check src/neosys_pharma/presentation/web/caisse.js
node --check src/neosys_pharma/presentation/web/encaissement_groupe.js
git diff --check
```

Résultat : **18 assertions B04 et 58 assertions B03 réussies**, syntaxe et diff
valides. Les tests B04 exécutent les fonctions réelles de calcul et de rendu du
récapitulatif groupé, avec un DOM minimal simulé. L'adaptation du test B03 ajoute
uniquement les méthodes de formulaire nécessaires au nouveau récapitulatif.

Nouveaux scénarios serveur : 7 000/7 000, 7 000/10 000, mixte de référence
101 400/101 900, paiement non espèces exact, plusieurs lignes espèces, grands
entiers FCFA exacts, excédents carte/mobile avec ou sans espèces, insuffisance,
montants invalides, deux tickets à 33 800 et 67 600 avec allocations nettes,
finalisation simple HTTP exacte/excédentaire/insuffisante, reçu et rejeu, et calcul
serveur du rendu groupé à partir d'un rendu client égal à zéro.
Les suites existantes complètent les moyens désactivés, confirmations acquises,
reçus individuels/collectif, rejeux, rollback, droits, sessions et P5.

## Limites et tests non exécutés

- Aucun test sur PostgreSQL natif. Les contrôles de concurrence nécessitant deux
  connexions PostgreSQL sont les cinq cas ignorés listés ci-dessus. Aucun
  comportement de verrouillage natif n'est déclaré validé.
- Aucun navigateur réel ni recette humaine exécutée dans B04. La disposition CSS,
  le focus et le responsive restent à contrôler par la recette ci-dessous. Les
  tests JavaScript utilisent des composants/DOM et transports simulés. Les suites
  DOM historiques dépendant de jsdom n'ont pas été exécutées : jsdom indisponible
  dans le runtime Node du checkout. Aucune dépendance ajoutée.
- La contrainte existante impose un net strictement positif par ligne du groupé.
  Le rendu est distribué depuis la dernière ligne espèces, sans rendre une ligne
  entièrement. Si les espèces seraient intégralement inutiles, le service refuse
  et demande de retirer/regrouper les lignes. Exemple : carte couvrant tout le dû
  plus une ligne espèces. Cette protection reste en place ; aucun changement de
  modèle d'allocations n'est nécessaire pour les deux cas de référence.
- Un brouillon insuffisant peut être enregistré pour correction ; il ne peut pas
  être ventilé/finalisé tant que son net ne couvre pas exactement les tickets.
- Les confirmations restent des paiements acquis par un terminal/fournisseur
  indépendant. B04 ne crée aucun paiement externe et ne contourne pas leur
  rapprochement, les preuves ou le fournisseur explicite.
- Le garde d'activation groupée reste inchangé. Les scénarios de finalisation
  groupée l'activent uniquement dans leurs fixtures isolées. Aucun écran B03
  n'est utilisé pour tester B04.

## Recette humaine courte, à exécuter après validation

**Prérequis** : un environnement B04 jetable séparé, avec cette version des
sources, un site/utilisateur fictif autorisé, une caisse/session ouverte et le
groupé autorisé par son mécanisme de recette existant. Ne pas utiliser le port
8003, le Compose B03 ou une base conservée. La préparation de cet environnement,
les éventuelles migrations/bootstrap et son lancement n'ont pas été exécutés dans
ce bloc. Ne pas lever le garde P4 dans les sources pour faire la recette.

1. Activer les espèces, une CARTE de recette et un fournisseur MOBILE MONEY nommé
   explicitement AIRTEL MONEY. Préparer des ventes fictives avec prix TTC permettant
   les montants ci-dessous ; ne pas utiliser de fidélité/prise en charge pour les
   deux exemples de référence.
2. **Simple** : transmettre un ticket dû de **7 000 FCFA**. Ouvrir son encaissement,
   saisir **10 000** espèces. Avant validation, constater total reçu **10 000**,
   rendu **3 000**, net **7 000**, reste **0**. Passer temporairement à **6 000** :
   reste **1 000**, finalisation refusée. Revenir à 10 000, confirmer et valider.
   Vérifier reçu, espèces attendues augmentées de 7 000 seulement et historique.
   Rejouer la même requête avec sa même clé : même reçu, aucun mouvement ajouté.
3. **Multiple** : transmettre deux tickets de **33 800** et **67 600**. Sélectionner
   les deux à gauche et créer le brouillon existant. Acquérir une confirmation
   indépendante CARTE **10 000** et AIRTEL MONEY **1 400**, avec fournisseurs,
   références et preuves explicites sur des ventes du groupe/session courante.
   Dans les règlements à droite, ajouter ESPÈCES **90 500**, CARTE **10 000** et
   AIRTEL MONEY **1 400**, en sélectionnant chaque confirmation une seule fois.
   Constater total des tickets/solde client **101 400**, total reçu **101 900**,
   rendu **500**, net **101 400**, reste **0**, sans saisir manuellement de rendu.
4. Passer les espèces à **90 000** : rendu **0**, net **101 400**. Passer à
   **89 000** : reste **1 000**. Revenir à 90 500. Enregistrer les règlements ;
   vérifier les totaux retournés par le serveur. Proposer et enregistrer
   explicitement la ventilation. Vérifier chaque ticket couvert exactement et
   une somme des allocations espèces de **90 000**. Valider l'encaissement,
   contrôler les deux reçus et le collectif (brut/rendu/net), puis rejouer avec
   la même clé : mêmes reçus, aucun second effet.
5. Dans un **autre brouillon jetable**, utiliser une confirmation CARTE **102 000**
   pour un dû de **101 400**, avec une ligne espèces. Constater le refus de
   l'excédent non espèces : aucun rendu autorisant l'opération, aucune finalisation.
   Ne pas supposer qu'un paiement acquis a été annulé : utiliser le circuit de
   résolution existant pour cette confirmation fictive.
6. Sur d'autres ventes fictives, désactiver successivement espèces, fournisseur
   CARTE/AIRTEL et famille correspondante après préparation : vérifier le refus
   serveur sans mouvement/reçu. Réactiver pour terminer par les procédures
   existantes. Essayer de sélectionner deux fois la même confirmation : refus,
   aucun double montant encaissé. Vérifier aussi retrait d'une ligne et mise à
   jour immédiate des totaux.
7. Contrôler à largeur 1 920 px puis mobile : tickets à gauche/règlements à droite
   sur grand écran, empilement lisible sur petit écran, totaux visibles, navigation
   clavier et confirmations/ventilation explicites conservées.

Contrôle final : branche et HEAD inchangés, `git diff --check` réussi. Les quatre
conteneurs B03/développement restent actifs avec les mêmes noms et images que lors
du contrôle initial. Le conteneur de tests B04 a été supprimé par `--rm` et son
seul réseau temporaire a été retiré ; aucun volume supprimé. L'image de tests B04
reste disponible localement.

Arrêt après B04 ; validation du propriétaire attendue avant toute autre action.


# Diagnostic consolidé après recette humaine B04 — 21 octobre 2026

## Périmètre et conclusion

Diagnostic uniquement, après les observations du propriétaire sur le port 8004.
Aucune correction applicative, migration, confirmation, rapprochement, écriture
financière ou finalisation exécutée. Aucun conteneur arrêté/recréé, aucun fichier
ou volume de données supprimé. Le présent rapport est le seul fichier modifié
pendant ce diagnostic. Branche/HEAD inchangés ; aucun B05, commit, push ou merge.

Trois défauts d'interface sont confirmés par le code et des reproductions isolées :
l'initialisation du récapitulatif simple avant clonage, le cache de confirmations
non rafraîchi et le défaut de réactivation des boutons de consultation groupée.
**La confirmation CARTE existante est compatible sans rapprochement.** Aucune
anomalie de calcul serveur n'est mise en évidence par les résultats de recette.
L'enregistrement des règlements groupés, leur ventilation et la finalisation
restent à valider humainement après autorisation de correction.

## Résultats humains conformes et état B04 observé

Résultats déclarés conformes par le propriétaire, distincts des reproductions
techniques exécutées pendant ce diagnostic :

- Simple : dû 7 000, reçu espèces 10 000, PDF avec rendu 3 000 et net 7 000 FCFA.
- Groupe : tickets 33 800 + 67 600 = 101 400 FCFA.
- Aperçu espèces 102 000 : rendu 600, net 101 400.
- Aperçu espèces 90 000 : reste 11 400.
- Aperçu mixte espèces 90 500 + CARTE 10 000 + AIRTEL MONEY 1 400 : brut 101 900,
  rendu 500 et net 101 400.

Lecture SQL B04 dans des transactions explicitement `read_only=True` ou
`SET TRANSACTION READ ONLY`. Le runner a vérifié la cible réelle avant lecture :
`neosys_browser`, `neosys_test`, serveur `172.23.0.2`, égal au `test-db` du réseau
B04, via le relais `127.0.0.1:55432`. Aucune base conservée consultée.

| Objet | État observé |
|---|---|
| Préparation 0001 | `0e5c114c-6f60-4cc7-85d0-05bd3501f718`, ENCAISSEE, révision 5 |
| Préparation 0002 | `cb13d88e-bba5-447c-b6ee-f6aa149c40d9`, TRANSMISE, révision 4 |
| Préparation 0003 | `3cacdabe-89ae-49e7-805c-85fba54f81c5`, TRANSMISE, révision 4 |
| Session | `89869cab-4520-452e-a7d1-1d54060b31cf`, OUVERTE, révision 2 |
| Caisse | `199e4378-edc4-4ea2-b927-bf49abf0de68`, commune aux ventes/session |
| Brouillon | `474a1999-38b1-418b-96af-9cceed2984f0`, BROUILLON, révision 2 |
| Tickets du brouillon | 0002 et 0003, révisions instantanées 4, dus 33 800 et 67 600 |
| Confirmation CARTE | `9d7bff79-3741-4408-8dde-7c336cc61db5`, référence `TEST-B04-CARTE-001`, montant 10 000 |
| Fournisseur CARTE | `fd85fc53-9a12-4c2c-8a83-d71849668041`, code CARTE_B04, actif, révision 1 |
| Fournisseur AIRTEL MONEY | `0c550990-3c5c-4214-a3d1-21c3268b8298`, actif, révision 1 |

Comptages : **1 encaissement individuel**, **1 confirmation**, **1 brouillon**,
**0 règlement groupé**, **0 allocation groupée**. Aucun événement
`PAIEMENT_RAPPROCHE`, aucun règlement individuel consommant une confirmation.
Aucune confirmation AIRTEL n'existe à ce stade : la ligne AIRTEL de l'aperçu ne
constitue pas un paiement indépendant confirmé.

## B04-UI-001 — Aperçu simple non actualisé : anomalie confirmée

### Cause

Dans `presentation/web/caisse.js`, `cashPay` construit un formulaire source `f`,
crée le nœud `summary` et attache directement sur `f` les listeners `input` et
`change`. La closure lit aussi `f.elements.especes` et écrit dans ce même
`summary`. L'appel initial à `refresh()` produit correctement l'aperçu à zéro.

`cashModal` transmet ensuite ce formulaire à `creationDialogCreate`, dans
`presentation/web/creation_dialogs.js`. Cette fonction fait
`source.cloneNode(true)` : la fenêtre affiche **le clone**, qui contient le texte
initial, mais pas les listeners attachés au formulaire source. La saisie dans le
clone ne déclenche donc pas le récapitulatif. Même recopier uniquement les
listeners serait insuffisant si la closure continuait à lire/écrire les nœuds
source détachés.

La sauvegarde, elle, lit les champs du vrai `entry.form` et le serveur recalcule
le rendu : cela explique le PDF correct malgré l'aperçu inchangé. Les valeurs
observées par le propriétaire correspondent exactement au texte initial cloné.

### Reproduction exécutée

Node VM, fonctions réelles `cashPay`, `cashModal`, `creationDialogCreate`,
`cashFinancialSummary` et `cashRenderFinancialSummary`, DOM minimal simulant le
clonage sans listeners. Saisie `10000` puis événements `input` et `change` sur le
champ cloné : reçu affiché **0**, source restée à **0**, clone à **10000**.
Calcul financier isolé : rendu **3000**. Assertions réussies.
Cette reproduction est technique, sans navigateur ni paiement réel supplémentaire.
Les tests B04 antérieurs vérifiaient les calculs et le rendu groupé ; le test B03
remplaçait l'hôte modal. Aucun ne traversait ce clonage de la modale simple.

### Correction minimale proposée — priorité P1

Dans `cashPay` uniquement, retourner un initialiseur appelé après clonage par le
mécanisme existant de `cashModal`. Résoudre les champs et le récapitulatif depuis
`entry.form`, attacher les listeners sur ce formulaire affiché, puis calculer
l'état initial. Préserver le composant partagé et le calcul serveur.

Tests proposés : vrai cycle modal avec clonage ; 7 000/10 000, changement de
montant, cases de confirmations, insuffisance et excédent non espèces. Vérifier
que la saisie actualise réellement les nœuds affichés, sans soumission.

## B04-M06 — Confirmation CARTE absente du groupé

### Identités, état et révisions : vérifiés

La confirmation appartient à la vente 0002 du groupe, porte la même session que
le brouillon et une `revision_vente=4`, égale à la révision courante de cette vente
et à son instantané dans le groupe. Mode CARTE, montant 10 000 et `moyen_id`
correspondent au fournisseur explicite CARTE actif. Aucun doublon consommé ni
rapprochement n'a été trouvé.

Le modèle de confirmation n'a pas de colonne d'état mutable ni de révision
propre : la révision mémorisée est celle de la vente lors de l'acquisition.
L'utilisation et les rapprochements sont représentés par les liens de règlements
et les événements d'audit, pas par un champ « à rapprocher ».

### Rapprochement : non nécessaire dans ce cas, démontré

`CaisseService.rapprochement_compatible` accepte directement une confirmation si
vente, session et révision de vente correspondent. Sinon il recherche un événement
`PAIEMENT_RAPPROCHE` compatible. La fonction réelle, exécutée sur B04 en lecture
seule avec les objets actuels, a retourné **True sans événement de rapprochement**.

Le bouton individuel « Rapprocher ... » n'est pas un diagnostic d'obsolescence :
`cashRender` le construit pour **chaque** confirmation d'une vente transmise,
sans tester `rapprochement_compatible`. Sa présence seule ne justifie donc aucun
rapprochement ni nouvelle confirmation.

Au groupé, l'enregistrement exige déjà session d'origine, vente du groupe, mode,
montant et fournisseur actif compatibles. La finalisation revérifie ces points,
les consommations et la compatibilité de rapprochement. Pour une révision devenue
obsolète dans la même session, un rapprochement audité peut être nécessaire à la
finalisation. En revanche, un rapprochement vers une autre session ne suffit pas
à lui seul au groupé actuel : celui-ci exige aussi `confirmation.session_id`
égal à la session du dossier. Aucun changement de cette règle n'est proposé ici.

### API et filtrage JavaScript

La route GET caisse `/ventes/{id}` inclut toutes les confirmations de la vente,
sans filtre de rapprochement. La fonction réelle de cette route, appelée
directement en transaction B04 en lecture seule, renvoie bien l'ID de
`TEST-B04-CARTE-001`. Il s'agit d'une invocation de la fonction de route/service,
pas d'une nouvelle connexion HTTP authentifiée ; les permissions ne sont pas
modifiées par le diagnostic.

`cgConfirmationOptions` filtre uniquement le cache
`cashGroupState.saleDetails` avec trois égalités :

1. `confirmation.mode === mode` ;
2. `(confirmation.moyen_id || null) === moyenId` ;
3. `Number(confirmation.montant) === amount`.

Il ne filtre ni la session, ni la révision, ni un état de rapprochement. Un
rapprochement ne peut donc pas faire apparaître à lui seul une confirmation
absente de ce cache. Les contrôles serveur restent nécessaires, car le sélecteur
n'est pas une preuve d'éligibilité complète.

Reproduction Node VM de la fonction réelle : cache sans confirmation → **0 choix** ;
cache contenant la confirmation réelle, CARTE/10 000/bon fournisseur → **1 choix** ;
fournisseur absent ou montant 9 999 → **0 choix**. Assertions réussies.

### Cache non actualisé : défaut confirmé, cause la plus probable de la recette

`cgLoadDraftSales` charge les confirmations à la création/reprise/recharge du
dossier. Après une confirmation créée dans l'individuel, `cashConfirm` recharge
`cashState.sale` mais pas `cashGroupState.saleDetails`. Le retour en mode groupé,
« Actualiser les tickets » et F12 chargent la liste des ventes, **pas les détails
du brouillon**. Le cache peut donc rester sans la nouvelle confirmation.

L'audit établit cette chronologie, heures Africa/Lagos (UTC+1) :

- création et ajout des tickets au brouillon : **14:57:20** ;
- confirmation CARTE créée ensuite : **15:10:38**.

Cette chronologie, le défaut de rafraîchissement et le bouton de recharge bloqué
expliquent ensemble l'observation. Le snapshot JavaScript du navigateur de la
recette n'a pas été capturé : il reste impossible d'affirmer rétrospectivement
que le fournisseur de la ligne, son montant exact et son cache étaient tous
ceux supposés. L'anomalie de cache est reproduite ; son rôle dans cette session
est très probable, sans inventer un état navigateur non observé.

### Correction minimale proposée — priorité P1, avec M07

Rafraîchir les détails des ventes du brouillon lors d'une demande explicite de
recharge et après acquisition/rapprochement d'une confirmation touchant une de
ses ventes. Faire converger l'actualisation du groupé sur cette lecture fraîche.
Préserver montants saisis, lignes, allocations et clés d'idempotence ; ne pas
recréer de confirmation. Une sélection devenue incompatible doit être signalée,
pas remplacée silencieusement. Afficher la référence, la vente et le fournisseur
pour distinguer une absence de confirmation d'un montant/fournisseur différent.

Tester : brouillon d'abord puis confirmation sur 0002, retour au groupé, lecture
fraîche et apparition de la même confirmation, sans rapprochement artificiel ;
fournisseur différent, montant différent, révision obsolète et confirmation déjà
consommée restent refusés selon les contrôles existants.

## B04-M07 — Recharger désactivé : anomalie confirmée

`cgBusy(true)` désactive **tous** les boutons de `cash-group-panel`. Au retour,
`cgBusy(false)` ne restaure pas leurs états précédents : il appelle seulement
les fonctions de rendu. `cgRenderDraft` réactive certaines actions et recalcule
la finalisation, mais omet **reload**. La même omission concerne notamment
**resume** (« Consulter le dossier »). Le brouillon est créé/repris dans un cycle
busy : ce défaut apparaît donc même après une opération réussie, sans exception.

Reproduction isolée de la fonction réelle : bouton reload initialement actif,
`cgBusy(true)` puis `cgBusy(false)` → `busy=false`, bouton toujours désactivé.
La revue du rendu réel confirme l'absence de toute affectation ultérieure pour
ce bouton. Il n'existe pas actuellement de règle d'activation fondée sur le
contenu du champ « Reprendre ... » : remplir ce champ ne réactive pas reload.

Comportements intentionnels : empêcher les actions pendant une opération,
consulter un dossier connu par son ID, désactiver la finalisation si les montants,
allocations, sessions ou permissions ne conviennent pas. **Maintenir la recharge
bloquée après busy n'est pas l'application d'une de ces protections.**

Correction proposée — priorité P1 : calculer explicitement l'état de tous les
boutons après busy, avec règles distinctes lecture/mutation/finalisation.
Reload : dossier chargé, consultation autorisée, pas d'opération en cours.
Resume : ID renseigné, consultation autorisée, pas d'opération en cours.
Conserver intégralement les conditions de `cgCanFinalize`, les confirmations de
réinitialisation d'allocations et le garde d'activation P4.
Ajouter une protection cohérente à la recharge elle-même contre les opérations
concurrentes ; préserver ou faire confirmer les saisies non enregistrées.
Ne pas appliquer une réactivation globale aveugle de tous les boutons.

## B04-UX-002 — Lignes trop hautes : amélioration de présentation P2

Cause structurelle : chaque `fieldset` présente légende, sélecteur de moyen,
montant, libellé/sélecteur de confirmation et bouton de suppression, sur une grille
à deux colonnes. La ligne espèces réserve même une zone pour une confirmation
désactivée « Sans confirmation espèces ». Les libellés et boutons longs augmentent
le nombre de rangées ; le rendu monnaie masqué n'explique pas seul cette hauteur.

Proposition minimale, proche des captures, sans nouveau parcours :

```text
[ ESPÈCES       v ] [ 90 500 ] [ × ]
[ CARTE         v ] [ 10 000 ] [ × ]
  Confirmation : [ 0002 · TEST-B04-CARTE-001 · 10 000  v ]
[ AIRTEL MONEY  v ] [  1 400 ] [ × ]
  Confirmation : [ Choisir une confirmation existante  v ]
[ + Mode de paiement ]
Total reçu          101 900 FCFA
Rendu monnaie           500 FCFA
Net encaissé        101 400 FCFA
Reste à répartir          0 FCFA
```

Une première rangée compacte **moyen / montant / suppression**, une seconde
rangée pleine largeur **uniquement pour les non espèces**. Aucun sélecteur de
confirmation inutile sur les espèces. Conserver les légendes accessibles,
`aria-label` de suppression, focus visible et saisies entières. Les références,
vente d'origine et fournisseur restent lisibles ; les détails session/preuve
peuvent être consultables sans masquer l'obligation de sélection. Les étapes
existantes d'enregistrement, ventilation explicite et validation restent en place.
Le serveur calcule toujours le rendu ; aucun changement d'allocation ou de modèle.

Vérifier à 1 920 px et à largeur mobile après autorisation. Pas de nouvelle
capture navigateur ni de maquette applicative réalisée dans ce diagnostic ;
la disposition ci-dessus est une proposition textuelle.

## Ordre de correction recommandé et limites de validation

| Priorité | Intervention | Périmètre minimal |
|---|---|---|
| P1 | UI-001 | Initialiser l'aperçu sur le clone affiché, test du vrai cycle modal |
| P1 | M07 + M06 | Réactivation contrôlée de la consultation et rafraîchissement du cache de confirmations |
| P2 | UX-002 | Lignes compactes, confirmation distincte conservée pour chaque non espèces |

Aucune nécessité démontrée de migration, de changement du modèle d'allocations,
de modification des règles B01–B04, de nouvelle confirmation CARTE ou de
rapprochement pour `TEST-B04-CARTE-001`.

Tests réellement exécutés pour ce diagnostic : trois reproductions Node VM
(calcul/modal clonée ; filtrage cache frais/périmé ; cycle busy), lectures SQL
B04 avec transactions non modifiantes et invocation en lecture seule des fonctions
réelles de compatibilité et de détail caisse. Les harnais Node ont été exécutés
via stdin et n'ont créé aucun fichier applicatif ou test persistant.

Non exécutés : nouvelle recette navigateur, nouveaux tests financiers, nouveau
paiement, confirmation AIRTEL, enregistrement du groupé, ventilation, reçu groupé,
rejeu de finalisation, tests de concurrence PostgreSQL. Les résultats humains
conformes ne valident pas ces étapes encore non réalisées. L'erreur de
sérialisation Decimal du rapport `check_initial.py`, déjà documentée dans la
préparation, reste hors correction et ne doit pas être effacée du bilan.

## Reprise courte proposée, sans effacer B04

À exécuter humainement après accord ; aucune de ces actions de reprise n'a été
réalisée pendant le diagnostic.

1. Conserver la session ouverte `89869cab-4520-452e-a7d1-1d54060b31cf` et le
   brouillon `474a1999-38b1-418b-96af-9cceed2984f0`. Ne pas fermer la session,
   recréer le dossier, annuler ou reconfirmer CARTE. L'espèce simple est déjà
   encaissée : ne pas essayer de la payer à nouveau.
2. Noter les montants de l'aperçu (90 500 / 10 000 / 1 400) avant toute recharge :
   **aucun règlement/aucune allocation groupé n'est sauvegardé en base**. Un
   rechargement complet du navigateur perd les saisies locales, mais ne supprime
   ni le brouillon ni la confirmation existants. Après corrections autorisées,
   déployer les seules sources B04 dans l'application 8004, sans toucher aux
   applications partageant le checkout sur 8001/8003 et sans recréer PostgreSQL.
3. Recharger la page 8004 dans son profil navigateur distinct, sélectionner la
   même session, ouvrir le mode multiple, saisir l'ID existant et « Consulter le
   dossier ». Cette reprise lit le dossier et ses ventes fraîches. Sans correction,
   le reload peut rester désactivé de nouveau : ce contournement ponctuel ne vaut
   pas validation du défaut M07 et F12 seul ne rafraîchit pas les confirmations.
4. Recréer seulement les **lignes de saisie** non sauvegardées ; choisir le
   fournisseur CARTE exact et 10 000. Vérifier que le sélecteur propose la
   confirmation existante `TEST-B04-CARTE-001`, puis la sélectionner une fois.
   Aucun rapprochement nécessaire avec l'état actuellement vérifié. Si elle est
   toujours absente, relever cache/réponse GET et identité de ligne ; arrêter
   avant toute nouvelle confirmation ou validation.
5. AIRTEL MONEY : aucune confirmation n'existe encore. Pour la recette mixte,
   l'acquérir une seule fois humainement avec preuve et fournisseur explicites,
   sous l'autorisation de recette correspondante ; rafraîchir les détails avant
   de la sélectionner. Une simple ligne d'aperçu ne suffit pas. Ne pas inventer
   une confirmation ni recycler la référence CARTE.
6. Vérifier les totaux attendus, puis, seulement lors de la recette financière
   autorisée, enregistrer les règlements, confirmer la ventilation explicite et
   vérifier 33 800 / 67 600 par vente et 90 000 espèces nettes. Ne finaliser qu'après
   validation de ces étapes ; contrôler ensuite reçus et rejeu sans double effet.

Diagnostic terminé ; aucune correction mise en œuvre. Attente de l'autorisation
explicite du propriétaire avant modification applicative ou poursuite de recette.


# Corrections finales B04 autorisées — UI-001, M06, M07, UX-002

## Modifications de cette étape

Les corrections portent sur `presentation/web/caisse.js`,
`presentation/web/encaissement_groupe.js` et `presentation/web/style.css`.
Ajout de `tests/b04_final_ui.cjs` ; adaptation de l'hôte simulé du test
`tests/b03_payment_choices_unit.cjs` pour exécuter l'initialiseur modal et les
méthodes de validité du sélecteur. Le présent rapport est complété.

Aucune modification supplémentaire des calculs serveur, du domaine, des modèles,
allocations financières, migrations, permissions serveur, droits, preuves,
confirmations indépendantes, idempotence, fidélité, stock ou prise en charge.
Les modifications Python B04 visibles dans Git précèdent cette étape ; elles
n'ont pas été retouchées. Aucun commit, push, merge ou autre bloc commencé.

### UI-001 — Initialisation sur le formulaire réellement affiché

`cashPay` retourne maintenant un initialiseur selon le contrat existant de
`cashModal`. Après clonage et ouverture, cet initialiseur lit les champs de
`entry.form`, résout son récapitulatif et y attache `input`/`change`. Il calcule
immédiatement l'état initial, puis actualise le texte du clone à chaque saisie et
changement de confirmation. Le composant partagé `creation_dialogs.js` et les
calculs serveur sont inchangés.

### M06 — Détails frais, références et sélections préservées

Un rafraîchissement de lecture des fiches du brouillon est appelé après une
acquisition ou un rapprochement explicitement effectué par l'utilisateur, et
lors de l'actualisation générale. Il ne fait que des GET de détails de ventes.
La recharge explicite du dossier relit également ces détails. Les retours sont
contrôlés par identité de vente avant remplacement du cache ; une erreur de
lecture est affichée et bloque la validation jusqu'à une lecture fraîche réussie.
Après une erreur, la lecture suivante couvre l'ensemble du groupe.

Les lignes, montants et sélections restent en mémoire lors de la lecture. Une
sélection devenue incompatible n'est pas remplacée par une autre : elle reste
visible, signalée comme à vérifier, et l'enregistrement est refusé. Si
l'utilisateur change le moyen d'une ligne portant une sélection, une confirmation
explicite demande de détacher cette sélection ; le paiement indépendant acquis
n'est pas supprimé. Les références et fournisseurs apparaissent dans les choix
et dans un texte pouvant revenir à la ligne sous la sélection.

La confirmation `TEST-B04-CARTE-001` est proposée par le filtre lorsque le cache
frais contient son identité exacte, son fournisseur CARTE et le montant 10 000.
Aucune nouvelle confirmation CARTE ni aucun rapprochement artificiel exécuté.
Les contrôles serveur de session, révision, fournisseur, montant et consommation
restent l'autorité. L'interface ne prétend pas remplacer ces validations.

### M07 — Consultation et conservation des saisies

Après chargement, les états de `Recharger`, `Consulter`, `Actualiser` et de la
pagination sont recalculés individuellement. Ils tiennent compte du droit de
consultation, de l'existence du dossier, de l'ID saisi, de la page et de l'absence
d'opération en cours. Le champ d'ID déclenche aussi ce calcul. Aucun
réenclenchement global des commandes : les conditions existantes de finalisation
restent en place, complétées par le contrôle de fraîcheur et de sélection.
Les champs de saisie sont temporairement verrouillés pendant l'opération, avec
restauration de leur état propre après celle-ci.

Recharger le même dossier conserve les lignes et montants locaux, y compris une
liste entièrement vidée par l'utilisateur. L'hydratation des lignes sauvegardées
est réservée à la première lecture du dossier. Les allocations manuelles locales
sont conservées pendant une simple actualisation des confirmations. Une recharge
explicite remplaçant une ventilation non enregistrée exige une confirmation.
Changer d'identifiant avec des saisies locales non enregistrées exige également
une décision explicite ; annuler ne lit ni ne remplace le dossier.

### UX-002 — Rangées compactes et accessibles

Chaque paiement présente `Moyen | Montant | ×`. Le bouton × possède un nom
accessible numéroté. Une seconde rangée pleine largeur contient la confirmation
uniquement pour un moyen non espèces. Aucun champ de confirmation ni de rendu
par ligne n'est affiché pour ESPÈCES ; le rendu reste dans les totaux immédiats.
Les légendes, libellés, contrôles clavier natifs et noms accessibles sont
conservés. Les styles prévoient une rangée adaptée aux écrans étroits et des
références pouvant revenir à la ligne. Aucun nouvel écran ni suppression des
étapes d'enregistrement, de ventilation explicite et de validation.

## Tests des corrections finales

```powershell
node tests/b04_final_ui.cjs
node tests/b03_payment_choices_unit.cjs
node tests/b04_rendu_unit.cjs
node --check src/neosys_pharma/presentation/web/caisse.js
node --check src/neosys_pharma/presentation/web/encaissement_groupe.js
node --check tests/b04_final_ui.cjs
git diff --check
```

Résultat : **41 assertions nouvelles**, **58 assertions B03** et **18 assertions
B04 antérieures** réussies, soit **117 assertions JavaScript**. Syntaxe et diff
valides. Les nouvelles assertions traversent les fonctions réelles
`cashPay → cashModal → creationDialogCreate → creationDialogOpen`, avec clonage,
reset, ouverture et saisie sur le formulaire cloné ; transport et DOM sont simulés.

Couverture nouvelle : aperçu initial/excédentaire/insuffisant, changement de case
de confirmation, source détachée intacte ; cache périmé puis frais ; fournisseur
explicite ; rafraîchissement après acquisition/rapprochement simulés ; échec de
lecture et reprise ; conservation des montants et identités ; incompatibilité
signalée et refusée ; états des consultations, ID vide et absence de permission ;
absence de recharge concurrente ; annulation de perte de ventilation ; maintien
d'une allocation éditée pendant la reconstruction du rendu ; maintien d'une liste
vidée et hydratation initiale ; annulation d'un changement de dossier ; changement
de moyen annulé conservant la confirmation ; références lisibles ; suppression
accessible ; trois cellules et aucune confirmation pour les espèces.

Non-régressions serveur dans un projet de tests distinct :

```powershell
docker compose -p neosys-pharma-b04-tests -f compose.yaml --profile test run --rm --no-deps --build tests python -m pytest -q -rs -p no:cacheprovider tests/test_b04_rendu.py tests/test_encaissement_groupe_domain.py tests/test_caisse.py tests/test_b01_moyens_paiement.py tests/test_moyens_paiement.py tests/test_b02_payment_name_unit.py tests/test_p5b_3_encaissement_prise_en_charge.py
```

Le runner de tests existant refuse les URL de connexion héritées et impose des
fixtures SQLite en mémoire. Aucun service PostgreSQL démarré par ces tests
(`--no-deps`), aucune connexion aux données de recette B04 ou aux bases conservées.
Seul le secret de tests du service est fourni ; aucune valeur affichée.

Résultat serveur final : **93 passed, 5 skipped, 3 subtests passed**, en
**269,03 s**, code de sortie **0**. Un avertissement préexistant de dépréciation
Starlette/httpx. Les cinq tests ignorés sont les mêmes cas natifs de
`tests/test_caisse.py` : `test_concurrence_postgresql_encaissement_session_et_points`
(skip ligne 236), `test_concurrence_postgresql_ouverture_session` (386),
`test_concurrence_postgresql_finalisation_groupe_meme_cle` (1059),
`test_concurrence_postgresql_encaissement_individuel_contre_groupe` (1128),
`test_concurrence_postgresql_deux_dossiers_meme_vente` (1187).

## Limites et état de livraison

- Aucun nouveau test PostgreSQL natif de concurrence/verrouillage ; les cas
  nécessitant deux connexions sont explicitement ignorés dans SQLite.
- Les suites DOM historiques dépendant de jsdom ne sont pas exécutées : cette
  dépendance est indisponible dans le runtime Node du checkout. Les nouveaux tests
  couvrent le cycle modal partagé réel avec un DOM simulé, sans installer de
  dépendance ni modifier le composant partagé.
- Aucune nouvelle recette financière ni validation visuelle en navigateur réel
  dans cette étape. Responsive, focus et compacité restent à confirmer visuellement
  après déploiement de ces sources dans la seule application de recette B04.
- **Les corrections sont locales ; elles ne sont pas déployées dans l'image figée
  servant actuellement 8004.** Aucun rebuild/redémarrage/recréation de cette
  application ou de PostgreSQL B04 exécuté. Les données de recette, le brouillon
  `474a1999-38b1-418b-96af-9cceed2984f0` et la confirmation acquise restent conservés.
- Aucun paiement, confirmation, rapprochement, seed ou migration exécuté sur B04.
  Aucun nettoyage ni intervention de cycle de vie sur 8001/8003. Le conteneur de
  tests est jetable selon `--rm` ; son réseau isolé est laissé en place.

La reprise humaine doit utiliser les données existantes, sans rejouer le simple
déjà encaissé et sans recréer `TEST-B04-CARTE-001`. Confirmer d'abord dans le
navigateur corrigé : aperçu simple actualisé sans soumission, recharge du dossier
avec saisies préservées, disponibilité de la CARTE existante et rangées compactes.
AIRTEL ne pourra être sélectionné comme règlement confirmé qu'après acquisition
humaine explicite de sa propre confirmation. Ne finaliser que dans la recette
financière autorisée. Arrêt après B04 et attente de validation.


## Déploiement ciblé 8004 après validation des corrections

Les corrections finales sont désormais servies sur **http://127.0.0.1:8004/**.
L'ancienne mention « non déployées » ci-dessus décrit l'état avant cette nouvelle
autorisation. Seul app B04 a été remplacé (`051c86127217`), après sauvegarde et
restauration vérifiées des sept fichiers temporaires privés ; aucune migration
ou seed rejoué. PostgreSQL reste `ebe59b76ce97`, même démarrage et tmpfs.
Les quatre ressources HTTP (caisse.js, encaissement_groupe.js, style.css et HTML)
ont une empreinte SHA-256 exactement égale à celle des sources locales corrigées.
La comparaison SQL avant/après confirme ventes, session, brouillon, confirmation
CARTE et révisions inchangés. Les conteneurs 8001/8003 ont les mêmes IDs, images
et dates de démarrage. Aucune nouvelle confirmation ou finalisation.

Méthode, commandes, empreintes, état des conteneurs et reprise humaine détaillés
dans `docs/RECETTE_B04_ISOLEE.md`, section de déploiement en tête du document.
La nouvelle recette visuelle/financière n'a pas été exécutée automatiquement.
Aucun commit, push ou merge. Arrêt après déploiement B04.


# Audit final financier et diagnostics UI-002 / UX-003 — 21 octobre 2026

## Conclusion actuelle

**Audit financier conforme : 36 contrôles réussis, aucun écart financier observé.**
Le dossier `G-B04-001-000001` est finalisé une seule fois dans l'état persistant
observé. Les montants, allocations, confirmations, mouvements, liens et intégrité
des trois reçus correspondent exactement à la recette validée par le propriétaire.

La recette financière B04 peut être considérée validée sur ce scénario. La
**clôture globale B04 reste à arbitrer** : UI-002 est une anomalie d'actualisation
confirmée et UX-003 est un déplacement de fonctionnalité demandé mais non réalisé.
Recommandation : corriger ces deux points après autorisation, faire leurs tests
ciblés et la vérification humaine, puis décider de la clôture et du commit.
Aucune modification applicative effectuée pendant cet audit ; seul ce rapport
est complété. Aucun B05 commencé.

## Méthode et limites de la lecture

Toutes les connexions SQL ciblent exclusivement B04, via le runner vérifiant
`neosys_browser`, `neosys_test`, serveur `172.23.0.2`, port interne 5432, égal au
`test-db` du réseau B04, relais `127.0.0.1:55432`. Les transactions sont déclarées
`read_only=True` ou `SET TRANSACTION READ ONLY`. La passe de 36 assertions utilise
également `REPEATABLE READ` ; `SHOW transaction_read_only` retourne **on**.
Les scripts d'audit sont transmis via stdin, sans fichier applicatif créé.

Aucun POST, aucune requête de finalisation/rejeu, aucun paiement, rapprochement,
seed, migration, connexion SQL Windows/8001/8003, arrêt Docker, nettoyage, commit,
push ou merge. Les données finalisées ont été uniquement lues.

## Tableau des contrôles et résultats

| Contrôle | Attendu | Observé / conclusion |
|---|---|---|
| Cible SQL | neosys_browser / neosys_test, serveur B04 | Conforme, IP 172.23.0.2 |
| PostgreSQL | même conteneur, tmpfs, pas de port publié | `ebe59b76ce97`, même démarrage `2026-10-21T13:33:32.629685165Z`, tmpfs `/var/lib/postgresql`, ports `{}` |
| Isolation DB | réseau interne B04 uniquement | `neosys-pharma-b04-recette_testing`, inchangé |
| Dossier | G-B04-001-000001 FINALISE | ID `474a1999-38b1-418b-96af-9cceed2984f0`, numéro 1, révision 5, total 101 400 |
| Ventes groupées | 0002 / 0003 ENCAISSEE | Deux ventes ENCAISSEE, révisions 5 ; instantanés de préparation révision 4 |
| Finalisation unique observée | un dossier, un événement, une opération | 1 dossier de cette référence, 1 DOSSIER_GROUPE_FINALISE et 1 stock_operation pour sa clé |
| Identité de l'opération | clé/audit cohérents, empreinte présente | même opération `1cc91197-a63c-4f70-9aaa-118503ef614b`, empreinte de requête 64 caractères |
| Reçus individuels | un par vente | Deux IDs distincts liés aux bonnes ventes, session et période |
| Reçu collectif | PDF du dossier finalisé | Présent, 2 526 octets, SHA-256 conforme aux octets stockés et à l'audit |
| Montants bruts/rendus/nets | 101 900 / 500 / 101 400 | Exactement conformes |
| Allocations | quatre affectations exactes | Conforme au tableau ci-dessous, couvertures nettes exactes par vente et règlement |
| Confirmations | CARTE et AIRTEL acquises une fois | Deux références exactes ; chacune liée à un seul règlement groupé et à aucun règlement individuel |
| Identités des confirmations | vente/session/fournisseur/mode/montant | Conforme ; fournisseurs actifs et organisation commune |
| Mouvements groupés | un mouvement par règlement | 3 mouvements, mêmes règlements/session ; espèces nettes 90 000 |
| Absence de doublon individuel du groupe | aucun règlement individuel comptabilisant ces paiements | Aucun `caisse_reglements` rattaché aux deux encaissements groupés ; leurs instantanés conservent les allocations |
| Session | même session ouverte | `89869cab-4520-452e-a7d1-1d54060b31cf`, OUVERTE, révision 3 (2 avant le groupe) |
| Historique caisse | un final + deux événements de ventes | Un final et deux VENTE_ENCAISSEE_GROUPEE, mêmes IDs, opération et révision finale 5 |
| Historique ventes | un événement groupé par vente | Deux ENCAISSEMENT_GROUPE, mêmes références/reçus/opération |
| Vente 0001 | conservation du simple antérieur | Même ID, ENCAISSEE, révision 5, reçu unique de 7 000 ; PDF SHA-256 identique à l'audit antérieur ; exclue du groupe |
| Historique 0001 | aucun nouvel effet du groupe | Aucun événement de cette vente à partir de la finalisation du groupe ; mouvement individuel toujours 7 000 nets |
| Environnements conservés | pas d'intervention sur 8001/8003 | IDs, images et démarrages identiques au relevé de déploiement ; aucune de leurs bases consultée |
| Liste actuelle d'attente | aucune vente transmise restante B04 | SQL : 0 ; fonction de route `caisse_attente` : items=[], total=0 |

La finalisation est horodatée **2026-10-21 15:59:51.738232 UTC**, soit **16:59:51
Africa/Lagos**. Les deux événements de vente et les événements caisse associés
appartiennent à la même opération. Les confirmations conservent la révision de
vente **4** de leur acquisition ; le passage des ventes à **5** après encaissement
est attendu, pas un défaut de rapprochement.

### Règlements et allocations vérifiés

| Moyen / référence | Brut FCFA | Rendu FCFA | Net FCFA | Mouvement groupé |
|---|---:|---:|---:|---|
| CARTE — TEST-B04-CARTE-001 | 10 000 | 0 | 10 000 | Unique, 10 000 |
| ESPÈCES | 90 500 | 500 | 90 000 | Unique, 90 000 |
| AIRTEL MONEY — TEST-B04-AIRTEL-001 | 1 400 | 0 | 1 400 | Unique, 1 400 |
| **Total** | **101 900** | **500** | **101 400** | **3 mouvements** |

| Ticket | CARTE | ESPÈCES nettes | AIRTEL MONEY | Total alloué / dû |
|---|---:|---:|---:|---:|
| 0002 | 10 000 | 23 800 | 0 | 33 800 / 33 800 |
| 0003 | 0 | 66 200 | 1 400 | 67 600 / 67 600 |
| **Total** | **10 000** | **90 000** | **1 400** | **101 400 / 101 400** |

Les quatre allocations sont uniques. Leur somme par règlement égale son net ;
leur somme par vente égale son dû. Les instantanés des reçus individuels
référencent les mêmes `reglement_groupe_id` et `allocation_id`. Le rendu 500 est
porté une seule fois par le règlement espèces du groupe ; les reçus individuels
présentent leurs parts nettes, sans dupliquer ce rendu.

### Liens des reçus et intégrité

| Reçu | ID / lien | Taille | SHA-256 vérifié |
|---|---|---:|---|
| Individuel 0002 | `b0b79d9b-f12c-49c2-a0f7-d36e6c147207` → vente `cb13d88e-bba5-447c-b6ee-f6aa149c40d9` | 2 353 | `7bf329d708cc489f36065e8922c06f39bb1777c155b9d1c8aeed5d59770a0bb8` |
| Individuel 0003 | `1209ca3f-3b8b-4d43-9b63-f17cdacea031` → vente `3cacdabe-89ae-49e7-805c-85fba54f81c5` | 2 358 | `c2041ed02901953e2e1445cacf4a64be2f7aaa19960f19303dfb9e56b8806c49` |
| Collectif | PDF du dossier `474a1999-38b1-418b-96af-9cceed2984f0`, référence G-B04-001-000001 | 2 526 | `926400f09f2fcb799c91c3bed89b4bcf5cb2761c7dba57c183918dd738f8ddf0` |

Les trois blobs commencent par `%PDF-` et leur SHA-256 recalculé correspond au
champ stocké et aux références d'audit. Leur contrôle visuel a été déclaré validé
par le propriétaire ; l'agent n'a ni régénéré ni réimprimé les PDF dans cet audit.
Le PDF du simple 0001 conserve son empreinte historique
`df6be4717f92249eaf2abe0c5e24ed7bb740eebd1d85ce76bfb426ec4809a946`.

## Limites : unicité observée et protections non réexercées

- La présence d'une seule opération et d'un seul événement prouve l'absence de
  duplication **dans l'état observé**. Aucun rejeu d'idempotence n'est envoyé :
  ce contrôle ne constitue pas un test dynamique de rejeu du dossier finalisé.
- Aucune concurrence PostgreSQL native exercée. Les cinq tests natifs ignorés
  lors des suites SQLite antérieures restent non couverts par cet audit.
- Les lectures sont cohérentes dans leur snapshot ; aucun test de résistance à
  une écriture concurrente n'est effectué.
- La conservation de 0001 est vérifiée sur identité/état/révision, reçu et PDF,
  mouvement et historique. Il n'existe pas de préimage exhaustive de chaque
  colonne métier : ne pas présenter ce contrôle comme une comparaison universelle
  de toutes les colonnes de la base.
- Pour 8001/8003, identité/image/démarrage des conteneurs et absence d'intervention
  de l'agent sont vérifiés ; le contenu de leurs bases n'est volontairement pas
  consulté. Aucun checksum de leurs données n'est revendiqué.

## B04-UI-002 — Actualisation après finalisation

### Défauts confirmés

Dans `presentation/web/encaissement_groupe.js`, après la réponse valide du POST,
`cgFinalize` remplace `cashGroupState.draft`, contrôle FINALISE et les reçus,
nettoie ses clés de finalisation, puis appelle `cgRenderDraft`. Le `finally`
appelle `cgBusy(false)`. **Aucun `cgLoadSales` ni `cashLoad` n'est appelé après
le succès**. Le dossier et les reçus deviennent donc finalisés, mais la liste
transmise déjà affichée reste telle quelle. Le rendu de fin de busy ne relit pas
cette liste.

Les sélections des tickets encaissés ne sont pas purgées du `Map selected`.
Les `saleDetails` peuvent aussi rester à TRANSMISE ; la session locale peut
conserver la révision 2 alors que la base est passée à 3. Le rafraîchissement des
confirmations introduit précédemment n'est pas automatiquement déclenché par la
finalisation groupée. Ces états locaux périmés expliquent des actions ou totaux de
sélection incohérents ; ils ne prouvent aucun second encaissement serveur.

`cgLoadSales` présente en outre une course de lectures : après ses `await`, il
applique toujours la réponse à `cash-group-sales`, sans numéro de génération,
contrôle du contexte (site/session/mode/page) ou rejet d'une réponse antérieure.
Plusieurs lectures peuvent se chevaucher (retour au mode, F12, pagination,
actualisations manuelles). Une lecture commencée avant la finalisation peut
arriver après une lecture fraîche et réafficher les tickets encaissés.

### Reproduction et réponses vérifiées

La fonction réelle `cgLoadSales` a été exécutée dans Node VM, transport et DOM
simulés, sans requête HTTP ni appel de finalisation : deux lectures en attente ;
la seconde rend `items=[]` ; la première arrive ensuite avec deux ventes et les
réaffiche. Assertions réussies : **une réponse périmée peut écraser la fraîche**.

En B04, la requête SQL actuelle filtre exactement `etat='TRANSMISE'` et retourne
zéro ligne. La fonction de route `caisse_attente`, appelée directement dans une
transaction SQL en lecture seule, retourne :

```json
{"items":[],"total":0,"page":1,"page_size":15}
```

Il ne s'agit pas d'une nouvelle session HTTP authentifiée. Aucun POST/rejeu ni
mutation n'a été utilisé pour obtenir cette réponse. Le GET statique du JavaScript
sur 8004 renvoie 200, contenu identique au code local audité et
`Cache-Control: no-store`. Le middleware pose aussi `no-store` sur les réponses
API ; aucun cache HTTP explicite n'est configuré par `authFetch`/`cashRequest`.

**Conclusion causale** : l'oubli de rafraîchissement après succès est confirmé.
La course de lectures est également reproduite et peut expliquer les
actualisations répétées. Sans trace réseau historique du navigateur, il n'est
pas possible d'affirmer qu'elle est l'unique cause de chaque clic observé.
Aucun défaut d'état financier ou de filtre SQL n'est mis en évidence.

### Correction minimale proposée — P1, sans second encaissement

1. Après confirmation serveur validée, conserver le résultat FINALISE et les
   reçus comme état terminal. Retirer seulement les IDs finalisés des sélections
   et marquer/invalider les détails correspondants, sans toucher à d'autres
   sélections encore admissibles.
2. Déclencher un rafraîchissement **de lecture** de la liste d'attente, des
   sessions (révision courante) et de l'historique utile. Garder le dossier
   finalisé affiché ; aucun rechargement complet de page nécessaire.
3. Versionner/invalider les lectures de liste avant la finalisation et avant tout
   nouveau chargement. N'appliquer que la dernière génération correspondant au
   site/contexte/page courants. Si la dernière page est devenue vide, ajuster la
   pagination par lecture bornée, sans boucle d'actualisation incontrôlée.
4. Si cette lecture échoue après le succès financier, afficher « Encaissement
   effectué ; actualisation à réessayer ». Le bouton de reprise doit refaire
   uniquement les GET, **jamais le POST de finalisation**. Ne pas confondre cette
   erreur avec un échec financier et ne pas réactiver les commandes du dossier
   terminal. Préserver les contrôles/clefs d'idempotence existants.

Fichiers probables : `encaissement_groupe.js` principalement ; `caisse.js` si une
petite fonction de rafraîchissement sessions/historique est réutilisée plutôt que
le chargement global. Aucune modification serveur nécessaire d'après l'audit.

Tests à ajouter en environnement isolé : une seule mutation simulée suivie des
lectures ; disparition immédiate des seuls tickets finalisés ; reçus conservés ;
session actualisée ; inversion de réponses anciennes/fraîches ; échec GET après
succès puis reprise uniquement en lecture ; changement de site/page pendant une
lecture ; page finale devenue vide ; aucune réactivation d'un dossier FINALISE.

## B04-UX-003 — Déplacer le ticket d'appel dans Ventes – Préparation

### Faisabilité sans changement de logique métier

Le bouton est actuellement construit par `cashRender` dans `caisse.js` pour une
vente TRANSMISE, si `configuration.ticket_appel` est actif, avec permission
`vente.consulter`. Son GET existant est :
`/api/caisses/organisations/{organisation_id}/ventes/{vente_id}/appel/pdf`.
Malgré son préfixe caisse, la route exige **vente.consulter**, pas une permission
d'encaissement, et n'impose aucune session de caisse ouverte.

`caisse_appel_pdf` lit la vente autorisée, vérifie le paramétrage, puis lit le
numéro d'appel existant. Désactivation ou absence de numéro : 409. La route
appelle `appel_pdf` et ne crée aucun règlement, encaissement ou numéro.
`appel_pdf` produit déjà deux pages : **CLIENT** et **PANIER DE PRÉPARATION**,
avec « Document de préparation - ne vaut pas reçu de paiement. ».
Cela fournit les exemplaires client et suivi interne ; le serveur ne commande
pas matériellement deux sorties d'imprimante.

Le numéro est attribué par le parcours de transmission existant, via
`VenteService.changer_etat(..., 'TRANSMISE', ...)`. Il faut réutiliser le GET,
**pas appeler `CaisseService.appel` lors d'une impression**, car cette dernière
fonction peut créer un numéro en son absence.

### Proposition minimale — P2

- Déplacer l'action du rendu caisse vers les outils de `venteRender` dans
  `vente.js`, pour une vente TRANSMISE (avant encaissement) et, pour réimpression,
  ENCAISSEE selon le même droit `vente.consulter` et le périmètre d'emplacement.
  Les ventes sans numéro/ancien historique gardent le refus explicite du serveur.
- Utiliser le GET et le générateur PDF existants ; réutiliser la mécanique
  d'ouverture authentifiée de `cashPDF` (ou son petit socle commun) plutôt que
  recopier la logique financière. Le chemin doit utiliser l'ID de la vente
  courante de Préparation et l'organisation courante, sans dépendre de
  `cashState.sale` ou d'une session de caisse sélectionnée.
- Retirer le bouton du module Encaissement & Fidélité ; conserver le paramétrage
  d'activation et le contrôle serveur. Ne pas ajouter `caisse.consulter` au vendeur
  pour pouvoir lire le contexte caisse : son endpoint `/contexte` utilise d'autres
  permissions. Sans extension de contexte, le bouton peut expliquer le refus
  409 à l'ouverture ; si son masquage selon configuration est requis, exposer
  uniquement ce booléen en lecture dans le contexte Vente, sans nouvel octroi.
- Libellé explicite « Ticket d'appel · client + suivi interne » ; réimpression
  par le même GET, sans revalidation, sans nouvelle transmission et sans nouveau
  numéro. Ce document reste distinct du reçu de paiement.

Fichiers concernés : `presentation/web/vente.js`, `presentation/web/caisse.js`,
tests DOM Vente/Caisse et tests de route dans `tests/test_caisse.py` (ou test dédié).
`presentation/caisse_api.py` et `infrastructure/caisse_pdf.py` sont des dépendances
à réutiliser et tester ; aucune modification nécessaire à ce stade.
`presentation/vente_api.py` seulement si le booléen de configuration est exposé.
Aucune entité, aucun modèle, aucune migration ni règle financière à modifier.

Risques à couvrir : affichage chez un vendeur sans permission caisse, mauvais ID
à cause d'un ancien état caisse, document bloqué par le navigateur, configuration
désactivée, vente sans numéro, double attribution de numéro, réimpression d'un
document confondue avec une nouvelle transaction. Préserver l'organisation/site/
emplacement courants et l'absence de side effects sur impression/réimpression.

Tests proposés : bouton dans Préparation après transmission, absent en caisse ;
permission vente.consulter seule suffisante sur le bon emplacement ; refus sans
permission/hors organisation/site ; absence de session caisse non bloquante ;
PDF deux pages avec les deux libellés et l'avertissement non-reçu ; réimpression
même numéro ; aucune mutation de vente/stock/paiement/séquence ; refus 409 si
configuration inactive ou numéro absent. Le test existant
`test_sessions_confirmation_et_numeros_independants` vérifie déjà la séquence
d'appel indépendante et les deux pages ; l'étendre sans l'affaiblir.

## Anomalies et décision de clôture

| Élément | État |
|---|---|
| Finance du groupe et reçus | Conforme, recette humaine validée et audit lecture seule positif |
| UI-002 | Anomalie confirmée : absence de rafraîchissement après succès ; course de lectures reproduite |
| UX-003 | Évolution de placement demandée ; faisable sans changer la logique métier |
| Rapport JSON de check_initial.py | Erreur Decimal antérieure toujours connue, hors périmètre des corrections déjà faites |
| Rejeu d'idempotence / concurrence native | Non exercés par cet audit, limites maintenues |

Aucun écart financier n'impose d'annuler, restituer, réencaisser ou modifier le
G-B04-001-000001. **Ne pas utiliser ce dossier finalisé pour tester de nouvelles
finalisations.** Les futures corrections et tests de scénarios financiers doivent
utiliser leur environnement isolé autorisé. Attendre l'arbitrage/correction des
observations avant la clôture logicielle B04 ; aucun commit autorisé ici.

## Fichiers pour un futur commit B04 — proposition, sans staging

À inclure après validation finale du périmètre et revue du diff :

- `src/neosys_pharma/domain/encaissement_groupe.py` ;
- `src/neosys_pharma/application/encaissement_groupe_service.py` ;
- `src/neosys_pharma/presentation/web/caisse.js` ;
- `src/neosys_pharma/presentation/web/encaissement_groupe.js` ;
- `src/neosys_pharma/presentation/web/index.html` ;
- `src/neosys_pharma/presentation/web/style.css` ;
- `tests/b03_payment_choices_unit.cjs` ;
- `tests/b04_rendu_unit.cjs` ;
- `tests/b04_final_ui.cjs` ;
- `tests/test_b04_rendu.py` ;
- `docs/RAPPORT_B04.md` ;
- `docs/RECETTE_B04_ISOLEE.md` (documentation de recette, sans mot de passe).

Si les deux nouvelles corrections sont autorisées avant clôture, ajouter leurs
fichiers modifiés et leurs tests ciblés ; notamment `vente.js` pour UX-003. Ne pas
anticiper ces modifications dans le commit avant leur réalisation/validation.

À exclure du commit fonctionnel, à conserver localement :

- `compose.b03-recette.yaml` : exclusion impérative demandée, aucune modification ;
- `compose.b04-recette.yaml` et `docker/b04-recette/{runner.py,seed_b04.py,check_initial.py}` :
  outillage local de recette, proposition de maintien hors commit fonctionnel ;
  leur éventuel versionnement doit être arbitré séparément, notamment à cause
  de l'erreur de sortie connue du script de contrôle ;
- `.secrets/` dans son intégralité : mots de passe, accès fictifs, archive de
  préservation et snapshots privés compris ; aucune valeur à ajouter au rapport ;
- `.env`, dumps, exports/PDF de recette, caches et artefacts locaux éventuels.

La proposition ne modifie ni `.gitignore` ni l'index Git. Aucun `git add`, commit,
push ou merge exécuté. Seul le rapport a été complété dans ce tour.

Audit et diagnostics terminés. Attente de l'autorisation du propriétaire pour
les corrections UI-002 / UX-003 et pour toute décision de clôture/commit B04.

## Livraison locale UI-002 / UX-003 — 21 octobre 2026

Cette section remplace l'attente d'autorisation de correction indiquée ci-dessus.
Les deux corrections ont été autorisées puis implémentées **localement** sur
`dev/codex-docker`. Le remplacement de l'application 8004 reste soumis à une
autorisation distincte et n'a pas été exécuté. Aucun commit, staging, push ou merge.

### Modifications de cette livraison

| Fichier | Modification |
|---|---|
| `presentation/web/encaissement_groupe.js` | Après réponse FINALISE avec reçus, conserver le dossier, invalider les lectures antérieures, retirer immédiatement les lignes et sélections des ventes finalisées, invalider leur ancien détail/confirmation, puis relire les listes, la session, l'historique des reçus et les détails des ventes par GET. |
| `presentation/web/caisse.js` | La lecture réutilisée du module caisse contrôle génération, organisation, site, pages et module courant ; les lignes sont identifiées par vente pour leur retrait immédiat. Ancien bouton d'appel retiré. |
| `presentation/web/vente.js` | Bouton « Ticket d'appel · client + suivi interne » dans les actions de la vente courante, seulement TRANSMISE ou ENCAISSEE avec numéro, paramétrage actif et permission vente.consulter. Réutilisation de cashPDF et du GET existant, sans session caisse. |
| `presentation/vente_api.py` | Ajouts en lecture uniquement : booléen ticket_appel dans le contexte Préparation, numero_appel existant dans le détail autorisé de la vente. Aucun octroi de permission caisse ni attribution de numéro. |
| `tests/b04_refresh_ticket_ui.cjs` | Tests des vrais contrôleurs avec DOM/transport simulés : courses, contexte, pagination, succès, erreur/reprise et placement du ticket. |
| `tests/test_b04_ticket_appel.py` | HTTP/PDF et comparaison de toutes les colonnes des tables vente/caisse/stock/encaissement avant/après les impressions, y compris séquences, révisions, historique et pièces financières. |
| `docs/RAPPORT_B04.md` | Résultats, limites et procédure de déploiement proposée. |

Les chemins applicatifs du tableau sont relatifs à `src/neosys_pharma/`.
Les modifications métier, HTML et CSS déjà présentes avant cette livraison sont
conservées ; aucune modification supplémentaire de calcul, modèle, service PDF,
allocation, permission, confirmation, numérotation ou migration dans cette étape.

UI-002 : chaque lecture des préparations possède une génération et un contexte
organisation/site/session/mode/module/page. Une réponse ou une erreur périmée ne
remplace plus la liste récente. La sélection asynchrone d'une ligne suit le même
contrôle. Si la page dépasse la dernière page disponible, une nouvelle lecture
bien bornée est faite sur la page corrigée. Les autres sélections ne sont pas
supprimées au seul motif qu'elles ne figurent pas sur la page consultée.

Une fois la réponse financière confirmée, le POST est terminé. Le contrôleur
`cgRefreshAfterFinalization` ne contient que des lectures. En cas d'échec, il
affiche « Encaissement effectué ; seule l’actualisation a échoué » avec un bouton
« Réessayer l’actualisation » qui appelle ce contrôleur, jamais la finalisation.
Le dossier FINALISE et ses trois reçus restent attachés. Les validations serveur,
la clé d'idempotence et les conditions de finalisation restent conservées.

UX-003 : le serveur conserve les refus 403/409 existants. Le nouveau contexte
évite d'appeler un endpoint de configuration caisse avec un droit vendeur.
Le PDF reste celui du service existant : CLIENT puis PANIER DE PRÉPARATION, avec
« Document de préparation - ne vaut pas reçu de paiement ». Le bouton s'appuie
sur l'identifiant Préparation, même si une autre vente était consultée en caisse.

### Vérifications et tests exécutés

Commandes locales exécutées, sans serveur ni base de recette :

```powershell
node tests/b04_refresh_ticket_ui.cjs
node tests/b04_final_ui.cjs
node tests/b03_payment_choices_unit.cjs
node tests/b04_rendu_unit.cjs
node --check src/neosys_pharma/presentation/web/encaissement_groupe.js
node --check src/neosys_pharma/presentation/web/caisse.js
node --check src/neosys_pharma/presentation/web/vente.js
git diff --check
```

Résultats : **35 + 41 + 58 + 18 = 152 assertions JavaScript réussies** ;
les trois contrôles de syntaxe et `git diff --check` réussissent.
L'analyse AST de `presentation/vente_api.py` et
`tests/test_b04_ticket_appel.py` réussit aussi, sans import applicatif ni connexion.

Couverture ciblée : actualisation automatique après un seul POST ; GET sessions,
attente et reçus réellement demandés par cashLoad ; ancienne liste reçue après une
liste récente ; ancienne erreur ignorée ; changement de site/page pendant GET ;
ancienne lecture invalidée lors de la finalisation ; dernière page vide ajustée ;
reçus et dossier conservés ; échec GET puis reprise sans POST ; numéro et vente
courante corrects pour impression ; réimpression et masquages selon droits,
configuration, état et numéro.

La première exécution Python ciblée a retourné **2 passed, 3 failed** en 18,75 s :
deux assertions attendaient à tort le mot « encaissement » au lieu de
l'avertissement réel du ticket ; une fixture tentait de supprimer un appel et
a correctement rencontré le trigger « Journal financier immuable ». Les tests
ont été corrigés : libellé réel et création d'une préparation sans numéro au lieu
de suppression du journal. Aucun trigger ni contrôle applicatif affaibli.

Commande de non-régression élargie exécutée :

```powershell
docker compose -p neosys-pharma-b04-tests --env-file .env.docker.example -f compose.yaml --profile test run --rm --no-deps --build tests python -m pytest -q -rs -p no:cacheprovider tests/test_b04_ticket_appel.py tests/test_b04_rendu.py tests/test_encaissement_groupe_domain.py tests/test_caisse.py tests/test_b01_moyens_paiement.py tests/test_moyens_paiement.py tests/test_b02_payment_name_unit.py tests/test_p5b_3_encaissement_prise_en_charge.py tests/test_vente.py
```

Isolation : image et conteneur de tests du projet `neosys-pharma-b04-tests`,
`--no-deps`, fixtures SQLite mémoire ; le runner refuse les URL héritées puis
fixe `TEST_DATABASE_URL=sqlite+pysqlite://`. Aucun PostgreSQL démarré ou consulté
pour ces tests. Aucun seed/migration de recette. Le conteneur de test est éphémère
via `--rm` ; aucune purge de volume ou de réseau.

Résultat Python final après correction et relance complète : **124 passed,
6 skipped, 3 subtests passed**, en **318,74 s**, **aucun échec** ; un avertissement
Starlette/httpx de dépréciation. Les cinq nouveaux tests HTTP/PDF sont réussis.

L'élargissement initial à `tests/test_vente.py` a retourné **123 passed, 1 failed,
6 skipped, 3 subtests passed**, en **350,73 s**. Le test existant
`test_rollback_revision_idempotence_et_retrait` a détecté l'ajout inutile de
`numero_appel: null` au GET d'une préparation sans appel. Correction de
compatibilité : le détail n'est enrichi que lorsqu'un appel existe ; la forme
historique reste intacte sinon. Le test existant n'a pas été modifié. La même
commande complète a été relancée sur l'image reconstruite après cette correction.

Les six skips sont explicites et inchangés : `tests/test_caisse.py:236`
(encaissement/session/points concurrents), `:386` (ouvertures de session), `:1059`
(finalisations groupées avec même clé), `:1128` (individuel contre groupé), `:1187`
(deux dossiers pour la même vente), et `tests/test_vente.py:136` (vente/stock
concurrents). Ils exigent deux connexions PostgreSQL natives ; aucune protection
n'a été contournée pour les forcer sous SQLite. Un avertissement de dépréciation
Starlette/httpx était également présent, sans effet sur le résultat des contrôles.

Limites maintenues : pas de nouvelle recette dans un navigateur réel ni de
comparaison visuelle de ces deux corrections avant déploiement autorisé ; DOM et
transport simulés pour les tests JavaScript ; suites DOM historiques dépendant de
jsdom non exécutées (dépendance absente du checkout). Pas de rejeu sur le dossier
B04 existant, ni de concurrence PostgreSQL native ; ces données sont préservées.
Les tests de réimpression HTTP couvrent une vente transmise et une vente encaissée,
avec session fermée et rôle réduit à vente.consulter, PDF deux pages, refus droits/
configuration/numéro/organisation/site et absence de mutation des tables suivies.

### Déploiement ciblé 8004 proposé — NE PAS EXÉCUTER avant autorisation

Méthode identique au dernier déploiement validé : nouvelle image figée, remplacement
de **app seulement**, conservation intégrale de test-db et restauration contrôlée
du tmpfs applicatif. La procédure détaillée de préservation est dans
`docs/RECETTE_B04_ISOLEE.md`, « Méthode et conservation préalable » et « Commandes
exécutées et résultats ». Ce sont des étapes à refaire avec une **nouvelle**
archive ; l'ancienne capture SQL décrivait un brouillon et ne doit pas servir de
référence après la finalisation humaine.

1. Vérifier Git, les identités/images/dates de démarrage des six conteneurs,
   les montages/réseaux et les ports, sans imprimer les variables d'environnement.
   Contrôler test-db B04 : même ID complet que l'audit, tmpfs /var/lib/postgresql,
   aucun port PostgreSQL ni volume. Faire `runner.py check-target` en lecture seule.
2. Capturer à nouveau, par transactions SQL strictement read-only, l'état
   actuellement finalisé : G-B04-001-000001 FINALISE révision 5, ventes 0001/0002/
   0003 ENCAISSEE révision 5, session et confirmations, reçus/PDF, allocations,
   mouvements et historique. Comparer l'identité de la cible avant toute suite.
   Arrêter si la conservation n'est pas garantie ; aucune remise à zéro.
3. Préserver dans un nouveau répertoire privé sous `.secrets/`, ACL restreintes,
   les fichiers tmpfs nécessaires : b04-connexion.txt, b04-fixture.json,
   b04-pre-migration.json, les trois marqueurs de seed et b04-deployment-state.json.
   Inventorier sans afficher les contenus ; inclure tout autre fichier B04 requis
   constaté au contrôle. Archiver par liste blanche + manifeste SHA-256 ; transfert
   base64 directement vers fichier privé (docker cp ne lisait pas le tmpfs sur
   ce moteur). Valider chaque membre/empreinte avant de remplacer app. Aucun
   secret PostgreSQL dans l'archive ou l'image, aucune régénération d'identifiant.
4. Seulement après ces contrôles et sauvegardes réussis, commandes prévues :

```powershell
docker build --target tests -t neosys-pharma-b04-recette:local .
docker compose -p neosys-pharma-b04-recette --env-file .env.docker.example -f compose.b04-recette.yaml config --quiet
docker compose -p neosys-pharma-b04-recette --env-file .env.docker.example -f compose.b04-recette.yaml up -d --no-deps --no-build --pull never --force-recreate app
```

5. Restaurer uniquement les membres validés dans le nouveau /tmp, avec création
   exclusive (O_EXCL), mode 0600, uid/gid 10001 et contrôle SHA-256, comme lors du
   précédent déploiement. Ne pas supprimer ni remplacer d'autre fichier. Le secret
   local dédié et le runner restent montés en lecture seule par Compose ; le relais
   redémarre uniquement dans app, boucle locale 127.0.0.1:55432 vers test-db B04.
6. Avant HTTP, refaire le contrôle de destination. Aucune migration ni seed :

```powershell
docker compose -p neosys-pharma-b04-recette --env-file .env.docker.example -f compose.b04-recette.yaml exec -T app python /opt/neosys/recette/runner.py check-target
docker compose -p neosys-pharma-b04-recette --env-file .env.docker.example -f compose.b04-recette.yaml exec -d app python /opt/neosys/recette/runner.py run python -m uvicorn neosys_pharma.presentation.app:app --host 0.0.0.0 --port 8000
```

7. GET /health et / sur 8004 ; comparer les SHA-256 HTTP des trois JS modifiés
   aux sources locales ; comparer exactement le snapshot SQL avant/après et l'ID/
   démarrage de test-db ; confirmer les quatre conteneurs 8001/8003 inchangés.
   Ne pas exécuter check_initial.py comme test de vacuité ou de tickets transmis :
   l'environnement est désormais finalisé. Aucun POST financier pour vérifier.

Conséquences prévues : courte indisponibilité HTTP 8004, nouvelle image locale
et nouveau conteneur app, /tmp app restauré ; **aucun** changement PostgreSQL,
réseau, volume, donnée financière, migration, seed, projet Docker ou autre recette.
Ne jamais exécuter compose down ni une commande de cycle de vie visant test-db.

### Reprise humaine après déploiement autorisé

- Recharger une fois les ressources du navigateur ; consulter le dossier finalisé
  et ses trois reçus, sans bouton de finalisation utilisable. Actualiser les listes
  et confirmer que 0002/0003 ne sont plus en attente. Aucun nouveau paiement.
- Dans Ventes – Préparation, ouvrir une vente avec numéro déjà existant, notamment
  une vente encaissée : contrôler le nouveau bouton, deux pages client/suivi interne,
  même numéro à la réimpression et absence du bouton dans Encaissement & Fidélité.
  Vérifier aussi un vendeur autorisé sans droits caisse. Ne pas modifier les rôles
  ou le paramétrage de recette sans autorisation dédiée.
- Le succès automatique d'une nouvelle finalisation et l'erreur GET après POST
  sont couverts par tests isolés. Leur reproduction humaine demanderait des
  données supplémentaires et une autorisation ; ne pas rejouer G-B04-001-000001.

### Git et décision

Ajouter à la proposition de futur commit B04 : `presentation/vente_api.py`,
`presentation/web/vente.js`, `tests/b04_refresh_ticket_ui.cjs` et
`tests/test_b04_ticket_appel.py`, avec les modifications caisse/groupé et le
rapport déjà listés. Les exclusions antérieures restent valides : Compose B03
intouché, outillage local B04 non ajouté, `.secrets/`, .env, PDF, archives et caches.
Les quatre fichiers de domaine/service/HTML/CSS modifiés avant cette étape ne
doivent pas être confondus avec les nouvelles modifications autorisées ici.

Déploiement non exécuté. Aucun accès financier à la base B04 pendant cette
implémentation. Attendre l'autorisation de remplacement de l'application 8004,
puis la validation humaine finale avant décision de clôture logicielle B04.

## Dernier déploiement de recette autorisé — UI-002 / UX-003 — 21 octobre 2026

**Déploiement réalisé sur http://127.0.0.1:8004/ ; contrôle humain attendu.**
Cette section remplace le statut « déploiement non exécuté » de la livraison
locale précédente. Aucun nouveau changement applicatif dans cette étape.
Branche `dev/codex-docker`, HEAD toujours
`4f91780b4a557640b0b42769b0a25f9e6da708a4` : aucun nouveau commit, push ou merge.

### Contrôles préalables et sauvegarde

- Identités des six conteneurs vérifiées avant remplacement, ainsi que montages,
  images, dates de démarrage, ports et réseaux, sans afficher les environnements
  ou les secrets. Le premier format d'inspection échouait sur le champ optionnel
  Tmpfs absent de certains conteneurs ; format corrigé avec `index` et inspection
  relancée en lecture seule avant toute opération de remplacement.
- PostgreSQL B04 est toujours
  `ebe59b76ce97d5618fa9aec2b40c06443e0f88d3cc09a17d17b1492e538d1fb7`,
  démarré le `2026-10-21T13:33:32.629685165Z`, tmpfs `/var/lib/postgresql`,
  aucun volume de données, aucun port PostgreSQL publié (`5432/tcp: null`).
  Seul réseau : `neosys-pharma-b04-recette_testing`, IP `172.23.0.2`.
- `runner.py check-target`, avant remplacement et après restauration : base
  `neosys_browser`, utilisateur `neosys_test`, serveur `172.23.0.2:5432`, égal au
  DNS test-db B04 ; relais `127.0.0.1:55432` ; 131 relations publiques.
- Capture initiale puis contrôle juste avant remplacement en transactions
  `read_only=True`, isolation REPEATABLE READ, vérification explicite
  `transaction_read_only=on` et identité serveur. Alembic `20261019_06`.
  Capture exhaustive des lignes de **51 tables** ventes/caisse/stock/fidélité,
  avec révisions, confirmations, allocations, opérations et événements d'audit.
  Les octets PDF sont hachés et comparés à leur empreinte enregistrée en base.
- Nouveau répertoire privé : `.secrets/b04-deploiement-final-20261021/`, ignoré
  par Git, exclu du contexte Docker, ACL uniquement compte Windows courant et
  SYSTEM. Captures SQL, métadonnées Docker, contrôles HTTP et scripts de contrôle
  y sont conservés. Aucun mot de passe affiché ou ajouté à ce rapport.
- Huit fichiers de `/tmp` sauvegardés : b04-connexion.txt, b04-fixture.json,
  b04-pre-migration.json, b04-seed-first-failed, b04-seed-started,
  b04-seed-completed, b04-deployment-state.json et b04-tmp-manifest.json.
  Archive par liste blanche de fichiers ordinaires, manifeste SHA-256 séparé,
  transfert base64 directement vers fichier privé, validation complète avant
  remplacement. Empreinte de `app-tmp-verified.tar` :
  `faa37c3a1e1d6c5f0b3d5b11c004f5066103193ff82effde5c08b00ed77ed60b`.
  Le secret PostgreSQL dédié reste dans son montage en lecture seule et n'est
  ni archivé ni intégré à l'image.

### Commandes et méthode réellement utilisées

Depuis le checkout, `git branch --show-current`, `git rev-parse HEAD`,
`git status --short` et `git diff --check` ; `docker ps --no-trunc` puis
`docker inspect --format ...` avec uniquement les champs non secrets.
Les fichiers `snapshot.py`, `archive.py`, `restore.py`, `verify_archive.py`,
`http_preserved.py`, `http_b04.py` et `runtime.py` sont des scripts privés de
preuve de ce déploiement, conservés dans le nouveau répertoire ignoré.

```powershell
$b04Dir='.secrets/b04-deploiement-final-20261021'
Get-Content "$b04Dir/snapshot.py" -Raw | docker exec -i neosys-pharma-b04-recette-app-1 python - > "$b04Dir/sql-before.json"
Get-Content "$b04Dir/archive.py" -Raw | docker exec -i neosys-pharma-b04-recette-app-1 python - > "$b04Dir/app-tmp.b64"
python "$b04Dir/verify_archive.py"
python "$b04Dir/http_preserved.py" before
docker compose -p neosys-pharma-b04-recette --env-file .env.docker.example -f compose.b04-recette.yaml config --quiet
docker build --target tests -t neosys-pharma-b04-recette:local .
```

Contrôle SQL renouvelé juste avant remplacement (`sql-pre-replace.json`) : même
empreinte que sql-before, identité test-db inchangée, archive revérifiée.
Build et configuration : codes 0. Puis :

```powershell
docker compose -p neosys-pharma-b04-recette --env-file .env.docker.example -f compose.b04-recette.yaml up -d --no-deps --no-build --pull never --force-recreate app
$b04Restore=Get-Content "$b04Dir/restore.py" -Raw
Get-Content "$b04Dir/app-tmp.b64" -Raw | docker compose -p neosys-pharma-b04-recette --env-file .env.docker.example -f compose.b04-recette.yaml exec -T --user 0 app python -c $b04Restore
docker compose -p neosys-pharma-b04-recette --env-file .env.docker.example -f compose.b04-recette.yaml exec -T app python /opt/neosys/recette/runner.py check-target
docker compose -p neosys-pharma-b04-recette --env-file .env.docker.example -f compose.b04-recette.yaml exec -d app python /opt/neosys/recette/runner.py run python -m uvicorn neosys_pharma.presentation.app:app --host 0.0.0.0 --port 8000
```

Codes 0 ; seul `app Recreate` exécuté. Restauration : **8/8 fichiers identiques**,
création exclusive O_EXCL, propriétaire `10001:10001`, mode `0600`, aucun autre
fichier supprimé. Le relais redémarre dans le nouvel app ; son écoute a été
vérifiée dans `/proc/net/tcp` : uniquement `127.0.0.1:55432`, destination test-db
B04 vérifiée. Garde groupé actif, trois marqueurs autorisés confinés au Compose
B04 inchangé. Aucun seed, bootstrap, migration, down ou nettoyage exécuté.

### Conteneurs après remplacement

| Environnement | Service | Identifiant | Résultat |
|---|---|---|---|
| 8001 | app | `1d05b1290dae` | Identité/image/démarrage/montages/réseaux inchangés ; healthy |
| 8001 | db | `a334ec625935` | Identique ; healthy ; aucune connexion SQL effectuée |
| 8003 | app | `1ae8ef53bf39` | Identique ; actif |
| 8003 | test-db | `a4082410121d` | Identique ; healthy ; aucune connexion SQL effectuée |
| 8004 | app | `ef96ca4f81df` | Nouveau, actif, publication uniquement 127.0.0.1:8004 |
| 8004 | test-db | `ebe59b76ce97` | Identique, même démarrage et réseau ; healthy |

App remplacé : `051c86127217` →
`ef96ca4f81df1d7b2feeee92c4d3033e54651a7a251e88d54b3557067aea5cad`.
Nouveau démarrage `2026-10-21T18:42:58.071405314Z` (19:42:58, Africa/Lagos).
Image attachée au nouvel app :
`sha256:846a43142dc2d9aa149ba6b6ecc173f42341a8f3aee00d2fbe59389cba41e97d`,
tag `neosys-pharma-b04-recette:local`. Aucun nouveau réseau, volume ou projet.

### Conservation financière constatée

Les captures `sql-before.json`, `sql-pre-replace.json`, `sql-after.json` et
`sql-final.json` ont la même empreinte canonique :
`94ceeb730bdabb1478e447f8194b2f34f79d8f4692e393424d8c3d35a2276ba4`.
La comparaison structurelle complète avant/finale est aussi strictement égale.

| Contrôle | Résultat avant/après |
|---|---|
| Dossier G-B04-001-000001 | Même ID, FINALISE, révision 5 |
| Ventes 0001/0002/0003 | Mêmes ID, toutes ENCAISSEE, révision 5, lignes et montants identiques |
| Session | `89869cab-4520-452e-a7d1-1d54060b31cf`, OUVERTE, révision 3, inchangée |
| Confirmations | Exactement 2, TEST-B04-CARTE-001 et TEST-B04-AIRTEL-001 ; identités, révisions et références identiques |
| Utilisation des confirmations | Deux liens groupés distincts, aucune utilisation individuelle supplémentaire |
| Règlements groupés | CARTE 10 000 ; ESPÈCES brut 90 500 / rendu 500 / net 90 000 ; MOBILE_MONEY 1 400, identiques |
| Allocations | Exactement 4 : vente 0002 CARTE 10 000 + ESPÈCES 23 800 ; vente 0003 ESPÈCES 66 200 + MOBILE_MONEY 1 400 |
| Mouvements groupés | Exactement 3, espèces nettes 90 000, aucune duplication |
| Reçus | Trois encaissements individuels au total dont les deux liés au dossier ; reçu collectif identique |
| Historique | 14 événements caisse, 15 événements vente et 30 opérations stock, contenus et nombres identiques |
| Alembic | Toujours 20261019_06 ; aucune migration appliquée |

Empreintes PDF calculées sur les octets et conservées avant/après :

| Pièce | SHA-256 |
|---|---|
| Reçu collectif G-B04-001-000001 | `926400f09f2fcb799c91c3bed89b4bcf5cb2761c7dba57c183918dd738f8ddf0` |
| Reçu vente 0002 | `7bf329d708cc489f36065e8922c06f39bb1777c155b9d1c8aeed5d59770a0bb8` |
| Reçu vente 0003 | `c2041ed02901953e2e1445cacf4a64be2f7aaa19960f19303dfb9e56b8806c49` |
| Reçu vente 0001, contrôle de conservation supplémentaire | `df6be4717f92249eaf2abe0c5e24ed7bb740eebd1d85ce76bfb426ec4809a946` |

### Ressources effectivement servies

`GET /health` : HTTP 200, `{"status":"ok","application":"NeoSys Pharma"}`.
Les réponses HTTP suivantes sont 200 et leurs octets sont exactement identiques
aux fichiers locaux. Preuve enregistrée dans `http-b04.json` :

| Ressource | SHA-256 |
|---|---|
| /static/encaissement_groupe.js | `a39266b3e3fbd6714add55638a9c466acacc33125467860fe2a939aa79bb1052` |
| /static/caisse.js | `0111bc561e09332eea3657973b15e7b574b4a3a5ad381b9f7fcede2707a91053` |
| /static/vente.js | `c977769ea2d78bd2ad22e206c7961ff5cf398cbd6e029f1a48909a4bfc3b4b94` |
| / (index.html) | `71b741a70c334fc86cbed4fbca16995429f5f56507c9c2c8bac70334b28c22d0` |
| /static/style.css | `56ddbf7779f4a4b8dea1a692113ff10a7f0b4fff0022512b07b73f4a13d8010e` |

Code `presentation/vente_api.py` présent dans le nouvel app, identique au local :
`0fb2fc710ef01b7441c0ece471d7c2cbc1d82ccc05a7c6f8f74c67e58a5614ce`.
Ainsi les ajouts de lecture du numéro et du paramétrage sont embarqués ; aucun
nouveau login ni appel métier authentifié effectué pour ce contrôle de déploiement.

Pour 8001 et 8003 : dix GET avant et dix après (`/health`, `/` et les trois JS
pour chacun), tous HTTP 200 et empreintes strictement identiques. Métadonnées des
cinq conteneurs conservés strictement égales avant/après. Aucun accès à leurs
bases, aucune modification de leurs ressources Docker.

### Recette humaine courte — consultation et impression uniquement

1. Ouvrir http://127.0.0.1:8004/, recharger une fois les ressources du navigateur
   si nécessaire, puis se connecter avec les accès fictifs privés existants
   (`.secrets/b04-connexion.txt`, mot de passe non reproduit ici).
2. Encaissement multiple : actualiser les préparations ; 0002 et 0003 doivent
   être absentes. Ne pas créer de vente, de dossier, de règlement ou confirmation.
3. Reprendre G-B04-001-000001 en consultation : FINALISÉ, reçus collectif et deux
   individuels disponibles, montants validés conservés ; aucune finalisation.
4. Ventes – Préparation : ouvrir une vente déjà encaissée avec numéro existant,
   par exemple 0002. Cliquer « Ticket d'appel · client + suivi interne » ; vérifier
   les deux pages CLIENT et PANIER DE PRÉPARATION, même numéro à la réimpression,
   et l'avertissement de document distinct d'un reçu. Aucun nouveau numéro attendu.
5. Encaissement & Fidélité : consulter la même vente et constater l'absence de
   l'ancien bouton de ticket d'appel. Le paramétrage d'activation reste à sa place.

Ne pas modifier les permissions ou le paramétrage pour ce contrôle ; le droit
vendeur seul et les refus ont déjà été vérifiés par tests isolés. L'automatisme
après une nouvelle finalisation et la reprise après erreur GET restent couverts
par les tests précédents ; ne pas rejouer le dossier finalisé pour les reproduire.

**Aucune anomalie de déploiement ou de conservation restante constatée.** Les
tests financiers n'ont pas été relancés sur la recette. Aucun paiement,
remboursement, rapprochement, confirmation, rejeu, migration, seed, bootstrap,
nettoyage, commit, push ou merge. Le déploiement est terminé ; arrêt en attente
du contrôle humain, sans commencer un autre bloc.

## Clôture B04 et autorisation de commit local — 21 octobre 2026

Le propriétaire valide la recette humaine finale sur 8004 : encaissement groupé,
reçus et corrections UI-001, UI-002, M06, M07, UX-002 et UX-003 conformes sur les
scénarios exécutés. La réimpression du ticket d'appel **0002 conserve le numéro
0002**. B04 est clôturable dans ce périmètre validé, avec les limites ci-dessous.

- Audit financier : **36 contrôles conformes**, aucun écart observé ; les preuves
  et montants détaillés restent conservés dans la section d'audit final.
- Tests : **124 tests Python réussis, 152 assertions JavaScript réussies,
  3 sous-tests réussis et 6 tests ignorés**. Les six exclusions PostgreSQL natives
  restent documentées avec leurs emplacements ; elles ne constituent pas des
  validations de concurrence réelle sous PostgreSQL.
- Limite de rejeu dynamique : aucun POST de finalisation ni rejeu sur le dossier
  B04 finalisé n'a été émis pour l'audit, le déploiement ou cette clôture. Les
  contrôles d'unicité en base et tests isolés ne remplacent pas une campagne de
  rejeu/concurrence PostgreSQL native sur un environnement dédié autorisé.
- **Point P4-08 restant : « Net à régler » affiché pour une vente déjà encaissée.**
  Ce point d'affichage est conservé explicitement comme travail ultérieur ; aucune
  correction n'est ajoutée au commit B04 pour ce point et aucun autre bloc n'est
  engagé. Il ne remet pas en cause les montants nets et reçus validés en recette.

Commit local unique autorisé, sur `dev/codex-docker`, avec le titre :
`feat(p4): finaliser rendu monnaie et encaissement groupé B04`.
Contrôle du diff applicatif et des tests, `git diff --check`, contrôle des fichiers
indexés et recherche de contenus sensibles avant création. Aucun fichier secret,
configuration locale de recette, archive, export, dump, PDF de recette ou cache
à inclure. Les identifiants et empreintes non secrets des preuves techniques sont
conservés ; aucun mot de passe n'est reproduit dans les rapports.

Les exclusions impératives restent locales : `.secrets/`, `.env`,
`compose.b03-recette.yaml`, `compose.b04-recette.yaml`, `docker/b04-recette/` et
les artefacts de recette. Aucun changement Docker, SQL, paiement, migration ou
seed pendant la préparation du commit. Toutes les données de recette B04 sont
conservées. Aucun push, merge, changement de branche, P4-05 ou P5 autorisé.
