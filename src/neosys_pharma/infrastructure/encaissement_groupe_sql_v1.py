"""DDL versionné de 3.2 : figé pour la reproductibilité de la migration eg32a2026.

SQLite : unicités/portées/immuabilité ; PostgreSQL : contrôles différés de clôture.
Aucune finalisation groupée n'est exposée dans cet incrément.
"""
IMMUTABLE = ('caisse_ventilations', 'caisse_allocations_reglements', 'caisse_ventes_encaissees')
TOTAL_TABLES = ('caisse_encaissements', 'caisse_reglements', 'caisse_ventilations', 'caisse_allocations_reglements')


def guard_sql(dialect):
    statements = []
    if dialect == 'sqlite':
        for table, enc in [('caisse_encaissements', 'NEW.id'), ('caisse_ventilations', 'NEW.encaissement_id')]:
            statements.append(f"""CREATE TRIGGER {table}_eg32_claim BEFORE INSERT ON {table}
            WHEN NEW.vente_id IS NOT NULL BEGIN
              INSERT OR IGNORE INTO caisse_ventes_encaissees(vente_id,organisation_id,encaissement_id)
                VALUES(NEW.vente_id,NEW.organisation_id,{enc});
              SELECT CASE WHEN EXISTS(SELECT 1 FROM caisse_ventes_encaissees WHERE vente_id=NEW.vente_id
                AND (encaissement_id<>{enc} OR organisation_id<>NEW.organisation_id))
                THEN RAISE(ABORT,'Vente deja encaissee') END;
            END""")
        for table in IMMUTABLE:
            for action in ('UPDATE', 'DELETE'):
                statements.append(f"CREATE TRIGGER {table}_eg32_{action.lower()} BEFORE {action} ON {table} BEGIN SELECT RAISE(ABORT,'Lien financier immuable'); END")
        for action in ('INSERT','UPDATE','DELETE'):
            refs=('NEW','OLD') if action=='UPDATE' else ('OLD',) if action=='DELETE' else ('NEW',)
            frozen=' OR '.join(f"EXISTS(SELECT 1 FROM caisse_dossiers_groupes d WHERE d.id={ref}.dossier_id AND (d.etat<>'BROUILLON' OR EXISTS(SELECT 1 FROM caisse_confirmations c WHERE c.dossier_groupe_id=d.id)))" for ref in refs)
            statements.append(f"CREATE TRIGGER caisse_selections_groupes_eg32_{action.lower()} BEFORE {action} ON caisse_selections_groupes WHEN {frozen} BEGIN SELECT RAISE(ABORT,'Selection figee'); END")
        statements.append("""CREATE TRIGGER caisse_dossiers_groupes_eg32_context BEFORE INSERT ON caisse_dossiers_groupes
          WHEN NOT EXISTS(SELECT 1 FROM caisse_sessions s WHERE s.id=NEW.session_id AND s.organisation_id=NEW.organisation_id AND s.site_id=NEW.site_id AND s.emplacement_id=NEW.emplacement_id AND s.caisse_id=NEW.caisse_id)
          BEGIN SELECT RAISE(ABORT,'Session hors contexte'); END""")
        for action in ('INSERT','UPDATE'):
            statements.append(f"""CREATE TRIGGER caisse_selections_groupes_eg32_scope_{action.lower()} BEFORE {action} ON caisse_selections_groupes
              WHEN NOT EXISTS(SELECT 1 FROM caisse_dossiers_groupes d JOIN ventes v ON v.id=NEW.vente_id WHERE d.id=NEW.dossier_id AND d.organisation_id=NEW.organisation_id AND v.organisation_id=d.organisation_id AND v.site_id=d.site_id AND v.emplacement_id=d.emplacement_id AND v.caisse_id=d.caisse_id)
              BEGIN SELECT RAISE(ABORT,'Vente hors contexte du groupe'); END""")
        statements.append("""CREATE TRIGGER caisse_dossiers_groupes_eg32_terminal BEFORE UPDATE ON caisse_dossiers_groupes
          WHEN OLD.etat IN ('ENCAISSE','ANNULE') BEGIN SELECT RAISE(ABORT,'Dossier terminal immuable'); END""")
        return statements
    if dialect != 'postgresql':
        raise ValueError('PostgreSQL et SQLite uniquement.')
    statements.append("""CREATE FUNCTION eg32_claim() RETURNS trigger LANGUAGE plpgsql AS $$
    DECLARE enc uuid; BEGIN
      IF NEW.vente_id IS NULL THEN RETURN NEW; END IF;
      IF TG_TABLE_NAME='caisse_encaissements' THEN enc:=NEW.id; ELSE enc:=NEW.encaissement_id; END IF;
      PERFORM 1 FROM ventes WHERE id=NEW.vente_id AND organisation_id=NEW.organisation_id FOR UPDATE;
      INSERT INTO caisse_ventes_encaissees(vente_id,organisation_id,encaissement_id)
        VALUES(NEW.vente_id,NEW.organisation_id,enc) ON CONFLICT(vente_id) DO NOTHING;
      IF EXISTS(SELECT 1 FROM caisse_ventes_encaissees WHERE vente_id=NEW.vente_id AND
        (encaissement_id<>enc OR organisation_id<>NEW.organisation_id)) THEN
        RAISE EXCEPTION 'Vente deja encaissee' USING ERRCODE='23505'; END IF;
      RETURN NEW; END $$""")
    for table in ('caisse_encaissements', 'caisse_ventilations'):
        statements.append(f'CREATE TRIGGER {table}_eg32_claim BEFORE INSERT ON {table} FOR EACH ROW EXECUTE FUNCTION eg32_claim()')
    statements.append("""CREATE FUNCTION eg32_immutable() RETURNS trigger LANGUAGE plpgsql AS $$
      BEGIN RAISE EXCEPTION 'Lien financier immuable' USING ERRCODE='23514'; END $$""")
    for table in IMMUTABLE:
        statements.append(f'CREATE TRIGGER {table}_eg32_immutable BEFORE UPDATE OR DELETE ON {table} FOR EACH ROW EXECUTE FUNCTION eg32_immutable()')
    statements.append("""CREATE FUNCTION eg32_context() RETURNS trigger LANGUAGE plpgsql AS $$
      BEGIN
      IF TG_TABLE_NAME='caisse_dossiers_groupes' THEN
        IF TG_OP='UPDATE' AND OLD.etat IN ('ENCAISSE','ANNULE') THEN
          RAISE EXCEPTION 'Dossier terminal immuable' USING ERRCODE='23514'; END IF;
        IF TG_OP='UPDATE' AND (OLD.etat<>'BROUILLON' OR EXISTS(SELECT 1 FROM caisse_confirmations c WHERE c.dossier_groupe_id=OLD.id)) AND ROW(NEW.organisation_id,NEW.site_id,NEW.emplacement_id,NEW.caisse_id,NEW.session_id,NEW.auteur_id,NEW.compte_id) IS DISTINCT FROM ROW(OLD.organisation_id,OLD.site_id,OLD.emplacement_id,OLD.caisse_id,OLD.session_id,OLD.auteur_id,OLD.compte_id) THEN
          RAISE EXCEPTION 'Contexte financier fige' USING ERRCODE='23514'; END IF;
        IF NOT EXISTS(SELECT 1 FROM caisse_sessions s WHERE s.id=NEW.session_id AND s.organisation_id=NEW.organisation_id
          AND s.site_id=NEW.site_id AND s.emplacement_id=NEW.emplacement_id AND s.caisse_id=NEW.caisse_id) THEN
          RAISE EXCEPTION 'Session hors contexte' USING ERRCODE='23514'; END IF;
      ELSIF TG_TABLE_NAME='caisse_selections_groupes' THEN
        IF TG_OP='DELETE' THEN
          IF EXISTS(SELECT 1 FROM caisse_dossiers_groupes d WHERE d.id=OLD.dossier_id AND
            (d.etat<>'BROUILLON' OR EXISTS(SELECT 1 FROM caisse_confirmations c WHERE c.dossier_groupe_id=d.id))) THEN
            RAISE EXCEPTION 'Selection figee' USING ERRCODE='23514'; END IF;
          RETURN OLD;
        END IF;
        IF EXISTS(SELECT 1 FROM caisse_dossiers_groupes d WHERE d.id=NEW.dossier_id AND
          (d.etat<>'BROUILLON' OR EXISTS(SELECT 1 FROM caisse_confirmations c WHERE c.dossier_groupe_id=d.id)))
          OR (TG_OP='UPDATE' AND EXISTS(SELECT 1 FROM caisse_dossiers_groupes d WHERE d.id=OLD.dossier_id AND (d.etat<>'BROUILLON' OR EXISTS(SELECT 1 FROM caisse_confirmations c WHERE c.dossier_groupe_id=d.id)))) THEN
          RAISE EXCEPTION 'Selection figee' USING ERRCODE='23514'; END IF;
        IF NOT EXISTS(SELECT 1 FROM caisse_dossiers_groupes d JOIN ventes v ON v.id=NEW.vente_id
          WHERE d.id=NEW.dossier_id AND d.organisation_id=NEW.organisation_id AND v.organisation_id=d.organisation_id
          AND v.site_id=d.site_id AND v.emplacement_id=d.emplacement_id AND v.caisse_id=d.caisse_id) THEN
          RAISE EXCEPTION 'Vente hors contexte du groupe' USING ERRCODE='23514'; END IF;
      END IF; RETURN NEW; END $$""")
    statements.extend([
        'CREATE TRIGGER caisse_dossiers_groupes_eg32_context BEFORE INSERT OR UPDATE ON caisse_dossiers_groupes FOR EACH ROW EXECUTE FUNCTION eg32_context()',
        'CREATE TRIGGER caisse_selections_groupes_eg32_context BEFORE INSERT OR UPDATE OR DELETE ON caisse_selections_groupes FOR EACH ROW EXECUTE FUNCTION eg32_context()',
    ])
    statements.append("""CREATE FUNCTION eg32_totals() RETURNS trigger LANGUAGE plpgsql AS $$
    DECLARE eid uuid; e caisse_encaissements%ROWTYPE; n bigint; total numeric; BEGIN
      IF TG_TABLE_NAME='caisse_encaissements' THEN eid:=NEW.id; ELSE eid:=NEW.encaissement_id; END IF;
      SELECT * INTO e FROM caisse_encaissements WHERE id=eid;
      IF NOT FOUND THEN RETURN NULL; END IF;
      SELECT count(*),coalesce(sum(net_ttc),0) INTO n,total FROM caisse_ventilations WHERE encaissement_id=eid;
      -- L'ancien moteur individuel reste compatible, sans inventer de ventilation historique.
      IF e.type_encaissement='INDIVIDUEL' AND n=0 THEN RETURN NULL; END IF;
      IF total<>e.total_xaf OR (e.type_encaissement='GROUPE' AND n<2)
         OR (e.type_encaissement='INDIVIDUEL' AND (n<>1 OR EXISTS(SELECT 1 FROM caisse_ventilations WHERE encaissement_id=eid AND vente_id<>e.vente_id))) THEN
        RAISE EXCEPTION 'Ventilations incompatibles avec encaissement' USING ERRCODE='23514'; END IF;
      IF e.type_encaissement='GROUPE' AND (
        NOT EXISTS(SELECT 1 FROM caisse_dossiers_groupes WHERE id=e.dossier_groupe_id AND etat='ENCAISSE' AND session_id=e.session_id)
        OR EXISTS((SELECT vente_id FROM caisse_selections_groupes WHERE dossier_id=e.dossier_groupe_id EXCEPT SELECT vente_id FROM caisse_ventilations WHERE encaissement_id=eid))
        OR EXISTS((SELECT vente_id FROM caisse_ventilations WHERE encaissement_id=eid EXCEPT SELECT vente_id FROM caisse_selections_groupes WHERE dossier_id=e.dossier_groupe_id))) THEN
        RAISE EXCEPTION 'Groupe final different de sa selection' USING ERRCODE='23514'; END IF;
      IF EXISTS(SELECT 1 FROM caisse_ventilations x JOIN ventes v ON v.id=x.vente_id JOIN caisse_sessions s ON s.id=e.session_id
        WHERE x.encaissement_id=eid AND (v.site_id<>s.site_id OR v.emplacement_id<>s.emplacement_id OR v.caisse_id<>s.caisse_id)) THEN
        RAISE EXCEPTION 'Ventilation hors contexte de caisse' USING ERRCODE='23514'; END IF;
      IF (SELECT coalesce(sum(montant-rendu),0) FROM caisse_reglements WHERE encaissement_id=eid)<>e.total_xaf
        OR EXISTS(SELECT 1 FROM caisse_reglements r WHERE r.encaissement_id=eid AND r.montant-r.rendu<>
          (SELECT coalesce(sum(a.montant_net),0) FROM caisse_allocations_reglements a WHERE a.reglement_id=r.id))
        OR EXISTS(SELECT 1 FROM caisse_ventilations x WHERE x.encaissement_id=eid AND x.net_ttc<>
          (SELECT coalesce(sum(a.montant_net),0) FROM caisse_allocations_reglements a WHERE a.ventilation_id=x.id)) THEN
        RAISE EXCEPTION 'Sommes des allocations incompatibles' USING ERRCODE='23514'; END IF;
      RETURN NULL; END $$""")
    for table in TOTAL_TABLES:
        statements.append(f'CREATE CONSTRAINT TRIGGER {table}_eg32_totals AFTER INSERT ON {table} DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION eg32_totals()')
    return statements


