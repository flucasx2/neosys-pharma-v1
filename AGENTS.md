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
