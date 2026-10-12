"""P4.6 documents de préparation immuables, sans modification P1–P4.5.

Migration additive documentée dans docs/P4_6_CADRAGE.md avant exécution.
"""
from alembic import op
import sqlalchemy as sa
revision='a46c001d2026'
down_revision='f22f6abb13c5'
branch_labels=None
depends_on=None

def upgrade():
    op.create_table('vente_documents_preparation',
        sa.Column('id',sa.Uuid(),primary_key=True),
        sa.Column('organisation_id',sa.Uuid(),sa.ForeignKey('organisations.id_organisation'),nullable=False),
        sa.Column('vente_id',sa.Uuid(),nullable=False),sa.Column('revision_vente',sa.Integer(),nullable=False),
        sa.Column('auteur_id',sa.Uuid(),nullable=False),sa.Column('date',sa.DateTime(timezone=True),nullable=False),
        sa.Column('instantane',sa.JSON(),nullable=False),sa.Column('pdf',sa.LargeBinary(),nullable=False),sa.Column('pdf_sha256',sa.String(64),nullable=False),
        sa.ForeignKeyConstraint(['vente_id','organisation_id'],['ventes.id','ventes.organisation_id'],name='fk_document_preparation_vente_org'),
        sa.ForeignKeyConstraint(['auteur_id','organisation_id'],['utilisateurs.id_utilisateur','utilisateurs.organisation_id'],name='fk_document_preparation_auteur_org'),
        sa.UniqueConstraint('vente_id','revision_vente',name='uq_document_preparation_revision'),sa.CheckConstraint('revision_vente >= 1',name='ck_document_preparation_revision'))
    op.create_index('ix_vente_documents_preparation_organisation_id','vente_documents_preparation',['organisation_id'])
    op.create_index('ix_vente_documents_preparation_vente_id','vente_documents_preparation',['vente_id'])
    if op.get_bind().dialect.name=='sqlite':
        for action in ('UPDATE','DELETE'):op.execute(f"CREATE TRIGGER vente_documents_preparation_{action.lower()}_immutable BEFORE {action} ON vente_documents_preparation BEGIN SELECT RAISE(ABORT, 'Document de preparation immuable'); END")
    else:
        op.execute("CREATE FUNCTION vente_documents_preparation_immutable() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN RAISE EXCEPTION 'Document de preparation immuable'; END $$")
        op.execute('CREATE TRIGGER vente_documents_preparation_immutable BEFORE UPDATE OR DELETE ON vente_documents_preparation FOR EACH ROW EXECUTE FUNCTION vente_documents_preparation_immutable()')

def downgrade():
    op.drop_table('vente_documents_preparation')
    if op.get_bind().dialect.name=='postgresql':op.execute('DROP FUNCTION vente_documents_preparation_immutable()')
