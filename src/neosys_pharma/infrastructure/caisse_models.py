"""P4.4 : encaissement local, confirmations indépendantes et fidélité organisationnelle."""
from datetime import date,datetime,timezone
from decimal import Decimal
from uuid import UUID
from sqlalchemy import Uuid,String,JSON,Numeric,Date,DateTime,LargeBinary,UniqueConstraint,ForeignKey,ForeignKeyConstraint,CheckConstraint,Index,text,event,DDL
from sqlalchemy.orm import Mapped,mapped_column
from neosys_pharma.infrastructure.database import Base
from neosys_pharma.infrastructure.montant_xaf import MontantXAF
from neosys_pharma.infrastructure.vente_models import EntiteVente
from neosys_pharma.infrastructure.client_models import ClientModel

def now():return datetime.now(timezone.utc)
def org_fk(local,table,remote='id'):
    return ForeignKeyConstraint([local,'organisation_id'],[f'{table}.{remote}',f'{table}.organisation_id'])
def scoped(name,*constraints):return (UniqueConstraint('id','organisation_id',name='uq_'+name+'_org'),*constraints)

class PeriodeCaisseSiteModel(EntiteVente,Base):
    __tablename__='caisse_periodes_site'
    __table_args__=scoped('periode_caisse',UniqueConstraint('id','organisation_id','site_id',name='uq_periode_org_site'),org_fk('site_id','sites','id_site'),UniqueConstraint('site_id','numero'),CheckConstraint('numero > 0 AND prochain_appel > 0 AND prochain_encaissement > 0'),CheckConstraint('prochain_encaissement_groupe > 0',name='ck_caisse_periode_groupe_sequence'),CheckConstraint("etat IN ('OUVERTE','CLOTUREE')"),Index('uq_caisse_periode_ouverte','site_id',unique=True,sqlite_where=text("etat='OUVERTE'"),postgresql_where=text("etat='OUVERTE'")))
    site_id:Mapped[UUID]=mapped_column(Uuid)
    numero:Mapped[int]=mapped_column(default=1)
    etat:Mapped[str]=mapped_column(String(20),default='OUVERTE')
    prochain_appel:Mapped[int]=mapped_column(default=1)
    prochain_encaissement:Mapped[int]=mapped_column(default=1)
    prochain_encaissement_groupe:Mapped[int]=mapped_column(default=1,server_default='1')

class AppelVenteModel(EntiteVente,Base):
    __tablename__='caisse_appels'
    __table_args__=scoped('appel',org_fk('vente_id','ventes'),org_fk('periode_id','caisse_periodes_site'),UniqueConstraint('vente_id'),UniqueConstraint('periode_id','numero'),CheckConstraint('numero > 0'))
    vente_id:Mapped[UUID]=mapped_column(Uuid)
    periode_id:Mapped[UUID]=mapped_column(Uuid)
    numero:Mapped[int]=mapped_column()

class SessionCaisseModel(EntiteVente,Base):
    __tablename__='caisse_sessions'
    __table_args__=scoped('session_caisse',org_fk('site_id','sites','id_site'),UniqueConstraint('id','organisation_id','site_id',name='uq_session_org_site'),org_fk('caissier_id','utilisateurs','id_utilisateur'),ForeignKeyConstraint(['emplacement_id','site_id'],['emplacements.id_emplacement','emplacements.site_id']),ForeignKeyConstraint(['caisse_id','emplacement_id'],['caisses.id_caisse','caisses.emplacement_id']),CheckConstraint('fond_initial >= 0 AND revision > 0'),CheckConstraint("etat IN ('OUVERTE','FERMEE')"),Index('uq_caisse_session_ouverte','caisse_id',unique=True,sqlite_where=text("etat='OUVERTE'"),postgresql_where=text("etat='OUVERTE'")))
    caisse_id:Mapped[UUID]=mapped_column(Uuid)
    emplacement_id:Mapped[UUID]=mapped_column(Uuid)
    site_id:Mapped[UUID]=mapped_column(Uuid)
    caissier_id:Mapped[UUID]=mapped_column(Uuid)
    etat:Mapped[str]=mapped_column(String(20),default='OUVERTE')
    revision:Mapped[int]=mapped_column(default=1)
    fond_initial:Mapped[Decimal]=mapped_column(MontantXAF())
    ouvert_le:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=now)
    ferme_le:Mapped[datetime|None]=mapped_column(DateTime(timezone=True))
    comptage_final:Mapped[Decimal|None]=mapped_column(MontantXAF())

