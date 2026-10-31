/* ============================================================================
 * v2s/content.js — قسم «المحتوى» بالشكل الجديد (الجولة الأخيرة): خط النشر · المقالات · الموضوعات · الأخبار · التعليقات · دليل الاستخدام · الموقع.
 * ⛔ لا منطق عمل هنا: الأعمدة والعدّادات وسطور العقل والزرّ الأساسي من `v2-logic.js` (كتلة `v2s:content`)، والكتابة كلها عبر دوال EP الموجودة بالحرف.
 * ⛔ كل نشر أو إلغاء نشر أو اعتماد أو رفض أو حذف أو استهلاك رصيد الكتابة الآلية يمرّ على ورقة تأكيد (`confirmSheet`) تضع
 *   `window.__v2ctConfirmAt`؛ والاستثناءات المسموحة مكتوبة في القائمة EXEMPT أدناه وليس غيرها.
 * ⛔ المفتاح مقفول ⇒ `index.html` لا يستدعي `render` أبدًا (الموزّع يشترط الغلاف الجديد)، فالملف بلا أثر.
 * ⛔ لا نداء لـ`platformOpinionsAnalysis` (يكتب خلاصة مدفوعة في كل زيارة): الأرقام من `platformOpinionsNumbers` (summarize=false)،
 *   والخلاصة المكتوبة نداء واحد بعد تأكيد صريح.
 * ========================================================================== */
