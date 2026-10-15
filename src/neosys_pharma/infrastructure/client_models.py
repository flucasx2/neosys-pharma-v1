"""Profils client et organismes de prise en charge, sans calcul de parts P5."""
from uuid import UUID
from sqlalchemy import Boolean, CheckConstraint, ForeignKey, ForeignKeyConstraint, Index, String, UniqueConstraint, Uuid, text
from sqlalchemy.orm import Mapped, mapped_column

from neosys_pharma.infrastructure.database import Base
from neosys_pharma.infrastructure.vente_models import EntiteVente


class ClientModel(EntiteVente, Base):
    __tablename__ = 'clients'
    __table_args__ = (UniqueConstraint('id', 'organisation_id', name='uq_client_org'), CheckConstraint('revision > 0'))
    nom: Mapped[str] = mapped_column(String(200))
    telephone: Mapped[str | None] = mapped_column(String(80), index=True)
    courriel: Mapped[str | None] = mapped_column(String(254))
    actif: Mapped[bool] = mapped_column(Boolean, default=True)
    revision: Mapped[int] = mapped_column(default=1)


class OrganismePriseEnChargeModel(EntiteVente, Base):
    __tablename__ = 'organismes_prise_en_charge'
    __table_args__ = (UniqueConstraint('id', 'organisation_id', name='uq_organisme_couverture_org'), UniqueConstraint('organisation_id', 'code'), CheckConstraint('revision > 0'))
    code: Mapped[str] = mapped_column(String(80))
    nom: Mapped[str] = mapped_column(String(200))
    actif: Mapped[bool] = mapped_column(Boolean, default=True)
    revision: Mapped[int] = mapped_column(default=1)


class ClientOrganismeModel(EntiteVente, Base):
    __tablename__ = 'clients_organismes_prise_en_charge'
    __table_args__ = (
        UniqueConstraint('client_id', 'organisme_id', name='uq_client_organisme'),
        ForeignKeyConstraint(['client_id','organisation_id'],['clients.id','clients.organisation_id'],name='fk_client_organisme_client_org'),
        ForeignKeyConstraint(['organisme_id','organisation_id'],['organismes_prise_en_charge.id','organismes_prise_en_charge.organisation_id'],name='fk_client_organisme_organisme_org'),
        CheckConstraint("role IN ('PRINCIPAL','COMPLEMENTAIRE')", name='ck_client_organisme_role'),
        Index('uq_client_organisme_principal', 'client_id', unique=True, sqlite_where=text("role='PRINCIPAL' AND actif=1"), postgresql_where=text("role='PRINCIPAL' AND actif=true")),
    )
    client_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    organisme_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    role: Mapped[str] = mapped_column(String(20))
    reference: Mapped[str | None] = mapped_column(String(200))
    actif: Mapped[bool] = mapped_column(Boolean, default=True)