class ParametrageCaisseModel(EntiteVente,Base):
    __tablename__='caisse_parametrages'
    __table_args__=scoped('caisse_param',UniqueConstraint('organisation_id'),CheckConstraint('revision > 0'))
    modes:Mapped[list]=mapped_column(JSON,default=list)
    ticket_appel:Mapped[bool]=mapped_column(default=False)
    revision:Mapped[int]=mapped_column(default=1)

class ConfirmationReglementModel(EntiteVente,Base):
    __tablename__='caisse_confirmations'
    __table_args__=scoped('confirmation',org_fk('vente_id','ventes'),org_fk('session_id','caisse_sessions'),org_fk('auteur_id','utilisateurs','id_utilisateur'),UniqueConstraint('organisation_id','mode','reference'),CheckConstraint('montant > 0'),CheckConstraint("mode IN ('CARTE','MOBILE_MONEY','CHEQUE','VIREMENT')"),CheckConstraint("source IN ('MANUEL_TERMINAL','MANUEL_JUSTIFICATIF','TECHNIQUE_PRESTATAIRE')"))
    vente_id:Mapped[UUID]=mapped_column(Uuid)
    session_id:Mapped[UUID]=mapped_column(Uuid)
    revision_vente:Mapped[int]=mapped_column()
    mode:Mapped[str]=mapped_column(String(30))
    montant:Mapped[Decimal]=mapped_column(MontantXAF())
    reference:Mapped[str]=mapped_column(String(200))
    source:Mapped[str]=mapped_column(String(30))
    preuve:Mapped[str]=mapped_column(String(2000))
    auteur_id:Mapped[UUID]=mapped_column(Uuid)
    confirme_le:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=now)

class ClientFideliteModel(EntiteVente,Base):
    __tablename__='fidelite_clients'
    __table_args__=scoped('client_fidelite',Index('uq_fidelite_client_profil','profil_client_id',unique=True),org_fk('profil_client_id','clients'))
    nom:Mapped[str]=mapped_column(String(200))
    telephone:Mapped[str|None]=mapped_column(String(80),index=True)
    profil_client_id:Mapped[UUID|None]=mapped_column(Uuid)

class CompteFideliteModel(EntiteVente,Base):
    __tablename__='fidelite_comptes'
    __table_args__=scoped('compte_fidelite',org_fk('client_id','fidelite_clients'),UniqueConstraint('client_id'),CheckConstraint('points >= 0 AND dette >= 0 AND revision > 0'))
    client_id:Mapped[UUID]=mapped_column(Uuid)
    points:Mapped[int]=mapped_column(default=0)
    dette:Mapped[int]=mapped_column(default=0)
    revision:Mapped[int]=mapped_column(default=1)

class CarteFideliteModel(EntiteVente,Base):
    __tablename__='fidelite_cartes'
    __table_args__=scoped('carte_fidelite',org_fk('compte_id','fidelite_comptes'),org_fk('remplace_id','fidelite_cartes'),UniqueConstraint('organisation_id','code'),CheckConstraint("type IN ('PHYSIQUE','VIRTUELLE')"),CheckConstraint("etat IN ('ACTIVE','OPPOSEE','REMPLACEE')"))
    compte_id:Mapped[UUID]=mapped_column(Uuid)
    code:Mapped[str]=mapped_column(String(200))
    type:Mapped[str]=mapped_column(String(20))
    etat:Mapped[str]=mapped_column(String(20),default='ACTIVE')
    remplace_id:Mapped[UUID|None]=mapped_column(Uuid)

