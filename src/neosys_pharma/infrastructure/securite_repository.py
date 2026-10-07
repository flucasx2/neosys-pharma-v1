from dataclasses import asdict, fields
from uuid import UUID

from sqlalchemy import delete, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from neosys_pharma.domain.organisation.permissions_systeme import PERMISSIONS, ROLES, permission_id, role_id
from neosys_pharma.domain.organisation.securite import (
    AffectationEmplacement, AffectationRole, AffectationSite, Permission, Role, RolePermission, Utilisateur,
)
from neosys_pharma.infrastructure.organisation_repository import SqlAlchemyOrganisationRepository
from neosys_pharma.infrastructure.securite_models import (
    AffectationEmplacementModel, AffectationRoleModel, AffectationSiteModel, PermissionModel,
    RoleModel, RolePermissionModel, UtilisateurModel,
)

MAPPINGS = {Utilisateur: UtilisateurModel, AffectationSite: AffectationSiteModel,
            Role: RoleModel, Permission: PermissionModel, AffectationEmplacement: AffectationEmplacementModel,
            AffectationRole: AffectationRoleModel, RolePermission: RolePermissionModel}


class SqlAlchemySecuriteRepository:
    def __init__(self, session: Session):
        self.session = session
        self.parents = SqlAlchemyOrganisationRepository(session)

    def organisation(self, identifiant):
        return self.parents.organisation(identifiant)

    def site(self, identifiant):
        return self.parents.site(identifiant)

    def emplacement(self, identifiant):
        return self.parents.emplacement(identifiant)

    @staticmethod
    def entite(classe, model):
        return classe(**{f.name: getattr(model, f.name) for f in fields(classe)})

    def trouver(self, classe, identifiant):
        model = self.session.get(MAPPINGS[classe], identifiant)
        return self.entite(classe, model) if model is not None else None

    def utilisateur(self, identifiant):
        return self.trouver(Utilisateur, identifiant)

    def affectation(self, identifiant):
        return self.trouver(AffectationSite, identifiant)

    def role(self, identifiant):
        return self.trouver(Role, identifiant)

    def permission(self, identifiant):
        return self.trouver(Permission, identifiant)

    def lister(self, classe, **filtres):
        models = self.session.scalars(select(MAPPINGS[classe]).filter_by(**filtres))
        return [self.entite(classe, model) for model in models]

    def utilisateurs(self, organisation_id):
        return self.lister(Utilisateur, organisation_id=organisation_id)

    def roles(self, organisation_id):
        requete = select(RoleModel).where(or_(RoleModel.organisation_id == organisation_id, RoleModel.organisation_id.is_(None))).order_by(RoleModel.code)
        return [self.entite(Role, model) for model in self.session.scalars(requete)]

    def permissions(self):
        return sorted(self.lister(Permission), key=lambda permission: permission.code)

    def affectations(self, utilisateur_id):
        return self.lister(AffectationSite, utilisateur_id=utilisateur_id)

    def roles_affectation(self, identifiant):
        liens = self.lister(AffectationRole, affectation_site_id=identifiant)
        return [self.role(lien.role_id) for lien in liens]

    def emplacements_affectation(self, identifiant):
        liens = self.lister(AffectationEmplacement, affectation_site_id=identifiant)
        return [self.emplacement(lien.emplacement_id) for lien in liens]

    def permissions_role(self, identifiant):
        liens = self.lister(RolePermission, role_id=identifiant)
        return [self.permission(lien.permission_id) for lien in liens]

    def ajouter(self, entite):
        valeurs = asdict(entite)
        if isinstance(entite, AffectationSite):
            valeurs["organisation_id"] = self.utilisateur(entite.utilisateur_id).organisation_id
        elif isinstance(entite, AffectationEmplacement):
            valeurs["site_id"] = self.affectation(entite.affectation_site_id).site_id
        elif isinstance(entite, AffectationRole):
            affectation = self.session.get(AffectationSiteModel, entite.affectation_site_id)
            role = self.session.get(RoleModel, entite.role_id)
            valeurs.update(organisation_id=affectation.organisation_id, role_scope=role.scope_id)
        self.session.add(MAPPINGS[type(entite)](**valeurs))
        self.flush()

    def flush(self):
        try:
            self.session.flush()
        except IntegrityError as exc:
            self.session.rollback()
            raise ValueError("Doublon ou rattachement de sécurité incohérent.") from exc

    def enregistrer(self):
        try:
            self.session.commit()
        except IntegrityError as exc:
            self.session.rollback()
            raise ValueError("Enregistrement de sécurité impossible.") from exc

    def mettre_a_jour(self, entite):
        cle = {Utilisateur: "id_utilisateur", AffectationSite: "id_affectation_site", Role: "id_role"}[type(entite)]
        model = self.session.get(MAPPINGS[type(entite)], getattr(entite, cle))
        for nom, valeur in asdict(entite).items():
            if nom != cle:
                setattr(model, nom, valeur)
        self.flush()

    def remplacer_liens(self, classe, parent_champ, parent_id, liens):
        model = MAPPINGS[classe]
        self.session.execute(delete(model).where(getattr(model, parent_champ) == parent_id))
        for lien in liens:
            self.ajouter(lien)


def installer_catalogue_systeme(session: Session) -> None:
    """Fixture de test : même catalogue que la migration, aucun bootstrap d'accès."""
    repo = SqlAlchemySecuriteRepository(session)
    for code, nom in PERMISSIONS:
        repo.ajouter(Permission(code=code, nom=nom, id_permission=permission_id(code)))
    for code, nom, permissions in ROLES:
        repo.ajouter(Role(code=code, nom=nom, type_role="SYSTEME", id_role=role_id(code)))
        for permission in permissions:
            repo.ajouter(RolePermission(role_id=role_id(code), permission_id=permission_id(permission)))
    repo.enregistrer()
