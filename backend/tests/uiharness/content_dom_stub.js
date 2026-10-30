// حاضنة دنيا لتشغيل dashboard-cloud/v2s/content.js في node بلا متصفح: window وdocument وEP مزيّفة، صفر شبكة.
// الدخل (stdin JSON): { state, data, tab, call, args } ⇒ الخرج: { html, modals, reloads }.
const path = require('path'), fs = require('fs');
const input = JSON.parse(fs.readFileSync(0, 'utf8'));
const DC = input.dc;
globalThis.window = globalThis;
const reloads = [], modals = [];
const fakeEl = () => ({ dataset: {}, querySelector: () => fakeEl(), querySelectorAll: () => [], contains: () => true, set onclick(v) {}, get onclick() { return null; } });
globalThis.document = { body: { contains: () => true }, getElementById: () => null, querySelector: () => null, querySelectorAll: () => [] };
globalThis.setInterval = () => 0; globalThis.clearInterval = () => {}; globalThis.setTimeout = (f) => 0; globalThis.clearTimeout = () => {};
window.openModal = (title, html) => { modals.push({ title, html }); return fakeEl(); };
window.closeModal = () => {};
window.V2_HOST = { current: () => 'topics' };
window.v2Snapshot = () => ({ topicsTab: input.tab || 'pipeline' });
window.EP = {
  authed: true, state: input.state || {}, data: input.data || {}, lastError: '',
  ensure: () => {}, reload: (k, cb) => { reloads.push(k); const was = window.EP.state[k]; window.EP.state[k] = 'loading'; if (cb) cb(); if (input.finish) { window.EP.state[k] = 'ready'; if (cb) cb(); } },
};
Object.assign(window, input.globals || {});
require(path.join(DC, 'v2-logic.js'));
require(path.join(DC, 'v2s', 'content.js'));
const API = window.V2SEC.content;
const view = { innerHTML: '', contains: () => true };
API.render('topics', view);
let ret = null;
if (input.call) ret = API._t[input.call].apply(null, input.args || []);
let html2 = null;
if (input.redraw) { API._tick(0); html2 = view.innerHTML; }
console.log(JSON.stringify({ html: view.innerHTML, html2, modals, reloads, ret, bg: Object.keys(API._state.bg) }));
