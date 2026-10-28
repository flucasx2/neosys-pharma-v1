"""Mode générique additif; valeurs historiques conservées sans conversion."""
from alembic import op
import sqlalchemy as sa

revision = "20261028_01"
down_revision = "20261022_02"
branch_labels = None
depends_on = None

MODES = "'SANS_TIERS','PRISE_EN_CHARGE','CNAMGS','MUTUELLE','CNAMGS_MUTUELLE','CREDIT'"
ANCIENS_MODES = "'SANS_TIERS','CNAMGS','MUTUELLE','CNAMGS_MUTUELLE','CREDIT'"
TABLES = (("ventes", "ck_vente_mode"), ("proforma_versions", "ck_proforma_mode"))


def _remplacer_modes(modes):
    connection = op.get_bind()
    for table, constraint in TABLES:
        triggers = []
        if connection.dialect.name == "sqlite":
            # Le batch reconstruit la table. Conserver aussi les triggers des
            # tables filles qui référencent son nom pendant le renommage.
            triggers = connection.execute(sa.text(
                "SELECT name, sql FROM sqlite_master WHERE type='trigger' "
                "AND sql IS NOT NULL AND (tbl_name=:table OR instr(sql,:table)>0)"
            ), {"table": table}).all()
            for name, _ in triggers:
                quoted = connection.dialect.identifier_preparer.quote(name)
                op.execute(sa.text(f"DROP TRIGGER {quoted}"))
        with op.batch_alter_table(table) as batch:
            batch.drop_constraint(constraint, type_="check")
            batch.create_check_constraint(constraint, f"mode IN ({modes})")
        for _, sql in triggers:
            op.execute(sa.text(sql))


def upgrade():
    _remplacer_modes(MODES)


def downgrade():
    # Ne jamais convertir ni supprimer une opération générique existante.
    connection = op.get_bind()
    for table, _ in TABLES:
        if connection.execute(sa.text(f"SELECT 1 FROM {table} WHERE mode = 'PRISE_EN_CHARGE' LIMIT 1")).first():
            raise RuntimeError("Downgrade refusé: opérations génériques présentes.")
    _remplacer_modes(ANCIENS_MODES)
