"""P4-05 MIG-02 : annulation auditée et remplacement explicite, aucun paiement."""
from alembic import op
import sqlalchemy as sa
from uuid import UUID,uuid5

revision='20261022_02'
down_revision='20261022_01'
branch_labels=None
depends_on=None
TABLE='finance_remboursements'
PERMISSION='caisse.remboursement.annuler'
PID=uuid5(UUID('5e0d5c59-9934-40a6-b798-92d3f544667d'),'permission:'+PERMISSION)


def guard(extended):
    dialect=op.get_bind().dialect.name
    columns=('organisation_id','id','site_id','retour_id','confirmation_id','session_id','montant','reglements','demandeur_id','justification','date')+ (('remplace_id',) if extended else ())
    states="'EXECUTE','ANNULE'" if extended else "'EXECUTE'"
    if dialect=='sqlite':
        changed=' OR '.join(f'NEW.{c} IS NOT OLD.{c}' for c in columns)
        op.execute(f"CREATE TRIGGER {TABLE}_guard_update BEFORE UPDATE ON {TABLE} WHEN OLD.etat IN ({states}) OR {changed} BEGIN SELECT RAISE(ABORT,'Dossier financier historique immuable'); END")
        op.execute(f"CREATE TRIGGER {TABLE}_guard_delete BEFORE DELETE ON {TABLE} BEGIN SELECT RAISE(ABORT,'Dossier financier historique immuable'); END")
    else:
        changed=' OR '.join(f'NEW.{c}::text IS DISTINCT FROM OLD.{c}::text' for c in columns)
        op.execute(f"CREATE OR REPLACE FUNCTION {TABLE}_guard() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN IF TG_OP='DELETE' THEN RAISE EXCEPTION 'Dossier financier historique immuable'; END IF; IF OLD.etat IN ({states}) OR {changed} THEN RAISE EXCEPTION 'Dossier financier historique immuable'; END IF; RETURN NEW; END $$")
        op.execute(f'CREATE TRIGGER {TABLE}_guard BEFORE UPDATE OR DELETE ON {TABLE} FOR EACH ROW EXECUTE FUNCTION {TABLE}_guard()')


def drop_guard():
    if op.get_bind().dialect.name=='sqlite':
        op.execute(f'DROP TRIGGER IF EXISTS {TABLE}_guard_update');op.execute(f'DROP TRIGGER IF EXISTS {TABLE}_guard_delete')
    else:op.execute(f'DROP TRIGGER IF EXISTS {TABLE}_guard ON {TABLE}')


