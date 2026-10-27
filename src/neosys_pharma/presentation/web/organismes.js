"use strict";
const organismesState = {scope:"", epoch:0, listVersion:0, detailVersion:0, page:1, selected:null, busy:false, pending:null};
const organismesScope = () => authState.me ? [authState.me.organisation.id_organisation,authState.site,authState.me.utilisateur.id_utilisateur].join(":") : "";
const organismesManage = () => authHas("tiers_payant.organisme.gerer");
const organismesRead = () => organismesManage() || authHas("tiers_payant.consulter");
function organismesReset() {
  organismesState.epoch++; organismesState.listVersion++; organismesState.detailVersion++;
  Object.assign(organismesState,{scope:"",page:1,selected:null,busy:false,pending:null});
  $("organismes-form").reset(); $("organismes-search-form").reset();
  $("organismes-rows").replaceChildren(); $("organismes-detail").hidden=true;
  $("organismes-message").textContent=""; $("organismes-page").textContent="";
}
function organismesControls() {
  $("organismes-new").hidden=!organismesManage();
  $("organismes-new").disabled=organismesState.busy;
  $("organismes-fields").disabled=organismesState.busy||!organismesManage();
  $("organismes-save").hidden=!organismesManage();
  $("organismes-save").disabled=organismesState.busy;
  $("organismes-cancel").disabled=organismesState.busy;
  $("organismes-reload").hidden=!organismesState.selected;
  $("organismes-reload").disabled=organismesState.busy;
}
async function organismesRequest(path,method="GET",body=null) {
  const org=authState.me.organisation.id_organisation;
  const response=await authFetch(`/api/tiers-payants/organisations/${org}/organismes${path}`,{method,body:body?JSON.stringify(body):undefined});
  const data=await response.json().catch(()=>null);
  if(!response.ok) {
    const message=typeof data?.detail==="string"?data.detail:response.status===422?"Vérifiez les valeurs saisies.":`Opération refusée (${response.status}).`;
    const error=new Error(message); error.status=response.status; throw error;
  }
  return data;
}
async function organismesLoad() {
  if(!authState.me||!organismesRead()||shellState.view!=="organismes")return;
  if(organismesState.scope!==organismesScope())organismesReset();
  organismesState.scope=organismesScope(); organismesControls();
  const epoch=organismesState.epoch,version=++organismesState.listVersion;
  const params=new URLSearchParams({q:$("organismes-search").value.trim(),page:String(organismesState.page),page_size:"25"});
  if($("organismes-status").value)params.set("actif",$("organismes-status").value);
  $("organismes-rows").setAttribute("aria-busy","true");
  try {
    const data=await organismesRequest(`?${params}`);
    if(epoch!==organismesState.epoch||version!==organismesState.listVersion)return;
    const body=$("organismes-rows");body.replaceChildren();
    for(const row of data.items) {
      const tr=document.createElement("tr");
      for(const value of [row.code,row.nom,row.actif?"Actif":"Inactif"]){const td=document.createElement("td");td.textContent=value;tr.append(td);}
      const td=document.createElement("td"),button=document.createElement("button");
      button.type="button";button.className="secondary";button.textContent=`Consulter ${row.nom}`;
      button.addEventListener("click",()=>organismesOpen(row.id));td.append(button);tr.append(td);body.append(tr);
    }
    $("organismes-page").textContent=`Page ${data.page} · ${data.total} organisme(s)`;
    $("organismes-prev").disabled=data.page<=1;$("organismes-next").disabled=data.page*data.page_size>=data.total;
  } catch(error) {if(epoch===organismesState.epoch&&version===organismesState.listVersion)$("organismes-message").textContent=error.message;}
  finally {if(epoch===organismesState.epoch&&version===organismesState.listVersion)$("organismes-rows").setAttribute("aria-busy","false");}
}
function organismesShow(row) {
  organismesState.selected=row;organismesState.pending=null;
  const form=$("organismes-form");form.reset();
  form.elements.code.value=row?.code||"";form.elements.nom.value=row?.nom||"";
  form.elements.actif.value=String(row?.actif??true);form.elements.actif.disabled=!row;
  $("organismes-title").textContent=row?row.nom:"Nouvel organisme";
  $("organismes-reference").textContent=row?`Identifiant : ${row.id}`:"Création indépendante des fiches clients et de la fidélité.";
  $("organismes-detail").hidden=false;organismesControls();
  if(organismesManage())form.elements.code.focus();else $("organismes-title").focus();
}
async function organismesOpen(id) {
  if(organismesState.busy||!organismesRead())return;
  const epoch=organismesState.epoch,version=++organismesState.detailVersion;
  try {const row=await organismesRequest(`/${id}`);if(epoch===organismesState.epoch&&version===organismesState.detailVersion)organismesShow(row);}
  catch(error){if(epoch===organismesState.epoch&&version===organismesState.detailVersion)$("organismes-message").textContent=error.message;}
}
$("organismes-form").addEventListener("submit",async event=>{
  event.preventDefault();if(organismesState.busy||!organismesManage())return;
  const form=event.currentTarget,row=organismesState.selected;
  const data={code:form.elements.code.value.trim(),nom:form.elements.nom.value.trim()};
  if(row)Object.assign(data,{revision:row.revision,actif:form.elements.actif.value==="true"});
  const path=row?`/${row.id}`:"", fingerprint=JSON.stringify({path,data});
  if(organismesState.pending?.fingerprint!==fingerprint)organismesState.pending={fingerprint,cle:crypto.randomUUID()};
  const epoch=organismesState.epoch;organismesState.busy=true;organismesControls();
  try {
    const result=await organismesRequest(path,row?"PUT":"POST",{...data,cle:organismesState.pending.cle});
    if(epoch!==organismesState.epoch)return;
    organismesShow(result);$("organismes-message").textContent="Organisme enregistré.";
    await organismesLoad();
  } catch(error) {
    if(epoch===organismesState.epoch)$("organismes-message").textContent=error.status===409?`${error.message} Rechargez la fiche avant de modifier à nouveau.`:error.message;
  } finally {if(epoch===organismesState.epoch){organismesState.busy=false;organismesControls();}}
});
$("organismes-new").addEventListener("click",()=>{if(organismesManage()&&!organismesState.busy){organismesState.detailVersion++;organismesShow(null);}});
$("organismes-reload").addEventListener("click",()=>{if(organismesState.selected)organismesOpen(organismesState.selected.id);});
$("organismes-cancel").addEventListener("click",()=>{if(!organismesState.busy){organismesState.detailVersion++;$("organismes-detail").hidden=true;organismesState.selected=null;organismesState.pending=null;}});
$("organismes-search-form").addEventListener("submit",event=>{event.preventDefault();organismesState.page=1;organismesLoad();});
$("organismes-prev").addEventListener("click",()=>{if(organismesState.page>1){organismesState.page--;organismesLoad();}});
$("organismes-next").addEventListener("click",()=>{organismesState.page++;organismesLoad();});
const organismesPreviousReset=authReset;
authReset=function(){organismesReset();organismesPreviousReset();};
const organismesPreviousSync=shellSync;
shellSync=function(){
  if(organismesState.scope&&(organismesState.scope!==organismesScope()||!organismesRead()))organismesReset();
  organismesPreviousSync();
  if(authState.me)organismesControls();
};
