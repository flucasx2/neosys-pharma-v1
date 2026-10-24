# CI : développement économique et recette exacte

Branche technique : `chore/actions-economies`, issue de `main` (`fe53c42`). Aucun fichier métier, migration, test applicatif ou donnée P1/P2/P3/P4.5 n'est modifié.

## Déclenchements

| Événement | Contrôles |
| --- | --- |
| PR Draft, changements applicatifs | Politique CI + SQLite complet |
| PR, changements exclusivement documentaires | Politique CI uniquement |
| PR Ready, changements applicatifs | SQLite, puis PostgreSQL/migrations et Chromium |
| Passage Draft → Ready ou réouverture Ready | Relecture du diff de toute la PR ; recette complète si code concerné |
| Passage Ready → Draft | Annulation de l'automatisme précédent, retour à SQLite si code concerné |
| Push sur `main` | Politique CI + SQLite si changement applicatif |
| `workflow_dispatch`, branche sélectionnée | Recette complète, même si seuls les documents changent |

Aucun `push` de branche de travail n'exécute la CI. Une PR ouverte reçoit une seule exécution automatique, pas le couple push/PR.

La classification examine les chemins Git en format NUL, sans limite de pagination API. Pour `synchronize`, elle examine le delta depuis le SHA précédent ; un commit documentaire sur une PR ayant déjà du code ne relance donc pas les suites. Pour ouverture, Ready et réouverture, le diff base/HEAD complet est examiné. Les renommages incluent le chemin d'origine et celui de destination. Un diff vide, indisponible ou illisible déclenche les contrôles applicatifs par prudence ; un force-push peut revenir au diff de toute la PR.

Liste documentaire volontairement restreinte : `README.md`, `CHANGELOG.md`, `CONTRIBUTING.md`, `LICENSE`, et fichiers `.md`, `.rst`, `.txt` sous `docs/`. Les scripts, SQL, workflows, migrations, dépendances, tests et tout autre chemin ne bénéficient pas de l'exemption. Aucun filtre global `paths-ignore` ne supprime le contrôle stable `CI / changements`.

## La CI légère n'est pas une recette complète

Le statut de commit **`neosys/recette-complete`** est le contrôle final à rendre obligatoire dans la protection de `main`. Ne pas utiliser seulement `CI / synthèse`, `sqlite`, ni des jobs ignorés comme autorisation de fusion.

1. Chaque nouvelle exécution marque le SHA testé `pending`, invalidant la validation précédente de ce même SHA en cas de nouvel événement.
2. Tous les checkouts des jobs applicatifs sont épinglés à ce SHA complet : HEAD de PR et non commit de merge temporaire.
3. La suite SQLite et la suite PostgreSQL sont intégrales (`pytest -q`), sans exclusion des tests d'autorisation HTTP, 401/403, CSRF, isolation, concurrence et cycles Alembic existants. Les bases PostgreSQL et migrations sont distinctes et jetables.
4. Le statut final devient `success` uniquement si les trois jobs sont réellement `success`, si le checkout final correspond au SHA et si l'API confirme que le HEAD courant de la PR/branche est toujours ce SHA.
5. `skipped`, échec, annulation ou job manquant ne constituent jamais une recette complète. SQLite seul ou documentation seuls laissent le statut `pending`. Une erreur de vérification du HEAD produit un échec.
6. Un nouveau commit possède son propre statut : la recette d'un ancien SHA ne le valide pas. Un commit documentaire après recette nécessite également une recette manuelle sur son SHA exact avant fusion, conformément à la règle validée.
7. Une recette manuelle devenue obsolète continue sans interruption, conserve ses artefacts, mais ne peut valider le nouveau HEAD. La CI automatique annulée laisse son SHA en attente.

La synthèse technique peut réussir pour une CI légère ; elle affiche explicitement `pending` et n'est **pas** le contrôle obligatoire de recette. Les PR externes n'ont pas de droit d'écriture de statut : leur gate échoue explicitement ; la recette finale doit se faire sur une branche interne approuvée. Pas de `pull_request_target` ni de token privilégié exécutant du code externe.

