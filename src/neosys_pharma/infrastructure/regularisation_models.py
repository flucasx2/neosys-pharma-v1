"""P4.5 : dossiers révisés, pièces et journaux compensatoires immuables."""
from uuid import UUID
from datetime import datetime
from decimal import Decimal
from sqlalchemy import Uuid,String,JSON,DateTime,LargeBinary,ForeignKey,ForeignKeyConstraint,UniqueConstraint,CheckConstraint,Index,text,event,DDL
from sqlalchemy.orm import Mapped,mapped_column
from neosys_pharma.infrastructure.database import Base
from neosys_pharma.infrastructure.vente_models import EntiteVente
from neosys_pharma.infrastructure.caisse_models import org_fk,scoped,now,immutable_sql
from neosys_pharma.infrastructure.montant_xaf import MontantXAF

class MouvementFinancierModel(EntiteVente,Base):
    __tablename__='finance_mouvements'
    __table_args__=scoped('finance_mouvement',org_fk('site_id','sites','id_site'),org_fk('session_id','caisse_sessions'),org_fk('auteur_id','utilisateurs','id_utilisateur'),CheckConstraint('montant <> 0'),CheckConstraint("(session_id IS NOT NULL AND coffre_id IS NULL) OR (session_id IS NULL AND coffre_id IS NOT NULL)"),UniqueConstraint('organisation_id','origine','type','session_id','coffre_id'))
    site_id:Mapped[UUID]=mapped_column(Uuid,index=True)
    session_id:Mapped[UUID|None]=mapped_column(Uuid,index=True)
    coffre_id:Mapped[UUID|None]=mapped_column(ForeignKey('coffres.id_coffre'),index=True)
    mode:Mapped[str]=mapped_column(String(30),default='ESPECES')
    montant:Mapped[Decimal]=mapped_column(MontantXAF())
    type:Mapped[str]=mapped_column(String(40))
    origine:Mapped[UUID]=mapped_column(Uuid)
    auteur_id:Mapped[UUID]=mapped_column(Uuid)
    justification:Mapped[str]=mapped_column(String(2000))
    date:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=now)

class TransfertFondsModel(EntiteVente,Base):
    __tablename__='finance_transferts'
    __table_args__=scoped('finance_transfert',org_fk('site_id','sites','id_site'),org_fk('session_id','caisse_sessions'),org_fk('demandeur_id','utilisateurs','id_utilisateur'),org_fk('autorisateur_id','utilisateurs','id_utilisateur'),org_fk('expediteur_id','utilisateurs','id_utilisateur'),org_fk('receptionnaire_id','utilisateurs','id_utilisateur'),CheckConstraint('montant > 0 AND revision > 0'),CheckConstraint("sens IN ('CAISSE_COFFRE','COFFRE_CAISSE')"),CheckConstraint("etat IN ('DEMANDE','AUTORISE','EN_TRANSIT','RECU','ANNULE')"),CheckConstraint('receptionnaire_id IS NULL OR receptionnaire_id <> expediteur_id'))
    site_id:Mapped[UUID]=mapped_column(Uuid,index=True)
    session_id:Mapped[UUID]=mapped_column(Uuid)
    coffre_id:Mapped[UUID]=mapped_column(ForeignKey('coffres.id_coffre'))
    sens:Mapped[str]=mapped_column(String(20))
    montant:Mapped[Decimal]=mapped_column(MontantXAF())
    etat:Mapped[str]=mapped_column(String(20),default='DEMANDE')
    revision:Mapped[int]=mapped_column(default=1)
    demandeur_id:Mapped[UUID]=mapped_column(Uuid)
    autorisateur_id:Mapped[UUID|None]=mapped_column(Uuid)
    expediteur_id:Mapped[UUID|None]=mapped_column(Uuid)
    receptionnaire_id:Mapped[UUID|None]=mapped_column(Uuid)
    justification:Mapped[str]=mapped_column(String(2000))
    date:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=now)

