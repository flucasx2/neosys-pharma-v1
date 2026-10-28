"""Créances financières et versions administratives append-only."""
from datetime import datetime
from uuid import UUID
from sqlalchemy import CheckConstraint, ForeignKeyConstraint, Integer, JSON, String, Uuid, DateTime, UniqueConstraint, event, DDL
from sqlalchemy.orm import Mapped, mapped_column
from neosys_pharma.infrastructure.database import Base
from neosys_pharma.infrastructure.vente_models import EntiteVente
from neosys_pharma.infrastructure.caisse_models import scoped, org_fk, now, immutable_sql


class CreanceOrganismeModel(EntiteVente, Base):
    __tablename__='tiers_payant_creances'
    __table_args__=scoped('tp_creance',
        ForeignKeyConstraint(['realisation_id','vente_id','organisation_id','site_id'], ['tiers_payant_realisations.id','tiers_payant_realisations.vente_id','tiers_payant_realisations.organisation_id','tiers_payant_realisations.site_id'],name='fk_tp_creance_realisation_scope'),
        org_fk('organisme_id','organismes_prise_en_charge'), org_fk('auteur_id','utilisateurs','id_utilisateur'),
        UniqueConstraint('realisation_id','organisme_id',name='uq_tp_creance_source'),
        CheckConstraint('montant_xaf > 0',name='ck_tp_creance_montant'),
        CheckConstraint('length(snapshot_hash) = 64',name='ck_tp_creance_hash'))
    realisation_id:Mapped[UUID]=mapped_column(Uuid,index=True)
    vente_id:Mapped[UUID]=mapped_column(Uuid,index=True)
    site_id:Mapped[UUID]=mapped_column(Uuid,index=True)
    organisme_id:Mapped[UUID]=mapped_column(Uuid,index=True)
    montant_xaf:Mapped[int]=mapped_column(Integer)
    snapshot:Mapped[dict]=mapped_column(JSON)
    snapshot_hash:Mapped[str]=mapped_column(String(64))
    exigences:Mapped[list]=mapped_column(JSON)
    auteur_id:Mapped[UUID]=mapped_column(Uuid)
    cree_le:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=now)


class VersionDossierCreanceModel(EntiteVente, Base):
    __tablename__='tiers_payant_creances_versions'
    __table_args__=scoped('tp_creance_version',org_fk('creance_id','tiers_payant_creances'),org_fk('auteur_id','utilisateurs','id_utilisateur'),
        UniqueConstraint('creance_id','revision',name='uq_tp_creance_revision'),CheckConstraint('revision > 0',name='ck_tp_creance_revision'),
        CheckConstraint("etat IN ('A_COMPLETER','A_CONTROLER','VALIDE_POUR_FACTURATION','EN_ANOMALIE','FACTURE')",name='ck_tp_creance_etat'))
    creance_id:Mapped[UUID]=mapped_column(Uuid,index=True)
    revision:Mapped[int]=mapped_column(Integer)
    etat:Mapped[str]=mapped_column(String(30))
    complements:Mapped[dict]=mapped_column(JSON)
    anomalies:Mapped[list]=mapped_column(JSON)
    motif:Mapped[str]=mapped_column(String(2000))
    auteur_id:Mapped[UUID]=mapped_column(Uuid)
    cree_le:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=now)


class CompensationCreanceOrganismeModel(EntiteVente, Base):
    """Écritures append-only reliant une créance à un retour P4 déterminé."""
    __tablename__='tiers_payant_compensations_creances'
    __table_args__=scoped('tp_compensation_creance',
        org_fk('creance_id','tiers_payant_creances'),
        org_fk('retour_id','vente_retours'),
        org_fk('auteur_id','utilisateurs','id_utilisateur'),
        UniqueConstraint('creance_id','retour_id',name='uq_tp_compensation_creance_retour'),
        CheckConstraint('montant_xaf > 0',name='ck_tp_compensation_creance_montant'),
        CheckConstraint('length(snapshot_hash) = 64',name='ck_tp_compensation_creance_hash'))
    creance_id:Mapped[UUID]=mapped_column(Uuid,index=True)
    retour_id:Mapped[UUID]=mapped_column(Uuid,index=True)
    montant_xaf:Mapped[int]=mapped_column(Integer)
    snapshot:Mapped[dict]=mapped_column(JSON)
    snapshot_hash:Mapped[str]=mapped_column(String(64))
    motif:Mapped[str]=mapped_column(String(2000))
    auteur_id:Mapped[UUID]=mapped_column(Uuid)
    cree_le:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=now)


for model in (CreanceOrganismeModel,VersionDossierCreanceModel,CompensationCreanceOrganismeModel):
    for dialect in ('sqlite','postgresql'):
        for sql in immutable_sql(model.__tablename__,dialect):
            event.listen(model.__table__,'after_create',DDL(sql).execute_if(dialect=dialect))
