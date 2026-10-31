/* ============================================================================
 * v2s/trainer_share.js — شاشة «نسبة المدرّب» داخل تبويب «المدرّبون» في قسم الدورات (SPEC-C-courses C2b).
 *
 * يعرض: قائمة المدرّبين بنسبتهم الأساسية وزيادة الإعلانات ومدتها وسببها · ورقة تعديل بالنصيب الحيّ (الناتج فقط) وإيداعات الإعلانات
 * وسجل التغييرات · بطاقة القواعد (الحد الأدنى مع كود المدرّب قابل للتعديل، والسقف ٦٥ للقراءة فقط).
 *
 * ⛔ المفتاح مقفول افتراضيًا: الملف بيتحمّل دايمًا لكن مفيش حاجة بترسم إلا لو courses.js نادى `V2TS.mount(...)` من تبويب المدرّبين.
 * ⛔ كل مصدر بيفشل لوحده: «غير متاح بعد» لا صفر كاذب. ولا كتابة بلا ورقة تأكيد، والكتابة كلها `confirmed:true` على
 *   `/api/v2/trainer-share*` (الفاعل من التوكن في الخادم).
 * الدوال النقية (`V2TS.helpers`) تتجرّب في node: `require('v2s/trainer_share.js')`.
 * ========================================================================== */
