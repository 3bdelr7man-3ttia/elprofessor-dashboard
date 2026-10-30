/* ============================================================================
 * v2s/market.js — «سوق الخدمات» على الهيكل الجديد (الجولة النهائية): لوحة تذاكر بعدّاد (طلب جديد · ينتظر خبيرًا · وصله عرض · انتهى هذا الأسبوع)
 * وسطر العقل وزرّ واحد، ودرج «تفاصيل الطلب»، وتبويبا «كل الطلبات» و«ماذا يطلب الناس».
 * ⛔ لا منطق عمل هنا: التصنيف والعدّادات وسطور العقل وأخطاء الربط وأرقام الطلب كلها من `V2L.v2sMarket` (نقي، في v2-logic.js).
 * ⛔ لا طلب شبكة من هنا غير: محمّلات الداشبورد الموجودة (`market` · `marketDemand` · `trainingInterests` · `courses`) · تفاصيل الطلب
 *   (`EP.marketRequestDetail`) · إغلاق/إخفاء الطلب (المساران الموجودان) · `GET|POST /api/v2/market/*` (بروكسيات أدمن، الكتابة بـ`confirmed:true`).
 * ⛔ لا قرار فلوس في هذا القسم. وما يُكتب فيه يمرّ على ورقة تأكيد.
 * ⛔ المفتاح مقفول افتراضيًا: الملف بيتحمّل دايمًا لكنه ما بيرسم شيئًا إلا لو index.html نادى `render` (والغلاف الجديد شغّال).
 * ========================================================================== */
