"""Catalogue système versionné ; jamais créé librement depuis l'interface."""
from uuid import UUID, uuid5

NAMESPACE = UUID("5e0d5c59-9934-40a6-b798-92d3f544667d")
P1_PERMISSIONS = (
    ("organisation.consulter", "Consulter l'organisation et sa structure"),
    ("organisation.gerer", "Gérer l'organisation et sa structure"),
    ("utilisateur.consulter", "Consulter les utilisateurs"),
    ("utilisateur.gerer", "Gérer les utilisateurs"),
    ("affectation.gerer", "Gérer les affectations et leurs périmètres"),
    ("role.consulter", "Consulter les rôles et permissions"),
    ("role.gerer", "Gérer les rôles personnalisés"),
)
P3_PERMISSIONS = (
    ("stock.consulter", "Consulter stocks et mouvements"),
    ("stock.gerer", "Enregistrer les entrées, sorties et corrections"),
    ("stock.reserver", "Réserver, libérer et consommer le stock"),
    ("stock.transferer", "Demander, expédier et transférer le stock"),
    ("stock.transfert.valider", "Valider ou annuler une demande de transfert"),
    ("stock.transfert.recevoir", "Recevoir un transfert et traiter ses écarts"),
    ("stock.fefo.deroger", "Déroger à FEFO avec justification"),
    ("stock.inventaire.gerer", "Créer les inventaires et affecter les zones"),
    ("stock.inventaire.compter", "Compter les zones explicitement affectées"),
    ("stock.inventaire.valider", "Consulter les écarts et valider les inventaires"),
)
P4_PERMISSIONS = (
    ("proforma.consulter", "Consulter les proformas autorisées et leurs documents"),
    ("proforma.gerer", "Créer et modifier les brouillons de proforma"),
    ("proforma.emettre", "Émettre une version immuable de proforma"),
    ("proforma.reprendre", "Reprendre une proforma en préparation"),
    ("proforma.parametrer", "Paramétrer la validité des proformas du site"),
    ("vente.remise.parametrer", "Configurer les plafonds de remise des rôles"),
    ("vente.consulter", "Consulter les préparations autorisées"),
    ("vente.preparer", "Créer et modifier les préparations"),
    ("vente.valider", "Valider une préparation sans encaissement"),
    ("vente.transmettre", "Transmettre une préparation à une caisse autorisée"),
    ("vente.annuler", "Annuler une préparation et libérer ses réservations"),
    ("vente.credit", "Préparer le mode crédit sans finalisation financière"),
    ("vente.remise.demander", "Demander une remise de ligne ou globale"),
    ("vente.remise.autoriser", "Décider les demandes de remise dans le périmètre autorisé"),
)
CAISSE_PERMISSIONS = (
    ("caisse.consulter", "Consulter sessions, règlements et reçus autorisés"),
    ("caisse.session.gerer", "Ouvrir et fermer sa session de caisse"),
    ("caisse.encaisser", "Finaliser les ventes et consommer leurs réservations"),
    ("caisse.paiement.confirmer", "Confirmer manuellement un paiement non espèces"),
    ("caisse.parametrer", "Activer les moyens de paiement et tickets d'appel"),
    ("fidelite.consulter", "Identifier un titulaire et consulter son compte fidélité"),
    ("fidelite.gerer", "Créer les comptes, remplacer ou opposer les cartes"),
    ("fidelite.parametrer", "Configurer les barèmes historiques de fidélité"),
    ("fidelite.utiliser", "Utiliser des points avec consentement et règle fiscale validée"),
    ("client.consulter", "Consulter les fiches client et leurs organismes associés"),
    ("client.gerer", "Créer et modifier les fiches client et leurs associations"),
)
P5A_PERMISSIONS = (
    ("tiers_payant.consulter", "Consulter conventions, adhésions et priorités de prise en charge"),
    ("tiers_payant.convention.gerer", "Créer et versionner les conventions de prise en charge"),
    ("tiers_payant.adhesion.consulter", "Consulter les bénéficiaires et adhésions de prise en charge"),
    ("tiers_payant.adhesion.gerer", "Gérer les bénéficiaires et adhésions de prise en charge"),
    ("tiers_payant.priorites.gerer", "Configurer et versionner les priorités de prise en charge"),
)
PERMISSIONS = P1_PERMISSIONS + P3_PERMISSIONS + P4_PERMISSIONS + CAISSE_PERMISSIONS + (
    ("catalogue.consulter", "Consulter le catalogue"),
    ("catalogue.gerer", "Gérer le catalogue"),
) + P5A_PERMISSIONS
ROLES = (
    ("OBSERVATEUR", "Observateur", ("organisation.consulter", "utilisateur.consulter", "role.consulter")),
    ("GESTION_ORGANISATION", "Gestion de l'organisation", tuple(code for code, _ in P1_PERMISSIONS)),
)


def permission_id(code: str):
    return uuid5(NAMESPACE, "permission:" + code)


def role_id(code: str):
    return uuid5(NAMESPACE, "role:" + code)

REGULARISATION_PERMISSIONS = (
    ('caisse.cloture.consulter','Consulter les clôtures et états financiers'),
    ('caisse.cloture.x','Produire un état X de caisse'),
    ('caisse.cloture.z','Valider la clôture Z du site'),
    ('caisse.ecart.reconnaitre','Reconnaître et justifier les écarts de caisse'),
    ('caisse.fonds.gerer','Enregistrer les entrées et sorties de fonds justifiées'),
    ('caisse.transfert.demander','Demander un transfert entre caisse et coffre'),
    ('caisse.transfert.autoriser','Autoriser un transfert de fonds'),
    ('caisse.transfert.expedier','Expédier les fonds autorisés'),
    ('caisse.transfert.recevoir','Confirmer la réception des fonds'),
    ('caisse.transfert.deroger','Déroger explicitement à la séparation autorisateur et expéditeur'),
    ('vente.retour.gerer','Enregistrer les retours de ventes encaissées'),
    ('caisse.remboursement.demander','Demander un remboursement ou une restitution'),
    ('caisse.remboursement.autoriser','Autoriser les remboursements justifiés'),
    ('caisse.remboursement.executer','Confirmer les remboursements réellement exécutés'),
    ('caisse.remboursement.substituer','Autoriser un autre moyen de remboursement'),
    ('stock.quarantaine.consulter','Consulter les produits retournés en quarantaine'),
    ('stock.quarantaine.decider','Décider la remise en vente ou le refus sanitaire'),
)
PERMISSIONS += REGULARISATION_PERMISSIONS
