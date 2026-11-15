// r27 — القسم والشريط والشارة بيتحدّثوا مع بعض: يحمّل الملفات الحقيقية (dashboard-api · v2-logic · v2-home · v2s/courses) في node:vm
// بجدول ردود قابل للتغيير بين الخطوات (المنصة «اتغيّرت» والتبويب مفتوح). ⛔ لا شبكة: fetch جدول في الذاكرة.
//   stdin : {"initial": {path: {status, body}}, "later": {path: {status, body}}}
//   stdout: {"before": {...}, "after": {...}, "calls": [...]}
const vm = require('vm');
const fs = require('fs');
const path = require('path');
const input = JSON.parse(fs.readFileSync(0, 'utf8'));
const dc = path.join(__dirname, '..', '..', '..', 'dashboard-cloud');
let table = input.initial;
const calls = [];
function stub(html) {
  const el = { innerHTML: html || '', style: {}, dataset: {}, classList: { add() {}, remove() {}, toggle() {}, contains() { return false; } }, children: [],
    addEventListener() {}, removeEventListener() {}, setAttribute() {}, getAttribute() { return null; }, remove() {}, contains() { return false; }, closest() { return null; },
    querySelector() { return null; }, querySelectorAll() { return []; }, appendChild() {}, focus() {}, id: 'v2sec' };
  return el;
}
const sb = { console, setTimeout, clearTimeout, setInterval() { return 1; }, clearInterval() {}, Promise, JSON, Math, Date, Intl, Object, Array, String, Number, Error, RegExp };
sb.window = sb;
sb.document = { readyState: 'complete', visibilityState: 'visible', addEventListener() {}, removeEventListener() {}, getElementById() { return null; }, querySelector() { return null; }, querySelectorAll() { return []; },
                createElement() { return stub(''); }, body: { appendChild() {}, contains() { return true; } }, documentElement: { classList: { add() {}, remove() {}, toggle() {} } }, activeElement: null };
sb.localStorage = { getItem() { return 'tok'; }, setItem() {}, removeItem() {} };
sb.location = { reload() {}, hash: '' };
sb.matchMedia = () => ({ matches: false });
sb.toast = function () {};
sb.fetch = function (url, opts) {
  const p = String(url);
  calls.push({ url: p, method: (opts && opts.method) || 'GET' });
  const hit = table[p] || table[p.split('?')[0]];
  const status = hit ? hit.status : 404;
  const body = hit ? hit.body : { error: 'not found' };
  return Promise.resolve({ ok: status >= 200 && status < 300, status: status, json: () => Promise.resolve(body) });
};
sb.V2_ON = true;
sb.V2SHELL = { on: true, refresh() {} };
sb.V2_HOST = { isHome: () => false, current: () => 'courses', state: () => ({ section: 'courses', tab: 'courses' }), openSection() {}, go() {} };
sb.v2Snapshot = () => ({ courseTab: 'courses' });
vm.createContext(sb);
for (const f of ['v2-logic.js', 'dashboard-api.js', 'v2-home.js', 'v2s/courses.js']) vm.runInContext(fs.readFileSync(path.join(dc, f), 'utf8'), sb);
const EP = sb.EP;
EP.authed = true; EP.role = 'admin';
const wait = (ms) => new Promise((r) => setTimeout(r, ms));
const view = stub('');
function snap() {
  const g = sb.V2.strip('courses'), c = sb.V2.counts(), tiles = sb.V2.tiles().filter((t) => t.key === 'courses')[0] || {};
  return { strip_n: g.n, counts_courses: c.courses, tile_count: tiles.count, html: view.innerHTML, state: EP.state.opsQueue };
}
(async () => {
  sb.V2.loadAll();
  sb.V2CO.take('courses', view);
  await wait(250);
  const before = snap();
  const nCalls = calls.length;
  table = input.later;                       // المنصة اتغيّرت (دورة اتقدّمت · مدرّب اتقبل) والتبويب لسه مفتوح من غير تحديث يدوي
  calls.length = 0;
  sb.V2.refreshAll(true);
  await wait(250);
  const after = snap();
  const states = { opsQueue: EP.state.opsQueue };
  // التحديث الصامت: ما مرّش بحالة «جارٍ التحميل» (ما يوميش الشريط)
  process.stdout.write(JSON.stringify({ before, after, states, calls: calls.map((c) => c.url) }));
  process.exit(0);
})().catch((e) => { process.stdout.write(JSON.stringify({ error: String(e && e.stack || e) })); process.exit(1); });
