"""Registre append-only de compensations explicites des créances P5-C1."""
from alembic import op
import sqlalchemy as sa

revision = "20261028_02"
down_revision = "20261028_01"
branch_labels = None
depends_on = None

TABLE = "tiers_payant_compensations_creances"
PERMISSION = ("tiers_payant.creance.regulariser",
              "Enregistrer une compensation de créance liée à un retour non engagé")


def upgrade():
    op.create_table(TABLE,
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organisation_id", sa.Uuid(), nullable=False),
        sa.Column("creance_id", sa.Uuid(), nullable=False),
        sa.Column("retour_id", sa.Uuid(), nullable=False),
        sa.Column("montant_xaf", sa.Integer(), nullable=False),
        sa.Column("snapshot", sa.JSON(), nullable=False),
        sa.Column("snapshot_hash", sa.String(64), nullable=False),
        sa.Column("motif", sa.String(2000), nullable=False),
        sa.Column("auteur_id", sa.Uuid(), nullable=False),
        sa.Column("cree_le", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["organisation_id"], ["organisations.id_organisation"]),
        sa.UniqueConstraint("id", "organisation_id", name="uq_tp_compensation_creance_org"),
        sa.ForeignKeyConstraint(["creance_id", "organisation_id"],
            ["tiers_payant_creances.id", "tiers_payant_creances.organisation_id"]),
        sa.ForeignKeyConstraint(["retour_id", "organisation_id"],
            ["vente_retours.id", "vente_retours.organisation_id"]),
        sa.ForeignKeyConstraint(["auteur_id", "organisation_id"],
            ["utilisateurs.id_utilisateur", "utilisateurs.organisation_id"]),
        sa.UniqueConstraint("creance_id", "retour_id", name="uq_tp_compensation_creance_retour"),
        sa.CheckConstraint("montant_xaf > 0", name="ck_tp_compensation_creance_montant"),
        sa.CheckConstraint("length(snapshot_hash) = 64", name="ck_tp_compensation_creance_hash"))
    op.create_index("ix_tiers_payant_compensations_creances_organisation_id", TABLE,
                    ["organisation_id"], unique=False)
    op.create_index("ix_tiers_payant_compensations_creances_creance_id", TABLE,
                    ["creance_id"], unique=False)
    op.create_index("ix_tiers_payant_compensations_creances_retour_id", TABLE,
                    ["retour_id"], unique=False)
    from neosys_pharma.infrastructure.caisse_models import immutable_sql
    for statement in immutable_sql(TABLE, op.get_bind().dialect.name):
        op.execute(statement)
    from neosys_pharma.domain.organisation.permissions_systeme import permission_id
    permissions = sa.table("permissions", sa.column("id_permission", sa.Uuid()),
                           sa.column("code", sa.String()), sa.column("nom", sa.String()))
    if not op.get_bind().scalar(sa.select(permissions.c.id_permission).where(
            permissions.c.code == PERMISSION[0])):
        op.bulk_insert(permissions, [{"id_permission": permission_id(PERMISSION[0]),
                                      "code": PERMISSION[0], "nom": PERMISSION[1]}])


def downgrade():
    if op.get_bind().scalar(sa.text(f"SELECT count(*) FROM {TABLE}")):
        raise RuntimeError("Downgrade refusé : écritures compensatoires de créances présentes.")
    op.drop_index("ix_tiers_payant_compensations_creances_retour_id", table_name=TABLE)
    op.drop_index("ix_tiers_payant_compensations_creances_creance_id", table_name=TABLE)
    op.drop_index("ix_tiers_payant_compensations_creances_organisation_id", table_name=TABLE)
    op.drop_table(TABLE)
    if op.get_bind().dialect.name == "postgresql":
        op.execute(f"DROP FUNCTION {TABLE}_immutable()")
    # La permission peut être liée à des rôles : aucune attribution n'est supprimée.
