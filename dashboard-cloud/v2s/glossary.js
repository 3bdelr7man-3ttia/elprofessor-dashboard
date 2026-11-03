/* ============================================================================
 * v2s/glossary.js — المنطق النقي لتبويب «القاموس» (المصطلحات القانونية بثلاث لغات) في قسم «المحتوى» (لا DOM ولا شبكة ولا ساعة خفية).
 *   ١) المصطلحات: القائمة والبحث والمجال والحالة (مسودة · تحت التأكيد · مؤكّد) · ٢) النموذج: إنشاء وتعديل بالفرق فقط وتحذير ختم المراجعة
 *   ٣) ختم «راجعه» (مع موافقة المراجع على ظهور اسمه) ومسحه · ٤) النشر وإلغاؤه والحذف (النشر بلا ختم ⇒ «تحت التأكيد»، ويُمنع فقط ما دام الشرط مفعّلًا)
 *   ٥) شرط المراجعة (إعداد، الافتراضي مغلق) · ٦) نقاش «الساحة» (ربط موجود وفصله) · ٧) الاستيراد: مصدر مدمج أو ملف ⇒ تجربة بلا حفظ ثم تأكيد
 *   ٨) «مراجعات القاموس»: ما يقدّمه المتخصصون من الموقع ⇒ اعتمد (يختم المصطلح أو يفتح اقتراحه) · ارفض · تمّ (دورة أو مسار).
 *   ٩) نقاش «الساحة» الجديد: لكل مصطلح منشور (معاينة بلا كتابة ⇒ تأكيد) ولكل المنشور بلا نقاش دفعةً (معاينة ⇒ تأكيد ⇒ نتيجة لكل مصطلح).
 * قرار المؤسس ٢٠٢٦-١١-٠١: «نفتحه للنقاش ونلمّ الاعتراضات» ⇒ المراجعات مطفأة افتراضيًا (`reviews_enabled` في ردّ الخادم): الحالات «مسودة / منشور» فقط،
 *   ولا شارة «تحت التأكيد» ولا صندوق مراجعات ولا شرط مراجعة، و«راجعه» ختم داخلي في المحرّر لا يظهر على الموقع. الكود كله باقٍ ويعمل حين يُفعَّل الإعداد.
 * الواجهة في `saha_glossary.js` (ركبت على محرّك الساحة فتُحمَّل بعد `saha_diwan.js`). ⛔ التحقق هنا يطابق الخادم (v2_glossary_routes.py) والتحقق النهائي عنده. المصدر الفاشل = null (والشاشة تكتب «غير متاح بعد»).
 * ⛔ نصوص ظاهرة: فصحى بسيطة محايدة للجنس، بلا مصطلحات تقنية، «·» لا تلاصق رقمًا (نستعمل «،»)، والنص الإنجليزي والفرنسي يبقى برقمه اللاتيني.
 * ========================================================================== */
