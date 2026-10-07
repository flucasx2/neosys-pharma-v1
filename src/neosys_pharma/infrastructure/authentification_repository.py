from datetime import timezone
from sqlalchemy import select, delete
from sqlalchemy.exc import IntegrityError
from neosys_pharma.infrastructure.authentification_models import CredentialModel, SessionModel, TentativeConnexionModel
from neosys_pharma.infrastructure.securite_models import UtilisateurModel
from neosys_pharma.infrastructure.securite_repository import SqlAlchemySecuriteRepository
from neosys_pharma.domain.organisation.securite import Utilisateur


class SqlAlchemyAuthRepository:
    def __init__(self, session):
        self.db = session
        self.securite = SqlAlchemySecuriteRepository(session)

    def utilisateur(self, identifiant):
        return self.securite.utilisateur(identifiant)

    def utilisateur_login(self, organisation_id, identifiant):
        model = self.db.scalar(select(UtilisateurModel).filter_by(organisation_id=organisation_id, identifiant=identifiant))
        return self.securite.entite(Utilisateur, model) if model else None

    def organisation_active(self, identifiant):
        org = self.securite.organisation(identifiant)
        return bool(org and org.actif)

    def password_hash(self, identifiant):
        model = self.db.get(CredentialModel, identifiant)
        return model.password_hash if model else None

    def definir_password(self, identifiant, encoded):
        model = self.db.get(CredentialModel, identifiant)
        if model:
            model.password_hash = encoded
        else:
            self.db.add(CredentialModel(utilisateur_id=identifiant, password_hash=encoded))

    def creer_session(self, session, creation, csrf_hash):
        self.db.add(SessionModel(empreinte=session.empreinte, utilisateur_id=session.utilisateur_id, creation=creation, expiration=session.expiration, csrf_hash=csrf_hash))

    def session(self, hashed):
        return self.db.get(SessionModel, hashed)

    def revoquer(self, hashed):
        self.db.execute(delete(SessionModel).where(SessionModel.empreinte == hashed))

    def revoquer_utilisateur(self, identifiant):
        self.db.execute(delete(SessionModel).where(SessionModel.utilisateur_id == identifiant))

    def tentative(self, cle, maintenant, maximum=10, fenetre=300):
        # Shared DB counter; SELECT FOR UPDATE serializes existing buckets on PostgreSQL.
        bucket = self.db.scalar(select(TentativeConnexionModel).where(TentativeConnexionModel.cle == cle).with_for_update())
        if bucket:
            debut = bucket.debut.replace(tzinfo=timezone.utc) if bucket.debut.tzinfo is None else bucket.debut
            if (maintenant - debut).total_seconds() >= fenetre:
                bucket.debut, bucket.nombre = maintenant, 0
            if bucket.nombre >= maximum:
                self.db.rollback()
                return False
            bucket.nombre += 1
        else:
            bucket = TentativeConnexionModel(cle=cle, debut=maintenant, nombre=1)
            self.db.add(bucket)
        try:
            self.db.commit()
        except IntegrityError:
            # Concurrent creation of the same bucket: retry against the winning row.
            self.db.rollback()
            return self.tentative(cle, maintenant, maximum, fenetre)
        return True

    def enregistrer(self):
        self.db.commit()
