const fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict');
const {JSDOM}=require('jsdom');
const web=path.resolve(__dirname,'../src/neosys_pharma/presentation/web');
const dom=new JSDOM(fs.readFileSync(path.join(web,'index.html'),'utf8').replace(/<script\b[^>]*>[\s\S]*?<\/script>/gi,''),{runScripts:'dangerously',url:'https://qa.example.test'});
const w=dom.window,d=w.document;let checks=0,calls=[];
function check(value,message){assert.ok(value,message);checks++;}
function load(s){const script=d.createElement('script');script.textContent=s;d.head.append(script);}
w.$=id=>d.getElementById(id);w.authReset=()=>{};w.shellSync=()=>{};w.authHas=()=>true;w.authState={me:{organisation:{id_organisation:'org'}}};w.shellState={view:'test'};
w.HTMLDialogElement.prototype.showModal=function(){this.open=true;};w.HTMLDialogElement.prototype.close=function(){this.open=false;};w.HTMLElement.prototype.scrollIntoView=function(){};
const stock=fs.readFileSync(path.join(web,'stock.js'),'utf8');
for(const name of ['stockText','stockField','stockButton'])load(stock.split('\n').find(l=>l.startsWith('function '+name+'(')));
load(fs.readFileSync(path.join(web,'creation_dialogs.js'),'utf8'));load(fs.readFileSync(path.join(web,'caisse.js'),'utf8'));
let config={modes:['ESPECES'],moyens:[],revision:0,ticket_appel:false};
w.eval('cashState.context={configuration:'+JSON.stringify(config)+'}');
function entry(){return w.eval('[...creationDialogs.entries.values()].filter(e=>e.dialog.open).at(-1)');}
function close(){const e=entry();if(e)w.creationDialogClose(e,true);}
function open(fn){close();fn();return entry();}
async function save(e){return e.options.save(Object.fromEntries(new w.FormData(e.form)));}
w.authFetch=async(url,options)=>{calls.push({url,...options,body:JSON.parse(options.body||'null')});return {ok:true,json:async()=>({revision:1})};};
(async()=>{try{
 let e=open(w.cashProviders);check(e.form.textContent.includes('ESPÈCES · Active'),'Espèces initiales');check(e.form.querySelectorAll('tbody tr').length===0,'Aucune création implicite');check(e.form.textContent.includes('Nouveau moyen de paiement'),'Bouton création');
 for(const [code,name] of [['AIRTEL_MONEY','AIRTEL MONEY'],['MOOV_MONEY','MOOV MONEY']]){e=open(()=>w.cashEditProvider(null));e.form.elements.code.value=code;e.form.elements.libelle.value=name;e.form.elements.mode.value='MOBILE_MONEY';await save(e);const call=calls.at(-1);check(call.url.endsWith('/org/moyens')&&call.method==='POST','Endpoint organisation');check(call.body.code===code&&call.body.libelle===name&&call.body.mode==='MOBILE_MONEY'&&call.body.actif,'Création explicite');}
 e=open(w.cashConfig);e.form.elements.ESPECES.checked=false;const before=calls.length;await assert.rejects(()=>save(e),/Confirmez/);check(calls.length===before,'Désactivation non confirmée sans requête');e.form.elements.desactivation_confirmee.checked=true;await save(e);check(calls.at(-1).body.modes.length===0&&calls.at(-1).body.revision===0,'Vide explicite et révision');
 config={modes:[],moyens:[{id:'air',code:'AIRTEL_MONEY',libelle:'AIRTEL MONEY GABON',mode:'MOBILE_MONEY',actif:true,revision:4}],revision:1,ticket_appel:false};w.eval('cashState.context.configuration='+JSON.stringify(config));
 e=open(w.cashProviders);check(e.form.textContent.includes('Aucun moyen de paiement actif'),'État indisponible');check(e.form.textContent.includes('famille inactive'),'Famille inactive signalée');check(e.form.querySelectorAll('tbody tr').length===1,'Liste des moyens');
 check(e.form.querySelector('table').classList.contains('cash-payment-admin-table'),'Styles limités au tableau B02');
 check([...e.form.querySelectorAll('thead th')].map(x=>x.textContent).join('|')==='Nom|Code|Famille|État|Actions','Colonnes alignées avec leurs en-têtes');
 e=open(()=>w.cashEditProvider(config.moyens[0]));check(e.form.elements.libelle.value==='AIRTEL MONEY GABON','Nom serveur prérempli après ouverture réelle de modale');
 e.form.elements.libelle.value='Nom temporaire';e.form.reset();check(e.form.elements.libelle.value==='AIRTEL MONEY GABON','Nom préservé après reset');
 for(const invalid of ['', '   ', '\t  ']){e.form.elements.libelle.value=invalid;const count=calls.length;await assert.rejects(()=>save(e),/nom.*obligatoire/);check(calls.length===count,'Nom vide refusé sans requête');}
 e.form.elements.libelle.value='AIRTEL MONEY GABON';await save(e);check(calls.at(-1).body.libelle==='AIRTEL MONEY GABON','Nom inchangé transmis au serveur');
 e.form.elements.actif.checked=false;await assert.rejects(()=>save(e),/Confirmez/);e.form.elements.desactivation_confirmee.checked=true;await save(e);check(calls.at(-1).method==='PUT'&&calls.at(-1).body.revision===4&&!calls.at(-1).body.actif,'Modification révision et désactivation');
 e=open(()=>w.cashEditProvider({...config.moyens[0],actif:false}));e.form.elements.actif.checked=true;await save(e);check(calls.at(-1).body.actif,'Réactivation');
 e=open(w.cashConfig);e.form.elements.MOBILE_MONEY.checked=true;await save(e);check(calls.at(-1).body.modes.join(',')==='MOBILE_MONEY','Activation famille');
 config.modes=['MOBILE_MONEY'];config.moyens[0].actif=false;
 w.authHas=p=>p==='caisse.parametrer';w.shellState.view='encaissement';
 w.authFetch=async(url,options)=>{check(options.method==='GET'&&url.endsWith('/contexte'),'Actualisation sans mutation');return {ok:true,json:async()=>({configuration:config})};};
 await w.cashLoad(true);e=open(w.cashProviders);check(e.form.textContent.includes('MOBILE MONEY · Active')&&e.form.textContent.includes('Aucun moyen de paiement actif'),'Cohérence après relecture serveur');
 config.modes=[];config.moyens=[];await w.cashLoad(true);e=open(w.cashProviders);check(e.form.textContent.includes('ESPÈCES · Inactive')&&e.form.textContent.includes('Aucun moyen créé'),'Vide conservé après actualisation');
 w.authHas=()=>true;e=open(()=>w.cashEditProvider({id:'air',code:'AIRTEL_MONEY',mode:'MOBILE_MONEY',libelle:'AIRTEL MONEY',actif:false,revision:4}));
 w.authFetch=async()=>({ok:false,status:409,json:async()=>({detail:'Moyen modifié : actualiser.'})});await assert.rejects(()=>save(e),/Moyen modifié : actualiser/);checks++;
 w.authFetch=async()=>({ok:false,status:403,json:async()=>({detail:'Permission refusée.'})});await assert.rejects(()=>save(e),/Permission refusée/);checks++;
 close();w.authHas=p=>!['caisse.parametrer','caisse.consulter'].includes(p);
 w.authFetch=async(url,options)=>{calls.push({url,...options});return {ok:true,json:async()=>({configuration:config})};};
 await w.cashLoad(true);check(![...d.querySelectorAll('#cash-actions button')].some(b=>b.textContent==='Moyens de paiement'),'Action administration absente sans caisse.parametrer');
 const deniedCount=calls.length;w.cashProviders();w.cashConfig();w.cashEditProvider(null);w.cashEditProvider({id:'air',libelle:'AIRTEL',actif:true});
 check(!entry(),'Création, modification et désactivation inaccessibles sans permission');check(calls.length===deniedCount,'Aucune requête de mutation sans permission');
 console.log(checks+' assertions DOM et HTTP simulé B02 réussies');
 }finally{dom.window.close();}})().catch(e=>{console.error(e);process.exitCode=1;});