def drop_guard_sql(dialect):
    if dialect == 'sqlite':
        names = [f'{t}_eg32_claim' for t in ('caisse_encaissements','caisse_ventilations')]
        names += [f'{t}_eg32_{a}' for t in IMMUTABLE for a in ('update','delete')]
        names += [f'caisse_selections_groupes_eg32_{a}' for a in ('insert','update','delete')]
        names += ['caisse_dossiers_groupes_eg32_terminal','caisse_dossiers_groupes_eg32_context','caisse_selections_groupes_eg32_scope_insert','caisse_selections_groupes_eg32_scope_update']
        return ['DROP TRIGGER IF EXISTS '+n for n in names]
    statements = []
    for table in ('caisse_encaissements','caisse_ventilations'):
        statements.append(f'DROP TRIGGER IF EXISTS {table}_eg32_claim ON {table}')
    for table in IMMUTABLE:
        statements.append(f'DROP TRIGGER IF EXISTS {table}_eg32_immutable ON {table}')
    for table in ('caisse_dossiers_groupes','caisse_selections_groupes'):
        statements.append(f'DROP TRIGGER IF EXISTS {table}_eg32_context ON {table}')
    for table in TOTAL_TABLES:
        statements.append(f'DROP TRIGGER IF EXISTS {table}_eg32_totals ON {table}')
    statements += [f'DROP FUNCTION IF EXISTS {f}()' for f in ('eg32_claim','eg32_immutable','eg32_context','eg32_totals')]
    return statements
