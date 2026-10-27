"""Permission explicite d'administration des organismes, sans attribution.

Revision ID: 20261018_01
Revises: 20261017_03
"""
from uuid import UUID, uuid5
from alembic import op
import sqlalchemy as sa

revision = '20261018_01'
down_revision = '20261017_03'
branch_labels = None
depends_on = None
CODE = 'tiers_payant.organisme.gerer'
IDENT = uuid5(UUID('5e0d5c59-9934-40a6-b798-92d3f544667d'), 'permission:' + CODE)


def upgrade():
    permissions = sa.table('permissions', sa.column('id_permission', sa.Uuid()),
                           sa.column('code', sa.String()), sa.column('nom', sa.String()))
    op.bulk_insert(permissions, [{'id_permission': IDENT, 'code': CODE,
                                 'nom': 'Créer et modifier les organismes de prise en charge'}])


def downgrade():
    bind = op.get_bind()
    links = sa.table('roles_permissions', sa.column('permission_id', sa.Uuid()))
    if bind.scalar(sa.select(sa.func.count()).select_from(links).where(links.c.permission_id == IDENT)):
        raise RuntimeError('Retirer explicitement les affectations de la permission organisme avant downgrade.')
    permissions = sa.table('permissions', sa.column('id_permission', sa.Uuid()))
    bind.execute(permissions.delete().where(permissions.c.id_permission == IDENT))