(function () {
  'use strict';
  var L = window.V2L;
  if (!L) return;
  var U = L.util, ar = U.ar;
  var SEC = window.V2SEC = window.V2SEC || {};
  var NA = L.NA;
  var API = {};
  SEC.content = API;

  // ------------------------------------------------------------------ حالة الشاشة
  var S = {
    view: null, sig: '', poll: null, minute: null, active: false,
    col: '', picked: false, expand: {}, cat: 'all', afilter: 'draft', nfilter: 'draft',
    note: null, noteT: null, generating: {}, summary: null, highlight: null, openArticle: null, afterPublish: false,
    items: {}, nowOverride: 0, busy: {}, lastTab: '', bg: {}, lastRefresh: 0
  };
  var KEYS = ['content', 'contentOverview', 'platformArticles', 'platformTopics', 'platformPendingTopics', 'platformTopicSegments', 'platformTopicsAnalysis',
              'platformOpinions', 'platformOpinionsApproved', 'platformNews', 'platformNewsSources', 'platformCreative', 'testimonials', 'testimonialsApproved',
              'platformOpinionsNumbers', 'tutorials', 'opsQueue'];
  var NEED = {
    pipeline: ['content', 'contentOverview', 'platformArticles', 'platformTopics', 'platformPendingTopics', 'platformOpinions', 'platformOpinionsApproved',
               'platformNews', 'platformCreative', 'testimonials', 'testimonialsApproved', 'opsQueue'],
    articles: ['content', 'contentOverview', 'platformArticles'],
    topics: ['platformTopics', 'platformPendingTopics', 'platformTopicSegments', 'platformTopicsAnalysis', 'content'],
    news: ['platformNews', 'platformNewsSources'],
    comments: ['platformOpinions', 'platformOpinionsApproved', 'platformOpinionsNumbers'],
    tutorials: ['tutorials']
  };
  var FAIL_LABEL = { content: 'مقالات الموقع', contentOverview: 'حالة مقالات الموقع', platformArticles: 'مقالات المنصة', platformTopics: 'الموضوعات',
                     platformPendingTopics: 'موضوعات الأعضاء', platformOpinions: 'التعليقات', platformOpinionsApproved: 'التعليقات المعتمدة', platformNews: 'الأخبار',
                     platformCreative: 'أعمال ركن الإبداع', testimonials: 'آراء المتعلّمين', testimonialsApproved: 'الآراء المعتمدة' };
  var SEC_SOURCE = 'https://elprofessor.net/article.html?id=';

  // ------------------------------------------------------------------ أدوات
  function esc(s) { return String(s == null ? '' : s).replace(/[&<>"']/g, function (c) { return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]; }); }
  // رابط قادم من بيانات: يُقبل http/https فقط (وللمسار الداخلي مرّر rel). غيره (javascript: وغيره) ⇒ نص بلا رابط.
  function safeHref(u, rel) {
    var v = String(u == null ? '' : u).trim();
    if (/^https?:\/\//i.test(v)) return v;
    if (rel && /^\/(?!\/)/.test(v)) return v;
    return '';
  }
  function safeLink(u, label, cls) {
    var h = safeHref(u);
    return h ? '<a class="' + (cls || 'v2ct-link') + '" href="' + esc(h) + '" target="_blank" rel="noopener noreferrer">' + esc(label) + '</a>' : '';
  }
  function host() { return window.V2_HOST || {}; }
  function ep() { return window.EP || null; }
  function now() { return S.nowOverride || Date.now(); }
  function q(sel, root) { return (root || document).querySelector(sel); }
  function qa(sel, root) { return Array.prototype.slice.call((root || document).querySelectorAll(sel)); }
  function st(k) { var E = ep(); return (E && E.state && E.state[k]) || 'idle'; }
  function isLoading(k) { var s = st(k); return s === 'idle' || s === 'loading'; }
  function img(name) { return 'v2/img/' + name + '.jpg'; }
  var BRAIN = '<img class="v2ct-bav" src="' + img('brain-avatar') + '" alt="">';
  function currentTab() { var t = window.v2Snapshot ? window.v2Snapshot().topicsTab : 'pipeline'; return L.v2ContentTabFor(t); }
  function topicsTabNow() { return window.v2Snapshot ? window.v2Snapshot().topicsTab : 'pipeline'; }
  function isCurrent() { return !!(host().current && host().current() === 'topics' && S.view && document.body.contains(S.view)); }
  function modalOpen() { return !!document.getElementById('epModal'); }
  function arDigits(t) { return String(t).replace(/\d/g, function (d) { return '٠١٢٣٤٥٦٧٨٩'.charAt(+d); }); }
  // رقم قادم من بيانات: غير الرقم ⇒ «غير متاح بعد» (لا صفر مخترع).
  function isNum(v) { return typeof v === 'number' && isFinite(v); }
  function numTxt(v) { return isNum(v) ? ar(v) : NA; }
  function numBox(v, label) { return '<div><b' + (isNum(v) ? '' : ' class="na"') + '>' + esc(numTxt(v)) + '</b><span>' + esc(label) + '</span></div>'; }
  function dateOf(iso) { return U.dateText ? U.dateText(iso) : ''; }
  function person(name, email) {
    if (!email) return esc(name);
    return '<a class="v2ct-person" href="' + esc(L.sectionHash('people', 'person', email)) + '" data-person="' + esc(email) + '">' + esc(name) + '</a>';
  }
  function emailLink(email) { return email ? '<a class="v2ct-person v2ct-ltr" dir="ltr" href="' + esc(L.sectionHash('people', 'person', email)) + '" data-person="' + esc(email) + '">' + esc(email) + '</a>' : ''; }

  // ------------------------------------------------------------------ قراءة المصادر (undefined = جارٍ · null = فشل · مصفوفة = وصل)
  function srcList(key, get) {
    var s = st(key);
    if (s === 'error') return null;
    if (s !== 'ready' && !(s === 'loading' && S.bg[key])) return undefined;   // تحديث في الخلفية: نبقي ما عندنا ظاهرًا بلا وميض
    var v;
    try { v = get(); } catch (e) { v = null; }
    return Array.isArray(v) ? v : null;
  }
  function D(key) { var E = ep(); return (E && E.data && E.data[key]) || null; }
  function rawOf(key) { var d = D(key); return d && Array.isArray(d.raw) ? d.raw : null; }
  function memberTopics() { return srcList('platformPendingTopics', function () { return window.PTOPICS_PENDING; }); }
  function topicsList() { return srcList('platformTopics', function () { return window.PTOPICS; }); }
  function commentsList() { return srcList('platformOpinions', function () { return window.POPINIONS; }); }
  function approvedRaw() { return srcList('platformOpinionsApproved', function () { return rawOf('platformOpinionsApproved'); }); }
  function approvedList() { return srcList('platformOpinionsApproved', function () { return window.POPINIONS_APPROVED; }); }
  function creativeList() { return srcList('platformCreative', function () { return rawOf('platformCreative'); }); }
  function testimonialsList() { return srcList('testimonials', function () { return rawOf('testimonials'); }); }
  function testimonialsApprovedList() { return srcList('testimonialsApproved', function () { return rawOf('testimonialsApproved'); }); }
  function siteArticles() { return srcList('contentOverview', function () { return (D('contentOverview') || {}).articles; }); }
  function siteRaw() { return srcList('content', function () { return rawOf('content'); }); }
  function platformRaw() { return srcList('platformArticles', function () { return rawOf('platformArticles'); }); }
  function newsList() {
    return srcList('platformNews', function () {
      var raw = rawOf('platformNews') || [], byId = {};
      raw.forEach(function (r) { byId[r.id] = r; });
      return (window.PNEWS || []).map(function (n) { var r = byId[n.id] || {}; return Object.assign({}, n, { published_at: r.published_at || '' }); });
    });
  }
  function overviewPrerender() { var o = D('contentOverview'); return st('contentOverview') === 'ready' && o ? o.prerender : null; }
  function boardSrc() {
    var E = ep(), Q = st('opsQueue') === 'ready' && E.data.opsQueue ? E.data.opsQueue : null;
    var qt = Q && typeof Q.testimonials_pending === 'number' ? Q.testimonials_pending : (Q && Q.testimonials_pending && typeof Q.testimonials_pending.count === 'number' ? Q.testimonials_pending.count : null);
    return { memberTopics: memberTopics(), testimonials: testimonialsList(), comments: commentsList(), creative: creativeList(),
             siteArticles: siteArticles(), platformArticles: platformRaw(), topics: topicsList(), news: newsList(),
             approvedComments: approvedRaw(), approvedTestimonials: testimonialsApprovedList(), generating: S.generating, queueTestimonials: qt };
  }
  // تحديث خط النشر: الجانب الذي يصل منه الجديد (موضوعات الأعضاء · الآراء · التعليقات · الأعمال · نظرة المقالات) كل ٦٠ ثانية وعند الدخول،
  // والزرّ «حدّث» يعيد كل مصادر الخط. المصدر الجاهز يبقى ظاهرًا أثناء إعادة جلبه (S.bg).
  var WAITING = ['platformPendingTopics', 'testimonials', 'platformOpinions', 'platformCreative', 'contentOverview'];
  function refreshKeys(keys) {
    var E = ep();
    if (!E || !E.authed) return;
    S.lastRefresh = Date.now();
    keys.forEach(function (k) {
      if (st(k) === 'loading') return;
      if (st(k) === 'ready') S.bg[k] = true;
      E.reload(k, function () { if (st(k) !== 'loading') { delete S.bg[k]; if (isCurrent() && !modalOpen()) redraw(); } });
    });
  }
  function refreshing() { return Object.keys(S.bg).length > 0 || NEED.pipeline.some(function (k) { return st(k) === 'loading'; }); }
  function ensureTab(tab) {
    var E = ep();
    if (!E || !E.authed) return;
    (NEED[tab] || []).forEach(function (k) { E.ensure(k, null); });
  }
  function signature() {
    var n = [(window.PTOPICS || []).length, (window.PTOPICS_PENDING || []).length, (window.POPINIONS || []).length, (window.PNEWS || []).length, (window.TUTORIALS || []).length,
             Object.keys(S.generating).length];
    return KEYS.map(st).join(',') + '|' + n.join(',') + '|' + topicsTabNow() + '|' + S.cat;
  }

  // ------------------------------------------------------------------ أجزاء مشتركة
  function warnStrip(labels, tail) {
    if (!labels.length) return '';
    return '<div class="v2ct-warn" role="status">تعذّر جلب: ' + esc(labels.join(' · ')) + ' — ' + esc(tail || 'ما يظهر ناقص، وليس معناه أنه لا شيء') + ' <button type="button" class="v2ct-b2 sm" data-a="retry">أعد المحاولة</button></div>';
  }
  function noteStrip() { return S.note ? '<div class="v2ct-ok" role="status">' + esc(S.note) + '</div>' : ''; }
  function setNote(text) {
    S.note = text; clearTimeout(S.noteT);
    S.noteT = setTimeout(function () { S.note = null; redraw(); }, 12000);
  }
  function unavailable(title) {
    return '<div class="v2ct-empty"><b>' + esc(title) + ': ' + NA + '</b><p>تعذّر الوصول إلى هذه البيانات الآن، فلا تعتبر الشاشة فارغة.</p><button type="button" class="v2ct-b2" data-a="retry">أعد المحاولة</button></div>';
  }
  function loadingBlock(t) { return '<div class="v2ct-empty"><b>…جارٍ جلب ' + esc(t) + '</b></div>'; }
  function failedLabels(tab) {
    return (NEED[tab] || []).filter(function (k) { return st(k) === 'error' && FAIL_LABEL[k]; }).map(function (k) { return FAIL_LABEL[k]; });
  }
  function retryFailed() {
    var E = ep();
    if (!E) return;
    (NEED[currentTab()] || []).forEach(function (k) { if (st(k) === 'error') E.reload(k, null); });
  }
  function head(title, sub) { return '<div class="v2ct-lead-line"><b>' + esc(title) + '</b>' + (sub ? '<span>' + esc(sub) + '</span>' : '') + '</div>'; }
  function pill(text, cls) { return '<span class="v2ct-pill ' + (cls || '') + '">' + esc(text) + '</span>'; }

  // ------------------------------------------------------------------ الأوراق (نافذة الداشبورد الموجودة)
  function openSheet(title, html, wide) {
    if (typeof window.openModal !== 'function') return null;
    var s = window.openModal(title, '<div class="v2ct-m' + (wide ? ' wide' : '') + '"><div class="v2ct-fw">' + html + '</div></div>');
    var x = q('[data-x]', s);
    if (x) x.onclick = function () { if (!s.dataset.busy) window.closeModal(); };
    s.onclick = function (e) { if (e.target === s && !s.dataset.busy) window.closeModal(); };
    return s;
  }
  function errBox(s, msg) { var e = q('#v2ctErr', s); if (e) e.innerHTML = msg ? '<div class="v2ct-err" role="alert">' + esc(msg) + '</div>' : ''; }
  function closeSheet() { if (typeof window.closeModal === 'function') window.closeModal(); }
  // ورقة تأكيد: lead جملة واحدة تسمّي الأثر العلني أو الرصيد · okLabel اسم الفعل · run(done) ⇒ done({ok, error, note, silent})
  function confirmSheet(o) {
    var s = openSheet(o.title || 'تأكيد', '<p class="v2ct-lead">' + esc(o.lead) + '</p>' + (o.extra || '') + '<div id="v2ctErr"></div>'
      + '<div class="v2ct-acts2"><button type="button" class="v2ct-b1' + (o.danger ? ' danger' : '') + '" id="v2ctGo">' + esc(o.okLabel) + '</button>'
      + '<button type="button" class="v2ct-b2" id="v2ctNo">رجوع</button></div>');
    if (!s) return null;
    var go = q('#v2ctGo', s), no = q('#v2ctNo', s);
    no.onclick = function () { if (!s.dataset.busy) closeSheet(); };
    go.onclick = function () {
      if (go.dataset.busy) return;
      window.__v2ctConfirmAt = Date.now();
      go.dataset.busy = '1'; s.dataset.busy = '1'; go.disabled = true; no.disabled = true; go.textContent = 'جارٍ التنفيذ…'; errBox(s, '');
      var fin = false;
      o.run(function (res) {
        if (fin) return; fin = true;
        res = res || {};
        delete s.dataset.busy;
        if (res.ok) {
          closeSheet();
          if (res.note) setNote(res.note);
          redraw();
        } else {
          delete go.dataset.busy; go.disabled = false; no.disabled = false; go.textContent = o.okLabel;
          errBox(s, 'لم يتم. ' + (res.error || ''));
        }
      }, s);
    };
    return s;
  }
  // تأكيد داخل نفس الورقة (للنماذج: ما كتبه المؤسس يبقى في مكانه، و«رجوع» يعيده إليه بدل أن يضيع).
  function inlineConfirm(s, o) {
    var fw = q('.v2ct-fw', s), m = q('.v2ct-m', s);
    var box = document.createElement('div');
    box.className = 'v2ct-inconf';
    box.innerHTML = '<p class="v2ct-lead">' + esc(o.lead) + '</p><div id="v2ctErr2"></div><div class="v2ct-acts2"><button type="button" class="v2ct-b1' + (o.danger ? ' danger' : '') + '" id="v2ctGo2">' + esc(o.okLabel) + '</button>'
      + '<button type="button" class="v2ct-b2" id="v2ctNo2">رجوع</button></div>';
    fw.style.display = 'none'; m.appendChild(box);
    var go = q('#v2ctGo2', box), no = q('#v2ctNo2', box);
    no.onclick = function () { if (s.dataset.busy) return; box.remove(); fw.style.display = ''; };
    go.onclick = function () {
      if (go.dataset.busy) return;
      window.__v2ctConfirmAt = Date.now();
      go.dataset.busy = '1'; s.dataset.busy = '1'; go.disabled = true; no.disabled = true; go.textContent = 'جارٍ التنفيذ…';
      o.run(function (res) {
        res = res || {};
        delete s.dataset.busy;
        if (res.ok) { closeSheet(); if (res.note) setNote(res.note); redraw(); }
        else { delete go.dataset.busy; go.disabled = false; no.disabled = false; go.textContent = o.okLabel; q('#v2ctErr2', box).innerHTML = '<div class="v2ct-err" role="alert">لم يتم. ' + esc(res.error || '') + '</div>'; }
      });
    };
  }
  // ينفّذ إجراء EP ثم يتحقق من النتيجة من البيانات المُعاد تحميلها (دوال EP تنادي callback عند النجاح والفشل معًا).
  // call(cb) ⇐ ينادي EP.xxx(..., cb) · keys: المفاتيح التي يمرّ عليها آخر reload · verify(): هل تغيّرت البيانات فعلًا.
  function perform(call, keys, verify, done) {
    var E = ep(), fin = false, called = false, timer, iv;
    if (!E) { done(false, 'انقطع الاتصال — حدّث الصفحة ثم جرّب'); return; }
    E.lastError = '';
    function ready() { return !keys.some(function (k) { return E.state[k] === 'loading'; }); }
    function finish() {
      if (fin) return; fin = true; clearTimeout(timer); clearInterval(iv);
      var ok = false;
      try { ok = !!verify(); } catch (e) { ok = false; }
      done(ok, ok ? '' : (E.lastError || 'تعذّر تأكيد النتيجة. حدّث الصفحة ثم تحقّق.'));
    }
    // دوال EP تنادي callback مرّتين عند النجاح (مرّة والمصدر «جارٍ» ومرّة عند وصوله) ومرّة عند الفشل: نبدأ الفحص من أول نداء وننتظر خروج المفاتيح من «جارٍ».
    var cb = function () { if (fin) return; called = true; if (ready()) setTimeout(finish, 0); };
    iv = setInterval(function () { if (!fin && called && ready()) finish(); }, 120);
    timer = setTimeout(finish, 25000);
    call(cb);
  }
  function noErr() { var E = ep(); return !(E && E.lastError); }
  function afterWrite(keys) { var E = ep(); if (E) (keys || []).forEach(function (k) { E.reload(k, null); }); }
  // مسار شبكة صريح (آراء المتعلّمين): نتيجة بوعد، والفشل رسالته من المنصة كما هي.
  function apiPost(path, body) {
    var E = ep();
    return E.api(path, { method: 'POST', body: body || {} });
  }
  function apiErr(e) {
    if (e && e.status === 401) return 'انتهت الجلسة — سجّل الدخول من جديد ثم جرّب';
    var d = (e && e.data) || {};
    if (typeof d.error === 'string' && d.error) return arDigits(d.error);
    return 'تعذّر تنفيذ العملية';
  }

  // ------------------------------------------------------------------ رسم: الإطار والتبويبات
  function wrap(tab, html) { return '<div class="v2ct" data-tab="' + tab + '">' + noteStrip() + html + '</div>'; }
  function redraw() {
    if (!S.view || !isCurrent()) return;
    if (modalOpen()) return;                      // لا نعيد الرسم وتحت نافذة مفتوحة تكتب فيها
    var tab = currentTab();
    var entered = S.lastTab !== tab;
    if (entered) { S.lastTab = tab; }
    ensureTab(tab);
    if (entered && tab === 'pipeline' && Date.now() - S.lastRefresh > 15000) refreshKeys(WAITING);
    if (entered && tab === 'site' && SS.init) siteEnter();
    var html;
    try {
      if (tab === 'pipeline') html = drawPipeline();
      else if (tab === 'articles') html = drawArticles();
      else if (tab === 'topics') html = drawTopics();
      else if (tab === 'news') html = drawNews();
      else if (tab === 'comments') html = drawComments();
      else if (tab === 'site') html = drawSite();
      else html = drawTutorials();
    } catch (err) {
      // عطل في الرسم لا يترك شاشة فاضية تبدو كأنها «لا شيء»: نقول إننا لم نعرضها ونعرض زرّ إعادة المحاولة.
      try { if (window.console) console.error('v2s/content', err); } catch (e2) {}
      html = '<div class="v2ct-empty"><b>تعذّر عرض هذه الشاشة</b><p>لا تعتبرها فارغة. أعد المحاولة، وإن تكرّر فأخبرنا.</p><button type="button" class="v2ct-b2" data-a="retry">أعد المحاولة</button></div>';
    }
    S.view.innerHTML = wrap(tab, html);
    S.sig = signature();
    // إبراز موضوع جديد (بعد «حوّله لموضوع»): يبقى ٨ ثوانٍ عبر إعادات الرسم، ويُمرَّر إليه مرّة واحدة.
    if (S.highlight) { S.hl = { id: S.highlight, until: Date.now() + 8000, scroll: true }; S.highlight = null; }
    if (S.hl && S.hl.scroll) { var el = q('[data-id="t:' + S.hl.id + '"]', S.view); if (el) { S.hl.scroll = false; try { el.scrollIntoView({ block: 'center' }); } catch (e) {} } }
    if (S.openArticle != null) {
      var rawA = siteRaw();
      if (rawA) { var oid = S.openArticle; S.openArticle = null; var hit = rawA.filter(function (a) { return String(a.id) === String(oid); })[0]; if (hit) setTimeout(function () { openSiteReader(hit.id); }, 0); else setNote('المقال المرتبط لم يعد موجودًا'); }
    }
  }

  // سطر ترويسة القسم من أعمدة خط النشر نفسها (لا من مربّع اللوحة): ينتظرك · مسودات · أفكار. تعذّر مصدر الانتظار ⇒ «غير متاح بعد».
  API.head = function () {
    var B;
    try { B = L.v2ContentBoard(boardSrc(), now()); } catch (e) { return null; }
    if (!B || !B.counts) return null;
    var c = B.counts;
    if (c.wait === null) return B.loading && B.loading.wait ? null : NA;
    var p = [];
    if (c.wait) p.push(U.U(c.wait, ['قرار واحد ينتظرك', 'قراران ينتظرانك', 'قرارات تنتظرك', 'قرارًا ينتظرك']));
    if (c.draft) p.push(U.U(c.draft, ['مسودة', 'مسودتان', 'مسودات', 'مسودة']));
    if (c.idea) p.push(U.U(c.idea, ['فكرة', 'فكرتان', 'أفكار', 'فكرة']));
    return p.length ? p.join(' · ') + (B.partial && (B.partial.wait || B.partial.draft) ? ' — العدد ناقص' : '') : 'لا شيء ينتظر قرارك';
  };

  // ================================================================== ١) خط النشر
  var COL_LABEL = { wait: 'ينتظرك', draft: 'مسودات', idea: 'أفكار', done: 'نُشر هذا الأسبوع' };
  var COL_SEG = { wait: 'ينتظرك', draft: 'مسودات', idea: 'أفكار', done: 'نُشر' };
  var COL_NOTE = { wait: 'أصحابها ينتظرون قرارك', draft: 'لم تُنشر بعد', idea: 'مادة خام تنتظر أن تتحول إلى نقاش أو خبر منشور', done: 'ما نُشر أو اعتُمد خلال ٧ أيام' };
  var COL_TONE = { wait: 'wine', draft: 'amber', idea: 'ink', done: 'green' };

  var SHEET_KINDS = ['memberTopic', 'testimonial', 'comment', 'creative', 'siteDraft', 'platformDraft', 'working', 'idea', 'newsDraft'];
  function hasDest(it) { return !!it.go || SHEET_KINDS.indexOf(it.kind) > -1; }
  function ticketHtml(it) {
    var slim = it.col === 'done';
    var sg = L.v2ContentSuggest(it);
    var who = it.who ? '<p class="v2ct-who">' + (it.who.email ? person(it.who.text, it.who.email) : esc(it.who.text)) + '</p>' : '';
    var brain = !slim && it.brain ? '<div class="v2ct-brain">' + BRAIN + '<p>' + esc(it.brain) + '</p></div>' : '';
    var btn = '';
    if (!slim) {
      if (it.kind === 'generating') btn = '<p class="v2ct-status" role="status">' + esc(it.status) + '</p>';
      else if (sg) btn = '<button type="button" class="v2ct-b1' + (sg.act === 'rejectComment' ? ' ink' : '') + '" data-a="primary" data-id="' + esc(it.id) + '">' + esc(sg.label) + '</button>';
    }
    if (slim && it.kind === 'doneArticle') btn = '<a class="v2ct-link" href="' + esc(SEC_SOURCE + encodeURIComponent(it.ref.id)) + '" target="_blank" rel="noopener noreferrer">اعرضه على الموقع</a>';
    var big = it.kind === 'testimonialCount';
    return '<article class="v2ct-t tone-' + esc(it.tone) + (slim ? ' slim' : '') + (big ? ' count' : '') + '" data-id="' + esc(it.id) + '">'
      + '<div class="v2ct-strip"><span class="v2ct-type">' + esc(it.strip) + '</span>' + (it.text ? '<time class="v2ct-time" data-since="' + esc(it.at || '') + '">' + esc(it.text) + '</time>' : '') + '</div>'
      + '<div class="v2ct-body">'
      + (big ? '<h3 class="v2ct-bignum"><b>' + esc(ar(it.n)) + '</b><span>رأي متعلّم ينتظر المراجعة</span></h3>'
             : '<h3>' + (hasDest(it) ? '<button type="button" class="v2ct-open" data-a="open" data-id="' + esc(it.id) + '">' + esc(it.title) + '</button>' : '<span class="v2ct-open static">' + esc(it.title) + '</span>') + '</h3>')
      + who + brain + (btn ? '<div class="v2ct-acts">' + btn + '</div>' : '') + '</div></article>';
  }
  function placeholder() { return '<div class="v2ct-t ph"><div class="v2ct-strip"></div><div class="v2ct-body"><i></i><i></i></div></div>'; }
  function prerenderPill() {
    var st0 = st('contentOverview');
    if (st0 === 'error') return '<span class="v2ct-fact na">تحديث صفحات محركات البحث: ' + NA + '</span>';
    if (st0 !== 'ready') return '';
    var p = L.v2ContentPrerender(overviewPrerender(), now());
    return '<span class="v2ct-fact ' + p.tone + '">' + esc(p.text) + '</span>';
  }
  function drawPipeline() {
    var B = L.v2ContentBoard(boardSrc(), now());
    S.board = B; S.items = {};
    B.order.forEach(function (c) { B.cols[c].forEach(function (it) { S.items[it.id] = it; }); });
    // العمود الظاهر في الموبايل: اختيار المؤسس يبقى، وقبله الافتراضي «ينتظرك» وإلا «مسودات» (يُحسب في كل رسم فلا يعلق على قيمة وقت التحميل).
    var active = S.picked && B.order.indexOf(S.col) > -1 ? S.col : (B.counts.draft > 0 && !(B.counts.wait > 0) && B.counts.wait !== null ? 'draft' : 'wait');
    var seg = '', cols = '';
    B.order.forEach(function (c) {
      var n = B.counts[c], chip;
      if (B.loading[c] && n === null) chip = '…';
      else if (n === null) chip = NA;
      else chip = ar(n) + (B.partial[c] ? '+' : '');
      var title = B.partial[c] ? ' title="العدد ناقص — تعذّر جلب بعض المصادر"' : '';
      seg += '<button type="button" class="v2ct-segb tone-' + COL_TONE[c] + (c === active ? ' on' : '') + '" role="tab" aria-selected="' + (c === active) + '" data-a="col" data-col="' + c + '"><span>' + esc(COL_SEG[c]) + '</span><b>' + esc(n === null ? '—' : chip) + '</b></button>';
      var body;
      if (B.failed[c]) body = unavailable(COL_LABEL[c]);
      else if (B.loading[c] && !B.cols[c].length) body = placeholder() + placeholder();
      else if (!B.cols[c].length) body = '<p class="v2ct-none">لا شيء هنا الآن</p>';
      else {
        var shown = S.expand[c] ? B.cols[c] : B.cols[c].slice(0, B.max);
        body = shown.map(ticketHtml).join('');
        if (B.more[c] && !S.expand[c]) body += '<button type="button" class="v2ct-b2 more" data-a="more" data-col="' + c + '">و' + esc(ar(B.more[c].n)) + ' أخرى — افتح القائمة</button>';
      }
      cols += '<section class="v2ct-col tone-' + COL_TONE[c] + '" data-col="' + c + '" aria-label="' + esc(COL_LABEL[c]) + '"><header class="v2ct-ch"><b>' + esc(COL_LABEL[c]) + '</b>'
        + '<span class="v2ct-n"' + title + '>' + esc(chip) + '</span></header><p class="v2ct-colnote">' + esc(COL_NOTE[c]) + '</p><div class="v2ct-list">' + body + '</div></section>';
    });
    // شريط الحقائق
    var facts = '';
    var so = st('contentOverview');
    if (so === 'ready' && B.top.today !== null) facts += '<span class="v2ct-fact">نُشر على الموقع اليوم: ' + esc(ar(B.top.today)) + '</span><span class="v2ct-fact">هذا الأسبوع: ' + esc(ar(B.top.week)) + '</span>';
    else if (so === 'error') facts += '<span class="v2ct-fact na">نُشر على الموقع اليوم: ' + NA + '</span>';
    facts += prerenderPill();
    facts += '<button type="button" class="v2ct-b2 sm v2ct-refresh" data-a="refreshBoard"' + (refreshing() ? ' disabled' : '') + '>' + (refreshing() ? '…جارٍ التحديث' : 'حدّث') + '</button>';
    var hero = '<div class="v2ct-hero" style="background-image:url(' + img('content') + ')"><div class="v2ct-hero-in">' + BRAIN + '<p>' + esc(B.top.line) + '</p></div></div>';
    return hero + '<div class="v2ct-facts">' + facts + '</div>' + warnStrip(failedLabels('pipeline'))
      + '<div class="v2ct-seg" role="tablist" aria-label="أعمدة خط النشر">' + seg + '</div>'
      + '<div class="v2ct-cols" data-active="' + active + '">' + cols + '</div>';
  }

  // ================================================================== ٢) المقالات
  var PLAT_CAT = { feature: 'شرح المنصة', news: 'تحليل خبر', law: 'قانوني', guide: 'دليل', platform: 'المنصة', other: 'أخرى' };
  function publishedTitles() {
    var raw = siteRaw() || [];
    return raw.filter(function (a) { return a.status === 'published'; }).map(function (a) { return String(a.title || '').trim(); });
  }
  function overviewFor(id) { return (siteArticles() || []).filter(function (a) { return String(a.id) === String(id); })[0] || null; }
  function factsFor(a) {
    var meta = overviewFor(a.id);
    return L.v2ContentFacts(meta ? Object.assign({}, meta, { title: a.title, status: a.status }) : { title: a.title, status: a.status }, publishedTitles());
  }
  function articleTools(sub) {
    return '<div class="v2ct-bar">' + (sub === 'site' ? '<button type="button" class="v2ct-b1 auto" data-a="newart">مقال جديد</button>' : '')
      + '<button type="button" class="v2ct-b2" data-a="tools">أدوات الكتابة</button></div>';
  }
  function drawArticles() {
    var sub = topicsTabNow() === 'auto' ? 'plat' : 'site';
    var switchHtml = '<div class="v2ct-sw" role="tablist" aria-label="مكان النشر"><button type="button" role="tab" class="' + (sub === 'site' ? 'on' : '') + '" aria-selected="' + (sub === 'site') + '" data-a="asub" data-v="articles">على الموقع</button>'
      + '<button type="button" role="tab" class="' + (sub === 'plat' ? 'on' : '') + '" aria-selected="' + (sub === 'plat') + '" data-a="asub" data-v="auto">على المنصة</button></div>';
    var line = sub === 'site' ? 'مقالات elprofessor.net: يقرؤها الناس ومحركات البحث.' : 'مقالات صفحة المقالات داخل المنصة.';
    var body = sub === 'site' ? drawSiteList() : drawPlatformList();
    return '<div class="v2ct-narrow">' + switchHtml + '<p class="v2ct-line">' + esc(line) + '</p>' + articleTools(sub) + body + '</div>';
  }
  function drawSiteList() {
    var raw = siteRaw();
    if (raw === undefined) return loadingBlock('مقالات الموقع');
    if (raw === null) return unavailable('مقالات الموقع');
    var strip = '';
    if (st('contentOverview') === 'error') strip += warnStrip(['حالة مقالات الموقع'], 'غير متاح بعد');
    var pre = overviewPrerender();
    if (S.afterPublish && pre) { var pp = L.v2ContentPrerender(pre, now()); if (pp.tone === 'bad') strip += '<div class="v2ct-warn" role="status">' + esc(pp.text) + '</div>'; }
    var drafts = raw.filter(function (a) { return a.status !== 'published'; }), pubs = raw.filter(function (a) { return a.status === 'published'; });
    var chips = '<div class="v2ct-chips"><button type="button" class="v2ct-chip' + (S.afilter === 'draft' ? ' on' : '') + '" data-a="afilter" data-v="draft">مسودات (' + esc(ar(drafts.length)) + ')</button>'
      + '<button type="button" class="v2ct-chip' + (S.afilter === 'published' ? ' on' : '') + '" data-a="afilter" data-v="published">منشورة (' + esc(ar(pubs.length)) + ')</button></div>';
    var list = S.afilter === 'published' ? pubs : drafts;
    var cards;
    if (!list.length) cards = '<div class="v2ct-empty"><b>' + (S.afilter === 'draft' ? 'لا مسودات الآن. اكتب مقالًا جديدًا أو اسحب الجاهز من المنصة من «أدوات الكتابة».' : 'لا مقالات منشورة بعد') + '</b></div>';
    else cards = '<div class="v2ct-stack">' + list.map(function (a) {
      var f = factsFor(a), chipsHtml = '';
      if (st('contentOverview') === 'ready') {
        if (f.words !== null) chipsHtml += pill(ar(f.words) + ' كلمة');
        if (f.hasImage === false) chipsHtml += pill('بلا صورة', 'amber');
        if (f.hasMeta === false) chipsHtml += pill('بلا وصف لمحركات البحث', 'amber');
        if (f.reviewer) chipsHtml += pill('راجعه ' + f.reviewer);
      }
      if (f.dupTitle) chipsHtml += pill('عنوانه مطابق لمقال منشور', 'amber');
      var pub = a.status === 'published';
      return '<button type="button" class="v2ct-card art" data-a="sread" data-id="' + esc(a.id) + '"><span class="v2ct-ct">' + esc(a.title) + '</span>'
        + '<span class="v2ct-cm">' + esc(L.v2ContentByText(a.by) + (a.date ? ' · ' + arDigits(a.date) : '')) + '</span>'
        + '<span class="v2ct-pills">' + pill(pub ? 'منشور' : 'مسودة', pub ? 'green' : 'amber') + chipsHtml + '</span></button>';
    }).join('') + '</div>';
    return strip + chips + cards;
  }
  function drawPlatformList() {
    var raw = platformRaw();
    if (raw === undefined) return loadingBlock('مقالات المنصة');
    if (raw === null) return unavailable('مقالات المنصة');
    var titles = publishedTitles();
    var stale = raw.filter(function (a) { return a.status !== 'published' && titles.indexOf(String(a.title || '').trim()) > -1; }).length;
    var brain = stale ? '<div class="v2ct-brain wide">' + BRAIN + '<p>' + esc(ar(stale) + ' مسودة هنا عناوينها مطابقة لمقالات منشورة على الموقع.') + '</p></div>' : '';
    if (!raw.length) return '<div class="v2ct-empty"><b>لا مقالات على المنصة بعد.</b></div>';
    return brain + '<div class="v2ct-stack">' + raw.map(function (a) {
      var pub = a.status === 'published', dup = !pub && titles.indexOf(String(a.title || '').trim()) > -1;
      return '<button type="button" class="v2ct-card art" data-a="pread" data-id="' + esc(a.id) + '"><span class="v2ct-ct">' + esc(a.title || 'بلا عنوان') + '</span>'
        + (a.excerpt ? '<span class="v2ct-ex">' + esc(a.excerpt) + '</span>' : '')
        + '<span class="v2ct-pills">' + pill(PLAT_CAT[a.category] || PLAT_CAT.other) + pill(pub ? 'منشور على المنصة' : 'مسودة', pub ? 'green' : 'amber')
        + (dup ? pill('عنوانه مطابق لمقال على الموقع', 'amber') : '') + '</span></button>';
    }).join('') + '</div>';
  }
  function bodyHtml(body) {
    var list = Array.isArray(body) ? body : (body ? String(body).split('\n\n') : []);
    if (!list.length) return '<p class="v2ct-none">لا يوجد نص لعرضه</p>';
    return list.map(function (b) { b = String(b); return b.indexOf('## ') === 0 ? '<h3>' + esc(b.slice(3)) + '</h3>' : '<p>' + esc(b) + '</p>'; }).join('');
  }
  function compareRow(title) {
    var hit = (siteRaw() || []).filter(function (a) { return a.status === 'published' && String(a.title || '').trim() === String(title || '').trim(); })[0];
    if (!hit) return '';
    return '<div class="v2ct-cmp"><span>المقال المنشور بنفس العنوان: <b>' + esc(hit.title) + '</b>' + (hit.date ? ' · ' + esc(arDigits(hit.date)) : '') + '</span>'
      + '<a class="v2ct-link" href="' + esc(SEC_SOURCE + encodeURIComponent(hit.id)) + '" target="_blank" rel="noopener noreferrer">اعرضه على الموقع</a></div>';
  }
  function cmsRef(a) { return { aid: a.id, title: a.title }; }

  // —— قارئ مقال الموقع ومحرّره (ورقة بمرحلتين)
  function openSiteReader(id) {
    var raw = (siteRaw() || []).filter(function (a) { return String(a.id) === String(id); })[0];
    if (!raw) { setNote('المقال غير موجود في القائمة الحالية'); redraw(); return; }
    var f = factsFor(raw), pub = raw.status === 'published', dupHit = compareRow(raw.title);
    var s = openSheet('مقال للموقع', '<div id="v2ctStage"></div>', true);
    if (!s) return;
    var stage = q('#v2ctStage', s);
    function read() {
      var prim, sec = '';
      if (pub) {
        prim = '<a class="v2ct-b1 lnk" href="' + esc(SEC_SOURCE + encodeURIComponent(raw.id)) + '" target="_blank" rel="noopener noreferrer">اعرضه على الموقع</a>';
        sec = '<button type="button" class="v2ct-b2" id="v2ctEdit">عدّل</button><button type="button" class="v2ct-b2" id="v2ctUnpub">أوقف النشر</button>';
      } else if (f.dupTitle) {
        prim = '<button type="button" class="v2ct-b1 danger" id="v2ctDelDup">احذف المكرر</button>';
        sec = '<button type="button" class="v2ct-b2" id="v2ctPub">انشر على الموقع</button><button type="button" class="v2ct-b2" id="v2ctEdit">عدّل</button><button type="button" class="v2ct-b3" id="v2ctDel">احذف المسودة</button>';
      } else {
        prim = '<button type="button" class="v2ct-b1" id="v2ctPub">انشر على الموقع</button>';
        sec = '<button type="button" class="v2ct-b2" id="v2ctEdit">عدّل</button><button type="button" class="v2ct-b3" id="v2ctDel">احذف المسودة</button>';
      }
      stage.innerHTML = '<p class="v2ct-kick">' + esc((raw.cat || '') + (raw.kicker ? ' · ' + raw.kicker : '')) + '</p><h2 class="v2ct-rt">' + esc(raw.title) + '</h2>'
        + '<p class="v2ct-pills">' + pill(pub ? 'منشور' : 'مسودة', pub ? 'green' : 'amber') + '</p>'
        + (f.factsLine ? '<p class="v2ct-line">' + esc(f.factsLine) + '</p>' : '') + (f.dupTitle ? dupHit : '')
        + (raw.excerpt ? '<p class="v2ct-exb">' + esc(raw.excerpt) + '</p>' : '')
        + (String(raw.image_url || '').trim() ? '<p class="v2ct-pills">' + pill('صورة الغلاف: موجودة', 'green') + '</p>' : '')
        + '<div class="v2ct-article">' + bodyHtml(raw.body) + '</div>'
        + '<div class="v2ct-acts2">' + prim + sec + '</div>'
        + (pub ? '<p class="v2ct-fine">لحذف مقال منشور: أوقف نشره أولًا، ثم احذفه من المسودات.</p>' : '');
      wireRead();
    }
    function wireRead() {
      var e = q('#v2ctEdit', stage); if (e) e.onclick = function () { edit(); };
      var p = q('#v2ctPub', stage); if (p) p.onclick = function () { closeSheet(); publishSite(raw); };
      var u = q('#v2ctUnpub', stage); if (u) u.onclick = function () { closeSheet(); unpublishSite(raw); };
      var d = q('#v2ctDel', stage); if (d) d.onclick = function () { closeSheet(); deleteDraft(raw, false); };
      var dd = q('#v2ctDelDup', stage); if (dd) dd.onclick = function () { closeSheet(); deleteDraft(raw, true); };
    }
    function edit() { articleForm(stage, raw, function () { read(); }, s); }
    read();
  }
  function articleForm(stage, raw, back, sheet) {
    var e = raw || {};
    var isNew = !raw, pub = !!raw && raw.status === 'published';
    var bodyText = Array.isArray(e.body) ? e.body.join('\n\n') : '';
    function fld(id, label, val, extra) { return '<div class="v2ct-fld"><label for="' + id + '">' + esc(label) + '</label>' + extra.replace('{v}', esc(val)) + '</div>'; }
    stage.innerHTML = '<h2 class="v2ct-rt">' + (isNew ? 'مقال جديد للموقع' : 'تعديل المقال') + '</h2>'
      + fld('ae_t', 'العنوان', e.title || '', '<input id="ae_t" value="{v}" placeholder="عنوان المقال">')
      + '<div class="v2ct-two">' + fld('ae_cat', 'التصنيف', e.cat || '', '<input id="ae_cat" value="{v}" placeholder="قانون الشركات">') + fld('ae_k', 'الوسم', e.kicker || '', '<input id="ae_k" value="{v}" placeholder="تشريعات">') + '</div>'
      + fld('ae_ex', 'المقتطف', e.excerpt || '', '<textarea id="ae_ex" rows="2" placeholder="ملخص قصير يظهر في بطاقة المقالات">{v}</textarea>')
      + fld('ae_body', 'نص المقال', bodyText, '<textarea id="ae_body" rows="9" placeholder="افصل بين الفقرات بسطر فارغ، وابدأ العنوان الفرعي بـ ##">{v}</textarea>')
      + fld('ae_by', 'الكاتب', isNew ? 'فريق البروفيسور' : (e.by ? L.v2ContentByText(e.by) : ''), '<input id="ae_by" value="{v}">')
      + fld('ae_img', 'رابط صورة المقال', e.image_url || '', '<input id="ae_img" dir="ltr" value="{v}" placeholder="https://...">')
      + fld('ae_meta', 'وصف محركات البحث', e.meta_description || '', '<textarea id="ae_meta" rows="2" placeholder="الجملة التي تظهر تحت العنوان في جوجل، وتبدأ بالإجابة المختصرة">{v}</textarea>')
      + fld('ae_rev', 'راجعه (اختياري)', e.reviewed_by || '', '<input id="ae_rev" value="{v}" placeholder="اسم من راجع المقال فعلًا، واتركه فارغًا إن لم يُراجَع">')
      + (isNew ? '' : '<p class="v2ct-fine">رابط المقال المنشور ثابت ولا يتغيّر بتغيير العنوان، وتاريخ آخر تحديث يتحرك فقط عند تعديل جوهري في النص.</p>')
      + '<div id="v2ctErr"></div><div class="v2ct-acts2"><button type="button" class="v2ct-b1" id="v2ctSave">' + (isNew ? 'احفظ مسودة' : 'احفظ') + '</button>'
      + (isNew ? '<button type="button" class="v2ct-b2" id="v2ctSavePub">احفظ وانشر الآن</button>' : '') + '<button type="button" class="v2ct-b2" id="v2ctBack">رجوع</button></div>';
    function gather() {
      return { t: q('#ae_t', stage).value.trim() || 'مقال بلا عنوان', cat: q('#ae_cat', stage).value.trim() || 'قانوني', k: q('#ae_k', stage).value.trim() || 'مقال',
               ex: q('#ae_ex', stage).value.trim(), by: q('#ae_by', stage).value.trim() || 'الإدارة', body: q('#ae_body', stage).value.trim(),
               img: q('#ae_img', stage).value.trim(), meta: q('#ae_meta', stage).value.trim(), rev: q('#ae_rev', stage).value.trim() };
    }
    q('#v2ctBack', stage).onclick = function () { if (isNew) closeSheet(); else back(); };
    function g0() { return gather(); }
    function doSave(g, publish, withConfirm) {
      var run = function (done) {
        var before = (siteRaw() || []).length;
        perform(function (cb) {
          if (isNew) ep().createArticle(g, publish, cb); else ep().updateArticle(cmsRef(raw), g, cb);
        }, ['content'], function () {
          if (!noErr()) return false;
          return isNew ? (siteRaw() || []).length > before : true;
        }, function (ok, err) {
          if (ok) { afterWrite(['contentOverview']); if (publish) S.afterPublish = true; }
          done({ ok: ok, error: err, note: ok ? (isNew ? (publish ? 'تمّ: نُشر «' + g.t + '» على الموقع.' : 'تمّ: حُفظت مسودة «' + g.t + '».') : 'تمّ: حُفظ «' + g.t + '».') : '' });
        });
      };
      if (withConfirm) {
        inlineConfirm(sheet, { lead: publish && isNew ? 'سيظهر «' + g.t + '» على الموقع الآن.' : 'يظهر التعديل على الموقع فور الحفظ.', okLabel: publish && isNew ? 'احفظ وانشر الآن' : 'احفظ', run: run });
      } else {
        // حفظ مسودة أو تعديل مسودة: مستثنى من التأكيد (لا يظهر شيء للناس).
        var sb = q('#v2ctSave', stage); sb.disabled = true; sb.textContent = 'جارٍ الحفظ…';
        run(function (res) {
          if (res.ok) { closeSheet(); setNote(res.note); redraw(); }
          else { sb.disabled = false; sb.textContent = isNew ? 'احفظ مسودة' : 'احفظ'; errBox(sheet, 'لم يتم. ' + res.error); }
        });
      }
    }
    q('#v2ctSave', stage).onclick = function () {
      var g = gather();
      if (!isNew && pub) {
        // مقال منشور: التعديل يظهر للناس فور الحفظ ⇒ تأكيد داخل الورقة نفسها (ما كتبه يبقى في مكانه).
        doSave(g, false, true);
      } else doSave(g, false, false);
    };
    var sp = q('#v2ctSavePub', stage);
    if (sp) sp.onclick = function () { doSave(g0(), true, true); };
  }
  function publishSite(raw) {
    var lead = L.v2ContentPublishLead(raw.title, overviewPrerender());
    confirmSheet({ title: 'نشر على الموقع', lead: lead, okLabel: 'انشر على الموقع', run: function (done) {
      perform(function (cb) { ep().publishArticle(cmsRef(raw), cb); }, ['content'], function () {
        var hit = (siteRaw() || []).filter(function (a) { return String(a.id) === String(raw.id); })[0];
        return !!hit && hit.status === 'published';
      }, function (ok, err) {
        if (ok) {
          S.afterPublish = true; afterWrite(['contentOverview']);
          setTimeout(function () { var E = ep(); if (E) E.reload('contentOverview', function () { if (isCurrent() && !modalOpen()) redraw(); }); }, 60000);
        }
        done({ ok: ok, error: err, note: 'تمّ: نُشر على الموقع.' });
      });
    } });
  }
  function unpublishSite(raw) {
    confirmSheet({ title: 'إيقاف النشر', lead: 'سيختفي «' + raw.title + '» من الموقع وتُحذف صفحته من محركات البحث مع التحديث القادم.', okLabel: 'أوقف النشر', danger: true, run: function (done) {
      perform(function (cb) { ep().unpublishArticle(cmsRef(raw), cb); }, ['content'], function () {
        var hit = (siteRaw() || []).filter(function (a) { return String(a.id) === String(raw.id); })[0];
        return !!hit && hit.status !== 'published';
      }, function (ok, err) { if (ok) afterWrite(['contentOverview']); done({ ok: ok, error: err, note: 'تمّ: أُوقف نشر «' + raw.title + '».' }); });
    } });
  }
  function deleteDraft(raw, isDup) {
    var lead = 'ستُحذف هذه المسودة نهائيًا ولا يمكن استرجاعها.';
    if (isDup) {
      var hit = (siteRaw() || []).filter(function (a) { return a.status === 'published' && String(a.title || '').trim() === String(raw.title || '').trim(); })[0];
      if (hit) lead += ' المسودة: ' + raw.title + ' · المنشور: ' + hit.title + (hit.date ? ' (' + arDigits(hit.date) + ')' : '');
    }
    confirmSheet({ title: isDup ? 'حذف المكرر' : 'حذف المسودة', lead: lead, okLabel: isDup ? 'احذف المكرر' : 'احذف المسودة', danger: true, run: function (done) {
      perform(function (cb) { ep().rejectArticle(cmsRef(raw), cb); }, ['content'], function () {
        return !(siteRaw() || []).some(function (a) { return String(a.id) === String(raw.id); });
      }, function (ok, err) { if (ok) afterWrite(['contentOverview']); done({ ok: ok, error: err, note: 'تمّ: حُذفت المسودة.' }); });
    } });
  }

  // —— قارئ مقال المنصة
  function openPlatformReader(id) {
    var raw = (platformRaw() || []).filter(function (a) { return String(a.id) === String(id); })[0];
    if (!raw) { setNote('المقال غير موجود في القائمة الحالية'); redraw(); return; }
    var pub = raw.status === 'published', stale = !pub && publishedTitles().indexOf(String(raw.title || '').trim()) > -1;
    var prim, sec = '';
    if (pub) { prim = '<button type="button" class="v2ct-b1" id="v2ctUnpubP">أوقف النشر</button>'; }
    else if (stale) { prim = '<button type="button" class="v2ct-b1 danger" id="v2ctDelDupP">احذف المكرر</button>'; sec = '<button type="button" class="v2ct-b2" id="v2ctPubP">انشر على المنصة</button>'; }
    else prim = '<button type="button" class="v2ct-b1" id="v2ctPubP">انشر على المنصة</button>';
    var s = openSheet('مقال على المنصة', '<p class="v2ct-kick">' + esc(PLAT_CAT[raw.category] || PLAT_CAT.other) + '</p><h2 class="v2ct-rt">' + esc(raw.title) + '</h2>'
      + '<p class="v2ct-pills">' + pill(pub ? 'منشور على المنصة' : 'مسودة', pub ? 'green' : 'amber') + '</p>' + (stale ? compareRow(raw.title) : '')
      + (raw.excerpt ? '<p class="v2ct-exb">' + esc(raw.excerpt) + '</p>' : '') + '<div class="v2ct-article">' + bodyHtml(raw.body) + '</div>'
      + '<div class="v2ct-acts2">' + prim + sec + '<button type="button" class="v2ct-b3" id="v2ctDelP">احذف</button></div>', true);
    if (!s) return;
    var ref = { id: raw.id, title: raw.title };
    function bind(sel, fn) { var b = q(sel, s); if (b) b.onclick = function () { closeSheet(); fn(); }; }
    bind('#v2ctPubP', function () {
      confirmSheet({ title: 'نشر على المنصة', lead: 'سيظهر في صفحة المقالات داخل المنصة.', okLabel: 'انشر على المنصة', run: function (done) {
        perform(function (cb) { ep().publishArticleP(ref, cb); }, ['platformArticles'], function () { return platRow(raw.id, 'published'); },
          function (ok, err) { done({ ok: ok, error: err, note: 'تمّ: نُشر على المنصة.' }); });
      } });
    });
    bind('#v2ctUnpubP', function () {
      confirmSheet({ title: 'إيقاف النشر', lead: 'سيختفي من صفحة المقالات داخل المنصة.', okLabel: 'أوقف النشر', danger: true, run: function (done) {
        perform(function (cb) { ep().unpublishArticleP(ref, cb); }, ['platformArticles'], function () { return platRow(raw.id, 'draft'); },
          function (ok, err) { done({ ok: ok, error: err, note: 'تمّ: أُوقف النشر.' }); });
      } });
    });
    function delP(isDup) {
      var lead = isDup ? 'سيُحذف «' + raw.title + '» من المنصة نهائيًا. المسودة: ' + raw.title + ' · المنشور على الموقع بنفس العنوان.' : 'سيُحذف «' + raw.title + '» من المنصة نهائيًا.';
      confirmSheet({ title: isDup ? 'حذف المكرر' : 'حذف المقال', lead: lead, okLabel: isDup ? 'احذف المكرر' : 'احذف', danger: true, run: function (done) {
        perform(function (cb) { ep().deleteArticleP(ref, cb); }, ['platformArticles'], function () { return !(platformRaw() || []).some(function (a) { return String(a.id) === String(raw.id); }); },
          function (ok, err) { done({ ok: ok, error: err, note: 'تمّ: حُذف المقال.' }); });
      } });
    }
    bind('#v2ctDelDupP', function () { delP(true); });
    bind('#v2ctDelP', function () { delP(false); });
  }
  function platRow(id, status) { return (platformRaw() || []).some(function (a) { return String(a.id) === String(id) && (status === 'published' ? a.status === 'published' : a.status !== 'published'); }); }

  // —— أدوات الكتابة
  function openTools(sub) {
    var rows = '';
    if (sub === 'site') {
      rows += toolRow('موضوعات المدوّنة', 'عناوين صفحات الموضوعات في المدوّنة ووصفها', 'tblog', 'افتح');
      rows += toolRow('اسحب الجاهز من المنصة', 'ينقل المقالات التي انتهت كتابتها على المنصة إلى مسودات الموقع', 'tsync', 'اسحب');
    }
    rows += toolRow('اكتب مقالات الآن', 'يكتب ٣ مقالات وموضوعين كمسودات', 'twrite', 'اكتب');
    var s = openSheet('أدوات الكتابة', '<div class="v2ct-tools">' + rows + '</div><div id="v2ctErr"></div><div class="v2ct-acts2"><button type="button" class="v2ct-b2" id="v2ctNo">إغلاق</button></div>');
    if (!s) return;
    q('#v2ctNo', s).onclick = closeSheet;
    var b1 = q('[data-t="tblog"]', s); if (b1) b1.onclick = function () { closeSheet(); openBlogTopics(); };
    var b2 = q('[data-t="tsync"]', s);
    if (b2) b2.onclick = function () {
      // مستثنى من التأكيد: ينشئ مسودات فقط ولا يظهر منه شيء للناس ولا يستهلك رصيدًا.
      b2.disabled = true; b2.textContent = 'جارٍ السحب…';
      perform(function (cb) { ep().syncContent(cb); }, ['content'], noErr, function (ok, err) {
        if (ok) { afterWrite(['contentOverview', 'platformArticles']); closeSheet(); setNote('تمّ: سُحب الجاهز من المنصة إلى مسودات الموقع.'); redraw(); }
        else { b2.disabled = false; b2.textContent = 'اسحب'; errBox(s, 'لم يتم. ' + err); }
      });
    };
    var b3 = q('[data-t="twrite"]', s);
    if (b3) b3.onclick = function () { closeSheet(); writeNow(); };
  }
  function toolRow(title, sub, t, btn) {
    return '<div class="v2ct-tool"><div><b>' + esc(title) + '</b><span>' + esc(sub) + '</span></div><button type="button" class="v2ct-b2" data-t="' + t + '">' + esc(btn) + '</button></div>';
  }
  function writeNow() {
    confirmSheet({ title: 'اكتب مقالات الآن', lead: 'يبدأ النظام كتابة ٣ مقالات وموضوعين كمسودات. يستهلك ذلك من رصيد الكتابة الآلية. تظهر المسودات هنا بعد انتهاء الكتابة، ويسحبها النظام تلقائيًا ما دامت هذه الصفحة مفتوحة.',
      okLabel: 'ابدأ الكتابة', run: function (done) {
        var E = ep(), fin = false;
        E.lastError = '';
        E.runDailyContent(function (r) {
          if (fin) return; fin = true;
          var already = !!(r && r.alreadyRunning);
          done({ ok: noErr(), error: E.lastError || 'تعذّر بدء الكتابة', note: already ? 'الكتابة الآلية تعمل الآن بالفعل. لم يُستهلك رصيد جديد.' : 'تمّ: بدأت الكتابة الآلية. تظهر المسودات بعد انتهائها.' });
        }, { isOpen: function () { return host().current && host().current() === 'topics'; } });
      } });
  }
  function openBlogTopics() {
    var s = openSheet('موضوعات المدوّنة', '<p class="v2ct-lead">العنوان والوصف يظهران على صفحة الموضوع وفي قائمة الموضوعات بالمدوّنة. الرابط ثابت ولا يتغيّر.</p><div id="v2ctBt" class="v2ct-line">…جارٍ تحميل الموضوعات</div><div class="v2ct-acts2"><button type="button" class="v2ct-b2" id="v2ctNo">إغلاق</button></div>', true);
    if (!s) return;
    q('#v2ctNo', s).onclick = closeSheet;
    ep().blogTopics(function (err, rows) {
      var box = q('#v2ctBt', s);
      if (!box) return;
      if (err) { box.innerHTML = '<div class="v2ct-err">لم يتم. ' + esc(err) + '</div>'; return; }
      if (!rows.length) { box.textContent = 'لا موضوعات بعد'; return; }
      box.className = '';
      box.innerHTML = rows.map(function (t, i) {
        return '<div class="v2ct-bt" data-i="' + i + '"><p class="v2ct-ltr" dir="ltr">/blog/topic/' + esc(t.slug) + '</p><span class="v2ct-line">' + (isNum(t.count) ? esc(ar(t.count)) + ' مقال منشور' : 'عدد المقالات: ' + NA) + '</span>'
          + '<div class="v2ct-fld"><label>العنوان</label><input data-f="label" maxlength="120" value="' + esc(t.label) + '"></div>'
          + '<div class="v2ct-fld"><label>الوصف</label><textarea data-f="description" rows="2" maxlength="400">' + esc(t.description || '') + '</textarea></div>'
          + '<div class="v2ct-rowacts"><button type="button" class="v2ct-b2" data-save="' + i + '">احفظ</button>' + (t.count && safeHref(t.url, true) ? '<a class="v2ct-link" target="_blank" rel="noopener noreferrer" href="' + esc(safeHref(t.url, true)) + '">اعرض الصفحة</a>' : '') + '</div>'
          + '<div class="v2ct-rowerr"></div></div>';
      }).join('');
      qa('[data-save]', box).forEach(function (b) {
        b.onclick = function () {
          var i = +b.getAttribute('data-save'), t = rows[i], row = q('[data-i="' + i + '"]', box);
          var lab = q('[data-f="label"]', row).value.trim(), desc = q('[data-f="description"]', row).value.trim(), er = q('.v2ct-rowerr', row);
          if (!lab) { er.innerHTML = '<div class="v2ct-err">عنوان الموضوع مطلوب</div>'; return; }
          er.innerHTML = '';
          confirmSheet({ title: 'حفظ الموضوع', lead: 'يظهر العنوان والوصف الجديدان على صفحة الموضوع في المدوّنة.', okLabel: 'احفظ', run: function (done) {
            window.__v2ctBlogSave = true;
            ep().saveBlogTopic(t.cluster_id, { label: lab, description: desc }, function (e2, nt) {
              if (!e2) { done({ ok: true, note: 'تمّ: حُفظ موضوع «' + lab + '».' }); }
              else done({ ok: false, error: e2 });
            });
          } });
        };
      });
    });
  }

  // ================================================================== ٣) الموضوعات
  var SRC_AR = { human: 'كتبه الفريق', idea: 'فكرة', expert: 'من خبير', news: 'من خبر' };
  var STATUS_AR = { draft: 'مسودة', open: 'على اللوحة', merged: 'يُكتب', published: 'منشور' };
  function segLabelPill(t) { return t.segment_label ? pill('الفئة: ' + t.segment_label + (t.segment_auto ? ' · اختيار آلي' : ''), 'wine') : pill('بلا فئة'); }
  function segSelect(t) {
    var E = ep();
    if (E && E.ensure) E.ensure('platformTopicSegments', null);
    var segs = window.PTOPIC_SEGMENTS || [];
    if (!segs.length) return '<select class="v2ct-sel" disabled><option>…جارٍ تحميل الفئات</option></select>';
    return '<select class="v2ct-sel" data-seg="' + esc(t.id) + '"><option value="">— اختر الفئة —</option>' + segs.map(function (s) {
      return '<option value="' + esc(s.id) + '"' + (t.segment === s.id ? ' selected' : '') + '>' + esc(s.label) + '</option>';
    }).join('') + '</select>';
  }
  function wireSeg(root, t) {
    qa('select[data-seg]', root).forEach(function (sel) {
      sel.onchange = function () {
        var a = sel.value; if (!a) return;
        sel.disabled = true;
        // مستثنى من التأكيد: تسمية داخلية للفئة لا تُظهر شيئًا للناس.
        perform(function (cb) { ep().setTopicSegment(t, a, cb); }, ['platformPendingTopics'], noErr, function (ok, err) {
          sel.disabled = false;
          var lbl = (window.PTOPIC_SEGMENTS || []).filter(function (x) { return x.id === a; })[0];
          if (ok) { t.segment = a; setNote('تمّ: أُسندت الفئة «' + ((lbl && lbl.label) || a) + '».'); }
          else errBox(root, 'لم يتم. ' + err);
        });
      };
    });
  }
  function topicChipList() {
    var pend = memberTopics(), tops = topicsList();
    return L.v2ContentTopicChips(tops === undefined ? null : tops, pend === undefined ? null : pend, topicsTabNow(), S.generating);
  }
  function topicsForChip(chip) {
    if (chip === 'pending') return memberTopics();
    var tops = topicsList();
    if (!Array.isArray(tops)) return tops;
    return tops.filter(function (t) { return L.v2ContentTopicTabOf(t) === chip; });
  }
  var TOPIC_MAIN = { pending: 'اعتمد وبلّغ', ideas: 'اعتمد للنقاش', incoming: 'اعتمد للنقاش', working: 'انشر على اللوحة', rejected: 'اعتمد بعد المراجعة', archived: 'أعد للأفكار' };
  function topicMainLabel(chip, t) { return chip === 'board' ? (t.linked_article_id ? 'افتح المقال' : 'اكتب منه مقالًا') : TOPIC_MAIN[chip]; }
  function drawTopics() {
    var chip = topicsTabNow();
    if (['pending', 'ideas', 'incoming', 'working', 'board', 'rejected', 'archived'].indexOf(chip) < 0) chip = 'pending';
    var chips = topicChipList();
    var chipHtml = chips.map(function (c) {
      var na = c.count === null;
      return '<button type="button" class="v2ct-chip' + (c.active ? ' on' : '') + '" data-a="tchip" data-v="' + c.key + '"' + (na ? ' title="' + NA + '"' : '') + '>' + esc(c.label) + ' <b>' + (na ? '—' : esc(ar(c.count))) + '</b></button>';
    }).join('');
    var list = topicsForChip(chip), strip = '';
    if (chip === 'pending' && list === null) strip = warnStrip(['موضوعات الأعضاء'], NA);
    var cats = {};
    (Array.isArray(list) ? list : []).forEach(function (t) { var c = t.category || t.specialty; if (c) cats[c] = 1; });
    var an = D('platformTopicsAnalysis');
    if (st('platformTopicsAnalysis') === 'ready' && an && Array.isArray(an.by_category)) an.by_category.forEach(function (c) { if (c.category) cats[c.category] = 1; });
    var catKeys = Object.keys(cats);
    var sel = '<div class="v2ct-catf"><label for="v2ctCat">التخصص</label><select id="v2ctCat" class="v2ct-sel" data-a="cat"><option value="all">كل التخصصات</option>'
      + catKeys.map(function (c) { return '<option value="' + esc(c) + '"' + (S.cat === c ? ' selected' : '') + '>' + esc(c) + '</option>'; }).join('') + '</select></div>';
    var brain = '';
    var pendN = memberTopics(), ideasN = topicsList();
    if (chip === 'pending' && Array.isArray(pendN)) brain = ar(pendN.length) + ' موضوعًا كتبه أعضاء، وهو مخفي عن اللوحة حتى تقرّر. القرار يصل إلى صاحبه.';
    else if (chip === 'ideas' && Array.isArray(ideasN)) brain = ar(topicsForChip('ideas').length) + ' فكرة. الاعتماد يضعها على اللوحة العامة، والرفض يحذفها.';
    else if (chip === 'archived' && Array.isArray(ideasN)) brain = 'موضوعات مؤرشفة لا تظهر للناس. أعدها إلى الأفكار أو احذفها.';
    else if (chip === 'board' && st('platformTopicsAnalysis') === 'ready') { var sg = L.v2ContentSegments(an); if (sg && sg.low) brain = 'أقل الفئات موضوعات: ' + sg.low.label + ' (' + ar(sg.low.count) + ').'; }
    var brainHtml = brain ? '<div class="v2ct-brain wide">' + BRAIN + '<p>' + esc(brain) + '</p></div>' : '';
    var body;
    if (list === undefined) body = loadingBlock('الموضوعات');
    else if (list === null) body = chip === 'pending' ? '' : unavailable('الموضوعات');
    else {
      var shown = list.filter(function (t) { return S.cat === 'all' || (t.category || t.specialty) === S.cat; });
      if (!shown.length) body = '<div class="v2ct-empty"><b>لا شيء هنا الآن</b></div>';
      else body = '<div class="v2ct-grid">' + shown.map(function (t) { return topicCard(chip, t); }).join('') + '</div>';
    }
    var wrapTop = '<div class="v2ct-bar"><button type="button" class="v2ct-b1 auto" data-a="newtopic">موضوع جديد</button></div>';
    return wrapTop + '<div class="v2ct-chips wrap">' + chipHtml + '</div>' + sel + strip + brainHtml + body + numbersCard();
  }
  function topicCard(chip, t) {
    var gen = !!S.generating[t.id], pills = '';
    if (chip !== 'pending') pills += pill(SRC_AR[t.source] || SRC_AR.human);
    var cat = t.category || t.specialty;
    if (cat) pills += pill(cat);
    pills += segLabelPill(t);
    if (t.linked_article_id) pills += pill('له مقال', 'green');
    var meta = [t.country, chip === 'board' && t.comments ? ar(t.comments) + ' تعليق معتمد' : '', t.date].filter(Boolean).join(' · ');
    var btn;
    if (gen) btn = '<p class="v2ct-status" role="status">جارٍ الكتابة…</p>';
    else btn = '<button type="button" class="v2ct-b1" data-a="tmain" data-id="' + esc(t.id) + '" data-chip="' + chip + '">' + esc(topicMainLabel(chip, t)) + '</button>';
    var lit = S.hl && String(S.hl.id) === String(t.id) && Date.now() < S.hl.until;
    return '<article class="v2ct-card topic' + (lit ? ' hl' : '') + '" data-id="t:' + esc(t.id) + '"><h3><button type="button" class="v2ct-open" data-a="topen" data-id="' + esc(t.id) + '" data-chip="' + chip + '">' + esc(t.title || 'موضوع بلا عنوان') + '</button></h3>'
      + '<p class="v2ct-pills">' + pills + '</p>' + (meta ? '<p class="v2ct-cm">' + esc(meta) + '</p>' : '') + '<div class="v2ct-acts">' + btn + '</div></article>';
  }
  function bars(list, labelKey, valueKey, max) {
    var top = Math.max.apply(null, list.map(function (x) { return isNum(x[valueKey]) ? x[valueKey] : 0; }).concat([1]));
    return '<ul class="v2ct-bars">' + list.slice(0, max || 8).map(function (x) {
      var v = isNum(x[valueKey]) ? x[valueKey] : 0;
      return '<li><div class="v2ct-bl"><span>' + esc(x[labelKey] || 'غير مصنّف') + '</span><b>' + esc(numTxt(x[valueKey])) + '</b></div><div class="v2ct-bar2"><i style="width:' + Math.round(v / top * 100) + '%"></i></div></li>';
    }).join('') + '</ul>';
  }
  function numbersCard() {
    var s0 = st('platformTopicsAnalysis'), an = D('platformTopicsAnalysis');
    var inner;
    if (s0 === 'error') inner = unavailable('أرقام الموضوعات');
    else if (s0 !== 'ready' || !an) inner = loadingBlock('أرقام الموضوعات');
    else {
      var tops = (an.top_topics || []).slice(0, 5);
      var sg = L.v2ContentSegments(an);
      inner = '<div class="v2ct-nums">' + numBox(an.total_topics, 'موضوعات') + numBox(an.total_comments, 'تعليقات معتمدة') + '</div>'
        + (tops.length ? '<h4>الأكثر تعليقًا</h4><ul class="v2ct-top">' + tops.map(function (t) {
          return '<li><b>' + esc(t.title) + '</b>' + pill(SRC_AR[t.source] || SRC_AR.human) + '<span>' + (t.engagement && isNum(t.engagement.comments) ? esc(ar(t.engagement.comments)) + ' تعليق' : 'التعليقات: ' + NA) + '</span></li>'; }).join('') + '</ul>' : '')
        + (sg ? '<h4>حسب الفئة المستهدفة</h4>' + bars(sg.lanes, 'label', 'count', 12) : '')
        + (an.by_category && an.by_category.length ? '<h4>حسب التخصص</h4>' + bars(an.by_category, 'category', 'count', 8) : '')
        + (an.categories_in_demand && an.categories_in_demand.length ? '<h4>ما يسأل عنه الناس في المحادثة</h4><div class="v2ct-pills">' + an.categories_in_demand.map(function (c) { return pill((c.category || c.name || '') + (isNum(c.count) ? ' · ' + ar(c.count) : '')); }).join('') + '</div>' : '');
    }
    return '<section class="v2ct-box"><header><h2>أرقام الموضوعات</h2><button type="button" class="v2ct-b2 sm" data-a="reloadNums">حدّث</button></header>' + inner + '</section>';
  }
  function findTopic(chip, id) {
    var l = topicsForChip(chip) || [];
    var t = l.filter(function (x) { return String(x.id) === String(id); })[0];
    if (!t) t = (topicsList() || []).filter(function (x) { return String(x.id) === String(id); })[0];
    return t || null;
  }
  // —— «موضوع جديد»
  function newTopicSheet() {
    var opts = ['human', 'idea', 'expert', 'news'].map(function (k) { return '<option value="' + k + '">' + SRC_AR[k] + '</option>'; }).join('');
    var s = openSheet('موضوع جديد', '<p class="v2ct-lead">يكتب النظام إجابة مقترحة كمسودة، ويستهلك ذلك من رصيد الكتابة الآلية. لا يُنشر شيء قبل اعتمادك.</p>'
      + '<div class="v2ct-fld"><label for="nt_t">العنوان</label><input id="nt_t" placeholder="مثال: حقوق العامل عند الفصل التعسّفي"></div>'
      + '<div class="v2ct-fld"><label for="nt_q">السؤال</label><textarea id="nt_q" rows="4" placeholder="اكتب السؤال القانوني بوضوح"></textarea></div>'
      + '<div class="v2ct-two"><div class="v2ct-fld"><label for="nt_sp">التخصص</label><input id="nt_sp" placeholder="مثال: قانون عمل"></div><div class="v2ct-fld"><label for="nt_src">المصدر</label><select id="nt_src">' + opts + '</select></div></div>'
      + '<div id="v2ctErr"></div><div class="v2ct-acts2"><button type="button" class="v2ct-b1" id="v2ctGo">احفظ واكتب الإجابة المقترحة</button><button type="button" class="v2ct-b2" id="v2ctNo">رجوع</button></div>');
    if (!s) return;
    q('#v2ctNo', s).onclick = closeSheet;
    var go = q('#v2ctGo', s);
    go.onclick = function () {
      var g = { title: q('#nt_t', s).value.trim(), question: q('#nt_q', s).value.trim(), specialty: q('#nt_sp', s).value.trim(), source: q('#nt_src', s).value };
      if (!g.title) { errBox(s, 'العنوان مطلوب'); return; }
      if (!g.question) { errBox(s, 'السؤال مطلوب'); return; }
      window.__v2ctConfirmAt = Date.now();        // هذه الورقة هي التأكيد: تسمّي الرصيد قبل الضغط
      go.disabled = true; go.textContent = 'جارٍ التنفيذ…'; s.dataset.busy = '1'; errBox(s, '');
      var before = (topicsList() || []).length;
      perform(function (cb) { ep().createTopic(g, cb); }, ['platformTopics'], function () { return noErr() && (topicsList() || []).length >= before; }, function (ok, err) {
        delete s.dataset.busy;
        if (ok) { closeSheet(); setNote('تمّ: أُنشئ الموضوع «' + g.title + '» وتُكتب إجابته المقترحة.'); redraw(); }
        else { go.disabled = false; go.textContent = 'احفظ واكتب الإجابة المقترحة'; errBox(s, 'لم يتم. ' + err); }
      });
    };
  }
  // —— إجراءات الموضوع (كلها بتأكيد إلا المستثنى)
  function approvePending(t) {
    confirmSheet({ title: 'اعتماد موضوع عضو', lead: 'سيظهر على اللوحة العامة، ويصل القرار إلى صاحبه.', okLabel: 'اعتمد وبلّغ', run: function (done) {
      perform(function (cb) { ep().decidePendingTopic(t, 'approve', cb); }, ['platformPendingTopics', 'platformTopics'], function () { return noErr() && !(window.PTOPICS_PENDING || []).some(function (x) { return x.id === t.id; }); },
        function (ok, err) { done({ ok: ok, error: err, note: 'تمّ: اعتُمد «' + t.title + '» وبُلّغ صاحبه.' }); });
    } });
  }
  function rejectPending(t) {
    confirmSheet({ title: 'رفض موضوع عضو', lead: 'لن يظهر على اللوحة، ويبقى محفوظًا بلا حذف.', okLabel: 'ارفض بلا حذف', danger: true, run: function (done) {
      perform(function (cb) { ep().decidePendingTopic(t, 'reject', cb); }, ['platformPendingTopics', 'platformTopics'], function () { return noErr() && !(window.PTOPICS_PENDING || []).some(function (x) { return x.id === t.id; }); },
        function (ok, err) { done({ ok: ok, error: err, note: 'تمّ: رُفض «' + t.title + '» بلا حذف.' }); });
    } });
  }
  function approveToBoard(t, lead) {
    confirmSheet({ title: 'اعتماد للنقاش', lead: lead || 'سيظهر على اللوحة العامة.', okLabel: 'اعتمد للنقاش', run: function (done) {
      perform(function (cb) { ep().updateTopic(t.id, { title: t.title, status: 'open' }, cb); }, ['platformTopics'], function () { return noErr() && topicStatus(t.id) === 'open'; },
        function (ok, err) { done({ ok: ok, error: err, note: 'تمّ: اعتُمد «' + t.title + '» على اللوحة.' }); });
    } });
  }
  function topicStatus(id) { var t = (topicsList() || []).filter(function (x) { return x.id === id; })[0]; return t ? t.status : ''; }
  function publishToBoard(t) {
    confirmSheet({ title: 'نشر على اللوحة', lead: 'سيظهر على اللوحة العامة بنصه الحالي.', okLabel: 'انشر على اللوحة', run: function (done) {
      perform(function (cb) { ep().publishTopic(t, cb); }, ['platformTopics'], function () { return noErr() && ['published', 'open'].indexOf(topicStatus(t.id)) > -1; },
        function (ok, err) { done({ ok: ok, error: err, note: 'تمّ: نُشر «' + t.title + '» على اللوحة.' }); });
    } });
  }
  function deleteTopic(t, lead) {
    confirmSheet({ title: 'حذف الموضوع', lead: lead || 'سيُحذف الموضوع نهائيًا.', okLabel: 'احذف', danger: true, run: function (done) {
      perform(function (cb) { ep().deleteTopic(t, cb); }, ['platformTopics'], function () { return noErr() && !(topicsList() || []).some(function (x) { return x.id === t.id; }); },
        function (ok, err) { done({ ok: ok, error: err, note: 'تمّ: حُذف الموضوع.' }); });
    } });
  }
  function openLinkedArticle(t) {
    if (!t.linked_article_id) { setNote('لا مقال مرتبط بهذا الموضوع'); redraw(); return; }
    S.openArticle = t.linked_article_id;
    window.v2OpenSection('content', 'articles', { st: { topicsTab: 'articles' } });
  }
  function makeArticle(t) {
    var linked = !!t.linked_article_id;
    confirmSheet({ title: 'اكتب منه مقالًا', okLabel: 'ابدأ الكتابة',
      lead: linked ? 'لهذا الموضوع مقال بالفعل. تكتب مقالًا آخر؟ يستهلك ذلك من رصيد الكتابة الآلية.'
                   : 'يكتب النظام مقالًا جديدًا مبنيًا على هذا الموضوع، ولا ينسخ نصه، ويستهلك ذلك من رصيد الكتابة الآلية. يظهر مسودة في «المقالات» لتقرأها ثم تنشرها.',
      run: function (done) {
        var E = ep();
        S.generating[t.id] = Date.now();
        done({ ok: true });
        E.lastError = '';
        E.generateArticleFromTopic(t, function (ok, newId, msg) {
          delete S.generating[t.id];
          if (ok) {
            var go = function () {
              S.openArticle = newId;
              setNote('تمّ: كُتب مقال من «' + t.title + '». اقرأه ثم انشره.');
              if (isCurrent()) window.v2OpenSection('content', 'articles', { st: { topicsTab: 'articles' } });
            };
            if (newId != null) {
              var fired = false;
              E.markTopicArticled(t, newId, function () { if (fired || E.state.platformTopics === 'loading') return; fired = true; go(); });
              setTimeout(function () { if (!fired) { fired = true; go(); } }, 15000);
            } else go();
          } else if (isCurrent()) {
            redraw();
            makeArticleFailed(t, msg);
          }
        });
        redraw();
      } });
  }
  function makeArticleFailed(t, msg) {
    var s = openSheet('تعذّر كتابة المقال', '<div class="v2ct-err big"><b>لم يُنشأ أي مقال، والموضوع بقي كما هو.</b><br>' + esc(arDigits(msg || '')) + '</div>'
      + '<div class="v2ct-acts2"><button type="button" class="v2ct-b1" id="v2ctRetry">أعد المحاولة</button><button type="button" class="v2ct-b2" id="v2ctNo">إغلاق</button></div>');
    if (!s) return;
    q('#v2ctNo', s).onclick = closeSheet;
    q('#v2ctRetry', s).onclick = function () { closeSheet(); makeArticle(t); };
  }
  function topicMain(chip, t) {
    if (chip === 'pending') return approvePending(t);
    if (chip === 'ideas' || chip === 'incoming') return approveToBoard(t);
    if (chip === 'working') return (t.merged_article || t.ai_answer) ? publishToBoard(t) : openTopicSheet(chip, t);
    if (chip === 'board') return t.linked_article_id ? openLinkedArticle(t) : makeArticle(t);
    if (chip === 'rejected') return approveRejected(t);
    if (chip === 'archived') return restoreArchived(t);
  }
  function restoreArchived(t) {
    confirmSheet({ title: 'إعادة الموضوع للأفكار', lead: 'يعود الموضوع إلى قائمة الأفكار، ولا يظهر للناس قبل اعتمادك.', okLabel: 'أعده للأفكار', run: function (done) {
      perform(function (cb) { ep().updateTopic(t.id, { title: t.title, status: 'draft' }, cb); }, ['platformTopics'], function () { return noErr() && topicStatus(t.id) === 'draft'; },
        function (ok, err) { done({ ok: ok, error: err, note: 'تمّ: عاد «' + t.title + '» إلى الأفكار.' }); });
    } });
  }
  function approveRejected(t) {
    confirmSheet({ title: 'اعتماد بعد المراجعة', lead: 'سيظهر على اللوحة العامة، ويصل القرار إلى صاحبه.', okLabel: 'اعتمد بعد المراجعة', run: function (done) {
      perform(function (cb) { ep().decidePendingTopic(t, 'approve', cb); }, ['platformPendingTopics', 'platformTopics'], function () { return noErr() && topicStatus(t.id) !== 'rejected'; },
        function (ok, err) { done({ ok: ok, error: err, note: 'تمّ: اعتُمد «' + t.title + '» وبُلّغ صاحبه.' }); });
    } });
  }
  // —— ورقة الموضوع
  function openTopicSheet(chip, t) {
    var s;
    if (chip === 'pending') {
      s = openSheet('موضوع من عضو', '<div class="v2ct-fld"><label>العنوان</label><p class="v2ct-val">' + esc(t.title || '—') + '</p></div>'
        + '<div class="v2ct-fld"><label>السؤال أو النص</label><p class="v2ct-val pre">' + esc(t.question || '—') + '</p></div>'
        + '<div class="v2ct-fld"><label>التخصص</label><p class="v2ct-val">' + esc(t.category || t.specialty || 'غير مصنّف') + '</p></div>'
        + '<div class="v2ct-fld"><label>الفئة المستهدفة (تُحفظ فور الاختيار)</label>' + segSelect(t) + '</div>'
        + '<p class="v2ct-fine">صاحب الموضوع محفوظ على المنصة ولا يظهر على اللوحة.</p><div id="v2ctErr"></div>'
        + '<div class="v2ct-acts2"><button type="button" class="v2ct-b1" id="v2ctOk">اعتمد وانشر وبلّغ صاحبه</button><button type="button" class="v2ct-b2" id="v2ctNoGo">ارفض بلا حذف</button><button type="button" class="v2ct-b2" id="v2ctNo">إغلاق</button></div>');
      if (!s) return;
      wireSeg(s, t);
      q('#v2ctNo', s).onclick = closeSheet;
      q('#v2ctOk', s).onclick = function () { closeSheet(); approvePending(t); };
      q('#v2ctNoGo', s).onclick = function () { closeSheet(); rejectPending(t); };
      return;
    }
    var onBoard = ['open', 'published'].indexOf(t.status) > -1;
    var stOpts = ['draft', 'open', 'merged', 'published'].map(function (k) { return '<option value="' + k + '"' + (t.status === k ? ' selected' : '') + '>' + STATUS_AR[k] + '</option>'; }).join('');
    var srcOpts = ['human', 'idea', 'expert', 'news'].map(function (k) { return '<option value="' + k + '"' + (t.source === k ? ' selected' : '') + '>' + SRC_AR[k] + '</option>'; }).join('');
    var main, others = '';
    if (chip === 'ideas' || chip === 'incoming') { main = '<button type="button" class="v2ct-b1" id="v2ctMain">اعتمد للنقاش</button>'; if (chip === 'incoming') others += '<button type="button" class="v2ct-b2" id="v2ctToWrite">حوّله للكتابة</button>'; }
    else if (chip === 'working') { main = '<button type="button" class="v2ct-b1" id="v2ctMain">انشر على اللوحة</button>'; others += (t.linked_article_id ? '<button type="button" class="v2ct-b2" id="v2ctArt">افتح المقال</button>' : '') + '<button type="button" class="v2ct-b2" id="v2ctMk">اكتب منه مقالًا</button>'; }
    else if (chip === 'archived') main = '<button type="button" class="v2ct-b1" id="v2ctMain">أعد للأفكار</button>';
    else if (chip === 'board') { main = t.linked_article_id ? '<button type="button" class="v2ct-b1" id="v2ctArt">افتح المقال</button>' : '<button type="button" class="v2ct-b1" id="v2ctMk">اكتب منه مقالًا</button>'; if (t.linked_article_id) others += '<button type="button" class="v2ct-b2" id="v2ctMk">اكتب منه مقالًا</button>'; }
    else main = '<button type="button" class="v2ct-b1" id="v2ctMain">اعتمد بعد المراجعة</button>';
    var isRej = chip === 'rejected' || chip === 'archived';
    s = openSheet('مراجعة الموضوع', (isRej ? '<div class="v2ct-fld"><label>العنوان</label><p class="v2ct-val">' + esc(t.title) + '</p></div><div class="v2ct-fld"><label>السؤال</label><p class="v2ct-val pre">' + esc(t.question || '—') + '</p></div>' :
      '<div class="v2ct-fld"><label for="tr_t">العنوان</label><input id="tr_t" value="' + esc(t.title) + '"></div>'
      + '<div class="v2ct-two"><div class="v2ct-fld"><label for="tr_sp">التخصص</label><input id="tr_sp" value="' + esc(t.category || t.specialty || '') + '"></div>'
      + '<div class="v2ct-fld"><label for="tr_src">المصدر</label><select id="tr_src">' + srcOpts + '</select></div></div>'
      + '<div class="v2ct-fld"><label>الفئة المستهدفة (تُحفظ فور الاختيار)</label>' + segSelect(t) + '</div>'
      + '<div class="v2ct-fld"><label for="tr_st">الحالة</label><select id="tr_st">' + stOpts + '</select></div>'
      + '<div class="v2ct-fld"><label for="tr_q">السؤال</label><textarea id="tr_q" rows="3">' + esc(t.question || '') + '</textarea></div>'
      + '<div class="v2ct-fld"><label for="tr_ai">الإجابة المقترحة</label><textarea id="tr_ai" rows="7" placeholder="لم تُكتب إجابة مقترحة بعد">' + esc(t.ai_answer || '') + '</textarea></div>'
      + (t.merged_article ? '<div class="v2ct-fld"><label for="tr_mg">النص المدموج</label><textarea id="tr_mg" rows="6">' + esc(t.merged_article) + '</textarea></div>' : ''))
      + '<div id="v2ctErr"></div><div class="v2ct-acts2">' + main
      + (isRej ? '' : '<button type="button" class="v2ct-b2" id="v2ctSave">احفظ التعديلات</button>') + others
      + '<button type="button" class="v2ct-b3" id="v2ctDel">' + (isRej ? 'احذف نهائيًا' : 'احذف') + '</button><button type="button" class="v2ct-b2" id="v2ctNo">إغلاق</button></div>', true);
    if (!s) return;
    wireSeg(s, t);
    q('#v2ctNo', s).onclick = closeSheet;
    var bind = function (sel, fn) { var b = q(sel, s); if (b) b.onclick = function () { closeSheet(); fn(); }; };
    bind('#v2ctMain', function () {
      if (chip === 'working') publishToBoard(t); else if (chip === 'archived') restoreArchived(t); else if (isRej) approveRejected(t); else approveToBoard(t);
    });
    bind('#v2ctToWrite', function () {
      // مستثنى من التأكيد: نقل داخلي إلى قائمة الكتابة، لا يظهر منه شيء للناس.
      perform(function (cb) { ep().updateTopic(t.id, { title: t.title, status: 'merged' }, cb); }, ['platformTopics'], function () { return noErr() && topicStatus(t.id) === 'merged'; },
        function (ok, err) { setNote(ok ? 'تمّ: حُوّل «' + t.title + '» إلى قائمة الكتابة.' : 'لم يتم. ' + err); redraw(); });
    });
    bind('#v2ctMk', function () { makeArticle(t); });
    bind('#v2ctArt', function () { openLinkedArticle(t); });
    bind('#v2ctDel', function () { deleteTopic(t, isRej ? 'سيُحذف الموضوع نهائيًا.' : 'سيُحذف الموضوع نهائيًا.'); });
    var sv = q('#v2ctSave', s);
    if (sv) sv.onclick = function () {
      var g = { title: q('#tr_t', s).value.trim(), specialty: q('#tr_sp', s).value.trim(), question: q('#tr_q', s).value.trim(), ai_answer: q('#tr_ai', s).value,
                source: q('#tr_src', s).value, status: q('#tr_st', s).value };
      var mg = q('#tr_mg', s); if (mg) g.merged_article = mg.value;
      if (!g.title) { errBox(s, 'العنوان مطلوب'); return; }
      var toBoard = onBoard || ['open', 'published'].indexOf(g.status) > -1;
      var run = function (done) {
        perform(function (cb) { ep().updateTopic(t.id, g, cb); }, ['platformTopics'], noErr, function (ok, err) { done({ ok: ok, error: err, note: 'تمّ: حُفظت تعديلات «' + g.title + '».' }); });
      };
      if (toBoard) { inlineConfirm(s, { lead: 'يظهر التعديل على اللوحة العامة فور الحفظ.', okLabel: 'احفظ التعديلات', run: run }); }
      else {
        sv.disabled = true; sv.textContent = 'جارٍ الحفظ…';
        run(function (res) { if (res.ok) { closeSheet(); setNote(res.note); redraw(); } else { sv.disabled = false; sv.textContent = 'احفظ التعديلات'; errBox(s, 'لم يتم. ' + res.error); } });
      }
    };
  }

  // ================================================================== ٤) الأخبار
  function drawNews() {
    var list = newsList();
    var drafts = Array.isArray(list) ? list.filter(function (n) { return n.status !== 'published'; }) : [], pubs = Array.isArray(list) ? list.filter(function (n) { return n.status === 'published'; }) : [];
    var f = S.nfilter;
    var chips = '<div class="v2ct-chips">' + [['draft', 'مسودات (' + ar(drafts.length) + ')'], ['published', 'منشورة (' + ar(pubs.length) + ')'], ['all', 'الكل']].map(function (c) {
      return '<button type="button" class="v2ct-chip' + (f === c[0] ? ' on' : '') + '" data-a="nfilter" data-v="' + c[0] + '">' + esc(c[1]) + '</button>'; }).join('') + '</div>';
    var bar = '<div class="v2ct-bar"><button type="button" class="v2ct-b1 auto" data-a="newnews">خبر جديد</button><button type="button" class="v2ct-b2" data-a="nsources">مصادر الأخبار</button></div>';
    var body;
    if (list === undefined) body = loadingBlock('الأخبار');
    else if (list === null) body = unavailable('الأخبار');
    else {
      var shown = f === 'draft' ? drafts : f === 'published' ? pubs : list;
      if (!shown.length) body = '<div class="v2ct-empty"><b>' + (f === 'draft' ? 'لا مسودات أخبار الآن' : 'لا أخبار هنا') + '</b></div>';
      else body = '<div class="v2ct-grid">' + shown.map(newsCard).join('') + '</div>';
    }
    return bar + chips + body;
  }
  function newsCard(n) {
    var srcs = (n.sources || []).length ? (n.sources || []).map(function (s) { return safeLink(s.url, s.title || s.url, 'v2ct-src') || '<span class="v2ct-src">' + esc(s.title || s.url) + '</span>'; }).join(' ') : '<span class="v2ct-mute">بلا مصدر</span>';
    var pub = n.status === 'published', complete = (n.sources || []).length >= 1 && !!String(n.summary || '').trim();
    var label = pub ? 'عدّل' : (complete ? 'انشر' : 'أكمل الخبر');
    return '<article class="v2ct-card news" data-id="n:' + esc(n.id) + '"><h3><button type="button" class="v2ct-open" data-a="nopen" data-id="' + esc(n.id) + '">' + esc(n.title) + '</button></h3>'
      + '<p class="v2ct-pills">' + pill('خبر') + (n.specialty ? pill(n.specialty) : '') + pill(pub ? 'منشور' : 'مسودة', pub ? 'green' : 'amber') + '</p>'
      + '<p class="v2ct-sum">' + esc(String(n.summary || '').trim() || 'بلا ملخص بعد') + '</p><p class="v2ct-srcs">' + srcs + '</p>'
      + '<p class="v2ct-cm">' + esc([n.country, n.date].filter(Boolean).join(' · ')) + '</p>'
      + '<div class="v2ct-acts"><button type="button" class="v2ct-b1" data-a="nmain" data-id="' + esc(n.id) + '">' + esc(label) + '</button></div></article>';
  }
  function newsById(id) { return (newsList() || []).filter(function (n) { return String(n.id) === String(id); })[0] || null; }
  function publishNews(n) {
    confirmSheet({ title: 'نشر الخبر', lead: 'سيظهر الخبر للأعضاء على المنصة.', okLabel: 'انشر الخبر', run: function (done) {
      perform(function (cb) { ep().updateNews(n.id, { title: n.title, is_published: true }, cb); }, ['platformNews'], function () { var x = newsById(n.id); return noErr() && !!x && x.status === 'published'; },
        function (ok, err) { done({ ok: ok, error: err, note: 'تمّ: نُشر الخبر «' + n.title + '».' }); });
    } });
  }
  function newsSheet(edit) {
    var e = edit || {};
    var srcText = (e.sources || []).map(function (s) { return s.url + (s.title && s.title !== s.url ? ' | ' + s.title : ''); }).join('\n');
    var isPub = e.status === 'published';
    var s = openSheet(edit ? 'تعديل خبر' : 'خبر جديد', '<div class="v2ct-fld"><label for="nw_t">العنوان</label><input id="nw_t" value="' + esc(e.title || '') + '"></div>'
      + '<div class="v2ct-fld"><label for="nw_sum">الملخص (بصوت البروفيسور، ويظهر للأعضاء)</label><textarea id="nw_sum" rows="5">' + esc(e.summary || '') + '</textarea></div>'
      + '<div class="v2ct-two"><div class="v2ct-fld"><label for="nw_cty">الدولة</label><input id="nw_cty" value="' + esc(e.country || '') + '" placeholder="مصر"></div>'
      + '<div class="v2ct-fld"><label for="nw_sp">التخصص</label><input id="nw_sp" value="' + esc(e.specialty || '') + '" placeholder="قانون عمل"></div></div>'
      + '<div class="v2ct-fld"><label for="nw_src">روابط المصادر (سطر لكل مصدر: الرابط | الاسم)</label><textarea id="nw_src" rows="3" dir="ltr" placeholder="https://example.com/news | جريدة رسمية">' + esc(srcText) + '</textarea></div>'
      + '<label class="v2ct-chk"><input id="nw_pub" type="checkbox"' + (isPub ? ' checked' : '') + '> منشور (ظاهر للأعضاء)</label><div id="v2ctErr"></div>'
      + '<div class="v2ct-acts2"><button type="button" class="v2ct-b1" id="v2ctSave">احفظ</button>'
      + (edit ? '<button type="button" class="v2ct-b2" id="v2ctDerive">حوّله لموضوع</button>' + (isPub ? '<button type="button" class="v2ct-b2" id="v2ctUnpub">أوقف النشر</button>' : '') + '<button type="button" class="v2ct-b3" id="v2ctDel">احذف</button>' : '')
      + '<button type="button" class="v2ct-b2" id="v2ctNo">رجوع</button></div>', true);
    if (!s) return;
    q('#v2ctNo', s).onclick = closeSheet;
    q('#v2ctSave', s).onclick = function () {
      var sources = q('#nw_src', s).value.split('\n').map(function (ln) {
        ln = ln.trim(); if (!ln) return null; var p = ln.split('|'); var url = (p[0] || '').trim(), title = (p[1] || '').trim(); return url ? { url: url, title: title || url } : null;
      }).filter(Boolean);
      var g = { title: q('#nw_t', s).value.trim(), summary: q('#nw_sum', s).value.trim(), country: q('#nw_cty', s).value.trim(), specialty: q('#nw_sp', s).value.trim(), sources: sources, is_published: q('#nw_pub', s).checked };
      if (!g.title) { errBox(s, 'العنوان مطلوب'); return; }
      var run = function (done) {
        perform(function (cb) { if (edit && edit.id) ep().updateNews(edit.id, g, cb); else ep().createNews(g, cb); }, ['platformNews'], noErr,
          function (ok, err) { done({ ok: ok, error: err, note: 'تمّ: حُفظ الخبر «' + g.title + '».' }); });
      };
      if (g.is_published) { inlineConfirm(s, { lead: 'سيظهر الخبر للأعضاء على المنصة.', okLabel: 'احفظ وانشر', run: run }); }
      else {
        var sb = q('#v2ctSave', s); sb.disabled = true; sb.textContent = 'جارٍ الحفظ…';
        run(function (res) { if (res.ok) { closeSheet(); setNote(res.note); redraw(); } else { sb.disabled = false; sb.textContent = 'احفظ'; errBox(s, 'لم يتم. ' + res.error); } });
      }
    };
    if (!edit) return;
    var bind = function (sel, fn) { var b = q(sel, s); if (b) b.onclick = function () { closeSheet(); fn(); }; };
    bind('#v2ctUnpub', function () {
      confirmSheet({ title: 'إيقاف نشر الخبر', lead: 'سيختفي الخبر من المنصة.', okLabel: 'أوقف النشر', danger: true, run: function (done) {
        perform(function (cb) { ep().updateNews(edit.id, { title: edit.title, is_published: false }, cb); }, ['platformNews'], function () { var x = newsById(edit.id); return noErr() && !!x && x.status !== 'published'; },
          function (ok, err) { done({ ok: ok, error: err, note: 'تمّ: أُوقف نشر الخبر.' }); });
      } });
    });
    bind('#v2ctDel', function () {
      confirmSheet({ title: 'حذف الخبر', lead: 'سيُحذف الخبر نهائيًا.', okLabel: 'احذف', danger: true, run: function (done) {
        perform(function (cb) { ep().deleteNews(edit, cb); }, ['platformNews'], function () { return noErr() && !newsById(edit.id); }, function (ok, err) { done({ ok: ok, error: err, note: 'تمّ: حُذف الخبر.' }); });
      } });
    });
    bind('#v2ctDerive', function () {
      confirmSheet({ title: 'تحويل لموضوع', lead: 'يصبح الخبر موضوع نقاش على اللوحة.', okLabel: 'حوّله لموضوع', run: function (done) {
        var E = ep(), fin = false; E.lastError = '';
        E.deriveTopicFromNews(edit, function (topic, newId) {
          if (fin) return; fin = true;
          if (!topic) { done({ ok: false, error: E.lastError || 'تعذّر التحويل لموضوع' }); return; }
          var id = newId || topic.id, found = (topicsList() || []).filter(function (x) { return x.id === id; })[0] || topic;
          done({ ok: true, silent: true, note: 'تمّ: صار الخبر موضوعًا.' });
          S.highlight = id; S.cat = 'all';
          window.v2OpenSection('content', 'topics', { replace: true, st: { topicsTab: L.v2ContentTopicTabOf(found) } });
        });
      } });
    });
  }
  function sourcesSheet() {
    var src = (D('platformNewsSources')) || { feeds: [], club_keywords: {} };
    var feedsText = (src.feeds || []).map(function (f) { return (f.country || '') + ' | ' + (f.url || ''); }).join('\n');
    var ck = src.club_keywords || {};
    var ckText = Object.keys(ck).map(function (c) { var kw = ck[c]; return c + ' : ' + (Array.isArray(kw) ? kw.join('، ') : kw); }).join('\n');
    var s = openSheet('مصادر الأخبار', '<div class="v2ct-fld"><label for="ns_feeds">مصادر الأخبار (سطر لكل مصدر: الدولة | الرابط)</label><textarea id="ns_feeds" rows="6" dir="ltr">' + esc(feedsText) + '</textarea></div>'
      + '<div class="v2ct-fld"><label for="ns_ck">كلمات التصنيف (سطر لكل مجموعة: الاسم : كلمة، كلمة)</label><textarea id="ns_ck" rows="5">' + esc(ckText) + '</textarea></div><div id="v2ctErr"></div>'
      + '<div class="v2ct-acts2"><button type="button" class="v2ct-b1" id="v2ctSave">احفظ</button><button type="button" class="v2ct-b2" id="v2ctNo">رجوع</button></div>');
    if (!s) return;
    q('#v2ctNo', s).onclick = closeSheet;
    q('#v2ctSave', s).onclick = function () {
      var feeds = q('#ns_feeds', s).value.split('\n').map(function (ln) { ln = ln.trim(); if (!ln) return null; var p = ln.split('|'); var url = (p[1] || '').trim(); return url ? { country: (p[0] || '').trim(), url: url } : null; }).filter(Boolean);
      var club = {};
      q('#ns_ck', s).value.split('\n').forEach(function (ln) { ln = ln.trim(); if (!ln) return; var i = ln.indexOf(':'); if (i < 0) return; var c = ln.slice(0, i).trim(), kw = ln.slice(i + 1).split(/[،,]/).map(function (k) { return k.trim(); }).filter(Boolean); if (c) club[c] = kw; });
      var sb = q('#v2ctSave', s); sb.disabled = true; sb.textContent = 'جارٍ الحفظ…';
      // مستثنى من التأكيد: إعدادات داخلية لمصادر الجلب، لا يظهر منها شيء للناس.
      perform(function (cb) { ep().saveNewsSources({ feeds: feeds, club_keywords: club }, cb); }, ['platformNewsSources'], noErr, function (ok, err) {
        if (ok) { closeSheet(); setNote('تمّ: حُفظت مصادر الأخبار.'); redraw(); } else { sb.disabled = false; sb.textContent = 'احفظ'; errBox(s, 'لم يتم. ' + err); }
      });
    };
  }

  // ================================================================== ٥) التعليقات
  function verdictOf(o) { return L.v2ContentCommentVerdict(o.moderation); }
  function commentRow(o) {
    var v = verdictOf(o), sg = L.v2ContentSuggest({ kind: 'comment', moderation: o.moderation });
    return '<article class="v2ct-row" data-id="o:' + esc(o.id) + '"><button type="button" class="v2ct-rowbody" data-a="copen" data-id="' + esc(o.id) + '"><span class="v2ct-body3">' + esc(o.body) + '</span>'
      + '<span class="v2ct-cm">على: ' + esc(o.topic_title || 'موضوع') + ' · ' + esc(o.date || '') + '</span></button>'
      + '<p class="v2ct-cm">' + emailLink(o.author_email) + '</p><div class="v2ct-brain">' + BRAIN + '<p>' + esc(v.text) + '</p></div>'
      + '<div class="v2ct-acts"><button type="button" class="v2ct-b1' + (sg.act === 'rejectComment' ? ' ink' : '') + '" data-a="cmain" data-id="' + esc(o.id) + '">' + esc(sg.label) + '</button></div></article>';
  }
  function approvedRow(o) {
    var reply = o.editor_reply ? '<div class="v2ct-reply"><b>ردّ ' + esc(o.editor_reply_by || 'هيئة التحرير') + '</b><p>' + esc(o.editor_reply) + '</p></div>' : '';
    return '<article class="v2ct-row" data-id="a:' + esc(o.id) + '"><span class="v2ct-body3">' + esc(o.body) + '</span><span class="v2ct-cm">على: ' + esc(o.topic_title || 'موضوع') + ' · ' + esc(o.date || '') + '</span>'
      + '<p class="v2ct-cm">' + emailLink(o.author_email) + '</p>' + reply
      + '<div class="v2ct-acts"><button type="button" class="v2ct-b1" data-a="creply" data-id="' + esc(o.id) + '">' + (o.editor_reply ? 'عدّل الرد' : 'ردّ') + '</button></div></article>';
  }
  function drawComments() {
    var pend = commentsList(), appr = approvedList();
    var c1, c2;
    if (pend === undefined) c1 = loadingBlock('التعليقات'); else if (pend === null) c1 = unavailable('التعليقات');
    else c1 = pend.length ? '<div class="v2ct-stack">' + pend.map(commentRow).join('') + '</div>' : '<div class="v2ct-empty"><b>لا تعليقات تنتظر قرارك. التعليق المطابق للموضوع يُعتمد تلقائيًا، والمشكوك فيه فقط يصل هنا.</b></div>';
    if (appr === undefined) c2 = loadingBlock('التعليقات المعتمدة'); else if (appr === null) c2 = unavailable('التعليقات المعتمدة');
    else c2 = appr.length ? '<div class="v2ct-stack">' + appr.slice(0, 30).map(approvedRow).join('') + '</div>' : '<p class="v2ct-none">لا تعليقات ظاهرة بعد</p>';
    return '<div class="v2ct-narrow wide">' + box('تنتظر قرارك', pend ? ar(pend.length) : '', c1) + box('ظاهرة الآن', appr ? ar(appr.length) : '', c2) + numbersComments() + '</div>';
  }
  function box(title, n, inner) { return '<section class="v2ct-box"><header><h2>' + esc(title) + '</h2>' + (n !== '' ? '<span class="v2ct-n">' + esc(n) + '</span>' : '') + '</header>' + inner + '</section>'; }
  function numbersComments() {
    var s0 = st('platformOpinionsNumbers'), an = D('platformOpinionsNumbers'), inner;
    if (s0 === 'error') inner = unavailable('أرقام التعليقات');
    else if (s0 !== 'ready' || !an) inner = loadingBlock('أرقام التعليقات');
    else {
      var sc = an.status_counts || {}, tops = (an.top_topics || []).slice(0, 5);
      inner = '<div class="v2ct-nums">' + numBox(sc.pending, 'تنتظر') + numBox(sc.approved, 'معتمدة') + numBox(sc.rejected, 'مرفوضة') + '</div>'
        + (tops.length ? '<h4>الأكثر تعليقًا</h4><ul class="v2ct-top">' + tops.map(function (t) { return '<li><b>' + esc(t.title) + '</b><span>' + (isNum(t.count) ? esc(ar(t.count)) + ' تعليق' : 'التعليقات: ' + NA) + '</span></li>'; }).join('') + '</ul>' : '')
        + (an.by_category && an.by_category.length ? '<h4>حسب التخصص</h4>' + bars(an.by_category, 'category', 'count', 8) : '')
        + (S.summary ? '<div class="v2ct-sumbox"><h4>خلاصة مكتوبة آليًا من آخر التعليقات المعتمدة</h4><p>' + esc(S.summary.insights || S.summary.note || '') + '</p></div>' : '')
        + '<div class="v2ct-acts"><button type="button" class="v2ct-b2" data-a="csummary">اكتب خلاصة</button></div>';
    }
    return '<section class="v2ct-box"><header><h2>أرقام التعليقات</h2></header>' + inner + '</section>';
  }
  function opinionById(id) { return (commentsList() || []).filter(function (o) { return o.id === id; })[0] || null; }
  function approvedById(id) { return (approvedList() || []).filter(function (o) { return o.id === id; })[0] || null; }
  function gone(listFn, id) { return !(listFn() || []).some(function (o) { return o.id === id; }); }
  function rejectOpinion(o) {
    confirmSheet({ title: 'رفض التعليق', lead: 'لن يظهر التعليق على المنصة.', okLabel: 'ارفض', danger: true, run: function (done) {
      perform(function (cb) { ep().rejectOpinion(o, cb); }, ['platformOpinions'], function () { return noErr() && gone(commentsList, o.id); },
        function (ok, err) { done({ ok: ok, error: err, note: 'تمّ: رُفض التعليق.' }); });
    } });
  }
  function approveOpinion(o) {
    confirmSheet({ title: 'اعتماد التعليق', lead: 'سيظهر التعليق للجميع تحت الموضوع.', okLabel: 'اعتمد', run: function (done) {
      perform(function (cb) { ep().approveOpinion(o, cb); }, ['platformOpinions'], function () { return noErr() && gone(commentsList, o.id); },
        function (ok, err) { if (ok) afterWrite(['platformOpinionsApproved', 'platformOpinionsNumbers']); done({ ok: ok, error: err, note: 'تمّ: اعتُمد التعليق.' }); });
    } });
  }
  function deleteOpinion(o) {
    confirmSheet({ title: 'حذف التعليق', lead: 'يُحذف التعليق من المنصة نهائيًا.', okLabel: 'احذف نهائيًا', danger: true, run: function (done) {
      perform(function (cb) { ep().deleteOpinion(o, cb); }, ['platformOpinions', 'platformOpinionsApproved'], function () { return noErr() && gone(commentsList, o.id) && gone(approvedList, o.id); },
        function (ok, err) { if (ok) afterWrite(['platformOpinionsNumbers']); done({ ok: ok, error: err, note: 'تمّ: حُذف التعليق.' }); });
    } });
  }
  function commentSheet(o) {
    var v = verdictOf(o), mod = o.moderation || {}, rejFirst = v.suggest === 'reject';
    var okB = '<button type="button" class="v2ct-b' + (rejFirst ? '2' : '1') + '" id="v2ctOk">اعتمد</button>', noB = '<button type="button" class="v2ct-b' + (rejFirst ? '1 ink' : '2') + '" id="v2ctRej">ارفض</button>';
    var s = openSheet('تعليق ينتظر قرارك', '<p class="v2ct-val pre">' + esc(o.body) + '</p><p class="v2ct-cm">على: ' + esc(o.topic_title || 'موضوع') + ' · ' + emailLink(o.author_email) + ' · ' + esc(o.date || '') + '</p>'
      + '<div class="v2ct-brain">' + BRAIN + '<p>' + esc(v.text) + '</p></div>' + (mod.reason ? '<p class="v2ct-line">سبب الفحص الآلي: ' + esc(mod.reason) + '</p>' : '')
      + '<div class="v2ct-acts2">' + (rejFirst ? noB + okB : okB + noB) + '<button type="button" class="v2ct-b3" id="v2ctDel">احذف نهائيًا</button></div>');
    if (!s) return;
    var bind = function (sel, fn) { var b = q(sel, s); if (b) b.onclick = function () { closeSheet(); fn(); }; };
    bind('#v2ctOk', function () { approveOpinion(o); });
    bind('#v2ctRej', function () { rejectOpinion(o); });
    bind('#v2ctDel', function () { deleteOpinion(o); });
  }
  function replySheet(o) {
    var s = openSheet('ردّ هيئة التحرير', '<p class="v2ct-lead">يظهر الرد للجميع تحت التعليق باسم هيئة التحرير.</p><p class="v2ct-val pre">' + esc(o.body) + '</p>'
      + '<div class="v2ct-fld"><label for="rp_t">اكتب ردّ هيئة التحرير</label><textarea id="rp_t" rows="5">' + esc(o.editor_reply || '') + '</textarea></div><div id="v2ctErr"></div>'
      + '<div class="v2ct-acts2"><button type="button" class="v2ct-b1" id="v2ctGo">انشر الرد</button>' + (o.editor_reply ? '' : '<button type="button" class="v2ct-b2" id="v2ctAi">اكتب ردًّا آليًا</button>')
      + '<button type="button" class="v2ct-b3" id="v2ctDel">احذف التعليق</button><button type="button" class="v2ct-b2" id="v2ctNo">رجوع</button></div>');
    if (!s) return;
    q('#v2ctNo', s).onclick = closeSheet;
    var go = q('#v2ctGo', s);
    go.onclick = function () {
      var text = q('#rp_t', s).value.trim();
      if (!text) { errBox(s, 'اكتب الرد أولًا'); return; }
      window.__v2ctConfirmAt = Date.now();        // الورقة تسمّي الأثر العلني وزرّها يسمّي الفعل: هي التأكيد
      go.disabled = true; go.textContent = 'جارٍ التنفيذ…'; s.dataset.busy = '1';
      perform(function (cb) { ep().replyOpinion(o, { reply: text }, cb); }, ['platformOpinionsApproved'], function () { var x = approvedById(o.id); return noErr() && !!x && x.editor_reply === text; }, function (ok, err) {
        delete s.dataset.busy;
        if (ok) { closeSheet(); setNote('تمّ: نُشر الرد تحت التعليق.'); redraw(); } else { go.disabled = false; go.textContent = 'انشر الرد'; errBox(s, 'لم يتم. ' + err); }
      });
    };
    var ai = q('#v2ctAi', s);
    if (ai) ai.onclick = function () {
      closeSheet();
      confirmSheet({ title: 'رد آلي', lead: 'يكتب النظام ردًّا ويظهر تحت التعليق باسم هيئة التحرير مباشرة، ويستهلك ذلك من رصيد الكتابة الآلية.', okLabel: 'اكتب الرد', run: function (done) {
        perform(function (cb) { ep().replyOpinion(o, { ai: true }, cb); }, ['platformOpinionsApproved'], function () { var x = approvedById(o.id); return noErr() && !!x && !!x.editor_reply; },
          function (ok, err) { done({ ok: ok, error: err, note: 'تمّ: كُتب الرد وظهر تحت التعليق.' }); });
      } });
    };
    var del = q('#v2ctDel', s);
    if (del) del.onclick = function () { closeSheet(); deleteOpinion(o); };
  }
  function summaryConfirm() {
    confirmSheet({ title: 'اكتب خلاصة', lead: 'يكتب النظام خلاصة من آخر التعليقات المعتمدة، ويستهلك ذلك من رصيد الكتابة الآلية.', okLabel: 'اكتب الخلاصة', run: function (done) {
      ep().api('/platform-opinions-analysis?summarize=true').then(function (r) {
        S.summary = { insights: (r && r.insights) || '', note: (r && r.insights_note) || 'لا آراء معتمدة كافية للتلخيص.' };
        done({ ok: true, note: 'تمّ: كُتبت الخلاصة.' });
      }).catch(function (e) { done({ ok: false, error: apiErr(e) }); });
    } });
  }

  // ================================================================== ٦) دليل الاستخدام
  function drawTutorials() {
    var s0 = st('tutorials');
    if (s0 === 'error') return unavailable('دليل الاستخدام');
    if (s0 !== 'ready') return loadingBlock('دليل الاستخدام');
    var list = (window.TUTORIALS || []).slice().sort(function (a, b) { return (a.order || 0) - (b.order || 0); });
    var p = list.filter(function (t) { return t.is_published; }).length, d = list.length - p, v = list.filter(function (t) { return t.video_url; }).length;
    var facts = '<p class="v2ct-line">' + esc(ar(p) + ' قسمًا منشورًا · ' + ar(d) + ' مسودة · ' + ar(v) + ' بفيديو') + '</p>';
    var groups = {}, order = [];
    list.forEach(function (t) { var g = t.section || 'بلا تصنيف'; if (!groups[g]) { groups[g] = []; order.push(g); } groups[g].push(t); });
    var body = order.length ? order.map(function (g) {
      return '<section class="v2ct-box"><header><h2>' + esc(g) + '</h2></header><div class="v2ct-grid">' + groups[g].map(function (t) {
        return '<article class="v2ct-card tut"><h3><button type="button" class="v2ct-open" data-a="tedit" data-id="' + esc(t.id) + '">' + esc(t.title) + '</button></h3>'
          + '<p class="v2ct-pills">' + pill('ترتيب ' + ar(t.order || 0)) + (t.video_url ? pill('فيديو') : '') + pill(t.is_published ? 'منشور' : 'مسودة', t.is_published ? 'green' : 'amber') + '</p>'
          + '<div class="v2ct-acts"><button type="button" class="v2ct-b1" data-a="tedit" data-id="' + esc(t.id) + '">عدّل</button></div></article>';
      }).join('') + '</div></section>';
    }).join('') : '<div class="v2ct-empty"><b>لا أقسام في الدليل بعد</b></div>';
    return '<div class="v2ct-bar"><button type="button" class="v2ct-b1 auto" data-a="newtut">قسم جديد</button></div>' + facts + body;
  }
  function tutSheet(edit) {
    var e = edit || {};
    var isPub = e.is_published === true;
    var s = openSheet(edit ? 'تعديل قسم' : 'قسم جديد', '<div class="v2ct-fld"><label for="tu_t">العنوان</label><input id="tu_t" value="' + esc(e.title || '') + '"></div>'
      + '<div class="v2ct-two"><div class="v2ct-fld"><label for="tu_sec">القسم</label><input id="tu_sec" value="' + esc(e.section || '') + '" placeholder="ابدأ من هنا"></div>'
      + '<div class="v2ct-fld"><label for="tu_ord">الترتيب</label><input id="tu_ord" type="number" inputmode="numeric" value="' + (e.order != null ? esc(e.order) : '') + '" placeholder="1"></div></div>'
      + '<div class="v2ct-fld"><label for="tu_body">النص (يظهر للأعضاء)</label><textarea id="tu_body" rows="7">' + esc(e.body || '') + '</textarea></div>'
      + '<div class="v2ct-fld"><label for="tu_vid">رابط الفيديو (اختياري، يوتيوب)</label><input id="tu_vid" dir="ltr" value="' + esc(e.video_url || '') + '" placeholder="https://www.youtube.com/watch?v="></div>'
      + '<label class="v2ct-chk"><input id="tu_pub" type="checkbox"' + (edit ? (isPub ? ' checked' : '') : ' checked') + '> منشور (ظاهر للأعضاء)</label><div id="v2ctErr"></div>'
      + '<div class="v2ct-acts2"><button type="button" class="v2ct-b1" id="v2ctSave">احفظ</button>'
      + (edit && isPub ? '<button type="button" class="v2ct-b2" id="v2ctHide">أخفِ</button>' : '') + (edit && !isPub ? '<button type="button" class="v2ct-b2" id="v2ctPubNow">انشر</button>' : '')
      + (edit ? '<button type="button" class="v2ct-b3" id="v2ctDel">احذف</button>' : '') + '<button type="button" class="v2ct-b2" id="v2ctNo">رجوع</button></div>', true);
    if (!s) return;
    q('#v2ctNo', s).onclick = closeSheet;
    q('#v2ctSave', s).onclick = function () {
      var g = { title: q('#tu_t', s).value.trim(), section: q('#tu_sec', s).value.trim(), order: parseInt(q('#tu_ord', s).value, 10) || 0, body: q('#tu_body', s).value,
                video_url: q('#tu_vid', s).value.trim(), is_published: q('#tu_pub', s).checked };
      if (!g.title) { errBox(s, 'العنوان مطلوب'); return; }
      var run = function (done) {
        perform(function (cb) { if (edit && edit.id) ep().updateTutorial(edit.id, g, cb); else ep().createTutorial(g, cb); }, ['tutorials'], noErr,
          function (ok, err) { done({ ok: ok, error: err, note: 'تمّ: حُفظ القسم «' + g.title + '».' }); });
      };
      if (g.is_published) { inlineConfirm(s, { lead: 'يظهر هذا القسم للأعضاء فور الحفظ.', okLabel: 'احفظ وانشر', run: run }); }
      else {
        var sb = q('#v2ctSave', s); sb.disabled = true; sb.textContent = 'جارٍ الحفظ…';
        run(function (res) { if (res.ok) { closeSheet(); setNote(res.note); redraw(); } else { sb.disabled = false; sb.textContent = 'احفظ'; errBox(s, 'لم يتم. ' + res.error); } });
      }
    };
    if (!edit) return;
    var hide = q('#v2ctHide', s);
    if (hide) hide.onclick = function () {
      // مستثنى من التأكيد: الإخفاء فوري ويُتراجع عنه.
      hide.disabled = true; hide.textContent = 'جارٍ التنفيذ…';
      perform(function (cb) { ep().updateTutorial(edit.id, { title: edit.title, is_published: false }, cb); }, ['tutorials'], function () {
        var x = (window.TUTORIALS || []).filter(function (t) { return t.id === edit.id; })[0]; return noErr() && !!x && !x.is_published; }, function (ok, err) {
        if (ok) { closeSheet(); setNote('تمّ: أُخفي القسم «' + edit.title + '».'); redraw(); } else { hide.disabled = false; hide.textContent = 'أخفِ'; errBox(s, 'لم يتم. ' + err); }
      });
    };
    var pn = q('#v2ctPubNow', s);
    if (pn) pn.onclick = function () {
      closeSheet();
      confirmSheet({ title: 'نشر القسم', lead: 'يظهر هذا القسم للأعضاء في دليل الاستخدام.', okLabel: 'انشر', run: function (done) {
        perform(function (cb) { ep().updateTutorial(edit.id, { title: edit.title, is_published: true }, cb); }, ['tutorials'], function () {
          var x = (window.TUTORIALS || []).filter(function (t) { return t.id === edit.id; })[0]; return noErr() && !!x && x.is_published; }, function (ok, err) { done({ ok: ok, error: err, note: 'تمّ: نُشر القسم «' + edit.title + '».' }); });
      } });
    };
    var del = q('#v2ctDel', s);
    if (del) del.onclick = function () {
      closeSheet();
      confirmSheet({ title: 'حذف القسم', lead: 'يُحذف هذا القسم من الدليل.', okLabel: 'احذف', danger: true, run: function (done) {
        perform(function (cb) { ep().deleteTutorial(edit, cb); }, ['tutorials'], function () { return noErr() && !(window.TUTORIALS || []).some(function (t) { return t.id === edit.id; }); },
          function (ok, err) { done({ ok: ok, error: err, note: 'تمّ: حُذف القسم.' }); });
      } });
    };
  }

  // ================================================================== أوراق: عمل إبداعي · رأي متعلّم
  function creativeSheet(w) {
    var kindText = ({ song: 'أغنية', video: 'فيديو', poem: 'قصيدة' })[w.kind] || 'عمل آخر';
    var s = openSheet('عمل من ركن الإبداع', '<h2 class="v2ct-rt">' + esc(w.title || 'عمل بلا عنوان') + '</h2><p class="v2ct-pills">' + pill(kindText) + '</p>'
      + '<p class="v2ct-cm">' + person(w.creator_name || w.creator_email || 'صاحب العمل', w.creator_email) + '</p>'
      + (String(w.cover_url || '').trim() ? '<p class="v2ct-pills">' + pill('صورة الغلاف: موجودة', 'green') + '</p>' : '')
      + (w.body ? '<p class="v2ct-val pre tall">' + esc(w.body) + '</p>' : '')
      + (String(w.media_url || '').trim() ? '<p>' + (safeLink(w.media_url, 'افتح الرابط') || '<span class="v2ct-mute">الرابط غير صالح للفتح: <span class="v2ct-ltr" dir="ltr">' + esc(w.media_url) + '</span></span>') + '</p>' : '')
      + '<div id="v2ctErr"></div><div class="v2ct-acts2"><button type="button" class="v2ct-b1" id="v2ctOk">اعتمد وانشر</button><button type="button" class="v2ct-b2" id="v2ctRej">ارفض</button><button type="button" class="v2ct-b2" id="v2ctNo">إغلاق</button></div>', true);
    if (!s) return;
    q('#v2ctNo', s).onclick = closeSheet;
    function gone2() { return !(creativeList() || []).some(function (x) { return x.id === w.id; }); }
    function decide(action, reason, done) {
      var E = ep(); E.lastError = '';
      Promise.resolve(E.decideInboxItem({ apiKind: 'creative', apiId: w.id }, action, function () {}, reason)).then(function (res) {
        res = res || {};
        if (!res.ok) { done({ ok: false, error: res.error || 'تعذّر تنفيذ القرار' }); return; }
        E.reload('platformCreative', function () {
          if (E.state.platformCreative === 'loading') return;
          if (gone2()) done({ ok: true, note: action === 'approve' ? 'تمّ: اعتُمد العمل ونُشر.' : 'تمّ: رُفض العمل وأُرسل السبب لصاحبه.' });
          else done({ ok: false, error: 'العمل ما زال بانتظار المراجعة. حدّث الصفحة ثم تحقّق.' });
        });
      });
    }
    q('#v2ctOk', s).onclick = function () {
      closeSheet();
      confirmSheet({ title: 'اعتماد العمل', lead: 'سيظهر العمل للجميع في ركن الإبداع.', okLabel: 'اعتمد وانشر', run: function (done) { decide('approve', '', done); } });
    };
    q('#v2ctRej', s).onclick = function () {
      closeSheet();
      var rs = openSheet('رفض العمل', '<p class="v2ct-lead">اكتب سبب الرفض، ويصل إلى صاحب العمل.</p><div class="v2ct-fld"><label for="rj_t">سبب الرفض</label><textarea id="rj_t" rows="4" maxlength="500"></textarea></div><div id="v2ctErr"></div>'
        + '<div class="v2ct-acts2"><button type="button" class="v2ct-b1 danger" id="v2ctGo" disabled>ارفض وأرسل السبب</button><button type="button" class="v2ct-b2" id="v2ctNo">رجوع</button></div>');
      if (!rs) return;
      var go = q('#v2ctGo', rs), f = q('#rj_t', rs);
      f.addEventListener('input', function () { if (!go.dataset.busy) go.disabled = !f.value.trim(); });
      q('#v2ctNo', rs).onclick = function () { if (!rs.dataset.busy) closeSheet(); };
      go.onclick = function () {
        if (go.dataset.busy || !f.value.trim()) return;
        window.__v2ctConfirmAt = Date.now();
        go.dataset.busy = '1'; rs.dataset.busy = '1'; go.disabled = true; go.textContent = 'جارٍ التنفيذ…';
        decide('reject', f.value.trim(), function (res) {
          delete rs.dataset.busy;
          if (res.ok) { closeSheet(); setNote(res.note); redraw(); } else { delete go.dataset.busy; go.disabled = false; go.textContent = 'ارفض وأرسل السبب'; errBox(rs, 'لم يتم. ' + res.error); }
        });
      };
    };
  }
  function testimonialSheet(r) {
    var consent = r.consent_public === true ? 'وافق كاتبه على النشر باسمه' : '';
    var s = openSheet('رأي متعلّم', '<p class="v2ct-kick">' + esc(r.course_title || 'دورة') + '</p><p class="v2ct-cm">' + person(r.name || 'متعلّم', r.user_email) + (r.rating != null && r.rating !== '' ? ' · التقييم ' + esc(ar(r.rating)) + ' من ٥' : '') + '</p>'
      + '<p class="v2ct-val pre tall">' + esc(r.text || '') + '</p>' + (consent ? '<p class="v2ct-line">' + esc(consent) + '</p>' : '')
      + '<div class="v2ct-acts2"><button type="button" class="v2ct-b1" id="v2ctOk">اعتمد</button><button type="button" class="v2ct-b2" id="v2ctRej">ارفض</button><button type="button" class="v2ct-b2" id="v2ctNo">إغلاق</button></div>');
    if (!s) return;
    q('#v2ctNo', s).onclick = closeSheet;
    q('#v2ctOk', s).onclick = function () {
      closeSheet(); approveTestimonial(r);
    };
    q('#v2ctRej', s).onclick = function () {
      closeSheet();
      confirmSheet({ title: 'رفض الرأي', lead: 'لن يظهر الرأي على صفحة الدورة.', okLabel: 'ارفض', danger: true, run: function (done) { decideTestimonial(r, 'reject', done); } });
    };
  }
  function decideTestimonial(r, action, done) {
    var E = ep();
    apiPost('/v2/testimonials/' + encodeURIComponent(r.id) + '/' + action, action === 'approve' ? { confirmed: true } : {}).then(function () {
      var fired = false;
      function chk() {
        if (fired || E.state.testimonials === 'loading') return;
        fired = true;
        if (!(testimonialsList() || []).some(function (x) { return x.id === r.id; })) done({ ok: true, note: action === 'approve' ? 'تمّ: اعتُمد الرأي.' : 'تمّ: رُفض الرأي.' });
        else done({ ok: false, error: 'الرأي ما زال بانتظار المراجعة. حدّث الصفحة ثم تحقّق.' });
      }
      E.reload('testimonialsApproved', null);
      E.reload('testimonials', chk);
    }).catch(function (e) { done({ ok: false, error: apiErr(e) }); });
  }
  function approveTestimonial(r) {
    var lead = r.consent_public === true ? 'سيظهر الرأي باسم كاتبه على صفحة الدورة.' : 'سيظهر الرأي على صفحة الدورة.';
    confirmSheet({ title: 'اعتماد الرأي', lead: lead, extra: '<p class="v2ct-val pre tall">' + esc(r.text || '') + '</p>', okLabel: 'اعتمد', run: function (done) { decideTestimonial(r, 'approve', done); } });
  }

  // ================================================================== ٧) الموقع: تعديل نصوص الموقع من اللوحة
  // الطريق: «عدّل» على نص ⇒ اقتراح بانتظار الاعتماد (لا يلمس الموقع) ⇒ «اعتمد وانشر» بورقة تأكيد ⇒ نسخة سابقة ثم نشر وتحقق.
  // ⛔ لا كتابة على الموقع من هنا مباشرة: كل شيء عبر مسارات `/v2/site/*` و`/v2/brain/items/<id>/approve` (الخادم هو الحَكَم).
  // ⛔ كل مصدر هنا: undefined = جارٍ · null = تعذّر (يُكتب ولا يُعتبر فارغًا) · مصفوفة = وصل.
  var SITE_PRODUCERS = ['site_review', 'site_edit_manual'];
  var SS = { init: false, pages: undefined, page: '', label: '', blocks: undefined, sha: '', decisions: undefined, backups: undefined, pending: undefined,
             kind: 'all', decDraft: '', decErr: '', err: {}, byId: {}, seq: {} };
  function siteApi(key, path, pick, bound) {
    var E = ep(), snap = SS.page, n = (SS.seq[key] || 0) + 1;
    SS.seq[key] = n;
    if (!E || !E.api) { SS[key] = null; return; }
    E.api(path).then(function (d) {
      if (SS.seq[key] !== n || (bound && SS.page !== snap)) return;       // وصل ردّ قديم بعد تبديل الصفحة: نتجاهله
      SS.err[key] = ''; SS[key] = pick(d || {});
    }).catch(function (e) {
      if (SS.seq[key] !== n || (bound && SS.page !== snap)) return;
      SS[key] = null; SS.err[key] = apiErr(e);
    }).then(siteRedraw);
  }
  function siteRedraw() { if (isCurrent() && currentTab() === 'site' && !modalOpen()) redraw(); }
  function siteLoadPending() {
    siteApi('pending', '/v2/brain/items?status=proposed&section=content', function (d) {
      SS.byId = {};
      var rows = (d.items || []).filter(function (i) { return SITE_PRODUCERS.indexOf(i.producer) > -1; });
      rows.forEach(function (i) { SS.byId[i.id] = i; });
      return rows;
    });
  }
  function siteLoadDecisions() { siteApi('decisions', '/v2/site/decisions', function (d) { return d.decisions || []; }); }
  function siteLoadPage() {
    if (!SS.page) return;
    var enc = encodeURIComponent(SS.page);
    SS.blocks = undefined; SS.backups = undefined;
    siteApi('blocks', '/v2/site/blocks?page=' + enc, function (d) { SS.sha = d.sha || ''; SS.label = d.label || SS.label; return d.blocks || []; }, true);
    siteApi('backups', '/v2/site/backups?page=' + enc, function (d) { return d.backups || []; }, true);
  }
  function siteLoadBase() {
    siteApi('pages', '/v2/site/pages', function (d) { return d.pages || []; });
    siteLoadDecisions();
    siteLoadPending();
    siteLoadPage();
  }
  function siteEnter() { siteLoadDecisions(); siteLoadPending(); siteLoadPage(); }          // دخول جديد للتبويب: كل شيء من جديد، والنصوص من الموقع الحي
  function siteAfterChange() { siteLoadPending(); siteLoadPage(); }
  function siteUnavailable(key, title) {
    return '<div class="v2ct-empty"><b>' + esc(title) + ': ' + NA + '</b><p>' + esc(SS.err[key] || 'تعذّر الوصول إلى هذه البيانات الآن، فلا تعتبرها فارغة.') + '</p>'
      + '<button type="button" class="v2ct-b2" data-a="sreload">أعد المحاولة</button></div>';
  }
  function siteDiff(item) {
    var b = item.body || {}, edits = Array.isArray(b.edits) ? b.edits : [];
    return '<ul class="v2ct-sdiff">' + edits.map(function (e) {
      return '<li><span class="v2ct-sold" dir="auto">' + esc(e.old) + '</span><span class="v2ct-snew" dir="auto">' + esc(e.new) + '</span>' + (e.why ? '<em>' + esc(e.why) + '</em>' : '') + '</li>';
    }).join('') + '</ul>';
  }
  function sitePendingBox() {
    if (SS.pending === undefined) return '';
    if (SS.pending === null) return '<div class="v2ct-warn" role="status">تعذّر جلب الاقتراحات المنتظرة. ' + esc(SS.err.pending || '') + ' <button type="button" class="v2ct-b2 sm" data-a="sreload">أعد المحاولة</button></div>';
    if (!SS.pending.length) return '';
    return '<section class="v2ct-box"><header><h2>ينتظر اعتمادك</h2><span class="v2ct-n">' + esc(ar(SS.pending.length)) + '</span></header>'
      + '<div class="v2ct-stack">' + SS.pending.map(function (it) {
        var mine = it.source === 'founder', body = it.body || {};
        return '<article class="v2ct-row v2ct-sprop"><p class="v2ct-cm">' + esc(body.page_label || it.target_label || 'صفحة') + ' · ' + esc(mine ? 'كتبته بنفسك' : 'اقترحه العقل') + '</p>'
          + siteDiff(it) + (it.last_error ? '<div class="v2ct-err" role="alert">' + esc(it.last_error) + '</div>' : '')
          + '<div class="v2ct-acts"><button type="button" class="v2ct-b1 auto" data-a="sapprove" data-id="' + esc(it.id) + '">اعتمد وانشر</button> '
          + '<button type="button" class="v2ct-b2" data-a="sreject" data-id="' + esc(it.id) + '">ارفض</button></div></article>';
      }).join('') + '</div></section>';
  }
  function sitePickerBox() {
    var head0 = '<header><h2>صفحات الموقع</h2></header>';
    if (SS.pages === undefined) return '<section class="v2ct-box">' + head0 + '<p class="v2ct-line">…جارٍ جلب الصفحات</p></section>';
    if (SS.pages === null) return '<section class="v2ct-box">' + head0 + siteUnavailable('pages', 'الصفحات') + '</section>';
    var opts = '<option value="">اختر صفحة…</option>' + SS.pages.map(function (p) {
      return '<option value="' + esc(p.page) + '"' + (p.page === SS.page ? ' selected' : '') + '>' + esc(p.label) + '</option>';
    }).join('');
    return '<section class="v2ct-box">' + head0 + '<div class="v2ct-catf"><label for="sitePage">الصفحة</label><select id="sitePage" class="v2ct-sel" data-a="spick">' + opts + '</select>'
      + (SS.page ? '<button type="button" class="v2ct-b2" data-a="sreload">حدّث النصوص من الموقع</button>' : '') + '</div>'
      + (SS.page ? '' : '<p class="v2ct-line">اختر صفحة لترى نصوصها كما هي على الموقع الآن.</p>') + '</section>';
  }
  function siteBlocksBox() {
    var title = SS.label || 'الصفحة';
    if (SS.blocks === undefined) return '<section class="v2ct-box"><header><h2>' + esc(title) + '</h2></header><p class="v2ct-line">…جارٍ قراءة الصفحة من الموقع</p></section>';
    if (SS.blocks === null) return '<section class="v2ct-box"><header><h2>' + esc(title) + '</h2></header>' + siteUnavailable('blocks', 'نصوص الصفحة') + '</section>';
    var chips = L.v2SiteKinds().map(function (k) {
      return '<button type="button" class="v2ct-chip' + (k.key === SS.kind ? ' on' : '') + '" data-a="skind" data-v="' + k.key + '">' + esc(k.label) + '</button>';
    }).join('');
    var rows = L.v2SiteBlockRows(SS.blocks, SS.kind);
    var list = rows.length ? rows.map(function (r) {
      return '<div class="v2ct-sb"><div class="v2ct-sbm"><span class="v2ct-pill">' + esc(r.tagLabel) + '</span>' + (r.part ? '<span class="v2ct-pill amber">جزء ' + esc(ar(r.part)) + ' من فقرة</span>' : '') + '</div>'
        + '<p class="v2ct-sbt" dir="auto">' + esc(r.text) + '</p>'
        + (r.editable ? '<button type="button" class="v2ct-b2 sm" data-a="sedit" data-i="' + r.index + '">عدّل</button>' : '<span class="v2ct-line">' + esc(r.note) + '</span>') + '</div>';
    }).join('') : '<div class="v2ct-none">لا نصوص من هذا النوع في الصفحة</div>';
    return '<section class="v2ct-box"><header><h2>' + esc(title) + '</h2><span class="v2ct-n">' + esc(ar(rows.length)) + '</span></header>'
      + '<p class="v2ct-line">النصوص كما هي على الموقع الآن. اضغط «عدّل» لتكتب بديلًا، فيصير اقتراحًا تعتمده بنفسك.</p>'
      + '<div class="v2ct-chips" role="tablist" aria-label="نوع النص">' + chips + '</div><div class="v2ct-sblist">' + list + '</div></section>';
  }
  function siteDecisionsBox() {
    var head0 = '<header><h2>القرارات</h2></header><p class="v2ct-line">قواعد النص العام التي يراعيها العقل حين يقترح تعديلًا على الموقع. أضف قاعدة أو احذف ما لم يعد صالحًا.</p>';
    if (SS.decisions === undefined) return '<section class="v2ct-box">' + head0 + '<p class="v2ct-line">…جارٍ جلب القرارات</p></section>';
    if (SS.decisions === null) return '<section class="v2ct-box">' + head0 + siteUnavailable('decisions', 'القرارات') + '</section>';
    var list = SS.decisions.length ? '<ul class="v2ct-sdec">' + SS.decisions.map(function (d) {
      return '<li><span>' + esc(d.text) + '</span><button type="button" class="v2ct-b3" data-a="sdecdel" data-id="' + esc(d.id) + '">احذف</button></li>';
    }).join('') + '</ul>' : '<div class="v2ct-none">لا قواعد بعد</div>';
    return '<section class="v2ct-box">' + head0 + list
      + '<div class="v2ct-sdecadd"><label for="siteDec">قاعدة جديدة</label><input id="siteDec" class="v2ct-sel" maxlength="300" value="' + esc(SS.decDraft) + '" placeholder="اكتب القاعدة في جملة واحدة">'
      + '<button type="button" class="v2ct-b2" data-a="sdecadd">أضف القاعدة</button></div>'
      + (SS.decErr ? '<div class="v2ct-err" role="alert">' + esc(SS.decErr) + '</div>' : '') + '</section>';
  }
  function siteBackupsBox() {
    var head0 = '<header><h2>النسخ السابقة</h2></header>';
    if (SS.backups === undefined) return '<section class="v2ct-box">' + head0 + '<p class="v2ct-line">…جارٍ جلب النسخ</p></section>';
    if (SS.backups === null) return '<section class="v2ct-box">' + head0 + siteUnavailable('backups', 'النسخ السابقة') + '</section>';
    var rows = L.v2SiteBackupRows(SS.backups, now());
    var list = rows.length ? '<ul class="v2ct-sdec">' + rows.map(function (r) {
      return '<li><span>' + esc(r.kind + ' · ' + r.when + (r.who ? ' · ' + r.who : '') + ' · ' + r.size) + '</span>'
        + '<button type="button" class="v2ct-b2 sm" data-a="srestore" data-id="' + esc(r.id) + '">أرجِع الصفحة</button></li>';
    }).join('') + '</ul>' : '<div class="v2ct-none">لا نسخ بعد. تُحفظ نسخة قبل كل تعديل يُنشر.</div>';
    return '<section class="v2ct-box">' + head0 + '<p class="v2ct-line">آخر ' + esc(ar(20)) + ' نسخة من هذه الصفحة. «أرجِع الصفحة» يعيدها كما كانت وقت النسخة.</p>' + list + '</section>';
  }
  function drawSite() {
    if (!SS.init) { SS.init = true; siteLoadBase(); }
    return head('الموقع', 'عدّل أي نص في صفحات الموقع. تعديلك يصير اقتراحًا، ولا يظهر للناس حتى تعتمده.')
      + sitePendingBox() + sitePickerBox() + (SS.page ? siteBlocksBox() : '') + siteDecisionsBox() + (SS.page ? siteBackupsBox() : '');
  }
  function sitePick(page) {
    SS.page = page || ''; SS.kind = 'all'; SS.blocks = undefined; SS.backups = undefined; SS.sha = '';
    SS.label = ((SS.pages || []).filter(function (p) { return p.page === SS.page; })[0] || {}).label || '';
    if (SS.page) siteLoadPage();
    redraw();
  }
  function siteEditSheet(r) {
    var s = openSheet('تعديل نص في الموقع', '<p class="v2ct-kick">' + esc(r.tagLabel + (r.part ? ' · جزء ' + ar(r.part) + ' من فقرة' : '')) + '</p>'
      + '<div class="v2ct-fld"><label>النص الحالي</label><p class="v2ct-val" dir="auto">' + esc(r.text) + '</p></div>'
      + '<div class="v2ct-fld"><label for="siteNew">النص الجديد</label><textarea id="siteNew" rows="5" maxlength="600">' + esc(r.text) + '</textarea></div>'
      + '<p class="v2ct-fine">لن يظهر على الموقع حتى تعتمده. اكتب نصًا عاديًا بلا وسوم.</p><div id="v2ctErr"></div>'
      + '<div class="v2ct-acts2"><button type="button" class="v2ct-b1" id="v2ctSave">احفظ الاقتراح</button><button type="button" class="v2ct-b2" id="v2ctNo">رجوع</button></div>', true);
    if (!s) return;
    var save = q('#v2ctSave', s), box = q('#siteNew', s);
    q('#v2ctNo', s).onclick = function () { if (!s.dataset.busy) closeSheet(); };
    save.onclick = function () {
      // مستثنى من التأكيد: يحفظ اقتراحًا فقط ولا يلمس الموقع؛ النشر نفسه يمرّ على ورقة «اعتمد وانشر».
      if (save.dataset.busy) return;
      var chk = L.v2SiteCheckNew(r.text, box.value, r.tag);
      if (!chk.ok) { errBox(s, chk.error); return; }
      save.dataset.busy = '1'; s.dataset.busy = '1'; save.disabled = true; save.textContent = 'جارٍ الحفظ…'; errBox(s, '');
      apiPost('/v2/site/edit', { page: SS.page, path: r.path, old: r.text, new: chk.text, sha: SS.sha, confirmed: true }).then(function () {
        delete s.dataset.busy; closeSheet();
        setNote('حُفظ الاقتراح. اعتمده من «ينتظر اعتمادك» حتى يظهر على الموقع.');
        siteLoadPending(); redraw();
      }).catch(function (e) {
        delete s.dataset.busy; delete save.dataset.busy; save.disabled = false; save.textContent = 'احفظ الاقتراح';
        errBox(s, apiErr(e));
        if (e && e.status === 409) siteLoadPage();
      });
    };
  }
  function siteApprove(it) {
    confirmSheet({ title: 'نشر التعديل على الموقع', lead: 'سيظهر التعديل على الموقع للناس فور الاعتماد، وتُحفظ نسخة سابقة تستطيع إرجاعها.', extra: siteDiff(it),
      okLabel: 'اعتمد وانشر', run: function (done) {
        apiPost('/v2/brain/items/' + encodeURIComponent(it.id) + '/approve', { confirmed: true }).then(function () {
          siteAfterChange(); done({ ok: true, note: 'تمّ: ظهر التعديل على الموقع.' });
        }).catch(function (e) { siteLoadPending(); done({ ok: false, error: apiErr(e) }); });
      } });
  }
  function siteReject(it) {
    confirmSheet({ title: 'رفض الاقتراح', lead: 'لن يُنشر هذا الاقتراح، ولن يتغيّر الموقع.', extra: siteDiff(it), okLabel: 'ارفض', run: function (done) {
      apiPost('/v2/brain/items/' + encodeURIComponent(it.id) + '/reject', { confirmed: true }).then(function () {
        siteLoadPending(); done({ ok: true, note: 'تمّ: رُفض الاقتراح.' });
      }).catch(function (e) { siteLoadPending(); done({ ok: false, error: apiErr(e) }); });
    } });
  }
  function siteRestore(id) {
    var row = L.v2SiteBackupRows((SS.backups || []).filter(function (b) { return String(b.id) === String(id); }), now())[0];
    if (!row) return;
    confirmSheet({ title: 'إرجاع الصفحة', danger: true,
      lead: 'ستعود «' + (SS.label || 'الصفحة') + '» كما كانت ' + row.when + '، وتظهر للناس فور الإرجاع. نحفظ نسخة من الحالية قبل ذلك.',
      okLabel: 'أرجِع الصفحة', run: function (done) {
        apiPost('/v2/site/restore', { page: SS.page, backup_id: Number(id), confirmed: true }).then(function () {
          siteAfterChange(); done({ ok: true, note: 'تمّ: عادت الصفحة كما كانت.' });
        }).catch(function (e) { done({ ok: false, error: apiErr(e) }); });
      } });
  }
  function siteAddDecision() {
    // مستثنى من التأكيد: قاعدة داخلية يقرؤها العقل ولا تظهر للناس، وتُحذف بتأكيد.
    var text = String(SS.decDraft || '').trim();
    if (text.length < 3) { SS.decErr = 'اكتب قاعدة من ٣ أحرف فأكثر'; return redraw(); }
    SS.decErr = '';
    apiPost('/v2/site/decisions', { text: text, confirmed: true }).then(function () {
      SS.decDraft = ''; setNote('تمّ: أُضيفت القاعدة.'); siteLoadDecisions(); redraw();
    }).catch(function (e) { SS.decErr = apiErr(e); redraw(); });
  }
  function siteDelDecision(id) {
    var d = (SS.decisions || []).filter(function (x) { return x.id === id; })[0];
    if (!d) return;
    confirmSheet({ title: 'حذف قاعدة', danger: true, lead: 'تُحذف هذه القاعدة من القرارات، ولا يراعيها العقل بعد الآن.', extra: '<p class="v2ct-val">' + esc(d.text) + '</p>', okLabel: 'احذف', run: function (done) {
      ep().api('/v2/site/decisions/' + encodeURIComponent(id), { method: 'DELETE', body: { confirmed: true } }).then(function () {
        siteLoadDecisions(); done({ ok: true, note: 'تمّ: حُذفت القاعدة.' });
      }).catch(function (e) { done({ ok: false, error: apiErr(e) }); });
    } });
  }

  // ================================================================== الأحداث
  function itemOf(id) { return S.items[id] || null; }
  function runAct(it) {
    var sg = L.v2ContentSuggest(it);
    if (!sg) return;
    var ref = it.ref;
    switch (sg.act) {
      case 'approveMemberTopic': approvePending(ref); break;
      case 'openTestimonial': testimonialSheet(ref); break;
      case 'approveTestimonial': approveTestimonial(ref); break;
      case 'rejectComment': rejectOpinion(ref); break;
      case 'openComment': commentSheet(ref); break;
      case 'openCreative': creativeSheet(ref); break;
      case 'openArticle': openSiteReader(ref.id); break;
      case 'openPlatformArticle': openPlatformReader(ref.id); break;
      case 'publishTopic': publishToBoard(ref); break;
      case 'openTopic': openTopicSheet(it.kind === 'working' ? 'working' : L.v2ContentTopicTabOf(ref), ref); break;
      case 'approveIdea': approveToBoard(ref); break;
      case 'publishNews': publishNews(ref); break;
      case 'openNews': newsSheet(ref); break;
      case 'retry': retryFailed(); break;
    }
  }
  function openItem(it) {
    var k = it.kind, ref = it.ref;
    if (k === 'memberTopic') openTopicSheet('pending', ref);
    else if (k === 'testimonial') testimonialSheet(ref);
    else if (k === 'comment') commentSheet(ref);
    else if (k === 'creative') creativeSheet(ref);
    else if (k === 'siteDraft') openSiteReader(ref.id);
    else if (k === 'platformDraft') openPlatformReader(ref.id);
    else if (k === 'working' || k === 'idea') openTopicSheet(L.v2ContentTopicTabOf(ref), ref);
    else if (k === 'newsDraft') newsSheet(newsById(ref.id) || ref);
    else if (it.go) goTo(it.go);
  }
  function goTo(go) {
    if (!go) return;
    if (go.tab === 'articles') { if (go.filter) S.afilter = go.filter; window.v2OpenSection('content', 'articles', { st: { topicsTab: go.st || 'articles' } }); }
    else if (go.tab === 'topics') window.v2OpenSection('content', 'topics', { st: { topicsTab: go.st || 'pending' } });
    else window.v2OpenSection('content', go.tab);
  }
  function onClick(e) {
    var b = e.target.closest ? e.target.closest('[data-a]') : null;
    // #view مشترك بين كل الشاشات: لا نتصرف إلا في عناصر هذا القسم وهو الظاهر (شاشات D2/D3 تستعمل data-a أيضًا).
    if (!b || !S.view || !S.view.contains(b) || !isCurrent() || !b.closest('.v2ct')) return;
    var a = b.getAttribute('data-a'), id = b.getAttribute('data-id'), v = b.getAttribute('data-v');
    if (a === 'refreshBoard') { refreshKeys(NEED.pipeline); return redraw(); }
    if (a === 'retry') { retryFailed(); return redraw(); }
    if (a === 'col') { S.col = b.getAttribute('data-col'); S.picked = true; return redraw(); }
    if (a === 'more') {
      var c = b.getAttribute('data-col'), m = S.board && S.board.more[c];
      if (m && m.go) return goTo(m.go);
      S.expand[c] = true; return redraw();
    }
    if (a === 'primary') { var it = itemOf(id); if (it) runAct(it); return; }
    if (a === 'open') { var it2 = itemOf(id); if (it2) openItem(it2); return; }
    if (a === 'asub') return window.v2OpenSection('content', 'articles', { replace: true, st: { topicsTab: v } });
    if (a === 'afilter') { S.afilter = v; return redraw(); }
    if (a === 'newart') return newArticle();
    if (a === 'tools') return openTools(topicsTabNow() === 'auto' ? 'plat' : 'site');
    if (a === 'sread') return openSiteReader(id);
    if (a === 'pread') return openPlatformReader(id);
    if (a === 'tchip') { S.cat = 'all'; return window.v2OpenSection('content', 'topics', { replace: true, st: { topicsTab: v } }); }
    if (a === 'newtopic') return newTopicSheet();
    if (a === 'tmain' || a === 'topen') {
      var chip = b.getAttribute('data-chip'), t = findTopic(chip, id);
      if (!t) return;
      return a === 'tmain' ? topicMain(chip, t) : openTopicSheet(chip, t);
    }
    if (a === 'reloadNums') { var E = ep(); if (E) E.reload('platformTopicsAnalysis', null); return; }
    if (a === 'nfilter') { S.nfilter = v; return redraw(); }
    if (a === 'newnews') return newsSheet(null);
    if (a === 'nsources') return sourcesSheet();
    if (a === 'nmain') { var n = newsById(id); if (!n) return; var complete = (n.sources || []).length >= 1 && !!String(n.summary || '').trim(); return n.status === 'published' || !complete ? newsSheet(n) : publishNews(n); }
    if (a === 'nopen') { var n2 = newsById(id); if (n2) newsSheet(n2); return; }
    if (a === 'copen') { var o = opinionById(id); if (o) commentSheet(o); return; }
    if (a === 'cmain') { var o2 = opinionById(id); if (!o2) return; var sg = L.v2ContentSuggest({ kind: 'comment', moderation: o2.moderation }); return sg.act === 'rejectComment' ? rejectOpinion(o2) : commentSheet(o2); }
    if (a === 'creply') { var o3 = approvedById(id); if (o3) replySheet(o3); return; }
    if (a === 'csummary') return summaryConfirm();
    if (a === 'sreload') { siteLoadDecisions(); siteLoadPending(); if (!SS.pages) siteApi('pages', '/v2/site/pages', function (d) { return d.pages || []; }); siteLoadPage(); return redraw(); }
    if (a === 'skind') { SS.kind = v; return redraw(); }
    if (a === 'sedit') { var sr = L.v2SiteBlockRows(SS.blocks, 'all').filter(function (x) { return String(x.index) === b.getAttribute('data-i'); })[0]; if (sr && sr.editable) siteEditSheet(sr); return; }
    if (a === 'sapprove') { var si = SS.byId[id]; if (si) siteApprove(si); return; }
    if (a === 'sreject') { var sj = SS.byId[id]; if (sj) siteReject(sj); return; }
    if (a === 'srestore') return siteRestore(id);
    if (a === 'sdecadd') { var inp = q('#siteDec', S.view); if (inp) SS.decDraft = inp.value; return siteAddDecision(); }
    if (a === 'sdecdel') return siteDelDecision(id);
    if (a === 'newtut') return tutSheet(null);
    if (a === 'tedit') { var tu = (window.TUTORIALS || []).filter(function (t2) { return t2.id === id; })[0]; if (tu) tutSheet(tu); return; }
  }
  function newArticle() { var s = openSheet('مقال جديد', '<div id="v2ctStage"></div>', true); if (s) articleForm(q('#v2ctStage', s), null, null, s); }
  function onChange(e) {
    var t = e.target;
    if (!isCurrent()) return;
    if (t && t.getAttribute && t.getAttribute('data-a') === 'cat' && t.closest && t.closest('.v2ct')) { S.cat = t.value; redraw(); }
    if (t && t.getAttribute && t.getAttribute('data-a') === 'spick' && t.closest && t.closest('.v2ct')) sitePick(t.value);
  }
  // مسوّدة «قاعدة جديدة» تبقى عبر إعادات الرسم (الدقيقة وتبديل المصادر) حتى تُضاف أو تُترك.
  function onInput(e) {
    if (e.target && e.target.id === 'siteDec' && isCurrent()) SS.decDraft = e.target.value;
  }

  // ================================================================== نقطة الدخول
  function activate() {
    var E = ep();
    if (E) E.muteNotes = true;
    S.active = true;
  }
  function deactivate() {
    var E = ep();
    if (E) E.muteNotes = false;
    S.active = false;
  }
  API.owns = function (mod) { return mod === 'topics'; };
  API.tabFor = L.v2ContentTabFor;
  API.render = function (mod, view) {
    S.view = view;
    activate();
    view.onclick = onClick;
    view.onchange = onChange;
    view.oninput = onInput;
    S.lastTab = '';          // دخول جديد للقسم ⇒ تحديث الجانب المنتظِر
    redraw();
    if (!S.poll) {
      S.poll = setInterval(function () {
        if (!isCurrent()) { if (S.active) { deactivate(); if (S.view) { if (S.view.onclick === onClick) S.view.onclick = null; if (S.view.onchange === onChange) S.view.onchange = null; if (S.view.oninput === onInput) S.view.oninput = null; } } return; }
        if (!S.active) activate();
        if (modalOpen()) return;
        if (signature() !== S.sig) redraw();
      }, 400);
    }
    if (!S.minute) S.minute = setInterval(function () {
      if (!isCurrent() || modalOpen()) return;
      if (currentTab() === 'pipeline' && Date.now() - S.lastRefresh >= 55000) refreshKeys(WAITING);
      redraw();
    }, 60000);   // العدّاد: نصوص الأزمنة تتجدّد بلا إعادة تحميل
  };
  API._state = S;
  API._site = SS;
  API._t = { safeHref: safeHref, safeLink: safeLink, creativeSheet: creativeSheet, testimonialSheet: testimonialSheet, approveTestimonial: approveTestimonial, refreshKeys: refreshKeys, WAITING: WAITING };   // خطّاف اختبار فقط
  API._tick = function (t) { S.nowOverride = t || 0; redraw(); };
})();
