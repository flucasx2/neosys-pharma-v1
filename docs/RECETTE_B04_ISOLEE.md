# B04 — Corrections déployées sur la recette 8004

## Validation humaine finale et clôture — 21 octobre 2026

Le propriétaire valide la recette finale B04 : encaissement groupé et reçus,
UI-001, UI-002, M06, M07, UX-002 et UX-003 conformes sur les scénarios exécutés.
La réimpression du ticket d'appel **0002 conserve le numéro 0002**.
Les 36 contrôles financiers sont conformes ; les résultats de tests restent
124 Python réussis, 152 assertions JavaScript réussies, 3 sous-tests réussis et
6 tests ignorés nécessitant PostgreSQL natif. La concurrence PostgreSQL native
et le rejeu dynamique du dossier finalisé ne sont pas couverts par cette recette.

Point ultérieur conservé dans le rapport : **P4-08 — « Net à régler » affiché pour
une vente déjà encaissée**, sans correction supplémentaire dans B04.
Un commit local unique B04 est autorisé ; aucun push ni merge. L'environnement,
ses données finalisées et les fichiers privés sont conservés sans intervention.
Les sections ci-dessous retracent le déploiement et l'attente de contrôle avant
cette validation finale ; elles restent des preuves historiques.

## État actuel — dernier déploiement UI-002 / UX-003 du 21 octobre 2026

**http://127.0.0.1:8004/** sert maintenant les corrections UI-002 et UX-003,
en complément des corrections B04 précédentes. Seul `app` a été remplacé avec
`--no-deps --no-build --pull never --force-recreate app`. Serveur HTTP relancé
manuellement après restauration et contrôle de destination ; aucune migration,
aucun seed, bootstrap, paiement, confirmation, rapprochement ou rejeu.

Nouveau app : `ef96ca4f81df1d7b2feeee92c4d3033e54651a7a251e88d54b3557067aea5cad`,
démarrage `2026-10-21T18:42:58.071405314Z` (19:42:58 Africa/Lagos).
Image `neosys-pharma-b04-recette:local`, identifiant attaché :
`sha256:846a43142dc2d9aa149ba6b6ecc173f42341a8f3aee00d2fbe59389cba41e97d`.
Ancien app `051c86127217` remplacé ; PostgreSQL reste
`ebe59b76ce97d5618fa9aec2b40c06443e0f88d3cc09a17d17b1492e538d1fb7`,
démarrage inchangé `2026-10-21T13:33:32.629685165Z`, tmpfs
`/var/lib/postgresql`, aucun volume de données ni port PostgreSQL publié.

Les contrôles avant/après confirment `neosys_browser`, `neosys_test`, serveur
`172.23.0.2:5432`, égal au DNS test-db B04, relais uniquement `127.0.0.1:55432`,
garde groupé actif. Révision Alembic conservée : `20261019_06`.

Sauvegarde **nouvelle**, à conserver :
`.secrets/b04-deploiement-final-20261021/`, ignorée par Git, exclue de l'image,
ACL compte local + SYSTEM. Huit fichiers temporaires restaurés à l'identique,
mode 0600, uid/gid 10001 : accès fictifs, fixture, preuve pré-migration, trois
marqueurs de seed, état du précédent déploiement et ancien manifeste tmpfs.
Archive vérifiée SHA-256 :
`faa37c3a1e1d6c5f0b3d5b11c004f5066103193ff82effde5c08b00ed77ed60b`.
Le secret PostgreSQL dédié n'a été ni copié, ni affiché, ni changé.

Comparaison SQL strictement read-only, avant, immédiatement avant remplacement,
après et après disponibilité HTTP : **51 tables identiques**, égalité des
captures JSON et empreinte financière commune
`94ceeb730bdabb1478e447f8194b2f34f79d8f4692e393424d8c3d35a2276ba4`.

| Données conservées | Résultat |
|---|---|
| G-B04-001-000001 | FINALISE, révision 5, même identité et mêmes reçus |
| Ventes 0001/0002/0003 | ENCAISSEE, révision 5 ; aucune modification |
| Session 89869cab-4520-452e-a7d1-1d54060b31cf | OUVERTE, révision 3 inchangée |
| Confirmations CARTE/AIRTEL MONEY | Exactement 2, liens uniques conservés |
| Règlements / allocations / mouvements du groupe | 3 / 4 / 3, mêmes lignes et montants ; espèces nettes 90 000 |
| Historique | 14 événements caisse, 15 événements vente, 30 opérations stock identiques |
| Quatre PDF, dont les trois du dossier | Empreintes inchangées, octets contrôlés |
| 8001 app/db | 1d05b1290dae / a334ec625935, métadonnées inchangées, healthy |
| 8003 app/test-db | 1ae8ef53bf39 / a4082410121d, métadonnées inchangées, actifs |

Les trois reçus du dossier conservent les SHA-256 suivants :

