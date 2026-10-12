# P4.4 — Décisions approuvées et frontières

L’autorisation P4.4 valide l’encaissement sans tiers payant et l’acquisition de points. Le modèle fidélité complète le référentiel UML historique, qui ne décrivait pas encore les comptes et cartes.

- Sessions : une ouverte par caisse ; caissier identifié, fermeture avant relève ; fermeture de session distincte de clôture Z.
- Moyens activables explicitement par organisation : espèces, carte, mobile money, chèque, virement. Aucun moyen actif par défaut.
- Paiement non espèces : référence unique par organisation/mode, justificatif, auteur/date de confirmation. Terminal indépendant confirmé manuellement ; aucun prestataire intégré simulé. Rapprochement append-only en cas de changement de session ou révision de préparation.
- Finalisation : montant net intégralement acquis, rendu uniquement espèces ; transaction commune stock, règlements, mouvements, fidélité, séquence et vente. Crédit et tiers payant restent interdits.
- Deux compteurs indépendants par site/période Z : appel à transmission ; encaissement à finalisation. Largeur minimale quatre caractères, dépassement 9999 autorisé. Aucune remise à zéro à fermeture de session ou changement de date. La vraie clôture Z relève de P4.5.
- Fidélité commune à l’organisation, accessible seulement depuis un site effectivement affecté. Carte physique/virtuelle, opposition/remplacement sans suppression du compte. Téléphone non unique ; choix explicite du titulaire.
- Barèmes indépendants acquisition/conversion, dates inclusives non chevauchantes, catégories explicites, sous-catégories selon option explicite, clôture conservant les valeurs historiques.
- Acquisition : entiers arrondis vers le bas sur TTC éligible payé après remises ; aucune fraction reportée ni taux implicite. Une dette historique éventuelle est compensée avant disponibilité des nouveaux points.
- Utilisation : après remises commerciales, consentement obligatoire, plafonds et possibilité du règlement intégral explicitement configurés. **Toute utilisation reste interdite côté serveur : règle fiscale gabonaise non validée.** Le point d’extension `RegleFiscaleFidelite` ne fournit aucun recalcul HT/TVA inventé.
- P4.5 : journal compensatoire, dette et calcul proportionnel pur préparés ; aucun retour/remboursement ni clôture Z complète implémenté dans cet incrément.

Les règlements externes acquis mais non encore finalisés restent distincts des mouvements de caisse. Les paiements abandonnés doivent être rapprochés par un responsable ; aucun remboursement automatique n’est exécuté.
