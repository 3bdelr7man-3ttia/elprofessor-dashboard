/* ============================================================================
 * v2-logic.js — الجزء النقي من اللوحة الجديدة (D1). ⛔ لا DOM ولا شبكة ولا ساعة خفية:
 * كل دالة تأخذ مدخلاتها وتعيد قيمة، و`now` يُمرَّر صراحةً (opts.now / extras.now) فيُختبَر بـnode.
 *
 *   v2Tiles(queue, extras)              ⇒ ١٢ مربّعًا {key,label,img,count,hot,failed,partial,next,dest,land}
 *   v2Decisions(rows, payouts, queue, opts) ⇒ بطاقات القرارات مرتّبة
 *   v2Card(row, opts)                   ⇒ بطاقة واحدة {kind,tag,title,sub,brain,reason,primary,secondary,…}
 *   v2Next(decisions)                   ⇒ أول بطاقة أو null
 *   v2Health(queue)                     ⇒ {ok,failed,alerts[],heartbeats[]}
 *   v2BrainLog(rows, now)               ⇒ ما وزّعه العقل اليوم (سجل بلا «اعكس» في D1)
 *
 * ⛔ لا اقتراح ذكاء اصطناعي هنا: اقتراح العقل يُبنى فقط من بيانات مخزّنة عندنا (`candidates[].auto_pick` ·
 * `assign_log` · الساعات · المبالغ · الأعداد). ولا حساب رقم ثانٍ: كل عدّاد يُقرأ من طابور المنصة أو من
 * قائمة محمّلة أصلًا، والعدّاد الذي تعذّر جلبه `null` + `failed:true` — **لا صفرًا** أبدًا.
 *
 * ⛔ نصوص ظاهرة: فصحى بسيطة بلا مصطلحات تقنية، ولا عنوان يبدأ بـ«ذكاء» أو «AI». محرّك القرار اسمه «العقل».
 * ========================================================================== */
