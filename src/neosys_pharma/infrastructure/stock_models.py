"""P3 : FK de périmètre, quantités entières, journal append-only et états explicites."""
from datetime import date, datetime, timezone
from uuid import UUID, uuid4
from sqlalchemy import BigInteger, DDL, event, CheckConstraint, DateTime, ForeignKey, ForeignKeyConstraint, JSON, String, UniqueConstraint, Uuid
from sqlalchemy.orm import Mapped, mapped_column
from neosys_pharma.infrastructure.database import Base


def now(): return datetime.now(timezone.utc)

class OrgEntity:
    id: Mapped[UUID] = mapped_column(Uuid,primary_key=True,default=uuid4)
    organisation_id: Mapped[UUID] = mapped_column(ForeignKey('organisations.id_organisation'),index=True)

class LotModel(OrgEntity,Base):
    __tablename__='stock_lots'
    __table_args__=(UniqueConstraint('id','organisation_id',name='uq_stock_lot_org'),UniqueConstraint('conditionnement_id','cle',name='uq_stock_lot_cle'),ForeignKeyConstraint(['conditionnement_id','organisation_id'],['catalogue_conditionnements.id_conditionnement','catalogue_conditionnements.organisation_id'],name='fk_stock_lot_conditionnement'))
    conditionnement_id: Mapped[UUID] = mapped_column(Uuid,index=True)
    numero: Mapped[str | None] = mapped_column(String(100))
    cle: Mapped[str] = mapped_column(String(110))
    peremption: Mapped[date | None]
    auteur_id: Mapped[UUID] = mapped_column(ForeignKey('utilisateurs.id_utilisateur'))
    cree_le: Mapped[datetime] = mapped_column(DateTime(timezone=True),default=now)

class StockEmplacementModel(OrgEntity,Base):
    __tablename__='stock_emplacements'
    __table_args__=(UniqueConstraint('id','organisation_id',name='uq_stock_balance_org'),UniqueConstraint('lot_id','emplacement_id',name='uq_stock_balance_lot_loc'),ForeignKeyConstraint(['lot_id','organisation_id'],['stock_lots.id','stock_lots.organisation_id'],name='fk_stock_balance_lot'),ForeignKeyConstraint(['site_id','organisation_id'],['sites.id_site','sites.organisation_id'],name='fk_stock_balance_site'),ForeignKeyConstraint(['emplacement_id','site_id'],['emplacements.id_emplacement','emplacements.site_id'],name='fk_stock_balance_location'),CheckConstraint('physique >= reserve AND reserve >= 0',name='ck_stock_quantites'))
    lot_id: Mapped[UUID] = mapped_column(Uuid,index=True)
    site_id: Mapped[UUID] = mapped_column(Uuid,index=True)
    emplacement_id: Mapped[UUID] = mapped_column(Uuid,index=True)
    physique: Mapped[int] = mapped_column(BigInteger,default=0)
    reserve: Mapped[int] = mapped_column(BigInteger,default=0)

class MouvementStockModel(OrgEntity,Base):
    __tablename__='stock_mouvements'
    __table_args__=(UniqueConstraint('organisation_id','sequence',name='uq_stock_mouvement_sequence'),ForeignKeyConstraint(['stock_id','organisation_id'],['stock_emplacements.id','stock_emplacements.organisation_id'],name='fk_stock_mouvement_balance'),CheckConstraint('delta_physique <> 0 OR delta_reserve <> 0',name='ck_stock_mouvement_delta'))
    stock_id: Mapped[UUID] = mapped_column(Uuid,index=True)
    sequence: Mapped[int] = mapped_column(BigInteger)
    type: Mapped[str] = mapped_column(String(40))
    delta_physique: Mapped[int] = mapped_column(BigInteger)
    delta_reserve: Mapped[int] = mapped_column(BigInteger)
    physique_apres: Mapped[int] = mapped_column(BigInteger)
    reserve_apres: Mapped[int] = mapped_column(BigInteger)
    origine: Mapped[str] = mapped_column(String(200))
    operation_id: Mapped[UUID] = mapped_column(Uuid,index=True)
    auteur_id: Mapped[UUID] = mapped_column(ForeignKey('utilisateurs.id_utilisateur'))
    date: Mapped[datetime] = mapped_column(DateTime(timezone=True),default=now)
    justification: Mapped[str | None] = mapped_column(String(2000))

