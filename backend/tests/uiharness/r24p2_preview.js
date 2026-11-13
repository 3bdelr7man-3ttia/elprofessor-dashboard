// R24 م٢ — معاينات HTML ثابتة (مش PNG): بيرسم اللوحة الحقيقية والشريط وصفحة الشخص وقايمة الناس في node:vm ببيانات مزيّفة، ويكتب ملفات `.html`
// بتحمّل نفس CSS الحقيقي من `dashboard-cloud/` (مسارات مطلقة). تتفتح في أي متصفح أو تتصوّر منه.
//   node r24p2_preview.js <out_dir>
// ⛔ ولا شبكة ولا منفذ: كله في الذاكرة. بتتعمل لمّا المنافذ وكروم مقفولين في الصندوق (مش بديل عن لقطات المتصفح الحقيقي).
const vm = require('vm');
const fs = require('fs');
const path = require('path');
const out = process.argv[2];
if (!out) { console.error('usage: node r24p2_preview.js <out_dir>'); process.exit(2); }
fs.mkdirSync(out, { recursive: true });
const dc = path.join(__dirname, '..', '..', '..', 'dashboard-cloud');
const now = Date.now();
const H = 3600e3;

const rows = [
  { apiKind: 'pending_user', apiId: 'u1', ref: 'PU-1', who: 'منى عبد الحميد', personEmail: 'mona@example.test', email: 'mona@example.test', ts: now - 3 * H, canReject: true, flagLabels: [], puCountry: 'مصر' },
  { apiKind: 'trainer', apiId: 't1', ref: 'TRN-1', who: 'منى عبد الحميد', personEmail: 'mona@example.test', ts: now - 48 * H, canReject: true, rejectNeedsReason: true, trJoin: 'both', trHeadline: 'محامية بالنقض، ١٢ سنة خبرة', trSpec: 'عقود' },
  { apiKind: 'signup', apiId: 'u1', ref: 'SGN-1', who: 'منى', personEmail: 'mona@example.test', email: 'mona@example.test', ts: now - 49 * H },
  { apiKind: 'pending_user', apiId: 'u2', ref: 'PU-2', who: 'أحمد سمير', personEmail: 'ahmed@example.test', email: 'ahmed@example.test', ts: now - 3 * H, canReject: true, flagLabels: [], puCountry: 'السعودية', puRole: 'محامٍ' },
  { apiKind: 'founding', apiId: 'f1', ref: 'FND-1', who: 'سلمى منصور', personEmail: 'salma@example.test', ts: now - 20 * H, nextStatus: 'contacted', statusLabel: 'جديد', canReject: true, fSpec: 'أحوال شخصية', fCountry: 'مصر' },
  { apiKind: 'identity_doc', apiId: 'i1', ref: 'IDD-1', who: 'إيمان فؤاد', personEmail: 'eman@example.test', idTitle: 'محامية', ts: now - 5 * H, canReject: true },
  { apiKind: 'signup', apiId: 's9', ref: 'SGN-9', who: 'علي حسن', personEmail: 'ali@example.test', email: 'ali@example.test', ts: now - 2 * H, sgProvider: 'بجوجل', sgWhere: 'مصر' },
  { apiKind: 'expert_file', apiId: 'ef9', efLane: 'waiting', ref: 'EF-ef9', who: 'عميل', ts: now - 12 * H, ef: { id: 'ef9', title: 'مراجعة عقد شراكة', status: 'awaiting_assignment', hours_left: 20, paid_at: new Date(now - 12 * H).toISOString(), candidates: [{ email: 'k@example.test', name: 'أ. كريم فوزي', auto_pick: true, same_specialty: true, load: 2 }] } },
  { apiKind: 'expert_file', apiId: 'ef8', efLane: 'review', ref: 'EF-ef8', who: 'رنا', ts: now - 6 * H, ef: { id: 'ef8', title: 'رأي في نفقة الصغير', expert_name: 'د. هالة رشدي', review: { submitted_at: new Date(now - 6 * H).toISOString() } } },
  { apiKind: 'dispute', dsrc: 'file', apiId: 'd1', ref: 'EF-d1', who: 'دينا', ts: now - 30 * H, ef: { id: 'd1', title: 'إنذار بسداد متأخرات الإيجار', expert_name: 'أ. فيصل العتيبي' }, amountLabel: '١٬٢٠٠ جنيه' },
  { apiKind: 'manual_payment', apiId: 'm1', ref: 'PAY-1', who: 'نادية', ts: now - 9 * H, amount: 369, currency: 'EGP', payMethod: 'إنستاباي', payWhat: 'كتاب «أساسيات العقود»', canReject: true },
  { apiKind: 'topic', apiId: 'tp1', ref: 'TPC-1', who: 'عقود', ts: now - 4 * H, note: 'هل يجوز إنهاء العقد قبل مدته؟ — سؤال من عضو عن الإنهاء المبكر لعقد إيجار.' },
  { apiKind: 'creative', apiId: 'cr1', ref: 'CRE-1', who: 'مبدعة', ts: now - 8 * H, note: 'عمل إبداعي بعنوان «ميزان العدالة» للنشر في الديوان', canReject: true, approveLabel: 'اعتماد ونشر' },
  { apiKind: 'site_message', apiId: 44, msgSource: 'site', msgId: 44, ref: 'MSG-44', who: 'زائر من الموقع', ts: now - 2 * H, note: 'عايز أعرف تكلفة مراجعة عقد.' }
];
const payouts = [{ kind: 'payout', pid: 'p1', who: 'كريم فوزي', email: 'k@example.test', amount: 2400, currency: 'EGP', dest: 'إنستاباي', status: 'pending', raw: { amount: 2400, method: 'إنستاباي', created_at: new Date(now - 30 * H).toISOString() } }];
const invites = [{ id: 'iv1', email: 'hala@example.test', name: 'د. هالة رشدي', invitedByLabel: 'سارة الحربي', status: 'awaiting_approval', generation: 2, at: now - 5 * H, note: 'زميلتي في نفس المكتب' }];