class BaremeFideliteModel(EntiteVente,Base):
    __tablename__='fidelite_baremes'
    __table_args__=scoped('bareme_fidelite',CheckConstraint("type IN ('ACQUISITION','CONVERSION')"),CheckConstraint('points > 0 AND montant_xaf > 0'),CheckConstraint('fin IS NULL OR fin >= debut'),CheckConstraint('plafond_xaf IS NULL OR plafond_xaf >= 0'),CheckConstraint('plafond_pourcentage IS NULL OR (plafond_pourcentage >= 0 AND plafond_pourcentage <= 100)'))
    type:Mapped[str]=mapped_column(String(20))
    debut:Mapped[date]=mapped_column(Date)
    fin:Mapped[date|None]=mapped_column(Date)
    points:Mapped[int]=mapped_column()
    montant_xaf:Mapped[Decimal]=mapped_column(MontantXAF())
    categories:Mapped[list]=mapped_column(JSON)
    sous_categories:Mapped[bool]=mapped_column()
    plafond_xaf:Mapped[Decimal|None]=mapped_column(MontantXAF())
    plafond_pourcentage:Mapped[Decimal|None]=mapped_column(Numeric(5,2))
    paiement_integral:Mapped[bool]=mapped_column(default=False)

class EncaissementModel(EntiteVente,Base):
    __tablename__='caisse_encaissements'
    __table_args__=scoped('encaissement',org_fk('vente_id','ventes'),UniqueConstraint('id','vente_id','organisation_id',name='uq_enc_vente_org'),org_fk('session_id','caisse_sessions'),org_fk('periode_id','caisse_periodes_site'),org_fk('compte_id','fidelite_comptes'),UniqueConstraint('vente_id'),UniqueConstraint('periode_id','numero'),CheckConstraint('numero > 0 AND total_xaf >= 0'))
    vente_id:Mapped[UUID]=mapped_column(Uuid)
    session_id:Mapped[UUID]=mapped_column(Uuid)
    periode_id:Mapped[UUID]=mapped_column(Uuid)
    numero:Mapped[int]=mapped_column()
    total_xaf:Mapped[Decimal]=mapped_column(MontantXAF())
    compte_id:Mapped[UUID|None]=mapped_column(Uuid)
    date:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=now)
    instantane:Mapped[dict]=mapped_column(JSON)
    pdf:Mapped[bytes]=mapped_column(LargeBinary)
    pdf_sha256:Mapped[str]=mapped_column(String(64))

class ReglementModel(EntiteVente,Base):
    __tablename__='caisse_reglements'
    __table_args__=scoped('reglement',org_fk('encaissement_id','caisse_encaissements'),org_fk('confirmation_id','caisse_confirmations'),UniqueConstraint('confirmation_id'),CheckConstraint('montant > 0 AND rendu >= 0 AND rendu <= montant'),CheckConstraint("mode IN ('ESPECES','CARTE','MOBILE_MONEY','CHEQUE','VIREMENT')"),CheckConstraint("(mode='ESPECES' AND confirmation_id IS NULL) OR (mode<>'ESPECES' AND confirmation_id IS NOT NULL AND rendu=0)"))
    encaissement_id:Mapped[UUID]=mapped_column(Uuid)
    confirmation_id:Mapped[UUID|None]=mapped_column(Uuid)
    mode:Mapped[str]=mapped_column(String(30))
    montant:Mapped[Decimal]=mapped_column(MontantXAF())
    rendu:Mapped[Decimal]=mapped_column(MontantXAF(),default=0)

class MouvementCaisseModel(EntiteVente,Base):
    __tablename__='caisse_mouvements'
    __table_args__=scoped('mouvement_caisse',org_fk('session_id','caisse_sessions'),org_fk('reglement_id','caisse_reglements'),org_fk('auteur_id','utilisateurs','id_utilisateur'),UniqueConstraint('reglement_id'))
    session_id:Mapped[UUID]=mapped_column(Uuid)
    reglement_id:Mapped[UUID]=mapped_column(Uuid)
    auteur_id:Mapped[UUID]=mapped_column(Uuid)
    mode:Mapped[str]=mapped_column(String(30))
    montant_net:Mapped[Decimal]=mapped_column(MontantXAF())
    date:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=now)

