# Corrections ciblées — fidélité et historique client

Livraison locale du 20 octobre 2026. **Préparée pour revue ; aucune intégration en recette, aucune clôture humaine des anomalies.**

## Référence et protections

- Branche : `fix/p4-fidelite-historique`.
- Parent exact : `9c273a94eeaacfac9f1425ca7411a6ea85f3b4c1` (P5-C.2).
- Référence justifiée : copie propre examinée dans le diagnostic accepté `DIAGNOSTIC_P4_FID_004_CLI_005(1).md`. Son contenu a été relu avant le développement.
- Copie Work : `/workspace/scratch/8ece5b1768c1/neosys-fid-diagnostic` ; aucun accès au worktree Windows ni à `neosys_p4p5_recette_integree`.
- Les commits de paiement `2b29700a` et d'affichage/import `773b106a`, disponibles dans le bundle antérieur, ne sont ni parents de cette branche ni intégrés. Leur comparaison préalable n'a pas révélé de changement des règles de fidélité ou de l'historique étudiées. Ils nécessiteront une intégration distincte, contrôlée.
- Aucun push, PR, déploiement, migration ou modification d'une base conservée. Aucun changement de permission attribuée. Le drapeau groupé et son garde CI restent inchangés, désactivés par défaut.
- Le SHA final, l'arbre et le SHA-256 du patch figurent dans `IDENTITE_LIVRAISON.txt` livré à côté du patch. Le présent document fait partie du commit.

## NC-P4-FID-004 — information, sans modification des droits à points

Le diagnostic ne démontrait pas d'erreur de calcul : une catégorie COSMÉTIQUES ne remplace pas la nature `COSMETIQUE`. La nature effective au paiement humain 0004 n'a pas été lue ici. Aucun crédit, reclassement de produit ou recalcul historique n'est effectué.

`CaisseService.assiette_acquisition` centralise la sélection existante des lignes et fournit les explications utilisées par le nouveau GET de lecture. `gagner` réutilise cette sélection avec le même calcul, le même arrondi inférieur, le même mécanisme de dette et la même structure de snapshot/journal qu'avant. Aucun calcul de points en JavaScript.

**Route ajoutée :** `GET /api/caisses/organisations/{organisation_id}/ventes/{vente_id}/fidelite`.

| Contexte | Source / informations | Garantie |
|---|---|---|
| Avant paiement | Finance de vente et barème daté actuels ; lignes éligibles/exclues, codes et motifs ; assiette client ; `points_acquis=null` | Lecture seule, aucune promesse d'attribution ni simulation de réussite financière |
| Avec organisme | Part client des lignes du snapshot de prise en charge confirmé et revalidé | Les parts organismes sont exclues ; une information tiers invalide est refusée |
| Après paiement | Snapshot de l'encaissement, points réellement acquis, dette compensée, motif de zéro vérifiable | Aucune relecture du catalogue pour recalculer le passé ; aucun crédit ni enrichissement du reçu |

Codes avant paiement : `LIGNE_INACTIVE`, `NATURE_ABSENTE`, `NATURE_NON_ADMISE`, `BAREME_ABSENT`, `CATEGORIE_NON_ADMISE`, `MONTANT_CLIENT_NUL`, `ELIGIBLE`.

Codes après paiement : `SANS_FIDELITE`, `BAREME_ABSENT`, `ASSIETTE_NULLE`, `SEUIL_NON_ATTEINT`, `ACQUISITION_CONFIRMEE`.

**Limite historique assumée :** les anciens snapshots ne conservent pas le motif détaillé de chaque exclusion. Si l'assiette figée vaut zéro, le serveur l'explique et signale que le motif par produit n'est pas conservé. Il ne présente pas la nature actuelle comme preuve de la nature passée. Les structures de reçu et de gain n'ont pas été enrichies pour masquer cette limite.

La route exige `caisse.consulter` puis `fidelite.consulter` sur l'emplacement de la vente, en plus du contexte organisation/site P1. Aucun compte n'est affecté par cette consultation. La lecture de prise en charge peut désactiver le verrou `FOR UPDATE` pour ce précontrôle ; les appels financiers existants gardent ce verrou par défaut. Le précontrôle ne remplace jamais les vérifications transactionnelles de finalisation.

À la caisse :

- Le titulaire sélectionné reste distinct de l'éligibilité des produits ; la confirmation l'indique explicitement.
- Les motifs par produit proviennent du serveur, affichés dans la vente et dans la confirmation si un titulaire est retenu.
- Après paiement, les points affichés proviennent du résultat/snapshot serveur. Une lecture complémentaire refusée ou indisponible ne transforme pas un paiement confirmé en échec financier.
- La lecture est contrôlée par vente/révision/contexte ; une préparation de paiement devenue obsolète est refusée. Un second clic pendant cette lecture n'ouvre pas une autre confirmation.
- Ni la carte ni un bénéficiaire tiers ne définissent implicitement `ventes.client_id`. L'utilisation des points reste fiscalement bloquée.