- Collectif : `926400f09f2fcb799c91c3bed89b4bcf5cb2761c7dba57c183918dd738f8ddf0`.
- Vente 0002 : `7bf329d708cc489f36065e8922c06f39bb1777c155b9d1c8aeed5d59770a0bb8`.
- Vente 0003 : `c2041ed02901953e2e1445cacf4a64be2f7aaa19960f19303dfb9e56b8806c49`.

HTTP 8004 : `/health`, `/` et ressources contrôlées répondent 200 ; les octets
servis correspondent aux fichiers locaux :

| Ressource | SHA-256 |
|---|---|
| encaissement_groupe.js | `a39266b3e3fbd6714add55638a9c466acacc33125467860fe2a939aa79bb1052` |
| caisse.js | `0111bc561e09332eea3657973b15e7b574b4a3a5ad381b9f7fcede2707a91053` |
| vente.js | `c977769ea2d78bd2ad22e206c7961ff5cf398cbd6e029f1a48909a4bfc3b4b94` |

`vente_api.py` embarqué correspond au local :
`0fb2fc710ef01b7441c0ece471d7c2cbc1d82ccc05a7c6f8f74c67e58a5614ce`.
Pour 8001/8003, dix GET avant et dix après donnent tous 200 et les mêmes
empreintes ; aucun accès à leurs bases ni commande de cycle de vie.
Les commandes détaillées, identités, empreintes index/CSS et preuves SQL sont
consignées dans `docs/RAPPORT_B04.md`, section « Dernier déploiement de recette
autorisé — UI-002 / UX-003 — 21 octobre 2026 ».

### Contrôle humain attendu, sans nouveau paiement

1. Ouvrir 8004 et recharger une fois les ressources si nécessaire. Utiliser les
   accès privés existants dans `.secrets/b04-connexion.txt`, sans les publier.
2. Encaissement multiple : actualiser la liste et constater que 0002/0003 ne sont
   plus en attente. Consulter G-B04-001-000001 FINALISÉ et ses trois reçus.
3. Ventes – Préparation : consulter 0002 déjà encaissée avec son numéro existant ;
   imprimer « Ticket d'appel · client + suivi interne », vérifier les deux pages
   CLIENT / PANIER DE PRÉPARATION et le même numéro à la réimpression.
4. Encaissement & Fidélité : vérifier l'absence de l'ancien bouton d'appel.

Ne créer aucune vente, confirmation, session ou dossier ; ne modifier aucun
paramétrage/droit ; ne pas finaliser ni rejouer le dossier existant. Aucune de ces
vérifications humaines n'a été exécutée automatiquement. Aucun commit autorisé.
Déploiement terminé, sans anomalie restante constatée ; attente du contrôle humain.

## Historique — état lors du déploiement antérieur UI-001 / M06 / M07 / UX-002

**http://127.0.0.1:8004/** répond avec les sources corrigées UI-001, M06, M07 et
UX-002. Seul le conteneur applicatif B04 a été remplacé. PostgreSQL B04, les quatre
conteneurs 8001/8003, leurs images et leurs dates de démarrage sont inchangés.
Aucune migration, aucun seed, aucune confirmation, aucun rapprochement et aucun
paiement exécuté. Aucun commit, push, merge, nettoyage de volume/réseau ou nouveau
projet Docker. Aucun code métier ou fichier de configuration modifié dans cette
étape. Branche `dev/codex-docker`, HEAD
`4f91780b4a557640b0b42769b0a25f9e6da708a4` inchangés.

## Méthode et conservation préalable

Reconstruction de l'image dédiée, puis remplacement **exclusif de app** avec
`--no-deps --force-recreate app`. Le serveur HTTP était lancé manuellement dans
l'ancien app ; le remplacement détruit son `/tmp` en tmpfs. Cette perte a été
anticipée avant la coupure : archive privée et empreintes vérifiées de sept
fichiers, restaurés à l'identique avant de relancer Uvicorn :

- `b04-connexion.txt` : accès fictifs, contenu jamais affiché ;
- `b04-fixture.json` ;
- `b04-pre-migration.json` ;
- `b04-seed-first-failed`, `b04-seed-started`, `b04-seed-completed` ;
- `b04-deployment-state.json` : état non secret des objets contrôlés avant déploiement.

Un manifeste SHA-256 complète l'archive. Les restaurations ont été contrôlées
contre ce manifeste : **7/7 identiques**, propriétaire Linux **10001:10001**, mode
**0600**. Les marqueurs de refus de réinitialisation restent présents.

Le secret PostgreSQL est resté dans son fichier local dédié monté en lecture
seule ; il n'a été ni régénéré, ni copié dans l'archive ou l'image, ni affiché.
Le relais a redémarré avec la même configuration : écoute seulement dans app sur
`127.0.0.1:55432`, destination unique `test-db:5432`, IP B04 `172.23.0.2`.
Le garde groupé du code est inchangé et son activation B04 est vérifiée.

