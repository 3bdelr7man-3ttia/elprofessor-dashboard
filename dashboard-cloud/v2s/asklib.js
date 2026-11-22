/* ============================================================================
 * v2s/asklib.js — «المحتوى ‹ أدخل قوانين المكتبة»: مستندات مكتبة المنصة ⇒ تقسيمها مواد في قاعدة نصوص «اسأل».
 * ١) ملخص القاعدة (مواد كل تخصص وحالة + التصحيحات المعتمدة) · ٢) قائمة المستندات (فلتر «المقترح للنيابة الإدارية» / «الكل» + بحث بالعنوان)
 * ٣) لكل مستند: التخصص ورقم القانون ثم «جرّب التقسيم» (معاينة بلا كتابة) ثم «أدخل المواد» (ورقة تأكيد ثم كتابة + تدقيق).
 * ٤) «تنظيف المكتبة»: النسخ المكررة بالحرف + المستندات شبه الفاضية + «المحذوفات». الحذف بيترجّع دايمًا (المنصة بتعلّم المستند وبس)،
 *    وشروطه عند المنصة: المكرر لازم يطابق الباقي حرفيًا، واللي اتدخلت منه مواد في قاعدة النصوص ما بيتحذفش.
 * ٥) «القوانين الناقصة»: القايمة الأساسية لكل بلد قصاد قاعدة «اسأل» (موجود بكام مادة / ناقص)، و«حط النص» بيدخّل نص قانون
 *    من مصدره الرسمي في قاعدة بلده: معاينة التقسيم الأول ثم إدخال. من غير رابط المصدر مفيش إدخال.
 * ⛔ المفتاح مقفول افتراضيًا: الملف بيتحمّل دايمًا لكنه ما بيرسم شيئًا إلا لو index.html نادى `render` (والغلاف الجديد شغّال).
 * ⛔ الكتابة للأدمن بس. ⛔ المصدر اللي غاب ⇒ «غير متاح بعد» لا صفر. ⛔ لا confirm ولا prompt. ⛔ «·» لا تلاصق رقمًا.
 * ========================================================================== */
