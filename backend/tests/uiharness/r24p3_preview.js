// R24 م٣ — معاينات HTML ثابتة (مش PNG): بيرسم الشاشات الحقيقية في node:vm ببيانات مزيّفة، ويكتب ملفات `.html` بتحمّل نفس CSS الحقيقي من
// `dashboard-cloud/` (مسارات مطلقة). تتفتح في أي متصفح أو تتصوّر منه.
//   node r24p3_preview.js <out_dir>
//   ١) 01-brain-rules.html        تبويب «العقل وقواعده» (جدول المستويات)
//   ٢) 02-home-alone-box.html     اللوحة وفيها صندوق «العقل عمل لوحده النهارده» ممتلئ بـ«رجّعها»
//   ٣) 03-decision-review-learn.html  بطاقة قرار فيها «راجعت…» وشريطة «تخليني أعملها لوحدي؟»
//   ٤) 04-alone-log.html          «اللي عمله لوحده» (السجل كله)
// ⛔ ولا شبكة ولا منفذ: كله في الذاكرة.
const vm = require('vm');
const fs = require('fs');
const path = require('path');
const out = process.argv[2];
if (!out) { console.error('usage: node r24p3_preview.js <out_dir>'); process.exit(2); }
fs.mkdirSync(out, { recursive: true });
const dc = path.join(__dirname, '..', '..', '..', 'dashboard-cloud');
const now = Date.now();
const H = 3600e3;
const iso = (t) => new Date(t).toISOString();

const T = (id, group, title, level, kw) => Object.assign({ id, group, title, hint: '', level, default: level, locked: false, lock: '', lock_text: '', reversible: true, eligible: true,
  levels: ['alone', 'suggest', 'ask'], external: '', unit: ['طلبات', 'طلبًا'], stats: { kind: 'none' }, learn: { n: 0, show: false }, updated_at: null, updated_by: null }, kw || {});
