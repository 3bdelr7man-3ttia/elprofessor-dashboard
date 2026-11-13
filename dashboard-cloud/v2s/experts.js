/* ============================================================================
 * v2s/experts.js — «ملفات الخبراء ‹ الخبراء» بالشكل الجديد: الخبراء المعتمدون (بطاقة لكل خبير) للقراية.
 * R24 م٢: ردود دعوة المؤسس (الخبراء المؤسسون) **اتشالت من هنا**: قرارها في «الناس» (بطاقة لكل شخص) ومتابعتها على صفحة الشخص — مفيش نسخة تانية بأزرار.
 * ⛔ لا منطق عمل هنا: التصنيف والتخصصات وسطر العقل من `V2L.v2s.experts` (نقي، في v2-logic.js). ⛔ لا كتابة من هنا خالص.
 * ⛔ لا فلوس هنا. ⛔ المصدر الذي تعذّر ⇒ «غير متاح بعد» لا صفر. ⛔ لا confirm ولا prompt.
 * ⛔ المفتاح مقفول افتراضيًا: لا يرسم شيئًا إلا لو `V2SEC.take('team')` اتنادى والغلاف الجديد شغّال. التبويبان «المدرّبون» و«الفريق الإداري» لهما موضعهما
 *   (الدورات ‹ المدرّبون، والشركة ‹ الإعدادات) فلا يتكرّران هنا.
 * ========================================================================== */
