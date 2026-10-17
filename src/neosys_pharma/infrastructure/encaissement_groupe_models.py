"""Persistance 3.2 uniquement : aucun parcours groupé activé."""
from datetime import datetime
from decimal import Decimal
from uuid import UUID
from sqlalchemy import String, Uuid, JSON, DateTime, ForeignKeyConstraint, UniqueConstraint, CheckConstraint, event, DDL
from sqlalchemy.orm import Mapped, mapped_column
from neosys_pharma.infrastructure.database import Base
from neosys_pharma.infrastructure.vente_models import EntiteVente
from neosys_pharma.infrastructure.caisse_models import scoped, org_fk, now
from neosys_pharma.infrastructure.montant_xaf import MontantXAF


class DossierEncaissementGroupeModel(EntiteVente, Base):
    __tablename__ = 'caisse_dossiers_groupes'
    __table_args__ = scoped('dossier_groupe', org_fk('site_id', 'sites', 'id_site'),
        ForeignKeyConstraint(['emplacement_id', 'site_id'], ['emplacements.id_emplacement', 'emplacements.site_id']),
        ForeignKeyConstraint(['caisse_id', 'emplacement_id'], ['caisses.id_caisse', 'caisses.emplacement_id']),
        org_fk('session_id', 'caisse_sessions'), org_fk('auteur_id', 'utilisateurs', 'id_utilisateur'),
        org_fk('compte_id', 'fidelite_comptes'),
        CheckConstraint("etat IN ('BROUILLON','EN_REGLEMENT','ENCAISSE','ANNULE')", name='ck_groupe_etat'),
        CheckConstraint('revision > 0 AND length(empreinte_selection) = 64', name='ck_groupe_revision'))
    site_id: Mapped[UUID] = mapped_column(Uuid)
    emplacement_id: Mapped[UUID] = mapped_column(Uuid)
    caisse_id: Mapped[UUID] = mapped_column(Uuid)
    session_id: Mapped[UUID] = mapped_column(Uuid)
    auteur_id: Mapped[UUID] = mapped_column(Uuid)
    compte_id: Mapped[UUID | None] = mapped_column(Uuid)
    etat: Mapped[str] = mapped_column(String(20), default='BROUILLON', server_default='BROUILLON')
    revision: Mapped[int] = mapped_column(default=1, server_default='1')
    empreinte_selection: Mapped[str] = mapped_column(String(64))
    cree_le: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class SelectionGroupeModel(EntiteVente, Base):
    __tablename__ = 'caisse_selections_groupes'
    __table_args__ = scoped('selection_groupe', org_fk('dossier_id', 'caisse_dossiers_groupes'), org_fk('vente_id', 'ventes'), org_fk('compte_id', 'fidelite_comptes'),
        UniqueConstraint('dossier_id', 'vente_id', name='uq_selection_groupe_vente'),
        UniqueConstraint('dossier_id', 'ordre', name='uq_selection_groupe_ordre'),
        CheckConstraint('revision_vente > 0 AND ordre > 0 AND (compte_id IS NULL OR revision_compte > 0)', name='ck_selection_groupe_revision'))
    dossier_id: Mapped[UUID] = mapped_column(Uuid)
    vente_id: Mapped[UUID] = mapped_column(Uuid)
    revision_vente: Mapped[int] = mapped_column()
    compte_id: Mapped[UUID | None] = mapped_column(Uuid)
    revision_compte: Mapped[int | None] = mapped_column()
    ordre: Mapped[int] = mapped_column()


