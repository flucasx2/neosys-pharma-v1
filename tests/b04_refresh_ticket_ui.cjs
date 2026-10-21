// Contrôleurs réels, transport et DOM simulés : aucune requête vers la recette.
const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
const web='src/neosys_pharma/presentation/web/';
const source=fs.readFileSync(web+'encaissement_groupe.js','utf8');
let checks=0;function check(value,label){assert.ok(value,label);checks++;}
function load(c,names){for(const name of names){const start=source.indexOf('function '+name+'('),begin=source.slice(start-6,start)==='async '?start-6:start;assert.ok(start>=0,name);const next=/\n(?:async )?function /.exec(source.slice(start+9));vm.runInContext(source.slice(begin,next?start+9+next.index:source.length),c);}}
class Element{constructor(){this.children=[];this.dataset={};this.listeners={};this.value='';}append(n){n.parent=this;this.children.push(n)}replaceChildren(){this.children=[]}querySelectorAll(tag){return this.children.filter(n=>tag==='tr'?n.tag==='tr':tag==='li'?n.tag==='li':false)}setAttribute(){}addEventListener(k,f){this.listeners[k]=f}remove(){this.parent.children=this.parent.children.filter(n=>n!==this)}}
const deferred=()=>{let resolve,reject;const promise=new Promise((a,b)=>{resolve=a;reject=b});return{promise,resolve,reject}};
const tick=()=>new Promise(resolve=>setImmediate(resolve));
function fixture(){
 const nodes={},node=id=>nodes[id]??=new Element(),messages=[],requests=[];
 const state={busy:false,page:1,pageSize:15,salesGeneration:0,mode:'GROUPE',selected:new Map(),saleDetails:new Map(),draft:null};
 const c=vm.createContext({cashGroupState:state,cashState:{epoch:0,session:{id:'session',revision:1}},authState:{me:{organisation:{id_organisation:'org'}},site:'site'},shellState:{view:'encaissement'},cg:node,$:node,document:{createElement:()=>new Element()},localStorage:{getItem:()=>null,removeItem(){}},authHas:()=>true,cgDraftStorageKey:()=>'',cgLoadActivation:async()=>{},cgRenderSelection(){},cgSyncConsultationButtons(){},cgMoney:String,cgMessage(text){messages.push(text)},cashRequest:async path=>{requests.push(path);return{items:[],total:0}},cgBusy:value=>state.busy=value});
 load(c,['cgReadContext','cgLoadSales']);return{c,state,node,messages,requests};
}
(async()=>{
 let {c,state,node}=fixture(),pending=[];
 c.cashRequest=path=>{const d=deferred();pending.push({path,...d});return d.promise};
 const old=c.cgLoadSales();await tick();const fresh=c.cgLoadSales();await tick();
 pending[1].resolve({items:[],total:0});await fresh;pending[0].resolve({items:[{id:'obsolete',net_ttc:1}],total:1});await old;
 check(node('sales').children.length===0,'une réponse ancienne ne remplace pas une liste récente');
 const site=c.cgLoadSales();await tick();c.authState.site='other';pending[2].resolve({items:[{id:'wrongsite'}],total:1});await site;check(node('sales').children.length===0,'changement site invalide la lecture');
 const page=c.cgLoadSales();await tick();state.page=2;pending[3].resolve({items:[{id:'wrongpage'}],total:1});await page;check(node('sales').children.length===0,'changement page invalide la lecture');
 const pages=[];c.cashRequest=async path=>{pages.push(path);return{items:[],total:0}};state.page=3;await c.cgLoadSales();check(state.page===1&&pages.length===2&&pages[1].includes('page=1&'),'dernière page vide ramenée à la première');
 const lateError=deferred();c.cashRequest=()=>lateError.promise;const ignored=c.cgLoadSales();await tick();state.salesGeneration++;lateError.reject(Error('ancienne erreur'));await ignored;check(true,'erreur périmée ignorée comme une réponse périmée');
 // La lecture existante réutilisée après succès doit réellement demander les trois GET.
 const cash=fs.readFileSync(web+'caisse.js','utf8');
 const cashLoad=cash.slice(cash.indexOf('async function cashLoad('),cash.indexOf('async function cashSelect('));
 const reads=[];Object.assign(c,{cashOpenSession(){},cashProviders(){},cashRename(){},cashRules(){},cashNewClient(){},cashHelp(){},cashButton(){},cashRender(){},cashRequest:async path=>{reads.push(path);return path==='/contexte'?{configuration:{}}:{items:[],total:0}}});
 vm.runInContext(cashLoad,c);Object.assign(c.cashState,{page:1,sessionPage:1,historyPage:1});await c.cashLoad(true);
 check(['/sessions?','/attente?','/recus?'].every(prefix=>reads.some(p=>p.startsWith(prefix))),'sessions, attente et historique rafraîchis par GET');
 for(const change of [()=>{c.authState.site='new-site'},()=>{c.cashState.page++}]){
  const waiting=deferred(),previous=c.cashState.context;c.cashRequest=()=>waiting.promise;const reading=c.cashLoad(true);change();waiting.resolve({obsolete:true});await reading;
  check(c.cashState.context===previous,'lecture caisse obsolète rejetée après changement de contexte/page');
 }
 for(const failRefresh of [false,true]){
  const f=fixture();({c,state,node}=f);let posts=0,loads=0,fail=failRefresh;
  const draft={dossier:{id:'draft',etat:'BROUILLON',revision:4},ventes:[{vente_id:'a'},{vente_id:'b'}]};
  const result={...draft,dossier:{...draft.dossier,etat:'FINALISE',revision:5},resultat:{recu_collectif:{id:'collectif'},recus_individuels:[{id:'r1'},{id:'r2'}]}};
  state.draft=draft;state.selected.set('a',{});state.selected.set('b',{});state.selected.set('unrelated',{});state.saleDetails.set('a',{confirmations:[]});c.cashState.sale={id:'a'};
  for(const id of ['sales','cash-waiting'])for(const sale of ['a','b','unrelated']){const row=new Element();row.tag='tr';row.dataset.venteId=sale;node(id).append(row)}
  Object.assign(c,{window:{confirm:()=>true},cgCanFinalize:()=>state.draft.dossier.etat==='BROUILLON',cgLoyaltyPayload:()=>[],cgFinalizationKey:()=> 'key',cgClearFinalizationKey(){},cgLoyaltyStorageKey:()=>'',cgMutation:async(path,method)=>{assert.equal(method,'POST');posts++;return result},cgRenderDraft(){},cgFailure(error){throw error},cgOriginalLoad:async()=>{loads++;if(fail)throw Error('GET indisponible')},cashRequest:async path=>path.startsWith('/ventes/')?{id:path.split('/')[2],etat:'ENCAISSEE',confirmations:[]}:{items:[],total:0}});
  load(c,['cgForgetFinalizedSales','cgRefreshAfterFinalization','cgFinalize']);await c.cgFinalize();
  check(posts===1&&loads===1,'un seul POST et actualisation automatique');check(state.draft===result&&state.draft.resultat.recus_individuels.length===2,'dossier finalisé et reçus conservés');
  check(!state.selected.has('a')&&!state.selected.has('b')&&state.selected.has('unrelated'),'seules les sélections obsolètes supprimées');check(c.cashState.sale===null,'ancienne vente individuelle invalidée');
  check(!node('cash-waiting').children.some(row=>row.dataset.venteId==='a'),'retrait immédiat des préparations finalisées');
  if(failRefresh){check(f.messages.at(-1).includes('Encaissement effectué ; seule l’actualisation'),'échec GET distinct du succès financier');const retry=node('cash-message').children.at(-1);fail=false;await retry.listeners.click();check(posts===1&&loads===2,'reprise exclusivement en lecture sans second POST');check(state.draft===result,'reprise conserve reçus et dossier');}
  else check(f.messages.at(-1).includes('historique actualisés'),'succès de lecture annoncé');
 }
 // Une ancienne liste encore en vol avant le POST ne peut ressusciter les ventes encaissées.
 {const f=fixture();const stale=deferred();f.c.cashRequest=()=>stale.promise;const reading=f.c.cgLoadSales();await tick();load(f.c,['cgForgetFinalizedSales']);f.c.cgForgetFinalizedSales({ventes:[{vente_id:'paid'}]});stale.resolve({items:[{id:'paid'}],total:1});await reading;check(f.node('sales').children.length===0,'finalisation invalide les GET antérieurs');}
 {const f=fixture(),waiting=deferred();f.state.draft={dossier:{etat:'FINALISE'},ventes:[],resultat:{recu_collectif:{id:'retained'}}};const draft=f.state.draft;f.c.cgOriginalLoad=()=>waiting.promise;load(f.c,['cgRefreshAfterFinalization']);const refresh=f.c.cgRefreshAfterFinalization();f.c.authState.site='different';waiting.resolve();await refresh;check(f.requests.length===0&&f.messages.length===0,'changement de contexte interrompt la chaîne de rafraîchissement');check(f.state.draft===draft&&draft.resultat.recu_collectif.id==='retained','lecture abandonnée conserve le dossier et ses reçus');}
 const vente=fs.readFileSync(web+'vente.js','utf8'),calls=[],vs={current:{id:'preparation',etat:'TRANSMISE',numero_appel:'0002',emplacement_id:'loc'},context:{ticket_appel:true}};let allowed=true;
 const v=vm.createContext({venteState:vs,authHas:p=>allowed&&p==='vente.consulter',cashState:{sale:{id:'wrong'},session:null},cashPDF:async(path,download)=>calls.push({path,download}),venteButton:(parent,label,fn,permission)=>parent.push({label,fn,permission})});
 for(const name of ['venteAppelDisponible','venteAppel','venteAppelAction'])vm.runInContext(vente.split('\n').find(l=>l.startsWith('function '+name+'(')),v);
 const buttons=[];v.venteAppelAction(buttons,vs.current);check(buttons.length===1&&buttons[0].permission==='vente.consulter','bouton vendeur sans permission caisse');check(buttons[0].label==="Ticket d'appel · client + suivi interne",'libellé demandé');await buttons[0].fn();check(calls[0].path==='/ventes/preparation/appel/pdf'&&!calls[0].download,'identifiant Préparation et GET PDF existant');
 vs.current.etat='ENCAISSEE';check(v.venteAppelDisponible(vs.current),'réimpression encaissée disponible');await v.venteAppel();check(calls.length===2&&vs.current.numero_appel==='0002','réimpression sans changer numéro');
 vs.context.ticket_appel=false;check(!v.venteAppelDisponible(vs.current),'configuration désactivée');vs.context.ticket_appel=true;vs.current.numero_appel=null;check(!v.venteAppelDisponible(vs.current),'numéro absent');vs.current.numero_appel='0002';allowed=false;check(!v.venteAppelDisponible(vs.current),'permission absente');allowed=true;vs.current.etat='PREPARATION';check(!v.venteAppelDisponible(vs.current),'pas avant transmission');
 check(!fs.readFileSync(web+'caisse.js','utf8').includes('Ticket d’appel · deux exemplaires'),'ancien bouton caisse retiré');
 console.log(`${checks} assertions UI-002 / UX-003 réussies (DOM et HTTP simulés).`);
})().catch(e=>{console.error(e);process.exitCode=1});
