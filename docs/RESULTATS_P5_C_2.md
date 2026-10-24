# Résultats P5-C.2 — 19 octobre 2026


Les noms de journaux ci-dessous identifient des preuves historiques conservées séparément et exclues de la publication P4. Leur mention ne garantit pas leur disponibilité publique et ne vaut pas validation complète de P5.
**Verdict : livraison partielle ; préparation de recette disponible, facturation de production non prête.** Aucune publication GitHub, base conservée, migration Windows ou activation du groupe effectuée. Aucune recette humaine intermédiaire demandée.

## Base vérifiée

Commit `b8ddf845695f1e82a8d1cbcf0b06e42824bf2133`, arbre `1a64bbcff9cde0f99df6eeda7a53d0f1ab26bd37`. Ancêtre `ba570569bb7063bf587ffac45c3eceff58dea93b` présent. Bundle Git complet vérifié ; patch P5-C.1 déjà intégré non réappliqué. ZIP fourni SHA-256 `7ef0b92549ecaf044c3adf73ac509d6b59d35f46b3ffc0ac1f43798f852da6bb` ; patch C1 `5049566e2a59ec962af4c91a71de51e02693d67199556e2beeea8d4818003ad8`.

## Contrôles exécutés

Python 3.14.8, dépendances déjà disponibles ; données fictives et bases SQLite temporaires exclusivement. Les résultats de campagnes successives ne s'additionnent pas en un nombre de tests distincts.

| Campagne / preuve | Résultat réel | Portée |
|---|---|---|
| `python-final.log` | 24 réussis, 9 ignorés, 1 avertissement, 75,47 s | C2 documents/migration, C1 créances/migration, P5-B.3 et groupe avec organismes ; campagne ciblée, pas suite complète |
| `migration-final.log` | 2 réussis, 1 ignoré, 5,51 s | Sommes 64 bits + migration C2 avec vraie créance C1 fictive conservée ; natif ignoré |
| `tracabilite.log` | 2 réussis, 11,03 s | Liens créance/documents/regroupements et recherche organisme nom/code/périodes |
| `nominal-final.log` | 1 réussi, 9,26 s | Bordereau/facture/PDF/récap/lot après le passage des totaux à BIGINT ; écritures P4 inchangées |
| `somme-final.log` | 1 réussi, 1,44 s | Dernier contrôle de la somme après typage/mise en forme |
| `statique.txt` | Réussi | Syntaxe de 14 fichiers Python, 2 JavaScript, YAML, 15 chemins OpenAPI et diff Git |
| `politique-ci.log` | 48 tests unittest réussis | Politique et configuration CI locale ; aucun run Actions |
| `dom-final.log` | 27 assertions réussies | UI réelle, HTTP explicitement simulé |
| `dom.log` | Créances 23 ; Conventions 38 assertions réussies | Non-régression DOM, HTTP simulé |
| `chromium.log` | Échec de lancement : binaire Chromium absent | Aucun parcours navigateur validé |

La campagne 24/9 précède le dernier test unitaire 64 bits ; ce test et la migration ont donc été exécutés séparément, puis le parcours nominal après cette modification. Les preuves ne représentent pas une validation exhaustive de P4/P5. Avertissement connu Starlette/httpx ; aucune assertion désactivée.

### Scénarios locaux vérifiés

- Deux créances réelles de deux ventes, même organisme/convention ; bordereau puis facture liée ; total exact, références uniques, PDF répété identique, historique et états FACTURE.
- Incomplet, source simulation, organisme différent, révision périmée, retour, dossier changé après validation : refus serveur ; abandon/retrait libèrent les engagements avant émission.
- Authentification réelle dans TestClient, CSRF, refus autre organisation/site/emplacement, révocation d'une permission y compris lors d'un rejeu.
- Rejeu identique sans double document, référence déjà utilisée refusée ; échec provoqué après insertion documentaire et état administratif : rollback sans pièce définitive.
- Triggers d'immutabilité SQLite : modifications du PDF/document/lignes/versions interdites ; suppression d'engagement d'un document émis interdite.
- Récapitulatif/lot sans double comptage ; retour après facture bloque les deux niveaux et laisse le PDF historique identique.
- Migration 05→06 avec créance C1 réellement constituée via l'API sur schéma 05 : hash/part financière conservés, cycle vide 06→05→head, `alembic check`, puis downgrade refusé après création d'une préparation.
- Somme 3 000 000 000 XAF exacte ; booléens, fractions, négatifs et dépassement 64 bits refusés.
- Les compteurs d'encaissements, mouvements de caisse, stock et fidélité ne changent pas lors des opérations documentaires.

