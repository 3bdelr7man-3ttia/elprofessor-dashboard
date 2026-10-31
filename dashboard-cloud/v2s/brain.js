/* ============================================================================
 * v2s/brain.js — الجولة الأخيرة · قسم «العقل»: «القواعد وسجل اليوم» (الموديول الوهمي v2s_brain) و«المساعدون» (الموديول القديم ai تحت الغلاف الجديد).
 * ⛔ لا منطق عمل هنا: الصفوف والجمل والأعداد كلها من `V2L.v2sBrain*` (نقية في v2-logic.js). هذا الملف يجلب ويرسم ويربط الأزرار فقط.
 * ⛔ المفتاح مقفول افتراضيًا: الملف يتحمّل دائمًا لكنه لا يرسم شيئًا إلا لو index.html نادى `V2SEC.brain.render` (والغلاف الجديد شغّال).
 * ⛔ الشبكة: محمّلات الداشبورد الموجودة + مسارات `/api/v2/brain/*` + `PUT /api/platform-expert-files/settings` (مفتاح التوزيع، بتأكيد) +
 *   `POST /api/ai/agents/run` من أزرار التشغيل وحدها (قفل واحد: ضغطة ثانية لا ترسل شيئًا). ولا نداء للدالتين الجاهزتين في dashboard-api.js
 *   (تشغيل المساعدين ومفتاح التوزيع) لأن نصوصهما عامية ولا تُرجعان وعدًا نكمل عليه.
 * ⛔ لا زرّ تراجع: لا فعل تلقائي له تراجع حقيقي بعد. الأمر الصادق للتوزيع الذي لم يُستلم هو «أرسله لخبير آخر» من درج الملف.
 * الجولة الثانية (SPEC brain2 §4.4): مجموعة «ما يكتبه العقل» (`/v2/brain/switches` · PUT بتأكيد) · «اكتب الاقتراحات الآن» (`POST /v2/brain/run` بتأكيد) ·
 *   صفوف السجل من `/v2/brain/items` وحذف الملاحظة (`POST …/discard` بتأكيد) · قرصا المساعدين. كل مصدر يفشل لوحده ⇒ «غير متاح بعد» لا صفر.
 * ========================================================================== */