### Protections et activation : limites constatées

Le 11 octobre 2026, l'API de branche indique `main.protected=false`. Lecture détaillée de protection : 403 « Resource not accessible by integration ». Lecture des rulesets : 403, fonctionnalité non disponible pour le dépôt privé avec le plan actuel selon GitHub. Les paramètres Actions ne sont pas lisibles avec l'outil disponible. Aucune protection, abonnement ou limite budgétaire n'a été modifié.

Le workflow prépare une validation stricte, mais **ne peut pas imposer un blocage serveur de fusion tant que la protection n'est pas activée**. Sans engager de dépense, garder la règle humaine : ne jamais fusionner sans `neosys/recette-complete=success` sur le dernier HEAD. Si le plan et les permissions le permettent, configurer ensuite `CI / changements` et `neosys/recette-complete` comme contrôles requis et interdire les contournements. L'intégration actuelle ne permet pas de certifier ou configurer ces réglages. Vérifier également les exigences de mise à jour avec `main` avant fusion.

`workflow_dispatch` doit être présent sur la branche par défaut avant son activation dans GitHub. Aucun workflow n'est fusionné ici. Après activation approuvée, choisir Actions → NeoSys CI → Run workflow → branche exacte, ou :

```bash
gh workflow run tests.yml --ref main \
  -f target_branch=BRANCHE_A_RECETTER \
  -f expected_sha=SHA_COMPLET_DE_40_CARACTERES
```

Le workflow de contrôle est sélectionné sur `main`, tandis que `target_branch` et `expected_sha` désignent le code applicatif. Le job de planification vérifie le HEAD cible avant les suites ; un décalage du SHA échoue. Les tests SQLite/PostgreSQL travaillent sur ce SHA cible. Chromium et la synthèse extraient séparément le contrôleur CI dans `.ci-control`, épinglé au SHA du workflow, afin de fonctionner même si la branche P4.5 possède encore l'ancien workflow et aucun dossier `ci/`. Une seconde vérification du HEAD cible est faite avant publication du statut. Sélectionner directement l'ancienne branche P4.5 avec `--ref feat/p4-vente-caisse` n'est donc pas la bonne commande.

Vérifier les deux SHA affichés (code ciblé et contrôleur) et le statut du dernier HEAD avant toute fusion. Ne pas laisser la future fusion de P4 écraser le workflow approuvé dans `main` ; ce conflit devra être résolu lors de l'intégration autorisée. La PR #4 n'est pas modifiée par cette livraison.

## Annulation, durée et dépendances

Les événements automatiques partagent un groupe par PR/branche, avec `cancel-in-progress`. Les recettes manuelles ont un groupe par run ID avec annulation désactivée ; un push ne les interrompt pas. Pas de relance automatique des échecs. Limites : classification/synthèse 5 minutes, SQLite 15, PostgreSQL 20, Chromium 15.

Aucun cache pip ajouté : les installations historiques ne prennent que 11–17 secondes par job, et aucun gain net cache/restauration n'est encore mesuré. N'ajouter `setup-python` avec `cache: pip` et `cache-dependency-path: pyproject.toml` qu'après comparaison à dépendances identiques entre cache absent et cache présent, sans créer des runs uniquement pour mesurer. Ne pas mettre en cache le virtualenv ni remplacer l'installation par la restauration. Pour Chromium, l'installation observée prend 20–25 secondes ; pas de cache binaire spéculatif.

Les parcours navigateur existants sont exécutés dans leur ordre de jeux de données. Le runner supporte les parcours P4 lorsqu'ils sont présents dans le checkout (sans ajouter ces fonctionnalités à `main`). Les cinq parcours P1/P2/P3 sont obligatoires. Les modules Vente/Proforma/Caisse/Régularisations présents imposent les parcours supplémentaires correspondants et leurs prérequis. La migration P4.5 `f22f6abb13c5` impose également les neuf parcours même si le fichier service Régularisations est absent. Chaque parcours et chaque seed manquant fait échouer la recette. Tout nouveau script `browser_*.py` non enregistré fait échouer la recette au lieu d'être ignoré. Les reçus, PDF et captures gardent leur collecte ; les nouveaux artefacts portent SHA et run ID, avec conservation de 30 jours.