## NC-P4-CLI-005 — historique de consultation

Le prédicat historique est désormais :

`vente.client_id = fiche consultée OU encaissement.compte_id → compte.client_id → titulaire.profil_client_id = fiche consultée`.

Le second chemin est limité aux emplacements cumulant `vente.consulter` et `fidelite.consulter`. `client.consulter` reste exigé par la route ; `caisse.consulter` reste exigé séparément pour exposer les références et ouvrir les reçus. Sans droit fidélité, les ventes du premier chemin restent consultables selon leurs droits existants.

La requête principale reste une requête de ventes, filtrée par organisation/site/emplacements ; `EXISTS` évite les multiplications par jointure. Décompte, tri stable et pagination SQL sont conservés. L'origine autorisée est calculée sur les seuls éléments de la page : `PREPARATION`, `FIDELITE_CAISSE`, ou les deux, sur une seule ligne. Aucun identifiant de compte n'est ajouté à la réponse pour exposer ce chemin.

La colonne « Rattachement » de l'écran Clients rend ces origines explicites. Aucun lien n'est reconstruit depuis le nom, le téléphone ou la carte courante. Zéro point n'exclut pas une vente de l'historique fidélité. Aucune mise à jour de `ventes.client_id`, des comptes ou des encaissements n'est réalisée.

## Fichiers de la livraison

| Fichier | Modification |
|---|---|
| `src/neosys_pharma/application/caisse_service.py` | Sélection commune d'assiette, lecture explicative, verrou conservé par défaut pour les opérations financières |
| `src/neosys_pharma/presentation/caisse_api.py` | GET explicatif protégé, sans mutation |
| `src/neosys_pharma/presentation/client_api.py` | Historique élargi par EXISTS, droits cumulés, origines et pagination |
| `src/neosys_pharma/presentation/web/caisse.js` | Messages serveur, distinction titulaire/produits/points, gestion des réponses obsolètes et lecture avant confirmation |
| `src/neosys_pharma/presentation/web/clients.js` | Origine de rattachement dans l'historique |
| `src/neosys_pharma/presentation/web/index.html` | Conteneur accessible d'information fidélité |
| `tests/test_fidelite_historique_corrections.py` | 19 nouveaux cas ciblés, dont 3 unitaires et 16 HTTP/FastAPI |
| `tests/fidelite_historique_ui.cjs` | 24 assertions DOM ; même scénario préparé avec `--chromium`, transport/modale simulés |
| `tests/finitions_caisse_ui.cjs` | Attendre `cashPay` devenu asynchrone, dans son contexte d'encaissement ; assertions conservées |
| `docs/CORRECTIONS_P4_FID_004_CLI_005.md` | Rapport, procédure et protocole de recette séparé |
| `docs/REGISTRE_NON_CONFORMITES_P5.md` | Ajout des statuts des deux anomalies et des limites de validation |

**Migration : aucune.** Aucun modèle, PDF, calcul de couverture, règle de remboursement ou montant persistant modifié.

## Résultats réellement obtenus

Environnement isolé CPython **3.14.8**, pytest 9.1.1, SQLAlchemy 2.1.5, FastAPI 0.151.0, ReportLab 4.5.1. Dépendances du projet installées sans modifier `pyproject.toml`. Node/jsdom 30.1.3 pour le DOM.

| Groupe | Exécuté / résultat | Portée |
|---|---|---|
| Nouveaux tests unitaires | **3 réussis** | Montants clients 106 500→106, 999→0, 1 000→1 ; pas de points sur la part organisme |
| Nouveaux tests HTTP | **16 réussis** | FastAPI et ORM réels, SQLite mémoire exclusivement ; aucune réponse métier simulée dans ces tests |
| Régressions P4/P5 sélectionnées | **25 réussies, 1 échouée** | Deux commandes, voir ci-dessous ; l'échec préexiste sur la base intacte |
| Nouveau DOM | **24 assertions réussies** | HTML/JS réels, serveur et hôte de modale simulés |
| DOM existants | **17 + 19 + 9 assertions réussies** | Formulaires caisse/cartes, groupe avec organismes, fournisseurs de paiement ; HTTP simulé |
| Chromium | **Non exécuté** | Installation Playwright tentée ; téléchargement Chromium invalide (« End of central directory record signature not found »), aucun binaire disponible |
| PostgreSQL natif | **Non exécuté** | Pas de Docker/Podman, psql ou serveur PostgreSQL local disponible ; aucun schéma ni contrainte changé dans ce lot, aucune connexion conservée essayée |
| Windows / recette humaine | **Non exécutés** | Environnement protégé non accessible ; autorisation d'intégration distincte nécessaire |

