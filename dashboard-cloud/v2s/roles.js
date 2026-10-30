/* ============================================================================
 * v2s/roles.js — شاشات غير الأدمن بالشكل الجديد: المدرّب (لوحتي · دوراتي · أرباحي) · المستثمر (محفظتي · فرص الاستثمار · استثماراتي) ·
 * فريق المتابعة (الأعضاء · الدورات · الموضوعات · دليل الاستخدام، للاطلاع فقط) · الحساب بانتظار التفعيل.
 *
 * ⛔ لا منطق عمل هنا: الأرقام والجمل والتصنيفات كلها من `V2L.roles` (نقي، في v2-logic.js)؛ هذا الملف يجلب ويرسم فقط.
 * ⛔ المفتاح: `GET /api/v2/roles/config` ⇒ enabled:true وإلا لا يتغيّر شيء (الشاشات القديمة كما هي حرفيًا). مفتاح رجوع خاص:
 *    `DASH_V2_ROLES_ENABLED=false` على الخادم.
 * ⛔ كل مصدر يفشل لوحده: رقمه «غير متاح بعد» لا صفر، وبجانبه «أعد المحاولة». والصفر الحقيقي «٠».
 * ⛔ فلوس: زرّ واحد فقط يكتب (طلب سحب) وبعد ورقة المراجعة، ويرسل `confirmed:true` إلى `/api/v2/roles/withdraw`.
 * ⛔ مسار الأدمن لا يُمَسّ: كل دالة مغلَّفة تنادي الأصل فورًا لو الدور أدمن.
 * ========================================================================== */
