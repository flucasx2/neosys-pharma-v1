"""P4.6/3.2 : expansion compatible, aucun parcours groupé activé.

Préparée pour bases jetables uniquement tant que son application n'est pas autorisée.
Les définitions SQL sont figées dans cette révision, indépendantes des modèles futurs.
"""
from alembic import op
import sqlalchemy as sa
from neosys_pharma.infrastructure.encaissement_groupe_sql_v1 import guard_sql, drop_guard_sql

revision = 'eg32a2026'
down_revision = 'a46c001d2026'
branch_labels = None
depends_on = None

TABLE_SQL = {'postgresql': {'caisse_dossiers_groupes': 'CREATE TABLE caisse_dossiers_groupes (\n'
                                           '\tsite_id UUID NOT NULL, \n'
                                           '\templacement_id UUID NOT NULL, \n'
                                           '\tcaisse_id UUID NOT NULL, \n'
                                           '\tsession_id UUID NOT NULL, \n'
                                           '\tauteur_id UUID NOT NULL, \n'
                                           '\tcompte_id UUID, \n'
                                           "\tetat VARCHAR(20) DEFAULT 'BROUILLON' NOT NULL, \n"
                                           "\trevision INTEGER DEFAULT '1' NOT NULL, \n"
                                           '\tempreinte_selection VARCHAR(64) NOT NULL, \n'
                                           '\tcree_le TIMESTAMP WITH TIME ZONE NOT NULL, \n'
                                           '\tid UUID NOT NULL, \n'
                                           '\torganisation_id UUID NOT NULL, \n'
                                           '\tPRIMARY KEY (id), \n'
                                           '\tFOREIGN KEY(site_id, organisation_id) REFERENCES sites '
                                           '(id_site, organisation_id), \n'
                                           '\tFOREIGN KEY(emplacement_id, site_id) REFERENCES emplacements '
                                           '(id_emplacement, site_id), \n'
                                           '\tFOREIGN KEY(caisse_id, emplacement_id) REFERENCES caisses '
                                           '(id_caisse, emplacement_id), \n'
                                           '\tFOREIGN KEY(session_id, organisation_id) REFERENCES '
                                           'caisse_sessions (id, organisation_id), \n'
                                           '\tFOREIGN KEY(auteur_id, organisation_id) REFERENCES '
                                           'utilisateurs (id_utilisateur, organisation_id), \n'
                                           '\tFOREIGN KEY(compte_id, organisation_id) REFERENCES '
                                           'fidelite_comptes (id, organisation_id), \n'
                                           '\tCONSTRAINT ck_groupe_etat CHECK (etat IN '
                                           "('BROUILLON','EN_REGLEMENT','ENCAISSE','ANNULE')), \n"
                                           '\tCONSTRAINT ck_groupe_revision CHECK (revision > 0 AND '
                                           'length(empreinte_selection) = 64), \n'
                                           '\tCONSTRAINT uq_dossier_groupe_org UNIQUE (id, '
                                           'organisation_id), \n'
                                           '\tFOREIGN KEY(organisation_id) REFERENCES organisations '
                                           '(id_organisation)\n'
                                           ')',
                'caisse_selections_groupes': 'CREATE TABLE caisse_selections_groupes (\n'
                                             '\tdossier_id UUID NOT NULL, \n'
                                             '\tvente_id UUID NOT NULL, \n'
                                             '\trevision_vente INTEGER NOT NULL, \n'
                                             '\tordre INTEGER NOT NULL, \n'
                                             '\tid UUID NOT NULL, \n'
                                             '\torganisation_id UUID NOT NULL, \n'
                                             '\tPRIMARY KEY (id), \n'
                                             '\tFOREIGN KEY(dossier_id, organisation_id) REFERENCES '
                                             'caisse_dossiers_groupes (id, organisation_id), \n'
                                             '\tFOREIGN KEY(vente_id, organisation_id) REFERENCES ventes '
                                             '(id, organisation_id), \n'
                                             '\tCONSTRAINT uq_selection_groupe_vente UNIQUE (dossier_id, '
                                             'vente_id), \n'
                                             '\tCONSTRAINT uq_selection_groupe_ordre UNIQUE (dossier_id, '
                                             'ordre), \n'
                                             '\tCONSTRAINT ck_selection_groupe_revision CHECK '
                                             '(revision_vente > 0 AND ordre > 0), \n'
                                             '\tCONSTRAINT uq_selection_groupe_org UNIQUE (id, '
                                             'organisation_id), \n'
                                             '\tFOREIGN KEY(organisation_id) REFERENCES organisations '
                                             '(id_organisation)\n'
                                             ')',
                'caisse_ventilations': 'CREATE TABLE caisse_ventilations (\n'
                                       '\tencaissement_id UUID NOT NULL, \n'
                                       '\tvente_id UUID NOT NULL, \n'
                                       '\trevision_vente INTEGER NOT NULL, \n'
                                       '\tmontant_ht NUMERIC(18, 0) NOT NULL, \n'
                                       '\tmontant_tva NUMERIC(18, 0) NOT NULL, \n'
                                       '\tnet_ttc NUMERIC(18, 0) NOT NULL, \n'
                                       "\tremise_ligne NUMERIC(18, 0) DEFAULT '0' NOT NULL, \n"
                                       "\tremise_globale NUMERIC(18, 0) DEFAULT '0' NOT NULL, \n"
                                       '\tinstantane JSON NOT NULL, \n'
                                       '\tid UUID NOT NULL, \n'
                                       '\torganisation_id UUID NOT NULL, \n'
                                       '\tPRIMARY KEY (id), \n'
                                       '\tFOREIGN KEY(encaissement_id, organisation_id) REFERENCES '
                                       'caisse_encaissements (id, organisation_id), \n'
                                       '\tFOREIGN KEY(vente_id, organisation_id) REFERENCES ventes (id, '
                                       'organisation_id), \n'
                                       '\tCONSTRAINT uq_ventilation_vente UNIQUE (vente_id), \n'
                                       '\tCONSTRAINT uq_ventilation_enc_org UNIQUE (id, encaissement_id, '
                                       'organisation_id), \n'
                                       '\tCONSTRAINT uq_ventilation_vente_parent UNIQUE (id, vente_id), \n'
                                       '\tCONSTRAINT ck_ventilation_montants CHECK (revision_vente > 0 AND '
                                       'montant_ht >= 0 AND montant_tva >= 0 AND net_ttc >= 0 AND '
                                       'remise_ligne >= 0 AND remise_globale >= 0 AND montant_ht + '
                                       'montant_tva = net_ttc), \n'
                                       '\tCONSTRAINT uq_ventilation_org UNIQUE (id, organisation_id), \n'
                                       '\tFOREIGN KEY(organisation_id) REFERENCES organisations '
                                       '(id_organisation)\n'
                                       ')',
                'caisse_allocations_reglements': 'CREATE TABLE caisse_allocations_reglements (\n'
                                                 '\tencaissement_id UUID NOT NULL, \n'
                                                 '\treglement_id UUID NOT NULL, \n'
                                                 '\tventilation_id UUID NOT NULL, \n'
                                                 '\tvente_id UUID NOT NULL, \n'
                                                 '\tligne_vente_id UUID NOT NULL, \n'
                                                 '\tmontant_net NUMERIC(18, 0) NOT NULL, \n'
                                                 '\tid UUID NOT NULL, \n'
                                                 '\torganisation_id UUID NOT NULL, \n'
                                                 '\tPRIMARY KEY (id), \n'
                                                 '\tFOREIGN KEY(reglement_id, encaissement_id, '
                                                 'organisation_id) REFERENCES caisse_reglements (id, '
                                                 'encaissement_id, organisation_id), \n'
                                                 '\tFOREIGN KEY(ventilation_id, encaissement_id, '
                                                 'organisation_id) REFERENCES caisse_ventilations (id, '
                                                 'encaissement_id, organisation_id), \n'
                                                 '\tFOREIGN KEY(ventilation_id, vente_id) REFERENCES '
                                                 'caisse_ventilations (id, vente_id), \n'
                                                 '\tFOREIGN KEY(ligne_vente_id, vente_id) REFERENCES '
                                                 'vente_lignes (id, vente_id), \n'
                                                 '\tFOREIGN KEY(ligne_vente_id, organisation_id) REFERENCES '
                                                 'vente_lignes (id, organisation_id), \n'
                                                 '\tCONSTRAINT uq_allocation_reglement_ligne UNIQUE '
                                                 '(reglement_id, ventilation_id, ligne_vente_id), \n'
                                                 '\tCONSTRAINT ck_allocation_montant CHECK (montant_net > '
                                                 '0), \n'
                                                 '\tCONSTRAINT uq_allocation_reglement_org UNIQUE (id, '
                                                 'organisation_id), \n'
                                                 '\tFOREIGN KEY(organisation_id) REFERENCES organisations '
                                                 '(id_organisation)\n'
                                                 ')',
                'caisse_ventes_encaissees': 'CREATE TABLE caisse_ventes_encaissees (\n'
                                            '\tvente_id UUID NOT NULL, \n'
                                            '\torganisation_id UUID NOT NULL, \n'
                                            '\tencaissement_id UUID NOT NULL, \n'
                                            '\tPRIMARY KEY (vente_id), \n'
                                            '\tFOREIGN KEY(vente_id, organisation_id) REFERENCES ventes (id, '
                                            'organisation_id), \n'
                                            '\tFOREIGN KEY(encaissement_id, organisation_id) REFERENCES '
                                            'caisse_encaissements (id, organisation_id) DEFERRABLE INITIALLY '
                                            'DEFERRED\n'
                                            ')'},
 'sqlite': {'caisse_dossiers_groupes': 'CREATE TABLE caisse_dossiers_groupes (\n'
                                       '\tsite_id CHAR(32) NOT NULL, \n'
                                       '\templacement_id CHAR(32) NOT NULL, \n'
                                       '\tcaisse_id CHAR(32) NOT NULL, \n'
                                       '\tsession_id CHAR(32) NOT NULL, \n'
                                       '\tauteur_id CHAR(32) NOT NULL, \n'
                                       '\tcompte_id CHAR(32), \n'
                                       "\tetat VARCHAR(20) DEFAULT 'BROUILLON' NOT NULL, \n"
                                       "\trevision INTEGER DEFAULT '1' NOT NULL, \n"
                                       '\tempreinte_selection VARCHAR(64) NOT NULL, \n'
                                       '\tcree_le DATETIME NOT NULL, \n'
                                       '\tid CHAR(32) NOT NULL, \n'
                                       '\torganisation_id CHAR(32) NOT NULL, \n'
                                       '\tPRIMARY KEY (id), \n'
                                       '\tFOREIGN KEY(site_id, organisation_id) REFERENCES sites (id_site, '
                                       'organisation_id), \n'
                                       '\tFOREIGN KEY(emplacement_id, site_id) REFERENCES emplacements '
                                       '(id_emplacement, site_id), \n'
                                       '\tFOREIGN KEY(caisse_id, emplacement_id) REFERENCES caisses '
                                       '(id_caisse, emplacement_id), \n'
                                       '\tFOREIGN KEY(session_id, organisation_id) REFERENCES '
                                       'caisse_sessions (id, organisation_id), \n'
                                       '\tFOREIGN KEY(auteur_id, organisation_id) REFERENCES utilisateurs '
                                       '(id_utilisateur, organisation_id), \n'
                                       '\tFOREIGN KEY(compte_id, organisation_id) REFERENCES '
                                       'fidelite_comptes (id, organisation_id), \n'
                                       '\tCONSTRAINT ck_groupe_etat CHECK (etat IN '
                                       "('BROUILLON','EN_REGLEMENT','ENCAISSE','ANNULE')), \n"
                                       '\tCONSTRAINT ck_groupe_revision CHECK (revision > 0 AND '
                                       'length(empreinte_selection) = 64), \n'
                                       '\tCONSTRAINT uq_dossier_groupe_org UNIQUE (id, organisation_id), \n'
                                       '\tFOREIGN KEY(organisation_id) REFERENCES organisations '
                                       '(id_organisation)\n'
                                       ')',
            'caisse_selections_groupes': 'CREATE TABLE caisse_selections_groupes (\n'
                                         '\tdossier_id CHAR(32) NOT NULL, \n'
                                         '\tvente_id CHAR(32) NOT NULL, \n'
                                         '\trevision_vente INTEGER NOT NULL, \n'
                                         '\tordre INTEGER NOT NULL, \n'
                                         '\tid CHAR(32) NOT NULL, \n'
                                         '\torganisation_id CHAR(32) NOT NULL, \n'
                                         '\tPRIMARY KEY (id), \n'
                                         '\tFOREIGN KEY(dossier_id, organisation_id) REFERENCES '
                                         'caisse_dossiers_groupes (id, organisation_id), \n'
                                         '\tFOREIGN KEY(vente_id, organisation_id) REFERENCES ventes (id, '
                                         'organisation_id), \n'
                                         '\tCONSTRAINT uq_selection_groupe_vente UNIQUE (dossier_id, '
                                         'vente_id), \n'
                                         '\tCONSTRAINT uq_selection_groupe_ordre UNIQUE (dossier_id, '
                                         'ordre), \n'
                                         '\tCONSTRAINT ck_selection_groupe_revision CHECK (revision_vente > '
                                         '0 AND ordre > 0), \n'
                                         '\tCONSTRAINT uq_selection_groupe_org UNIQUE (id, '
                                         'organisation_id), \n'
                                         '\tFOREIGN KEY(organisation_id) REFERENCES organisations '
                                         '(id_organisation)\n'
                                         ')',
            'caisse_ventilations': 'CREATE TABLE caisse_ventilations (\n'
                                   '\tencaissement_id CHAR(32) NOT NULL, \n'
                                   '\tvente_id CHAR(32) NOT NULL, \n'
                                   '\trevision_vente INTEGER NOT NULL, \n'
                                   '\tmontant_ht BIGINT NOT NULL, \n'
                                   '\tmontant_tva BIGINT NOT NULL, \n'
                                   '\tnet_ttc BIGINT NOT NULL, \n'
                                   "\tremise_ligne BIGINT DEFAULT '0' NOT NULL, \n"
                                   "\tremise_globale BIGINT DEFAULT '0' NOT NULL, \n"
                                   '\tinstantane JSON NOT NULL, \n'
                                   '\tid CHAR(32) NOT NULL, \n'
                                   '\torganisation_id CHAR(32) NOT NULL, \n'
                                   '\tPRIMARY KEY (id), \n'
                                   '\tFOREIGN KEY(encaissement_id, organisation_id) REFERENCES '
                                   'caisse_encaissements (id, organisation_id), \n'
                                   '\tFOREIGN KEY(vente_id, organisation_id) REFERENCES ventes (id, '
                                   'organisation_id), \n'
                                   '\tCONSTRAINT uq_ventilation_vente UNIQUE (vente_id), \n'
                                   '\tCONSTRAINT uq_ventilation_enc_org UNIQUE (id, encaissement_id, '
                                   'organisation_id), \n'
                                   '\tCONSTRAINT uq_ventilation_vente_parent UNIQUE (id, vente_id), \n'
                                   '\tCONSTRAINT ck_ventilation_montants CHECK (revision_vente > 0 AND '
                                   'montant_ht >= 0 AND montant_tva >= 0 AND net_ttc >= 0 AND remise_ligne '
                                   '>= 0 AND remise_globale >= 0 AND montant_ht + montant_tva = net_ttc), \n'
                                   '\tCONSTRAINT uq_ventilation_org UNIQUE (id, organisation_id), \n'
                                   '\tFOREIGN KEY(organisation_id) REFERENCES organisations '
                                   '(id_organisation)\n'
                                   ')',
            'caisse_allocations_reglements': 'CREATE TABLE caisse_allocations_reglements (\n'
                                             '\tencaissement_id CHAR(32) NOT NULL, \n'
                                             '\treglement_id CHAR(32) NOT NULL, \n'
                                             '\tventilation_id CHAR(32) NOT NULL, \n'
                                             '\tvente_id CHAR(32) NOT NULL, \n'
                                             '\tligne_vente_id CHAR(32) NOT NULL, \n'
                                             '\tmontant_net BIGINT NOT NULL, \n'
                                             '\tid CHAR(32) NOT NULL, \n'
                                             '\torganisation_id CHAR(32) NOT NULL, \n'
                                             '\tPRIMARY KEY (id), \n'
                                             '\tFOREIGN KEY(reglement_id, encaissement_id, organisation_id) '
                                             'REFERENCES caisse_reglements (id, encaissement_id, '
                                             'organisation_id), \n'
                                             '\tFOREIGN KEY(ventilation_id, encaissement_id, '
                                             'organisation_id) REFERENCES caisse_ventilations (id, '
                                             'encaissement_id, organisation_id), \n'
                                             '\tFOREIGN KEY(ventilation_id, vente_id) REFERENCES '
                                             'caisse_ventilations (id, vente_id), \n'
                                             '\tFOREIGN KEY(ligne_vente_id, vente_id) REFERENCES '
                                             'vente_lignes (id, vente_id), \n'
                                             '\tFOREIGN KEY(ligne_vente_id, organisation_id) REFERENCES '
                                             'vente_lignes (id, organisation_id), \n'
                                             '\tCONSTRAINT uq_allocation_reglement_ligne UNIQUE '
                                             '(reglement_id, ventilation_id, ligne_vente_id), \n'
                                             '\tCONSTRAINT ck_allocation_montant CHECK (montant_net > 0), \n'
                                             '\tCONSTRAINT uq_allocation_reglement_org UNIQUE (id, '
                                             'organisation_id), \n'
                                             '\tFOREIGN KEY(organisation_id) REFERENCES organisations '
                                             '(id_organisation)\n'
                                             ')',
            'caisse_ventes_encaissees': 'CREATE TABLE caisse_ventes_encaissees (\n'
                                        '\tvente_id CHAR(32) NOT NULL, \n'
                                        '\torganisation_id CHAR(32) NOT NULL, \n'
                                        '\tencaissement_id CHAR(32) NOT NULL, \n'
                                        '\tPRIMARY KEY (vente_id), \n'
                                        '\tFOREIGN KEY(vente_id, organisation_id) REFERENCES ventes (id, '
                                        'organisation_id), \n'
                                        '\tFOREIGN KEY(encaissement_id, organisation_id) REFERENCES '
                                        'caisse_encaissements (id, organisation_id) DEFERRABLE INITIALLY '
                                        'DEFERRED\n'
                                        ')'}}
