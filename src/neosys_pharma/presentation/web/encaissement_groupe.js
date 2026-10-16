"use strict";

// P4-C.4: presentation des brouillons groupees. Les ecritures financieres
// restent exclusivement sous l'autorite de l'API P4-C.3.
const cashGroupState = {
  mode: "INDIVIDUEL", page: 1, pageSize: 15, selected: new Map(), draft: null,
  saleDetails: new Map(), loyalty: new Map(), payments: [], allocations: [], busy: false,
  mutationRetry: null, finalisationKey: null, finalisationPayload: null,
  finalisationEnabled: false,
};
const cg = id => document.getElementById("cash-group-" + id);
const cgMoney = value => venteMoney(Number(value || 0));
const cgIdempotentKey = () => crypto.randomUUID();
const cgDraftStorageKey = () => `neosys:p4c4:draft:${authState.me?.organisation?.id_organisation || ""}:${authState.site || ""}`;
function cgRememberDraft(id) {
  if (!id) return;
  cg("resume-id").value = id;
  try { localStorage.setItem(cgDraftStorageKey(), id); } catch (_) {}
}
function cgFinalizationKey(dossierId, fingerprint) {
  const key = `${cgDraftStorageKey()}:${dossierId}:finalisation`;
  try {
    const saved = JSON.parse(localStorage.getItem(key) || "null");
    if (saved?.fingerprint === fingerprint && saved?.key) return saved.key;
    const next = cgIdempotentKey();
    localStorage.setItem(key, JSON.stringify({ fingerprint, key: next }));
    return next;
  } catch (_) {
    if (cashGroupState.finalisationPayload === fingerprint && cashGroupState.finalisationKey) return cashGroupState.finalisationKey;
    throw new Error("Le navigateur ne peut pas conserver la clé d’idempotence. Autorisez le stockage local avant de finaliser.");
  }
}
function cgClearFinalizationKey(dossierId) {
  try { localStorage.removeItem(`${cgDraftStorageKey()}:${dossierId}:finalisation`); } catch (_) {}
}
function cgLoyaltyStorageKey(dossierId) {
  return `${cgDraftStorageKey()}:${dossierId}:fidelite`;
}
function cgSavedLoyaltyChoices(dossierId) {
  try { return JSON.parse(localStorage.getItem(cgLoyaltyStorageKey(dossierId)) || "{}"); }
  catch (_) { return {}; }
}
function cgStoreLoyaltyChoices() {
  const dossierId = cashGroupState.draft?.dossier?.id;
  if (!dossierId) return;
  const choices = {};
  for (const [saleId, state] of cashGroupState.loyalty) if (state.selected && state.account) {
    choices[saleId] = { compte_id: state.account.id, revision_compte: state.account.revision };
  }
  try {
    const key = cgLoyaltyStorageKey(dossierId);
    if (Object.keys(choices).length) localStorage.setItem(key, JSON.stringify(choices));
    else localStorage.removeItem(key);
  } catch (_) {}
}
async function cgLoadLoyaltyForSale(sale) {
  const saleId = sale.id;
  const base = { status: "loading", selected: false, account: null, message: "Recherche du compte associé…" };
  const isCurrent = () => cashGroupState.loyalty.get(saleId) === base;
  cashGroupState.loyalty.set(saleId, base);
  const cell = document.getElementById(`cash-group-loyalty-${saleId}`);
  if (cell) cgRenderLoyaltyCell(cell, sale);
  if (!sale.client) {
    Object.assign(base, { status: "none", message: "Aucun client associé : fidélité non applicable." });
    if (cell) cgRenderLoyaltyCell(cell, sale);
    return;
  }
  if (!authHas("fidelite.consulter", sale.emplacement_id)) {
    Object.assign(base, { status: "blocked", message: "Permission de consultation fidélité absente pour cet emplacement." });
    if (cell) cgRenderLoyaltyCell(cell, sale);
    return;
  }
  const query = String(sale.client.nom || sale.client.telephone || "").trim();
  if (query.length < 3) {
    Object.assign(base, { status: "none", message: "Aucune recherche sûre possible pour ce client." });
    if (cell) cgRenderLoyaltyCell(cell, sale);
    return;
  }
  try {
    const result = await cashRequest(`/fidelite?q=${encodeURIComponent(query)}&page=1&page_size=100`);
    if (!isCurrent()) return;
    const account = result.items.find(row => row.client?.profil_client_id === sale.client.id) || null;
    if (!account) {
      Object.assign(base, { status: "none", message: "Aucun compte fidélité associé à cette fiche client." });
    } else {
      const debt = Number(account.dette || 0);
      const saved = cashGroupState.draft ? cgSavedLoyaltyChoices(cashGroupState.draft.dossier.id)[saleId] : null;
      const selected = Boolean(saved && saved.compte_id === account.id && saved.revision_compte === account.revision && debt === 0);
      Object.assign(base, {
        status: debt > 0 ? "blocked" : "ready", account, selected,
        message: debt > 0 ? `Compte non admissible : dette de ${cgMoney(debt)}.` : "",
      });
      if (saved && !selected) {
        const choices = cgSavedLoyaltyChoices(cashGroupState.draft.dossier.id);
        delete choices[saleId];
        try { localStorage.setItem(cgLoyaltyStorageKey(cashGroupState.draft.dossier.id), JSON.stringify(choices)); } catch (_) {}
      }
    }
  } catch (error) {
    if (!isCurrent()) return;
    Object.assign(base, { status: "error", message: error.message || "Le compte fidélité n’a pas pu être consulté." });
  }
  if (cell) cgRenderLoyaltyCell(cell, sale);
}

