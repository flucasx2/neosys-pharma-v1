"""Associer les comptes fidélité aux ventes ventilées d'un groupe.

Révision additive : les dossiers et encaissements historiques gardent leurs
colonnes compte_id. Les brouillons et groupes déjà créés sont reliés au même
compte qu'avant; les nouveaux groupes peuvent porter un compte par vente.
"""
from alembic import op
import sqlalchemy as sa

revision = 'eg33a2026'
down_revision = 'eg32a2026'
branch_labels = None
depends_on = None


def upgrade():
    for table, check, expression in (
        ('caisse_selections_groupes', 'ck_selection_groupe_revision',
         'revision_vente > 0 AND ordre > 0 AND (compte_id IS NULL OR revision_compte > 0)'),
        ('caisse_ventilations', 'ck_ventilation_montants',
         'revision_vente > 0 AND montant_ht >= 0 AND montant_tva >= 0 AND net_ttc >= 0 '
         'AND remise_ligne >= 0 AND remise_globale >= 0 AND montant_ht + montant_tva = net_ttc '
         'AND (compte_id IS NULL OR revision_compte > 0)'),
    ):
        # Batch mode supports SQLite migration tests and emits ordinary ALTER
        # TABLE constraints on PostgreSQL.
        with op.batch_alter_table(table) as batch:
            batch.add_column(sa.Column('compte_id', sa.Uuid(), nullable=True))
            batch.add_column(sa.Column('revision_compte', sa.Integer(), nullable=True))
            batch.create_foreign_key(
                f'fk_{table}_fidelite_compte_org', 'fidelite_comptes',
                ['compte_id', 'organisation_id'], ['id', 'organisation_id'])
            batch.drop_constraint(check, type_='check')
            batch.create_check_constraint(check, expression)

    # Preserve the former single-account meaning for existing drafts/finalized
    # groups. Per-sale compensation can then resolve its beneficiary from the
    # immutable ventilation snapshot.
    op.execute("""
        UPDATE caisse_selections_groupes
        SET compte_id = (SELECT d.compte_id FROM caisse_dossiers_groupes d
                         WHERE d.id = caisse_selections_groupes.dossier_id
                           AND d.organisation_id = caisse_selections_groupes.organisation_id),
            revision_compte = (SELECT c.revision FROM caisse_dossiers_groupes d
                               JOIN fidelite_comptes c ON c.id = d.compte_id
                                 AND c.organisation_id = d.organisation_id
                               WHERE d.id = caisse_selections_groupes.dossier_id
                                 AND d.organisation_id = caisse_selections_groupes.organisation_id)
        WHERE EXISTS (SELECT 1 FROM caisse_dossiers_groupes d
                      WHERE d.id = caisse_selections_groupes.dossier_id
                        AND d.organisation_id = caisse_selections_groupes.organisation_id
                        AND d.compte_id IS NOT NULL)
    """)
    op.execute("""
        UPDATE caisse_ventilations
        SET compte_id = (SELECT e.compte_id FROM caisse_encaissements e
                         WHERE e.id = caisse_ventilations.encaissement_id
                           AND e.organisation_id = caisse_ventilations.organisation_id),
            revision_compte = (SELECT c.revision FROM caisse_encaissements e
                               JOIN fidelite_comptes c ON c.id = e.compte_id
                                 AND c.organisation_id = e.organisation_id
                               WHERE e.id = caisse_ventilations.encaissement_id
                                 AND e.organisation_id = caisse_ventilations.organisation_id)
        WHERE EXISTS (SELECT 1 FROM caisse_encaissements e
                      WHERE e.id = caisse_ventilations.encaissement_id
                        AND e.organisation_id = caisse_ventilations.organisation_id
                        AND e.compte_id IS NOT NULL)
    """)


def downgrade():
    bind = op.get_bind()
    divergent_selection = bind.execute(sa.text("""
        SELECT 1 FROM caisse_selections_groupes s
        JOIN caisse_dossiers_groupes d ON d.id = s.dossier_id AND d.organisation_id = s.organisation_id
        WHERE (s.compte_id IS NULL AND d.compte_id IS NOT NULL)
           OR (s.compte_id IS NOT NULL AND (d.compte_id IS NULL OR s.compte_id <> d.compte_id))
        LIMIT 1
    """)).first()
    divergent_ventilation = bind.execute(sa.text("""
        SELECT 1 FROM caisse_ventilations v
        JOIN caisse_encaissements e ON e.id = v.encaissement_id AND e.organisation_id = v.organisation_id
        WHERE (v.compte_id IS NULL AND e.compte_id IS NOT NULL)
           OR (v.compte_id IS NOT NULL AND (e.compte_id IS NULL OR v.compte_id <> e.compte_id))
        LIMIT 1
    """)).first()
    if divergent_selection or divergent_ventilation:
        raise RuntimeError('Downgrade eg33a2026 refusé : des ventes portent des comptes fidélité distincts du compte historique du groupe.')
    for table, check, expression in (
        ('caisse_ventilations', 'ck_ventilation_montants',
         'revision_vente > 0 AND montant_ht >= 0 AND montant_tva >= 0 AND net_ttc >= 0 '
         'AND remise_ligne >= 0 AND remise_globale >= 0 AND montant_ht + montant_tva = net_ttc'),
        ('caisse_selections_groupes', 'ck_selection_groupe_revision',
         'revision_vente > 0 AND ordre > 0'),
    ):
        with op.batch_alter_table(table) as batch:
            batch.drop_constraint(check, type_='check')
            batch.create_check_constraint(check, expression)
            batch.drop_constraint(f'fk_{table}_fidelite_compte_org', type_='foreignkey')
            batch.drop_column('revision_compte')
            batch.drop_column('compte_id')
