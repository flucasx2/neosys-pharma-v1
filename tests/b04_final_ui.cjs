// Régression B04 : vrais contrôleurs et cycle de clonage modal ; DOM/HTTP simulés.
const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
const web='src/neosys_pharma/presentation/web/';
const cash=fs.readFileSync(web+'caisse.js','utf8'),group=fs.readFileSync(web+'encaissement_groupe.js','utf8'),dialogs=fs.readFileSync(web+'creation_dialogs.js','utf8');
let checks=0;
function check(condition,message){assert.ok(condition,message);checks++;}
function load(context,source,names){for(const name of names){if(source===cash){vm.runInContext(source.split('\n').find(line=>line.startsWith('function '+name+'(')||line.startsWith('async function '+name+'(')),context);continue;}const start=source.indexOf('function '+name+'(');assert.ok(start>=0,name);const begin=source.slice(start-6,start)==='async '?start-6:start;const tail=source.slice(start+9);const next=/\n(?:async )?function /.exec(tail);vm.runInContext(source.slice(begin,next?start+9+next.index:source.length),context);}}
class Element{
 constructor(tag){this.tagName=tag;this.children=[];this.listeners={};this.value='';this.defaultValue='';this.textContent='';this.disabled=false;this.checked=false;this.dataset={};this.classList={add(){},toggle(){}};}
 append(...nodes){for(const n of nodes){if(n.parent)n.parent.children.splice(n.parent.children.indexOf(n),1);n.parent=this;this.children.push(n)}}
 prepend(n){this.children.unshift(n);n.parent=this}
 get firstChild(){return this.children[0]}
 setAttribute(k,v){this[k]=v}
 hasAttribute(k){return this[k]!==undefined}
 addEventListener(type,fn){(this.listeners[type]??=[]).push(fn)}
 emit(type){for(const f of this.listeners[type]||[])f({target:this});if(this.parent)this.parent.emit(type)}
 querySelectorAll(selector){const all=this.children.flatMap(n=>[n,...n.querySelectorAll('*')]);if(selector==='*')return all;if(selector==='[id]')return all.filter(n=>n.id);if(selector==='[for]')return [];if(selector==='button')return all.filter(n=>n.tagName==='button');if(selector==='tr')return all.filter(n=>n.tagName==='tr');if(selector.includes('data-edited'))return all.filter(n=>n.tagName==='input'&&n.dataset.edited==='true');if(selector.includes('input'))return all.filter(n=>n.tagName==='input');return []}
 querySelector(selector){if(selector==='.cash-financial-summary')return this.querySelectorAll('*').find(n=>n.className==='cash-financial-summary');if(selector==='[aria-live=polite]')return this.querySelectorAll('*').find(n=>n['aria-live']==='polite');return this.querySelectorAll(selector)[0]||null}
 get elements(){const result=Object.fromEntries(this.querySelectorAll('*').filter(n=>n.name).map(n=>[n.name,n]));Object.defineProperty(result,Symbol.iterator,{value:function*(){yield* Object.values(this)}});return result;}
 get options(){return this.children.filter(n=>n.tagName==='option')}
 add(n){this.append(n)}
 replaceChildren(){this.children=[]}
 setCustomValidity(text){this.validationMessage=text}
 closest(tag){return this.parent?.tagName===tag?this.parent:this.parent?.closest(tag)}
 cloneNode(){const copy=new Element(this.tagName);for(const k of ['value','defaultValue','textContent','name','type','id','className','aria-live','checked'])if(this[k]!==undefined)copy[k]=this[k];for(const child of this.children)copy.append(child.cloneNode(true));return copy}
 reset(){for(const e of Object.values(this.elements)){e.value=e.defaultValue;e.checked=false}}
 showModal(){this.open=true}
 getClientRects(){return [1]}
 focus(){}
}
const forms=[],document={body:new Element('body'),createElement(tag){const n=new Element(tag);if(tag==='form')forms.push(n);return n}};
const state={busy:false,epoch:1,key:'B04',sale:{id:'sale',totaux:{ttc:7000},confirmations:[{id:'card',mode:'CARTE',montant:1000,moyen_libelle:'CARTE'}]},session:{id:'session'},account:null,context:{configuration:{modes:['ESPECES'],moyens:[]}}};
const ctx=vm.createContext({document,window:{addEventListener(){}},cashState:state,shellState:{view:'encaissement'},creationDialogs:{entries:new Map()},crypto:require('node:crypto'),authHas:()=>true,cashRefreshFidelity:async()=>{},cashBusy(){},venteMoney:String,
 FormData:class{constructor(form){this.form=form}*[Symbol.iterator](){for(const [name,n] of Object.entries(this.form.elements))yield [name,n.value]}},
 stockText(parent,text){const n=document.createElement('p');n.textContent=text;parent.append(n)},
 stockField(form,name,label,type='text',required=true,value=''){const n=document.createElement('input');n.name=name;n.type=type;n.value=n.defaultValue=String(value);form.append(n);return n},
});
load(ctx,cash,['cashFinancialSummary','cashRenderFinancialSummary','cashPaymentChoices','cashModal','cashPay']);load(ctx,dialogs,['creationDialogSnapshot','creationDialogCreate','creationDialogOpen']);
(async()=>{
 await ctx.cashPay();const entry=[...ctx.creationDialogs.entries.values()][0],summary=entry.form.querySelector('[aria-live=polite]');
 check(entry.dialog.open,'vraie ouverture modale');check(entry.form!==forms[0],'formulaire cloné');
 check(summary.textContent.includes('Total reçu : 0'),'état initial du clone');
 entry.form.elements.especes.value='10000';entry.form.elements.especes.emit('input');
 check(summary.textContent.includes('Total reçu : 10000'),'saisie sur clone');check(summary.textContent.includes('Rendu monnaie : 3000'),'rendu visible');check(summary.textContent.includes('Net encaissé : 7000'),'net visible');
 check(forms[0].elements.especes.value==='0','source détachée intacte');
 entry.form.elements.especes.value='6000';entry.form.elements.especes.emit('change');check(summary.textContent.includes('Reste à répartir : 1000'),'change/insuffisant');
 entry.form.elements.confirmation_card.checked=true;entry.form.elements.confirmation_card.emit('change');check(summary.textContent.includes('Reste à répartir : 0'),'confirmation cochée');
 const nodes=Object.fromEntries(['panel','reload','resume','resume-id','refresh','prev','next','finalise','allocation-body','payments'].map(k=>[k,new Element(['reload','resume','refresh','prev','next','finalise'].includes(k)?'button':k)]));nodes['resume-id'].value='draft';nodes.panel.append(nodes.reload,nodes.resume,nodes.refresh,nodes.prev,nodes.next,nodes.finalise);
 let allowed=true,requests=[],fail=false,resolve;
 const cf={id:'existing',mode:'CARTE',moyen_id:'card-provider',montant:'10000',reference:'TEST-B04-CARTE-001'};
 const pay={mode:'CARTE',moyen_id:'card-provider',montant:'10000',rendu:'0',confirmation_id:'existing'};
 const gs={busy:false,page:1,hasNextPage:false,draft:{dossier:{id:'draft',etat:'BROUILLON'},ventes:[{vente_id:'sale'}],totaux:{du_xaf:'101400'},reglements:[]},payments:[pay],saleDetails:new Map([['sale',{confirmations:[]}]]),loyalty:new Map()};
 const c=vm.createContext({document,Option:function(label,value){const n=new Element('option');n.textContent=label;n.value=value;return n},cashGroupState:gs,cashState:{context:{configuration:{modes:['CARTE','ESPECES'],moyens:[{id:'card-provider',libelle:'CARTE',mode:'CARTE',actif:true}]}}},authHas:()=>allowed,cg:id=>nodes[id],cgMoney:String,cgMessage(){},cgSyncFinaliseButton(){nodes.finalise.disabled=true},cgRenderSelection(){},cgRenderDraft(){},cgRenderReview(){},cgFailure(e){throw e},cgRequest:async path=>{requests.push(path);return gs.draft},cashRequest:async path=>{requests.push(path);if(fail)throw new Error('offline');return {id:'sale',confirmations:[cf]}},window:{confirm:()=>false}});
 load(c,cash,['cashPaymentChoices']);load(c,group,['cgInt','cgCashChange','cgConfirmationOptions','cgSyncConsultationButtons','cgBusy','cgRefreshConfirmations','cgReload','cgRenderPayments','cgPaymentPayload']);
 check(c.cgConfirmationOptions('CARTE',10000,'card-provider').length===0,'cache initial périmé');
 await c.cgRefreshConfirmations('sale');
 check(c.cgConfirmationOptions('CARTE',10000,'card-provider')[0].id==='existing','confirmation existante après lecture fraîche');check(gs.payments[0]===pay&&pay.montant==='10000'&&pay.confirmation_id==='existing','saisie et identité préservées');check(requests.join()==='/ventes/sale','aucune requête financière');
 check(!nodes.reload.disabled&&!nodes.resume.disabled,'consultations réactivées');check(nodes.finalise.disabled,'pas de réactivation globale');
 nodes['resume-id'].value='';c.cgSyncConsultationButtons();check(nodes.resume.disabled&&!nodes.reload.disabled,'id requis uniquement pour consulter');
 allowed=false;c.cgSyncConsultationButtons();check(nodes.reload.disabled&&nodes.refresh.disabled,'permissions consultation');allowed=true;
 gs.busy=true;const n=requests.length;await c.cgReload();check(requests.length===n,'pas de reload concurrent');gs.busy=false;
 const row=new Element('tr'),edit=new Element('input');edit.dataset.edited='true';row.append(edit);nodes['allocation-body'].append(row);await c.cgReload();check(requests.length===n,'annulation protège ventilation locale');nodes['allocation-body'].replaceChildren();
 fail=true;await c.cgRefreshConfirmations();check(gs.confirmationRefreshError.includes('offline'),'échec refresh visible');check(pay.confirmation_id==='existing','pas de remplacement en cas erreur');fail=false;await c.cgRefreshConfirmations();check(gs.confirmationRefreshError==='','reprise lecture réussie');
 c.cgRenderPayments();let root=nodes.payments.children[0];check(root.children.some(n=>n.className==='cash-group-confirmation'),'confirmation non espèces conservée');check(root.children.find(n=>n.tagName==='button')['aria-label'].includes('1'),'suppression accessible');
 check(nodes.payments.querySelectorAll('*').some(n=>n.className==='cash-group-confirmation-reference'&&n.textContent.includes('TEST-B04-CARTE-001')),'référence lisible hors du sélecteur');const modeInput=root.children.find(n=>n.tagName==='select');modeInput.value='ESPECES';modeInput.emit('change');check(pay.mode==='CARTE'&&pay.confirmation_id==='existing','annuler changement moyen conserve confirmation');
 pay.montant='9999';c.cgRenderPayments();check(pay.confirmation_id==='existing','incompatible conservée explicitement');check(nodes.payments.querySelectorAll('*').some(n=>n.validationMessage),'incompatibilité affichée');assert.throws(()=>c.cgPaymentPayload(),/incompatible/);checks++;
 Object.assign(gs.payments[0],{mode:'ESPECES',moyen_id:null,confirmation_id:null,montant:'102000'});c.cgRenderPayments();check(!nodes.payments.querySelectorAll('*').some(n=>n.className==='cash-group-confirmation'),'aucun champ confirmation espèces');check(nodes.payments.children[0].children.filter(n=>n.tagName!=='legend').length===3,'rangée moyen montant suppression');

 // Recharge explicite réussie conserve même une liste vidée localement.
 c.cgLoadLoyaltyForSale=async()=>{};load(c,group,['cgLoadDraftSales']);
 const local=gs.payments;await c.cgReload();check(gs.payments===local,'reload conserve les lignes locales');
 gs.payments=[];gs.paymentsHydrated=true;await c.cgReload();check(gs.payments.length===0,'reload conserve une suppression locale');
 // Un refresh des confirmations reconstruit la grille sans effacer une allocation éditée.
 const makeRow=value=>{const r=new Element('tr');r.rowIndex=1;const input=new Element('input');input.value=value;input.dataset.edited='true';r.append(input);return r};
 nodes['allocation-body'].append(makeRow('345'));
 c.cgRenderDraft=()=>{nodes['allocation-body'].replaceChildren();nodes['allocation-body'].append(makeRow('0'))};
 await c.cgRefreshConfirmations();check(nodes['allocation-body'].querySelectorAll('input')[0].value==='345','allocation locale restaurée après refresh');

 // Le rendu réel ne réhydrate pas silencieusement une suppression locale complète.
 const renderNodes={};const stored={dossier:{id:'stored',etat:'BROUILLON'},reglements:[{mode:'ESPECES',montant:'100',rendu:'0'}],ventes:[],allocations:[],totaux:{du_xaf:'100'}};
 const renderState={draft:stored,payments:[],paymentsHydrated:true,loyalty:new Map()};
 const rc=vm.createContext({cashGroupState:renderState,cashState:{session:null},cg:id=>renderNodes[id]??=(new Element(id)),cgRememberDraft(){},cgMoney:String,cgRenderPayments(){},cgRenderAllocations(){},cgRenderReview(){},cgRenderReceipts(){},cgSyncFinaliseButton(){},cgSyncConsultationButtons(){}});
 load(rc,group,['cgRenderDraft']);rc.cgRenderDraft();check(renderState.payments.length===0,'rendu réel conserve la liste vidée');
 renderState.paymentsHydrated=false;rc.cgRenderDraft();check(renderState.payments.length===1,'première consultation hydrate les lignes sauvegardées');
 // Changer de dossier avec saisies locales demande une décision explicite.
 c.cgHasUnsavedFinancialChanges=()=>true;c.cgRememberDraft=()=>{};load(c,group,['cgResume']);nodes['resume-id'].value='other';const before=requests.length;await c.cgResume();check(requests.length===before&&gs.draft.dossier.id==='draft','annulation changement dossier sans lecture ni perte');
 // Les points d'acquisition et de rapprochement réels appellent la lecture fraîche.
 let save,refreshed=[],transport=[];
 const hooks=vm.createContext({cashState:{sale:{id:'sale',revision:4,totaux:{ttc:33800}},session:{id:'session'},context:{configuration:{modes:['CARTE'],moyens:[{id:'provider',mode:'CARTE',libelle:'CARTE',actif:true}]}}},cashModal(title,permission,build,callback){save=callback},cashRequest:async(path,method,body)=>{transport.push({path,method,body});return {id:'sale'}},cgRefreshConfirmations:async id=>refreshed.push(id)});
 load(hooks,cash,['cashPaymentChoices','cashConfirm','cashReconcile']);
 hooks.cashConfirm();await save({mode:'CARTE:provider',montant:'10000',reference:'fictive',preuve:'test'},{});
 check(refreshed.join()==='sale','acquisition déclenche lecture du groupe');check(transport[0].body.moyen_id==='provider','identité du fournisseur conservée');
 hooks.cashState.sale={id:'sale',revision:4,totaux:{ttc:33800}};hooks.cashReconcile({id:'existing',reference:'TEST-B04-CARTE-001',montant:10000});await save({justification:'test'},{});
 check(refreshed.join()==='sale,sale','rapprochement explicite déclenche lecture du groupe');check(transport.filter(x=>x.path.endsWith('/confirmations')).length===1,'aucune nouvelle acquisition lors du rapprochement');
 console.log(`${checks} assertions B04 finales réussies : clonage/saisie, cache, consultation, concurrence, conservation et lignes compactes.`);
})().catch(e=>{console.error(e);process.exitCode=1});
