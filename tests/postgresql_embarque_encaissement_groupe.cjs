/* PostgreSQL embarqué PGlite, exclusivement mémoire : pas de serveur métier. */
const fs=require('fs'),path=require('path'),assert=require('node:assert/strict'),{randomUUID}=require('crypto');
const {PGlite}=require('@electric-sql/pglite'),{btree_gist}=require('@electric-sql/pglite/contrib/btree_gist');
const dir=process.env.EG32_VALIDATION_DIR;if(!dir)throw Error('EG32_VALIDATION_DIR avec SQL/fixtures fictives obligatoire');
const q=x=>"'"+String(x).replaceAll("'","''")+"'",uid=()=>randomUUID();
(async()=>{
 const pg=new PGlite({extensions:{btree_gist}}),checks=[];const f=JSON.parse(fs.readFileSync(path.join(dir,'parents-fictifs.sql.json')));
 const exec=s=>pg.exec(s),one=async s=>(await pg.query(s)).rows[0];
 const rejected=async(sql,expected)=>{await exec('BEGIN');let error;try{await exec(sql+'; COMMIT');}catch(e){error=e;}await exec('ROLLBACK');assert(error,'SQL devrait être refusé');if(expected)assert.match(error.message,expected);};
 try{
 await exec(fs.readFileSync(path.join(dir,'upgrade-postgresql.sql'),'utf8'));await exec(fs.readFileSync(path.join(dir,'parents-fictifs.sql'),'utf8'));
 const period=(await one('SELECT id FROM caisse_periodes_site WHERE site_id='+q(f.site))).id;
 const dossier=(id,state='BROUILLON',session=f.session)=>`INSERT INTO caisse_dossiers_groupes(id,organisation_id,site_id,emplacement_id,caisse_id,session_id,auteur_id,etat,revision,empreinte_selection,cree_le) VALUES(${[id,f.org,f.site,f.loc,f.caisse,session,f.user].map(q)},${q(state)},1,${q('a'.repeat(64))},now())`;
 const selection=(d,i)=>`INSERT INTO caisse_selections_groupes(id,organisation_id,dossier_id,vente_id,revision_vente,ordre) VALUES(${[uid(),f.org,d,f.ventes[i]].map(q)},1,${i+1})`;
 const enc=(id,vente,d,total,num)=>`INSERT INTO caisse_encaissements(id,organisation_id,vente_id,dossier_groupe_id,type_encaissement,session_id,periode_id,numero,total_xaf,date,instantane,pdf,pdf_sha256) VALUES(${[id,f.org].map(q)},${vente?q(vente):'NULL'},${d?q(d):'NULL'},${q(d?'GROUPE':'INDIVIDUEL')},${[f.session,period].map(q)},${num},${total},now(),'{}','\\x504446',${q('b'.repeat(64))})`;
 const vent=(id,e,i,total=100)=>`INSERT INTO caisse_ventilations(id,organisation_id,encaissement_id,vente_id,revision_vente,montant_ht,montant_tva,net_ttc,remise_ligne,remise_globale,instantane) VALUES(${[id,f.org,e,f.ventes[i]].map(q)},1,${total},0,${total},0,0,'{"fictif":true}')`;
 const payment=(id,e,total)=>`INSERT INTO caisse_reglements(id,organisation_id,encaissement_id,mode,montant,rendu) VALUES(${[id,f.org,e].map(q)},'ESPECES',${total},0)`;
 const alloc=(e,r,v,i,amount)=>`INSERT INTO caisse_allocations_reglements(id,organisation_id,encaissement_id,reglement_id,ventilation_id,vente_id,ligne_vente_id,montant_net) VALUES(${[uid(),f.org,e,r,v,f.ventes[i],f.lignes[i]].map(q)},${amount})`;
 const d=uid();await exec(dossier(d)+';'+selection(d,0)+';'+selection(d,1));
 // Ancien lien puis ventilation vers un autre encaissement : refus avant validation totale.
 await exec('BEGIN;'+enc(uid(),f.ventes[0],null,0,90)+'; COMMIT');
 await exec('BEGIN');const wrong=uid();await exec(enc(wrong,null,d,200,91));let duplicate;try{await exec(vent(uid(),wrong,0));}catch(e){duplicate=e;}await exec('ROLLBACK');assert.match(duplicate.message,/Vente deja encaissee/);checks.push('historique → groupe : doublon refusé');
 // Isoler la seconde direction dans un nouveau moteur sans supprimer de journaux.
 await pg.close();
 const pg2=new PGlite({extensions:{btree_gist}});await pg2.exec(fs.readFileSync(path.join(dir,'upgrade-postgresql.sql'),'utf8'));await pg2.exec(fs.readFileSync(path.join(dir,'parents-fictifs.sql'),'utf8'));
 const run=s=>pg2.exec(s),query=s=>pg2.query(s);
 const d2=uid(),e=uid(),v0=uid(),v1=uid(),r=uid();await run(dossier(d2)+';'+selection(d2,0)+';'+selection(d2,1));
 await run('BEGIN;'+enc(e,null,d2,200,92)+';'+vent(v0,e,0)+';'+vent(v1,e,1)+';'+payment(r,e,200)+';'+alloc(e,r,v0,0,100)+';'+alloc(e,r,v1,1,100)+`; UPDATE caisse_dossiers_groupes SET etat='ENCAISSE',revision=2 WHERE id=${q(d2)}; COMMIT`);
 assert.equal(Number((await query('SELECT count(*) FROM caisse_ventes_encaissees')).rows[0].count),2);checks.push('groupe complet et sommes différées validés');
 await run('BEGIN');duplicate=null;try{await run(enc(uid(),f.ventes[0],null,0,93));}catch(e){duplicate=e;}await run('ROLLBACK');assert.match(duplicate.message,/Vente deja encaissee/);checks.push('groupe → historique : doublon refusé');
 for(const sql of ['DELETE FROM caisse_ventilations','DELETE FROM caisse_allocations_reglements','DELETE FROM caisse_ventes_encaissees',`DELETE FROM caisse_selections_groupes WHERE dossier_id=${q(d2)}`]){await run('BEGIN');let err;try{await run(sql);}catch(e){err=e;}await run('ROLLBACK');assert(err);}checks.push('immutabilité et sélection figée');
 // Troisième moteur : échec de commit sur des allocations financièrement incomplètes.
 const pg3=new PGlite({extensions:{btree_gist}});await pg3.exec(fs.readFileSync(path.join(dir,'upgrade-postgresql.sql'),'utf8'));await pg3.exec(fs.readFileSync(path.join(dir,'parents-fictifs.sql'),'utf8'));
 const d3=uid(),e3=uid(),a=uid(),b=uid(),p=uid();await pg3.exec(dossier(d3)+';'+selection(d3,0)+';'+selection(d3,1));
 await pg3.exec('BEGIN');let totals;try{await pg3.exec(enc(e3,null,d3,200,94)+';'+vent(a,e3,0)+';'+vent(b,e3,1)+';'+payment(p,e3,200)+';'+alloc(e3,p,a,0,99)+';'+alloc(e3,p,b,1,100)+`; UPDATE caisse_dossiers_groupes SET etat='ENCAISSE' WHERE id=${q(d3)}; COMMIT`);}catch(err){totals=err;}
 await pg3.exec('ROLLBACK');assert.match(totals.message,/Sommes des allocations/);assert.equal(Number((await pg3.query('SELECT count(*) FROM caisse_encaissements')).rows[0].count),0);checks.push('commit invalide refusé et rollback complet');
 let scope;try{await pg3.exec(dossier(uid(),'BROUILLON',uid()));}catch(e){scope=e;}assert(scope);checks.push('session hors contexte refusée');
 const roles=(await pg3.query("SELECT count(*) FROM roles_permissions rp JOIN permissions p ON p.id_permission=rp.permission_id WHERE p.code='caisse.encaisser.groupe'")).rows[0].count;assert.equal(Number(roles),0);checks.push('permission présente sans attribution');
 const version=(await pg3.query('SELECT version()')).rows[0].version;await pg2.close();await pg3.close();console.log(JSON.stringify({ok:true,checks,version,limite:'PostgreSQL embarqué, pas de concurrence multi-connexions ni serveur natif'},null,2));
 }finally{try{await pg.close();}catch{}}
})().catch(e=>{console.error(e.message);process.exit(1);});
