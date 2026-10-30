/* ============================================================================
 * v2-d3.js — الجولة D3: شاشات «الفلوس» (نظرة · التحويلات · الإيصالات والعالقة · الأسعار · النسب والإعدادات · إعلانات الأعمال)
 * وشاشتا «الكتب» (مراجعة العروض · طلبات القرّاء). ⛔ لا منطق عمل هنا: الأرقام والتصنيف والفروق قبل ⇒ بعد كلها من `v2-logic.js` (نقي)،
 * وأزرار الفلوس بتنادي نافذة التأكيد الموجودة في v2-home.js (`V2.openMoney`) — لا مسار قرار جديد.
 *
 * ⛔ المفتاح مقفول افتراضيًا: الملف بيتحمّل دايمًا لكنه ما بيرسم شيئًا إلا لو index.html نادى `V2D3.render` (وده ما بيحصل إلا والغلاف
 * الجديد شغّال، لأن الموديولات `v2m_*` و`v2b_*` وهمية ما لها وجود برّاه).
 * ⛔ ولا طلب شبكة من هنا غير: محمّلات الداشبورد الموجودة · `/api/revenues` (دفتر الداشبورد نفسه) · مسارات `/api/v2/*` (بروكسيات أدمن بس) ·
 *   `/api/platform-wallet-payouts?status=paid|rejected` (الموجود). وكل مصدر بيفشل لوحده: رقمه «غير متاح بعد» لا صفر.
 * ⛔ كل زرّ يغيّر رقمًا أو سعرًا أو نسبة بيعدّي على ورقة «راجع التغيير» (قبل ⇒ بعد) ثم «أكّد» — والتأكيد الصريح `confirmed:true` بيروح للخادم.
 * ========================================================================== */