INDEX_SQL = {'caisse_dossiers_groupes': ['CREATE INDEX ix_caisse_dossiers_groupes_organisation_id ON '
                             'caisse_dossiers_groupes (organisation_id)'],
 'caisse_selections_groupes': ['CREATE INDEX ix_caisse_selections_groupes_organisation_id ON '
                               'caisse_selections_groupes (organisation_id)'],
 'caisse_ventilations': ['CREATE INDEX ix_caisse_ventilations_organisation_id ON caisse_ventilations '
                         '(organisation_id)'],
 'caisse_allocations_reglements': ['CREATE INDEX ix_caisse_allocations_reglements_organisation_id ON '
                                   'caisse_allocations_reglements (organisation_id)'],
 'caisse_ventes_encaissees': []}


LEGACY_CHECKS = {'caisse_encaissements': ['numero > 0 AND total_xaf >= 0'],
 'caisse_confirmations': ['montant > 0',
                          "mode IN ('CARTE','MOBILE_MONEY','CHEQUE','VIREMENT')",
                          "source IN ('MANUEL_TERMINAL','MANUEL_JUSTIFICATIF','TECHNIQUE_PRESTATAIRE')"],
 'caisse_reglements': ['montant > 0 AND rendu >= 0 AND rendu <= montant',
                       "mode IN ('ESPECES','CARTE','MOBILE_MONEY','CHEQUE','VIREMENT')",
                       "(mode='ESPECES' AND confirmation_id IS NULL) OR (mode<>'ESPECES' AND confirmation_id "
                       'IS NOT NULL AND rendu=0)'],
 'vente_retours': ['montant >= 0']}

