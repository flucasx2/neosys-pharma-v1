"""P5-B.3: réalisation immuable des parts organismes à l'encaissement client.

Revision ID: 20261017_03
Revises: 20261017_02
"""
from alembic import op
import sqlalchemy as sa
from neosys_pharma.infrastructure.montant_xaf import MontantXAF

revision = "20261017_03"
down_revision = "20261017_02"
branch_labels = None
depends_on = None


def upgrade():
    # Null on old return records means the sale used the historical P4 split
    # (entire returned amount was the customer refund basis).
    op.add_column("vente_retours", sa.Column("montant_ttc_xaf", MontantXAF(), nullable=True))
    op.add_column("vente_retours", sa.Column("montant_organismes_xaf", MontantXAF(), nullable=True))
    op.create_table(
        "tiers_payant_realisations",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("vente_id", sa.Uuid(), nullable=False),
        sa.Column("encaissement_id", sa.Uuid(), nullable=False),
        sa.Column("calcul_id", sa.Uuid(), nullable=False),
        sa.Column("organisation_id", sa.Uuid(), nullable=False),
        sa.Column("site_id", sa.Uuid(), nullable=False),
        sa.Column("total_xaf", sa.Integer(), nullable=False),
        sa.Column("total_organismes_xaf", sa.Integer(), nullable=False),
        sa.Column("part_client_xaf", sa.Integer(), nullable=False),
        sa.Column("realisee_le", sa.DateTime(timezone=True), nullable=False),
        sa.Column("snapshot", sa.JSON(), nullable=False),
        sa.CheckConstraint(
            "total_xaf > 0 AND total_organismes_xaf > 0 AND part_client_xaf >= 0",
            name="ck_tp_realisation_amounts",
        ),
        sa.CheckConstraint(
            "total_xaf = total_organismes_xaf + part_client_xaf",
            name="ck_tp_realisation_balance",
        ),
        sa.ForeignKeyConstraint(["organisation_id"], ["organisations.id_organisation"]),
        sa.ForeignKeyConstraint(
            ["vente_id", "organisation_id", "site_id"],
            ["ventes.id", "ventes.organisation_id", "ventes.site_id"],
            name="fk_tp_realisation_vente",
        ),
        sa.ForeignKeyConstraint(
            ["encaissement_id", "vente_id", "organisation_id"],
            ["caisse_encaissements.id", "caisse_encaissements.vente_id", "caisse_encaissements.organisation_id"],
            name="fk_tp_realisation_encaissement",
        ),
        sa.ForeignKeyConstraint(
            ["calcul_id", "vente_id", "organisation_id"],
            ["tiers_payant_calculs_vente.id", "tiers_payant_calculs_vente.vente_id", "tiers_payant_calculs_vente.organisation_id"],
            name="fk_tp_realisation_calcul",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("id", "organisation_id", name="uq_tp_realisation_org"),
        sa.UniqueConstraint("vente_id", name="uq_tp_realisation_vente"),
        sa.UniqueConstraint("encaissement_id", name="uq_tp_realisation_encaissement"),
        sa.UniqueConstraint("calcul_id", name="uq_tp_realisation_calcul"),
    )
    op.create_index(
        "ix_tiers_payant_realisations_organisation_id",
        "tiers_payant_realisations", ["organisation_id"],
    )
    op.create_index(
        "ix_tp_realisation_org_site", "tiers_payant_realisations",
        ["organisation_id", "site_id", "realisee_le"],
    )
    bind = op.get_bind()
    if bind.dialect.name == "sqlite":
        for action in ("UPDATE", "DELETE"):
            op.execute(
                f"CREATE TRIGGER tiers_payant_realisations_{action.lower()}_immutable "
                f"BEFORE {action} ON tiers_payant_realisations BEGIN "
                "SELECT RAISE(ABORT, 'Réalisation de prise en charge immuable'); END"
            )
    else:
        op.execute("""CREATE OR REPLACE FUNCTION tiers_payant_realisations_immutable()
            RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN
            RAISE EXCEPTION 'Réalisation de prise en charge immuable'; END $$""")
        op.execute("""CREATE TRIGGER tiers_payant_realisations_immutable
            BEFORE UPDATE OR DELETE ON tiers_payant_realisations FOR EACH ROW
            EXECUTE FUNCTION tiers_payant_realisations_immutable()""")


def downgrade():
    bind = op.get_bind()
    if bind.dialect.name == "sqlite":
        op.execute("DROP TRIGGER IF EXISTS tiers_payant_realisations_update_immutable")
        op.execute("DROP TRIGGER IF EXISTS tiers_payant_realisations_delete_immutable")
    else:
        op.execute("DROP TRIGGER IF EXISTS tiers_payant_realisations_immutable ON tiers_payant_realisations")
        op.execute("DROP FUNCTION IF EXISTS tiers_payant_realisations_immutable()")
    op.drop_index("ix_tp_realisation_org_site", table_name="tiers_payant_realisations")
    op.drop_index("ix_tiers_payant_realisations_organisation_id", table_name="tiers_payant_realisations")
    op.drop_table("tiers_payant_realisations")
    op.drop_column("vente_retours", "montant_organismes_xaf")
    op.drop_column("vente_retours", "montant_ttc_xaf")
