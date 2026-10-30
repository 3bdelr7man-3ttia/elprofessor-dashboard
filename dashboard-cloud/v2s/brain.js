/* ============================================================================
 * v2s/brain.js — الجولة الأخيرة · قسم «العقل»: «القواعد وسجل اليوم» (الموديول الوهمي v2s_brain) و«المساعدون» (الموديول القديم ai تحت الغلاف الجديد).
 * ⛔ لا منطق عمل هنا: الصفوف والجمل والأعداد كلها من `V2L.v2sBrain*` (نقية في v2-logic.js). هذا الملف يجلب ويرسم ويربط الأزرار فقط.
 * ⛔ المفتاح مقفول افتراضيًا: الملف يتحمّل دائمًا لكنه لا يرسم شيئًا إلا لو index.html نادى `V2SEC.brain.render` (والغلاف الجديد شغّال).
 * ⛔ الشبكة: محمّلات الداشبورد الموجودة + مسارات `/api/v2/brain/*` + `PUT /api/platform-expert-files/settings` (مفتاح التوزيع، بتأكيد) +
 *   `POST /api/ai/agents/run` من أزرار التشغيل وحدها (قفل واحد: ضغطة ثانية لا ترسل شيئًا). ولا نداء للدالتين الجاهزتين في dashboard-api.js
 *   (تشغيل المساعدين ومفتاح التوزيع) لأن نصوصهما عامية ولا تُرجعان وعدًا نكمل عليه.
 * ⛔ لا زرّ تراجع: لا فعل تلقائي له تراجع حقيقي بعد. الأمر الصادق للتوزيع الذي لم يُستلم هو «أرسله لخبير آخر» من درج الملف.
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
            ruleText: '', ruleErr: '', ruleBusy: false, switchBusy: false, nowOverride: 0, sheetAgent: '' };
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
    status: function () { return '/v2/brain/helpers-status'; }
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
    return '<div class="v3-brain v2sb-line">' + AV + '<p>' + esc(text) + '</p>' + (btn ? '<button type="button" class="v3-btn2" data-a="goto" data-s="' + esc(btn.section) + '">' + esc(btn.label) + '</button>' : '') + '</div>';
  }
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
      + '<p class="v2sb-st">' + esc(r.line) + '</p></div>';
  }
  function requestedRow(x) {
    return '<div class="v2sb-row req" data-id="' + esc(x.id) + '"><p class="v2sb-rtx">' + esc(x.text) + '</p>'
      + '<div class="v2sb-ctl"><span class="v2sb-chip tone-na">لم تُبنَ بعد</span><button type="button" class="v3-btn2 v2sb-del" data-a="del" data-id="' + esc(x.id) + '">احذف</button></div>'
      + '<p class="v2sb-st">حُفظت ' + esc(L.util.agoText(L.v2sBrainTime(x.created_at), now()) || NA) + '</p></div>';
  }
  function groupHtml(g, isOpen, count) {
    return '<div class="v2sb-grp' + (isOpen ? ' open' : '') + '"><button type="button" class="v2sb-gh" data-a="grp" data-g="' + esc(g.key) + '" aria-expanded="' + isOpen + '">'
      + '<span class="v2sb-gt">' + esc(g.title) + '</span><span class="v2sb-gc">' + esc(U.ar(count)) + '</span>' + CHEV + '</button>'
      + (isOpen ? '<div class="v2sb-rows">' + g.rowsHtml + '</div>' : '') + '</div>';
  }
  function isOpen(key) {
    if (S.open[key] !== undefined) return S.open[key];
    return mobile() ? key === 'files' : true;
  }
  function rulesCard() {
    var st = srcState('rules'), res = L.v2sBrainRules(rulesInput());
    var groups = res.groups.map(function (g) { return { key: g.key, title: g.title, count: g.rows.length, rowsHtml: g.rows.map(ruleRow).join('') }; });
    var req = (data('rules') && data('rules').requested) || [];
    if (req.length) groups.push({ key: 'requested', title: 'قواعد طلبتها', count: req.length, rowsHtml: req.map(requestedRow).join('') });
    var warn = (st === 'error' || st === 'closed') ? '<div class="v3-warn" role="status">تعذّر جلب حالة القواعد الآن. ما يظهر «' + NA + '» ليس معناه أنه متوقف. ' + retryBtn('retry-rules') + '</div>' : '';
    var want = '<div class="v2sb-want"><h3>قاعدة تريدها</h3>'
      + '<input id="v2sbWant" type="text" maxlength="300" autocomplete="off" aria-label="اكتب القاعدة التي تريدها" placeholder="مثلًا: لا توزّع ملفات الخليج على خبير من مصر" value="' + esc(S.ruleText) + '"' + (S.ruleBusy ? ' disabled' : '') + '>'
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
      + '<button type="button" class="v2sb-la" data-a="logact" data-i="' + i + '">' + esc(r.action.label) + '</button></li>';
  }
  function logCard() {
    var ent = entries(), st = srcState('today'), body, notes = '';
    var agents = agentsResp();
    var rows = ent ? L.v2sBrainLogRows(ent, agents ? agents.agents : [], sinceMs()) : null;
    S.logRows = rows || [];
    if (ent && ent.fromInbox) notes += '<div class="v3-warn" role="status">من الملفات المفتوحة فقط، وقد يكون السجل ناقصًا</div>';
    else if (ent && ent.missing) notes += '<div class="v3-warn" role="status">سجل التوزيع غير موجود على المنصة بعد</div>';
    else if (ent && ent.partial) notes += '<div class="v3-warn" role="status">معروض أحدث ' + U.ar(200) + ' ملف فقط، وقد يكون في سجل اليوم ما لم يظهر</div>';
    if (st === 'idle' || st === 'loading') body = skeleton(3);
    else if (!ent) body = '<div class="v3-empty"><b>تعذّر جلب سجل الملفات</b><p>لا نعرف ما وُزّع اليوم، فلا تعتبر السجل فارغًا.</p>' + retryBtn('retry-today') + '</div>';
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
    var line = L.v2sBrainLine({ queue: Q, settings: data('rules'), entries: ent });
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
  function drawHelpers(v) {
    var A = agentsResp(), st = data('status'), H = A ? L.v2sBrainHelpers(A, st, S.running ? S.running.id : null) : null;
    var loading = epState('aiAgents') === 'idle' || epState('aiAgents') === 'loading';
    var head, body;
    if (loading) { head = lineHtml('…جارٍ جلب تقارير المساعدين', null); body = '<div class="v2sb-grid">' + skeleton(1) + skeleton(1) + skeleton(1) + '</div>'; }
    else if (!H) {
      head = lineHtml('تعذّر جلب تقارير المساعدين', null);
      body = '<div class="v3-empty"><b>تعذّر جلب تقارير المساعدين</b><p>لا نعرف ما كتبوه، فلا تعتبر الشاشة فارغة.</p>' + retryBtn('retry-agents') + '</div>';
    } else {
      var all = '<button type="button" class="v3-btn2 v2sb-run" data-a="hall" data-run="all" data-label="حدّث الكل"' + (H.canRunAll ? '' : ' disabled') + (H.runAllReason ? ' title="' + esc(H.runAllReason) + '"' : '') + '>' + (S.running && S.running.id === 'all' ? 'جارٍ الكتابة…' : 'حدّث الكل') + '</button>';
      head = '<div class="v2sb-hl">' + lineHtml(L.v2sBrainHelpersLine(H, st, now()), null) + '<div class="v2sb-hdisc">' + disc(L.v2sBrainCap(st), 'تحديثات اليوم', !st) + all + '</div></div>'
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
      + sectionBlock('آخر تشغيل', '<p>' + esc(r.runKey ? r.run.text : r.line) + '</p>' + (key === 'assign' && r.line !== r.run.text ? '<p class="v2sb-st">' + esc(r.line) + '</p>' : ''));
    if (key === 'assign') {
      var hist = ((data('rules') && data('rules').history) || []).filter(function (h) { return h.action === 'expert_file.auto_assign'; });
      body += sectionBlock('تاريخ التغيير', hist.length ? '<ul class="v2sb-hist">' + hist.map(function (h) {
        var on = h.meta && h.meta.auto_assign === true;
        return '<li>' + esc((U.agoText(L.v2sBrainTime(h.at), now()) || NA) + ' — ' + (on ? 'شُغّل' : 'أُوقف') + ' بواسطة ') + '<span dir="ltr">' + esc(h.actor_email) + '</span></li>';
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
      if (a === 'goto') { if (host().openSection) host().openSection(b.getAttribute('data-s')); }
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
        if (r.kind === 'report') openHelper(r.agent); else openFile(r.entry);
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
    v2s_brain: { ep: ['opsQueue', 'inbox', 'aiAgents', 'inviteSettings'], src: ['today', 'rules'] },
    ai: { ep: ['aiAgents'], src: ['status'] }
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
  B.render = function (mod, view) {
    S.view = view; S.mod = mod;
    ensureFor(mod);
    redraw(true);
    if (!S.poll) {
      S.poll = setInterval(function () {
        if (!(host().current && B.owns(host().current()))) return;
        if (document.getElementById('epModal')) return;
        if (signature() !== S.sig) redraw();
      }, 400);
    }
    if (!S.minute) S.minute = setInterval(function () {
      if (host().current && B.owns(host().current()) && !document.getElementById('epModal')) {
        if (S.mod === 'v2s_brain') load('today', true, true);
        redraw();
      }
    }, 60000);
  };
  B._state = S;
  B._src = SRC;
  B._tick = function (t) { S.nowOverride = t || 0; redraw(true); };
})();
