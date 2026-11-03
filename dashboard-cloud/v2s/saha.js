/* ============================================================================
 * v2s/saha.js — الجزء الأول: المنطق النقي لمربّعات «الساحة» و«الديوان» في الداشبورد (لا DOM ولا شبكة ولا ساعة خفية؛ `now` يُمرَّر صراحةً).
 *   الساحة:  ١) الأخبار (مسودات تنتظر · منشورة) وتعديلها واعتمادها · ٢) الفرص (قوائم · مراجعة الطابور بالنوع · النموذج الكامل قبل ⇐ بعد)
 *            ٣) رابط دورة التحضير · ٤) استيراد الفرص (تجربة ثم تأكيد) · ٥) الآراء (إخفاء وإظهار) · ٦) التذكير (آخر تشغيل).
 *   الديوان: ٧) الأعمال (اعتماد · رفض بسبب · تمييز · إخفاء · قفل التعليقات) · ٨) التعليقات · ٩) التحديات (نموذج · لجنة · جوائز · فائزون) · ١٠) التقرير.
 * ⛔ المصدر الفاشل = null (والشاشة تكتب «غير متاح بعد»)، والرقم الغايب «لا رقم بعد» لا صفر مخترع. كل رقم ظاهر بأرقام هندية، و«·» لا تلاصق رقمًا (نستعمل «،»).
 * ⛔ نصوص ظاهرة: فصحى بسيطة محايدة للجنس، بلا مصطلحات تقنية، ولا عنوان يبدأ بـ«الذكاء». التحقق هنا يطابق الخادم (v2_saha_routes.py) والتحقق النهائي عنده وعند المنصة.
 * ========================================================================== */
