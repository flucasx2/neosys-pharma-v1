# Incrément 03 — moyens de paiement configurables

Base vérifiée : ef1256bfe350fdc3bfde693b4f2f35dab08ab935, après ed208094 et P5-CONF.1b 1cc86cee. Branche work/p4-p5-consolidation propre avant travaux. Le bundle de NeoSys_P4_P5_Consolidation_01_02.zip est identique au bundle local, vérifié avec git bundle verify. Aucun patch alternatif appliqué.

## Fonctionnel livré

- Catalogue de moyens par organisation, code stable, famille financière, libellé, statut actif et révision ; création/modification sous caisse.parametrer, audit et idempotence. Aucune permission attribuée implicitement. Le code/famille n'est pas modifiable par l'API.
- Airtel Money et Moov Money sont deux exemples configurables, pas des noms codés en dur dans le calcul. Les familles P4 restent inchangées ; espèces conserve son circuit existant.
- Chaque confirmation peut désigner un moyen. L'identité et son libellé au moment de confirmation sont immuables ; les règlements individuels/groupés le retrouvent via la confirmation. Aucun règlement ou mouvement dupliqué.
- Dès qu'une famille possède un catalogue configuré, les nouvelles confirmations doivent choisir explicitement un fournisseur actif ; désactiver tous les fournisseurs ne réactive pas un mobile générique. Les confirmations historiques sans fournisseur restent lisibles.
- Les reçus individuels/collectifs, X/Z et remboursements distinguent les fournisseurs. Les totaux par famille historiques restent disponibles, avec une ventilation additionnelle nets_par_moyen réconciliée sur les mêmes écritures.
- Les remboursements réservent le disponible par identité et famille ; passer d'Airtel à Moov exige la permission de substitution et la justification P4.5. Le montant d'une vente reste plafonné à ses règlements/allocations. Les anciens remboursements JSON restent compatibles.
- Défaut reproduit dans le formulaire cloné : la valeur sélectionnée d'un select était perdue au clonage et pouvait proposer des espèces au lieu du fournisseur d'origine. defaultSelected est maintenant fixé ; assertion DOM dédiée.
- Défaut de lecteur reproduit par le cas groupé : /retours/{id}/solde ignorait les allocations groupées. Il utilise désormais le même calcul de disponible que le service de remboursement.

L'interface réutilise les écrans Caisse et Régularisations. « Fournisseurs de paiement » permet la gestion. La confirmation non espèces et les lignes groupées distinguent les fournisseurs ; l'interface de remboursement conserve les origines indépendantes.

## Contrats et persistance

POST /api/caisses/organisations/{org}/moyens : cle, code, mode non espèces, libelle, actif.
PUT .../moyens/{id} : cle, revision, libelle, actif. Consultation via /contexte.configuration.moyens.
POST .../ventes/{id}/confirmations : champ facultatif moyen_id, exigé pour une famille configurée. Les règlements ne portent pas de second fournisseur contradictoire : confirmation_id fait foi.
Remboursement : moyen_id cible et moyen_origine_id source, tous deux explicites pour un fournisseur ; null conserve l'origine générique historique. disponible_par_moyen complète disponible_par_mode.

Migration additive 20261019_02 après 20261019_01 : caisse_moyens_paiement ; moyen_id et moyen_libelle facultatifs dans caisse_confirmations, FK composite (id, organisation, famille), cohérence présence libellé/identité. Les CHECK historiques sont conservés explicitement lors du batch SQLite. Les confirmations antérieures restent null, aucune réaffectation présumée. Downgrade refusé si le catalogue n'est pas vide. Aucune migration historique réécrite ou base conservée touchée.

Protection conservée : l'unicité historique de référence (organisation, famille, référence) n'est PAS élargie aux fournisseurs. Une même référence saisie sur deux fournisseurs mobiles reste refusée explicitement ; si les prestataires émettent réellement des références identiques, une évolution de cette règle devra être validée et migrée avec protection des confirmations historiques non qualifiées. Il n'y a pas de connecteur prestataire.

## Résultats réels

CPython 3.14.8, données SQLite fictives isolées :

```sh
TZ=Africa/Libreville PYTHONPATH=src:tests:<site-packages-3.14> python3.14 -m pytest -q tests/test_moyens_paiement.py tests/test_caisse.py tests/test_regularisation.py -k 'moyens or encaissement_mixte_atomique or retours_partiels_cumulatifs or x_z_annulation or paiement_acquis_restitution'
```

**12 passed, 66 deselected, 1 warning — 31.53 s.** Quatre nouveaux cas : identités/révisions/permissions, deux fournisseurs avec remboursement et X/Z, groupe avec allocations et refus d'inactif, FK organisation/famille. Les tests prouvent aussi conservation du libellé historique, PDF inchangé, rejeu du remboursement et absence d'encaissement partiel après refus.

Migration après correction de préservation des CHECK : **1 passed, 1 skipped — 3.42 s** (tests/test_consolidation_migrations.py). Cycle Alembic montant/descendant, données organisme P4-B fictives conservées, schéma sans drift, FK et refus conservateur du downgrade. Le skip est PostgreSQL natif, pas un succès.

Régressions complémentaires pendant le développement : 9 passed, 4 skipped, 23 deselected (77.78 s), comprenant groupe avec organismes, finitions, retours et X/Z ; cette sélection chevauche les contrôles ci-dessus et n'est pas additionnée comme des tests uniques. La première version de migration produisait un avertissement sur les CHECK anonymes : corrigé par leur préservation explicite et une assertion de conservation des expressions.

DOM final : 7 assertions fournisseurs + 19 groupe + 10 formulaires, HTML/JS applicatifs, HTTP/hôte de modale simulés. Le scénario fournisseur a d'abord échoué sur la sélection clonée puis réussi après correction. node --check réussi sur les trois modules modifiés.

PostgreSQL natif, Chromium et PowerShell non exécutés, limitations d'environnement déjà établies. Les lanceurs préparent seulement des bases neuves marquées, sans suppression automatique : recette_p4p5_postgresql.ps1 inclut désormais les quatre cas fournisseurs (13 tests attendus au total), recette_consolidation_migrations.ps1 cible le contrôle Alembic natif séparément. Exécution avec les mêmes paramètres explicites serveur/port/utilisateur/base et -CreerBaseJetable après inspection ; préfixe neosys_consolidation_migrations_* pour ce dernier. Ne pas confondre create_all des fixtures API avec validation Alembic.

Aucune publication ni activation. GROUPED_ENCASHMENT_ENABLED reste fermé par défaut. Validation partielle ; le lot est implémenté, pas accepté en natif ou en recette humaine.
