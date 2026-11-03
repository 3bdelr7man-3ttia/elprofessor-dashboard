/* ============================================================================
 * v2s/books.js — تبويب «الكتب» (قسم «الكتب»): قائمة بممرّات قرار + صفحة عمل + أوراق التأكيد.
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
  // سجلّ الأقسام الموحّد (v2s/_registry.js): index.html يسأل V2SEC.owner(mod) فقط.
  (window.V2SEC = window.V2SEC || {}).books = { owns: function (m) { return R.owns(m); }, render: function (m, v) { return R.render(m, v); } };

  var SESSION_AR = 'انتهت الجلسة — سجّل الدخول من جديد ثم جرّب';
  var FAIL_AR = 'تعذّر تنفيذ العملية';
  var NOTFOUND_AR = 'هذا العمل غير موجود';
  var S = { view: null, q: '', open: null, rejOpen: false, note: null, noteT: null, sheetBusy: false, saved: null, away: false, dirty: false,
            res: null, retryT: null, minute: null, poll: null, hashFn: null };

  function esc(s) { return String(s == null ? '' : s).replace(/[&<>"']/g, function (c) { return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]; }); }
  function host() { return window.V2_HOST || {}; }
  function ep() { return window.EP || null; }
  function img(name) { return 'v2/img/' + name + '.jpg'; }
  function now() { return Date.now(); }
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
  var STALE_MS = 60000, LATE_MS = 8000;
  // المصادر التي تحسم رسم القائمة؛ الباقي يلحق بها بلا حجب
  var CORE = ['knowledge', 'prices', 'offers'];
  var LATE_LABEL = { revPending: 'حالة المراجعة', revRejected: 'حالة المراجعة', store: 'بيانات المتجر' };
  function srcOf(k) { return SRC[k] || (SRC[k] = { state: 'idle', data: null, status: 0, seq: 0, at: 0 }); }
  function load(k, force) {
    var s = srcOf(k), E = ep();
    if (!E || !E.api || !E.authed || !PATHS[k]) return;
    if (!force && s.state !== 'idle') return;
    if (s.state === 'idle') s.state = 'loading';          // أول جلب بس؛ التحديث بيسيب القديم ظاهرًا لحد ما يوصل الجديد
    var seq = ++s.seq;
    if (s.state === 'loading') {                          // مصدر متأخر لا يحجب الشاشة: بعد ٨ ثوانٍ يصير «غير متاح بعد» وإن وصل لاحقًا يحلّ محلّه
      setTimeout(function () { if (seq === s.seq && s.state === 'loading') { s.state = 'error'; s.status = 0; s.data = null; s.at = Date.now(); changed(); } }, LATE_MS);
    }
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
    return '<div class="v3-warn" role="status">تعذّر جلب: ' + esc(labels.join('، ')) + ' — ما يظهر ناقص، وليس معناه أنه لا شيء</div>';
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
    return parts.join('، ');
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
    var html = '<div class="v3 v2s-books" data-board="works">' + noteStrip() + warnStrip(res.failed) + (res.pending ? '<p class="v3-fine bk-pending" role="status">…جارٍ جلب بقية البيانات</p>' : '') + (res.storeClosed ? '<p class="v3-fine bk-closed">متجر الكتب لم يُفتح بعد، فتظهر هنا أعمال السوق وحدها.</p>' : '');
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
    var all = CORE.every(settled);
    if (!all) {
      v.innerHTML = '<div class="v3 v2s-books" data-board="works">' + noteStrip() + '<div class="v3-empty"><b>…جارٍ جلب الكتب</b></div></div>';
      S.res = null; return;
    }
    var res = L.v2kWorks(srcAll(), now());
    var late = LIST.filter(function (k) { return !settled(k); });
    if (res && late.length) {                              // ما لم يصل بعد ليس «تعذّر»؛ يُذكر كجلب جارٍ ويلحق بالرسم حين يصل
      var lateNames = late.map(function (k) { return LATE_LABEL[k]; });
      res.failed = res.failed.filter(function (f) { return lateNames.indexOf(f) < 0; });
      if (!res.rows.length) res = { loadingOnly: true };
    }
    if (res && res.loadingOnly) {
      v.innerHTML = '<div class="v3 v2s-books" data-board="works">' + noteStrip() + '<div class="v3-empty"><b>…جارٍ جلب الكتب</b></div></div>';
      S.res = null; return;
    }
    S.res = res;
    if (res) res.pending = late.length > 0;
    if (!res) {
      v.innerHTML = '<div class="v3 v2s-books" data-board="works">' + noteStrip() + '<div class="v3-empty"><b>الكتب: غير متاح بعد</b><p>تعذّر الوصول إلى هذه البيانات الآن، فلا تعتبر الشاشة فارغة.</p>' + retryBtn() + '</div></div>';
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
      + '<button type="button" class="btn btn-ghost" id="bk_x">' + esc(o.cancel || 'رجوع') + '</button></div></div>');
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
      + '<button type="button" class="btn btn-ghost" id="bk_x">رجوع</button></div></div><div id="bk_s2" hidden></div>');
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
      + 'يلزم ربط حساب جوجل درايف من المنصة مرة واحدة قبل أول استيراد.</p>'
      + '<div class="fld"><label for="bk_lf">رابط المجلد في جوجل درايف</label><input id="bk_lf" type="text" dir="ltr" autocomplete="off" placeholder="الصق رابط المجلد"></div>'
      + '<div class="fld"><label for="bk_lc">نوع الملفات</label><select id="bk_lc">' + CATS.map(function (c) { return '<option value="' + c[0] + '">' + esc(c[1]) + '</option>'; }).join('') + '</select></div>';
    formSheet({
      title: 'استيراد إلى مكتبة المراجع', btn: 'استورد', busy: 'جارٍ الاستيراد… قد يستغرق دقيقة', mode: 'library', html: f,
      collect: function (s) {
        var id = L.v2kFolderId(q('#bk_lf', s).value);
        return id ? { ok: true, payload: { folder_id: id, category: q('#bk_lc', s).value, max_files: 40 } } : { ok: false, error: 'الصق رابط مجلد من جوجل درايف' };
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
    startTimers();
  }
  // المؤقّتات تعيش ما دام التبويب حاضرًا؛ عند مغادرته (تغيّر الرابط) تتوقف كلها وتبدأ من جديد مع أول رسم.
  function leftTab() {
    var cur = host().current && host().current();
    return !(cur && R.owns(cur));
  }
  function checkAway() {
    if (!S.minute && !S.retryT) return;
    if (leftTab()) stopTimers();
  }
  function stopTimers() {
    S.away = true;
    if (S.minute) { clearInterval(S.minute); S.minute = null; }
    if (S.retryT) { clearInterval(S.retryT); S.retryT = null; }
    if (S.hashFn) { window.removeEventListener('hashchange', S.hashFn); window.removeEventListener('popstate', S.hashFn); S.hashFn = null; }
  }
  function startTimers() {
    if (!S.minute) S.minute = setInterval(function () { if (leftTab()) { stopTimers(); return; } if (isCurrent() && !modalOpen()) redraw(); }, 60000);
    if (!S.hashFn) {
      S.hashFn = function () { setTimeout(function () { checkAway(); if (!modalOpen()) dockHide(false); }, 0); };
      window.addEventListener('hashchange', S.hashFn); window.addEventListener('popstate', S.hashFn);
    }
  }
  // ============================================================================================================================
  // «كتبنا» — تبويب أعمالنا نحن (كتب وأدلّة وأبحاث): القائمة · كتاب جديد · صفحة الكتاب بثلاث خطوات (المحتوى · السعر · المتجر) · أكواد الأدلّة.
  // ⛔ مفيش confirm()/alert()/prompt(): التأكيد لوحة جوه الصفحة. ⛔ مفيش فورم سعر هنا: السعر من ورقة الأسعار الموجودة (V2D3.openPrice) بس.
  // ⛔ كل كتابة تروح مع `confirmed:true` ولا تتحرّك إلا بعد ضغطة «تأكيد» من اللوحة. مفيش حفظ في المتصفح.
  // ============================================================================================================================
  var OMOD = 'v2s_books_ours';
  var OTYPES = [['book', 'كتاب'], ['guide', 'دليل'], ['research', 'بحث'], ['other', 'أخرى']];
  var CODE_RE = /^[a-z0-9_-]{3,40}$/;
  var CODE_ERR = 'الكود من ٣ إلى ٤٠ حرفًا: أحرف إنجليزية صغيرة وأرقام وشرطة فقط';
  var O = { view: null, mode: 'list', slug: null, src: {}, note: null, noteT: null, err: null, confirm: null, busy: false, writer: false,
            f: { instruction: '', outline: '', draft: null, dirty: false, tokens: [] }, pending: null, rows: null, poll: null, away: false, hist: false };

  function oTypeText(t) { var r = OTYPES.filter(function (x) { return x[0] === t; })[0]; return r ? r[1] : 'أخرى'; }
  function oSrc(k) { return O.src[k] || (O.src[k] = { state: 'idle', data: null, status: 0, seq: 0 }); }
  function oLoad(k, path, force) {
    var s = oSrc(k), E = ep();
    if (!E || !E.api || !E.authed) return;
    if (!force && s.state !== 'idle') return;
    if (s.state === 'idle') s.state = 'loading';
    var seq = ++s.seq;
    E.api(path).then(function (d) {
      if (seq !== s.seq) return;
      s.state = 'ready'; s.data = d; s.status = 200; oChanged();
    }).catch(function (e) {
      if (seq !== s.seq || (e && e.status === 401)) return;
      s.state = e && e.status === 404 ? 'closed' : 'error'; s.status = (e && e.status) || 0; s.data = null; oChanged();
    });
  }
  var OP = { list: '/v2/books/ours', codes: '/v2/books/guide-codes', gprice: '/v2/prices/book/_guides' };
  function oPricePath(slug) { return '/v2/prices/book/' + encodeURIComponent(slug); }
  function oDraftPath(slug) { return '/v2/books/ours/' + encodeURIComponent(slug) + '/brain/draft'; }
  function oEnsureList() {
    oLoad('list', OP.list, false); oLoad('codes', OP.codes, false); oLoad('gprice', OP.gprice, false);
  }
  function oBooks() { var s = oSrc('list'); return s.state === 'ready' && s.data && Array.isArray(s.data.books) ? s.data.books : null; }
  function oBook(slug) { var b = oBooks(); return b ? b.filter(function (x) { return x.slug === slug; })[0] || null : null; }
  function oIsCurrent() { return !!(O.view && host().current && host().current() === OMOD && document.body.contains(O.view)); }
  var oRedrawT = null;
  function oChanged() {
    if (O.mode === 'codes' && O.rows === null) { var cs = codesFromSource(); if (cs) O.rows = cs; }
    if (oRedrawT) return;
    oRedrawT = setTimeout(function () { oRedrawT = null; oRedraw(); }, 0);
  }
  var oRetryT = null;
  function oRedraw() {
    if (!oIsCurrent()) return;
    if (modalOpen()) {                                   // لا نمسح ما يكتبه المؤسس في ورقة مفتوحة؛ نلحق بعد إغلاقها
      if (!oRetryT) oRetryT = setInterval(function () { if (modalOpen()) return; clearInterval(oRetryT); oRetryT = null; oRedraw(); }, 400);
      return;
    }
    oDraw(O.view);
  }
  function oSetNote(t) { O.note = t; clearTimeout(O.noteT); O.noteT = setTimeout(function () { O.note = null; oRedraw(); }, 10000); }
  function oErr(e) {
    if (e && e.status === 401) return SESSION_AR;
    var d = (e && e.data) || {};
    return typeof d.error === 'string' && d.error ? arDigits(d.error) : FAIL_AR;
  }
  function fmtSize(n) {
    n = Number(n) || 0;
    if (n < 1048576) return arDigits(Math.max(1, Math.round(n / 1024))) + ' كيلوبايت';
    return arDigits((n / 1048576).toFixed(1).replace('.', '٫')) + ' ميغا';
  }
  function oFileLine(b) {
    var f = b.file;
    if (!f || !f.uploaded) return null;
    var parts = [];
    if (f.pages) parts.push(arDigits(f.pages) + ' صفحة');
    if (f.size) parts.push(fmtSize(f.size));
    return parts.join('، ');
  }
  function oStatusPill(b) { return b.status === 'live' ? '<span class="bk-st st-live">في المتجر</span>' : '<span class="bk-st st-hidden">مسودة</span>'; }
  function oTypePill(b) { return '<span class="bk-type">' + esc(oTypeText(b.type)) + '</span>'; }
  function oNoteStrip() { return O.note ? '<div class="v3-ok" role="status">' + esc(O.note) + '</div>' : ''; }
  function oErrStrip(where) { return O.err && O.err.where === where ? '<div class="v3-err" role="alert">' + esc(O.err.text) + '</div>' : ''; }
  function oSetErr(where, e) { O.err = { where: where, text: typeof e === 'string' ? e : oErr(e) }; }
  function confirmBox(kind, text, goLabel) {
    if (!O.confirm || O.confirm.kind !== kind) return '';
    return '<div class="ou-confirm" role="group" aria-label="تأكيد"><p>' + esc(text) + '</p><div class="ou-acts"><button type="button" class="ep-b1" data-a="cgo"' + (O.busy ? ' disabled' : '') + '>'
      + esc(O.busy ? 'جارٍ التنفيذ…' : goLabel) + '</button><button type="button" class="ep-b2" data-a="cno"' + (O.busy ? ' disabled' : '') + '>رجوع</button></div></div>';
  }

  // ------------------------------------------------------------------ القائمة
  function guidesCard() {
    var cs = oSrc('codes'), ps = oSrc('gprice'), codes = cs.state === 'ready' && cs.data && Array.isArray(cs.data.codes) ? cs.data.codes : null;
    var sum = codes ? (codes.length ? U.ar(codes.length) + (codes.length === 1 ? ' كود' : ' أكواد') + '، ' + U.ar(codes.filter(function (c) { return c.active; }).length) + ' مفعّل' : 'لا أكواد بعد')
      : (cs.state === 'loading' || cs.state === 'idle' ? '…جارٍ الجلب' : 'غير متاح بعد');
    var price = ps.state === 'ready' ? priceLines(ps.data) : null;
    var priceTxt = price ? (price.length ? price.join('، ') : 'لم يُحدَّد سعر بعد') : (ps.state === 'loading' || ps.state === 'idle' ? '…جارٍ الجلب' : 'غير متاح بعد');
    return '<article class="ou-card ou-guides" data-card="guides"><h3>الأدلّة</h3><p class="ou-about">سعر واحد لكل الأدلّة، وأكواد تفتح الدليل لمن تعطيهم إياها.</p>'
      + '<dl class="ou-sums"><div><dt>السعر</dt><dd>' + esc(priceTxt) + '</dd></div><div><dt>أكواد الفتح</dt><dd>' + esc(sum) + '</dd></div></dl>'
      + '<div class="ou-acts"><button type="button" class="ep-b2" data-a="gprice">سعر الأدلّة</button><button type="button" class="ep-b2" data-a="codes">أكواد الفتح</button></div></article>';
  }
  function bookCard(b) {
    var fl = oFileLine(b), has = !!fl;
    var dr = b.draft === 'ready' ? '<p class="ou-fine">مسودة العقل محفوظة</p>' : (b.draft === 'writing' ? '<p class="ou-fine">العقل يكتب الآن</p>' : '');
    return '<article class="ou-card" data-slug="' + esc(b.slug) + '"><div class="ou-pills">' + oTypePill(b) + oStatusPill(b) + '</div><h3>' + esc(b.title) + '</h3>'
      + '<p class="ou-file ' + (has ? 'ok' : 'no') + '">' + (has ? 'الملف جاهز · ' + esc(fl) : 'لا يوجد ملف بعد') + '</p>' + dr
      + '<div class="ou-acts"><button type="button" class="ep-b2" data-a="open" data-slug="' + esc(b.slug) + '" aria-label="افتح ' + esc(b.title) + '">افتح</button></div></article>';
  }
  function drawOursList(v) {
    var s = oSrc('list'), books = oBooks();
    var head = '<section class="ou-head"><div><h2 class="v3-h2">كتبنا وأدلّتنا</h2><p class="ou-sub">ما نصدره نحن: كتب وأدلّة وأبحاث. ارفع الملف أو اكتبه مع العقل، وحدّد السعر، ثم اعرضه في المتجر.</p></div>'
      + '<button type="button" class="ep-b1" data-a="new">كتاب جديد</button></section>';
    var body;
    if (s.state === 'idle' || s.state === 'loading') body = '<div class="v3-empty"><b>…جارٍ جلب الكتب</b></div>';
    else if (s.state === 'closed') body = '<div class="v3-empty"><b>المتجر لم يُفتح بعد</b><p>تظهر هنا كتبنا حين يُفتح المتجر.</p></div>';
    else if (!books) body = '<div class="v3-empty"><b>الكتب: غير متاح بعد</b><p>تعذّر الوصول إلى هذه البيانات الآن، فلا تعتبر الشاشة فارغة.</p><button type="button" class="ep-b2" data-a="retry">أعد المحاولة</button></div>';
    else if (!books.length) body = '<div class="v3-empty"><b>لا كتب بعد</b><p>ابدأ بكتاب أو دليل جديد، ثم ارفع ملفه أو اكتبه مع العقل.</p></div>';
    else body = '<div class="ou-grid">' + books.map(bookCard).join('') + guidesCard() + '</div>';
    if (!books || !books.length) body += '<div class="ou-grid ou-one">' + guidesCard() + '</div>';
    v.innerHTML = '<div class="v3 v2s-books v2s-ours" data-board="ours">' + oNoteStrip() + head + oErrStrip('list') + body + '</div>';
    oWire(v);
  }

  // ------------------------------------------------------------------ أسعار الكتاب (قراءة فقط هنا؛ التعديل من ورقة الأسعار الموجودة)
  function priceLines(resp) {
    var form = L.v2PriceForm(resp);
    if (!form) return null;
    var out = [];
    form.versions.forEach(function (v) {
      var cs = form.countries.filter(function (c) { return v.cells[c.key] !== ''; }).map(function (c) {
        var n = Number(String(v.cells[c.key]).replace(/[٬,\s]/g, ''));
        return c.label + ' ' + arDigits(String(isFinite(n) ? n : v.cells[c.key]).replace('.', '٫')) + ' ' + c.currencyName;
      });
      if (cs.length) out.push(v.label + ': ' + cs.join('، '));
    });
    return out;
  }

  // ------------------------------------------------------------------ صفحة الكتاب
  function stepHead(n, title, done, flagYes, flagNo) {
    return '<header class="ou-sh"><span class="ou-n" aria-hidden="true">' + arDigits(n) + '</span><h3>' + esc(title) + '</h3><span class="ou-flag ' + (done ? 'yes' : 'no') + '">' + esc(done ? flagYes : flagNo) + '</span></header>';
  }
  function writerPanel(b) {
    var dsrc = oSrc('draft:' + b.slug), dv = dsrc.state === 'ready' ? dsrc.data : null;
    var st = dv && dv.status;
    var h = '<div class="ou-writer" id="ou-writer"><h4>اكتبه مع العقل</h4>'
      + '<div class="fld"><label for="ou_ins">ماذا تريد أن يُكتب؟</label><textarea id="ou_ins" rows="4" maxlength="2000" placeholder="مثال: دليل مبسّط لعقود الإيجار للمستأجرين الجدد، بأسلوب هادئ وأمثلة قصيرة">' + esc(O.f.instruction) + '</textarea></div>'
      + '<div class="fld"><label for="ou_out">الفصول المطلوبة (اختياري، سطر لكل فصل)</label><textarea id="ou_out" rows="3" maxlength="3000">' + esc(O.f.outline) + '</textarea></div>'
      + '<div class="ou-acts"><button type="button" class="ep-b1" data-a="draft"' + (st === 'writing' || O.busy ? ' disabled' : '') + '>' + (st === 'writing' ? 'العقل يكتب الآن…' : (O.f.draft ? 'اكتب مسودة جديدة' : 'اكتب المسودة')) + '</button></div>'
      + '<p class="ou-fine">تُحفظ المسودة هنا لتراجعها وتعدّلها. لا يُرفع شيء قبل أن تضغط «اعمل ملف PDF وارفعه».</p>';
    if (st === 'writing') h += '<p class="ou-writing" role="status">…العقل يكتب المسودة، قد يستغرق دقيقة. يمكنك البقاء في هذه الصفحة.</p>';
    if (st === 'failed' && dv.error) h += '<div class="v3-err" role="alert">' + esc(dv.error) + (O.f.draft ? ' (المسودة السابقة ما زالت محفوظة)' : '') + '</div>';
    h += oErrStrip('writer');
    if (O.f.draft) h += draftEditor(b, dv);
    return h + '</div>';
  }
  // ------------------------------------------------------------------ علامات المراجعة (أرقام وأسماء لاتينية ليست في التعليمات): تُعلَّم لا تُرفض
  function reviewPhrase(n) {
    if (n === 1) return 'موضع واحد يحتاج مراجعة';
    if (n === 2) return 'موضعان يحتاجان مراجعة';
    if (n <= 10) return arDigits(n) + ' مواضع تحتاج مراجعة';
    return arDigits(n) + ' موضعًا يحتاج مراجعة';
  }
  function liveMarks() {
    var d = O.f.draft, toks = O.f.tokens || [], n = 0;
    if (!d || !toks.length) return 0;
    toks.forEach(function (t) {
      if (String(d.title || '').indexOf(t) >= 0 || String(d.about || '').indexOf(t) >= 0) n++;
      d.chapters.forEach(function (c) { if (String(c.title || '').indexOf(t) >= 0 || String(c.body || '').indexOf(t) >= 0) n++; });
    });
    return n;
  }
  // نص ⇒ HTML فيه الرموز المعلَّمة داخل <mark> (الباقي مهرَّب). الرمز يطابق الرقم أو الكلمة كاملة.
  function markHtml(text, toks) {
    var set = {}; (toks || []).forEach(function (t) { set[t] = 1; });
    return String(text == null ? '' : text).split(/([0-9٠-٩]+|[A-Za-z]+)/).map(function (part, i) {
      return i % 2 === 1 && set[part] ? '<mark>' + esc(part) + '</mark>' : esc(part);
    }).join('');
  }
  // خانة بتعليم ناعم: طبقة خلفية بنفس النص (شفّافة) يظهر منها التسطير فقط، والخانة الحقيقية فوقها
  function hlField(kind, attrs, value) {
    var inner = kind === 'ta' ? '<textarea ' + attrs + '>' + esc(value) + '</textarea>' : '<input type="text" ' + attrs + ' value="' + esc(value) + '" autocomplete="off">';
    return '<div class="ou-hl ' + (kind === 'ta' ? 'multi' : 'one') + '"><div class="ou-hl-back" aria-hidden="true">' + markHtml(value, O.f.tokens) + '</div>' + inner + '</div>';
  }
  function autosize(v) { qa('.ou-hl.multi textarea', v).forEach(function (t) { t.style.height = 'auto'; t.style.height = (t.scrollHeight + 2) + 'px'; }); }

  function draftEditor(b, dv) {
    var d = O.f.draft;
    var who = dv && dv.writer === 'backup' ? 'كتبها الكاتب الاحتياطي' : 'كتبها العقل';
    var h = '<div class="ou-draft"><p class="ou-fine">' + esc(who) + '. راجعها وعدّلها كما تشاء قبل أن تعمل الملف.</p>'
      + '<p class="ou-review" id="ou-review" role="note"' + (liveMarks() ? '' : ' hidden') + '>راجع هذه الأرقام والأسماء قبل العرض</p>'
      + '<div class="fld"><label for="ou_dt">عنوان الكتاب</label>' + hlField('in', 'id="ou_dt" maxlength="160"', d.title) + '</div>'
      + '<div class="fld"><label for="ou_da">نبذة قصيرة</label>' + hlField('ta', 'id="ou_da" rows="3" maxlength="2000"', d.about) + '</div>';
    d.chapters.forEach(function (c, i) {
      h += '<div class="ou-ch" data-i="' + i + '"><div class="ou-chh"><b>الفصل ' + arDigits(i + 1) + '</b>'
        + '<button type="button" class="ep-bs" data-a="chdel" data-i="' + i + '"' + (d.chapters.length < 2 ? ' disabled' : '') + '>احذف الفصل</button></div>'
        + '<div class="fld"><label for="ou_ct' + i + '">عنوان الفصل</label>' + hlField('in', 'id="ou_ct' + i + '" data-f="ct" data-i="' + i + '" maxlength="120"', c.title) + '</div>'
        + '<div class="fld"><label for="ou_cb' + i + '">النص</label>' + hlField('ta', 'id="ou_cb' + i + '" data-f="cb" data-i="' + i + '" rows="8" maxlength="8000"', c.body) + '</div></div>';
    });
    h += '<div class="ou-acts"><button type="button" class="ep-bs" data-a="chadd"' + (d.chapters.length >= 12 ? ' disabled' : '') + '>أضف فصلًا</button></div>'
      + '<div class="ou-acts"><button type="button" class="ep-b2" data-a="savedraft"' + (O.f.dirty ? '' : ' disabled') + '>' + (O.f.dirty ? 'احفظ التعديل' : 'التعديل محفوظ') + '</button>'
      + '<button type="button" class="ep-b1" data-a="mkpdf">اعمل ملف PDF وارفعه</button></div>'
      + confirmBox('pdf', 'سيُنشأ ملف PDF من هذه المسودة ويُرفع' + (b.file && b.file.uploaded ? '، ويحلّ محلّ الملف الحالي' : '') + '.' + (liveMarks() ? ' ' + reviewPhrase(liveMarks()) + '.' : ''), 'اعمل الملف وارفعه') + oErrStrip('pdf') + '</div>';
    return h;
  }
  function stepContent(b, nextIs) {
    var fl = oFileLine(b), has = !!(b.file && b.file.uploaded);
    var h = '<li class="ou-step ' + (has ? 'done' : 'todo') + '" data-step="content">' + stepHead(1, 'المحتوى', has, 'تم', 'لم يتم بعد');
    if (has) h += '<p class="ou-line">الملف الحالي: <b dir="auto">' + esc(b.file.name || 'ملف PDF') + '</b>' + (fl ? '، ' + esc(fl) : '') + (b.file.uploaded_at ? '، رُفع ' + esc(U.agoText(b.file.uploaded_at, now())) : '') + '</p>';
    else h += '<p class="ou-line mute">لا يوجد ملف بعد. ارفع ملف PDF جاهزًا، أو اكتبه مع العقل.</p>';
    if (O.pending) {
      h += '<p class="ou-line">الملف المختار: <b dir="auto">' + esc(O.pending.name) + '</b>، ' + esc(fmtSize(O.pending.size)) + '</p>';
      h += confirmBox('file', 'سيُرفع هذا الملف' + (has ? '، ويحلّ محلّ الملف الحالي' : '') + '.', 'ارفع الملف');
    } else {
      h += '<div class="ou-acts"><button type="button" class="' + (nextIs && !O.writer ? 'ep-b1' : 'ep-b2') + '" data-a="pick">' + (has ? 'ارفع ملفًا آخر' : 'ارفع ملف PDF') + '</button>'
        + '<button type="button" class="ep-b2" data-a="write" aria-expanded="' + (O.writer ? 'true' : 'false') + '">' + (O.writer ? 'أخفِ الكتابة مع العقل' : 'اكتبه مع العقل') + '</button></div>';
    }
    h += '<input type="file" id="ou_file" accept="application/pdf,.pdf" hidden>' + oErrStrip('file');
    if (O.writer) h += writerPanel(b);
    return h + '</li>';
  }
  function stepPrice(b, nextIs) {
    var ps = oSrc('price:' + b.slug), lines = ps.state === 'ready' ? priceLines(ps.data) : (ps.state === 'closed' ? [] : null);
    var has = !!(lines && lines.length);
    var h = '<li class="ou-step ' + (has ? 'done' : 'todo') + '" data-step="price">' + stepHead(2, 'السعر', has, 'تم', 'لم يتم بعد');
    if (lines === null) h += '<p class="ou-line mute">' + (ps.state === 'loading' || ps.state === 'idle' ? '…جارٍ جلب السعر' : 'السعر: غير متاح بعد') + '</p>';
    else if (!has) h += '<p class="ou-line mute">لم يُحدَّد سعر بعد.</p>';
    else h += '<ul class="ou-list">' + lines.map(function (l) { return '<li>' + esc(l) + '</li>'; }).join('') + '</ul>';
    h += '<div class="ou-acts"><button type="button" class="' + (nextIs ? 'ep-b1' : 'ep-b2') + '" data-a="price">' + (has ? 'عدّل السعر' : 'حدّد السعر') + '</button></div>'
      + '<p class="ou-fine">يُحفظ السعر من نفس ورقة الأسعار في «الفلوس».</p>' + oErrStrip('price');
    return h + '</li>';
  }
  function stepStore(b, nextIs) {
    var live = b.status === 'live', has = !!(b.file && b.file.uploaded);
    var h = '<li class="ou-step ' + (live ? 'done' : 'todo') + '" data-step="store">' + stepHead(3, 'المتجر', live, 'في المتجر', 'غير معروض');
    if (live) {
      h += '<p class="ou-line">الكتاب معروض للناس في المتجر الآن.</p>';
      if (!O.confirm || O.confirm.kind !== 'pause') h += '<div class="ou-acts"><button type="button" class="ep-b2" data-a="pause">اسحبه من المتجر</button></div>';
      h += confirmBox('pause', 'سيختفي «' + b.title + '» من المتجر فور التأكيد.', 'اسحبه الآن');
    } else if (!has) {
      h += '<p class="ou-line mute">ارفع ملف PDF أولًا، ثم يمكنك عرض الكتاب في المتجر.</p>';
    } else {
      h += '<p class="ou-line">الكتاب مسودة، ولا يراه الناس.</p>';
      if (!O.confirm || O.confirm.kind !== 'live') h += '<div class="ou-acts"><button type="button" class="' + (nextIs ? 'ep-b1' : 'ep-b2') + '" data-a="golive">اعرضه في المتجر</button></div>';
      h += confirmBox('live', 'سيظهر «' + b.title + '» للناس في المتجر فور التأكيد.', 'اعرضه الآن');
    }
    return h + oErrStrip('store') + '</li>';
  }
  function drawOursBook(v) {
    var b = oBook(O.slug);
    if (!b) {
      v.innerHTML = '<div class="v3 v2s-books v2s-ours" data-board="ours">' + oNoteStrip() + '<button type="button" class="v3-link bk-back" data-a="back">→ كتبنا</button><div class="v3-empty"><b>' + esc(NOTFOUND_AR) + '</b></div></div>';
      oWire(v); return;
    }
    oAdoptDraft(b.slug);
    var has = !!(b.file && b.file.uploaded);
    var ps = oSrc('price:' + b.slug), pl = ps.state === 'ready' ? priceLines(ps.data) : null, hasPrice = !!(pl && pl.length);
    var next = !has ? 'content' : (!hasPrice && pl !== null ? 'price' : (b.status !== 'live' ? 'store' : ''));
    v.innerHTML = '<div class="v3 v2s-books v2s-ours" data-board="ours-book">' + oNoteStrip()
      + '<button type="button" class="v3-link bk-back" data-a="back">→ كتبنا</button>'
      + '<header class="ou-bhead"><div class="ou-pills">' + oTypePill(b) + oStatusPill(b) + '</div><h2>' + esc(b.title) + '</h2>' + (b.about ? '<p class="ou-about">' + esc(b.about) + '</p>' : '')
      + '<div class="ou-acts"><button type="button" class="ep-bs" data-a="edit">عدّل العنوان والنبذة والنوع</button></div></header>'
      + '<ol class="ou-steps">' + stepContent(b, next === 'content') + stepPrice(b, next === 'price') + stepStore(b, next === 'store') + '</ol></div>';
    oWire(v);
  }

  // ------------------------------------------------------------------ أكواد الفتح
  function codeRow(r, i) {
    var used = r.uses ? 'استُعمل ' + arDigits(r.uses) + (r.uses === 1 ? ' مرة' : ' مرات') : 'لم يُستعمل بعد';
    return '<div class="ou-code" role="row" data-i="' + i + '">'
      + '<div class="ou-cell" data-l="الكود"><input type="text" data-f="code" data-i="' + i + '" dir="ltr" maxlength="40" value="' + esc(r.code) + '" aria-label="الكود" autocomplete="off" autocapitalize="none" spellcheck="false"></div>'
      + '<div class="ou-cell" data-l="الملاحظة"><input type="text" data-f="note" data-i="' + i + '" maxlength="200" value="' + esc(r.note || '') + '" aria-label="الملاحظة" autocomplete="off"></div>'
      + '<div class="ou-cell" data-l="أقصى عدد"><input type="text" inputmode="numeric" data-f="max" data-i="' + i + '" dir="ltr" maxlength="7" value="' + esc(r.max_uses == null ? '' : arDigits(r.max_uses)) + '" placeholder="بلا حد" aria-label="أقصى عدد استعمال" autocomplete="off"></div>'
      + '<div class="ou-cell ou-chk" data-l="مفعّل"><label><input type="checkbox" data-f="active" data-i="' + i + '"' + (r.active ? ' checked' : '') + '> مفعّل</label></div>'
      + '<div class="ou-cell ou-used" data-l="الاستعمال"><span>' + esc(used) + '</span></div>'
      + '<div class="ou-cell ou-del"><button type="button" class="ep-bs" data-a="coderm" data-i="' + i + '" aria-label="احذف الكود">احذف</button></div></div>';
  }
  function drawCodes(v) {
    var s = oSrc('codes');
    var head = '<button type="button" class="v3-link bk-back" data-a="back">→ كتبنا</button><section class="ou-head"><div><h2 class="v3-h2">أكواد فتح الأدلّة</h2>'
      + '<p class="ou-sub">الكود يفتح الدليل لمن يكتبه بدل الدفع. اكتب الأكواد ثم احفظها كلها مرة واحدة.</p></div></section>';
    var body;
    if (O.rows === null) {
      body = s.state === 'idle' || s.state === 'loading' ? '<div class="v3-empty"><b>…جارٍ جلب الأكواد</b></div>'
        : '<div class="v3-empty"><b>الأكواد: غير متاح بعد</b><p>تعذّر الوصول إلى هذه البيانات الآن، فلا تعتبر القائمة فارغة.</p><button type="button" class="ep-b2" data-a="retry">أعد المحاولة</button></div>';
    } else {
      body = '<div class="ou-codes" role="table" aria-label="أكواد الفتح">'
        + (O.rows.length ? '<div class="ou-chead" role="row"><span>الكود</span><span>الملاحظة</span><span>أقصى عدد</span><span>مفعّل</span><span>الاستعمال</span><span></span></div>' + O.rows.map(codeRow).join('')
                         : '<p class="v3-none">لا أكواد بعد. أضف أول كود.</p>') + '</div>'
        + '<div class="ou-acts"><button type="button" class="ep-bs" data-a="codeadd"' + (O.rows.length >= 200 ? ' disabled' : '') + '>أضف كودًا</button></div>'
        + oErrStrip('codes')
        + '<div class="ou-acts ou-save"><button type="button" class="ep-b1" data-a="codesave">احفظ الأكواد</button></div>'
        + confirmBox('codes', 'ستُحفظ ' + arDigits(O.rows.length) + (O.rows.length === 1 ? ' كود' : ' أكواد') + '، منها ' + arDigits(O.rows.filter(function (r) { return r.active; }).length) + ' مفعّل. تحلّ هذه القائمة محل القائمة الحالية.', 'احفظ الآن');
    }
    v.innerHTML = '<div class="v3 v2s-books v2s-ours" data-board="ours-codes">' + oNoteStrip() + head + body + '</div>';
    oWire(v);
  }
  function codesFromSource() {
    var s = oSrc('codes');
    if (s.state === 'ready' && s.data && Array.isArray(s.data.codes)) return s.data.codes.map(function (c) { return { code: c.code, note: c.note || '', max_uses: c.max_uses == null ? null : c.max_uses, active: c.active !== false, uses: c.uses || 0 }; });
    return null;
  }
  // الصفوف المكتوبة ⇒ {ok, codes} أو {ok:false, error}
  function codesPayload() {
    var out = [], seen = {}, i, r;
    for (i = 0; i < O.rows.length; i++) {
      r = O.rows[i];
      var code = String(r.code || '').trim().toLowerCase();
      if (!CODE_RE.test(code)) return { ok: false, error: CODE_ERR };
      if (seen[code]) return { ok: false, error: 'الكود مكرر: ' + code };
      seen[code] = 1;
      var mu = String(r.max_uses == null ? '' : r.max_uses).replace(/[٠-٩]/g, function (d) { return String(d.charCodeAt(0) - 0x660); }).trim(), n = null;
      if (mu !== '') {
        if (!/^\d{1,7}$/.test(mu) || Number(mu) < 1) return { ok: false, error: 'أقصى عدد استعمال رقم صحيح أكبر من صفر، أو اتركه فارغًا' };
        n = Number(mu);
      }
      out.push({ code: code, note: String(r.note || '').trim().slice(0, 200), max_uses: n, active: !!r.active });
    }
    return { ok: true, codes: out };
  }

  // ------------------------------------------------------------------ الرسم والتنقّل
  function oDraw(v) {
    if (O.mode === 'codes') return drawCodes(v);
    if (O.mode === 'book') {
      var s = oSrc('list');
      if (s.state === 'idle' || s.state === 'loading') { v.innerHTML = '<div class="v3 v2s-books v2s-ours" data-board="ours-book"><div class="v3-empty"><b>…جارٍ جلب الكتاب</b></div></div>'; return; }
      return drawOursBook(v);
    }
    return drawOursList(v);
  }
  function oPush(state) { try { history.pushState({ v2sOurs: state }, '', location.hash); O.hist = true; } catch (e) {} }
  function oGo(mode, slug) {
    O.mode = mode; O.slug = slug || null; O.confirm = null; O.err = null; O.pending = null; O.busy = false; O.writer = false;
    O.f = { instruction: '', outline: '', draft: null, dirty: false, tokens: [] };
    oStopPoll();
    if (mode === 'book') { oLoad('price:' + slug, oPricePath(slug), true); oLoad('draft:' + slug, oDraftPath(slug), true); }
    if (mode === 'codes') { oLoad('codes', OP.codes, true); O.rows = codesFromSource(); }
    oRedraw();
  }
  function oBack() {
    var st = null; try { st = history.state; } catch (e) {}
    if (st && st.v2sOurs && O.hist) { try { history.back(); return; } catch (e2) {} }
    oGo('list');
  }
  window.addEventListener('popstate', function (e) {
    if (!oIsCurrent()) return;
    var st = e.state && e.state.v2sOurs;
    if (!st) { O.hist = false; if (O.mode !== 'list') oGo('list'); return; }
    if (st === 'codes') oGo('codes'); else oGo('book', st);
  });
  function oOpen(mode, slug) { oPush(mode === 'codes' ? 'codes' : slug); oGo(mode, slug); window.scrollTo(0, 0); var c = q('.content'); if (c) c.scrollTop = 0; }

  // ------------------------------------------------------------------ الكتابة (كلها بعد «تأكيد»)
  function oReloadList() { oLoad('list', OP.list, true); }
  function oDone(note, e) { O.busy = false; O.confirm = null; if (note) oSetNote(note); oRedraw(); return e; }
  function oFail(where, e) {
    O.busy = false; O.confirm = null; oSetErr(where, e);
    if (e && (e.status === 409 || (e.data && e.data.no_reply))) oReloadList();
    oRedraw();
  }
  function oUpload(slug, file) {
    var fd = new FormData();
    fd.append('file', file, file.name); fd.append('confirmed', 'true');
    return ep().api('/v2/books/ours/' + encodeURIComponent(slug) + '/file', { method: 'POST', body: fd });
  }
  function oDoConfirm() {
    var c = O.confirm, b = O.slug ? oBook(O.slug) : null;
    if (!c || O.busy) return;
    O.busy = true; O.err = null; oRedraw();
    var E = ep();
    if (c.kind === 'file' && O.pending && b) {
      var f = O.pending.file;
      oUpload(b.slug, f).then(function () { O.pending = null; oReloadList(); oDone('رُفع الملف'); }).catch(function (e) { O.pending = null; oFail('file', e); });
    } else if (c.kind === 'live' || c.kind === 'pause') {
      var live = c.kind === 'live';
      E.api('/v2/books/ours/' + encodeURIComponent(b.slug) + '/status', { method: 'PUT', body: { live: live, confirmed: true } })
        .then(function () { oReloadList(); oDone(live ? 'عُرض «' + b.title + '» في المتجر' : 'سُحب «' + b.title + '» من المتجر'); }).catch(function (e) { oFail('store', e); });
    } else if (c.kind === 'pdf' && b) {
      var save = O.f.dirty ? saveDraft(b.slug, true) : Promise.resolve();
      save.then(function () { return E.api('/v2/books/ours/' + encodeURIComponent(b.slug) + '/brain/pdf', { method: 'POST', body: { confirmed: true } }); })
        .then(function () { oReloadList(); oDone('أُنشئ ملف PDF من المسودة ورُفع'); }).catch(function (e) { oFail('pdf', e); });
    } else if (c.kind === 'codes') {
      var p = codesPayload();
      if (!p.ok) { O.busy = false; O.confirm = null; oSetErr('codes', p.error); oRedraw(); return; }
      E.api(OP.codes, { method: 'PUT', body: { codes: p.codes, confirmed: true } })
        .then(function () { O.busy = false; O.confirm = null; oLoad('codes', OP.codes, true); O.rows = null; oSetNote('حُفظت الأكواد'); oGo('codes'); })
        .catch(function (e) { oFail('codes', e); });
    } else { O.busy = false; O.confirm = null; oRedraw(); }
  }
  function saveDraft(slug, silent) {
    var d = O.f.draft;
    return ep().api(oDraftPath(slug), { method: 'PUT', body: { title: d.title, about: d.about, chapters: d.chapters } }).then(function (res) {
      O.f.dirty = false; var s = oSrc('draft:' + slug); s.state = 'ready'; s.data = res;
      if (!silent) { oSetNote('حُفظ التعديل'); oRedraw(); }
      return res;
    });
  }
  function oStopPoll() { if (O.poll) { clearInterval(O.poll); O.poll = null; } }
  function oStartPoll(slug) {
    oStopPoll();
    O.poll = setInterval(function () {
      if (!oIsCurrent() || O.mode !== 'book' || O.slug !== slug) { oStopPoll(); return; }
      var s = oSrc('draft:' + slug);
      if (s.state === 'ready' && s.data && s.data.status !== 'writing') { oStopPoll(); return; }
      oLoad('draft:' + slug, oDraftPath(slug), true);
    }, 3000);
  }
  // مسودة وصلت من الخادم ⇒ تدخل نموذج التعديل (مرة واحدة؛ ما يكتبه المؤسس لا يُمحى بإعادة الرسم)
  function oAdoptDraft(slug) {
    if (!slug) return;
    var s = oSrc('draft:' + slug);
    if (s.state !== 'ready' || !s.data) return;
    if (s.data.status === 'writing') oStartPoll(slug);
    if (s.data.draft && !O.f.dirty && (!O.f.draft || O.f.stamp !== s.data.updated_at)) {
      O.f.draft = JSON.parse(JSON.stringify(s.data.draft)); O.f.stamp = s.data.updated_at;
      var seenT = {}; O.f.tokens = (s.data.review_marks || []).map(function (m) { return m.token; }).filter(function (t) { return t && !seenT[t] && (seenT[t] = 1); });
    }
    if (!O.f.instruction && s.data.instruction) O.f.instruction = s.data.instruction;
    if (!O.f.outline && s.data.outline) O.f.outline = s.data.outline;
    if ((s.data.draft || s.data.status === 'writing' || s.data.status === 'failed') && !O.f.seen) { O.f.seen = true; O.writer = true; }
  }

  // ------------------------------------------------------------------ أوراق: كتاب جديد · تعديل البيانات
  function typeSelect(id, cur) {
    return '<select id="' + id + '">' + OTYPES.map(function (t) { return '<option value="' + t[0] + '"' + (t[0] === cur ? ' selected' : '') + '>' + esc(t[1]) + '</option>'; }).join('') + '</select>';
  }
  function rid() { var a = []; for (var i = 0; i < 16; i++) a.push(Math.floor(Math.random() * 256).toString(16).replace(/^(.)$/, '0$1')); return 'o-' + a.join(''); }
  function openNewBook() {
    var key = rid();
    formSheet({
      title: 'كتاب جديد', btn: 'أنشئ المسودة', busy: 'جارٍ الإنشاء…', mode: 'ours',
      html: '<p class="mc-lead">يُنشأ الكتاب مسودة لا يراها أحد. بعدها ترفع ملفه أو تكتبه مع العقل، وتحدّد السعر، ثم تعرضه في المتجر.</p>'
        + '<div class="fld"><label for="ou_t">العنوان</label><input id="ou_t" type="text" maxlength="160" autocomplete="off"></div>'
        + '<div class="fld"><label for="ou_a">نبذة قصيرة</label><textarea id="ou_a" rows="3" maxlength="2000"></textarea></div>'
        + '<div class="fld"><label for="ou_ty">النوع</label>' + typeSelect('ou_ty', 'book') + '</div>',
      collect: function (s) {
        var t = (q('#ou_t', s).value || '').trim();
        if (!t) return { ok: false, error: 'اكتب عنوان الكتاب' };
        return { ok: true, payload: { title: t, about: (q('#ou_a', s).value || '').trim(), type: q('#ou_ty', s).value, idem_key: key, confirmed: true } };
      },
      send: function (body) { return ep().api('/v2/books/ours', { method: 'POST', body: body }); },
      onOk: function (res) {
        closeSheet(); oReloadList(); oSetNote('أُنشئت المسودة');
        var slug = res && res.book && res.book.slug;
        if (slug) oOpen('book', slug); else oRedraw();
      }
    });
  }
  function openEditBook(b) {
    formSheet({
      title: 'بيانات الكتاب', btn: 'احفظ', busy: 'جارٍ الحفظ…', mode: 'ours',
      html: '<div class="fld"><label for="ou_t">العنوان</label><input id="ou_t" type="text" maxlength="160" value="' + esc(b.title) + '" autocomplete="off"></div>'
        + '<div class="fld"><label for="ou_a">نبذة قصيرة</label><textarea id="ou_a" rows="3" maxlength="2000">' + esc(b.about || '') + '</textarea></div>'
        + '<div class="fld"><label for="ou_ty">النوع</label>' + typeSelect('ou_ty', b.type) + '</div>',
      collect: function (s) {
        var t = (q('#ou_t', s).value || '').trim();
        if (!t) return { ok: false, error: 'اكتب عنوان الكتاب' };
        return { ok: true, payload: { title: t, about: (q('#ou_a', s).value || '').trim(), type: q('#ou_ty', s).value, confirmed: true } };
      },
      send: function (body) { return ep().api('/v2/books/ours/' + encodeURIComponent(b.slug), { method: 'PUT', body: body }); },
      onOk: function () { closeSheet(); oReloadList(); oSetNote('حُفظت بيانات الكتاب'); oRedraw(); }
    });
  }

  // ------------------------------------------------------------------ ربط الأحداث
  function readDraftFields(v) {
    if (!O.f.draft) return;
    var t = q('#ou_dt', v), a = q('#ou_da', v);
    if (t) O.f.draft.title = t.value;
    if (a) O.f.draft.about = a.value;
    qa('[data-f="ct"]', v).forEach(function (el) { O.f.draft.chapters[+el.getAttribute('data-i')].title = el.value; });
    qa('[data-f="cb"]', v).forEach(function (el) { O.f.draft.chapters[+el.getAttribute('data-i')].body = el.value; });
  }
  function oWire(v) {
    var root = q('.v2s-ours', v) || v;
    var ins = q('#ou_ins', v), out = q('#ou_out', v);
    if (ins) ins.addEventListener('input', function () { O.f.instruction = ins.value; });
    if (out) out.addEventListener('input', function () { O.f.outline = out.value; });
    qa('#ou_dt,#ou_da,[data-f="ct"],[data-f="cb"]', v).forEach(function (el) {
      el.addEventListener('input', function () {
        readDraftFields(v);
        var hl = el.closest('.ou-hl'); if (hl) { hl.querySelector('.ou-hl-back').innerHTML = markHtml(el.value, O.f.tokens) + (el.tagName === 'TEXTAREA' ? '\u200b' : ''); }
        if (el.tagName === 'TEXTAREA') { el.style.height = 'auto'; el.style.height = (el.scrollHeight + 2) + 'px'; }
        var rv = q('#ou-review', v); if (rv) rv.hidden = !liveMarks();
        if (!O.f.dirty) { O.f.dirty = true; var sb = q('[data-a="savedraft"]', v); if (sb) { sb.disabled = false; sb.textContent = 'احفظ التعديل'; } }
      });
    });
    qa('[data-f="code"],[data-f="note"],[data-f="max"]', v).forEach(function (el) {
      el.addEventListener('input', function () { var r = O.rows[+el.getAttribute('data-i')], f = el.getAttribute('data-f'); if (!r) return; if (f === 'code') r.code = el.value; else if (f === 'note') r.note = el.value; else r.max_uses = el.value; });
    });
    qa('[data-f="active"]', v).forEach(function (el) { el.addEventListener('change', function () { var r = O.rows[+el.getAttribute('data-i')]; if (r) r.active = el.checked; }); });
    autosize(v);
    var fi = q('#ou_file', v);
    if (fi) fi.addEventListener('change', function () {
      var f = fi.files && fi.files[0]; if (!f) return;
      if (!/\.pdf$/i.test(f.name)) { oSetErr('file', 'اختر ملف PDF فقط'); O.pending = null; O.confirm = null; oRedraw(); return; }
      O.err = null; O.pending = { file: f, name: f.name, size: f.size }; O.confirm = { kind: 'file' }; oRedraw();
    });
    root.addEventListener('click', function (e) {
      var el = e.target && e.target.closest ? e.target.closest('[data-a]') : null;
      if (!el || !root.contains(el) || el.disabled) return;
      var a = el.getAttribute('data-a'), b = O.slug ? oBook(O.slug) : null, i = +el.getAttribute('data-i');
      if (a === 'new') return openNewBook();
      if (a === 'open') return oOpen('book', el.getAttribute('data-slug'));
      if (a === 'back') return oBack();
      if (a === 'retry') { ['list', 'codes', 'gprice'].forEach(function (k) { if (oSrc(k).state === 'error' || oSrc(k).state === 'closed') oLoad(k, OP[k], true); }); return; }
      if (a === 'gprice') { return openPriceSheet('_guides', 'أسعار الأدلّة', function () { oLoad('gprice', OP.gprice, true); }); }
      if (a === 'codes') return oOpen('codes');
      if (a === 'edit' && b) return openEditBook(b);
      if (a === 'price' && b) return openPriceSheet(b.slug, b.title, function () { oLoad('price:' + b.slug, oPricePath(b.slug), true); });
      if (a === 'pick') { var fi2 = q('#ou_file', v); if (fi2) { fi2.value = ''; fi2.click(); } return; }
      if (a === 'write') { O.writer = !O.writer; O.err = null; oRedraw(); if (O.writer) { var w = q('#ou-writer'); if (w) w.scrollIntoView({ block: 'nearest' }); } return; }
      if (a === 'golive') { O.err = null; O.confirm = { kind: 'live' }; return oRedraw(); }
      if (a === 'pause') { O.err = null; O.confirm = { kind: 'pause' }; return oRedraw(); }
      if (a === 'cno') { O.confirm = null; if (O.pending) O.pending = null; return oRedraw(); }
      if (a === 'cgo') return oDoConfirm();
      if (a === 'draft' && b) return makeDraft(b, v);
      if (a === 'chadd' && O.f.draft) { readDraftFields(v); O.f.draft.chapters.push({ title: '', body: '' }); O.f.dirty = true; return oRedraw(); }
      if (a === 'chdel' && O.f.draft) { readDraftFields(v); O.f.draft.chapters.splice(i, 1); O.f.dirty = true; return oRedraw(); }
      if (a === 'savedraft' && b) { readDraftFields(v); O.err = null; return saveDraft(b.slug).catch(function (e) { oSetErr('pdf', e); oRedraw(); }); }
      if (a === 'mkpdf' && b) { readDraftFields(v); O.err = null; var chk = checkDraft(); if (chk) { oSetErr('pdf', chk); return oRedraw(); } O.confirm = { kind: 'pdf' }; return oRedraw(); }
      if (a === 'codeadd') { O.rows.push({ code: '', note: '', max_uses: null, active: true, uses: 0 }); return oRedraw(); }
      if (a === 'coderm') { O.rows.splice(i, 1); O.confirm = null; return oRedraw(); }
      if (a === 'codesave') {
        var p = codesPayload();
        if (!p.ok) { oSetErr('codes', p.error); O.confirm = null; return oRedraw(); }
        O.err = null; O.confirm = { kind: 'codes' }; return oRedraw();
      }
    });
  }
  function checkDraft() {
    var d = O.f.draft;
    if (!d || !String(d.title || '').trim()) return 'اكتب عنوانًا للكتاب';
    if (!d.chapters.length) return 'أضف فصلًا واحدًا على الأقل';
    for (var i = 0; i < d.chapters.length; i++) if (!String(d.chapters[i].title || '').trim() || !String(d.chapters[i].body || '').trim()) return 'الفصل ' + arDigits(i + 1) + ' ناقص: اكتب عنوانه ونصه أو احذفه';
    return '';
  }
  function makeDraft(b, v) {
    var ins = (O.f.instruction || '').trim();
    if (!ins) { oSetErr('writer', 'اكتب ما تريده من العقل'); return oRedraw(); }
    O.err = null; O.busy = true; oRedraw();
    ep().api(oDraftPath(b.slug), { method: 'POST', body: { instruction: ins, outline: O.f.outline } }).then(function (res) {
      O.busy = false; var s = oSrc('draft:' + b.slug); s.state = 'ready'; s.data = res; O.f.dirty = false; O.f.draft = null;
      oAdoptDraft(b.slug); oRedraw();
    }).catch(function (e) { O.busy = false; oSetErr('writer', e); oRedraw(); });
  }
  function openPriceSheet(id, title, done) {
    var D3 = window.V2D3;
    if (D3 && typeof D3.openPrice === 'function') return D3.openPrice('book', id, title, done);
    go2('money', 'prices');
  }

  function oRender(v) {
    S.view = null;           // تبويب «الكتب» ما يرسم فوق هذه الشاشة وهي ظاهرة
    O.view = v; O.away = false;
    if (O.mode === 'codes' && O.rows === null) O.rows = codesFromSource();
    oEnsureList();
    if (O.mode === 'book' && O.slug) { oLoad('price:' + O.slug, oPricePath(O.slug), false); oLoad('draft:' + O.slug, oDraftPath(O.slug), false); }
    oRedraw();
  }
  R.mods[OMOD] = {
    owns: function () { return !!(window.V2SHELL && V2SHELL.on); },
    render: oRender
  };

  R.mods.knowledge = {
    owns: function () { return !!(window.V2SHELL && V2SHELL.on); },
    render: render,
    summary: function () { return L.v2kSummary(S.res); },
    library: openLibrary
  };
})();