(function () {
  'use strict';
  var L = window.V2L;
  if (!L) return;
  var U = L.util;
  var D3 = window.V2D3 = {};
  var MODS = { v2m_overview: 1, v2m_payouts: 1, v2m_receipts: 1, v2m_prices: 1, v2m_shares: 1, v2m_ads: 1, v2b_offers: 1, v2b_requests: 1 };
  var S = { view: null, mod: '', sig: '', poll: null, minute: null, period: 'month', note: null, noteT: null, busy: {}, picked: {} };
  var SESSION_AR = 'انتهت الجلسة — سجّل الدخول من جديد ثم جرّب';
  var FAIL_AR = 'تعذّر تنفيذ العملية';

  function esc(s) { return String(s == null ? '' : s).replace(/[&<>"']/g, function (c) { return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]; }); }
  function host() { return window.V2_HOST || {}; }
  function ep() { return window.EP || null; }
  function img(name) { return 'v2/img/' + name + '.jpg'; }
  function now() { return S.nowOverride || Date.now(); }
  function q(sel, root) { return (root || document).querySelector(sel); }
  function qa(sel, root) { return Array.prototype.slice.call((root || document).querySelectorAll(sel)); }
  var BRAIN = '<img class="v3-bav" src="' + img('brain-avatar') + '" alt="">';
  D3.owns = function (mod) { return !!MODS[mod]; };

  try { var saved = localStorage.getItem('v3_period'); if (saved === 'day' || saved === 'month' || saved === 'year') S.period = saved; } catch (e) {}

  // ------------------------------------------------------------------ مصادر الجسور (كلٌّ تفشل لوحدها)
  var SRC = {};
  var PATHS = {
    revenues: function () { return '/revenues'; },
    income: function () { return '/v2/income/by-service?month=' + L.v2Period('month', now()).month; },
    settings: function () { return '/v2/money/settings'; },
    shares: function () { return '/v2/shares'; },
    ads: function () { return '/v2/ads-ledger'; },
    stuck: function () { return '/v2/payments/stuck'; },
    refunds: function () { return '/v2/refunds/pending'; },
    pricesBook: function () { return '/v2/prices/book'; },
    pricesCourse: function () { return '/v2/prices/course'; },
    paid: function () { return '/platform-wallet-payouts?status=paid'; },
    rejected: function () { return '/platform-wallet-payouts?status=rejected'; },
    offers: function () { return '/v2/book-offers?status=in_review'; },
    requests: function () { return '/v2/book-requests'; }
  };
  var LABEL = { revenues: 'دفتر الإيرادات', income: 'مدفوعات هذا الشهر', settings: 'الحد الأدنى للسحب', shares: 'جدول النسب', ads: 'أرصدة الإعلانات', stuck: 'المدفوعات العالقة',
                refunds: 'الاستردادات اليدوية', pricesBook: 'أسعار الكتب', pricesCourse: 'أسعار الدورات', paid: 'التحويلات المنفّذة', rejected: 'التحويلات المرفوضة',
                offers: 'عروض الكتب', requests: 'طلبات القرّاء' };
  function srcOf(k) { return SRC[k] || (SRC[k] = { state: 'idle', data: null, status: 0, seq: 0 }); }
  function load(k, force) {
    var s = srcOf(k), E = ep();
    if (!E || !E.api || !E.authed || !PATHS[k]) return;
    if (s.state === 'loading') return;
    if (!force && s.state !== 'idle') return;
    s.state = 'loading';
    var seq = ++s.seq;
    E.api(PATHS[k]()).then(function (d) {
      if (seq !== s.seq) return;
      s.state = 'ready'; s.data = d; s.at = Date.now(); changed();
    }).catch(function (e) {
      if (seq !== s.seq) return;
      if (e && e.status === 401) return;
      s.state = e && e.status === 404 ? 'closed' : 'error'; s.status = (e && e.status) || 0; s.data = null; changed();
    });
  }
  function data(k) { var s = srcOf(k); return s.state === 'ready' ? s.data : null; }
  function srcState(k) { return srcOf(k).state; }
  function loadMany(keys, force) { keys.forEach(function (k) { load(k, force); }); }

  // مصادر الداشبورد الموجودة
  function epState(k) { var E = ep(); return (E && E.state && E.state[k]) || 'idle'; }
  function epEnsure(keys) { var E = ep(); if (E && E.authed) keys.forEach(function (k) { E.ensure(k, null); }); }
  function epReload(keys) { var E = ep(); if (E && E.authed) keys.forEach(function (k) { E.reload(k, null); }); }
  function epPayouts() { var E = ep(); return epState('walletPayouts') === 'ready' && E.data.walletPayouts ? (E.data.walletPayouts.rows || []) : null; }
  function epEscrow() { var E = ep(); return epState('escrow') === 'ready' && E.data.escrow ? (E.data.escrow.sessions || []) : null; }
  function inboxRows() { return epState('inbox') === 'ready' ? (window.INBOX || []) : null; }
  function queue() { var E = ep(); return epState('opsQueue') === 'ready' ? (E.data.opsQueue || null) : null; }
  function isLoading(k) { var s = epState(k); return s === 'idle' || s === 'loading'; }

  function signature() {
    return Object.keys(PATHS).map(function (k) { return srcOf(k).state + srcOf(k).seq; }).join(',') + '|' + ['walletPayouts', 'escrow', 'inbox', 'opsQueue'].map(epState).join(',')
      + '|' + ((window.INBOX || []).length) + '|' + S.period;
  }
  var redrawT = null;
  function changed() {
    try { if (window.V2SHELL && V2SHELL.on && V2SHELL.refresh) V2SHELL.refresh(); } catch (e) {}     // شارات القائمة تلحق بالأعداد الجديدة فورًا
    if (redrawT) return;
    redrawT = setTimeout(function () { redrawT = null; if (!document.getElementById('epModal') || !S.sheetBusy) redraw(); }, 0);
  }

  // ------------------------------------------------------------------ أجزاء مشتركة
  function personLink(name, email) {
    if (!email) return esc(name);
    return '<a class="v3-person" href="' + esc(L.sectionHash('people', 'person', email)) + '" data-person="' + esc(email) + '">' + esc(name) + '</a>';
  }
  function warnStrip(failedLabels, tail) {
    if (!failedLabels.length) return '';
    return '<div class="v3-warn" role="status">تعذّر جلب: ' + esc(failedLabels.join(' · ')) + ' — ' + esc(tail || 'ما يظهر ناقص، وليس معناه أنه لا شيء') + '</div>';
  }
  function noteStrip() { return S.note ? '<div class="v3-ok" role="status">' + esc(S.note) + '</div>' : ''; }
  function setNote(text) {
    S.note = text; clearTimeout(S.noteT);
    S.noteT = setTimeout(function () { S.note = null; redraw(); }, 12000);
  }
  function srcFailed(keys) { return keys.filter(function (k) { return ['error', 'closed'].indexOf(srcState(k)) > -1; }).map(function (k) { return LABEL[k]; }); }
  function epFailed(pairs) { return pairs.filter(function (p) { return epState(p[0]) === 'error'; }).map(function (p) { return p[1]; }); }
  function retryBtn() { return '<button type="button" class="v3-btn2" data-a="retry">أعد المحاولة</button>'; }
  function loadingBlock(t) { return '<div class="v3-empty"><b>…جارٍ جلب ' + esc(t) + '</b></div>'; }
  function unavailable(t, key) {
    return '<div class="v3-empty"><b>' + esc(t) + ': غير متاح بعد</b><p>تعذّر الجلب الآن، فلا تعتبر الشاشة فارغة.</p>' + retryBtn() + '</div>';
  }
  function section(title, hint, body, extra) {
    return '<section class="v3-card' + (extra ? ' ' + extra : '') + '"><header class="v3-ch"><h2>' + esc(title) + '</h2>' + (hint ? '<p>' + esc(hint) + '</p>' : '') + '</header>' + body + '</section>';
  }

  // ------------------------------------------------------------------ نظرة
  function numbersHtml(board) {
    return '<div class="v3-nums">' + board.numbers.map(function (n) {
      return '<article class="v3-num k-' + n.key + (n.na ? ' na' : '') + '"><h3>' + esc(n.label) + '</h3>'
        + '<p class="v3-big' + (n.na ? ' na' : '') + '">' + esc(n.text) + '</p>'
        + (n.others ? '<p class="v3-oth">' + esc(n.others) + '</p>' : '')
        + '<p class="v3-note">' + esc(n.na && n.why ? n.why : n.note) + '</p></article>';
    }).join('') + '</div>';
  }
  function payRow(r) {
    return '<li class="v3-pay" data-id="' + esc(r.id) + '"><div class="v3-pid"><b>' + personLink(r.name, r.email) + '</b><span>' + esc([r.what, r.method].filter(Boolean).join(' · ')) + '</span>'
      + (r.fx ? '<em class="v3-fx">العملة ليست الجنيه — حدّد سعر الصرف قبل التحويل</em>' : '') + '</div>'
      + '<div class="v3-pm"><b class="v3-amt">' + esc(r.amountText) + '</b>' + (r.since ? '<time>' + esc(r.since) + '</time>' : '') + '</div>'
      + '<button type="button" class="v3-btn1" data-a="settle" data-id="' + esc(r.id) + '">سجّل التحويل</button></li>';
  }
  function barsHtml(bars) {
    if (!bars) return unavailable('مصدر الدخل');
    var rows = bars.rows.map(function (r) {
      return '<li><div class="v3-bl"><span>' + esc(r.label) + '</span><b>' + esc(r.text) + '</b></div><div class="v3-bar" role="img" aria-label="' + esc(r.label + ': ' + r.text) + '"><i style="width:' + r.width + '%"></i></div>'
        + (r.others.length ? '<small>بعملة أخرى: ' + esc(r.others.join(' · ')) + '</small>' : '') + '</li>';
    }).join('');
    return '<ul class="v3-bars">' + rows + '</ul><p class="v3-fine">' + esc(bars.note) + '</p>';
  }
  function refundRow(r) {
    var btn;
    if (!r.refundable) btn = '<p class="v3-norefund">' + esc(r.noRefundText || 'الكتب لا تُسترد') + '</p>';
    else btn = '<button type="button" class="v3-btn1" data-a="refund" data-id="' + esc(r.id) + '">' + esc(r.button || 'افتح وقرّر') + '</button>';
    return '<li class="v3-rf" data-id="' + esc(r.id) + '"><div class="v3-pid"><b>' + esc(r.title) + '</b>'
      + '<span>' + (r.person ? personLink(r.who, r.person.email) : esc(r.who)) + (r.since ? ' · ' + esc(r.since) : '') + '</span>'
      + '<div class="v3-brain">' + BRAIN + '<p>' + esc(r.brain) + '</p></div></div>'
      + '<div class="v3-pm"><b class="v3-amt">' + esc(r.amountText) + '</b></div>' + btn + '</li>';
  }
  function disputeRefunds() {
    var rows = inboxRows();
    if (!rows) return null;
    var T = L.v2DisputeTickets(rows.filter(function (r) { return r && !r.fyi; }), { now: now(), queue: queue() });
    S.refundTickets = T.cols.refunds;
    return T.cols.refunds;
  }
  function drawOverview(v) {
    var per = S.period, t = now();
    var revenues = data('revenues'), escrow = epEscrow(), payouts = epPayouts();
    var board = L.v2MoneyBoard({ revenues: revenues, escrow: escrow, payouts: payouts }, per, t);
    var failed = srcFailed(['revenues', 'refunds']).concat(epFailed([['escrow', 'أموال الضمان'], ['walletPayouts', 'طلبات السحب'], ['inbox', 'الدفعات بلا ملف']]));
    var seg = L.PERIODS.map(function (p) {
      return '<button type="button" role="tab" class="v3-pb' + (p.key === per ? ' on' : '') + '" aria-selected="' + (p.key === per) + '" data-a="period" data-p="' + p.key + '">' + esc(p.label) + '</button>';
    }).join('');
    var rows = L.v2PayoutRows(payouts, t);
    var due;
    if (rows === null) due = isLoading('walletPayouts') ? loadingBlock('طلبات السحب') : unavailable('طلبات السحب');
    else if (!rows.length) due = '<p class="v3-none">لا تحويلات مستحقة الآن</p>';
    else due = '<ul class="v3-list">' + rows.slice(0, 5).map(payRow).join('') + '</ul>'
      + '<button type="button" class="v3-link" data-a="goto" data-s="money" data-t="payouts">كل التحويلات (' + esc(U.ar(rows.length)) + ')</button>';
    var inc = L.v2Income(revenues, per, t);
    var bars = (inc || data('income')) ? L.v2IncomeBars(inc, data('income'), per) : null;
    var barsBody = (!bars && srcState('revenues') === 'loading') ? loadingBlock('الدخل') : barsHtml(bars);
    var refunds = L.v2Refunds(data('refunds'), disputeRefunds(), t);
    var refBody;
    if (refunds.failed.length === 2) refBody = isLoading('inbox') || srcState('refunds') === 'loading' ? loadingBlock('الاستردادات') : unavailable('الاستردادات');
    else if (!refunds.rows.length) refBody = '<p class="v3-none">لا استردادات تنتظر قرارك</p>';
    else refBody = '<ul class="v3-list">' + refunds.rows.map(refundRow).join('') + '</ul>';
    if (refunds.failed.length === 1) refBody = warnStrip(refunds.failed, 'القائمة ناقصة') + refBody;
    if (refunds.more) refBody = '<div class="v3-warn" role="status">المعروض أقدم ' + esc(U.ar(refunds.more.shown)) + (refunds.more.total ? ' من ' + esc(U.ar(refunds.more.total)) : '') + ' استردادًا، وبعد البتّ في هذه يظهر الباقي</div>' + refBody;
    v.innerHTML = '<div class="v3" data-board="overview">' + noteStrip() + warnStrip(failed)
      + '<div class="v3-top"><div class="v3-seg" role="tablist" aria-label="الفترة">' + seg + '</div><p class="v3-ptxt">الدخل والمحجوز والمستحق حتى الآن، والأرقام بالجنيه وكل عملة أخرى تظهر لوحدها</p></div>'
      + numbersHtml(board)
      + '<div class="v3-two">' + section('التحويلات المستحقة', 'طلبات سحب بانتظار تسجيل التحويل', due) + section('من أين جاء الدخل', board.period.label, barsBody) + '</div>'
      + section('استردادات تنتظر قرارك', 'الكتب لا تُسترد', refBody, 'v3-wide') + '</div>';
    wire(v);
  }

  // ------------------------------------------------------------------ التحويلات
  function payoutTicket(r) {
    var late = r.at !== Infinity && now() - r.at > 24 * 3600e3;
    return '<article class="v3-t tone-' + (late ? 'late' : 'wait') + '" data-id="' + esc(r.id) + '"><div class="v3-strip"><span class="v3-type">طلب تحويل</span>'
      + (r.since ? '<time class="v3-time" data-since="' + esc(r.at) + '">' + esc(r.since) + '</time>' : '') + '</div>'
      + '<div class="v3-body"><h3>' + personLink(r.name, r.email) + '</h3><p class="v3-amount">' + esc(r.amountText) + '</p>'
      + '<p class="v3-line">' + esc([r.what, r.method].filter(Boolean).join(' · ')) + '</p>' + (r.dest && r.dest !== r.method ? '<p class="v3-line v3-dest" dir="auto">' + esc(r.dest) + '</p>' : '')
      + (r.fx ? '<p class="v3-fxline">العملة ليست الجنيه — حدّد سعر الصرف قبل التحويل</p>' : '')
      + '<div class="v3-acts"><button type="button" class="v3-btn1" data-a="settle" data-id="' + esc(r.id) + '">سجّل التحويل</button></div></div></article>';
  }
  function minPayoutBar() {
    var info = L.v2MinPayout(data('settings'), now());
    if (!info) {
      return '<div class="v3-minbar na"><span>الحد الأدنى للسحب: <b>غير متاح بعد</b></span>' + (srcState('settings') === 'loading' ? '' : retryBtn()) + '</div>';
    }
    return '<div class="v3-minbar"><span>الحد الأدنى للسحب: <b>' + esc(info.text) + '</b></span><button type="button" class="v3-btn2" data-a="minpay">غيّر</button></div>';
  }
  function drawPayouts(v) {
    var t = now(), payouts = epPayouts(), rows = L.v2PayoutRows(payouts, t);
    var paidRes = data('paid'), rejRes = data('rejected');      // رد المسار: {payouts:[…], count}
    var hist = L.v2PayoutHistory(paidRes && Array.isArray(paidRes.payouts) ? paidRes.payouts : null, rejRes && Array.isArray(rejRes.payouts) ? rejRes.payouts : null, t);
    var failed = srcFailed(['settings']).concat(epFailed([['walletPayouts', 'طلبات السحب']]));
    var body;
    if (rows === null) body = isLoading('walletPayouts') ? loadingBlock('طلبات السحب') : unavailable('طلبات السحب');
    else if (!rows.length) body = '<div class="v3-empty"><b>لا تحويلات مستحقة</b><p>كل طلبات السحب حُسمت.</p></div>';
    else body = '<div class="v3-tgrid">' + rows.map(payoutTicket).join('') + '</div>';
    var histBody;
    if (!hist) histBody = srcState('paid') === 'loading' || srcState('rejected') === 'loading' ? loadingBlock('التحويلات المنتهية') : unavailable('التحويلات المنتهية');
    else {
      histBody = warnStrip(hist.failed, 'القائمة ناقصة');
      histBody += hist.rows.length ? '<ul class="v3-hist">' + hist.rows.map(function (h) {
        return '<li class="st-' + h.status + '"><span class="v3-hs">' + esc(h.statusText) + '</span><b>' + personLink(h.name, h.email) + '</b><span class="v3-hm">' + esc(h.amountText) + '</span>'
          + '<time>' + esc(h.when) + '</time>' + (h.ref ? '<small>مرجع التحويل: <span class="v3-ref" dir="ltr">' + esc(h.ref) + '</span></small>' : '') + '</li>';
      }).join('') + '</ul>' : '<p class="v3-none">لا تحويلات منتهية هذا الشهر</p>';
    }
    v.innerHTML = '<div class="v3" data-board="payouts">' + noteStrip() + warnStrip(failed) + minPayoutBar()
      + '<h2 class="v3-h2">بانتظار التحويل <span class="v3-cnt">' + esc(rows ? U.ar(rows.length) : '—') + '</span></h2>' + body
      + section('هذا الشهر', 'ما حُوِّل أو رُفض', histBody, 'v3-wide') + '</div>';
    wire(v);
  }

  // ------------------------------------------------------------------ الإيصالات والمدفوعات العالقة
  function receiptTicket(c) {
    var m = c.primary.money || {};
    return '<article class="v3-t tone-wait" data-id="' + esc(c.id) + '"><div class="v3-strip"><span class="v3-type">إيصال تحويل</span>' + (c.ageText ? '<time class="v3-time">' + esc(c.ageText) + '</time>' : '') + '</div>'
      + '<div class="v3-body"><h3>' + (c.person ? personLink(c.title, c.person.email) : esc(c.title)) + '</h3><p class="v3-amount">' + esc(U.moneyText(m.amount, m.currency)) + '</p>'
      + '<p class="v3-line">' + esc(c.sub) + '</p><p class="v3-line" dir="auto">' + esc(c.reason) + '</p>'
      + (c.link ? '<p class="v3-line"><a class="v3-lnk" href="' + esc(c.link.url) + '" target="_blank" rel="noopener noreferrer">' + esc(c.link.label) + '</a></p>' : '')
      + '<div class="v3-acts two"><button type="button" class="v3-btn1" data-a="rconfirm" data-id="' + esc(c.id) + '">أكّد الدفع</button>'
      + '<button type="button" class="v3-btn2" data-a="rreject" data-id="' + esc(c.id) + '">ارفض</button></div></div></article>';
  }
  function stuckTicket(r) {
    return '<article class="v3-t tone-late v3-stuck"><div class="v3-strip"><span class="v3-type">دفعة عالقة</span>' + (r.ageText ? '<time class="v3-time">' + esc(r.ageText) + '</time>' : '') + '</div>'
      + '<div class="v3-body"><h3>' + (r.person ? personLink(r.name, r.person.email) : esc(r.name)) + '</h3><p class="v3-amount">' + esc(r.amountText) + '</p>'
      + '<p class="v3-line">' + esc([r.kindText, r.title !== r.kindText ? r.title : '', r.provider].filter(Boolean).join(' · ')) + '</p>'
      + '<p class="v3-line v3-mute">دفع بالبطاقة لم يكتمل. للقراءة فقط: تابع مع صاحب الدفع.</p>'
      + (!r.refundable ? '<p class="v3-norefund">' + esc(r.noRefundText) + '</p>' : '')
      + (r.person ? '<div class="v3-acts"><a class="v3-btn2" href="' + esc(L.sectionHash('people', 'person', r.person.email)) + '" data-person="' + esc(r.person.email) + '">افتح الشخص</a></div>' : '')
      + '</div></article>';
  }
  function receiptCards() {
    var rows = inboxRows();
    if (!rows) return null;
    return rows.filter(function (r) { return r && !r.fyi && r.apiKind === 'manual_payment'; }).map(function (r) { return L.v2Card(r, { now: now(), inboxRows: null }); }).filter(Boolean);
  }
  function drawReceipts(v) {
    var cards = receiptCards(), stuck = L.v2Stuck(data('stuck'), now());
    S.receiptCards = cards || [];
    var colA, colB;
    if (cards === null) colA = isLoading('inbox') ? loadingBlock('الإيصالات') : unavailable('الإيصالات');
    else colA = cards.length ? '<div class="v3-tcol">' + cards.map(receiptTicket).join('') + '</div>' : '<p class="v3-none">لا إيصالات تنتظر التأكيد</p>';
    if (!stuck) colB = srcState('stuck') === 'loading' || srcState('stuck') === 'idle' ? loadingBlock('المدفوعات العالقة') : unavailable('المدفوعات العالقة');
    else colB = (stuck.partial ? warnStrip(['باقي القائمة'], 'المعروض أقدم ' + U.ar(stuck.count) + ' دفعة') : '')
      + (stuck.rows.length ? '<div class="v3-tcol">' + stuck.rows.map(stuckTicket).join('') + '</div>' : '<p class="v3-none">لا مدفوعات عالقة</p>');
    var failed = epFailed([['inbox', 'الإيصالات']]);
    v.innerHTML = '<div class="v3" data-board="receipts">' + noteStrip() + warnStrip(failed)
      + '<div class="v3-twocol"><section class="v3-colbox"><h2 class="v3-h2">إيصالات تنتظر التأكيد <span class="v3-cnt">' + esc(cards ? U.ar(cards.length) : '—') + '</span></h2>' + colA + '</section>'
      + '<section class="v3-colbox"><h2 class="v3-h2">مدفوعات بالبطاقة عالقة <span class="v3-cnt">' + esc(stuck ? U.ar(stuck.count) : '—') + '</span></h2>'
      + (stuck ? '<p class="v3-fine">دفعات بدأها أصحابها ولم تكتمل منذ أكثر من ' + esc(U.ar(stuck.afterHours)) + ' ساعة</p>' + (stuck.deliveryNote ? '<p class="v3-fine">' + esc(stuck.deliveryNote) + '</p>' : '') : '') + colB + '</section></div></div>';
    wire(v);
  }

  // ------------------------------------------------------------------ الأسعار
  function priceRow(kind, r) {
    return '<li class="v3-pr" data-id="' + esc(r.id) + '"><div class="v3-pid"><b>' + esc(r.title) + '</b><span class="v3-vis ' + (r.visible ? 'on' : 'off') + '">ظاهر للناس: ' + (r.visible ? 'نعم' : 'لا') + '</span></div>'
      + '<p class="v3-mins">' + esc(r.minText) + '</p>'
      + '<button type="button" class="v3-btn2" data-a="price" data-kind="' + kind + '" data-id="' + esc(r.id) + '">عدّل</button></li>';
  }
  function priceBlock(kind, title, key) {
    var st = srcState(key), res = L.v2Prices(data(key));
    var body;
    if (st === 'closed' && kind === 'course') body = '<div class="v3-empty"><b>الدورات لسه مقفولة</b><p>أسعار الدورات تظهر هنا حين تُفتح من المنصة.</p></div>';
    else if (st === 'closed') body = '<div class="v3-empty"><b>متجر الكتب لم يُفتح بعد</b><p>أسعار الكتب تظهر هنا حين يُفتح المتجر.</p></div>';
    else if (!res) body = st === 'loading' || st === 'idle' ? loadingBlock(title) : unavailable(title);
    else body = res.rows.length ? '<ul class="v3-list">' + res.rows.map(function (r) { return priceRow(kind, r); }).join('') + '</ul>' : '<p class="v3-none">لا أعمال بعد</p>';
    return section(title, kind === 'book' ? 'أقل سعر في كل بلد' : 'أقل سعر في كل بلد، من المنصة', body);
  }
  function drawPrices(v) {
    v.innerHTML = '<div class="v3" data-board="prices">' + noteStrip() + '<p class="v3-ptxt v3-lead">الأسعار تُعدَّل من هنا فقط، وكل تعديل يمرّ على ورقة تراجع فيها ما سيتغير قبل التأكيد</p>'
      + priceBlock('book', 'الكتب', 'pricesBook') + priceBlock('course', 'الدورات', 'pricesCourse') + '</div>';
    wire(v);
  }

  // ------------------------------------------------------------------ النسب والإعدادات
  function drawShares(v) {
    var view = L.v2SharesView(data('shares')), info = L.v2MinPayout(data('settings'), now());
    var body;
    if (!view) body = srcState('shares') === 'loading' || srcState('shares') === 'idle' ? loadingBlock('جدول النسب') : unavailable('جدول النسب');
    else {
      var lines = view.lines.map(function (l) {
        return '<li class="v3-sh"><div class="v3-pid"><b>' + esc(l.title) + '</b><span>' + esc(l.text) + '</span>' + (l.note ? '<small>' + esc(l.note) + '</small>' : '') + '</div>'
          + (l.editable ? '<button type="button" class="v3-btn2" data-a="share" data-k="' + l.key + '">عدّل</button>' : '') + '</li>';
      }).join('');
      var ladder = '<li class="v3-sh v3-lad"><div class="v3-pid"><b>القضايا حسب القيمة</b><table class="v3-ladder"><thead><tr><th>قيمة القضية</th><th>صاحب العمل</th><th>المنصة</th></tr></thead><tbody>'
        + view.ladder.map(function (r) { return '<tr><td>' + esc(r.upTo) + '</td><td>' + esc(r.ownerText) + '</td><td>' + esc(r.platformText) + '</td></tr>'; }).join('') + '</tbody></table></div>'
        + '<button type="button" class="v3-btn2" data-a="share" data-k="ladder">عدّل</button></li>';
      body = '<p class="v3-floor">' + esc(view.floorText) + '</p><ul class="v3-list">' + lines + ladder + '</ul>';
    }
    var hist = view ? L.v2SharesHistory(data('shares'), now()) : null;
    var histBody;
    if (!hist) histBody = view ? '<p class="v3-none">لا سجل بعد</p>' : '';
    else histBody = hist.length ? '<ul class="v3-log">' + hist.map(function (h) {
      return '<li><div><b>' + esc(h.by || 'الإدارة') + '</b><time>' + esc(h.when) + '</time></div>' + (h.lines.length ? '<ul>' + h.lines.map(function (x) {
        return '<li>' + esc(x.label) + ': <s>' + esc(x.from) + '</s> ← <b>' + esc(x.to) + '</b></li>'; }).join('') + '</ul>' : '<p class="v3-fine">لا فروق ظاهرة</p>') + '</li>';
    }).join('') + '</ul>' : '<p class="v3-none">لا تعديلات بعد</p>';
    var minBody;
    if (!info) minBody = srcState('settings') === 'loading' || srcState('settings') === 'idle' ? loadingBlock('الحد الأدنى للسحب') : unavailable('الحد الأدنى للسحب');
    else minBody = '<div class="v3-sh"><div class="v3-pid"><b>الحد الأدنى للسحب</b><span>' + esc(info.text) + '</span><small>ويسحب صاحب الحساب رصيده كاملًا في أي وقت</small>' + notesHtml(info.notes) + '</div><button type="button" class="v3-btn2" data-a="minpay">غيّر</button></div>';
    var mh = info && info.history.length ? '<ul class="v3-log">' + info.history.slice(0, 5).map(function (h) {
      return '<li><div><b>' + esc(h.by || 'الإدارة') + '</b><time>' + esc(h.when) + '</time></div><ul><li>الحد الأدنى للسحب: <s>' + esc(h.from) + '</s> ← <b>' + esc(h.to) + '</b></li></ul></li>'; }).join('') + '</ul>' : '';
    v.innerHTML = '<div class="v3" data-board="shares">' + noteStrip()
      + section('النسب', 'كل بيع يقسم الأموال بين صاحب العمل والمنصة بهذه الأرقام', body)
      + section('إعدادات السحب', '', minBody + mh)
      + section('سجل التعديلات', 'من عدّل ومتى، وما كان وما صار', histBody, 'v3-wide') + '</div>';
    wire(v);
  }

  // ------------------------------------------------------------------ إعلانات الأعمال
  function drawAds(v) {
    var rows = L.v2AdsLedger(data('ads'), now());
    var body;
    if (!rows) body = srcState('ads') === 'closed' ? '<div class="v3-empty"><b>أرصدة الإعلانات غير متاحة بعد</b></div>' : (srcState('ads') === 'loading' || srcState('ads') === 'idle' ? loadingBlock('أرصدة الإعلانات') : unavailable('أرصدة الإعلانات'));
    else if (!rows.length) body = '<div class="v3-empty"><b>لا أرصدة إعلانات بعد</b><p>يظهر هنا كل عمل أودع صاحبه رصيدًا للإعلان.</p></div>';
    else body = '<ul class="v3-list">' + rows.map(function (r) {
      return '<li class="v3-ad"><button type="button" class="v3-adrow" data-a="ad" data-id="' + esc(r.id) + '" data-kind="' + esc(r.kind) + '"><div class="v3-pid"><b>' + esc(r.title) + '</b>'
        + '<span>' + esc(r.kindText) + (r.ownerEmail ? ' · ' + esc(r.ownerEmail) : '') + '</span></div><div class="v3-pm"><b class="v3-amt">' + esc(r.balanceText) + '</b><time>آخر حركة: ' + esc(r.last) + '</time></div></button></li>';
    }).join('') + '</ul>';
    v.innerHTML = '<div class="v3" data-board="ads">' + noteStrip() + '<p class="v3-ptxt v3-lead">رصيد كل عمل أودعه صاحبه للإعلان. للقراءة فقط: اضغط على عمل لترى حركاته</p>' + body + '</div>';
    wire(v);
  }

  // ------------------------------------------------------------------ الكتب: مراجعة العروض
  function offerCard(o) {
    return '<article class="v3-t tone-wait v3-offer" data-id="' + esc(o.id) + '"><div class="v3-strip"><span class="v3-type">عرض ' + esc(o.typeText) + ' للمراجعة</span>' + (o.since ? '<time class="v3-time">' + esc(o.since) + '</time>' : '') + '</div>'
      + '<div class="v3-body"><h3>' + esc(o.title) + '</h3><p class="v3-line">' + (o.ownerEmail ? personLink(o.ownerName, o.ownerEmail) : esc(o.ownerName)) + (o.agreementText ? ' · ' + esc(o.agreementText) : '') + '</p>'
      + (o.about ? '<p class="v3-line v3-mute">' + esc(o.about) + '</p>' : '')
      + '<p class="v3-amount">' + (o.suggestedText ? 'السعر المقترح: ' + esc(o.suggestedText) : '<span class="v3-mute">لم يقترح سعرًا</span>') + '</p>'
      + (o.brain ? '<div class="v3-brain">' + BRAIN + '<p>' + esc(o.brain) + '</p></div>' : '')
      + '<div class="v3-acts two"><button type="button" class="v3-btn1" data-a="oapprove" data-id="' + esc(o.id) + '">اعتمد بالأسعار دي</button>'
      + '<button type="button" class="v3-btn2" data-a="oreject" data-id="' + esc(o.id) + '">ارفض</button></div></div></article>';
  }
  function offerRows() { return L.v2OffersQueue(data('offers'), data('pricesBook'), now()); }
  function drawOffers(v) {
    var rows = offerRows();
    S.offerRows = rows || [];
    var body;
    if (!rows) body = srcState('offers') === 'closed' ? '<div class="v3-empty"><b>متجر الكتب لم يُفتح بعد</b><p>تظهر العروض هنا حين يُفتح المتجر.</p></div>' : (srcState('offers') === 'loading' || srcState('offers') === 'idle' ? loadingBlock('عروض الكتب') : unavailable('عروض الكتب'));
    else if (!rows.length) body = '<div class="v3-empty"><b>لا عروض تنتظر المراجعة</b><p>كل ما وصل حُسم.</p></div>';
    else body = '<div class="v3-tgrid">' + rows.map(offerCard).join('') + '</div>';
    var noPrices = rows && rows.length && !data('pricesBook') && srcState('pricesBook') !== 'loading' ? warnStrip(['أسعار الكتب'], 'لا مقارنة بمتوسط الأسعار الآن') : '';
    v.innerHTML = '<div class="v3" data-board="offers">' + noteStrip() + noPrices + body + '</div>';
    wire(v);
  }
  function drawRequests(v) {
    var res = L.v2Requests(data('requests'), now());
    var body;
    function gRow(g, approved) {
      return '<li class="v3-rq" data-id="' + esc(g.firstId) + '"><div class="v3-pid"><b>' + esc(g.topic) + '</b><span>' + esc(g.typeText) + ' · ' + esc(g.countText) + (g.lastText ? ' · آخر طلب ' + esc(g.lastText) : '') + '</span></div>'
        + (approved ? '<span class="v3-vis on">معتمد</span>' : '<div class="v3-acts two"><button type="button" class="v3-btn1" data-a="rqok" data-key="' + esc(g.key) + '">اعتمد</button><button type="button" class="v3-btn2" data-a="rqhide" data-key="' + esc(g.key) + '">اخفِ</button></div>') + '</li>';
    }
    if (!res) body = srcState('requests') === 'closed' ? '<div class="v3-empty"><b>متجر الكتب لم يُفتح بعد</b></div>' : (srcState('requests') === 'loading' || srcState('requests') === 'idle' ? loadingBlock('طلبات القرّاء') : unavailable('طلبات القرّاء'));
    else {
      S.reqGroups = res.open.concat(res.approved);
      body = section('تنتظر قرارك', 'اعتمادها يُظهرها للأعضاء في «المطلوب الآن»', res.open.length ? '<ul class="v3-list">' + res.open.map(function (g) { return gRow(g, false); }).join('') + '</ul>' : '<p class="v3-none">لا طلبات جديدة</p>')
        + section('معتمدة', 'ظاهرة للأعضاء', res.approved.length ? '<ul class="v3-list">' + res.approved.map(function (g) { return gRow(g, true); }).join('') + '</ul>' : '<p class="v3-none">لا طلبات معتمدة</p>');
    }
    v.innerHTML = '<div class="v3" data-board="requests">' + noteStrip() + '<p class="v3-ptxt v3-lead">الطلبات المتشابهة مجمّعة بعددها. الأكثر طلبًا أولًا</p>' + body + '</div>';
    wire(v);
  }

  // ------------------------------------------------------------------ الأوراق (نوافذ التعديل والتأكيد)
  // رسالة المنصة تُعرض كما هي (هي اللي بتشرح الرفض)، والأرقام اللاتينية فيها بتتحوّل للعربية.
  function arDigits(t) { return String(t).replace(/\d/g, function (d) { return '٠١٢٣٤٥٦٧٨٩'.charAt(+d); }); }
  function errMsg(e) {
    if (e && e.status === 401) return SESSION_AR;
    var d = (e && e.data) || {};
    if (typeof d.error === 'string' && d.error) return arDigits(d.error);
    return FAIL_AR;
  }
  function openSheet(title, html) {
    if (typeof window.openModal !== 'function') return null;
    var s = window.openModal(title, '<div class="v3m">' + html + '</div>');
    var x = q('[data-x]', s);
    if (x) x.onclick = function () { if (!s.dataset.busy) window.closeModal(); };
    s.onclick = function (e) { if (e.target === s && !s.dataset.busy) window.closeModal(); };
    return s;
  }
  function diffTable(lines) {
    return '<table class="v3-diff"><thead><tr><th>البند</th><th>الآن</th><th>بعد التعديل</th></tr></thead><tbody>' + lines.map(function (l) {
      return '<tr><td>' + esc(l.label) + '</td><td>' + esc(l.from) + '</td><td><b>' + esc(l.to) + '</b></td></tr>'; }).join('') + '</tbody></table>';
  }
  // ورقة بمرحلتين: النموذج ثم «راجع التغيير» (قبل ⇒ بعد) ثم «أكّد». o: {title, form(html), wire(s), collect(s)→{ok,payload,error}, review(payload)→{lead,lines,changed},
  //   send(payload)→Promise, btnReview, btnConfirm, busy, onOk(res), retryNote}
  function twoStage(o) {
    var s = openSheet(o.title, '<div class="v3-stage" data-stage="form">' + o.form + '<div id="v3err" role="alert"></div>'
      + '<div class="acts"><button type="button" class="btn btn-primary" id="v3_review">' + esc(o.btnReview || 'راجع التغيير') + '</button><button type="button" class="btn btn-ghost" id="v3_cancel">إلغاء</button></div></div>');
    if (!s) return;
    S.sheetBusy = false;
    var stage = q('.v3-stage', s), formHtml = stage.innerHTML;
    var payload = null;
    function showErr(msg) { var e = q('#v3err', s); if (e) e.innerHTML = msg ? '<div class="v3-err">' + esc(msg) + '</div>' : ''; }
    function bindForm() {
      q('#v3_cancel', s).onclick = function () { window.closeModal(); };
      q('#v3_review', s).onclick = function () {
        var c = o.collect(s);
        if (!c.ok) { showErr(c.error); return; }
        var r = o.review(c.payload);
        if (!r.changed) { showErr('لم تغيّر أي شيء'); return; }
        payload = c.payload;
        stage.setAttribute('data-stage', 'review');
        stage.innerHTML = '<p class="mc-lead">' + (r.lead || 'راجع ما سيتغير قبل التأكيد') + '</p>' + diffTable(r.lines) + (r.extra || '') + '<div id="v3err" role="alert"></div>'
          + '<div class="acts"><button type="button" class="btn btn-primary" id="v3_go">' + esc(o.btnConfirm || 'أكّد التعديل') + '</button><button type="button" class="btn btn-ghost" id="v3_back">رجوع للتعديل</button></div>';
        q('#v3_back', s).onclick = function () { stage.setAttribute('data-stage', 'form'); stage.innerHTML = formHtml; restore(); };
        var go = q('#v3_go', s);
        go.onclick = function () {
          if (go.dataset.busy) return;
          go.dataset.busy = '1'; s.dataset.busy = '1'; S.sheetBusy = true; go.disabled = true; q('#v3_back', s).disabled = true; go.textContent = o.busy || 'جارٍ التنفيذ…'; showErr('');
          Promise.resolve(o.send(payload)).then(function (res) {
            delete s.dataset.busy; S.sheetBusy = false;
            window.closeModal();
            o.onOk(res || {});
          }).catch(function (e) {
            delete s.dataset.busy; S.sheetBusy = false; delete go.dataset.busy; go.disabled = false; q('#v3_back', s).disabled = false; go.textContent = o.btnConfirm || 'أكّد التعديل';
            var msg = errMsg(e);
            var refused = e && (e.status === 422 || e.status === 400);
            var stale = e && e.status === 409;
            showErr((refused ? 'رفضت المنصة هذا التعديل: ' : '') + msg + (refused ? ' — عدّل الرقم ثم راجع من جديد' : '') + (stale ? ' — أغلق هذه الورقة وافتحها من جديد' : ''));
            if (stale || (e && e.data && e.data.no_reply)) { o.onStale && o.onStale(); }
          });
        };
      };
    }
    // إعادة ملء الخانات بعد الرجوع (المحتوى أعيد رسمه من نص النموذج الأصلي، فنكتب فيه آخر ما كتبه المستخدم)
    var lastValues = null;
    function restore() {
      bindForm(); if (o.wire) o.wire(s);
      if (lastValues) o.fill(s, lastValues);
    }
    var origCollect = o.collect;
    o.collect = function (sheet) { var c = origCollect(sheet); if (c.ok && o.snapshot) lastValues = o.snapshot(sheet); return c; };
    bindForm(); if (o.wire) o.wire(s);
    return s;
  }
  function numInput(id, val, attrs) {
    return '<input ' + (id ? 'id="' + id + '" ' : '') + 'type="text" inputmode="decimal" autocomplete="off" dir="ltr" value="' + esc(val) + '" ' + (attrs || '') + '>';
  }

  // —— ورقة سعر عمل (تعديل أسعار موجودة، أو أسعار اعتماد عرض كتاب)
  function priceFields(form, cells) {
    return form.versions.map(function (v) {
      return '<fieldset class="v3-vers"><legend>' + esc(v.label) + '</legend>' + form.countries.map(function (c) {
        return '<label class="v3-prow"><span class="v3-pc">' + esc(c.label) + '</span>' + numInput('', (cells[v.key] || {})[c.key] || '', 'data-v="' + v.key + '" data-c="' + c.key + '" aria-label="' + esc(v.label + ' ' + c.label) + '"')
          + '<span class="v3-cur">' + esc(c.currencyName) + '</span></label>';
      }).join('') + '</fieldset>';
    }).join('');
  }
  function readCells(s) {
    var cells = {};
    qa('input[data-v]', s).forEach(function (i) { var v = i.getAttribute('data-v'), c = i.getAttribute('data-c'); (cells[v] = cells[v] || {})[c] = i.value; });
    return cells;
  }
  function fillCells(s, vals) {
    qa('input[data-v]', s).forEach(function (i) { var r = (vals.cells[i.getAttribute('data-v')] || {})[i.getAttribute('data-c')]; if (r != null) i.value = r; });
    var vis = q('#v3_vis', s); if (vis && vals.visible != null) vis.checked = vals.visible;
    var nt = q('#v3_note', s); if (nt && vals.note != null) nt.value = vals.note;
  }
  function openPrice(kind, id, title) {
    var E = ep();
    var s0 = openSheet('أسعار: ' + title, '<p class="v3-load">…جارٍ جلب الأسعار</p>');
    if (!s0 || !E) return;
    E.api('/v2/prices/' + kind + '/' + encodeURIComponent(id)).then(function (resp) {
      var form = L.v2PriceForm(resp);
      if (!document.body.contains(s0)) return;
      window.closeModal();
      if (!form) { notifyFail('تعذّر قراءة أسعار هذا العمل'); return; }
      var cells0 = {};
      form.versions.forEach(function (v) { cells0[v.key] = v.cells; });
      twoStage({
        title: 'أسعار: ' + form.title,
        form: '<p class="mc-lead">اكتب السعر في كل بلد بعملته. اترك الخانة فارغة إن لم يكن للعمل سعر في هذا البلد.</p>' + priceFields(form, cells0)
          + '<label class="tg v3-togg"><input type="checkbox" id="v3_vis"' + (form.visible ? ' checked' : '') + '> ظاهر للناس</label>'
          + '<div class="fld"><label for="v3_note">ملاحظة (اختيارية)</label><textarea id="v3_note" rows="2" maxlength="300"></textarea></div>',
        collect: function (s) {
          var cells = readCells(s), vis = !!q('#v3_vis', s).checked;
          var built = L.v2PriceBuild(form, { visible: vis, cells: cells });
          if (!built.ok) return { ok: false, error: built.error };
          return { ok: true, payload: { built: built, note: (q('#v3_note', s).value || '').trim() } };
        },
        snapshot: function (s) { return { cells: readCells(s), visible: !!q('#v3_vis', s).checked, note: q('#v3_note', s).value }; },
        fill: fillCells,
        review: function (p) { var d = L.v2PriceDiff(form, p.built); return { lines: d.lines, changed: d.changed, lead: 'ستغيّر أسعار <b>' + esc(form.title) + '</b>. راجع ما سيتغير:' }; },
        busy: 'جارٍ الحفظ…', btnConfirm: 'أكّد التعديل',
        send: function (p) {
          return E.api('/v2/prices/' + kind + '/' + encodeURIComponent(id), { method: 'PUT', body: { versions: p.built.versions, visible: p.built.visible, note: p.note, rev: form.rev, title: form.title, confirmed: true } });
        },
        onOk: function () { setNote('حُفظت أسعار «' + form.title + '»'); load(kind === 'book' ? 'pricesBook' : 'pricesCourse', true); redraw(); },
        onStale: function () { load(kind === 'book' ? 'pricesBook' : 'pricesCourse', true); }
      });
    }).catch(function (e) {
      if (document.body.contains(s0)) window.closeModal();
      notifyFail(e && e.status === 404 ? 'هذا النوع لم يُفتح بعد' : 'تعذّر جلب أسعار هذا العمل');
    });
  }
  function notifyFail(msg) { try { (window.toast || window.notify || function () {})(msg); } catch (e) {} }

  // —— اعتماد عرض كتاب بالأسعار (قابلة للتعديل)
  function pricesFormFor(kind) {
    var list = data(kind === 'book' ? 'pricesBook' : 'pricesCourse');
    if (!list) return null;
    var resp = { prices: { kind: 'book', id: '', title: '', visible: false, rev: 0, versions: {} }, countries: list.countries, currencies: list.currencies, versions_allowed: ['read', 'pdf'] };
    return L.v2PriceForm(resp);
  }
  function openApprove(offer, cb) {
    var E = ep(), form = pricesFormFor('book');
    if (!form) {
      load('pricesBook', true);
      notifyFail('تعذّر جلب الدول والعملات الآن — حاول بعد لحظات');
      return;
    }
    var cells0 = L.v2OfferPrefill(offer, form);
    var base = {};
    form.versions.forEach(function (v) { base[v.key] = {}; form.countries.forEach(function (c) { base[v.key][c.key] = ''; }); });
    var formBefore = Object.assign({}, form, { versions: form.versions.map(function (v) { return Object.assign({}, v, { cells: base[v.key] }); }) });
    twoStage({
      title: 'اعتماد: ' + offer.title,
      form: '<p class="mc-lead">أسعار البيع لـ«' + esc(offer.title) + '»' + (offer.suggestedText ? ' — السعر الذي اقترحه صاحب العرض: <b>' + esc(offer.suggestedText) + '</b>' : '') + '. عدّل الأرقام كما تريد قبل الاعتماد.</p>'
        + priceFields(form, cells0) + '<p class="v3-fine">لازم سعر القراءة في بلد واحد على الأقل. ويظهر العمل للناس إذا كان له سعر في «باقي البلاد».</p>',
      collect: function (s) {
        var built = L.v2PriceBuild(form, { visible: true, cells: readCells(s) });
        if (!built.ok) return { ok: false, error: built.error };
        if (!Object.keys(built.versions.read || {}).length) return { ok: false, error: 'اكتب سعر القراءة في بلد واحد على الأقل' };
        return { ok: true, payload: { built: built } };
      },
      snapshot: function (s) { return { cells: readCells(s) }; },
      fill: fillCells,
      review: function (p) {
        var d = L.v2PriceDiff(Object.assign({}, formBefore, { visible: false }), Object.assign({}, p.built, { visible: false }));
        return { lines: d.lines, changed: d.changed, lead: 'ستعتمد <b>' + esc(offer.title) + '</b> وتنشره بهذه الأسعار:' };
      },
      btnReview: 'راجع الأسعار', btnConfirm: 'اعتمد العرض', busy: 'جارٍ الاعتماد…',
      send: function (p) {
        var versions = {};
        Object.keys(p.built.versions).forEach(function (v) { versions[v] = { pricing: p.built.versions[v] }; });
        return E.api('/v2/book-offers/' + encodeURIComponent(offer.id) + '/approve', { method: 'POST', body: { versions: versions, confirmed: true } });
      },
      onOk: function () { load('offers', true); load('pricesBook', true); (cb || function () { setNote('اعتُمد «' + offer.title + '»'); redraw(); })('اعتُمد «' + offer.title + '»'); },
      onStale: function () { load('offers', true); }
    });
  }
  function openReject(offer, cb) {
    var E = ep();
    var s = openSheet('رفض: ' + offer.title, '<p class="mc-lead">سيُرفض عرض <b>' + esc(offer.title) + '</b> ويصل السبب الذي تكتبه إلى صاحب العرض.</p>'
      + '<div class="fld"><label for="v3_reason">سبب الرفض (مطلوب — يصل لصاحب العرض)</label><textarea id="v3_reason" rows="3" maxlength="500"></textarea></div><div id="v3err" role="alert"></div>'
      + '<div class="acts"><button type="button" class="btn btn-human" id="v3_go" disabled>ارفض العرض</button><button type="button" class="btn btn-ghost" id="v3_x">رجوع</button></div>');
    if (!s) return;
    var go = q('#v3_go', s), f = q('#v3_reason', s);
    f.addEventListener('input', function () { if (!go.dataset.busy) go.disabled = !f.value.trim(); });
    q('#v3_x', s).onclick = function () { if (!s.dataset.busy) window.closeModal(); };
    go.onclick = function () {
      if (go.dataset.busy || !f.value.trim()) return;
      go.dataset.busy = '1'; s.dataset.busy = '1'; go.disabled = true; go.textContent = 'جارٍ الرفض…';
      E.api('/v2/book-offers/' + encodeURIComponent(offer.id) + '/reject', { method: 'POST', body: { reason: f.value.trim(), confirmed: true } }).then(function () {
        delete s.dataset.busy; window.closeModal(); load('offers', true);
        (cb || function (t) { setNote(t); redraw(); })('رُفض «' + offer.title + '»');
      }).catch(function (e) {
        delete s.dataset.busy; delete go.dataset.busy; go.disabled = !f.value.trim(); go.textContent = 'ارفض العرض';
        q('#v3err', s).innerHTML = '<div class="v3-err">' + esc(errMsg(e)) + '</div>';
      });
    };
    setTimeout(function () { try { f.focus(); } catch (e) {} }, 30);
  }

  // —— الحد الأدنى للسحب
  function notesHtml(list) {
    return list && list.length ? '<ul class="v3-notes">' + list.map(function (n) { return '<li>' + esc(n) + '</li>'; }).join('') + '</ul>' : '';
  }
  function openMinPay() {
    var E = ep(), info = L.v2MinPayout(data('settings'), now());
    if (!info) { load('settings', true); notifyFail('تعذّر جلب الحد الأدنى الآن'); return; }
    twoStage({
      title: 'الحد الأدنى للسحب',
      form: '<p class="mc-lead">الحد الأدنى الآن <b>' + esc(info.text) + '</b>. أقل مبلغ يسحبه صاحب الحساب في المرة الواحدة، وله أن يسحب رصيده كاملًا مهما كان.</p>'
        + '<div class="fld"><label for="v3_min">الحد الأدنى الجديد (بالجنيه، بين ' + esc(U.fmt(info.min)) + ' و' + esc(U.fmt(info.max)) + ')</label>' + numInput('v3_min', String(info.value)) + '</div>',
      collect: function (s) { var r = L.v2MinPayoutInput(q('#v3_min', s).value, info); return r.ok ? { ok: true, payload: r.value } : { ok: false, error: r.error }; },
      snapshot: function (s) { return { cells: {}, min: q('#v3_min', s).value }; },
      fill: function (s, vals) { var i = q('#v3_min', s); if (i && vals.min != null) i.value = vals.min; },
      review: function (v) { return { changed: v !== info.value, lines: [{ label: 'الحد الأدنى للسحب', from: info.text, to: U.moneyText(v, 'EGP') }], lead: 'ستغيّر الحد الأدنى للسحب. يسري على الطلبات الجديدة فقط:',
                                      extra: notesHtml(info.notes) }; },
      busy: 'جارٍ الحفظ…',
      send: function (v) { return E.api('/v2/money/settings', { method: 'PUT', body: { withdraw_min: v, rev: info.rev, confirmed: true } }); },
      onOk: function () { setNote('تغيّر الحد الأدنى للسحب'); load('settings', true); redraw(); },
      onStale: function () { load('settings', true); }
    });
  }

  // —— النسب
  var SH_TITLE = { books: 'نسبة الكتب', books_ads: 'نسبة الكتب مع إعلانات', ladder: 'القضايا حسب القيمة', affiliate: 'عمولة الإحالة' };
  function openShares(kind) {
    var E = ep(), view = L.v2SharesView(data('shares'));
    if (!view) { load('shares', true); notifyFail('تعذّر جلب جدول النسب الآن'); return; }
    var t = view.table, floors = view.floors, body = '';
    if (kind === 'books') body = '<div class="fld"><label for="v3_bo">نصيب صاحب العمل (٪)</label>' + numInput('v3_bo', String(t.books.normal.owner)) + '</div><p class="v3-fine" id="v3_bp"></p>';
    else if (kind === 'books_ads') body = '<div class="fld"><label for="v3_bao">نصيب صاحب العمل في الكتب مع إعلانات (٪)</label>' + numInput('v3_bao', String(t.books.ads.owner)) + '</div><p class="v3-fine" id="v3_bap"></p>';
    else if (kind === 'ladder') body = view.ladder.map(function (r, i) {
      return '<div class="fld"><label for="v3_l' + i + '">نصيب المنصة (٪) — ' + esc(r.upTo) + '</label>' + numInput('v3_l' + i, String(r.platform), 'data-l="' + i + '"') + '</div>';
    }).join('');
    else body = '<div class="fld"><label for="v3_af">عمولة الإحالة (٪ من قيمة البيع)</label>' + numInput('v3_af', String(t.affiliate.rate)) + '</div><p class="v3-fine">تُخصم من الطرفين بنسبة نصيب كلٍّ منهما.</p>';
    function input(s) {
      if (kind === 'books') return { booksOwner: q('#v3_bo', s).value };
      if (kind === 'books_ads') return { booksAdsOwner: q('#v3_bao', s).value };
      if (kind === 'ladder') return { ladder: qa('input[data-l]', s).map(function (i) { return i.value; }) };
      return { affiliateRate: q('#v3_af', s).value };
    }
    function wireLive(s) {
      function sync() {
        var o = q('#v3_bo', s), p = q('#v3_bp', s), o2 = q('#v3_bao', s), p2 = q('#v3_bap', s);
        if (o && p) { var n = U.parseAmount(o.value); p.textContent = n == null || isNaN(n) ? '' : 'نصيب المنصة: ' + U.ar(100 - n) + '٪'; }
        if (o2 && p2) { var n2 = U.parseAmount(o2.value); p2.textContent = n2 == null || isNaN(n2) ? '' : 'نصيب المنصة: ' + U.ar(100 - n2) + '٪'; }
      }
      qa('input', s).forEach(function (i) { i.addEventListener('input', sync); }); sync();
    }
    twoStage({
      title: SH_TITLE[kind] || 'النسب',
      form: '<p class="mc-lead">' + esc(view.floorText) + '. إن كسر الرقم هذا الحد ترفضه المنصة وتعرض سببًا.</p>' + body,
      wire: wireLive,
      collect: function (s) { var r = L.v2SharesChanges(t, input(s)); return r.ok ? { ok: true, payload: r } : { ok: false, error: r.error }; },
      snapshot: function (s) { return { cells: {}, raw: input(s) }; },
      fill: function (s, vals) {
        var r = vals.raw || {};
        var set = function (id, v) { var i = q(id, s); if (i && v != null) i.value = v; };
        set('#v3_bo', r.booksOwner); set('#v3_bao', r.booksAdsOwner); set('#v3_af', r.affiliateRate);
        (r.ladder || []).forEach(function (v, i) { set('#v3_l' + i, v); }); wireLive(s);
      },
      review: function (r) { var d = L.v2SharesDiff(t, r.after); return { lines: d.lines, changed: d.changed, lead: 'ستغيّر النسب. يسري على البيوع الجديدة فقط، وما بيع قبل اليوم يبقى بنسبته:' }; },
      busy: 'جارٍ الحفظ…',
      send: function (r) { return E.api('/v2/shares', { method: 'PUT', body: { changes: r.changes, version: view.version, confirmed: true } }); },
      onOk: function () { setNote('تغيّرت النسب'); load('shares', true); redraw(); },
      onStale: function () { load('shares', true); }
    });
  }

  // —— حركات رصيد عمل
  function openAd(id, kind) {
    var E = ep(), row = (L.v2AdsLedger(data('ads'), now()) || []).filter(function (r) { return r.id === id; })[0];
    // جسر المنصة لا يعرف إلا الكتب: ردّه لعمل من نوع آخر ٢٠٠ فارغ، وهو صفر كاذب. فلا نسأله عن الدورات أصلًا.
    if (kind === 'course') {
      var cs = openSheet('رصيد الإعلانات: ' + (row ? row.title : ''), '<p class="v3-load"></p>');
      if (!cs) return;
      q('.v3m', cs).innerHTML = '<div class="v3-err">حركات الدورات غير متاحة بعد</div>' + (row ? '<p class="mc-lead">الرصيد الآن: <b>' + esc(row.balanceText) + '</b></p>' : '')
        + '<div class="acts"><button type="button" class="btn btn-ghost" id="v3_x">إغلاق</button></div>';
      q('#v3_x', cs).onclick = function () { window.closeModal(); };
      return;
    }
    var s = openSheet('رصيد الإعلانات: ' + (row ? row.title : ''), '<p class="v3-load">…جارٍ جلب الحركات</p>');
    if (!s || !E) return;
    E.api('/v2/ads-ledger/' + encodeURIComponent(id) + '?kind=' + encodeURIComponent(kind || 'book')).then(function (resp) {
      if (!document.body.contains(s)) return;
      var res = L.v2AdsEntries(resp, now());
      var b = q('.v3m', s);
      if (!res) { b.innerHTML = '<div class="v3-err">تعذّر قراءة حركات هذا العمل</div><div class="acts"><button type="button" class="btn btn-ghost" id="v3_x">إغلاق</button></div>'; q('#v3_x', s).onclick = function () { window.closeModal(); }; return; }
      b.innerHTML = '<p class="mc-lead">الرصيد الآن: <b>' + esc([res.balance.main].concat(res.balance.others).join(' · ')) + '</b></p>'
        + (res.rows.length ? '<ul class="v3-ent">' + res.rows.map(function (e) {
          return '<li><span>' + esc(e.entry) + '</span><b>' + esc(e.sign + ' ' + e.amountText) + '</b><time>' + esc(e.when) + '</time></li>'; }).join('') + '</ul>' : '<p class="v3-none">لا حركات</p>')
        + '<p class="v3-fine">للقراءة فقط</p><div class="acts"><button type="button" class="btn btn-ghost" id="v3_x">إغلاق</button></div>';
      q('#v3_x', s).onclick = function () { window.closeModal(); };
    }).catch(function (e) {
      if (!document.body.contains(s)) return;
      var b = q('.v3m', s);
      b.innerHTML = '<div class="v3-err">' + esc(e && e.status === 404 ? 'حركات هذا النوع من الأعمال غير متاحة بعد' : 'تعذّر جلب الحركات الآن') + '</div><div class="acts"><button type="button" class="btn btn-ghost" id="v3_x">إغلاق</button></div>';
      q('#v3_x', s).onclick = function () { window.closeModal(); };
    });
  }

  // ------------------------------------------------------------------ ربط الأحداث
  function afterMoney(text) {
    setNote(text);
    epReload(['walletPayouts', 'inbox', 'opsQueue']);
    load('paid', true); load('rejected', true); load('refunds', true);
    redraw();
  }
  function payoutRowById(id) { return (L.v2PayoutRows(epPayouts(), now()) || []).filter(function (r) { return r.id === id; })[0]; }
  function wire(v) {
    var retry = qa('[data-a="retry"]', v);
    retry.forEach(function (b) {
      b.onclick = function () {
        Object.keys(PATHS).forEach(function (k) { if (srcState(k) === 'error') load(k, true); });
        epReload(['walletPayouts', 'escrow', 'inbox', 'opsQueue']);
      };
    });
    qa('[data-a="period"]', v).forEach(function (b) {
      b.onclick = function () { S.period = b.getAttribute('data-p'); try { localStorage.setItem('v3_period', S.period); } catch (e) {} redraw(); };
    });
    qa('[data-a="goto"]', v).forEach(function (b) { b.onclick = function () { if (host().openSection) host().openSection(b.getAttribute('data-s'), b.getAttribute('data-t')); }; });
    qa('[data-a="settle"]', v).forEach(function (b) {
      b.onclick = function (e) {
        e.stopPropagation();
        var r = payoutRowById(b.getAttribute('data-id'));
        if (!r || !window.V2 || !V2.openMoney) return;
        V2.openMoney(r.card, r.card.primary.act, afterMoney);
      };
    });
    qa('[data-a="rconfirm"],[data-a="rreject"]', v).forEach(function (b) {
      b.onclick = function () {
        var id = b.getAttribute('data-id'), c = (S.receiptCards || []).filter(function (x) { return x.id === id; })[0];
        if (!c || !window.V2 || !V2.openMoney) return;
        V2.openMoney(c, b.getAttribute('data-a') === 'rconfirm' ? c.primary.act : c.secondary.act, afterMoney);
      };
    });
    qa('[data-a="refund"]', v).forEach(function (b) {
      b.onclick = function () {
        var id = b.getAttribute('data-id'), res = L.v2Refunds(data('refunds'), disputeRefunds(), now()), r = res.rows.filter(function (x) { return x.id === id; })[0];
        if (!r) return;
        if (r.act.do === 'escrow') { if (host().openSection) host().openSection('disputes', 'escrow'); }
        else if (r.ticket && host().openRowAt) host().openRowAt('disputes', 'all', r.ticket.row);
      };
    });
    qa('[data-a="price"]', v).forEach(function (b) {
      b.onclick = function () {
        var kind = b.getAttribute('data-kind'), id = b.getAttribute('data-id');
        var res = L.v2Prices(data(kind === 'book' ? 'pricesBook' : 'pricesCourse')), row = res && res.rows.filter(function (r) { return r.id === id; })[0];
        openPrice(kind, id, row ? row.title : id);
      };
    });
    qa('[data-a="share"]', v).forEach(function (b) { b.onclick = function () { openShares(b.getAttribute('data-k')); }; });
    qa('[data-a="minpay"]', v).forEach(function (b) { b.onclick = openMinPay; });
    qa('[data-a="ad"]', v).forEach(function (b) { b.onclick = function () { openAd(b.getAttribute('data-id'), b.getAttribute('data-kind')); }; });
    qa('[data-a="oapprove"],[data-a="oreject"]', v).forEach(function (b) {
      b.onclick = function () {
        var o = (S.offerRows || []).filter(function (x) { return x.id === b.getAttribute('data-id'); })[0];
        if (!o) return;
        if (b.getAttribute('data-a') === 'oapprove') openApprove(o); else openReject(o);
      };
    });
    qa('[data-a="rqok"],[data-a="rqhide"]', v).forEach(function (b) {
      b.onclick = function () {
        var g = (S.reqGroups || []).filter(function (x) { return x.key === b.getAttribute('data-key'); })[0], E = ep();
        if (!g || !E || S.busy[g.key]) return;
        var ok = b.getAttribute('data-a') === 'rqok';
        function run() {
          S.busy[g.key] = true; b.disabled = true; b.textContent = 'جارٍ التنفيذ…';
          E.api('/v2/book-requests/' + encodeURIComponent(g.firstId), { method: 'PATCH', body: ok ? { status: 'seeking', apply_to_group: true } : { hidden: true, apply_to_group: true } }).then(function () {
            S.busy[g.key] = false; setNote(ok ? 'اعتُمد الطلب وسيظهر للأعضاء: ' + g.topic : 'أُخفي الطلب: ' + g.topic); load('requests', true); redraw();
          }).catch(function (e) { S.busy[g.key] = false; setNote(errMsg(e)); redraw(); });
        }
        if (!ok) return run();
        // «اعتمد» ينشر الطلب للأعضاء ⇒ سطر تأكيد واحد قبل التنفيذ (الإخفاء يُتراجع عنه فيبقى مباشرًا).
        var cs = openSheet('اعتماد طلب القرّاء', '<p class="mc-lead">سيظهر «' + esc(g.topic) + '» للأعضاء في «المطلوب الآن». أكّد الاعتماد؟</p>'
          + '<div class="acts"><button type="button" class="btn btn-primary" id="v3_rqgo">اعتمد وانشر</button><button type="button" class="btn btn-ghost" id="v3_rqno">إلغاء</button></div>');
        if (!cs) return;
        q('#v3_rqno', cs).onclick = function () { window.closeModal(); };
        q('#v3_rqgo', cs).onclick = function () { window.closeModal(); run(); };
      };
    });
  }

  // ------------------------------------------------------------------ نقطة الدخول
  function isCurrent(mod) { return !!(host().current && host().current() === mod && S.view && document.body.contains(S.view)); }
  var NEEDS = {
    v2m_overview: { src: ['revenues', 'income', 'refunds'], ep: ['walletPayouts', 'escrow', 'inbox', 'opsQueue'] },
    v2m_payouts: { src: ['settings', 'paid', 'rejected'], ep: ['walletPayouts'] },
    v2m_receipts: { src: ['stuck'], ep: ['inbox', 'opsQueue'] },
    v2m_prices: { src: ['pricesBook', 'pricesCourse'], ep: [] },
    v2m_shares: { src: ['shares', 'settings'], ep: [] },
    v2m_ads: { src: ['ads'], ep: [] },
    v2b_offers: { src: ['offers', 'pricesBook'], ep: [] },
    v2b_requests: { src: ['requests'], ep: [] }
  };
  function ensureFor(mod) {
    var n = NEEDS[mod];
    if (!n) return;
    epEnsure(n.ep); loadMany(n.src, false);
  }
  function redraw() {
    if (!S.view || !host().current || !D3.owns(host().current())) return;
    S.mod = host().current();
    var v = S.view;
    // لا نعيد رسم الشاشة وتحت نافذة مفتوحة تكتب فيها (الأرقام المكتوبة تضيع)
    if (document.getElementById('epModal')) return;
    ({ v2m_overview: drawOverview, v2m_payouts: drawPayouts, v2m_receipts: drawReceipts, v2m_prices: drawPrices, v2m_shares: drawShares, v2m_ads: drawAds,
       v2b_offers: drawOffers, v2b_requests: drawRequests })[S.mod](v);
    S.sig = signature();
  }
  D3.render = function (mod, view) {
    S.view = view; S.mod = mod;
    ensureFor(mod);
    redraw();
    if (!S.poll) {
      S.poll = setInterval(function () {
        if (!(host().current && D3.owns(host().current()))) { S.mod = ''; return; }
        S.mod = host().current();
        if (document.getElementById('epModal')) return;
        if (signature() !== S.sig) redraw();
      }, 400);
    }
    if (!S.minute) S.minute = setInterval(function () { if (host().current && D3.owns(host().current()) && !document.getElementById('epModal')) { S.mod = host().current(); redraw(); } }, 60000);
  };

  // —— للوحة القرارات: الدفعات العالقة وعروض الكتب (صفوف جاهزة لـ`v2Decisions`)، وأرقام الشارات. لا يُحمَّل هنا إلا ما لم يُحمَّل.
  D3.preload = function () { loadMany(['stuck', 'offers', 'pricesBook'], false); };
  D3.cardSources = function () {
    var stuck = L.v2Stuck(data('stuck'), now());
    if (!stuck && srcState('stuck') !== 'idle' && srcState('stuck') !== 'loading') stuck = L.v2StuckFromQueue(queue());
    var offers = L.v2OffersQueue(data('offers'), data('pricesBook'), now());
    var failed = [];
    if (srcState('stuck') === 'error' && !stuck) failed.push('المدفوعات العالقة');
    if (srcState('offers') === 'error') failed.push('عروض الكتب');
    return { stuck: stuck ? stuck.rows : [], offers: offers || [], failed: failed,
             offersCount: offers ? offers.length : (srcState('offers') === 'error' ? null : undefined) };
  };
  D3.sig = function () { return ['stuck', 'offers', 'pricesBook'].map(function (k) { return srcOf(k).state; }).join(','); };
  D3.openApprove = openApprove;
  D3.openReject = openReject;
  D3._state = S;
  D3._src = SRC;
  D3._tick = function (t) { S.nowOverride = t || 0; redraw(); };
})();
