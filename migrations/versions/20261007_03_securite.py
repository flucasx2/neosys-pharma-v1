"""P1 users contextual roles and permissions

Revision ID: 20261007_03
Revises: 20261007_02
Create Date: 2026-10-07 12:22:33.249547

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from uuid import UUID, uuid5


# revision identifiers, used by Alembic.
revision: str = '20261007_03'
down_revision: Union[str, Sequence[str], None] = '20261007_02'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""

    with op.batch_alter_table("sites") as batch:
        batch.create_unique_constraint("uq_site_organisation_parent", ["id_site", "organisation_id"])
    with op.batch_alter_table("emplacements") as batch:
        batch.create_unique_constraint("uq_emplacement_site_parent", ["id_emplacement", "site_id"])
    op.create_table('permissions',
    sa.Column('id_permission', sa.Uuid(), nullable=False),
    sa.Column('code', sa.String(length=120), nullable=False),
    sa.Column('nom', sa.String(length=200), nullable=False),
    sa.PrimaryKeyConstraint('id_permission'),
    sa.UniqueConstraint('code')
    )
    op.create_table('roles',
    sa.Column('id_role', sa.Uuid(), nullable=False),
    sa.Column('organisation_id', sa.Uuid(), nullable=True),
    sa.Column('scope_id', sa.String(length=40), sa.Computed("CASE WHEN organisation_id IS NULL THEN 'systeme' ELSE CAST(organisation_id AS VARCHAR) END", persisted=True), nullable=False),
    sa.Column('code', sa.String(length=80), nullable=False),
    sa.Column('nom', sa.String(length=200), nullable=False),
    sa.Column('type_role', sa.String(length=20), nullable=False),
    sa.Column('actif', sa.Boolean(), nullable=False),
    sa.CheckConstraint("(type_role = 'SYSTEME' AND organisation_id IS NULL) OR (type_role = 'PERSONNALISE' AND organisation_id IS NOT NULL)", name='ck_role_portee'),
    sa.ForeignKeyConstraint(['organisation_id'], ['organisations.id_organisation'], ),
    sa.PrimaryKeyConstraint('id_role'),
    sa.UniqueConstraint('id_role', 'scope_id', name='uq_role_scope'),
    sa.UniqueConstraint('scope_id', 'code', name='uq_role_scope_code')
    )
    op.create_index(op.f('ix_roles_organisation_id'), 'roles', ['organisation_id'], unique=False)
    op.create_table('utilisateurs',
    sa.Column('id_utilisateur', sa.Uuid(), nullable=False),
    sa.Column('organisation_id', sa.Uuid(), nullable=False),
    sa.Column('identifiant', sa.String(length=80), nullable=False),
    sa.Column('nom', sa.String(length=200), nullable=False),
    sa.Column('email', sa.String(length=254), nullable=True),
    sa.Column('actif', sa.Boolean(), nullable=False),
    sa.ForeignKeyConstraint(['organisation_id'], ['organisations.id_organisation'], ),
    sa.PrimaryKeyConstraint('id_utilisateur'),
    sa.UniqueConstraint('id_utilisateur', 'organisation_id', name='uq_utilisateur_organisation'),
    sa.UniqueConstraint('organisation_id', 'identifiant', name='uq_utilisateur_identifiant')
    )
    op.create_index(op.f('ix_utilisateurs_organisation_id'), 'utilisateurs', ['organisation_id'], unique=False)
    op.create_table('affectations_site',
    sa.Column('id_affectation_site', sa.Uuid(), nullable=False),
    sa.Column('utilisateur_id', sa.Uuid(), nullable=False),
    sa.Column('site_id', sa.Uuid(), nullable=False),
    sa.Column('organisation_id', sa.Uuid(), nullable=False),
    sa.Column('date_debut', sa.Date(), nullable=False),
    sa.Column('date_fin', sa.Date(), nullable=True),
    sa.Column('actif', sa.Boolean(), nullable=False),
    sa.CheckConstraint('date_fin IS NULL OR date_fin >= date_debut', name='ck_affectation_periode'),
    sa.ForeignKeyConstraint(['site_id', 'organisation_id'], ['sites.id_site', 'sites.organisation_id'], name='fk_affectation_site_organisation'),
    sa.ForeignKeyConstraint(['utilisateur_id', 'organisation_id'], ['utilisateurs.id_utilisateur', 'utilisateurs.organisation_id'], name='fk_affectation_utilisateur_organisation'),
    sa.PrimaryKeyConstraint('id_affectation_site'),
    sa.UniqueConstraint('id_affectation_site', 'organisation_id', name='uq_affectation_organisation'),
    sa.UniqueConstraint('id_affectation_site', 'site_id', name='uq_affectation_site_parent'),
    sa.UniqueConstraint('utilisateur_id', 'site_id', 'date_debut', name='uq_affectation_site_debut')
    )
    op.create_index(op.f('ix_affectations_site_site_id'), 'affectations_site', ['site_id'], unique=False)
    op.create_index(op.f('ix_affectations_site_utilisateur_id'), 'affectations_site', ['utilisateur_id'], unique=False)
    op.create_table('roles_permissions',
    sa.Column('role_id', sa.Uuid(), nullable=False),
    sa.Column('permission_id', sa.Uuid(), nullable=False),
    sa.ForeignKeyConstraint(['permission_id'], ['permissions.id_permission'], ),
    sa.ForeignKeyConstraint(['role_id'], ['roles.id_role'], ),
    sa.PrimaryKeyConstraint('role_id', 'permission_id')
    )
    op.create_table('affectations_emplacement',
    sa.Column('affectation_site_id', sa.Uuid(), nullable=False),
    sa.Column('emplacement_id', sa.Uuid(), nullable=False),
    sa.Column('site_id', sa.Uuid(), nullable=False),
    sa.ForeignKeyConstraint(['affectation_site_id', 'site_id'], ['affectations_site.id_affectation_site', 'affectations_site.site_id'], name='fk_emplacement_affectation_site'),
    sa.ForeignKeyConstraint(['emplacement_id', 'site_id'], ['emplacements.id_emplacement', 'emplacements.site_id'], name='fk_emplacement_meme_site'),
    sa.PrimaryKeyConstraint('affectation_site_id', 'emplacement_id')
    )
    op.create_table('affectations_role',
    sa.Column('affectation_site_id', sa.Uuid(), nullable=False),
    sa.Column('role_id', sa.Uuid(), nullable=False),
    sa.Column('organisation_id', sa.Uuid(), nullable=False),
    sa.Column('role_scope', sa.String(length=40), nullable=False),
    sa.CheckConstraint("role_scope = 'systeme' OR role_scope = CAST(organisation_id AS VARCHAR)", name='ck_affectation_role_organisation'),
    sa.ForeignKeyConstraint(['affectation_site_id', 'organisation_id'], ['affectations_site.id_affectation_site', 'affectations_site.organisation_id'], name='fk_role_affectation_organisation'),
    sa.ForeignKeyConstraint(['role_id', 'role_scope'], ['roles.id_role', 'roles.scope_id'], name='fk_affectation_role_scope'),
    sa.PrimaryKeyConstraint('affectation_site_id', 'role_id')
    )
    seed_catalogue()
    # ### end Alembic commands ###


def downgrade() -> None:
    """Downgrade schema."""
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_table('affectations_role')
    op.drop_table('affectations_emplacement')
    op.drop_table('roles_permissions')
    op.drop_index(op.f('ix_affectations_site_utilisateur_id'), table_name='affectations_site')
    op.drop_index(op.f('ix_affectations_site_site_id'), table_name='affectations_site')
    op.drop_table('affectations_site')
    op.drop_index(op.f('ix_utilisateurs_organisation_id'), table_name='utilisateurs')
    op.drop_table('utilisateurs')
    op.drop_index(op.f('ix_roles_organisation_id'), table_name='roles')
    op.drop_table('roles')
    op.drop_table('permissions')
    with op.batch_alter_table('emplacements') as batch:
        batch.drop_constraint('uq_emplacement_site_parent', type_='unique')
    with op.batch_alter_table('sites') as batch:
        batch.drop_constraint('uq_site_organisation_parent', type_='unique')
    # ### end Alembic commands ###



NAMESPACE = UUID("5e0d5c59-9934-40a6-b798-92d3f544667d")
PERMISSIONS = (
    ("organisation.consulter", "Consulter l'organisation et sa structure"),
    ("organisation.gerer", "Gérer l'organisation et sa structure"),
    ("utilisateur.consulter", "Consulter les utilisateurs"),
    ("utilisateur.gerer", "Gérer les utilisateurs"),
    ("affectation.gerer", "Gérer les affectations et leurs périmètres"),
    ("role.consulter", "Consulter les rôles et permissions"),
    ("role.gerer", "Gérer les rôles personnalisés"),
)
ROLES = (
    ("OBSERVATEUR", "Observateur", ("organisation.consulter", "utilisateur.consulter", "role.consulter")),
    ("GESTION_ORGANISATION", "Gestion de l'organisation", tuple(code for code, _ in PERMISSIONS)),
)



def seed_catalogue():
    permissions = sa.table('permissions', sa.column('id_permission', sa.Uuid()), sa.column('code', sa.String()), sa.column('nom', sa.String()))
    roles = sa.table('roles', sa.column('id_role', sa.Uuid()), sa.column('organisation_id', sa.Uuid()), sa.column('code', sa.String()), sa.column('nom', sa.String()), sa.column('type_role', sa.String()), sa.column('actif', sa.Boolean()))
    links = sa.table('roles_permissions', sa.column('role_id', sa.Uuid()), sa.column('permission_id', sa.Uuid()))
    op.bulk_insert(permissions, [{'id_permission': uuid5(NAMESPACE, 'permission:' + code), 'code': code, 'nom': nom} for code, nom in PERMISSIONS])
    op.bulk_insert(roles, [{'id_role': uuid5(NAMESPACE, 'role:' + code), 'organisation_id': None, 'code': code, 'nom': nom, 'type_role': 'SYSTEME', 'actif': True} for code, nom, _ in ROLES])
    op.bulk_insert(links, [{'role_id': uuid5(NAMESPACE, 'role:' + code), 'permission_id': uuid5(NAMESPACE, 'permission:' + permission)} for code, _, grants in ROLES for permission in grants])
