# Registre — recette suspendue, mise en conformité P5

Date : 18 octobre 2026. Base locale 5ad489c. Les observations de la mission sont conservées; seules les preuves exécutées ci-dessous permettent de qualifier le sous-lot.

| ID | Module / priorité | Constat et dépendances | État après P5-CONF.1a |
|---|---|---|---|
| NC-P5-01 | Administration / haute | Organismes accessibles seulement depuis une fiche client | Écran autonome et API implémentés; tests HTTP et DOM réussis. Chromium/PostgreSQL/recette humaine en attente. Non clos métier. |
| NC-P5-02 | Référentiel / haute | Régimes, conventions, barèmes, seuils, plafonds et périodes administrables | Conventions et règles explicites P5-A/B réutilisables. Interface et concepts manquants ouverts; pas de calcul contractuel inventé. |
| NC-P5-03 | Droits / haute | Modes liste/externe/mixte, champs typés et contrôles de format | Patch préparatoire inspecté, non intégré. Import Excel/CSV et validation de valeurs restent ouverts. |
| NC-P5-04 | Adhésions / haute | Titulaire/ayant droit, dates, régimes, plafonds individuels et encours | Bénéficiaires/adhésions P5-A existants conservés. Interface et plafonds/cumuls restent ouverts selon contrats. |
| NC-P5-05 | Justificatifs / haute | Exigences simples/cumulatives/alternatives et référence de vérification humaine | Aucune saisie ne confirme automatiquement les droits. Configuration et enregistrement des preuves à raccorder à la vente. Aucun secret de portail stocké. |
| NC-P5-06 | Facturation / haute | Continuité des documents, versions et parts vers P5-C | Snapshots financiers existants conservés; dossier documentaire et créances/factures restent à traiter dans les lots autorisés. |
| OBS-CAT-01 | Catalogue / haute | Import PharmaGabon terminé, produits non retrouvés | Signalé, non reproduit ici; vérifier filtres/périmètres et rapport d'import avant correction. |
| OBS-ORG-01 | Structure / normale | Modifier l'intitulé d'une caisse | Signalé, reporté; préserver ses références historiques. |
| OBS-CAI-01 | Caisse / haute | Paramétrage autonome Airtel Money, Moov Money et autres moyens | Signalé, reporté; dépend des moyens autorisés et confirmations existants. |
| OBS-CAI-02 | Caisse / haute | Rendu automatique | Signalé, reporté; espèces uniquement, contrôles financiers à préserver. |
| OBS-CAI-03 | Caisse / haute | Simplifier encaissement groupé | Signalé, reporté; ne pas modifier l'orchestration financière ni activer le flag. |
| OBS-FID-01 | Fidélité / normale | Identifiant carte virtuelle automatique | Signalé, reporté; unicité et idempotence à préserver. |
| OBS-FID-02 | Fidélité / normale | Carte physique par numéro/code-barres | Signalé, reporté; format/symbologie à confirmer selon référentiel. |
| OBS-UI-01 | Présentation / normale | Retirer les mentions de phases | Le nouvel écran n'en contient pas; nettoyage des autres écrans reporté. |
| OBS-VENTE-01 | Vente / haute | Libellés de modes génériques | Signalé, reporté; compatibilité des valeurs et historiques à préserver. |
| OBS-FAC-01 | P5-C / haute | Informations de facturation par organisme | À traiter avec NC-P5-06; ne pas développer la facturation dans ce sous-lot. |

Les priorités sont un ordre de traitement technique proposé, pas une nouvelle règle métier. Aucune observation hors périmètre n'a été corrigée sans reproduction. La suspension de la recette humaine générale du 18/10 reste effective; la recette ciblée ci-jointe est une procédure à exécuter après préparation autorisée de l'environnement.


## Mise à jour du 19 octobre 2026 — P5-CONF.1b

Les lignes précédentes décrivent la livraison du 18/10. La mission actuelle confirme l'acceptation P5-CONF.1a, réserve ergonomique maintenue. Les résultats Windows sont rapportés par le responsable ; ils ne sont pas présentés comme exécutés dans Work.

