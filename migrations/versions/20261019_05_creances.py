"""Créances immuables et compléments administratifs P5-FAC-02."""
from alembic import op
import sqlalchemy as sa
revision='20261019_05'
down_revision='20261019_04'
branch_labels=None
depends_on=None
TABLES=('tiers_payant_creances','tiers_payant_creances_versions')
PERMISSIONS=(
 ('tiers_payant.creance.consulter','Consulter les créances et dossiers administratifs autorisés'),
 ('tiers_payant.creance.constituer','Constituer les créances depuis les réalisations confirmées'),
 ('tiers_payant.creance.completer','Compléter les versions administratives des créances'),
 ('tiers_payant.creance.verifier','Contrôler les dossiers avant facturation'))


def fk(local,table,remote='id'):
    return sa.ForeignKeyConstraint([local,'organisation_id'],[f'{table}.{remote}',f'{table}.organisation_id'])


def common():
    return [sa.Column('id',sa.Uuid(),primary_key=True),sa.Column('organisation_id',sa.Uuid(),sa.ForeignKey('organisations.id_organisation'),nullable=False,index=True)]


def source_constraint(create):
    with op.batch_alter_table('tiers_payant_realisations') as b:
        if create:b.create_unique_constraint('uq_tp_realisation_source_scope',['id','vente_id','organisation_id','site_id'])
        else:b.drop_constraint('uq_tp_realisation_source_scope',type_='unique')
    if op.get_bind().dialect.name=='sqlite':
        from neosys_pharma.infrastructure.caisse_models import immutable_sql
        for sql in immutable_sql('tiers_payant_realisations','sqlite'):op.execute(sql)


def upgrade():
    source_constraint(True)
    op.create_table(TABLES[0],*common(),
        sa.Column('realisation_id',sa.Uuid(),nullable=False,index=True),sa.Column('vente_id',sa.Uuid(),nullable=False,index=True),
        sa.Column('site_id',sa.Uuid(),nullable=False,index=True),sa.Column('organisme_id',sa.Uuid(),nullable=False,index=True),
        sa.Column('montant_xaf',sa.Integer(),nullable=False),sa.Column('snapshot',sa.JSON(),nullable=False),
        sa.Column('snapshot_hash',sa.String(64),nullable=False),sa.Column('exigences',sa.JSON(),nullable=False),
        sa.Column('auteur_id',sa.Uuid(),nullable=False),sa.Column('cree_le',sa.DateTime(timezone=True),nullable=False),
        sa.UniqueConstraint('id','organisation_id',name='uq_tp_creance_org'),
        sa.UniqueConstraint('realisation_id','organisme_id',name='uq_tp_creance_source'),
        sa.ForeignKeyConstraint(['realisation_id','vente_id','organisation_id','site_id'],['tiers_payant_realisations.id','tiers_payant_realisations.vente_id','tiers_payant_realisations.organisation_id','tiers_payant_realisations.site_id'],name='fk_tp_creance_realisation_scope'),
        fk('organisme_id','organismes_prise_en_charge'),fk('auteur_id','utilisateurs','id_utilisateur'),
        sa.CheckConstraint('montant_xaf > 0',name='ck_tp_creance_montant'),sa.CheckConstraint('length(snapshot_hash) = 64',name='ck_tp_creance_hash'))
    op.create_table(TABLES[1],*common(),sa.Column('creance_id',sa.Uuid(),nullable=False,index=True),
        sa.Column('revision',sa.Integer(),nullable=False),sa.Column('etat',sa.String(30),nullable=False),
        sa.Column('complements',sa.JSON(),nullable=False),sa.Column('anomalies',sa.JSON(),nullable=False),
        sa.Column('motif',sa.String(2000),nullable=False),sa.Column('auteur_id',sa.Uuid(),nullable=False),
        sa.Column('cree_le',sa.DateTime(timezone=True),nullable=False),
        sa.UniqueConstraint('id','organisation_id',name='uq_tp_creance_version_org'),
        sa.UniqueConstraint('creance_id','revision',name='uq_tp_creance_revision'),fk('creance_id',TABLES[0]),fk('auteur_id','utilisateurs','id_utilisateur'),
        sa.CheckConstraint('revision > 0',name='ck_tp_creance_revision'),
        sa.CheckConstraint("etat IN ('A_COMPLETER','A_CONTROLER','VALIDE_POUR_FACTURATION','EN_ANOMALIE','FACTURE')",name='ck_tp_creance_etat'))
    from neosys_pharma.infrastructure.caisse_models import immutable_sql
    for table in TABLES:
        for sql in immutable_sql(table,op.get_bind().dialect.name):op.execute(sql)
    from neosys_pharma.domain.organisation.permissions_systeme import permission_id
    table=sa.table('permissions',sa.column('id_permission',sa.Uuid()),sa.column('code',sa.String()),sa.column('nom',sa.String()))
    for code,label in PERMISSIONS:
        if not op.get_bind().scalar(sa.select(table.c.id_permission).where(table.c.code==code)):
            op.bulk_insert(table,[{'id_permission':permission_id(code),'code':code,'nom':label}])


def downgrade():
    if any(op.get_bind().scalar(sa.text(f'SELECT count(*) FROM {table}')) for table in TABLES):
        raise RuntimeError('Downgrade refusé : créances ou historique administratif à conserver.')
    for table in reversed(TABLES):
        op.drop_table(table)
        if op.get_bind().dialect.name=='postgresql':op.execute(f'DROP FUNCTION {table}_immutable()')
    source_constraint(False)
    # Les permissions peuvent être liées à des rôles ; aucune attribution supprimée.
