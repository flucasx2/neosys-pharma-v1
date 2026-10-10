"""P4.3 : portée organisation/site, versions émises protégées même en SQL direct."""
from datetime import date,datetime,timezone
from uuid import UUID
from decimal import Decimal
from sqlalchemy import String,Uuid,JSON,ForeignKey,ForeignKeyConstraint,UniqueConstraint,CheckConstraint,DateTime,Date,Numeric,LargeBinary,event,DDL,Index,text
from sqlalchemy.orm import Mapped,mapped_column
from neosys_pharma.infrastructure.database import Base
from neosys_pharma.infrastructure.vente_models import EntiteVente

class ParametrageProformaModel(EntiteVente,Base):
    __tablename__='proforma_parametrages'
    __table_args__=(UniqueConstraint('site_id',name='uq_proforma_param_site'),ForeignKeyConstraint(['site_id','organisation_id'],['sites.id_site','sites.organisation_id'],name='fk_proforma_param_site_org'),CheckConstraint('duree_jours >= 1 AND duree_jours <= 3650',name='ck_proforma_duree'),)
    site_id:Mapped[UUID]=mapped_column(Uuid)
    duree_jours:Mapped[int]=mapped_column(default=30)
    revision:Mapped[int]=mapped_column(default=1)

class ProformaModel(EntiteVente,Base):
    __tablename__='proformas'
    __table_args__=(UniqueConstraint('id','organisation_id',name='uq_proforma_org'),UniqueConstraint('organisation_id','reference',name='uq_proforma_reference'),UniqueConstraint('site_id','sequence',name='uq_proforma_sequence_site'),ForeignKeyConstraint(['site_id','organisation_id'],['sites.id_site','sites.organisation_id'],name='fk_proforma_site_org'),ForeignKeyConstraint(['emplacement_id','site_id'],['emplacements.id_emplacement','emplacements.site_id'],name='fk_proforma_emplacement'),ForeignKeyConstraint(['auteur_id','organisation_id'],['utilisateurs.id_utilisateur','utilisateurs.organisation_id'],name='fk_proforma_auteur'),CheckConstraint('sequence > 0',name='ck_proforma_sequence'))
    site_id:Mapped[UUID]=mapped_column(Uuid,index=True)
    emplacement_id:Mapped[UUID]=mapped_column(Uuid)
    reference:Mapped[str]=mapped_column(String(150))
    sequence:Mapped[int]=mapped_column()
    auteur_id:Mapped[UUID]=mapped_column(Uuid)
    cree_le:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=lambda:datetime.now(timezone.utc))

class VersionProformaModel(EntiteVente,Base):
    __tablename__='proforma_versions'
    __table_args__=(UniqueConstraint('id','organisation_id',name='uq_proforma_version_org'),UniqueConstraint('id','proforma_id',name='uq_proforma_version_parent'),UniqueConstraint('proforma_id','numero',name='uq_proforma_version_numero'),ForeignKeyConstraint(['proforma_id','organisation_id'],['proformas.id','proformas.organisation_id'],name='fk_version_proforma_org'),ForeignKeyConstraint(['site_id','organisation_id'],['sites.id_site','sites.organisation_id'],name='fk_version_proforma_site_org'),ForeignKeyConstraint(['emplacement_id','site_id'],['emplacements.id_emplacement','emplacements.site_id'],name='fk_version_proforma_emplacement'),ForeignKeyConstraint(['auteur_id','organisation_id'],['utilisateurs.id_utilisateur','utilisateurs.organisation_id'],name='fk_version_proforma_auteur'),CheckConstraint("etat IN ('BROUILLON','EMISE')",name='ck_proforma_version_etat'),CheckConstraint("mode IN ('SANS_TIERS','CNAMGS','MUTUELLE','CNAMGS_MUTUELLE','CREDIT')",name='ck_proforma_mode'),CheckConstraint('numero > 0 AND revision > 0',name='ck_proforma_version_revision'),CheckConstraint("etat <> 'EMISE' OR (emis_le IS NOT NULL AND valide_jusqu_au IS NOT NULL AND instantane IS NOT NULL AND pdf IS NOT NULL AND pdf_sha256 IS NOT NULL)",name='ck_proforma_emission_complete'))
    proforma_id:Mapped[UUID]=mapped_column(Uuid,index=True)
    site_id:Mapped[UUID]=mapped_column(Uuid)
    emplacement_id:Mapped[UUID]=mapped_column(Uuid)
    numero:Mapped[int]=mapped_column()
    revision:Mapped[int]=mapped_column(default=1)
    etat:Mapped[str]=mapped_column(String(20),default='BROUILLON')
    mode:Mapped[str]=mapped_column(String(30),default='SANS_TIERS')
    destinataire:Mapped[dict]=mapped_column(JSON,default=dict)
    auteur_id:Mapped[UUID]=mapped_column(Uuid)
    cree_le:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=lambda:datetime.now(timezone.utc))
    emis_le:Mapped[datetime|None]=mapped_column(DateTime(timezone=True))
    valide_jusqu_au:Mapped[date|None]=mapped_column(Date)
    instantane:Mapped[dict|None]=mapped_column(JSON)
    pdf:Mapped[bytes|None]=mapped_column(LargeBinary)
    pdf_sha256:Mapped[str|None]=mapped_column(String(64))