(function () {
  'use strict';
  if (typeof window === 'undefined' || typeof document === 'undefined') return;     // node: لا واجهة
  var A = window.V2S_ASKLIB = {};
  var MOD = 'v2s_asklib';
  var AP = 'eg-administrative-prosecution';
  var NA = 'غير متاح بعد';
  var SCAN_CAP = 500;   // = SCAN_LIMIT في v2_asklib_routes.py (كان ناقص ⇒ ReferenceError في رسم «جاهز» ⇒ الشاشة بتقول «تعذّر الجلب» دايمًا)
  var DIG = '٠١٢٣٤٥٦٧٨٩';
  var ST_AR = { library: 'مكتبة', proposed: 'مقترحة', verified: 'معتمدة', rejected: 'مرفوضة' };
  var BATCH = 60;       // = DELETE_BATCH في v2_asklib_routes.py
  var SHOW_CAP = 80;    // أقصى عدد بطاقات في كل قايمة تنظيف (الزرار الجماعي بيشتغل على الكل)
  var WHY_AR = { missing: 'مش موجود', has_articles: 'اتدخلت منه مواد في قاعدة النصوص', keep_missing: 'النسخة الباقية مش موجودة', not_identical: 'مش مطابق للنسخة الباقية', not_empty: 'فيه نص' };
  var REASON_AR = { duplicate: 'نسخة مكررة', empty: 'شبه فاضي', manual: 'حذف يدوي' };
  var S = { view: null, state: 'idle', data: null, err: '', filter: 'ap', q: '', rows: {}, note: '', noteT: null,
            mode: 'ingest', c: { state: 'idle', data: null, err: '' }, w: { state: 'idle', data: null, err: '' } };

  function esc(s) { return String(s == null ? '' : s).replace(/[&<>"']/g, function (c) { return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]; }); }
  function ar(n) { return String(n == null ? '' : n).replace(/\d/g, function (d) { return DIG.charAt(+d); }); }
  function ep() { return window.EP || null; }
  function host() { return window.V2_HOST || {}; }
  function roleName() { try { if (typeof role !== 'undefined') return role; } catch (e) {} var E = ep(); return (E && E.role) || ''; }
  A.canWrite = function () { return roleName() === 'admin'; };
  A.owns = function (mod) { return !!(mod === MOD && window.V2_ON && window.V2SHELL && window.V2SHELL.on); };
  function isCurrent() { return !!(S.view && document.body.contains(S.view) && host().current && A.owns(host().current())); }
  function q1(sel, r) { return (r || document).querySelector(sel); }
  function row(id) { return S.rows[id] || (S.rows[id] = { track: null, law: null, prev: null, busy: false, err: '', done: null }); }
  function trackLabel(id) {
    var t = (S.data && S.data.tracks) || [];
    for (var i = 0; i < t.length; i++) if (t[i].id === id) return t[i].label;
    return id || '';
  }
  function item(id) { var it = (S.data && S.data.items) || []; for (var i = 0; i < it.length; i++) if (it[i].id === id) return it[i]; return null; }

  // ------------------------------------------------------------------ المصدر
  function load(force) {
    var E = ep();
    if (!E || !E.api || !E.authed) return;
    if (!force && S.state !== 'idle') return;
    S.state = 'loading';
    E.api('/v2/ask/library').then(function (d) {
      S.state = 'ready'; S.data = d; S.err = ''; redraw();
    }).catch(function (e) {
      if (e && e.status === 401) return;
      S.data = null;
      S.state = e && e.status === 404 ? 'closed' : 'error';
      S.err = (e && e.data && e.data.error) || '';
      redraw();
    });
  }
  function loadClean(force) {
    var E = ep();
    if (!E || !E.api || !E.authed) return;
    if (!force && S.c.state !== 'idle') return;
    if (!S.c.data) S.c.state = 'loading';          // تحديث وفيه بيانات ⇒ القديم يفضل ظاهر لحد ما الجديد يوصل
    E.api('/v2/ask/library/cleanup').then(function (d) {
      S.c = { state: 'ready', data: d, err: '' }; redraw();
    }).catch(function (e) {
      if (e && e.status === 401) return;
      S.c = { state: e && e.status === 404 ? 'closed' : 'error', data: null, err: (e && e.data && e.data.error) || '' };
      redraw();
    });
  }
  function loadWant(force) {
    var E = ep();
    if (!E || !E.api || !E.authed) return;
    if (!force && S.w.state !== 'idle') return;
    S.w.state = 'loading';
    E.api('/v2/ask/library/coverage').then(function (d) {
      S.w = { state: 'ready', data: d, err: '' }; redraw();
    }).catch(function (e) {
      if (e && e.status === 401) return;
      S.w = { state: e && e.status === 404 ? 'closed' : 'error', data: null, err: (e && e.data && e.data.error) || '' };
      redraw();
    });
  }
  function setNote(t) { S.note = t; clearTimeout(S.noteT); S.noteT = setTimeout(function () { S.note = ''; redraw(); }, 9000); }

  // ------------------------------------------------------------------ الرسم
  function statsHtml() {
    return pendingHtml() + statsCore();
  }
  // المنصة بتعدّ المواد في الخلفية (المسح بقى خفيف) ⇒ سطر هادي بدل «غير متاح بعد» من غير تفسير.
  function pendingHtml() {
    var n = S.data && S.data.pending;
    return n ? '<p class="al-mute" data-al-pending>لسه بنعدّ المواد في ' + esc(ar(n)) + ' مستند، حدّث بعد دقيقة. <button type="button" class="ep-bs" data-a="retry">حدّث</button></p>' : '';
  }
  function statsCore() {
    var st = S.data && S.data.stats;
    if (!st) return '<section class="al-sum"><h3>قاعدة النصوص</h3><p class="al-mute">ملخص القاعدة: ' + NA + '</p></section>';
    var tracks = Object.keys(st.articles || {});
    var cells = tracks.map(function (t) {
      var r = st.articles[t], parts = Object.keys(ST_AR).filter(function (k) { return r[k]; }).map(function (k) { return ar(r[k]) + ' ' + ST_AR[k]; });
      return '<div class="al-cell"><b>' + esc(trackLabel(t)) + '</b><span>' + esc(parts.join('، ') || 'لا مواد') + '</span></div>';
    }).join('');
    return '<section class="al-sum"><h3>قاعدة النصوص</h3><div class="al-cells">' + (cells || '<p class="al-mute">لا مواد في القاعدة بعد</p>')
      + '<div class="al-cell"><b>التصحيحات المعتمدة</b><span>' + esc(ar(st.corrections_approved || 0)) + '</span></div></div></section>';
  }
  function visibleItems() {
    var q = S.q.trim().toLowerCase();
    return ((S.data && S.data.items) || []).filter(function (it) {
      if (S.filter === 'ap' && it.suggested_track !== AP) return false;
      return !q || (it.title || '').toLowerCase().indexOf(q) > -1;
    });
  }
  function previewHtml(r) {
    var p = r.prev;
    if (!p) return '';
    var dup = p.duplicates && p.duplicates.length
      ? '<p class="al-warn" role="status">مواد مكررة (' + esc(ar(p.duplicates.length)) + '): ' + esc(p.duplicates.slice(0, 20).join('، ')) + (p.duplicates.length > 20 ? '…' : '') + '</p>' : '';
    var list = p.preview.map(function (a) { return '<li><b>مادة ' + esc(a.article_no) + '</b><span>' + esc(a.text) + '</span></li>'; }).join('');
    return '<div class="al-prev"><p class="al-lead">المعاينة: ' + esc(ar(p.articles)) + ' مادة' + (p.law_key ? ' من القانون ' + esc(p.law_key) : '') + '. هذه أول ' + esc(ar(p.preview.length)) + ' فقط.</p>'
      + dup + '<ol class="al-arts">' + list + '</ol></div>';
  }
  function resultHtml(r) {
    if (!r.done) return '';
    if (r.done.applied !== true) return '<p class="al-warn" role="status">لم يُدخل شيء</p>';
    var c = r.done.counts;
    var txt = c ? 'اتضاف ' + ar(c.inserted) + '، واتحدّث ' + ar(c.updated) + '، واتساب كما هو ' + ar(c.kept) : 'تم إدخال المواد';
    return '<p class="al-ok" role="status">' + esc(txt) + '</p>';
  }
  function cardHtml(it) {
    var r = row(it.id), tracks = S.data.tracks || [];
    var track = r.track != null ? r.track : (it.suggested_track || '');
    var law = r.law != null ? r.law : (it.law_key || '');
    var opts = '<option value=""' + (track ? '' : ' selected') + '>اختر التخصص</option>' + tracks.map(function (t) {
      return '<option value="' + esc(t.id) + '"' + (t.id === track ? ' selected' : '') + '>' + esc(t.label) + '</option>';
    }).join('');
    var ing = it.ingested || { total: 0, by_status: {} };
    var ingTxt = ing.total ? 'اتدخل منه ' + ar(ing.total) + ' مادة' : 'لم يُدخل منه شيء';
    var meta = [it.law_number ? 'قانون ' + it.law_number : 'بلا رقم قانون', it.country, it.category].filter(Boolean).join('، ');
    var w = A.canWrite();
    var canIngest = w && r.prev && r.prev.articles > 0 && !r.busy;
    return '<article class="al-card" data-id="' + esc(it.id) + '"><div class="al-top"><h4>' + esc(it.title || 'بلا عنوان') + '</h4>'
      + (it.suggested_track ? '<span class="al-chip">مقترح: ' + esc(trackLabel(it.suggested_track)) + '</span>' : '<span class="al-chip off">بلا تخصص مقترح</span>') + '</div>'
      + '<p class="al-meta">' + esc(meta) + '</p>'
      + '<p class="al-meta">وُجدت ' + esc(it.articles_found == null ? NA : ar(it.articles_found) + ' مادة') + '، ' + esc(ingTxt) + '</p>'
      + '<div class="al-form"><label>التخصص<select data-f="track">' + opts + '</select></label>'
      + '<label>رقم القانون (اختياري)<input type="text" dir="ltr" data-f="law" maxlength="20" placeholder="117/1958" value="' + esc(law) + '"></label></div>'
      + (r.err ? '<div class="al-err" role="alert">' + esc(r.err) + '</div>' : '')
      + resultHtml(r) + previewHtml(r)
      + (w ? '<div class="al-acts"><button type="button" class="ep-b2" data-a="prev" data-id="' + esc(it.id) + '"' + (r.busy ? ' disabled' : '') + '>' + (r.busy === 'prev' ? 'جارٍ التقسيم…' : 'جرّب التقسيم') + '</button>'
        + '<button type="button" class="ep-b1" data-a="ingest" data-id="' + esc(it.id) + '"' + (canIngest ? '' : ' disabled') + '>أدخل المواد</button></div>'
        : '<p class="al-mute">الإدخال للأدمن فقط</p>')
      + '</article>';
  }
  function listHtml() {
    var items = visibleItems();
    if (!items.length) return '<div class="al-empty"><b>لا مستندات مطابقة</b><p>' + (S.filter === 'ap' ? 'جرّب «الكل» لعرض كل مستندات المكتبة.' : 'غيّر كلمة البحث.') + '</p></div>';
    return '<div class="al-grid">' + items.map(cardHtml).join('') + '</div>';
  }
  function stateBlock(st, msg) {
    if (st === 'idle' || st === 'loading') return '<div class="al-skel" role="status" aria-label="جارٍ التحميل"><i></i><i></i><i></i></div>';
    if (st === 'closed') return '<div class="al-empty"><b>الميزة لسه ما وصلتش المنصة</b><p>هتظهر هنا تلقائيًا أول ما تتفعّل.</p></div>';
    return '<div class="al-warnbox" role="alert">تعذّر جلب مستندات المكتبة' + (msg ? ': ' + esc(msg) : '') + '، وليس معناه أنها فارغة<button type="button" class="ep-bs" data-a="retry">أعد المحاولة</button></div>';
  }
  function modeBar() {
    function tab(k, label) { return '<button type="button" class="al-tab' + (S.mode === k ? ' on' : '') + '" data-a="mode" data-k="' + k + '">' + label + '</button>'; }
    return '<div class="al-seg al-modes" role="group" aria-label="القسم">' + tab('ingest', 'إدخال القوانين') + tab('want', 'القوانين الناقصة') + tab('clean', 'تنظيف المكتبة') + '</div>';
  }
  function ingestHtml() {
    var lead = '<p class="al-lead">مستندات مكتبة المنصة اللي تتحوّل مواد في قاعدة نصوص «اسأل». ';
    if (S.state !== 'ready') return lead + '</p>' + stateBlock(S.state, S.err);
    return lead + ((S.data.items || []).length >= SCAN_CAP ? 'أول ' + esc(ar(SCAN_CAP)) + ' مستند فقط، ابحث بالعنوان.' : esc(ar((S.data.items || []).length)) + ' مستند في المكتبة.') + '</p>'
      + statsHtml()
      + '<div class="al-bar"><div class="al-seg" role="group" aria-label="الفلتر">'
      + '<button type="button" class="al-tab' + (S.filter === 'ap' ? ' on' : '') + '" data-a="filter" data-k="ap">المقترح للنيابة الإدارية</button>'
      + '<button type="button" class="al-tab' + (S.filter === 'all' ? ' on' : '') + '" data-a="filter" data-k="all">الكل</button></div>'
      + '<input type="search" id="alQ" class="al-q" placeholder="ابحث بالعنوان" value="' + esc(S.q) + '" aria-label="بحث بالعنوان"></div>'
      + '<div id="alList">' + listHtml() + '</div>';
  }

  // ------------------------------------------------------------------ تنظيف المكتبة
  function day(t) { return ar(String(t || '').slice(0, 10)); }
  function more(n) { return n > SHOW_CAP ? '<p class="al-mute">ظاهر أول ' + esc(ar(SHOW_CAP)) + ' من ' + esc(ar(n)) + '، والباقي بيظهر بعد ما تنظّف دول.</p>' : ''; }
  function dupItems(groups) {
    var out = [];
    groups.forEach(function (g) { g.extras.forEach(function (x) { out.push({ id: x.id, dup_of: g.keep.id }); }); });
    return out;
  }
  function tinyItems(tiny) { return tiny.filter(function (t) { return !t.ingested; }).map(function (t) { return { id: t.id }; }); }
  function groupHtml(g, i, w) {
    var k = g.keep;
    return '<article class="al-card"><div class="al-top"><h4>' + esc(k.title || 'بلا عنوان') + '</h4><span class="al-chip">هيفضل</span></div>'
      + '<p class="al-meta">' + esc(ar(k.chars)) + ' حرف' + (k.ingested ? '، واتدخل منه ' + esc(ar(k.ingested)) + ' مادة' : '') + '</p>'
      + '<p class="al-meta">نسخ مطابقة له بالحرف (' + esc(ar(g.extras.length)) + '):</p>'
      + '<ul class="al-dups">' + g.extras.map(function (x) { return '<li><span>' + esc(x.title || 'بلا عنوان') + '</span>' + (x.created_at ? '<small>اتضاف ' + esc(day(x.created_at)) + '</small>' : '') + '</li>'; }).join('') + '</ul>'
      + (w ? '<div class="al-acts"><button type="button" class="ep-b2" data-a="deldup" data-k="' + i + '">احذف النسخ</button></div>' : '')
      + '</article>';
  }
  function tinyHtml(t, w) {
    return '<article class="al-card"><div class="al-top"><h4>' + esc(t.title || 'بلا عنوان') + '</h4><span class="al-chip off">' + esc(ar(t.chars)) + ' حرف</span></div>'
      + '<p class="al-meta al-head">' + esc(t.head || 'بلا نص') + '</p>'
      + (t.ingested ? '<p class="al-mute">اتدخلت منه مواد في قاعدة النصوص، فمش هيتحذف.</p>'
        : (w ? '<div class="al-acts"><button type="button" class="ep-b2" data-a="delone" data-id="' + esc(t.id) + '">احذف</button></div>' : ''))
      + '</article>';
  }
  function goneHtml(x, w) {
    var meta = [REASON_AR[x.reason] || '', x.deleted_at ? 'اتحذف ' + day(x.deleted_at) : ''].filter(Boolean).join('، ');
    return '<li><div><b>' + esc(x.title || 'بلا عنوان') + '</b><small>' + esc(meta) + '</small></div>'
      + (w ? '<button type="button" class="ep-bs" data-a="restore" data-id="' + esc(x.id) + '">رجّع</button>' : '') + '</li>';
  }
  function cleanHtml() {
    var lead = '<p class="al-lead">شيل من مكتبة المنصة النسخ المكررة والمستندات اللي طلعت فاضية. الحذف هنا مش نهائي، وأي مستند تقدر ترجّعه من «المحذوفات».</p>';
    if (S.c.state !== 'ready') return lead + stateBlock(S.c.state, S.c.err);
    var d = S.c.data, w = A.canWrite(), dups = dupItems(d.groups), tiny = tinyItems(d.tiny);
    var cell = function (label, n) { return '<div class="al-cell"><b>' + label + '</b><span>' + esc(ar(n)) + ' مستند</span></div>'; };
    return lead
      + (d.pending ? '<p class="al-mute" data-al-pending>لسه بنفحص ' + esc(ar(d.pending)) + ' مستند، والأرقام ممكن تزيد. حدّث بعد دقيقة. <button type="button" class="ep-bs" data-a="retry">حدّث</button></p>' : '')
      + '<section class="al-sum"><div class="al-cells">' + cell('المكتبة', d.total) + cell('نسخ مكررة', dups.length) + cell('شبه فاضية', d.tiny.length) + cell('المحذوفات', d.deleted.length) + '</div></section>'
      + '<div class="al-sec"><h3>نسخ مكررة</h3>' + (w && dups.length ? '<button type="button" class="ep-b1" data-a="delalldup">احذف كل النسخ المكررة</button>' : '') + '</div>'
      + (d.groups.length ? '<div class="al-grid">' + d.groups.slice(0, SHOW_CAP).map(function (g, i) { return groupHtml(g, i, w); }).join('') + '</div>' + more(d.groups.length)
        : '<div class="al-empty"><b>مفيش نسخ مكررة</b><p>كل مستند في المكتبة نصه مختلف عن الباقي.</p></div>')
      + '<div class="al-sec"><h3>مستندات شبه فاضية</h3>' + (w && tiny.length ? '<button type="button" class="ep-b2" data-a="delalltiny">احذف كل شبه الفاضية</button>' : '') + '</div>'
      + '<p class="al-mute al-gap">مستندات نصها أقل من ' + esc(ar(d.tiny_chars)) + ' حرف، وغالبًا ملفها ما اتقراش.</p>'
      + (d.tiny.length ? '<div class="al-grid">' + d.tiny.slice(0, SHOW_CAP).map(function (t) { return tinyHtml(t, w); }).join('') + '</div>' + more(d.tiny.length)
        : '<div class="al-empty"><b>مفيش مستندات شبه فاضية</b></div>')
      + '<div class="al-sec"><h3>المحذوفات</h3></div>'
      + (d.deleted.length ? '<ul class="al-gone">' + d.deleted.slice(0, SHOW_CAP).map(function (x) { return goneHtml(x, w); }).join('') + '</ul>' + more(d.deleted.length)
        : '<div class="al-empty"><b>مفيش محذوفات</b><p>أي مستند تحذفه هيظهر هنا وتقدر ترجّعه.</p></div>');
  }
  // ------------------------------------------------------------------ القوانين الناقصة
  function wantRow(c, l, w) {
    var has = l.articles > 0;
    return '<li class="' + (has ? 'has' : 'miss') + '"><div><b>' + esc(l.title) + '</b><small>' + esc(ar(l.key)) + '</small></div>'
      + '<span class="al-chip' + (has ? '' : ' off') + '">' + (has ? 'موجود، ' + esc(ar(l.articles)) + ' مادة' : 'ناقص') + '</span>'
      + (w && !has ? '<button type="button" class="ep-bs" data-a="wantadd" data-c="' + esc(c.id) + '" data-k="' + esc(l.key) + '">حط النص</button>' : '') + '</li>';
  }
  function wantCountry(c, w) {
    var laws = c.laws.slice().sort(function (a, b) { return (a.articles > 0) - (b.articles > 0); });
    return '<section class="al-want"><div class="al-sec"><h3>' + esc(c.label) + '</h3>'
      + (w ? '<button type="button" class="ep-b2" data-a="wantadd" data-c="' + esc(c.id) + '" data-k="">أضف قانون تاني</button>' : '') + '</div>'
      + '<p class="al-mute al-gap">في القاعدة ' + esc(ar(c.base_laws)) + ' قانون و' + esc(ar(c.base_articles)) + ' مادة. '
      + (c.missing ? 'ناقص ' + esc(ar(c.missing)) + ' من القوانين الأساسية.' : 'القوانين الأساسية كلها موجودة.')
      + (c.official ? ' المصدر الرسمي: ' + esc(c.official) + '.' : '') + '</p>'
      + '<ul class="al-wl">' + laws.map(function (l) { return wantRow(c, l, w); }).join('') + '</ul></section>';
  }
  function wantHtml() {
    var lead = '<p class="al-lead">القوانين الأساسية لكل بلد، والموجود منها في قاعدة «اسأل». أي قانون ناقص تجيب نصه من مصدره الرسمي وتحطه هنا في مكانه.</p>';
    if (S.w.state !== 'ready') return lead + stateBlock(S.w.state, S.w.err);
    var d = S.w.data, w = A.canWrite();
    if (!d.countries.length) return lead + '<div class="al-empty"><b>قواعد البلاد لسه ما اتحمّلتش</b><p>هتظهر هنا أول ما تتحمّل.</p></div>';
    return lead + d.countries.map(function (c) { return wantCountry(c, w); }).join('')
      + (d.later.length ? '<p class="al-mute al-later">بلاد لسه مالهاش قاعدة: ' + esc(d.later.join('، ')) + '.</p>' : '');
  }
  function draw(v) {
    v.innerHTML = '<div class="v2s-al">' + modeBar() + (S.note ? '<p class="al-ok" role="status">' + esc(S.note) + '</p>' : '')
      + (S.mode === 'clean' ? cleanHtml() : S.mode === 'want' ? wantHtml() : ingestHtml()) + '</div>';
  }
  function drawList() { var l = q1('#alList', S.view); if (l) l.innerHTML = listHtml(); }
  function modalOpen() { return !!document.getElementById('epModal'); }
  function redraw() {
    if (!isCurrent() || modalOpen()) return;
    var y = window.pageYOffset;
    draw(S.view);
    if (window.pageYOffset !== y) window.scrollTo(0, y);
  }

  // ------------------------------------------------------------------ كتابة
  function errText(e) {
    if (e && e.status === 401) return 'انتهت الجلسة، سجّل الدخول من جديد ثم جرّب';
    if (e && e.status === 404 && e.data && e.data.bridge_missing) return 'الميزة لسه ما وصلتش المنصة';
    return (e && e.data && e.data.error) || 'تعذّر التنفيذ الآن، جرّب بعد قليل';
  }
  function body(it, r, extra) {
    var o = { track: r.track != null ? r.track : (it.suggested_track || ''), ref_id: it.id };
    var law = (r.law != null ? r.law : (it.law_key || '')).trim();
    if (law) o.law = law;
    for (var k in extra) o[k] = extra[k];
    return o;
  }
  function preview(id) {
    var it = item(id), r = row(id), E = ep();
    if (!it || !E || r.busy) return;
    var b = body(it, r, {});
    if (!b.track) { r.err = 'اختر التخصص أولًا'; drawList(); return; }
    var key = b.track + '|' + (b.law || '');       // لقطة القيم وقت الطلب: لو اتغيّرت قبل ما الرد يوصل نتجاهل الرد
    r.busy = 'prev'; r.err = ''; r.done = null; drawList();
    E.api('/v2/ask/library/preview', { method: 'POST', body: b }).then(function (d) {
      r.busy = false;
      if (body(it, r, {}).track + '|' + (body(it, r, {}).law || '') === key) r.prev = d;
      drawList();
    }).catch(function (e) {
      r.busy = false;
      if (body(it, r, {}).track + '|' + (body(it, r, {}).law || '') === key) { r.prev = null; r.err = errText(e); }
      drawList();
    });
  }
  function sheet(title, html) {
    if (typeof window.openModal !== 'function') return null;
    var s = window.openModal(title, '<div class="v3m v2s-al-sb">' + html + '</div>');
    var x = s.querySelector('[data-x]');
    if (x) { x.setAttribute('aria-label', 'إغلاق'); x.onclick = function () { if (!s.dataset.busy) window.closeModal(); }; }
    return s;
  }
  function ingestSheet(id) {
    var it = item(id), r = row(id), p = r && r.prev;
    if (!it || !p) return;
    var b = body(it, r, { confirmed: true });
    var s = sheet('أدخل المواد', '<p class="mc-lead">هتدخل ' + esc(ar(p.articles)) + ' مادة من «' + esc(it.title) + '» في تخصص «' + esc(trackLabel(b.track)) + '».'
      + (p.duplicates && p.duplicates.length ? ' فيه ' + esc(ar(p.duplicates.length)) + ' مادة مكررة، والمكرر بيتحدّث أو بيتساب حسب حالته.' : '')
      + '</p><div id="alErr" role="alert"></div><div class="acts"><button type="button" class="ep-b1" id="alGo">أدخل المواد</button><button type="button" class="ep-b2" id="alNo">رجوع</button></div>');
    if (!s) return;
    var go = q1('#alGo', s), no = q1('#alNo', s), err = q1('#alErr', s);
    no.onclick = function () { if (!s.dataset.busy) window.closeModal(); };
    go.onclick = function () {
      if (s.dataset.busy) return;
      s.dataset.busy = '1'; go.disabled = true; no.disabled = true; go.textContent = 'جارٍ الإدخال…'; err.innerHTML = '';
      ep().api('/v2/ask/library/ingest', { method: 'POST', body: b }).then(function (d) {
        delete s.dataset.busy; window.closeModal();
        r.done = d; r.prev = null; r.err = '';
        setNote('اتدخلت مواد «' + it.title + '»');
        load(true); redraw();
      }).catch(function (e) {
        delete s.dataset.busy; go.disabled = false; no.disabled = false; go.textContent = 'أدخل المواد';
        err.innerHTML = '<div class="al-err">' + esc(errText(e)) + '</div>';
        if (e && e.data && e.data.no_reply) load(true);
      });
    };
    setTimeout(function () { try { no.focus(); } catch (e) {} }, 30);
  }

  // ------------------------------------------------------------------ تنظيف: كتابة
  // الحذف على دفعات (٦٠ في المرة) واحدة ورا التانية؛ لو دفعة وقعت نقف ونقول اتحذف كام قبلها.
  function runDelete(items, reason) {
    var E = ep(), res = { deleted: 0, skipped: [] }, i = 0;
    function next() {
      if (i >= items.length) return Promise.resolve(res);
      var part = items.slice(i, i + BATCH);
      i += BATCH;
      return E.api('/v2/ask/library/delete', { method: 'POST', body: { items: part, reason: reason, confirmed: true } }).then(function (d) {
        res.deleted += (d.deleted || []).length;
        res.skipped = res.skipped.concat(d.skipped || []);
        return next();
      }, function (e) { e.done = res.deleted; throw e; });
    }
    return next();
  }
  function skippedText(sk) {
    if (!sk.length) return '';
    var by = {}, parts = [];
    sk.forEach(function (x) { by[x.why] = (by[x.why] || 0) + 1; });
    Object.keys(by).forEach(function (k) { parts.push(ar(by[k]) + ' ' + (WHY_AR[k] || 'لسبب غير معروف')); });
    return '، واتساب ' + ar(sk.length) + ' (' + parts.join('، ') + ')';
  }
  function confirmSheet(title, lead, goLabel, run) {
    var s = sheet(title, '<p class="mc-lead">' + lead + '</p><div id="alErr" role="alert"></div><div class="acts"><button type="button" class="ep-b1" id="alGo">' + esc(goLabel) + '</button><button type="button" class="ep-b2" id="alNo">رجوع</button></div>');
    if (!s) return;
    var go = q1('#alGo', s), no = q1('#alNo', s), err = q1('#alErr', s);
    var shut = function () { if (!s.dataset.busy) { window.closeModal(); redraw(); } };
    no.onclick = shut;
    var x = s.querySelector('[data-x]'); if (x) x.onclick = shut;
    go.onclick = function () {
      if (s.dataset.busy) return;
      s.dataset.busy = '1'; go.disabled = true; no.disabled = true; go.textContent = 'جارٍ التنفيذ…'; err.innerHTML = '';
      run().then(function (msg) {
        delete s.dataset.busy; window.closeModal();
        setNote(msg); loadClean(true); redraw();
      }).catch(function (e) {
        delete s.dataset.busy; go.disabled = false; no.disabled = false; go.textContent = goLabel;
        err.innerHTML = '<div class="al-err">' + esc(errText(e)) + (e && e.done ? '. اتحذف ' + esc(ar(e.done)) + ' مستند قبل التوقف.' : '') + '</div>';
        loadClean(true);
      });
    };
    setTimeout(function () { try { no.focus(); } catch (e) {} }, 30);
  }
  function deleteSheet(items, reason, title, lead) {
    if (!items.length) return;
    confirmSheet(title, lead + ' الحذف مش نهائي، وتقدر ترجّع أي مستند من «المحذوفات».', title, function () {
      return runDelete(items, reason).then(function (r) { return 'اتحذف ' + ar(r.deleted) + ' مستند' + skippedText(r.skipped); });
    });
  }
  function cleanAct(k, a) {
    var d = S.c.data;
    if (!d) return;
    if (k === 'delalldup') {
      var all = dupItems(d.groups);
      deleteSheet(all, 'duplicate', 'احذف كل النسخ المكررة', 'هتتحذف ' + esc(ar(all.length)) + ' نسخة مكررة، ومن كل مجموعة هيفضل مستند واحد.');
    } else if (k === 'deldup') {
      var g = d.groups[+a.getAttribute('data-k')];
      if (g) deleteSheet(dupItems([g]), 'duplicate', 'احذف النسخ', 'هتتحذف ' + esc(ar(g.extras.length)) + ' نسخة مطابقة لـ«' + esc(g.keep.title) + '»، وهو هيفضل.');
    } else if (k === 'delalltiny') {
      var tiny = tinyItems(d.tiny);
      deleteSheet(tiny, 'empty', 'احذف كل شبه الفاضية', 'هتتحذف ' + esc(ar(tiny.length)) + ' مستند نصه أقل من ' + esc(ar(d.tiny_chars)) + ' حرف.');
    } else if (k === 'delone') {
      var id = a.getAttribute('data-id'), t = d.tiny.filter(function (x) { return x.id === id; })[0];
      if (t && !t.ingested) deleteSheet([{ id: id }], 'empty', 'احذف المستند', 'هيتحذف «' + esc(t.title) + '».');
    } else if (k === 'restore') {
      var rid = a.getAttribute('data-id'), x = d.deleted.filter(function (y) { return y.id === rid; })[0];
      if (x) confirmSheet('رجّع المستند', 'هيرجع «' + esc(x.title) + '» للمكتبة زي ما كان.', 'رجّع', function () {
        return ep().api('/v2/ask/library/restore', { method: 'POST', body: { ids: [rid], confirmed: true } }).then(function (r) {
          return (r.restored || []).length ? 'رجع «' + x.title + '» للمكتبة' : 'المستند مش موجود';
        });
      });
    }
  }

  // ------------------------------------------------------------------ القوانين الناقصة: حط النص
  function wantSheet(cid, key) {
    var d = S.w.data, c = d && d.countries.filter(function (x) { return x.id === cid; })[0];
    if (!c) return;
    var l = c.laws.filter(function (x) { return x.key === key; })[0] || { key: '', title: '' };
    var s = sheet(l.title ? 'حط نص القانون' : 'أضف قانون', '<p class="mc-lead">البلد: ' + esc(c.label) + '. الصق النص كامل من مصدره الرسمي، وهيتقسم مواد لوحده.</p>'
      + '<div class="al-wf"><label>اسم القانون<input id="wfTitle" maxlength="300" value="' + esc(l.title) + '"></label>'
      + '<label>النوع<select id="wfKind"><option value="law">قانون</option><option value="regulation">لائحة</option><option value="decision">قرار</option><option value="other">أخرى (مرسوم أو نظام أو أمر)</option></select></label>'
      + '<label>الرقم والسنة<input id="wfLaw" maxlength="20" inputmode="text" placeholder="14/2025" value="' + esc(l.key) + '"></label>'
      + '<label class="wide">رابط المصدر الرسمي<input id="wfUrl" maxlength="600" dir="ltr" placeholder="https://"></label>'
      + '<label class="wide">نص القانون<textarea id="wfText" rows="5" placeholder="المادة 1 …"></textarea></label></div>'
      + '<div id="wfPrev"></div><div id="alErr" role="alert"></div>'
      + '<div class="acts"><button type="button" class="ep-b1" id="alGo" disabled>أدخل المواد</button><button type="button" class="ep-b2" id="wfTry">جرّب التقسيم</button><button type="button" class="ep-b2" id="alNo">رجوع</button></div>');
    if (!s) return;
    var go = q1('#alGo', s), tryB = q1('#wfTry', s), no = q1('#alNo', s), err = q1('#alErr', s), pv = q1('#wfPrev', s), ok = '';
    function vals() {
      var k = q1('#wfKind', s).value;
      return { country: cid, kind: k === 'other' ? 'law' : k, law: q1('#wfLaw', s).value.trim(), title: q1('#wfTitle', s).value.trim(),
               source_url: q1('#wfUrl', s).value.trim(), text: q1('#wfText', s).value };
    }
    function sig(b) { return [b.kind, b.law, b.title, b.source_url, b.text.length, b.text.slice(0, 200)].join('|'); }
    function stale() { ok = ''; go.disabled = true; pv.innerHTML = ''; }
    function busy(on, btn, label) { if (on) s.dataset.busy = '1'; else delete s.dataset.busy; go.disabled = on || !ok; tryB.disabled = on; no.disabled = on; btn.textContent = label; }
    s.querySelector('.al-wf').oninput = stale; s.querySelector('.al-wf').onchange = stale;
    no.onclick = function () { if (!s.dataset.busy) window.closeModal(); };
    tryB.onclick = function () {
      if (s.dataset.busy) return;
      var b = vals(), k = sig(b);
      err.innerHTML = ''; stale(); busy(true, tryB, 'جارٍ التقسيم…');
      ep().api('/v2/ask/library/law-text/preview', { method: 'POST', body: b }).then(function (r) {
        busy(false, tryB, 'جرّب التقسيم');
        if (sig(vals()) !== k) return;
        if (!r.articles) { pv.innerHTML = '<div class="al-warn">ما لقيناش مواد في النص. اتأكد إن كل مادة بتبدأ بكلمة «المادة» ورقمها.</div>'; return; }
        var li = function (a) { return '<li><b>مادة ' + esc(ar(a.article_no)) + '</b><span>' + esc(a.text) + '</span></li>'; };
        pv.innerHTML = '<div class="al-prev"><p class="al-mute al-gap">اتقسم ' + esc(ar(r.articles)) + ' مادة، ومرجعه ' + esc(ar(r.law_key)) + '.'
          + (r.existing ? ' القانون ده له ' + esc(ar(r.existing)) + ' مادة في القاعدة، والمختلف منها هيتحدّث.' : '')
          + (r.duplicates.length ? ' فيه ' + esc(ar(r.duplicates.length)) + ' رقم مادة مكرر، راجع النص.' : '') + '</p>'
          + '<ul class="al-arts">' + r.preview.map(li).join('') + (r.last.length ? '<li class="gap">…</li>' + r.last.map(li).join('') : '') + '</ul></div>';
        ok = k; go.disabled = false;
      }).catch(function (e) { busy(false, tryB, 'جرّب التقسيم'); err.innerHTML = '<div class="al-err">' + esc(errText(e)) + '</div>'; });
    };
    go.onclick = function () {
      var b = vals();
      if (s.dataset.busy || !ok || sig(b) !== ok) return;
      b.confirmed = true; err.innerHTML = ''; busy(true, go, 'جارٍ الإدخال…');
      ep().api('/v2/ask/library/law-text', { method: 'POST', body: b }).then(function (r) {
        delete s.dataset.busy; window.closeModal();
        var n = r.counts ? r.counts.inserted + r.counts.updated : r.articles;
        setNote('اتدخل «' + b.title + '» في قاعدة ' + c.label + ': ' + ar(n) + ' مادة');
        loadWant(true); redraw();
      }).catch(function (e) {
        busy(false, go, 'أدخل المواد');
        err.innerHTML = '<div class="al-err">' + esc(errText(e)) + '</div>';
        if (e && e.data && e.data.no_reply) loadWant(true);
      });
    };
    setTimeout(function () { try { q1(l.title ? '#wfUrl' : '#wfTitle', s).focus(); } catch (e) {} }, 30);
  }

  // ------------------------------------------------------------------ أحداث
  function onClick(e) {
    var a = e.target.closest ? e.target.closest('[data-a]') : null;
    if (!a || !S.view.contains(a) || a.disabled) return;
    var k = a.getAttribute('data-a'), id = a.getAttribute('data-id');
    if (k === 'mode') { var m = a.getAttribute('data-k'); S.mode = m === 'clean' || m === 'want' ? m : 'ingest'; if (S.mode === 'clean') loadClean(false); if (S.mode === 'want') loadWant(false); redraw(); }
    else if (k === 'filter') { S.filter = a.getAttribute('data-k'); redraw(); }
    else if (k === 'retry') { if (S.mode === 'clean') loadClean(true); else if (S.mode === 'want') loadWant(true); else load(true); redraw(); }
    else if (k === 'wantadd') { if (A.canWrite()) wantSheet(a.getAttribute('data-c'), a.getAttribute('data-k') || ''); }
    else if (/^(del|restore)/.test(k)) { if (A.canWrite()) cleanAct(k, a); }
    else if (k === 'prev' && A.canWrite()) preview(id);
    else if (k === 'ingest' && A.canWrite()) ingestSheet(id);
  }
  function onInput(e) {
    var t = e.target;
    if (t && t.id === 'alQ') { S.q = t.value; drawList(); return; }
    var card = t && t.closest ? t.closest('.al-card') : null, f = t && t.getAttribute ? t.getAttribute('data-f') : null;
    if (!card || !f) return;
    var r = row(card.getAttribute('data-id'));
    if (f === 'track') r.track = t.value; else r.law = t.value;
    r.prev = null; r.err = ''; r.done = null;       // أي تغيير في التخصص/القانون يلغي المعاينة القديمة
    var btn = card.querySelector('[data-a="ingest"]'); if (btn) btn.disabled = true;
    var pv = card.querySelector('.al-prev'); if (pv) pv.remove();
  }
  A.render = function (mod, view) {
    S.view = view;
    view.onclick = onClick; view.oninput = onInput; view.onchange = onInput;
    var E = ep();
    if (E && E.authed) load(false);
    draw(view);
  };
  A._state = S;
  (window.V2SEC = window.V2SEC || {}).asklib = { owns: A.owns, render: A.render };
})();
