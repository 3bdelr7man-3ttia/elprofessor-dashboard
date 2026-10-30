/* ============================================================================
 * v2s/experts.js — «ملفات الخبراء ‹ الخبراء» بالشكل الجديد: ردود دعوة المؤسس (تذاكر) ثم الخبراء المعتمدون (بطاقة لكل خبير).
 * ⛔ لا منطق عمل هنا: التصنيف والتخصصات وسطر العقل من `V2L.v2s.experts` (نقي، في v2-logic.js).
 * ⛔ الكتابة الوحيدة: تغيير حالة رد على دعوة المؤسس بنفس مسار الداشبورد القديم (`EP.setFoundingLeadStatus`). «صار مدرّبًا» و«ليس مناسبًا» نهاية فلهما ورقة تأكيد.
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
  function loadAll() { var E = ep(); if (!E || !E.authed) return; ['experts', 'foundingLeads'].forEach(function (k) { E.ensure(k, null); }); }

  // ------------------------------------------------------------------ مصادر
  function expertsList() { return stateOf('experts') === 'ready' && window.EXPERTS ? window.EXPERTS : null; }
  function leadsInfo() {
    var st = stateOf('foundingLeads'), d = dataOf('foundingLeads');
    if (st === 'ready' && d) return { state: d.missing ? 'closed' : 'ready', rows: d.missing ? null : (d.rows || []), count: d.count };
    return { state: st === 'error' ? 'error' : 'loading', rows: null };
  }
  function signature() {
    var li = leadsInfo(), xs = window.EXPERTS || [];
    return [stateOf('experts'), stateOf('foundingLeads'), xs.length, xs.filter(function (e) { return e.online; }).length, li.rows ? li.rows.map(function (r) { return r.id + r.status; }).join(',') : li.state,
            Object.keys(S.busy).join(','), Object.keys(S.err).join(',')].join('|');
  }

  // ------------------------------------------------------------------ رسم
  function avatarLetter(name) { var m = String(name || '').match(/[ء-يٱ-ۓA-Za-z]/); return m ? m[0] : '؟'; }
  function tel(t) {
    return t.phone ? '<a class="v2ex-tel" dir="ltr" href="tel:' + esc(t.phone) + '">' + esc(t.phoneText) + '</a>' : '<span class="v2ex-mute">بلا رقم</span>';
  }
  function leadHtml(t) {
    var id = t.id, busy = !!S.busy[id], err = S.err[id] || '', done = S.done[id] || '';
    var meta = [t.specs.length ? t.specs.join('، ') : 'لم يحدّد تخصصه', t.country, t.years ? 'خبرة ' + t.years : ''].filter(Boolean).join(' · ');
    var acts = '';
    if (done) acts = '<p class="v2ex-ok" role="status">' + esc(done) + '</p>';
    else if (t.primary) {
      acts = '<button type="button" class="v2ex-btn1" data-a="lead" data-id="' + esc(id) + '" data-st="' + esc(t.primary.status) + '"' + (busy ? ' disabled' : '') + '>' + esc(busy ? 'جارٍ التسجيل…' : t.primary.label) + '</button>'
        + '<button type="button" class="v2ex-btn2" data-a="lead" data-id="' + esc(id) + '" data-st="' + esc(t.secondary.status) + '"' + (busy ? ' disabled' : '') + '>' + esc(t.secondary.label) + '</button>';
    }
    return '<article class="v2ex-t tone-' + esc(t.tone) + '" data-id="' + esc(id) + '">'
      + '<div class="v2ex-strip"><span class="v2ex-type">' + esc(t.statusLabel) + '</span>' + (t.since ? '<time class="v2ex-time">' + esc(t.since) + '</time>' : '') + '</div>'
      + '<div class="v2ex-body"><h3>' + esc(t.name) + '</h3>'
      + '<p class="v2ex-meta">' + esc(meta) + '</p>'
      + '<p class="v2ex-contact">' + tel(t) + (t.email ? '<span class="v2ex-mail" dir="ltr">' + esc(t.email) + '</span>' : '') + '</p>'
      + (t.brain ? '<div class="v2ex-brain">' + BRAIN + '<p>' + esc(t.brain) + '</p></div>' : '')
      + (err ? '<div class="v2ex-err" role="alert">' + esc(err) + '</div>' : '')
      + (acts ? '<div class="v2ex-acts">' + acts + '</div>' : '') + '</div></article>';
  }
  function leadsSection() {
    var li = leadsInfo(), head = '<h2 class="v2ex-h2">ردود دعوة المؤسس';
    if (li.state === 'error') {
      return '<section class="v2ex-sec">' + head + '</h2><div class="v2ex-empty"><b>ردود دعوة المؤسس: ' + NA + '</b><p>تعذّر الوصول إلى هذه البيانات الآن، فلا تعتبر القائمة فارغة.</p>'
        + '<button type="button" class="v2ex-btn2" data-a="retry">أعد المحاولة</button></div></section>';
    }
    if (li.state === 'closed') {
      return '<section class="v2ex-sec">' + head + '</h2><div class="v2ex-empty"><b>ردود دعوة المؤسس: ' + NA + '</b><p>لم يفتح هذا المسار في المنصة بعد، وستظهر الردود هنا فور فتحه.</p></div></section>';
    }
    if (li.state !== 'ready') return '<section class="v2ex-sec">' + head + '</h2><div class="v2ex-empty"><b>…جارٍ تحميل ردود دعوة المؤسس</b></div></section>';
    var B = X.leadBoard(li.rows, now());
    var trunc = li.count != null && li.count > li.rows.length ? '<p class="v2ex-warn" role="status">معروض ' + esc(ar(li.rows.length)) + ' من ' + esc(ar(li.count)) + ' — القائمة ناقصة.</p>' : '';
    if (!B.open.length) {
      return '<section class="v2ex-sec">' + head + '<span class="v2ex-n">٠</span></h2>' + trunc + '<div class="v2ex-empty"><b>لا ردود تنتظرك</b><p>يظهر هنا كل خبير يترك بياناته في صفحة المؤسسين.</p></div>' + ledger(B) + '</section>';
    }
    return '<section class="v2ex-sec">' + head + '<span class="v2ex-n">' + esc(ar(B.open.length)) + '</span></h2>' + trunc
      + '<div class="v2ex-grid">' + B.open.map(leadHtml).join('') + '</div>' + ledger(B) + '</section>';
  }
  function ledger(B) {
    if (!B.converted && !B.rejected) return '';
    var p = [];
    if (B.converted) p.push(ar(B.converted) + ' صاروا مدرّبين');
    if (B.rejected) p.push(ar(B.rejected) + ' ليسوا مناسبين');
    return '<p class="v2ex-fine">تمت معالجتهم: ' + esc(p.join(' · ')) + '</p>';
  }
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
    var list = expertsList(), eb = list ? X.expertBoard(list) : null, li = leadsInfo(), lb = li.rows ? X.leadBoard(li.rows, now()) : null;
    v.innerHTML = '<div class="v2ex"><p class="v2ex-sum">' + esc(X.summaryLine(eb, lb)) + '</p>' + leadsSection() + expertsSection() + '</div>';
  }
  function redraw() {
    var v = S.view;
    if (!v || !document.body.contains(v) || document.getElementById('epModal')) return;
    var y = window.pageYOffset;
    draw(v);
    S.sig = signature();
    if (window.pageYOffset !== y) window.scrollTo(0, y);
  }

  // ------------------------------------------------------------------ تغيير حالة رد على دعوة
  function findTicket(id) {
    var li = leadsInfo(), B = li.rows ? X.leadBoard(li.rows, now()) : null, hit = null;
    if (B) B.open.forEach(function (t) { if (t.id === id) hit = t; });
    return hit;
  }
  function apply(t, st) {
    var E = ep(); if (!E || !E.setFoundingLeadStatus || S.busy[t.id]) return;
    S.busy[t.id] = true; S.err[t.id] = ''; redraw();
    E.setFoundingLeadStatus(t.row, st, function (ok) {
      delete S.busy[t.id];
      if (ok === false) S.err[t.id] = 'تعذّر تسجيل الحالة. حدّث الصفحة ثم جرّب مرة أخرى.';
      else S.done[t.id] = 'تم تسجيل «' + t.name + '»: ' + (X.LEAD_STATUS[st] || '');
      redraw();
      if (ok !== false) setTimeout(function () { delete S.done[t.id]; redraw(); }, 6000);
    });
  }
  function confirmSheet(t, st) {
    if (typeof window.openModal !== 'function') return;
    var label = X.LEAD_STATUS[st];
    var s = window.openModal(label, '<div class="v2ex-m"><p class="v2ex-lead">تسجيل «' + esc(t.name) + '» بحالة «' + esc(label) + '».</p>'
      + '<p class="v2ex-fine">هذه حالة نهائية: يخرج الطلب من قائمة ما ينتظرك ولا يعود إليها.</p>'
      + '<div class="acts"><button type="button" class="btn btn-primary" id="exGo">سجّل الحالة</button><button type="button" class="btn btn-ghost" id="exNo">رجوع</button></div></div>');
    s.querySelector('#exNo').onclick = window.closeModal;
    s.querySelector('#exGo').onclick = function () { window.closeModal(); apply(t, st); };
  }
  function onClick(e) {
    var b = e.target.closest && e.target.closest('[data-a]');
    if (!b || !S.view.contains(b)) return;
    var a = b.getAttribute('data-a');
    if (a === 'retry') { var E = ep(); if (E) { E.reload('experts', null); E.reload('foundingLeads', null); } return; }
    if (a === 'lead') {
      var t = findTicket(b.getAttribute('data-id')), st = b.getAttribute('data-st');
      if (!t) return;
      if (st === 'rejected' || st === 'converted') confirmSheet(t, st); else apply(t, st);
    }
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