| ID | Reproduction / cause | Gravité / module | État, correction et preuve |
|---|---|---|---|
| NC-P5-01 | Administration autonome reçue et acceptée en recette précédente | Haute / organismes | Accepté avec réserve OBS-P5-UI-01 selon décision du 19/10. Code accepté réutilisé |
| OBS-P5-UI-01 | Messages de confirmation redondants ou persistants pendant la recette | Normale / UI | Ouvert, non bloquant, pas de correction de l'écran accepté dans ce lot |
| NC-P5-02 | API de conventions sans administration complète | Haute / conventions | Conventions/régimes embarqués/barèmes par ligne administrables ; tests ciblés. Plafonds périodiques, majorations et montants fixes ouverts ; recette réelle non exécutée |
| NC-P5-03 | Champs et modes de vérification non raccordés | Haute / droits | Schéma strict et preuves manuelles LISTE/IDENTIFICATION/EXTERNE/MIXTE implémentés et testés ; imports non livrés |
| NC-P5-04 | Bénéficiaires/adhésions sans écrans ni plafonds individuels | Haute / adhésions | Recherche/création/adhésion/décision sur droits réutilisent P5-A ; plafonds consommables et édition d'identité restent ouverts |
| NC-P5-05 | Pièces absentes ou preuve d'une autre vente pourraient être réutilisées | Haute / vérification | Preuve par vente/bénéficiaire/révision, champs/alternatives/périodes contrôlés, refus explicites ; tests API et DOM. Native/recette humaine requises avant clôture |
| P5-FAC-01 / NC-P5-06 | Continuité documentaire vers P5-C | Haute / snapshots | Métadonnées, identité/régime, pièces/références/auteur et données historiques de lignes figées dans le snapshot ; aucun document binaire ni facture. Couverture partielle, non clos globalement |
| CONF-INT-01 | Enrichissement du snapshot utilisait un attribut `ProduitModel.designation` absent : test de simulation en erreur | Bloquante / projection nouvelle | Corrigé par `LigneVenteModel.designation`, valeur historique ; test de confirmation avec dossier documentaire |
| CONF-UI-01 | Recherche catalogue utilisait `designation` au lieu du contrat réel `nom` | Haute / sélecteurs | Corrigé ; assertion DOM sur le nom de produit reçu de l'API |
| CONF-UI-02 | Choix du bénéficiaire non explicitement renseigné dans le nouveau formulaire | Haute / preuve | Option initiale vide obligatoire, résultat également explicite ; tests DOM et validation UUID serveur |
| CONF-INT-02 | La création P5-A d'adhésion ne vérifiait pas le statut de l'organisme | Haute / adhésions | Contrôle serveur ajouté et test dédié ; historiques préservés |
| CONF-ENV-01 | Binaire Python 3.14 préexistant termine par Bus error avant tests | Environnement / Work | Installation séparée de CPython 3.14.8 fonctionnelle ; aucun fichier applicatif modifié pour contourner |
| CONF-ENV-02 | Binaires PostgreSQL 16.2 exécutables, mais création d'un cluster sous utilisateur non privilégié impossible : chown invalide et runuser cannot set groups | Bloquante pour preuve native / environnement | Aucun serveur ni base de tests PostgreSQL démarré ; script Windows gardé et test natif fournis, non exécutés. PostgreSQL 18.6 cible non vérifié |
| CONF-ENV-03 | Téléchargement Chromium : archive tronquée, puis exécutable absent | Bloquante pour navigateur / environnement | Test préparé sur origine localhost sécurisée ; aucun scénario Chromium exécuté |
| CONF-LIM-01 | Certains sélecteurs limités aux 100 premières références ; preuve demandant identifiant de vente | Normale / ergonomie | Ouvert avant généralisation aux gros référentiels ; listes principales paginées ; limites signalées dans la documentation |

Les autres observations catalogue, caisse, encaissement groupé et fidélité restent ouvertes comme précédemment. Aucun succès DOM ou SQLite n'est une clôture métier ou une preuve de concurrence PostgreSQL.