async function cgRequest(path, method = "GET", body = null) {
  const response = await authFetch(cashRoot() + "/groupes" + path, {
    method, body: body ? JSON.stringify(body) : undefined,
  });
  const data = await response.json().catch(() => null);
  if (!response.ok) {
    const error = new Error(typeof data?.detail === "string" ? data.detail : `Opération refusée (${response.status}).`);
    error.status = response.status;
    if (response.status === 409) error.message += " Rechargez le dossier avant de poursuivre.";
    throw error;
  }
  return data;
}
function cgMutation(path, method, data, stableKey = null) {
  const encoded = JSON.stringify({ path, method, data });
  if (!cashGroupState.mutationRetry || cashGroupState.mutationRetry.encoded !== encoded) {
    cashGroupState.mutationRetry = { encoded, key: stableKey || cgIdempotentKey() };
  }
  return cgRequest(path, method, { ...data, cle: cashGroupState.mutationRetry.key });
}
function cgMessage(text, error = false) {
  const node = $("cash-message"); node.textContent = text || "";
  node.classList.toggle("error", Boolean(error));
}
function cgBusy(value) {
  cashGroupState.busy = value;
  cg("panel").setAttribute("aria-busy", String(value));
  if (value) for (const button of cg("panel").querySelectorAll("button")) button.disabled = true;
  else { cgRenderSelection(); if (cashGroupState.draft) cgRenderDraft(); }
}
function cgResetDraftTransient() {
  cashGroupState.payments = [];
  cashGroupState.allocations = [];
  cashGroupState.loyalty.clear();
  cashGroupState.mutationRetry = null;
  cashGroupState.finalisationKey = null;
  cashGroupState.finalisationPayload = null;
}
function cgInt(value) { return /^\d+$/.test(String(value)) ? Number(value) : NaN; }
function cgSelectedTotal() {
  return [...cashGroupState.selected.values()].reduce((sum, sale) => sum + Number(sale.totaux.ttc), 0);
}
function cgScope() {
  return `${authState.me.organisation.id_organisation}:${authState.site}:${cashState.session?.id || ""}`;
}
function cgRequireSession() {
  if (!cashState.session || cashState.session.etat !== "OUVERTE") throw new Error("Choisissez une session de caisse ouverte qui vous est autorisée.");
  if (!authHas("caisse.encaisser")) throw new Error("La permission caisse.encaisser est requise.");
}
function cgPermissionForSelection() {
  if (![...cashGroupState.selected.values()].every(sale => authHas("caisse.encaisser", sale.emplacement_id))) {
    throw new Error("Vous ne disposez pas de la permission d’encaissement pour tous les emplacements sélectionnés.");
  }
}
function cgAssertDraftSession() {
  cgRequireSession();
  if (cashGroupState.draft && cashGroupState.draft.dossier.session_id !== cashState.session.id) {
    throw new Error("Ce dossier appartient à une autre session. Sélectionnez la session associée pour poursuivre.");
  }
  for (const row of cashGroupState.draft?.ventes || []) {
    const sale = cashGroupState.saleDetails.get(row.vente_id);
    if (sale && !authHas("caisse.encaisser", sale.emplacement_id)) {
      throw new Error("La permission d’encaissement manque pour un emplacement de ce dossier.");
    }
  }
}
function cgSetMode(mode) {
  cashGroupState.mode = mode;
  const group = mode === "GROUPE";
  if (!group) { cashGroupState.selected.clear(); cgRenderSelection(); }
  $("cash-mode-group").setAttribute("aria-pressed", String(group));
  $("cash-mode-individual").setAttribute("aria-pressed", String(!group));
  cg("panel").hidden = !group;
  $("cash-waiting").closest("article").hidden = group;
  $("cash-sale").hidden = group || !cashState.sale;
  if (group) cgLoadSales().catch(error => cgMessage(error.message, true));
}
async function cgLoadSales() {
  await cgLoadActivation();
  try {
    const remembered = localStorage.getItem(cgDraftStorageKey());
    if (remembered && !cg("resume-id").value) cg("resume-id").value = remembered;
  } catch (_) {}
  const page = cashGroupState.page;
  const result = await cashRequest(`/attente?page=${page}&page_size=${cashGroupState.pageSize}`);
  const body = cg("sales"); body.replaceChildren();
  for (const row of result.items) {
    const tr = document.createElement("tr");
    const selectCell = document.createElement("td");
    const checkbox = document.createElement("input"); checkbox.type = "checkbox";
    checkbox.setAttribute("aria-label", `Sélectionner la vente ${row.id.slice(0, 8)}`);
    checkbox.checked = cashGroupState.selected.has(row.id);
    checkbox.addEventListener("change", async () => {
      if (checkbox.checked) {
        try {
          const sale = await cashRequest(`/ventes/${row.id}`);
          if (sale.etat !== "TRANSMISE") throw new Error("Cette vente n’est plus admissible. Actualisez la liste.");
          if (!authHas("caisse.encaisser", sale.emplacement_id)) throw new Error("Permission d’encaissement absente pour cet emplacement.");
          cashGroupState.selected.set(sale.id, sale); cashGroupState.saleDetails.set(sale.id, sale);
          await cgLoadLoyaltyForSale(sale);
        } catch (error) { checkbox.checked = false; cgMessage(error.message, true); }
      } else cashGroupState.selected.delete(row.id);
      cgRenderSelection();
    });
    selectCell.append(checkbox); tr.append(selectCell);
    for (const value of [row.numero_appel || "Ancienne préparation", row.id.slice(0, 8), cgMoney(row.net_ttc), row.emplacement_id?.slice(0, 8) || "—"]) {
      const cell = document.createElement("td"); cell.textContent = value; tr.append(cell);
    }
    body.append(tr);
  }
  cg("page").textContent = `${result.total} préparation(s) · page ${page}`;
  cg("prev").disabled = page <= 1; cg("next").disabled = page * cashGroupState.pageSize >= result.total;
  cgRenderSelection();
}
async function cgLoadActivation() {
  try {
    const result = await cgRequest("/activation");
    cashGroupState.finalisationEnabled = result.finalisation_active === true;
  } catch (error) {
    cashGroupState.finalisationEnabled = false;
    cgMessage(error.message, true);
  }
  cg("finalisation-note").textContent = cashGroupState.finalisationEnabled
    ? "L’API a autorisé la finalisation dans cet environnement. Vérifiez le récapitulatif avant validation."
    : "La finalisation groupée demeure désactivée par le serveur hors de la recette isolée.";
  cg("finalise").textContent = cashGroupState.finalisationEnabled ? "Finaliser le dossier" : "Finalisation indisponible";
  if (cashGroupState.draft) cg("finalise").disabled = !cgCanFinalize();
}
function cgRenderSelection() {
  const rows = [...cashGroupState.selected.values()];
  cg("selected-total").textContent = `${rows.length} ticket(s) sélectionné(s) · Total ${cgMoney(cgSelectedTotal())}`;
  cg("create").disabled = rows.length < 2 || !cashState.session || cashGroupState.busy;
  cg("add-selected").disabled = rows.length < 1 || !cashGroupState.draft || cashGroupState.busy;
}
function cgFailure(error) {
  cgMessage(error.message || "Opération impossible.", true);
  if (error.status === 409) cg("status").textContent = "Conflit de révision : rechargez le dossier et vérifiez à nouveau les ventes.";
}
async function cgCreateDraft() {
  if (cashGroupState.draft?.dossier?.etat === "BROUILLON") return cgAddSelected();
  cgRequireSession(); cgPermissionForSelection();
  if (cashGroupState.selected.size < 2) throw new Error("Sélectionnez au moins deux tickets.");
  cgResetDraftTransient();
  cgBusy(true);
  try {
    const created = await cgMutation("", "POST", { session_id: cashState.session.id });
    cashGroupState.mutationRetry = null;
    cashGroupState.draft = created;
    const sales = [...cashGroupState.selected.values()];
    const saved = await cgMutation(`/${created.dossier.id}/ventes`, "PUT", {
      revision: created.dossier.revision,
      ventes: sales.map(sale => ({ vente_id: sale.id, revision: sale.revision })),
    });
    cashGroupState.mutationRetry = null; cashGroupState.draft = saved;
    // Charger les fiches et les comptes fidélité avant de construire les cellules du brouillon.
    // Les détails de sélection ne garantissent pas un état de fidélité initialisé.
    await cgLoadDraftSales();
    cgRenderDraft(); cgMessage("Brouillon créé. Les ventes ne sont pas réservées par ce dossier.");
  } catch (error) { cgFailure(error); }
  finally { cgBusy(false); cgRenderSelection(); }
}
async function cgAddSelected() {
  if (!cashGroupState.draft || !cashGroupState.selected.size) return;
  cgRequireSession(); cgPermissionForSelection();
  const existing = new Set(cashGroupState.draft.ventes.map(row => row.vente_id));
  const selected = [...cashGroupState.selected.values()].filter(sale => !existing.has(sale.id));
  if (!selected.length) throw new Error("Aucun nouveau ticket à ajouter.");
  const replace = [...cashGroupState.draft.ventes.map(row => ({ vente_id: row.vente_id, revision: row.revision_vente })),
    ...selected.map(sale => ({ vente_id: sale.id, revision: sale.revision }))];
  await cgReplaceSales(replace);
  cashGroupState.selected.clear(); await cgLoadSales();
}
async function cgReplaceSales(sales) {
  const d = cashGroupState.draft; cgAssertDraftSession();
  if (d.allocations.length && !window.confirm("Modifier les tickets efface leur ventilation actuelle. Continuer explicitement ?")) return;
  cgBusy(true);
  try {
    cashGroupState.draft = await cgMutation(`/${d.dossier.id}/ventes`, "PUT", {
      revision: d.dossier.revision, ventes: sales,
      reinitialiser_allocations: d.allocations.length > 0,
    });
    const retained = new Set(sales.map(row => row.vente_id));
    for (const saleId of cashGroupState.loyalty.keys()) if (!retained.has(saleId)) cashGroupState.loyalty.delete(saleId);
    for (const saleId of retained) {
      const sale = cashGroupState.saleDetails.get(saleId);
      if (sale && !cashGroupState.loyalty.has(saleId)) await cgLoadLoyaltyForSale(sale);
    }
    cgStoreLoyaltyChoices();
    cashGroupState.mutationRetry = null; cgRenderDraft(); cgMessage("Tickets du brouillon actualisés.");
  } catch (error) { cgFailure(error); }
  finally { cgBusy(false); }
}
async function cgRemoveSale(id) {
  const d = cashGroupState.draft;
  await cgReplaceSales(d.ventes.filter(row => row.vente_id !== id)
    .map(row => ({ vente_id: row.vente_id, revision: row.revision_vente })));
}
async function cgResume() {
  const id = cg("resume-id").value.trim();
  if (!id) throw new Error("Saisissez l’identifiant du dossier à consulter.");
  cgBusy(true);
  try {
    const draft = await cgRequest(`/${encodeURIComponent(id)}`);
    cashGroupState.draft = draft; cashGroupState.mutationRetry = null;
    cgRememberDraft(draft.dossier.id);
    await cgLoadDraftSales(); cgRenderDraft(); cgMessage("Dossier rechargé depuis le serveur.");
  } catch (error) { cgFailure(error); }
  finally { cgBusy(false); }
}
async function cgReload() {
  if (!cashGroupState.draft) return;
  try {
    cashGroupState.draft = await cgRequest(`/${cashGroupState.draft.dossier.id}`);
    await cgLoadDraftSales(); cgRenderDraft(); cgMessage("Données du dossier rechargées.");
  } catch (error) { cgFailure(error); }
}
async function cgLoadDraftSales() {
  cashGroupState.saleDetails.clear();
  cashGroupState.loyalty.clear();
  await Promise.all(cashGroupState.draft.ventes.map(async row => {
    const sale = await cashRequest(`/ventes/${row.vente_id}`);
    cashGroupState.saleDetails.set(row.vente_id, sale);
    await cgLoadLoyaltyForSale(sale);
  }));
}
function cgRenderDraft() {
  const d = cashGroupState.draft;
  cg("draft").hidden = !d;
  if (!d) return;
  // Un brouillon abandonné ne doit pas réhydrater les règlements du serveur
  // dans le formulaire éditable. Conserver les données historiques côté dossier.
  if (d.dossier.etat === "ABANDONNE") cashGroupState.payments = [];
  else if (!cashGroupState.payments.length && d.reglements.length) cashGroupState.payments = d.reglements.map(row => ({ mode: row.mode, montant: String(row.montant), rendu: String(row.rendu), confirmation_id: row.confirmation_id }));
  cashGroupState.allocations = d.allocations;
  cg("resume-id").value = d.dossier.id;
  cgRememberDraft(d.dossier.id);
  cg("status").textContent = `${d.dossier.etat} · Révision ${d.dossier.revision} · ${d.ventes.length} vente(s)`;
  cg("session").textContent = `Session ${d.dossier.session_id} · ${cashState.session?.id === d.dossier.session_id ? "session courante" : "vérifiez votre session active"}`;
  const rows = cg("draft-sales"); rows.replaceChildren();
  for (const row of d.ventes) {
    const sale = cashGroupState.saleDetails.get(row.vente_id);
    const tr = document.createElement("tr");
    for (const text of [row.vente_id.slice(0, 8), sale?.client?.nom || "Client non associé", sale?.emplacement_id?.slice(0, 8) || "—", cgMoney(row.montant_du)]) {
      const td = document.createElement("td"); td.textContent = text; tr.append(td);
    }
    const fidelity = document.createElement("td"); fidelity.id = `cash-group-loyalty-${row.vente_id}`;
    if (sale) cgRenderLoyaltyCell(fidelity, sale);
    else fidelity.textContent = "Client et fidélité indisponibles";
    tr.append(fidelity);
    const td = document.createElement("td");
    const remove = document.createElement("button"); remove.type = "button"; remove.className = "secondary"; remove.textContent = "Retirer";
    remove.disabled = d.dossier.etat !== "BROUILLON" || cashGroupState.busy;
    remove.addEventListener("click", () => cgRemoveSale(row.vente_id).catch(cgFailure)); td.append(remove); tr.append(td); rows.append(tr);
  }
  const due = Number(d.totaux.du_xaf);
  cg("due").textContent = `Total dû ${cgMoney(due)} · Règlements nets ${cgMoney(d.totaux.net_regle_xaf)} · Reste ${cgMoney(d.totaux.reste_xaf)}`;
  cgRenderPayments(); cgRenderAllocations(); cgRenderReview(); cgRenderReceipts();
  const editable = d.dossier.etat === "BROUILLON";
  for (const id of ["add-payment", "save-payments", "auto", "save-allocations", "abandon", "add-selected"]) cg(id).disabled = !editable || cashGroupState.busy;
  cg("finalise").disabled = !cgCanFinalize();
}
function cgRenderLoyaltyCell(cell, sale) {
  cell.replaceChildren();
  const state = cashGroupState.loyalty.get(sale.id);
  if (!state || state.status === "loading" || state.status === "none" || state.status === "blocked" || state.status === "error") {
    cell.textContent = state?.message || "Fidélité non sélectionnée.";
    return;
  }
  const label = document.createElement("label");
  const checkbox = document.createElement("input"); checkbox.type = "checkbox";
  checkbox.checked = state.selected; checkbox.disabled = cashGroupState.busy || cashGroupState.draft?.dossier?.etat !== "BROUILLON";
  checkbox.setAttribute("aria-label", `Attribuer la fidélité du client ${state.account.client.nom} à la vente ${sale.id.slice(0, 8)}`);
  checkbox.addEventListener("change", () => {
    state.selected = checkbox.checked;
    cgStoreLoyaltyChoices(); cgRenderReview();
  });
  label.append(checkbox, document.createTextNode(` Compte de ${state.account.client.nom} · ${state.account.points} points · ${state.account.cartes.filter(card => card.etat === "ACTIVE").length} carte(s) active(s)`));
  cell.append(label);
}
function cgLoyaltyPayload() {
  const selected = [];
  for (const row of cashGroupState.draft.ventes) {
    const state = cashGroupState.loyalty.get(row.vente_id);
    if (!state?.selected) continue;
    const sale = cashGroupState.saleDetails.get(row.vente_id);
    if (state.status !== "ready" || !state.account || !sale?.client ||
        state.account.client?.profil_client_id !== sale.client.id || Number(state.account.dette || 0) > 0 ||
        !authHas("fidelite.consulter", sale.emplacement_id)) {
      throw new Error(`Le compte fidélité de la vente ${row.vente_id.slice(0, 8)} n’est plus admissible. Actualisez le dossier.`);
    }
    selected.push({ vente_id: row.vente_id, compte_id: state.account.id, revision_compte: state.account.revision });
  }
  return selected;
}
function cgCanFinalize() {
  const d = cashGroupState.draft;
  return Boolean(!cashGroupState.busy && cashGroupState.finalisationEnabled && d &&
    d.dossier.etat === "BROUILLON" && d.dossier.session_id === cashState.session?.id &&
    cashState.session?.etat === "OUVERTE" && Number(d.totaux.du_xaf) > 0 &&
    Number(d.totaux.reste_xaf) === 0 && Number(d.totaux.du_xaf) === Number(d.totaux.net_regle_xaf) &&
    d.totaux.allocation_valide && d.ventes.length > 1 &&
    d.ventes.every(row => {
      const sale = cashGroupState.saleDetails.get(row.vente_id);
      const loyalty = cashGroupState.loyalty.get(row.vente_id);
      return sale && authHas("caisse.encaisser", sale.emplacement_id) && loyalty && loyalty.status !== "loading" && loyalty.status !== "error";
    }));
}
function cgConfirmationOptions(mode, amount) {
  const choices = [];
  for (const [saleId, sale] of cashGroupState.saleDetails) for (const confirmation of sale.confirmations || []) {
    if (confirmation.mode === mode && Number(confirmation.montant) === amount) {
      choices.push({ id: confirmation.id, label: `${saleId.slice(0, 8)} · ${confirmation.reference} · ${cgMoney(confirmation.montant)}` });
    }
  }
  return choices;
}
function cgRenderPayments() {
  const root = cg("payments"); root.replaceChildren();
  const modes = cashState.context?.configuration?.modes || [];
  for (const [index, payment] of cashGroupState.payments.entries()) {
    const fieldset = document.createElement("fieldset"); fieldset.className = "cash-group-payment";
    const legend = document.createElement("legend"); legend.textContent = `Règlement ${index + 1}`; fieldset.append(legend);
    const mode = document.createElement("select"); mode.disabled = cashGroupState.draft?.dossier?.etat !== "BROUILLON"; mode.setAttribute("aria-label", `Mode règlement ${index + 1}`);
    for (const code of modes) mode.add(new Option(code.replaceAll("_", " "), code));
    if (payment.mode && modes.includes(payment.mode)) mode.value = payment.mode;
    const amountLabel = document.createElement("label"); amountLabel.textContent = payment.mode === "ESPECES" ? "Espèces reçues (XAF)" : "Montant confirmé (XAF)";
    const amount = document.createElement("input"); amount.disabled = cashGroupState.draft?.dossier?.etat !== "BROUILLON"; amount.type = "number"; amount.min = "0"; amount.step = "1"; amount.value = payment.montant ?? ""; amount.setAttribute("aria-label", `Montant règlement ${index + 1}`); amountLabel.append(amount);
    fieldset.append(mode, amountLabel);
    const changeLabel = document.createElement("label"); changeLabel.textContent = "Rendu espèces (XAF)";
    const change = document.createElement("input"); change.disabled = payment.mode !== "ESPECES" || cashGroupState.draft?.dossier?.etat !== "BROUILLON"; change.type = "number"; change.min = "0"; change.step = "1"; change.value = payment.rendu || "0"; change.setAttribute("aria-label", `Rendu espèces règlement ${index + 1}`); changeLabel.append(change); fieldset.append(changeLabel);
    const confirmationLabel = document.createElement("label"); confirmationLabel.textContent = "Confirmation P4.5";
    const confirmation = document.createElement("select"); confirmation.disabled = payment.mode === "ESPECES" || cashGroupState.draft?.dossier?.etat !== "BROUILLON"; confirmation.setAttribute("aria-label", `Confirmation règlement ${index + 1}`);
    confirmation.add(new Option(payment.mode === "ESPECES" ? "Sans confirmation espèces" : "Choisir une confirmation existante", ""));
    for (const choice of cgConfirmationOptions(payment.mode, cgInt(payment.montant))) confirmation.add(new Option(choice.label, choice.id));
    confirmation.value = payment.confirmation_id || "";
    confirmationLabel.append(confirmation); fieldset.append(confirmationLabel);
    const remove = document.createElement("button"); remove.type = "button"; remove.className = "secondary"; remove.textContent = "Supprimer cette ligne";
    remove.addEventListener("click", () => { cashGroupState.payments.splice(index, 1); cgRenderPayments(); }); fieldset.append(remove);
    const updateConfirmationChoices = () => {
      const previous = confirmation.value; confirmation.replaceChildren();
      confirmation.add(new Option(payment.mode === "ESPECES" ? "Sans confirmation espèces" : "Choisir une confirmation existante", ""));
      for (const choice of cgConfirmationOptions(payment.mode, cgInt(payment.montant))) confirmation.add(new Option(choice.label, choice.id));
      if ([...confirmation.options].some(option => option.value === previous)) confirmation.value = previous;
    };
    mode.addEventListener("change", () => { payment.mode = mode.value; payment.confirmation_id = null; payment.rendu = "0"; cgRenderPayments(); });
    amount.addEventListener("input", () => { payment.montant = amount.value; payment.confirmation_id = null; updateConfirmationChoices(); cgRenderReview(); });
    change.addEventListener("input", () => { payment.rendu = change.value; cgRenderReview(); });
    confirmation.addEventListener("change", () => { payment.confirmation_id = confirmation.value || null; cgRenderReview(); });
    root.append(fieldset);
  }
  cgRenderReview();
}
function cgPaymentPayload() {
  if (!cashGroupState.payments.length) throw new Error("Ajoutez au moins un règlement.");
  return cashGroupState.payments.map((payment, index) => {
    const amount = cgInt(payment.montant), change = cgInt(payment.rendu || "0");
    if (!Number.isSafeInteger(amount) || amount <= 0 || !Number.isSafeInteger(change) || change < 0 || change >= amount) throw new Error(`Règlement ${index + 1} : montants XAF entiers invalides ou rendu supérieur au montant reçu.`);
    if (payment.mode !== "ESPECES" && !payment.confirmation_id) throw new Error(`Règlement ${index + 1} : sélectionnez une confirmation P4.5.`);
    if (payment.mode === "ESPECES" && payment.confirmation_id) throw new Error("Les espèces ne peuvent pas porter de confirmation externe.");
    return { mode: payment.mode, montant: String(amount), rendu: String(payment.mode === "ESPECES" ? change : 0), confirmation_id: payment.mode === "ESPECES" ? null : payment.confirmation_id };
  });
}
async function cgSavePayments() {
  const d = cashGroupState.draft; if (!d) throw new Error("Créez ou consultez un dossier.");
  cgAssertDraftSession();
  const payments = cgPaymentPayload();
  const reset = d.allocations.length > 0;
  if (reset && !window.confirm("Enregistrer ces règlements efface la ventilation existante. Continuer explicitement ?")) return;
  cgBusy(true);
  try {
    cashGroupState.draft = await cgMutation(`/${d.dossier.id}/reglements`, "PUT", {
      revision: d.dossier.revision, reglements: payments, reinitialiser_allocations: reset,
    });
    cashGroupState.mutationRetry = null; cgRenderDraft(); cgMessage("Règlements enregistrés. Vérifiez les montants nets et la ventilation.");
  } catch (error) { cgFailure(error); }
  finally { cgBusy(false); }
}
function cgRenderAllocations() {
  const d = cashGroupState.draft; const head = cg("allocation-head"), body = cg("allocation-body");
  head.replaceChildren(); body.replaceChildren();
  const trHead = document.createElement("tr");
  for (const label of ["Règlement", ...d.ventes.map(row => row.vente_id.slice(0, 8))]) { const th = document.createElement("th"); th.textContent = label; trHead.append(th); }
  head.append(trHead);
  const matrix = new Map(cashGroupState.allocations.map(row => [`${row.reglement_id}:${row.vente_id}`, String(row.montant)]));
  for (const payment of d.reglements) {
    const tr = document.createElement("tr"); const label = document.createElement("td");
    label.textContent = `${payment.mode} · net ${cgMoney(Number(payment.montant) - Number(payment.rendu))}`; tr.append(label);
    for (const sale of d.ventes) {
      const cell = document.createElement("td"); const input = document.createElement("input"); input.type = "number"; input.min = "0"; input.step = "1";
      input.value = matrix.get(`${payment.id}:${sale.vente_id}`) || "";
      input.disabled = d.dossier.etat !== "BROUILLON" || cashGroupState.busy;
      input.setAttribute("aria-label", `Allocation ${payment.mode} vers vente ${sale.vente_id.slice(0, 8)}`);
      input.addEventListener("input", () => { input.dataset.edited = "true"; cgRenderReview(); }); cell.append(input); tr.append(cell);
    }
    body.append(tr);
  }
  cgRenderReview();
}
function cgReadManualAllocations() {
  const d = cashGroupState.draft, result = [], bySale = new Map(), byPayment = new Map();
  const rows = [...cg("allocation-body").querySelectorAll("tr")];
  rows.forEach((row, paymentIndex) => {
    const payment = d.reglements[paymentIndex];
    [...row.querySelectorAll("input")].forEach((input, saleIndex) => {
      const raw = input.value.trim(); if (!raw) return;
      const amount = cgInt(raw); if (!Number.isSafeInteger(amount) || amount <= 0) throw new Error("Les allocations doivent être des francs XAF entiers strictement positifs.");
      const sale = d.ventes[saleIndex];
      result.push({ reglement_id: payment.id, vente_id: sale.vente_id, montant: String(amount) });
      bySale.set(sale.vente_id, (bySale.get(sale.vente_id) || 0) + amount);
      byPayment.set(payment.id, (byPayment.get(payment.id) || 0) + amount);
    });
  });
  for (const sale of d.ventes) if ((bySale.get(sale.vente_id) || 0) !== Number(sale.montant_du)) throw new Error(`Ventilation invalide pour la vente ${sale.vente_id.slice(0, 8)} : alloué ${cgMoney(bySale.get(sale.vente_id) || 0)}, dû ${cgMoney(sale.montant_du)}.`);
  for (const payment of d.reglements) {
    const net = Number(payment.montant) - Number(payment.rendu);
    if ((byPayment.get(payment.id) || 0) !== net) throw new Error(`Ventilation invalide pour le règlement ${payment.mode} : alloué ${cgMoney(byPayment.get(payment.id) || 0)}, net ${cgMoney(net)}.`);
  }
  return result;
}
async function cgSaveAllocations(allocations = null) {
  const d = cashGroupState.draft; if (!d) throw new Error("Aucun dossier actif.");
  cgAssertDraftSession();
  const rows = allocations || cgReadManualAllocations();
  cgBusy(true);
  try {
    cashGroupState.draft = await cgMutation(`/${d.dossier.id}/allocations`, "PUT", { revision: d.dossier.revision, allocations: rows });
    cashGroupState.mutationRetry = null; cashGroupState.allocations = cashGroupState.draft.allocations;
    cgRenderDraft(); cgMessage("Ventilation enregistrée par le service métier.");
  } catch (error) { cgFailure(error); }
  finally { cgBusy(false); }
}
async function cgAutoAllocate() {
  const d = cashGroupState.draft; if (!d) throw new Error("Aucun dossier actif.");
  cgAssertDraftSession();
  const proposed = await cgRequest(`/${d.dossier.id}/allocations/proposition?revision=${d.dossier.revision}`);
  if (!window.confirm("Enregistrer explicitement la proposition automatique retournée par le service ?")) return;
  await cgSaveAllocations(proposed);
}
function cgRenderReview() {
  const root = cg("review"); if (!root) return; root.replaceChildren();
  const d = cashGroupState.draft; if (!d) return;
  const due = Number(d.totaux.du_xaf || 0);
  const payments = cashGroupState.payments.length ? cashGroupState.payments : d.reglements.map(row => ({ ...row }));
  const net = payments.reduce((sum, row) => sum + Math.max(0, Number(row.montant || 0) - Number(row.rendu || 0)), 0);
  const list = document.createElement("ul");
  for (const line of [`Tickets : ${d.ventes.length}`, `Total dû : ${cgMoney(due)}`, `Règlements nets : ${cgMoney(net)}`, `Écart à régler : ${cgMoney(due - net)}`, `Ventilation : ${d.totaux.allocation_valide ? "valide" : "à vérifier"}`]) {
    const item = document.createElement("li"); item.textContent = line; list.append(item);
  }
  for (const payment of payments) {
    const item = document.createElement("li"); item.textContent = `${payment.mode} · brut ${cgMoney(payment.montant)} · rendu ${cgMoney(payment.rendu || 0)} · net ${cgMoney(Number(payment.montant || 0) - Number(payment.rendu || 0))}`; list.append(item);
  }
  const allocatedBySale = new Map();
  for (const row of [...cg("allocation-body").querySelectorAll("tr")]) {
    const cells = [...row.querySelectorAll("input")];
    cells.forEach((input, index) => { const value = cgInt(input.value); if (Number.isSafeInteger(value) && value > 0) { const id = d.ventes[index]?.vente_id; if (id) allocatedBySale.set(id, (allocatedBySale.get(id) || 0) + value); } });
  }
  for (const sale of d.ventes) {
    const allocated = allocatedBySale.get(sale.vente_id) || 0, difference = allocated - Number(sale.montant_du);
    const item = document.createElement("li"); item.textContent = `Vente ${sale.vente_id.slice(0, 8)} · alloué ${cgMoney(allocated)} · dû ${cgMoney(sale.montant_du)} · écart ${cgMoney(difference)}`; list.append(item);
    const loyalty = cashGroupState.loyalty.get(sale.vente_id);
    const loyaltyItem = document.createElement("li");
    loyaltyItem.textContent = loyalty?.selected && loyalty.account
      ? `Fidélité vente ${sale.vente_id.slice(0, 8)} · compte ${loyalty.account.client.nom} · solde actuel ${loyalty.account.points} points`
      : loyalty?.status === "error" || loyalty?.status === "loading"
        ? `Fidélité vente ${sale.vente_id.slice(0, 8)} · à vérifier : ${loyalty.message}`
        : `Fidélité vente ${sale.vente_id.slice(0, 8)} · ${loyalty?.status === "blocked" ? loyalty.message : "non appliquée"}`;
    list.append(loyaltyItem);
  }
  root.append(list);
  cg("allocation-status").textContent = `Total dû ${cgMoney(d.totaux.du_xaf)} · Total alloué ${cgMoney(d.totaux.alloue_xaf)} · ${d.totaux.allocation_valide ? "ventilation équilibrée" : "ventilation non validée"}`;
}
async function cgAbandon() {
  const d = cashGroupState.draft; if (!d || d.dossier.etat !== "BROUILLON") return;
  if (!window.confirm("Abandonner ce brouillon ? Aucune vente ne sera encaissée.")) return;
  cgBusy(true);
  try {
    cashGroupState.draft = await cgMutation(`/${d.dossier.id}/abandonner`, "POST", { revision: d.dossier.revision });
    cgResetDraftTransient(); cgRenderDraft(); cgMessage("Brouillon abandonné. Aucune écriture financière n’a été effectuée.");
  } catch (error) { cgFailure(error); }
  finally { cgBusy(false); }
}
function cgRenderReceipts() {
  const d = cashGroupState.draft; const result = d?.resultat;
  const section = cg("receipts"); section.hidden = !result;
  if (!result) return;
  cg("receipt-summary").textContent = `Reçu collectif ${result.recu_collectif.reference} · ${cgMoney(result.recu_collectif.total_xaf)} · ${result.recus_individuels.length} reçu(s) individuel(s). Les points affichés proviennent des reçus serveur par vente.`;
  const actions = cg("receipt-actions"); actions.replaceChildren();
  const group = document.createElement("button"); group.type = "button"; group.textContent = "Ouvrir le reçu collectif";
  group.addEventListener("click", () => cashPDF(`/groupes/${d.dossier.id}/recu.pdf`, false).catch(cgFailure)); actions.append(group);
  for (const receipt of result.recus_individuels) {
    const button = document.createElement("button"); button.type = "button"; button.className = "secondary";
    const fidelity = receipt.instantane?.fidelite;
    const points = fidelity ? `${fidelity.points_acquis ?? fidelity.points ?? 0} point(s) · ${fidelity.client?.nom || "titulaire fidélité"}` : "sans fidélité";
    button.textContent = `Reçu individuel ${receipt.instantane?.numero_encaissement || receipt.id.slice(0, 8)} · ${points}`;
    button.addEventListener("click", () => cashPDF(`/recus/${receipt.id}/pdf`, false).catch(cgFailure)); actions.append(button);
  }
}
async function cgFinalize() {
  if (cashGroupState.busy) return;
  if (!cgCanFinalize()) throw new Error("Le dossier, la session ou les allocations ne permettent pas la finalisation. Rechargez et vérifiez les données.");
  const d = cashGroupState.draft;
  let revisionConflict = false;
  const payload = { revision: d.dossier.revision, revision_session: cashState.session.revision, fidelite: cgLoyaltyPayload() };
  const fingerprint = JSON.stringify(payload);
  if (cashGroupState.finalisationPayload !== fingerprint) {
    const key = cgFinalizationKey(d.dossier.id, fingerprint);
    cashGroupState.finalisationPayload = fingerprint;
    cashGroupState.finalisationKey = key;
  }
  const recap = [...cg("review").querySelectorAll("li")].map(item => item.textContent).join("\n");
  if (!window.confirm(`Finaliser définitivement ce dossier ?\n\n${recap}\n\nCette opération encaisse toutes les ventes du dossier.`)) return;
  cgBusy(true);
  try {
    const result = await cgMutation(`/${d.dossier.id}/finaliser`, "POST", payload, cashGroupState.finalisationKey);
    cashGroupState.mutationRetry = null;
    cashGroupState.draft = result;
    if (result.dossier?.etat !== "FINALISE" || !result.resultat?.recu_collectif || !Array.isArray(result.resultat?.recus_individuels)) {
      throw new Error("La réponse du serveur ne contient pas le résultat finalisé attendu. Rechargez le dossier pour vérifier son état.");
    }
    cashGroupState.finalisationKey = null; cashGroupState.finalisationPayload = null;
    cgClearFinalizationKey(d.dossier.id);
    try { localStorage.removeItem(cgLoyaltyStorageKey(d.dossier.id)); } catch (_) {}
    cgRenderDraft();
    cgMessage("Finalisation confirmée par le serveur. Consultez les reçus associés ci-dessous.");
  } catch (error) {
    cgFailure(error);
    if (error.status === 409) {
      await cgReload();
      revisionConflict = true;
    }
  } finally { cgBusy(false); }
  if (revisionConflict) {
    cg("status").textContent += " · Conflit de révision, données rechargées";
    cgMessage("Le serveur a détecté une modification concurrente. Vérifiez les montants et la ventilation avant de confirmer à nouveau.", true);
  }
}
function cgReset() {
  cashGroupState.mode = "INDIVIDUEL";
  cashGroupState.page = 1; cashGroupState.selected.clear(); cashGroupState.saleDetails.clear(); cashGroupState.draft = null;
  cashGroupState.loyalty.clear();
  cashGroupState.payments = []; cashGroupState.allocations = []; cashGroupState.mutationRetry = null;
  cashGroupState.finalisationKey = null; cashGroupState.finalisationPayload = null;
  if (cg("panel")) {
    cg("panel").hidden = true; cg("draft").hidden = true; cg("sales").replaceChildren();
    $("cash-mode-group").setAttribute("aria-pressed", "false"); $("cash-mode-individual").setAttribute("aria-pressed", "true");
    $("cash-waiting").closest("article").hidden = false;
  }
}