def _batch(table):
    return op.batch_alter_table(table, table_args=tuple(sa.CheckConstraint(c) for c in LEGACY_CHECKS[table]))


def _restore_immutable_sqlite():
    if op.get_bind().dialect.name == 'sqlite':
        for table in ('caisse_encaissements','caisse_confirmations','caisse_reglements','vente_retours'):
            for action in ('UPDATE','DELETE'):
                op.execute(f"DROP TRIGGER IF EXISTS {table}_{action.lower()}_immutable")
                op.execute(f"CREATE TRIGGER {table}_{action.lower()}_immutable BEFORE {action} ON {table} BEGIN SELECT RAISE(ABORT,'Journal financier immuable'); END")


def upgrade():
    dialect = op.get_bind().dialect.name
    if dialect not in TABLE_SQL:
        raise ValueError('PostgreSQL ou SQLite requis.')
    for name in ('caisse_dossiers_groupes','caisse_selections_groupes'):
        op.execute(TABLE_SQL[dialect][name])
        for sql in INDEX_SQL[name]: op.execute(sql)
    with _batch('caisse_encaissements') as b:
        b.add_column(sa.Column('type_encaissement',sa.String(20),nullable=False,server_default='INDIVIDUEL'))
        b.add_column(sa.Column('dossier_groupe_id',sa.Uuid(),nullable=True))
        b.alter_column('vente_id',existing_type=sa.Uuid(),nullable=True)
        b.create_foreign_key('fk_encaissement_dossier_org','caisse_dossiers_groupes',['dossier_groupe_id','organisation_id'],['id','organisation_id'])
        b.create_unique_constraint('uq_encaissement_dossier',['dossier_groupe_id'])
        b.create_check_constraint('ck_encaissement_forme',"(type_encaissement='INDIVIDUEL' AND vente_id IS NOT NULL AND dossier_groupe_id IS NULL) OR (type_encaissement='GROUPE' AND vente_id IS NULL AND dossier_groupe_id IS NOT NULL)")
    with _batch('caisse_confirmations') as b:
        b.add_column(sa.Column('dossier_groupe_id',sa.Uuid(),nullable=True))
        b.add_column(sa.Column('revision_groupe',sa.Integer(),nullable=True))
        b.alter_column('vente_id',existing_type=sa.Uuid(),nullable=True)
        b.alter_column('revision_vente',existing_type=sa.Integer(),nullable=True)
        b.create_foreign_key('fk_confirmation_dossier_org','caisse_dossiers_groupes',['dossier_groupe_id','organisation_id'],['id','organisation_id'])
        b.create_check_constraint('ck_confirmation_portee',"(vente_id IS NOT NULL AND dossier_groupe_id IS NULL AND revision_vente IS NOT NULL AND revision_vente > 0 AND revision_groupe IS NULL) OR (vente_id IS NULL AND dossier_groupe_id IS NOT NULL AND revision_vente IS NULL AND revision_groupe IS NOT NULL AND revision_groupe > 0)")
    with _batch('caisse_reglements') as b:
        b.create_unique_constraint('uq_reglement_enc_org',['id','encaissement_id','organisation_id'])
    for name in ('caisse_ventilations','caisse_allocations_reglements','caisse_ventes_encaissees'):
        op.execute(TABLE_SQL[dialect][name])
        for sql in INDEX_SQL[name]: op.execute(sql)
    with _batch('vente_retours') as b:
        b.add_column(sa.Column('ventilation_id',sa.Uuid(),nullable=True))
        b.create_foreign_key('fk_retour_ventilation_enc_org','caisse_ventilations',['ventilation_id','encaissement_id','organisation_id'],['id','encaissement_id','organisation_id'])
    # Identités historiques avérées uniquement, sans inventer de montant/allocation.
    op.execute('INSERT INTO caisse_ventes_encaissees(vente_id,organisation_id,encaissement_id) SELECT vente_id,organisation_id,id FROM caisse_encaissements WHERE vente_id IS NOT NULL')
    _restore_immutable_sqlite()
    for sql in guard_sql(dialect): op.execute(sql)
    code='caisse.encaisser.groupe'
    from uuid import UUID,uuid5
    key=uuid5(UUID('5e0d5c59-9934-40a6-b798-92d3f544667d'),'permission:'+code)
    table=sa.table('permissions',sa.column('id_permission',sa.Uuid()),sa.column('code',sa.String()),sa.column('nom',sa.String()))
    op.bulk_insert(table,[dict(id_permission=key,code=code,nom='Encaisser atomiquement plusieurs préparations autorisées')])


