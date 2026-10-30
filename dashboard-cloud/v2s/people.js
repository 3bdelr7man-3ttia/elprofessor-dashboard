/* ============================================================================
 * v2s/people.js — «الناس والدعوات» بالشكل النهائي: الطلبات (من ينتظر الدخول) · الدعوات (خط الرحلة) · المستخدمون (قائمة بحث) · الرسائل (تذاكر).
 * ⛔ لا منطق عمل هنا: التصنيف والأعداد وسطور العقل والنصوص من `V2L.v2p` (نقي في v2-logic.js)، والكتابة كلها بنفس مسارات الداشبورد القديمة
 *   (`PX.call` أو `EP.decideInboxItem` أو `EP.resolveInboxItem`). ⛔ لا `prompt` ولا `confirm` ولا `alert`: كل كتابة لها ورقة تأكيدها.
 * ⛔ المفتاح مقفول افتراضيًا: الملف بيتحمّل دايمًا لكنه ما بيرسم شيئًا إلا لو index.html نادى `V2SECT.people.render` (وده ما بيحصل إلا والغلاف
 *   الجديد شغّال للأدمن، لأن `owns` بترجع false من غيره فتظهر الشاشات القديمة كما هي).
 * ⛔ الرقم المجهول «غير متاح بعد» لا صفر. ⛔ لا فلوس في هذا القسم.
 * ========================================================================== */
