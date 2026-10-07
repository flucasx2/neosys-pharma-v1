"use strict";
const catalogueState={version:0,products:[],categories:[],formes:[],laboratoires:[],selected:"",packaging:"",site:""};
function catalogueRoot(){return `/api/catalogue/organisations/${authState.me.organisation.id_organisation}`;}
function catalogueReset(){catalogueState.version++;catalogueState.products=[];catalogueState.selected="";catalogueState.packaging="";catalogueState.site="";$("catalogue-products").replaceChildren();$("catalogue-detail").hidden=true;$("catalogue-message").textContent="";}
function catalogueGate(){
  const manage=authHas("catalogue.gerer");
  for(const id of ["catalogue-product-form","catalogue-data-form","catalogue-packaging-form","catalogue-reference-form"])$(id).hidden=!manage;
  $("catalogue-create").hidden=!manage;
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
function catalogueProductSelection(id){
  catalogueState.selected=id;const row=catalogueState.products.find(r=>r.id_produit===id),form=$("catalogue-product-form");
  $("catalogue-editor-title").textContent=row?"Modifier le produit":"Créer un produit";
  form.reset();form.elements.nom.value=row?.nom||"";form.elements.description.value=row?.description||"";form.elements.actif.checked=row?.actif??true;
  catalogueOptions("catalogue-category",catalogueState.categories,"id_categorie",row?.categorie_id,"Choisir une catégorie");
  catalogueOptions("catalogue-forme",catalogueState.formes,"id_forme",row?.forme_id);
  catalogueOptions("catalogue-laboratoire",catalogueState.laboratoires,"id_laboratoire",row?.laboratoire_id);
  $("catalogue-first-packaging").hidden=Boolean(row);
  for(const name of ["premier_code","premier_libelle"])form.elements[name].required=!row;
  $("catalogue-detail").hidden=!row;
  if(row){
    $("catalogue-ancestors").textContent="Catégorie et parents : "+row.categories.map(c=>c.nom).reverse().join(" → ");
    catalogueOptions("catalogue-packaging-selected",row.conditionnements,"id_conditionnement",catalogueState.packaging,"Nouveau conditionnement");
    cataloguePackagingSelection();
    $("catalogue-packagings").replaceChildren();
    for(const packaging of row.conditionnements){
      const item=document.createElement("li");item.textContent=`${packaging.code} · ${packaging.libelle}${packaging.actif?"":" (inactif)"}`;
      const refs=document.createElement("ul");
      for(const ref of packaging.references){const r=document.createElement("li");r.textContent=`${ref.type_reference} : ${ref.valeur}${ref.actif?"":" (archivée)"}`;refs.append(r);}
      item.append(refs);$("catalogue-packagings").append(item);
    }
  }
  catalogueGate();
}
function cataloguePackagingSelection(){
  catalogueState.packaging=$("catalogue-packaging-selected").value;
  const product=catalogueState.products.find(r=>r.id_produit===catalogueState.selected);
  const packaging=product?.conditionnements.find(c=>c.id_conditionnement===catalogueState.packaging);
  const form=$("catalogue-packaging-form");form.reset();form.elements.code.value=packaging?.code||"";form.elements.libelle.value=packaging?.libelle||"";form.elements.actif.checked=packaging?.actif??true;
  catalogueOptions("catalogue-reference-packaging",product?.conditionnements||[],"id_conditionnement",packaging?.id_conditionnement||product?.conditionnements[0]?.id_conditionnement,"Choisir un conditionnement");
  catalogueReferenceSelection(true);
}
function catalogueReferenceSelection(reset=false){
  const product=catalogueState.products.find(r=>r.id_produit===catalogueState.selected),pid=$("catalogue-reference-packaging").value;
  const refs=product?.conditionnements.find(c=>c.id_conditionnement===pid)?.references||[];
  const old=reset?"":$("catalogue-reference-selected").value;
  catalogueOptions("catalogue-reference-selected",refs.map(r=>({...r,nom:`${r.type_reference} : ${r.valeur}`})),"id_reference",old,"Nouvelle référence");
  const row=refs.find(r=>r.id_reference===old),form=$("catalogue-reference-form");
  form.elements.type_reference.value=row?.type_reference||"CIP7";form.elements.valeur.value=row?.valeur||"";form.elements.actif.checked=row?.actif??true;
}
async function catalogueLoad(selected=catalogueState.selected){
  catalogueGate();if(!authHas("catalogue.consulter"))return;
  const version=++catalogueState.version,site=authState.site;
  $("catalogue-operation").disabled=true;
  try{
    const [products,categories,formes,laboratoires]=await Promise.all(["produits","categories","formes","laboratoires"].map(p=>catalogueRequest("/"+p)));
    if(version!==catalogueState.version||site!==authState.site)return;
    Object.assign(catalogueState,{products,categories,formes,laboratoires,site});
    catalogueRender();catalogueDataSelection();catalogueProductSelection(products.some(p=>p.id_produit===selected)?selected:"");
  }catch(e){if(version===catalogueState.version)$("catalogue-message").textContent=e.message;}
  finally{if(version===catalogueState.version)$("catalogue-operation").disabled=false;}
}
function catalogueRender(){
  const search=$("catalogue-search").value.trim().toLocaleLowerCase();$("catalogue-products").replaceChildren();
  const products=catalogueState.products.filter(p=>!search||p.nom.toLocaleLowerCase().includes(search)||p.conditionnements.some(c=>c.references.some(r=>r.valeur.toLocaleLowerCase().includes(search))));
  for(const row of products){
    const tr=document.createElement("tr"),name=document.createElement("td"),button=document.createElement("button");button.type="button";button.className="secondary";button.textContent=row.nom;button.addEventListener("click",()=>catalogueProductSelection(row.id_produit));name.append(button);tr.append(name);
    for(const text of [row.categories[0].nom,String(row.conditionnements.length),row.actif?"Actif":"Inactif"]){const td=document.createElement("td");td.textContent=text;tr.append(td);}$("catalogue-products").append(tr);
  }
  $("catalogue-empty").hidden=Boolean(products.length);
}
function catalogueSubmit(id,action){
  $(id).addEventListener("submit",async event=>{
    event.preventDefault();if(!authHas("catalogue.gerer")||catalogueState.site!==authState.site)return;
    const data=Object.fromEntries(new FormData(event.target));
    $("catalogue-operation").disabled=true;$("catalogue-message").textContent="";
    try{const selected=await action(data);await catalogueLoad(selected??catalogueState.selected);$("catalogue-message").textContent="Enregistrement réussi — catalogue resynchronisé.";}
    catch(e){$("catalogue-message").textContent=e.message;}
    finally{$("catalogue-operation").disabled=false;}
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
$("catalogue-create").addEventListener("click",()=>catalogueProductSelection(""));
$("catalogue-search").addEventListener("input",catalogueRender);
$("catalogue-data-type").addEventListener("change",()=>{$("catalogue-data-selected").value="";catalogueDataSelection();});
$("catalogue-data-selected").addEventListener("change",catalogueDataSelection);
$("catalogue-packaging-selected").addEventListener("change",cataloguePackagingSelection);
$("catalogue-reference-packaging").addEventListener("change",()=>catalogueReferenceSelection(true));
$("catalogue-reference-selected").addEventListener("change",()=>catalogueReferenceSelection());
