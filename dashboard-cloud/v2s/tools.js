/* ============================================================================
 * v2s/tools.js — الجزء الأول: المنطق النقي لـ«الأدوات / الاستوديو» في الداشبورد (لا DOM ولا شبكة ولا ساعة خفية؛ `now` يُمرَّر صراحةً).
 *   ١) نظرة اليوم: الصرف مقابل السقف · أعمال اليوم والفاشل · حالة الإيقاف · المفاتيح (للقراءة فقط).
 *   ٢) الأدوات: الصفوف حسب المجموعة · السعر والقاعدة المجانية · تحقق السعر وحارس المضاعِف قبل أي نداء · الفروق للتأكيد.
 *   ٣) الأماكن والأنماط: صفوف كل أداة (ظاهر/غير ظاهر · محمي من الحذف) · تحقق الاسم والترتيب والوصف والصورة.
 *   ٤) الإعدادات: السقف اليومي وأعلى سقف · حدود الاستخدام · الشحن لكل عملة وسقفه · المضاعِفات وأسعار الصرف · سطر «الجاي».
 *   ٥) العيّنات: صفوف المراجعة ونصوص «سليم / أخفِ / امنع» · ٦) التقرير: الصفوف والإجماليات والشحن منفصلًا (رصيد للعميل لا إيراد).
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
  function fixSep(s) { return String(s == null ? '' : s).replace(/([\d٠-٩])\s*·\s*/g, '$1، ').replace(/\s*·\s*([\d٠-٩])/g, '، $1'); }
  function line(parts) { return fixSep(arDigits(parts.filter(function (p) { return p; }).join('، '))); }
  function ms(iso) { var t = typeof iso === 'number' ? iso : Date.parse(iso || ''); return isNaN(t) ? NaN : t; }
  function when(iso, now) { var t = ms(iso); return isNaN(t) ? '' : Un.agoText(t, now); }
  // رقم بمنازل عشرية بأرقام هندية وبلا فاصل آلاف (للخانات): ٠٫١٢
  function dec(n) { return isNum(n) ? arDigits(String(Math.round(n * 10000) / 10000)).replace('.', '٫') : ''; }
  function ceil2(n) { return Math.ceil(n * 100 - 1e-9) / 100; }

  var CURRENCIES = ['EGP', 'SAR', 'AED', 'QAR', 'KWD', 'OMR', 'USD'];
  var CUR_NAME = { EGP: 'جنيه مصري', SAR: 'ريال سعودي', AED: 'درهم إماراتي', QAR: 'ريال قطري', KWD: 'دينار كويتي', OMR: 'ريال عُماني', USD: 'دولار أمريكي' };
  var CUR_SHORT = { EGP: 'جنيه', SAR: 'ريال سعودي', AED: 'درهم', QAR: 'ريال قطري', KWD: 'دينار كويتي', OMR: 'ريال عُماني', USD: 'دولار' };
  var DEFAULT_RATES = { EGP: 50, SAR: 3.75, AED: 3.67, QAR: 3.64, KWD: 0.31, OMR: 0.385, USD: 1 };
  var GROUPS = [['photo', 'صورتك'], ['social', 'لينكدإن والسوشيال'], ['video_cards', 'الفيديو والكروت']];
  var PROTECTED_KINDS = ['expert_card', 'certificate_card', 'winner_card'];
  var FREE_FIXED = ['none', 'once_per_verified_account', 'always'];

  function usdText(n) {
    if (!isNum(n)) return '';
    if (n === Math.floor(n) && n >= 0) return U(n, ['دولار واحد', 'دولاران', 'دولارات', 'دولارًا']);
    return fmt(n) + ' دولار';
  }
  function moneyLine(by) {          // {EGP:460, SAR:20} ⇒ «٤٦٠ جنيه، ٢٠ ريال سعودي» (لا جمع بين عملات)
    var parts = [];
    CURRENCIES.forEach(function (c) { if (by && isNum(by[c]) && by[c] !== 0) parts.push(fmt(by[c]) + ' ' + CUR_SHORT[c]); });
    return parts.join('، ');
  }

  // ------------------------------------------------------------------ ١ · نظرة اليوم
  var STATE_TEXT = {
    on: ['الاستوديو شغّال', 'يقبل أعمالًا جديدة ما دام الصرف دون السقف اليومي'],
    kill: ['الاستوديو متوقف يدويًا', 'لا تبدأ أعمال جديدة الآن، وتكتمل الأعمال الجارية. أعد تشغيله من هنا حين تشاء'],
    cap: ['الاستوديو في استراحة حتى الصباح', 'بلغ الصرف السقف اليومي. يعود تلقائيًا غدًا، أو ارفع السقف من «الإعدادات»']
  };
  function overview(resp) {
    if (!resp || typeof resp !== 'object' || !resp.today || typeof resp.today !== 'object') return null;
    var t = resp.today, fl = resp.flags && typeof resp.flags === 'object' ? resp.flags : {};
    var state = t.kill ? 'kill' : (t.paused ? 'cap' : 'on');
    var cap = isNum(t.cap_usd) ? t.cap_usd : null, spent = isNum(t.spent_usd) ? t.spent_usd : null;
    var pct = cap && spent != null ? Math.min(100, Math.max(0, Math.round(spent / cap * 100))) : null;
    var jobs = resp.jobs && typeof resp.jobs === 'object' ? resp.jobs : null;
    var provider = fl.provider === 'live' ? ['حيّ', 'يرسم عند مزوّد خارجي، ويُحسب كل عمل على السقف اليومي'] : (fl.provider === 'mock' ? ['تجريبي', 'الصور تُرسم داخل النظام بلا أي تكلفة'] : ['غير معروف', '']);
    var facts = [
      { k: 'وضع الرسم', v: provider[0], note: provider[1] },
      { k: 'الأدوات للأعضاء', off: !fl.tools_enabled, v: fl.tools_enabled ? 'مفتوحة' : 'مغلقة', note: fl.tools_enabled ? 'يراها من تناسبه من الأعضاء' : 'الأعضاء لا يرونها الآن. يفتحها الفريق التقني حين تقرّر' },
      { k: 'شحن الرصيد', off: !fl.topup_enabled, v: fl.topup_enabled ? 'مفتوح' : 'مغلق', note: fl.topup_enabled ? '' : 'الأدوات المدفوعة تعرض «الرصيد لا يكفي» لمن رصيده ناقص' }
    ];
    var warns = [];
    if (resp.ffmpeg === false) warns.push('الفيديو غير جاهز على الخادم بعد، فلا تُشغّل «فيديو ترند»');
    if (resp.raqm === false) warns.push('كتابة الحروف العربية على الصور غير جاهزة على الخادم بعد');
    return {
      state: state, killed: !!t.kill, paused: state !== 'on', stateText: STATE_TEXT[state][0], stateNote: STATE_TEXT[state][1],
      capText: cap == null ? '' : usdText(cap), spentText: spent == null ? '' : usdText(spent), pct: pct,
      spendLine: cap == null || spent == null ? 'الصرف غير متاح بعد' : (spent > 0 ? 'صُرف اليوم ' + usdText(spent) + ' من ' + usdText(cap) : 'لم يُصرف شيء اليوم، والسقف ' + usdText(cap)),
      remainingLine: isNum(t.remaining_usd) ? 'المتبقي ' + usdText(t.remaining_usd) : '',
      jobs: jobs ? { count: jobs.count, succeeded: jobs.succeeded, failures: jobs.failures } : null,
      jobsText: jobs ? ar(jobs.count) : '—', failText: jobs ? ar(jobs.failures) : '—', okText: jobs ? ar(jobs.succeeded) : '—',
      failHot: !!(jobs && jobs.failures > 0), facts: facts, warns: warns,
      provider: fl.provider || '', toolsEnabled: !!fl.tools_enabled
    };
  }
  var KILL_COPY = {
    stop: { title: 'إيقاف الاستوديو الآن', lead: 'سيتوقف الاستوديو فورًا عن بدء أعمال جديدة لكل الأعضاء، وتكتمل الأعمال الجارية. يمكنك إعادة تشغيله من هنا في أي وقت.', go: 'أوقف الاستوديو الآن', done: 'أُوقف الاستوديو. لا تبدأ أعمال جديدة الآن' },
    resume: { title: 'إعادة تشغيل الاستوديو', lead: 'سيعود الاستوديو لقبول أعمال جديدة ما دام صرف اليوم دون السقف.', go: 'أعد تشغيل الاستوديو', done: 'عاد الاستوديو للعمل' }
  };
  function killCopy(stop) { return stop ? KILL_COPY.stop : KILL_COPY.resume; }

  // ------------------------------------------------------------------ ٢ · الأدوات
  function freeText(rule) {
    var m = /^daily:(\d{1,3})$/.exec(str(rule));
    if (m) return 'مجانًا ' + U(+m[1], ['مرة واحدة', 'مرتين', 'مرات', 'مرة']) + ' كل يوم';
    return { none: 'بلا قاعدة مجانية', once_per_verified_account: 'مجانًا أول مرة لكل حساب موثّق', always: 'مجانية دائمًا' }[str(rule)] || 'قاعدة غير معروفة';
  }
  function priceLine(price) {
    var by = price && typeof price === 'object' ? price : {};
    var paid = CURRENCIES.filter(function (c) { return isNum(by[c]) && by[c] > 0; });
    if (!paid.length) return 'بلا سعر';
    var first = paid.indexOf('EGP') > -1 ? 'EGP' : paid[0];
    var t = fmt(by[first]) + ' ' + CUR_SHORT[first];
    if (paid.length > 1) t += '، و' + U(paid.length - 1, ['عملة أخرى', 'عملتان أخريان', 'عملات أخرى', 'عملة أخرى']);
    return t;
  }
  function recipes(resp) {
    if (!resp || !Array.isArray(resp.recipes)) return null;
    var styles = Array.isArray(resp.styles) ? resp.styles.filter(function (s) { return s && typeof s === 'object' && str(s.id); }) : [];
    var rows = resp.recipes.filter(function (r) { return r && typeof r === 'object' && str(r.id); }).map(function (r) {
      var group = str(r.group), gl = '';
      GROUPS.forEach(function (g) { if (g[0] === group) gl = g[1]; });
      var cost = isNum(r.est_cost_usd) ? r.est_cost_usd : 0, provider = r.provider !== 'none' && str(r.provider) !== '';
      var ids = Array.isArray(r.styles) ? r.styles : [];
      var own = styles.filter(function (s) { return s.recipe_id === r.id; });
      return { id: str(r.id), title: str(r.title_ar) || str(r.id), sub: str(r.sub_ar), group: group, groupLabel: gl || 'أخرى', enabled: !!r.enabled, draft: !!r.draft,
               provider: provider, providerText: provider ? 'رسم بمزوّد خارجي' : 'تصميم بالكود بلا تكلفة', video: r.output_kind === 'video',
               cost: cost, costText: provider && cost > 0 ? 'تكلفتها علينا نحو ' + usdText(cost) + ' للعمل' : (provider ? 'التكلفة التقديرية غير مكتوبة' : ''),
               price: r.price || {}, priceText: priceLine(r.price), free: str(r.free_rule) || 'none', freeText: freeText(r.free_rule),
               stylesCount: ids.length, ownCount: own.length, stylesText: ids.length ? U(ids.length, ['مكان واحد ظاهر', 'مكانان ظاهران', 'أماكن ظاهرة', 'مكانًا ظاهرًا']) : 'بلا أماكن ظاهرة',
               canEnable: ids.length > 0, updatedAt: str(r.updated_at), sort: isNum(r.sort) ? r.sort : 0 };
    });
    rows.sort(function (a, b) { return a.sort - b.sort; });
    var groups = GROUPS.map(function (g) { return { key: g[0], label: g[1], rows: rows.filter(function (r) { return r.group === g[0]; }) }; }).filter(function (g) { return g.rows.length; });
    var other = rows.filter(function (r) { return !GROUPS.some(function (g) { return g[0] === r.group; }); });
    if (other.length) groups.push({ key: 'other', label: 'أخرى', rows: other });
    var on = rows.filter(function (r) { return r.enabled; }).length;
    return { rows: rows, groups: groups, enabledCount: on, total: rows.length,
             countText: rows.length ? ar(on) + ' من ' + U(rows.length, ['أداة واحدة', 'أداتين', 'أدوات', 'أداة']) + ' شغّالة' : 'لا أدوات' };
  }
  function enableCopy(row, on, toolsOpen) {
    if (on) {
      var lines = ['ستظهر «' + row.title + '» لكل من تناسبه من الأعضاء.'];
      lines.push(row.provider ? 'كل عمل بها يُحسب على السقف اليومي، وسعرها: ' + row.priceText + '.' : 'تصميمها بالكود ولا تكلّف شيئًا.');
      if (!toolsOpen) lines.push('الأدوات ما زالت مغلقة للأعضاء، فلن يروها حتى تُفتح.');
      return { title: 'تشغيل «' + row.title + '»', lead: lines.join(' '), go: 'شغّل الأداة', done: 'شُغّلت «' + row.title + '»' };
    }
    return { title: 'إيقاف «' + row.title + '»', lead: 'ستختفي «' + row.title + '» من الاستوديو فورًا، ولن يستطيع أحد صنع أعمال جديدة بها. يمكنك تشغيلها من جديد في أي وقت.', go: 'أوقف الأداة', done: 'أُوقفت «' + row.title + '»' };
  }
  // حدّ أدنى للسعر بكل عملة = التكلفة × المضاعِف × سعر الصرف (نفس حارس المنصة). 0 = لا حارس.
  function priceMins(rec, settings) {
    var out = {}, est = isNum(rec && rec.cost) ? rec.cost : 0;
    CURRENCIES.forEach(function (c) { out[c] = 0; });
    if (!rec || !rec.provider || est <= 0) return out;
    var s = settings || {}, mult = rec.video ? (isNum(s.video_min_multiple) ? s.video_min_multiple : 2.5) : (isNum(s.image_min_multiple) ? s.image_min_multiple : 3);
    var rates = s.rates || {};
    CURRENCIES.forEach(function (c) { out[c] = ceil2(est * mult * (isNum(rates[c]) && rates[c] > 0 ? rates[c] : DEFAULT_RATES[c])); });
    return out;
  }
  // رقم عشري من خانة: أرقام هندية أو لاتينية، «٫» أو «.» للكسر، و«٬» أو «,» أو فراغ فواصل آلاف (تُحذف). ⇒ {kind:'empty'|'bad'|'num', n}
  function parseDec(text, maxPlaces) {
    var t = toLatin(text).replace(/[٬,\s]/g, '').replace(/٫/g, '.');
    if (t === '') return { kind: 'empty' };
    var places = maxPlaces == null ? 4 : maxPlaces;
    var re = places > 0 ? new RegExp('^\\d{1,9}(\\.\\d{1,' + places + '})?$') : /^\d{1,9}$/;
    if (!re.test(t)) return { kind: 'bad' };
    return { kind: 'num', n: Number(t) };
  }
  function ruleValue(form) {
    var r = str(form.rule);
    if (r !== 'daily') return r;
    var n = parseDec(form.daily, 0);
    return n.kind === 'num' && n.n >= 1 && n.n <= 999 ? 'daily:' + n.n : null;
  }
  function ruleOptions() {
    return [['none', 'بلا قاعدة مجانية'], ['once_per_verified_account', 'مجانًا أول مرة لكل حساب موثّق'], ['always', 'مجانية دائمًا'], ['daily', 'مجانًا عددًا محددًا كل يوم']];
  }
  function ruleForm(rule) {
    var m = /^daily:(\d{1,3})$/.exec(str(rule));
    return m ? { rule: 'daily', daily: ar(+m[1]) } : { rule: FREE_FIXED.indexOf(str(rule)) > -1 ? str(rule) : 'none', daily: '' };
  }
  function recipeInputs(rec) {
    var o = { price: {}, est: rec.provider ? dec(rec.cost) : '', rule: 'none', daily: '' };
    CURRENCIES.forEach(function (c) { o.price[c] = isNum(rec.price[c]) ? dec(rec.price[c]) : ''; });
    var rf = ruleForm(rec.free); o.rule = rf.rule; o.daily = rf.daily;
    return o;
  }
  // form: {price:{EGP:'٢٥'…}, est:'٠٫١٢', rule, daily} ⇒ {ok, errors, payload, error, mins}
  function recipeCheck(rec, form, settings) {
    form = form || {};
    var errors = {}, payload = { price: {} }, mins = priceMins(rec, settings);
    var rule = ruleValue(form);
    if (rule === null) errors.rule = 'اكتب عددًا صحيحًا من ١ إلى ٩٩٩';
    else if (FREE_FIXED.indexOf(rule) < 0 && !/^daily:\d{1,3}$/.test(rule)) errors.rule = 'اختر قاعدة من القائمة';
    var est = rec.cost;
    if (rec.provider) {
      var e = parseDec(form.est, 4);
      if (e.kind !== 'num' || e.n > 20) errors.est = 'اكتب التكلفة التقديرية بالدولار، رقمًا من صفر إلى ٢٠';
      else { est = e.n; payload.est_cost_usd = e.n; }
    }
    var recForMins = { provider: rec.provider, cost: est, video: rec.video };
    mins = priceMins(recForMins, settings);
    CURRENCIES.forEach(function (c) {
      var p = parseDec((form.price || {})[c], 3);
      if (p.kind !== 'num' || p.n > 100000) { errors['price_' + c] = 'اكتب السعر رقمًا من صفر إلى ١٠٠٬٠٠٠'; return; }
      payload.price[c] = p.n;
      if (p.n <= 0) {
        if (rec.provider && est > 0 && (rule === 'none' || rule === null)) errors['price_' + c] = 'السعر صفر والتكلفة أكبر من صفر. حدّد سعرًا أو اختر قاعدة مجانية';
      } else if (mins[c] > 0 && p.n + 1e-9 < mins[c]) {
        errors['price_' + c] = 'أقل سعر مسموح ' + fmt(mins[c]) + ' ' + CUR_SHORT[c];
      }
    });
    if (rule !== null && !errors.rule) payload.free_rule = rule;
    var bad = Object.keys(errors).length > 0;
    return { ok: !bad, errors: errors, payload: payload, mins: mins, error: bad ? 'صحّح الخانات المعلَّمة' : '' };
  }
  function recipeDiff(rec, payload) {
    var lines = [];
    CURRENCIES.forEach(function (c) {
      var a = isNum(rec.price[c]) ? rec.price[c] : 0, b = payload.price ? payload.price[c] : a;
      if (a !== b) lines.push({ label: 'السعر بـ' + CUR_NAME[c], from: fmt(a) + ' ' + CUR_SHORT[c], to: fmt(b) + ' ' + CUR_SHORT[c] });
    });
    if (payload.est_cost_usd != null && payload.est_cost_usd !== rec.cost) lines.push({ label: 'التكلفة التقديرية للعمل', from: usdText(rec.cost), to: usdText(payload.est_cost_usd) });
    if (payload.free_rule != null && payload.free_rule !== rec.free) lines.push({ label: 'القاعدة المجانية', from: freeText(rec.free), to: freeText(payload.free_rule) });
    return lines;
  }
  var WRITE_FAIL = { 404: 'لم تعد هذه الأداة موجودة على المنصة', other: 'تعذّر الحفظ، حاول مرة أخرى' };
  function writeError(status, data) {
    var msg = data && typeof data.error === 'string' ? data.error : '';
    if (data && (data.no_reply || data.not_saved || data.attach_failed) && msg) return arDigits(msg);     // رد المنصة الأكيد: «لم يُحفظ شيء» أو «لم يُربط»
    if (msg && (status === 409 || status === 422 || status === 404 || status === 400 || status === 413)) return arDigits(msg);
    return WRITE_FAIL[status] || WRITE_FAIL.other;
  }

  // ------------------------------------------------------------------ ٣ · الأماكن والأنماط
  function styles(resp) {
    if (!resp || !Array.isArray(resp.recipes) || !Array.isArray(resp.styles)) return null;
    var rec = recipes(resp);
    var sections = rec.rows.map(function (r) {
      var raw = resp.recipes.filter(function (x) { return x && x.id === r.id; })[0] || {};
      var shown = Array.isArray(raw.styles) ? raw.styles : [];
      var list = resp.styles.filter(function (s) { return s && s.recipe_id === r.id && str(s.id); }).map(function (s) {
        var protectedKind = PROTECTED_KINDS.indexOf(str(s.kind)) > -1;
        var codeOnly = s.uses_provider === false || !r.provider;
        return { id: str(s.id), recipeId: r.id, title: str(s.title_ar) || str(s.id), sort: isNum(s.sort) ? s.sort : 0, place: str(s.place_prompt), preview: str(s.preview_data),
                 hasPreview: !!str(s.preview_data), visible: shown.indexOf(str(s.id)) > -1, judgeOk: s.judge_ok !== false, protectedKind: protectedKind, codeOnly: codeOnly,
                 kind: str(s.kind), canDelete: !protectedKind,
                 orderText: 'الترتيب ' + ar(isNum(s.sort) ? s.sort : 0) };
      }).sort(function (a, b) { return a.sort - b.sort; });
      return { recipe: r, styles: list, canAdd: r.provider, updatedAt: r.updatedAt, enabled: r.enabled,
               countText: list.length ? U(list.length, ['تصميم واحد', 'تصميمان', 'تصاميم', 'تصميمًا']) : 'لا تصاميم' };
    });
    var total = resp.styles.filter(function (s) { return s && str(s.id); }).length;
    return { sections: sections, total: total, totalText: total ? U(total, ['تصميم واحد', 'تصميمان', 'تصاميم', 'تصميمًا']) : 'لا تصاميم' };
  }
  function styleCheck(form, creating) {
    form = form || {};
    var errors = {}, out = {};
    var t = str(form.title);
    if (!t || t.length > 60) errors.title = 'اكتب اسم المكان (حتى ٦٠ حرفًا)'; else out.title_ar = t;
    var so = parseDec(form.sort, 0);
    if (so.kind !== 'num' || so.n > 999) errors.sort = 'الترتيب رقم صحيح من ٠ إلى ٩٩٩'; else out.sort = so.n;
    if (form.hasPlace !== false) {
      var p = str(form.place);
      if (creating && !p) errors.place = 'صف المكان بجملة قصيرة';
      else if (p.length > 400) errors.place = 'الوصف حتى ٤٠٠ حرف';
      else out.place_prompt = p;
    }
    out.judge_ok = form.judge !== false;
    if (creating && !form.file) errors.file = 'اختر صورة المكان';
    var bad = Object.keys(errors).length > 0;
    return { ok: !bad, errors: errors, payload: out, error: bad ? 'صحّح الخانات المعلَّمة' : '' };
  }
  var FILE_MAX = 3 * 1024 * 1024;
  var IMG_TYPES = ['image/png', 'image/jpeg', 'image/webp'];
  function fileCheck(file) {
    if (!file) return { ok: false, error: 'اختر صورة المكان' };
    if (IMG_TYPES.indexOf(str(file.type).toLowerCase()) < 0) return { ok: false, error: 'اختر صورة بصيغة JPG أو PNG أو WebP' };
    if (!isNum(file.size) || file.size <= 0) return { ok: false, error: 'الملف فارغ' };
    if (file.size > FILE_MAX) return { ok: false, error: 'صورة المكان أكبر من ٣ ميجا' };
    return { ok: true, error: '' };
  }
  function newStyleId(rand) {
    // معرّف ثابت للنافذة الواحدة: رد ضايع ثم إعادة ضغط ⇒ المنصة ترد ٤٠٩ بدل ما تكرّر المكان. `rand` يُمرَّر (٨ خانات سداسية).
    var h = String(rand || '').toLowerCase().replace(/[^0-9a-f]/g, '').slice(0, 8);
    while (h.length < 8) h += '0';
    return 'st_' + h;
  }
  function styleDiff(before, payload) {
    var lines = [];
    if (payload.title_ar != null && payload.title_ar !== before.title) lines.push({ label: 'الاسم', from: before.title, to: payload.title_ar });
    if (payload.sort != null && payload.sort !== before.sort) lines.push({ label: 'الترتيب', from: ar(before.sort), to: ar(payload.sort) });
    if (payload.place_prompt != null && payload.place_prompt !== before.place) lines.push({ label: 'وصف المكان', from: before.place || 'بلا وصف', to: payload.place_prompt || 'بلا وصف' });
    if (payload.judge_ok != null && payload.judge_ok !== before.judgeOk) lines.push({ label: 'يناسب القضاة وأعضاء النيابة', from: before.judgeOk ? 'نعم' : 'لا', to: payload.judge_ok ? 'نعم' : 'لا' });
    if (payload.preview_data != null) lines.push({ label: 'الصورة', from: 'الصورة الحالية', to: 'صورة جديدة' });
    return lines;
  }
  function visibleCopy(st, on, recipeTitle) {
    if (on) return { title: 'إظهار «' + st.title + '»', lead: 'سيظهر هذا المكان للأعضاء في «' + recipeTitle + '».', go: 'أظهره للناس', done: 'ظهر «' + st.title + '» للناس' };
    return { title: 'إخفاء «' + st.title + '»', lead: 'سيختفي هذا المكان من «' + recipeTitle + '». يبقى محفوظًا هنا ويمكنك إظهاره لاحقًا.', go: 'أخفِه عن الناس', done: 'اختفى «' + st.title + '» عن الناس' };
  }
  function deleteCopy(st, recipeTitle) {
    return { title: 'حذف «' + st.title + '»', lead: 'سيُحذف هذا المكان نهائيًا من «' + recipeTitle + '» وتُحذف صورته، ولا يمكن التراجع. إن أردت إخفاءه فقط فاختر «أخفِه».', go: 'احذف المكان', done: 'حُذف «' + st.title + '»' };
  }
  function createDone(res) {
    if (res && res.attach_failed) return 'أُضيف المكان، لكنه لم يُربط بالأداة بعد. اضغط «أظهره للناس» عليه ليظهر';
    if (res && res.attached === false) return 'أُضيف المكان وهو غير ظاهر للناس. اضغط «أظهره للناس» حين تريد';
    return 'أُضيف المكان وظهر للناس';
  }

  // ------------------------------------------------------------------ ٤ · الإعدادات
  function settings(resp) {
    if (!resp || typeof resp !== 'object' || !isNum(resp.daily_cap_usd)) return null;
    return resp;
  }
  function settingsInputs(s) {
    var o = { cap: dec(s.daily_cap_usd), capMax: dec(s.daily_cap_max_usd), imgM: dec(s.image_min_multiple), vidM: dec(s.video_min_multiple), perUser: dec(s.per_user_daily), perIp: dec(s.per_ip_daily),
              freePosts: dec(s.free_posts_daily), sample: dec(s.sample_pct), retry: dec(s.retry_limit), tmax: dec(s.topup_max_egp), next: str(s.next_line), tmin: {}, rate: {} };
    CURRENCIES.forEach(function (c) { o.tmin[c] = dec((s.topup_min_by_currency || {})[c]); o.rate[c] = dec((s.rates || {})[c]); });
    return o;
  }
  // ⇒ {ok, errors, changes, error, lines}. `changes` فيها الحقول التي تغيّرت فقط (نفس ما يقبله الخادم).
  function settingsCheck(form, cur) {
    form = form || {}; cur = cur || {};
    var errors = {}, changes = {}, abs = isNum(cur.absolute_max_usd) ? cur.absolute_max_usd : 50;
    function whole(key, label, lo, hi, curVal, outKey) {
      var p = parseDec(form[key], 0);
      if (p.kind !== 'num' || p.n < lo || p.n > hi) { errors[key] = label + ' رقم صحيح من ' + ar(lo) + ' إلى ' + ar(hi); return null; }
      if (p.n !== curVal) changes[outKey] = p.n;
      return p.n;
    }
    var capMax = parseDec(form.capMax, 2), capMaxV = isNum(cur.daily_cap_max_usd) ? cur.daily_cap_max_usd : 20;
    if (capMax.kind !== 'num' || !(capMax.n > 0 && capMax.n <= abs)) errors.capMax = 'أعلى سقف رقم أكبر من صفر ولا يزيد على ' + usdText(abs);
    else { if (capMax.n !== cur.daily_cap_max_usd) changes.daily_cap_max_usd = capMax.n; capMaxV = capMax.n; }
    var cap = parseDec(form.cap, 2);
    if (cap.kind !== 'num' || !(cap.n > 0)) errors.cap = 'السقف اليومي رقم أكبر من صفر';
    else if (cap.n > capMaxV) errors.cap = 'السقف اليومي لا يزيد على أعلى سقف (' + usdText(capMaxV) + ')';
    else if (cap.n !== cur.daily_cap_usd) changes.daily_cap_usd = cap.n;
    ['imgM', 'vidM'].forEach(function (k) {
      var p = parseDec(form[k], 2), key = k === 'imgM' ? 'image_min_multiple' : 'video_min_multiple';
      if (p.kind !== 'num' || p.n < 1 || p.n > 20) errors[k] = 'المضاعِف رقم من ١ إلى ٢٠';
      else if (p.n !== cur[key]) changes[key] = p.n;
    });
    whole('perUser', 'حد المستخدم اليومي', 1, 200, cur.per_user_daily, 'per_user_daily');
    whole('perIp', 'حد الشبكة اليومي', 1, 1000, cur.per_ip_daily, 'per_ip_daily');
    whole('freePosts', 'عدد البوستات المجانية اليومية', 0, 50, cur.free_posts_daily, 'free_posts_daily');
    whole('sample', 'نسبة العيّنات', 0, 100, cur.sample_pct, 'sample_pct');
    whole('retry', 'إعادات المحاولة المجانية', 0, 10, cur.retry_limit, 'retry_limit');
    var tm = parseDec(form.tmax, 0);
    if (tm.kind !== 'num' || tm.n < 100 || tm.n > 10000000) errors.tmax = 'سقف الشحن رقم صحيح لا يقل عن ١٠٠ جنيه';
    else if (tm.n !== cur.topup_max_egp) changes.topup_max_egp = tm.n;
    var tmins = {}, rates = {};
    CURRENCIES.forEach(function (c) {
      var m = parseDec((form.tmin || {})[c], 0), r = parseDec((form.rate || {})[c], 4);
      if (m.kind !== 'num' || m.n < 1 || m.n > 1000000) errors['tmin_' + c] = 'أقل شحنة بـ' + CUR_NAME[c] + ' رقم صحيح أكبر من صفر';
      else if (m.n !== (cur.topup_min_by_currency || {})[c]) tmins[c] = m.n;
      if (r.kind !== 'num' || !(r.n > 0 && r.n <= 1000000)) errors['rate_' + c] = 'سعر الصرف رقم أكبر من صفر';
      else if (r.n !== (cur.rates || {})[c]) rates[c] = r.n;
    });
    if (Object.keys(tmins).length) changes.topup_min_by_currency = tmins;
    if (Object.keys(rates).length) changes.rates = rates;
    var nx = str(form.next);
    if (nx.length > 80) errors.next = 'سطر «الجاي» أقصر من ٨٠ حرفًا'; else if (nx !== str(cur.next_line)) changes.next_line = nx;
    var bad = Object.keys(errors).length > 0;
    return { ok: !bad && Object.keys(changes).length > 0, errors: errors, changes: changes,
             error: bad ? 'صحّح الخانات المعلَّمة' : (Object.keys(changes).length ? '' : 'لا يوجد تغيير للحفظ'), nothing: !bad && !Object.keys(changes).length };
  }
  var SET_LABELS = { daily_cap_usd: 'السقف اليومي', daily_cap_max_usd: 'أعلى سقف يمكن اختياره', image_min_multiple: 'مضاعِف حارس السعر للصور', video_min_multiple: 'مضاعِف حارس السعر للفيديو',
                     per_user_daily: 'حد المستخدم اليومي', per_ip_daily: 'حد الشبكة اليومي', free_posts_daily: 'البوستات المجانية اليومية', sample_pct: 'نسبة العيّنات للمراجعة',
                     retry_limit: 'إعادات المحاولة المجانية', topup_max_egp: 'سقف الشحن بالجنيه', next_line: 'سطر «الجاي»' };
  function settingValue(k, v) {
    if (k === 'daily_cap_usd' || k === 'daily_cap_max_usd') return usdText(v);
    if (k === 'sample_pct') return fmt(v) + '٪';
    if (k === 'topup_max_egp') return fmt(v) + ' جنيه';
    if (k === 'next_line') return v ? '«' + v + '»' : 'بلا سطر';
    return fmt(v);
  }
  function settingsDiff(changes, cur) {
    var lines = [];
    Object.keys(SET_LABELS).forEach(function (k) {
      if (changes[k] === undefined) return;
      var now = cur[k];
      lines.push({ label: SET_LABELS[k], from: now === undefined || now === null || now === '' ? (k === 'next_line' ? 'بلا سطر' : '—') : settingValue(k, now), to: settingValue(k, changes[k]) });
    });
    CURRENCIES.forEach(function (c) {
      if (changes.topup_min_by_currency && changes.topup_min_by_currency[c] !== undefined) lines.push({ label: 'أقل شحنة بـ' + CUR_NAME[c], from: fmt((cur.topup_min_by_currency || {})[c]) + ' ' + CUR_SHORT[c], to: fmt(changes.topup_min_by_currency[c]) + ' ' + CUR_SHORT[c] });
    });
    CURRENCIES.forEach(function (c) {
      if (changes.rates && changes.rates[c] !== undefined) lines.push({ label: 'سعر الصرف: وحدات ' + CUR_SHORT[c] + ' لكل دولار', from: fmt((cur.rates || {})[c]), to: fmt(changes.rates[c]) });
    });
    return lines;
  }
  function settingsError(status, data) { return writeError(status, data); }
  function settingsHot(changes) {
    var out = [];
    if (changes.daily_cap_usd != null) out.push('يتغيّر سقف الصرف اليومي، ويسري فورًا');
    if (changes.daily_cap_max_usd != null) out.push('تتغيّر أعلى قيمة يمكن اختيارها للسقف اليومي');
    if (changes.image_min_multiple != null || changes.video_min_multiple != null || changes.rates) out.push('يتغيّر حارس السعر: قد ترفض المنصة حفظ أدوات أسعارها تحت الحد الجديد');
    if (changes.topup_min_by_currency || changes.topup_max_egp != null) out.push('تتغيّر حدود الشحن التي يراها الأعضاء');
    return out;
  }

  // ------------------------------------------------------------------ ٥ · العيّنات
  function samples(resp, recipeRows, styleRows, now) {
    if (!resp || !Array.isArray(resp.samples)) return null;
    var rt = {}, st = {};
    (recipeRows || []).forEach(function (r) { rt[r.id] = r.title; });
    (styleRows || []).forEach(function (s) { if (s && s.id) st[s.id] = str(s.title_ar); });
    var rows = resp.samples.filter(function (r) { return r && typeof r === 'object' && str(r.id); }).map(function (r) {
      return { id: str(r.id), who: str(r.email), recipe: rt[str(r.recipe_id)] || 'أداة محذوفة', style: st[str(r.style_id)] || '', preview: str(r.preview), hasPreview: !!str(r.preview),
               when: when(r.created_at, now), ts: ms(r.created_at) };
    });
    var limit = isNum(resp.limit) ? resp.limit : 50, capped = rows.length >= limit;
    return { rows: rows, count: rows.length, capped: capped,
             countText: rows.length ? (capped ? ar(rows.length) + ' عيّنة أو أكثر تنتظر مراجعتك' : U(rows.length, ['عيّنة واحدة تنتظر مراجعتك', 'عيّنتان تنتظران مراجعتك', 'عيّنات تنتظر مراجعتك', 'عيّنة تنتظر مراجعتك'])) : 'لا عيّنات تنتظر' };
  }
  function moderateCopy(action, row) {
    var who = row.who || 'صاحب العمل';
    if (action === 'ok') return { title: 'عمل سليم', lead: 'سيُعلَّم هذا العمل أنه روجع وسليم، ويخرج من الطابور. لا يتغيّر شيء عند صاحبه.', go: 'العمل سليم', danger: false };
    if (action === 'hide') return { title: 'إخفاء العمل', lead: 'سيُخفى هذا العمل عن صاحبه فلا يراه ولا يحمّله. إن كان مدفوعًا وكانت كل أعمال المهمة مخفية يُرَدّ المبلغ إلى «فلوسي» تلقائيًا.', go: 'أخفِ العمل', danger: true };
    return { title: 'منع صاحب العمل', lead: 'سيُمنع ' + who + ' من الاستوديو، وتُخفى كل أعماله، ويُرَدّ ما دفعه عن الأعمال المخفية إلى «فلوسي». هذا قرار كبير، وتراجعه من فريق المنصة.', go: 'امنع صاحب العمل', danger: true };
  }
  function moderateDone(action, res) {
    var r = res && isNum(res.refunded) ? res.refunded : 0;
    var refund = r ? '، ورُدّ مبلغ ' + U(r, ['مهمة واحدة', 'مهمتين', 'مهام', 'مهمة']) + ' إلى «فلوسي»' : '';
    if (action === 'ok') return 'عُلِّم العمل سليمًا';
    if (action === 'hide') return 'أُخفي العمل' + refund;
    return 'مُنع صاحب العمل من الاستوديو، وأُخفيت أعماله' + refund;
  }
  function moderateError(status, data) {
    var msg = data && typeof data.error === 'string' ? data.error : '';
    if (data && data.no_reply) return msg;
    if (status === 404) return 'هذا العمل لم يعد في الطابور. حدّث الصفحة';
    if (msg && (status === 422 || status === 409 || status === 400)) return arDigits(msg);
    return 'تعذّر تنفيذ القرار، حاول مرة أخرى';
  }

  // ------------------------------------------------------------------ ٦ · التقرير
  var RANGE_LABEL = { today: 'اليوم', week: 'آخر ٧ أيام', custom: 'أخرى' };
  function dateText(iso) {
    var m = /^(\d{4})-(\d{2})-(\d{2})$/.exec(str(iso));
    if (!m) return '';
    var months = ['يناير', 'فبراير', 'مارس', 'أبريل', 'مايو', 'يونيو', 'يوليو', 'أغسطس', 'سبتمبر', 'أكتوبر', 'نوفمبر', 'ديسمبر'];
    return ar(+m[3]) + ' ' + months[+m[2] - 1] + ' ' + ar(+m[1]).replace(/٬/g, '');
  }
  function periodText(range, from, to) {
    if (!from || !to) return '';
    if (range === 'today' || from === to) return 'تقرير يوم ' + dateText(from);
    return 'من ' + dateText(from) + ' إلى ' + dateText(to);
  }
  function rangeCheck(from, to) {
    var a = /^\d{4}-\d{2}-\d{2}$/.test(str(from)), b = /^\d{4}-\d{2}-\d{2}$/.test(str(to));
    if (!a || !b) return { ok: false, error: 'اختر تاريخ البداية والنهاية' };
    if (from > to) return { ok: false, error: 'تاريخ البداية بعد تاريخ النهاية' };
    if ((Date.parse(to) - Date.parse(from)) / 86400e3 >= 366) return { ok: false, error: 'اختر مدة لا تزيد على سنة' };
    return { ok: true, error: '' };
  }
  function reportQuery(range, from, to) {
    var q = '/v2/tools/report?range=' + (range === 'week' || range === 'custom' ? range : 'today');
    if (range === 'custom') q += '&from=' + encodeURIComponent(from || '') + '&to=' + encodeURIComponent(to || '');
    return q;
  }
  function report(resp) {
    if (!resp || !Array.isArray(resp.recipes)) return null;
    var tot = { count: 0, succeeded: 0, failures: 0, cost: 0, revenue_usd: 0, by: {} };
    var rows = resp.recipes.map(function (r) {
      var m = isNum(r.margin_usd) ? r.margin_usd : 0;
      tot.count += r.count || 0; tot.succeeded += r.succeeded || 0; tot.failures += r.failures || 0; tot.cost += r.cost_usd || 0; tot.revenue_usd += r.revenue_usd || 0;
      CURRENCIES.forEach(function (c) { var v = r.revenue_by_currency && r.revenue_by_currency[c]; if (isNum(v)) tot.by[c] = (tot.by[c] || 0) + v; });
      var rev = moneyLine(r.revenue_by_currency);
      return { id: str(r.recipe_id), title: str(r.title) || str(r.recipe_id), count: r.count || 0, succeeded: r.succeeded || 0, failures: r.failures || 0, cost: r.cost_usd || 0,
               countText: ar(r.count || 0), failText: ar(r.failures || 0), costText: (r.cost_usd || 0) > 0 ? usdText(r.cost_usd) : 'بلا تكلفة',
               revenueText: rev ? rev + (r.revenue_usd > 0 ? ' ويعادل ' + usdText(r.revenue_usd) : '') : 'لا إيراد', marginText: m >= 0 ? (m > 0 ? 'هامش ' + usdText(m) : 'بلا هامش') : 'عجز ' + usdText(-m),
               marginNeg: m < 0, guard: !!r.guard_flag, avgText: (r.avg_cost_usd || 0) > 0 ? 'متوسط التكلفة الفعلية ' + usdText(r.avg_cost_usd) : '', active: (r.count || 0) > 0 };
    });
    var guardRows = rows.filter(function (r) { return r.guard; });
    var tp = resp.topups && typeof resp.topups === 'object' && resp.topups.by_currency ? resp.topups : null;
    var tpLine = tp ? moneyLine(tp.by_currency) : '';
    return {
      rows: rows, activeRows: rows.filter(function (r) { return r.active; }), guardRows: guardRows,
      totals: { count: ar(tot.count), succeeded: ar(tot.succeeded), failures: ar(tot.failures), failHot: tot.failures > 0, cost: tot.cost > 0 ? usdText(tot.cost) : 'بلا تكلفة',
                revenue: moneyLine(tot.by) || 'لا إيراد', revenueUsd: tot.revenue_usd > 0 ? 'يعادل ' + usdText(tot.revenue_usd) : '' },
      topups: { available: !!tp, line: tp ? (tpLine ? (isNum(tp.count) && tp.count ? 'شُحن ' + U(tp.count, ['مرة واحدة', 'مرتين', 'مرات', 'مرة']) + ': ' + tpLine : 'شحنات هذه الفترة: ' + tpLine) : 'لا شحنات في هذه الفترة') : 'أرقام الشحن غير متاحة بعد من المنصة' },
      period: periodText(resp.range, resp.from, resp.to), range: resp.range || 'today', from: resp.from || '', to: resp.to || ''
    };
  }
  var TOPUP_NOTE = 'شحن «فلوسي» رصيد للعميل وليس إيرادًا، فلا يدخل في الإيراد أعلاه. الإيراد هو ما خُصم من الرصيد مقابل أعمال ناجحة.';
  var GUARD_NOTE = 'متوسط التكلفة الفعلية لهذه الأداة صار أعلى من الحد الذي يحميه حارس السعر. راجع سعرها.';

  L.v2sTools = {
    CURRENCIES: CURRENCIES, CUR_NAME: CUR_NAME, CUR_SHORT: CUR_SHORT, GROUPS: GROUPS, PROTECTED_KINDS: PROTECTED_KINDS, RANGE_LABEL: RANGE_LABEL, TOPUP_NOTE: TOPUP_NOTE, GUARD_NOTE: GUARD_NOTE,
    arDigits: arDigits, fixSep: fixSep, line: line, usdText: usdText, moneyLine: moneyLine, dec: dec, parseDec: parseDec,
    overview: overview, killCopy: killCopy,
    freeText: freeText, priceLine: priceLine, recipes: recipes, enableCopy: enableCopy, priceMins: priceMins, ruleOptions: ruleOptions, ruleForm: ruleForm, recipeInputs: recipeInputs,
    recipeCheck: recipeCheck, recipeDiff: recipeDiff, writeError: writeError,
    styles: styles, styleCheck: styleCheck, fileCheck: fileCheck, newStyleId: newStyleId, styleDiff: styleDiff, visibleCopy: visibleCopy, deleteCopy: deleteCopy, createDone: createDone,
    settings: settings, settingsInputs: settingsInputs, settingsCheck: settingsCheck, settingsDiff: settingsDiff, settingsError: settingsError, settingsHot: settingsHot,
    samples: samples, moderateCopy: moderateCopy, moderateDone: moderateDone, moderateError: moderateError,
    rangeCheck: rangeCheck, reportQuery: reportQuery, report: report, periodText: periodText, dateText: dateText
  };
  if (typeof module !== 'undefined' && module.exports) module.exports.v2sTools = L.v2sTools;
})(typeof window !== 'undefined' ? window : (typeof globalThis !== 'undefined' ? globalThis : this));

