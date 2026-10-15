# P4-B — Incrément 1 : historique de ventes fidélité

## Écart visé

P4.5 possède déjà des comptes fidélité (nom/téléphone), des cartes physiques et virtuelles, des soldes et dettes de points, ainsi qu'un journal des acquisitions et compensations. Les ventes enregistrent le compte fidélité associé à l'encaissement. Le journal existant montre les mouvements de points, mais ne donne pas la liste des ventes qui ont été liées à ce compte.

## Contrat ajouté

`GET /api/caisses/organisations/{organisation_id}/fidelite/{compte_id}/ventes?page=1&page_size=25`

Retour paginé : identifiants vente/encaissement, numéro du reçu, date, total XAF et mode de vente. Seules les ventes encaissées avec le compte sélectionné sont retournées. Le résultat est borné à l'organisation, au site et aux emplacements où l'utilisateur possède `fidelite.consulter`, avec ordre stable du plus récent au plus ancien. Le reçu d'origine reste consultable par son identifiant selon les permissions de caisse existantes.

## Acceptation ciblée

- Deux ventes affectées au même compte apparaissent dans l'historique et peuvent être paginées.
- Le numéro et l'identifiant du reçu restent ceux de l'encaissement individuel P4.5.
- Une vente sans compte fidélité n'est pas attribuée à un client par inférence.
- L'API n'altère ni vente, ni paiement, ni stock, ni points.
- L'usage monétaire des points demeure bloqué par la règle fiscale non validée.

Test ciblé : `tests/test_caisse.py::test_historique_client_affiche_les_ventes_liees_avec_pagination`.