def downgrade():
    bind=op.get_bind(); dialect=bind.dialect.name
    # Refus explicite : aucune perte silencieuse de nouvelles données financières.
    for table in ('caisse_dossiers_groupes','caisse_selections_groupes','caisse_ventilations','caisse_allocations_reglements'):
        if bind.execute(sa.text(f'SELECT count(*) FROM {table}')).scalar():
            raise ValueError('Downgrade refusé : des données de groupes ou ventilations existent.')
    if bind.execute(sa.text("SELECT count(*) FROM caisse_encaissements WHERE type_encaissement='GROUPE'")).scalar():
        raise ValueError('Downgrade refusé : encaissement groupé existant.')
    for sql in drop_guard_sql(dialect): op.execute(sql)
    with _batch('vente_retours') as b:
        b.drop_constraint('fk_retour_ventilation_enc_org',type_='foreignkey')
        b.drop_column('ventilation_id')
    op.drop_table('caisse_ventes_encaissees')
    op.drop_table('caisse_allocations_reglements')
    op.drop_table('caisse_ventilations')
    with _batch('caisse_reglements') as b:
        b.drop_constraint('uq_reglement_enc_org',type_='unique')
    with _batch('caisse_confirmations') as b:
        b.drop_constraint('ck_confirmation_portee',type_='check')
        b.drop_constraint('fk_confirmation_dossier_org',type_='foreignkey')
        b.alter_column('vente_id',existing_type=sa.Uuid(),nullable=False)
        b.alter_column('revision_vente',existing_type=sa.Integer(),nullable=False)
        b.drop_column('dossier_groupe_id');b.drop_column('revision_groupe')
    with _batch('caisse_encaissements') as b:
        b.drop_constraint('ck_encaissement_forme',type_='check')
        b.drop_constraint('uq_encaissement_dossier',type_='unique')
        b.drop_constraint('fk_encaissement_dossier_org',type_='foreignkey')
        b.alter_column('vente_id',existing_type=sa.Uuid(),nullable=False)
        b.drop_column('dossier_groupe_id');b.drop_column('type_encaissement')
    op.drop_table('caisse_selections_groupes');op.drop_table('caisse_dossiers_groupes')
    op.execute("DELETE FROM roles_permissions WHERE permission_id IN (SELECT id_permission FROM permissions WHERE code='caisse.encaisser.groupe')")
    op.execute("DELETE FROM permissions WHERE code='caisse.encaisser.groupe'")
    _restore_immutable_sqlite()