(function () {
  'use strict';
  var L = window.V2L;
  if (!L || !L.v2s || !L.v2s.experts) return;
  var X = L.v2s.experts, U = L.util, NA = X.NA;
  window.V2SEC = window.V2SEC || { _o: [], add: function (o) { this._o.push(o); },
    take: function (mod, v) { if (!window.V2_ON || !(window.V2SHELL && V2SHELL.on)) return false;
      for (var i = 0; i < this._o.length; i++) { if (this._o[i].take(mod, v)) return true; } return false; } };
  var EX = window.V2EX = {};
  var S = { view: null, sig: '', poll: null, minute: null, busy: {}, err: {}, done: {}, nowOverride: 0, ledgerOpen: false };

  function esc(s) { return String(s == null ? '' : s).replace(/[&<>"']/g, function (c) { return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]; }); }
  function host() { return window.V2_HOST || {}; }
  function ep() { return window.EP || null; }
  function now() { return S.nowOverride || Date.now(); }
  function ar(n) { return U.ar(n); }
  function q(sel, root) { return (root || document).querySelector(sel); }
  function qa(sel, root) { return Array.prototype.slice.call((root || document).querySelectorAll(sel)); }
  function img(name) { return 'v2/img/' + name + '.jpg'; }
  var BRAIN = '<img class="v2ex-bav" src="' + img('brain-avatar') + '" alt="">';

  function stateOf(k) { var E = ep(); return (E && E.state && E.state[k]) || 'idle'; }
  function dataOf(k) { var E = ep(); return E && E.data ? E.data[k] : null; }
  function loadAll() { var E = ep(); if (!E || !E.authed) return; ['experts'].forEach(function (k) { E.ensure(k, null); }); }

  // ------------------------------------------------------------------ مصادر
  function expertsList() { return stateOf('experts') === 'ready' && window.EXPERTS ? window.EXPERTS : null; }
  function signature() {
    var xs = window.EXPERTS || [];
    return [stateOf('experts'), xs.length, xs.filter(function (e) { return e.online; }).length].join('|');
  }

  // ------------------------------------------------------------------ رسم
  function avatarLetter(name) { var m = String(name || '').match(/[ء-يٱ-ۓA-Za-z]/); return m ? m[0] : '؟'; }
  function expertHtml(r) {
    var num = function (label, v) { return '<div><dt>' + esc(label) + '</dt><dd>' + esc(v == null ? NA : ar(v)) + '</dd></div>'; };
    var name = r.email ? '<a class="v2ex-person" href="' + esc(L.sectionHash('people', 'person', r.email)) + '" data-person="' + esc(r.email) + '">' + esc(r.name) + '</a>' : esc(r.name);
    return '<article class="v2ex-x' + (r.hidden ? ' hid' : '') + '">'
      + '<span class="v2ex-av" aria-hidden="true">' + esc(avatarLetter(r.name)) + (r.online ? '<i class="v2ex-on" title="متصل الآن"></i>' : '') + '</span>'
      + '<div class="v2ex-id"><h3>' + name + (r.online ? ' <small class="v2ex-onl">متصل الآن</small>' : '') + '</h3>'
      + '<p class="v2ex-specs">' + (r.specs.length ? r.specs.map(function (x) { return '<span class="v2ex-chip">' + esc(x) + '</span>'; }).join('') : '<span class="v2ex-mute">لم يحدّد تخصصه</span>') + '</p></div>'
      + '<dl class="v2ex-nums"><div><dt>التقييم</dt><dd>' + esc(r.rating) + '</dd></div>' + num('الإحالات', r.referrals) + num('الدورات', r.courses) + num('المتعلّمون', r.learners) + '</dl>'
      + '<div class="v2ex-brain">' + BRAIN + '<p>' + esc(r.brain) + '</p></div>'
      + (r.email ? '<a class="v2ex-btn1 lnk" href="' + esc(L.sectionHash('people', 'person', r.email)) + '" data-person="' + esc(r.email) + '">افتح صفحته</a>' : '')
      + '</article>';
  }
  function expertsSection() {
    var st = stateOf('experts'), list = expertsList(), head = '<h2 class="v2ex-h2">الخبراء المعتمدون';
    if (st === 'error') {
      return '<section class="v2ex-sec">' + head + '</h2><div class="v2ex-empty"><b>الخبراء: ' + NA + '</b><p>تعذّر الوصول إلى هذه البيانات الآن، فلا تعتبر القائمة فارغة.</p>'
        + '<button type="button" class="v2ex-btn2" data-a="retry">أعد المحاولة</button></div></section>';
    }
    if (!list) return '<section class="v2ex-sec">' + head + '</h2><div class="v2ex-empty"><b>…جارٍ تحميل الخبراء</b></div></section>';
    var B = X.expertBoard(list);
    if (!B.rows.length) return '<section class="v2ex-sec">' + head + '<span class="v2ex-n">٠</span></h2><div class="v2ex-empty"><b>لا خبراء بعد</b><p>يظهر الخبير هنا عند اعتماد مدرّب.</p></div></section>';
    return '<section class="v2ex-sec">' + head + '<span class="v2ex-n">' + esc(ar(B.rows.length)) + '</span></h2><div class="v2ex-list">' + B.rows.map(expertHtml).join('') + '</div></section>';
  }
  function draw(v) {
    var list = expertsList(), eb = list ? X.expertBoard(list) : null;
    v.innerHTML = '<div class="v2ex"><p class="v2ex-sum">' + esc(X.summaryLine(eb, null)) + '</p>'
      + '<p class="v2ex-fine">طلبات الخبراء المؤسسين وكل من يطلب الانضمام في «الناس» — بطاقة واحدة لكل شخص، وبقية خطواتهم على صفحته.</p>' + expertsSection() + '</div>';
  }
  function redraw() {
    var v = S.view;
    if (!v || !document.body.contains(v) || document.getElementById('epModal')) return;
    var y = window.pageYOffset;
    draw(v);
    S.sig = signature();
    if (window.pageYOffset !== y) window.scrollTo(0, y);
  }

  function onClick(e) {
    var b = e.target.closest && e.target.closest('[data-a]');
    if (!b || !S.view.contains(b)) return;
    if (b.getAttribute('data-a') === 'retry') { var E = ep(); if (E) E.reload('experts', null); }
  }

  // ------------------------------------------------------------------ الدخول من الشاشة القديمة
  EX.take = function (mod, v) {
    if (!window.V2_ON || !(window.V2SHELL && V2SHELL.on)) return false;
    if (mod !== 'team') return false;
    var snap = window.v2Snapshot ? window.v2Snapshot() : {};
    if (snap.teamTab === 'trainers') return false;                           // «المدرّبون» تملكها الدورات
    if (snap.teamTab && snap.teamTab !== 'experts' && host().setLegacy) host().setLegacy('teamTab', 'experts');   // «الفريق الإداري» القديم: في الشركة
    S.view = v;
    if (!v.__v2ex) { v.__v2ex = true; v.addEventListener('click', onClick); }
    var ap = q('.app'); if (ap) ap.classList.add('v2-bare');
    loadAll();
    draw(v);
    S.sig = signature();
    if (!S.poll) S.poll = setInterval(function () {
      var m = host().current ? host().current() : '';
      if (m !== 'team' || !S.view || !document.body.contains(S.view)) return;
      if (signature() !== S.sig) redraw();
    }, 400);
    if (!S.minute) S.minute = setInterval(function () { var m = host().current ? host().current() : ''; if (m === 'team' && !document.getElementById('epModal')) redraw(); }, 60000);
    return true;
  };
  EX._state = S; EX._tick = function (t) { S.nowOverride = t || 0; redraw(); };
  window.V2SEC.add({ key: 'experts', take: EX.take });
})();
