"""Origines de listes immuables ; aucun droit ou adhésion créé par l'import."""
from alembic import op
import sqlalchemy as sa
revision='20261019_04'
down_revision='20261019_03'
branch_labels=None
depends_on=None
TABLE='tiers_payant_origines_import_beneficiaires'

def upgrade():
    op.create_table(TABLE,
        sa.Column('id',sa.Uuid(),primary_key=True),sa.Column('organisation_id',sa.Uuid(),sa.ForeignKey('organisations.id_organisation'),nullable=False,index=True),
        sa.Column('organisme_id',sa.Uuid(),nullable=False),sa.Column('beneficiaire_id',sa.Uuid(),nullable=False,index=True),
        sa.Column('reference_externe',sa.String(200),nullable=False),sa.Column('empreinte_ligne',sa.String(64),nullable=False),sa.Column('empreinte_fichier',sa.String(64),nullable=False),
        sa.Column('nom_fichier',sa.String(200),nullable=False),sa.Column('donnees',sa.JSON(),nullable=False),sa.Column('auteur_id',sa.Uuid(),nullable=False),sa.Column('cree_le',sa.DateTime(timezone=True),nullable=False),
        sa.UniqueConstraint('id','organisation_id',name='uq_tp_import_benef_org'),sa.UniqueConstraint('organisation_id','organisme_id','reference_externe',name='uq_tp_import_benef_source'),
        sa.ForeignKeyConstraint(['organisme_id','organisation_id'],['organismes_prise_en_charge.id','organismes_prise_en_charge.organisation_id'],name='fk_tp_import_benef_organisme'),
        sa.ForeignKeyConstraint(['beneficiaire_id','organisation_id'],['tiers_payant_beneficiaires.id','tiers_payant_beneficiaires.organisation_id'],name='fk_tp_import_benef_personne'),
        sa.ForeignKeyConstraint(['auteur_id','organisation_id'],['utilisateurs.id_utilisateur','utilisateurs.organisation_id'],name='fk_tp_import_benef_auteur'),
        sa.CheckConstraint('length(empreinte_ligne)=64 AND length(empreinte_fichier)=64',name='ck_tp_import_benef_hash'))
    from neosys_pharma.infrastructure.caisse_models import immutable_sql
    for sql in immutable_sql(TABLE,op.get_bind().dialect.name):op.execute(sql)

def downgrade():
    if op.get_bind().scalar(sa.text(f'SELECT count(*) FROM {TABLE}')):raise RuntimeError('Downgrade refusé : provenances à conserver.')
    op.drop_table(TABLE)
    if op.get_bind().dialect.name=='postgresql':op.execute(f'DROP FUNCTION {TABLE}_immutable()')
