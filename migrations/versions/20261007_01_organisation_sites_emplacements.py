"""P1 organisation, sites and emplacements (additive)."""
from alembic import op
import sqlalchemy as sa

revision = "20261007_01"
down_revision = "29485f21585c"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table("organisations",
        sa.Column("id_organisation", sa.Uuid(), primary_key=True),
        sa.Column("nom_commercial", sa.String(200), nullable=False),
        sa.Column("raison_sociale", sa.String(200), nullable=False),
        sa.Column("logo", sa.String(1000)),
        sa.Column("coordonnees", sa.String(2000)),
        sa.Column("informations_legales", sa.String(2000)),
        sa.Column("actif", sa.Boolean(), nullable=False))
    op.create_table("sites",
        sa.Column("id_site", sa.Uuid(), primary_key=True),
        sa.Column("organisation_id", sa.Uuid(), sa.ForeignKey("organisations.id_organisation"), nullable=False),
        sa.Column("code", sa.String(80), nullable=False),
        sa.Column("nom", sa.String(200), nullable=False),
        sa.Column("adresse", sa.String(1000)),
        sa.Column("telephone", sa.String(80)),
        sa.Column("email", sa.String(254)),
        sa.Column("actif", sa.Boolean(), nullable=False),
        sa.UniqueConstraint("organisation_id", "code", name="uq_site_organisation_code"))
    op.create_index("ix_sites_organisation_id", "sites", ["organisation_id"])
    op.create_table("emplacements",
        sa.Column("id_emplacement", sa.Uuid(), primary_key=True),
        sa.Column("site_id", sa.Uuid(), sa.ForeignKey("sites.id_site"), nullable=False),
        sa.Column("code", sa.String(80), nullable=False),
        sa.Column("nom", sa.String(200), nullable=False),
        sa.Column("actif", sa.Boolean(), nullable=False),
        sa.UniqueConstraint("site_id", "code", name="uq_emplacement_site_code"))
    op.create_index("ix_emplacements_site_id", "emplacements", ["site_id"])


def downgrade() -> None:
    # Explicit rollback only: destructive on a populated database.
    op.drop_index("ix_emplacements_site_id", table_name="emplacements")
    op.drop_table("emplacements")
    op.drop_index("ix_sites_organisation_id", table_name="sites")
    op.drop_table("sites")
    op.drop_table("organisations")
