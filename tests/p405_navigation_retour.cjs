// H4 : même navigation réelle pour reçu individuel simple et issu du groupe.
const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
const {JSDOM}=require('jsdom');
const source=fs.readFileSync('src/neosys_pharma/presentation/web/regularisation.js','utf8');
function load(c,name){const start=source.indexOf('function '+name+'('),begin=source.slice(start-6,start)==='async '?start-6:start,next=/\n(?:async )?function /.exec(source.slice(start+9));assert.ok(start>=0);vm.runInContext(source.slice(begin,next?start+9+next.index:source.length),c);}
let checks=0;const check=(v)=>{assert.ok(v);checks++};
(async()=>{
for(const grouped of [false,true]){
 const dom=new JSDOM('<table><thead id="finance-head"></thead><tbody id="finance-rows"></tbody></table>');
 const document=dom.window.document,buttons=[],reads=[],modals=[];let mutations=0;
 const receipt={id:grouped?'recu-individuel-du-groupe':'recu-individuel-simple',dossier_id:grouped?'dossier-collectif':null,total_xaf:'33800'};
 const c=vm.createContext({document,$:id=>document.getElementById(id),BigInt,venteMoney:String,stockDate:()=>'',
 stockText(parent,text,tag='p'){const n=document.createElement(tag);n.textContent=text;parent.append(n);return n},
 stockField(parent,name,label,type,required,value){const n=document.createElement(type==='textarea'?'textarea':'input');n.name=name;n.type=type;n.value=value??'';parent.append(n);return n},
 financeButton(parent,label,fn,permission){buttons.push({label,fn,permission})},
 financeReadForAction:async path=>{reads.push(path);return{lignes:[{designation:'Produit fictif historique',conditionnement:'Unité',lot:'LOT-FICTIF',quantite_restante:1,ligne_id:'line',stock_id:'stock'}]}},
 financeRequest:()=>{mutations++;throw Error('Aucune mutation pendant une consultation H4')},
 financeModal(title,permission,build){const form=document.createElement('form');build(form);modals.push({title,permission,form})}});
 load(c,'financeRender');load(c,'financeReturn');c.financeRender({items:[receipt]},'ventes');
 check(buttons.length===1&&buttons[0].label==='Créer un retour'&&buttons[0].permission==='vente.retour.gerer');
 await buttons[0].fn();
 check(reads[0]==='/recus/'+receipt.id+'/retournable'&&!reads[0].includes('dossier-collectif'));
 check(modals[0].permission==='vente.retour.gerer'&&modals[0].title.includes('prix historiques'));
 check(modals[0].form.elements.namedItem('q_0').max==='1'&&modals[0].form.textContent.includes('LOT-FICTIF'));
 check(mutations===0);
 dom.window.close();
}
console.log(`${checks} assertions de navigation retour réussies (DOM réel jsdom, GET simulé, aucun POST).`);
})().catch(e=>{console.error(e);process.exitCode=1});
