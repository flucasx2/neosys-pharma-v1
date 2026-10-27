# B01 — Moyens de paiement configurables

## Modèle réutilisé

Les espèces restent le moyen natif `ESPECES`, piloté par
`ParametrageCaisseModel.modes` au niveau organisationnel. Les autres moyens sont
des identités `MoyenPaiementModel` rattachées à cette même organisation et à une
famille financière (`CARTE`, `MOBILE_MONEY`, `CHEQUE`, `VIREMENT`). Aucun modèle
parallèle ni fournisseur automatique n'est ajouté.

En l'absence de paramétrage enregistré, seules les espèces sont disponibles.
Cette configuration initiale est calculée sans écriture lors des consultations ;
le premier enregistrement conserve la révision attendue 0. La valeur par défaut
ORM est alignée. Une configuration existante, même vide, reste prioritaire : la
lecture ne réactive jamais les espèces désactivées. Les espèces n'ont pas
d'identifiant fournisseur et ne sont pas ajoutées à la liste `moyens`.

La configuration de famille et l'activation du fournisseur restent deux conditions
cumulatives. Activer une famille ne crée pas de moyen non espèces : toute nouvelle
confirmation requiert un identifiant explicitement créé par un utilisateur ayant
`caisse.parametrer`. La création d'un fournisseur ne change pas silencieusement
les familles activées. L'API existante conserve ces deux opérations distinctes.

## Garanties existantes conservées

- Unicité du code par organisation, appartenance organisationnelle et compatibilité
  famille/fournisseur contrôlées en persistance et dans les services.
- Permission, révision optimiste, idempotence et événements avant/après pour les
  modifications ; contrôle explicite de permission ajouté au service de paramétrage.
- Refus des fournisseurs désactivés lors des nouvelles confirmations et des
  encaissements individuel/groupé.
- Contrôle des familles activées lors des encaissements individuel et groupé,
  y compris les espèces. Pour une substitution de remboursement, famille et
  fournisseur de remplacement doivent être actifs à la demande et à l'exécution.
- Reçus, confirmations et remboursements gardent leurs identités/libellés figés.
  Aucun historique n'est renommé ou réécrit.

Les confirmations historiques sans fournisseur restent lisibles et utilisables
selon les contrôles financiers existants : ce sont des paiements déjà acquis.
La restitution vers leur identité historique sans fournisseur reste possible,
sans exiger sa réactivation. Une substitution vers un nouveau moyen non espèces
requiert un fournisseur explicite et la permission de substitution existante.

## Correction finale validée — remboursements historiques

La désactivation interdit les nouveaux paiements, mais n'empêche pas de restituer
un paiement historique sur son identité exacte d'origine (famille et identifiant
fournisseur identiques). L'exception s'applique aussi aux espèces et aux familles
désactivées, à la demande comme à l'exécution, uniquement dans le parcours de
remboursement existant. Elle couvre les retours de ventes encaissées et les
paiements acquis non finalisés. Les permissions de demande, autorisation préalable,
exécution et les contrôles de montant, session, disponibilité des espèces et
preuves restent applicables. Aucun moyen n'est automatiquement réactivé.

Une substitution exige toujours la permission spécifique et un remplacement
actif. L'état du remplacement et la permission sont revérifiés à l'exécution,
même après autorisation. Le périmètre organisationnel et la famille du fournisseur
restent vérifiés, y compris pour l'identité historique désactivée.

Après confirmation effective, l'audit existant reçoit l'événement
`P4.5:REMBOURSEMENT_HISTORIQUE_MOYEN_DESACTIVE` avec le dossier, les moyens
désactivés utilisés, les montants, demandeur/autorisateur, auteur d'exécution,
justification, preuves et identifiant d'opération. Il est enregistré dans la même
transaction que l'exécution ; aucun événement de ce type n'est produit pour une
tentative refusée et le rejeu idempotent ne le duplique pas. Les événements
ordinaires de demande, autorisation et exécution sont conservés.

## Migration et portée

Aucune migration nécessaire : aucune colonne, contrainte ou donnée historique
n'est modifiée. Les paramétrages enregistrés gardent leurs valeurs. Aucune
migration appliquée à une base conservée, aucun bootstrap, aucun changement d'interface, de calcul XAF,
de fidélité, de prise en charge, de marqueur ou de confirmation P4/P5.

## Validation avant B02

Les tests sont exécutés dans le service Docker `tests`, sans dépendances démarrées
(`run --rm --no-deps`), avec `TEST_DATABASE_URL=sqlite+pysqlite://` imposé par
l'entrypoint. Les fixtures SQLite créent/suppriment uniquement leur base en mémoire.
Le contrôle statique vérifie les réseaux internes, secrets séparés, ports et volume
externe ; `check-target` valide le garde avant exécution. Aucune base PostgreSQL
Windows ou Docker persistante n'est utilisée.

Avant B02, valider le choix d'interface pour les deux niveaux existants (famille
et fournisseur), l'état sans aucun moyen actif et la présentation des espèces
sans fournisseur. Les nouveaux appels non espèces doivent transmettre `moyen_id`.
Ne pas proposer automatiquement une famille sans fournisseur créé. Les preuves
et confirmations externes restent obligatoires. Les tests de concurrence native
PostgreSQL nécessitent encore une orchestration de bases jetables marquées et
validées ; les protections actuelles restent en place.

Les tests de cycle de migration existants utilisent également des fichiers SQLite
temporaires sous `/tmp` dans le conteneur, sans migration sur PostgreSQL.

Commande de régression B01 exécutée avant la correction finale (non relancée) :

