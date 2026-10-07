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
  const select=$(id);select.replaceChildren(new Option(id==="sites"?"Choisir un site":id==="equipement-emplacement"?"Choisir un emplacement":"Choisir une organisation", ""));
  for(const item of values)select.add(new Option(item.nom_commercial||`${item.code} · ${item.nom}`,item.id_organisation||item.id_site||item.id_emplacement));
  select.value=selected;select.disabled=!values.length;
}
async function loadOrganisations(selected="") { options("organisations",await api("/organisations"),selected);await loadSites(); }
async function loadSites(selected="") {
  resetEquipements();
  options("sites",[]);$("emplacements").textContent="Sélectionnez un site.";$("emplacement-form").querySelector("button").disabled=true;
  const id=$("organisations").value;$("site-form").querySelector("button").disabled=!id;
  if(id)options("sites",await api(`/organisations/${id}/sites`),selected);
  await loadEmplacements();
}
async function loadEmplacements() {
  const selected=$("equipement-emplacement").value;
  resetEquipements();
  const id=$("sites").value;$("emplacement-form").querySelector("button").disabled=!id;
  $("emplacements").replaceChildren();
  if(!id){$("emplacements").textContent="Sélectionnez un site.";return;}
  const values=await api(`/sites/${id}/emplacements`);
  if($("sites").value!==id)return;
  for(const item of values){const li=document.createElement("li");li.textContent=`${item.code} · ${item.nom}${item.actif?"":" · Inactif"}`;$("emplacements").append(li);}
  options("equipement-emplacement",values,selected);
  await Promise.all([loadPostesCaisses(),loadCoffres()]);
}
$("organisations").addEventListener("change",()=>loadSites().catch(e=>message(e.message,true)));
$("sites").addEventListener("change",()=>loadEmplacements().catch(e=>message(e.message,true)));
function form(id, submit){$(id).addEventListener("submit",async event=>{event.preventDefault();const button=event.target.querySelector("button");button.disabled=true;try{await submit(Object.fromEntries(new FormData(event.target)));event.target.reset();message("Enregistrement effectué.");}catch(e){message(e.message,true);}finally{button.disabled=id==="site-form"?!$("organisations").value:["emplacement-form","coffre-form"].includes(id)?!$("sites").value:["poste-form","caisse-form"].includes(id)?!$("equipement-emplacement").value:false;}});}
form("organisation-form",async d=>{const created=await api("/organisations",{nom_commercial:d.nom_commercial,raison_sociale:d.raison_sociale,premier_site:{code:d.site_code,nom:d.site_nom,premier_emplacement:{code:d.emplacement_code,nom:d.emplacement_nom}}});await loadOrganisations(created.id_organisation);});
form("site-form",async d=>{const org=$("organisations").value;if(!org)throw new Error("Sélectionnez une organisation.");const created=await api(`/organisations/${org}/sites`,{code:d.code,nom:d.nom,adresse:d.adresse||null,telephone:d.telephone||null,email:d.email||null,premier_emplacement:{code:d.emplacement_code,nom:d.emplacement_nom}});await loadSites(created.id_site);});
form("emplacement-form",async d=>{const site=$("sites").value;if(!site)throw new Error("Sélectionnez un site.");await api(`/sites/${site}/emplacements`,d);await loadEmplacements();});
function list(id,values){$(id).replaceChildren();for(const item of values){const li=document.createElement("li");li.textContent=`${item.code} · ${item.nom}`;$(id).append(li);}if(!values.length)$(id).textContent="Aucun équipement enregistré.";}
function resetEquipements(){options("equipement-emplacement",[]);for(const id of ["poste-form","caisse-form","coffre-form"])$(id).querySelector("button").disabled=true;$("postes-list").textContent=$("caisses-list").textContent="Sélectionnez un emplacement.";$("coffres-list").textContent="Sélectionnez un site.";}
async function loadPostesCaisses(){const id=$("equipement-emplacement").value;for(const formId of ["poste-form","caisse-form"])$(formId).querySelector("button").disabled=!id;if(!id){$("postes-list").textContent=$("caisses-list").textContent="Sélectionnez un emplacement.";return;}const [postes,caisses]=await Promise.all([api(`/emplacements/${id}/postes-vente`),api(`/emplacements/${id}/caisses`)]);if($("equipement-emplacement").value!==id)return;list("postes-list",postes);list("caisses-list",caisses);}
async function loadCoffres(){const id=$("sites").value;$("coffre-form").querySelector("button").disabled=!id;if(!id)return;const values=await api(`/sites/${id}/coffres`);if($("sites").value===id)list("coffres-list",values);}
$("equipement-emplacement").addEventListener("change",()=>loadPostesCaisses().catch(e=>message(e.message,true)));
for(const [formId,path] of [["poste-form","postes-vente"],["caisse-form","caisses"]])form(formId,async d=>{const id=$("equipement-emplacement").value;if(!id)throw new Error("Sélectionnez un emplacement.");await api(`/emplacements/${id}/${path}`,d);await loadPostesCaisses();});
form("coffre-form",async d=>{const id=$("sites").value;if(!id)throw new Error("Sélectionnez un site.");await api(`/sites/${id}/coffres`,d);await loadCoffres();});
loadOrganisations().catch(e=>message(e.message,true));
