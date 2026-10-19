// Application HTML + modules réels, authentification et HTTP simulés.
const fs=require('node:fs'),path=require('node:path');
const dir=path.resolve(__dirname,'../src/neosys_pharma/presentation/web');
const html=fs.readFileSync(path.join(dir,'index.html'),'utf8').replace(/<script\b[^>]*>[\s\S]*?<\/script>/gi,'');
const sources=['organismes.js','conventions.js'].map(x=>fs.readFileSync(path.join(dir,x),'utf8'));
async function scenarios(w,sources){
 let checks=0;const assert=(x,message)=>{if(!x)throw Error(message);checks++;};
 const d=w.document,el=id=>d.getElementById(id),wait=async f=>{for(let i=0;i<250;i++){if(f())return;await new Promise(r=>w.setTimeout(r,4));}throw Error('Attente dépassée');};
 const click=async text=>{const b=Array.from(d.querySelectorAll('button')).find(x=>x.textContent===text);assert(b,'Bouton absent : '+text);b.click();await new Promise(r=>w.setTimeout(r,0));};
 const submit=form=>form.dispatchEvent(new w.Event('submit',{bubbles:true,cancelable:true}));
 let permissions=new Set(['catalogue.consulter','tiers_payant.consulter','tiers_payant.organisme.gerer','tiers_payant.convention.gerer','tiers_payant.adhesion.consulter','tiers_payant.adhesion.gerer','tiers_payant.priorites.gerer']);
 const org={id:'org1',code:'QA',nom:'Organisme fictif',revision:1,actif:true};const records=[],calls=[],idempotency=new Map();let offline=false,conflict=false;
 w.$=el;w.authState={me:{organisation:{id_organisation:'organisation-qa'},utilisateur:{id_utilisateur:'user-qa'}},site:'site-qa'};w.authHas=p=>permissions.has(p);w.shellState={view:'organismes'};w.shellSync=()=>{};w.authReset=()=>{w.authState.me=null;};w.confirm=()=>true;
 const response=(data,status=200)=>({ok:status<400,status,json:async()=>structuredClone(data)});
 w.authFetch=async(url,options)=>{const body=options.body?JSON.parse(options.body):null;calls.push({url,method:options.method,body});
  if(url.includes('/api/catalogue/')&&url.includes('/produits'))return response({items:[{id_produit:'produit-qa',nom:'Produit cosmétique QA'}]});
  if(url.includes('/api/catalogue/')&&url.includes('/categories'))return response([{id_categorie:'cat-qa',nom:'Cosmétiques QA'}]);
  if(url.includes('/conventions-configurees')){if(conflict)return response({detail:'Révision concurrente'},409);if(idempotency.has(body.cle))return response(idempotency.get(body.cle),201);await new Promise(r=>w.setTimeout(r,8));const row={...body,id:'contract'+records.length,version:1,configuration:{id:'config',definition:body.configuration}};records.push(row);idempotency.set(body.cle,row);if(offline){offline=false;throw Error('Réponse réseau perdue');}return response(row,201);}
  if(url.includes('/conventions/'))return response(records.find(r=>url.endsWith('/'+r.id)));
  if(url.includes('/conventions?'))return response({items:records,total:records.length,page:1,page_size:25});
  if(url.includes('/beneficiaires'))return response({items:[{id:'b1',nom:'Titulaire fictif',actif:true},{id:'b2',nom:'Ayant droit fictif',actif:true}],total:2,page:1,page_size:25});
  if(url.includes('/adhesions?'))return response({items:[{id:'a1',reference_adhesion:'QA-ADH',convention_id:records[0].id,revision:1,statut:'ACTIVE',droits_statut:'CONFIRMES',beneficiaires:[{beneficiaire_id:'b1',beneficiaire_nom:'Titulaire fictif',relation:'TITULAIRE'}]}],total:1});
  if(url.includes('/priorites'))return response({items:[],total:0,page:1,page_size:25});
  if(url.includes('/verifications')){if(options.method==='POST')return response(body,201);return response({items:[],total:0,page:1,page_size:25});}
  if(url.includes('/organismes/'))return response(org);
  if(url.includes('/organismes'))return response({items:[org],total:1,page:1,page_size:25});
  throw Error('Requête inattendue : '+url);
 };
 for(const source of sources){const s=d.createElement('script');s.textContent=source;d.head.append(s);}
 await w.organismesLoad();await click('Consulter '+org.nom);await wait(()=>!el('organismes-detail').hidden);
 await click('Conventions et droits');await wait(()=>!el('conventions-panel').hidden);assert(el('conventions-title').textContent.includes(org.nom),'Organisme mal associé');
 await click('Nouvelle convention');let form=el('conf-editor').querySelector('form');form.elements.convention_code.value='TEST';form.elements.debut.value='2026-10-19';form.elements.fin.value='2026-12-31';
 await click('Charger les produits et catégories');assert(form.querySelector('select[name="produits"]').textContent.includes('Produit cosmétique QA'),'Libellé produit du vrai contrat API perdu');
 let rule=form.querySelector('.conf-rule');rule.querySelector('[name="code"]').value='BASE';rule.querySelector('[name="num"]').value='80';rule.querySelector('[name="den"]').value='100';rule.querySelector('[name="plafond"]').value='2000';rule.querySelector('[name="arrondi"]').value='PLANCHER';
 rule.querySelector('[name="plafond"]').value='9007199254740993';let unsafe=false;try{w.confRuleValue(rule);}catch(e){unsafe=true;}assert(unsafe,'Entier non représentable transmis silencieusement');rule.querySelector('[name="plafond"]').value='2000';
 form.elements.regime_code.value='GENERAL';form.elements.regime_nom.value='Régime général';form.elements.mode_verification.value='EXTERNE';
 await click('Ajouter un renseignement demandé');let field=form.querySelector('.conf-field');field.querySelector('[name="code"]').value='MATRICULE';field.querySelector('[name="libelle"]').value='Matricule';field.querySelector('[name="format"]').value='CHIFFRES';
 await click('Ajouter un justificatif requis');let doc=form.querySelector('.conf-document');doc.querySelector('[name="code"]').value='CARTE';doc.querySelector('[name="libelle"]').value='Carte';
 offline=true;submit(form);submit(form);await wait(()=>el('conventions-message').textContent.includes('perdue'));
 assert(calls.filter(x=>x.method==='POST').length===1,'Double clic non bloqué');assert(records.length===1,'Première écriture simulée manquante');
 submit(form);await wait(()=>el('conventions-message').textContent.includes('enregistrée'));
 const posts=calls.filter(x=>x.url.includes('/conventions-configurees'));assert(posts.length===2&&posts[0].body.cle===posts[1].body.cle,'Clé non conservée au rejeu');assert(records.length===1,'Doublon au rejeu');assert(posts[0].body.extensions_p5b.baremes[0].plafond_ligne_xaf===2000,'Plafond non transmis');assert(posts[0].body.configuration.regime.code==='GENERAL','Régime absent');assert(posts[0].body.configuration.justificatifs[0].code==='CARTE','Justificatif absent');
 await click('Consulter');await wait(()=>el('conf-editor')?.textContent.includes('historique immuable'));assert(el('conf-editor').textContent.includes('Matricule'),'Renseignement historique absent');
 await click('Préparer une nouvelle version');form=el('conf-editor').querySelector('form');assert(form.elements.debut.value==='','Une période a été reconduite silencieusement');form.elements.debut.value='2027-01-01';conflict=true;submit(form);await wait(()=>el('conventions-message').textContent.includes('Rechargez'));assert(form.elements.convention_code.value==='TEST','Saisie perdue au conflit');conflict=false;
 await click('Bénéficiaires et adhésions');await wait(()=>el('conventions-content').textContent.includes('Titulaire fictif'));assert(!calls.some(x=>x.url.includes('fidelite')),'Dépendance fidélité');
 await click('Priorités');await click('Ajouter un organisme');await click('Ajouter un organisme');assert(d.querySelectorAll('.conf-priorite').length===3,'Complémentaires limités à un seul');assert(Array.from(d.querySelectorAll('.conf-priorite select[name="role"]')).every(x=>x.value==='SECONDAIRE'),'Principal imposé');
 await click('Vérifications et justificatifs');form=el('conventions-content').querySelector('form');form.elements.vente.value='sale-qa';submit(form);await wait(()=>d.querySelector('[name="convention_preuve"]'));let sel=d.querySelector('[name="convention_preuve"]');sel.value=records[0].id;sel.dispatchEvent(new w.Event('change'));await wait(()=>d.querySelector('[name="adhesion_preuve"]'));sel=d.querySelector('[name="adhesion_preuve"]');sel.value='a1';sel.dispatchEvent(new w.Event('change'));
 form=Array.from(d.querySelectorAll('#conventions-content form')).find(x=>x.elements.resultat);assert(form,'Formulaire de preuve absent');assert(form.elements.resultat.value==='','Confirmation sélectionnée implicitement');assert(Array.from(form.elements.beneficiaire.options).some(x=>x.textContent.includes('Titulaire fictif')),'Bénéficiaire non identifiable');
 form.elements.beneficiaire.value='b1';form.elements.resultat.value='CONFIRME';form.elements.reference.value='EXTERNE-QA';form.elements.motif.value='Documents contrôlés';form.elements.debut.value='2026-10-19';form.elements.fin.value='2026-10-19';form.querySelector('[data-conf-field="MATRICULE"]').value='123';form.querySelector('[data-conf-doc="CARTE"]').value='CARTE-QA';form.querySelector('[data-conf-checked="CARTE"]').checked=true;submit(form);await wait(()=>el('conventions-message').textContent.includes('EXTERNE-QA'));
 const proof=calls.find(x=>x.url.includes('/ventes/sale-qa/verifications')&&x.method==='POST');assert(proof.body.beneficiaire_id==='b1'&&proof.body.revision_adhesion===1,'Preuve mal rattachée');assert(proof.body.documents[0].verifie===true,'Vérification de pièce perdue');
 permissions.delete('tiers_payant.adhesion.gerer');w.shellSync();assert(form.elements.reference.disabled,'Révocation non reflétée');
 const count=calls.length;submit(form);await new Promise(r=>w.setTimeout(r,10));assert(calls.length===count,'Mutation sans permission');
 w.authState.site='autre-site';w.shellSync();assert(el('conventions-panel').hidden,'Données conservées après changement de site');
 assert(!calls.some(x=>x.url.includes('/finaliser')||x.url.includes('/encaissements')),'Écriture financière inattendue');
 return checks;
}
(async()=>{if(process.argv.includes('--chromium')){const {chromium}=require('playwright');const browser=await chromium.launch({headless:true});try{const page=await browser.newPage();await page.route('http://localhost:8765/**',r=>r.fulfill({status:200,contentType:'text/html',body:html}));await page.goto('http://localhost:8765/');const count=await page.evaluate(async({fn,sources})=>await (0,eval)(`(${fn})`)(window,sources),{fn:scenarios.toString(),sources});console.log(`${count} assertions Chromium (HTTP simulé)`);}finally{await browser.close();}}else{const {JSDOM}=require('jsdom');const dom=new JSDOM(html,{runScripts:'dangerously',url:'https://qa.example.test'});try{console.log(`${await scenarios(dom.window,sources)} assertions DOM (HTTP simulé)`);}finally{dom.window.close();}}})().catch(e=>{console.error(e);process.exitCode=1;});
