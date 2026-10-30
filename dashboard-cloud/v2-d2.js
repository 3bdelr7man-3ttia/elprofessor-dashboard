/* ============================================================================
 * v2-d2.js — الجولة D2: لوحات التذاكر بعدّاد («ملفات الخبراء» و«النزاعات والاستردادات») وصفحة الشخص الواحد وبحث الناس.
 * ⛔ لا منطق عمل هنا: التصنيف والعدّادات ونصوص الشخص من `v2-logic.js` (نقي)، والأزرار بتنادي نفس دوال D1 بالحرف
 *   (`EP.expertFileSend` للإرسال، وفتح الدرج القديم للباقي). ⛔ لا قرار فلوس من التذكرة: «افتح وقرّر» يفتح الدرج بتأكيده القديم.
 * ⛔ المفتاح مقفول افتراضيًا: الملف بيتحمّل دايمًا لكنه ما بيرسم شيئًا إلا لو index.html نادى `V2D2.render` (وده ما بيحصل
 *   إلا والغلاف الجديد شغّال، لأن الموديولات `v2files`/`v2disputes`/`v2person` ما لها وجود برّاه).
 * ⛔ ولا طلب شبكة من هنا غير: محمّلات اللوحة الموجودة · `GET /api/v2/person` · `GET /api/platform-users?search=` (الموجود).
 * ========================================================================== */