class ReservationStockModel(OrgEntity,Base):
    __tablename__='stock_reservations'
    __table_args__=(UniqueConstraint('id','organisation_id',name='uq_stock_reservation_org'),)
    origine: Mapped[str] = mapped_column(String(200))
    statut: Mapped[str] = mapped_column(String(20),default='ACTIVE')
    auteur_id: Mapped[UUID] = mapped_column(ForeignKey('utilisateurs.id_utilisateur'))
    cree_le: Mapped[datetime] = mapped_column(DateTime(timezone=True),default=now)

class AllocationReservationModel(OrgEntity,Base):
    __tablename__='stock_allocations_reservation'
    __table_args__=(ForeignKeyConstraint(['reservation_id','organisation_id'],['stock_reservations.id','stock_reservations.organisation_id'],name='fk_stock_allocation_reservation'),ForeignKeyConstraint(['stock_id','organisation_id'],['stock_emplacements.id','stock_emplacements.organisation_id'],name='fk_stock_allocation_balance'),CheckConstraint('quantite > 0',name='ck_stock_allocation_qte'))
    reservation_id: Mapped[UUID] = mapped_column(Uuid,index=True)
    stock_id: Mapped[UUID] = mapped_column(Uuid)
    quantite: Mapped[int] = mapped_column(BigInteger)

class DerogationFEFOModel(OrgEntity,Base):
    __tablename__='stock_derogations_fefo'
    reservation_id: Mapped[UUID] = mapped_column(ForeignKey('stock_reservations.id'))
    auteur_id: Mapped[UUID] = mapped_column(ForeignKey('utilisateurs.id_utilisateur'))
    justification: Mapped[str] = mapped_column(String(2000))
    proposition: Mapped[list] = mapped_column(JSON)
    choix: Mapped[list] = mapped_column(JSON)
    date: Mapped[datetime] = mapped_column(DateTime(timezone=True),default=now)

class DemandeTransfertModel(OrgEntity,Base):
    __tablename__='stock_demandes_transfert'
    __table_args__=(UniqueConstraint('id','organisation_id',name='uq_stock_demande_org'),ForeignKeyConstraint(['source_site_id','organisation_id'],['sites.id_site','sites.organisation_id'],name='fk_stock_demande_source_site'),ForeignKeyConstraint(['destination_site_id','organisation_id'],['sites.id_site','sites.organisation_id'],name='fk_stock_demande_destination_site'),ForeignKeyConstraint(['source_id','source_site_id'],['emplacements.id_emplacement','emplacements.site_id'],name='fk_stock_demande_source'),ForeignKeyConstraint(['destination_id','destination_site_id'],['emplacements.id_emplacement','emplacements.site_id'],name='fk_stock_demande_destination'))
    source_site_id: Mapped[UUID] = mapped_column(Uuid)
    destination_site_id: Mapped[UUID] = mapped_column(Uuid)
    source_id: Mapped[UUID] = mapped_column(ForeignKey('emplacements.id_emplacement'))
    destination_id: Mapped[UUID] = mapped_column(ForeignKey('emplacements.id_emplacement'))
    statut: Mapped[str] = mapped_column(String(25),default='DEMANDEE')
    lignes: Mapped[list] = mapped_column(JSON)
    justification: Mapped[str] = mapped_column(String(2000))
    auteur_id: Mapped[UUID] = mapped_column(ForeignKey('utilisateurs.id_utilisateur'))
    date: Mapped[datetime] = mapped_column(DateTime(timezone=True),default=now)

class TransfertStockModel(OrgEntity,Base):
    __tablename__='stock_transferts'
    __table_args__=(UniqueConstraint('id','organisation_id',name='uq_stock_transfert_org'),UniqueConstraint('demande_id',name='uq_stock_transfert_demande'),ForeignKeyConstraint(['demande_id','organisation_id'],['stock_demandes_transfert.id','stock_demandes_transfert.organisation_id'],name='fk_stock_transfert_demande'))
    demande_id: Mapped[UUID] = mapped_column(Uuid)
    reservation_id: Mapped[UUID] = mapped_column(ForeignKey('stock_reservations.id'))
    valide_par: Mapped[UUID] = mapped_column(ForeignKey('utilisateurs.id_utilisateur'))
    valide_le: Mapped[datetime] = mapped_column(DateTime(timezone=True),default=now)
    expedie_par: Mapped[UUID | None] = mapped_column(ForeignKey('utilisateurs.id_utilisateur'))
    expedie_le: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