class ReconnaissanceEcartModel(EntiteVente,Base):
    __tablename__='finance_ecarts_reconnus'
    __table_args__=scoped('ecart_reconnu',org_fk('session_id','caisse_sessions'),org_fk('auteur_id','utilisateurs','id_utilisateur'),UniqueConstraint('session_id'))
    session_id:Mapped[UUID]=mapped_column(Uuid)
    auteur_id:Mapped[UUID]=mapped_column(Uuid)
    ecart:Mapped[Decimal]=mapped_column(MontantXAF())
    justification:Mapped[str]=mapped_column(String(2000))
    date:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=now)

class ClotureModel(EntiteVente,Base):
    __tablename__='finance_clotures'
    __table_args__=scoped('cloture',org_fk('site_id','sites','id_site'),org_fk('session_id','caisse_sessions'),org_fk('periode_id','caisse_periodes_site'),org_fk('auteur_id','utilisateurs','id_utilisateur'),CheckConstraint("type IN ('X','Z')"),CheckConstraint("(type='X' AND session_id IS NOT NULL) OR (type='Z' AND session_id IS NULL)"),Index('uq_cloture_z_periode','periode_id',unique=True,sqlite_where=text("type='Z'"),postgresql_where=text("type='Z'")))
    site_id:Mapped[UUID]=mapped_column(Uuid,index=True)
    session_id:Mapped[UUID|None]=mapped_column(Uuid)
    periode_id:Mapped[UUID]=mapped_column(Uuid)
    type:Mapped[str]=mapped_column(String(1))
    auteur_id:Mapped[UUID]=mapped_column(Uuid)
    date:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=now)
    instantane:Mapped[dict]=mapped_column(JSON)
    pdf:Mapped[bytes]=mapped_column(LargeBinary)
    pdf_sha256:Mapped[str]=mapped_column(String(64))

class SessionClotureeZModel(EntiteVente,Base):
    __tablename__='finance_sessions_z'
    __table_args__=scoped('session_z',org_fk('session_id','caisse_sessions'),org_fk('cloture_id','finance_clotures'),UniqueConstraint('session_id'))
    session_id:Mapped[UUID]=mapped_column(Uuid)
    cloture_id:Mapped[UUID]=mapped_column(Uuid)

class RetourVenteModel(EntiteVente,Base):
    __tablename__='vente_retours'
    __table_args__=scoped('retour',ForeignKeyConstraint(['ventilation_id','encaissement_id','organisation_id'],['caisse_ventilations.id','caisse_ventilations.encaissement_id','caisse_ventilations.organisation_id']),org_fk('encaissement_id','caisse_encaissements'),org_fk('site_id','sites','id_site'),org_fk('auteur_id','utilisateurs','id_utilisateur'),CheckConstraint('montant >= 0'))
    ventilation_id:Mapped[UUID|None]=mapped_column(Uuid)
    encaissement_id:Mapped[UUID]=mapped_column(Uuid,index=True)
    site_id:Mapped[UUID]=mapped_column(Uuid)
    auteur_id:Mapped[UUID]=mapped_column(Uuid)
    montant:Mapped[Decimal]=mapped_column(MontantXAF())
    justification:Mapped[str]=mapped_column(String(2000))
    instantane:Mapped[dict]=mapped_column(JSON)
    date:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=now)

class LigneRetourVenteModel(EntiteVente,Base):
    __tablename__='vente_lignes_retour'
    __table_args__=scoped('ligne_retour',org_fk('retour_id','vente_retours'),org_fk('ligne_id','vente_lignes'),org_fk('stock_id','stock_emplacements'),CheckConstraint('quantite > 0 AND montant >= 0'))
    retour_id:Mapped[UUID]=mapped_column(Uuid,index=True)
    ligne_id:Mapped[UUID]=mapped_column(Uuid,index=True)
    stock_id:Mapped[UUID]=mapped_column(Uuid)
    quantite:Mapped[int]=mapped_column()
    montant:Mapped[Decimal]=mapped_column(MontantXAF())
    instantane:Mapped[dict]=mapped_column(JSON)