Bilan des cas Python distincts de la sélection : **44 réussis et 1 échec préexistant** ; aucun test ignoré parmi les cas sélectionnés. Ces résultats ne sont pas une validation de concurrence PostgreSQL. Le test échoué a été exécuté une seconde fois, seul, sur une copie intacte de la base pour prouver son antériorité ; cette reproduction ne constitue pas un nouveau cas distinct.

Les 16 nouveaux cas HTTP couvrent notamment : nature COSMETIQUE et catégorie admise ; nature absente/médicament/code accentué non admis malgré compte sélectionné ; catégorie hors barème ; absence de barème ; seuil inférieur à un point ; historique carte seule/préparation/deux liens sans doublon, pagination de taille 1 et totaux ; autre client ; retrait séparé des permissions ; refus organisation/site/emplacement/401 ; résultat sans compte ; snapshot non recalculé après changement de catalogue ; part client P5 confirmée.

Les états financiers (ventes, comptes, encaissements/PDF, journal fidélité, règlements, mouvements de caisse/stock, réservations, balances stock, calculs/répartitions/réalisations P5) sont comparés avant/après les lectures dans les nouveaux tests concernés. Un ancien reçu à zéro garde son PDF et son snapshot après modification du catalogue fictif. Aucun test n'a utilisé 0004 ou le lecteur réel.

### Échec existant, non corrigé hors périmètre

`tests/test_caisse.py::test_finalisation_groupe_atomique_reçus_mouvements_fidelite_et_rejeu`, ligne 907 : comparaison stricte d'un dictionnaire d'audit de remboursement substitué. La réponse possède quatre champs de fournisseur déjà présents dans la base : `moyen_id`, `moyen_libelle`, `moyen_origine_id`, `moyen_origine_libelle`, absents de l'attendu.

Même erreur reproduite au parent exact `9c273a94` intact, avec le même environnement. Aucun changement apporté à cette assertion, au remboursement ou aux champs. Il s'agit d'une incompatibilité observée de l'attendu de test avec le contrat d'audit enrichi, **pas d'une preuve d'erreur de montant**. Une correction éventuelle de cet attendu et sa revue financière restent distinctes. Ne pas annoncer la sélection de régressions entièrement verte.

Les premiers essais des nouveaux tests ont aussi corrigé deux défauts de fixture : réattribution de permissions déjà présentes et comparaison d'une date POST avec offset à sa relecture SQLite sans offset. La comparaison finale exige l'identité du snapshot et compare les lectures persistées intégrales ; aucune assertion financière n'a été retirée pour contourner un défaut applicatif.

Un avertissement de dépréciation Starlette/TestClient sur httpx reste présent ; il ne fait échouer aucun cas.

## Commandes reproductibles et preuves

Les logs de cette livraison sont dans l'archive, dossier `preuves/`. Les tests HTTP nouveaux forcent explicitement l'absence d'URL de base externe et utilisent la fixture SQLite mémoire. Les tests historiques utilisent la fixture existante : lancer ceux-ci dans un terminal de tests **sans** `TEST_DATABASE_URL`, `DATABASE_URL` ou `TEST_MIGRATION_DATABASE_URL` héritées. Ne jamais les pointer vers une base conservée.

Installation dans une nouvelle copie et un venv de test : `python -m pip install -e ".[dev]"` (Python 3.14).

Nouveaux cas :

```text
python -m pytest -q tests/test_fidelite_historique_corrections.py
```

Sélection de régression exécutée :

```text
python -m pytest -q tests/test_caisse.py::test_encaissement_mixte_atomique_recu_et_rejeu tests/test_caisse.py::test_echec_sans_effet_financier_stock_ou_points tests/test_caisse.py::test_historique_client_affiche_les_ventes_liees_avec_pagination tests/test_caisse.py::test_acquisition_sous_categories_et_aucun_taux_implicite tests/test_caisse.py::test_acquisition_apres_remises_et_immutabilite_vente_payee tests/test_caisse.py::test_eligibilite_categorie_principale_et_descendants tests/test_caisse.py::test_finalisation_groupe_atomique_reçus_mouvements_fidelite_et_rejeu tests/test_caisse.py::test_finalisation_groupe_rollback_apres_creation_des_reçus tests/test_caisse.py::test_activation_groupe_reservee_a_la_recette_jetable tests/test_p5b_3_encaissement_prise_en_charge.py tests/test_regularisation.py::test_retours_partiels_cumulatifs_quarantaine_remboursement_fidelite tests/test_regularisation.py::test_dette_points_et_quarantaine_non_reservable tests/test_regularisation.py::test_x_z_annulation_sequences_et_pdf_historiques tests/test_clients_p4b.py::test_preparation_peut_referencer_une_fiche_client_et_historique_scoped tests/test_clients_p4b.py::test_permissions_client_non_attribuees_par_defaut
python -m pytest -q tests/test_caisse.py::test_401_403_csrf_lecture_seule_isolation_et_rejeu
```

