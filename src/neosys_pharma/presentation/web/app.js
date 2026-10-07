"use strict";
const $ = id => document.getElementById(id);
const base = "/api/organisation";
const message = (text, error=false) => { $("message").textContent=text; $("message").className=error?"error":""; };
async function api(path, data) {
  const response=await fetch(base+path, data?{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(data)}:{});
  const result=await response.json().catch(()=>null);
  if(!response.ok) throw new Error(typeof result?.detail==="string"?result.detail:response.status===422?"Vérifiez les champs obligatoires et leur longueur.":"La base est indisponible. Vérifiez la configuration et les migrations.");
  return result;
}
function options(id, values, selected="") {
  const select=$(id);select.replaceChildren(new Option(id==="sites"?"Choisir un site":"Choisir une organisation", ""));
  for(const item of values)select.add(new Option(item.nom_commercial||`${item.code} · ${item.nom}`,item.id_organisation||item.id_site));
  select.value=selected;select.disabled=!values.length;
}
async function loadOrganisations(selected="") { options("organisations",await api("/organisations"),selected);await loadSites(); }
async function loadSites(selected="") {
  options("sites",[]);$("emplacements").textContent="Sélectionnez un site.";$("emplacement-form").querySelector("button").disabled=true;
  const id=$("organisations").value;$("site-form").querySelector("button").disabled=!id;
  if(id)options("sites",await api(`/organisations/${id}/sites`),selected);
  await loadEmplacements();
}
async function loadEmplacements() {
  const id=$("sites").value;$("emplacement-form").querySelector("button").disabled=!id;
  $("emplacements").replaceChildren();
  if(!id){$("emplacements").textContent="Sélectionnez un site.";return;}
  for(const item of await api(`/sites/${id}/emplacements`)){const li=document.createElement("li");li.textContent=`${item.code} · ${item.nom}${item.actif?"":" · Inactif"}`;$("emplacements").append(li);}
}
$("organisations").addEventListener("change",()=>loadSites().catch(e=>message(e.message,true)));
$("sites").addEventListener("change",()=>loadEmplacements().catch(e=>message(e.message,true)));
function form(id, submit){$(id).addEventListener("submit",async event=>{event.preventDefault();const button=event.target.querySelector("button");button.disabled=true;try{await submit(Object.fromEntries(new FormData(event.target)));event.target.reset();message("Enregistrement effectué.");}catch(e){message(e.message,true);}finally{button.disabled=id==="site-form"?!$("organisations").value:id==="emplacement-form"?!$("sites").value:false;}});}
form("organisation-form",async d=>{const created=await api("/organisations",{nom_commercial:d.nom_commercial,raison_sociale:d.raison_sociale,premier_site:{code:d.site_code,nom:d.site_nom,premier_emplacement:{code:d.emplacement_code,nom:d.emplacement_nom}}});await loadOrganisations(created.id_organisation);});
form("site-form",async d=>{const org=$("organisations").value;if(!org)throw new Error("Sélectionnez une organisation.");const created=await api(`/organisations/${org}/sites`,{code:d.code,nom:d.nom,adresse:d.adresse||null,telephone:d.telephone||null,email:d.email||null,premier_emplacement:{code:d.emplacement_code,nom:d.emplacement_nom}});await loadSites(created.id_site);});
form("emplacement-form",async d=>{const site=$("sites").value;if(!site)throw new Error("Sélectionnez un site.");await api(`/sites/${site}/emplacements`,d);await loadEmplacements();});
loadOrganisations().catch(e=>message(e.message,true));