Sauvegarde conservée sous `.secrets/b04-deploiement-20261021/`, ignorée par Git et
exclue du contexte Docker, ACL limitées au compte Windows courant et SYSTEM.
Elle contient des accès fictifs : ne pas la publier. Le fichier privé d'accès
habituel `.secrets/b04-connexion.txt` est inchangé et toujours utilisable.

## Commandes exécutées et résultats

Depuis `D:\Projets_Python\NeoSys_Pharma_Dev`. Vérifications Git, `git diff --check`,
inspection des six conteneurs et des deux réseaux B04 en lecture seule. Contrôles
SQL en transaction `read_only=True` : ventes 0001 encaissée, 0002/0003 transmises,
session ouverte, brouillon et confirmation attendus présents. Révision
`20261019_06`. La cible réelle est `neosys_browser` / `neosys_test` sur
`172.23.0.2`, identique au serveur `test-db` du réseau interne B04.

Les snapshots privés de métadonnées Docker, de l'état SQL et des empreintes des
sources ont été enregistrés avant remplacement. L'inventaire de `/tmp` a confirmé
les fichiers à préserver. Création de l'archive par Python dans l'ancien app,
sans lecture/affichage des valeurs de secrets PostgreSQL.

Tentative de transfert :

```powershell
docker cp neosys-pharma-b04-recette-app-1:/tmp/b04-app-preserve.tar .secrets/b04-deploiement-20261021/app-tmp.tar
```

Échec : le moteur Docker n'a pas exposé ce fichier du tmpfs à `docker cp`.
Aucun conteneur n'avait alors été remplacé. Transfert sûr utilisé à la place :

```powershell
docker compose -p neosys-pharma-b04-recette --env-file .env.docker.example -f compose.b04-recette.yaml exec -T app python -c "import base64; from pathlib import Path; print(base64.b64encode(Path('/tmp/b04-app-preserve.tar').read_bytes()).decode('ascii'))" > .secrets/b04-deploiement-20261021/app-tmp.b64
```

Code 0 ; sortie directement redirigée dans le répertoire privé, sans affichage.
Décodage local vers `app-tmp-verified.tar`, validation de la liste exacte des
membres, absence de chemin imbriqué/lien et comparaison de chaque SHA-256 : succès.
La conservation était garantie avant remplacement, sans redémarrer PostgreSQL.

```powershell
docker build --target tests -t neosys-pharma-b04-recette:local .
docker compose -p neosys-pharma-b04-recette --env-file .env.docker.example -f compose.b04-recette.yaml config --quiet
docker compose -p neosys-pharma-b04-recette --env-file .env.docker.example -f compose.b04-recette.yaml up -d --no-deps --no-build --pull never --force-recreate app
```

Codes 0. Seule la ligne `app Recreate` apparaît au remplacement. Aucun
`docker compose down`, aucune commande de cycle de vie sur `test-db`.

Restauration par flux privé et Python, exécuté en root **uniquement pour créer
les fichiers restaurés avec leur propriétaire 10001 et permissions 0600** :

```powershell
Get-Content -LiteralPath .secrets/b04-deploiement-20261021/app-tmp.b64 -Raw | docker compose -p neosys-pharma-b04-recette --env-file .env.docker.example -f compose.b04-recette.yaml exec -T --user 0 app python -c $b04Restore
```

`$b04Restore` était un script Python transmis en argument : décodage base64,
validation des huit membres (sept fichiers et manifeste), vérification SHA-256,
refus de remplacer un fichier déjà présent dans le nouveau `/tmp`, création avec
`O_EXCL`, puis `fchmod(0600)` et `fchown(10001,10001)`. Aucun extraction de chemin
libre, aucun autre fichier supprimé. Résultat : code 0, sept fichiers identiques.

```powershell
docker compose -p neosys-pharma-b04-recette --env-file .env.docker.example -f compose.b04-recette.yaml exec -T app python /opt/neosys/recette/runner.py check-target
docker compose -p neosys-pharma-b04-recette --env-file .env.docker.example -f compose.b04-recette.yaml exec -d app python /opt/neosys/recette/runner.py run python -m uvicorn neosys_pharma.presentation.app:app --host 0.0.0.0 --port 8000
```

Codes 0. Cible conservée confirmée avant Uvicorn. Le premier GET, lancé avant la
fin du démarrage, a reçu une fermeture de connexion ; le contrôle de disponibilité
avec attente courte et bornée a ensuite réussi, sans redémarrage supplémentaire.
Aucune erreur de fonctionnement restante constatée pendant le déploiement.

## Preuve des ressources réellement servies

`/health` retourne `{"status":"ok","application":"NeoSys Pharma"}`.
Les quatre réponses HTTP sont **200** et leurs octets correspondent exactement
aux fichiers locaux corrigés, vérification SHA-256 :

