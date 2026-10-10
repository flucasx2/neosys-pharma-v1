"""P4 vente preparation snapshots reservations et permissions additives

Revision ID: 45a17d1b7b8f
Revises: 2b3c30f2b213
Create Date: 2026-10-10 19:48:58.235370

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '45a17d1b7b8f'
down_revision: Union[str, Sequence[str], None] = '2b3c30f2b213'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_index('uq_caisse_id_emplacement', 'caisses', ['id_caisse', 'emplacement_id'], unique=True)
    op.create_index('uq_poste_id_emplacement', 'postes_vente', ['id_poste_vente', 'emplacement_id'], unique=True)
    # Additive P4 objects.
    op.create_table('ventes',
    sa.Column('site_id', sa.Uuid(), nullable=False),
    sa.Column('emplacement_id', sa.Uuid(), nullable=False),
    sa.Column('poste_id', sa.Uuid(), nullable=False),
    sa.Column('vendeur_id', sa.Uuid(), nullable=False),
    sa.Column('caisse_id', sa.Uuid(), nullable=True),
    sa.Column('etat', sa.String(length=30), nullable=False),
    sa.Column('mode', sa.String(length=30), nullable=False),
    sa.Column('destinataire', sa.JSON(), nullable=False),
    sa.Column('revision', sa.Integer(), nullable=False),
    sa.Column('cree_le', sa.DateTime(timezone=True), nullable=False),
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('organisation_id', sa.Uuid(), nullable=False),
    sa.CheckConstraint("etat IN ('PREPARATION','EN_ATTENTE','VALIDEE_PREPARATION','TRANSMISE','ENCAISSEE','ANNULEE')", name='ck_vente_etat'),
    sa.CheckConstraint("mode IN ('SANS_TIERS','CNAMGS','MUTUELLE','CNAMGS_MUTUELLE','CREDIT')", name='ck_vente_mode'),
    sa.CheckConstraint('revision >= 1', name='ck_vente_revision'),
    sa.ForeignKeyConstraint(['caisse_id', 'emplacement_id'], ['caisses.id_caisse', 'caisses.emplacement_id'], name='fk_vente_caisse_emplacement'),
    sa.ForeignKeyConstraint(['emplacement_id', 'site_id'], ['emplacements.id_emplacement', 'emplacements.site_id'], name='fk_vente_emplacement_site'),
    sa.ForeignKeyConstraint(['organisation_id'], ['organisations.id_organisation'], ),
    sa.ForeignKeyConstraint(['poste_id', 'emplacement_id'], ['postes_vente.id_poste_vente', 'postes_vente.emplacement_id'], name='fk_vente_poste_emplacement'),
    sa.ForeignKeyConstraint(['site_id', 'organisation_id'], ['sites.id_site', 'sites.organisation_id'], name='fk_vente_site_org'),
    sa.ForeignKeyConstraint(['vendeur_id', 'organisation_id'], ['utilisateurs.id_utilisateur', 'utilisateurs.organisation_id'], name='fk_vente_vendeur_org'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('id', 'organisation_id', name='uq_vente_org')
    )
    with op.batch_alter_table('ventes', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_ventes_emplacement_id'), ['emplacement_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_ventes_organisation_id'), ['organisation_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_ventes_site_id'), ['site_id'], unique=False)

    op.create_table('vente_evenements',
    sa.Column('vente_id', sa.Uuid(), nullable=False),
    sa.Column('auteur_id', sa.Uuid(), nullable=False),
    sa.Column('date', sa.DateTime(timezone=True), nullable=False),
    sa.Column('type', sa.String(length=80), nullable=False),
    sa.Column('donnees', sa.JSON(), nullable=False),
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('organisation_id', sa.Uuid(), nullable=False),
    sa.ForeignKeyConstraint(['auteur_id', 'organisation_id'], ['utilisateurs.id_utilisateur', 'utilisateurs.organisation_id'], name='fk_evenement_auteur_org'),
    sa.ForeignKeyConstraint(['organisation_id'], ['organisations.id_organisation'], ),
    sa.ForeignKeyConstraint(['vente_id', 'organisation_id'], ['ventes.id', 'ventes.organisation_id'], name='fk_evenement_vente_org'),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('vente_evenements', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_vente_evenements_organisation_id'), ['organisation_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_vente_evenements_vente_id'), ['vente_id'], unique=False)

    op.create_table('vente_lignes',
    sa.Column('vente_id', sa.Uuid(), nullable=False),
    sa.Column('produit_id', sa.Uuid(), nullable=False),
    sa.Column('conditionnement_id', sa.Uuid(), nullable=False),
    sa.Column('actif', sa.Boolean(), nullable=False),
    sa.Column('quantite', sa.Integer(), nullable=False),
    sa.Column('designation', sa.String(length=200), nullable=False),
    sa.Column('conditionnement', sa.String(length=200), nullable=False),
    sa.Column('reference', sa.String(length=200), nullable=True),
    sa.Column('instantane_tarif', sa.JSON(), nullable=False),
    sa.Column('montants', sa.JSON(), nullable=False),
    sa.Column('remise_appliquee', sa.JSON(), nullable=True),
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('organisation_id', sa.Uuid(), nullable=False),
    sa.CheckConstraint('quantite > 0', name='ck_ligne_vente_qte'),
    sa.ForeignKeyConstraint(['conditionnement_id', 'produit_id', 'organisation_id'], ['catalogue_conditionnements.id_conditionnement', 'catalogue_conditionnements.produit_id', 'catalogue_conditionnements.organisation_id'], name='fk_ligne_conditionnement_org'),
    sa.ForeignKeyConstraint(['organisation_id'], ['organisations.id_organisation'], ),
    sa.ForeignKeyConstraint(['produit_id', 'organisation_id'], ['catalogue_produits.id_produit', 'catalogue_produits.organisation_id'], name='fk_ligne_produit_org'),
    sa.ForeignKeyConstraint(['vente_id', 'organisation_id'], ['ventes.id', 'ventes.organisation_id'], name='fk_ligne_vente_org'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('id', 'organisation_id', name='uq_ligne_vente_org'),
    sa.UniqueConstraint('id', 'vente_id', name='uq_ligne_vente_parent')
    )
    with op.batch_alter_table('vente_lignes', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_vente_lignes_organisation_id'), ['organisation_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_vente_lignes_vente_id'), ['vente_id'], unique=False)

    op.create_table('vente_demandes_remise',
    sa.Column('vente_id', sa.Uuid(), nullable=False),
    sa.Column('ligne_id', sa.Uuid(), nullable=True),
    sa.Column('type', sa.String(length=20), nullable=False),
    sa.Column('valeur', sa.Numeric(precision=18, scale=2), nullable=False),
    sa.Column('statut', sa.String(length=20), nullable=False),
    sa.Column('revision_vente', sa.Integer(), nullable=False),
    sa.Column('auteur_id', sa.Uuid(), nullable=False),
    sa.Column('justification', sa.String(length=2000), nullable=False),
    sa.Column('autorisation', sa.JSON(), nullable=True),
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('organisation_id', sa.Uuid(), nullable=False),
    sa.CheckConstraint("statut IN ('DEMANDEE','AUTORISEE','REFUSEE','INVALIDEE')", name='ck_remise_statut'),
    sa.CheckConstraint("type IN ('POURCENTAGE','MONTANT_XAF') AND valeur > 0 AND (type <> 'POURCENTAGE' OR valeur <= 100)", name='ck_remise_valeur'),
    sa.ForeignKeyConstraint(['auteur_id', 'organisation_id'], ['utilisateurs.id_utilisateur', 'utilisateurs.organisation_id'], name='fk_remise_auteur_org'),
    sa.ForeignKeyConstraint(['ligne_id', 'vente_id'], ['vente_lignes.id', 'vente_lignes.vente_id'], name='fk_remise_ligne_vente'),
    sa.ForeignKeyConstraint(['organisation_id'], ['organisations.id_organisation'], ),
    sa.ForeignKeyConstraint(['vente_id', 'organisation_id'], ['ventes.id', 'ventes.organisation_id'], name='fk_remise_vente_org'),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('vente_demandes_remise', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_vente_demandes_remise_organisation_id'), ['organisation_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_vente_demandes_remise_vente_id'), ['vente_id'], unique=False)

    op.create_table('vente_reservations',
    sa.Column('ligne_id', sa.Uuid(), nullable=False),
    sa.Column('reservation_id', sa.Uuid(), nullable=False),
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('organisation_id', sa.Uuid(), nullable=False),
    sa.ForeignKeyConstraint(['ligne_id', 'organisation_id'], ['vente_lignes.id', 'vente_lignes.organisation_id'], name='fk_reservation_ligne_org'),
    sa.ForeignKeyConstraint(['organisation_id'], ['organisations.id_organisation'], ),
    sa.ForeignKeyConstraint(['reservation_id', 'organisation_id'], ['stock_reservations.id', 'stock_reservations.organisation_id'], name='fk_reservation_stock_org'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('reservation_id', name='uq_reservation_vente_stock')
    )
    with op.batch_alter_table('vente_reservations', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_vente_reservations_ligne_id'), ['ligne_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_vente_reservations_organisation_id'), ['organisation_id'], unique=False)

    # ### end Alembic commands ###


    permissions = (
        ('vente.consulter','Consulter les préparations autorisées'),
        ('vente.preparer','Créer et modifier les préparations'),
        ('vente.valider','Valider une préparation sans encaissement'),
        ('vente.transmettre','Transmettre une préparation à une caisse autorisée'),
        ('vente.annuler','Annuler une préparation et libérer ses réservations'),
        ('vente.credit','Préparer le mode crédit sans finalisation financière'),
        ('vente.remise.demander','Demander une remise de ligne ou globale'),
        ('vente.remise.autoriser','Décider les demandes de remise dans le périmètre autorisé'),
    )
    from uuid import UUID,uuid5
    table=sa.table('permissions',sa.column('id_permission',sa.Uuid()),sa.column('code',sa.String()),sa.column('nom',sa.String()))
    op.bulk_insert(table,[dict(id_permission=uuid5(UUID('5e0d5c59-9934-40a6-b798-92d3f544667d'),'permission:'+code),code=code,nom=nom) for code,nom in permissions])
    if op.get_bind().dialect.name=='sqlite':
        for action in ('UPDATE','DELETE'):
            op.execute(f"CREATE TRIGGER vente_evenements_{action.lower()}_immutable BEFORE {action} ON vente_evenements BEGIN SELECT RAISE(ABORT, 'Journal Vente immuable'); END")
    else:
        op.execute("CREATE OR REPLACE FUNCTION vente_evenements_immutable() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN RAISE EXCEPTION 'Journal Vente immuable'; END $$")
        op.execute("CREATE TRIGGER vente_evenements_immutable BEFORE UPDATE OR DELETE ON vente_evenements FOR EACH ROW EXECUTE FUNCTION vente_evenements_immutable()")


def downgrade() -> None:
    """Downgrade schema."""
    codes=('vente.consulter','vente.preparer','vente.valider','vente.transmettre','vente.annuler','vente.credit','vente.remise.demander','vente.remise.autoriser')
    bind=op.get_bind()
    for code in codes:
        bind.execute(sa.text('DELETE FROM roles_permissions WHERE permission_id IN (SELECT id_permission FROM permissions WHERE code=:code)'),{'code':code})
        bind.execute(sa.text('DELETE FROM permissions WHERE code=:code'),{'code':code})

    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('vente_reservations', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_vente_reservations_organisation_id'))
        batch_op.drop_index(batch_op.f('ix_vente_reservations_ligne_id'))

    op.drop_table('vente_reservations')
    with op.batch_alter_table('vente_demandes_remise', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_vente_demandes_remise_vente_id'))
        batch_op.drop_index(batch_op.f('ix_vente_demandes_remise_organisation_id'))

    op.drop_table('vente_demandes_remise')
    with op.batch_alter_table('vente_lignes', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_vente_lignes_vente_id'))
        batch_op.drop_index(batch_op.f('ix_vente_lignes_organisation_id'))

    op.drop_table('vente_lignes')
    with op.batch_alter_table('vente_evenements', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_vente_evenements_vente_id'))
        batch_op.drop_index(batch_op.f('ix_vente_evenements_organisation_id'))

    op.drop_table('vente_evenements')
    with op.batch_alter_table('ventes', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_ventes_site_id'))
        batch_op.drop_index(batch_op.f('ix_ventes_organisation_id'))
        batch_op.drop_index(batch_op.f('ix_ventes_emplacement_id'))

    op.drop_table('ventes')
    # ### end Alembic commands ###

    op.drop_index('uq_poste_id_emplacement', table_name='postes_vente')
    op.drop_index('uq_caisse_id_emplacement', table_name='caisses')
    if op.get_bind().dialect.name=='postgresql':op.execute('DROP FUNCTION IF EXISTS vente_evenements_immutable()')
