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
    ("vente.consulter", "Consulter les préparations autorisées"),
    ("vente.preparer", "Créer et modifier les préparations"),
    ("vente.valider", "Valider une préparation sans encaissement"),
    ("vente.transmettre", "Transmettre une préparation à une caisse autorisée"),
    ("vente.annuler", "Annuler une préparation et libérer ses réservations"),
    ("vente.credit", "Préparer le mode crédit sans finalisation financière"),
    ("vente.remise.demander", "Demander une remise de ligne ou globale"),
    ("vente.remise.autoriser", "Décider les demandes de remise dans le périmètre autorisé"),
)
PERMISSIONS = P1_PERMISSIONS + P3_PERMISSIONS + P4_PERMISSIONS + (
    ("catalogue.consulter", "Consulter le catalogue"),
    ("catalogue.gerer", "Gérer le catalogue"),
)
ROLES = (
    ("OBSERVATEUR", "Observateur", ("organisation.consulter", "utilisateur.consulter", "role.consulter")),
    ("GESTION_ORGANISATION", "Gestion de l'organisation", tuple(code for code, _ in P1_PERMISSIONS)),
)


def permission_id(code: str):
    return uuid5(NAMESPACE, "permission:" + code)


def role_id(code: str):
    return uuid5(NAMESPACE, "role:" + code)