Index('uq_proforma_brouillon',VersionProformaModel.proforma_id,unique=True,sqlite_where=text("etat='BROUILLON'"),postgresql_where=text("etat='BROUILLON'"))

class LigneProformaModel(EntiteVente,Base):
    __tablename__='proforma_lignes'
    __table_args__=(UniqueConstraint('id','organisation_id',name='uq_proforma_ligne_org'),UniqueConstraint('id','version_id',name='uq_proforma_ligne_parent'),ForeignKeyConstraint(['version_id','organisation_id'],['proforma_versions.id','proforma_versions.organisation_id'],name='fk_proforma_ligne_version_org'),ForeignKeyConstraint(['produit_id','organisation_id'],['catalogue_produits.id_produit','catalogue_produits.organisation_id'],name='fk_proforma_ligne_produit'),ForeignKeyConstraint(['conditionnement_id','produit_id','organisation_id'],['catalogue_conditionnements.id_conditionnement','catalogue_conditionnements.produit_id','catalogue_conditionnements.organisation_id'],name='fk_proforma_ligne_conditionnement'),CheckConstraint('quantite > 0',name='ck_proforma_ligne_quantite'))
    version_id:Mapped[UUID]=mapped_column(Uuid,index=True)
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

class DemandeRemiseProformaModel(EntiteVente,Base):
    __tablename__='proforma_demandes_remise'
    __table_args__=(ForeignKeyConstraint(['vente_id','organisation_id'],['proforma_versions.id','proforma_versions.organisation_id'],name='fk_proforma_remise_version'),ForeignKeyConstraint(['ligne_id','vente_id'],['proforma_lignes.id','proforma_lignes.version_id'],name='fk_proforma_remise_ligne'),ForeignKeyConstraint(['auteur_id','organisation_id'],['utilisateurs.id_utilisateur','utilisateurs.organisation_id'],name='fk_proforma_remise_auteur'),CheckConstraint("type IN ('POURCENTAGE','MONTANT_XAF') AND valeur > 0 AND (type <> 'POURCENTAGE' OR valeur <= 100)",name='ck_proforma_remise_valeur'),CheckConstraint("statut IN ('DEMANDEE','AUTORISEE','REFUSEE','INVALIDEE')",name='ck_proforma_remise_statut'))
    # Attribute Vente naming permits the same audited P4.2 decision engine, no financial duplicate.
    vente_id:Mapped[UUID]=mapped_column(Uuid,index=True)
    ligne_id:Mapped[UUID|None]=mapped_column(Uuid)
    type:Mapped[str]=mapped_column(String(20))
    valeur:Mapped[Decimal]=mapped_column(Numeric(18,2))
    statut:Mapped[str]=mapped_column(String(20),default='DEMANDEE')
    revision_vente:Mapped[int]=mapped_column()
    auteur_id:Mapped[UUID]=mapped_column(Uuid)
    justification:Mapped[str]=mapped_column(String(2000))
    autorisation:Mapped[dict|None]=mapped_column(JSON)

