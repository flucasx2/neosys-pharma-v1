# NeoSys Pharma — sécurité locale

- Travailler exclusivement dans ce checkout ; branche attendue `dev/codex-docker`.
- Vérifier Git avant toute intervention. Ne pas changer de branche, fusionner,
  créer de commit ou publier sans autorisation explicite. Préserver les changements utilisateur.
- Ne jamais lire ou afficher les secrets réels ; ne pas versionner les fichiers .env.
- PostgreSQL Windows et ses bases de recette sont conservés : aucune connexion,
  migration, suppression, création de tables ou exécution de tests sur ces bases.
- Docker : développement via `db`, tests via `test-db`, réseaux et comptes séparés.
  Aucun port PostgreSQL publié ; aucun montage des données Windows ; aucun réseau hôte.
- Migrations et bootstrap sont manuels, jamais automatiques au démarrage.
  Vérifier la cible avant toute commande ; demander l'autorisation si elle manque.
- Les fixtures pytest peuvent supprimer leurs tables. Aucun TEST_*_URL hérité
  du poste ; pas de tests natifs sans orchestration de bases jetables validée.
- Ne jamais affaiblir les marqueurs, confirmations et protections P4/P5.
- Ne pas modifier les règles métier de calcul, encaissement, fidélité et prise en charge.
- Conserver le volume de développement. Ne jamais utiliser `docker compose down -v`
  ni les commandes de purge de volumes.
- Volume de développement externe : `neosys_pharma_dev_pgdata`. Création et cycle
  de vie uniquement sur autorisation explicite ; aucun remplacement par un volume jetable.
- Secrets Compose locaux : `.secrets/`, jamais versionnés, affichés ou copiés
  dans une image. Tests ne reçoit que son secret, jamais celui de développement.
- Mise en service autorisée : construire app/tests, créer les secrets locaux et
  le volume dédié absent, démarrer seulement db/app, migrer la base Docker neuve
  après confirmation de cible et laisser l'utilisateur saisir le bootstrap.
  Les services de tests et les tests destructifs restent hors de cette autorisation.
- Le réseau frontend sert uniquement à la publication HTTP de app ; db reste sur
  development interne, tests/test-db sur testing interne.

## Continuité documentaire — décision du 27 octobre 2026

- Avant modification, lire JOURNAL_DEVELOPPEMENT.md, PROGRESS.md et
  REPRISE_NEOSYS_PHARMA.md ; confronter leurs informations à Git et aux preuves.
- JOURNAL_DEVELOPPEMENT.md est cumulatif : ajouts uniquement, aucune ancienne
  entrée effacée ou réécrite. Archiver les décisions de PROGRESS.md avant de
  remplacer son état courant. Les rapports de validation historiques sont conservés.
- PROGRESS.md décrit l'état courant daté, la dernière IA, les résultats réellement
  vérifiés, blocages, limites et autorisations manquantes ; référencer les rapports
  détaillés au lieu de recopier leurs tableaux.
- REPRISE_NEOSYS_PHARMA.md conserve les décisions structurantes et leur
  traçabilité ; distinguer instructions courantes et consignes remplacées.
- Priorité : clôture P4/P4-05. P5 historique est gelé et incomplet : aucune
  activation ni poursuite automatique, aucune validation exhaustive P5 nouvelle
  requise pour clôturer P4. Ne pas supprimer ses commits ou dépendances partagées.
- Aucun résultat, SHA ou acceptation ne doit être inventé. Une suite partielle,
  un job annulé ou une CI sur un ancien SHA ne valide pas le nouveau HEAD.
- À la fin de la mission de clôture : arrêter les développements et présenter
  les preuves et le périmètre. Attendre les autorisations d'intégration, de
  commits, de publication et d'opérations GitHub ; aucun merge ou déploiement implicite.

## Références Git — décision du propriétaire du 27 octobre 2026

- Référence de publication autorisée : `origin/main`, SHA attendu
  `2910cc60e8c8287a587ce8ff8e3f48c95be1ba39`. Revérifier le serveur distant
  avant toute intégration ; aucune mise à jour automatique des références.
- `main` local est volontairement non synchronisé à
  `fe53c42dc89d79618290b182aae29b01d8cb42d6` : ne pas le modifier,
  réinitialiser, fusionner ou synchroniser automatiquement.
- Distinguer ces références dans l'audit et conserver l'anomalie connue.
  Un ancien contrôle exigeant leur égalité reste une preuve historique d'échec.
  Toute adaptation doit être ciblée, vérifiable, présentée puis autorisée avant
  application ; ne pas supprimer ni rendre artificiellement passant un contrôle.