function bootSandbox(extra) {
  const sb = { console, setTimeout: (f) => { f(); return 0; }, clearTimeout() {}, setInterval() { return 1; }, clearInterval() {}, Promise, JSON, Math, Date, Intl, Object, Array, String, Number, Error, RegExp, WeakMap };
  sb.window = sb;
  const el = () => ({ innerHTML: '', style: {}, dataset: {}, classList: { add() {}, remove() {}, toggle() {} }, children: [], addEventListener() {}, setAttribute() {}, getAttribute() { return null; }, querySelector() { return null; }, querySelectorAll() { return []; }, remove() {}, contains() { return false; }, closest() { return null; }, focus() {} });
  sb.document = { readyState: 'complete', addEventListener() {}, removeEventListener() {}, getElementById() { return null; }, querySelector() { return null; }, createElement: el, body: { appendChild() {}, contains() { return true; } } };
  sb.matchMedia = () => ({ matches: false });
  sb.openModal = () => el(); sb.closeModal = () => {};
  sb.INBOX = rows; sb.INBOX_SNOOZED = []; sb.INBOX_FAILED = []; sb.INBOX_TRUNCATED = [];
  sb.EP = {
    authed: true, role: 'admin', user: { name: 'عبد الرحمن عطية' },
    state: { opsQueue: 'ready', inbox: 'ready', walletPayouts: 'ready', invites: 'ready', pendingUsers: 'ready', market: 'ready' },
    data: { opsQueue: { courses_pending: { count: 1, titles: ['صياغة العقود'] } }, walletPayouts: { rows: payouts, hidden: [], count: 1 }, invites: { rows: invites }, pendingUsers: { rows: [] }, market: { rows: [] }, snooze: { map: { 'topic:tpX': { key: 'topic:tpX', kind: 'snooze', until: '2099-01-01T08:00:00Z', fingerprint: '' } }, ok: true, at: 1 } },
    ensure() {}, reload() {}, decideInboxItem() { return Promise.resolve({ ok: true }); }, api() { return Promise.resolve({}); }
  };
  sb.V2_HOST = Object.assign({ isHome: () => true, openRow() { return true; }, openReading() { return true; }, openSection() {}, goOps() {}, go() {}, current: () => 'home', state: () => ({ section: 'home', tab: 'board' }) }, extra || {});
  vm.createContext(sb);
  ['v2-logic.js', 'v2-home.js', 'v2-strip.js', 'v2-d2.js'].forEach((f) => vm.runInContext(fs.readFileSync(path.join(dc, f), 'utf8'), sb));
  return sb;
}
const css = ['v2-home.css', 'v2-shell.css', 'v2-d2.css', 'v2-strip.css'].map((f) => '<link rel="stylesheet" href="file://' + path.join(dc, f) + '">').join('');
function page(name, title, body, opts) {
  opts = opts || {};
  const sb = opts.sb;
  const side = sb ? sidebar(sb, opts.active || 'home') : '';
  const html = '<!doctype html><html lang="ar" dir="rtl"><head><meta charset="utf-8"><title>' + title + '</title>'
    + '<style>@font-face{font-family:x;src:local(Arial)}html,body{margin:0;background:#F7F3ED;font-family:"IBM Plex Sans Arabic","Cairo",Tahoma,sans-serif}</style>' + css
    + '<style>.pv{display:grid;grid-template-columns:250px 1fr;min-height:100vh}.pv-main{padding:26px 34px 40px;min-width:0}.v2-side{display:flex!important;height:auto}.v2-sec{display:block}</style></head>'
    + '<body><div class="app v2-shell"><div class="pv">' + (side ? '<aside id="v2Side" class="v2-side">' + side + '</aside>' : '') + '<main class="pv-main">' + body + '</main></div></div></body></html>';
  fs.writeFileSync(path.join(out, name), html);
}
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