const LOCKED = (id, title, hint, lock) => T(id, 'locked', title, 'suggest', { hint, locked: true, lock, lock_text: 'دايمًا بموافقتك', reversible: false, eligible: false, levels: ['suggest', 'ask'], stats: { kind: 'locked' } });
const LEVELS = {
  streak_needed: 8,
  groups: [{ key: 'people', title: 'الناس' }, { key: 'files', title: 'ملفات الخبراء' }, { key: 'content', title: 'المحتوى' }, { key: 'notes', title: 'ملاحظات العقل' }, { key: 'locked', title: 'الفلوس والنشر للناس' }],
  types: [
    T('application_review', 'people', 'مراجعة طلب انضمام خبير أو مدرّب', 'suggest', { hint: 'السيرة، والفيديو، ورقم القيد، والهوية', stats: { kind: 'approvals', n: 8, of: 8 }, learn: { n: 8, show: true }, unit: ['طلبات انضمام', 'طلب انضمام'] }),
    T('visitor_open', 'people', 'فتح المنصة لزائر عادي', 'alone', { hint: 'إيميل عادي من غير علامة اشتباه', stats: { kind: 'times', n: 23 }, unit: ['زوّار', 'زائرًا'] }),
    T('reply_draft', 'people', 'الرد على رسائل الموقع', 'suggest', { hint: 'يكتب الرد وانت تبعته', locked: true, lock: 'message', lock_text: 'دايمًا بموافقتك', reversible: false, eligible: false, levels: ['suggest', 'ask'], stats: { kind: 'locked' } }),
    T('file_assign', 'files', 'توزيع ملف على خبير', 'alone', { hint: 'حسب التخصص والضغط', levels: ['alone', 'suggest'], external: 'auto_assign', stats: { kind: 'external' } }),
    T('file_review', 'files', 'مراجعة أول رأي لخبير جديد', 'suggest', { hint: 'يراجعه قبل ما يوصل العميل', locked: true, lock: 'message', lock_text: 'دايمًا بموافقتك', reversible: false, eligible: false, levels: ['suggest', 'ask'], stats: { kind: 'locked' } }),
    T('comment_reject_abusive', 'content', 'إخفاء تعليق مسيء بوضوح', 'suggest', { hint: 'لما فحص التعليقات يحكم إنه مسيء', stats: { kind: 'approvals', n: 5, of: 6 } }),
    T('seo_notes', 'content', 'ملاحظات الظهور في البحث على المسودات', 'alone', { hint: 'ملاحظة داخلية بس', stats: { kind: 'times', n: 12 }, unit: ['ملاحظات', 'ملاحظة'] }),
    T('opinion', 'notes', 'رأي العقل في كل قرار', 'alone', { hint: 'سطر على بطاقة القرار', levels: ['alone', 'ask'], stats: { kind: 'times', n: 61 } }),
    T('weekly_read', 'notes', 'قراءة الأسبوع', 'ask', { stats: { kind: 'none' } }),
    LOCKED('payout', 'تحويل أرباح خبير أو مدرّب', 'يراجع الحساب ويقترح', 'money'),
    LOCKED('manual_payment', 'تأكيد إيصال تحويل', 'يطابق الإيصال ويقترح', 'money'),
    LOCKED('course_review', 'نشر دورة جديدة', 'يراجع الدروس ويكتب ملاحظته', 'publish'),
    LOCKED('topic_publish', 'موضوع من عضو في الساحة', '', 'publish'),
  ]
};
const ALONE = [
  { id: '1'.repeat(32), work_type: 'visitor_open', what: 'فتح المنصة لـسلمى', target_ref: 'pu:1', at: iso(now - 3 * H), undone: false, can_undo: true, undo_note: '' },
  { id: '2'.repeat(32), work_type: 'visitor_open', what: 'فتح المنصة لـنادية', target_ref: 'pu:2', at: iso(now - 3 * H + 6e4), undone: false, can_undo: true, undo_note: '' },
  { id: '3'.repeat(32), work_type: 'visitor_open', what: 'فتح المنصة لـعلي', target_ref: 'pu:3', at: iso(now - 3 * H + 12e4), undone: false, can_undo: true, undo_note: '' },
  { id: '4'.repeat(32), work_type: 'comment_reject_abusive', what: 'إخفاء تعليق مسيء على «نفقة الصغير»', target_ref: 'op:9', at: iso(now - 2 * H), undone: false, can_undo: true, undo_note: '' },
  { id: '5'.repeat(32), work_type: 'seo_notes', what: 'كتب ملاحظة بحث على «مقال الإيجار»', target_ref: 'x1', at: iso(now - 1 * H), undone: false, can_undo: true, undo_note: '' },
  { id: '6'.repeat(32), work_type: 'seo_notes', what: 'كتب ملاحظة بحث على «مقال النفقة»', target_ref: 'x2', at: iso(now - 5 * H), undone: false, can_undo: false, undo_note: 'الملاحظة اتحسمت قبل كده' },
  { id: '7'.repeat(32), work_type: 'comment_reject_abusive', what: 'إخفاء تعليق مسيء على «عقد العمل»', target_ref: 'op:3', at: iso(now - 26 * H), undone: true, can_undo: false, undo_note: 'اترجّعت' },
];
const POINTS = [
  { ok: true, text: 'السيرة وصلت: ملف واحد مرفق' },
  { ok: true, text: 'الفيديو وصل' },
  { ok: true, text: 'رقم القيد مكتوب' },
  { ok: false, text: 'صورة بطاقة الهوية لسه بتستنى مراجعتك' },
];
const REVIEW_ITEM = { id: 'a'.repeat(32), producer: 'application_review', section: 'people', kind: 'note', target_label: 'مراجعة طلب انضمام: منى عبد الحميد', tag: 'مراجعة طلب انضمام', status: 'proposed',
  body: { text: 'اقبلوا الطلب بعد مراجعة وثيقة الهوية', why: 'الورق كامل ما عدا وثيقة الهوية، والمراجعة مبنية على ما وصل فقط من غير قراءة السيرة', recommend: 'open', points: POINTS, approve_label: 'احتفظ بها' },
  created_at: iso(now - 2 * H), approve_label: 'احتفظ بها' };
const TRAINER = { apiKind: 'trainer', apiId: 't1', ref: 'TRN-1', who: 'منى عبد الحميد', personEmail: 'mona@example.test', ts: now - 48 * H, canReject: true, rejectNeedsReason: true, trJoin: 'both', trHeadline: 'محامية بالنقض، ١٢ سنة خبرة', trSpec: 'عقود' };
const VISITOR = { apiKind: 'pending_user', apiId: 'u9', ref: 'PU-9', who: 'أحمد سمير', personEmail: 'ahmed@example.test', email: 'ahmed@example.test', ts: now - 3 * H, canReject: true, flagLabels: [], puCountry: 'السعودية', puRole: 'محامٍ' };
const API = {
  'GET /v2/brain/levels': LEVELS,
  'GET /v2/brain/alone-log?day=today': { rows: ALONE.filter((r) => Date.parse(r.at) > now - 12 * H) },
  'GET /v2/brain/alone-log?day=all': { rows: ALONE },
  'GET /v2/brain/learn': { streak_needed: 8, prompts: [{ work_type: 'application_review', n: 8, title: 'مراجعة طلب انضمام خبير أو مدرّب', unit: ['طلبات انضمام', 'طلب انضمام'] }, { work_type: 'visitor_open', n: 9, title: 'x', unit: ['زوّار', 'زائرًا'] }] },
  'GET /v2/brain/reviews': { reviews: { 'trainer:t1': { producer: 'application_review', text: 'اقبلوا الطلب بعد مراجعة وثيقة الهوية', why: 'الورق كامل ما عدا وثيقة الهوية', recommend: 'open', points: POINTS, source: 'ai', created_at: iso(now - 2 * H) } } },
};