(function () {
  'use strict';
  var L = window.V2L;
  if (!L) return;
  var U = L.util;
  var D2 = window.V2D2 = {};
  var MODS = { v2files: 1, v2disputes: 1, v2person: 1 };
  var SOURCES = ['opsQueue', 'inbox', 'walletPayouts', 'invites', 'pendingUsers', 'market'];
  // أسماء المصادر كما تسمّيها طبقة الوارد القديمة (مفاتيح المطابقة فقط) ⇒ نصها الظاهر بفصحى.
  var LABEL_AR = { 'آراء مستنية مراجعتك': 'آراء تنتظر مراجعتك', 'ملفات مستنية توزيع': 'ملفات تنتظر التوزيع', 'آراء متأخرة': 'آراء متأخرة',
                   'نزاعات الملفات': 'نزاعات الملفات', 'ملفات فلوسها واقفة': 'ملفات أموالها متوقفة', 'ملفات اتدفعت وما وصلتش للتوزيع': 'ملفات دُفعت ولم تصل إلى التوزيع',
                   'قضايا فيها ملاحظة': 'قضايا عليها ملاحظة', 'نزاعات الاستشارات': 'نزاعات الاستشارات', 'استشارات قديمة': 'استشارات قديمة' };
  var FILE_LABELS = ['آراء مستنية مراجعتك', 'ملفات مستنية توزيع', 'آراء متأخرة', 'نزاعات الملفات', 'ملفات فلوسها واقفة', 'ملفات اتدفعت وما وصلتش للتوزيع'];
  var DISPUTE_LABELS = ['نزاعات الملفات', 'قضايا فيها ملاحظة', 'ملفات اتدفعت وما وصلتش للتوزيع', 'نزاعات الاستشارات', 'استشارات قديمة'];
  function plainLabels(list) { return list.map(function (l) { return LABEL_AR[l] || l; }); }
  var S = {
    view: null, mod: '', sig: '', poll: null, minute: null,
    col: { files: '', disputes: '' }, picked: { files: false, disputes: false },          // العمود الظاهر في الموبايل
    busy: {}, err: {}, done: {}, locked: {},   // حالة أزرار التذاكر
    person: { email: '', state: 'idle', resp: null, seq: 0 }
  };

  function esc(s) { return String(s == null ? '' : s).replace(/[&<>"']/g, function (c) { return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]; }); }
  function host() { return window.V2_HOST || {}; }
  function ep() { return window.EP || null; }
  function stateOf(k) { var E = ep(); return (E && E.state && E.state[k]) || 'idle'; }
  function isLoading(k) { var s = stateOf(k); return s === 'idle' || s === 'loading'; }
  function img(name) { return 'v2/img/' + name + '.jpg'; }
  var BRAIN = '<img class="v2d-bav" src="' + img('brain-avatar') + '" alt="">';
  var ARROW = '<span class="v2d-arrow" aria-hidden="true">←</span>';

  D2.owns = function (mod) { return !!MODS[mod]; };

  // ------------------------------------------------------------------ تحميل وجمع
  function loadAll() {
    var E = ep();
    if (!E || !E.authed) return;
    SOURCES.forEach(function (k) { E.ensure(k, null); });
  }
  function gather() {
    var E = ep(), D = (E && E.data) || {}, now = S.nowOverride || Date.now();
    var inboxReady = stateOf('inbox') === 'ready';
    var Q = stateOf('opsQueue') === 'ready' ? (D.opsQueue || null) : null;
    var rows = inboxReady ? (window.INBOX || []) : null;       // ⛔ بما فيها صفوف «للعلم» (هي عمود «عند الخبراء»)
    var live = rows ? rows.filter(function (r) { return r && !r.fyi; }) : null;
    var auto = D.efSettings && typeof D.efSettings.auto_assign === 'boolean' ? D.efSettings.auto_assign : undefined;
    return {
      now: now, Q: Q, rows: rows, failed: (window.INBOX_FAILED || []).slice(), trunc: (window.INBOX_TRUNCATED || []).slice(),
      inboxState: stateOf('inbox'), queueState: stateOf('opsQueue'), auto: auto,
      brainToday: live ? L.v2BrainLog(live, now).length : 0
    };
  }
  function fileRows(rows) {
    return (rows || []).filter(function (r) { return r && r.apiKind === 'expert_file' && r.efLane !== 'unactivated' && r.efLane !== 'case_disputed'; });
  }
  function signature() {
    var E = ep();
    var n = (window.INBOX || []).length;
    return SOURCES.map(stateOf).join(',') + '|' + n + '|' + (window.INBOX_FAILED || []).length + '|' + (window.INBOX_TRUNCATED || []).length
      + '|' + (E && E.data && E.data.efSettings ? String(E.data.efSettings.auto_assign) : '');
  }

  // ------------------------------------------------------------------ شرائح تحذير مشتركة
  function strips(g, labels) {
    var out = '';
    var failed = plainLabels(g.failed.filter(function (l) { return labels.indexOf(l) > -1; }));
    if (stateOf('opsQueue') === 'error') failed.push('بيانات المنصة');
    if (failed.length) out += '<div class="v2d-warn" role="status">تعذّر جلب: ' + esc(failed.join(' · ')) + ' — القائمة ناقصة وليس معناه أنه لا شيء ينتظرك</div>';
    var trunc = plainLabels(g.trunc.map(function (t) { return String(t).split(':')[0].trim(); }).filter(function (l) { return labels.indexOf(l) > -1; }));
    if (trunc.length) out += '<div class="v2d-warn" role="status">معروض جزء فقط من: ' + esc(trunc.join(' · ')) + ' — القائمة ناقصة</div>';
    return out;
  }
  function loadingOrError(g, title) {
    if (g.inboxState === 'error') {
      return '<div class="v2d"><div class="v2d-empty big"><b>تعذّر جلب ' + esc(title) + '</b><p>لا نعرف الآن إن كان شيء ينتظرك، فلا تعتبر الشاشة فارغة.</p>'
        + '<button class="v2d-btn1" data-a="reload">أعد المحاولة</button></div></div>';
    }
    if (g.inboxState !== 'ready') {
      return '<div class="v2d"><div class="v2d-empty big"><b>…جارٍ جلب ' + esc(title) + '</b></div></div>';
    }
    return '';
  }

  // ------------------------------------------------------------------ تذكرة ملف
  function personLink(name, email, cls) {
    if (!email) return esc(name);
    return '<a class="v2d-person ' + (cls || '') + '" href="' + esc(L.sectionHash('people', 'person', email)) + '" data-person="' + esc(email) + '">' + esc(name) + '</a>';
  }
  D2.link = function (name, email) {
    if (!email || !window.V2_ON) return esc(name);
    return personLink(name, email, 'v2d-inline');
  };

  function ticketHtml(t, board) {
    var id = t.id, busy = !!S.busy[id], err = S.err[id] || '', done = S.done[id] || '';
    var who = '';
    if (board === 'files') {
      var c = t.client ? esc(t.client) : 'صاحب الطلب';
      var e = t.expert && t.expert.name ? (t.expert.email ? personLink(t.expert.name, t.expert.email) : esc(t.expert.name)) : '<span class="v2d-mute">بلا خبير بعد</span>';
      who = '<p class="v2d-who"><span>' + c + '</span>' + ARROW + '<span>' + e + '</span></p>';
    } else {
      var parts = '<span>' + (t.client ? esc(t.client) : 'صاحب الطلب') + '</span>';
      if (t.expert) parts += ARROW + '<span>' + (t.person ? personLink(t.expert, t.person.email) : esc(t.expert)) + '</span>';
      who = '<p class="v2d-who">' + parts + '</p>';
    }
    var amount = t.amount ? '<p class="v2d-amount">' + esc(t.amount) + '</p>' : '';
    // ب٤: شريط + طرفان + سطر واحد للعقل + زرّ واحد. «عند الخبراء» و«اعتُمد اليوم» شريط وطرفان فقط (الضغط على البطاقة يفتح الدرج).
    var slim = board === 'files' && (t.col === 'with' || t.col === 'done');
    var brain = slim ? '' : board === 'files'
      ? '<div class="v2d-brain">' + BRAIN + '<p>' + esc(t.brain) + '</p></div>'
      : '<p class="v2d-reason">' + esc(t.reason) + '</p>';
    var label = t.primary ? t.primary.label : 'افتح';
    var isOpen = !t.primary || !t.primary.act || t.primary.act.do === 'open' || t.primary.act.do === 'goto';
    var btn;
    if (done) btn = '<p class="v2d-ok" role="status">' + esc(done) + '</p>';
    else if (S.locked[id]) btn = '<button class="v2d-btn1" data-a="refresh" data-id="' + esc(id) + '">حدّث الآن</button>';
    else if (slim) btn = '';
    else btn = '<button class="v2d-btn1' + (isOpen ? '' : ' act') + '" data-a="primary" data-id="' + esc(id) + '"' + (busy ? ' disabled' : '') + '>' + esc(busy ? 'جارٍ التنفيذ…' : label) + '</button>';
    return '<article class="v2d-t tone-' + esc(t.strip.tone) + '" data-id="' + esc(id) + '">'
      + '<div class="v2d-strip"><span class="v2d-type">' + esc(t.strip.label) + '</span>'
      + (t.text ? '<time class="v2d-time tone-' + esc(t.tone) + '" data-tid="' + esc(id) + '">' + esc(t.text) + '</time>' : '') + '</div>'
      + '<div class="v2d-body"><h3><button class="v2d-open" data-a="open" data-id="' + esc(id) + '">' + esc(t.title) + '</button></h3>'
      + who + amount + brain
      + (err ? '<div class="v2d-err" role="alert">' + esc(err) + '</div>' : '')
      + (btn ? '<div class="v2d-acts">' + btn + '</div>' : '') + '</div></article>';
  }

  // ------------------------------------------------------------------ لوحة الملفات
  var FILE_COL_TONE = { late: 'late', review: 'wait', with: 'ok', done: 'done' };
  function drawFiles(v, g) {
    var pre = loadingOrError(g, 'الملفات');
    if (pre) { v.innerHTML = pre; wire(v, null); return; }
    var T = L.v2Tickets(fileRows(g.rows), { now: g.now, queue: g.Q, autoAssign: g.auto, brainToday: g.brainToday });
    S.tickets = T;
    var active = S.col.files;
    // اختيار الشخص يبقى حتى لو العمود فاضي (لازم يقدر يشوف «لا شيء هنا»)؛ الاختيار التلقائي لأول عمود فيه شيء قبل أن يختار.
    if (L.COLS.indexOf(active) < 0 || (!S.picked.files && !T.counts[active])) {
      active = L.COLS.filter(function (c) { return T.counts[c]; })[0] || 'late';
    }
    S.col.files = active;
    var seg = '', cols = '';
    L.COLS.forEach(function (c) {
      var n = T.counts[c];
      seg += '<button type="button" class="v2d-segb tone-' + FILE_COL_TONE[c] + (c === active ? ' on' : '') + '" role="tab" aria-selected="' + (c === active) + '" data-a="col" data-col="' + c + '"><span>' + esc(L.COL_LABEL[c]) + '</span><b>' + esc(U.ar(n)) + '</b></button>';
      var list = T.shown[c].map(function (t) { return ticketHtml(t, 'files'); }).join('');
      if (!list) list = '<p class="v2d-none">' + (c === 'done' ? 'لا رأي معتمد اليوم' : c === 'with' ? 'لا ملفات عند الخبراء الآن' : 'لا شيء هنا') + '</p>';
      var more = c === 'with' && T.withMore ? '<p class="v2d-more">و ' + esc(U.ar(T.withMore)) + ' في موعدها</p>' : '';
      var note = T.notes[c] ? '<p class="v2d-colnote">' + esc(T.notes[c]) + (c === 'with' ? '' : ' — العدد ناقص') + '</p>' : '';
      var hint = c === 'done' ? '<p class="v2d-colnote">يظهر هنا ما اعتمدته من آراء اليوم</p>' : '';
      cols += '<section class="v2d-col tone-' + FILE_COL_TONE[c] + '" data-col="' + c + '" aria-label="' + esc(L.COL_LABEL[c]) + '">'
        + '<header class="v2d-ch"><b>' + esc(L.COL_LABEL[c]) + '</b><span class="v2d-n">' + esc(U.ar(n)) + '</span></header>'
        + note + '<div class="v2d-list">' + list + '</div>' + more + hint + '</section>';
    });
    var head = '<div class="v2d-top">'
      + (T.header ? '<p class="v2d-auto' + (T.autoOn === false ? ' off' : '') + '">' + BRAIN + '<span>' + esc(T.header) + '</span></p>' : '')
      + (T.openTotal != null ? '<p class="v2d-open-total">الملفات المفتوحة على المنصة: <b>' + esc(U.ar(T.openTotal)) + '</b></p>' : '') + '</div>';
    v.innerHTML = '<div class="v2d" data-board="files">' + head + strips(g, FILE_LABELS)
      + '<div class="v2d-seg" role="tablist" aria-label="أعمدة الملفات">' + seg + '</div>'
      + '<div class="v2d-cols cols4" data-active="' + active + '">' + cols + '</div></div>';
    wire(v, 'files');
  }

  // ------------------------------------------------------------------ لوحة النزاعات
  var DCOLS = ['disputes', 'refunds', 'legacy'];
  var DLABEL = { disputes: 'نزاعات مفتوحة', refunds: 'استردادات تنتظرك', legacy: 'استشارات قديمة' };
  var DTONE = { disputes: 'late', refunds: 'wait', legacy: 'wait' };
  function manualCard(n) {
    if (n === null) return '<article class="v2d-t tone-wait"><div class="v2d-strip"><span class="v2d-type">استردادات يدوية</span></div><div class="v2d-body"><p class="v2d-reason">تعذّر جلب عدد الاستردادات اليدوية</p></div></article>';
    if (!n) return '';
    return '<article class="v2d-t tone-wait v2d-count"><div class="v2d-strip"><span class="v2d-type">استردادات يدوية</span></div><div class="v2d-body">'
      + '<h3 class="v2d-bignum"><b>' + esc(U.ar(n)) + '</b><span>' + esc(U.U(n, ['استرداد ينتظر التنفيذ بيدك', 'استردادان ينتظران التنفيذ بيدك', 'استردادات تنتظر التنفيذ بيدك', 'استردادًا ينتظر التنفيذ بيدك'])) + '</span></h3>'
      + '<p class="v2d-reason">أُلغي الحجز وأمواله لدينا، والرد يتم يدويًا من نفس وسيلة الدفع</p>'
      + '<div class="v2d-acts"><button class="v2d-btn1" data-a="manual">افتح</button></div></div></article>';
  }
  function drawDisputes(v, g) {
    var pre = loadingOrError(g, 'النزاعات');
    if (pre) { v.innerHTML = pre; wire(v, null); return; }
    var T = L.v2DisputeTickets(g.rows ? g.rows.filter(function (r) { return r && !r.fyi; }) : [], { now: g.now, queue: g.Q });
    S.dtickets = T;
    var active = S.col.disputes;
    if (DCOLS.indexOf(active) < 0 || (!S.picked.disputes && !T.counts[active])) active = DCOLS.filter(function (c) { return T.counts[c]; })[0] || 'disputes';
    S.col.disputes = active;
    var seg = '', cols = '';
    DCOLS.forEach(function (c) {
      var n = T.counts[c], list = T.cols[c].map(function (t) { return ticketHtml(t, 'disputes'); }).join('');
      if (c === 'refunds') list += manualCard(T.manualRefunds);
      if (!list) list = '<p class="v2d-none">' + (c === 'disputes' ? 'لا نزاعات مفتوحة' : c === 'refunds' ? 'لا استردادات تنتظرك' : 'لا استشارات قديمة') + '</p>';
      seg += '<button type="button" class="v2d-segb tone-' + DTONE[c] + (c === active ? ' on' : '') + '" role="tab" aria-selected="' + (c === active) + '" data-a="col" data-col="' + c + '"><span>' + esc(DLABEL[c]) + '</span><b>' + esc(U.ar(n)) + '</b></button>';
      cols += '<section class="v2d-col tone-' + DTONE[c] + '" data-col="' + c + '" aria-label="' + esc(DLABEL[c]) + '"><header class="v2d-ch"><b>'
        + esc(DLABEL[c]) + '</b><span class="v2d-n">' + esc(U.ar(n)) + '</span></header><div class="v2d-list">' + list + '</div></section>';
    });
    v.innerHTML = '<div class="v2d" data-board="disputes">' + strips(g, DISPUTE_LABELS)
      + '<div class="v2d-seg three" role="tablist" aria-label="أعمدة النزاعات">' + seg + '</div>'
      + '<div class="v2d-cols cols3" data-active="' + active + '">' + cols + '</div></div>';
    wire(v, 'disputes');
  }

  // ------------------------------------------------------------------ أحداث اللوحات
  function ticketById(board, id) {
    var T = board === 'files' ? S.tickets : S.dtickets, found = null;
    if (!T) return null;
    Object.keys(T.cols).forEach(function (c) { T.cols[c].forEach(function (t) { if (t.id === id) found = t; }); });
    return found;
  }
  function openTicket(board, t) {
    if (!t || !t.row) return;
    var sec = board === 'files' ? 'files' : 'disputes';
    if (host().openRowAt) host().openRowAt(sec, 'all', t.row);
  }
  function refreshAll(cb) {
    var E = ep(), keys = ['opsQueue', 'inbox', 'walletPayouts'], fin = false;
    if (!E || !E.authed) { if (cb) cb(); return; }
    var finish = function () { if (!fin) { fin = true; if (cb) cb(); } };
    setTimeout(finish, 20000);
    keys.forEach(function (k) { E.reload(k, function () { if (keys.every(function (x) { return stateOf(x) !== 'loading'; })) finish(); }); });
  }
  function sendTicket(board, t) {
    var E = ep(), a = t.primary.act, id = t.id;
    if (!E || S.busy[id]) return;
    S.busy[id] = true; S.err[id] = ''; redraw();
    Promise.resolve(E.expertFileSend(t.row, a.email, a.name, '', null)).then(function (res) {
      res = res || {};
      S.busy[id] = false;
      if (res.ok) { S.done[id] = 'أُرسل «' + t.title + '» إلى ' + a.name; refreshAll(function () { delete S.done[id]; redraw(); }); }
      else {
        S.err[id] = window.V2 && V2.plainError ? V2.plainError(res) : ((res && res.error) || 'تعذّر تنفيذ العملية');
        if (res.noReply || res.final) { S.locked[id] = true; refreshAll(null); }
      }
      redraw();
    }).catch(function (e) { S.busy[id] = false; S.err[id] = (e && e.message) || 'تعذّر تنفيذ العملية'; redraw(); });
  }
  function wire(v, board) {
    var re = v.querySelector('[data-a="reload"]');
    if (re) re.onclick = function () { var E = ep(); if (E) { E.reload('inbox'); E.reload('opsQueue'); } };
    if (!board) return;
    v.querySelectorAll('[data-a="col"]').forEach(function (b) {
      b.onclick = function () { S.col[board] = b.getAttribute('data-col'); S.picked[board] = true; redraw(); };
    });
    v.querySelectorAll('.v2d-t').forEach(function (art) {
      var id = art.getAttribute('data-id');
      art.onclick = function (e) {
        if (e.target.closest && e.target.closest('button,a')) return;
        openTicket(board, ticketById(board, id));
      };
    });
    v.querySelectorAll('[data-a="open"]').forEach(function (b) { b.onclick = function (e) { e.stopPropagation(); openTicket(board, ticketById(board, b.getAttribute('data-id'))); }; });
    v.querySelectorAll('[data-a="primary"]').forEach(function (b) {
      b.onclick = function (e) {
        e.stopPropagation();
        var t = ticketById(board, b.getAttribute('data-id'));
        if (!t) return;
        var a = t.primary && t.primary.act;
        if (a && a.do === 'send') sendTicket(board, t); else openTicket(board, t);
      };
    });
    v.querySelectorAll('[data-a="refresh"]').forEach(function (b) {
      b.onclick = function (e) { e.stopPropagation(); var id = b.getAttribute('data-id'); b.disabled = true; refreshAll(function () { delete S.locked[id]; S.err[id] = ''; redraw(); }); };
    });
    var m = v.querySelector('[data-a="manual"]');
    if (m) m.onclick = function () { if (host().openSection) host().openSection('disputes', 'escrow'); };
  }

  // ------------------------------------------------------------------ العدّاد (كل دقيقة)
  function tickDisputes(now) {
    var g = gather();
    if (!g.rows) return;
    var T = L.v2DisputeTickets(g.rows.filter(function (r) { return r && !r.fyi; }), { now: now || g.now, queue: g.Q });
    S.dtickets = T;
    Object.keys(T.cols).forEach(function (c) {
      T.cols[c].forEach(function (t) {
        var el = S.view.querySelector('.v2d-time[data-tid="' + (window.CSS && CSS.escape ? CSS.escape(t.id) : t.id) + '"]');
        if (el) el.textContent = t.text;
      });
    });
  }
  function tick(now) {
    if (!S.view) return;
    if (isCurrent('v2disputes')) { S.nowOverride = now || 0; tickDisputes(now); return; }
    if (!isCurrent('v2files')) return;
    S.nowOverride = now || 0;        // للاختبار فقط: ساعة مفروضة
    var g = gather();
    if (!g.rows) return;
    var T = L.v2Tickets(fileRows(g.rows), { now: now || g.now, queue: g.Q, autoAssign: g.auto, brainToday: g.brainToday });
    var place = function (X) { return L.COLS.map(function (c) { return X.shown[c].map(function (t) { return t.id; }).join(','); }).join('|'); };
    if (!S.tickets || place(T) !== place(S.tickets)) { redraw(); return; }   // لو تذكرة غيّرت عمودها (فات موعدها) نعيد الرسم
    S.tickets = T;
    L.COLS.forEach(function (c) {
      T.cols[c].forEach(function (t) {
        var el = S.view.querySelector('.v2d-time[data-tid="' + (window.CSS && CSS.escape ? CSS.escape(t.id) : t.id) + '"]');
        if (el) { el.textContent = t.text; el.className = 'v2d-time tone-' + t.tone; }
      });
    });
  }
  D2._tick = tick;

  // ------------------------------------------------------------------ صفحة الشخص
  var HEAD_ICON = '<svg viewBox="0 0 24 24" class="v2-ic" aria-hidden="true"><path d="M9 6l6 6-6 6"/></svg>';
  function personCard(c) {
    var body;
    if (c.na) body = '<p class="v2d-na">' + esc(c.text) + '</p>';
    else if (c.rows) body = '<dl class="v2d-rows">' + c.rows.map(function (r) { return '<div><dt>' + esc(r.k) + '</dt><dd' + (r.na ? ' class="v2d-na"' : '') + '>' + esc(r.v) + '</dd></div>'; }).join('') + '</dl>';
    else {
      body = '<p class="v2d-sum">' + esc(c.summary || '') + '</p>';
      if (c.items && c.items.length) body += '<ul class="v2d-items">' + c.items.map(function (i) { return '<li><b>' + esc(i.title) + '</b>' + (i.meta ? '<span>' + esc(i.meta) + '</span>' : '') + '</li>'; }).join('') + '</ul>';
      if (c.note) body += '<p class="v2d-fine">' + esc(c.note) + '</p>';
    }
    return '<section class="v2d-pc"><h3>' + esc(c.title) + '</h3>' + body + '</section>';
  }
  function drawPerson(v) {
    var P = S.person, email = P.email;
    var back = '<a class="v2d-back" href="' + esc(L.sectionHash('people', 'users')) + '" data-a="back">' + HEAD_ICON + 'المستخدمون</a>';
    if (!email) { v.innerHTML = '<div class="v2d" data-board="person">' + back + '<div class="v2d-empty big"><b>اختر شخصًا من البحث أو من قائمة المستخدمين</b></div></div>'; wire(v, null); wirePerson(v); return; }
    if (P.state === 'loading' || P.state === 'idle') {
      v.innerHTML = '<div class="v2d" data-board="person">' + back + '<div class="v2d-ph"><span class="v2d-av sk"></span><div class="v2d-sk"><i></i><i></i></div></div><div class="v2d-pgrid sk">'
        + '<i></i><i></i><i></i><i></i></div><p class="v2d-mute center">…جارٍ جلب بيانات هذا الشخص</p></div>';
      wirePerson(v); return;
    }
    var vm = L.v2Person(P.resp, Date.now(), email);
    if (vm.state === 'failed' || vm.state === 'notfound') {
      var notfound = vm.state === 'notfound';
      v.innerHTML = '<div class="v2d" data-board="person">' + back + '<div class="v2d-ph"><span class="v2d-av">' + esc((email || '?').charAt(0).toUpperCase()) + '</span><div><h1 class="v2d-name">' + esc(email) + '</h1>'
        + '<p class="v2d-join">' + (notfound ? 'لا يوجد حساب بهذا البريد على المنصة' : 'تعذّر جلب بيانات هذا الشخص') + '</p></div></div>'
        + (notfound ? '' : '<div class="v2d-pgrid">' + ['الملفات', 'الدورات', 'الفلوس', 'التعلّم'].map(function (t) { return '<section class="v2d-pc"><h3>' + t + '</h3><p class="v2d-na">' + esc(L.NA) + '</p></section>'; }).join('') + '</div>'
          + '<p class="v2d-warn" role="status">لا نعرف الآن شيئًا عن هذا الشخص — لا تعتبر خلو الصفحة دليلًا على خلو سجل هذا الحساب. <button class="v2d-btn2" data-a="retry">أعد المحاولة</button></p>')
        + '</div>';
      wirePerson(v); return;
    }
    var chips = vm.chips.map(function (c) { return '<span class="v2d-chip chip-' + esc(c.key) + '">' + esc(c.label) + '</span>'; }).join('');
    var av = vm.photo ? '<img class="v2d-av" src="' + esc(vm.photo) + '" alt="">' : '<span class="v2d-av">' + esc(vm.initial) + '</span>';
    var meta = [];
    if (vm.lastLogin) meta.push('آخر دخول ' + vm.lastLogin);
    meta.push('البلد: ' + vm.countryText);
    var mail = 'mailto:' + encodeURIComponent(email).replace(/%40/g, '@');
    var warn = vm.failed.length ? '<p class="v2d-warn" role="status">تعذّر جلب بعض البيانات فتظهر «' + esc(L.NA) + '» في أماكنها — لا تعتبرها فارغة. <button class="v2d-btn2" data-a="retry">أعد المحاولة</button></p>' : '';
    var log;
    if (vm.log === null) log = '<p class="v2d-na">' + esc(L.NA) + '</p>';
    else if (!vm.log.length) log = '<p class="v2d-sum">لا أحداث بعد</p>';
    else log = '<ul class="v2d-log">' + vm.log.map(function (e) { return '<li><time>' + esc(e.when) + '</time><span>' + esc(e.text) + '</span><small>' + esc(e.ago) + '</small></li>'; }).join('') + '</ul>';
    v.innerHTML = '<div class="v2d" data-board="person">' + back + warn
      + '<header class="v2d-ph">' + av + '<div class="v2d-pid"><h1 class="v2d-name">' + esc(vm.name) + '</h1><div class="v2d-chips">' + chips + (vm.active ? '' : '<span class="v2d-chip chip-off">الحساب موقوف</span>') + '</div>'
      + '<p class="v2d-join">' + esc(vm.joinLine) + '</p>' + (meta.length ? '<p class="v2d-meta">' + esc(meta.join(' · ')) + '</p>' : '') + '</div>'
      + '<div class="v2d-pact"><a class="v2d-btn1" href="' + esc(mail) + '" data-a="mail">مراسلة</a></div></header>'
      + '<div class="v2d-pgrid">' + vm.cards.map(personCard).join('') + '</div>'
      + '<section class="v2d-plog"><h3>السجل' + (vm.logPartial ? ' <small>(جزء منه — تعذّر جلب بعض المصادر)</small>' : '') + '</h3>' + log + '</section></div>';
    wirePerson(v);
  }
  function wirePerson(v) {
    var r = v.querySelectorAll('[data-a="retry"]');
    r.forEach(function (b) { b.onclick = function () { loadPerson(S.person.email, true); }; });
    v.querySelectorAll('[data-a="back"]').forEach(function (a) {
      a.onclick = function (e) { if (e.metaKey || e.ctrlKey || e.shiftKey || e.button === 1) return; e.preventDefault(); if (host().openSection) host().openSection('people', 'users'); };
    });
  }
  function loadPerson(email, force) {
    var P = S.person;
    if (!email) return;
    if (!force && P.email === email && (P.state === 'loading' || (P.state === 'ready' && Date.now() - (P.at || 0) < 60000))) return;
    var E = ep();
    P.email = email; P.state = 'loading'; P.resp = null;
    var seq = ++P.seq;
    if (!E || !E.api) { P.state = 'error'; return; }
    E.api('/v2/person?email=' + encodeURIComponent(email)).then(function (r) {
      if (seq !== P.seq) return;
      P.resp = r; P.state = 'ready'; P.at = Date.now(); if (isCurrent('v2person')) drawPerson(S.view);
    }).catch(function () {
      if (seq !== P.seq) return;
      P.resp = null; P.state = 'ready'; P.at = Date.now(); if (isCurrent('v2person')) drawPerson(S.view);
    });
    return seq;
  }
  D2.openPerson = function (email) { if (host().openPerson) host().openPerson(email); };

  // ------------------------------------------------------------------ بحث الناس
  var SEARCH = { timer: null, seq: 0, items: [], open: false, q: '' };
  var ROLE_AR = { admin: 'إدارة', staff: 'فريق العمل', investor: 'مستثمر', member: 'عضو', trainer: 'مدرّب' };
  function searchHtml() {
    return '<div class="v2d-search" role="search"><label for="v2dq">ابحث عن شخص</label>'
      + '<div class="v2d-sbox"><input id="v2dq" type="search" autocomplete="off" placeholder="الاسم أو البريد أو رقم الهاتف" aria-controls="v2dres" aria-expanded="false" dir="auto">'
      + '<button type="button" class="v2d-sgo" data-a="sgo" aria-label="ابحث">ابحث</button></div>'
      + '<ul id="v2dres" class="v2d-res" role="listbox" hidden></ul></div>';
  }
  function localMatches(q) {
    var list = window.USERS || [];
    q = q.toLowerCase();
    return list.filter(function (u) { return u && ((u.name || '').toLowerCase().indexOf(q) > -1 || (u.email || '').toLowerCase().indexOf(q) > -1 || String(u.phone || '').indexOf(q) > -1); })
      .slice(0, 8).map(function (u) { return { name: u.name, email: u.email, role: u.trainer === 'approved' ? 'trainer' : u.role }; });
  }
  function drawResults(root, msg) {
    var ul = root.querySelector('#v2dres'), input = root.querySelector('#v2dq');
    if (!ul) return;
    var items = SEARCH.items;
    if (!SEARCH.open) { ul.hidden = true; input.setAttribute('aria-expanded', 'false'); return; }
    ul.hidden = false; input.setAttribute('aria-expanded', 'true');
    if (msg) { ul.innerHTML = '<li class="v2d-rmsg">' + esc(msg) + '</li>'; return; }
    ul.innerHTML = items.map(function (u, i) {
      return '<li role="option" id="v2dr' + i + '"><a href="' + esc(L.sectionHash('people', 'person', u.email)) + '" data-person="' + esc(u.email) + '"><b>' + esc(u.name || u.email) + '</b><span>' + esc(u.email) + '</span>'
        + (ROLE_AR[u.role] ? '<em>' + esc(ROLE_AR[u.role]) + '</em>' : '') + '</a></li>';
    }).join('');
  }
  function runSearch(root, q) {
    q = (q || '').trim();
    SEARCH.q = q;
    if (q.length < 2) { SEARCH.open = false; SEARCH.items = []; drawResults(root); return; }
    var E = ep(), seq = ++SEARCH.seq;
    SEARCH.open = true; SEARCH.items = localMatches(q);
    drawResults(root, SEARCH.items.length ? '' : '…جارٍ البحث');
    if (!E || !E.api) return;
    E.api('/platform-users?search=' + encodeURIComponent(q.slice(0, 80))).then(function (r) {
      if (seq !== SEARCH.seq) return;
      var list = (r && Array.isArray(r.users)) ? r.users : [];
      SEARCH.items = list.slice(0, 8).map(function (u) { return { name: u.full_name || u.name || u.email, email: u.email || '', role: u.trainer_status === 'approved' ? 'trainer' : u.role }; }).filter(function (u) { return u.email; });
      drawResults(root, SEARCH.items.length ? '' : 'لا نتائج مطابقة');
    }).catch(function () {
      if (seq !== SEARCH.seq) return;
      drawResults(root, SEARCH.items.length ? '' : 'تعذّر البحث الآن — جرّب كتابة البريد كاملًا');
    });
  }
  D2.mountSearch = function (el) {
    if (!el || el.getAttribute('data-mounted')) return;
    el.setAttribute('data-mounted', '1');
    el.innerHTML = searchHtml();
    var input = el.querySelector('#v2dq');
    input.addEventListener('input', function () {
      clearTimeout(SEARCH.timer);
      SEARCH.timer = setTimeout(function () { runSearch(el, input.value); }, 220);
    });
    input.addEventListener('keydown', function (e) {
      if (e.key === 'Escape') { SEARCH.open = false; drawResults(el); }
      else if (e.key === 'Enter') {
        e.preventDefault();
        var q = input.value.trim().toLowerCase(), em = L.personEmailOf(q);
        if (em) { SEARCH.open = false; drawResults(el); D2.openPerson(em); return; }
        var first = el.querySelector('#v2dres a'); if (first) first.click(); else runSearch(el, input.value);
      }
    });
    el.querySelector('[data-a="sgo"]').onclick = function () { var q = input.value.trim().toLowerCase(), em = L.personEmailOf(q); if (em) D2.openPerson(em); else runSearch(el, input.value); };
    document.addEventListener('click', function (e) {
      if (SEARCH.open && !el.contains(e.target)) { SEARCH.open = false; drawResults(el); }
    });
  };

  // أي اسم عليه `data-person` يفتح صفحة صاحبه (قبل أي معالج آخر للصف الذي يحويه).
  document.addEventListener('click', function (e) {
    var a = e.target && e.target.closest ? e.target.closest('[data-person]') : null;
    if (!a || !window.V2_ON) return;
    if (e.metaKey || e.ctrlKey || e.shiftKey || e.button === 1) return;
    var em = a.getAttribute('data-person');
    if (!em) return;
    e.preventDefault(); e.stopPropagation();
    SEARCH.open = false;
    var box = document.getElementById('v2sbar'); if (box) drawResults(box);
    D2.openPerson(em);
  }, true);

  // ------------------------------------------------------------------ نقطة الدخول
  // ⛔ ردّ متأخر ما يرسمش فوق شاشة تانية: الشاشة الحالية تُسأل من الغلاف مش من آخر رسم.
  function isCurrent(mod) { return !!(host().current && host().current() === mod && S.view && document.body.contains(S.view)); }
  function redraw() {
    if (!S.view || !host().current || !D2.owns(host().current())) return;
    S.mod = host().current();
    if (S.mod === 'v2files') drawFiles(S.view, gather());
    else if (S.mod === 'v2disputes') drawDisputes(S.view, gather());
    else if (S.mod === 'v2person') drawPerson(S.view);
    S.sig = signature();
  }
  D2.render = function (mod, view) {
    S.view = view; S.mod = mod;
    if (mod === 'v2person') {
      var st = host().state ? host().state() : null;
      loadPerson(st && st.person ? st.person : '', false);
      drawPerson(view);
    } else {
      loadAll();
      redraw();
    }
    if (!S.poll) {
      // المحمّلات الأولى بتبدأ برّه (bootNavCounts) ⇒ نلاحظ تغيّر الحالة بفحص خفيف ونعيد الرسم في اللوحات بس.
      S.poll = setInterval(function () {
        if (!(host().current && D2.owns(host().current()))) { S.mod = ''; return; }
        S.mod = host().current();
        if (S.mod === 'v2person') return;
        if (document.getElementById('epModal')) return;
        if (signature() !== S.sig && !hasActiveWork()) redraw();
      }, 400);
    }
    if (!S.minute) S.minute = setInterval(function () { if (host().current && D2.owns(host().current())) { S.mod = host().current(); tick(); } }, 60000);
  };
  function hasActiveWork() { return Object.keys(S.busy).some(function (k) { return S.busy[k]; }); }
  D2._state = S;
})();