class VentilationEncaissementModel(EntiteVente, Base):
    __tablename__ = 'caisse_ventilations'
    __table_args__ = scoped('ventilation', org_fk('encaissement_id', 'caisse_encaissements'), org_fk('vente_id', 'ventes'), org_fk('compte_id', 'fidelite_comptes'),
        UniqueConstraint('vente_id', name='uq_ventilation_vente'),
        UniqueConstraint('id', 'encaissement_id', 'organisation_id', name='uq_ventilation_enc_org'),
        UniqueConstraint('id', 'vente_id', name='uq_ventilation_vente_parent'),
        CheckConstraint('revision_vente > 0 AND montant_ht >= 0 AND montant_tva >= 0 AND net_ttc >= 0 AND remise_ligne >= 0 AND remise_globale >= 0 AND montant_ht + montant_tva = net_ttc AND (compte_id IS NULL OR revision_compte > 0)', name='ck_ventilation_montants'))
    encaissement_id: Mapped[UUID] = mapped_column(Uuid)
    vente_id: Mapped[UUID] = mapped_column(Uuid)
    revision_vente: Mapped[int] = mapped_column()
    compte_id: Mapped[UUID | None] = mapped_column(Uuid)
    revision_compte: Mapped[int | None] = mapped_column()
    montant_ht: Mapped[Decimal] = mapped_column(MontantXAF())
    montant_tva: Mapped[Decimal] = mapped_column(MontantXAF())
    net_ttc: Mapped[Decimal] = mapped_column(MontantXAF())
    remise_ligne: Mapped[Decimal] = mapped_column(MontantXAF(), default=0, server_default='0')
    remise_globale: Mapped[Decimal] = mapped_column(MontantXAF(), default=0, server_default='0')
    instantane: Mapped[dict] = mapped_column(JSON)


class AllocationReglementModel(EntiteVente, Base):
    __tablename__ = 'caisse_allocations_reglements'
    __table_args__ = scoped('allocation_reglement',
        ForeignKeyConstraint(['reglement_id', 'encaissement_id', 'organisation_id'], ['caisse_reglements.id', 'caisse_reglements.encaissement_id', 'caisse_reglements.organisation_id']),
        ForeignKeyConstraint(['ventilation_id', 'encaissement_id', 'organisation_id'], ['caisse_ventilations.id', 'caisse_ventilations.encaissement_id', 'caisse_ventilations.organisation_id']),
        ForeignKeyConstraint(['ventilation_id', 'vente_id'], ['caisse_ventilations.id', 'caisse_ventilations.vente_id']),
        ForeignKeyConstraint(['ligne_vente_id', 'vente_id'], ['vente_lignes.id', 'vente_lignes.vente_id']),
        org_fk('ligne_vente_id', 'vente_lignes'),
        UniqueConstraint('reglement_id', 'ventilation_id', 'ligne_vente_id', name='uq_allocation_reglement_ligne'),
        CheckConstraint('montant_net > 0', name='ck_allocation_montant'))
    encaissement_id: Mapped[UUID] = mapped_column(Uuid)
    reglement_id: Mapped[UUID] = mapped_column(Uuid)
    ventilation_id: Mapped[UUID] = mapped_column(Uuid)
    vente_id: Mapped[UUID] = mapped_column(Uuid)
    ligne_vente_id: Mapped[UUID] = mapped_column(Uuid)
    montant_net: Mapped[Decimal] = mapped_column(MontantXAF())


class VenteEncaisseeModel(Base):
    """Registre technique commun ; aucun montant historique n'est fabriqué."""
    __tablename__ = 'caisse_ventes_encaissees'
    __table_args__ = (org_fk('vente_id', 'ventes'),
        ForeignKeyConstraint(['encaissement_id', 'organisation_id'], ['caisse_encaissements.id', 'caisse_encaissements.organisation_id'], deferrable=True, initially='DEFERRED'))
    vente_id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    organisation_id: Mapped[UUID] = mapped_column(Uuid)
    encaissement_id: Mapped[UUID] = mapped_column(Uuid)


from neosys_pharma.infrastructure.encaissement_groupe_sql_v1 import guard_sql
for dialect in ('sqlite', 'postgresql'):
    for sql in guard_sql(dialect):
        event.listen(Base.metadata, 'after_create', DDL(sql.replace('%', '%%')).execute_if(dialect=dialect))
