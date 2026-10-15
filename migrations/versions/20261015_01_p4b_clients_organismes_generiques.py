"""P4-B: fiches client indépendantes et associations génériques aux organismes.

Revision ID: 20261015_01
Revises: f22f6abb13c5
"""
from uuid import UUID, uuid4, uuid5

from alembic import op
import sqlalchemy as sa

revision = '20261015_01'
down_revision = 'f22f6abb13c5'
branch_labels = None
depends_on = None

_NAMESPACE = UUID('5e0d5c59-9934-40a6-b798-92d3f544667d')
_PERMISSIONS = (
    ('client.consulter', 'Consulter les fiches client et leurs organismes associés'),
    ('client.gerer', 'Créer et modifier les fiches client et leurs associations'),
)


def _drop_sale_guards(bind):
    if bind.dialect.name != 'sqlite':
        return
    for table in ('ventes', 'vente_lignes', 'vente_demandes_remise'):
        for action in ('insert', 'update', 'delete'):
            bind.exec_driver_sql(f'DROP TRIGGER IF EXISTS {table}_paye_{action}')


def _create_sale_guards(bind):
    if bind.dialect.name != 'sqlite':
        return
    from neosys_pharma.infrastructure.caisse_models import paid_guard_sql
    for statement in paid_guard_sql('sqlite'):
        bind.exec_driver_sql(statement)


