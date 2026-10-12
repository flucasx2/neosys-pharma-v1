const fs=require('fs'),assert=require('node:assert/strict'),{JSDOM}=require('jsdom');
const root=require('node:path').join(__dirname,'../src/neosys_pharma/presentation/web/');
const dom=new JSDOM(fs.readFileSync(root+'index.html','utf8'),{url:'http://localhost:8000',runScripts:'outside-only'}),w=dom.window;
w.HTMLDialogElement.prototype.showModal=function(){this.setAttribute('open','');};w.HTMLDialogElement.prototype.close=function(){this.removeAttribute('open');};w.HTMLElement.prototype.scrollIntoView=function(){};
Object.defineProperty(w,'crypto',{value:require('node:crypto').webcrypto});
const stock=fs.readFileSync(root+'stock.js','utf8').split('\n').filter(x=>/^function stock(Text|Field|Button)\(/.test(x)).join('\n');
const bootstrap=`const $=id=>document.getElementById(id); const authState={site:'site',me:{organisation:{id_organisation:'org'},utilisateur:{id_utilisateur:'user'}}};const shellState={view:'vente'};let authReset=()=>{},shellSync=()=>{};function authHas(p){return p==='vente.consulter';}function stockDate(x){return x||'—';}function authHeaders(){return{};} `;
const test=`
(async()=>{
 let calls=[];const v={id:'00000000-0000-0000-0000-000000000001',revision:2,etat:'TRANSMISE',mode:'SANS_TIERS',emplacement_id:'loc',numero_appel:'0001',periode_appel_id:'period-123',ticket_appel_active:false,lignes:[],remises:[],totaux:{ht:'0',tva:'0',ttc:'0',remise_ligne:'0',remise_globale:'0'}};
 window.authFetch=async(path,options={})=>{calls.push([path,options.method]);const data=path.endsWith('/contextes')?{emplacements:[{id:'loc',nom:'COMPTOIR',caisses:[]}]}:path.includes('/documents')?{id:'document',revision_vente:2}:path.includes('?page=')?{items:[v],total:1}:v;return{ok:true,json:async()=>data};};
 await venteLoad();const form=document.querySelector('#p4-filters form');form.elements.q.value='MÉDICAMENT';form.dispatchEvent(new Event('submit',{bubbles:true,cancelable:true}));await new Promise(r=>setTimeout(r,10));
 if(!calls.some(([p])=>p.includes('q=M%C3%89DICAMENT')))throw Error('Recherche non transmise');
 await venteLoad();if(form.elements.q.value!=='MÉDICAMENT')throw Error('Recherche perdue');
 venteState.current=v;venteDocumentEdit();const entry=[...creationDialogs.entries.values()].at(-1);if(!entry.dialog.open)throw Error('Modale PDF fermée');entry.form.dispatchEvent(new Event('submit',{bubbles:true,cancelable:true}));await new Promise(r=>setTimeout(r,20));
 if(entry.dialog.open||!entry.error.hidden)throw Error('Edition PDF non confirmée : '+entry.error.textContent);
 if(!calls.some(([p,m])=>p.includes('/documents')&&m==='POST'))throw Error('Edition non envoyée');
 window.result={ok:true,calls:calls.length};
})().catch(e=>{window.result={ok:false,error:e.stack};});`;
w.eval(bootstrap+stock+'\n'+fs.readFileSync(root+'creation_dialogs.js','utf8')+'\n'+fs.readFileSync(root+'comptoir.js','utf8')+'\n'+fs.readFileSync(root+'vente.js','utf8')+'\n'+test);
setTimeout(()=>{assert.equal(w.result?.ok,true,JSON.stringify(w.result));console.log('DOM : recherche serveur, conservation des filtres, modale PDF et fermeture après succès OK');w.close();},100);
