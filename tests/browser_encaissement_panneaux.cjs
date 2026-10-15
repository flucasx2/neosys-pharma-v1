/* Chromium ciblé : fichiers UI réels, HTTP simulé, données entièrement fictives. */
const fs=require('fs'),path=require('path'),assert=require('node:assert/strict');
const {chromium}=require('playwright');
const root=path.join(__dirname,'../src/neosys_pharma/presentation/web/');
const output=process.env.CASH_CAPTURE_DIR||path.join(__dirname,'../qa/encaissement-panneaux');
const stock=fs.readFileSync(root+'stock.js','utf8').split('\n').filter(x=>/^function stock(Text|Field|Button)\(/.test(x)).join('\n');
const bootstrap=`const $=id=>document.getElementById(id);const authState={site:'site-fiction',me:{organisation:{id_organisation:'org-fiction'},utilisateur:{id_utilisateur:'user-fiction'}}};const shellState={view:'encaissement'};let authReset=()=>{},shellSync=()=>{},rights=['caisse.consulter','caisse.encaisser','caisse.paiement.confirmer','caisse.session.gerer','fidelite.consulter'];function authHas(p){return rights.includes(p);}function stockDate(x){return x?new Date(x).toLocaleDateString('fr-FR'):'—';}function venteMoney(x){return Number(x).toLocaleString('fr-FR')+' FCFA';}window.authFetch=(url,opt={})=>fetch(url,{...opt,headers:{'Content-Type':'application/json'}});`;
(async()=>{
 fs.mkdirSync(output,{recursive:true});const browser=await chromium.launch({headless:true,...(process.env.CHROMIUM_EXECUTABLE?{executablePath:process.env.CHROMIUM_EXECUTABLE,args:['--no-sandbox','--disable-dev-shm-usage','--disable-gpu']}:{} )});
 try{
 const page=await browser.newPage({viewport:{width:1600,height:1100}}),errors=[];page.on('pageerror',e=>errors.push(String(e)));let posts=[];
 const session={id:'session-fiction-001',revision:1,caisse_id:'caisse-fiction',etat:'OUVERTE',caissier_id:'user-fiction',ouvert_le:'2026-10-13T09:00:00Z',especes_attendues:'1000'};
 let sale={id:'c6badb8c-fiction-001',revision:2,etat:'TRANSMISE',numero_appel:'0003',emplacement_id:'loc-fiction',totaux:{ttc:'800'},lignes:[{designation:'SOLUTION HYDRATANTE FICTIVE — RECETTE',conditionnement:'FLACON 100 ML',quantite:1,montants_appliques:{ttc:'800'}}],confirmations:[{id:'confirmation-fiction',mode:'CARTE',montant:'300',reference:'TERMINAL-FICTIF-01'}]};let receipt=null;
 await page.route('http://localhost:8123/**',async route=>{
 const url=route.request().url();let data;
 if(url==='http://localhost:8123/')return route.fulfill({contentType:'text/html',body:fs.readFileSync(root+'index.html','utf8').replace(/<script[\s\S]*?<\/script>/g,'').replace(/<link[^>]*>/g,'')});
 if(route.request().method()==='POST'){posts.push(JSON.parse(route.request().postData()));sale={...sale,etat:'ENCAISSEE',revision:3};receipt={id:'receipt-fiction',vente_id:sale.id,total_xaf:'800',instantane:{numero_encaissement:'0001',fidelite:{points_acquis:0}}};data=receipt;}
 else if(url.endsWith('/contexte'))data={caisses:[{id:'caisse-fiction',nom:'CAISSE RECETTE'}],emplacements:[{id:'loc-fiction',nom:'COMPTOIR RECETTE'}],categories:[],configuration:{modes:['ESPECES','CARTE'],ticket_appel:false}};
 else if(url.includes('/sessions?'))data={items:[session],total:1};else if(url.includes('/attente?'))data={items:sale.etat==='TRANSMISE'?[{...sale,net_ttc:'800'},{id:'fixture-002',numero_appel:'0004',net_ttc:'1250'}]:[],total:sale.etat==='TRANSMISE'?2:0};else if(url.includes('/recus?'))data={items:receipt?[receipt]:[],total:receipt?1:0};else if(url.includes('/ventes/'))data=sale;else data={items:[],total:0};
 await route.fulfill({contentType:'application/json',body:JSON.stringify(data)});
 });
 await page.goto('http://localhost:8123/');await page.addStyleTag({content:fs.readFileSync(root+'style.css','utf8')});
 await page.addScriptTag({content:bootstrap+stock+'\n'+['creation_dialogs.js','comptoir.js','caisse.js'].map(f=>fs.readFileSync(root+f,'utf8')).join('\n')});
 await page.evaluate(()=>{document.querySelector('#login-panel').hidden=true;document.querySelector('#app-shell').hidden=false;document.querySelector('#administration').hidden=false;document.querySelector('#security-operation').disabled=false;document.querySelector('#security-operation').hidden=false;document.querySelector('#cash-panel').hidden=false;document.querySelector('#module-title').textContent='Encaissement & Fidélité';document.querySelector('#nav-encaissement').hidden=false;document.querySelector('#nav-encaissement').classList.add('active');for(const [id,label]of[['organisations','PHARMACIE FICTIVE — RECETTE'],['sites','SITE FICTIF'],['equipement-emplacement','COMPTOIR RECETTE']]){const e=document.getElementById(id);e.replaceChildren(new Option(label,'fiction'));e.disabled=false;}return cashLoad();});
 await page.locator('.cash-session-tools').evaluate(e=>e.open=true);await page.getByRole('button',{name:'Utiliser cette session',exact:true}).click();await page.locator('.cash-session-tools').evaluate(e=>e.open=false);
 await page.locator('#cash-waiting tr').first().getByRole('button').click();
 await page.locator('[name=settlement_cash]').fill('500');await page.locator('[name=settlement_mode]').selectOption('multiple');await page.locator('[name=settlement_confirmation-fiction]').check();
 assert.match(await page.locator('#cash-payment-summary').innerText(),/Montant réparti : 800/);assert.equal(posts.length,0);
 await page.evaluate(()=>document.activeElement?.blur());await page.screenshot({path:path.join(output,'encaissement-deux-panneaux.png'),fullPage:true});
 await page.keyboard.press('Alt+Shift+Digit0');await page.locator('dialog[open]').waitFor({state:'visible'});assert.equal(await page.locator('dialog[open]').count(),1);assert.equal(await page.locator('dialog[open] [name=especes]').inputValue(),'500');await page.keyboard.press('Escape');assert.equal(await page.locator('dialog[open]').count(),0);assert.equal(posts.length,0);
 await page.locator('#cash-queue-filters [name=q]').fill('SOLUTION');await page.locator('#cash-queue-filters button[type=submit]').click();await page.waitForTimeout(100);assert.equal(await page.locator('#cash-queue-filters [name=q]').inputValue(),'SOLUTION');assert.equal(await page.locator('[name=settlement_cash]').inputValue(),'500');
 await page.keyboard.press('Alt+Shift+Digit0');await page.locator('dialog[open]').waitFor({state:'visible'});await page.locator('dialog[open] [name=confirme]').check();await page.locator('dialog[open]').getByRole('button',{name:'Enregistrer',exact:true}).click();await page.locator('#cash-receipt').waitFor({state:'visible'});assert.equal(posts.length,1);assert.equal(posts[0].reglements.length,2);assert.equal(await page.locator('.cash-pay-primary').count(),0);assert.equal(await page.locator('#cash-payment').isVisible(),false);
 await page.evaluate(()=>document.activeElement?.blur());await page.screenshot({path:path.join(output,'encaissement-confirme-recu.png'),fullPage:true});
 await page.keyboard.press('Alt+Shift+Digit0');assert.equal(posts.length,1);assert.equal(await page.locator('dialog[open]').count(),0);
 await page.setViewportSize({width:800,height:1100});await page.evaluate(()=>document.activeElement?.blur());await page.screenshot({path:path.join(output,'encaissement-responsive.png'),fullPage:true});assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>window.innerWidth),false);
 assert.deepEqual(errors,[]);console.log('Chromium '+browser.version()+' : sélection, session, mixte, confirmation clavier, annulation, filtres, reçu, non-double paiement, responsive OK (HTTP simulé).');
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exit(1);});