| Ressource HTTP | SHA-256 |
|---|---|
| `/static/caisse.js` | `18f1dc99ce32ce8c7380ff9d580112576b8817fe55603c06320ff2648e0b0d0d` |
| `/static/encaissement_groupe.js` | `e9073e7f84c1968f2efe80dafeb8cd7d01d5fd6d8ced9f23f10f25ab0dbe6260` |
| `/static/style.css` | `56ddbf7779f4a4b8dea1a692113ff10a7f0b4fff0022512b07b73f4a13d8010e` |
| `/` (`index.html`) | `71b741a70c334fc86cbed4fbca16995429f5f56507c9c2c8bac70334b28c22d0` |

Nouvelle image dédiée :
`sha256:6f8028bb529ada13d7de1a33bcd50115e68a27cfb73dfbf7bcf5965895cb3380`.
Elle contient les sources figées ; aucun montage du checkout/src dans app B04.

## État final des conteneurs et réseaux

| Service | ID avant | ID après | État final |
|---|---|---|---|
| App B04 — 8004 | `cd516948943c` | **`051c86127217`** | actif, HTTP vérifié |
| PostgreSQL B04 | `ebe59b76ce97` | **identique** | healthy |
| App 8001 | `1d05b1290dae` | identique | healthy |
| Base 8001 | `a334ec625935` | identique | healthy |
| App 8003 | `1ae8ef53bf39` | identique | actif |
| Base 8003 | `a4082410121d` | identique | healthy |

PostgreSQL B04 conserve exactement son ID complet
`ebe59b76ce97d5618fa9aec2b40c06443e0f88d3cc09a17d17b1492e538d1fb7`,
son image et son démarrage **`2026-10-21T13:33:32.629685165Z`**. Le stockage reste
`tmpfs /var/lib/postgresql`, aucun port PostgreSQL publié et aucun volume.
Les quatre conteneurs 8001/8003 conservent également leurs dates de démarrage et
images exactes. Aucune requête SQL n'a visé leurs bases.

Réseaux B04 conservés : `testing` interne, DB `172.23.0.2`, app `172.23.0.3` ;
`frontend`, app `172.24.0.2` uniquement. HTTP reste publié uniquement sur
`127.0.0.1:8004`. Aucun réseau créé ou supprimé pendant ce déploiement.

## Preuve de conservation des données

La capture SQL avant remplacement a été comparée exactement, après restauration
et démarrage, à une nouvelle lecture dans une transaction non modifiante.
**Résultat : identité complète des objets, états, révisions et relations contrôlés.**

| Objet | Résultat identique avant/après |
|---|---|
| Vente 0001 | `0e5c114c-6f60-4cc7-85d0-05bd3501f718`, ENCAISSEE, révision 5 |
| Vente 0002 | `cb13d88e-bba5-447c-b6ee-f6aa149c40d9`, TRANSMISE, révision 4 |
| Vente 0003 | `3cacdabe-89ae-49e7-805c-85fba54f81c5`, TRANSMISE, révision 4 |
| Session | `89869cab-4520-452e-a7d1-1d54060b31cf`, OUVERTE, révision 2 |
| Brouillon | `474a1999-38b1-418b-96af-9cceed2984f0`, BROUILLON, révision 2 |
| Tickets du groupe | mêmes ventes 0002/0003, révisions 4, dus 33 800 / 67 600 |
| CARTE | même ID `9d7bff79-3741-4408-8dde-7c336cc61db5`, référence `TEST-B04-CARTE-001`, montant 10 000, mêmes vente/session/fournisseur |
| Comptages | 1 reçu individuel, 0 règlement groupé, 0 allocation groupée |
| Alembic | `20261019_06`, aucune migration rejouée |

## Reprise humaine courte

1. Dans le profil navigateur dédié à 8004, noter les lignes locales non
   enregistrées avant **Ctrl+F5** pour charger les nouveaux scripts. Les saisies
   de l'ancien document navigateur ne sont pas des données sauvegardées ; les
   objets PostgreSQL ci-dessus restent conservés. Utiliser le même compte et,
   si nécessaire, le fichier privé `.secrets/b04-connexion.txt` inchangé.
2. Sélectionner la session ouverte existante. Ne pas repayer 0001. Pour vérifier
   l'aperçu simple sans nouveau ticket, ouvrir F10 sur 0002 (33 800), saisir
   40 000 espèces : attendu reçu 40 000, rendu 6 200, net 33 800, reste 0 ;
   **fermer sans valider**. Ne pas cocher la CARTE pour ce seul contrôle espèces.
3. Passer au multiple, reprendre le brouillon
   `474a1999-38b1-418b-96af-9cceed2984f0` ; constater que la consultation/recharge
   est accessible hors chargement. Reprendre espèces 90 500 et CARTE 10 000,
   sélectionner **la confirmation existante** `TEST-B04-CARTE-001`. Aucun
   rapprochement artificiel et aucune seconde confirmation CARTE.