def upgrade():
    op.create_table(
        'clients',
        sa.Column('nom', sa.String(200), nullable=False),
        sa.Column('telephone', sa.String(80), nullable=True),
        sa.Column('courriel', sa.String(254), nullable=True),
        sa.Column('actif', sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column('revision', sa.Integer(), nullable=False, server_default='1'),
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('organisation_id', sa.Uuid(), nullable=False),
        sa.CheckConstraint('revision > 0'),
        sa.ForeignKeyConstraint(['organisation_id'], ['organisations.id_organisation']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('id', 'organisation_id', name='uq_client_org'),
    )
    op.create_index('ix_clients_organisation_id', 'clients', ['organisation_id'])
    op.create_index('ix_clients_telephone', 'clients', ['telephone'])

    op.create_table(
        'organismes_prise_en_charge',
        sa.Column('code', sa.String(80), nullable=False),
        sa.Column('nom', sa.String(200), nullable=False),
        sa.Column('actif', sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column('revision', sa.Integer(), nullable=False, server_default='1'),
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('organisation_id', sa.Uuid(), nullable=False),
        sa.CheckConstraint('revision > 0'),
        sa.ForeignKeyConstraint(['organisation_id'], ['organisations.id_organisation']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('id', 'organisation_id', name='uq_organisme_couverture_org'),
        sa.UniqueConstraint('organisation_id', 'code'),
    )
    op.create_index('ix_organismes_prise_en_charge_organisation_id', 'organismes_prise_en_charge', ['organisation_id'])

    op.create_table(
        'clients_organismes_prise_en_charge',
        sa.Column('client_id', sa.Uuid(), nullable=False),
        sa.Column('organisme_id', sa.Uuid(), nullable=False),
        sa.Column('role', sa.String(20), nullable=False),
        sa.Column('reference', sa.String(200), nullable=True),
        sa.Column('actif', sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('organisation_id', sa.Uuid(), nullable=False),
        sa.CheckConstraint("role IN ('PRINCIPAL','COMPLEMENTAIRE')", name='ck_client_organisme_role'),
        sa.ForeignKeyConstraint(['client_id','organisation_id'], ['clients.id','clients.organisation_id'], name='fk_client_organisme_client_org'),
        sa.ForeignKeyConstraint(['organisme_id','organisation_id'], ['organismes_prise_en_charge.id','organismes_prise_en_charge.organisation_id'], name='fk_client_organisme_organisme_org'),
        sa.ForeignKeyConstraint(['organisation_id'], ['organisations.id_organisation']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('client_id', 'organisme_id', name='uq_client_organisme'),
    )
    op.create_index('ix_clients_organismes_prise_en_charge_organisation_id', 'clients_organismes_prise_en_charge', ['organisation_id'])
    op.create_index('ix_clients_organismes_prise_en_charge_client_id', 'clients_organismes_prise_en_charge', ['client_id'])
    op.create_index('ix_clients_organismes_prise_en_charge_organisme_id', 'clients_organismes_prise_en_charge', ['organisme_id'])
    op.create_index('uq_client_organisme_principal', 'clients_organismes_prise_en_charge', ['client_id'], unique=True, sqlite_where=sa.text("role='PRINCIPAL' AND actif=1"), postgresql_where=sa.text("role='PRINCIPAL' AND actif=true"))

    bind = op.get_bind()
    _drop_sale_guards(bind)
    with op.batch_alter_table('fidelite_clients') as batch:
        batch.add_column(sa.Column('profil_client_id', sa.Uuid(), nullable=True))
        batch.create_foreign_key('fk_fidelite_client_profil', 'clients', ['profil_client_id','organisation_id'], ['id','organisation_id'])
    op.create_index('uq_fidelite_client_profil', 'fidelite_clients', ['profil_client_id'], unique=True)
    with op.batch_alter_table('ventes') as batch:
        batch.add_column(sa.Column('client_id', sa.Uuid(), nullable=True))
        batch.create_foreign_key('fk_vente_client', 'clients', ['client_id','organisation_id'], ['id','organisation_id'])
    _create_sale_guards(bind)
    op.create_index('ix_ventes_client_id', 'ventes', ['client_id'])

    # Créer un profil canonique pour chaque client fidélité existant, sans fusionner les personnes.
    fidelity = sa.table('fidelite_clients', sa.column('id', sa.Uuid()), sa.column('organisation_id', sa.Uuid()), sa.column('nom', sa.String()), sa.column('telephone', sa.String()), sa.column('profil_client_id', sa.Uuid()))
    profiles = sa.table('clients', sa.column('id', sa.Uuid()), sa.column('organisation_id', sa.Uuid()), sa.column('nom', sa.String()), sa.column('telephone', sa.String()), sa.column('courriel', sa.String()), sa.column('actif', sa.Boolean()), sa.column('revision', sa.Integer()))
    for row in bind.execute(sa.select(fidelity.c.id, fidelity.c.organisation_id, fidelity.c.nom, fidelity.c.telephone)).mappings():
        profile_id = uuid4()
        bind.execute(sa.insert(profiles).values(id=profile_id, organisation_id=row['organisation_id'], nom=row['nom'], telephone=row['telephone'], courriel=None, actif=True, revision=1))
        bind.execute(sa.update(fidelity).where(fidelity.c.id == row['id']).values(profil_client_id=profile_id))

    permission_table = sa.table('permissions', sa.column('id_permission', sa.Uuid()), sa.column('code', sa.String()), sa.column('nom', sa.String()))
    for code, name in _PERMISSIONS:
        if not bind.execute(sa.select(permission_table.c.id_permission).where(permission_table.c.code == code)).first():
            bind.execute(sa.insert(permission_table).values(id_permission=uuid5(_NAMESPACE, 'permission:' + code), code=code, nom=name))


def downgrade():
    bind = op.get_bind()
    role_permissions = sa.table('roles_permissions', sa.column('permission_id', sa.Uuid()))
    permissions = sa.table('permissions', sa.column('id_permission', sa.Uuid()), sa.column('code', sa.String()))
    for code, _ in _PERMISSIONS:
        permission_id = uuid5(_NAMESPACE, 'permission:' + code)
        bind.execute(sa.delete(role_permissions).where(role_permissions.c.permission_id == permission_id))
        bind.execute(sa.delete(permissions).where(permissions.c.id_permission == permission_id))

    op.drop_index('ix_ventes_client_id', table_name='ventes')
    bind = op.get_bind()
    _drop_sale_guards(bind)
    with op.batch_alter_table('ventes') as batch:
        batch.drop_constraint('fk_vente_client', type_='foreignkey')
        batch.drop_column('client_id')
    op.drop_index('uq_fidelite_client_profil', table_name='fidelite_clients')
    with op.batch_alter_table('fidelite_clients') as batch:
        batch.drop_constraint('fk_fidelite_client_profil', type_='foreignkey')
        batch.drop_column('profil_client_id')
    _create_sale_guards(bind)
    op.drop_index('uq_client_organisme_principal', table_name='clients_organismes_prise_en_charge')
    op.drop_index('ix_clients_organismes_prise_en_charge_organisme_id', table_name='clients_organismes_prise_en_charge')
    op.drop_index('ix_clients_organismes_prise_en_charge_client_id', table_name='clients_organismes_prise_en_charge')
    op.drop_index('ix_clients_organismes_prise_en_charge_organisation_id', table_name='clients_organismes_prise_en_charge')
    op.drop_table('clients_organismes_prise_en_charge')
    op.drop_index('ix_organismes_prise_en_charge_organisation_id', table_name='organismes_prise_en_charge')
    op.drop_table('organismes_prise_en_charge')
    op.drop_index('ix_clients_telephone', table_name='clients')
    op.drop_index('ix_clients_organisation_id', table_name='clients')
    op.drop_table('clients')
