"use strict";
const authState={me:null,site:""};
function authContext(){return authState.me?.contextes.find(c=>c.site_id===authState.site);}
function authHas(permission,location=""){const context=authContext();return location?Boolean(context?.emplacements.find(e=>e.id_emplacement===location)?.permissions.includes(permission)):Boolean(context?.permissions_site.includes(permission));}
function authHeaders(){const headers={"Content-Type":"application/json"};const csrf=document.cookie.split("; ").find(x=>x.startsWith("neosys_csrf="))?.split("=")[1];if(csrf)headers["X-CSRF-Token"]=decodeURIComponent(csrf);if(authState.site)headers["X-Site-ID"]=authState.site;return headers;}
async function authFetch(url,options={}){const response=await fetch(url,{...options,headers:{...authHeaders(),...options.headers}});if(response.status===401&&authState.me){authReset();$("login-message").textContent="Session expirée. Reconnectez-vous.";}return response;}
function authReset(){structureState.version++;structureState.sites=[];structureState.locations=[];structureState.site="";structureState.pending=null;$("creation-feedback").hidden=true;$("creation-assign").hidden=true;shellReset();authState.me=null;authState.site="";securityState.version++;securityState.users=[];securityState.assignments=[];securityState.roles=[];securityState.org="";options("sites",[]);options("organisations",[]);$("message").textContent="";$("security-message").textContent="";$("identity-name").textContent="";$("administration").hidden=true;$("login-panel").hidden=false;$("session-panel").hidden=true;$("no-access").hidden=true;$("security-result").textContent="";$("security-user").replaceChildren();$("security-assignment").replaceChildren();$("security-location-checks").replaceChildren();$("security-role-checks").replaceChildren();$("emplacements").replaceChildren();resetEquipements();}
function authGate(){
  const map={"site-form":"organisation.gerer","emplacement-form":"organisation.gerer","coffre-form":"organisation.gerer","security-user-create":"utilisateur.gerer","security-user-edit":"utilisateur.gerer","security-assignment-create":"affectation.gerer","security-assignment-edit":"affectation.gerer","security-locations":"affectation.gerer","security-roles":"affectation.gerer","security-role-create":"role.gerer","security-password":"utilisateur.gerer","security-preview":"utilisateur.consulter"};
  for(const [id,permission] of Object.entries(map)){const form=$(id);form.closest("details")?form.closest("details").hidden=!authHas(permission):form.hidden=!authHas(permission)||(id==="security-user-edit"&&!$("security-user").value)||(id==="security-assignment-edit"&&!$("security-assignment").value);}
  $("organisation-form").closest("details").hidden=true;
  $("security-role-create").closest("article").hidden=!authHas("role.gerer");
  for(const id of ["poste-form","caisse-form"])$(id).closest("details").hidden=!authHas("organisation.gerer",$("equipement-emplacement").value);
  $("security-user").closest("label").hidden=!authHas("utilisateur.consulter");
  $("security-role-selected").closest("label").hidden=!authHas("role.consulter");
  $("security-new-permissions").closest("fieldset").hidden=!authHas("role.consulter");
  $("security-assignment").closest("label").hidden=!authHas("utilisateur.consulter");
  $("security-role-edit").hidden=!authHas("role.consulter");
  const role=securityState.roles.find(r=>r.id_role===$("security-role-selected").value);
  const editable=authHas("role.gerer")&&role?.type_role==="PERSONNALISE";
  $("security-role-edit").querySelector("fieldset").disabled=!editable;
  $("security-role-edit").querySelector("button").hidden=!editable;
  $("creation-assign").hidden=!canManageAssignments();
  shellSync();
}
async function authRefresh(){
  const response=await authFetch("/api/auth/me");if(!response.ok){authReset();return false;}
  authState.me=await response.json();if(!authState.me.contextes.some(c=>c.site_id===authState.site))authState.site=authState.me.contextes[0]?.site_id||"";
  $("login-panel").hidden=true;$("session-panel").hidden=false;$("identity-name").textContent=`${authState.me.utilisateur.nom} · ${authState.me.organisation.nom_commercial}`;
  $("no-access").hidden=Boolean(authState.site);authGate();
  return Boolean(authState.site);
}
async function authLoad(){
  shellState.loading=true;$("app-shell").hidden=true;$("login-panel").hidden=true;$("app-loading").hidden=false;
  try{
    if(await authRefresh()){await loadOrganisations(authState.me.organisation.id_organisation);await securityLoadOrg();authGate();}
  }finally{
    shellState.loading=false;$("app-loading").hidden=true;
    if(authState.me)shellStart();else $("login-panel").hidden=false;
  }
}
$("login-form").addEventListener("submit",async event=>{event.preventDefault();const form=event.target;const d=Object.fromEntries(new FormData(form));const button=form.querySelector("button");button.disabled=true;try{const response=await fetch("/api/auth/login",{method:"POST",headers:{"Content-Type":"application/json","X-NeoSys-Request":"1"},body:JSON.stringify({organisation_id:d.organisation_id,identifiant:d.identifiant,password:d.password})});const result=await response.json();form.elements.password.value="";if(!response.ok)throw new Error(typeof result.detail==="string"?result.detail:"Vérifiez les informations de connexion.");$("login-message").textContent="";await authLoad();}catch(e){$("login-message").textContent=e.message;}finally{button.disabled=false;}});
$("logout-button").addEventListener("click",async()=>{const response=await authFetch("/api/auth/logout",{method:"POST"});if(response.ok||response.status===401){authReset();$("login-form").reset();}else $("session-message").textContent="La déconnexion a échoué. Réessayez.";});
$("equipement-emplacement").addEventListener("change",authGate);
new MutationObserver(()=>{if(authState.me)authGate();}).observe($("security-user"),{childList:true});
securityForm("security-password",async d=>{const id=$("security-user").value;if(!id)throw new Error("Sélectionnez un utilisateur.");const response=await authFetch(`/api/auth/utilisateurs/${id}/password`,{method:"PUT",body:JSON.stringify({password:d.password})});if(!response.ok){const result=await response.json();throw new Error(typeof result.detail==="string"?result.detail:"Mot de passe invalide.");}if(id===authState.me?.utilisateur.id_utilisateur)authReset();},true);
authLoad().catch(e=>{$("login-message").textContent=e.message;authReset();});