/* ============================================================================
 * v2s/tools.js — «الأدوات» داخل قسم «الشركة ورأس المال»: لوحة حالة (نظرة اليوم ومفتاح الإيقاف) ومربّعات بصور (كاشير المطاعم)، وكل مربّع يفتح مهمة واحدة:
 *   الأدوات (تشغيل وسعر ورسم تجريبي) · الأماكن والأنماط (رفع صورة وتعديل وإظهار وحذف) · العيّنات (سليم/أخفِ/امنع) · التقرير · الإعدادات.
 * ⛔ لا منطق عمل هنا: كل التحقق والنصوص من `V2L.v2sTools`. ولا طلب شبكة إلا `/api/v2/tools/*` (بروكسيات أدمن).
 * ⛔ كل كتابة تمرّ على ورقة تأكيد وتذهب بـ`confirmed:true`. مفيش confirm()/alert()/prompt() ولا حفظ في المتصفح.
 *    (الاستثناء الوحيد: «الرسم التجريبي» معاينة بمزوّد تجريبي، ما بتغيّر شيئًا ولا بتكلّف، فبلا ورقة تأكيد.)
 * ⛔ المفتاح مقفول افتراضيًا: الملف بيتحمّل دايمًا لكنه ما بيرسم شيئًا إلا لو index.html نادى `render` (والغلاف الجديد شغّال).
 * ========================================================================== */