```powershell
docker compose -p neosys-pharma-dev --env-file .env.docker.example --profile test run --rm --no-deps tests python -m pytest -q -ra -p no:cacheprovider tests/test_b01_moyens_paiement.py tests/test_moyens_paiement.py tests/test_caisse.py tests/test_regularisation.py tests/test_p4p5_groupe_organismes.py
```

## Fichiers concernés et risques

- `domain/caisse.py` : définition des familles initiales.
- `infrastructure/caisse_models.py` : défaut ORM du paramétrage.
- `application/caisse_service.py` : défaut effectif, permission du service,
  sélection explicite du fournisseur pour les nouvelles confirmations.
- `application/regularisation_service.py` : fournisseur explicite en substitution,
  exception historique ciblée, contrôle du remplacement et audit existant enrichi.
- `tests/test_b01_moyens_paiement.py` : scénarios B01 et correction finale ciblée.
- `tests/test_caisse.py`, `tests/test_regularisation.py` : données de recette
  avec identifiants explicites ; assertion d'un message de refus préexistant
  actualisée, refus HTTP 409 conservé.
- Ce document.

Le principal risque de compatibilité concerne les clients envoyant une nouvelle
confirmation non espèces sans `moyen_id` : ils sont désormais refusés, même sans
fournisseur configuré. Ce changement est intentionnel. Un remplacement désactivé
après autorisation bloque l'exécution d'une substitution ; l'identité d'origine
désactivée reste remboursable sous les contrôles et l'audit précités. Les bases qui possèdent déjà
un paramétrage ne voient aucune activation automatique nouvelle. La concurrence
native PostgreSQL n'est pas couverte par les validations SQLite.

## Résultats du 21 octobre 2026

Avant la correction finale des remboursements historiques, la commande ci-dessus
a terminé avec **78 réussites, 12 ignorés, aucun
échec**, en 273,67 secondes. Les six nouveaux scénarios B01 sont compris dans
les 78 réussites. Les ignorés correspondent aux cinq cas de concurrence caisse,
quatre variantes de concurrence régularisation et trois variantes de contention
P4/P5 nécessitant PostgreSQL natif. Un avertissement de dépréciation existant
Starlette/httpx reste présent.

Une première exécution avait donné 72 réussites, 12 ignorés et trois échecs de
tests : deux payloads de remboursement sans identifiants explicites et une
assertion de message périmée. Ces attentes ont été corrigées avant la relance
finale, sans assouplir les contrôles serveur.

`python -B docker/check_static.py` : 17 cas du garde réussis, isolation Compose,
volume externe et verrous hachés validés. `git diff --check` : réussi.
`tests check-target` : accepté avant les tests, sans connexion PostgreSQL.
`docker compose ... ps` : app et db healthy ; aucun de ces services n'a été
recréé ou arrêté. Aucun service `test-db` démarré : les suites sélectionnées
utilisent SQLite dans le conteneur tests.

Bloc B01 validé par l'utilisateur ; enregistrement par commit local autorisé sur
`dev/codex-docker`. Aucun push ni merge autorisé.

## Validation ciblée de la correction finale

Seuls `application/regularisation_service.py`, les tests B01 et ce rapport ont
été ajustés pour cette correction finale. Aucun modèle ni schéma supplémentaire.

La cible a de nouveau été acceptée par `tests check-target`. L'image `tests` a
été reconstruite puis les sélections suivantes ont été exécutées via Compose
`run --rm --no-deps tests python -m pytest -q -ra -p no:cacheprovider` :

- `tests/test_b01_moyens_paiement.py` (16 cas, paramétrages compris) ;
- `tests/test_regularisation.py::test_paiement_acquis_restitution_preuve_et_blocage_z` ;
- `tests/test_regularisation.py::test_rollback_remboursement_et_non_contournement`
  (4 variantes : PDF, fonds insuffisants, garde fiscal, doublon) ;
- `tests/test_moyens_paiement.py::test_deux_fournisseurs_recu_remboursement_et_clotures`.

Première passe : 20 réussites et 2 échecs d'assertions de libellé, en 97,80 s.
Les deux assertions confondaient le libellé courant du fournisseur renommé avec
le libellé historique d'origine. Elles ont été corrigées en vérifiant séparément
ces deux valeurs, sans modifier le comportement des libellés.

Les 8 variantes de
`tests/test_b01_moyens_paiement.py::test_remboursement_historique_moyen_desactive_audite`
ont ensuite été rejouées : **8 réussites, aucun échec, aucun ignoré**, en 38,26 s.
Le bilan couvre donc **22 cas ciblés distincts validés**. La suite complète n'a
pas été relancée. L'avertissement Starlette/httpx préexistant subsiste.

Couverture : refus des nouveaux paiements désactivés ; remboursement historique
sur le fournisseur ou la famille désactivés avant demande ou après autorisation ;
retour de vente et paiement acquis non finalisé ; espèces désactivées ; refus des
substitutions sans permission ou vers un fournisseur/une famille/les espèces
désactivés à la demande et à l'exécution ; autorisation préalable, permission
d'exécution, plafonds et preuves obligatoires ; audit explicite sans doublon ni
événement d'exécution pour les tentatives refusées ; absence de réactivation et
immutabilité des confirmations et reçus historiques.

Contrôles statiques : 17 cas du garde réussis ; `git diff --check` réussi après les
tests. Aucune base PostgreSQL ou migration utilisée dans cette validation.

Limites : concurrence native PostgreSQL non rejouée et non validée ici ; la
restitution externe reste manuelle avec les preuves et confirmations existantes,
sans connecteur bancaire automatique. B02 devra rendre lisible la distinction
entre origine historique désactivée et remplacement actif, sans automatiser
l'exécution. Aucun travail B02, push ou merge effectué. Le commit local de clôture
B01 est autorisé après contrôle du périmètre et de `git diff --check`.
