/* ============================================================================
 * v2s/course_editor.js — محرّر الدورات من الداشبورد (SPEC-C-courses §C1): قائمة «أنشئ دورة» · صفحة الدورة بأربع تبويبات (البيانات · الهيكل · الدروس ·
 * المراجعة والنشر) · محرّر الدرس التفاعلي والمسجّل والمباشر · «اطلب من المساعد». يُحمَّل بعد courses.js ويعمل من خلاله (`V2CO.kit`).
 *
 * ⛔ لا منطق عمل هنا: القاموس وعمليات القوائم وفرق الهيكل وأجسام الحفظ وخطة الرفع كلها من `V2L.courses2` (نقي، في v2-logic.js).
 * ⛔ كل كتابة من هنا: ورقة تأكيد أولًا، ثم مسار `/api/v2/courses2/*` بـ`confirmed:true` (والخادم يضع `by` من التوكن). ⛔ لا سعر ولا نسبة في أي شاشة.
 * ⛔ المفتاح مقفول افتراضيًا: الملف يُحمَّل دائمًا لكنه لا يرسم شيئًا إلا لو نادته courses.js (والغلاف الجديد شغّال).
 * ⛔ نصوص الأخطاء تُعرض كما ترجع من المنصة (عربية). الرفع المباشر لـBunny بـTUS من المتصفح (القطعة ٥ ميغابايت).
 * ========================================================================== */
