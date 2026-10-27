// Fonctions applicatives réelles ; composants et transport simulés, aucune base.
const fs = require('node:fs');
const vm = require('node:vm');
const assert = require('node:assert/strict');
const path = require('node:path');
const web = path.join(__dirname, '../src/neosys_pharma/presentation/web');
const cash = fs.readFileSync(path.join(web, 'caisse.js'), 'utf8');
const group = fs.readFileSync(path.join(web, 'encaissement_groupe.js'), 'utf8');
let checks = 0;
function check(value, message) { assert.ok(value, message); checks++; }
function element() {
  return { options: [], children: [], value: '', dataset: {},
    append(...items) { this.children.push(...items); },
    replaceChildren() { this.children = []; },
    add(option) { this.options.push(option); },
    setAttribute() {}, setCustomValidity() {}, addEventListener() {} };
}
const provider = { id: 'air', mode: 'MOBILE_MONEY', libelle: 'Airtel', actif: true };
let modal, addPayment, groupMessage, calls = [];
const state = { epoch: 1, sale: { id: 'sale', revision: 2, totaux: { ttc: 100 }, confirmations: [] },
  session: { id: 'session', revision: 1 }, account: null };
const paymentsRoot = element();
const context = {
  cashState: state, shellState: { view: 'encaissement' }, Number, Error,
  cashRefreshFidelity: async () => {}, cashRenderFinancialSummary() {}, venteMoney: String, stockText() {},
  stockField(form, name) { return form.elements[name] = element(); },
  cashModal(title, permission, build, save) {
    const form = { elements: {}, append() {}, addEventListener() {}, querySelector:element }; const init=build(form); if(init)init({form}); modal = { title, permission, form, save };
  },
  cashRequest: async (route, method, body) => { calls.push({ route, method, body }); return state.sale; },
  cashGroupState: { payments: [], draft: { dossier: { etat: 'BROUILLON' } } },
  cg: id => id === 'add-payment' ? { addEventListener(event, callback) { addPayment = callback; } } : paymentsRoot,
  cgMessage(message) { groupMessage = message; }, cgInt: Number, cgConfirmationOptions: () => [], cgRenderReview() {},
  document: { createElement: element },
  Option: function(label, value) { this.label = label; this.value = value; },
};
vm.createContext(context);
for (const name of ['cashPaymentChoices', 'cashPay']) {
  vm.runInContext(cash.split('\n').find(line => line.startsWith(`function ${name}(`) || line.startsWith(`async function ${name}(`)), context);
}
const render = group.slice(group.indexOf('function cgRenderPayments()'), group.indexOf('\nfunction ', group.indexOf('function cgRenderPayments()') + 1));
vm.runInContext(render, context);
vm.runInContext(group.split('\n').find(line => line.startsWith('cg("add-payment").addEventListener')), context);
const cases = [
  ['espèces actives', { modes: ['ESPECES'], moyens: [] }, ['ESPECES']],
  ['espèces inactives', { modes: [], moyens: [] }, []],
  ['famille sans fournisseur', { modes: ['MOBILE_MONEY'], moyens: [] }, []],
  ['fournisseur actif', { modes: ['MOBILE_MONEY'], moyens: [provider] }, ['MOBILE_MONEY:air']],
  ['fournisseur désactivé', { modes: ['MOBILE_MONEY'], moyens: [{ ...provider, actif: false }] }, []],
  ['famille désactivée', { modes: [], moyens: [provider] }, []],
  ['fournisseur incompatible', { modes: ['CARTE'], moyens: [provider] }, []],
  ['identité manquante', { modes: ['MOBILE_MONEY'], moyens: [{ ...provider, id: null }] }, []],
];
(async () => {
  for (const [label, config, expected] of cases) {
    state.context = { configuration: config };
    const choices = context.cashPaymentChoices(config, true);
    assert.deepEqual(Array.from(choices, x => x.key), expected); checks++;
    check(context.cashPaymentChoices(config).every(x => x.mode !== 'ESPECES'), label + ': espèces exclues des confirmations');
    check(choices.every(x => x.mode === 'ESPECES' || x.moyen_id), label + ': identité explicite');
    // Le rendu groupé réel construit ses options depuis les mêmes choix.
    context.cashGroupState.payments = [{ mode: null, montant: '' }];
    context.cgRenderPayments();
    const select = paymentsRoot.children[0].children[1];
    assert.deepEqual(select.options.map(x => x.value), expected); checks++;
    context.cashGroupState.payments = [];
    addPayment();
    check(context.cashGroupState.payments.length === (expected.length ? 1 : 0), label + ': ajout groupé sans repli espèces');
    if (!expected.length) check(groupMessage === 'Aucun moyen de paiement actif.', label + ': état vide explicite');
  }
  state.context.configuration = { modes: ['ESPECES'], moyens: [] };
  await context.cashPay();
  check(modal.form.elements.especes, 'champ espèces actif');
  check(modal.permission === 'caisse.encaisser', 'permission de modale conservée');
  modal.form.elements.confirme.checked = true;
  await modal.save({ especes: '100' }, { cle: 'cash' }, modal);
  check(calls[0].body.reglements[0].mode === 'ESPECES', 'payload espèces actif');
  check(calls[0].body.reglements[0].montant === '100', 'montant conservé');

  // Relecture de configuration : nouvelle ouverture sans espèces, historique intact.
  state.sale.confirmations = [{ id: 'historical', mode: 'CARTE', moyen_id: 'old', moyen_libelle: 'Ancien', montant: 100 }];
  const history = JSON.stringify(state.sale.confirmations);
  state.context.configuration = { modes: [], moyens: [] };
  await context.cashPay();
  check(!modal.form.elements.especes, 'espèces absentes après actualisation');
  check(modal.form.elements.confirmation_historical, 'confirmation historique toujours lisible');
  check(JSON.stringify(state.sale.confirmations) === history, 'historique inchangé');
  modal.form.elements.confirmation_historical.checked = true;
  modal.form.elements.confirme.checked = true;
  calls = [];
  await modal.save({ especes: '999' }, { cle: 'history' }, modal);
  check(calls[0].body.reglements.length === 1 && calls[0].body.reglements[0].confirmation_id === 'historical', 'aucune nouvelle espèce injectée ; identité historique conservée, validation serveur');

  state.sale.confirmations = [];
  await assert.rejects(context.cashPay(), /Aucun moyen de paiement actif/); checks++;
  check(state.paymentPreparation === null, 'préparation libérée après refus');
  state.context.configuration = { modes: ['MOBILE_MONEY'], moyens: [provider] };
  await context.cashPay();
  check(!modal.form.elements.especes, 'famille non espèces seule sans champ espèces');
  state.context.configuration = { modes: ['ESPECES'], moyens: [] };
  await context.cashPay();
  check(modal.form.elements.especes, 'réactivation relue à la nouvelle ouverture');
  console.log(`${checks} assertions B03 réussies (fonctions réelles, composants/HTTP simulés)`);
})().catch(error => { console.error(error); process.exitCode = 1; });