(function () {
  'use strict';
  var L = window.V2L;
  if (!L || !L.roles) return;
  var R = L.roles, U = L.util;
  var V = window.V2R = { active: false, role: '', flag: 'idle', hooks: {} };

  var ROLEKEY = { trainer: 'trainer', investor: 'investor', employee: 'staff', viewer: 'viewer' };
  var RGB = { courses: '91,74,170', money: '26,43,74', company: '58,60,72', people: '24,126,78', content: '190,88,48', books: '14,120,130', home: '158,43,78' };
  var PLATFORM_URL = 'https://app.elprofessor.net/?page=trainer';
  var MEMO = 'ep_v2_roles';
  var PAGE = 100;
  var SRC_NAME = { me: 'حسابك', courses: 'دوراتك', payouts: 'مستحقاتك', wallet: 'محفظتك', badges: 'الشارات', active: 'استثماراتك', history: 'استثماراتك',
                   opps: 'فرص الاستثمار', people: 'الأعضاء', pcourses: 'الدورات', topics: 'الموضوعات', tutorials: 'دليل الاستخدام' };
  var PATH = { me: '/v2/roles/config', courses: '/courses', payouts: '/payouts', wallet: '/me/investor-wallet', badges: '/investor/badges',
               active: '/investments/active', history: '/investments/history', opps: '/investment-opportunities', people: '/platform-users',
               pcourses: '/platform-courses', topics: '/platform-topics', tutorials: '/tutorials' };

  var LOGO = '<svg viewBox="0 0 798 588" aria-hidden="true"><path fill="currentColor" d="M389 50 Q389 0 439 0 L672 0 Q762 0 762 90 L762 347 L675 347 L675 353 L572 353 L572 588 L496 588 L496 493 L462 493 L462 588 L386 588 L386 493 L302 493 L302 588 L228 588 L228 493 L201 493 L201 588 L104 588 L104 335 L76 335 L76 409 L0 409 L0 351 L40 351 L40 182 L108 182 L108 106 L389 106 Z"/><path fill="currentColor" d="M675 337 L762 337 L762 421 L798 421 L798 492 L675 492 Z"/></svg>';
  var GRID = '<svg viewBox="0 0 24 24" class="v2s-ic" aria-hidden="true"><rect x="3" y="3" width="7" height="7" rx="1.5"/><rect x="14" y="3" width="7" height="7" rx="1.5"/><rect x="3" y="14" width="7" height="7" rx="1.5"/><rect x="14" y="14" width="7" height="7" rx="1.5"/></svg>';
  var OUT = '<svg viewBox="0 0 24 24" class="v2s-ic" aria-hidden="true"><path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4"/><path d="m16 17 5-5-5-5"/><path d="M21 12H9"/></svg>';
  var CLOSE = '<svg viewBox="0 0 24 24" class="v2s-ic" aria-hidden="true"><path d="M6 6l12 12M18 6 6 18"/></svg>';
  var DOT = '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M19 12H5M11 6l-6 6 6 6"/></svg>';

  function esc(s) { return String(s == null ? '' : s).replace(/[&<>"']/g, function (c) { return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]; }); }
  function q(sel, root) { return (root || document).querySelector(sel); }
  function qa(sel, root) { return Array.prototype.slice.call((root || document).querySelectorAll(sel)); }
  function img(name) { return 'v2/img/' + name + '.jpg'; }
  function ep() { return window.EP || null; }
  function now() { return Date.now(); }
  // متغيّرات السكربت الداخلي (let/const عامة) تُقرأ بالاسم المجرّد خلف typeof ولا تُكتب أبدًا.
  var G = {
    current: function () { return typeof current !== 'undefined' ? current : ''; },
    topicsTab: function () { return typeof topicsTab !== 'undefined' ? topicsTab : ''; },
    courseTab: function () { return typeof courseTab !== 'undefined' ? courseTab : ''; },
    setters: function () { return typeof V2_SETTERS !== 'undefined' ? V2_SETTERS : null; },
    seg: function () { return typeof SEG_LABEL !== 'undefined' ? SEG_LABEL : null; }
  };

  // ------------------------------------------------------------------ الحالة
  function freshState() {
    return { tab: { i_invest: 'active', courses: 'catalog', topics: 'topics' }, chip: { users: 'all', courses: 'all', topics: 'all' }, q: '', open: {}, lim: {},
             lastKey: '', baseCapped: null, sheetDirty: false, searchT: null, sseq: 0, wd: null };
  }
  var S = freshState();
  var SRC = {};
  var GEN = 0;   // يزيد مع كل تغيّر في الحساب: أي رد متأخر من الحساب السابق يُهمَل
  function src(k) { return SRC[k] || (SRC[k] = { state: 'idle', data: null, status: 0, msg: '', seq: 0 }); }
  function st(k) { return src(k).state; }
  function pack(keys) { var o = {}; keys.forEach(function (k) { o[k] = { state: st(k), data: src(k).data }; }); return o; }

  var redrawT = null;
  function changed() {
    if (!V.active || redrawT) return;
    redrawT = setTimeout(function () { redrawT = null; V.render(); }, 0);
  }
  function load(k, force, path) {
    var s = src(k), E = ep();
    if (!E || !E.api || !PATH[k]) return;
    if (s.state === 'loading' && !force) return;
    if (!force && s.state !== 'idle') return;
    s.state = 'loading';
    var seq = ++s.seq, gen = GEN;
    E.api(path || PATH[k]).then(function (d) {
      if (seq !== s.seq || gen !== GEN) return;
      s.state = 'ready'; s.data = d; s.at = now(); s.status = 0; s.msg = '';
      if (k === 'people' && !path) S.baseCapped = R.peopleCapped(d);
      changed();
    }).catch(function (e) {
      if (seq !== s.seq || gen !== GEN) return;
      if (e && e.status === 401) return;
      s.state = 'error'; s.status = (e && e.status) || 0;
      s.msg = e && e.data && typeof e.data.error === 'string' ? e.data.error : '';
      s.data = null; changed();
    });
  }
  function need() { Array.prototype.slice.call(arguments).forEach(function (k) { load(k, false); }); }
  function reload(k) {
    var s = src(k); s.state = 'idle';
    load(k, true);
    changed();
  }

  // ------------------------------------------------------------------ التنقل والدور
  function mapRole() {
    var r = V.role;
    return ROLEKEY[r] ? r : 'viewer';
  }
  function navIds() {
    var ids = [];
    try { ids = typeof window.roleNavFor === 'function' ? window.roleNavFor(V.role) : []; } catch (e) { ids = []; }
    return ids;
  }
  function navItems() { return R.navFor(V.role, navIds(), null); }
  function curKey() {
    var c = G.current() || '';
    if (c === 'topics' && G.topicsTab() === 'tutorials') return 'tutorials';
    if (V.role === 'viewer') return 'v_pending';
    var ids = navIds();
    if (ids.indexOf(c) < 0 && !(c === 'topics' && ids.indexOf('tutorials') > -1) && ids.length) return ids[0];
    return c;
  }
  function nav(id) {
    if (typeof window.go !== 'function') return;
    window.go(id);
    if (id === 'tutorials') { try { history.replaceState(null, '', '#tutorials'); } catch (e) {} }
  }

  // ------------------------------------------------------------------ قطع الرسم الصغيرة
  function chip(c) { return '<span class="v2ro-chip ' + esc(c.tone) + '">' + esc(c.t) + '</span>'; }
  function loadBlock() { return '<div class="v2ro-load">…جارٍ التحميل</div>'; }
  function retryBtn(k) { return '<button type="button" class="v2ro-link" data-r-act="retry" data-k="' + k + '">أعد المحاولة</button>'; }
  function failStrip(k, name, withNums) {
    var s = src(k);
    var msg = s.status === 403 && s.msg ? s.msg : 'تعذّر جلب ' + (name || SRC_NAME[k]) + '.' + (withNums ? ' الأرقام التي تعتمد عليه تظهر «غير متاح بعد».' : '');
    return '<div class="v2ro-fail" role="status"><span>' + esc(msg) + '</span>' + retryBtn(k) + '</div>';
  }
  function emptyBlock(t, p, extra) { return '<div class="v2ro-empty"><b>' + esc(t) + '</b>' + (p ? '<p>' + esc(p) + '</p>' : '') + (extra || '') + '</div>'; }
  function cardState(keys, off) {
    if (off) return 'na';
    var res = 'ready';
    keys.forEach(function (k) {
      var s = st(k);
      if (s === 'error') res = 'na';
      else if ((s === 'idle' || s === 'loading') && res !== 'na') res = 'load';
    });
    return res;
  }
  function numCard(label, state, text, note, tone) {
    var big = state === 'load' ? '<p class="v2ro-big">…</p>' : (state === 'na' ? '<p class="v2ro-big na">' + esc(R.NA) + '</p>' : '<p class="v2ro-big">' + esc(text) + '</p>');
    return '<article class="v2ro-num ' + (tone || '') + '"><h3>' + esc(label) + '</h3>' + big + '<p class="v2ro-note">' + esc(note) + '</p></article>';
  }
  function hero(photo, line) {
    return '<section class="v2ro-hero" style="background-image:url(' + img(photo) + ')"><div class="v2ro-hb"><h2>' + esc(R.greeting(ep() && ep().user)) + '</h2><p>' + esc(line) + '</p></div></section>';
  }
  function nextCard(n) {
    if (!n) return '';
    var lk = '';
    if (n.link) lk = '<button type="button" class="v2ro-link" data-r-act="' + (n.link.act ? 'wd' : 'go') + '"' + (n.link.go ? ' data-id="' + n.link.go + '"' : '') + '>' + esc(n.link.label) + '</button>';
    return '<aside class="v2ro-next"><span class="v2ro-nd">' + DOT + '</span><p>' + esc(n.text) + '</p>' + lk + '</aside>';
  }
  function notice(t) { return '<div class="v2ro-warn" role="status">' + esc(t) + '</div>'; }
  function rowHtml(title, chipObj, lines, extra) {
    return '<article class="v2ro-row"><div class="v2ro-rb"><h3>' + esc(title) + '</h3>' + lines.filter(Boolean).map(function (l) { return '<p class="v2ro-meta">' + esc(l) + '</p>'; }).join('') + (extra || '') + '</div>'
      + (chipObj ? '<div class="v2ro-rs">' + chip(chipObj) + '</div>' : '') + '</article>';
  }
  function countLine(n, forms) { return n > 0 ? '<p class="v2ro-count">' + esc(U.U(n, forms)) + '</p>' : ''; }
  function platformLine(main) {
    return '<section class="v2ro-row v2ro-plat"><div class="v2ro-rb"><h3>مبيعات دوراتك على المنصة، وطلب التحويل منها، في لوحتك هناك.</h3>'
      + '<p class="v2ro-meta">المبيعات والطلاب والجلسات المباشرة كما تظهر لك على المنصة.</p></div>'
      + '<div class="v2ro-rs"><a class="' + (main ? 'v2ro-btn1' : 'v2ro-btn2') + '" href="' + PLATFORM_URL + '" target="_blank" rel="noopener">افتح لوحتك على المنصة</a></div></section>';
  }

  // ------------------------------------------------------------------ المدرّب
  function viewTHome() {
    need('me', 'courses', 'payouts');
    var T = R.trainerView(pack(['me', 'courses', 'payouts']), now());
    var off = T.linked === false;
    var html = hero('courses', 'هذه دوراتك ومستحقاتك كما سجّلتها الإدارة.');
    if (off) html += notice('حسابك غير مربوط باسمك في سجلات الإدارة بعد، لذلك لا تظهر دوراتك ولا مستحقاتك هنا. تواصل مع الإدارة لربطه.');
    html += nextCard(T.next);
    if (st('courses') === 'error') html += failStrip('courses', 'دوراتك', true);
    if (st('payouts') === 'error') html += failStrip('payouts', 'مستحقاتك', true);
    html += '<div class="v2ro-nums n3">'
      + numCard('دوراتي', cardState(['courses'], off), T.nums.courses == null ? '' : U.ar(T.nums.courses), 'مربوطة باسمك', 'wine')
      + numCard('المسجّلون في دوراتي', cardState(['courses'], off), T.nums.students == null ? '' : U.ar(T.nums.students), 'في كل دوراتك', 'ink')
      + numCard('مستحق لك في دفتر الإدارة', cardState(['payouts'], off), T.nums.due == null ? '' : U.fmt(T.nums.due) + ' جنيه', 'سجّلته الإدارة ولم يُحوَّل بعد', 'green')
      + '</div>';
    html += platformLine(true);
    html += '<h2 class="v2ro-h2">آخر دوراتي</h2>';
    if (st('courses') === 'ready') {
      if (!T.rows.length) html += emptyBlock('لا توجد دورات مربوطة بحسابك بعد.', '');
      else html += T.rows.slice(0, 3).map(courseRowHtml).join('') + '<button type="button" class="v2ro-link" data-r-act="go" data-id="t_courses">كل دوراتي</button>';
    } else if (st('courses') !== 'error') html += loadBlock();
    return html;
  }
  function courseRowHtml(r) { return rowHtml(r.title, r.chip, [r.meta, r.share]); }
  function viewTCourses() {
    need('courses');
    var T = R.trainerView(pack(['me', 'courses', 'payouts']), now());
    var s = st('courses');
    if (s === 'error') return failStrip('courses', 'دوراتك', false);
    if (s !== 'ready') return loadBlock();
    if (!T.rows.length) return emptyBlock('لا توجد دورات مربوطة بحسابك بعد', 'تظهر هنا كل دورة تربطها الإدارة باسمك.');
    return countLine(T.rows.length, R.COUNT.course) + T.rows.map(courseRowHtml).join('');
  }
  function walletBlock(W, withTitle) {
    var html = '';
    html += '<div class="v2ro-nums">'
      + numCard('متاح للسحب', 'ready', U.fmt(W.balanceEgp) + ' جنيه', 'بعد خصم طلبات السحب قيد المراجعة', 'wine')
      + numCard('إجمالي ما استثمرته', 'ready', U.fmt(W.investedEgp) + ' جنيه', 'كل استثماراتك', 'ink')
      + numCard('عوائد مستلمة', 'ready', U.fmt(W.returnsEgp) + ' جنيه', 'من الاستثمارات المنتهية', 'green')
      + numCard('سحب قيد المراجعة', 'ready', W.pending.value, W.pending.note, 'amber')
      + '</div><p class="v2ro-fine">القيم مسجّلة بالدولار وتظهر بالجنيه بسعر الصرف الحالي.</p>';
    html += withdrawArea(W);
    return html;
  }
  function withdrawArea(W) {
    if (W.canWithdraw) return '<div class="v2ro-wdrow"><button type="button" class="v2ro-btn1" data-r-act="wd">اطلب سحب الرصيد</button></div>';
    if (W.balanceEgp === 0) return '<p class="v2ro-fine">لا يوجد رصيد متاح للسحب الآن.</p>';
    return '';
  }
  function viewTEarnings() {
    need('me', 'payouts', 'wallet', 'active');
    var E = R.trainerEarnings(pack(['payouts', 'wallet', 'active']), now());
    var html = '<h2 class="v2ro-h2">من الدورات</h2>';
    if (st('payouts') === 'error') html += failStrip('payouts', 'مستحقاتك', true);
    var s = cardState(['payouts'], false);
    html += '<div class="v2ro-nums n3">'
      + numCard('مستحق لك في دفتر الإدارة', s, E.due == null ? '' : U.fmt(E.due) + ' جنيه', 'لم يُحوَّل بعد', 'wine')
      + numCard('حُوّل إليك', s, E.paid == null ? '' : U.fmt(E.paid) + ' جنيه', 'منذ البداية', 'green')
      + numCard('آخر ٣٠ يومًا', s, E.last30 == null ? '' : U.fmt(E.last30) + ' جنيه', 'سُجّل لك في آخر ٣٠ يومًا', 'ink')
      + '</div>';
    var W = E.wallet;
    var drawsWd = !!(W && W.linked && W.canWithdraw);
    html += platformLine(!drawsWd);
    html += '<h2 class="v2ro-h3">سجل المستحقات</h2>';
    if (st('payouts') === 'ready') {
      if (!E.list.length) html += emptyBlock('لا توجد مستحقات مسجّلة باسمك بعد.', '');
      else html += E.list.map(function (r) { return rowHtml(r.title, r.chip, [r.date], '<p class="v2ro-amt">' + esc(r.amountText) + '</p>'); }).join('');
    } else if (st('payouts') !== 'error') html += loadBlock();
    html += '<p class="v2ro-fine">مستحقات الدفتر تحوّلها الإدارة إليك، وتظهر هنا حين تُسجَّل.</p>';
    // الجزء ب: محفظة الاستثمار
    if (st('wallet') === 'error') {
      html += '<h2 class="v2ro-h2">محفظة الاستثمار</h2>' + failStrip('wallet', 'محفظتك', false);
    } else if (W && W.linked) {
      html += '<h2 class="v2ro-h2">محفظة الاستثمار</h2>' + walletBlock(W, true);
      if (st('active') === 'error') html += failStrip('active', 'استثماراتك', false);
      else if (st('active') === 'ready') {
        var rows = E.activeRows;
        if (rows.length) html += '<h2 class="v2ro-h3">استثماراتك الجارية</h2>' + rows.map(invRowHtml).join('');
      }
    }
    return html;
  }

  // ------------------------------------------------------------------ المستثمر
  function viewIHome() {
    need('wallet', 'badges', 'opps', 'active');
    var wv = st('wallet') === 'ready' ? R.walletView(src('wallet').data) : null;
    var off = !!(wv && wv.linked === false);
    var html = hero('company', 'رصيدك واستثماراتك كما سجّلتها الإدارة.');
    if (off) html += notice('حسابك غير مربوط بمحفظة بعد، لذلك لا يظهر رصيدك هنا. تواصل مع الإدارة لربطه.');
    html += nextCard(R.investorNext(pack(['wallet', 'opps'])));
    if (st('wallet') === 'error') html += failStrip('wallet', 'محفظتك', true);
    var s = cardState(['wallet'], off);
    var W = wv && wv.linked ? wv : null;
    html += '<div class="v2ro-nums">'
      + numCard('متاح للسحب', s, W ? U.fmt(W.balanceEgp) + ' جنيه' : '', 'بعد خصم طلبات السحب قيد المراجعة', 'wine')
      + numCard('إجمالي ما استثمرته', s, W ? U.fmt(W.investedEgp) + ' جنيه' : '', 'كل استثماراتك', 'ink')
      + numCard('عوائد مستلمة', s, W ? U.fmt(W.returnsEgp) + ' جنيه' : '', 'من الاستثمارات المنتهية', 'green')
      + numCard('سحب قيد المراجعة', s, W ? W.pending.value : '', W ? W.pending.note : 'تراجعه الإدارة', 'amber')
      + '</div>';
    if (W) html += '<p class="v2ro-fine">القيم مسجّلة بالدولار وتظهر بالجنيه بسعر الصرف الحالي.</p>' + withdrawArea(W);
    // المستوى والشارات
    if (W) {
      var bv = st('badges') === 'ready' ? R.badgesView(src('badges').data) : null;
      var line = st('badges') === 'error' ? 'الشارات: ' + R.NA : (bv ? bv.line : 'الشارات: …');
      html += '<section class="v2ro-row v2ro-lvl"><div class="v2ro-rb"><h3>مستواك: ' + esc(W.level) + '</h3><p class="v2ro-meta">' + esc(line) + '</p>'
        + (bv && bv.earned.length ? '<div class="v2ro-chips-line">' + bv.earned.map(function (t) { return chip({ t: t, tone: 'wine' }); }).join('') + '</div>' : '') + '</div></section>';
    }
    // الاختصارات
    var oppLine = st('opps') === 'error' ? R.NA : (st('opps') === 'ready' ? (R.openOppCount(src('opps').data) > 0 ? 'المفتوحة الآن: ' + U.U(R.openOppCount(src('opps').data), R.COUNT.opp) : 'لا توجد فرص مفتوحة الآن') : '…');
    var actN = st('active') === 'ready' ? (Array.isArray(src('active').data) ? src('active').data.length : 0) : null;
    var invLine = st('active') === 'error' ? R.NA : (actN == null ? '…' : (actN > 0 ? 'الجارية: ' + U.U(actN, R.COUNT.invest) : 'لا توجد استثمارات جارية'));
    html += '<a class="v2ro-row v2ro-go" href="#i_market" data-r-act="go" data-id="i_market"><div class="v2ro-rb"><h3>فرص الاستثمار</h3><p class="v2ro-meta">' + esc(oppLine) + '</p></div></a>'
      + '<a class="v2ro-row v2ro-go" href="#i_invest" data-r-act="go" data-id="i_invest"><div class="v2ro-rb"><h3>استثماراتي</h3><p class="v2ro-meta">' + esc(invLine) + '</p></div></a>';
    return html;
  }
  function viewIMarket() {
    need('opps');
    var s = st('opps');
    if (s === 'error') return failStrip('opps', 'فرص الاستثمار', false);
    if (s !== 'ready') return loadBlock();
    var rows = Array.isArray(src('opps').data) ? src('opps').data : [];
    var html = '<aside class="v2ro-next v2ro-fixed"><span class="v2ro-nd">' + DOT + '</span><p>للمشاركة في فرصة، تواصل مع الإدارة.</p></aside>';
    if (!rows.length) return html + emptyBlock('لا توجد فرص استثمار مفتوحة الآن', 'تظهر هنا كل فرصة تفتحها الإدارة.');
    html += countLine(rows.length, R.COUNT.opp);
    html += rows.map(function (o) {
      var c = R.oppCard(o);
      var facts = [['العائد المتوقع', c.roiText, c.roiNote], ['الحد الأدنى للمشاركة', c.minText, '']];
      if (c.start) facts.push(['تبدأ', c.start, '']);
      if (c.end) facts.push(['تنتهي', c.end, '']);
      var meta = [];
      if (c.trainer) meta.push('يقدّمها: ' + c.trainer);
      meta.push('المسجّلون: ' + c.students);
      return '<article class="v2ro-opp"><header><div class="v2ro-rb"><h3>' + esc(c.title) + '</h3><p class="v2ro-meta">' + esc(meta.join(' · ')) + '</p></div>' + chip(c.chip) + '</header>'
        + (c.showBar ? '<div class="v2ro-bar" role="img" aria-label="' + esc(c.progressText) + '"><i style="width:' + c.pct + '%"></i></div>' : '')
        + '<p class="v2ro-prog">' + esc(c.progressText) + '</p>'
        + '<dl class="v2ro-facts">' + facts.map(function (f) { return '<div><dt>' + esc(f[0]) + '</dt><dd>' + esc(f[1]) + (f[2] ? '<small>' + esc(f[2]) + '</small>' : '') + '</dd></div>'; }).join('') + '</dl></article>';
    }).join('');
    return html;
  }
  function invRowHtml(r) {
    return rowHtml(r.title, r.chip, [r.meta, r.second, r.actual]);
  }
  function viewIInvest() {
    need('active', 'history');
    var tab = S.tab.i_invest;
    var k = tab === 'history' ? 'history' : 'active';
    var s = st(k);
    if (s === 'error') return failStrip(k, 'استثماراتك', false);
    if (s !== 'ready') return loadBlock();
    var rows = Array.isArray(src(k).data) ? src(k).data : [];
    if (!rows.length) {
      return k === 'active' ? emptyBlock('لا توجد استثمارات جارية باسمك.', '', '<button type="button" class="v2ro-link" data-r-act="go" data-id="i_market">تصفّح فرص الاستثمار</button>')
                            : emptyBlock('لا توجد استثمارات منتهية بعد.', '');
    }
    return countLine(rows.length, R.COUNT.invest) + rows.map(function (x) { return invRowHtml(R.investmentRow(x, k)); }).join('');
  }

  // ------------------------------------------------------------------ الحساب بانتظار التفعيل
  function viewViewer(empty) {
    var u = (ep() && ep().user) || {};
    var name = (u.name || '').trim();
    var email = (u.email || '').trim();
    var title = empty ? 'حسابك' : 'حسابك بانتظار التفعيل';
    var body = empty ? 'لا توجد شاشات متاحة لحسابك الآن. تواصل مع الإدارة.' : 'سجّلت بنجاح. تراجع الإدارة حسابك وتحدّد صفته، ثم تظهر لوحتك هنا.';
    return '<section class="v2ro-vw"><div class="v2ro-vph" style="background-image:url(' + img('people') + ')"><span class="v2ro-vlogo">' + LOGO + '</span></div>'
      + '<div class="v2ro-vb"><h1>' + esc(title) + '</h1><p>' + esc(body) + '</p>'
      + '<div class="v2ro-id">' + (name ? '<p>الحساب: <b>' + esc(name) + '</b></p>' : '') + (email ? '<p class="v2ro-mail" dir="ltr">' + esc(email) + '</p>' : '') + '</div>'
      + '<div class="v2ro-vbt"><button type="button" class="v2ro-btn1" data-r-act="recheck">تحقّق من جديد</button>'
      + '<button type="button" class="v2ro-btn2" data-r-act="logout">تسجيل الخروج</button></div></div></section>';
  }

  // ------------------------------------------------------------------ فريق المتابعة
  function chipsBar(items, active, counts) {
    return '<div class="v2ro-chips" role="group">' + items.map(function (c) {
      var n = counts && counts[c[0]] != null ? ' (' + U.ar(counts[c[0]]) + ')' : '';
      return '<button type="button" class="v2ro-fchip' + (c[0] === active ? ' on' : '') + '" data-r-act="chip" data-id="' + c[0] + '" aria-pressed="' + (c[0] === active) + '">' + esc(c[1] + n) + '</button>';
    }).join('') + '</div>';
  }
  function moreBtn(key, total, shown) {
    return total > shown ? '<button type="button" class="v2ro-btn2 v2ro-more" data-r-act="more" data-id="' + key + '">اعرض المزيد (' + U.ar(total - shown) + ')</button>' : '';
  }
  function expandRow(id, head, details) {
    var open = !!S.open[id];
    return '<article class="v2ro-row v2ro-x' + (open ? ' open' : '') + '" data-r-act="expand" data-id="' + esc(id) + '" role="button" tabindex="0" aria-expanded="' + open + '">' + head
      + '<div class="v2ro-det"' + (open ? '' : ' hidden') + '>' + details + '</div></article>';
  }
  var PEOPLE_CHIPS = [['all', 'الكل'], ['trainer', 'المدرّبون'], ['pending', 'طلبات تدريب'], ['admin', 'الإدارة'], ['investor', 'المستثمرون'], ['test', 'تجريبي']];
  function peopleList() {
    var rows = R.peopleRows(src('people').data);
    var capped = S.baseCapped && S.baseCapped.capped;
    var useLocalQ = !capped;
    var f = R.peopleFilter(rows, S.chip.users, useLocalQ ? S.q : '');
    var lim = S.lim.users || PAGE;
    if (!f.length) return emptyBlock('لا يوجد أعضاء بهذا الشرط.', '');
    var seg = G.seg();
    return f.slice(0, lim).map(function (u, i) {
      var p = R.personRow(u, seg && typeof seg === 'object' ? seg : null);
      var head = '<div class="v2ro-xh"><span class="v2ro-av">' + esc(p.initial) + '</span><div class="v2ro-rb"><h3>' + esc(p.name) + '</h3>'
        + (p.email ? '<p class="v2ro-meta v2ro-mail" dir="ltr">' + esc(p.email) + '</p>' : '')
        + '<div class="v2ro-chips-line">' + p.chips.map(chip).join('') + '</div>'
        + (p.meta ? '<p class="v2ro-meta">' + esc(p.meta) + '</p>' : '') + '</div></div>';
      var det = '<dl class="v2ro-facts">' + p.details.map(function (d) {
        var v = Array.isArray(d.v) ? (d.v.length ? d.v.map(function (t) { return chip({ t: t, tone: 'grey' }); }).join('') : '—') : esc(d.v);
        return '<div><dt>' + esc(d.k) + '</dt><dd>' + v + '</dd></div>';
      }).join('') + '</dl>';
      return expandRow('u' + (u.id || i), head, det);
    }).join('') + moreBtn('users', f.length, lim);
  }
  function peopleCount() {
    var rows = R.peopleRows(src('people').data);
    var capped = S.baseCapped && S.baseCapped.capped;
    var f = R.peopleFilter(rows, S.chip.users, capped ? '' : S.q);
    var n = capped && S.chip.users === 'all' && !S.q ? S.baseCapped.count : f.length;
    return countLine(n, R.COUNT.member) + (capped ? '<p class="v2ro-fine">' + esc(S.baseCapped.note) + '</p>' : '');
  }
  function viewUsers() {
    need('people');
    var s = st('people');
    if (s === 'error') return failStrip('people', 'الأعضاء', false);
    if (s !== 'ready' && !src('people').data) return loadBlock();
    var rows = R.peopleRows(src('people').data);
    var html = nextCard(R.staffNext('users', pack(['people'])));
    html += '<div class="v2ro-find"><input id="v2roQ" type="search" data-r-act="search" value="' + esc(S.q) + '" placeholder="ابحث بالاسم أو البريد أو الهاتف" autocomplete="off" aria-label="بحث في الأعضاء"></div>';
    html += chipsBar(PEOPLE_CHIPS, S.chip.users, R.peopleCounts(rows));
    html += '<div id="v2roCount">' + peopleCount() + '</div><div id="v2roList">' + (s === 'loading' ? loadBlock() : peopleList()) + '</div>';
    return html;
  }
  var COURSE_CHIPS = [['all', 'الكل'], ['published', 'منشورة'], ['pending', 'بانتظار الاعتماد'], ['draft', 'مسودات']];
  function viewCourses() {
    need('pcourses');
    var s = st('pcourses');
    if (s === 'error') return failStrip('pcourses', 'الدورات', false);
    if (s !== 'ready') return loadBlock();
    var rows = R.pcourseFilter(src('pcourses').data && Array.isArray(src('pcourses').data.courses) ? src('pcourses').data.courses : [], 'all');
    var html = nextCard(R.staffNext('courses', pack(['pcourses'])));
    html += chipsBar(COURSE_CHIPS, S.chip.courses, R.pcourseCounts(rows));
    var f = R.pcourseFilter(rows, S.chip.courses);
    var lim = S.lim.courses || PAGE;
    if (!f.length) return html + emptyBlock(rows.length ? 'لا توجد دورات بهذا الشرط.' : 'لا توجد دورات على المنصة بعد.', '');
    html += countLine(f.length, R.COUNT.course);
    html += f.slice(0, lim).map(function (c) { var r = R.pcourseRow(c); return rowHtml(r.title, r.chip, [r.meta]); }).join('') + moreBtn('courses', f.length, lim);
    return html;
  }
  var TOPIC_CHIPS = [['all', 'الكل'], ['published', 'منشورة'], ['open', 'على البورد'], ['merged', 'قيد العمل'], ['pending_review', 'مقترحة من الأعضاء'], ['draft', 'مسودات'],
                     ['rejected', 'مرفوضة'], ['archived', 'مؤرشفة']];
  function topicRows() { var d = src('topics').data; return Array.isArray(d) ? d : (d && Array.isArray(d.topics) ? d.topics : []); }
  function topicsList() {
    need('topics');
    var s = st('topics');
    if (s === 'error') return failStrip('topics', 'الموضوعات', false);
    if (s !== 'ready') return loadBlock();
    var rows = topicRows();
    var html = nextCard(R.staffNext('topics', pack(['topics'])));
    html += chipsBar(TOPIC_CHIPS, S.chip.topics, R.topicCounts(rows));
    var f = R.topicFilter(rows, S.chip.topics);
    var lim = S.lim.topics || PAGE;
    if (!f.length) return html + emptyBlock(rows.length ? 'لا توجد موضوعات بهذا الشرط.' : 'لا توجد موضوعات بعد.', '');
    html += countLine(f.length, R.COUNT.topic);
    html += f.slice(0, lim).map(function (t, i) {
      var r = R.topicRow(t);
      var head = '<div class="v2ro-xh"><div class="v2ro-rb"><h3>' + esc(r.title) + '</h3>' + (r.meta ? '<p class="v2ro-meta">' + esc(r.meta) + '</p>' : '') + '</div><div class="v2ro-rs">' + chip(r.chip) + '</div></div>';
      return expandRow('t' + (t.id || i), head, r.summary ? '<p class="v2ro-body">' + esc(r.summary) + '</p>' : '<p class="v2ro-meta">لا يوجد ملخّص لهذا الموضوع.</p>');
    }).join('') + moreBtn('topics', f.length, lim);
    return html;
  }
  function tutorialsList() {
    need('tutorials');
    var s = st('tutorials');
    if (s === 'error') return failStrip('tutorials', 'دليل الاستخدام', false);
    if (s !== 'ready') return loadBlock();
    var groups = R.tutorialGroups(src('tutorials').data);
    if (!groups.length) return emptyBlock('لا توجد شروحات بعد.', '');
    var n = 0;
    return groups.map(function (g) {
      return '<h2 class="v2ro-h3">' + esc(g.section) + '</h2>' + g.items.map(function (t) {
        n++;
        var head = '<div class="v2ro-xh"><div class="v2ro-rb"><h3>' + esc(t.title) + '</h3></div><div class="v2ro-rs">' + chip(t.published ? { t: 'منشور', tone: 'green' } : { t: 'مسودة', tone: 'grey' }) + '</div></div>';
        var det = (t.body ? '<p class="v2ro-body">' + esc(t.body) + '</p>' : '<p class="v2ro-meta">لا يوجد نص لهذا الشرح.</p>')
          + (/^https?:\/\//i.test(t.video) ? '<a class="v2ro-link" href="' + esc(t.video) + '" target="_blank" rel="noopener">شاهد الشرح</a>' : '');
        return expandRow('tu' + n, head, det);
      }).join('');
    }).join('');
  }

  // ------------------------------------------------------------------ الشاشات والرؤوس
  function tabsFor(key) {
    if (key === 'i_invest') {
      var a = st('active') === 'ready' && Array.isArray(src('active').data) ? ' (' + U.ar(src('active').data.length) + ')' : '';
      var h = st('history') === 'ready' && Array.isArray(src('history').data) ? ' (' + U.ar(src('history').data.length) + ')' : '';
      return [['active', 'الجارية' + a], ['history', 'المنتهية' + h]];
    }
    if (key === 'courses') return [['catalog', 'الكتالوج'], ['legacy', 'كل السجلات']];
    if (key === 'topics') {
      var t = [['topics', 'الموضوعات']];
      if (navIds().indexOf('tutorials') > -1) t.push(['tut', 'دليل الاستخدام']);
      t.push(['legacy', 'كل السجلات']);
      return t;
    }
    return [];
  }
  function screenHtml(key, tab) {
    switch (key) {
      case 't_home': return viewTHome();
      case 't_courses': return viewTCourses();
      case 't_earnings': return viewTEarnings();
      case 'i_home': return viewIHome();
      case 'i_market': return viewIMarket();
      case 'i_invest': return viewIInvest();
      case 'users': return viewUsers();
      case 'courses': return viewCourses();
      case 'topics': return tab === 'tut' ? tutorialsList() : topicsList();
      case 'tutorials': return tutorialsList();
      default: return viewViewer(false);
    }
  }

  // ------------------------------------------------------------------ الإطار: القائمة الجانبية · الترويسة · الورقة
  function appEl() { return q('.app'); }
  function userName() { var u = ep() && ep().user; return (u && (u.name || u.email)) || 'حسابك'; }
  function sideItem(it, on) {
    var ph = it.img ? '<span class="v2s-ph" style="background-image:url(' + img(it.img) + ')"></span>' : '<span class="v2s-ph v2s-ph-home">' + GRID + '</span>';
    return '<a class="v2s-item' + (on ? ' on' : '') + '" href="#' + it.id + '" data-mod="' + it.id + '"' + (on ? ' aria-current="page"' : '') + '>' + ph + '<span class="v2s-name">' + esc(it.label) + '</span></a>';
  }
  function userBlock() {
    return '<div class="v2s-me"><span class="v2s-av">' + esc(String(userName()).trim().charAt(0) || '—') + '</span><span class="v2s-who"><b>' + esc(userName()) + '</b><small>' + esc(R.ROLE_LINE[mapRole()]) + '</small></span>'
      + '<button type="button" class="v2s-out" data-r-act="logout" aria-label="تسجيل الخروج" title="تسجيل الخروج">' + OUT + '</button></div>';
  }
  function drawSide(items, key) {
    var el = q('#v2roSide'); if (!el) return;
    el.innerHTML = '<div class="v2s-brand"><span class="v2s-mark">' + LOGO + '</span><span class="v2s-bt"><b>البروفيسور</b><small>' + esc(R.ROLE_SUB[mapRole()]) + '</small></span></div>'
      + '<nav class="v2s-nav" aria-label="الشاشات">' + items.map(function (it) { return sideItem(it, it.id === key || (key === 'tutorials' && it.id === 'tutorials')); }).join('') + '</nav>' + userBlock();
  }
  function drawSheet(items, key) {
    var el = q('#v2roSheet'); if (!el) return;
    el.innerHTML = '<div class="v2s-scrim" data-r-act="close"></div><div class="v2s-box" role="dialog" aria-modal="true" aria-label="القائمة">'
      + '<div class="v2s-bh"><b>القائمة</b><button type="button" class="v2s-x" data-r-act="close" aria-label="إغلاق">' + CLOSE + '</button></div>'
      + '<div class="v2s-grid">' + items.map(function (it) {
        var on = it.id === key;
        return '<a class="v2s-tile' + (it.img ? '' : ' home') + (on ? ' on' : '') + '" href="#' + it.id + '" data-mod="' + it.id + '" style="--rgb:' + (RGB[it.img || 'home'] || RGB.home) + (it.img ? ';background-image:url(' + img(it.img) + ')' : '') + '">'
          + (it.img ? '' : GRID) + '<span class="v2s-tn">' + esc(it.label) + '</span></a>';
      }).join('') + '</div>' + userBlock() + '</div>';
  }
  function drawHead(items, key, tab) {
    var el = q('#v2roSec'); if (!el) return;
    if (!items.length) {   // موظف بلا أي شاشة مسموحة: لا ترويسة، والبطاقة وحدها
      el.innerHTML = '';
      var pt0 = q('#pageTitle'); if (pt0) pt0.textContent = 'حسابك';
      return;
    }
    var it = null;
    items.forEach(function (x) { if (x.id === key) it = x; });
    if (!it) it = { label: R.NAV[key] ? R.NAV[key].label : 'حسابك', desc: R.NAV[key] ? R.NAV[key].desc : '' };
    var tabs = tabsFor(key);
    var strip = q('.v2c-tabs', el), keepLeft = strip ? strip.scrollLeft : 0;
    el.innerHTML = '<div class="v2c-h"><h1>' + esc(it.label) + '</h1>' + (it.desc ? '<p>' + esc(it.desc) + '</p>' : '') + '</div>'
      + (tabs.length ? '<div class="v2c-tabs" role="tablist" aria-label="' + esc(it.label) + '">' + tabs.map(function (t) {
        return '<button type="button" role="tab" class="v2c-tab' + (t[0] === tab ? ' on' : '') + '" aria-selected="' + (t[0] === tab) + '" data-r-act="tab" data-id="' + t[0] + '">' + esc(t[1]) + '</button>';
      }).join('') + '</div>' : '');
    var s2 = q('.v2c-tabs', el); if (s2) s2.scrollLeft = keepLeft;
    var pt = q('#pageTitle'); if (pt) pt.textContent = V.role === 'viewer' ? 'حسابك' : it.label;
  }
  V.chrome = function () {
    if (!V.active) return;
    var key = curKey();
    var items = navItems();
    drawSide(items, key);
    var tab = S.tab[key] || '';
    drawHead(items, key, tab);
    if (sheetOpen()) S.sheetDirty = true; else { drawSheet(items, key); S.sheetDirty = false; }
  };
  function sheetOpen() { var el = q('#v2roSheet'); return !!(el && el.classList.contains('open')); }
  function openSheet() {
    var el = q('#v2roSheet'); if (!el) return;
    el.classList.add('open'); el.setAttribute('aria-hidden', 'false');
    document.documentElement.classList.add('v2-noscroll');
    var f = q('.v2s-x', el); if (f && f.focus) { try { f.focus(); } catch (e) {} }
  }
  function closeSheet() {
    var el = q('#v2roSheet'); if (!el) return;
    el.classList.remove('open'); el.setAttribute('aria-hidden', 'true');
    document.documentElement.classList.remove('v2-noscroll');
    if (S.sheetDirty) { S.sheetDirty = false; V.chrome(); }
  }

  // ------------------------------------------------------------------ «كل السجلات» (الشاشات القديمة بالشكل الجديد)
  var HIDDEN_TOPIC_TABS = ['pending', 'ideas', 'working', 'board', 'incoming', 'rejected', 'tutorials'];
  function prepLegacy(key) {
    var setters = G.setters();
    if (!setters) return;
    if (key === 'courses' && G.courseTab() === 'platform' && setters.courseTab) setters.courseTab('courses');
    if (key === 'topics' && HIDDEN_TOPIC_TABS.indexOf(G.topicsTab()) > -1 && setters.topicsTab) setters.topicsTab('news');
  }
  function setLegacy(on) {
    var a = appEl(); if (a) a.classList.toggle('v2ro-legacy', !!on);
    var n = q('#v2roLegacyNote'); if (n) n.hidden = !on;
    V.legacy = !!on;
    if (on) startLegacyWatch(); else stopLegacyWatch();
  }

  // نصوص «كل السجلات» القادمة من الشاشات القديمة: كلمات تقنية وأرقام لاتينية وخانة إيراد فاضية. الشاشات القديمة لا تُمَسّ (أقسام أخرى)،
  // فنصحّح المعروض هنا فقط، ويُعاد التصحيح مع كل إعادة رسم (الشاشة القديمة تعيد كتابة نفسها من ردود التحميل).
  var DIG_AR = '٠١٢٣٤٥٦٧٨٩';
  function legacyText(t) {
    var o = t;
    t = t.replace(/\s*[·\-]?\s*\b[A-Z]{2,5}-[A-Za-z0-9-]+/g, '').replace(/\s*app\.elprofessor\.net/gi, ' المنصة').replace(/\belprofessor\.net\b/gi, 'الموقع').replace(/\s*\bnative\b\s*/gi, ' ').replace(/\bUSD\b/g, 'دولار').replace(/\bEGP\b/g, 'جنيه');
    t = t.replace(/من (\d+) دورة(?![\u0600-\u06FF])/g, function (m, n) { return 'من ' + U.U(+n, R.COUNT.course); });
    t = t.replace(/\d/g, function (d) { return DIG_AR.charAt(+d); });
    t = t.replace(/([٠-٩]) ج(?![\u0600-\u06FF])/g, '$1 جنيه');
    t = t.replace(/^(\s*من\s+)?[·—]\s*$/, function (m, a) { return (a || '') + R.NA; });
    t = t.replace(/ {2,}/g, ' ');
    return t === o ? o : t;
  }
  function cleanLegacy(root) {
    if (!root) return;
    qa('.from, .sub', root).forEach(function (el) {
      // الشاشة القديمة تحسب الإيراد = المسجّلين × سعر غير موجود ⇒ صفر مختلَق. لا نعرض رقمًا لا مصدر له.
      if (/^\s*إيراد\s*[·—–\-٠0]\s*(ج|جنيه)\s*$/.test(el.textContent)) el.textContent = 'الإيراد: ' + R.NA;
    });
    var w = document.createTreeWalker(root, NodeFilter.SHOW_TEXT, null), list = [];
    while (w.nextNode()) list.push(w.currentNode);
    list.forEach(function (n) {
      var p = n.parentNode;
      if (!p || /^(SCRIPT|STYLE|TEXTAREA|INPUT|OPTION)$/.test(p.nodeName)) return;
      if (p.closest && p.closest('[dir="ltr"], .v2ro-mail, code')) return;
      var v = n.nodeValue, c = legacyText(v);
      if (c !== v) n.nodeValue = c;
    });
  }
  var LEG = { obs: null, busy: false };
  function legacyPass() {
    var view = q('#view');
    if (!view || !V.active || !V.legacy || LEG.busy) return;
    LEG.busy = true;
    try { cleanLegacy(view); } catch (e) {}
    if (LEG.obs) LEG.obs.takeRecords();
    LEG.busy = false;
  }
  function startLegacyWatch() {
    var view = q('#view');
    if (!view) return;
    if (!LEG.obs && typeof MutationObserver === 'function') {
      LEG.obs = new MutationObserver(function () { legacyPass(); });
      LEG.obs.observe(view, { childList: true, subtree: true, characterData: true });
    }
    legacyPass();
  }
  function stopLegacyWatch() {
    if (LEG.obs) { LEG.obs.disconnect(); LEG.obs = null; }
  }

  // ------------------------------------------------------------------ الرسم
  V.skeleton = function () {
    var v = q('#view'); if (v) v.innerHTML = '<div class="v2ro"><div class="v2ro-load">…جارٍ التحميل</div></div>';
  };
  V.render = function () {
    if (!V.active) return;
    var view = q('#view'); if (!view) return;
    var key = curKey();
    if (S.lastKey !== key) { S.q = ''; S.open = {}; S.lim = {}; S.lastKey = key; S.baseCapped = S.baseCapped; }
    var ids = navIds();
    V.navSig = ids.join(',');
    var tab = S.tab[key] || '';
    if (key === 'topics' && tab === 'tut' && ids.indexOf('tutorials') < 0) { tab = S.tab.topics = 'topics'; }
    var legacy = tab === 'legacy' && (key === 'courses' || key === 'topics');
    setLegacy(legacy);
    V.chrome();
    var keep = focusSnapshot(view);
    if (legacy) {
      prepLegacy(key);
      if (typeof V.hooks.renderView === 'function') V.hooks.renderView();
      return;
    }
    if (!ids.length && V.role === 'employee') { view.innerHTML = '<div class="v2ro v2ro-solo">' + viewViewer(true) + '</div>'; return; }
    view.innerHTML = '<div class="v2ro">' + screenHtml(key, tab) + '</div>';
    restoreFocus(view, keep);
  };
  function focusSnapshot(view) {
    var a = document.activeElement;
    if (a && a.id === 'v2roQ' && view.contains(a)) return { id: 'v2roQ', s: a.selectionStart, e: a.selectionEnd };
    return null;
  }
  function restoreFocus(view, k) {
    if (!k) return;
    var n = q('#' + k.id, view);
    if (n) { try { n.focus({ preventScroll: true }); n.setSelectionRange(k.s, k.e); } catch (e) {} }
  }

  // ------------------------------------------------------------------ الأحداث (تفويض واحد على #view والإطار)
  function act(el, e) {
    var a = el.getAttribute('data-r-act'), id = el.getAttribute('data-id'), k = el.getAttribute('data-k');
    switch (a) {
      case 'retry': if (k === 'people') { S.q = ''; reloadPeople(''); } else reload(k); break;
      case 'go': e.preventDefault(); closeSheet(); nav(id); break;
      case 'wd': openWithdraw(); break;
      case 'logout': { var b = q('#logoutBtn'); if (b) b.click(); break; }
      case 'recheck': location.reload(); break;
      case 'tab': S.tab[curKey()] = id; S.lim = {}; V.render(); break;
      case 'chip': S.chip[chipScope()] = id; S.lim = {}; V.render(); break;
      case 'more': S.lim[id] = (S.lim[id] || PAGE) + PAGE; V.render(); break;
      case 'close': closeSheet(); break;
      case 'expand': {
        if (e.target.closest && (e.target.closest('a,button') || e.target.closest('.v2ro-det'))) return;
        S.open[id] = !S.open[id];
        el.classList.toggle('open', !!S.open[id]);
        el.setAttribute('aria-expanded', String(!!S.open[id]));
        var d = q('.v2ro-det', el); if (d) d.hidden = !S.open[id];
        break;
      }
    }
  }
  function chipScope() { var k = curKey(); return k === 'users' ? 'users' : (k === 'courses' ? 'courses' : 'topics'); }
  function onSearch(inp) {
    S.q = inp.value;
    var capped = S.baseCapped && S.baseCapped.capped;
    if (!capped) { var c = q('#v2roCount'), l = q('#v2roList'); if (c) c.innerHTML = peopleCount(); if (l) l.innerHTML = peopleList(); return; }
    clearTimeout(S.searchT);
    var qv = S.q.trim();
    S.searchT = setTimeout(function () {
      if (qv.length >= 2) reloadPeople(qv); else if (qv.length === 0) reloadPeople('');
    }, 400);
  }
  function reloadPeople(qv) {
    var s = src('people');
    s.state = 'idle';
    load('people', true, qv ? PATH.people + '?search=' + encodeURIComponent(qv) : undefined);
    changed();
  }
  function wireOnce() {
    var view = q('#view');
    if (view && !view._v2ro) {
      view._v2ro = true;
      view.addEventListener('click', function (e) {
        var el = e.target.closest ? e.target.closest('[data-r-act]') : null;
        if (!el || !V.active || V.legacy) return;
        if (el.getAttribute('data-r-act') === 'search') return;
        act(el, e);
      });
      view.addEventListener('input', function (e) {
        var t = e.target;
        if (t && t.getAttribute && t.getAttribute('data-r-act') === 'search' && V.active) onSearch(t);
      });
      view.addEventListener('keydown', function (e) {
        if ((e.key === 'Enter' || e.key === ' ') && e.target && e.target.getAttribute && e.target.getAttribute('data-r-act') === 'expand') { e.preventDefault(); act(e.target, e); }
      });
    }
    ['#v2roSide', '#v2roSheet', '#v2roSec'].forEach(function (id) {
      var el = q(id); if (!el || el._v2ro) return;
      el._v2ro = true;
      el.addEventListener('click', function (ev) {
        var a = ev.target.closest ? ev.target.closest('[data-mod],[data-r-act]') : null;
        if (!a) return;
        if (a.hasAttribute('data-mod') && !a.hasAttribute('data-r-act')) {
          if (ev.metaKey || ev.ctrlKey || ev.shiftKey || ev.button === 1) return;
          ev.preventDefault(); closeSheet(); nav(a.getAttribute('data-mod')); return;
        }
        act(a, ev);
      });
    });
  }

  // ------------------------------------------------------------------ طلب السحب (ورقة المراجعة ثم التأكيد)
  function openWithdraw() {
    var W = st('wallet') === 'ready' ? R.walletView(src('wallet').data) : null;
    if (!W || !W.linked || !W.canWithdraw || typeof window.openModal !== 'function') return;
    var s = window.openModal('طلب سحب من محفظتك', '<div class="v2rom" id="v2roWd"></div>');
    var box = q('#v2roWd', s);
    var closeIt = function () { if (!s.dataset.busy) window.closeModal(); };
    var x = q('[data-x]', s); if (x) x.onclick = closeIt;
    s.onclick = function (e) { if (e.target === s) closeIt(); };
    var amount = Math.floor(W.balanceEgp);
    stage1(box, s, W, String(amount), closeIt);
  }
  function stage1(box, s, W, val, closeIt, err) {
    var rate = W.rate;
    box.innerHTML = '<p class="mc-lead">يصل طلبك إلى الإدارة لمراجعته وتحويله. يُخصم المبلغ من رصيدك المتاح فور إرسال الطلب.</p>'
      + '<div class="fld"><label for="v2roAmt">المبلغ بالجنيه</label><input id="v2roAmt" inputmode="numeric" dir="ltr" autocomplete="off" value="' + esc(val) + '">'
      + '<p class="v2ro-fine">الرصيد المتاح: ' + esc(U.fmt(W.balanceEgp)) + ' جنيه</p>'
      + (rate ? '<p class="v2ro-fine">الحد الأدنى للسحب ٥٠ دولارًا (نحو ' + esc(U.fmt(W.minEgp)) + ' جنيه)</p>' : '') + '</div>'
      + '<div id="v2roWdErr">' + (err ? '<div class="v2ro-err">' + esc(err) + '</div>' : '') + '</div>'
      + '<div class="v2rom-acts"><button type="button" class="v2ro-btn1" id="v2roRev">راجع الطلب</button><button type="button" class="v2ro-btn2" id="v2roCan">رجوع</button></div>';
    var inp = q('#v2roAmt', box);
    q('#v2roCan', box).onclick = closeIt;
    q('#v2roRev', box).onclick = function () {
      var chk = R.withdrawCheck(inp.value, W);
      if (!chk.ok) { q('#v2roWdErr', box).innerHTML = '<div class="v2ro-err">' + esc(chk.error) + '</div>'; return; }
      stage2(box, s, W, chk.amount, closeIt);
    };
    setTimeout(function () { try { inp.focus(); inp.select(); } catch (e) {} }, 30);
  }
  function stage2(box, s, W, amount, closeIt) {
    var rows = [['المبلغ', U.fmt(amount) + ' جنيه']];
    if (W.rate) rows.push(['بالدولار', 'نحو ' + U.fmt(Math.round(amount / W.rate * 100) / 100) + ' دولار']);
    rows.push(['العملة', 'جنيه مصري'], ['الاسم', userName()], ['من', 'محفظة الاستثمار']);
    box.innerHTML = '<p class="mc-lead">راجع الطلب قبل التأكيد</p>'
      + '<table class="mc-tab">' + rows.map(function (r) { return '<tr><td>' + esc(r[0]) + '</td><td>' + (r[0] === 'المبلغ' ? '<b>' + esc(r[1]) + '</b>' : esc(r[1])) + '</td></tr>'; }).join('') + '</table>'
      + '<div id="v2roWdErr"></div>'
      + '<div class="v2rom-acts"><button type="button" class="v2ro-btn1" id="v2roGo">أكّد طلب السحب</button><button type="button" class="v2ro-btn2" id="v2roBack">رجوع للتعديل</button></div>';
    var go = q('#v2roGo', box), back = q('#v2roBack', box), errEl = q('#v2roWdErr', box);
    back.onclick = function () { if (!s.dataset.busy) stage1(box, s, W, String(amount), closeIt); };
    go.onclick = function () {
      if (go.dataset.busy) return;
      go.dataset.busy = '1'; s.dataset.busy = '1'; go.disabled = true; back.disabled = true; go.textContent = 'جارٍ الإرسال…'; errEl.innerHTML = '';
      var E = ep();
      E.api('/v2/roles/withdraw', { method: 'POST', body: { amount: amount, currency: 'EGP', confirmed: true } }).then(function () {
        delete s.dataset.busy;
        window.closeModal();
        if (typeof window.toast === 'function') window.toast('أُرسل طلب السحب');
        reload('wallet');
      }).catch(function (e) {
        var status = e && e.status, msg = e && e.data && typeof e.data.error === 'string' ? e.data.error : '';
        if (status === 401) return;
        delete s.dataset.busy;
        if (status && status < 500 && msg) {
          delete go.dataset.busy; go.disabled = false; back.disabled = false; go.textContent = 'أكّد طلب السحب';
          errEl.innerHTML = '<div class="v2ro-err">' + esc(R.arDigits(msg)) + '</div>';
          return;
        }
        if (status && status >= 500 && msg) {
          delete go.dataset.busy; go.disabled = false; back.disabled = false; go.textContent = 'أكّد طلب السحب';
          errEl.innerHTML = '<div class="v2ro-err">' + esc(R.arDigits(msg)) + '</div>';
          return;
        }
        back.disabled = false;
        go.textContent = 'حدّث الصفحة أولًا';
        errEl.innerHTML = '<div class="v2ro-err">لم يصل رد. حدّث الصفحة وتأكّد من رصيدك قبل أي محاولة جديدة.</div>';
        reload('wallet');
      });
    };
  }

  // ------------------------------------------------------------------ التفعيل
  V.activate = function () {
    var app = appEl(); if (!app || V.active) return;
    app.classList.add('v2-shell', 'v2-roles', 'v2-bare');
    syncRoleClass();
    var rail = q('.rail'), view = q('#view');
    var rb = q('#roBanner'); if (rb) { rb.style.display = 'none'; rb.innerHTML = ''; }   // setRole كتب display:flex بأسلوب مضمّن قبل رد المفتاح
    var side = document.createElement('aside'); side.id = 'v2roSide'; side.className = 'v2-side';
    if (rail && rail.parentNode) rail.parentNode.insertBefore(side, rail.nextSibling); else app.insertBefore(side, app.firstChild);
    if (view && view.parentNode) {
      var sec = document.createElement('div'); sec.id = 'v2roSec'; sec.className = 'v2-sec'; view.parentNode.insertBefore(sec, view);
      var note = document.createElement('p'); note.id = 'v2roLegacyNote'; note.className = 'v2ro-lnote'; note.hidden = true;
      note.textContent = 'كل السجلات كما كانت، للاطلاع فقط.';
      view.parentNode.insertBefore(note, view);
    }
    var sheet = document.createElement('div'); sheet.id = 'v2roSheet'; sheet.className = 'v2-sheet'; sheet.setAttribute('aria-hidden', 'true');
    document.body.appendChild(sheet);
    var tb = q('.topbar'), ttl = tb && q('.ttl', tb);
    if (tb && ttl && !q('.v2-tb-logo', tb)) { var lg = document.createElement('span'); lg.className = 'v2-tb-logo'; lg.innerHTML = LOGO; tb.insertBefore(lg, ttl); }
    var mb = q('#menuBtn');
    if (mb) mb.onclick = function () { if (sheetOpen()) closeSheet(); else openSheet(); };
    if (!V.docWired) {
      V.docWired = true;
      document.addEventListener('keydown', trapKeys);
      window.addEventListener('resize', function () { if (window.innerWidth >= 1180) closeSheet(); });
    }
    V.active = true;
    wireOnce();
    if (typeof window.renderView === 'function') window.renderView();
  };
  function trapKeys(e) {
      if (!V.active || !sheetOpen()) return;
      if (e.key === 'Escape') { closeSheet(); return; }
      if (e.key !== 'Tab') return;
      var box = q('#v2roSheet .v2s-box'); if (!box) return;
      var f = qa('a[href],button:not([disabled])', box).filter(function (n) { return n.offsetParent !== null; });
      if (!f.length) return;
      var first = f[0], last = f[f.length - 1], cur = document.activeElement;
      if (!box.contains(cur)) { e.preventDefault(); first.focus(); }
      else if (e.shiftKey && cur === first) { e.preventDefault(); last.focus(); }
      else if (!e.shiftKey && cur === last) { e.preventDefault(); first.focus(); }
  }

  // صنف الدور على الإطار (يتبدّل مع الحساب بلا إعادة تحميل)
  function syncRoleClass() {
    var app = appEl(); if (!app) return;
    ['v2ro-trainer', 'v2ro-investor', 'v2ro-staff', 'v2ro-viewer'].forEach(function (c) { app.classList.remove(c); });
    var key = ROLEKEY[V.role] || 'viewer';
    app.classList.add('v2ro-' + (key === 'employee' ? 'staff' : key));
  }
  // يفكّ الشكل الجديد كله (دخل أدمن في نفس الصفحة، أو رجع المفتاح مقفولًا): لا يبقى من الإطار شيء.
  function deactivate() {
    if (!V.active) return;
    V.active = false; V.legacy = false;
    clearTimeout(S.searchT); clearTimeout(redrawT); redrawT = null;
    stopLegacyWatch();
    closeSheet();
    var app = appEl();
    if (app) ['v2-shell', 'v2-roles', 'v2-bare', 'v2ro-trainer', 'v2ro-investor', 'v2ro-staff', 'v2ro-viewer', 'v2ro-legacy', 'v2-pre'].forEach(function (c) { app.classList.remove(c); });
    ['v2roSide', 'v2roSec', 'v2roSheet', 'v2roLegacyNote'].forEach(function (id) { var n = document.getElementById(id); if (n && n.parentNode) n.parentNode.removeChild(n); });
    var lg = q('.v2-tb-logo'); if (lg && lg.parentNode) lg.parentNode.removeChild(lg);
    var rb = q('#roBanner'); if (rb) rb.style.display = '';
  }
  // حساب جديد في نفس الصفحة (٤٠١ ثم دخول آخر): لا يبقى رقم من الحساب السابق ولا حالة شاشة.
  function resetForAccount() {
    GEN++;
    clearTimeout(S.searchT); clearTimeout(redrawT); redrawT = null;
    SRC = {};
    S = freshState();
  }

  V.loadFlag = function () {
    var E = ep(), done = false;
    V.flag = 'pending';
    function fin(on, decisive) {
      if (done) return; done = true;
      if (decisive) { try { if (on) localStorage.setItem(MEMO, '1'); else localStorage.removeItem(MEMO); } catch (e) {} }
      V.flag = on ? 'on' : 'off';
      var a = appEl(); if (a) a.classList.remove('v2-pre');
      if (on) V.activate();
      else { if (V.active) deactivate(); if (typeof window.renderView === 'function') window.renderView(); }
    }
    try {
      E.api('/v2/roles/config').then(function (r) { fin(!!(r && r.enabled === true), true); }).catch(function () { fin(false, false); });
    } catch (e) { fin(false, false); }
    setTimeout(function () { fin(false, false); }, 3000);
  };

  // ------------------------------------------------------------------ التركيب (لا شيء يتغيّر قبل رد المفتاح)
  function memoOn() { try { return localStorage.getItem(MEMO) === '1'; } catch (e) { return false; } }
  function install() {
    if (V.installed) return;
    if (!(typeof window.renderView === 'function' && typeof window.setRole === 'function' && typeof window.go === 'function' && typeof window.roleNavFor === 'function')) return;
    V.installed = true;
    var origRenderView = window.renderView, origSetRole = window.setRole, origRenderNav = window.renderNav;
    V.hooks.renderView = origRenderView;
    var lastWho = null;
    window.setRole = function (r) {
      var u = ep() && ep().user;
      var who = String(r) + '|' + ((u && (u.id || u.email)) || '');
      if (lastWho !== null && lastWho !== who) {
        resetForAccount();
        if (V.active && r === 'admin') deactivate();
      }
      lastWho = who;
      if (r === 'admin') { V.role = ''; return origSetRole.apply(this, arguments); }
      V.role = r;
      if (V.active) { syncRoleClass(); closeSheet(); }
      V.flag = 'pending';
      var a = appEl();
      if (memoOn() && a) a.classList.add('v2-pre');
      var out = origSetRole.apply(this, arguments);
      if (V.active) { var rb = q('#roBanner'); if (rb) { rb.style.display = 'none'; rb.innerHTML = ''; } }   // setRole يكتب الشريط القديم من جديد مع كل حساب
      V.loadFlag();
      return out;
    };
    var origGo = window.go;
    window.go = function (mod) {
      // غير الأدمن لا يفتح شاشة خارج قائمته (مثل رابط إشعار إلى «الرسائل»): نتجاهل بدل أن نعرض شاشة غير شاشته.
      if (V.active && V.role && V.role !== 'admin' && navIds().indexOf(mod) < 0) return;
      return origGo.apply(this, arguments);
    };
    window.renderView = function () {
      if (V.role && V.role !== 'admin') {
        if (V.active) return V.render();
        if (V.flag === 'pending' && memoOn()) return V.skeleton();
      }
      return origRenderView.apply(this, arguments);
    };
    if (typeof origRenderNav === 'function') {
      window.renderNav = function () {
        var out = origRenderNav.apply(this, arguments);
        if (V.active && V.role && V.role !== 'admin') {
          // وصلت خريطة الصلاحيات المحفوظة: لو تغيّرت قائمة الشاشات نعيد رسم الشاشة نفسها لا الإطار فقط.
          if (V.navSig !== navIds().join(',')) V.render(); else V.chrome();
        }
        return out;
      };
    }
    // الشاشات القديمة تستدعي نفسها من ردود التحميل مباشرةً (EP.ensure) فتمسح الشاشة الجديدة؛ نردّها إلى الرسم الجديد إلا داخل «كل السجلات».
    ['viewTHome', 'viewTCourses', 'viewTEarnings', 'viewIHome', 'viewIMarket', 'viewIInvest', 'viewViewer', 'viewUsers', 'viewCourses', 'viewTopics', 'viewTutorials',
     'viewNews', 'viewContent', 'viewComments', 'viewArticlesAuto'].forEach(function (name) {
      var o = window[name];
      if (typeof o !== 'function') return;
      window[name] = function () {
        if (V.active && V.role && V.role !== 'admin' && !(V.legacy && /^view(Courses|Topics|News|Content|Comments|ArticlesAuto|Tutorials)$/.test(name))) { V.render(); return; }
        return o.apply(this, arguments);
      };
    });
  }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', install); else install();
})();