function stub() {
  const el = () => ({ innerHTML: '', style: {}, dataset: {}, classList: { add() {}, remove() {}, toggle() {} }, children: [], onclick: null, addEventListener() {}, setAttribute() {}, getAttribute() { return null; }, querySelector() { return null; }, querySelectorAll() { return []; }, remove() {}, contains() { return true; }, closest() { return null; }, focus() {}, scrollIntoView() {} });
  return el;
}
function boot(mode, extra) {
  const sb = { console, setTimeout: (f, ms) => { if (ms && ms >= 1000) return 0; f(); return 0; }, clearTimeout() {}, setInterval() { return 1; }, clearInterval() {}, Promise, JSON, Math, Date, Intl, Object, Array, String, Number, Error, RegExp, WeakMap };
  const el = stub();
  sb.window = sb;
  sb.document = { readyState: 'complete', addEventListener() {}, removeEventListener() {}, getElementById() { return null; }, querySelector() { return null; }, querySelectorAll() { return []; }, createElement: el, body: { appendChild() {}, contains() { return true; } }, activeElement: null };
  sb.matchMedia = () => ({ matches: false });
  sb.localStorage = { getItem() { return null; }, setItem() {} };
  sb.openModal = () => el(); sb.closeModal = () => {}; sb.toast = () => {};
  sb.INBOX = (extra && extra.inbox) || []; sb.INBOX_SNOOZED = []; sb.INBOX_FAILED = []; sb.INBOX_TRUNCATED = [];
  sb.EP = { authed: true, role: 'admin', user: { name: 'عبد الرحمن عطية' },
    state: { opsQueue: 'ready', inbox: 'ready', walletPayouts: 'ready', invites: 'ready', pendingUsers: 'ready', market: 'ready', aiAgents: 'ready', inviteSettings: 'ready' },
    data: { opsQueue: {}, walletPayouts: { rows: [], hidden: [], count: 0 }, invites: { rows: [] }, pendingUsers: { rows: [] }, market: { rows: [] }, snooze: { map: {}, ok: true, at: 1 }, aiAgents: { agents: [] }, inviteSettings: {} },
    ensure() {}, reload() {}, api(p, o) { const k = ((o && o.method) || 'GET') + ' ' + p; return API[k] !== undefined ? Promise.resolve(JSON.parse(JSON.stringify(API[k]))) : Promise.reject({ status: 404, data: {} }); } };
  sb.V2_HOST = { isHome: () => mode === 'home', current: () => (mode === 'tab' ? 'v2s_brain' : 'home'), openRow() { return true; }, openReading() { return true; }, openSection() {}, goOps() {}, go() {},
                 state: () => ({ section: mode === 'tab' ? 'company' : 'home', tab: mode === 'tab' ? 'brain' : 'board' }) };
  sb.V2SHELL = { on: true };
  vm.createContext(sb);
  ['v2-logic.js', 'v2-home.js', 'v2-strip.js', 'v2-levels.js', 'v2s/_registry.js', 'v2s/brain.js'].forEach((f) => vm.runInContext(fs.readFileSync(path.join(dc, f), 'utf8'), sb));
  if (extra && extra.brain) sb.V2BRAIN = { pending: () => extra.brain, decorate: (c) => c, prefetch() {}, sig: () => '1', listen: () => () => {}, reload() {}, act() {} };
  return sb;
}
const flush = async () => { for (let i = 0; i < 8; i++) await new Promise((r) => setImmediate(r)); };
const dummy = () => ({ style: {}, onclick: null, offsetHeight: 0, dataset: {}, querySelectorAll() { return []; }, querySelector() { return null; }, getAttribute() { return null; }, setAttribute() {}, addEventListener() {}, remove() {} });
const view = () => ({ innerHTML: '', onclick: null, oninput: null, onkeydown: null, contains() { return true; }, querySelectorAll() { return []; }, querySelector() { return dummy(); }, addEventListener() {} });
const css = ['v2-home.css', 'v2-shell.css', 'v2-d2.css', 'v2-d3.css', 'v2-strip.css', 'v2-brain2.css', 'v2-levels.css', 'v2s/brain.css'].map((f) => '<link rel="stylesheet" href="file://' + path.join(dc, f) + '">').join('');
function sidebar(sb, active) {
  const L = sb.V2L, tiles = {};
  try { sb.V2.tiles().forEach((t) => { tiles[t.key] = t; }); } catch (e) {}
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
function page(name, title, body, sb, active) {
  const html = '<!doctype html><html lang="ar" dir="rtl"><head><meta charset="utf-8"><title>' + title + '</title>'
    + '<style>@font-face{font-family:x;src:local(Arial)}html,body{margin:0;background:#F7F3ED;font-family:"IBM Plex Sans Arabic","Cairo",Tahoma,sans-serif}</style>' + css
    + '<style>.pv{display:grid;grid-template-columns:250px 1fr;min-height:100vh}.pv-main{padding:26px 34px 40px;min-width:0}.v2-side{display:flex!important;height:auto}.v2-sec{display:block}.v2-focus .v2-fgrid{max-width:760px}</style></head>'
    + '<body><div class="app v2-shell"><div class="pv"><aside id="v2Side" class="v2-side">' + sidebar(sb, active) + '</aside><main class="pv-main">' + body + '</main></div></div></body></html>';
  fs.writeFileSync(path.join(out, name), html);
}

(async () => {
  // ١) تبويب «العقل وقواعده»
  let sb = boot('tab');
  let v = view();
  sb.V2SEC.brain.render('v2s_brain', v); await flush(); sb.V2SEC.brain.render('v2s_brain', v);
  page('01-brain-rules.html', 'العقل وقواعده', heading(sb, 'company', 'brain') + '<div id="view">' + v.innerHTML + '</div>', sb, 'company');
  // ٤) «اللي عمله لوحده»
  sb = boot('tab'); v = view();
  sb.V2SEC.brain.want('alone');
  sb.V2SEC.brain.render('v2s_brain', v); await flush(); sb.V2SEC.brain.render('v2s_brain', v);
  page('04-alone-log.html', 'اللي عمله لوحده', heading(sb, 'company', 'brain') + '<div id="view">' + v.innerHTML + '</div>', sb, 'company');
  // ٢) اللوحة وصندوق «العقل عمل لوحده النهارده»
  sb = boot('home', { inbox: [VISITOR, TRAINER] }); v = view();
  sb.V2.render(v); await flush(); sb.V2.render(v);
  page('02-home-alone-box.html', 'اللوحة', '<div id="view">' + v.innerHTML + '</div>', sb, 'home');
  // ٣) بطاقة قرار: «راجعت…» + شريطة «تخليني أعملها لوحدي؟» (اقتراح العقل على مراجعة طلب الانضمام، والبطاقة الثانية زائر عادي)
  sb = boot('home', { inbox: [TRAINER], brain: [REVIEW_ITEM] }); v = view();
  const d = sb.V2.split().decisions;
  const first = d.filter((c) => c.kind === 'brain_item')[0] || d[0];
  sb.V2._state.deck = [first].concat(d.filter((c) => c !== first)); sb.V2._state.total = d.length; sb.V2._state.mode = 'focus';
  sb.V2.render(v); await flush(); sb.V2.render(v);
  page('03-decision-review-learn.html', 'ابدأ القرارات', '<div id="view">' + v.innerHTML + '</div>', sb, 'home');
  // ٣-ب) نفس الشغل في شريط قسم الناس (بطاقة طلب الانضمام عليها «راجعت…»)
  sb = boot('home', { inbox: [TRAINER, VISITOR] });
  const z = { innerHTML: '', hidden: false, setAttribute() {}, getAttribute() { return null; }, querySelectorAll() { return []; }, querySelector() { return null; } };
  sb.V2STRIP.mount('people', z, false); await flush(); sb.V2STRIP.mount('people', z, false);
  page('05-people-strip.html', 'الناس', heading(sb, 'people', 'users') + '<div class="v2-strip">' + z.innerHTML + '</div>', sb, 'people');
  // ٦) شريط قسم فاضي بسطر «للعلم» الحقيقي (بدل الشريط الكحلي القديم) + شرائط «العقل» الفاتحة
  sb = boot('home', { inbox: [] });
  const z2 = { innerHTML: '', hidden: false, setAttribute() {}, getAttribute() { return null; }, querySelectorAll() { return []; }, querySelector() { return null; } };
  sb.V2STRIP.info('files', 'التوزيع التلقائي يعمل، ووزّع ٣ ملفات اليوم');
  sb.V2STRIP.mount('files', z2, false); await flush(); sb.V2STRIP.mount('files', z2, false);
  page('06-files-strip-info.html', 'ملفات الخبراء', heading(sb, 'files', 'files') + '<div class="v2-strip">' + z2.innerHTML + '</div>', sb, 'files');
  console.log(fs.readdirSync(out).sort().join('\n'));
})();