4. Vérifier la rangée compacte et la référence lisible. Une ligne AIRTEL 1 400
   complète l'aperçu : brut 101 900, rendu 500, net 101 400, reste 0. Son
   enregistrement exigera une confirmation AIRTEL acquise humainement, une seule
   fois, dans le cadre de la recette financière autorisée.
5. Tester recharge, conservation des montants et avertissements pour la
   ventilation locale sans perdre le brouillon. Les étapes d'enregistrement,
   de ventilation et de validation restent explicites ; ne pas finaliser avant
   vérification des allocations et autorisation de recette correspondante.

Aucune de ces étapes humaines n'a été effectuée par l'agent pendant le déploiement.
Déploiement terminé ; arrêt et attente de validation humaine.

---

## Historique antérieur au déploiement — à lire comme état passé

Les sections suivantes conservent la préparation et ses diagnostics précédents.
L'état actuel est celui décrit en tête de ce document.

# B04 — Recette isolée préparée après reprise autorisée

## État actuel : application disponible, recette financière non commencée

La reprise explicitement autorisée par le propriétaire a réussi le 21 octobre
2026. **Une seule nouvelle tentative de seed**, code de sortie **0**. Aucune
migration réappliquée, aucun conteneur arrêté ou recréé, aucune donnée supprimée.

- URL : **http://127.0.0.1:8004/** (utiliser un profil navigateur distinct).
- Accès fictifs : **`.secrets/b04-connexion.txt`**, ignoré par Git et protégé par
  ACL pour le compte Windows courant et SYSTEM. Mot de passe jamais affiché.
- Compte : `caisse.b04` ; caisse : `Caisse fictive B04`.
- Organisation : `f897fa1b-aee9-4e4a-8408-6bc7a7206361`.
- Garde groupé inchangé ; marqueurs de recette confinés à app B04. Son activation
  a été vérifiée par les assertions du contrôle initial.

## Correction minimale et vérifications avant reprise

Seul `docker/b04-recette/seed_b04.py` a été corrigé, par ajout d'imports ORM :
`tiers_payants_models`, `regularisation_models`, `proforma_models`,
`import_catalogue_models`, `creance_models`, `facturation_organisme_models`.
Aucune entité, aucun modèle applicatif, aucune migration, aucun runner ou script
de contrôle modifié pendant cette reprise. Le présent document est mis à jour.

Vérification statique : `ast.parse` des trois scripts et `git diff --check`
réussis. Chargement des seuls imports du seed dans le conteneur existant, sans
exécution du seed ni connexion SQL : `configure_mappers()` valide, **130 tables
ORM et 655 clés étrangères résolues**.

Contrôles Docker et PostgreSQL en lecture seule avant réarmement :

```json
{"project":"neosys-pharma-b04-recette","database":"neosys_browser","user":"neosys_test","server_ip":"172.23.0.2","expected_test_db_ip":"172.23.0.2","alembic":"20261019_06","business_tables_checked":127,"business_rows":0,"non_system_roles":0,"failed_marker_verified":true,"success_marker_absent":true}
```

Les 127 tables contrôlées comprennent toutes les tables publiques sauf
`alembic_version`, `permissions`, `roles`, `roles_permissions` (catalogues de
migration). Les rôles non système ont été contrôlés séparément : zéro.
L'adresse serveur réelle a été comparée à l'adresse du `test-db` du réseau B04,
avec contrôle des labels Compose des deux conteneurs. Aucune base conservée
consultée.

## Réarmement et résultat de la nouvelle tentative

Le seul marqueur `/tmp/b04-seed-started` a été vérifié puis **renommé** en
`/tmp/b04-seed-first-failed`, sans suppression et après vérification de l'absence
du marqueur de réussite, de fixture et de fichier de connexion. Le seed corrigé
recrée son marqueur de tentative et produit ensuite son marqueur de réussite.
Le refus d'une autre initialisation reste actif ; aucun autre lancement du seed
n'a été effectué pour le tester.

```powershell
docker compose -p neosys-pharma-b04-recette --env-file .env.docker.example -f compose.b04-recette.yaml exec -T app python /opt/neosys/recette/runner.py run python /opt/neosys/recette/seed_b04.py
```

**Résultat : code 0**, organisation et données synthétiques créées :

| Ticket transmis | Montant FCFA |
|---|---:|
| `0e5c114c-6f60-4cc7-85d0-05bd3501f718` | 7 000 |
| `cb13d88e-bba5-447c-b6ee-f6aa149c40d9` | 33 800 |
| `3cacdabe-89ae-49e7-805c-85fba54f81c5` | 67 600 |

Une organisation, un utilisateur, une caisse, un poste, trois produits et leurs
conditionnements/tarifs fictifs. Stock physique total **30**, stock réservé **3**.
Modes actifs : ESPÈCES, CARTE, MOBILE_MONEY. Fournisseurs explicitement créés et
actifs : **CARTE** et **AIRTEL MONEY**. Aucun client fidélité ou prise en charge
nécessaire à ces scénarios.

