# Résultats — P5-B.3

## Référence et périmètre

- Branche locale : `feat/p5-b-moteur-prise-en-charge`.
- Base : P5-A `ebbe37e7fa241e9b29e3a9eb83c53635bf3f8e15`, P5-B.1 `b05b8b4c920858cc90749d91c6519a40a4d850b0`, P5-B.2 `d9a6c79`.
- Aucun push, PR, fusion, déploiement ni accès à une base conservée.
- P5-C (factures, créances facturées, bordereaux et règlements organismes) n'est pas implémenté.

## Fonctionnalités livrées

1. La finalisation individuelle d'une vente P5-B utilise le montant `part_client_xaf` comme montant dû et conserve le TTC de vente historique dans son snapshot. Le client peut répartir sa part entre les moyens P4 existants. Les confirmations non espèces restent requises et rattachées à la vente.
2. Les montants client et organismes, par vente, ligne et organisme, figurent sur le reçu et dans son snapshot. Le montant comptabilisé dans les mouvements de caisse X/Z reste le montant net payé par le client, rendu d'espèces déduit.
3. La migration `20261017_03` ajoute un registre append-only `tiers_payant_realisations`, lié aux snapshots P5-B.2, à l'encaissement individuel, à la vente, à l'organisation et au site. Cette réalisation définitive est créée dans la transaction d'encaissement et uniquement si une part organisme est due. Elle est la source transactionnelle préparatoire de P5-C; elle ne constitue pas une facture ni un règlement organisme.
4. Les retours préservent le TTC historique, la part organismes et la part client. Le champ P4 `vente_retours.montant` reste le montant remboursable au client. Les remboursements P4 existants restent plafonnés par les règlements disponibles, par moyen d'origine.
5. Les points d'acquisition sont calculés à partir des lignes explicitement codées `COSMETIQUE` et de la part client associée. Les produits de nature médicament ou inconnue ne génèrent pas de points. Les retours successifs révoquent les points acquis de manière cumulative; un historique d'utilisation est restauré au prorata selon ses snapshots. Si une révocation dépasse les points disponibles, le service utilise le champ dette P4 non négatif et conserve le journal compensatoire.
6. La consultation caisse peut afficher une vente tierce avant la confirmation de son calcul. L'encaissement reste bloqué tant que le snapshot P5-B.2 n'est pas admissible et confirmé.

## Anomalies reproduites et corrections

- Le test réel d'encaissement a montré que `StockService.ajouter()` injecte déjà l'organisation. La création de la réalisation passait l'organisation une seconde fois et échouait avant commit; l'argument redondant a été retiré et l'intégration repasse.
- `alembic check` a détecté une divergence entre `NUMERIC(18,0)` de migration et `MontantXAF` dans le modèle des retours. La migration utilise désormais le type XAF canonique, réutilisant son mapping SQLite/PostgreSQL; les trois contrôles P4 de cycle/alembic passent à nouveau.
- La route de consultation de la caisse essayait de valider obligatoirement un snapshot tiers même lorsqu'il n'existait pas encore. Elle retourne maintenant `prise_en_charge: null` dans ce seul cas, ce qui permet l'affichage du ticket; la route de finalisation continue d'exiger `_prise_en_charge()` et refuse tout paiement sans snapshot confirmé.

## Migration et intégrité

- Révision Alembic : `20261017_03`, dépend de `20261017_02`.
- Colonnes nullable ajoutées à `vente_retours`: `montant_ttc_xaf`, `montant_organismes_xaf`; une valeur nulle conserve les anciens retours P4 sans ventilation tierce.
- Registre de réalisation : unicité par vente, encaissement et calcul; FK composites garantissant l'organisation et le site de la vente ainsi que le rattachement au même encaissement et calcul; contraintes d'équilibre XAF; déclencheurs UPDATE/DELETE immuables.
- Les colonnes de montant utilisent le type canonique `MontantXAF` : INTEGER sur SQLite et NUMERIC(18,0) sur PostgreSQL.
- La migration a été montée/descendue dans le contrôle SQLite existant. Celui-ci vérifie aussi la présence des colonnes, FK, contraintes uniques, checks, triggers et la conservation d'un organisme P4-B fictif.

## Tests réellement exécutés

Python utilisé : **3.14.8**.

