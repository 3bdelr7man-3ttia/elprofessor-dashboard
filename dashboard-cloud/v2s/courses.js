/* ============================================================================
 * v2s/courses.js — قسم «الدورات والمدرّبون» على الهيكل الجديد (الجولة الأخيرة): لوحة الدورات · المدرّبون · الدورات الحيّة · ما يطلبه الناس ·
 * عروض الأسعار · صفحة الدورة · «كل السجلات» (الشاشة القديمة بشكل جديد). ⛔ لا منطق عمل هنا: التصنيف والعدّادات وسطر العقل كلها من
 * `V2L.v2s.courses` (نقي، في v2-logic.js)، والكتابات كلها من مسارات `/api/v2/courses/*` بـ`confirmed:true` بعد ورقة تأكيد.
 *
 * ⛔ المفتاح مقفول افتراضيًا: الملف بيتحمّل دايمًا لكنه ما بيرسم شيئًا إلا لو `V2SEC.take` اتنادى والغلاف الجديد شغّال.
 * ⛔ ولا طلب شبكة من هنا غير: محمّلات الداشبورد الموجودة (طابور القرارات وتحليل الشات) · مسارات القراءة الموجودة `/api/platform-*` ·
 *   `/api/v2/*` · قرارات الأشخاص الموجودة (قبول/رفض مدرّب وطلب برنامج · إيقاف مدرّب). وكل مصدر بيفشل لوحده: «غير متاح بعد» لا صفر.
 * ========================================================================== */
