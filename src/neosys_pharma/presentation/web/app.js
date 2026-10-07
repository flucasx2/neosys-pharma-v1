"use strict";
const structureState={sites:[],locations:[],site:"",version:0,pending:null};
const $ = id => document.getElementById(id);
const base = "/api/organisation";
const message = (text, error=false) => { $("message").textContent=text; $("message").className=error?"error":""; };
async function api(path, data) {
  const response=await authFetch(base+path, data?{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(data)}:{});
  const result=await response.json().catch(()=>null);
  if(!response.ok) throw new Error(typeof result?.detail==="string"?result.detail:response.status===422?"Vérifiez les champs obligatoires et leur longueur.":"La base est indisponible. Vérifiez la configuration et les migrations.");
  return result;
}
function options(id, values, selected="") {
  const select=$(id);select.replaceChildren(new Option(["sites","structure-site"].includes(id)?"Choisir un site":id==="equipement-emplacement"?"Choisir un emplacement":"Choisir une organisation", ""));
  for(const item of values)select.add(new Option(item.nom_commercial||`${item.code} · ${item.nom}`,item.id_organisation||item.id_site||item.id_emplacement));
  select.value=selected;select.disabled=!values.length;
}
async function loadOrganisations(selected="") { options("organisations",authState.me?[authState.me.organisation]:[],selected);await loadSites();await loadStructure(); }
async function loadSites(selected="") {
  resetEquipements();
  options("sites",[]);$("emplacements").textContent="Sélectionnez un site.";$("emplacement-form").querySelector("button").disabled=true;
  const id=$("organisations").value;$("site-form").querySelector("button").disabled=!id;
  if(id)options("sites",await api(`/organisations/${id}/sites`),selected||authState.site);
  await loadEmplacements();
}
let emplacementVersion=0;
async function loadEmplacements(preferred="") {
  const version=++emplacementVersion;
  const selected=preferred||$("equipement-emplacement").value;
  resetEquipements();
  const id=$("sites").value;$("emplacement-form").querySelector("button").disabled=!id;

  if(!id||!authHas("organisation.consulter"))return;
  const values=await api(`/sites/${id}/emplacements`);
  if(version!==emplacementVersion||$("sites").value!==id)return;
  options("equipement-emplacement",values,values.some(e=>e.id_emplacement===selected)?selected:values[0]?.id_emplacement||"");
  await Promise.all([loadPostesCaisses(),loadCoffres()]);authGate();
}
$("organisations").addEventListener("change",()=>loadSites().catch(e=>message(e.message,true)));
$("sites").addEventListener("change",async()=>{
  authState.site=$("sites").value;$("security-operation").disabled=true;authGate();
  try{await loadEmplacements();await loadStructure(authState.site);await securityLoadOrg();}
  catch(e){message(e.message,true);}
  finally{$("security-operation").disabled=false;authGate();}
});
function form(id, submit){$(id).addEventListener("submit",async event=>{event.preventDefault();const button=event.target.querySelector("button");button.disabled=true;try{await submit(Object.fromEntries(new FormData(event.target)));event.target.reset();message("Enregistrement effectué.");}catch(e){message(e.message,true);}finally{authGate();button.disabled=id==="site-form"?!$("organisations").value:id==="emplacement-form"?!structureState.site:id==="coffre-form"?!$("sites").value:["poste-form","caisse-form"].includes(id)?!$("equipement-emplacement").value:false;}});}
form("organisation-form",async d=>{const created=await api("/organisations",{nom_commercial:d.nom_commercial,raison_sociale:d.raison_sociale,premier_site:{code:d.site_code,nom:d.site_nom,premier_emplacement:{code:d.emplacement_code,nom:d.emplacement_nom}}});await loadOrganisations(created.id_organisation);});
form("site-form",async d=>{
  const org=$("organisations").value;if(!org)throw new Error("Sélectionnez une organisation.");
  const created=await api(`/organisations/${org}/sites`,{code:d.code,nom:d.nom,adresse:d.adresse||null,telephone:d.telephone||null,email:d.email||null,premier_emplacement:{code:d.emplacement_code,nom:d.emplacement_nom}});
  await synchronizeStructure(created.id_site);await securityLoadOrg();
  creationFeedback("site",created);
});
form("emplacement-form",async d=>{
  const site=structureState.site;if(!site)throw new Error("Sélectionnez un site à administrer.");
  const created=await api(`${structurePrefix()}/sites/${site}/emplacements`,d);
  await synchronizeStructure(site,created.id_emplacement);await securityLoadOrg();
  creationFeedback("emplacement",created);
});
function structurePrefix(){return authHas("organisation.gerer")?"/administration":"";}
function canManageAssignments(){return authHas("organisation.gerer")&&authHas("affectation.gerer")&&authHas("utilisateur.consulter");}
async function loadStructure(preferred=""){
  const version=++structureState.version,org=authState.me?.organisation.id_organisation;
  if(!org||!authHas("organisation.consulter"))return;
  const values=await api(`${structurePrefix()}/organisations/${org}/sites`);
  if(version!==structureState.version)return;
  structureState.sites=values;
  const selected=preferred||structureState.site||authState.site;
  structureState.site=values.some(s=>s.id_site===selected)?selected:values[0]?.id_site||"";
  options("structure-site",values,structureState.site);
  await loadStructureLocations();
}
async function loadStructureLocations(){
  const site=structureState.site,version=structureState.version;
  const values=site?await api(`${structurePrefix()}/sites/${site}/emplacements`):[];
  if(site!==structureState.site||version!==structureState.version)return;
  structureState.locations=values;$("emplacements").replaceChildren();
  for(const item of values){const li=document.createElement("li");li.textContent=`${item.code} · ${item.nom}`;$("emplacements").append(li);}
  $("emplacement-form").querySelector("button").disabled=!site;authGate();
}
async function synchronizeStructure(preferredSite="",preferredLocation=""){
  await authRefresh();if(!authState.me)return;
  const currentLocation=$("equipement-emplacement").value;
  const context=authState.me.contextes.find(c=>c.site_id===preferredSite);
  if(!preferredLocation&&structureState.pending?.kind==="emplacement"&&structureState.pending.site===preferredSite&&context?.emplacements.some(e=>e.id_emplacement===structureState.pending.id))preferredLocation=structureState.pending.id;
  if(context&&(!preferredLocation||context.emplacements.some(e=>e.id_emplacement===preferredLocation)))authState.site=preferredSite;
  await loadSites(authState.site);
  await loadEmplacements(preferredLocation&&authState.site===preferredSite?preferredLocation:currentLocation);
  await loadStructure(preferredSite);if(structureState.pending)creationFeedback(structureState.pending.kind,structureState.pending.created);authGate();
}
function creationFeedback(kind,created){
  structureState.pending={kind,created,id:created.id_site||created.id_emplacement,site:kind==="site"?created.id_site:created.site_id};
  const context=authState.me.contextes.find(c=>c.site_id===structureState.pending.site);
  const accessible=kind==="site"?Boolean(context):Boolean(context?.emplacements.some(e=>e.id_emplacement===created.id_emplacement));
  $("creation-status").textContent=`${kind==="site"?"Site créé":"Emplacement créé"}${accessible?"":" — accès à attribuer"} : ${created.code} · ${created.nom}`;
  $("creation-feedback").hidden=false;$("creation-assign").hidden=!canManageAssignments();
}
$("structure-site").addEventListener("change",()=>{structureState.site=$("structure-site").value;structureState.version++;loadStructureLocations().catch(e=>message(e.message,true));});
$("creation-assign").addEventListener("click",async()=>{
  if(!canManageAssignments())return;
  try{
    await securityLoadOrg(authState.me.utilisateur.id_utilisateur);
    if(structureState.pending)$("security-new-site").value=structureState.pending.site;
    $("security-assignment-create").closest("details").open=true;shellNavigate("affectations");
  }catch(e){securityMessage(e.message,true);}
});
function list(id,values){$(id).replaceChildren();for(const item of values){const li=document.createElement("li");li.textContent=`${item.code} · ${item.nom}`;$(id).append(li);}if(!values.length)$(id).textContent="Aucun équipement enregistré.";}
function resetEquipements(){options("equipement-emplacement",[]);for(const id of ["poste-form","caisse-form","coffre-form"])$(id).querySelector("button").disabled=true;$("postes-list").textContent=$("caisses-list").textContent="Sélectionnez un emplacement.";$("coffres-list").textContent="Sélectionnez un site.";}
async function loadPostesCaisses(){const id=$("equipement-emplacement").value;for(const formId of ["poste-form","caisse-form"])$(formId).querySelector("button").disabled=!id;if(!id||!authHas("organisation.consulter",id)){$("postes-list").textContent=$("caisses-list").textContent="Sélectionnez un emplacement.";return;}const [postes,caisses]=await Promise.all([api(`/emplacements/${id}/postes-vente`),api(`/emplacements/${id}/caisses`)]);if($("equipement-emplacement").value!==id)return;list("postes-list",postes);list("caisses-list",caisses);}
async function loadCoffres(){const id=$("sites").value;$("coffre-form").querySelector("button").disabled=!id;if(!id||!authHas("organisation.consulter"))return;const values=await api(`/sites/${id}/coffres`);if($("sites").value===id)list("coffres-list",values);}
$("equipement-emplacement").addEventListener("change",()=>loadPostesCaisses().catch(e=>message(e.message,true)));
for(const [formId,path] of [["poste-form","postes-vente"],["caisse-form","caisses"]])form(formId,async d=>{const id=$("equipement-emplacement").value;if(!id)throw new Error("Sélectionnez un emplacement.");await api(`/emplacements/${id}/${path}`,d);await loadPostesCaisses();});
form("coffre-form",async d=>{const id=$("sites").value;if(!id)throw new Error("Sélectionnez un site.");await api(`/sites/${id}/coffres`,d);await loadCoffres();});
