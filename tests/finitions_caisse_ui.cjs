// Formulaires applicatifs réels ; transport HTTP et hôte des modales simulés.
const fs=require('node:fs'),path=require('node:path');
const web=path.resolve(__dirname,'../src/neosys_pharma/presentation/web');
const html=fs.readFileSync(path.join(web,'index.html'),'utf8').replace(/<script\b[^>]*>[\s\S]*?<\/script>/gi,'');
const sources=Object.fromEntries(['stock.js','caisse.js','clients.js'].map(file=>[file,fs.readFileSync(path.join(web,file),'utf8')]));
async function scenario(w,sources){
const d=w.document;
let checks=0,entry,saver,calls=[];function check(v,msg){if(!v)throw Error(msg);checks++;}
function load(file){const script=d.createElement('script');script.textContent=sources[file];d.head.append(script);}
w.$=id=>d.getElementById(id);w.authReset=()=>{};w.shellSync=()=>{};w.authHas=()=>true;w.authState={me:null};w.shellState={view:'test'};w.venteMoney=x=>x+' XAF';
// Réutiliser les constructeurs de champs du module stock, sans initialiser ses requêtes.
const stock=sources['stock.js'];
for(const name of ['stockText','stockField'])w.eval(stock.split('\n').find(line=>line.startsWith('function '+name+'(')));
function modal(title,permission,build,save){const source=d.createElement('form'),init=build(source);const form=source.cloneNode(true);d.body.append(form);entry={form};if(init)init(entry);saver=save;return entry;}
function values(){return Object.fromEntries(new w.FormData(entry.form));}
load('caisse.js');load('clients.js');w.cashModal=modal;w.clientsModal=modal;
w.cashRequest=async(route,method,body)=>{calls.push({route,method,body});return {id:'account',revision:2,cartes:[]};};w.clientsRequest=w.cashRequest;
 w.eval('cashState.account={id:"account",revision:1,cartes:[]};clientsState.loyalty={id:"account",revision:1}');
 for(const open of [()=>w.cashCard(),()=>w.clientsCard({id:'client'})]){
  open();check(entry.form.elements.code.required,'Carte physique sans identifiant obligatoire');
  check(!entry.form.elements.code_barres.disabled,'Code-barres physique indisponible');
  entry.form.elements.code.value='VISIBLE-007';entry.form.elements.code_barres.value='SCAN-00007';
  await saver(values(),{cle:'physical'},entry);check(calls.at(-1).body.code==='VISIBLE-007'&&calls.at(-1).body.code_barres==='SCAN-00007','Numéro et code-barres physique fusionnés');
  entry.form.elements.type.value='VIRTUELLE';entry.form.elements.type.dispatchEvent(new w.Event('change'));
  check(entry.form.elements.code.disabled&&!entry.form.elements.code.required,'Initialisation après clonage incorrecte');
  await saver(values(),{cle:'key'},entry);check(!Object.hasOwn(calls.at(-1).body,'code')&&!Object.hasOwn(calls.at(-1).body,'code_barres'),'Identifiant physique envoyé pour une carte virtuelle');check(entry.form.elements.code_barres.disabled,'Code-barres laissé actif pour une carte virtuelle');
 }
 w.eval('cashState.sale={id:"sale",revision:1,totaux:{ttc:1000},confirmations:[]};cashState.session={id:"session",revision:1};cashState.account=null;cashState.context={configuration:{modes:["ESPECES"],moyens:[]}}');
 w.shellState.view="encaissement";await w.cashPay();entry.form.elements.especes.value='1200';entry.form.elements.especes.dispatchEvent(new w.Event('input',{bubbles:true}));
 check(entry.form.querySelector('.cash-financial-summary').textContent==='Solde client à régler : 1000 XAF\nTotal reçu : 1200 XAF\nRendu monnaie : 200 XAF\nNet encaissé : 1000 XAF\nReste à répartir : 0 XAF','Récapitulatif espèces ou rendu incorrect');
 let refused=false;try{await saver(values(),{cle:'unconfirmed'},entry);}catch(_){refused=true;}
 check(refused&&!calls.some(c=>c.route==='/ventes/sale/finaliser'),'Encaissement sans confirmation explicite');
 entry.form.elements.confirme.checked=true;
 check(entry.form.checkValidity(),'Le formulaire refuse les espèces supérieures au montant dû');
 await saver(values(),{cle:'pay'},entry);
 check(calls.find(c=>c.route==='/ventes/sale/finaliser').body.reglements[0].montant==='1200','Montant réellement remis perdu');
 w.eval('cashState.context={caisses:[{id:"till",nom:"Nom original"}]}');w.cashRename();
 check(entry.form.elements.nom.value==='Nom original','Nom courant absent après clonage');entry.form.elements.nom.value='Nouveau nom';
 await saver(values(),{cle:'rename'},entry);
 check(calls.at(-1).route==='/caisses/till/libelle'&&calls.at(-1).body.nom_attendu==='Nom original','Conflit de nom non contrôlé');
 w.cashPrintCard({id:'card',code:'VISIBLE-007',code_barres:'SCAN-00007'});check(entry.form.textContent.includes('SCAN-00007'),'Récapitulatif d’impression absent');
 return checks;
}
(async()=>{if(process.argv.includes('--chromium')){const {chromium}=require('playwright');const browser=await chromium.launch({headless:true});try{const page=await browser.newPage();await page.route('http://localhost:8765/**',r=>r.fulfill({contentType:'text/html',body:html}));await page.goto('http://localhost:8765/');console.log(await page.evaluate(async({sources,fn})=>await(0,eval)(`(${fn})`)(window,sources),{sources,fn:scenario.toString()}),'assertions Chromium, HTTP simulé');}finally{await browser.close();}}else{const {JSDOM}=require('jsdom');const dom=new JSDOM(html,{runScripts:'dangerously',url:'https://qa.example.test'});try{console.log(await scenario(dom.window,sources),'assertions DOM, HTTP simulé');}finally{dom.window.close();}}})().catch(e=>{console.error(e);process.exitCode=1;});
