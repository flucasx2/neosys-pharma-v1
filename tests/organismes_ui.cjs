// Real application markup/module, simulated HTTP. --chromium uses the same scenarios.
const fs=require('node:fs');
const path=require('node:path');
const root=path.resolve(__dirname,'../src/neosys_pharma/presentation/web');
const html=fs.readFileSync(path.join(root,'index.html'),'utf8').replace(/<script\b[^>]*>[\s\S]*?<\/script>/gi,'');
const source=fs.readFileSync(path.join(root,'organismes.js'),'utf8');
async function scenarios(w,source){
 const d=w.document, el=id=>d.getElementById(id), calls=[], saved=new Map();let checks=0;
 const assert=(condition,message)=>{if(!condition)throw Error(message);checks++;};
 const wait=async fn=>{for(let i=0;i<200;i++){if(fn())return;await new Promise(r=>w.setTimeout(r,5));}throw Error('Attente UI dÃ©passÃ©e');};
 const submit=id=>el(id).dispatchEvent(new w.Event('submit',{bubbles:true,cancelable:true}));
 let permissions=new Set(['tiers_payant.organisme.gerer']), nextId=1, failOnce=false, conflict=false, hold=null;
 let rows=[{id:'initial',code:'INITIAL',nom:'Initial QA',actif:true,revision:1}];
 w.$=el;w.authState={me:{organisation:{id_organisation:'org-qa'},utilisateur:{id_utilisateur:'user-qa'}},site:'site-qa'};
 w.authHas=p=>permissions.has(p);w.shellState={view:'organismes'};w.shellSync=()=>{};w.authReset=()=>{w.authState.me=null;};
 const response=(data,status=200)=>({ok:status>=200&&status<300,status,json:async()=>structuredClone(data)});
 w.authFetch=async(url,options)=>{
  const body=options.body?JSON.parse(options.body):null;calls.push({url,method:options.method,body});
  if(hold&&options.method==='GET')return new Promise(resolve=>{hold.resolve=()=>resolve(response({items:rows,total:rows.length,page:1,page_size:25}));});
  if(options.method==='POST'){
   await new Promise(r=>w.setTimeout(r,10));
   if(saved.has(body.cle))return response(saved.get(body.cle),201);
   const row={id:String(nextId++),code:body.code.toUpperCase(),nom:body.nom,actif:true,revision:1};rows.push(row);saved.set(body.cle,row);
   if(failOnce){failOnce=false;throw Error('Connexion interrompue');}return response(row,201);
  }
  if(options.method==='PUT'){
   if(conflict)return response({detail:'RÃ©vision dÃ©passÃ©e'},409);
   const id=url.split('/').pop();const row=rows.find(x=>x.id===id);Object.assign(row,body,{revision:row.revision+1});return response(row);
  }
  if(url.includes('?'))return response({items:rows,total:rows.length,page:1,page_size:25});
  return response(rows.find(x=>x.id===url.split('/').pop()));
 };
 const script=d.createElement("script");script.textContent=source;d.head.append(script);
 assert(d.querySelector('#admin-subnav [data-view="organismes"]')!==null,'Navigation autonome absente');
 await w.organismesLoad();assert(el('organismes-rows').children.length===1,'Liste initiale');
 el('organismes-new').click();const form=el('organismes-form');
 form.elements.code.value='QA';form.elements.nom.value='Assureur QA';
 submit('organismes-form');submit('organismes-form');
 assert(el('organismes-save').disabled,'Protection double clic absente');
 await wait(()=>!el('organismes-save').disabled);
 assert(calls.filter(x=>x.method==='POST').length===1,'Double crÃ©ation');
 assert(el('organismes-title').textContent==='Assureur QA','RÃ©sultat crÃ©ation non affichÃ©');
 form.elements.nom.value='<img src=x onerror=alert(1)>';form.elements.actif.value='false';submit('organismes-form');
 await wait(()=>!el('organismes-save').disabled);
 assert(el('organismes-title').textContent.includes('<img'),'LibellÃ© perdu');
 assert(!el('organismes-detail').querySelector('img'),'Injection HTML');
 assert(form.elements.actif.value==='false','DÃ©sactivation perdue');
 assert(calls.find(x=>x.method==='PUT').body.revision===1,'RÃ©vision non transmise');
 conflict=true;form.elements.nom.value='Tentative concurrente';submit('organismes-form');
 await wait(()=>!el('organismes-save').disabled);
 assert(el('organismes-message').textContent.includes('Rechargez'),'Conflit non explicite');
 assert(form.elements.nom.value==='Tentative concurrente','Saisie silencieusement Ã©crasÃ©e');
 conflict=false;el('organismes-reload').click();await wait(()=>form.elements.nom.value!=='Tentative concurrente');
 el('organismes-new').click();form.elements.code.value='RETRY';form.elements.nom.value='Reprise QA';failOnce=true;submit('organismes-form');
 await wait(()=>!el('organismes-save').disabled);
 assert(el('organismes-message').textContent==='Connexion interrompue','Erreur rÃ©seau masquÃ©e');
 submit('organismes-form');await wait(()=>!el('organismes-save').disabled);
 const retry=calls.filter(x=>x.method==='POST'&&x.body.code==='RETRY');
 assert(retry.length===2&&retry[0].body.cle===retry[1].body.cle,'ClÃ© de rejeu non conservÃ©e');
 assert(rows.filter(x=>x.code==='RETRY').length===1,'CrÃ©ation doublÃ©e aprÃ¨s panne rÃ©seau');
 permissions=new Set(['tiers_payant.consulter']);w.shellSync();
 assert(el('organismes-save').hidden&&el('organismes-fields').disabled,'RÃ©vocation du droit non reflÃ©tÃ©e immÃ©diatement');
 await w.organismesOpen('initial');
 assert(el('organismes-new').hidden&&el('organismes-save').hidden&&el('organismes-fields').disabled,'Lecture seule contournable');
 const count=calls.length;submit('organismes-form');assert(calls.length===count,'Mutation en lecture seule');
 hold={};const pending=w.organismesLoad();await wait(()=>hold.resolve);
 w.authState.site='autre-site';w.shellSync();hold.resolve();await pending;hold=null;
 assert(el('organismes-rows').children.length===0&&el('organismes-detail').hidden,'RÃ©ponse pÃ©rimÃ¨tre prÃ©cÃ©dent affichÃ©e');
 assert(calls.every(x=>x.url.startsWith('/api/tiers-payants/')),'DÃ©pendance Ã  une fiche client');
 w.authReset();assert(el('organismes-rows').children.length===0,'DonnÃ©es persistantes aprÃ¨s dÃ©connexion');
 return checks;
}
(async()=>{
 if(process.argv.includes('--chromium')){
  const {chromium}=require('playwright');const browser=await chromium.launch({headless:true});
  try {const page=await browser.newPage();await page.route('**/*',route=>route.abort());await page.route("http://localhost:8765/**", route =>
  route.fulfill({
    status: 200,
    contentType: "text/html",
    body: html
  })
);
await page.goto("http://localhost:8765/");
   const result=await page.evaluate(async({fn,source})=>await (0,eval)(`(${fn})`)(window,source),{fn:scenarios.toString(),source});
   console.log(`${result} assertions Chromium rÃ©ussies (HTTP simulÃ©)`);
  }finally{await browser.close();}
 }else{
  const {JSDOM}=require('jsdom');const dom=new JSDOM(html,{runScripts:'dangerously',url:'https://qa.example.test'});
  try{const result=await scenarios(dom.window,source);console.log(`${result} assertions DOM rÃ©ussies (HTTP simulÃ©)`);}finally{dom.window.close();}
 }
})().catch(error=>{console.error(error);process.exitCode=1;});
