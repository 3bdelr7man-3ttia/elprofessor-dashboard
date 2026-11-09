/* ============================================================================
 * v2s/asklib.js — «المحتوى ‹ أدخل قوانين المكتبة»: مستندات مكتبة المنصة ⇒ تقسيمها مواد في قاعدة نصوص «اسأل».
 * ١) ملخص القاعدة (مواد كل تخصص وحالة + التصحيحات المعتمدة) · ٢) قائمة المستندات (فلتر «المقترح للنيابة الإدارية» / «الكل» + بحث بالعنوان)
 * ٣) لكل مستند: التخصص ورقم القانون ثم «جرّب التقسيم» (معاينة بلا كتابة) ثم «أدخل المواد» (ورقة تأكيد ثم كتابة + تدقيق).
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
  var DIG = '٠١٢٣٤٥٦٧٨٩';
  var ST_AR = { library: 'مكتبة', proposed: 'مقترحة', verified: 'معتمدة', rejected: 'مرفوضة' };
  var S = { view: null, state: 'idle', data: null, err: '', filter: 'ap', q: '', rows: {}, note: '', noteT: null };

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
  function stateBlock() {
    if (S.state === 'idle' || S.state === 'loading') return '<div class="al-skel" role="status" aria-label="جارٍ التحميل"><i></i><i></i><i></i></div>';
    if (S.state === 'closed') return '<div class="al-empty"><b>الميزة لسه ما وصلتش المنصة</b><p>هتظهر هنا تلقائيًا أول ما تتفعّل.</p></div>';
    return '<div class="al-warnbox" role="alert">تعذّر جلب مستندات المكتبة' + (S.err ? ': ' + esc(S.err) : '') + '، وليس معناه أنها فارغة<button type="button" class="ep-bs" data-a="retry">أعد المحاولة</button></div>';
  }
  function draw(v) {
    if (S.state !== 'ready') { v.innerHTML = '<div class="v2s-al"><p class="al-lead">مستندات مكتبة المنصة اللي تتحوّل مواد في قاعدة نصوص «اسأل».</p>' + stateBlock() + '</div>'; return; }
    v.innerHTML = '<div class="v2s-al">' + (S.note ? '<p class="al-ok" role="status">' + esc(S.note) + '</p>' : '')
      + '<p class="al-lead">مستندات مكتبة المنصة اللي تتحوّل مواد في قاعدة نصوص «اسأل». ' + ((S.data.items || []).length >= SCAN_CAP ? 'أول ' + esc(ar(SCAN_CAP)) + ' مستند فقط، ابحث بالعنوان.' : esc(ar((S.data.items || []).length)) + ' مستند في المكتبة.') + '</p>'
      + statsHtml()
      + '<div class="al-bar"><div class="al-seg" role="group" aria-label="الفلتر">'
      + '<button type="button" class="al-tab' + (S.filter === 'ap' ? ' on' : '') + '" data-a="filter" data-k="ap">المقترح للنيابة الإدارية</button>'
      + '<button type="button" class="al-tab' + (S.filter === 'all' ? ' on' : '') + '" data-a="filter" data-k="all">الكل</button></div>'
      + '<input type="search" id="alQ" class="al-q" placeholder="ابحث بالعنوان" value="' + esc(S.q) + '" aria-label="بحث بالعنوان"></div>'
      + '<div id="alList">' + listHtml() + '</div></div>';
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

  // ------------------------------------------------------------------ أحداث
  function onClick(e) {
    var a = e.target.closest ? e.target.closest('[data-a]') : null;
    if (!a || !S.view.contains(a) || a.disabled) return;
    var k = a.getAttribute('data-a'), id = a.getAttribute('data-id');
    if (k === 'filter') { S.filter = a.getAttribute('data-k'); redraw(); }
    else if (k === 'retry') { load(true); redraw(); }
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
