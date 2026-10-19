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
