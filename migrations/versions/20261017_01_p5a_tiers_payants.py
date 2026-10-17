"""P5-A: conventions, bénéficiaires/adhésions, priorités versionnées et audit.

Revision ID: 20261017_01
Revises: 20261015_02
"""
from uuid import UUID, uuid5

from alembic import op
import sqlalchemy as sa


revision = "20261017_01"
down_revision = "20261015_02"
branch_labels = None
depends_on = None

NAMESPACE = UUID("5e0d5c59-9934-40a6-b798-92d3f544667d")
PERMISSIONS = (
    ("tiers_payant.consulter", "Consulter conventions, adhésions et priorités de prise en charge"),
    ("tiers_payant.convention.gerer", "Créer et versionner les conventions de prise en charge"),
    ("tiers_payant.adhesion.consulter", "Consulter les bénéficiaires et adhésions de prise en charge"),
    ("tiers_payant.adhesion.gerer", "Gérer les bénéficiaires et adhésions de prise en charge"),
    ("tiers_payant.priorites.gerer", "Configurer et versionner les priorités de prise en charge"),
)


def upgrade() -> None:
    op.create_table(
        "tiers_payant_conventions",
        sa.Column("organisme_id", sa.Uuid(), nullable=False),
        sa.Column("code", sa.String(80), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("reference_contractuelle", sa.String(200)),
        sa.Column("date_debut", sa.Date(), nullable=False),
        sa.Column("date_fin", sa.Date()),
        sa.Column("statut", sa.String(20), nullable=False),
        sa.Column("conditions", sa.JSON(), nullable=False),
        sa.Column("extensions_p5b", sa.JSON(), nullable=False),
        sa.Column("auteur_id", sa.Uuid(), nullable=False),
        sa.Column("cree_le", sa.DateTime(timezone=True), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organisation_id", sa.Uuid(), nullable=False),
        sa.CheckConstraint("version > 0", name="ck_tp_convention_version"),
        sa.CheckConstraint("date_fin IS NULL OR date_fin >= date_debut", name="ck_tp_convention_periode"),
        sa.CheckConstraint("length(trim(code)) > 0", name="ck_tp_convention_code"),
        sa.CheckConstraint("statut IN ('ACTIVE','INACTIVE')", name="ck_tp_convention_statut"),
        sa.ForeignKeyConstraint(["organisation_id"], ["organisations.id_organisation"]),
        sa.ForeignKeyConstraint(["organisme_id", "organisation_id"], ["organismes_prise_en_charge.id", "organismes_prise_en_charge.organisation_id"], name="fk_tp_convention_organisme_org"),
        sa.ForeignKeyConstraint(["auteur_id", "organisation_id"], ["utilisateurs.id_utilisateur", "utilisateurs.organisation_id"], name="fk_tp_convention_auteur_org"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("id", "organisation_id", name="uq_tp_convention_org"),
        sa.UniqueConstraint("organisation_id", "organisme_id", "code", "version", name="uq_tp_convention_version"),
    )
    op.create_index("ix_tiers_payant_conventions_organisation_id", "tiers_payant_conventions", ["organisation_id"])
    op.create_index("ix_tp_convention_organisme_periode", "tiers_payant_conventions", ["organisation_id", "organisme_id", "date_debut", "date_fin"])

    op.create_table(
        "tiers_payant_beneficiaires",
        sa.Column("client_id", sa.Uuid()),
        sa.Column("nom", sa.String(200), nullable=False),
        sa.Column("date_naissance", sa.Date()),
        sa.Column("reference_externe", sa.String(200)),
        sa.Column("actif", sa.Boolean(), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("auteur_id", sa.Uuid(), nullable=False),
        sa.Column("cree_le", sa.DateTime(timezone=True), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organisation_id", sa.Uuid(), nullable=False),
        sa.CheckConstraint("revision > 0", name="ck_tp_beneficiaire_revision"),
        sa.CheckConstraint("length(trim(nom)) > 0", name="ck_tp_beneficiaire_nom"),
        sa.ForeignKeyConstraint(["organisation_id"], ["organisations.id_organisation"]),
        sa.ForeignKeyConstraint(["client_id", "organisation_id"], ["clients.id", "clients.organisation_id"], name="fk_tp_beneficiaire_client_org"),
        sa.ForeignKeyConstraint(["auteur_id", "organisation_id"], ["utilisateurs.id_utilisateur", "utilisateurs.organisation_id"], name="fk_tp_beneficiaire_auteur_org"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("id", "organisation_id", name="uq_tp_beneficiaire_org"),
    )
    op.create_index("ix_tiers_payant_beneficiaires_organisation_id", "tiers_payant_beneficiaires", ["organisation_id"])
    op.create_index("ix_tp_beneficiaire_client", "tiers_payant_beneficiaires", ["organisation_id", "client_id"])

    op.create_table(
        "tiers_payant_adhesions",
        sa.Column("convention_id", sa.Uuid(), nullable=False),
        sa.Column("titulaire_id", sa.Uuid(), nullable=False),
        sa.Column("reference_adhesion", sa.String(200), nullable=False),
        sa.Column("date_debut", sa.Date(), nullable=False),
        sa.Column("date_fin", sa.Date()),
        sa.Column("statut", sa.String(20), nullable=False),
        sa.Column("droits_statut", sa.String(20), nullable=False),
        sa.Column("reference_verification_droits", sa.String(200)),
        sa.Column("droits_verifies_le", sa.DateTime(timezone=True)),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("auteur_id", sa.Uuid(), nullable=False),
        sa.Column("cree_le", sa.DateTime(timezone=True), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organisation_id", sa.Uuid(), nullable=False),
        sa.CheckConstraint("date_fin IS NULL OR date_fin >= date_debut", name="ck_tp_adhesion_periode"),
        sa.CheckConstraint("statut IN ('ACTIVE','INACTIVE','SUSPENDUE')", name="ck_tp_adhesion_statut"),
        sa.CheckConstraint("droits_statut IN ('A_VERIFIER','CONFIRMES','REFUSES','SUSPENDUS')", name="ck_tp_adhesion_droits"),
        sa.CheckConstraint("droits_statut = 'A_VERIFIER' OR (reference_verification_droits IS NOT NULL AND droits_verifies_le IS NOT NULL)", name="ck_tp_adhesion_droits_preuve"),
        sa.CheckConstraint("revision > 0", name="ck_tp_adhesion_revision"),
        sa.ForeignKeyConstraint(["organisation_id"], ["organisations.id_organisation"]),
        sa.ForeignKeyConstraint(["convention_id", "organisation_id"], ["tiers_payant_conventions.id", "tiers_payant_conventions.organisation_id"], name="fk_tp_adhesion_convention_org"),
        sa.ForeignKeyConstraint(["titulaire_id", "organisation_id"], ["tiers_payant_beneficiaires.id", "tiers_payant_beneficiaires.organisation_id"], name="fk_tp_adhesion_titulaire_org"),
        sa.ForeignKeyConstraint(["auteur_id", "organisation_id"], ["utilisateurs.id_utilisateur", "utilisateurs.organisation_id"], name="fk_tp_adhesion_auteur_org"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("id", "organisation_id", name="uq_tp_adhesion_org"),
        sa.UniqueConstraint("organisation_id", "reference_adhesion", "date_debut", name="uq_tp_adhesion_reference_debut"),
    )
    op.create_index("ix_tiers_payant_adhesions_organisation_id", "tiers_payant_adhesions", ["organisation_id"])
    op.create_index("ix_tp_adhesion_convention_periode", "tiers_payant_adhesions", ["organisation_id", "convention_id", "date_debut", "date_fin"])

    op.create_table(
        "tiers_payant_adhesion_beneficiaires",
        sa.Column("adhesion_id", sa.Uuid(), nullable=False),
        sa.Column("beneficiaire_id", sa.Uuid(), nullable=False),
        sa.Column("relation", sa.String(20), nullable=False),
        sa.Column("date_debut", sa.Date(), nullable=False),
        sa.Column("date_fin", sa.Date()),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organisation_id", sa.Uuid(), nullable=False),
        sa.CheckConstraint("relation IN ('TITULAIRE','AYANT_DROIT','AUTRE')", name="ck_tp_lien_relation"),
        sa.CheckConstraint("date_fin IS NULL OR date_fin >= date_debut", name="ck_tp_lien_periode"),
        sa.ForeignKeyConstraint(["organisation_id"], ["organisations.id_organisation"]),
        sa.ForeignKeyConstraint(["adhesion_id", "organisation_id"], ["tiers_payant_adhesions.id", "tiers_payant_adhesions.organisation_id"], name="fk_tp_lien_adhesion_org"),
        sa.ForeignKeyConstraint(["beneficiaire_id", "organisation_id"], ["tiers_payant_beneficiaires.id", "tiers_payant_beneficiaires.organisation_id"], name="fk_tp_lien_beneficiaire_org"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("adhesion_id", "beneficiaire_id", name="uq_tp_adhesion_beneficiaire"),
    )
    op.create_index("ix_tiers_payant_adhesion_beneficiaires_organisation_id", "tiers_payant_adhesion_beneficiaires", ["organisation_id"])
    op.create_index("ix_tp_lien_beneficiaire", "tiers_payant_adhesion_beneficiaires", ["organisation_id", "beneficiaire_id"])

    op.create_table(
        "tiers_payant_parametrages_priorite",
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("date_debut", sa.Date(), nullable=False),
        sa.Column("date_fin", sa.Date()),
        sa.Column("statut", sa.String(20), nullable=False),
        sa.Column("motif", sa.String(2000), nullable=False),
        sa.Column("auteur_id", sa.Uuid(), nullable=False),
        sa.Column("cree_le", sa.DateTime(timezone=True), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organisation_id", sa.Uuid(), nullable=False),
        sa.CheckConstraint("version > 0", name="ck_tp_priorite_version"),
        sa.CheckConstraint("date_fin IS NULL OR date_fin >= date_debut", name="ck_tp_priorite_periode"),
        sa.CheckConstraint("statut IN ('ACTIVE','INACTIVE')", name="ck_tp_priorite_statut"),
        sa.CheckConstraint("length(trim(motif)) > 0", name="ck_tp_priorite_motif"),
        sa.ForeignKeyConstraint(["organisation_id"], ["organisations.id_organisation"]),
        sa.ForeignKeyConstraint(["auteur_id", "organisation_id"], ["utilisateurs.id_utilisateur", "utilisateurs.organisation_id"], name="fk_tp_priorite_auteur_org"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("id", "organisation_id", name="uq_tp_priorite_org"),
        sa.UniqueConstraint("organisation_id", "version", name="uq_tp_priorite_version"),
        sa.UniqueConstraint("organisation_id", "date_debut", name="uq_tp_priorite_debut"),
    )
    op.create_index("ix_tiers_payant_parametrages_priorite_organisation_id", "tiers_payant_parametrages_priorite", ["organisation_id"])

    op.create_table(
        "tiers_payant_priorites",
        sa.Column("parametrage_id", sa.Uuid(), nullable=False),
        sa.Column("organisme_id", sa.Uuid(), nullable=False),
        sa.Column("convention_id", sa.Uuid(), nullable=False),
        sa.Column("rang", sa.Integer(), nullable=False),
        sa.Column("role", sa.String(20), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organisation_id", sa.Uuid(), nullable=False),
        sa.CheckConstraint("rang > 0", name="ck_tp_priorite_rang"),
        sa.CheckConstraint("role IN ('PRINCIPAL','SECONDAIRE')", name="ck_tp_priorite_role"),
        sa.CheckConstraint("role != 'PRINCIPAL' OR rang = 1", name="ck_tp_principal_premier"),
        sa.ForeignKeyConstraint(["organisation_id"], ["organisations.id_organisation"]),
        sa.ForeignKeyConstraint(["parametrage_id", "organisation_id"], ["tiers_payant_parametrages_priorite.id", "tiers_payant_parametrages_priorite.organisation_id"], name="fk_tp_priorite_entete_org"),
        sa.ForeignKeyConstraint(["organisme_id", "organisation_id"], ["organismes_prise_en_charge.id", "organismes_prise_en_charge.organisation_id"], name="fk_tp_priorite_organisme_org"),
        sa.ForeignKeyConstraint(["convention_id", "organisation_id"], ["tiers_payant_conventions.id", "tiers_payant_conventions.organisation_id"], name="fk_tp_priorite_convention_org"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("parametrage_id", "rang", name="uq_tp_priorite_rang"),
        sa.UniqueConstraint("parametrage_id", "organisme_id", name="uq_tp_priorite_organisme"),
    )
    op.create_index("ix_tiers_payant_priorites_organisation_id", "tiers_payant_priorites", ["organisation_id"])
    op.create_index("ix_tp_priorite_parametrage", "tiers_payant_priorites", ["organisation_id", "parametrage_id", "rang"])
    op.create_index("uq_tp_priorite_principal", "tiers_payant_priorites", ["parametrage_id"], unique=True,
                    postgresql_where=sa.text("role = 'PRINCIPAL'"), sqlite_where=sa.text("role = 'PRINCIPAL'"))

    op.create_table(
        "tiers_payant_evenements",
        sa.Column("entite_type", sa.String(50), nullable=False),
        sa.Column("entite_id", sa.Uuid(), nullable=False),
        sa.Column("type", sa.String(80), nullable=False),
        sa.Column("donnees", sa.JSON(), nullable=False),
        sa.Column("auteur_id", sa.Uuid(), nullable=False),
        sa.Column("date", sa.DateTime(timezone=True), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organisation_id", sa.Uuid(), nullable=False),
        sa.CheckConstraint("length(trim(type)) > 0", name="ck_tp_event_type"),
        sa.ForeignKeyConstraint(["organisation_id"], ["organisations.id_organisation"]),
        sa.ForeignKeyConstraint(["auteur_id", "organisation_id"], ["utilisateurs.id_utilisateur", "utilisateurs.organisation_id"], name="fk_tp_event_auteur_org"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_tiers_payant_evenements_organisation_id", "tiers_payant_evenements", ["organisation_id"])
    op.create_index("ix_tp_event_entity", "tiers_payant_evenements", ["organisation_id", "entite_type", "entite_id", "date"])
    _create_immutable_triggers()

    permissions = sa.table("permissions", sa.column("id_permission", sa.Uuid()), sa.column("code", sa.String()), sa.column("nom", sa.String()))
    op.bulk_insert(permissions, [{
        "id_permission": uuid5(NAMESPACE, "permission:" + code), "code": code, "nom": label,
    } for code, label in PERMISSIONS])


def _create_immutable_triggers() -> None:
    bind = op.get_bind()
    tables = ("tiers_payant_conventions", "tiers_payant_priorites", "tiers_payant_evenements")
    if bind.dialect.name == "sqlite":
        for table in tables:
            for action in ("UPDATE", "DELETE"):
                op.execute(f"CREATE TRIGGER {table}_{action.lower()}_immutable BEFORE {action} ON {table} BEGIN SELECT RAISE(ABORT, 'Référentiel Tiers Payant versionné immuable'); END")
    else:
        for table in tables:
            op.execute(f"CREATE OR REPLACE FUNCTION {table}_immutable() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN RAISE EXCEPTION 'Référentiel Tiers Payant versionné immuable'; END $$")
            op.execute(f"CREATE TRIGGER {table}_immutable BEFORE UPDATE OR DELETE ON {table} FOR EACH ROW EXECUTE FUNCTION {table}_immutable()")


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "sqlite":
        for table in ("tiers_payant_conventions", "tiers_payant_priorites", "tiers_payant_evenements"):
            op.execute(f"DROP TRIGGER IF EXISTS {table}_update_immutable")
            op.execute(f"DROP TRIGGER IF EXISTS {table}_delete_immutable")
    else:
        for table in ("tiers_payant_conventions", "tiers_payant_priorites", "tiers_payant_evenements"):
            op.execute(f"DROP TRIGGER IF EXISTS {table}_immutable ON {table}")
            op.execute(f"DROP FUNCTION IF EXISTS {table}_immutable()")
    role_permissions = sa.table("roles_permissions", sa.column("permission_id", sa.Uuid()))
    permission_table = sa.table("permissions", sa.column("id_permission", sa.Uuid()))
    ids = [uuid5(NAMESPACE, "permission:" + code) for code, _ in PERMISSIONS]
    bind.execute(role_permissions.delete().where(role_permissions.c.permission_id.in_(ids)))
    bind.execute(permission_table.delete().where(permission_table.c.id_permission.in_(ids)))
    for index in ("ix_tp_event_entity", "ix_tiers_payant_evenements_organisation_id"):
        op.drop_index(index, table_name="tiers_payant_evenements")
    op.drop_table("tiers_payant_evenements")
    op.drop_index("uq_tp_priorite_principal", table_name="tiers_payant_priorites")
    op.drop_index("ix_tp_priorite_parametrage", table_name="tiers_payant_priorites")
    op.drop_index("ix_tiers_payant_priorites_organisation_id", table_name="tiers_payant_priorites")
    op.drop_table("tiers_payant_priorites")
    op.drop_index("ix_tiers_payant_parametrages_priorite_organisation_id", table_name="tiers_payant_parametrages_priorite")
    op.drop_table("tiers_payant_parametrages_priorite")
    op.drop_index("ix_tp_lien_beneficiaire", table_name="tiers_payant_adhesion_beneficiaires")
    op.drop_index("ix_tiers_payant_adhesion_beneficiaires_organisation_id", table_name="tiers_payant_adhesion_beneficiaires")
    op.drop_table("tiers_payant_adhesion_beneficiaires")
    op.drop_index("ix_tp_adhesion_convention_periode", table_name="tiers_payant_adhesions")
    op.drop_index("ix_tiers_payant_adhesions_organisation_id", table_name="tiers_payant_adhesions")
    op.drop_table("tiers_payant_adhesions")
    op.drop_index("ix_tp_beneficiaire_client", table_name="tiers_payant_beneficiaires")
    op.drop_index("ix_tiers_payant_beneficiaires_organisation_id", table_name="tiers_payant_beneficiaires")
    op.drop_table("tiers_payant_beneficiaires")
    op.drop_index("ix_tp_convention_organisme_periode", table_name="tiers_payant_conventions")
    op.drop_index("ix_tiers_payant_conventions_organisation_id", table_name="tiers_payant_conventions")
    op.drop_table("tiers_payant_conventions")
