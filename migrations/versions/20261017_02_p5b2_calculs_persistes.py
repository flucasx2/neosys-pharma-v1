"""P5-B.2: snapshots financiers de prise en charge immuables.

Revision ID: 20261017_02
Revises: 20261017_01
"""
from alembic import op
import sqlalchemy as sa

revision = "20261017_02"
down_revision = "20261017_01"
branch_labels = None
depends_on = None


def _triggers(tables, create=True):
    bind = op.get_bind()
    if create:
        if bind.dialect.name == "sqlite":
            for table in tables:
                for action in ("UPDATE", "DELETE"):
                    op.execute(f"CREATE TRIGGER {table}_{action.lower()}_immutable BEFORE {action} ON {table} BEGIN SELECT RAISE(ABORT, 'Snapshot financier P5-B immuable'); END")
        else:
            for table in tables:
                op.execute(f"CREATE OR REPLACE FUNCTION {table}_immutable() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN RAISE EXCEPTION 'Snapshot financier P5-B immuable'; END $$")
                op.execute(f"CREATE TRIGGER {table}_immutable BEFORE UPDATE OR DELETE ON {table} FOR EACH ROW EXECUTE FUNCTION {table}_immutable()")
    elif bind.dialect.name == "sqlite":
        for table in tables:
            for action in ("UPDATE", "DELETE"):
                op.execute(f"DROP TRIGGER IF EXISTS {table}_{action.lower()}_immutable")
    else:
        for table in tables:
            op.execute(f"DROP TRIGGER IF EXISTS {table}_immutable ON {table}")
            op.execute(f"DROP FUNCTION IF EXISTS {table}_immutable()")


