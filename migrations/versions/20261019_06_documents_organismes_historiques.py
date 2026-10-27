"""documents organismes historiques

Revision ID: 20261019_06
Revises: 20261019_05
Create Date: 2026-10-19 16:30:28.971910

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '20261019_06'
down_revision: Union[str, Sequence[str], None] = '20261019_05'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""

    op.create_table('tiers_payant_regroupements_documents',
    sa.Column('site_id', sa.Uuid(), nullable=False),
    sa.Column('organisme_id', sa.Uuid(), nullable=False),
    sa.Column('genre', sa.String(length=20), nullable=False),
    sa.Column('total_xaf', sa.BigInteger(), nullable=False),
    sa.Column('snapshot', sa.JSON(), nullable=False),
    sa.Column('pdf', sa.LargeBinary(), nullable=False),
    sa.Column('pdf_sha256', sa.String(length=64), nullable=False),
    sa.Column('auteur_id', sa.Uuid(), nullable=False),
    sa.Column('cree_le', sa.DateTime(timezone=True), nullable=False),
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('organisation_id', sa.Uuid(), nullable=False),
    sa.CheckConstraint("genre IN ('RECAPITULATIF','LOT')", name='ck_tp_regroupement_doc_genre'),
    sa.CheckConstraint('total_xaf > 0 AND length(pdf_sha256)=64', name='ck_tp_regroupement_doc_total_hash'),
    sa.ForeignKeyConstraint(['auteur_id', 'organisation_id'], ['utilisateurs.id_utilisateur', 'utilisateurs.organisation_id'], ),
    sa.ForeignKeyConstraint(['organisation_id'], ['organisations.id_organisation'], ),
    sa.ForeignKeyConstraint(['organisme_id', 'organisation_id'], ['organismes_prise_en_charge.id', 'organismes_prise_en_charge.organisation_id'], ),
    sa.ForeignKeyConstraint(['site_id', 'organisation_id'], ['sites.id_site', 'sites.organisation_id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('id', 'organisation_id', name='uq_tp_regroupement_doc_org')
    )
    with op.batch_alter_table('tiers_payant_regroupements_documents', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_tiers_payant_regroupements_documents_organisation_id'), ['organisation_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_tiers_payant_regroupements_documents_organisme_id'), ['organisme_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_tiers_payant_regroupements_documents_site_id'), ['site_id'], unique=False)

    op.create_table('tiers_payant_preparations_documents',
    sa.Column('site_id', sa.Uuid(), nullable=False),
    sa.Column('organisme_id', sa.Uuid(), nullable=False),
    sa.Column('convention_id', sa.Uuid(), nullable=False),
    sa.Column('presentation_id', sa.Uuid(), nullable=True),
    sa.Column('genre', sa.String(length=20), nullable=False),
    sa.Column('date_debut', sa.Date(), nullable=False),
    sa.Column('date_fin', sa.Date(), nullable=False),
    sa.Column('auteur_id', sa.Uuid(), nullable=False),
    sa.Column('cree_le', sa.DateTime(timezone=True), nullable=False),
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('organisation_id', sa.Uuid(), nullable=False),
    sa.CheckConstraint("genre IN ('BORDEREAU','FACTURE')", name='ck_tp_preparation_doc_genre'),
    sa.CheckConstraint('date_fin >= date_debut', name='ck_tp_preparation_doc_periode'),
    sa.ForeignKeyConstraint(['auteur_id', 'organisation_id'], ['utilisateurs.id_utilisateur', 'utilisateurs.organisation_id'], ),
    sa.ForeignKeyConstraint(['convention_id', 'organisation_id'], ['tiers_payant_conventions.id', 'tiers_payant_conventions.organisation_id'], ),
    sa.ForeignKeyConstraint(['organisation_id'], ['organisations.id_organisation'], ),
    sa.ForeignKeyConstraint(['organisme_id', 'organisation_id'], ['organismes_prise_en_charge.id', 'organismes_prise_en_charge.organisation_id'], ),
    sa.ForeignKeyConstraint(['presentation_id', 'organisation_id'], ['tiers_payant_preparations_documents.id', 'tiers_payant_preparations_documents.organisation_id'], ),
    sa.ForeignKeyConstraint(['site_id', 'organisation_id'], ['sites.id_site', 'sites.organisation_id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('id', 'organisation_id', 'genre', name='uq_tp_preparation_doc_genre'),
    sa.UniqueConstraint('id', 'organisation_id', name='uq_tp_preparation_doc_org')
    )
    with op.batch_alter_table('tiers_payant_preparations_documents', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_tiers_payant_preparations_documents_organisation_id'), ['organisation_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_tiers_payant_preparations_documents_organisme_id'), ['organisme_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_tiers_payant_preparations_documents_site_id'), ['site_id'], unique=False)

    op.create_table('tiers_payant_documents_emis',
    sa.Column('preparation_id', sa.Uuid(), nullable=False),
    sa.Column('site_id', sa.Uuid(), nullable=False),
    sa.Column('organisme_id', sa.Uuid(), nullable=False),
    sa.Column('genre', sa.String(length=20), nullable=False),
    sa.Column('reference', sa.String(length=80), nullable=False),
    sa.Column('reference_validation', sa.String(length=200), nullable=False),
    sa.Column('total_xaf', sa.BigInteger(), nullable=False),
    sa.Column('snapshot', sa.JSON(), nullable=False),
    sa.Column('pdf', sa.LargeBinary(), nullable=False),
    sa.Column('pdf_sha256', sa.String(length=64), nullable=False),
    sa.Column('auteur_id', sa.Uuid(), nullable=False),
    sa.Column('emis_le', sa.DateTime(timezone=True), nullable=False),
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('organisation_id', sa.Uuid(), nullable=False),
    sa.CheckConstraint('total_xaf > 0 AND length(pdf_sha256)=64', name='ck_tp_document_emis_total_hash'),
    sa.ForeignKeyConstraint(['auteur_id', 'organisation_id'], ['utilisateurs.id_utilisateur', 'utilisateurs.organisation_id'], ),
    sa.ForeignKeyConstraint(['organisation_id'], ['organisations.id_organisation'], ),
    sa.ForeignKeyConstraint(['organisme_id', 'organisation_id'], ['organismes_prise_en_charge.id', 'organismes_prise_en_charge.organisation_id'], ),
    sa.ForeignKeyConstraint(['preparation_id', 'organisation_id', 'genre'], ['tiers_payant_preparations_documents.id', 'tiers_payant_preparations_documents.organisation_id', 'tiers_payant_preparations_documents.genre'], ),
    sa.ForeignKeyConstraint(['site_id', 'organisation_id'], ['sites.id_site', 'sites.organisation_id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('id', 'organisation_id', 'genre', name='uq_tp_document_emis_genre'),
    sa.UniqueConstraint('id', 'organisation_id', name='uq_tp_document_emis_org'),
    sa.UniqueConstraint('organisation_id', 'genre', 'reference', name='uq_tp_document_emis_reference'),
    sa.UniqueConstraint('preparation_id', name='uq_tp_document_emis_preparation')
    )
    with op.batch_alter_table('tiers_payant_documents_emis', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_tiers_payant_documents_emis_organisation_id'), ['organisation_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_tiers_payant_documents_emis_organisme_id'), ['organisme_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_tiers_payant_documents_emis_site_id'), ['site_id'], unique=False)

    op.create_table('tiers_payant_versions_preparations',
    sa.Column('preparation_id', sa.Uuid(), nullable=False),
    sa.Column('revision', sa.Integer(), nullable=False),
    sa.Column('etat', sa.String(length=20), nullable=False),
    sa.Column('selection', sa.JSON(), nullable=False),
    sa.Column('motif', sa.String(length=2000), nullable=False),
    sa.Column('auteur_id', sa.Uuid(), nullable=False),
    sa.Column('cree_le', sa.DateTime(timezone=True), nullable=False),
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('organisation_id', sa.Uuid(), nullable=False),
    sa.CheckConstraint("etat IN ('PREPARATION','VALIDEE','ABANDONNEE','EMISE')", name='ck_tp_version_preparation_etat'),
    sa.CheckConstraint('revision > 0', name='ck_tp_version_preparation_revision'),
    sa.ForeignKeyConstraint(['auteur_id', 'organisation_id'], ['utilisateurs.id_utilisateur', 'utilisateurs.organisation_id'], ),
    sa.ForeignKeyConstraint(['organisation_id'], ['organisations.id_organisation'], ),
    sa.ForeignKeyConstraint(['preparation_id', 'organisation_id'], ['tiers_payant_preparations_documents.id', 'tiers_payant_preparations_documents.organisation_id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('id', 'organisation_id', name='uq_tp_version_preparation_org'),
    sa.UniqueConstraint('preparation_id', 'revision', name='uq_tp_version_preparation_revision')
    )
    with op.batch_alter_table('tiers_payant_versions_preparations', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_tiers_payant_versions_preparations_organisation_id'), ['organisation_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_tiers_payant_versions_preparations_preparation_id'), ['preparation_id'], unique=False)

    op.create_table('tiers_payant_membres_regroupements',
    sa.Column('regroupement_id', sa.Uuid(), nullable=False),
    sa.Column('document_id', sa.Uuid(), nullable=True),
    sa.Column('recapitulatif_id', sa.Uuid(), nullable=True),
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('organisation_id', sa.Uuid(), nullable=False),
    sa.CheckConstraint('(document_id IS NULL) <> (recapitulatif_id IS NULL)', name='ck_tp_membre_regroupement_type'),
    sa.ForeignKeyConstraint(['document_id', 'organisation_id'], ['tiers_payant_documents_emis.id', 'tiers_payant_documents_emis.organisation_id'], ),
    sa.ForeignKeyConstraint(['organisation_id'], ['organisations.id_organisation'], ),
    sa.ForeignKeyConstraint(['recapitulatif_id', 'organisation_id'], ['tiers_payant_regroupements_documents.id', 'tiers_payant_regroupements_documents.organisation_id'], ),
    sa.ForeignKeyConstraint(['regroupement_id', 'organisation_id'], ['tiers_payant_regroupements_documents.id', 'tiers_payant_regroupements_documents.organisation_id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('document_id', name='uq_tp_membre_facture'),
    sa.UniqueConstraint('id', 'organisation_id', name='uq_tp_membre_regroupement_org'),
    sa.UniqueConstraint('recapitulatif_id', name='uq_tp_membre_recapitulatif')
    )
    with op.batch_alter_table('tiers_payant_membres_regroupements', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_tiers_payant_membres_regroupements_organisation_id'), ['organisation_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_tiers_payant_membres_regroupements_regroupement_id'), ['regroupement_id'], unique=False)

    op.create_table('tiers_payant_engagements_creances',
    sa.Column('preparation_id', sa.Uuid(), nullable=False),
    sa.Column('creance_id', sa.Uuid(), nullable=False),
    sa.Column('genre', sa.String(length=20), nullable=False),
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('organisation_id', sa.Uuid(), nullable=False),
    sa.ForeignKeyConstraint(['creance_id', 'organisation_id'], ['tiers_payant_creances.id', 'tiers_payant_creances.organisation_id'], ),
    sa.ForeignKeyConstraint(['organisation_id'], ['organisations.id_organisation'], ),
    sa.ForeignKeyConstraint(['preparation_id', 'organisation_id', 'genre'], ['tiers_payant_preparations_documents.id', 'tiers_payant_preparations_documents.organisation_id', 'tiers_payant_preparations_documents.genre'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('creance_id', 'genre', name='uq_tp_engagement_creance_genre'),
    sa.UniqueConstraint('id', 'organisation_id', name='uq_tp_engagement_creance_org')
    )
    with op.batch_alter_table('tiers_payant_engagements_creances', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_tiers_payant_engagements_creances_creance_id'), ['creance_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_tiers_payant_engagements_creances_organisation_id'), ['organisation_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_tiers_payant_engagements_creances_preparation_id'), ['preparation_id'], unique=False)

    op.create_table('tiers_payant_lignes_documents_emis',
    sa.Column('document_id', sa.Uuid(), nullable=False),
    sa.Column('creance_id', sa.Uuid(), nullable=False),
    sa.Column('genre', sa.String(length=20), nullable=False),
    sa.Column('montant_xaf', sa.Integer(), nullable=False),
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('organisation_id', sa.Uuid(), nullable=False),
    sa.CheckConstraint('montant_xaf > 0', name='ck_tp_ligne_document_montant'),
    sa.ForeignKeyConstraint(['creance_id', 'organisation_id'], ['tiers_payant_creances.id', 'tiers_payant_creances.organisation_id'], ),
    sa.ForeignKeyConstraint(['document_id', 'organisation_id', 'genre'], ['tiers_payant_documents_emis.id', 'tiers_payant_documents_emis.organisation_id', 'tiers_payant_documents_emis.genre'], ),
    sa.ForeignKeyConstraint(['organisation_id'], ['organisations.id_organisation'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('creance_id', 'genre', name='uq_tp_ligne_document_creance_genre'),
    sa.UniqueConstraint('id', 'organisation_id', name='uq_tp_ligne_document_org')
    )
    with op.batch_alter_table('tiers_payant_lignes_documents_emis', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_tiers_payant_lignes_documents_emis_creance_id'), ['creance_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_tiers_payant_lignes_documents_emis_document_id'), ['document_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_tiers_payant_lignes_documents_emis_organisation_id'), ['organisation_id'], unique=False)

    op.create_table('tiers_payant_selections_versions_documents',
    sa.Column('version_id', sa.Uuid(), nullable=False),
    sa.Column('creance_id', sa.Uuid(), nullable=False),
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('organisation_id', sa.Uuid(), nullable=False),
    sa.ForeignKeyConstraint(['creance_id', 'organisation_id'], ['tiers_payant_creances.id', 'tiers_payant_creances.organisation_id'], ),
    sa.ForeignKeyConstraint(['organisation_id'], ['organisations.id_organisation'], ),
    sa.ForeignKeyConstraint(['version_id', 'organisation_id'], ['tiers_payant_versions_preparations.id', 'tiers_payant_versions_preparations.organisation_id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('id', 'organisation_id', name='uq_tp_selection_version_org'),
    sa.UniqueConstraint('version_id', 'creance_id', name='uq_tp_selection_version_creance')
    )
    with op.batch_alter_table('tiers_payant_selections_versions_documents', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_tiers_payant_selections_versions_documents_creance_id'), ['creance_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_tiers_payant_selections_versions_documents_organisation_id'), ['organisation_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_tiers_payant_selections_versions_documents_version_id'), ['version_id'], unique=False)

    from neosys_pharma.infrastructure.caisse_models import immutable_sql
    for table in IMMUTABLE_TABLES:
        for statement in immutable_sql(table,op.get_bind().dialect.name):op.execute(statement)
    for statement in engagement_guard_sql(op.get_bind().dialect.name):op.execute(statement)
    from neosys_pharma.domain.organisation.permissions_systeme import permission_id
    permissions=sa.table('permissions',sa.column('id_permission',sa.Uuid()),sa.column('code',sa.String()),sa.column('nom',sa.String()))
    for code,label in PERMISSIONS:
        if not op.get_bind().scalar(sa.select(permissions.c.id_permission).where(permissions.c.code==code)):
            op.bulk_insert(permissions,[{'id_permission':permission_id(code),'code':code,'nom':label}])



def downgrade() -> None:
    """Downgrade conservateur, sans suppression d'historique."""
    if any(op.get_bind().scalar(sa.text(f'SELECT count(*) FROM {table}')) for table in ALL_TABLES):
        raise RuntimeError('Downgrade refusé : préparations ou documents à conserver.')

    with op.batch_alter_table('tiers_payant_selections_versions_documents', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_tiers_payant_selections_versions_documents_version_id'))
        batch_op.drop_index(batch_op.f('ix_tiers_payant_selections_versions_documents_organisation_id'))
        batch_op.drop_index(batch_op.f('ix_tiers_payant_selections_versions_documents_creance_id'))

    op.drop_table('tiers_payant_selections_versions_documents')
    with op.batch_alter_table('tiers_payant_lignes_documents_emis', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_tiers_payant_lignes_documents_emis_organisation_id'))
        batch_op.drop_index(batch_op.f('ix_tiers_payant_lignes_documents_emis_document_id'))
        batch_op.drop_index(batch_op.f('ix_tiers_payant_lignes_documents_emis_creance_id'))

    op.drop_table('tiers_payant_lignes_documents_emis')
    with op.batch_alter_table('tiers_payant_engagements_creances', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_tiers_payant_engagements_creances_preparation_id'))
        batch_op.drop_index(batch_op.f('ix_tiers_payant_engagements_creances_organisation_id'))
        batch_op.drop_index(batch_op.f('ix_tiers_payant_engagements_creances_creance_id'))

    op.drop_table('tiers_payant_engagements_creances')
    with op.batch_alter_table('tiers_payant_membres_regroupements', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_tiers_payant_membres_regroupements_regroupement_id'))
        batch_op.drop_index(batch_op.f('ix_tiers_payant_membres_regroupements_organisation_id'))

    op.drop_table('tiers_payant_membres_regroupements')
    with op.batch_alter_table('tiers_payant_versions_preparations', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_tiers_payant_versions_preparations_preparation_id'))
        batch_op.drop_index(batch_op.f('ix_tiers_payant_versions_preparations_organisation_id'))

    op.drop_table('tiers_payant_versions_preparations')
    with op.batch_alter_table('tiers_payant_documents_emis', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_tiers_payant_documents_emis_site_id'))
        batch_op.drop_index(batch_op.f('ix_tiers_payant_documents_emis_organisme_id'))
        batch_op.drop_index(batch_op.f('ix_tiers_payant_documents_emis_organisation_id'))

    op.drop_table('tiers_payant_documents_emis')
    with op.batch_alter_table('tiers_payant_preparations_documents', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_tiers_payant_preparations_documents_site_id'))
        batch_op.drop_index(batch_op.f('ix_tiers_payant_preparations_documents_organisme_id'))
        batch_op.drop_index(batch_op.f('ix_tiers_payant_preparations_documents_organisation_id'))

    op.drop_table('tiers_payant_preparations_documents')
    with op.batch_alter_table('tiers_payant_regroupements_documents', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_tiers_payant_regroupements_documents_site_id'))
        batch_op.drop_index(batch_op.f('ix_tiers_payant_regroupements_documents_organisme_id'))
        batch_op.drop_index(batch_op.f('ix_tiers_payant_regroupements_documents_organisation_id'))

    op.drop_table('tiers_payant_regroupements_documents')
    if op.get_bind().dialect.name=='postgresql':
        for table in IMMUTABLE_TABLES:op.execute(f'DROP FUNCTION {table}_immutable()')
        op.execute('DROP FUNCTION tp_engagement_guard()')

IMMUTABLE_TABLES=('tiers_payant_preparations_documents', 'tiers_payant_versions_preparations', 'tiers_payant_documents_emis', 'tiers_payant_lignes_documents_emis', 'tiers_payant_regroupements_documents', 'tiers_payant_membres_regroupements', 'tiers_payant_selections_versions_documents')
ALL_TABLES=IMMUTABLE_TABLES+('tiers_payant_engagements_creances',)
PERMISSIONS=(('tiers_payant.document.consulter', 'Consulter les préparations et documents organismes autorisés'), ('tiers_payant.document.preparer', 'Préparer et abandonner les bordereaux et factures organismes'), ('tiers_payant.document.valider', 'Contrôler les préparations de documents organismes'), ('tiers_payant.document.emettre', 'Émettre des documents organismes en recette autorisée'), ('tiers_payant.document.regrouper', 'Regrouper les factures émises et leurs récapitulatifs'))

def engagement_guard_sql(dialect):
    table='tiers_payant_engagements_creances'
    if dialect=='sqlite':
        return [f"CREATE TRIGGER tp_engagement_update BEFORE UPDATE ON {table} BEGIN SELECT RAISE(ABORT, 'Engagement non modifiable'); END",
            f"CREATE TRIGGER tp_engagement_delete BEFORE DELETE ON {table} WHEN EXISTS (SELECT 1 FROM tiers_payant_documents_emis d WHERE d.preparation_id=OLD.preparation_id) BEGIN SELECT RAISE(ABORT, 'Document emis : engagement irreversible'); END"]
    return ["CREATE OR REPLACE FUNCTION tp_engagement_guard() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN IF TG_OP='UPDATE' OR EXISTS (SELECT 1 FROM tiers_payant_documents_emis d WHERE d.preparation_id=OLD.preparation_id) THEN RAISE EXCEPTION 'Engagement emis ou modification interdite'; END IF; RETURN OLD; END $$",
        f"CREATE TRIGGER tp_engagement_guard BEFORE UPDATE OR DELETE ON {table} FOR EACH ROW EXECUTE FUNCTION tp_engagement_guard()"]
