// U01 : contrôleurs et cycle réel des modales clonées, DOM/HTTP simulés.
const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
const base='src/neosys_pharma/presentation/web/',source=fs.readFileSync(base+'regularisation.js','utf8'),dialogs=fs.readFileSync(base+'creation_dialogs.js','utf8');
let checks=0;function check(value,label){assert.ok(value,label);checks++;}
function load(c,text,names){for(const name of names){const start=text.indexOf('function '+name+'(');assert.ok(start>=0,name);const begin=text.slice(start-6,start)==='async '?start-6:start,next=/\n(?:async )?function /.exec(text.slice(start+9));vm.runInContext(text.slice(begin,next?start+9+next.index:text.length),c);}}
class Element{
 constructor(tag='div'){this.tagName=tag;this.children=[];this.listeners={};this.value=this.defaultValue='';this.checked=false;this.disabled=false;this.dataset={};this.classList={add(){},toggle(){}};this.textContent='';}
 append(...nodes){for(const node of nodes){if(node.parent)node.remove();node.parent=this;this.children.push(node)}}prepend(n){n.parent=this;this.children.unshift(n)}remove(){this.parent.children=this.parent.children.filter(n=>n!==this)}
 replaceChildren(...nodes){this.children=[];this.append(...nodes)}get firstChild(){return this.children[0]}setAttribute(k,v){this[k]=v}hasAttribute(k){return this[k]!==undefined}
 addEventListener(type,fn){(this.listeners[type]??=[]).push(fn)}async emit(type){for(const fn of this.listeners[type]||[])await fn({target:this,preventDefault(){}})}
 querySelectorAll(selector){const all=this.children.flatMap(n=>[n,...n.querySelectorAll('*')]);if(selector==='*')return all;if(selector==='[id]')return all.filter(n=>n.id);if(selector==='[for]')return[];if(selector==='button')return all.filter(n=>n.tagName==='button');if(selector.includes('input'))return all.filter(n=>['input','select','textarea'].includes(n.tagName));return[]}
 get elements(){const result=Object.fromEntries(this.querySelectorAll('*').filter(n=>n.name).map(n=>[n.name,n]));Object.defineProperty(result,Symbol.iterator,{value:function*(){yield*Object.values(this)}});Object.defineProperty(result,'namedItem',{value:name=>result[name]});return result;}
 get options(){return this.children.filter(n=>n.tagName==='option')}get selectedOptions(){return this.options.filter(n=>n.value===this.value)}add(n){this.append(n)}
 cloneNode(){const copy=new Element(this.tagName);for(const k of ['name','id','value','defaultValue','checked','defaultChecked','type'])if(this[k]!==undefined)copy[k]=this[k];for(const child of this.children)copy.append(child.cloneNode(true));return copy}
 reset(){for(const n of this.elements){n.value=n.defaultValue;n.checked=!!n.defaultChecked}}showModal(){this.open=true}close(){this.open=false}getClientRects(){return[1]}focus(){}scrollIntoView(){}
}
const deferred=()=>{let resolve,reject;const promise=new Promise((a,b)=>{resolve=a;reject=b});return{promise,resolve,reject}};
const tick=()=>new Promise(r=>setImmediate(r));
function fixture(){
 const nodes={},node=id=>nodes[id]??=new Element(),rendered=[];
 node('finance-genre').value='clotures';for(const genre of ['clotures','retours','ventes','quarantaine']){const option=new Element('option');option.value=genre;node('finance-genre').add(option)}node('finance-session').value='session';
 const document={body:new Element('body'),createElement:tag=>new Element(tag)};
 const c=vm.createContext({document,$:node,window:{confirm:()=>true,addEventListener(){}},crypto:require('node:crypto'),financeState:{epoch:0,page:1,context:{sessions:[]},key:'org:site:'},authState:{me:{organisation:{id_organisation:'org'},utilisateur:{id_utilisateur:'user'}},site:'site'},shellState:{view:'finance'},authHas:()=>true,
 financeRequest:async path=>path==='/contexte'?{sessions:[{id:'session',etat:'OUVERTE',caissier_id:'user',especes_attendues:'1000'}],coffres:[],periode:null}:{items:[],total:0},financeRender:(data,genre)=>rendered.push({data,genre}),
 financeButton(){},financeX(){},financeZ(){},financeFonds(){},financeTransfer(){},financeEcart(){},venteMoney:String,stockText(){},
 stockOptions(select,rows){select.replaceChildren();for(const row of rows){const option=new Element('option');option.value=row.id;select.add(option)}},
 stockField(form,name,label,type='text',required=true,value=''){const n=new Element('input');n.name=name;n.type=type;n.value=n.defaultValue=String(value);form.append(n);return n},creationDialogs:{entries:new Map()},
 FormData:class{constructor(f){this.f=f}*[Symbol.iterator](){for(const n of this.f.elements)if(!n.disabled&&(n.type!=='checkbox'||n.checked))yield[n.name,n.value]}},
 });
 load(c,source,['financeScope','financeReadContext','financeActionContext','financeModalContext','financeReadForAction','financeLoad']);return{c,node,rendered};
}
(async()=>{
 let f=fixture(),{c,node,rendered}=f,pending=[];
 const original=c.financeRequest;c.financeRequest=path=>path==='/contexte'?original(path):(()=>{const d=deferred();pending.push(d);return d.promise})();
 const old=c.financeLoad();await tick();const recent=c.financeLoad();await tick();pending[1].resolve({items:[{id:'new'}],total:1});await recent;pending[0].resolve({items:[{id:'old'}],total:1});await old;
 check(rendered.length===1&&rendered[0].data.items[0].id==='new','réponse ancienne ne remplace pas la récente');
 const stale=c.financeLoad();await tick();node('finance-message').textContent='message récent';c.financeState.epoch++;pending[2].reject(Error('ancienne erreur'));await stale;check(node('finance-message').textContent==='message récent','erreur ancienne ignorée');
 for(const change of [f=>f.c.authState.site='other',f=>f.node('equipement-emplacement').value='other',f=>f.c.financeState.page=2,f=>f.node('finance-genre').value='retours',f=>f.node('finance-search').value='new',f=>f.c.shellState.view='vente']){
  f=fixture();const d=deferred();f.c.financeRequest=()=>d.promise;const reading=f.c.financeLoad();change(f);d.resolve({sessions:[],coffres:[],periode:null});check(await reading===false&&f.rendered.length===0,'contexte site/emplacement/page/genre/recherche/module périmé');
 }
 f=fixture();let reads=0;const transport=f.c.financeRequest;f.c.financeRequest=async p=>{if(p!=='/contexte')reads++;return transport(p)};f.c.financeState.page=4;await f.c.financeLoad();check(f.c.financeState.page===1&&reads===2,'pagination vide ajustée avec lecture bornée');
 for(const name of ['financeReturn','financeRefund']){
  for(const reject of [false,true]){
   f=fixture();load(f.c,source,[name]);let opened=0;f.c.financeModal=()=>opened++;const d=deferred();f.c.financeRequest=()=>d.promise;
   f.c.financeSession=()=>({id:'session'});const opening=f.c[name]({id:'sale'});await tick();f.node('finance-session').value='other';if(reject)d.reject(Error('old'));else d.resolve({lignes:[],montant:'1',disponible_par_moyen:[]});await opening;
   check(opened===0,'aucune modale ni erreur obsolète après changement de session');
  }
 }
 f=fixture();const actions=[];f.c.financeRequest=()=>{const d=deferred();actions.push(d);return d.promise};const a=f.c.financeReadForAction('/a'),b=f.c.financeReadForAction('/b');actions[1].resolve({id:'b'});check((await b).id==='b','détail récent accepté');actions[0].resolve({id:'a'});check(await a===null,'détail ancien abandonné');
 // Vrai contrôleur partagé : après POST réussi, le second submit ne relit que les GET.
 f=fixture();({c,node}=f);load(c,dialogs,['creationDialogSnapshot','creationDialogClose','creationDialogCreate','creationDialogOpen']);load(c,source,['financeBusy','financeModal']);let posts=0,refreshes=0;
 c.financeLoad=async()=>{refreshes++;if(refreshes===1)throw Error('GET hors ligne');return true};
 const entry=c.financeModal('Fonds','caisse.fonds.gerer',form=>c.stockField(form,'montant','Montant','number',true,'100'),async()=>{posts++;return{id:'saved'}});
 check(entry.dialog.open&&entry.form.elements.montant.value==='100','modale clonée initialisée');await entry.form.emit('submit');check(posts===1&&entry.saved.id==='saved','mutation enregistrée une seule fois');
 check(entry.error.textContent.includes('Enregistrement effectué')&&entry.submit.textContent==='Réessayer l’actualisation','succès financier distingué du GET échoué');check(entry.form.elements.montant.disabled,'saisie figée après succès');
 await entry.form.emit('submit');check(posts===1&&refreshes===2&&!entry.dialog.open,'reprise GET sans nouveau POST');
 const second=c.financeModal('Fonds','caisse.fonds.gerer',()=>{},async()=>{posts++;return{id:'forbidden'}});c.authState.site='other';await second.form.emit('submit');check(posts===1,'contexte changé interdit sauvegarde de l’ancienne modale');
 f=fixture();({c,node}=f);load(c,dialogs,['creationDialogSnapshot','creationDialogClose','creationDialogCreate','creationDialogOpen']);load(c,source,['financeBusy','financeModal']);const keys=[];
 c.financeLoad=async()=>true;
 const uncertain=c.financeModal('Fonds','caisse.fonds.gerer',()=>{},async(d,k)=>{keys.push(k.cle);if(keys.length===1)throw Error('Réponse réseau perdue');return{id:'same-operation'}});
 await uncertain.form.emit('submit');check(uncertain.saved===null&&uncertain.dialog.open,'réponse de mutation incertaine conserve la modale');
 await uncertain.form.emit('submit');check(keys.length===2&&keys[0]===keys[1],'mutation incertaine réutilise sa clé d’idempotence');
 // D03/D04 : vrais formulaires clonés, attestation et reprise GET uniquement.
 f=fixture();({c,node}=f);load(c,dialogs,['creationDialogSnapshot','creationDialogClose','creationDialogCreate','creationDialogOpen']);load(c,source,['financeBusy','financeModal','financeCancelRefund']);const mutations=[];let reloads=0;
 c.financeRequest=async(path,method,body)=>{mutations.push({path,method,body});return{id:'refund',etat:'ANNULE'}};
 c.financeLoad=async()=>{if(++reloads===1)throw Error('GET après annulation indisponible');return true};
 const cancel=c.financeCancelRefund({id:'refund',revision:3,montant:'301',retour_id:'return'});
 cancel.form.elements.justification.value='Erreur de moyen avant restitution';await cancel.form.emit('submit');
 check(mutations.length===0&&cancel.error.textContent.includes('Attestation'),'attestation responsable obligatoire après clonage');
 cancel.form.elements.attestation_absence_restitution.checked=true;cancel.form.elements.restitution_externe_incertaine.checked=true;await cancel.form.emit('submit');
 check(mutations.length===0&&cancel.error.textContent.includes('incertaine'),'incertitude externe bloque avant POST');
 cancel.form.elements.restitution_externe_incertaine.checked=false;await cancel.form.emit('submit');
 check(mutations.length===1&&mutations[0].body.revision===3&&mutations[0].body.attestation_absence_restitution===true,'annulation explicite et révisée transmise');
 check(cancel.saved.etat==='ANNULE'&&cancel.error.textContent.includes('Enregistrement effectué'),'annulation réussie distinguée du GET échoué');
 await cancel.form.emit('submit');check(mutations.length===1&&reloads===2,'reprise d’annulation sans second POST');
 c.authHas=()=>false;check(c.financeCancelRefund({id:'forbidden'})===undefined,'permission annuler distincte contrôlée avant modale');
 c.authHas=()=>true;const buttons=[];c.financeButton=(parent,label,fn)=>buttons.push({label,fn});c.financeLoad=async()=>true;
 const received=c.financeModal('Réception','vente.retour.gerer',()=>{},async()=>({document:{retour_id:'return'}}));await received.form.emit('submit');
 check(buttons.some(b=>b.label==='Reçu de réception PDF'),'PDF proposé après réception réussie');
 load(c,source,['financeRender']);c.stockDate=()=>'';buttons.length=0;c.financeRender({items:[{id:'return',montant:'0',document_disponible:true}]},'retours');
 check(buttons.some(b=>b.label==='Reçu de réception PDF')&&!buttons.some(b=>b.label==='Demander remboursement'),'réception nulle imprimable sans demande financière');
 buttons.length=0;c.financeRender({items:[{id:'historical',montant:'0',document_disponible:false}]},'retours');check(buttons.length===0,'historique sans pièce ne fabrique pas de PDF');
 buttons.length=0;c.financeRender({items:[{id:'refund',montant:'301',etat:'ANNULE',annulations:[{justification:'Conservée'}]}]},'remboursements');check(buttons.length===0,'aucune action financière sur état annulé terminal');
 console.log(`${checks} assertions U01 réussies : lectures, contexte, modales clonées et reprise sans POST.`);
})().catch(e=>{console.error(e);process.exitCode=1});
