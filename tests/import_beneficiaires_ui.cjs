// Import applicatif, FileReader et DOM réels ; HTTP simulé, aucune création financière.
const fs=require('node:fs'),path=require('node:path'),{JSDOM}=require('jsdom');
const web=path.resolve(__dirname,'../src/neosys_pharma/presentation/web'),html=fs.readFileSync(path.join(web,'index.html'),'utf8').replace(/<script\b[^>]*>[\s\S]*?<\/script>/gi,'');
const dom=new JSDOM(html,{runScripts:'dangerously',url:'https://qa.example.test'}),w=dom.window,d=w.document;
let checks=0,allow=true,bad=false,lose=true,calls=[];const assert=(v,m)=>{if(!v)throw Error(m);checks++;};
const wait=async fn=>{for(let i=0;i<200;i++){if(fn())return;await new Promise(r=>w.setTimeout(r,5));}throw Error('Attente bornée dépassée');};
w.$=id=>d.getElementById(id);w.authHas=()=>allow;w.organismesScope=()=>'scope';w.organismesShow=()=>{};w.organismesState={};w.authReset=()=>{};w.shellSync=()=>{};w.authState={me:{organisation:{id_organisation:'org'}},site:'site'};
const script=d.createElement('script');script.textContent=fs.readFileSync(path.join(web,'conventions.js'),'utf8');d.head.append(script);
w.eval('conventionsState.organisme={id:"payer"};conventionsState.epoch=1');w.confTab=async()=>{};
w.authFetch=async(url,options)=>{const body=JSON.parse(options.body);calls.push({url,body});if(url.endsWith('/previsualiser'))return {ok:true,json:async()=>({empreinte:'a'.repeat(64),total:1,compteurs:{INVALIDE:bad?1:0},confirmation_possible:!bad,lignes:[{numero:2,donnees:{reference_externe:'0001',nom:'Personne fictive'},statut:bad?'INVALIDE':'NOUVEAU',erreurs:bad?['À corriger']:[]}]})};if(lose){lose=false;throw Error('Réponse réseau perdue');}return {ok:true,json:async()=>({crees:['bene'],rattaches:[],deja_importes:[],droits_confirmes:false})};};
w.confImportBeneficiaires(d.getElementById('conventions-content'));
const form=d.querySelector('#conventions-content form'),file=form.elements.fichier,check=d.querySelector('[name="accord_import"]'),button=[...d.querySelectorAll('button')].find(b=>b.textContent==='Confirmer l’import');
let files=[new w.File(['reference_externe;nom\n0001;Personne fictive\n'],'qa.csv',{type:'text/csv'})];Object.defineProperty(file,'files',{get:()=>files});
async function preview(){file.dispatchEvent(new w.Event('change'));form.dispatchEvent(new w.Event('submit',{cancelable:true}));await wait(()=>d.getElementById('conventions-message').textContent.includes('analysée'));}
(async()=>{try{
 assert(button.disabled,'Confirmation autorisée sans prévisualisation');await preview();assert(d.getElementById('conventions-content').textContent.includes('0001'),'Zéros perdus dans le rapport');assert(button.disabled,'Accord opérateur présumé');
 check.checked=true;check.dispatchEvent(new w.Event('change'));assert(!button.disabled,'Prévisualisation valide non confirmable');
 button.click();await wait(()=>d.getElementById('conventions-message').textContent.includes('perdue'));button.click();await wait(()=>d.getElementById('conventions-message').textContent.includes('Liste importée'));
 const attempts=calls.filter(c=>c.url.endsWith('/confirmer'));assert(attempts.length===2&&attempts[0].body.cle===attempts[1].body.cle,'Clé modifiée au rejeu identique');assert(attempts[0].body.confirmer===true&&attempts[0].body.organisme_id==='payer','Import non lié à sa source/confirmation');assert(!Object.hasOwn(attempts[0].body,'droits_statut'),'Confirmation de droits fabriquée côté UI');
 d.getElementById('conventions-message').textContent='';await preview();check.checked=true;check.dispatchEvent(new w.Event('change'));w.eval('conventionsState.epoch++');const count=calls.length;button.click();await new Promise(r=>w.setTimeout(r,5));assert(calls.length===count,'Ancien contexte accepté');
 bad=true;d.getElementById('conventions-message').textContent='';await preview();check.checked=true;check.dispatchEvent(new w.Event('change'));assert(button.disabled,'Ligne invalide autorisée');
 form.elements.feuille.value='Autre';form.elements.feuille.dispatchEvent(new w.Event('input'));assert(button.disabled&&!check.checked,'Modification de source sans invalidation');
 console.log(checks,'assertions DOM import bénéficiaires, HTTP simulé');
 }finally{dom.window.close();}})().catch(e=>{console.error(e);process.exitCode=1;});
