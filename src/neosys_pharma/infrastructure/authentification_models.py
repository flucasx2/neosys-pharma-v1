from datetime import datetime
from uuid import UUID
from sqlalchemy import ForeignKey, String, DateTime, CheckConstraint
from sqlalchemy.orm import Mapped, mapped_column
from neosys_pharma.infrastructure.database import Base


class CredentialModel(Base):
    __tablename__ = 'auth_credentials'
    utilisateur_id: Mapped[UUID] = mapped_column(ForeignKey('utilisateurs.id_utilisateur'), primary_key=True)
    password_hash: Mapped[str] = mapped_column(String(512))


class SessionModel(Base):
    __tablename__ = 'auth_sessions'
    __table_args__ = (CheckConstraint('expiration > creation', name='ck_session_expiration'),)
    empreinte: Mapped[str] = mapped_column(String(64), primary_key=True)
    utilisateur_id: Mapped[UUID] = mapped_column(ForeignKey('utilisateurs.id_utilisateur'), index=True)
    creation: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    expiration: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    csrf_hash: Mapped[str] = mapped_column(String(64))


class TentativeConnexionModel(Base):
    __tablename__ = 'auth_tentatives'
    cle: Mapped[str] = mapped_column(String(64), primary_key=True)
    nombre: Mapped[int]
    debut: Mapped[datetime] = mapped_column(DateTime(timezone=True))
