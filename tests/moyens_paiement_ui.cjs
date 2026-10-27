// Modules applicatifs et HTML réels ; transport HTTP et hôte de modale simulés.
const fs=require('node:fs'),path=require('node:path');
const web=path.resolve(__dirname,'../src/neosys_pharma/presentation/web');
const html=fs.readFileSync(path.join(web,'index.html'),'utf8').replace(/<script\b[^>]*>[\s\S]*?<\/script>/gi,'');
const stock=fs.readFileSync(path.join(web,'stock.js'),'utf8');
const sources=['stockText','stockField'].map(name=>stock.split('\n').find(l=>l.startsWith('function '+name+'('))).concat(['caisse.js','regularisation.js','encaissement_groupe.js'].map(f=>fs.readFileSync(path.join(web,f),'utf8')));
async function scenario(w,sources){
 const d=w.document;let checks=0,entry,save,calls=[];const assert=(v,msg)=>{if(!v)throw Error(msg);checks++;};
 w.$=id=>d.getElementById(id);w.authReset=()=>{};w.shellSync=()=>{};w.authHas=()=>true;w.authState={me:null};w.shellState={view:'test'};w.venteMoney=x=>x+' XAF';
 function load(source){const script=d.createElement('script');script.textContent=source;d.head.append(script);}sources.forEach(load);
 const config={modes:['ESPECES','MOBILE_MONEY'],moyens:[{id:'air',mode:'MOBILE_MONEY',libelle:'Airtel Money',actif:true},{id:'moov',mode:'MOBILE_MONEY',libelle:'Moov Money',actif:true},{id:'old',mode:'MOBILE_MONEY',libelle:'Ancien fournisseur',actif:false}]};
 const choices=w.cashPaymentChoices(config,true);assert(choices.length===3,'Fournisseur inactif ou mobile générique proposé');assert(choices.map(c=>c.key).includes('MOBILE_MONEY:air')&&choices.map(c=>c.key).includes('MOBILE_MONEY:moov'),'Fournisseurs fusionnés');
 function modal(title,p,build,saver){const source=d.createElement('form'),init=build(source);entry={form:source.cloneNode(true),submit:d.createElement('button')};d.body.append(entry.form);if(init)init(entry);save=saver;}
 w.cashModal=modal;w.financeModal=modal;w.cashRequest=async(route,method,body)=>{calls.push({route,method,body});return {};};
 w.eval('cashState.sale={id:"sale",revision:2,totaux:{ttc:500},confirmations:[]};cashState.session={id:"session",revision:1};cashState.context={configuration:'+JSON.stringify(config)+'};');
 w.cashConfirm();entry.form.elements.mode.value='MOBILE_MONEY:moov';entry.form.elements.montant.value='100';entry.form.elements.reference.value='REF';entry.form.elements.preuve.value='Ticket';await save(Object.fromEntries(new w.FormData(entry.form)),{cle:'test'});
 assert(calls[0].body.mode==='MOBILE_MONEY'&&calls[0].body.moyen_id==='moov','Identité fournisseur non transmise');
 w.eval('cashGroupState.draft={dossier:{id:"group",etat:"BROUILLON",session_id:"session"},ventes:[],reglements:[],totaux:{du_xaf:500}};cashGroupState.payments=[{mode:"MOBILE_MONEY",moyen_id:"air",montant:"100",rendu:"0",confirmation_id:"cf-air"}];cashGroupState.saleDetails.set("sale",{confirmations:[{id:"cf-air",mode:"MOBILE_MONEY",moyen_id:"air",reference:"AIR",montant:100},{id:"cf-moov",mode:"MOBILE_MONEY",moyen_id:"moov",reference:"MOOV",montant:100}]});');
 w.cgRenderPayments();const choice=d.querySelector('[aria-label="Mode règlement 1"]'),confirmation=d.querySelector('[aria-label="Confirmation règlement 1"]');
 assert(choice.value==='MOBILE_MONEY:air','Choix fournisseur groupé perdu');assert([...confirmation.options].some(o=>o.value==='cf-air')&&![...confirmation.options].some(o=>o.value==='cf-moov'),'Confirmation d’un autre fournisseur proposée');
 const session=d.getElementById('finance-session');session.add(new w.Option('Session','session'));session.value='session';
 w.eval('financeState.context={sessions:[{id:"session",revision:1}],...'+JSON.stringify(config)+'}');
 w.financeRequest=async(route,method,body)=>{if(method){calls.push({route,method,body});return {};}
 return {montant:'100',remplace_id:'demande-annulee',disponible_par_moyen:[{mode:'MOBILE_MONEY',moyen_id:'air',libelle:'Airtel Money',montant:'100'},{mode:'MOBILE_MONEY',moyen_id:'moov',libelle:'Moov Money',montant:'100'}]};};
 await w.financeRefund({id:'retour'});assert(entry.form.elements.montant_0&&entry.form.elements.montant_1,'Deux origines de même famille fusionnées');
 entry.form.elements.justification.value='Restitution';await save(Object.fromEntries(new w.FormData(entry.form)),{cle:'refund'});
 assert(calls.at(-1).body.reglements[0].moyen_origine_id==='air'&&calls.at(-1).body.reglements[0].moyen_id==='air','Origine du remboursement perdue');
 assert(calls.at(-1).body.remplace_id==='demande-annulee','Lien explicite de remplacement perdu');
 assert(entry.form.elements.mode_0&&entry.form.elements.mode_1,'Contrôles de fournisseurs non indépendants');
 w.financeRequest=async()=>({montant:'100',disponible_par_moyen:[{mode:'ESPECES',moyen_id:null,libelle:'ESPECES',montant:'100'},{mode:'CARTE',moyen_id:null,libelle:'CARTE',montant:'100'}]});
 w.eval('financeState.context.modes=["ESPECES","CARTE"];financeState.context.moyens=[]');
 await w.financeRefund({id:'legacy'});assert(entry.form.elements.montant_ESPECES&&entry.form.elements.mode_CARTE.value==='CARTE','Sélecteurs Chromium historiques modifiés');
 return checks;
}
(async()=>{if(process.argv.includes('--chromium')){const {chromium}=require('playwright');const b=await chromium.launch({headless:true});try{const page=await b.newPage();await page.route('http://localhost:8765/**',r=>r.fulfill({contentType:'text/html',body:html}));await page.goto('http://localhost:8765/');console.log(await page.evaluate(async({sources,fn})=>(0,eval)(`(${fn})`)(window,sources),{sources,fn:scenario.toString()}),'assertions Chromium, HTTP simulé');}finally{await b.close();}}else{const {JSDOM}=require('jsdom');const dom=new JSDOM(html,{runScripts:'dangerously',url:'https://qa.example.test'});try{console.log(await scenario(dom.window,sources),'assertions DOM fournisseurs, HTTP simulé');}finally{dom.window.close();}}})().catch(e=>{console.error(e);process.exitCode=1;});
