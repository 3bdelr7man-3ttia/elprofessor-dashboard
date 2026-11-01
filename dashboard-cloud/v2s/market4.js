/* ============================================================================
 * v2s/market4.js — الجزء الأول: المنطق النقي لـ«السوق v4» في الداشبورد (لا DOM ولا شبكة ولا ساعة خفية؛ `now` يُمرَّر صراحةً).
 *   ١) اقتراحات «أخرى»: صفوف الطابور · قرار الاعتماد (نوع الخدمة والتخصص والنطاق، وفي كلٍّ «أخرى»).
 *   ٢) مدى الأسعار: صفوف الكتالوج · التحقق من سبع عملات (أعداد صحيحة · الأدنى < الأعلى · تحذير فوق ثلاثة أضعاف) · الفروق للتأكيد.
 *   ٣) المكاتب: صفوف الطابور · رابط السجل · عدد الأعضاء · أيّ مكتب يقبل «وثّق السجل».
 *   ٤) الطلبات المفتوحة: صفوف القراءة فقط (الخدمة · البلد · العروض · مرات فتح المرفقات).
 *   ٥) الترخيص عند القبول: بلاد القيد (ISO-2 بتسمية عربية) · بلد الطلب مسبقًا · معرّف ملف الترخيص.
 * ⛔ المصدر الفاشل = null (والشاشة تكتب «غير متاح بعد»)، لا صفر مخترع. كل رقم ظاهر بأرقام هندية، و«·» لا تلاصق رقمًا (نستعمل «،»).
 * ⛔ نصوص ظاهرة: فصحى بسيطة محايدة للجنس، بلا مصطلحات تقنية، ولا عنوان يبدأ بـ«الذكاء».
 * ========================================================================== */
