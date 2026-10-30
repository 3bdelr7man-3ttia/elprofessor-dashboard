/* ============================================================================
 * v2s/books.js — تبويب «الكتب والأعمال» (قسم «الكتب»): قائمة بممرّات قرار + صفحة عمل + أوراق التأكيد.
 * ⛔ لا منطق عمل هنا: الحالة والممرّ ونص المبيعات وسطر العقل والفرق قبل ⇒ بعد كلها من `v2-logic.js` (دوال `v2k*` النقية).
 * ⛔ المفتاح مقفول: الملف بيتحمّل دايمًا، لكنه ما بيرسم شيئًا إلا لو index.html نادى `V2SX.render('knowledge', …)`، وده ما بيحصل إلا
 *   والغلاف الجديد شغّال (`owns()` ⇒ `V2SHELL.on`). الغلاف مقفول أو دور غير الأدمن ⇒ الشاشة القديمة زي ما هي.
 * ⛔ ولا طلب شبكة من هنا غير: المحمّلات الموجودة (`/platform-knowledge`) · مسارات `/v2/*` (قراءة، أدمن بس) · مسارات الكتابة الأربعة الموجودة
 *   (قرار العمل · تعديل العمل · إضافة كتاب · استيراد مكتبة المراجع). مفيش مسار قرار جديد، ومفيش حركة فلوس هنا.
 * ⛔ مفيش حفظ في المتصفح: نص البحث وحالة الطيّ في الذاكرة بس.
 * ========================================================================== */
