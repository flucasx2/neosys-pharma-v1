from datetime import datetime, timedelta, timezone
from hashlib import sha256
from secrets import token_urlsafe, compare_digest
from typing import Protocol
from uuid import UUID

from neosys_pharma.domain.organisation.authentification import IdentiteNonAuthentifiee, SessionAuthentifiee
from neosys_pharma.domain.organisation.securite import Utilisateur


def empreinte(value: str) -> str:
    return sha256(value.encode()).hexdigest()


class AuthRepository(Protocol):
    def utilisateur_login(self, organisation_id: UUID, identifiant: str) -> Utilisateur | None: ...
    def utilisateur(self, identifiant: UUID) -> Utilisateur | None: ...
    def organisation_active(self, identifiant: UUID) -> bool: ...
    def password_hash(self, identifiant: UUID) -> str | None: ...
    def definir_password(self, identifiant: UUID, encoded: str) -> None: ...
    def creer_session(self, session: SessionAuthentifiee, creation: datetime, csrf_hash: str) -> None: ...
    def session(self, hashed: str): ...
    def revoquer(self, hashed: str) -> None: ...
    def revoquer_utilisateur(self, identifiant: UUID) -> None: ...
    def enregistrer(self) -> None: ...


class AuthentificationService:
    def __init__(self, repository: AuthRepository, passwords, duree_minutes=480):
        self.repo, self.passwords, self.duree = repository, passwords, duree_minutes

    def connecter(self, organisation_id: UUID, identifiant: str, password: str, maintenant: datetime):
        utilisateur = self.repo.utilisateur_login(organisation_id, identifiant.strip().lower())
        encoded = self.repo.password_hash(utilisateur.id_utilisateur) if utilisateur else None
        valide = self.passwords.verifier(encoded, password)
        if not utilisateur or not encoded or not valide or not utilisateur.actif or not self.repo.organisation_active(organisation_id):
            raise IdentiteNonAuthentifiee('Identifiants invalides ou compte indisponible.')
        self.repo.definir_password(utilisateur.id_utilisateur, self.passwords.actualiser(encoded, password))
        token, csrf = token_urlsafe(32), token_urlsafe(32)
        session = SessionAuthentifiee(utilisateur_id=utilisateur.id_utilisateur, empreinte=empreinte(token), expiration=maintenant + timedelta(minutes=self.duree))
        self.repo.creer_session(session, maintenant, empreinte(csrf))
        self.repo.enregistrer()
        return utilisateur, token, csrf

    def courant(self, token: str | None, maintenant: datetime, csrf: str | None = None, mutation=False):
        model = self.repo.session(empreinte(token)) if token and len(token) <= 128 else None
        if not model:
            raise IdentiteNonAuthentifiee('Connexion requise.')
        expiration = model.expiration.replace(tzinfo=timezone.utc) if model.expiration.tzinfo is None else model.expiration
        session = SessionAuthentifiee(utilisateur_id=model.utilisateur_id, expiration=expiration, empreinte=model.empreinte)
        utilisateur = self.repo.utilisateur(session.utilisateur_id)
        if not session.valide(maintenant) or not utilisateur or not utilisateur.actif or not self.repo.organisation_active(utilisateur.organisation_id):
            raise IdentiteNonAuthentifiee('Session expirée ou compte indisponible.')
        if mutation and (not csrf or not compare_digest(model.csrf_hash, empreinte(csrf))):
            raise PermissionError('Jeton de protection CSRF absent ou invalide.')
        return utilisateur

    def definir_password(self, utilisateur_id: UUID, password: str):
        if self.repo.utilisateur(utilisateur_id) is None:
            raise LookupError('Utilisateur introuvable.')
        self.repo.definir_password(utilisateur_id, self.passwords.hacher(password))
        self.repo.revoquer_utilisateur(utilisateur_id)
        self.repo.enregistrer()

    def deconnecter(self, token: str):
        self.repo.revoquer(empreinte(token))
        self.repo.enregistrer()