Pour les tests DOM, installer `jsdom` et facultativement `playwright` dans un dossier d'outillage séparé (hors dépôt), et désigner son `node_modules` par `NODE_PATH` :

```text
node tests/fidelite_historique_ui.cjs
node tests/finitions_caisse_ui.cjs
node tests/groupe_organismes_ui.cjs
node tests/moyens_paiement_ui.cjs
```

Préparé mais **non exécuté** : après installation du module Node Playwright et de Chromium dans cet outillage, `node tests/fidelite_historique_ui.cjs --chromium`. Ce scénario reste un test de navigateur avec HTTP/modale simulés, pas un E2E financier réel. Son origine localhost est interceptée, il n'appelle aucune recette.

## Intégration ultérieure — aucune action réalisée

1. Conserver intact `D:\Projets_Python\NeoSys_P4_P5_RECETTE`. Examiner son HEAD et ses modifications avant toute future intégration autorisée ; le présent rapport ne prétend pas connaître son état.
2. Dans une **autre** copie, vérifier que `9c273a94` est présent. Créer une branche dédiée depuis cette base. Le bundle livré conserve la branche de correction sans publication.
3. Vérifier le SHA-256 du patch et lancer `git apply --check p4-fidelite-historique.patch`. Pour conserver le commit, utiliser `git am p4-fidelite-historique.patch` dans cette copie indépendante après vérification. Ne pas appliquer à la fois le patch et le commit du bundle.
4. Si les correctifs paiement/import sont déjà intégrés à une autre branche, comparer les diff des fichiers communs, particulièrement `caisse.js` et `clients.js`. Préparer une intégration à trois voies contrôlée dans une copie jetable ; ne pas écraser un fichier entier. Ce scénario n'a pas été appliqué dans cette mission.
5. Exécuter les contrôles ciblés puis la campagne native/navigateur manquante sur un environnement autorisé. Aucune migration n'est requise par ce correctif.
6. Toute installation en recette reste suspendue à l'autorisation du responsable. Ne rejouer aucun paiement ancien.

## Protocole humain limité aux deux anomalies

À prévoir après intégration autorisée, avec nouvelles données fictives pour les paiements :

| Cas | Actions | Attendu |
|---|---|---|
| F1 — cosmétique admissible | Nature COSMETIQUE, catégorie admise, barème 1/1 000 applicable, compte sans dette ; vente SANS_TIERS fictive à 106 500, sans client préparé ; sélectionner sa carte puis encaisser | Titulaire et éligibilité distincts, aucun point acquis annoncé avant paiement ; après confirmation 106 points, compte correct, mouvement unique |
| F2 — non éligible | Nouvelle vente fictive de nature médicament/dispositif ou absente ; choisir une carte | Motif serveur explicite, acquisition zéro sans reclassement automatique ; montant et reçu exacts |
| F3 — ancien 0004 | Consultation seulement du reçu et du diagnostic | Résultat historique inchangé ; si assiette nulle, absence de motif détaillé ancien signalée, aucun recalcul |
| H1 — carte à la caisse | Ouvrir l'historique du titulaire du nouveau cas F1/F2 ; puis 0004 si son compte/profil est réellement enregistré | Vente visible une seule fois, origine fidélité à la caisse, client de préparation toujours absent |
| H2 — préparation + carte | Nouvelle vente avec fiche préparée et même compte à la caisse | Une seule ligne, les deux origines, pagination et total corrects ; ancien 0002 toujours consultable |
| H3 — confidentialité | Autre fiche/compte, opérateur sans droit fidélité, sans droit vente ou sans droit caisse, autre périmètre | Aucun rattachement fidélité non autorisé ; reçu uniquement sous caisse.consulter ; aucune attribution ni modification provoquée par l'historique |

## Verdict et risques résiduels

**Corrections locales livrées pour revue, non intégrées et non déclarées définitivement corrigées.** Les tests ciblés passent. La validation générale reste partielle : un échec ancien est conservé, PostgreSQL natif/Chromium et la validation humaine ne sont pas exécutés.

Risques à contrôler avant intégration : divergences du worktree de recette ; fusion des fichiers UI avec les correctifs antérieurs ; rattachement compte→titulaire→fiche réellement présent sur 0004 ; permissions effectives et volume des historiques ; comportement réel du navigateur. Aucun motif absent d'un ancien snapshot n'est inventé, aucune donnée financière n'est réparée rétroactivement. Les incidents PharmaGabon, plafonds et autres réserves P4/P5 restent ouverts. Arrêt après livraison, sans intégration.