## Contrôles initiaux et erreur résiduelle d'affichage

```powershell
docker compose -p neosys-pharma-b04-recette --env-file .env.docker.example -f compose.b04-recette.yaml exec -T app python /opt/neosys/recette/runner.py run python /opt/neosys/recette/check_initial.py
```

Cette commande a passé **toutes ses assertions**, y compris les trois montants
calculés par le service, états transmis, moyens actifs, révision, stocks et garde
groupé actif. Elle a néanmoins terminé avec **code 1** à la dernière instruction
`json.dumps` : `TypeError: Object of type Decimal is not JSON serializable`, pour
`stock_physique`. PostgreSQL renvoie `sum(bigint)` comme Decimal.

Le script de contrôle n'a pas été corrigé, pour respecter le périmètre limité aux
imports du seed. Aucun contrôle de données n'a été supprimé ou assoupli. Une
lecture seule indépendante a confirmé ensuite les mêmes résultats, avec conversion
en entier des deux sommes uniquement pour l'affichage JSON ; code de sortie **0** :

| Contrôle | Résultat |
|---|---:|
| Organisations / utilisateurs / caisses | 1 / 1 / 1 |
| Ventes, toutes transmises | 3 |
| Moyens explicites, tous actifs | 2 |
| Confirmations indépendantes | **0** |
| Encaissements individuels / dossiers groupés | **0 / 0** |
| Sessions de caisse | **0** |
| Stock physique / réservé | **30 / 3** |
| Alembic | **20261019_06** |

**Erreur restante connue** : le rapport JSON de `check_initial.py` ne sérialise
pas ses sommes Decimal. Cela n'affecte pas les données ni l'application ; sa
correction n'est pas comprise dans cette reprise. Ne pas présenter cette commande
comme ayant terminé avec un code 0.

## Démarrage et disponibilité

Après vérification des données, démarrage explicite du serveur :

```powershell
docker compose -p neosys-pharma-b04-recette --env-file .env.docker.example -f compose.b04-recette.yaml exec -d app python /opt/neosys/recette/runner.py run python -m uvicorn neosys_pharma.presentation.app:app --host 0.0.0.0 --port 8000
```

Code 0. Contrôles HTTP sans authentification, sans paiement et sans lecture de
base conservée : `/` **200**, page de connexion ; `/health` **ok** ;
`/static/encaissement_groupe.js` **200**, contenu B04 présent. Le premier accès
HTTP depuis le shell sandboxé a été bloqué par les permissions du socket avant
réponse ; le même contrôle en lecture seule hors sandbox a réussi.

Export des accès vers un fichier neuf, préalablement protégé par ACL, sans
écrasement ni affichage de contenu :

```powershell
docker compose -p neosys-pharma-b04-recette --env-file .env.docker.example -f compose.b04-recette.yaml exec -T app python /opt/neosys/recette/runner.py credentials > .secrets/b04-connexion.txt
```

Code 0, fichier non vide et `git check-ignore` réussi. Les accès existent aussi
dans `/tmp/b04-connexion.txt` (mode 0600) du conteneur app. Ne pas les joindre à
Git, au rapport ou au chat.

## Isolation et conservation

Identifiants B04 inchangés : app `cd516948943c`, PostgreSQL `ebe59b76ce97`, démarré
le `2026-10-21T13:33:32.629685165Z` et non redémarré. PostgreSQL reste healthy,
uniquement sur `neosys-pharma-b04-recette_testing`, tmpfs `/var/lib/postgresql`,
aucun port publié et aucun volume. Relais inchangé `127.0.0.1:55432` dans app vers
le seul `test-db` B04. HTTP publié uniquement sur `127.0.0.1:8004`.

Les projets 8001 et 8003 restent actifs, avec leurs mêmes conteneurs :
`1d05b1290dae` / `a334ec625935` et `1ae8ef53bf39` / `a4082410121d`.
Aucune commande de cycle de vie, migration, seed ou SQL ne les a ciblés. Les
sources métier figées dans l'image B04 n'ont pas été modifiées. Aucun nettoyage,
aucun arrêt/recréation, aucun commit, push ou merge. Branche et HEAD inchangés.

## Recette humaine à venir, après validation

1. Ouvrir `http://localhost:8004/` dans un profil navigateur distinct ; utiliser
   le fichier privé d'accès. Ouvrir humainement une session sur la caisse fictive.
2. Simple : ticket **7 000**, espèces **10 000** → rendu **3 000**, net **7 000**,
   reste **0**. Contrôler les informations affichées avant toute validation.
3. Multiple : tickets **33 800 + 67 600**. Acquérir humainement les confirmations
   CARTE **10 000** et AIRTEL MONEY **1 400**, avec fournisseurs/preuves explicites.
   Espèces **90 500** → brut **101 900**, rendu **500**, net **101 400**, reste **0**.
   Enregistrer et contrôler les allocations par vente selon le parcours existant.