Commande de la suite ciblée (11 modules P4/P5, stockage éphémère SQLite des tests) :

```sh
PYTHONPATH="src:tests:<site-packages Python 3.14>" python3.14 -m pytest -q \
  tests/test_p5b_1_moteur_prise_en_charge.py \
  tests/test_p5b_2_projection_persistance.py \
  tests/test_p5b_2_integration_vente.py \
  tests/test_p5b_3_encaissement_prise_en_charge.py \
  tests/test_p5a_tiers_payants.py tests/test_vente.py \
  tests/test_clients_p4b.py tests/test_encaissement_groupe_domain.py \
  tests/test_encaissement_groupe_persistance.py tests/test_caisse.py \
  tests/test_regularisation.py
```

Résultat après correction : **148 passed, 12 skipped, 1 warning, 3 subtests passed** en 112,37 s. Les 12 ignorés sont les scénarios qui exigent PostgreSQL natif et deux connexions, ou une URL PostgreSQL jetable nommée explicitement (concurrence vente/caisse/remboursement, migration native P4-B/P4-C et concurrence de l'encaissement groupé). Le seul avertissement est une dépréciation Starlette liée à l'utilisation de `httpx` dans le TestClient.

Contrôle relancé après correction de la représentation du type de montant : **6 passed, 1 warning** pour les cycles `alembic check` P4/P4.4/P4.5, le cycle de migration P5-A/B.2/B.3 et les deux tests d'intégration P5-B.3.

`git diff --check`, `node --check` sur `caisse.js` et `compileall` Python ciblé ont réussi.

Le scénario API SQLite P5-B.3 vérifie réellement : cascade principal + deux secondaires, règlement de la seule part client par carte et espèces, reçu PDF et détail des montants, absence d'encaissement double, réalisation unique, mouvements de caisse et total X par mode limités à la part client, points limités à la part client, médicament sans points, panne PDF provoquée avant commit et rollback du stock/encaissement/réalisation/mouvement/fidélité, rejeu idempotent du reçu, retours partiels successifs, remboursements en modes d'origine, rejeu du retour et du remboursement, puis compensation avec un journal historique fictif de points utilisés.

## Contrôles non exécutés / risques résiduels

- **PostgreSQL natif : non exécuté.** Aucun `psql`, `postgres`, Docker ou Podman n'était disponible. Les tests SQLite ne valident ni les verrous PostgreSQL, ni les niveaux d'isolation, ni les déclencheurs PostgreSQL de cette migration. Aucune URL ou base PostgreSQL n'a été utilisée.
- **Chromium : non exécuté.** Aucun Chromium/Chrome installé dans cet environnement. La vérification `node --check` ne prouve pas le parcours navigateur ni les appels HTTP dans l'interface.
- Le test d'intégration des retours avec journal `UTILISATION` simule un journal historique fictif directement en base, car l'utilisation de points reste bloquée par la règle fiscale P4 non validée. Une recette humaine doit vérifier le cas historique et toute éventuelle dette de points.
- Le code reconnaît uniquement le code de nature canonique `COSMETIQUE`. Confirmer que le catalogue de production utilise exactement ce code avant activation des acquisitions de points; aucun autre code n'est assimilé à un cosmétique.
- Le barème est configuré en données existantes; vérifier opérationnellement la valeur 1 point / 1 000 XAF avant recette.
- La vente en mode tiers peut être encaissée individuellement après confirmation. Le moteur de groupe P4 n'accepte toujours que `SANS_TIERS`; l'encaissement groupé de ventes avec des parts organismes reste un travail d'intégration futur. Les ventes groupées P4 comptant ne sont pas modifiées.
- Les remboursements P4 rendent au client sa part et n'émettent pas de remboursement organisme. P5-C devra créer les créances et les ajustements organismes à partir du registre de réalisation et des retours traçables.

## Statut

**P5-B.3 est livré localement avec tests SQLite ciblés, mais n'est pas validé pour activation.** Il faut encore exécuter les migrations et scénarios transactionnels sur PostgreSQL natif jetable, la recette Chromium et la recette humaine. Maintenir toute activation financière de prise en charge désactivée hors test isolé. P5-B ne doit pas être déclaré terminé et P5-C n'est pas commencé.
