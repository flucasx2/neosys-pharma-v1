"""Moyens organisationnels et identité figée des confirmations, sans réécriture financière."""
from alembic import op
import sqlalchemy as sa
revision='20261019_02'
down_revision='20261019_01'
branch_labels=None
depends_on=None

def upgrade():
    op.create_table('caisse_moyens_paiement',
        sa.Column('id',sa.Uuid(),primary_key=True),
        sa.Column('organisation_id',sa.Uuid(),sa.ForeignKey('organisations.id_organisation'),nullable=False,index=True),
        sa.Column('code',sa.String(80),nullable=False),sa.Column('libelle',sa.String(200),nullable=False),
        sa.Column('mode',sa.String(30),nullable=False),sa.Column('actif',sa.Boolean(),nullable=False),sa.Column('revision',sa.Integer(),nullable=False),
        sa.UniqueConstraint('id','organisation_id',name='uq_moyen_paiement_org'),
        sa.UniqueConstraint('id','organisation_id','mode',name='uq_moyen_mode_org'),
        sa.UniqueConstraint('organisation_id','code',name='uq_moyen_code_org'),
        sa.CheckConstraint("mode IN ('CARTE','MOBILE_MONEY','CHEQUE','VIREMENT')",name='ck_moyen_mode'),
        sa.CheckConstraint('revision > 0 AND length(trim(code)) > 0 AND length(trim(libelle)) > 0',name='ck_moyen_valeurs'))
    # SQLite batch reflection omits unnamed historical CHECKs unless carried explicitly.
    checks=sa.inspect(op.get_bind()).get_check_constraints('caisse_confirmations')
    preserved=tuple(sa.CheckConstraint(c['sqltext'],name='ck_confirmation_historique_'+str(i)) for i,c in enumerate(checks) if c['name'] is None) if op.get_bind().dialect.name=='sqlite' else ()
    with op.batch_alter_table('caisse_confirmations',table_args=preserved) as b:
        b.add_column(sa.Column('moyen_id',sa.Uuid(),nullable=True))
        b.add_column(sa.Column('moyen_libelle',sa.String(200),nullable=True))
        b.create_foreign_key('fk_confirmation_moyen_org_mode','caisse_moyens_paiement',['moyen_id','organisation_id','mode'],['id','organisation_id','mode'])
        b.create_check_constraint('ck_confirmation_moyen_libelle','(moyen_id IS NULL AND moyen_libelle IS NULL) OR (moyen_id IS NOT NULL AND moyen_libelle IS NOT NULL)')
    if op.get_bind().dialect.name=='sqlite':
        from neosys_pharma.infrastructure.caisse_models import immutable_sql
        for sql in immutable_sql('caisse_confirmations','sqlite'):op.execute(sql)

def downgrade():
    if op.get_bind().scalar(sa.text('SELECT count(*) FROM caisse_moyens_paiement')):
        raise RuntimeError('Downgrade refusé : moyens de paiement à conserver.')
    with op.batch_alter_table('caisse_confirmations') as b:
        b.drop_constraint('fk_confirmation_moyen_org_mode',type_='foreignkey')
        b.drop_constraint('ck_confirmation_moyen_libelle',type_='check')
        b.drop_column('moyen_libelle');b.drop_column('moyen_id')
    if op.get_bind().dialect.name=='sqlite':
        from neosys_pharma.infrastructure.caisse_models import immutable_sql
        for sql in immutable_sql('caisse_confirmations','sqlite'):op.execute(sql)
    op.drop_table('caisse_moyens_paiement')
