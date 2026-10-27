"""Numéro/code-barres distincts, registre unique et documents immuables des cartes."""
from alembic import op
import sqlalchemy as sa
revision='20261019_03'
down_revision='20261019_02'
branch_labels=None
depends_on=None

def upgrade():
    checks=sa.inspect(op.get_bind()).get_check_constraints('fidelite_cartes')
    preserved=tuple(sa.CheckConstraint(c['sqltext'],name='ck_carte_historique_'+str(i)) for i,c in enumerate(checks) if c['name'] is None) if op.get_bind().dialect.name=='sqlite' else ()
    with op.batch_alter_table('fidelite_cartes',table_args=preserved) as b:
        b.add_column(sa.Column('code_barres',sa.String(80),nullable=True))
        b.create_check_constraint('ck_carte_barres_physique',"code_barres IS NULL OR (type='PHYSIQUE' AND length(trim(code_barres)) > 0)")
    op.create_table('fidelite_cartes_identifiants',
        sa.Column('organisation_id',sa.Uuid(),sa.ForeignKey('organisations.id_organisation'),primary_key=True),
        sa.Column('valeur',sa.String(200),primary_key=True),sa.Column('carte_id',sa.Uuid(),nullable=False),
        sa.ForeignKeyConstraint(['carte_id','organisation_id'],['fidelite_cartes.id','fidelite_cartes.organisation_id'],name='fk_identifiant_carte_org'),
        sa.CheckConstraint('length(valeur) > 0',name='ck_identifiant_non_vide'))
    op.create_index('ix_fidelite_cartes_identifiants_carte_id','fidelite_cartes_identifiants',['carte_id'])
    op.create_table('fidelite_cartes_documents',
        sa.Column('id',sa.Uuid(),primary_key=True),sa.Column('organisation_id',sa.Uuid(),sa.ForeignKey('organisations.id_organisation'),nullable=False,index=True),
        sa.Column('carte_id',sa.Uuid(),nullable=False),sa.Column('auteur_id',sa.Uuid(),nullable=False),
        sa.Column('instantane',sa.JSON(),nullable=False),sa.Column('pdf',sa.LargeBinary(),nullable=False),sa.Column('pdf_sha256',sa.String(64),nullable=False),sa.Column('date',sa.DateTime(timezone=True),nullable=False),
        sa.UniqueConstraint('id','organisation_id',name='uq_document_carte_org'),sa.UniqueConstraint('carte_id',name='uq_document_carte'),
        sa.ForeignKeyConstraint(['carte_id','organisation_id'],['fidelite_cartes.id','fidelite_cartes.organisation_id'],name='fk_document_carte_org'),
        sa.ForeignKeyConstraint(['auteur_id','organisation_id'],['utilisateurs.id_utilisateur','utilisateurs.organisation_id'],name='fk_document_carte_auteur_org'))
    op.execute('INSERT INTO fidelite_cartes_identifiants(organisation_id,valeur,carte_id) SELECT organisation_id,code,id FROM fidelite_cartes')
    from neosys_pharma.infrastructure.caisse_models import cartes_identifiants_sql
    for sql in cartes_identifiants_sql(op.get_bind().dialect.name):op.execute(sql)

def downgrade():
    c=op.get_bind()
    if c.scalar(sa.text('SELECT count(*) FROM fidelite_cartes_documents')) or c.scalar(sa.text('SELECT count(*) FROM fidelite_cartes WHERE code_barres IS NOT NULL')):
        raise RuntimeError('Downgrade refusé : codes-barres ou documents historiques à conserver.')
    if c.dialect.name=='sqlite':
        for trigger in ('carte_identifiants_insert','carte_barres_insert','carte_identite_immutable','carte_delete_immutable'):
            op.execute(f'DROP TRIGGER {trigger}')
    else:
        op.execute('DROP TRIGGER carte_identifiants_register ON fidelite_cartes')
        op.execute('DROP TRIGGER carte_identite_guard ON fidelite_cartes')
    op.drop_table('fidelite_cartes_documents');op.drop_table('fidelite_cartes_identifiants')
    if c.dialect.name=='postgresql':
        for fn in ('carte_identifiants_register','carte_identite_guard','carte_alias_valide','fidelite_cartes_identifiants_immutable','fidelite_cartes_documents_immutable'):op.execute(f'DROP FUNCTION {fn}()')
    with op.batch_alter_table('fidelite_cartes') as b:
        b.drop_constraint('ck_carte_barres_physique',type_='check');b.drop_column('code_barres')