class QuarantaineModel(EntiteVente,Base):
    __tablename__='stock_quarantaine'
    __table_args__=scoped('quarantaine',org_fk('ligne_retour_id','vente_lignes_retour'),org_fk('stock_id','stock_emplacements'),UniqueConstraint('ligne_retour_id'),CheckConstraint('quantite > 0'),CheckConstraint("etat IN ('EN_CONTROLE','LIBEREE','REFUSEE')"))
    ligne_retour_id:Mapped[UUID]=mapped_column(Uuid)
    stock_id:Mapped[UUID]=mapped_column(Uuid)
    quantite:Mapped[int]=mapped_column()
    etat:Mapped[str]=mapped_column(String(20),default='EN_CONTROLE')

class DecisionQuarantaineModel(EntiteVente,Base):
    __tablename__='stock_decisions_quarantaine'
    __table_args__=scoped('decision_quarantaine',org_fk('quarantaine_id','stock_quarantaine'),org_fk('auteur_id','utilisateurs','id_utilisateur'),UniqueConstraint('quarantaine_id'))
    quarantaine_id:Mapped[UUID]=mapped_column(Uuid)
    auteur_id:Mapped[UUID]=mapped_column(Uuid)
    decision:Mapped[str]=mapped_column(String(20))
    controles:Mapped[dict]=mapped_column(JSON)
    justification:Mapped[str]=mapped_column(String(2000))
    date:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=now)

class RemboursementModel(EntiteVente,Base):
    __tablename__='finance_remboursements'
    __table_args__=scoped('remboursement',org_fk('retour_id','vente_retours'),org_fk('confirmation_id','caisse_confirmations'),org_fk('site_id','sites','id_site'),org_fk('session_id','caisse_sessions'),org_fk('demandeur_id','utilisateurs','id_utilisateur'),org_fk('autorisateur_id','utilisateurs','id_utilisateur'),UniqueConstraint('retour_id'),UniqueConstraint('confirmation_id'),CheckConstraint('montant > 0 AND revision > 0'),CheckConstraint("etat IN ('DEMANDE','AUTORISE','EXECUTE')"),CheckConstraint('(retour_id IS NULL) <> (confirmation_id IS NULL)'))
    site_id:Mapped[UUID]=mapped_column(Uuid,index=True)
    retour_id:Mapped[UUID|None]=mapped_column(Uuid)
    confirmation_id:Mapped[UUID|None]=mapped_column(Uuid)
    session_id:Mapped[UUID]=mapped_column(Uuid)
    montant:Mapped[Decimal]=mapped_column(MontantXAF())
    reglements:Mapped[list]=mapped_column(JSON)
    etat:Mapped[str]=mapped_column(String(20),default='DEMANDE')
    revision:Mapped[int]=mapped_column(default=1)
    demandeur_id:Mapped[UUID]=mapped_column(Uuid)
    autorisateur_id:Mapped[UUID|None]=mapped_column(Uuid)
    justification:Mapped[str]=mapped_column(String(2000))
    date:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=now)

class PieceFinanciereModel(EntiteVente,Base):
    __tablename__='finance_pieces'
    __table_args__=scoped('piece_financiere',org_fk('remboursement_id','finance_remboursements'),org_fk('auteur_id','utilisateurs','id_utilisateur'),UniqueConstraint('remboursement_id'))
    remboursement_id:Mapped[UUID]=mapped_column(Uuid)
    auteur_id:Mapped[UUID]=mapped_column(Uuid)
    instantane:Mapped[dict]=mapped_column(JSON)
    pdf:Mapped[bytes]=mapped_column(LargeBinary)
    pdf_sha256:Mapped[str]=mapped_column(String(64))
    date:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=now)