(function () {
  'use strict';
  var L = window.V2L;
  if (!L || !L.v2p) return;
  var P = L.v2p, U = L.util, NA = L.NA;
  var PX = {};
  var KEYS = { requests: ['inbox', 'invites', 'waitlist', 'pendingUsers', 'inviteSettings', 'users'], pipeline: ['invites', 'inviteSettings'],
               users: ['users', 'dashboard', 'pendingUsers', 'packages'], messages: ['messages', 'inbox'] };
  var SESSION_AR = 'انتهت الجلسة — سجّل الدخول من جديد ثم جرّب';
  var NO_REPLY_AR = 'ما وصلنا رد — حدّث الصفحة وانظر ما حدث قبل أن تضغط مرة أخرى';
  var FAIL_AR = 'تعذّر تنفيذ العملية';
  var S = {
    view: null, mod: '', tab: '', sig: '', poll: null, minute: null, seen: {}, items: {},
    busy: {}, err: {}, done: {}, sent: {}, expanded: {}, laterOpen: false,
    col: { requests: '', pipeline: '', messages: '' }, picked: { requests: false, pipeline: false, messages: false },
    inviter: 'all', own: { chat: { state: 'idle', rows: null, seq: 0 }, follow: { state: 'idle', rows: null, seq: 0 } },
    users: { q: '', chip: 'all', filter: { role: null, seg: null }, sort: 'new', limit: 50, extra: [], searching: false, searchFailed: false, seq: 0, timer: null },
    sheet: null, sheetWas: false, reqEmail: {}
  };

  function esc(s) { return String(s == null ? '' : s).replace(/[&<>"']/g, function (c) { return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]; }); }
  function host() { return window.V2_HOST || {}; }
  function ep() { return window.EP || null; }
  function img(name) { return 'v2/img/' + name + '.jpg'; }
  function now() { return S.nowOverride || Date.now(); }
  function ar(n) { return U.ar(n); }
  function q(sel, root) { return (root || document).querySelector(sel); }
  function qa(sel, root) { return Array.prototype.slice.call((root || document).querySelectorAll(sel)); }
  function safeHttps(u) { u = String(u || '').trim(); return /^https?:\/\//i.test(u) ? u : ''; }
  function digits(p) { return String(p == null ? '' : p).replace(/\D/g, ''); }
  function personHref(email) { return L.sectionHash('people', 'person', email); }
  var BRAIN = '<img class="v2p-bav" src="' + img('brain-avatar') + '" alt="">';
  var GEAR = '<svg viewBox="0 0 24 24" class="v2p-ic" aria-hidden="true"><circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.7 1.7 0 0 0 .3 1.8l.1.1a2 2 0 1 1-2.8 2.8l-.1-.1a1.7 1.7 0 0 0-1.8-.3 1.7 1.7 0 0 0-1 1.5V21a2 2 0 1 1-4 0v-.1a1.7 1.7 0 0 0-1.1-1.5 1.7 1.7 0 0 0-1.8.3l-.1.1a2 2 0 1 1-2.8-2.8l.1-.1a1.7 1.7 0 0 0 .3-1.8 1.7 1.7 0 0 0-1.5-1H3a2 2 0 1 1 0-4h.1a1.7 1.7 0 0 0 1.5-1.1 1.7 1.7 0 0 0-.3-1.8l-.1-.1a2 2 0 1 1 2.8-2.8l.1.1a1.7 1.7 0 0 0 1.8.3H9a1.7 1.7 0 0 0 1-1.5V3a2 2 0 1 1 4 0v.1a1.7 1.7 0 0 0 1 1.5 1.7 1.7 0 0 0 1.8-.3l.1-.1a2 2 0 1 1 2.8 2.8l-.1.1a1.7 1.7 0 0 0-.3 1.8V9a1.7 1.7 0 0 0 1.5 1H21a2 2 0 1 1 0 4h-.1a1.7 1.7 0 0 0-1.5 1z"/></svg>';

  function owns(mod) {
    if (!(window.V2SHELL && window.V2SHELL.on)) return false;
    if (mod === 'invites' || mod === 'users' || mod === 'v2p_invites') return true;
    if (mod === 'inbox') { var st = host().state ? host().state() : null; return !!(st && st.section === 'people' && st.tab === 'messages'); }
    return false;
  }
  function tabOfMod(mod) { return mod === 'invites' ? 'requests' : mod === 'v2p_invites' ? 'pipeline' : mod === 'users' ? 'users' : 'messages'; }

  // ------------------------------------------------------------------ مصادر الداشبورد (قراءة فقط)
  function stateOf(k) { var E = ep(); return (E && E.state && E.state[k]) || 'idle'; }
  // أثناء إعادة التحميل بعد قرار: نبقي ما عندنا بدل وميض «جارٍ الجلب».
  function eff(k) { var s = stateOf(k); if (s === 'ready') S.seen[k] = true; return (s === 'loading' && S.seen[k]) ? 'ready' : s; }
  function dataOf(k) { var E = ep(); return E && E.data ? E.data[k] : null; }
  var serial = typeof WeakMap !== 'undefined' ? new WeakMap() : null, nextSerial = 1;
  function ser(o) { if (!o || typeof o !== 'object') return '0'; if (!serial) return String(o.length || 0); var v = serial.get(o); if (!v) { v = nextSerial++; serial.set(o, v); } return String(v); }
  function ensureKeys(tab) {
    var E = ep(); if (!E || !E.authed) return;
    KEYS[tab].forEach(function (k) { E.ensure(k, null); });
    if (tab === 'messages') loadOwn(false);
  }
  function reloadKeys(keys) { var E = ep(); if (E && E.authed) keys.forEach(function (k) { E.reload(k, null); }); }
  function readyData(k) { return eff(k) === 'ready' ? dataOf(k) : null; }

  function loadOwn(force) {
    var E = ep(); if (!E || !E.api || !E.authed) return;
    [['chat', '/platform-messages?status=new'], ['follow', '/platform-leads?status=new']].forEach(function (d) {
      var o = S.own[d[0]];
      if (o.state === 'loading' || (!force && o.state !== 'idle')) return;
      if (o.state !== 'ready') o.state = 'loading';
      var seq = ++o.seq;
      PX.read(d[1]).then(function (r) {
        if (seq !== o.seq) return;
        var list = (r && (r.messages || r.leads || r.items)) || (Array.isArray(r) ? r : []);
        o.rows = Array.isArray(list) ? list : []; o.state = 'ready'; changedSoon();
      }).catch(function () { if (seq !== o.seq) return; o.state = 'error'; o.rows = null; changedSoon(); });
    });
  }
  PX.read = function (path) { var E = ep(); return E && E.api ? E.api(path) : Promise.reject(new Error('x')); };
  function plain(e) {
    var st = e && e.status, d = (e && e.data) || {};
    var msg = typeof d.error === 'string' && d.error ? d.error : (typeof d.detail === 'string' ? d.detail : '');
    if (st === 401) return SESSION_AR;
    if (st === 403) return 'هذا الإجراء للإدارة فقط';
    if (st === 404) return 'غير متاح بعد من المنصة';
    if (!st) return NO_REPLY_AR;
    if (msg && /[؀-ۿ]/.test(msg)) return msg;
    return FAIL_AR;
  }
  // ⛔ الكتابة الوحيدة: نفس مسارات الداشبورد القديمة بنفس الجسم، ثم إعادة تحميل المفاتيح. تعيد {ok, error, data}.
  PX.call = function (spec) {
    var E = ep();
    if (!E || !E.api) return Promise.resolve({ ok: false, error: FAIL_AR });
    var opts = { method: spec.method || 'POST' };
    if (spec.body !== undefined) opts.body = spec.body;
    return E.api(spec.path, opts).then(function (r) {
      reloadKeys(spec.reload || []);
      return { ok: true, data: r || {} };
    }).catch(function (e) { return { ok: false, error: plain(e), status: e && e.status }; });
  };
  function resErr(res) { return window.V2 && V2.plainError ? V2.plainError(res) : ((res && res.error) || FAIL_AR); }

  // ------------------------------------------------------------------ مدخلات الدوال النقية
  function reqInputs() {
    var D = (dataOf('users') && dataOf('users').raw) ? dataOf('users').raw : null;
    return {
      inbox: eff('inbox') === 'ready' ? (window.INBOX || []) : null, inboxState: eff('inbox'), failed: (window.INBOX_FAILED || []).slice(), trunc: (window.INBOX_TRUNCATED || []).slice(),
      invites: readyData('invites'), invitesState: eff('invites'), waitlist: readyData('waitlist'), waitlistState: eff('waitlist'),
      pending: readyData('pendingUsers'), pendingState: eff('pendingUsers'), settings: readyData('inviteSettings'),
      userEmails: (D && eff('users') === 'ready') ? D.map(function (u) { return String(u.email || '').toLowerCase(); }) : null
    };
  }
  function usersInputs() {
    var E = ep(), U0 = S.users;
    var m = E && E.data && E.data.metrics && E.data.metrics.raw && E.data.metrics.raw.customers ? E.data.metrics.raw.customers : null;
    var pk = E && E.data && E.data.packages ? E.data.packages.packages : null;
    return { usersState: eff('users'), metrics: eff('dashboard') === 'ready' ? m : null, pending: readyData('pendingUsers'), packages: Array.isArray(pk) ? pk : null,
             q: U0.q, chip: U0.chip, filter: U0.filter, sort: U0.sort, limit: U0.limit, now: now(), searchExtra: U0.extra, searching: U0.searching, searchFailed: U0.searchFailed };
  }
  function usersRaw() { var u = dataOf('users'); return (eff('users') === 'ready' && u && Array.isArray(u.raw)) ? u.raw : null; }
  function messagesVM() {
    var site = eff('messages') === 'ready' ? dataOf('messages') : null;
    return P.messages(Array.isArray(site) ? site : null, eff('messages'), S.own.chat.rows, S.own.chat.state, S.own.follow.rows, S.own.follow.state, now());
  }

  // ------------------------------------------------------------------ قطع مشتركة
  function personLink(name, email) {
    if (!email) return esc(name);
    return '<a class="v2p-person" href="' + esc(personHref(email)) + '" data-person="' + esc(email) + '">' + esc(name) + '</a>';
  }
  function emptyCard(title, extra) {
    return '<div class="v2p-empty"><img src="' + img('people') + '" alt=""><b>' + esc(title) + '</b>' + (extra || '') + '</div>';
  }
  function warnStrips(failed, partial) {
    var out = '';
    if (failed && failed.length) out += '<div class="v2p-warn" role="status">تعذّر جلب: ' + esc(failed.join(' · ')) + ' — القائمة ناقصة وليس معناه أنه لا شيء ينتظرك</div>';
    (partial || []).forEach(function (t) { out += '<div class="v2p-warn" role="status">' + esc(t) + '</div>'; });
    return out;
  }
  function segHtml(cols, order, active, cls) {
    return '<div class="v2d-seg ' + (cls || '') + '" role="tablist">' + order.map(function (k) {
      var c = cols[k];
      return '<button type="button" class="v2d-segb tone-' + esc(c.tone || 'wait') + (k === active ? ' on' : '') + '" role="tab" aria-selected="' + (k === active) + '" data-a="col" data-col="' + k + '"><span>' + esc(c.short) + '</span><b>' + esc(c.countText != null ? c.countText : (c.count == null ? '—' : ar(c.count))) + '</b></button>';
    }).join('') + '</div>';
  }
  function skeleton() { return '<div class="v2p-sk"><i></i><i></i></div>'; }
  function waHrefFor(t, kind) {
    var r = t.ref || {};
    var phone = r.phone || '';
    return P.waUrl(phone, P.waText(kind, t.name || t.title, t.inviteUrl));
  }

  // ------------------------------------------------------------------ زرّ التذكرة
  function actBtn(t, a, cls, w) {
    var act = a.act || {}, id = t.id;
    var label = esc(a.label);
    if (a.disabled || act.do === 'none') return '<button type="button" class="' + cls + '" disabled>' + label + '</button>';
    if (act.do === 'wa') return '<a class="' + cls + '" href="' + esc(waHrefFor(t, act.kind)) + '" target="_blank" rel="noopener" data-a="wa" data-id="' + esc(id) + '" data-w="' + w + '">' + label + '</a>';
    if (act.do === 'link') { var u = safeHttps(act.url); return u ? '<a class="' + cls + '" href="' + esc(u) + '" target="_blank" rel="noopener" data-a="link" data-w="' + w + '">' + label + '</a>' : ''; }
    if (act.do === 'sent') {
      var href = act.url || '';
      var ok = /^(mailto:|https:\/\/wa\.me\/)/.test(href);
      return ok ? '<a class="' + cls + '" href="' + esc(href) + '"' + (href.indexOf('http') === 0 ? ' target="_blank" rel="noopener"' : '') + ' data-a="sent" data-id="' + esc(id) + '" data-w="' + w + '">' + label + '</a>' : '';
    }
    var busy = !!S.busy[id];
    return '<button type="button" class="' + cls + '" data-a="act" data-id="' + esc(id) + '" data-w="' + w + '"' + (busy ? ' disabled' : '') + '>' + (busy && w === 'p' ? 'جارٍ التنفيذ…' : label) + '</button>';
  }
  function ticketHtml(t, tone) {
    var id = t.id; S.items[id] = t;
    var err = S.err[id] || '', done = S.done[id] || '';
    var who = t.kind ? t.link : t.person;
    var title = who ? personLink(t.title, who) : esc(t.title);
    var h = '<article class="v2p-t tone-' + esc(tone) + '" data-id="' + esc(id) + '" data-a="detail">'
      + '<div class="v2p-strip"><span class="v2p-type">' + esc(t.tag || t.strip || '') + '</span>' + (t.age || t.ageText ? '<time class="v2p-time">' + esc(t.age || t.ageText) + '</time>' : '') + '</div>'
      + '<div class="v2p-body"><h3>' + title + '</h3>';
    if (t.sub) h += '<p class="v2p-subl">' + esc(t.sub) + '</p>';
    if (t.expiry) h += '<p class="v2p-subl' + (t.expiry === 'انتهت مهلتها' ? ' late' : '') + '">' + esc(t.expiry) + '</p>';
    if (t.docRequested) h += '<span class="v2p-chip2">طلب توثيق من خبير</span>';
    if (t.brain) h += '<div class="v2p-bline">' + BRAIN + '<p>' + esc(t.brain) + '</p></div>';
    if (t.reason) h += '<p class="v2p-reason">' + esc(t.reason) + '</p>';
    if (t.warn) h += '<p class="v2p-tw">' + esc(t.warn) + '</p>';
    (t.extra || []).forEach(function (x) { h += '<p class="v2p-reason">' + esc(x) + '</p>'; });
    if (t.teamNote) h += '<p class="v2p-reason">' + esc(t.teamNote) + '</p>';
    if (err) h += '<div class="v2p-err" role="alert">' + esc(err) + '</div>';
    if (done) h += '<p class="v2p-ok" role="status">' + esc(done) + '</p>';
    else if (t.primary) {
      h += '<div class="v2p-acts">' + actBtn(t, t.primary, 'v2p-btn1', 'p');
      var sec = (t.secondary || []).map(function (a, i) { return actBtn(t, a, 'v2p-btn2', 's' + i); }).join('');
      if (sec) h += '<div class="v2p-sacts">' + sec + '</div>';
      h += '</div>';
    }
    return h + '</div></article>';
  }

  // ------------------------------------------------------------------ لوحة الطلبات
  var TONE_CLS = { amber: 'wait', ink: 'ink', green: 'ok' };
  function colHtml(key, c, tabKey, ticketTone, emptyText, opts) {
    opts = opts || {};
    var body = '';
    if (c.state === 'loading') body = skeleton() + skeleton() + '<p class="v2p-none">…جارٍ الجلب</p>';
    else if (c.state === 'failed') {
      var labs = (c.retry && c.retry.length ? c.retry.map(function (r) { return r.label; }) : [c.label]).join(' و');
      body = '<p class="v2p-none">تعذّر جلب ' + esc(labs) + ' — لا تعتبر العمود فارغًا.</p>'
        + (c.retry && c.retry.length ? c.retry.map(function (r) { return '<button type="button" class="v2p-btn2" data-a="retry" data-key="' + esc(r.key) + '">أعد المحاولة</button>'; }).join('') : '');
    } else if (c.state === 'missing') body = '<p class="v2p-none">هذه البيانات غير متاحة بعد من المنصة</p>';
    else {
      var expanded = !!S.expanded[tabKey + ':' + key];
      var shown = expanded ? c.items.length : (opts.shown || 6);
      var list = c.items.slice(0, shown).map(function (t) { return (opts.render || ticketHtml)(t, ticketTone); }).join('');
      if (!list) list = '<p class="v2p-none">' + esc(emptyText || 'لا شيء هنا الآن') + '</p>';
      var totalN = opts.total != null ? opts.total : c.items.length;
      if (!expanded && totalN > Math.min(c.items.length, shown)) list += '<button type="button" class="v2p-btn2 v2p-all" data-a="expand" data-k="' + tabKey + ':' + key + '">اعرض الكل (' + esc(ar(totalN)) + ')</button>';
      body = list;
      if (c.state === 'mixed') (c.retry || []).forEach(function (r) {
        body += '<p class="v2p-miss">' + (r.missing ? 'قائمة الانتظار غير متاحة بعد من المنصة' : 'تعذّر جلب ' + esc(r.label)) + (r.missing ? '' : ' — <button type="button" class="v2p-link" data-a="retry" data-key="' + esc(r.key) + '">أعد المحاولة</button>') + '</p>';
      });
      if (c.partial) body += '<p class="v2p-miss">معروض جزء فقط — القائمة ناقصة</p>';
    }
    return '<section class="v2p-col tone-' + esc(c.tone || 'wait') + (opts.active ? ' on' : '') + (opts.dim ? ' dim' : '') + '" data-col="' + key + '" aria-label="' + esc(c.label) + '"><header class="v2p-ch"><b>' + esc(c.label)
      + '</b><span class="v2p-n">' + esc(c.countText != null ? c.countText : (c.count == null ? '—' : ar(c.count))) + '</span></header><div class="v2p-list">' + body + '</div></section>';
  }
  var REQ_ORDER = ['visitors', 'approval', 'join', 'founding'];
  function pickActive(tab, cols, order) {
    var a = S.col[tab];
    if (order.indexOf(a) < 0 || !S.picked[tab]) {
      a = order.filter(function (k) { return cols[k].items && cols[k].items.length; })[0] || order[0];
    }
    S.col[tab] = a; return a;
  }
  function drawRequests(v) {
    var R = S.req = P.requests(reqInputs(), now());
    var active = pickActive('requests', R.cols, REQ_ORDER);
    var all = REQ_ORDER.every(function (k) { return R.cols[k].state === 'ready'; });
    var total = REQ_ORDER.reduce(function (n, k) { return n + R.cols[k].items.length; }, 0);
    var partial = [];
    var inv = readyData('invites');
    if (inv && inv.count != null && inv.count > (inv.rows || []).length) partial.push('معروض ' + ar((inv.rows || []).length) + ' من ' + ar(inv.count) + ' دعوة — القائمة ناقصة');
    var tr = (window.INBOX_TRUNCATED || []).map(function (x) { return String(x).split(':')[0].trim(); }).filter(function (l) { return ['زوّار ينتظرون الفتح', 'طلبات تقديم الخدمة', 'ليدات خبير مؤسس'].indexOf(l) > -1; });
    if (tr.length) partial.push('معروض جزء فقط من: ' + tr.map(function (l) { return { 'زوّار ينتظرون الفتح': 'الزوّار', 'طلبات تقديم الخدمة': 'طلبات تقديم الخدمة', 'ليدات خبير مؤسس': 'الخبراء المؤسسون' }[l]; }).join(' · ') + ' — القائمة ناقصة');
    var head = '<div class="v2p-top"><p class="v2p-brain">' + BRAIN + '<span>' + esc(R.head.text) + '</span></p><button type="button" class="v2p-btn2" data-a="refresh">حدّث</button></div>'
      + (R.head.invitesLine ? '<p class="v2p-jump"><a href="' + esc(R.head.invitesLine.href) + '" data-a="goto-pipeline">' + esc(R.head.invitesLine.text) + '</a></p>' : '');
    var body;
    if (all && total === 0) {
      body = emptyCard('لا أحد ينتظر قرارك الآن');
    } else {
      body = segHtml(R.cols, REQ_ORDER, active, '') + '<div class="v2p-cols cols4">' + REQ_ORDER.map(function (k) {
        return colHtml(k, R.cols[k], 'requests', TONE_CLS[R.cols[k].tone] || 'wait', 'لا شيء هنا الآن', { active: k === active });
      }).join('') + '</div>';
    }
    body += laterHtml(R.later);
    v.innerHTML = '<div class="v2p" data-tab="requests">' + head + warnStrips(R.head.failedLabels.length ? R.head.failedLabels : null, partial) + body + '</div>';
  }
  function laterHtml(L2) {
    if (L2.state === 'loading') return '';
    var title = 'سجّلوا ولم يطلبوا الفتح بعد';
    if (L2.state !== 'ready') return '<section class="v2p-later"><div class="v2p-lh"><b>' + title + '</b></div><p class="v2p-none">' + (L2.state === 'missing' ? 'هذه البيانات غير متاحة بعد من المنصة' : 'تعذّر جلب هذه القائمة — أعد المحاولة') + '</p>'
      + (L2.state === 'failed' ? '<button type="button" class="v2p-btn2" data-a="retry" data-key="pendingUsers">أعد المحاولة</button>' : '') + '</section>';
    var open = S.laterOpen;
    var cnt = '(' + ar(L2.rows.length) + ')' + (L2.total != null && L2.total > L2.rows.length ? ' · معروض ' + ar(L2.shown) + ' من ' + ar(L2.total) : '');
    var h = '<section class="v2p-later"><button type="button" class="v2p-lh" data-a="later" aria-expanded="' + open + '"><b>' + title + ' ' + esc(cnt) + '</b><span class="v2p-caret" aria-hidden="true">' + (open ? '▴' : '▾') + '</span></button>';
    if (open) {
      h += L2.rows.length ? '<ul class="v2p-lrows">' + L2.rows.map(function (r) {
        return '<li class="v2p-lrow" data-id="' + esc(r.id) + '"><div class="v2p-lid"><b>' + personLink(r.name, r.email) + '</b>' + (r.rejected ? '<span class="v2p-chip2 red">رُفض طلب سابق</span>' : '')
          + '<span class="v2p-em">' + esc(r.email) + '</span><span class="v2p-mute">' + esc([r.signedText, r.lastText, r.aiText].filter(Boolean).join(' · ')) + '</span></div>'
          + '<div class="v2p-lacts"><button type="button" class="v2p-btn2" data-a="later-open" data-id="' + esc(r.id) + '">افتح المنصة</button><button type="button" class="v2p-btn3" data-a="later-del" data-id="' + esc(r.id) + '">احذف نهائيًا</button></div></li>';
      }).join('') + '</ul>' : '<p class="v2p-none">لا أحد هنا الآن</p>';
    }
    return h + '</section>';
  }

  // ------------------------------------------------------------------ لوحة الدعوات
  function numCard(cls, title, value, notes, link) {
    var na = value == null;
    return '<div class="v2p-num ' + cls + (na ? ' na' : '') + '"><h3>' + esc(title) + '</h3><div class="v2p-big' + (na ? ' na' : '') + '">' + (na ? NA : esc(ar(value))) + '</div>'
      + notes.map(function (n) { return n ? '<p class="v2p-note">' + esc(n) + '</p>' : ''; }).join('') + (link || '') + '</div>';
  }
  var PIPE_ORDER = ['waiting', 'journey', 'joined', 'stopped'];
  var PIPE_DEF = { waiting: ['لم تُفتح بعد', 'تنتظر', 'wait'], journey: ['في الطريق', 'في الطريق', 'ink'], joined: ['انضمّ — آخر ٧ أيام', 'انضمّ', 'ok'], stopped: ['توقّفت', 'توقّفت', 'late'] };
  function drawPipeline(v) {
    var inv = readyData('invites'), st = eff('invites');
    var PL = S.pl = P.pipeline(inv, st, now(), S.inviter);
    PIPE_ORDER.forEach(function (k) { var c = PL.cols[k]; c.label = PIPE_DEF[k][0]; c.short = PIPE_DEF[k][1]; c.tone = PIPE_DEF[k][2]; c.count = c.total; c.countText = PL.state === 'ready' ? ar(c.total) : (PL.state === 'loading' ? '…' : '—'); });
    var brain = PL.state === 'ready' ? PL.brain : [PL.state === 'loading' ? '…جارٍ الجلب' : NA];
    var head = '<div class="v2p-top"><div class="v2p-brain tall">' + BRAIN + '<div class="v2p-bl">' + brain.map(function (l, i) { return '<span' + (i ? ' class="s"' : '') + '>' + esc(l) + '</span>'; }).join('') + '</div></div>'
      + '<div class="v2p-topacts"><button type="button" class="v2p-btn1 inline" data-a="new-invite">+ دعوة جديدة</button><button type="button" class="v2p-gear" data-a="settings" aria-label="إعدادات الدعوة" title="إعدادات الدعوة">' + GEAR + '</button></div></div>';
    var sub = PL.partial ? ' (من آخر ' + ar(PL.partial.shown) + ' دعوة)' : '';
    var steps = PL.steps.map(function (s2) { return s2.label + ' ' + (s2.n == null ? NA : ar(s2.n)); }).join(' · ');
    var awaitingLink = '<a class="v2p-lnk" href="' + esc('#s/people/invites') + '" data-a="goto-requests">افتح الطلبات</a>';
    var cards = '<div class="v2p-nums">'
      + numCard('k-sent', 'أُرسلت', PL.cards.sent, [sub])
      + numCard('k-open', 'فُتحت', PL.cards.opened, [PL.pct.opened, steps])
      + numCard('k-join', 'انضمّ', PL.cards.joined, [PL.pct.joined])
      + numCard('k-wait', 'تنتظر موافقتك', PL.cards.awaiting, [], PL.cards.awaiting ? awaitingLink : '') + '</div>';
    var strips = '';
    if (PL.partial) strips += '<div class="v2p-warn" role="status">معروض ' + esc(ar(PL.partial.shown)) + ' من ' + esc(ar(PL.partial.total)) + ' — الأعداد من المعروض فقط</div>';
    if (PL.state === 'failed') strips += '<div class="v2p-warn" role="status">تعذّر جلب: الدعوات — القائمة ناقصة وليس معناه أنه لا شيء</div>';
    var body;
    if (PL.state === 'ready' && (inv.rows || []).length === 0) {
      body = emptyCard('لم تُرسل أي دعوة بعد', '<button type="button" class="v2p-btn1 inline" data-a="new-invite">+ دعوة جديدة</button>');
    } else if (PL.state === 'loading') {
      body = '<div class="v2p-cols cols4">' + PIPE_ORDER.map(function (k) { return colHtml(k, Object.assign({}, PL.cols[k], { state: 'loading' }), 'pipeline', 'wait', ''); }).join('') + '</div>';
    } else if (PL.state !== 'ready') {
      var m = PL.state === 'missing' ? '<p class="v2p-none">هذه البيانات غير متاحة بعد من المنصة</p>' : '<p class="v2p-none">تعذّر جلب الدعوات — لا تعتبر الشاشة فارغة.</p><button type="button" class="v2p-btn2" data-a="retry" data-key="invites">أعد المحاولة</button>';
      body = '<div class="v2p-empty"><b>الدعوات: ' + NA + '</b>' + m + '</div>';
    } else {
      var active = pickActive('pipeline', PL.cols, PIPE_ORDER);
      var sel = '<div class="v2p-filter"><label for="v2pinv">الداعي</label><select id="v2pinv" data-a="inviter">' + PL.inviters.map(function (i2) {
        return '<option value="' + esc(i2.key) + '"' + (i2.key === (S.inviter || 'all') ? ' selected' : '') + '>' + esc(i2.label) + '</option>'; }).join('') + '</select><span class="v2p-mute">الأرقام أعلاه لكل الدعوات</span></div>';
      body = sel + segHtml(PL.cols, PIPE_ORDER, active, '') + '<div class="v2p-cols cols4">' + PIPE_ORDER.map(function (k) {
        var c = PL.cols[k], expJ = k === 'joined' && S.expanded['pipeline:joined'];
        return colHtml(k, { state: 'ready', items: expJ ? c.all : c.items, tone: c.tone, label: c.label, countText: c.countText, count: c.count, partial: false }, 'pipeline', c.tone === 'late' ? 'late' : c.tone, 'لا شيء هنا الآن',
          { active: k === active, shown: c.shown, total: c.total, dim: k === 'joined' || k === 'stopped' });
      }).join('') + '</div>';
    }
    v.innerHTML = '<div class="v2p" data-tab="pipeline">' + head + strips + (PL.state === 'ready' && (inv.rows || []).length === 0 ? '' : cards) + body + '</div>';
  }

  // ------------------------------------------------------------------ لوحة الرسائل
  var MSG_ORDER = ['site', 'chat', 'follow'];
  function msgTicket(t) {
    var id = t.id, mode = S.sent[id];
    var tone = t.old ? 'wait' : 'ink';
    S.items[id] = t;
    var title = esc(t.title);
    var h = '<article class="v2p-t tone-' + tone + '" data-id="' + esc(id) + '"><div class="v2p-strip"><span class="v2p-type">' + esc(t.strip) + '</span>' + (t.ageText ? '<time class="v2p-time">' + esc(t.ageText) + '</time>' : '') + '</div>'
      + '<div class="v2p-body"><h3>' + title + '</h3>' + (t.sub ? '<p class="v2p-subl">' + esc(t.sub) + '</p>' : '') + (t.body ? '<p class="v2p-prev">' + esc(t.body) + '</p>' : '')
      + (t.email ? '<p class="v2p-em">' + esc(t.email) + '</p>' : '') + (t.phone ? '<p class="v2p-em">' + esc(t.phone) + '</p>' : '')
      + (t.brain ? '<div class="v2p-bline">' + BRAIN + '<p>' + esc(t.brain) + '</p></div>' : '');
    if (S.err[id]) h += '<div class="v2p-err" role="alert">' + esc(S.err[id]) + '</div>';
    if (S.done[id]) return h + '<p class="v2p-ok" role="status">' + esc(S.done[id]) + '</p></div></article>';
    if (mode) {
      var yes = t.src === 'follow' ? 'نعم، تمت المتابعة' : 'نعم، علّمها منتهية';
      h += '<div class="v2p-acts"><p class="v2p-q">هل أرسلت الرد؟</p><button type="button" class="v2p-btn1" data-a="resolve" data-id="' + esc(id) + '"' + (S.busy[id] ? ' disabled' : '') + '>' + (S.busy[id] ? 'جارٍ التنفيذ…' : yes) + '</button>'
        + '<div class="v2p-sacts"><button type="button" class="v2p-btn2" data-a="notyet" data-id="' + esc(id) + '">ليس بعد</button></div></div>';
    } else if (t.primary) {
      h += '<div class="v2p-acts">' + actBtn(t, t.primary, 'v2p-btn1', 'p');
      var sec = (t.secondary || []).map(function (a, i) { return actBtn(t, a, 'v2p-btn2', 's' + i); }).join('');
      if (sec) h += '<div class="v2p-sacts">' + sec + '</div>';
      h += '</div>';
    }
    return h + '</div></article>';
  }
  function drawMessages(v) {
    var M = S.msg = messagesVM();
    var tones = { site: 'ink', chat: 'ink', follow: 'green' };
    MSG_ORDER.forEach(function (k) { var c = M.cols[k]; c.tone = tones[k] === 'green' ? 'ok' : 'wait'; c.countText = c.state === 'loading' ? '…' : (c.count == null ? '—' : ar(c.count)); c.retry = c.state === 'failed' ? [{ key: k, label: c.label }] : []; });
    var active = pickActive('messages', M.cols, MSG_ORDER);
    var all = MSG_ORDER.every(function (k) { return M.cols[k].state === 'ready'; });
    var total = MSG_ORDER.reduce(function (n, k) { return n + M.cols[k].items.length; }, 0);
    var head = '<div class="v2p-top"><p class="v2p-brain">' + BRAIN + '<span>' + esc(M.head.text) + '</span></p><button type="button" class="v2p-btn2" data-a="refresh">حدّث</button></div>';
    var warn = warnStrips(M.head.failedLabels && M.head.failedLabels.length ? M.head.failedLabels : null, []);
    var body;
    if (all && total === 0 && !M.replied.length) body = emptyCard('لا رسائل تنتظر الرد');
    else {
      body = segHtml(M.cols, MSG_ORDER, active, 'three') + '<div class="v2p-cols cols3">' + MSG_ORDER.map(function (k) {
        return colHtml(k, M.cols[k], 'messages', 'wait', 'لا شيء هنا الآن', { active: k === active, render: msgTicket });
      }).join('') + '</div>';
    }
    if (M.replied.length) {
      var open = S.expanded['messages:replied'];
      body += '<section class="v2p-later"><button type="button" class="v2p-lh" data-a="expand" data-k="messages:replied" aria-expanded="' + !!open + '"><b>رسائل رُدّ عليها (' + esc(ar(M.replied.length)) + ')</b><span class="v2p-caret" aria-hidden="true">' + (open ? '▴' : '▾') + '</span></button>'
        + (open ? '<ul class="v2p-lrows">' + M.replied.map(function (r) {
          S.items[r.id] = r;
          return '<li class="v2p-lrow"><div class="v2p-lid"><b>' + esc(r.name) + '</b><span class="v2p-mute">' + esc([r.topic, r.dateText].filter(Boolean).join(' · ')) + '</span></div><div class="v2p-lacts"><button type="button" class="v2p-btn3" data-a="msg-del" data-id="' + esc(r.id) + '">احذف</button></div></li>';
        }).join('') + '</ul>' : '') + '</section>';
    }
    v.innerHTML = '<div class="v2p" data-tab="messages">' + head + warn + body + '</div>';
  }

  // ------------------------------------------------------------------ لوحة المستخدمين
  function chipRowHtml(UV) {
    var f = S.users.filter, k = (f.role ? 1 : 0) + (f.seg ? 1 : 0) + (S.users.sort === 'login' ? 1 : 0);
    var chips = UV.chips.map(function (c) {
      return '<button type="button" class="v2p-chip' + (c.key === S.users.chip ? ' on' : '') + '" data-a="chip" data-k="' + c.key + '" aria-pressed="' + (c.key === S.users.chip) + '">' + esc(c.label) + (c.n != null ? ' <b>' + esc(ar(c.n)) + '</b>' : '') + '</button>';
    }).join('');
    var filt = '<button type="button" class="v2p-chip filt' + (k ? ' on' : '') + '" data-a="filter">تصفية' + (k ? ' (' + esc(ar(k)) + ')' : '') + '</button>';
    var act = UV.activeFilters.map(function (a) { return '<button type="button" class="v2p-xchip" data-a="unfilter" data-k="' + a.key + '">× ' + esc(a.label) + '</button>'; }).join('');
    return '<div class="v2p-chips" role="group" aria-label="تصنيف الحسابات">' + chips + filt + '</div>' + (act ? '<div class="v2p-xrow">' + act + '</div>' : '');
  }
  function userRowHtml(u) {
    S.items['user:' + u.id] = u;
    var chips = u.chips.map(function (c) { return '<span class="v2p-ch2 k-' + esc(c.key) + (c.gold ? ' gold' : '') + '">' + esc(c.label) + '</span>'; }).join('');
    return '<article class="v2p-u' + (u.active ? '' : ' off') + '" data-a="person" data-email="' + esc(u.email) + '"><span class="v2p-av" aria-hidden="true">' + esc(u.initial) + '</span><div class="v2p-uid">'
      + '<h3>' + personLink(u.name, u.email) + '</h3><div class="v2p-uch">' + chips + '</div><p class="v2p-em">' + esc(u.email) + '</p>'
      + '<p class="v2p-um">' + esc(u.planText + ' · انضمّ ' + u.joinedText + ' · آخر دخول ' + u.lastText) + (u.fromSearch ? ' · من البحث' : '') + '</p></div>'
      + '<button type="button" class="v2p-btn2" data-a="person" data-email="' + esc(u.email) + '">افتح صفحة الشخص</button></article>';
  }
  function usersBodyHtml(UV) {
    if (UV.state === 'loading') return '<div class="v2p-list one">' + skeleton() + skeleton() + skeleton() + '</div><p class="v2p-none">…جارٍ جلب الحسابات</p>';
    if (UV.state === 'failed') return '<div class="v2p-empty"><b>الحسابات: ' + NA + '</b><p class="v2p-none">تعذّر الجلب الآن، فلا تعتبر الشاشة فارغة.</p><button type="button" class="v2p-btn2" data-a="retry" data-key="users">أعد المحاولة</button></div>';
    if (UV.state === 'empty') return emptyCard('لا حسابات بعد');
    var h = chipRowHtml(UV);
    if (UV.empty) h += '<div class="v2p-empty small"><b>' + esc(UV.empty.text) + '</b>' + (UV.empty.hint ? '<p class="v2p-none">' + esc(UV.empty.hint) + '</p>' : '') + '</div>';
    else h += '<div class="v2p-list one">' + UV.rows.map(userRowHtml).join('') + '</div>' + (UV.more ? '<button type="button" class="v2p-btn2 v2p-all" data-a="more-users">اعرض ' + esc(ar(UV.more)) + ' أخرى</button>' : '');
    if (UV.truncated && UV.total != null) h += '<p class="v2p-fine">معروض ' + esc(ar(S.rawN || 0)) + ' من ' + esc(ar(UV.total)) + ' — اكتب في البحث للوصول إلى الباقي</p>';
    return h;
  }
  function drawUsers(v) {
    var raw = usersRaw();
    var UV = S.uv = P.users(raw, usersInputs());
    S.rawN = raw ? raw.length : 0;
    var skel = v.querySelector('.v2p[data-tab="users"]');
    if (!skel) {
      v.innerHTML = '<div class="v2p" data-tab="users"><div class="v2p-top"><p class="v2p-brain" id="v2pUHead"></p><button type="button" class="v2p-btn2" data-a="new-invite">+ دعوة جديدة</button></div>'
        + '<div class="v2p-search"><label for="v2pq" class="v2p-sr">ابحث عن حساب</label><input id="v2pq" type="search" autocomplete="off" placeholder="ابحث بالاسم أو البريد أو الهاتف" dir="auto" aria-describedby="v2pUStatus">'
        + '<p class="v2p-sline" id="v2pUStatus" role="status"></p></div><div id="v2pUBody"></div></div>';
      var inp = q('#v2pq', v);
      inp.value = S.users.q;
      inp.addEventListener('input', function () {
        clearTimeout(S.users.timer);
        S.users.timer = setTimeout(function () { S.users.q = inp.value; S.users.limit = 50; runUserSearch(); drawUsers(S.view); }, 200);
      });
      inp.addEventListener('keydown', function (e) {
        if (e.key !== 'Enter') return;
        e.preventDefault();
        var val = inp.value.trim().toLowerCase(), em = L.personEmailOf(val);
        S.users.q = inp.value;
        if (em && (!S.uv || !S.uv.rows.length)) { host().openPerson && host().openPerson(em); return; }
        runUserSearch(true); drawUsers(S.view);
      });
    }
    var hd = q('#v2pUHead', v);
    if (hd) hd.innerHTML = BRAIN + '<span>' + esc(UV.state === 'loading' ? '…جارٍ الجلب' : (UV.state === 'failed' ? NA : UV.head)) + '</span>';
    var st = q('#v2pUStatus', v); if (st) st.textContent = UV.searchLine || '';
    var bd = q('#v2pUBody', v); if (bd) bd.innerHTML = usersBodyHtml(UV);
  }
  // بحث الخادم: لما العدد الكلي أكبر من المعروض والنص حرفان فأكثر. ⛔ فشله يُقال صراحة.
  function runUserSearch(force) {
    var U0 = S.users, qq = String(U0.q || '').trim(), raw = usersRaw(), m = dataOf('metrics');
    var total = m && m.raw && m.raw.customers && typeof m.raw.customers.total === 'number' ? m.raw.customers.total : null;
    U0.searchFailed = false;
    if (qq.length < 2 || !raw || (total != null ? total <= raw.length : raw.length < 500)) { U0.extra = []; U0.searching = false; return; }
    var seq = ++U0.seq; U0.searching = true;
    PX.read('/platform-users?search=' + encodeURIComponent(qq.slice(0, 80))).then(function (r) {
      if (seq !== U0.seq) return;
      U0.extra = (r && Array.isArray(r.users)) ? r.users : []; U0.searching = false; refreshUsers();
    }).catch(function () { if (seq !== U0.seq) return; U0.extra = []; U0.searching = false; U0.searchFailed = true; refreshUsers(); });
  }
  function refreshUsers() { if (S.view && S.tab === 'users' && isCurrent()) drawUsers(S.view); }

  // ------------------------------------------------------------------ الدخول والرسم والتحديث
  function isCurrent() { return !!(S.view && document.body.contains(S.view) && host().current && owns(host().current())); }
  function signature() {
    var E = ep(), keys = KEYS[S.tab] || [];
    var out = keys.map(function (k) { return k + ':' + stateOf(k) + ':' + ser(E && E.data ? E.data[k] : null); }).join(',');
    out += '|' + ser(window.INBOX) + '|' + (window.INBOX_FAILED || []).length + '|' + (window.INBOX_TRUNCATED || []).length;
    out += '|' + S.own.chat.state + ser(S.own.chat.rows) + S.own.follow.state + ser(S.own.follow.rows);
    return out;
  }
  var redrawT = null;
  function changedSoon() { if (redrawT) return; redrawT = setTimeout(function () { redrawT = null; if (isCurrent()) redraw(); }, 0); }
  function busyNow() { return Object.keys(S.busy).some(function (k) { return S.busy[k]; }); }
  function redraw(force) {
    if (!isCurrent()) return;
    if (!force && (document.getElementById('epModal') || busyNow())) return;
    var v = S.view;
    S.tab = tabOfMod(host().current());
    var inputFocus = document.activeElement && document.activeElement.closest && document.activeElement.closest('.v2p') && /^(INPUT|TEXTAREA|SELECT)$/.test(document.activeElement.tagName);
    if (inputFocus && S.tab !== 'users' && !force) return;
    S.items = {};
    if (S.tab === 'requests') drawRequests(v);
    else if (S.tab === 'pipeline') drawPipeline(v);
    else if (S.tab === 'users') drawUsers(v);
    else drawMessages(v);
    S.sig = signature();
  }
  function render(mod, view) {
    S.view = view; S.mod = mod; S.tab = tabOfMod(mod);
    if (S.tab !== 'users') { /* الشاشات الأخرى تُرسم من جديد دائمًا */ }
    ensureKeys(S.tab);
    if (S.tab === 'users') {
      try { if (typeof pendingUserFocus === 'string' && pendingUserFocus) { var em = pendingUserFocus; pendingUserFocus = null; if (window.V2D2 && V2D2.openPerson) { V2D2.openPerson(em); return; } } } catch (e) {}
      view.innerHTML = '';     // هيكل البحث يُبنى من جديد عند كل دخول للتبويب
    }
    redraw(true);
    if (!S.poll) {
      S.poll = setInterval(function () {
        if (!isCurrent()) { S.sheetWas = false; return; }
        S.tab = tabOfMod(host().current());
        var open = !!document.getElementById('epModal');
        if (open) { S.sheetWas = true; return; }
        if (S.sheetWas) { S.sheetWas = false; S.sheet = null; redraw(true); return; }
        if (signature() !== S.sig) redraw();
      }, 400);
    }
    if (!S.minute) S.minute = setInterval(function () { if (isCurrent() && !document.getElementById('epModal') && !busyNow()) redraw(); }, 60000);
  }

  // ------------------------------------------------------------------ الأوراق (نافذة الداشبورد الموجودة + صنف v2pm)
  var SH = { cur: null, back: null };
  function sheetEl(title, side) {
    var el = document.getElementById('epModal');
    if (!el || !el.classList.contains('v2pm-wrap')) {
      if (el && typeof window.closeModal === 'function') window.closeModal();
      if (typeof window.openModal !== 'function') return null;
      el = window.openModal(title, '<div class="v2pm-in"></div>');
      el.classList.add('v2pm-wrap');
      var mo0 = el.querySelector('.modal'); if (mo0) mo0.classList.add('v2pm');
      var x = el.querySelector('[data-x]'); if (x) x.setAttribute('aria-label', 'إغلاق');
    }
    var mo = el.querySelector('.modal');
    mo.classList.toggle('v2pm-side', !!side);
    el.classList.toggle('v2pm-sidew', !!side);
    var sp = el.querySelector('.mh span'); if (sp) sp.textContent = title;
    return el;
  }
  // الشاشة = {title, side, build()→{html, wire(root)}} وتُبنى من جديد كل مرة (فالرجوع من التأكيد يرجع بحالتها الحالية).
  function showScreen(sc) {
    SH.cur = sc;
    var b = sc.build();
    var el = sheetEl(sc.title, sc.side);
    if (!el) return null;
    var root = el.querySelector('.v2pm-in');
    root.innerHTML = b.html;
    var bd = el.querySelector('.mb'); if (bd) bd.scrollTop = 0;
    if (b.wire) b.wire(root, el);
    return el;
  }
  function closeSheet() { SH.cur = SH.back = null; if (typeof window.closeModal === 'function') window.closeModal(); S.sheetWas = true; }
  function backOrClose(back) { if (back) showScreen(back); else closeSheet(); }
  function runBtn(root, btn, fn, onOk) {
    var err = q('.v2pm-err', root), old = btn.textContent;
    btn.disabled = true; btn.textContent = 'جارٍ التنفيذ…'; if (err) err.textContent = '';
    var fail = function (m) { btn.disabled = false; btn.textContent = old; if (err) err.textContent = m || FAIL_AR; };
    var p; try { p = Promise.resolve(fn()); } catch (e) { return fail(FAIL_AR); }
    p.then(function (res) { res = res || {}; if (res.ok) onOk(res); else fail(resErr(res)); }).catch(function () { fail(FAIL_AR); });
  }
  function fld(label, id, o) {
    o = o || {};
    var h = '<div class="v2pm-fld"><label for="' + id + '">' + esc(label) + '</label>';
    if (o.area) h += '<textarea id="' + id + '" rows="3"' + (o.max ? ' maxlength="' + o.max + '"' : '') + (o.ph ? ' placeholder="' + esc(o.ph) + '"' : '') + '>' + esc(o.value || '') + '</textarea>';
    else h += '<input id="' + id + '" type="' + (o.type || 'text') + '" value="' + esc(o.value || '') + '"' + (o.ltr ? ' dir="ltr"' : ' dir="auto"') + (o.ph ? ' placeholder="' + esc(o.ph) + '"' : '')
      + (o.max ? ' maxlength="' + o.max + '"' : '') + (o.mode ? ' inputmode="' + o.mode + '"' : '') + ' autocomplete="off">';
    return h + (o.hint ? '<small>' + esc(o.hint) + '</small>' : '') + '</div>';
  }
  function dash(v) { v = v == null ? '' : String(v).trim(); return v === '—' ? '' : v; }
  function kvRows(list) {
    var rows = list.filter(function (r) { return dash(r[1]); });
    if (!rows.length) return '';
    return '<dl class="v2pm-rows">' + rows.map(function (r) { return '<div><dt>' + esc(r[0]) + '</dt><dd' + (r[2] ? ' dir="ltr" class="ltr"' : '') + '>' + (r[3] ? r[1] : esc(r[1])) + '</dd></div>'; }).join('') + '</dl>';
  }
  function acts() { return '<div class="v2pm-acts">' + Array.prototype.slice.call(arguments).join('') + '</div>'; }
  function btn(id, label, cls) { return '<button type="button" class="' + (cls || 'v2p-btn2') + '" id="' + id + '">' + esc(label) + '</button>'; }
  function errBox() { return '<div class="v2pm-err" role="alert"></div>'; }
  function okLine(t) { return t ? '<p class="v2pm-ok" role="status">' + esc(t) + '</p>' : ''; }
  function toLatin(s) { return String(s == null ? '' : s).replace(/[٠-٩]/g, function (d) { return String(d.charCodeAt(0) - 0x660); }).replace(/[۰-۹]/g, function (d) { return String(d.charCodeAt(0) - 0x6F0); }); }
  function fmtWhen(iso) { if (!iso) return ''; try { return new Intl.DateTimeFormat('ar-EG', { day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit' }).format(new Date(iso)); } catch (e) { return ''; } }
  function copyText(text, cb) {
    var done = function (ok) { if (cb) cb(ok); };
    try {
      if (navigator.clipboard && navigator.clipboard.writeText) { navigator.clipboard.writeText(text).then(function () { done(true); }, function () { done(fallbackCopy(text)); }); return; }
    } catch (e) {}
    done(fallbackCopy(text));
  }
  function fallbackCopy(text) {
    try { var ta = document.createElement('textarea'); ta.value = text; ta.setAttribute('readonly', ''); ta.style.cssText = 'position:fixed;opacity:0;top:0'; document.body.appendChild(ta); ta.select(); var ok = document.execCommand('copy'); ta.remove(); return !!ok; } catch (e) { return false; }
  }

  // —— تأكيد (S14 وأخواتها): العنوان والجملة والزرّ، ثم التنفيذ. «رجوع» يرجع للشاشة التي فتحته.
  function confirmScreen(o) {
    var back = o.back === undefined ? SH.cur : o.back;
    showScreen({ title: o.title || 'تأكيد التغيير', build: function () {
      var h = (o.lead ? '<p class="v2pm-lead">' + (o.leadHtml ? o.lead : esc(o.lead)) + '</p>' : '') + (o.body || '') + errBox()
        + acts('<button type="button" class="' + (o.danger ? 'v2p-btn1 danger' : 'v2p-btn1') + '" id="v2pmGo"' + (o.disabled ? ' disabled' : '') + '>' + esc(o.label || 'أكّد') + '</button>', btn('v2pmBack', 'رجوع'));
      return { html: h, wire: function (root) {
        if (o.wire) o.wire(root);
        q('#v2pmBack', root).onclick = function () { backOrClose(back); };
        q('#v2pmGo', root).onclick = function () { runBtn(root, this, function () { return o.run(root); }, function (res) { if (o.onOk) o.onOk(res, back); else closeSheet(); }); };
      } };
    } });
  }

  // ------------------------------------------------------------------ تفاصيل الطلبات (زائر · قائمة انتظار · خدمة · مؤسس)
  function pendingRowOf(id, email) {
    var p = dataOf('pendingUsers'); if (!p || !Array.isArray(p.rows)) return null;
    for (var i = 0; i < p.rows.length; i++) if ((id && p.rows[i].id === id) || (email && String(p.rows[i].email).toLowerCase() === String(email).toLowerCase())) return p.rows[i];
    return null;
  }
  function visitorScreen(pu, inboxRow) {
    var name = (pu && pu.name) || (inboxRow && inboxRow.who) || 'زائر';
    var id = (pu && pu.id) || (inboxRow && inboxRow.apiId) || '';
    var email = (pu && pu.email) || (inboxRow && (inboxRow.personEmail || inboxRow.email)) || '';
    var flags = (pu && pu.flagLabels && pu.flagLabels.length) ? pu.flagLabels : ((inboxRow && inboxRow.flagLabels) || []);
    var sc = { title: name, build: function () {
      var rowsH = kvRows([['البريد', email, true], ['الهاتف', pu && pu.phone, true], ['الصفة', dash(pu && pu.roleLabel) || (inboxRow && inboxRow.puRole)], ['التخصص', dash(pu && pu.specialtyLabel)],
        ['البلد', dash(pu && pu.countryLabel) || (inboxRow && inboxRow.puCountry)], ['بلد التسجيل', dash(pu && pu.signupCountryLabel)], ['سبب الانضمام', pu && pu.why], ['سجّل في', pu && pu.signedAt],
        ['طلب الفتح منذ', pu && pu.requestedAt ? U.agoText(pu.requestedAt, now()).replace(/^منذ /, '') : ''], ['الأسئلة المستعملة', pu && pu.aiUsed != null ? ar(pu.aiUsed) : ''], ['يحتاج مراجعة', flags.join(' · ')]]);
      var h = rowsH + '<div id="v2pmRej" hidden>' + fld('سبب الرفض (اختياري) — يُحفظ على الطلب، فاكتب ما لا تمانع أن يقرأه صاحبه', 'v2pmNote', { area: true, max: 300 }) + '</div>' + errBox()
        + acts(btn('v2pmOpen', 'افتح المنصة', 'v2p-btn1'), btn('v2pmRej0', 'ارفض ويبقى زائرًا'), btn('v2pmDel', 'احذف الحساب نهائيًا', 'v2p-btn3'));
      return { html: h, wire: function (root) {
        var rejMode = false;
        q('#v2pmOpen', root).onclick = function () {
          runBtn(root, this, function () { return PX.call({ path: '/pending-users/' + encodeURIComponent(id) + '/access', body: { access: 'member' }, reload: ['inbox', 'pendingUsers'] }); }, function () { closeSheet(); });
        };
        q('#v2pmRej0', root).onclick = function () {
          if (!rejMode) { rejMode = true; q('#v2pmRej', root).hidden = false; this.textContent = 'أكّد الرفض'; this.classList.add('danger'); q('#v2pmNote', root).focus(); return; }
          var note = q('#v2pmNote', root).value.trim().slice(0, 300), body = { access: 'pending' }; if (note) body.note = note;
          runBtn(root, this, function () { return PX.call({ path: '/pending-users/' + encodeURIComponent(id) + '/access', body: body, reload: ['inbox', 'pendingUsers'] }); }, function () { closeSheet(); });
        };
        q('#v2pmDel', root).onclick = function () { purgeScreen({ id: id, name: name, email: email }, sc); };
      } };
    } };
    showScreen(sc);
  }
  function waitlistScreen(w) {
    showScreen({ title: w.name || 'بلا اسم', build: function () {
      return { html: kvRows([['البريد', w.email, true], ['الهاتف', w.phone, true], ['الصفة', dash(w.roleLabel)], ['التخصص', dash(w.specialtyLabel)], ['البلد', dash(w.countryLabel)], ['سبب الطلب', w.note], ['التاريخ', w.at ? fmtWhen(w.at) : '']])
        + acts(btn('v2pmInv', 'أرسل دعوة', 'v2p-btn1'), btn('v2pmClose', 'إغلاق')),
        wire: function (root) { q('#v2pmInv', root).onclick = function () { phoneScreen(w); }; q('#v2pmClose', root).onclick = closeSheet; } };
    } });
  }
  function joinScreen(row) {
    var sc = { title: row.who || 'مقدّم الطلب', side: true, build: function () {
      var files = (Array.isArray(row.attachments) ? row.attachments : []).map(function (a, i) { var u = safeHttps(a && a.url ? a.url : a); return u ? '<a href="' + esc(u) + '" target="_blank" rel="noopener">مرفق ' + esc(ar(i + 1)) + '</a>' : ''; }).filter(Boolean).join(' · ');
      var det = (row.details || []).map(function (d) { return [d.k, String(d.v)]; });
      var h = (row.licenceMissing ? '<p class="v2pm-warn">' + esc(row.licenceNote || 'الترخيص بلا رقم قيد — لا يُقبل الطلب قبل استكماله') + '</p>' : '')
        + kvRows([['الخدمة', row.serviceLabel || row.from], ['الحالة', row.statusLabel], ['الترخيص', row.licensed ? 'مع ترخيص' : 'بلا ترخيص'], ['البريد', row.email || row.personEmail, true]].concat(det))
        + (files ? '<p class="v2pm-files">' + files + '</p>' : '') + (row.infoRequest ? '<p class="v2pm-lead">طُلب من صاحب الطلب: ' + esc(row.infoRequest) + ' — بانتظار رده</p>' : '') + errBox()
        + acts(row.licenceMissing ? '' : btn('v2pmOk', 'اقبل', 'v2p-btn1'), btn('v2pmNo', 'ارفض', 'v2p-btn3'), btn('v2pmAsk', 'اطلب استكمالًا'));
      return { html: h, wire: function (root) {
        var ok = q('#v2pmOk', root);
        if (ok) ok.onclick = function () { runBtn(root, this, function () { return ep().decideInboxItem(row, 'approve', null, ''); }, closeSheet); };
        q('#v2pmNo', root).onclick = function () { rejectJoinScreen(row, sc); };
        q('#v2pmAsk', root).onclick = function () { infoJoinScreen(row, sc); };
      } };
    } };
    showScreen(sc);
  }
  function foundingScreen(row) {
    var sc = { title: row.who || 'خبير', build: function () {
      var det = (row.details || []).map(function (d) {
        if (d.k === 'لينكدإن') { var u = safeHttps(d.v); return [d.k, u ? '<a href="' + esc(u) + '" target="_blank" rel="noopener">فتح الرابط</a>' : '', true, true]; }
        return [d.k, String(d.v), d.k === 'واتساب'];
      });
      var wa = ''; (row.details || []).forEach(function (d) { if (d.k === 'واتساب') wa = d.v; });
      var h = kvRows([['البريد', row.email, true]].concat(det.map(function (d) { return d[3] ? [d[0], d[1], false, true] : d; }))) + '<p class="v2pm-lead">' + esc(L.v2Card(row, { now: now() }).reason) + '</p>' + errBox()
        + acts(btn('v2pmGo', L.v2Card(row, { now: now() }).primary.label, 'v2p-btn1'), btn('v2pmMk', 'أنشئ دعوة بهذه البيانات'), btn('v2pmNo', 'ليس مناسبًا', 'v2p-btn3'));
      return { html: h, wire: function (root) {
        q('#v2pmGo', root).onclick = function () { runBtn(root, this, function () { return ep().decideInboxItem(row, 'approve', null, ''); }, closeSheet); };
        q('#v2pmMk', root).onclick = function () { newInviteScreen({ name: row.who || '', phone: phoneOk(wa) ? String(wa).replace(/[^\d+]/g, '') : '', email: row.email || '' }, sc); };
        q('#v2pmNo', root).onclick = function () { rejectFoundingScreen(row, sc); };
      } };
    } };
    showScreen(sc);
  }
  function rejectFoundingScreen(row, back) {
    confirmScreen({ title: 'ليس مناسبًا', lead: 'سيُعلَّم طلب ' + (row.who || 'هذا الخبير') + ' «ليس مناسبًا» ويخرج من القائمة.', label: 'نعم، ليس مناسبًا', danger: true, back: back,
      run: function () { return ep().decideInboxItem(row, 'reject', null, ''); } });
  }
  function rejectJoinScreen(row, back) {
    confirmScreen({ title: 'رفض طلب تقديم خدمة', lead: 'يقرأ صاحب الطلب السبب كما تكتبه.', back: back, label: 'ارفض الطلب', danger: true,
      body: fld('سبب الرفض', 'v2pmReason', { area: true, max: 1000 }),
      run: function (root) {
        var why = q('#v2pmReason', root).value.trim();
        if (!why) return { ok: false, error: 'اكتب سبب الرفض — يقرؤه صاحب الطلب' };
        return ep().decideInboxItem(row, 'reject', null, why);
      } });
  }
  function infoJoinScreen(row, back) {
    confirmScreen({ title: 'طلب استكمال', lead: 'يبقى الطلب مفتوحًا حتى يرد صاحبه.', back: back, label: 'أرسل الطلب',
      body: fld('المطلوب بالضبط', 'v2pmAsk', { area: true, max: 1000 }),
      run: function (root) {
        var ask = q('#v2pmAsk', root).value.trim();
        if (!ask) return { ok: false, error: 'اكتب المطلوب بالضبط من صاحب الطلب' };
        return ep().decideInboxItem(row, 'request_info', null, ask);
      } });
  }

  // ------------------------------------------------------------------ الدعوات: جديدة · رابط · سحب · إعادة إصدار · رفض · تفصيل
  function phoneOk(v) { return digits(v).length >= 8; }
  function linkScreen(name, link, phone) {
    showScreen({ title: 'رابط الدعوة لـ' + (name || 'صاحب الدعوة'), build: function () {
      var l = safeHttps(link);
      var h = l ? '<div class="v2pm-fld"><label for="v2pmLink">رابط الدعوة</label><input id="v2pmLink" readonly dir="ltr" value="' + esc(l) + '"><small>الرابط شخصي، أرسله بنفسك.</small></div>'
        : '<p class="v2pm-warn">أُنشئت الدعوة لكن المنصة لم ترسل الرابط. ستجده في القائمة بعد التحديث.</p>';
      h += '<p class="v2pm-ok" id="v2pmCp" role="status" hidden>نُسخ الرابط</p>' + acts(l ? btn('v2pmCopy', 'انسخ الرابط', 'v2p-btn1') : '', l ? '<a class="v2p-btn2" id="v2pmWa" target="_blank" rel="noopener" href="' + esc(P.waUrl(phone, P.waText('invite', name, l))) + '">أرسل عبر واتساب</a>' : '', btn('v2pmDone', 'تم'));
      return { html: h, wire: function (root) {
        var c = q('#v2pmCopy', root); if (c) c.onclick = function () { copyText(l, function (ok) { var m = q('#v2pmCp', root); m.hidden = false; m.textContent = ok ? 'نُسخ الرابط' : 'تعذّر النسخ — انسخه يدويًا'; }); };
        q('#v2pmDone', root).onclick = closeSheet;
      } };
    } });
  }
  function newInviteScreen(pre, back) {
    pre = pre || {};
    var sc = { title: 'دعوة جديدة', build: function () {
      return { html: fld('الاسم', 'v2pmName', { value: pre.name, max: 120 }) + fld('رقم واتساب', 'v2pmPhone', { value: pre.phone, type: 'tel', ltr: true, mode: 'tel', hint: 'تُفتح الدعوة بهذا الرقم وحده' })
        + fld('البريد (اختياري)', 'v2pmMail', { value: pre.email, type: 'email', ltr: true }) + fld('ملاحظة لك (اختياري)', 'v2pmNote', { area: true, max: 300 }) + errBox()
        + acts(btn('v2pmGo', 'أنشئ الرابط', 'v2p-btn1'), btn('v2pmBack', 'رجوع')),
        wire: function (root) {
          q('#v2pmBack', root).onclick = function () { backOrClose(back); };
          q('#v2pmGo', root).onclick = function () {
            var name = q('#v2pmName', root).value.trim(), phone = q('#v2pmPhone', root).value.trim(), mail = q('#v2pmMail', root).value.trim(), note = q('#v2pmNote', root).value.trim();
            var er = q('.v2pm-err', root);
            if (name.length < 2) { er.textContent = 'اكتب اسم صاحب الدعوة'; return; }
            if (!phoneOk(phone)) { er.textContent = 'اكتب رقم واتساب صالحًا (٨ أرقام على الأقل)'; return; }
            runBtn(root, this, function () { return PX.call({ path: '/invites', body: { name: name, email: mail, phone: phone, note: note }, reload: ['invites'] }); },
              function (res) { var r = res.data || {}; linkScreen(name, r.link || r.invite_url || (r.invite && (r.invite.link || r.invite.invite_url)) || '', phone); });
          };
        } };
    } };
    showScreen(sc);
  }
  function phoneScreen(w) {
    var known = phoneOk(w.phone);
    showScreen({ title: 'رقم واتساب لصاحب الدعوة', build: function () {
      return { html: '<p class="v2pm-lead">' + (known ? 'هذا الرقم المكتوب في الطلب. تُربط الدعوة به ولا يفتحها غيره. أكّده أو عدّله.' : 'لا يوجد رقم واتساب صالح في الطلب. اكتب الرقم الذي سترسل عليه الدعوة.') + '</p>'
        + fld('رقم واتساب', 'v2pmPhone', { value: w.phone, type: 'tel', ltr: true, mode: 'tel' }) + errBox() + acts(btn('v2pmGo', 'أنشئ الرابط', 'v2p-btn1'), btn('v2pmBack', 'رجوع')),
        wire: function (root) {
          q('#v2pmBack', root).onclick = closeSheet;
          q('#v2pmGo', root).onclick = function () {
            var phone = q('#v2pmPhone', root).value.trim();
            if (!phoneOk(phone)) { q('.v2pm-err', root).textContent = 'اكتب رقم واتساب صالحًا (٨ أرقام على الأقل)'; return; }
            runBtn(root, this, function () { return PX.call({ path: '/waitlist/' + encodeURIComponent(w.id) + '/invite', body: { phone: phone }, reload: ['waitlist', 'invites'] }); },
              function (res) { var r = res.data || {}; linkScreen(w.name, r.link || r.invite_url || (r.invite && (r.invite.link || r.invite.invite_url)) || '', phone); });
          };
        } };
    } });
  }
  function rejectInviteScreen(r, back) {
    confirmScreen({ title: 'رفض دعوة', lead: 'سيُرفض طلب دعوة ' + (r.name || 'صاحب الدعوة') + '. لن يعمل الرابط، ولن تُحسب من حصة الداعي.', back: back, label: 'ارفض الدعوة', danger: true,
      body: fld('سبب الرفض — يقرؤه الداعي كما تكتبه (اختياري)', 'v2pmReason', { area: true, max: 300 }),
      run: function (root) { return PX.call({ path: '/invites/' + encodeURIComponent(r.id) + '/reject', body: { note: q('#v2pmReason', root).value.trim() }, reload: ['invites'] }); } });
  }
  function revokeScreen(r, back) {
    confirmScreen({ title: 'سحب دعوة', lead: 'ستُسحب دعوة ' + (r.name || 'صاحب الدعوة') + '. يتوقف الرابط ولا يمكن إنشاء حساب به. يمكنك إرسال دعوة جديدة في أي وقت.', back: back, label: 'اسحب الدعوة', danger: true,
      run: function () { return PX.call({ path: '/invites/' + encodeURIComponent(r.id) + '/revoke', body: {}, reload: ['invites'] }); } });
  }
  function reissueScreen(r, back) {
    confirmScreen({ title: 'إعادة إصدار الدعوة', lead: 'سيُنشأ رابط جديد لـ' + (r.name || 'صاحب الدعوة') + ' بمهلة جديدة، وتبدأ الرحلة من أولها. يبقى الرابط القديم متوقفًا، فأرسل الجديد بنفسك.', back: back, label: 'أعِد إصدارها',
      run: function () { return PX.call({ path: '/invites/' + encodeURIComponent(r.id) + '/reissue', body: {}, reload: ['invites'] }); },
      onOk: function (res) { var d = res.data || {}; linkScreen(r.name, d.link || d.invite_url || (d.invite && (d.invite.link || d.invite.invite_url)) || '', r.phone || ''); } });
  }
  var VERDICT = { correct: 'صحيحة', partly: 'ناقصة', wrong: 'خاطئة' };
  var TL = { created: 'إنشاء الدعوة', opened: 'فتح الرابط', email_bound: 'كتابة البريد', pain_seen: 'مشاهدة التعريف', exercised: 'تجربة المثال', declared: 'الموافقة على الشروط', registered: 'الانضمام' };
  var ROLE_AR = { trainer: 'مدرّب', lawyer: 'محامٍ', consultant: 'مستشار', researcher: 'باحث', graduate: 'خريج' };
  function demoHtml(demo) {
    demo = demo || {};
    var tr = Array.isArray(demo.transcript) ? demo.transcript : [];
    if (!tr.length) return '<p class="v2pm-mute">لم يبدأ المثال بعد</p>';
    var bubbles = tr.slice(0, 12).map(function (m) {
      var ai = !!(m && m.who === 'ai');
      return '<div class="v2pm-bub' + (ai ? ' ai' : '') + '"><small>' + (ai ? 'المساعد' : 'صاحب الدعوة') + (ai && m.ai_source === 'fallback' ? ' (إجابة جاهزة)' : '') + '</small><span>' + esc(String((m && m.text) || '').slice(0, 160)) + '</span></div>';
    }).join('');
    var dc = demo.documented || null, h = kvRows([['السؤال', dash(demo.question)]]) + '<div class="v2pm-bubs">' + bubbles + '</div>';
    if (dc && dc.mode === 'request') h += kvRows([['طلب توثيق من خبير', 'نعم'], ['ملاحظة للخبير', dash(dc.notes)], ['الاقتراح', dash(dc.proposal)]]);
    else if (dc) h += kvRows([['الإجابة المعتمدة', dash(dc.final_text)], ['الحكم', VERDICT[dc.verdict] || ''], ['التصحيح', dash(dc.notes)], ['الاقتراح', dash(dc.proposal)]]);
    return h;
  }
  function inviteActions(r) {
    var st = r.stage, a = [];
    var link = safeHttps(r.link), phone = r.phone || '';
    if (st === 'awaiting_approval') { a.push(btn('v2pmAp', 'وافق على الدعوة', 'v2p-btn1')); a.push(btn('v2pmRj', 'ارفض')); return a.join(''); }
    if (st === 'pending' && link) { a.push(btn('v2pmCopy', 'انسخ الرابط', 'v2p-btn1')); a.push('<a class="v2p-btn2" target="_blank" rel="noopener" href="' + esc(P.waUrl(phone, P.waText('invite', r.name, link))) + '">أرسل عبر واتساب</a>'); }
    if (['opened', 'roles_chosen', 'pain_seen', 'exercised', 'declared'].indexOf(st) > -1 && link) a.push('<a class="v2p-btn1" target="_blank" rel="noopener" href="' + esc(P.waUrl(phone, P.waText('remind', r.name, link))) + '">ذكّر عبر واتساب</a>');
    if (st === 'registered' && r.email) a.push(btn('v2pmPerson', 'افتح صفحة الشخص', 'v2p-btn1'));
    var live = ['pending', 'opened', 'roles_chosen', 'pain_seen', 'exercised', 'declared'].indexOf(st) > -1;
    if (live) a.push(btn('v2pmRevoke', 'اسحب الدعوة', 'v2p-btn3'));
    if (['expired', 'revoked', 'rejected'].indexOf(st) > -1 && !r.registered) a.push(btn('v2pmReissue', 'أعِد إصدارها', 'v2p-btn1'));
    return a.join('');
  }
  function inviteScreen(r) {
    var E = ep(), state = { loading: r.stage !== 'pending', d: null, err: '' };
    var sc = { title: r.name || 'بلا اسم', side: true, build: function () {
      var h = '';
      if (r.stage === 'pending') h = '<p class="v2pm-mute">لا تفاصيل بعد — لم يُفتح الرابط</p>' + kvRows([['البريد', r.email, true], ['الداعي', dash(r.invitedByLabel)], ['الصفات', dash(r.rolesLabel)], ['التخصص', dash(r.specialtyLabel)]]);
      else if (state.loading) h = '<p class="v2pm-mute">…جارٍ جلب التفاصيل</p>';
      else if (state.err === 'missing') h = '<p class="v2pm-mute">التفاصيل غير متاحة بعد من المنصة</p>';
      else if (state.err) h = '<p class="v2pm-err" style="display:block">تعذّر جلب التفاصيل</p>' + btn('v2pmRetry', 'أعد المحاولة');
      else {
        var d = state.d || {}, inv = d.inviter || null, usr = d.user || null;
        var inviter = inv ? (inv.kind === 'founder' ? 'المؤسس' : dash(inv.name)) : dash(r.invitedByLabel);
        var gen = d.generation != null ? d.generation : r.generation;
        h = kvRows([['البريد', r.email || d.email, true], ['الهاتف', usr && usr.phone, true], ['الداعي', inviter], ['الصفات', dash(r.rolesLabel)], ['التخصص', dash(r.specialtyLabel)],
          ['سنوات الخبرة', d.years != null ? ar(d.years) : ''], ['الجيل', gen != null ? ar(gen) : ''], ['طبيعة العمل', dash(d.focus)]]);
        var tl = Array.isArray(d.timeline) ? d.timeline : [];
        if (tl.length) h += '<h4 class="v2pm-h">الخط الزمني</h4><ul class="v2pm-tl">' + tl.map(function (t2) { return '<li><span>' + esc(TL[t2.key] || '') + '</span><time>' + esc(t2.at ? fmtWhen(t2.at) : '') + '</time></li>'; }).join('') + '</ul>';
        var ex = Array.isArray(d.exercises) ? d.exercises : [], props = (Array.isArray(d.proposals) ? d.proposals : []).filter(function (p) { return p && String(p.proposal || '').trim() && !ex.some(function (e2) { return e2.role === p.role; }); });
        var legacy = ex.length || props.length;
        if (d.demo || !legacy) h += '<h4 class="v2pm-h">المثال</h4>' + demoHtml(d.demo);
        if (legacy) h += '<h4 class="v2pm-h">التجربة</h4>' + ex.map(function (e2) {
          return '<div class="v2pm-ex">' + kvRows([[ROLE_AR[e2.role] || '', dash(e2.question)], ['إجابة المساعد', dash(e2.ai_answer) + (e2.ai_source === 'fallback' ? ' (إجابة جاهزة)' : '')], ['الحكم', VERDICT[e2.verdict] || ''], ['ملاحظاته', dash(e2.notes)], ['الاقتراح', dash(e2.proposal)]]) + '</div>';
        }).join('') + props.map(function (p) { return '<div class="v2pm-ex">' + kvRows([[ROLE_AR[p.role] || p.label || '', ''], ['الاقتراح', dash(p.proposal)]]) + '</div>'; }).join('');
        var vid = d.video_source === 'platform' ? 'فيديو المنصة' : (d.video_source === 'inviter' ? 'فيديو الداعي' : '');
        var decl = d.declaration ? 'في ' + fmtWhen(d.declaration.accepted_at) + ' — نسخة الشروط ' + (d.declaration.terms_version != null ? ar(d.declaration.terms_version) : '') : '';
        h += kvRows([['فيديو الدعوة', vid], ['الموافقة على الشروط', decl], ['صفة المؤسس', d.founding != null ? (d.founding ? 'نعم' : 'لا') : '']]);
      }
      h += errBox() + acts(inviteActions(r));
      return { html: h, wire: function (root) {
        var set = function (id, fn) { var b2 = q('#' + id, root); if (b2) b2.onclick = fn; };
        set('v2pmRetry', function () { state.loading = true; state.err = ''; showScreen(sc); load(); });
        set('v2pmCopy', function () { copyText(safeHttps(r.link), function () {}); });
        set('v2pmPerson', function () { closeSheet(); host().openPerson && host().openPerson(r.email); });
        set('v2pmRevoke', function () { revokeScreen(r, sc); });
        set('v2pmReissue', function () { reissueScreen(r, sc); });
        set('v2pmRj', function () { rejectInviteScreen(r, sc); });
        set('v2pmAp', function () { runBtn(root, q('#v2pmAp', root), function () { return PX.call({ path: '/invites/' + encodeURIComponent(r.id) + '/approve', body: {}, reload: ['invites'] }); }, closeSheet); });
      } };
    } };
    function load() {
      if (!E || !E.inviteDetail) { state.loading = false; state.err = 'missing'; return; }
      E.inviteDetail(r.id, function (d) { state.loading = false; state.d = d; if (SH.cur === sc) showScreen(sc); },
        function (e) { state.loading = false; state.err = (e && e.status === 404) ? 'missing' : 'fail'; if (SH.cur === sc) showScreen(sc); });
    }
    showScreen(sc);
    if (r.stage !== 'pending') load();
  }

  // ------------------------------------------------------------------ إعدادات الدعوة (S8)
  function settingsScreen() {
    var E = ep(), openG = '', form = {}, msg = {};
    ['founding', 'inviteSettings', 'inviteVideos'].forEach(function (k) { E.ensure(k, null); });
    var sc = { title: 'إعدادات الدعوة', side: true, build: function () {
      var F = readyData('founding'), I = readyData('inviteSettings'), V = readyData('inviteVideos');
      var fo = F && !F.missing && F.open != null ? (F.open ? 'مفتوح' : 'مغلق') : NA;
      var iq = I && !I.missing && I.member_invite_quota != null ? ar(I.member_invite_quota) : NA, ig = I && !I.missing && I.invite_approval_from_generation != null ? ar(I.invite_approval_from_generation) : NA;
      var VK = ['trainer', 'lawyer', 'consultant', 'researcher', 'graduate', 'multi'], VL = { trainer: 'مدرّب', lawyer: 'محامٍ', consultant: 'مستشار', researcher: 'باحث', graduate: 'خريج', multi: 'أكثر من صفة' };
      var vcount = V && !V.missing && !V.forbidden ? VK.filter(function (k) { return V[k]; }).length : null;
      var vline = V && V.forbidden ? 'للإدارة فقط' : (vcount == null ? NA : ar(vcount) + ' من ٦ فيديوهات مضبوطة');
      function group(key, title, line, inner) {
        var on = openG === key;
        return '<section class="v2pm-g' + (on ? ' on' : '') + '"><button type="button" class="v2pm-gh" data-g="' + key + '" aria-expanded="' + on + '"><b>' + title + '</b><span>' + esc(line) + '</span><i aria-hidden="true">' + (on ? '▴' : '▾') + '</i></button>'
          + (on ? '<div class="v2pm-gb">' + inner + okLine(msg[key]) + '<div class="v2pm-err" data-err="' + key + '" role="alert"></div></div>' : '') + '</section>';
      }
      var g1 = '<p class="v2pm-lead">ما دام الباب مفتوحًا، يحصل كل من يكمل رحلة الدعوة على صفة «مؤسس» دائمة. يمكنك إغلاقه وفتحه في أي وقت.</p>'
        + '<button type="button" class="v2p-btn1" id="v2pmFound"' + (F && !F.missing && F.open != null ? '' : ' disabled') + '>' + (F && F.open ? 'أغلق الباب' : 'افتح الباب') + '</button>';
      var iv = function (k) { return form[k] != null ? form[k] : (I && I[k] != null && I[k] !== '' ? (typeof I[k] === 'number' ? ar(I[k]) : String(I[k])) : ''); };
      var g2 = fld('فيديو الترحيب', 'v2pmF_welcome', { value: iv('welcome_video_url'), ltr: true, type: 'url', ph: 'الصق رابط الفيديو', hint: 'أول ما يراه صاحب الدعوة' })
        + fld('فيديو المنصة', 'v2pmF_platform', { value: iv('platform_video_url'), ltr: true, type: 'url', ph: 'الصق رابط الفيديو', hint: 'يظهر بعد اختيار الصفة' })
        + fld('عدد الدعوات لكل عضو', 'v2pmF_quota', { value: iv('member_invite_quota'), type: 'text', mode: 'numeric', hint: I && I.member_invite_quota != null ? '' : 'القيمة الحالية غير متاحة بعد' })
        + fld('الموافقة مطلوبة من الجيل', 'v2pmF_gen', { value: iv('invite_approval_from_generation'), type: 'text', mode: 'numeric', hint: (I && I.invite_approval_from_generation != null ? '' : 'القيمة الحالية غير متاحة بعد — ') + 'دعوات هذا الجيل وما بعده تنتظر موافقتك قبل أن يعمل رابطها' })
        + '<button type="button" class="v2p-btn1" id="v2pmSaveI">احفظ إعدادات الدعوة</button>';
      var g3 = V && V.forbidden ? '<p class="v2pm-mute">للإدارة فقط</p>' : (!V || V.missing ? '<p class="v2pm-mute">' + NA + '</p>' : VK.map(function (k) {
        return fld(VL[k], 'v2pmV_' + k, { value: form['v_' + k] != null ? form['v_' + k] : (V[k] || ''), ltr: true, type: 'url', ph: 'الصق رابط الفيديو' });
      }).join('') + '<p class="v2pm-mute">يظهر الفيديو بدل النص المكتوب لكل صفة.</p><button type="button" class="v2p-btn1" id="v2pmSaveV">احفظ الفيديوهات</button>');
      return { html: group('founding', 'باب المؤسسين', 'باب المؤسسين: ' + fo, g1) + group('invite', 'الدعوة', 'حصة العضو: ' + iq + ' · الموافقة من الجيل ' + ig, g2) + group('videos', 'فيديو لكل صفة', vline, g3), wire: function (root) {
        qa('.v2pm-gh', root).forEach(function (b2) { b2.onclick = function () { var g = b2.getAttribute('data-g'); openG = openG === g ? '' : g; showScreen(sc); }; });
        qa('input', root).forEach(function (i2) { i2.addEventListener('input', function () {
          var m = /^v2pmF_(.+)$/.exec(i2.id), mv = /^v2pmV_(.+)$/.exec(i2.id);
          var map = { welcome: 'welcome_video_url', platform: 'platform_video_url', quota: 'member_invite_quota', gen: 'invite_approval_from_generation' };
          if (m) form[map[m[1]]] = i2.value; if (mv) form['v_' + mv[1]] = i2.value;
        }); });
        var setErr = function (g, t) { var e = q('[data-err="' + g + '"]', root); if (e) e.textContent = t; };
        var fb = q('#v2pmFound', root);
        if (fb) fb.onclick = function () {
          var open = !(F && F.open);
          confirmScreen({ title: 'تأكيد التغيير', lead: open ? 'سيُفتح باب المؤسسين: كل من يكمل رحلة الدعوة يحصل على صفة «مؤسس» دائمة.' : 'سيُغلق باب المؤسسين: لن يحصل من يكمل الرحلة بعد الآن على صفة «مؤسس».', label: open ? 'افتح الباب' : 'أغلق الباب', back: sc,
            run: function () { return PX.call({ path: '/settings/founding', body: { open: open }, reload: ['founding'] }); }, onOk: function (res, back) { msg.founding = 'حُفظ'; showScreen(sc); } });
        };
        var si = q('#v2pmSaveI', root);
        if (si) si.onclick = function () {
          var body = {}, cur = I || {};
          var wv = (form.welcome_video_url != null ? form.welcome_video_url : null), pv = (form.platform_video_url != null ? form.platform_video_url : null);
          if (wv != null && wv.trim() !== (cur.welcome_video_url || '')) { if (wv.trim() && !safeHttps(wv)) return setErr('invite', 'رابط فيديو الترحيب غير صالح'); body.welcome_video_url = wv.trim(); }
          if (pv != null && pv.trim() !== (cur.platform_video_url || '')) { if (pv.trim() && !safeHttps(pv)) return setErr('invite', 'رابط فيديو المنصة غير صالح'); body.platform_video_url = pv.trim(); }
          if (form.member_invite_quota != null && form.member_invite_quota.trim() !== '') {
            var n1 = Number(toLatin(form.member_invite_quota).trim());
            if (!(n1 >= 0) || n1 !== Math.floor(n1)) return setErr('invite', 'عدد الدعوات لكل عضو رقم صحيح من صفر فأكثر');
            if (n1 !== cur.member_invite_quota) body.member_invite_quota = n1;
          }
          if (form.invite_approval_from_generation != null && form.invite_approval_from_generation.trim() !== '') {
            var n2 = Number(toLatin(form.invite_approval_from_generation).trim());
            if (!(n2 >= 1) || n2 !== Math.floor(n2)) return setErr('invite', 'الجيل رقم صحيح من واحد فأكثر');
            if (n2 !== cur.invite_approval_from_generation) body.invite_approval_from_generation = n2;
          }
          if (!Object.keys(body).length) return setErr('invite', 'لم يتغيّر شيء');
          setErr('invite', '');
          runBtn(root, si, function () { return PX.call({ path: '/settings/invites', body: body, reload: ['inviteSettings'] }); }, function () { form = {}; msg.invite = 'حُفظ'; showScreen(sc); });
        };
        var sv = q('#v2pmSaveV', root);
        if (sv) sv.onclick = function () {
          var body = {}, cur = V || {};
          var bad = false;
          ['trainer', 'lawyer', 'consultant', 'researcher', 'graduate', 'multi'].forEach(function (k) {
            var val = form['v_' + k]; if (val == null) return; val = val.trim();
            if (val !== (cur[k] || '')) { if (val && !safeHttps(val)) bad = true; body[k] = val; }
          });
          if (bad) return setErr('videos', 'رابط فيديو غير صالح');
          if (!Object.keys(body).length) return setErr('videos', 'لم يتغيّر شيء');
          setErr('videos', '');
          runBtn(root, sv, function () { return PX.call({ path: '/settings/invite-videos', body: body, reload: ['inviteVideos'] }); }, function () { form = {}; msg.videos = 'حُفظ'; showScreen(sc); });
        };
      } };
    } };
    showScreen(sc);
    var sig0 = ['founding', 'inviteSettings', 'inviteVideos'].map(stateOf).join(',');
    var t = setInterval(function () {
      if (SH.cur !== sc || !document.getElementById('epModal')) { clearInterval(t); return; }
      var sig = ['founding', 'inviteSettings', 'inviteVideos'].map(stateOf).join(',');
      if (sig !== sig0) { sig0 = sig; if (!document.activeElement || !/^(INPUT|TEXTAREA)$/.test(document.activeElement.tagName)) showScreen(sc); }
    }, 500);
  }

  // ------------------------------------------------------------------ حذف نهائي (S9) · إلغاء اعتماد مدرّب (S15)
  function purgeScreen(u, back) {
    var E = ep(), st = { loading: true, res: null, err: false };
    var sc = { title: 'حذف حساب ' + (u.name || '') + ' نهائيًا', build: function () {
      var h;
      if (st.loading) h = '<p class="v2pm-mute">جارٍ التحقق…</p>' + acts(btn('v2pmBack', 'رجوع'));
      else if (st.err) h = '<p class="v2pm-warn">تعذّر التحقق الآن، ولا يمكن الحذف قبل التحقق.</p>' + acts(btn('v2pmRetry', 'أعد المحاولة'), btn('v2pmBack', 'رجوع'));
      else if (st.res.purgeable) h = '<p class="v2pm-lead">لا بيانات مرتبطة بهذا الحساب. الحذف نهائي ولا رجوع فيه.</p>' + fld('اكتب كلمة «احذف» للتأكيد', 'v2pmWord', {}) + errBox()
        + acts('<button type="button" class="v2p-btn1 danger" id="v2pmGo" disabled>احذف نهائيًا</button>', btn('v2pmBack', 'رجوع'));
      else h = '<p class="v2pm-warn">لا يمكن الحذف النهائي. السبب: ' + esc(st.res.reason || 'توجد بيانات مرتبطة بالحساب') + '</p>' + errBox()
        + acts(u.email ? btn('v2pmHide', 'أخفِ الحساب كتجريبي بدلًا من ذلك', 'v2p-btn1') : '', btn('v2pmBack', 'رجوع'));
      return { html: h, wire: function (root) {
        q('#v2pmBack', root).onclick = function () { backOrClose(back); };
        var rt = q('#v2pmRetry', root); if (rt) rt.onclick = function () { st.loading = true; st.err = false; showScreen(sc); check(); };
        var w = q('#v2pmWord', root), go = q('#v2pmGo', root);
        if (w) w.addEventListener('input', function () { go.disabled = w.value.trim() !== 'احذف'; });
        if (go) go.onclick = function () {
          runBtn(root, go, function () { return PX.call({ path: '/users/' + encodeURIComponent(u.id) + '/purge', body: { note: '' }, reload: ['users', 'pendingUsers', 'inbox'] }); },
            function () { closeSheet(); if (host().current && host().current() === 'v2person') host().openSection('people', 'users'); });
        };
        var hide = q('#v2pmHide', root);
        if (hide) hide.onclick = function () { runBtn(root, hide, function () { return PX.call({ path: '/platform-users/' + encodeURIComponent(u.id) + '/flag-test', body: { is_test: true, email: u.email || '' }, reload: ['users'] }); }, closeSheet); };
      } };
    } };
    function check() {
      E.purgeCheck(u.id).then(function (res) { st.loading = false; st.res = res; if (SH.cur === sc) showScreen(sc); })
        .catch(function () { st.loading = false; st.err = true; if (SH.cur === sc) showScreen(sc); });
    }
    showScreen(sc); check();
  }
  function trainerScreen(u, back, onDone) {
    var name = u.full_name || u.name || u.email || '';
    confirmScreen({ title: 'إلغاء اعتماد ' + name + ' كمدرّب', back: back, label: 'ألغِ الاعتماد', danger: true, disabled: true,
      body: '<ul class="v2pm-ul"><li>يُلغى الاعتماد مدرّبًا وخبيرًا</li><li>تُسحب صلاحية تقديم العروض</li><li>يُفرَّغ الملف العام من الدليل</li><li>الحساب نفسه لا يُحذف</li></ul>'
        + fld('اكتب البريد للتأكيد: ' + (u.email || ''), 'v2pmEm', { ltr: true }) + '<label class="v2pm-chk"><input type="checkbox" id="v2pmTest" checked> إخفاء الحساب كتجريبي أيضًا</label>'
        + fld('السبب (اختياري، يُحفظ في السجل)', 'v2pmWhy', { max: 300 }),
      wire: function (root) { var go = q('#v2pmGo', root), em = q('#v2pmEm', root); em.addEventListener('input', function () { go.disabled = em.value.trim().toLowerCase() !== String(u.email || '').toLowerCase(); }); },
      run: function (root) { return PX.call({ path: '/platform-trainers/' + encodeURIComponent(u.id) + '/deactivate', body: { reason: q('#v2pmWhy', root).value.trim(), is_test: q('#v2pmTest', root).checked, email: u.email || '' }, reload: ['users', 'experts'] }); },
      onOk: function (res, bk) { if (onDone) onDone(); else closeSheet(); } });
  }

  // ------------------------------------------------------------------ إدارة الحساب (S13) — بابها الوحيد صفحة الشخص
  function metricsCustomers() { var m = dataOf('metrics'); return (eff('dashboard') === 'ready' && m && m.raw && m.raw.customers) ? m.raw.customers : null; }
  function manageScreen(u0, fromSearch) {
    var E = ep(); ['users', 'dashboard', 'packages'].forEach(function (k) { E.ensure(k, null); });
    var u = Object.assign({}, u0), msg = {}, moreOpen = false, tagsVal = null, planVal = null;
    var sc = { title: 'إدارة الحساب', side: true, build: function () {
      var raw = usersRaw() || [], m = metricsCustomers();
      var trunc = fromSearch ? true : (m && typeof m.total === 'number' ? m.total > raw.length : raw.length >= 500);
      var guard = P.adminGuard(u, m, raw, trunc);
      var name = u.full_name || u.name || u.email || '—';
      var pk = dataOf('packages') && eff('packages') === 'ready' ? dataOf('packages').packages : null;
      var planName = P.planLabel(u.plan_id, pk);
      var tags = Array.isArray(u.tags) ? u.tags : [];
      var head = '<div class="v2pm-uh"><span class="v2p-av">' + esc(String(name).charAt(0).toUpperCase()) + '</span><div><b>' + esc(name) + '</b><div class="v2p-uch">'
        + '<span class="v2p-ch2 k-' + esc(u.role || 'member') + '">' + esc(P.ROLE[u.role] || 'عضو') + '</span>' + (u.trainer_status === 'approved' ? '<span class="v2p-ch2 k-trainer">مدرّب</span>' : '') + (u.is_test ? '<span class="v2p-ch2 k-test">تجريبي</span>' : '') + (u.is_active === false ? '<span class="v2p-ch2 k-off">موقوف</span>' : '') + '</div>'
        + '<span class="v2p-em">' + esc(u.email || '') + '</span>' + (u.phone ? '<span class="v2p-em">' + esc(u.phone) + '</span>' : '')
        + '<span class="v2p-um">' + esc('انضمّ ' + (U.dateText(u.created_at) || NA) + ' · آخر دخول ' + (u.last_login_at ? U.agoText(u.last_login_at, now()) : 'غير متاح')) + '</span></div></div>';
      var roleBtns = ['admin', 'staff', 'member', 'investor'].map(function (r) {
        var cur = u.role === r, dis = guard.locked && !cur;
        return '<button type="button" class="v2pm-rb' + (cur ? ' on' : '') + '" data-role="' + r + '"' + (dis ? ' disabled' : '') + ' aria-pressed="' + cur + '">' + esc(P.ROLE[r]) + '</button>';
      }).join('');
      var part1 = '<section class="v2pm-part"><h4>الدور</h4><div class="v2pm-seg4" role="group">' + roleBtns + '</div>' + (guard.locked ? '<p class="v2pm-warn">' + esc(guard.note) + '</p>' : '') + okLine(msg.role) + '<div class="v2pm-err" data-err="role" role="alert"></div></section>';
      var trainerH = '';
      if (u.trainer_status === 'approved') trainerH = '<button type="button" class="v2p-btn3" id="v2pmTr">إلغاء اعتماد المدرّب</button>';
      else if (u.trainer_status === 'pending') trainerH = '<p class="v2pm-lead">طلب اعتماد مدرّب قيد المراجعة في «الدورات والمدرّبون»</p><button type="button" class="v2p-link" id="v2pmTrGo">افتح «الدورات والمدرّبون»</button>';
      var part2 = '<section class="v2pm-part"><h4>الظهور والمدرّب</h4><button type="button" class="v2p-btn2" id="v2pmVis">' + (u.is_test ? 'أعِد إظهار الحساب' : 'أخفِ الحساب من الواجهات العامة (تجريبي)') + '</button>' + trainerH + okLine(msg.vis) + '<div class="v2pm-err" data-err="vis" role="alert"></div></section>';
      var planOpts = Array.isArray(pk) ? pk.map(function (p2) { return '<option value="' + esc(p2.id) + '"' + ((planVal || u.plan_id) === p2.id ? ' selected' : '') + '>' + esc(p2.name || p2.id) + '</option>'; }).join('') : '';
      var planH = Array.isArray(pk) ? '<div class="v2pm-fld"><label for="v2pmPlan" class="v2p-sr">الباقة</label><select id="v2pmPlan">' + planOpts + '</select></div><button type="button" class="v2p-btn2" id="v2pmPlanGo">احفظ الباقة</button>' + okLine(msg.plan)
        : '<p class="v2pm-mute">الباقات غير متاحة بعد</p>';
      var more = '<div class="v2pm-more"><div class="v2pm-sub"><h5>الباقة</h5>' + planH + '<button type="button" class="v2p-link" id="v2pmPrices">الأسعار والخصومات في «الفلوس»</button><div class="v2pm-err" data-err="plan" role="alert"></div></div>'
        + '<div class="v2pm-sub"><h5>الوسوم</h5>' + fld('وسوم يدوية — افصل بينها بفاصلة', 'v2pmTags', { value: tagsVal != null ? tagsVal : tags.join('، ') }) + '<button type="button" class="v2p-btn2" id="v2pmTagsGo">احفظ الوسوم</button>' + okLine(msg.tags)
        + (SEGLABEL(u.segment) ? '<p class="v2pm-mute">تصنيف المحادثة: ' + esc(SEGLABEL(u.segment)) + ' — يُحدَّد تلقائيًا ولا يُعدَّل من هنا</p>' : '') + '<div class="v2pm-err" data-err="tags" role="alert"></div></div>'
        + '<div class="v2pm-sub"><h5>الحذف</h5><button type="button" class="v2p-btn3" id="v2pmDel">احذف الحساب نهائيًا</button></div></div>';
      var summ = 'الباقة: ' + planName + ' · ' + (tags.length ? U.U(tags.length, ['وسم واحد', 'وسمان', 'وسوم', 'وسمًا']) : 'بلا وسوم');
      var part3 = '<section class="v2pm-part"><button type="button" class="v2pm-gh" id="v2pmMore" aria-expanded="' + moreOpen + '"><b>المزيد</b><span>' + esc(summ) + '</span><i aria-hidden="true">' + (moreOpen ? '▴' : '▾') + '</i></button>' + (moreOpen ? more : '') + '</section>';
      return { html: head + part1 + part2 + part3, wire: function (root) {
        var setErr = function (k, t) { var e = q('[data-err="' + k + '"]', root); if (e) e.textContent = t; };
        qa('.v2pm-rb', root).forEach(function (b2) { b2.onclick = function () {
          var nr = b2.getAttribute('data-role'); if (nr === u.role || b2.disabled) return;
          confirmScreen({ title: 'تأكيد التغيير', lead: 'تغيير الدور من ' + (P.ROLE[u.role] || 'عضو') + ' إلى ' + P.ROLE[nr], back: sc, label: 'أكّد',
            run: function () { return PX.call({ path: '/platform-users/' + encodeURIComponent(u.id) + '/role', body: { role: nr, email: u.email || '' }, reload: ['users', 'dashboard'] }); },
            onOk: function () { u.role = nr; msg = { role: 'حُفظ' }; showScreen(sc); } });
        }; });
        q('#v2pmVis', root).onclick = function () {
          var to = !u.is_test;
          confirmScreen({ title: 'تأكيد التغيير', lead: to ? 'يختفي الحساب من كل الواجهات العامة، وتبقى بياناته كما هي.' : 'يعود الحساب إلى الظهور في الواجهات العامة.', back: sc, label: 'أكّد',
            run: function () { return PX.call({ path: '/platform-users/' + encodeURIComponent(u.id) + '/flag-test', body: { is_test: to, email: u.email || '' }, reload: ['users'] }); },
            onOk: function () { u.is_test = to; msg = { vis: 'حُفظ' }; showScreen(sc); } });
        };
        var tr = q('#v2pmTr', root); if (tr) tr.onclick = function () { trainerScreen(u, sc, function () { u.trainer_status = 'none'; u.is_test = true; msg = { vis: 'حُفظ' }; showScreen(sc); }); };
        var trg = q('#v2pmTrGo', root); if (trg) trg.onclick = function () { closeSheet(); host().openSection && host().openSection('courses', 'trainers'); };
        q('#v2pmMore', root).onclick = function () { moreOpen = !moreOpen; showScreen(sc); };
        var pg = q('#v2pmPrices', root); if (pg) pg.onclick = function () { closeSheet(); host().openSection && host().openSection('money', 'prices'); };
        var pl = q('#v2pmPlan', root); if (pl) pl.addEventListener('change', function () { planVal = pl.value; });
        var plg = q('#v2pmPlanGo', root);
        if (plg) plg.onclick = function () {
          var to = q('#v2pmPlan', root).value; if (to === u.plan_id) return setErr('plan', 'لم يتغيّر شيء');
          confirmScreen({ title: 'تأكيد التغيير', lead: 'من ' + planName + ' إلى ' + P.planLabel(to, pk) + '. لا يُحصَّل أي مبلغ بهذا التغيير.', back: sc, label: 'أكّد',
            run: function () { return PX.call({ path: '/platform-users/' + encodeURIComponent(u.id) + '/plan', body: { plan_id: to }, reload: ['users'] }); },
            onOk: function () { u.plan_id = to; planVal = null; msg = { plan: 'حُفظ' }; showScreen(sc); } });
        };
        var tg = q('#v2pmTags', root); if (tg) tg.addEventListener('input', function () { tagsVal = tg.value; });
        var tgg = q('#v2pmTagsGo', root);
        if (tgg) tgg.onclick = function () {
          var list = q('#v2pmTags', root).value.split(/[،,]/).map(function (x) { return x.trim(); }).filter(Boolean).slice(0, 20);
          setErr('tags', '');
          runBtn(root, tgg, function () { return PX.call({ path: '/platform-users/' + encodeURIComponent(u.id) + '/tags', body: { tags: list }, reload: ['users'] }); }, function () { u.tags = list; tagsVal = null; msg = { tags: 'حُفظ' }; moreOpen = true; showScreen(sc); });
        };
        var dl = q('#v2pmDel', root); if (dl) dl.onclick = function () { purgeScreen({ id: u.id, name: name, email: u.email }, sc); };
      } };
    } };
    showScreen(sc);
  }
  function SEGLABEL(k) { return P.SEG[k] || ''; }
  // الباب الوحيد: زرّ «إدارة الحساب» في ترويسة صفحة الشخص (D2 يستدعي manageBtn).
  function manageBtn(email) {
    return '<button type="button" class="v2d-btn2" data-v2p-manage="' + esc(email) + '">إدارة الحساب</button><p class="v2d-fine v2p-nouser" data-v2p-msg hidden>لا يوجد حساب بهذا البريد على المنصة</p>';
  }
  function findUserByEmail(email, cb) {
    var raw = usersRaw(), em = String(email || '').toLowerCase();
    if (raw) { for (var i = 0; i < raw.length; i++) if (String(raw[i].email || '').toLowerCase() === em) return cb(raw[i], false); }
    PX.read('/platform-users?search=' + encodeURIComponent(em.slice(0, 80))).then(function (r) {
      var list = (r && Array.isArray(r.users)) ? r.users : [], hit = null;
      list.forEach(function (x) { if (String(x.email || '').toLowerCase() === em) hit = x; });
      cb(hit, true);
    }).catch(function () { cb(null, true); });
  }
  document.addEventListener('click', function (e) {
    var b = e.target && e.target.closest ? e.target.closest('[data-v2p-manage]') : null;
    if (!b || !window.V2_ON) return;
    e.preventDefault();
    var email = b.getAttribute('data-v2p-manage'), msg = b.parentNode ? b.parentNode.querySelector('[data-v2p-msg]') : null;
    if (msg) msg.hidden = true;
    var E = ep(); if (E && E.authed) ['users', 'dashboard', 'packages'].forEach(function (k) { E.ensure(k, null); });
    findUserByEmail(email, function (u, viaSearch) { if (u) manageScreen(u, viaSearch); else if (msg) msg.hidden = false; });
  });

  // ------------------------------------------------------------------ فلتر المستخدمين (S18)
  function filterScreen() {
    var tmp = { role: S.users.filter.role, seg: S.users.filter.seg, sort: S.users.sort };
    var sc = { title: 'تصفية الحسابات', side: true, build: function () {
      var UV = S.uv || { filterOptions: { roles: [], segs: [] } };
      var roles = '<button type="button" class="v2pm-rb' + (!tmp.role ? ' on' : '') + '" data-role="">الكل</button>' + UV.filterOptions.roles.map(function (r) {
        return '<button type="button" class="v2pm-rb' + (tmp.role === r.key ? ' on' : '') + '" data-role="' + r.key + '">' + esc(r.label) + (r.n != null ? ' (' + esc(ar(r.n)) + ')' : '') + '</button>'; }).join('');
      var segs = '<option value="">كل التصنيفات</option>' + UV.filterOptions.segs.map(function (s2) { return '<option value="' + esc(s2.key) + '"' + (tmp.seg === s2.key ? ' selected' : '') + '>' + esc(s2.label) + ' (' + esc(ar(s2.n)) + ')</option>'; }).join('');
      var h = '<section class="v2pm-part"><h4>الصفة</h4><div class="v2pm-seg4 wrap" role="group">' + roles + '</div></section>'
        + '<section class="v2pm-part"><h4>التصنيف</h4><div class="v2pm-fld"><select id="v2pmSeg" aria-label="التصنيف">' + segs + '</select></div></section>'
        + '<section class="v2pm-part"><h4>الترتيب</h4><div class="v2pm-seg4" role="group"><button type="button" class="v2pm-rb' + (tmp.sort !== 'login' ? ' on' : '') + '" data-sort="new">الأحدث انضمامًا</button><button type="button" class="v2pm-rb' + (tmp.sort === 'login' ? ' on' : '') + '" data-sort="login">آخر دخول</button></div></section>'
        + acts(btn('v2pmApply', 'اعرض النتائج', 'v2p-btn1'), btn('v2pmClear', 'امسح التصفية'));
      return { html: h, wire: function (root) {
        qa('[data-role]', root).forEach(function (b2) { b2.onclick = function () { tmp.role = b2.getAttribute('data-role') || null; showScreen(sc); }; });
        qa('[data-sort]', root).forEach(function (b2) { b2.onclick = function () { tmp.sort = b2.getAttribute('data-sort'); showScreen(sc); }; });
        q('#v2pmSeg', root).onchange = function () { tmp.seg = this.value || null; };
        q('#v2pmApply', root).onclick = function () { S.users.filter = { role: tmp.role, seg: tmp.seg }; S.users.sort = tmp.sort; if (tmp.role) S.users.chip = 'all'; S.users.limit = 50; closeSheet(); refreshUsers(); };
        q('#v2pmClear', root).onclick = function () { S.users.filter = { role: null, seg: null }; S.users.sort = 'new'; closeSheet(); refreshUsers(); };
      } };
    } };
    showScreen(sc);
  }

  // ------------------------------------------------------------------ الرسائل: رد · حذف · إنهاء
  function openMail(email, text) {
    try { var a = document.createElement('a'); a.href = 'mailto:' + encodeURIComponent(email).replace(/%40/g, '@') + '?subject=' + encodeURIComponent('ردًّا على رسالتك — البروفيسور') + '&body=' + encodeURIComponent(text); a.rel = 'noopener'; document.body.appendChild(a); a.click(); a.remove(); } catch (e) {}
  }
  function replyScreen(t) {
    var m = t.ref || {};
    showScreen({ title: 'الرد على ' + (t.title || ''), build: function () {
      return { html: '<blockquote class="v2pm-quote">' + (m.topic ? '<b>' + esc(m.topic) + '</b>' : '') + '<span>' + esc(m.body || '') + '</span></blockquote>' + fld('نص الرد', 'v2pmReply', { area: true, max: 4000 })
        + '<p class="v2pm-mute">يُحفظ ردك هنا وتُعلَّم الرسالة «تم الرد»، ثم يُفتح بريدك والنص جاهز للإرسال.</p>' + errBox() + acts('<button type="button" class="v2p-btn1" id="v2pmGo" disabled>احفظ وافتح البريد</button>', btn('v2pmBack', 'رجوع')),
        wire: function (root) {
          var ta = q('#v2pmReply', root), go = q('#v2pmGo', root);
          ta.addEventListener('input', function () { go.disabled = !ta.value.trim(); });
          q('#v2pmBack', root).onclick = closeSheet;
          go.onclick = function () {
            var text = ta.value.trim();
            runBtn(root, go, function () { return PX.call({ path: '/messages/' + encodeURIComponent(t.rid) + '/reply', body: { body: text }, reload: ['messages', 'inbox'] }); },
              function () { if (t.email) openMail(t.email, text); closeSheet(); });
          };
        } };
    } });
  }
  function deleteMsgScreen(t) {
    confirmScreen({ title: 'حذف رسالة', lead: 'ستُحذف رسالة ' + (t.title || t.name || '') + ' نهائيًا.', label: 'احذف', danger: true, back: null,
      run: function () { return PX.call({ path: '/messages/' + encodeURIComponent(t.rid) + '', method: 'DELETE', reload: ['messages', 'inbox'] }); } });
  }
  function resolveMsg(id) {
    var t = S.items[id], E = ep(); if (!t || !E || S.busy[id]) return;
    S.busy[id] = true; S.err[id] = ''; redraw(true);
    Promise.resolve(E.resolveInboxItem({ apiKind: t.src === 'chat' ? 'message' : 'lead', apiId: t.rid })).then(function (res) {
      res = res || {}; S.busy[id] = false;
      if (res.ok) { S.done[id] = t.src === 'follow' ? 'تمت المتابعة' : 'عُلّمت منتهية'; delete S.sent[id]; loadOwn(true); }
      else S.err[id] = res.error ? resErr(res) : FAIL_AR;
      redraw(true);
    }).catch(function () { S.busy[id] = false; S.err[id] = FAIL_AR; redraw(true); });
  }

  // ------------------------------------------------------------------ قرارات التذاكر
  function finishTicket(id, text) { S.done[id] = text; S.err[id] = ''; setTimeout(function () { delete S.done[id]; if (isCurrent()) redraw(); }, 4000); }
  function decideTicket(t, action, okText) {
    var E = ep(), id = t.id; if (!E || S.busy[id]) return;
    S.busy[id] = true; S.err[id] = ''; redraw(true);
    Promise.resolve(E.decideInboxItem(t.ref, action, null, '')).then(function (res) {
      res = res || {}; S.busy[id] = false;
      if (res.ok) finishTicket(id, okText); else S.err[id] = resErr(res);
      redraw(true);
    }).catch(function () { S.busy[id] = false; S.err[id] = FAIL_AR; redraw(true); });
  }
  function approveInvite(t) {
    var id = t.id; if (S.busy[id]) return;
    S.busy[id] = true; S.err[id] = ''; redraw(true);
    PX.call({ path: '/invites/' + encodeURIComponent(t.ref.id) + '/approve', body: {}, reload: ['invites'] }).then(function (res) {
      S.busy[id] = false;
      if (res.ok) finishTicket(id, 'اعتُمدت الدعوة — الرابط يعمل الآن'); else S.err[id] = resErr(res);
      redraw(true);
    });
  }
  var OK_TEXT = { visitor: 'فُتحت المنصة للزائر', join: 'تم قبول الطلب', founding: 'سُجّلت الخطوة' };
  function doAct(t, act) {
    if (!act) return;
    switch (act.do) {
      case 'decide': return decideTicket(t, act.action, OK_TEXT[t.kind] || 'تم');
      case 'approve_invite': return approveInvite(t);
      case 'person': return host().openPerson && host().openPerson(act.email);
      case 'copy': return copyText(t.inviteUrl || '', function (ok) { finishTicket(t.id, ok ? 'نُسخ الرابط' : 'تعذّر النسخ — انسخه يدويًا'); redraw(true); });
      case 'sheet': return openSheetFor(t, act.sheet);
    }
  }
  function openSheetFor(t, name) {
    var r = t.ref;
    switch (name) {
      case 'visitor': return visitorScreen(pendingRowOf(r.apiId, r.personEmail), r);
      case 'waitlist': return waitlistScreen(r);
      case 'phone': return phoneScreen(r);
      case 'join': return joinScreen(r);
      case 'reject_join': return rejectJoinScreen(r, null);
      case 'info_join': return infoJoinScreen(r, null);
      case 'founding': return foundingScreen(r);
      case 'reject_founding': return rejectFoundingScreen(r, null);
      case 'reject_invite': return rejectInviteScreen(r, null);
      case 'invite': return inviteScreen(Object.assign({}, r, { stage: t.stage || r.stage }));
      case 'revoke': return revokeScreen(r, null);
      case 'reissue': return reissueScreen(r, null);
      case 'reply': return replyScreen(t);
      case 'delete': return deleteMsgScreen(t);
    }
  }
  function openDetail(t) {
    if (!t) return;
    if (t.kind === 'visitor') return openSheetFor(t, 'visitor');
    if (t.kind === 'waitlist') return openSheetFor(t, 'waitlist');
    if (t.kind === 'approval') return openSheetFor(t, 'invite');
    if (t.kind === 'join') return openSheetFor(t, 'join');
    if (t.kind === 'founding') return openSheetFor(t, 'founding');
    if (t.stage) return openSheetFor(t, 'invite');
  }

  // ------------------------------------------------------------------ الأحداث
  function actOf(t, w) { if (!t) return null; var a = w === 'p' ? t.primary : (t.secondary || [])[Number(String(w).slice(1))]; return a ? a.act : null; }
  function reloadTab() {
    var tab = S.tab; reloadKeys(KEYS[tab].filter(function (k) { return k !== 'users' && k !== 'inviteSettings' && k !== 'packages'; }));
    if (tab === 'messages') loadOwn(true);
  }
  function onClick(e) {
    var view = S.view;
    if (!view || !isCurrent() || !view.contains(e.target)) return;
    var b = e.target.closest('[data-a]'); if (!b || !view.contains(b)) return;
    var a = b.getAttribute('data-a'), id = b.getAttribute('data-id');
    if (a === 'detail') { if (e.target.closest('a,button,input,select,textarea,label')) return; return openDetail(S.items[id]); }
    if (a === 'person') {
      if (e.target.closest('a[data-person]')) return;
      var em = b.getAttribute('data-email'); if (em && host().openPerson) host().openPerson(em); return;
    }
    switch (a) {
      case 'col': S.col[S.tab] = b.getAttribute('data-col'); S.picked[S.tab] = true; return redraw(true);
      case 'expand': var k = b.getAttribute('data-k'); S.expanded[k] = !S.expanded[k]; return redraw(true);
      case 'later': S.laterOpen = !S.laterOpen; return redraw(true);
      case 'retry':
        var key = b.getAttribute('data-key');
        if (key === 'chat' || key === 'follow') { loadOwn(true); } else if (key === 'site') reloadKeys(['messages']); else reloadKeys([key]);
        return;
      case 'refresh': return reloadTab();
      case 'goto-pipeline': e.preventDefault(); return host().openSection && host().openSection('people', 'pipeline');
      case 'goto-requests': e.preventDefault(); return host().openSection && host().openSection('people', 'invites');
      case 'new-invite': return newInviteScreen({}, null);
      case 'settings': return settingsScreen();
      case 'act': return doAct(S.items[id], actOf(S.items[id], b.getAttribute('data-w')));
      case 'sent': S.sent[id] = true; return void setTimeout(function () { if (isCurrent()) redraw(true); }, 80);
      case 'notyet': delete S.sent[id]; return redraw(true);
      case 'resolve': return resolveMsg(id);
      case 'msg-del': return deleteMsgScreen(S.items[id]);
      case 'later-open': return visitorScreen(pendingRowOf(id, ''), null);
      case 'later-del': var pu = pendingRowOf(id, ''); return pu && purgeScreen({ id: pu.id, name: pu.name || pu.email, email: pu.email }, null);
      case 'chip': S.users.chip = b.getAttribute('data-k'); S.users.limit = 50; return refreshUsers();
      case 'filter': return filterScreen();
      case 'unfilter':
        var fk = b.getAttribute('data-k');
        if (fk === 'role') S.users.filter.role = null; else if (fk === 'seg') S.users.filter.seg = null; else S.users.sort = 'new';
        return refreshUsers();
      case 'more-users': S.users.limit += 50; return refreshUsers();
    }
  }
  document.addEventListener('click', onClick);
  document.addEventListener('change', function (e) {
    var t = e.target;
    if (t && t.id === 'v2pinv' && S.view && S.view.contains(t)) { S.inviter = t.value || 'all'; redraw(true); }
  });

  window.V2SECT = window.V2SECT || {};
  window.V2SECT.people = { owns: owns, render: render, manageBtn: manageBtn };
  window.V2P = { _state: S, _sheets: { purge: purgeScreen, manage: manageScreen }, PX: PX };
})();