class JournalFideliteModel(EntiteVente,Base):
    __tablename__='fidelite_journal'
    __table_args__=scoped('journal_fidelite',org_fk('compte_id','fidelite_comptes'),org_fk('encaissement_id','caisse_encaissements'),org_fk('auteur_id','utilisateurs','id_utilisateur'),org_fk('compensation_de','fidelite_journal'),UniqueConstraint('encaissement_id','type'),CheckConstraint("type IN ('ACQUISITION','UTILISATION','RESTITUTION','REVOCATION','DETTE','COMPENSATION')"))
    compte_id:Mapped[UUID]=mapped_column(Uuid)
    encaissement_id:Mapped[UUID|None]=mapped_column(Uuid)
    auteur_id:Mapped[UUID]=mapped_column(Uuid)
    type:Mapped[str]=mapped_column(String(20))
    delta_points:Mapped[int]=mapped_column()
    delta_dette:Mapped[int]=mapped_column(default=0)
    compensation_de:Mapped[UUID|None]=mapped_column(Uuid)
    details:Mapped[dict]=mapped_column(JSON)
    date:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=now)

class EvenementCaisseModel(EntiteVente,Base):
    __tablename__='caisse_evenements'
    __table_args__=scoped('evenement_caisse',org_fk('auteur_id','utilisateurs','id_utilisateur'))
    auteur_id:Mapped[UUID]=mapped_column(Uuid)
    date:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=now)
    type:Mapped[str]=mapped_column(String(80))
    donnees:Mapped[dict]=mapped_column(JSON)


class EncaissementGroupeModel(EntiteVente,Base):
    """Dossier de préparation et reçu collectif; un brouillon n'écrit pas de finance."""
    __tablename__='caisse_encaissements_groupes'
    __table_args__=scoped(
        'encaissement_groupe',
        UniqueConstraint('id','organisation_id','site_id',name='uq_enc_groupe_org_site'),
        UniqueConstraint('id','organisation_id','session_id',name='uq_enc_groupe_org_session'),
        org_fk('site_id','sites','id_site'),
        ForeignKeyConstraint(['session_id','organisation_id','site_id'],['caisse_sessions.id','caisse_sessions.organisation_id','caisse_sessions.site_id'],name='fk_enc_groupe_session_site'),
        org_fk('auteur_id','utilisateurs','id_utilisateur'),
        ForeignKeyConstraint(['periode_id','organisation_id','site_id'],['caisse_periodes_site.id','caisse_periodes_site.organisation_id','caisse_periodes_site.site_id'],name='fk_encaissement_groupe_periode_site'),
        UniqueConstraint('periode_id','numero',name='uq_enc_groupe_periode_numero'),
        UniqueConstraint('organisation_id','reference',name='uq_enc_groupe_reference_org'),
        UniqueConstraint('organisation_id','cle_idempotence',name='uq_enc_groupe_idempotence_org'),
        CheckConstraint("etat IN ('BROUILLON','FINALISE','ABANDONNE')",name='ck_enc_groupe_etat'),
        CheckConstraint('revision >= 1',name='ck_enc_groupe_revision'),
        CheckConstraint("(etat='FINALISE' AND periode_id IS NOT NULL AND numero IS NOT NULL AND reference IS NOT NULL AND total_xaf IS NOT NULL AND pdf IS NOT NULL AND pdf_sha256 IS NOT NULL) OR (etat IN ('BROUILLON','ABANDONNE') AND periode_id IS NULL AND numero IS NULL AND reference IS NULL AND total_xaf IS NULL AND pdf IS NULL AND pdf_sha256 IS NULL)",name='ck_enc_groupe_recu_final'),
        CheckConstraint("(etat='FINALISE' AND cle_idempotence IS NOT NULL AND empreinte_requete IS NOT NULL) OR (etat IN ('BROUILLON','ABANDONNE') AND cle_idempotence IS NULL AND empreinte_requete IS NULL)",name='ck_enc_groupe_idempotence'),
        CheckConstraint("cle_idempotence IS NULL OR length(trim(cle_idempotence)) > 0",name='ck_enc_groupe_cle_idempotence'),
        CheckConstraint("empreinte_requete IS NULL OR length(empreinte_requete)=64",name='ck_enc_groupe_empreinte_sha256'),
        CheckConstraint('(numero IS NULL OR numero > 0) AND (total_xaf IS NULL OR total_xaf >= 0)',name='ck_enc_groupe_montants'),
    )
    site_id:Mapped[UUID]=mapped_column(Uuid,index=True)
    session_id:Mapped[UUID]=mapped_column(Uuid,index=True)
    auteur_id:Mapped[UUID]=mapped_column(Uuid)
    etat:Mapped[str]=mapped_column(String(20),default='BROUILLON',index=True)
    revision:Mapped[int]=mapped_column(default=1)
    cree_le:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=now)
    periode_id:Mapped[UUID|None]=mapped_column(Uuid)
    numero:Mapped[int|None]=mapped_column()
    reference:Mapped[str|None]=mapped_column(String(100))
    total_xaf:Mapped[Decimal|None]=mapped_column(MontantXAF())
    pdf:Mapped[bytes|None]=mapped_column(LargeBinary)
    pdf_sha256:Mapped[str|None]=mapped_column(String(64))
    cle_idempotence:Mapped[str|None]=mapped_column(String(200))
    empreinte_requete:Mapped[str|None]=mapped_column(String(64))