4. Priorité visuelle : simplicité du paiement multiple, tickets à gauche,
   règlements à droite, ajout/suppression et totaux immédiats. Ne pas créer une
   seconde confirmation pour un même paiement indépendant déjà acquis.

**Aucune authentification ni recette financière effectuée automatiquement.**
Préparation terminée ; attente de validation avant la recette humaine.

---

## Historique : première tentative, avant l'autorisation de reprise

Les sections suivantes décrivent uniquement l'état antérieur et les commandes
de la première préparation. Elles ne remplacent pas l'état actuel ci-dessus.

# B04 — Préparation de la recette PostgreSQL isolée

## État : arrêt après échec du seed

Autorisation du propriétaire : création du projet B04, contrôle de destination,
migration d'une base neuve, une tentative de seed synthétique et disponibilité
initiale. Consigne impérative : arrêt en cas d'échec d'un contrôle, sans solution
de contournement non autorisée. Aucun nouvel essai ni démarrage HTTP après l'échec.

Branche `dev/codex-docker`, HEAD `4f91780b4a557640b0b42769b0a25f9e6da708a4`
inchangés. Les modifications métier B04 antérieures restent présentes, sans autre
modification de `src`. Aucun commit, push, merge, paiement ou nettoyage.

## Ressources réellement créées

| Ressource | Valeur / état |
|---|---|
| Projet | `neosys-pharma-b04-recette` |
| Image figée | `neosys-pharma-b04-recette:local`, digest `sha256:02efc3eb235f925dc530c21a950f45ba5aa2dcf46a3b6d206509df6890d6e1c0` |
| App | `neosys-pharma-b04-recette-app-1`, ID `cd516948943c`, actif, relais seulement |
| Base | `neosys-pharma-b04-recette-test-db-1`, ID `ebe59b76ce97`, healthy |
| HTTP réservé | `127.0.0.1:8004 -> app:8000`, aucun serveur Uvicorn démarré |
| Base PostgreSQL | `neosys_browser`, compte `neosys_test`, IP `172.23.0.2`, port interne `5432` |
| Stockage base | tmpfs `/var/lib/postgresql`, aucun volume et aucun port PostgreSQL publié |
| Réseau interne | `neosys-pharma-b04-recette_testing`, `internal=true` ; base `172.23.0.2`, app `172.23.0.3` |
| Réseau HTTP | `neosys-pharma-b04-recette_frontend`, app `172.24.0.2` uniquement |
| Relais | écoute `127.0.0.1:55432` dans app, destination DNS B04 `test-db`, IP figée au démarrage, port `5432` |
| Secret dédié | `.secrets/b04-test-db-password.txt`, créé neuf, ignoré par Git, ACL compte Windows courant et SYSTEM, valeur jamais affichée |
| Fichiers techniques | `compose.b04-recette.yaml`, `docker/b04-recette/runner.py`, `seed_b04.py`, `check_initial.py` |

Les sources applicatives, tests et migrations sont dans l'image dédiée ; aucun
montage de `src`, de base Windows ou du checkout entier. Seuls les scripts de
recette et le secret dédié sont montés en lecture seule dans app. Le runner
refuse les variables héritées de connexion, impose la cible et les trois
marqueurs B04. Le garde métier groupé est inchangé. Ces marqueurs ne sont fournis
qu'au conteneur app B04. Aucun service conservé n'a été reconfiguré/redémarré.

## Commandes et résultats

Depuis `D:\Projets_Python\NeoSys_Pharma_Dev`, après vérification Git et inventaire
Docker. Syntaxe des trois scripts vérifiée par `ast.parse` ; `git diff --check`
réussi. Secret généré avec `RandomNumberGenerator`, sans lecture/affichage de sa
valeur, après refus d'écrasement et contrôle `git check-ignore`.

```powershell
docker compose -p neosys-pharma-b04-recette --env-file .env.docker.example -f compose.b04-recette.yaml config --quiet
docker build --target tests -t neosys-pharma-b04-recette:local .
docker compose -p neosys-pharma-b04-recette --env-file .env.docker.example -f compose.b04-recette.yaml up -d --no-build --pull never test-db app
```

Résultat : codes de sortie 0 ; image, deux réseaux et deux conteneurs créés.
PostgreSQL healthy. App ne démarre que son relais ; ni migration ni seed automatique.
Inspection ciblée des montages, réseaux, ports et tmpfs par `docker inspect` et
`docker network inspect`, sans affichage de l'environnement ou de secrets.

```powershell
docker compose -p neosys-pharma-b04-recette --env-file .env.docker.example -f compose.b04-recette.yaml exec -T app python /opt/neosys/recette/runner.py check-target --require-empty
```

Code 0 ; preuve obtenue **avant migration**, puis vérifiée de nouveau par le runner
immédiatement avant Alembic :

```json
{"database":"neosys_browser","user":"neosys_test","server_ip":"172.23.0.2","server_port":5432,"expected_test_db_ip":"172.23.0.2","public_relations":0,"relay":"127.0.0.1:55432"}
```

