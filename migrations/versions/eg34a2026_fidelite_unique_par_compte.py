"""Autoriser un journal de fidélité par bénéficiaire et encaissement."""
from alembic import op
import sqlalchemy as sa

revision = 'eg34a2026'
down_revision = 'eg33a2026'
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    if bind.dialect.name == 'postgresql':
        op.drop_constraint('fidelite_journal_encaissement_id_type_key', 'fidelite_journal', type_='unique')
        op.create_unique_constraint('uq_journal_fidelite_encaissement_type_compte', 'fidelite_journal',
                                    ['encaissement_id', 'type', 'compte_id'])
        return
    naming = {'uq': 'uq_%(table_name)s_%(column_0_name)s_%(column_1_name)s'}
    with op.batch_alter_table('fidelite_journal', naming_convention=naming,
                              table_args=(sa.CheckConstraint("type IN ('ACQUISITION','UTILISATION','RESTITUTION','REVOCATION','DETTE','COMPENSATION')"),)) as batch:
        batch.drop_constraint('uq_fidelite_journal_encaissement_id_type', type_='unique')
        batch.create_unique_constraint('uq_journal_fidelite_encaissement_type_compte',
                                       ['encaissement_id', 'type', 'compte_id'])


def downgrade():
    bind = op.get_bind()
    conflict = bind.execute(sa.text("""
        SELECT 1 FROM fidelite_journal
        WHERE encaissement_id IS NOT NULL
        GROUP BY encaissement_id, type
        HAVING count(*) > 1
        LIMIT 1
    """)).first()
    if conflict:
        raise RuntimeError('Downgrade eg34a2026 refusé : plusieurs comptes ont un journal de même type pour un encaissement.')
    if bind.dialect.name == 'postgresql':
        op.drop_constraint('uq_journal_fidelite_encaissement_type_compte', 'fidelite_journal', type_='unique')
        op.create_unique_constraint('fidelite_journal_encaissement_id_type_key', 'fidelite_journal',
                                    ['encaissement_id', 'type'])
        return
    naming = {'uq': 'uq_%(table_name)s_%(column_0_name)s_%(column_1_name)s'}
    with op.batch_alter_table('fidelite_journal', naming_convention=naming,
                              table_args=(sa.CheckConstraint("type IN ('ACQUISITION','UTILISATION','RESTITUTION','REVOCATION','DETTE','COMPENSATION')"),)) as batch:
        batch.drop_constraint('uq_journal_fidelite_encaissement_type_compte', type_='unique')
        batch.create_unique_constraint('uq_fidelite_journal_encaissement_id_type',
                                       ['encaissement_id', 'type'])
