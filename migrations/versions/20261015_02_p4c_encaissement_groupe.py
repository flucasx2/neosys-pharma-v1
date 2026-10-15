"""P4-C.2: dossiers, règlements, allocations et mouvements groupés.

Revision ID: 20261015_02
Revises: 20261015_01
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20261015_02"
down_revision: Union[str, Sequence[str], None] = "20261015_01"
branch_labels = None
depends_on = None

XAF = sa.BigInteger().with_variant(sa.Numeric(18, 0), "postgresql")


def upgrade() -> None:
    with op.batch_alter_table(
        "caisse_periodes_site",
        table_args=(
            sa.CheckConstraint("etat IN ('OUVERTE','CLOTUREE')"),
            sa.CheckConstraint("numero > 0 AND prochain_appel > 0 AND prochain_encaissement > 0"),
        ),
    ) as batch:
        batch.add_column(sa.Column("prochain_encaissement_groupe", sa.Integer(), nullable=False, server_default="1"))
        batch.create_check_constraint("ck_caisse_periode_groupe_sequence", "prochain_encaissement_groupe > 0")
        batch.create_unique_constraint("uq_periode_org_site", ["id", "organisation_id", "site_id"])
    _drop_sqlite_sale_and_encaissement_guards()
    with op.batch_alter_table("ventes") as batch:
        batch.create_unique_constraint("uq_vente_org_site", ["id", "organisation_id", "site_id"])
    with op.batch_alter_table(
        "caisse_sessions",
        table_args=(
            sa.CheckConstraint("etat IN ('OUVERTE','FERMEE')"),
            sa.CheckConstraint("fond_initial >= 0 AND revision > 0"),
        ),
    ) as batch:
        batch.create_unique_constraint("uq_session_org_site", ["id", "organisation_id", "site_id"])
    with op.batch_alter_table(
        "caisse_encaissements",
        table_args=(sa.CheckConstraint("numero > 0 AND total_xaf >= 0"),),
    ) as batch:
        batch.create_unique_constraint("uq_enc_vente_org", ["id", "vente_id", "organisation_id"])
    _restore_sqlite_sale_and_encaissement_guards()

    op.create_table(
        "caisse_encaissements_groupes",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organisation_id", sa.Uuid(), nullable=False),
        sa.Column("site_id", sa.Uuid(), nullable=False),
        sa.Column("session_id", sa.Uuid(), nullable=False),
        sa.Column("auteur_id", sa.Uuid(), nullable=False),
        sa.Column("etat", sa.String(20), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("cree_le", sa.DateTime(timezone=True), nullable=False),
        sa.Column("periode_id", sa.Uuid(), nullable=True),
        sa.Column("numero", sa.Integer(), nullable=True),
        sa.Column("reference", sa.String(100), nullable=True),
        sa.Column("total_xaf", XAF, nullable=True),
        sa.Column("pdf", sa.LargeBinary(), nullable=True),
        sa.Column("pdf_sha256", sa.String(64), nullable=True),
        sa.Column("cle_idempotence", sa.String(200), nullable=True),
        sa.Column("empreinte_requete", sa.String(64), nullable=True),
        sa.CheckConstraint("etat IN ('BROUILLON','FINALISE','ABANDONNE')", name="ck_enc_groupe_etat"),
        sa.CheckConstraint("revision >= 1", name="ck_enc_groupe_revision"),
        sa.CheckConstraint(
            "(etat='FINALISE' AND periode_id IS NOT NULL AND numero IS NOT NULL AND reference IS NOT NULL AND total_xaf IS NOT NULL AND pdf IS NOT NULL AND pdf_sha256 IS NOT NULL) OR (etat IN ('BROUILLON','ABANDONNE') AND periode_id IS NULL AND numero IS NULL AND reference IS NULL AND total_xaf IS NULL AND pdf IS NULL AND pdf_sha256 IS NULL)",
            name="ck_enc_groupe_recu_final",
        ),
        sa.CheckConstraint(
            "(etat='FINALISE' AND cle_idempotence IS NOT NULL AND empreinte_requete IS NOT NULL) OR (etat IN ('BROUILLON','ABANDONNE') AND cle_idempotence IS NULL AND empreinte_requete IS NULL)",
            name="ck_enc_groupe_idempotence",
        ),
        sa.CheckConstraint("cle_idempotence IS NULL OR length(trim(cle_idempotence)) > 0", name="ck_enc_groupe_cle_idempotence"),
        sa.CheckConstraint("empreinte_requete IS NULL OR length(empreinte_requete)=64", name="ck_enc_groupe_empreinte_sha256"),
        sa.CheckConstraint("(numero IS NULL OR numero > 0) AND (total_xaf IS NULL OR total_xaf >= 0)", name="ck_enc_groupe_montants"),
        sa.ForeignKeyConstraint(["organisation_id"], ["organisations.id_organisation"]),
        sa.ForeignKeyConstraint(["site_id", "organisation_id"], ["sites.id_site", "sites.organisation_id"], name="fk_encaissement_groupe_site_org"),
        sa.ForeignKeyConstraint(["session_id", "organisation_id", "site_id"], ["caisse_sessions.id", "caisse_sessions.organisation_id", "caisse_sessions.site_id"], name="fk_enc_groupe_session_site"),
        sa.ForeignKeyConstraint(["auteur_id", "organisation_id"], ["utilisateurs.id_utilisateur", "utilisateurs.organisation_id"], name="fk_encaissement_groupe_auteur_org"),
        sa.ForeignKeyConstraint(["periode_id", "organisation_id", "site_id"], ["caisse_periodes_site.id", "caisse_periodes_site.organisation_id", "caisse_periodes_site.site_id"], name="fk_encaissement_groupe_periode_site"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("id", "organisation_id", name="uq_encaissement_groupe_org"),
        sa.UniqueConstraint("id", "organisation_id", "site_id", name="uq_enc_groupe_org_site"),
        sa.UniqueConstraint("id", "organisation_id", "session_id", name="uq_enc_groupe_org_session"),
        sa.UniqueConstraint("periode_id", "numero", name="uq_enc_groupe_periode_numero"),
        sa.UniqueConstraint("organisation_id", "reference", name="uq_enc_groupe_reference_org"),
        sa.UniqueConstraint("organisation_id", "cle_idempotence", name="uq_enc_groupe_idempotence_org"),
    )
    op.create_index("ix_caisse_encaissements_groupes_organisation_id", "caisse_encaissements_groupes", ["organisation_id"])
    op.create_index("ix_caisse_encaissements_groupes_site_id", "caisse_encaissements_groupes", ["site_id"])
    op.create_index("ix_caisse_encaissements_groupes_session_id", "caisse_encaissements_groupes", ["session_id"])
    op.create_index("ix_caisse_encaissements_groupes_etat", "caisse_encaissements_groupes", ["etat"])

    op.create_table(
        "caisse_encaissements_groupes_ventes",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organisation_id", sa.Uuid(), nullable=False),
        sa.Column("dossier_id", sa.Uuid(), nullable=False),
        sa.Column("site_id", sa.Uuid(), nullable=False),
        sa.Column("vente_id", sa.Uuid(), nullable=False),
        sa.Column("encaissement_id", sa.Uuid(), nullable=True),
        sa.Column("ordre", sa.Integer(), nullable=False),
        sa.Column("revision_vente", sa.Integer(), nullable=False),
        sa.Column("montant_du", XAF, nullable=False),
        sa.CheckConstraint("ordre > 0 AND revision_vente > 0 AND montant_du >= 0", name="ck_enc_groupe_vente_snapshot"),
        sa.ForeignKeyConstraint(["organisation_id"], ["organisations.id_organisation"]),
        sa.ForeignKeyConstraint(["dossier_id", "organisation_id", "site_id"], ["caisse_encaissements_groupes.id", "caisse_encaissements_groupes.organisation_id", "caisse_encaissements_groupes.site_id"], name="fk_enc_groupe_vente_dossier"),
        sa.ForeignKeyConstraint(["vente_id", "organisation_id", "site_id"], ["ventes.id", "ventes.organisation_id", "ventes.site_id"], name="fk_enc_groupe_vente_vente_site"),
        sa.ForeignKeyConstraint(["encaissement_id", "vente_id", "organisation_id"], ["caisse_encaissements.id", "caisse_encaissements.vente_id", "caisse_encaissements.organisation_id"], name="fk_enc_groupe_vente_encaissement_vente"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("id", "organisation_id", name="uq_enc_groupe_vente_org"),
        sa.UniqueConstraint("dossier_id", "vente_id", name="uq_enc_groupe_vente"),
        sa.UniqueConstraint("dossier_id", "ordre", name="uq_enc_groupe_ordre"),
        sa.UniqueConstraint("encaissement_id", name="uq_enc_groupe_encaissement"),
        sa.UniqueConstraint("dossier_id", "vente_id", "organisation_id", name="uq_enc_groupe_dossier_vente_org"),
    )
    for column in ("organisation_id", "dossier_id", "site_id", "vente_id", "encaissement_id"):
        op.create_index(f"ix_caisse_encaissements_groupes_ventes_{column}", "caisse_encaissements_groupes_ventes", [column])

    op.create_table(
        "caisse_reglements_groupes",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organisation_id", sa.Uuid(), nullable=False),
        sa.Column("dossier_id", sa.Uuid(), nullable=False),
        sa.Column("ordre", sa.Integer(), nullable=False),
        sa.Column("mode", sa.String(30), nullable=False),
        sa.Column("montant", XAF, nullable=False),
        sa.Column("rendu", XAF, nullable=False),
        sa.Column("confirmation_id", sa.Uuid(), nullable=True),
        sa.CheckConstraint("ordre > 0 AND montant > 0 AND rendu >= 0 AND rendu < montant", name="ck_reg_groupe_montants"),
        sa.CheckConstraint("mode IN ('ESPECES','CARTE','MOBILE_MONEY','CHEQUE','VIREMENT')", name="ck_reg_groupe_mode"),
        sa.CheckConstraint("(mode='ESPECES' AND confirmation_id IS NULL) OR (mode<>'ESPECES' AND confirmation_id IS NOT NULL AND rendu=0)", name="ck_reg_groupe_confirmation"),
        sa.ForeignKeyConstraint(["organisation_id"], ["organisations.id_organisation"]),
        sa.ForeignKeyConstraint(["dossier_id", "organisation_id"], ["caisse_encaissements_groupes.id", "caisse_encaissements_groupes.organisation_id"], name="fk_reg_groupe_dossier"),
        sa.ForeignKeyConstraint(["confirmation_id", "organisation_id"], ["caisse_confirmations.id", "caisse_confirmations.organisation_id"], name="fk_reglement_groupe_confirmation_org"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("id", "organisation_id", name="uq_reglement_groupe_org"),
        sa.UniqueConstraint("id", "dossier_id", "organisation_id", name="uq_reg_groupe_dossier_org"),
        sa.UniqueConstraint("dossier_id", "ordre", name="uq_reg_groupe_ordre"),
        sa.UniqueConstraint("confirmation_id", name="uq_reg_groupe_confirmation"),
    )
    op.create_index("ix_caisse_reglements_groupes_organisation_id", "caisse_reglements_groupes", ["organisation_id"])
    op.create_index("ix_caisse_reglements_groupes_dossier_id", "caisse_reglements_groupes", ["dossier_id"])

    op.create_table(
        "caisse_allocations_reglements_groupes",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organisation_id", sa.Uuid(), nullable=False),
        sa.Column("reglement_id", sa.Uuid(), nullable=False),
        sa.Column("dossier_id", sa.Uuid(), nullable=False),
        sa.Column("vente_id", sa.Uuid(), nullable=False),
        sa.Column("montant", XAF, nullable=False),
        sa.CheckConstraint("montant > 0", name="ck_alloc_reg_montant"),
        sa.ForeignKeyConstraint(["organisation_id"], ["organisations.id_organisation"]),
        sa.ForeignKeyConstraint(["reglement_id", "dossier_id", "organisation_id"], ["caisse_reglements_groupes.id", "caisse_reglements_groupes.dossier_id", "caisse_reglements_groupes.organisation_id"], name="fk_alloc_reg_groupe"),
        sa.ForeignKeyConstraint(["dossier_id", "vente_id", "organisation_id"], ["caisse_encaissements_groupes_ventes.dossier_id", "caisse_encaissements_groupes_ventes.vente_id", "caisse_encaissements_groupes_ventes.organisation_id"], name="fk_alloc_vente_groupe"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("id", "organisation_id", name="uq_allocation_reg_groupe_org"),
        sa.UniqueConstraint("reglement_id", "vente_id", name="uq_alloc_reg_vente"),
    )
    for column in ("organisation_id", "reglement_id", "dossier_id", "vente_id"):
        op.create_index(f"ix_caisse_allocations_reglements_groupes_{column}", "caisse_allocations_reglements_groupes", [column])

    op.create_table(
        "caisse_mouvements_groupes",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organisation_id", sa.Uuid(), nullable=False),
        sa.Column("dossier_id", sa.Uuid(), nullable=False),
        sa.Column("reglement_id", sa.Uuid(), nullable=False),
        sa.Column("session_id", sa.Uuid(), nullable=False),
        sa.Column("auteur_id", sa.Uuid(), nullable=False),
        sa.Column("mode", sa.String(30), nullable=False),
        sa.Column("montant_net", XAF, nullable=False),
        sa.Column("date", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("montant_net > 0", name="ck_mvt_groupe_montant_net"),
        sa.CheckConstraint("mode IN ('ESPECES','CARTE','MOBILE_MONEY','CHEQUE','VIREMENT')", name="ck_mvt_groupe_mode"),
        sa.ForeignKeyConstraint(["organisation_id"], ["organisations.id_organisation"]),
        sa.ForeignKeyConstraint(["dossier_id", "organisation_id", "session_id"], ["caisse_encaissements_groupes.id", "caisse_encaissements_groupes.organisation_id", "caisse_encaissements_groupes.session_id"], name="fk_mvt_groupe_dossier_session"),
        sa.ForeignKeyConstraint(["reglement_id", "dossier_id", "organisation_id"], ["caisse_reglements_groupes.id", "caisse_reglements_groupes.dossier_id", "caisse_reglements_groupes.organisation_id"], name="fk_mvt_groupe_reglement"),
        sa.ForeignKeyConstraint(["auteur_id", "organisation_id"], ["utilisateurs.id_utilisateur", "utilisateurs.organisation_id"], name="fk_mvt_groupe_auteur_org"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("id", "organisation_id", name="uq_mouvement_caisse_groupe_org"),
        sa.UniqueConstraint("reglement_id", name="uq_mvt_groupe_reglement"),
    )
    for column in ("organisation_id", "dossier_id", "reglement_id", "session_id"):
        op.create_index(f"ix_caisse_mouvements_groupes_{column}", "caisse_mouvements_groupes", [column])

    _create_immutable_movement_triggers(op.get_bind().dialect.name)


def _create_immutable_movement_triggers(dialect: str) -> None:
    if dialect == "sqlite":
        for action in ("UPDATE", "DELETE"):
            op.execute(
                f"CREATE TRIGGER caisse_mouvements_groupes_{action.lower()}_immutable "
                f"BEFORE {action} ON caisse_mouvements_groupes BEGIN "
                "SELECT RAISE(ABORT, 'Journal financier immuable'); END"
            )
    elif dialect == "postgresql":
        op.execute(
            "CREATE OR REPLACE FUNCTION caisse_mouvements_groupes_immutable() RETURNS trigger "
            "LANGUAGE plpgsql AS $$ BEGIN RAISE EXCEPTION 'Journal financier immuable'; END $$"
        )
        op.execute(
            "CREATE TRIGGER caisse_mouvements_groupes_immutable BEFORE UPDATE OR DELETE "
            "ON caisse_mouvements_groupes FOR EACH ROW EXECUTE FUNCTION caisse_mouvements_groupes_immutable()"
        )


def _drop_sqlite_sale_and_encaissement_guards() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "sqlite":
        return
    for table in ("ventes", "vente_lignes", "vente_demandes_remise"):
        for action in ("insert", "update", "delete"):
            op.execute(f"DROP TRIGGER IF EXISTS {table}_paye_{action}")
    for action in ("update", "delete"):
        op.execute(f"DROP TRIGGER IF EXISTS caisse_encaissements_{action}_immutable")


def _restore_sqlite_sale_and_encaissement_guards() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "sqlite":
        return
    from neosys_pharma.infrastructure.caisse_models import immutable_sql, paid_guard_sql

    for sql in paid_guard_sql("sqlite"):
        op.execute(sql)
    for sql in immutable_sql("caisse_encaissements", "sqlite"):
        op.execute(sql)


def downgrade() -> None:
    bind = op.get_bind()
    count = bind.execute(sa.text("SELECT count(*) FROM caisse_encaissements_groupes")).scalar_one()
    if count:
        raise RuntimeError("Downgrade refusé : exporter puis traiter les dossiers P4-C avant suppression du schéma.")
    if bind.dialect.name == "sqlite":
        op.execute("DROP TRIGGER IF EXISTS caisse_mouvements_groupes_update_immutable")
        op.execute("DROP TRIGGER IF EXISTS caisse_mouvements_groupes_delete_immutable")
    elif bind.dialect.name == "postgresql":
        op.execute("DROP FUNCTION IF EXISTS caisse_mouvements_groupes_immutable()")
    for table in (
        "caisse_mouvements_groupes",
        "caisse_allocations_reglements_groupes",
        "caisse_reglements_groupes",
        "caisse_encaissements_groupes_ventes",
        "caisse_encaissements_groupes",
    ):
        op.drop_table(table)
    _drop_sqlite_sale_and_encaissement_guards()
    with op.batch_alter_table(
        "caisse_encaissements",
        table_args=(sa.CheckConstraint("numero > 0 AND total_xaf >= 0"),),
    ) as batch:
        batch.drop_constraint("uq_enc_vente_org", type_="unique")
    with op.batch_alter_table(
        "caisse_sessions",
        table_args=(
            sa.CheckConstraint("etat IN ('OUVERTE','FERMEE')"),
            sa.CheckConstraint("fond_initial >= 0 AND revision > 0"),
        ),
    ) as batch:
        batch.drop_constraint("uq_session_org_site", type_="unique")
    with op.batch_alter_table("ventes") as batch:
        batch.drop_constraint("uq_vente_org_site", type_="unique")
    with op.batch_alter_table(
        "caisse_periodes_site",
        table_args=(
            sa.CheckConstraint("etat IN ('OUVERTE','CLOTUREE')"),
            sa.CheckConstraint("numero > 0 AND prochain_appel > 0 AND prochain_encaissement > 0"),
        ),
    ) as batch:
        batch.drop_constraint("uq_periode_org_site", type_="unique")
        batch.drop_constraint("ck_caisse_periode_groupe_sequence", type_="check")
        batch.drop_column("prochain_encaissement_groupe")
    _restore_sqlite_sale_and_encaissement_guards()