class LigneTransfertStockModel(OrgEntity,Base):
    __tablename__='stock_lignes_transfert'
    __table_args__=(UniqueConstraint('id','organisation_id',name='uq_stock_ligne_transfert_org'),ForeignKeyConstraint(['transfert_id','organisation_id'],['stock_transferts.id','stock_transferts.organisation_id'],name='fk_stock_ligne_transfert'),ForeignKeyConstraint(['lot_id','organisation_id'],['stock_lots.id','stock_lots.organisation_id'],name='fk_stock_ligne_transfert_lot'),CheckConstraint('quantite > 0 AND recue >= 0 AND recue <= quantite',name='ck_stock_transfert_quantites'))
    transfert_id: Mapped[UUID] = mapped_column(Uuid,index=True)
    lot_id: Mapped[UUID] = mapped_column(Uuid)
    quantite: Mapped[int] = mapped_column(BigInteger)
    recue: Mapped[int] = mapped_column(BigInteger,default=0)

class ReceptionTransfertModel(OrgEntity,Base):
    __tablename__='stock_receptions_transfert'
    __table_args__=(ForeignKeyConstraint(['transfert_id','organisation_id'],['stock_transferts.id','stock_transferts.organisation_id'],name='fk_stock_reception_transfert'),)
    transfert_id: Mapped[UUID] = mapped_column(Uuid,index=True)
    lignes: Mapped[list] = mapped_column(JSON)
    ecarts: Mapped[list] = mapped_column(JSON)
    justification: Mapped[str | None] = mapped_column(String(2000))
    auteur_id: Mapped[UUID] = mapped_column(ForeignKey('utilisateurs.id_utilisateur'))
    date: Mapped[datetime] = mapped_column(DateTime(timezone=True),default=now)

class InventaireModel(OrgEntity,Base):
    __tablename__='stock_inventaires'
    __table_args__=(UniqueConstraint('id','organisation_id',name='uq_stock_inventaire_org'),UniqueConstraint('id','site_id',name='uq_stock_inventaire_site'),ForeignKeyConstraint(['site_id','organisation_id'],['sites.id_site','sites.organisation_id'],name='fk_stock_inventaire_site'),)
    site_id: Mapped[UUID] = mapped_column(Uuid,index=True)
    nom: Mapped[str] = mapped_column(String(200))
    type: Mapped[str] = mapped_column(String(20))
    statut: Mapped[str] = mapped_column(String(20),default='OUVERT')
    snapshot_sequence: Mapped[int] = mapped_column(BigInteger)
    auteur_id: Mapped[UUID] = mapped_column(ForeignKey('utilisateurs.id_utilisateur'))
    date: Mapped[datetime] = mapped_column(DateTime(timezone=True),default=now)
    valide_par: Mapped[UUID | None] = mapped_column(ForeignKey('utilisateurs.id_utilisateur'))
    valide_le: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

class ZoneInventaireModel(OrgEntity,Base):
    __tablename__='stock_zones_inventaire'
    __table_args__=(UniqueConstraint('id','organisation_id',name='uq_stock_zone_org'),ForeignKeyConstraint(['inventaire_id','site_id'],['stock_inventaires.id','stock_inventaires.site_id'],name='fk_stock_zone_site'),ForeignKeyConstraint(['emplacement_id','site_id'],['emplacements.id_emplacement','emplacements.site_id'],name='fk_stock_zone_emplacement'),ForeignKeyConstraint(['inventaire_id','organisation_id'],['stock_inventaires.id','stock_inventaires.organisation_id'],name='fk_stock_zone_inventaire'),)
    inventaire_id: Mapped[UUID] = mapped_column(Uuid,index=True)
    site_id: Mapped[UUID] = mapped_column(Uuid)
    emplacement_id: Mapped[UUID] = mapped_column(ForeignKey('emplacements.id_emplacement'))
    nom: Mapped[str] = mapped_column(String(200))

class ParticipantZoneInventaireModel(OrgEntity,Base):
    __tablename__='stock_participants_zone'
    __table_args__=(UniqueConstraint('zone_id','utilisateur_id',name='uq_stock_participant'),ForeignKeyConstraint(['zone_id','organisation_id'],['stock_zones_inventaire.id','stock_zones_inventaire.organisation_id'],name='fk_stock_participant_zone'))
    zone_id: Mapped[UUID] = mapped_column(Uuid,index=True)
    utilisateur_id: Mapped[UUID] = mapped_column(ForeignKey('utilisateurs.id_utilisateur'))