(function (root) {
  'use strict';
  var L = root.V2L;
  if (!L || !L.util) return;
  var Un = L.util, ar = Un.ar, fmt = Un.fmt, U = Un.U;
  var DIG = '٠١٢٣٤٥٦٧٨٩';

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

  // ------------------------------------------------------------------ جداول التسميات (نسخة من المنصة؛ التحقق النهائي عندها)
  var SERVICE_TYPES = [
    ['contract_review', 'مراجعة عقد'], ['contract_draft', 'صياغة عقد أو اتفاق'], ['memo', 'مذكرة دفاع أو صحيفة دعوى'],
    ['objection', 'لائحة اعتراض أو استئناف'], ['legal_research', 'بحث قانوني مسنَد'], ['written_opinion', 'رأي قانوني مكتوب'],
    ['case_review', 'مراجعة ملف قضية وخطة تقاضٍ'], ['company_setup', 'تأسيس شركة وتوثيق'], ['compliance', 'مراجعة امتثال وسياسات'],
    ['thesis_review', 'مراجعة رسالة أو بحث أكاديمي'], ['filing_prep', 'إعداد أوراق لجهة رسمية'], ['training', 'تدريب أو ورشة مخصّصة']
  ];
  var SPECIALTIES = [
    ['civil', 'مدني وتعويضات'], ['criminal', 'جنائي'], ['commercial', 'تجاري وشركات'], ['labor', 'عمل وتأمينات'], ['family', 'أحوال شخصية وميراث'],
    ['administrative', 'إداري ومناقصات'], ['constitutional', 'دستوري وحقوق'], ['real_estate', 'عقاري وتوثيق'], ['arbitration', 'تحكيم وتسوية منازعات'],
    ['ip', 'ملكية فكرية وتقنية'], ['tax', 'ضرائب وجمارك'], ['banking', 'مصرفي وتمويل'], ['compliance', 'امتثال وحوكمة'], ['practice_skills', 'مهارات المهنة وإدارة المكتب']
  ];
  var OTHER = 'other';
  function labelOf(list, key) { for (var i = 0; i < list.length; i++) if (list[i][0] === key) return list[i][1]; return ''; }
  function typeLabel(key) { return labelOf(SERVICE_TYPES, key) || 'أخرى'; }
  function specialtyLabel(key) { return labelOf(SPECIALTIES, key) || 'أخرى'; }

  var COUNTRIES = [
    ['EG', 'مصر'], ['SA', 'السعودية'], ['AE', 'الإمارات'], ['QA', 'قطر'], ['KW', 'الكويت'], ['OM', 'عُمان'], ['BH', 'البحرين'], ['JO', 'الأردن'],
    ['IQ', 'العراق'], ['LB', 'لبنان'], ['PS', 'فلسطين'], ['SY', 'سوريا'], ['YE', 'اليمن'], ['LY', 'ليبيا'], ['TN', 'تونس'], ['DZ', 'الجزائر'],
    ['MA', 'المغرب'], ['SD', 'السودان'], ['XX', 'أخرى']
  ];
  function countryLabel(code) { var c = str(code).toUpperCase(); return labelOf(COUNTRIES, c) || (c ? 'أخرى' : ''); }

  var CURRENCIES = ['EGP', 'SAR', 'AED', 'QAR', 'KWD', 'OMR', 'USD'];
  var CUR_NAME = { EGP: 'جنيه مصري', SAR: 'ريال سعودي', AED: 'درهم إماراتي', QAR: 'ريال قطري', KWD: 'دينار كويتي', OMR: 'ريال عُماني', USD: 'دولار أمريكي' };
  var CUR_SHORT = { EGP: 'جنيه', SAR: 'ريال سعودي', AED: 'درهم', QAR: 'ريال قطري', KWD: 'دينار كويتي', OMR: 'ريال عُماني', USD: 'دولار' };
  var MAX_TIMES = 3;

  // ------------------------------------------------------------------ ١ · اقتراحات «أخرى»
  var SUG_STATUS = { pending: 'ينتظر قرارك', approved: 'اعتُمد', rejected: 'رُفض' };
  function suggestions(resp, now) {
    if (!resp || !Array.isArray(resp.items)) return null;
    var rows = resp.items.filter(function (r) { return r && typeof r === 'object' && str(r.id); }).map(function (r) {
      var st = str(r.status) || 'pending';
      return { id: str(r.id), name: str(r.name) || 'اقتراح بلا اسم', note: str(r.note), who: str(r.user_email), status: st, statusText: SUG_STATUS[st] || 'حالة غير معروفة',
               open: st === 'pending', slug: str(r.created_slug), decidedBy: str(r.decided_by), when: when(r.created_at, now), ts: ms(r.created_at) };
    });
    var pending = isNum(resp.pending) ? resp.pending : rows.filter(function (r) { return r.open; }).length;
    return { rows: rows, pending: pending, total: isNum(resp.total) ? resp.total : rows.length,
             countText: pending ? U(pending, ['اقتراح واحد ينتظر', 'اقتراحان ينتظران', 'اقتراحات تنتظر', 'اقتراحًا ينتظر']) : 'لا اقتراحات تنتظر' };
  }
  // نموذج القرار ⇒ {ok, body} | {ok:false, error}.
  // type/specialty: مفتاح أو 'other' («أخرى» ⇒ الافتراضي عند المنصة: رأي مكتوب · عام). scopeMode: 'note' (كما كتبه صاحب الاقتراح) | 'other' (نص جديد).
  function suggestionDecision(form) {
    form = form || {};
    if (form.decision === 'reject') return { ok: true, body: { decision: 'reject' } };
    if (form.decision !== 'approve') return { ok: false, error: 'اختر: اعتماد أو رفض' };
    var type = str(form.type), spec = str(form.specialty);
    if (!type) return { ok: false, error: 'اختر نوع الخدمة، أو «أخرى»' };
    if (!spec) return { ok: false, error: 'اختر التخصص، أو «أخرى»' };
    if (type !== OTHER && !labelOf(SERVICE_TYPES, type)) return { ok: false, error: 'نوع الخدمة غير معروف' };
    if (spec !== OTHER && !labelOf(SPECIALTIES, spec)) return { ok: false, error: 'التخصص غير معروف' };
    var scope = '';
    if (form.scopeMode === 'other') {
      scope = str(form.scope);
      if (!scope) return { ok: false, error: 'اكتب النطاق، أو اختر «كما كتبه صاحب الاقتراح»' };
      if (scope.length > 600) return { ok: false, error: 'النطاق طويل (حتى ٦٠٠ حرف)' };
    }
    return { ok: true, body: { decision: 'approve', service_type: type === OTHER ? '' : type, specialty: spec === OTHER ? '' : spec, scope: scope } };
  }
  var APPROVE_FAIL = { 404: 'هذا الاقتراح لم يعد موجودًا على المنصة', 409: 'سبق أن اتُّخذ قرار في هذا الاقتراح، حدّث الصفحة', 422: 'نوع الخدمة أو التخصص غير معروف', other: 'تعذّر تنفيذ القرار، حاول مرة أخرى' };
  function decideError(status, data) {
    var msg = data && typeof data.error === 'string' ? data.error : '';
    if (data && data.no_reply) return msg;
    if (msg && (status === 409 || status === 422 || status === 404)) return arDigits(msg);
    return APPROVE_FAIL[status] || APPROVE_FAIL.other;
  }
  function decideDone(decision, res) {
    if (decision === 'reject') return 'رُفض الاقتراح، وأُبلغ صاحبه';
    if (res && res.claimed === false) return 'أُضيفت الخدمة إلى القائمة، ولم يُسجَّل طلب تقديمها باسم صاحب الاقتراح';
    return 'أُضيفت الخدمة إلى القائمة، وسجّلنا طلب تقديمها باسم صاحب الاقتراح';
  }

  // ------------------------------------------------------------------ ٢ · مدى الأسعار
  function cleanRange(r) {
    var out = {};
    if (!r || typeof r !== 'object') return out;
    CURRENCIES.forEach(function (c) {
      var v = r[c];
      if (Array.isArray(v) && v.length === 2 && isNum(v[0]) && isNum(v[1])) out[c] = [v[0], v[1]];
    });
    return out;
  }
  function rangeOne(cur, pair) { return fmt(pair[0]) + ' إلى ' + fmt(pair[1]) + ' ' + (CUR_SHORT[cur] || cur); }
  function rangeText(range) {
    var keys = CURRENCIES.filter(function (c) { return range[c]; });
    if (!keys.length) return '';
    var first = keys[0];
    var t = rangeOne(first, range[first]);
    if (keys.length > 1) t += '، و' + U(keys.length - 1, ['عملة أخرى', 'عملتان أخريان', 'عملات أخرى', 'عملة أخرى']);
    return t;
  }
  function catalog(resp) {
    if (!resp || !Array.isArray(resp.items)) return null;
    var rows = resp.items.filter(function (r) { return r && typeof r === 'object' && str(r.slug); }).map(function (r) {
      var fixed = r.pricing_mode === 'fixed', range = cleanRange(r.anchor_range), n = Object.keys(range).length;
      return { slug: str(r.slug), name: str(r.name) || str(r.slug), type: typeLabel(str(r.service_type)), specialty: str(r.specialty_label) || specialtyLabel(str(r.specialty)),
               fixed: fixed, licensed: !!r.licensed, range: range, hasRange: n > 0, canEdit: !fixed,
               text: fixed ? 'سعر ثابت' : (n ? rangeText(range) : 'بلا مدى') };
    });
    var cur = Array.isArray(resp.currencies) ? resp.currencies.filter(function (c) { return CURRENCIES.indexOf(c) > -1; }) : [];
    var noRange = isNum(resp.no_range_count) ? resp.no_range_count : null;
    return { rows: rows, total: isNum(resp.total) ? resp.total : rows.length, currencies: cur.length ? cur : CURRENCIES.slice(), noRangeCount: noRange,
             noRangeText: noRange == null ? '' : (noRange ? U(noRange, ['خدمة واحدة بلا مدى', 'خدمتان بلا مدى', 'خدمات بلا مدى', 'خدمة بلا مدى']) : 'كل الخدمات لها مدى') };
  }
  // نص رقم صحيح من خانة: لاتيني أو هندي، وفواصل الآلاف مقبولة. ⇒ {kind:'empty'|'bad'|'num', n}
  function parseWhole(text) {
    var t = toLatin(text).replace(/[٬,\s]/g, '');
    if (t === '') return { kind: 'empty' };
    if (!/^\d{1,10}$/.test(t)) return { kind: 'bad' };
    return { kind: 'num', n: Number(t) };
  }
  // inputs: {EGP:{min:'٢٥٠٠', max:'٦٠٠٠'}, SAR:{...}}. ⇒ {ok, empty, errors, warns, payload}. فارغ تمامًا ⇒ ok:false وempty:true (المسح زرّ مستقل).
  function anchorCheck(inputs) {
    inputs = inputs || {};
    var errors = {}, warns = {}, payload = {}, any = false;
    CURRENCIES.forEach(function (c) {
      var i = inputs[c] || {}, a = parseWhole(i.min), b = parseWhole(i.max);
      if (a.kind === 'empty' && b.kind === 'empty') return;
      if (a.kind === 'bad' || b.kind === 'bad') { errors[c] = 'اكتب أرقامًا صحيحة بلا كسور'; return; }
      if (a.kind === 'empty' || b.kind === 'empty') { errors[c] = 'اكتب الأدنى والأعلى معًا، أو اترك الخانتين فارغتين'; return; }
      if (a.n >= b.n) { errors[c] = 'يجب أن يكون الأدنى أقل من الأعلى'; return; }
      payload[c] = [a.n, b.n]; any = true;
      if (b.n > MAX_TIMES * a.n) warns[c] = 'الأعلى أكبر من ثلاثة أضعاف الأدنى، راجع الرقمين';
    });
    var hasErr = Object.keys(errors).length > 0;
    return { ok: !hasErr && any, empty: !hasErr && !any, errors: errors, warns: warns, payload: payload,
             error: hasErr ? 'صحّح الخانات المعلَّمة' : (!any ? 'اكتب مدى لعملة واحدة على الأقل، أو اختر «امسح المدى»' : '') };
  }
  function anchorInputs(range) {
    var out = {};
    CURRENCIES.forEach(function (c) {
      var p = range && range[c];
      out[c] = { min: p ? ar(p[0]) : '', max: p ? ar(p[1]) : '' };
    });
    return out;
  }
  // قبل ⇒ بعد لكل عملة تغيّرت (للورقة والتأكيد).
  function anchorDiff(before, after) {
    var b = cleanRange(before), a = cleanRange(after), lines = [];
    CURRENCIES.forEach(function (c) {
      var x = b[c] ? rangeOne(c, b[c]) : 'بلا مدى', y = a[c] ? rangeOne(c, a[c]) : 'بلا مدى';
      if (x !== y) lines.push({ label: CUR_NAME[c], from: x, to: y });
    });
    return lines;
  }
  function anchorError(status, data) {
    var msg = data && typeof data.error === 'string' ? data.error : '';
    if (data && data.no_reply) return msg;
    if (status === 409 || status === 422) return arDigits(msg || 'رفضت المنصة هذا المدى');
    if (status === 404) return 'هذه الخدمة لم تعد في القائمة';
    return 'تعذّر حفظ المدى، حاول مرة أخرى';
  }
  function catalogQuery(f) {
    f = f || {};
    var q = [];
    if (f.noRange) q.push('no_range=1');
    var t = str(f.q).slice(0, 120);
    if (t) q.push('q=' + encodeURIComponent(t));
    return '/v2/market/catalog' + (q.length ? '?' + q.join('&') : '');
  }

  // ------------------------------------------------------------------ ٣ · المكاتب
  function safeHttps(u) { u = str(u); return /^https?:\/\//i.test(u) ? u : ''; }
  var ORG_STATUS = { pending: 'ينتظر التوثيق', active: 'مفعّل', suspended: 'موقوف' };
  function orgs(resp, now) {
    if (!resp || !Array.isArray(resp.items)) return null;
    var rows = resp.items.filter(function (r) { return r && typeof r === 'object' && str(r.id); }).map(function (r) {
      var reg = r.commercial_reg && typeof r.commercial_reg === 'object' ? r.commercial_reg : null;
      var url = reg ? safeHttps(reg.url) : '', verified = !!(reg && str(reg.verified_at));
      var members = Array.isArray(r.members) ? r.members.filter(function (m) { return m && typeof m === 'object'; }) : [];
      var st = str(r.status) || 'pending';
      var place = [str(r.city), countryLabel(r.country)].filter(function (x, i, a) { return x && a.indexOf(x) === i; }).join('، ');
      return { id: str(r.id), name: str(r.name) || 'مكتب بلا اسم', place: place, founded: isNum(r.founded_year) ? ar(r.founded_year).replace(/٬/g, '') : '', status: st,
               statusText: ORG_STATUS[st] || 'حالة غير معروفة', regUrl: url, regVerified: verified, verifiedBy: reg ? str(reg.verified_by) : '', members: members.length,
               membersText: members.length ? U(members.length, ['عضو واحد', 'عضوان', 'أعضاء', 'عضوًا']) : 'بلا أعضاء', badge: !!r.badge,
               canVerify: !!url && !verified && st !== 'suspended', blockedText: !url ? 'لم يرفع سجله التجاري بعد' : (verified ? 'سُجّل توثيق السجل' : (st === 'suspended' ? 'المكتب موقوف' : '')),
               when: when(r.created_at, now), lawyers: members.filter(function (m) { return m.verified_lawyer; }).length };
    });
    return { rows: rows, total: isNum(resp.total) ? resp.total : rows.length,
             countText: rows.length ? U(rows.length, ['مكتب واحد ينتظر', 'مكتبان ينتظران', 'مكاتب تنتظر', 'مكتبًا ينتظر']) : 'لا مكاتب تنتظر' };
  }
  function verifyError(status, data) {
    var msg = data && typeof data.error === 'string' ? data.error : '';
    if (data && data.no_reply) return msg;
    if (status === 422) return arDigits(msg || 'المكتب لم يرفع سجله التجاري بعد');
    if (status === 404) return 'هذا المكتب لم يعد موجودًا على المنصة';
    return 'تعذّر توثيق السجل، حاول مرة أخرى';
  }
  function verifyDone(res) { return res && res.already ? 'كان السجل موثّقًا من قبل' : 'تم توثيق السجل، والمكتب مفعّل'; }

  // ------------------------------------------------------------------ ٤ · الطلبات المفتوحة (قراءة فقط)
  function openRequests(resp, now) {
    if (!resp || !Array.isArray(resp.items)) return null;
    var rows = resp.items.filter(function (r) { return r && typeof r === 'object' && str(r.id) && r.kind !== 'training_offer' && !r.is_test && r.status !== 'closed' && r.status !== 'matched'; })
      .map(function (r) {
        var offers = isNum(r.offer_count) ? r.offer_count : 0, files = isNum(r.attachment_count) ? r.attachment_count : 0, seen = isNum(r.attachment_access_count) ? r.attachment_access_count : 0;
        return { id: str(r.id), title: str(r.title) || 'طلب بلا عنوان', service: str(r.service_name) || (str(r.service_slug) ? str(r.service_slug) : ''), country: countryLabel(r.applicable_country),
                 offers: offers, offersText: offers ? U(offers, ['عرض واحد', 'عرضان', 'عروض', 'عرضًا']) : 'بلا عروض',
                 files: files, seen: seen, filesText: files ? (U(files, ['مرفق واحد', 'مرفقان', 'مرفقات', 'مرفقًا']) + '، ' + (seen ? 'فُتح ' + U(seen, ['مرة واحدة', 'مرتين', 'مرات', 'مرة']) : 'لم يُفتح بعد')) : 'بلا مرفقات',
                 when: when(r.created_at, now), ts: ms(r.created_at), hidden: !!r.hidden };
      });
    rows.sort(function (a, b) { return (isNaN(b.ts) ? 0 : b.ts) - (isNaN(a.ts) ? 0 : a.ts); });
    var total = isNum(resp.total) ? resp.total : rows.length;
    return { rows: rows, total: total, countText: rows.length ? U(rows.length, ['طلب واحد مفتوح', 'طلبان مفتوحان', 'طلبات مفتوحة', 'طلبًا مفتوحًا']) : 'لا طلبات مفتوحة' };
  }

  // ------------------------------------------------------------------ ٥ · الترخيص عند القبول
  var FILE_RE = /\/bridge\/market\/licence-files\/([A-Za-z0-9_-]{8,64})(?:[?#].*)?$/;
  function licenceFileId(url) { var m = FILE_RE.exec(str(url)); return m ? m[1] : ''; }
  // answers من طلب الانضمام ⇒ {country, countryName, fileId, bar}. بلد الطلب مسبقًا من `licence_country`.
  function licenceOf(answers) {
    var a = answers && typeof answers === 'object' ? answers : {};
    var c = str(a.licence_country).toUpperCase();
    return { country: /^[A-Z]{2}$/.test(c) ? c : '', countryName: str(a.licence_country_name), fileId: licenceFileId(a.licence), bar: str(a.bar_number) };
  }
  function countryOptions() { return COUNTRIES.map(function (c) { return { code: c[0], label: c[1] }; }); }
  // اختيار المراجِع ⇒ قائمة ISO-2 نظيفة بلا تكرار (حتى ١٢ كما تقبل المنصة).
  function licensedCountries(codes) {
    var out = [];
    (Array.isArray(codes) ? codes : []).forEach(function (c) { c = str(c).toUpperCase(); if (/^[A-Z]{2}$/.test(c) && out.indexOf(c) < 0) out.push(c); });
    if (out.length > 12) return { ok: false, error: 'اختر حتى ١٢ بلدًا' };
    return { ok: true, list: out };
  }
  function licenceLine(row) {
    var o = row && row.licence ? row.licence : { country: '', fileId: '' };
    var parts = [];
    if (o.country) parts.push('بلد القيد المكتوب في الطلب: ' + (o.country === 'XX' && o.countryName ? o.countryName : countryLabel(o.country)));
    if (o.bar) parts.push('رقم القيد: ' + arDigits(o.bar));
    return line(parts);
  }
  var FILE_ERR = { 404: 'ملف الترخيص غير موجود', 422: 'تعذّر عرض هذا الملف', other: 'تعذّر جلب ملف الترخيص، حاول مرة أخرى' };
  function fileError(status) { return FILE_ERR[status] || FILE_ERR.other; }

  L.v2sMarket4 = {
    SERVICE_TYPES: SERVICE_TYPES, SPECIALTIES: SPECIALTIES, COUNTRIES: COUNTRIES, CURRENCIES: CURRENCIES, CUR_NAME: CUR_NAME, OTHER: OTHER,
    arDigits: arDigits, fixSep: fixSep, line: line, typeLabel: typeLabel, specialtyLabel: specialtyLabel, countryLabel: countryLabel,
    suggestions: suggestions, suggestionDecision: suggestionDecision, decideError: decideError, decideDone: decideDone,
    catalog: catalog, parseWhole: parseWhole, anchorCheck: anchorCheck, anchorInputs: anchorInputs, anchorDiff: anchorDiff, anchorError: anchorError, catalogQuery: catalogQuery,
    rangeText: rangeText, orgs: orgs, verifyError: verifyError, verifyDone: verifyDone, openRequests: openRequests,
    licenceFileId: licenceFileId, licenceOf: licenceOf, countryOptions: countryOptions, licensedCountries: licensedCountries, licenceLine: licenceLine, fileError: fileError
  };
  if (typeof module !== 'undefined' && module.exports) module.exports.v2sMarket4 = L.v2sMarket4;
})(typeof window !== 'undefined' ? window : (typeof globalThis !== 'undefined' ? globalThis : this));

/* ============================================================================
 * v2s/market4.js — «إدارة السوق» داخل قسم «سوق الخدمات» (السوق v4): مربّعات بصور (كاشير المطاعم) وكل مربّع يفتح مهمة واحدة:
 *   اقتراحات الخدمات («أخرى») · مدى الأسعار (سبع عملات) · المكاتب («وثّق السجل») · الطلبات المفتوحة (قراءة فقط).
 * والقطعة الخامسة (بلاد القيد وعرض ملف الترخيص عند قبول طلب الانضمام) كتلة مشتركة `V2S_MARKET4.licence*` تستعملها شاشة «الناس» والوارد.
 * ⛔ لا منطق عمل هنا: كل التحقق والنصوص والتصنيف من `V2L.v2sMarket4` (v2s/market4_logic.js). ولا طلب شبكة إلا `/api/v2/market/*` (بروكسيات أدمن).
 * ⛔ كل كتابة تمرّ على ورقة تأكيد وتذهب بـ`confirmed:true`. مفيش confirm()/alert()/prompt() ولا حفظ في المتصفح.
 * ⛔ المفتاح مقفول افتراضيًا: الملف بيتحمّل دايمًا لكنه ما بيرسم شيئًا إلا لو index.html نادى `render` (والغلاف الجديد شغّال).
 * ========================================================================== */
(function () {
  'use strict';
  if (typeof window === 'undefined' || typeof document === 'undefined') return;     // node (اختبارات المنطق): لا واجهة
  var L = window.V2L;
  if (!L || !L.v2sMarket4) return;
  var X = L.v2sMarket4, U = L.util, ar = U.ar;
  var M = window.V2S_MARKET4 = {};
  var MOD = 'v2s_market_v4';
  var IMG = { sug: 'content', price: 'money', firms: 'company', open: 'market' };
  var P = { sug: '/v2/market/suggestions?status=pending', orgs: '/v2/market/orgs?status=pending', open: '/v2/market/requests?status=open&lane=all&limit=100' };
  var CAT0 = X.catalogQuery({ noRange: true, q: '' });
  var S = { view: null, sub: 'hub', src: {}, noRange: true, q: '', note: '', noteT: null, nowOverride: 0, qTimer: null, retryT: null, minute: null };

  function esc(s) { return String(s == null ? '' : s).replace(/[&<>"']/g, function (c) { return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]; }); }
  function host() { return window.V2_HOST || {}; }
  function ep() { return window.EP || null; }
  function img(n) { return 'v2/img/' + n + '.jpg'; }
  function nowMs() { return S.nowOverride || Date.now(); }
  function roleName() { try { if (typeof role !== 'undefined') return role; } catch (e) {} var E = ep(); return (E && E.role) || ''; }
  M.canWrite = function () { return roleName() === 'admin'; };
  M.owns = function (mod) { return !!(mod === MOD && window.V2_ON && window.V2SHELL && window.V2SHELL.on); };
  function isCurrent() { return !!(S.view && document.body.contains(S.view) && host().current && M.owns(host().current())); }
  function q1(sel, root) { return (root || document).querySelector(sel); }
  function qa(sel, root) { return Array.prototype.slice.call((root || document).querySelectorAll(sel)); }

  // ------------------------------------------------------------------ المصادر (كل مصدر: حالته وبياناته)
  function src(k) { return S.src[k] || (S.src[k] = { state: 'idle', data: null, status: 0, seq: 0 }); }
  function load(k, path, force) {
    var s = src(k), E = ep();
    if (!E || !E.api || !E.authed) return;
    if (!force && s.state !== 'idle') return;
    if (s.state === 'idle') s.state = 'loading';
    var seq = ++s.seq;
    E.api(path).then(function (d) {
      if (seq !== s.seq) return;
      s.state = 'ready'; s.data = d; s.status = 200; changed();
    }).catch(function (e) {
      if (seq !== s.seq || (e && e.status === 401)) return;
      s.state = e && e.status === 404 ? 'closed' : 'error'; s.status = (e && e.status) || 0; s.data = null; changed();
    });
  }
  function catPath() { return X.catalogQuery({ noRange: S.noRange, q: S.q }); }
  function loadAll(force) {
    load('sug', P.sug, force); load('orgs', P.orgs, force); load('open', P.open, force); load('cat:' + CAT0, CAT0, force);
    if (S.sub === 'price' && catPath() !== CAT0) load('cat:' + catPath(), catPath(), force);
  }
  function reloadAfterWrite() {
    load('sug', P.sug, true); load('orgs', P.orgs, true); load('open', P.open, true); load('cat:' + CAT0, CAT0, true);
    if (catPath() !== CAT0) load('cat:' + catPath(), catPath(), true);
  }
  var drawT = null;
  function changed() { if (drawT) return; drawT = setTimeout(function () { drawT = null; redraw(); }, 0); }
  function modalOpen() { return !!document.getElementById('epModal'); }
  function redraw() {
    if (!isCurrent()) return;
    if (modalOpen()) {                                   // لا نمسح ما يكتبه المؤسس في ورقة مفتوحة؛ نلحق بعد إغلاقها
      if (!S.retryT) S.retryT = setInterval(function () { if (modalOpen()) return; clearInterval(S.retryT); S.retryT = null; redraw(); }, 400);
      return;
    }
    if (S.sub === 'price') drawKeep(); else draw(S.view);
  }
  function setNote(t) { S.note = t; clearTimeout(S.noteT); S.noteT = setTimeout(function () { S.note = ''; redraw(); }, 9000); }

  // ------------------------------------------------------------------ نماذج العرض من المصادر
  function viewSug() { var s = src('sug'); return s.state === 'ready' ? X.suggestions(s.data, nowMs()) : null; }
  function viewCat(key) { var s = src(key); return s.state === 'ready' ? X.catalog(s.data) : null; }
  function viewOrgs() { var s = src('orgs'); return s.state === 'ready' ? X.orgs(s.data, nowMs()) : null; }
  function viewOpen() { var s = src('open'); return s.state === 'ready' ? X.openRequests(s.data, nowMs()) : null; }

  // ------------------------------------------------------------------ أجزاء مشتركة
  function stateBlock(key, what) {
    var s = src(key);
    if (s.state === 'idle' || s.state === 'loading') return '<div class="m4-skel" role="status" aria-label="جارٍ التحميل"><i></i><i></i><i></i></div>';
    if (s.state === 'closed') return '<div class="m4-empty"><b>' + esc(what) + ' غير متاح بعد على المنصة</b><p>سيظهر هنا تلقائيًا حين يصبح متاحًا</p></div>';
    return '<div class="m4-warn" role="alert">تعذّر جلب ' + esc(what) + '، وليس معناه أنه لا شيء ينتظرك<button type="button" class="ep-bs" data-a="retry">أعد المحاولة</button></div>';
  }
  function back(title, sub) {
    return '<div class="m4-bar"><button type="button" class="ep-bs m4-back" data-a="hub">→ إدارة السوق</button></div>'
      + '<header class="m4-head"><span class="m4-himg" style="background-image:url(' + img(IMG[S.sub]) + ')" role="img" aria-label="' + esc(title) + '"></span><div><h2>' + esc(title) + '</h2>' + (sub ? '<p>' + esc(sub) + '</p>' : '') + '</div></header>';
  }
  function noteHtml() { return S.note ? '<p class="m4-note" role="status">' + esc(S.note) + '</p>' : ''; }

  // ------------------------------------------------------------------ الرئيسية: أربعة مربّعات
  function tileCount(key, getter) {
    var s = src(key);
    if (s.state === 'ready') { var v = getter(); return v == null ? { n: '—', sub: 'غير متاح بعد', off: true } : v; }
    if (s.state === 'error' || s.state === 'closed') return { n: '—', sub: 'غير متاح بعد', off: true };
    return { n: '…', sub: 'جارٍ التحميل', off: true, loading: true };
  }
  function tiles() {
    var sug = tileCount('sug', function () { var v = viewSug(); return v ? { n: ar(v.pending), sub: v.pending ? 'تنتظر قرارك' : 'لا شيء ينتظر', hot: v.pending > 0 } : null; });
    var price = tileCount('cat:' + CAT0, function () { var v = viewCat('cat:' + CAT0); return v && v.noRangeCount != null ? { n: ar(v.noRangeCount), sub: v.noRangeCount ? 'خدمة بلا مدى سعر' : 'كل الخدمات لها مدى', hot: v.noRangeCount > 0 } : null; });
    var firms = tileCount('orgs', function () { var v = viewOrgs(); return v ? { n: ar(v.rows.length), sub: v.rows.length ? 'مكتب ينتظر التوثيق' : 'لا مكاتب تنتظر', hot: v.rows.length > 0 } : null; });
    var open = tileCount('open', function () { var v = viewOpen(); return v ? { n: ar(v.rows.length), sub: v.rows.length ? 'طلب مفتوح الآن' : 'لا طلبات مفتوحة', hot: false } : null; });
    var defs = [['sug', 'اقتراحات الخدمات', sug], ['price', 'مدى الأسعار', price], ['firms', 'المكاتب', firms], ['open', 'الطلبات المفتوحة', open]];
    return '<div class="m4-tiles" role="list">' + defs.map(function (d) {
      var t = d[2];
      return '<button type="button" class="m4-tile' + (t.hot ? ' hot' : '') + (t.off ? ' off' : '') + '" role="listitem" data-a="go" data-sub="' + d[0] + '">'
        + '<span class="m4-timg" style="background-image:url(' + img(IMG[d[0]]) + ')" role="img" aria-label="' + esc(d[1]) + '"></span>'
        + '<span class="m4-tbody"><b class="m4-n">' + esc(t.n) + '</b><span class="m4-tname">' + esc(d[1]) + '</span><small>' + esc(t.sub) + '</small></span></button>';
    }).join('') + '</div>';
  }
  function anyFailed() { return ['sug', 'orgs', 'open', 'cat:' + CAT0].some(function (k) { var st = src(k).state; return st === 'error' || st === 'closed'; }); }
  function drawHub(v) {
    var warn = anyFailed() ? '<div class="m4-warn" role="status">بعض الأرقام غير متاحة الآن<button type="button" class="ep-bs" data-a="retry">أعد المحاولة</button></div>' : '';
    v.innerHTML = '<div class="v2s-m4" data-board="m4-hub">' + noteHtml() + '<p class="m4-lead">اختر ما تريد مراجعته</p>' + warn + tiles() + '</div>';
  }

  // ------------------------------------------------------------------ ١ · اقتراحات الخدمات
  function drawSug(v) {
    var d = viewSug(), body;
    if (!d) body = stateBlock('sug', 'اقتراحات الخدمات');
    else if (!d.rows.length) body = '<div class="m4-empty"><b>لا اقتراحات تنتظر</b><p>حين يقترح أحد خدمة جديدة تظهر هنا لتقرر فيها</p></div>';
    else body = '<ul class="m4-cards">' + d.rows.map(function (r) {
      return '<li class="m4-card" data-id="' + esc(r.id) + '"><div class="m4-ch"><h3>' + esc(r.name) + '</h3><span class="m4-st">' + esc(r.statusText) + '</span></div>'
        + (r.note ? '<p class="m4-nt">' + esc(r.note) + '</p>' : '<p class="m4-nt mute">بلا ملاحظة مكتوبة</p>')
        + '<p class="m4-meta"><span class="m4-who" dir="ltr">' + esc(r.who || '—') + '</span>' + (r.when ? '<span>' + esc(r.when) + '</span>' : '') + '</p>'
        + (r.open ? '<div class="m4-acts"><button type="button" class="ep-b1" data-a="sapprove" data-id="' + esc(r.id) + '">اعتمد</button><button type="button" class="ep-b2" data-a="sreject" data-id="' + esc(r.id) + '">ارفض</button></div>' : '')
        + '</li>';
    }).join('') + '</ul>';
    v.innerHTML = '<div class="v2s-m4" data-board="m4-sug">' + noteHtml() + back('اقتراحات الخدمات', d ? d.countText : '') + body + '</div>';
  }

  // ------------------------------------------------------------------ أوراق التأكيد
  function sheet(title, html) {
    if (typeof window.openModal !== 'function') return null;
    var s = window.openModal(title, '<div class="v3m v2s-m4-sb">' + html + '</div>');
    s.classList.add('v2s-m4-sh');
    var x = s.querySelector('[data-x]');
    if (x) { x.setAttribute('aria-label', 'إغلاق'); x.onclick = function () { if (!s.dataset.busy) window.closeModal(); }; }
    s.onclick = function (e) { if (e.target === s && !s.dataset.busy) window.closeModal(); };
    return s;
  }
  function plain401(e) { return e && e.status === 401; }
  // يشغّل كتابة واحدة داخل ورقة: يقفل الأزرار، وعند النجاح يغلق ويعيد التحميل، وعند الفشل يكتب السبب في الورقة ويفتح الأزرار.
  function runWrite(s, goBtn, noBtn, errBox, label, send, errText, onOk) {
    if (s.dataset.busy) return;
    s.dataset.busy = '1'; goBtn.disabled = true; if (noBtn) noBtn.disabled = true; goBtn.textContent = 'جارٍ التنفيذ…'; errBox.innerHTML = '';
    Promise.resolve(send()).then(function (res) {
      delete s.dataset.busy; window.closeModal(); onOk(res || {}); reloadAfterWrite(); redraw();
    }).catch(function (e) {
      delete s.dataset.busy; goBtn.disabled = false; if (noBtn) noBtn.disabled = false; goBtn.textContent = label;
      errBox.innerHTML = '<div class="m4-err" role="alert">' + esc(plain401(e) ? 'انتهت الجلسة، سجّل الدخول من جديد ثم جرّب' : errText(e && e.status, e && e.data)) + '</div>';
    });
  }
  function api(path, body, method) { return ep().api(path, { method: method || 'POST', body: body }); }
  function byId(list, id) { for (var i = 0; i < list.length; i++) if (list[i].id === id) return list[i]; return null; }

  // اعتماد اقتراح: النوع والتخصص والنطاق، وفي كلٍّ «أخرى»
  function approveSheet(r) {
    function opts(list, ph) {
      return '<option value="">' + esc(ph) + '</option>' + list.map(function (o) { return '<option value="' + o[0] + '">' + esc(o[1]) + '</option>'; }).join('') + '<option value="other">أخرى</option>';
    }
    var s = sheet('اعتماد الاقتراح', '<p class="mc-lead">ستُضاف «' + esc(r.name) + '» إلى قائمة الخدمات، ويصل لصاحب الاقتراح إشعار وطلب تقديم الخدمة باسمه.</p>'
      + '<div class="fld"><label for="m4Type">نوع الخدمة</label><select id="m4Type">' + opts(X.SERVICE_TYPES, 'اختر النوع') + '</select><small id="m4TypeH" aria-live="polite"></small></div>'
      + '<div class="fld"><label for="m4Spec">التخصص</label><select id="m4Spec">' + opts(X.SPECIALTIES, 'اختر التخصص') + '</select><small id="m4SpecH" aria-live="polite"></small></div>'
      + '<fieldset class="m4-scope"><legend>نطاق الخدمة</legend>'
      + '<label class="m4-radio"><input type="radio" name="m4sc" value="note" checked><span><b>كما كتبه صاحب الاقتراح</b>' + (r.note ? '<small>' + esc(r.note.length > 140 ? r.note.slice(0, 140) + '…' : r.note) + '</small>' : '<small>بلا ملاحظة مكتوبة، فيُكتب اسم الخدمة</small>') + '</span></label>'
      + '<label class="m4-radio"><input type="radio" name="m4sc" value="other"><span><b>أخرى: أكتب النطاق بنفسي</b></span></label>'
      + '<div class="fld" id="m4ScopeBox" hidden><label for="m4Scope">النطاق</label><textarea id="m4Scope" maxlength="600" rows="3"></textarea></div></fieldset>'
      + '<div id="m4Err" role="alert"></div><div class="acts"><button type="button" class="ep-b1" id="m4Go">اعتمد الخدمة</button><button type="button" class="ep-b2" id="m4No">رجوع</button></div>');
    if (!s) return;
    var type = q1('#m4Type', s), spec = q1('#m4Spec', s), box = q1('#m4ScopeBox', s), err = q1('#m4Err', s), go = q1('#m4Go', s), no = q1('#m4No', s);
    type.onchange = function () { q1('#m4TypeH', s).textContent = type.value === 'other' ? 'تُسجَّل الآن ضمن «رأي قانوني مكتوب»' : ''; };
    spec.onchange = function () { q1('#m4SpecH', s).textContent = spec.value === 'other' ? 'تُسجَّل الآن ضمن «عام / غير محدد»' : ''; };
    qa('input[name="m4sc"]', s).forEach(function (rd) { rd.onchange = function () { box.hidden = rd.value !== 'other' || !rd.checked; if (!box.hidden) q1('#m4Scope', s).focus(); }; });
    no.onclick = function () { if (!s.dataset.busy) window.closeModal(); };
    go.onclick = function () {
      var mode = (q1('input[name="m4sc"]:checked', s) || {}).value || 'note';
      var res = X.suggestionDecision({ decision: 'approve', type: type.value, specialty: spec.value, scopeMode: mode, scope: q1('#m4Scope', s).value });
      if (!res.ok) { err.innerHTML = '<div class="m4-err" role="alert">' + esc(res.error) + '</div>'; return; }
      var body = res.body; body.confirmed = true;
      runWrite(s, go, no, err, 'اعتمد الخدمة', function () { return api('/v2/market/suggestions/' + encodeURIComponent(r.id) + '/decide', body); }, X.decideError,
        function (out) { setNote(X.decideDone('approve', out)); });
    };
    setTimeout(function () { try { type.focus(); } catch (e) {} }, 30);
  }
  function rejectSheet(r) {
    var s = sheet('رفض الاقتراح', '<p class="mc-lead">سيصل لصاحب الاقتراح إشعار بأننا لم نتمكن من إضافة «' + esc(r.name) + '» الآن، بلا ذكر سبب. هل تريد الرفض؟</p>'
      + '<div id="m4Err" role="alert"></div><div class="acts"><button type="button" class="ep-b1" id="m4Go">ارفض الاقتراح</button><button type="button" class="ep-b2" id="m4No">رجوع</button></div>');
    if (!s) return;
    var go = q1('#m4Go', s), no = q1('#m4No', s), err = q1('#m4Err', s);
    no.onclick = function () { if (!s.dataset.busy) window.closeModal(); };
    go.onclick = function () {
      runWrite(s, go, no, err, 'ارفض الاقتراح', function () { return api('/v2/market/suggestions/' + encodeURIComponent(r.id) + '/decide', { decision: 'reject', confirmed: true }); }, X.decideError,
        function (out) { setNote(X.decideDone('reject', out)); });
    };
    setTimeout(function () { try { no.focus(); } catch (e) {} }, 30);
  }

  // ------------------------------------------------------------------ ٢ · مدى الأسعار
  function drawPrice(v) {
    var key = 'cat:' + catPath(), d = viewCat(key), all = viewCat('cat:' + CAT0), body;
    var chip = '<button type="button" class="m4-chip' + (S.noRange ? ' on' : '') + '" data-a="norange" aria-pressed="' + S.noRange + '">بلا مدى فقط' + (all && all.noRangeCount != null ? ' (' + ar(all.noRangeCount) + ')' : '') + '</button>';
    var search = '<div class="m4-search" role="search"><label for="m4q">ابحث في الخدمات</label><div class="m4-sbox"><input id="m4q" type="search" maxlength="120" autocomplete="off" placeholder="اسم الخدمة" value="' + esc(S.q) + '"><button type="button" class="ep-b1" data-a="qgo">ابحث</button></div></div>';
    if (!d) body = stateBlock(key, 'الخدمات');
    else if (!d.rows.length) body = '<div class="m4-empty"><b>' + esc(S.q || S.noRange ? 'لا خدمات تطابق هذا الاختيار' : 'لا خدمات في القائمة') + '</b>' + ((S.q || S.noRange) ? '<p></p><button type="button" class="ep-b2" data-a="qclear">امسح الاختيار</button>' : '') + '</div>';
    else body = '<p class="m4-count">' + esc(U.U(d.rows.length, ['خدمة واحدة', 'خدمتان', 'خدمات', 'خدمة'])) + (d.total > d.rows.length ? ' من ' + esc(ar(d.total)) : '') + '</p><ul class="m4-cards price">' + d.rows.map(function (r) {
      var btn = !r.canEdit ? '<span class="m4-st fixed">سعر ثابت</span>' : '<button type="button" class="' + (r.hasRange ? 'ep-b2' : 'ep-b1') + '" data-a="edit" data-slug="' + esc(r.slug) + '">' + (r.hasRange ? 'عدّل المدى' : 'حدّد المدى') + '</button>';
      return '<li class="m4-card" data-slug="' + esc(r.slug) + '"><div class="m4-ch"><h3>' + esc(r.name) + '</h3>' + btn + '</div>'
        + '<p class="m4-meta"><span>' + esc(r.type) + '</span><span>' + esc(r.specialty) + '</span>' + (r.licensed ? '<span class="m4-tag">مرخَّصة</span>' : '') + '</p>'
        + '<p class="m4-range' + (r.hasRange ? '' : ' none') + '">' + esc(r.text) + '</p></li>';
    }).join('') + '</ul>';
    v.innerHTML = '<div class="v2s-m4" data-board="m4-price">' + noteHtml() + back('مدى الأسعار', all && all.noRangeText ? all.noRangeText : '') 
      + '<div class="m4-ctl">' + chip + '</div>' + search + '<div id="m4PriceBody" aria-live="polite">' + body + '</div></div>';
    var inp = q1('#m4q', v);
    if (inp) {
      inp.addEventListener('input', function () { clearTimeout(S.qTimer); S.qTimer = setTimeout(function () { applyQ(inp.value); }, 450); });
      inp.addEventListener('keydown', function (e) { if (e.key === 'Enter') { e.preventDefault(); clearTimeout(S.qTimer); applyQ(inp.value); } });
    }
  }
  function applyQ(val) {
    var t = String(val || '').trim().slice(0, 120);
    if (t === S.q) return;
    S.q = t; loadAll(false); drawKeep();
  }
  // يعيد رسم النتائج فقط (بدون هدم خانة البحث أثناء الكتابة)
  function drawKeep() {
    if (!isCurrent() || S.sub !== 'price') return;
    var host2 = q1('#m4PriceBody', S.view);
    if (!host2) return draw(S.view);
    var focused = document.activeElement && document.activeElement.id === 'm4q';
    if (!focused) return draw(S.view);
    var tmp = document.createElement('div'); draw(tmp);
    var nb = q1('#m4PriceBody', tmp); if (nb) host2.innerHTML = nb.innerHTML;
  }
  function editSheet(slug) {
    var key = 'cat:' + catPath(), d = viewCat(key) || viewCat('cat:' + CAT0), row = null;
    if (d) for (var i = 0; i < d.rows.length; i++) if (d.rows[i].slug === slug) row = d.rows[i];
    if (!row || !row.canEdit) return;
    var inputs = X.anchorInputs(row.range);
    var s = sheet('مدى السعر', '<div id="m4Stage"></div>');
    if (!s) return;
    var stage = q1('#m4Stage', s);
    function collect() {
      var out = {};
      X.CURRENCIES.forEach(function (c) { out[c] = { min: q1('#m4min_' + c, s).value, max: q1('#m4max_' + c, s).value }; });
      return out;
    }
    function showChecks(r, submit) {
      X.CURRENCIES.forEach(function (c) {
        var i2 = collect()[c], both = String(i2.min).trim() !== '' && String(i2.max).trim() !== '';
        var e = q1('#m4e_' + c, s), msg = '', cls = '';
        if (r.errors[c] && (submit || both)) { msg = r.errors[c]; cls = 'bad'; }
        else if (r.warns[c]) { msg = r.warns[c]; cls = 'warn'; }
        e.textContent = msg; e.className = 'm4-ce' + (cls ? ' ' + cls : '');
        q1('#m4row_' + c, s).classList.toggle('bad', cls === 'bad');
      });
    }
    function form() {
      s.dataset.stage = 'form';
      stage.innerHTML = '<p class="mc-lead">' + esc(row.name) + '</p><p class="m4-fine">أرقام صحيحة بلا كسور، والأدنى أقل من الأعلى. اترك العملة فارغة إن لم يكن لها مدى.</p>'
        + '<div class="m4-curs">' + X.CURRENCIES.map(function (c) {
          return '<div class="m4-cur" id="m4row_' + c + '"><b>' + esc(X.CUR_NAME[c]) + '</b><div class="m4-cf">'
            + '<label for="m4min_' + c + '">الأدنى</label><input id="m4min_' + c + '" inputmode="numeric" autocomplete="off" value="' + esc(inputs[c].min) + '">'
            + '<label for="m4max_' + c + '">الأعلى</label><input id="m4max_' + c + '" inputmode="numeric" autocomplete="off" value="' + esc(inputs[c].max) + '"></div>'
            + '<p class="m4-ce" id="m4e_' + c + '" role="alert"></p></div>';
        }).join('') + '</div><div id="m4Err" role="alert"></div>'
        + '<div class="acts"><button type="button" class="ep-b1" id="m4Next">راجع ثم احفظ</button>'
        + (row.hasRange ? '<button type="button" class="ep-bs m4-clear" id="m4Clear">امسح المدى</button>' : '') + '<button type="button" class="ep-b2" id="m4No">رجوع</button></div>';
      qa('input', stage).forEach(function (el) { el.addEventListener('input', function () { inputs = collect(); showChecks(X.anchorCheck(inputs), false); }); });
      showChecks(X.anchorCheck(inputs), false);
      q1('#m4No', s).onclick = function () { if (!s.dataset.busy) window.closeModal(); };
      q1('#m4Next', s).onclick = function () {
        inputs = collect();
        var r = X.anchorCheck(inputs);
        showChecks(r, true);
        if (!r.ok) { q1('#m4Err', s).innerHTML = '<div class="m4-err" role="alert">' + esc(r.error) + '</div>'; return; }
        review(r.payload, r.warns);
      };
      var cl = q1('#m4Clear', s);
      if (cl) cl.onclick = function () { review(null, {}); };
      var first = qa('input', stage)[0]; if (first) setTimeout(function () { try { first.focus(); } catch (e) {} }, 30);
    }
    function review(payload, warns) {
      s.dataset.stage = 'review';
      var lines = X.anchorDiff(row.range, payload);
      var warnLines = Object.keys(warns || {}).map(function (c) { return '<li class="warn">' + esc(X.CUR_NAME[c] + ': ' + warns[c]) + '</li>'; }).join('');
      stage.innerHTML = '<p class="mc-lead">' + esc(payload ? 'سيُحفظ هذا المدى لـ«' + row.name + '»، ويظهر لأصحاب الطلبات والمقدّمين:' : 'سيُمسح مدى السعر كله من «' + row.name + '»، وتعود الخدمة «بلا مدى»:') + '</p>'
        + (lines.length ? '<ul class="m4-diff">' + lines.map(function (l) { return '<li><b>' + esc(l.label) + '</b><span><s>' + esc(l.from) + '</s><i aria-hidden="true">←</i><em>' + esc(l.to) + '</em></span></li>'; }).join('') + '</ul>' : '<p class="m4-fine">لا فرق عن المدى الحالي.</p>')
        + (warnLines ? '<ul class="m4-warns">' + warnLines + '</ul>' : '') + '<div id="m4Err" role="alert"></div>'
        + '<div class="acts"><button type="button" class="ep-b1" id="m4Go">' + (payload ? 'احفظ المدى' : 'امسح المدى') + '</button><button type="button" class="ep-b2" id="m4Back">ارجع للتعديل</button></div>';
      var go = q1('#m4Go', s), bk = q1('#m4Back', s), err = q1('#m4Err', s);
      bk.onclick = function () { if (!s.dataset.busy) form(); };
      go.onclick = function () {
        runWrite(s, go, bk, err, payload ? 'احفظ المدى' : 'امسح المدى', function () {
          return api('/v2/market/catalog/' + encodeURIComponent(row.slug) + '/anchor', { anchor_range: payload, confirmed: true }, 'PUT');
        }, X.anchorError, function () { setNote(payload ? 'حُفظ مدى السعر' : 'مُسح مدى السعر'); });
      };
      setTimeout(function () { try { bk.focus(); } catch (e) {} }, 30);
    }
    form();
  }

  // ------------------------------------------------------------------ ٣ · المكاتب
  function drawFirms(v) {
    var d = viewOrgs(), body;
    if (!d) body = stateBlock('orgs', 'المكاتب');
    else if (!d.rows.length) body = '<div class="m4-empty"><b>لا مكاتب تنتظر التوثيق</b><p>يظهر هنا كل مكتب جديد بعد رفع سجله التجاري</p></div>';
    else body = '<ul class="m4-cards">' + d.rows.map(function (r) {
      var reg = r.regUrl ? '<a class="m4-reg" href="' + esc(r.regUrl) + '" target="_blank" rel="noopener noreferrer">فتح السجل التجاري</a>' : '<span class="m4-reg none">لم يرفع سجله التجاري بعد</span>';
      var act = r.canVerify ? '<button type="button" class="ep-b1" data-a="verify" data-id="' + esc(r.id) + '">وثّق السجل</button>' : (r.blockedText && r.regUrl ? '<span class="m4-fine">' + esc(r.blockedText) + '</span>' : '');
      return '<li class="m4-card" data-id="' + esc(r.id) + '"><div class="m4-ch"><h3>' + esc(r.name) + '</h3><span class="m4-st">' + esc(r.statusText) + '</span></div>'
        + '<p class="m4-meta">' + (r.place ? '<span>' + esc(r.place) + '</span>' : '') + (r.founded ? '<span>تأسس عام ' + esc(r.founded) + '</span>' : '') + '<span>' + esc(r.membersText) + '</span>' + (r.when ? '<span>' + esc(r.when) + '</span>' : '') + '</p>'
        + '<div class="m4-reg-row">' + reg + '</div>' + (act ? '<div class="m4-acts">' + act + '</div>' : '') + '</li>';
    }).join('') + '</ul>';
    v.innerHTML = '<div class="v2s-m4" data-board="m4-firms">' + noteHtml() + back('المكاتب', d ? d.countText : '') + body + '</div>';
  }
  function verifySheet(r) {
    var s = sheet('توثيق السجل التجاري', '<p class="mc-lead">سيُسجَّل توثيق السجل التجاري لمكتب «' + esc(r.name) + '» ويُفعَّل المكتب. افتح السجل وراجعه قبل أن تؤكد.</p>'
      + (r.regUrl ? '<p><a class="m4-reg" href="' + esc(r.regUrl) + '" target="_blank" rel="noopener noreferrer">فتح السجل التجاري</a></p>' : '')
      + '<div id="m4Err" role="alert"></div><div class="acts"><button type="button" class="ep-b1" id="m4Go">وثّق السجل</button><button type="button" class="ep-b2" id="m4No">رجوع</button></div>');
    if (!s) return;
    var go = q1('#m4Go', s), no = q1('#m4No', s), err = q1('#m4Err', s);
    no.onclick = function () { if (!s.dataset.busy) window.closeModal(); };
    go.onclick = function () {
      runWrite(s, go, no, err, 'وثّق السجل', function () { return api('/v2/market/orgs/' + encodeURIComponent(r.id) + '/verify-reg', { confirmed: true }); }, X.verifyError,
        function (out) { setNote(X.verifyDone(out)); });
    };
    setTimeout(function () { try { no.focus(); } catch (e) {} }, 30);
  }

  // ------------------------------------------------------------------ ٤ · الطلبات المفتوحة (قراءة فقط)
  function drawOpen(v) {
    var d = viewOpen(), body;
    if (!d) body = stateBlock('open', 'الطلبات المفتوحة');
    else if (!d.rows.length) body = '<div class="m4-empty"><b>لا طلبات مفتوحة</b><p>تظهر هنا الطلبات التي تنتظر عروضًا</p></div>';
    else {
      var tb = '<div class="m4-tbw"><table class="m4-tb"><thead><tr><th>الطلب</th><th>الخدمة</th><th>البلد</th><th>العروض</th><th>المرفقات</th></tr></thead><tbody>' + d.rows.map(function (r) {
        return '<tr><td><b>' + esc(r.title) + '</b>' + (r.when ? '<small>' + esc(r.when) + '</small>' : '') + '</td><td>' + (r.service ? esc(r.service) : '<span class="mute">بلا خدمة محددة</span>') + '</td><td>' + (r.country ? esc(r.country) : '<span class="mute">—</span>') + '</td><td>' + esc(r.offersText) + '</td><td>' + esc(r.filesText) + '</td></tr>';
      }).join('') + '</tbody></table></div>';
      var cards = '<ul class="m4-cards open">' + d.rows.map(function (r) {
        return '<li class="m4-card"><div class="m4-ch"><h3>' + esc(r.title) + '</h3></div><p class="m4-meta">' + (r.service ? '<span>' + esc(r.service) + '</span>' : '<span class="mute">بلا خدمة محددة</span>') + (r.country ? '<span>' + esc(r.country) + '</span>' : '') + (r.when ? '<span>' + esc(r.when) + '</span>' : '') + '</p>'
          + '<p class="m4-facts"><span class="' + (r.offers ? '' : 'mute') + '">' + esc(r.offersText) + '</span><span class="' + (r.files ? '' : 'mute') + '">' + esc(r.filesText) + '</span></p></li>';
      }).join('') + '</ul>';
      var trunc = (src('open').data && src('open').data.total > (src('open').data.items || []).length) ? '<p class="m4-fine">معروض أحدث ' + esc(ar((src('open').data.items || []).length)) + ' من ' + esc(ar(src('open').data.total)) + ' طلبًا.</p>' : '';
      body = tb + cards + trunc;
    }
    v.innerHTML = '<div class="v2s-m4" data-board="m4-open">' + noteHtml() + back('الطلبات المفتوحة', d ? d.countText : '') + '<p class="m4-ro soft">للعرض فقط. الإغلاق والإخفاء من تبويب «الطلبات».</p>' + body + '</div>';
  }

  // ------------------------------------------------------------------ الرسم والأحداث
  function draw(v) {
    if (!v) return;
    if (!M.canWrite()) { v.innerHTML = '<div class="v2s-m4" data-board="m4-ro"><p class="m4-ro" role="status">هذا القسم للإدارة فقط</p></div>'; return; }
    if (S.sub === 'sug') drawSug(v);
    else if (S.sub === 'price') drawPrice(v);
    else if (S.sub === 'firms') drawFirms(v);
    else if (S.sub === 'open') drawOpen(v);
    else drawHub(v);
  }
  function onClick(e) {
    var a = e.target.closest ? e.target.closest('[data-a]') : null;
    if (!a || !S.view.contains(a) || a.disabled) return;
    var k = a.getAttribute('data-a'), id = a.getAttribute('data-id');
    if (k === 'go') { S.sub = a.getAttribute('data-sub'); if (S.sub === 'price') { loadAll(false); } redraw(); scrollTop(); }
    else if (k === 'hub') { S.sub = 'hub'; redraw(); scrollTop(); }
    else if (k === 'retry') { ['sug', 'orgs', 'open', 'cat:' + CAT0, 'cat:' + catPath()].forEach(function (key) { var s = src(key); if (s.state === 'error' || s.state === 'closed') { s.state = 'loading'; } }); loadAll(true); redraw(); }
    else if (k === 'sapprove' && M.canWrite()) { var r1 = byId((viewSug() || { rows: [] }).rows, id); if (r1) approveSheet(r1); }
    else if (k === 'sreject' && M.canWrite()) { var r2 = byId((viewSug() || { rows: [] }).rows, id); if (r2) rejectSheet(r2); }
    else if (k === 'verify' && M.canWrite()) { var r3 = byId((viewOrgs() || { rows: [] }).rows, id); if (r3) verifySheet(r3); }
    else if (k === 'edit' && M.canWrite()) editSheet(a.getAttribute('data-slug'));
    else if (k === 'norange') { S.noRange = !S.noRange; loadAll(false); redraw(); }
    else if (k === 'qgo') { clearTimeout(S.qTimer); var inp = q1('#m4q', S.view); applyQ(inp ? inp.value : ''); }
    else if (k === 'qclear') { S.q = ''; S.noRange = false; loadAll(false); redraw(); }
  }
  function scrollTop() { try { var c = document.querySelector('.content'); if (c) c.scrollTop = 0; window.scrollTo(0, 0); } catch (e) {} }
  M.render = function (mod, view) {
    S.view = view;
    var E = ep();
    if (E && E.authed && M.canWrite()) loadAll(false);
    view.onclick = onClick;
    draw(view);
    if (!S.minute) S.minute = setInterval(function () { if (!isCurrent()) { clearInterval(S.minute); S.minute = null; return; } if (!modalOpen() && S.sub !== 'price') redraw(); }, 60000);
  };
  M._state = S;

  // ------------------------------------------------------------------ ٥ · كتلة الترخيص المشتركة (طلب انضمام مرخَّص)
  // `row` صف الوارد (من dashboard-api.js): {licensed, licence:{country, countryName, fileId, bar}}. الكتلة تُرسم داخل شاشة القبول،
  // ومنها `selected()` ⇒ قائمة ISO-2، و«عرض ملف الترخيص» يجلب البايتات بالتوكن (صورة ⇒ data، وPDF ⇒ تنزيل).
  M.needsLicence = function (row) { return !!(row && row.apiKind === 'join' && (row.licensed || row.licensedFamily)); };
  M.licenceHtml = function (row, pre) {
    if (!M.needsLicence(row)) return '';
    pre = pre || 'm4l';
    var lic = row.licence || {}, mine = {};
    var sel = lic.country ? [lic.country] : [];
    sel.forEach(function (c) { mine[c] = 1; });
    var info = X.licenceLine(row);
    return '<fieldset class="m4-lic" id="' + pre + 'Box" data-m4lic="1"><legend>بلاد القيد المعتمدة</legend>'
      + (info ? '<p class="m4-lic-info">' + esc(info) + '</p>' : '<p class="m4-lic-info mute">لم يُذكر بلد القيد في الطلب</p>')
      + '<div class="m4-lic-grid" role="group" aria-label="بلاد القيد">' + X.countryOptions().map(function (c) {
        return '<label class="m4-lic-opt"><input type="checkbox" value="' + c.code + '"' + (mine[c.code] ? ' checked' : '') + '><span>' + esc(c.label) + '</span></label>';
      }).join('') + '</div>'
      + '<p class="m4-fine">اختر البلد أو البلاد المقيَّد فيها مقدّم الطلب بعد مراجعة الكارنيه، فلا تصله إلا طلبات هذه البلاد.</p>'
      + (lic.fileId ? '<div class="m4-lic-file"><button type="button" class="ep-b2" id="' + pre + 'View">عرض ملف الترخيص</button><div id="' + pre + 'Out" aria-live="polite"></div></div>' : '<p class="m4-fine mute">لم يُرفع ملف ترخيص مع الطلب</p>')
      + '</fieldset>';
  };
  M.licenceSelected = function (root) {
    var box = q1('[data-m4lic]', root);
    if (!box) return null;
    return qa('input[type=checkbox]:checked', box).map(function (i) { return i.value; });
  };
  // ⇒ {ok, list} | {ok:false, error}. مرخَّصة بلا بلد واحد على الأقل = لا يصلح (المقدّم يبقى مقفولًا على كل الطلبات).
  M.licenceCheck = function (root) {
    var codes = M.licenceSelected(root);
    if (codes === null) return { ok: true, list: [] };
    var r = X.licensedCountries(codes);
    if (!r.ok) return r;
    if (!r.list.length) return { ok: false, error: 'اختر بلد القيد على الأقل، أو «أخرى»' };
    return r;
  };
  M.licenceWire = function (root, row, pre) {
    pre = pre || 'm4l';
    var b = q1('#' + pre + 'View', root), out = q1('#' + pre + 'Out', root), E = ep();
    if (!b || !out || !E) return;
    var fileId = row.licence && row.licence.fileId, url = null;
    b.onclick = function () {
      if (b.dataset.busy) return;
      if (url) { out.innerHTML = ''; if (url.revoke) URL.revokeObjectURL(url.revoke); url = null; b.textContent = 'عرض ملف الترخيص'; return; }
      b.dataset.busy = '1'; b.disabled = true; b.textContent = 'جارٍ جلب الملف…'; out.innerHTML = '';
      E.api('/v2/market/licence-files/' + encodeURIComponent(fileId), { blob: true }).then(function (blob) {
        var type = String(blob && blob.type || '').toLowerCase();
        if (type.indexOf('image/') === 0) {
          var fr = new FileReader();
          fr.onload = function () {
            out.innerHTML = '<img class="m4-lic-img" alt="صورة ملف الترخيص" src="' + esc(String(fr.result)) + '">';
            url = {}; fin();
          };
          fr.onerror = function () { out.innerHTML = '<div class="m4-err" role="alert">' + esc(X.fileError(0)) + '</div>'; fin(true); };
          fr.readAsDataURL(blob);
        } else if (type === 'application/pdf') {
          var href = URL.createObjectURL(blob);
          out.innerHTML = '<p class="m4-fine">الملف بصيغة PDF.</p><a class="ep-b2 m4-lic-dl" href="' + href + '" download="licence.pdf" target="_blank" rel="noopener">نزّل الملف وافتحه</a>';
          url = { revoke: href }; fin();
        } else { out.innerHTML = '<div class="m4-err" role="alert">' + esc(X.fileError(422)) + '</div>'; fin(true); }
      }).catch(function (e) {
        if (plain401(e)) return;
        out.innerHTML = '<div class="m4-err" role="alert">' + esc(X.fileError(e && e.status)) + '</div>'; fin(true);
      });
      function fin(failed) { delete b.dataset.busy; b.disabled = false; b.textContent = failed ? 'عرض ملف الترخيص' : 'أخفِ الملف'; }
    };
  };

  (window.V2SEC = window.V2SEC || {}).market4 = { owns: M.owns, render: M.render };
})();
