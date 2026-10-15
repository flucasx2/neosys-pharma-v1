# P4.6 — Recette humaine locale sous Windows

## Périmètre et preuves

La CI complète 38271053293 a validé le commit `1ddc8c3ea1d37c3b307d57ad48a7e3ee8db44c28` : SQLite 385 réussis/22 ignorés, PostgreSQL 17 406 réussis/1 ignoré, neuf parcours Chromium réussis. Le statut `neosys/recette-complete` appartient exclusivement à ce SHA.

La stabilisation locale change uniquement les libellés de caisse et leur test DOM :

- TRANSMISE : « Montant dû », avec le contexte de session.
- ENCAISSEE : « Montant encaissé à l’origine », sans demande d’ouverture de session. Le montant provient du reçu correspondant lorsqu’il est chargé, sinon du TTC serveur de la vente déjà finalisée. Ce montant historique n’est pas le net restant après d’éventuels remboursements, ni la somme des espèces remises avant rendu de monnaie.
- Autres états : « Montant de la préparation », sans présenter un brouillon ou une annulation comme une dette.

Aucun moteur financier, état, réservation, droit, migration ou mécanisme d’immuabilité n’est modifié. Aucun commit ni push n’est effectué pendant cette préparation. La recette CI précédente ne valide pas automatiquement les modifications locales.

## Démarrage minimal — PowerShell, base SQLite jetable

Ces commandes sont destinées au poste Windows ; elles n’ont pas été exécutées sur Windows dans l’environnement Linux de préparation. SQLite permet la recette visuelle sans connexion à PostgreSQL 18, donc sans toucher à `neosys_pharma_v1`. La concurrence PostgreSQL reste couverte par la CI existante, pas par cette recette SQLite.

Ouvrir PowerShell depuis le dépôt, sur `feat/p4-6-comptoir`. Vérifier le SHA sans écraser les modifications locales :

```powershell
git branch --show-current
git rev-parse HEAD
git status --short
```

Le SHA attendu avant publication de la correction est `1ddc8c3ea1d37c3b307d57ad48a7e3ee8db44c28`. Si la correction n’est pas déjà présente, le paquet de recette fournit `stabilisation-locale.patch` ; vérifier puis appliquer depuis la racine du dépôt :

```powershell
git apply --check C:\chemin\pieces-recette\stabilisation-locale.patch
git apply C:\chemin\pieces-recette\stabilisation-locale.patch
```

Ne pas appliquer une seconde fois. Ne pas utiliser de reset, clean ou checkout pour écraser un travail existant. Aucun push.

Utiliser l’environnement virtuel existant. Seulement s’il n’existe pas :

```powershell
py -3.14 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e '.[dev]'
```

Préparer une base neuve et ses comptes. Le script utilise historiquement `/tmp/p1-browser-fixture.json`, soit le dossier `tmp` à la racine du lecteur courant sous Windows. S’il existe déjà, arrêter et conserver ce fichier : ne pas l’écraser. Ne pas lancer deux initialisations simultanément.

```powershell
$python = Join-Path (Get-Location).Path '.venv\Scripts\python.exe'
$fixture = & $python -c "from pathlib import Path; print(Path('/tmp/p1-browser-fixture.json').resolve())"
if ($LASTEXITCODE -ne 0) { throw 'Python indisponible' }
if (Test-Path $fixture) { throw 'Fixture existante à préserver : arrêter sans écrasement' }
$recette = Join-Path $env:LOCALAPPDATA ('NeoSysP46Recette\recette-' + (Get-Date -Format 'yyyyMMdd-HHmmss'))
if (Test-Path $recette) { throw 'Choisir un dossier neuf' }
New-Item -ItemType Directory -Path $recette -ErrorAction Stop | Out-Null
$sid = [System.Security.Principal.WindowsIdentity]::GetCurrent().User.Value
icacls $recette /inheritance:r /grant:r ('*{0}:(OI)(CI)F' -f $sid) | Out-Null
if ($LASTEXITCODE -ne 0) { throw 'Protection du dossier impossible' }
New-Item -ItemType Directory -Force -Path (Split-Path $fixture) | Out-Null
$db = Join-Path $recette 'neosys_p46_recette_humaine.db'
$dbURL = 'sqlite:///' + $db.Replace('\', '/')
& $python scripts/recette_comptoir.py --database-url $dbURL --confirmer-base-jetable
if ($LASTEXITCODE -ne 0) { throw 'Initialisation interrompue : préserver les fichiers pour diagnostic' }
icacls $fixture /inheritance:r /grant:r ('*{0}:F' -f $sid) | Out-Null
if ($LASTEXITCODE -ne 0) { throw 'Protection des identifiants impossible' }
Copy-Item $fixture (Join-Path $recette 'comptes-recette.json') -ErrorAction Stop
# Suppression uniquement de la fixture produite par CETTE initialisation, après copie privée.
Remove-Item $fixture -ErrorAction Stop
Set-Content (Join-Path $recette 'database-url.txt') $dbURL -Encoding utf8
```

Les migrations additives existantes jusqu’à `a46c001d2026` sont appliquées uniquement au nouveau fichier. Aucune nouvelle migration n’est créée. Les seeds produisent des données fictives, deux conditionnements avec entrées physiques explicites et des affectations P1 explicites. Ils ne doivent jamais être utilisés sur une base métier.

Démarrer dans le même terminal :

```powershell
$env:DATABASE_URL = $dbURL
$env:AUTH_COOKIE_SECURE = 'false'
& $python -m uvicorn neosys_pharma.presentation.app:app --host 127.0.0.1 --port 8000
```