class EncaissementGroupeVenteModel(EntiteVente,Base):
    """Snapshot ordonné d'une vente; l'encaissement individuel n'existe qu'au commit final."""
    __tablename__='caisse_encaissements_groupes_ventes'
    __table_args__=scoped(
        'enc_groupe_vente',
        ForeignKeyConstraint(['dossier_id','organisation_id','site_id'],['caisse_encaissements_groupes.id','caisse_encaissements_groupes.organisation_id','caisse_encaissements_groupes.site_id'],name='fk_enc_groupe_vente_dossier'),
        ForeignKeyConstraint(['vente_id','organisation_id','site_id'],['ventes.id','ventes.organisation_id','ventes.site_id'],name='fk_enc_groupe_vente_vente_site'),
        ForeignKeyConstraint(['encaissement_id','vente_id','organisation_id'],['caisse_encaissements.id','caisse_encaissements.vente_id','caisse_encaissements.organisation_id'],name='fk_enc_groupe_vente_encaissement_vente'),
        UniqueConstraint('dossier_id','vente_id',name='uq_enc_groupe_vente'),
        UniqueConstraint('dossier_id','ordre',name='uq_enc_groupe_ordre'),
        UniqueConstraint('encaissement_id',name='uq_enc_groupe_encaissement'),
        UniqueConstraint('dossier_id','vente_id','organisation_id',name='uq_enc_groupe_dossier_vente_org'),
        CheckConstraint('ordre > 0 AND revision_vente > 0 AND montant_du >= 0',name='ck_enc_groupe_vente_snapshot'),
    )
    dossier_id:Mapped[UUID]=mapped_column(Uuid,index=True)
    site_id:Mapped[UUID]=mapped_column(Uuid,index=True)
    vente_id:Mapped[UUID]=mapped_column(Uuid,index=True)
    encaissement_id:Mapped[UUID|None]=mapped_column(Uuid,index=True)
    ordre:Mapped[int]=mapped_column()
    revision_vente:Mapped[int]=mapped_column()
    montant_du:Mapped[Decimal]=mapped_column(MontantXAF())


class ReglementGroupeModel(EntiteVente,Base):
    """Moyen présenté dans un dossier; jamais un mouvement financier avant finalisation."""
    __tablename__='caisse_reglements_groupes'
    __table_args__=scoped(
        'reglement_groupe',
        ForeignKeyConstraint(['dossier_id','organisation_id'],['caisse_encaissements_groupes.id','caisse_encaissements_groupes.organisation_id'],name='fk_reg_groupe_dossier'),
        org_fk('confirmation_id','caisse_confirmations'),
        UniqueConstraint('id','dossier_id','organisation_id',name='uq_reg_groupe_dossier_org'),
        UniqueConstraint('dossier_id','ordre',name='uq_reg_groupe_ordre'),
        UniqueConstraint('confirmation_id',name='uq_reg_groupe_confirmation'),
        CheckConstraint('ordre > 0 AND montant > 0 AND rendu >= 0 AND rendu < montant',name='ck_reg_groupe_montants'),
        CheckConstraint("mode IN ('ESPECES','CARTE','MOBILE_MONEY','CHEQUE','VIREMENT')",name='ck_reg_groupe_mode'),
        CheckConstraint("(mode='ESPECES' AND confirmation_id IS NULL) OR (mode<>'ESPECES' AND confirmation_id IS NOT NULL AND rendu=0)",name='ck_reg_groupe_confirmation'),
    )
    dossier_id:Mapped[UUID]=mapped_column(Uuid,index=True)
    ordre:Mapped[int]=mapped_column()
    mode:Mapped[str]=mapped_column(String(30))
    montant:Mapped[Decimal]=mapped_column(MontantXAF())
    rendu:Mapped[Decimal]=mapped_column(MontantXAF(),default=0)
    confirmation_id:Mapped[UUID|None]=mapped_column(Uuid)


