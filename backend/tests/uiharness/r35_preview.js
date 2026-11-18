// R35 — معاينات «طلبات الانضمام» (طابور واحد بأنواعه + «اطلب معلومات») من الكود الحقيقي (v2-logic/v2-home/v2-strip) في node:vm ببيانات مزيّفة،
// وبتكتب `.html` بتحمّل CSS اللوحة الحقيقي (ملفات `dashboard-cloud/` + ستايل index.html نفسه للنافذة). تتصوّر بعدها في متصفح محلي.
//   node r35_preview.js <out_dir>
// ⛔ ولا شبكة ولا منفذ: كله في الذاكرة.
const vm = require('vm');
const fs = require('fs');
const path = require('path');
const out = process.argv[2];
if (!out) { console.error('usage: node r35_preview.js <out_dir>'); process.exit(2); }
fs.mkdirSync(out, { recursive: true });
const dc = path.join(__dirname, '..', '..', '..', 'dashboard-cloud');
const now = Date.now();
const H = 3600e3;
const base = { apiKind: 'trainer', canReject: true, rejectNeedsReason: true, from: 'درّب معنا' };
const rows = [
  Object.assign({}, base, { apiId: 't1', ref: 'TRN-t1', who: 'خالد السني', personEmail: 'khaled.s@example.test', ts: now - 60 * 24 * H,
    trJoin: 'expert', trType: 'new', trHeadline: 'جنائي', trSpecs: ['جنائي'], trBio: 'محامٍ بالاستئناف، ١١ سنة في قضايا الجنايات والجنح، ومذكرات الدفاع والطعون.',
    trYears: 'من ١١ إلى ١٥ سنة', trBar: '١٤٣٢٥٦', trPhone: '+201001112233', trLi: 'https://linkedin.com/in/x', trFrom: 'د. هالة رشدي', trStatus: 'pending' }),
  Object.assign({}, base, { apiId: 't2', ref: 'TRN-t2', who: 'منى عبد الحميد', personEmail: 'mona@example.test', ts: now - 30 * H,
    trJoin: 'trainer', trType: 'new', trHeadline: 'صياغة العقود التجارية للمحامين الجدد', trYears: 'من ٦ إلى ١٠ سنوات', trVideo: 'https://youtu.be/x', trCv: 'https://drive.google.com/x', trPhone: '+966500000000', trStatus: 'pending' }),
  Object.assign({}, base, { apiId: 't3', ref: 'TRN-t3', who: 'خالد منصور', personEmail: 'khaled.m@example.test', ts: now - 4 * H,
    trJoin: 'trainer', trType: 'add_role', trAddRole: 'expert', trSpecs: ['تجاري وشركات', 'مدني وعقود'],
    trBio: 'محامٍ ومدرّب، ٩ سنوات في عقود الشركات والشراكات، أراجع العقود التجارية وأكتب رأيًا واضحًا قبل التوقيع.', trYears: 'من ٦ إلى ١٠ سنوات', trStatus: 'pending' }),
  Object.assign({}, base, { apiId: 't4', ref: 'TRN-t4', who: 'د. سارة عبد الله', personEmail: 'sara@example.test', ts: now - 9 * H,
    trJoin: 'expert', trType: 'add_role', trAddRole: 'trainer', trTeach: 'قضايا الأسرة للمحامين الجدد', trVideo: 'https://youtu.be/y', trStatus: 'pending' }),
  Object.assign({}, base, { apiId: 't5', ref: 'TRN-t5', who: 'د. ثابت أبو الروس', personEmail: 'thabet@example.test', ts: now - 9 * 24 * H,
    trJoin: 'expert', trType: 'new', trHeadline: 'تحكيم', trSpecs: ['تحكيم تجاري'], trBio: '', trYears: 'أكثر من ١٥ سنة', trStatus: 'needs_info',
    trInfo: 'اختر تخصصاتك من القايمة واكتب نبذة من سطرين تظهر للعملاء.' }),
  Object.assign({}, base, { apiId: 't6', ref: 'TRN-t6', who: 'ريم حسن', personEmail: 'reem@example.test', ts: now - 2 * H,
    trJoin: 'other', trOther: 'مترجم قانوني معتمد', trType: 'new', trHeadline: 'ترجمة العقود والأحكام', trPhone: '+201009998877', trStatus: 'pending' }),
];