def upgrade():
    # Clé composite additive requise pour relier chaque snapshot à une ligne
    # et à sa vente dans la même organisation.
    with op.batch_alter_table("vente_lignes") as batch:
        batch.create_unique_constraint("uq_ligne_vente_vente_org", ["id", "vente_id", "organisation_id"])
    op.create_table(
        "tiers_payant_calculs_vente",
        sa.Column("id", sa.Uuid(), nullable=False), sa.Column("vente_id", sa.Uuid(), nullable=False),
        sa.Column("organisation_id", sa.Uuid(), nullable=False), sa.Column("site_id", sa.Uuid(), nullable=False),
        sa.Column("beneficiaire_id", sa.Uuid()), sa.Column("date_calcul", sa.Date(), nullable=False),
        sa.Column("revision_vente", sa.Integer(), nullable=False), sa.Column("parametrage_id", sa.Uuid(), nullable=False),
        sa.Column("parametrage_version", sa.Integer(), nullable=False), sa.Column("moteur_version", sa.String(40), nullable=False),
        sa.Column("snapshot_hash", sa.String(64), nullable=False), sa.Column("total_xaf", sa.Integer(), nullable=False),
        sa.Column("total_organismes_xaf", sa.Integer(), nullable=False), sa.Column("part_client_xaf", sa.Integer(), nullable=False),
        sa.Column("snapshot", sa.JSON(), nullable=False), sa.Column("auteur_id", sa.Uuid(), nullable=False),
        sa.Column("confirme_le", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("revision_vente > 0 AND parametrage_version > 0", name="ck_tp_calc_revisions"),
        sa.CheckConstraint("total_xaf >= 0 AND total_organismes_xaf >= 0 AND part_client_xaf >= 0", name="ck_tp_calc_montants"),
        sa.CheckConstraint("total_xaf = total_organismes_xaf + part_client_xaf", name="ck_tp_calc_equilibre"),
        sa.CheckConstraint("length(snapshot_hash) = 64", name="ck_tp_calc_hash_sha256"),
        sa.ForeignKeyConstraint(["organisation_id"], ["organisations.id_organisation"]),
        sa.ForeignKeyConstraint(["vente_id", "organisation_id", "site_id"], ["ventes.id", "ventes.organisation_id", "ventes.site_id"], name="fk_tp_calc_vente_site_org"),
        sa.ForeignKeyConstraint(["beneficiaire_id", "organisation_id"], ["tiers_payant_beneficiaires.id", "tiers_payant_beneficiaires.organisation_id"], name="fk_tp_calc_benef_org"),
        sa.ForeignKeyConstraint(["parametrage_id", "organisation_id"], ["tiers_payant_parametrages_priorite.id", "tiers_payant_parametrages_priorite.organisation_id"], name="fk_tp_calc_priorite_org"),
        sa.ForeignKeyConstraint(["auteur_id", "organisation_id"], ["utilisateurs.id_utilisateur", "utilisateurs.organisation_id"], name="fk_tp_calc_auteur_org"),
        sa.PrimaryKeyConstraint("id"), sa.UniqueConstraint("id", "organisation_id", name="uq_tp_calc_org"),
        sa.UniqueConstraint("id", "vente_id", "organisation_id", name="uq_tp_calc_vente_org"),
        sa.UniqueConstraint("vente_id", name="uq_tp_calc_vente_unique"), sa.UniqueConstraint("snapshot_hash", name="uq_tp_calc_snapshot_hash"),
    )
    op.create_index("ix_tiers_payant_calculs_vente_organisation_id", "tiers_payant_calculs_vente", ["organisation_id"])
    op.create_index("ix_tp_calc_org_site", "tiers_payant_calculs_vente", ["organisation_id", "site_id", "date_calcul"])
    op.create_table(
        "tiers_payant_calculs_lignes",
        sa.Column("id", sa.Uuid(), nullable=False), sa.Column("calcul_id", sa.Uuid(), nullable=False),
        sa.Column("vente_id", sa.Uuid(), nullable=False), sa.Column("ligne_vente_id", sa.Uuid(), nullable=False),
        sa.Column("organisation_id", sa.Uuid(), nullable=False), sa.Column("net_xaf", sa.Integer(), nullable=False),
        sa.Column("part_client_xaf", sa.Integer(), nullable=False), sa.Column("total_organismes_xaf", sa.Integer(), nullable=False),
        sa.CheckConstraint("net_xaf >= 0 AND part_client_xaf >= 0 AND total_organismes_xaf >= 0 AND net_xaf = part_client_xaf + total_organismes_xaf", name="ck_tp_calc_ligne_equilibre"),
        sa.ForeignKeyConstraint(["calcul_id", "vente_id", "organisation_id"], ["tiers_payant_calculs_vente.id", "tiers_payant_calculs_vente.vente_id", "tiers_payant_calculs_vente.organisation_id"], name="fk_tp_calc_ligne_entete"),
        sa.ForeignKeyConstraint(["ligne_vente_id", "vente_id", "organisation_id"], ["vente_lignes.id", "vente_lignes.vente_id", "vente_lignes.organisation_id"], name="fk_tp_calc_ligne_vente"),
        sa.PrimaryKeyConstraint("id"), sa.UniqueConstraint("id", "organisation_id", name="uq_tp_calc_ligne_org"),
        sa.UniqueConstraint("id", "calcul_id", "organisation_id", name="uq_tp_calc_ligne_parent_org"),
        sa.UniqueConstraint("calcul_id", "ligne_vente_id", name="uq_tp_calc_ligne_vente"),
    )
    op.create_index("ix_tiers_payant_calculs_lignes_organisation_id", "tiers_payant_calculs_lignes", ["organisation_id"])
    op.create_table(
        "tiers_payant_calculs_parts",
        sa.Column("id", sa.Uuid(), nullable=False), sa.Column("ligne_calcul_id", sa.Uuid(), nullable=False),
        sa.Column("organisation_id", sa.Uuid(), nullable=False), sa.Column("type_part", sa.String(20), nullable=False),
        sa.Column("organisme_id", sa.Uuid()), sa.Column("montant_xaf", sa.Integer(), nullable=False), sa.Column("rang", sa.Integer()),
        sa.CheckConstraint("montant_xaf >= 0", name="ck_tp_calc_part_nonnegative"),
        sa.CheckConstraint("(type_part = 'CLIENT' AND organisme_id IS NULL) OR (type_part = 'ORGANISME' AND organisme_id IS NOT NULL)", name="ck_tp_calc_part_type"),
        sa.ForeignKeyConstraint(["ligne_calcul_id", "organisation_id"], ["tiers_payant_calculs_lignes.id", "tiers_payant_calculs_lignes.organisation_id"], name="fk_tp_calc_part_ligne_org"),
        sa.ForeignKeyConstraint(["organisme_id", "organisation_id"], ["organismes_prise_en_charge.id", "organismes_prise_en_charge.organisation_id"], name="fk_tp_calc_part_organisme_org"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_tiers_payant_calculs_parts_organisation_id", "tiers_payant_calculs_parts", ["organisation_id"])
    op.create_index("ix_tp_calc_part_ligne", "tiers_payant_calculs_parts", ["organisation_id", "ligne_calcul_id"])
    op.create_index("uq_tp_part_client", "tiers_payant_calculs_parts", ["ligne_calcul_id"], unique=True,
                    postgresql_where=sa.text("type_part = 'CLIENT'"), sqlite_where=sa.text("type_part = 'CLIENT'"))
    op.create_index("uq_tp_part_organisme", "tiers_payant_calculs_parts", ["ligne_calcul_id", "organisme_id"], unique=True,
                    postgresql_where=sa.text("type_part = 'ORGANISME'"), sqlite_where=sa.text("type_part = 'ORGANISME'"))
    op.create_table(
        "tiers_payant_calculs_etapes",
        sa.Column("id", sa.Uuid(), nullable=False), sa.Column("ligne_calcul_id", sa.Uuid(), nullable=False),
        sa.Column("organisation_id", sa.Uuid(), nullable=False), sa.Column("organisme_id", sa.Uuid(), nullable=False),
        sa.Column("rang", sa.Integer(), nullable=False), sa.Column("role", sa.String(20), nullable=False),
        sa.Column("convention_id", sa.Uuid()), sa.Column("convention_version", sa.Integer()),
        sa.Column("adhesion_id", sa.Uuid()), sa.Column("adhesion_revision", sa.Integer()),
        sa.Column("base_initiale_xaf", sa.Integer(), nullable=False), sa.Column("base_eligible_xaf", sa.Integer(), nullable=False),
        sa.Column("montant_couvert_xaf", sa.Integer(), nullable=False), sa.Column("reste_apres_xaf", sa.Integer(), nullable=False),
        sa.Column("code", sa.String(80), nullable=False), sa.Column("regle_code", sa.String(80)),
        sa.Column("snapshot_convention", sa.JSON(), nullable=False), sa.Column("snapshot_droits", sa.JSON(), nullable=False),
        sa.CheckConstraint("rang > 0 AND base_initiale_xaf >= 0 AND base_eligible_xaf >= 0 AND montant_couvert_xaf >= 0 AND reste_apres_xaf >= 0", name="ck_tp_calc_etape_values"),
        sa.ForeignKeyConstraint(["ligne_calcul_id", "organisation_id"], ["tiers_payant_calculs_lignes.id", "tiers_payant_calculs_lignes.organisation_id"], name="fk_tp_calc_etape_ligne_org"),
        sa.ForeignKeyConstraint(["organisme_id", "organisation_id"], ["organismes_prise_en_charge.id", "organismes_prise_en_charge.organisation_id"], name="fk_tp_calc_etape_organisme_org"),
        sa.ForeignKeyConstraint(["convention_id", "organisation_id"], ["tiers_payant_conventions.id", "tiers_payant_conventions.organisation_id"], name="fk_tp_calc_etape_convention_org"),
        sa.ForeignKeyConstraint(["adhesion_id", "organisation_id"], ["tiers_payant_adhesions.id", "tiers_payant_adhesions.organisation_id"], name="fk_tp_calc_etape_adhesion_org"),
        sa.UniqueConstraint("ligne_calcul_id", "rang", name="uq_tp_calc_etape_rang"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_tiers_payant_calculs_etapes_organisation_id", "tiers_payant_calculs_etapes", ["organisation_id"])
    op.create_index("ix_tp_calc_etape_line", "tiers_payant_calculs_etapes", ["organisation_id", "ligne_calcul_id", "rang"])
    _triggers(("tiers_payant_calculs_vente", "tiers_payant_calculs_lignes", "tiers_payant_calculs_parts", "tiers_payant_calculs_etapes"))


def downgrade():
    _triggers(("tiers_payant_calculs_vente", "tiers_payant_calculs_lignes", "tiers_payant_calculs_parts", "tiers_payant_calculs_etapes"), create=False)
    for table, indexes in (
        ("tiers_payant_calculs_etapes", ("ix_tp_calc_etape_line", "ix_tiers_payant_calculs_etapes_organisation_id")),
        ("tiers_payant_calculs_parts", ("uq_tp_part_organisme", "uq_tp_part_client", "ix_tp_calc_part_ligne", "ix_tiers_payant_calculs_parts_organisation_id")),
        ("tiers_payant_calculs_lignes", ("ix_tiers_payant_calculs_lignes_organisation_id",)),
        ("tiers_payant_calculs_vente", ("ix_tp_calc_org_site", "ix_tiers_payant_calculs_vente_organisation_id")),
    ):
        for index in indexes:
            op.drop_index(index, table_name=table)
        op.drop_table(table)
    with op.batch_alter_table("vente_lignes") as batch:
        batch.drop_constraint("uq_ligne_vente_vente_org", type_="unique")
