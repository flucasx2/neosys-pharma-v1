"use strict";
const securityState = {org:"", users:[], sites:[], roles:[], permissions:[], assignments:[], version:0};
const securityMessage = (text,error=false)=>{$("security-message").textContent=text;$("security-message").className=error?"error":"";};
async function securityApi(path,data,method="POST") {
  const response=await authFetch(base+path,data===undefined?{}:{method,headers:{"Content-Type":"application/json"},body:JSON.stringify(data)});
  const result=await response.json().catch(()=>null);
  if(!response.ok)throw new Error(typeof result?.detail==="string"?result.detail:"Vérifiez les champs et les rattachements sélectionnés.");
  if(data!==undefined&&/affectations|roles|utilisateurs/.test(path))await authRefresh();
  return result;
}
function securityOptions(id,items,key,label,selected="") {
  const select=$(id);select.replaceChildren(new Option("Choisir…",""));
  for(const item of items)select.add(new Option(label(item),item[key]));
  select.value=selected;select.disabled=!items.length;
}
function securityChecks(id,items,key,label,selected=[]) {
  const target=$(id);target.replaceChildren();
  for(const item of items){const row=document.createElement("label");row.className="check";const input=document.createElement("input");input.type="checkbox";input.value=item[key];input.checked=selected.includes(item[key]);row.append(input,document.createTextNode(label(item)));target.append(row);}
  if(!items.length)target.textContent="Aucun élément disponible.";
}
const securityIds=id=>Array.from($(id).querySelectorAll("input:checked"),input=>input.value);
function securityFill(id,item){for(const input of $(id).querySelectorAll("input")){if(input.type==="checkbox")input.checked=Boolean(item[input.name]);else input.value=item[input.name]||"";}}
function securityResetUser(){securityState.assignments=[];securityOptions("security-assignment",[],"id_affectation_site",()=>"");$("security-user-edit").hidden=true;$("security-assignment-create").querySelector("button").disabled=true;$("security-preview").querySelector("button").disabled=true;$("security-result").textContent="Sélectionnez un utilisateur et un site.";securityResetAssignment();}
function securityResetAssignment(){$("security-assignment-edit").hidden=true;for(const id of ["security-locations","security-roles"])$(id).querySelector("fieldset").disabled=true;$("security-location-checks").replaceChildren();$("security-role-checks").replaceChildren();$("security-scope-help").textContent="Sélectionnez une affectation.";}
async function securityLoadOrg(selectedUser="") {
  const version=++securityState.version;securityState.org=$("organisations").value;
  securityResetUser();securityOptions("security-user",[],"id_utilisateur",()=>"");securityOptions("security-role-selected",[],"id_role",()=>"");$("security-role-edit").querySelector("fieldset").disabled=true;$("security-edit-permissions").replaceChildren();
  for(const id of ["security-user-create","security-role-create"])$(id).querySelector("button").disabled=!securityState.org;
  securityOptions("security-new-site",[],"id_site",()=>"");securityOptions("security-preview-site",[],"id_site",()=>"");
  if(!securityState.org)return;
  const org=securityState.org;
  const [users,sites,roles,permissions]=await Promise.all([authHas("utilisateur.consulter")?securityApi(`/organisations/${org}/utilisateurs`):[],Promise.resolve(authState.me.contextes.filter(c=>c.site_id===authState.site).map(c=>({id_site:c.site_id,nom:c.nom}))),authHas("role.consulter")?securityApi(`/organisations/${org}/roles`):[],authHas("role.consulter")?securityApi("/permissions"):[]]);
  if(version!==securityState.version)return;
  Object.assign(securityState,{users,sites,roles,permissions});
  securityOptions("security-user",users,"id_utilisateur",u=>`${u.nom} · ${u.identifiant}${u.actif?"":" · Inactif"}`,selectedUser);
  for(const id of ["security-new-site","security-preview-site"])securityOptions(id,sites,"id_site",s=>s.nom);
  securityOptions("security-role-selected",roles,"id_role",r=>`${r.nom} · ${r.type_role}`);
  securityChecks("security-new-permissions",permissions,"id_permission",p=>`${p.nom} (${p.code})`);
  if(selectedUser)await securityLoadUser();
  authGate();
}
async function securityLoadUser(selectedAssignment="") {
  securityResetUser();const userId=$("security-user").value;if(!userId)return;
  const user=securityState.users.find(u=>u.id_utilisateur===userId);securityFill("security-user-edit",user);$("security-user-edit").hidden=false;
  $("security-assignment-create").querySelector("button").disabled=false;$("security-preview").querySelector("button").disabled=false;
  const assignments=await securityApi(`/utilisateurs/${userId}/affectations`);if($("security-user").value!==userId)return;
  securityState.assignments=assignments.filter(a=>a.site_id===authState.site);securityOptions("security-assignment",securityState.assignments,"id_affectation_site",a=>`${a.site_nom} · ${a.date_debut} → ${a.date_fin||"sans fin"}${a.actif?"":" · Inactive"}`,selectedAssignment);
  if(selectedAssignment)await securityLoadAssignment();
  authGate();
}
async function securityLoadAssignment(){
  securityResetAssignment();const id=$("security-assignment").value;if(!id)return;
  const assignment=securityState.assignments.find(a=>a.id_affectation_site===id);
  const locations=authState.me.contextes.find(c=>c.site_id===assignment.site_id)?.emplacements.map(e=>({...e,site_id:assignment.site_id}))||[];if($("security-assignment").value!==id)return;
  securityFill("security-assignment-edit",assignment);$("security-assignment-edit").hidden=false;
  securityChecks("security-location-checks",locations,"id_emplacement",e=>e.nom,assignment.emplacements.map(e=>e.id_emplacement));
  securityChecks("security-role-checks",securityState.roles,"id_role",r=>`${r.nom} · ${r.type_role}`,assignment.roles.map(r=>r.id_role));
  for(const form of ["security-locations","security-roles"])$(form).querySelector("fieldset").disabled=false;
  $("security-scope-help").textContent=`Affectation au site ${assignment.site_nom}`;$("security-preview-site").value=assignment.site_id;
  authGate();
}
function securityLoadRole(){const role=securityState.roles.find(r=>r.id_role===$("security-role-selected").value);securityChecks("security-edit-permissions",role?securityState.permissions:[],"id_permission",p=>`${p.nom} (${p.code})`,role?.permissions.map(p=>p.id_permission)||[]);$("security-role-edit").querySelector("fieldset").disabled=!role||role.type_role==="SYSTEME";authGate();}
async function securityPreview(){
  const user=$("security-user").value,site=$("security-preview-site").value,jour=$("security-preview-date").value;
  if(site!==authState.site)throw new Error("Choisissez d’abord ce site dans le contexte courant en haut de page.");
  if(!user||!site||!jour)throw new Error("Sélectionnez un utilisateur, un site et une date.");
  const result=await securityApi(`/utilisateurs/${user}/sites/${site}/permissions?jour=${jour}`);
  if($("security-user").value!==user||$("security-preview-site").value!==site||$("security-preview-date").value!==jour)return;
  const target=$("security-result");target.replaceChildren();const p=document.createElement("p");p.textContent=`${result.affectations_effectives.length} affectation(s) effective(s).`;target.append(p);
  const heading=document.createElement("h3");heading.textContent="Permissions au niveau du site";target.append(heading);
  const ul=document.createElement("ul");for(const code of result.permissions_site){const li=document.createElement("li");li.textContent=code;ul.append(li);}if(!result.permissions_site.length)ul.textContent="Aucune permission effective.";target.append(ul);
  for(const location of result.emplacements){const h=document.createElement("h3");h.textContent=location.nom;const text=document.createElement("p");text.textContent=location.permissions.join(", ")||"Aucune permission effective.";target.append(h,text);}
}
function securityForm(id,action,reset=false){$(id).addEventListener("submit",async event=>{event.preventDefault();const data=Object.fromEntries(new FormData(event.target));const button=event.target.querySelector("button");button.disabled=true;$("security-operation").disabled=true;$("sites").disabled=true;try{await action(data);if(reset)event.target.reset();securityMessage("Enregistrement effectué.");}catch(error){securityMessage(error.message,true);}finally{button.disabled=false;$("security-operation").disabled=false;$("sites").disabled=!authState.me?.contextes.length;authGate();}});}
securityForm("security-user-create",async d=>{if(!securityState.org)throw new Error("Sélectionnez une organisation.");const user=await securityApi(`/organisations/${securityState.org}/utilisateurs`,{identifiant:d.identifiant,nom:d.nom,email:d.email||null});await securityLoadOrg(user.id_utilisateur);},true);
securityForm("security-user-edit",async d=>{const id=$("security-user").value;await securityApi(`/utilisateurs/${id}`,{nom:d.nom,email:d.email||null,actif:d.actif==="on"},"PUT");await securityLoadOrg(id);});
securityForm("security-assignment-create",async d=>{const id=$("security-user").value;if(!id)throw new Error("Sélectionnez un utilisateur.");const assignment=await securityApi(`/utilisateurs/${id}/affectations`,{site_id:d.site_id,date_debut:d.date_debut,date_fin:d.date_fin||null});await securityLoadUser(assignment.id_affectation_site);},true);
securityForm("security-assignment-edit",async d=>{const id=$("security-assignment").value;await securityApi(`/affectations/${id}`,{date_debut:d.date_debut,date_fin:d.date_fin||null,actif:d.actif==="on"},"PUT");await securityLoadUser(id);});
for(const [formId,checks,path] of [["security-locations","security-location-checks","emplacements"],["security-roles","security-role-checks","roles"]])securityForm(formId,async()=>{const id=$("security-assignment").value;await securityApi(`/affectations/${id}/${path}`,{ids:securityIds(checks)},"PUT");await securityLoadUser(id);$("security-result").textContent="Les affectations ont changé. Vérifiez à nouveau les permissions.";});
securityForm("security-role-create",async d=>{if(!securityState.org)throw new Error("Sélectionnez une organisation.");const user=$("security-user").value;await securityApi(`/organisations/${securityState.org}/roles`,{code:d.code,nom:d.nom,permission_ids:securityIds("security-new-permissions")});await securityLoadOrg(user);},true);
securityForm("security-role-edit",async()=>{const id=$("security-role-selected").value,user=$("security-user").value;await securityApi(`/roles/${id}/permissions`,{ids:securityIds("security-edit-permissions")},"PUT");await securityLoadOrg(user);$("security-role-selected").value=id;securityLoadRole();});
securityForm("security-preview",securityPreview);
for(const [id,action] of [["security-user",securityLoadUser],["security-assignment",securityLoadAssignment],["security-role-selected",securityLoadRole],["organisations",securityLoadOrg]])$(id).addEventListener("change",()=>Promise.resolve().then(()=>action()).catch(e=>securityMessage(e.message,true)));
document.addEventListener("structure-updated",()=>securityLoadOrg().catch(e=>securityMessage(e.message,true)));
$("security-preview-date").value=new Intl.DateTimeFormat("en-CA",{timeZone:"Africa/Libreville",year:"numeric",month:"2-digit",day:"2-digit"}).format(new Date());
