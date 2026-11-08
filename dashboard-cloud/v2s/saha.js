/* ============================================================================
 * v2s/saha.js — الجزء الأول: المنطق النقي لمربّعات «الساحة» و«الديوان» في الداشبورد (لا DOM ولا شبكة ولا ساعة خفية؛ `now` يُمرَّر صراحةً).
 *   الساحة:  ١) الأخبار (مسودات تنتظر · منشورة) وتعديلها واعتمادها · ٢) الفرص (قوائم · مراجعة الطابور بالنوع · النموذج الكامل قبل ⇐ بعد)
 *            ٣) رابط دورة التحضير · ٤) استيراد الفرص (تجربة ثم تأكيد) · ٥) الآراء (إخفاء وإظهار) · ٥ب) النقاشات (إخفاء وإرجاع + فحص الصلة بالقانون ثم إخفاء غير المرتبط) · ٦) التذكير (آخر تشغيل).
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
  // R17: ختم حارس الصلة على الخبر (`legal.ok === false`) ⇒ المنشور مخفي فعلًا عن القرّاء، والمسودة صلتها غير واضحة.
  function newsHidden(r) { return !!(r && r.legal && typeof r.legal === 'object' && r.legal.ok === false); }
  function newsHiddenText(r) {
    if (!newsHidden(r)) return '';
    if (r.legal.by === 'human') return 'مخفي يدويًا';
    return r.status === 'published' ? 'مخفي لعدم الصلة بالقانون' : 'صلته بالقانون غير واضحة';
  }
  function news(resp, now) {
    var list = items(resp);
    if (!list) return null;
    var rows = list.map(function (r) {
      var rp = r.related_product && typeof r.related_product === 'object' ? r.related_product : null;
      return { id: String(r.id), title: str(r.title) || 'خبر بلا عنوان', summary: str(r.summary), body: short(r.body, 700), source: str(r.source_name), sourceUrl: httpUrl(r.source_url),
               country: str(r.country), category: str(r.category) || 'أخرى', featured: r.featured === true, cover: httpUrl(r.cover_url), published: r.status === 'published',
               statusText: r.status === 'published' ? 'منشور' : 'مسودة', when: when(r.published_at || r.created_at, now), ts: ms(r.created_at), product: rp ? str(rp.label) : '',
               hasTopic: !!str(r.topic_id), extra: Array.isArray(r.extra_sources) ? r.extra_sources.length : 0,
               hidden: newsHidden(r), hiddenText: newsHiddenText(r) };
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
    if (intent === 'restore') {
      body.status = 'published';
      return { ok: true, body: body, lines: [{ label: 'الظهور', from: 'مخفي', to: 'ظاهر للقرّاء' }], errors: {},
               lead: 'سيظهر الخبر «' + row.title + '» للقرّاء في الساحة مرة أخرى:' };
    }
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
    var held = res && isNum(res.total_held_for_review) ? res.total_held_for_review : 0;
    var heldText = held ? U(held, ['خبر واحد', 'خبران', 'أخبار', 'خبرًا']) + ' صلته بالقانون غير واضحة ينتظر قرارك' : '';
    if (!total && !held) return 'اكتمل الجلب، ولم تُضَف مسودات جديدة';
    if (!total) return 'اكتمل الجلب، وأُضيف ' + heldText;
    return 'أُضيفت ' + U(total, ['مسودة واحدة', 'مسودتان', 'مسودات', 'مسودة']) + ' تنتظر مراجعتك' + (held ? '، ومعها ' + heldText : '');
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
  // ------------------------------------------------------------------ ٥ب · النقاشات (إخفاء وإرجاع) والصلة بالقانون (R17)
  var TOPIC_CHIPS = [['open', 'المفتوحة'], ['hidden', 'المخفية']];
  var TOPIC_STATUS_TEXT = { open: 'مفتوح', published: 'منشور', draft: 'مسودة', pending_review: 'ينتظر المراجعة', merged: 'مدموج', rejected: 'مرفوض', archived: 'مؤرشف' };
  var GATE_LABELS = [['news', 'الأخبار'], ['topics', 'النقاشات'], ['articles', 'المقالات']];
  var GATE_REASONS = { 'off-theme': 'لا يتناول موضوعًا قانونيًا', negative: 'حوادث أو سياسة أو منوّعات', 'weak-legal-signal': 'صلته بالقانون ضعيفة',
                       'no-pillar': 'خارج مجالات المنصة' };
  function gateReason(r) { return GATE_REASONS[str(r)] || 'غير مرتبط بالقانون'; }
  function topics(resp) {
    var list = items(resp);
    if (!list) return null;
    var rows = list.map(function (r) {
      var lg = r.legal && typeof r.legal === 'object' ? r.legal : null, hidden = !!(lg && lg.ok === false), st = str(r.status);
      return { id: String(r.id), title: str(r.title) || 'نقاش بلا عنوان', status: st, statusText: TOPIC_STATUS_TEXT[st] || 'حالة غير معروفة',
               hidden: hidden, hiddenText: hidden ? (lg.by === 'human' ? 'مخفي يدويًا' : 'مخفي لعدم الصلة بالقانون') : '',
               opinions: isNum(r.opinions_count) ? r.opinions_count : null };
    });
    var n = rows.length;
    return { rows: rows, hiddenCount: rows.filter(function (r) { return r.hidden; }).length,
             countText: n ? U(n, ['نقاش واحد', 'نقاشان', 'نقاشات', 'نقاشًا']) : 'لا نقاشات هنا' };
  }
  function topicAction(kind) {
    if (kind === 'hide') return { lead: 'سيختفي هذا النقاش من الساحة وعدّاداتها، وتبقى آراؤه محفوظة ويمكن إرجاعه في أي وقت:', goLabel: 'أخفِ النقاش', done: 'أُخفي النقاش' };
    return { lead: 'سيرجع هذا النقاش إلى الساحة كما كان:', goLabel: 'أرجِع النقاش', done: 'رجع النقاش إلى الساحة' };
  }
  // رد الفحص/الإخفاء ⇒ {rows: [{id, kind, title, reason}], counts: [{key, label, n}], failed: [تسميات]، total، listed، applied، totalText} أو null
  // بعد الإخفاء: العدد = ما اتعلّم عليه فعلًا (غير المرتبط ناقص اللي اتشال من الاختيار).
  function gateView(resp) {
    if (!resp || typeof resp !== 'object' || !resp.collections || typeof resp.collections !== 'object') return null;
    var rows = [], counts = [], failed = [];
    GATE_LABELS.forEach(function (g) {
      var c = resp.collections[g[0]];
      if (!c || typeof c !== 'object') { failed.push(g[1]); return; }
      var n = isNum(c.would_hide) ? c.would_hide : 0;
      if (resp.applied === true && isNum(c.skipped_unselected)) n = Math.max(0, n - c.skipped_unselected);
      counts.push({ key: g[0], label: g[1], n: n });
      (Array.isArray(c.hidden) ? c.hidden : []).forEach(function (h) {
        if (h && typeof h === 'object' && str(String(h.id == null ? '' : h.id))) rows.push({ id: String(h.id), kind: g[1], title: str(h.title) || 'بلا عنوان', reason: gateReason(h.reason) });
      });
    });
    if (!counts.length) return null;            // ولا مجموعة اتفحصت ⇒ مفيش نتيجة (مش «كله مرتبط»)
    var total = counts.reduce(function (a, c) { return a + c.n; }, 0);
    return { rows: rows, counts: counts, failed: failed, total: total, listed: rows.length, applied: resp.applied === true,
             totalText: total ? U(total, ['عنصر واحد غير مرتبط بالقانون', 'عنصران غير مرتبطين بالقانون', 'عناصر غير مرتبطة بالقانون', 'عنصرًا غير مرتبط بالقانون'])
               : (failed.length ? 'لا شيء غير مرتبط بالقانون فيما أمكن فحصه' : 'كل ما فُحص مرتبط بالقانون') };
  }
  // الاختيار من نتيجة الفحص: كل المعروض متعلَّم عليه إلا اللي اتشال (`off` = {id: true})
  function gatePicked(v, off) {
    off = off && typeof off === 'object' ? off : {};
    return (v && v.rows ? v.rows : []).filter(function (r) { return !off[r.id]; }).map(function (r) { return r.id; });
  }
  function gateDone(v) {
    if (!v) return 'اكتمل الإخفاء';
    return v.total ? 'أُخفي ' + U(v.total, ['عنصر واحد', 'عنصران', 'عناصر', 'عنصرًا']) + ' من الساحة، ويمكن إرجاع أي نقاش منها' : 'لم يكن هناك ما يُخفى';
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

  // ------------------------------------------------------------------ ٦ب · محرّك الفرص (R18): التشغيل اليومي · آخر تشغيل · المراجعة · المصادر · إيميل الأسبوع
  var ENG_CHIPS = [['run', 'التشغيل'], ['review', 'للمراجعة'], ['sources', 'المصادر'], ['digest', 'إيميل الأسبوع']];
  var ENG_SRC_TEXT = { settings: 'مضبوط من هنا', env: 'مضبوط من إعدادات الخادم', 'default': 'الوضع الأول (مقفول)' };
  var DAY_TEXT = { sat: 'سبت', sun: 'أحد', mon: 'اثنين', tue: 'ثلاثاء', wed: 'أربعاء', thu: 'خميس', fri: 'جمعة' };
  var ENG_RUN_ROWS = [['fetched', 'جُلبت من المصادر'], ['published', 'نُشرت مباشرة'], ['drafts', 'مسودات للمراجعة'], ['errors', 'أعطال']];
  // رموز المنصة نفسها (`opp_digest.send_test` و`preview`) — رمز مجهول ⇒ نص عام.
  var TEST_REASONS = { 'no-brevo-key': 'مفتاح خدمة البريد غير مضبوط على المنصة، والتفاصيل في الشركة ← الإعدادات ← فحص الإعدادات',
                       'no-items': 'لا فرص جديدة هذا الأسبوع في أي مسار، فلا شيء يُرسل',
                       'brevo-rejected': 'خدمة البريد رفضت الإرسال، وغالبًا السبب عنوان الإرسال أو المفتاح (فحص الإعدادات في الشركة ← الإعدادات)',
                       'bad-email': 'البريد الإلكتروني غير صحيح', unsubscribed: 'صاحب هذا البريد أوقف رسائل المنصة' };
  var PREVIEW_REASONS = { 'no-user': 'هذا البريد ليس لعضو على المنصة', 'no-track': 'صاحب هذا البريد لم يختر مسارًا بعد، فلن تصله الرسالة',
                          'no-items': 'لا فرص جديدة في مسار صاحب هذا البريد هذا الأسبوع، فلن تصله رسالة',
                          unsubscribed: 'صاحب هذا البريد أوقف رسائل المنصة، فلن تصله الرسالة', pending: 'الحساب ينتظر فتح الدخول، فلن تصله الرسالة',
                          inactive: 'الحساب موقوف، فلن تصله الرسالة', 'test-account': 'هذا حساب تجريبي، فلن تصله الرسالة' };
  function hourText(h) {
    if (!isNum(h) || h < 0 || h > 23) return '';
    if (h === 0) return '١٢ منتصف الليل';
    if (h < 12) return ar(h) + ' صباحًا';
    if (h === 12) return '١٢ ظهرًا';
    return ar(h - 12) + ' مساءً';
  }
  function hoursList(s) { return str(s).split(',').filter(function (p) { return /^\d{1,2}$/.test(p) && +p <= 23; }).map(Number); }
  function hoursText(s) {
    var hs = hoursList(s);
    if (!hs.length) return '';
    var t = hs.map(hourText);
    return t.length === 1 ? t[0] : t.slice(0, -1).join('، ') + ' و' + t[t.length - 1];
  }
  // آخر تشغيل ⇒ {when, rows: [{key, label, n}], errors, failed, busy, headline} أو null لو مفيش تشغيل.
  function engRun(r, now) {
    if (!r || typeof r !== 'object') return null;
    var rows = ENG_RUN_ROWS.map(function (x) { return { key: x[0], label: x[1], n: isNum(r[x[0]]) ? r[x[0]] : 0 }; });
    var errors = isNum(r.errors) ? r.errors : 0;
    var headline = r.busy ? 'كان هناك تشغيل آخر يعمل' : r.failed ? 'تعذّر آخر تشغيل' : errors ? 'اكتمل آخر تشغيل وفيه أعطال' : 'اكتمل آخر تشغيل';
    return { when: when(r.at, now), rows: rows, errors: errors, failed: r.failed === true, busy: r.busy === true, headline: headline };
  }
  // resp = GET engine/autorun ⇒ {on, source, sourceText, hours, hoursText, running, statusText, last} أو null
  function engAuto(resp, now) {
    if (!resp || typeof resp !== 'object' || typeof resp.enabled !== 'boolean') return null;
    var hs = hoursText(resp.hours) || hourText(7);
    return { on: resp.enabled, source: str(resp.source), sourceText: ENG_SRC_TEXT[str(resp.source)] || '', hours: str(resp.hours) || '7', hoursText: hs,
             running: resp.running === true, statusText: resp.enabled ? 'يعمل كل يوم الساعة ' + hs + ' بتوقيت القاهرة' : 'التشغيل اليومي متوقّف',
             last: engRun(resp.last_result, now) };
  }
  // الضغط على المفتاح ⇒ ورقة المراجعة
  function engAutoToggle(cur) {
    var on = !(cur && cur.on);
    var lines = [{ label: 'التشغيل اليومي', from: cur ? (cur.on ? 'يعمل' : 'متوقّف') : '', to: on ? 'يعمل' : 'متوقّف' }];
    var lead = on ? 'ستجلب المنصة الفرص من مصادرها كل يوم الساعة ' + (cur ? cur.hoursText : hourText(7)) + ' بتوقيت القاهرة. ما يأتي من مصدر موثوق يُنشر مباشرة، والباقي مسودات تنتظر المراجعة:'
      : 'سيتوقّف الجلب اليومي للفرص، ويبقى التشغيل اليدوي «تشغيل الآن» متاحًا:';
    var warns = cur && cur.source === 'env' ? ['الاختيار المحفوظ هنا يغلب إعداد الخادم من الآن.'] : [];
    return { ok: true, body: { enabled: on }, lead: lead, lines: lines, warns: warns, goLabel: on ? 'تشغيل الجلب اليومي' : 'إيقاف الجلب اليومي',
             done: on ? 'التشغيل اليومي يعمل الآن' : 'توقّف التشغيل اليومي' };
  }
  // تغيير المواعيد: «٧» أو «٧، ١٩» ⇒ {ok, body, lines, ...}
  function engHoursCheck(text, cur) {
    var raw = toLatin(text).replace(/[،]/g, ',').replace(/\s+/g, '');
    var parts = raw.split(',').filter(function (p) { return p !== ''; });
    if (!parts.length || parts.length > 6 || !parts.every(function (p) { return /^\d{1,2}$/.test(p) && +p <= 23; })) {
      return { ok: false, error: 'الساعة من ٠ إلى ٢٣، ولأكثر من موعد فاصلة بينها (حتى ست ساعات)', errors: { hours: 'الساعة من ٠ إلى ٢٣' } };
    }
    var hs = parts.map(Number).filter(function (h, i, a) { return a.indexOf(h) === i; }).sort(function (a, b) { return a - b; });
    var norm = hs.join(',');
    if (cur && norm === cur.hours) return { ok: false, error: 'هذه هي المواعيد الحالية نفسها', errors: {} };
    var on = cur ? cur.on : false;
    // المواعيد وحدها: حالة المفتاح تُقرأ طازة على الخادم قبل الإرسال، فلا يرجع التشغيل لقيمة قديمة على الشاشة.
    return { ok: true, body: { hours: norm }, lead: 'ستتغيّر مواعيد الجلب اليومي (بتوقيت القاهرة)، ويبقى التشغيل اليومي على حاله:', goLabel: 'حفظ المواعيد',
             lines: [{ label: 'المواعيد', from: cur ? cur.hoursText : '', to: hoursText(norm) }], warns: on ? [] : ['التشغيل اليومي متوقّف الآن، والمواعيد تُستعمل حين يعمل.'] };
  }
  function engRunDone(res) {
    var r = engRun(res, 0);
    if (!r) return 'اكتمل التشغيل';
    if (r.busy) return 'هناك تشغيل آخر يعمل الآن، وستظهر نتيجته في «آخر تشغيل»';
    if (r.failed) return 'تعذّر التشغيل على المنصة، والمحاولة ممكنة بعد قليل';
    var n = function (k) { return r.rows.filter(function (x) { return x.key === k; })[0].n; };
    var t = 'اكتمل التشغيل: ' + line([n('published') ? 'نُشرت ' + U(n('published'), ['فرصة واحدة', 'فرصتان', 'فرص', 'فرصة']) : 'لم يُنشر شيء',
                                      n('drafts') ? U(n('drafts'), ['مسودة واحدة', 'مسودتان', 'مسودات', 'مسودة']) + ' للمراجعة' : '']);
    return r.errors ? t + '، ومعه ' + U(r.errors, ['عطل واحد', 'عطلان', 'أعطال', 'عطلًا']) : t;
  }
  // المصادر ⇒ {rows: [{id, name, host, enabled, trusted, lastText, lastBad}], on, trusted, countText} أو null
  function engSources(resp, now) {
    var list = items(resp);
    if (!list) return null;
    var rows = list.map(function (r) {
      var lr = r.last_run && typeof r.last_run === 'object' ? r.last_run : null;
      var lastText = lr ? line([when(lr.at, now), lr.ok === false ? 'تعذّر الجلب' : (isNum(lr.fetched) ? 'جُلب ' + U(lr.fetched, ['عنصر واحد', 'عنصران', 'عناصر', 'عنصرًا']) : '')]) || 'لم يُجلب بعد' : 'لم يُجلب بعد';
      if (lr && lr.ok !== false && lr.fetched === 0) lastText = line([when(lr.at, now), 'لم يُجلب شيء']);
      return { id: String(r.id), name: str(r.name) || str(r.host) || 'مصدر بلا اسم', host: str(r.host), url: httpUrl(r.url), enabled: r.enabled === true, trusted: r.trusted === true,
               lastText: lastText, lastBad: !!(lr && lr.ok === false) };
    });
    var n = rows.length;
    return { rows: rows, on: rows.filter(function (r) { return r.enabled; }).length, trusted: rows.filter(function (r) { return r.trusted; }).length,
             countText: n ? U(n, ['مصدر واحد', 'مصدران', 'مصادر', 'مصدرًا']) : 'لا مصادر بعد' };
  }
  function engSourceToggle(row, field) {
    var v = !row[field];
    if (field === 'trusted') {
      return { ok: true, body: { trusted: v }, goLabel: v ? 'توثيق المصدر' : 'إلغاء التوثيق', done: v ? 'صار المصدر موثوقًا' : 'لم يعد المصدر موثوقًا',
               lead: v ? 'ما يأتي من «' + row.name + '» سيُنشر مباشرة بعد فحص صلته بالقانون، بلا مراجعة:' : 'ما يأتي من «' + row.name + '» سيصير مسودات تنتظر المراجعة:',
               lines: [{ label: 'موثوق', from: row.trusted ? 'نعم' : 'لا', to: v ? 'نعم' : 'لا' }] };
    }
    return { ok: true, body: { enabled: v }, goLabel: v ? 'تشغيل المصدر' : 'إيقاف المصدر', done: v ? 'المصدر يعمل الآن' : 'توقّف المصدر',
             lead: v ? 'سيُجلب من «' + row.name + '» في كل تشغيل:' : 'لن يُجلب من «' + row.name + '» حتى يُشغَّل من جديد، وتبقى فرصه السابقة كما هي:',
             lines: [{ label: 'التشغيل', from: row.enabled ? 'يعمل' : 'متوقّف', to: v ? 'يعمل' : 'متوقّف' }] };
  }
  // سبب الفحص: رمز معروف ⇒ نصّه العربي، ونص عربي من المنصة يعدّي، وغير ذلك (رمز لاتيني مجهول) لا يظهر.
  function reviewReason(x) { x = str(x); return GATE_REASONS[x] || (/[\u0600-\u06FF]/.test(x) ? arDigits(x) : ''); }
  // «للمراجعة» ⇒ {rows, dupCount, countText} أو null. srcRows لاسم المصدر.
  function engReview(resp, srcRows, now) {
    var list = items(resp);
    if (!list) return null;
    var names = {};
    (srcRows || []).forEach(function (s) { names[s.id] = s.name; });
    var rows = list.map(function (r) {
      var dl = dayText(r.deadline);
      return { id: String(r.id), title: str(r.title) || 'فرصة بلا عنوان', kindText: kindText(r.kind) || 'أخرى', provider: str(r.provider),
               deadlineText: dl ? 'آخر موعد ' + dl : 'بلا موعد معلن', source: names[str(r.source_id)] || '', dup: !!str(r.possible_duplicate_of),
               reason: reviewReason(r.legal_reason), when: when(r.created_at, now) };
    });
    var n = rows.length;
    return { rows: rows, dupCount: rows.filter(function (r) { return r.dup; }).length,
             countText: n ? U(n, ['مسودة واحدة تنتظر', 'مسودتان تنتظران', 'مسودات تنتظر', 'مسودة تنتظر']) : 'لا مسودات تنتظر' };
  }
  // ملخص الفرص (للمربّع) ⇒ {drafts, dups, published, held, autoOn} (الغايب null)
  function engSummary(resp) {
    if (!resp || typeof resp !== 'object') return null;
    var num = function (k) { return isNum(resp[k]) ? resp[k] : null; };
    var au = resp.autorun && typeof resp.autorun === 'object' ? resp.autorun : {};
    return { drafts: num('drafts_waiting'), dups: num('possible_duplicates'), published: num('published_24h'), held: num('held_news_24h'), autoOn: au.enabled === true };
  }
  function engTile(sum) {
    if (!sum) return null;
    if (sum.drafts == null) return { n: sum.autoOn ? 'يعمل' : 'متوقّف', note: sum.autoOn ? 'التشغيل اليومي يعمل' : 'التشغيل اليومي متوقّف', word: true, off: !sum.autoOn };
    return { n: ar(sum.drafts), note: (sum.drafts ? 'مسودة تنتظر مراجعتك' : 'لا مسودات تنتظر') + (sum.autoOn ? '' : '، والتشغيل اليومي متوقّف'), hot: sum.drafts > 0 };
  }
  // إيميل الأسبوع ⇒ {on, scheduleText, lastText}
  function engDigest(resp, now) {
    if (!resp || typeof resp !== 'object' || typeof resp.enabled !== 'boolean') return null;
    var day = DAY_TEXT[str(resp.day)] || '', hr = hourText(resp.hour);
    var sched = day ? 'كل ' + day + (hr ? ' الساعة ' + hr : '') : '';
    var last = resp.last_sent_at ? line([when(resp.last_sent_at, now), isNum(resp.last_count) ? 'أُرسل إلى ' + U(resp.last_count, ['عضو واحد', 'عضوين', 'أعضاء', 'عضوًا']) : '']) : 'لم يُرسل بعد';
    if (resp.last_sent_at && resp.last_count === 0) last = line([when(resp.last_sent_at, now), 'لم يكن هناك من يُرسل إليه']);
    return { on: resp.enabled, scheduleText: sched, statusText: resp.enabled ? 'يعمل' + (sched ? '، ' + sched : '') : 'متوقّف', lastText: last };
  }
  function engDigestToggle(cur) {
    var on = !(cur && cur.on);
    return { ok: true, body: { enabled: on }, goLabel: on ? 'تشغيل إيميل الأسبوع' : 'إيقاف إيميل الأسبوع', done: on ? 'إيميل الأسبوع يعمل الآن' : 'توقّف إيميل الأسبوع',
             lead: on ? 'سيصل كل عضو مرة في الأسبوع بريد «فرص الأسبوع في مسارك» بالفرص الجديدة في مساره، ولمن أوقف الرسائل لا يُرسل شيء:' : 'لن يُرسل بريد «فرص الأسبوع في مسارك» حتى يُشغَّل من جديد:',
             lines: [{ label: 'إيميل الأسبوع', from: cur ? (cur.on ? 'يعمل' : 'متوقّف') : '', to: on ? 'يعمل' : 'متوقّف' }] };
  }
  function engEmailCheck(text) {
    var e = str(text);
    if (!/^[^\s@<>"']{1,64}@[^\s@<>"']{1,190}\.[A-Za-z]{2,24}$/.test(e)) return { ok: false, error: 'البريد الإلكتروني غير صحيح' };
    return { ok: true, email: e.toLowerCase() };
  }
  // المعاينة ⇒ {subject, html, trackText, countText, warn, ...}. اسم المسار العربي بس (الرمز اللاتيني لا يظهر).
  // `warn` = سبب عدم الإرسال لو المنصة قالت `will_send: false`، ولو مفيش نص للرسالة يحلّ السبب محلّ العدّ.
  function engPreview(resp) {
    if (!resp || typeof resp !== 'object') return null;
    var c = isNum(resp.count) ? resp.count : null, html = typeof resp.html === 'string' ? resp.html : '';
    var reason = PREVIEW_REASONS[str(resp.reason)] || '';
    var warn = resp.will_send === false ? (reason || 'لن تصل هذه الرسالة لصاحب هذا البريد') : '';
    var countText = c == null ? '' : (c ? U(c, ['فرصة واحدة', 'فرصتان', 'فرص', 'فرصة']) : 'لا فرص في هذا الأسبوع');
    if (!html && warn) countText = '';
    return { subject: str(resp.subject) || 'بلا عنوان', html: html, trackText: str(resp.track_title), countText: countText, warn: warn,
             willSend: resp.will_send === true, tooBig: resp.too_big === true };
  }
  function engTestDone(res) {
    res = res || {};
    if (res.sent === true) {
      return str(res.reason) === 'sample-track' ? 'أُرسلت رسالة التجربة بفرص مسار آخر، لأن هذا البريد بلا مسار' : 'أُرسلت رسالة التجربة، ويمكن فتح البريد للتأكد';
    }
    return 'لم تُرسل رسالة التجربة: ' + (TEST_REASONS[str(res.reason)] || 'المنصة لم ترسلها');
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
    opinions: opinions, topics: topics, opinionAction: opinionAction, topicAction: topicAction, gateView: gateView, gateDone: gateDone, gatePicked: gatePicked, TOPIC_CHIPS: TOPIC_CHIPS, newsHidden: newsHidden, gateReason: gateReason, reminders: reminders, reminderTile: reminderTile, reminderRunDone: reminderRunDone,
    ENG_CHIPS: ENG_CHIPS, hourText: hourText, hoursText: hoursText, engRun: engRun, engAuto: engAuto, engAutoToggle: engAutoToggle, engHoursCheck: engHoursCheck, engRunDone: engRunDone,
    engSources: engSources, engSourceToggle: engSourceToggle, engReview: engReview, engSummary: engSummary, engTile: engTile, engDigest: engDigest, engDigestToggle: engDigestToggle,
    engEmailCheck: engEmailCheck, engPreview: engPreview, engTestDone: engTestDone,
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
  Kit.link = function (url, text, title) { return url ? '<a class="sh-lnk" href="' + esc(url) + '"' + (title ? ' title="' + esc(title) + '"' : '') + ' target="_blank" rel="noopener noreferrer">' + esc(text) + '</a>' : ''; };
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
    topicsHidden: '/v2/saha/topics?status=all&hidden=1',
    ops: function (st, topic) { return '/v2/saha/opinions?status=' + st + (topic ? '&topic_id=' + encodeURIComponent(topic) : ''); },
    engAuto: '/v2/saha/engine/autorun', engSum: '/v2/saha/engine/summary', engSrc: '/v2/saha/engine/sources', engRev: '/v2/saha/engine/review?limit=50',
    engDig: '/v2/saha/engine/digest'
  };
  var HUB = [P.news('draft'), P.rev, P.opps, P.settings, P.ops('pending', ''), P.rem, P.topics, P.engSum];
  var now = function () { return Date.now(); };
  var B = null;
  function row(rows, id) { for (var i = 0; i < (rows || []).length; i++) if (rows[i].id === id) return rows[i]; return null; }
  function newsView(st) { var d = B.data(P.news(st)); return d ? X.news(d, now()) : null; }
  function revView() { var d = B.data(P.rev); return d ? X.opps(d, now()) : null; }
  function oppsView() { var d = B.data(P.opps); return d ? X.opps(d, now()) : null; }
  function opsView(st, topic) { var d = B.data(P.ops(st, topic)); return d ? X.opinions(d, now()) : null; }
  function remView() { var d = B.data(P.rem); return d ? X.reminders(d, now()) : null; }
  function setView() { var d = B.data(P.settings); return d ? X.prepView(d) : null; }
  function topicsPath(st) { return st === 'hidden' ? P.topicsHidden : P.topics; }
  function topicsView(st) { var d = B.data(topicsPath(st || 'open')); return d ? X.topics(d) : null; }
  function engAutoView() { var d = B.data(P.engAuto); return d ? X.engAuto(d, now()) : null; }
  function engSrcView() { var d = B.data(P.engSrc); return d ? X.engSources(d, now()) : null; }
  function engRevView() { var d = B.data(P.engRev); return d ? X.engReview(d, (engSrcView() || {}).rows, now()) : null; }
  function engDigView() { var d = B.data(P.engDig); return d ? X.engDigest(d, now()) : null; }
  function engSumView() { var d = B.data(P.engSum); return d ? X.engSummary(d) : null; }

  // —— المربّعات
  function tiles() {
    var n = Kit.count(B, P.news('draft'), function () { var v = newsView('draft'); return v ? { n: ar(v.rows.length), note: v.rows.length ? 'خبر ينتظر مراجعتك' : 'لا أخبار تنتظر', hot: v.rows.length > 0 } : null; });
    var rv = Kit.count(B, P.rev, function () { var v = revView(); return v ? { n: ar(v.rows.length), note: v.rows.length ? 'إعلان ينتظر قرارك' : 'لا إعلانات تنتظر', hot: v.rows.length > 0 } : null; });
    var op = Kit.count(B, P.opps, function () { var v = oppsView(); return v ? { n: ar(v.rows.length), note: v.rows.length ? 'فرصة في القائمة' : 'لا فرص بعد' } : null; });
    var pr = Kit.count(B, P.settings, function () { var v = setView(); return v ? { n: v.url ? 'مضبوط' : 'غير مضبوط', note: 'رابط دورة التحضير', word: true, hot: !v.url } : null; });
    var ot = Kit.count(B, P.ops('pending', ''), function () { var v = opsView('pending', ''); return v ? { n: ar(v.rows.length), note: v.rows.length ? 'رأي ينتظر قرارك' : 'لا آراء تنتظر', hot: v.rows.length > 0 } : null; });
    var rm = Kit.count(B, P.rem, function () { var t = X.reminderTile(remView()); return { n: t.n, note: t.sub, off: t.off, word: t.word, hot: t.hot }; });
    var imp = { n: 'جرّب', note: 'استيراد فرص جاهزة', word: true };
    var tp = Kit.count(B, P.topics, function () {
      var v = topicsView();
      return v ? { n: ar(v.rows.length), note: v.hiddenCount ? 'نقاش مفتوح، منها ' + ar(v.hiddenCount) + ' مخفية' : (v.rows.length ? 'نقاش مفتوح في الساحة' : 'لا نقاشات مفتوحة') } : null;
    });
    var eg = Kit.count(B, P.engSum, function () { return X.engTile(engSumView()); });
    return [
      Object.assign({ sub: 'news', name: 'أخبار للمراجعة', img: 'content' }, n),
      Object.assign({ sub: 'review', name: 'مراجعة الإعلانات والفرص', img: 'files' }, rv),
      Object.assign({ sub: 'opps', name: 'الفرص', img: 'marketing' }, op),
      Object.assign({ sub: 'import', name: 'استيراد الفرص', img: 'reports' }, imp),
      Object.assign({ sub: 'prep', name: 'رابط دورة التحضير', img: 'courses' }, pr),
      Object.assign({ sub: 'topics', name: 'النقاشات', img: 'disputes' }, tp),
      Object.assign({ sub: 'engine', name: 'محرّك الفرص', img: 'brain' }, eg),
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
      { h: 'الحالة', c: function (r) { return Kit.pill(r.statusText) + (r.hidden ? ' ' + Kit.pill(r.hiddenText, 'mute') : '') + (r.when ? '<span class="sh-sub">' + esc(r.when) + '</span>' : ''); } }
    ], function (r) {
      if (r.published && r.hidden) return '<button type="button" class="ep-b1" data-a="newsrestore" data-id="' + esc(r.id) + '">أرجِع</button><button type="button" class="ep-bs" data-a="newsun" data-id="' + esc(r.id) + '">ألغِ النشر</button>';
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
  function newsRestore(r) {
    B.flow({ title: 'إرجاع الخبر للقرّاء', check: function () { return X.newsCheck(X.newsForm(r), r, 'restore'); }, goLabel: 'أرجِع الخبر',
      send: function (res) { return B.api('/v2/saha/news/' + encodeURIComponent(r.id), Object.assign({}, res.body, { confirmed: true }), 'PUT'); }, done: function () { return 'رجع الخبر ظاهرًا للقرّاء'; } });
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
        + '<p class="sh-cur"><b>الرابط الحالي</b>' + (d.url ? Kit.link(d.url, 'افتح الرابط', d.url) : '<span class="sh-sub">لا يوجد رابط بعد</span>') + '</p>'
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

  // —— ٥ب · النقاشات: إخفاء وإرجاع + فحص الصلة بالقانون (تجربة بلا حفظ ثم تأكيد)
  function gatePanel() {
    var gv = B.f('gateRes', null) ? X.gateView(B.f('gateRes', null)) : null;
    if (!gv) return '';
    var off = B.f('gateOff', {}) || {}, picked = X.gatePicked(gv, off);
    // كل عنصر متعلَّم عليه افتراضيًّا، و«استبعاد من الإخفاء» يشيله من الإخفاء (القرار البشري لكل عنصر)
    var list = gv.applied ? '' : gv.rows.map(function (r) {
      var out = !!off[r.id];
      return '<li' + (out ? ' class="sh-off"' : '') + '><b>' + esc(r.kind) + '</b> ' + esc(r.title) + ' <span class="sh-sub">' + esc(out ? 'سيبقى كما هو' : r.reason) + '</span> '
        + '<button type="button" class="ep-bs" data-a="gatetoggle" data-id="' + esc(r.id) + '">' + (out ? 'إعادة للإخفاء' : 'استبعاد من الإخفاء') + '</button></li>';
    }).join('');
    var more = !gv.applied && gv.total > gv.listed ? '<p class="sh-fine">' + esc('تظهر هنا أول ' + ar(gv.listed) + ' فقط، والإخفاء يشمل المعروض هنا وحده.') + '</p>' : '';
    return '<div class="sh-panel" data-r="gate"><h3>' + esc(gv.applied ? 'تم الإخفاء' : 'نتيجة الفحص') + '</h3><p class="sh-fine">' + esc(gv.applied ? gv.totalText : 'لم يتغير شيء بعد. ' + gv.totalText) + '</p>'
      + '<ul class="sh-nums">' + gv.counts.map(function (c) { return '<li><b>' + esc(ar(c.n)) + '</b><span>' + esc(c.label) + '</span></li>'; }).join('') + '</ul>'
      + (gv.failed.length ? '<p class="sh-fine">' + esc(X.NA + ': ' + gv.failed.join('، ')) + '</p>' : '')
      + (list ? '<ul class="sh-warns">' + list + '</ul>' + more : '')
      + (!gv.applied && picked.length ? '<div class="sh-acts"><button type="button" class="ep-b1" data-a="gateapply">أخفِ المحدد (' + esc(ar(picked.length)) + ')</button></div>' : '') + '</div>';
  }
  function screenTopics() {
    var st = B.f('topSt', 'open'), p = topicsPath(st);
    B.need(p);
    var d = topicsView(st), body, busy = B.f('gateBusy', false), err = B.f('gateErr', '');
    var top = '<div class="sh-top"><button type="button" class="ep-b1" data-a="gatecheck"' + (busy ? ' disabled' : '') + '>' + (busy ? 'جارٍ الفحص…' : 'افحص الصلة بالقانون') + '</button></div>'
      + '<p class="sh-fine">الفحص يعرض الأخبار والنقاشات والمقالات غير المرتبطة بالقانون بلا أن يغيّر شيئًا، ثم تقرر إخفاءها.</p>'
      + (err ? '<div class="sh-err" role="alert">' + esc(err) + '</div>' : '');
    if (!d) body = B.stateBlock(p, 'النقاشات');
    else if (!d.rows.length) body = st === 'hidden' ? B.empty('لا نقاشات مخفية', 'كل نقاش يُخفى يظهر هنا ويمكن إرجاعه')
      : B.empty('لا نقاشات مفتوحة', 'تظهر هنا النقاشات المفتوحة في الساحة');
    else body = '<p class="sh-count">' + esc(d.countText) + '</p>' + B.list(d.rows, [
      { h: 'النقاش', c: function (r) { return '<b class="sh-t">' + esc(r.title) + '</b>'; } },
      { h: 'الآراء', c: function (r) { return esc(r.opinions == null ? X.NO_NUM : ar(r.opinions)); } },
      { h: 'الحالة', c: function (r) { return Kit.pill(r.hidden ? r.hiddenText : r.statusText, r.hidden ? 'mute' : ''); } }
    ], function (r) {
      return r.hidden ? '<button type="button" class="ep-b2" data-a="topicshow" data-id="' + esc(r.id) + '">أرجِع</button>'
        : '<button type="button" class="ep-b2" data-a="topichide" data-id="' + esc(r.id) + '">أخفِ</button>';
    });
    return { title: 'النقاشات', sub: d ? d.countText : '', img: 'disputes', html: top + gatePanel() + B.chips('topSt', X.TOPIC_CHIPS, st) + body };
  }
  function gateCheck() {
    if (B.f('gateBusy', false)) return;
    B.set('gateBusy', true); B.set('gateErr', ''); B.redraw();
    B.api('/v2/saha/legal-gate/check', {}).then(function (d) {
        var ok = !!X.gateView(d);
        B.set('gateBusy', false); B.set('gateRes', ok ? d : null); B.set('gateOff', {}); B.set('gateErr', ok ? '' : 'تعذّر الفحص الآن، حاول مرة أخرى'); B.redraw();
      })
      .catch(function (e) { B.set('gateBusy', false); B.set('gateRes', null); B.set('gateErr', X.writeError(e && e.status, e && e.data)); B.redraw(); });
  }
  function gateToggle(id) {
    var off = Object.assign({}, B.f('gateOff', {}) || {});
    if (off[id]) delete off[id]; else off[id] = true;
    B.set('gateOff', off); B.redraw();
  }
  function gateApplyFlow() {
    var v = X.gateView(B.f('gateRes', null));
    if (!v || v.applied) return;
    var ids = X.gatePicked(v, B.f('gateOff', {}));
    if (!ids.length) return;
    var byKind = {};
    v.rows.forEach(function (r) { if (ids.indexOf(r.id) > -1) byKind[r.kind] = (byKind[r.kind] || 0) + 1; });
    B.flow({ title: 'إخفاء غير المرتبط بالقانون', check: function () {
        return { ok: true, lead: 'سيختفي من الساحة ما حددته من نتيجة الفحص، بلا حذف. ويمكن إرجاع أي نقاش منه من هذه الشاشة:', goLabel: 'أخفِ المحدد',
                 lines: Object.keys(byKind).map(function (k) { return { label: k, to: ar(byKind[k]) }; }) };
      },
      send: function () { return B.api('/v2/saha/legal-gate/apply', { confirmed: true, ids: ids }); },
      done: function (out) { return X.gateDone(X.gateView(out)); }, after: function (out) { B.set('gateRes', out); } });
  }
  function topicFlow(r, kind) {
    var a = X.topicAction(kind);
    B.flow({ title: kind === 'hide' ? 'إخفاء النقاش' : 'إرجاع النقاش', check: function () { return { ok: true, lead: a.lead, goLabel: a.goLabel, lines: [{ label: 'النقاش', to: r.title }] }; },
      send: function () { return B.api('/v2/saha/topics/' + encodeURIComponent(r.id) + '/' + (kind === 'hide' ? 'hide' : 'restore'), { confirmed: true }); }, done: function () { return a.done; } });
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

  // —— ٦ب · محرّك الفرص (R18)
  function switchBtn(act, on, label, stateText) {
    return '<button type="button" class="sh-switch' + (on ? ' on' : '') + '" role="switch" aria-checked="' + (on ? 'true' : 'false') + '" data-a="' + act + '">'
      + '<i aria-hidden="true"></i><span><b>' + esc(label) + '</b><small>' + esc(stateText) + '</small></span></button>';
  }
  function nums(rows) { return '<ul class="sh-nums">' + rows.map(function (r) { return '<li><b>' + esc(ar(r.n)) + '</b><span>' + esc(r.label) + '</span></li>'; }).join('') + '</ul>'; }
  function engRunTab() {
    B.need(P.engAuto); B.need(P.engSum);
    var a = engAutoView(), sum = engSumView(), html;
    if (!a) return B.stateBlock(P.engAuto, 'حالة التشغيل اليومي');
    html = '<div class="sh-panel" data-r="auto">' + switchBtn('engauto', a.on, 'التشغيل اليومي', a.on ? 'يعمل' : 'متوقّف')
      + '<p class="sh-fine">' + esc(a.on ? a.statusText + '.' : 'لا يُجلب شيء تلقائيًا الآن. حين يعمل: كل يوم الساعة ' + a.hoursText + ' بتوقيت القاهرة.') + (a.sourceText ? ' ' + esc(a.sourceText) + '.' : '') + '</p>'
      + (a.running ? '<p class="sh-fine">يعمل تشغيل الآن، وتظهر نتيجته هنا حين ينتهي.</p>' : '')
      + '<div class="sh-acts"><button type="button" class="ep-bs" data-a="enghours">تغيير المواعيد</button></div></div>';
    var last = a.last;
    if (!last && sum) { var sd = B.data(P.engSum); last = sd ? X.engRun(sd.last_run, now()) : null; }
    html += '<div class="sh-panel" data-r="last"><h3>آخر تشغيل</h3>'
      + (last ? '<div class="sh-stat"><b class="sh-big ' + (last.failed ? 'red' : last.errors || last.busy ? 'gold' : 'green') + '">' + esc(last.headline) + '</b>' + (last.when ? '<span class="sh-sub">' + esc(last.when) + '</span>' : '') + '</div>'
        + (last.failed || last.busy ? '' : nums(last.rows)) : '<p class="sh-fine">لم يحدث أي تشغيل بعد. يمكن تشغيله الآن باليد.</p>')
      + '<p class="sh-fine">التشغيل قد يستغرق دقائق. لو لم يصل رد فالتشغيل مستمر على المنصة، وتظهر نتيجته هنا بعد قليل.</p>'
      + '<div class="sh-acts"><button type="button" class="ep-b1" data-a="engrun"' + (a.running ? ' disabled' : '') + '>تشغيل الآن</button></div></div>';
    if (sum) {
      var day = [[sum.published, 'فرص نُشرت آخر ٢٤ ساعة'], [sum.drafts, 'مسودات تنتظر المراجعة'], [sum.dups, 'منها غالبًا مكررة'], [sum.held, 'أخبار محجوزة للمراجعة آخر ٢٤ ساعة']]
        .filter(function (x) { return x[0] != null; }).map(function (x) { return { n: x[0], label: x[1] }; });
      if (day.length) html += '<div class="sh-panel" data-r="day"><h3>الصورة الآن</h3>' + nums(day) + '</div>';
    }
    return html;
  }
  function engReviewTab() {
    B.need(P.engRev); B.need(P.engSrc);
    var d = engRevView();
    if (!d) return B.stateBlock(P.engRev, 'مسودات المحرّك');
    if (!d.rows.length) return B.empty('لا مسودات تنتظر', 'ما يأتي من مصدر غير موثوق يظهر هنا للقرار فيه');
    return '<p class="sh-count">' + esc(d.countText) + (d.dupCount ? '، ' + esc(U.U(d.dupCount, ['واحدة منها غالبًا مكررة', 'اثنتان منها غالبًا مكررتان', 'منها غالبًا مكررة', 'منها غالبًا مكررة'])) : '') + '</p>'
      + '<ul class="sh-cards big">' + d.rows.map(function (r) {
        var facts = [r.kindText, r.provider, r.source ? 'من ' + r.source : ''].filter(Boolean).join('، ');
        return '<li class="sh-card big" data-id="' + esc(r.id) + '"><div class="sh-ch"><h3>' + esc(r.title) + '</h3><span class="sh-pills">' + (r.dup ? Kit.pill('غالبًا مكررة', 'gold') : '') + '</span></div>'
          + (facts ? '<p class="sh-meta"><span>' + esc(facts) + '</span></p>' : '')
          + '<p class="sh-meta"><b>الموعد</b><span>' + esc(r.deadlineText) + '</span>' + (r.when ? '<span>' + esc(r.when) + '</span>' : '') + '</p>'
          + (r.reason ? '<p class="sh-meta"><b>ملاحظة الفحص</b><span>' + esc(r.reason) + '</span></p>' : '')
          + '<div class="sh-acts"><button type="button" class="ep-b1" data-a="engpub" data-id="' + esc(r.id) + '">نشر</button><button type="button" class="ep-b2" data-a="engrej" data-id="' + esc(r.id) + '">رفض</button>'
          + '<button type="button" class="ep-bs" data-a="engedit" data-id="' + esc(r.id) + '">فتح للتعديل</button></div></li>';
      }).join('') + '</ul>';
  }
  function engSourcesTab() {
    B.need(P.engSrc);
    var d = engSrcView(), lead = '<p class="sh-fine">ما يأتي من مصدر موثوق يُنشر مباشرة، والباقي يصل مسودة تنتظر المراجعة.</p>';
    if (!d) return lead + B.stateBlock(P.engSrc, 'المصادر');
    if (!d.rows.length) return lead + B.empty('لا مصادر بعد', 'تُضاف القائمة الأولى من المصادر المعروفة بضغطة، وكلها تبدأ غير موثوقة') + '<div class="sh-acts"><button type="button" class="ep-b1" data-a="engseed">إضافة المصادر الأولى</button></div>';
    return lead + '<p class="sh-count">' + esc(X.line([d.countText, U.U(d.on, ['واحد يعمل', 'اثنان يعملان', 'تعمل', 'تعمل']), d.trusted ? U.U(d.trusted, ['واحد موثوق', 'اثنان موثوقان', 'موثوقة', 'موثوقًا']) : 'لا مصدر موثوق'])) + '</p>'
      + B.list(d.rows, [
        { h: 'المصدر', c: function (r) { return '<b class="sh-t">' + esc(r.name) + '</b>' + (r.host ? '<span class="sh-who" dir="ltr">' + esc(r.host) + '</span>' : ''); } },
        { h: 'آخر جلب', c: function (r) { return r.lastBad ? Kit.pill(r.lastText, 'gold') : esc(r.lastText); } },
        { h: 'يعمل', c: function (r) { return Kit.pill(r.enabled ? 'يعمل' : 'متوقّف', r.enabled ? 'green' : 'mute'); } },
        { h: 'موثوق', c: function (r) { return Kit.pill(r.trusted ? 'موثوق' : 'غير موثوق', r.trusted ? 'green' : 'mute'); } }
      ], function (r) {
        return '<button type="button" class="ep-b2" data-a="engsrcon" data-id="' + esc(r.id) + '">' + (r.enabled ? 'إيقاف' : 'تشغيل') + '</button>'
          + '<button type="button" class="ep-bs" data-a="engsrctr" data-id="' + esc(r.id) + '">' + (r.trusted ? 'إلغاء التوثيق' : 'توثيق المصدر') + '</button>';
      });
  }
  function myEmail() { var E = ep(), u = (E && E.user) || {}; return typeof u.email === 'string' ? u.email : ''; }
  function engDigestTab() {
    B.need(P.engDig);
    var d = engDigView();
    if (!d) return B.stateBlock(P.engDig, 'إيميل الأسبوع');
    var mail = B.f('engMail', myEmail()), busy = B.f('engPrevBusy', false), err = B.f('engPrevErr', ''), pv = X.engPreview(B.f('engPrev', null));
    var html = '<div class="sh-panel" data-r="digest">' + switchBtn('engdig', d.on, 'إيميل «فرص الأسبوع في مسارك»', d.statusText)
      + '<p class="sh-fine">يصل كل عضو مرة في الأسبوع بالفرص الجديدة في مساره. آخر إرسال: ' + esc(d.lastText) + '.</p></div>'
      + '<div class="sh-panel" data-r="preview"><h3>معاينة وتجربة</h3><p class="sh-fine">المعاينة تعرض الرسالة كما ستصل لهذا البريد بلا أن تُرسل شيئًا.</p>'
      + '<div class="sh-sbox"><label for="shEngMail">البريد (بريدك أو بريد عضو)</label><input id="shEngMail" type="text" inputmode="email" dir="ltr" maxlength="254" autocomplete="off" value="' + esc(mail) + '"></div>'
      + '<div class="sh-acts"><button type="button" class="ep-b2" data-a="engprev"' + (busy ? ' disabled' : '') + '>' + (busy ? 'جارٍ التحضير…' : 'معاينة') + '</button>'
      + '<button type="button" class="ep-bs" data-a="engtest">إرسال تجربة لهذا البريد</button></div>' + (err ? '<div class="sh-err" role="alert">' + esc(err) + '</div>' : '') + '</div>';
    if (pv) {
      var pvFacts = X.line([pv.trackText ? 'المسار: ' + pv.trackText : '', pv.countText]);
      html += '<div class="sh-panel" data-r="pv"><h3>' + esc(pv.subject) + '</h3>' + (pvFacts ? '<p class="sh-fine">' + esc(pvFacts) + '</p>' : '')
        + (pv.warn ? '<p class="sh-warn" role="status" data-r="pvwarn">' + esc(pv.warn) + '</p>' : '')
        + (pv.html ? '<iframe class="sh-pv" title="معاينة الرسالة" sandbox="" referrerpolicy="no-referrer" srcdoc="' + esc(pv.html) + '"></iframe>' : (pv.warn ? '' : '<p class="sh-fine">لا نص للرسالة.</p>'))
        + (pv.tooBig ? '<p class="sh-fine">الرسالة طويلة، فظهر أولها فقط.</p>' : '') + '<p class="sh-fine">الصور تظهر في البريد الحقيقي وقد لا تظهر هنا.</p></div>';
    }
    return html;
  }
  function screenEngine() {
    var tab = B.f('engTab', 'run'), sum = engSumView();
    var chips = X.ENG_CHIPS.map(function (c) { return c[0] === 'review' && sum && sum.drafts ? [c[0], c[1], ar(sum.drafts)] : c; });
    var body = tab === 'review' ? engReviewTab() : tab === 'sources' ? engSourcesTab() : tab === 'digest' ? engDigestTab() : engRunTab();
    return { title: 'محرّك الفرص', sub: 'جلب الفرص كل يوم من مصادر معروفة', img: 'brain', html: B.chips('engTab', chips, tab) + body, after: function (v) {
      var i = q1('#shEngMail', v);
      if (i) i.addEventListener('input', function () { B.set('engMail', i.value); });
    } };
  }
  function engFlow(title, res, path, method, after) {
    B.flow({ title: title, check: function () { return res; }, send: function () { return B.api(path, Object.assign({}, res.body, { confirmed: true }), method); },
      done: function (out) { return typeof res.done === 'function' ? res.done(out) : res.done; }, after: after });
  }
  function engAutoFlow() { var a = engAutoView(); if (a) engFlow('التشغيل اليومي', X.engAutoToggle(a), '/v2/saha/engine/autorun', 'PUT'); }
  function engHoursFlow() {
    var a = engAutoView();
    if (!a) return;
    B.flow({ title: 'مواعيد التشغيل اليومي', intro: 'الساعة بنظام ٢٤ ساعة بتوقيت القاهرة، ولأكثر من موعد فاصلة بينها (مثل ٧، ١٩).',
      form: function (v) { return fld('الساعة', inp('hours', (v || {}).hours, { max: 30, mode: 'numeric' }), 'hours', 'من ٠ إلى ٢٣'); }, init: { hours: ar(a.hours).replace(/,/g, '، ') },
      check: function (v) { return X.engHoursCheck(v.hours, engAutoView()); }, nextLabel: 'مراجعة ثم حفظ',
      send: function (res) { return B.api('/v2/saha/engine/autorun', Object.assign({}, res.body, { confirmed: true }), 'PUT'); }, done: function () { return 'حُفظت مواعيد التشغيل اليومي'; } });
  }
  function engRunFlow() {
    B.flow({ title: 'تشغيل المحرّك الآن', check: function () {
        return { ok: true, lead: 'ستجلب المنصة الفرص الآن من كل المصادر التي تعمل. ما يأتي من مصدر موثوق يُنشر مباشرة، والباقي مسودات تنتظر المراجعة. قد يستغرق ذلك دقائق.', goLabel: 'بدء التشغيل', lines: [] };
      },
      send: function () { return B.api('/v2/saha/engine/run', { confirmed: true }); }, done: function (out) { return X.engRunDone(out); } });
  }
  function engSeedFlow() {
    B.flow({ title: 'إضافة المصادر الأولى', check: function () {
        return { ok: true, lead: 'ستُضاف قائمة المصادر المعروفة الجاهزة على المنصة، وكلها تبدأ غير موثوقة فيصل ما يأتي منها مسودات. لا يتغيّر مصدر موجود.', goLabel: 'إضافة المصادر', lines: [] };
      },
      send: function () { return B.api('/v2/saha/engine/sources/import-seed', { confirmed: true }); },
      done: function (out) { var n = out && typeof out.created === 'number' ? out.created : 0; return n ? 'أُضيف ' + U.U(n, ['مصدر واحد', 'مصدران', 'مصادر', 'مصدرًا']) : 'لم يكن هناك مصدر جديد يُضاف'; } });
  }
  function engSourceFlow(r, field) {
    engFlow(field === 'trusted' ? 'توثيق المصدر' : 'تشغيل المصدر', X.engSourceToggle(r, field), '/v2/saha/engine/sources/' + encodeURIComponent(r.id), 'PUT');
  }
  // «فتح للتعديل»: الصف الكامل من مسار الفرصة الموجود ثم نفس نموذج التعديل (قراءة بلا كتابة؛ الحفظ يمرّ على ورقة المراجعة).
  function engEdit(id) {
    var E = ep();
    if (!E || !E.api || B.f('engEditBusy', false)) return;
    B.set('engEditBusy', true);
    E.api('/v2/saha/opportunities/' + encodeURIComponent(id)).then(function (d) {
      B.set('engEditBusy', false);
      var v = X.opps({ items: [d] }, now()), r = v && v.rows[0];
      if (r) oppFlow(r); else B.setNote('تعذّر فتح الفرصة الآن، والمحاولة ممكنة بعد قليل');
      B.redraw();
    }).catch(function (e) { B.set('engEditBusy', false); B.setNote(X.writeError(e && e.status, e && e.data)); B.redraw(); });
  }
  function engDigestFlow() { var d = engDigView(); if (d) engFlow('إيميل الأسبوع', X.engDigestToggle(d), '/v2/saha/engine/digest', 'PUT'); }
  function engMailNow() { var i = q1('#shEngMail'); if (i) B.set('engMail', i.value); return X.engEmailCheck(i ? i.value : B.f('engMail', '')); }
  function engPreviewRun() {
    if (B.f('engPrevBusy', false)) return;
    var ck = engMailNow();
    if (!ck.ok) { B.set('engPrevErr', ck.error); B.redraw(); return; }
    B.set('engPrevBusy', true); B.set('engPrevErr', ''); B.redraw();
    B.api('/v2/saha/engine/digest/preview', { email: ck.email }).then(function (d) { B.set('engPrevBusy', false); B.set('engPrev', d); B.redraw(); })
      .catch(function (e) { B.set('engPrevBusy', false); B.set('engPrev', null); B.set('engPrevErr', X.writeError(e && e.status, e && e.data)); B.redraw(); });
  }
  function engTestFlow() {
    var ck = engMailNow();
    if (!ck.ok) { B.set('engPrevErr', ck.error); B.redraw(); return; }
    B.set('engPrevErr', '');
    B.flow({ title: 'إرسال رسالة تجربة', check: function () {
        return { ok: true, lead: 'ستُرسل رسالة «فرص الأسبوع في مسارك» مرة واحدة إلى هذا البريد فقط:', goLabel: 'إرسال التجربة', lines: [{ label: 'البريد', to: ck.email }] };
      },
      send: function () { return B.api('/v2/saha/engine/digest/send-test', { email: ck.email, confirmed: true }); }, done: function (out) { return X.engTestDone(out); } });
  }

  // ------------------------------------------------------------------ التسجيل
  B = Kit.board({
    key: 'saha', mod: 'v2s_saha', label: 'الساحة', lead: 'اختر ما تريد إدارته في الساحة',
    hub: function () { return HUB; }, tiles: tiles,
    screens: { news: screenNews, review: screenReview, opps: screenOpps, import: screenImport, prep: screenPrep, topics: screenTopics, opinions: screenOpinions, reminders: screenReminders, engine: screenEngine },
    act: {
      newsrun: function () { newsRun(); },
      newsapprove: function (b, a, id) { var r = row((newsView(b.f('newsSt', 'draft')) || {}).rows, id); if (r) newsFlow(r, 'approve'); },
      newsrestore: function (b, a, id) { var r = row((newsView(b.f('newsSt', 'draft')) || {}).rows, id); if (r) newsRestore(r); },
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
      remrun: function () { remFlow(); },
      gatecheck: gateCheck,
      gateapply: function () { gateApplyFlow(); },
      gatetoggle: function (b, a, id) { gateToggle(id); },
      topichide: function (b, a, id) { var r = row((topicsView(b.f('topSt', 'open')) || {}).rows, id); if (r) topicFlow(r, 'hide'); },
      topicshow: function (b, a, id) { var r = row((topicsView(b.f('topSt', 'open')) || {}).rows, id); if (r) topicFlow(r, 'show'); },
      engauto: function () { engAutoFlow(); },
      enghours: function () { engHoursFlow(); },
      engrun: function () { engRunFlow(); },
      engseed: function () { engSeedFlow(); },
      engsrcon: function (b, a, id) { var r = row((engSrcView() || {}).rows, id); if (r) engSourceFlow(r, 'enabled'); },
      engsrctr: function (b, a, id) { var r = row((engSrcView() || {}).rows, id); if (r) engSourceFlow(r, 'trusted'); },
      engpub: function (b, a, id) { var r = row((engRevView() || {}).rows, id); if (r) decideFlow(r, 'approve'); },
      engrej: function (b, a, id) { var r = row((engRevView() || {}).rows, id); if (r) decideFlow(r, 'reject'); },
      engedit: function (b, a, id) { engEdit(id); },
      engdig: function () { engDigestFlow(); },
      engprev: engPreviewRun,
      engtest: function () { engTestFlow(); }
    }
  });
  window.V2S_SAHA = B;
})();