(function () {
  'use strict';
  if (typeof window === 'undefined' || typeof document === 'undefined') return;     // node (اختبارات المنطق): لا واجهة
  var L = window.V2L;
  if (!L || !L.v2sTools) return;
  var X = L.v2sTools, U = L.util, ar = U.ar;
  var T = window.V2S_TOOLS = {};
  var MOD = 'v2s_tools';
  var IMG = { recipes: 'marketing', styles: 'content', samples: 'people', report: 'money', settings: 'company' };
  var TITLES = { recipes: 'الأدوات', styles: 'الأماكن والأنماط', samples: 'العيّنات', report: 'التقرير', settings: 'الإعدادات' };
  var P = { ov: '/v2/tools/overview', rec: '/v2/tools/recipes', set: '/v2/tools/settings', smp: '/v2/tools/samples' };
  var S = { view: null, sub: 'hub', src: {}, note: '', noteT: null, nowOverride: 0, retryT: null, minute: null, range: 'today', cFrom: '', cTo: '', rangeErr: '', drawT: null, form: null };

  function esc(s) { return String(s == null ? '' : s).replace(/[&<>"']/g, function (c) { return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]; }); }
  function host() { return window.V2_HOST || {}; }
  function ep() { return window.EP || null; }
  function img(n) { return 'v2/img/' + n + '.jpg'; }
  function nowMs() { return S.nowOverride || Date.now(); }
  function roleName() { try { if (typeof role !== 'undefined') return role; } catch (e) {} var E = ep(); return (E && E.role) || ''; }
  T.canWrite = function () { return roleName() === 'admin'; };
  T.owns = function (mod) { return !!(mod === MOD && window.V2_ON && window.V2SHELL && window.V2SHELL.on); };
  function isCurrent() { return !!(S.view && document.body.contains(S.view) && host().current && T.owns(host().current())); }
  function q1(sel, r) { return (r || document).querySelector(sel); }
  function qa(sel, r) { return Array.prototype.slice.call((r || document).querySelectorAll(sel)); }

  // ------------------------------------------------------------------ المصادر
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
      s.state = e && e.status === 404 ? 'closed' : 'error'; s.status = (e && e.status) || 0; s.data = null; s.err = e && e.data && e.data.error || ''; changed();
    });
  }
  function repKey() { return 'rep:' + X.reportQuery(S.range, S.cFrom, S.cTo); }
  function repPath() { return X.reportQuery(S.range, S.cFrom, S.cTo); }
  function loadAll(force) {
    load('ov', P.ov, force); load('rec', P.rec, force); load('set', P.set, force); load('smp', P.smp, force);
    if (S.sub === 'report' && reportReady()) load(repKey(), repPath(), force);
  }
  function reportReady() { return S.range !== 'custom' || X.rangeCheck(S.cFrom, S.cTo).ok; }
  function reloadAfterWrite() { loadAll(true); }
  function changed() { if (S.drawT) return; S.drawT = setTimeout(function () { S.drawT = null; redraw(); }, 0); }
  function modalOpen() { return !!document.getElementById('epModal'); }
  function formFocused() { var a = document.activeElement; return !!(a && a.closest && a.closest('.tl-form') && /^(INPUT|TEXTAREA|SELECT)$/.test(a.tagName)); }
  function redraw() {
    if (!isCurrent()) return;
    if (modalOpen() || formFocused()) {                  // لا نمسح ما يكتبه المؤسس: نلحق بعد إغلاق الورقة أو ترك الخانة
      if (!S.retryT) S.retryT = setInterval(function () { if (modalOpen() || formFocused()) return; clearInterval(S.retryT); S.retryT = null; redraw(); }, 400);
      return;
    }
    draw(S.view);
  }
  function setNote(t) { S.note = t; clearTimeout(S.noteT); S.noteT = setTimeout(function () { S.note = ''; redraw(); }, 9000); }

  // ------------------------------------------------------------------ نماذج العرض
  function viewOv() { var s = src('ov'); return s.state === 'ready' ? X.overview(s.data) : null; }
  function viewRec() { var s = src('rec'); return s.state === 'ready' ? X.recipes(s.data) : null; }
  function viewStyles() { var s = src('rec'); return s.state === 'ready' ? X.styles(s.data) : null; }
  function viewSet() { var s = src('set'); return s.state === 'ready' ? X.settings(s.data) : null; }
  function viewSmp() {
    var s = src('smp'), r = src('rec');
    if (s.state !== 'ready') return null;
    var rr = r.state === 'ready' ? X.recipes(r.data) : null;
    return X.samples(s.data, rr ? rr.rows : [], r.state === 'ready' ? (r.data.styles || []) : [], nowMs());
  }
  function viewRep() { var s = src(repKey()); if (s.state !== 'ready') return null; var d = X.report(s.data); return d; }

  // ------------------------------------------------------------------ أجزاء مشتركة
  function stateBlock(key, what) {
    var s = src(key);
    if (s.state === 'idle' || s.state === 'loading') return '<div class="tl-skel" role="status" aria-label="جارٍ التحميل"><i></i><i></i><i></i></div>';
    if (s.state === 'closed') return '<div class="tl-empty"><b>' + esc(what) + ' غير متاح بعد على المنصة</b><p>سيظهر هنا تلقائيًا حين يصبح متاحًا</p></div>';
    return '<div class="tl-warn" role="alert">تعذّر جلب ' + esc(what) + '، وليس معناه أنه لا شيء فيه<button type="button" class="ep-bs" data-a="retry">أعد المحاولة</button></div>';
  }
  function back(title, sub) {
    return '<div class="tl-bar"><button type="button" class="ep-bs tl-back" data-a="hub">→ الأدوات</button></div>'
      + '<header class="tl-head"><span class="tl-himg" style="background-image:url(' + img(IMG[S.sub]) + ')" role="img" aria-label="' + esc(title) + '"></span><div><h2>' + esc(title) + '</h2>' + (sub ? '<p>' + esc(sub) + '</p>' : '') + '</div></header>';
  }
  function noteHtml() { return S.note ? '<p class="tl-note" role="status">' + esc(S.note) + '</p>' : ''; }
  function chip(t, cls) { return '<span class="tl-chip' + (cls ? ' ' + cls : '') + '">' + esc(t) + '</span>'; }
  function errLine(id, k, errs) { return '<p class="tl-ce' + (errs && errs[k] ? ' bad' : '') + '" id="' + id + '" role="alert">' + esc(errs && errs[k] ? errs[k] : '') + '</p>'; }

  // ------------------------------------------------------------------ الرئيسية: لوحة الحالة ومربّعات
  function statusCard() {
    var s = src('ov'), o = viewOv();
    if (!o) return '<section class="tl-status off" data-board="tl-status">' + stateBlock('ov', 'نظرة اليوم') + '</section>';
    var kill = o.killed
      ? '<button type="button" class="ep-b1" data-a="kill" data-on="0">أعد تشغيل الاستوديو</button>'
      : '<button type="button" class="ep-b1 tl-danger" data-a="kill" data-on="1">أوقف الاستوديو الآن</button>';
    return '<section class="tl-status ' + o.state + '" data-board="tl-status" aria-label="حالة الاستوديو اليوم">'
      + '<div class="tl-sh"><div class="tl-sht"><h2>الاستوديو اليوم</h2>' + chip(o.stateText, o.state) + '</div>' + (T.canWrite() ? kill : '') + '</div><p class="tl-snote">' + esc(o.stateNote) + '</p>'
      + '<div class="tl-spend"><div class="tl-bar2" role="progressbar" aria-label="الصرف اليوم من السقف" aria-valuemin="0" aria-valuemax="100"' + (o.pct == null ? '' : ' aria-valuenow="' + o.pct + '"') + '><i style="width:' + (o.pct || 0) + '%"></i></div>'
      + '<p class="tl-spendline"><b>' + esc(o.spendLine) + '</b>' + (o.remainingLine ? '<span>' + esc(o.remainingLine) + '</span>' : '') + '</p></div>'
      + '<div class="tl-stats"><div><b>' + esc(o.jobsText) + '</b><span>عمل اليوم</span></div><div><b>' + esc(o.okText) + '</b><span>نجحت</span></div><div class="' + (o.failHot ? 'hot' : '') + '"><b>' + esc(o.failText) + '</b><span>لم تنجح</span></div></div>'
      + (o.jobs ? '' : '<p class="tl-fine">أرقام أعمال اليوم غير متاحة بعد</p>')
      + '<ul class="tl-facts">' + o.facts.map(function (f) { return '<li' + (f.off ? ' class="off"' : '') + '><b>' + esc(f.k) + '</b><span class="tl-fv">' + esc(f.v) + '</span>' + (f.note ? '<small>' + esc(f.note) + '</small>' : '') + '</li>'; }).join('') + '</ul>'
      + o.warns.map(function (w) { return '<p class="tl-warn soft" role="status">' + esc(w) + '</p>'; }).join('')
      + '</section>';
  }
  function tileCount(key, getter) {
    var s = src(key);
    if (s.state === 'ready') { var v = getter(); return v == null ? { n: '—', sub: 'غير متاح بعد', off: true } : v; }
    if (s.state === 'error' || s.state === 'closed') return { n: '—', sub: 'غير متاح بعد', off: true };
    return { n: '…', sub: 'جارٍ التحميل', off: true, loading: true };
  }
  function tiles() {
    var rec = tileCount('rec', function () { var v = viewRec(); return v ? { n: ar(v.enabledCount), sub: 'من ' + ar(v.total) + ' أدوات شغّالة', hot: false } : null; });
    var sty = tileCount('rec', function () { var v = viewStyles(); return v ? { n: ar(v.total), sub: 'مكان وتصميم', hot: false } : null; });
    var smp = tileCount('smp', function () { var v = viewSmp(); return v ? { n: v.capped ? ar(v.count) + '+' : ar(v.count), sub: v.count ? 'عيّنة تنتظر مراجعتك' : 'لا شيء ينتظر', hot: v.count > 0 } : null; });
    var ov = viewOv();
    var rep = tileCount('ov', function () { return ov && ov.jobs ? { n: ar(ov.jobs.count), sub: 'عمل اليوم، ولك تقرير الأسبوع', hot: false } : null; });
    var set = tileCount('set', function () { var v = viewSet(); return v ? { n: ar(Math.round(v.daily_cap_usd * 100) / 100), sub: 'دولار سقف الصرف اليومي', hot: false } : null; });
    var defs = [['recipes', 'الأدوات', rec], ['styles', 'الأماكن والأنماط', sty], ['samples', 'العيّنات', smp], ['report', 'التقرير', rep], ['settings', 'الإعدادات', set]];
    return '<div class="tl-tiles" role="list">' + defs.map(function (d) {
      var t = d[2];
      return '<button type="button" class="tl-tile' + (t.hot ? ' hot' : '') + (t.off ? ' off' : '') + '" role="listitem" data-a="go" data-sub="' + d[0] + '">'
        + '<span class="tl-timg" style="background-image:url(' + img(IMG[d[0]]) + ')" role="img" aria-label="' + esc(d[1]) + '"></span>'
        + '<span class="tl-tbody"><b class="tl-n">' + esc(t.n) + '</b><span class="tl-tname">' + esc(d[1]) + '</span><small>' + esc(t.sub) + '</small></span></button>';
    }).join('') + '</div>';
  }
  function drawHub(v) {
    v.innerHTML = '<div class="v2s-tl" data-board="tl-hub">' + noteHtml() + statusCard() + '<p class="tl-lead">اختر ما تريد ضبطه</p>' + tiles() + '</div>';
  }

  // ------------------------------------------------------------------ أوراق التأكيد
  function sheet(title, html) {
    if (typeof window.openModal !== 'function') return null;
    var s = window.openModal(title, '<div class="v3m v2s-tl-sb">' + html + '</div>');
    s.classList.add('v2s-tl-sh');
    var x = s.querySelector('[data-x]');
    if (x) { x.setAttribute('aria-label', 'إغلاق'); x.onclick = function () { if (!s.dataset.busy) window.closeModal(); }; }
    s.onclick = function (e) { if (e.target === s && !s.dataset.busy) window.closeModal(); };
    return s;
  }
  function plain401(e) { return e && e.status === 401; }
  function runWrite(s, goBtn, noBtn, errBox, label, send, errText, onOk) {
    if (s.dataset.busy) return;
    s.dataset.busy = '1'; goBtn.disabled = true; if (noBtn) noBtn.disabled = true; goBtn.textContent = 'جارٍ التنفيذ…'; errBox.innerHTML = '';
    Promise.resolve(send()).then(function (res) {
      delete s.dataset.busy; window.closeModal(); onOk(res || {}); reloadAfterWrite(); redraw();
    }).catch(function (e) {
      delete s.dataset.busy; goBtn.disabled = false; if (noBtn) noBtn.disabled = false; goBtn.textContent = label;
      errBox.innerHTML = '<div class="tl-err" role="alert">' + esc(plain401(e) ? 'انتهت الجلسة، سجّل الدخول من جديد ثم جرّب' : errText(e && e.status, e && e.data)) + '</div>';
      if (e && (e.status === 409 || (e.data && (e.data.no_reply || e.data.attach_failed)))) reloadAfterWrite();
    });
  }
  function api(path, body, method) { return ep().api(path, { method: method || 'POST', body: body }); }
  function byId(list, id) { for (var i = 0; i < list.length; i++) if (list[i].id === id) return list[i]; return null; }
  function confirmSheet(copy, danger, send, onOk, errFn) {
    var s = sheet(copy.title, '<p class="mc-lead">' + esc(copy.lead) + '</p><div id="tlErr" role="alert"></div><div class="acts"><button type="button" class="ep-b1' + (danger ? ' tl-danger' : '') + '" id="tlGo">' + esc(copy.go) + '</button><button type="button" class="ep-b2" id="tlNo">رجوع</button></div>');
    if (!s) return;
    var go = q1('#tlGo', s), no = q1('#tlNo', s), err = q1('#tlErr', s);
    no.onclick = function () { if (!s.dataset.busy) window.closeModal(); };
    go.onclick = function () { runWrite(s, go, no, err, copy.go, send, errFn || X.writeError, onOk); };
    setTimeout(function () { try { no.focus(); } catch (e) {} }, 30);
    return s;
  }

  // ------------------------------------------------------------------ مفتاح الإيقاف
  function killSheet(stop) {
    var c = X.killCopy(stop);
    confirmSheet(c, stop, function () { return api('/v2/tools/kill', { kill: stop, confirmed: true }); }, function () { setNote(c.done); });
  }

  // ------------------------------------------------------------------ الأدوات
  function drawRecipes(v) {
    var d = viewRec(), body;
    var set = viewSet();
    if (!d) body = stateBlock('rec', 'الأدوات');
    else if (!d.rows.length) body = '<div class="tl-empty"><b>لا أدوات على المنصة</b><p>تظهر هنا حين تُجهَّز على المنصة</p></div>';
    else body = d.groups.map(function (g) {
      return '<section class="tl-group"><h3 class="tl-gh">' + esc(g.label) + '</h3><ul class="tl-cards">' + g.rows.map(function (r) {
        var sw = '<button type="button" class="tl-sw' + (r.enabled ? ' on' : '') + '" role="switch" aria-checked="' + (r.enabled ? 'true' : 'false') + '" aria-label="' + esc((r.enabled ? 'إيقاف ' : 'تشغيل ') + r.title) + '" data-a="enable" data-id="' + esc(r.id) + '" data-on="' + (r.enabled ? '0' : '1') + '"><i></i><span>' + (r.enabled ? 'شغّالة' : 'موقوفة') + '</span></button>';
        return '<li class="tl-card' + (r.enabled ? ' live' : '') + '" data-id="' + esc(r.id) + '"><div class="tl-ch"><h3>' + esc(r.title) + '</h3>' + sw + '</div>'
          + (r.sub ? '<p class="tl-nt">' + esc(r.sub) + '</p>' : '')
          + '<p class="tl-meta"><span>' + esc(r.providerText) + '</span>' + (r.draft ? '<span class="tl-tag">مسوّدة من العقل</span>' : '') + (r.costText ? '<span>' + esc(r.costText) + '</span>' : '') + '</p>'
          + '<dl class="tl-kv"><div><dt>السعر</dt><dd>' + esc(r.priceText) + '</dd></div><div><dt>قاعدة المجاني</dt><dd>' + esc(r.freeText) + '</dd></div><div><dt>الأماكن</dt><dd>' + esc(r.stylesText) + '</dd></div></dl>'
          + '<div class="tl-acts"><button type="button" class="ep-b2" data-a="redit" data-id="' + esc(r.id) + '">عدّل السعر والقاعدة</button><button type="button" class="ep-bs" data-a="rtest" data-id="' + esc(r.id) + '">رسم تجريبي</button></div></li>';
      }).join('') + '</ul></section>';
    }).join('');
    v.innerHTML = '<div class="v2s-tl" data-board="tl-recipes">' + noteHtml() + back('الأدوات', d ? d.countText : '') + (set ? '' : '') + body + '</div>';
  }
  function recipeRow(id) { var d = viewRec(); return d ? byId(d.rows, id) : null; }
  function enableSheet(row, on) {
    var ov = viewOv(), c = X.enableCopy(row, on, !!(ov && ov.toolsEnabled));
    confirmSheet(c, false, function () { return api('/v2/tools/recipes/' + encodeURIComponent(row.id) + '/enable', { enabled: on, base_updated_at: row.updatedAt, confirmed: true }); }, function () { setNote(c.done); });
  }
  function recipeSheet(row) {
    var set = viewSet() || {}, inp = X.recipeInputs(row);
    var s = sheet('سعر «' + row.title + '»', '<div id="tlStage"></div>');
    if (!s) return;
    var stage = q1('#tlStage', s), cur = inp;
    function collect() {
      var o = { price: {}, est: row.provider ? q1('#tlEst', s).value : '', rule: q1('#tlRule', s).value, daily: q1('#tlDaily', s).value };
      X.CURRENCIES.forEach(function (c) { o.price[c] = q1('#tlP_' + c, s).value; });
      return o;
    }
    function showChecks(r, submit) {
      X.CURRENCIES.forEach(function (c) {
        var e = q1('#tlE_' + c, s), msg = r.errors['price_' + c] || '', both = String((collect().price || {})[c]).trim() !== '';
        e.textContent = (submit || both) ? msg : ''; e.className = 'tl-ce' + (msg && (submit || both) ? ' bad' : '');
        q1('#tlrow_' + c, s).classList.toggle('bad', !!msg && (submit || both));
      });
      var er = q1('#tlERule', s); er.textContent = r.errors.rule || ''; er.className = 'tl-ce' + (r.errors.rule ? ' bad' : '');
      if (row.provider) { var ee = q1('#tlEEst', s); ee.textContent = r.errors.est || ''; ee.className = 'tl-ce' + (r.errors.est ? ' bad' : ''); }
    }
    function form() {
      s.dataset.stage = 'form';
      var mins = X.priceMins(row, set);
      stage.innerHTML = '<p class="mc-lead">' + esc(row.title) + '</p><p class="tl-fine">أرقام بلا كسور أو بكسور قليلة. الصفر يعني مجانية ويحتاج قاعدة مجانية إن كانت لها تكلفة.</p>'
        + (row.provider ? '<div class="fld"><label for="tlEst">تكلفتها علينا بالدولار للعمل الواحد</label><input id="tlEst" inputmode="decimal" autocomplete="off" value="' + esc(cur.est) + '"><small>تحدّد أقل سعر مسموح، وتُقارَن بالتكلفة الفعلية في التقرير</small><p class="tl-ce" id="tlEEst" role="alert"></p></div>' : '')
        + '<div class="tl-curs">' + X.CURRENCIES.map(function (c) {
          return '<div class="tl-cur" id="tlrow_' + c + '"><b>' + esc(X.CUR_NAME[c]) + '</b><div class="tl-cf"><label for="tlP_' + c + '">السعر</label><input id="tlP_' + c + '" inputmode="decimal" autocomplete="off" value="' + esc(cur.price[c]) + '"></div>'
            + (mins[c] > 0 ? '<small>أقل سعر مسموح ' + esc(L.util.fmt(mins[c])) + '</small>' : '') + '<p class="tl-ce" id="tlE_' + c + '" role="alert"></p></div>';
        }).join('') + '</div>'
        + '<div class="fld"><label for="tlRule">قاعدة المجاني</label><select id="tlRule">' + X.ruleOptions().map(function (o) { return '<option value="' + o[0] + '"' + (o[0] === cur.rule ? ' selected' : '') + '>' + esc(o[1]) + '</option>'; }).join('') + '</select></div>'
        + '<div class="fld" id="tlDailyBox"' + (cur.rule === 'daily' ? '' : ' hidden') + '><label for="tlDaily">عدد المرات المجانية كل يوم</label><input id="tlDaily" inputmode="numeric" autocomplete="off" value="' + esc(cur.daily) + '"></div><p class="tl-ce" id="tlERule" role="alert"></p>'
        + '<div id="tlErr" role="alert"></div><div class="acts"><button type="button" class="ep-b1" id="tlNext">راجع ثم احفظ</button><button type="button" class="ep-b2" id="tlNo">رجوع</button></div>';
      var rule = q1('#tlRule', s);
      rule.onchange = function () { q1('#tlDailyBox', s).hidden = rule.value !== 'daily'; };
      qa('input,select', stage).forEach(function (el) { el.addEventListener('input', function () { cur = collect(); showChecks(X.recipeCheck(row, cur, set), false); }); });
      showChecks(X.recipeCheck(row, cur, set), false);
      q1('#tlNo', s).onclick = function () { if (!s.dataset.busy) window.closeModal(); };
      q1('#tlNext', s).onclick = function () {
        cur = collect();
        var r = X.recipeCheck(row, cur, set);
        showChecks(r, true);
        if (!r.ok) { q1('#tlErr', s).innerHTML = '<div class="tl-err" role="alert">' + esc(r.error) + '</div>'; return; }
        review(r.payload);
      };
      var first = qa('input', stage)[0]; if (first) setTimeout(function () { try { first.focus(); } catch (e) {} }, 30);
    }
    function review(payload) {
      s.dataset.stage = 'review';
      var lines = X.recipeDiff(row, payload);
      stage.innerHTML = '<p class="mc-lead">' + esc(lines.length ? 'سيُحفظ هذا التعديل في «' + row.title + '»، ويسري على الأعضاء فورًا:' : 'لا فرق عن القيم الحالية.') + '</p>'
        + (lines.length ? '<ul class="tl-diff">' + lines.map(function (l) { return '<li><b>' + esc(l.label) + '</b><span><s>' + esc(l.from) + '</s><i aria-hidden="true">←</i><em>' + esc(l.to) + '</em></span></li>'; }).join('') + '</ul>' : '')
        + '<div id="tlErr" role="alert"></div><div class="acts"><button type="button" class="ep-b1" id="tlGo"' + (lines.length ? '' : ' disabled') + '>احفظ التعديل</button><button type="button" class="ep-b2" id="tlBack">ارجع للتعديل</button></div>';
      var go = q1('#tlGo', s), bk = q1('#tlBack', s), err = q1('#tlErr', s);
      bk.onclick = function () { if (!s.dataset.busy) form(); };
      go.onclick = function () {
        var body = { base_updated_at: row.updatedAt, confirmed: true, price: payload.price, free_rule: payload.free_rule };
        if (payload.est_cost_usd != null) body.est_cost_usd = payload.est_cost_usd;
        runWrite(s, go, bk, err, 'احفظ التعديل', function () { return api('/v2/tools/recipes/' + encodeURIComponent(row.id), body, 'PUT'); }, X.writeError, function () { setNote('حُفظ سعر «' + row.title + '»'); });
      };
      setTimeout(function () { try { bk.focus(); } catch (e) {} }, 30);
    }
    form();
  }
  // رسم تجريبي: معاينة بمزوّد تجريبي (لا تكلفة ولا تخزين) — لذلك بلا تأكيد
  function testSheet(row) {
    var d = viewStyles(), sec = d ? byId(d.sections.map(function (x) { return { id: x.recipe.id, sec: x }; }), row.id) : null;
    var list = sec ? sec.sec.styles : [];
    var s = sheet('رسم تجريبي لـ«' + row.title + '»', '<p class="mc-lead">معاينة تجريبية مرسومة داخل النظام: لا تكلّف شيئًا، ولا تُحفظ، ولا تُحسب على أحد.</p>'
      + (row.video ? '<p class="tl-fine">هذه الأداة فيديو، ولا معاينة صور لها.</p>' : '')
      + (list.length ? '<div class="fld"><label for="tlSt">المكان</label><select id="tlSt"><option value="">أول مكان في الأداة</option>' + list.map(function (x) { return '<option value="' + esc(x.id) + '">' + esc(x.title) + '</option>'; }).join('') + '</select></div>' : '')
      + '<div id="tlOut" aria-live="polite"></div><div id="tlErr" role="alert"></div><div class="acts"><button type="button" class="ep-b1" id="tlGo">ارسم معاينة</button><button type="button" class="ep-b2" id="tlNo">إغلاق</button></div>');
    if (!s) return;
    var go = q1('#tlGo', s), no = q1('#tlNo', s), out = q1('#tlOut', s), err = q1('#tlErr', s);
    no.onclick = function () { if (!s.dataset.busy) window.closeModal(); };
    go.onclick = function () {
      if (s.dataset.busy) return;
      s.dataset.busy = '1'; go.disabled = true; go.textContent = 'جارٍ الرسم…'; err.innerHTML = ''; out.innerHTML = '';
      var sel = q1('#tlSt', s);
      api('/v2/tools/recipes/' + encodeURIComponent(row.id) + '/test-render', { style_id: sel ? sel.value : '' }).then(function (res) {
        delete s.dataset.busy; go.disabled = false; go.textContent = 'ارسم معاينة من جديد';
        var imgs = res && Array.isArray(res.images) ? res.images : [];
        out.innerHTML = imgs.length ? '<div class="tl-shots">' + imgs.map(function (u, i) { return '<img class="tl-shot" alt="معاينة تجريبية ' + ar(i + 1) + '" src="' + esc(u) + '">'; }).join('') + '</div><p class="tl-fine">صور تجريبية مرسومة داخل النظام، وليست من المزوّد.</p>' : '<p class="tl-fine">لا صور لهذه الأداة في المعاينة.</p>';
      }).catch(function (e) {
        delete s.dataset.busy; go.disabled = false; go.textContent = 'ارسم معاينة';
        err.innerHTML = '<div class="tl-err" role="alert">' + esc(plain401(e) ? 'انتهت الجلسة، سجّل الدخول من جديد ثم جرّب' : X.writeError(e && e.status, e && e.data)) + '</div>';
      });
    };
  }

  // ------------------------------------------------------------------ الأماكن والأنماط
  function drawStyles(v) {
    var d = viewStyles(), body;
    if (!d) body = stateBlock('rec', 'الأماكن والأنماط');
    else body = d.sections.map(function (sec) {
      var r = sec.recipe;
      var tiles2 = sec.styles.map(function (st) {
        var pic = st.hasPreview ? '<span class="tl-pic" style="background-image:url(' + esc(st.preview) + ')" role="img" aria-label="' + esc(st.title) + '"></span>' : '<span class="tl-pic none" role="img" aria-label="' + esc(st.title) + '"><em>' + esc(st.codeOnly ? 'يُرسم بالكود' : 'بلا صورة') + '</em></span>';
        return '<li class="tl-style" data-id="' + esc(st.id) + '">' + pic + '<div class="tl-sbody"><h4>' + esc(st.title) + '</h4><p class="tl-meta"><span>' + esc(st.orderText) + '</span>' + chip(st.visible ? 'ظاهر للناس' : 'غير ظاهر', st.visible ? 'on' : 'off') + '</p></div>'
          + '<div class="tl-acts"><button type="button" class="ep-b2" data-a="sedit" data-id="' + esc(st.id) + '">عدّل</button>'
          + '<button type="button" class="ep-bs" data-a="svis" data-id="' + esc(st.id) + '" data-on="' + (st.visible ? '0' : '1') + '">' + (st.visible ? 'أخفِه' : 'أظهره للناس') + '</button>'
          + (st.canDelete ? '<button type="button" class="ep-bs tl-del" data-a="sdel" data-id="' + esc(st.id) + '">احذف</button>' : '') + '</div></li>';
      }).join('');
      var add = sec.canAdd ? '<button type="button" class="ep-b2 tl-addbtn" data-a="sadd" data-id="' + esc(r.id) + '">أضِف مكانًا</button>' : '';
      return '<section class="tl-group" data-recipe="' + esc(r.id) + '"><div class="tl-gh2"><h3>' + esc(r.title) + '</h3>' + chip(r.enabled ? 'الأداة شغّالة' : 'الأداة موقوفة', r.enabled ? 'on' : 'off') + '<span class="tl-fine">' + esc(sec.countText) + '</span>' + add + '</div>'
        + (tiles2 ? '<ul class="tl-styles">' + tiles2 + '</ul>' : '<p class="tl-fine">لا تصاميم لهذه الأداة</p>') + '</section>';
    }).join('');
    v.innerHTML = '<div class="v2s-tl" data-board="tl-styles">' + noteHtml() + back('الأماكن والأنماط', d ? d.totalText : '') + (d ? '<p class="tl-ro soft">صور الأماكن فارغة أو بظل فقط، بلا وجوه أشخاص.</p>' : '') + body + '</div>';
  }
  function styleRow(id) {
    var d = viewStyles();
    if (!d) return null;
    for (var i = 0; i < d.sections.length; i++) { var st = byId(d.sections[i].styles, id); if (st) return { st: st, sec: d.sections[i] }; }
    return null;
  }
  function randHex() {
    try { var a = new Uint8Array(4); (window.crypto || window.msCrypto).getRandomValues(a); return Array.prototype.map.call(a, function (b) { return ('0' + b.toString(16)).slice(-2); }).join(''); } catch (e) {}
    return ('00000000' + Math.floor(Math.random() * 4294967295).toString(16)).slice(-8);
  }
  function fileFields(withCheck) {
    return '<div class="fld"><label for="tlFile">صورة المكان</label><div class="tl-filebox"><label class="ep-b2 tl-filebtn" for="tlFile">اختر صورة</label><input id="tlFile" type="file" accept="image/png,image/jpeg,image/webp"><span id="tlFileName" class="tl-fine">لم تُختر صورة</span></div>'
      + '<img id="tlThumb" class="tl-thumb" alt="معاينة الصورة المختارة" hidden><small>صورة المكان فارغة أو بظل فقط، بلا وجوه. حتى ٣ ميجا (JPG أو PNG أو WebP).</small><p class="tl-ce" id="tlEFile" role="alert"></p></div>';
  }
  function bindFile(s, st) {
    var f = q1('#tlFile', s);
    f.onchange = function () {
      var file = f.files && f.files[0], c = X.fileCheck(file), e = q1('#tlEFile', s), th = q1('#tlThumb', s);
      st.file = null; st.dataUrl = ''; th.hidden = true; q1('#tlFileName', s).textContent = file ? file.name : 'لم تُختر صورة';
      if (!c.ok) { e.textContent = file ? c.error : ''; e.className = 'tl-ce' + (file ? ' bad' : ''); return; }
      e.textContent = ''; e.className = 'tl-ce'; st.file = file;
      var fr = new FileReader();
      fr.onload = function () { st.dataUrl = String(fr.result || ''); th.src = st.dataUrl; th.hidden = false; };
      fr.readAsDataURL(file);
    };
  }
  function stylePickerFields(vals, hasPlace, withFile) {
    return '<div class="fld"><label for="tlTitle">اسم المكان</label><input id="tlTitle" maxlength="60" autocomplete="off" value="' + esc(vals.title) + '"><p class="tl-ce" id="tlETitle" role="alert"></p></div>'
      + '<div class="fld"><label for="tlSort">الترتيب في القائمة</label><input id="tlSort" inputmode="numeric" autocomplete="off" value="' + esc(vals.sort) + '"><small>الأصغر يظهر أولًا</small><p class="tl-ce" id="tlESort" role="alert"></p></div>'
      + (hasPlace ? '<div class="fld"><label for="tlPlace">وصف المكان</label><textarea id="tlPlace" maxlength="400" rows="3">' + esc(vals.place) + '</textarea><small>جملة قصيرة تصف المكان الذي يُرسم فيه العمل</small><p class="tl-ce" id="tlEPlace" role="alert"></p></div>' : '')
      + '<label class="tl-radio"><input type="checkbox" id="tlJudge"' + (vals.judge ? ' checked' : '') + '><span><b>يناسب القضاة وأعضاء النيابة</b><small>إن لم يُعلَّم لا يظهر لهم</small></span></label>'
      + (withFile ? fileFields() : '');
  }
  // أثناء الكتابة: الخطأ المعروض يختفي أول ما يتصلّح (ولا نُظهر أخطاء لخانة لم يُضغط عليها «راجع» بعد)
  function refreshStyleErrors(s, r) {
    [['tlETitle', 'title'], ['tlESort', 'sort'], ['tlEPlace', 'place'], ['tlEFile', 'file']].forEach(function (p) {
      var e = q1('#' + p[0], s); if (!e || !e.classList.contains('bad')) return;
      e.textContent = r.errors[p[1]] || ''; e.className = 'tl-ce' + (r.errors[p[1]] ? ' bad' : '');
    });
  }
  function showStyleErrors(s, r) {
    [['tlETitle', 'title'], ['tlESort', 'sort'], ['tlEPlace', 'place'], ['tlEFile', 'file']].forEach(function (p) {
      var e = q1('#' + p[0], s); if (!e) return; e.textContent = r.errors[p[1]] || ''; e.className = 'tl-ce' + (r.errors[p[1]] ? ' bad' : '');
    });
  }
  function addSheet(rid) {
    var d = viewStyles(), sec = null;
    if (d) d.sections.forEach(function (x) { if (x.recipe.id === rid) sec = x; });
    if (!sec) return;
    var nextSort = sec.styles.reduce(function (m, x) { return Math.max(m, x.sort); }, 0) + 1;
    var st = { file: null, dataUrl: '' }, id = X.newStyleId(randHex());
    var s = sheet('أضِف مكانًا إلى «' + sec.recipe.title + '»', '<div id="tlStage"></div>');
    if (!s) return;
    var stage = q1('#tlStage', s);
    function collect() { return { title: q1('#tlTitle', s).value, sort: q1('#tlSort', s).value, place: q1('#tlPlace', s).value, judge: q1('#tlJudge', s).checked, file: st.file, hasPlace: true }; }
    function form(vals) {
      s.dataset.stage = 'form';
      vals = vals || { title: '', sort: ar(nextSort), place: '', judge: true };
      stage.innerHTML = stylePickerFields(vals, true, true) + '<label class="tl-radio"><input type="checkbox" id="tlAttach"' + (st.attach === false ? '' : ' checked') + '><span><b>أظهره للناس فور إضافته</b><small>إن لم يُعلَّم يبقى محفوظًا هنا حتى تظهره</small></span></label>'
        + '<div id="tlErr" role="alert"></div><div class="acts"><button type="button" class="ep-b1" id="tlNext">راجع ثم أضِف</button><button type="button" class="ep-b2" id="tlNo">رجوع</button></div>';
      bindFile(s, st);
      qa('#tlTitle,#tlSort,#tlPlace,#tlJudge', stage).forEach(function (el) { el.addEventListener('input', function () { refreshStyleErrors(s, X.styleCheck(collect(), true)); }); });
      if (st.dataUrl) { var th = q1('#tlThumb', s); th.src = st.dataUrl; th.hidden = false; q1('#tlFileName', s).textContent = st.file ? st.file.name : ''; }
      q1('#tlNo', s).onclick = function () { if (!s.dataset.busy) window.closeModal(); };
      q1('#tlNext', s).onclick = function () {
        var vals2 = collect(); st.attach = q1('#tlAttach', s).checked;
        var r = X.styleCheck(vals2, true), fc = vals2.file ? X.fileCheck(vals2.file) : { ok: false };
        if (vals2.file && !fc.ok) r.errors.file = fc.error;
        r.ok = r.ok && (!vals2.file || fc.ok);
        showStyleErrors(s, r);
        if (!r.ok) { q1('#tlErr', s).innerHTML = '<div class="tl-err" role="alert">' + esc(r.error || 'صحّح الخانات المعلَّمة') + '</div>'; return; }
        st.vals = vals2; review(r.payload);
      };
      setTimeout(function () { try { q1('#tlTitle', s).focus(); } catch (e) {} }, 30);
    }
    function review(p) {
      s.dataset.stage = 'review';
      stage.innerHTML = '<p class="mc-lead">سيُضاف هذا المكان إلى «' + esc(sec.recipe.title) + '»' + (st.attach ? ' ويظهر للناس فورًا:' : ' بلا ظهور للناس:') + '</p>'
        + '<div class="tl-rev">' + (st.dataUrl ? '<img class="tl-thumb" alt="الصورة المختارة" src="' + esc(st.dataUrl) + '">' : '') + '<dl class="tl-kv"><div><dt>الاسم</dt><dd>' + esc(p.title_ar) + '</dd></div><div><dt>الترتيب</dt><dd>' + esc(ar(p.sort)) + '</dd></div><div><dt>الوصف</dt><dd>' + esc(p.place_prompt) + '</dd></div><div><dt>القضاة وأعضاء النيابة</dt><dd>' + (p.judge_ok ? 'يناسبهم' : 'لا يظهر لهم') + '</dd></div></dl></div>'
        + '<div id="tlErr" role="alert"></div><div class="acts"><button type="button" class="ep-b1" id="tlGo">أضِف المكان</button><button type="button" class="ep-b2" id="tlBack">ارجع للتعديل</button></div>';
      var go = q1('#tlGo', s), bk = q1('#tlBack', s), err = q1('#tlErr', s);
      bk.onclick = function () { if (!s.dataset.busy) form(st.vals); };
      go.onclick = function () {
        var fd = new FormData();
        fd.append('id', id); fd.append('recipe_id', sec.recipe.id); fd.append('title_ar', p.title_ar); fd.append('place_prompt', p.place_prompt); fd.append('sort', String(p.sort));
        fd.append('judge_ok', p.judge_ok ? 'true' : 'false'); fd.append('attach', st.attach === false ? 'false' : 'true'); fd.append('confirmed', 'true'); fd.append('preview', st.file, st.file.name);
        runWrite(s, go, bk, err, 'أضِف المكان', function () { return ep().api('/v2/tools/styles', { method: 'POST', body: fd }); }, X.writeError, function (res) { setNote(X.createDone(res)); });
      };
      setTimeout(function () { try { bk.focus(); } catch (e) {} }, 30);
    }
    form();
  }
  function editStyleSheet(sr) {
    var st = sr.st, hasPlace = !st.codeOnly, pic = { file: null, dataUrl: '' };
    var s = sheet('تعديل «' + st.title + '»', '<div id="tlStage"></div>');
    if (!s) return;
    var stage = q1('#tlStage', s);
    function collect() { return { title: q1('#tlTitle', s).value, sort: q1('#tlSort', s).value, place: hasPlace ? q1('#tlPlace', s).value : '', judge: q1('#tlJudge', s).checked, hasPlace: hasPlace }; }
    function form(vals) {
      s.dataset.stage = 'form';
      vals = vals || { title: st.title, sort: ar(st.sort), place: st.place, judge: st.judgeOk };
      stage.innerHTML = stylePickerFields(vals, hasPlace, !st.codeOnly) + '<div id="tlErr" role="alert"></div><div class="acts"><button type="button" class="ep-b1" id="tlNext">راجع ثم احفظ</button><button type="button" class="ep-b2" id="tlNo">رجوع</button></div>';
      qa('#tlTitle,#tlSort,#tlPlace,#tlJudge', stage).forEach(function (el) { el.addEventListener('input', function () { refreshStyleErrors(s, X.styleCheck(collect(), false)); }); });
      if (!st.codeOnly) {
        bindFile(s, pic);
        q1('#tlFileName', s).textContent = pic.file ? pic.file.name : 'تبقى الصورة الحالية إن لم تختر غيرها';
        if (pic.dataUrl) { var th = q1('#tlThumb', s); th.src = pic.dataUrl; th.hidden = false; }
        else if (st.hasPreview) { var th2 = q1('#tlThumb', s); th2.src = st.preview; th2.hidden = false; }
      }
      q1('#tlNo', s).onclick = function () { if (!s.dataset.busy) window.closeModal(); };
      q1('#tlNext', s).onclick = function () {
        var v2 = collect(), r = X.styleCheck(v2, false);
        if (pic.file) { var fc = X.fileCheck(pic.file); if (!fc.ok) { r.errors.file = fc.error; r.ok = false; } }
        showStyleErrors(s, r);
        if (!r.ok) { q1('#tlErr', s).innerHTML = '<div class="tl-err" role="alert">' + esc(r.error || 'صحّح الخانات المعلَّمة') + '</div>'; return; }
        var payload = r.payload; if (pic.dataUrl) payload.preview_data = pic.dataUrl;
        review(payload, v2);
      };
      setTimeout(function () { try { q1('#tlTitle', s).focus(); } catch (e) {} }, 30);
    }
    function review(payload, vals) {
      s.dataset.stage = 'review';
      var lines = X.styleDiff(st, payload);
      stage.innerHTML = '<p class="mc-lead">' + esc(lines.length ? 'سيُحفظ هذا التعديل في «' + st.title + '»:' : 'لا فرق عن القيم الحالية.') + '</p>'
        + (lines.length ? '<ul class="tl-diff">' + lines.map(function (l) { return '<li><b>' + esc(l.label) + '</b><span><s>' + esc(l.from) + '</s><i aria-hidden="true">←</i><em>' + esc(l.to) + '</em></span></li>'; }).join('') + '</ul>' : '')
        + (payload.preview_data ? '<img class="tl-thumb" alt="الصورة الجديدة" src="' + esc(payload.preview_data) + '">' : '')
        + '<div id="tlErr" role="alert"></div><div class="acts"><button type="button" class="ep-b1" id="tlGo"' + (lines.length ? '' : ' disabled') + '>احفظ التعديل</button><button type="button" class="ep-b2" id="tlBack">ارجع للتعديل</button></div>';
      var go = q1('#tlGo', s), bk = q1('#tlBack', s), err = q1('#tlErr', s);
      bk.onclick = function () { if (!s.dataset.busy) form(vals); };
      go.onclick = function () {
        var body = { confirmed: true };
        ['title_ar', 'sort', 'judge_ok', 'place_prompt', 'preview_data'].forEach(function (k) {
          var changedKey = (k === 'title_ar' && payload[k] !== st.title) || (k === 'sort' && payload[k] !== st.sort) || (k === 'judge_ok' && payload[k] !== st.judgeOk) || (k === 'place_prompt' && hasPlace && payload[k] !== st.place) || (k === 'preview_data' && payload[k]);
          if (changedKey) body[k] = payload[k];
        });
        runWrite(s, go, bk, err, 'احفظ التعديل', function () { return api('/v2/tools/styles/' + encodeURIComponent(st.id), body, 'PUT'); }, X.writeError, function () { setNote('حُفظ تعديل «' + st.title + '»'); });
      };
      setTimeout(function () { try { bk.focus(); } catch (e) {} }, 30);
    }
    form();
  }
  function visibleSheet(sr, on) {
    var c = X.visibleCopy(sr.st, on, sr.sec.recipe.title);
    confirmSheet(c, false, function () { return api('/v2/tools/styles/' + encodeURIComponent(sr.st.id) + '/visible', { visible: on, base_updated_at: sr.sec.updatedAt, confirmed: true }); }, function () { setNote(c.done); });
  }
  function deleteSheet(sr) {
    var c = X.deleteCopy(sr.st, sr.sec.recipe.title);
    confirmSheet(c, true, function () { return api('/v2/tools/styles/' + encodeURIComponent(sr.st.id), { confirmed: true }, 'DELETE'); }, function () { setNote(c.done); });
  }

  // ------------------------------------------------------------------ العيّنات
  function drawSamples(v) {
    var d = viewSmp(), body;
    if (!d) body = stateBlock('smp', 'العيّنات');
    else if (!d.rows.length) body = '<div class="tl-empty"><b>لا عيّنات تنتظر</b><p>نسحب عيّنة من الأعمال، وأول عمل لكل مستخدم جديد، لتراجعها هنا</p></div>';
    else body = '<ul class="tl-cards samples">' + d.rows.map(function (r) {
      var pic = r.hasPreview ? '<span class="tl-spic" style="background-image:url(' + esc(r.preview) + ')" role="img" aria-label="صورة العمل"></span>' : '<span class="tl-spic none" role="img" aria-label="لا معاينة"><em>لا معاينة</em></span>';
      return '<li class="tl-card sample" data-id="' + esc(r.id) + '">' + pic + '<div class="tl-sbody"><h3>' + esc(r.recipe) + '</h3><p class="tl-meta">' + (r.style ? '<span>' + esc(r.style) + '</span>' : '') + (r.when ? '<span>' + esc(r.when) + '</span>' : '') + '</p>'
        + '<p class="tl-meta"><span class="tl-who" dir="ltr">' + esc(r.who || '—') + '</span></p>'
        + '<div class="tl-acts"><button type="button" class="ep-b1" data-a="mok" data-id="' + esc(r.id) + '">سليم</button><button type="button" class="ep-b2" data-a="mhide" data-id="' + esc(r.id) + '">أخفِ العمل</button><button type="button" class="ep-bs tl-del" data-a="mban" data-id="' + esc(r.id) + '">امنع صاحبه</button></div></div></li>';
    }).join('') + '</ul>';
    v.innerHTML = '<div class="v2s-tl" data-board="tl-samples">' + noteHtml() + back('العيّنات', d ? d.countText : '') + body + '</div>';
  }
  function moderateSheet(action, row) {
    var c = X.moderateCopy(action, row);
    confirmSheet(c, c.danger, function () { return api('/v2/tools/samples/' + encodeURIComponent(row.id), { action: action, confirmed: true }); }, function (res) { setNote(X.moderateDone(action, res)); }, X.moderateError);
  }

  // ------------------------------------------------------------------ التقرير
  function drawReport(v) {
    var d = viewRep(), key = repKey(), body;
    var chips = ['today', 'week', 'custom'].map(function (k) { return '<button type="button" class="tl-chipb' + (S.range === k ? ' on' : '') + '" data-a="range" data-k="' + k + '" aria-pressed="' + (S.range === k) + '">' + esc(X.RANGE_LABEL[k]) + '</button>'; }).join('');
    var custom = S.range === 'custom' ? '<div class="tl-dates tl-form"><div class="fld"><label for="tlFrom">من</label><input id="tlFrom" type="date" value="' + esc(S.cFrom) + '"></div><div class="fld"><label for="tlTo">إلى</label><input id="tlTo" type="date" value="' + esc(S.cTo) + '"></div><button type="button" class="ep-b1" data-a="rgo">اعرض</button></div>' + (S.rangeErr ? '<p class="tl-ce bad" role="alert">' + esc(S.rangeErr) + '</p>' : '') : '';
    if (S.range === 'custom' && !reportReady()) body = '<div class="tl-empty"><b>اختر الفترة</b><p>حدّد تاريخ البداية والنهاية ثم اضغط «اعرض»</p></div>';
    else if (!d) body = stateBlock(key, 'التقرير');
    else {
      var t = d.totals;
      var sum = '<div class="tl-stats big"><div><b>' + esc(t.count) + '</b><span>عمل</span></div><div class="' + (t.failHot ? 'hot' : '') + '"><b>' + esc(t.failures) + '</b><span>لم تنجح</span></div><div><b class="sm">' + esc(t.cost) + '</b><span>تكلفة المزوّد</span></div><div><b class="sm">' + esc(t.revenue) + '</b><span>الإيراد' + (t.revenueUsd ? '، ' + esc(t.revenueUsd) : '') + '</span></div></div>';
      var tb = '<div class="tl-tbw"><table class="tl-tb"><thead><tr><th>الأداة</th><th>الأعمال</th><th>لم تنجح</th><th>تكلفة المزوّد</th><th>الإيراد</th><th>الهامش</th></tr></thead><tbody>' + d.rows.map(function (r) {
        return '<tr' + (r.guard ? ' class="guard"' : '') + '><td><b>' + esc(r.title) + '</b>' + (r.guard ? '<small class="tl-gflag">' + esc(X.GUARD_NOTE) + '</small>' : '') + (r.avgText ? '<small>' + esc(r.avgText) + '</small>' : '') + '</td><td>' + esc(r.countText) + '</td><td>' + esc(r.failText) + '</td><td>' + esc(r.costText) + '</td><td>' + esc(r.revenueText) + '</td><td class="' + (r.marginNeg ? 'neg' : '') + '">' + esc(r.marginText) + '</td></tr>';
      }).join('') + '</tbody></table></div>';
      var cards = '<ul class="tl-cards rep">' + d.rows.map(function (r) {
        return '<li class="tl-card' + (r.guard ? ' guard' : '') + '"><div class="tl-ch"><h3>' + esc(r.title) + '</h3></div><p class="tl-facts2"><span>' + esc(r.countText) + ' عمل</span><span class="' + (r.failures ? 'hot' : '') + '">' + esc(r.failText) + ' لم تنجح</span></p><dl class="tl-kv"><div><dt>تكلفة المزوّد</dt><dd>' + esc(r.costText) + '</dd></div><div><dt>الإيراد</dt><dd>' + esc(r.revenueText) + '</dd></div><div><dt>الهامش</dt><dd class="' + (r.marginNeg ? 'neg' : '') + '">' + esc(r.marginText) + '</dd></div></dl>'
          + (r.guard ? '<p class="tl-gflag">' + esc(X.GUARD_NOTE) + '</p>' : '') + (r.avgText ? '<p class="tl-fine">' + esc(r.avgText) + '</p>' : '') + '</li>';
      }).join('') + '</ul>';
      var guardBtn = d.guardRows.length ? '<p class="tl-warn soft" role="status">' + esc(U.U(d.guardRows.length, ['أداة واحدة تحتاج مراجعة سعرها', 'أداتان تحتاجان مراجعة سعرهما', 'أدوات تحتاج مراجعة سعرها', 'أداة تحتاج مراجعة سعرها'])) + '<button type="button" class="ep-bs" data-a="go" data-sub="recipes">افتح الأدوات</button></p>' : '';
      var tp = '<section class="tl-topup" aria-label="شحن الرصيد"><h3>شحن «فلوسي»</h3><p class="tl-fine">' + esc(X.TOPUP_NOTE) + '</p><p class="tl-tpline' + (d.topups.available ? '' : ' na') + '">' + esc(d.topups.line) + '</p></section>';
      body = sum + guardBtn + tb + cards + tp;
      var per = d.period;
      S._per = per;
    }
    v.innerHTML = '<div class="v2s-tl" data-board="tl-report">' + noteHtml() + back('التقرير', d && d.period ? d.period : '') + '<div class="tl-ctl" role="group" aria-label="الفترة">' + chips + '</div>' + custom + '<div id="tlRepBody" aria-live="polite">' + body + '</div></div>';
  }

  // ------------------------------------------------------------------ الإعدادات
  function drawSettings(v) {
    var d = viewSet(), body;
    if (!d) body = stateBlock('set', 'الإعدادات');
    else {
      if (!S.form || S.formSrc !== src('set').data) { S.form = X.settingsInputs(d); S.formSrc = src('set').data; }     // بيانات جديدة من المنصة ⇒ الخانات من جديد
      var f = S.form;
      function fld(id, label, val, hint, key, mode) {
        return '<div class="fld"><label for="' + id + '">' + esc(label) + '</label><input id="' + id + '" inputmode="' + (mode || 'decimal') + '" autocomplete="off" value="' + esc(val) + '">' + (hint ? '<small>' + esc(hint) + '</small>' : '') + '<p class="tl-ce" id="tlE_' + key + '" role="alert"></p></div>';
      }
      body = '<div class="tl-form" id="tlSetForm">'
        + '<section class="tl-set"><h3>الصرف اليومي</h3>' + fld('tlS_cap', 'السقف اليومي بالدولار', f.cap, 'أقصى ما يُصرف على المزوّدين في اليوم. عند بلوغه يتوقف الاستوديو حتى الصباح', 'cap')
        + fld('tlS_capMax', 'أعلى سقف يمكن اختياره بالدولار', f.capMax, 'حدّ أمان ثانٍ: لا يزيد على ' + X.usdText(d.absolute_max_usd || 50), 'capMax') + '</section>'
        + '<section class="tl-set"><h3>حدود الاستخدام</h3>' + fld('tlS_perUser', 'أعمال المستخدم في اليوم', f.perUser, '', 'perUser', 'numeric') + fld('tlS_perIp', 'أعمال الشبكة الواحدة في اليوم', f.perIp, '', 'perIp', 'numeric')
        + fld('tlS_freePosts', 'البوستات المجانية في اليوم', f.freePosts, '', 'freePosts', 'numeric') + fld('tlS_retry', 'إعادات المحاولة المجانية بعد الفشل', f.retry, '', 'retry', 'numeric')
        + fld('tlS_sample', 'نسبة الأعمال التي تصلك للمراجعة (٪)', f.sample, 'إضافة إلى أول عمل لكل مستخدم جديد', 'sample', 'numeric') + '</section>'
        + '<section class="tl-set"><h3>شحن «فلوسي»</h3><p class="tl-fine">أرقام صحيحة. يبدأ الأعضاء من الحد الأدنى بكل عملة، ولا يتجاوزون السقف.</p>'
        + X.CURRENCIES.map(function (c) { return fld('tlS_tmin_' + c, 'أقل شحنة بـ' + X.CUR_NAME[c], f.tmin[c], '', 'tmin_' + c, 'numeric'); }).join('')
        + fld('tlS_tmax', 'سقف الشحن بالجنيه (أو ما يعادله بالعملات الأخرى)', f.tmax, '', 'tmax', 'numeric') + '</section>'
        + '<section class="tl-set"><h3>حارس السعر</h3><p class="tl-fine">لا تُحفظ أداة سعرها أقل من تكلفتها مضروبة في المضاعِف.</p>'
        + fld('tlS_imgM', 'المضاعِف للصور', f.imgM, '', 'imgM') + fld('tlS_vidM', 'المضاعِف للفيديو', f.vidM, '', 'vidM')
        + X.CURRENCIES.map(function (c) { return fld('tlS_rate_' + c, 'وحدات ' + X.CUR_SHORT[c] + ' لكل دولار', f.rate[c], c === 'USD' ? '' : '', 'rate_' + c); }).join('') + '</section>'
        + '<section class="tl-set"><h3>سطر «الجاي»</h3><div class="fld"><label for="tlS_next">سطر رمادي في آخر الاستوديو</label><input id="tlS_next" maxlength="80" autocomplete="off" value="' + esc(f.next) + '"><small>اتركه فارغًا ليختفي. بلا سعر ولا صورة</small><p class="tl-ce" id="tlE_next" role="alert"></p></div></section>'
        + '<div id="tlSetErr" role="alert"></div><div class="tl-savebar"><button type="button" class="ep-b1" data-a="sreview">راجع ثم احفظ</button><button type="button" class="ep-bs" data-a="sreset">أعد القيم الحالية</button></div></div>';
    }
    v.innerHTML = '<div class="v2s-tl" data-board="tl-settings">' + noteHtml() + back('الإعدادات', d ? 'تسري التعديلات فورًا بعد التأكيد' : '') + body + '</div>';
  }
  function collectSettings() {
    var f = { cap: q1('#tlS_cap').value, capMax: q1('#tlS_capMax').value, perUser: q1('#tlS_perUser').value, perIp: q1('#tlS_perIp').value, freePosts: q1('#tlS_freePosts').value, retry: q1('#tlS_retry').value,
              sample: q1('#tlS_sample').value, tmax: q1('#tlS_tmax').value, imgM: q1('#tlS_imgM').value, vidM: q1('#tlS_vidM').value, next: q1('#tlS_next').value, tmin: {}, rate: {} };
    X.CURRENCIES.forEach(function (c) { f.tmin[c] = q1('#tlS_tmin_' + c).value; f.rate[c] = q1('#tlS_rate_' + c).value; });
    return f;
  }
  function showSettingErrors(r) {
    qa('#tlSetForm .tl-ce').forEach(function (e) { var k = e.id.replace('tlE_', ''); e.textContent = r.errors[k] || ''; e.className = 'tl-ce' + (r.errors[k] ? ' bad' : ''); });
  }
  function refreshSettingErrors() {
    var d = viewSet(); if (!d || !q1('#tlSetForm')) return;
    var r = X.settingsCheck(collectSettings(), d);
    qa('#tlSetForm .tl-ce.bad').forEach(function (e) { var k = e.id.replace('tlE_', ''); e.textContent = r.errors[k] || ''; e.className = 'tl-ce' + (r.errors[k] ? ' bad' : ''); });
  }
  function settingsReview() {
    var d = viewSet(); if (!d) return;
    var f = collectSettings(); S.form = f;
    var r = X.settingsCheck(f, d);
    showSettingErrors(r);
    var box = q1('#tlSetErr');
    if (!r.ok) { box.innerHTML = '<div class="tl-err" role="alert">' + esc(r.error) + '</div>'; return; }
    box.innerHTML = '';
    var lines = X.settingsDiff(r.changes, d), hot = X.settingsHot(r.changes);
    var s = sheet('مراجعة الإعدادات', '<p class="mc-lead">سيُحفظ هذا التعديل، ويسري فورًا:</p><ul class="tl-diff">' + lines.map(function (l) { return '<li><b>' + esc(l.label) + '</b><span><s>' + esc(l.from) + '</s><i aria-hidden="true">←</i><em>' + esc(l.to) + '</em></span></li>'; }).join('') + '</ul>'
      + (hot.length ? '<ul class="tl-warns">' + hot.map(function (h) { return '<li>' + esc(h) + '</li>'; }).join('') + '</ul>' : '')
      + '<div id="tlErr" role="alert"></div><div class="acts"><button type="button" class="ep-b1" id="tlGo">احفظ الإعدادات</button><button type="button" class="ep-b2" id="tlNo">ارجع للتعديل</button></div>');
    if (!s) return;
    var go = q1('#tlGo', s), no = q1('#tlNo', s), err = q1('#tlErr', s);
    no.onclick = function () { if (!s.dataset.busy) window.closeModal(); };
    go.onclick = function () { runWrite(s, go, no, err, 'احفظ الإعدادات', function () { return api('/v2/tools/settings', { changes: r.changes, confirmed: true }, 'PUT'); }, X.settingsError, function () { S.form = null; setNote('حُفظت الإعدادات'); }); };
    setTimeout(function () { try { no.focus(); } catch (e) {} }, 30);
  }

  // ------------------------------------------------------------------ الرسم والأحداث
  function draw(v) {
    if (!v) return;
    if (!T.canWrite()) { v.innerHTML = '<div class="v2s-tl" data-board="tl-ro"><p class="tl-ro" role="status">هذا القسم للإدارة فقط</p></div>'; return; }
    if (S.sub === 'recipes') drawRecipes(v);
    else if (S.sub === 'styles') drawStyles(v);
    else if (S.sub === 'samples') drawSamples(v);
    else if (S.sub === 'report') drawReport(v);
    else if (S.sub === 'settings') drawSettings(v);
    else drawHub(v);
  }
  function scrollTop() { try { var c = document.querySelector('.content'); if (c) c.scrollTop = 0; window.scrollTo(0, 0); } catch (e) {} }
  function onClick(e) {
    var a = e.target.closest ? e.target.closest('[data-a]') : null;
    if (!a || !S.view.contains(a) || a.disabled) return;
    var k = a.getAttribute('data-a'), id = a.getAttribute('data-id'), w = T.canWrite();
    if (k === 'go') { S.sub = a.getAttribute('data-sub'); if (S.sub === 'settings') S.form = null; loadAll(false); redraw(); scrollTop(); }
    else if (k === 'hub') { S.sub = 'hub'; S.form = null; redraw(); scrollTop(); }
    else if (k === 'retry') { Object.keys(S.src).forEach(function (key) { var s = S.src[key]; if (s.state === 'error' || s.state === 'closed') s.state = 'loading'; }); loadAll(true); redraw(); }
    else if (k === 'kill' && w) killSheet(a.getAttribute('data-on') === '1');
    else if (k === 'enable' && w) { var r1 = recipeRow(id); if (r1) enableSheet(r1, a.getAttribute('data-on') === '1'); }
    else if (k === 'redit' && w) { var r2 = recipeRow(id); if (r2) recipeSheet(r2); }
    else if (k === 'rtest' && w) { var r3 = recipeRow(id); if (r3) testSheet(r3); }
    else if (k === 'sadd' && w) addSheet(id);
    else if (k === 'sedit' && w) { var s1 = styleRow(id); if (s1) editStyleSheet(s1); }
    else if (k === 'svis' && w) { var s2 = styleRow(id); if (s2) visibleSheet(s2, a.getAttribute('data-on') === '1'); }
    else if (k === 'sdel' && w) { var s3 = styleRow(id); if (s3) deleteSheet(s3); }
    else if ((k === 'mok' || k === 'mhide' || k === 'mban') && w) { var m1 = byId((viewSmp() || { rows: [] }).rows, id); if (m1) moderateSheet(k === 'mok' ? 'ok' : (k === 'mhide' ? 'hide' : 'ban_user'), m1); }
    else if (k === 'range') { S.range = a.getAttribute('data-k'); S.rangeErr = ''; if (S.range !== 'custom') load(repKey(), repPath(), false); redraw(); }
    else if (k === 'rgo') {
      var f = q1('#tlFrom', S.view), t = q1('#tlTo', S.view); S.cFrom = f ? f.value : ''; S.cTo = t ? t.value : '';
      var c = X.rangeCheck(S.cFrom, S.cTo); S.rangeErr = c.ok ? '' : c.error;
      if (c.ok) load(repKey(), repPath(), true);
      redraw();
    }
    else if (k === 'sreview' && w) settingsReview();
    else if (k === 'sreset') { S.form = null; draw(S.view); }
  }
  T.render = function (mod, view) {
    S.view = view;
    var E = ep();
    if (E && E.authed && T.canWrite()) loadAll(false);
    view.onclick = onClick;
    view.oninput = function (e) { if (e.target && e.target.closest && e.target.closest('#tlSetForm')) refreshSettingErrors(); };
    draw(view);
    if (!S.minute) S.minute = setInterval(function () {
      if (!isCurrent()) { clearInterval(S.minute); S.minute = null; return; }
      if (modalOpen() || formFocused() || !T.canWrite()) return;
      if (S.sub === 'hub') load('ov', P.ov, true);            // الصرف يتحرّك: نحدّث نظرة اليوم كل دقيقة والورقة مغلقة
      if (S.sub === 'hub' || S.sub === 'samples') redraw();
    }, 60000);
  };
  T._state = S;

  (window.V2SEC = window.V2SEC || {}).tools = { owns: T.owns, render: T.render };
})();
