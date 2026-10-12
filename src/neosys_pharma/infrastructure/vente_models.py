"""Contraintes additives P4, identités permanentes et portée organisationnelle."""
from datetime import datetime,timezone
from decimal import Decimal
from uuid import UUID,uuid4
from sqlalchemy import String,Uuid,JSON,ForeignKey,ForeignKeyConstraint,UniqueConstraint,CheckConstraint,DateTime,Numeric
from sqlalchemy.orm import Mapped,mapped_column
from neosys_pharma.infrastructure.database import Base

class EntiteVente:
    id:Mapped[UUID]=mapped_column(Uuid,primary_key=True,default=uuid4)
    organisation_id:Mapped[UUID]=mapped_column(ForeignKey('organisations.id_organisation'),index=True)

class VenteModel(EntiteVente,Base):
    __tablename__='ventes'
    __table_args__=(UniqueConstraint('id','organisation_id',name='uq_vente_org'),ForeignKeyConstraint(['poste_id','emplacement_id'],['postes_vente.id_poste_vente','postes_vente.emplacement_id'],name='fk_vente_poste_emplacement'),ForeignKeyConstraint(['caisse_id','emplacement_id'],['caisses.id_caisse','caisses.emplacement_id'],name='fk_vente_caisse_emplacement'),ForeignKeyConstraint(['site_id','organisation_id'],['sites.id_site','sites.organisation_id'],name='fk_vente_site_org'),ForeignKeyConstraint(['emplacement_id','site_id'],['emplacements.id_emplacement','emplacements.site_id'],name='fk_vente_emplacement_site'),ForeignKeyConstraint(['vendeur_id','organisation_id'],['utilisateurs.id_utilisateur','utilisateurs.organisation_id'],name='fk_vente_vendeur_org'),CheckConstraint("etat IN ('PREPARATION','EN_ATTENTE','VALIDEE_PREPARATION','TRANSMISE','ENCAISSEE','ANNULEE')",name='ck_vente_etat'),CheckConstraint("mode IN ('SANS_TIERS','CNAMGS','MUTUELLE','CNAMGS_MUTUELLE','CREDIT')",name='ck_vente_mode'),CheckConstraint('revision >= 1',name='ck_vente_revision'))
    site_id:Mapped[UUID]=mapped_column(Uuid,index=True)
    emplacement_id:Mapped[UUID]=mapped_column(Uuid,index=True)
    poste_id:Mapped[UUID]=mapped_column(Uuid)
    vendeur_id:Mapped[UUID]=mapped_column(Uuid)
    caisse_id:Mapped[UUID|None]=mapped_column(Uuid)
    etat:Mapped[str]=mapped_column(String(30),default='PREPARATION')
    mode:Mapped[str]=mapped_column(String(30),default='SANS_TIERS')
    destinataire:Mapped[dict]=mapped_column(JSON,default=dict)
    revision:Mapped[int]=mapped_column(default=1)
    cree_le:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=lambda:datetime.now(timezone.utc))

class LigneVenteModel(EntiteVente,Base):
    __tablename__='vente_lignes'
    __table_args__=(UniqueConstraint('id','organisation_id',name='uq_ligne_vente_org'),UniqueConstraint('id','vente_id',name='uq_ligne_vente_parent'),ForeignKeyConstraint(['vente_id','organisation_id'],['ventes.id','ventes.organisation_id'],name='fk_ligne_vente_org'),ForeignKeyConstraint(['produit_id','organisation_id'],['catalogue_produits.id_produit','catalogue_produits.organisation_id'],name='fk_ligne_produit_org'),ForeignKeyConstraint(['conditionnement_id','produit_id','organisation_id'],['catalogue_conditionnements.id_conditionnement','catalogue_conditionnements.produit_id','catalogue_conditionnements.organisation_id'],name='fk_ligne_conditionnement_org'),CheckConstraint('quantite > 0',name='ck_ligne_vente_qte'))
    vente_id:Mapped[UUID]=mapped_column(Uuid,index=True)
    produit_id:Mapped[UUID]=mapped_column(Uuid)
    conditionnement_id:Mapped[UUID]=mapped_column(Uuid)
    actif:Mapped[bool]=mapped_column(default=True)
    quantite:Mapped[int]=mapped_column()
    designation:Mapped[str]=mapped_column(String(200))
    conditionnement:Mapped[str]=mapped_column(String(200))
    reference:Mapped[str|None]=mapped_column(String(200))
    instantane_tarif:Mapped[dict]=mapped_column(JSON)
    montants:Mapped[dict]=mapped_column(JSON)
    remise_appliquee:Mapped[dict|None]=mapped_column(JSON)

