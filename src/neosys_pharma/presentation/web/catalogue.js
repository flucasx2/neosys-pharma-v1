"use strict";
const catalogueState={version:0,products:[],categories:[],formes:[],laboratoires:[],selected:"",packaging:"",site:"",detail:null,mode:"list",page:1,pageSize:25,total:0,detailVersion:0};
function catalogueRoot(){return `/api/catalogue/organisations/${authState.me.organisation.id_organisation}`;}
function catalogueReset(){
  clearTimeout(catalogueSearchTimer);catalogueState.detailVersion++;catalogueState.version++;Object.assign(catalogueState,{products:[],categories:[],formes:[],laboratoires:[],selected:"",packaging:"",site:"",detail:null,mode:"list",page:1,pageSize:25,total:0,detailVersion:0});
  for(const id of ["catalogue-products","catalogue-packagings","catalogue-category","catalogue-forme","catalogue-laboratoire","catalogue-data-selected","catalogue-parent","catalogue-packaging-selected","catalogue-reference-packaging","catalogue-reference-selected"])$(id).replaceChildren();
  for(const id of ["catalogue-product-form","catalogue-data-form","catalogue-packaging-form","catalogue-reference-form"])$(id).reset();
  $("catalogue-editor-panel").hidden=true;$("catalogue-list-panel").hidden=false;$("catalogue-count").textContent="";$("catalogue-page").textContent="";$("catalogue-page-size").value="25";$("catalogue-data-disclosure").open=false;$("catalogue-detail").hidden=true;$("catalogue-message").textContent="";$("catalogue-ancestors").textContent="";$("catalogue-product-summary").textContent="";$("catalogue-product-description").textContent="";$("catalogue-search").value="";
}
function catalogueGate(){
  const manage=authHas("catalogue.gerer"),edit=manage&&catalogueState.mode==="edit";
  for(const id of ["catalogue-product-form","catalogue-data-form","catalogue-packaging-form","catalogue-reference-form"])$(id).hidden=id==="catalogue-data-form"?!manage:!edit;
  $("catalogue-create").hidden=!manage;$("catalogue-edit").hidden=!manage||catalogueState.mode!=="view";$("catalogue-read-summary").hidden=edit;
  for(const id of ["catalogue-packaging-selected","catalogue-reference-packaging","catalogue-reference-selected"])$(id).closest("label").hidden=!edit;
  $("catalogue-data-panel").hidden=!manage;
  if(!authHas("catalogue.consulter"))catalogueReset();
}
async function catalogueRequest(path,method="GET",body){
  const response=await authFetch(catalogueRoot()+path,{method,body:body?JSON.stringify(body):undefined});
  const result=await response.json();
  if(!response.ok)throw new Error(typeof result.detail==="string"?result.detail:"Vérifiez les champs du catalogue.");
  return result;
}
function catalogueOptions(id,rows,key,selected="",empty="Aucun"){
  const select=$(id);select.replaceChildren(new Option(empty,""));
  for(const row of rows)select.add(new Option(row.nom||row.libelle,row[key]));
  select.value=selected;
}
function catalogueDataSelection(){
  const type=$("catalogue-data-type").value,rows=catalogueState[type];
  const key={categories:"id_categorie",formes:"id_forme",laboratoires:"id_laboratoire"}[type];
  const old=$("catalogue-data-selected").value;
  catalogueOptions("catalogue-data-selected",rows,key,old,"Nouvelle entrée");
  catalogueOptions("catalogue-parent",catalogueState.categories,"id_categorie");
  $("catalogue-parent-label").hidden=type!=="categories";
  const row=rows.find(r=>r[key]===old),form=$("catalogue-data-form");
  form.elements.code.value=row?.code||"";form.elements.nom.value=row?.nom||"";form.elements.actif.checked=row?.actif??true;
  $("catalogue-parent").value=row?.parent_id||"";
}
async function catalogueOpen(id,mode="view"){
  if(mode==="edit"&&!authHas("catalogue.gerer"))return;
  const version=++catalogueState.detailVersion,sessionVersion=catalogueState.version,site=authState.site;
  try{
    const row=id?await catalogueRequest(`/produits/${id}`):null;
    if(version!==catalogueState.detailVersion||sessionVersion!==catalogueState.version||site!==authState.site)return;
    Object.assign(catalogueState,{selected:id,detail:row,mode});catalogueProductSelection();
    $("catalogue-editor-panel").scrollIntoView({block:"start"});$("catalogue-editor-title").focus();
  }catch(e){if(version===catalogueState.detailVersion&&sessionVersion===catalogueState.version)$("catalogue-message").textContent=e.message;}
}
function catalogueProductSelection(){
  const row=catalogueState.detail,form=$("catalogue-product-form");
  $("catalogue-editor-panel").hidden=false;$("catalogue-list-panel").hidden=true;
  $("catalogue-editor-title").textContent=row?(catalogueState.mode==="edit"?"Modifier le produit":"Détail du produit"):"Créer un produit";
  form.reset();form.elements.nom.value=row?.nom||"";form.elements.description.value=row?.description||"";form.elements.actif.checked=row?.actif??true;
  catalogueOptions("catalogue-category",catalogueState.categories,"id_categorie",row?.categorie_id,"Choisir une catégorie");
  catalogueOptions("catalogue-forme",catalogueState.formes,"id_forme",row?.forme_id);
  catalogueOptions("catalogue-laboratoire",catalogueState.laboratoires,"id_laboratoire",row?.laboratoire_id);
  $("catalogue-first-packaging").hidden=Boolean(row);
  for(const name of ["premier_code","premier_libelle"])form.elements[name].required=!row;
  $("catalogue-detail").hidden=!row;
  if(row){
    $("catalogue-product-summary").textContent=`${row.nom} · ${row.actif?"Actif":"Inactif"}`;
    $("catalogue-product-description").textContent=row.description||"Aucune description.";
    $("catalogue-classification").textContent=`Forme : ${catalogueState.formes.find(f=>f.id_forme===row.forme_id)?.nom||"Aucune"} · Laboratoire : ${catalogueState.laboratoires.find(l=>l.id_laboratoire===row.laboratoire_id)?.nom||"Aucun"}`;
    $("catalogue-ancestors").textContent="Catégorie et parents : "+row.categories.map(c=>c.nom).reverse().join(" → ");
    catalogueOptions("catalogue-packaging-selected",row.conditionnements,"id_conditionnement",catalogueState.packaging,"Nouveau conditionnement");
    cataloguePackagingSelection();$("catalogue-packagings").replaceChildren();
    for(const packaging of row.conditionnements){
      const item=document.createElement("li");item.textContent=`${packaging.code} · ${packaging.libelle}${packaging.actif?"":" (inactif)"}`;
      const refs=document.createElement("ul");
      for(const ref of packaging.references){const r=document.createElement("li");r.textContent=`${ref.type_reference} : ${ref.valeur}${ref.actif?"":" (archivée)"}`;refs.append(r);}
      if(!packaging.references.length){const r=document.createElement("li");r.textContent="Aucune référence renseignée.";refs.append(r);}
      item.append(refs);$("catalogue-packagings").append(item);
    }
  }
  catalogueGate();
}
function cataloguePackagingSelection(){
  catalogueState.packaging=$("catalogue-packaging-selected").value;
  const product=catalogueState.detail;
  const packaging=product?.conditionnements.find(c=>c.id_conditionnement===catalogueState.packaging);
  const form=$("catalogue-packaging-form");form.reset();form.elements.code.value=packaging?.code||"";form.elements.libelle.value=packaging?.libelle||"";form.elements.actif.checked=packaging?.actif??true;
  catalogueOptions("catalogue-reference-packaging",product?.conditionnements||[],"id_conditionnement",packaging?.id_conditionnement||product?.conditionnements[0]?.id_conditionnement,"Choisir un conditionnement");
  catalogueReferenceSelection(true);
}
function catalogueReferenceSelection(reset=false){
  const product=catalogueState.detail,pid=$("catalogue-reference-packaging").value;
  const refs=product?.conditionnements.find(c=>c.id_conditionnement===pid)?.references||[];
  const old=reset?"":$("catalogue-reference-selected").value;
  catalogueOptions("catalogue-reference-selected",refs.map(r=>({...r,nom:`${r.type_reference} : ${r.valeur}`})),"id_reference",old,"Nouvelle référence");
  const row=refs.find(r=>r.id_reference===old),form=$("catalogue-reference-form");
  form.elements.type_reference.value=row?.type_reference||"CIP7";form.elements.valeur.value=row?.valeur||"";form.elements.actif.checked=row?.actif??true;
}
async function catalogueLoad(selected=catalogueState.selected,reloadMetadata=true){
  catalogueGate();if(!authHas("catalogue.consulter"))return;
  const version=++catalogueState.version,site=authState.site;
  $("catalogue-list-panel").setAttribute("aria-busy","true");$("catalogue-previous").disabled=true;$("catalogue-next").disabled=true;
  try{
    const params=new URLSearchParams({q:$("catalogue-search").value,page:catalogueState.page,page_size:catalogueState.pageSize});
    const calls=[catalogueRequest("/produits?"+params)];
    if(reloadMetadata)calls.push(...["categories","formes","laboratoires"].map(p=>catalogueRequest("/"+p)));
    const [result,categories,formes,laboratoires]=await Promise.all(calls);
    if(version!==catalogueState.version||site!==authState.site)return;
    Object.assign(catalogueState,{products:result.items,total:result.total,site});
    if(reloadMetadata)Object.assign(catalogueState,{categories,formes,laboratoires});
    // A filter or concurrent change may remove the last page.
    const last=Math.max(1,Math.ceil(result.total/catalogueState.pageSize));
    if(catalogueState.page>last){catalogueState.page=last;return await catalogueLoad(selected,false);}
    catalogueRender();if(reloadMetadata)catalogueDataSelection();
    if(catalogueState.mode!=="list"){
      const detailVersion=catalogueState.detailVersion;
      const detail=selected?await catalogueRequest(`/produits/${selected}`):null;
      if(version!==catalogueState.version||site!==authState.site||detailVersion!==catalogueState.detailVersion||catalogueState.mode==="list")return;
      Object.assign(catalogueState,{selected,detail});catalogueProductSelection();
    }
  }catch(e){if(version===catalogueState.version)$("catalogue-message").textContent=e.message;}
  finally{if(version===catalogueState.version)$("catalogue-list-panel").setAttribute("aria-busy","false");}
}
function catalogueRender(){
  $("catalogue-products").replaceChildren();
  for(const row of catalogueState.products){
    const tr=document.createElement("tr");tr.dataset.productId=row.id_produit;
    for(const text of [row.reference||"—",row.nom,row.categorie,row.forme||"—",row.laboratoire||"—",row.conditionnement||"—",row.actif?"Actif":"Inactif"]){
      const td=document.createElement("td");td.textContent=text;tr.append(td);
    }
    if(row.type_reference){const type=document.createElement("small");type.textContent=row.type_reference;tr.children[0].append(type);}
    if(row.nombre_conditionnements>1){const badge=document.createElement("small");badge.className="catalogue-badge";badge.textContent=`${row.nombre_conditionnements} conditionnements`;tr.children[5].append(badge);}
    tr.children[6].className=row.actif?"catalogue-status":"catalogue-status inactive";
    const actions=document.createElement("td");
    for(const [label,mode] of [["Consulter","view"],["Modifier","edit"]]){
      if(mode==="edit"&&!authHas("catalogue.gerer"))continue;
      const button=document.createElement("button");button.type="button";button.className="secondary";button.textContent=label;button.setAttribute("aria-label",`${label} ${row.nom}`);button.addEventListener("click",()=>catalogueOpen(row.id_produit,mode));actions.append(button);
    }
    tr.append(actions);$("catalogue-products").append(tr);
  }
  $("catalogue-empty").hidden=Boolean(catalogueState.products.length);
  const total=catalogueState.total,start=total?(catalogueState.page-1)*catalogueState.pageSize+1:0,end=Math.min(catalogueState.page*catalogueState.pageSize,total);
  $("catalogue-count").textContent=`${total} résultat${total>1?"s":""} · ${start}–${end}`;
  $("catalogue-page").textContent=`Page ${catalogueState.page} sur ${Math.max(1,Math.ceil(total/catalogueState.pageSize))}`;
  $("catalogue-previous").disabled=catalogueState.page<=1;$("catalogue-next").disabled=catalogueState.page*catalogueState.pageSize>=total;
}
function catalogueSubmit(id,action){
  $(id).addEventListener("submit",async event=>{
    event.preventDefault();if(!authHas("catalogue.gerer")||catalogueState.site!==authState.site)return;
    const data=Object.fromEntries(new FormData(event.target)),org=authState.me.organisation.id_organisation,site=authState.site;
    $("security-operation").disabled=true;$("sites").disabled=true;
    $("catalogue-operation").disabled=true;$("catalogue-message").textContent="";
    try{const selected=await action(data);if(authState.me?.organisation.id_organisation!==org||authState.site!==site){catalogueReset();return;}await catalogueLoad(selected??catalogueState.selected);$("catalogue-message").textContent="Enregistrement réussi — catalogue resynchronisé.";}
    catch(e){$("catalogue-message").textContent=e.message;}
    finally{$("catalogue-operation").disabled=false;$("security-operation").disabled=false;$("sites").disabled=!authState.me?.contextes.length;authGate();}
  });
}
catalogueSubmit("catalogue-data-form",async d=>{
  const type=$("catalogue-data-type").value,id=$("catalogue-data-selected").value;
  const body={code:d.code,nom:d.nom,actif:Boolean(d.actif)};if(type==="categories")body.parent_id=d.parent_id||null;
  await catalogueRequest(`/${type}${id?"/"+id:""}`,id?"PUT":"POST",body);$("catalogue-data-selected").value="";
});
catalogueSubmit("catalogue-product-form",async d=>{
  const id=catalogueState.selected,body={nom:d.nom,categorie_id:d.categorie_id,forme_id:d.forme_id||null,laboratoire_id:d.laboratoire_id||null,description:d.description||null,actif:Boolean(d.actif)};
  if(!id)body.premier_conditionnement={code:d.premier_code,libelle:d.premier_libelle,actif:true};
  const result=await catalogueRequest(`/produits${id?"/"+id:""}`,id?"PUT":"POST",body);return result.id_produit;
});
catalogueSubmit("catalogue-packaging-form",async d=>{
  const id=catalogueState.packaging,path=id?`/conditionnements/${id}`:`/produits/${catalogueState.selected}/conditionnements`;
  const result=await catalogueRequest(path,id?"PUT":"POST",{code:d.code,libelle:d.libelle,actif:Boolean(d.actif)});catalogueState.packaging=result.id_conditionnement;
});
catalogueSubmit("catalogue-reference-form",async d=>{
  const id=$("catalogue-reference-selected").value,pid=$("catalogue-reference-packaging").value;
  await catalogueRequest(id?`/references/${id}`:`/conditionnements/${pid}/references`,id?"PUT":"POST",{type_reference:d.type_reference,valeur:d.valeur,actif:Boolean(d.actif)});
});
let catalogueSearchTimer;
$("catalogue-create").addEventListener("click",()=>{catalogueState.packaging="";catalogueOpen("","edit");});
$("catalogue-edit").addEventListener("click",()=>catalogueOpen(catalogueState.selected,"edit"));
$("catalogue-back").addEventListener("click",()=>{catalogueState.detailVersion++;Object.assign(catalogueState,{selected:"",detail:null,mode:"list",packaging:""});$("catalogue-editor-panel").hidden=true;$("catalogue-list-panel").hidden=false;catalogueGate();$("catalogue-search").focus();});
$("catalogue-search").addEventListener("input",()=>{clearTimeout(catalogueSearchTimer);catalogueState.version++;catalogueState.page=1;catalogueSearchTimer=setTimeout(()=>catalogueLoad("",false),250);});
for(const [id,delta] of [["catalogue-previous",-1],["catalogue-next",1]])$(id).addEventListener("click",()=>{catalogueState.page+=delta;catalogueLoad("",false);});
$("catalogue-page-size").addEventListener("change",()=>{catalogueState.pageSize=Number($("catalogue-page-size").value);catalogueState.page=1;catalogueLoad("",false);});
$("catalogue-data-type").addEventListener("change",()=>{$("catalogue-data-selected").value="";catalogueDataSelection();});
$("catalogue-data-selected").addEventListener("change",catalogueDataSelection);
$("catalogue-packaging-selected").addEventListener("change",cataloguePackagingSelection);
$("catalogue-reference-packaging").addEventListener("change",()=>catalogueReferenceSelection(true));
$("catalogue-reference-selected").addEventListener("change",()=>catalogueReferenceSelection());
