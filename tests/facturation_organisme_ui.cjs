// Présentation réelle de l'application ; HTTP explicitement simulé, aucune preuve financière.
const fs=require('node:fs'),path=require('node:path');
const dir=path.resolve(__dirname,'../src/neosys_pharma/presentation/web');
const html=fs.readFileSync(path.join(dir,'index.html'),'utf8').replace(/<script\b[^>]*>[\s\S]*?<\/script>/gi,'');
const sources=['organismes.js','conventions.js','creances.js','facturation_organisme.js'].map(x=>fs.readFileSync(path.join(dir,x),'utf8'));
async function scenarios(w,sources){
 let checks=0;const assert=(x,m)=>{if(!x)throw Error(m);checks++;};const d=w.document,el=id=>d.getElementById(id);
 const perms=new Set(['tiers_payant.creance.consulter','tiers_payant.document.consulter','tiers_payant.document.preparer','tiers_payant.document.valider','tiers_payant.document.emettre','tiers_payant.document.regrouper']);
 w.$=el;w.authState={me:{organisation:{id_organisation:'org'},utilisateur:{id_utilisateur:'agent'}},site:'site'};w.authHas=p=>perms.has(p);w.shellState={view:'creances'};w.shellSync=()=>{};w.authReset=()=>{};w.confirm=()=>true;
 const eligible={id:'c1',vente_id:'v1',organisme_id:'o1',montant_xaf:1234,etat_effectif:'VALIDE_POUR_FACTURATION',facturable:true,engagements:[],dossier:{revision:3},anomalies_effectives:[],snapshot:{lignes:[{etape:{convention_id:'conv1'}}]}};
 const blocked={...structuredClone(eligible),id:'c2',facturable:false,etat_effectif:'A_COMPLETER',anomalies_effectives:['Pièce manquante']};
 const calls=[],cache=new Map();let record=null,offline=true,conflict=false,downloaded=0;
 const response=(data,status=200)=>({ok:status<400,status,json:async()=>structuredClone(data),blob:async()=>new w.Blob(['PDF fictif pour test DOM'])});
 w.URL.createObjectURL=()=> 'blob:test';w.URL.revokeObjectURL=()=>{};w.HTMLAnchorElement.prototype.click=function(){downloaded++;};
 w.authFetch=async(url,options={})=>{const body=options.body?JSON.parse(options.body):null;calls.push({url,method:options.method||'GET',body});
 if(url.includes('/documents/activation'))return response({emission_recette_autorisee:false,emission_production_autorisee:false,motif:'Émission désactivée hors recette isolée'});
 if(url.endsWith('.pdf?revision=1')||url.includes('/emis/'))return response({});
 if(url.includes('/documents/organismes?'))return response({items:[{id:'o1',nom:'Organisme fictif',code:'ORG'}],total:1,page:1,page_size:25});
 if(url.includes('/documents/creances?'))return response({items:[eligible,blocked],total:2,page:1,page_size:25});
 if(url.includes('/documents/regroupements?'))return response({items:[],total:0,page:1,page_size:25});
 if(url.includes('/historique?'))return response({items:[{revision:1,etat:'PREPARATION',cree_le:'2026-10-19',auteur_id:'agent',motif:'Constitution'}],total:1,page:1,page_size:25});
 if(options.method==='POST'){
  if(cache.has(body.cle))return response(cache.get(body.cle));await new Promise(r=>w.setTimeout(r,8));
  if(url.endsWith('/preparations')){record={preparation:{id:'p1',genre:body.genre,date_debut:body.date_debut,date_fin:body.date_fin},version:{revision:1,etat:'PREPARATION',selection:body.selection},document:null};cache.set(body.cle,structuredClone(record));if(offline){offline=false;throw Error('Réponse réseau perdue');}return response(record,201);}
  if(conflict)return response({detail:'Révision modifiée'},409);
  if(url.endsWith('/valider')){record.version={...record.version,revision:2,etat:'VALIDEE'};return response(record);}
  if(url.endsWith('/selection')){record.version={revision:3,etat:'PREPARATION',selection:body.selection};return response(record);}
  if(url.endsWith('/abandonner')){record.version={...record.version,revision:4,etat:'ABANDONNEE'};return response(record);}
 }
 if(url.endsWith('/preparations/p1'))return response(record);
 if(url.includes('/documents/preparations?'))return response({items:record?[record]:[],total:record?1:0,page:1,page_size:25});
 if(url.includes('/creances?'))return response({items:[],total:0,page:1,page_size:25});throw Error('Requête inattendue '+url);
 };
 for(const source of sources){const script=d.createElement('script');script.textContent=source;d.head.append(script);}
 const wait=async fn=>{for(let i=0;i<300;i++){if(fn())return;await new Promise(r=>w.setTimeout(r,4));}throw Error('Attente dépassée');};
 const button=t=>Array.from(d.querySelectorAll('[data-pane="creances"] button')).find(x=>x.textContent===t);
 const click=async t=>{const b=button(t);assert(b,'Bouton absent : '+t);b.click();await new Promise(r=>w.setTimeout(r,0));};
 d.querySelector('[data-pane="creances"]').hidden=false;await w.creancesLoad();await click('Préparer bordereaux et factures');await wait(()=>d.querySelector('[name="genre"]'));
 assert(d.querySelector('[name="organisme_id"]').textContent.includes('Organisme fictif'),'Recherche organisme sans libellé');
 assert(calls.some(x=>x.url.includes('statut=VALIDE_POUR_FACTURATION')&&x.url.includes('page_size=25')),'Filtre serveur absent');
 const checksBoxes=Array.from(el('creances-content').querySelectorAll('article input[type="checkbox"]'));assert(checksBoxes.length===2&&!checksBoxes[0].disabled&&checksBoxes[1].disabled,'Créance bloquée sélectionnable');
 checksBoxes[0].checked=true;checksBoxes[0].dispatchEvent(new w.Event('change'));assert(el('documents-selection-total').textContent.includes('1234 XAF'),'Total de sélection absent');
 const search=el('creances-content').querySelector('form');search.elements.date_debut.value='2026-10-01';search.elements.date_fin.value='2026-10-31';
 const create=Array.from(el('creances-content').querySelectorAll('form')).find(x=>x.elements.motif);create.elements.motif.value='Préparation de recette';
 await click('Préparer le document sélectionné');button('Préparer le document sélectionné').click();await wait(()=>el('creances-message').textContent.includes('perdue'));
 const posts=()=>calls.filter(x=>x.method==='POST'&&x.url.endsWith('/preparations'));assert(posts().length===1,'Double clic non bloqué');await click('Préparer le document sélectionné');await wait(()=>button('Valider la préparation'));
 assert(posts()[0].body.cle===posts()[1].body.cle,'Clé différente au rejeu identique');assert(posts()[0].body.selection.length===1&&posts()[0].body.selection[0].creance_id==='c1','Sélection bloquée transmise');assert(record.document===null,'Préparation confondue avec émission');
 await click('Télécharger la prévisualisation');await wait(()=>downloaded===1);assert(calls.some(x=>x.url.includes('previsualisation.pdf?revision=1')),'Mauvaise révision de prévisualisation');
 let form=el('creances-content').querySelector('form');form.elements.motif.value='Contrôle';await click('Valider la préparation');await wait(()=>button('Émettre en recette isolée'));
 assert(button('Émettre en recette isolée').disabled,'Activation serveur contournée dans le navigateur');assert(!calls.some(x=>x.url.endsWith('/emettre')),'Appel émission alors que le serveur la désactive');
 await click('Historique de la préparation');await wait(()=>el('documents-history'));assert(el('documents-history').textContent.includes('agent'),'Historique auteur absent');
 conflict=true;form=el('creances-content').querySelector('form');form.elements.motif.value='Retrait à corriger';await click('Retirer les dossiers cochés');await wait(()=>el('creances-message').textContent.includes('Rechargez'));assert(form.elements.motif.value==='Retrait à corriger','Saisie perdue après conflit');conflict=false;
 const remove=el('creances-content').querySelector('article input[type="checkbox"]');remove.checked=true;remove.dispatchEvent(new w.Event('change'));await click('Retirer les dossiers cochés');await wait(()=>record.version.selection.length===0);assert(record.version.etat==='PREPARATION','Retrait conserve une validation périmée');
 await wait(()=>el('creances-content').querySelector('form'));form=el('creances-content').querySelector('form');form.elements.motif.value='Abandon';await click('Abandonner la préparation');await wait(()=>el('creances-content').textContent.includes('ABANDONNEE'));assert(!button('Valider la préparation'),'Action disponible sur dossier abandonné');
 await click('Créances prêtes à facturer');await wait(()=>d.querySelector('[name="genre"]'));w.authState.site='autre';w.shellSync();assert(!el('creances-content').children.length,'Données conservées après changement de site');assert(!calls.some(x=>x.url.includes('/finaliser')||x.url.includes('/reglements')),'Écriture de caisse déclenchée');return checks;
}
(async()=>{if(process.argv.includes('--chromium')){const {chromium}=require('playwright');const browser=await chromium.launch({headless:true});try{const page=await browser.newPage();await page.route('http://localhost:8765/**',r=>r.fulfill({status:200,contentType:'text/html',body:html}));await page.goto('http://localhost:8765/');console.log(`${await page.evaluate(async({fn,sources})=>(0,eval)(`(${fn})`)(window,sources),{fn:scenarios.toString(),sources})} assertions Chromium (HTTP simulé)`);}finally{await browser.close();}}else{const {JSDOM}=require('jsdom');const dom=new JSDOM(html,{runScripts:'dangerously',url:'https://qa.example.test'});try{console.log(`${await scenarios(dom.window,sources)} assertions DOM (HTTP simulé)`);}finally{dom.window.close();}}})().catch(e=>{console.error(e);process.exitCode=1;});