Ouvrir http://127.0.0.1:8000 dans Chrome. Arrêter par Ctrl+C. Pour reprendre une session ultérieure, **ne pas relancer le seed** :

```powershell
$recette = 'C:\chemin\vers\le\dossier\recette-yyyyMMdd-HHmmss'
$env:DATABASE_URL = (Get-Content (Join-Path $recette 'database-url.txt') -Raw).Trim()
if ($env:DATABASE_URL -notmatch '^sqlite:///.*[/]neosys_p46_recette_[^/]+\.db$') { throw 'URL de recette isolée attendue' }
$env:AUTH_COOKIE_SECURE = 'false'
.\.venv\Scripts\python.exe -m uvicorn neosys_pharma.presentation.app:app --host 127.0.0.1 --port 8000
```

L’application reste limitée au poste local. Ne pas exposer le port au réseau et ne pas employer ces cookies HTTP en production.

## Connexion et acteurs fictifs

Lire `comptes-recette.json` dans le dossier privé : `organisation_id` renseigne le formulaire de connexion ; `password` contient le mot de passe aléatoire de recette. Ne pas envoyer ce fichier, le committer ou le joindre aux captures. Chaque acteur utilise sa propre session ; les identifiants de test ne constituent aucun mécanisme d’administration implicite.

| Identifiant | Usage |
| --- | --- |
| vente.qa | Préparer, demander des remises, transmettre, éditer les documents |
| responsable.qa | Autoriser les remises avec les plafonds fictifs explicitement configurés |
| caisse.qa | Sessions, paiements, reçus, fidélité et opérations P4.5 habilitées |
| responsable.p45.qa | Responsable distinct pour les validations caisse/coffre |
| vente.lecture.qa | Consultation des préparations et éditions ; aucune mutation commerciale |
| caisse.lecture.qa | Consultation caisse, sans encaissement ni paramétrage |

Sélectionner **Libreville QA / Réserve QA**. Le site Owendo et le comptoir non autorisé servent aux refus d’accès. Utiliser **PRÉPARATION VENTE QA P4**, CIP7 `8812345`, code-barres `8812345678901`, BOÎTE DE 20 P4 ou BOÎTE DE 60 P4. Les deux préparations transmises issues du seed permettent de commencer immédiatement la recette de caisse. Aucun moyen de paiement ni ticket d’appel n’est activé implicitement : les choisir avec `caisse.qa` dans « Moyens de paiement ».

## Ordre pratique de recette

Exécuter la grille complète de `P4_6_RECETTE.md`, avec fenêtres/sessions Chrome séparées pour le préparateur, les responsables et le caissier. Les numéros de départ dépendent des préparations fictives déjà transmises : ne pas supposer que la prochaine préparation porte 0001.

1. Rechercher les préparations par désignation, référence et UUID ; filtrer, paginer, actualiser et vérifier la conservation des critères et du contexte.
2. Créer une préparation, choisir explicitement le conditionnement, saisir les quantités, vérifier stock et erreurs sans perte de saisie ; demander puis autoriser une remise dans une autre session.
3. Éditer un PDF avant modification, enregistrer le fichier téléchargé, modifier une ligne, éditer une nouvelle révision. Ouvrir la première édition dans « Éditions historiques » : quantité et allocations d’origine inchangées. Vérifier le SHA-256 avec `Get-FileHash -Algorithm SHA256`.
4. Valider puis transmettre ; constater le numéro d’appel, les deux exemplaires CLIENT/PANIER si l’option est activée, la réimpression sans nouvelle attribution.
5. Ouvrir une session de caisse compatible et sélectionner le dossier : « Montant dû ». Effectuer le paiement intégral confirmé, éventuellement mixte avec référence/preuve. Vérifier « Montant encaissé à l’origine », l’absence d’action pour payer à nouveau et le reçu retrouvable par recherche.
6. Poursuivre fonds, retours, quarantaine, fidélité et X/Z selon la grille. Les points monétaires, le crédit et les tiers payants restent bloqués. Aucun coût historique ne doit être inventé.
7. Rejouer les consultations avec les comptes en lecture seule, au clavier (Tab/Maj+Tab/Entrée/Échap et raccourcis documentés). Consigner les refus, captures et documents dans un dossier sans secrets.

Le PDF joint aux pièces locales est une édition réelle de la révision 2 (trois unités), issue de l’API et conservée après passage à la révision 3 (quatre unités). Ce document est une preuve fictive locale, pas un artefact de l’exécution CI précédente. Les UUID de votre nouvelle recette Windows seront différents.

## Publication sans GitHub Actions — proposition à approuver

Le dépôt contient uniquement `.github/workflows/tests.yml`, déclenché automatiquement par `push` sur main et `pull_request`. Proposition : après accord, publier un seul commit avec `[skip ci]` dans son message, sur la branche P4.6 uniquement, en conservant la PR #6 Draft et sans événement Ready, réouverture, dispatch ou fusion. GitHub documente que cette instruction empêche les workflows `push`/`pull_request` de se déclencher ; elle ne couvre pas d’autres familles d’événements.

Les contrôles ignorés peuvent rester pending ; ils ne valent pas recette réussie. Le nouveau SHA n’hérite pas du `success` de `1ddc8c3`. Ne pas publier artificiellement `neosys/recette-complete=success`, ne pas modifier le budget ou les protections, et ne pas déclencher de recette complète. La validation du nouveau SHA devra être décidée explicitement après revue des résultats locaux et de la recette humaine.

Référence : https://docs.github.com/en/actions/how-tos/manage-workflow-runs/skip-workflow-runs
