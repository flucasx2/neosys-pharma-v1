"use strict";
// Module intégré aux créances. Les montants et états définitifs viennent du serveur.
const documentsState={selection:new Map(),filters:{statut:"VALIDE_POUR_FACTURATION",organisme_id:"",date_debut:"",date_fin:""},genre:"BORDEREAU",request:0,active:false};
async function documentsRequest(path,method="GET",body=null){
 const epoch=creancesState.epoch,scope=creanceScope();
 const r=await authFetch(`${confRoot()}/documents${path}`,{method,body:body?JSON.stringify(body):undefined});
 const data=await r.json().catch(()=>null);
 if(epoch!==creancesState.epoch||scope!==creanceScope()){const e=Error("Contexte changé.");e.stale=true;throw e;}
 if(!r.ok){const e=Error(typeof data?.detail==="string"?data.detail:`Opération refusée (${r.status}).`);e.status=r.status;throw e;}
 return data;
}
async function documentsMutation(path,body){
 if(creancesState.busy)throw Error("Un enregistrement est déjà en cours.");
 const fingerprint=JSON.stringify({path,body});
 if(!creancesState.pending.has(fingerprint))creancesState.pending.set(fingerprint,crypto.randomUUID());
 const epoch=creancesState.epoch;creancesState.busy=true;creanceControls();
 try{return await documentsRequest(path,"POST",{...body,cle:creancesState.pending.get(fingerprint)});}
 finally{if(epoch===creancesState.epoch){creancesState.busy=false;creanceControls();}}
}
function documentsNavigation(){
 documentsState.active=true;
 const root=$("creances-actions");root.replaceChildren();
 creanceButton(root,"Créances à contrôler",()=>{documentsState.filters.statut="A_COMPLETER";documentsState.selection.clear();return documentsRecherche();});
 creanceButton(root,"Créances prêtes à facturer",()=>{documentsState.filters.statut="VALIDE_POUR_FACTURATION";documentsState.selection.clear();return documentsRecherche();});
 creanceButton(root,"Préparations et documents",()=>documentsPreparations(),"tiers_payant.document.consulter");
 creanceButton(root,"Récapitulatifs et lots",()=>documentsRegroupements(),"tiers_payant.document.consulter");
 creanceButton(root,"Gestion des créances",()=>creancesLoad());
}
function documentsPager(root,data,load){
 confNode("p",`Page ${data.page} · ${data.total} élément(s)`,root);
 if(data.page>1)creanceButton(root,"Précédent",()=>load(data.page-1));
 if(data.page*data.page_size<data.total)creanceButton(root,"Suivant",()=>load(data.page+1));
}
async function documentsRecherche(page=1){
 if(creancesState.busy)return;documentsNavigation();const version=++documentsState.request;
 const query=new URLSearchParams({page:String(page),page_size:"25"});
 for(const [k,v]of Object.entries(documentsState.filters))if(v)query.set(k,v);
 const data=await documentsRequest(`/creances?${query}`);if(version!==documentsState.request)return;
 const root=$("creances-content");root.replaceChildren();confNode("h3","Préparation des dossiers organismes",root);
 confNode("p","Période fondée sur la date UTC de réalisation. Les dossiers incomplets, non vérifiés, retournés ou déjà engagés sont refusés côté serveur.",root);
 const form=confNode("form",null,root);
 const organisme=confSelect(form,"organisme_id","Organisme",[["","Tous"],...(documentsState.filters.organisme_id?[[documentsState.filters.organisme_id,"Organisme sélectionné"]]:[])],documentsState.filters.organisme_id);
 const orgSearch=confField(form,"organisme_recherche","Trouver un organisme par nom ou code","search","",false);
 const orgResults=confNode("div",null,form);
 const loadOrganismes=async(orgPage=1)=>{const found=await documentsRequest(`/organismes?q=${encodeURIComponent(orgSearch.value)}&page=${orgPage}&page_size=25`);if(version!==documentsState.request||!organisme.isConnected)return;const chosen=organisme.value;organisme.replaceChildren();confNode("option","Tous",organisme,{value:""});for(const item of found.items)confNode("option",`${item.nom} · ${item.code}`,organisme,{value:item.id});if(chosen&&!Array.from(organisme.options).some(x=>x.value===chosen))confNode("option","Organisme sélectionné (autre page)",organisme,{value:chosen});organisme.value=chosen;orgResults.replaceChildren();documentsPager(orgResults,found,loadOrganismes);};
 creanceButton(form,"Trouver l’organisme",()=>loadOrganismes());await loadOrganismes();if(version!==documentsState.request)return;
 confField(form,"date_debut","Réalisations à partir du","date",documentsState.filters.date_debut,false);
 confField(form,"date_fin","Réalisations jusqu’au","date",documentsState.filters.date_fin,false);
 confSelect(form,"statut","État du dossier",[["","Tous"],["A_COMPLETER","À compléter"],["A_CONTROLER","À contrôler"],["VALIDE_POUR_FACTURATION","Prêt à facturer"],["EN_ANOMALIE","En anomalie"],["FACTURE","Facturé"]],documentsState.filters.statut);
 confNode("button","Rechercher",form,{type:"submit"});form.addEventListener("submit",e=>{e.preventDefault();for(const k of Object.keys(documentsState.filters))documentsState.filters[k]=form.elements[k].value;documentsState.selection.clear();documentsRecherche().catch(creanceError);});
 const genre=confSelect(root,"genre","Document à préparer",[["BORDEREAU","Bordereau de présentation"],["FACTURE","Facture organisme"]],documentsState.genre);
 genre.addEventListener("change",()=>{documentsState.genre=genre.value;documentsState.selection.clear();documentsRecherche().catch(creanceError);});
 const summary=confNode("p","",root,{id:"documents-selection-total"});
 const update=()=>{const rows=[...documentsState.selection.values()];summary.textContent=`${rows.length} créance(s) sélectionnée(s) · ${rows.reduce((n,x)=>n+x.montant_xaf,0)} XAF (à vérifier par le serveur)`;};
 for(const row of data.items){
  const article=confNode("article",null,root);const blocked=!row.facturable||(row.engagements||[]).some(x=>x.genre===documentsState.genre);
  const label=confNode("label",`${row.montant_xaf} XAF · vente ${row.vente_id} · organisme ${row.organisme?.nom||row.organisme_id} · ${row.etat_effectif}`,article);
  const check=confNode("input",null,label,{type:"checkbox",checked:documentsState.selection.has(row.id),disabled:blocked||!authHas("tiers_payant.document.preparer")});
  check.dataset.permission="tiers_payant.document.preparer";if(blocked)check.dataset.locked="1";
  check.addEventListener("change",()=>{if(blocked)return;check.checked?documentsState.selection.set(row.id,row):documentsState.selection.delete(row.id);update();});
  for(const message of row.anomalies_effectives)confNode("p",message,article);
  if((row.engagements||[]).length)confNode("p","Engagements : "+row.engagements.map(x=>x.genre+" / "+x.preparation_id).join(", "),article);
  creanceButton(article,"Consulter et compléter le dossier",()=>{documentsState.request++;return creancesOpen(row.id);});
 }
 update();documentsPager(root,data,documentsRecherche);
 const create=confNode("form",null,root);confField(create,"motif","Motif de préparation");
 confField(create,"presentation_id","Identifiant de préparation du bordereau déjà émis (facultatif)","text","",false);
 creanceButton(create,"Préparer le document sélectionné",async()=>{
  if(!create.reportValidity())return;const claims=[...documentsState.selection.values()];if(!claims.length)throw Error("Sélectionnez au moins une créance éligible.");
  const conventions=claims.map(x=>x.snapshot.lignes[0].etape.convention_id);
  if(new Set(claims.map(x=>x.organisme_id)).size!==1||new Set(conventions).size!==1)throw Error("Sélectionnez un seul organisme et une seule version de convention.");
  if(!form.elements.date_debut.value||!form.elements.date_fin.value)throw Error("Renseignez la période avant de préparer un document.");
  if(!window.confirm(`Préparer ${documentsState.genre} avec ${claims.length} créance(s) ? Aucun numéro définitif n’est attribué.`))return;
  const result=await documentsMutation("/preparations",{genre:documentsState.genre,organisme_id:claims[0].organisme_id,convention_id:conventions[0],
   date_debut:form.elements.date_debut.value,date_fin:form.elements.date_fin.value,presentation_id:create.elements.presentation_id.value||null,
   selection:claims.map(x=>({creance_id:x.id,revision:x.dossier.revision})),motif:create.elements.motif.value});
  documentsState.selection.clear();await documentsOpen(result.preparation.id);
 },"tiers_payant.document.preparer");
 create.addEventListener("submit",e=>e.preventDefault());
}
async function documentsPreparations(page=1,creanceId=null){
 documentsNavigation();const version=++documentsState.request;const data=await documentsRequest(`/preparations?page=${page}&page_size=25${creanceId?"&creance_id="+encodeURIComponent(creanceId):""}`);if(version!==documentsState.request)return;
 const root=$("creances-content");root.replaceChildren();confNode("h3","Préparations, bordereaux et factures",root);
 const chosen=new Set();
 for(const row of data.items){const article=confNode("article",null,root);confNode("p",`${row.preparation.genre} · ${row.version.etat} · ${row.document?.reference||"Sans référence définitive"}`,article);
  creanceButton(article,"Consulter la préparation",()=>documentsOpen(row.preparation.id));
  if(row.document)creanceButton(article,"Récapitulatifs et lots liés",()=>documentsRegroupements(1,row.document.id));
  if(row.document?.genre==="FACTURE"){const input=confField(article,"facture","Inclure dans un récapitulatif","checkbox","",false);input.addEventListener("change",()=>input.checked?chosen.add(row.document.id):chosen.delete(row.document.id));}
 }
 documentsPager(root,data,p=>documentsPreparations(p,creanceId));
 const form=confNode("form",null,root);const motif=confField(form,"motif","Motif de regroupement");
 creanceButton(form,"Créer le récapitulatif facultatif",async()=>{if(!form.reportValidity())return;const r=await documentsMutation("/regroupements",{genre:"RECAPITULATIF",ids:[...chosen],motif:motif.value});await documentsShowGroup(r.id);},"tiers_payant.document.regrouper");form.addEventListener("submit",e=>e.preventDefault());
}
async function documentsOpen(id){
 const version=++documentsState.request;const data=await documentsRequest(`/preparations/${id}`);if(version!==documentsState.request)return;
 const activation=await documentsRequest("/activation");if(version!==documentsState.request)return;documentsNavigation();
 const root=$("creances-content");root.replaceChildren();const row=data.preparation,v=data.version,doc=data.document;
 confNode("h3",`${row.genre} · ${v.etat}`,root);confNode("p",`Préparation ${row.id} · révision ${v.revision} · période ${row.date_debut} / ${row.date_fin}`,root);
 confNode("p",doc?`Référence ${doc.reference} · ${doc.total_xaf} XAF · ${doc.pdf_sha256}`:"Aucun document définitif. La prévisualisation porte la mention BROUILLON.",root);
 const selected=new Set();
 for(const item of v.selection){const line=confNode("article",null,root);confNode("p",`Créance ${item.creance_id} · dossier révision ${item.revision}`,line);creanceButton(line,"Consulter le dossier",()=>{documentsState.request++;return creancesOpen(item.creance_id);});if(!["EMISE","ABANDONNEE"].includes(v.etat)){const check=confField(line,"retirer","Retirer de cette préparation","checkbox","",false);check.addEventListener("change",()=>check.checked?selected.add(item.creance_id):selected.delete(item.creance_id));}}
 const form=confNode("form",null,root);const motif=confField(form,"motif","Motif de l’opération");
 if(!["EMISE","ABANDONNEE"].includes(v.etat)){
  creanceButton(form,"Retirer les dossiers cochés",async()=>{if(!form.reportValidity())return;await documentsMutation(`/preparations/${id}/selection`,{revision:v.revision,selection:v.selection.filter(x=>!selected.has(x.creance_id)),motif:motif.value});await documentsOpen(id);},"tiers_payant.document.preparer");
  creanceButton(form,"Abandonner la préparation",async()=>{if(!form.reportValidity()||!window.confirm("Abandonner sans émission ? Les engagements de cette préparation seront libérés."))return;await documentsMutation(`/preparations/${id}/abandonner`,{revision:v.revision,motif:motif.value});await documentsOpen(id);},"tiers_payant.document.preparer");
  creanceButton(form,"Valider la préparation",async()=>{if(!form.reportValidity()||!window.confirm("Recontrôler tous les dossiers et valider cette préparation ?"))return;await documentsMutation(`/preparations/${id}/valider`,{revision:v.revision,motif:motif.value});await documentsOpen(id);},"tiers_payant.document.valider");
  creanceButton(root,"Télécharger la prévisualisation",()=>documentsPdf(`/preparations/${id}/previsualisation.pdf?revision=${v.revision}`,"brouillon-organisme.pdf"));
 }
 if(v.etat==="VALIDEE"){
  const reference=confField(form,"reference","Référence manuelle unique du protocole de recette","text","",false);
  const validation=confField(form,"validation","Référence du protocole de recette autorisé","text","",false);
  confNode("p",activation.motif,root);
  const b=creanceButton(form,"Émettre en recette isolée",async()=>{if(!form.reportValidity())return;if(!reference.value||!validation.value)throw Error("Référence et protocole de recette requis.");if(!window.confirm("Émettre uniquement dans cette recette isolée ? Le document restera marqué sans validité fiscale."))return;await documentsMutation(`/preparations/${id}/emettre`,{revision:v.revision,motif:motif.value,reference:reference.value,reference_validation:validation.value});await documentsOpen(id);},"tiers_payant.document.emettre");
  if(b&&!activation.emission_recette_autorisee){b.dataset.locked="1";b.disabled=true;}
 }
 form.addEventListener("submit",e=>e.preventDefault());
 if(doc)creanceButton(root,"Télécharger le document émis",()=>documentsPdf(`/emis/${doc.id}/pdf`,`${doc.reference.replaceAll("/","-")}.pdf`));
 creanceButton(root,"Historique de la préparation",()=>documentsHistorique(id));creanceControls();
}
async function documentsHistorique(id,page=1){
 const version=++documentsState.request;const data=await documentsRequest(`/preparations/${id}/historique?page=${page}&page_size=25`);if(version!==documentsState.request)return;
 $("documents-history")?.remove();const root=confNode("article",null,$("creances-content"),{id:"documents-history"});confNode("h4","Historique conservé",root);
 for(const x of data.items)confNode("p",`Révision ${x.revision} · ${x.etat} · ${x.cree_le} · ${x.auteur_id} · ${x.motif}`,root);
 documentsPager(root,data,p=>documentsHistorique(id,p));
}
async function documentsRegroupements(page=1,documentId=null){
 documentsNavigation();const version=++documentsState.request;const data=await documentsRequest(`/regroupements?page=${page}&page_size=25${documentId?"&document_id="+encodeURIComponent(documentId):""}`);if(version!==documentsState.request)return;
 const root=$("creances-content");root.replaceChildren();confNode("h3","Récapitulatifs et lots facultatifs",root);const selected=new Set();
 for(const row of data.items){const article=confNode("article",null,root);confNode("p",`${row.genre} · ${row.id} · ${row.total_xaf} XAF`,article);creanceButton(article,"Consulter le regroupement",()=>documentsShowGroup(row.id));if(row.genre==="RECAPITULATIF"){const c=confField(article,"regroupement","Inclure dans un lot","checkbox","",false);c.addEventListener("change",()=>c.checked?selected.add(row.id):selected.delete(row.id));}}
 documentsPager(root,data,p=>documentsRegroupements(p,documentId));const form=confNode("form",null,root);const motif=confField(form,"motif","Motif du lot");creanceButton(form,"Créer le lot facultatif",async()=>{if(!form.reportValidity())return;const result=await documentsMutation("/regroupements",{genre:"LOT",ids:[...selected],motif:motif.value});await documentsShowGroup(result.id);},"tiers_payant.document.regrouper");form.addEventListener("submit",e=>e.preventDefault());
}
async function documentsShowGroup(id){const version=++documentsState.request;const row=await documentsRequest(`/regroupements/${id}`);if(version!==documentsState.request)return;const root=$("creances-content");root.replaceChildren();confNode("h3",`${row.genre} · ${row.id}`,root);confNode("p",`${row.total_xaf} XAF · auteur ${row.auteur_id} · ${row.cree_le}`,root);for(const x of row.snapshot.lignes)confNode("p",`${x.reference} · ${x.montant_xaf} XAF`,root);creanceButton(root,"Télécharger le regroupement",()=>documentsPdf(`/regroupements/${id}/pdf`,"regroupement-organisme.pdf"));}
async function documentsPdf(path,name){
 const scope=creanceScope(),epoch=creancesState.epoch;const r=await authFetch(`${confRoot()}/documents${path}`);
 if(scope!==creanceScope()||epoch!==creancesState.epoch)return;
 if(!r.ok){const data=await r.json().catch(()=>null);const e=Error(typeof data?.detail==="string"?data.detail:"Document inaccessible.");e.status=r.status;throw e;}
 const url=URL.createObjectURL(await r.blob());const a=document.createElement("a");a.href=url;a.download=name;a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);
}
const documentsOldLoad=creancesLoad;
creancesLoad=async function(...args){documentsState.request++;documentsState.active=false;await documentsOldLoad(...args);if(authState.me&&authHas("tiers_payant.document.consulter"))creanceButton($("creances-actions"),"Préparer bordereaux et factures",()=>{documentsState.selection.clear();return documentsRecherche();},"tiers_payant.document.consulter");};
const documentsOldReset=creancesReset;
creancesReset=function(){documentsState.active=false;documentsState.genre="BORDEREAU";documentsState.request++;documentsState.selection.clear();documentsState.filters={statut:"VALIDE_POUR_FACTURATION",organisme_id:"",date_debut:"",date_fin:""};documentsOldReset();};

const documentsOldSync=shellSync;
shellSync=function(){if(documentsState.active&&!authHas("tiers_payant.document.consulter")){documentsState.request++;documentsState.active=false;documentsState.selection.clear();$("creances-content").replaceChildren();$("creances-actions").replaceChildren();}documentsOldSync();};

const documentsOldCreanceOpen=creancesOpen;
creancesOpen=async function(id){
 documentsState.request++;documentsState.active=false;const epoch=creancesState.epoch,version=creancesState.version+1;
 await documentsOldCreanceOpen(id);
 if(epoch===creancesState.epoch&&version===creancesState.version&&authHas("tiers_payant.document.consulter"))creanceButton($("creances-content"),"Documents liés à la créance",()=>documentsPreparations(1,id),"tiers_payant.document.consulter");
};
