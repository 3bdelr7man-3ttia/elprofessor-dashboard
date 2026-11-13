// R24 م٢ — يرسم اللوحة وشريط «محتاج قرارك» (v2-home.js + v2-strip.js) في node:vm بمستند مزيّف ويضغط على الأزرار.
//   stdin : {"inbox": [rows], "snoozed": [...], "payouts": [], "queue": {...}, "invites": [rows], "brain": [items], "snooze": {map...},
//            "mount": "<قسم>", "stateOverride": {inbox: 'error'}, "steps": [ {"mode":"focus"} | {"click":"<selector>","attr":{...},"idx":0} | {"modalClick":..} | {"modalType":..} ]}
//   stdout: {"html": "<اللوحة>", "strip": "<الشريط>", "calls": [...], "deck": [...ids], "modal": {...}, "tiles": [...], "counts": {...}}
// ⛔ لا شبكة ولا DOM حقيقي: `fetch` مش موجود أصلًا، و`EP` دالة في الذاكرة بتسجّل النداءات (decide/resolve/send/invite/snooze…).
const vm = require('vm');
const fs = require('fs');
const path = require('path');
const input = JSON.parse(fs.readFileSync(0, 'utf8'));
const dc = path.join(__dirname, '..', '..', '..', 'dashboard-cloud');
const calls = [];
const handlers = [];
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
  const el = { innerHTML: html || '', style: {}, dataset: {}, classList: { add() {}, remove() {}, toggle() {} }, children: [], onclick: null, disabled: false, value: '', textContent: '', hidden: false,
    _attrs: attrs, addEventListener(t, f) { (el._listeners = el._listeners || []).push(f); }, setAttribute(k, v) { attrs[k] = v; }, getAttribute(k) { return k in attrs ? attrs[k] : null; },
    remove() {}, contains() { return false; }, closest() { return null; }, focus() {}, scrollIntoView() {} };
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
const stripEl = stubEl('');
const sb = { console, setTimeout: (f) => { f(); return 0; }, clearTimeout() {}, setInterval() { return 1; }, clearInterval() {}, Promise, JSON, Math, Date, Intl, Object, Array, String, Number, Error, RegExp };
sb.window = sb;
sb.document = { readyState: 'complete', addEventListener() {}, removeEventListener() {}, getElementById() { return null; }, querySelector() { return null; }, createElement() { return stubEl(''); }, body: { appendChild() {} } };
sb.matchMedia = () => ({ matches: false });
let lastModal = null, modalMark = 0;
sb.openModal = function (title, html) { modals.push({ title, html }); lastModal = stubEl('<button data-x></button>' + html); modalMark = handlers.length; return lastModal; };
sb.closeModal = function () {};
const now = Date.now();
sb.INBOX = input.inbox || [];
sb.INBOX_SNOOZED = input.snoozed || [];
sb.INBOX_FAILED = input.failed || []; sb.INBOX_TRUNCATED = input.truncated || [];
const st0 = Object.assign({ opsQueue: 'ready', inbox: 'ready', walletPayouts: 'ready', invites: 'ready', pendingUsers: 'ready', market: 'ready' }, input.stateOverride || {});
const ok = (v) => ({ ok: true, v });
sb.EP = {
  authed: true, role: 'admin', user: { name: 'عبد الرحمن عطية' },
  state: st0,
  data: { opsQueue: input.queue || {}, walletPayouts: { rows: input.payouts || [], hidden: [], count: (input.payouts || []).length }, invites: { rows: input.invites || [] }, pendingUsers: { rows: [] }, market: { rows: [] },
          snooze: input.snooze || { map: {}, ok: true, at: 1 } },
  ensure() {}, reload() {},
  snoozeItem(key, until, fp) { calls.push({ fn: 'snoozeItem', key, until, fp }); return Promise.resolve({ ok: true }); },
  dismissItem(key, reason, fp) { calls.push({ fn: 'dismissItem', key, reason, fp }); return Promise.resolve({ ok: true }); },
  restoreItem(key) { calls.push({ fn: 'restoreItem', key }); return Promise.resolve({ ok: true }); },
  decideInboxItem(row, action, after, note) { calls.push({ fn: 'decideInboxItem', kind: row.apiKind, id: row.apiId, ref: row.ref, action, note: note || '' }); return Promise.resolve(input.failOn && input.failOn === row.apiKind ? { ok: false, error: 'رفض من المنصة' } : { ok: true }); },
  decideInvite(id, action, note) { calls.push({ fn: 'decideInvite', id, action, note: note || '' }); return Promise.resolve({ ok: true }); },
  resolveInboxItem(row) { calls.push({ fn: 'resolveInboxItem', ref: row.ref }); return Promise.resolve({ ok: true }); },
  expertFileSend(row, email) { calls.push({ fn: 'expertFileSend', ref: row.ref, email }); return Promise.resolve({ ok: true }); },
  post(p, body) { calls.push({ fn: 'post', path: p, body }); return Promise.resolve({}); },
};
sb.V2_HOST = {
  isHome: () => input.isHome !== false,
  openRow: (row) => { calls.push({ fn: 'openRow', ref: row.ref }); return input.openRowResult !== false; },
  openReading: (row, o) => { calls.push({ fn: 'openReading', ref: row.ref, home: o && o.home }); return input.openRowResult !== false; },
  openSection(k, t) { calls.push({ fn: 'openSection', k, t }); }, goOps() {}, go() {},
};
sb.toast = (t) => calls.push({ fn: 'toast', t });
vm.createContext(sb);
vm.runInContext(fs.readFileSync(path.join(dc, 'v2-logic.js'), 'utf8'), sb);
vm.runInContext(fs.readFileSync(path.join(dc, 'v2-home.js'), 'utf8'), sb);
vm.runInContext(fs.readFileSync(path.join(dc, 'v2-strip.js'), 'utf8'), sb);
if (input.brain) sb.V2BRAIN = { pending: () => input.brain, decorate: (c) => c, prefetch() {}, sig: () => '1', listen: () => () => {}, reload() {}, act(c, a, cb) { calls.push({ fn: 'brainAct', id: c.id, act: a.do }); cb({ ok: true, text: 'تم' }); } };
const v = stubEl('');
sb.V2.render(v);
if (input.mount) sb.V2STRIP.mount(input.mount, stripEl, false);
const out = { html: v.innerHTML };
function match(h, attr) { if (!attr) return true; return Object.keys(attr).every((k) => h._attrs && h._attrs[k] === attr[k]); }
function find(sel, idx, attr) {
  const hs = handlers.filter((h) => h._sel === sel && h._hit !== false && (idx == null || h._i === idx) && match(h, attr));
  return hs[hs.length - 1] || null;
}
(async () => {
  for (const st of (input.steps || [])) {
    if (st.mode === 'focus') { handlers.length = 0; sb.V2.render(v); const b = find('[data-a="start"]'); if (b && b.onclick) b.onclick(); }
    else if (st.modalClick) { const hs = handlers.slice(modalMark).filter((h) => h._sel === st.modalClick && h._hit); const h = hs[st.idx || 0]; if (h && h.onclick) await h.onclick(); else calls.push({ fn: 'NO_MODAL_HANDLER', sel: st.modalClick }); }
    else if (st.modalType) { const hs = handlers.slice(modalMark).filter((h) => h._sel === st.modalType.sel && h._hit); const h = hs[0]; if (h) { h.value = st.modalType.value; (h._listeners || []).forEach((f) => f()); } else calls.push({ fn: 'NO_MODAL_INPUT', sel: st.modalType.sel }); }
    else if (st.strip) {      // اضغط زرار في الشريط: attr بتحدّد الزرار (data-a + data-id)
      handlers.length = 0; sb.V2STRIP.mount(input.mount, stripEl, false);
      const b = find(st.strip, st.idx, st.attr); if (b && b.onclick) await b.onclick(); else calls.push({ fn: 'NO_STRIP_HANDLER', sel: st.strip, attr: st.attr });
    }
    else if (st.click) { handlers.length = 0; sb.V2.render(v); const b = find(st.click, st.idx, st.attr); if (b && b.onclick) await b.onclick(); else calls.push({ fn: 'NO_HANDLER', sel: st.click }); }
    await new Promise((r) => setImmediate(r));
  }
  out.html = v.innerHTML;
  if (input.mount) { sb.V2STRIP.mount(input.mount, stripEl, false); out.strip = stripEl.innerHTML; }
  out.calls = calls; out.deck = (sb.V2._state.deck || []).map((c) => c.id); out.modal = modals.length ? modals[modals.length - 1] : null; out.mode = sb.V2._state.mode;
  out.modals = modals.map((m) => m.title);
  out.tiles = sb.V2.tiles().map((t) => ({ key: t.key, count: t.count, next: t.next, failed: t.failed, hot: t.hot }));
  out.counts = sb.V2.counts();
  out.strips = {};
  sb.V2L.SECTION_KEYS.forEach((k) => { const s = sb.V2.strip(k); out.strips[k] = { n: s.n, ids: s.cards.map((c) => c.id), kinds: s.cards.map((c) => c.kind), later: s.later.length, gone: s.gone.length }; });
  process.stdout.write(JSON.stringify(out, (k, x) => (x === Infinity ? null : x)));
})();
