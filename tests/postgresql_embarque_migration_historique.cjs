/* Migration PostgreSQL embarquée sur historique exclusivement fictif et mémoire. */
const fs=require('fs'),path=require('path'),assert=require('node:assert/strict'),{randomUUID,createHash}=require('crypto');
const {PGlite}=require('@electric-sql/pglite'),{btree_gist}=require('@electric-sql/pglite/contrib/btree_gist');
const dir=process.env.EG32_VALIDATION_DIR;if(!dir)throw Error('Répertoire de SQL de validation obligatoire');
const quote=x=>"'"+String(x).replaceAll("'","''")+"'";
(async()=>{const pg=new PGlite({extensions:{btree_gist}});try{
 await pg.exec(fs.readFileSync(path.join(dir,'avant-eg32-postgresql.sql'),'utf8'));
 const parents=fs.readFileSync(path.join(dir,'parents-fictifs.sql'),'utf8').split('\n').filter(l=>!l.includes("caisse.encaisser.groupe")).join('\n');await pg.exec(parents);
 const f=JSON.parse(fs.readFileSync(path.join(dir,'parents-fictifs.sql.json'))),id=randomUUID(),reg=randomUUID(),move=randomUUID();
 const period=(await pg.query('SELECT id FROM caisse_periodes_site WHERE site_id='+quote(f.site))).rows[0].id;
 const pdf=Buffer.from('PDF HISTORIQUE EXCLUSIVEMENT FICTIF'),hash=createHash('sha256').update(pdf).digest('hex');
 await pg.exec(`BEGIN;
 INSERT INTO caisse_encaissements(id,organisation_id,vente_id,session_id,periode_id,numero,total_xaf,date,instantane,pdf,pdf_sha256)
 VALUES(${[id,f.org,f.ventes[0],f.session,period].map(quote)},70,100,now(),'{"fictif":true}',decode('${pdf.toString('hex')}','hex'),${quote(hash)});
 INSERT INTO caisse_reglements(id,organisation_id,encaissement_id,mode,montant,rendu) VALUES(${[reg,f.org,id].map(quote)},'ESPECES',120,20);
 INSERT INTO caisse_mouvements(id,organisation_id,session_id,reglement_id,auteur_id,mode,montant_net,date) VALUES(${[move,f.org,f.session,reg,f.user].map(quote)},'ESPECES',100,now()); COMMIT;`);
 const cols='id,organisation_id,vente_id,session_id,periode_id,numero,total_xaf,date,instantane,pdf,pdf_sha256';
 const before=(await pg.query('SELECT '+cols+' FROM caisse_encaissements')).rows;
 const payments=(await pg.query('SELECT * FROM caisse_reglements')).rows;
 await pg.exec(fs.readFileSync(path.join(dir,'eg32-postgresql.sql'),'utf8'));
 assert.deepEqual((await pg.query('SELECT '+cols+' FROM caisse_encaissements')).rows,before);
 assert.deepEqual((await pg.query('SELECT * FROM caisse_reglements')).rows,payments);
 assert.equal((await pg.query('SELECT encaissement_id FROM caisse_ventes_encaissees')).rows[0].encaissement_id,id);
 assert.equal(Number((await pg.query('SELECT count(*) FROM caisse_ventilations')).rows[0].count),0);
 assert.equal((await pg.query('SELECT version_num FROM alembic_version')).rows[0].version_num,'eg34a2026');
 let immutable;try{await pg.exec("UPDATE caisse_encaissements SET total_xaf=0");}catch(e){immutable=e;}assert(immutable);
 console.log('PostgreSQL embarqué : upgrade a46 → eg34, migration additive, ancien encaissement/règlement/PDF identiques, immuabilité préservée : OK');
 }finally{await pg.close();}})().catch(e=>{console.error(e.message);process.exit(1);});