(function () {
  'use strict';
  var L = window.V2L;
  if (!L || !L.v2s || !L.v2s.courses) return;
  var U = L.util, C = L.v2s.courses, K2 = L.courses2 || null;
  // سجلّ مشترك مع أقسام الجولة الأخيرة الأخرى: كل قسم يسجّل `take` بتاعه، والحارس في الشاشات القديمة يسأل السجلّ.
  window.V2SEC = window.V2SEC || { _o: [], add: function (o) { this._o.push(o); },
    take: function (mod, v) { if (!window.V2_ON || !(window.V2SHELL && V2SHELL.on)) return false;
      for (var i = 0; i < this._o.length; i++) { if (this._o[i].take(mod, v)) return true; } return false; } };
  var CO = window.V2CO = {};
  var NA = C.NA;
  var S = { view: null, screen: '', sig: '', poll: null, minute: null, list: false, filter: 'all', search: '', col: '', tr: '', note: null, noteT: null,
            busy: {}, sheetBusy: false, nowOverride: 0, fresh: {}, editing: '' };
  try { var sc = localStorage.getItem('v2co_col'); if (sc === 'review' || sc === 'building' || sc === 'published') S.col = sc; } catch (e) {}
  try { var st = localStorage.getItem('v2co_tr'); if (st === 'apps' || st === 'list') S.tr = st; } catch (e) {}

  function esc(s) { return String(s == null ? '' : s).replace(/[&<>"']/g, function (c) { return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]; }); }
  function host() { return window.V2_HOST || {}; }
  function ep() { return window.EP || null; }
  function now() { return S.nowOverride || Date.now(); }
  function img(name) { return 'v2/img/' + name + '.jpg'; }
  function q(sel, root) { return (root || document).querySelector(sel); }
  function qa(sel, root) { return Array.prototype.slice.call((root || document).querySelectorAll(sel)); }
  function ar(n) { return U.ar(n); }
  var BRAIN = '<img class="v2co-bav" src="' + img('brain-avatar') + '" alt="">';
  var PLUS = '<svg viewBox="0 0 24 24" class="v2co-ic" aria-hidden="true"><path d="M12 5v14M5 12h14"/></svg>';

  // ------------------------------------------------------------------ مصادر (كلٌّ تفشل لوحدها)
  var SRC = {};
  var PATHS = { courses: '/platform-courses', apps: '/platform-trainer-applications?status=pending', experts: '/platform-experts', schedules: '/platform-schedules',
                offers: '/platform-course-offers?status=pending', progStats: '/platform-program-requests/stats', programs: '/platform-program-requests?status=pending',
                stats: '/v2/courses/stats', shares: '/v2/shares', courses2: '/v2/courses2' };
  var LABEL = { courses: 'الدورات', apps: 'طلبات المدرّبين', experts: 'المدرّبون', schedules: 'مواعيد الدورات الحيّة', offers: 'عروض الأسعار', progStats: 'أكثر الدورات طلبًا',
                programs: 'طلبات البرامج', stats: 'المبيعات ونسبة الإكمال', shares: 'جدول النسب', courses2: 'دورات المحرّر' };
  var OPTIONAL = { stats: 1, shares: 1, courses2: 1 };            // ٤٠٤ فيها = «غير متاح بعد» بهدوء، لا شريط تحذير
  function pathOf(k) {
    if (PATHS[k]) return PATHS[k];
    var m = /^(checklist|detail):(.+)$/.exec(k);
    if (!m) return '';
    var id = encodeURIComponent(m[2]);
    return m[1] === 'checklist' ? '/v2/courses/' + id + '/checklist' : '/platform-courses/' + id + '/detail';
  }
  function srcOf(k) { return SRC[k] || (SRC[k] = { state: 'idle', data: null, status: 0, seq: 0 }); }
  function load(k, force) {
    var s = srcOf(k), E = ep(), path = pathOf(k);
    if (!E || !E.api || !E.authed || !path) return;
    if (s.state === 'loading') return;
    if (!force && s.state !== 'idle') return;
    s.state = 'loading';
    var seq = ++s.seq;
    E.api(path).then(function (d) {
      if (seq !== s.seq) return;
      s.state = 'ready'; s.data = d; changed();
    }).catch(function (e) {
      if (seq !== s.seq) return;
      if (e && e.status === 401) return;
      s.state = e && e.status === 404 ? 'closed' : 'error'; s.status = (e && e.status) || 0; s.data = null; changed();
    });
  }
  function data(k) { var s = srcOf(k); return s.state === 'ready' ? s.data : null; }
  function srcState(k) { return srcOf(k).state; }
  function pending(k) { var s = srcState(k); return s === 'idle' || s === 'loading'; }
  function rowsOf(k, key) { var d = data(k); return d && Array.isArray(d[key]) ? d[key] : null; }
  function epState(k) { var E = ep(); return (E && E.state && E.state[k]) || 'idle'; }
  function epEnsure(keys) { var E = ep(); if (E && E.authed) keys.forEach(function (k) { E.ensure(k, null); }); }
  function queueLive() {
    var E = ep();
    if (epState('opsQueue') !== 'ready' || !E.data.opsQueue) return null;
    return Array.isArray(E.data.opsQueue.live_needs_decision) ? E.data.opsQueue.live_needs_decision : [];
  }
  function failedLabels(keys) { return keys.filter(function (k) { var s = srcState(k); return s === 'error' || (s === 'closed' && !OPTIONAL[k]); }).map(function (k) { return LABEL[k]; }); }

  function signature() {
    return Object.keys(SRC).map(function (k) { return k + srcOf(k).state + srcOf(k).seq; }).join(',') + '|' + ['opsQueue', 'analysis'].map(epState).join(',');
  }
  var redrawT = null;
  function changed() {
    if (redrawT) return;
    redrawT = setTimeout(function () { redrawT = null; redraw(); }, 0);
  }

  // ------------------------------------------------------------------ أجزاء مشتركة
  function personLink(name, email) {
    if (!email) return esc(name);
    return '<a class="v2co-person" href="' + esc(L.sectionHash('people', 'person', email)) + '" data-person="' + esc(email) + '">' + esc(name) + '</a>';
  }
  function warnStrip(labels, tail) {
    if (!labels.length) return '';
    return '<div class="v2co-warn" role="status">تعذّر جلب: ' + esc(labels.join(' · ')) + ' — ' + esc(tail || 'ما يظهر ناقص، وليس معناه أنه لا شيء') + '</div>';
  }
  // شريط النجاح يظهر في الشاشة (وفي صفحة الدورة نفسها) التي وقع فيها الحدث فقط، لا في كل ما بعدها.
  function noteKey() { return S.screen === 'course' ? 'course:' + ((host().state && host().state().course) || '') : S.screen; }
  function noteStrip() { return S.note && (!S.noteScr || S.noteScr === noteKey()) ? '<div class="v2co-ok" role="status">' + esc(S.note) + '</div>' : ''; }
  function setNote(text, scr) {
    S.note = text; S.noteScr = scr || noteKey(); clearTimeout(S.noteT);
    S.noteT = setTimeout(function () { S.note = null; redraw(); }, 12000);
  }
  function retryBtn() { return '<button type="button" class="v2co-btn2" data-a="retry">أعد المحاولة</button>'; }
  function loadingBlock(t) { return '<div class="v2co-empty"><b>…جارٍ جلب ' + esc(t) + '</b></div>'; }
  function unavailable(t, extra) {
    return '<div class="v2co-empty"><b>' + esc(t) + ': ' + NA + '</b><p>تعذّر الوصول إلى هذه البيانات الآن، فلا تعتبر الشاشة فارغة.</p>' + (extra || '') + retryBtn() + '</div>';
  }
  function none(t) { return '<p class="v2co-none">' + esc(t) + '</p>'; }
  function skeleton(n) {
    var o = ''; for (var i = 0; i < (n || 3); i++) o += '<div class="v2co-sk"><i></i><i></i></div>';
    return o;
  }
  function coverHtml(c, cls) {
    var url = String(c.thumbnail_url || '').trim();
    var letter = C.cover(c.title).letter;
    return '<span class="v2co-cover ' + (cls || '') + (url ? ' has' : '') + '" aria-hidden="true"><i>' + esc(letter) + '</i>' + (url ? '<img class="v2co-img" src="' + esc(url) + '" alt="" loading="lazy">' : '') + '</span>';
  }
  function chip(text, tone) { return '<span class="v2co-chip ' + (tone || '') + '">' + esc(text) + '</span>'; }
  var STATE_TONE = { published: 'green', review: 'amber', building: 'grey', rejected: 'amber', archived: 'grey' };
  function stateChip(st) { return chip(C.STATE_LABEL[st], STATE_TONE[st]); }
  function priceLine(c) { var p = C.priceOf(c); return p.ok === false ? 'بلا سعر' : (p.short || p.text); }
  function trainerHtml(c) {
    if (c.platform_owned === true) return esc('البروفيسور');
    var name = C.trainerOf(c);
    return c.instructor_email ? personLink(name, String(c.instructor_email).toLowerCase()) : esc(name);
  }
  function timeHtml(text, tone, at) {
    return text ? '<time class="v2co-time tone-' + esc(tone || 'none') + '"' + (at ? ' datetime="' + esc(new Date(at).toISOString()) + '"' : '') + '>' + esc(text) + '</time>' : '';
  }
  function arDigits(t) { return String(t).replace(/\d/g, function (d) { return '٠١٢٣٤٥٦٧٨٩'.charAt(+d); }); }
  var SESSION_AR = 'انتهت الجلسة — سجّل الدخول من جديد ثم جرّب';
  var FAIL_AR = 'تعذّر تنفيذ العملية';
  var NOREPLY_AR = 'لم يصلنا رد من المنصة — حدّث الصفحة وتأكد قبل أن تعيد المحاولة';
  var STALE_AR = 'تغيّرت الحالة على المنصة — حدّث الصفحة';
  function errMsg(e) {
    if (e && e.status === 401) return SESSION_AR;
    var d = (e && e.data) || {};
    if (d.no_reply) return NOREPLY_AR;
    if (e && e.status === 409) return STALE_AR + (typeof d.error === 'string' && d.error ? ' — ' + arDigits(d.error) : '');
    if (typeof d.error === 'string' && d.error) return arDigits(d.error);
    return FAIL_AR;
  }
  function courseById(id) { var cs = rowsOf('courses', 'courses'); if (!cs) return null; for (var i = 0; i < cs.length; i++) if (cs[i] && String(cs[i].id) === String(id)) return cs[i]; return null; }
  // محرّر الدورات (course_editor.js): قائمة `courses2` تُدمج مع لوحة المنصّة بالمعرّف أو الرابط المختصر
  function c2Rows() { return rowsOf('courses2', 'courses') || []; }
  function c2Of(c) { return c && K2 ? K2.c2Index(c2Rows())[c.id] || (c.slug ? K2.c2Index(c2Rows())[c.slug] : null) || null : null; }
  function c2ById(id) { return K2 ? K2.c2Index(c2Rows())[id] || null : null; }
  function c2Meta(c) {
    var m = c2Of(c), line = m && K2 ? K2.c2Line(m) : '';
    return m ? '<span class="v2co-st v2ce-c2">' + chip(m.status_ar || 'مسودة', m.status === 'published' ? 'green' : (m.status === 'draft' || m.status === 'paused' ? 'grey' : 'amber')) + (line ? ' ' + esc(line) : '') + '</span>' : '';
  }
  function courseBySlug(slug) { var cs = rowsOf('courses', 'courses'); if (!cs) return null; for (var i = 0; i < cs.length; i++) if (cs[i] && cs[i].slug === slug) return cs[i]; return null; }
  function schedOf(c) {
    var rs = rowsOf('schedules', 'schedules');
    if (!rs || !c) return null;
    for (var i = 0; i < rs.length; i++) if (rs[i] && (rs[i].id === c.id || (c.slug && rs[i].slug === c.slug))) return rs[i];
    return null;
  }
  function checklistOf(id) { var d = data('checklist:' + id); return d && Array.isArray(d.checklist) ? d : null; }
  function checklistStateOf(id) { var s = srcState('checklist:' + id); return s === 'idle' ? 'loading' : s; }
  function goPage(id) { if (host().openCourse) host().openCourse(id); }
  function goSection(key, tab) { if (host().openSection) host().openSection(key, tab); }

  // ------------------------------------------------------------------ الأوراق
  function openSheet(title, html) {
    if (typeof window.openModal !== 'function') return null;
    var s = window.openModal(title, '<div class="v2co-m">' + html + '</div>');
    var x = q('[data-x]', s);
    if (x) x.onclick = function () { if (!s.dataset.busy) { S.sheetBusy = false; window.closeModal(); } };
    s.onclick = function (e) { if (e.target === s && !s.dataset.busy) { S.sheetBusy = false; window.closeModal(); } };
    return s;
  }
  function closeSheet() { S.sheetBusy = false; try { window.closeModal(); } catch (e) {} }
  function listHtml(items) { return '<ul class="v2co-will">' + items.map(function (t) { return '<li>' + t + '</li>'; }).join('') + '</ul>'; }
  // ورقة بمرحلة أو مرحلتين:
  //   o.form      نص المرحلة الأولى (سؤال أو حقول) · o.wire(s) ربط حقولها · o.collect(s) ⇒ {ok, payload, error}
  //   o.review(p) نص المرحلة الثانية «ما سيحدث» (اختياري: بدونه زرّ المرحلة الأولى ينفّذ مباشرة) · o.reviewWire(s, p) ⇒ ربط (مثل كتابة العنوان) · o.ready(s) ⇒ هل يُفتح الزرّ
  //   o.send(p) ⇒ Promise · o.onOk(res, p) · o.result(res, p, s) ⇒ نص نتيجة تبقى الورقة مفتوحة عليه · o.danger · o.btnNext · o.btnConfirm · o.busy
  function flow(o) {
    var s = openSheet(o.title, '<div class="v2co-stage"></div>');
    if (!s) return null;
    S.sheetBusy = false;
    var stage = q('.v2co-stage', s), payload = null, step = o.form != null ? 'form' : 'review', formHtml = '', locked = false;
    function errBox(msg) { var e = q('.v2co-err', s); if (e) e.innerHTML = msg ? '<div class="v2co-errbox" role="alert">' + esc(msg) + '</div>' : ''; }
    function finalBtn() { return '<button type="button" class="v2co-btn1' + (o.danger ? ' danger' : '') + '" id="co_go">' + esc(o.btnConfirm || 'أكّد') + '</button>'; }
    function bindSend(btn) {
      btn.onclick = function () {
        if (btn.dataset.busy || locked) return;
        if (o.ready && !o.ready(s)) return;
        btn.dataset.busy = '1'; s.dataset.busy = '1'; S.sheetBusy = true; btn.disabled = true;
        var back = q('#co_back', s); if (back) back.disabled = true;
        var label = btn.textContent; btn.textContent = o.busy || 'جارٍ التنفيذ…'; errBox('');
        Promise.resolve(o.send(payload)).then(function (res) {
          delete s.dataset.busy; S.sheetBusy = false;
          if (o.result) { stage.innerHTML = o.result(res || {}, payload, s); var dn = q('#co_done', s); if (dn) dn.onclick = closeSheet; if (o.onOk) o.onOk(res || {}, payload); return; }
          closeSheet();
          if (o.onOk) o.onOk(res || {}, payload);
        }).catch(function (e) {
          delete s.dataset.busy; S.sheetBusy = false; delete btn.dataset.busy;
          var d = (e && e.data) || {};
          if (d.no_reply) { locked = true; btn.textContent = label; btn.disabled = true; errBox(NOREPLY_AR); var x2 = q('#co_x', s); if (x2) { x2.textContent = 'إغلاق'; x2.disabled = false; } if (o.onStale) o.onStale(); return; }
          btn.disabled = false; btn.textContent = label; if (back) back.disabled = false;
          errBox(errMsg(e));
          if (e && e.status === 409 && o.onStale) o.onStale();
        });
      };
    }
    function show() {
      if (step === 'form') {
        stage.innerHTML = o.form + '<div class="v2co-err"></div><div class="v2co-macts">'
          + (o.review ? '<button type="button" class="v2co-btn1" id="co_next">' + esc(o.btnNext || 'تابع') + '</button>' : finalBtn())
          + '<button type="button" class="v2co-btn2" id="co_x">رجوع</button></div>';
        formHtml = stage.innerHTML;
        q('#co_x', s).onclick = closeSheet;
        if (o.wire) o.wire(s);
        if (o.review) {
          q('#co_next', s).onclick = function () {
            var c = o.collect ? o.collect(s) : { ok: true, payload: {} };
            if (!c.ok) { errBox(c.error); return; }
            payload = c.payload; step = 'review'; show();
          };
        } else {
          var go = q('#co_go', s);
          var upd = function () { if (!locked && !go.dataset.busy) go.disabled = o.ready ? !o.ready(s) : false; };
          if (o.ready) { qa('input,textarea,select', s).forEach(function (i) { i.addEventListener('input', upd); }); }
          bindSend(go);
          var send = go.onclick;
          go.onclick = function () {
            var c = o.collect ? o.collect(s) : { ok: true, payload: {} };
            if (!c.ok) { errBox(c.error); return; }
            payload = c.payload; send();
          };
          upd();
        }
      } else {
        stage.innerHTML = (o.review ? o.review(payload) : '') + '<div class="v2co-err"></div><div class="v2co-macts">' + finalBtn()
          + (o.form != null ? '<button type="button" class="v2co-btn2" id="co_back">رجوع</button>' : '<button type="button" class="v2co-btn2" id="co_x">رجوع</button>') + '</div>';
        var go2 = q('#co_go', s);
        bindSend(go2);
        if (o.form != null) q('#co_back', s).onclick = function () { step = 'form'; stage.innerHTML = formHtml; show(); };
        else q('#co_x', s).onclick = closeSheet;
        if (o.reviewWire) o.reviewWire(s, payload);
        if (o.ready) { go2.disabled = !o.ready(s); qa('input,textarea,select', s).forEach(function (i) { i.addEventListener('input', function () { if (!locked && !go2.dataset.busy) go2.disabled = !o.ready(s); }); }); }
      }
    }
    show();
    return s;
  }
  function post(path, body) { return ep().api(path, { method: 'POST', body: body }); }
  function fld(id, label, inner, hint) { return '<div class="v2co-fld"><label for="' + id + '">' + esc(label) + '</label>' + inner + (hint ? '<small>' + esc(hint) + '</small>' : '') + '</div>'; }
  function factsTable(rows) {
    return '<dl class="v2co-facts">' + rows.filter(function (r) { return r[1] !== '' && r[1] != null; }).map(function (r) { return '<div><dt>' + esc(r[0]) + '</dt><dd>' + r[1] + '</dd></div>'; }).join('') + '</dl>';
  }

  // ------------------------------------------------------------------ لوحة الدورات
  function reviewTicket(c, first) {
    var cl = checklistOf(c.id), cst = checklistStateOf(c.id);
    var facts = C.courseFacts(c, { schedule: schedOf(c), checklist: cl, now: now(), checklistState: cst });
    var t = C.reviewTimer(c, now());
    var live = c.type === 'live_upcoming';
    var main = facts.suggestion === 'publish' ? ['approve', 'انشرها'] : (facts.suggestion === 'return' ? ['return', 'أعِدها بملاحظات'] : ['open', 'افتح وراجع']);
    var lessons = c.type === 'live_upcoming' ? '' : ' · ' + C.lessonsPhrase(C.lessonsOf(c));
    return '<article class="v2co-t tone-' + esc(t ? t.tone : 'none') + (first ? ' first' : '') + '" data-id="' + esc(c.id) + '">'
      + '<div class="v2co-strip"><span class="v2co-type">' + (live ? 'دورة حيّة' : 'دورة جديدة') + '</span>' + (t ? timeHtml(t.label, t.tone, t.at) : '') + '</div>'
      + '<div class="v2co-body">' + coverHtml(c, 'big')
      + '<h3><button type="button" class="v2co-open" data-a="open" data-id="' + esc(c.id) + '">' + esc(c.title || 'دورة بلا عنوان') + '</button></h3>'
      + '<p class="v2co-who">' + trainerHtml(c) + esc(lessons) + '</p>'
      + '<div class="v2co-brain">' + BRAIN + '<p>' + esc(facts.line) + '</p></div>'
      + '<div class="v2co-acts"><button type="button" class="v2co-btn1" data-a="' + main[0] + '" data-id="' + esc(c.id) + '">' + esc(main[1]) + '</button>'
      + (main[0] === 'open' ? '' : '<button type="button" class="v2co-link" data-a="open" data-id="' + esc(c.id) + '">افتح الدورة</button>') + '</div></div></article>';
  }
  // مهلة أول دورة (إضافة د من المنصة): تظهر فقط لو الحقل موجود على المدرّب ولم تُنشر له دورة بعد؛ غيابه = لا سطر ولا مهلة مخترعة.
  function dueLine(c) {
    var ex = rowsOf('experts', 'experts'), email = String(c.instructor_email || '').toLowerCase();
    if (!ex || !email) return null;
    var e = ex.filter(function (x) { return String(x.email || '').toLowerCase() === email; })[0];
    var due = e ? Date.parse(e.first_course_due_at || '') : NaN;
    if (isNaN(due)) return null;
    var cs = rowsOf('courses', 'courses') || [];
    if (cs.some(function (x) { return String(x.instructor_email || '').toLowerCase() === email && x.is_active === true; })) return null;
    var left = due - now();
    if (left > 0) return { text: 'باقٍ ' + U.durShort(left) + ' على مهلة أول دورة', cls: left < 3 * 86400e3 ? 'amber' : '' };
    return { text: 'انتهت مهلة أول دورة منذ ' + U.durShort(-left), cls: 'red' };
  }
  function buildingCard(c) {
    var lessons = c.type === 'live_upcoming' ? '' : ' · ' + C.lessonsPhrase(C.lessonsOf(c)) + ' حتى الآن';
    var line = '', cls = '', due = dueLine(c);
    if (c.state === 'rejected') {
      var n = String(c.review_note || '').trim();
      line = 'أُعيدت بملاحظات' + (n ? ': ' + (n.length > 80 ? n.slice(0, 80) + '…' : n) : ''); cls = 'amber';
    } else {
      var at = Date.parse(c.updated_at || '');
      if (!isNaN(at)) line = 'آخر تعديل ' + U.agoText(at, now());
    }
    return '<button type="button" class="v2co-bc" data-a="open" data-id="' + esc(c.id) + '">' + coverHtml(c, 'big')
      + '<b>' + esc(c.title || 'دورة بلا عنوان') + '</b><span class="v2co-who">' + esc(C.trainerOf(c) + lessons) + '</span>'
      + (line ? '<span class="v2co-st ' + cls + '">' + esc(line) + '</span>' : '') + (due ? '<span class="v2co-st ' + due.cls + '">' + esc(due.text) + '</span>' : '') + c2Meta(c) + '</button>';
  }
  function publishedRow(c) {
    var learners = U.U(c.total_enrolled || 0, ['متعلّم واحد', 'متعلّمان', 'متعلّمين', 'متعلّمًا']);
    var hidden = C.hiddenFromPublic(c);
    var st = data('stats') ? C.statFor(data('stats'), c) : null;
    var l2;
    if (st && Array.isArray(st.sales)) {
      var sales = st.sales.map(function (x) { return U.moneyText(x.amount, x.currency); }).filter(Boolean).join(' + ');
      var bits = ['المبيعات: ' + (sales || 'لا مبيعات بعد')];
      if (st.completion_pct != null) bits.push('يكملها ' + ar(st.completion_pct) + '٪');
      l2 = '<span class="v2co-l2">' + esc(bits.join(' · ')) + '</span>'
        + (st.stall_lesson && st.stall_lesson.index != null ? '<span class="v2co-l2 amber">يتوقف أغلبهم عند الدرس ' + esc(ar(st.stall_lesson.index)) + '</span>' : '');
    } else l2 = '<span class="v2co-l2 mute">المبيعات ونسبة الإكمال: ' + NA + '</span>';
    return '<button type="button" class="v2co-pr" data-a="open" data-id="' + esc(c.id) + '">' + coverHtml(c, 'thumb')
      + '<span class="v2co-prb"><b>' + esc(c.title || 'دورة بلا عنوان') + '</b>'
      + '<span class="v2co-l1">' + esc(learners + ' · ' + (C.priceOf(c).free ? 'مجانية' : priceLine(c))) + (c.bid_enabled ? ' ' + chip('يقبل عروض الأسعار', 'wine') : '') + '</span>'
      + (hidden ? '<span class="v2co-l2 amber">لا تظهر للناس بعد: لا دروس فيها</span>' : '') + l2 + '</span></button>';
  }
  function trainerRank(r) { return r.inReview ? 0 : (r.rejected ? 1 : (r.building ? 2 : (r.tone !== 'none' ? 3 : 4))); }
  function trainersCard() {
    var rows = C.trainerRows(rowsOf('experts', 'experts'), rowsOf('courses', 'courses'), { now: now() });
    var apps = C.appTickets(rowsOf('apps', 'applications'), { now: now() });
    var body;
    if (!rows) body = srcState('experts') === 'loading' || srcState('experts') === 'idle' ? loadingBlock('المدرّبين') : '<div class="v2co-empty sm"><b>المدرّبون: ' + NA + '</b>' + retryBtn() + '</div>';
    else {
      var listed = rows.filter(function (r) { return r.listed; }).sort(function (a, b) { return trainerRank(a) - trainerRank(b) || (b.students || 0) - (a.students || 0); }).slice(0, 3);
      body = listed.length ? '<ul class="v2co-trl">' + listed.map(trainerMini).join('') + '</ul>' : none('لا مدرّبين لهم دورات بعد');
    }
    var appsLine = apps ? 'طلبات انضمام جديدة: ' + ar(apps.length) : 'طلبات الانضمام: ' + NA;
    return '<section class="v2co-col v2co-trcol tone-wine" data-col="trainers" aria-label="المدرّبون"><header class="v2co-ch"><b>المدرّبون</b></header>'
      + '<div class="v2co-trfull">' + body + '<div class="v2co-trfoot"><span>' + esc(appsLine) + '</span><button type="button" class="v2co-link" data-a="goto" data-s="courses" data-t="trainers">راجعها</button></div></div>'
      + '<button type="button" class="v2co-trrow" data-a="goto" data-s="courses" data-t="trainers"><b>المدرّبون</b><span>' + esc(appsLine) + '</span></button></section>';
  }
  function avatar(name) { return '<span class="v2co-av" aria-hidden="true">' + esc(String(name || '؟').trim().charAt(0) || '؟') + '</span>'; }
  function trainerMini(r) {
    return '<li class="v2co-tm">' + avatar(r.name) + '<div><b>' + personLink(r.name, r.email) + '</b>' + (r.statusLine ? '<span class="v2co-st ' + (r.tone === 'late' ? 'red' : (r.tone === 'warn' ? 'amber' : '')) + '">' + esc(r.statusLine) + '</span>' : '') + '</div></li>';
  }
  function activeCol(b) {
    if (S.col && b.counts && (S.col === 'review' || S.col === 'building' || S.col === 'published')) return S.col;
    return b.review.length ? 'review' : 'published';
  }
  function drawBoard(v) {
    if (S.list) return drawList(v);
    var st = srcState('courses');
    var b = C.board(rowsOf('courses', 'courses'), { now: now() });
    var failed = failedLabels(['schedules', 'stats']).filter(function (x) { return x !== LABEL.stats; });
    var top = '<div class="v2co-top"><p class="v2co-sum">' + esc(st === 'ready' ? b.summary : (pending('courses') ? '…جارٍ جلب الدورات' : b.summary)) + '</p>'
      + '<button type="button" class="v2co-main" data-a="create">' + PLUS + 'أنشئ دورة</button></div>';
    var cols = '';
    if (b.na) {
      var inner = pending('courses') ? '<div class="v2co-skw">' + skeleton(3) + '</div>' : unavailable('الدورات');
      v.innerHTML = '<div class="v2co" data-screen="board">' + noteStrip() + top + (pending('courses') ? '<div class="v2co-cols">' + ['في المراجعة', 'تحت البناء', 'منشورة'].map(function (t) { return '<section class="v2co-col"><header class="v2co-ch"><b>' + t + '</b></header><div class="v2co-list">' + skeleton(2) + '</div></section>'; }).join('') + trainersCard() + '</div>'
        : '<div class="v2co-cols one">' + '<div class="v2co-colwide">' + inner + '</div>' + trainersCard() + '</div>') + '</div>';
      return;
    }
    // الدورات الحيّة في المراجعة تحتاج مواعيدها (رابط اللقاء)، والجميع يحتاج فحصه
    if (b.review.some(function (c) { return c.type === 'live_upcoming'; })) load('schedules');
    b.review.slice(0, 12).forEach(function (c) { load('checklist:' + c.id); });
    load('stats');
    var active = activeCol(b);
    var firstOk = b.review.length && Date.parse(b.review[0].submitted_at || '') > 0;
    var revHtml = b.review.length ? b.review.map(function (c, i) { return reviewTicket(c, i === 0 && firstOk); }).join('') : none('لا دورات تنتظر المراجعة');
    var bldHtml = b.building.length ? b.building.map(buildingCard).join('') : none('لا دورات تحت البناء');
    var allLink = '<button type="button" class="v2co-link wide" data-a="all">كل الدورات (' + esc(ar(b.counts.total)) + ')</button>';
    var pubHtml = b.published.length ? b.published.slice(0, 5).map(publishedRow).join('') + allLink : none('لا دورات منشورة بعد') + allLink;
    function col(key, title, n, inner, tone) {
      return '<section class="v2co-col tone-' + tone + '" data-col="' + key + '" aria-label="' + esc(title) + '"><header class="v2co-ch"><b>' + esc(title) + '</b><span class="v2co-n">' + esc(ar(n)) + '</span></header><div class="v2co-list">' + inner + '</div></section>';
    }
    cols = col('review', 'في المراجعة', b.counts.review, revHtml, 'wait') + col('building', 'تحت البناء', b.counts.building, bldHtml, 'grey') + col('published', 'منشورة', b.counts.published, pubHtml, 'ok') + trainersCard();
    var seg = [['review', 'في المراجعة', b.counts.review], ['building', 'تحت البناء', b.counts.building], ['published', 'منشورة', b.counts.published]].map(function (x) {
      return '<button type="button" role="tab" class="v2co-segb' + (x[0] === active ? ' on' : '') + '" aria-selected="' + (x[0] === active) + '" data-a="col" data-col="' + x[0] + '"><span>' + x[1] + '</span><b>' + esc(ar(x[2])) + '</b></button>';
    }).join('');
    v.innerHTML = '<div class="v2co" data-screen="board">' + noteStrip() + warnStrip(failed) + top + '<div class="v2co-seg" role="tablist" aria-label="أعمدة الدورات">' + seg + '</div>'
      + '<div class="v2co-cols" data-active="' + active + '">' + cols + '</div></div>';
  }

  // ------------------------------------------------------------------ «كل الدورات»
  function listItems(b) {
    return b.review.concat(b.building, b.published, b.archived);
  }
  function matchFilter(c, f) {
    switch (f) {
      case 'published': return c.state === 'published';
      case 'building': return c.state === 'building' || c.state === 'rejected';
      case 'review': return c.state === 'review';
      case 'hidden': return !c.is_active && !String(c.archived_at || '').trim();
      case 'archived': return c.state === 'archived';
      case 'rejected': return c.state === 'rejected';
      default: return true;
    }
  }
  function drawList(v) {
    var b = C.board(rowsOf('courses', 'courses'), { now: now() });
    if (b.na) { v.innerHTML = '<div class="v2co" data-screen="list">' + (pending('courses') ? loadingBlock('الدورات') : unavailable('الدورات')) + '</div>'; return; }
    var all = listItems(b);
    var chips = [['all', 'الكل', all.length], ['published', 'منشورة', b.counts.published], ['building', 'تحت البناء', b.counts.building], ['review', 'في المراجعة', b.counts.review],
                 ['hidden', 'مخفية', b.counts.hidden], ['archived', 'مؤرشفة', b.counts.archived], ['rejected', 'أُعيدت', b.counts.rejected]].map(function (x) {
      return '<button type="button" class="v2co-fchip' + (S.filter === x[0] ? ' on' : '') + '" aria-pressed="' + (S.filter === x[0]) + '" data-a="filter" data-f="' + x[0] + '">' + esc(x[1]) + ' <b>' + esc(ar(x[2])) + '</b></button>';
    }).join('');
    var extras = K2 ? K2.c2Extras(c2Rows(), rowsOf('courses', 'courses') || []) : [];
    var extraHtml = extras.length ? '<section class="v2co-card v2ce-extras" aria-label="دورات المحرّر"><h2 class="v2co-h2">دورات من المحرّر</h2><ul class="v2ce-xl">' + extras.map(function (x) {
      return '<li><button type="button" class="v2co-lrow v2ce-xr" data-a="open" data-id="' + esc(x.id) + '"><span class="v2co-lt"><b>' + esc(x.title || 'دورة بلا عنوان') + '</b>' + c2Meta(x) + '</span></button></li>'; }).join('') + '</ul></section>' : '';
    v.innerHTML = '<div class="v2co" data-screen="list">' + noteStrip()
      + '<div class="v2co-top"><button type="button" class="v2co-link back" data-a="board">‹ اللوحة</button><button type="button" class="v2co-main" data-a="create">' + PLUS + 'أنشئ دورة</button></div>' + extraHtml
      + '<div class="v2co-fchips" role="group" aria-label="تصفية الدورات">' + chips + '</div>'
      + '<div class="v2co-search"><input type="search" id="co_q" placeholder="ابحث بعنوان الدورة أو اسم المدرّب" value="' + esc(S.search) + '" aria-label="بحث في الدورات" autocomplete="off"></div>'
      + '<div class="v2co-lhead" aria-hidden="true"><span>الدورة</span><span>المدرّب</span><span>النوع</span><span>المتعلّمون</span><span>السعر</span><span>الحالة</span></div>'
      + '<ul class="v2co-lrows" id="co_lbody">' + listRowsHtml(all) + '</ul></div>';
  }
  function listRowsHtml(all) {
    var term = S.search.trim().toLowerCase();
    var rows = all.filter(function (c) {
      if (!matchFilter(c, S.filter)) return false;
      if (!term) return true;
      return String(c.title || '').toLowerCase().indexOf(term) > -1 || String(C.trainerOf(c)).toLowerCase().indexOf(term) > -1;
    });
    if (!rows.length) return '<li class="v2co-lnone">' + none('لا دورات تطابق هذا الاختيار') + '</li>';
    return rows.map(function (c) {
      var type = (C.TYPE_LABEL[c.type] || '') + (c.story ? ' · تفاعلية' : '');
      var pr = C.priceOf(c);
      return '<li><button type="button" class="v2co-lrow" data-a="open" data-id="' + esc(c.id) + '">'
        + '<span class="v2co-lc1">' + coverHtml(c, 'sm') + '<span class="v2co-lt"><b>' + esc(c.title || 'دورة بلا عنوان') + '</b><small>' + esc(C.trainerOf(c) + ' · ' + type) + '</small>' + c2Meta(c) + '</span></span>'
        + '<span class="v2co-lc2">' + esc(C.trainerOf(c)) + '</span><span class="v2co-lc3">' + esc(type) + '</span>'
        + '<span class="v2co-lc4"><em>المتعلّمون: </em>' + esc(ar(c.total_enrolled || 0)) + '</span><span class="v2co-lc5">' + esc(pr.ok === false ? 'بلا سعر' : pr.text) + '</span>'
        + '<span class="v2co-lc6">' + stateChip(c.state) + '</span></button></li>';
    }).join('');
  }

  // ------------------------------------------------------------------ المدرّبون
  function appTicketHtml(a) {
    var more = a.moreChips ? chip('+' + ar(a.moreChips), 'grey') : '';
    return '<article class="v2co-t tone-' + esc(a.tone === 'none' ? 'ok' : a.tone) + '" data-id="' + esc(a.id) + '">'
      + '<div class="v2co-strip"><span class="v2co-type">طلب مدرّب جديد</span>' + timeHtml(a.text, a.tone, a.timer && a.timer.at) + '</div>'
      + '<div class="v2co-body"><h3><button type="button" class="v2co-open" data-a="appopen" data-id="' + esc(a.id) + '">' + esc(a.name) + '</button></h3>'
      + (a.headline ? '<p class="v2co-who">' + esc(a.headline) + '</p>' : '')
      + (a.chips.length ? '<p class="v2co-chips">' + a.chips.map(function (x) { return chip(x, 'grey'); }).join('') + more + '</p>' : '')
      + '<div class="v2co-brain">' + BRAIN + '<p>' + esc(a.line) + '</p></div>'
      + '<div class="v2co-acts two">' + (a.suggestion === 'accept' ? '<button type="button" class="v2co-btn1" data-a="appaccept" data-id="' + esc(a.id) + '">اقبله وأرسل الاتفاقية</button>'
        : '<button type="button" class="v2co-btn1" data-a="appopen" data-id="' + esc(a.id) + '">افتح الطلب</button>')
      + '<button type="button" class="v2co-btn2" data-a="appreject" data-id="' + esc(a.id) + '">ارفض</button></div></div></article>';
  }
  function trainerRowHtml(r) {
    return '<li class="v2co-trw">' + avatar(r.name) + '<div class="v2co-trt"><b>' + personLink(r.name, r.email) + '</b>' + (r.countsText ? '<span class="v2co-l1">' + esc(r.countsText) + '</span>' : '')
      + (r.statusLine ? '<span class="v2co-st ' + (r.tone === 'late' ? 'red' : (r.tone === 'warn' ? 'amber' : '')) + '">' + esc(r.statusLine) + '</span>' : '') + '</div>'
      + '<details class="v2co-kebab"><summary aria-label="المزيد عن ' + esc(r.name) + '"><svg viewBox="0 0 24 24" class="v2co-ic" aria-hidden="true"><circle cx="12" cy="5" r="1.6"/><circle cx="12" cy="12" r="1.6"/><circle cx="12" cy="19" r="1.6"/></svg></summary>'
      + '<div class="v2co-menu">' + (r.email ? '<a class="v2co-mi" href="' + esc(L.sectionHash('people', 'person', r.email)) + '" data-person="' + esc(r.email) + '">افتح صفحة الشخص</a>' : '')
      + '<button type="button" class="v2co-mi red" data-a="tstop" data-email="' + esc(r.email) + '">أوقف كمدرّب</button></div></details></li>';
  }
  function drawTrainers(v) {
    var apps = C.appTickets(rowsOf('apps', 'applications'), { now: now() });
    var rows = C.trainerRows(rowsOf('experts', 'experts'), rowsOf('courses', 'courses'), { now: now() });
    var failed = failedLabels(['courses']);
    var appsHtml;
    if (!apps) appsHtml = pending('apps') ? loadingBlock('طلبات المدرّبين') : unavailable('طلبات المدرّبين');
    else appsHtml = apps.length ? '<div class="v2co-tgrid two">' + apps.map(appTicketHtml).join('') + '</div>' : '<div class="v2co-empty"><b>لا طلبات انضمام جديدة</b></div>';
    var listHtml;
    if (!rows) listHtml = pending('experts') ? loadingBlock('المدرّبين') : unavailable('المدرّبين');
    else {
      var listed = rows.filter(function (r) { return r.listed; }), others = rows.length - listed.length;
      listHtml = (listed.length ? '<ul class="v2co-trlist">' + listed.map(trainerRowHtml).join('') + '</ul>' : none('لا مدرّبين لهم دورات بعد'))
        + (others > 0 ? '<p class="v2co-fine">و' + esc(U.U(others, ['خبير معتمد واحد', 'خبيران معتمدان', 'خبراء معتمدين', 'خبيرًا معتمدًا'])) + ' بلا دورات بعد <button type="button" class="v2co-link" data-a="goto" data-s="files" data-t="experts">اعرضهم في «ملفات الخبراء»</button></p>' : '');
    }
    var seg = S.tr || (apps && apps.length ? 'apps' : (apps ? 'list' : 'apps'));
    var segHtml = '<button type="button" role="tab" class="v2co-segb' + (seg === 'apps' ? ' on' : '') + '" aria-selected="' + (seg === 'apps') + '" data-a="trseg" data-seg="apps"><span>الطلبات</span><b>' + esc(apps ? ar(apps.length) : '—') + '</b></button>'
      + '<button type="button" role="tab" class="v2co-segb' + (seg === 'list' ? ' on' : '') + '" aria-selected="' + (seg === 'list') + '" data-a="trseg" data-seg="list"><span>المدرّبون</span><b>' + esc(rows ? ar(rows.filter(function (r) { return r.listed; }).length) : '—') + '</b></button>';
    v.innerHTML = '<div class="v2co" data-screen="trainers">' + noteStrip() + warnStrip(failed)
      + '<div class="v2co-seg" role="tablist" aria-label="الطلبات والمدرّبون">' + segHtml + '</div>'
      + '<div class="v2co-two" data-active="' + seg + '"><section class="v2co-colbox" data-col="apps"><h2 class="v2co-h2">طلبات المدرّبين <span class="v2co-cnt">' + esc(apps ? ar(apps.length) : '—') + '</span></h2>' + appsHtml + '</section>'
      + '<section class="v2co-colbox card" data-col="list"><h2 class="v2co-h2">المدرّبون</h2>' + listHtml + '</section></div></div>';
    if (window.V2TS) window.V2TS.mount(q('.v2co', v));       // نسبة المدرّب (v2s/trainer_share.js)
  }

  // ------------------------------------------------------------------ الدورات الحيّة
  function liveTicketHtml(t) {
    var strip = t.timer ? timeHtml(t.timerText, (t.timer.at < now() ? 'late' : 'warn'), t.timer.at) : '<time class="v2co-time tone-none">' + esc(t.label) + '</time>';
    var sec = t.secondary.map(function (x) { return '<button type="button" class="v2co-btn2' + (x.key === 'cancel' ? ' red' : '') + '" data-a="live-' + x.key + '" data-slug="' + esc(t.slug) + '">' + esc(x.label) + '</button>'; }).join('');
    return '<article class="v2co-t tone-late" data-slug="' + esc(t.slug) + '"><div class="v2co-strip"><span class="v2co-type">دورة حيّة تحتاج قرارك</span>' + strip + '</div>'
      + '<div class="v2co-body"><h3><button type="button" class="v2co-open" data-a="live-open" data-slug="' + esc(t.slug) + '">' + esc(t.title) + '</button></h3>'
      + '<p class="v2co-who">' + esc([t.trainer, t.startText].filter(Boolean).join(' · ')) + '</p>'
      + '<div class="v2co-brain">' + BRAIN + '<p>' + esc(t.line) + '</p></div>'
      + '<div class="v2co-acts stack"><button type="button" class="v2co-btn1" data-a="live-' + t.main.key + '" data-slug="' + esc(t.slug) + '">' + esc(t.main.label) + '</button>' + sec + '</div></div></article>';
  }
  function liveRowHtml(r) {
    var acts = '<span class="v2co-lacts"><button type="button" class="v2co-btn2" data-a="live-edit" data-slug="' + esc(r.slug) + '">عدّل الموعد</button>'
      + '<button type="button" class="v2co-btn2" data-a="live-who" data-slug="' + esc(r.slug) + '">من حجز</button>'
      + (r.canceled ? '<button type="button" class="v2co-btn2" data-a="live-paid" data-slug="' + esc(r.slug) + '">من دفع</button>' : '') + '</span>';
    var seats = r.booked != null && r.max != null ? ar(r.booked) + ' من ' + ar(r.max) : NA;
    return '<li class="v2co-lv"><span class="v2co-vc1"><button type="button" class="v2co-open" data-a="live-open" data-slug="' + esc(r.slug) + '">' + esc(r.title) + '</button><small>' + esc(r.trainer) + '</small></span>'
      + '<span class="v2co-vc2">' + esc([r.dateText, r.timeText].filter(Boolean).join(' · ')) + '</span>'
      + '<span class="v2co-vc3"><em>المقاعد: </em>' + esc(seats) + '</span><span class="v2co-vc4"><em>الحد الأدنى: </em>' + esc(r.quorum != null ? ar(r.quorum) : NA) + '</span>'
      + '<span class="v2co-vc5">' + chip(r.statusText, r.status === 'confirmed' ? 'green' : (r.canceled ? 'grey' : 'amber')) + '</span>'
      + '<span class="v2co-vc6"><em>رابط اللقاء: </em>' + (r.hasZoom ? 'موجود' : 'غير موجود') + '</span>' + acts + '</li>';
  }
  function drawLive(v) {
    var T = C.liveTickets(rowsOf('schedules', 'schedules'), queueLive(), { now: now() });
    var failed = failedLabels(['courses']);
    var dec;
    if (!T.decide) dec = epState('opsQueue') === 'error' ? '<div class="v2co-empty sm"><b>الدورات التي تحتاج قرارًا: ' + NA + '</b>' + retryBtn() + '</div>' : (epState('opsQueue') === 'ready' ? '' : loadingBlock('الدورات التي تحتاج قرارًا'));
    else dec = T.decide.length ? '<h2 class="v2co-h2">تحتاج قرارك <span class="v2co-cnt">' + esc(ar(T.decide.length)) + '</span></h2><div class="v2co-tgrid three">' + T.decide.map(liveTicketHtml).join('') + '</div>'
      : '<p class="v2co-none">لا دورات حيّة تنتظر قرارك</p>';
    var all;
    if (!T.all) all = pending('schedules') ? loadingBlock('الدورات الحيّة') : unavailable('الدورات الحيّة');
    else all = T.all.length ? '<div class="v2co-lvhead" aria-hidden="true"><span>الدورة</span><span>الموعد</span><span>المقاعد</span><span>الحد الأدنى</span><span>الحالة</span><span>رابط اللقاء</span><span></span></div><ul class="v2co-lvl">' + T.all.map(liveRowHtml).join('') + '</ul>'
      : '<div class="v2co-empty"><b>لا توجد دورات حيّة بعد</b></div>';
    v.innerHTML = '<div class="v2co" data-screen="live">' + noteStrip() + warnStrip(failed) + dec + '<h2 class="v2co-h2">كل الدورات الحيّة</h2>' + all + '</div>';
  }

  // ------------------------------------------------------------------ ما يطلبه الناس
  function programTicketHtml(p) {
    return '<article class="v2co-t tone-ok" data-id="' + esc(p.id) + '"><div class="v2co-strip"><span class="v2co-type">طلب برنامج</span>' + timeHtml(p.text, 'ok', p.timer && p.timer.at) + '</div>'
      + '<div class="v2co-body"><h3>' + esc(p.title) + '</h3><p class="v2co-who">' + (p.email ? personLink(p.requester, p.email) : esc(p.requester)) + '</p>'
      + '<div class="v2co-brain">' + BRAIN + '<p>' + esc(p.line) + '</p></div>'
      + '<div class="v2co-acts two"><button type="button" class="v2co-btn1" data-a="prog-accept" data-id="' + esc(p.id) + '">اقبل الطلب</button><button type="button" class="v2co-btn2" data-a="prog-reject" data-id="' + esc(p.id) + '">ارفض</button></div></div></article>';
  }
  function drawDemand(v) {
    var an = epState('analysis') === 'ready' ? (ep().data.analysis || {}) : null;
    var D = C.demand(data('progStats'), data('programs'), an, { now: now() });
    S.demand = D;
    var failed = failedLabels(['progStats', 'programs']).concat(epState('analysis') === 'error' ? ['أسئلة الشات'] : []);
    var topLine = D.topLine ? '<p class="v2co-sum"><img class="v2co-bav" src="' + img('brain-avatar') + '" alt="">' + esc(D.topLine) + '</p>' : '';
    var prog;
    if (!D.programs) prog = pending('programs') ? loadingBlock('طلبات البرامج') : unavailable('طلبات البرامج');
    else prog = D.programs.length ? '<div class="v2co-tgrid two">' + D.programs.map(programTicketHtml).join('') + '</div>' : '<div class="v2co-empty"><b>لا طلبات تنتظرك</b></div>';
    var top;
    if (!D.top) top = pending('progStats') ? loadingBlock('أكثر الدورات طلبًا') : unavailable('أكثر الدورات طلبًا');
    else top = D.top.length ? '<ul class="v2co-bars">' + D.top.map(function (r) {
      return '<li><div class="v2co-bl"><span>' + esc(r.title) + '</span><b>' + esc(r.countText) + '</b></div><div class="v2co-bar" role="img" aria-label="' + esc(r.title + ': ' + r.countText) + '"><i style="width:' + r.width + '%"></i></div></li>'; }).join('') + '</ul>'
      : none('لا طلبات على دورات بعد');
    var chat;
    if (!D.chat) chat = epState('analysis') === 'error' ? '<div class="v2co-empty sm"><b>أسئلة الشات: ' + NA + '</b></div>' : loadingBlock('أسئلة الشات');
    else chat = '<p class="v2co-fine">' + esc(D.chat.sampleText) + '</p>' + (D.chat.groups.length ? '<ul class="v2co-qs">' + D.chat.groups.map(function (g, i) {
      return '<li><div><b>' + esc(g.category) + '</b> <span class="v2co-cntx">' + esc(g.countText) + '</span><p>مثال: ' + esc(g.example) + '</p></div><button type="button" class="v2co-link" data-a="mk" data-i="' + i + '">أنشئ دورة بهذا العنوان</button></li>'; }).join('') + '</ul>'
      : none('لا أسئلة عن دورات في هذه العيّنة'));
    v.innerHTML = '<div class="v2co" data-screen="demand">' + noteStrip() + warnStrip(failed) + topLine
      + '<div class="v2co-dgrid"><section class="v2co-dleft"><h2 class="v2co-h2">طلبات تنتظرك</h2>' + prog + '</section>'
      + '<aside class="v2co-dright"><section class="v2co-card"><h2 class="v2co-h2">أكثر الدورات طلبًا</h2>' + top + '</section><section class="v2co-card"><h2 class="v2co-h2">من أسئلة الشات</h2>' + chat + '</section></aside></div></div>';
  }

  // ------------------------------------------------------------------ عروض الأسعار
  function offerTicketHtml(o) {
    var amounts = '<dl class="v2co-amt">' + o.amounts.map(function (a) { return '<div><dt>' + esc(a.k) + '</dt><dd>' + esc(a.v) + '</dd></div>'; }).join('') + '</dl>';
    var acceptMain = o.suggestion === 'approve';
    var main = acceptMain ? '<button type="button" class="v2co-btn1" data-a="offer-accept" data-id="' + esc(o.id) + '">اقبل العرض</button>' : '<button type="button" class="v2co-btn1" data-a="offer-counter" data-id="' + esc(o.id) + '">اعرض سعرًا آخر</button>';
    var other = acceptMain ? '<button type="button" class="v2co-btn2" data-a="offer-counter" data-id="' + esc(o.id) + '">اعرض سعرًا آخر</button>' : '<button type="button" class="v2co-btn2" data-a="offer-accept" data-id="' + esc(o.id) + '">اقبل العرض</button>';
    return '<article class="v2co-t tone-wait" data-id="' + esc(o.id) + '"><div class="v2co-strip"><span class="v2co-type">عرض سعر</span>' + timeHtml(o.text, 'ok', o.timer && o.timer.at) + '</div>'
      + '<div class="v2co-body"><h3>' + esc(o.course) + '</h3><p class="v2co-who">' + (o.buyerEmail ? personLink(o.buyer, o.buyerEmail) : esc(o.buyer)) + ' · ' + esc(o.segment) + '</p>' + amounts
      + (o.message ? '<blockquote class="v2co-q">سبب العرض: ' + esc(o.message) + '</blockquote>' : '')
      + '<div class="v2co-brain">' + BRAIN + '<p>' + esc(o.line) + '</p></div>'
      + '<div class="v2co-acts stack">' + main + other + '<button type="button" class="v2co-btn2 red" data-a="offer-reject" data-id="' + esc(o.id) + '">ارفض</button></div></div></article>';
  }
  function drawOffers(v) {
    var T = C.offerTickets(rowsOf('offers', 'offers'), { now: now() });
    S.offerRows = T || [];
    var body;
    if (!T) body = pending('offers') ? loadingBlock('عروض الأسعار') : unavailable('عروض الأسعار');
    else body = T.length ? '<div class="v2co-tgrid three">' + T.map(offerTicketHtml).join('') + '</div>' : '<div class="v2co-empty"><b>لا عروض أسعار تنتظرك</b></div>';
    v.innerHTML = '<div class="v2co" data-screen="offers">' + noteStrip() + body + '</div>';
  }

  // ------------------------------------------------------------------ صفحة الدورة
  function contentHtml(c, m, id) {
    var story = c.story && c.story.lessons > 0;
    if (story) {
      return '<p>دورة تفاعلية: ' + esc(ar(c.story.lessons) + ' درسًا في ' + ar(c.story.units) + ' أجزاء، نحو ' + ar(c.story.minutes) + ' دقيقة') + '.</p>'
        + (m.hasPreview ? '<a class="v2co-btn2 inl" href="' + esc(window.pcPreviewUrl ? window.pcPreviewUrl(c) : '#') + '" target="_blank" rel="noopener noreferrer">شاهدها كما يراها المتعلّم</a>' : '');
    }
    var st = srcState('detail:' + id), d = data('detail:' + id);
    if (!d) return st === 'loading' || st === 'idle' ? '<p class="v2co-mute">…جارٍ جلب المحتوى</p>' : '<p class="v2co-mute">المحتوى: ' + NA + '</p><button type="button" class="v2co-btn2" data-a="retrydetail" data-id="' + esc(id) + '">أعد المحاولة</button>';
    var secs = Array.isArray(d.sections) ? d.sections : [], les = Array.isArray(d.lessons) ? d.lessons : [];
    var out = '';
    if (secs.length && secs.some(function (s) { return (s.lessons || []).length; })) {
      out += secs.map(function (s) {
        var ls = Array.isArray(s.lessons) ? s.lessons : [];
        return '<div class="v2co-sec"><b>' + esc(s.title || 'بلا قسم') + ' <small>(' + esc(U.U(ls.length, ['محاضرة واحدة', 'محاضرتان', 'محاضرات', 'محاضرة'])) + ')</small></b><ul>'
          + ls.map(function (x) { return '<li>' + esc(x.title || 'محاضرة') + (x.is_preview ? ' ' + chip('معاينة مجانية', 'green') : '') + '</li>'; }).join('') + '</ul></div>';
      }).join('');
    }
    if (les.length) {
      var qn = les.reduce(function (n, x) { return n + (Array.isArray(x.quiz) ? x.quiz.length : 0); }, 0);
      out += '<p>' + esc(U.U(les.length, ['درس مكتوب واحد', 'درسان مكتوبان', 'دروس مكتوبة', 'درسًا مكتوبًا']) + '، وفيها ' + U.U(qn, ['سؤال واحد', 'سؤالان', 'أسئلة', 'سؤالًا'])) + '.</p>';
    }
    return out || '<p class="v2co-mute">لا محاضرات ولا دروس بعد.</p>';
  }
  function checklistCard(c, m, cst) {
    var items = m.facts.items.map(function (i) {
      if (i.ok === true) return '<li class="ok"><span aria-hidden="true">✓</span>' + esc(i.pos) + '</li>';
      if (i.ok === false) return '<li class="bad"><span aria-hidden="true">✗</span>' + esc(i.label) + '</li>';
      return '<li class="na">' + esc((i.name || i.label) + ': ' + NA) + '</li>';
    });
    if (cst !== 'ready' && cst !== 'loading') items.push('<li class="na">' + esc('بنود الفحص: ' + NA) + '</li>');
    var btns = '';
    if (m.state === 'review') {
      if (m.decisionBlock) {
        var miss = m.facts.unknown.length ? 'لا أستطيع أن أقترح: ' + m.facts.unknown.join('، ') + ' ' + NA : 'القرار لك';
        btns = '<div class="v2co-decide"><h3>القرار لك</h3><div class="v2co-brain">' + BRAIN + '<p>' + esc(miss) + '</p></div>'
          + (m.main && m.main.key === 'refetch' ? '<button type="button" class="v2co-btn1" data-a="refetch" data-id="' + esc(c.id) + '">أعد جلب الفحص</button>' : '')
          + '<div class="v2co-eq"><button type="button" class="v2co-btn1 outline" data-a="approve" data-id="' + esc(c.id) + '" data-unknown="1">انشرها</button>'
          + '<button type="button" class="v2co-btn1 outline" data-a="return" data-id="' + esc(c.id) + '">أعِدها بملاحظات</button></div></div>';
      } else {
        btns = '<div class="v2co-brain">' + BRAIN + '<p>' + esc(m.facts.line) + '</p></div><div class="v2co-acts stack">'
          + '<button type="button" class="v2co-btn1" data-a="' + (m.main.key === 'publish' ? 'approve' : m.main.key) + '" data-id="' + esc(c.id) + '">' + esc(m.main.label) + '</button>'
          + m.secondary.map(function (x) { return '<button type="button" class="v2co-btn2" data-a="' + (x.key === 'publish' ? 'approve' : x.key) + '" data-id="' + esc(c.id) + '">' + esc(x.label) + '</button>'; }).join('') + '</div>';
      }
    } else if (m.main) btns = '<div class="v2co-acts stack"><button type="button" class="v2co-btn1" data-a="' + m.main.key + '" data-id="' + esc(c.id) + '">' + esc(m.main.label) + '</button></div>';
    else if (m.secondary.length) btns = '<div class="v2co-acts stack">' + m.secondary.map(function (x) { return '<button type="button" class="v2co-btn2" data-a="' + x.key + '" data-id="' + esc(c.id) + '">' + esc(x.label) + '</button>'; }).join('') + '</div>';
    return '<section class="v2co-card"><h2 class="v2co-h2"><img class="v2co-bav" src="' + img('brain-avatar') + '" alt="">فحص النشر</h2><ul class="v2co-chk">' + items.join('') + '</ul>' + btns + '</section>';
  }
  function drawCourse(v) {
    var id = (host().state && host().state().course) || '';
    var back = '<button type="button" class="v2co-link back" data-a="all-courses">‹ كل الدورات</button>';
    if (window.V2CE && id && (S.editing === id || (!pending('courses') && !courseById(id) && c2ById(id)))) { S.editing = id; load('courses2'); window.V2CE.draw(v, id); return; }
    if (pending('courses')) { v.innerHTML = '<div class="v2co" data-screen="course">' + back + '<div class="v2co-skw">' + skeleton(3) + '</div></div>'; return; }
    var c = courseById(id);
    if (!c) {
      v.innerHTML = '<div class="v2co" data-screen="course">' + back + (srcState('courses') === 'ready' ? '<div class="v2co-empty"><b>الدورة: ' + NA + '</b><p>لم نجد هذه الدورة في قائمة الدورات.</p></div>' : unavailable('الدورة')) + '</div>';
      return;
    }
    load('detail:' + id); load('stats'); load('shares');
    if (c.type === 'live_upcoming') load('schedules');
    if (C.stateOf(c) === 'review') load('checklist:' + id);
    var cst = checklistStateOf(id);
    var m = C.pageModel(c, data('detail:' + id), C.statFor(data('stats'), c), checklistOf(id), schedOf(c), { now: now(), checklistState: cst });
    var hero = m.hero ? '<img class="v2co-himg" src="' + esc(m.hero) + '" alt="">' : '<img class="v2co-himg" src="' + img('courses') + '" alt="">';
    var chips = [stateChip(m.state), chip(m.typeLabel, 'grey')].concat(m.interactive ? [chip('تفاعلية', 'wine')] : [], m.sourceLabel ? [chip(m.sourceLabel, 'grey')] : []).join('');
    var tiles = '<div class="v2co-nums"><div class="v2co-tiles"><div class="v2co-tile"><span>المتعلّمون</span><b>' + esc(m.tiles.learners) + '</b></div>'
      + '<div class="v2co-tile"><span>الدروس</span><b>' + esc(m.tiles.lessons) + '</b></div>'
      + '<div class="v2co-tile"><span>السعر</span><b>' + esc(m.tiles.price) + '</b><button type="button" class="v2co-link" data-a="goto" data-s="money" data-t="prices">غيّر السعر من «الفلوس»</button></div>'
      + '<div class="v2co-tile' + (m.tiles.sales.na ? ' na' : '') + '"><span>المبيعات</span><b>' + esc(m.tiles.sales.text) + '</b></div></div><p class="v2co-fine">' + esc(m.completion) + '</p></div>';
    var bid = m.bid.show ? '<section class="v2co-card"><h2 class="v2co-h2">البيع</h2><label class="v2co-tg"><input type="checkbox" id="co_bid"' + (m.bid.enabled ? ' checked' : '') + ' data-a="bid" data-id="' + esc(c.id) + '"> يقبل عروض الأسعار</label>'
      + '<p class="v2co-fine">يستطيع المشتري أن يقترح سعرًا أقل، وتصلك العروض في «عروض الأسعار»</p></section>' : '';
    var livec = '';
    if (m.live) {
      livec = '<section class="v2co-card"><h2 class="v2co-h2">الدورة الحيّة</h2>' + (m.live.na ? '<p class="v2co-mute">موعد الدورة: ' + NA + '</p>' :
        '<ul class="v2co-lvfacts"><li>' + esc('تبدأ ' + m.live.startText + (m.live.timeText ? ' · ' + m.live.timeText : '')) + '</li><li>' + esc(m.live.seats) + '</li><li>' + esc(m.live.quorum) + '</li><li>' + (m.live.status ? chip(m.live.status, 'amber') : '') + '</li><li>' + esc(m.live.zoom) + '</li></ul>')
        + '<div class="v2co-acts stack"><button type="button" class="v2co-btn2" data-a="live-edit" data-slug="' + esc(c.slug) + '">عدّل الموعد</button><button type="button" class="v2co-btn2" data-a="live-who" data-slug="' + esc(c.slug) + '">من حجز</button></div></section>';
    }
    var danger = m.danger ? '<section class="v2co-card danger"><h2 class="v2co-h2">إجراءات لا رجعة سهلة فيها</h2><button type="button" class="v2co-btn2 red" data-a="' + (m.danger === 'delete' ? 'delete' : 'archive') + '" data-id="' + esc(c.id) + '">' + (m.danger === 'delete' ? 'احذفها نهائيًا' : 'أرشف الدورة') + '</button></section>' : '';
    var note = m.state === 'rejected' && m.reviewNote ? '<div class="v2co-warn" role="status">أُعيدت بملاحظات: ' + esc(m.reviewNote) + '</div>' : '';
    var failed = failedLabels(['schedules']);
    var heroHtml = '<section class="v2co-hero">' + hero + '<div class="v2co-hb"><h1>' + esc(m.title) + '</h1><p class="v2co-chips">' + chips + '</p><p class="v2co-who">'
      + (c.platform_owned === true ? 'البروفيسور' : (m.trainerEmail ? personLink(m.trainer, m.trainerEmail) : esc(m.trainer))) + '</p></div></section>';
    var side = '<aside class="v2co-pgside">' + (m.state === 'archived'
      ? '<section class="v2co-card"><h2 class="v2co-h2">مؤرشفة</h2><p class="v2co-fine">لا يراها متعلّمون جدد، والمسجّلون ودفعاتهم تبقى كما هي.</p><div class="v2co-acts stack"><button type="button" class="v2co-btn1" data-a="show" data-id="' + esc(c.id) + '">أعِد نشرها</button></div></section>'
      : checklistCard(c, m, cst)) + '</aside>';
    var contentCard = '<section class="v2co-card"><h2 class="v2co-h2">المحتوى</h2>' + contentHtml(c, m, id) + '<div class="v2co-acts stack"><button type="button" class="v2co-btn1" data-a="edit-course" data-id="' + esc(c.id) + '">حرّر الدورة</button></div></section>';
    v.innerHTML = '<div class="v2co" data-screen="course">' + noteStrip() + warnStrip(failed) + back
      + '<div class="v2co-pg">' + heroHtml + note + tiles + side + bid + livec + contentCard + danger + '</div></div>';
  }

  // ------------------------------------------------------------------ «كل السجلات» (الشاشة القديمة بشكل جديد)
  var LEGACY_NOTE = 'هنا ما بقي من الشاشة السابقة للدورات: تعديل الدروس والمنهج، وإنشاء منهج مكتوب، وسجلّ الإدارة للاطلاع. القرارات كلها في التبويبات الجديدة.';
  // أرقام الشاشة القديمة لاتينية في أماكن (عدّاد التبويبات مثلًا)؛ نعرضها بالأرقام العربية كباقي اللوحة، دون المساس بالنص نفسه ولا بالروابط والمعرّفات.
  // كلمات منعها قانون المؤسس تظهر في الشاشة القديمة (رموز العملة والأسماء اللاتينية والنطاق ووسم «مزايدة»): نبدّلها بنص عربي بسيط داخل إطار «كل السجلات» وأوراقه فقط.
  var LEGACY_WORDS = [
    [/EGP\s*([\d٠-٩][\d٠-٩.,٬]*)/g, function (m, n) { return n + ' جنيه مصري'; }], [/([\d٠-٩][\d٠-٩.,٬]*)\s*EGP/g, function (m, n) { return n + ' جنيه مصري'; }], [/\bEGP\b/g, 'جنيه مصري'],
    [/\bUSD\b/g, 'دولار'], [/\bSAR\b/g, 'ريال سعودي'], [/\bAED\b/g, 'درهم إماراتي'],
    [/([\d٠-٩][\d٠-٩.,٬]*)\s*ج(?![\u0621-\u064A])/g, function (m, n) { return n + ' جنيه'; }],
    [/بمنهج\s+Titch/g, 'بمنهج مكتوب'], [/Titch\s*/g, 'المنهج المكتوب '],
    [/Google\s*Drive/g, 'جوجل درايف'], [/YouTube/g, 'يوتيوب'], [/\bDrive\b/g, 'درايف'],
    [/app\.elprofessor\.net/g, 'المنصة'],
    [/المزايدة/g, 'عروض الأسعار'], [/مزايدة/g, 'عروض الأسعار']
  ];
  var LEGACY_TEST = /EGP|USD|SAR|AED|Titch|Google|YouTube|Drive|app\.elprofessor|مزايدة|ج(?![\u0621-\u064A])/;
  function legacyWords(str) {
    if (!LEGACY_TEST.test(str)) return str;
    LEGACY_WORDS.forEach(function (r) { str = str.replace(r[0], r[1]); });
    return str.replace(/\s{2,}/g, ' ');
  }
  // أرقام الشاشة القديمة لاتينية في أماكن (عدّاد التبويبات مثلًا)؛ نعرضها بالأرقام العربية كباقي اللوحة، دون المساس بالروابط والمعرّفات.
  function arabize(root) {
    if (!root || !document.createTreeWalker) return;
    var w = document.createTreeWalker(root, 4, null), n, list = [];
    while ((n = w.nextNode())) { list.push(n); }
    list.forEach(function (t) {
      var p = t.parentNode;
      if (!p || /^(SCRIPT|STYLE|TEXTAREA|INPUT|OPTION)$/.test(p.nodeName)) return;
      var v = t.nodeValue, o = v;
      if (!(p.closest && p.closest('[dir="ltr"],a')) && /\d/.test(v)) v = v.replace(/\d/g, function (d) { return '٠١٢٣٤٥٦٧٨٩'.charAt(+d); });
      v = legacyWords(v);
      if (v !== o) t.nodeValue = v;
    });
    if (root.querySelectorAll) Array.prototype.forEach.call(root.querySelectorAll('[placeholder],[title],[aria-label]'), function (e) {
      ['placeholder', 'title', 'aria-label'].forEach(function (a) { var x = e.getAttribute(a); if (x && /Titch|YouTube|Google|EGP/.test(x)) e.setAttribute(a, legacyWords(x)); });
    });
  }
  function watchDigits(el, key) {
    if (!el || !window.MutationObserver) return;
    if (S[key]) { try { S[key].disconnect(); } catch (e) {} }
    var t = null;
    S[key] = new MutationObserver(function () { if (t) return; t = setTimeout(function () { t = null; arabize(el); }, 30); });
    S[key].observe(el, { childList: true, subtree: true });
    arabize(el);
  }
  function drawLegacy(v) {
    var snap = window.v2Snapshot ? window.v2Snapshot() : {};
    if (snap.courseTab !== 'courses' && snap.courseTab !== 'platform' && host().setLegacy) host().setLegacy('courseTab', 'courses');
    v.innerHTML = '<div class="v2co-legacy"><p class="v2co-legacy-note">' + esc(LEGACY_NOTE) + '</p><div id="v2coLegacyHost"></div></div>';
    var h = document.getElementById('v2coLegacyHost');
    if (h && typeof window.viewCourses === 'function') window.viewCourses(h);
    watchDigits(h, 'dObs');
  }

  // ------------------------------------------------------------------ الأوراق: دورة
  function afterCourseWrite(text, scr) {
    setNote(text, scr);
    load('courses', true); load('stats', true);
    var E = ep(); if (E && E.authed) { E.reload('opsQueue', null); }
    redraw();
  }
  function courseFactsOf(c) { return C.courseFacts(c, { schedule: schedOf(c), checklist: checklistOf(c.id), now: now(), checklistState: checklistStateOf(c.id) }); }
  function shareLine() {
    var sh = data('shares');
    var base = sh && sh.courses && typeof sh.courses.base === 'number' ? sh.courses.base : null;
    return '<p class="v2co-fine">' + (base != null ? 'النسبة الأساسية لأصحاب الدورات في جدول النسب: ' + esc(ar(base)) + '٪' : 'النسبة: ' + NA)
      + ' <button type="button" class="v2co-link" data-goto="money/shares" id="co_shares">جدول النسب في «الفلوس»</button></p>';
  }
  function bindGotoLinks(s) {
    qa('[data-goto]', s).forEach(function (b) { b.onclick = function () { var p = b.getAttribute('data-goto').split('/'); closeSheet(); goSection(p[0], p[1]); }; });
  }
  function openApprove(id, unknownBlock) {
    var c = courseById(id); if (!c) return;
    var facts = courseFactsOf(c);
    var owned = !!c.instructor_email && c.platform_owned !== true;
    var pay = owned ? '<fieldset class="v2co-radio"><legend>طريقة الدفع لصاحب الدورة</legend>'
      + '<label><input type="radio" name="co_pm" value="share" checked> نسبة من كل بيعة</label><label><input type="radio" name="co_pm" value="hourly"> أجر بالساعة بلا نسبة</label></fieldset>' : '';
    flow({
      title: 'انشر الدورة',
      form: '<p class="v2co-lead">نشر «' + esc(c.title) + '» للناس.</p>'
        + factsTable([['الدورة', esc(c.title)], ['صاحب الدورة', trainerHtml(c)], ['النوع', esc(C.TYPE_LABEL[c.type] || '')], ['السعر', esc(priceLine(c))], ['فحص النشر', esc(facts.line)]])
        + pay + (owned ? shareLine() : ''),
      wire: bindGotoLinks,
      collect: function (s) { var r = q('input[name="co_pm"]:checked', s); return { ok: true, payload: { pm: r ? r.value : '' } }; },
      review: function () {
        var items = ['تظهر الدورة للناس في المنصة'];
        if (c.platform_owned !== true) items.push('يصل إلى صاحب الدورة بريد بالنشر');
        if (unknownBlock && facts.unknown.length) items.push('لم يكتمل فحص النشر: ' + esc(facts.unknown.join('، ')));
        return '<p class="v2co-lead">ما سيحدث:</p>' + listHtml(items.map(function (t) { return typeof t === 'string' ? t : t; })) + '<p class="v2co-fine">إن كان صاحب الدورة لم يوقّع الاتفاقية أو كانت الدورة الحيّة بلا موعد بدء فستعرض المنصة السبب هنا.</p>';
      },
      btnNext: 'راجع قبل النشر', btnConfirm: 'أكّد النشر', busy: 'جارٍ النشر…',
      send: function (p) { var b = { confirmed: true }; if (p.pm) b.payout_model = p.pm; return post('/v2/courses/' + encodeURIComponent(id) + '/approve', b); },
      onOk: function () { afterCourseWrite('نُشرت «' + c.title + '»'); },
      onStale: function () { load('courses', true); }
    });
  }
  function openReturn(id) {
    var c = courseById(id); if (!c) return;
    var facts = courseFactsOf(c);
    var prefill = facts.suggestion === 'return' ? facts.returnNote : '';
    flow({
      title: 'أعِد الدورة بملاحظات',
      form: '<p class="v2co-lead">ستعود «' + esc(c.title) + '» إلى صاحبها بملاحظاتك، ولا تظهر للناس.</p>'
        + fld('co_note', 'ملاحظاتك لصاحب الدورة', '<textarea id="co_note" rows="4" maxlength="600">' + esc(prefill) + '</textarea>', 'تصل إلى صاحب الدورة في بريد كما تكتبها')
        + '<p class="v2co-fine" id="co_cnt"></p>',
      wire: function (s) {
        var t = q('#co_note', s), n = q('#co_cnt', s);
        function sync() { n.textContent = ar(t.value.length) + ' / ' + ar(600); }
        t.addEventListener('input', sync); sync();
        setTimeout(function () { try { t.focus(); } catch (e) {} }, 30);
      },
      ready: function (s) { return !!q('#co_note', s).value.trim(); },
      collect: function (s) { var v = q('#co_note', s).value.trim(); return v ? { ok: true, payload: { note: v } } : { ok: false, error: 'اكتب ملاحظاتك أولًا، فهي تصل إلى صاحب الدورة' }; },
      btnConfirm: 'أعِدها', busy: 'جارٍ الإرسال…',
      send: function (p) { return post('/v2/courses/' + encodeURIComponent(id) + '/reject', { confirmed: true, note: p.note }); },
      onOk: function () { afterCourseWrite('أُعيدت «' + c.title + '» بملاحظاتك'); },
      onStale: function () { load('courses', true); }
    });
  }
  function openVisibility(id, mode) {
    var c = courseById(id); if (!c) return;
    var on = mode !== 'hide';
    var items = on ? ['تظهر الدورة للناس الآن.'] : ['تختفي الدورة من المنصة للمتعلّمين الجدد، ويكمل المسجّلون (' + ar(c.total_enrolled || 0) + ') دراستهم.'];
    if (on && c.approval_status !== 'approved') items.push('هذه الدورة لم تمر بالمراجعة.');
    flow({
      title: on ? (mode === 'show' ? 'أعِد نشر الدورة' : 'انشر الدورة الآن') : 'أوقف ظهور الدورة',
      form: '<p class="v2co-lead">' + (on ? 'نشر «' + esc(c.title) + '» دون مرحلة المراجعة؟' : 'إيقاف ظهور «' + esc(c.title) + '»؟') + '</p>',
      review: function () { return '<p class="v2co-lead">ما سيحدث:</p>' + listHtml(items.map(esc)); },
      collect: function () { return { ok: true, payload: {} }; },
      btnNext: 'تابع', btnConfirm: on ? 'أكّد النشر' : 'أكّد الإيقاف', danger: !on, busy: 'جارٍ التنفيذ…',
      send: function () { return post('/v2/courses/' + encodeURIComponent(id) + '/visibility', { confirmed: true, is_active: on }); },
      onOk: function () { afterCourseWrite(on ? 'نُشرت «' + c.title + '»' : 'أُوقف ظهور «' + c.title + '»'); },
      onStale: function () { load('courses', true); }
    });
  }
  function openBid(id, target) {
    var c = courseById(id); if (!c) return;
    flow({
      title: 'عروض الأسعار',
      form: '<p class="v2co-lead">' + (target ? 'تفعيل عروض الأسعار على «' + esc(c.title) + '»؟' : 'إيقاف عروض الأسعار على «' + esc(c.title) + '»؟') + '</p>'
        + '<p class="v2co-fine">' + (target ? 'يستطيع المشتري أن يقترح سعرًا أقل، وتصلك العروض في «عروض الأسعار».' : 'لا يستطيع المشتري بعد الآن أن يقترح سعرًا.') + '</p>',
      collect: function () { return { ok: true, payload: {} }; },
      btnConfirm: target ? 'فعّل' : 'أوقف', busy: 'جارٍ الحفظ…',
      send: function () { return post('/v2/courses/' + encodeURIComponent(id) + '/bid', { confirmed: true, bid_enabled: target }); },
      onOk: function () { afterCourseWrite(target ? 'فُعّلت عروض الأسعار على «' + c.title + '»' : 'أُوقفت عروض الأسعار على «' + c.title + '»'); },
      onStale: function () { load('courses', true); }
    });
  }
  function openArchive(id, hard) {
    var c = courseById(id); if (!c) return;
    var n = c.total_enrolled || 0;
    var lead = hard ? 'تُحذف «' + esc(c.title) + '» من المنصة نهائيًا:' : 'تُؤرشف «' + esc(c.title) + '»:';
    var items = hard ? ['تختفي من قائمة الدورات ومن المنصة.', 'تُحذف دروسها ومنهجها وأسئلتها معها.', 'لا تراجع بعد الحذف.']
      : ['تختفي من قائمة الدورات في المنصة، ولا يراها متعلّمون جدد.', U.U(n, ['مسجّل واحد', 'مسجّلان', 'مسجّلون', 'مسجّلًا']) + ' ودفعاتهم وتقدّمهم تبقى كما هي، ويكمل المسجّل الحالي دراسته.', 'لا حذف: يمكنك إعادة نشرها من صفحة الدورة.'];
    flow({
      title: hard ? 'احذف الدورة نهائيًا' : 'أرشف الدورة',
      form: '<p class="v2co-lead">' + lead + '</p>' + listHtml(items.map(esc))
        + (hard ? '<p class="v2co-fine">الحذف متاح لأن الدورة مسودة بلا مسجّلين. إن وُجد عليها اشتراك أو دفعة سترفض المنصة الحذف، وعندها استعمل الأرشفة.</p>'
          + fld('co_t', 'اكتب عنوان الدورة للتأكيد', '<input id="co_t" type="text" autocomplete="off" placeholder="' + esc(c.title) + '">') : ''),
      ready: hard ? function (s) { return q('#co_t', s).value.trim() === String(c.title || '').trim(); } : null,
      collect: function () { return { ok: true, payload: {} }; },
      btnConfirm: hard ? 'احذفها نهائيًا' : 'أرشفها', danger: hard, busy: 'جارٍ التنفيذ…',
      send: function () { return post('/v2/courses/' + encodeURIComponent(id) + '/archive', { confirmed: true, hard: !!hard }); },
      onOk: function (res) {
        var deleted = res && res.deleted === true;
        S.list = true; S.keepList = true;
        afterCourseWrite(deleted ? 'حُذفت الدورة نهائيًا' : 'أُرشفت الدورة', 'board');
        goSection('courses', 'courses');
      },
      onStale: function () { load('courses', true); }
    });
  }

  // ------------------------------------------------------------------ الأوراق: مدرّبون
  function decideP(row, action, reason) {
    return ep().decideInboxItem(row, action, null, reason || '').then(function (r) {
      if (r && r.ok) return r;
      var e = new Error((r && r.error) || FAIL_AR);
      e.data = { error: r && r.error, no_reply: !!(r && r.noReply) };
      e.status = r && r.unauthorized ? 401 : (r && r.final ? 409 : 0);
      throw e;
    });
  }
  function appById(id) { var l = C.appTickets(rowsOf('apps', 'applications'), { now: now() }) || []; for (var i = 0; i < l.length; i++) if (l[i].id === id) return l[i]; return null; }
  function afterApp(text) {
    setNote(text); load('apps', true); load('experts', true); redraw();
  }
  function openAppAccept(id) {
    var a = appById(id); if (!a) return;
    flow({
      title: 'اقبل المدرّب',
      form: '<p class="v2co-lead">قبول ' + esc(a.name) + ' مدرّبًا؟</p>' + listHtml(['يصل إلى مقدّم الطلب بريد فيه اتفاقية التدريب ليوقّعها.', 'لا تُنشر أي دورة لمقدّم الطلب قبل توقيع الاتفاقية.'].map(esc)),
      collect: function () { return { ok: true, payload: {} }; },
      btnConfirm: 'اقبل وأرسل الاتفاقية', busy: 'جارٍ القبول…',
      send: function () { return decideP({ apiKind: 'trainer', apiId: id }, 'approve', ''); },
      onOk: function () { afterApp('قُبل ' + a.name + ' مدرّبًا، وأُرسلت إليه الاتفاقية'); },
      onStale: function () { load('apps', true); }
    });
  }
  function openAppReject(id) {
    var a = appById(id); if (!a) return;
    flow({
      title: 'ارفض الطلب',
      form: '<p class="v2co-lead">رفض طلب ' + esc(a.name) + '؟</p>' + fld('co_why', 'سبب الرفض', '<textarea id="co_why" rows="3" maxlength="600"></textarea>', 'يقرؤه مقدّم الطلب كما تكتبه'),
      wire: function (s) { setTimeout(function () { try { q('#co_why', s).focus(); } catch (e) {} }, 30); },
      ready: function (s) { return !!q('#co_why', s).value.trim(); },
      collect: function (s) { var v = q('#co_why', s).value.trim(); return v ? { ok: true, payload: { why: v } } : { ok: false, error: 'اكتب سبب الرفض، فهو يصل إلى مقدّم الطلب' }; },
      btnConfirm: 'ارفض الطلب', danger: true, busy: 'جارٍ الرفض…',
      send: function (p) { return decideP({ apiKind: 'trainer', apiId: id }, 'reject', p.why); },
      onOk: function () { afterApp('رُفض طلب ' + a.name); },
      onStale: function () { load('apps', true); }
    });
  }
  function openAppDetail(id) {
    var a = appById(id); if (!a) return;
    function link(url, label) { return url ? '<a href="' + esc(url) + '" target="_blank" rel="noopener noreferrer">' + esc(label) + '</a>' : ''; }
    var links = [link(a.links.linkedin, 'لينكدإن'), link(a.links.cv, 'السيرة الذاتية'), link(a.links.portfolio, 'نماذج الأعمال')].filter(Boolean).join(' · ');
    var s = openSheet('طلب ' + a.name, factsTable([['العنوان المهني', esc(a.headline || '—')], ['المجالات', esc(a.expertise.length ? a.expertise.join('، ') : 'بلا مجال محدّد')],
      ['نبذة الخبرة', esc(a.summary || '—')], ['الروابط', links || 'بلا روابط'], ['تاريخ التقديم', esc(a.createdAt ? U.dateText(a.createdAt) : '—')]])
      + '<div class="v2co-brain">' + BRAIN + '<p>' + esc(a.line) + '</p></div><div class="v2co-macts">'
      + (a.suggestion === 'accept' ? '<button type="button" class="v2co-btn1" id="co_acc">اقبله وأرسل الاتفاقية</button>' : '')
      + '<button type="button" class="v2co-btn2" id="co_rej">ارفض الطلب</button></div>'
      + (a.email ? '<p class="v2co-fine"><a class="v2co-person" href="' + esc(L.sectionHash('people', 'person', a.email)) + '" data-person="' + esc(a.email) + '" id="co_pp">افتح صفحة الشخص</a></p>' : ''));
    if (!s) return;
    var acc = q('#co_acc', s); if (acc) acc.onclick = function () { closeSheet(); openAppAccept(id); };
    q('#co_rej', s).onclick = function () { closeSheet(); openAppReject(id); };
    var pp = q('#co_pp', s); if (pp) pp.onclick = function (e) { e.preventDefault(); closeSheet(); if (host().openPerson) host().openPerson(a.email); };
  }
  function openStopTrainer(email) {
    var rows = C.trainerRows(rowsOf('experts', 'experts'), rowsOf('courses', 'courses'), { now: now() }) || [];
    var r = rows.filter(function (x) { return x.email === email; })[0];
    var name = r ? r.name : email;
    flow({
      title: 'أوقف كمدرّب',
      form: '<p class="v2co-lead">يُلغى اعتماد ' + esc(name) + ' مدرّبًا، ويختفي من دليل الخبراء.</p>' + listHtml(['الدورات المنشورة لصاحب الحساب لا تُحذف.'])
        + '<label class="v2co-tg"><input type="checkbox" id="co_test"> وسم الحساب تجريبيًا (لحسابات التجربة فقط)</label>'
        + fld('co_em', 'اكتب البريد للتأكيد', '<input id="co_em" type="text" dir="ltr" autocomplete="off" placeholder="' + esc(email) + '">')
        + fld('co_rs', 'السبب (اختياري)', '<input id="co_rs" type="text" maxlength="200" autocomplete="off">'),
      ready: function (s) { return q('#co_em', s).value.trim().toLowerCase() === String(email).toLowerCase(); },
      collect: function (s) { return { ok: true, payload: { test: !!q('#co_test', s).checked, reason: q('#co_rs', s).value.trim() } }; },
      btnConfirm: 'أوقف المدرّب', danger: true, busy: 'جارٍ الإيقاف…',
      send: function (p) {
        return ep().api('/platform-users?search=' + encodeURIComponent(email)).then(function (res) {
          var u = ((res && res.users) || []).filter(function (x) { return String(x.email || '').toLowerCase() === String(email).toLowerCase(); })[0];
          if (!u) { var e = new Error('x'); e.data = { error: 'لم نجد حساب هذا المدرّب على المنصة' }; e.status = 404; throw e; }
          return ep().api('/platform-trainers/' + encodeURIComponent(u.id) + '/deactivate', { method: 'POST', body: { reason: p.reason, is_test: p.test, email: email } });
        });
      },
      onOk: function () { afterApp('أُوقف ' + name + ' كمدرّب'); },
      onStale: function () { load('experts', true); }
    });
  }

  // ------------------------------------------------------------------ الأوراق: الدورات الحيّة
  function liveTitle(slug) { var c = courseBySlug(slug); if (c) return c.title; var r = (rowsOf('schedules', 'schedules') || []).filter(function (x) { return x.slug === slug; })[0]; return r ? r.title : slug; }
  function afterLive(text) { setNote(text); load('schedules', true); load('courses', true); var E = ep(); if (E && E.authed) E.reload('opsQueue', null); redraw(); }
  function refundsHtml(refunds) {
    var rows = Array.isArray(refunds) ? refunds : [];
    var need = rows.filter(function (r) { return !r.no_payment_found; }).length;
    if (!rows.length) return '<p class="v2co-lead">أُلغيت الدورة.</p><p class="v2co-fine">لا أحد دفع، فلا استرداد.</p>';
    return '<p class="v2co-lead">أُلغيت الدورة.</p><p class="v2co-lead strong">' + esc(U.U(need, ['شخص واحد يحتاج', 'شخصان يحتاجان', 'أشخاص يحتاجون', 'شخصًا يحتاجون']) + ' استردادًا يدويًا') + '</p>'
      + '<ul class="v2co-refunds">' + rows.map(function (r) {
        var who = r.email ? personLink(r.name || r.email, r.email) : esc(r.name || 'صاحب الدفع');
        var amt = r.no_payment_found ? '<span class="v2co-mute">لم نجد دفعة</span>' : (r.amount != null && r.currency ? '<b>' + esc(U.moneyText(r.amount, r.currency)) + '</b>' : '<span class="v2co-mute">المبلغ: ' + NA + '</span>');
        return '<li><div>' + who + (r.phone ? ' <span class="v2co-ph" dir="ltr">' + esc(r.phone) + '</span>' : '') + '</div><div>' + amt + '</div></li>';
      }).join('') + '</ul><div class="v2co-macts"><button type="button" class="v2co-btn1" id="co_done">تمّ</button></div>';
  }
  function openLiveDecision(slug, action) {
    var title = liveTitle(slug);
    var path = '/v2/courses/live/' + encodeURIComponent(slug) + '/decide';
    if (action === 'confirm') {
      flow({ title: 'ثبّت الدورة', form: '<p class="v2co-lead">تثبيت «' + esc(title) + '»؟</p>' + listHtml(['يُدعى كل من حجز ولم يدفع إلى الدفع.']),
        collect: function () { return { ok: true, payload: {} }; }, btnConfirm: 'ثبّت الدورة', busy: 'جارٍ التثبيت…',
        send: function () { return post(path, { action: 'confirm', confirmed: true }); }, onOk: function () { afterLive('ثُبّتت «' + title + '»'); }, onStale: function () { load('schedules', true); } });
    } else if (action === 'extend') {
      flow({ title: 'مدّد المهلة', form: '<p class="v2co-lead">تمديد مهلة الدفع ٤٨ ساعة؟</p>' + listHtml(['يُدعى من لم يدفع مرة أخرى.']),
        collect: function () { return { ok: true, payload: {} }; }, btnConfirm: 'مدّد ٤٨ ساعة', busy: 'جارٍ التمديد…',
        send: function () { return post(path, { action: 'extend', extend_hours: 48, confirmed: true }); }, onOk: function () { afterLive('مُدّدت مهلة «' + title + '» ٤٨ ساعة'); }, onStale: function () { load('schedules', true); } });
    } else {
      flow({ title: 'ألغِ الدورة',
        form: '<p class="v2co-lead">إلغاء «' + esc(title) + '»؟</p>' + listHtml(['يصل إلى كل من حجز أو دفع بريد وتنبيه بالإلغاء.', 'المنصة لا تردّ المال تلقائيًا: من دفع تردّ له يدويًا، وتظهر قائمتهم بعد الإلغاء مباشرة.']),
        collect: function () { return { ok: true, payload: {} }; },
        review: function () { return '<p class="v2co-lead">اكتب عنوان الدورة للتأكيد:</p>' + fld('co_t', 'عنوان الدورة', '<input id="co_t" type="text" autocomplete="off" placeholder="' + esc(title) + '">'); },
        ready: function (s) { var i = q('#co_t', s); return !!i && i.value.trim() === String(title).trim(); },
        btnNext: 'تابع', btnConfirm: 'ألغِ الدورة', danger: true, busy: 'جارٍ الإلغاء…',
        send: function () { return post(path, { action: 'cancel', confirmed: true }); },
        result: function (res) { return refundsHtml(res.refunds); },
        onOk: function () { setNote('أُلغيت «' + title + '»'); load('schedules', true); load('courses', true); var E = ep(); if (E && E.authed) E.reload('opsQueue', null); },
        onStale: function () { load('schedules', true); } });
    }
  }
  function toLocalInput(iso) {
    var t = Date.parse(iso || ''); if (isNaN(t)) return '';
    var d = new Date(t), p = function (n) { return (n < 10 ? '0' : '') + n; };
    return d.getFullYear() + '-' + p(d.getMonth() + 1) + '-' + p(d.getDate()) + 'T' + p(d.getHours()) + ':' + p(d.getMinutes());
  }
  function isoLocal(v) {
    var d = new Date(v); if (isNaN(d.getTime())) return '';
    var p = function (n) { return (n < 10 ? '0' : '') + n; }, off = -d.getTimezoneOffset(), sg = off >= 0 ? '+' : '-', ao = Math.abs(off);
    return d.getFullYear() + '-' + p(d.getMonth() + 1) + '-' + p(d.getDate()) + 'T' + p(d.getHours()) + ':' + p(d.getMinutes()) + ':00' + sg + p(Math.floor(ao / 60)) + ':' + p(ao % 60);
  }
  function offsetText() { var off = -new Date().getTimezoneOffset(), ao = Math.abs(off); return (off >= 0 ? '+' : '−') + ar(Math.floor(ao / 60)) + ':' + (ao % 60 < 10 ? '٠' : '') + ar(ao % 60); }
  function openSchedule(slug) {
    var c = courseBySlug(slug), sch = (rowsOf('schedules', 'schedules') || []).filter(function (x) { return x.slug === slug; })[0] || null;
    var id = (c && c.id) || (sch && sch.id); if (!id) return;
    var title = liveTitle(slug);
    var cur = { start: sch ? toLocalInput(sch.start_date) : '', zoom: sch ? String(sch.zoom_link || '') : '', seats: sch && sch.max_seats != null ? String(sch.max_seats) : '' };
    flow({
      title: 'موعد الدورة الحيّة',
      form: '<p class="v2co-lead">موعد «' + esc(title) + '».</p>'
        + fld('co_st', 'تاريخ البدء ووقته', '<input id="co_st" type="datetime-local" value="' + esc(cur.start) + '">', 'بتوقيت جهازك: ' + offsetText())
        + fld('co_zl', 'رابط اللقاء', '<input id="co_zl" type="url" dir="ltr" autocomplete="off" value="' + esc(cur.zoom) + '" placeholder="https://">')
        + fld('co_sn', 'عدد المقاعد', '<input id="co_sn" type="number" min="0" inputmode="numeric" value="' + esc(cur.seats) + '">')
        + '<label class="v2co-tg"><input type="checkbox" id="co_pin"> ثبّت الموعد للمتعلّمين</label>',
      collect: function (s) {
        var st = q('#co_st', s).value, zl = q('#co_zl', s).value.trim(), sn = q('#co_sn', s).value.trim(), pin = !!q('#co_pin', s).checked;
        var p = { pin: pin, rows: [] };
        if (st && st !== cur.start) { p.start_date = isoLocal(st); p.rows.push(['تاريخ البدء', cur.start ? U.dateText(sch.start_date) + ' · ' + C.liveTimeText(sch.start_date) : 'بلا موعد', U.dateText(p.start_date) + ' · ' + C.liveTimeText(p.start_date)]); }
        if (zl !== cur.zoom && zl) { p.zoom_link = zl; p.rows.push(['رابط اللقاء', cur.zoom ? 'موجود' : 'غير موجود', 'مُحدَّث']); }
        if (sn !== '' && sn !== cur.seats) {
          var n = Number(sn); if (!isFinite(n) || n < 0 || Math.floor(n) !== n) return { ok: false, error: 'عدد المقاعد غير صالح' };
          p.max_seats = n; p.rows.push(['عدد المقاعد', cur.seats ? ar(cur.seats) : 'غير محدد', ar(n)]);
        }
        if (pin) p.rows.push(['تثبيت الموعد للمتعلّمين', 'غير مثبّت', 'مثبّت']);
        if (!p.rows.length) return { ok: false, error: 'لم تغيّر أي شيء' };
        return { ok: true, payload: p };
      },
      review: function (p) {
        return '<p class="v2co-lead">راجع ما سيتغير:</p><table class="v2co-diff"><thead><tr><th>البند</th><th>الآن</th><th>بعد التعديل</th></tr></thead><tbody>'
          + p.rows.map(function (r) { return '<tr><td>' + esc(r[0]) + '</td><td>' + esc(r[1]) + '</td><td><b>' + esc(r[2]) + '</b></td></tr>'; }).join('') + '</tbody></table>';
      },
      btnNext: 'راجع التغيير', btnConfirm: 'أكّد التعديل', busy: 'جارٍ الحفظ…',
      send: function (p) {
        var b = { confirmed: true };
        ['start_date', 'zoom_link', 'max_seats'].forEach(function (k) { if (p[k] != null) b[k] = p[k]; });
        if (p.pin) b.pin_schedule = true;
        return post('/v2/courses/' + encodeURIComponent(id) + '/schedule', b);
      },
      onOk: function () { afterLive('حُفظ موعد «' + title + '»'); },
      onStale: function () { load('schedules', true); }
    });
  }
  var RES_STATUS = { reserved: 'حجز', invited_to_pay: 'دُعي للدفع', paid: 'دفع', released: 'أُلغي', waitlisted: 'في الانتظار' };
  function openReservations(slug, onlyPaid) {
    var title = liveTitle(slug);
    var s = openSheet(onlyPaid ? 'من دفع: ' + title : 'من حجز: ' + title, '<p class="v2co-mute">…جارٍ جلب القائمة</p>');
    if (!s) return;
    ep().api('/platform-courses/' + encodeURIComponent(slug) + '/reservations?status=all').then(function (r) {
      if (!document.body.contains(s)) return;
      var rows = (r && Array.isArray(r.reservations)) ? r.reservations : null;
      var box = q('.v2co-m', s);
      if (!rows) { box.innerHTML = '<p class="v2co-mute">قائمة الحجوزات: ' + NA + '</p>'; return; }
      if (onlyPaid) rows = rows.filter(function (x) { return x.status === 'paid'; });
      box.innerHTML = (rows.length ? '<ul class="v2co-refunds">' + rows.map(function (x) {
        var who = x.user_email ? personLink(x.user_name || x.user_email, String(x.user_email).toLowerCase()) : esc(x.user_name || 'صاحب الحجز');
        return '<li><div>' + who + '</div><div>' + chip(RES_STATUS[x.status] || 'حجز', x.status === 'paid' ? 'green' : 'grey') + ' <span class="v2co-mute">' + esc(x.created_at ? U.dateText(x.created_at) : '') + '</span></div></li>';
      }).join('') + '</ul>' : '<p class="v2co-mute">' + (onlyPaid ? 'لا أحد دفع' : 'لا حجوزات بعد') + '</p>')
        + '<div class="v2co-macts"><button type="button" class="v2co-btn2" id="co_x">إغلاق</button></div>';
      q('#co_x', s).onclick = closeSheet;
    }).catch(function () {
      if (!document.body.contains(s)) return;
      q('.v2co-m', s).innerHTML = '<p class="v2co-mute">قائمة الحجوزات: ' + NA + '</p><div class="v2co-macts"><button type="button" class="v2co-btn2" id="co_x">إغلاق</button></div>';
      q('#co_x', s).onclick = closeSheet;
    });
  }

  // ------------------------------------------------------------------ الأوراق: الطلب وعروض الأسعار
  function progById(id) { var d = S.demand; if (!d || !d.programs) return null; for (var i = 0; i < d.programs.length; i++) if (d.programs[i].id === id) return d.programs[i]; return null; }
  function afterProg(text) { setNote(text); load('programs', true); load('progStats', true); redraw(); }
  function openProgAccept(id) {
    var p = progById(id); if (!p) return;
    flow({ title: 'اقبل الطلب', form: '<p class="v2co-lead">قبول طلب «' + esc(p.title) + '»؟ يصل إلى صاحب الطلب رابط الدخول إلى البرنامج.</p>',
      collect: function () { return { ok: true, payload: {} }; }, btnConfirm: 'اقبل الطلب', busy: 'جارٍ القبول…',
      send: function () { return decideP({ apiKind: 'program', apiId: id }, 'approve', ''); },
      onOk: function () { afterProg('قُبل طلب «' + p.title + '»'); }, onStale: function () { load('programs', true); } });
  }
  function openProgReject(id) {
    var p = progById(id); if (!p) return;
    flow({ title: 'ارفض الطلب', form: '<p class="v2co-lead">رفض طلب «' + esc(p.title) + '»؟</p>' + fld('co_why', 'سبب الرفض', '<textarea id="co_why" rows="3" maxlength="600"></textarea>', 'يقرؤه صاحب الطلب كما تكتبه'),
      ready: function (s) { return !!q('#co_why', s).value.trim(); },
      collect: function (s) { var v = q('#co_why', s).value.trim(); return v ? { ok: true, payload: { why: v } } : { ok: false, error: 'اكتب سبب الرفض، فهو يصل إلى صاحب الطلب' }; },
      btnConfirm: 'ارفض الطلب', danger: true, busy: 'جارٍ الرفض…',
      send: function (pl) { return decideP({ apiKind: 'program', apiId: id }, 'reject', pl.why); },
      onOk: function () { afterProg('رُفض طلب «' + p.title + '»'); }, onStale: function () { load('programs', true); } });
  }
  function offerById(id) { var l = S.offerRows || []; for (var i = 0; i < l.length; i++) if (l[i].id === id) return l[i]; return null; }
  function afterOffer(text) { setNote(text); load('offers', true); var E = ep(); if (E && E.authed) E.reload('opsQueue', null); redraw(); }
  function willAgree(o, amount) {
    var floor = o.floor, agreed = floor != null ? Math.max(amount, floor) : amount;
    var items = ['يصبح المبلغ المتفق عليه ' + U.moneyText(agreed, o.currency) + '، ويستطيع صاحب العرض الشراء به.'];
    if (floor != null && amount < floor) items.push('العرض أقل من الحد الأدنى، فيُعتمد بالحد الأدنى لا بالمبلغ المعروض.');
    return '<p class="v2co-lead">ما سيحدث:</p>' + listHtml(items.map(esc));
  }
  function openOfferAccept(id) {
    var o = offerById(id); if (!o || o.offered == null) return;
    flow({ title: 'اقبل العرض', form: '<p class="v2co-lead">قبول عرض ' + esc(o.buyer) + ' على «' + esc(o.course) + '» بمبلغ ' + esc(U.moneyText(o.offered, o.currency)) + '؟</p>',
      collect: function () { return { ok: true, payload: {} }; }, review: function () { return willAgree(o, o.offered); },
      btnNext: 'تابع', btnConfirm: 'أكّد قبول العرض', busy: 'جارٍ الاعتماد…',
      send: function () { return post('/v2/courses/offers/' + encodeURIComponent(id) + '/decide', { confirmed: true, decision: 'approve' }); },
      onOk: function () { afterOffer('قُبل عرض ' + o.buyer + ' على «' + o.course + '»'); }, onStale: function () { load('offers', true); } });
  }
  function openOfferCounter(id) {
    var o = offerById(id); if (!o) return;
    flow({ title: 'اعرض سعرًا آخر',
      form: '<p class="v2co-lead">اعرض على ' + esc(o.buyer) + ' سعرًا آخر لدورة «' + esc(o.course) + '».</p>'
        + fld('co_am', 'المبلغ (' + U.curLong(o.currency) + ')', '<input id="co_am" type="text" inputmode="decimal" dir="ltr" autocomplete="off" placeholder="' + esc(o.floor != null ? String(o.floor) : '') + '">',
          o.floor != null ? 'لا يقل المبلغ عن ' + U.moneyText(o.floor, o.currency) : ''),
      collect: function (s) {
        var n = U.parseAmount(q('#co_am', s).value);
        if (n == null || isNaN(n) || n <= 0) return { ok: false, error: 'اكتب المبلغ' };
        if (o.floor != null && n < o.floor) return { ok: false, error: 'لا يقل المبلغ عن ' + U.moneyText(o.floor, o.currency) };
        return { ok: true, payload: { amount: n } };
      },
      review: function (p) { return willAgree(o, p.amount); },
      btnNext: 'راجع العرض', btnConfirm: 'أكّد العرض', busy: 'جارٍ الإرسال…',
      send: function (p) { return post('/v2/courses/offers/' + encodeURIComponent(id) + '/decide', { confirmed: true, decision: 'counter', amount: p.amount }); },
      onOk: function () { afterOffer('أُرسل العرض الجديد إلى ' + o.buyer); }, onStale: function () { load('offers', true); } });
  }
  function openOfferReject(id) {
    var o = offerById(id); if (!o) return;
    flow({ title: 'ارفض العرض', form: '<p class="v2co-lead">رفض عرض ' + esc(o.buyer) + ' على «' + esc(o.course) + '»؟</p>',
      collect: function () { return { ok: true, payload: {} }; }, btnConfirm: 'ارفض العرض', danger: true, busy: 'جارٍ الرفض…',
      send: function () { return post('/v2/courses/offers/' + encodeURIComponent(id) + '/decide', { confirmed: true, decision: 'reject' }); },
      onOk: function () { afterOffer('رُفض عرض ' + o.buyer); }, onStale: function () { load('offers', true); } });
  }

  // ------------------------------------------------------------------ «أنشئ دورة» (مسودة مخفية بلا سعر)
  function openCreate(prefillTitle, done) {   // done: يستدعيه بعد النجاح بدل الانتقال لصفحة الدورة (يستعمله قسم السوق)
    var experts = C.trainerRows(rowsOf('experts', 'experts'), null, { now: now() }) || [];
    var opts = '<option value="">البروفيسور</option>' + experts.filter(function (r) { return r.email; }).map(function (r) { return '<option value="' + esc(r.email) + '" data-name="' + esc(r.name) + '">' + esc(r.name) + '</option>'; }).join('');
    flow({
      title: 'أنشئ دورة',
      form: '<p class="v2co-lead">تُنشأ الدورة مسودة لا يراها الناس. السعر يُحدَّد لاحقًا من «الفلوس».</p>'
        + fld('co_ti', 'عنوان الدورة', '<input id="co_ti" type="text" maxlength="160" autocomplete="off" value="' + esc(prefillTitle || '') + '">')
        + fld('co_ow', 'صاحب الدورة', '<select id="co_ow">' + opts + '</select>', srcState('experts') === 'error' ? 'قائمة المدرّبين: ' + NA : '')
        + fld('co_ty', 'النوع', '<select id="co_ty"><option value="recorded_paid">مسجّلة مدفوعة</option><option value="recorded_free">مسجّلة مجانية</option></select>'),
      wire: function (s) { setTimeout(function () { try { q('#co_ti', s).focus(); } catch (e) {} }, 30); },
      collect: function (s) {
        var title = q('#co_ti', s).value.trim();
        if (!title) return { ok: false, error: 'اكتب عنوان الدورة' };
        if (title.length > 160) return { ok: false, error: 'العنوان طويل: الحد ١٦٠ حرفًا' };
        var sel = q('#co_ow', s), op = sel.options[sel.selectedIndex];
        return { ok: true, payload: { title: title, type: q('#co_ty', s).value, email: sel.value, name: sel.value ? (op.getAttribute('data-name') || '') : 'البروفيسور' } };
      },
      review: function (p) {
        var items = ['تُنشأ الدورة مسودة على المنصة باسم ' + (p.email ? p.name : 'البروفيسور') + '، ولا يراها الناس.', 'تضيف دروسها من «كل السجلات»، ثم تنشرها من صفحة الدورة.'];
        if (p.type === 'recorded_paid') items.push('تحدّد سعرها من «الفلوس › الأسعار».');
        return '<p class="v2co-lead">ما سيحدث:</p>' + listHtml(items.map(esc));
      },
      btnNext: 'راجع قبل الإنشاء', btnConfirm: 'أنشئ المسودة', busy: 'جارٍ الإنشاء…',
      send: function (p) {
        var b = { confirmed: true, title: p.title, type: p.type };
        if (p.email) { b.instructor_email = p.email; b.trainer_name = p.name; } else b.platform_owned = true;
        return post('/v2/courses/create', b);
      },
      onOk: function (res, p) {
        load('courses', true);
        if (typeof done === 'function') { done(res, p); return; }
        setNote('أُنشئت الدورة مسودة.' + (p.type === 'recorded_paid' ? ' حدّد سعرها من «الفلوس › الأسعار».' : ''), res && res.platform_course_id ? 'course:' + res.platform_course_id : undefined);
        if (res && res.platform_course_id) goPage(res.platform_course_id); else redraw();
      }
    });
  }

  // ------------------------------------------------------------------ الأحداث
  function reloadAll() {
    Object.keys(SRC).forEach(function (k) { var st = srcState(k); if (st === 'error' || (st === 'closed' && !OPTIONAL[k] && k.indexOf(':') < 0)) load(k, true); });
    var E = ep(); if (E && E.authed) { if (epState('opsQueue') === 'error') E.reload('opsQueue', null); if (epState('analysis') === 'error') E.reload('analysis', null); }
  }
  function editLessons(id) {
    var c = courseById(id); if (!c) return;
    function pick() {
      var list = typeof window.csPlatformCourses === 'function' ? window.csPlatformCourses() : [];
      var idx = -1; for (var i = 0; i < list.length; i++) if (list[i] && String(list[i].id) === String(id)) idx = i;
      var h = document.getElementById('v2coLegacyHost');
      if (idx < 0 || !h) return;
      host().setLegacy('selected', 'P' + idx);
      window.viewCourses(h);
      if (typeof window.drawCourse === 'function') window.drawCourse();
    }
    if (typeof window.v2OpenSection === 'function') window.v2OpenSection('courses', 'all', { st: { courseTab: 'platform' } }); else goSection('courses', 'all');
    var E = ep();
    if (E && E.authed) E.ensure('platform_courses', pick);
    pick();
  }
  var ACT = {
    retry: function () { reloadAll(); },
    create: function () { if (window.V2CE && window.V2CE.openCreate) { load('experts'); window.V2CE.openCreate({}); } else openCreate(''); },
    'edit-course': function (el) { openEditor(el.getAttribute('data-id')); },
    mk: function (el) { var g = S.demand && S.demand.chat && S.demand.chat.groups[+el.getAttribute('data-i')]; openCreate(g ? g.title : ''); },
    open: function (el) { goPage(el.getAttribute('data-id')); },
    all: function () { S.list = true; S.filter = 'all'; redraw(); },
    board: function () { S.list = false; redraw(); },
    'all-courses': function () { S.list = true; S.filter = 'all'; if (S.screen === 'board') redraw(); else { S.keepList = true; goSection('courses', 'courses'); } },
    col: function (el) { S.col = el.getAttribute('data-col'); try { localStorage.setItem('v2co_col', S.col); } catch (e) {} redraw(); },
    trseg: function (el) { S.tr = el.getAttribute('data-seg'); try { localStorage.setItem('v2co_tr', S.tr); } catch (e) {} redraw(); },
    filter: function (el) { S.filter = el.getAttribute('data-f'); redraw(); },
    goto: function (el) { goSection(el.getAttribute('data-s'), el.getAttribute('data-t')); },
    approve: function (el) { openApprove(el.getAttribute('data-id'), el.getAttribute('data-unknown') === '1'); },
    'return': function (el) { openReturn(el.getAttribute('data-id')); },
    publishNow: function (el) { openVisibility(el.getAttribute('data-id'), 'publishNow'); },
    show: function (el) { openVisibility(el.getAttribute('data-id'), 'show'); },
    hide: function (el) { openVisibility(el.getAttribute('data-id'), 'hide'); },
    bid: function (el, e) { e.preventDefault(); openBid(el.getAttribute('data-id'), !!el.checked); },
    archive: function (el) { openArchive(el.getAttribute('data-id'), false); },
    'delete': function (el) { openArchive(el.getAttribute('data-id'), true); },
    refetch: function (el) { load('checklist:' + el.getAttribute('data-id'), true); redraw(); },
    retrydetail: function (el) { load('detail:' + el.getAttribute('data-id'), true); redraw(); },
    'edit-lessons': function (el) { editLessons(el.getAttribute('data-id')); },
    appopen: function (el) { openAppDetail(el.getAttribute('data-id')); },
    appaccept: function (el) { openAppAccept(el.getAttribute('data-id')); },
    appreject: function (el) { openAppReject(el.getAttribute('data-id')); },
    tstop: function (el) { var d = el.closest('details'); if (d) d.removeAttribute('open'); openStopTrainer(el.getAttribute('data-email')); },
    'live-open': function (el) { var c = courseBySlug(el.getAttribute('data-slug')); if (c) goPage(c.id); },
    'live-confirm': function (el) { openLiveDecision(el.getAttribute('data-slug'), 'confirm'); },
    'live-extend': function (el) { openLiveDecision(el.getAttribute('data-slug'), 'extend'); },
    'live-cancel': function (el) { openLiveDecision(el.getAttribute('data-slug'), 'cancel'); },
    'live-zoom': function (el) { openSchedule(el.getAttribute('data-slug')); },
    'live-edit': function (el) { openSchedule(el.getAttribute('data-slug')); },
    'live-who': function (el) { openReservations(el.getAttribute('data-slug'), false); },
    'live-paid': function (el) { openReservations(el.getAttribute('data-slug'), true); },
    'prog-accept': function (el) { openProgAccept(el.getAttribute('data-id')); },
    'prog-reject': function (el) { openProgReject(el.getAttribute('data-id')); },
    'offer-accept': function (el) { openOfferAccept(el.getAttribute('data-id')); },
    'offer-counter': function (el) { openOfferCounter(el.getAttribute('data-id')); },
    'offer-reject': function (el) { openOfferReject(el.getAttribute('data-id')); }
  };
  function onClick(e) {
    var t = e.target;
    if (!t || !t.closest) return;
    var root = t.closest('.v2co');
    if (!root) return;
    var p = t.closest('a[data-person]');
    if (p && root.contains(p)) {
      if (e.metaKey || e.ctrlKey || e.shiftKey || e.button === 1) return;
      e.preventDefault(); if (host().openPerson) host().openPerson(p.getAttribute('data-person')); return;
    }
    var el = t.closest('[data-a]');
    if (!el || !root.contains(el)) return;
    var h = ACT[el.getAttribute('data-a')];
    if (h) { if (el.tagName !== 'INPUT') e.preventDefault(); h(el, e); }
  }
  function onInput(e) {
    var t = e.target;
    if (!t || t.id !== 'co_q') return;
    S.search = t.value;
    var b = C.board(rowsOf('courses', 'courses'), { now: now() });
    var body = document.getElementById('co_lbody');
    if (body && !b.na) body.innerHTML = listRowsHtml(listItems(b));
  }
  // الصور التي تفشل ⇒ الغلاف الورقي بدل صورة مكسورة
  function onImgError(e) {
    var t = e.target;
    if (!t || t.tagName !== 'IMG' || !t.classList.contains('v2co-img')) return;
    var box = t.parentNode; if (box) { box.classList.remove('has'); box.classList.add('fail'); }
    t.remove();
  }

  // ------------------------------------------------------------------ نقطة الدخول
  function screenNow(mod) {
    var snap = window.v2Snapshot ? window.v2Snapshot() : {};
    var st = host().state ? host().state() : {};
    if (mod === 'team') return snap.teamTab === 'trainers' ? 'trainers' : '';
    if (mod !== 'courses') return '';
    if (st.section === 'courses' && st.tab === 'all') return 'all';
    var t = snap.courseTab;
    if (t === 'schedules') return 'live';
    if (t === 'demand' || t === 'programs') return 'demand';
    if (t === 'offers') return 'offers';
    if (t === 'page') return st.course ? 'course' : 'board';
    return 'board';
  }
  var NEEDS = {
    board: function () { load('courses'); load('apps'); load('experts'); load('schedules'); load('courses2'); },
    trainers: function () { load('courses'); load('apps'); load('experts'); },
    live: function () { load('courses'); load('schedules'); epEnsure(['opsQueue']); },
    demand: function () { load('progStats'); load('programs'); epEnsure(['analysis']); },
    offers: function () { load('offers'); },
    course: function () { load('courses'); load('courses2'); },
    all: function () {}
  };
  var DRAW = { board: drawBoard, trainers: drawTrainers, live: drawLive, demand: drawDemand, offers: drawOffers, course: drawCourse };
  function isFocusInside() { var a = document.activeElement; return !!(a && S.view && S.view.contains(a) && /^(INPUT|TEXTAREA|SELECT)$/.test(a.tagName)); }
  function redraw() {
    var v = S.view;
    if (!v || !document.body.contains(v) || v.id === 'v2coLegacyHost') return;
    var mod = host().current ? host().current() : '';
    var scr = screenNow(mod);
    if (!scr || scr === 'all') return;
    if (document.getElementById('epModal')) return;           // لا نعيد الرسم تحت ورقة مفتوحة (ما يُكتب فيها يضيع)
    if (S.editing && window.V2CE && scr === 'course') return; // المحرّر يرسم نفسه (مسودّاته غير المحفوظة لا تُمسح بإعادة رسم الصفحة)
    S.screen = scr;
    if (NEEDS[scr]) NEEDS[scr]();
    DRAW[scr](v);
    S.sig = signature();
  }
  function watchLegacy() {
    if (S.obs) return;
    var view = document.getElementById('view');
    if (!view || !window.MutationObserver) return;
    S.obs = new MutationObserver(function () { document.documentElement.classList.toggle('v2co-legacy-modal', !!document.querySelector('#view .v2co-legacy')); });
    S.obs.observe(view, { childList: true });
    // نافذة مفتوحة من «كل السجلات» (المنهج والمحاضرات…): أرقامها بالعربية كذلك
    S.mObs = new MutationObserver(function (list) {
      if (!document.documentElement.classList.contains('v2co-legacy-modal')) return;
      list.forEach(function (m) { Array.prototype.forEach.call(m.addedNodes, function (nd) { if (nd.id === 'epModal') watchDigits(nd, 'mdObs'); }); });
    });
    S.mObs.observe(document.body, { childList: true });
  }
  function openEditor(id) {
    if (!window.V2CE || !id) return;
    S.editing = id; window.V2CE.start(id);
    if (S.view) { S.screen = 'course'; drawCourse(S.view); }
  }
  // أدوات يستعملها course_editor.js (الأوراق · النماذج · قائمة المدرّبين · الرجوع) — ⛔ لا منطق عمل، ولا شبكة.
  CO.kit = {
    flow: flow, listHtml: listHtml, fld: fld, BRAIN: BRAIN, NA: NA,
    trainerOptions: function () { var rows = C.trainerRows(rowsOf('experts', 'experts'), null, { now: now() }) || []; return rows.filter(function (r) { return r.email; }).map(function (r) { return { email: r.email, name: r.name }; }); },
    reloadList: function () { load('courses', true); load('courses2', true); },
    closeEditor: function () { S.editing = ''; load('courses', true); load('courses2', true); redraw(); },
    openEditorFor: function (id, note, tab) { S.editing = id; if (window.V2CE) window.V2CE.start(id, note, tab); goPage(id); }
  };
  CO.take = function (mod, v) {
    if (!window.V2_ON || !(window.V2SHELL && V2SHELL.on)) return false;
    if (v && v.id === 'v2coLegacyHost') return false;
    var scr = screenNow(mod);
    if (!scr) return false;
    // فتح تبويب «الدورات» من الترويسة يرجع للّوحة دايمًا؛ وضع «كل الدورات» يبقى فقط لما نطلبه نحن (من صفحة الدورة أو بعد أرشفة/حذف).
    var keep = S.keepList; S.keepList = false;
    if (!keep && scr === 'board') S.list = false;
    S.view = v; S.screen = scr;
    if (S.editing && !(scr === 'course' && host().state && host().state().course === S.editing)) S.editing = '';
    if (!v.__v2co) {
      v.__v2co = true;
      v.addEventListener('click', onClick); v.addEventListener('input', onInput); v.addEventListener('error', onImgError, true);
    }
    var ap = q('.app'); if (ap) ap.classList.add('v2-bare');
    watchLegacy();
    if (scr === 'all') {
      document.documentElement.classList.add('v2co-legacy-modal');
      drawLegacy(v);
      return true;
    }
    document.documentElement.classList.remove('v2co-legacy-modal');
    if (NEEDS[scr]) NEEDS[scr]();
    DRAW[scr](v);
    S.sig = signature();
    if (!S.poll) {
      S.poll = setInterval(function () {
        var m = host().current ? host().current() : '';
        if (!screenNow(m) || screenNow(m) === 'all') return;
        if (document.getElementById('epModal')) return;
        if (signature() !== S.sig) redraw();
      }, 400);
    }
    if (!S.minute) S.minute = setInterval(function () {
      var m = host().current ? host().current() : '';
      if (screenNow(m) && screenNow(m) !== 'all' && !document.getElementById('epModal') && !isFocusInside()) redraw();
    }, 60000);
    return true;
  };
  // سطر ترويسة القسم من القائمة نفسها التي ترسمها اللوحة (الدورات في المراجعة وطلبات المدرّبين).
  CO.head = function () {
    var st = srcState('courses');
    if (st === 'error' || st === 'closed') return NA;
    if (st !== 'ready') return null;
    var b = C.board(rowsOf('courses', 'courses'), { now: now() });
    if (b.na || !b.counts) return NA;
    var p = [];
    if (b.counts.review) p.push(U.U(b.counts.review, ['دورة واحدة تنتظر قرارك', 'دورتان تنتظران قرارك', 'دورات تنتظر قرارك', 'دورة تنتظر قرارك']));
    var apps = C.appTickets(rowsOf('apps', 'applications'), { now: now() });
    if (apps && apps.length) p.push(U.U(apps.length, ['طلب مدرّب جديد', 'طلبان من مدرّبين', 'طلبات من مدرّبين', 'طلبًا من مدرّبين']));
    return p.length ? p.join(' · ') : 'لا شيء ينتظر قرارك';
  };
  CO.openCourse = function (id) { goPage(id); };
  // «أنشئ دورة» من خارج قسم الدورات (السوق: دورة من طلب): نفس الورقة الجديدة؛ opts.done(res) يُستدعى بعد النجاح بدل الانتقال لصفحة الدورة.
  CO.create = function (title, opts) { load('experts'); openCreate(String(title || ''), opts && opts.done); };
  CO._state = S; CO._src = SRC;
  CO._tick = function (t) { S.nowOverride = t || 0; redraw(); };
  window.V2SEC.add({ key: 'courses', take: CO.take, head: CO.head });
})();