(function (root) {
  'use strict';
  var H = {};
  var CAP = 65, BASE_MIN = 35, BASE_MAX = 65, BONUS_MAX = 25;
  var NA = 'غير متاح بعد';
  var AR_D = '٠١٢٣٤٥٦٧٨٩';
  var MONTHS = ['يناير', 'فبراير', 'مارس', 'أبريل', 'مايو', 'يونيو', 'يوليو', 'أغسطس', 'سبتمبر', 'أكتوبر', 'نوفمبر', 'ديسمبر'];
  var CUR = { EGP: 'جنيه مصري', USD: 'دولار أمريكي', SAR: 'ريال سعودي', AED: 'درهم إماراتي', KWD: 'دينار كويتي', QAR: 'ريال قطري' };
  var CUR_COUNTRY = { EGP: 'مصر', SAR: 'السعودية', AED: 'الإمارات', KWD: 'الكويت', QAR: 'قطر', USD: 'دول أخرى' };

  // ------------------------------------------------------------------ دوال نقية
  function ar(n) { return String(n).replace(/\d/g, function (d) { return AR_D.charAt(+d); }); }
  function latin(s) {
    return String(s == null ? '' : s).replace(/[٠-٩]/g, function (d) { return String(AR_D.indexOf(d)); })
      .replace(/[۰-۹]/g, function (d) { return String('۰۱۲۳۴۵۶۷۸۹'.indexOf(d)); });
  }
  function isInt(n) { return typeof n === 'number' && isFinite(n) && Math.floor(n) === n; }
  function readInt(v) {
    if (typeof v === 'number') return isInt(v) ? v : null;
    var s = latin(v).replace(/[\s٪%]/g, '');
    return /^\d{1,3}$/.test(s) ? parseInt(s, 10) : null;
  }
  function str(v) { return typeof v === 'string' ? v.trim() : ''; }
  function datePart(s) { return /^\d{4}-\d{2}-\d{2}/.test(s) ? s.slice(0, 10) : ''; }
  function validDate(s) {
    if (!/^\d{4}-\d{2}-\d{2}$/.test(s)) return false;
    var d = new Date(s + 'T00:00:00Z');
    return !isNaN(d.getTime()) && d.toISOString().slice(0, 10) === s;
  }
  function dateText(iso) {
    var s = datePart(str(iso));
    if (!s) return '';
    return ar(parseInt(s.slice(8, 10), 10)) + ' ' + MONTHS[parseInt(s.slice(5, 7), 10) - 1] + ' ' + ar(s.slice(0, 4));
  }
  function periodText(from, until) {
    var f = dateText(from), u = dateText(until);
    if (f && u) return 'من ' + f + ' إلى ' + u;
    if (f) return 'من ' + f;
    if (u) return 'حتى ' + u;
    return '';
  }
  // هل زيادة الإعلانات سارية الآن؟ بلا «من» تبدأ من لحظة الحفظ، و«إلى» بتاريخ فقط = حتى آخر ذلك اليوم.
  function bonusActive(from, until, nowMs) {
    var f = str(from), u = str(until), now = typeof nowMs === 'number' ? nowMs : Date.now();
    if (f) { var fm = Date.parse(f); if (!isNaN(fm) && fm > now) return false; }
    if (u) {
      var um = Date.parse(u);
      if (!isNaN(um)) { if (/^\d{4}-\d{2}-\d{2}$/.test(u)) um += 86400000; if (now >= um) return false; }
    }
    return true;
  }
  // نصيب المدرّب = min(65، max(الأساسية، الحد الأدنى مع الكود لو البيع بكوده) + الزيادة)، والمنصة = ١٠٠ − النصيب. الناتج فقط.
  function shareTotals(base, bonus, o) {
    o = o || {};
    var b = isInt(base) ? base : BASE_MIN, bo = isInt(bonus) ? bonus : 0;
    if (o.bonusActive === false) bo = 0;
    var floor = o.viaCode && isInt(o.codeMin) ? Math.max(b, o.codeMin) : b;
    var trainer = Math.min(CAP, floor + bo);
    return { trainer: trainer, platform: 100 - trainer };
  }
  function totalLine(t) { return 'نصيب المدرّب الآن: ' + ar(t.trainer) + '٪ · المنصة ' + ar(t.platform) + '٪'; }

  var ERR = {
    base: 'اكتب نسبة أساسية صحيحة بين ' + ar(BASE_MIN) + ' و' + ar(BASE_MAX),
    bonus: 'اكتب زيادة صحيحة بين ٠ و' + ar(BONUS_MAX),
    date: 'اختر تاريخًا صالحًا',
    range: 'تاريخ النهاية قبل تاريخ البداية',
    reason: 'اكتب السبب (ثلاثة أحرف على الأقل)',
    codeMin: 'اكتب حدًّا أدنى صحيحًا بين ' + ar(BASE_MIN) + ' و' + ar(BASE_MAX)
  };
  // ورقة التعديل: v = {base, bonus, from, until, reason} نصوص الحقول ⇒ {ok, errors, payload}
  function validateSheet(v) {
    var errors = {}, base = readInt(v.base), bonus = str(latin(v.bonus)) === '' ? 0 : readInt(v.bonus);
    var from = str(v.from), until = str(v.until), reason = str(v.reason).replace(/\s+/g, ' ');
    if (base === null || base < BASE_MIN || base > BASE_MAX) errors.base = ERR.base;
    if (bonus === null || bonus < 0 || bonus > BONUS_MAX) errors.bonus = ERR.bonus;
    if (from && !validDate(from)) errors.from = ERR.date;
    if (until && !validDate(until)) errors.until = ERR.date;
    if (!errors.from && !errors.until && from && until && until < from) errors.until = ERR.range;
    if (reason.length < 3) errors.reason = ERR.reason;
    var ok = Object.keys(errors).length === 0, payload = null;
    if (ok) {
      payload = { base_pct: base, ads_bonus_pts: bonus, reason: reason.slice(0, 300) };
      if (from) payload.from = from;
      if (until) payload.until = until;
    }
    return { ok: ok, errors: errors, payload: payload };
  }
  function validateRules(v) {
    var errors = {}, min = readInt(v.codeMin), reason = str(v.reason).replace(/\s+/g, ' ');
    if (min === null || min < BASE_MIN || min > BASE_MAX) errors.codeMin = ERR.codeMin;
    if (reason.length < 3) errors.reason = ERR.reason;
    var ok = Object.keys(errors).length === 0;
    return { ok: ok, errors: errors, payload: ok ? { code_min_pct: min, reason: reason.slice(0, 300) } : null };
  }

  function rowOf(it) {
    if (!it || typeof it !== 'object') return null;
    var email = str(it.email).toLowerCase();
    if (!email) return null;
    return { email: email, name: str(it.name) || email, base: isInt(it.base_pct) ? it.base_pct : BASE_MIN, bonus: isInt(it.ads_bonus_pts) ? it.ads_bonus_pts : 0,
             reason: str(it.reason), from: str(it.from), until: str(it.until), updatedAt: str(it.updated_at), updatedBy: str(it.updated_by) };
  }
  function parseList(resp) {
    if (!resp || !Array.isArray(resp.items)) return null;
    return resp.items.map(rowOf).filter(Boolean);
  }
  function parseOne(resp) {
    var row = rowOf(resp);
    if (!row) return null;
    var lim = resp.limits && typeof resp.limits === 'object' ? resp.limits : {};
    var hist = (Array.isArray(resp.history) ? resp.history : []).filter(function (h) { return h && typeof h === 'object'; }).map(function (h) {
      return { base: isInt(h.base_pct) ? h.base_pct : null, bonus: isInt(h.ads_bonus_pts) ? h.ads_bonus_pts : 0, reason: str(h.reason), from: str(h.from), until: str(h.until), at: str(h.at), by: str(h.by) };
    });
    return { row: row, limits: { min: isInt(lim.min) ? lim.min : BASE_MIN, max: isInt(lim.max) ? lim.max : CAP, adsBonusMax: isInt(lim.ads_bonus_max) ? lim.ads_bonus_max : BONUS_MAX }, history: hist };
  }
  function parseRules(resp) {
    if (!resp || !isInt(resp.code_min_pct)) return null;
    return { codeMin: resp.code_min_pct, cap: isInt(resp.cap_pct) ? resp.cap_pct : CAP, updatedAt: str(resp.updated_at), updatedBy: str(resp.updated_by) };
  }

  function moneyText(amount, currency) {
    var n = Number(amount), c = str(currency).toUpperCase();
    if (!isFinite(n)) return '';
    var t = (Math.round(n * 100) / 100).toString().split('.');
    t[0] = t[0].replace(/\B(?=(\d{3})+(?!\d))/g, '٬');
    return ar(t.join('٫')) + ' ' + (CUR[c] || c);
  }
  function sumBy(entries) {
    var by = {}, order = [];
    entries.forEach(function (e) {
      var c = str(e.currency).toUpperCase(), n = Number(e.amount), country = str(e.country) || CUR_COUNTRY[c] || '';
      if (!c || !isFinite(n)) return;
      var k = c + '|' + country;
      if (!by[k]) { by[k] = { currency: c, country: country, amount: 0 }; order.push(k); }
      by[k].amount += n;
    });
    return order.map(function (k) { return by[k]; });
  }
  // من قراءة دفتر الإعلانات الموجودة (`/v2/ads-ledger`، نفس مصدر قسم الفلوس): أعمال المدرّب (دورات بريده) ⇒ إيداعات حسب العملة والبلد.
  // الجسر الحالي يرجّع الرصيد لا الإيداعات؛ لو جاءت `deposits` نعرضها إيداعات، وإلا نعرض الرصيد باسمه.
  // المبيعات قبل أول إيداع وبعده تظهر فقط لو الردّ فيها `sales_before` و`sales_after` لكل أعماله؛ وإلا ⇒ null (غير متاح بعد).
  function adsFor(resp, email) {
    if (!resp || !Array.isArray(resp.items)) return null;
    var e = str(email).toLowerCase();
    var mine = resp.items.filter(function (it) { return it && it.owner_kind === 'course' && str(it.owner_email).toLowerCase() === e; });
    var dep = [], bal = [], hasDeposits = false;
    mine.forEach(function (it) {
      if (Array.isArray(it.deposits)) { hasDeposits = true; dep = dep.concat(it.deposits.filter(Boolean)); }
      else if (Array.isArray(it.balance)) bal = bal.concat(it.balance.filter(Boolean));
    });
    var rows = sumBy(hasDeposits ? dep : bal).map(function (r) { return { currency: r.currency, country: r.country, amount: r.amount, text: moneyText(r.amount, r.currency) }; });
    var sales = null;
    if (mine.length && mine.every(function (it) { return isInt(it.sales_before) && isInt(it.sales_after); })) {
      sales = { before: mine.reduce(function (a, it) { return a + it.sales_before; }, 0), after: mine.reduce(function (a, it) { return a + it.sales_after; }, 0) };
    }
    return { owners: mine.length, kind: hasDeposits ? 'deposits' : 'balance', rows: rows, sales: sales };
  }

  H.ar = ar; H.latin = latin; H.readInt = readInt; H.isInt = isInt; H.dateText = dateText; H.periodText = periodText; H.bonusActive = bonusActive;
  H.shareTotals = shareTotals; H.totalLine = totalLine; H.validateSheet = validateSheet; H.validateRules = validateRules;
  H.parseList = parseList; H.parseOne = parseOne; H.parseRules = parseRules; H.adsFor = adsFor; H.moneyText = moneyText;
  H.NA = NA; H.CAP = CAP;

  if (typeof module !== 'undefined' && module.exports) module.exports = H;
  if (!root || !root.document) return;

  // ------------------------------------------------------------------ الواجهة
  var S = { list: { st: 'idle', data: null, at: 0 }, rules: { st: 'idle', data: null, at: 0 }, ads: { st: 'idle', data: null, at: 0 },
            note: '', noteT: null, busy: false };
  var STALE_MS = 60000;
  var SESSION_AR = 'انتهت الجلسة — سجّل الدخول من جديد ثم جرّب';
  var FAIL_AR = 'تعذّر تنفيذ العملية';
  var NOREPLY_AR = 'لم يصلنا رد من المنصة — حدّث الصفحة وتأكد قبل أن تعيد المحاولة';

  function esc(s) { return String(s == null ? '' : s).replace(/[&<>"']/g, function (c) { return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]; }); }
  function ep() { return root.EP || null; }
  function q(sel, r) { return (r || root.document).querySelector(sel); }
  function qa(sel, r) { return Array.prototype.slice.call((r || root.document).querySelectorAll(sel)); }
  function arDigits(t) { return String(t).replace(/\d/g, function (d) { return AR_D.charAt(+d); }); }
  function errMsg(e) {
    if (e && e.status === 401) return SESSION_AR;
    var d = (e && e.data) || {};
    if (d.no_reply) return NOREPLY_AR;
    if (typeof d.error === 'string' && d.error) return arDigits(d.error);
    return FAIL_AR;
  }

  function load(key, path, force) {
    var s = S[key], E = ep();
    if (!E || !E.api || !E.authed) return;
    if (s.st === 'loading') return;
    if (!force && s.st !== 'idle' && Date.now() - s.at < STALE_MS) return;
    s.st = s.data ? 'ready' : 'loading';
    var inflight = s.token = (s.token || 0) + 1;
    E.api(path).then(function (d) {
      if (inflight !== s.token) return;
      s.st = 'ready'; s.data = d; s.at = Date.now(); redraw();
    }).catch(function (e) {
      if (inflight !== s.token) return;
      if (e && e.status === 401) return;
      s.st = e && e.status === 404 ? 'closed' : 'error'; s.data = null; s.at = Date.now(); redraw();
    });
  }
  function loadAll(force) {
    load('list', '/v2/trainer-share', force);
    load('rules', '/v2/trainer-share-rules', force);
  }

  function chip(text, tone) { return '<span class="v2ts-chip ' + (tone || '') + '">' + esc(text) + '</span>'; }
  function avatar(name) { return '<span class="v2ts-av" aria-hidden="true">' + esc(String(name || '؟').trim().charAt(0) || '؟') + '</span>'; }
  function unavailable(label) { return '<div class="v2ts-na" role="status"><b>' + esc(label ? label + ': ' + NA : NA) + '</b><button type="button" class="v2ts-btn2" data-ts="retry">أعد المحاولة</button></div>'; }

  function rulesCard() {
    var r = S.rules, p = r.st === 'ready' ? parseRules(r.data) : null, inner;
    if (r.st === 'loading' || r.st === 'idle') inner = '<p class="v2ts-load">…جارٍ جلب القواعد</p>';
    else if (!p) inner = '<p class="v2ts-na-line">' + esc('القواعد: ' + NA) + '</p>';
    else inner = '<dl class="v2ts-rules"><div><dt>الحد الأدنى مع كود المدرّب</dt><dd>' + esc(ar(p.codeMin)) + '٪</dd></div>'
      + '<div><dt>السقف</dt><dd>' + esc(ar(p.cap)) + '٪ <small>ثابت</small></dd></div></dl>'
      + '<button type="button" class="v2ts-btn2" data-ts="rules">عدّل الحد الأدنى</button>';
    return '<div class="v2ts-card v2ts-rulescard" data-ts-card="rules"><h3>قواعد النسبة</h3>' + inner + '</div>';
  }
  function rowHtml(r) {
    var per = periodText(r.from, r.until);
    return '<li class="v2ts-row" data-email="' + esc(r.email) + '">' + avatar(r.name)
      + '<div class="v2ts-who"><b>' + esc(r.name) + '</b><span class="v2ts-mail" dir="ltr">' + esc(r.email) + '</span>'
      + '<span class="v2ts-chips">' + chip('الأساسية ' + ar(r.base) + '٪', 'wine') + (r.bonus > 0 ? chip('زيادة الإعلانات +' + ar(r.bonus), 'green') : chip('بلا زيادة', 'grey')) + '</span>'
      + (per && r.bonus > 0 ? '<span class="v2ts-per">' + esc(per) + '</span>' : '')
      + (r.reason ? '<span class="v2ts-why">' + esc(r.reason) + '</span>' : '') + '</div>'
      + '<button type="button" class="v2ts-btn2" data-ts="edit" data-email="' + esc(r.email) + '" aria-label="' + esc('عدّل نسبة ' + r.name) + '">عدّل النسبة</button></li>';
  }
  function listHtml() {
    var l = S.list;
    if (l.st === 'loading' || l.st === 'idle') return '<p class="v2ts-load">…جارٍ جلب المدرّبين</p>';
    var rows = l.st === 'ready' ? parseList(l.data) : null;
    if (!rows) return unavailable('نسب المدرّبين');
    if (!rows.length) return '<p class="v2ts-none">لا مدرّبين معتمدين بعد</p>';
    return '<ul class="v2ts-list">' + rows.map(rowHtml).join('') + '</ul>';
  }
  function noteHtml() { return S.note ? '<div class="v2ts-ok" role="status">' + esc(S.note) + '</div>' : ''; }
  function sectionHtml() {
    return '<header class="v2ts-h"><h2>نسبة المدرّب</h2><p>النسبة الأساسية وزيادة الإعلانات لكل مدرّب. يسري التغيير على المبيعات الجديدة فقط.</p></header>'
      + noteHtml() + rulesCard() + '<div class="v2ts-card" data-ts-card="list">' + listHtml() + '</div>';
  }
  function hostEl() { return q('[data-ts-host]'); }
  function redraw() {
    var h = hostEl();
    if (h) { h.innerHTML = sectionHtml(); wire(h); }
    if (typeof S.adsPaint === 'function' && q('#ts_ads')) S.adsPaint();      // ورقة التعديل مفتوحة: حدّث إعلاناتها
  }
  function setNote(t) {
    S.note = t; clearTimeout(S.noteT);
    S.noteT = setTimeout(function () { S.note = ''; redraw(); }, 12000);
    redraw();
  }

  // ------------------------------------------------------------------ الأوراق
  function openSheet(title, html) {
    if (typeof root.openModal !== 'function') return null;
    var s = root.openModal(title, '<div class="v2ts-m">' + html + '</div>');
    var x = q('[data-x]', s);
    if (x) x.onclick = function () { if (!s.dataset.busy) root.closeModal(); };
    s.onclick = function (e) { if (e.target === s && !s.dataset.busy) root.closeModal(); };
    return s;
  }
  function fld(id, label, inner, hint, err) {
    return '<div class="v2ts-fld"><label for="' + id + '">' + esc(label) + '</label>' + inner + (hint ? '<small>' + esc(hint) + '</small>' : '')
      + '<em class="v2ts-ferr" data-err="' + id + '" role="alert">' + esc(err || '') + '</em></div>';
  }
  function numInput(id, val, ph) { return '<input id="' + id + '" type="text" inputmode="numeric" autocomplete="off" value="' + esc(val == null ? '' : ar(val)) + '" placeholder="' + esc(ph || '') + '">'; }

  function adsHtml(email) {
    var a = S.ads;
    if (a.st === 'idle' || a.st === 'loading') return '<p class="v2ts-load">…جارٍ جلب إعلانات المدرّب</p>';
    var p = a.st === 'ready' ? adsFor(a.data, email) : null;
    var dep, sal;
    if (!p) { dep = '<p class="v2ts-na-line">' + esc('إيداعات الإعلانات: ' + NA) + '</p>'; sal = '<p class="v2ts-na-line">' + esc('المبيعات قبل الإيداع وبعده: ' + NA) + '</p>'; }
    else {
      if (!p.owners) dep = '<p class="v2ts-none sm">لا أعمال إعلانية لهذا المدرّب حتى الآن</p>';
      else if (!p.rows.length) dep = '<p class="v2ts-none sm">لا إيداعات إعلانات حتى الآن</p>';
      else dep = '<ul class="v2ts-dep">' + p.rows.map(function (r) { return '<li><span>' + esc(r.country || '') + '</span><b>' + esc(r.text) + '</b></li>'; }).join('') + '</ul>';
      sal = p.sales ? '<p class="v2ts-sales">مبيعات قبل أول إيداع: <b>' + esc(ar(p.sales.before)) + '</b> · بعده: <b>' + esc(ar(p.sales.after)) + '</b></p>'
        : '<p class="v2ts-na-line">' + esc('المبيعات قبل الإيداع وبعده: ' + NA) + '</p>';
    }
    var title = p && p.kind === 'balance' && p.rows.length ? 'رصيد إعلانات المدرّب الآن' : 'إيداعات الإعلانات';
    return '<div class="v2ts-ads"><h4>' + esc(title) + '</h4>' + dep + sal + '</div>';
  }
  function historyHtml(one) {
    if (one.st === 'idle' || one.st === 'loading') return '<p class="v2ts-load">…جارٍ جلب السجل</p>';
    var p = one.st === 'ready' ? parseOne(one.data) : null;
    if (!p) return '<p class="v2ts-na-line">' + esc('سجل التغييرات: ' + NA) + '</p>';
    if (!p.history.length) return '<p class="v2ts-none sm">لا تغييرات سابقة</p>';
    return '<ul class="v2ts-hist">' + p.history.slice().reverse().slice(0, 12).map(function (h) {
      var per = periodText(h.from, h.until);
      return '<li><time>' + esc(dateText(h.at)) + '</time><b>' + esc((h.base != null ? 'الأساسية ' + ar(h.base) + '٪' : '') + (h.bonus > 0 ? ' · زيادة +' + ar(h.bonus) : '')) + '</b>'
        + (per && h.bonus > 0 ? '<span>' + esc(per) + '</span>' : '') + (h.reason ? '<span>' + esc(h.reason) + '</span>' : '')
        + (h.by ? '<small dir="ltr">' + esc(h.by) + '</small>' : '') + '</li>';
    }).join('') + '</ul>';
  }

  function openEdit(email) {
    var rows = S.list.st === 'ready' ? parseList(S.list.data) : null;
    var row = rows && rows.filter(function (r) { return r.email === email; })[0];
    if (!row) return;
    var rules = S.rules.st === 'ready' ? parseRules(S.rules.data) : null;
    var one = { st: 'loading', data: null }, E = ep();
    var s = openSheet('نسبة المدرّب: ' + row.name, '<div class="v2ts-stage"></div>');
    if (!s) return;
    var stage = q('.v2ts-stage', s), step = 'form', payload = null;
    load('ads', '/v2/ads-ledger', false);
    if (E && E.api) {
      E.api('/v2/trainer-share/' + encodeURIComponent(email)).then(function (d) { one.st = 'ready'; one.data = d; paintExtras(); })
        .catch(function (e) { one.st = e && e.status === 404 ? 'closed' : 'error'; paintExtras(); });
    }
    S.adsPaint = paintExtras;
    function vals() {
      return { base: q('#ts_base', s).value, bonus: q('#ts_bonus', s).value, from: q('#ts_from', s).value, until: q('#ts_until', s).value, reason: q('#ts_reason', s).value };
    }
    function paintTotal() {
      var box = q('#ts_total', s);
      if (!box) return;
      var base = readInt(q('#ts_base', s).value), bonus = str(latin(q('#ts_bonus', s).value)) === '' ? 0 : readInt(q('#ts_bonus', s).value);
      var okNums = base !== null && base >= BASE_MIN && base <= BASE_MAX && bonus !== null && bonus >= 0 && bonus <= BONUS_MAX;
      if (!okNums) { box.innerHTML = '<span class="v2ts-totna">اكتب نسبة أساسية وزيادة صحيحتين لترى النصيب</span>'; return; }
      var active = bonusActive(q('#ts_from', s).value, q('#ts_until', s).value, Date.now());
      var t = shareTotals(base, bonus, { bonusActive: active });
      box.innerHTML = '<b>' + esc(totalLine(t)) + '</b>'
        + (bonus > 0 && !active ? '<small>الزيادة خارج مدتها الآن فلا تدخل في النصيب</small>' : '')
        + (rules ? '<small>' + esc('مع بيع بكود المدرّب: ' + totalLine(shareTotals(base, bonus, { bonusActive: active, viaCode: true, codeMin: rules.codeMin })).replace('نصيب المدرّب الآن: ', 'نصيبه ')) + '</small>' : '');
    }
    function paintExtras() {
      var a = q('#ts_ads', s), h = q('#ts_hist', s);
      if (a) a.innerHTML = adsHtml(email);
      if (h) h.innerHTML = historyHtml(one);
    }
    function showErrors(errors) {
      qa('[data-err]', s).forEach(function (n) { n.textContent = ''; });
      Object.keys(errors).forEach(function (k) { var n = q('[data-err="ts_' + k + '"]', s); if (n) n.textContent = errors[k]; });
    }
    function form() {
      var f = row.bonus > 0 ? row : { from: '', until: '' };
      stage.innerHTML = '<div class="v2ts-total" id="ts_total" aria-live="polite"></div>'
        + fld('ts_base', 'النسبة الأساسية', numInput('ts_base', row.base), 'رقم صحيح بين ' + ar(BASE_MIN) + ' و' + ar(BASE_MAX) + '٪')
        + fld('ts_bonus', 'زيادة الإعلانات', numInput('ts_bonus', row.bonus), 'نقاط تُضاف إلى النسبة، من ٠ إلى ' + ar(BONUS_MAX))
        + '<div class="v2ts-two">' + fld('ts_from', 'من', '<input id="ts_from" type="date" value="' + esc(datePart(f.from)) + '">')
        + fld('ts_until', 'إلى', '<input id="ts_until" type="date" value="' + esc(datePart(f.until)) + '">') + '</div>'
        + fld('ts_reason', 'السبب', '<textarea id="ts_reason" rows="3" maxlength="300" placeholder="لماذا هذا التغيير؟"></textarea>', 'مطلوب، ويُحفظ في سجل التغييرات')
        + '<div id="ts_ads">' + adsHtml(email) + '</div>'
        + '<div class="v2ts-histbox"><h4>سجل التغييرات</h4><div id="ts_hist">' + historyHtml(one) + '</div></div>'
        + '<div class="v2ts-err" id="ts_err"></div>'
        + '<div class="v2ts-macts"><button type="button" class="v2ts-btn1" id="ts_next">راجع واحفظ</button><button type="button" class="v2ts-btn2" id="ts_close">إغلاق</button></div>';
      qa('input,textarea', stage).forEach(function (i) {
        var clear = function () { var m = q('[data-err="' + i.id + '"]', s); if (m) m.textContent = ''; };
        i.addEventListener('input', function () { clear(); paintTotal(); });
        i.addEventListener('change', function () { clear(); paintTotal(); });
      });
      paintTotal();
      q('#ts_close', s).onclick = function () { root.closeModal(); };
      q('#ts_next', s).onclick = function () {
        var v = validateSheet(vals());
        showErrors(v.errors);
        if (!v.ok) { var first = Object.keys(v.errors)[0]; var el = q('#ts_' + first, s); if (el) el.focus(); return; }
        payload = v.payload; step = 'confirm'; confirm();
      };
    }
    function confirm() {
      var active = bonusActive(payload.from || '', payload.until || '', Date.now());
      var t = shareTotals(payload.base_pct, payload.ads_bonus_pts, { bonusActive: active });
      var per = periodText(payload.from, payload.until);
      stage.innerHTML = '<p class="v2ts-lead">راجع التغيير قبل الحفظ:</p><ul class="v2ts-will">'
        + '<li>النسبة الأساسية لـ«' + esc(row.name) + '»: <b>' + esc(ar(payload.base_pct)) + '٪</b></li>'
        + '<li>' + (payload.ads_bonus_pts > 0 ? 'زيادة الإعلانات: <b>+' + esc(ar(payload.ads_bonus_pts)) + '</b>' + (per ? ' (' + esc(per) + ')' : ' (من لحظة الحفظ)') : 'بلا زيادة إعلانات') + '</li>'
        + '<li>' + esc(totalLine(t)) + '</li>'
        + '<li>السبب: ' + esc(payload.reason) + '</li>'
        + '<li>يسري على المبيعات الجديدة فقط، وما بيع قبل اليوم يبقى بنسبته.</li></ul>'
        + '<div class="v2ts-err" id="ts_err"></div>'
        + '<div class="v2ts-macts"><button type="button" class="v2ts-btn1" id="ts_go">أكّد الحفظ</button><button type="button" class="v2ts-btn2" id="ts_back">رجوع</button></div>';
      q('#ts_back', s).onclick = function () { step = 'form'; form(); restore(); };
      q('#ts_go', s).onclick = function () { send(this); };
    }
    function restore() {
      q('#ts_base', s).value = ar(payload.base_pct); q('#ts_bonus', s).value = ar(payload.ads_bonus_pts);
      q('#ts_from', s).value = payload.from || ''; q('#ts_until', s).value = payload.until || ''; q('#ts_reason', s).value = payload.reason;
      paintTotal();
    }
    function send(btn) {
      if (S.busy || !E || !E.api) return;
      S.busy = true; s.dataset.busy = '1'; btn.disabled = true;
      var back = q('#ts_back', s); if (back) back.disabled = true;
      var label = btn.textContent; btn.textContent = 'جارٍ الحفظ…';
      var body = { base_pct: payload.base_pct, ads_bonus_pts: payload.ads_bonus_pts, reason: payload.reason, confirmed: true };
      if (payload.from) body.from = payload.from;
      if (payload.until) body.until = payload.until;
      E.api('/v2/trainer-share/' + encodeURIComponent(email), { method: 'PUT', body: body }).then(function () {
        S.busy = false; delete s.dataset.busy; S.adsPaint = null;
        root.closeModal(); setNote('تم حفظ نسبة «' + row.name + '»'); load('list', '/v2/trainer-share', true);
      }).catch(function (e) {
        S.busy = false; delete s.dataset.busy;
        var noReply = e && e.data && e.data.no_reply;
        var box = q('#ts_err', s); if (box) box.innerHTML = '<div class="v2ts-errbox" role="alert">' + esc(errMsg(e)) + '</div>';
        if (noReply) { btn.textContent = label; btn.disabled = true; load('list', '/v2/trainer-share', true); if (back) back.disabled = false; return; }
        btn.disabled = false; btn.textContent = label; if (back) back.disabled = false;
      });
    }
    form();
  }

  function openRules() {
    var p = S.rules.st === 'ready' ? parseRules(S.rules.data) : null;
    if (!p) return;
    var s = openSheet('الحد الأدنى مع كود المدرّب', '<div class="v2ts-stage"></div>');
    if (!s) return;
    var stage = q('.v2ts-stage', s), E = ep(), payload = null;
    function vals() { return { codeMin: q('#tr_min', s).value, reason: q('#tr_reason', s).value }; }
    function form() {
      stage.innerHTML = '<p class="v2ts-lead">عند البيع بكود المدرّب لا يقل نصيبه عن هذا الحد، ولو كانت نسبته الأساسية أقل.</p>'
        + fld('tr_min', 'الحد الأدنى مع كود المدرّب', numInput('tr_min', p.codeMin), 'رقم صحيح بين ' + ar(BASE_MIN) + ' و' + ar(BASE_MAX) + '٪')
        + '<div class="v2ts-fld"><label>السقف</label><div class="v2ts-ro">' + esc(ar(p.cap)) + '٪ <small>ثابت ولا يُعدَّل من هنا</small></div></div>'
        + fld('tr_reason', 'السبب', '<textarea id="tr_reason" rows="3" maxlength="300" placeholder="لماذا هذا التغيير؟"></textarea>', 'مطلوب، ويُحفظ في السجل')
        + '<div class="v2ts-err" id="tr_err"></div>'
        + '<div class="v2ts-macts"><button type="button" class="v2ts-btn1" id="tr_next">راجع واحفظ</button><button type="button" class="v2ts-btn2" id="tr_close">إغلاق</button></div>';
      q('#tr_close', s).onclick = function () { root.closeModal(); };
      qa('input,textarea', stage).forEach(function (i) { i.addEventListener('input', function () { var m = q('[data-err="' + i.id + '"]', s); if (m) m.textContent = ''; }); });
      q('#tr_next', s).onclick = function () {
        var v = validateRules(vals());
        qa('[data-err]', s).forEach(function (n) { n.textContent = ''; });
        Object.keys(v.errors).forEach(function (k) { var n = q('[data-err="' + (k === 'codeMin' ? 'tr_min' : 'tr_' + k) + '"]', s); if (n) n.textContent = v.errors[k]; });
        if (!v.ok) return;
        payload = v.payload; confirm();
      };
    }
    function confirm() {
      stage.innerHTML = '<p class="v2ts-lead">راجع التغيير قبل الحفظ:</p><ul class="v2ts-will">'
        + '<li>الحد الأدنى مع كود المدرّب: <b>' + esc(ar(payload.code_min_pct)) + '٪</b></li>'
        + '<li>السقف يبقى ' + esc(ar(p.cap)) + '٪</li><li>السبب: ' + esc(payload.reason) + '</li>'
        + '<li>يسري على المبيعات الجديدة فقط.</li></ul><div class="v2ts-err" id="tr_err"></div>'
        + '<div class="v2ts-macts"><button type="button" class="v2ts-btn1" id="tr_go">أكّد الحفظ</button><button type="button" class="v2ts-btn2" id="tr_back">رجوع</button></div>';
      q('#tr_back', s).onclick = function () { form(); q('#tr_min', s).value = ar(payload.code_min_pct); q('#tr_reason', s).value = payload.reason; };
      q('#tr_go', s).onclick = function () {
        var btn = this;
        if (S.busy || !E || !E.api) return;
        S.busy = true; s.dataset.busy = '1'; btn.disabled = true; var label = btn.textContent; btn.textContent = 'جارٍ الحفظ…';
        var back = q('#tr_back', s); if (back) back.disabled = true;
        E.api('/v2/trainer-share-rules', { method: 'PUT', body: { code_min_pct: payload.code_min_pct, reason: payload.reason, confirmed: true } }).then(function () {
          S.busy = false; delete s.dataset.busy; root.closeModal(); setNote('تم حفظ الحد الأدنى مع كود المدرّب'); load('rules', '/v2/trainer-share-rules', true);
        }).catch(function (e) {
          S.busy = false; delete s.dataset.busy;
          var box = q('#tr_err', s); if (box) box.innerHTML = '<div class="v2ts-errbox" role="alert">' + esc(errMsg(e)) + '</div>';
          var noReply = e && e.data && e.data.no_reply;
          btn.textContent = label; btn.disabled = !!noReply; if (back) back.disabled = false;
          if (noReply) load('rules', '/v2/trainer-share-rules', true);
        });
      };
    }
    form();
  }

  function wire(h) {
    qa('[data-ts="edit"]', h).forEach(function (b) { b.onclick = function () { openEdit(b.getAttribute('data-email')); }; });
    qa('[data-ts="rules"]', h).forEach(function (b) { b.onclick = openRules; });
    qa('[data-ts="retry"]', h).forEach(function (b) { b.onclick = function () { loadAll(true); }; });
  }

  // يُنادى من courses.js بعد رسم تبويب «المدرّبون»: يضيف القسم تحت الشاشة ويرسمه من آخر ما وصل (بلا وميض) ثم يحدّث.
  function mount(parent) {
    if (!parent || !parent.appendChild) return null;
    qa('[data-ts-host]', parent).forEach(function (n) { n.remove(); });
    var sec = root.document.createElement('section');
    sec.className = 'v2ts';
    sec.setAttribute('data-ts-host', '1');
    sec.setAttribute('aria-label', 'نسبة المدرّب');
    parent.appendChild(sec);
    sec.innerHTML = sectionHtml();
    wire(sec);
    loadAll(false);
    return sec;
  }

  root.V2TS = { mount: mount, helpers: H, _state: S, _redraw: redraw };
})(typeof window !== 'undefined' ? window : this);