(function () {
  'use strict';
  var L = window.V2L;
  if (!L) return;
  var U = L.util, NA = L.NA;

  // سجلّ الأقسام: أي قسم يقدر يملك موديول قديم من غير ما يكتب خطّافًا جديدًا في index.html.
  var R = window.V2SX = window.V2SX || {
    mods: {},
    owns: function (m) { var e = this.mods[m]; return !!(e && e.owns()); },
    render: function (m, v) { return this.mods[m].render(v); }
  };

  var SESSION_AR = 'انتهت الجلسة — سجّل الدخول من جديد ثم جرّب';
  var FAIL_AR = 'تعذّر تنفيذ العملية';
  var NOTFOUND_AR = 'هذا العمل غير موجود';
  var S = { view: null, q: '', open: null, rejOpen: false, note: null, noteT: null, sheetBusy: false, saved: null, away: false, dirty: false,
            res: null, nowOverride: 0, retryT: null, minute: null, poll: null };

  function esc(s) { return String(s == null ? '' : s).replace(/[&<>"']/g, function (c) { return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]; }); }
  function host() { return window.V2_HOST || {}; }
  function ep() { return window.EP || null; }
  function img(name) { return 'v2/img/' + name + '.jpg'; }
  function now() { return S.nowOverride || Date.now(); }
  function q(sel, root) { return (root || document).querySelector(sel); }
  function qa(sel, root) { return Array.prototype.slice.call((root || document).querySelectorAll(sel)); }
  function arDigits(t) { return String(t).replace(/\d/g, function (d) { return '٠١٢٣٤٥٦٧٨٩'.charAt(+d); }); }
  var BRAIN = '<img class="v3-bav" src="' + img('brain-avatar') + '" alt="">';
  var LANE_TITLE = { review: 'ينتظر مراجعتك', noprice: 'بلا سعر', hiddenSold: 'مخفي وبيعت منه نسخ', live: 'ظاهر للناس', hidden: 'مخفي', unknown: 'لم تصل حالتها', rejected: 'مرفوض' };
  var DECISION = { review: 1, noprice: 1, hiddenSold: 1 };
  var OFFER_FORMS = ['عرض واحد', 'عرضان', 'عروض', 'عرضًا'];

  // ------------------------------------------------------------------ المصادر (كل مصدر يفشل لوحده، وفشله ما بيتحوّل لقائمة فاضية أبدًا)
  var SRC = {};
  var PATHS = {
    knowledge: '/platform-knowledge',
    revPending: '/v2/books/review?status=pending_review',
    revRejected: '/v2/books/review?status=rejected',
    prices: '/v2/prices/book',
    offers: '/v2/book-offers?status=all',
    store: '/v2/books/store',
    ads: '/v2/ads-ledger'
  };
  var LIST = ['knowledge', 'revPending', 'revRejected', 'prices', 'offers', 'store'];
  var STALE_MS = 60000;
  function srcOf(k) { return SRC[k] || (SRC[k] = { state: 'idle', data: null, status: 0, seq: 0, at: 0 }); }
  function load(k, force) {
    var s = srcOf(k), E = ep();
    if (!E || !E.api || !E.authed || !PATHS[k]) return;
    if (!force && s.state !== 'idle') return;
    if (s.state === 'idle') s.state = 'loading';          // أول جلب بس؛ التحديث بيسيب القديم ظاهرًا لحد ما يوصل الجديد
    var seq = ++s.seq;
    E.api(PATHS[k]).then(function (d) {
      if (seq !== s.seq) return;
      s.state = 'ready'; s.data = d; s.at = Date.now(); changed();
    }).catch(function (e) {
      if (seq !== s.seq) return;
      if (e && e.status === 401) return;
      s.state = e && e.status === 404 ? 'closed' : 'error'; s.status = (e && e.status) || 0; s.data = null; s.at = Date.now(); changed();
    });
  }
  function settled(k) { var st = srcOf(k).state; return st === 'ready' || st === 'error' || st === 'closed'; }
  function srcValue(k) {
    var s = srcOf(k);
    if (s.state === 'ready') return s.data;
    if (s.state === 'closed' && (k === 'prices' || k === 'store' || k === 'offers')) return 'closed';
    return null;
  }
  function ensureAll() {
    LIST.forEach(function (k) {
      var s = srcOf(k);
      if (s.state === 'idle') load(k, true);
      else if (s.at && Date.now() - s.at > STALE_MS) load(k, true);
    });
  }
  function reloadWorks() { ['knowledge', 'revPending', 'revRejected'].forEach(function (k) { load(k, true); }); }
  function epReload(keys) { var E = ep(); if (E && E.authed && E.reload) keys.forEach(function (k) { E.reload(k, null); }); }

  var redrawT = null;
  function changed() {
    try { if (window.V2SHELL && V2SHELL.on && V2SHELL.refresh) V2SHELL.refresh(); } catch (e) {}
    if (redrawT) return;
    redrawT = setTimeout(function () { redrawT = null; redraw(); }, 0);
  }
  function isCurrent() { return !!(host().current && R.owns(host().current()) && S.view && document.body.contains(S.view)); }
  function modalOpen() { return !!document.getElementById('epModal'); }
  // لا نعيد الرسم وتحت ورقة مفتوحة يكتب فيها المؤسس (المكتوب يضيع)؛ وبعد إغلاقها نلحق بما فاتنا.
  function redraw() {
    if (!S.view || !isCurrent()) return;
    if (modalOpen()) { S.dirty = true; armRetry(); return; }
    S.dirty = false;
    draw(S.view);
  }
  function armRetry() {
    if (S.retryT) return;
    S.retryT = setInterval(function () {
      if (modalOpen()) return;
      clearInterval(S.retryT); S.retryT = null;
      if (S.dirty) redraw();
    }, 400);
  }

  // ------------------------------------------------------------------ أجزاء مشتركة
  function personLink(name, email) {
    if (!email) return esc(name);
    return '<a class="v3-person" href="' + esc(L.sectionHash('people', 'person', email)) + '" data-person="' + esc(email) + '">' + esc(name) + '</a>';
  }
  function ownerHtml(r) {
    if (r.ownerNA) return 'صاحب العمل: <span class="bk-na">' + esc(NA) + '</span>';
    return 'صاحب العمل: ' + personLink(r.ownerName, r.ownerEmail);
  }
  function setNote(text) {
    S.note = text; clearTimeout(S.noteT);
    S.noteT = setTimeout(function () { S.note = null; redraw(); }, 12000);
  }
  function noteStrip() { return S.note ? '<div class="v3-ok" role="status">' + esc(S.note) + '</div>' : ''; }
  function warnStrip(labels) {
    if (!labels.length) return '';
    return '<div class="v3-warn" role="status">تعذّر جلب: ' + esc(labels.join(' · ')) + ' — ما يظهر ناقص، وليس معناه أنه لا شيء</div>';
  }
  function rowByKey(res, key) { return res ? res.rows.filter(function (r) { return r.key === key; })[0] || null : null; }
  function srcAll() {
    var o = {};
    LIST.forEach(function (k) { o[k] = srcValue(k); });
    return o;
  }
  function scrollNow() {
    var c = q('.content');
    return { c: c ? c.scrollTop : 0, w: window.scrollY || 0 };
  }
  function scrollTo(pos) {
    var c = q('.content');
    try { if (c) c.scrollTop = pos ? pos.c : 0; window.scrollTo(0, pos ? pos.w : 0); } catch (e) {}
  }

  // ------------------------------------------------------------------ أزرار القرار لكل نوع صف (نفس الأزرار في القائمة وفي صفحة العمل)
  var LABELS = { approve: 'اعتمد وانشر', reject: 'ارفض', show: 'أظهر للناس', hide: 'أخفِ عن الناس', edit: 'عدّل', priceNew: 'ضع سعرًا', priceEdit: 'عدّل الأسعار والظهور' };
  function actionsFor(r) {
    var a = { main: null, second: [] };
    function act(id, label) { return { a: id, label: label || LABELS[id] }; }
    if (r.kind === 'market') {
      if (r.status === 'review') {
        if (r.brain && r.brain.id === 'B1') { a.main = act('reject'); a.second = [act('approve')]; }
        else { a.main = act('approve'); a.second = [act('reject')]; }
      } else if (r.status === 'hidden') { a.main = act('show'); a.second = [act('edit')]; }
      else if (r.status === 'live') { a.second = [act('hide'), act('edit')]; }
    } else if (r.kind === 'store') {
      if (r.status === 'noprice') a.main = act('price', LABELS.priceNew);
      else if (r.status === 'hidden') a.main = act('price', LABELS.priceEdit);
      else a.second = [act('price', LABELS.priceEdit)];
    }
    return a;
  }
  function btn(a, cls, key) { return '<button type="button" class="' + cls + '" data-a="' + a.a + '" data-key="' + esc(key) + '">' + esc(a.label) + '</button>'; }

  // ------------------------------------------------------------------ بنود القائمة (مكوّن واحد بكثافتين)
  function pillsHtml(r) {
    return '<span class="bk-pills"><span class="bk-type">' + esc(r.typeText) + '</span><span class="bk-st st-' + r.status + '">' + esc(r.statusText) + '</span></span>';
  }
  function metaLine(r) {
    var parts = [ownerHtml(r)];
    if (r.kind === 'offer') { if (r.priceAmount != null) parts.push('السعر المقترح: ' + esc(r.priceText)); }
    else if (r.salesNA) parts.push('<span class="bk-na">' + esc(r.salesText) + '</span>');
    else if (r.salesText) parts.push(esc(r.salesText));
    return parts.join(' · ');
  }
  function brainLine(r) { return r.brain ? '<div class="v3-brain">' + BRAIN + '<p>' + esc(r.brain.text) + '</p></div>' : ''; }
  function decisionItem(r) {
    var late = r.brain && r.brain.id === 'B1';
    var act = actionsFor(r), acts = '';
    if (act.main) acts += btn(act.main, 'v3-btn1', r.key);
    if (r.status === 'review' && act.second[0]) acts += btn(act.second[0], 'v3-btn2', r.key);
    acts += '<button type="button" class="v3-link" data-a="open" data-key="' + esc(r.key) + '">التفاصيل</button>';
    var since = r.waitingSince != null ? '<time class="v3-time">' + esc(U.agoText(r.waitingSince, now())) + '</time>' : '';
    return '<article class="v3-t bk-item bk-dec tone-' + (late ? 'late' : 'wait') + '" data-key="' + esc(r.key) + '"><div class="v3-strip">' + pillsHtml(r) + since + '</div>'
      + '<div class="v3-body"><h3>' + esc(r.title) + '</h3><p class="v3-line">' + metaLine(r) + '</p>' + brainLine(r) + '<div class="bk-acts">' + acts + '</div></div></article>';
  }
  function compactItem(r) {
    return '<article class="bk-item bk-row" data-key="' + esc(r.key) + '"><div class="bk-main"><h3>' + esc(r.title) + '</h3><div class="bk-meta">' + pillsHtml(r) + '<span class="v3-line">' + metaLine(r) + '</span></div></div>'
      + '<button type="button" class="v3-btn2" data-a="open" data-key="' + esc(r.key) + '">افتح</button></article>';
  }

  // ------------------------------------------------------------------ الممرّات
  function laneHtml(key, ids, res) {
    var n = ids.length, partial = res.partial[key];
    var cnt = '<span class="v3-cnt"' + (partial ? ' title="العدد ناقص لأن بعض المصادر لم تصل"' : '') + '>' + esc(U.ar(n) + (partial ? '+' : '')) + '</span>';
    var rows = ids.map(function (k) { return rowByKey(res, k); }).filter(Boolean);
    var link = '';
    if (key === 'review' && res.offersWaiting > 0) {
      link = '<a class="v3-lnk bk-offlink" href="' + esc(L.sectionHash('books', 'offers')) + '" data-a="offers">و' + esc(U.U(res.offersWaiting, OFFER_FORMS)) + ' في «مراجعة العروض»</a>';
    }
    if (key === 'rejected') {
      var open = S.rejOpen;
      return '<section class="bk-lane" data-lane="rejected" id="bk-lane-rejected"><h2 class="v3-h2" tabindex="-1"><button type="button" class="bk-fold" data-a="fold" aria-expanded="' + open + '" aria-controls="bk-lane-rejected-body">'
        + '<span class="bk-ft">' + esc(LANE_TITLE.rejected) + '</span>' + cnt + '<span class="bk-fx">' + (open ? 'أخفِ' : 'اعرض') + '</span></button></h2>'
        + '<div class="bk-list" id="bk-lane-rejected-body"' + (open ? '' : ' hidden') + '>' + rows.map(compactItem).join('') + '</div></section>';
    }
    if (key === 'review' && !n) {
      return '<section class="bk-lane" data-lane="review" id="bk-lane-review"><h2 class="v3-h2" tabindex="-1">' + esc(LANE_TITLE.review) + '</h2><p class="v3-none bk-lnone">'
        + (partial ? 'أعمال السوق التي تنتظر المراجعة: ' + esc(NA) : 'لا أعمال من السوق تنتظر مراجعتك') + '</p>' + link + '</section>';
    }
    var body = DECISION[key] ? '<div class="bk-tgrid">' + rows.map(decisionItem).join('') + '</div>' : '<div class="bk-list">' + rows.map(compactItem).join('') + '</div>';
    return '<section class="bk-lane" data-lane="' + key + '" id="bk-lane-' + key + '"><h2 class="v3-h2" tabindex="-1">' + esc(LANE_TITLE[key]) + ' ' + cnt + '</h2>' + link + body + '</section>';
  }
  function lanesHtml(res) {
    var lanes = L.v2kSearch(res, S.q), out = '';
    L.v2kLanes.forEach(function (key) {
      var ids = lanes[key] || [];
      if (ids.length || (key === 'review' && (res.offersWaiting > 0 || res.partial.review) && !S.q)) out += laneHtml(key, ids, res);
    });
    if (!out && S.q) return '<p class="v3-none">لا أعمال بهذا الوصف</p><p class="bk-center"><button type="button" class="v3-link" data-a="clearq">امسح البحث</button></p>';
    return out;
  }

  function brainCard(res) {
    var sum = L.v2kBrainSummary(res);
    return '<section class="bk-brain" aria-label="العقل"><div class="bk-bt"><img class="v3-bav bk-av" src="' + img('brain-avatar') + '" alt=""><div class="bk-btx"><p class="bk-bsum">' + esc(sum.text) + '</p>'
      + (sum.action ? '<button type="button" class="v3-btn1" data-a="brain" data-lane="' + sum.action.lane + '">' + esc(sum.action.label) + '</button>' : '') + '</div></div>'
      + '<img class="bk-photo" src="' + img('books') + '" alt=""></section>';
  }
  function libraryLine() {
    return '<p class="bk-libline">مكتبة المراجع: ملفات تقرأ منها إجابات المنصة · <button type="button" class="v3-link" data-a="library">استورد ملفات</button></p>';
  }
  function retryBtn() { return '<button type="button" class="v3-btn2" data-a="retry">أعد المحاولة</button>'; }

  function drawList(v, res) {
    var total = res.rows.length;
    var onlyOffers = total === 0 && res.offersWaiting > 0;
    var html = '<div class="v3 v2s-books" data-board="works">' + noteStrip() + warnStrip(res.failed) + (res.storeClosed ? '<p class="v3-fine bk-closed">متجر الكتب لم يُفتح بعد، فتظهر هنا أعمال السوق وحدها.</p>' : '');
    html += brainCard(res);
    if (total === 0 && !onlyOffers) {
      html += res.failed.length
        ? '<div class="v3-empty"><b>لم يصل ما نعرضه بعد</b><p>تعذّر جلب بعض المصادر، فلا تعتبر الشاشة فارغة.</p>' + retryBtn() + '</div>'
        : '<div class="v3-empty"><b>لا أعمال بعد</b><p>يظهر هنا كل كتاب أو عمل يُضاف إلى المنصة.</p><button type="button" class="v3-btn1" data-a="add">أضف كتابًا</button></div>';
      html += libraryLine() + '</div>';
      v.innerHTML = html; wire(v); return;
    }
    if (total > 12) html += '<input type="search" id="bkSearch" class="bk-search" placeholder="ابحث بالعنوان أو باسم صاحب العمل" aria-label="ابحث في الأعمال" value="' + esc(S.q) + '" autocomplete="off">';
    html += '<div id="bkLanes">' + lanesHtml(res) + '</div>';
    html += '<p class="bk-addrow"><button type="button" class="v3-btn2" data-a="add">أضف كتابًا</button></p>' + libraryLine() + '</div>';
    v.innerHTML = html;
    wire(v);
  }

  // ------------------------------------------------------------------ صفحة العمل
  function factsFor(r, res) {
    var f = [];
    function put(label, html, plain) { f.push({ label: label, html: html, na: plain === NA }); }
    put('الحالة', '<span class="bk-st st-' + r.status + '">' + esc(r.statusText) + '</span>', r.status === 'unknown' ? NA : '');
    if (r.kind !== 'offer') {
      var sales = r.salesNA ? '<span class="bk-na">' + esc(r.salesText) + '</span>' : esc(r.salesText);
      put('المبيعات', sales + (r.salesSub ? '<span class="bk-sub">' + esc(r.salesSub) + '</span>' : ''), r.salesNA ? NA : '');
    }
    put(r.kind === 'offer' ? 'السعر المقترح' : 'السعر', esc(r.priceText), r.priceText === NA ? NA : '');
    put('اتفاقية البيع', esc(r.agreementText), r.agreementText === NA ? NA : '');
    if (r.kind === 'store' && r.catalogId) {
      var ad = adsText(r.catalogId);
      put('رصيد الإعلان', ad.html, ad.na ? NA : '');
    }
    if (r.kind === 'market') {
      put('الملف', r.hasFile === true ? 'مرفق' : (r.hasFile === false ? 'لا يوجد ملف' : '<span class="bk-na">' + esc(NA) + '</span>'), r.hasFile == null ? NA : '');
      put('أُضيف', r.createdText ? esc(r.createdText) : '<span class="bk-na">' + esc(NA) + '</span>', r.createdText ? '' : NA);
    }
    if (r.kind === 'offer') put('أُرسل للمراجعة', r.createdText ? esc(r.createdText) : '<span class="bk-na">' + esc(NA) + '</span>', r.createdText ? '' : NA);
    if (r.reviewNote) put('ملاحظة المراجعة', esc(r.reviewNote), '');
    put('رقم العمل', '<span class="bk-ref" dir="ltr">' + esc(r.slug || r.id) + '</span>', '');
    return f;
  }
  function adsText(catalogId) {
    var st = srcOf('ads').state;
    if (st === 'loading' || st === 'idle') return { html: '…جارٍ جلب الرصيد', na: false };
    if (st !== 'ready') return { html: '<span class="bk-na">' + esc(NA) + '</span>', na: true };
    var rows = L.v2AdsLedger(srcOf('ads').data, now()) || [];
    var row = rows.filter(function (x) { return x.id === catalogId; })[0];
    if (!row) return { html: 'لا رصيد إعلان', na: false };
    return { html: esc(row.balanceText) + '<span class="bk-sub">آخر حركة: ' + esc(row.last) + '</span><a class="v3-lnk" href="#s/money/ads" data-a="ads">إعلانات الأعمال</a>', na: false };
  }
  function workPage(r, res) {
    var act = actionsFor(r);
    var facts = factsFor(r, res).map(function (x) { return '<div><dt>' + esc(x.label) + '</dt><dd' + (x.na ? ' class="na"' : '') + '>' + x.html + '</dd></div>'; }).join('');
    var panel = '';
    if (!act.main) panel += '<p class="bk-lead">لا شيء ينتظرك في هذا العمل.</p>';
    panel += brainLine(r);
    if (act.main) panel += btn(act.main, 'v3-btn1 bk-mainbtn', r.key);
    panel += act.second.map(function (a) { return btn(a, 'v3-btn2', r.key); }).join('');
    if (r.kind === 'store') panel += '<p class="v3-fine">الأسعار وظهور الكتاب للناس تُعدَّل من «الفلوس › الأسعار» فقط.</p>';
    var dock = act.main ? '<div class="bk-dock" id="bkDock">' + btn(act.main, 'v3-btn1', r.key) + '</div>' : '';
    return '<div class="v3 v2s-books" data-board="work"' + (act.main ? ' data-dock="1"' : '') + '>' + noteStrip()
      + '<button type="button" class="v3-link bk-back" data-a="back">→ كل الأعمال</button>'
      + '<div class="bk-work"><header class="bk-whead">' + pillsHtml(r) + '<h2>' + esc(r.title) + '</h2><p class="v3-line">' + ownerHtml(r) + '</p></header>'
      + '<dl class="bk-facts">' + facts + '</dl><aside class="v3-card bk-panel">' + panel + '</aside></div>' + dock + '</div>';
  }
  function missingPage() {
    return '<div class="v3 v2s-books" data-board="work">' + noteStrip() + '<div class="v3-empty"><b>' + esc(NOTFOUND_AR) + '</b><button type="button" class="v3-btn2" data-a="back">كل الأعمال</button></div></div>';
  }

  // ------------------------------------------------------------------ الرسم
  function draw(v) {
    var focusSearch = document.activeElement && document.activeElement.id === 'bkSearch';
    var caret = focusSearch ? document.activeElement.selectionStart : 0;
    var all = LIST.every(settled);
    if (!all) {
      v.innerHTML = '<div class="v3 v2s-books" data-board="works">' + noteStrip() + '<div class="v3-empty"><b>…جارٍ جلب الكتب والأعمال</b></div></div>';
      S.res = null; return;
    }
    var res = L.v2kWorks(srcAll(), now());
    S.res = res;
    if (!res) {
      v.innerHTML = '<div class="v3 v2s-books" data-board="works">' + noteStrip() + '<div class="v3-empty"><b>الكتب والأعمال: غير متاح بعد</b><p>تعذّر الجلب الآن، فلا تعتبر الشاشة فارغة.</p>' + retryBtn() + '</div></div>';
      wire(v); return;
    }
    if (S.open) {
      var row = rowByKey(res, S.open);
      if (row && row.kind === 'store' && row.catalogId) load('ads', false);
      v.innerHTML = row ? workPage(row, res) : missingPage();
      wire(v);
      if (!row) S.open = null;
      return;
    }
    drawList(v, res);
    if (focusSearch) { var i = q('#bkSearch', v); if (i) { i.focus(); try { i.setSelectionRange(caret, caret); } catch (e) {} } }
  }

  // ------------------------------------------------------------------ التنقّل بين القائمة وصفحة العمل (زر الرجوع يرجع للقائمة)
  function openWork(key) {
    S.saved = scrollNow();
    S.open = key;
    try { history.pushState({ v2sBooks: key }, '', location.hash); } catch (e) {}
    redraw(); scrollTo(null);
  }
  function closeWork() {
    var st = null;
    try { st = history.state; } catch (e) {}
    if (st && st.v2sBooks) { try { history.back(); return; } catch (e2) {} }
    S.open = null; redraw(); scrollTo(S.saved);
  }
  window.addEventListener('popstate', function (e) {
    if (!(host().current && R.owns(host().current()) && S.view && document.body.contains(S.view))) return;
    var key = e.state && e.state.v2sBooks;
    var was = S.open;
    S.open = key && rowByKey(S.res, key) ? key : null;
    redraw();
    if (!S.open && was) scrollTo(S.saved); else if (S.open) scrollTo(null);
  });

  // ------------------------------------------------------------------ الأوراق
  function dockHide(on) { var d = document.getElementById('bkDock'); if (d) d.hidden = !!on; }
  function openSheet(title, html) {
    if (typeof window.openModal !== 'function') return null;
    dockHide(true);
    var s = window.openModal(title, '<div class="v3m v2s-bm">' + html + '</div>');
    var x = q('[data-x]', s);
    if (x) x.onclick = function () { if (!s.dataset.busy) closeSheet(); };
    s.onclick = function (e) { if (e.target === s && !s.dataset.busy) closeSheet(); };
    return s;
  }
  function closeSheet() {
    window.closeModal(); S.sheetBusy = false; dockHide(false);
    if (S.dirty) redraw();
  }
  function errText(e, mode) {
    if (e && e.status === 401) return SESSION_AR;
    var d = (e && e.data) || {};
    var msg = typeof d.error === 'string' && d.error ? arDigits(d.error) : '';
    if (e && e.status === 404 && mode !== 'add' && mode !== 'library') return NOTFOUND_AR;
    if (mode === 'edit') return (e && (e.status === 400 || e.status === 422) && msg) ? 'رفضت المنصة هذا التعديل: ' + msg : FAIL_AR;
    return msg || FAIL_AR;
  }
  function showErr(s, msg) { var e = q('#bkerr', s); if (e) e.innerHTML = msg ? '<div class="v3-err">' + esc(msg) + '</div>' : ''; }
  function lockSheet(s, on, go, busyText, idleText) {
    if (on) { s.dataset.busy = '1'; S.sheetBusy = true; } else { delete s.dataset.busy; S.sheetBusy = false; }
    qa('button, input, textarea, select', s).forEach(function (el) { if (!el.hasAttribute('data-x')) el.disabled = !!on; });
    if (go) go.textContent = on ? busyText : idleText;
  }
  // ورقة بخطوة واحدة: حقول اختيارية ثم زرّ التنفيذ. o: {title, html, btn, busy, mode, collect(s)→{ok,payload,error}, send(payload), onOk(res, s), onFail(e)}
  function formSheet(o) {
    var s = openSheet(o.title, '<div class="bk-sbody">' + o.html + '<div id="bkerr" role="alert"></div><div class="acts"><button type="button" class="btn btn-primary" id="bk_go">' + esc(o.btn) + '</button>'
      + '<button type="button" class="btn btn-ghost" id="bk_x">' + esc(o.cancel || 'إلغاء') + '</button></div></div>');
    if (!s) return null;
    S.sheetBusy = false;
    var go = q('#bk_go', s);
    q('#bk_x', s).onclick = function () { if (!s.dataset.busy) closeSheet(); };
    go.onclick = function () {
      if (s.dataset.busy) return;
      var c = o.collect ? o.collect(s) : { ok: true, payload: null };
      if (!c.ok) { showErr(s, c.error); return; }
      showErr(s, ''); lockSheet(s, true, go, o.busy || 'جارٍ التنفيذ…', o.btn);
      Promise.resolve(o.send(c.payload)).then(function (res) {
        lockSheet(s, false, go, '', o.btn);
        o.onOk(res || {}, s);
      }).catch(function (e) {
        lockSheet(s, false, go, '', o.btn);
        showErr(s, errText(e, o.mode));
        if (o.onFail) o.onFail(e);
      });
    };
    return s;
  }
  function diffTable(lines) {
    return '<table class="v3-diff"><thead><tr><th>البند</th><th>الآن</th><th>بعد التعديل</th></tr></thead><tbody>' + lines.map(function (l) {
      return '<tr><td>' + esc(l.label) + '</td><td>' + esc(l.from) + '</td><td><b>' + esc(l.to) + '</b></td></tr>'; }).join('') + '</tbody></table>';
  }

  // —— قرار عمل في المراجعة
  function afterDecision(text) {
    setNote(text); reloadWorks(); epReload(['inbox']);
  }
  function decide(r, body, okText) {
    var E = ep();
    return E.api('/platform-knowledge/' + encodeURIComponent(r.id) + '/decide', { method: 'POST', body: body }).then(function (res) { afterDecision(okText); return res; });
  }
  function openApprove(r) {
    formSheet({
      title: 'اعتماد: ' + r.title, btn: 'اعتمد وانشر', busy: 'جارٍ الاعتماد…', mode: 'decide',
      html: '<p class="mc-lead">سيظهر «' + esc(r.title) + '» للناس في السوق، ويصل إلى صاحب العمل بريد بالنتيجة.</p>',
      send: function () { return decide(r, { decision: 'approve', admin_note: '' }, 'اعتُمد «' + r.title + '» وظهر للناس'); },
      onOk: function () { closeSheet(); redraw(); },
      onFail: function (e) { if (e && e.status === 409) reloadWorks(); }
    });
  }
  function openReject(r) {
    var pre = r.brain && r.brain.id === 'B1' ? 'أرفق ملف العمل ثم أرسله للمراجعة من جديد.' : '';
    formSheet({
      title: 'رفض: ' + r.title, btn: 'أرسل الرفض', busy: 'جارٍ الرفض…', mode: 'decide',
      html: '<div class="fld"><label for="bk_reason">سبب الرفض (يصل إلى صاحب العمل)</label><textarea id="bk_reason" rows="3" maxlength="2000">' + esc(pre) + '</textarea></div>',
      collect: function (s) {
        var t = (q('#bk_reason', s).value || '').trim();
        return t ? { ok: true, payload: t } : { ok: false, error: 'اكتب سبب الرفض، فهو يصل إلى صاحب العمل' };
      },
      send: function (t) { return decide(r, { decision: 'reject', admin_note: t }, 'رُفض «' + r.title + '»، ووصل السبب إلى صاحب العمل'); },
      onOk: function () { closeSheet(); redraw(); },
      onFail: function (e) { if (e && e.status === 409) reloadWorks(); }
    });
  }
  // —— إظهار وإخفاء
  function setActive(r, on, okText) {
    return ep().api('/platform-knowledge/' + encodeURIComponent(r.id), { method: 'PUT', body: { is_active: on } }).then(function (res) { setNote(okText); load('knowledge', true); return res; });
  }
  function openShow(r) {
    formSheet({
      title: 'إظهار: ' + r.title, btn: 'أظهر للناس', busy: 'جارٍ الحفظ…', mode: 'item',
      html: '<p class="mc-lead">سيظهر «' + esc(r.title) + '» للناس في السوق.</p>',
      send: function () { return setActive(r, true, 'ظهر «' + r.title + '» للناس'); },
      onOk: function () { closeSheet(); redraw(); },
      onFail: function (e) { if (e && e.status === 404) load('knowledge', true); }
    });
  }
  function openHide(r) {
    var warn = L.v2kHideWarning(r);
    formSheet({
      title: 'إخفاء: ' + r.title, btn: 'أخفِ عن الناس', busy: 'جارٍ الحفظ…', mode: 'item',
      html: '<p class="mc-lead">لن يظهر «' + esc(r.title) + '» للناس في السوق.</p>' + (warn ? '<div class="v3-warn">' + esc(warn) + '</div>' : ''),
      send: function () { return setActive(r, false, 'أُخفي «' + r.title + '» عن الناس'); },
      onOk: function () { closeSheet(); redraw(); },
      onFail: function (e) { if (e && e.status === 404) load('knowledge', true); }
    });
  }

  // —— تعديل عمل من السوق: خطوتان (النموذج ثم «راجع التغيير» قبل ⇒ بعد ثم «أكّد»)
  function amountField(n) { return n == null ? '' : String(n); }
  function openEdit(r) {
    var form = '<div class="fld"><label for="bk_t">العنوان</label><input id="bk_t" type="text" maxlength="300" autocomplete="off" value="' + esc(r.title) + '"></div>';
    if (r.forSale) {
      form += '<div class="fld"><label for="bk_p">السعر (' + esc(U.curLong(r.priceCurrency)) + ')</label><input id="bk_p" type="text" inputmode="decimal" dir="ltr" autocomplete="off" value="' + esc(amountField(r.priceAmount)) + '">'
        + '<p class="v3-fine">سعر أعمال السوق يُعدَّل من هنا إلى أن تنتقل إلى «الفلوس › الأسعار».</p></div>'
        + '<label class="tg v3-togg"><input type="checkbox" id="bk_b"' + (r.bid ? ' checked' : '') + '> يسمح للأعضاء بأن يعرضوا سعرًا («اعرض سعرك»)</label>';
    }
    var s = openSheet('تعديل: ' + r.title, '<div id="bk_s1">' + form + '<div id="bkerr" role="alert"></div><div class="acts"><button type="button" class="btn btn-primary" id="bk_rev">راجع التغيير</button>'
      + '<button type="button" class="btn btn-ghost" id="bk_x">إلغاء</button></div></div><div id="bk_s2" hidden></div>');
    if (!s) return;
    S.sheetBusy = false;
    var s1 = q('#bk_s1', s), s2 = q('#bk_s2', s);
    q('#bk_x', s).onclick = function () { if (!s.dataset.busy) closeSheet(); };
    q('#bk_rev', s).onclick = function () {
      var d = L.v2kEditDiff(r, { title: q('#bk_t', s).value, priceText: r.forSale ? q('#bk_p', s).value : '', bid: r.forSale ? !!q('#bk_b', s).checked : false });
      if (!d.ok) { showErr(s, d.error); return; }
      if (!d.changed) { showErr(s, 'لم تغيّر أي شيء'); return; }
      var extra = '';
      if (d.body.price_egp !== undefined && r.sold > 0) extra += '<p class="v3-fine">السعر الجديد يسري على المشترين القادمين فقط.</p>';
      if (d.body.price_egp !== undefined && r.legacySplit === true && r.platformPct != null) extra += '<p class="v3-fine">ويبقى البيع بالنسبة القديمة: المنصة ' + esc(U.ar(r.platformPct)) + '٪.</p>';
      s1.hidden = true; s2.hidden = false;
      s2.innerHTML = '<p class="mc-lead">ستغيّر «' + esc(r.title) + '». راجع ما سيتغير:</p>' + diffTable(d.lines) + extra + '<div id="bkerr2" role="alert"></div>'
        + '<div class="acts"><button type="button" class="btn btn-primary" id="bk_go">أكّد التعديل</button><button type="button" class="btn btn-ghost" id="bk_back">رجوع للتعديل</button></div>';
      var go = q('#bk_go', s), back = q('#bk_back', s), err2 = q('#bkerr2', s);
      back.onclick = function () { if (s.dataset.busy) return; s2.hidden = true; s1.hidden = false; };
      go.onclick = function () {
        if (s.dataset.busy) return;
        err2.innerHTML = ''; lockSheet(s, true, go, 'جارٍ الحفظ…', 'أكّد التعديل');
        ep().api('/platform-knowledge/' + encodeURIComponent(r.id), { method: 'PUT', body: d.body }).then(function () {
          lockSheet(s, false, go, '', 'أكّد التعديل'); closeSheet(); setNote('حُفظ «' + (d.body.title || r.title) + '»'); load('knowledge', true); redraw();
        }).catch(function (e) {
          lockSheet(s, false, go, '', 'أكّد التعديل');
          err2.innerHTML = '<div class="v3-err">' + esc(errText(e, 'edit')) + '</div>';
          if (e && e.status === 404) load('knowledge', true);
        });
      };
    };
  }

  // —— «أضف كتابًا»
  function openAdd() {
    var f = '<p class="mc-lead">يُضاف الكتاب إلى أعمال السوق على المنصة. كتب المتجر تصل من عروض الأعضاء بعد مراجعتها.</p>'
      + '<div class="fld"><label for="bk_at">عنوان الكتاب</label><input id="bk_at" type="text" maxlength="300" autocomplete="off"></div>'
      + '<div class="fld"><label for="bk_aa">اسم المؤلف أو الجهة</label><input id="bk_aa" type="text" maxlength="200" autocomplete="off"></div>'
      + '<div class="fld"><label for="bk_ad">وصف قصير يظهر مع الكتاب</label><textarea id="bk_ad" rows="3" maxlength="2000"></textarea></div>'
      + '<div class="fld"><label for="bk_ap">السعر</label><input id="bk_ap" type="text" inputmode="decimal" dir="ltr" autocomplete="off"><p class="v3-fine">اتركه فارغًا ليكون مجانيًا للجميع</p></div>'
      + '<div class="fld"><label for="bk_ac">العملة</label><select id="bk_ac"><option value="EGP">جنيه مصري</option><option value="USD">دولار أمريكي</option></select></div>'
      + '<div class="fld"><label for="bk_af">رابط ملف الكتاب</label><input id="bk_af" type="text" dir="ltr" autocomplete="off" placeholder="https://"></div>'
      + '<div class="fld"><label for="bk_acv">رابط صورة الغلاف</label><input id="bk_acv" type="text" dir="ltr" autocomplete="off" placeholder="https://"></div>'
      + '<label class="tg v3-togg"><input type="checkbox" id="bk_aact" checked> ظاهر للناس فور إضافته</label>';
    formSheet({
      title: 'أضف كتابًا إلى السوق', btn: 'أضف الكتاب', busy: 'جارٍ الإضافة…', mode: 'add', html: f,
      collect: function (s) {
        var d = L.v2kAddBook({ title: q('#bk_at', s).value, author: q('#bk_aa', s).value, description: q('#bk_ad', s).value, priceText: q('#bk_ap', s).value,
                               currency: q('#bk_ac', s).value, fileUrl: q('#bk_af', s).value, coverUrl: q('#bk_acv', s).value, active: !!q('#bk_aact', s).checked });
        return d.ok ? { ok: true, payload: d.body } : { ok: false, error: d.error };
      },
      send: function (body) { return ep().api('/platform-books', { method: 'POST', body: body }).then(function (res) { return { res: res, title: body.title }; }); },
      onOk: function (r) { closeSheet(); setNote('أُضيف «' + r.title + '» إلى السوق'); load('knowledge', true); redraw(); }
    });
  }

  // —— مكتبة المراجع
  var CATS = [['memo_template', 'صيغ ونماذج'], ['law', 'قوانين وتشريعات'], ['ruling', 'أحكام'], ['custom', 'أخرى']];
  function openLibrary() {
    var f = '<p class="mc-lead">ملفات تقرأ منها إجابات المنصة ومحرّر المذكرات، ولا تُعرض للبيع. يُستورد حتى ' + U.ar(40) + ' ملفًا في كل مرة. الملفات المصوّرة (صور صفحات) لا تُقرأ بعد وتُتخطى. '
      + 'يلزم ربط حساب Google Drive من المنصة مرة واحدة قبل أول استيراد.</p>'
      + '<div class="fld"><label for="bk_lf">رابط المجلد في Google Drive</label><input id="bk_lf" type="text" dir="ltr" autocomplete="off" placeholder="الصق رابط المجلد"></div>'
      + '<div class="fld"><label for="bk_lc">نوع الملفات</label><select id="bk_lc">' + CATS.map(function (c) { return '<option value="' + c[0] + '">' + esc(c[1]) + '</option>'; }).join('') + '</select></div>';
    formSheet({
      title: 'استيراد إلى مكتبة المراجع', btn: 'استورد', busy: 'جارٍ الاستيراد… قد يستغرق دقيقة', mode: 'library', html: f,
      collect: function (s) {
        var id = L.v2kFolderId(q('#bk_lf', s).value);
        return id ? { ok: true, payload: { folder_id: id, category: q('#bk_lc', s).value, max_files: 40 } } : { ok: false, error: 'الصق رابط مجلد من Google Drive' };
      },
      send: function (body) { return ep().api('/platform-library/ingest-folder', { method: 'POST', body: body }); },
      onOk: function (res, s) {
        var ing = typeof res.ingested === 'number' ? res.ingested : null, fnd = typeof res.found === 'number' ? res.found : null;
        var text = ing != null && fnd != null ? 'استُورد ' + U.ar(ing) + ' من ' + U.ar(fnd) + ' ملفًا' : (ing != null ? 'استُورد ' + U.ar(ing) + ' ملفًا' : 'تمّ الاستيراد، وعدد الملفات: ' + NA);
        var b = q('.bk-sbody', s);
        b.innerHTML = '<p class="mc-lead bk-done">' + esc(text) + '</p><div class="acts"><button type="button" class="btn btn-primary" id="bk_done">تم</button></div>';
        q('#bk_done', s).onclick = function () { closeSheet(); };
      }
    });
  }

  // ------------------------------------------------------------------ ربط الأحداث
  function go2(sec, tab) { if (host().openSection) host().openSection(sec, tab); }
  function wire(v) {
    var root = q('.v2s-books', v) || v;
    var search = q('#bkSearch', v);
    if (search) {
      search.addEventListener('input', function () {
        S.q = search.value;
        var box = q('#bkLanes', v);
        if (box && S.res) box.innerHTML = lanesHtml(S.res);
      });
    }
    root.addEventListener('click', function (e) {
      var el = e.target && e.target.closest ? e.target.closest('[data-a]') : null;
      if (!el || !root.contains(el) || el.getAttribute('data-person') != null) return;
      var a = el.getAttribute('data-a'), key = el.getAttribute('data-key'), r = key ? rowByKey(S.res, key) : null;
      if (el.tagName === 'A') e.preventDefault();
      if (a === 'open' && r) return openWork(r.key);
      if (a === 'back') return closeWork();
      if (a === 'approve' && r) return openApprove(r);
      if (a === 'reject' && r) return openReject(r);
      if (a === 'show' && r) return openShow(r);
      if (a === 'hide' && r) return openHide(r);
      if (a === 'edit' && r) return openEdit(r);
      if (a === 'price') return go2('money', 'prices');
      if (a === 'ads') return go2('money', 'ads');
      if (a === 'offers') return go2('books', 'offers');
      if (a === 'add') return openAdd();
      if (a === 'library') return openLibrary();
      if (a === 'retry') { LIST.forEach(function (k) { if (srcOf(k).state === 'error' || srcOf(k).state === 'closed') load(k, true); }); return; }
      if (a === 'clearq') { S.q = ''; var s2 = q('#bkSearch', v); if (s2) s2.value = ''; var b2 = q('#bkLanes', v); if (b2 && S.res) b2.innerHTML = lanesHtml(S.res); return; }
      if (a === 'fold') { S.rejOpen = !S.rejOpen; var b3 = q('#bkLanes', v); if (b3 && S.res) b3.innerHTML = lanesHtml(S.res); var fb = q('.bk-fold', v); if (fb) fb.focus(); return; }
      if (a === 'brain') {
        var lane = q('#bk-lane-' + el.getAttribute('data-lane'), v);
        if (lane) { lane.scrollIntoView({ block: 'start' }); var h = q('h2', lane); if (h) { try { h.focus({ preventScroll: true }); } catch (e2) { h.focus(); } } }
      }
    });
  }

  // ------------------------------------------------------------------ نقطة الدخول
  function render(v) {
    if (S.away) { S.open = null; S.q = ''; S.rejOpen = false; S.away = false; }
    S.view = v;
    ensureAll();
    redraw();
    if (!S.poll) {
      S.poll = setInterval(function () {
        var cur = host().current && host().current();
        if (!(cur && R.owns(cur))) S.away = true;
        if (!modalOpen()) dockHide(false);
      }, 500);
    }
    if (!S.minute) S.minute = setInterval(function () { if (isCurrent() && !modalOpen()) redraw(); }, 60000);
  }
  R.mods.knowledge = {
    owns: function () { return !!(window.V2SHELL && V2SHELL.on); },
    render: render,
    summary: function () { return L.v2kSummary(S.res); },
    library: openLibrary
  };
  window.V2SX_BOOKS = { _state: S, _src: SRC, _tick: function (t) { S.nowOverride = t || 0; redraw(); } };
})();
