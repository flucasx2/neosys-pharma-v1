"use strict";
// Shared presentation primitive for simple management workflows. Business screens
// (orders, sale preparation and payment) remain separate from this component.
const creationDialogs={entries:new Map(),generation:0};
function creationDialogSnapshot(form){return JSON.stringify([...new FormData(form)]);}
function creationDialogDirty(entry){return entry.dialog.open&&!entry.saved&&creationDialogSnapshot(entry.form)!==entry.initial;}
function creationDialogClose(entry,force=false){
  if(entry.pending&&!force)return false;
  if(!force&&creationDialogDirty(entry)&&!window.confirm("Des modifications non enregistrées seront perdues. Abandonner la saisie ?"))return false;
  entry.generation++;entry.dialog.close();entry.form.reset();entry.error.textContent="";entry.saved=null;
  document.body.classList.toggle("modal-open",[...creationDialogs.entries.values()].some(e=>e.dialog.open));
  if(!force&&entry.returnFocus?.isConnected)entry.returnFocus.focus({preventScroll:true});
  return true;
}
function creationDialogReset(){for(const entry of creationDialogs.entries.values())creationDialogClose(entry,true);}
function creationDialogCreate(id,source){
  const dialog=document.createElement("dialog");dialog.id=id;dialog.className="creation-dialog";dialog.setAttribute("aria-labelledby",id+"-title");
  const header=document.createElement("div");header.className="creation-dialog-header";
  const title=document.createElement("h2");title.id=id+"-title";
  const close=document.createElement("button");close.type="button";close.className="secondary";close.textContent="×";close.setAttribute("aria-label","Fermer la fenêtre");header.append(title,close);
  const form=source.cloneNode(true);form.id=id+"-form";form.hidden=false;
  const ids=new Map([[source.id,form.id]]);
  for(const node of form.querySelectorAll("[id]")){ids.set(node.id,id+"-"+node.id);node.id=ids.get(node.id);}
  for(const node of form.querySelectorAll("[for]"))if(ids.has(node.htmlFor))node.htmlFor=ids.get(node.htmlFor);
  for(const node of form.querySelectorAll("button"))if(!node.hasAttribute("data-catalogue-create"))node.remove();
  const content=document.createElement("div");content.className="creation-dialog-content";
  while(form.firstChild)content.append(form.firstChild);
  const error=document.createElement("p");error.id=id+"-error";error.className="creation-dialog-error";error.setAttribute("role","alert");error.hidden=true;content.prepend(error);
  const footer=document.createElement("div");footer.className="creation-dialog-footer";
  const cancel=document.createElement("button");cancel.type="button";cancel.className="secondary";cancel.textContent="Annuler";
  const submit=document.createElement("button");submit.type="submit";submit.textContent="Enregistrer";footer.append(cancel,submit);
  form.append(content,footer);dialog.append(header,form);document.body.append(dialog);
  const entry={dialog,form,title,error,submit,close,cancel,ids,generation:0,pending:false,saved:null};creationDialogs.entries.set(id,entry);
  close.addEventListener("click",()=>creationDialogClose(entry));cancel.addEventListener("click",()=>creationDialogClose(entry));
  dialog.addEventListener("cancel",event=>{event.preventDefault();creationDialogClose(entry);});
  dialog.addEventListener("keydown",event=>{
    if(event.key!=="Tab")return;
    const focusable=[...dialog.querySelectorAll('button,input,select,textarea,a[href],[tabindex]:not([tabindex="-1"])')].filter(e=>!e.disabled&&e.getClientRects().length);
    const first=focusable[0],last=focusable.at(-1);
    if(event.shiftKey&&document.activeElement===first){event.preventDefault();last?.focus();}
    else if(!event.shiftKey&&document.activeElement===last){event.preventDefault();first?.focus();}
  });
  form.addEventListener("submit",async event=>{
    event.preventDefault();if(entry.pending||!entry.options.allowed())return;
    const data=Object.fromEntries(new FormData(form)),generation=entry.generation;entry.pending=true;entry.error.hidden=true;entry.error.textContent="";entry.options.lock(true);
    const disabled=[...form.elements,close].map(node=>[node,node.disabled]);for(const [node] of disabled)node.disabled=true;
    try{
      // Retrying a failed refresh must not repeat a successful POST.
      if(!entry.saved)entry.saved=await entry.options.save(data);
      if(generation!==entry.generation)return;
      await entry.options.refresh(entry.saved);
      if(generation!==entry.generation)return;
      creationDialogClose(entry,true);entry.options.confirm();
      if(entry.returnFocus?.isConnected)entry.returnFocus.focus({preventScroll:true});
    }catch(error){
      if(generation===entry.generation){entry.error.textContent=entry.saved?"Enregistrement effectué. L’actualisation a échoué : "+error.message:error.message;entry.error.hidden=false;entry.submit.textContent=entry.saved?"Réessayer l’actualisation":"Enregistrer";entry.error.scrollIntoView({block:"nearest"});}
    }finally{
      for(const [node,wasDisabled] of disabled)node.disabled=wasDisabled||(Boolean(entry.saved)&&![entry.cancel,entry.submit,entry.close].includes(node));
      entry.pending=false;entry.options.lock(false);
    }
  });
  return entry;
}
function creationDialogOpen(entry,title,options,initialize){
  if(!options.allowed())return;
  entry.generation++;entry.options=options;entry.saved=null;entry.pending=false;entry.form.reset();entry.error.textContent="";entry.error.hidden=true;entry.submit.textContent="Enregistrer";
  for(const node of [...entry.form.elements,entry.close])node.disabled=false;
  entry.title.textContent=title;entry.returnFocus=document.activeElement;
  initialize(entry);entry.initial=creationDialogSnapshot(entry.form);
  entry.dialog.showModal();document.body.classList.add("modal-open");[...entry.dialog.querySelectorAll("input:not([type=checkbox]),select,textarea")].find(node=>!node.disabled&&node.getClientRects().length)?.focus({preventScroll:true});
}
window.addEventListener("beforeunload",event=>{if([...creationDialogs.entries.values()].some(creationDialogDirty)){event.preventDefault();event.returnValue="";}});

// Mirror backend normalization on explicitly opted-in short business inputs.
// Unicode composition and caret positions are respected; IME composition is
// normalized only when complete. Free text and external identifiers are excluded.
function businessUppercase(input){
  if(!input.matches?.("[data-business-uppercase]")||input.disabled)return;
  const value=input.value,start=input.selectionStart,end=input.selectionEnd;
  const upper=text=>text.normalize("NFC").toLocaleUpperCase("fr-FR");
  input.value=upper(value);
  if(start!==null&&end!==null)input.setSelectionRange(upper(value.slice(0,start)).length,upper(value.slice(0,end)).length);
}
for(const type of ["input","change","compositionend"])document.addEventListener(type,event=>{if(!event.isComposing)businessUppercase(event.target);});
