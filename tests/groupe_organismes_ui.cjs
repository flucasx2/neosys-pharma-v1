// Rendu applicatif réel ; services HTTP simulés. Aucune preuve PostgreSQL.
const fs=require('node:fs'),path=require('node:path');
const web=path.resolve(__dirname,'../src/neosys_pharma/presentation/web');
const html=fs.readFileSync(path.join(web,'index.html'),'utf8').replace(/<script\b[^>]*>[\s\S]*?<\/script>/gi,'');
const source=fs.readFileSync(path.join(web,'encaissement_groupe.js'),'utf8');
async function scenario(w,source){
 const d=w.document;let checks=0;const assert=(v,msg)=>{if(!v)throw Error(msg);checks++;};
 w.$=id=>d.getElementById(id);w.authState={me:{organisation:{id_organisation:'qa'}},site:'site'};w.cashState={session:{id:'session',etat:'OUVERTE'},context:{configuration:{modes:['ESPECES','CARTE']}},key:'qa'};
 w.authHas=()=>true;w.cashLoad=async()=>{};w.authReset=()=>{};w.shellSync=()=>{};w.venteMoney=value=>`${value} XAF`;w.shellState={view:'encaissement'};
 const sale={id:'sale-a',etat:'TRANSMISE',mode:'MUTUELLE',emplacement_id:'loc',totaux:{ttc:2000},prise_en_charge:{part_client_xaf:500,total_organismes_xaf:1500},client:{nom:'Client A'}};
 const cash={id:'sale-b',etat:'TRANSMISE',mode:'SANS_TIERS',emplacement_id:'loc',totaux:{ttc:1000},client:{nom:'Client B'}};
 w.cashRequest=async route=>route.startsWith('/attente')?{items:[{...sale,net_ttc:2000},{...cash,net_ttc:1000}],page:1,page_size:15,total:2}:structuredClone(route.includes('sale-a')?sale:cash);
 w.fetch=async()=>{throw Error('Requête réseau interdite');};
 w.authFetch=async()=>({ok:true,json:async()=>({finalisation_active:false})});
 const script=d.createElement('script');script.textContent=source;d.head.append(script);
 assert(w.cgSaleDue(sale)===500,'Part client incorrecte');assert(w.cgSaleDue(cash)===1000,'Comptant individuel modifié');
 for(const candidate of [{...sale,prise_en_charge:null},{...sale,mode:'CREDIT'}]){let rejected=false;try{w.cgSaleDue(candidate);}catch(_){rejected=true;}assert(rejected,'Vente inadmissible acceptée');}
 // Les totaux de sélection utilisent les montants serveur, sans recalcul des taux.
 w.eval('cashGroupState.selected.set("sale-a", '+JSON.stringify(sale)+');cashGroupState.selected.set("sale-b", '+JSON.stringify(cash)+');');
 assert(w.cgSelectedTotal()===1500,'Total TTC utilisé à la place des parts clients');w.cgRenderSelection();
 assert(d.getElementById('cash-group-selected-total').textContent.includes('1500'),'Total sélection non affiché');
 w.eval('cashGroupState.selected.delete("sale-a")');assert(w.cgSelectedTotal()===1000,'Retrait sans recalcul');
 assert(sale.totaux.ttc===2000&&sale.prise_en_charge.total_organismes_xaf===1500,'Historique financier modifié côté navigateur');
 w.cgReset();assert(w.cgSelectedTotal()===0,'Sélection résiduelle après réinitialisation');
 return checks;
}
(async()=>{if(process.argv.includes('--chromium')){const {chromium}=require('playwright');const browser=await chromium.launch({headless:true});try{const page=await browser.newPage();await page.route('http://localhost:8765/**',r=>r.fulfill({contentType:'text/html',body:html}));await page.goto('http://localhost:8765/');console.log(await page.evaluate(async({source,fn})=>await(0,eval)(`(${fn})`)(window,source),{source,fn:scenario.toString()}),'assertions Chromium, HTTP simulé');}finally{await browser.close();}}else{const {JSDOM}=require('jsdom');const dom=new JSDOM(html,{runScripts:'dangerously',url:'https://qa.example.test'});try{console.log(await scenario(dom.window,source),'assertions DOM, HTTP simulé');}finally{dom.window.close();}}})().catch(e=>{console.error(e);process.exitCode=1;});
