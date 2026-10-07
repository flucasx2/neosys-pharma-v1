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
PERMISSIONS = P1_PERMISSIONS + (
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