class AllocationReglementGroupeModel(EntiteVente,Base):
    """Ventilation explicite entre une ligne de règlement et un ticket du même dossier."""
    __tablename__='caisse_allocations_reglements_groupes'
    __table_args__=scoped(
        'allocation_reg_groupe',
        ForeignKeyConstraint(['reglement_id','dossier_id','organisation_id'],['caisse_reglements_groupes.id','caisse_reglements_groupes.dossier_id','caisse_reglements_groupes.organisation_id'],name='fk_alloc_reg_groupe'),
        ForeignKeyConstraint(['dossier_id','vente_id','organisation_id'],['caisse_encaissements_groupes_ventes.dossier_id','caisse_encaissements_groupes_ventes.vente_id','caisse_encaissements_groupes_ventes.organisation_id'],name='fk_alloc_vente_groupe'),
        UniqueConstraint('reglement_id','vente_id',name='uq_alloc_reg_vente'),
        CheckConstraint('montant > 0',name='ck_alloc_reg_montant'),
    )
    reglement_id:Mapped[UUID]=mapped_column(Uuid,index=True)
    dossier_id:Mapped[UUID]=mapped_column(Uuid,index=True)
    vente_id:Mapped[UUID]=mapped_column(Uuid,index=True)
    montant:Mapped[Decimal]=mapped_column(MontantXAF())


class MouvementCaisseGroupeModel(EntiteVente,Base):
    """Écriture nette par règlement groupé, créée uniquement lors de la finalisation."""
    __tablename__='caisse_mouvements_groupes'
    __table_args__=scoped(
        'mouvement_caisse_groupe',
        ForeignKeyConstraint(['dossier_id','organisation_id','session_id'],['caisse_encaissements_groupes.id','caisse_encaissements_groupes.organisation_id','caisse_encaissements_groupes.session_id'],name='fk_mvt_groupe_dossier_session'),
        ForeignKeyConstraint(['reglement_id','dossier_id','organisation_id'],['caisse_reglements_groupes.id','caisse_reglements_groupes.dossier_id','caisse_reglements_groupes.organisation_id'],name='fk_mvt_groupe_reglement'),
        org_fk('auteur_id','utilisateurs','id_utilisateur'),
        UniqueConstraint('reglement_id',name='uq_mvt_groupe_reglement'),
        CheckConstraint('montant_net > 0',name='ck_mvt_groupe_montant_net'),
        CheckConstraint("mode IN ('ESPECES','CARTE','MOBILE_MONEY','CHEQUE','VIREMENT')",name='ck_mvt_groupe_mode'),
    )
    dossier_id:Mapped[UUID]=mapped_column(Uuid,index=True)
    reglement_id:Mapped[UUID]=mapped_column(Uuid,index=True)
    session_id:Mapped[UUID]=mapped_column(Uuid,index=True)
    auteur_id:Mapped[UUID]=mapped_column(Uuid)
    mode:Mapped[str]=mapped_column(String(30))
    montant_net:Mapped[Decimal]=mapped_column(MontantXAF())
    date:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=now)

IMMUTABLE=('caisse_appels','caisse_confirmations','caisse_encaissements','caisse_reglements','caisse_mouvements','caisse_mouvements_groupes','fidelite_journal','caisse_evenements')
def immutable_sql(name,dialect):
    if dialect=='sqlite':return [f"CREATE TRIGGER {name}_{a.lower()}_immutable BEFORE {a} ON {name} BEGIN SELECT RAISE(ABORT, 'Journal financier immuable'); END" for a in ('UPDATE','DELETE')]
    return [f"CREATE OR REPLACE FUNCTION {name}_immutable() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN RAISE EXCEPTION 'Journal financier immuable'; END $$",f"CREATE TRIGGER {name}_immutable BEFORE UPDATE OR DELETE ON {name} FOR EACH ROW EXECUTE FUNCTION {name}_immutable()"]