function el() {
  const e = { innerHTML: '', style: {}, dataset: {}, value: '', classList: { add() {}, remove() {}, toggle() {} }, children: [], addEventListener() {}, setAttribute() {}, getAttribute() { return null; },
    querySelectorAll() { return []; }, remove() {}, contains() { return false; }, closest() { return null; }, focus() {} };
  e.querySelector = () => el();
  return e;
}
let modal = null;
function bootSandbox(extra) {
  const sb = { console, setTimeout: (f) => { try { f(); } catch (e) {} return 0; }, clearTimeout() {}, setInterval() { return 1; }, clearInterval() {}, Promise, JSON, Math, Date, Intl, Object, Array, String, Number, Error, RegExp, WeakMap };
  sb.window = sb;
  sb.document = { readyState: 'complete', addEventListener() {}, removeEventListener() {}, getElementById() { return null; }, querySelector() { return null; }, querySelectorAll() { return []; }, createElement: el, body: { appendChild() {}, contains() { return true; } } };
  sb.matchMedia = () => ({ matches: false });
  sb.openModal = (title, body) => { modal = { title, body }; return el(); }; sb.closeModal = () => {};
  sb.INBOX = rows; sb.INBOX_SNOOZED = []; sb.INBOX_FAILED = []; sb.INBOX_TRUNCATED = [];
  sb.EP = {
    authed: true, role: 'admin', user: { name: 'عبد الرحمن عطية' },
    state: { opsQueue: 'ready', inbox: 'ready', walletPayouts: 'ready', invites: 'ready', pendingUsers: 'ready', market: 'ready' },
    data: { opsQueue: {}, walletPayouts: { rows: [], hidden: [], count: 0 }, invites: { rows: [] }, pendingUsers: { rows: [] }, market: { rows: [] }, snooze: { map: {}, ok: true, at: 1 } },
    ensure() {}, reload() {}, decideInboxItem() { return Promise.resolve({ ok: true }); }, api() { return Promise.resolve({}); }
  };
  sb.V2_HOST = Object.assign({ isHome: () => false, openRow() { return true; }, openReading() { return true; }, openSection() {}, goOps() {}, go() {}, current: () => 'people', state: () => ({ section: 'people', tab: 'users' }) }, extra || {});
  vm.createContext(sb);
  ['v2-logic.js', 'v2-home.js', 'v2-strip.js', 'v2-d2.js'].forEach((f) => vm.runInContext(fs.readFileSync(path.join(dc, f), 'utf8'), sb));
  return sb;
}
const idx = fs.readFileSync(path.join(dc, 'index.html'), 'utf8');
const inlineCss = (idx.match(/<style>[\s\S]*?<\/style>/) || [''])[0];
const css = inlineCss + ['v2-home.css', 'v2-shell.css', 'v2-d2.css', 'v2-strip.css'].map((f) => '<link rel="stylesheet" href="file://' + path.join(dc, f) + '">').join('');
function sidebar(sb, active) {
  const L = sb.V2L, tiles = {};
  sb.V2.tiles().forEach((t) => { tiles[t.key] = t; });
  const items = L.SECTIONS.map((s) => {
    const t = tiles[s.key];
    const tail = !s.img ? '' : (t && t.count ? '<span class="v2s-badge">' + L.util.ar(t.count) + '</span>' : '<span class="v2s-dash">—</span>');
    return '<a class="v2s-item' + (s.key === active ? ' on' : '') + (s.img ? '' : ' v2s-home') + '" href="#"><span class="v2s-name">' + s.label + '</span>' + tail + '</a>';
  }).join('');
  return '<div class="v2s-brand"><span class="v2s-bt"><b>البروفيسور</b><small>غرفة التحكم</small></span></div><nav class="v2s-nav">' + items + '</nav>'
    + '<div class="v2s-me"><span class="v2s-av">ع</span><span class="v2s-who"><b>عبد الرحمن عطية</b><small>المؤسس</small></span></div>';
}
function heading(sb, key, tabKey) {
  const L = sb.V2L, sec = L.sectionByKey(key);
  return '<div class="v2-sec"><div class="v2c-h"><h1>' + sec.label + '</h1><p>' + sec.desc + '</p></div><div class="v2c-tabs">'
    + sec.tabs.filter((t) => !t.hidden).map((t) => '<button class="v2c-tab' + (t.key === (tabKey || sec.tabs[0].key) ? ' on' : '') + '">' + t.label + '</button>').join('') + '</div></div>';
}
function page(name, title, body, sb, extraHtml) {
  const html = '<!doctype html><html lang="ar" dir="rtl"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>' + title + '</title>' + css
    + '<style>html,body{margin:0;background:#F7F3ED}.pv{display:grid;grid-template-columns:250px 1fr;min-height:100vh}.pv-main{padding:22px 30px 40px;min-width:0}.v2-side{display:flex!important;height:auto}.v2-sec{display:block}'
    + '@media(max-width:700px){.pv{grid-template-columns:1fr}.v2-side{display:none!important}.pv-main{padding:14px 16px 30px}}</style></head>'
    + '<body><div class="app v2-shell"><div class="pv"><aside id="v2Side" class="v2-side">' + sidebar(sb, 'people') + '</aside><main class="pv-main">' + body + '</main></div></div>' + (extraHtml || '') + '</body></html>';
  fs.writeFileSync(path.join(out, name), html);
}