def upgrade():
    bind=op.get_bind();ins=sa.inspect(bind);sqlite=bind.dialect.name=='sqlite'
    checks=ins.get_check_constraints(TABLE);uniques=ins.get_unique_constraints(TABLE)
    # SQLite reflection omet les CHECK anonymes : conserver les invariants initiaux.
    preserved=tuple(sa.CheckConstraint(c['sqltext']) for c in checks if sqlite and c['name'] is None and 'etat' not in c['sqltext'])
    drop_guard()
    with op.batch_alter_table(TABLE,naming_convention={'uq':'uq_%(table_name)s_%(column_0_name)s'},table_args=preserved) as b:
        for u in uniques:
            if u['column_names'] in (['retour_id'],['confirmation_id']):
                b.drop_constraint(u['name'] or 'uq_'+TABLE+'_'+u['column_names'][0],type_='unique')
        for c in checks:
            if 'etat' in c['sqltext'] and c['name']:b.drop_constraint(c['name'],type_='check')
        b.add_column(sa.Column('remplace_id',sa.Uuid(),nullable=True))
        b.create_foreign_key('fk_remboursement_remplace_org',TABLE,['remplace_id','organisation_id'],['id','organisation_id'])
        b.create_unique_constraint('uq_remboursement_remplacement',['remplace_id'])
        b.create_check_constraint('ck_remboursement_etat',"etat IN ('DEMANDE','AUTORISE','EXECUTE','ANNULE')")
        b.create_check_constraint('ck_remboursement_non_autoremplacement','remplace_id IS NULL OR remplace_id <> id')
        for column,name in (('retour_id','uq_remboursement_retour_actif'),('confirmation_id','uq_remboursement_confirmation_active')):
            b.create_index(name,[column],unique=True,sqlite_where=sa.text("etat <> 'ANNULE'"),postgresql_where=sa.text("etat <> 'ANNULE'"))
    guard(True)
    op.create_table('finance_annulations_remboursement',
        sa.Column('id',sa.Uuid(),primary_key=True),
        sa.Column('organisation_id',sa.Uuid(),sa.ForeignKey('organisations.id_organisation'),nullable=False,index=True),
        sa.Column('remboursement_id',sa.Uuid(),nullable=False),sa.Column('auteur_id',sa.Uuid(),nullable=False),
        sa.Column('justification',sa.String(2000),nullable=False),sa.Column('attestation_absence_restitution',sa.Boolean(),nullable=False),
        sa.Column('revision_avant',sa.Integer(),nullable=False),sa.Column('revision_apres',sa.Integer(),nullable=False),
        sa.Column('instantane',sa.JSON(),nullable=False),sa.Column('date',sa.DateTime(timezone=True),nullable=False),
        sa.ForeignKeyConstraint(['remboursement_id','organisation_id'],[TABLE+'.id',TABLE+'.organisation_id']),
        sa.ForeignKeyConstraint(['auteur_id','organisation_id'],['utilisateurs.id_utilisateur','utilisateurs.organisation_id']),
        sa.UniqueConstraint('id','organisation_id',name='uq_annulation_remboursement_org'),
        sa.UniqueConstraint('remboursement_id',name='uq_annulation_remboursement'),
        sa.CheckConstraint('revision_apres = revision_avant + 1 AND revision_avant > 0',name='ck_annulation_revisions'),
        sa.CheckConstraint('attestation_absence_restitution AND length(trim(justification)) > 0',name='ck_annulation_attestation'))
    from neosys_pharma.infrastructure.caisse_models import immutable_sql
    for sql in immutable_sql('finance_annulations_remboursement',bind.dialect.name):op.execute(sql)
    permissions=sa.table('permissions',sa.column('id_permission',sa.Uuid()),sa.column('code',sa.String()),sa.column('nom',sa.String()))
    op.bulk_insert(permissions,[{'id_permission':PID,'code':PERMISSION,'nom':'Annuler une demande de remboursement non exécutée avec attestation responsable'}])


def downgrade():
    bind=op.get_bind()
    if bind.scalar(sa.text("SELECT count(*) FROM finance_remboursements WHERE etat='ANNULE' OR remplace_id IS NOT NULL")) or bind.scalar(sa.text('SELECT count(*) FROM finance_annulations_remboursement')):
        raise RuntimeError('Downgrade refusé : annulations et remplacements historiques à conserver.')
    # Ne pas retirer une permission attribuée explicitement sans décision dédiée.
    if bind.scalar(sa.text('SELECT count(*) FROM roles_permissions WHERE permission_id=:pid').bindparams(sa.bindparam('pid',PID,type_=sa.Uuid()))):
        raise RuntimeError('Downgrade refusé : permission d’annulation attribuée.')
    bind.execute(sa.text('DELETE FROM permissions WHERE id_permission=:pid').bindparams(sa.bindparam('pid',PID,type_=sa.Uuid())))
    op.drop_table('finance_annulations_remboursement')
    if bind.dialect.name=='postgresql':op.execute('DROP FUNCTION finance_annulations_remboursement_immutable()')
    drop_guard()
    checks=sa.inspect(bind).get_check_constraints(TABLE)
    preserved=tuple(sa.CheckConstraint(c['sqltext']) for c in checks if bind.dialect.name=='sqlite' and c['name'] is None)
    with op.batch_alter_table(TABLE,table_args=preserved) as b:
        b.drop_index('uq_remboursement_retour_actif');b.drop_index('uq_remboursement_confirmation_active')
        b.drop_constraint('fk_remboursement_remplace_org',type_='foreignkey')
        b.drop_constraint('uq_remboursement_remplacement',type_='unique')
        b.drop_constraint('ck_remboursement_non_autoremplacement',type_='check')
        b.drop_constraint('ck_remboursement_etat',type_='check')
        b.drop_column('remplace_id')
        b.create_check_constraint('ck_remboursement_etat',"etat IN ('DEMANDE','AUTORISE','EXECUTE')")
        b.create_unique_constraint('uq_finance_remboursements_retour_id',['retour_id'])
        b.create_unique_constraint('uq_finance_remboursements_confirmation_id',['confirmation_id'])
    guard(False)