L'émission testée sur SQLite utilise une substitution explicite du garde d'activation dans le test. Les routes, transactions, CSRF, contrôles administratifs et PDF sont réels ; cette substitution ne prouve pas la sûreté PostgreSQL ni une activation réelle autorisée.

## Anomalies reproduites et corrections

| Anomalie | Cause et correction | Preuve |
|---|---|---|
| Récapitulatif non sérialisable | UUID provenant d'une extraction brute des colonnes ; encodage explicite `jsonable_encoder` | Parcours nominal désormais réussi |
| Retour après facture accepté dans un récapitulatif (201 au lieu de 409) | Le garde pré-émission ne couvrait pas les regroupements ultérieurs ; contrôle des sources et retours ajouté pour recap et lot | Test rouge conservé en extrait, puis 2 cas verts ; campagne finale incluse |
| Total documentaire potentiellement > entier 32 bits | Agrégation de plusieurs créances ; BIGINT et somme exacte bornée | Test 3 milliards + migration/check + nominal |
| Fixture migration créait deux fois le catalogue de sécurité | Catalogue déjà installé par Alembic ; initialisation redondante supprimée uniquement dans le test | Cycle migration réussit, permissions métier inchangées |

## Contrôles non exécutés

Les 9 ignorés de la campagne ciblée sont : 2 courses C2, 1 migration C2 native, 2 courses C1, 1 migration C1 native et 3 courses groupe P4/P5. Aucun serveur/binaire PostgreSQL, Docker ou Podman exploitable retrouvé dans cet environnement. Aucune base native n'a été créée ni migrée.

Les deux courses C2 préparées utilisent des agents habilités différents, des transactions indépendantes, PID distincts, observation effective de `pg_blocking_pids` et timeouts bornés. Elles doivent encore s'exécuter sur PostgreSQL 17/18. Contraintes, triggers, conservation historique et rollback natifs restent non validés.

Chromium : Playwright présent, binaire `chromium_headless_shell-1234` absent. Tentative de lancement échouée ; le test `--chromium` est prêt avec HTTP simulé, pas un E2E financier. Le parcours C2 réel navigateur/FastAPI/PostgreSQL reste à réaliser en environnement jetable autorisé, puis en campagne humaine consolidée.

## Limites bloquant la clôture

- Numérotation définitive, conformité fiscale et mentions obligatoires non spécifiées : aucune émission de production possible ; références de recette seulement.
- PostgreSQL natif, courses et navigateur réels non validés ; pas de certification des garanties concurrentes.
- Compensations, avoirs, rejets/représentations, règlements et rapprochements organismes non développés ici ; créances affectées par retour bloquées.
- Une préparation est limitée à un site/organisme/version de convention, 100 créances ; récap/lot également bornés à 100 membres par niveau. Regroupements multiconventions/intersites à arbitrer.
- Période UTC de réalisation provisoire ; aucune politique contractuelle de regroupement inventée.
- Incident réel PharmaGabon et plafonds consommables ouverts, inchangés.

Les fichiers exacts sont listés dans `FICHIERS_P5_C_2.txt`. La documentation de reprise précise les tests et conditions d'intégration sans publication.

Les prévisualisations et factures PDF fictives ont été rendues et inspectées visuellement : marquages, tableaux, totaux et pieds de page lisibles. Les cinq exemples du ZIP proviennent du parcours API local réussi, jamais de données réelles.