const sb = bootSandbox();
const z = { innerHTML: '', hidden: false, setAttribute() {}, getAttribute() { return null; }, querySelectorAll() { return []; }, querySelector() { return null; } };
sb.V2STRIP.mount('people', z, false);
page('d1-people-queue.html', 'طلبات الانضمام', heading(sb, 'people', 'users') + '<div class="v2-strip">' + z.innerHTML + '</div>', sb);

// «اطلب معلومات» على بطاقة د. ثابت: نفس `run` الحقيقي ⇐ `infoModal` ⇐ `confirmModal` ⇐ `openModal` (اتمسك هنا وبيترسم بنفس شكل index.html).
const cards = sb.V2.strip ? sb.V2.strip('people') : null;
const all = cards ? [].concat(cards.cards || cards.now || cards.items || []) : [];
let target = all.find((c) => c && c.title === 'خالد السني') || all[0];
if (target && target.edit && sb.V2.runCard) sb.V2.runCard(target, target.edit.act, () => {}, () => {});
if (!modal) console.error('no modal captured; strip keys=', cards && Object.keys(cards));
const m = modal || { title: '', body: '' };
const modalHtml = '<div class="scrim" id="epModal"><div class="modal"><div class="mh"><span>' + m.title + '</span><button data-x>✕</button></div><div class="mb">' + m.body + '</div></div></div>';
page('d2-request-info-dialog.html', 'اطلب معلومات', heading(sb, 'people', 'users') + '<div class="v2-strip">' + z.innerHTML + '</div>', sb, modalHtml);
// «اقبل واختر صفته» على بطاقة «أخرى» (ريم حسن): نفس `run` ⇐ `otherModal` ⇐ `openModal`.
modal = null;
const other = all.find((c) => c && c.title === 'ريم حسن');
if (other && other.primary && sb.V2.runCard) sb.V2.runCard(other, other.primary.act, () => {}, () => {});
const m2 = modal || { title: '', body: '' };
page('d3-approve-other-dialog.html', 'اقبل واختر صفته', heading(sb, 'people', 'users') + '<div class="v2-strip">' + z.innerHTML + '</div>', sb,
  '<div class="scrim" id="epModal"><div class="modal"><div class="mh"><span>' + m2.title + '</span><button data-x>✕</button></div><div class="mb">' + m2.body + '</div></div></div>');
console.log(fs.readdirSync(out).sort().join('\n'));