(function (root) {
  'use strict';
  var L = root.V2L;
  if (!L || !L.util) return;
  var Un = L.util, ar = Un.ar, U = Un.U;
  var DIG = '٠١٢٣٤٥٦٧٨٩';
  var MONTHS = ['يناير', 'فبراير', 'مارس', 'أبريل', 'مايو', 'يونيو', 'يوليو', 'أغسطس', 'سبتمبر', 'أكتوبر', 'نوفمبر', 'ديسمبر'];
  var OTHER = 'other';
  var NA = 'غير متاح بعد';
  var SESSION_AR = 'انتهت الجلسة، سجّل الدخول من جديد ثم جرّب';
  var NEEDS_REVIEW_AR = 'يُنشر بعد أن يراجعه خبير';
  var SITE = 'https://elprofessor.net/glossary/';
  var SAHA_APP = 'https://app.elprofessor.net/?page=saha&topic=';
  var SLUG_RE = /^[a-z](?:[a-z0-9-]{0,62}[a-z0-9])?$/;
  var TOPIC_RE = /^[A-Za-z0-9_-]{8,64}$/;
  var URL_RE = /https?:\/\/|www\./i;
  var CTRL_RE = /[\x00-\x08\x0b\x0c\x0e-\x1f]/g;
  var RELATED_MAX = 20;
  var IMPORT_MAX = 500;

  function str(v) { return typeof v === 'string' ? v.trim() : ''; }
  function isNum(v) { return typeof v === 'number' && isFinite(v); }
  function arDigits(s) { return String(s == null ? '' : s).replace(/\d/g, function (d) { return DIG.charAt(+d); }); }
  function toLatin(s) { return String(s == null ? '' : s).replace(/[٠-٩]/g, function (d) { return String(DIG.indexOf(d)); }); }
  // «·» ما تلاصق رقمًا أبدًا: تتحول «،». (حارس أخير لأي نص جاء من خارج هذا الملف)
  function fixSep(s) {
    return String(s == null ? '' : s).replace(/([\d٠-٩])\s*·\s*/g, '$1، ').replace(/\s*·\s*([\d٠-٩])/g, '، $1');
  }
  function labelOf(list, key) { for (var i = 0; i < list.length; i++) if (list[i][0] === key) return list[i][1]; return ''; }
  function short(s, n) { s = String(s == null ? '' : s).replace(/\s+/g, ' ').trim(); return s.length > n ? s.slice(0, n) + '…' : s; }
  function dayText(v) {
    var m = /^(\d{4})-(\d{2})-(\d{2})/.exec(str(v));
    if (!m) return '';
    var mo = +m[2];
    if (mo < 1 || mo > 12) return '';
    return ar(+m[3]) + ' ' + MONTHS[mo - 1] + ' ' + arDigits(m[1]);
  }
  function slugify(text) {
    var s = String(text == null ? '' : text).toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-+|-+$/g, '').slice(0, 64).replace(/-+$/g, '');
    return SLUG_RE.test(s) ? s : '';
  }
  function plain(v) { return typeof v === 'string' ? v.replace(CTRL_RE, '').trim() : ''; }
  // اسم أو صفة مراجع: مسافات مفردة، بلا روابط ولا @ (نفس `person` في الخادم)
  function person(v) { return typeof v === 'string' ? v.replace(CTRL_RE, '').replace(/\s+/g, ' ').trim() : ''; }

  // ------------------------------------------------------------------ جداول التسميات
  var AREAS = [['contracts', 'عقود'], ['litigation', 'تقاضٍ'], ['corporate', 'شركات'], ['general', 'عام'], ['arbitration', 'تحكيم'],
               ['criminal', 'جنائي'], ['ip', 'ملكية فكرية'], ['labor', 'عمل'], ['family', 'أسرة'],
               ['realestate', 'عقارات'], ['banking', 'بنوك ومصارف'], ['data', 'البيانات والخصوصية'], [OTHER, 'أخرى']];
  var STATUS_CHIPS = [['all', 'الكل'], ['confirmed', 'مؤكّد'], ['under_review', 'تحت التأكيد'], ['draft', 'مسودة']];
  var STATUS_CHIPS_OFF = [['all', 'الكل'], ['published', 'منشور'], ['draft', 'مسودة']];
  function statusChips(on) { return on ? STATUS_CHIPS : STATUS_CHIPS_OFF; }
  var STATE_TEXT = { draft: 'مسودة', under_review: 'تحت التأكيد', confirmed: 'مؤكّد' };
  var REVIEW_KINDS = [['glossary_term', 'مصطلح'], ['course', 'دورة'], ['track', 'مسار']];
  var REVIEW_STATUS_CHIPS = [['pending', 'تنتظر القرار'], ['approved', 'اعتُمدت'], ['rejected', 'رُفضت'], ['all', 'الكل']];
  var REVIEW_KIND_CHIPS = [['all', 'الكل']].concat(REVIEW_KINDS);
  var REVIEW_STATUS_TEXT = { pending: 'تنتظر القرار', approved: 'اعتُمدت', rejected: 'رُفضت' };
  var VERDICT_TEXT = { confirm: 'يؤكد الترجمة والتعريف', suggest: 'يقترح تعديلًا' };
  var NOTE_MAX = 500;
  var REVIEW_CHIPS = [['all', 'الكل'], ['reviewed', 'راجعه خبير'], ['unreviewed', 'ينتظر خبيرًا']];
  var SUBSTANTIVE = ['ar', 'en', 'fr', 'definition_ar', 'example_en', 'example_ar', 'false_friend_note_ar', 'countries_note_ar'];
  // [الاسم، التسمية، الحد الأقصى، مطلوب، لاتيني]
  var FIELDS = [['ar', 'المصطلح بالعربية', 300, true, false], ['en', 'المصطلح بالإنجليزية', 300, true, true], ['fr', 'المصطلح بالفرنسية', 300, false, true],
                ['definition_ar', 'التعريف', 3000, true, false], ['example_en', 'المثال بالإنجليزية', 1500, false, true], ['example_ar', 'المثال بالعربية', 1500, false, false],
                ['false_friend_note_ar', 'الخطأ الشائع', 2000, false, false], ['countries_note_ar', 'ملاحظة الدول', 2000, false, false]];
  var IMPORT_SOURCES = [['seed', 'القاموس الأساسي (٨٠)'], ['course1', 'مرشّحة من دورة القراءة (٣١)'], ['ext', 'توسعة القاموس (١٥٠)'], ['upload', 'ملف من جهازك']];
  var PROBLEM_LABELS = FIELDS.map(function (f) { return [f[0], f[1]]; }).concat([['slug', 'رابط المصطلح'], ['area', 'المجال'], ['related', 'المصطلحات القريبة']]);

  function areaText(code) { return labelOf(AREAS, str(code)) || labelOf(AREAS, OTHER); }
  function areaChips(counts) {
    var by = counts && counts.byArea ? counts.byArea : null;
    return [['all', 'الكل']].concat(AREAS.map(function (a) { var n = by ? by[a[0]] : 0; return n ? [a[0], a[1], ar(n)] : [a[0], a[1]]; }));      // العدّاد عنصر ثالث يُرسم دائرة داخل الشريحة (لا أقواس)
  }
  function countWord(n, forms, none) { return n ? U(n, forms) : none; }

  // ------------------------------------------------------------------ أخطاء الكتابة (نص الخادم العربي يعدّي بنفس الكود)
  function writeError(status, data) {
    var msg = data && typeof data.error === 'string' ? data.error : '';
    if (data && data.no_reply) return msg || 'لم يصل رد. حدّث الصفحة ثم أعد المحاولة.';
    if (status === 401) return SESSION_AR;
    if (msg && /[؀-ۿ]/.test(msg) && (status === 400 || status === 404 || status === 409 || status === 422 || status === 502)) return problemText(msg);
    if (status === 404) return 'لم يعد هذا المصطلح موجودًا، حدّث الصفحة';
    if (status === 409) return 'تغيّرت حالة هذا المصطلح، حدّث الصفحة وحاول مرة أخرى';
    if (status === 400 || status === 422) return 'لم يُقبل هذا الطلب، راجع البيانات وحاول مرة أخرى';
    return 'تعذّر تنفيذ العملية، حاول مرة أخرى';
  }
  // رسائل التحقق في الخادم تذكر اسم الحقل بالإنجليزية (مثل «definition_ar: …») فنستبدله بتسميته العربية
  function problemText(msg) {
    var t = String(msg == null ? '' : msg);
    PROBLEM_LABELS.slice().sort(function (a, b) { return b[0].length - a[0].length; }).forEach(function (p) {
      t = t.replace(new RegExp('(^|[^A-Za-z_])' + p[0] + '(?![A-Za-z_])', 'g'), function (m, pre) { return pre + p[1]; });
    });
    return arDigits(t);
  }

  // ------------------------------------------------------------------ ١ · القائمة
  // on = المراجعات مفعّلة (`reviews_enabled`). مطفأة: «مسودة / منشور» فقط ولا شارة موقع.
  function toRow(r, on) {
    var st = r.status === 'confirmed' || r.status === 'under_review' ? r.status : 'draft';
    on = on === true;
    var area = labelOf(AREAS, str(r.area)) ? str(r.area) : OTHER;
    var name = str(r.reviewed_by_name), role = str(r.reviewed_by_role);
    var rev = r.reviewed === true && !!name && !!role;
    var slug = str(r.slug), tid = str(r.saha_topic_id), frozen = r.slug_frozen === true;
    return {
      id: String(r.id), slug: slug, ar: str(r.ar) || 'مصطلح بلا عنوان', en: str(r.en), fr: str(r.fr), area: area, areaText: areaText(area),
      definition: str(r.definition_ar), exampleEn: str(r.example_en), exampleAr: str(r.example_ar), falseFriend: str(r.false_friend_note_ar), countries: str(r.countries_note_ar),
      related: Array.isArray(r.related) ? r.related.filter(function (x) { return typeof x === 'string' && SLUG_RE.test(x); }) : [],
      status: st, published: st !== 'draft', confirmed: st === 'confirmed', underReview: st === 'under_review', reviewsOn: on, statusText: on ? STATE_TEXT[st] : (st === 'draft' ? 'مسودة' : 'منشور'),
      reviewed: rev, reviewerName: rev ? name : '', reviewerRole: rev ? role : '', reviewedOn: rev ? dayText(r.reviewed_at) : '', namePublic: rev && r.reviewer_name_public === true,
      reviewLine: rev ? 'راجعه: ' + name + '، ' + role : '',
      siteBadge: !on ? '' : st === 'confirmed' ? (rev && r.reviewer_name_public === true ? 'راجعه: ' + name + '، ' + role : 'راجعه متخصص') : (st === 'under_review' ? 'تحت التأكيد: نبحث عن متخصص يراجع هذا المصطلح' : ''),
      topicId: TOPIC_RE.test(tid) ? tid : '', frozen: frozen, source: str(r.source),
      canDelete: st === 'draft' && !frozen, previewUrl: st !== 'draft' && SLUG_RE.test(slug) ? SITE + slug + '.html' : ''
    };
  }
  // resp = ردّ GET /v2/content/glossary ⇒ null لو المصدر فشل
  function terms(resp) {
    if (!resp || typeof resp !== 'object' || !Array.isArray(resp.items)) return null;
    var on = resp.reviews_enabled === true;
    var rows = resp.items.filter(function (r) { return r && typeof r === 'object' && r.id != null && str(String(r.id)); }).map(function (r) { return toRow(r, on); });
    var c = resp.counts && typeof resp.counts === 'object' ? resp.counts : null;
    var n = function (k, d) { return c && isNum(c[k]) ? c[k] : d; };
    var rev = rows.filter(function (r) { return r.reviewed; }).length;
    var pub = rows.filter(function (r) { return r.published; }).length;
    var under = rows.filter(function (r) { return r.underReview; }).length, conf = rows.filter(function (r) { return r.confirmed; }).length;
    var by = {};
    AREAS.forEach(function (a) { by[a[0]] = c && c.by_area && isNum(c.by_area[a[0]]) ? c.by_area[a[0]] : rows.filter(function (r) { return r.area === a[0]; }).length; });
    var counts = { all: n('all', rows.length), draft: n('draft', rows.length - pub), underReview: n('under_review', under), confirmed: n('confirmed', conf), published: n('published', pub),
                   reviewed: n('reviewed', rev), unreviewed: n('unreviewed', rows.length - rev), publishedUnreviewed: n('published_unreviewed', under),
                   reviewsPending: on ? n('reviews_pending', 0) : 0, publishedNoTopic: n('published_no_topic', rows.filter(function (r) { return r.published && !r.topicId; }).length), reviewsOn: on, byArea: by };
    var total = isNum(resp.total) ? resp.total : rows.length;
    return { rows: rows, total: total, counts: counts, reviewsEnabled: on, requireReview: on && resp.require_review === true, truncated: total > rows.length };
  }
  function summary(counts) {
    if (!counts) return '';
    if (!counts.reviewsOn) return 'منشور ' + ar(counts.published) + '، مسودة ' + ar(counts.draft);
    return 'مؤكّد ' + ar(counts.confirmed) + '، تحت التأكيد ' + ar(counts.underReview) + '، مسودة ' + ar(counts.draft);
  }
  function termCountText(n) { return countWord(n, ['مصطلح واحد', 'مصطلحان', 'مصطلحات', 'مصطلحًا'], 'لا مصطلحات هنا'); }
  // بحث بلا حساسية لحالة الحروف ولا للتشكيل ولا لصور الألف
  function norm(s) {
    return toLatin(s).toLowerCase().replace(/[ً-ٰٟـ]/g, '').replace(/[أإآٱ]/g, 'ا').replace(/ى/g, 'ي').replace(/ة/g, 'ه').replace(/\s+/g, ' ').trim();
  }
  // f = {q, area, status, review} ⇒ الصفوف المطابقة (نفس منطق الخادم: ar/en/fr/التعريف/الرابط)
  function filterRows(rows, f) {
    f = f || {};
    var q = norm(f.q);
    return (rows || []).filter(function (r) {
      if (f.area && f.area !== 'all' && r.area !== f.area) return false;
      if (f.status === 'published' && !r.published) return false;
      if ((f.status === 'draft' || f.status === 'under_review' || f.status === 'confirmed') && r.status !== f.status) return false;
      if (f.review === 'reviewed' && !r.reviewed) return false;
      if (f.review === 'unreviewed' && r.reviewed) return false;
      if (!q) return true;
      return norm([r.ar, r.en, r.fr, r.definition, r.slug].join(' ')).indexOf(q) > -1;
    });
  }
  function bySlug(rows) { var m = {}; (rows || []).forEach(function (r) { m[r.slug] = r; }); return m; }
  // القريبة: كل slug ⇒ {slug, label, known, id}
  function relatedView(row, rows) {
    var m = bySlug(rows);
    return (row.related || []).map(function (s) { var r = m[s]; return { slug: s, label: r ? r.ar : s, known: !!r, id: r ? r.id : '' }; });
  }
  function relatedOptions(rows, selfSlug, chosen) {
    return (rows || []).filter(function (r) { return r.slug !== selfSlug && (chosen || []).indexOf(r.slug) < 0; })
      .sort(function (a, b) { return a.en.toLowerCase() < b.en.toLowerCase() ? -1 : (a.en.toLowerCase() > b.en.toLowerCase() ? 1 : 0); })
      .map(function (r) { return [r.slug, r.ar + ' — ' + r.en]; });
  }
  function previewUrl(slug) { return SLUG_RE.test(str(slug)) ? SITE + str(slug) + '.html' : ''; }
  function topicUrl(id) { return TOPIC_RE.test(str(id)) ? SAHA_APP + str(id) : ''; }

  // ------------------------------------------------------------------ ٢ · النموذج (إنشاء وتعديل)
  function termForm(row) {
    var r = row || {};
    return { slug: r.slug || '', ar: row ? r.ar : '', en: r.en || '', fr: r.fr || '', area: r.area || '', definition_ar: r.definition || '', example_en: r.exampleEn || '', example_ar: r.exampleAr || '',
             false_friend_note_ar: r.falseFriend || '', countries_note_ar: r.countries || '', related: (r.related || []).slice() };
  }
  var FIELD_ORIG = { ar: 'ar', en: 'en', fr: 'fr', definition_ar: 'definition', example_en: 'exampleEn', example_ar: 'exampleAr', false_friend_note_ar: 'falseFriend', countries_note_ar: 'countries' };
  function sameList(a, b) { return JSON.stringify(a || []) === JSON.stringify(b || []); }
  function areaValue(v) { return v ? areaText(v) : 'فارغ'; }
  // mode: 'create' | 'edit'. orig: الصف عند التعديل. nameOf(slug) ⇒ اسم عربي للقريب. ⇒ {ok, error, errors, body, lines, warns, lead, goLabel}
  function termCheck(form, mode, orig, requireReview, nameOf) {
    form = form || {};
    var create = mode === 'create', errors = {}, v = {};
    FIELDS.forEach(function (f) {
      var raw = form[f[0]];
      if (raw != null && typeof raw !== 'string') { errors[f[0]] = f[1] + ' نص'; return; }
      var t = plain(raw);
      if (!t && f[3]) errors[f[0]] = f[1] + ' مطلوب';
      else if (URL_RE.test(t)) errors[f[0]] = 'لا تضع روابط في النص';
      else if (t.length > f[2]) errors[f[0]] = f[1] + ' حتى ' + ar(f[2]) + ' حرف';
      v[f[0]] = t;
    });
    var area = str(form.area);
    if (!labelOf(AREAS, area)) errors.area = 'اختر المجال، أو «أخرى»';
    var frozen = !create && orig && orig.frozen, slug = str(form.slug);
    if (frozen) slug = orig.slug;
    else if (!slug) {
      if (create) { slug = slugify(v.en); if (!slug && !errors.en) errors.slug = 'اكتب رابط المصطلح بحروف إنجليزية صغيرة'; }
      else errors.slug = 'رابط المصطلح مطلوب';
    }
    if (slug && !SLUG_RE.test(slug)) errors.slug = 'الرابط حروف إنجليزية صغيرة وأرقام وشرطات فقط، مثل force-majeure';
    var rel = [];
    (Array.isArray(form.related) ? form.related : []).forEach(function (s) { s = str(s); if (s && rel.indexOf(s) < 0) rel.push(s); });
    if (rel.length > RELATED_MAX) errors.related = 'المصطلحات القريبة حتى ' + ar(RELATED_MAX);
    else if (rel.some(function (s) { return !SLUG_RE.test(s); })) errors.related = 'رابط مصطلح قريب غير صالح';
    if (Object.keys(errors).length) return { ok: false, error: 'صحّح الخانات المعلَّمة', errors: errors };

    var nm = nameOf || function (s) { return s; };
    var relShow = function (list) { return list && list.length ? list.map(nm).join('، ') : 'فارغ'; };
    var body = {}, lines = [], warns = [];
    function put(key, label, before, after, show, ltr) {
      body[key] = after;
      lines.push({ label: label, from: create ? '' : (show ? show(before) : (before || 'فارغ')), to: show ? show(after) : (after || 'فارغ'), ltr: !!ltr });
    }
    var shortShow = function (x) { return x ? short(x, 120) : 'فارغ'; };
    if (create) {
      body.slug = slug; body.ar = v.ar; body.en = v.en; body.area = area; body.definition_ar = v.definition_ar;
      lines.push({ label: 'المصطلح', from: '', to: v.ar }, { label: 'بالإنجليزية', from: '', to: v.en, ltr: true });
      if (v.fr) { body.fr = v.fr; lines.push({ label: 'بالفرنسية', from: '', to: v.fr, ltr: true }); }
      lines.push({ label: 'المجال', from: '', to: areaText(area) }, { label: 'التعريف', from: '', to: short(v.definition_ar, 120) });
      ['example_en', 'example_ar', 'false_friend_note_ar', 'countries_note_ar'].forEach(function (k) {
        if (v[k]) { body[k] = v[k]; lines.push({ label: labelOf(FIELDS, k) || k, from: '', to: short(v[k], 120), ltr: k === 'example_en' }); }
      });
      if (rel.length) { body.related = rel; lines.push({ label: 'مصطلحات قريبة', from: '', to: relShow(rel) }); }
      lines.push({ label: 'رابط المصطلح', from: '', to: slug, ltr: true });
      warns.push('يتجمّد رابط المصطلح عند أول نشر ولا يتغير بعده.');
      return { ok: true, body: body, lines: lines, warns: warns, errors: {}, goLabel: 'احفظ المصطلح',
               lead: 'سيُحفظ المصطلح «' + v.ar + '» مسودة، ' + (requireReview ? 'ولا يظهر على الموقع قبل أن يراجعه خبير وتنشره.' : 'ولا يظهر على الموقع حتى تنشره.') };
    }
    var o = orig || {};
    FIELDS.forEach(function (f) {
      var k = f[0], before = str(o[FIELD_ORIG[k]]);
      if (before !== v[k]) put(k, f[1], before, v[k], k === 'ar' || k === 'en' || k === 'fr' ? null : shortShow, f[4]);
    });
    if (str(o.area) !== area) put('area', 'المجال', o.area, area, areaValue);
    if (!frozen && slug !== o.slug) put('slug', 'رابط المصطلح', o.slug, slug, null, true);
    if (!sameList(o.related, rel)) put('related', 'مصطلحات قريبة', o.related, rel, relShow);
    if (!Object.keys(body).length) return { ok: false, error: 'لا يوجد تغيير', errors: {} };
    var touchesText = SUBSTANTIVE.some(function (k) { return k in body; });
    var drops = false;
    if (o.reviewed && touchesText) {
      warns.push('سيُلغى ختم المراجعة لأنك عدّلت النص' + (o.reviewerName ? ' (راجعه ' + o.reviewerName + ')' : '') + '.');
      if (o.published && requireReview) { drops = true; warns.push('وسيعود المصطلح مسودة وتختفي صفحته من الموقع عند التوليد التالي، حتى يراجعه خبير وتنشره من جديد.'); }
      else if (o.published && o.reviewsOn) warns.push('سيرجع المصطلح إلى «تحت التأكيد» ويبقى ظاهرًا.');
    }
    var lead = 'ستُحفظ التعديلات على «' + o.ar + '»' + (o.published && !drops ? '، وتتحدّث صفحته على الموقع خلال دقائق' : '') + ':';
    return { ok: true, body: body, lines: lines, warns: warns, errors: {}, lead: lead, goLabel: 'احفظ التعديلات', clearsReview: !!(o.reviewed && touchesText), drops: drops };
  }
  function termDone(kind, out, on) {
    if (kind === 'create') return 'أُضيف المصطلح «' + (out && out.item && out.item.ar ? out.item.ar : '') + '» مسودة';
    var t = 'حُفظت التعديلات';
    if (!out || !Array.isArray(out.changed) || !out.changed.length) return 'لا يوجد تغيير';
    if (out.review_cleared) t += '، وأُلغي ختم المراجعة';
    if (out.unpublished) t += '، وعاد المصطلح مسودة وستختفي صفحته من الموقع حتى يراجعه خبير وتنشره';
    else if (on !== false && out.review_cleared && out.item && out.item.status === 'under_review') t += '، وعاد المصطلح إلى «تحت التأكيد» ويبقى ظاهرًا';
    return t;
  }

  // ------------------------------------------------------------------ ٣ · ختم «راجعه»
  // form = {reviewer_name, reviewer_role, reviewer_name_public} ⇒ {ok, error, errors, body, lines, warns, lead, goLabel}
  function reviewCheck(form, row) {
    form = form || {};
    var name = person(form.reviewer_name), role = person(form.reviewer_role), errors = {}, shown = form.reviewer_name_public === true;
    var bad = function (t) { return URL_RE.test(t) || t.indexOf('@') > -1; };
    if (name.length < 2 || name.length > 120 || bad(name)) errors.reviewer_name = 'اكتب اسم المراجع (حرفان على الأقل)، بلا روابط ولا بريد';
    if (role.length < 2 || role.length > 80 || bad(role)) errors.reviewer_role = 'اكتب صفة المراجع، مثل: محامٍ أو أستاذ قانون';
    if (Object.keys(errors).length) return { ok: false, error: 'صحّح الخانات المعلَّمة', errors: errors };
    var on = row.reviewsOn !== false;
    var lines = [{ label: 'المصطلح', to: row.ar }, { label: 'المراجع', from: row.reviewed ? row.reviewerName + '، ' + row.reviewerRole : '', to: name + '، ' + role }];
    if (on) lines.push({ label: 'ظهور الاسم للناس', from: row.reviewed ? (row.namePublic ? 'يظهر' : 'لا يظهر') : '', to: shown ? 'يظهر' : 'لا يظهر' });
    if (on && row.published) lines.push({ label: 'الحالة', from: row.statusText, to: STATE_TEXT.confirmed });
    var warns = [];
    if (!on) warns.push('مراجعة داخلية: تُحفظ في الداشبورد ولا تظهر على الموقع.');
    else {
      warns.push(shown ? 'يظهر هذا الاسم وصفته للناس في صفحة المصطلح، فتأكد أن هذا الخبير راجع المصطلح فعلًا وأنه وافق على ظهور اسمه.'
                       : 'لن يظهر اسم المراجع للناس، وتقول الصفحة «راجعه متخصص» فقط.');
      if (!row.published) warns.push('المصطلح مسودة، فيبقى مسودة، ويظهر مؤكّدًا حين تنشره.');
      if (row.countries && !row.confirmed) warns.push('وتظهر ملاحظة الدول في الصفحة بعد الختم.');
    }
    return { ok: true, body: { reviewer_name: name, reviewer_role: role, reviewer_name_public: shown }, lines: lines, warns: warns, errors: {},
             lead: on ? (row.reviewed ? 'سيحلّ هذا المراجع محلّ المراجع السابق' : 'سيُختم المصطلح بأن خبيرًا راجعه') + (row.published ? '، وتتحدّث صفحته على الموقع خلال دقائق:' : ':')
                      : (row.reviewed ? 'سيحلّ هذا المراجع محلّ المراجع السابق في سجلّ الداشبورد:' : 'سيُسجَّل في الداشبورد أن خبيرًا راجع المصطلح:'),
             goLabel: row.reviewed ? 'جدّد ختم المراجعة' : 'ضع ختم المراجعة' };
  }
  function reviewDone(row) { return 'خُتم المصطلح «' + row.ar + '» بأن خبيرًا راجعه'; }
  function unreviewCheck(row, requireReview) {
    if (!row.reviewed) return { ok: false, error: 'المصطلح لم يُراجَع بعد' };
    var warns = [];
    if (row.published && requireReview) warns.push('ولأنه منشور وشرط المراجعة مفعّل سيعود مسودة، وتختفي صفحته من الموقع حتى يُراجَع وينشر من جديد.');
    else if (row.published && row.reviewsOn) warns.push('سيرجع المصطلح إلى «تحت التأكيد» ويبقى ظاهرًا.');
    var lines = [{ label: 'المراجعة', from: row.reviewLine.replace(/^راجعه: /, ''), to: 'بلا ختم' }];
    if (row.published && row.reviewsOn) lines.push({ label: 'الحالة', from: row.statusText, to: requireReview ? STATE_TEXT.draft : STATE_TEXT.under_review });
    return { ok: true, lead: 'سيُمسح ختم المراجعة عن «' + row.ar + '»:', goLabel: 'امسح الختم', warns: warns, unpublishes: !!(row.published && requireReview), lines: lines };
  }
  function unreviewDone(out, on) {
    if (out && out.unpublished) return 'مُسح الختم، وعاد المصطلح مسودة';
    return on !== false && out && out.item && out.item.status === 'under_review' ? 'مُسح الختم، وعاد المصطلح إلى «تحت التأكيد»' : 'مُسح ختم المراجعة';
  }

  // ------------------------------------------------------------------ ٤ · النشر والحذف
  function publishCheck(row, requireReview) {
    if (row.published) return { ok: false, error: 'المصطلح منشور بالفعل' };
    if (requireReview && !row.reviewed) return { ok: false, error: NEEDS_REVIEW_AR, needsReview: true };
    var warns = [];
    if (row.reviewsOn && !row.reviewed) warns.push('لم يراجعه خبير بعد، فستظهر صفحته بشارة «تحت التأكيد: نبحث عن متخصص يراجع هذا المصطلح» حتى يراجعه متخصص.');
    if (row.reviewsOn && !row.reviewed && row.countries) warns.push('وملاحظة الدول لا تظهر حتى يُؤكَّد المصطلح.');
    if (!row.frozen) warns.push('يتجمّد رابط المصطلح بعد أول نشر ولا يتغير.');
    return { ok: true, lead: 'ستظهر صفحة المصطلح على الموقع خلال دقائق.', goLabel: 'انشر المصطلح', warns: warns,
             lines: [{ label: 'المصطلح', to: row.ar }, { label: 'الحالة', from: row.statusText, to: row.reviewsOn ? (row.reviewed ? STATE_TEXT.confirmed : STATE_TEXT.under_review) : 'منشور' },
                     { label: 'الصفحة', to: SITE.replace('https://', '') + row.slug + '.html', ltr: true }] };
  }
  function unpublishCheck(row) {
    if (!row.published) return { ok: false, error: 'المصطلح غير منشور' };
    return { ok: true, lead: 'ستختفي صفحة المصطلح من الموقع خلال دقائق، ويعود «' + row.ar + '» مسودة.', goLabel: 'ألغِ النشر',
             lines: [{ label: 'الحالة', from: row.statusText, to: STATE_TEXT.draft }] };
  }
  function deleteCheck(row) {
    if (!row.canDelete) return { ok: false, error: 'يُحذف المصطلح قبل أول نشر فقط؛ بعده ألغِ نشره' };
    return { ok: true, lead: 'سيُحذف المصطلح «' + row.ar + '» نهائيًا ولا يمكن التراجع.', goLabel: 'احذف المصطلح', lines: [{ label: 'المصطلح', to: row.ar }] };
  }
  // سبب تعطيل زرّ النشر (أو '' لو متاح)
  function publishBlock(row, requireReview) {
    if (row.published) return '';
    return requireReview && !row.reviewed ? NEEDS_REVIEW_AR : '';
  }
  function publishDone(row) { return 'نُشر المصطلح «' + row.ar + '»' + (row.reviewed || !row.reviewsOn ? '' : ' تحت التأكيد') + '، وتظهر صفحته على الموقع خلال دقائق'; }
  function unpublishDone(row) { return 'أُلغي نشر «' + row.ar + '»، وتختفي صفحته من الموقع خلال دقائق'; }

  // ------------------------------------------------------------------ ٥ · شرط المراجعة (إعداد، الافتراضي مغلق)
  var RULE_ON = 'لا يُنشر أي مصطلح قبل أن يراجعه خبير، وتعديل نص مصطلح مؤكَّد يعيده مسودة حتى يُراجَع من جديد.';
  var RULE_OFF = 'يُنشر المصطلح فورًا بشارة «تحت التأكيد: نبحث عن متخصص يراجع هذا المصطلح» حتى يراجعه متخصص، وتعديل نص مصطلح مؤكَّد يعيده إلى «تحت التأكيد» ويبقى ظاهرًا.';
  function rulesView(v) {
    if (!v) return null;
    var pu = v.counts.publishedUnreviewed;
    return { on: v.requireReview, word: v.requireReview ? 'مطلوبة' : 'غير مطلوبة', text: v.requireReview ? RULE_ON : RULE_OFF, onText: RULE_ON, offText: RULE_OFF, publishedUnreviewed: pu,
             puText: pu ? U(pu, ['مصطلح واحد تحت التأكيد', 'مصطلحان تحت التأكيد', 'مصطلحات تحت التأكيد', 'مصطلحًا تحت التأكيد']) : '' };
  }
  function settingsCheck(want, cur, underReview) {
    if (typeof want !== 'boolean') return { ok: false, error: 'اختر الوضع' };
    if (want === cur) return { ok: false, error: 'هذا هو الوضع الحالي' };
    var warns = [];
    if (want && underReview > 0) warns.push(countWord(underReview, ['مصطلح واحد تحت التأكيد', 'مصطلحان تحت التأكيد', 'مصطلحات تحت التأكيد', 'مصطلحًا تحت التأكيد'], '') + ' لا يُنزَل تلقائيًا، ويبقى ظاهرًا حتى تراجعه أو تلغي نشره.');
    if (!want) warns.push('سيُنشر أي مصطلح بشارة «تحت التأكيد» حتى يراجعه متخصص، ولن يتوقف العمل على مراجعة مسبقة.');
    return { ok: true, body: { require_review: want }, warns: warns,
             lines: [{ label: 'مراجعة الخبير قبل النشر', from: cur ? 'مطلوبة' : 'غير مطلوبة', to: want ? 'مطلوبة' : 'غير مطلوبة' }],
             lead: want ? RULE_ON : RULE_OFF,
             goLabel: want ? 'اجعل المراجعة مطلوبة' : 'أغلق شرط المراجعة' };
  }
  function settingsDone(out) { return out && out.require_review ? 'صارت مراجعة الخبير مطلوبة قبل النشر' : 'أُغلق شرط مراجعة الخبير قبل النشر'; }

  // ------------------------------------------------------------------ ٦ · نقاش «الساحة»
  // resp = {topics:[{id,title,status}], url_prefix} ⇒ null لو المصدر فشل
  function topics(resp) {
    if (!resp || typeof resp !== 'object' || !Array.isArray(resp.topics)) return null;
    return { rows: resp.topics.filter(function (t) { return t && typeof t.id === 'string' && TOPIC_RE.test(t.id); }).map(function (t) { return { id: t.id, title: str(t.title) || 'نقاش بلا عنوان' }; }) };
  }
  function topicTitle(tv, id) { if (tv) for (var i = 0; i < tv.rows.length; i++) if (tv.rows[i].id === id) return tv.rows[i].title; return ''; }
  function attachCheck(id, tv, row) {
    id = str(id);
    if (!id) return { ok: false, error: 'اختر نقاشًا من القائمة' };
    if (row.topicId) return { ok: false, error: 'لهذا المصطلح نقاش مرتبط بالفعل، افصله أولًا' };
    var title = topicTitle(tv, id);
    if (!title) return { ok: false, error: 'هذا النقاش غير موجود في القائمة' };
    return { ok: true, body: { saha_topic_id: id }, lead: 'سيُربط المصطلح «' + row.ar + '» بنقاش «' + title + '»' + (row.published ? '، ويظهر في صفحته زرّ «ناقشه في الساحة» خلال دقائق:' : '، ويظهر زرّ «ناقشه في الساحة» في صفحته عند نشره:'),
             lines: [{ label: 'النقاش', to: title }], goLabel: 'اربط النقاش' };
  }
  function detachCheck(row, tv) {
    if (!row.topicId) return { ok: false, error: 'لا نقاش مرتبط بهذا المصطلح' };
    return { ok: true, lead: 'سيُفصل النقاش عن المصطلح «' + row.ar + '»، ويبقى النقاش نفسه في الساحة' + (row.published ? '، ويختفي زرّه من صفحة المصطلح خلال دقائق:' : ':'),
             lines: [{ label: 'النقاش', to: topicTitle(tv, row.topicId) || 'نقاش في الساحة' }], goLabel: 'افصل النقاش' };
  }

  // ------------------------------------------------------------------ ٦ب · نقاش جديد في «الساحة» (يطابق الخادم: العنوان والسؤال الافتراضيان)
  var TOPIC_TAIL = ': هل الترجمة والتعريف دقيقان؟';
  var TOPIC_QUESTION = 'هل الترجمة أو التعريف دقيق في نظامك القانوني؟ اكتب اعتراضك أو اقتراحك.';
  var TOPIC_TITLE_MAX = 200, TOPIC_QUESTION_MAX = 5000;
  var SAHA_NOTE = 'يظهر زرّ «ناقشه في الساحة» في صفحة المصطلح خلال دقائق، ويعمل للناس حين تُفتح الساحة على المنصة.';
  // المصطلح المنشور بلا نقاش
  function canOpenTopic(row) {
    if (!row.published) return { ok: false, error: 'انشر المصطلح أولًا ثم افتح نقاشه' };
    if (row.topicId) return { ok: false, error: 'لهذا المصطلح نقاش مرتبط بالفعل، افصله أولًا' };
    return { ok: true };
  }
  function topicDefaults(row) { return { title: str(row.ar) + ' (' + str(row.en) + ')' + TOPIC_TAIL, question: TOPIC_QUESTION }; }
  // form = {title, question} ⇒ {ok, errors, body}
  function topicFormCheck(form) {
    form = form || {};
    var t = plain(form.title), q = plain(form.question), errors = {};
    if (t.length < 3 || t.length > TOPIC_TITLE_MAX) errors.title = 'عنوان النقاش من ' + ar(3) + ' إلى ' + ar(TOPIC_TITLE_MAX) + ' حرف';
    if (!q || q.length > TOPIC_QUESTION_MAX) errors.question = 'اكتب سؤال النقاش (حتى ' + ar(TOPIC_QUESTION_MAX) + ' حرف)';
    if (Object.keys(errors).length) return { ok: false, error: 'صحّح الخانات المعلَّمة', errors: errors };
    return { ok: true, body: { title: t, question: q } };
  }
  // pv = ردّ معاينة الخادم {plan: create | link_existing, title, question, existing_id} ⇒ ورقة المراجعة
  function topicOpenCheck(row, pv) {
    var link = pv && pv.plan === 'link_existing';
    if (!pv || (pv.plan !== 'create' && !link)) return { ok: false, error: 'تعذّر قراءة معاينة النقاش، حاول مرة أخرى' };
    var lines = [{ label: 'العنوان', to: str(pv.title) }, { label: 'السؤال', to: short(pv.question, 160) },
                 { label: 'النتيجة', to: link ? 'يوجد نقاش بنفس العنوان، سيُربط به' : 'سيُفتح نقاش جديد في الساحة' }];
    return { ok: true, body: { title: str(pv.title), question: str(pv.question) }, lines: lines, warns: [SAHA_NOTE], goLabel: link ? 'اربط النقاش' : 'افتح النقاش',
             lead: link ? 'يوجد في الساحة نقاش بهذا العنوان، فلن يُفتح نقاش ثانٍ، وسيُربط المصطلح «' + row.ar + '» به:'
                        : 'سيُفتح في الساحة نقاش جديد للمصطلح «' + row.ar + '»، ويدعو الناس إلى مراجعة ترجمته وتعريفه:' };
  }
  function topicOpenDone(out, row) {
    return out && out.adopted ? 'رُبط المصطلح «' + row.ar + '» بنقاش موجود في الساحة' : 'فُتح للمصطلح «' + row.ar + '» نقاش في الساحة';
  }

  // الدفعة الكاملة: resp = ردّ /saha-topics/bulk/preview | /bulk/open (أو جسم الخطأ الجزئي) ⇒ null لو غير مفهوم
  var BULK_OUTCOME = { created: 'create', linked_existing: 'link', error: 'problem' };
  function bulkView(resp) {
    if (!resp || typeof resp !== 'object' || !Array.isArray(resp.results)) return null;
    var rows = resp.results.filter(function (r) { return r && typeof r === 'object' && BULK_OUTCOME[r.outcome]; }).map(function (r) {
      return { id: String(r.id), ar: str(r.ar) || 'مصطلح بلا عنوان', en: str(r.en), slug: str(r.slug), kind: BULK_OUTCOME[r.outcome], message: str(r.message), topicId: TOPIC_RE.test(str(r.topic_id)) ? str(r.topic_id) : '' };
    });
    var cnt = function (k) { return rows.filter(function (r) { return r.kind === k; }).length; };
    return { applied: resp.applied === true, stopped: resp.stopped === true, rows: rows, total: isNum(resp.total) ? resp.total : rows.length, batches: isNum(resp.batches) ? resp.batches : 0,
             remaining: isNum(resp.remaining) ? resp.remaining : 0, create: cnt('create'), link: cnt('link'), problem: cnt('problem') };
  }
  function bulkSummary(v) {
    if (!v) return '';
    var parts = [];
    if (v.create) parts.push(U(v.create, ['نقاش جديد واحد', 'نقاشان جديدان', 'نقاشات جديدة', 'نقاشًا جديدًا']));
    if (v.link) parts.push(U(v.link, ['ربط واحد بنقاش موجود', 'ربطان بنقاش موجود', 'ربط بنقاش موجود', 'ربطًا بنقاش موجود']));
    if (v.problem) parts.push(U(v.problem, ['مصطلح واحد بمشكلة', 'مصطلحان بمشكلة', 'مصطلحات بمشكلة', 'مصطلحًا بمشكلة']));
    return parts.join('، ');
  }
  function bulkCheck(v) {
    if (!v || !v.rows.length) return { ok: false, error: 'لا مصطلحات منشورة بلا نقاش' };
    var todo = v.create + v.link;
    if (!todo) return { ok: false, error: 'لا مصطلحات يمكن فتح نقاش لها الآن، راجع المشاكل المعروضة' };
    var lines = [{ label: 'مصطلحات منشورة بلا نقاش', to: ar(v.rows.length) }, { label: 'نقاش جديد يُفتح', to: ar(v.create) }, { label: 'تُربط بنقاش موجود', to: ar(v.link) }, { label: 'تُترك لمشكلة', to: ar(v.problem) }];
    var warns = [SAHA_NOTE];
    if (v.batches > 1) warns.push('يُنفَّذ على ' + ar(v.batches) + ' دفعات متتابعة، وإن توقفت إحداها يبقى ما سبقها ويمكنك إعادة المحاولة للباقي.');
    if (v.problem) warns.push('المصطلحات التي بها مشكلة تُترك كما هي، وتفتح نقاشها بنفسك من شاشة المصطلح.');
    return { ok: true, lead: 'سيُفتح الآن في الساحة نقاش لكل مصطلح منشور بلا نقاش، ويُربط به:', lines: lines, warns: warns, goLabel: 'افتح النقاشات' };
  }
  function bulkDone(v) {
    if (!v) return 'تمّت العملية';
    var t = bulkSummary(v);
    return 'اكتملت العملية' + (t ? ': ' + t : '');
  }
  // خطأ في وسط الدفعة ⇒ نص واحد يذكر ما تم قبله
  function bulkStopText(data, status) {
    var base = writeError(status, data), v = bulkView(data);
    var done = v ? v.create + v.link : 0;
    return base + (v && v.stopped ? (done ? ' رُبط ' + U(done, ['مصطلح واحد', 'مصطلحان', 'مصطلحات', 'مصطلحًا']) + ' قبل التوقف، وبقي ' + ar(v.remaining) + '. أعد المحاولة للباقي.' : ' لم يُربط شيء.') : '');
  }

  // ------------------------------------------------------------------ ٧ · الاستيراد (تجربة بلا حفظ ثم تأكيد)
  // ملف مرفوع ⇒ نفس فحص الخادم (قائمة كائنات ≤٥٠٠، أو {items: [...]}).
  function importFileCheck(obj) {
    var list = Array.isArray(obj) ? obj : (obj && typeof obj === 'object' && Array.isArray(obj.items) ? obj.items : null);
    if (!list) return { ok: false, error: 'الملف غير صالح: لا توجد فيه قائمة مصطلحات' };
    if (!list.length) return { ok: false, error: 'الملف فارغ: لا مصطلحات فيه' };
    if (list.length > IMPORT_MAX) return { ok: false, error: 'الملف أكبر من ' + ar(IMPORT_MAX) + ' مصطلح' };
    if (!list.every(function (i) { return i && typeof i === 'object' && !Array.isArray(i); })) return { ok: false, error: 'الملف غير صالح: بعض عناصره غير مفهومة' };
    return { ok: true, count: list.length, list: list };
  }
  function importBody(src, file) {
    var b = { source: src };
    if (src === 'upload' && file) b.payload = { items: file.list };
    return b;
  }
  function importCanPreview(src, file) {
    if (!labelOf(IMPORT_SOURCES, src)) return { ok: false, error: 'اختر مصدر الاستيراد' };
    if (src === 'upload' && !file) return { ok: false, error: 'اختر ملفًا من جهازك أولًا' };
    return { ok: true };
  }
  function importView(resp) {
    if (!resp || typeof resp !== 'object') return null;
    var n = function (k) { return isNum(resp[k]) ? resp[k] : 0; };
    var rows = [{ key: 'new', label: 'جديد يُضاف مسودة', n: n('new_count') }, { key: 'exists', label: 'موجود من قبل فيُترك كما هو', n: n('skip_existing') },
                { key: 'dup', label: 'مكرّر داخل الملف فيُترك', n: n('skip_duplicate_in_file') }, { key: 'bad', label: 'فيه خطأ فيُترك', n: n('invalid_count') }];
    var problems = (Array.isArray(resp.problems) ? resp.problems : []).filter(function (p) { return p && typeof p === 'object'; }).map(function (p) {
      return { row: isNum(p.row) ? ar(p.row) : '', slug: str(p.slug), text: problemText(p.problem) };
    });
    var sample = (Array.isArray(resp.sample) ? resp.sample : []).filter(function (s) { return s && typeof s === 'object'; }).map(function (s) {
      return { slug: str(s.slug), ar: str(s.ar), en: str(s.en), areaText: areaText(s.area) };
    });
    return { rows: rows, problems: problems, sample: sample, total: n('total'), changes: n('new_count'), imported: n('imported') };
  }
  function importDone(v) {
    if (!v) return 'تم الاستيراد';
    var k = v.imported || v.changes;
    return 'تم الاستيراد: ' + (k ? U(k, ['مصطلح جديد', 'مصطلحان جديدان', 'مصطلحات جديدة', 'مصطلحًا جديدًا']) + ' مسودات بلا ختم مراجعة' : 'بلا مصطلحات جديدة');
  }

  // ------------------------------------------------------------------ ٨ · «مراجعات القاموس» (ما يقدّمه المتخصصون من الموقع)
  // resp = ردّ GET /v2/content/glossary/reviews ⇒ null لو المصدر فشل
  function toReview(r) {
    var kind = labelOf(REVIEW_KINDS, str(r.kind)) ? str(r.kind) : 'glossary_term';
    var st = REVIEW_STATUS_TEXT[str(r.status)] ? str(r.status) : 'pending';
    var verdict = r.verdict === 'suggest' ? 'suggest' : 'confirm';
    var term = r.term && typeof r.term === 'object' && r.term.id != null ? toRow(r.term, true) : null;
    var spec = str(r.specialty_text) || str(r.specialty_label) || labelOf(AREAS, OTHER);
    return {
      id: String(r.id), kind: kind, kindText: labelOf(REVIEW_KINDS, kind), isTerm: kind === 'glossary_term', ref: str(r.ref), title: str(r.ref_title) || str(r.ref),
      name: str(r.name), email: str(r.email), specialtyText: spec, verdict: verdict, verdictText: VERDICT_TEXT[verdict], suggests: verdict === 'suggest', text: str(r.text),
      showName: r.show_name === true, showNameText: r.show_name === true ? 'وافق على ظهور اسمه' : 'لم يوافق على ظهور اسمه',
      status: st, statusText: REVIEW_STATUS_TEXT[st], pending: st === 'pending', createdOn: dayText(r.created_at), decidedOn: dayText(r.decided_at),
      note: str(r.admin_note), termChanged: r.term_changed === true, term: term, termId: term ? term.id : ''
    };
  }
  function reviews(resp) {
    if (!resp || typeof resp !== 'object' || !Array.isArray(resp.items)) return null;
    var rows = resp.items.filter(function (r) { return r && typeof r === 'object' && r.id != null && str(String(r.id)); }).map(toReview);
    var c = resp.counts && typeof resp.counts === 'object' ? resp.counts : null;
    var n = function (k, d) { return c && isNum(c[k]) ? c[k] : d; };
    var cnt = function (st) { return rows.filter(function (r) { return r.status === st; }).length; };
    return { rows: rows, counts: { pending: n('pending', cnt('pending')), approved: n('approved', cnt('approved')), rejected: n('rejected', cnt('rejected')), all: n('all', rows.length) } };
  }
  function filterReviews(rows, f) {
    f = f || {};
    return (rows || []).filter(function (r) { return (!f.status || f.status === 'all' || r.status === f.status) && (!f.kind || f.kind === 'all' || r.kind === f.kind); });
  }
  function reviewCountText(n) { return countWord(n, ['مراجعة واحدة', 'مراجعتان', 'مراجعات', 'مراجعةً'], 'لا مراجعات هنا'); }
  function reviewWho(rv) { return rv.name + '، ' + rv.specialtyText; }
  // المراجعة المقترحة بجانب نص المصطلح عند فتح المحرّر بعد «اعتمد» على اقتراح
  function suggestionView(rv) { return rv ? { name: rv.name, specialtyText: rv.specialtyText, text: rv.text, title: rv.title, termId: rv.termId } : null; }
  function approveLabel(rv) { return rv && !rv.isTerm ? 'تمّ' : 'اعتمد'; }
  function approveCheck(rv) {
    if (!rv || !rv.pending) return { ok: false, error: 'سبق البتّ في هذه المراجعة' };
    var base = [{ label: rv.kindText, to: rv.title }, { label: 'المراجع', to: reviewWho(rv) }, { label: 'رأيه', to: rv.verdictText }];
    if (rv.text) base.push({ label: rv.suggests ? 'اقتراحه' : 'ملاحظته', to: short(rv.text, 300) });
    if (!rv.isTerm) {
      return { ok: true, body: {}, goLabel: 'تمّ', lead: 'ستُعلَّم هذه المراجعة «تمّ» بلا أي ختم. العمل على ' + (rv.kind === 'course' ? 'الدورة' : 'المسار') + ' نفسه يتم من المنصة.',
               lines: base.concat([{ label: 'المراجعة', from: REVIEW_STATUS_TEXT.pending, to: 'تمّ' }]), warns: [] };
    }
    var t = rv.term;
    if (!t) return { ok: false, error: 'المصطلح لم يعد موجودًا' };
    var warns = [];
    if (rv.termChanged) warns.push('تغيّر نص المصطلح بعد وصول هذه المراجعة، فراجع النص الحالي قبل أن تعتمد.');
    if (rv.suggests) {
      return { ok: true, body: {}, goLabel: 'اعتمد وافتح المحرّر', lead: 'ستُعلَّم المراجعة معتمدة، ثم يفتح محرّر المصطلح والاقتراح بجانبه. لا يتغيّر المصطلح حتى تحفظ تعديلك، ويبقى «' + t.statusText + '».',
               lines: base.concat([{ label: 'المراجعة', from: REVIEW_STATUS_TEXT.pending, to: REVIEW_STATUS_TEXT.approved }]), warns: warns };
    }
    var lines = base.concat([
      { label: 'ختم المصطلح', from: t.reviewed ? t.reviewerName + '، ' + t.reviewerRole : 'بلا ختم', to: reviewWho(rv) },
      { label: 'ظهور الاسم للناس', from: t.reviewed ? (t.namePublic ? 'يظهر' : 'لا يظهر') : '', to: rv.showName ? 'يظهر' : 'لا يظهر' },
      { label: 'حالة المصطلح', from: t.statusText, to: t.published ? STATE_TEXT.confirmed : STATE_TEXT.draft }]);
    if (t.reviewed) warns.push('يحلّ هذا المراجع محلّ ' + t.reviewerName + '.');
    if (!rv.showName) warns.push('لن يظهر اسم المراجع للناس، وتقول الصفحة «راجعه متخصص» فقط.');
    if (!t.published) warns.push('المصطلح مسودة الآن، فيُختم ويبقى مسودة حتى تنشره.');
    else if (t.countries && !t.confirmed) warns.push('وتظهر ملاحظة الدول في الصفحة بعد الختم.');
    return { ok: true, body: {}, goLabel: 'اعتمد وضع الختم', lead: 'سيُختم المصطلح «' + t.ar + '» بأن متخصصًا راجعه' + (t.published ? '، وتتحدّث صفحته على الموقع خلال دقائق:' : ':'), lines: lines, warns: warns };
  }
  function approveDone(rv, out) {
    if (!rv.isTerm) return 'تمّت المراجعة';
    if (rv.suggests) return 'اعتُمد الاقتراح، وعدّل المصطلح من الشاشة المفتوحة';
    return out && out.term && out.term.status === 'confirmed' ? 'اعتُمدت المراجعة وصار المصطلح «' + rv.title + '» مؤكّدًا' : 'اعتُمدت المراجعة ووُضع الختم، ويبقى المصطلح مسودة حتى تنشره';
  }
  // form = {admin_note} اختيارية ⇒ جسم الرفض
  function rejectCheck(rv, form) {
    if (!rv || !rv.pending) return { ok: false, error: 'سبق البتّ في هذه المراجعة' };
    var note = plain((form || {}).admin_note);
    if (note.length > NOTE_MAX) return { ok: false, error: 'صحّح الخانات المعلَّمة', errors: { admin_note: 'الملاحظة حتى ' + ar(NOTE_MAX) + ' حرف' } };
    var lines = [{ label: rv.kindText, to: rv.title }, { label: 'المراجع', to: reviewWho(rv) }, { label: 'المراجعة', from: REVIEW_STATUS_TEXT.pending, to: REVIEW_STATUS_TEXT.rejected }];
    if (note) lines.push({ label: 'ملاحظتك الخاصة', to: note });
    return { ok: true, body: note ? { admin_note: note } : {}, lines: lines, warns: ['لا يصل إلى صاحب المراجعة أي رد من هنا.'], goLabel: 'ارفض المراجعة',
             lead: 'سترفض هذه المراجعة ولا يتغيّر ' + (rv.isTerm ? 'المصطلح' : (rv.kind === 'course' ? 'الدورة' : 'المسار')) + ':' };
  }
  function rejectDone() { return 'رُفضت المراجعة'; }

  L.v2sGlossary = {
    OTHER: OTHER, NA: NA, SITE: SITE, SAHA_APP: SAHA_APP, NEEDS_REVIEW_AR: NEEDS_REVIEW_AR, AREAS: AREAS, STATUS_CHIPS: STATUS_CHIPS, REVIEW_CHIPS: REVIEW_CHIPS,
    STATE_TEXT: STATE_TEXT, REVIEW_KINDS: REVIEW_KINDS, REVIEW_STATUS_CHIPS: REVIEW_STATUS_CHIPS, REVIEW_KIND_CHIPS: REVIEW_KIND_CHIPS, NOTE_MAX: NOTE_MAX,
    reviews: reviews, filterReviews: filterReviews, reviewCountText: reviewCountText, suggestionView: suggestionView, approveLabel: approveLabel, approveCheck: approveCheck,
    approveDone: approveDone, rejectCheck: rejectCheck, rejectDone: rejectDone,
    SUBSTANTIVE: SUBSTANTIVE, FIELDS: FIELDS, IMPORT_SOURCES: IMPORT_SOURCES, RELATED_MAX: RELATED_MAX, IMPORT_MAX: IMPORT_MAX, SLUG_RE: SLUG_RE,
    arDigits: arDigits, fixSep: fixSep, dayText: dayText, slugify: slugify, areaText: areaText, areaChips: areaChips, writeError: writeError, problemText: problemText,
    terms: terms, summary: summary, termCountText: termCountText, norm: norm, filterRows: filterRows, bySlug: bySlug, relatedView: relatedView, relatedOptions: relatedOptions,
    previewUrl: previewUrl, topicUrl: topicUrl,
    termForm: termForm, termCheck: termCheck, termDone: termDone, reviewCheck: reviewCheck, reviewDone: reviewDone, unreviewCheck: unreviewCheck, unreviewDone: unreviewDone,
    publishCheck: publishCheck, unpublishCheck: unpublishCheck, deleteCheck: deleteCheck, publishBlock: publishBlock, publishDone: publishDone, unpublishDone: unpublishDone,
    rulesView: rulesView, settingsCheck: settingsCheck, settingsDone: settingsDone,
    topics: topics, topicTitle: topicTitle, attachCheck: attachCheck, detachCheck: detachCheck,
    statusChips: statusChips, STATUS_CHIPS_OFF: STATUS_CHIPS_OFF, SAHA_NOTE: SAHA_NOTE, TOPIC_QUESTION: TOPIC_QUESTION, canOpenTopic: canOpenTopic, topicDefaults: topicDefaults, topicFormCheck: topicFormCheck,
    topicOpenCheck: topicOpenCheck, topicOpenDone: topicOpenDone, bulkView: bulkView, bulkSummary: bulkSummary, bulkCheck: bulkCheck, bulkDone: bulkDone, bulkStopText: bulkStopText,
    importFileCheck: importFileCheck, importBody: importBody, importCanPreview: importCanPreview, importView: importView, importDone: importDone
  };
  if (typeof module !== 'undefined' && module.exports) module.exports.v2sGlossary = L.v2sGlossary;
})(typeof window !== 'undefined' ? window : (typeof globalThis !== 'undefined' ? globalThis : this));