(function () {
  'use strict';
  var L = window.V2L;
  if (!L) return;
  var U = L.util;
  window.V2SEC = window.V2SEC || {};
  var B = window.V2SEC.brain = {};
  var MODS = { v2s_brain: 1, ai: 1 };
  var S = { view: null, mod: '', sig: '', poll: null, minute: null, seg: 'rules', open: {}, expandLog: false, running: null, note: null, noteT: null,
            ruleText: '', ruleErr: '', ruleBusy: false, switchBusy: false, nowOverride: 0, sheetAgent: '', modeBusy: false, wasActive: false };
  var FAIL_AR = 'تعذّر تنفيذ العملية';
  var SESSION_AR = 'انتهت الجلسة. سجّل الدخول من جديد ثم جرّب.';
  var NOREPLY_AR = 'لم يصل رد. حدّث الصفحة وتأكّد مما حدث قبل أن تضغط مرة أخرى.';
  var NA = 'غير متاح بعد';
  var FILE_FORMS = ['ملف واحد', 'ملفان', 'ملفات', 'ملفًا'];
  var DAYS = ['الأحد', 'الاثنين', 'الثلاثاء', 'الأربعاء', 'الخميس', 'الجمعة', 'السبت'];
  var MONTHS = ['يناير', 'فبراير', 'مارس', 'أبريل', 'مايو', 'يونيو', 'يوليو', 'أغسطس', 'سبتمبر', 'أكتوبر', 'نوفمبر', 'ديسمبر'];

  function esc(s) { return String(s == null ? '' : s).replace(/[&<>"']/g, function (c) { return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]; }); }
  function host() { return window.V2_HOST || {}; }
  function ep() { return window.EP || null; }
  function img(name) { return 'v2/img/' + name + '.jpg'; }
  function now() { return S.nowOverride || Date.now(); }
  function q(sel, root) { return (root || document).querySelector(sel); }
  function qa(sel, root) { return Array.prototype.slice.call((root || document).querySelectorAll(sel)); }
  function toast(t) { try { if (typeof window.toast === 'function') window.toast(t); } catch (e) {} }
  function mobile() { return window.innerWidth <= 760; }
  var AV = '<img class="v3-bav" src="' + img('brain-avatar') + '" alt="">';
  B.owns = function (mod) { return !!MODS[mod]; };

  try { var sv = localStorage.getItem('v2sb_seg'); if (sv === 'rules' || sv === 'log') S.seg = sv; } catch (e) {}

  // ------------------------------------------------------------------ مصادر الخادم (كلٌّ تفشل لوحدها)
  var SRC = {};
  var PATHS = {
    today: function () { return '/v2/brain/today?since=' + encodeURIComponent(new Date(L.v2sBrainSince(now())).toISOString()); },
    rules: function () { return '/v2/brain/rules'; },
    status: function () { return '/v2/brain/helpers-status'; },
    switches: function () { return '/v2/brain/switches'; },
    items: function () { return '/v2/brain/items?status=all&since=' + encodeURIComponent(new Date(L.v2sBrainSince(now())).toISOString()); },
    run: function () { return '/v2/brain/runs/latest'; }
  };
  function srcOf(k) { return SRC[k] || (SRC[k] = { state: 'idle', data: null, at: 0, busy: false, status: 0 }); }
  function data(k) { var s = srcOf(k); return s.state === 'ready' ? s.data : null; }
  function srcState(k) { return srcOf(k).state; }
  // quiet = تحديث في الخلفية: يُبقي المعروض ولا يرجع بالشاشة إلى «جارٍ الجلب». أي فشل أثناء التحديث الهادئ يُبقي آخر قراءة سليمة.
  function load(k, force, quiet) {
    var s = srcOf(k), E = ep();
    if (!E || !E.api || !E.authed || !PATHS[k] || s.busy) return;
    if (!force && s.state !== 'idle') return;
    s.busy = true;
    if (!quiet || s.state === 'idle') s.state = 'loading';
    E.api(PATHS[k]()).then(function (d) {
      s.busy = false; s.state = 'ready'; s.data = d; s.at = Date.now(); changed();
    }).catch(function (e) {
      s.busy = false;
      if (e && e.status === 401) return;
      s.at = Date.now();
      if (quiet && s.data) { s.state = 'ready'; changed(); return; }
      s.state = e && e.status === 404 ? 'closed' : 'error'; s.status = (e && e.status) || 0; s.data = null; changed();
    });
  }
  function epState(k) { var E = ep(); return (E && E.state && E.state[k]) || 'idle'; }
  function epReady(k) { return epState(k) === 'ready'; }
  function epEnsure(keys) { var E = ep(); if (E && E.authed) keys.forEach(function (k) { E.ensure(k, null); }); }
  function epReload(keys) { var E = ep(); if (E && E.authed) keys.forEach(function (k) { E.reload(k, null); }); }
  function queue() { var E = ep(); return epReady('opsQueue') ? (E.data.opsQueue || null) : null; }
  function agentsResp() { var E = ep(); return epReady('aiAgents') ? (E.data.aiAgents || null) : null; }
  function inviteSet() { var E = ep(); return epReady('inviteSettings') ? (E.data.inviteSettings || null) : null; }
  function sinceMs() { return L.v2sBrainSince(now()); }
  // مصادر الجولة الثانية: null = لم تصل (جارية أو فاشلة)، لا قيمة مخترعة.
  function swInfo() { return srcState('switches') === 'ready' ? L.v2sBrainSwitches(data('switches'), now()) : null; }
  function itemsList() { return srcState('items') === 'ready' ? L.v2sBrainItems(data('items')) : null; }
  function runState() { return L.v2sBrainRunState(srcState('run') === 'ready' ? data('run') : null, now()); }
  function failedSrc(k) { var st = srcState(k); return st === 'error' || st === 'closed' || (st === 'ready' && (k === 'switches' ? !swInfo() : k === 'items' ? !itemsList() : false)); }
  function pendingSrc(k) { var st = srcState(k); return st === 'idle' || st === 'loading'; }

  // سجل اليوم الواحد لكل المواضع: من B1، وإن فشل فمن صفوف الوارد المفتوحة (ناقص دائمًا ويُعلَن). بلا صفوف في الاحتياط ⇒ null (لا سجل فاضي كاذب).
  function entries() {
    var st = srcState('today');
    if (st === 'idle' || st === 'loading') return null;
    var ent = L.v2sBrainEntries(data('today'), sinceMs());
    if (ent) return ent;
    if (epReady('inbox')) { var fb = L.v2sBrainLogFromInbox(window.INBOX || [], sinceMs()); if (fb && fb.entries.length) return fb; }
    return null;
  }

  function signature() {
    return Object.keys(PATHS).map(function (k) { return srcOf(k).state + srcOf(k).at; }).join(',') + '|' + ['opsQueue', 'inbox', 'aiAgents', 'inviteSettings'].map(epState).join(',')
      + '|' + ((window.INBOX || []).length) + '|' + (S.running ? S.running.id : '') + '|' + S.seg + '|' + (S.ruleBusy ? 1 : 0) + '|' + S.ruleErr;
  }
  var redrawT = null;
  function changed() {
    try { if (window.V2SHELL && V2SHELL.on && V2SHELL.refresh) V2SHELL.refresh(); } catch (e) {}
    if (redrawT) return;
    redrawT = setTimeout(function () { redrawT = null; redraw(); }, 0);
  }

  // ------------------------------------------------------------------ الرقم الواحد للمربّع والقائمة وشاشة الملفات
  B.tileCount = function () {
    if (!window.V2_ON) return undefined;
    var s = srcOf('today');
    if (s.state === 'idle' || (!s.busy && s.state !== 'loading' && Date.now() - s.at > 60000)) load('today', true, true);
    if (s.state === 'ready') { var e = L.v2sBrainEntries(s.data, sinceMs()); return e ? e.autoCount : null; }
    if (s.state === 'error' || s.state === 'closed') return null;
    return undefined;
  };
  B.tilePartial = function () { var e = srcOf('today').state === 'ready' ? L.v2sBrainEntries(srcOf('today').data, sinceMs()) : null; return !!(e && e.partial); };
  B.sig = function () { var s = srcOf('today'); return s.state + ':' + s.at; };

  // ------------------------------------------------------------------ أجزاء مشتركة
  function personLink(name, email) {
    if (!email) return esc(name);
    return '<a class="v2sb-person" href="' + esc(L.sectionHash('people', 'person', email)) + '" data-person="' + esc(email) + '">' + esc(name) + '</a>';
  }
  function setNote(t) {
    S.note = t; clearTimeout(S.noteT);
    S.noteT = setTimeout(function () { S.note = null; redraw(); }, 9000);
  }
  function noteStrip() { return S.note ? '<div class="v3-ok" role="status">' + esc(S.note) + '</div>' : ''; }
  function skeleton(n) {
    var o = '<div class="v2sb-sk" aria-busy="true" aria-label="جارٍ الجلب">';
    for (var i = 0; i < n; i++) o += '<i></i>';
    return o + '</div>';
  }
  function retryBtn(a) { return '<button type="button" class="v3-btn2" data-a="' + a + '">أعد المحاولة</button>'; }
  function arDate(t) { var d = new Date(t); return DAYS[d.getDay()] + ' ' + U.ar(d.getDate()) + ' ' + MONTHS[d.getMonth()]; }
  function discNum(n, least) { return n == null ? NA : (n === 0 ? 'لا شيء' : (least ? 'على الأقل ' : '') + U.ar(n)); }
  function disc(v, label, na) { return '<div class="v2sb-disc' + (na ? ' na' : '') + (String(v).length > 5 ? ' long' : '') + '"><b>' + esc(v) + '</b><span>' + esc(label) + '</span></div>'; }
  function lineHtml(text, btn) {
    return '<div class="v3-brain v2sb-line">' + AV + '<p>' + esc(text) + '</p>' + (btn ? '<button type="button" class="v3-btn2" data-a="goto" data-s="' + esc(btn.section) + '"' + (btn.deck ? ' data-deck="1"' : '') + '>' + esc(btn.label) + '</button>' : '') + '</div>';
  }
  // البريد الإلكتروني داخل جملة عربية يُعزل اتجاهيًا (وإلا يتبعثر ترتيب الكلمات حوله).
  function bidi(t) { return esc(t).replace(/[^\s<>&]+@[^\s<>&]+/g, function (m) { return '<bdi dir="ltr">' + m + '</bdi>'; }); }
  var CHEV = '<svg viewBox="0 0 24 24" class="v2sb-chev" aria-hidden="true"><path d="m6 9 6 6 6-6"/></svg>';

  // ------------------------------------------------------------------ التبويب الأول: القواعد وسجل اليوم
  function rulesInput() { return { settings: data('rules'), queue: queue(), invite: inviteSet(), now: now() }; }
  function controlHtml(r) {
    var c = r.control;
    if (c.type === 'switch') {
      return '<div class="v2sb-sw" role="radiogroup" aria-label="' + esc(r.title) + '">'
        + '<button type="button" role="radio" class="auto" aria-checked="' + (c.value === true) + '" data-a="sw" data-v="1"' + (S.switchBusy ? ' disabled' : '') + '>وحده</button>'
        + '<button type="button" role="radio" class="ask" aria-checked="' + (c.value === false) + '" data-a="sw" data-v="0"' + (S.switchBusy ? ' disabled' : '') + '>يسألني</button></div>';
    }
    return '<span class="v2sb-chip tone-' + esc(c.tone) + '">' + esc(c.label) + '</span>';
  }
  function ruleRow(r) {
    var sw = r.control.type === 'switch';
    return '<div class="v2sb-row' + (sw ? ' has-sw' : '') + (r.stopped ? ' stopped' : '') + '" data-key="' + esc(r.key) + '">'
      + '<button type="button" class="v2sb-rt" data-a="rule" data-key="' + esc(r.key) + '">' + esc(r.title) + '</button>'
      + '<div class="v2sb-ctl">' + (r.stopped && sw ? '<span class="v2sb-chip tone-stop">متوقّف</span>' : '') + controlHtml(r) + '</div>'
      + '<p class="v2sb-st">' + bidi(r.line) + '</p></div>';
  }
  function requestedRow(x) {
    return '<div class="v2sb-row req" data-id="' + esc(x.id) + '"><p class="v2sb-rtx">' + esc(x.text) + '</p>'
      + '<div class="v2sb-ctl"><span class="v2sb-chip tone-na">لم تُبنَ بعد</span><button type="button" class="v3-btn2 v2sb-del" data-a="del" data-id="' + esc(x.id) + '">احذف</button></div>'
      + '<p class="v2sb-st">حُفظت ' + esc(L.util.agoText(L.v2sBrainTime(x.created_at), now()) || NA) + '</p></div>';
  }
  function groupHtml(g, isOpen, count) {
    return '<div class="v2sb-grp' + (isOpen ? ' open' : '') + '"><button type="button" class="v2sb-gh" data-a="grp" data-g="' + esc(g.key) + '" aria-expanded="' + isOpen + '">'
      + '<span class="v2sb-gt">' + esc(g.title) + '</span>' + (count == null ? '' : '<span class="v2sb-gc">' + esc(U.ar(count)) + '</span>') + CHEV + '</button>'
      + (isOpen ? '<div class="v2sb-rows">' + g.rowsHtml + '</div>' : '') + '</div>';
  }
  function isOpen(key) {
    if (S.open[key] !== undefined) return S.open[key];
    if (key === 'writes') return true;
    return mobile() ? key === 'files' : true;
  }
  // —— مجموعة «ما يكتبه العقل»
  function modeRow(r) {
    var radios = r.options.map(function (o) {
      return '<button type="button" role="radio" class="' + esc(o.value) + '" aria-checked="' + o.on + '" data-a="mode" data-id="' + esc(r.id) + '" data-v="' + esc(o.value) + '"' + (S.modeBusy ? ' disabled' : '') + '>' + esc(o.label) + '</button>';
    }).join('');
    return '<div class="v2sb-row has-md' + (r.locked ? ' locked' : '') + '" data-key="w:' + esc(r.id) + '">'
      + '<button type="button" class="v2sb-rt" data-a="mrule" data-id="' + esc(r.id) + '">' + esc(r.title) + '</button>'
      + '<div class="v2sb-ctl"><div class="v2sb-md" role="radiogroup" aria-label="' + esc(r.title) + '">' + radios + '</div></div>'
      + '<p class="v2sb-st">' + bidi(r.line) + '</p></div>';
  }
  function writesGroup() {
    var sw = swInfo(), hint = '<p class="v2sb-hint v2sb-whint">اقتراحات يكتبها العقل من بيانات حقيقية</p>', body, count = null;
    if (pendingSrc('switches')) body = hint + skeleton(2);
    else if (!sw) body = hint + '<div class="v3-warn" role="status">' + NA + '. ما يكتبه العقل لا نعرف حالته الآن. ' + retryBtn('retry-switches') + '</div>';
    else {
      var ri = L.v2sBrainRunInfo(sw, runState(), now());
      count = sw.rows.length;
      body = hint + sw.rows.map(modeRow).join('')
        + '<div class="v2sb-runnow"><button type="button" class="v3-btn2 v2sb-runbtn" data-a="runnow"' + (ri.canStart ? '' : ' disabled') + '>اكتب الاقتراحات الآن</button>'
        + (ri.reason ? '<p class="v2sb-hint v2sb-runwhy" role="status">' + esc(ri.reason) + '</p>' : '') + '</div>';
    }
    return { key: 'writes', title: 'ما يكتبه العقل', count: count, rowsHtml: body };
  }
  function rulesCard() {
    var st = srcState('rules'), res = L.v2sBrainRules(rulesInput());
    var groups = [writesGroup()].concat(res.groups.map(function (g) { return { key: g.key, title: g.title, count: g.rows.length, rowsHtml: g.rows.map(ruleRow).join('') }; }));
    var req = (data('rules') && data('rules').requested) || [];
    if (req.length) groups.push({ key: 'requested', title: 'قواعد طلبتها', count: req.length, rowsHtml: req.map(requestedRow).join('') });
    var warn = (st === 'error' || st === 'closed') ? '<div class="v3-warn" role="status">تعذّر جلب حالة القواعد الآن. ما يظهر «' + NA + '» ليس معناه أنه متوقف. ' + retryBtn('retry-rules') + '</div>' : '';
    var want = '<div class="v2sb-want"><h3>قاعدة تريدها</h3>'
      + '<textarea id="v2sbWant" rows="' + (mobile() ? 2 : 1) + '" maxlength="300" autocomplete="off" aria-label="اكتب القاعدة التي تريدها" placeholder="مثلًا: لا توزّع ملفات الخليج على خبير من مصر"' + (S.ruleBusy ? ' disabled' : '') + '>' + esc(S.ruleText) + '</textarea>'
      + '<p class="v2sb-hint">تُحفظ هنا حتى تُبنى في المنصة، ولا تعمل الآن.</p>'
      + (S.ruleErr ? '<div class="v3-err" role="alert">' + esc(S.ruleErr) + '</div>' : '')
      + '<button type="button" class="v3-btn1" data-a="save" id="v2sbSave"' + (S.ruleBusy || S.ruleText.trim().length < 6 ? ' disabled' : '') + '>' + (S.ruleBusy ? 'جارٍ الحفظ…' : 'احفظها') + '</button></div>';
    return '<section class="v3-card v2sb-rules" aria-label="القواعد"><header class="v3-ch"><h2>القواعد</h2><p>ما يحدث وحده كلما وقع أمر</p></header>' + warn
      + groups.map(function (g) { return groupHtml(g, isOpen(g.key), g.count); }).join('') + want + '</section>';
  }
  function logRowHtml(r, i) {
    var text;
    if (r.kind === 'file') text = esc(r.parts[0]) + personLink(r.parts[1], r.email) + esc(r.parts[2]);
    else text = esc(r.text);
    return '<li class="v2sb-lr' + (r.muted ? ' muted' : '') + '"><time>' + esc(r.time) + '</time><div class="v2sb-lt"><span>' + text + '</span>' + (r.why ? '<small>' + esc(r.why) + '</small>' : '') + '</div>'
      + (r.action ? '<button type="button" class="v2sb-la" data-a="logact" data-i="' + i + '">' + esc(r.action.label) + '</button>' : '') + '</li>';
  }
  function logCard() {
    var ent = entries(), st = srcState('today'), body, notes = '';
    var agents = agentsResp(), items = itemsList(), itemsBad = failedSrc('items');
    var rows = (ent || items) ? L.v2sBrainLogRows(ent, agents ? agents.agents : [], sinceMs(), items) : null;
    S.logRows = rows || [];
    if (ent && ent.fromInbox) notes += '<div class="v3-warn" role="status">من الملفات المفتوحة فقط، وقد يكون السجل ناقصًا</div>';
    else if (ent && ent.missing) notes += '<div class="v3-warn" role="status">سجل التوزيع غير موجود على المنصة بعد</div>';
    else if (ent && ent.partial) notes += '<div class="v3-warn" role="status">معروض أحدث ' + U.ar(200) + ' ملف فقط، وقد يكون في سجل اليوم ما لم يظهر</div>';
    if (itemsBad) notes += '<div class="v3-warn" role="status">ما كتبه العقل اليوم: ' + NA + '. قد يكون السجل ناقصًا. ' + retryBtn('retry-items') + '</div>';
    else if (!ent && items && st !== 'idle' && st !== 'loading') notes += '<div class="v3-warn" role="status">سجل الملفات: ' + NA + '. قد يكون السجل ناقصًا. ' + retryBtn('retry-today') + '</div>';
    if (st === 'idle' || st === 'loading' || (!ent && !items && pendingSrc('items'))) body = skeleton(3);
    else if (!rows) body = '<div class="v3-empty"><b>تعذّر جلب سجل الملفات</b><p>لا نعرف ما وُزّع اليوم، فلا تعتبر السجل فارغًا.</p>' + retryBtn('retry-today') + '</div>';
    else if (ent && ent.missing && !rows.length) body = '<div class="v3-empty v2sb-na"><b>' + NA + '</b><p>لا نعرف ما وُزّع اليوم، فلا تعتبر السجل فارغًا.</p></div>';
    else if (!rows.length && itemsBad) body = '<div class="v3-empty v2sb-na"><b>' + NA + '</b><p>لا نعرف ما كتبه العقل اليوم، فلا تعتبر السجل فارغًا.</p></div>';
    else if (!rows.length) body = '<div class="v3-empty v2sb-empty"><img src="' + img('brain-avatar') + '" alt=""><b>لم يحدث شيء وحده اليوم حتى الآن</b></div>';
    else {
      var shown = S.expandLog ? rows : rows.slice(0, 12);
      body = '<ul class="v2sb-log">' + shown.map(logRowHtml).join('') + '</ul>'
        + (rows.length > 12 && !S.expandLog ? '<button type="button" class="v3-btn2 v2sb-more" data-a="more">اعرض الكل (' + U.ar(rows.length) + ')</button>' : '');
    }
    return '<section class="v3-card v2sb-log-card" aria-label="سجل اليوم"><header class="v3-ch"><h2>سجل اليوم</h2><p>' + esc(arDate(now())) + '</p></header>' + notes + body + '</section>';
  }
  function drawRules(v) {
    var ent = entries(), Q = queue();
    var line = L.v2sBrainLine({ queue: Q, settings: data('rules'), entries: ent, proposed: L.v2sBrainProposed(itemsList()) });
    var loadingAll = ['today', 'rules'].some(function (k) { return srcState(k) === 'idle' || srcState(k) === 'loading'; }) || ['opsQueue', 'inbox'].some(function (k) { return epState(k) === 'idle' || epState(k) === 'loading'; });
    var least = !!(ent && (ent.partial || ent.fromInbox));
    var d1 = ent ? discNum(ent.autoCount, least) : NA, d2 = ent ? discNum(ent.changedCount, least) : NA;
    var seg = '<div class="v3-seg v2sb-seg" role="tablist" aria-label="العرض">'
      + '<button type="button" role="tab" class="v3-pb' + (S.seg === 'rules' ? ' on' : '') + '" aria-selected="' + (S.seg === 'rules') + '" data-a="seg" data-s="rules">القواعد</button>'
      + '<button type="button" role="tab" class="v3-pb' + (S.seg === 'log' ? ' on' : '') + '" aria-selected="' + (S.seg === 'log') + '" data-a="seg" data-s="log">سجل اليوم</button></div>';
    v.innerHTML = '<div class="v3 v2sb" data-board="brain-log" data-seg="' + S.seg + '" data-ready="' + (loadingAll ? 0 : 1) + '">' + noteStrip()
      + '<div class="v3-top v2sb-top">' + (loadingAll && !ent ? lineHtml('…جارٍ جلب ما فعله العقل اليوم', null) : lineHtml(line.text, line.button))
      + '<div class="v2sb-discs">' + disc(d1, 'وُزّع وحده اليوم', !ent) + disc(d2, 'غيّرت خبيره يدويًا', !ent) + '</div></div>'
      + seg + '<div class="v2sb-cols">' + rulesCard() + logCard() + '</div></div>';
    wire(v);
  }

  // ------------------------------------------------------------------ التبويب الثاني: المساعدون
  function runLabel(c, base) { return S.running && S.running.id === c.id ? 'جارٍ الكتابة…' : base; }
  function helperCard(c) {
    var when = c.createdMs != null ? 'آخر تحديث: ' + U.agoText(c.createdMs, now()) : '';
    return '<article class="v2sb-hc" data-id="' + esc(c.id) + '"><div class="v2sb-hph" style="background-image:url(' + img(c.img) + ')"></div><div class="v2sb-hb"><h3>' + esc(c.label) + '</h3>'
      + '<p class="v2sb-hd">' + esc(c.desc) + '</p>'
      + (c.hasReport ? '<p class="v2sb-hw">' + esc(when) + (c.dataOnly ? ' <span class="v2sb-chip tone-na">أرقام فقط</span>' : '') + '</p><p class="v2sb-hs" dir="auto">' + esc(c.summary) + '</p>'
        : '<p class="v2sb-hw">لم يكتب تقريرًا بعد</p>')
      + '<div class="v2sb-hact">' + (c.hasReport ? '<button type="button" class="v3-btn2" data-a="hview" data-id="' + esc(c.id) + '">اعرض</button>' : '')
      + '<button type="button" class="v3-btn2 v2sb-run" data-a="hrun" data-run="' + esc(c.id) + '" data-label="حدّث"' + (c.canRun ? '' : ' disabled') + '>' + esc(runLabel(c, 'حدّث')) + '</button></div></div></article>';
  }
  function masterCard(H) {
    var m = H.master;
    if (!m) return '';
    var when = m.createdMs != null ? 'آخر تحديث: ' + U.agoText(m.createdMs, now()) : '';
    var acts = m.actions.slice(0, 3);
    return '<section class="v3-card v2sb-master" aria-label="الصورة الكاملة"><header class="v3-ch"><h2>الصورة الكاملة</h2><p>' + esc(m.desc) + '</p></header>'
      + (m.hasReport ? '<p class="v2sb-ms" dir="auto">' + esc(m.summary) + '</p>' + (acts.length ? '<h3 class="v2sb-sg">اقتراحات</h3><ul class="v2sb-acts">' + acts.map(function (a) { return '<li dir="auto">' + esc(a) + '</li>'; }).join('') + '</ul>' : '')
          + '<p class="v2sb-hw">' + esc(when) + (m.dataOnly ? ' <span class="v2sb-chip tone-na">أرقام فقط</span>' : '') + '</p>'
        : '<p class="v2sb-none">لم تُكتب بعد. حدّثها بعد أن يكتب المساعدون تقاريرهم.</p>')
      + '<button type="button" class="v3-btn1 v2sb-run" data-a="hrun" data-run="master" data-label="حدّث الصورة الكاملة"' + (m.canRun ? '' : ' disabled') + '>' + esc(runLabel(m, 'حدّث الصورة الكاملة')) + '</button></section>';
  }
  // قرصا «من يكتب الآن» و«كتابات العقل اليوم»: كل واحد من مصدره، والفاشل «غير متاح بعد».
  function writerDiscs() {
    var stt = data('status'), sw = swInfo(), writer, known = false;
    if (stt && Object.prototype.hasOwnProperty.call(stt, 'writer') && (stt.writer === null || stt.writer === 'main' || stt.writer === 'backup')) { writer = stt.writer; known = true; }
    else if (sw && sw.writer !== undefined) { writer = sw.writer; known = true; }
    var w = L.v2sBrainWriterText(writer, known), t = L.v2sBrainWritesToday(sw ? sw.brainToday : null);
    return '<div class="v2sb-discs v2sb-wdiscs">' + disc(w, 'من يكتب الآن', w === NA) + disc(t, 'كتابات العقل اليوم', t === NA) + '</div>';
  }
  function drawHelpers(v) {
    var A = agentsResp(), st = data('status'), H = A ? L.v2sBrainHelpers(A, st, S.running ? S.running.id : null) : null;
    var loading = epState('aiAgents') === 'idle' || epState('aiAgents') === 'loading';
    var head, body, wd = writerDiscs();
    if (loading) { head = lineHtml('…جارٍ جلب تقارير المساعدين', null); body = '<div class="v2sb-grid">' + skeleton(1) + skeleton(1) + skeleton(1) + '</div>'; }
    else if (!H) {
      head = '<div class="v2sb-hl">' + lineHtml('تعذّر جلب تقارير المساعدين', null) + wd + '</div>';
      body = '<div class="v3-empty"><b>تعذّر جلب تقارير المساعدين</b><p>لا نعرف ما كتبوه، فلا تعتبر الشاشة فارغة.</p>' + retryBtn('retry-agents') + '</div>';
    } else {
      var all = '<button type="button" class="v3-btn2 v2sb-run" data-a="hall" data-run="all" data-label="حدّث الكل"' + (H.canRunAll ? '' : ' disabled') + (H.runAllReason ? ' title="' + esc(H.runAllReason) + '"' : '') + '>' + (S.running && S.running.id === 'all' ? 'جارٍ الكتابة…' : 'حدّث الكل') + '</button>';
      head = '<div class="v2sb-hl">' + lineHtml(L.v2sBrainHelpersLine(H, st, now()), null) + '<div class="v2sb-hdisc">' + disc(L.v2sBrainCap(st), 'تحديثات اليوم', !st) + all + '</div>' + wd + '</div>'
        + (H.runAllReason ? '<p class="v2sb-why">' + esc(H.runAllReason) + '</p>' : '');
      body = masterCard(H) + '<div class="v2sb-grid">' + H.cards.filter(function (c) { return c.id !== 'master'; }).map(helperCard).join('') + '</div>';
    }
    v.innerHTML = '<div class="v3 v2sb v2sb-helpers" data-board="brain-helpers" data-ready="' + (loading ? 0 : 1) + '">' + noteStrip() + '<div class="v3-top v2sb-top">' + head + '</div>' + body + '</div>';
    S.H = H;
    wire(v);
  }

  // ------------------------------------------------------------------ الأوراق
  function errMsg(e) {
    if (e && e.status === 401) return SESSION_AR;
    var d = (e && e.data) || {};
    if (typeof d.error === 'string' && d.error) return d.error.replace(/\d/g, function (c) { return '٠١٢٣٤٥٦٧٨٩'.charAt(+c); });
    return FAIL_AR;
  }
  function openSheet(title, html) {
    if (typeof window.openModal !== 'function') return null;
    var s = window.openModal(title, '<div class="v3m v2sbm">' + html + '</div>');
    var x = q('[data-x]', s);
    if (x) x.onclick = function () { if (!s.dataset.busy) { S.sheetAgent = ''; window.closeModal(); } };
    s.onclick = function (e) { if (e.target === s && !s.dataset.busy) { S.sheetAgent = ''; window.closeModal(); } };
    return s;
  }
  function closeSheet() { S.sheetAgent = ''; window.closeModal(); }
  function sectionBlock(h, body) { return '<div class="v2sb-sec"><h3>' + esc(h) + '</h3>' + body + '</div>'; }

  // —— ورقة قاعدة
  function openRule(key) {
    var res = L.v2sBrainRules(rulesInput()), r = res.rows.filter(function (x) { return x.key === key; })[0];
    if (!r) return;
    var body = sectionBlock('متى يعمل', '<p>' + esc(r.sentence) + '</p>')
      + sectionBlock('آخر تشغيل', '<p>' + bidi(String(r.runKey ? r.run.text : r.line).replace(/^آخر تشغيل: /, '')) + '</p>')
      + (key === 'assign' && r.line !== r.run.text ? sectionBlock('آخر تغيير', '<p>' + bidi(String(r.line).replace(/^آخر تغيير: /, '')) + '</p>') : '');
    if (key === 'assign') {
      var hist = ((data('rules') && data('rules').history) || []).filter(function (h) { return h.action === 'expert_file.auto_assign'; });
      body += sectionBlock('تاريخ التغيير', hist.length ? '<ul class="v2sb-hist">' + hist.map(function (h) {
        var on = h.meta && h.meta.auto_assign === true;
        return '<li>' + esc((U.agoText(L.v2sBrainTime(h.at), now()) || NA) + ' — ' + (on ? 'شُغّل' : 'أُوقف') + ' بواسطة ') + '<bdi dir="ltr">' + esc(h.actor_email) + '</bdi></li>';
      }).join('') + '</ul>' : '<p>لم يتغيّر من هذه اللوحة</p>');
    }
    if (key === 'release') body += sectionBlock('المهلة', '<p>' + (r.hours ? esc(U.U(r.hours, ['ساعة', 'ساعتان', 'ساعات', 'ساعة'])) : NA) + '</p>');
    body += sectionBlock('أين ترى نتيجته', '<button type="button" class="v3-btn2" id="v2sbGo">' + esc(r.link.label) + '</button>')
      + '<div class="acts"><button type="button" class="btn btn-ghost" id="v2sbX">إغلاق</button></div>';
    var s = openSheet(r.title, body);
    if (!s) return;
    q('#v2sbX', s).onclick = closeSheet;
    q('#v2sbGo', s).onclick = function () { closeSheet(); if (host().openSection) host().openSection(r.link.section, r.link.tab || undefined); };
  }

  // —— ورقة قاعدة من «ما يكتبه العقل»
  function swRow(id) { var sw = swInfo(); return sw ? sw.rows.filter(function (r) { return r.id === id; })[0] || null : null; }
  function openModeRule(id) {
    var r = swRow(id);
    if (!r) return;
    var cur = r.options.filter(function (o) { return o.on; })[0];
    var body = sectionBlock('متى يعمل', '<p>' + esc(r.sentence) + '</p>')
      + sectionBlock('اختيارك الآن', '<p>' + esc(cur ? cur.label : NA) + '</p>')
      + (r.locked ? sectionBlock('لماذا لا يعمل وحده', '<p>' + esc(r.lockReason) + '</p>') : '')
      + (r.link ? sectionBlock('أين ترى نتيجته', '<button type="button" class="v3-btn2" id="v2sbGo">' + esc(r.link.label) + '</button>') : '')
      + '<div class="acts"><button type="button" class="btn btn-ghost" id="v2sbX">إغلاق</button></div>';
    var s = openSheet(r.title, body);
    if (!s) return;
    q('#v2sbX', s).onclick = closeSheet;
    var go = q('#v2sbGo', s);
    if (go) go.onclick = function () { closeSheet(); if (host().openSection) host().openSection(r.link.section); };
  }

  // —— تأكيد تغيير ما يكتبه العقل
  function openMode(id, mode) {
    var r = swRow(id), E = ep();
    if (!r || !E) return;
    var sh = L.v2sBrainSwitchSheet(r, mode);
    var s = openSheet(sh.title, '<p class="mc-lead">' + esc(sh.lead) + '</p><div id="v2sbErr" role="alert"></div>'
      + '<div class="acts"><button type="button" class="btn btn-human" id="v2sbGo">' + esc(sh.go) + '</button><button type="button" class="btn btn-ghost" id="v2sbNo">رجوع</button></div>');
    if (!s) return;
    var go = q('#v2sbGo', s), no = q('#v2sbNo', s);
    no.onclick = function () { if (!s.dataset.busy) closeSheet(); };
    go.onclick = function () {
      if (s.dataset.busy) return;
      s.dataset.busy = '1'; S.modeBusy = true; go.disabled = true; no.disabled = true; go.textContent = 'جارٍ الحفظ…';
      E.api('/v2/brain/switches/' + encodeURIComponent(id), { method: 'PUT', body: { mode: mode, confirmed: true } }).then(function () {
        S.modeBusy = false; delete s.dataset.busy;
        var d = data('switches'), list = d && (Array.isArray(d) ? d : (d.switches || d.producers));
        if (Array.isArray(list)) list.forEach(function (p) { if (p && p.id === id) p.mode = mode; });     // يظهر الاختيار فورًا، ثم تأتي القراءة الأحدث
        closeSheet(); toast('حُفظ الاختيار'); load('switches', true, true); redraw(true);
      }).catch(function (e) {
        S.modeBusy = false; delete s.dataset.busy;
        var box = q('#v2sbErr', s); if (box) box.innerHTML = '<div class="v3-err">' + esc(errMsg(e)) + '</div>';
        go.disabled = false; no.disabled = false; go.textContent = sh.go; redraw();
      });
    };
  }

  // —— حذف ملاحظة كتبها العقل (هذا هو التراجع الحقيقي الوحيد: الملاحظة نصّ فقط)
  function openDiscard(id) {
    var E = ep();
    var s = openSheet('حذف الملاحظة', '<p class="mc-lead">تُحذف هذه الملاحظة. لم تغيّر شيئًا في المنصة.</p><div id="v2sbErr" role="alert"></div>'
      + '<div class="acts"><button type="button" class="btn btn-human" id="v2sbGo">احذفها</button><button type="button" class="btn btn-ghost" id="v2sbNo">رجوع</button></div>');
    if (!s || !E) return;
    var go = q('#v2sbGo', s), no = q('#v2sbNo', s);
    no.onclick = function () { if (!s.dataset.busy) closeSheet(); };
    go.onclick = function () {
      if (s.dataset.busy) return;
      s.dataset.busy = '1'; go.disabled = true; no.disabled = true; go.textContent = 'جارٍ الحذف…';
      E.api('/v2/brain/items/' + encodeURIComponent(id) + '/discard', { method: 'POST', body: { confirmed: true } }).then(function () {
        delete s.dataset.busy; closeSheet(); toast('حُذفت الملاحظة'); load('items', true, true);
      }).catch(function (e) {
        delete s.dataset.busy; go.disabled = false; no.disabled = false; go.textContent = 'احذفها';
        var box = q('#v2sbErr', s); if (box) box.innerHTML = '<div class="v3-err">' + esc(errMsg(e)) + '</div>';
        load('items', true, true);
      });
    };
  }

  // —— «اكتب الاقتراحات الآن»
  function openRunNow() {
    var ri = L.v2sBrainRunInfo(swInfo(), runState(), now()), E = ep();
    if (!ri.canStart || !E) return;
    var s = openSheet('اكتب الاقتراحات الآن', '<p class="mc-lead">' + esc(ri.lead) + '</p><div id="v2sbErr" role="alert"></div>'
      + '<div class="acts"><button type="button" class="btn btn-human" id="v2sbGo">نعم، ابدأ</button><button type="button" class="btn btn-ghost" id="v2sbNo">رجوع</button></div>');
    if (!s) return;
    var go = q('#v2sbGo', s), no = q('#v2sbNo', s);
    no.onclick = function () { if (!s.dataset.busy) closeSheet(); };
    go.onclick = function () {
      if (s.dataset.busy) return;
      s.dataset.busy = '1'; go.disabled = true; no.disabled = true; go.textContent = 'جارٍ البدء…';
      E.api('/v2/brain/run', { method: 'POST', body: { confirmed: true } }).then(function () {
        delete s.dataset.busy;
        var sr = srcOf('run'); sr.state = 'ready'; sr.at = Date.now(); sr.data = { run: { started_at: new Date(now()).toISOString(), finished_at: null } };
        S.wasActive = true;
        closeSheet(); toast('بدأ العقل الكتابة'); redraw(true);
      }).catch(function (e) {
        delete s.dataset.busy; go.disabled = false; no.disabled = false; go.textContent = 'نعم، ابدأ';
        var box = q('#v2sbErr', s); if (box) box.innerHTML = '<div class="v3-err">' + esc(errMsg(e)) + '</div>';
        load('run', true, true);
      });
    };
  }

  // «ابدأ القرارات»: القسم الرئيسي ثم زرّ البدء نفسه حين يظهر (لا مدخل آخر لبطاقات القرار).
  function startDeck() {
    if (host().openSection) host().openSection('home');
    var tries = 0;
    (function tick() {
      if (!(host().isHome && host().isHome())) { if (++tries < 30) setTimeout(tick, 150); return; }
      var b = q('.v2 [data-a="start"]');
      if (b) { b.click(); return; }
      if (++tries < 30) setTimeout(tick, 150);
    })();
  }

  // —— تأكيد مفتاح التوزيع
  function reloadAfterSwitch() {
    load('rules', true, true); load('today', true, true);
    epReload(['inbox', 'opsQueue']);
  }
  function openSwitch(toAuto) {
    var Q = queue(), waiting = Q && typeof Q.expert_files_awaiting_assignment === 'number' ? Q.expert_files_awaiting_assignment : 0;
    var body;
    if (!toAuto) body = '<p class="mc-lead">إذا أوقفته، ينتظر كل ملف يُدفع بعد الآن أن توزّعه بنفسك، ولن تُرسل الملفات المنتظرة الآن وحدها. ويصلك تنبيه عن كل ملف لم يُستلم.</p>';
    else body = '<p class="mc-lead">إذا شغّلته، يُرسل كل ملف مدفوع ينتظر الآن، وكل ملف يُدفع بعده، إلى أنسب خبير متاح وحده. ويمكنك إرسال أي ملف إلى خبير آخر قبل أن يستلمه.</p>'
      + (waiting > 0 ? '<p class="v2sb-wait">ينتظر الآن: ' + esc(U.U(waiting, ['ملف واحد', 'ملفان', 'ملفات', 'ملفًا'])) + '</p>' : '');
    var s = openSheet(toAuto ? 'تشغيل التوزيع التلقائي' : 'إيقاف التوزيع التلقائي', body + '<div id="v2sbErr" role="alert"></div>'
      + '<div class="acts"><button type="button" class="btn btn-human" id="v2sbGo">' + (toAuto ? 'نعم، شغّله' : 'نعم، أوقفه') + '</button><button type="button" class="btn btn-ghost" id="v2sbNo">رجوع</button></div>');
    if (!s) return;
    var go = q('#v2sbGo', s), no = q('#v2sbNo', s), E = ep();
    no.onclick = function () { if (!s.dataset.busy) closeSheet(); };
    go.onclick = function () {
      if (s.dataset.busy || go.dataset.dead) return;
      s.dataset.busy = '1'; S.switchBusy = true; go.disabled = true; no.disabled = true; go.textContent = 'جارٍ الحفظ…';
      E.api('/platform-expert-files/settings', { method: 'PUT', body: { auto_assign: toAuto, confirmed: true } }).then(function (r) {
        var on = r && typeof r.auto_assign === 'boolean' ? r.auto_assign : toAuto;
        E.data.efSettings = { auto_assign: on };
        S.switchBusy = false; delete s.dataset.busy; closeSheet();
        toast(on ? 'شُغّل التوزيع التلقائي' : 'أُوقف التوزيع التلقائي');
        reloadAfterSwitch(); redraw();
      }).catch(function (e) {
        S.switchBusy = false; delete s.dataset.busy;
        var st = e && e.status, lost = !st || st >= 500;
        var box = q('#v2sbErr', s);
        if (box) box.innerHTML = '<div class="v3-err">' + esc(lost ? NOREPLY_AR : errMsg(e)) + '</div>';
        no.disabled = false; go.textContent = toAuto ? 'نعم، شغّله' : 'نعم، أوقفه';
        if (lost) { go.dataset.dead = '1'; go.disabled = true; reloadAfterSwitch(); } else go.disabled = false;
        redraw();
      });
    };
  }

  // —— حذف قاعدة طلبها المؤسس
  function openDelete(id) {
    var s = openSheet('حذف القاعدة', '<p class="mc-lead">تُحذف هذه القاعدة من القائمة. لم تكن تعمل، فلن يتغيّر شيء في المنصة.</p><div id="v2sbErr" role="alert"></div>'
      + '<div class="acts"><button type="button" class="btn btn-human" id="v2sbGo">احذفها</button><button type="button" class="btn btn-ghost" id="v2sbNo">رجوع</button></div>');
    if (!s) return;
    var go = q('#v2sbGo', s), no = q('#v2sbNo', s), E = ep();
    no.onclick = function () { if (!s.dataset.busy) closeSheet(); };
    go.onclick = function () {
      if (s.dataset.busy) return;
      s.dataset.busy = '1'; go.disabled = true; no.disabled = true; go.textContent = 'جارٍ الحذف…';
      E.api('/v2/brain/rules/' + encodeURIComponent(id), { method: 'DELETE', body: { confirmed: true } }).then(function () {
        delete s.dataset.busy; closeSheet(); toast('حُذفت القاعدة'); load('rules', true, true);
      }).catch(function (e) {
        delete s.dataset.busy; go.disabled = false; no.disabled = false; go.textContent = 'احذفها';
        var box = q('#v2sbErr', s); if (box) box.innerHTML = '<div class="v3-err">' + esc(errMsg(e)) + '</div>';
      });
    };
  }

  // —— حفظ قاعدة تريدها (ضغطة واحدة، بلا ورقة تأكيد: لا فلوس ولا شيء يتغيّر في المنصة)
  function saveRule() {
    var E = ep(), text = S.ruleText.trim();
    if (S.ruleBusy || text.length < 6 || !E) return;
    S.ruleBusy = true; S.ruleErr = ''; redraw(true);
    E.api('/v2/brain/rules', { method: 'POST', body: { text: text, confirmed: true } }).then(function () {
      S.ruleBusy = false; S.ruleText = ''; S.ruleErr = ''; S.open.requested = true;
      toast('حُفظت القاعدة'); load('rules', true, true); redraw(true);
    }).catch(function (e) {
      S.ruleBusy = false; S.ruleErr = errMsg(e); redraw(true);
    });
  }

  // —— تقرير مساعد
  function fillHelperSheet(s, id) {
    var H = L.v2sBrainHelpers(agentsResp(), data('status'), S.running ? S.running.id : null);
    var c = H && H.cards.filter(function (x) { return x.id === id; })[0];
    var box = q('.v2sbm', s);
    if (!c || !box) return;
    box.innerHTML = '<div class="v3-brain v2sb-line">' + AV + '<p dir="auto">' + esc(c.hasReport ? c.summary : 'لم يكتب تقريرًا بعد') + '</p></div>'
      + '<p class="v2sb-by">كتبه المساعد</p>'
      + sectionBlock('ما لاحظه', c.bullets.length ? '<ul class="v2sb-hist" dir="auto">' + c.bullets.map(function (b) { return '<li>' + esc(b) + '</li>'; }).join('') + '</ul>' : '<p>لا ملاحظات</p>')
      + sectionBlock('ما يقترحه', c.actions.length ? '<ul class="v2sb-hist" dir="auto">' + c.actions.map(function (b) { return '<li>' + esc(b) + '</li>'; }).join('') + '</ul>' : '<p>لا اقتراحات</p>')
      + (c.createdMs != null ? '<p class="v2sb-st">آخر تحديث: ' + esc(U.agoText(c.createdMs, now())) + '</p>' : '')
      + '<div class="acts"><button type="button" class="btn btn-human v2sb-run" data-run="' + esc(id) + '" data-label="حدّث هذا التقرير" id="v2sbRun"' + (c.canRun ? '' : ' disabled') + '>' + esc(runLabel(c, 'حدّث هذا التقرير')) + '</button>'
      + '<button type="button" class="btn btn-ghost" id="v2sbX">إغلاق</button></div>';
    q('#v2sbX', s).onclick = closeSheet;
    q('#v2sbRun', s).onclick = function () { runAgent(id); };
  }
  function openHelper(id) {
    var H = L.v2sBrainHelpers(agentsResp(), data('status'), S.running ? S.running.id : null);
    var c = H && H.cards.filter(function (x) { return x.id === id; })[0];
    if (!c) return;
    var s = openSheet('تقرير: ' + c.label, '');
    if (!s) return;
    S.sheetAgent = id;
    fillHelperSheet(s, id);
  }

  // —— تشغيل المساعدين (قفل واحد على الصفحتين والأوراق)
  function syncRunButtons() {
    var H = S.H, st = data('status'), blocked = !!(st && st.blocked);
    qa('[data-run]').forEach(function (b) {
      var id = b.getAttribute('data-run'), base = b.getAttribute('data-label') || b.textContent;
      var mine = S.running && S.running.id === id;
      var off = !!S.running || blocked || (id === 'all' && H && !H.canRunAll && !S.running);
      b.disabled = off;
      b.textContent = mine ? 'جارٍ الكتابة…' : base;
    });
  }
  function runAgent(id) {
    var E = ep();
    if (S.running || !E) return;
    S.running = { id: id, since: Date.now() };
    syncRunButtons();
    var allSheet = q('#v2sbAllGo'); if (allSheet) { allSheet.disabled = true; allSheet.textContent = 'جارٍ الكتابة…'; }
    var info = L.v2sBrainAgentInfo(id, id, '');
    var reply = [];
    E.api('/ai/agents/run?agent=' + encodeURIComponent(id), { method: 'POST', body: {} }).then(function (r) {
      var k = (r && r.agents && r.agents.length) || 0;
      reply = (r && r.agents) || [];
      if (id === 'all') toast(k ? 'كُتبت ' + U.U(k, ['تقرير واحد', 'تقريران', 'تقارير', 'تقريرًا']) : 'لم يُكتب أي تقرير');
      else toast(k ? 'كُتب تقرير «' + info.label + '»' : 'لم يُكتب أي تقرير');
    }).catch(function (e) {
      toast(e && e.data && typeof e.data.error === 'string' && e.data.error ? errMsg(e) : 'تعذّر كتابة التقارير الآن');
    }).then(function () {
      S.running = null;
      if (id === 'all' && q('#v2sbAllGo')) closeSheet();
      load('status', true, true);
      syncRunButtons();
      // إعادة جلب هادئة: تُبقي التقارير المعروضة حتى يصل الجديد (لا وميض «جارٍ الجلب» بعد كل تشغيل).
      E.api('/ai/agents').then(function (r) {
        var list = (r && r.agents) || [];
        // القائمة المخزَّنة لا تحمل مصدر التقرير، وردّ التشغيل يحمله: نحفظه على الصفوف التي كُتبت الآن (يضيع عند تحديث الصفحة).
        reply.forEach(function (x) { list.forEach(function (a) { if (x && a.agent === x.agent) { a.source = x.source; a.ai_unavailable = x.ai_unavailable; } }); });
        E.data.aiAgents = { agents: list, ai_configured: !!(r && r.ai_configured) }; E.state.aiAgents = 'ready';
      }).catch(function () {}).then(function () { afterRun(); });
    });
  }
  function afterRun() {
    var s = document.getElementById('epModal');
    if (s && S.sheetAgent) fillHelperSheet(s, S.sheetAgent);
    redraw(true);
  }
  function openRunAll() {
    var H = S.H;
    if (!H || !H.canRunAll) return;
    var s = openSheet('تحديث كل التقارير', '<p class="mc-lead">' + esc(L.v2sBrainConfirmAll(H)) + '</p><div class="acts"><button type="button" class="btn btn-human" id="v2sbAllGo">نعم، حدّثها كلها</button><button type="button" class="btn btn-ghost" id="v2sbNo">رجوع</button></div>');
    if (!s) return;
    q('#v2sbNo', s).onclick = function () { if (!S.running) closeSheet(); };
    q('#v2sbAllGo', s).onclick = function () { runAgent('all'); };
  }

  // ------------------------------------------------------------------ ربط الأحداث
  function openFile(entry) {
    var rows = window.INBOX || [], row = null;
    for (var i = 0; i < rows.length; i++) if (rows[i] && (rows[i].apiId === entry.file_id || (rows[i].ef && rows[i].ef.id === entry.file_id))) { row = rows[i]; break; }
    if (row && host().openRowAt) host().openRowAt('files', 'all', row);
    else if (host().openSection) host().openSection('files');
  }
  function wire(v) {
    v.onclick = function (e) {
      var b = e.target.closest ? e.target.closest('[data-a]') : null;
      if (!b || !v.contains(b) || b.disabled) return;
      var a = b.getAttribute('data-a');
      if (a === 'goto') { if (b.getAttribute('data-deck')) startDeck(); else if (host().openSection) host().openSection(b.getAttribute('data-s')); }
      else if (a === 'mode') {
        var mr = swRow(b.getAttribute('data-id')), mv = b.getAttribute('data-v');
        if (!mr || S.modeBusy || b.getAttribute('aria-checked') === 'true') return;
        openMode(mr.id, mv);
      }
      else if (a === 'mrule') openModeRule(b.getAttribute('data-id'));
      else if (a === 'runnow') openRunNow();
      else if (a === 'retry-switches') { load('switches', true); }
      else if (a === 'retry-items') { load('items', true); }
      else if (a === 'seg') { S.seg = b.getAttribute('data-s'); try { localStorage.setItem('v2sb_seg', S.seg); } catch (x) {} redraw(true); }
      else if (a === 'grp') { var g = b.getAttribute('data-g'); S.open[g] = !isOpen(g); redraw(true); }
      else if (a === 'rule') openRule(b.getAttribute('data-key'));
      else if (a === 'sw') {
        var want = b.getAttribute('data-v') === '1', cur = (data('rules') || {}).auto_assign;
        if (cur && cur.value === want) return;
        openSwitch(want);
      }
      else if (a === 'save') saveRule();
      else if (a === 'del') openDelete(b.getAttribute('data-id'));
      else if (a === 'more') { S.expandLog = true; redraw(true); }
      else if (a === 'retry-today') { load('today', true); }
      else if (a === 'retry-rules') { load('rules', true); epReload(['opsQueue']); }
      else if (a === 'retry-agents') { epReload(['aiAgents']); }
      else if (a === 'logact') {
        var r = (S.logRows || [])[+b.getAttribute('data-i')];
        if (!r) return;
        if (r.kind === 'report') openHelper(r.agent);
        else if (r.kind === 'item') { if (r.action && r.action.kind === 'discard') openDiscard(r.id); else if (host().openSection) host().openSection(r.section || 'home'); }
        else openFile(r.entry);
      }
      else if (a === 'hview') openHelper(b.getAttribute('data-id'));
      else if (a === 'hrun') runAgent(b.getAttribute('data-run'));
      else if (a === 'hall') openRunAll();
    };
    v.oninput = function (e) {
      if (e.target && e.target.id === 'v2sbWant') {
        S.ruleText = e.target.value; S.ruleErr = '';
        var sv = q('#v2sbSave', v); if (sv) sv.disabled = S.ruleBusy || S.ruleText.trim().length < 6;
        var er = q('.v2sb-want .v3-err', v); if (er) er.remove();
      }
    };
    v.onkeydown = function (e) {
      if (e.key === 'Enter' && e.target && e.target.id === 'v2sbWant') { e.preventDefault(); saveRule(); }
    };
  }

  // ------------------------------------------------------------------ نقطة الدخول
  var NEEDS = {
    v2s_brain: { ep: ['opsQueue', 'inbox', 'aiAgents', 'inviteSettings'], src: ['today', 'rules', 'switches', 'items', 'run'] },
    ai: { ep: ['aiAgents'], src: ['status', 'switches'] }
  };
  function ensureFor(mod) {
    var n = NEEDS[mod];
    if (!n) return;
    epEnsure(n.ep); n.src.forEach(function (k) { load(k, false); });
  }
  function redraw(force) {
    if (!S.view || !host().current || !B.owns(host().current())) return;
    S.mod = host().current();
    // لا نعيد رسم الصفحة تحت ورقة مفتوحة، ولا والمؤسس يكتب في خانة القاعدة (يضيع المؤشر)
    if (document.getElementById('epModal') && !force) return;
    var a = document.activeElement;
    if (!force && a && a.id === 'v2sbWant') return;
    var keepFocus = a && a.id === 'v2sbWant' ? { s: a.selectionStart, e: a.selectionEnd } : null;
    var sc = q('.content'), y = sc ? sc.scrollTop : 0;
    if (S.mod === 'ai') drawHelpers(S.view); else drawRules(S.view);
    if (keepFocus) { var inp = q('#v2sbWant', S.view); if (inp) { inp.focus(); try { inp.setSelectionRange(keepFocus.s, keepFocus.e); } catch (e) {} } }
    if (sc && sc.scrollTop !== y) sc.scrollTop = y;
    S.sig = signature();
    syncRunButtons();
  }
  // جولة الكتابة قيد العمل: نسأل عنها كل بضع ثوانٍ، وحين تنتهي نقرأ المكتوب والعدّاد من جديد.
  function watchRun() {
    if (S.mod !== 'v2s_brain') return;
    var rs = runState(), sr = srcOf('run');
    if (rs.active) {
      S.wasActive = true;
      if (!sr.busy && Date.now() - sr.at > 4000) load('run', true, true);
    } else if (S.wasActive && rs.known) {
      S.wasActive = false; load('items', true, true); load('switches', true, true);
    }
  }
  B.render = function (mod, view) {
    S.view = view; S.mod = mod;
    ensureFor(mod);
    redraw(true);
    if (!S.poll) {
      S.poll = setInterval(function () {
        if (!(host().current && B.owns(host().current()))) return;
        watchRun();
        if (document.getElementById('epModal')) return;
        if (signature() !== S.sig) redraw();
      }, 400);
    }
    if (!S.minute) S.minute = setInterval(function () {
      if (host().current && B.owns(host().current()) && !document.getElementById('epModal')) {
        if (S.mod === 'v2s_brain') { load('today', true, true); load('items', true, true); load('switches', true, true); load('run', true, true); }
        redraw();
      }
    }, 60000);
  };
  B._state = S;
  B._src = SRC;
  B._tick = function (t) { S.nowOverride = t || 0; redraw(true); };
})();
