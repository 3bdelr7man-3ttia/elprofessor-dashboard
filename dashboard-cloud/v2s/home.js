/* ============================================================================
 * v2s/home.js — «اللوحة + كل الوارد + الدرج + الجرس + الدخول» (الجولة النهائية، SPEC-home).
 * ⛔ المفتاح مقفول (أو غير أدمن) ⇒ `inbox()` و`list()` ترجعان false ولا تكتبان في الصفحة، والجرس والنصوص والسطر الصحي لا يُركَّبون:
 * الشاشة القديمة بالحرف. الاستثناء الوحيد: صنف `v2h-login` على <html> (شكل شاشة الدخول فقط).
 * ⛔ لا منطق عمل هنا: الترتيب والمطابقة والنصوص من v2-logic.js (نقي)، وكل فعل (قرار أو فلوس) يمرّ من الدرج القديم
 * ونافذة التأكيد القديمة بـ`confirmed:true`. ولا طلب شبكة هنا غير `GET /api/notifications` (قراءة) ودالة التوزيع التلقائي الموجودة.
 * مساحة الأسماء: `window.V2SEC.home` (⛔ لا `V2S`: اسم حالة الأقسام في index.html).
 * ========================================================================== */
(function () {
  'use strict';
  var NS = window.V2SEC = window.V2SEC || {};
  var H = NS.home = {};

  // —— شكل شاشة الدخول: الافتراضي الجديد، و`'0'` المخزَّنة وحدها ترجع القديم (§٨). يُنفَّذ قبل EP.start.
  try { if (localStorage.getItem('ep_v2_shell') !== '0') document.documentElement.classList.add('v2h-login'); }
  catch (e) { try { document.documentElement.classList.add('v2h-login'); } catch (e2) {} }

  var L = window.V2L;
  if (!L) return;
  var UT = L.util;

  // ------------------------------------------------------------------ أدوات
  function esc(s) { return String(s == null ? '' : s).replace(/[&<>"']/g, function (c) { return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]; }); }
  function ep() { return window.EP || null; }
  function qs(sel, root) { return (root || document).querySelector(sel); }
  function qsa(sel, root) { return Array.prototype.slice.call((root || document).querySelectorAll(sel)); }
  function mm(q) { try { return !!(window.matchMedia && window.matchMedia(q).matches); } catch (e) { return false; } }
  function narrow() { return mm('(max-width:1179px)'); }
  function mobile() { return mm('(max-width:760px)'); }
  function reduced() { return mm('(prefers-reduced-motion: reduce)'); }
  function img(n) { return 'v2/img/' + n + '.jpg'; }
  function stateOf(k) { var E = ep(); return (E && E.state && E.state[k]) || 'idle'; }
  function loadingState(k) { var s = stateOf(k); return s === 'idle' || s === 'loading'; }

  // متغيرات الحالة العامة في index.html (let/var في سكربت عادي) — تُقرأ وتُكتب بالاسم، وأي غيابها (اختبار/صفحة أخرى) لا يكسر شيئًا.
  function getSel() { try { return selected; } catch (e) { return null; } }
  function setSel(v) { try { selected = v; } catch (e) {} }
  function getFilter() { try { return activeFilter || 'all'; } catch (e) { return 'all'; } }
  function setFilter(v) { try { activeFilter = v; } catch (e) {} }
  function curMod() { try { return current; } catch (e) { return ''; } }
  function roleNow() { try { return role; } catch (e) { return ep() && ep().role; } }
  function call(name) {   // يستدعي دالة عامة من index.html إن وُجدت
    try { var f = window[name]; if (typeof f === 'function') return f.apply(null, Array.prototype.slice.call(arguments, 1)); } catch (e) {}
    return undefined;
  }
  function enabled() {
    try { return !!(window.V2_ON && window.V2SHELL && window.V2SHELL.on && roleNow() === 'admin'); } catch (e) { return false; }
  }
  function host() { return window.V2_HOST || {}; }
  function ctxNow() {
    var s = null;
    try { s = host().state && host().state(); } catch (e) {}
    var k = s && s.section;
    return k === 'files' ? 'files' : k === 'disputes' ? 'disputes' : k === 'people' ? 'messages' : 'home';
  }
  var CTX_DEFAULT = { home: 'all', files: 't:files', disputes: 't:disputes', messages: 't:messages' };
  function ar(n) { return UT.ar(n); }

  // ------------------------------------------------------------------ الحالة
  var S = H.S = { q: '', seg: null, page: 60, key: '', timer: null, sig: '', opener: null, wasOpen: false,
                  auto: { confirm: false, busy: false, err: '' }, typesOpen: false, lastCtx: '' };

  // ------------------------------------------------------------------ بيانات الوارد
  function rowsAll() { return Array.isArray(window.INBOX) ? window.INBOX : []; }
  function match(r, f) { try { return !!window.inboxMatches(r, f); } catch (e) { return true; } }
  function isLate(r) { try { return !!window.inboxIsLate(r); } catch (e) { return false; } }
  function destLabel(r) { try { var m = MODULES_LOOKUP[r.dest]; return (m && m.label) || ''; } catch (e) { return ''; } }
  function cardOf(r, now) { try { return L.v2Card(r, { now: now }) || null; } catch (e) { return null; } }
  function inboxStatus() {
    var s = stateOf('inbox');
    return s === 'error' ? 'error' : (s === 'ready' ? 'ready' : 'loading');
  }
  function failedList() { return (window.INBOX_FAILED && window.INBOX_FAILED.length) ? window.INBOX_FAILED.slice() : []; }
  function truncList() { return (window.INBOX_TRUNCATED && window.INBOX_TRUNCATED.length) ? window.INBOX_TRUNCATED.slice() : []; }
  function fyiRows() { return rowsAll().filter(function (r) { return r.fyi; }); }

  // كل بنود الفلتر الحالي (قبل البحث) ثم بعد البحث
  function build() {
    var now = Date.now(), f = getFilter(), all = rowsAll(), q = L.v2hNorm(S.q);
    var base = [], shown = [];
    all.forEach(function (r, i) {
      if (!match(r, f)) return;
      var card = cardOf(r, now), late = isLate(r);
      var it = { card: card, row: r, idx: i, late: late, tone: L.v2hTone(r, card, late) };
      base.push(it);
      if (q && L.v2hNorm(L.v2hSearchText(r, destLabel(r), card)).indexOf(q) < 0) return;
      shown.push(it);
    });
    return { now: now, filter: f, base: base, shown: shown };
  }
  function countsFor(ctx) {
    var out = {}, all = rowsAll();
    L.v2hChipKeys(ctx).forEach(function (k) { out[k] = all.filter(function (r) { return match(r, k); }).length; });
    return out;
  }

  // ------------------------------------------------------------------ الإقلاع والرسم
  H.inbox = function (v) {
    if (!enabled()) return false;
    if (curMod() !== 'inbox') return true;           // رد متأخر لا يكتب فوق شاشة أخرى
    var E = ep();
    if (E && E.ensure) {
      ['inbox', 'opsQueue', 'pendingUsers', 'escrow'].forEach(function (k) { E.ensure(k, function () { if (mounted()) softRedraw(); }); });
    }
    mount(v || qs('#view'));
    return true;
  };
  H.list = function () {
    if (!enabled() || !mounted()) return false;
    drawAll(true);
    return true;
  };
  function mounted() { return !!document.getElementById('v2hDw'); }

  var SEARCH_ICON = '<svg viewBox="0 0 24 24" class="v2h-ic" aria-hidden="true"><circle cx="11" cy="11" r="7"/><path d="m20 20-3.5-3.5"/></svg>';
  var CHEV = '<svg viewBox="0 0 24 24" class="v2h-ic" aria-hidden="true"><path d="m6 9 6 6 6-6"/></svg>';

  function mount(v) {
    if (!v) return;
    var ctx = ctxNow();
    S.lastCtx = ctx;
    v.innerHTML = '<div class="v2h" data-ctx="' + ctx + '">'
      + '<div class="v2h-top"><label class="v2h-search">' + SEARCH_ICON
      + '<input id="v2hq" type="search" autocomplete="off" placeholder="' + (mobile() ? 'ابحث في الوارد' : 'ابحث باسم صاحب الطلب أو بريده أو الخدمة') + '" aria-label="ابحث في الوارد"></label>'
      + '<button type="button" class="v2h-qlink" data-a="queue">أرقام المنصة</button></div>'
      + '<div id="v2hHead"></div>'
      + '<div class="filterbar v2h-fb" id="filters"></div>'
      + '<div class="v2h-wrap"><section class="v2h-list" aria-label="بنود الوارد"><div id="rows"></div></section>'
      + '<div class="v2h-dw" id="v2hDw"><div class="v2h-dwp"><div class="v2h-dbar"><button type="button" data-a="dclose">رجوع إلى الوارد</button></div>'
      + '<aside class="drawer" id="drawer"></aside></div></div></div>'
      + '<details class="v2h-q" id="v2hQueue"><summary></summary><div class="v2h-qgrid"></div></details>'
      + '<span id="inboxN" hidden></span>'
      + '<div class="v2h-tscrim" id="v2hTScrim"></div><div class="v2h-types" id="v2hTypes" role="dialog" aria-label="اختر النوع"></div>'
      + '</div>';
    var inp = document.getElementById('v2hq');
    inp.value = S.q;
    var t = null;
    inp.addEventListener('input', function () {
      S.q = inp.value; clearTimeout(t);
      t = setTimeout(function () { if (mounted()) softRedraw(); }, 120);
    });
    wire(v.firstChild);
    S.typesOpen = false;
    drawAll(true);
    startWatch();
  }

  function startWatch() {
    if (S.timer) return;
    S.sig = signature();
    S.timer = setInterval(function () {
      if (!mounted() || !enabled() || curMod() !== 'inbox') { clearInterval(S.timer); S.timer = null; return; }
      var s = signature();
      if (s !== S.sig) { S.sig = s; softRedraw(); }
    }, 700);
  }
  function signature() {
    return ['inbox', 'opsQueue', 'pendingUsers', 'escrow'].map(stateOf).join(',') + '|' + rowsAll().length + '|' + failedList().length + '|' + (ctxNow())
      + (window.V2BRAIN && window.V2BRAIN.sig ? '|' + window.V2BRAIN.sig() : '');
  }

  // إعادة رسم خفيفة (البحث وتحميل المصادر): الرأس والشرائح والقائمة فقط — لا نلمس الدرج لئلا يضيع ما يُكتب فيه
  function softRedraw() {
    if (!mounted()) return;
    var sel = getSel();
    if (sel !== null && !rowsAll()[sel]) { setSel(null); drawAll(true); return; }
    drawAll(false);
  }

  function drawAll(full) {
    var root = qs('.v2h'); if (!root) return;
    var ctx = ctxNow();
    if (ctx !== S.lastCtx) { root.setAttribute('data-ctx', ctx); S.lastCtx = ctx; }
    // تغيّر الفلتر/البحث/القسم ⇒ نرجع للمقطع الافتراضي وأول صفحة
    var key = getFilter() + '|' + L.v2hNorm(S.q) + '|' + ctx;
    if (key !== S.key) { S.key = key; S.seg = null; S.page = 60; }
    var b = build();
    drawHead(b, ctx);
    drawFilters(b, ctx);
    drawRows(b, ctx);
    drawQueue();
    syncSheet();
    if (full) call('drawInbox');
  }

  // ------------------------------------------------------------------ الرأس: سطر العقل والشرائط
  function strip(cls, html) { return '<div class="v2h-strip ' + cls + '">' + html + '</div>'; }
  function drawHead(b, ctx) {
    var el = document.getElementById('v2hHead'); if (!el) return;
    var st = inboxStatus(), failed = failedList(), trunc = truncList(), html = '';
    var bs = st === 'ready' && failed.length ? 'partial' : st;
    var log = [];
    try { log = L.v2BrainLog(rowsAll(), b.now) || []; } catch (e) {}
    var line = L.v2hBrainLine(b.base, (ctx === 'home' || ctx === 'files') ? log.length : 0, bs);   // توزيع العقل للملفات: لا يُذكر في شاشتي النزاعات والرسائل
    if (line) html += '<p class="v2h-bl"><img src="' + img('brain-avatar') + '" alt=""><span><b>العقل:</b> ' + esc(line) + '</span></p>';
    if (st === 'error') {
      html += strip('bad', '<span>تعذّر جلب الوارد — لا نعرف إن كان شيء ينتظرك</span><button type="button" class="v2h-lnk" data-a="retry">أعد المحاولة</button>');
    } else if (failed.length) {
      html += strip('bad', '<span>تعذّر جلب: ' + esc(failed.join(' · ')) + ' — العدد ناقص، وما ظهر ليس كل شيء</span><button type="button" class="v2h-lnk" data-a="retry">أعد المحاولة</button>');
    }
    if (trunc.length) {
      html += strip('warn', '<span>معروض جزء فقط من: ' + esc(trunc.map(function (t) { return String(t).split(':')[0].trim(); }).join(' · ')) + ' — الباقي موجود ولا يظهر هنا</span>');
    }
    if (inboxUnknown()) { el.innerHTML = html; return; }          // الوارد لم يصل: لا شرائط خدمة ولا توزيع ولا «للعلم» فوق مجهول
    // وضع الخدمة
    var mode = call('efServiceMode');
    var hasFiles = rowsAll().some(function (r) { return r.apiKind === 'expert_file' || (r.apiKind === 'dispute' && r.dsrc === 'file'); });
    if (ctx !== 'messages' && hasFiles && (mode === 'closed' || mode === 'allowlist')) {
      var n = ep() && ep().data ? ep().data.efAllowlistSize : null;
      html += strip('info', '<span>' + esc(L.v2hServiceLine(mode, typeof n === 'number' ? n : null)) + '</span>');
    }
    // التوزيع التلقائي
    var f = getFilter();
    var autoCtx = (ctx === 'files') || (ctx === 'home' && ['all', 't:files', 'attn', 'review', 'urgent', 'nocand', 'contract'].indexOf(f) > -1);
    var autoLine = autoCtx ? L.v2hAutoLine(call('efAutoOn') === undefined ? null : call('efAutoOn')) : null;
    if (autoLine) {
      var a = S.auto, on = call('efAutoOn') === true;
      var btn = on ? (a.confirm ? '' : '<button type="button" class="v2h-btn2" data-a="auto_off">' + autoLine.btn + '</button>')
                   : '<button type="button" class="v2h-btn2" data-a="auto_on"' + (a.busy ? ' disabled' : '') + '>' + (a.busy ? 'جارٍ التنفيذ…' : autoLine.btn) + '</button>';
      var conf = (on && a.confirm)
        ? '<div class="v2h-conf" role="group" aria-label="تأكيد إيقاف التوزيع التلقائي"><p>' + esc(autoLine.confirm) + '</p>'
          + '<div class="v2h-confa"><button type="button" class="v2h-btn1 sm" data-a="auto_go"' + (a.busy ? ' disabled' : '') + '>' + (a.busy ? 'جارٍ التنفيذ…' : 'نعم، أوقفه') + '</button>'
          + '<button type="button" class="v2h-btn2" data-a="auto_x"' + (a.busy ? ' disabled' : '') + '>رجوع</button></div></div>' : '';
      html += '<div class="v2h-auto' + (on ? '' : ' off') + '" role="group" aria-label="التوزيع التلقائي"><div class="v2h-autot"><b>' + esc(autoLine.head) + '</b> <span>' + esc(autoLine.body) + '</span></div>' + btn
        + (a.err ? '<p class="v2h-err" aria-live="polite">' + esc(a.err) + '</p>' : '') + conf + '</div>';
    }
    // للعلم
    var nf = fyiRows().length;
    if (f === 'fyi') {
      var back = ctx === 'files' ? 't:files' : 'all';
      html += strip('info fyi', '<span>' + esc(L.v2hFyiLine(nf, null, true)) + '</span><button type="button" class="v2h-lnk" data-a="fyi_back" data-f="' + back + '">رجوع إلى الكل</button>');
    } else if (nf > 0 && mode !== 'closed' && ((ctx === 'home' && f === 'all') || (ctx === 'files' && f === 't:files'))) {
      html += strip('info fyi', '<span>' + esc(L.v2hFyiLine(nf, call('efAutoOn'), false)) + '</span><button type="button" class="v2h-lnk" data-a="fyi_on">اعرضها</button>');
    }
    el.innerHTML = html;
  }

  // ------------------------------------------------------------------ الشرائح والشريط الصغير
  function chipHtml(c) {
    return '<button type="button" class="v2h-chip' + (c.on ? ' on' : '') + (c.tone ? ' tone-' + c.tone : '') + '" data-f="' + esc(c.key) + '" aria-pressed="' + (c.on ? 'true' : 'false') + '">'
      + esc(c.label) + ' <b>' + c.text + '</b></button>';
  }
  function activeLabel(chips, f) {
    var all = chips.row1.concat(chips.row2), hit = all.filter(function (c) { return c.key === f; })[0];
    if (hit) return hit.label;
    return f === 'fyi' ? 'للعلم' : 'الكل';
  }
  function inboxUnknown() { return !rowsAll().length && inboxStatus() !== 'ready'; }      // لم يصل شيء بعد: لا أعداد (لا صفر كاذب)
  function drawFilters(b, ctx) {
    var el = document.getElementById('filters'); if (!el) return;
    if (inboxUnknown()) { el.innerHTML = ''; var ts0 = document.getElementById('v2hTypes'); if (ts0) ts0.innerHTML = ''; return; }
    var f = getFilter();
    var chips = L.v2hChips(ctx, countsFor(ctx), f);
    var h = '';
    if (chips.row1.length || chips.row2.length) {
      h += '<div class="v2h-chips" role="group" aria-label="تصفية الوارد">' + chips.row1.map(chipHtml).join('') + '</div>';
      if (chips.row2.length) h += '<div class="v2h-chips sub" role="group" aria-label="تصفية الملفات">' + chips.row2.map(chipHtml).join('') + '</div>';
    }
    var sg = L.v2hSegs(b.shown, S.seg);
    h += '<div class="v2h-mbar"><div class="v2h-seg" role="tablist" aria-label="حالة البنود">'
      + sg.segs.map(function (s) {
        return '<button type="button" role="tab" class="v2h-segb' + (s.on ? ' on' : '') + (s.key === 'late' ? ' tone-late' : '') + '" data-g="' + s.key + '" aria-selected="' + (s.on ? 'true' : 'false') + '"><span>' + esc(s.label) + '</span><b>' + s.text + '</b></button>';
      }).join('') + '</div>';
    if (chips.row1.length || chips.row2.length) {
      h += '<button type="button" class="v2h-typebtn" data-a="types" aria-haspopup="dialog"><span>النوع: ' + esc(activeLabel(chips, f)) + '</span>' + CHEV + '</button>';
    }
    h += '</div>';
    el.innerHTML = h;
    S.activeSeg = sg.active;
    // ورقة النوع
    var ts = document.getElementById('v2hTypes');
    if (ts) {
      var rows = chips.row1.filter(function (c) { return c.key !== 'late' && c.key !== 'auto'; }).concat(chips.row2);
      ts.innerHTML = '<div class="v2h-th"><b>اختر النوع</b><button type="button" class="v2h-tx" data-a="tclose">إغلاق</button></div>'
        + rows.map(function (c) { return '<button type="button" class="v2h-trow' + (c.on ? ' on' : '') + '" data-f="' + esc(c.key) + '"><span>' + esc(c.label) + '</span><b>' + c.text + '</b></button>'; }).join('');
      applyTypes();
    }
  }
  function applyTypes() {
    var root = qs('.v2h'); if (!root) return;
    root.classList.toggle('types-open', !!S.typesOpen && mobile());
    if (S.typesOpen && mobile()) document.documentElement.classList.add('v2-noscroll');
    else if (!sheetIsOpen()) document.documentElement.classList.remove('v2-noscroll');
  }

  // ------------------------------------------------------------------ التذاكر
  function ticketHtml(it, sel) {
    var c = it.card || { tag: 'بند', title: str(it.row.who) || 'بند ينتظر قرارك', sub: '', brain: '', ageText: '' };
    var btn = L.v2hTicketBtn(it.card);
    // brain2: رأي العقل من الذاكرة فقط (لا طلب رأي جديد من التذكرة) وبلا تبديل لزرّها. أي عطل ⇒ السطر القديم كما هو.
    if (it.card && window.V2BRAIN) { try { c = window.V2BRAIN.decorate(it.card, { remap: false }) || it.card; } catch (e) { c = it.card; } }
    var flags = L.v2hFlags(it.row), warn = L.v2hWarn(it.row);
    var title = esc(c.title);
    if (c.person && window.V2D2 && window.V2D2.link) title = window.V2D2.link(c.title, c.person.email);
    var h = '<article class="v2h-t tone-' + it.tone + (sel ? ' sel' : '') + '" data-i="' + it.idx + '"' + (sel ? ' aria-current="true"' : '') + '>'
      + '<div class="v2h-ttop"><span>' + esc(c.tag) + '</span><span class="v2h-age">' + esc(c.ageText || 'غير معروف الوقت') + '</span></div>'
      + '<div class="v2h-tbody"><b class="v2h-ttl">' + title + '</b>'
      + (c.sub ? '<p class="v2h-sub">' + esc(c.sub) + '</p>' : '')
      + (flags.length ? '<div class="v2h-flags">' + flags.map(function (f) { return '<span class="v2h-flag' + (f.w ? ' w' : '') + '"' + (f.tip ? ' title="' + esc(f.tip) + '"' : '') + '>' + esc(f.t) + '</span>'; }).join('') + '</div>' : '')
      + (warn ? '<p class="v2h-warn">' + esc(warn) + '</p>' : '')
      + (c.brain && c.brain !== c.tag && c.brain !== c.sub ? '<p class="v2h-brain"><img src="' + img('brain-avatar') + '" alt=""><span>' + esc(c.brain)
          + (c.src && c.src.text ? '<span class="v2b-src ' + esc(c.src.tone || '') + '">' + esc(c.src.text) + '</span>' : '') + '</span></p>' : '')
      + (it.row.amountLabel ? '<span class="v2h-amt">' + esc(it.row.amountLabel) + '</span>' : '')
      + '</div><div class="v2h-tfoot"><button type="button" class="v2h-btn1" data-a="t1" data-i="' + it.idx + '" aria-label="' + esc(btn.label + ': ' + c.title) + '">' + esc(btn.label) + '</button></div></article>';
    return h;
  }
  function str(v) { return typeof v === 'string' ? v.trim() : ''; }
  var SKEL = '<div class="v2h-sk"><i></i><i></i><i></i></div>';

  function drawRows(b, ctx) {
    var el = document.getElementById('rows'); if (!el) return;
    var st = inboxStatus(), failed = failedList(), sel = getSel();
    var items = b.shown, h = '';
    if (window.V2BRAIN && items.length) { try { window.V2BRAIN['prefetch'](items.slice(0, 40).map(function (it) { return it.card; }).filter(Boolean)); } catch (e) {} }   // مفتاح نصّي: فحص «لا شبكة هنا» يمنع الكلمة مع القوس
    var inN = document.getElementById('inboxN'); if (inN) inN.textContent = String(items.length);
    if (!items.length) {
      var ctxDefault = CTX_DEFAULT[ctx] || 'all';
      var ctxHas = rowsAll().some(function (r) { return match(r, ctxDefault); });
      var q = S.q.trim();
      if (!rowsAll().length && st === 'loading') h = '<div class="v2h-empty"><p>جارٍ جلب الوارد…</p>' + SKEL + '</div>';
      else if (!rowsAll().length && st === 'error') h = '<div class="v2h-empty"><b>لا نعرف الآن ما ينتظرك</b></div>';
      else if (q && b.base.length) h = '<div class="v2h-empty"><b>لا بنود تطابق «' + esc(q) + '»</b><button type="button" class="v2h-btn2" data-a="clearq">امسح البحث</button></div>';
      else if (!ctxHas || (b.filter === ctxDefault && !b.base.length)) {
        if (failed.length) h = '<div class="v2h-empty"><b>لا بنود ظهرت، لكن تعذّر جلب ' + esc(failed.join(' · ')) + ' — لا تعتبر القائمة فارغة</b></div>';
        else h = '<div class="v2h-empty"><img src="' + img('brain-avatar') + '" alt=""><b>لا شيء ينتظرك هنا الآن</b></div>';
      } else h = '<div class="v2h-empty"><b>لا بنود في هذا الاختيار</b><button type="button" class="v2h-btn2" data-a="showall" data-f="' + esc(ctxDefault) + '">اعرض الكل</button></div>';
      el.removeAttribute('data-seg');
      el.innerHTML = h;
      return;
    }
    var groups = L.v2hGroups(items);
    var seg = L.v2hSegs(items, S.seg).active;
    var mob = mobile();
    if (mob) groups = groups.filter(function (g) { return g.key === seg; });
    var left = S.page, total = 0;
    groups.forEach(function (g) { total += g.items.length; });
    groups.forEach(function (g) {
      if (left <= 0) return;
      var part = g.items.slice(0, left); left -= part.length;
      h += '<div class="v2h-g" data-grp="' + g.key + '"><h2 class="v2h-gh">' + esc(b.filter === 'fyi' ? 'للعلم' : g.label) + ' <b>' + ar(g.items.length) + '</b></h2><div class="v2h-tl">'
        + part.map(function (it) { return ticketHtml(it, sel === it.idx); }).join('') + '</div></div>';
    });
    var rest = total - S.page;
    if (rest > 0) h += '<button type="button" class="v2h-more" data-a="more">اعرض المزيد (' + ar(rest) + ')</button>';
    el.setAttribute('data-seg', seg);
    el.innerHTML = h;
  }

  // ------------------------------------------------------------------ أرقام المنصة
  function drawQueue() {
    var d = document.getElementById('v2hQueue'); if (!d) return;
    var sum = qs('summary', d), body = qs('.v2h-qgrid', d);
    var s = stateOf('opsQueue'), E = ep();
    var Q = s === 'ready' && E && E.data ? E.data.opsQueue : null;
    if (s === 'idle' || s === 'loading') { sum.textContent = 'أرقام المنصة الآن'; body.innerHTML = '<p class="v2h-qn">جارٍ الجلب…</p>'; return; }
    if (s === 'error' || !Q) {
      sum.textContent = 'أرقام المنصة: تعذّر الجلب';
      body.innerHTML = '<p class="v2h-qn">تعذّر جلب أرقام المنصة</p><button type="button" class="v2h-btn2" data-a="qretry">أعد المحاولة</button>';
      return;
    }
    var rows = [];
    try { rows = call('opsQueueCounters', Q) || []; } catch (e) {}
    if (!rows.length) { sum.textContent = 'أرقام المنصة الآن'; body.innerHTML = '<p class="v2h-qn">لا أرقام تنتظرك الآن</p>'; return; }
    sum.textContent = 'أرقام المنصة الآن (' + UT.U(rows.length, ['بند واحد', 'بندان', 'بنود', 'بندًا']) + ')';
    body.innerHTML = rows.map(function (r, i) {
      var label = L.v2hQueueLabel(r[3]), n = ar(r[1]);
      return r[2]
        ? '<button type="button" class="v2h-qb" data-a="qgo" data-qi="' + i + '"><span>' + esc(label) + '</span><b>' + n + '</b></button>'
        : '<div class="v2h-qb off"><span>' + esc(label) + ' · لا شاشة له بعد</span><b>' + n + '</b></div>';
    }).join('');
    H._qrows = rows;
  }

  // ------------------------------------------------------------------ ورقة الدرج
  function sheetIsOpen() { var d = document.getElementById('v2hDw'); return !!(d && d.classList.contains('open') && narrow()); }
  function syncSheet() {
    var d = document.getElementById('v2hDw'); if (!d) return;
    var open = getSel() !== null && !!rowsAll()[getSel()];
    d.classList.toggle('open', open);
    var lock = open && narrow();
    var html = document.documentElement;
    if (lock) html.classList.add('v2-noscroll');
    else if (!(S.typesOpen && mobile())) html.classList.remove('v2-noscroll');
    if (open && narrow() && !S.wasOpen) { var cb = qs('.v2h-dbar button', d); if (cb) { try { cb.focus({ preventScroll: true }); } catch (e) {} } }
    if (!open && S.wasOpen && narrow() && S.opener != null) {
      var t = qs('.v2h-btn1[data-i="' + S.opener + '"]');
      if (t) { try { t.focus({ preventScroll: true }); } catch (e) {} }
      S.opener = null;
    }
    S.wasOpen = open;
  }
  function closeSheet() {
    setSel(null);
    try { window.efDspOpen.id = null; } catch (e) {}
    call('efVoiceDrop'); call('efCaseUiReset');
    call('renderInbox');
  }
  function openTicket(i, drawerA) {
    S.opener = i;
    setSel(i);
    try { window.efDspOpen.id = null; } catch (e) {}
    call('efVoiceDrop'); call('efCaseUiReset');
    call('renderInbox');
    var dr = document.getElementById('drawer');
    if (!dr) return;
    if (!narrow()) { try { dr.scrollTop = 0; } catch (e) {} }
    if (drawerA !== undefined) focusTarget(dr, drawerA);
  }
  // زر التذكرة «أرسله/انقله إلى فلان»: يفتح قائمة الاختيار الموجودة والخبير المقترح محدَّد فيها، ولا يُرسل شيئًا:
  // الإرسال نفسه يبقى بزر القائمة («ابعته لـ…») ومن غير تغيير في مساره. لو لم يُعثر على الاسم تُترك القائمة بلا تحديد ليختار المؤسس.
  function openPicker(card) {
    var a = card && card.primary && card.primary.act;
    var name = a && String(a.name || a.email || '').trim();
    var dr = document.getElementById('drawer');
    var b = dr && qs('.acts [data-a="ef_pick"]', dr);
    if (!name || !b) return;
    b.click();
    var m = document.getElementById('epModal'); if (!m) return;
    var hit = qsa('.ef-cand', m).filter(function (lb) { var n = qs('.nm', lb); return n && n.textContent.trim() === name; })[0];
    var inp = hit && qs('input[type=radio]', hit);
    if (!inp) return;
    inp.checked = true;
    try { if (typeof inp.onchange === 'function') inp.onchange(); else inp.dispatchEvent(new Event('change', { bubbles: true })); } catch (e) {}
    var go = qs('#ep_go', m); if (go) { try { go.focus({ preventScroll: true }); } catch (e2) {} }
  }
  function focusTarget(dr, drawerA) {
    var acts = qs('.acts', dr), t = null;
    if (drawerA) t = qs('.acts [data-a="' + drawerA + '"]', dr);
    if (!t) t = qs('.acts .btn-primary, .acts .btn-human', dr);
    if (!t) t = qs('h3', dr) || qs('button', dr);
    if (acts) {
      if (narrow()) { if (acts.scrollIntoView) { try { acts.scrollIntoView({ block: 'center', behavior: reduced() ? 'auto' : 'smooth' }); } catch (e) {} } }
      else { var dw = document.getElementById('v2hDw'); if (dw) { try { dw.scrollTop = Math.max(0, acts.offsetTop - Math.round(dw.clientHeight / 2)); } catch (e) {} } }
    }
    if (t) {
      if (!t.hasAttribute('tabindex') && !/^(BUTTON|A|INPUT|SELECT|TEXTAREA)$/.test(t.tagName)) t.setAttribute('tabindex', '-1');
      try { t.focus({ preventScroll: true }); } catch (e) {}
      t.classList.add('v2h-hl');
      setTimeout(function () { try { t.classList.remove('v2h-hl'); } catch (e) {} }, 1600);
    }
  }

  // ------------------------------------------------------------------ الأحداث
  function chooseFilter(f) {
    setFilter(f); setSel(null); S.seg = null;
    call('renderInbox');
  }
  function wire(root) {
    root.addEventListener('click', function (e) {
      var t = e.target;
      var a = t.closest && t.closest('a'); if (a && !t.closest('[data-a]')) { if (t.closest('.v2h-t')) return; }
      if (t === document.getElementById('v2hDw')) { if (narrow()) closeSheet(); return; }      // نقرة على الستار خارج الورقة
      var el = t.closest && t.closest('[data-a],[data-f],[data-g],.v2h-t');
      if (!el || !root.contains(el)) return;
      var act = el.getAttribute('data-a');
      if (act === 't1') {
        var ti = +el.getAttribute('data-i'), tc = cardForIdx(ti), tb = L.v2hTicketBtn(tc);
        openTicket(ti, tb.drawerA);
        if (tb.drawerA === 'ef_pick') openPicker(tc);
        return;
      }
      if (el.classList.contains('v2h-t') && !act) { if (t.closest('a')) return; openTicket(+el.getAttribute('data-i')); return; }
      if (el.hasAttribute('data-g') && !act) { S.seg = el.getAttribute('data-g'); drawAll(false); return; }
      if (act === 'more') { S.page += 60; drawAll(false); return; }
      if (act === 'dclose') { closeSheet(); return; }
      if (act === 'clearq') { S.q = ''; var i0 = document.getElementById('v2hq'); if (i0) { i0.value = ''; i0.focus(); } softRedraw(); return; }
      if (act === 'showall' || act === 'fyi_back') { chooseFilter(el.getAttribute('data-f') || 'all'); return; }
      if (act === 'fyi_on') { chooseFilter('fyi'); return; }
      if (act === 'retry') { var E = ep(); if (E && E.reload) E.reload('inbox', function () { if (mounted()) softRedraw(); }); return; }
      if (act === 'qretry') { var E2 = ep(); if (E2 && E2.reload) E2.reload('opsQueue', function () { if (mounted()) drawQueue(); }); return; }
      if (act === 'queue') { var d = document.getElementById('v2hQueue'); if (d) { d.open = true; var sm = qs('summary', d); try { d.scrollIntoView({ block: 'start', behavior: reduced() ? 'auto' : 'smooth' }); if (sm) sm.focus({ preventScroll: true }); } catch (e3) {} } return; }
      if (act === 'qgo') { var r = (H._qrows || [])[+el.getAttribute('data-qi')]; if (r) call('goOps', r[2], r[4]); return; }
      if (act === 'types') { S.typesOpen = true; applyTypes(); var fr = qs('#v2hTypes .v2h-trow.on, #v2hTypes .v2h-trow'); if (fr) fr.focus(); return; }
      if (act === 'tclose') { S.typesOpen = false; applyTypes(); return; }
      if (act === 'auto_off') { S.auto = { confirm: true, busy: false, err: '' }; drawHead(build(), ctxNow()); var x = qs('[data-a="auto_x"]'); if (x) x.focus(); return; }
      if (act === 'auto_x') { S.auto = { confirm: false, busy: false, err: '' }; drawHead(build(), ctxNow()); var o = qs('[data-a="auto_off"]'); if (o) o.focus(); return; }
      if (act === 'auto_on' || act === 'auto_go') { setAuto(act === 'auto_on'); return; }
      var f = el.getAttribute('data-f');
      if (f && !act) { S.typesOpen = false; applyTypes(); chooseFilter(f); return; }
    });
    var tsc = document.getElementById('v2hTScrim');
    if (tsc) tsc.addEventListener('click', function () { S.typesOpen = false; applyTypes(); });
    wireGlobal();
  }
  var globalDone = false;
  function wireGlobal() {
    if (globalDone) return; globalDone = true;
    // تبويب مقيّد داخل الورقة المفتوحة + Escape
    document.addEventListener('keydown', function (e) {
      if (!mounted()) return;
      if (e.key === 'Escape') {
        if (document.getElementById('epModal')) return;
        if (S.typesOpen && mobile()) { S.typesOpen = false; applyTypes(); return; }
        if (sheetIsOpen()) { closeSheet(); }
        return;
      }
      if (e.key !== 'Tab') return;
      var box = null;
      if (S.typesOpen && mobile()) box = document.getElementById('v2hTypes');
      else if (sheetIsOpen() && !document.getElementById('epModal')) box = document.getElementById('v2hDw');
      if (!box) return;
      var f = qsa('a[href],button:not([disabled]),input:not([disabled]),select:not([disabled]),textarea:not([disabled])', box).filter(function (n) { return n.offsetParent !== null; });
      if (!f.length) return;
      var first = f[0], last = f[f.length - 1], cur = document.activeElement;
      if (!box.contains(cur)) { e.preventDefault(); first.focus(); }
      else if (e.shiftKey && cur === first) { e.preventDefault(); last.focus(); }
      else if (!e.shiftKey && cur === last) { e.preventDefault(); first.focus(); }
    });
    // عبور حدّ الموبايل/التابلت ⇒ إعادة رسم خفيفة
    ['(max-width:760px)', '(max-width:1179px)'].forEach(function (q) {
      try { var m = window.matchMedia(q); var f2 = function () { if (mounted()) { applyTypes(); softRedraw(); } }; if (m.addEventListener) m.addEventListener('change', f2); else if (m.addListener) m.addListener(f2); } catch (e) {}
    });
  }
  function cardForIdx(i) { var r = rowsAll()[i]; return r ? cardOf(r, Date.now()) : null; }

  function setAuto(value) {
    var E = ep(); if (!E || !E.expertFileAutoAssign || S.auto.busy) return;
    S.auto = { confirm: !value, busy: true, err: '' };
    drawHead(build(), ctxNow());
    var done = function () { if (mounted()) softRedraw(); };
    E.expertFileAutoAssign(value, done).then(function (r) {
      if (r && r.ok) S.auto = { confirm: false, busy: false, err: '' };
      else {
        var msg = (r && r.error) || 'تعذّر تنفيذ العملية';
        try { msg = (window.V2 && V2.plainError) ? V2.plainError(r) : msg; } catch (e) {}
        S.auto = { confirm: !value, busy: false, err: msg };
      }
      done();
    });
  }

  // ------------------------------------------------------------------ الجرس (حالة المنصة + الإشعارات)
  var B = H.bell = { mountedOk: false, open: false, notif: { state: 'idle', items: null, at: 0 }, seen: null };
  function seenLoad() {
    if (B.seen) return B.seen;
    var arr = [];
    try { var v = JSON.parse(localStorage.getItem('ep_v2h_seen') || '[]'); if (Array.isArray(v)) arr = v; } catch (e) {}
    B.seen = arr;
    return arr;
  }
  function seenSave() {
    try { localStorage.setItem('ep_v2h_seen', JSON.stringify(B.seen.slice(-300))); } catch (e) {}
  }
  function healthNow() {
    var s = stateOf('opsQueue'), E = ep();
    if (s === 'idle' || s === 'loading') return { src: 'loading', health: null };
    if (s === 'error') return { src: 'error', health: { ok: false, failed: true, alerts: [], heartbeats: [] } };
    var h = L.v2Health(E && E.data ? E.data.opsQueue : null, Date.now());
    return { src: 'ready', health: h };
  }
  function notifList() {
    var n = B.notif;
    if (n.state === 'error') return null;
    if (n.state === 'ready') return n.items;
    return undefined;
  }
  function fetchNotifs(force) {
    var E = ep(); if (!E || !E.api || !E.authed) return;
    var n = B.notif;
    if (n.state === 'loading') return;
    if (!force && n.state === 'ready' && Date.now() - n.at < 60000) return;
    n.state = 'loading'; badge(); redrawBell();
    var p;
    try { p = E.api('/notifications'); } catch (e) { n.state = 'error'; badge(); redrawBell(); return; }
    p.then(function (r) {
      var list = L.v2hNotifList(r);
      if (list === null) { n.state = 'error'; n.items = null; } else { n.state = 'ready'; n.items = list; n.at = Date.now(); }
      badge(); redrawBell();
    }).catch(function () { n.state = 'error'; n.items = null; badge(); redrawBell(); });
  }
  function badge() {
    var bb = document.getElementById('bellBtn'); if (!bb || !B.mountedOk) return;
    var hn = healthNow();
    var b = L.v2hBellBadge(hn.health, notifList(), seenLoad());
    var em = qs('.v2h-bn', bb);
    if (!em) { em = document.createElement('em'); em.className = 'v2h-bn'; bb.appendChild(em); }
    em.textContent = b.text;
    em.className = 'v2h-bn tone-' + b.tone + (b.dot ? ' dot' : '');
    bb.classList.toggle('v2h-hd', !!(b.dot && b.text));        // عدّ + صحة معًا: النقطة على زاوية الزر لا فوق الرقم
    var label = 'التنبيهات';
    if (b.text && b.text !== '!') label = 'التنبيهات · ' + b.text + ' جديدة';
    else if (b.dot || b.text === '!') label = 'التنبيهات · حالة المنصة تحتاج نظرة';
    bb.setAttribute('aria-label', label);
  }
  function bellHtml() {
    var hn = healthNow(), E = ep();
    var h = '<div class="v2h-bh"><b>التنبيهات</b><button type="button" class="v2h-bx" data-a="bclose">إغلاق</button></div>';
    // —— حالة المنصة
    h += '<section class="v2h-bs" id="v2HHealth"><h3>حالة المنصة</h3>';
    if (hn.src === 'loading') h += '<p class="v2h-bm">جارٍ الفحص…</p>';
    else if (hn.src === 'error') h += '<p class="v2h-bm bad">تعذّر فحص حالة المنصة — لا تعتبرها سليمة</p><button type="button" class="v2h-btn2" data-a="hretry">أعد المحاولة</button>';
    else {
      var hh = hn.health;
      if (hh.failed) h += '<p class="v2h-bm bad">تعذّر فحص حالة المنصة — لا تعتبرها سليمة</p><button type="button" class="v2h-btn2" data-a="hretry">أعد المحاولة</button>';
      else if (hh.ok) h += '<p class="v2h-bm ok"><i></i>كل شيء يعمل</p>';
      else {
        var shown = (B.allAlerts || hh.alerts.length <= 4) ? hh.alerts : hh.alerts.slice(0, 3);
        h += shown.map(function (t) {
          var sec = L.v2hAlertSection(t);
          return '<div class="v2h-al"><span>' + esc(t) + '</span>' + (sec ? '<button type="button" class="v2h-btn2" data-a="hopen" data-s="' + sec + '">افتح</button>' : '') + '</div>';
        }).join('');
        if (shown.length < hh.alerts.length) h += '<button type="button" class="v2h-lnk" data-a="hmore">اعرض باقي التنبيهات (' + ar(hh.alerts.length - shown.length) + ')</button>';
      }
      if (hh.heartbeats && hh.heartbeats.length) {
        h += '<h4>آخر تشغيل للمهام الدورية</h4><ul class="v2h-hb">' + hh.heartbeats.map(function (b) { return '<li><span>' + esc(b.label) + '</span><b>' + esc(b.ago) + '</b></li>'; }).join('') + '</ul>';
      }
    }
    h += '</section>';
    // —— الإشعارات
    var n = B.notif, seen = seenLoad();
    h += '<section class="v2h-bs" id="v2HNotifs"><div class="v2h-bsh"><h3>الإشعارات</h3>'
      + (n.state === 'ready' && n.items && n.items.length ? '<button type="button" class="v2h-lnk" data-a="hall">علّم الكل كمقروء</button>' : '') + '</div>';
    if (n.state === 'idle' || n.state === 'loading') h += '<div class="v2h-bsk"><i></i><i></i></div>';
    else if (n.state === 'error') h += '<p class="v2h-bm bad">تعذّر جلب الإشعارات</p><button type="button" class="v2h-btn2" data-a="nretry">أعد المحاولة</button>';
    else if (!n.items || !n.items.length) h += '<p class="v2h-bm">لا إشعارات جديدة</p>';
    else {
      var now = Date.now();
      h += '<ul class="v2h-nl">' + n.items.map(function (it, i) {
        var unseen = it.unread && seen.indexOf(it.id) < 0;
        var when = it.when ? UT.agoText(Date.parse(it.when), now) : '';
        return '<li><button type="button" class="v2h-ni' + (unseen ? ' unseen' : '') + '" data-a="nopen" data-ni="' + i + '"><i></i><span><b>' + esc(it.title) + '</b>'
          + (it.detail ? '<small>' + esc(it.detail) + '</small>' : '') + '</span>' + (when ? '<time>' + esc(when) + '</time>' : '') + '</button></li>';
      }).join('') + '</ul>';
    }
    h += '</section>';
    return h;
  }
  function redrawBell() {
    var p = document.getElementById('v2HBell');
    if (!p || !B.open) return;
    var scroll = p.scrollTop;
    var focusA = document.activeElement && p.contains(document.activeElement) ? document.activeElement.getAttribute('data-a') : null;
    p.innerHTML = bellHtml();
    p.scrollTop = scroll;
    if (focusA) { var n = qs('[data-a="' + focusA + '"]', p); if (n) { try { n.focus({ preventScroll: true }); } catch (e) {} } }
  }
  function ensureBellDom() {
    if (document.getElementById('v2HBell')) return;
    var sc = document.createElement('div'); sc.id = 'v2HBellScrim'; sc.className = 'v2h-bscrim';
    var p = document.createElement('div'); p.id = 'v2HBell'; p.className = 'v2h-bell'; p.setAttribute('role', 'dialog'); p.setAttribute('aria-label', 'التنبيهات');
    document.body.appendChild(sc); document.body.appendChild(p);
    sc.addEventListener('click', function () { B.close(); });
    p.addEventListener('click', function (e) {
      var el = e.target.closest && e.target.closest('[data-a]'); if (!el) return;
      var a = el.getAttribute('data-a');
      if (a === 'bclose') { B.close(); return; }
      if (a === 'hretry') { var E = ep(); if (E && E.reload) E.reload('opsQueue', function () { badge(); redrawBell(); }); return; }
      if (a === 'nretry') { fetchNotifs(true); return; }
      if (a === 'hmore') { B.allAlerts = true; redrawBell(); return; }
      if (a === 'hall') { var seen = seenLoad(); (B.notif.items || []).forEach(function (it) { if (seen.indexOf(it.id) < 0) seen.push(it.id); }); seenSave(); badge(); redrawBell(); return; }
      if (a === 'hopen') { var s = el.getAttribute('data-s'); B.close(); try { host().openSection(s); } catch (e2) {} return; }
      if (a === 'nopen') {
        var it = (B.notif.items || [])[+el.getAttribute('data-ni')]; if (!it) return;
        var sn = seenLoad(); if (sn.indexOf(it.id) < 0) sn.push(it.id); seenSave(); badge();
        B.close();
        if (it.dest) { try { host().openSection(it.dest.section, it.dest.tab); } catch (e3) {} }
      }
    });
    document.addEventListener('keydown', function (e) {
      if (!B.open) return;
      if (e.key === 'Escape') { B.close(); return; }
      if (e.key !== 'Tab') return;
      var f = qsa('button:not([disabled])', p).filter(function (n) { return n.offsetParent !== null; });
      if (!f.length) return;
      var first = f[0], last = f[f.length - 1], cur = document.activeElement;
      if (!p.contains(cur)) { e.preventDefault(); first.focus(); }
      else if (e.shiftKey && cur === first) { e.preventDefault(); last.focus(); }
      else if (!e.shiftKey && cur === last) { e.preventDefault(); first.focus(); }
    });
  }
  B.mount = function () {
    if (!enabled() || B.mountedOk) return;
    var bb = document.getElementById('bellBtn'); if (!bb) return;
    B.mountedOk = true;
    bb.onclick = function (e) { if (e && e.stopPropagation) e.stopPropagation(); if (B.open) B.close(); else B.show(); };
    var E = ep(); if (E && E.ensure) E.ensure('opsQueue', function () { badge(); redrawBell(); });
    badge();
    fetchNotifs(false);
  };
  B.show = function (focusHealth) {
    if (!enabled()) return;
    ensureBellDom();
    B.open = true; B.allAlerts = false;
    var E = ep(); if (E && E.ensure) E.ensure('opsQueue', function () { badge(); redrawBell(); });
    var p = document.getElementById('v2HBell');
    p.innerHTML = bellHtml();
    p.classList.add('open'); document.getElementById('v2HBellScrim').classList.add('open');
    B.opener = document.activeElement;
    fetchNotifs(false);
    var c = qs('.v2h-bx', p); if (c) { try { c.focus({ preventScroll: true }); } catch (e) {} }
    if (focusHealth) { var hs = document.getElementById('v2HHealth'); if (hs && hs.scrollIntoView) { try { hs.scrollIntoView({ block: 'start' }); } catch (e) {} } }
  };
  B.close = function () {
    B.open = false;
    var p = document.getElementById('v2HBell'), sc = document.getElementById('v2HBellScrim');
    if (p) p.classList.remove('open'); if (sc) sc.classList.remove('open');
    var o = B.opener; B.opener = null;
    if (o && o.focus && document.body.contains(o)) { try { o.focus({ preventScroll: true }); } catch (e) {} }
  };

  // ------------------------------------------------------------------ سطر الصحة في الشريط الداكن (اللوحة)
  function healthLine() {
    if (!enabled()) return;
    var hostOk = false;
    try { hostOk = !!(host().isHome && host().isHome()); } catch (e) {}
    if (!hostOk) return;
    var nt = qs('.v2-next .v2-nt'); if (!nt) return;
    var old = qs('.v2h-healthline', nt); if (old) old.remove();
    var hn = healthNow();
    var line = L.v2hHealthLine(hn.src, hn.health);
    var b = document.createElement('button');
    b.type = 'button'; b.className = 'v2h-healthline tone-' + line.tone; b.setAttribute('data-a', 'bell'); b.textContent = line.text;
    nt.appendChild(b);
  }
  function watchBoard() {
    var view = qs('#view'); if (!view || !window.MutationObserver) return;
    try { new MutationObserver(function () { healthLine(); }).observe(view, { childList: true }); } catch (e) {}
    document.addEventListener('click', function (e) {
      var b = e.target.closest && e.target.closest('.v2h-healthline');
      if (b) { e.preventDefault(); B.show(true); }
    });
    healthLine();
  }

  // ------------------------------------------------------------------ طبقة النصوص (الدرج ونافذة التأكيد والتنبيهات)
  var C = H.copy = { missed: new Set ? new Set() : null, installed: false, log: window.__v2hCap && window.Set ? new Set() : null };   // `log`: التقاط النصوص الأصلية لسكربت اللقطات فقط
  var MARKERS = L.V2H_COLLOQUIAL;
  // ⛔ الدرج: درج الوارد وحده (`.v2h .drawer`). غيره من الأقسام (جهات الاتصال · المستثمرون · الأسواق · المستخدمون · الدورات …) يشارك
  // نفس صنف `.drawer` وفيه أسماء وكلام كتبه الناس، فلا تُلمس أبدًا. النافذة والتنبيهات المنبثقة تعمل خارج الوارد بالعبارات الطويلة وحدها.
  var SCOPE = '.v2h .drawer,#epModal,#toasts';
  // «بقى» (عامية: إذن) لا تُطابَق داخل «يبقى/تبقى»: تُقرأ كلمةً كاملة.
  function hasMarker(t) {
    for (var i = 0; i < MARKERS.length; i++) {
      var m = MARKERS[i];
      if (m === 'بقى' ? /(^|[^\u0621-\u064A])بقى/.test(t) : t.indexOf(m) > -1) return true;
    }
    return false;
  }
  // 'skip' = كلام الناس نفسه (الاقتباس) ⇒ لا يُلمس ولا يُسجَّل · 'data' = نص قد يكون من المنصة أو من الناس (آراء الخبراء وأسئلة العملاء) ⇒
  // تُطبَّق العبارات الطويلة وحدها (جمل الداشبورد نفسها) ولا يُسجَّل فائتًا · غير ذلك ⇒ نص الداشبورد: كل القاموس ويُسجَّل الفائت.
  function zoneOf(el) {
    if (!el || !el.closest) return 'skip';
    if (el.closest('.ef-quote .row2,.ef-ms .row2,.ef-voice-msg,.ef-cand .nm,script,style,[data-nocopy]')) return 'skip';       // `.ef-cand .nm` = اسم خبير
    if (el.closest('.note-ai b')) return 'data';                                                                  // اسم الطرف الآخر / الخبير الحالي داخل جملة الداشبورد
    if (el.closest('.ef-op') && !el.closest('.ef-op .meta')) return 'data';       // `.meta` تحت الرأي سطر كتبه الداشبورد («اتبعت …» · «+ ١ إجابة…»)
    return '';
  }
  // نصوص المنصة وكلام الناس في الصف المفتوح: تبقى كما وصلت (لا تُترجَم ولا تُسجَّل كفائت)
  var OWN_FIELDS = ['details', 'body', 'topic', 'who', 'email', 'serviceLabel', 'statusLabel', 'infoRequest', 'attachments', 'ef', 'cons', 'raw', 'candidates', 'flagLabels', 'licenceNote'];
  function ownStrings() {
    var row = rowsAll()[getSel()];
    if (!row) return null;
    if (C._ownFor === row) return C._own;
    var set = new Set();
    (function walk(o, d) {
      if (o == null || d > 6) return;
      if (typeof o === 'string') { var t = o.trim(); if (t.length > 1 && t.length < 4000) set.add(t); return; }
      if (typeof o === 'object') { for (var k in o) { try { walk(o[k], d + 1); } catch (e) {} } }
    })(OWN_FIELDS.reduce(function (acc, f) {
      if (row[f] == null) return acc;
      // عناوين الحقول (details[].k) كتبها الداشبورد فتُترجَم؛ القيم (v) كلام الناس فتبقى
      acc[f] = f === 'details' && Array.isArray(row[f]) ? row[f].map(function (d) { return d && d.v; }) : row[f];
      return acc;
    }, {}), 0);
    C._ownFor = row; C._own = set;
    return set;
  }
  // اسم الشاشة القديمة التي يشير إليها الدرج («الضمان والنزاعات» …) ⇒ اسم مكانها في الهيكل الجديد (الغلاف هو من يفتحها فعلًا)
  function newPlace(row) {
    var d = row.dest, k = row.apiKind;
    if (d === 'escrow') return 'الفلوس';
    if (d === 'team' || d === 'courses') return 'الدورات والمدرّبون';
    if (d === 'invites' || d === 'users' || d === 'messages') return 'الناس والدعوات';
    if (d === 'topics') return 'المحتوى';
    if (d === 'knowledge') return 'الكتب';
    if (d === 'inbox') return (k === 'expert_file' || k === 'verify') ? 'ملفات الخبراء' : ((k === 'dispute' || k === 'legacy') ? 'النزاعات والاستردادات' : 'كل الوارد');
    return '';
  }
  function placeMap() {
    var row = rowsAll()[getSel()];
    if (!row) return null;
    if (C._plFor === row) return C._pl;
    var m = {}, old = '';
    try { old = (MODULES_LOOKUP[row.dest] || {}).label || ''; } catch (e) {}
    var nw = newPlace(row);
    if (old && nw && old !== nw) m[old] = nw;
    C._plFor = row; C._pl = m;
    return m;
  }
  function isUrlish(t) { return /^(https?:|mailto:)|@|^www\./i.test(t.trim()); }
  function processText(node) {
    var par = node.parentNode;
    if (!par || par.nodeType !== 1) return;
    if (!par.closest || !par.closest(SCOPE)) return;
    var zone = zoneOf(par);
    if (zone === 'skip') return;
    if (par.closest('a[href]') && isUrlish(node.nodeValue)) return;
    if (par.tagName === 'TEXTAREA') {
      var ta = par; if (ta.value !== ta.defaultValue) return;
    }
    var t = node.nodeValue;
    if (!t || !t.trim()) return;
    if (C.log) C.log.add(t.trim());
    var own = par.closest('.drawer') ? ownStrings() : null;
    var pm = own ? placeMap() : null;
    if (pm) {
      var tt = t.trim(), pre = tt.indexOf('فتح ') === 0 ? 'فتح ' : '', nm = pm[pre ? tt.slice(4) : tt];
      if (nm) { node.nodeValue = t.replace(tt, (pre ? 'افتح ' : '') + nm); return; }
    }
    var strict = zone === 'data' || !!(own && own.has(t.trim())) || (!par.closest('.drawer') && !mounted());   // نافذة/تنبيه خارج الوارد: عبارات طويلة فقط
    var out = L.v2hCopy(t, strict);
    if (out != null) { node.nodeValue = out; return; }
    if (!strict && C.missed && C.missed.size < 500 && hasMarker(t)) C.missed.add(t.trim());
  }
  var ATTRS = ['placeholder', 'title', 'aria-label'];
  function processAttrs(el) {
    if (!el.closest || !el.closest(SCOPE)) return;
    var zone = zoneOf(el);
    if (zone === 'skip') return;
    ATTRS.forEach(function (a) {
      var v = el.getAttribute && el.getAttribute(a);
      if (!v) return;
      if (C.log) C.log.add(v.trim());
      var strictA = zone === 'data' || (!el.closest('.drawer') && !mounted());
      var out = L.v2hCopy(v, strictA);
      if (out != null) el.setAttribute(a, out);
      else if (!strictA && C.missed && C.missed.size < 500 && hasMarker(v)) C.missed.add(v.trim());
    });
  }
  function processTree(root) {
    if (!root) return;
    if (root.nodeType === 3) { processText(root); return; }
    if (root.nodeType !== 1) return;
    var scope = root.closest ? root.closest(SCOPE) : null;
    if (!scope && !(root.querySelector && root.querySelector(SCOPE))) return;
    var walker = document.createTreeWalker(root, 1 | 4);   // عناصر ونصوص
    var n = root, nodes = [];
    if (root.nodeType === 1) nodes.push(root);
    while ((n = walker.nextNode())) nodes.push(n);
    nodes.forEach(function (x) { if (x.nodeType === 3) processText(x); else processAttrs(x); });
  }
  C.apply = processTree;
  C.processText = processText;
  C.install = function () {
    if (C.installed || !window.MutationObserver) return;
    C.installed = true;
    try {
      new MutationObserver(function (muts) {
        muts.forEach(function (m) {
          for (var i = 0; i < m.addedNodes.length; i++) {
            var n = m.addedNodes[i];
            if (n.nodeType === 3) processText(n); else processTree(n);
          }
        });
      }).observe(document.body, { childList: true, subtree: true });
    } catch (e) {}
    processTree(document.body);
  };

  // ------------------------------------------------------------------ الدفعة اليدوية: القرار المالي عبر ورقة التأكيد الموجودة
  // درج الوارد القديم كان يرسل «تأكيد الدفعة» مباشرة؛ هنا يمرّ من نفس ورقة التأكيد التي تفتحها بطاقة اللوحة (المبلغ والمرجع، و`confirmed:true`).
  function payIntercept() {
    document.addEventListener('click', function (e) {
      if (!enabled() || !mounted()) return;
      var b = e.target.closest && e.target.closest('#drawer [data-a="approve"], #drawer [data-a="reject"]');
      if (!b) return;
      var row = rowsAll()[getSel()];
      if (!row || row.apiKind !== 'manual_payment' || !(window.V2 && window.V2.openMoney)) return;
      var card = cardOf(row, Date.now());
      if (!card || card.kind !== 'manual_payment' || !card.primary || !card.primary.money) return;
      e.stopImmediatePropagation(); e.preventDefault();
      var act = b.getAttribute('data-a') === 'approve' ? card.primary.act : (card.secondary && card.secondary.act);
      if (!act) return;
      window.V2.openMoney(card, act, function () { setSel(null); call('efRefreshInbox'); });
    }, true);
  }

  // ------------------------------------------------------------------ البدء (عند إقلاع الغلاف فقط)
  var started = false;
  H.start = function () {
    if (started || !enabled()) return;
    started = true;
    try { document.documentElement.classList.add('v2h-login'); } catch (e) {}
    B.mount();
    C.install();
    payIntercept();
    watchBoard();
    if (window.V2SHELL) {
      var on = window.V2SHELL.nav;
      if (typeof on === 'function') window.V2SHELL.nav = function () { var r = on.apply(this, arguments); try { badge(); if (B.open) redrawBell(); } catch (e) {} return r; };
    }
  };
  if (window.V2SHELL && typeof window.V2SHELL.boot === 'function') {
    var ob = window.V2SHELL.boot;
    window.V2SHELL.boot = function () { var r = ob.apply(this, arguments); try { H.start(); } catch (e) {} return r; };
  }
})();
