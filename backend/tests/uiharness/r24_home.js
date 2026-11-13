// R24 م١ — يرسم اللوحة الحقيقية (v2-home.js) في node:vm بمستند مزيّف ويرجّع الـHTML + يضغط على الأزرار.
//   stdin : {"inbox": [rows], "snoozed": [{row, entry, key}], "payouts": [], "queue": {...}, "snooze": {map...}, "steps": [{"click": "<selector>", "idx": 0}|{"mode":"focus"}]}
//   stdout: {"html": "...", "calls": [...], "deck": [...ids], "modal": "<html آخر نافذة>"}
// ⛔ لا شبكة ولا DOM حقيقي: `fetch` مش موجود أصلًا، و`EP` دالة في الذاكرة تسجّل النداءات.
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
  if ((m = /^\[(data-[a-z]+)\]$/.exec(sel))) return new RegExp(m[1], 'g');
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
  const el = { innerHTML: html || '', style: {}, dataset: {}, classList: { add() {}, remove() {}, toggle() {} }, children: [], onclick: null, disabled: false, value: '', textContent: '',
    addEventListener(t, f) { (el._listeners = el._listeners || []).push(f); }, setAttribute(k, v) { attrs[k] = v; }, getAttribute(k) { return k in attrs ? attrs[k] : null; },
    remove() {}, contains() { return false; }, closest() { return null; }, focus() {} };
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
const sb = { console, setTimeout: (f) => { f(); return 0; }, clearTimeout() {}, setInterval() { return 1; }, clearInterval() {}, Promise, JSON, Math, Date, Intl, Object, Array, String, Number, Error, RegExp };
sb.window = sb;
sb.document = { readyState: 'complete', addEventListener() {}, removeEventListener() {}, getElementById() { return null; }, querySelector() { return null; }, createElement() { return stubEl(''); }, body: { appendChild() {} } };
sb.matchMedia = () => ({ matches: false });
let lastModal = null, modalMark = 0;
sb.openModal = function (title, html) { modals.push({ title, html }); lastModal = stubEl(html); modalMark = handlers.length; return lastModal; };
sb.closeModal = function () {};
const now = Date.now();
sb.INBOX = input.inbox || [];
sb.INBOX_SNOOZED = input.snoozed || [];
sb.INBOX_FAILED = []; sb.INBOX_TRUNCATED = [];
const ready = { opsQueue: 1, inbox: 1, walletPayouts: 1, invites: 1, pendingUsers: 1, market: 1 };
sb.EP = {
  authed: true, role: 'admin', user: { name: 'المؤسس' },
  state: { opsQueue: 'ready', inbox: 'ready', walletPayouts: 'ready', invites: 'ready', pendingUsers: 'ready', market: 'ready' },
  data: { opsQueue: input.queue || {}, walletPayouts: { rows: input.payouts || [], hidden: [], count: (input.payouts || []).length }, invites: { rows: [] }, pendingUsers: { rows: [] }, market: { rows: [] },
          snooze: input.snooze || { map: {}, ok: true, at: 1 } },
  ensure() {}, reload() {},
  snoozeItem(key, until, fp) { calls.push({ fn: 'snoozeItem', key, until, fp }); return Promise.resolve({ ok: true }); },
  dismissItem(key, reason, fp) { calls.push({ fn: 'dismissItem', key, reason, fp }); return Promise.resolve({ ok: true }); },
  restoreItem(key) { calls.push({ fn: 'restoreItem', key }); return Promise.resolve({ ok: true }); },
  decideInboxItem(row, action) { calls.push({ fn: 'decideInboxItem', ref: row.ref, action }); return Promise.resolve({ ok: true }); },
  resolveInboxItem(row) { calls.push({ fn: 'resolveInboxItem', ref: row.ref }); return Promise.resolve({ ok: true }); },
  expertFileSend(row, email) { calls.push({ fn: 'expertFileSend', ref: row.ref, email }); return Promise.resolve({ ok: true }); },
};
sb.V2_HOST = { isHome: () => true, openRow: (row) => { calls.push({ fn: 'openRow', ref: row.ref }); return input.openRowResult !== false; }, openSection() {}, goOps() {}, go() {} };
sb.toast = (t) => calls.push({ fn: 'toast', t });
vm.createContext(sb);
vm.runInContext(fs.readFileSync(path.join(dc, 'v2-logic.js'), 'utf8'), sb);
vm.runInContext(fs.readFileSync(path.join(dc, 'v2-home.js'), 'utf8'), sb);
const v = stubEl('');
sb.V2.render(v);
const out = { html: v.innerHTML };
function find(sel, idx) { const hs = handlers.filter((h) => h._sel === sel && h._hit !== false && (idx == null || h._i === idx)); return hs[hs.length - 1] || null; }
(async () => {
  for (const st of (input.steps || [])) {
    if (st.mode === 'focus') { handlers.length = 0; sb.V2.render(v); const b = find('[data-a="start"]'); if (b && b.onclick) b.onclick(); }
    else if (st.modalClick) { const hs = handlers.slice(modalMark).filter((h) => h._sel === st.modalClick && h._hit); const h = hs[st.idx || 0]; if (h && h.onclick) await h.onclick(); else calls.push({ fn: 'NO_MODAL_HANDLER', sel: st.modalClick }); }
    else if (st.modalType) { const hs = handlers.slice(modalMark).filter((h) => h._sel === st.modalType.sel && h._hit); const h = hs[0]; if (h) { h.value = st.modalType.value; (h._listeners || []).forEach((f) => f()); } else calls.push({ fn: 'NO_MODAL_INPUT', sel: st.modalType.sel }); }
    else if (st.click) { handlers.length = 0; sb.V2._redraw && sb.V2._redraw(); sb.V2.render(v); const b = find(st.click, st.idx); if (b && b.onclick) await b.onclick(); else calls.push({ fn: 'NO_HANDLER', sel: st.click }); }
    await new Promise((r) => setImmediate(r));
  }
  out.html = v.innerHTML; out.calls = calls; out.deck = (sb.V2._state.deck || []).map((c) => c.id); out.modal = modals.length ? modals[modals.length - 1] : null; out.mode = sb.V2._state.mode;
  process.stdout.write(JSON.stringify(out));
})();