## Conservation P4.5

La recette existante réussie est conservée : commit `9f09af42a22b20a1528fba3d93b986dd105209e1`, [run PR 38152190064](https://github.com/flucasx2/neosys-pharma-v1/actions/runs/38152190064), run push `38152185889`. Les artefacts de ce run sont des références historiques ; leur disponibilité et leur expiration ne sont pas attestées par cette publication. Cette preuve ne valide pas automatiquement un nouveau SHA.

## Tests locaux et runner Ubuntu optionnel

Préparer une installation locale Python 3.14 et les dépendances du projet dans un virtualenv, puis :

```bash
python -m unittest discover -s ci/tests -v
pytest -q tests/TEST_CONCERNE.py
pytest -q
```

La première commande ne nécessite que la bibliothèque standard et ne touche à aucune base. Les suites applicatives complètes sont utiles avant push lorsque le code change ; ne pas relancer un test réussi sans modification ou anomalie nouvelle.

Pour une recette PostgreSQL locale, utiliser exclusivement PostgreSQL 17 jetable (conteneur ou VM dédiée), avec bases distinctes `neosys_test`, `neosys_migration`, `neosys_browser`. Ne jamais utiliser la base métier locale ni un serveur de production. Passer les deux URL de test uniquement au processus pytest :

```bash
TEST_DATABASE_URL=postgresql+psycopg://UTILISATEUR:MOT_DE_PASSE@127.0.0.1:PORT/neosys_test \
TEST_MIGRATION_DATABASE_URL=postgresql+psycopg://UTILISATEUR:MOT_DE_PASSE@127.0.0.1:PORT/neosys_migration \
pytest -q
```

Les tests Alembic existants exécutent upgrade/check/downgrade/upgrade sur cette base migrations jetable. Après installation locale de `playwright==1.58.0` et de Chromium (`python -m playwright install --with-deps chromium`), préparer une base navigateur neuve et :

```bash
DATABASE_URL=postgresql+psycopg://UTILISATEUR:MOT_DE_PASSE@127.0.0.1:PORT/neosys_browser \
AUTH_COOKIE_SECURE=false python ci/browser.py
```

Un éventuel runner Ubuntu dédié doit être sans données métier ni secrets de production, réservé aux branches internes approuvées et équipé de Docker, Python 3.14 et Chromium. Nettoyage des bases/espaces de travail après chaque run, utilisateur dédié et permissions minimales, jobs PostgreSQL isolés et ports sans collision. Préinstaller les dépendances système ne dispense pas de vérifier les versions Python/Playwright. Préférer des instances de runner éphémères ou une VM réinitialisable. Aucun runner installé, machine louée ou dépense engagée dans cette livraison.

## Validation technique de cette livraison

30 tests locaux de politique/recette : documentation, changements mixtes, renommage de code vers docs, suppression, accents, diff force-push indisponible, Draft/Ready/réouverture, delta documentaire, SHA exact, nouveau HEAD, mauvais checkout, refus des jobs ignorés/échoués/annulés/manquants, erreur API, publication pending/success, refus des forks et parcours navigateur inconnus. Parsing YAML et contrôle local des événements, permissions, dépendances, SHA épinglés, timeouts et groupes concurrency. `git diff --check` réussi.

Aucune suite métier ni CI GitHub relancée : absence de changement applicatif, recette P4.5 déjà réussie et contrainte de dépenses. La branche technique est publiée sans PR pour éviter un déclenchement automatique avant revue ; activation réelle et recette GitHub du nouveau workflow restent à valider lors de l'intégration autorisée.

## Revue complémentaire du commit 9931439

Deux anomalies démontrées et corrigées : sélection du mauvais workflow pour une recette manuelle P4.5 et omission possible d'un parcours connu supprimé. La documentation REST actuelle de GitHub indique que GET /pulls/{number} accepte `contents: read` ou `pull-requests: read`, mais l'exécution réelle de la PR #5 (run 38165644680) a reçu un HTTP 403 avec `contents: read`. La correction autorisée ajoute donc `pull-requests: read` uniquement au job `CI / synthèse`, qui consulte le HEAD courant via l'API PR. Les permissions globales restent `contents: read` ; la classification et les jobs applicatifs ne reçoivent aucun droit supplémentaire de lecture PR. Références : https://docs.github.com/en/rest/pulls/pulls#get-a-pull-request et https://docs.github.com/en/rest/commits/statuses#create-a-commit-status. `statuses: write` reste limité aux jobs de classification et synthèse ; les jobs exécutant les suites applicatives ont seulement `contents: read`. Aucune écriture de statut GitHub n'est effectuée pendant cette revue.

Validation complémentaire ciblée : 12 nouveaux tests passent, dont des appels HTTP réels à un serveur **local** vérifiant le chemin /statuses/{SHA}, le contexte, le corps JSON, l'authentification et le refus HTTP 403. Les tests couvrent également la cible manuelle distincte du contrôleur, le SHA changé au démarrage, les branches invalides, le refus d'un job ignoré, la suppression de chacun des neuf parcours et de chacun des seeds. Trois tests existants modifiés par ces corrections sont réexécutés et passent ; les 27 autres tests déjà réussis et les suites métier ne sont pas relancés. Les tests HTTP locaux ne démontrent pas l'autorisation réelle du GITHUB_TOKEN du dépôt : cette dernière nécessite une première exécution GitHub explicitement autorisée. Un refus de permission n'est jamais converti en validation réussie.

### Activation minimale proposée, sans exécution dans cette livraison

1. Vérifier dans GitHub les minutes restantes et que l'usage payant supplémentaire est bloqué. Les limites de dépense ne sont pas accessibles à cette intégration ; aucune augmentation ni abonnement demandé.
2. Après accord humain, ouvrir la PR technique vers `main`, conserver Draft pour le contrôle SQLite, puis Ready pour sa recette complète sur son dernier HEAD. Ne modifier ni intégrer le code P4.5 dans cette PR. Exiger le statut final exact avant son intégration humaine autorisée.
3. Après intégration autorisée du workflow dans `main`, lancer **une seule** recette P4.5 depuis le contrôleur `main`, sans modifier la PR #4 :

```bash
gh workflow run tests.yml --ref main \
  -f target_branch=feat/p4-vente-caisse \
  -f expected_sha=9f09af42a22b20a1528fba3d93b986dd105209e1
```

Actualiser explicitement `expected_sha` si la branche change ; ne pas réutiliser un SHA ancien. Conserver PR #4 Draft. Le premier run permettra de constater les permissions effectives, les neuf parcours, les artefacts et la publication réelle de `neosys/recette-complete` sur le SHA P4.5.
4. Vérifier les contrôles de branche disponibles. Sans protection serveur disponible, conserver impérativement la validation humaine du statut exact avant toute fusion ; aucune promesse de blocage serveur n'est faite.

Estimation de minutes de runner Ubuntu, et non de temps écoulé : contrôle documentaire 2–3 ; Draft applicatif 6–8 ; recette complète P4.5 environ 20–25 (SQLite 5–6, PostgreSQL 7–11, Chromium 4–5, contrôles et synthèse 2–3). Le parcours d'activation via PR technique Draft/Ready, contrôle `main` après intégration et une recette P4.5 représente environ **45–65 minutes** selon les durées des suites sur `main`. Ne pas effectuer des essais de recette redondants : Ready valide la PR technique, puis la recette manuelle cible le SHA P4.5 différent. Ces chiffres ne garantissent pas le montant facturé ni les minutes restantes du compte ; ne déclencher qu'après vérification du quota et accord. Consommation Actions de cette revue : zéro.