$("cash-mode-individual").addEventListener("click", () => cgSetMode("INDIVIDUEL"));
$("cash-mode-group").addEventListener("click", () => cgSetMode("GROUPE"));
cg("refresh").addEventListener("click", () => cgLoadSales().catch(cgFailure));
cg("prev").addEventListener("click", () => { cashGroupState.page--; cgLoadSales().catch(cgFailure); });
cg("next").addEventListener("click", () => { cashGroupState.page++; cgLoadSales().catch(cgFailure); });
cg("create").addEventListener("click", () => cgCreateDraft().catch(cgFailure));
cg("add-selected").addEventListener("click", () => cgAddSelected().catch(cgFailure));
cg("resume").addEventListener("click", () => cgResume());
cg("reload").addEventListener("click", () => cgReload());
cg("add-payment").addEventListener("click", () => { cashGroupState.payments.push({ mode: (cashState.context?.configuration?.modes || ["ESPECES"])[0], montant: "", rendu: "0", confirmation_id: null }); cgRenderPayments(); });
cg("save-payments").addEventListener("click", () => cgSavePayments().catch(cgFailure));
cg("auto").addEventListener("click", () => cgAutoAllocate().catch(cgFailure));
cg("save-allocations").addEventListener("click", () => cgSaveAllocations().catch(cgFailure));
cg("abandon").addEventListener("click", () => cgAbandon());
$("cash-group-finalise").addEventListener("click", () => cgFinalize().catch(cgFailure));
cg("create").disabled = true; cg("add-selected").disabled = true;
cg("resume-id").addEventListener("keydown", event => { if (event.key === "Enter") { event.preventDefault(); cgResume(); } });
try { cg("resume-id").value = localStorage.getItem(cgDraftStorageKey()) || ""; } catch (_) {}

// Reprendre l'actualisation existante sans modifier le parcours individuel.
const cgOriginalLoad = cashLoad;
cashLoad = async function (propagate = false) {
  await cgOriginalLoad(propagate);
  if (cashGroupState.mode === "GROUPE" && authState.me && shellState.view === "encaissement") {
    await cgLoadSales().catch(error => cgMessage(error.message, true));
  }
};
const cgOriginalReset = authReset;
authReset = function () { cgReset(); cgOriginalReset(); };
const cgOriginalSync = shellSync;
shellSync = function () {
  const previous = cashState.key;
  cgOriginalSync();
  if (previous && cashState.key && previous !== cashState.key) cgReset();
};
