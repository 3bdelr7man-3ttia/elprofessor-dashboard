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
    deck: [], total: 0, done: [],
    busy: false, err: '', lockedId: '',
    panel: null,          // health | user
    view: null, sig: '', timer: null, leaving: ''
  };
  var V2 = window.V2 = {};

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
    var rows = stateOf('inbox') === 'ready' ? (window.INBOX || []).filter(function (r) { return !r.fyi; }) : null;
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
    return { E: E, D: D, now: now, Q: Q, rows: rows, inboxFailed: inboxFailed, payouts: payouts, inboxTrunc: inboxTrunc, extras: extras, d3: d3 };
  }
  function compute() {
    var g = gather(), Q = g.Q, rows = g.rows, now = g.now, inboxFailed = g.inboxFailed, inboxTrunc = g.inboxTrunc;
    var tiles = L.v2Tiles(Q, g.extras);
    var decisions = L.v2Decisions(rows, g.payouts, Q, { now: now, inboxFailed: inboxFailed, inboxTruncated: inboxTrunc,
                                                          stuck: g.d3 ? g.d3.stuck : null, offers: g.d3 ? g.d3.offers : null });
    var truncated = (inboxTrunc || []).map(function (t) { return String(t).split(':')[0].trim(); });
    var failed = [];
    if (stateOf('opsQueue') === 'error') failed.push('بيانات المنصة');
    if (stateOf('inbox') === 'error') failed.push('الوارد');
    if (stateOf('walletPayouts') === 'error') failed.push('تحويلات الأرباح');
    inboxFailed.forEach(function (n) { if (failed.indexOf(n) < 0) failed.push(n); });
    if (g.d3) g.d3.failed.forEach(function (n) { if (failed.indexOf(n) < 0) failed.push(n); });
    return {
      now: now, Q: Q, rows: rows, tiles: tiles, decisions: decisions, failed: failed, truncated: truncated,
      health: L.v2Health(Q, now), next: L.v2Next(decisions),
      brainLog: rows ? L.v2BrainLog(rows, now) : null,
      loading: isLoading('opsQueue') || isLoading('inbox') || isLoading('walletPayouts')
    };
  }
  function signature() {
    var E = ep();
    return SOURCES.map(stateOf).join(',') + '|' + ((window.INBOX || []).length) + '|' + (E && E.data.walletPayouts ? E.data.walletPayouts.count : '')
      + (window.V2D3 ? '|' + V2D3.sig() : '') + (window.V2SEC && V2SEC.brain && V2SEC.brain.sig ? '|' + V2SEC.brain.sig() : '');
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
  function header(d) {
    var hp = healthPill(d), E = ep(), u = (E && E.user) || {};
    var name = u.name || u.full_name || (E && E.user && E.user.email) || 'المؤسس';
    var pop = '';
    if (S.panel === 'health') pop = '<div class="v2-pop" data-pop>' + popHealth(d) + '</div>';
    if (S.panel === 'user') pop = '<div class="v2-pop v2-pop-u" data-pop><div class="v2-pop-t">' + esc(name) + '</div><p class="v2-pop-p">المؤسس</p><button class="v2-btn2" data-a="logout">تسجيل الخروج</button></div>';
    return '<header class="v2-head"><div class="v2-logo"><span class="v2-mark">' + LOGO + '</span><div><b>البروفيسور</b><small>اللوحة</small></div></div>'
      + '<div class="v2-tools">'
      + '<button class="v2-health ' + hp.cls + '" data-a="health" aria-expanded="' + (S.panel === 'health') + '"><i></i><span>' + esc(hp.text) + '</span></button>'
      + '<button class="v2-iconbtn" data-a="health" aria-label="التنبيهات" title="التنبيهات">' + BELL + (hp.n ? '<em>' + esc(U.ar(hp.n)) + '</em>' : '') + '</button>'
      + '<button class="v2-iconbtn" data-a="user" aria-label="حسابي" title="حسابي">' + USER + '</button>'
      + pop + '</div></header>';
  }
  function nextBar(d) {
    var n = d.decisions.length, nx = d.next;
    var brainN = d.brainLog ? d.brainLog.length : null;
    var left, btn = '';
    if (d.loading && !nx) {
      left = '<small>الحاجة الجاية</small><b>…جارٍ جلب القرارات</b>';
    } else if (nx) {
      left = '<small>الحاجة الجاية</small><b>' + esc(L.v2NextLine(nx)) + '</b>' + (nx.brain ? '<p>' + esc(nx.brain) + '</p>' : '');
      btn = '<button class="v2-start" data-a="start">ابدأ القرارات (' + esc(U.ar(n)) + ')</button>';
    } else if (d.failed.length) {
      // ⛔ لا «العقل يعمل» ولا «لا توجد قرارات» فوق جلب فاشل: لا نعرف إن كان شيء ينتظرك.
      left = '<small>الحاجة الجاية</small><b>تعذّر جلب القرارات — لا نعرف إن كان شيء ينتظرك</b>';
    } else if (d.truncated.length) {
      left = '<small>الحاجة الجاية</small><b>القائمة ناقصة — معروض جزء من القرارات فقط</b>';
    } else {
      left = '<small>الحاجة الجاية</small><b>لا توجد قرارات بانتظارك الآن — العقل يعمل</b>';
    }
    var sub = (brainN != null && brainN > 0) ? '<span class="v2-brainline">العقل وزّع ' + esc(U.U(brainN, ['ملفًا واحدًا', 'ملفين', 'ملفات', 'ملفًا'])) + ' اليوم</span>' : '';
    var warn = d.failed.length ? '<span class="v2-warnline">تعذّر جلب: ' + esc(d.failed.join(' · ')) + ' — القائمة ناقصة</span>' : '';
    if (d.truncated.length) warn += '<span class="v2-warnline">معروض جزء فقط من: ' + esc(d.truncated.join(' · ')) + ' — القائمة ناقصة</span>';
    return '<section class="v2-next" aria-label="الحاجة الجاية"><img class="v2-av" src="' + img('brain-avatar') + '" alt="">'
      + '<div class="v2-nt">' + left + sub + warn + '</div>' + btn + '</section>';
  }
  function tileHtml(t, d) {
    var loading = tileLoading(t);
    var circle = '';
    if (loading) circle = '<span class="v2-cnt ld">…</span>';
    else if (t.failed) circle = '<span class="v2-cnt fail">' + esc(L.FAILED_TEXT) + '</span>';
    else if (t.count) circle = '<span class="v2-cnt' + (t.hot ? ' hot' : '') + '"' + (t.partial ? ' title="العدد ناقص — تعذّر جلب بعض المصادر"' : '') + '>' + esc(U.ar(t.count)) + (t.partial ? '+' : '') + '</span>';
    var nextTxt = loading ? '' : t.next;
    return '<button class="v2-tile" data-tile="' + esc(t.key) + '" style="--rgb:' + (TILE_RGB[t.key] || '33,38,46') + ';background-image:url(' + img(t.img) + ')">'
      + circle + '<span class="v2-tt"><b>' + esc(t.label) + '</b><small>' + esc(nextTxt) + '</small></span></button>';
  }
  var DEPS = { files: ['opsQueue'], disputes: ['opsQueue'], courses: ['opsQueue'], money: ['opsQueue'], content: ['opsQueue'],
               books: ['inbox'], brain: ['inbox'], market: ['market'], people: ['pendingUsers', 'invites', 'inbox', 'opsQueue'] };
  function tileLoading(t) { return (DEPS[t.key] || []).some(isLoading); }

  function drawBoard(v, d) {
    var tiles = d.tiles.map(function (t) { return tileHtml(t, d); }).join('');
    v.innerHTML = '<div class="v2">' + header(d) + nextBar(d) + '<section class="v2-grid" aria-label="الأقسام">' + tiles + '</section></div>';
    wireCommon(v, d);
    var st = v.querySelector('[data-a="start"]');
    if (st) st.onclick = function () { startFocus(d); };
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
  function openTile(key, d) {
    var t = d.tiles.filter(function (x) { return x.key === key; })[0];
    if (!t) return;
    if (t.internal) {
      if (host().openSection) host().openSection('brain', 'log');       // سجل العقل القديم اتشال: القسم الجديد «العقل وقواعده» هو الوحيد
      return;
    }
    // D2: مربّعا الملفات والنزاعات يفتحان لوحة التذاكر (لما الغلاف الجديد شغّال) بدل الوارد القديم.
    // D3: «الفلوس» و«الكتب» كذلك (تبويبهما الأول: نظرة · مراجعة العروض). المحتوى: «خط النشر».
    if ((key === 'files' || key === 'disputes' || key === 'money' || key === 'books' || key === 'content') && window.V2SHELL && V2SHELL.on && host().openSection) { host().openSection(key); return; }
    if (host().goOps) host().goOps(t.dest, t.land);
  }

  // —— وضع التركيز: بطاقة واحدة
  function startFocus(d) {
    S.deck = d.decisions.slice(); S.total = S.deck.length; S.done = []; S.err = ''; S.lockedId = ''; S.busy = false; S.busyText = '';
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
    if (d.failed.length) p.push('تعذّر جلب: ' + d.failed.join(' · '));
    if (d.truncated.length) p.push('معروض جزء فقط من: ' + d.truncated.join(' · '));
    return p.join(' — ');
  }
  function counter() { return U.ar(S.total - S.deck.length + 1) + ' من ' + U.ar(S.total); }
  function drawFocus(v, d) {
    var c = S.deck[0];
    var done = S.done.length
      ? '<aside class="v2-done"><h3>أنجزت الآن</h3><ul>' + S.done.slice(0, 12).map(function (x) { return '<li>' + esc(x.text) + '</li>'; }).join('') + '</ul></aside>' : '';
    if (!c) {
      v.innerHTML = '<div class="v2 v2-focus"><div class="v2-end"><img src="' + img('brain-avatar') + '" alt="">'
        + '<h2>' + endText(d) + '</h2>'
        + (incompleteLine(d) ? '<p class="v2-warnline">' + esc(incompleteLine(d)) + '</p>' : '')
        + '<button class="v2-start" data-a="back">العودة إلى اللوحة</button>' + done + '</div></div>';
      v.querySelector('[data-a="back"]').onclick = leaveFocus;
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
    var showOpen = !(c.primary && c.primary.act.do === 'open') && !(c.secondary && c.secondary.act.do === 'open');
    if (showOpen) acts += '<button class="v2-btn3" data-a="open"' + (S.busy ? ' disabled' : '') + '>غيّر / افتح</button>';
    acts += '<button class="v2-btn3" data-a="later"' + (S.busy ? ' disabled' : '') + '>لاحقًا</button>';
    var facts = (c.facts || []).filter(function (f) { return f.v; }).map(function (f) { return '<div><small>' + esc(f.k) + '</small><b>' + esc(f.v) + '</b></div>'; }).join('');
    v.innerHTML = '<div class="v2 v2-focus">'
      + '<div class="v2-ftop"><button class="v2-link" data-a="back">' + BACK + 'اللوحة</button><span class="v2-count">' + esc(counter()) + '</span><span class="v2-prog"><i style="width:' + pct + '%"></i></span></div>'
      + '<div class="v2-fgrid' + (done ? '' : ' solo') + '"><article class="v2-card' + (S.leaving === c.id ? ' v2-out' : '') + '" data-id="' + esc(c.id) + '" data-kind="' + esc(c.kind) + '">'
      + '<div class="v2-cimg" style="background-image:url(' + img(c.img) + ')"><span class="v2-tag">' + esc(c.tag) + '</span>' + (c.ageText ? '<span class="v2-age">' + esc(c.ageText) + '</span>' : '') + '</div>'
      + '<div class="v2-cbody"><h2>' + (c.person && window.V2D2 ? V2D2.link(c.title, c.person.email) : esc(c.title)) + '</h2>' + (c.sub ? '<p class="v2-csub">' + esc(c.sub) + '</p>' : '')
      + '<div class="v2-brain"><img src="' + img('brain-avatar') + '" alt=""><div><b>' + esc(c.brainHead) + '</b><p>' + esc(c.brain) + '</p>' + (c.reason ? '<p class="v2-reason">' + esc(c.reason) + '</p>' : '') + '</div></div>'
      + (c.warn ? '<div class="v2-cwarn">' + esc(c.warn) + '</div>' : '')
      + (facts ? '<div class="v2-facts">' + facts + '</div>' : '')
      + (c.link ? '<p class="v2-linkp"><a href="' + esc(c.link.url) + '" target="_blank" rel="noopener noreferrer">' + esc(c.link.label) + '</a></p>' : '')
      + (S.err ? '<div class="v2-err" role="alert">' + esc(S.err) + '</div>' : '')
      + '<div class="v2-acts">' + acts + '</div></div></article>' + done + '</div></div>';
    v.querySelector('[data-a="back"]').onclick = leaveFocus;
    var q = function (a, fn) { var b = v.querySelector('[data-a="' + a + '"]'); if (b) b.onclick = fn; };
    q('primary', function () { run(c, c.primary.act); });
    q('refresh', function () { refreshLocked(c); });
    q('secondary', function () { run(c, c.secondary.act); });
    q('open', function () { openCard(c); });
    q('later', function () { S.deck.push(S.deck.shift()); S.err = ''; redraw(); });
    if (S.err) { var er = v.querySelector('.v2-err'); if (er && er.scrollIntoView) { try { er.scrollIntoView({ block: 'center' }); } catch (e) {} } }
    if (S.scrollTop) { S.scrollTop = false; try { var ct = document.querySelector('.content'); if (ct) ct.scrollTop = 0; } catch (e) {} }
  }
  function leaveFocus() {
    removePill();
    S.mode = 'board'; S.err = ''; S.busy = false;
    var E = ep(); if (E) { E.reload('opsQueue'); E.reload('inbox'); E.reload('walletPayouts'); }
    redraw();
  }

  // ------------------------------------------------------------------ التنفيذ
  function rowKey(r) { return r ? [r.apiKind, r.dsrc || '', r.apiId].join('|') : ''; }
  function stillPending(c) {
    var E = ep();
    if (c.kind === 'payout') {
      if (stateOf('walletPayouts') !== 'ready' || !E.data.walletPayouts) return true;
      return (E.data.walletPayouts.rows || []).some(function (p) { return p.pid === c.row.pid; });
    }
    if (c.kind === 'course' || c.kind === 'live' || c.kind === 'stuck_payment') return true;
    if (c.kind === 'book_offer') {
      var d3 = window.V2D3 ? V2D3.cardSources() : null;
      return !d3 || !d3.offers.length || d3.offers.some(function (o) { return o.id === (c.row.offerRow || {}).id; });
    }
    if (stateOf('inbox') !== 'ready') return true;
    var key = rowKey(c.row);
    return (window.INBOX || []).some(function (r) { return !r.fyi && rowKey(r) === key; });
  }
  // انتظار تحميل المصادر التلاتة (مش مجرد طلبها): الاستدعاء بيرجع مرتين لكل مفتاح (بداية التحميل ونهايته).
  function reloadAll(done) {
    var E = ep(), keys = ['opsQueue', 'inbox', 'walletPayouts'], fin = false;
    if (!E || !E.authed) { done(); return; }
    var finish1 = function () { if (!fin) { fin = true; done(); } };
    var check = function () { if (keys.every(function (k) { return stateOf(k) !== 'loading'; })) finish1(); };
    setTimeout(finish1, 20000);
    keys.forEach(function (k) { E.reload(k, check); });
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
  function openCard(c) {
    var a = c.open || { do: 'open' };
    S.err = '';
    if (a.do === 'section' && host().openSection) { showPill(); host().openSection(a.section, a.tab); return; }
    if (a.do === 'goto' && window.V2SHELL && V2SHELL.on && host().openSection) {
      // D3: تحويلات الأرباح والإيصالات لها تبويباتها الجديدة تحت «الفلوس».
      var dest = a.mod === 'finance' ? (a.land === 'stuck_card_payments' ? 'receipts' : a.land === 'wallet_payouts_pending' ? 'payouts' : null)
        : (a.mod === 'escrow' && a.land === 'manual_payments_pending') ? 'receipts' : null;
      if (dest) { showPill(); host().openSection('money', dest); return; }
    }
    if (a.do === 'goto') { showPill(); if (host().goOps) host().goOps(a.mod, a.land); return; }
    showPill();
    if (host().openRow) host().openRow(c.row);
  }
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
    if (S.ext && S.ext.id === c.id) { var cb = S.ext.cb; S.ext = null; reload(); if (cb) cb(text); return; }
    S.done.unshift({ text: text, at: Date.now() });
    S.err = ''; S.busy = false; S.lockedId = '';
    var go = function () { S.deck = S.deck.filter(function (x) { return x.id !== c.id; }); S.leaving = ''; S.scrollTop = true; redraw(); };
    if (reduced()) go();
    else { S.leaving = c.id; redraw(); setTimeout(go, 240); }
    reload();
  }
  function fail(c, res) {
    S.busy = false; S.err = plainError(res);
    if (res && (res.noReply || res.final)) { S.lockedId = c.id; reload(); }
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
  function run(c, a) {
    if (S.busy || !a) return;
    var E = ep(); if (!E) return;
    var r = c.row;
    S.ext = null;
    switch (a.do) {
      case 'open': case 'goto': case 'section': return openCard(c);
      case 'person': if (window.V2D2 && V2D2.openPerson) { showPill(); V2D2.openPerson(a.email); } return;
      case 'offer_approve': return offerAct(c, 'approve');
      case 'offer_reject': return offerAct(c, 'reject');
      case 'send': return track(c, E.expertFileSend(r, a.email, a.name, '', null), 'أُرسل «' + c.title + '» إلى ' + a.name);
      case 'decide': return track(c, E.decideInboxItem(r, a.action, null, ''), doneVerb(c));
      case 'resolve': return track(c, E.resolveInboxItem(r, null), 'أُنهي: ' + c.title);
      case 'payout_settle': return payoutModal(c, 'settle');
      case 'payout_reject': return payoutModal(c, 'reject');
      case 'pay_confirm': return payConfirm(c);
      case 'pay_reject': return payReject(c);
    }
  }
  function doneVerb(c) {
    switch (c.kind) {
      case 'trainer': return 'قُبل المدرّب ' + c.title;
      case 'join': return 'قُبل طلب ' + c.title;
      case 'pending_user': return 'فُتحت المنصة لـ' + c.title;
      case 'founding': return 'عُلّمت الخطوة: ' + c.title;
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
      + (o.alt ? '<button class="btn btn-ghost v2m-alt" id="v2m_alt">' + esc(o.alt.label) + '</button>' : '')
      + '<button class="btn btn-ghost" id="v2m_x">رجوع</button></div>');
    var go = s.querySelector('#v2m_go'), x = s.querySelector('#v2m_x'), err = s.querySelector('#v2m_err'), f = s.querySelector('#v2m_f');
    var xTop = s.querySelector('[data-x]');
    var close = function () { if (!s.dataset.busy) window.closeModal(); };
    xTop.onclick = close; x.onclick = close; s.onclick = function (e) { if (e.target === s) close(); };
    var alt = s.querySelector('#v2m_alt');
    if (alt) alt.onclick = function () { if (s.dataset.busy) return; window.closeModal(); o.alt.run(); };
    var need = function () { return !!o.field && !String(f.value || '').trim(); };
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
    var rows = [['المبلغ', U.fmt(m.amount)], ['العملة', m.curName], ['الاسم', m.name], ['الطريقة', m.method], ['الوجهة', m.dest]];
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
      rows: [['المبلغ', U.fmt(m.amount)], ['العملة', m.curName], ['الاسم', m.name], ['الطريقة', m.method], ['المرجع', m.ref]],
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
      rows: [['المبلغ', U.fmt(m.amount)], ['العملة', m.curName], ['الاسم', m.name], ['الطريقة', m.method], ['المرجع', m.ref]],
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

  // ------------------------------------------------------------------ نقطة الدخول
  function redraw() { if (S.view && host().isHome && host().isHome()) V2.render(S.view); }
  V2.render = function (v) {
    S.view = v;
    removePill();
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
  V2.tiles = function () { var g = gather(); return L.v2Tiles(g.Q, g.extras); };
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
