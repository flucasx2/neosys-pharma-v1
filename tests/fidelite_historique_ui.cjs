// DOM réel, modale et HTTP simulés. --chromium exécute les mêmes cas dans Chromium.
const fs=require('node:fs'),path=require('node:path');
const web=path.resolve(__dirname,'../src/neosys_pharma/presentation/web');
const html=fs.readFileSync(path.join(web,'index.html'),'utf8').replace(/<script\b[^>]*>[\s\S]*?<\/script>/gi,'');
const stock=fs.readFileSync(path.join(web,'stock.js'),'utf8');
const sources=['stockText','stockField','stockButton'].map(name=>stock.split('\n').find(line=>line.startsWith('function '+name+'('))).concat(['caisse.js','clients.js'].map(file=>fs.readFileSync(path.join(web,file),'utf8')));
async function scenarios(w,sources){
 const d=w.document;let checks=0,modal=null,save=null,modalCount=0;const calls=[],permissions=new Set(['fidelite.consulter','caisse.consulter','caisse.encaisser','client.consulter','vente.consulter']);
 const assert=(v,m)=>{if(!v)throw Error(m);checks++;};
 w.$=id=>d.getElementById(id);w.authReset=()=>{};w.shellSync=()=>{};w.shellState={view:'encaissement'};
 w.authState={me:{organisation:{id_organisation:'org-fictif'},utilisateur:{id_utilisateur:'caissier-fictif'}},site:'site-fictif'};
 w.authHas=p=>permissions.has(p);w.venteMoney=x=>x+' XAF';w.stockDate=x=>x||'—';
 w.fetch=w.authFetch=async()=>{throw Error('Réseau réel interdit');};
 for(const text of sources){const script=d.createElement('script');script.textContent=text;d.head.append(script);}
 w.cashModal=(title,permission,build,submit)=>{modalCount++;modal=d.createElement('form');d.body.append(modal);build(modal);save=submit;return {form:modal};};
 const sale={id:'vente-fictive',revision:1,mode:'SANS_TIERS',etat:'TRANSMISE',emplacement_id:'loc-fictif',client_id:null,confirmations:[],totaux:{ttc:'106500'},lignes:[]};
 const account={id:'compte-fictif',revision:1,client:{nom:'Titulaire fictif'},points:0,dette:0,cartes:[]};
 let info={vente_id:sale.id,revision:1,phase:'AVANT_ENCAISSEMENT',source:'REGLES_ACTUELLES',points_acquis:null,motif:'Aucun point attribué avant encaissement confirmé.',lignes:[{designation:'Produit fictif',eligible:false,code:'NATURE_NON_ADMISE',motif:'Nature du produit différente de COSMETIQUE.'}]};
 let persisted={...sale},delay=null;
 w.cashRequest=async(route,method='GET',body=null)=>{
  calls.push({route,method,body});
  if(route.includes('/fidelite?q='))return {items:[account],total:1};
  if(route.endsWith('/fidelite')){if(delay)await delay;return structuredClone(info);}
  if(route.endsWith('/finaliser')){
   persisted={...sale,revision:2,etat:'ENCAISSEE'};
   // 73 est un résultat serveur fictif choisi pour détecter tout recalcul JS.
   info={vente_id:sale.id,revision:2,phase:'ENCAISSEE',source:'SNAPSHOT_ENCAISSEMENT',points_acquis:73,dette_compensee:0,motif:'Résultat du snapshot serveur.',lignes:[]};
   return {id:'recu-fictif',instantane:{numero_encaissement:'FICTIF',totaux:{ttc:'106500'},fidelite:{points_acquis:73}}};
  }
  if(route==='/ventes/'+sale.id)return structuredClone(persisted);
  throw Error('Route simulée inattendue : '+route);
 };
 w.eval('cashState.sale='+JSON.stringify(sale)+';cashState.session={id:"session-fictive",revision:1};cashState.context={configuration:{ticket_appel:false}};');
 w.$('cash-client-search').value='CARTE-FICTIVE';await w.cashSearch();
 w.$('cash-clients').querySelector('button').click();await Promise.resolve();await Promise.resolve();
 assert(w.eval('cashState.account.id')===account.id,'Titulaire explicite perdu');
 await w.cashRefreshFidelity();w.cashRender();
 assert(w.$('cash-selected-client').textContent.includes('Titulaire fictif'),'Identification du titulaire absente');
 assert(w.$('cash-fidelity-information').textContent.includes('Non éligible'),'Nature refusée non signalée');
 assert(w.$('cash-fidelity-information').textContent.includes('différente de COSMETIQUE'),'Motif serveur absent');
 await w.cashPay();
 assert(modal.textContent.includes('Identification uniquement'),'Sélection du titulaire confondue avec éligibilité');
 assert(modal.textContent.includes('Non éligible'),'Motif absent de la confirmation');
 assert(!modal.textContent.includes('106 points'),'Points calculés dans le navigateur avant paiement');
 info.lignes[0]={designation:'Cosmétique fictif',eligible:true,code:'ELIGIBLE',motif:'Montant client éligible selon le serveur.'};
 await w.cashPay();assert(modal.textContent.includes('Éligible'),'Éligibilité serveur non affichée');
 modal.elements.especes.value='106500';modal.elements.confirme.checked=true;
 await save({especes:'106500'},{cle:'idempotence-fictive'},{form:modal});w.cashRender();
 const sent=calls.find(c=>c.method==='POST').body;
 assert(sent.compte_id===account.id&&sent.revision_compte===1,'Compte choisi non transmis');
 assert(sent.points_utilises===0,'Usage des points débloqué');
 assert(!Object.hasOwn(sent,'client_id'),'Client de préparation modifié implicitement');
 assert(sent.reglements[0].montant==='106500','Montant modifié par la présentation');
 assert(w.$('cash-receipt-summary').textContent.includes('Points acquis 73'),'Points du résultat serveur remplacés par un calcul local');
 assert(w.$('cash-fidelity-information').textContent.includes('effectivement acquis : 73'),'Résultat fidélité non distingué du précontrôle');
 assert(calls.filter(c=>c.method==='POST').length===1,'Lecture fidélité provoquant une écriture');
 // Un contexte modifié pendant la lecture ne doit pas ouvrir une confirmation obsolète.
 w.eval('cashState.sale='+JSON.stringify(sale)+';cashState.receipt=null;');
 info={...info,revision:1};let release;delay=new Promise(resolve=>{release=resolve;});
 const countBefore=modalCount;const stale=w.cashPay();await w.cashPay();assert(modalCount===countBefore,'Double clic ouvrant plusieurs confirmations pendant la lecture');w.eval('cashState.epoch++');release();
 let refused=false;try{await stale;}catch(e){refused=e.message.includes('Contexte modifié');}delay=null;
 assert(refused,'Confirmation obsolète ouverte après changement de contexte');
 // Les messages respectent les permissions, indépendamment du compte déjà en cache.
 permissions.delete('fidelite.consulter');await w.cashRefreshFidelity();w.cashRender();
 assert(w.$('cash-fidelity-information').textContent==='','Diagnostic exposé sans permission fidélité');
 permissions.add('fidelite.consulter');
 let historyCalls=0;w.clientsRequest=async()=>{historyCalls++;return {total:2,items:[
  {...sale,id:'vente-carte-seule',origines_rattachement:['FIDELITE_CAISSE']},
  {...sale,id:'vente-double-lien',origines_rattachement:['PREPARATION','FIDELITE_CAISSE']}
 ]};};
 await w.clientsLoadHistory({id:'client-fictif'});
 assert(w.$('clients-history').querySelectorAll('tr').length===2,'Lignes du résultat serveur perdues ou multipliées');
 assert(w.$('clients-history').textContent.includes('Titulaire fidélité à la caisse'),'Origine fidélité non affichée');
 assert(w.$('clients-history').textContent.includes('Client à la préparation'),'Origine préparation non affichée');
 assert(!w.$('clients-history').textContent.includes('Reçu FICTIF'),'Reçu fabriqué depuis la vente');
 permissions.delete('vente.consulter');await w.clientsLoadHistory({id:'client-fictif'});
 assert(historyCalls===1,'Appel historique effectué sans droit vente');
 assert(w.$('clients-history').textContent.includes('non autorisé'),'Refus historique non affiché');
 return checks;
}
(async()=>{
 if(process.argv.includes('--chromium')){
  const {chromium}=require('playwright');const browser=await chromium.launch();
  try{const page=await browser.newPage();const errors=[];page.on('pageerror',e=>errors.push(String(e)));
   await page.route('http://localhost:8765/**',r=>r.fulfill({status:200,contentType:'text/html',body:html}));
   await page.goto('http://localhost:8765/');
   const count=await page.evaluate(async({fn,sources})=>(0,eval)(`(${fn})`)(window,sources),{fn:scenarios.toString(),sources});
   if(errors.length)throw Error(errors.join('\n'));console.log(`${count} assertions Chromium, HTTP et modale simulés`);
  }finally{await browser.close();}
 }else{
  const {JSDOM}=require('jsdom');const dom=new JSDOM(html,{runScripts:'dangerously',url:'https://qa.example.test'});
  try{console.log(`${await scenarios(dom.window,sources)} assertions DOM, HTTP et modale simulés`);}finally{dom.window.close();}
 }
})().catch(e=>{console.error(e);process.exitCode=1;});