class MotifEcartInventaireModel(OrgEntity,Base):
    __tablename__='stock_motifs_ecart'
    __table_args__=(UniqueConstraint('id','organisation_id',name='uq_stock_motif_org'),UniqueConstraint('organisation_id','code',name='uq_stock_motif_code'))
    code: Mapped[str] = mapped_column(String(80))
    nom: Mapped[str] = mapped_column(String(200))

class LigneInventaireModel(OrgEntity,Base):
    __tablename__='stock_lignes_inventaire'
    __table_args__=(UniqueConstraint('id','organisation_id',name='uq_stock_ligne_inventaire_org'),UniqueConstraint('zone_id','stock_id',name='uq_stock_ligne_zone_stock'),ForeignKeyConstraint(['zone_id','organisation_id'],['stock_zones_inventaire.id','stock_zones_inventaire.organisation_id'],name='fk_stock_ligne_zone'),ForeignKeyConstraint(['stock_id','organisation_id'],['stock_emplacements.id','stock_emplacements.organisation_id'],name='fk_stock_ligne_balance'))
    zone_id: Mapped[UUID] = mapped_column(Uuid,index=True)
    stock_id: Mapped[UUID] = mapped_column(Uuid)
    theorique: Mapped[int] = mapped_column(BigInteger)
    compte: Mapped[int | None] = mapped_column(BigInteger)
    comptage_sequence: Mapped[int | None] = mapped_column(BigInteger)
    ecart: Mapped[int | None] = mapped_column(BigInteger)
    motif_id: Mapped[UUID | None] = mapped_column(ForeignKey('stock_motifs_ecart.id'))
    justification: Mapped[str | None] = mapped_column(String(2000))

class ComptageInventaireModel(OrgEntity,Base):
    __tablename__='stock_comptages_inventaire'
    ligne_id: Mapped[UUID] = mapped_column(ForeignKey('stock_lignes_inventaire.id'),index=True)
    quantite: Mapped[int] = mapped_column(BigInteger)
    sequence: Mapped[int] = mapped_column(BigInteger)
    auteur_id: Mapped[UUID] = mapped_column(ForeignKey('utilisateurs.id_utilisateur'))
    date: Mapped[datetime] = mapped_column(DateTime(timezone=True),default=now)
    justification: Mapped[str | None] = mapped_column(String(2000))

class OperationStockModel(OrgEntity,Base):
    __tablename__='stock_operations'
    __table_args__=(UniqueConstraint('organisation_id','cle',name='uq_stock_operation_cle'),)
    cle: Mapped[UUID] = mapped_column(Uuid)
    empreinte: Mapped[str] = mapped_column(String(64))
    resultat: Mapped[dict] = mapped_column(JSON)
    auteur_id: Mapped[UUID] = mapped_column(ForeignKey('utilisateurs.id_utilisateur'))
    date: Mapped[datetime] = mapped_column(DateTime(timezone=True),default=now)

# Les journaux sont immuables même pour un UPDATE/DELETE SQL direct.
IMMUTABLE_TABLES=('stock_mouvements','stock_derogations_fefo','stock_comptages_inventaire','stock_receptions_transfert','stock_operations')
for name in IMMUTABLE_TABLES:
    table=Base.metadata.tables[name]
    for action in ('UPDATE','DELETE'):
        trigger=f"CREATE TRIGGER {name}_{action.lower()}_immutable BEFORE {action} ON {name} BEGIN SELECT RAISE(ABORT, 'Journal P3 immuable'); END"
        event.listen(table,'after_create',DDL(trigger).execute_if(dialect='sqlite'))
    function=f"CREATE OR REPLACE FUNCTION {name}_immutable() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN RAISE EXCEPTION 'Journal P3 immuable'; END $$"
    event.listen(table,'after_create',DDL(function).execute_if(dialect='postgresql'))
    event.listen(table,'after_create',DDL(f"CREATE TRIGGER {name}_immutable BEFORE UPDATE OR DELETE ON {name} FOR EACH ROW EXECUTE FUNCTION {name}_immutable()").execute_if(dialect='postgresql'))
