// R24 م٣ — يرسم شاشات مستويات العقل (v2-levels.js + v2-home.js + v2-strip.js + v2s/brain.js) في node:vm بمستند مزيّف ويضغط على الأزرار.
//   stdin : {"api": {"GET /v2/brain/levels": {...}, "PUT /v2/brain/levels/x": {...}, ...}   ردود جاهزة بمفتاح «الطريقة المسار»؛ قيمة {"__status": 409, "error": "..."} ⇒ رفض
//            "inbox": [rows], "brain": [items], "mount": "<قسم>", "mode": "board"|"focus"|"tab", "seg": "levels"|"alone", "wire": false,
//            "steps": [ {"click":"<selector>","attr":{...},"idx":0} | {"strip":"<selector>","attr":{...}} | {"modalClick":"<selector>"} ]}
//   stdout: {"html": "<الشاشة>", "strip": "<الشريط>", "calls": [...], "modal": {...}, "toasts": [...]}
// ⛔ لا شبكة ولا DOM حقيقي: `fetch` مش موجود أصلًا، و`EP.api` دالة في الذاكرة بتسجّل كل نداء.
const vm = require('vm');
const fs = require('fs');
const path = require('path');
const input = JSON.parse(fs.readFileSync(0, 'utf8'));
const dc = path.join(__dirname, '..', '..', '..', 'dashboard-cloud');
const calls = [];
const handlers = [];
const sets = [];     // كل كتابة على عنصر لُقط بـ querySelector (مثلًا رسالة خطأ جوه ورقة)
function needleRe(sel) {
  let m;
  if ((m = /^\[data-a="([^"]+)"\]$/.exec(sel))) return new RegExp('data-a="' + m[1] + '"', 'g');
  if ((m = /^#(.+)$/.exec(sel))) return new RegExp('id="' + m[1] + '"', 'g');
  if ((m = /^\.(.+)$/.exec(sel))) return new RegExp('class="[^"]*\\b' + m[1].replace(/[-]/g, '\\-') + '\\b[^"]*"', 'g');
  if ((m = /^\[(data-[a-z]+)\]$/.exec(sel))) return new RegExp(m[1] + '(?==|\\s|>)', 'g');
  return new RegExp('\u0000', 'g');
}
function tagAttrs(html, idx) {
  const lt = html.lastIndexOf('<', idx), gt = html.indexOf('>', idx);
  const tag = html.slice(lt, gt + 1), attrs = {};
  tag.replace(/([\w:-]+)="([^"]*)"/g, (m, k, v) => { attrs[k] = v; return m; });
  return attrs;
}
function stubEl(html, attrs) {
  attrs = attrs || {};
  let inner = html || '';
  const el = { get innerHTML() { return inner; }, set innerHTML(v) { inner = v; if (el._sel) sets.push([el._sel, String(v)]); }, style: {}, dataset: {}, classList: { add() {}, remove() {}, toggle() {} }, children: [], onclick: null, disabled: false, value: '', textContent: '', hidden: false,
    _attrs: attrs, addEventListener(t, f) { (el._listeners = el._listeners || []).push(f); }, setAttribute(k, v) { attrs[k] = v; }, getAttribute(k) { return k in attrs ? attrs[k] : null; },
    remove() {}, contains() { return true; }, closest() { return null; }, focus() {}, scrollIntoView() {} };
  const pick = (sel, which) => {
    const re = needleRe(sel), found = [];
    let m;
    while ((m = re.exec(el.innerHTML))) found.push(m.index);
    return which === 'all' ? found : found.slice(0, 1);
  };
  el.querySelector = function (sel) {
    const hit = pick(sel, 'first');
    const b = stubEl('', hit.length ? tagAttrs(el.innerHTML, hit[0]) : {}); b._sel = sel; b._i = 0; b._hit = hit.length > 0; handlers.push(b);
    return hit.length ? b : null;
  };
  el.querySelectorAll = function (sel) {
    return pick(sel, 'all').map((idx, i) => { const b = stubEl('', tagAttrs(el.innerHTML, idx)); b._sel = sel; b._i = i; b._hit = true; handlers.push(b); return b; });
  };
  return el;
}
const modals = [];
const toasts = [];
const stripEl = stubEl('');
const sb = { console, setTimeout: (f, ms) => { if (ms && ms >= 1000) return 0; f(); return 0; }, clearTimeout() {}, setInterval() { return 1; }, clearInterval() {}, Promise, JSON, Math, Date, Intl, Object, Array, String, Number, Error, RegExp, WeakMap };
sb.window = sb;
sb.document = { readyState: 'complete', addEventListener() {}, removeEventListener() {}, getElementById() { return null; }, querySelector() { return null; }, querySelectorAll() { return []; }, activeElement: null, createElement() { return stubEl(''); }, body: { appendChild() {} } };
sb.matchMedia = () => ({ matches: false });
sb.localStorage = { getItem() { return null; }, setItem() {} };
let modalMark = 0;
sb.openModal = function (title, html) { modals.push({ title, html }); const m = stubEl('<button data-x></button>' + html); modalMark = handlers.length; return m; };
sb.closeModal = function () {};
sb.toast = (t) => { toasts.push(t); };
sb.INBOX = input.inbox || []; sb.INBOX_SNOOZED = []; sb.INBOX_FAILED = []; sb.INBOX_TRUNCATED = [];
const st0 = { opsQueue: 'ready', inbox: 'ready', walletPayouts: 'ready', invites: 'ready', pendingUsers: 'ready', market: 'ready', aiAgents: 'ready', inviteSettings: 'ready' };
const clone = (x) => JSON.parse(JSON.stringify(x));
sb.EP = {
  authed: true, role: 'admin', user: { name: 'عبد الرحمن عطية' }, state: st0,
  data: { opsQueue: input.queue || {}, walletPayouts: { rows: [], hidden: [], count: 0 }, invites: { rows: [] }, pendingUsers: { rows: [] }, market: { rows: [] }, snooze: input.snooze || { map: {}, ok: true, at: 1 }, aiAgents: { agents: [] }, inviteSettings: {} },
  ensure() {}, reload() {},
  api(p, o) {
    const m = (o && o.method) || 'GET', key = m + ' ' + p;
    calls.push({ fn: 'api', m, path: p, body: o && o.body !== undefined ? o.body : undefined });
    const hit = (input.api || {})[key];
    if (hit === undefined) return Promise.reject({ status: 404, data: {} });
    if (hit && hit.__status) return Promise.reject({ status: hit.__status, data: hit });
    return Promise.resolve(clone(hit));
  },
  decideInboxItem(row, action, after, note) { calls.push({ fn: 'decideInboxItem', kind: row.apiKind, id: row.apiId, action, note: note || '' }); return Promise.resolve({ ok: true }); },
  snoozeItem() { return Promise.resolve({ ok: true }); }, dismissItem() { return Promise.resolve({ ok: true }); }, restoreItem() { return Promise.resolve({ ok: true }); },
  decideInvite() { return Promise.resolve({ ok: true }); }, resolveInboxItem() { return Promise.resolve({ ok: true }); }, expertFileSend() { return Promise.resolve({ ok: true }); },
  post(p, body) { calls.push({ fn: 'post', path: p, body }); return Promise.resolve({}); },
};
sb.V2_HOST = {
  isHome: () => input.mode !== 'tab', current: () => (input.mode === 'tab' ? 'v2s_brain' : 'home'),
  openRow: () => true, openReading: () => true, openSection(k, t) { calls.push({ fn: 'openSection', k, t }); }, goOps() {}, go() {},
};
sb.V2SHELL = { on: true };
vm.createContext(sb);
const load = (f) => vm.runInContext(fs.readFileSync(path.join(dc, f), 'utf8'), sb);
load('v2-logic.js'); load('v2-home.js'); load('v2-strip.js'); load('v2-levels.js');
if (input.mode === 'tab') { load('v2s/_registry.js'); load('v2s/brain.js'); }
if (input.brain) sb.V2BRAIN = { pending: () => input.brain, decorate: (c) => c, prefetch() {}, sig: () => '1', listen: () => () => {}, reload() {}, act(c, a, cb) { cb({ ok: true, text: 'تم' }); } };
Object.keys(input.info || {}).forEach((k) => sb.V2STRIP.info(k, input.info[k]));      // سطر «للعلم» اللي بتبعته الأقسام
const v = stubEl('');
function match(h, attr) { if (!attr) return true; return Object.keys(attr).every((k) => h._attrs && h._attrs[k] === attr[k]); }
function find(sel, idx, attr) {
  const hs = handlers.filter((h) => h._sel === sel && h._hit !== false && (idx == null || h._i === idx) && match(h, attr));
  return hs[hs.length - 1] || null;
}
const tick = () => new Promise((r) => setImmediate(r));
async function flush() { for (let i = 0; i < 6; i++) await tick(); }
function draw() {
  handlers.length = 0;
  if (input.mode === 'tab') {
    if (input.seg) sb.V2SEC.brain.want(input.seg);
    sb.V2SEC.brain.render('v2s_brain', v);
  } else {
    if (input.mode === 'focus') { const d = sb.V2.split().decisions.slice(); sb.V2._state.deck = d; sb.V2._state.total = d.length; sb.V2._state.mode = 'focus'; }
    sb.V2.render(v);
    if (input.mount) sb.V2STRIP.mount(input.mount, stripEl, false);
  }
}
(async () => {
  draw(); await flush(); draw(); await flush(); draw();
  for (const stp of (input.steps || [])) {
    if (stp.modalClick) { const hs = handlers.slice(modalMark).filter((h) => h._sel === stp.modalClick && h._hit); const h = hs[stp.idx || 0]; if (h && h.onclick) await h.onclick(); else calls.push({ fn: 'NO_MODAL_HANDLER', sel: stp.modalClick }); }
    else if (stp.strip) { handlers.length = 0; sb.V2STRIP.mount(input.mount, stripEl, false); const b = find(stp.strip, stp.idx, stp.attr); if (b && b.onclick) await b.onclick(); else calls.push({ fn: 'NO_STRIP_HANDLER', sel: stp.strip, attr: stp.attr }); }
    else if (stp.click) { draw(); const b = find(stp.click, stp.idx, stp.attr); if (b && b.onclick) await b.onclick(); else calls.push({ fn: 'NO_HANDLER', sel: stp.click, attr: stp.attr }); }
    await flush();
  }
  draw(); await flush(); draw();
  const L = sb.V2L, split = sb.V2.split();
  const sums = { tiles: sb.V2.tiles().map((t) => ({ key: t.key, count: t.count })), counts: split.counts, deckN: split.decisions.length, strips: {} };
  L.SECTION_KEYS.forEach((k) => { const st = sb.V2.strip(k); sums.strips[k] = { n: st.n, ids: st.cards.map((c) => c.id), homes: st.cards.map((c) => c.home) }; });
  const out = { sums, html: v.innerHTML, sets, calls, modal: modals.length ? modals[modals.length - 1] : null, modals: modals.map((m) => m.title), toasts };
  if (input.mount) { sb.V2STRIP.mount(input.mount, stripEl, false); out.strip = stripEl.innerHTML; }
  process.stdout.write(JSON.stringify(out, (k, x) => (x === Infinity ? null : x)));
})();