class ReservationVenteModel(EntiteVente,Base):
    __tablename__='vente_reservations'
    __table_args__=(ForeignKeyConstraint(['ligne_id','organisation_id'],['vente_lignes.id','vente_lignes.organisation_id'],name='fk_reservation_ligne_org'),ForeignKeyConstraint(['reservation_id','organisation_id'],['stock_reservations.id','stock_reservations.organisation_id'],name='fk_reservation_stock_org'),UniqueConstraint('reservation_id',name='uq_reservation_vente_stock'))
    ligne_id:Mapped[UUID]=mapped_column(Uuid,index=True)
    reservation_id:Mapped[UUID]=mapped_column(Uuid)

class DemandeRemiseModel(EntiteVente,Base):
    __tablename__='vente_demandes_remise'
    __table_args__=(ForeignKeyConstraint(['vente_id','organisation_id'],['ventes.id','ventes.organisation_id'],name='fk_remise_vente_org'),ForeignKeyConstraint(['ligne_id','vente_id'],['vente_lignes.id','vente_lignes.vente_id'],name='fk_remise_ligne_vente'),ForeignKeyConstraint(['auteur_id','organisation_id'],['utilisateurs.id_utilisateur','utilisateurs.organisation_id'],name='fk_remise_auteur_org'),CheckConstraint("type IN ('POURCENTAGE','MONTANT_XAF') AND valeur > 0 AND (type <> 'POURCENTAGE' OR valeur <= 100)",name='ck_remise_valeur'),CheckConstraint("statut IN ('DEMANDEE','AUTORISEE','REFUSEE','INVALIDEE')",name='ck_remise_statut'))
    vente_id:Mapped[UUID]=mapped_column(Uuid,index=True)
    ligne_id:Mapped[UUID|None]=mapped_column(Uuid)
    type:Mapped[str]=mapped_column(String(20))
    valeur:Mapped[Decimal]=mapped_column(Numeric(18,2))
    statut:Mapped[str]=mapped_column(String(20),default='DEMANDEE')
    revision_vente:Mapped[int]=mapped_column()
    auteur_id:Mapped[UUID]=mapped_column(Uuid)
    justification:Mapped[str]=mapped_column(String(2000))
    autorisation:Mapped[dict|None]=mapped_column(JSON)

class EvenementVenteModel(EntiteVente,Base):
    __tablename__='vente_evenements'
    __table_args__=(ForeignKeyConstraint(['vente_id','organisation_id'],['ventes.id','ventes.organisation_id'],name='fk_evenement_vente_org'),ForeignKeyConstraint(['auteur_id','organisation_id'],['utilisateurs.id_utilisateur','utilisateurs.organisation_id'],name='fk_evenement_auteur_org'))
    vente_id:Mapped[UUID]=mapped_column(Uuid,index=True)
    auteur_id:Mapped[UUID]=mapped_column(Uuid)
    date:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=lambda:datetime.now(timezone.utc))
    type:Mapped[str]=mapped_column(String(80))
    donnees:Mapped[dict]=mapped_column(JSON)

# Journal append-only y compris lors de SQL direct.
from sqlalchemy import event,DDL
table=EvenementVenteModel.__table__
for action in ('UPDATE','DELETE'):
    event.listen(table,'after_create',DDL(f"CREATE TRIGGER vente_evenements_{action.lower()}_immutable BEFORE {action} ON vente_evenements BEGIN SELECT RAISE(ABORT, 'Journal Vente immuable'); END").execute_if(dialect='sqlite'))
event.listen(table,'after_create',DDL("CREATE OR REPLACE FUNCTION vente_evenements_immutable() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN RAISE EXCEPTION 'Journal Vente immuable'; END $$").execute_if(dialect='postgresql'))
event.listen(table,'after_create',DDL("CREATE TRIGGER vente_evenements_immutable BEFORE UPDATE OR DELETE ON vente_evenements FOR EACH ROW EXECUTE FUNCTION vente_evenements_immutable()").execute_if(dialect='postgresql'))

class PlafondRemiseModel(EntiteVente,Base):
    __tablename__='vente_plafonds_remise'
    __table_args__=(UniqueConstraint('organisation_id','role_id',name='uq_plafond_remise_role'),CheckConstraint('max_pourcentage IS NULL OR (max_pourcentage > 0 AND max_pourcentage <= 100)',name='ck_plafond_pourcentage'),CheckConstraint('max_montant_xaf IS NULL OR max_montant_xaf > 0',name='ck_plafond_montant'),CheckConstraint('max_pourcentage IS NOT NULL OR max_montant_xaf IS NOT NULL',name='ck_plafond_configure'))
    role_id:Mapped[UUID]=mapped_column(ForeignKey('roles.id_role'))
    max_pourcentage:Mapped[Decimal|None]=mapped_column(Numeric(5,2))
    max_montant_xaf:Mapped[Decimal|None]=mapped_column(Numeric(18,2))
    actif:Mapped[bool]=mapped_column(default=True)
    revision:Mapped[int]=mapped_column(default=1)
