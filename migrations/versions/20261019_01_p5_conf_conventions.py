"""Configuration contractuelle et preuves documentaires immuables, additives."""
from alembic import op
import sqlalchemy as sa

revision = '20261019_01'
down_revision = '20261018_01'
branch_labels = None
depends_on = None
TABLES = ('tiers_payant_configurations_convention', 'tiers_payant_verifications_convention')


def upgrade():
    with op.batch_alter_table("tiers_payant_adhesions") as batch:
        batch.create_unique_constraint("uq_tp_adhesion_convention_scope", ["id", "organisation_id", "convention_id"])
    op.create_table(TABLES[0],
        sa.Column('id', sa.Uuid(), primary_key=True), sa.Column('organisation_id', sa.Uuid(), sa.ForeignKey('organisations.id_organisation'), nullable=False, index=True),
        sa.Column('convention_id', sa.Uuid(), nullable=False), sa.Column('schema_version', sa.Integer(), nullable=False),
        sa.Column('definition', sa.JSON(), nullable=False), sa.Column('auteur_id', sa.Uuid(), nullable=False),
        sa.Column('cree_le', sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint('convention_id', 'organisation_id', name='uq_tp_conf_convention'),
        sa.UniqueConstraint('id','organisation_id','convention_id', name='uq_tp_conf_scope'),
        sa.CheckConstraint('schema_version = 1', name='ck_tp_conf_schema'),
        sa.ForeignKeyConstraint(['convention_id','organisation_id'], ['tiers_payant_conventions.id','tiers_payant_conventions.organisation_id'], name='fk_tp_conf_convention_org'),
        sa.ForeignKeyConstraint(['auteur_id','organisation_id'], ['utilisateurs.id_utilisateur','utilisateurs.organisation_id'], name='fk_tp_conf_auteur_org'))
    op.create_table(TABLES[1],
        sa.Column('id', sa.Uuid(), primary_key=True), sa.Column('organisation_id', sa.Uuid(), sa.ForeignKey('organisations.id_organisation'), nullable=False, index=True),
        sa.Column('vente_id', sa.Uuid(), nullable=False), sa.Column('site_id', sa.Uuid(), nullable=False),
        sa.Column('configuration_id', sa.Uuid(), nullable=False), sa.Column('convention_id', sa.Uuid(), nullable=False),
        sa.Column('adhesion_id', sa.Uuid(), nullable=False), sa.Column('beneficiaire_id', sa.Uuid(), nullable=False),
        sa.Column('revision_adhesion', sa.Integer(), nullable=False), sa.Column('source', sa.String(20), nullable=False),
        sa.Column('reference', sa.String(200), nullable=False), sa.Column('resultat', sa.String(20), nullable=False),
        sa.Column('motif', sa.String(1000), nullable=False), sa.Column('date_verification', sa.Date(), nullable=False),
        sa.Column('date_fin', sa.Date(), nullable=False), sa.Column('valeurs', sa.JSON(), nullable=False),
        sa.Column('documents', sa.JSON(), nullable=False), sa.Column('auteur_id', sa.Uuid(), nullable=False),
        sa.Column('cree_le', sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint('revision_adhesion > 0', name='ck_tp_verif_revision'),
        sa.CheckConstraint("resultat IN ('CONFIRME','REFUSE')", name='ck_tp_verif_resultat'),
        sa.CheckConstraint("source IN ('LISTE','IDENTIFICATION','EXTERNE')", name='ck_tp_verif_source'),
        sa.CheckConstraint('date_fin >= date_verification', name='ck_tp_verif_periode'),
        sa.ForeignKeyConstraint(['configuration_id','organisation_id','convention_id'], [TABLES[0]+'.id',TABLES[0]+'.organisation_id',TABLES[0]+'.convention_id'], name='fk_tp_verif_configuration_scope'),
        sa.ForeignKeyConstraint(['adhesion_id','organisation_id','convention_id'], ['tiers_payant_adhesions.id','tiers_payant_adhesions.organisation_id','tiers_payant_adhesions.convention_id'], name='fk_tp_verif_adhesion_org'),
        sa.ForeignKeyConstraint(['adhesion_id','beneficiaire_id'], ['tiers_payant_adhesion_beneficiaires.adhesion_id','tiers_payant_adhesion_beneficiaires.beneficiaire_id'], name='fk_tp_verif_lien_beneficiaire'),
        sa.ForeignKeyConstraint(['beneficiaire_id','organisation_id'], ['tiers_payant_beneficiaires.id','tiers_payant_beneficiaires.organisation_id'], name='fk_tp_verif_benef_org'),
        sa.ForeignKeyConstraint(['vente_id','organisation_id','site_id'], ['ventes.id','ventes.organisation_id','ventes.site_id'], name='fk_tp_verif_vente_site_org'),
        sa.ForeignKeyConstraint(['auteur_id','organisation_id'], ['utilisateurs.id_utilisateur','utilisateurs.organisation_id'], name='fk_tp_verif_auteur_org'))
    op.create_index('ix_tp_verif_benef_adhesion', TABLES[1], ['organisation_id','beneficiaire_id','adhesion_id','cree_le'])
    for table in TABLES:
        if op.get_bind().dialect.name == 'sqlite':
            for action in ('UPDATE','DELETE'):
                op.execute(f"CREATE TRIGGER {table}_{action.lower()}_immutable BEFORE {action} ON {table} BEGIN SELECT RAISE(ABORT, 'Configuration et preuve immuables'); END")
        else:
            op.execute(f"CREATE FUNCTION {table}_immutable() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN RAISE EXCEPTION 'Configuration et preuve immuables'; END $$")
            op.execute(f'CREATE TRIGGER {table}_immutable BEFORE UPDATE OR DELETE ON {table} FOR EACH ROW EXECUTE FUNCTION {table}_immutable()')


def downgrade():
    # Pas de suppression automatique de preuves ou configurations déjà utilisées.
    for table in reversed(TABLES):
        if op.get_bind().scalar(sa.text(f'SELECT count(*) FROM {table}')):
            raise RuntimeError('Downgrade refusé : configurations ou preuves à conserver.')
    for table in reversed(TABLES):
        op.drop_table(table)
        if op.get_bind().dialect.name == 'postgresql':
            op.execute(f'DROP FUNCTION {table}_immutable()')

    with op.batch_alter_table("tiers_payant_adhesions") as batch:
        batch.drop_constraint("uq_tp_adhesion_convention_scope", type_="unique")