class CompensationRetourModel(EntiteVente,Base):
    __tablename__='fidelite_compensations_retour'
    __table_args__=scoped('compensation_retour',org_fk('journal_id','fidelite_journal'),org_fk('retour_id','vente_retours'),org_fk('compte_id','fidelite_comptes'),UniqueConstraint('retour_id'))
    retour_id:Mapped[UUID]=mapped_column(Uuid)
    compte_id:Mapped[UUID]=mapped_column(Uuid)
    journal_id:Mapped[UUID|None]=mapped_column(Uuid)
    points_restitues:Mapped[int]=mapped_column(default=0)
    points_revoques:Mapped[int]=mapped_column()
    dette_creee:Mapped[int]=mapped_column()
    details:Mapped[dict]=mapped_column(JSON)

class PreuveRemboursementModel(EntiteVente,Base):
    __tablename__='finance_preuves_remboursement'
    __table_args__=scoped('preuve_remboursement',org_fk('remboursement_id','finance_remboursements'),UniqueConstraint('organisation_id','mode','reference'))
    remboursement_id:Mapped[UUID]=mapped_column(Uuid)
    mode:Mapped[str]=mapped_column(String(30))
    reference:Mapped[str]=mapped_column(String(200))
    preuve:Mapped[str]=mapped_column(String(2000))

IMMUTABLE_P45=('finance_preuves_remboursement','finance_mouvements','finance_ecarts_reconnus','finance_clotures','finance_sessions_z','vente_retours','vente_lignes_retour','stock_decisions_quarantaine','finance_pieces','fidelite_compensations_retour')
for name in IMMUTABLE_P45:
    for dialect in ('sqlite','postgresql'):
        for sql in immutable_sql(name,dialect):event.listen(Base.metadata.tables[name],'after_create',DDL(sql).execute_if(dialect=dialect))

# Dossiers révisables uniquement pendant leur circuit ; les données financières originales sont figées.
def dossier_guard_sql(dialect):
    rows=[('finance_transferts',('site_id','session_id','coffre_id','sens','montant','demandeur_id','justification','date'),"'RECU','ANNULE'"),('finance_remboursements',('site_id','retour_id','confirmation_id','session_id','montant','reglements','demandeur_id','justification','date'),"'EXECUTE'"),('stock_quarantaine',('ligne_retour_id','stock_id','quantite'),"'LIBEREE','REFUSEE'")]
    result=[]
    for table,columns,states in rows:
        changed=' OR '.join(f'NEW.{c} IS NOT OLD.{c}' if dialect=='sqlite' else f'NEW.{c}::text IS DISTINCT FROM OLD.{c}::text' for c in ('organisation_id','id',*columns))
        name=table+'_guard'
        if dialect=='sqlite':result.extend([f"CREATE TRIGGER {name}_update BEFORE UPDATE ON {table} WHEN OLD.etat IN ({states}) OR {changed} BEGIN SELECT RAISE(ABORT,'Dossier financier historique immuable'); END",f"CREATE TRIGGER {name}_delete BEFORE DELETE ON {table} BEGIN SELECT RAISE(ABORT,'Dossier financier historique immuable'); END"])
        else:result.extend([f"CREATE OR REPLACE FUNCTION {name}() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN IF TG_OP='DELETE' THEN RAISE EXCEPTION 'Dossier financier historique immuable'; END IF; IF OLD.etat IN ({states}) OR {changed} THEN RAISE EXCEPTION 'Dossier financier historique immuable'; END IF; RETURN NEW; END $$",f"CREATE TRIGGER {name} BEFORE UPDATE OR DELETE ON {table} FOR EACH ROW EXECUTE FUNCTION {name}()"])
    return result
for dialect in ('sqlite','postgresql'):
    for sql in dossier_guard_sql(dialect):
        table=next(t for t in ('finance_transferts','finance_remboursements','stock_quarantaine') if t+'_guard' in sql)
        event.listen(Base.metadata.tables[table],'after_create',DDL(sql).execute_if(dialect=dialect))
