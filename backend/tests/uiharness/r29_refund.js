// r29 — ورقة «استرداد شراء دورة» في v2-d3.js الحقيقي داخل node:vm (بلا شبكة ولا متصفح): DOM مصغّر + `EP.api` بجدول ردود.
//   stdin : {"preview": {...}, "refund": {"ok": {...}} | {"fail": {"status": 502, "data": {...}}} | {"fail": {}},
//            "rechecks": [{...}, ...]   // ردود refund-preview اللي بعد الفشل بالترتيب (الأخيرة تتكرر)
//            "confirmedRows": [...]   // اختياري: صفوف /platform-manual-payments?status=confirmed قبل وبعد الاسترداد
//            "who": "receipts" | "person" }
//   stdout: {"err": "...", "go": {"text", "disabled"}, "closed": bool, "done": bool, "toast": "...", "refunded": {...}, "calls": [...], "rows": [...]}
const vm = require('vm');
const fs = require('fs');
const path = require('path');
process.on('unhandledRejection', (e) => { process.stderr.write('UNHANDLED ' + (e && e.stack || e) + '\n'); });
const input = JSON.parse(fs.readFileSync(0, 'utf8'));
const dc = path.join(__dirname, '..', '..', '..', 'dashboard-cloud');
const calls = [];
const timers = [];
let closed = false, doneCalled = false;
const toasts = [];

function mkEl(html) { return { dataset: {}, disabled: false, textContent: '', value: '', onclick: null, innerHTML: html || '', attrs: {},
  setAttribute(k, v) { this.attrs[k] = v; }, getAttribute(k) { return this.attrs[k] || null; } }; }
let registry = {};
function register(html) { registry = {}; String(html).replace(/id="([^"]+)"/g, (m, id) => { registry[id] = mkEl(''); return m; }); }
let stageHtml = '';
const stage = { attrs: {}, setAttribute(k, v) { this.attrs[k] = v; }, getAttribute(k) { return this.attrs[k] || null; },
  get innerHTML() { return stageHtml; }, set innerHTML(h) { stageHtml = h; register(h); } };
const sheet = { dataset: {}, onclick: null, querySelector(sel) {
  if (sel === '.v3-stage') return stage;
  if (sel[0] === '#') return registry[sel.slice(1)] || null;
  return null; }, querySelectorAll() { return []; } };

const sb = { console, setTimeout(fn) { timers.push(fn); return timers.length; }, clearTimeout() {}, setInterval() { return 1; }, clearInterval() {}, Promise, JSON, Math, Date, Intl, Object, Array, String, Number, Error, RegExp };
sb.window = sb;
sb.document = { readyState: 'complete', body: { contains(el) { return el === sheet ? !closed : true; } }, getElementById(id) { return id === 'epModal' && !closed ? sheet : null; },
                querySelector() { return null; }, querySelectorAll() { return []; }, addEventListener() {}, createElement() { return mkEl(''); } };
sb.localStorage = { getItem() { return null; }, setItem() {} };
sb.matchMedia = () => ({ matches: false });
sb.toast = function (t) { toasts.push(String(t)); };
sb.openModal = function (title, html) { closed = false; stageHtml = ''; register(html); stage.attrs = {}; return sheet; };
sb.closeModal = function () { closed = true; };
sb.V2_HOST = { current: () => (input.who === 'person' ? 'v2person' : 'v2m_receipts') };
sb.V2 = { refreshAll() { calls.push('REFRESH_ALL'); } };
const rechecks = (input.rechecks || []).slice();
sb.EP = { authed: true, state: {}, data: {},
  api(p, opts) {
    const m = (opts && opts.method) || 'GET';
    calls.push(m + ' ' + p);
    if (/\/refund-preview$/.test(p) && !calls.slice(0, -1).some((c) => /refund-preview$/.test(c))) return Promise.resolve(input.preview);
    if (/\/refund-preview$/.test(p)) {
      const r = rechecks.length > 1 ? rechecks.shift() : rechecks[0];
      if (r && r.fail) { const e = new Error('x'); Object.assign(e, r.fail); return Promise.reject(e); }
      return Promise.resolve(r);
    }
    if (/\/refund$/.test(p) && m === 'POST') {
      if (input.refund.ok) return Promise.resolve(input.refund.ok);
      const e = new Error('x'); Object.assign(e, input.refund.fail || {}); return Promise.reject(e);
    }
    if (/platform-manual-payments/.test(p)) return Promise.resolve({ payments: input.confirmedRows || [] });
    return Promise.resolve({});
  } };
vm.createContext(sb);
for (const f of ['v2-logic.js', 'v2-d3.js']) vm.runInContext(fs.readFileSync(path.join(dc, f), 'utf8'), sb);
const tick = () => new Promise((r) => setImmediate(r));
async function settle(n) { for (let i = 0; i < (n || 12); i++) { await tick(); } }
async function flushTimers() { for (let i = 0; i < 8; i++) { const t = timers.splice(0); t.forEach((f) => { try { f(); } catch (e) {} }); await settle(6); } }
(async () => {
  if (input.confirmedRows) sb.V2D3._src.confirmed = { state: 'ready', data: { payments: input.confirmedRows }, status: 0, seq: 0 };
  sb.V2D3.openRefund('pay-1', function () { doneCalled = true; });
  await settle();
  if (!registry.v3_rfr) { process.stdout.write(JSON.stringify({ stageHtml, err: 'no form', calls })); process.exit(0); }
  registry.v3_rfr.value = 'تجربة';
  registry.v3_rfnext.onclick();
  await settle();
  const go = registry.v3_rfgo;
  go.onclick();
  await settle();
  await flushTimers();
  const out = { err: registry.v3err ? registry.v3err.innerHTML : '', go: { text: go.textContent, disabled: go.disabled }, closed, done: doneCalled, toast: toasts.join('|'),
                refunded: sb.V2D3._state.refunded, calls, stage: stage.attrs['data-stage'] };
  process.stdout.write(JSON.stringify(out));
  process.exit(0);
})().catch((e) => { process.stdout.write(JSON.stringify({ error: String(e && e.stack || e) })); process.exit(1); });