(function () {
  'use strict';
  var L = window.V2L;
  if (!L || !L.v2sMarket) return;
  var X = L.v2sMarket, U = L.util, ar = U.ar;
  var M = window.V2S_MARKET = {};
  var MODS = { market: 1, v2s_market_all: 1, v2s_market_demand: 1 };
  var SOURCES = ['market', 'marketDemand', 'trainingInterests'];
  var S = {
    view: null, mod: '', sig: '', poll: null, minute: null, nowOverride: 0,
    lane: 'all', showTest: false, expanded: { 'new': false, waiting: false, offered: false, done: false }, seg: null,
    drawerId: '', opener: null, ov: '', busy: {}, err: {}, done: {}, detail: {}, bodyOpen: {}, rows: [], T: null,
    all: { state: 'idle', items: [], total: null, counts: null, lane: 'all', status: 'all', need: 'all', author: 'all', q: '', seq: 0, more: false, httpStatus: 0 },
    qTimer: null, courseGuard: false, doneTimers: {}
  };

  function esc(s) { return String(s == null ? '' : s).replace(/[&<>"']/g, function (c) { return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]; }); }
  function host() { return window.V2_HOST || {}; }
  function ep() { return window.EP || null; }
  function stateOf(k) { var E = ep(); return (E && E.state && E.state[k]) || 'idle'; }
  function img(n) { return 'v2/img/' + n + '.jpg'; }
  function nowMs() { return S.nowOverride || Date.now(); }
  var BRAIN = '<img class="v2d-bav" src="' + img('brain-avatar') + '" alt="">';
  function roleName() { try { if (typeof role !== 'undefined') return role; } catch (e) {} var E = ep(); return (E && E.role) || ''; }
  M.canWrite = function () { return roleName() === 'admin'; };
  M.owns = function (mod) { return !!(MODS[mod] && window.V2_ON && window.V2SHELL && window.V2SHELL.on); };
  function isCurrent() { return !!(S.view && document.body.contains(S.view) && host().current && M.owns(host().current())); }
  function curMod() { return host().current ? host().current() : S.mod; }
  function toast(t) { try { (window.toast || window.notify || function () {})(t); } catch (e) {} }
  function U1(n, f) { return U.U(n, f); }
  var TOTAL_FORMS = ['طلب واحد', 'طلبان', 'طلبات', 'طلبًا'];

  // ------------------------------------------------------------------ بيانات اللوحة
  function boardData() {
    var E = ep(), st = stateOf('market'), D = E && E.data && E.data.market;
    var missing = !!(D && D.missing);
    var rows = D && !missing && Array.isArray(D.rows) ? X.merge(D.rows, D.raw) : null;
    return { state: st, missing: missing, rows: rows, counts: (D && D.counts) || null, count: D && D.count != null ? D.count : (rows ? rows.length : null) };
  }
  function isLoading(g) { return (g.state === 'idle' || g.state === 'loading') && !g.rows; }
  function rowById(id) {
    var i, r;
    for (i = 0; i < S.rows.length; i++) if (String(S.rows[i].id) === String(id)) return S.rows[i];
    for (i = 0; i < S.all.items.length; i++) { r = S.all.items[i]; if (String(r.id) === String(id)) return X.norm(r); }
    return null;
  }

  // ------------------------------------------------------------------ أجزاء مشتركة
  function personLink(name, email) {
    if (!email) return esc(name);
    return window.V2D2 && V2D2.link ? V2D2.link(name, email) : esc(name);
  }
  function emptyCard(title, text) {
    return '<div class="v2s-mk-empty"><span class="v2s-mk-eimg" style="background-image:url(' + img('market') + ')" role="img" aria-label="سوق الخدمات"></span><b>' + esc(title) + '</b><p>' + esc(text) + '</p></div>';
  }
  function missingCard() { return emptyCard('سوق الخدمات غير متاح بعد على المنصة', 'ستظهر الطلبات هنا تلقائيًا حين يصبح متاحًا'); }
  function warn(text, btn) { return '<div class="v2d-warn" role="status">' + esc(text) + (btn || '') + '</div>'; }
  function retryBtn(a) { return '<button type="button" class="v2d-btn2" data-a="' + a + '">أعد المحاولة</button>'; }
  function fine(t) { return '<p class="v2s-mk-fine">' + esc(t) + '</p>'; }
  function statusChip(r) {
    var k = r.status === 'matched' ? 'matched' : r.status === 'closed' ? 'closed' : ((r.status === undefined || r.status === '' || r.status === 'open') ? 'open' : 'unknown');
    var t = { open: 'مفتوح', matched: 'تمّت المطابقة', closed: 'أُغلق', unknown: 'حالة غير معروفة' }[k];
    return '<span class="v2s-mk-st st-' + k + '">' + t + '</span>';
  }
  function readOnlyLine() { return M.canWrite() ? '' : '<p class="v2s-mk-ro" role="status">عرض فقط: القرارات في هذا القسم للإدارة</p>'; }

  // ------------------------------------------------------------------ التذكرة
  // اسم الكتالوج في سطر ثانٍ صغير تحت نوع الطلب، فلا يتكدّس الشريط مع العدّاد.
  function typeHtml(t) {
    var cat = t.row && t.row.catalog_name ? String(t.row.catalog_name) : '', lbl = String(t.typeLabel || '');
    if (cat && lbl.slice(-cat.length - 3) === ' · ' + cat) return esc(lbl.slice(0, -cat.length - 3)) + '<small class="v2s-mk-cat">' + esc(cat) + '</small>';
    return esc(lbl);
  }
  function ticketHtml(t) {
    var id = t.id, busy = !!S.busy[id], err = S.err[id] || '', done = S.done[id] || '';
    var who = '<p class="v2d-who"><span>' + personLink(t.who.name, t.who.email) + '</span>'
      + (t.specialty ? '<span class="v2s-mk-tag">' + esc(t.specialty) + '</span>' : '')
      + t.badges.map(function (b) { return '<span class="v2s-mk-tag b-' + b.k + '">' + esc(b.label) + '</span>'; }).join('') + '</p>';
    var prog = '';
    if (t.progress) {
      prog = '<div class="v2s-mk-prog">' + (t.progress.goal ? '<div class="v2s-mk-pbar" role="img" aria-label="' + esc('انضم ' + ar(t.progress.joined) + ' من ' + ar(t.progress.goal)) + '"><i style="width:' + t.progress.pct + '%"></i></div>' : '')
        + '<p>' + esc(t.progress.goal ? 'انضم ' + ar(t.progress.joined) + ' من ' + ar(t.progress.goal) : 'انضم ' + ar(t.progress.joined)) + '</p></div>';
    }
    var line = '<div class="v2d-brain">' + BRAIN + '<p>' + esc(t.brain.line) + '</p></div>';
    var btn = '';
    var p = t.brain.primary;
    if (p) btn = '<button type="button" class="v2d-btn1" data-a="primary" data-id="' + esc(id) + '"' + (busy ? ' disabled' : '') + '>' + esc(busy ? 'جارٍ التنفيذ…' : p.label) + '</button>';
    var timer = t.text ? '<time class="v2d-time"' + (t.timer ? ' data-ts="' + t.timer.ts + '" data-pre="' + esc(t.timer.pre) + '"' : '') + '>' + esc(t.text) + '</time>' : '';
    return '<article class="v2d-t tone-' + esc(t.tone) + '" data-id="' + esc(id) + '"><div class="v2d-strip"><span class="v2d-type">' + typeHtml(t) + '</span>' + timer + '</div>'
      + '<div class="v2d-body"><h3><button type="button" class="v2d-open" data-a="open" data-id="' + esc(id) + '">' + esc(t.title) + '</button></h3>' + who + prog + line
      + (done ? '<p class="v2d-ok" role="status">' + esc(done) + '</p>' : '')
      + (err ? '<div class="v2d-err" role="alert">' + esc(err) + '</div>' : '')
      + (btn ? '<div class="v2d-acts">' + btn + '</div>' : '') + '</div></article>';
  }

  // ------------------------------------------------------------------ لوحة التذاكر
  var COL_TONE = { 'new': 'new', waiting: 'wait', offered: 'ok', done: 'done' };
  function laneChips(H, extra) {
    var defs = [['all', 'كل الطلبات'], ['request', 'طلبات الخبرة'], ['course_request', 'طلبات الدورات'], ['public_service', 'خدمات للجمهور']];
    return defs.map(function (d) {
      return '<button type="button" class="v2s-mk-chip' + (S.lane === d[0] ? ' on' : '') + '" role="tab" aria-selected="' + (S.lane === d[0]) + '" data-a="lane" data-lane="' + d[0] + '">' + esc(d[1]) + ' (' + ar(H.lanes[d[0]]) + ')</button>';
    }).join('');
  }
  function laneLabel(k) { return { all: 'الكل', request: 'طلبات الخبرة', course_request: 'طلبات الدورات', public_service: 'خدمات للجمهور' }[k] || 'الكل'; }
  function drawBoard(v) {
    var g = boardData(), now = nowMs();
    S.rows = g.rows || [];
    var top;
    if (g.state === 'error' && !g.missing) {
      v.innerHTML = '<div class="v2d v2s-mk" data-board="market">' + warn('تعذّر جلب طلبات السوق من المنصة، وليس معناه أنه لا شيء ينتظرك', retryBtn('reload')) + '</div>';
      wire(v); return;
    }
    if (g.missing) { v.innerHTML = '<div class="v2d v2s-mk" data-board="market">' + missingCard() + '</div>'; wire(v); return; }
    if (isLoading(g)) {
      var sk = X.COLS.map(function (c) { return '<section class="v2d-col tone-' + COL_TONE[c] + '" data-col="' + c + '"><header class="v2d-ch"><b>' + esc(X.COL_LABEL[c]) + '</b></header><div class="v2d-list"><i class="v2s-mk-sk"></i><i class="v2s-mk-sk"></i></div></section>'; }).join('');
      v.innerHTML = '<div class="v2d v2s-mk" data-board="market"><div class="v2d-top"><p class="v2d-auto">' + BRAIN + '<span>جارٍ تحميل طلبات السوق…</span></p></div><div class="v2d-cols cols4 v2s-mk-skcols" data-active="new">' + sk + '</div></div>';
      wire(v); return;
    }
    if (!g.rows.length) { v.innerHTML = '<div class="v2d v2s-mk" data-board="market">' + emptyCard('لا طلبات في السوق بعد', 'أول طلب يصل من محادثة بروف أو من صفحة السوق على المنصة') + '</div>'; wire(v); return; }
    var ro = !M.canWrite();
    var T = X.tickets(g.rows, { now: now, lane: S.lane, showTest: S.showTest, expanded: S.expanded, readOnly: ro });
    S.T = T;
    var H = X.header(g.rows, g.counts, g.count, now);
    var active = S.seg && X.COLS.indexOf(S.seg) > -1 ? S.seg : (X.COLS.filter(function (c) { return T.counts[c]; })[0] || 'new');
    var brainSpan = '<span' + (H.brainTs ? ' data-ts="' + H.brainTs + '" data-pre="' + esc(H.brainPre) + '"' : '') + '>' + esc(H.brainText) + '</span>';
    top = '<div class="v2d-top"><p class="v2d-auto">' + BRAIN + brainSpan + '</p><p class="v2d-open-total">' + esc(H.totals) + '</p></div>';
    var supply = H.lanes.training_offer > 0 ? '<button type="button" class="v2s-mk-link" data-a="supply">عروض المدرّبين (' + ar(H.lanes.training_offer) + ')</button>' : '';
    var testBtn = T.testCount > 0 ? '<button type="button" class="v2s-mk-chip tog' + (S.showTest ? ' on' : '') + '" data-a="test" aria-pressed="' + S.showTest + '">' + (S.showTest ? 'أخفِ التجريبي' : 'أظهر التجريبي (' + ar(T.testCount) + ')') + '</button>' : '';
    var desk = '<div class="v2s-mk-ctl v2s-mk-desk"><div class="v2s-mk-chips" role="tablist" aria-label="نوع الطلب">' + laneChips(H) + '</div>' + supply + testBtn + '</div>';
    var mob = '<div class="v2s-mk-ctl v2s-mk-mob"><button type="button" class="v2s-mk-fbtn" data-a="fopen">تصفية (' + esc(laneLabel(S.lane)) + ')</button>'
      + (S.lane !== 'all' ? '<button type="button" class="v2s-mk-chip on rm" data-a="lane" data-lane="all" aria-label="أزل التصفية">' + esc(laneLabel(S.lane)) + ' ✕</button>' : '') + '</div>';
    var trunc = H.truncated ? warn('معروض ' + ar(H.shownRows) + ' من ' + ar(H.total) + ' طلب، فالأعمدة ناقصة. القائمة الكاملة في «كل الطلبات»', '<button type="button" class="v2d-btn2" data-a="goall">افتح كل الطلبات</button>') : '';
    var seg = '', cols = '';
    X.COLS.forEach(function (c) {
      var n = T.counts[c];
      seg += '<button type="button" class="v2d-segb tone-' + COL_TONE[c] + (c === active ? ' on' : '') + '" role="tab" aria-selected="' + (c === active) + '" data-a="col" data-col="' + c + '"><span>' + esc(X.COL_LABEL[c]) + '</span><b>' + esc(ar(n)) + '</b></button>';
      var list = T.shown[c].map(ticketHtml).join('');
      if (!list) list = '<p class="v2d-none">' + esc(X.COL_EMPTY[c]) + '</p>';
      var more = T.more[c] > 0 ? '<button type="button" class="v2d-btn2 v2s-mk-more" data-a="more" data-col="' + c + '">اعرض الباقي (' + ar(T.more[c]) + ')</button>' : '';
      var note = c === 'done' && T.doneOlder > 0 ? '<p class="v2d-colnote">و' + esc(ar(T.doneOlder)) + ' أقدم في «كل الطلبات»</p>' : '';
      cols += '<section class="v2d-col tone-' + COL_TONE[c] + '" data-col="' + c + '" aria-label="' + esc(X.COL_LABEL[c]) + '"><header class="v2d-ch"><b>' + esc(X.COL_LABEL[c]) + '</b><span class="v2d-n">' + esc(ar(n)) + '</span></header>'
        + '<div class="v2d-list">' + list + '</div>' + more + note + '</section>';
    });
    v.innerHTML = '<div class="v2d v2s-mk" data-board="market">' + top + desk + mob + readOnlyLine() + trunc
      + '<div class="v2d-seg" role="tablist" aria-label="أعمدة الطلبات">' + seg + '</div><div class="v2d-cols cols4" data-active="' + active + '">' + cols + '</div></div>';
    wire(v);
  }

  // ------------------------------------------------------------------ أحداث اللوحة
  function afterWrite(id, text) {
    S.done[id] = text; delete S.detail[id]; S.err[id] = '';
    clearTimeout(S.doneTimers[id]);
    S.doneTimers[id] = setTimeout(function () { delete S.done[id]; if (isCurrent() && mod() === 'market') redraw(); }, 20000);
    var E = ep();
    if (E) E.reload('market', redraw);
    if (S.all.state === 'ready') loadAll(false);
    if (S.drawerId === id) { loadDetail(id, true); }
    redraw();
  }
  function mod() { return curMod(); }
  function runPrimary(id, how) {
    var r = rowById(id); if (!r) return;
    var b = X.brain(r, nowMs(), { readOnly: !M.canWrite() }).primary;
    if (!b) { openDrawer(id); return; }
    if (b.act === 'relane') openRelane(r, b.target);
    else if (b.act === 'link') openLink(r);
    else openDrawer(id, b.act === 'offers' ? { scroll: 'offers' } : null);
  }
  function wire(v) {
    v.onclick = function (e) {
      var t = e.target, a = t.closest ? t.closest('[data-a]') : null;
      if (!a || !v.contains(a)) {
        var art = t.closest ? t.closest('.v2d-t') : null;
        if (art && !(t.closest('a,button'))) openDrawer(art.getAttribute('data-id'));
        return;
      }
      var k = a.getAttribute('data-a'), id = a.getAttribute('data-id');
      if (k === 'reload') { var E = ep(); if (E) E.reload('market', redraw); }
      else if (k === 'open') { e.stopPropagation(); openDrawer(id); }
      else if (k === 'primary') { e.stopPropagation(); runPrimary(id); }
      else if (k === 'col') { S.seg = a.getAttribute('data-col'); redraw(); }
      else if (k === 'more') { S.expanded[a.getAttribute('data-col')] = true; redraw(); }
      else if (k === 'lane') { S.lane = a.getAttribute('data-lane'); S.seg = null; redraw(); }
      else if (k === 'test') { S.showTest = !S.showTest; redraw(); }
      else if (k === 'supply') { S.all.lane = 'training_offer'; goTab('all'); }
      else if (k === 'goall') { goTab('all'); }
      else if (k === 'fopen') { openFilter('board'); }
      else if (k === 'dreload') { var E2 = ep(); if (E2) { E2.reload('marketDemand', redraw); E2.reload('trainingInterests', redraw); } }
      else if (k === 'dretry') { var E3 = ep(); if (E3) E3.reload(a.getAttribute('data-src'), redraw); }
      else if (k === 'course') { courseSheet(a.getAttribute('data-title') || ''); }
    };
  }
  function goTab(tab) { if (host().openSection) host().openSection('market', tab); }

  // ------------------------------------------------------------------ تفاصيل الطلب (من المنصة)
  function loadDetail(id, force) {
    var E = ep(), d = S.detail[id];
    if (!E || !E.marketRequestDetail) return;
    if (d && d.state === 'loading') return;
    if (d && !force && d.state !== 'error') return;
    S.detail[id] = { state: 'loading' };
    E.marketRequestDetail(id, function (data) {
      S.detail[id] = { state: 'ready', data: data || {} }; if (S.drawerId === id) drawDrawer();
    }, function (e) {
      S.detail[id] = { state: e && e.status === 404 ? 'missing' : 'error' }; if (S.drawerId === id) drawDrawer();
    });
  }

  // ------------------------------------------------------------------ الدرج
  var ST_OFFER = { pending: 'ينتظر قرار صاحب الطلب', accepted: 'مقبول', declined: 'لم يُختر', rejected: 'لم يُختر' };
  function courseTitleOf(slug) {
    var E = ep(), list = E && E.data && E.data.courses && E.data.courses.courses;
    if (!slug) return '';
    if (Array.isArray(list)) for (var i = 0; i < list.length; i++) if (list[i].platform_slug === slug || list[i].platform_id === slug) return list[i].title || slug;
    return slug;
  }
  function telOf(p) { return String(p || '').replace(/[^\d+]/g, ''); }
  function telLink(p, cls) {
    var t = telOf(p);
    if (!t) return '<span class="v2d-mute">بلا رقم</span>';
    if (!M.canWrite()) return '<span dir="ltr" class="v2s-mk-ltr">' + esc(t) + '</span>';
    return '<a class="v2s-mk-tel ' + (cls || '') + '" href="tel:' + esc(t) + '" dir="ltr">' + esc(t) + '</a>';
  }
  function fact(k, v, cls) { return '<div class="v2s-mk-f' + (cls ? ' ' + cls : '') + '"><dt>' + esc(k) + '</dt><dd>' + v + '</dd></div>'; }
  function naText() { return '<span class="v2d-mute">' + esc(L.NA) + '</span>'; }
  function drawerRow(id) {
    var r = rowById(id); if (!r) return null;
    var d = S.detail[id];
    var q = d && d.state === 'ready' && d.data && typeof d.data.request === 'object' && d.data.request ? d.data.request : null;
    if (q) { var out = {}; Object.keys(r).forEach(function (k) { out[k] = r[k]; }); ['member_phone', 'author_kind', 'open_demand', 'join_goal', 'joined_count', 'goal_reached_at', 'linked_course_id', 'linked_course_slug', 'source', 'last_activity_at', 'updated_at', 'last_offer_at'].forEach(function (k) { if (out[k] === undefined && q[k] !== undefined && q[k] !== null) out[k] = q[k]; }); r = out; }
    return r;
  }
  function offersHtml(r, d) {
    var shownN = Number(r.offer_count) || 0;
    var body;
    if (!d || d.state === 'loading') body = '<p class="v2s-mk-load">جارٍ جلب العروض…</p>';
    else if (d.state === 'missing') body = '<p class="v2d-err">هذا الطلب لم يعد موجودًا على المنصة</p>';
    else if (d.state === 'error') body = '<p class="v2d-err" role="alert">تعذّر جلب العروض</p><button type="button" class="v2d-btn2" data-a="dretry2" data-id="' + esc(r.id) + '">أعد المحاولة</button>';
    else {
      var list = (d.data && (d.data.offers || (d.data.request && d.data.request.offers))) || [];
      shownN = list.length;
      if (!list.length) body = '<p class="v2d-none">لم يصل أي عرض بعد</p>';
      else body = '<ul class="v2s-mk-offers">' + list.map(function (o) {
        var acc = o.status === 'accepted' || (r.accepted_offer_id && o.id === r.accepted_offer_id);
        var st = acc ? 'مقبول' : (ST_OFFER[o.status] || '');
        var price = U.moneyText(o.price, o.currency || 'EGP');
        var eta = Number(o.eta_days) > 0 ? 'خلال ' + U1(Number(o.eta_days), ['يوم واحد', 'يومين', 'أيام', 'يومًا']) : '';
        var when = o.created_at ? U.agoText(o.created_at, nowMs()) : '';
        var course = o.course ? (typeof o.course === 'string' ? o.course : (o.course.title || '')) : '';
        return '<li class="' + (acc ? 'acc' : '') + '"><div class="of-h"><b>' + esc(o.expert_display || 'خبير') + '</b>' + (price ? '<span class="of-p">' + esc(price) + '</span>' : '') + '</div>'
          + '<p class="of-m">' + esc([eta, st, when].filter(Boolean).join(' · ')) + '</p>' + (o.message ? '<p class="of-t">' + esc(o.message) + '</p>' : '')
          + (course ? '<p class="of-c">الدورة المرفقة: ' + esc(course) + '</p>' : '') + '</li>';
      }).join('') + '</ul>';
    }
    return '<section class="v2s-mk-sec" id="mkOffers"><h3>' + esc('العروض (' + ar(shownN) + ')') + '</h3>' + body + '</section>';
  }
  function drawerHtml(r) {
    var now = nowMs(), ro = !M.canWrite();
    var B = X.brain(r, now, { readOnly: ro });
    var isPlat = r.author_kind === 'platform', d = S.detail[r.id];
    var created = Date.parse(r.created_at);
    var typeLbl = r.open_demand ? 'طلب مفتوح من المنصة' : (X.LANE_ONE[r.kind] || 'طلب');
    var timer = !isNaN(created) ? '<time class="v2s-mk-dt" data-ts="' + created + '" data-pre="وصل ">' + esc('وصل ' + U.agoText(created, now)) + '</time>' : '';
    var head = '<header class="v2s-mk-dh"><span class="v2s-mk-dty">' + esc(typeLbl) + '</span>' + statusChip(r) + timer
      + '<button type="button" class="v2s-mk-x" data-a="dx" aria-label="أغلق التفاصيل">✕</button></header>';
    var main = '';
    if (B.primary && (B.primary.act === 'relane' || B.primary.act === 'link')) main = '<button type="button" class="v2d-btn1" data-a="dmain" data-id="' + esc(r.id) + '">' + esc(B.primary.label) + '</button>';
    var body = r.body ? '<div class="v2s-mk-body' + (S.bodyOpen[r.id] ? ' open' : '') + '" id="mkBody">' + esc(r.body) + '</div>'
      + (String(r.body).split('\n').length > 12 || String(r.body).length > 700 ? '<button type="button" class="v2s-mk-link" data-a="dbody" data-id="' + esc(r.id) + '">' + (S.bodyOpen[r.id] ? 'اعرض أقل' : 'اعرض النص كاملًا') + '</button>' : '')
      : '<p class="v2d-none">لم يكتب صاحب الطلب نصًا</p>';
    var who = isPlat ? 'المنصة' : (personLink(r.member_name || r.member_alias || 'صاحب الطلب', r.member_email)
      + (r.member_email ? '<span class="v2s-mk-ltr sub">' + esc(r.member_email) + '</span>' : '') + (r.member_alias ? '<span class="sub">يظهر على صفحة السوق العامة باسم: ' + esc(r.member_alias) + '</span>' : ''));
    var facts = fact('صاحب الطلب', who);
    if (!isPlat) facts += fact('الهاتف', r.member_phone === undefined ? naText() : telLink(r.member_phone));
    if (r.specialty || !isPlat) facts += fact('التخصص', r.specialty ? esc(r.specialty) : '<span class="v2d-mute">لم يُحدَّد</span>');
    if (!isPlat) {
      var money = Number(r.budget) > 0 ? esc(U.moneyText(r.budget, r.currency || 'EGP')) : '<span class="v2d-mute">لم يحدّد صاحب الطلب ميزانية</span>';
      facts += fact('الميزانية', money);
    }
    facts += fact('الظهور', (r.visibility === 'public' ? 'عام في صفحة السوق' : 'خاص، لا يظهر على صفحة السوق العامة') + (r.hidden ? '<span class="sub warn">مخفي بقرار إشراف' + (r.hidden_reason ? ': ' + esc(X.arDigits(r.hidden_reason)) : '') + '</span>' : ''));
    facts += fact('وصل في', !isNaN(created) ? esc(U.dateText(r.created_at)) + '<span class="sub">' + esc(U.agoText(created, now)) + '</span>' : naText());
    facts += fact('المصدر', r.source === 'chat' ? 'محادثة بروف' : (isPlat ? 'المنصة' : (r.source === undefined && r.author_kind === undefined ? 'صفحة السوق' : 'صفحة السوق')));
    if (r.preferred_expert_email) facts += fact('موجَّه إلى', '<span class="v2s-mk-ltr">' + esc(r.preferred_expert_email) + '</span>');
    if (r.open_demand) {
      facts += fact('المنضمّون', isNum(r.joined_count) ? esc(r.join_goal > 0 ? ar(r.joined_count) + ' من ' + ar(r.join_goal) : ar(r.joined_count)) : naText());
      facts += fact('اكتمل العدد', r.goal_reached_at ? esc(U.dateText(r.goal_reached_at)) : 'لم يكتمل بعد');
      facts += fact('الدورة المرتبطة', r.linked_course_id || r.linked_course_slug ? esc(courseTitleOf(r.linked_course_slug || r.linked_course_id)) : 'لا دورة مرتبطة');
    }
    var foot = '';
    if (!ro) {
      var tgt = X.laneOf(r.need_kind), openR = r.status === undefined || r.status === '' || r.status === 'open';
      var btns = [];
      if (openR) btns.push('<button type="button" class="v2d-btn2" data-a="dclose" data-id="' + esc(r.id) + '">أغلق الطلب</button>');
      btns.push(r.hidden ? '<button type="button" class="v2d-btn2" data-a="dshow" data-id="' + esc(r.id) + '"' + (S.busy[r.id] ? ' disabled' : '') + '>' + (S.busy[r.id] ? 'جارٍ التنفيذ…' : 'أظهره على صفحة السوق العامة') + '</button>'
        : '<button type="button" class="v2d-btn2" data-a="dhide" data-id="' + esc(r.id) + '">أخفِه عن صفحة السوق العامة</button>');
      if (openR && !(Number(r.offer_count) > 0) && tgt && tgt !== r.kind && ['request', 'course_request', 'public_service'].indexOf(r.kind) > -1)
        btns.push('<button type="button" class="v2d-btn2" data-a="drelane" data-id="' + esc(r.id) + '">انقله إلى ' + esc(X.lanePlural(tgt)) + '</button>');
      if (r.open_demand && openR) btns.push('<button type="button" class="v2d-btn2" data-a="dlink" data-id="' + esc(r.id) + '">' + (r.linked_course_id ? 'غيّر الدورة المرتبطة' : 'اربط دورة') + '</button>');
      if (r.need_kind === 'course' || r.kind === 'course_request') btns.push('<button type="button" class="v2d-btn2" data-a="dcourse" data-title="' + esc(r.title || '') + '">أنشئ دورة من هذا الطلب</button>');
      if (r.member_email && !isPlat) btns.push('<button type="button" class="v2d-btn2" data-a="dperson" data-email="' + esc(r.member_email) + '">صفحة صاحب الطلب</button>');
      var tel = !isPlat ? telOf(r.member_phone) : '';
      var callBtn = tel ? '<a class="v2d-btn2 v2s-mk-calld" href="tel:' + esc(tel) + '">اتصل</a>' : '';
      foot = '<footer class="v2s-mk-df">' + callBtn + btns.join('') + '</footer>' + (tel ? '<div class="v2s-mk-callbar"><a class="v2d-btn1 v2s-mk-call" href="tel:' + esc(tel) + '">اتصل</a></div>' : '');
    } else if (r.member_email && !isPlat) {
      foot = '<footer class="v2s-mk-df"><button type="button" class="v2d-btn2" data-a="dperson" data-email="' + esc(r.member_email) + '">صفحة صاحب الطلب</button></footer>';
    }
    var err = S.err[r.id] ? '<div class="v2d-err" role="alert">' + esc(S.err[r.id]) + '</div>' : '';
    var done = S.done[r.id] ? '<p class="v2d-ok" role="status">' + esc(S.done[r.id]) + '</p>' : '';
    return head + '<div class="v2s-mk-db"><h2 id="mkDrT">' + esc(r.title || 'طلب بلا عنوان') + '</h2>'
      + '<div class="v2d-brain">' + BRAIN + '<p>' + esc(B.line) + '</p></div>' + main + done + err
      + '<section class="v2s-mk-sec"><h3>نص الطلب</h3>' + body + '</section>'
      + '<section class="v2s-mk-sec"><h3>التفاصيل</h3><dl class="v2s-mk-facts">' + facts + '</dl></section>' + offersHtml(r, d) + '</div>' + foot;
  }
  function isNum(n) { return typeof n === 'number' && isFinite(n); }

  function removeOv() { var o = document.getElementById('mkOv'); if (o) o.remove(); S.ov = ''; document.documentElement.classList.remove('v2s-mk-lock'); }
  function mountOv(kind, cls, html) {
    removeOv();
    var o = document.createElement('div');
    o.id = 'mkOv'; o.className = 'v2s-mk-ov ' + cls;
    o.innerHTML = '<div class="v2s-mk-scrim" data-a="dx"></div><section class="v2s-mk-panel v3m" role="dialog" aria-modal="true">' + html + '</section>';
    document.body.appendChild(o);
    S.ov = kind;
    document.documentElement.classList.add('v2s-mk-lock');
    o.onclick = ovClick;
    return o;
  }
  function openDrawer(id, opts) {
    var r = drawerRow(id); if (!r) return;
    if (S.ov !== 'drawer') S.opener = document.activeElement;
    S.drawerId = id;
    var o = mountOv('drawer', 'v2s-mk-dr', '');
    o.querySelector('.v2s-mk-panel').setAttribute('aria-labelledby', 'mkDrT');
    drawDrawer();
    loadDetail(id, false);
    var x = o.querySelector('.v2s-mk-x'); if (x) { try { x.focus({ preventScroll: true }); } catch (e) {} }
    if (opts && opts.scroll === 'offers') { var of = document.getElementById('mkOffers'); if (of && of.scrollIntoView) of.scrollIntoView({ block: 'start' }); }
  }
  function drawDrawer() {
    var o = document.getElementById('mkOv');
    if (!o || S.ov !== 'drawer') return;
    var r = drawerRow(S.drawerId);
    var panel = o.querySelector('.v2s-mk-panel'); if (!panel) return;
    if (!r) { closeDrawer(); return; }
    var db = panel.querySelector('.v2s-mk-db'), top = db ? db.scrollTop : 0;
    var hadFocus = panel.contains(document.activeElement) ? document.activeElement.getAttribute('data-a') : '';
    panel.innerHTML = drawerHtml(r);
    var nd = panel.querySelector('.v2s-mk-db'); if (nd) nd.scrollTop = top;
    if (hadFocus) { var f = panel.querySelector('[data-a="' + hadFocus + '"]'); if (f) { try { f.focus({ preventScroll: true }); } catch (e) {} } }
    if (!panel.contains(document.activeElement)) { var x = panel.querySelector('.v2s-mk-x'); if (x) { try { x.focus({ preventScroll: true }); } catch (e) {} } }
  }
  function closeDrawer() {
    var wasDrawer = S.ov === 'drawer';
    removeOv(); S.drawerId = '';
    var op = S.opener; S.opener = null;
    if (wasDrawer && op && op.focus && document.body.contains(op)) { try { op.focus({ preventScroll: true }); } catch (e) {} }
  }
  function ovClick(e) {
    var a = e.target.closest ? e.target.closest('[data-a]') : null;
    if (!a) return;
    var k = a.getAttribute('data-a'), id = a.getAttribute('data-id');
    if (k === 'dx') closeDrawer();
    else if (k === 'dretry2') loadDetail(id, true), drawDrawer();
    else if (k === 'dbody') { S.bodyOpen[id] = !S.bodyOpen[id]; drawDrawer(); }
    else if (k === 'dmain') runPrimary(id);
    else if (k === 'dclose') openClose(rowById(id));
    else if (k === 'dhide') openHide(rowById(id));
    else if (k === 'dshow') showAgain(rowById(id));
    else if (k === 'drelane') { var r = rowById(id); openRelane(r, X.laneOf(r.need_kind)); }
    else if (k === 'dlink') openLink(rowById(id));
    else if (k === 'dcourse') courseSheet(a.getAttribute('data-title') || '');
    else if (k === 'dperson') { var em = a.getAttribute('data-email'); closeDrawer(); if (host().openPerson) host().openPerson(em); }
    else if (k === 'fclose') closeDrawer();
    else if (k === 'flane') { S.lane = a.getAttribute('data-lane'); S.seg = null; redraw(); drawFilterBoard(); }
    else if (k === 'ftest') { S.showTest = !S.showTest; redraw(); drawFilterBoard(); }
    else if (k === 'fsupply') { S.all.lane = 'training_offer'; closeDrawer(); goTab('all'); }
  }

  // ------------------------------------------------------------------ أوراق التأكيد (نافذة الداشبورد الموجودة بشكل الورقة الجديدة)
  function sheet(title, html) {
    if (typeof window.openModal !== 'function') return null;
    var s = window.openModal(title, '<div class="v3m v2s-mk-sb">' + html + '</div>');
    s.classList.add('v2s-mk-sh');
    var x = s.querySelector('[data-x]');
    if (x) { x.setAttribute('aria-label', 'إغلاق'); x.onclick = function () { if (!s.dataset.busy) window.closeModal(); }; }
    s.onclick = function (e) { if (e.target === s && !s.dataset.busy) window.closeModal(); };
    return s;
  }
  function plainErr(e, map) {
    if (e && e.status === 401) return 'انتهت الجلسة — سجّل الدخول من جديد ثم جرّب';
    var st = e && e.status;
    if (map && map[st]) return map[st];
    return map && map.other ? map.other : 'تعذّر تنفيذ العملية، حاول مرة أخرى';
  }
  // o: {title, lead, field(label)|null, ok, send(reason)→Promise, success(res, reason)→text, errs:{409,404,422,other}, id}
  function confirmSheet(o) {
    var field = o.field ? '<div class="fld"><label for="mkReason">' + esc(o.field) + '</label><textarea id="mkReason" maxlength="300" rows="3"></textarea><div class="v2s-mk-cnt" id="mkCnt" aria-live="polite">' + ar(0) + ' / ' + ar(300) + '</div></div>' : '';
    var s = sheet(o.title, '<p class="mc-lead">' + o.lead + '</p>' + (o.extra || '') + field + '<div id="mkErr" role="alert"></div>'
      + '<div class="acts"><button type="button" class="btn btn-primary" id="mkGo">' + esc(o.ok) + '</button><button type="button" class="btn btn-ghost" id="mkNo">تراجع</button></div>');
    if (!s) return;
    var go = s.querySelector('#mkGo'), no = s.querySelector('#mkNo'), ta = s.querySelector('#mkReason'), err = s.querySelector('#mkErr');
    if (o.after) o.after(s);
    if (ta) ta.addEventListener('input', function () { s.querySelector('#mkCnt').textContent = ar(ta.value.length) + ' / ' + ar(300); });
    no.onclick = function () { if (!s.dataset.busy) window.closeModal(); };
    go.onclick = function () {
      if (s.dataset.busy) return;
      if (o.validate) { var bad = o.validate(s); if (bad) { err.innerHTML = '<div class="v2d-err">' + esc(bad) + '</div>'; return; } }
      var reason = ta ? ta.value.trim().slice(0, 300) : '';
      s.dataset.busy = '1'; go.disabled = true; no.disabled = true; go.textContent = 'جارٍ التنفيذ…'; err.innerHTML = '';
      Promise.resolve(o.send(reason, s)).then(function (res) {
        delete s.dataset.busy; window.closeModal();
        afterWrite(o.id, o.success(res || {}, reason));
      }).catch(function (e) {
        delete s.dataset.busy; go.disabled = false; no.disabled = false; go.textContent = o.ok;
        err.innerHTML = '<div class="v2d-err" role="alert">' + esc(o.errText ? o.errText(e) : plainErr(e, o.errs)) + '</div>';
      });
    };
    setTimeout(function () { var f = ta || go; if (f && f.focus) { try { f.focus(); } catch (e) {} } }, 30);
    return s;
  }
  function api(path, body, method) { var E = ep(); return E.api(path, { method: method || 'POST', body: body }); }
  function qtitle(r) { return '«' + esc(r.title || 'طلب بلا عنوان') + '»'; }

  function openClose(r) {
    if (!r) return;
    var cnt = Number(r.offer_count) || 0;
    confirmSheet({
      id: r.id, title: 'إغلاق الطلب', ok: 'أغلق الطلب', field: 'سبب الإغلاق (اختياري، يُحفظ في السجل)',
      lead: 'إغلاق ' + qtitle(r) + '؟ لن يقبل عروضًا جديدة.' + (cnt > 0 ? ' وصله ' + esc(U1(cnt, ['عرض واحد', 'عرضان', 'عروض', 'عرضًا'])) + ' لم يختر صاحب الطلب منها شيئًا.' : ''),
      send: function (reason) { return api('/platform-market-requests/' + encodeURIComponent(r.id) + '/close', { reason: reason }); },
      success: function (res) { return res && res.already ? 'كان مغلقًا من قبل' : 'أُغلق «' + (r.title || 'الطلب') + '»'; },
      errs: { 409: 'تمّت مطابقة هذا الطلب، فلا يمكن إغلاقه', 404: 'هذا الطلب لم يعد موجودًا على المنصة', other: 'تعذّر إغلاق الطلب، حاول مرة أخرى' }
    });
  }
  function openHide(r) {
    if (!r) return;
    confirmSheet({
      id: r.id, title: 'إخفاء عن صفحة السوق العامة', ok: 'أخفِه', field: 'السبب (اختياري، يُحفظ في السجل)',
      lead: 'يختفي ' + qtitle(r) + ' من صفحة السوق العامة ولا يقبل عروضًا جديدة، ويبقى ظاهرًا لصاحبه وهنا. يمكنك إظهاره في أي وقت.',
      send: function (reason) { return api('/platform-market-requests/' + encodeURIComponent(r.id) + '/hide', { hidden: true, reason: reason }); },
      success: function () { return 'أُخفي «' + (r.title || 'الطلب') + '» عن صفحة السوق العامة'; },
      errs: { 404: 'هذا الطلب لم يعد موجودًا على المنصة', other: 'تعذّر الإخفاء، حاول مرة أخرى' }
    });
  }
  function showAgain(r) {
    if (!r || S.busy[r.id]) return;
    S.busy[r.id] = true; S.err[r.id] = ''; drawDrawer();
    api('/platform-market-requests/' + encodeURIComponent(r.id) + '/hide', { hidden: false, reason: '' }).then(function () {
      S.busy[r.id] = false; afterWrite(r.id, 'رجع الطلب إلى صفحة السوق العامة');
    }).catch(function (e) {
      S.busy[r.id] = false; S.err[r.id] = plainErr(e, { 404: 'هذا الطلب لم يعد موجودًا على المنصة', other: 'تعذّر تنفيذ العملية، حاول مرة أخرى' }); drawDrawer(); redraw();
    });
  }
  function openRelane(r, target) {
    if (!r || !target) return;
    confirmSheet({
      id: r.id, title: 'نقل الطلب', ok: 'انقل الطلب', field: 'السبب (اختياري)',
      lead: 'نقل ' + qtitle(r) + ' من ' + esc(X.lanePlural(r.kind)) + ' إلى ' + esc(X.lanePlural(target)) + '؟ لا يتغير نصه ولا صاحبه، ويمكن إرجاعه.',
      send: function (reason) { return api('/v2/market/requests/' + encodeURIComponent(r.id) + '/relane', { need_kind: r.need_kind, reason: reason, confirmed: true }); },
      success: function () { return 'نُقل إلى ' + X.lanePlural(target); },
      errs: { 409: 'وصله عرض بالفعل، فلا يمكن نقله الآن', 422: 'نوع الطلب غير معروف', 404: 'هذا الطلب لم يعد موجودًا على المنصة', other: 'تعذّر نقل الطلب، حاول مرة أخرى' }
    });
  }

  // —— ربط دورة بطلب مفتوح
  function openLink(r) {
    if (!r) return;
    var E = ep();
    if (E && stateOf('courses') === 'idle') E.ensure('courses', function () { refreshLink(r.id); });
    relinkSheet(r);
  }
  function refreshLink(id) {
    var cur = document.getElementById('epModal');
    if (!cur || cur.getAttribute('data-link') !== String(id) || cur.dataset.busy) return;
    var r = rowById(id); if (!r) return;
    window.closeModal(); relinkSheet(r);
  }
  function relinkSheet(r) {
    var E = ep(), st = stateOf('courses'), list = E && E.data && E.data.courses && E.data.courses.courses;
    var lead = r.open_demand && isNum(r.joined_count) ? 'اكتمل العدد: ' + esc(r.join_goal > 0 ? 'انضم ' + ar(r.joined_count) + ' من ' + ar(r.join_goal) : 'انضم ' + ar(r.joined_count)) : 'اختر الدورة التي ستُربط بهذا الطلب.';
    var courses = Array.isArray(list) ? list.filter(function (c) { return c.on_platform && c.platform_slug; }) : [];
    var body, chosen = '';
    if (st === 'error') body = '<div class="v2d-err" role="alert">تعذّر جلب الدورات</div><button type="button" class="btn btn-ghost" id="mkRetry">أعد المحاولة</button>';
    else if (st === 'idle' || (st === 'loading' && !list)) body = '<p class="v2s-mk-load">جارٍ جلب الدورات…</p>';
    else if (!courses.length) body = '<p class="v2d-none">لا دورات منشورة على المنصة بعد</p><button type="button" class="btn btn-ghost" id="mkMake">أنشئ دورة من هذا الطلب</button>';
    else {
      body = (courses.length > 8 ? '<div class="fld"><label for="mkCs">ابحث في الدورات</label><input id="mkCs" type="search" autocomplete="off"></div>' : '')
        + '<div class="v2s-mk-radios" role="radiogroup" aria-label="الدورات">' + courses.map(function (c) {
          return '<label class="v2s-mk-radio" data-t="' + esc((c.title + ' ' + c.inst).toLowerCase()) + '"><input type="radio" name="mkc" value="' + esc(c.platform_slug) + '"'
            + (r.linked_course_slug === c.platform_slug ? ' checked' : '') + '><span><b>' + esc(c.title) + '</b><small>' + esc(c.inst && c.inst !== '—' ? c.inst : 'فريق البروفيسور') + '</small></span></label>';
        }).join('') + '</div>';
    }
    var notice = isNum(r.joined_count) ? '<p class="v2s-mk-note">سيصل إشعار داخل المنصة لكل من انضم (' + esc(ar(r.joined_count)) + ') بأن الدورة صارت متاحة للحجز.</p>' : '<p class="v2s-mk-note">سيصل إشعار داخل المنصة لكل من انضم بأن الدورة صارت متاحة للحجز.</p>';
    var unlink = r.linked_course_id ? '<button type="button" class="btn btn-ghost" id="mkUnlink">ألغِ ربط الدورة</button>' : '';
    var s = sheet('ربط دورة بالطلب', '<p class="mc-lead">' + lead + '</p>' + body + (courses.length ? notice : '') + '<div id="mkErr" role="alert"></div>'
      + '<div class="acts">' + (courses.length ? '<button type="button" class="btn btn-primary" id="mkGo" disabled>اربط الدورة</button>' : '') + unlink + '<button type="button" class="btn btn-ghost" id="mkNo">تراجع</button></div>');
    if (!s) return;
    s.setAttribute('data-link', String(r.id));
    var go = s.querySelector('#mkGo'), no = s.querySelector('#mkNo'), err = s.querySelector('#mkErr');
    function send(course, label) {
      if (s.dataset.busy) return;
      s.dataset.busy = '1'; [go, no, s.querySelector('#mkUnlink')].forEach(function (b) { if (b) b.disabled = true; });
      err.innerHTML = ''; if (go && label !== 'unlink') go.textContent = 'جارٍ التنفيذ…';
      api('/v2/market/requests/' + encodeURIComponent(r.id) + '/link-course', { course: course, confirmed: true }).then(function () {
        delete s.dataset.busy; window.closeModal(); afterWrite(r.id, course ? 'رُبطت الدورة' : 'أُلغي ربط الدورة');
      }).catch(function (e) {
        delete s.dataset.busy; [go, no, s.querySelector('#mkUnlink')].forEach(function (b) { if (b) b.disabled = false; }); if (go) { go.textContent = 'اربط الدورة'; go.disabled = !chosen; }
        err.innerHTML = '<div class="v2d-err" role="alert">' + esc(e && e.status === 401 ? 'انتهت الجلسة — سجّل الدخول من جديد ثم جرّب' : L.v2sMarket.linkErr(e && e.status, e && e.data)) + '</div>';
      });
    }
    no.onclick = function () { if (!s.dataset.busy) window.closeModal(); };
    s.querySelectorAll('input[name="mkc"]').forEach(function (i) { i.onchange = function () { chosen = i.value; if (go) go.disabled = false; }; if (i.checked) { chosen = i.value; if (go) go.disabled = false; } });
    if (go) go.onclick = function () { if (chosen) send(chosen, 'link'); };
    var un = s.querySelector('#mkUnlink'); if (un) un.onclick = function () { send('', 'unlink'); };
    var cs = s.querySelector('#mkCs');
    if (cs) cs.oninput = function () { var q = cs.value.trim().toLowerCase(); s.querySelectorAll('.v2s-mk-radio').forEach(function (l) { l.style.display = !q || l.getAttribute('data-t').indexOf(q) > -1 ? '' : 'none'; }); };
    var rt = s.querySelector('#mkRetry'); if (rt) rt.onclick = function () { if (ep()) ep().reload('courses', function () { refreshLink(r.id); }); };
    var mk = s.querySelector('#mkMake'); if (mk) mk.onclick = function () { window.closeModal(); courseSheet(r.title || ''); };
  }

  // —— إنشاء دورة من طلب: نافذة الإنشاء الموجودة بعد إعادة تلبيسها (الدورات تملكها؛ نحن نلبّسها من الخارج فقط)
  function retext(el, text) {
    if (!el) return;
    var n = Array.prototype.filter.call(el.childNodes, function (c) { return c.nodeType === 3 && c.nodeValue.trim(); })[0];
    if (n) n.nodeValue = ' ' + text + ' '; else el.appendChild(document.createTextNode(text));
  }
  function guardCourseView() {
    if (S.courseGuard || typeof window.viewCourses !== 'function') return;
    S.courseGuard = true;
    var orig = window.viewCourses;
    // بعد نجاح الإنشاء يستدعي الكود القديم `viewCourses(#view)` فيرسم شاشة الدورات القديمة فوق هذا القسم؛ داخل قسمنا نعيد رسم السوق بدلًا منها.
    window.viewCourses = function (v) {
      if (isCurrent() && S.view === v) { toast('أُنشئت الدورة'); if (ep()) ep().reload('courses', null); redraw(); return; }
      return orig.apply(this, arguments);
    };
  }
  function courseSheet(title) {
    if (typeof window.createCourseModal !== 'function') return;
    var E = ep();
    guardCourseView();
    if (E) E.ensure('courses', null);
    window.createCourseModal(title || '');
    var s = document.getElementById('epModal');
    if (!s) return;
    s.classList.add('v2s-mk-cc');
    var mb = s.querySelector('.mb'); if (mb) mb.classList.add('v3m');
    var x = s.querySelector('[data-x]'); if (x) x.setAttribute('aria-label', 'إغلاق');
    var hd = s.querySelector('#m_head'); if (hd && hd.parentNode) retext(hd.parentNode, 'تسعير لكل فرد');
    retext(s.querySelector('details summary'), 'أنشئ المنهج تلقائيًا (اختياري)');
    var tit = s.querySelector('#m_titch'); if (tit) retext(tit, 'أنشئ المنهج وانشر');
    var hint = s.querySelector('details > div > div'); if (hint) hint.textContent = 'الصق ملخّص الدورة وهدفها التعليمي، فيُولَّد منهج من دروس متدرّجة وأسئلة تفاعلية ويرتبط بالدورة تلقائيًا.';
    var plat = s.querySelector('#m_plat'); if (plat && plat.parentNode) retext(plat.parentNode, 'دورة من المنصة نفسها (بلا مدرّب)');
    var mail = s.querySelector('#m_email'); if (mail && mail.nextElementSibling) mail.nextElementSibling.textContent = 'بهذا البريد تصبح الدورة دورة المدرّب: تظهر في «دوراتي» عنده، ويضيف حلقاتها ويرى دفعتها ومستحقاته. بدونه تبقى الدورة للإدارة وحدها.';
    if (mail) mail.setAttribute('placeholder', 'بريد المدرّب');
    var f = s.querySelector('#m_title'); if (f && f.focus) { try { f.focus(); } catch (e) {} }
  }
  M.courseSheet = courseSheet;

  // ------------------------------------------------------------------ ورقة التصفية (اللوحة في الموبايل · وكل الطلبات)
  function drawFilterBoard() {
    var o = document.getElementById('mkOv');
    if (!o || S.ov !== 'fboard') return;
    var g = boardData(), H = X.header(g.rows || [], g.counts, g.count, nowMs()), T = S.T;
    var chips = ['all', 'request', 'course_request', 'public_service'].map(function (k) {
      return '<button type="button" class="v2s-mk-chip' + (S.lane === k ? ' on' : '') + '" role="radio" aria-checked="' + (S.lane === k) + '" data-a="flane" data-lane="' + k + '">' + esc(laneLabel(k) === 'الكل' ? 'كل الطلبات' : laneLabel(k)) + ' (' + ar(H.lanes[k]) + ')</button>';
    }).join('');
    var test = T && T.testCount > 0 ? '<button type="button" class="v2s-mk-chip tog' + (S.showTest ? ' on' : '') + '" data-a="ftest" aria-pressed="' + S.showTest + '">' + (S.showTest ? 'أخفِ التجريبي' : 'أظهر التجريبي (' + ar(T.testCount) + ')') + '</button>' : '';
    var supply = H.lanes.training_offer > 0 ? '<button type="button" class="v2s-mk-link" data-a="fsupply">عروض المدرّبين (' + ar(H.lanes.training_offer) + ')</button>' : '';
    o.querySelector('.v2s-mk-panel').innerHTML = '<header class="v2s-mk-dh"><span class="v2s-mk-dty">تصفية الطلبات</span><button type="button" class="v2s-mk-x" data-a="fclose" aria-label="أغلق">✕</button></header>'
      + '<div class="v2s-mk-db"><h3>نوع الطلب</h3><div class="v2s-mk-chips col" role="radiogroup">' + chips + '</div>' + (test ? '<h3>التجريبي</h3>' + test : '') + (supply ? '<h3>العروض</h3>' + supply : '') + '</div>'
      + '<footer class="v2s-mk-df"><button type="button" class="v2d-btn1" data-a="fclose">اعرض النتائج</button></footer>';
  }
  function openFilter(kind) {
    S.opener = document.activeElement;
    if (kind === 'board') { mountOv('fboard', 'v2s-mk-fs', ''); drawFilterBoard(); }
    else openFilterAll();
    var x = document.querySelector('#mkOv .v2s-mk-x'); if (x) { try { x.focus({ preventScroll: true }); } catch (e) {} }
  }
  var FD = null;
  function openFilterAll() {
    var A = S.all;
    FD = { status: A.status, need: A.need, author: A.author, test: S.showTest };
    mountOv('fall', 'v2s-mk-fs', '');
    drawFilterAll();
  }
  function chipGroup(label, key, defs, cur, counts) {
    return '<h3>' + esc(label) + '</h3><div class="v2s-mk-chips col" role="radiogroup" aria-label="' + esc(label) + '">' + defs.map(function (d) {
      var n = counts && d[0] !== 'all' ? ' (' + ar(counts[d[0]] || 0) + ')' : '';   // المنصة تحذف الأرقام الصفرية من الرد، فغيابها داخل رد موجود = صفر حقيقي؛ ولا رقم لـ«الكل» (قد يخالف الإجمالي)
      return '<button type="button" class="v2s-mk-chip' + (cur === d[0] ? ' on' : '') + '" role="radio" aria-checked="' + (cur === d[0]) + '" data-a="fset" data-k="' + key + '" data-v="' + d[0] + '">' + esc(d[1]) + n + '</button>';
    }).join('') + '</div>';
  }
  function drawFilterAll() {
    var o = document.getElementById('mkOv');
    if (!o || S.ov !== 'fall') return;
    var C = S.all.counts || {}, bs = S.all.status === 'all' ? (C.by_status || {}) : null, bn = S.all.need === 'all' ? (C.by_need_kind || {}) : null, ba = S.all.author === 'all' ? (C.by_author_kind || {}) : null;
    var st = chipGroup('الحالة', 'status', [['all', 'كل الحالات'], ['open', 'مفتوح'], ['matched', 'تمّت المطابقة'], ['closed', 'أُغلق']], FD.status, bs);
    var needDefs = [['all', 'الكل']].concat(['expert', 'service', 'course', 'book', 'other'].map(function (k) { return [k, X.needLabel(k)]; }));
    var nd = chipGroup('نوع الاحتياج', 'need', needDefs, FD.need, bn);
    var au = chipGroup('كاتب الطلب', 'author', [['all', 'الكل'], ['member', 'الأعضاء'], ['platform', 'المنصة']], FD.author, ba);
    var test = '<h3>التجريبي</h3><button type="button" class="v2s-mk-chip tog' + (FD.test ? ' on' : '') + '" data-a="fset" data-k="test" data-v="' + (FD.test ? '0' : '1') + '" aria-pressed="' + FD.test + '">أظهر التجريبي</button>';
    o.querySelector('.v2s-mk-panel').innerHTML = '<header class="v2s-mk-dh"><span class="v2s-mk-dty">تصفية الطلبات</span><button type="button" class="v2s-mk-x" data-a="dx" aria-label="أغلق">✕</button></header>'
      + '<div class="v2s-mk-db">' + st + nd + au + test + '</div><footer class="v2s-mk-df"><button type="button" class="v2d-btn1" data-a="fapply">اعرض النتائج</button><button type="button" class="v2d-btn2" data-a="fclear">امسح الفلاتر</button></footer>';
    o.onclick = function (e) {
      var a = e.target.closest ? e.target.closest('[data-a]') : null; if (!a) return;
      var k = a.getAttribute('data-a');
      if (k === 'dx') closeDrawer();
      else if (k === 'fset') { var kk = a.getAttribute('data-k'), vv = a.getAttribute('data-v'); if (kk === 'test') FD.test = vv === '1'; else FD[kk] = vv; drawFilterAll(); }
      else if (k === 'fclear') { FD = { status: 'all', need: 'all', author: 'all', test: false }; drawFilterAll(); }
      else if (k === 'fapply') { S.all.status = FD.status; S.all.need = FD.need; S.all.author = FD.author; S.showTest = FD.test; closeDrawer(); loadAll(false); }
    };
  }

  // ------------------------------------------------------------------ كل الطلبات
  function loadAll(append) {
    var E = ep(), A = S.all;
    if (!E || !E.api) { A.state = 'error'; return; }
    var seq = ++A.seq;
    if (!append) { A.state = 'loading'; A.loadedSig = allSig(); }
    else A.more = true;
    var qs = X.query({ lane: A.lane, status: A.status, need: A.need, author: A.author, q: A.q, showTest: S.showTest, limit: 50, skip: append ? A.items.length : 0 });
    redrawAll();
    E.api('/v2/market/requests?' + qs).then(function (r) {
      if (seq !== A.seq) return;
      var items = Array.isArray(r && r.items) ? r.items : [];
      A.items = append ? A.items.concat(items) : items;
      A.total = r && r.total != null ? r.total : A.items.length;
      A.counts = (r && r.counts) || A.counts || null;
      // أرقام الحارات على المجموعة المفلترة (جسر المنصة): تحت حارة محدّدة تنهار الحارات التانية لصفر كاذب، فنحفظ آخر أرقام الحارات من استعلام «كل الأنواع» بنفس باقي الفلاتر.
      if (A.lane === 'all' && A.counts && A.counts.by_lane) A.laneCache = { sig: filterSig(), by_lane: A.counts.by_lane };
      A.state = 'ready'; A.more = false; redrawAll();
    }).catch(function (e) {
      if (seq !== A.seq) return;
      A.more = false;
      if (e && e.status === 401) { if (append) { A.state = 'ready'; A.appendErr = true; } else A.state = 'error'; redrawAll(); return; }
      if (append) { A.state = 'ready'; A.appendErr = true; }
      else { A.state = e && e.status === 404 && e.data && e.data.bridge_missing ? 'missing' : 'error'; }
      redrawAll();
    });
  }
  function allSig() { return filterSig() + '|' + S.all.lane; }
  function filterSig() { var A = S.all; return [A.status, A.need, A.author, A.q, S.showTest ? 1 : 0].join('|'); }
  function laneNumbers() {
    var A = S.all, bl = A.counts && A.counts.by_lane ? A.counts.by_lane : null;
    if (A.lane === 'all') return bl ? { request: bl.request || 0, course_request: bl.course_request || 0, public_service: bl.public_service || 0, training_offer: bl.training_offer || 0 } : null;
    if (A.laneCache && A.laneCache.sig === filterSig()) { var c = A.laneCache.by_lane; return { request: c.request || 0, course_request: c.course_request || 0, public_service: c.public_service || 0, training_offer: c.training_offer || 0 }; }
    return null;
  }
  function allFilterCount() { return X.activeFilters({ status: S.all.status, need: S.all.need, author: S.all.author, showTest: S.showTest }).length; }
  function rm(k, label) { return '<button type="button" class="v2s-mk-chip on rm" data-a="arm" data-k="' + k + '" aria-label="' + esc('أزل ' + label) + '">' + esc(label) + ' ✕</button>'; }
  function allBodyHtml() {
    var A = S.all, now = nowMs();
    var bl = laneNumbers();
    var defs = [['all', 'كل الأنواع'], ['request', 'طلبات الخبرة'], ['course_request', 'طلبات الدورات'], ['public_service', 'خدمات للجمهور'], ['training_offer', 'عروض المدرّبين']];
    var chips = defs.map(function (d) {
      var n = bl ? (d[0] === 'all' ? bl.request + bl.course_request + bl.public_service + bl.training_offer : bl[d[0]])
        : (d[0] === A.lane && A.state === 'ready' && A.total != null ? A.total : null);
      return '<button type="button" class="v2s-mk-chip' + (A.lane === d[0] ? ' on' : '') + '" role="tab" aria-selected="' + (A.lane === d[0]) + '" data-a="alane" data-lane="' + d[0] + '">' + esc(d[1]) + (n != null ? ' (' + ar(n) + ')' : '') + '</button>';
    }).join('');
    var nf = allFilterCount();
    var act = X.activeFilters({ status: A.status, need: A.need, author: A.author, showTest: S.showTest }).map(function (f) { return rm(f.k, f.label); }).join('');
    var ctl = '<div class="v2s-mk-ctl"><div class="v2s-mk-chips strip" role="tablist" aria-label="نوع الطلب">' + chips + '</div><button type="button" class="v2s-mk-fbtn" data-a="afopen">تصفية' + (nf ? ' (' + ar(nf) + ')' : '') + '</button></div>'
      + (act ? '<div class="v2s-mk-act">' + act + '</div>' : '');
    var res;
    if (A.state === 'idle' || (A.state === 'loading' && !A.items.length)) {
      res = '<div class="v2s-mk-skrows">' + '<i class="v2s-mk-sk"></i>'.repeat(6) + '</div>';
    } else if (A.state === 'missing') res = missingCard();
    else if (A.state === 'error') res = warn('تعذّر جلب الطلبات من المنصة', retryBtn('aretry'));
    else {
      var filtered = A.q || A.lane !== 'all' || nf > 0;
      if (!A.items.length) {
        res = filtered ? '<div class="v2s-mk-empty"><b>لا طلبات تطابق هذا البحث</b><p></p><button type="button" class="v2d-btn2" data-a="aclear">امسح الفلاتر</button></div>' : emptyCard('لا طلبات في السوق بعد', 'أول طلب يصل من محادثة بروف أو من صفحة السوق على المنصة');
      } else {
        var rowsV = A.items.map(function (it) { return X.allRow(X.norm(it), now); });
        var hid = '';
        var g = boardData();
        if (!S.showTest && g.rows && !(g.count > g.rows.length)) {
          var tc = g.rows.filter(function (x) { return x.is_test && x.kind !== 'training_offer'; }).length;
          if (tc > 0) hid = ' + ' + ar(tc) + ' تجريبي مخفي';
        }
        var line = '<p class="v2s-mk-rl">' + esc(U1(A.total, TOTAL_FORMS) + hid) + (filtered ? ' — <button type="button" class="v2s-mk-link" data-a="aclear">امسح الفلاتر</button>' : '') + '</p>';
        var tb = '<div class="v2s-mk-tbw"><table class="v2s-mk-tb"><thead><tr><th>الطلب</th><th>صاحب الطلب</th><th>العروض</th><th>الحالة</th><th class="c-date">وصل</th></tr></thead><tbody>' + rowsV.map(function (r) {
          return '<tr data-a="arow" data-id="' + esc(r.id) + '"><td><button type="button" class="v2s-mk-rowbtn" data-a="arow" data-id="' + esc(r.id) + '">' + esc(r.title) + '</button><span class="v2s-mk-tag lane">' + esc(r.lane) + '</span>'
            + r.badges.map(function (b) { return '<span class="v2s-mk-tag b-' + b.k + '">' + esc(b.label) + '</span>'; }).join('') + '<span class="v2s-mk-ago">' + esc(r.ago) + '</span></td><td>' + esc(r.who.name) + '</td><td>' + esc(r.offersText) + '</td><td><span class="v2s-mk-st st-' + r.statusKey + '">' + esc(r.status) + '</span></td><td class="c-date">' + esc(r.date) + '</td></tr>';
        }).join('') + '</tbody></table></div>';
        var cards = '<ul class="v2s-mk-cards">' + rowsV.map(function (r) {
          return '<li><button type="button" class="v2s-mk-card" data-a="arow" data-id="' + esc(r.id) + '"><b>' + esc(r.title) + '</b><span class="cm"><span class="v2s-mk-tag lane">' + esc(r.lane) + '</span>' + r.badges.map(function (b) { return '<span class="v2s-mk-tag b-' + b.k + '">' + esc(b.label) + '</span>'; }).join('')
            + '</span><span class="cw">' + esc(r.who.name) + '</span><span class="cs"><span class="v2s-mk-st st-' + r.statusKey + '">' + esc(r.status) + '</span><small>' + esc(r.ago) + '</small></span></button></li>';
        }).join('') + '</ul>';
        var pager = A.items.length < A.total ? '<p class="v2s-mk-pg">معروض ' + esc(ar(A.items.length)) + ' من ' + esc(ar(A.total)) + '</p><button type="button" class="v2d-btn2 v2s-mk-more" data-a="amore"' + (A.more ? ' disabled' : '') + '>' + (A.more ? 'جارٍ التحميل…' : 'اعرض ' + ar(50) + ' أخرى') + '</button>' : '<p class="v2s-mk-pg">معروض ' + esc(ar(A.items.length)) + ' من ' + esc(ar(A.total)) + '</p>';
        res = line + tb + cards + pager + (A.appendErr ? warn('تعذّر تحميل المزيد، حاول مرة أخرى') : '');
      }
    }
    return ctl + '<div class="v2s-mk-res" aria-live="polite">' + res + '</div>';
  }
  function allShellHtml() {
    return '<div class="v2d v2s-mk v2s-mk-all" data-board="market-all">' + readOnlyLine() + '<div class="v2s-mk-search" role="search"><label for="mkq">ابحث في الطلبات</label><div class="v2s-mk-sbox"><input id="mkq" type="search" maxlength="80" autocomplete="off" placeholder="العنوان أو النص أو البريد" value="' + esc(S.all.q) + '"><button type="button" class="v2d-btn1 sgo" data-a="ago">ابحث</button></div></div><div id="mkAllBody"></div></div>';
  }
  function drawAll(v) {
    v.innerHTML = allShellHtml();
    var inp = v.querySelector('#mkq');
    inp.addEventListener('input', function () { clearTimeout(S.qTimer); S.qTimer = setTimeout(function () { applyQ(inp.value); }, 400); });
    inp.addEventListener('keydown', function (e) { if (e.key === 'Enter') { e.preventDefault(); clearTimeout(S.qTimer); applyQ(inp.value); } });
    v.onclick = allClick;
    redrawAll();
    // يعاد الجلب إذا تغيّر أي فلتر (النوع/الحالة/الاحتياج/الكاتب/البحث/التجريبي) منذ آخر جلب، لا عند أول دخول فقط.
    if (S.all.state === 'idle' || S.all.loadedSig !== allSig()) loadAll(false);
  }
  function applyQ(val) { var q = String(val || '').trim().slice(0, 80); if (q === S.all.q && S.all.state !== 'error') return; S.all.q = q; loadAll(false); }
  function redrawAll() {
    if (!S.view || curMod() !== 'v2s_market_all') return;
    var b = S.view.querySelector('#mkAllBody'); if (!b) return;
    b.innerHTML = allBodyHtml();
  }
  function allClick(e) {
    var a = e.target.closest ? e.target.closest('[data-a]') : null; if (!a || !S.view.contains(a)) return;
    var k = a.getAttribute('data-a'), id = a.getAttribute('data-id');
    if (k === 'arow') openDrawer(id);
    else if (k === 'alane') { S.all.lane = a.getAttribute('data-lane'); loadAll(false); }
    else if (k === 'afopen') openFilter('all');
    else if (k === 'ago') { clearTimeout(S.qTimer); applyQ(S.view.querySelector('#mkq').value); }
    else if (k === 'aretry') loadAll(false);
    else if (k === 'amore') loadAll(true);
    else if (k === 'aclear') { S.all.status = 'all'; S.all.need = 'all'; S.all.author = 'all'; S.all.lane = 'all'; S.all.q = ''; S.showTest = false; var qi = S.view.querySelector('#mkq'); if (qi) qi.value = ''; loadAll(false); }
    else if (k === 'arm') { var kk = a.getAttribute('data-k'); if (kk === 'test') S.showTest = false; else S.all[kk] = 'all'; loadAll(false); }
    else if (k === 'reload') { var E = ep(); if (E) E.reload('market', redraw); }
  }

  // ------------------------------------------------------------------ ماذا يطلب الناس
  function srcBlock(key, title, ready, okHtml) {
    var st = stateOf(key), E = ep(), D = E && E.data && E.data[key];
    if (D && D.missing) return '<p class="v2d-none">' + esc(title === 'أرقام الطلب' ? 'أرقام الطلب غير متاحة بعد على المنصة' : 'طلبات التدريب غير متاحة بعد على المنصة') + '</p>';
    if (st === 'error') return '<div class="v2d-warn" role="alert">' + esc(title === 'أرقام الطلب' ? 'تعذّر جلب أرقام الطلب' : 'تعذّر جلب طلبات التدريب') + '<button type="button" class="v2d-btn2" data-a="dretry" data-src="' + key + '">أعد المحاولة</button></div>';
    if ((st === 'idle' || st === 'loading') && !D) return '<div class="v2s-mk-skrows"><i class="v2s-mk-sk"></i><i class="v2s-mk-sk"></i><i class="v2s-mk-sk"></i></div>';
    return okHtml();
  }
  function bars(items, cls) {
    return '<ul class="v2s-mk-bars ' + (cls || '') + '">' + items.map(function (i) {
      return '<li><div class="bl"><span>' + esc(i.label) + '</span><b>' + esc(i.countText) + '</b></div><div class="v2s-mk-bar"><i style="width:' + Math.max(3, i.pct) + '%"></i></div>' + (i.sub || '') + '</li>';
    }).join('') + '</ul>';
  }
  function drawDemand(v) {
    var E = ep(), ro = !M.canWrite();
    var dm = X.demand(E && E.data && E.data.marketDemand);
    var d = stateOf('marketDemand') === 'ready' ? dm : null;
    var head = '<div class="v2d-top">' + (d && d.brain ? '<p class="v2d-auto">' + BRAIN + '<span>' + esc(d.brain) + '</span></p>' : '') + '<button type="button" class="v2d-btn2" data-a="dreload">حدّث الأرقام</button></div>'
      + (d && d.platform ? '<p class="v2d-open-total">' + esc(d.platform) + '</p>' : '') + readOnlyLine();
    var needHtml = srcBlock('marketDemand', 'أرقام الطلب', true, function () {
      if (!d) return '<p class="v2d-none">أرقام الطلب غير متاحة بعد</p>';
      if (!d.byNeed.length) return '<p class="v2d-none">لا احتياجات مسجّلة بعد</p>';
      return bars(d.byNeed.map(function (n) {
        var f = [];
        if (n.zero !== undefined) f.push('<span class="' + (n.zero > 0 ? 'warn' : '') + '">' + esc(ar(n.zero)) + ' بلا عرض</span>');
        if (n.withOffers !== undefined) f.push('<span>' + esc(ar(n.withOffers)) + ' عليها عروض</span>');
        if (n.total !== undefined) f.push('<span>' + esc(ar(n.total)) + ' في المدة</span>');
        return { label: n.label, countText: n.countText + ' مفتوح', pct: n.pct, sub: f.length ? '<p class="v2s-mk-sub">' + f.join('') + '</p>' : '' };
      }));
    });
    var specHtml = srcBlock('marketDemand', 'أرقام الطلب', true, function () {
      if (!d) return '<p class="v2d-none">أرقام الطلب غير متاحة بعد</p>';
      if (!d.specs.items.length) return '<p class="v2d-none">لا تخصصات مسجّلة بعد</p>';
      return bars(d.specs.items, 'gold');
    });
    var crsHtml = srcBlock('marketDemand', 'أرقام الطلب', true, function () {
      if (!d) return '<p class="v2d-none">أرقام الطلب غير متاحة بعد</p>';
      if (!d.courses.length) return '<p class="v2d-none">لا طلب متكرر يكفي لاقتراح دورة بعد</p>';
      return (d.topBrain ? '<div class="v2d-brain">' + BRAIN + '<p>' + esc(d.topBrain) + '</p></div>' : '') + '<ul class="v2s-mk-crs">' + d.courses.map(function (c) {
        return '<li><div class="ch"><b>' + esc(c.title) + '</b><span class="v2s-mk-tag ' + (c.explicit ? 'ex' : '') + '">' + esc(c.originLabel) + '</span></div><p class="cn">' + esc(c.countText) + '</p>' + (c.reason ? '<p class="cr">' + esc(c.reason) + '</p>' : '')
          + (c.canCreate && !ro ? '<button type="button" class="v2d-btn2" data-a="course" data-title="' + esc(c.hint) + '">أنشئ الدورة</button>' : '') + '</li>';
      }).join('') + '</ul>';
    });
    var tr = X.training(stateOf('trainingInterests') === 'ready' ? (E.data.trainingInterests || null) : null);
    var trHtml = srcBlock('trainingInterests', 'طلبات التدريب', true, function () {
      if (!tr) return '<p class="v2d-none">طلبات التدريب غير متاحة بعد</p>';
      if (!tr.rows.length) return '<p class="v2d-none">لم يسجّل أحد اهتمامًا بالتدريب بعد</p>';
      var tb = '<div class="v2s-mk-tbw"><table class="v2s-mk-tb"><thead><tr><th>الاسم</th><th>الدورة المطلوبة</th><th>متى</th><th>اتصل</th></tr></thead><tbody>' + tr.rows.map(function (t) {
        return '<tr><td>' + esc(t.name || 'بلا اسم') + (t.email ? '<span class="v2s-mk-ltr sub">' + esc(t.email) + '</span>' : '') + '</td><td>' + (t.course ? esc(t.course) : '<span class="v2d-mute">لم يحدّد دورة</span>') + '</td><td>' + esc(t.when) + '</td><td>' + telLink(t.phone) + '</td></tr>';
      }).join('') + '</tbody></table></div>';
      var cards = '<ul class="v2s-mk-cards tr">' + tr.rows.map(function (t) {
        return '<li><div class="v2s-mk-card static"><b>' + esc(t.name || 'بلا اسم') + '</b><span class="cw">' + (t.course ? esc(t.course) : 'لم يحدّد دورة') + '</span><small>' + esc(t.when) + '</small>'
          + (telOf(t.phone) && !ro ? '<a class="v2d-btn1 call" href="tel:' + esc(telOf(t.phone)) + '">اتصل</a>' : (telOf(t.phone) ? '<span class="v2s-mk-ltr">' + esc(telOf(t.phone)) + '</span>' : '<span class="v2d-mute">بلا رقم</span>')) + '</div></li>';
      }).join('') + '</ul>';
      return (tr.noContact ? fine('لم يُسجَّل تواصل مع أحد منهم بعد') : '') + (tr.truncated ? fine('معروض ' + ar(tr.rows.length) + ' من ' + ar(tr.count)) : '') + tb + cards;
    });
    var trTitle = 'من طلب التدريب' + (tr ? ' (' + ar(tr.rows.length) + ')' : '');
    // مصدر «أرقام الطلب» واحد لثلاث بطاقات: إن فشل أو غاب يظهر تنبيه واحد فوقها، ولا تتكرر الرسالة في كل بطاقة.
    var dD = E && E.data && E.data.marketDemand, dBan = '', dCards;
    if (dD && dD.missing) dBan = '<p class="v2d-none">أرقام الطلب غير متاحة بعد على المنصة</p>';
    else if (stateOf('marketDemand') === 'error') dBan = '<div class="v2d-warn" role="alert">تعذّر جلب أرقام الطلب<button type="button" class="v2d-btn2" data-a="dretry" data-src="marketDemand">أعد المحاولة</button></div>';
    if (dBan) dCards = dBan;
    else dCards = '<div class="v2s-mk-grid">'
      + '<section class="v2s-mk-cardbox"><h2>الطلب حسب النوع</h2>' + needHtml + '</section>'
      + '<section class="v2s-mk-cardbox"><h2>' + esc(d ? d.specs.title : 'حسب التخصص') + '</h2>' + specHtml + '</section>'
      + '<section class="v2s-mk-cardbox wide"><h2>دورات يطلبها الناس</h2>' + crsHtml + '</section></div>';
    v.innerHTML = '<div class="v2d v2s-mk v2s-mk-dem" data-board="market-demand">' + head + dCards + '<div class="v2s-mk-grid">'
      + '<section class="v2s-mk-cardbox wide"><h2>' + esc(trTitle) + '</h2>' + trHtml + '</section></div></div>';
    wire(v);
  }

  // ------------------------------------------------------------------ نقطة الدخول
  function signature() {
    var A = S.all;
    return SOURCES.concat(['courses']).map(stateOf).join(',') + '|' + (S.rows.length);
  }
  function redraw() {
    if (!S.view || !isCurrent()) return;
    var m = curMod(); S.mod = m;
    if (m === 'market') drawBoard(S.view);
    else if (m === 'v2s_market_all') redrawAll();
    else if (m === 'v2s_market_demand') drawDemand(S.view);
    S.sig = signature();
    if (S.ov === 'drawer') drawDrawer();
  }
  function stopTimers() { clearInterval(S.poll); clearInterval(S.minute); S.poll = null; S.minute = null; }
  M._tick = function (nowOverride) {
    if (nowOverride) S.nowOverride = nowOverride;
    var now = nowMs();
    document.querySelectorAll('.v2s-mk [data-ts], #mkOv [data-ts]').forEach(function (el) {
      var txt = X.timerText(el.getAttribute('data-pre') || '', Number(el.getAttribute('data-ts')), now);
      if (txt && el.textContent !== txt) el.textContent = txt;
    });
  };
  M.render = function (mod, view) {
    var changed = S.mod !== mod;
    S.view = view; S.mod = mod;
    var E = ep();
    if (E && E.authed) {
      if (mod === 'market') E.ensure('market', redraw);
      if (mod === 'v2s_market_all') E.ensure('market', redraw);
      if (mod === 'v2s_market_demand') { E.ensure('marketDemand', redraw); E.ensure('trainingInterests', redraw); }
    }
    if (changed && S.ov) closeDrawer();
    // دخول القسم من شاشة تانية: لو آخر جلب أقدم من دقيقة ونص نعيد الجلب بهدوء (الصفوف القديمة تفضل ظاهرة لحد ما يوصل الجديد).
    if (changed && E && E.authed && (mod === 'market' || mod === 'v2s_market_all') && stateOf('market') === 'ready' && Date.now() - (S.mktAt || 0) > 90000) { S.mktAt = Date.now(); E.reload('market', redraw); }
    if (!S.mktAt) S.mktAt = Date.now();
    if (mod === 'v2s_market_all') drawAll(view);
    else if (mod === 'v2s_market_demand') drawDemand(view);
    else drawBoard(view);
    S.sig = signature();
    if (!S.poll) {
      S.poll = setInterval(function () {
        if (!isCurrent()) { stopTimers(); return; }
        var cs = stateOf('courses');
        if (cs !== S.courseSt) { S.courseSt = cs; var lk = document.getElementById('epModal'); if (lk && lk.getAttribute('data-link')) refreshLink(lk.getAttribute('data-link')); }
        if (signature() !== S.sig) { var m = curMod(); if (m === 'market' || m === 'v2s_market_demand') redraw(); else { S.sig = signature(); redrawAll(); } }
      }, 400);
    }
    if (!S.minute) S.minute = setInterval(function () { if (!isCurrent()) { stopTimers(); return; } M._tick(); }, 60000);
  };
  M._state = S;

  document.addEventListener('keydown', function (e) {
    if (e.key !== 'Escape') return;
    var m = document.getElementById('epModal');
    if (m && (m.classList.contains('v2s-mk-sh') || m.classList.contains('v2s-mk-cc'))) { if (!m.dataset.busy) window.closeModal(); return; }
    if (S.ov) { closeDrawer(); }
  });
  document.addEventListener('keydown', function (e) {
    if (e.key !== 'Tab' || !S.ov || document.getElementById('epModal')) return;
    var p = document.querySelector('#mkOv .v2s-mk-panel'); if (!p) return;
    var f = Array.prototype.slice.call(p.querySelectorAll('a[href],button:not([disabled]),input,textarea')).filter(function (n) { return n.offsetParent !== null; });
    if (!f.length) return;
    var first = f[0], last = f[f.length - 1], cur = document.activeElement;
    if (!p.contains(cur)) { e.preventDefault(); first.focus(); }
    else if (e.shiftKey && cur === first) { e.preventDefault(); last.focus(); }
    else if (!e.shiftKey && cur === last) { e.preventDefault(); first.focus(); }
  });

  (window.V2SEC = window.V2SEC || []).push({ owns: M.owns, render: M.render });
})();
