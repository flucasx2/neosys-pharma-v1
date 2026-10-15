"use strict";
const comptoirFilters=new Map();
function comptoirClear(prefix){for(const [key,entry] of comptoirFilters)if(key.startsWith(prefix)){entry.form.remove();comptoirFilters.delete(key);}}
function comptoirQuery(key){const entry=comptoirFilters.get(key);return entry?new URLSearchParams(entry.values).toString():"";}
function comptoirFilter(key,target,context,states,refresh){
 if(comptoirFilters.has(key))return;
 const form=document.createElement('form');form.className='catalogue-fields comptoir-filters';form.setAttribute('aria-label',key==='p4-search'?'Recherche des préparations':key==='cash-queue-search'?'Recherche de la file caisse':'Recherche des reçus');
 const search=stockField(form,'q','Rechercher numéro, référence, produit ou UUID','search',false);search.maxLength=200;
 if(states.length){const select=stockField(form,'etat','État','select',false);select.add(new Option('Tous les états',''));for(const x of states)select.add(new Option(x.replaceAll('_',' '),x));}
 stockField(form,'debut','Du (UTC)','date',false);stockField(form,'fin','Au inclus (UTC)','date',false);
 const locations=context.emplacements||[];if(locations.length){const select=stockField(form,'emplacement_id','Emplacement','select',false);select.add(new Option('Tous les emplacements autorisés',''));for(const x of locations)select.add(new Option(x.nom,x.id));}
 const caisses=context.caisses||locations.flatMap(l=>l.caisses);if(caisses.length){const select=stockField(form,'caisse_id','Caisse destinataire','select',false);select.add(new Option('Toutes les caisses autorisées',''));for(const x of caisses)select.add(new Option(x.nom,x.id));}
 const apply=document.createElement('button');apply.type='submit';apply.textContent='Rechercher';form.append(apply);
 const reset=document.createElement('button');reset.type='button';reset.textContent='Effacer les filtres';form.append(reset);
 const entry={form,values:{}};comptoirFilters.set(key,entry);$(target).append(form);
 const run=()=>{entry.values=Object.fromEntries([...new FormData(form)].filter(([k,v])=>v));Promise.resolve(refresh()).catch(e=>{const box=$(key.startsWith('p4')?'p4-message':'cash-message');box.textContent=e.message;});};
 form.addEventListener('submit',e=>{e.preventDefault();run();});reset.addEventListener('click',()=>{form.reset();run();});
}
