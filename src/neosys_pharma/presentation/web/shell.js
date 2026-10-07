"use strict";
// Navigation de présentation uniquement ; authHas reste la source des droits UI.
const shellViews={
  dashboard:{title:"Tableau de bord"},
  structure:{title:"Organisation, sites & emplacements",allowed:()=>authHas("organisation.consulter")||authHas("organisation.gerer")},
  equipements:{title:"Postes de vente, caisses & coffres",allowed:()=>authHas("organisation.consulter")||authHas("organisation.gerer")},
  utilisateurs:{title:"Utilisateurs",allowed:()=>authHas("utilisateur.consulter")||authHas("utilisateur.gerer")},
  affectations:{title:"Affectations",allowed:()=>authHas("utilisateur.consulter")},
  roles:{title:"Rôles & Permissions",allowed:()=>authHas("role.consulter")||authHas("role.gerer")}
};
const shellState={loading:true,view:"dashboard",lastAdmin:"structure"};
function shellAllowed(view){return Boolean(authState.me&&shellViews[view]&&(view==="dashboard"||shellViews[view].allowed()));}
function shellMobile(open){
  $("sidebar").classList.toggle("is-open",open);
  $("sidebar-backdrop").hidden=!open;
  $("sidebar-toggle").setAttribute("aria-expanded",String(open));
  if(open)$("sidebar-close").focus();
}
function shellReset(){
  shellState.loading=false;$("app-loading").hidden=true;
  shellState.view="dashboard";shellState.lastAdmin="structure";
  $("app-shell").hidden=true;$("dashboard").hidden=true;$("administration").hidden=true;
  shellMobile(false);history.replaceState(null,"",location.pathname+location.search);
  document.title="NeoSys Pharma · Connexion";
}
function shellNavigate(view,{focus=true,remember=true}={}){
  if($("security-operation").disabled)return;
  shellState.view=shellAllowed(view)?view:"dashboard";
  if(shellState.view!=="dashboard")shellState.lastAdmin=shellState.view;
  if(remember)history.replaceState(null,"",shellState.view==="dashboard"?"#tableau-de-bord":`#administration/${shellState.view}`);
  shellSync();shellMobile(false);
  if(focus){$("module-title").focus();window.scrollTo({top:0,behavior:"instant"});}
}
function shellStart(){
  const requested=location.hash.startsWith("#administration/")?location.hash.split("/")[1]:"dashboard";
  shellNavigate(requested,{focus:false});
}
function shellSync(){
  if(!authState.me||shellState.loading)return;
  $("app-shell").hidden=false;
  if(!shellAllowed(shellState.view))shellState.view="dashboard";
  const view=shellState.view,isAdmin=view!=="dashboard";
  $("dashboard").hidden=isAdmin;$("administration").hidden=!isAdmin;
  $("module-title").textContent=shellViews[view].title;
  $("module-eyebrow").textContent=isAdmin?"ADMINISTRATION":"ESPACE DE GESTION";
  document.title=`NeoSys Pharma · ${shellViews[view].title}`;
  $("identity-avatar").textContent=authState.me.utilisateur.nom.trim().split(/\s+/).slice(0,2).map(x=>x[0]).join("").toUpperCase();
  const adminViews=Object.keys(shellViews).filter(v=>v!=="dashboard"&&shellAllowed(v));
  $("nav-administration").hidden=!adminViews.length;
  $("admin-subnav").hidden=!adminViews.length;
  for(const button of document.querySelectorAll("[data-view]")){
    const id=button.dataset.view;button.hidden=!shellAllowed(id);
    if(id===view)button.setAttribute("aria-current","page");else button.removeAttribute("aria-current");
  }
  if(isAdmin)$("nav-administration").setAttribute("aria-current","page");else $("nav-administration").removeAttribute("aria-current");
  for(const pane of document.querySelectorAll("[data-pane]"))pane.hidden=pane.dataset.pane!==view;
  $("user-context").hidden=!isAdmin||!["utilisateurs","affectations"].includes(view)||!authHas("utilisateur.consulter");
  $("location-context").hidden=!authHas("organisation.consulter")||!authContext()?.emplacements.length;
  const siteValues=authState.me.contextes.map(c=>({id_site:c.site_id,nom:c.nom,code:c.code}));
  const currentSiteIds=Array.from($("sites").options).map(o=>o.value).filter(Boolean);
  if(JSON.stringify(currentSiteIds)!==JSON.stringify(siteValues.map(s=>s.id_site)))options("sites",siteValues,authState.site);
  $("sites").value=authState.site;
  if($("organisations").value!==authState.me.organisation.id_organisation)options("organisations",[authState.me.organisation],authState.me.organisation.id_organisation);
  $("organisations").disabled=true;
  $("sites").disabled=$("security-operation").disabled||!siteValues.length;
  const allowedLocations=new Set(authContext()?.emplacements.map(e=>e.id_emplacement)||[]);
  for(const option of Array.from($("equipement-emplacement").options))if(option.value&&!allowedLocations.has(option.value))option.remove();
  $("equipement-emplacement").disabled=$("security-operation").disabled||!allowedLocations.size;
  const context=authContext(),locationId=$("equipement-emplacement").value;
  $("stat-sites").textContent=authState.me.contextes.length;
  $("stat-locations").textContent=context?.emplacements.length||0;
  $("stat-permissions").textContent=context?.permissions_site.length||0;
  $("dashboard-organisation").textContent=authState.me.organisation.nom_commercial;
  $("dashboard-site").textContent=context?`${context.code} · ${context.nom}`:siteValues.length?"Sélectionnez un site":"Aucun site accessible";
  $("dashboard-location").textContent=context?.emplacements.find(e=>e.id_emplacement===locationId)?.nom||"Aucun emplacement sélectionné";
  $("dashboard-date").textContent=new Intl.DateTimeFormat("fr-FR",{timeZone:"Africa/Libreville",day:"numeric",month:"long",year:"numeric"}).format(new Date());
  $("organisation-details").textContent=authState.me.organisation.nom_commercial;
  const adminSite=structureState.sites.find(s=>s.id_site===structureState.site);
  $("site-details").textContent=adminSite?`${adminSite.code} · ${adminSite.nom}`:"Sélectionnez un site à administrer.";
  const user=securityState.users.find(u=>u.id_utilisateur===$("security-user").value);
  $("user-summary").textContent=user?`${user.nom} · ${user.identifiant}${user.email?" · "+user.email:""} · ${user.actif?"Actif":"Inactif"}`:"Sélectionnez un utilisateur dans la barre ci-dessus.";
  // Do not replace focused quick-link buttons during a permissions refresh.
  const links=$("quick-links");
  for(const id of Object.keys(shellViews).filter(id=>id!=="dashboard")){
    const button=links.querySelector(`[data-view="${id}"]`);
    if(button)button.hidden=!shellAllowed(id);
  }
  $("shortcuts-empty").hidden=Boolean(adminViews.length);
}
for(const [view,info] of Object.entries(shellViews)){
  if(view==="dashboard")continue;
  const button=document.createElement("button");button.type="button";button.dataset.view=view;
  button.append(document.createTextNode(info.title));const arrow=document.createElement("span");arrow.textContent="→";arrow.setAttribute("aria-hidden","true");button.append(arrow);$("quick-links").append(button);
}
for(const button of document.querySelectorAll("[data-view]"))button.addEventListener("click",()=>shellNavigate(button.dataset.view));
$("nav-administration").addEventListener("click",()=>shellNavigate(shellAllowed(shellState.lastAdmin)?shellState.lastAdmin:Object.keys(shellViews).find(v=>v!=="dashboard"&&shellAllowed(v))));
$("sidebar-toggle").addEventListener("click",()=>shellMobile(!$("sidebar").classList.contains("is-open")));
for(const id of ["sidebar-close","sidebar-backdrop"])$(id).addEventListener("click",()=>{shellMobile(false);$("sidebar-toggle").focus();});
document.addEventListener("keydown",event=>{
  if(!$("sidebar").classList.contains("is-open"))return;
  if(event.key==="Escape"){shellMobile(false);$("sidebar-toggle").focus();}
  if(event.key==="Tab"){
    const buttons=Array.from($("sidebar").querySelectorAll("button")).filter(b=>!b.hidden&&b.getClientRects().length);
    const first=buttons[0],last=buttons.at(-1);
    if(event.shiftKey&&document.activeElement===first){event.preventDefault();last.focus();}
    else if(!event.shiftKey&&document.activeElement===last){event.preventDefault();first.focus();}
  }
});
window.addEventListener("hashchange",()=>{if(authState.me)shellStart();});
window.matchMedia("(min-width:901px)").addEventListener("change",event=>{if(event.matches)shellMobile(false);});
$("equipement-emplacement").addEventListener("change",shellSync);
// Une sauvegarde d'accès garde son contexte et sa vue jusqu'à sa réponse.
new MutationObserver(()=>{
  const busy=$("security-operation").disabled;
  for(const button of document.querySelectorAll("[data-view],#nav-administration"))button.disabled=busy;
}).observe($("security-operation"),{attributes:true,attributeFilter:["disabled"]});
