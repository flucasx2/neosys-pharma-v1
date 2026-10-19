# Consolidation P4/P5 — incrément 01

Base locale vérifiée : `1cc86cee036dc20d5b174832e6565e7c4f008da0`, arbre propre avant intervention, parent P5-CONF.1a `40c8fb27cca0c9b532d2536e8bb542930dab4452`. Empreinte du patch P5-CONF.1b revérifiée : `84f71f9b1fe02f8d1b146dafbf6c21140394fe33d48686e15d56967c0ead4d6c`. L'incrément était déjà présent : aucune seconde application ni reconstruction. Branche isolée `work/p4-p5-consolidation`. Aucun accès Windows ou distant.

## Décision et portée

La mission du 19 octobre suspend les recettes humaines intermédiaires. Les scénarios déjà rédigés sont conservés pour une recette unique P4/P5. Aucun résultat automatique ne vaut acceptation humaine. Les contraintes de publication et de données sont maintenues.

Le service groupé refusait explicitement les modes autres que SANS_TIERS et calculait le montant dû sur le TTC global. Il utilise désormais la validation P5-B de l'encaissement individuel (`_prise_en_charge`) pour les ventes avec organismes. Les snapshots doivent être confirmés et correspondre aux révisions et montants des ventes. Le mode CREDIT reste refusé.

Les allocations groupées portent uniquement sur les parts clients. Chaque vente conserve un EncaissementModel, ses références individuelles, ses allocations de règlements et sa réalisation de prise en charge. Les organismes ne deviennent pas des règlements de caisse. Les confirmations restent uniques ; les mouvements de groupe ne sont pas doublés par des mouvements individuels. Les allocations existantes restent le support des règlements par vente et des remboursements : aucune duplication dans caisse_reglements.

Fidélité : réutilisation de `gagner` avec la part client par ligne, selon les règles P5-B.3. Les reçus individuels reprennent les parts ; le reçu collectif distingue net des ventes / organismes / clients lorsque nécessaire. Le champ historique total_xaf du groupe reste le total réellement encaissé des clients. Aucun calcul de prise en charge n'est refait en JavaScript. Aucune migration nécessaire. Aucune créance P5-C inventée : réalisation P5-B existante réutilisée.

## Résultats réellement exécutés

Python 3.14.8, SQLite isolé :

```sh
TZ=Africa/Libreville PYTHONPATH=src:tests:<site-packages-3.14> python3.14 -m pytest -q tests/test_p4p5_groupe_organismes.py tests/test_p5b_3_encaissement_prise_en_charge.py tests/test_encaissement_groupe_domain.py tests/test_caisse.py -k 'groupe or part_client or medicaments'
```

**15 passed, 5 skipped, 43 deselected, 1 warning, 3 subtests passed — 34,89 s.** Les 5 skips sont les trois nouveaux scénarios natifs et deux contrôles natifs existants ; ils ne valident aucune concurrence PostgreSQL. Les trois nouveaux cas API SQLite sont réussis : groupe mixte, groupe de deux clients avec organismes, rollback après création des pièces. Retour/remboursement, X, non-double comptabilisation, points par client et rejeu sont vérifiés dans ces cas.

`NODE_PATH=<jsdom>/node_modules node tests/groupe_organismes_ui.cjs` : **9 assertions DOM réussies**, code/HTML applicatifs, HTTP simulé. Node --check réussi. Chromium et PostgreSQL natif non exécutés ; blocages de l'environnement déjà établis, pas de nouvelle installation répétitive.

Les trois scénarios natifs préparés exigent des connexions/PID indépendants, une attente réellement observée via pg_blocking_pids et des délais bornés. Ils couvrent le rejeu simultané du même groupe, deux dossiers visant les mêmes ventes et individuel contre groupe. Le module refuse les fixtures PostgreSQL destructrices sauf base neuve `neosys_p4p5_*`, nom confirmé dans P4P5_CONFIRM_DATABASE et commentaire NEOSYS_P4P5_DISPOSABLE. Ne jamais lancer ces fixtures sur une base conservée.

Le flag de finalisation n'est activé que par monkeypatch dans l'application fictive des tests API ; son contrôle serveur et son défaut désactivé ne changent pas. Pas d'activation sur une instance ordinaire.

## Fichiers applicatifs

- application/encaissement_groupe_service.py : dette client, réalisation et points par vente.
- infrastructure/caisse_pdf.py : répartition sur reçu collectif, compatibilité des anciens reçus.
- presentation/web/encaissement_groupe.js : sélection et total des parts clients, refus de sélection sans prise en charge confirmée.
- tests/test_p4p5_groupe_organismes.py : contrôles API, rollback, données financières et concurrence native préparée.
- tests/groupe_organismes_ui.cjs : DOM et variante Chromium sur localhost.

## Limites

Validation technique partielle : sûreté PostgreSQL native et Chromium restent à démontrer. Le moteur ne doit pas être activé sur base conservée. Les clôtures Z, retours successifs, confirmations partagées et comptes fidélité ont leurs régressions existantes ; seules les branches ciblées indiquées ci-dessus ont été exécutées ici, pas une campagne P4 complète. Aucun module P4/P5 n'est déclaré clos.
