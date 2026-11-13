// R24 م٢ — يشغّل الغلاف الحقيقي (v2-shell.js) في node:vm: القايمة الجانبية الفاتحة (١١ عنصر · عدّاد القرارات · «—») وترويسة القسم وتركيب شريط «محتاج قرارك».
//   stdin : {"inbox": [rows], "section": "files", "tab": "files", "invites": [...]}
//   stdout: {"side": "<html>", "head": "<html>", "strip": {"hidden": bool, "html": "..."}, "sheet": "<html>"}
// ⛔ لا شبكة ولا DOM حقيقي: عناصر مزيّفة بتتسجّل بالـid لما تتحط في الصفحة.
const vm = require('vm');
const fs = require('fs');
const path = require('path');
const input = JSON.parse(fs.readFileSync(0, 'utf8'));
const dc = path.join(__dirname, '..', '..', '..', 'dashboard-cloud');
const byId = {}, bySel = {};
function mk(tag) {
  const el = { tag, innerHTML: '', style: {}, hidden: false, dataset: {}, className: '', children: [], _attrs: {}, parentNode: null,
    classList: { add() {}, remove() {}, toggle() {}, contains() { return false; } },
    setAttribute(k, v) { el._attrs[k] = v; }, getAttribute(k) { return k in el._attrs ? el._attrs[k] : null; },
    addEventListener() {}, removeEventListener() {}, focus() {}, scrollIntoView() {},
    querySelector(sel) { return null; }, querySelectorAll() { return []; }, contains() { return false; }, closest() { return null; },
    insertBefore(n) { n.parentNode = el; if (n.id) byId[n.id] = n; return n; }, appendChild(n) { n.parentNode = el; if (n.id) byId[n.id] = n; return n; } };
  return el;
}
const app = mk('div'), view = mk('div'), topbar = mk('div');
view.parentNode = app; byId.view = view;
bySel['.app'] = app; bySel['#view'] = view; bySel['.topbar'] = topbar; bySel['.rail'] = mk('div'); bySel['#menuBtn'] = mk('button');
const doc = { readyState: 'complete', body: mk('body'), addEventListener() {}, removeEventListener() {}, createElement: mk, documentElement: mk('html'),
  getElementById(id) { return byId[id] || null; },
  querySelector(sel) { if (sel[0] === '#' && byId[sel.slice(1)]) return byId[sel.slice(1)]; return bySel[sel] || null; },
  querySelectorAll() { return []; }, activeElement: null };
doc.body.appendChild = function (n) { n.parentNode = doc.body; if (n.id) byId[n.id] = n; return n; };
const sb = { console, setTimeout: (f) => { f(); return 0; }, clearTimeout() {}, setInterval() { return 1; }, clearInterval() {}, Promise, JSON, Math, Date, Intl, Object, Array, String, Number, Error, RegExp, WeakMap, MutationObserver: undefined };
sb.window = sb; sb.document = doc; sb.matchMedia = () => ({ matches: false }); sb.addEventListener = () => {};
sb.getComputedStyle = () => ({ direction: 'rtl', position: 'static' });
sb.INBOX = input.inbox || []; sb.INBOX_SNOOZED = []; sb.INBOX_FAILED = []; sb.INBOX_TRUNCATED = [];
sb.EP = { authed: true, role: 'admin', user: { name: 'عبد الرحمن عطية' },
  state: { opsQueue: 'ready', inbox: 'ready', walletPayouts: 'ready', invites: 'ready', pendingUsers: 'ready', market: 'ready' },
  data: { opsQueue: {}, walletPayouts: { rows: [], hidden: [], count: 0 }, invites: { rows: input.invites || [] }, pendingUsers: { rows: [] }, market: { rows: [] }, snooze: { map: {}, ok: true, at: 1 } },
  ensure() {}, reload() {} };
const state = { section: input.section || 'home', tab: input.tab || 'board' };
const host = { state: () => state, openSection(k, t) { state.section = k; state.tab = t || state.tab; }, userName: () => 'عبد الرحمن عطية', logout() {}, isHome: () => state.section === 'home', current: () => 'x' };
sb.V2_HOST = host; sb.V2_ON = true;
vm.createContext(sb);
['v2-logic.js', 'v2-home.js', 'v2-strip.js', 'v2-shell.js'].forEach((f) => vm.runInContext(fs.readFileSync(path.join(dc, f), 'utf8'), sb));
sb.V2SHELL.boot(host);
const out = { side: (byId.v2Side || {}).innerHTML, head: (byId.v2sec || {}).innerHTML, sheet: (byId.v2Sheet || {}).innerHTML };
const z = byId.v2strip || {};
out.strip = { hidden: !!z.hidden, html: z.innerHTML || '' };
process.stdout.write(JSON.stringify(out));
