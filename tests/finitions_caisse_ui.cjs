// Formulaires applicatifs réels ; transport HTTP et hôte des modales simulés.
const fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict');
const {JSDOM}=require('jsdom');
const web=path.resolve(__dirname,'../src/neosys_pharma/presentation/web');
const html=fs.readFileSync(path.join(web,'index.html'),'utf8').replace(/<script\b[^>]*>[\s\S]*?<\/script>/gi,'');
const dom=new JSDOM(html,{runScripts:'dangerously',url:'https://qa.example.test'}),w=dom.window,d=w.document;
let checks=0,entry,saver,calls=[];function check(v,msg){assert.ok(v,msg);checks++;}
function load(file){const script=d.createElement('script');script.textContent=fs.readFileSync(path.join(web,file),'utf8');d.head.append(script);}
w.$=id=>d.getElementById(id);w.authReset=()=>{};w.shellSync=()=>{};w.authHas=()=>true;w.authState={me:null};w.shellState={view:'test'};w.venteMoney=x=>x+' XAF';
// Réutiliser les constructeurs de champs du module stock, sans initialiser ses requêtes.
const stock=fs.readFileSync(path.join(web,'stock.js'),'utf8');
for(const name of ['stockText','stockField'])w.eval(stock.split('\n').find(line=>line.startsWith('function '+name+'(')));
function modal(title,permission,build,save){const source=d.createElement('form'),init=build(source);const form=source.cloneNode(true);d.body.append(form);entry={form};if(init)init(entry);saver=save;return entry;}
function values(){return Object.fromEntries(new w.FormData(entry.form));}
load('caisse.js');load('clients.js');w.cashModal=modal;w.clientsModal=modal;
w.cashRequest=async(route,method,body)=>{calls.push({route,method,body});return {id:'account',revision:2,cartes:[]};};w.clientsRequest=w.cashRequest;
(async()=>{try{
 w.eval('cashState.account={id:"account",revision:1,cartes:[]};clientsState.loyalty={id:"account",revision:1}');
 for(const open of [()=>w.cashCard(),()=>w.clientsCard({id:'client'})]){
  open();check(entry.form.elements.code.required,'Carte physique sans identifiant obligatoire');
  entry.form.elements.type.value='VIRTUELLE';entry.form.elements.type.dispatchEvent(new w.Event('change'));
  check(entry.form.elements.code.disabled&&!entry.form.elements.code.required,'Initialisation après clonage incorrecte');
  await saver(values(),{cle:'key'},entry);check(!Object.hasOwn(calls.at(-1).body,'code'),'Code virtuel envoyé par le navigateur');
 }
 w.eval('cashState.sale={id:"sale",revision:1,totaux:{ttc:1000},confirmations:[]};cashState.session={id:"session",revision:1};cashState.account=null');
 w.cashPay();entry.form.elements.especes.value='1200';entry.form.elements.confirme.checked=true;
 check(entry.form.checkValidity(),'Le formulaire refuse les espèces supérieures au montant dû');
 await saver(values(),{cle:'pay'},entry);
 check(calls.find(c=>c.route==='/ventes/sale/finaliser').body.reglements[0].montant==='1200','Montant réellement remis perdu');
 w.eval('cashState.context={caisses:[{id:"till",nom:"Nom original"}]}');w.cashRename();
 check(entry.form.elements.nom.value==='Nom original','Nom courant absent après clonage');entry.form.elements.nom.value='Nouveau nom';
 await saver(values(),{cle:'rename'},entry);
 check(calls.at(-1).route==='/caisses/till/libelle'&&calls.at(-1).body.nom_attendu==='Nom original','Conflit de nom non contrôlé');
 console.log(checks,'assertions DOM formulaires, HTTP et hôte modale simulés');
 }finally{dom.window.close();}})().catch(error=>{console.error(error);process.exitCode=1;});