(function (root) {
  'use strict';

  var DIG = '٠١٢٣٤٥٦٧٨٩';
  var DAY = 86400e3, HOUR = 3600e3, MIN = 60e3;

  // ------------------------------------------------------------------ أدوات صغيرة
  function ar(n) {
    n = Number(n);
    if (!isFinite(n)) n = 0;
    return String(Math.round(n)).replace(/\d/g, function (d) { return DIG.charAt(+d); });
  }
  // رقم بفاصل آلاف عربي ٫ كسور بحدّ منزلتين — للمبالغ.
  function fmt(n) {
    n = Number(n);
    if (!isFinite(n)) return '—';
    var neg = n < 0 ? '-' : '';
    n = Math.abs(n);
    var whole = Math.floor(n), frac = Math.round((n - whole) * 100);
    if (frac === 100) { whole += 1; frac = 0; }
    var s = String(whole).replace(/\B(?=(\d{3})+(?!\d))/g, '٬');
    s = s.replace(/\d/g, function (d) { return DIG.charAt(+d); });
    if (frac) s += '٫' + (frac < 10 ? '٠' : '') + ar(frac).replace(/٠+$/, function (z) { return frac % 10 ? z : ''; });
    return neg + s;
  }
  // صيغة العدد العربية: forms = [المفرد الكامل, المثنّى الكامل, «عدد + جمع», «عدد + تمييز مفرد»]
  //   U(1,['تحويل واحد','تحويلان','تحويلات','تحويلًا']) ⇒ «تحويل واحد» · ٢ ⇒ «تحويلان» · ٣ ⇒ «٣ تحويلات» · ١١ ⇒ «١١ تحويلًا»
  function U(n, forms) {
    n = Math.round(Number(n) || 0);
    if (n === 1) return forms[0];
    if (n === 2) return forms[1];
    if (n >= 3 && n <= 10) return ar(n) + ' ' + forms[2];
    return ar(n) + ' ' + forms[3];
  }
  function qn(Q, key) {
    if (!Q) return 0;
    var v = Q[key];
    if (v && typeof v === 'object') return Number(v.count) || 0;
    return Number(v) || 0;
  }
  function listLen(v) {
    if (Array.isArray(v)) return v.length;
    if (v && typeof v === 'object') return Number(v.count) || 0;
    return Number(v) || 0;
  }
  function str(v) { return typeof v === 'string' ? v.trim() : ''; }
  function ms(iso) {
    if (typeof iso === 'number') return isFinite(iso) && iso > 0 ? iso : NaN;
    var t = Date.parse(iso || '');
    return isNaN(t) ? NaN : t;
  }
  function shorten(s, n) {
    s = String(s == null ? '' : s).replace(/\s+/g, ' ').trim();
    return s.length > n ? s.slice(0, n) + '…' : s;
  }
  function clean(arr) { return arr.filter(function (x) { return x; }); }

  var CUR_NAME = { EGP: 'جنيه', USD: 'دولار', SAR: 'ريال', EUR: 'يورو', AED: 'درهم', GBP: 'جنيه إسترليني', KWD: 'دينار', QAR: 'ريال' };
  function curName(c) {
    c = String(c || 'EGP').trim().toUpperCase();
    return CUR_NAME[c] || c;
  }
  function moneyText(amount, cur) {
    if (amount == null || amount === '' || isNaN(Number(amount))) return '';
    return fmt(amount) + ' ' + curName(cur);
  }

  // «منذ ٣ ساعات» — من وقت بالميلي ثانية و`now`. وقت غير معروف ⇒ "".
  function agoText(t, now) {
    t = ms(t);
    if (isNaN(t)) return '';
    var d = Math.max(0, (now || 0) - t);
    var m = Math.floor(d / MIN);
    if (m < 1) return 'الآن';
    if (m < 60) return 'منذ ' + U(m, ['دقيقة', 'دقيقتين', 'دقائق', 'دقيقة']);
    var h = Math.floor(m / 60);
    if (h < 24) return 'منذ ' + U(h, ['ساعة', 'ساعتين', 'ساعات', 'ساعة']);
    var dd = Math.floor(h / 24);
    return 'منذ ' + U(dd, ['يوم', 'يومين', 'أيام', 'يومًا']);
  }
  function hoursBetween(t, now) {
    t = ms(t);
    if (isNaN(t)) return 0;
    return Math.max(0, Math.floor(((now || 0) - t) / HOUR));
  }
  function hoursWord(h) { return U(h, ['ساعة واحدة', 'ساعتين', 'ساعات', 'ساعة']); }
  function sameLocalDay(a, b) {
    var x = new Date(a), y = new Date(b);
    return x.getFullYear() === y.getFullYear() && x.getMonth() === y.getMonth() && x.getDate() === y.getDate();
  }
  function hhmm(t) {
    var d = new Date(t);
    var h = d.getHours(), m = d.getMinutes();
    var ap = h >= 12 ? 'م' : 'ص';
    h = h % 12; if (h === 0) h = 12;
    return ar(h) + ':' + (m < 10 ? '٠' : '') + ar(m) + ' ' + ap;
  }

  // ------------------------------------------------------------------ المربّعات
  var TILE_DEFS = [
    { key: 'files', label: 'ملفات الخبراء', img: 'files' },
    { key: 'disputes', label: 'النزاعات والاستردادات', img: 'disputes' },
    { key: 'courses', label: 'الدورات والمدرّبون', img: 'courses' },
    { key: 'market', label: 'سوق الخدمات', img: 'market' },
    { key: 'books', label: 'الكتب', img: 'books' },
    { key: 'people', label: 'الناس والدعوات', img: 'people' },
    { key: 'money', label: 'الفلوس', img: 'money' },
    { key: 'content', label: 'المحتوى', img: 'content' },
    { key: 'marketing', label: 'التسويق', img: 'marketing' },
    { key: 'reports', label: 'التقارير', img: 'reports' },
    { key: 'brain', label: 'العقل', img: 'brain' },
    { key: 'company', label: 'الشركة ورأس المال', img: 'company' }
  ];
  var FAILED_TEXT = 'تعذّر الجلب';

  function baseTile(def) {
    return { key: def.key, label: def.label, img: def.img, count: null, hot: false, failed: false, partial: false,
             next: '', dest: null, land: null, internal: false };
  }
  function failTile(t) { t.failed = true; t.count = null; t.hot = false; t.next = FAILED_TEXT; return t; }
  // عدّاد ناقص معلَن: «العدد ناقص» أول جملة في السطر (السطر مقصوص بسطرين/٣ في الموبايل — التحذير آخر شيء يُخفى).
  var PARTIAL_TEXT = 'العدد ناقص';
  function markPartial(t) {
    if (t.failed) return t;
    t.partial = true;
    if (t.next.indexOf(PARTIAL_TEXT) !== 0) t.next = PARTIAL_TEXT + (t.next ? ' · ' + t.next : '');
    return t;
  }
  function hasTrunc(extras) { return !!(extras && Array.isArray(extras.inboxTruncated) && extras.inboxTruncated.length); }

  function inboxFailedHas(extras, label) {
    var f = extras && extras.inboxFailed;
    return Array.isArray(f) && f.indexOf(label) > -1;
  }
  function rowsOfKind(rows, kind) {
    return (rows || []).filter(function (r) { return r && r.apiKind === kind && !r.fyi; });
  }

  // سجل العقل اليوم: كل توزيع `by:'auto'` في `assign_log` ملف اليوم، من صفوف الوارد (ولا طلب ثانٍ للمنصة).
  function v2BrainLog(rows, now) {
    var out = [], seen = {};
    (rows || []).forEach(function (r) {
      var f = r && r.ef;
      if (!f || !Array.isArray(f.assign_log)) return;
      var names = {};
      (Array.isArray(f.candidates) ? f.candidates : []).forEach(function (c) { if (c && c.email) names[String(c.email).toLowerCase()] = c.name; });
      (Array.isArray(f.declined) ? f.declined : []).forEach(function (d) { if (d && d.email && d.name) names[String(d.email).toLowerCase()] = d.name; });
      if (f.assigned_to && f.assigned_name) names[String(f.assigned_to).toLowerCase()] = f.assigned_name;
      if (f.expert_email && f.expert_name) names[String(f.expert_email).toLowerCase()] = f.expert_name;
      f.assign_log.forEach(function (e) {
        if (!e || typeof e !== 'object' || e.by !== 'auto' || typeof e.to !== 'string' || !e.to) return;
        var t = ms(e.at);
        if (isNaN(t) || !sameLocalDay(t, now)) return;
        var key = [f.id, e.at, e.to].join('|');
        if (seen[key]) return;
        seen[key] = true;
        out.push({ at: t, time: hhmm(t), who: names[e.to.toLowerCase()] || e.to, title: str(f.title) || 'ملف',
                   why: shorten(e.why, 160), fileId: f.id || '' });
      });
    });
    out.sort(function (a, b) { return b.at - a.at; });
    return out;
  }

  function v2Tiles(queue, extras) {
    extras = extras || {};
    var Q = queue || null, now = extras.now || 0;
    var rows = Array.isArray(extras.inbox) ? extras.inbox : null;
    var T = {};
    TILE_DEFS.forEach(function (d) { T[d.key] = baseTile(d); });

    // —— ملفات الخبراء
    (function (t) {
      t.dest = 'inbox'; t.land = 'expert_files_awaiting_assignment';
      if (!Q) return failTile(t);
      var late = qn(Q, 'expert_files_late'), over = qn(Q, 'expert_files_assign_overdue');
      var rev = qn(Q, 'expert_files_in_review'), aw = qn(Q, 'expert_files_awaiting_assignment'), bl = qn(Q, 'expert_files_blocked');
      var hot = late + over;
      t.count = hot + rev + aw + bl; t.hot = hot > 0;
      var p = [];
      if (hot) p.push(ar(hot) + ' متأخر');
      if (rev) p.push(ar(rev) + ' تنتظر مراجعتك');
      if (aw) p.push(ar(aw) + ' تنتظر خبيرًا');
      if (bl) p.push(U(bl, ['ملف أمواله متوقفة', 'ملفان أموالهما متوقفة', 'ملفات أموالها متوقفة', 'ملفًا أمواله متوقفة']));
      t.next = p.length ? p.join(' · ') : 'كل شيء يسير في موعده';
      t.land = late ? 'expert_files_late' : over ? 'expert_files_assign_overdue' : rev ? 'expert_files_in_review'
        : aw ? 'expert_files_awaiting_assignment' : bl ? 'expert_files_blocked' : 'expert_files_awaiting_assignment';
    })(T.files);

    // —— النزاعات والاستردادات
    (function (t) {
      t.dest = 'inbox'; t.land = 'expert_files_disputed';
      if (!Q) return failTile(t);
      var d = qn(Q, 'expert_files_disputed') + qn(Q, 'expert_files_case_disputed') + qn(Q, 'consultation_disputes');
      var leg = qn(Q, 'consultations_legacy'), ref = qn(Q, 'manual_refunds_pending'), un = qn(Q, 'expert_files_unactivated');
      t.count = d + leg + ref + un; t.hot = d > 0;
      var p = [];
      if (d) p.push(U(d, ['نزاع واحد', 'نزاعان', 'نزاعات', 'نزاعًا']));
      if (leg) p.push(U(leg, ['استشارة قديمة', 'استشارتان قديمتان', 'استشارات قديمة', 'استشارة قديمة']));
      if (un) p.push(ar(un) + ' دفع بلا ملف');
      if (ref) p.push(ar(ref) + ' استرداد يدوي');
      t.next = p.length ? p.join(' · ') : 'لا نزاعات مفتوحة';
      t.land = d ? 'expert_files_disputed' : leg ? 'consultations_legacy' : un ? 'expert_files_unactivated' : 'expert_files_disputed';
    })(T.disputes);

    // —— الدورات والمدرّبون
    (function (t) {
      t.dest = 'courses'; t.land = 'courses_pending';
      if (!Q) return failTile(t);
      var c = qn(Q, 'courses_pending'), tr = qn(Q, 'trainer_applications_pending'), lv = listLen(Q.live_needs_decision);
      t.count = c + tr + lv;
      var p = [];
      if (c) p.push(U(c, ['دورة تنتظر الاعتماد', 'دورتان تنتظران الاعتماد', 'دورات تنتظر الاعتماد', 'دورة تنتظر الاعتماد']));
      if (tr) p.push(U(tr, ['مدرّب جديد', 'مدرّبان جديدان', 'مدرّبين جدد', 'مدرّبًا جديدًا']));
      if (lv) p.push(ar(lv) + ' حيّة تحتاج قرارًا');
      t.next = p.length ? p.join(' · ') : 'لا شيء ينتظر قرارك';
      if (c) { t.dest = 'courses'; t.land = 'courses_pending'; }
      else if (tr) { t.dest = 'team'; t.land = 'trainer_applications_pending'; }
      else if (lv) { t.dest = 'courses'; t.land = 'live_needs_decision'; }
    })(T.courses);

    // —— سوق الخدمات: العدد من محمّل السوق إن وُجد وإلا لا رقم (لا صفرًا مختلقًا).
    (function (t) {
      t.dest = 'market';
      if (extras.market === null) return failTile(t);
      if (typeof extras.market === 'number') {
        t.count = extras.market;
        t.next = extras.market ? U(extras.market, ['طلب بلا عرض', 'طلبان بلا عرض', 'طلبات بلا عرض', 'طلبًا بلا عرض']) : 'الطلبات والعروض';
      } else { t.next = 'الطلبات والعروض'; }
    })(T.market);

    // —— الكتب: من طابور المراجعة في الوارد.
    (function (t) {
      t.dest = 'knowledge';
      if (!rows || inboxFailedHas(extras, 'سوق المعرفة')) return failTile(t);
      var n = rowsOfKind(rows, 'book').length;
      t.count = n;
      t.next = n ? U(n, ['كتاب ينتظر المراجعة', 'كتابان ينتظران المراجعة', 'كتب تنتظر المراجعة', 'كتابًا ينتظر المراجعة']) : 'المتجر والمراجعة';
      if (hasTrunc(extras)) markPartial(t);      // قائمة الوارد مقصوصة ⇒ العدّ من صفوفها ناقص معلَن
      // D3: عروض الكتب في طابور المراجعة الجديد (رقم من الجسر؛ تعذّر جلبه ⇒ العدد ناقص معلَن لا صفر).
      if (typeof extras.bookOffers === 'number' && extras.bookOffers > 0) {
        t.count += extras.bookOffers;
        t.next = U(extras.bookOffers, ['عرض ينتظر المراجعة', 'عرضان ينتظران المراجعة', 'عروض تنتظر المراجعة', 'عرضًا ينتظر المراجعة']) + (n ? ' · ' + t.next : '');
      } else if (extras.bookOffers === null) markPartial(t);
    })(T.books);

    // —— الناس والدعوات: أربعة مصادر؛ ناقص أحدها ⇒ المجموع جزئي ومعلَن (لا رقم يكذب).
    (function (t) {
      t.dest = 'invites';
      var v = typeof extras.pendingVisitors === 'number' ? extras.pendingVisitors : null;
      var iv = typeof extras.invitesAwaiting === 'number' ? extras.invitesAwaiting : null;
      var jn = (rows && !inboxFailedHas(extras, 'طلبات تقديم الخدمة')) ? rowsOfKind(rows, 'join').length : null;
      var ld = Q ? qn(Q, 'founding_leads_new') : null;
      var parts = [v, iv, jn, ld];
      var known = parts.filter(function (x) { return x !== null; });
      if (!known.length) return failTile(t);
      t.count = known.reduce(function (a, b) { return a + b; }, 0);
      t.partial = known.length < parts.length;
      var p = [];
      if (v) p.push(U(v, ['زائر ينتظر الفتح', 'زائران ينتظران الفتح', 'زوّار ينتظرون الفتح', 'زائرًا ينتظر الفتح']));
      if (iv) p.push(U(iv, ['دعوة تنتظر موافقتك', 'دعوتان تنتظران موافقتك', 'دعوات تنتظر موافقتك', 'دعوة تنتظر موافقتك']));
      if (jn) p.push(U(jn, ['طلب انضمام', 'طلبا انضمام', 'طلبات انضمام', 'طلب انضمام']));
      if (ld) p.push(U(ld, ['خبير مؤسس', 'خبيران مؤسسان', 'خبراء مؤسسون', 'خبيرًا مؤسسًا']));
      t.next = p.length ? p.join(' · ') : 'الأعضاء والدعوات';
      if (t.partial || hasTrunc(extras)) markPartial(t);
    })(T.people);

    // —— الفلوس: تحويلات + إيصالات + دفعات عالقة + استردادات يدوية، بالمجموع الذي حدّدته المواصفة وحده.
    (function (t) {
      t.dest = 'finance'; t.land = 'wallet_payouts_pending';
      if (!Q) return failTile(t);
      var B = v2MoneyBadge(Q).parts, po = B.payouts, mp = B.receipts, st = B.stuck, rf = B.refunds;
      t.count = po + mp + st + rf; t.hot = st > 0;
      var p = [];
      if (po) p.push(U(po, ['تحويل واحد', 'تحويلان', 'تحويلات', 'تحويلًا']));
      if (mp) p.push(U(mp, ['إيصال', 'إيصالان', 'إيصالات', 'إيصالًا']));
      if (st) p.push(U(st, ['دفعة عالقة', 'دفعتان عالقتان', 'دفعات عالقة', 'دفعة عالقة']));
      if (rf) p.push(U(rf, ['استرداد ينتظر قرارك', 'استردادان ينتظران قرارك', 'استردادات تنتظر قرارك', 'استردادًا ينتظر قرارك']));
      t.next = p.length ? p.join(' · ') : 'التحويلات والإيصالات';
      if (st) { t.dest = 'finance'; t.land = 'stuck_card_payments'; }
      else if (po) { t.dest = 'finance'; t.land = 'wallet_payouts_pending'; }
      else if (mp) { t.dest = 'escrow'; t.land = 'manual_payments_pending'; }
    })(T.money);

    // —— المحتوى
    (function (t) {
      t.dest = 'topics'; t.land = 'topics_drafts';
      if (!Q) return failTile(t);
      var d = qn(Q, 'topics_drafts'), s = qn(Q, 'testimonials_pending');
      t.count = d + s;
      var p = [];
      if (d) p.push(U(d, ['مسودة', 'مسودتان', 'مسودات', 'مسودة']));
      if (s) p.push(U(s, ['شهادة تنتظر المراجعة', 'شهادتان تنتظران المراجعة', 'شهادات تنتظر المراجعة', 'شهادة تنتظر المراجعة']));
      t.next = p.length ? p.join(' · ') : 'المقالات والموضوعات';
      t.land = d ? 'topics_drafts' : s ? 'testimonials_pending' : 'topics_drafts';
    })(T.content);

    // —— بلا رقم في D1
    T.marketing.dest = 'marketing'; T.marketing.next = 'الحملات والسوشيال';
    T.reports.dest = 'analysis'; T.reports.next = 'شغّال · واقف · فرصة';
    T.company.dest = 'investment'; T.company.next = 'الشركاء والمعدات والإعدادات';

    // —— العقل: ما وزّعه اليوم من صفوف الوارد.
    (function (t) {
      t.dest = 'brain'; t.internal = true;
      if (!rows) return failTile(t);
      var n = v2BrainLog(rows, now).length;
      t.count = n;
      t.next = n ? 'وزّع ' + U(n, ['ملفًا واحدًا', 'ملفين', 'ملفات', 'ملفًا']) + ' وحده اليوم' : 'لم يوزّع شيئًا اليوم';
      if (hasTrunc(extras)) markPartial(t);
    })(T.brain);

    return TILE_DEFS.map(function (d) { return T[d.key]; });
  }

  // ------------------------------------------------------------------ البطاقات
  var IMG_OF = {
    file_waiting: 'files', file_late: 'files', file_attention: 'files', review: 'files', verify: 'files',
    dispute: 'disputes', unactivated: 'disputes', legacy: 'disputes',
    payout: 'money', manual_payment: 'money', stuck_payment: 'money', book_offer: 'books',
    trainer: 'people', join: 'people', pending_user: 'people', founding: 'people', lead: 'people', message: 'people', open_message: 'people',
    book: 'books', program: 'courses', course: 'courses', live: 'courses', topic: 'content', creative: 'content', other: 'people'
  };
  // الترتيب (قرار المؤسس): ملفات مستعجلة/متأخرة ⇐ نزاعات ⇐ استردادات ⇐ تحويلات ⇐ إيصالات ⇐ آراء للمراجعة ⇐
  // مدرّبون وانضمام ⇐ زوّار ⇐ خبراء مؤسسون ⇐ محتوى وكتب وبرامج ⇐ رسائل. الملف العادي المنتظر بين الأولى والثانية.
  var RANK = { file_urgent: 10, file_waiting: 15, dispute: 20, refund: 30, payout: 40, stuck_payment: 45, manual_payment: 50, review: 60,
               trainer: 70, join: 70, pending_user: 80, founding: 90, book_offer: 95, content: 100, message: 110 };

  function kindOf(r) {
    if (!r) return null;
    if (r.apiKind === 'payout' || r.kind === 'payout') return 'payout';
    if (r.apiKind === 'stuck_payment') return 'stuck_payment';
    if (r.apiKind === 'book_offer') return 'book_offer';
    if (r.apiKind === 'course_q') return 'course';
    if (r.apiKind === 'live_q') return 'live';
    switch (r.apiKind) {
      case 'expert_file': {
        if (r.unact) return 'unactivated';
        if (r.efLane === 'case_disputed' || r.dsrc === 'case') return 'dispute';
        if (r.efLane === 'review') return 'review';
        if (r.needsAttention) return 'file_attention';
        var f = r.ef || {};
        if (r.efLane === 'late') return 'file_late';
        if (f.status === 'assigned' && f.assign_overdue) return 'file_late';
        return 'file_waiting';
      }
      case 'dispute': return 'dispute';
      case 'legacy': return 'legacy';
      case 'manual_payment': case 'trainer': case 'join': case 'pending_user': case 'founding':
      case 'book': case 'program': case 'topic': case 'creative': case 'verify':
        return r.apiKind;
      case 'lead': case 'message': return r.apiKind;
    }
    if (r.msgSource === 'site') return 'open_message';
    return 'other';
  }
  function rankOf(kind, r) {
    switch (kind) {
      case 'file_late': case 'file_attention': return RANK.file_urgent;
      case 'file_waiting': {
        var f = (r && r.ef) || {}, u = f.urgent && typeof f.urgent === 'object' ? f.urgent : null;
        var overdue = Number(f.hours_left) <= 0 || (f.speed === 'urgent' && u && u.state === 'waiting');
        return overdue ? RANK.file_urgent : RANK.file_waiting;
      }
      case 'dispute': return RANK.dispute;
      case 'unactivated': case 'legacy': return RANK.refund;
      case 'payout': return RANK.payout;
      case 'stuck_payment': return RANK.stuck_payment;
      case 'book_offer': return RANK.book_offer;
      case 'manual_payment': return RANK.manual_payment;
      case 'review': return RANK.review;
      case 'trainer': case 'join': return RANK.trainer;
      case 'pending_user': return RANK.pending_user;
      case 'founding': return RANK.founding;
      case 'lead': case 'message': case 'open_message': case 'other': return RANK.message;
      default: return RANK.content;      // كتب · برامج · مواضيع · إبداع · توثيق · دورات
    }
  }
  // وقت البند بالميلي ثانية (الأقدم أولًا داخل المجموعة). غير معروف ⇒ Infinity (آخر المجموعة بترتيبه الأصلي).
  function tsOf(kind, r) {
    var f = (r && r.ef) || {}, c = (r && r.cons) || {}, t = NaN;
    switch (kind) {
      case 'file_late': t = r.efLane === 'late' ? ms(f.writing_due_at) : ms(f.assigned_at); if (isNaN(t)) t = ms(f.paid_at); break;
      case 'file_waiting': t = ms(f.paid_at); break;
      case 'file_attention': { var b = Array.isArray(f.blocked) && f.blocked[0]; t = ms(b && b.at); if (isNaN(t)) t = ms(f.paid_at); break; }
      case 'dispute': {
        var m0 = f.case && Array.isArray(f.case.milestones) ? f.case.milestones.filter(function (m) { return m && m.status === 'disputed'; })[0] : null;
        t = ms((f.dispute && f.dispute.at) || c.disputed_at || (m0 && m0.disputed_at)); break;
      }
      case 'unactivated': t = ms(f.paid_at); break;
      case 'legacy': t = ms(c.delivered_at); break;
      case 'review': t = ms(f.review && f.review.submitted_at); break;
      case 'payout': t = ms(r.raw && r.raw.created_at); break;
      default: t = ms(r && r.ts);
    }
    return isNaN(t) ? Infinity : t;
  }

  // اقتراح العقل = `auto_pick` اللي المنصة بعتته (أول مؤهَّل بترتيب التوزيع التلقائي) — بس مش نفس الخبير الحالي للملف أبدًا.
  function pickCandidate(cands, f) {
    if (!Array.isArray(cands) || !cands.length) return null;
    var cur = f ? str(f.expert_email).toLowerCase() : '';
    var flagged = cands.some(function (c) { return c && typeof c.auto_pick === 'boolean'; });
    var i, c, ok = function (x) { return x && x.email && x.current !== true && (!cur || String(x.email).toLowerCase() !== cur); };
    if (flagged) {
      for (i = 0; i < cands.length; i++) { c = cands[i]; if (c && c.auto_pick === true) return ok(c) ? c : null; }
      return null;
    }
    // منصة قبل الجولة ١٤: أول مرشّح لم يعتذر وليس هو الحالي.
    for (i = 0; i < cands.length; i++) { c = cands[i]; if (ok(c) && !c.declined) return c; }
    return null;
  }
  function whyBits(c, f) {
    var b = [];
    if (f && f.kind === 'contract' && c.reviews_contracts === true) b.push('يراجع العقود');
    if (c.same_specialty === true) b.push('نفس التخصص');
    if (c.same_country === true) b.push('نفس بلد القانون');
    if (typeof c.load === 'number') {
      b.push(c.load > 0 ? 'عدد الملفات المفتوحة: ' + ar(c.load) : 'لا ملفات مفتوحة');
    }
    return b;
  }
  function expertNameOf(f) { return str(f.expert_name) || str(f.assigned_name) || str(f.expert_email) || str(f.assigned_to) || 'الخبير الحالي'; }

  function safeUrl(u) {
    u = str(u);
    return /^https?:\/\//i.test(u) ? u : '';
  }
  function act(o) { return o; }
  var OPEN = { do: 'open' };

  // نص الدفع اليدوي: الطريقة · المبلغ · ما يخصّه.
  function payBrain(r) {
    return clean([str(r.payMethod), moneyText(r.amount, r.currency), str(r.payWhat)]).join(' · ');
  }

  // هل يوجد نزاع مفتوح **على هذا الشخص كخبير**؟ true/false، أو null لو الفحص ما اكتملش لأي سبب:
  //   · الوارد ما وصلش / أي طابور من طوابير النزاعات الثلاثة تعذّر جلبه،
  //   · أو قائمة النزاعات/القضايا/الاستشارات القديمة اتقصّت («معروض ١٠٠ من ٣٠٠») ⇒ المعروض مش كل اللي موجود،
  //   · أو ما اتبعتش لنا بيان القصّ أصلًا (نعتبره مجهولًا مش «لا قصّ»).
  // ⛔ false = «فحصنا كل المصادر ولا يوجد»، لا أقل. والفحص كله على إيميلات الخبير/المسنَد إليه/المستفيد في صفوف النزاع —
  // عميل سحب فلوسًا مستردّة إيميله مش في الصفوف أصلًا (بيانات العميل مقصوصة) ⇒ الجملة ما بتقولش شيئًا عنه.
  var DISPUTE_SOURCES = ['نزاعات الملفات', 'نزاعات الاستشارات', 'قضايا فيها ملاحظة'];
  var DISPUTE_TRUNC_MARKS = ['نزاعات', 'قضايا', 'استشارات قديمة'];
  function openDisputeFor(email, rows, opts) {
    email = str(email).toLowerCase();
    if (!email || !Array.isArray(rows)) return null;
    // نزاع معروض فعلًا = حقيقة حتى لو باقي الفحص ناقص (التحذير لا يحتاج اكتمال المصادر، «لا يوجد» وحدها هي اللي تحتاجه).
    for (var j = 0; j < rows.length; j++) {
      var r = rows[j];
      if (!r || (r.apiKind !== 'dispute' && r.efLane !== 'case_disputed')) continue;
      var f = r.ef || {}, c = r.cons || {};
      var emails = [f.expert_email, f.assigned_to, c.payee_email, c.expert_email].map(function (x) { return str(x).toLowerCase(); });
      if (emails.indexOf(email) > -1) return true;
    }
    var failed = (opts && Array.isArray(opts.inboxFailed)) ? opts.inboxFailed : null;
    var trunc = (opts && Array.isArray(opts.inboxTruncated)) ? opts.inboxTruncated : null;
    if (!failed || !trunc) return null;
    var i;
    for (i = 0; i < DISPUTE_SOURCES.length; i++) if (failed.indexOf(DISPUTE_SOURCES[i]) > -1) return null;
    for (i = 0; i < trunc.length; i++) {
      var tl = String(trunc[i]);
      if (DISPUTE_TRUNC_MARKS.some(function (m) { return tl.indexOf(m) > -1; })) return null;
    }
    return false;
  }

  function v2Card(row, opts) {
    opts = opts || {};
    var now = opts.now || 0;
    var kind = kindOf(row);
    if (!kind) return null;
    var r = row, f = r.ef || {}, c = r.cons || {};
    var card = {
      id: [kind, r.apiId != null ? r.apiId : (r.pid || r.ref || ''), r.ref || ''].join('|'),
      kind: kind, group: rankOf(kind, r), tag: '', title: '', sub: '', brain: '', brainHead: 'ما يراه العقل', reason: '', warn: '',
      ageText: '', ts: tsOf(kind, r), primary: null, secondary: null, open: OPEN, link: null, facts: [],
      img: IMG_OF[kind] || 'people', row: row
    };
    var t = card.ts;
    card.ageText = isFinite(t) ? agoText(t, now) : '';
    var who = str(r.who);
    var amountLabel = str(r.amountLabel);

    switch (kind) {
      case 'file_waiting': case 'file_late': {
        var late = kind === 'file_late';
        var pre = f.status === 'awaiting_assignment';
        var cand = pickCandidate(f.candidates || r.candidates, f);
        card.tag = late ? 'ملف متأخر' : 'ملف ينتظر خبيرًا';
        card.title = str(f.title) || 'ملف';
        card.sub = clean([who && ('العميل: ' + who), str(f.law_label), amountLabel]).join(' · ');
        card.brainHead = 'اقتراح العقل';
        var cur = expertNameOf(f);
        if (late) {
          var from = r.efLane === 'late' ? f.writing_due_at : (f.assigned_at || f.paid_at);
          var h = Math.max(1, hoursBetween(from, now));
          card.brain = (r.efLane === 'late' ? 'متأخر ' + hoursWord(h) + ' عند ' + cur : 'لم يُستلم لدى ' + cur + ' منذ ' + hoursWord(h))
            + (cand ? '. أقترح نقله إلى ' + cand.name : '. لا يوجد خبير آخر متاح');
        } else if (!pre && f.status === 'assigned') {
          card.brain = 'أُرسل إلى ' + cur + ' ولم يُستلم بعد' + (cand ? '. أقترح نقله إلى ' + cand.name : '. لا يوجد خبير آخر متاح');
        } else {
          card.brain = cand ? 'أقترح ' + cand.name : 'لا يوجد خبير متاح';
        }
        if (cand) {
          card.reason = whyBits(cand, f).join(' · ');
          var verb = (pre && !late) ? 'أرسله إلى ' : 'انقله إلى ';
          card.primary = { label: verb + cand.name, act: act({ do: 'send', email: cand.email, name: cand.name }) };
          card.secondary = { label: 'افتح الملف', act: OPEN };
        } else {
          card.reason = 'اختر الخبير بنفسك من الملف';
          card.primary = { label: 'افتح الملف', act: OPEN };
        }
        if (f.speed === 'urgent') card.warn = 'طلب مستعجل';
        if (Number(f.hours_left) > 0 && pre) card.facts.push({ k: 'المتبقي للاستلام', v: hoursWord(Math.floor(Number(f.hours_left))) });
        break;
      }
      case 'file_attention': {
        card.tag = 'أموال ملف متوقفة';
        card.title = str(f.title) || 'ملف';
        card.sub = clean([who && ('العميل: ' + who), amountLabel]).join(' · ');
        card.brain = 'أموال هذا الملف لم تتحرك وحدها وتحتاج تدخّلك';
        card.reason = 'القرار هنا يخص الأموال، فيُفتح الملف للمراجعة أولًا';
        card.primary = { label: 'افتح وراجع', act: OPEN };
        break;
      }
      case 'review': {
        card.tag = 'أول رأي لخبير جديد';
        card.title = str(f.title) || 'رأي ينتظر المراجعة';
        card.sub = clean([who && ('العميل: ' + who), amountLabel]).join(' · ');
        card.brain = 'رأي ' + (str(f.expert_name) || 'الخبير') + ' في «' + (str(f.title) || 'الملف') + '» ينتظر مراجعتك';
        card.reason = 'العميل ينتظر؛ لا يصله الرأي قبل موافقتك';
        card.primary = { label: 'افتح وراجع', act: OPEN };
        break;
      }
      case 'dispute': {
        var isCase = r.efLane === 'case_disputed' || r.dsrc === 'case';
        card.tag = isCase ? 'ملاحظة على قضية' : 'نزاع';
        card.title = str(f.title) || str(c.title) || 'نزاع';
        card.sub = clean([(str(f.expert_name) || str(c.expert_name)) && ('الخبير: ' + (str(f.expert_name) || str(c.expert_name)))]).join(' · ');
        card.brain = 'اعتراض من ' + (who || 'العميل') + ' على ' + (card.title ? '«' + card.title + '»' : 'الخدمة') + (amountLabel ? ' · ' + amountLabel : '');
        card.reason = 'الأموال محجوزة لحين قرارك، والحسم من صفحة البند بعد قراءة الرأيين';
        card.primary = { label: 'افتح النزاع', act: OPEN };
        break;
      }
      case 'unactivated': {
        card.tag = 'دفع بلا ملف';
        card.title = str(f.title) || 'دفعة لم يصل ملفها';
        card.sub = who ? 'العميل: ' + who : '';
        card.brain = (amountLabel ? 'دُفع ' + amountLabel : 'دُفع مبلغ') + ' ولم يصل ملف';
        card.reason = 'الأموال وصلت ولم يصل الملف إلى قائمة التوزيع';
        card.primary = { label: 'افتح', act: OPEN };
        break;
      }
      case 'legacy': {
        card.tag = 'استشارة قديمة';
        card.title = str(c.title) || 'استشارة قديمة';
        card.sub = clean([who && ('العميل: ' + who), amountLabel]).join(' · ');
        card.brain = 'استشارة سُلّمت قبل التحويل التلقائي وأموالها تنتظر قرارك';
        card.reason = 'للخبير أم للعميل؟ القرار من صفحة البند';
        card.primary = { label: 'افتح وراجع', act: OPEN };
        break;
      }
      case 'payout': {
        // ⛔ المبلغ الحقيقي من صف المنصة (`raw.amount`) مش `r.amount`: محمّل الفلوس القديم بيقرّب للجنيه، والمنصة بتحوّل
        // المبلغ بالكسور — المؤسس لازم يأكّد نفس الرقم اللي بيتحوّل (٦٠٠٫٥ مش ٦٠١).
        var amount = Number(r.raw && r.raw.amount != null ? r.raw.amount : r.amount), cr = r.currency || 'EGP';
        card.tag = 'تحويل أرباح';
        card.title = str(r.who) || 'صاحب الطلب';
        card.sub = clean([moneyText(amount, cr), str(r.dest)]).join(' · ');
        var method = str(r.raw && r.raw.method) || str(r.dest);
        card.brain = 'طلب تحويل ' + moneyText(amount, cr) + ' إلى ' + (str(r.who) || 'صاحب الطلب') + (method ? ' عبر ' + method : '');
        var dis = openDisputeFor(r.email, opts.inboxRows, opts);
        if (dis === false) card.reason = 'روجعت النزاعات المفتوحة: لا نزاع مفتوحًا على صاحب الطلب كخبير';
        else if (dis === true) { card.warn = 'يوجد نزاع مفتوح على صاحب هذا الطلب — راجعه قبل التحويل'; }
        if (r.fx_alert) card.warn = (card.warn ? card.warn + ' · ' : '') + 'العملة ليست الجنيه — حدّد سعر الصرف قبل التحويل';
        var mo = { amount: amount, currency: cr, curName: curName(cr), name: str(r.who) || str(r.email), what: 'تحويل أرباح',
                   method: method, dest: str(r.dest) };
        card.primary = { label: 'سجّل التحويل', act: act({ do: 'payout_settle', id: r.pid }), money: mo };
        card.secondary = { label: 'ارفض', act: act({ do: 'payout_reject', id: r.pid }), money: mo };
        card.open = act({ do: 'goto', mod: 'finance', land: 'wallet_payouts_pending' });
        card.facts = [{ k: 'المبلغ', v: moneyText(amount, cr) }, { k: 'الوجهة', v: str(r.dest) || '—' }];
        break;
      }
      case 'manual_payment': {
        var mo2 = { amount: r.amount, currency: r.currency || 'EGP', curName: curName(r.currency), name: who || str(r.email),
                    what: str(r.payWhat) || 'دفعة يدوية', method: str(r.payMethod), ref: str(r.payRef) };
        card.tag = 'إيصال تحويل';
        card.title = who || 'دافع';
        card.sub = clean([str(r.payWhat), moneyText(r.amount, r.currency)]).join(' · ');
        card.brain = payBrain(r) || str(r.note);
        card.reason = str(r.payRef) ? 'رقم المرجع: ' + str(r.payRef) + ' — طابقه مع الإيصال قبل التأكيد' : 'طابق الإيصال مع كشف الحساب قبل التأكيد';
        var pu = safeUrl(r.proofUrl);
        card.link = pu ? { label: 'افتح الإيصال', url: pu } : null;
        card.primary = { label: 'أكّد الدفع', act: act({ do: 'pay_confirm' }), money: mo2 };
        card.secondary = { label: 'ارفض', act: act({ do: 'pay_reject' }), money: mo2 };
        card.open = act({ do: 'goto', mod: 'escrow', land: 'manual_payments_pending' });
        card.facts = [{ k: 'المبلغ', v: moneyText(r.amount, r.currency) }, { k: 'الطريقة', v: str(r.payMethod) || '—' }];
        break;
      }
      case 'stuck_payment': {
        var sk = r.stuck || {};
        card.tag = 'دفعة عالقة';
        card.title = sk.name || 'صاحب الدفع';
        card.sub = clean([sk.kindText, sk.amountText, sk.provider]).join(' · ');
        card.brain = 'دفع بالبطاقة لم يكتمل' + (sk.ageText ? ' ' + sk.ageText : '') + (sk.title && sk.title !== sk.kindText ? ' عن «' + sk.title + '»' : '');
        card.reason = 'لا إجراء مالي من هنا: افتح صفحة صاحب الدفع وتابع معه';
        if (!sk.refundable) card.warn = sk.noRefundText;
        card.open = act({ do: 'section', section: 'money', tab: 'receipts' });
        card.primary = sk.email ? { label: 'افتح الشخص', act: act({ do: 'person', email: sk.email }) } : { label: 'افتح الدفعات العالقة', act: card.open };
        card.facts = [{ k: 'المبلغ', v: sk.amountText }, { k: 'الطريقة', v: sk.provider }];
        break;
      }
      case 'book_offer': {
        var of = r.offerRow || {};
        card.tag = 'عرض كتاب للمراجعة';
        card.title = of.title || 'عرض كتاب';
        card.sub = clean([of.typeText, of.ownerName, of.suggestedText && ('السعر المقترح: ' + of.suggestedText)]).join(' · ');
        card.brain = of.brain || 'عرض جديد ينتظر اعتمادك';
        card.reason = 'تُراجع الأسعار قبل الاعتماد، والرفض يحتاج سببًا يصل إلى صاحب العرض';
        card.open = act({ do: 'section', section: 'books', tab: 'offers' });
        card.primary = { label: 'اعتمد بالأسعار دي', act: act({ do: 'offer_approve', id: of.id }) };
        card.secondary = { label: 'ارفض', act: act({ do: 'offer_reject', id: of.id }) };
        card.facts = [{ k: 'النوع', v: of.typeText }, { k: 'السعر المقترح', v: of.suggestedText || 'لم يُقترح' }];
        break;
      }
      case 'trainer': {
        var facts = clean([str(r.trSpec), str(r.trYears) && ('الخبرة: ' + str(r.trYears)),
                           r.trAttach ? U(r.trAttach, ['مرفق واحد', 'مرفقان', 'مرفقات', 'مرفقًا']) : '']);
        card.tag = 'مدرّب جديد';
        card.title = who || 'مدرّب';
        card.sub = shorten(str(r.trHeadline) || str(r.note).replace(/\s*—\s*اعتمد.*$/, ''), 140);
        card.brain = clean([who || 'مدرّب', card.sub].concat(facts)).join(' · ');
        card.reason = 'اطّلع على الطلب كاملًا إن أردت قبل القبول';
        card.primary = { label: 'اقبل الطلب', act: act({ do: 'decide', action: 'approve' }) };
        card.secondary = { label: 'افتح الطلب', act: OPEN };
        break;
      }
      case 'join': {
        card.tag = 'طلب انضمام';
        card.title = who || 'مقدّم الطلب';
        card.sub = clean([str(r.serviceLabel) || str(r.from), r.licensed ? 'مع ترخيص' : 'بلا ترخيص',
                          (Array.isArray(r.attachments) && r.attachments.length) ? U(r.attachments.length, ['مرفق واحد', 'مرفقان', 'مرفقات', 'مرفقًا']) : '']).join(' · ');
        card.brain = 'طلب تقديم الخدمة' + (str(r.serviceLabel) ? ' «' + str(r.serviceLabel) + '»' : '') + ' — القبول ينشر الاسم على المنصة';
        card.reason = r.licenceMissing ? (str(r.licenceNote) || 'الترخيص بلا رقم قيد — لا يُقبل الطلب قبل استكماله') : (shorten(r.note, 140) || 'اقرأ إجاباته من الطلب إن أردت');
        if (r.licenceMissing) {
          card.warn = 'رقم القيد ناقص';
          card.primary = { label: 'افتح وراجع', act: OPEN };
        } else {
          card.primary = { label: 'اقبل', act: act({ do: 'decide', action: 'approve' }) };
          card.secondary = { label: 'افتح الطلب', act: OPEN };
        }
        break;
      }
      case 'pending_user': {
        var flags = Array.isArray(r.flagLabels) ? r.flagLabels : [];
        card.tag = 'زائر ينتظر الفتح';
        card.title = who || 'زائر';
        card.sub = clean([str(r.puRole), str(r.puCountry)]).join(' · ');
        card.brain = clean([who || 'زائر', str(r.puCountry), card.ageText]).join(' · ');
        if (flags.length) {
          card.warn = 'مشبوه: ' + flags.join(' · ');
          card.reason = 'يُفتح الطلب للمراجعة قبل فتح المنصة';
          card.primary = { label: 'افتح وراجع', act: OPEN };
        } else {
          card.reason = 'طلب فتح المنصة بعد التسجيل';
          card.primary = { label: 'افتح المنصة للزائر', act: act({ do: 'decide', action: 'approve' }) };
          card.secondary = { label: 'افتح', act: OPEN };
        }
        break;
      }
      case 'founding': {
        var labels = { contacted: 'تم التواصل', invited: 'أُرسلت الدعوة', converted: 'تم التحويل إلى مدرّب' };
        card.tag = 'خبير مؤسس';
        card.title = who || 'خبير';
        card.sub = shorten(r.note, 150);
        card.brain = clean([who, str(r.fSpec), str(r.fCountry)]).join(' · ') || 'طلب انضمام كخبير مؤسس';
        card.reason = 'تواصل عبر واتساب ثم علّم الخطوة';
        card.primary = { label: labels[r.nextStatus] || 'تم التواصل', act: act({ do: 'decide', action: 'approve' }) };
        card.secondary = { label: 'افتح', act: OPEN };
        break;
      }
      case 'book': case 'program': case 'topic': case 'creative': case 'verify': {
        var T = { book: ['كتاب بانتظار المراجعة', 'books'], program: ['طلب برنامج', 'courses'], topic: ['موضوع بانتظار المراجعة', 'content'],
                  creative: ['عمل إبداعي بانتظار المراجعة', 'content'], verify: ['طلب توثيق بلا خبير', 'files'] }[kind];
        card.tag = T[0]; card.img = T[1];
        card.title = who || T[0];
        card.sub = shorten(r.note, 150);
        card.brain = shorten(r.note, 170) || T[0];
        card.reason = kind === 'verify' ? 'اختر خبيرًا معتمدًا من صفحة البند' : 'يحتاج قراءة قبل القرار';
        card.primary = { label: 'افتح وراجع', act: OPEN };
        break;
      }
      case 'course': {
        card.tag = 'دورة تنتظر الاعتماد';
        card.title = str(r.title) || 'دورات بانتظار الاعتماد';
        card.sub = r.summary ? 'عدد الدورات: ' + ar(r.summary) : '';
        card.brain = r.summary ? U(r.summary, ['دورة تنتظر قرارك', 'دورتان تنتظران قرارك', 'دورات تنتظر قرارك', 'دورة تنتظر قرارك']) : 'دورة تنتظر قرارك';
        card.reason = 'تُراجع الدورة كاملة قبل النشر';
        card.open = act({ do: 'goto', mod: 'courses', land: 'courses_pending' });
        card.primary = { label: 'افتح وراجع', act: card.open };
        break;
      }
      case 'live': {
        card.tag = 'دورة حيّة تحتاج قرارًا';
        card.title = str(r.title) || 'دورة حيّة';
        card.sub = (r.reserved != null && r.quorum != null) ? ('حجز ' + ar(r.reserved) + ' من ' + ar(r.quorum)) : '';
        card.brain = 'الحجز لم يكتمل — إما تثبيت الموعد وإما تأجيله';
        card.reason = 'القرار من جدول الدورات الحيّة';
        card.open = act({ do: 'goto', mod: 'courses', land: 'live_needs_decision' });
        card.primary = { label: 'افتح وراجع', act: card.open };
        break;
      }
      case 'lead': case 'message': {
        card.tag = kind === 'lead' ? 'عميل محتمل' : 'رسالة';
        card.title = who || card.tag;
        card.sub = shorten(r.note, 160);
        card.brain = shorten(r.note, 170) || card.tag;
        card.reason = 'بعد التعامل مع الطلب اضغط «تم»';
        if (r.resolve) {
          card.primary = { label: 'تم', act: act({ do: 'resolve' }) };
          card.secondary = { label: 'افتح', act: OPEN };
        } else {
          card.primary = { label: 'افتح', act: OPEN };
        }
        break;
      }
      default: {
        card.tag = str(r.from) || 'بند';
        card.title = who || str(r.out) || 'بند ينتظر قرارك';
        card.sub = shorten(r.note, 160);
        card.brain = shorten(r.note, 170) || str(r.out);
        card.reason = 'يُفتح للمراجعة';
        card.primary = { label: 'افتح وراجع', act: OPEN };
      }
    }
    // D2: صاحب الاسم (لو عنوان البطاقة اسم شخص وعندنا بريده) ⇒ الاسم يفتح صفحته.
    if (PERSON_TITLE[kind]) { var pe = personEmailOfRow(r); if (pe) card.person = { email: pe, name: card.title }; }
    return card;
  }
  var PERSON_TITLE = { payout: 1, manual_payment: 1, stuck_payment: 1, trainer: 1, join: 1, pending_user: 1, founding: 1 };
  function v2Decisions(rows, payouts, queue, opts) {
    opts = opts || {};
    var now = opts.now || 0;
    var cardOpts = { now: now, inboxRows: Array.isArray(rows) ? rows : null, inboxFailed: opts.inboxFailed,
                     inboxTruncated: opts.inboxTruncated };   // الوارد ما وصلش / قصّ مش معلوم / مقصوص ⇒ null ⇒ جملة المراجعة تتشال
    var src = [];
    (Array.isArray(rows) ? rows : []).forEach(function (r) { if (r && !r.fyi) src.push(r); });
    (Array.isArray(payouts) ? payouts : []).forEach(function (p) {
      if (p && (p.status == null || p.status === 'pending') && p.pid) src.push(Object.assign({}, p, { apiKind: 'payout' }));
    });
    // D3: دفعات عالقة (صفوف `stuckRow`) وعروض كتب بانتظار المراجعة (صفوف `v2OffersQueue`) — كلٌّ منهما بطاقة قرار عادية.
    (Array.isArray(opts.stuck) ? opts.stuck : []).forEach(function (sk) {
      if (!sk || !sk.id) return;
      src.push({ apiKind: 'stuck_payment', apiId: sk.id, ref: sk.id, stuck: sk, email: sk.email, who: sk.name, ts: sk.ageHours != null ? now - sk.ageHours * HOUR : undefined });
    });
    (Array.isArray(opts.offers) ? opts.offers : []).forEach(function (of) {
      if (!of || !of.id) return;
      src.push({ apiKind: 'book_offer', apiId: of.id, ref: of.id, offerRow: of, who: of.ownerName, ts: isFinite(of.at) ? of.at : undefined });
    });
    var Q = queue || null;
    if (Q) {
      var titles = Q.courses_pending && Array.isArray(Q.courses_pending.titles) ? Q.courses_pending.titles.filter(Boolean) : [];
      var cp = qn(Q, 'courses_pending');
      if (titles.length) titles.forEach(function (tt, i) { src.push({ apiKind: 'course_q', apiId: 'c' + i, title: String(tt), ref: 'CRS-' + i }); });
      else if (cp > 0) src.push({ apiKind: 'course_q', apiId: 'c', summary: cp, title: '', ref: 'CRS' });
      (Array.isArray(Q.live_needs_decision) ? Q.live_needs_decision : []).forEach(function (l, i) {
        if (l && typeof l === 'object') src.push({ apiKind: 'live_q', apiId: 'l' + i, title: l.title || l.slug || '', reserved: l.reserved_count, quorum: l.quorum, ref: 'LIV-' + i });
      });
    }
    var cards = [];
    src.forEach(function (r, i) {
      var c = v2Card(r, cardOpts);
      if (c) { c._i = i; cards.push(c); }
    });
    cards.sort(function (a, b) {
      if (a.group !== b.group) return a.group - b.group;
      if (a.ts !== b.ts) return a.ts < b.ts ? -1 : 1;   // Infinity مقارنة صحيحة: المجهول آخرًا
      return a._i - b._i;
    });
    cards.forEach(function (c) { delete c._i; });
    return cards;
  }

  function v2Next(decisions) {
    return Array.isArray(decisions) && decisions.length ? decisions[0] : null;
  }
  // سطر «الحاجة الجاية»: الوسم ثم العنوان؛ وتحته كلام العقل.
  function v2NextLine(card) {
    if (!card) return '';
    return clean([card.tag, card.title]).join(' — ');
  }

  var HB_LABEL = { tick_last: 'الفحص الدوري', remind_last: 'التذكيرات', sla_last: 'مهل الملفات', backup_last: 'النسخ الاحتياطي',
                   invite_reminders_last: 'تذكير الدعوات', coach_stalled_last: 'متابعة المتعثرين' };

  // —— تنبيهات الصحة بالفصحى: ⛔ نصوص المنصة (`queue.alerts`) لا تُعرض كما وصلت أبدًا — فيها عامية وإيموجي وأرقام لاتينية
  // وأحيانًا اسم الشاشة. كل تنبيه معروف يُعاد بناؤه من عدده، وغير المعروف يُلخَّص بجملة ثابتة (لا يُطبع نصّه).
  var UNKNOWN_ALERT = 'تنبيه من المنصة يحتاج مراجعتك';
  var ALERT_RULES = [
    [/^(\d+)\s+ملف مستعجل مستني خبير يبدأ/, ['ملف مستعجل واحد ينتظر خبيرًا يبدأ', 'ملفان مستعجلان ينتظران خبيرًا يبدأ', 'ملفات مستعجلة تنتظر خبيرًا يبدأ', 'ملفًا مستعجلًا ينتظر خبيرًا يبدأ']],
    [/^(\d+)\s+رأي مستني مراجعتك/, ['رأي واحد ينتظر مراجعتك', 'رأيان ينتظران مراجعتك', 'آراء تنتظر مراجعتك', 'رأيًا ينتظر مراجعتك']],
    [/^(\d+)\s+ملف مالوش خبير متاح/, ['ملف واحد بلا خبير متاح — اختر الخبير بنفسك', 'ملفان بلا خبير متاح — اختر الخبير بنفسك', 'ملفات بلا خبير متاح — اختر الخبير بنفسك', 'ملفًا بلا خبير متاح — اختر الخبير بنفسك']],
    [/^(\d+)\s+ملف مستني توزيع/, ['ملف واحد ينتظر التوزيع', 'ملفان ينتظران التوزيع', 'ملفات تنتظر التوزيع', 'ملفًا ينتظر التوزيع']],
    [/^(\d+)\s+ملف اتبعت لخبير وما اتستلمش/, ['ملف واحد أُرسل إلى خبير ولم يُستلم منذ ١٢ ساعة', 'ملفان أُرسلا إلى خبراء ولم يُستلما منذ ١٢ ساعة', 'ملفات أُرسلت إلى خبراء ولم تُستلم منذ ١٢ ساعة', 'ملفًا أُرسل إلى خبراء ولم يُستلم منذ ١٢ ساعة']],
    [/^(\d+)\s+رأي متأخر/, ['رأي متأخر واحد', 'رأيان متأخران', 'آراء متأخرة', 'رأيًا متأخرًا']],
    [/^(\d+)\s+ملف فيه ملاحظة مستنية قرارك/, ['ملف واحد عليه ملاحظة تنتظر قرارك', 'ملفان عليهما ملاحظة تنتظران قرارك', 'ملفات عليها ملاحظة تنتظر قرارك', 'ملفًا عليه ملاحظة تنتظر قرارك']],
    [/^(\d+)\s+دفعة قضية عليها ملاحظة/, ['دفعة قضية واحدة عليها ملاحظة تنتظر قرارك', 'دفعتا قضية عليهما ملاحظة تنتظران قرارك', 'دفعات قضايا عليها ملاحظة تنتظر قرارك', 'دفعة قضية عليها ملاحظة تنتظر قرارك']],
    [/^(\d+)\s+ملف فلوسه ما اتحرّكتش لوحدها/, ['ملف واحد لم تتحرك أمواله وحدها ويحتاج تدخّلك', 'ملفان لم تتحرك أموالهما وحدها ويحتاجان تدخّلك', 'ملفات لم تتحرك أموالها وحدها وتحتاج تدخّلك', 'ملفًا لم تتحرك أمواله وحدها ويحتاج تدخّلك']],
    [/^(\d+)\s+ملف اتدفع وما وصلش لقايمة التوزيع/, ['ملف واحد دُفع ولم يصل إلى قائمة التوزيع — راجعه من النزاعات والاستردادات', 'ملفان دُفعا ولم يصلا إلى قائمة التوزيع — راجعهما من النزاعات والاستردادات', 'ملفات دُفعت ولم تصل إلى قائمة التوزيع — راجعها من النزاعات والاستردادات', 'ملفًا دُفع ولم يصل إلى قائمة التوزيع — راجعها من النزاعات والاستردادات']],
    [/^(\d+)\s+ملف مدفوع والميزة مقفولة/, ['ملف واحد مدفوع والخدمة مغلقة — أعد الأموال أو احسمه أو افتح الخدمة', 'ملفان مدفوعان والخدمة مغلقة — أعد الأموال أو احسمهما أو افتح الخدمة', 'ملفات مدفوعة والخدمة مغلقة — أعد الأموال أو احسمها أو افتح الخدمة', 'ملفًا مدفوعًا والخدمة مغلقة — أعد الأموال أو احسمها أو افتح الخدمة']],
    [/^(\d+)\s+نزاع على استشارة/, ['نزاع واحد على استشارة ينتظر قرارك', 'نزاعان على استشارتين ينتظران قرارك', 'نزاعات على استشارات تنتظر قرارك', 'نزاعًا على استشارات ينتظر قرارك']],
    [/^(\d+)\s+استشارة قديمة/, ['استشارة قديمة واحدة سُلّمت وتنتظر قرارك: للخبير أم للعميل', 'استشارتان قديمتان سُلّمتا وتنتظران قرارك: للخبير أم للعميل', 'استشارات قديمة سُلّمت وتنتظر قرارك: للخبير أم للعميل', 'استشارة قديمة سُلّمت وتنتظر قرارك: للخبير أم للعميل']],
    [/^(\d+)\s+حجز اتلغى وفلوسه لسه عندنا/, ['حجز واحد أُلغي وأمواله لدينا — أعدها يدويًا', 'حجزان أُلغيا وأموالهما لدينا — أعدهما يدويًا', 'حجوزات أُلغيت وأموالها لدينا — أعدها يدويًا', 'حجزًا أُلغي وأمواله لدينا — أعدها يدويًا']]
  ];
  function latinDigits(s) { return String(s).replace(/[٠-٩]/g, function (d) { return String(d.charCodeAt(0) - 0x660); }); }
  function hrs(x) { return x === Math.floor(x) ? hoursWord(x) : fmt(x) + ' ساعة'; }
  function plainAlert(raw) {
    var s = latinDigits(raw).replace(/[\u{1F000}-\u{1FAFF}←-➿⬀-⯿⌀-⏿️‍‏‎]/gu, ' ').replace(/\s+/g, ' ').trim();
    var i, m;
    for (i = 0; i < ALERT_RULES.length; i++) {
      m = ALERT_RULES[i][0].exec(s);
      if (m) return U(+m[1], ALERT_RULES[i][1]);
    }
    if ((m = /^(.+?): لم تعمل ولا مرّة حتى الآن/.exec(s))) return m[1] + ': لم تعمل حتى الآن — شغّلها اليوم';
    if ((m = /^(.+?): متوقّفة منذ ([\d.]+) ساعة، والحدّ المسموح ([\d.]+) ساعة/.exec(s))) {
      return m[1] + ': متوقفة منذ ' + hrs(+m[2]) + ' والحد المسموح ' + hrs(+m[3]) + ' — أعد تشغيلها الآن';
    }
    if ((m = /^طلب بلا أول رد منذ (\d+) ساعة: (.+)$/.exec(s))) return 'طلب بلا رد أول منذ ' + hoursWord(+m[1]) + ': ' + m[2];
    if (/تعذّر الوصول إلى سجلّ الالتحاق/.test(s)) return 'تعذّر الوصول إلى سجل الالتحاق بالدورات — الرقم المعروض غير موثوق، تحقق منه بنفسك قبل أي قرار';
    if (/تفصيل الالتحاق حسب كل دورة غير مكتمل/.test(s)) return 'تفصيل الالتحاق حسب كل دورة غير مكتمل اليوم — الإجمالي وحده هو الرقم الموثوق';
    return UNKNOWN_ALERT;
  }
  function v2Health(queue, now) {
    if (!queue) return { ok: false, failed: true, alerts: [], heartbeats: [] };
    var raw = (Array.isArray(queue.alerts) ? queue.alerts : []).filter(function (a) { return typeof a === 'string' && a.trim(); });
    var alerts = [];
    raw.forEach(function (a) { var t = plainAlert(a); if (alerts.indexOf(t) < 0) alerts.push(t); });
    var hb = queue.heartbeats && typeof queue.heartbeats === 'object' ? queue.heartbeats : {};
    var beats = Object.keys(HB_LABEL).filter(function (k) { return Object.prototype.hasOwnProperty.call(hb, k); }).map(function (k) {
      return { key: k, label: HB_LABEL[k], at: hb[k] || null, ago: hb[k] ? agoText(ms(hb[k]), now || 0) : 'لم تعمل بعد' };
    });
    return { ok: alerts.length === 0, failed: false, alerts: alerts, heartbeats: beats };
  }


  // ------------------------------------------------------------------ التذاكر (D2) — لوحة «ملفات الخبراء» و«النزاعات»
  // ⛔ نقي: نفس صفوف الوارد (`window.INBOX` بما فيها صفوف «للعلم») + أعداد الطابور. لا مصدر جديد ولا حساب ثانٍ للأعداد.
  // كل ملف في عمود واحد بالضبط، وأي صف لا نعرف نوعه يذهب إلى «ينتظر مراجعتك» بجملة عامة — لا يسقط بصمت.
  var COLS = ['late', 'review', 'with', 'done'];
  var COL_LABEL = { late: 'متأخر', review: 'ينتظر مراجعتك', with: 'عند الخبراء', done: 'اعتُمد اليوم' };
  var WITH_SHOWN = 3;
  var EMAIL_RE = /^[^@\s]{1,120}@[^@\s.]+(?:\.[^@\s.]+)+$/;

  // مدة قصيرة: «٣٥ د» · «٥ س» · «٣ أيام». `d` بالميلي ثانية (≥ ٠).
  function durShort(d) {
    d = Math.max(0, d || 0);
    var m = Math.floor(d / MIN);
    if (m < 60) return ar(Math.max(m, 1)) + ' د';
    var h = Math.floor(m / 60);
    if (h < 48) return ar(h) + ' س';
    return U(Math.floor(h / 24), ['يوم', 'يومان', 'أيام', 'يومًا']);
  }
  // العدّاد: {mode:'left'|'over'|'since', at} ⇒ نصه عند `now`. «باقٍ» يتحوّل «متأخر» وحده لو الموعد عدّى.
  function v2TimerText(t, now) {
    if (!t || t.at == null || isNaN(ms(t.at))) return '';
    var at = ms(t.at), d = (now || 0) - at;
    if (t.mode === 'since') return d < MIN ? 'الآن' : 'منذ ' + durShort(d);
    if (t.mode === 'over' && d < 0) return 'متأخر';                       // موعد في المستقبل (فرق ساعة الجهاز): لا نكتب الباقي كأنه تأخير
    if (t.mode === 'over' || d >= 0) return 'متأخر ' + durShort(Math.abs(d));
    return 'باقٍ ' + durShort(-d);
  }
  function v2TimerTone(t, now) {
    if (!t || t.at == null || isNaN(ms(t.at))) return 'none';
    var d = (now || 0) - ms(t.at);
    if (t.mode === 'over' || (t.mode === 'left' && d >= 0)) return 'late';
    if (t.mode === 'left') return -d <= 2 * HOUR ? 'warn' : 'ok';
    return 'since';
  }
  function timerOf(mode, at) { return { mode: mode, at: isNaN(ms(at)) ? null : ms(at) }; }

  function personEmailOfRow(r) {
    var c = [r && r.personEmail, r && r.email, r && r.raw && r.raw.user_email];
    for (var i = 0; i < c.length; i++) {
      var e = typeof c[i] === 'string' ? c[i].trim().toLowerCase() : '';
      if (e && EMAIL_RE.test(e)) return e;
    }
    return '';
  }
  function expertOfFile(f) {
    var email = (str(f.expert_email) || str(f.assigned_to)).toLowerCase();
    var name = str(f.expert_name) || str(f.assigned_name);
    return { email: EMAIL_RE.test(email) ? email : '', name: name };
  }

  // يحدّد عمود الملف ووسمه وعدّاده. `kind` من `kindOf` نفسها (لا تصنيف ثانٍ).
  function placeFile(r, kind, now) {
    var f = r.ef || {}, st = str(f.status);
    var claim = ms(f.claim_deadline_at), due = ms(f.writing_due_at);
    switch (kind) {
      case 'review': {
        var rv = f.review || {}, ap = ms(rv.approved_at);
        if (!isNaN(ap) && !r.needsAttention && sameLocalDay(ap, now))
          return { col: 'done', strip: { label: 'اعتُمد اليوم', tone: 'done' }, timer: timerOf('since', ap), brain: 'اعتُمد الرأي ويصل إلى صاحب الطلب', reason: '' };
        if (!isNaN(ap))
          return { col: 'review', strip: { label: 'توصيل الرأي متوقف', tone: 'wait' }, timer: timerOf('since', ap), brain: 'اعتُمد الرأي لكن توصيله إلى صاحب الطلب توقف', reason: 'افتح الملف لمعرفة السبب' };
        return { col: 'review', strip: { label: Number(rv.returns) > 0 ? 'رأي معدّل ينتظر مراجعتك' : 'رأي ينتظر مراجعتك', tone: 'wait' },
                 timer: timerOf('since', rv.submitted_at) };
      }
      case 'file_attention': {
        var b = Array.isArray(f.blocked) && f.blocked[0];
        return { col: 'review', strip: { label: 'أموال متوقفة', tone: 'wait' }, timer: timerOf('since', (b && b.at) || f.paid_at) };
      }
      case 'file_late': {
        if (r.efLane === 'late') return { col: 'late', strip: { label: 'رأي متأخر', tone: 'late' }, timer: timerOf('over', due) };
        return { col: 'late', strip: { label: 'لم يُستلم', tone: 'late' }, timer: timerOf('since', f.assigned_at || f.paid_at) };
      }
      case 'file_waiting': {
        if (st === 'claimed' || st === 'writing' || st === 'needs_info')
          return { col: 'with', strip: { label: 'عند الخبير', tone: 'ok' }, timer: timerOf('left', due) };
        if (st === 'delivered' || st === 'closed') {
          var dt = ms(f.delivered_at || f.closed_at);
          if (!isNaN(dt) && sameLocalDay(dt, now)) return { col: 'done', strip: { label: 'سُلّم اليوم', tone: 'done' }, timer: timerOf('since', dt) };
          return { col: 'review', strip: { label: FILE_STATUS[st] || 'ملف', tone: 'wait' }, timer: timerOf('since', dt), brain: 'لا قرار مطلوب', reason: '', noAction: true };
        }
        if (!isNaN(claim) && claim <= now)
          return { col: 'late', strip: { label: 'فات ميعاد الاستلام', tone: 'late' }, timer: timerOf('over', claim) };
        if (st === 'assigned')
          return { col: 'with', strip: { label: 'عند الخبير', tone: 'ok' }, timer: timerOf('left', claim) };
        return { col: 'review', strip: { label: f.speed === 'urgent' ? 'مستعجل · ينتظر خبيرًا' : 'ينتظر خبيرًا', tone: 'wait' }, timer: timerOf('left', claim) };
      }
    }
    return null;
  }

  function v2Tickets(rows, opts) {
    opts = opts || {};
    var now = opts.now || 0, Q = opts.queue || null;
    var cols = { late: [], review: [], with: [], done: [] };
    (Array.isArray(rows) ? rows : []).forEach(function (r) {
      if (!r) return;
      var card = v2Card(r, { now: now, inboxRows: null });
      var kind = card ? card.kind : kindOf(r);
      var pl = (kind === 'file_waiting' || kind === 'file_late' || kind === 'file_attention' || kind === 'review') ? placeFile(r, kind, now) : null;
      var f = r.ef || {}, ex = expertOfFile(f), client = str(r.who);
      var t;
      if (pl) {
        t = { col: pl.col, strip: pl.strip, timer: pl.timer, brain: pl.brain, reason: pl.reason };
        if (t.brain == null) { t.brain = card ? card.brain : ''; t.reason = card ? card.reason : ''; }
        // «عند الخبراء»: لا نقترح نقلًا قبل الموعد — الزرّ يفتح الملف فقط.
        if (pl.col === 'with') {
          var who = ex.name || 'الخبير';
          t.brain = str(f.status) === 'assigned' ? 'ما زال بانتظار الاستلام لدى ' + who : str(f.status) === 'needs_info' ? 'بانتظار إجابة صاحب الطلب' : 'قيد العمل لدى ' + who;
          t.reason = 'ضمن الموعد';
        }
        t.primary = !pl.noAction && (pl.col === 'late' || pl.col === 'review') && card && card.primary ? card.primary : { label: 'افتح الملف', act: { do: 'open' } };
        if (pl.col === 'done') t.primary = { label: 'افتح الملف', act: { do: 'open' } };
      } else {
        // نوع غير معروف: لا يسقط — ينتظر مراجعتك بجملة عامة وزرّ فتح.
        t = { col: 'review', strip: { label: 'بند ينتظر قرارك', tone: 'wait' }, timer: timerOf('since', card && isFinite(card.ts) ? card.ts : NaN),
              brain: 'يحتاج إلى قرارك', reason: 'افتح البند لمعرفة التفاصيل', primary: { label: 'افتح البند', act: { do: 'open' } } };
      }
      t.id = (card && card.id) || ['t', r.apiKind || '', r.apiId != null ? r.apiId : '', r.ref || ''].join('|');
      t.kind = kind || 'other';
      t.row = r; t.card = card;
      t.title = str(f.title) || (card && card.title) || str(r.out) || 'ملف';
      t.client = client; t.expert = ex;
      t.person = ex.email ? { email: ex.email, name: ex.name || ex.email } : null;
      // الترتيب داخل العمود: الأقرب لموعده (أو الأقدم) أولًا.
      t.sortAt = t.timer && t.timer.at != null ? t.timer.at : Infinity;
      t.text = v2TimerText(t.timer, now);
      t.tone = v2TimerTone(t.timer, now);
      cols[t.col].push(t);
    });
    COLS.forEach(function (c) {
      cols[c].sort(function (a, b) {
        if (c === 'done') return b.sortAt - a.sortAt;                          // خلص اليوم: الأحدث أولًا
        return a.sortAt - b.sortAt;                                            // غيره: الأقرب موعدًا/الأقدم أولًا
      });
    });
    var shown = cols.with.slice(0, WITH_SHOWN);
    var counts = { late: cols.late.length, review: cols.review.length, with: cols.with.length, done: cols.done.length };
    var notes = { late: '', review: '', with: '', done: '' };
    if (Q) {
      var qLate = qn(Q, 'expert_files_late') + qn(Q, 'expert_files_assign_overdue'), qRev = qn(Q, 'expert_files_in_review');
      // عدّاد الطابور بالنوع (مش بالعمود): الرأي المعتمد النهارده لسه `in_review` عند المنصة وهو في «خلص اليوم» عندنا.
      var byKind = function (k) { return COLS.reduce(function (n, c) { return n + cols[c].filter(function (x) { return x.kind === k; }).length; }, 0); };
      var rLate = byKind('file_late'), rRev = byKind('review');
      if (rLate < qLate) notes.late = 'معروض ' + ar(rLate) + ' من ' + ar(qLate);
      if (rRev < qRev) notes.review = 'معروض ' + ar(rRev) + ' من ' + ar(qRev);
    }
    // العمود يعدّ ما في الوارد فقط (المُرسَل ولم يُستلم)، فلا يُقرأ رقمه كإجمالي ما عند الخبراء.
    notes.with = 'المعروض هنا ما أُرسل ولم يُستلم بعد فقط';
    var autoOn = opts.autoAssign === true ? true : opts.autoAssign === false ? false : (Q && typeof Q.expert_files_auto_assign === 'boolean' ? Q.expert_files_auto_assign : null);
    var today = Number(opts.brainToday) || 0;
    var header = autoOn === true ? 'التوزيع التلقائي يعمل · ' + (today ? 'وزّع ' + U(today, ['ملفًا واحدًا', 'ملفين', 'ملفات', 'ملفًا']) + ' اليوم' : 'لم يوزّع شيئًا اليوم')
      : autoOn === false ? 'التوزيع التلقائي متوقف — الملفات تنتظر توزيعك' : '';
    var openTotal = Q && Q.expert_files_open_total != null ? qn(Q, 'expert_files_open_total') : null;
    return { cols: cols, shown: { late: cols.late, review: cols.review, with: shown, done: cols.done }, counts: counts,
             withMore: Math.max(0, cols.with.length - shown.length), notes: notes, header: header, autoOn: autoOn,
             openTotal: openTotal, total: counts.late + counts.review + counts.with + counts.done };
  }

  // —— تذاكر النزاعات والاستردادات
  var DISPUTE_REASON = { unclear: 'جزء من الرأي غير مفهوم لصاحب الطلب', not_answered: 'الرأي لم يجب عن سؤال صاحب الطلب',
                         wrong_facts: 'خطأ في الوقائع المذكورة في الرأي' };
  var DISPUTE_NOREASON = 'لم يحدد صاحب الطلب سببًا';
  function disputeKindOf(r) {
    if (!r) return null;
    var k = kindOf(r);
    return (k === 'dispute' || k === 'unactivated' || k === 'legacy') ? k : null;
  }
  function milestoneOf(f) {
    var list = f && f.case && Array.isArray(f.case.milestones) ? f.case.milestones : [];
    for (var i = 0; i < list.length; i++) if (list[i] && list[i].status === 'disputed') return list[i];
    return null;
  }
  // سبب النزاع بفصحى من الحقول: الكود المعروف يُترجم، والنص الحر من العميل/المنصة لا يُعرض أبدًا.
  function disputeReason(r, kind) {
    var f = r.ef || {}, c = r.cons || {};
    if (kind === 'unactivated') {
      var why = !f.file_found ? 'ولم يُعثر على الملف' : (!f.file_on_this_payment ? 'والملف مرتبط بدفعة أخرى' : 'والملف ما زال بانتظار الدفع');
      return 'دُفع المبلغ ولم يصل الملف إلى قائمة التوزيع، ' + why;
    }
    if (kind === 'legacy') return 'استشارة سُلّمت قبل التحويل التلقائي، وأموالها بانتظار قرارك: للخبير أم لصاحب الطلب';
    if (r.efLane === 'case_disputed' || r.dsrc === 'case') {
      var m = milestoneOf(f);
      return (m && m.n != null ? 'ملاحظة من صاحب الطلب على المرحلة رقم ' + ar(m.n) : 'ملاحظة من صاحب الطلب على إحدى مراحل القضية') + '، والدفعة محفوظة لحين قرارك';
    }
    if (r.dsrc === 'consultation' || r.cons) {
      return 'اعتراض صاحب الطلب على الاستشارة' + (c.cancel_requested ? ' وكان قد طلب الإلغاء' : '') + (c.manual_refund_settled_at ? '، وأُعيدت أمواله يدويًا من قبل' : '');
    }
    var code = str(f.dispute && f.dispute.reason);
    return 'اعتراض صاحب الطلب: ' + (DISPUTE_REASON[code] || DISPUTE_NOREASON);
  }
  function disputeAmount(r, kind) {
    var f = r.ef || {}, c = r.cons || {};
    if (r.efLane === 'case_disputed' || r.dsrc === 'case') {
      var m = milestoneOf(f);
      return moneyText(m && m.amount != null ? m.amount : f.amount, f.currency);
    }
    if (kind === 'legacy' || r.dsrc === 'consultation' || r.cons) return moneyText(c.amount, c.currency);
    return moneyText(f.amount, f.currency);
  }
  function disputeSince(r, kind) {
    var f = r.ef || {}, c = r.cons || {};
    if (kind === 'unactivated') return f.paid_at;
    if (kind === 'legacy') return c.delivered_at;
    if (r.efLane === 'case_disputed' || r.dsrc === 'case') { var m = milestoneOf(f); return m && m.disputed_at; }
    return (f.dispute && f.dispute.at) || c.disputed_at;
  }
  function v2DisputeTickets(rows, opts) {
    opts = opts || {};
    var now = opts.now || 0, Q = opts.queue || null;
    var cols = { disputes: [], refunds: [], legacy: [] };
    (Array.isArray(rows) ? rows : []).forEach(function (r) {
      var kind = disputeKindOf(r);
      if (!kind) return;
      var f = r.ef || {}, c = r.cons || {};
      var isCase = r.efLane === 'case_disputed' || r.dsrc === 'case';
      var strip = kind === 'dispute' ? (isCase ? 'ملاحظة على مرحلة من قضية' : (r.dsrc === 'consultation' || r.cons ? 'نزاع على استشارة' : 'نزاع على ملف'))
        : kind === 'unactivated' ? 'دفع بلا ملف' : 'استشارة قديمة';
      var at = disputeSince(r, kind);
      var tm = timerOf('since', at);
      var ex = str(f.expert_name) || str(c.expert_name) || str(c.payee_name);
      var t = {
        id: ['x', kind, r.apiId != null ? r.apiId : '', r.dsrc || ''].join('|'), kind: kind,
        col: kind === 'dispute' ? 'disputes' : kind === 'unactivated' ? 'refunds' : 'legacy',
        strip: { label: strip, tone: kind === 'dispute' ? 'late' : 'wait' }, timer: tm,
        text: isNaN(ms(at)) ? '' : 'مفتوح منذ ' + durShort(now - ms(at)), tone: 'since',
        amount: disputeAmount(r, kind), client: str(r.who), expert: ex,
        title: str(f.title) || str(c.title) || 'بند', reason: disputeReason(r, kind),
        primary: { label: 'افتح وقرّر', act: { do: 'open' } }, row: r, sortAt: isNaN(ms(at)) ? Infinity : ms(at), person: null
      };
      var pe = str(f.expert_email).toLowerCase();
      if (EMAIL_RE.test(pe) && ex) t.person = { email: pe, name: ex };
      cols[t.col].push(t);
    });
    Object.keys(cols).forEach(function (k) { cols[k].sort(function (a, b) { return a.sortAt - b.sortAt; }); });
    // استردادات يدوية: عدّاد من الطابور فقط (لا قايمة في الداشبورد) ⇒ بطاقة بالعدد. الطابور ناقص ⇒ null (لا صفر).
    var manual = Q ? (Q.manual_refunds_pending == null ? null : qn(Q, 'manual_refunds_pending')) : null;
    var counts = { disputes: cols.disputes.length, refunds: cols.refunds.length + (manual || 0), legacy: cols.legacy.length };
    return { cols: cols, manualRefunds: manual, counts: counts, total: counts.disputes + counts.refunds + counts.legacy };
  }

  // ------------------------------------------------------------------ صفحة الشخص (D2)
  // ⛔ المدخل ردّ `/api/v2/person` (أو null لو الطلب كله فشل). كل قسم `null` ⇒ «غير متاح بعد» — لا صفر مختلق أبدًا؛ والصفر الحقيقي
  // (مصدر وصل وقال لا شيء) يُكتب «لا …» بنص. التواريخ والأحداث بفصحى من الحقول، ولا نص خام من المنصة.
  var NA = 'غير متاح بعد';
  var MONTHS = ['يناير', 'فبراير', 'مارس', 'أبريل', 'مايو', 'يونيو', 'يوليو', 'أغسطس', 'سبتمبر', 'أكتوبر', 'نوفمبر', 'ديسمبر'];
  function dateText(iso) {
    var t = ms(iso);
    if (isNaN(t)) return '';
    var d = new Date(t);
    return ar(d.getDate()) + ' ' + MONTHS[d.getMonth()] + ' ' + ar(d.getFullYear());
  }
  var ROLE_CHIP = { admin: 'إدارة', staff: 'فريق العمل', investor: 'مستثمر', expert: 'خبير', trainer: 'مدرّب', trainer_pending: 'طلب مدرّب',
                    learner: 'متعلّم', visitor: 'زائر', member: 'عضو' };
  var FILE_STATUS = { awaiting_assignment: 'ينتظر خبيرًا', assigned: 'أُرسل إلى الخبير', claimed: 'استلمه الخبير', writing: 'قيد الكتابة', in_review: 'ينتظر المراجعة',
                      delivered: 'سُلّم', closed: 'مغلق', disputed: 'نزاع مفتوح', refunded: 'أُعيدت أمواله', cancelled: 'أُلغي', needs_info: 'ينتظر إجابة صاحب الطلب' };
  var COURSE_STATE = { published: 'منشورة', pending: 'تنتظر الاعتماد', rejected: 'مرفوضة', draft: 'مسودة', archived: 'مؤرشفة' };
  var EVENT_TEXT = { joined: 'الانضمام إلى المنصة', login: 'آخر دخول', invite_sent: 'إرسال دعوة الانضمام', invite_opened: 'فتح رابط الدعوة',
                     invite_approved: 'الموافقة على الدعوة', invite_registered: 'إكمال التسجيل من الدعوة', file_assigned: 'إسناد ملف',
                     payout_requested: 'طلب سحب أرباح', payout_paid: 'تحويل طلب السحب' };
  function amountsText(list) {
    return (Array.isArray(list) ? list : []).map(function (a) { return moneyText(a.amount, a.currency); }).filter(Boolean).join(' + ');
  }
  function naCard(c) { c.na = true; c.text = NA; return c; }

  function v2Person(resp, now, email) {
    if (!resp || typeof resp !== 'object') return { state: 'failed', email: email || '', cards: null };
    var em = str(resp.email) || email || '';
    if (resp.found === null || resp.found === undefined) return { state: 'failed', email: em, cards: null, sources: resp.sources || {} };
    if (resp.found === false) return { state: 'notfound', email: em, cards: null, sources: resp.sources || {} };
    var id = resp.identity || {}, src = resp.sources || {};
    var failed = Object.keys(src).filter(function (k) { return src[k] === 'failed'; });
    var name = str(id.name) || em;
    // الحرف الأول من الاسم بعد اللقب («د.» «أ.» «م.») — لا من اللقب نفسه.
    var plain = name.replace(/^(?:د|أ|م|السيد|السيدة|الدكتور|الدكتورة|الأستاذ|الأستاذة|المهندس|المهندسة)\.?\s+/, '');
    var vm = { state: 'ok', email: em, name: name, initial: (plain || name).charAt(0), photo: id.photo || null,
               chips: (Array.isArray(resp.roles) ? resp.roles : []).map(function (k) { return { key: k, label: ROLE_CHIP[k] || '' }; }).filter(function (c) { return c.label; }),
               country: str(id.country) || null, countryText: str(id.country) || NA, failed: failed, sources: src, active: id.is_active !== false };
    // «الانضمام في … بدعوة من …» — الداعي لا يُدّعى إلا من صف دعوة فعلي، وفشل المصدر يُقال.
    var join = dateText(id.joined_at);
    var line = join ? 'الانضمام في ' + join : 'تاريخ الانضمام: ' + NA;
    if (id.invited_by && id.invited_by.name) line += ' · بدعوة من ' + id.invited_by.name;
    else if (id.invited_by && id.invited_by.kind === 'founder') line += ' · بدعوة من الإدارة';
    else if ((src.invites === 'failed' || src.invites === 'partial')) line += ' · الداعي: ' + NA;
    vm.joinLine = line;
    vm.lastLogin = id.last_login_at ? agoText(id.last_login_at, now || 0) : '';

    // —— ملفاته
    var ex = resp.expert, c1 = { key: 'files', title: 'الملفات' };
    if (ex === null || ex === undefined) naCard(c1);
    else {
      c1.count = ex.files_count; c1.partial = !!ex.partial;
      c1.summary = ex.files_count ? (U(ex.files_count, ['ملف واحد', 'ملفان', 'ملفات', 'ملفًا']) + (ex.partial ? ' ضمن المعروض فقط' : ''))
        : (ex.partial ? 'لا ملفات ضمن الجزء المعروض من الملفات' : 'لا ملفات بعد');
      c1.items = (ex.latest || []).map(function (f) {
        return { title: str(f.title) || 'ملف', meta: clean([FILE_STATUS[f.status] || '', moneyText(f.amount, f.currency), f.at ? agoText(f.at, now || 0) : '']).join(' · ') };
      });
      c1.note = 'تشمل الملفات المسندة إلى هذا الشخص كخبير فقط؛ الملفات المقدَّمة منه كصاحب طلب غير متاحة بعد';
    }
    // —— دوراته (كمدرّب)
    var tr = resp.trainer, c2 = { key: 'courses', title: 'الدورات' };
    if (tr === null || tr === undefined) {
      if (id.trainer_status === 'none') { c2.summary = 'لا صفة مدرّب لهذا الحساب'; c2.items = []; } else naCard(c2);
    } else {
      var bits = [];
      if (tr.status === 'pending') bits.push('طلب المدرّب بانتظار القرار');
      if (tr.courses_count != null) bits.push(tr.courses_count ? U(tr.courses_count, ['دورة واحدة', 'دورتان', 'دورات', 'دورة']) : 'لا دورات بعد');
      if (tr.students_count != null && tr.courses_count) bits.push('المتعلمون: ' + ar(tr.students_count));
      if (tr.rating_avg != null && tr.rating_count) bits.push('التقييم: ' + fmt(tr.rating_avg) + ' من ' + U(tr.rating_count, ['تقييم واحد', 'تقييمين', 'تقييمات', 'تقييمًا']));
      if (!bits.length) naCard(c2);
      else {
        c2.summary = bits.join(' · ');
        c2.items = (tr.courses || []).map(function (c) { return { title: str(c.title) || 'دورة', meta: COURSE_STATE[c.state] || '' }; });
      }
    }
    // —— فلوسه
    var mo = resp.money, c3 = { key: 'money', title: 'الفلوس' };
    if (mo === null || mo === undefined) naCard(c3);
    else {
      c3.rows = [];
      var payRow = function (k, blk, none) {
        if (blk === null || blk === undefined) c3.rows.push({ k: k, v: NA, na: true });
        else if (!blk.count) c3.rows.push({ k: k, v: blk.partial ? 'لا شيء ضمن الجزء المعروض' : none });
        else c3.rows.push({ k: k, v: U(blk.count, ['طلب واحد', 'طلبان', 'طلبات', 'طلبًا']) + (amountsText(blk.amounts) ? ' — ' + amountsText(blk.amounts) : '') });
      };
      payRow('طلبات سحب معلقة', mo.pending, 'لا طلبات سحب معلقة');
      payRow('ما حُوّل من قبل', mo.paid, 'لا تحويلات سابقة');
      c3.rows.push({ k: 'رصيد المحفظة', v: NA, na: true });
    }
    // —— ما تعلّمه
    var le = resp.learner, c4 = { key: 'learning', title: 'التعلّم', rows: [] };
    c4.rows.push(le === null || le === undefined ? { k: 'دورات سجّل فيها أو دفع ثمنها', v: NA, na: true }
      : { k: 'دورات سجّل فيها أو دفع ثمنها', v: le.enrollments_count ? U(le.enrollments_count, ['دورة واحدة', 'دورتان', 'دورات', 'دورة']) : 'لا تسجيلات' });
    c4.rows.push(resp.books === null || resp.books === undefined ? { k: 'الكتب المشتراة', v: NA, na: true } : { k: 'الكتب المشتراة', v: String(resp.books) });
    vm.cards = [c1, c2, c3, c4];
    // —— السجل
    vm.log = resp.log === null || resp.log === undefined ? null : resp.log.map(function (e) {
      var base = EVENT_TEXT[e.kind];
      if (!base) return null;
      return { at: ms(e.at), when: dateText(e.at), ago: agoText(e.at, now || 0), text: base + (e.kind === 'file_assigned' && str(e.title) ? ' «' + str(e.title) + '»' : '') };
    }).filter(Boolean);
    vm.logPartial = !!resp.log_partial;
    return vm;
  }

  // ------------------------------------------------------------------ خريطة الأقسام (D1-B)
  // كل شاشة قديمة تقع داخل قسم وتبويب. ⛔ لا نسخ للشاشات: التبويب يسمّي الموديول القديم (`mod`) والحالة الداخلية
  // التي تُضبط قبل رسمه (`st`)، و`m` شرط التعرّف العكسي (أي حالة داخلية تعني أي تبويب).
  //   st : {اسم متغيّر الحالة: قيمة}     تُطبَّق عند فتح التبويب
  //   m  : {اسم متغيّر: [قيم]} أو {اسم: {not:[قيم]}}      بلا m وبلا st = يطابق أي حالة للموديول
  var STATE_DEFAULTS = { activeFilter: 'all', escTab: 'sessions', finTab: 'summary', teamTab: 'experts', topicsTab: 'ideas',
                         courseTab: 'platform', invTab: 'owners', tgTab: 'goals', v2mode: 'board' };
  var FILE_FILTERS = ['t:files', 'attn', 'review', 'urgent', 'nocand', 'contract', 'case'];

  function hiddenTab(t) { t.hidden = true; return t; }
  function T(key, label, mod, st, m) { var t = { key: key, label: label, mod: mod, st: st || {} }; if (m) t.m = m; return t; }

  var SECTIONS = [
    { key: 'home', label: 'اللوحة', img: null, desc: 'ما يحتاج قرارك الآن وكل ما ينتظرك', tabs: [
      T('board', 'اللوحة والقرارات', 'home', { v2mode: 'board' }, { v2mode: ['board', 'focus'] }),
      T('inbox', 'كل الوارد', 'inbox', { activeFilter: 'all' }, {})
    ] },
    { key: 'files', label: 'ملفات الخبراء', img: 'files', desc: 'ملفات تنتظر خبيرًا أو مراجعة، وفريق الخبراء', tabs: [
      T('files', 'الملفات', 'v2files'),
      T('experts', 'الخبراء', 'team', { teamTab: 'experts' }, { teamTab: ['experts'] }),
      T('all', 'كل الملفات', 'inbox', { activeFilter: 't:files' }, { activeFilter: FILE_FILTERS })
    ] },
    { key: 'disputes', label: 'النزاعات والاستردادات', img: 'disputes', desc: 'اعتراضات العملاء وأموال محجوزة لحين قرارك', tabs: [
      T('disputes', 'النزاعات', 'v2disputes'),
      T('escrow', 'الضمان', 'escrow', { escTab: 'sessions' }, { escTab: ['sessions', 'disputes', 'released'] }),
      T('all', 'كل النزاعات', 'inbox', { activeFilter: 't:disputes' }, { activeFilter: ['t:disputes', 't:legacy'] })
    ] },
    { key: 'courses', label: 'الدورات والمدرّبون', img: 'courses', desc: 'الدورات المنشورة وطلبات المدرّبين', tabs: [
      T('courses', 'الدورات', 'courses'),
      T('trainers', 'المدرّبون', 'team', { teamTab: 'trainers' }, { teamTab: ['trainers'] })
    ] },
    { key: 'market', label: 'سوق الخدمات', img: 'market', desc: 'طلبات الأعضاء وعروض الخبراء', tabs: [
      T('requests', 'الطلبات', 'market')
    ] },
    { key: 'books', label: 'الكتب', img: 'books', desc: 'عروض الكتب بانتظار المراجعة وطلبات القرّاء والمتجر', tabs: [
      T('offers', 'مراجعة العروض', 'v2b_offers'),
      T('requests', 'طلبات القرّاء', 'v2b_requests'),
      T('books', 'الكتب والأعمال', 'knowledge')
    ] },
    { key: 'people', label: 'الناس والدعوات', img: 'people', desc: 'الأعضاء والدعوات والرسائل', tabs: [
      T('users', 'المستخدمون', 'users'),
      T('invites', 'الدعوات', 'invites'),
      T('messages', 'الرسائل', 'inbox', { activeFilter: 't:messages' }, { activeFilter: ['t:messages'] }),
      hiddenTab(T('person', 'صفحة الشخص', 'v2person'))
    ] },
    { key: 'money', label: 'الفلوس', img: 'money', desc: 'كل جنيه دخل، وأين هو الآن، والقرارات المالية', tabs: [
      T('overview', 'نظرة', 'v2m_overview'),
      T('payouts', 'التحويلات', 'v2m_payouts'),
      T('receipts', 'الإيصالات والمدفوعات العالقة', 'v2m_receipts'),
      T('prices', 'الأسعار', 'v2m_prices'),
      T('shares', 'النسب والإعدادات', 'v2m_shares'),
      T('ads', 'إعلانات الأعمال', 'v2m_ads'),
      T('all', 'كل السجلات', 'finance', { finTab: 'summary' }, { finTab: { not: [] } }),
      hiddenTab(T('manual', 'الإيصالات (الشاشة القديمة)', 'escrow', { escTab: 'manual' }, { escTab: ['manual'] }))
    ] },
    { key: 'content', label: 'المحتوى', img: 'content', desc: 'المقالات والموضوعات ودليل الاستخدام', tabs: [
      T('topics', 'المحتوى', 'topics', { topicsTab: 'ideas' }, { topicsTab: { not: ['tutorials'] } }),
      T('tutorials', 'دليل الاستخدام', 'topics', { topicsTab: 'tutorials' }, { topicsTab: ['tutorials'] })
    ] },
    { key: 'marketing', label: 'التسويق', img: 'marketing', desc: 'الحملات والنشر على المنصات', tabs: [
      T('campaigns', 'الحملات', 'marketing')
    ] },
    { key: 'reports', label: 'التقارير', img: 'reports', desc: 'ما يطلبه الناس وأين الفرصة', tabs: [
      T('demand', 'تحليل الطلب', 'analysis')
    ] },
    { key: 'brain', label: 'العقل', img: 'brain', desc: 'ما قرّره العقل اليوم ومساعدوه', tabs: [
      T('log', 'سجل اليوم', 'home', { v2mode: 'brain' }, { v2mode: ['brain'] }),
      T('helpers', 'المساعدون', 'ai')
    ] },
    { key: 'company', label: 'الشركة ورأس المال', img: 'company', desc: 'الشركاء والأهداف والإعدادات', tabs: [
      T('invest', 'الاستثمار والشركاء', 'investment'),
      T('targets', 'الأهداف والتأسيس', 'targets'),
      T('settings', 'الإعدادات', 'settings')
    ] }
  ];
  // مفاتيح قديمة ابتُلعت (REDIRECTS في index.html) — تُحلّ هنا بنفس حالتها الداخلية.
  var ALIASES = {
    overview: { mod: 'inbox', state: {} },
    messages: { mod: 'inbox', state: { activeFilter: 't:messages' } },
    packages: { mod: 'finance', state: { finTab: 'packages' } },
    tutorials: { mod: 'topics', state: { topicsTab: 'tutorials' } },
    partners: { mod: 'investment', state: { invTab: 'owners' } },
    foundation: { mod: 'targets', state: { tgTab: 'foundation' } }
  };

  function secOf(key) { for (var i = 0; i < SECTIONS.length; i++) if (SECTIONS[i].key === key) return SECTIONS[i]; return null; }
  function tabOf(secKey, tabKey) {
    var s = secOf(secKey); if (!s) return null;
    for (var i = 0; i < s.tabs.length; i++) if (s.tabs[i].key === tabKey) return s.tabs[i];
    return null;
  }
  function stVal(state, k) { var v = state && state[k]; return (v === undefined || v === null || v === '') ? STATE_DEFAULTS[k] : v; }
  // درجة مطابقة تبويب لحالة: -1 لا يطابق، وإلا عدد الشروط المتحقّقة (الأخصّ يفوز).
  function scoreTab(tab, state) {
    var m = tab.m || (function () { var o = {}; Object.keys(tab.st).forEach(function (k) { o[k] = [tab.st[k]]; }); return o; })();
    var n = 0, ks = Object.keys(m);
    for (var i = 0; i < ks.length; i++) {
      var v = stVal(state, ks[i]), c = m[ks[i]];
      var ok = Array.isArray(c) ? c.indexOf(v) > -1 : (c && Array.isArray(c.not) ? c.not.indexOf(v) < 0 : true);
      if (!ok) return -1;
      n++;
    }
    return n;
  }
  function pack(sec, tab, extra) {
    var st = tab.st;
    if (extra) { st = {}; Object.keys(tab.st).forEach(function (k) { st[k] = tab.st[k]; }); Object.keys(extra).forEach(function (k) { st[k] = extra[k]; }); }
    return { section: sec.key, tab: tab.key, mod: tab.mod, st: st };
  }
  // sectionFor(oldModule[, state[, hint]]) ⇒ {section, tab, mod, st} أو null لموديول مجهول.
  //   hint = {section, tab} الحالي: يُفضَّل عند التعادل أو حين لا يطابق شيء (حالة داخلية بلا تبويب، مثل «الفريق الإداري»).
  function sectionFor(oldModule, state, hint) {
    var mod = String(oldModule == null ? '' : oldModule);
    var st = {};
    Object.keys(state || {}).forEach(function (k) { st[k] = state[k]; });
    var aliasState = null;
    if (ALIASES[mod]) { var a = ALIASES[mod]; aliasState = a.state; Object.keys(a.state).forEach(function (k) { st[k] = a.state[k]; }); mod = a.mod; }
    var best = null, bestScore = -2, hintHit = null, any = null;
    SECTIONS.forEach(function (sec) {
      sec.tabs.forEach(function (tab) {
        if (tab.mod !== mod) return;
        if (!any) any = { sec: sec, tab: tab };
        var sc = scoreTab(tab, st);
        if (sc < 0) return;
        if (hint && hint.section === sec.key && hint.tab === tab.key) hintHit = { sec: sec, tab: tab, sc: sc };
        if (sc > bestScore) { bestScore = sc; best = { sec: sec, tab: tab }; }
      });
    });
    if (hintHit && hintHit.sc >= bestScore) return pack(hintHit.sec, hintHit.tab, aliasState);
    if (best && hint && bestScore === 0 && best.tab.key !== hint.tab) {
      // أفضل مطابقة هي التبويب العام لـ«كل الوارد» (بلا شرط): لا تُنقل المستخدم من قسمه إن كان تبويبه من نفس الشاشة (شرائح الوارد داخل «الملفات» مثلًا).
      var gt = tabOf(hint.section, hint.tab);
      if (gt && gt.mod === mod && mod === 'inbox') return pack(secOf(hint.section), gt, aliasState);
    }
    if (best) return pack(best.sec, best.tab, aliasState);
    // حالة داخلية بلا تبويب (مثل «الفريق الإداري» داخل شاشة الفريق): ابقَ حيث أنت إن كان تبويبك لنفس الموديول.
    if (hint) {
      var ht = tabOf(hint.section, hint.tab);
      if (ht && ht.mod === mod) return pack(secOf(hint.section), ht, aliasState);
    }
    return any ? pack(any.sec, any.tab, aliasState) : null;
  }
  // العنوان: #s/<قسم>[/<تبويب>] — يقبل بدون # وبدون s/ المسبوقة بشرطة.
  function sectionHash(key, tab, person) {
    if (person && key === 'people' && tab === 'person') return '#s/people/person/' + personKey(person);
    return '#s/' + key + (tab ? '/' + tab : '');
  }
  // مفتاح الشخص في العنوان = بريده بحروف صغيرة مُرمَّزًا (لا هاش ولا اسم ولا معرّف داخلي).
  function personKey(email) { return encodeURIComponent(String(email == null ? '' : email).trim().toLowerCase()); }
  function personEmailOf(key) {
    var e;
    try { e = decodeURIComponent(String(key == null ? '' : key)); } catch (x) { return ''; }
    e = e.trim().toLowerCase();
    return e.length <= 200 && EMAIL_RE.test(e) ? e : '';
  }
  function parseSectionHash(h) {
    var s = String(h == null ? '' : h).replace(/^#/, '').replace(/^\/+/, '').trim();
    var parts = s.split('/');
    if (parts[0] !== 's' || !parts[1]) return null;
    var sec = secOf(parts[1]);
    if (!sec) return null;
    var tab = parts[2] ? tabOf(sec.key, parts[2]) : null;
    var out = { section: sec.key, tab: (tab || sec.tabs[0]).key, exact: !!(parts[2] ? tab : true) };
    if (tab && tab.hidden) {
      // صفحة الشخص: بلا بريد صالح في العنوان ⇒ أول تبويب في القسم (ولا صفحة فاضية).
      var em = sec.key === 'people' && tab.key === 'person' ? personEmailOf(parts[3]) : '';
      if (em) out.person = em; else { out.tab = sec.tabs[0].key; out.exact = false; }
    }
    return out;
  }
  // أي عنوان (جديد أو رابط قديم) ⇒ {section, tab, mod, st[, person]} أو null.
  function routeFor(hash, state) {
    var s = String(hash == null ? '' : hash).replace(/^#/, '').trim();
    if (!s || s === 'home') return pack(secOf('home'), secOf('home').tabs[0]);
    var p = parseSectionHash(s);
    if (p) {
      var t = tabOf(p.section, p.tab), r = pack(secOf(p.section), t);
      if (p.person) r.person = p.person;
      return r;
    }
    return sectionFor(s, state);
  }

  // ------------------------------------------------------------------ «الفلوس» على الهيكل الجديد (D3)
  // ⛔ نقي: كل دالة تأخذ ردود المصادر كما وصلت وتعيد قيمة. المصدر الذي تعذّر جلبه = `null` (والشاشة تكتب «غير متاح بعد»)،
  // ولا يتحوّل إلى صفر أبدًا. ⛔ العملات لا تُجمع ولا تُحوَّل: لكل عملة رقمها، وغير الجنيه يظهر منفصلًا «بعملة أخرى».
  // ⛔ لا حساب لـ«صافي البروفيسور»: لا يوجد مصدر يفصل نصيب المنصة عن نصيب أصحاب الأعمال، فيبقى «غير متاح بعد».
  var CUR_LONG = { EGP: 'جنيه مصري', USD: 'دولار أمريكي', SAR: 'ريال سعودي', AED: 'درهم إماراتي', KWD: 'دينار كويتي', QAR: 'ريال قطري',
                   EUR: 'يورو', GBP: 'جنيه إسترليني' };
  function curLong(c) { c = String(c || 'EGP').trim().toUpperCase(); return CUR_LONG[c] || c; }
  var COUNTRY_LABEL = { eg: 'مصر', sa: 'السعودية', ae: 'الإمارات', kw: 'الكويت', qa: 'قطر', 'default': 'باقي البلاد' };
  var PERIODS = [{ key: 'day', label: 'اليوم' }, { key: 'month', label: 'الشهر' }, { key: 'year', label: 'السنة' }];
  var SERVICES = [{ key: 'experts', label: 'ملفات الخبراء' }, { key: 'courses', label: 'الدورات' }, { key: 'books', label: 'الكتب' }, { key: 'other', label: 'أخرى' }];

  function two(n) { return (n < 10 ? '0' : '') + n; }
  function ymd(d) { return d.getFullYear() + '-' + two(d.getMonth() + 1) + '-' + two(d.getDate()); }
  // الفترة بتوقيت الجهاز: day = اليوم · month = من أول الشهر · year = من أول السنة. `until` غير شامل.
  function v2Period(key, now) {
    var d = new Date(now || 0), y = d.getFullYear(), m = d.getMonth();
    var from, until;
    if (key === 'day') { from = ymd(d); until = ymd(new Date(y, m, d.getDate() + 1)); }
    else if (key === 'year') { from = y + '-01-01'; until = (y + 1) + '-01-01'; }
    else { key = 'month'; from = y + '-' + two(m + 1) + '-01'; until = ymd(new Date(y, m + 1, 1)); }
    return { key: key, label: key === 'day' ? 'اليوم' : key === 'month' ? 'الشهر' : 'السنة', from: from, until: until, month: y + '-' + two(m + 1) };
  }
  function numOf(v) { var n = typeof v === 'number' ? v : (typeof v === 'string' && v.trim() !== '' ? Number(v) : NaN); return isFinite(n) ? n : 0; }
  function cents(n) { return Math.round(n * 100); }
  // يجمع {currency, amount}[] لكل عملة لوحدها (الجنيه أولًا ثم الباقي أبجديًا). مبالغ بالسنت لتفادي أخطاء الكسور.
  function sumByCurrency(items) {
    var acc = {};
    items.forEach(function (it) {
      var c = String(it.currency || 'EGP').trim().toUpperCase() || 'EGP', a = numOf(it.amount);
      if (!a) return;
      acc[c] = (acc[c] || 0) + cents(a);
    });
    return Object.keys(acc).sort(function (x, y) { return x === 'EGP' ? -1 : y === 'EGP' ? 1 : (x < y ? -1 : 1); })
      .map(function (c) { return { currency: c, amount: acc[c] / 100 }; });
  }
  // «١٬٢٠٠ جنيه» + «بعملة أخرى: ٣٠ دولار · ١٠٠ ريال». لا مبلغ أصلًا (والمصدر معروف) ⇒ «٠ جنيه».
  function v2MoneyLine(totals) {
    if (!Array.isArray(totals)) return null;
    var egp = totals.filter(function (t) { return t.currency === 'EGP'; })[0];
    var others = totals.filter(function (t) { return t.currency !== 'EGP'; }).map(function (t) { return moneyText(t.amount, t.currency); });
    return { main: moneyText(egp ? egp.amount : 0, 'EGP'), others: others, othersText: others.length ? 'بعملة أخرى: ' + others.join(' · ') : '' };
  }
  function serviceOf(source) {
    var s = String(source || '').trim().toLowerCase();
    if (s === 'consultation' || s === 'consulting' || s === 'expert_file' || s === 'expert_case') return 'experts';
    if (s === 'course' || s === 'course_offer' || s === 'program') return 'courses';
    if (s === 'book' || s === 'knowledge') return 'books';
    return 'other';
  }
  // دخل الفترة من صفوف `/api/revenues` الخام (قبل أي تحويل أو تقريب). ⛔ `total_egp` لا تُستعمل: بتحوّل الدولار للجنيه بسعر صرف.
  //   الجنيه من `amount_egp` · الدولار من `amount_usd` · أي عملة أخرى من `amount_original` حين `needs_fx`.
  function v2Income(rows, periodKey, now) {
    if (!Array.isArray(rows)) return null;
    var P = v2Period(periodKey, now), all = [], by = { experts: [], courses: [], books: [], other: [] }, n = 0;
    rows.forEach(function (r) {
      if (!r) return;
      var d = String(r.date || '').slice(0, 10);
      if (!(d >= P.from && d < P.until)) return;
      var svc = serviceOf(r.source), parts = [];
      if (numOf(r.amount_egp)) parts.push({ currency: 'EGP', amount: numOf(r.amount_egp) });
      if (numOf(r.amount_usd)) parts.push({ currency: 'USD', amount: numOf(r.amount_usd) });
      var oc = String(r.currency || '').trim().toUpperCase();
      if (r.needs_fx && oc && oc !== 'EGP' && oc !== 'USD' && numOf(r.amount_original)) parts.push({ currency: oc, amount: numOf(r.amount_original) });
      if (!parts.length) return;
      n++;
      parts.forEach(function (p) { all.push(p); by[svc].push(p); });
    });
    var services = {};
    SERVICES.forEach(function (s) { services[s.key] = sumByCurrency(by[s.key]); });
    return { period: P, count: n, totals: sumByCurrency(all), services: services };
  }
  // المحجوز في الضمان: كل جلسة لم تُحرَّر ولم تُردّ (محجوزة · بانتظار التأكيد · عليها نزاع). `null` ⇒ المصدر تعذّر.
  function v2Held(sessions) {
    if (!Array.isArray(sessions)) return null;
    var live = sessions.filter(function (s) { return s && (!s.status || ['held', 'confirm', 'dispute'].indexOf(s.status) > -1); });
    return { count: live.length, totals: sumByCurrency(live.map(function (s) { return { currency: s.currency, amount: s.amount }; })) };
  }
  function payoutAmount(p) { return numOf(p && p.raw && p.raw.amount != null ? p.raw.amount : p && p.amount); }
  function payoutCurrency(p) { return (p && p.raw && p.raw.currency) || (p && p.currency) || 'EGP'; }
  // المستحق للخبراء والمدرّبين = طلبات السحب المعلّقة (لم تُحوَّل بعد).
  function v2Owed(payouts) {
    if (!Array.isArray(payouts)) return null;
    var live = payouts.filter(function (p) { return p && (p.status == null || p.status === 'pending'); });
    return { count: live.length, totals: sumByCurrency(live.map(function (p) { return { currency: payoutCurrency(p), amount: payoutAmount(p) }; })) };
  }
  var NA_MONEY = 'غير متاح بعد';
  var NET_WHY = 'لا يوجد مصدر يفصل نصيب البروفيسور عن نصيب أصحاب الأعمال بعد';
  // اللوحة: أربعة أرقام بشرح سطر لكل رقم. `src` = {revenues, escrow, payouts, net} (كلٌّ منها null لو مصدره تعذّر).
  function v2MoneyBoard(src, periodKey, now) {
    src = src || {};
    var P = v2Period(periodKey, now), inc = v2Income(src.revenues, P.key, now), held = v2Held(src.escrow), owed = v2Owed(src.payouts);
    function num(key, label, note, data, extra) {
      var line = data ? v2MoneyLine(data.totals) : null;
      return { key: key, label: label, note: note, na: !line, text: line ? line.main : NA_MONEY, others: line ? line.othersText : '', count: data ? data.count : null,
               why: line ? '' : (extra || '') };
    }
    var net = Array.isArray(src.net) ? { totals: src.net, count: null } : null;
    return { period: P, numbers: [
      num('income', 'دخل', 'ما دخل دفتر الشركة ' + (P.key === 'day' ? 'اليوم' : P.key === 'month' ? 'هذا الشهر' : 'هذه السنة'), inc, 'تعذّر جلب دفتر الإيرادات'),
      num('held', 'محجوز حتى يُسلَّم العمل', 'أموال دفعها الناس وتنتظر تسليم العمل لتصل إلى أصحابها', held, 'تعذّر جلب أموال الضمان'),
      num('owed', 'مستحق للخبراء والمدرّبين', 'طلبات سحب أُرسلت ولم تُحوَّل بعد', owed, 'تعذّر جلب طلبات السحب'),
      num('net', 'صافي البروفيسور', 'نصيب البروفيسور بعد نصيب أصحاب الأعمال', net, NET_WHY)
    ] };
  }
  // أعمدة «من أين جاء الدخل»: الجنيه فقط (العملات الأخرى سطر منفصل). في الشهر نستعمل مدفوعات المنصة (تفصل ملف الخبير عن الاستشارة
  // العادية) إن وصلت، وإلا دفتر الإيرادات. `bridge` = رد `/api/v2/income/by-service` أو null.
  var BRIDGE_KEY = { expert_files: 'experts', courses: 'courses', books: 'books', other: 'other' };
  function v2IncomeBars(income, bridge, periodKey) {
    var fromBridge = periodKey === 'month' && bridge && Array.isArray(bridge.services);
    var perService = {}, foreign = [];
    if (fromBridge) {
      bridge.services.forEach(function (s) { if (BRIDGE_KEY[s.key]) perService[BRIDGE_KEY[s.key]] = sumByCurrency(s.totals || []); });
    } else if (income) {
      SERVICES.forEach(function (s) { perService[s.key] = income.services[s.key] || []; });
    } else return null;
    var rows = SERVICES.map(function (s) {
      var t = perService[s.key] || [], egp = t.filter(function (x) { return x.currency === 'EGP'; })[0];
      var oth = t.filter(function (x) { return x.currency !== 'EGP'; });
      oth.forEach(function (o) { foreign.push(o); });
      return { key: s.key, label: s.label, amount: egp ? egp.amount : 0, text: moneyText(egp ? egp.amount : 0, 'EGP'), others: oth.map(function (o) { return moneyText(o.amount, o.currency); }) };
    });
    var max = Math.max.apply(null, rows.map(function (r) { return r.amount; }).concat([0]));
    var sum = rows.reduce(function (a, r) { return a + r.amount; }, 0);
    rows.forEach(function (r) { r.width = max > 0 ? Math.max(r.amount > 0 ? 4 : 0, Math.round(r.amount / max * 100)) : 0; r.share = sum > 0 ? Math.round(r.amount / sum * 100) : 0; });
    return { rows: rows, source: fromBridge ? 'payments' : 'ledger', total: moneyText(sum, 'EGP'), foreign: sumByCurrency(foreign),
             note: fromBridge ? 'من مدفوعات المنصة في هذا الشهر' : 'من دفتر الإيرادات — ملفات الخبراء تشمل الاستشارات العادية' };
  }

  // —— التحويلات المستحقة
  function v2PayoutRows(pending, now) {
    if (!Array.isArray(pending)) return null;
    var rows = pending.filter(function (p) { return p && p.pid && (p.status == null || p.status === 'pending'); }).map(function (p) {
      var card = v2Card(Object.assign({}, p, { apiKind: 'payout' }), { now: now, inboxRows: null });
      var m = card.primary.money, at = ms(p.raw && p.raw.created_at);
      return { id: String(p.pid), name: m.name, email: personEmailOfRow(p), what: 'سحب من المحفظة', method: m.method || m.dest || '', dest: m.dest,
               amount: m.amount, currency: m.currency, amountText: moneyText(m.amount, m.currency), fx: !!p.fx_alert,
               timer: timerOf('since', at), since: isNaN(at) ? '' : v2TimerText(timerOf('since', at), now), at: isNaN(at) ? Infinity : at, card: card };
    });
    rows.sort(function (a, b) { return a.at - b.at; });
    return rows;
  }
  // المنتهي هذا الشهر (محوَّل أو مرفوض). مصدر فشل ⇒ يُذكر في `failed` ويبقى النصف الآخر.
  function v2PayoutHistory(paid, rejected, now) {
    var P = v2Period('month', now), failed = [], out = [];
    if (!Array.isArray(paid) && !Array.isArray(rejected)) return null;
    function take(list, status, field) {
      if (!Array.isArray(list)) { failed.push(status === 'paid' ? 'التحويلات المنفّذة' : 'التحويلات المرفوضة'); return; }
      list.forEach(function (p) {
        if (!p) return;
        var at = ms(p[field] || p.updated_at);
        if (isNaN(at)) return;
        var day = ymd(new Date(at));
        if (!(day >= P.from && day < P.until)) return;
        out.push({ id: String(p.id || ''), status: status, statusText: status === 'paid' ? 'حُوِّل' : 'رُفض', name: str(p.user_name) || str(p.user_email) || 'صاحب الطلب',
                   email: str(p.user_email).toLowerCase(), amountText: moneyText(p.amount, p.currency || 'EGP'), at: at, when: agoText(at, now), ref: status === 'paid' ? str(p.reference) : '' });
      });
    }
    take(paid, 'paid', 'settled_at'); take(rejected, 'rejected', 'rejected_at');
    out.sort(function (a, b) { return b.at - a.at; });
    return { rows: out, failed: failed };
  }

  // —— المدفوعات العالقة (قراءة فقط)
  var STUCK_KIND = { course: 'دورة', course_offer: 'دورة', consultation: 'استشارة أو ملف خبير', plan: 'اشتراك', book: 'كتاب', knowledge: 'عمل معرفي', verify: 'توثيق',
                     ads_deposit: 'رصيد إعلانات' };
  var PAY_PROVIDER = { stripe: 'بطاقة بنكية', paymob: 'بطاقة بنكية', paytabs: 'بطاقة بنكية', card: 'بطاقة بنكية', manual: 'تحويل يدوي' };
  var NO_REFUND_KINDS = ['book', 'knowledge'];
  // الكتب لا تُسترد (قرار المؤسس): لا زرّ استرداد لعمل من الكتب، ويُكتب السبب مكانه.
  function v2RefundRule(kind) {
    var k = String(kind || '').trim().toLowerCase();
    return NO_REFUND_KINDS.indexOf(k) > -1 ? { refundable: false, text: 'الكتب لا تُسترد' } : { refundable: true, text: '' };
  }
  function stuckRow(o, now) {
    var email = str(o.buyer_email || o.user_email).toLowerCase(), name = str(o.buyer_name) || email, kind = str(o.kind).toLowerCase();
    var created = ms(o.created_at), age = typeof o.age_hours === 'number' && isFinite(o.age_hours) ? o.age_hours : (isNaN(created) ? NaN : (now - created) / HOUR);
    var rule = v2RefundRule(kind);
    return { id: String(o.order_id || o.id || ''), kind: kind, kindText: STUCK_KIND[kind] || 'طلب', title: str(o.title) || STUCK_KIND[kind] || 'طلب',
             amount: o.amount, currency: o.currency || 'EGP', amountText: moneyText(o.amount, o.currency || 'EGP'),
             name: name || 'صاحب الدفع', email: EMAIL_RE.test(email) ? email : '', provider: PAY_PROVIDER[str(o.provider || o.gateway).toLowerCase()] || '',
             ageText: isNaN(age) ? '' : (age < 1 ? 'منذ أقل من ساعة' : 'منذ ' + hoursWord(Math.floor(age))), ageHours: isNaN(age) ? null : age,
             refundable: rule.refundable, noRefundText: rule.text, person: EMAIL_RE.test(email) ? { email: email, name: name } : null };
  }
  var STUCK_CAP = 200;
  function v2Stuck(resp, now) {
    if (!resp || !Array.isArray(resp.items)) return null;
    var rows = resp.items.filter(function (o) { return o && typeof o === 'object'; }).map(function (o) { return stuckRow(o, now); });
    rows.sort(function (a, b) { return (b.ageHours || 0) - (a.ageHours || 0); });
    // «مدفوع والتسليم ما وصلش»: المنصة بتقول صراحة `null` (مفيش علامة تسليم مسجّلة) ⇒ نكتبها «غير متاح بعد» بدل ما نسكت عنها.
    return { rows: rows, count: rows.length, partial: rows.length >= STUCK_CAP, afterHours: Number(resp.after_hours) || 2,
             deliveryNote: resp.paid_without_delivery === null ? 'دفعات تمّ سدادها ولم يصل تسليمها: غير متاح بعد' : '' };
  }
  // احتياط للوحة القرارات: طابور المنصة يحمل نفس الطلبات العالقة (بلا اسم) لو جسر التفصيل تعذّر.
  function v2StuckFromQueue(Q) {
    var s = Q && Q.stuck_card_payments;
    if (!s || !Array.isArray(s.orders)) return null;
    return v2Stuck({ items: s.orders.map(function (o) { return { order_id: o.id, kind: o.kind, amount: o.amount, currency: o.currency, created_at: o.created_at,
                                                                  buyer_email: o.user_email, provider: o.gateway }; }) }, Date.now());
  }

  // —— استردادات تنتظر القرار
  var CANCEL_BY = { member: 'صاحب الحجز', expert: 'الخبير', admin: 'الإدارة' };
  // `bridge` = رد `/api/v2/refunds/pending` (أو null)، `disputes` = `v2DisputeTickets(...).cols.refunds` (أو null). كلٌّ منهما يفشل وحده.
  function v2Refunds(bridge, disputes, now) {
    var rows = [], failed = [], more = null;
    if (bridge && Array.isArray(bridge.refunds)) {
      // المنصة تقصّ الصفحة عند حدّ ثابت (الأقدم أولًا) وتعيد `total` الكلي و`next_cursor`: لا نعرض قائمة ناقصة على أنها كاملة.
      var tot = Number(bridge.total), shown = bridge.refunds.length;
      if ((isFinite(tot) && tot > shown) || str(bridge.next_cursor)) more = { shown: shown, total: isFinite(tot) && tot > shown ? tot : null };
      bridge.refunds.forEach(function (r) {
        if (!r) return;
        var full = r.full_refund === true, who = CANCEL_BY[str(r.cancelled_by).toLowerCase()];
        var at = ms(r.cancelled_at);
        var email = str(r.member_email).toLowerCase();
        rows.push({ id: 'm|' + str(r.consultation_id), source: 'booking', title: 'استرداد بعد إلغاء حجز', amountText: moneyText(r.amount, r.currency || 'EGP'),
                    who: EMAIL_RE.test(email) ? email : 'صاحب الحجز', person: EMAIL_RE.test(email) ? { email: email, name: email } : null,
                    since: isNaN(at) ? '' : agoText(at, now), at: isNaN(at) ? Infinity : at,
                    brain: (full ? 'أُلغي الحجز بالكامل والمبلغ كله مستحق للاسترداد' : 'إلغاء متأخر: راجع المبلغ المستحق قبل الرد') + (who ? ' · طلب الإلغاء من ' + who : ''),
                    act: { do: 'escrow' }, button: 'افتح وقرّر', refundable: true });
      });
    } else failed.push('الاستردادات اليدوية');
    if (Array.isArray(disputes)) {
      disputes.forEach(function (t) {
        var rule = v2RefundRule(t.row && t.row.ef && t.row.ef.kind);
        rows.push({ id: 'd|' + t.id, source: 'dispute', title: t.title || 'دفع بلا ملف', amountText: t.amount || '', who: t.client || 'صاحب الطلب', person: null,
                    since: t.text || '', at: isFinite(t.sortAt) ? t.sortAt : Infinity, brain: t.reason || 'دُفع المبلغ ولم يصل الملف', act: { do: 'row', id: t.id },
                    button: rule.refundable ? 'افتح وقرّر' : '', noRefundText: rule.text, refundable: rule.refundable, ticket: t });
      });
    } else failed.push('الدفعات بلا ملف');
    rows.sort(function (a, b) { return a.at - b.at; });
    return { rows: rows, failed: failed, more: more };
  }

  // —— الأسعار
  function minLine(mins) { return mins.map(function (m) { return m.label + ': ' + m.amountText; }).join(' · '); }
  function v2Prices(resp) {
    if (!resp || !Array.isArray(resp.items)) return null;
    var order = Array.isArray(resp.countries) ? resp.countries : Object.keys(COUNTRY_LABEL);
    var rows = resp.items.map(function (it) {
      var mp = it.min_price && typeof it.min_price === 'object' ? it.min_price : {};
      var mins = order.filter(function (c) { return mp[c]; }).map(function (c) { return { country: c, label: COUNTRY_LABEL[c] || c, amountText: moneyText(mp[c].amount, mp[c].currency) }; });
      return { id: String(it.id), title: str(it.title) || String(it.id), visible: it.visible === true, hasPrices: it.has_prices === true, mins: mins,
               minText: mins.length ? minLine(mins) : 'لا أسعار بعد', updatedAt: it.updated_at || null };
    });
    return { rows: rows, countries: order, currencies: resp.currencies || {} };
  }
  var VERSION_LABEL = { read: 'القراءة على المنصة', pdf: 'نسخة PDF', standard: 'السعر العادي' };
  function digitsToLatin(s) {
    return String(s == null ? '' : s).replace(/[٠-٩]/g, function (d) { return String(d.charCodeAt(0) - 0x660); })
      .replace(/[۰-۹]/g, function (d) { return String(d.charCodeAt(0) - 0x6F0); });
  }
  // نص مدخل ⇒ رقم (يقبل الأرقام العربية والفاصلة العربية). فارغ ⇒ null، وغير صالح ⇒ NaN.
  function parseAmount(text) {
    var t = digitsToLatin(text).replace(/[٬,\s]/g, '').replace(/٫/g, '.').trim();
    if (t === '') return null;
    if (!/^\d+(\.\d{1,2})?$/.test(t)) return NaN;
    return Number(t);
  }
  function amountField(n) { return n == null ? '' : String(n); }
  // رد `GET /api/v2/prices/<kind>/<id>` ⇒ نموذج التعديل (نسخ × بلاد، وعملة كل بلد بجانب الخانة).
  function v2PriceForm(resp) {
    var p = resp && resp.prices;
    if (!p || typeof p !== 'object') return null;
    var countries = (Array.isArray(resp.countries) && resp.countries.length ? resp.countries : Object.keys(COUNTRY_LABEL)).map(function (c) {
      var cur = (resp.currencies && resp.currencies[c]) || '';
      return { key: c, label: COUNTRY_LABEL[c] || c, currency: cur, currencyName: curLong(cur) };
    });
    var keys = Array.isArray(resp.versions_allowed) && resp.versions_allowed.length ? resp.versions_allowed.slice() : Object.keys(p.versions || {});
    if (!keys.length) keys = [p.kind === 'course' ? 'standard' : 'read'];
    var versions = keys.map(function (k) {
      var row = (p.versions && p.versions[k]) || {}, cells = {};
      countries.forEach(function (c) { cells[c.key] = row[c.key] ? amountField(row[c.key].amount) : ''; });
      return { key: k, label: VERSION_LABEL[k] || k, cells: cells };
    });
    return { kind: p.kind || '', id: p.id, title: str(p.title) || String(p.id), visible: p.visible === true, rev: typeof p.rev === 'number' ? p.rev : 0,
             countries: countries, versions: versions, updatedBy: str(p.updated_by), updatedAt: p.updated_at || null, history: Array.isArray(p.history) ? p.history.slice(-10).reverse() : [] };
  }
  // مدخلات المستخدم ⇒ {ok, versions, visible} بالشكل اللي تقبله المنصة، أو {ok:false, error}. الخانة الفاضية = لا سعر لهذا البلد.
  function v2PriceBuild(form, input) {
    var versions = {}, err = '';
    form.versions.forEach(function (v) {
      var row = {};
      form.countries.forEach(function (c) {
        var raw = input && input.cells && input.cells[v.key] ? input.cells[v.key][c.key] : '';
        var n = parseAmount(raw);
        if (n === null) return;
        if (isNaN(n)) { if (!err) err = 'السعر في ' + c.label + ' (' + v.label + ') لازم يكون رقمًا'; return; }
        row[c.key] = { amount: n, currency: c.currency };
      });
      versions[v.key] = row;
    });
    if (err) return { ok: false, error: err };
    return { ok: true, versions: versions, visible: !!(input && input.visible) };
  }
  // before → after لكل خانة تغيّرت: [{label, from, to}] + «ظاهر للناس». `form` = v2PriceForm، `built` = v2PriceBuild.
  function v2PriceDiff(form, built) {
    var lines = [];
    form.versions.forEach(function (v) {
      form.countries.forEach(function (c) {
        var before = parseAmount(v.cells[c.key]), after = built.versions[v.key] && built.versions[v.key][c.key] ? built.versions[v.key][c.key].amount : null;
        before = before === null || isNaN(before) ? null : before;
        if (before === after) return;
        lines.push({ label: v.label + ' · ' + c.label, from: before === null ? 'لا سعر' : moneyText(before, c.currency), to: after === null ? 'لا سعر' : moneyText(after, c.currency) });
      });
    });
    if (form.visible !== built.visible) lines.push({ label: 'ظاهر للناس', from: form.visible ? 'نعم' : 'لا', to: built.visible ? 'نعم' : 'لا' });
    return { lines: lines, changed: lines.length > 0 };
  }

  // —— النسب
  var PLATFORM_FLOOR = 35, CASE_FLOOR = 25;
  function pct(n) { return ar(n) + '٪'; }
  function ladderRows(ladder) {
    var out = [], prev = 0;
    (Array.isArray(ladder) ? ladder : []).forEach(function (s, i) {
      var cap = s.max_egp, pp = numOf(s.platform_pct), upTo;
      if (cap == null) upTo = prev ? 'من ' + fmt(prev) + ' جنيه فأكثر' : 'أي قيمة';
      else upTo = i === 0 ? 'أقل من ' + fmt(cap) + ' جنيه' : 'من ' + fmt(prev) + ' إلى أقل من ' + fmt(cap) + ' جنيه';
      out.push({ upTo: upTo, platform: pp, owner: 100 - pp, platformText: pct(pp), ownerText: pct(100 - pp), max: cap == null ? null : cap });
      if (cap != null) prev = cap;
    });
    return out;
  }
  function v2SharesView(resp) {
    var t = resp && (resp.shares && typeof resp.shares === 'object' ? resp.shares : null);
    if (!t || !t.books || !t.courses || !t.cases) return null;
    var b = t.books, c = t.courses, a = t.affiliate || {};
    var lines = [
      { key: 'books', title: 'الكتب', editable: true, text: 'صاحب العمل ' + pct(b.normal.owner) + ' · المنصة ' + pct(b.normal.platform) },
      { key: 'books_ads', title: 'الكتب مع إعلانات', editable: true, text: 'صاحب العمل ' + pct(b.ads.owner) + ' · المنصة ' + pct(b.ads.platform) },
      { key: 'courses', title: 'الدورات', editable: false, text: 'صاحب الدورة يبدأ من ' + pct(c.base) + '، ويصل بكوده إلى ' + pct(c.code_max) + '، وبالإعلانات يزيد حتى ' + ar(c.ads_max_bonus) + ' نقطة، بسقف ' + pct(c.owner_cap),
        note: 'تُعدَّل في جولة الدورات' },
      { key: 'affiliate', title: 'عمولة الإحالة', editable: true, text: pct(a.rate) + ' من قيمة البيع، تُخصم من الطرفين بنسبة نصيب كلٍّ منهما' }
    ];
    return { version: typeof t.version === 'number' ? t.version : (typeof resp.version === 'number' ? resp.version : 0), lines: lines, ladder: ladderRows(t.cases.ladder),
             floors: { platform: numOf(t.platform_floor) || PLATFORM_FLOOR, cases: numOf(t.case_floor) || CASE_FLOOR },
             floorText: 'نصيب المنصة لا ينزل عن ' + pct(numOf(t.platform_floor) || PLATFORM_FLOOR) + ' في أي بيع، والقضايا ' + pct(numOf(t.case_floor) || CASE_FLOOR) + ' كحدّ أدنى',
             table: t, updatedBy: str(t.updated_by), updatedAt: t.updated_at || null };
  }
  // كل رقم قابل للقراءة بمسار: يُستعمل للمقارنة قبل/بعد (سجل التعديلات وورقة التأكيد).
  function flatShares(t) {
    var out = {};
    if (!t) return out;
    if (t.books) ['normal', 'ads'].forEach(function (k) {
      if (!t.books[k]) return;
      var n = k === 'normal' ? 'الكتب' : 'الكتب مع إعلانات';
      out['books.' + k + '.owner'] = { label: n + ' · صاحب العمل', v: pct(t.books[k].owner) };
      out['books.' + k + '.platform'] = { label: n + ' · المنصة', v: pct(t.books[k].platform) };
    });
    if (t.courses) [['base', 'الأساسية'], ['code_max', 'بالكود'], ['ads_max_bonus', 'زيادة الإعلانات'], ['owner_cap', 'السقف']].forEach(function (p) {
      if (t.courses[p[0]] != null) out['courses.' + p[0]] = { label: 'الدورات · ' + p[1], v: p[0] === 'ads_max_bonus' ? ar(t.courses[p[0]]) + ' نقطة' : pct(t.courses[p[0]]) };
    });
    var lad = ladderRows(t.cases && t.cases.ladder);
    lad.forEach(function (r, i) { out['cases.' + i] = { label: 'القضايا · ' + r.upTo, v: 'المنصة ' + r.platformText }; });
    if (t.case_floor != null) out.case_floor = { label: 'الحد الأدنى للقضايا', v: pct(t.case_floor) };
    if (t.platform_floor != null) out.platform_floor = { label: 'الحد الأدنى للمنصة', v: pct(t.platform_floor) };
    if (t.affiliate && t.affiliate.rate != null) out['affiliate.rate'] = { label: 'عمولة الإحالة', v: pct(t.affiliate.rate) };
    return out;
  }
  function v2SharesDiff(before, after) {
    var a = flatShares(before), b = flatShares(after), keys = {}, lines = [];
    Object.keys(a).concat(Object.keys(b)).forEach(function (k) { keys[k] = 1; });
    Object.keys(keys).forEach(function (k) {
      var x = a[k], y = b[k];
      if ((x && x.v) === (y && y.v)) return;
      lines.push({ label: (y || x).label, from: x ? x.v : 'لا شيء', to: y ? y.v : 'لا شيء' });
    });
    return { lines: lines, changed: lines.length > 0 };
  }
  function clone(o) { return JSON.parse(JSON.stringify(o)); }
  // مدخلات النسب ⇒ {ok, changes, after}. input = {booksOwner, booksAdsOwner, ladder:[نصيب المنصة لكل درجة], affiliateRate} (نصوص أو أرقام).
  // يُرسَل فقط ما تغيّر. ⛔ الأرضيات (٣٥ والقضايا ٢٥) تحرسها المنصة؛ هنا فقط شكل الرقم (٠–١٠٠).
  function v2SharesChanges(table, input) {
    var changes = {}, after = clone(table), err = '';
    function pctIn(v, label) {
      var n = parseAmount(v);
      if (n === null || isNaN(n) || n < 0 || n > 100) { if (!err) err = label + ' لازم يكون رقمًا بين ٠ و١٠٠'; return null; }
      return n;
    }
    function bookPlan(plan, raw, label) {
      if (raw == null || raw === '') return;
      var o = pctIn(raw, label);
      if (o == null || o === table.books[plan].owner) return;
      changes.books = changes.books || {}; changes.books[plan] = { owner: o, platform: 100 - o };
      after.books[plan] = { owner: o, platform: 100 - o };
    }
    bookPlan('normal', input.booksOwner, 'نصيب صاحب العمل في الكتب');
    bookPlan('ads', input.booksAdsOwner, 'نصيب صاحب العمل في الكتب مع إعلانات');
    if (Array.isArray(input.ladder)) {
      var lad = clone(table.cases.ladder), diff = false;
      input.ladder.forEach(function (raw, i) {
        if (!lad[i] || raw == null || raw === '') return;
        var p = pctIn(raw, 'نصيب المنصة في القضايا');
        if (p == null || p === lad[i].platform_pct) return;
        lad[i].platform_pct = p; diff = true;
      });
      if (diff) { changes.cases = { ladder: lad }; after.cases.ladder = lad; }
    }
    if (input.affiliateRate != null && input.affiliateRate !== '') {
      var r = pctIn(input.affiliateRate, 'عمولة الإحالة');
      if (r != null && r !== table.affiliate.rate) { changes.affiliate = { rate: r }; after.affiliate = Object.assign({}, table.affiliate, { rate: r }); }
    }
    if (err) return { ok: false, error: err };
    if (!Object.keys(changes).length) return { ok: false, error: 'لم تغيّر أي رقم', unchanged: true };
    return { ok: true, changes: changes, after: after };
  }
  // سجل تعديلات النسب (آخر ٢٠): من، متى، وسطور قبل ⇒ بعد.
  function v2SharesHistory(resp, now) {
    var h = resp && (resp.history || resp.log);
    if (!Array.isArray(h)) return null;
    return h.filter(function (r) { return r && typeof r === 'object'; }).map(function (r) {
      var at = ms(r.at);
      return { by: str(r.by), email: str(r.by).toLowerCase(), at: isNaN(at) ? null : at, when: isNaN(at) ? '' : dateText(new Date(at).toISOString()) + ' · ' + agoText(at, now),
               lines: v2SharesDiff(r.before, r.after).lines };
    });
  }

  // —— الحد الأدنى للسحب
  function v2MinPayout(resp, now) {
    if (!resp || typeof resp.withdraw_min !== 'number') return null;
    var al = resp.allowed && resp.allowed.withdraw_min ? resp.allowed.withdraw_min : {};
    var hist = (Array.isArray(resp.history) ? resp.history : []).filter(Boolean).map(function (r) {
      var at = ms(r.at), b = r.before && r.before.withdraw_min, a = r.after && r.after.withdraw_min;
      return { by: str(r.by), when: isNaN(at) ? '' : dateText(new Date(at).toISOString()) + ' · ' + agoText(at, now), from: b == null ? '' : moneyText(b, 'EGP'), to: a == null ? '' : moneyText(a, 'EGP') };
    });
    // ملاحظات تأثير التغيير: نصوصنا بفصحى، والمنصة بس بتقول إنها موجودة (`notes`) وبتبعت الثواني — ⛔ نصها العامي ما يُعرض.
    var nt = resp.notes && typeof resp.notes === 'object' ? resp.notes : null, notes = [];
    if (nt) {
      if (nt.agreement) notes.push('الحد الأدنى يظهر في اتفاقية المدرّبين. تغييره يغيّر نص الاتفاقية عند من وقّعها قبل ذلك أيضًا، ولا يُطلب منهم التوقيع من جديد.');
      if (nt.full_balance) notes.push('سحب الرصيد كاملًا في طلب واحد مسموح دائمًا مهما كان الحد.');
      if (nt.propagation) notes.push('يسري التعديل فورًا' + (typeof nt.cache_seconds === 'number' ? '، وقد يتأخر في بعض الحالات حتى ' + U(nt.cache_seconds, ['ثانية واحدة', 'ثانيتين', 'ثوانٍ', 'ثانية']) : '') + '.');
    }
    return { value: resp.withdraw_min, text: moneyText(resp.withdraw_min, 'EGP'), rev: typeof resp.rev === 'number' ? resp.rev : 0, notes: notes,
             min: typeof al.min === 'number' ? al.min : 50, max: typeof al.max === 'number' ? al.max : 20000, history: hist, updatedBy: str(resp.updated_by) };
  }
  function v2MinPayoutInput(text, info) {
    var n = parseAmount(text);
    if (n === null || isNaN(n) || n !== Math.floor(n)) return { ok: false, error: 'اكتب رقمًا صحيحًا بالجنيه' };
    if (n < info.min || n > info.max) return { ok: false, error: 'الحد الأدنى للسحب يكون بين ' + fmt(info.min) + ' و' + fmt(info.max) + ' جنيه' };
    return { ok: true, value: n };
  }

  // —— إعلانات الأعمال (قراءة)
  function v2AdsLedger(resp, now) {
    if (!resp || !Array.isArray(resp.items)) return null;
    var rows = resp.items.filter(Boolean).map(function (it) {
      var bal = Array.isArray(it.balance) ? it.balance.map(function (b) { return { currency: b.currency, amount: b.amount }; }) : [];
      var line = v2MoneyLine(sumByCurrency(bal)), at = ms(it.last_entry_at), email = str(it.owner_email).toLowerCase();
      return { id: String(it.owner_id), kind: str(it.owner_kind), kindText: it.owner_kind === 'course' ? 'دورة' : 'كتاب', title: str(it.title) || 'عمل بلا عنوان',
               ownerEmail: EMAIL_RE.test(email) ? email : '', balanceText: bal.length ? [line.main].concat(line.others).filter(function (x) { return x; }).join(' · ') : '٠ جنيه',
               balances: bal, last: isNaN(at) ? 'لا حركة' : agoText(at, now), at: isNaN(at) ? 0 : at, entries: Number(it.entries) || 0 };
    });
    rows.sort(function (a, b) { return b.at - a.at; });
    return rows;
  }
  var ENTRY_TEXT = { deposit: 'إيداع', spend: 'صرف على الإعلانات', refund: 'رد إلى صاحب العمل' };
  function v2AdsEntries(resp, now) {
    if (!resp || !Array.isArray(resp.entries)) return null;
    var rows = resp.entries.filter(Boolean).map(function (e) {
      var at = ms(e.at);
      return { entry: ENTRY_TEXT[e.entry] || 'حركة', amountText: moneyText(e.amount, e.currency || 'EGP'), sign: e.entry === 'deposit' ? '+' : '−', when: isNaN(at) ? '' : dateText(new Date(at).toISOString()), at: isNaN(at) ? 0 : at };
    });
    rows.sort(function (a, b) { return b.at - a.at; });
    return { rows: rows, balance: v2MoneyLine(sumByCurrency((resp.balance || []).map(function (b) { return { currency: b.currency, amount: b.amount }; }))) };
  }

  // —— الكتب: مراجعة العروض
  var OFFER_TYPE = { guide: 'دليل', book: 'كتاب', research: 'بحث', other: 'عمل' };
  var OFFER_COUNTRY = { EGP: 'eg', SAR: 'sa', AED: 'ae', KWD: 'kw', QAR: 'qa', USD: 'default' };
  // متوسط أقل سعر لكتب بلد معيّن (من قائمة الأسعار): {avg, n, currency} أو null لو أقل من كتابين بسعر في هذا البلد.
  function v2BookAverage(pricesResp, country) {
    if (!pricesResp || !Array.isArray(pricesResp.items)) return null;
    var vals = [], cur = '';
    pricesResp.items.forEach(function (it) {
      var m = it.min_price && it.min_price[country];
      if (m && numOf(m.amount) > 0 && it.visible === true) { vals.push(numOf(m.amount)); cur = m.currency; }
    });
    if (vals.length < 2) return null;
    return { avg: vals.reduce(function (a, b) { return a + b; }, 0) / vals.length, n: vals.length, currency: cur };
  }
  // سطر العقل: حقائق من حقول العرض فقط — لا حكم مخترع. لا شيء للمقارنة ⇒ سطر فاضي.
  function v2OfferLine(offer, avgByCountry) {
    var bits = [], sp = offer && offer.suggested_price;
    if (sp && numOf(sp.amount) > 0) {
      var geo = OFFER_COUNTRY[String(sp.currency).toUpperCase()], base = geo && avgByCountry ? avgByCountry[geo] : null;
      if (base && base.currency === String(sp.currency).toUpperCase() && base.avg > 0) {
        var d = Math.round((numOf(sp.amount) - base.avg) / base.avg * 100);
        var where = geo === 'default' ? 'باقي البلاد' : (COUNTRY_LABEL[geo] === 'مصر' ? 'مصر' : COUNTRY_LABEL[geo]);
        if (Math.abs(d) < 5) bits.push('السعر قريب من متوسط الكتب في ' + where);
        else bits.push('السعر ' + (d > 0 ? 'أعلى' : 'أقل') + ' من متوسط الكتب في ' + where + ' بـ' + pct(Math.abs(d)));
      }
    } else if (offer) bits.push('لم يقترح صاحب العرض سعرًا');
    var ag = offer && offer.agreement;
    if (ag && ag.platform_pct != null) bits.push('اتفاقية البيع: نصيب المنصة ' + pct(ag.platform_pct));
    else if (offer && !ag) bits.push('لم يوافق صاحب العرض على اتفاقية البيع بعد');
    return bits.join(' · ');
  }
  function v2OffersQueue(resp, pricesResp, now) {
    if (!resp || !Array.isArray(resp.offers)) return null;
    var avg = {};
    Object.keys(COUNTRY_LABEL).forEach(function (g) { avg[g] = v2BookAverage(pricesResp, g); });
    var rows = resp.offers.filter(function (o) { return o && o.id && (o.status == null || o.status === 'in_review'); }).map(function (o) {
      var sp = o.suggested_price, at = ms(o.submitted_at), email = str(o.owner_email).toLowerCase();
      return { id: String(o.id), title: str(o.title) || 'عمل بلا عنوان', about: shorten(o.about, 160), typeText: OFFER_TYPE[str(o.type)] || 'عمل',
               ownerName: str(o.owner_name) || email || 'صاحب العرض', ownerEmail: EMAIL_RE.test(email) ? email : '',
               suggestedText: sp && numOf(sp.amount) > 0 ? moneyText(sp.amount, sp.currency) : '', suggested: sp && numOf(sp.amount) > 0 ? { amount: numOf(sp.amount), currency: String(sp.currency).toUpperCase() } : null,
               brain: v2OfferLine(o, avg), since: isNaN(at) ? '' : agoText(at, now), at: isNaN(at) ? Infinity : at, agreementText: o.agreement && o.agreement.plan_label ? o.agreement.plan_label : '', offer: o };
    });
    rows.sort(function (a, b) { return a.at - b.at; });
    return rows;
  }
  // الأسعار المقترحة لورقة الاعتماد: سعر القراءة في بلد عملة العرض (إن عُرفت)، والباقي فاضٍ ليكتبه المؤسس.
  function v2OfferPrefill(row, form) {
    var cells = {};
    form.versions.forEach(function (v) { cells[v.key] = {}; form.countries.forEach(function (c) { cells[v.key][c.key] = ''; }); });
    if (row && row.suggested) {
      var geo = OFFER_COUNTRY[row.suggested.currency];
      if (geo && cells.read && cells.read[geo] != null) cells.read[geo] = amountField(row.suggested.amount);
    }
    return cells;
  }
  var REQ_TYPE = { book: 'كتاب', guide: 'دليل', research: 'بحث', other: 'غير ذلك' };
  function v2Requests(resp, now) {
    if (!resp || !Array.isArray(resp.groups)) return null;
    var byId = {};
    (Array.isArray(resp.requests) ? resp.requests : []).forEach(function (r) { if (r && r.id) byId[r.id] = r; });
    var groups = resp.groups.map(function (g) {
      var ids = Array.isArray(g.request_ids) ? g.request_ids : [], rs = ids.map(function (i) { return byId[i]; }).filter(Boolean);
      var hidden = rs.length > 0 && rs.every(function (r) { return r.hidden === true; });
      var status = rs.some(function (r) { return r.status === 'seeking'; }) ? 'seeking' : (rs.length && rs.every(function (r) { return r.status === 'fulfilled'; }) ? 'fulfilled' : 'new');
      var last = ms(g.last_at);
      return { key: str(g.key), topic: str(g.public_text) || str(g.topic), typeText: REQ_TYPE[str(g.type)] || 'غير ذلك', count: Number(g.count) || ids.length,
               countText: U(Number(g.count) || ids.length, ['طلب واحد', 'طلبان', 'طلبات', 'طلبًا']), lastText: isNaN(last) ? '' : agoText(last, now), at: isNaN(last) ? 0 : last,
               firstId: ids[0] || '', status: status, hidden: hidden };
    });
    groups.sort(function (a, b) { return b.count - a.count || b.at - a.at; });
    return { groups: groups, open: groups.filter(function (g) { return !g.hidden && g.status === 'new'; }), approved: groups.filter(function (g) { return !g.hidden && g.status === 'seeking'; }) };
  }

  // —— شارة الفلوس: تحويلات + إيصالات + دفعات عالقة + استردادات، والمجموع كما في المواصفة بالحرف. الغائب من الطابور لا يُحسب صفرًا مختلقًا.
  function v2MoneyBadge(Q) {
    if (!Q) return null;
    var parts = { payouts: qn(Q, 'wallet_payouts_pending'), receipts: qn(Q, 'manual_payments_pending'), stuck: qn(Q, 'stuck_card_payments'),
                  refunds: qn(Q, 'manual_refunds_pending') };
    return { parts: parts, total: parts.payouts + parts.receipts + parts.stuck + parts.refunds };
  }

  var api = {
    v2Tiles: v2Tiles, v2Decisions: v2Decisions, v2Card: v2Card, v2Next: v2Next, v2NextLine: v2NextLine,
    v2Health: v2Health, v2BrainLog: v2BrainLog,
    v2Tickets: v2Tickets, v2DisputeTickets: v2DisputeTickets, v2TimerText: v2TimerText, v2TimerTone: v2TimerTone, v2Person: v2Person,
    personKey: personKey, personEmailOf: personEmailOf, COLS: COLS, COL_LABEL: COL_LABEL, NA: NA,
    v2Period: v2Period, v2Income: v2Income, v2Held: v2Held, v2Owed: v2Owed, v2MoneyLine: v2MoneyLine, v2MoneyBoard: v2MoneyBoard,
    v2IncomeBars: v2IncomeBars, v2PayoutRows: v2PayoutRows, v2PayoutHistory: v2PayoutHistory, v2Stuck: v2Stuck, v2StuckFromQueue: v2StuckFromQueue,
    v2RefundRule: v2RefundRule, v2Refunds: v2Refunds, v2Prices: v2Prices, v2PriceForm: v2PriceForm, v2PriceBuild: v2PriceBuild, v2PriceDiff: v2PriceDiff,
    v2SharesView: v2SharesView, v2SharesDiff: v2SharesDiff, v2SharesChanges: v2SharesChanges, v2SharesHistory: v2SharesHistory,
    v2MinPayout: v2MinPayout, v2MinPayoutInput: v2MinPayoutInput, v2AdsLedger: v2AdsLedger, v2AdsEntries: v2AdsEntries,
    v2BookAverage: v2BookAverage, v2OfferLine: v2OfferLine, v2OffersQueue: v2OffersQueue, v2OfferPrefill: v2OfferPrefill, v2Requests: v2Requests,
    v2MoneyBadge: v2MoneyBadge, PERIODS: PERIODS, SERVICES: SERVICES, COUNTRY_LABEL: COUNTRY_LABEL,
    SECTIONS: SECTIONS, ALIASES: ALIASES, STATE_DEFAULTS: STATE_DEFAULTS, sectionFor: sectionFor, sectionHash: sectionHash,
    parseSectionHash: parseSectionHash, routeFor: routeFor, sectionByKey: secOf, tabByKey: tabOf,
    TILE_DEFS: TILE_DEFS, FAILED_TEXT: FAILED_TEXT, PARTIAL_TEXT: PARTIAL_TEXT,
    util: { ar: ar, fmt: fmt, U: U, agoText: agoText, curName: curName, moneyText: moneyText, kindOf: kindOf, pickCandidate: pickCandidate,
            dateText: dateText, durShort: durShort, parseAmount: parseAmount, curLong: curLong, sumByCurrency: sumByCurrency }
  };
  root.V2L = api;
  if (typeof module !== 'undefined' && module.exports) module.exports = api;
})(typeof window !== 'undefined' ? window : (typeof globalThis !== 'undefined' ? globalThis : this));

// ===== v2s:roles =====
/* ============================================================================
 * شاشات غير الأدمن (المدرّب · المستثمر · فريق المتابعة · الحساب بانتظار التفعيل) — الجزء النقي. ⛔ لا DOM ولا شبكة ولا ساعة خفية (`now` يُمرَّر).
 * كل مصدر مُدخَل بشكل `{state:'idle'|'loading'|'ready'|'error', data}`؛ ما ليس `ready` ⇒ `null` (لا صفر مختلق). والصفر الحقيقي يُكتب «٠».
 * ========================================================================== */
(function (root) {
  'use strict';
  var L = root.V2L;
  if (!L) return;
  var U = L.util, ar = U.ar, fmt = U.fmt, uu = U.U, moneyText = U.moneyText, dateText = U.dateText;
  var NA = 'غير متاح بعد';
  var DAY = 86400e3;

  var NAV = {
    t_home: { label: 'لوحتي', img: null, desc: 'دوراتك ومستحقاتك كما سجّلتها الإدارة' },
    t_courses: { label: 'دوراتي', img: 'courses', desc: 'الدورات المربوطة باسمك وحالة كل دورة' },
    t_earnings: { label: 'أرباحي', img: 'money', desc: 'مستحقاتك من الدورات، ومحفظتك إن كانت لك استثمارات' },
    i_home: { label: 'محفظتي', img: null, desc: 'رصيدك وما استثمرته وعوائدك' },
    i_market: { label: 'فرص الاستثمار', img: 'company', desc: 'الفرص المفتوحة الآن وما جُمع لكل فرصة' },
    i_invest: { label: 'استثماراتي', img: 'money', desc: 'كل استثمار باسمك وحالته' },
    users: { label: 'الأعضاء', img: 'people', desc: 'أعضاء المنصة للاطلاع فقط' },
    courses: { label: 'الدورات', img: 'courses', desc: 'دورات المنصة وحالتها للاطلاع فقط' },
    topics: { label: 'الموضوعات', img: 'content', desc: 'موضوعات المنصة وحالتها للاطلاع فقط' },
    tutorials: { label: 'دليل الاستخدام', img: 'books', desc: 'شروحات المنصة كما يراها الأعضاء' },
    v_pending: { label: 'حسابك', img: null, desc: '' }
  };
  var ROLE_SUB = { trainer: 'لوحة المدرّب', investor: 'لوحة المستثمر', employee: 'فريق المتابعة', viewer: 'حسابك' };
  var ROLE_LINE = { trainer: 'مدرّب', investor: 'مستثمر', employee: 'فريق المتابعة · للاطلاع فقط', viewer: 'بانتظار التفعيل' };
  var COUNT = {
    course: ['دورة واحدة', 'دورتان', 'دورات', 'دورة'],
    opp: ['فرصة واحدة', 'فرصتان', 'فرص', 'فرصة'],
    invest: ['استثمار واحد', 'استثماران', 'استثمارات', 'استثمارًا'],
    member: ['عضو واحد', 'عضوان', 'أعضاء', 'عضوًا'],
    request: ['طلب واحد', 'طلبان', 'طلبات', 'طلبًا'],
    topic: ['موضوع واحد', 'موضوعان', 'موضوعات', 'موضوعًا'],
    badge: ['شارة واحدة', 'شارتان', 'شارات', 'شارة']
  };
  var LEVELS = { bronze: 'برونزي', silver: 'فضي', gold: 'ذهبي', platinum: 'بلاتيني' };

  // ------------------------------------------------------------------ أدوات
  function str(v) { return typeof v === 'string' ? v.trim() : ''; }
  function num(v) { var n = Number(v); return isFinite(n) ? n : 0; }
  function isNum(v) { return typeof v === 'number' && isFinite(v); }
  function ready(s) { return !!s && s.state === 'ready'; }
  function list(d, key) {
    if (Array.isArray(d)) return d;
    if (d && Array.isArray(d[key])) return d[key];
    return [];
  }
  function ms(iso) { var t = Date.parse(iso || ''); return isNaN(t) ? NaN : t; }
  function arDigits(s) {
    return String(s == null ? '' : s).replace(/[0-9]/g, function (d) { return '٠١٢٣٤٥٦٧٨٩'.charAt(+d); });
  }
  function toLatin(s) {
    return String(s == null ? '' : s).replace(/[٠-٩]/g, function (d) { return String('٠١٢٣٤٥٦٧٨٩'.indexOf(d)); })
      .replace(/[۰-۹]/g, function (d) { return String('۰۱۲۳۴۵۶۷۸۹'.indexOf(d)); });
  }
  function greeting(user) {
    var n = str(user && user.name);
    if (n && n.indexOf('@') > -1) n = '';
    return n ? 'أهلًا، ' + n : 'أهلًا بك';
  }
  function navFor(role, base, perms) {
    var b = (base || []).slice();
    var p = perms;
    if (typeof p === 'string') { try { p = JSON.parse(p); } catch (e) { p = null; } }
    var ids = b;
    if (p && typeof p === 'object') {
      var entry = p[role];
      var mods = entry && (entry.modules || entry);
      if (Array.isArray(mods)) ids = b.filter(function (id) { return mods.indexOf(id) > -1; });
    }
    return ids.filter(function (id) { return NAV[id]; }).map(function (id) {
      return { id: id, label: NAV[id].label, img: NAV[id].img, desc: NAV[id].desc };
    });
  }

  // ------------------------------------------------------------------ المدرّب
  var COURSE_CHIP = { active: { t: 'مفتوحة', tone: 'green' }, draft: { t: 'مسودة', tone: 'grey' }, completed: { t: 'انتهت', tone: 'wine' },
                      archived: { t: 'مؤرشفة', tone: 'grey' } };
  function courseRow(c) {
    c = c || {};
    var chip = COURSE_CHIP[c.status] || { t: 'غير معروفة', tone: 'grey' };
    var price = num(c.price_egp) > 0 ? fmt(c.price_egp) + ' جنيه' : (num(c.price_usd) > 0 ? fmt(c.price_usd) + ' دولار' : 'مجانية');
    var meta = ['المسجّلون: ' + ar(c.students_count), price];
    var sd = dateText(c.start_date);
    if (sd) meta.push('تبدأ ' + sd);
    var pc = num(c.revenue_split && c.revenue_split.trainer_percent);
    return { title: str(c.title) || 'دورة', chip: { t: chip.t, tone: chip.tone }, meta: meta.join(' · '),
             share: 'نصيبك من الدورة: ' + (pc > 0 ? fmt(pc) + '٪' : 'غير محدد بعد') };
  }
  function payBucket(p) { var s = p && p.status; return s === 'paid' ? 'paid' : (s === 'waived' ? 'waived' : 'due'); }
  function sumPay(rows, pred) {
    var t = 0;
    rows.forEach(function (p) { if (pred(p)) t += num(p.total_egp); });
    return t;
  }
  function trainerNext(src, nums, linked) {
    if (nums.due != null && nums.due > 0) {
      return { text: 'لك في دفتر الإدارة ' + fmt(nums.due) + ' جنيه لم تُحوَّل بعد.', link: { label: 'التفاصيل', go: 't_earnings' } };
    }
    if (ready(src.courses) && list(src.courses.data).length === 0 && linked === true) {
      return { text: 'لا توجد دورات مربوطة بحسابك بعد. تواصل مع الإدارة لربط دوراتك.', link: null };
    }
    return null;
  }
  function trainerView(src, now) {
    src = src || {};
    var linked = ready(src.me) ? (src.me.data && src.me.data.linked !== false) : null;
    if (ready(src.me) && src.me.data && src.me.data.linked === false) linked = false;
    var unl = linked === false;
    var cs = ready(src.courses) ? list(src.courses.data) : null;
    var ps = ready(src.payouts) ? list(src.payouts.data) : null;
    var nums = {
      courses: unl || !cs ? null : cs.length,
      students: unl || !cs ? null : cs.reduce(function (t, c) { return t + num(c.students_count); }, 0),
      due: unl || !ps ? null : sumPay(ps, function (p) { return payBucket(p) === 'due'; })
    };
    return { linked: linked, nums: nums, rows: cs ? cs.map(courseRow) : [], next: unl ? null : trainerNext(src, nums, linked) };
  }

  var PAY_CHIP = { due: { t: 'مستحق', tone: 'amber' }, paid: { t: 'حُوّل', tone: 'green' }, waived: { t: 'أُسقط', tone: 'grey' } };
  var WD_MIN_USD = 50;
  function walletRate(w) {
    var pairs = [['balance_egp', 'balance'], ['total_invested_egp', 'total_invested'], ['total_returns_egp', 'total_returns']];
    for (var i = 0; i < pairs.length; i++) {
      var e = num(w[pairs[i][0]]), d = num(w[pairs[i][1]]);
      if (e !== 0 && d !== 0) return e / d;
    }
    return null;
  }
  function walletView(w) {
    if (!w || typeof w !== 'object') return null;
    if (w.id == null) return { linked: false };
    var rate = walletRate(w);
    var bal = num(w.balance_egp);
    var pend = num(w.pending_withdrawals);
    var pending;
    if (pend === 0) pending = { value: '٠ جنيه', note: 'لا طلبات قيد المراجعة' };
    else if (rate) pending = { value: 'نحو ' + fmt(Math.round(pend * rate)) + ' جنيه', note: moneyText(pend, 'USD') + ' · تراجعه الإدارة' };
    else pending = { value: moneyText(pend, 'USD'), note: 'تراجعه الإدارة' };
    return {
      linked: true, rate: rate, balanceEgp: bal, investedEgp: num(w.total_invested_egp), returnsEgp: num(w.total_returns_egp),
      pending: pending, pendingUsd: pend, level: LEVELS[w.level] || str(w.level) || LEVELS.bronze, canWithdraw: bal > 0,
      minEgp: rate ? Math.round(WD_MIN_USD * rate) : null
    };
  }
  function trainerEarnings(src, now) {
    src = src || {};
    var ps = ready(src.payouts) ? list(src.payouts.data) : null;
    var out = { due: null, paid: null, last30: null, list: [], wallet: null, activeRows: [] };
    if (ps) {
      out.due = sumPay(ps, function (p) { return payBucket(p) === 'due'; });
      out.paid = sumPay(ps, function (p) { return payBucket(p) === 'paid'; });
      out.last30 = sumPay(ps, function (p) {
        if (payBucket(p) === 'waived') return false;
        var t = ms(p.date);
        return !isNaN(t) && t <= (now || 0) + DAY && (now || 0) - t <= 30 * DAY;
      });
      out.list = ps.slice().sort(function (a, b) { return (ms(b.date) || 0) - (ms(a.date) || 0); }).map(function (p) {
        var ch = PAY_CHIP[payBucket(p)];
        return { title: str(p.related_to) || 'مستحق', date: dateText(p.date), amountText: fmt(p.total_egp) + ' جنيه', chip: { t: ch.t, tone: ch.tone } };
      });
    }
    out.wallet = ready(src.wallet) ? walletView(src.wallet.data) : null;
    if (ready(src.active)) out.activeRows = list(src.active.data).map(function (x) { return investmentRow(x, 'active'); });
    return out;
  }

  // ------------------------------------------------------------------ المستثمر
  function openOppCount(opps) {
    return list(opps).filter(function (o) { return ['open', 'hot', 'invite_only'].indexOf(o.status) > -1; }).length;
  }
  function investorNext(src) {
    src = src || {};
    if (ready(src.wallet)) {
      var w = walletView(src.wallet.data);
      if (w && w.linked) {
        if (w.pendingUsd > 0) {
          var t = w.rate ? 'طلب سحب بقيمة نحو ' + fmt(Math.round(w.pendingUsd * w.rate)) + ' جنيه (' + moneyText(w.pendingUsd, 'USD') + ') قيد المراجعة لدى الإدارة.'
                         : 'طلب سحب بقيمة ' + moneyText(w.pendingUsd, 'USD') + ' قيد المراجعة لدى الإدارة.';
          return { text: t, link: null };
        }
        if (w.balanceEgp > 0) return { text: 'لك ' + fmt(w.balanceEgp) + ' جنيه متاحة للسحب.', link: { label: 'اطلب السحب', act: 'withdraw' } };
      }
    }
    if (ready(src.opps)) {
      var n = openOppCount(src.opps.data);
      if (n > 0) return { text: 'الفرص المفتوحة الآن: ' + uu(n, COUNT.opp) + '.', link: { label: 'اعرضها', go: 'i_market' } };
    }
    return null;
  }
  var OPP_CHIP = { open: { t: 'مفتوحة', tone: 'green' }, hot: { t: 'إقبال مرتفع', tone: 'wine' }, invite_only: { t: 'بدعوة', tone: 'amber' },
                   funded: { t: 'اكتمل التمويل', tone: 'grey' } };
  function oppCard(o) {
    o = o || {};
    var target = num(o.target_amount), funded = num(o.current_funded);
    var pct = Math.max(0, Math.min(100, num(o.funding_percent)));
    var showBar = target > 0;
    var ch = OPP_CHIP[o.status] || { t: 'غير معروفة', tone: 'grey' };
    var roi = num(o.expected_roi), min = num(o.min_investment);
    return {
      title: str(o.course_title) || 'فرصة استثمار', trainer: str(o.trainer_name), students: ar(o.students_count),
      fundedText: moneyText(funded, 'USD'), targetText: showBar ? moneyText(target, 'USD') : '', pct: pct, showBar: showBar,
      progressText: showBar ? 'جُمع ' + moneyText(funded, 'USD') + ' من ' + moneyText(target, 'USD') + ' · ' + ar(pct) + '٪'
                            : 'جُمع ' + moneyText(funded, 'USD') + ' · الهدف غير محدد بعد',
      roiText: roi > 0 ? fmt(roi) + '٪' : 'غير محدد بعد', roiNote: roi > 0 ? 'رقم تقديري حدّدته الإدارة' : '',
      minText: min > 0 ? moneyText(min, 'USD') : 'غير محدد بعد',
      start: dateText(o.expected_start), end: dateText(o.expected_end), chip: { t: ch.t, tone: ch.tone }
    };
  }
  var INV_CHIP = { active: { t: 'جارٍ', tone: 'green' }, pending: { t: 'بانتظار', tone: 'amber' }, accrued: { t: 'قيد الاحتساب', tone: 'amber' },
                   completed: { t: 'مكتمل', tone: 'wine' }, paid: { t: 'صُرف', tone: 'green' }, loss: { t: 'خسارة', tone: 'red' } };
  function investmentRow(x, tab) {
    x = x || {};
    var title = str(x.course_title);
    var ch = INV_CHIP[x.status] || { t: 'غير معروفة', tone: 'grey' };
    var meta = ['استثمرت ' + fmt(x.invested_total_egp) + ' جنيه'];
    var d = dateText(x.created_at);
    if (d) meta.push(d);
    var out = { title: title || 'استثمار', meta: meta.join(' · '), chip: { t: ch.t, tone: ch.tone }, second: 'العائد: ' + NA, actual: '' };
    if (title) {
      // -١٠٠٪ بالحساب يعني «لم يُسجَّل عائد بعد» (عائد صفر) لا خسارة حقيقية: لا نحكم بخسارة إلا لو حالتها «خسارة».
      // أي نسبة سالبة تُكتب كلمة «خسارة» لا شرطة قبل الأرقام (الشرطة تنقلب اتجاهها في السطر العربي).
      var roi = Number(x.roi_percent);
      if (x.roi_percent == null || x.roi_percent === '' || !isFinite(roi)) out.second = 'العائد: ' + NA;
      else if (roi < 0) out.second = (roi <= -100 && x.status !== 'loss') ? 'العائد: ' + NA : 'العائد المحسوب حتى الآن: خسارة ' + fmt(-roi) + '٪';
      else out.second = 'العائد المحسوب حتى الآن: ' + fmt(roi) + '٪';
    }
    if (tab === 'history' && num(x.actual_return) > 0) out.actual = 'العائد الفعلي: ' + moneyText(x.actual_return, 'USD');
    return out;
  }
  function badgesView(b) {
    if (!b) return null;
    var rows = list(b);
    var earned = rows.filter(function (x) { return x.earned; });
    return { earned: earned.map(function (x) { return str(x.label) || 'شارة'; }), line: 'الشارات: ' + ar(earned.length) + ' من ' + ar(rows.length) };
  }
  function withdrawCheck(input, wallet) {
    var bad = { ok: false, error: 'اكتب مبلغًا صحيحًا لا يزيد على رصيدك المتاح.' };
    var s = toLatin(str(input)).replace(/[\s,٬]/g, '');
    if (!/^\d+$/.test(s)) return bad;
    var n = Number(s);
    var max = Math.floor(num(wallet && (wallet.balanceEgp != null ? wallet.balanceEgp : wallet.balance_egp)));
    if (!(n > 0) || n > max) return bad;
    return { ok: true, amount: n };
  }

  // ------------------------------------------------------------------ فريق المتابعة
  var PLAN = { free: 'مجانية', pro: 'احترافية', premium: 'بريميوم' };
  function peopleRows(d) { return list(d, 'users'); }
  function peopleFilter(rows, chip, q) {
    var needle = str(q).toLowerCase();
    return (rows || []).filter(function (u) {
      if (chip === 'trainer' && u.trainer_status !== 'approved') return false;
      if (chip === 'pending' && u.trainer_status !== 'pending') return false;
      if (chip === 'admin' && ['admin', 'staff'].indexOf(u.role) < 0) return false;
      if (chip === 'investor' && u.role !== 'investor') return false;
      if (chip === 'test' && !u.is_test) return false;
      if (!needle) return true;
      return [u.full_name, u.name, u.email, u.phone].some(function (f) { return String(f || '').toLowerCase().indexOf(needle) > -1; });
    });
  }
  function peopleCounts(rows) {
    var c = { all: 0, trainer: 0, pending: 0, admin: 0, investor: 0, test: 0 };
    (rows || []).forEach(function (u) {
      c.all++;
      if (u.trainer_status === 'approved') c.trainer++;
      if (u.trainer_status === 'pending') c.pending++;
      if (u.role === 'admin' || u.role === 'staff') c.admin++;
      if (u.role === 'investor') c.investor++;
      if (u.is_test) c.test++;
    });
    return c;
  }
  function peopleCapped(reply) {
    var users = peopleRows(reply), count = num(reply && reply.count);
    var capped = count > users.length;
    return { capped: capped, count: count,
             note: capped ? 'المعروض أحدث ' + ar(users.length) + ' من ' + uu(count, COUNT.member) + '؛ ابحث بالاسم أو البريد لعرض غيرهم.' : '' };
  }
  function personRow(u, segLabels) {
    u = u || {};
    var name = str(u.full_name) || str(u.name) || str(u.email) || 'عضو';
    var chips = [];
    var roleChip = u.role === 'admin' ? 'إدارة' : (u.role === 'staff' ? 'فريق' : (u.role === 'investor' ? 'مستثمر' : 'عضو'));
    chips.push({ t: roleChip, tone: 'grey' });
    if (u.trainer_status === 'approved') chips.push({ t: 'مدرّب', tone: 'green' });
    else if (u.trainer_status === 'pending') chips.push({ t: 'طلب تدريب', tone: 'amber' });
    if (u.is_test) chips.push({ t: 'تجريبي', tone: 'grey' });
    var meta = [];
    var j = dateText(u.created_at);
    if (j) meta.push('انضم ' + j);
    var plan = str(u.plan_id);
    if (plan) meta.push(PLAN[plan] || plan);
    var seg = str(u.segment);
    var pub = u.public_ready;
    return {
      name: name, email: str(u.email), initial: name.charAt(0) || '—', chips: chips, meta: meta.join(' · '),
      details: [
        { k: 'الهاتف', v: str(u.phone) || '—' },
        { k: 'الفئة', v: seg ? ((segLabels && segLabels[seg]) || seg) : '—' },
        { k: 'الوسوم', v: Array.isArray(u.tags) && u.tags.length ? u.tags.map(str).filter(Boolean) : [] },
        { k: 'يظهر في الدليل العام', v: pub === true ? 'نعم' : (pub === false ? 'لا' : NA) }
      ]
    };
  }
  var TYPE_AR = { recorded_paid: 'مسجّلة مدفوعة', recorded_free: 'مسجّلة مجانية', live_upcoming: 'مباشرة' };
  function courseKind(c) {
    c = c || {};
    if (c.approval_status === 'pending') return 'pending';
    if (c.approval_status === 'rejected') return 'rejected';
    if (!c.is_active && c.archived_at) return 'archived';
    return c.is_active ? 'published' : 'draft';
  }
  var KIND_CHIP = { pending: { t: 'بانتظار الاعتماد', tone: 'amber' }, rejected: { t: 'مرفوضة', tone: 'red' }, archived: { t: 'مؤرشفة', tone: 'grey' },
                    published: { t: 'منشورة', tone: 'green' }, draft: { t: 'مسودة', tone: 'grey' } };
  function courseStatus(c) { var k = KIND_CHIP[courseKind(c)]; return { t: k.t, tone: k.tone }; }
  function pcourseRow(c) {
    c = c || {};
    var price = num(c.price_amount) > 0 ? moneyText(c.price_amount, c.price_currency) : (c.type === 'recorded_free' ? 'مجانية' : '—');
    var lessons = c.story && num(c.story.lessons) > 0 ? c.story.lessons : c.lesson_count;
    var meta = [str(c.instructor_name) || 'بلا مدرّب', TYPE_AR[c.type] || str(c.type), price, 'المسجّلون: ' + ar(c.total_enrolled), 'الدروس: ' + ar(lessons)];
    return { title: str(c.title) || 'دورة', chip: courseStatus(c), meta: meta.filter(Boolean).join(' · '), kind: courseKind(c) };
  }
  function pcourseFilter(rows, chip) {
    return (rows || []).filter(function (c) {
      var k = courseKind(c);
      if (chip === 'published') return k === 'published';
      if (chip === 'pending') return k === 'pending';
      if (chip === 'draft') return k === 'draft';
      return true;
    });
  }
  function pcourseCounts(rows) {
    var c = { all: 0, published: 0, pending: 0, draft: 0 };
    (rows || []).forEach(function (x) { c.all++; var k = courseKind(x); if (c[k] != null) c[k]++; });
    return c;
  }
  var TOPIC_STATUS = { published: ['منشور', 'green'], open: ['على البورد', 'green'], merged: ['قيد العمل', 'amber'], pending_review: ['بانتظار المراجعة', 'amber'],
                       rejected: ['مرفوض', 'red'], archived: ['مؤرشف', 'grey'], draft: ['مسودة', 'grey'] };
  var TOPIC_SRC = { news: 'خبر', expert: 'خبير', idea: 'فكرة', human: 'عضو' };
  function topicKey(t) { return TOPIC_STATUS[t && t.status] ? t.status : 'draft'; }
  function topicRow(t) {
    t = t || {};
    var st = TOPIC_STATUS[topicKey(t)];
    var meta = [];
    if (TOPIC_SRC[t.source]) meta.push(TOPIC_SRC[t.source]);
    if (str(t.category)) meta.push(str(t.category));
    var eng = [];
    if (isNum(t.comments)) eng.push('التعليقات: ' + ar(t.comments));
    if (isNum(t.reactions)) eng.push('التفاعلات: ' + ar(t.reactions));
    if (eng.length) meta.push(eng.join(' · '));
    var d = dateText(t.created_at || t.published_at || t.date);
    if (d) meta.push(d);
    var sum = str(t.summary);
    if (sum.length > 600) sum = sum.slice(0, 600) + '…';
    return { title: str(t.title) || str(t.question) || 'موضوع', chip: { t: st[0], tone: st[1] }, meta: meta.join(' · '), summary: sum, key: topicKey(t) };
  }
  function topicCounts(rows) {
    var c = { all: 0, published: 0, open: 0, merged: 0, pending_review: 0, draft: 0, rejected: 0, archived: 0 };
    (rows || []).forEach(function (t) { c.all++; c[topicKey(t)]++; });
    return c;
  }
  function topicFilter(rows, chip) {
    return (rows || []).filter(function (t) { return chip === 'all' || topicKey(t) === chip; });
  }
  function tutorialGroups(rows) {
    var items = list(rows, 'tutorials').slice();
    items.sort(function (a, b) { return num(a.order) - num(b.order); });
    var groups = [], idx = {};
    items.forEach(function (t) {
      var s = str(t.section) || 'عام';
      if (idx[s] == null) { idx[s] = groups.length; groups.push({ section: s, items: [] }); }
      groups[idx[s]].items.push({
        title: str(t.title) || 'شرح', published: t.published !== false && t.status !== 'draft' && t.is_published !== false,
        body: String(t.body == null ? (t.content == null ? '' : t.content) : t.body), video: str(t.video_url)
      });
    });
    return groups;
  }
  function staffNext(screen, src) {
    src = src || {};
    if (screen === 'users' && ready(src.people)) {
      var n = peopleCounts(peopleRows(src.people.data)).pending;
      if (n > 0) return { text: 'طلبات تدريب قيد المراجعة لدى الإدارة: ' + uu(n, COUNT.request) + '.', link: null };
    }
    if (screen === 'courses' && ready(src.pcourses)) {
      var m = pcourseCounts(list(src.pcourses.data, 'courses')).pending;
      if (m > 0) return { text: 'بانتظار اعتماد الإدارة: ' + uu(m, COUNT.course) + '.', link: null };
    }
    if (screen === 'topics' && ready(src.topics)) {
      var k = topicCounts(list(src.topics.data, 'topics')).pending_review;
      if (k > 0) return { text: 'مقترحات من الأعضاء بانتظار المراجعة: ' + uu(k, COUNT.topic) + '.', link: null };
    }
    return null;
  }

  L.roles = {
    NAV: NAV, COUNT: COUNT, ROLE_SUB: ROLE_SUB, ROLE_LINE: ROLE_LINE, NA: NA,
    arDigits: arDigits, greeting: greeting, navFor: navFor, trainerView: trainerView, trainerEarnings: trainerEarnings, courseRow: courseRow,
    walletView: walletView, investorNext: investorNext, openOppCount: openOppCount, oppCard: oppCard, investmentRow: investmentRow,
    badgesView: badgesView, withdrawCheck: withdrawCheck, peopleRows: peopleRows, peopleFilter: peopleFilter, peopleCounts: peopleCounts,
    peopleCapped: peopleCapped, personRow: personRow, courseStatus: courseStatus, courseKind: courseKind, pcourseRow: pcourseRow,
    pcourseFilter: pcourseFilter, pcourseCounts: pcourseCounts, topicRow: topicRow, topicCounts: topicCounts, topicFilter: topicFilter,
    tutorialGroups: tutorialGroups, staffNext: staffNext
  };
  if (typeof module !== 'undefined' && module.exports) module.exports.roles = L.roles;
})(typeof window !== 'undefined' ? window : (typeof globalThis !== 'undefined' ? globalThis : this));
// ===== /v2s:roles =====