(function () {
  'use strict';
  var L = window.V2L;
  if (!L || !L.courses2) return;
  var K = L.courses2;
  var CE = window.V2CE = {};

  // ------------------------------------------------------------------ حالة المحرّر (دورة واحدة مفتوحة في كل مرة)
  var E = null;
  var uidN = 0;
  function fresh(id) {
    return { id: id, course: null, state: 'idle', err: '', status: 0, tab: 'data', lesson: '', dd: null, sd: null, ld: {}, open: {}, picker: false, pv: {}, as: {}, up: {}, note: '', noteT: null,
             view: null, cases: null };
  }

  function esc(s) { return String(s == null ? '' : s).replace(/[&<>"']/g, function (c) { return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]; }); }
  function q(sel, root) { return (root || document).querySelector(sel); }
  function qa(sel, root) { return Array.prototype.slice.call((root || document).querySelectorAll(sel)); }
  function ar(n) { return String(Math.round(Number(n) || 0)).replace(/\d/g, function (d) { return '٠١٢٣٤٥٦٧٨٩'.charAt(+d); }); }
  function arDigits(t) { return String(t).replace(/\d/g, function (d) { return '٠١٢٣٤٥٦٧٨٩'.charAt(+d); }); }
  function kit() { return (window.V2CO && window.V2CO.kit) || null; }
  function api(method, path, body) {
    var o = { method: method };
    if (body !== undefined) o.body = body;
    return window.EP.api(path, o).catch(function (e) {
      // 409 من المنصة يُعرض نصه كما رجع (لا عبارة «تغيّرت الحالة» العامة)
      if (e && e.status === 409) { var e2 = new Error(e.message); e2.status = 400; e2.data = e.data; throw e2; }
      throw e;
    });
  }
  var BASE = '/v2/courses2';
  function enc(s) { return encodeURIComponent(s); }
  var NOREPLY = 'لم يصل رد. حدّث الصفحة وتأكّد مما حدث قبل أن تضغط مرة أخرى.';
  function errText(e) {
    if (e && e.status === 401) return 'انتهت الجلسة — سجّل الدخول من جديد ثم جرّب';
    var d = (e && e.data) || {};
    if (d.no_reply) return NOREPLY;
    if (typeof d.error === 'string' && d.error) return arDigits(d.error);
    return 'تعذّر تنفيذ العملية';
  }

  // ------------------------------------------------------------------ قراءة الدورة
  function lessonsOf(c) {
    var out = [], no = 0;
    ((c && c.outline && c.outline.units) || []).forEach(function (u, ui) {
      (u.lessons || []).forEach(function (l) { no++; out.push({ lesson: l, unit: u, ui: ui, no: l.no || no }); });
    });
    return out;
  }
  function lessonById(id) {
    var all = lessonsOf(E.course);
    for (var i = 0; i < all.length; i++) if (all[i].lesson.id === id) return all[i];
    return null;
  }
  // opts.resetData / opts.resetStruct: بعد حفظ ذلك الجزء نفسه نبدأ من نسخة المنصّة؛ غير ذلك المسودّة غير المحفوظة تبقى (حفظ درس لا يمسح هيكلًا لم يُحفظ).
  function setCourse(c, opts) {
    opts = opts || {};
    var firstLoad = !E.course;
    var keepDd = !firstLoad && !opts.resetData && dataDirty() ? E.dd : null, keepSd = !firstLoad && !opts.resetStruct && structDirty() ? E.sd : null;
    E.course = c;
    var m = c.meta || {};
    E.dd = keepDd || { title: m.title || '', subtitle: m.subtitle || '', description: m.description || '', cover: m.cover || '', level: m.level || '', outcomes: (m.outcomes || []).join('\n') };
    E.sd = keepSd || K.structFrom(c);
    var keep = {};
    lessonsOf(c).forEach(function (x) { if (E.ld[x.lesson.id]) keep[x.lesson.id] = E.ld[x.lesson.id]; });
    E.ld = keep;
    if (firstLoad || !lessonById(E.lesson)) E.lesson = '';
  }
  function dataDirty() { return JSON.stringify(K.dataBody(E.dd)) !== JSON.stringify(K.dataBody({ title: E.course.meta.title, subtitle: E.course.meta.subtitle, description: E.course.meta.description, cover: E.course.meta.cover, level: E.course.meta.level, outcomes: E.course.meta.outcomes || [] })); }
  function structDirty() { return K.structureDiff(K.structFrom(E.course), E.sd).changed; }
  function draftOf(id) {
    var x = lessonById(id);
    if (!x) return null;
    if (!E.ld[id]) E.ld[id] = K.draftFrom(x.lesson);
    return E.ld[id];
  }
  function lessonDirty(id) {
    var x = lessonById(id);
    if (!x || !E.ld[id]) return false;
    return JSON.stringify(K.lessonBody(x.lesson, E.ld[id])) !== JSON.stringify(K.lessonBody(x.lesson, K.draftFrom(x.lesson)));
  }
  function anyDirty() {
    if (!E.course) return false;
    if (dataDirty() || structDirty()) return true;
    return Object.keys(E.ld).some(lessonDirty);
  }
  function dirtyList() {
    var out = [];
    if (dataDirty()) out.push('بيانات الدورة');
    if (structDirty()) out.push('هيكل الدورة');
    Object.keys(E.ld).forEach(function (id) { if (lessonDirty(id)) { var x = lessonById(id); out.push('الدرس «' + (x ? x.lesson.title : id) + '»'); } });
    return out;
  }

  // ------------------------------------------------------------------ مسار القراءة
  function loadCourse(force) {
    if (E.state === 'loading') return;
    if (E.state === 'ready' && !force) return;
    E.state = 'loading';
    var id = E.id;
    window.EP.api(BASE + '/' + enc(id)).then(function (res) {
      if (!E || E.id !== id) return;
      E.state = 'ready';
      setCourse(res.course || {});
      paint();
    }).catch(function (e) {
      if (!E || E.id !== id) return;
      E.state = e && e.status === 404 ? 'closed' : 'error'; E.err = errText(e); E.status = (e && e.status) || 0;
      paint();
    });
  }

  // ------------------------------------------------------------------ أجزاء الرسم
  function chip(text, tone) { return '<span class="v2co-chip ' + (tone || '') + '">' + esc(text) + '</span>'; }
  var STATUS_TONE = { published: 'green', review: 'amber', changes: 'amber', draft: 'grey', paused: 'grey' };
  var STATE_TONE = { ready: 'green', missing_video: 'amber', draft: 'grey' };
  function uid() { uidN++; return 'ce' + uidN; }
  // حقل نص/منطقة: scope = المسار من جذر المسودة. data-p المسار، data-t النوع.
  function field(scope, path, val, o) {
    o = o || {};
    var id = uid(), t = o.bool ? 'bool' : (o.t || '');
    var attrs = ' id="' + id + '" data-s="' + scope + '" data-p="' + esc(path) + '"' + (t ? ' data-t="' + t + '"' : '') + (o.ph ? ' placeholder="' + esc(o.ph) + '"' : '') + (o.ltr ? ' dir="ltr"' : '');
    var ctl;
    if (o.sel) ctl = '<select' + attrs + '>' + o.sel.map(function (p) { return '<option value="' + esc(p[0]) + '"' + (String(val) === String(p[0]) ? ' selected' : '') + '>' + esc(p[1]) + '</option>'; }).join('') + '</select>';
    else if (o.area) ctl = '<textarea' + attrs + ' rows="' + (o.rows || 4) + '">' + esc(val) + '</textarea>';
    else if (o.bool) ctl = '<label class="v2ce-chk"><input type="checkbox"' + attrs + (val === true ? ' checked' : '') + '> ' + esc(o.bool) + '</label>';
    else ctl = '<input type="' + (o.type || 'text') + '"' + attrs + ' value="' + esc(val) + '"' + (o.max ? ' maxlength="' + o.max + '"' : '') + ' autocomplete="off">';
    if (o.bool) return '<div class="v2co-fld v2ce-f">' + ctl + (o.hint ? '<small>' + esc(o.hint) + '</small>' : '') + '</div>';
    return '<div class="v2co-fld v2ce-f"><label for="' + id + '">' + esc(o.label || '') + '</label>' + ctl + (o.hint ? '<small>' + esc(o.hint) + '</small>' : '') + '</div>';
  }
  function getP(obj, path) {
    var cur = obj;
    String(path).split('.').forEach(function (k) { cur = cur == null ? undefined : cur[/^\d+$/.test(k) ? +k : k]; });
    return cur;
  }
  function blankRow(cols) { var r = {}; cols.forEach(function (c) { r[c.k] = c.t === 'bool' ? false : ''; }); return r; }

  // حقول كتلة حسب القاموس
  function fieldsHtml(def, base) {
    var b = getP(E.ld[E.lesson], base) || {};
    return def.fields.map(function (f) {
      var p = base + '.' + f.k, v = b[f.k];
      if (f.t === 'text') return field('les', p, v == null ? '' : v, { label: f.l, hint: f.hint });
      if (f.t === 'area') return field('les', p, v == null ? '' : v, { label: f.l, area: true, rows: 4, hint: f.hint });
      if (f.t === 'lines') return field('les', p, K.arrToLines(v), { label: f.l, area: true, rows: 4, t: 'lines', hint: f.hint });
      if (f.t === 'rows') return rowsHtml(p, f, Array.isArray(v) ? v : []);
      return '';
    }).join('');
  }
  function rowsHtml(path, f, rows) {
    var cols = f.cols;
    var body = rows.map(function (r, i) {
      return '<div class="v2ce-row" data-row="' + i + '"><div class="v2ce-rowf">' + cols.map(function (c) {
        var p = path + '.' + i + '.' + c.k;
        if (c.t === 'bool') return field('les', p, r[c.k] === true, { bool: c.l, t: 'bool' });
        return field('les', p, r[c.k] == null ? '' : r[c.k], { label: c.l, area: c.t === 'area', rows: 2 });
      }).join('') + '</div><button type="button" class="v2co-btn2 v2ce-ib" data-ce="row-del" data-p="' + esc(path) + '" data-i="' + i + '" aria-label="احذف الصف ' + ar(i + 1) + '">حذف</button></div>';
    }).join('');
    return '<div class="v2ce-rows"><b class="v2ce-rl">' + esc(f.l) + '</b>' + (f.hint ? '<small class="v2ce-hint">' + esc(f.hint) + '</small>' : '') + body
      + '<button type="button" class="v2co-btn2" data-ce="row-add" data-p="' + esc(path) + '" data-cols="' + esc(JSON.stringify(blankRow(cols))) + '">+ أضف صفًا</button></div>';
  }

  // ------------------------------------------------------------------ معاينة قراءة فقط لقائمة الكتل
  function para(t) { return esc(t).replace(/\n/g, '<br>'); }
  function ul(items) { return '<ul>' + (items || []).map(function (x) { return '<li>' + esc(typeof x === 'string' ? x : (x && (x.text || x.term || x.front)) || '') + '</li>'; }).join('') + '</ul>'; }
  function pvBlock(b) {
    var t = b.type, tag = '<span class="v2ce-pvt">' + esc(K.typeAr(t)) + '</span>';
    var body = '';
    if (t === 'text') body = '<p>' + para(b.md) + '</p>';
    else if (t === 'objectives' || t === 'summary') body = ul(b.items);
    else if (t === 'steps') body = '<ol>' + (b.items || []).map(function (x) { return '<li>' + esc(x) + '</li>'; }).join('') + '</ol>';
    else if (t === 'situation' || t === 'decision') {
      body = '<p>' + para(b.text) + '</p><p class="v2ce-pvq">' + esc(b.question) + '</p><ul class="v2ce-pvo">' + (b.options || []).map(function (o) {
        return '<li><b>' + esc(o.text) + '</b>' + (o.result ? '<span>' + esc(o.result) + '</span>' : '') + (o.comment ? '<em>' + esc(o.comment) + '</em>' : '') + '</li>'; }).join('') + '</ul>';
    } else if (t === 'quiz') {
      body = '<p class="v2ce-pvq">' + esc(b.question) + '</p><ul class="v2ce-pvo">' + (b.options || []).map(function (o) { return '<li' + (o.ok ? ' class="ok"' : '') + '><b>' + (o.ok ? '✓ ' : '') + esc(o.text) + '</b>' + (o.feedback ? '<em>' + esc(o.feedback) + '</em>' : '') + '</li>'; }).join('') + '</ul>';
    } else if (t === 'example') body = (b.title ? '<b>' + esc(b.title) + '</b>' : '') + '<p>' + para(b.text) + '</p>';
    else if (t === 'cards') body = '<p class="v2ce-pvq">' + esc(b.prompt) + '</p><div class="v2ce-pvg">' + (b.cards || []).map(function (c) { return '<div><b>' + esc(c.front) + '</b><span>' + esc(c.back) + '</span></div>'; }).join('') + '</div>';
    else if (t === 'order') body = '<p class="v2ce-pvq">' + esc(b.prompt) + '</p><ol>' + (b.items || []).map(function (x) { return '<li>' + esc(x) + '</li>'; }).join('') + '</ol>';
    else if (t === 'match') body = '<p class="v2ce-pvq">' + esc(b.prompt) + '</p><div class="v2ce-pvg">' + (b.pairs || []).map(function (c) { return '<div><b>' + esc(c.left) + '</b><span>' + esc(c.right) + '</span></div>'; }).join('') + '</div>';
    else if (t === 'before_after') body = '<div class="v2ce-pvg"><div><b>قبل</b><span>' + para(b.before) + '</span></div><div><b>بعد</b><span>' + para(b.after) + '</span></div></div>';
    else if (t === 'quote') body = '<blockquote>' + para(b.text) + (b.by ? '<cite>' + esc(b.by) + '</cite>' : '') + '</blockquote>';
    else if (t === 'icon_line') body = '<p>' + esc(b.text) + '</p>';
    else if (t === 'recall') body = '<p class="v2ce-mute">تُعرض هنا عبارة مرتبطة باختيار المتعلّم في قرار سابق.</p>';
    else if (t === 'accordion') body = (b.title ? '<b>' + esc(b.title) + '</b>' : '') + ul(b.items);
    else if (t === 'image' || t === 'video' || t === 'audio') body = '<p>' + esc(b.title || b.alt || b.url || '') + '</p>';
    else body = '<p class="v2ce-mute">كتلة متقدّمة، تظهر للمتعلّم كما تعرضها المنصة.</p>';
    return '<article class="v2ce-pvb">' + tag + body + '</article>';
  }
  function previewHtml(blocks) {
    return (blocks || []).length ? (blocks || []).map(pvBlock).join('') : '<p class="v2ce-mute">لا كتل في الدرس بعد.</p>';
  }

  // ------------------------------------------------------------------ الرسم الرئيسي
  function scroller() { return document.querySelector('.content') || document.scrollingElement; }
  function paint() {
    if (!E || !E.view || !document.body.contains(E.view)) return;
    var sc = scroller(), top = sc ? sc.scrollTop : 0;
    E.view.innerHTML = screenHtml();
    if (sc) sc.scrollTop = top;
  }
  CE.paint = paint;

  function tabsHtml() {
    var T = [['data', 'البيانات'], ['structure', 'الهيكل'], ['lessons', 'الدروس'], ['review', 'المراجعة والنشر']];
    var dirty = { data: dataDirty(), structure: structDirty(), lessons: Object.keys(E.ld).some(lessonDirty) };
    return '<div class="v2ce-tabs" role="tablist" aria-label="أقسام الدورة">' + T.map(function (t) {
      return '<button type="button" role="tab" class="v2ce-tab' + (E.tab === t[0] ? ' on' : '') + '" aria-selected="' + (E.tab === t[0]) + '" data-ce="tab" data-tab="' + t[0] + '">' + t[1]
        + (dirty[t[0]] ? '<i class="v2ce-dot" title="تعديلات لم تُحفظ"></i>' : '') + '</button>';
    }).join('') + '</div>';
  }
  function noteHtml() { return E.note ? '<div class="v2co-ok" role="status" data-ce-note>' + esc(E.note) + '</div>' : ''; }
  function setNote(t) {
    E.note = t; clearTimeout(E.noteT);
    E.noteT = setTimeout(function () { if (!E) return; E.note = ''; var n = q('[data-ce-note]', E.view || document); if (n) n.remove(); }, 9000);
  }

  function screenHtml() {
    var back = '<button type="button" class="v2co-link back" data-ce="back">‹ صفحة الدورة</button>';
    if (E.state === 'idle' || E.state === 'loading') return '<div class="v2co v2ce" data-screen="editor">' + back + '<div class="v2co-skw"><div class="v2co-sk"><i></i><i></i></div><div class="v2co-sk"><i></i><i></i></div></div></div>';
    if (E.state === 'closed') return '<div class="v2co v2ce" data-screen="editor">' + back + '<div class="v2co-empty"><b>محرّر الدورات: غير متاح بعد</b><p>لم تنشر المنصة المحرّر بعد، أو هذه الدورة غير موجودة. لا تعتبر الشاشة فارغة.</p><button type="button" class="v2co-btn2" data-ce="retry">أعد المحاولة</button></div></div>';
    if (E.state === 'error') return '<div class="v2co v2ce" data-screen="editor">' + back + '<div class="v2co-empty"><b>الدورة: غير متاح بعد</b><p>' + esc(E.err) + '</p><button type="button" class="v2co-btn2" data-ce="retry">أعد المحاولة</button></div></div>';
    var c = E.course, st = c.status || 'draft';
    var kinds = (c.kinds || []).map(function (k) { return K.KIND_AR[k] || k; });
    var owner = c.owner && c.owner.platform_owned ? 'البروفيسور' : ((c.owner && (c.owner.name || c.owner.email)) || '');
    var head = '<section class="v2ce-head"><h1>' + esc((c.meta && c.meta.title) || 'دورة بلا عنوان') + '</h1><p class="v2co-chips">' + chip(c.status_ar || '', STATUS_TONE[st]) + kinds.map(function (k) { return chip(k, 'grey'); }).join('')
      + chip(ar(c.lessons_count || 0) + ' ' + ((c.lessons_count || 0) === 1 ? 'درس' : ((c.lessons_count || 0) === 2 ? 'درسان' : ((c.lessons_count || 0) <= 10 ? 'دروس' : 'درسًا'))), 'grey')
      + (owner ? chip(owner, 'wine') : '') + '</p></section>';
    var panel = E.tab === 'data' ? dataHtml() : (E.tab === 'structure' ? structureHtml() : (E.tab === 'lessons' ? lessonsHtml() : reviewHtml()));
    return '<div class="v2co v2ce" data-screen="editor">' + noteHtml() + back + head + tabsHtml() + '<div class="v2ce-panel" role="tabpanel">' + panel + '</div></div>';
  }

  // ------------------------------------------------------------------ تبويب البيانات
  var LEVELS = [['', 'غير محدد'], ['مبتدئ', 'مبتدئ'], ['متوسط', 'متوسط'], ['متقدم', 'متقدم'], ['كل المستويات', 'كل المستويات']];
  function dataHtml() {
    var d = E.dd, ci = K.coverIssue(d.cover);
    return '<section class="v2co-card v2ce-card"><h2 class="v2co-h2">بيانات الدورة</h2>'
      + field('data', 'title', d.title, { label: 'العنوان', max: 300 })
      + field('data', 'subtitle', d.subtitle, { label: 'العنوان الفرعي', max: 300 })
      + field('data', 'description', d.description, { label: 'الوصف', area: true, rows: 5 })
      + field('data', 'cover', d.cover, { label: 'رابط الغلاف', ltr: true, ph: 'https://', hint: 'رابط صورة يبدأ بـ https://' })
      + (ci ? '<div class="v2co-errbox" role="alert">' + esc(ci) + '</div>' : '')
      + field('data', 'level', d.level, { label: 'المستوى', sel: LEVELS })
      + field('data', 'outcomes', d.outcomes, { label: 'ما سيتعلّمه الدارس', area: true, rows: 5, hint: 'سطر لكل ناتج تعلّم' })
      + '<div class="v2ce-err" data-ce-err="data"></div>'
      + '<div class="v2co-acts stack"><button type="button" class="v2co-btn1" data-ce="save-data"' + (dataDirty() ? '' : ' disabled') + '>احفظ البيانات</button></div></section>'
      + assistHtml('course');
  }

  // ------------------------------------------------------------------ تبويب الهيكل
  var KIND_BTN = [['interactive', 'تفاعلي'], ['recorded', 'مسجّل'], ['live', 'مباشر']];
  function structureHtml() {
    var us = E.sd, diff = K.structureDiff(K.structFrom(E.course), us);
    var h = us.map(function (u, ui) {
      var ls = (u.lessons || []).map(function (l, li) {
        return '<li class="v2ce-ls"><span class="v2ce-lsn">' + ar(li + 1) + '</span>'
          + '<div class="v2ce-lsf">' + field('sd', ui + '.lessons.' + li + '.title', l.title, { label: 'عنوان الدرس', max: 200 }) + '</div>'
          + '<span class="v2ce-lsk">' + chip(K.KIND_AR[l.kind] || 'بلا نوع', l.id ? 'grey' : 'wine') + (l.id ? '' : chip('جديد', 'green')) + '</span>'
          + '<span class="v2ce-ops"><button type="button" class="v2co-btn2 v2ce-ib" data-ce="ls-up" data-u="' + ui + '" data-l="' + li + '" aria-label="انقل الدرس لأعلى">↑</button>'
          + '<button type="button" class="v2co-btn2 v2ce-ib" data-ce="ls-down" data-u="' + ui + '" data-l="' + li + '" aria-label="انقل الدرس لأسفل">↓</button>'
          + '<button type="button" class="v2co-btn2 v2ce-ib red" data-ce="ls-del" data-u="' + ui + '" data-l="' + li + '" aria-label="احذف الدرس">حذف</button></span></li>';
      }).join('');
      return '<section class="v2co-card v2ce-card v2ce-unit"><div class="v2ce-uh"><span class="v2ce-un">وحدة ' + ar(ui + 1) + '</span>' + field('sd', ui + '.title', u.title, { label: 'عنوان الوحدة', max: 200 })
        + '<span class="v2ce-ops"><button type="button" class="v2co-btn2 v2ce-ib" data-ce="un-up" data-u="' + ui + '" aria-label="انقل الوحدة لأعلى">↑</button>'
        + '<button type="button" class="v2co-btn2 v2ce-ib" data-ce="un-down" data-u="' + ui + '" aria-label="انقل الوحدة لأسفل">↓</button>'
        + '<button type="button" class="v2co-btn2 v2ce-ib red" data-ce="un-del" data-u="' + ui + '" aria-label="احذف الوحدة">حذف</button></span></div>'
        + '<ul class="v2ce-lsl">' + (ls || '<li class="v2co-none">لا دروس في هذه الوحدة</li>') + '</ul>'
        + '<div class="v2ce-addls"><b>أضف درسًا:</b>' + KIND_BTN.map(function (k) { return '<button type="button" class="v2co-btn2" data-ce="ls-add" data-u="' + ui + '" data-kind="' + k[0] + '">+ ' + k[1] + '</button>'; }).join('') + '</div></section>';
    }).join('');
    var sum = diff.changed ? structSummaryLine(diff) : 'لا تغييرات غير محفوظة في الهيكل';
    return '<p class="v2co-fine v2ce-lead">الوحدات والدروس وأنواعها. الدرس الجديد يحتاج نوعًا يُختار عند إضافته ولا يتغيّر بعدها. الحفظ يستبدل الهيكل كله، والدرس الموجود يحتفظ بمحتواه.</p>'
      + h + '<div class="v2ce-bar"><button type="button" class="v2co-btn2" data-ce="un-add">+ أضف وحدة</button></div>'
      + '<div class="v2ce-err" data-ce-err="structure"></div>'
      + '<section class="v2co-card v2ce-card"><p class="v2ce-sum">' + esc(sum) + '</p><div class="v2co-acts stack"><button type="button" class="v2co-btn1" data-ce="save-struct"' + (diff.changed ? '' : ' disabled') + '>احفظ الهيكل</button></div></section>'
      + assistHtml('course');
  }
  function structSummaryLine(d) {
    var p = [];
    if (d.added.length) p.push('إضافة ' + ar(d.added.length) + ' ' + (d.added.length === 1 ? 'درس' : (d.added.length === 2 ? 'درسين' : 'دروس')));
    if (d.removed.length) p.push('حذف ' + ar(d.removed.length) + ' ' + (d.removed.length === 1 ? 'درس' : (d.removed.length === 2 ? 'درسين' : 'دروس')));
    if (d.renamed.length) p.push('تغيير ' + ar(d.renamed.length) + ' ' + (d.renamed.length === 1 ? 'عنوان' : 'عناوين'));
    if (d.reordered) p.push('تغيير الترتيب');
    if (d.unitsAdded) p.push('وحدات جديدة: ' + ar(d.unitsAdded));
    if (d.unitsRemoved) p.push('وحدات محذوفة: ' + ar(d.unitsRemoved));
    return p.length ? 'تغييرات غير محفوظة: ' + p.join(' · ') : 'تغييرات غير محفوظة في العناوين';
  }

  // ------------------------------------------------------------------ تبويب الدروس
  function lessonsHtml() {
    var all = lessonsOf(E.course);
    if (!all.length) return '<div class="v2co-empty"><b>لا دروس بعد</b><p>أضف دروسًا من تبويب «الهيكل» ثم عد لكتابة محتواها.</p><button type="button" class="v2co-btn2" data-ce="tab" data-tab="structure">افتح الهيكل</button></div>';
    var list = '<ul class="v2ce-ll" aria-label="دروس الدورة">' + all.map(function (x) {
      var l = x.lesson, on = l.id === E.lesson;
      return '<li><button type="button" class="v2ce-lb' + (on ? ' on' : '') + '" data-ce="pick" data-id="' + esc(l.id) + '" aria-pressed="' + on + '"><span class="v2ce-lno">الدرس ' + ar(x.no) + '</span><b>' + esc(l.title || 'درس بلا عنوان') + '</b>'
        + '<span class="v2ce-lm">' + chip(K.KIND_AR[l.kind] || '', 'grey') + (l.state_ar ? chip(l.state_ar, STATE_TONE[l.state]) : '') + (lessonDirty(l.id) ? chip('لم يُحفظ', 'amber') : '') + '</span></button></li>';
    }).join('') + '</ul>';
    var ed = E.lesson && lessonById(E.lesson) ? lessonEditorHtml(E.lesson) : '<div class="v2co-empty"><b>اختر درسًا لتحريره</b><p>يظهر محتوى الدرس هنا حسب نوعه: تفاعلي أو مسجّل أو مباشر.</p></div>';
    var cur = E.lesson && lessonById(E.lesson), open = window.innerWidth >= 900 || !cur;   // في الموبايل تنطوي القائمة بعد اختيار درس ليظهر المحرّر
    var sel = '<details class="v2ce-lsel"' + (open ? ' open' : '') + '><summary>' + (cur ? 'الدرس ' + ar(cur.no) + ' · ' + esc(cur.lesson.title || 'بلا عنوان') + ' — غيّر الدرس' : 'اختر درسًا') + '</summary>' + list + '</details>';
    return '<div class="v2ce-split"><aside class="v2ce-side">' + sel + '</aside><div class="v2ce-main" data-ce-lesson>' + ed + '</div></div>';
  }
  function lessonEditorHtml(id) {
    var x = lessonById(id), l = x.lesson, d = draftOf(id);
    var head = '<div class="v2ce-lh"><h2 class="v2co-h2">الدرس ' + ar(x.no) + ' · ' + esc(K.KIND_AR[l.kind] || '') + '</h2>' + (lessonDirty(id) ? chip('تعديلات لم تُحفظ', 'amber') : (l.state_ar ? chip(l.state_ar, STATE_TONE[l.state]) : '')) + '</div>';
    var body = field('les', 'title', d.title, { label: 'عنوان الدرس', max: 200 });
    if (l.kind === 'interactive') body += interactiveHtml(id, d);
    else if (l.kind === 'recorded') body += recordedHtml(id, d, l);
    else body += liveHtml(id, d);
    var pv = E.pv[id];
    var pvBox = '';
    if (pv && pv.err) pvBox = '<div class="v2co-errbox" role="alert">' + esc(pv.err) + '</div>';
    else if (pv && pv.ok) pvBox = '<section class="v2ce-pv" aria-label="معاينة"><h3>معاينة الدرس <small>لم يُحفظ شيء</small></h3>' + (l.kind === 'interactive' ? previewHtml(pv.blocks) : '<p class="v2ce-mute">' + esc(pv.text || 'الدرس صالح للحفظ.') + '</p>') + '</section>';
    return head + '<section class="v2co-card v2ce-card">' + body + '</section>' + assistHtml('lesson')
      + '<div class="v2ce-err" data-ce-err="lesson"></div>' + pvBox
      + '<div class="v2ce-bar sticky"><button type="button" class="v2co-btn2" data-ce="preview">عاين</button><button type="button" class="v2co-btn1" data-ce="save-lesson">احفظ الدرس</button></div>';
  }

  // —— تفاعلي
  function interactiveHtml(id, d) {
    var fs = '<div class="v2ce-grid2">' + field('les', 'time', d.time == null ? '' : d.time, { label: 'مدة الدرس بالدقائق', type: 'number', ltr: true, t: 'int' })
      + field('les', 'for', (d.for || []).join(', '), { label: 'الحالات (فارغ = للجميع)', t: 'list', ltr: true, ph: 'student, office' }) + '</div>'
      + '<div class="v2ce-grid2">' + field('les', 'hero', d.hero || '', { label: 'صورة الدرس (رابط)', ltr: true, ph: 'https://' }) + field('les', 'motion', d.motion || '', { label: 'حركة الدرس (ملف mp4)', ltr: true, ph: 'https://' }) + '</div>';
    var blocks = (d.blocks || []).map(function (b, i) { return blockHtml(b, i, (d.blocks || []).length); }).join('');
    var picker = E.picker ? pickerHtml() : '';
    return fs + '<div class="v2ce-bh"><h3>كتل الدرس <span class="v2co-n">' + ar((d.blocks || []).length) + '</span></h3></div>'
      + '<div class="v2ce-blocks" data-ce-blocks>' + (blocks || '<p class="v2co-none">لا كتل بعد. أضف كتلة من الزر أدناه.</p>') + '</div>'
      + '<button type="button" class="v2co-btn2 v2ce-addb" data-ce="picker">' + (E.picker ? 'أغلق قائمة الأنواع' : '+ أضف كتلة') + '</button>' + picker;
  }
  function pickerHtml() {
    var main = K.TYPES.filter(function (t) { return t.main; }), adv = K.TYPES.filter(function (t) { return !t.main; });
    return '<div class="v2ce-picker" role="group" aria-label="اختر نوع الكتلة">' + main.map(function (t) { return '<button type="button" class="v2ce-pt" data-ce="blk-add" data-type="' + t.type + '">' + esc(t.ar) + '</button>'; }).join('')
      + '<details class="v2ce-padv"><summary>أنواع متقدّمة</summary><div class="v2ce-picker in">' + adv.map(function (t) { return '<button type="button" class="v2ce-pt" data-ce="blk-add" data-type="' + t.type + '">' + esc(t.ar) + '</button>'; }).join('') + '</div></details></div>';
  }
  function blockHtml(b, i, n) {
    var def = K.typeDef(b.type), open = E.open[E.lesson + ':' + i] === true;
    var form = def && def.fields.length ? fieldsHtml(def, 'blocks.' + i) : '<p class="v2ce-mute">هذا النوع يُحرَّر من «متقدّم» أدناه.</p>';
    return '<article class="v2ce-blk' + (open ? ' open' : '') + '" data-blk="' + i + '"><div class="v2ce-bhd">'
      + '<button type="button" class="v2ce-bt" data-ce="blk-toggle" data-i="' + i + '" aria-expanded="' + open + '"><span class="v2ce-bn">' + ar(i + 1) + '</span><b>' + esc(K.typeAr(b.type)) + '</b><span class="v2ce-bhead">' + esc(K.blockHead(b)) + '</span></button>'
      + '<span class="v2ce-ops"><button type="button" class="v2co-btn2 v2ce-ib" data-ce="blk-up" data-i="' + i + '"' + (i === 0 ? ' disabled' : '') + ' aria-label="انقل الكتلة لأعلى">↑</button>'
      + '<button type="button" class="v2co-btn2 v2ce-ib" data-ce="blk-down" data-i="' + i + '"' + (i === n - 1 ? ' disabled' : '') + ' aria-label="انقل الكتلة لأسفل">↓</button>'
      + '<button type="button" class="v2co-btn2 v2ce-ib red" data-ce="blk-del" data-i="' + i + '" aria-label="احذف الكتلة">حذف</button></span></div>'
      + '<div class="v2ce-bbody">' + form + '<details class="v2ce-adv"><summary>متقدّم</summary><textarea class="v2ce-json" dir="ltr" rows="8" data-ce-json="' + i + '" aria-label="كتلة بصيغة JSON">' + esc(JSON.stringify(b, null, 2)) + '</textarea>'
      + '<div class="v2ce-jerr" data-ce-jerr="' + i + '"></div></details></div></article>';
  }

  // —— مسجّل
  function videoState(d, l) {
    var v = d._video || {};
    if (v.touched) return v.mode === 'upload' ? 'رُفع فيديو جديد ولم يُربط بالدرس بعد: اضغط «احفظ الدرس»' : (v.mode === 'link' ? 'رابط جديد لم يُحفظ بعد' : 'سيُزال الفيديو عند الحفظ');
    if (v.mode === 'upload') return 'الفيديو مرفوع على المنصة';
    if (v.mode === 'link') return 'الفيديو من رابط';
    return 'لا فيديو بعد';
  }
  function recordedHtml(id, d, l) {
    var up = E.up[id] || {}, v = d._video || {};
    var cfgOff = up.configured === false;
    var upBox = cfgOff ? '<p class="v2ce-mute">رفع الفيديو من اللوحة غير متاح الآن. الصق رابط الفيديو في الخانة المجاورة.</p>'
      : '<div class="v2ce-upl"><label class="v2co-btn2 v2ce-file">اختر ملف الفيديو<input type="file" accept="video/*" data-ce-file="' + esc(id) + '" hidden></label>'
        + '<span class="v2ce-fn">' + esc(up.file ? up.file.name : 'لم يُختر ملف') + '</span>'
        + '<button type="button" class="v2co-btn1" data-ce="upload"' + (up.file && up.state !== 'uploading' ? '' : ' disabled') + '>ارفع الفيديو</button></div>'
        + (up.state === 'uploading' || up.state === 'done' ? '<div class="v2ce-prog" role="progressbar" aria-valuemin="0" aria-valuemax="100" aria-valuenow="' + (up.pct || 0) + '"><i style="width:' + (up.pct || 0) + '%" data-ce-prog></i></div><p class="v2ce-mute" data-ce-progt>' + esc(up.msg || '') + '</p>' : '')
        + (up.state === 'error' ? '<div class="v2co-errbox" role="alert">' + esc(up.msg) + '</div>' : '');
    var chapters = rowsHtml('chapters', { l: 'الفصول', hint: 'الوقت بصيغة ١:٣٠ أو بالثواني', cols: [{ k: 't', l: 'الوقت', t: 'text' }, { k: 'title', l: 'العنوان', t: 'text' }] }, d.chapters || []);
    var cps = (d.checkpoints || []).map(function (c, i) {
      return '<div class="v2ce-cp"><div class="v2ce-cph"><b>سؤال توقف ' + ar(i + 1) + '</b><button type="button" class="v2co-btn2 v2ce-ib red" data-ce="row-del" data-p="checkpoints" data-i="' + i + '">حذف</button></div>'
        + '<div class="v2ce-grid2">' + field('les', 'checkpoints.' + i + '.t', c.t, { label: 'الوقت' }) + field('les', 'checkpoints.' + i + '.question', c.question, { label: 'السؤال' }) + '</div>'
        + rowsHtml('checkpoints.' + i + '.options', { l: 'الاختيارات', hint: 'علّم الصحيح', cols: [{ k: 'text', l: 'الاختيار', t: 'text' }, { k: 'ok', l: 'صحيح', t: 'bool' }, { k: 'explanation', l: 'الشرح', t: 'text' }] }, c.options || []) + '</div>';
    }).join('');
    return '<div class="v2ce-sec"><h3>الفيديو</h3><p class="v2ce-vs">' + esc(videoState(d, l)) + '</p><div class="v2ce-vgrid"><div>' + upBox + '</div><div>'
      + field('les', '_video.url', v.mode === 'link' ? v.url || '' : '', { label: 'أو الصق رابط الفيديو', ltr: true, ph: 'https://', hint: 'يوتيوب أو درايف أو ملف mp4', t: 'vlink' })
      + '<button type="button" class="v2co-btn2" data-ce="video-clear"' + (v.mode !== 'none' || v.touched ? '' : ' disabled') + '>أزل الفيديو</button></div></div></div>'
      + '<div class="v2ce-grid2">' + field('les', 'duration_seconds', d.duration_seconds || '', { label: 'مدة الفيديو (د:ث)', ltr: true, ph: '12:30' }) + field('les', 'is_preview', d.is_preview === true, { bool: 'درس معاينة يراه الجميع', t: 'bool' }) + '</div>'
      + '<div class="v2ce-sec">' + chapters + '</div>'
      + '<div class="v2ce-sec"><h3>أسئلة التوقف</h3>' + cps + '<button type="button" class="v2co-btn2" data-ce="cp-add">+ أضف سؤال توقف</button></div>'
      + field('les', 'summary', Array.isArray(d.summary) ? d.summary.join('\n') : (d.summary || ''), { label: 'الملخّص', area: true, rows: 3, t: 'lines', hint: 'ثلاثة أسطر على الأكثر' })
      + field('les', 'transcript', d.transcript || '', { label: 'نص الفيديو', area: true, rows: 8 });
  }

  // —— مباشر
  var LIVE_ST = [['scheduled', 'مجدولة'], ['done', 'انتهت'], ['postponed', 'أُجّلت'], ['canceled', 'أُلغيت']];
  function liveHtml(id, d) {
    var qz = d.quiz || { question: '', options: [] };
    var sa = String(d.starts_at || '').slice(0, 16);
    return '<div class="v2ce-grid2">' + field('les', 'starts_at', sa, { label: 'موعد البدء', type: 'datetime-local', ltr: true, t: 'dt' }) + field('les', 'duration_min', d.duration_min || '', { label: 'المدة بالدقائق', type: 'number', ltr: true, t: 'int' }) + '</div>'
      + field('les', 'zoom_link', d.zoom_link || '', { label: 'رابط اللقاء', ltr: true, ph: 'https://' })
      + field('les', 'recording_url', d.recording_url || '', { label: 'رابط التسجيل بعد اللقاء', ltr: true, ph: 'https://' })
      + field('les', 'status', d.status || 'scheduled', { label: 'حالة اللقاء', sel: LIVE_ST })
      + '<div class="v2ce-sec"><h3>اختبار بعد اللقاء <small>اختياري</small></h3>' + field('les', 'quiz.question', qz.question || '', { label: 'السؤال' })
      + rowsHtml('quiz.options', { l: 'الاختيارات', cols: [{ k: 'text', l: 'الاختيار', t: 'text' }, { k: 'ok', l: 'صحيح', t: 'bool' }, { k: 'explanation', l: 'الشرح', t: 'text' }] }, qz.options || []) + '</div>';
  }

  // ------------------------------------------------------------------ «اطلب من المساعد»
  function asState(scope) {
    var key = scope === 'lesson' ? 'l:' + E.lesson : 'c';
    if (!E.as[key]) E.as[key] = { kind: scope === 'lesson' ? 'activity_decision' : 'from_material', instr: '', material: '', busy: false, res: null, err: '', choice: 0, added: false };
    return E.as[key];
  }
  function assistHtml(scope) {
    var s = asState(scope), kinds = K.assistKinds(scope === 'lesson');
    var cur = kinds.filter(function (k) { return k.kind === s.kind; })[0] || kinds[0];
    if (cur.kind !== s.kind) s.kind = cur.kind;
    var chips = kinds.map(function (k) { return '<button type="button" class="v2ce-ak' + (k.kind === s.kind ? ' on' : '') + '" data-ce="as-kind" data-scope="' + scope + '" data-kind="' + k.kind + '" aria-pressed="' + (k.kind === s.kind) + '">' + esc(k.ar) + '</button>'; }).join('');
    var inputs = '';
    if (cur.ask) inputs += '<div class="v2co-fld"><label for="as_i_' + scope + '">سؤالك</label><textarea id="as_i_' + scope + '" rows="3" data-as="instr" data-scope="' + scope + '">' + esc(s.instr) + '</textarea></div>';
    if (cur.material) inputs += '<div class="v2co-fld"><label for="as_m_' + scope + '">الصق مادتك هنا</label><textarea id="as_m_' + scope + '" rows="6" data-as="material" data-scope="' + scope + '">' + esc(s.material) + '</textarea><small>نص من ٨٠ حرفًا على الأقل: مادة تدريبية أو تفريغ.</small></div>';
    var res = s.res ? assistResultHtml(scope, s, cur) : '';
    return '<section class="v2co-card v2ce-card v2ce-as" data-ce-as="' + scope + '"><h2 class="v2co-h2">' + (window.V2CO && window.V2CO.kit ? window.V2CO.kit.BRAIN : '') + 'اطلب من المساعد</h2>'
      + '<p class="v2co-fine">يكتب المساعد مسودة فقط. لا يُحفظ شيء حتى تضيفه وتضغط «احفظ».</p><div class="v2ce-aks" role="group" aria-label="ما تطلبه">' + chips + '</div>' + inputs
      + (s.err ? '<div class="v2co-errbox" role="alert">' + esc(s.err) + '</div>' : '')
      + '<div class="v2co-acts stack"><button type="button" class="v2co-btn1" data-ce="as-ask" data-scope="' + scope + '"' + (s.busy ? ' disabled' : '') + '>' + (s.busy ? 'جارٍ الكتابة…' : 'اطلب') + '</button></div>' + res + '</section>';
  }
  function assistResultHtml(scope, s, cur) {
    var r = s.res, dr = r.draft || {}, out = '<div class="v2ce-draft" aria-live="polite"><h3>مسودة المساعد <small>لم تُحفظ</small></h3>', add = '';
    if (r.kind === 'activity_decision' && dr.block) {
      out += previewHtml([dr.block]);
      if (r.valid === false) out += '<div class="v2co-errbox">' + (r.issues || []).map(esc).join('<br>') + '</div>';
      add = r.valid === false ? '' : '<button type="button" class="v2co-btn1" data-ce="as-add" data-scope="' + scope + '">أضفه إلى الدرس</button>';
    } else if (r.kind === 'shorter_title' && dr.titles) {
      out += '<div class="v2ce-titles" role="radiogroup" aria-label="العناوين المقترحة">' + dr.titles.map(function (t, i) { return '<label class="v2ce-radio"><input type="radio" name="as_t" data-as-choice="' + i + '" data-scope="' + scope + '"' + (i === (s.choice || 0) ? ' checked' : '') + '> ' + esc(t) + '</label>'; }).join('') + '</div>';
      add = '<button type="button" class="v2co-btn1" data-ce="as-add" data-scope="' + scope + '">أضفه إلى الدرس</button>';
    } else if (r.kind === 'video_script' && typeof dr.transcript === 'string') {
      out += '<div class="v2ce-script">' + para(dr.transcript) + '</div>';
      add = '<button type="button" class="v2co-btn1" data-ce="as-add" data-scope="' + scope + '">أضفه إلى الدرس</button>';
    } else if (r.kind === 'from_material' && dr.units) {
      out += '<p class="v2co-fine">' + esc(ar(r.units || dr.units.length) + ' وحدات · ' + ar(r.lessons || 0) + ' دروس') + '</p>' + dr.units.map(function (u) {
        return '<div class="v2ce-du"><b>' + esc(u.title) + '</b><ul>' + (u.lessons || []).map(function (l) { return '<li>' + esc(l.title) + (l.state_ar ? ' ' + chip(l.state_ar, 'amber') : '') + '</li>'; }).join('') + '</ul></div>'; }).join('');
      add = '<button type="button" class="v2co-btn1" data-ce="as-build">أنشئ الهيكل منها</button>';
    } else if (r.kind === 'free' || typeof r.answer === 'string') {
      out += '<div class="v2ce-script">' + para(r.answer || '') + '</div>';
    } else out += '<p class="v2ce-mute">لم يصل من المساعد ما يمكن عرضه. أعد الطلب.</p>';
    if (s.added) out += '<div class="v2co-ok" role="status">أُضيف إلى الدرس ولم يُحفظ بعد. راجعه ثم اضغط «احفظ الدرس».</div>';
    return out + (add ? '<div class="v2co-acts stack">' + add + '</div>' : '') + '</div>';
  }

  // ------------------------------------------------------------------ المراجعة والنشر
  function reviewHtml() {
    var c = E.course, st = c.status, gaps = c.gaps || [], notes = (c.notes && c.notes.items) || [];
    var gp = gaps.length ? '<div class="v2co-warn" role="status">' + esc(K.gapsLine(c)) + '</div>' : '<div class="v2co-ok" role="status">' + esc(K.gapsLine(c)) + '</div>';
    var nt = '<section class="v2co-card v2ce-card"><h2 class="v2co-h2">ملاحظات المراجعة</h2>' + (c.notes && c.notes.summary_ar ? '<p class="v2co-fine">' + esc(c.notes.summary_ar) + '</p>' : '')
      + (notes.length ? '<ul class="v2ce-notes">' + notes.map(function (n) { return '<li><div class="v2ce-nh"><b>' + esc(n.target_label || '') + (n.target_title ? ' · ' + esc(n.target_title) : '') + '</b>' + chip(n.status_ar || '', n.status === 'edited' ? 'green' : 'amber') + '</div><p>' + esc(n.text) + '</p></li>'; }).join('') + '</ul>' : '<p class="v2co-none">لا ملاحظات على هذه الدورة</p>') + '</section>';
    var dirty = dirtyList();
    var warn = dirty.length ? '<div class="v2co-warn" role="status">عندك تعديلات لم تُحفظ: ' + esc(dirty.join('، ')) + '. احفظها قبل النشر.</div>' : '';
    var acts = '';
    if (st === 'review') acts += '<button type="button" class="v2co-btn1 outline" data-ce="return">أرجِعها بملاحظات</button>';
    if (st !== 'published') acts += '<button type="button" class="v2co-btn1" data-ce="publish">انشر</button>';
    if (st === 'published') acts += '<button type="button" class="v2co-btn2 red" data-ce="pause">أوقفها</button>';
    return '<section class="v2co-card v2ce-card"><h2 class="v2co-h2">حالة الدورة: ' + esc(c.status_ar || '') + '</h2>' + gp + warn + '<div class="v2ce-err" data-ce-err="review"></div><div class="v2co-acts stack">' + acts + '</div></section>' + nt;
  }

  // ------------------------------------------------------------------ الأوراق
  function confirmSheet(o) {
    var k = kit();
    return k.flow({ title: o.title, review: function () { return (o.lead ? '<p class="v2co-lead">' + o.lead + '</p>' : '') + (o.items && o.items.length ? k.listHtml(o.items) : '') + (o.warn ? '<div class="v2co-warn">' + o.warn + '</div>' : ''); },
      btnConfirm: o.btn, danger: o.danger, busy: o.busy, send: o.send, onOk: o.onOk, result: o.result });
  }
  function afterSave(res, msg, reset) {
    if (res && res.course) setCourse(res.course, reset);
    setNote(msg);
    refreshList();
    paint();
  }
  function refreshList() { var k = kit(); if (k && k.reloadList) k.reloadList(); }

  function saveData() {
    var body = K.dataBody(E.dd), ci = K.coverIssue(E.dd.cover);
    if (!body.title) { showErr('data', 'اكتب عنوان الدورة'); return; }
    if (ci) { showErr('data', ci); return; }
    showErr('data', '');
    var cur = K.dataBody({ title: E.course.meta.title, subtitle: E.course.meta.subtitle, description: E.course.meta.description, cover: E.course.meta.cover, level: E.course.meta.level, outcomes: E.course.meta.outcomes || [] });
    var names = { title: 'العنوان', subtitle: 'العنوان الفرعي', description: 'الوصف', cover: 'الغلاف', level: 'المستوى', outcomes: 'ما سيتعلّمه الدارس' };
    var items = Object.keys(names).filter(function (f) { return JSON.stringify(body[f]) !== JSON.stringify(cur[f]); }).map(function (f) { return esc(names[f]); });
    var payload = Object.assign({ confirmed: true }, body);
    confirmSheet({ title: 'احفظ بيانات الدورة', lead: 'سيُحفظ على المنصة:', items: items, btn: 'احفظ البيانات', busy: 'جارٍ الحفظ…',
      send: function () { return api('PUT', BASE + '/' + enc(E.id) + '/data', payload); }, onOk: function (res) { afterSave(res, 'حُفظت بيانات الدورة.', { resetData: true }); } });
  }

  function saveStruct() {
    var errs = K.structureErrors(E.sd);
    if (errs.length) { showErr('structure', errs.join('. ')); return; }
    showErr('structure', '');
    var diff = K.structureDiff(K.structFrom(E.course), E.sd), items = [];
    if (diff.added.length) items.push('دروس جديدة: ' + esc(diff.added.map(function (a) { return (a.title || 'بلا عنوان') + ' (' + (K.KIND_AR[a.kind] || '') + ')'; }).join('، ')));
    if (diff.renamed.length) items.push('عناوين تتغيّر: ' + esc(diff.renamed.map(function (r) { return r.from + ' ⇐ ' + r.to; }).join('، ')));
    if (diff.reordered) items.push('يتغيّر ترتيب الوحدات أو الدروس');
    if (diff.unitsAdded) items.push('وحدات جديدة: ' + ar(diff.unitsAdded));
    var gone = diff.removed, withC = gone.filter(function (r) { return r.hasContent; });
    var warn = '';
    if (gone.length) items.push('دروس تُحذف: ' + esc(gone.map(function (r) { return r.title; }).join('، ')));
    if (withC.length) warn = '<b>يُمسح محتوى هذه الدروس نهائيًا:</b> ' + esc(withC.map(function (r) { return r.title; }).join('، ')) + '. هذا لا يمكن التراجع عنه.';
    if (!items.length) items.push('لا تغيير في العدّ، فقط ضبط العناوين');
    var payload = Object.assign({ confirmed: true }, K.structureBody(E.sd));
    confirmSheet({ title: 'احفظ هيكل الدورة', lead: 'سيُستبدل هيكل الدورة بهذا:', items: items, warn: warn, btn: withC.length ? 'احفظ واحذف المحتوى' : 'احفظ الهيكل', danger: withC.length > 0, busy: 'جارٍ الحفظ…',
      send: function () { return api('PUT', BASE + '/' + enc(E.id) + '/structure', payload); },
      onOk: function (res) { afterSave(res, 'حُفظ هيكل الدورة.', { resetStruct: true }); } });
  }

  function lessonName() { var x = lessonById(E.lesson); return x ? x.lesson.title : ''; }
  function saveLesson() {
    var x = lessonById(E.lesson), d = draftOf(E.lesson);
    var issues = K.lessonIssues(x.lesson, d);
    if (issues.length) { showErr('lesson', issues.join('. ')); return; }
    showErr('lesson', '');
    var body = K.lessonBody(x.lesson, d), items = [];
    if (x.lesson.kind === 'interactive') items.push('الكتل: ' + ar((body.blocks || []).length));
    if (x.lesson.kind === 'recorded') items.push(body.video && body.video.bunny_video_id ? 'يُربط الفيديو المرفوع بالدرس' : (body.video && body.video.url ? 'يُحفظ رابط الفيديو' : (body.video ? 'يُزال الفيديو' : 'بيانات الدرس المسجّل')));
    if (x.lesson.kind === 'live') items.push('موعد اللقاء وروابطه');
    var id = E.lesson, payload = Object.assign({ confirmed: true }, body);
    confirmSheet({ title: 'احفظ الدرس «' + esc(body.title) + '»', lead: 'سيُحفظ الدرس على المنصة:', items: items, btn: 'احفظ الدرس', busy: 'جارٍ الحفظ…',
      send: function () { return api('PUT', BASE + '/' + enc(E.id) + '/lessons/' + enc(id), payload); },
      onOk: function (res) { delete E.ld[id]; delete E.pv[id]; afterSave(res, 'حُفظ الدرس.'); } });
  }

  function previewLesson() {
    var x = lessonById(E.lesson), d = draftOf(E.lesson), id = E.lesson;
    var issues = K.lessonIssues(x.lesson, d);
    if (issues.length) { E.pv[id] = { err: issues.join('. ') }; paint(); return; }
    var body = K.lessonBody(x.lesson, d);
    E.pv[id] = { busy: true };
    api('POST', BASE + '/' + enc(E.id) + '/lessons/' + enc(id) + '/preview', body).then(function () {
      E.pv[id] = { ok: true, blocks: body.blocks || [], text: x.lesson.kind === 'interactive' ? '' : 'الدرس صالح، وهكذا سيظهر للمتعلّم عند الحفظ.' };
      paint();
    }).catch(function (e) { E.pv[id] = { err: errText(e) }; paint(); });
  }

  function showErr(which, msg) {
    var el = q('[data-ce-err="' + which + '"]', E.view);
    if (el) el.innerHTML = msg ? '<div class="v2co-errbox" role="alert">' + esc(msg) + '</div>' : '';
  }

  function openReturn() {
    var k = kit(), c = E.course, rows = [{ kind: 'course', id: '', label: 'الدورة كلها' }];
    ((c.outline && c.outline.units) || []).forEach(function (u, ui) {
      rows.push({ kind: 'unit', id: u.id, label: 'الوحدة ' + ar(ui + 1) + ' · ' + (u.title || '') });
      (u.lessons || []).forEach(function (l) { rows.push({ kind: 'lesson', id: l.id, label: 'الدرس ' + ar(l.no || 0) + ' · ' + (l.title || '') }); });
    });
    var form = '<p class="v2co-lead">اختر ما تعلّق عليه، واكتب ملاحظة لكل اختيار. تصل الملاحظات إلى صاحب الدورة.</p>' + rows.map(function (r, i) {
      return '<div class="v2ce-rr"><label class="v2ce-chk"><input type="checkbox" data-rr="' + i + '"> ' + esc(r.label) + '</label><textarea rows="2" maxlength="600" data-rrt="' + i + '" aria-label="ملاحظة ' + esc(r.label) + '" hidden></textarea></div>';
    }).join('');
    k.flow({ title: 'أرجِعها بملاحظات', form: form,
      wire: function (s) { qa('[data-rr]', s).forEach(function (cb) { cb.onchange = function () { var t = q('[data-rrt="' + cb.getAttribute('data-rr') + '"]', s); t.hidden = !cb.checked; if (cb.checked) t.focus(); }; }); },
      collect: function (s) {
        var sel = rows.map(function (r, i) { return { kind: r.kind, id: r.id, label: r.label, on: q('[data-rr="' + i + '"]', s).checked, text: q('[data-rrt="' + i + '"]', s).value }; });
        var iss = K.returnIssues(sel);
        return iss.length ? { ok: false, error: iss.join('. ') } : { ok: true, payload: K.returnBody(sel) };
      },
      review: function (p) { return '<p class="v2co-lead">ستعود الدورة إلى صاحبها بـ' + ar(p.notes.length) + (p.notes.length === 1 ? ' ملاحظة' : ' ملاحظات') + '.</p>' + k.listHtml(p.notes.map(function (n) { return esc(n.text.length > 90 ? n.text.slice(0, 90) + '…' : n.text); })); },
      btnNext: 'راجع الملاحظات', btnConfirm: 'أرجِعها', busy: 'جارٍ الإرجاع…',
      send: function (p) { return api('POST', BASE + '/' + enc(E.id) + '/return', Object.assign({ confirmed: true }, p)); },
      onOk: function (res) { afterSave(res, 'أُرجعت الدورة بملاحظات.'); } });
  }
  function openPublish() {
    var gaps = E.course.gaps || [], dirty = dirtyList();
    confirmSheet({ title: 'انشر الدورة', lead: 'ستظهر الدورة «' + esc(E.course.meta.title || '') + '» للناس بعد النشر.',
      items: gaps.length ? ['ما زال ينقصها: ' + esc(gaps.join('، ')) + '. إن رفضت المنصة النشر فسيظهر السبب هنا.'] : ['مكتملة وجاهزة للنشر'],
      warn: dirty.length ? 'عندك تعديلات لم تُحفظ: ' + esc(dirty.join('، ')) + '. لن تدخل في النشر.' : '', btn: 'انشر الآن', busy: 'جارٍ النشر…',
      send: function () { return api('POST', BASE + '/' + enc(E.id) + '/publish', { confirmed: true }); },
      onOk: function (res) { afterSave(res, 'نُشرت الدورة.'); } });
  }
  function openPause() {
    confirmSheet({ title: 'أوقف الدورة', lead: 'ستختفي الدورة «' + esc(E.course.meta.title || '') + '» من الظهور للناس، ويمكن نشرها من جديد.', items: ['المسجّلون فيها يبقون كما هم'],
      btn: 'أوقفها', danger: true, busy: 'جارٍ الإيقاف…', send: function () { return api('POST', BASE + '/' + enc(E.id) + '/pause', { confirmed: true }); }, onOk: function (res) { afterSave(res, 'أُوقفت الدورة.'); } });
  }

  // ------------------------------------------------------------------ رفع الفيديو (TUS)
  function startUpload() {
    var id = E.lesson, up = E.up[id] || (E.up[id] = {});
    if (!up.file) return;
    var title = lessonName() || 'درس';
    confirmSheet({ title: 'ارفع الفيديو', lead: 'سيُرفع الملف «' + esc(up.file.name) + '» مباشرة إلى مخزن الفيديو.', items: ['لا تغلق الصفحة حتى يكتمل الرفع', 'بعد الرفع اضغط «احفظ الدرس» ليرتبط الفيديو بالدرس'], btn: 'ابدأ الرفع', busy: 'جارٍ التجهيز…',
      send: function () { return api('POST', BASE + '/' + enc(E.id) + '/upload', { confirmed: true, title: title }); },
      onOk: function (res) {
        if (!res || res.configured !== true) { up.configured = false; up.file = null; paint(); return; }
        up.state = 'uploading'; up.pct = 0; up.msg = 'جارٍ الرفع…'; paint();
        var file = up.file;
        K.tusUpload(file, res, function (u, init) { return window.fetch(u, init); }, {
          title: title,
          onProgress: function (sent, total) {
            up.pct = total ? Math.floor(sent * 100 / total) : 0; up.msg = 'تم رفع ' + ar(up.pct) + '٪';
            var bar = q('[data-ce-prog]', E.view), t = q('[data-ce-progt]', E.view);
            if (bar) { bar.style.width = up.pct + '%'; if (bar.parentNode) bar.parentNode.setAttribute('aria-valuenow', up.pct); }
            if (t) t.textContent = up.msg;
          }
        }).then(function () {
          up.state = 'done'; up.pct = 100; up.msg = 'اكتمل الرفع. اضغط «احفظ الدرس» ليرتبط الفيديو بالدرس.';
          var d = draftOf(id); d._video = { touched: true, mode: 'upload', bunny_video_id: res.video_id, url: '' };
          up.file = null; paint();
        }).catch(function (e) { up.state = 'error'; up.msg = (e && e.message) || 'انقطع الرفع. أعد المحاولة.'; paint(); });
      } });
  }

  // ------------------------------------------------------------------ المساعد: طلب وتطبيق
  function ask(scope) {
    var s = asState(scope), lessonId = scope === 'lesson' ? E.lesson : '';
    var errs = K.assistErrors(s.kind, s.instr, s.material, lessonId);
    if (errs.length) { s.err = errs.join('. '); paintKeep(); return; }
    s.err = ''; s.busy = true; s.res = null; s.added = false; paintKeep();
    var body = K.assistBody(s.kind, s.instr, s.material, lessonId), id = E.id;
    api('POST', BASE + '/' + enc(id) + '/brain/draft', body).then(function (res) { s.busy = false; s.res = res; s.choice = 0; paintKeep(); })
      .catch(function (e) { s.busy = false; s.err = errText(e); paintKeep(); });
  }
  function paintKeep() { paint(); }
  function addDraft(scope) {
    var s = asState(scope), x = lessonById(E.lesson); if (!x || !s.res) return;
    var r = K.applyDraft(x.lesson.kind, draftOf(E.lesson), s.res.kind, s.res, s.choice || 0);
    if (r.ok) { E.ld[E.lesson] = r.lesson; s.added = true; delete E.pv[E.lesson]; if (s.res.kind === 'activity_decision') E.open[E.lesson + ':' + (r.lesson.blocks.length - 1)] = true; }
    paint();
  }
  function buildFromMaterial() {
    var s = asState('course'), dr = s.res && s.res.draft; if (!dr || !dr.units) return;
    var merged = K.mergeDraftIntoStructure(K.structFrom(E.course), dr), prevIds = lessonsOf(E.course).map(function (x) { return x.lesson.id; });
    var nl = K.draftLessons(dr).length;
    var errs = K.structureErrors(merged);
    if (errs.length) { s.err = errs.join('. '); paint(); return; }
    confirmSheet({ title: 'أنشئ الهيكل من المادة', lead: 'ستُضاف ' + ar(dr.units.length) + ' وحدات و' + ar(nl) + ' دروس إلى الدورة، ثم يُحفظ ملخّص كل درس ونصه.',
      items: ['يُحفظ الهيكل أولًا، ثم تُحفظ الدروس واحدًا بعد الآخر', 'إن تعذّر حفظ درس يتوقف العمل ويظهر لك السبب'], btn: 'أنشئ الآن', busy: 'جارٍ الإنشاء…',
      send: function () {
        return api('PUT', BASE + '/' + enc(E.id) + '/structure', Object.assign({ confirmed: true }, K.structureBody(merged))).then(function (res) {
          var course = res.course, pairs = K.pairNewLessons(prevIds, course, dr), i = 0;
          setCourse(course, { resetStruct: true });
          function failWith(msg) { var e = new Error(msg); e.status = 400; e.data = { error: msg }; throw e; }
          if (pairs.length !== nl) { refreshList(); failWith('أُنشئ الهيكل، لكن تعذّر مطابقة كل الدروس الجديدة. افتح تبويب «الدروس» وراجعها.'); }
          function next() {
            if (i >= pairs.length) return Promise.resolve(res);
            var p = pairs[i];
            return api('PUT', BASE + '/' + enc(E.id) + '/lessons/' + enc(p.id), Object.assign({ confirmed: true }, p.body)).then(function (r2) { if (r2 && r2.course) setCourse(r2.course, { resetStruct: true }); i++; return next(); })
              .catch(function (e) { refreshList(); var m = errText(e); paint(); failWith('أُنشئ الهيكل وحُفظ ' + ar(i) + ' من ' + ar(pairs.length) + ' دروس، وتعذّر حفظ الدرس «' + p.title + '»: ' + m); });
          }
          return next();
        });
      },
      onOk: function (res) { s.res = null; s.added = false; E.tab = 'lessons'; setNote('أُنشئ الهيكل وحُفظت الدروس. أضف الفيديو لكل درس من تبويب «الدروس».'); refreshList(); paint(); } });
  }

  // ------------------------------------------------------------------ الأحداث
  function readVal(el) {
    var t = el.getAttribute('data-t') || '';
    if (el.type === 'checkbox') return el.checked;
    if (t === 'lines') return K.linesToArr(el.value);
    if (t === 'int') return el.value === '' ? '' : Number(el.value);
    if (t === 'list') return K.linesToArr(el.value.replace(/[,،]/g, '\n'));
    return el.value;
  }
  function applyField(el) {
    var scope = el.getAttribute('data-s'), path = el.getAttribute('data-p'), t = el.getAttribute('data-t') || '';
    if (!scope || !path) return;
    var v = readVal(el);
    if (scope === 'data') { E.dd[path] = v; refreshDirty(); return; }
    if (scope === 'sd') { E.sd = K.setIn(E.sd, path, v); refreshDirty(); return; }
    if (scope === 'les') {
      var d = draftOf(E.lesson);
      if (t === 'vlink') { d._video = { touched: true, mode: String(v).trim() ? 'link' : 'none', url: String(v).trim(), bunny_video_id: '' }; refreshDirty(); return; }
      if (path === 'for') { d.for = v; }
      else E.ld[E.lesson] = K.setIn(d, path, v);
      var m = /^blocks\.(\d+)\./.exec(path);
      if (m) syncBlock(+m[1]);
      refreshDirty();
    }
  }
  // بعد تعديل حقل كتلة: نحدّث رأسها ومربع JSON فقط (دون إعادة رسم)
  function syncBlock(i) {
    var d = draftOf(E.lesson), b = d.blocks[i], card = q('[data-blk="' + i + '"]', E.view);
    if (!card || !b) return;
    var h = q('.v2ce-bhead', card); if (h) h.textContent = K.blockHead(b);
    var ta = q('[data-ce-json]', card); if (ta && document.activeElement !== ta) ta.value = JSON.stringify(b, null, 2);
  }
  function refreshDirty() {
    if (!E.view) return;
    var tabs = q('.v2ce-tabs', E.view);
    if (tabs) {
      var dirty = { data: dataDirty(), structure: structDirty(), lessons: Object.keys(E.ld).some(lessonDirty) };
      qa('.v2ce-tab', tabs).forEach(function (b) {
        var k = b.getAttribute('data-tab'), dot = q('.v2ce-dot', b);
        if (dirty[k] && !dot) b.insertAdjacentHTML('beforeend', '<i class="v2ce-dot" title="تعديلات لم تُحفظ"></i>');
        if (!dirty[k] && dot) dot.remove();
      });
    }
    var sd = q('[data-ce="save-data"]', E.view); if (sd) sd.disabled = !dataDirty();
    var ss = q('[data-ce="save-struct"]', E.view); if (ss) ss.disabled = !structDirty();
    var sm = q('.v2ce-sum', E.view); if (sm && E.tab === 'structure') { var df = K.structureDiff(K.structFrom(E.course), E.sd); sm.textContent = df.changed ? structSummaryLine(df) : 'لا تغييرات غير محفوظة في الهيكل'; }
  }
  function onInput(e) {
    var el = e.target;
    if (!E || !el || !el.getAttribute) return;
    if (el.hasAttribute('data-as')) { var s = asState(el.getAttribute('data-scope')); s[el.getAttribute('data-as')] = el.value; return; }
    if (el.hasAttribute('data-as-choice')) { asState(el.getAttribute('data-scope')).choice = +el.getAttribute('data-as-choice'); return; }
    if (el.hasAttribute('data-s') && el.type !== 'checkbox' && el.tagName !== 'SELECT') applyField(el);
  }
  function onChange(e) {
    var el = e.target;
    if (!E || !el || !el.getAttribute) return;
    if (el.hasAttribute('data-ce-json')) { applyJson(+el.getAttribute('data-ce-json'), el); return; }
    if (el.hasAttribute('data-ce-file')) {
      var id = el.getAttribute('data-ce-file'), up = E.up[id] || (E.up[id] = {});
      up.file = el.files && el.files[0] ? el.files[0] : null; up.state = 'idle'; up.msg = '';
      paint(); return;
    }
    if (el.hasAttribute('data-as-choice')) { asState(el.getAttribute('data-scope')).choice = +el.getAttribute('data-as-choice'); return; }
    if (el.hasAttribute('data-s') && (el.type === 'checkbox' || el.tagName === 'SELECT')) applyField(el);
  }
  var jsonBusy = false;
  function applyJson(i, ta) {
    if (jsonBusy) return;   // استبدال البطاقة يسحب التركيز فيُطلق «change» ثانية: لا نعيد الدخول
    jsonBusy = true;
    try { applyJson2(i, ta); } finally { jsonBusy = false; }
  }
  function applyJson2(i, ta) {
    var r = K.parseBlockJson(ta.value), err = q('[data-ce-jerr="' + i + '"]', E.view);
    if (!r.ok) { if (err) err.innerHTML = '<div class="v2co-errbox" role="alert">' + esc(r.error) + '</div>'; return; }
    if (err) err.innerHTML = '';
    var d = draftOf(E.lesson), blocks = d.blocks.slice(); blocks[i] = r.block; d.blocks = blocks; delete E.pv[E.lesson];
    var card = q('[data-blk="' + i + '"]', E.view);
    if (card) {   // نعيد رسم البطاقة وحدها حتى لا نبتلع ضغطة على زر خارجها
      var tmp = document.createElement('div'); tmp.innerHTML = blockHtml(r.block, i, blocks.length);
      var nu = tmp.firstChild; nu.querySelector('details.v2ce-adv').open = true;
      if (card.parentNode) card.parentNode.replaceChild(nu, card);
    }
    refreshDirty();
  }

  function swap(arr, i, j) { var t = arr[i]; arr[i] = arr[j]; arr[j] = t; }
  function openIdx(i, v) { E.open[E.lesson + ':' + i] = v; }
  var ACT = {
    back: function () { goBack(); },
    retry: function () { E.state = 'idle'; paint(); loadCourse(true); },
    tab: function (el) { E.tab = el.getAttribute('data-tab'); E.note = ''; paint(); },
    pick: function (el) { E.lesson = el.getAttribute('data-id'); E.picker = false; draftOf(E.lesson); paint(); },
    'save-data': function () { saveData(); },
    'save-struct': function () { saveStruct(); },
    'save-lesson': function () { saveLesson(); },
    preview: function () { previewLesson(); },
    'return': function () { openReturn(); },
    publish: function () { openPublish(); },
    pause: function () { openPause(); },
    upload: function () { startUpload(); },
    'video-clear': function () { var d = draftOf(E.lesson); d._video = { touched: true, mode: 'none', url: '', bunny_video_id: '' }; paint(); },
    'cp-add': function () { var d = draftOf(E.lesson); d.checkpoints = (d.checkpoints || []).concat([{ t: '', question: '', options: [{ text: '', ok: true, explanation: '' }, { text: '', ok: false, explanation: '' }] }]); paint(); },
    'row-add': function (el) {
      var d = draftOf(E.lesson), p = el.getAttribute('data-p'), row = JSON.parse(el.getAttribute('data-cols') || '{}');
      var arr = (getP(d, p) || []).slice(); arr.push(row); E.ld[E.lesson] = K.setIn(d, p, arr); paint();
    },
    'row-del': function (el) {
      var d = draftOf(E.lesson), p = el.getAttribute('data-p'), arr = (getP(d, p) || []).slice(); arr.splice(+el.getAttribute('data-i'), 1); E.ld[E.lesson] = K.setIn(d, p, arr); paint();
    },
    picker: function () { E.picker = !E.picker; paint(); },
    'blk-add': function (el) {
      var d = draftOf(E.lesson), nb = K.blankBlock(el.getAttribute('data-type'));
      d.blocks = K.blocksAdd(d.blocks, nb); openIdx(d.blocks.length - 1, true); E.picker = false; delete E.pv[E.lesson]; paint();
    },
    'blk-toggle': function (el) {
      var i = +el.getAttribute('data-i'), card = el.closest('.v2ce-blk'), on = !card.classList.contains('open');
      card.classList.toggle('open', on); el.setAttribute('aria-expanded', on); openIdx(i, on);
    },
    'blk-up': function (el) { moveBlk(+el.getAttribute('data-i'), -1); },
    'blk-down': function (el) { moveBlk(+el.getAttribute('data-i'), 1); },
    'blk-del': function (el) {
      var d = draftOf(E.lesson), i = +el.getAttribute('data-i'), open = [];
      for (var k = 0; k < d.blocks.length; k++) open.push(E.open[E.lesson + ':' + k] === true);
      open.splice(i, 1); d.blocks = K.blocksDelete(d.blocks, i);
      open.forEach(function (o, k) { E.open[E.lesson + ':' + k] = o; }); delete E.open[E.lesson + ':' + open.length]; delete E.pv[E.lesson]; paint();
    },
    'un-add': function () { E.sd = E.sd.concat([{ title: '', lessons: [] }]); paint(); },
    'un-up': function (el) { var u = +el.getAttribute('data-u'); E.sd = K.blocksMove(E.sd, u, -1); paint(); },
    'un-down': function (el) { var u = +el.getAttribute('data-u'); E.sd = K.blocksMove(E.sd, u, 1); paint(); },
    'un-del': function (el) { delUnit(+el.getAttribute('data-u')); },
    'ls-add': function (el) { var u = +el.getAttribute('data-u'), sd = JSON.parse(JSON.stringify(E.sd)); sd[u].lessons.push({ title: '', kind: el.getAttribute('data-kind') }); E.sd = sd; paint(); },
    'ls-up': function (el) { moveLs(+el.getAttribute('data-u'), +el.getAttribute('data-l'), -1); },
    'ls-down': function (el) { moveLs(+el.getAttribute('data-u'), +el.getAttribute('data-l'), 1); },
    'ls-del': function (el) { delLs(+el.getAttribute('data-u'), +el.getAttribute('data-l')); },
    'as-kind': function (el) { var s = asState(el.getAttribute('data-scope')); s.kind = el.getAttribute('data-kind'); s.res = null; s.err = ''; s.added = false; paint(); },
    'as-ask': function (el) { ask(el.getAttribute('data-scope')); },
    'as-add': function (el) { addDraft(el.getAttribute('data-scope')); },
    'as-build': function () { buildFromMaterial(); }
  };
  function moveBlk(i, dir) {
    var d = draftOf(E.lesson), j = i + dir; if (j < 0 || j >= d.blocks.length) return;
    var a = E.open[E.lesson + ':' + i] === true, b = E.open[E.lesson + ':' + j] === true;
    d.blocks = K.blocksMove(d.blocks, i, dir); E.open[E.lesson + ':' + i] = b; E.open[E.lesson + ':' + j] = a; delete E.pv[E.lesson]; paint();
  }
  function moveLs(u, l, dir) {
    var sd = JSON.parse(JSON.stringify(E.sd)), ls = sd[u].lessons, j = l + dir;
    if (j >= 0 && j < ls.length) { swap(ls, l, j); }
    else if (dir < 0 && u > 0) { var it = ls.splice(l, 1)[0]; sd[u - 1].lessons.push(it); }
    else if (dir > 0 && u < sd.length - 1) { var it2 = ls.splice(l, 1)[0]; sd[u + 1].lessons.unshift(it2); }
    E.sd = sd; paint();
  }
  function delLs(u, l) {
    var ls = E.sd[u].lessons[l];
    if (!ls) return;
    var done = function () { var sd = JSON.parse(JSON.stringify(E.sd)); sd[u].lessons.splice(l, 1); E.sd = sd; paint(); };
    if (ls.id && ls.hasContent) {
      kit().flow({ title: 'احذف الدرس', review: function () { return '<p class="v2co-lead">للدرس «' + esc(ls.title) + '» محتوى. سيُمسح من الدورة نهائيًا عند حفظ الهيكل.</p>'; },
        btnConfirm: 'احذف الدرس من الهيكل', danger: true, send: function () { return Promise.resolve({}); }, onOk: done });
    } else done();
  }
  function delUnit(u) {
    var un = E.sd[u]; if (!un) return;
    var withC = (un.lessons || []).filter(function (l) { return l.id && l.hasContent; });
    var done = function () { var sd = E.sd.slice(); sd.splice(u, 1); E.sd = sd; paint(); };
    if (withC.length) {
      kit().flow({ title: 'احذف الوحدة', review: function () { return '<p class="v2co-lead">في الوحدة «' + esc(un.title) + '» دروس لها محتوى: ' + esc(withC.map(function (l) { return l.title; }).join('، ')) + '. سيُمسح من الدورة نهائيًا عند حفظ الهيكل.</p>'; },
        btnConfirm: 'احذف الوحدة من الهيكل', danger: true, send: function () { return Promise.resolve({}); }, onOk: done });
    } else done();
  }
  function goBack() {
    var dirty = anyDirty() ? dirtyList() : [];
    var leave = function () { var k = kit(); if (k && k.closeEditor) k.closeEditor(); };
    if (dirty.length) {
      kit().flow({ title: 'اترك المحرّر', review: function () { return '<p class="v2co-lead">عندك تعديلات لم تُحفظ: ' + esc(dirty.join('، ')) + '. ستضيع إن خرجت الآن.</p>'; },
        btnConfirm: 'اخرج دون حفظ', danger: true, send: function () { return Promise.resolve({}); }, onOk: function () { E = null; leave(); } });
    } else { E = null; leave(); }
  }
  function onClick(e) {
    var t = e.target;
    if (!E || !t || !t.closest) return;
    var el = t.closest('[data-ce]');
    if (!el || !E.view || !E.view.contains(el)) return;
    var h = ACT[el.getAttribute('data-ce')];
    if (h) { e.preventDefault(); h(el, e); }
  }

  // ------------------------------------------------------------------ نقاط الدخول
  CE.draw = function (v, id) {
    if (!E || E.id !== id) E = fresh(id);
    E.view = v;
    if (!v.__v2ce) {
      v.__v2ce = true;
      v.addEventListener('click', onClick); v.addEventListener('input', onInput); v.addEventListener('change', onChange);
    }
    paint();
    loadCourse(false);
  };
  CE.active = function () { return !!E; };
  CE.dirty = function () { return E ? anyDirty() : false; };
  CE._state = function () { return E; };

  // «أنشئ دورة»: عنوان + صاحب الدورة (مدرّب أو «دورة من المنصّة»). مفتاح منع التكرار يُولَّد مرة واحدة عند فتح الورقة.
  CE.openCreate = function (opts) {
    opts = opts || {};
    var k = kit(); if (!k) return;
    var idem = K.idemKey(function () { try { return window.crypto && window.crypto.randomUUID ? window.crypto.randomUUID() : ''; } catch (e) { return ''; } });
    var trainers = (k.trainerOptions ? k.trainerOptions() : []);
    var optsHtml = '<option value="">دورة من المنصّة (البروفيسور)</option>' + trainers.map(function (r) { return '<option value="' + esc(r.email) + '">' + esc(r.name) + '</option>'; }).join('');
    k.flow({
      title: 'أنشئ دورة',
      form: '<p class="v2co-lead">تُنشأ الدورة مسودة لا يراها الناس، وتبني دروسها بعدها في المحرّر.</p>'
        + k.fld('ce_ti', 'عنوان الدورة', '<input id="ce_ti" type="text" maxlength="160" autocomplete="off" value="' + esc(opts.title || '') + '">')
        + k.fld('ce_ow', 'صاحب الدورة', '<select id="ce_ow">' + optsHtml + '</select>', 'اختر مدرّبًا، أو اترك «دورة من المنصّة»'),
      wire: function (s) { setTimeout(function () { try { q('#ce_ti', s).focus(); } catch (e) {} }, 30); },
      collect: function (s) {
        var title = q('#ce_ti', s).value.trim();
        if (!title) return { ok: false, error: 'اكتب عنوان الدورة' };
        if (title.length > 160) return { ok: false, error: 'العنوان طويل: الحد ١٦٠ حرفًا' };
        var sel = q('#ce_ow', s), email = sel.value, op = sel.options[sel.selectedIndex];
        return { ok: true, payload: { title: title, email: email, who: email ? op.textContent : 'البروفيسور' } };
      },
      review: function (p) { return '<p class="v2co-lead">ما سيحدث:</p>' + k.listHtml(['تُنشأ الدورة «' + esc(p.title) + '» مسودة باسم ' + esc(p.who) + '.', 'تبني هيكلها ودروسها في المحرّر، ثم تنشرها من تبويب «المراجعة والنشر».']); },
      btnNext: 'راجع قبل الإنشاء', btnConfirm: 'أنشئ المسودة', busy: 'جارٍ الإنشاء…',
      send: function (p) {
        var b = { confirmed: true, title: p.title, idem_key: idem };
        if (p.email) b.owner_email = p.email; else b.platform_owned = true;
        return api('POST', BASE, b);
      },
      onOk: function (res) {
        var c = res && res.course;
        if (k.reloadList) k.reloadList();
        if (typeof opts.done === 'function') { opts.done(res); return; }
        if (c && c.id && k.openEditorFor) k.openEditorFor(c.id, 'أُنشئت الدورة مسودة. ابدأ من تبويب «الهيكل».', 'structure');
      }
    });
  };
  CE.start = function (id, note, tab) {   // يُنادى من courses.js حين يُفتح المحرّر
    if (!E || E.id !== id) E = fresh(id);
    else E.state = 'idle';                   // رجوع لمحرّر مفتوح قبل: نعيد جلب الدورة، والمسودّات غير المحفوظة تبقى
    if (tab) E.tab = tab;
    if (note) setNote(note);
  };
})();