La vacuité vérifie tables, tables partitionnées, vues, vues matérialisées,
séquences et tables étrangères du schéma public. Le résultat est conservé dans
`/tmp/b04-pre-migration.json` du conteneur app, sans secret.

```powershell
docker compose -p neosys-pharma-b04-recette --env-file .env.docker.example -f compose.b04-recette.yaml exec -T app python /opt/neosys/recette/runner.py run alembic upgrade head
```

Code 0. Migration complète PostgreSQL jusqu'à **`20261019_06`**. Aucun changement
de fichier de migration ; seules les migrations existantes ont été appliquées.

```powershell
docker compose -p neosys-pharma-b04-recette --env-file .env.docker.example -f compose.b04-recette.yaml exec -T app python /opt/neosys/recette/runner.py run python /opt/neosys/recette/seed_b04.py
```

**Code 1, une seule tentative.** Échec lors du contrôle de base vide effectué par
le bootstrap existant, avant sa première écriture métier :

```text
sqlalchemy.exc.NoReferencedTableError:
Foreign key associated with column 'tiers_payant_calculs_etapes.convention_id'
could not find table 'tiers_payant_conventions'
```

Diagnostic : le seed n'a pas chargé tous les modules ORM requis. La table existe
sur PostgreSQL après migrations, mais le modèle de `tiers_payants_models.py`
n'est pas enregistré dans les métadonnées Python du processus de seed. Aucun
changement métier ou migration supplémentaire n'est indiqué par ce diagnostic.
Le marqueur `/tmp/b04-seed-started` existe ; aucun marqueur de fin, aucune fixture
ni fichier d'accès humain n'a été produit. Le refus de seconde initialisation
reste en place. Il n'a pas été testé par un second lancement réel.

## Contrôle en lecture seule après arrêt

Une connexion B04 via le relais, transaction `read_only=True`, a confirmé la même
cible, la révision `20261019_06` et les nombres suivants :

| Table | Nombre |
|---|---:|
| organisations | 0 |
| utilisateurs | 0 |
| ventes | 0 |
| stock_emplacements | 0 |
| caisse_moyens_paiement | 0 |
| caisse_confirmations | 0 |
| caisse_encaissements | 0 |
| caisse_sessions | 0 |

**Tickets préparés : 0 sur 3 attendus.** Les catalogues système issus des
migrations sont conservés. Aucun seed relancé, aucun pytest, aucune session de
caisse ouverte, aucune confirmation externe et aucun encaissement.

`docker ps -a` confirme les mêmes quatre identifiants de conteneurs conservés
qu'avant intervention : 8001 app `1d05b1290dae`, db `a334ec625935` ; 8003 app
`1ae8ef53bf39`, base `a4082410121d`. Ils restent actifs, les bases et app 8001
healthy. Aucune requête SQL ou de cycle de vie ne les a ciblés. Aucun contrôle
HTTP n'a été lancé sur ces environnements pour éviter une consultation de leur
base. 8004 est réservé, mais son serveur HTTP reste non démarré.

## Reprise à autoriser

Corriger uniquement les imports du seed, puis définir explicitement une reprise
autorisée du marqueur d'échec après nouveau contrôle de destination et absence
de données métier. Ne pas supprimer le marqueur ni relancer automatiquement.
Aucune correction ou reprise n'a été effectuée dans cette exécution.

Le lancement de `check_initial.py`, le démarrage Uvicorn, les contrôles HTTP,
l'export privé des identifiants fictifs et la recette financière ne sont pas
exécutés. `.secrets/b04-connexion.txt` n'existe pas : aucun compte n'a été créé.
Le seul secret existant est celui du PostgreSQL B04 ; ne pas le partager.

Après préparation réussie et autorisée, recette humaine prévue dans un profil
navigateur distinct sur `http://localhost:8004/` :

1. Ouvrir une session sur la caisse fictive B04. Ticket simple 7 000, espèces
   10 000 : rendu 3 000, net 7 000, reste 0 ; vérifier reçu/historique.
2. Sélectionner les tickets 33 800 et 67 600. Acquérir humainement CARTE 10 000 et
   AIRTEL MONEY 1 400, avec fournisseurs et preuves explicites. Ajouter espèces
   90 500 : brut 101 900, rendu 500, net 101 400, reste 0. Enregistrer les
   règlements et allocations selon les confirmations existantes avant validation.
3. Contrôler prioritairement la simplicité du multiple : tickets à gauche,
   règlements à droite, ajout/suppression et totaux immédiats. Aucun parcours
   financier ne doit être lancé pendant la préparation.

Aucun arrêt, suppression, nettoyage ou nouvelle tentative effectué. Les données
B04 de migration restent en tmpfs ; ne pas arrêter le conteneur PostgreSQL avant
la décision de reprise. Arrêt de la procédure et attente du propriétaire.
