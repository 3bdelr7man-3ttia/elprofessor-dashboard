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

    // —— الفلوس
    (function (t) {
      t.dest = 'finance'; t.land = 'wallet_payouts_pending';
      if (!Q) return failTile(t);
      var po = qn(Q, 'wallet_payouts_pending'), mp = qn(Q, 'manual_payments_pending');
      var st = qn(Q, 'stuck_card_payments'), sp = qn(Q, 'course_split_pending');
      t.count = po + mp + st + sp; t.hot = st > 0;
      var p = [];
      if (po) p.push(U(po, ['تحويل واحد', 'تحويلان', 'تحويلات', 'تحويلًا']));
      if (mp) p.push(U(mp, ['إيصال', 'إيصالان', 'إيصالات', 'إيصالًا']));
      if (st) p.push(U(st, ['دفعة عالقة', 'دفعتان عالقتان', 'دفعات عالقة', 'دفعة عالقة']));
      if (sp) p.push(ar(sp) + ' اقتسام معلّق');
      t.next = p.length ? p.join(' · ') : 'التحويلات والإيصالات';
      if (st) { t.dest = 'finance'; t.land = 'stuck_card_payments'; }
      else if (po) { t.dest = 'finance'; t.land = 'wallet_payouts_pending'; }
      else if (sp) { t.dest = 'finance'; t.land = 'course_split_pending'; }
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
    payout: 'money', manual_payment: 'money',
    trainer: 'people', join: 'people', pending_user: 'people', founding: 'people', lead: 'people', message: 'people', open_message: 'people',
    book: 'books', program: 'courses', course: 'courses', live: 'courses', topic: 'content', creative: 'content', other: 'people'
  };
  // الترتيب (قرار المؤسس): ملفات مستعجلة/متأخرة ⇐ نزاعات ⇐ استردادات ⇐ تحويلات ⇐ إيصالات ⇐ آراء للمراجعة ⇐
  // مدرّبون وانضمام ⇐ زوّار ⇐ خبراء مؤسسون ⇐ محتوى وكتب وبرامج ⇐ رسائل. الملف العادي المنتظر بين الأولى والثانية.
  var RANK = { file_urgent: 10, file_waiting: 15, dispute: 20, refund: 30, payout: 40, manual_payment: 50, review: 60,
               trainer: 70, join: 70, pending_user: 80, founding: 90, content: 100, message: 110 };

  function kindOf(r) {
    if (!r) return null;
    if (r.apiKind === 'payout' || r.kind === 'payout') return 'payout';
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
          card.brain = (r.efLane === 'late' ? 'متأخر ' + hoursWord(h) + ' عند ' + cur : 'لم يستلمه ' + cur + ' منذ ' + hoursWord(h))
            + (cand ? '. أقترح نقله إلى ' + cand.name : '. لا يوجد خبير آخر متاح');
        } else if (!pre && f.status === 'assigned') {
          card.brain = 'أُرسل إلى ' + cur + ' ولم يستلمه بعد' + (cand ? '. أقترح نقله إلى ' + cand.name : '. لا يوجد خبير آخر متاح');
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
    return card;
  }
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

  var api = {
    v2Tiles: v2Tiles, v2Decisions: v2Decisions, v2Card: v2Card, v2Next: v2Next, v2NextLine: v2NextLine,
    v2Health: v2Health, v2BrainLog: v2BrainLog,
    TILE_DEFS: TILE_DEFS, FAILED_TEXT: FAILED_TEXT, PARTIAL_TEXT: PARTIAL_TEXT,
    util: { ar: ar, fmt: fmt, U: U, agoText: agoText, curName: curName, moneyText: moneyText, kindOf: kindOf, pickCandidate: pickCandidate }
  };
  root.V2L = api;
  if (typeof module !== 'undefined' && module.exports) module.exports = api;
})(typeof window !== 'undefined' ? window : (typeof globalThis !== 'undefined' ? globalThis : this));