// ١) اللوحة
let sb = bootSandbox();
const dummy = () => ({ style: {}, onclick: null, offsetHeight: 0, querySelectorAll() { return []; }, querySelector() { return null; }, getAttribute() { return null; }, setAttribute() {} });
const mkView = () => ({ innerHTML: '', querySelectorAll() { return []; }, querySelector() { return dummy(); }, addEventListener() {} });
let v = mkView();
sb.V2.render(v);
page('01-home.html', 'اللوحة', v.innerHTML, { sb, active: 'home' });
// ٢) «ابدأ القرارات»
sb = bootSandbox();
v = mkView();
sb.V2.render(v);
sb.V2._state.mode = 'focus';
sb.V2._state.deck = sb.V2.split().decisions.slice(); sb.V2._state.total = sb.V2._state.deck.length;
sb.V2.render(v);
page('02-decisions-focus.html', 'ابدأ القرارات', v.innerHTML, { sb, active: 'home' });
// ٣) شرائط الأقسام
function stripPage(file, key, tab, note) {
  const s2 = bootSandbox({ current: () => key, state: () => ({ section: key, tab: tab || sb.V2L.sectionByKey(key).tabs[0].key }) });
  const z = { innerHTML: '', hidden: false, setAttribute() {}, getAttribute() { return null; }, querySelectorAll() { return []; }, querySelector() { return null; } };
  s2.V2STRIP.mount(key, z, false);
  page(file, s2.V2L.sectionByKey(key).label, heading(s2, key, tab) + '<div class="v2-strip">' + z.innerHTML + '</div>' + (note ? '<div class="v2z" style="margin-top:14px"><p class="v2z-empty">' + note + '</p></div>' : ''), { sb: s2, active: key });
}
stripPage('03-people.html', 'people', 'users', 'تحت الشريط قايمة الناس (بحث · الكل · خبراء · مدرّبون · أعضاء · زوّار · الرسائل) — بلا أي زرار قرار مكرّر.');
stripPage('04-files.html', 'files', 'files');
stripPage('05-money.html', 'money', 'overview');
stripPage('06-disputes.html', 'disputes', 'disputes');
stripPage('07-courses-empty-strip.html', 'courses', 'courses');
stripPage('08-company-empty-strip.html', 'company', 'invest');
// ٩) صفحة الشخص
const personResp = {
  email: 'mona@example.test', found: true, sources: { users: 'ok', invites: 'ok' }, roles: ['visitor', 'trainer_pending'],
  identity: { name: 'منى عبد الحميد', is_active: true, joined_at: new Date(now - 60 * 24 * H).toISOString(), last_login_at: new Date(now - 5 * H).toISOString(), country: 'مصر', trainer_status: 'pending', invited_by: { name: 'سارة', kind: 'member' } },
  expert: { files_count: 0, partial: false, latest: [] }, trainer: { status: 'pending', courses_count: 0, students_count: 0 }, money: null, learner: { enrollments_count: 1, reservations_count: 0 }, books: null, log: [],
  request_sources: {},
  requests: [
    { kind: 'pending_user', id: 'u1', at: new Date(now - 3 * H).toISOString(), name: 'منى عبد الحميد', role: 'محامية', country: 'مصر', flags: [] },
    { kind: 'trainer', id: 't1', at: new Date(now - 48 * H).toISOString(), name: 'منى', join_as: 'both', headline: 'محامية بالنقض، ١٢ سنة خبرة' },
    { kind: 'identity_doc', id: 'i1', at: new Date(now - 5 * H).toISOString(), name: 'منى', title: 'محامية' },
    { kind: 'founding', id: 'f7', at: new Date(now - 90 * H).toISOString(), name: 'منى', status: 'invited', spec: 'عقود' },
    { kind: 'signup', id: 'u1', at: new Date(now - 60 * 24 * H).toISOString(), name: 'منى', provider: 'google', where: 'مصر' }
  ]
};
const sp = bootSandbox({ current: () => 'v2person', state: () => ({ section: 'people', tab: 'person', person: 'mona@example.test' }) });
sp.EP.api = () => Promise.resolve(personResp);
const pv = mkView();
sp.V2D2.render('v2person', pv);
setImmediate(() => {
  page('09-person.html', 'صفحة الشخص', heading(sp, 'people', 'person') + '<div id="view" class="v2d-wrap">' + pv.innerHTML + '</div>', { sb: sp, active: 'people' });
  console.log(fs.readdirSync(out).sort().join('\n'));
});