class EvenementProformaModel(EntiteVente,Base):
    __tablename__='proforma_evenements'
    __table_args__=(ForeignKeyConstraint(['proforma_id','organisation_id'],['proformas.id','proformas.organisation_id'],name='fk_proforma_evenement_org'),ForeignKeyConstraint(['version_id','proforma_id'],['proforma_versions.id','proforma_versions.proforma_id'],name='fk_proforma_evenement_version'),ForeignKeyConstraint(['auteur_id','organisation_id'],['utilisateurs.id_utilisateur','utilisateurs.organisation_id'],name='fk_proforma_evenement_auteur'))
    proforma_id:Mapped[UUID]=mapped_column(Uuid,index=True)
    version_id:Mapped[UUID]=mapped_column(Uuid)
    auteur_id:Mapped[UUID]=mapped_column(Uuid)
    date:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=lambda:datetime.now(timezone.utc))
    type:Mapped[str]=mapped_column(String(80))
    donnees:Mapped[dict]=mapped_column(JSON)

# DB-level immutability: all emitted payloads, lines, approval audit and stored PDF.
for model,parent in [(ProformaModel,'journal'),(VersionProformaModel,None),(LigneProformaModel,'version_id'),(DemandeRemiseProformaModel,'vente_id'),(EvenementProformaModel,'journal')]:
    table=model.__table__;name=table.name
    for action in ('UPDATE','DELETE'):
        condition="OLD.etat = 'EMISE'" if parent is None else '1=1' if parent=='journal' else f"EXISTS (SELECT 1 FROM proforma_versions WHERE id=OLD.{parent} AND etat='EMISE')"
        if parent not in (None,'journal') and action=='UPDATE':condition+=f" OR EXISTS (SELECT 1 FROM proforma_versions WHERE id=NEW.{parent} AND etat='EMISE')"
        event.listen(table,'after_create',DDL(f"CREATE TRIGGER {name}_{action.lower()}_immutable BEFORE {action} ON {name} WHEN {condition} BEGIN SELECT RAISE(ABORT, 'Version proforma emise immuable'); END").execute_if(dialect='sqlite'))
    if parent not in (None,'journal'):
        condition=f"EXISTS (SELECT 1 FROM proforma_versions WHERE id=NEW.{parent} AND etat='EMISE')"
        event.listen(table,'after_create',DDL(f"CREATE TRIGGER {name}_insert_immutable BEFORE INSERT ON {name} WHEN {condition} BEGIN SELECT RAISE(ABORT, 'Version proforma emise immuable'); END").execute_if(dialect='sqlite'))
    check="IF OLD.etat='EMISE' THEN RAISE EXCEPTION 'Version proforma emise immuable'; END IF;" if parent is None else "RAISE EXCEPTION 'Journal proforma immuable';" if parent=='journal' else f"IF (TG_OP <> 'INSERT' AND EXISTS(SELECT 1 FROM proforma_versions WHERE id=OLD.{parent} AND etat='EMISE')) OR (TG_OP <> 'DELETE' AND EXISTS(SELECT 1 FROM proforma_versions WHERE id=NEW.{parent} AND etat='EMISE')) THEN RAISE EXCEPTION 'Version proforma emise immuable'; END IF;"
    event.listen(table,'after_create',DDL(f"CREATE OR REPLACE FUNCTION {name}_immutable() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN {check} IF TG_OP='DELETE' THEN RETURN OLD; END IF; RETURN NEW; END $$").execute_if(dialect='postgresql'))
    actions='UPDATE OR DELETE' if parent in (None,'journal') else 'INSERT OR UPDATE OR DELETE'
    event.listen(table,'after_create',DDL(f"CREATE TRIGGER {name}_immutable BEFORE {actions} ON {name} FOR EACH ROW EXECUTE FUNCTION {name}_immutable()").execute_if(dialect='postgresql'))
