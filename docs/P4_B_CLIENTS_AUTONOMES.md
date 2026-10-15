# P4-B — Profils client et organismes de prise en charge

## Contrat

- Une fiche client est créée et consultée sans compte fidélité ni carte. L'adhésion est une action séparée.
- Les comptes fidélité P4.5 gardent leurs identifiants, soldes, cartes, points, routes et reçus. Chaque ancien titulaire est copié vers un profil client lors de la migration additive ; aucun rapprochement automatique entre des titulaires distincts n'est effectué.
- Une nouvelle préparation peut référencer un `client_id`. Les ventes antérieures ne sont pas rapprochées automatiquement. `GET /{client_id}/ventes` expose uniquement les ventes explicitement liées, dans le site et les emplacements autorisés.
- Les fiches peuvent être associées à plusieurs **Organismes de prise en charge**. Les rôles sont **Organisme principal** et **Organisme complémentaire** ; une fiche ne peut avoir plus d'un organisme principal actif.
- Les champs `reference` restent des références d'adhésion. Ils ne constituent ni une créance ni une preuve d'éligibilité financière.
- P4 ne calcule ni **Part organisme** ni **Part client**. Aucun barème, taux, montant ou reste dû n'est ajouté dans cet incrément ; le calcul est reporté à P5.

## API

Base : `/api/clients/organisations/{organisation_id}`

| Méthode | Route | Permission | Rôle |
| --- | --- | --- | --- |
| GET | `/` | `client.consulter` ou `client.gerer` | Rechercher par nom, téléphone, courriel ou identifiant, puis paginer |
| POST | `/` | `client.gerer` | Créer un profil indépendant |
| GET | `/{client_id}` | `client.consulter` ou `client.gerer` | Consulter profil, organismes et adhésion facultative |
| PUT | `/{client_id}` | `client.gerer` | Modifier profil avec contrôle de révision |
| GET / POST | `/organismes` | `client.consulter` ou `client.gerer` / `client.gerer` | Lister ou créer un organisme générique |
| POST | `/{client_id}/organismes` | `client.gerer` | Associer un principal ou complémentaire |
| DELETE | `/{client_id}/organismes/{association_id}?cle=…` | `client.gerer` | Désactiver une association |
| POST | `/{client_id}/fidelite` | `fidelite.gerer` | Adhérer une fiche au programme existant |
| GET | `/{client_id}/ventes` | `client.consulter` + portée `vente.consulter` | Historique des ventes explicitement reliées |

Une fiche peut être choisie dans une préparation encore à l'état `PREPARATION` par `PUT /api/ventes/organisations/{organisation_id}/{vente_id}/client`, avec `vente.preparer` et `client.consulter`. L'opération vérifie l'organisation, le statut et la révision, écrit un événement d'audit, et refuse toute modification après changement d'état. Le client peut être désassocié explicitement avec `client_id: null`.

## Interface

- La navigation **Clients** donne accès à la recherche, aux fiches, à leurs organismes et à l'adhésion facultative. L'identifiant client est recherchable exactement.
- Les actions de création/modification et d'association sont affichées uniquement avec `client.gerer`.
- La vue montre points et cartes via les routes P4.5 existantes si `fidelite.consulter` est accordée ; création et opposition de carte restent soumises à `fidelite.gerer`.
- L'historique est filtré par `client.consulter`, `vente.consulter` et les emplacements permis. Un reçu PDF apparaît uniquement si la route renvoie le reçu et que `caisse.consulter` est permise pour cet emplacement.
- La sélection client de la préparation est distincte de la transmission et de l'encaissement. Elle ne change ni la caisse individuelle, ni le calcul de fidélité.

La migration `20261015_01` suit `f22f6abb13c5`. Elle ajoute des tables et des colonnes nullables, reporte les titulaires historiques vers des profils et ajoute deux permissions au catalogue sans les attribuer à aucun rôle. Les migrations historiques restent inchangées.

## Vérifications ciblées

`tests/test_clients_p4b.py` couvre la création indépendante, l'absence d'adhésion par défaut, l'association de plusieurs organismes, l'unicité du principal actif, l'adhésion facultative et le maintien des données de fidélité après modification du profil. Il vérifie la recherche par identifiant, la sélection explicite d'une fiche en préparation, l'exigence de permissions, le refus après reprise de l'état et l'historique client.

Les essais d'API ciblés s'exécutent sur les bases temporaires SQLite des fixtures de tests ; ils ne valident ni la concurrence PostgreSQL ni les calculs P5. La CI ajoute désormais `tests/test_clients_p4b.py::test_migration_p4b_postgresql_natif_sur_base_jetable_dediee` sur une base éphémère séparée nommée `neosys_p4b_migration`, et le parcours Chromium `tests/seed_browser_clients.py` + `tests/browser_clients.py` après les recettes P4.5.

Le parcours Chromium couvre les recherches par nom, téléphone et UUID, la création d'une fiche sans adhésion, la modification, l'adhésion facultative et une carte, deux organismes de rôles différents, l'historique scoped, l'association/retrait d'un client d'une préparation et le refus d'accès d'un profil sans permission. Les reçus nécessitent encore une recette Chromium dédiée avec une vente liée réellement encaissée ; les tests HTTP existants restent la vérification de référence des autorisations de reçus.