(function (root) {
  'use strict';
  var L = root.V2L;
  if (!L || !L.util) return;
  var Un = L.util, ar = Un.ar, fmt = Un.fmt, U = Un.U;
  var DIG = '٠١٢٣٤٥٦٧٨٩';
  var MONTHS = ['يناير', 'فبراير', 'مارس', 'أبريل', 'مايو', 'يونيو', 'يوليو', 'أغسطس', 'سبتمبر', 'أكتوبر', 'نوفمبر', 'ديسمبر'];
  var OTHER = 'other';
  var SESSION_AR = 'انتهت الجلسة، سجّل الدخول من جديد ثم جرّب';
  var NA = 'غير متاح بعد';
  var NO_NUM = 'لا رقم بعد';

  function str(v) { return typeof v === 'string' ? v.trim() : ''; }
  function isNum(v) { return typeof v === 'number' && isFinite(v); }
  function arDigits(s) { return String(s == null ? '' : s).replace(/\d/g, function (d) { return DIG.charAt(+d); }); }
  function toLatin(s) { return String(s == null ? '' : s).replace(/[٠-٩]/g, function (d) { return String(DIG.indexOf(d)); }).replace(/[۰-۹]/g, function (d) { return String('۰۱۲۳۴۵۶۷۸۹'.indexOf(d)); }); }
  // «·» ما تلاصق رقمًا أبدًا: تتحول «،». (حارس أخير لأي نص جاء من خارج هذا الملف)
  function fixSep(s) {
    return String(s == null ? '' : s).replace(/([\d٠-٩])\s*·\s*/g, '$1، ').replace(/\s*·\s*([\d٠-٩])/g, '، $1');
  }
  function line(parts) { return fixSep(arDigits(parts.filter(function (p) { return p; }).join('، '))); }
  function ms(iso) { var t = typeof iso === 'number' ? iso : Date.parse(iso || ''); return isNaN(t) ? NaN : t; }
  function when(iso, now) { var t = ms(iso); return isNaN(t) ? '' : Un.agoText(t, now); }
  function labelOf(list, key) { for (var i = 0; i < list.length; i++) if (list[i][0] === key) return list[i][1]; return ''; }
  function short(s, n) { s = String(s == null ? '' : s).replace(/\s+/g, ' ').trim(); return s.length > n ? s.slice(0, n) + '…' : s; }
  function httpUrl(u) { u = str(u); return /^https?:\/\/\S+$/i.test(u) ? u : ''; }
  var HTTPS_RE = /^https:\/\/[^\s/$.?#]\S*$/i;
  var DATE_RE = /^\d{4}-\d{2}-\d{2}$/;
  // يوم «YYYY-MM-DD» (أو بادئة تاريخ ISO) ⇒ «٨ ديسمبر ٢٠٢٦» بلا إزاحة توقيت (اليوم المكتوب هو اليوم المعروض).
  function dayText(v) {
    var m = /^(\d{4})-(\d{2})-(\d{2})/.exec(str(v));
    if (!m) return '';
    var mo = +m[2];
    if (mo < 1 || mo > 12) return '';
    return ar(+m[3]) + ' ' + MONTHS[mo - 1] + ' ' + arDigits(m[1]);
  }
  // آخر لحظة من اليوم بتوقيت القاهرة: اليوم المجرَّد تقرؤه المنصة منتصف الليل بالتوقيت العالمي فيضيع آخر يوم من الإغلاق أو التمييز.
  // (+٠٢:٠٠ لا يقطع اليوم في مصر ولا الخليج، وأقصى ما يعطيه ساعتان زيادة)
  function dayEnd(d) { return d + 'T23:59:59+02:00'; }
  function dayInput(v) { var m = /^(\d{4}-\d{2}-\d{2})/.exec(str(v)); return m ? m[1] : ''; }
  function realDate(v) {
    if (!DATE_RE.test(v)) return false;
    var d = new Date(v + 'T00:00:00Z');
    return !isNaN(d.getTime()) && d.toISOString().slice(0, 10) === v;
  }
  function parseWhole(text) {
    var t = toLatin(text).replace(/[٬,\s]/g, '');
    if (t === '') return { kind: 'empty' };
    if (!/^\d{1,9}$/.test(t)) return { kind: 'bad' };
    return { kind: 'num', n: Number(t) };
  }

  // ------------------------------------------------------------------ جداول التسميات
  var OPP_KINDS = [['job', 'وظيفة'], ['grant', 'منحة'], ['fellowship', 'زمالة'], ['training', 'تدريب'], ['competition', 'مسابقة'], [OTHER, 'أخرى']];
  var KIND_CHIPS = [['all', 'الكل'], ['grants', 'منح'], ['job', 'وظائف'], ['training', 'تدريب'], ['competition', 'مسابقات'], [OTHER, 'أخرى']];
  var LANGS = [['en', 'الإنجليزية'], ['fr', 'الفرنسية'], ['ar', 'العربية'], [OTHER, 'أخرى']];
  var FUNDS = [['full', 'تمويل كامل'], ['partial', 'تمويل جزئي'], ['none', 'بلا تمويل'], ['varies', 'أخرى (يختلف)']];
  var NEWS_CATS = ['مسابقات وتعيينات', 'قوانين جديدة', 'أحكام', 'أخرى'];
  var COUNTRIES = [['EG', 'مصر'], ['SA', 'السعودية'], ['AE', 'الإمارات'], ['QA', 'قطر'], ['KW', 'الكويت'], ['JO', 'الأردن'], ['MA', 'المغرب'], ['TN', 'تونس'],
                   ['GB', 'المملكة المتحدة'], ['US', 'الولايات المتحدة'], ['CA', 'كندا'], ['DE', 'ألمانيا'], ['FR', 'فرنسا'], ['NL', 'هولندا'], ['CH', 'سويسرا'],
                   ['SE', 'السويد'], ['AU', 'أستراليا'], ['TR', 'تركيا'], ['online', 'عبر الإنترنت'], ['various', 'بلدان متعددة']];
  var REVIEW_TEXT = { pending: 'ينتظر المراجعة', published: 'منشورة', rejected: 'مرفوضة', draft: 'مسودة' };
  var OPP_STATUS_CHIPS = [['all', 'الكل'], ['pending', 'تنتظر المراجعة'], ['published', 'منشورة'], ['draft', 'مسودات'], ['rejected', 'مرفوضة']];
  var OP_CHIPS = [['pending', 'تنتظر القرار'], ['approved', 'ظاهرة'], ['rejected', 'مخفية'], ['all', 'الكل']];
  var NEWS_CHIPS = [['draft', 'مسودات'], ['published', 'منشورة']];
  var WORK_KINDS = [['film', 'فيلم'], ['poem', 'قصيدة'], ['story', 'قصة'], ['book', 'كتاب'], [OTHER, 'أخرى']];
  var WORK_CHIPS = [['pending_review', 'تنتظر القرار'], ['published', 'منشورة'], ['hidden', 'مخفية'], ['rejected', 'مرفوضة']];
  var WORK_STATUS_TEXT = { pending_review: 'تنتظر القرار', published: 'منشور', hidden: 'مخفي', rejected: 'مرفوض' };
  var COMMENT_CHIPS = [['visible', 'ظاهرة'], ['hidden', 'مخفية']];
  var CH_STATUS_TEXT = { draft: 'مسودة', open: 'مفتوح', closed: 'مغلق', results: 'أُعلنت النتائج' };
  var CH_CHIPS = [['all', 'الكل'], ['draft', 'مسودة'], ['open', 'مفتوح'], ['closed', 'مغلق'], ['results', 'أُعلنت النتائج']];
  var PRIZE_TYPES = [['certificate', 'شهادة'], ['course_seat', 'مقعد في دورة'], ['featured_week', 'أسبوع تمييز'], ['book', 'كتاب'], [OTHER, 'أخرى']];
  var PLACES = ['', 'الأول', 'الثاني', 'الثالث'];
  var DAYS_CHIPS = [[7, 'آخر ٧ أيام'], [30, 'آخر ٣٠ يومًا'], [90, 'آخر ٩٠ يومًا']];

  function kindText(k) { return labelOf(OPP_KINDS, str(k)) || (str(k) ? 'أخرى' : ''); }
  function langText(k) { return labelOf(LANGS, str(k)) || (str(k) ? 'أخرى' : ''); }
  function fundText(k) { return labelOf(FUNDS, str(k)) || (str(k) ? 'أخرى' : ''); }
  function countryText(c) {
    c = str(c);
    if (!c) return '';
    var hit = labelOf(COUNTRIES, c) || labelOf(COUNTRIES, c.toUpperCase());
    return hit || 'أخرى (' + c.toUpperCase() + ')';
  }
  function kindMatches(kind, chip) {
    if (!chip || chip === 'all') return true;
    if (chip === 'grants') return kind === 'grant' || kind === 'fellowship';
    if (chip === OTHER) return kind === OTHER || !labelOf(OPP_KINDS, kind);
    return kind === chip;
  }

  // ------------------------------------------------------------------ أخطاء الكتابة (نص المنصة العربي يعدّي بنفس الكود)
  function writeError(status, data) {
    var msg = data && typeof data.error === 'string' ? data.error : '';
    if (data && data.no_reply) return msg;
    if (status === 401) return SESSION_AR;
    // نص المنصة العربي يعدّي كما هو؛ أما الإنجليزي (بعض رسائل الجسر) فيُستبدل بنص عربي حسب الرمز
    if (msg && /[\u0600-\u06FF]/.test(msg) && (status === 400 || status === 404 || status === 409 || status === 422)) return arDigits(msg);
    if (status === 404) return 'لم يعد هذا العنصر موجودًا على المنصة';
    if (status === 409) return 'تغيّرت حالة هذا العنصر على المنصة، حدّث الصفحة وحاول مرة أخرى';
    if (status === 400 || status === 422) return 'المنصة لم تقبل هذه البيانات، راجعها وحاول مرة أخرى';
    return 'تعذّر تنفيذ العملية، حاول مرة أخرى';
  }
  function countWord(n, forms, none) { return n ? U(n, forms) : none; }
  function items(resp) { return resp && Array.isArray(resp.items) ? resp.items.filter(function (r) { return r && typeof r === 'object' && str(String(r.id == null ? '' : r.id)); }) : null; }

  // ------------------------------------------------------------------ ١ · الأخبار
  function news(resp, now) {
    var list = items(resp);
    if (!list) return null;
    var rows = list.map(function (r) {
      var rp = r.related_product && typeof r.related_product === 'object' ? r.related_product : null;
      return { id: String(r.id), title: str(r.title) || 'خبر بلا عنوان', summary: str(r.summary), body: short(r.body, 700), source: str(r.source_name), sourceUrl: httpUrl(r.source_url),
               country: str(r.country), category: str(r.category) || 'أخرى', featured: r.featured === true, cover: httpUrl(r.cover_url), published: r.status === 'published',
               statusText: r.status === 'published' ? 'منشور' : 'مسودة', when: when(r.published_at || r.created_at, now), ts: ms(r.created_at), product: rp ? str(rp.label) : '',
               hasTopic: !!str(r.topic_id), extra: Array.isArray(r.extra_sources) ? r.extra_sources.length : 0 };
    });
    var n = rows.length;
    return { rows: rows, total: isNum(resp.total) ? resp.total : n,
             countText: n ? U(n, ['خبر واحد', 'خبران', 'أخبار', 'خبرًا']) : 'لا أخبار هنا' };
  }
  function newsForm(row) {
    return { title: row.title, summary: row.summary, category: NEWS_CATS.indexOf(row.category) > -1 ? row.category : 'أخرى', featured: !!row.featured, cover_url: row.cover };
  }
  // intent: 'approve' (نشر) | 'unpublish' (إلغاء النشر) | 'edit'. ⇒ {ok, error, errors, body, lines, lead}
  function newsCheck(form, row, intent) {
    form = form || {};
    var errors = {}, body = {}, lines = [], b = newsForm(row);
    var title = str(form.title), summary = str(form.summary), cover = str(form.cover_url);
    if (!title || title.length > 300) errors.title = 'العنوان من ١ إلى ٣٠٠ حرف';
    if (summary.length > 2000) errors.summary = 'الملخص حتى ٢٠٠٠ حرف';
    if (NEWS_CATS.indexOf(form.category) < 0) errors.category = 'اختر تصنيفًا، أو «أخرى»';
    if (cover && (cover.length > 2000 || !HTTPS_RE.test(cover))) errors.cover_url = 'يجب أن يبدأ الرابط بـ https';
    if (Object.keys(errors).length) return { ok: false, error: 'صحّح الخانات المعلَّمة', errors: errors };
    function ch(key, label, before, after, show) {
      if (before === after) return;
      body[key] = after;
      lines.push({ label: label, from: show ? show(before) : (before || 'فارغ'), to: show ? show(after) : (after || 'فارغ') });
    }
    var yn = function (v) { return v ? 'نعم' : 'لا'; };
    if (intent === 'approve') { body.status = 'published'; lines.push({ label: 'الحالة', from: 'مسودة', to: 'منشور' }); }
    if (intent === 'unpublish') { body.status = 'draft'; lines.push({ label: 'الحالة', from: 'منشور', to: 'مسودة' }); }
    ch('title', 'العنوان', b.title, title);
    ch('summary', 'الملخص', b.summary, summary, function (v) { return v ? short(v, 120) : 'فارغ'; });
    ch('category', 'التصنيف', b.category, form.category);
    ch('featured', 'التمييز', b.featured, !!form.featured, yn);
    ch('cover_url', 'رابط الغلاف', b.cover_url, cover);
    if (!Object.keys(body).length) return { ok: false, error: 'لا يوجد تغيير', errors: {} };
    var lead = intent === 'approve' ? 'سيُنشر الخبر «' + row.title + '» في الساحة.' : intent === 'unpublish' ? 'سيُسحب الخبر «' + row.title + '» من الساحة ويعود مسودة.' : 'ستُحفظ التعديلات على الخبر «' + row.title + '».';
    return { ok: true, body: body, lines: lines, lead: lead, errors: {} };
  }
  function newsRunCheck(form) {
    form = form || {};
    var n = str(form.limit), body = {}, text = 'كما تحدده المنصة';
    if (n) {
      var p = parseWhole(n);
      if (p.kind !== 'num' || p.n < 1 || p.n > 8) return { ok: false, error: 'عدد الأخبار لكل بلد من ١ إلى ٨' };
      body.per_country_limit = p.n; text = ar(p.n);
    }
    return { ok: true, body: body, lines: [{ label: 'عدد الأخبار لكل بلد', to: text }] };
  }
  function newsRunDone(res) {
    var total = res && isNum(res.total_created) ? res.total_created : 0;
    if (!total) return 'اكتمل الجلب، ولم تُضَف مسودات جديدة';
    return 'أُضيفت ' + U(total, ['مسودة واحدة', 'مسودتان', 'مسودات', 'مسودة']) + ' تنتظر مراجعتك';
  }

  // ------------------------------------------------------------------ ٢ · الفرص
  function opps(resp, now) {
    var list = items(resp);
    if (!list) return null;
    var rows = list.map(function (r) {
      var kind = str(r.kind) || 'job', review = str(r.review_status) || 'draft', dl = str(r.deadline), days = isNum(r.days_left) ? r.days_left : null;
      var dtext = dl ? dayText(dl) : str(r.deadline_text);
      var left = days == null || !dl ? '' : (days > 0 ? 'بعد ' + U(days, ['يوم', 'يومين', 'أيام', 'يومًا']) : (days === 0 ? 'اليوم' : 'انتهى الموعد'));
      return { id: String(r.id), title: str(r.title) || 'فرصة بلا عنوان', titleEn: str(r.title_en), kind: kind, kindText: kindText(kind) || 'أخرى', provider: str(r.provider) || str(r.employer),
               employer: str(r.employer), place: str(r.place), country: str(r.country), countryText: countryText(r.country), language: str(r.language), funding: str(r.funding),
               fundText: fundText(r.funding), langText: langText(r.language), deadline: dl, deadlineText: line([dtext, left]), expired: r.expired === true || (days != null && days < 0 && !!dl),
               review: review, reviewText: REVIEW_TEXT[review] || 'حالة غير معروفة', pending: review === 'pending', featured: r.featured === true, image: httpUrl(r.image),
               officialUrl: httpUrl(r.official_url), sourceUrl: httpUrl(r.source_url), eligibility: Array.isArray(r.eligibility_ar) ? r.eligibility_ar.filter(function (x) { return typeof x === 'string' && x.trim(); }) : [],
               covers: str(r.covers_ar), submittedBy: str(r.submitted_by), rejectReason: str(r.reject_reason), sourceName: str(r.source_name), sourceLabel: str(r.source_label),
               verifiedAt: dayInput(r.verified_at), employmentType: str(r.employment_type), specialty: str(r.specialty), body: str(r.body), logoInitial: str(r.logo_initial),
               deadlineIn: dayInput(dl), deadlineTextRaw: str(r.deadline_text), when: when(r.created_at, now), isJob: kind === 'job' };
    });
    var n = rows.length;
    return { rows: rows, total: isNum(resp.total) ? resp.total : n, pending: rows.filter(function (r) { return r.pending; }).length };
  }
  function oppFilter(rows, chip) { return (rows || []).filter(function (r) { return kindMatches(r.kind, chip); }); }
  function oppCountText(n) { return n ? U(n, ['فرصة واحدة', 'فرصتان', 'فرص', 'فرصة']) : 'لا فرص هنا'; }
  function pendingText(n) { return n ? U(n, ['إعلان واحد ينتظر', 'إعلانان ينتظران', 'إعلانات تنتظر', 'إعلانًا ينتظر']) : 'لا إعلانات تنتظر'; }

  var OPP_TEXT = [['title', 'العنوان', 200, 3], ['title_en', 'العنوان بالإنجليزية', 200, 0], ['provider', 'الجهة المنظِّمة', 200, 0], ['employer', 'جهة العمل', 200, 0], ['place', 'المكان', 200, 0],
                  ['employment_type', 'نوع الدوام', 40, 0], ['specialty', 'التخصص', 80, 0], ['covers_ar', 'ما تغطيه', 300, 0], ['deadline_text', 'نص الموعد', 80, 0],
                  ['source_name', 'اسم المصدر', 80, 0], ['source_label', 'تسمية المصدر', 40, 0], ['body', 'الوصف', 5000, 0], ['logo_initial', 'حرف الشعار', 2, 0]];
  var OPP_URL = [['official_url', 'الرابط الرسمي'], ['source_url', 'رابط المصدر'], ['image', 'رابط الصورة']];
  var OPP_DATE = [['deadline', 'آخر موعد'], ['verified_at', 'تاريخ التحقق']];
  var OPP_LABEL = { kind: 'النوع', publish: 'النشر', country: 'البلد', language: 'اللغة', funding: 'التمويل', eligibility_ar: 'الشروط', featured: 'التمييز', expires_in_days: 'مدة الإعلان' };
  OPP_TEXT.concat(OPP_URL, OPP_DATE).forEach(function (f) { OPP_LABEL[f[0]] = f[1]; });

  function normCountry(c) { c = str(c); return /^(online|various)$/i.test(c) ? c.toLowerCase() : c.toUpperCase(); }
  function countryField(code) {
    code = str(code);
    if (!code) return { country: '', other: '' };
    var lower = /^(online|various)$/i.test(code) ? code.toLowerCase() : code.toUpperCase();
    return labelOf(COUNTRIES, lower) ? { country: lower, other: '' } : { country: OTHER, other: code.toUpperCase() };
  }
  // صف ⇒ نموذج (نصوص كلها). null ⇒ نموذج فارغ للإضافة.
  function oppForm(row) {
    var r = row || {}, c = countryField(r.country);
    return { kind: r.kind ? (labelOf(OPP_KINDS, r.kind) ? r.kind : OTHER) : '', publish: '', title: r.title && row ? r.title : '', title_en: r.titleEn || '', provider: r.provider || '', employer: r.employer || '',
             place: r.place || '', country: c.country, country_other: c.other, language: r.language ? (labelOf(LANGS, r.language) ? r.language : OTHER) : '',
             funding: r.funding ? (labelOf(FUNDS, r.funding) ? r.funding : 'varies') : '', eligibility: (r.eligibility || []).join('\n'), covers_ar: r.covers || '',
             deadline: r.deadlineIn || '', deadline_text: r.deadlineTextRaw || '', official_url: r.officialUrl || '', source_url: r.sourceUrl || '', source_name: r.sourceName || '',
             source_label: r.sourceLabel || '', image: r.image || '', featured: !!r.featured, verified_at: r.verifiedAt || '', employment_type: r.employmentType || '',
             specialty: r.specialty || '', body: r.body || '', logo_initial: r.logoInitial || '', expires_in_days: '' };
  }
  function eligLines(text) { return String(text == null ? '' : text).split(/\r?\n/).map(function (s) { return s.trim(); }).filter(Boolean); }
  function oppValue(key, v) {
    if (key === 'kind') return kindText(v) || 'فارغ';
    if (key === 'language') return langText(v) || 'غير محدد';
    if (key === 'funding') return fundText(v) || 'غير محدد';
    if (key === 'country') return countryText(v) || 'غير محدد';
    if (key === 'featured') return v ? 'نعم' : 'لا';
    if (key === 'publish') return v ? 'منشورة' : 'مسودة';
    if (key === 'eligibility_ar') return v && v.length ? v.join('، ') : 'فارغ';
    if (key === 'deadline' || key === 'verified_at') return v ? dayText(v) : 'فارغ';
    if (key === 'expires_in_days') return v ? U(v, ['يوم واحد', 'يومان', 'أيام', 'يومًا']) : 'فارغ';
    return v ? short(v, 120) : 'فارغ';
  }
  // mode: 'create' | 'edit'. orig: الصف عند التعديل. ⇒ {ok, error, errors, body, lines, lead}
  function oppCheck(form, mode, orig) {
    form = form || {};
    var errors = {}, create = mode === 'create', v = {};
    var base = create ? oppForm(null) : oppForm(orig);
    if (create) {
      if (!labelOf(OPP_KINDS, form.kind)) errors.kind = 'اختر نوع الفرصة، أو «أخرى»';
      if (form.publish !== 'published' && form.publish !== 'draft') errors.publish = 'اختر: نشر الآن أو حفظ مسودة';
    } else if (form.kind && !labelOf(OPP_KINDS, form.kind)) errors.kind = 'نوع غير معروف';
    OPP_TEXT.forEach(function (f) {
      var t = str(form[f[0]]);
      if (t.length > f[2] || t.length < f[3] && (create || t !== str(base[f[0]]) || f[0] === 'title')) errors[f[0]] = f[3] ? f[1] + ' من ' + ar(f[3]) + ' إلى ' + ar(f[2]) + ' حرف' : f[1] + ' حتى ' + ar(f[2]) + ' حرف';
      v[f[0]] = t;
    });
    OPP_URL.forEach(function (f) {
      var t = str(form[f[0]]);
      if (t && (t.length > 2000 || !HTTPS_RE.test(t))) errors[f[0]] = 'يجب أن يبدأ ' + f[1] + ' بـ https';
      // المنصة ترفض مسح الرابط الرسمي أو رابط المصدر بعد حفظه (الصورة وحدها تُمسح)
      else if (!create && !t && f[0] !== 'image' && str(base[f[0]])) errors[f[0]] = f[1] + ' مطلوب، عدّله ولا تمسحه';
      v[f[0]] = t;
    });
    OPP_DATE.forEach(function (f) {
      var t = str(form[f[0]]);
      if (t && !realDate(t)) errors[f[0]] = f[1] + ': تاريخ غير صالح';
      v[f[0]] = t;
    });
    var c = form.country === OTHER ? str(form.country_other) : str(form.country);
    if (form.country === OTHER && !c) errors.country = 'اكتب رمز البلد من حرفين، أو اختر من القائمة';
    else if (c && !/^(?:[A-Za-z]{2}|online|various)$/.test(c)) errors.country = 'رمز البلد حرفان فقط، مثل EG';
    v.country = /^(?:online|various)$/.test(c) ? c : c.toUpperCase();
    var lang = str(form.language), fund = str(form.funding);
    if (lang && !labelOf(LANGS, lang)) errors.language = 'اللغة غير معروفة';
    if (fund && !labelOf(FUNDS, fund)) errors.funding = 'التمويل غير معروف';
    var elig = eligLines(form.eligibility);
    if (elig.length > 8) errors.eligibility = 'الشروط حتى ٨ أسطر';
    else if (elig.some(function (x) { return x.length > 160; })) errors.eligibility = 'السطر الواحد حتى ١٦٠ حرفًا';
    var exp = null;
    if (create && str(form.expires_in_days)) {
      var p = parseWhole(form.expires_in_days);
      if (p.kind !== 'num' || p.n < 1 || p.n > 365) errors.expires_in_days = 'مدة الإعلان من ١ إلى ٣٦٥ يومًا';
      else exp = p.n;
    }
    if (create && !(v.official_url || v.source_url) && !errors.official_url && !errors.source_url) errors.official_url = 'الرابط الرسمي مطلوب';
    if (Object.keys(errors).length) return { ok: false, error: 'صحّح الخانات المعلَّمة', errors: errors };

    var body = {}, lines = [];
    function put(key, before, after) {
      var same = JSON.stringify(before) === JSON.stringify(after);
      if (!create && same) return;
      if (create && (after === '' || after === false || (Array.isArray(after) && !after.length))) return;
      body[key] = after;
      lines.push({ label: OPP_LABEL[key], from: create ? '' : oppValue(key, before), to: oppValue(key, after) });
    }
    if (create) {
      body.kind = form.kind; body.publish = form.publish === 'published';
      lines.push({ label: OPP_LABEL.kind, from: '', to: oppValue('kind', body.kind) }, { label: OPP_LABEL.publish, from: '', to: oppValue('publish', body.publish) });
    }
    else if (form.kind) put('kind', base.kind, form.kind);
    OPP_TEXT.forEach(function (f) { put(f[0], str(base[f[0]]), v[f[0]]); });
    OPP_URL.forEach(function (f) { put(f[0], str(base[f[0]]), v[f[0]]); });
    OPP_DATE.forEach(function (f) { put(f[0], str(base[f[0]]), v[f[0]]); });
    put('country', create ? '' : normCountry(orig && orig.country), v.country);
    put('language', str(base.language), lang);
    put('funding', str(base.funding), fund);
    put('eligibility_ar', eligLines(base.eligibility), elig);
    put('featured', !!base.featured, !!form.featured);
    if (create && exp) { body.expires_in_days = exp; lines.push({ label: OPP_LABEL.expires_in_days, from: '', to: oppValue('expires_in_days', exp) }); }
    if (!create && (form.publish === 'published' || form.publish === 'draft')) {
      var was = orig.review === 'published';
      if ((form.publish === 'published') !== was) { body.publish = form.publish === 'published'; lines.push({ label: OPP_LABEL.publish, from: orig.reviewText, to: body.publish ? 'منشورة' : 'مسودة' }); }
    }
    if (!create && !Object.keys(body).length) return { ok: false, error: 'لا يوجد تغيير', errors: {} };
    var name = create ? v.title : (orig.title || v.title);
    var lead = create ? (body.publish ? 'ستُنشر «' + name + '» في الساحة فور التأكيد.' : 'ستُحفظ «' + name + '» مسودة، ولا تظهر للناس حتى تنشرها.') : 'ستُحفظ التعديلات على «' + name + '»:';
    return { ok: true, body: body, lines: lines, lead: lead, errors: {} };
  }
  // قرار الطابور ⇒ {ok, error, body, lead, goLabel}
  function oppDecision(decision, reason, row) {
    if (decision === 'approve') return { ok: true, body: { decision: 'approve' }, lead: 'ستظهر «' + row.title + '» في الساحة للجميع فور التأكيد.', goLabel: 'اعتمد ونشر' };
    var r = str(reason);
    if (r.length < 3) return { ok: false, error: 'اكتب سبب الرفض (٣ أحرف على الأقل)' };
    if (r.length > 140) return { ok: false, error: 'سبب الرفض حتى ١٤٠ حرفًا' };
    return { ok: true, body: { decision: 'reject', reason: r }, lead: 'سيُرفض الإعلان «' + row.title + '» ويُحفظ سبب الرفض معه:', goLabel: 'ارفض الإعلان', lines: [{ label: 'السبب', to: r }] };
  }
  function oppDone(kind, res) {
    var t = res && res.title ? ' «' + res.title + '»' : '';
    return ({ create: 'تمت إضافة الفرصة', edit: 'حُفظت التعديلات', approve: 'اعتُمد الإعلان ونُشر', reject: 'رُفض الإعلان', remove: 'حُذفت الفرصة' }[kind] || 'تم') + (kind === 'create' ? t : '');
  }

  // ------------------------------------------------------------------ ٣ · رابط دورة التحضير
  function prepView(resp) {
    if (!resp || typeof resp !== 'object') return null;
    return { url: httpUrl(resp.prep_course_url) };
  }
  function prepCheck(text, current, clear) {
    var cur = str(current);
    if (clear) {
      if (!cur) return { ok: false, error: 'لا يوجد رابط محفوظ لتمسحه' };
      return { ok: true, url: '', lines: [{ label: 'رابط دورة التحضير', from: cur, to: 'بلا رابط' }], lead: 'سيُمسح رابط دورة التحضير، ولا يظهر زرّها للناس.' };
    }
    var t = str(text);
    if (!t) return { ok: false, error: 'اكتب الرابط، أو اختر «امسح الرابط»' };
    if (t.length > 2000 || !HTTPS_RE.test(t)) return { ok: false, error: 'يجب أن يبدأ الرابط بـ https' };
    if (t === cur) return { ok: false, error: 'هذا هو الرابط المحفوظ الآن' };
    return { ok: true, url: t, lines: [{ label: 'رابط دورة التحضير', from: cur || 'بلا رابط', to: t }], lead: 'سيُحفظ هذا الرابط لدورة التحضير في الساحة:' };
  }

  // ------------------------------------------------------------------ ٤ · استيراد الفرص
  var SEED_ROWS = [['created', 'فرص جديدة تُضاف'], ['filled', 'فرص يُكمَّل ما ينقصها'], ['skipped_unverified', 'فرص تُتخطى لعدم التحقق منها'], ['unchanged', 'فرص بلا تغيير']];
  function seedView(resp) {
    if (!resp || typeof resp !== 'object') return null;
    var rows = SEED_ROWS.map(function (r) { return { key: r[0], label: r[1], n: isNum(resp[r[0]]) ? resp[r[0]] : 0 }; });
    var warns = Array.isArray(resp.warnings) ? resp.warnings.filter(function (w) { return typeof w === 'string' && w; }).map(function (w) { return arDigits(w); }) : [];
    return { rows: rows, warnings: warns, dry: resp.dry_run === true, changes: rows[0].n + rows[1].n };
  }
  function seedDone(v) {
    if (!v) return 'تم الاستيراد';
    var n = v.rows[0].n, f = v.rows[1].n;
    return 'تم الاستيراد: ' + (n ? U(n, ['فرصة جديدة', 'فرصتان جديدتان', 'فرص جديدة', 'فرصة جديدة']) : 'بلا فرص جديدة') + (f ? '، وأُكمل ما ينقص ' + U(f, ['فرصة', 'فرصتين', 'فرص', 'فرصة']) : '');
  }
  // ملف مرفوع ⇒ نفس فحص الخادم (items قائمة قواميس ≤٥٠٠).
  function seedCheck(obj) {
    if (!obj || typeof obj !== 'object' || Array.isArray(obj) || !Array.isArray(obj.items)) return { ok: false, error: 'الملف غير صالح: لا توجد فيه قائمة فرص' };
    if (obj.items.length > 500) return { ok: false, error: 'الملف أكبر من ٥٠٠ فرصة' };
    if (!obj.items.every(function (i) { return i && typeof i === 'object' && !Array.isArray(i); })) return { ok: false, error: 'الملف غير صالح: بعض عناصره غير مفهومة' };
    return { ok: true, count: obj.items.length };
  }

  // ------------------------------------------------------------------ ٥ · الآراء
  var OP_STATUS_TEXT = { pending: 'تنتظر القرار', approved: 'ظاهر', rejected: 'مخفي' };
  function opinions(resp, now) {
    var list = items(resp);
    if (!list) return null;
    var rows = list.map(function (r) {
      var st = str(r.status) || 'pending';
      return { id: String(r.id), body: str(r.body), author: str(r.author_email), expert: r.is_expert === true, authorText: r.is_expert === true ? 'خبير' : 'عضو', topic: str(r.topic_title), topicId: str(r.topic_id),
               status: st, statusText: OP_STATUS_TEXT[st] || 'حالة غير معروفة', canHide: st !== 'rejected', canShow: st !== 'approved', showLabel: st === 'rejected' ? 'أعد إظهاره' : 'أظهره',
               when: when(r.created_at, now), edited: r.edited === true };
    });
    var n = rows.length;
    return { rows: rows, total: isNum(resp.total) ? resp.total : n, countText: n ? U(n, ['رأي واحد', 'رأيان', 'آراء', 'رأيًا']) : 'لا آراء هنا' };
  }
  function topics(resp) {
    var list = items(resp);
    if (!list) return null;
    return { rows: list.map(function (r) { return { id: String(r.id), title: str(r.title) || 'نقاش بلا عنوان' }; }) };
  }
  function opinionAction(kind, row) {
    if (kind === 'hide') return { lead: 'سيُخفى هذا الرأي عن القرّاء ولا يُحتسب في عدّاد النقاش:', goLabel: 'أخفِ الرأي', done: 'أُخفي الرأي' };
    return { lead: 'سيظهر هذا الرأي للقرّاء، وتُبلَّغ المنصة باعتماده:', goLabel: 'أظهر الرأي', done: 'ظهر الرأي للقرّاء' };
  }

  // ------------------------------------------------------------------ ٦ · التذكير
  var REM_ROWS = [['opportunities', 'فرص اقترب موعدها'], ['sent', 'تذكيرات أُرسلت'], ['skipped_already', 'سبق تذكيرهم'], ['skipped_toggle_off', 'أوقفوا التذكير'], ['errors', 'تعذّر إرسالها']];
  // resp = {last, enabled, locked} من GET saha/reminders. ⇒ null لو المصدر فشل.
  function reminders(resp, now) {
    if (!resp || typeof resp !== 'object' || !('last' in resp)) return null;
    var last = resp.last && typeof resp.last === 'object' ? resp.last : null;
    var out = { kind: 'never', headline: 'لم يُشغَّل بعد', detail: 'لم يحدث أي تشغيل بعد. يمكنك تشغيله الآن بيدك، وسيظهر هنا ما حدث في آخر تشغيل.', rows: [], when: '', locked: false, sent: null };
    if (!last) return out;
    var at = when(last.at, now), how = last.trigger === 'cron' ? 'تلقائي' : (last.trigger === 'manual' ? 'يدوي' : '');
    out.when = line([at, how ? 'تشغيل ' + how : '']);
    if (last.ok !== true) { out.kind = 'failed'; out.headline = 'تعذّر آخر تشغيل'; out.detail = last.no_reply === true ? 'لم يصل رد من المنصة، ولا نعرف إن كان التشغيل تمّ. جرّب «شغّل الآن» أو انتظر التشغيل التالي.' : 'لم يكتمل آخر تشغيل لأن المنصة رفضته. جرّب «شغّل الآن» بعد قليل، وإن تكرر ذلك فأخبر فريق التطوير.'; return out; }
    if (resp.locked === true || last.enabled === false) {
      out.kind = 'locked'; out.locked = true; out.headline = 'التذكير مقفول'; out.detail = 'المنصة لا ترسل تذكيرات الآن، فلا يحدث شيء عند التشغيل. يُفتح من إعدادات المنصة.'; return out;
    }
    out.kind = 'ok'; out.headline = 'التذكير مفتوح'; out.detail = 'هذه أرقام آخر تشغيل.';
    out.sent = isNum(last.sent) ? last.sent : 0;
    out.rows = REM_ROWS.map(function (r) { return { label: r[1], n: isNum(last[r[0]]) ? last[r[0]] : 0 }; });
    return out;
  }
  function reminderTile(v) {
    if (!v) return { n: '—', sub: NA, off: true };
    if (v.kind === 'locked') return { n: 'مقفول', sub: 'التذكير مقفول', off: true, word: true };
    if (v.kind === 'never') return { n: '—', sub: 'لم يُشغَّل بعد', off: true };
    if (v.kind === 'failed') return { n: '—', sub: 'تعذّر آخر تشغيل', off: true, hot: true };
    return { n: ar(v.sent), sub: v.sent ? 'تذكير أُرسل في آخر تشغيل' : 'لم يُرسَل شيء في آخر تشغيل', hot: false };
  }
  function reminderRunDone(res) {
    res = res || {};
    if (res.locked === true || res.enabled === false) return 'التذكير مقفول، فلم يُرسَل شيء';
    var sent = isNum(res.sent) ? res.sent : 0, err = isNum(res.errors) ? res.errors : 0;
    var t = sent ? 'أُرسل ' + U(sent, ['تذكير واحد', 'تذكيران', 'تذكيرات', 'تذكيرًا']) : 'اكتمل التشغيل ولم يكن هناك ما يُرسل';
    return err ? t + '، وتعذّر ' + U(err, ['تذكير', 'تذكيران', 'تذكيرات', 'تذكيرًا']) : t;
  }

  // ------------------------------------------------------------------ ٧ · الديوان · الأعمال
  function works(resp, now) {
    var list = items(resp);
    if (!list) return null;
    var nowMs = typeof now === 'number' ? now : Date.now();
    var rows = list.map(function (r) {
      var st = str(r.status) || 'pending_review';
      var until = ms(r.featured_until), timed = !isNaN(until) && until > nowMs;        // مميَّز بتاريخ لم ينتهِ بعد (ومنه أسبوع الفائزين)
      return { id: String(r.id), title: str(r.title) || 'عمل بلا عنوان', kind: str(r.kind), kindText: labelOf(WORK_KINDS, str(r.kind)) || 'أخرى',
               creator: str(r.creator_name) || str(r.pen_name) || str(r.creator_email), email: str(r.creator_email), body: short(r.body, 600), about: short(r.about, 300),
               mediaUrl: httpUrl(r.media_url), cover: httpUrl(r.cover_url), status: st, statusText: WORK_STATUS_TEXT[st] || 'حالة غير معروفة', featured: r.featured === true || timed,
               featuredUntil: timed ? dayInput(r.featured_until) : '', locked: r.comments_locked === true, likes: isNum(r.likes) ? r.likes : null, comments: isNum(r.comments_count) ? r.comments_count : null,
               ai: r.ai_assisted === true, rejectReason: str(r.reject_reason), when: when(r.created_at, now), member: r.member_submitted === true, challengeId: str(r.challenge_id) };
    });
    var n = rows.length;
    return { rows: rows, total: isNum(resp.total) ? resp.total : n, countText: n ? U(n, ['عمل واحد', 'عملان', 'أعمال', 'عملًا']) : 'لا أعمال هنا' };
  }
  // kind: approve | reject | feature | unfeature | hide | show | lock | unlock. form: {reason, note, until}
  // ⇒ {ok, error, op:'decide'|'patch', body, lead, lines, goLabel, done}
  function workAction(kind, row, form) {
    form = form || {};
    var t = '«' + row.title + '»';
    if (kind === 'approve') return { ok: true, op: 'decide', body: { decision: 'approve' }, lead: 'سيُنشر العمل ' + t + ' في الديوان فور التأكيد.', goLabel: 'اعتمد ونشر', done: 'اعتُمد العمل ونُشر' };
    if (kind === 'reject') {
      var reason = str(form.reason), note = str(form.note);
      if (reason.length < 3) return { ok: false, error: 'اكتب سبب الرفض (٣ أحرف على الأقل)' };
      if (reason.length > 140) return { ok: false, error: 'سبب الرفض حتى ١٤٠ حرفًا' };
      if (note.length > 1000) return { ok: false, error: 'الملاحظة حتى ١٠٠٠ حرف' };
      var body = { decision: 'reject', reason: reason, note: note };
      var lines = [{ label: 'السبب', to: reason }];
      if (note) lines.push({ label: 'ملاحظة لصاحب العمل', to: short(note, 160) });
      return { ok: true, op: 'decide', body: body, lead: 'سيُرفض العمل ' + t + ' ويُحفظ سبب الرفض معه:', lines: lines, goLabel: 'ارفض العمل', done: 'رُفض العمل' };
    }
    if (kind === 'feature') {
      var until = str(form.until);
      if (until && !realDate(until)) return { ok: false, error: 'تاريخ نهاية التمييز غير صالح' };
      // بتاريخ نهاية: التاريخ وحده يميّز ثم ينتهي (لو بقي «مثبّتًا» لظل العمل مميَّزًا بعد التاريخ)، وبدونه يُثبَّت بلا نهاية
      var b = until ? { featured: false, featured_until: dayEnd(until) } : { featured: true };
      return { ok: true, op: 'patch', body: b, lead: 'سيُميَّز العمل ' + t + ' في الديوان' + (until ? ' حتى ' + dayText(until) : ' بلا تاريخ نهاية') + '.', goLabel: 'ميّز العمل', done: 'تم تمييز العمل' };
    }
    if (kind === 'unfeature') return { ok: true, op: 'patch', body: { featured: false, featured_until: '' }, lead: 'سيزول التمييز عن العمل ' + t + '.', goLabel: 'ألغِ التمييز', done: 'أُلغي تمييز العمل' };
    if (kind === 'hide') return { ok: true, op: 'patch', body: { status: 'hidden' }, lead: 'سيُخفى العمل ' + t + ' عن القرّاء، ويمكنك إظهاره لاحقًا.', goLabel: 'أخفِ العمل', done: 'أُخفي العمل' };
    if (kind === 'show') return { ok: true, op: 'patch', body: { status: 'published' }, lead: 'سيظهر العمل ' + t + ' للقرّاء من جديد.', goLabel: 'أظهر العمل', done: 'ظهر العمل للقرّاء' };
    if (kind === 'lock') return { ok: true, op: 'patch', body: { comments_locked: true }, lead: 'لن يستطيع أحد التعليق على ' + t + ' حتى تفتح التعليقات.', goLabel: 'اقفل التعليقات', done: 'قُفلت التعليقات على العمل' };
    if (kind === 'unlock') return { ok: true, op: 'patch', body: { comments_locked: false }, lead: 'سيعود التعليق مفتوحًا على ' + t + '.', goLabel: 'افتح التعليقات', done: 'فُتحت التعليقات على العمل' };
    return { ok: false, error: 'إجراء غير معروف' };
  }
  function workActions(row) {
    var a = [];
    if (row.status === 'pending_review') a.push(['approve', 'اعتمد', 1], ['reject', 'ارفض', 2]);
    if (row.status === 'published') {
      a.push([row.featured ? 'unfeature' : 'feature', row.featured ? 'ألغِ التمييز' : 'ميّز', 2], [row.locked ? 'unlock' : 'lock', row.locked ? 'افتح التعليقات' : 'اقفل التعليقات', 2], ['hide', 'أخفِ', 2]);
    }
    if (row.status === 'hidden') a.push(['show', 'أظهر', 1]);
    return a;
  }

  // ------------------------------------------------------------------ ٨ · الديوان · التعليقات
  function comments(resp, now) {
    var list = items(resp);
    if (!list) return null;
    var rows = list.map(function (r) {
      var st = str(r.status) || 'visible';
      return { id: String(r.id), name: str(r.display_name) || str(r.user_email), email: str(r.user_email), body: str(r.body), work: str(r.work_title), workId: str(r.work_id),
               hidden: st === 'hidden', statusText: st === 'hidden' ? 'مخفي' : 'ظاهر', when: when(r.created_at, now) };
    });
    var n = rows.length;
    return { rows: rows, total: isNum(resp.total) ? resp.total : n, countText: n ? U(n, ['تعليق واحد', 'تعليقان', 'تعليقات', 'تعليقًا']) : 'لا تعليقات هنا' };
  }

  // ------------------------------------------------------------------ ٩ · الديوان · التحديات
  function challenges(resp, now) {
    var list = items(resp);
    if (!list) return null;
    var rows = list.map(function (r) {
      var st = str(r.status) || 'draft';
      var kinds = Array.isArray(r.kind_allowed) ? r.kind_allowed.filter(function (k) { return typeof k === 'string'; }) : [];
      var sp = r.sponsor && typeof r.sponsor === 'object' ? r.sponsor : null;
      return { id: String(r.id), title: str(r.title) || 'تحدٍّ بلا عنوان', brief: str(r.brief), kinds: kinds, kindsText: kinds.map(function (k) { return labelOf(WORK_KINDS, k) || 'أخرى'; }).join('، '),
               wordCap: isNum(r.word_cap) ? r.word_cap : null, opens: dayInput(r.opens_at), closes: dayInput(r.closes_at), results: dayInput(r.results_at),
               datesText: line([r.opens_at ? 'يبدأ ' + dayText(r.opens_at) : '', r.closes_at ? 'يُغلق ' + dayText(r.closes_at) : '']), status: st, statusText: CH_STATUS_TEXT[st] || 'حالة غير معروفة',
               entries: isNum(r.entries_count) ? r.entries_count : null, prizes: Array.isArray(r.prizes) ? r.prizes : [], jury: Array.isArray(r.jury) ? r.jury : [],
               winners: Array.isArray(r.winners) ? r.winners : [], sponsorName: sp ? str(sp.name) : '', sponsorLogo: sp ? httpUrl(sp.logo_url) : '', cover: httpUrl(r.cover_url),
               canWinners: st === 'closed', when: when(r.created_at, now) };
    });
    var n = rows.length;
    return { rows: rows, total: isNum(resp.total) ? resp.total : n, open: rows.filter(function (r) { return r.status === 'open'; }).length,
             countText: n ? U(n, ['تحدٍّ واحد', 'تحدّيان', 'تحدّيات', 'تحدّيًا']) : 'لا تحدّيات هنا' };
  }
  function prizeTypeText(t) { return labelOf(PRIZE_TYPES, t) || 'أخرى'; }
  // صف ⇒ نموذج. null ⇒ فارغ. التواريخ أيام فقط.
  function challengeForm(row) {
    var r = row || {};
    return { title: row ? r.title : '', brief: r.brief || '', kinds: (r.kinds || []).map(function (k) { return labelOf(WORK_KINDS, k) ? k : OTHER; }), word_cap: r.wordCap ? ar(r.wordCap) : '',
             opens_at: r.opens || '', closes_at: r.closes || '', results_at: r.results || '', status: r.status && r.status !== 'results' ? r.status : (row ? r.status : 'draft'),
             prizes: (r.prizes || []).map(function (p) { return { type: labelOf(PRIZE_TYPES, p.type) ? p.type : OTHER, label: str(p.label), ref: str(p.ref), place: isNum(p.place) ? String(p.place) : '' }; }),
             jury: (r.jury || []).map(function (j) { return { name: str(j.name), title: str(j.title) }; }), sponsor_name: r.sponsorName || '', sponsor_logo: r.sponsorLogo || '', cover_url: r.cover || '' };
  }
  function challengeCheck(form, mode, orig) {
    form = form || {};
    var create = mode === 'create', errors = {}, base = challengeForm(create ? null : orig), body = {}, lines = [];
    var title = str(form.title), brief = str(form.brief);
    if (!title || title.length > 120) errors.title = 'عنوان التحدّي من ١ إلى ١٢٠ حرفًا';
    if (brief.length > 600) errors.brief = 'الوصف حتى ٦٠٠ حرف';
    var kinds = (form.kinds || []).filter(function (k) { return !!labelOf(WORK_KINDS, k); });
    if (!kinds.length) errors.kinds = 'اختر نوع عمل واحدًا على الأقل، أو «أخرى»';
    var cap = null, capP = parseWhole(form.word_cap);
    if (capP.kind === 'bad' || (capP.kind === 'num' && (capP.n < 1 || capP.n > 20000))) errors.word_cap = 'سقف الكلمات من ١ إلى ٢٠٬٠٠٠، أو اتركه فارغًا';
    else if (capP.kind === 'num') cap = capP.n;
    ['opens_at', 'closes_at', 'results_at'].forEach(function (k) {
      var t = str(form[k]);
      if (t && !realDate(t)) errors[k] = 'تاريخ غير صالح';
      else if (!t && create && k !== 'results_at') errors[k] = k === 'opens_at' ? 'تاريخ البدء مطلوب' : 'تاريخ الإغلاق مطلوب';
    });
    if (!errors.opens_at && !errors.closes_at && str(form.opens_at) && str(form.closes_at) && str(form.closes_at) <= str(form.opens_at)) errors.closes_at = 'يجب أن يكون الإغلاق بعد البدء';
    var status = str(form.status);
    if (create && status !== 'draft' && status !== 'open') errors.status = 'اختر: مسودة أو مفتوح';
    if (!create && ['draft', 'open', 'closed'].indexOf(status) < 0 && status !== str(base.status)) errors.status = 'اختر الحالة';
    var prizes = [], jury = [];
    (form.prizes || []).forEach(function (p, i) {
      var label = str(p.label), ref = str(p.ref), place = str(p.place);
      if (!label && !ref && !place) return;
      var tp = labelOf(PRIZE_TYPES, p.type) ? p.type : '';
      if (!tp) errors['prize' + i] = 'اختر نوع الجائزة، أو «أخرى»';
      else if (!label || label.length > 80) errors['prize' + i] = 'اسم الجائزة من ١ إلى ٨٠ حرفًا';
      else if (ref.length > 120) errors['prize' + i] = 'مرجع الجائزة حتى ١٢٠ حرفًا';
      else if (place && ['1', '2', '3'].indexOf(toLatin(place)) < 0) errors['prize' + i] = 'المركز من ١ إلى ٣';
      var row = { type: tp === OTHER ? 'certificate' : tp, label: label, ref: ref };
      if (place) row.place = Number(toLatin(place));
      prizes.push(row);
    });
    if (prizes.length > 6) errors.prizes = 'الجوائز حتى ٦';
    (form.jury || []).forEach(function (j, i) {
      var name = str(j.name), tt = str(j.title);
      if (!name && !tt) return;
      if (!name || name.length > 80) errors['jury' + i] = 'اسم المحكّم من ١ إلى ٨٠ حرفًا';
      else if (tt.length > 80) errors['jury' + i] = 'صفة المحكّم حتى ٨٠ حرفًا';
      jury.push({ name: name, title: tt });
    });
    if (jury.length > 6) errors.jury = 'اللجنة حتى ٦ أعضاء';
    if (create && status === 'open' && jury.length !== 3) errors.jury = 'يجب أن تتكون لجنة التحكيم من ثلاثة أعضاء قبل فتح التحدّي';
    var spName = str(form.sponsor_name), spLogo = str(form.sponsor_logo), cover = str(form.cover_url);
    if (spLogo && !spName) errors.sponsor_name = 'اكتب اسم الراعي مع الشعار';
    if (spName.length > 80) errors.sponsor_name = 'اسم الراعي حتى ٨٠ حرفًا';
    if (spLogo && (spLogo.length > 500 || !HTTPS_RE.test(spLogo))) errors.sponsor_logo = 'يجب أن يبدأ رابط الشعار بـ https';
    if (cover && (cover.length > 500 || !HTTPS_RE.test(cover))) errors.cover_url = 'يجب أن يبدأ رابط الغلاف بـ https';
    if (Object.keys(errors).length) return { ok: false, error: 'صحّح الخانات المعلَّمة', errors: errors };

    function put(key, label, before, after, show) {
      var same = JSON.stringify(before) === JSON.stringify(after);
      if (!create && same) return;
      if (create && (after === '' || after == null || (Array.isArray(after) && !after.length))) return;
      body[key] = after;
      lines.push({ label: label, from: create ? '' : (show ? show(before) : (before || 'فارغ')), to: show ? show(after) : (after || 'فارغ') });
    }
    var dshow = function (v) { return v ? dayText(v) : 'فارغ'; };
    var kshow = function (v) { return (v || []).map(function (k) { return labelOf(WORK_KINDS, k) || 'أخرى'; }).join('، ') || 'فارغ'; };
    var pshow = function (v) { return (v || []).length ? v.map(function (p) { return (p.place ? 'المركز ' + PLACES[p.place] + ': ' : '') + (p.label || prizeTypeText(p.type)); }).join('، ') : 'فارغ'; };
    var jshow = function (v) { return (v || []).length ? v.map(function (j) { return j.name + (j.title ? ' (' + j.title + ')' : ''); }).join('، ') : 'فارغ'; };
    put('title', 'العنوان', str(base.title), title);
    put('brief', 'الوصف', str(base.brief), brief, function (v) { return v ? short(v, 120) : 'فارغ'; });
    if (create || JSON.stringify((base.kinds || []).slice().sort()) !== JSON.stringify(kinds.slice().sort())) {         // المقارنة بلا ترتيب، والمرسَل بترتيب الاختيار
      body.kind_allowed = kinds;
      lines.push({ label: 'أنواع الأعمال', from: create ? '' : kshow(base.kinds), to: kshow(kinds) });
    }
    if (create) { if (cap != null) { body.word_cap = cap; lines.push({ label: 'سقف الكلمات', from: '', to: ar(cap) }); } }
    else put('word_cap', 'سقف الكلمات', parseWhole(base.word_cap).n == null ? null : parseWhole(base.word_cap).n, cap, function (v) { return v == null ? 'بلا سقف' : ar(v); });
    put('opens_at', 'يبدأ', str(base.opens_at), str(form.opens_at), dshow);
    put('closes_at', 'يُغلق', str(base.closes_at), str(form.closes_at), dshow);
    put('results_at', 'النتائج', str(base.results_at), str(form.results_at), dshow);
    if (body.closes_at) body.closes_at = dayEnd(body.closes_at);          // العرض والمقارنة باليوم، والمرسَل آخر لحظة منه
    put('status', 'الحالة', base.status, status, function (v) { return CH_STATUS_TEXT[v] || 'فارغ'; });
    put('prizes', 'الجوائز', (base.prizes || []).map(function (p) { var o = { type: p.type === OTHER ? 'certificate' : p.type, label: p.label, ref: p.ref }; if (p.place) o.place = Number(p.place); return o; }), prizes, pshow);
    put('jury', 'لجنة التحكيم', base.jury, jury, jshow);
    if (create) { if (spName) { body.sponsor = { name: spName, logo_url: spLogo }; lines.push({ label: 'الراعي', from: '', to: spName }); } }
    else if (str(base.sponsor_name) !== spName || str(base.sponsor_logo) !== spLogo) {
      body.sponsor = spName ? { name: spName, logo_url: spLogo } : null;
      lines.push({ label: 'الراعي', from: str(base.sponsor_name) || 'بلا راعٍ', to: spName || 'بلا راعٍ' });
    }
    put('cover_url', 'رابط الغلاف', str(base.cover_url), cover);
    if (!create && !Object.keys(body).length) return { ok: false, error: 'لا يوجد تغيير', errors: {} };
    var lead = create ? (body.status === 'open' ? 'سيُفتح التحدّي «' + title + '» للمشاركة فور التأكيد.' : 'سيُحفظ التحدّي «' + title + '» مسودة، ولا يظهر حتى تفتحه.') : 'ستُحفظ التعديلات على التحدّي «' + title + '»:';
    return { ok: true, body: body, lines: lines, lead: lead, errors: {} };
  }
  // اختيار الفائزين: form.rows = [{work_id, jury_line}] للمراكز ١ و٢ و٣ بالترتيب. entries: صفوف الأعمال (works().rows) ⇒ {ok, error, body, lines, lead}
  function winnersCheck(form, entries) {
    var rows = (form && form.rows) || [], picked = [], seen = {}, gap = false;
    for (var i = 0; i < 3; i++) {
      var r = rows[i] || {}, id = str(r.work_id), jl = str(r.jury_line);
      if (!id) { if (jl) return { ok: false, error: 'اختر العمل الفائز بالمركز ' + PLACES[i + 1] + ' أو احذف سطر اللجنة' }; gap = true; continue; }
      if (gap) return { ok: false, error: 'اختر الفائز بالمركز ' + PLACES[i] + ' أولًا' };
      if (seen[id]) return { ok: false, error: 'لا يتكرر العمل نفسه في مركزين' };
      if (!jl) return { ok: false, error: 'اكتب سطر اللجنة للمركز ' + PLACES[i + 1] };
      if (jl.length > 140) return { ok: false, error: 'سطر اللجنة حتى ١٤٠ حرفًا' };
      seen[id] = 1;
      picked.push({ place: i + 1, work_id: id, jury_line: jl });
    }
    if (!picked.length) return { ok: false, error: 'اختر فائزًا واحدًا على الأقل' };
    var lines = picked.map(function (w) {
      var e = (entries || []).filter(function (x) { return x.id === w.work_id; })[0];
      return { label: 'المركز ' + PLACES[w.place], to: (e ? e.title + (e.creator ? ' (' + e.creator + ')' : '') : 'عمل') + ' — «' + w.jury_line + '»' };
    });
    return { ok: true, body: { winners: picked }, lines: lines, lead: 'ستُعلن النتيجة بهذه الأسماء، وتُصدر شهادات الفائزين ويصلهم بريد بالنتيجة. راجع الأسماء جيدًا قبل التأكيد:' };
  }
  function winnersDone(res) {
    if (res && res.already === true) return 'سبق إعلان نتيجة هذا التحدّي، ولم يتغير شيء';
    var c = res && Array.isArray(res.certificates) ? res.certificates.length : 0, e = res && isNum(res.emails_sent) ? res.emails_sent : 0;
    return 'أُعلنت النتيجة، وأُصدرت ' + U(c, ['شهادة واحدة', 'شهادتان', 'شهادات', 'شهادة']) + (e ? '، وأُرسل ' + U(e, ['بريد واحد', 'بريدان', 'رسائل بريد', 'بريدًا']) : '');
  }

  // ------------------------------------------------------------------ ١٠ · الديوان · التقرير
  function pct(v) { return v == null ? null : ar(Math.round((v > 1 ? v / 100 : v) * 100)) + '٪'; }
  function report(resp) {
    if (!resp || typeof resp !== 'object') return null;
    var num = function (k) { return isNum(resp[k]) ? resp[k] : null; };
    var wa = resp.works_acceptance && typeof resp.works_acceptance === 'object' ? resp.works_acceptance : null;
    var cards = [
      { key: 'visitors', label: 'زوّار الديوان', value: num('visitors'), hint: 'زائر مميَّز' },
      { key: 'legal_open_share', label: 'من فتحوا مساحة قانونية', value: num('legal_open_share'), hint: 'من مجموع الزيارات', pct: true },
      { key: 'signups', label: 'حسابات جاءت من الديوان', value: num('signups'), hint: 'حساب جديد' },
      { key: 'share_card_clicks', label: 'نقرات مشاركة البطاقة', value: num('share_card_clicks'), hint: 'نقرة' },
      { key: 'return_7d', label: 'عادوا خلال أسبوع', value: num('return_7d'), hint: 'ممن زاروا أول مرة', pct: true }
    ].map(function (c) {
      var has = c.value != null;
      return { key: c.key, label: c.label, hint: c.hint, na: !has, text: has ? (c.pct ? pct(c.value) : fmt(c.value)) : NO_NUM };
    });
    var acc = wa && isNum(wa.submitted) && isNum(wa.accepted) ? { na: false, text: fmt(wa.accepted) + ' من ' + fmt(wa.submitted), pct: isNum(wa.ratio) ? pct(wa.ratio) : '' }
      : { na: true, text: NO_NUM, pct: '' };
    var epc = Array.isArray(resp.entries_per_challenge) ? resp.entries_per_challenge.filter(function (e) { return e && typeof e === 'object'; }).map(function (e) {
      return { title: str(e.title) || 'تحدٍّ بلا عنوان', n: isNum(e.entries) ? e.entries : null };
    }) : null;
    var days = isNum(resp.window_days) ? resp.window_days : 30;
    return { cards: cards, acceptance: acc, challenges: epc, daysText: 'آخر ' + U(days, ['يوم', 'يومين', 'أيام', 'يومًا']), days: days };
  }
  function reportTile(v) {
    if (!v) return { n: '—', sub: NA, off: true };
    var c = v.cards[0];
    return c.na ? { n: '—', sub: NO_NUM, off: true } : { n: c.text, sub: 'زائر ' + v.daysText, hot: false };
  }

  L.v2sSaha = {
    OTHER: OTHER, NA: NA, NO_NUM: NO_NUM, OPP_KINDS: OPP_KINDS, KIND_CHIPS: KIND_CHIPS, LANGS: LANGS, FUNDS: FUNDS, NEWS_CATS: NEWS_CATS, COUNTRIES: COUNTRIES,
    OPP_STATUS_CHIPS: OPP_STATUS_CHIPS, OP_CHIPS: OP_CHIPS, NEWS_CHIPS: NEWS_CHIPS, WORK_KINDS: WORK_KINDS, WORK_CHIPS: WORK_CHIPS, COMMENT_CHIPS: COMMENT_CHIPS,
    CH_CHIPS: CH_CHIPS, PRIZE_TYPES: PRIZE_TYPES, PLACES: PLACES, DAYS_CHIPS: DAYS_CHIPS, REVIEW_TEXT: REVIEW_TEXT,
    arDigits: arDigits, fixSep: fixSep, line: line, dayText: dayText, dayInput: dayInput, realDate: realDate, parseWhole: parseWhole, writeError: writeError,
    kindText: kindText, langText: langText, fundText: fundText, countryText: countryText, kindMatches: kindMatches,
    news: news, newsForm: newsForm, newsCheck: newsCheck, newsRunCheck: newsRunCheck, newsRunDone: newsRunDone,
    opps: opps, oppFilter: oppFilter, oppCountText: oppCountText, pendingText: pendingText, oppForm: oppForm, oppCheck: oppCheck, oppDecision: oppDecision, oppDone: oppDone,
    prepView: prepView, prepCheck: prepCheck, seedView: seedView, seedDone: seedDone, seedCheck: seedCheck,
    opinions: opinions, topics: topics, opinionAction: opinionAction, reminders: reminders, reminderTile: reminderTile, reminderRunDone: reminderRunDone,
    works: works, workAction: workAction, workActions: workActions, comments: comments, challenges: challenges, challengeForm: challengeForm, challengeCheck: challengeCheck,
    prizeTypeText: prizeTypeText, winnersCheck: winnersCheck, winnersDone: winnersDone, report: report, reportTile: reportTile
  };
  if (typeof module !== 'undefined' && module.exports) module.exports.v2sSaha = L.v2sSaha;
})(typeof window !== 'undefined' ? window : (typeof globalThis !== 'undefined' ? globalThis : this));

/* ============================================================================
 * v2s/saha.js — الجزء الثاني: محرّك اللوحات المشترك (`V2S_SAHA_KIT.board`) + لوحة «الساحة» (تبويب في قسم «المحتوى»).
 * مربّعات بصور وكل مربّع يفتح مهمة واحدة وعليها «→ الساحة» للرجوع. «الديوان» في `saha_diwan.js` على نفس المحرّك.
 * ⛔ لا منطق عمل هنا: كل التحقق والنصوص من `V2L.v2sSaha`. ولا طلب شبكة إلا `/api/v2/saha/*` و`/api/v2/diwan/*` (بروكسيات أدمن).
 * ⛔ كل كتابة تمرّ على ورقة مراجعة ثم تأكيد وتذهب بـ`confirmed: true`. مفيش confirm()/alert()/prompt() ولا حفظ في المتصفح.
 * ⛔ المفتاح مقفول: الملف بيتحمّل دايمًا لكنه ما بيرسم شيئًا إلا لو index.html نادى `render` (والغلاف الجديد شغّال).
 * ========================================================================== */
(function () {
  'use strict';
  if (typeof window === 'undefined' || typeof document === 'undefined') return;
  var L = window.V2L;
  if (!L || !L.v2sSaha) return;
  var X = L.v2sSaha, U = L.util, ar = U.ar;
  var Kit = window.V2S_SAHA_KIT = {};

  function esc(s) { return String(s == null ? '' : s).replace(/[&<>"']/g, function (c) { return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]; }); }
  function host() { return window.V2_HOST || {}; }
  function ep() { return window.EP || null; }
  function img(n) { return 'v2/img/' + n + '.jpg'; }
  function q1(sel, root) { return (root || document).querySelector(sel); }
  function qa(sel, root) { return Array.prototype.slice.call((root || document).querySelectorAll(sel)); }
  function roleName() { try { if (typeof role !== 'undefined') return role; } catch (e) {} var E = ep(); return (E && E.role) || ''; }
  function modalOpen() { return !!document.getElementById('epModal'); }
  function scrollTop() { try { var c = document.querySelector('.content'); if (c) c.scrollTop = 0; window.scrollTo(0, 0); } catch (e) {} }
  Kit.esc = esc; Kit.q1 = q1; Kit.qa = qa; Kit.img = img;

  // ------------------------------------------------------------------ بناة الحقول داخل الأوراق (الأسماء في data-f والتجميع بنداء واحد)
  function fld(label, inner, name, hint) {
    return '<div class="fld"><label' + (name ? ' for="f_' + name + '"' : '') + '>' + esc(label) + '</label>' + inner + (hint ? '<small class="hint">' + esc(hint) + '</small>' : '')
      + (name ? '<small class="ferr" data-e="' + name + '" role="alert"></small>' : '') + '</div>';
  }
  function inp(name, v, o) {
    o = o || {};
    return '<input id="f_' + name + '" data-f="' + name + '" type="' + (o.type || 'text') + '" value="' + esc(v) + '"' + (o.max ? ' maxlength="' + o.max + '"' : '')
      + (o.ph ? ' placeholder="' + esc(o.ph) + '"' : '') + (o.ltr ? ' dir="ltr"' : '') + (o.mode ? ' inputmode="' + o.mode + '"' : '') + ' autocomplete="off">';
  }
  function txt(name, v, rows, max) { return '<textarea id="f_' + name + '" data-f="' + name + '" rows="' + (rows || 3) + '"' + (max ? ' maxlength="' + max + '"' : '') + '>' + esc(v) + '</textarea>'; }
  function sel(name, v, opts, ph) {
    return '<select id="f_' + name + '" data-f="' + name + '">' + (ph != null ? '<option value="">' + esc(ph) + '</option>' : '')
      + opts.map(function (o) { return '<option value="' + esc(o[0]) + '"' + (String(o[0]) === String(v) ? ' selected' : '') + '>' + esc(o[1]) + '</option>'; }).join('') + '</select>';
  }
  function chk(name, v, label) { return '<label class="sh-chk"><input type="checkbox" data-f="' + name + '"' + (v ? ' checked' : '') + '><span>' + esc(label) + '</span></label>'; }
  function collect(root) {
    var o = {};
    qa('[data-f]', root).forEach(function (el) { o[el.getAttribute('data-f')] = el.type === 'checkbox' ? el.checked : el.value; });
    qa('[data-fm]', root).forEach(function (el) { var n = el.getAttribute('data-fm'); o[n] = o[n] || []; if (el.checked) o[n].push(el.value); });
    return o;
  }
  function showErrors(root, res) {
    var errs = res.errors || {}, first = null;
    qa('[data-e]', root).forEach(function (el) { var m = errs[el.getAttribute('data-e')] || ''; el.textContent = m; if (m && !first) first = el; });
    qa('[data-f]', root).forEach(function (el) { el.classList.toggle('bad', !!errs[el.getAttribute('data-f')]); });
    qa('details', root).forEach(function (d) { if (qa('[data-e]', d).some(function (e) { return !!errs[e.getAttribute('data-e')]; })) d.open = true; });
    var box = q1('#shErr', root);
    if (box) box.innerHTML = res.error ? '<div class="sh-err" role="alert">' + esc(res.error) + '</div>' : '';
    if (first) { try { first.scrollIntoView({ block: 'center' }); var f = first.parentNode.querySelector('[data-f]'); if (f) f.focus(); } catch (e) {} }
  }
  function diffHtml(lines) {
    if (!lines || !lines.length) return '';
    return '<ul class="sh-diff">' + lines.map(function (l) {
      var change = l.from != null && l.from !== '';
      return '<li><b>' + esc(l.label) + '</b><span>' + (change ? '<s>' + esc(l.from) + '</s><i aria-hidden="true">←</i>' : '') + '<em>' + esc(l.to) + '</em></span></li>';
    }).join('') + '</ul>';
  }
  Kit.fld = fld; Kit.inp = inp; Kit.txt = txt; Kit.sel = sel; Kit.chk = chk; Kit.collect = collect; Kit.diffHtml = diffHtml;

  // ------------------------------------------------------------------ المحرّك
  // cfg: {key, mod, label, tiles(B), hub(B) ⇒ مسارات الرقم، screens: {sub: fn(B) ⇒ {title, sub, img, html}}، act: {name: fn(B, el, id)}}
  Kit.board = function (cfg) {
    var B = { cfg: cfg, S: { sub: 'hub', src: {}, f: {}, note: '', noteT: null, view: null, retryT: null, drawT: null } };
    var S = B.S;
    B.canWrite = function () { return roleName() === 'admin'; };
    B.owns = function (mod) { return !!(mod === cfg.mod && window.V2_ON && window.V2SHELL && window.V2SHELL.on); };
    function isCurrent() { return !!(S.view && document.body.contains(S.view) && host().current && B.owns(host().current())); }

    // —— المصادر: المفتاح هو المسار نفسه
    function src(p) { return S.src[p] || (S.src[p] = { state: 'idle', data: null, status: 0, seq: 0 }); }
    function load(p, force) {
      var s = src(p), E = ep();
      if (!E || !E.api || !E.authed) return;
      if (!force && s.state !== 'idle') return;
      if (s.state === 'idle') s.state = 'loading';
      var seq = ++s.seq;
      E.api(p).then(function (d) {
        if (seq !== s.seq) return;
        s.state = 'ready'; s.data = d; s.status = 200; changed();
      }).catch(function (e) {
        if (seq !== s.seq || (e && e.status === 401)) return;
        s.state = e && e.status === 404 ? 'closed' : 'error'; s.status = (e && e.status) || 0; s.data = null; changed();
      });
    }
    B.need = function (p) { load(p, false); };
    B.state = function (p) { return src(p).state; };
    B.data = function (p) { var s = src(p); return s.state === 'ready' ? s.data : null; };
    B.refresh = function () { Object.keys(S.src).forEach(function (p) { if (S.src[p].state !== 'idle') load(p, true); }); };
    B.failed = function (p) { var st = src(p).state; return st === 'error' || st === 'closed'; };
    function changed() { if (S.drawT) return; S.drawT = setTimeout(function () { S.drawT = null; redraw(); }, 0); }
    function redraw() {
      if (!isCurrent()) return;
      if (modalOpen()) {                                  // لا نمسح ما يكتبه المؤسس في ورقة مفتوحة؛ نلحق بعد إغلاقها
        if (!S.retryT) S.retryT = setInterval(function () { if (modalOpen()) return; clearInterval(S.retryT); S.retryT = null; redraw(); }, 400);
        return;
      }
      draw(S.view);
    }
    B.redraw = redraw;
    B.setNote = function (t) { S.note = t; clearTimeout(S.noteT); S.noteT = setTimeout(function () { S.note = ''; redraw(); }, 9000); };
    B.f = function (k, d) { return S.f[k] === undefined ? d : S.f[k]; };
    B.set = function (k, v) { S.f[k] = v; };
    B.api = function (path, body, method) { return ep().api(path, { method: method || 'POST', body: body }); };

    // —— أجزاء مشتركة
    B.stateBlock = function (p, what) {
      var st = src(p).state;
      if (st === 'idle' || st === 'loading') return '<div class="sh-skel" role="status" aria-label="جارٍ التحميل"><i></i><i></i><i></i></div>';
      return '<div class="sh-warn" role="alert"><span>' + esc(what) + ': غير متاح بعد' + (st === 'error' ? '، وليس معناه أنه لا شيء ينتظرك' : '') + '</span><button type="button" class="ep-bs" data-a="retry">أعد المحاولة</button></div>';
    };
    B.empty = function (title, text) { return '<div class="sh-empty"><b>' + esc(title) + '</b>' + (text ? '<p>' + esc(text) + '</p>' : '') + '</div>'; };
    B.chips = function (key, list, cur) {
      return '<div class="sh-ctl" role="group">' + list.map(function (c) {
        return '<button type="button" class="sh-chip' + (String(c[0]) === String(cur) ? ' on' : '') + '" data-a="chip" data-k="' + key + '" data-v="' + esc(c[0]) + '" aria-pressed="' + (String(c[0]) === String(cur)) + '">' + esc(c[1]) + (c[2] ? ' <i class="sh-cn">' + esc(c[2]) + '</i>' : '') + '</button>';
      }).join('') + '</div>';
    };
    // جدول للكمبيوتر وبطاقات للموبايل من نفس تعريف الأعمدة؛ cols: [{h, c(r) ⇒ html}] (الأول عنوان البطاقة)، acts(r) ⇒ html أزرار.
    B.list = function (rows, cols, acts) {
      var head = cols.map(function (c) { return '<th>' + esc(c.h) + '</th>'; }).join('') + (acts ? '<th><span class="sh-vh">إجراءات</span></th>' : '');
      var body = rows.map(function (r) {
        return '<tr data-id="' + esc(r.id) + '">' + cols.map(function (c) { return '<td>' + c.c(r) + '</td>'; }).join('') + (acts ? '<td class="sh-ta">' + acts(r) + '</td>' : '') + '</tr>';
      }).join('');
      var cards = rows.map(function (r) {
        return '<li class="sh-card" data-id="' + esc(r.id) + '"><div class="sh-ch">' + cols[0].c(r) + '</div>' + cols.slice(1).map(function (c) {
          var h = c.c(r);
          return h ? '<p class="sh-meta"><b>' + esc(c.h) + '</b><span>' + h + '</span></p>' : '';
        }).join('') + (acts ? '<div class="sh-acts">' + acts(r) + '</div>' : '') + '</li>';
      }).join('');
      return '<div class="sh-tbw"><table class="sh-tb"><thead><tr>' + head + '</tr></thead><tbody>' + body + '</tbody></table></div><ul class="sh-cards sh-m">' + cards + '</ul>';
    };

    // —— الأوراق
    B.sheet = function (title, html) {
      if (typeof window.openModal !== 'function') return null;
      var s = window.openModal(title, '<div class="v3m v2s-sh-sb">' + html + '</div>');
      s.classList.add('v2s-sh-sh');
      var x = s.querySelector('[data-x]');
      if (x) { x.setAttribute('aria-label', 'إغلاق'); x.onclick = function () { if (!s.dataset.busy) window.closeModal(); }; }
      s.onclick = function (e) { if (e.target === s && !s.dataset.busy) window.closeModal(); };
      return s;
    };
    function runWrite(s, goBtn, noBtn, errBox, label, send, onOk) {
      if (s.dataset.busy) return;
      s.dataset.busy = '1'; goBtn.disabled = true; if (noBtn) noBtn.disabled = true; goBtn.textContent = 'جارٍ التنفيذ…'; errBox.innerHTML = '';
      Promise.resolve(send()).then(function (res) {
        delete s.dataset.busy; window.closeModal(); onOk(res || {}); B.refresh(); redraw();
      }).catch(function (e) {
        delete s.dataset.busy; goBtn.disabled = false; if (noBtn) noBtn.disabled = false; goBtn.textContent = label;
        errBox.innerHTML = '<div class="sh-err" role="alert">' + esc(X.writeError(e && e.status, e && e.data)) + '</div>';
      });
    }
    // تدفّق كتابة واحد: [نموذج ⇒] مراجعة «قبل ⇐ بعد» ⇒ تأكيد. ⛔ لا نداء قبل ضغطة التأكيد الأخيرة.
    // o: {title, intro, form(vals) ⇒ html | null، init، collect(root)، hook({root, s, redo}), check(vals) ⇒ {ok, error, errors, lead, lines, warns, ...},
    //     nextLabel, goLabel (يؤخذ من النتيجة لو غاب)، check قد يرجع وعدًا ⇒ نتيجة (معاينة من الخادم)، send(res) ⇒ promise, done(out, res) ⇒ نص، extra: [{id, label, run(s)}]}
    B.flow = function (o) {
      var s = B.sheet(o.title, '<div id="shStage"></div>');
      if (!s) return;
      var stage = q1('#shStage', s), vals = o.init || {}, gather = o.collect || collect;
      function close() { if (!s.dataset.busy) window.closeModal(); }
      function formStage() {
        s.dataset.stage = 'form';
        stage.innerHTML = (o.intro ? '<p class="mc-lead">' + esc(o.intro) + '</p>' : '') + o.form(vals) + '<div id="shErr" role="alert"></div>'
          + '<div class="acts"><button type="button" class="ep-b1" id="shNext">' + esc(o.nextLabel || 'راجع ثم احفظ') + '</button>'
          + (o.extra || []).map(function (x) { return '<button type="button" class="ep-bs" id="' + x.id + '">' + esc(x.label) + '</button>'; }).join('')
          + '<button type="button" class="ep-b2" id="shNo">رجوع</button></div>';
        q1('#shNo', s).onclick = close;
        (o.extra || []).forEach(function (x) { q1('#' + x.id, s).onclick = function () { x.run(s); }; });
        q1('#shNext', s).onclick = function () {
          if (s.dataset.checking) return;
          vals = gather(s);
          var r = o.check(vals);
          var land = function (x) { if (!x.ok) { showErrors(stage, x); return; } review(x); };
          // check قد يرجع وعدًا (معاينة من الخادم بلا كتابة، مثل «افتح نقاشًا للمصطلح»): الزرّ يتعطّل أثناءها، والفشل يظهر في الورقة.
          if (r && typeof r.then === 'function') {
            var nx = q1('#shNext', s), label = nx.textContent;
            s.dataset.checking = '1'; nx.disabled = true; nx.textContent = 'جارٍ التحقق…';
            r.then(function (x) { delete s.dataset.checking; nx.disabled = false; nx.textContent = label; if (s.isConnected) land(x); },
                   function () { delete s.dataset.checking; nx.disabled = false; nx.textContent = label; showErrors(stage, { ok: false, error: 'تعذّر التحقق، حاول مرة أخرى' }); });
            return;
          }
          land(r);
        };
        if (o.hook) o.hook({ root: stage, s: s, redo: function (v) { vals = v || gather(s); formStage(); } });
        var first = q1('[data-f]', stage); if (first) setTimeout(function () { try { first.focus(); } catch (e) {} }, 30);
      }
      function review(r) {
        s.dataset.stage = 'review';
        var warns = (r.warns || []).map(function (w) { return '<li>' + esc(w) + '</li>'; }).join('');
        stage.innerHTML = '<p class="mc-lead">' + esc(r.lead || o.intro || '') + '</p>' + diffHtml(r.lines) + (warns ? '<ul class="sh-warns">' + warns + '</ul>' : '') + (r.extraHtml || '')
          + '<div id="shErr" role="alert"></div><div class="acts"><button type="button" class="ep-b1" id="shGo">' + esc(r.goLabel || o.goLabel || 'تأكيد') + '</button>'
          + '<button type="button" class="ep-b2" id="shBack">' + esc(o.form ? 'ارجع للتعديل' : 'رجوع') + '</button></div>';
        var go = q1('#shGo', s), bk = q1('#shBack', s), err = q1('#shErr', s);
        bk.onclick = function () { if (s.dataset.busy) return; if (o.form) formStage(); else close(); };
        go.onclick = function () {
          runWrite(s, go, bk, err, r.goLabel || o.goLabel || 'تأكيد', function () { return o.send(r); }, function (out) { var t = o.done ? o.done(out, r) : ''; if (t) B.setNote(t); if (o.after) o.after(out, r); });
        };
        setTimeout(function () { try { bk.focus(); } catch (e) {} }, 30);
      }
      if (o.form) formStage();
      else {
        var r0 = o.check(vals);
        if (r0.ok) review(r0);
        else { stage.innerHTML = '<div class="sh-err" role="alert">' + esc(r0.error) + '</div><div class="acts"><button type="button" class="ep-b2" id="shNo">رجوع</button></div>'; q1('#shNo', s).onclick = close; }
      }
    };

    // —— الرسم
    function back(title, sub, imgName) {
      return '<div class="sh-bar"><button type="button" class="ep-bs sh-back" data-a="hub">→ ' + esc(cfg.label) + '</button></div>'
        + '<header class="sh-head"><span class="sh-himg" style="background-image:url(' + img(imgName) + ')" role="img" aria-label="' + esc(title) + '"></span><div><h2>' + esc(title) + '</h2>' + (sub ? '<p>' + esc(sub) + '</p>' : '') + '</div></header>';
    }
    function noteHtml() { return S.note ? '<p class="sh-note" role="status">' + esc(S.note) + '</p>' : ''; }
    function hub(v) {
      var defs = cfg.tiles(B), anyFail = (cfg.hub(B) || []).some(function (p) { return B.failed(p); });
      var warn = anyFail ? '<div class="sh-warn" role="status"><span>بعض الأرقام غير متاحة الآن</span><button type="button" class="ep-bs" data-a="retry">أعد المحاولة</button></div>' : '';
      v.innerHTML = '<div class="v2s-sh" data-board="' + cfg.key + '-hub">' + noteHtml() + '<p class="sh-lead">' + esc(cfg.lead) + '</p>' + warn
        + '<div class="sh-tiles" role="list">' + defs.map(function (t) {
          return '<button type="button" class="sh-tile' + (t.hot ? ' hot' : '') + (t.off ? ' off' : '') + '" role="listitem" data-a="go" data-sub="' + t.sub + '">'
            + '<span class="sh-timg" style="background-image:url(' + img(t.img) + ')" role="img" aria-label="' + esc(t.name) + '"></span>'
            + '<span class="sh-tbody"><b class="sh-n' + (t.word ? ' word' : '') + '">' + esc(t.n) + '</b><span class="sh-tname">' + esc(t.name) + '</span><small>' + esc(t.note) + '</small></span></button>';
        }).join('') + '</div></div>';
    }
    function draw(v) {
      if (!v) return;
      if (!B.canWrite()) { v.innerHTML = '<div class="v2s-sh" data-board="' + cfg.key + '-ro"><p class="sh-ro" role="status">هذا القسم للإدارة فقط</p></div>'; return; }
      (cfg.hub(B) || []).forEach(B.need);
      if (S.sub === 'hub' || !cfg.screens[S.sub]) { S.sub = 'hub'; return hub(v); }
      var sc = cfg.screens[S.sub](B);
      v.innerHTML = '<div class="v2s-sh" data-board="' + cfg.key + '-' + S.sub + '">' + noteHtml() + back(sc.title, sc.sub, sc.img) + sc.html + '</div>';
      if (sc.after) sc.after(v);
    }
    B.draw = draw;
    function onClick(e) {
      var a = e.target.closest ? e.target.closest('[data-a]') : null;
      if (!a || !S.view.contains(a) || a.disabled) return;
      var k = a.getAttribute('data-a'), id = a.getAttribute('data-id');
      if (k === 'go') { S.sub = a.getAttribute('data-sub'); S.note = ''; redraw(); scrollTop(); }
      else if (k === 'hub') { S.sub = 'hub'; redraw(); scrollTop(); }
      else if (k === 'retry') { Object.keys(S.src).forEach(function (p) { var st = S.src[p].state; if (st === 'error' || st === 'closed') S.src[p].state = 'loading'; }); B.refresh(); redraw(); }
      else if (k === 'chip') { S.f[a.getAttribute('data-k')] = a.getAttribute('data-v'); redraw(); }
      else if (cfg.act[k]) cfg.act[k](B, a, id);
    }
    B.render = function (mod, view) {
      S.view = view;
      var E = ep();
      if (E && E.authed && B.canWrite()) (cfg.hub(B) || []).forEach(B.need);
      view.onclick = onClick;
      draw(view);
    };
    (window.V2SEC = window.V2SEC || {})[cfg.key] = { owns: B.owns, render: B.render };
    return B;
  };

  // ------------------------------------------------------------------ مؤشرات المربّعات
  Kit.count = function (B, path, getter) {
    var st = B.state(path);
    if (st === 'ready') { var v = getter(); return v == null ? { n: '—', note: X.NA, off: true } : v; }
    if (st === 'error' || st === 'closed') return { n: '—', note: X.NA, off: true };
    return { n: '…', note: 'جارٍ التحميل', off: true };
  };
  Kit.pill = function (text, cls) { return '<span class="sh-st' + (cls ? ' ' + cls : '') + '">' + esc(text) + '</span>'; };
  Kit.link = function (url, text) { return url ? '<a class="sh-lnk" href="' + esc(url) + '" target="_blank" rel="noopener noreferrer">' + esc(text) + '</a>' : ''; };
  Kit.who = function (email) { return email ? '<span class="sh-who" dir="ltr">' + esc(email) + '</span>' : ''; };

  // ============================================================================================================================
  // لوحة «الساحة»
  // ============================================================================================================================
  var P = {
    news: function (st) { return '/v2/saha/news?status=' + st; },
    rev: '/v2/saha/opportunities?review_status=pending',
    opps: '/v2/saha/opportunities?review_status=all',
    settings: '/v2/saha/settings',
    rem: '/v2/saha/reminders',
    topics: '/v2/saha/topics?status=open',
    ops: function (st, topic) { return '/v2/saha/opinions?status=' + st + (topic ? '&topic_id=' + encodeURIComponent(topic) : ''); }
  };
  var HUB = [P.news('draft'), P.rev, P.opps, P.settings, P.ops('pending', ''), P.rem];
  var now = function () { return Date.now(); };
  var B = null;
  function row(rows, id) { for (var i = 0; i < (rows || []).length; i++) if (rows[i].id === id) return rows[i]; return null; }
  function newsView(st) { var d = B.data(P.news(st)); return d ? X.news(d, now()) : null; }
  function revView() { var d = B.data(P.rev); return d ? X.opps(d, now()) : null; }
  function oppsView() { var d = B.data(P.opps); return d ? X.opps(d, now()) : null; }
  function opsView(st, topic) { var d = B.data(P.ops(st, topic)); return d ? X.opinions(d, now()) : null; }
  function remView() { var d = B.data(P.rem); return d ? X.reminders(d, now()) : null; }
  function setView() { var d = B.data(P.settings); return d ? X.prepView(d) : null; }

  // —— المربّعات
  function tiles() {
    var n = Kit.count(B, P.news('draft'), function () { var v = newsView('draft'); return v ? { n: ar(v.rows.length), note: v.rows.length ? 'خبر ينتظر مراجعتك' : 'لا أخبار تنتظر', hot: v.rows.length > 0 } : null; });
    var rv = Kit.count(B, P.rev, function () { var v = revView(); return v ? { n: ar(v.rows.length), note: v.rows.length ? 'إعلان ينتظر قرارك' : 'لا إعلانات تنتظر', hot: v.rows.length > 0 } : null; });
    var op = Kit.count(B, P.opps, function () { var v = oppsView(); return v ? { n: ar(v.rows.length), note: v.rows.length ? 'فرصة في القائمة' : 'لا فرص بعد' } : null; });
    var pr = Kit.count(B, P.settings, function () { var v = setView(); return v ? { n: v.url ? 'مضبوط' : 'غير مضبوط', note: 'رابط دورة التحضير', word: true, hot: !v.url } : null; });
    var ot = Kit.count(B, P.ops('pending', ''), function () { var v = opsView('pending', ''); return v ? { n: ar(v.rows.length), note: v.rows.length ? 'رأي ينتظر قرارك' : 'لا آراء تنتظر', hot: v.rows.length > 0 } : null; });
    var rm = Kit.count(B, P.rem, function () { var t = X.reminderTile(remView()); return { n: t.n, note: t.sub, off: t.off, word: t.word, hot: t.hot }; });
    var imp = { n: 'جرّب', note: 'استيراد فرص جاهزة', word: true };
    return [
      Object.assign({ sub: 'news', name: 'أخبار للمراجعة', img: 'content' }, n),
      Object.assign({ sub: 'review', name: 'مراجعة الإعلانات والفرص', img: 'files' }, rv),
      Object.assign({ sub: 'opps', name: 'الفرص', img: 'marketing' }, op),
      Object.assign({ sub: 'import', name: 'استيراد الفرص', img: 'reports' }, imp),
      Object.assign({ sub: 'prep', name: 'رابط دورة التحضير', img: 'courses' }, pr),
      Object.assign({ sub: 'opinions', name: 'الآراء', img: 'people' }, ot),
      Object.assign({ sub: 'reminders', name: 'التذكير', img: 'company' }, rm)
    ];
  }

  // —— ١ · الأخبار
  function screenNews() {
    var st = B.f('newsSt', 'draft'), p = P.news(st);
    B.need(p);
    var d = newsView(st), body;
    var run = '<div class="sh-top"><button type="button" class="ep-b1" data-a="newsrun">شغّل جلب الأخبار</button></div>';
    if (!d) body = B.stateBlock(p, 'الأخبار');
    else if (!d.rows.length) body = B.empty(st === 'draft' ? 'لا أخبار تنتظر مراجعتك' : 'لا أخبار منشورة', st === 'draft' ? 'حين تُجلب أخبار جديدة تظهر هنا مسودات لتقرر فيها' : '');
    else body = '<p class="sh-count">' + esc(d.countText) + '</p>' + B.list(d.rows, [
      { h: 'الخبر', c: function (r) { return '<b class="sh-t">' + esc(r.title) + '</b>' + (r.summary ? '<span class="sh-sub">' + esc(r.summary.length > 140 ? r.summary.slice(0, 140) + '…' : r.summary) + '</span>' : ''); } },
      { h: 'التصنيف', c: function (r) { return esc(r.category) + (r.featured ? ' ' + Kit.pill('مميَّز', 'gold') : ''); } },
      { h: 'المصدر', c: function (r) { return Kit.link(r.sourceUrl, r.source || 'فتح المصدر') || esc(r.source); } },
      { h: 'الحالة', c: function (r) { return Kit.pill(r.statusText) + (r.when ? '<span class="sh-sub">' + esc(r.when) + '</span>' : ''); } }
    ], function (r) {
      return r.published ? '<button type="button" class="ep-b2" data-a="newsedit" data-id="' + esc(r.id) + '">عدّل</button><button type="button" class="ep-bs" data-a="newsun" data-id="' + esc(r.id) + '">ألغِ النشر</button>'
        : '<button type="button" class="ep-b1" data-a="newsapprove" data-id="' + esc(r.id) + '">راجع واعتمد</button>';
    });
    return { title: 'أخبار للمراجعة', sub: d ? d.countText : '', img: 'content', html: run + B.chips('newsSt', X.NEWS_CHIPS, st) + body };
  }
  function newsFormHtml(r) {
    return function (v) {
      v = v || {};
      return '<div class="sh-ro-box"><b>' + esc(r.title) + '</b>' + (r.body ? '<p>' + esc(r.body) + '</p>' : '') + '<p class="sh-sub">' + Kit.link(r.sourceUrl, 'فتح المصدر') + '</p></div>'
        + fld('العنوان', inp('title', v.title, { max: 300 }), 'title') + fld('الملخص', txt('summary', v.summary, 4, 2000), 'summary')
        + fld('التصنيف', sel('category', v.category, X.NEWS_CATS.map(function (c) { return [c, c]; })), 'category')
        + fld('رابط الغلاف', inp('cover_url', v.cover_url, { ltr: true, type: 'url', ph: 'https://' }), 'cover_url') + chk('featured', v.featured, 'خبر مميَّز في الساحة');
    };
  }
  function newsFlow(r, intent) {
    var title = intent === 'approve' ? 'مراجعة الخبر قبل النشر' : 'تعديل الخبر';
    B.flow({ title: title, intro: intent === 'approve' ? 'راجع الخبر وعدّل ما تريد، ثم انتقل لمراجعة ما سيُنشر.' : '', form: newsFormHtml(r), init: X.newsForm(r), check: function (v) { return X.newsCheck(v, r, intent); },
      nextLabel: intent === 'approve' ? 'راجع ثم انشر' : 'راجع ثم احفظ', goLabel: intent === 'approve' ? 'اعتمد ونشر' : 'احفظ التعديل',
      send: function (res) { return B.api('/v2/saha/news/' + encodeURIComponent(r.id), Object.assign({}, res.body, { confirmed: true }), 'PUT'); },
      done: function () { return intent === 'approve' ? 'نُشر الخبر في الساحة' : 'حُفظ تعديل الخبر'; } });
  }
  function newsUnpublish(r) {
    B.flow({ title: 'سحب الخبر من الساحة', check: function () { return X.newsCheck(X.newsForm(r), r, 'unpublish'); }, goLabel: 'ألغِ النشر',
      send: function (res) { return B.api('/v2/saha/news/' + encodeURIComponent(r.id), Object.assign({}, res.body, { confirmed: true }), 'PUT'); }, done: function () { return 'سُحب الخبر من الساحة وعاد مسودة'; } });
  }
  function newsRun() {
    B.flow({ title: 'جلب أخبار جديدة', intro: 'ستجلب المنصة أخبارًا جديدة من مصادرها وتصوغها مسودات تنتظر مراجعتك، ولا يُنشر منها شيء قبل اعتمادك. قد يستغرق ذلك دقيقة.',
      form: function (v) { return fld('عدد الأخبار لكل بلد', sel('limit', (v || {}).limit || '', [1, 2, 3, 4, 5, 6, 7, 8].map(function (n) { return [String(n), ar(n)]; }), 'كما تحدده المنصة'), 'limit'); },
      init: { limit: '' }, check: function (v) { var r = X.newsRunCheck(v); if (r.ok) { r.lead = 'ستبدأ المنصة جلب الأخبار الآن:'; r.goLabel = 'ابدأ الجلب'; } return r; }, nextLabel: 'راجع ثم ابدأ',
      send: function (res) { return B.api('/v2/saha/news/run', Object.assign({}, res.body, { confirmed: true })); }, done: function (out) { return X.newsRunDone(out); } });
  }

  // —— ٢ · الفرص: طابور المراجعة
  function oppCard(r, queue) {
    var facts = [r.kindText, r.provider, r.place, r.countryText].filter(Boolean).join('، ');
    return '<li class="sh-card big" data-id="' + esc(r.id) + '"><div class="sh-ch"><h3>' + esc(r.title) + '</h3>' + Kit.pill(r.reviewText, r.pending ? 'gold' : '') + '</div>'
      + (facts ? '<p class="sh-meta"><span>' + esc(facts) + '</span></p>' : '')
      + (r.deadlineText ? '<p class="sh-meta"><b>الموعد</b><span>' + esc(r.deadlineText) + '</span></p>' : '')
      + (r.covers ? '<p class="sh-meta"><b>تغطي</b><span>' + esc(r.covers) + '</span></p>' : '')
      + (r.eligibility.length ? '<ul class="sh-elig">' + r.eligibility.map(function (e) { return '<li>' + esc(e) + '</li>'; }).join('') + '</ul>' : '')
      + '<p class="sh-meta">' + (Kit.link(r.officialUrl, 'فتح الرابط الرسمي') || '<span class="sh-sub">لا رابط رسمي</span>') + (r.submittedBy ? Kit.who(r.submittedBy) : '') + (r.when ? '<span>' + esc(r.when) + '</span>' : '') + '</p>'
      + (queue ? '<div class="sh-acts"><button type="button" class="ep-b1" data-a="oppapprove" data-id="' + esc(r.id) + '">اعتمد ونشر</button><button type="button" class="ep-b2" data-a="oppreject" data-id="' + esc(r.id) + '">ارفض</button>'
        + '<button type="button" class="ep-bs" data-a="oppedit" data-id="' + esc(r.id) + '">عدّل</button></div>' : '') + '</li>';
  }
  function screenReview() {
    B.need(P.rev);
    var chip = B.f('revKind', 'all'), d = revView(), body;
    if (!d) body = B.stateBlock(P.rev, 'الإعلانات');
    else {
      var rows = X.oppFilter(d.rows, chip);
      body = !d.rows.length ? B.empty('لا إعلانات تنتظر', 'حين يرسل أحد إعلانًا أو فرصة تظهر هنا لتقرر فيها')
        : !rows.length ? B.empty('لا إعلانات من هذا النوع', 'جرّب نوعًا آخر أو اختر «الكل»')
        : '<p class="sh-count">' + esc(X.pendingText(rows.length)) + '</p><ul class="sh-cards big">' + rows.map(function (r) { return oppCard(r, true); }).join('') + '</ul>';
    }
    return { title: 'مراجعة الإعلانات والفرص', sub: d ? X.pendingText(d.rows.length) : '', img: 'files', html: B.chips('revKind', X.KIND_CHIPS, chip) + body };
  }
  function decideFlow(r, decision) {
    var rej = decision === 'reject';
    B.flow({ title: rej ? 'رفض الإعلان' : 'اعتماد الإعلان', intro: rej ? 'اكتب سبب الرفض، ويُحفظ مع القرار.' : '',
      form: rej ? function (v) { return fld('سبب الرفض', txt('reason', (v || {}).reason, 3, 140), 'reason', 'حتى ١٤٠ حرفًا'); } : null, init: { reason: '' }, nextLabel: 'راجع ثم ارفض',
      check: function (v) { var x = X.oppDecision(decision, v.reason, r); if (x.ok) x.lines = x.lines || []; return x; },
      send: function (res) { return B.api('/v2/saha/opportunities/' + encodeURIComponent(r.id) + '/decide', Object.assign({}, res.body, { confirmed: true })); },
      done: function () { return X.oppDone(decision); } });
  }

  // —— ٢ · الفرص: القائمة والنموذج الكامل
  function screenOpps() {
    B.need(P.opps);
    var st = B.f('oppSt', 'all'), kd = B.f('oppKind', 'all'), d = oppsView(), body;
    if (!d) body = B.stateBlock(P.opps, 'الفرص');
    else {
      var rows = X.oppFilter(d.rows, kd).filter(function (r) { return st === 'all' || r.review === st; });
      body = !d.rows.length ? B.empty('لا فرص بعد', 'أضف أول فرصة من الزرّ فوق، أو استورد فرصًا جاهزة')
        : !rows.length ? B.empty('لا فرص تطابق هذا الاختيار', 'غيّر الحالة أو النوع')
        : '<p class="sh-count">' + esc(X.oppCountText(rows.length)) + '</p>' + B.list(rows, [
          { h: 'الفرصة', c: function (r) { return '<b class="sh-t">' + esc(r.title) + '</b>' + (r.provider ? '<span class="sh-sub">' + esc(r.provider) + '</span>' : ''); } },
          { h: 'النوع', c: function (r) { return esc(r.kindText); } },
          { h: 'الموعد', c: function (r) { return esc(r.deadlineText); } },
          { h: 'الحالة', c: function (r) { return Kit.pill(r.reviewText, r.pending ? 'gold' : '') + (r.featured ? ' ' + Kit.pill('مميَّزة', 'gold') : ''); } }
        ], function (r) { return '<button type="button" class="ep-b2" data-a="oppedit" data-id="' + esc(r.id) + '">عدّل</button>'; });
    }
    return { title: 'الفرص', sub: d ? X.oppCountText(d.rows.length) : '', img: 'marketing',
      html: '<div class="sh-top"><button type="button" class="ep-b1" data-a="oppnew">فرصة جديدة</button></div>' + B.chips('oppSt', X.OPP_STATUS_CHIPS, st) + B.chips('oppKind', X.KIND_CHIPS, kd) + body };
  }
  function oppFormHtml(create) {
    return function (v) {
      v = v || {};
      var kinds = X.OPP_KINDS.map(function (k) { return [k[0], k[1]]; });
      var cn = X.COUNTRIES.concat([[X.OTHER, 'أخرى']]);
      return fld('نوع الفرصة', sel('kind', v.kind, kinds, create ? 'اختر النوع' : null), 'kind')
        + fld('النشر', sel('publish', v.publish, [['published', 'منشورة'], ['draft', 'مسودة']], create ? 'اختر: نشر أو مسودة' : 'كما هي'), 'publish')
        + fld('العنوان', inp('title', v.title, { max: 200 }), 'title')
        + fld('الرابط الرسمي', inp('official_url', v.official_url, { ltr: true, type: 'url', ph: 'https://' }), 'official_url')
        + fld('الجهة المنظِّمة', inp('provider', v.provider, { max: 200 }), 'provider') + fld('المكان', inp('place', v.place, { max: 200 }), 'place')
        + fld('البلد', sel('country', v.country, cn, 'غير محدد'), 'country')
        + '<div class="fld" id="shCountryOther"' + (v.country === X.OTHER ? '' : ' hidden') + '><label for="f_country_other">رمز البلد (حرفان)</label>' + inp('country_other', v.country_other, { max: 2, ltr: true, ph: 'مثل JP' }) + '<small class="ferr" data-e="country_other" role="alert"></small></div>'
        + fld('اللغة', sel('language', v.language, X.LANGS, 'غير محددة'), 'language') + fld('التمويل', sel('funding', v.funding, X.FUNDS, 'غير محدد'), 'funding')
        + fld('آخر موعد', inp('deadline', v.deadline, { type: 'date', ltr: true }), 'deadline') + fld('نص الموعد (اختياري)', inp('deadline_text', v.deadline_text, { max: 80 }), 'deadline_text')
        + fld('ما تغطيه', inp('covers_ar', v.covers_ar, { max: 300 }), 'covers_ar') + fld('الشروط (كل شرط في سطر، حتى ٨)', txt('eligibility', v.eligibility, 4), 'eligibility')
        + fld('رابط الصورة', inp('image', v.image, { ltr: true, type: 'url', ph: 'https://' }), 'image') + chk('featured', v.featured, 'فرصة مميَّزة في الساحة')
        + '<details class="sh-more"><summary>تفاصيل أخرى</summary>'
        + fld('العنوان بالإنجليزية', inp('title_en', v.title_en, { max: 200, ltr: true }), 'title_en') + fld('جهة العمل', inp('employer', v.employer, { max: 200 }), 'employer')
        + fld('نوع الدوام', inp('employment_type', v.employment_type, { max: 40 }), 'employment_type') + fld('التخصص', inp('specialty', v.specialty, { max: 80 }), 'specialty')
        + fld('رابط المصدر', inp('source_url', v.source_url, { ltr: true, type: 'url', ph: 'https://' }), 'source_url') + fld('اسم المصدر', inp('source_name', v.source_name, { max: 80 }), 'source_name')
        + fld('تسمية المصدر', inp('source_label', v.source_label, { max: 40 }), 'source_label') + fld('تاريخ التحقق', inp('verified_at', v.verified_at, { type: 'date', ltr: true }), 'verified_at')
        + fld('حرف الشعار', inp('logo_initial', v.logo_initial, { max: 2 }), 'logo_initial') + fld('الوصف', txt('body', v.body, 5, 5000), 'body')
        + (create ? fld('مدة الإعلان بالأيام (اختياري)', inp('expires_in_days', v.expires_in_days, { mode: 'numeric', max: 3 }), 'expires_in_days') : '') + '</details>';
    };
  }
  function oppFlow(r) {
    var create = !r;
    B.flow({ title: create ? 'فرصة جديدة' : 'تعديل الفرصة', form: oppFormHtml(create), init: X.oppForm(r), check: function (v) { return X.oppCheck(v, create ? 'create' : 'edit', r); },
      nextLabel: 'راجع ثم احفظ', goLabel: 'احفظ',
      hook: function (c) {
        var cs = q1('#f_country', c.root), box = q1('#shCountryOther', c.root);
        if (cs && box) cs.onchange = function () { box.hidden = cs.value !== X.OTHER; };
      },
      // الوظائف تُقفل ولا تُحذف (المنصة ترفض حذفها دائمًا) فلا يُعرض زر الحذف لها
      extra: create || r.isJob ? [] : [{ id: 'shDel', label: 'احذف الفرصة', run: function () { window.closeModal(); deleteFlow(r); } }],
      send: function (res) {
        return create ? B.api('/v2/saha/opportunities', Object.assign({}, res.body, { confirmed: true })) : B.api('/v2/saha/opportunities/' + encodeURIComponent(r.id), Object.assign({}, res.body, { confirmed: true }), 'PUT');
      },
      done: function (out) { return X.oppDone(create ? 'create' : 'edit', out); } });
  }
  function deleteFlow(r) {
    B.flow({ title: 'حذف الفرصة', check: function () { return { ok: true, lead: 'ستُحذف الفرصة «' + r.title + '» نهائيًا.', lines: [], goLabel: 'احذف الفرصة' }; },
      send: function () { return B.api('/v2/saha/opportunities/' + encodeURIComponent(r.id), { confirmed: true }, 'DELETE'); }, done: function () { return X.oppDone('remove'); } });
  }

  // —— ٣ · رابط دورة التحضير
  function screenPrep() {
    B.need(P.settings);
    var d = setView(), body;
    if (!d) body = B.stateBlock(P.settings, 'الرابط');
    else {
      var typed = B.f('prepUrl', d.url);
      body = '<div class="sh-panel"><p class="sh-fine">يظهر هذا الرابط زرًّا «جهّز طلبك بالإنجليزية» بجانب فرص المنح والزمالات.</p>'
        + '<p class="sh-cur"><b>الرابط الحالي</b>' + (d.url ? Kit.link(d.url, d.url) : '<span class="sh-sub">لا يوجد رابط بعد</span>') + '</p>'
        + '<div class="sh-sbox"><label for="shPrep">رابط الدورة</label><div class="sh-row"><input id="shPrep" type="url" dir="ltr" maxlength="2000" autocomplete="off" placeholder="https://" value="' + esc(typed) + '">'
        + '<button type="button" class="ep-b1" data-a="prepsave">راجع ثم احفظ</button></div></div>'
        + (d.url ? '<div class="sh-acts"><button type="button" class="ep-bs" data-a="prepclear">امسح الرابط</button></div>' : '') + '<div id="shPrepErr" role="alert"></div></div>';
    }
    return { title: 'رابط دورة التحضير', sub: d ? (d.url ? 'الرابط مضبوط' : 'لم يُضبط بعد') : '', img: 'courses', html: body, after: function (v) {
      var i = q1('#shPrep', v);
      if (i) {
        i.addEventListener('input', function () { B.set('prepUrl', i.value); });
        i.addEventListener('keydown', function (e) { if (e.key === 'Enter') { e.preventDefault(); B.set('prepUrl', i.value); prepFlow(false); } });
      }
    } };
  }
  function prepFlow(clear) {
    var d = setView(), inpEl = q1('#shPrep'), err = q1('#shPrepErr');
    var res = X.prepCheck(inpEl ? inpEl.value : '', d ? d.url : '', clear);
    if (!res.ok) { if (err) err.innerHTML = '<div class="sh-err" role="alert">' + esc(res.error) + '</div>'; return; }
    if (err) err.innerHTML = '';
    B.flow({ title: clear ? 'مسح رابط الدورة' : 'حفظ رابط الدورة', check: function () { return { ok: true, lead: res.lead, lines: res.lines, goLabel: clear ? 'امسح الرابط' : 'احفظ الرابط' }; },
      send: function () { return B.api('/v2/saha/settings', { prep_course_url: res.url, confirmed: true }, 'PUT'); },
      done: function () { return clear ? 'مُسح رابط دورة التحضير' : 'حُفظ رابط دورة التحضير'; }, after: function () { B.set('prepUrl', undefined); } });
  }

  // —— ٤ · استيراد الفرص (تجربة بلا حفظ ثم تأكيد)
  function seedBody() { var f = B.f('seedFile', null); return f ? { seed: f.obj } : {}; }
  function screenImport() {
    var prev = B.f('seedPrev', null), file = B.f('seedFile', null), busy = B.f('seedBusy', false), err = B.f('seedErr', ''), v = prev ? X.seedView(prev) : null;
    var html = '<div class="sh-panel"><p class="sh-fine">يستورد فرصًا جاهزة إلى الساحة. جرّب أولًا لترى ما سيحدث بلا أن يُحفظ شيء، ثم أكِّد الاستيراد.</p>'
      + '<div class="sh-sbox"><span class="sh-flabel">ملف الفرص (اختياري، وإلا استُعمل ملف المنصة نفسه)</span><label class="ep-bs sh-filebtn"><input id="shSeedFile" class="sh-fileinp" type="file" accept=".json,application/json">' + (file ? 'اختر ملفًا آخر' : 'اختر ملفًا') + '</label></div>'
      + (file ? '<p class="sh-cur"><b>الملف المختار</b><span>' + esc(file.name) + '، ' + esc(U.U(file.count, ['فرصة واحدة', 'فرصتان', 'فرص', 'فرصة'])) + '</span><button type="button" class="ep-bs" data-a="seedclear">اختر ملف المنصة بدلًا منه</button></p>' : '')
      + '<div class="sh-acts"><button type="button" class="ep-b1" data-a="seedprev"' + (busy ? ' disabled' : '') + '>' + (busy ? 'جارٍ التجربة…' : 'جرّب الاستيراد (بلا حفظ)') + '</button></div>'
      + (err ? '<div class="sh-err" role="alert">' + esc(err) + '</div>' : '') + '</div>';
    if (v) {
      html += '<div class="sh-panel" data-r="seed"><h3>نتيجة التجربة</h3><p class="sh-fine">لم يُحفظ شيء بعد.</p><ul class="sh-nums">' + v.rows.map(function (r) { return '<li><b>' + esc(ar(r.n)) + '</b><span>' + esc(r.label) + '</span></li>'; }).join('') + '</ul>'
        + (v.warnings.length ? '<div class="sh-warns"><b>تنبيهات (' + esc(ar(v.warnings.length)) + ')</b><ul>' + v.warnings.slice(0, 20).map(function (w) { return '<li>' + esc(w) + '</li>'; }).join('') + '</ul>' + (v.warnings.length > 20 ? '<p class="sh-fine">والباقي مخفي هنا.</p>' : '') + '</div>' : '')
        + '<div class="sh-acts"><button type="button" class="ep-b1" data-a="seedgo"' + (v.changes ? '' : ' disabled') + '>راجع ثم استورد</button>' + (v.changes ? '' : '<span class="sh-fine">لا شيء جديد يُستورد.</span>') + '</div></div>';
    }
    return { title: 'استيراد الفرص', sub: 'جرّب أولًا ثم أكِّد', img: 'reports', html: html, after: function (vw) {
      var fi = q1('#shSeedFile', vw);
      if (fi) fi.onchange = function () {
        var f = fi.files && fi.files[0];
        if (!f) return;
        var rd = new FileReader();
        rd.onload = function () {
          var obj = null;
          try { obj = JSON.parse(String(rd.result)); } catch (e) { obj = null; }
          var ck = X.seedCheck(obj);
          if (!ck.ok) { B.set('seedErr', obj === null ? 'تعذّرت قراءة الملف، اختر ملفًا صحيحًا' : ck.error); B.set('seedFile', null); }
          else { B.set('seedErr', ''); B.set('seedFile', { name: f.name, obj: obj, count: ck.count }); }
          B.set('seedPrev', null); B.redraw();
        };
        rd.onerror = function () { B.set('seedErr', 'تعذّرت قراءة الملف'); B.redraw(); };
        rd.readAsText(f);
      };
    } };
  }
  function seedPreview() {
    if (B.f('seedBusy', false)) return;
    B.set('seedBusy', true); B.set('seedErr', ''); B.redraw();
    B.api('/v2/saha/opportunities/seed/preview', seedBody()).then(function (d) { B.set('seedBusy', false); B.set('seedPrev', d); B.redraw(); })
      .catch(function (e) { B.set('seedBusy', false); B.set('seedPrev', null); B.set('seedErr', X.writeError(e && e.status, e && e.data)); B.redraw(); });
  }
  function seedFlow() {
    var v = X.seedView(B.f('seedPrev', null));
    if (!v) return;
    B.flow({ title: 'تأكيد الاستيراد', check: function () {
        return { ok: true, lead: 'سيُستورد الآن ما رأيته في التجربة، وتظهر الفرص الجديدة في الساحة:', goLabel: 'استورد الفرص',
                 lines: v.rows.map(function (r) { return { label: r.label, to: ar(r.n) }; }), warns: v.warnings.length ? [U.U(v.warnings.length, ['تنبيه واحد', 'تنبيهان', 'تنبيهات', 'تنبيهًا']) + ' ظهرت في التجربة'] : [] };
      },
      send: function () { return B.api('/v2/saha/opportunities/seed/import', Object.assign({}, seedBody(), { confirmed: true })); },
      done: function (out) { return X.seedDone(X.seedView(out)); }, after: function () { B.set('seedPrev', null); B.set('seedFile', null); } });
  }

  // —— ٥ · الآراء
  function screenOpinions() {
    var st = B.f('opSt', 'pending'), topic = B.f('opTopic', ''), p = P.ops(st, topic);
    B.need(p); B.need(P.topics);
    var d = opsView(st, topic), tp = B.data(P.topics) ? X.topics(B.data(P.topics)) : null, body;
    var picker = tp ? '<div class="sh-sbox"><label for="shTopic">النقاش</label><select id="shTopic"><option value="">كل النقاشات</option>' + tp.rows.map(function (r) {
      return '<option value="' + esc(r.id) + '"' + (r.id === topic ? ' selected' : '') + '>' + esc(r.title) + '</option>';
    }).join('') + '</select></div>' : '';
    if (!d) body = B.stateBlock(p, 'الآراء');
    else if (!d.rows.length) body = B.empty(st === 'pending' ? 'لا آراء تنتظر قرارك' : 'لا آراء هنا', 'تظهر هنا الآراء حين يكتبها الأعضاء');
    else body = '<p class="sh-count">' + esc(d.countText) + '</p>' + B.list(d.rows, [
      { h: 'الرأي', c: function (r) { return '<span class="sh-body">' + esc(r.body.length > 280 ? r.body.slice(0, 280) + '…' : r.body) + '</span>'; } },
      { h: 'الكاتب', c: function (r) { return esc(r.authorText) + Kit.who(r.author); } },
      { h: 'النقاش', c: function (r) { return esc(r.topic); } },
      { h: 'الحالة', c: function (r) { return Kit.pill(r.statusText, r.status === 'rejected' ? 'mute' : '') + (r.when ? '<span class="sh-sub">' + esc(r.when) + '</span>' : ''); } }
    ], function (r) {
      return (r.canShow ? '<button type="button" class="ep-b2" data-a="opshow" data-id="' + esc(r.id) + '">' + esc(r.showLabel) + '</button>' : '')
        + (r.canHide ? '<button type="button" class="ep-b2" data-a="ophide" data-id="' + esc(r.id) + '">أخفِ</button>' : '');
    });
    return { title: 'الآراء', sub: d ? d.countText : '', img: 'people', html: B.chips('opSt', X.OP_CHIPS, st) + picker + body, after: function (v) {
      var t = q1('#shTopic', v); if (t) t.onchange = function () { B.set('opTopic', t.value); B.redraw(); };
    } };
  }
  function opinionFlow(r, kind) {
    var a = X.opinionAction(kind, r);
    B.flow({ title: kind === 'hide' ? 'إخفاء الرأي' : 'إظهار الرأي', check: function () { return { ok: true, lead: a.lead, goLabel: a.goLabel, lines: [{ label: 'الرأي', to: r.body.length > 160 ? r.body.slice(0, 160) + '…' : r.body }, { label: 'الكاتب', to: r.author || r.authorText }] }; },
      send: function () { return B.api('/v2/saha/opinions/' + encodeURIComponent(r.id) + '/' + (kind === 'hide' ? 'hide' : 'restore'), { confirmed: true }); }, done: function () { return a.done; } });
  }

  // —— ٦ · التذكير
  function screenReminders() {
    B.need(P.rem);
    var v = remView(), body;
    if (!v) body = B.stateBlock(P.rem, 'حالة التذكير');
    else {
      var stCls = v.kind === 'locked' ? 'mute' : v.kind === 'failed' ? 'red' : v.kind === 'ok' ? 'green' : 'gold';
      body = '<div class="sh-panel"><div class="sh-stat"><b class="sh-big ' + stCls + '">' + esc(v.headline) + '</b>' + (v.when ? '<span class="sh-sub">آخر تشغيل: ' + esc(v.when) + '</span>' : '') + '</div><p class="sh-fine">' + esc(v.detail) + '</p>'
        + (v.rows.length ? '<ul class="sh-nums">' + v.rows.map(function (r) { return '<li><b>' + esc(ar(r.n)) + '</b><span>' + esc(r.label) + '</span></li>'; }).join('') + '</ul>' : '')
        + '<div class="sh-acts"><button type="button" class="ep-b1" data-a="remrun">شغّل الآن</button></div></div>';
    }
    return { title: 'التذكير', sub: 'قبل موعد الفرصة بثلاثة أيام وبيوم', img: 'company', html: body };
  }
  function remFlow() {
    B.flow({ title: 'تشغيل التذكير الآن', check: function () {
        return { ok: true, lead: 'سيُرسَل الآن تذكير بالفرص التي يقترب موعدها لمن طلبوه (قبل الموعد بثلاثة أيام وبيوم). لو كان التذكير مقفولًا من المنصة فلن يُرسَل شيء.', goLabel: 'شغّل التذكير', lines: [] };
      },
      send: function () { return B.api('/v2/saha/reminders/run', { confirmed: true }); }, done: function (out) { return X.reminderRunDone(out); } });
  }

  // ------------------------------------------------------------------ التسجيل
  B = Kit.board({
    key: 'saha', mod: 'v2s_saha', label: 'الساحة', lead: 'اختر ما تريد إدارته في الساحة',
    hub: function () { return HUB; }, tiles: tiles,
    screens: { news: screenNews, review: screenReview, opps: screenOpps, import: screenImport, prep: screenPrep, opinions: screenOpinions, reminders: screenReminders },
    act: {
      newsrun: function () { newsRun(); },
      newsapprove: function (b, a, id) { var r = row((newsView(b.f('newsSt', 'draft')) || {}).rows, id); if (r) newsFlow(r, 'approve'); },
      newsedit: function (b, a, id) { var r = row((newsView(b.f('newsSt', 'draft')) || {}).rows, id); if (r) newsFlow(r, 'edit'); },
      newsun: function (b, a, id) { var r = row((newsView(b.f('newsSt', 'draft')) || {}).rows, id); if (r) newsUnpublish(r); },
      oppapprove: function (b, a, id) { var r = row((revView() || {}).rows, id); if (r) decideFlow(r, 'approve'); },
      oppreject: function (b, a, id) { var r = row((revView() || {}).rows, id); if (r) decideFlow(r, 'reject'); },
      oppedit: function (b, a, id) { var r = row((oppsView() || {}).rows, id) || row((revView() || {}).rows, id); if (r) oppFlow(r); },
      oppnew: function () { oppFlow(null); },
      prepsave: function () { prepFlow(false); },
      prepclear: function () { prepFlow(true); },
      seedprev: seedPreview,
      seedgo: seedFlow,
      seedclear: function (b) { b.set('seedFile', null); b.set('seedPrev', null); b.redraw(); },
      ophide: function (b, a, id) { var r = row((opsView(b.f('opSt', 'pending'), b.f('opTopic', '')) || {}).rows, id); if (r) opinionFlow(r, 'hide'); },
      opshow: function (b, a, id) { var r = row((opsView(b.f('opSt', 'pending'), b.f('opTopic', '')) || {}).rows, id); if (r) opinionFlow(r, 'show'); },
      remrun: function () { remFlow(); }
    }
  });
  window.V2S_SAHA = B;
})();
