/* ============================================================================
 * v2-home.js — اللوحة الجديدة (D1): رسم + تفاعل. ⛔ ما فيه منطق قرار هنا: الأرقام والترتيب والبطاقات من
 * v2-logic.js (نقي)، والأزرار بتنادي الدوال الموجودة في dashboard-api.js بالحرف:
 *   EP.expertFileSend · EP.decideInboxItem · EP.resolveInboxItem
 * والاستثناء الوحيد مساران جديدان للفلوس: سجّل/ارفض تحويل أرباح (`/platform-wallet-payouts/<id>/settle|reject`).
 *
 * ⛔ المفتاح مقفول افتراضيًا: الملف بيتحمّل دايمًا لكنه ما بيعمل شيئًا إلا لو index.html استدعى `V2.render`
 * (وده ما بيحصل إلا لما `/api/v2/config` يرجّع enabled:true).
 * ⛔ ولا طلب شبكة من هنا غير الدوال المذكورة. روابط الإيصالات بتتعرض نصًّا (مفيش تحميل تلقائي).
 * ========================================================================== */
(function () {
  'use strict';
  var L = window.V2L;
  if (!L) return;
  var U = L.util;

  var SOURCES = ['opsQueue', 'inbox', 'walletPayouts', 'invites', 'pendingUsers', 'market'];
  var S = {
    mode: 'board',        // board | focus | brain
    deck: [], total: 0, done: [], later: [],    // R24: later = اللي أجّلته في الجلسة دي (للسطر الأخير)
    lines: '', fg: {}, cards: {},               // R24: القايمة المفتوحة (later | gone) · مجموعات «للعلم» المفتوحة · بطاقات للأزرار
    flash: '',
    busy: false, err: '', lockedId: '',
    errMap: {},           // R24 م٢: خطأ كل بطاقة (للشريط في الأقسام) — بيتمسح مع أول محاولة جديدة
    panel: null,          // health | user
    view: null, sig: '', timer: null, leaving: ''
  };
  var V2 = window.V2 = {};
  // R24 م٢: أي تغيّر في حالة التنفيذ (نجاح · خطأ · تأجيل) بيصحّي شريط القسم وصفحة الشخص — مش بس اللوحة.
  var listeners = [];
  V2.listen = function (fn) { listeners.push(fn); return function () { listeners = listeners.filter(function (x) { return x !== fn; }); }; };
  function notify() { listeners.slice().forEach(function (fn) { try { fn(); } catch (e) {} }); }

  function esc(s) { return String(s == null ? '' : s).replace(/[&<>"']/g, function (c) { return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]; }); }
  function host() { return window.V2_HOST || {}; }
  function ep() { return window.EP || null; }
  function reduced() { try { return window.matchMedia && matchMedia('(prefers-reduced-motion: reduce)').matches; } catch (e) { return false; } }
  function img(name) { return 'v2/img/' + name + '.jpg'; }

  // ------------------------------------------------------------------ البيانات (من المحمّلات الموجودة فقط)
  function stateOf(k) { var E = ep(); return (E && E.state && E.state[k]) || 'idle'; }
  function isLoading(k) { var s = stateOf(k); return s === 'idle' || s === 'loading'; }
  function load() {
    var E = ep();
    if (!E || !E.authed) return;
    SOURCES.forEach(function (k) { E.ensure(k, null); });
  }
  function marketCount() {
    var E = ep(), s = stateOf('market');
    if (s === 'error') return null;
    if (s !== 'ready') return undefined;
    var d = E.data.market;
    if (!d || d.missing) return undefined;                       // الجسر مش منشور ⇒ ولا رقم
    return (d.rows || []).filter(function (r) {
      return r.status === 'open' && !r.hidden && !r.is_test && r.kind !== 'training_offer' && !r.offer_count;
    }).length;
  }
  // يجمع مدخلات المربّعات من المحمّلات (مرة واحدة لكل استدعاء): تتشاركها اللوحة وقائمة القسم الجانبية فلا عدّ ثانٍ.
  function gather() {
    var E = ep(), D = (E && E.data) || {}, now = Date.now();
    var Q = stateOf('opsQueue') === 'ready' ? (D.opsQueue || null) : null;
    // R24: `window.INBOX` مرئي بس (المؤجَّل/المتجاهَل اتشال في المحمّل). صفوف «ملف اتبعت ولسه ما استلمهوش» (`fyi`) بتروح «للعلم» مش القرارات.
    var allRows = stateOf('inbox') === 'ready' ? (window.INBOX || []) : null;
    var rows = allRows ? allRows.filter(function (r) { return !r.fyi; }) : null;
    var fyiRows = allRows ? allRows.filter(function (r) { return !!r.fyi; }) : [];
    var inboxFailed = (window.INBOX_FAILED && window.INBOX_FAILED.length) ? window.INBOX_FAILED.slice() : [];
    var payouts = (stateOf('walletPayouts') === 'ready' && D.walletPayouts) ? (D.walletPayouts.rows || []) : null;
    var pu = (stateOf('pendingUsers') === 'ready' && D.pendingUsers && !D.pendingUsers.missing)
      ? (D.pendingUsers.rows || []).filter(function (u) { return u.requested; }).length : null;
    var inv = (stateOf('invites') === 'ready' && D.invites && !D.invites.missing)
      ? (D.invites.rows || []).filter(function (i) { return i.status === 'awaiting_approval'; }).length : null;
    // ما قُصَّ من قوائم الوارد («نزاعات الملفات: معروض ١٠٠ من ٣٠٠»): المعروض مش كل الموجود ⇒ بطاقات ناقصة وعدّاد ناقص معلَن.
    var inboxTrunc = rows ? ((window.INBOX_TRUNCATED && window.INBOX_TRUNCATED.length) ? window.INBOX_TRUNCATED.slice() : []) : null;
    var extras = { inbox: rows, inboxFailed: inboxFailed, inboxTruncated: inboxTrunc || [], pendingVisitors: pu, invitesAwaiting: inv, market: marketCount(), now: now };
    // D3: عروض الكتب في الطابور الجديد (رقم من الجسر؛ تعذّر ⇒ null؛ لم يُحمَّل بعد ⇒ غير موجود فلا يتغيّر العدّ).
    var d3 = window.V2D3 && window.V2SHELL && V2SHELL.on ? V2D3.cardSources() : null;
    if (d3 && d3.offersCount !== undefined) extras.bookOffers = d3.offersCount;
    // العقل: رقم واحد للمربّع والقائمة والشاشة من سجل اليوم الكامل (عدد · null عند الفشل · undefined قبل الوصول ⇒ العدّ القديم).
    if (window.V2SEC && V2SEC.brain && V2SEC.brain.tileCount) { extras.brainToday = V2SEC.brain.tileCount(); extras.brainTodayPartial = !!(V2SEC.brain.tilePartial && V2SEC.brain.tilePartial()); }
    // brain2: اقتراحات العقل المنتظرة (مصفوفة · null إن تعذّر · undefined قبل الوصول). غيابها لا يغيّر شيئًا.
    var brainItems = null;
    try { var bp = window.V2BRAIN && V2BRAIN.pending ? V2BRAIN.pending() : null; if (Array.isArray(bp)) brainItems = bp; } catch (e) {}
    // R24: «بعدين/تجاهل» من خادم الداشبورد. الفلتر الواحد (`L.v2Split` ⇐ `v2SnoozeSplit`) على كل المصادر، والمخفي بيتشال من أعداد المربّعات
    // بنفس الصفوف — فالمربّع والقايمة الجانبية والشريط و«ابدأ القرارات» بيطلعوا بنفس الرقم.
    var sz = E && E.data && E.data.snooze;
    var snooze = (sz && sz.map) ? { map: sz.map, now: now } : null;
    var hiddenBase = [].concat(Array.isArray(window.INBOX_SNOOZED) ? window.INBOX_SNOOZED : [],
                               (payouts && D.walletPayouts && Array.isArray(D.walletPayouts.hidden)) ? D.walletPayouts.hidden : []);
    // R24 م٢: دعوات الأعضاء اللي بتنتظر موافقتك (مصدر الدعوات) — بتتجمّع مع باقي طلبات نفس الشخص في بطاقة واحدة.
    var inviteRows = (stateOf('invites') === 'ready' && D.invites && !D.invites.missing)
      ? (D.invites.rows || []).filter(function (i) { return i.status === 'awaiting_approval'; }) : [];
    var split = L.v2Split(rows, payouts, Q, { now: now, inboxFailed: inboxFailed, inboxTruncated: inboxTrunc, fyiRows: fyiRows, hidden: hiddenBase, snooze: snooze,
                                              stuck: d3 ? d3.stuck : null, offers: d3 ? d3.offers : null, brainItems: brainItems, invites: inviteRows });
    extras.hidden = split.hiddenRows;
    // توفّر المصادر للمربّعات: true وصل · false فشل · undefined لسه بيتحمّل.
    var avail = { inbox: stateOf('inbox') === 'error' ? false : (rows ? true : undefined), payouts: stateOf('walletPayouts') === 'error' ? false : (payouts ? true : undefined),
                  market: stateOf('market') === 'error' ? false : (extras.market === null ? false : (extras.market === undefined ? undefined : true)) };
    return { E: E, D: D, now: now, Q: Q, rows: rows, inboxFailed: inboxFailed, payouts: payouts, inboxTrunc: inboxTrunc, extras: extras, d3: d3, brainItems: brainItems,
             split: split, snoozeOk: !(sz && sz.ok === false), avail: avail };
  }
  function compute() {
    var g = gather(), Q = g.Q, rows = g.rows, now = g.now, inboxFailed = g.inboxFailed, inboxTrunc = g.inboxTrunc;
    var tiles = L.v2SectionTiles(L.v2Tiles(Q, g.extras), g.split, g.avail);      // R24 م٢: العدد = عدد القرارات من نفس الدالة (بعد البعدين والتجاهل)
    var decisions = g.split.decisions;
    var truncated = (inboxTrunc || []).map(function (t) { return String(t).split(':')[0].trim(); });
    var failed = [];
    if (stateOf('opsQueue') === 'error') failed.push('بيانات المنصة');
    if (stateOf('inbox') === 'error') failed.push('الوارد');
    if (stateOf('walletPayouts') === 'error') failed.push('تحويلات الأرباح');
    inboxFailed.forEach(function (n) { if (failed.indexOf(n) < 0) failed.push(n); });
    if (g.d3) g.d3.failed.forEach(function (n) { if (failed.indexOf(n) < 0) failed.push(n); });
    return {
      now: now, Q: Q, rows: rows, tiles: tiles, decisions: decisions, failed: failed, truncated: truncated,
      fyi: g.split.fyi, lists: L.v2SnoozeLists(g.split.snoozed), snoozeOk: g.snoozeOk, split: g.split, total: g.split.decisions.length,
      health: L.v2Health(Q, now), next: L.v2Next(decisions),
      brainLog: rows ? L.v2BrainLog(rows, now) : null,
      loading: isLoading('opsQueue') || isLoading('inbox') || isLoading('walletPayouts')
    };
  }
  function signature() {
    var E = ep();
    return SOURCES.map(stateOf).join(',') + '|' + ((window.INBOX || []).length) + '|' + (E && E.data.walletPayouts ? E.data.walletPayouts.count : '')
      + (window.V2D3 ? '|' + V2D3.sig() : '') + (window.V2SEC && V2SEC.brain && V2SEC.brain.sig ? '|' + V2SEC.brain.sig() : '')
      + (window.V2BRAIN && V2BRAIN.sig ? '|' + V2BRAIN.sig() : '')
      + '|' + ((E && E.data && E.data.snooze && E.data.snooze.at) || 0) + '|' + ((window.INBOX_SNOOZED || []).length);
  }

  // ------------------------------------------------------------------ الرسم
  var TILE_RGB = { files: '158,43,78', disputes: '122,30,40', courses: '91,74,170', market: '176,118,12', books: '14,120,130',
                   people: '24,126,78', money: '26,43,74', content: '190,88,48', marketing: '138,38,92', reports: '34,70,112',
                   brain: '33,38,46', company: '58,60,72' };
  var LOGO = '<svg viewBox="0 0 798 588" aria-hidden="true"><path fill="currentColor" d="M389 50 Q389 0 439 0 L672 0 Q762 0 762 90 L762 347 L675 347 L675 353 L572 353 L572 588 L496 588 L496 493 L462 493 L462 588 L386 588 L386 493 L302 493 L302 588 L228 588 L228 493 L201 493 L201 588 L104 588 L104 335 L76 335 L76 409 L0 409 L0 351 L40 351 L40 182 L108 182 L108 106 L389 106 Z"/><path fill="currentColor" d="M675 337 L762 337 L762 421 L798 421 L798 492 L675 492 Z"/></svg>';
  var BELL = '<svg viewBox="0 0 24 24" class="v2-ic" aria-hidden="true"><path d="M18 8A6 6 0 0 0 6 8c0 7-3 9-3 9h18s-3-2-3-9"/><path d="M13.7 21a2 2 0 0 1-3.4 0"/></svg>';
  var USER = '<svg viewBox="0 0 24 24" class="v2-ic" aria-hidden="true"><circle cx="12" cy="8" r="4"/><path d="M4 21a8 8 0 0 1 16 0"/></svg>';
  var BACK = '<svg viewBox="0 0 24 24" class="v2-ic" aria-hidden="true"><path d="M9 6l6 6-6 6"/></svg>';

  function healthPill(d) {
    var h = d.health;
    if (isLoading('opsQueue')) return { cls: 'ld', text: '…جارٍ الفحص', n: 0 };
    if (h.failed) return { cls: 'warn', text: 'تعذّر فحص الصحة', n: 0 };
    if (h.ok) return { cls: 'ok', text: 'كل شيء يعمل', n: 0 };
    var n = h.alerts.length;
    return { cls: 'warn', text: U.U(n, ['تنبيه واحد', 'تنبيهان', 'تنبيهات', 'تنبيهًا']), n: n };
  }
  function popHealth(d) {
    var h = d.health;
    if (h.failed) return '<div class="v2-pop-t">تعذّر جلب حالة المنصة</div><p class="v2-pop-p">لا نعرف الآن إن كان كل شيء يعمل، فلا تعتبره سليمًا.</p>';
    var alerts = h.alerts.length
      ? '<ul class="v2-alerts">' + h.alerts.map(function (a) { return '<li>' + esc(a) + '</li>'; }).join('') + '</ul>'
      : '<p class="v2-pop-p">لا تنبيهات الآن.</p>';
    var beats = h.heartbeats.length
      ? '<div class="v2-pop-t" style="margin-top:12px">آخر نبضات الفحص</div><ul class="v2-beats">' + h.heartbeats.map(function (b) { return '<li><span>' + esc(b.label) + '</span><b>' + esc(b.ago) + '</b></li>'; }).join('') + '</ul>' : '';
    return '<div class="v2-pop-t">التنبيهات</div>' + alerts + beats;
  }
  // نص بحروف لاتينية متصلة (رقم حساب دولي · بريد) يُعزل اتجاهه فلا يختلط بالعربية حوله.
  var LTR_RE = /[A-Za-z]{2}\d{2}(?: ?[A-Za-z0-9]{2,5}){3,}|[\w.+-]+@[\w-]+(?:\.[\w-]+)+/g;
  function ltr(text) {
    var out = '', last = 0, str = String(text == null ? '' : text), m;
    LTR_RE.lastIndex = 0;
    while ((m = LTR_RE.exec(str))) { out += esc(str.slice(last, m.index)) + '<bdi dir="ltr">' + esc(m[0]) + '</bdi>'; last = m.index + m[0].length; }
    return out + esc(str.slice(last));
  }
  function greetName() {
    var E = ep(), u = (E && E.user) || {};
    var full = String(u.name || u.full_name || '').trim();
    return full ? full.split(/\s+/).slice(0, 2).join(' ') : 'المؤسس';
  }
  function header(d) {
    var hp = healthPill(d), E = ep(), u = (E && E.user) || {};
    var name = u.name || u.full_name || (E && E.user && E.user.email) || 'المؤسس';
    var pop = '';
    if (S.panel === 'health') pop = '<div class="v2-pop" data-pop>' + popHealth(d) + '</div>';
    if (S.panel === 'user') pop = '<div class="v2-pop v2-pop-u" data-pop><div class="v2-pop-t">' + esc(name) + '</div><p class="v2-pop-p">المؤسس</p><button class="v2-btn2" data-a="logout">تسجيل الخروج</button></div>';
    var hour = new Date(d.now).getHours();
    return '<header class="v2-head"><div class="v2-hi"><h1>' + (hour < 12 ? 'صباح الخير' : 'مساء الخير') + ' يا ' + esc(greetName()) + '</h1><p>' + esc(L.snoozeUntilText(new Date(d.now).toISOString())) + '</p></div>'
      + '<div class="v2-tools">'
      + '<button class="v2-health ' + hp.cls + '" data-a="health" aria-expanded="' + (S.panel === 'health') + '"><i></i><span>' + esc(hp.text) + '</span></button>'
      + '<button class="v2-iconbtn" data-a="health" aria-label="التنبيهات" title="التنبيهات">' + BELL + (hp.n ? '<em>' + esc(U.ar(hp.n)) + '</em>' : '') + '</button>'
      + '<button class="v2-iconbtn" data-a="user" aria-label="حسابي" title="حسابي">' + USER + '</button>'
      + pop + '</div></header>';
  }
  // «ن قرار مستنيك» + «ابدأ القرارات (ن)»: العدد = عدد قرارات الأقسام كلها بعد البعدين والتجاهل (نفس عدّاد المربّعات والشريط والقايمة).
  function heroCount(n) { return n === 1 ? 'قرار واحد مستنيك' : n === 2 ? 'قرارين مستنيينك' : U.ar(n) + ' قرار مستنيك'; }
  function nextBar(d) {
    var n = d.decisions.length;
    var left, sub = '', btn = '';
    if (d.loading && !n) {
      left = '<h2>…جارٍ جلب القرارات</h2>';
    } else if (n) {
      left = '<h2>' + esc(heroCount(n)) + '</h2>';
      sub = '<p>راجع كل قرار مرة واحدة، ولو محتاج وقت اختار «بعدين» وهيرجع لك في ميعاده.</p>';
      btn = '<button class="v2-start" data-a="start">ابدأ القرارات (' + esc(U.ar(n)) + ')</button>';
    } else if (d.failed.length) {
      // ⛔ لا «مفيش قرار» فوق جلب فاشل: لا نعرف إن كان شيء ينتظرك.
      left = '<h2>تعذّر جلب القرارات</h2>';
      sub = '<p>لا نعرف إن كان شيء ينتظرك، فلا تعتبر اللوحة فاضية.</p>';
    } else if (d.truncated.length) {
      left = '<h2>القائمة ناقصة</h2>';
      sub = '<p>معروض جزء من القرارات فقط.</p>';
    } else {
      left = '<h2>مفيش قرار مستنيك</h2>';
      sub = '<p>كل حاجة في ميعادها، والعقل شغّال.</p>';
    }
    var warn = d.failed.length ? '<span class="v2-warnline">تعذّر جلب: ' + esc(d.failed.join('، ')) + ' — القائمة ناقصة</span>' : '';
    if (d.truncated.length) warn += '<span class="v2-warnline">معروض جزء فقط من: ' + esc(d.truncated.join('، ')) + ' — القائمة ناقصة</span>';
    return '<section class="v2-hero" aria-label="القرارات"><img class="v2-av" src="' + img('brain-avatar') + '" alt=""><div class="v2-nt">' + left + sub + warn + '</div>'
      + '<div class="v2-hact"><button type="button" class="v2-link wine" data-a="brainlog">اللي عمله العقل</button>' + btn + '</div></section>';
  }
  function tileHtml(t, d) {
    var loading = tileLoading(t);
    var txt = loading ? '…' : (t.failed ? L.FAILED_TEXT : t.next);
    var pill = !loading && !t.failed && t.count > 0;
    return '<button class="v2-tile' + (t.hot && pill ? ' hot' : '') + '" data-tile="' + esc(t.key) + '" style="--rgb:' + (TILE_RGB[t.key] || '33,38,46') + ';background-image:url(' + img(t.img) + ')"'
      + (t.partial ? ' title="العدد ناقص — تعذّر جلب بعض المصادر"' : '') + '>'
      + '<span class="v2-tt"><b>' + esc(t.label) + '</b><small class="' + (pill ? 'v2-tn pill' : 'v2-tn') + (t.failed ? ' fail' : '') + '">' + esc(txt) + (t.partial && pill ? '+' : '') + '</small></span></button>';
  }
  var DEPS = { files: ['inbox'], disputes: ['inbox'], courses: ['inbox'], money: ['walletPayouts', 'inbox'], content: ['inbox'],
               books: ['inbox'], market: ['market'], people: ['invites', 'inbox'] };
  function tileLoading(t) { return (DEPS[t.key] || []).some(isLoading); }

  // صندوقا اللوحة: «العقل عمل لوحده النهارده» (م٣ هتملاه) و«للعلم بس» (بدون قرار).
  function brainBox() {
    return '<section class="v2-box v2-brainbox" aria-label="العقل عمل لوحده النهارده"><div class="v2-boxh"><h3>العقل عمل لوحده النهارده</h3><button type="button" class="v2-link wine" data-a="brainlog">السجل كله</button></div>'
      + '<p class="v2-boxempty">لسه مفيش حاجة اتعملت لوحدها. لما العقل يبدأ يشتغل لوحده هتلاقي هنا كل حاجة عملها، وجنبها «رجّعها» لو عايز تلغيها.</p></section>';
  }
  function drawBoard(v, d) {
    var tiles = d.tiles.map(function (t) { return tileHtml(t, d); }).join('');
    S.cards = {};
    v.innerHTML = '<div class="v2">' + header(d) + nextBar(d) + '<section class="v2-grid" aria-label="الأقسام">' + tiles + '</section>' + linesBar(d)
      + '<div class="v2-boxes">' + fyiBox(d) + brainBox() + '</div></div>';
    wireCommon(v, d);
    wireLists(v, d);
    var st = v.querySelector('[data-a="start"]');
    if (st) st.onclick = function () { startFocus(d); };
    v.querySelectorAll('[data-a="brainlog"]').forEach(function (b) { b.onclick = function () { if (host().openSection) host().openSection('company', 'brain'); }; });
    v.querySelectorAll('[data-tile]').forEach(function (b) { b.onclick = function () { openTile(b.getAttribute('data-tile'), d); }; });
  }
  function wireCommon(v, d) {
    v.querySelectorAll('[data-a="health"]').forEach(function (b) { b.onclick = function (e) { e.stopPropagation(); S.panel = S.panel === 'health' ? null : 'health'; redraw(); }; });
    var u = v.querySelector('[data-a="user"]'); if (u) u.onclick = function (e) { e.stopPropagation(); S.panel = S.panel === 'user' ? null : 'user'; redraw(); };
    var lo = v.querySelector('[data-a="logout"]'); if (lo) lo.onclick = function () { if (host().logout) host().logout(); };
    if (S.panel) {
      setTimeout(function () {
        var off = function (e) { if (!e.target.closest || (!e.target.closest('[data-pop]') && !e.target.closest('.v2-tools'))) { document.removeEventListener('click', off); S.panel = null; redraw(); } };
        document.addEventListener('click', off);
      }, 0);
    }
  }
  // المربّع بيفتح قسمه (والشريط «محتاج قرارك» فوق). ولا مسار لـ«كل الوارد» — اتشال.
  function openTile(key, d) {
    var t = d.tiles.filter(function (x) { return x.key === key; })[0];
    if (!t) return;
    if (host().openSection) host().openSection(key);
  }

  // —— وضع التركيز: بطاقة واحدة
  function startFocus(d) {
    S.deck = d.decisions.slice(); S.total = S.deck.length; S.done = []; S.later = []; S.err = ''; S.lockedId = ''; S.busy = false; S.busyText = '';
    S.mode = 'focus'; redraw();
  }
  // ⛔ نهاية القرارات لا تطمئن فوق جلب فاشل أو قائمة مقصوصة.
  function endText(d) {
    if (d.failed.length) return S.total ? 'انتهت القرارات التي وصلت — وهناك ما لم نستطع جلبه' : 'تعذّر جلب القرارات — لا نعرف إن كان شيء ينتظرك';
    if (d.truncated.length) return S.total ? 'انتهت القرارات المعروضة — والقائمة ناقصة' : 'القائمة ناقصة — معروض جزء من القرارات فقط';
    return S.total ? 'انتهت القرارات. العقل يكمل الباقي' : 'لا توجد قرارات بانتظارك الآن';
  }
  function incompleteLine(d) {
    var p = [];
    if (d.failed.length) p.push('تعذّر جلب: ' + d.failed.join('، '));
    if (d.truncated.length) p.push('معروض جزء فقط من: ' + d.truncated.join('، '));
    return p.join(' — ');
  }
  function counter() { return U.ar(S.total - S.deck.length + 1) + ' من ' + U.ar(S.total); }
  // brain2: رأي العقل على بطاقة التركيز (من الذاكرة، ويطلب الجديد من الخادم مرة واحدة) + جلب آراء البطاقات التالية بنداء واحد. أي عطل ⇒ البطاقة كما هي.
  function brainCard(c) {
    if (!c || !window.V2BRAIN) return c;
    try { var out = V2BRAIN.decorate(c, { fetch: true }) || c; V2BRAIN.prefetch(S.deck.slice(1, 9)); return out; } catch (e) { return c; }
  }
  function brainSrc(c) { return c.src && c.src.text ? '<span class="v2b-src ' + esc(c.src.tone || '') + '">' + esc(c.src.text) + '</span>' : ''; }
  function brainFields(c) {
    return (c.fields && c.fields.length) ? '<div class="v2b-fields">' + c.fields.map(function (x) { return '<div><small>' + esc(x.k) + '</small><b>' + esc(x.v) + '</b></div>'; }).join('') + '</div>' : '';
  }
  function drawFocus(v, d) {
    var c = brainCard(S.deck[0]);
    var done = S.done.length
      ? '<aside class="v2-done"><h3>أنجزت الآن</h3><ul>' + S.done.slice(0, 12).map(function (x) { return '<li>' + esc(x.text) + '</li>'; }).join('') + '</ul></aside>' : '';
    if (!c) {
      v.innerHTML = '<div class="v2 v2-focus"><div class="v2-end"><img src="' + img('brain-avatar') + '" alt="">'
        + '<h2>' + endText(d) + '</h2>'
        + (incompleteLine(d) ? '<p class="v2-warnline">' + esc(incompleteLine(d)) + '</p>' : '')
        + (S.later.length ? '<p class="v2-endnote">' + esc('أجّلت ' + U.U(S.later.length, ['قرارًا واحدًا', 'قرارين', 'قرارات', 'قرارًا'])) + ' — هترجع لك في ميعادها</p>' : '')
        + '<button class="v2-start" data-a="back">العودة إلى اللوحة</button>'
        + (S.later.length ? '<button class="v2-btn3 v2-endlater" data-a="showlater">اعرض المؤجّلة</button>' : '') + done + '</div></div>';
      v.querySelector('[data-a="back"]').onclick = leaveFocus;
      var sl = v.querySelector('[data-a="showlater"]'); if (sl) sl.onclick = function () { S.lines = 'later'; leaveFocus(); };
      return;
    }
    var locked = S.lockedId === c.id;
    var isOpenAct = function (x) { return !!x && (x.do === 'open' || x.do === 'goto'); };
    var pct = Math.round(((S.total - S.deck.length) / Math.max(1, S.total)) * 100);
    var acts = '';
    // مقفولة بعد رد ضايع أو رفض نهائي: الزرّ الأساسي يبقى «حدّث الآن» وبيشتغل فعلًا (بيحدّث ويرجّع الأزرار أو يقدّم بطاقة تانية)،
    // وأزرار الفتح تفضل شغّالة — اللي بيتقفل بس الفعل اللي ممكن يتنفّذ مرتين.
    if (locked) acts += '<button class="v2-btn1" data-a="refresh"' + (S.busy ? ' disabled' : '') + '>' + esc(S.busy ? (S.busyText || 'جارٍ التحديث…') : 'حدّث الآن') + '</button>';
    else acts += '<button class="v2-btn1" data-a="primary"' + (S.busy ? ' disabled' : '') + '>' + esc(S.busy ? (S.busyText || 'جارٍ التنفيذ…') : c.primary.label) + '</button>';
    if (c.secondary) acts += '<button class="v2-btn2" data-a="secondary"' + ((S.busy || (locked && !isOpenAct(c.secondary.act))) ? ' disabled' : '') + '>' + esc(c.secondary.label) + '</button>';
    var isBrain = c.kind === 'brain_item';
    if (isBrain && c.edit) acts += '<button class="v2-btn2" data-a="edit"' + ((S.busy || locked) ? ' disabled' : '') + '>' + esc(c.edit.label) + '</button>';
    // R24 م٢: «افتح في <القسم>» = بيت البطاقة (نفس القسم اللي فيه شريطها). بطاقة اللوحة نسخة من بطاقة القسم بنفس الأزرار.
    var hsec = c.home && L.sectionByKey(c.home);
    if (hsec) acts += '<button class="v2-btn3" data-a="openhome"' + (S.busy ? ' disabled' : '') + '>افتح في ' + esc(hsec.label) + '</button>';
    if (c.key) acts += '<button class="v2-btn3" data-a="later"' + (S.busy ? ' disabled' : '') + '>بعدين</button>';     // R24: بيفتح اختيار الميعاد وبيتحفظ على الخادم
    if (c.dismiss) acts += '<button class="v2-btn3" data-a="dismiss"' + (S.busy ? ' disabled' : '') + '>تجاهل</button>';
    var facts = (c.facts || []).filter(function (f) { return f.v; }).map(function (f) { return '<div><small>' + esc(f.k) + '</small><b>' + ltr(f.v) + '</b></div>'; }).join('');
    v.innerHTML = '<div class="v2 v2-focus">'
      + '<div class="v2-ftop"><button class="v2-link" data-a="back">' + BACK + 'اللوحة</button><span class="v2-count">' + esc(counter()) + '</span><span class="v2-prog"><i style="width:' + pct + '%"></i></span></div>'
      + '<div class="v2-fgrid' + (done ? '' : ' solo') + '"><article class="v2-card' + (S.leaving === c.id ? ' v2-out' : '') + '" data-id="' + esc(c.id) + '" data-bid="' + esc(c.id) + '" data-kind="' + esc(c.kind) + '">'
      + '<div class="v2-cimg" style="background-image:url(' + img(c.img) + ')">' + (hsec ? '<span class="v2-from">من: ' + esc(hsec.label) + '</span>' : '') + '<span class="v2-tag">' + esc(c.tag) + '</span>' + (c.ageText ? '<span class="v2-age">' + esc(c.ageText) + '</span>' : '') + '</div>'
      + '<div class="v2-cbody"><h2>' + (c.person && window.V2D2 ? V2D2.link(c.title, c.person.email) : esc(c.title)) + '</h2>' + (c.sub ? '<p class="v2-csub">' + esc(c.sub) + '</p>' : '')
      + '<div class="v2-brain"><img src="' + img('brain-avatar') + '" alt=""><div><b>' + esc(c.brainHead) + '</b><p' + (isBrain ? ' class="v2b-draft"' : '') + '>' + esc(c.brain) + '</p>' + (c.reason ? '<p class="v2-reason">' + esc(c.reason) + '</p>' : '') + brainSrc(c) + '</div></div>'
      + brainFields(c)
      + (c.chips && c.chips.length ? '<div class="v2-chips">' + c.chips.map(function (x) { return '<span class="v2-chip2">' + esc(x) + '</span>'; }).join('') + (c.merged > 1 ? '<span class="v2-chip2 ok">بطاقة واحدة بدل ' + esc(U.ar(c.merged)) + '</span>' : '') + '</div>' : '')
      + (c.returned ? '<div class="v2-returned">' + esc(c.returned) + '</div>' : '')
      + (c.warn ? '<div class="v2-cwarn">' + esc(c.warn) + '</div>' : '')
      + (facts ? '<div class="v2-facts">' + facts + '</div>' : '')
      + (c.link ? '<p class="v2-linkp"><a href="' + esc(c.link.url) + '" target="_blank" rel="noopener noreferrer">' + esc(c.link.label) + '</a></p>' : '')
      + (S.err ? '<div class="v2-err" role="alert">' + esc(S.err) + '</div>' : '')
      + '<div class="v2-acts">' + acts + '</div></div></article>' + done + '</div></div>';
    v.querySelector('[data-a="back"]').onclick = leaveFocus;
    // الموبايل: الشريط السفلي ثابت، فالحشو تحت البطاقة على قد ارتفاعه الفعلي لا رقمًا ثابتًا (لا فراغ زائد حين يكون الشريط سطرًا واحدًا)
    try {
      var bar = v.querySelector('.v2-acts'), cb = v.querySelector('.v2-cbody');
      if (bar && cb && window.getComputedStyle(bar).position === 'fixed') cb.style.paddingBottom = (bar.offsetHeight + 16) + 'px';
    } catch (e) {}
    var q = function (a, fn) { var b = v.querySelector('[data-a="' + a + '"]'); if (b) b.onclick = fn; };
    q('primary', function () { run(c, c.primary.act); });
    q('refresh', function () { refreshLocked(c); });
    q('secondary', function () { run(c, c.secondary.act); });
    q('edit', function () { if (c.edit) run(c, c.edit.act); });
    q('openhome', function () { openHome(c); });
    q('later', function () { snoozeModal(c); });
    q('dismiss', function () { dismissModal(c); });
    if (S.err) { var er = v.querySelector('.v2-err'); if (er && er.scrollIntoView) { try { er.scrollIntoView({ block: 'center' }); } catch (e) {} } }
    if (S.scrollTop) { S.scrollTop = false; try { var ct = document.querySelector('.content'); if (ct) ct.scrollTop = 0; } catch (e) {} }
  }
  function leaveFocus() {
    removePill();
    S.mode = 'board'; S.err = ''; S.busy = false;
    var E = ep(); if (E) { E.reload('opsQueue'); E.reload('inbox'); E.reload('walletPayouts'); }
    try { if (window.V2BRAIN && V2BRAIN.reload) V2BRAIN.reload(); } catch (e) {}
    redraw();
  }

  // ------------------------------------------------------------------ R24 م١ · «للعلم» · «مؤجّلة» · «اتشالت» · بعدين · تجاهل
  // «للعلم»: كل اللي مش قرار بضغطة (دفعة عالقة · تسجيل · دفع فشل · ملف اتبعت ولسه ما اتستلمش · طلب مستني رد صاحبه · خبير في المتابعة)
  // + البنود اللي قرارها في صفحتها (نزاع · رأي · هوية · …) معلَّمة «قراره في صفحته». مفيش فيها زراير قرار مالية: «افتح» بيودّي لبيتها.
  function cardBtns(c) {
    var out = '<button type="button" class="v2-mini" data-a="fopen" data-id="' + esc(c.id) + '">افتح</button>';
    if (c.bucket === 'fyi' && c.primary && c.primary.act && c.primary.act.do === 'decide' && (c.kind === 'signup' || (c.kind === 'payfail' && c.fyiKind !== 'gateway'))) {
      out += '<button type="button" class="v2-mini pri" data-a="fack" data-id="' + esc(c.id) + '"' + (S.busy ? ' disabled' : '') + '>' + esc(c.primary.label) + '</button>';
    }
    if (c.key) out += '<button type="button" class="v2-mini" data-a="fsnooze" data-id="' + esc(c.id) + '">بعدين</button>';
    if (c.dismiss) out += '<button type="button" class="v2-mini" data-a="fdismiss" data-id="' + esc(c.id) + '">' + (c.fyiKind === 'gateway' ? 'اسكتها' : 'تجاهل') + '</button>';
    return out;
  }
  function fyiBox(d) {
    var f = d.fyi;
    var warn = d.snoozeOk === false ? '<p class="v2-warnline dark">تعذّر جلب المؤجّلة — ممكن تشوف بنودًا كنت أجّلتها</p>' : '';
    if (!f || !f.total) return warn;
    var rows = f.groups.map(function (g) {
      var openG = !!S.fg[g.key];
      var items = '';
      g.cards.forEach(function (c) { S.cards[c.id] = c; });
      if (openG) {
        items = '<ul class="v2-fi">' + g.cards.map(function (c) {
          return '<li><span class="v2-fit"><b>' + (c.person && window.V2D2 ? V2D2.link(c.title, c.person.email) : esc(c.title)) + '</b>'
            + '<small>' + esc(joinSmall([c.ageText, c.sub])) + '</small>'
            + (c.returned ? '<em class="v2-returned">' + esc(c.returned) + '</em>' : '') + '</span><span class="v2-fib">' + cardBtns(c) + '</span></li>';
        }).join('') + '</ul>';
      }
      return '<div class="v2-fg' + (openG ? ' on' : '') + '"><button type="button" class="v2-fgh" data-a="fg" data-k="' + esc(g.key) + '" aria-expanded="' + openG + '">'
        + '<span class="v2-fgl">' + esc(g.label) + '</span>' + (g.kind === 'open' ? '<em class="v2-fgc">قراره في صفحته</em>' : '') + '<span class="v2-fgx">' + (openG ? 'إخفاء' : 'التفاصيل') + '</span></button>' + items + '</div>';
    }).join('');
    return warn + '<section class="v2-fyi" aria-label="للعلم"><h3>للعلم (' + esc(U.ar(f.total)) + ')</h3><div class="v2-fl">' + rows + '</div></section>';
  }
  function joinSmall(arr) { return (arr || []).filter(Boolean).join('، '); }
  // سطر «مؤجّلة (ن)» و«اتشالت (ن)»: بيفتح القايمة وفيها «رجّعها».
  function linesBar(d) {
    var la = d.lists.later, go = d.lists.gone;
    if (!la.length && !go.length) return '';
    var chip = function (k, label, n) { return n ? '<button type="button" class="v2-chip' + (S.lines === k ? ' on' : '') + '" data-a="lines" data-k="' + k + '" aria-expanded="' + (S.lines === k) + '">' + label + ' (' + esc(U.ar(n)) + ')</button>' : ''; };
    var panel = '';
    var list = S.lines === 'later' ? la : S.lines === 'gone' ? go : null;
    if (list && list.length) {
      panel = '<ul class="v2-sl">' + list.map(function (x) {
        return '<li><span class="v2-slt"><b>' + esc(x.title) + '</b><small>' + esc(joinSmall([x.tag, x.kind === 'dismiss' ? ('السبب: ' + x.reason) : x.untilText])) + '</small></span>'
          + '<button type="button" class="v2-mini pri" data-a="restore" data-k="' + esc(x.key) + '"' + (S.busy ? ' disabled' : '') + '>رجّعها</button></li>';
      }).join('') + '</ul>';
    }
    return '<section class="v2-lines" aria-label="المؤجّل والمتشال">' + chip('later', 'مؤجّلة', la.length) + chip('gone', 'اتشالت', go.length) + panel + '</section>';
  }
  function wireLists(v, d) {
    v.querySelectorAll('[data-a="fg"]').forEach(function (b) { b.onclick = function () { var k = b.getAttribute('data-k'); S.fg[k] = !S.fg[k]; redraw(); }; });
    v.querySelectorAll('[data-a="lines"]').forEach(function (b) { b.onclick = function () { var k = b.getAttribute('data-k'); S.lines = S.lines === k ? '' : k; redraw(); }; });
    var byId = function (b) { return S.cards[b.getAttribute('data-id')]; };
    v.querySelectorAll('[data-a="fopen"]').forEach(function (b) { b.onclick = function () { var c = byId(b); if (c) openCard(c); }; });
    v.querySelectorAll('[data-a="fack"]').forEach(function (b) { b.onclick = function () { var c = byId(b); if (c) run(c, c.primary.act); }; });
    v.querySelectorAll('[data-a="fsnooze"]').forEach(function (b) { b.onclick = function () { var c = byId(b); if (c) snoozeModal(c); }; });
    v.querySelectorAll('[data-a="fdismiss"]').forEach(function (b) { b.onclick = function () { var c = byId(b); if (c) dismissModal(c); }; });
    v.querySelectorAll('[data-a="restore"]').forEach(function (b) { b.onclick = function () { restoreItem(b.getAttribute('data-k')); }; });
  }
  function restoreItem(key) {
    var E = ep(); if (!E || !E.restoreItem || S.busy) return;
    S.busy = true; redraw();
    E.restoreItem(key).then(function (res) {
      S.busy = false;
      if (!res || !res.ok) { S.err = (res && res.error) || 'تعذّر الحفظ — حاول تاني'; say(S.err); }
      redraw();
    });
  }
  // البطاقة طلعت من اللوحة بعد «بعدين»/«تجاهل» (مش «أنجزت»): بتتشال من الكوتشينة وتتحسب في «أجّلت م».
  function dropCard(c, text, counted) {
    if (counted) S.later.unshift({ text: text, at: Date.now() });
    S.err = ''; S.busy = false; S.lockedId = '';
    var go = function () { S.deck = S.deck.filter(function (x) { return x.id !== c.id; }); S.leaving = ''; S.scrollTop = true; redraw(); };
    if (S.mode !== 'focus' || reduced()) go();
    else { S.leaving = c.id; redraw(); setTimeout(go, 240); }
  }
  function ymd(d) { return d.getFullYear() + '-' + ('0' + (d.getMonth() + 1)).slice(-2) + '-' + ('0' + d.getDate()).slice(-2); }
  function snoozeModal(c) {
    var E = ep();
    if (typeof window.openModal !== 'function' || !E || !E.snoozeItem || !c || !c.key) return;
    var now = Date.now(), picks = L.snoozePicks(now), tom = new Date(now); tom.setDate(tom.getDate() + 1);
    var s = window.openModal('بعدين لحد إمتى؟',
      '<div class="mc-lead">«' + esc(c.title) + '» هيختفي من القرارات ويرجع لك في الميعاد اللي تختاره.</div>'
      + '<div class="v2z-picks">' + picks.map(function (p, i) { return '<button type="button" class="btn btn-ghost v2z-pick" data-i="' + i + '"><b>' + esc(p.label) + '</b><small>' + esc(L.snoozeUntilText(p.until)) + '</small></button>'; }).join('') + '</div>'
      + '<div class="fld"><label for="v2z_d">أو اختار يوم</label><input id="v2z_d" type="date" min="' + ymd(tom) + '"></div>'
      + '<div id="v2z_err"></div>'
      + '<div class="acts"><button class="btn btn-primary" id="v2z_go" disabled>بعدين لليوم ده</button><button class="btn btn-ghost" id="v2z_x">رجوع</button></div>');
    var err = s.querySelector('#v2z_err'), dt = s.querySelector('#v2z_d'), go = s.querySelector('#v2z_go'), x = s.querySelector('#v2z_x');
    var busy = false;
    var close = function () { if (!busy) window.closeModal(); };
    var xt = s.querySelector('[data-x]'); if (xt) xt.onclick = close;
    x.onclick = close; s.onclick = function (e) { if (e.target === s) close(); };
    dt.addEventListener('input', function () { go.disabled = !dt.value; });
    var fire = function (until) {
      if (busy) return;
      if (!until) { err.innerHTML = '<div class="ef-err">اختار يوم جاي</div>'; return; }
      busy = true; err.innerHTML = '';
      s.querySelectorAll('button').forEach(function (b) { b.disabled = true; });
      Promise.resolve(E.snoozeItem(c.key, until, c.fp)).then(function (res) {
        busy = false;
        if (res && res.ok) { window.closeModal(); dropCard(c, 'أُجّل «' + c.title + '» لحد ' + L.snoozeUntilText(until), true); return; }
        s.querySelectorAll('button').forEach(function (b) { b.disabled = false; }); go.disabled = !dt.value;
        err.innerHTML = '<div class="ef-err">' + esc((res && res.error) || 'تعذّر الحفظ — حاول تاني') + '</div>';
      });
    };
    s.querySelectorAll('.v2z-pick').forEach(function (b) { b.onclick = function () { fire(picks[+b.getAttribute('data-i')].until); }; });
    go.onclick = function () { fire(L.snoozeUntilFromDate(dt.value, Date.now())); };
  }
  function dismissModal(c) {
    var E = ep();
    if (typeof window.openModal !== 'function' || !E || !E.dismissItem || !c || !c.key) return;
    var s = window.openModal(c.fyiKind === 'gateway' ? 'اسكت التنبيه' : 'تجاهل البند',
      '<div class="mc-lead">«' + esc(c.title) + '» هيتشال من القرارات و«للعلم» وتلاقيه في «اتشالت» لو حبيت ترجّعه. لو حالته اتغيّرت على المنصة هيرجع لوحده.</div>'
      + '<div class="fld"><label for="v2z_r">السبب (مطلوب، قصير)</label><input id="v2z_r" type="text" maxlength="200" autocomplete="off"></div>'
      + '<div id="v2z_err"></div>'
      + '<div class="acts"><button class="btn btn-primary" id="v2z_go" disabled>تجاهل</button><button class="btn btn-ghost" id="v2z_x">رجوع</button></div>');
    var err = s.querySelector('#v2z_err'), r = s.querySelector('#v2z_r'), go = s.querySelector('#v2z_go'), x = s.querySelector('#v2z_x'), busy = false;
    var close = function () { if (!busy) window.closeModal(); };
    var xt = s.querySelector('[data-x]'); if (xt) xt.onclick = close;
    x.onclick = close; s.onclick = function (e) { if (e.target === s) close(); };
    var sync = function () { go.disabled = busy || String(r.value || '').trim().length < 3; };
    r.addEventListener('input', sync); sync(); setTimeout(function () { try { r.focus(); } catch (e) {} }, 30);
    go.onclick = function () {
      if (busy || go.disabled) return;
      busy = true; go.disabled = true; x.disabled = true; err.innerHTML = '';
      Promise.resolve(E.dismissItem(c.key, String(r.value || '').trim(), c.fp)).then(function (res) {
        busy = false; x.disabled = false;
        if (res && res.ok) { window.closeModal(); dropCard(c, 'اتشال «' + c.title + '»', false); return; }
        sync(); err.innerHTML = '<div class="ef-err">' + esc((res && res.error) || 'تعذّر الحفظ — حاول تاني') + '</div>';
      });
    };
  }

  // ------------------------------------------------------------------ التنفيذ
  function rowKey(r) { return r ? [r.apiKind, r.dsrc || '', r.apiId].join('|') : ''; }
  function stillPending(c) {
    var E = ep();
    if (c.kind === 'brain_item') {
      var bp = null;
      try { bp = window.V2BRAIN && V2BRAIN.pending ? V2BRAIN.pending() : null; } catch (e) {}
      return !Array.isArray(bp) || bp.some(function (i) { return 'brain_item|' + i.id === c.id; });
    }
    if (c.kind === 'payout') {
      if (stateOf('walletPayouts') !== 'ready' || !E.data.walletPayouts) return true;
      return (E.data.walletPayouts.rows || []).some(function (p) { return p.pid === c.row.pid; });
    }
    if (c.kind === 'book_offer') {
      var d3 = window.V2D3 ? V2D3.cardSources() : null;
      return !d3 || !d3.offers.length || d3.offers.some(function (o) { return o.id === (c.row.offerRow || {}).id; });
    }
    if (c.kind === 'person') return (c.parts || []).some(stillPending);
    if (c.kind === 'invite') {
      var D0 = E.data || {};
      return stateOf('invites') !== 'ready' || !D0.invites || (D0.invites.rows || []).some(function (i) { return i.id === c.row.apiId && i.status === 'awaiting_approval'; });
    }
    if (stateOf('inbox') !== 'ready') return true;
    var key = rowKey(c.row);
    return (window.INBOX || []).some(function (r) { return !r.fyi && rowKey(r) === key; });
  }
  // انتظار تحميل المصادر التلاتة (مش مجرد طلبها): الاستدعاء بيرجع مرتين لكل مفتاح (بداية التحميل ونهايته).
  function reloadAll(done) {
    var E = ep(), keys = ['opsQueue', 'inbox', 'walletPayouts'], fin = false, bdone = !(window.V2BRAIN && V2BRAIN.reload);
    if (!E || !E.authed) { done(); return; }
    var finish1 = function () { if (!fin) { fin = true; done(); } };
    var check = function () { if (bdone && keys.every(function (k) { return stateOf(k) !== 'loading'; })) finish1(); };
    setTimeout(finish1, 20000);
    keys.forEach(function (k) { E.reload(k, check); });
    if (!bdone) { try { V2BRAIN.reload(function () { bdone = true; check(); }); } catch (e) { bdone = true; } }
  }
  // «حدّث الآن»: يحمّل من جديد، يشيل البطاقات اللي ما بقتش بانتظارك (ومنها اللي وزّعها العقل أو اتحسمت في تبويب تاني)،
  // ويفكّ القفل — فإما تبان أزرار البطاقة تاني (الفعل ما اتنفّذش) وإما نمشي للّي بعدها.
  function refreshLocked(c) {
    if (S.busy) return;
    S.busy = true; S.busyText = 'جارٍ التحديث…'; S.err = ''; redraw();
    reloadAll(function () {
      var fresh = {};
      compute().decisions.forEach(function (x) { fresh[x.id] = x; });
      S.deck = S.deck.filter(stillPending).map(function (x) { return fresh[x.id] || x; });
      S.lockedId = ''; S.busy = false; S.busyText = ''; S.scrollTop = true;
      redraw();
    });
  }
  // «افتح في <القسم>»: بيت البطاقة. بطاقة الشخص بتفتح صفحته (فيها كل طلباته بأزرارها).
  function openHome(c) {
    S.err = '';
    if (c.open && c.open.do === 'person' && window.V2D2 && V2D2.openPerson && c.person) { showPill(); V2D2.openPerson(c.person.email); return; }
    if (host().openSection && c.home) { showPill(); host().openSection(c.home); }
  }
  function openCard(c) {
    var a = c.open || { do: 'open' };
    S.err = '';
    if (a.do === 'section' && host().openSection) { showPill(); host().openSection(a.section, a.tab); return; }
    if (a.do === 'person' && a.email && window.V2D2 && V2D2.openPerson) { showPill(); V2D2.openPerson(a.email); return; }
    if (a.do === 'goto' && window.V2SHELL && V2SHELL.on && host().openSection) {
      // D3: تحويلات الأرباح والإيصالات لها تبويباتها الجديدة تحت «الفلوس».
      var dest = a.mod === 'finance' ? (a.land === 'stuck_card_payments' ? 'receipts' : a.land === 'wallet_payouts_pending' ? 'payouts' : null)
        : (a.mod === 'escrow' && a.land === 'manual_payments_pending') ? 'receipts' : null;
      if (dest) { showPill(); host().openSection('money', dest); return; }
    }
    if (a.do === 'goto') { showPill(); if (host().goOps) host().goOps(a.mod, a.land); return; }
    // R24: الصف اتحل/اختفى ⇒ بنقول كده بدل ما نرمي المؤسس على «كل الوارد» من غير ما يتفتح حاجة، ونحدّث الأعداد.
    var opened = host().openRow ? host().openRow(c.row) : true;
    if (opened === false) { removePill(); gone(c); return; }
    showPill();
  }
  function gone(c) {
    S.err = 'البند ده اتحل بالفعل';
    say(S.err);
    S.deck = S.deck.filter(function (x) { return x.id !== c.id; });
    reload();
    redraw();
  }
  function say(t) { try { (window.toast || window.notify || function () {})(t); } catch (e) {} }
  function showPill() {
    removePill();
    var b = document.createElement('button');
    b.id = 'v2Pill'; b.className = 'v2-pill'; b.type = 'button';
    b.textContent = 'العودة إلى القرارات (' + U.ar(S.deck.length) + ')';
    b.onclick = function () {
      removePill();
      S.resume = true;
      S.deck = S.deck.filter(stillPending);
      S.err = '';
      if (host().go) host().go('home');
    };
    document.body.appendChild(b);
  }
  function removePill() { var p = document.getElementById('v2Pill'); if (p) p.remove(); }

  function reload() { var E = ep(); if (E) { E.reload('opsQueue'); E.reload('inbox'); E.reload('walletPayouts'); } }
  function finish(c, text) {
    // D3: الفتح من شاشة «الفلوس» (V2.openMoney): نفس نافذة التأكيد، والنتيجة ترجع لصاحب الشاشة لا لبطاقات اللوحة.
    if (S.ext && S.ext.id === c.id) { var cb = S.ext.cb; S.ext = null; delete S.errMap[c.id]; S.busy = false; reload(); if (cb) cb(text); notify(); return; }
    S.done.unshift({ text: text, at: Date.now() });
    S.err = ''; S.busy = false; S.lockedId = '';
    var go = function () { S.deck = S.deck.filter(function (x) { return x.id !== c.id; }); S.leaving = ''; S.scrollTop = true; redraw(); };
    if (reduced()) go();
    else { S.leaving = c.id; redraw(); setTimeout(go, 240); }
    reload();
  }
  function fail(c, res) {
    S.busy = false; S.err = plainError(res); S.errMap[c.id] = S.err;
    if (res && (res.noReply || res.final)) { S.lockedId = c.id; reload(); }
    if (S.ext && S.ext.id === c.id) { var cb0 = S.ext; S.ext = null; if (cb0.fail) cb0.fail(S.err); }
    redraw();
  }
  // ⛔ نصوص الخطأ الجاية من طبقة الاتصال القديمة (عامية: «ما وصلناش رد» · «سجّل دخول تاني») بتتبدّل بفصحى ثابتة.
  // رسالة رفض المنصة نفسها (٤٠٠/٤٠٩ بسبب محدد) بتتعرض كما هي — هي اللي بتشرح ليه الفعل ما اتنفّذش.
  var NO_REPLY_AR = 'ما وصلنا رد — حدّث الصفحة وانظر ما حدث قبل أن تضغط مرة أخرى';
  var SESSION_AR = 'انتهت الجلسة — سجّل الدخول من جديد ثم جرّب';
  function plainError(res) {
    if (res && res.noReply) return NO_REPLY_AR;
    if (res && res.unauthorized) return SESSION_AR;
    return (res && res.error) || 'تعذّر تنفيذ العملية';
  }
  function track(c, p, doneText) {
    S.busy = true; S.err = ''; redraw();
    Promise.resolve(p).then(function (res) {
      res = res || {};
      if (res.ok) finish(c, doneText); else fail(c, res);
    }).catch(function (e) { fail(c, { error: (e && e.message) || 'تعذّر تنفيذ العملية' }); });
  }
  function run(c, a, keepExt) {
    if (S.busy || !a) return;
    var E = ep(); if (!E) return;
    var r = c.row;
    if (!keepExt) S.ext = null;
    delete S.errMap[c.id];
    switch (a.do) {
      case 'open': case 'goto': case 'section': S.ext = null; return openCard(c);
      case 'read': S.ext = null; return readCard(c);
      case 'reject_reason': return rejectModal(c);
      case 'invite_approve': return track(c, E.decideInvite(r.apiId, 'approve'), 'اعتُمدت دعوة ' + c.title);
      case 'person_accept': return personModal(c, 'accept');
      case 'person_reject': return personModal(c, 'reject');
      case 'person': S.ext = null; if (window.V2D2 && V2D2.openPerson) { showPill(); V2D2.openPerson(a.email); } return;
      case 'offer_approve': return offerAct(c, 'approve');
      case 'offer_reject': return offerAct(c, 'reject');
      case 'send': return track(c, E.expertFileSend(r, a.email, a.name, '', null), 'أُرسل «' + c.title + '» إلى ' + a.name);
      case 'decide': return a.confirm ? publishModal(c, a) : track(c, E.decideInboxItem(r, a.action, null, ''), doneVerb(c));
      case 'resolve': return track(c, E.resolveInboxItem(r, null), 'أُنهي: ' + c.title);
      case 'payout_settle': return payoutModal(c, 'settle');
      case 'payout_reject': return payoutModal(c, 'reject');
      case 'pay_confirm': return payConfirm(c);
      case 'pay_reject': return payReject(c);
      case 'brain_approve': case 'brain_reject': case 'brain_edit': return brainAct(c, a);
    }
  }
  // brain2: اعتماد/رفض/تعديل اقتراح العقل. الورقة (بنصها) في V2BRAIN؛ بعد النجاح ننهي البطاقة بـ`track` كأي قرار، والقفل (ردّ ضائع/حُسم من قبل) يقفل البطاقة.
  function brainAct(c, a) {
    if (!window.V2BRAIN || !V2BRAIN.act) return;
    V2BRAIN.act(c, a, function (res) {
      res = res || {};
      if (res.ok) track(c, Promise.resolve({ ok: true }), (res.text || 'تم') + ': ' + c.title);
      else fail(c, res);
    });
  }
  function doneVerb(c) {
    switch (c.kind) {
      case 'trainer': return 'قُبل المدرّب ' + c.title;
      case 'join': return 'قُبل طلب ' + c.title;
      case 'identity_doc': return 'وُثّقت هوية ' + c.title;
      case 'pending_user': return 'فُتحت المنصة لـ' + c.title;
      case 'invite': return 'اعتُمدت دعوة ' + c.title;
      case 'book': case 'creative': return 'اعتُمد ونُشر: ' + c.title;
      case 'topic': return 'اعتُمد الموضوع: ' + c.title;
      case 'program': return 'قُبل طلب البرنامج: ' + c.title;
      case 'founding': return 'عُلّمت الخطوة: ' + c.title;
      case 'signup': return 'تمّ الاطّلاع على تسجيل ' + c.title;
      case 'payfail': return 'تمّ الاطّلاع على دفع فشل: ' + c.title;
      default: return 'تم: ' + c.title;
    }
  }

  // —— نافذة تأكيد الفلوس (نمط efRefundModal): المبلغ والعملة والاسم قبل التنفيذ، وزرّ ما بيتضغطش مرتين.
  function confirmModal(o) {
    if (typeof window.openModal !== 'function') return;
    var rows = (o.rows || []).filter(function (r) { return r[1] !== '' && r[1] != null; });
    var field = '';
    if (o.field) {
      field = '<div class="fld"><label>' + esc(o.field.label) + '</label>'
        + (o.field.area ? '<textarea id="v2m_f" rows="3" maxlength="' + o.field.max + '"></textarea>' : '<input id="v2m_f" type="text" maxlength="' + o.field.max + '" autocomplete="off">')
        + '</div>';
    }
    var s = window.openModal(o.title,
      '<div class="mc-lead">' + o.lead + '</div>'
      + '<table class="mc-tab">' + rows.map(function (r) { return '<tr><td>' + esc(r[0]) + '</td><td>' + (r[0] === 'المبلغ' ? '<b>' + esc(r[1]) + '</b>' : esc(r[1])) + '</td></tr>'; }).join('') + '</table>'
      + field + '<div id="v2m_err"></div>'
      + '<div class="acts"><button class="btn ' + (o.btnCls || 'btn-primary') + '" id="v2m_go">' + esc(o.btn) + '</button>'
      + '<button class="btn btn-ghost" id="v2m_x">رجوع</button></div>'
      + (o.alt ? '<p class="v2m-altrow"><button type="button" class="v2m-altlink" id="v2m_alt">' + esc(o.alt.label) + '</button></p>' : ''));      // الرفض رابط أحمر صغير مستقل: زرّان فقط في الورقة
    var go = s.querySelector('#v2m_go'), x = s.querySelector('#v2m_x'), err = s.querySelector('#v2m_err'), f = s.querySelector('#v2m_f');
    var xTop = s.querySelector('[data-x]');
    var close = function () { if (!s.dataset.busy) window.closeModal(); };
    xTop.onclick = close; x.onclick = close; s.onclick = function (e) { if (e.target === s) close(); };
    var alt = s.querySelector('#v2m_alt');
    if (alt) alt.onclick = function () { if (s.dataset.busy) return; window.closeModal(); o.alt.run(); };
    var need = function () { return !!o.field && String(f.value || '').trim().length < (o.min || 1); };
    var sync = function () { if (!go.dataset.busy) go.disabled = need(); };
    if (f) { f.addEventListener('input', sync); sync(); setTimeout(function () { try { f.focus(); } catch (e) {} }, 30); }
    go.onclick = function () {
      if (go.dataset.busy || need()) return;           // الضغطة التانية ما بتعملش حاجة
      go.dataset.busy = '1'; s.dataset.busy = '1'; go.disabled = true; x.disabled = true; go.textContent = o.busy || '…'; err.innerHTML = '';
      Promise.resolve(o.run(f ? String(f.value || '').trim() : '')).then(function (res) {
        res = res || {};
        delete s.dataset.busy;
        if (res.ok) { window.closeModal(); o.onOk(); return; }
        x.disabled = false;
        err.innerHTML = '<div class="ef-err">' + esc(plainError(res)) + '</div>';
        if (res.noReply || res.final) { go.textContent = res.noReply ? 'حدّث الصفحة أولًا' : o.btn; S.lockedId = o.cardId; reload(); redraw(); return; }   // ⛔ لا ضغطة تانية من هنا
        delete go.dataset.busy; go.textContent = o.btn; sync();
      }).catch(function (e) {
        delete s.dataset.busy; delete go.dataset.busy; x.disabled = false;
        err.innerHTML = '<div class="ef-err">' + esc((e && e.message) || 'تعذّر تنفيذ العملية') + '</div>'; go.textContent = o.btn; sync();
      });
    };
    return s;
  }
  // ردّ كتابة الفلوس من المسارين الجديدين: {ok} أو {ok:false,error,noReply,final} (نفس منطق efFailed).
  function moneyResult(p) {
    return p.then(function () { return { ok: true }; }).catch(function (e) {
      var status = e && e.status, data = (e && e.data) || {}, msg = typeof data.error === 'string' ? data.error : '';
      var noReply = !!data.no_reply || !status || (status >= 500 && !msg);
      if (status === 401) return { ok: false, error: SESSION_AR, unauthorized: true };
      return { ok: false, error: msg || (noReply ? NO_REPLY_AR : 'تعذّر تنفيذ العملية'), noReply: noReply, final: !noReply && status === 409 };
    });
  }
  function payoutModal(c, which) {
    var m = c.primary.money, E = ep(), r = c.row;
    var amt = U.moneyText(m.amount, m.currency);
    var rows = [['المبلغ', U.fmtMoney(m.amount)], ['العملة', m.curName], ['الاسم', m.name], ['الطريقة', m.method], ['الوجهة', m.dest]];
    var path = '/platform-wallet-payouts/' + encodeURIComponent(r.pid) + '/' + which;
    if (which === 'settle') {
      confirmModal({
        title: 'تسجيل تحويل أرباح', cardId: c.id,
        lead: 'ستسجّل أنك حوّلت <b>' + esc(amt) + '</b> إلى <b>' + esc(m.name) + '</b>. بعد التسجيل يصل إشعار لصاحب الطلب. الخطوة لا يمكن الرجوع عنها.',
        rows: rows, field: { label: 'رقم أو مرجع التحويل (مطلوب)', max: 120 },
        btn: 'سجّل تحويل ' + amt, busy: 'جارٍ التسجيل…',
        alt: S.ext ? { label: 'ارفض الطلب', run: function () { payoutModal(c, 'reject'); } } : null,   // D3: «ارفض» جوه ورقة التأكيد مع سببه
        run: function (ref) { return moneyResult(E.post(path, { reference: ref, confirmed: true })); },
        onOk: function () { finish(c, 'سُجّل تحويل ' + amt + ' إلى ' + m.name); }
      });
    } else {
      confirmModal({
        title: 'رفض طلب التحويل', cardId: c.id,
        lead: 'سيُرفض طلب <b>' + esc(m.name) + '</b> بمبلغ <b>' + esc(amt) + '</b> وتعود الأموال إلى محفظة صاحب الطلب، ويصله السبب الذي تكتبه.',
        rows: rows, field: { label: 'سبب الرفض (مطلوب — يصل لصاحب الطلب)', max: 500, area: true },
        btn: 'ارفض الطلب', btnCls: 'btn-human', busy: 'جارٍ الرفض…',
        run: function (reason) { return moneyResult(E.post(path, { reason: reason, confirmed: true })); },
        onOk: function () { finish(c, 'رُفض طلب ' + m.name + ' وعادت ' + amt + ' إلى محفظة صاحب الطلب'); }
      });
    }
  }
  function payConfirm(c) {
    var m = c.primary.money, E = ep();
    var amt = U.moneyText(m.amount, m.currency);
    confirmModal({
      title: 'تأكيد الدفع', cardId: c.id,
      lead: 'ستؤكد استلام <b>' + esc(amt) + '</b> من <b>' + esc(m.name) + '</b>' + (m.what ? ' عن «' + esc(m.what) + '»' : '') + '. عند التأكيد يُفعَّل المنتج لصاحبه ويصله إشعار. تأكد من مطابقة الإيصال.',
      rows: [['المبلغ', U.fmtMoney(m.amount)], ['العملة', m.curName], ['الاسم', m.name], ['الطريقة', m.method], ['المرجع', m.ref]],
      btn: 'أكّد ' + amt, busy: 'جارٍ التأكيد…',
      run: function () { return Promise.resolve(E.decideInboxItem(c.row, 'approve', null, '', { confirmed: true })); },
      onOk: function () { finish(c, 'أُكّد دفع ' + amt + ' من ' + m.name); }
    });
  }
  function payReject(c) {
    var m = c.primary.money, E = ep();
    var amt = U.moneyText(m.amount, m.currency);
    confirmModal({
      title: 'رفض الدفعة', cardId: c.id,
      lead: 'سترفض دفعة <b>' + esc(amt) + '</b> من <b>' + esc(m.name) + '</b>. لا يُفعَّل شيء، ويصله السبب الذي تكتبه.',
      rows: [['المبلغ', U.fmtMoney(m.amount)], ['العملة', m.curName], ['الاسم', m.name], ['الطريقة', m.method], ['المرجع', m.ref]],
      field: { label: 'سبب الرفض (مطلوب)', max: 500, area: true },
      btn: 'ارفض الدفعة', btnCls: 'btn-human', busy: 'جارٍ الرفض…',
      run: function (reason) { return Promise.resolve(E.decideInboxItem(c.row, 'reject', null, reason)); },
      onOk: function () { finish(c, 'رُفضت دفعة ' + m.name); }
    });
  }

  // —— عروض الكتب من بطاقة القرار (D3): نفس ورقتي الاعتماد والرفض في شاشة «مراجعة العروض».
  function offerAct(c, which) {
    var of = (c.row && c.row.offerRow) || null;
    if (!of || !window.V2D3) return;
    var done = function (text) { finish(c, text); };
    if (which === 'approve') V2D3.openApprove(of, done); else V2D3.openReject(of, done);
  }
  // —— للشاشات الجديدة (D3): افتح نافذة التأكيد القديمة لبطاقة فلوس، والنتيجة تُسلَّم لـ`onDone(text)`.
  V2.openMoney = function (c, a, onDone) {
    if (!c || !a) return;
    S.ext = { id: c.id, cb: onDone || null };
    switch (a.do) {
      case 'payout_settle': return payoutModal(c, 'settle');
      case 'payout_reject': return payoutModal(c, 'reject');
      case 'pay_confirm': return payConfirm(c);
      case 'pay_reject': return payReject(c);
    }
  };

  // ------------------------------------------------------------------ R24 م٢ · القراية جوه البيت + قرارات الشخص
  // «اقرأ وقرّر»: درج الوارد القديم بكل أزراره بيتفتح فوق الشاشة الحالية (جوه قسمها) — مش «كل الوارد». نفس دوال الدرج القديم بالحرف.
  function readCard(c) {
    S.err = '';
    var ok = host().openReading ? host().openReading(c.row, { home: c.home }) : false;
    if (ok === false) gone(c);
  }
  var REJECT_LEAD = { pending_user: 'ما تفتحش له المنصة؛ يفضل زائرًا ويوصله السبب.', trainer: 'هيترفض طلب انضمامه ويوصله السبب كما تكتبه.',
                      join: 'هيترفض طلب تقديم الخدمة ويوصل السبب لصاحبه.', invite: 'هتترفض الدعوة ويوصل السبب للداعي.',
                      book: 'هيترفض ويوصل السبب لصاحبه.', creative: 'هيترفض ويوصل السبب لصاحبه.', topic: 'هيترفض ويوصل السبب لصاحبه.', program: 'هيترفض ويوصل السبب لصاحبه.' };
  function rejectModal(c) {
    var E = ep();
    if (c.kind === 'founding') {
      return confirmModal({ title: 'ليس مناسبًا', cardId: c.id, lead: 'هتعلّم طلب <b>' + esc(c.title) + '</b> «ليس مناسبًا» ويتشال من القرارات.', rows: [],
        btn: 'علّمه ليس مناسبًا', btnCls: 'btn-human', busy: 'جارٍ التسجيل…',
        run: function () { return Promise.resolve(E.decideInboxItem(c.row, 'reject', null, '')); }, onOk: function () { finish(c, 'اتعلّم «ليس مناسبًا»: ' + c.title); } });
    }
    confirmModal({ title: 'ارفض بسبب', cardId: c.id, lead: '<b>' + esc(c.title) + '</b>: ' + esc(REJECT_LEAD[c.kind] || 'هيترفض ويوصل السبب لصاحبه.'), rows: [],
      field: { label: 'السبب (مطلوب، بيوصل لصاحب الطلب كما تكتبه)', max: 500, area: true }, min: 5, btn: 'ارفض', btnCls: 'btn-human', busy: 'جارٍ الرفض…',
      run: function (reason) { return Promise.resolve(c.kind === 'invite' ? E.decideInvite(c.row.apiId, 'reject', reason) : E.decideInboxItem(c.row, 'reject', null, reason)); },
      onOk: function () { finish(c, 'رُفض: ' + c.title); } });
  }
  // النشر للناس (كتاب · عمل إبداعي · موضوع) وقبول طلب البرنامج: تأكيد باسم البند قبل ما يتنفّذ.
  var PUB_KIND = { book: 'الكتاب', creative: 'العمل الإبداعي', topic: 'الموضوع', program: 'طلب البرنامج' };
  function publishModal(c, a) {
    var E = ep(), publish = a.confirm !== 'program';
    confirmModal({ title: publish ? 'تأكيد النشر' : 'قبول الطلب', cardId: c.id,
      lead: (publish ? 'هتعتمد ' + esc(PUB_KIND[a.confirm] || 'البند') + ' وينزل للناس.' : 'هتقبل طلب البرنامج.') + ' اقرأه الأول لو لسه ما قرأتوش.',
      rows: [[publish ? 'البند' : 'صاحب الطلب', c.title], ['التفاصيل', c.brain]], btn: c.primary.label, busy: 'جارٍ التنفيذ…',
      run: function () { return Promise.resolve(E.decideInboxItem(c.row, 'approve', null, '')); },
      onOk: function () { finish(c, doneVerb(c)); } });
  }
  // بطاقة الشخص: تنفيذ كل خطوة بفعل بيتها نفسه، بالترتيب، وتوقف عند أول فشل وتقول إيه اللي اتعمل وإيه اللي لأ.
  var STEP_NAME = { accept: { pending_user: 'فتح المنصة', trainer: 'قبول الانضمام', join: 'قبول طلب الخدمة', founding: 'علامة الخبير المؤسس', invite: 'الموافقة على الدعوة' },
                    reject: { pending_user: 'رفض طلب الفتح', trainer: 'رفض الانضمام', join: 'رفض طلب الخدمة', founding: 'علامة «ليس مناسبًا»', invite: 'رفض الدعوة' } };
  function partCall(E, p, which, reason) {
    if (p.kind === 'invite') return E.decideInvite(p.row.apiId, which === 'accept' ? 'approve' : 'reject', reason);
    return E.decideInboxItem(p.row, which === 'accept' ? 'approve' : 'reject', null, reason || '');
  }
  function runParts(list, which, reason, doneIds) {
    var i = 0, doneT = [];
    function nextStep() {
      while (i < list.length && doneIds[list[i].id]) i++;
      if (i >= list.length) return Promise.resolve({ ok: true });
      var p = list[i], nm = STEP_NAME[which][p.kind] || p.tag;
      return Promise.resolve(partCall(ep(), p, which, reason)).then(function (res) {
        res = res || {};
        if (!res.ok) return { ok: false, error: (doneT.length ? 'تمّ: ' + doneT.join('، ') + '. ' : '') + 'لم يتم «' + nm + '»: ' + plainError(res), noReply: res.noReply, final: res.final };
        doneIds[p.id] = true; doneT.push(nm); i++;
        return nextStep();
      });
    }
    return nextStep();
  }
  function personModal(c, which) {
    var accept = which === 'accept', parts = c.parts || [];
    var list = accept ? parts : parts.filter(function (p) { return !!STEP_NAME.reject[p.kind]; });
    var steps = ((accept ? c.primary : c.secondary) || {}).steps || [];
    var doneIds = {};
    confirmModal({ title: accept ? 'قبول كل طلبات ' + c.title : 'رفض طلبات ' + c.title, cardId: c.id,
      lead: (accept ? 'ده اللي هيحصل بالترتيب:' : 'ده اللي هيحصل بالترتيب، والسبب بيوصل لصاحب الطلب كما تكتبه:'),
      rows: steps.map(function (t, i) { return [U.ar(i + 1), t]; }),
      field: accept ? null : { label: 'السبب (مطلوب، بيوصل لصاحب الطلب كما تكتبه)', max: 500, area: true }, min: accept ? 0 : 5,
      btn: accept ? 'أيوه، نفّذ' : 'ارفض', btnCls: accept ? '' : 'btn-human', busy: 'جارٍ التنفيذ…',
      run: function (reason) { return runParts(list, which, reason, doneIds); },
      onOk: function () { finish(c, accept ? 'تمّ قبول كل طلبات ' + c.title : 'رُفضت طلبات ' + c.title); } });
  }

  // للأقسام وصفحة الشخص: نفس المنفّذ بالحرف، والنتيجة ترجع لصاحب الشاشة (`onDone(text)` / `onFail(msg)`).
  V2.runCard = function (c, a, onDone, onFail) {
    if (!c || !a) return;
    S.ext = { id: c.id, cb: onDone || null, fail: onFail || null };
    run(c, a, true);
  };
  V2.snooze = snoozeModal; V2.dismiss = dismissModal; V2.restore = restoreItem; V2.retry = reload;
  V2.errorOf = function (id) { return S.errMap[id] || ''; };
  V2.isBusy = function () { return !!S.busy; };
  V2.openCard = openCard;
  // الدرج المفتوح فوق القسم اتقفل (بعد قرار أو بالرجوع): نحدّث المصادر والشريط، وفي وضع التركيز نشيل البطاقة اللي خلصت.
  V2.afterReading = function () {
    if (S.mode === 'focus' && host().isHome && host().isHome()) {
      reloadAll(function () { S.deck = S.deck.filter(stillPending); S.lockedId = ''; S.busy = false; S.scrollTop = true; redraw(); });
    } else { reload(); notify(); }
  };

  // ------------------------------------------------------------------ نقطة الدخول
  function redraw() { if (S.view && host().isHome && host().isHome()) V2.render(S.view); notify(); }
  V2.render = function (v) {
    S.view = v;
    removePill();
    // brain2: وصول رأي أو اقتراح والبطاقة معروضة ⇒ إعادة رسمها (مؤقّت اللوحة لا يعمل في وضع التركيز).
    if (!S.bl && window.V2BRAIN && V2BRAIN.listen) S.bl = V2BRAIN.listen(function () { if (S.mode === 'focus' && host().isHome && host().isHome()) redraw(); });
    // رجوع للّوحة من القائمة (مش من زرّ «العودة إلى القرارات») ⇒ على اللوحة نفسها لا على بطاقة قديمة.
    if (S.away) { S.away = false; if (!S.resume) { S.mode = 'board'; S.panel = null; S.err = ''; S.busy = false; } S.resume = false; }
    load();
    var d = compute();
    S.sig = signature();
    if (S.mode === 'focus') drawFocus(v, d);
    else drawBoard(v, d);
    // الغلاف الجديد يخفي ترويسة القسم وتبويباته أثناء وضع التركيز.
    try { var ap = document.querySelector('.app'); if (ap) ap.classList.toggle('v2-focus', S.mode === 'focus'); } catch (e) {}
    if (!S.timer) {
      // المحمّلات الأولى بتبدأ من bootNavCounts بدون callback عندنا ⇒ نلاحظ تغيّر الحالة بفحص خفيف، ونعيد الرسم في اللوحة بس.
      S.timer = setInterval(function () {
        if (!(host().isHome && host().isHome())) { clearInterval(S.timer); S.timer = null; return; }
        if (S.mode === 'focus' || document.getElementById('epModal')) return;
        if (signature() !== S.sig) redraw();
      }, 400);
    }
  };
  // أول فتح من الهاش/القائمة يبدأ على اللوحة نفسها لا على وضع تركيز قديم.
  V2.leave = function () { S.away = true; if (S.timer) { clearInterval(S.timer); S.timer = null; } };
  V2._state = S;
  V2.plainError = plainError;     // D2: نفس نصوص الخطأ لأزرار التذاكر

  // —— للغلاف الجديد (D1-B): نفس المربّعات بنفس الأعداد، وتحميل كل المصادر، وتبديل الوضع من التبويبات.
  V2.tiles = function () { var g = gather(); return L.v2SectionTiles(L.v2Tiles(g.Q, g.extras), g.split, g.avail); };
  // R24 م٢: الشريط الواحد لكل قسم + القرارات كلها (بنفس الفلتر) — من نفس `gather()` اللي بتحسب منه المربّعات والقايمة الجانبية.
  V2.strip = function (key) { var g = gather(); return L.v2Strip(g.split, key); };
  V2.split = function () { return gather().split; };
  V2.counts = function () { return gather().split.counts; };
  V2.tileLoading = function (key) { return tileLoading({ key: key }); };
  V2.loadAll = function (cb) {
    var E = ep();
    if (!E || !E.authed) return;
    SOURCES.forEach(function (k) { E.ensure(k, cb || null); });
    try { if (window.V2D3 && V2D3.preload) V2D3.preload(); } catch (e) {}      // D3: الدفعات العالقة وعروض الكتب لبطاقات القرار
  };
  V2.sourcesSignature = function () { return signature() + '|' + SOURCES.map(function (k) { return stateOf(k); }).join(''); };
  V2.mode = function () { return S.mode; };
  V2.setMode = function (m) {
    S.mode = 'board';
    if (m === 'brain' && host().openSection) setTimeout(function () { host().openSection('brain', 'log'); }, 0);   // رابط قديم v2mode=brain ⇒ القسم الجديد
    S.away = false; S.resume = false; S.panel = null; S.err = ''; S.busy = false;
  };
})();
