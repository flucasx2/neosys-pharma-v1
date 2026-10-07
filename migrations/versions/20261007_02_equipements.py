"""PosteVente/Caisse -> Emplacement ; Coffre -> Site."""
from alembic import op
import sqlalchemy as sa

revision = "20261007_02"
down_revision = "20261007_01"
branch_labels = None
depends_on = None


def upgrade() -> None:
    for table, identifiant, parent, reference, contrainte in (
        ("postes_vente", "id_poste_vente", "emplacement_id", "emplacements.id_emplacement", "uq_poste_emplacement_code"),
        ("caisses", "id_caisse", "emplacement_id", "emplacements.id_emplacement", "uq_caisse_emplacement_code"),
        ("coffres", "id_coffre", "site_id", "sites.id_site", "uq_coffre_site_code"),
    ):
        op.create_table(table,
            sa.Column(identifiant, sa.Uuid(), primary_key=True),
            sa.Column(parent, sa.Uuid(), sa.ForeignKey(reference), nullable=False),
            sa.Column("code", sa.String(80), nullable=False),
            sa.Column("nom", sa.String(200), nullable=False),
            sa.Column("actif", sa.Boolean(), nullable=False),
            sa.UniqueConstraint(parent, "code", name=contrainte))
        op.create_index(f"ix_{table}_{parent}", table, [parent])


def downgrade() -> None:
    # Destructif pour les équipements : base jetable ou sauvegarde/validation.
    for table, parent in (("coffres", "site_id"), ("caisses", "emplacement_id"), ("postes_vente", "emplacement_id")):
        op.drop_index(f"ix_{table}_{parent}", table_name=table)
        op.drop_table(table)