for name in IMMUTABLE:
    for dialect in ('sqlite','postgresql'):
        for sql in immutable_sql(name,dialect):event.listen(Base.metadata.tables[name],'after_create',DDL(sql).execute_if(dialect=dialect))


def bareme_guard_sql(dialect):
    cols=('organisation_id','type','debut','points','montant_xaf','categories','sous_categories','plafond_xaf','plafond_pourcentage','paiement_integral')
    if dialect=='sqlite':
        changed=' OR '.join(f'NEW.{c} IS NOT OLD.{c}' for c in cols)
        return [f"CREATE TRIGGER fidelite_bareme_update BEFORE UPDATE ON fidelite_baremes WHEN {changed} OR OLD.fin IS NOT NULL OR NEW.fin IS NULL OR NEW.fin < OLD.debut BEGIN SELECT RAISE(ABORT, 'Bareme historique immuable'); END", "CREATE TRIGGER fidelite_bareme_delete BEFORE DELETE ON fidelite_baremes BEGIN SELECT RAISE(ABORT, 'Bareme historique immuable'); END"]
    changed=' OR '.join(f'NEW.{c}::text IS DISTINCT FROM OLD.{c}::text' for c in cols)
    return [f"CREATE OR REPLACE FUNCTION fidelite_bareme_guard() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN IF TG_OP='DELETE' THEN RAISE EXCEPTION 'Bareme historique immuable'; END IF; IF {changed} OR OLD.fin IS NOT NULL OR NEW.fin IS NULL OR NEW.fin < OLD.debut THEN RAISE EXCEPTION 'Bareme historique immuable'; END IF; RETURN NEW; END $$", "CREATE TRIGGER fidelite_bareme_guard BEFORE UPDATE OR DELETE ON fidelite_baremes FOR EACH ROW EXECUTE FUNCTION fidelite_bareme_guard()"]
for dialect in ('sqlite','postgresql'):
    for sql in bareme_guard_sql(dialect):event.listen(BaremeFideliteModel.__table__,'after_create',DDL(sql).execute_if(dialect=dialect))

def paid_guard_sql(dialect):
    statements=[]
    for table,parent in [('ventes',None),('vente_lignes','vente_id'),('vente_demandes_remise','vente_id')]:
        actions=('UPDATE','DELETE') if parent is None else ('INSERT','UPDATE','DELETE')
        for action in actions:
            if parent is None:condition="OLD.etat='ENCAISSEE'"
            else:
                refs=['NEW'] if action=='INSERT' else ['OLD'] if action=='DELETE' else ['OLD','NEW']
                condition=' OR '.join(f"EXISTS(SELECT 1 FROM ventes WHERE id={ref}.{parent} AND etat='ENCAISSEE')" for ref in refs)
            name=table+'_paye_'+action.lower()
            if dialect=='sqlite':statements.append(f"CREATE TRIGGER {name} BEFORE {action} ON {table} WHEN {condition} BEGIN SELECT RAISE(ABORT, 'Vente encaissee immuable'); END")
            else:statements.extend([f"CREATE OR REPLACE FUNCTION {name}() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN IF {condition} THEN RAISE EXCEPTION 'Vente encaissee immuable'; END IF; IF TG_OP='DELETE' THEN RETURN OLD; END IF; RETURN NEW; END $$",f"CREATE TRIGGER {name} BEFORE {action} ON {table} FOR EACH ROW EXECUTE FUNCTION {name}()"])
    return statements
for dialect in ('sqlite','postgresql'):
    for sql in paid_guard_sql(dialect):
        table=sql.split(' ON ')[1].split(' ')[0] if dialect=='sqlite' else next(t for t in ('vente_demandes_remise','vente_lignes','ventes') if t+'_paye_' in sql)
        event.listen(Base.metadata.tables[table],'after_create',DDL(sql).execute_if(dialect=dialect))
