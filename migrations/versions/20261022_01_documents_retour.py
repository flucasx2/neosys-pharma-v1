"""P4-05 MIG-01 : pièce autonome de réception, sans backfill historique."""
from alembic import op
import sqlalchemy as sa

revision='20261022_01'
down_revision='20261019_06'
branch_labels=None
depends_on=None


def upgrade():
    op.create_table('vente_documents_retour',
        sa.Column('id',sa.Uuid(),primary_key=True),
        sa.Column('organisation_id',sa.Uuid(),sa.ForeignKey('organisations.id_organisation'),nullable=False,index=True),
        sa.Column('retour_id',sa.Uuid(),nullable=False),sa.Column('auteur_id',sa.Uuid(),nullable=False),
        sa.Column('instantane',sa.JSON(),nullable=False),sa.Column('pdf',sa.LargeBinary(),nullable=False),
        sa.Column('pdf_sha256',sa.String(64),nullable=False),sa.Column('date',sa.DateTime(timezone=True),nullable=False),
        sa.ForeignKeyConstraint(['retour_id','organisation_id'],['vente_retours.id','vente_retours.organisation_id']),
        sa.ForeignKeyConstraint(['auteur_id','organisation_id'],['utilisateurs.id_utilisateur','utilisateurs.organisation_id']),
        sa.UniqueConstraint('id','organisation_id',name='uq_document_retour_org'),
        sa.UniqueConstraint('retour_id',name='uq_document_retour_source'))
    from neosys_pharma.infrastructure.caisse_models import immutable_sql
    for sql in immutable_sql('vente_documents_retour',op.get_bind().dialect.name):op.execute(sql)


def downgrade():
    if op.get_bind().scalar(sa.text('SELECT count(*) FROM vente_documents_retour')):
        raise RuntimeError('Downgrade refusé : documents de retour à conserver.')
    op.drop_table('vente_documents_retour')
    if op.get_bind().dialect.name=='postgresql':op.execute('DROP FUNCTION vente_documents_retour_immutable()')
