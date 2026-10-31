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

  var CUR_NAME = { EGP: 'جنيه', USD: 'دولار', SAR: 'ريال', EUR: 'يورو', AED: 'درهم', GBP: 'جنيه إسترليني', KWD: 'دينار', QAR: 'ريال', BHD: 'دينار', OMR: 'ريال' };
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
  var FAILED_TEXT = 'تعذّر الوصول';

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

    // —— المحتوى (بنفس كلمات لوحة «خط النشر»؛ الطابور لا يحمل غير هذين العددين)
    (function (t) {
      t.dest = 'topics'; t.land = 'topics_drafts';
      if (!Q) return failTile(t);
      // الشارة تعدّ ما ينتظر قرارًا فقط (موضوعات الأعضاء · آراء المتعلّمين · التعليقات · الأعمال) كأعمدة «ينتظرك»؛
      // مسودات الأفكار أرشيف يُذكر نصًّا في السطر ولا يدخل العدّاد (٣١١ فكرة ليست ٣١١ قرارًا).
      var d = qn(Q, 'topics_drafts'), s = qn(Q, 'testimonials_pending'), tp = qn(Q, 'topics_pending_review'), op = qn(Q, 'opinions_pending'), cr = qn(Q, 'creative_pending');
      t.count = tp + s + op + cr;
      var p = [];
      if (tp) p.push(U(tp, ['موضوع من عضو', 'موضوعان من أعضاء', 'موضوعات من أعضاء', 'موضوعًا من أعضاء']));
      if (s) p.push(U(s, ['رأي متعلّم واحد', 'رأيان لمتعلّمَين', 'آراء متعلّمين', 'رأيًا لمتعلّمين']));
      if (op) p.push(U(op, ['تعليق', 'تعليقان', 'تعليقات', 'تعليقًا']));
      if (cr) p.push(U(cr, ['عمل إبداعي', 'عملان إبداعيان', 'أعمال إبداعية', 'عملًا إبداعيًا']));
      if (d) p.push(U(d, ['فكرة في الأرشيف', 'فكرتان في الأرشيف', 'أفكار في الأرشيف', 'فكرة في الأرشيف']));
      t.next = p.length ? p.join(' · ') : 'خط النشر';
      t.land = 'topics_drafts';
    })(T.content);

    // —— بلا رقم في D1
    T.marketing.dest = 'marketing'; T.marketing.next = 'الحملات والسوشيال';
    T.reports.dest = 'analysis'; T.reports.next = 'شغّال · واقف · فرصة';
    T.company.dest = 'investment'; T.company.next = 'الشركاء والمعدات والإعدادات';

    // —— العقل: ما وزّعه اليوم من صفوف الوارد.
    (function (t) {
      t.dest = 'brain'; t.internal = true;
      // v2s:brain — الرقم الواحد للمربّع والقائمة والشاشة: لو جاء من سجل اليوم الكامل (عدد) نستعمله، وفشله (null) فشل للمربّع،
      // وغيابه (undefined) يبقي العدّ القديم من صفوف الوارد. ⛔ لا حساب ثانٍ.
      var n, fromLog = typeof extras.brainToday === 'number';
      if (fromLog) n = extras.brainToday;
      else if (extras.brainToday === null) return failTile(t);
      else { if (!rows) return failTile(t); n = v2BrainLog(rows, now).length; }
      t.count = n;
      t.next = n ? 'وزّع ' + U(n, ['ملفًا واحدًا', 'ملفين', 'ملفات', 'ملفًا']) + ' وحده اليوم' : 'لم يوزّع شيئًا اليوم';
      if (fromLog ? extras.brainTodayPartial === true : hasTrunc(extras)) markPartial(t);
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
    if (r.apiKind === 'brain_item') return 'brain_item';       // brain2: اقتراح كتبه العقل (يُبنى بـv2bItemCard)
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
      case 'brain_item': {
        // brain2: البطاقة جاهزة من `v2bItemCard` (آخر الملف). ما فيها صف وارد ولا شخص.
        var mk = root.V2L && root.V2L.v2bItemCard;
        return (mk && r.item) ? mk(r.item, now) : null;
      }
      case 'file_waiting': case 'file_late': {
        var late = kind === 'file_late';
        var pre = f.status === 'awaiting_assignment';
        var cand = pickCandidate(f.candidates || r.candidates, f);
        card.tag = late ? 'ملف متأخر' : 'ملف ينتظر خبيرًا';
        card.title = str(f.title) || 'ملف';
        card.sub = clean([who && ('صاحب الطلب: ' + who), str(f.law_label), amountLabel]).join(' · ');
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
        card.sub = clean([who && ('صاحب الطلب: ' + who), amountLabel]).join(' · ');
        card.brain = 'أموال هذا الملف لم تتحرك وحدها وتحتاج تدخّلك';
        card.reason = 'القرار هنا يخص الأموال، فيُفتح الملف للمراجعة أولًا';
        card.primary = { label: 'افتح وراجع', act: OPEN };
        break;
      }
      case 'review': {
        card.tag = 'أول رأي لخبير جديد';
        card.title = str(f.title) || 'رأي ينتظر المراجعة';
        card.sub = clean([who && ('صاحب الطلب: ' + who), amountLabel]).join(' · ');
        card.brain = 'رأي ' + (str(f.expert_name) || 'الخبير') + ' في «' + (str(f.title) || 'الملف') + '» ينتظر مراجعتك';
        card.reason = 'صاحب الطلب ينتظر؛ لا يصله الرأي قبل موافقتك';
        card.primary = { label: 'افتح وراجع', act: OPEN };
        break;
      }
      case 'dispute': {
        var isCase = r.efLane === 'case_disputed' || r.dsrc === 'case';
        card.tag = isCase ? 'ملاحظة على قضية' : 'نزاع';
        card.title = str(f.title) || str(c.title) || 'نزاع';
        card.sub = clean([(str(f.expert_name) || str(c.expert_name)) && ('الخبير: ' + (str(f.expert_name) || str(c.expert_name)))]).join(' · ');
        card.brain = 'اعتراض من ' + (who || 'صاحب الطلب') + ' على ' + (card.title ? '«' + card.title + '»' : 'الخدمة') + (amountLabel ? ' · ' + amountLabel : '');
        card.reason = 'الأموال محجوزة لحين قرارك، والحسم من صفحة البند بعد قراءة الرأيين';
        card.primary = { label: 'افتح النزاع', act: OPEN };
        break;
      }
      case 'unactivated': {
        card.tag = 'دفع بلا ملف';
        card.title = str(f.title) || 'دفعة لم يصل ملفها';
        card.sub = who ? 'صاحب الطلب: ' + who : '';
        card.brain = (amountLabel ? 'دُفع ' + amountLabel : 'دُفع مبلغ') + ' ولم يصل ملف';
        card.reason = 'الأموال وصلت ولم يصل الملف إلى قائمة التوزيع';
        card.primary = { label: 'افتح', act: OPEN };
        break;
      }
      case 'legacy': {
        card.tag = 'استشارة قديمة';
        card.title = str(c.title) || 'استشارة قديمة';
        card.sub = clean([who && ('صاحب الطلب: ' + who), amountLabel]).join(' · ');
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
        card.primary = { label: 'اعتمد هذه الأسعار', act: act({ do: 'offer_approve', id: of.id }) };
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
          card.warn = 'يحتاج مراجعة: ' + flags.join(' · ');
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
    // brain2: اقتراحات العقل المنتظرة (proposed فقط) بطاقاتٌ في آخر الترتيب.
    (Array.isArray(opts.brainItems) ? opts.brainItems : []).forEach(function (it) {
      if (!it || !it.id || (it.status != null && it.status !== 'proposed')) return;
      src.push({ apiKind: 'brain_item', apiId: it.id, ref: it.id, item: it, ts: ms(it.created_at) });
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
  // سطر «القرار التالي»: الوسم ثم العنوان؛ وتحته كلام العقل.
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
      T('all', 'كل النزاعات', 'inbox', { activeFilter: 't:disputes' }, { activeFilter: ['t:disputes', 't:legacy'] }),
      T('escrow', 'كل السجلات', 'escrow', { escTab: 'sessions' }, { escTab: ['sessions', 'disputes', 'released'] })
    ] },
    { key: 'courses', label: 'الدورات والمدرّبون', img: 'courses', desc: 'الدورات وطلبات المدرّبين وما يطلبه الناس', tabs: [
      T('courses', 'الدورات', 'courses', { courseTab: 'platform' }, { courseTab: ['platform'] }),
      T('trainers', 'المدرّبون', 'team', { teamTab: 'trainers' }, { teamTab: ['trainers'] }),
      T('live', 'الدورات الحيّة', 'courses', { courseTab: 'schedules' }, { courseTab: ['schedules'] }),
      T('demand', 'ما يطلبه الناس', 'courses', { courseTab: 'demand' }, { courseTab: ['demand', 'programs'] }),
      T('offers', 'عروض الأسعار', 'courses', { courseTab: 'offers' }, { courseTab: ['offers'] }),
      hiddenTab(T('course', 'صفحة الدورة', 'courses', { courseTab: 'page' }, { courseTab: ['page'] })),
      T('all', 'كل السجلات', 'courses', { courseTab: 'courses' }, { courseTab: { not: [] } })
    ] },
    { key: 'market', label: 'سوق الخدمات', img: 'market', desc: 'طلبات الأعضاء وعروض الخبراء', tabs: [
      T('requests', 'الطلبات', 'market'),
      T('all', 'كل الطلبات', 'v2s_market_all'),
      T('demand', 'ماذا يطلب الناس', 'v2s_market_demand')
    ] },
    { key: 'books', label: 'الكتب', img: 'books', desc: 'كل كتاب وعمل، وعروض تنتظر المراجعة، وطلبات القرّاء', tabs: [
      T('offers', 'مراجعة العروض', 'v2b_offers'),
      T('requests', 'طلبات القرّاء', 'v2b_requests'),
      T('books', 'الكتب والأعمال', 'knowledge')
    ] },
    { key: 'people', label: 'الناس والدعوات', img: 'people', desc: 'من ينتظر الدخول، والدعوات، والأعضاء، والرسائل', tabs: [
      T('invites', 'الطلبات', 'invites'),
      T('pipeline', 'الدعوات', 'v2p_invites'),
      T('users', 'المستخدمون', 'users'),
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
      T('all', 'كل السجلات', 'finance', { finTab: 'summary' }, { finTab: { not: [] } })
    ] },
    { key: 'content', label: 'المحتوى', img: 'content', desc: 'المقالات والموضوعات والأخبار والتعليقات ودليل الاستخدام', tabs: [
      T('pipeline',  'خط النشر',       'topics', { topicsTab: 'pipeline' },  { topicsTab: ['pipeline'] }),
      T('articles',  'المقالات',        'topics', { topicsTab: 'articles' },  { topicsTab: ['articles', 'blog', 'auto'] }),
      T('topics',    'الموضوعات',       'topics', { topicsTab: 'pending' },   { topicsTab: ['pending', 'ideas', 'incoming', 'working', 'board', 'rejected', 'archived'] }),
      T('news',      'الأخبار',         'topics', { topicsTab: 'news' },      { topicsTab: ['news'] }),
      T('comments',  'التعليقات',       'topics', { topicsTab: 'comments' },  { topicsTab: ['comments'] }),
      T('tutorials', 'دليل الاستخدام', 'topics', { topicsTab: 'tutorials' }, { topicsTab: ['tutorials'] }),
      T('site',      'الموقع',          'topics', { topicsTab: 'site' },      { topicsTab: ['site'] })
    ] },
    { key: 'marketing', label: 'التسويق', img: 'marketing', desc: 'الحملات من الإعلان حتى الدفع، والسوشيال، وخطة النشر', tabs: [
      T('campaigns', 'الحملات', 'marketing'),
      T('social', 'السوشيال ميديا', 'v2mk_social'),
      T('plan', 'خطة النشر', 'v2mk_plan')
    ] },
    { key: 'reports', label: 'التقارير', img: 'reports', desc: 'ما الذي يعمل، وما الذي توقّف، وأين الفرصة', tabs: [
      T('report', 'التقرير', 'analysis'),
      T('demand', 'ما يسأل عنه الناس', 'v2r_demand'),
      T('sunday', 'تقرير الأحد', 'v2r_sunday')
    ] },
    { key: 'brain', label: 'العقل', img: 'brain', desc: 'ما يفعله العقل وحده، وما ينتظر قرارك. ما له مفتاح تغيّره من هنا.', tabs: [
      T('log', 'القواعد وسجل اليوم', 'v2s_brain'),
      T('helpers', 'المساعدون', 'ai')
    ] },
    { key: 'company', label: 'الشركة ورأس المال', img: 'company', desc: 'الشركاء ورأس المال والمعدات والاتفاقات والإعدادات', tabs: [
      T('invest', 'نظرة', 'investment'),
      T('partners', 'الشركاء ورأس المال', 'v2c_partners'),
      T('assets', 'المعدات والاشتراكات', 'v2c_assets'),
      T('deals', 'الاتفاقات والرعاة', 'v2c_deals'),
      T('ads', 'عملاء الإعلانات', 'v2c_ads'),
      T('settings', 'الإعدادات', 'settings'),
      hiddenTab(T('targets', 'الأهداف', 'targets'))
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
  // الاستعلام الاختياري في العنوان (`?scope=…&period=…`): مفاتيح مسموحة فقط وقيمها [a-z]{1,12}. بلا `?` كل عنوان قديم يُقرأ كما كان.
  var HASH_Q_KEYS = ['scope', 'period'];
  function hashQuery(q) {
    var parts = [];
    HASH_Q_KEYS.forEach(function (k) { if (q && typeof q[k] === 'string' && /^[a-z]{1,12}$/.test(q[k])) parts.push(k + '=' + q[k]); });
    return parts.length ? '?' + parts.join('&') : '';
  }
  function sectionHash(key, tab, person, q) {
    if (person && key === 'people' && tab === 'person') return '#s/people/person/' + personKey(person);
    if (person && key === 'courses' && tab === 'course') return '#s/courses/course/' + courseKey(person);
    return '#s/' + key + (tab ? '/' + tab : '') + hashQuery(q);
  }
  // صفحة الدورة: معرّفها في العنوان كما هو (حروف وأرقام وشرطتان فقط)، وغير الصالح ⇒ ''.
  function courseKey(id) { return encodeURIComponent(String(id == null ? '' : id).trim()); }
  function courseIdOf(key) {
    var e;
    try { e = decodeURIComponent(String(key == null ? '' : key)); } catch (x) { return ''; }
    e = e.trim();
    return /^[A-Za-z0-9_-]{1,100}$/.test(e) ? e : '';
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
    var qi = s.indexOf('?'), qs = '';
    if (qi > -1) { qs = s.slice(qi + 1); s = s.slice(0, qi); }
    var parts = s.split('/');
    if (parts[0] !== 's' || !parts[1]) return null;
    var sec = secOf(parts[1]);
    if (!sec) return null;
    var tab = parts[2] ? tabOf(sec.key, parts[2]) : null;
    var out = { section: sec.key, tab: (tab || sec.tabs[0]).key, exact: !!(parts[2] ? tab : true) };
    if (qs) {
      var q = {}, any = false;
      qs.split('&').forEach(function (kv) {
        var i = kv.indexOf('='), k = i > -1 ? kv.slice(0, i) : kv, v = i > -1 ? kv.slice(i + 1) : '';
        if (HASH_Q_KEYS.indexOf(k) > -1 && /^[a-z]{1,12}$/.test(v)) { q[k] = v; any = true; }
      });
      if (any) out.q = q;
    }
    if (tab && tab.hidden) {
      // صفحة الشخص: بلا بريد صالح في العنوان ⇒ أول تبويب في القسم (ولا صفحة فاضية).
      var em = sec.key === 'people' && tab.key === 'person' ? personEmailOf(parts[3]) : '';
      var cid = sec.key === 'courses' && tab.key === 'course' ? courseIdOf(parts[3]) : '';
      if (em) out.person = em; else if (cid) out.course = cid; else { out.tab = sec.tabs[0].key; out.exact = false; }
    }
    return out;
  }
  // أي عنوان (جديد أو رابط قديم) ⇒ {section, tab, mod, st[, person]} أو null.
  function routeFor(hash, state) {
    var s = String(hash == null ? '' : hash).replace(/^#/, '').trim();
    if (!s || s === 'home') return pack(secOf('home'), secOf('home').tabs[0]);
    // v2s:content — الرابط القديم العاري #topics يفتح الباب الأمامي للقسم (خط النشر)؛ أي نداء بحالة صريحة يمرّ على sectionFor.
    if (s === 'topics') return pack(secOf('content'), tabOf('content', 'pipeline'));
    var p = parseSectionHash(s);
    if (p) {
      var t = tabOf(p.section, p.tab), r = pack(secOf(p.section), t);
      if (p.person) r.person = p.person;
      if (p.course) r.course = p.course;
      if (p.q) r.q = p.q;
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
    personKey: personKey, personEmailOf: personEmailOf, courseKey: courseKey, courseIdOf: courseIdOf, COLS: COLS, COL_LABEL: COL_LABEL, NA: NA,
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
    util: { ar: ar, fmt: fmt, U: U, agoText: agoText, curName: curName, cur: curName, moneyText: moneyText, kindOf: kindOf, pickCandidate: pickCandidate,
            dateText: dateText, durShort: durShort, parseAmount: parseAmount, curLong: curLong, sumByCurrency: sumByCurrency }
  };
  // ===== v2s:brain =====
  // الجولة الأخيرة · قسم «العقل» (قواعده وسجل اليوم ومساعدوه). ⛔ نقي: لا DOM ولا شبكة ولا ساعة خفية (`now` يُمرَّر صراحةً).
  // مصدر فاشل = null (لا صفر). كل نص ظاهر فصحى بسيطة بلا مصطلحات تقنية ولا «اعكس» (لا تراجع حقيقي عن أي فعل تلقائي بعد).
  var BR_ZONE_RE = /(Z|[+-]\d\d:?\d\d)$/i;
  // وقت ISO ⇒ ميلي ثانية. بلا منطقة (SQLite) = UTC دائمًا؛ وإلا قرأه المتصفح بتوقيت الجهاز فيقع في يوم خطأ.
  function v2sBrainTime(s) {
    if (typeof s === 'number') return isFinite(s) && s > 0 ? s : null;
    if (typeof s !== 'string' || !s.trim()) return null;
    var t = s.trim();
    if (/^\d{4}-\d\d-\d\d$/.test(t)) t += 'T00:00:00Z';
    else if (!BR_ZONE_RE.test(t)) t += 'Z';
    var v = Date.parse(t);
    return isNaN(v) ? null : v;
  }
  function v2sBrainSince(now) { var d = new Date(now); d.setHours(0, 0, 0, 0); return d.getTime(); }
  function brClock(t) {
    var d = new Date(t), h = d.getHours(), m = d.getMinutes();
    return ar(h) + ':' + (m < 10 ? '٠' : '') + ar(m);
  }
  function brArDigits(t) { return String(t == null ? '' : t).replace(/\d/g, function (d) { return DIG.charAt(+d); }); }   // نص الخادم بأرقام عربية (لا أرقام لاتينية في الشاشة)
  function brLocal(email) { return String(email || '').split('@')[0]; }
  function brFile(n, forms) { return U(n, forms || ['ملف واحد', 'ملفان', 'ملفات', 'ملفًا']); }

  // مدخلات السجل: {file_id,title,status,atMs,by,reason,why,to_email,to_name,pre_claim,current,afterAuto}
  function brFinish(list, since, partial, missing, fromInbox) {
    var seen = {}, out = [], sinceMs = v2sBrainTime(since);
    list.forEach(function (e) {
      if (e.atMs == null || (sinceMs != null && e.atMs < sinceMs)) return;
      var key = [e.file_id, e.atMs, e.to_email].join('|');
      if (seen[key]) return;
      seen[key] = true;
      out.push(e);
    });
    out.sort(function (a, b) { return b.atMs - a.atMs; });
    var firstAuto = {};
    out.slice().reverse().forEach(function (e) { if (e.by === 'auto' && firstAuto[e.file_id] == null) firstAuto[e.file_id] = e.atMs; });
    var changed = {}, autoCount = 0;
    out.forEach(function (e) {
      e.afterAuto = e.by !== 'auto' && firstAuto[e.file_id] != null && e.atMs >= firstAuto[e.file_id];
      if (e.by === 'auto') autoCount++;
      if (e.afterAuto) changed[e.file_id] = true;
    });
    return { entries: out, autoCount: autoCount, changedCount: Object.keys(changed).length, partial: !!partial, missing: !!missing, fromInbox: !!fromInbox };
  }
  // ردّ B1 ⇒ {entries, autoCount, changedCount, partial, missing}، أو null إن فشل المصدر (والجسر غير ناقص).
  function v2sBrainEntries(resp, since) {
    if (!resp || typeof resp !== 'object') return null;
    if (resp.files_ok !== true) {
      if (resp.missing === true) return { entries: [], autoCount: null, changedCount: null, partial: false, missing: true, fromInbox: false };
      return null;
    }
    if (!Array.isArray(resp.entries)) return null;
    var list = resp.entries.filter(function (e) { return e && typeof e === 'object'; }).map(function (e) {
      return { file_id: str(e.file_id), title: str(e.title), status: str(e.status), atMs: v2sBrainTime(e.at), by: e.by === 'auto' ? 'auto' : 'founder',
               reason: str(e.reason), why: str(e.why), to_email: str(e.to_email).toLowerCase(), to_name: str(e.to_name) || null,
               pre_claim: e.pre_claim === true, current: e.current === true };
    });
    return brFinish(list, since, resp.partial === true, false, false);
  }
  // احتياط حين يفشل B1: من صفوف الوارد **بما فيها «للعلم»** (ملف وُزّع قبل ساعة ما زال في مهلة الاستلام). ناقص دائمًا (partial).
  function v2sBrainLogFromInbox(rows, since) {
    if (!Array.isArray(rows)) return null;
    var list = [];
    rows.forEach(function (r) {
      var f = r && r.ef;
      if (!f || !Array.isArray(f.assign_log) || !f.assign_log.length) return;
      var names = {};
      (Array.isArray(f.candidates) ? f.candidates : []).forEach(function (c) { if (c && c.email && c.name) names[String(c.email).toLowerCase()] = c.name; });
      (Array.isArray(f.declined) ? f.declined : []).forEach(function (d) { if (d && d.email && d.name && !names[String(d.email).toLowerCase()]) names[String(d.email).toLowerCase()] = d.name; });
      if (f.assigned_to && f.assigned_name) names[String(f.assigned_to).toLowerCase()] = f.assigned_name;
      if (f.expert_email && f.expert_name) names[String(f.expert_email).toLowerCase()] = f.expert_name;
      var last = f.assign_log[f.assign_log.length - 1], assignedTo = str(f.assigned_to).toLowerCase();
      f.assign_log.forEach(function (e) {
        if (!e || typeof e !== 'object' || typeof e.to !== 'string' || !e.to) return;
        var to = e.to.toLowerCase();
        list.push({ file_id: str(f.id), title: shorten(f.title, 80), status: str(f.status), atMs: v2sBrainTime(e.at), by: e.by === 'auto' ? 'auto' : 'founder',
                    reason: str(e.reason), why: shorten(e.why, 300), to_email: to, to_name: str(e.to_name) || names[to] || null,
                    pre_claim: str(f.status) === 'assigned', current: e === last && to === assignedTo });
      });
    });
    return brFinish(list, since, true, false, true);
  }
  function brName(e) { return e.to_name || brLocal(e.to_email) || 'خبير'; }
  // جملة السجل لمدخل ملف، مقسومة [قبل الاسم، الاسم، بعده] ليُرسم الاسم رابطًا لصفحة صاحبه.
  function v2sBrainLogParts(e) {
    var t = '«' + (e.title || 'ملف') + '»', n = brName(e);
    if (e.by !== 'auto') return ['أُرسل ' + t + ' يدويًا إلى ', n, ''];
    if (e.reason === 'declined') return ['وزّع ' + t + ' على ', n, ' بعد اعتذار خبير'];
    if (e.reason === 'timeout') return ['نقل ' + t + ' إلى ', n, ' لأن الملف لم يُستلم في وقته'];
    return ['وزّع ' + t + ' على ', n, ''];
  }
  function v2sBrainLogText(e) { return v2sBrainLogParts(e).join(''); }
  // اسم المساعد وصورته ووصفه بالعربية البسيطة (أسماء الخادم فيها SEO وMaster وn8n).
  var BR_AGENTS = {
    master: ['الصورة الكاملة', 'يجمع ما كتبه المساعدون في صورة واحدة وأهم ثلاث خطوات', 'brain-avatar'],
    articles: ['المقالات', 'المسودات التي تنتظر الاعتماد، وما لم نكتب عنه بعد', 'content'],
    seo: ['الظهور في البحث', 'هل تظهر مقالاتنا لمن يبحث عنها، وهل ننشر بانتظام', 'reports'],
    automation: ['الأعمال المتكرّرة', 'ما يتكرّر كل يوم في اللوحة ويمكن أن يعمل وحده', 'files'],
    sales: ['المبيعات', 'من سأل ولم يشترِ بعد، والخطوة التالية مع كل واحد', 'market'],
    marketing: ['التسويق', 'أي بلد وأي فئة نخاطب، بناءً على ما يطلبه الناس', 'marketing'],
    platform: ['المنصة', 'ما ينتظر الاعتماد، وما يبدو غير معتاد في الأرقام', 'company'],
    topics: ['الموضوعات', 'ما نكتب عنه بعد ذلك، من أسئلة الناس الحقيقية', 'books'],
    incoming: ['ما يطلبه الزوار', 'من أين يأتي الناس وماذا يسألون', 'people'],
    dev: ['سلامة الأنظمة', 'الأعطال وما يحتاج إصلاحًا', 'disputes'],
    finance: ['المالية', 'الدخل والمصروف وما قد يتأخر', 'money']
  };
  function v2sBrainAgentInfo(id, serverLabel, serverDesc) {
    var a = BR_AGENTS[id];
    return a ? { label: a[0], desc: a[1], img: a[2] } : { label: str(serverLabel) || str(id), desc: str(serverDesc), img: 'reports' };
  }
  // سجل اليوم كاملًا: مدخلات التوزيع (التي وزّعها العقل + تغيير المؤسس اللاحق) وتقارير المساعدين المكتوبة اليوم، الأحدث أولًا.
  function v2sBrainLogRows(ent, agents, since, items) {
    var rows = [], sinceMs = v2sBrainTime(since);
    ((ent && ent.entries) || []).forEach(function (e) {
      if (e.by !== 'auto' && !e.afterAuto) return;
      var act = e.by === 'auto' && e.pre_claim && e.current ? { kind: 'send', label: 'أرسله لخبير آخر' } : { kind: 'open', label: 'اعرض' };
      rows.push({ kind: 'file', atMs: e.atMs, time: brClock(e.atMs), text: v2sBrainLogText(e), parts: v2sBrainLogParts(e), why: e.by === 'auto' ? brArDigits(shorten(e.why, 160)) : '', muted: e.by !== 'auto',
                  entry: e, action: act, name: brName(e), email: e.to_email });
    });
    (Array.isArray(agents) ? agents : []).forEach(function (a) {
      var t = v2sBrainTime(a && a.created_at);
      if (t == null || (sinceMs != null && t < sinceMs) || !str(a.summary)) return;
      var id = str(a.agent || a.id), info = v2sBrainAgentInfo(id, a.label, a.desc);
      rows.push({ kind: 'report', atMs: t, time: brClock(t), text: 'كتب مساعد «' + info.label + '» تقريره', why: '', muted: false, agent: id, action: { kind: 'report', label: 'اعرض' } });
    });
    v2sBrainItemRows(items, since).forEach(function (r) { rows.push(r); });
    rows.sort(function (a, b) { return b.atMs - a.atMs; });
    return rows;
  }

  // —— ما يكتبه العقل (الجولة الثانية): المفاتيح والسجل والتشغيل. ⛔ كل مصدر يفشل لوحده ⇒ null (لا صفر ولا قائمة فاضية).
  var BR_MODE_LABEL = { alone: 'وحده', ask: 'يسألني', off: 'متوقّف' };
  var BR_RUN_CAP = 20;
  var BR_RUN_FRESH = 15 * 60 * 1000;
  // ردّ GET /switches ⇒ {rows, writer, brainToday} أو null. writer: 'main' | 'backup' | null (لا كاتب) | undefined (غير معروف).
  function v2sBrainSwitches(resp, now) {
    var list = resp && Array.isArray(resp) ? resp : (resp && typeof resp === 'object' ? (resp.switches || resp.producers) : null);
    if (!Array.isArray(list)) return null;
    var rows = [];
    list.forEach(function (p) {
      if (!p || typeof p !== 'object' || !str(p.id)) return;
      var locked = p.may_run_alone === false || str(p.kind) === 'draft';
      var opinion = str(p.kind) === 'opinion';
      var opts = locked ? ['ask', 'off'] : (opinion ? ['alone', 'off'] : ['alone', 'ask', 'off']);
      var mode = str(p.mode);
      if (opts.indexOf(mode) < 0) mode = opinion ? 'alone' : 'ask';       // الاختيار المحجوب لا يُعرض أبدًا: القفل في الخادم، وهنا نعرض ما يعمل فعلًا
      var sec = secOf(str(p.section)), t = v2sBrainTime(p.updated_at), line;
      if (locked) line = str(p.lock_reason) || 'يسألك دائمًا قبل أن يصل ما يكتبه إلى أحد.';
      else if (t != null) line = 'آخر تغيير: ' + (agoText(t, now || Date.now()) || 'غير متاح بعد') + (str(p.updated_by) ? ' بواسطة ' + str(p.updated_by) : '');
      else line = 'لم يُغيَّر من قبل';
      // «اسألني على تليجرام»: يظهر المفتاح فقط لو الخادم أعلن أنه يُضبط لهذا الصف (الرأي لا يُرسل أبدًا) وبقيمة منطقية صريحة.
      var tgToggle = p.telegram_can_toggle === true && typeof p.telegram === 'boolean';
      rows.push({ id: str(p.id), section: str(p.section), kind: str(p.kind), title: str(p.label) || str(p.id), sentence: str(p.sentence), lockReason: str(p.lock_reason),
                  tgToggle: tgToggle, telegram: tgToggle ? p.telegram : null, tgOk: p.telegram_ok === true,
                  locked: locked, mode: mode, updatedMs: t, updatedBy: str(p.updated_by), line: line,
                  options: opts.map(function (o) { return { value: o, label: BR_MODE_LABEL[o], on: o === mode }; }),
                  link: sec ? { label: 'افتح ' + sec.label, section: sec.key } : null });
    });
    var bt = resp && !Array.isArray(resp) && resp.brain_today && typeof resp.brain_today === 'object' ? resp.brain_today : null;
    var used = bt && typeof bt.used === 'number' && isFinite(bt.used) && bt.used >= 0 ? bt.used : null;
    var cap = bt && typeof bt.cap === 'number' && isFinite(bt.cap) && bt.cap > 0 ? bt.cap : null;
    var w = resp && !Array.isArray(resp) ? resp.writer : undefined;
    return { rows: rows, writer: w === 'main' || w === 'backup' || w === null ? w : undefined, writerLabel: resp && !Array.isArray(resp) ? brKeyLabel(resp.writer_label) : '', brainToday: { used: used, cap: cap } };
  }
  // ورقة تأكيد تغيير الاختيار: {title, lead, go}.
  function v2sBrainSwitchSheet(row, mode) {
    var t = '«' + row.title + '»', lead, go;
    if (mode === 'off') {
      lead = row.kind === 'opinion' ? 'يتوقف العقل عن كتابة رأيه على بطاقات القرار، وتعود الجملة الثابتة. ويبقى ما كتبه من قبل كما هو.'
        : 'يتوقف العقل عن كتابة ' + t + '. ويبقى ما كتبه من قبل كما هو.';
      go = 'نعم، أوقفه';
    } else if (mode === 'alone') {
      lead = row.kind === 'opinion' ? 'يكتب العقل رأيه على كل قرار وحده، ويظهر في بطاقة القرار. لا يُنفَّذ شيء بسببه.'
        : 'يكتب العقل ' + t + ' وحده، ويظهر ما كتبه في اللوحة دون انتظار موافقتك. لا يصل منه شيء إلى أحد خارج اللوحة.';
      go = 'نعم، وحده';
    } else {
      lead = 'يكتب العقل ' + t + ' اقتراحًا يظهر في اللوحة، ولا يُنفَّذ شيء إلا بعد موافقتك.';
      go = 'نعم، يسألني';
    }
    return { title: row.title, lead: lead, go: go };
  }
  // ورقة تأكيد «اسألني على تليجرام»: {title, lead, go}. ⛔ لا نقول إن الاعتماد من تليجرام متاح إلا لو الخادم أعلنه (`tgOk`).
  function v2sBrainTelegramSheet(row, on) {
    var t = '«' + row.title + '»', lead, go;
    if (on) {
      lead = 'يرسل العقل ' + t + ' إلى تليجرام عندما يكتب اقتراحًا جديدًا. '
        + (row.tgOk ? 'تستطيع أن تعتمده أو ترفضه من هناك، وتفتحه في اللوحة.' : 'تصلك رسالة بالرابط فقط، والقرار يبقى في اللوحة.');
      go = 'نعم، اسألني';
    } else {
      lead = 'لا يرسل العقل ' + t + ' إلى تليجرام. يبقى الاقتراح في اللوحة تراه هناك.';
      go = 'نعم، أوقفه';
    }
    return { title: row.title, lead: lead, go: go };
  }
  // ردّ GET /items ⇒ قائمة مطبَّعة أو null.
  function v2sBrainItems(resp) {
    var list = Array.isArray(resp) ? resp : (resp && typeof resp === 'object' ? resp.items : null);
    if (!Array.isArray(list)) return null;
    return list.filter(function (i) { return i && typeof i === 'object' && str(i.id); }).map(function (i) {
      var b = i.body && typeof i.body === 'object' ? i.body : {};
      return { id: str(i.id), producer: str(i.producer), section: str(i.section), kind: str(i.kind), label: shorten(str(i.target_label), 80), tag: str(i.tag),
               status: str(i.status), source: str(i.source), text: str(b.text), atMs: v2sBrainTime(i.created_at), decidedMs: v2sBrainTime(i.decided_at),
               by: str(i.decided_by), error: str(i.last_error) };
    });
  }
  var BR_OPINION_FORMS = ['قرار واحد', 'قرارين', 'قرارات', 'قرارًا'];
  // صفوف السجل من العناصر: الآراء صف واحد مجمَّع، والباقي صف لكل عنصر بالجمل المعتمدة.
  function v2sBrainItemRows(items, since) {
    var rows = [], sinceMs = v2sBrainTime(since), ops = 0, opAt = null;
    (Array.isArray(items) ? items : []).forEach(function (i) {
      var at = (i.decidedMs != null && ['approved', 'edited', 'rejected', 'discarded'].indexOf(i.status) >= 0) ? i.decidedMs : i.atMs;
      if (at == null || (sinceMs != null && at < sinceMs)) return;
      if (i.kind === 'opinion') {
        if (i.status === 'failed' || i.status === 'discarded') return;
        ops++; if (opAt == null || at > opAt) opAt = at;
        return;
      }
      var on = '«' + (i.label || 'عنصر') + '»', tag = '«' + (i.tag || 'كتابة') + '»', text, act = null, muted = false;
      if (i.status === 'done_alone') { text = 'كتب ملاحظة على ' + on; act = { kind: 'discard', label: 'احذفها' }; }
      else if (i.status === 'proposed') { text = 'اقترح ' + tag + ' على ' + on; act = { kind: 'open', label: 'افتح' }; }
      else if (i.status === 'approved' || i.status === 'edited') text = 'نُفّذ ' + tag + ' على ' + on + ' بموافقتك';
      else if (i.status === 'rejected') { text = 'رُفض اقتراح على ' + on; muted = true; }
      else if (i.status === 'discarded') { text = 'حُذفت ملاحظة على ' + on; muted = true; }
      else if (i.status === 'failed') { text = 'تعذّرت الكتابة عن ' + on; muted = true; }
      else if (i.status === 'unknown') text = 'لم نتأكد من نتيجة ' + tag + ' على ' + on;
      else return;
      rows.push({ kind: 'item', atMs: at, time: brClock(at), text: text, why: '', muted: muted, id: i.id, status: i.status, section: i.section, action: act });
    });
    if (ops > 0) rows.push({ kind: 'opinions', atMs: opAt, time: brClock(opAt), text: 'كتب رأيه في ' + U(ops, BR_OPINION_FORMS), why: '', muted: false, count: ops, action: null });
    return rows;
  }
  // عدد الاقتراحات التي تنتظر القرار (null إن فشل المصدر).
  function v2sBrainProposed(items) {
    if (!Array.isArray(items)) return null;
    return items.filter(function (i) { return i.status === 'proposed' && i.kind !== 'opinion'; }).length;
  }
  // الجولة: ردّ GET /runs/latest ⇒ {known, active}. جولة بلا انتهاء مضى عليها أكثر من ١٥ دقيقة لا تُعدّ نشطة (القفل نفسه كذلك).
  function v2sBrainRunState(resp, now) {
    if (!resp || typeof resp !== 'object') return { known: false, active: false };
    var r = resp.run !== undefined ? resp.run : resp;
    if (r === null || typeof r !== 'object') return { known: true, active: false };
    var st = v2sBrainTime(r.started_at), fin = r.finished_at;
    return { known: true, active: !fin && st != null && (now || 0) - st < BR_RUN_FRESH };
  }
  // زرّ «اكتب الاقتراحات الآن»: {canStart, active, reason, n, lead}. sw = ناتج v2sBrainSwitches|null · run = ناتج v2sBrainRunState.
  function v2sBrainRunInfo(sw, run, now) {
    var bt = sw && sw.brainToday ? sw.brainToday : { used: null, cap: null };
    var left = bt.used != null && bt.cap != null ? Math.max(0, bt.cap - bt.used) : null;
    var n = left != null ? Math.min(BR_RUN_CAP, left) : BR_RUN_CAP;
    var reason = '';
    if (run && run.active) reason = 'العقل يكتب الآن';
    else if (sw && sw.writer === null) reason = 'لا كاتب مفعّل الآن';
    else if (left === 0) reason = 'بلغ العقل حدّ كتابته اليوم';
    var lead = left != null || !sw ? 'يكتب العقل الآن ما ينقص من اقتراحات، بحد أقصى ' + U(n, ['كتابة واحدة', 'كتابتين', 'كتابات', 'كتابة']) + '.'
      : 'يكتب العقل الآن ما ينقص من اقتراحات.';
    return { canStart: !reason, active: !!(run && run.active), reason: reason, n: n, lead: lead };
  }
  // قرصا المساعدين الجديدان.
  function v2sBrainWriterText(writer, known, label) {
    if (!known || writer === undefined) return 'غير متاح بعد';
    var lab = brKeyLabel(label);
    if (lab && (writer === 'main' || writer === 'backup')) return lab + ' (' + (writer === 'main' ? 'الأساسي' : 'الاحتياطي') + ')';
    return writer === 'main' ? 'الكاتب الأساسي' : writer === 'backup' ? 'الكاتب الاحتياطي' : 'لا أحد';
  }
  // من يكتب الآن: من حالة المساعدين أولًا ثم من قواعد العقل. {writer, known, label}؛ الاسم يخصّ مفتاح القاعدة فقط ويغيب مع إعداد الخادم.
  function v2sBrainWriterPick(status, sw) {
    var okW = function (w) { return w === null || w === 'main' || w === 'backup'; };
    if (status && typeof status === 'object' && Object.prototype.hasOwnProperty.call(status, 'writer') && okW(status.writer)) return { writer: status.writer, known: true, label: brKeyLabel(status.writer_label) };
    if (sw && sw.writer !== undefined) return { writer: sw.writer, known: true, label: brKeyLabel(sw.writerLabel) };
    return { writer: undefined, known: false, label: '' };
  }
  function v2sBrainWritesToday(bt) {
    if (!bt || bt.used == null || bt.cap == null) return 'غير متاح بعد';
    return ar(bt.used) + ' من ' + ar(bt.cap);
  }

  // —— القواعد
  var BR_PLATFORM_LABEL = { sla: 'حارس المهلة والاسترداد', remind: 'تذكيرات المواعيد', tick: 'ساعة الدورات الحيّة', invite_reminders: 'تذكير أصحاب الدعوات', coach: 'متابعة المتدرّبين المتوقّفين' };
  var BR_HB = { sla: 'sla_last', remind: 'remind_last', tick: 'tick_last', invite_reminders: 'invite_reminders_last', coach: 'coach_stalled_last' };
  var BR_GROUPS = [['files', 'ملفات الخبراء والاستشارات'], ['courses', 'الدورات'], ['people', 'الناس والدعوات'], ['content', 'المحتوى']];
  // الصفوف بالترتيب: [المفتاح، المجموعة، العنوان، التشغيل (run)، الوجهة]
  var BR_ROWS = [
    ['assign', 'files', 'توزيع الملفات على الخبراء', 'sla', 'files'],
    ['move', 'files', 'نقل الملف إن لم يُستلم', 'sla', 'files'],
    ['unclaimed_refund', 'files', 'ردّ مبلغ الملف الذي لا يستلمه أحد', 'sla', 'files'],
    ['consult_refund', 'files', 'ردّ مبلغ الاستشارة عند تأخر الرد', 'sla', 'disputes'],
    ['release', 'files', 'تحرير أجر الخبير بعد التسليم', 'sla', 'disputes'],
    ['case_release', 'files', 'تحرير مراحل القضية', 'sla', 'files'],
    ['urgent', 'files', 'الملف المستعجل الذي لم يُستلم في وقته', 'sla', 'files'],
    ['reminders', 'files', 'تذكيرات الملفات', 'sla', 'files'],
    ['first_review', 'files', 'مراجعة أول ملفات الخبير الجديد', null, 'files'],
    ['offer_accept', 'courses', 'عروض الأسعار على الدورات', null, 'courses'],
    ['live', 'courses', 'الدورات المباشرة', 'tick', 'courses'],
    ['session_remind', 'courses', 'تذكير مواعيد الجلسات', 'remind', 'courses'],
    ['coach', 'courses', 'متابعة المتعلّمين المتوقّفين', 'coach', 'courses'],
    ['invite_remind', 'people', 'تذكير الدعوات المنتظرة', 'invite_reminders', 'invites'],
    ['invite_approval', 'people', 'دعوات الأجيال البعيدة', null, 'invites'],
    ['comments', 'content', 'التعليقات على الموضوعات', null, 'content']
  ];
  var BR_LINK = { files: ['افتح ملفات الخبراء', 'files', null], disputes: ['افتح النزاعات والاستردادات', 'disputes', null], courses: ['افتح الدورات', 'courses', null],
                  invites: ['افتح الدعوات', 'people', 'invites'], content: ['افتح المحتوى', 'content', null] };
  var BR_PLAIN_SENT = {
    unclaimed_refund: 'عندما تمر مهلة الاستلام بعد الدفع دون أن يستلم أي خبير الملف، يُردّ المبلغ كاملًا إلى صاحب الطلب.',
    consult_refund: 'عندما لا يرد الخبير على الاستشارة في المهلة الموعودة، يُردّ المبلغ إلى محفظة صاحب الطلب.',
    case_release: 'عندما تمر مهلة المرحلة دون اعتراض، يتحرّر أجرها.',
    urgent: 'عندما لا يُستلم الملف المستعجل في وقته، يصبح عاديًا ويُردّ فرق السعر إلى صاحب الطلب.',
    reminders: 'عندما يتأخر الدفع، أو تنقص معلومات، أو يقترب موعد جلسة، يصل تذكير إلى صاحبه.',
    first_review: 'عندما يسلّم خبير جديد أحد ملفاته الأولى، ينتظر الرأي مراجعتك قبل أن يصل إلى صاحب الطلب.',
    offer_accept: 'عندما يعرض متعلّم السعر العادل أو أكثر، يُقبل العرض وحده. وما هو أقل ينتظر قرارك.',
    live: 'عندما يكتمل العدد في موعده، تُفتح مهلة الدفع وحدها. وإن لم يكتمل، تنتظر الدورة قرارك.',
    session_remind: 'عندما تقترب جلسة، يصل تذكير إلى كل مشارك.',
    coach: 'عندما يتوقف متعلّم عن دورته مدة، تصله رسالة تشجيع وحدها، ولا تتكرر له قبل مهلة.',
    invite_remind: 'عندما يطول انتظار دعوة، يصل تذكير إلى المدعو أو إلى صاحب الدعوة.',
    comments: 'عندما يكون التعليق في الموضوع وبلا إساءة، يُنشر وحده. وغير ذلك ينتظر مراجعة.'
  };
  var BR_ALWAYS = { unclaimed_refund: 1, consult_refund: 1, release: 1, case_release: 1, urgent: 1 };
  var BR_STATIC_LINE = { first_review: 'في ملفات الخبراء', offer_accept: 'يعمل لحظة العرض', comments: 'يعمل لحظة التعليق' };

  function v2sBrainRunText(at, now, unavailable) {
    if (unavailable) return 'آخر تشغيل: غير متاح بعد';
    var t = v2sBrainTime(at);
    if (t == null) return 'لم يعمل حتى الآن';
    var d = Math.max(0, (now || 0) - t);
    return 'آخر تشغيل: ' + (d < MIN ? 'الآن' : 'منذ ' + durShort(d));
  }
  // التنبيه المبسَّط لتشغيل بعينه (باسمه في المنصة) أو null. ⛔ نص المنصة الخام لا يُعرض: من `v2Health`.
  function v2sBrainStopped(queue, platformLabel) {
    if (!queue) return null;
    var al = v2Health(queue).alerts;
    for (var i = 0; i < al.length; i++) if (al[i].indexOf(platformLabel + ':') === 0) return al[i];
    return null;
  }
  function v2sBrainStoppedAll(queue) {
    var out = [];
    Object.keys(BR_PLATFORM_LABEL).forEach(function (k) { var a = v2sBrainStopped(queue, BR_PLATFORM_LABEL[k]); if (a && out.indexOf(a) < 0) out.push(a); });
    return out;
  }
  function brReleaseWord(h) {
    if (h >= 48 && h % 24 === 0) return U(h / 24, ['يوم', 'يومان', 'أيام', 'يومًا']);
    return U(h, ['ساعة', 'ساعتان', 'ساعات', 'ساعة']);
  }
  // input = {settings: ردّ B2|null, queue: opsQueue|null, invite: inviteSettings|null, now}
  function v2sBrainRules(input) {
    input = input || {};
    var S = input.settings && typeof input.settings === 'object' ? input.settings : null, Q = input.queue || null, now = input.now || 0;
    var inv = input.invite && !input.invite.missing ? input.invite : null;
    var A = S && S.auto_assign && typeof S.auto_assign.value === 'boolean' ? S.auto_assign : null;
    var missingAuto = !!(S && S.auto_assign_missing);
    var hb = Q && Q.heartbeats && typeof Q.heartbeats === 'object' ? Q.heartbeats : {};
    var hours = S && typeof S.release_hours === 'number' && S.release_hours > 0 ? S.release_hours : null;
    var gen = inv && inv.invite_approval_from_generation != null && isFinite(Number(inv.invite_approval_from_generation)) ? Number(inv.invite_approval_from_generation) : null;
    var groups = BR_GROUPS.map(function (g) { return { key: g[0], title: g[1], rows: [] }; }), flat = [];
    BR_ROWS.forEach(function (d) {
      var key = d[0], run = d[3], lk = BR_LINK[d[4]];
      var alert = run ? v2sBrainStopped(Q, BR_PLATFORM_LABEL[run]) : null;
      var runLine = run ? v2sBrainRunText(hb[BR_HB[run]], now, !Q) : (BR_STATIC_LINE[key] || '');
      var row = { key: key, group: d[1], title: d[2], sentence: BR_PLAIN_SENT[key] || '', control: null, line: runLine,
                  run: { text: runLine, stopped: !!alert, alert: alert }, runKey: run, stopped: alert,
                  link: { label: lk[0], section: lk[1], tab: lk[2] } };
      if (key === 'assign') {
        row.sentence = 'عندما يُدفع ملف، يُرسل وحده إلى أنسب خبير متاح: حسب التخصص، ثم بلد القانون، ثم الأقل انشغالًا.';
        if (A) {
          row.control = { type: 'switch', value: A.value, label: A.value ? 'وحده' : 'يسألني', tone: A.value ? 'auto' : 'ask' };
          if (A.explicit === true) {
            var when = A.updated_at ? agoText(v2sBrainTime(A.updated_at), now) : '';
            row.line = 'آخر تغيير: ' + (when || 'غير متاح بعد') + (A.updated_by ? ' بواسطة ' + A.updated_by : '');
          } else if (A.explicit === false) row.line = 'لم يُغيَّر من قبل';
        } else {
          row.control = { type: 'chip', value: null, label: 'غير متاح بعد', tone: 'na' };
          row.line = missingAuto ? 'التوزيع التلقائي غير موجود على المنصة بعد' : 'تعذّر جلب حالة التوزيع';
        }
      } else if (key === 'move') {
        var on = A ? A.value : null;
        row.sentence = on === false ? 'عندما لا يستلم الخبير الملف في مهلته، يصلك تنبيه لترسله بنفسك.' : 'عندما لا يستلم الخبير الملف في مهلته، يُرسل وحده إلى الخبير التالي.';
        row.control = on === null ? { type: 'chip', value: null, label: 'غير متاح بعد', tone: 'na' } : { type: 'chip', value: on, label: on ? 'وحده' : 'يسألني', tone: on ? 'auto' : 'ask' };
        if (on === null) row.line = 'تعذّر جلب حالة التوزيع';
      } else if (key === 'release') {
        row.sentence = hours != null ? 'عندما تمر ' + brReleaseWord(hours) + ' على التسليم دون اعتراض، يتحرّر أجر الخبير.' : 'عندما تمر مهلة الاعتراض بعد التسليم دون اعتراض، يتحرّر أجر الخبير.';
        row.hours = hours;
        row.control = { type: 'chip', value: null, label: 'وحده دائمًا', tone: 'auto' };
      } else if (key === 'invite_approval') {
        row.sentence = gen != null ? 'عندما يدعو عضو من الجيل ' + ar(gen) + ' أو بعده، تنتظر الدعوة موافقتك.' : 'عندما تأتي دعوة من جيل بعيد، تنتظر موافقتك.';
        row.line = gen != null ? 'من الجيل ' + ar(gen) : 'الجيل: غير متاح بعد';
        row.control = { type: 'chip', value: null, label: 'يسألني', tone: 'ask' };
        row.link = { label: 'غيّرها من الدعوات', section: 'people', tab: 'invites' };
      } else if (key === 'first_review') {
        row.control = { type: 'chip', value: null, label: 'يسألني', tone: 'ask' };
      } else {
        row.control = { type: 'chip', value: null, label: BR_ALWAYS[key] ? 'وحده دائمًا' : 'وحده', tone: 'auto' };
      }
      // تنبيه المنصة باسم التشغيل يحلّ محلّ الشارة فقط (المفتاح الحقيقي يبقى ظاهرًا)، ونصّه هو سطر الحالة.
      if (alert) {
        if (row.control.type === 'chip') row.control = { type: 'chip', value: null, label: 'متوقّف', tone: 'stop' };
        row.line = alert;
      }
      groups.filter(function (g) { return g.key === d[1]; })[0].rows.push(row);
      flat.push(row);
    });
    return { groups: groups, rows: flat, autoAssign: A ? A.value : null };
  }
  // سطر العقل في التبويب الأول: أول حالة صحيحة. ctx = {queue, settings, entries (ناتج v2sBrainEntries|null), rulesOk}
  function v2sBrainLine(ctx) {
    ctx = ctx || {};
    var Q = ctx.queue || null, S = ctx.settings || null, ent = ctx.entries || null;
    var stopped = v2sBrainStoppedAll(Q);
    if (stopped.length) return { text: stopped[0], button: null };
    var A = S && S.auto_assign && typeof S.auto_assign.value === 'boolean' ? S.auto_assign.value : null;
    var waiting = Q ? qn(Q, 'expert_files_awaiting_assignment') : 0;
    if (A === false && waiting > 0) return { text: 'التوزيع التلقائي متوقّف، وينتظر توزيعك: ' + brFile(waiting), button: { label: 'افتح الملفات', section: 'files' } };
    if (typeof ctx.proposed === 'number' && ctx.proposed > 0) {
      return { text: 'ينتظرك من العقل: ' + U(ctx.proposed, ['اقتراح واحد', 'اقتراحان', 'اقتراحات', 'اقتراحًا']), button: { label: 'ابدأ القرارات', section: 'home', deck: true } };
    }
    var n = ent && typeof ent.autoCount === 'number' ? ent.autoCount : null;
    var least = ent && (ent.partial || ent.fromInbox) ? 'على الأقل ' : '';
    if (n != null && n > 0) {
      var m = ent.changedCount || 0;
      return { text: 'وُزّع اليوم ' + least + brFile(n) + ' وحده' + (m > 0 ? '، وغُيّر خبير ' + brFile(m, ['ملف واحد', 'ملفين', 'ملفات', 'ملفًا']) + ' منها يدويًا' : '') + '.', button: null };
    }
    var failed = [];
    if (!ent || n == null) failed.push('الملفات');
    if (!Q) failed.push('حالة ما يعمل وحده');
    if (!S || S.auto_assign == null && !S.auto_assign_missing) failed.push('القواعد');
    if (!failed.length) {
      var noAlerts = !(Array.isArray(Q.alerts) && Q.alerts.length);
      return { text: 'لم يوزّع العقل شيئًا اليوم' + (noAlerts ? '، وكل ما يعمل وحده يعمل' : '') + '.', button: null };
    }
    return { text: 'تعذّر جلب بعض ما يفعله العقل: ' + failed.join('، ') + '. لا نعرف الصورة كاملة.', button: null };
  }

  // —— المساعدون
  // agentsResp = EP.data.aiAgents {agents, ai_configured}|null · status = ردّ B3|null · running = معرّف المساعد قيد الكتابة|null
  function v2sBrainHelpers(agentsResp, status, running) {
    if (!agentsResp || !Array.isArray(agentsResp.agents)) return null;
    var list = agentsResp.agents.filter(function (a) { return a && typeof a === 'object'; });
    var blocked = !!(status && status.blocked === true);
    var remaining = status && typeof status.remaining === 'number' ? status.remaining : null;
    var count = list.length, busy = !!running;
    var cards = list.map(function (a) {
      var id = str(a.agent || a.id), info = v2sBrainAgentInfo(id, a.label, a.desc), t = v2sBrainTime(a.created_at);
      return { id: id, label: info.label, desc: info.desc, img: info.img, summary: str(a.summary), bullets: Array.isArray(a.bullets) ? a.bullets : [],
               actions: Array.isArray(a.actions) ? a.actions : [], createdMs: t, hasReport: !!str(a.summary),
               dataOnly: a.source === 'data' || a.ai_unavailable === true || /بلا تحليل نصّي\.?$/.test(str(a.summary)), canRun: !busy && !blocked, running: running === id };
    });
    cards.sort(function (a, b) { return (a.id === 'master' ? 0 : 1) - (b.id === 'master' ? 0 : 1); });
    var short = remaining !== null && remaining < count;
    var remText = !status ? 'غير متاح بعد' : status.cap == null ? 'بلا سقف' : remaining == null ? 'غير متاح بعد' : remaining === 0 ? 'لا شيء' : ar(remaining);
    return { cards: cards, master: cards.filter(function (c) { return c.id === 'master'; })[0] || null, count: count, remaining: remaining, remainingText: remText, blocked: blocked,
             canRunAll: !busy && !blocked && !short && count > 0, runAllReason: short ? 'لا يكفي المتبقي من تحديثات اليوم' : '',
             configured: status && typeof status.configured === 'boolean' ? status.configured : (typeof agentsResp.ai_configured === 'boolean' ? agentsResp.ai_configured : null) };
  }
  // قرص «تحديثات اليوم» في تبويب المساعدين.
  function v2sBrainCap(status) {
    if (!status || typeof status !== 'object') return 'غير متاح بعد';
    if (status.cap == null) return 'بلا سقف';
    if (status.used == null) return 'غير متاح بعد';
    return ar(status.used) + ' من ' + ar(status.cap);
  }
  function v2sBrainHelpersLine(H, status, now) {
    if (status && status.blocked === true) return 'وصلت تحديثات اليوم إلى حدّها، وتعود بعد منتصف الليل بتوقيت غرينتش.';
    if (status && status.configured === false) return 'التحليل المكتوب غير مفعّل الآن، فيكتب المساعدون الأرقام وحدها.';
    var m = H && H.master;
    if (m && m.hasReport && m.createdMs != null) return 'آخر صورة كاملة كُتبت ' + agoText(m.createdMs, now) + '.';
    return 'لم تُكتب الصورة الكاملة بعد.';
  }
  function v2sBrainConfirmAll(H) {
    var n = H.count;
    return 'سيكتب المساعدون ' + U(n, ['مساعد واحد', 'مساعدان', 'مساعدين', 'مساعدًا']) + ' تقاريرهم الآن، وتُحسب ' + U(n, ['تحديث واحد', 'تحديثان', 'تحديثات', 'تحديثًا'])
      + ' من تحديثات اليوم (المتبقي: ' + H.remainingText + ').';
  }

  // —— «المفاتيح والكاتب» (SPEC-B B1): صفوف المفاتيح والنموذج والجمل. ⛔ لا نص مفتاح يصل هنا أبدًا: الخادم يرسل آخر ٤ أحرف فقط.
  var BR_KEY_ROLE = { main: 'الأساسي', backup: 'الاحتياطي', off: 'موقوف' };
  var BR_KEY_TONE = { main: 'auto', backup: 'ask', off: 'na' };
  var BR_KEY_ROLES = ['main', 'backup', 'off'];
  var BR_KEY_HTTPS = 'https://';
  function brKeyLabel(v) { return typeof v === 'string' ? v.replace(/[\u0000-\u001f\u007f]/g, ' ').replace(/\s+/g, ' ').trim().slice(0, 60) : ''; }
  function brKeyTest(k, now) {
    var t = v2sBrainTime(k.last_test_at);
    if (k.last_test_ok === true) return { state: 'ok', text: 'جُرّب ' + (t != null ? agoText(t, now || Date.now()) : 'قبل قليل') + ': يعمل' };
    if (k.last_test_ok === false) return { state: 'fail', text: 'آخر تجربة لم تنجح: ' + (str(k.last_test_error) || 'لم يصل رد') };
    return { state: 'none', text: 'لم يُجرَّب بعد' };
  }
  // ردّ GET /keys ⇒ {rows, presets, main, backup} أو null (مصدر فاشل = null لا قائمة فاضية). «أخرى» دائمًا في آخر القوالب (قاعدة المؤسس).
  function v2sBrainKeys(resp, now) {
    if (!resp || typeof resp !== 'object' || !Array.isArray(resp.keys)) return null;
    var presets = [], seen = {};
    (Array.isArray(resp.presets) ? resp.presets : []).forEach(function (p) {
      if (!p || typeof p !== 'object' || !str(p.id) || !str(p.label) || seen[str(p.id)]) return;
      seen[str(p.id)] = 1;
      presets.push({ id: str(p.id), label: str(p.label), needsUrl: p.needs_url === true, defaultModel: str(p.default_model) });
    });
    var other = presets.filter(function (p) { return p.id === 'other'; })[0];
    presets = presets.filter(function (p) { return p.id !== 'other'; });
    presets.push(other || { id: 'other', label: 'أخرى', needsUrl: true, defaultModel: '' });
    var rows = [];
    resp.keys.forEach(function (k) {
      if (!k || typeof k !== 'object' || !str(k.id)) return;
      var role = BR_KEY_ROLES.indexOf(k.role) >= 0 ? k.role : 'off';
      var tail = typeof k.key_tail === 'string' ? k.key_tail.replace(/[^\x21-\x7e]/g, '').slice(-4) : '';
      var pr = presets.filter(function (p) { return p.id === str(k.preset); })[0];
      var readable = k.readable !== false;
      rows.push({ id: str(k.id), label: brKeyLabel(k.label) || (pr ? pr.label : 'مفتاح'), preset: str(k.preset), presetLabel: pr ? pr.label : '', model: str(k.model),
                  baseUrl: str(k.base_url), tail: tail ? '••••' + tail : '', tailText: tail ? 'ينتهي بـ ••••' + tail : 'غير متاح بعد',
                  role: role, roleLabel: BR_KEY_ROLE[role], tone: readable ? BR_KEY_TONE[role] : 'stop', readable: readable,
                  notice: readable ? '' : (str(k.notice) || 'تعذّرت قراءة هذا المفتاح؛ أضِفه من جديد'), test: readable ? brKeyTest(k, now) : { state: 'none', text: '' } });
    });
    var rank = { main: 0, backup: 1, off: 2 };      // الأساسي ثم الاحتياطي ثم الموقوف، وتبقى الأحدث أولًا داخل كل دور
    rows = rows.map(function (r, i) { return { r: r, i: i }; }).sort(function (a, b) { return (rank[a.r.role] - rank[b.r.role]) || (a.i - b.i); }).map(function (x) { return x.r; });
    var pick = function (r) { return rows.filter(function (x) { return x.role === r && x.readable; })[0] || null; };
    return { rows: rows, presets: presets, main: pick('main'), backup: pick('backup') };
  }
  // نموذج «أضف مفتاحًا»: {ok, field, error, body}. preset = عنصر من v2sBrainKeys().presets. التحقق هنا للراحة، والخادم هو الحَكَم.
  function v2sBrainKeyForm(preset, input) {
    var inp = input && typeof input === 'object' ? input : {};
    var fail = function (field, error) { return { ok: false, field: field, error: error, body: null }; };
    if (!preset || !str(preset.id)) return fail('preset', 'اختر الجهة أولًا');
    var model = str(inp.model) || str(preset.defaultModel);
    if (!model) return fail('model', 'اكتب اسم الموديل');
    if (model.length > 80 || /\s/.test(model)) return fail('model', 'اسم الموديل غير صالح؛ بلا مسافات وبحد أقصى ' + ar(80) + ' حرفًا');
    var url = str(inp.base_url);
    if (preset.needsUrl) {
      if (!url && preset.id === 'other') return fail('base_url', 'اكتب عنوان الخدمة كما يعطيه المزوّد');
      if (url && (url.slice(0, 8).toLowerCase() !== BR_KEY_HTTPS || /\s/.test(url) || url.length > 200)) return fail('base_url', 'اكتب عنوانًا آمنًا يبدأ بـ ' + BR_KEY_HTTPS);
    }
    var key = typeof inp.key === 'string' ? inp.key.trim() : '';
    if (!key) return fail('key', 'الصق المفتاح هنا');
    if (key.length < 8 || key.length > 400 || /\s/.test(key) || !/^[\x21-\x7e]+$/.test(key)) return fail('key', 'المفتاح غير مكتمل أو فيه مسافات');
    var role = BR_KEY_ROLES.indexOf(inp.role) >= 0 ? inp.role : '';
    if (!role) return fail('role', 'اختر دور المفتاح');
    var label = brKeyLabel(inp.label);
    if (str(inp.label).length > 60) return fail('label', 'الاسم أطول من ' + ar(60) + ' حرفًا');
    var body = { preset: preset.id, model: model, key: key, role: role, confirmed: true };
    if (label) body.label = label;
    if (preset.needsUrl && url) body.base_url = url;
    return { ok: true, field: '', error: '', body: body };
  }
  // أوراق التأكيد: {title, lead, go}. action: delete|main|backup|off|test. rows = ناتج v2sBrainKeys().rows (لذكر ما يتغيّر معه).
  function v2sBrainKeySheet(action, row, rows) {
    var t = '«' + row.label + '»', list = Array.isArray(rows) ? rows : [];
    var other = function (r) { return list.filter(function (x) { return x.role === r && x.id !== row.id; })[0] || null; };
    var lead, title, go;
    if (action === 'delete') {
      title = 'حذف المفتاح'; go = 'نعم، احذفه';
      lead = 'يُحذف المفتاح ' + t + ' من اللوحة نهائيًّا.' + (row.role === 'main' ? ' وهو الكاتب الأساسي الآن؛ بعد حذفه يكتب الاحتياطي إن وُجد، وإلا الإعداد الأصلي للخادم.'
        : row.role === 'backup' ? ' وهو الاحتياطي الآن.' : '');
    } else if (action === 'main') {
      var om = other('main'), ob = other('backup');
      title = 'اجعله الأساسي'; go = 'نعم، اجعله الأساسي';
      lead = t + ' يصير الكاتب الأساسي.' + (om ? ' وينتقل «' + om.label + '» إلى الاحتياطي' + (ob ? '، ويتوقف «' + ob.label + '»' : '') + '.' : (ob && ob.id !== row.id ? ' ويتوقف الاحتياطي «' + ob.label + '».' : ''));
    } else if (action === 'backup') {
      var pb = other('backup');
      title = 'اجعله احتياطيًّا'; go = 'نعم، اجعله احتياطيًّا';
      lead = t + ' لا يكتب إلا إذا تعثّر الكاتب الأساسي.' + (pb ? ' ويتوقف الاحتياطي الحالي «' + pb.label + '».' : '');
    } else if (action === 'off') {
      title = 'أوقف المفتاح'; go = 'نعم، أوقفه';
      lead = t + ' لا يكتب بعد الآن، ويبقى محفوظًا لتعيده متى شئت.';
    } else {
      title = 'جرّب المفتاح'; go = 'نعم، جرّبه';
      lead = 'يُرسل إلى ' + t + ' طلب صغير واحد، ويُحسب من تحديثات اليوم.';
    }
    return { title: title, lead: lead, go: go };
  }

  // —— «الأنظمة المتصلة» (SPEC-B B5): أنظمة نقرأ منها، ورموز تدخل بها أنظمة أخرى إلى هذه اللوحة. ⛔ لا نص رمز يصل هنا إلا لحظة الإنشاء (يُعرض مرة واحدة).
  var BR_MCP_SCOPE = { 'read': 'للقراءة فقط', 'read,propose': 'للقراءة والاقتراح' };
  var BR_LINK_BRAND_RE = /^[A-Za-z0-9][A-Za-z0-9._\-]{0,63}$/;
  function brHost(u) {
    var m = /^https:\/\/([^\/?#:]+)/i.exec(typeof u === 'string' ? u.trim() : '');
    return m ? m[1].toLowerCase() : '';
  }
  function brLinkTest(l, now) {
    var err = str(l.last_error), t = v2sBrainTime(l.last_ok_at);
    if (err) return { state: 'fail', text: 'آخر محاولة لم تنجح: ' + err };
    if (t != null) return { state: 'ok', text: 'آخر اتصال ناجح ' + agoText(t, now || Date.now()) };
    return { state: 'none', text: 'لم يُجرَّب بعد' };
  }
  // ردّ GET /links ⇒ {rows} أو null (مصدر فاشل = null لا قائمة فاضية).
  function v2sBrainLinks(resp, now) {
    if (!resp || typeof resp !== 'object' || !Array.isArray(resp.links)) return null;
    var rows = [];
    resp.links.forEach(function (l) {
      if (!l || typeof l !== 'object' || !str(l.id)) return;
      var readable = l.readable !== false, enabled = l.enabled !== false, known = l.known === true;
      rows.push({ id: str(l.id), name: brKeyLabel(l.name) || 'نظام', host: brHost(l.url), enabled: enabled, known: known, readable: readable,
                  brandId: str(l.brand_id), notice: readable ? '' : (str(l.notice) || 'تعذّرت قراءة الرمز المحفوظ؛ أضِف النظام من جديد'),
                  tone: !readable ? 'stop' : (enabled ? 'auto' : 'na'), stateLabel: !readable ? 'غير مقروء' : (enabled ? 'مفعّل' : 'موقوف'),
                  autoText: known ? 'يقرأ العقل أرقامه ويكتب ملخصًا قصيرًا' : 'لا يقرأ العقل منه تلقائيًا؛ تظهر أدواته عند التجربة فقط',
                  test: readable ? brLinkTest(l, now) : { state: 'none', text: '' } });
    });
    return { rows: rows, full: rows.length >= 10 };
  }
  // نموذج «أضف نظامًا»: {ok, field, error, body}. التحقق هنا للراحة، والخادم هو الحَكَم.
  function v2sBrainLinkForm(input) {
    var inp = input && typeof input === 'object' ? input : {};
    var fail = function (field, error) { return { ok: false, field: field, error: error, body: null }; };
    var name = brKeyLabel(inp.name);
    if (!name) return fail('name', 'اكتب اسم النظام');
    if (str(inp.name).length > 60) return fail('name', 'الاسم أطول من ' + ar(60) + ' حرفًا');
    var url = str(inp.url);
    if (!url) return fail('url', 'اكتب عنوان النظام كما يعطيه');
    if (url.slice(0, 8).toLowerCase() !== BR_KEY_HTTPS || /\s/.test(url) || url.length > 200 || !brHost(url)) return fail('url', 'اكتب عنوانًا آمنًا يبدأ بـ ' + BR_KEY_HTTPS);
    var token = typeof inp.token === 'string' ? inp.token.trim() : '';
    if (!token) return fail('token', 'الصق الرمز هنا');
    if (token.length < 8 || token.length > 600 || !/^[\x21-\x7e]+$/.test(token)) return fail('token', 'الرمز غير مكتمل أو فيه مسافات');
    var brand = str(inp.brand_id);
    if (brand && !BR_LINK_BRAND_RE.test(brand)) return fail('brand_id', 'معرّف العلامة غير صالح');
    var body = { name: name, url: url, token: token, confirmed: true };
    if (brand) body.brand_id = brand;
    return { ok: true, field: '', error: '', body: body };
  }
  // ردّ GET /mcp-tokens ⇒ {rows, active, serverUrl, tools} أو null. العاملة أولًا ثم الملغاة.
  function v2sBrainMcpTokens(resp, now) {
    if (!resp || typeof resp !== 'object' || !Array.isArray(resp.tokens)) return null;
    var rows = [];
    resp.tokens.forEach(function (t) {
      if (!t || typeof t !== 'object' || !str(t.id)) return;
      var revoked = v2sBrainTime(t.revoked_at) != null, used = v2sBrainTime(t.last_used_at), canPropose = t.can_propose === true;
      rows.push({ id: str(t.id), name: brKeyLabel(t.name) || 'رمز', canPropose: canPropose, scopeLabel: BR_MCP_SCOPE[canPropose ? 'read,propose' : 'read'],
                  revoked: revoked, tone: revoked ? 'stop' : 'auto', stateLabel: revoked ? 'أُلغي' : 'عامل',
                  usedText: revoked ? 'توقف عن الدخول ' + (agoText(v2sBrainTime(t.revoked_at), now || Date.now()) || '')
                    : (used != null ? 'آخر استعمال ' + agoText(used, now || Date.now()) : 'لم يُستعمل بعد') });
    });
    rows = rows.map(function (r, i) { return { r: r, i: i }; }).sort(function (a, b) { return (a.r.revoked - b.r.revoked) || (a.i - b.i); }).map(function (x) { return x.r; });
    var su = str(resp.server_url);
    return { rows: rows, active: rows.filter(function (r) { return !r.revoked; }).length, serverUrl: su.slice(0, 8).toLowerCase() === BR_KEY_HTTPS && !/\s/.test(su) ? su : '',
             tools: Array.isArray(resp.tools) ? resp.tools.filter(function (x) { return typeof x === 'string'; }) : [] };
  }
  // نموذج «أنشئ رمزًا»: {ok, field, error, body}.
  function v2sBrainMcpTokenForm(input) {
    var inp = input && typeof input === 'object' ? input : {};
    var fail = function (field, error) { return { ok: false, field: field, error: error, body: null }; };
    var name = brKeyLabel(inp.name);
    if (!name) return fail('name', 'اكتب اسم النظام الذي سيستعمل الرمز');
    if (str(inp.name).length > 36) return fail('name', 'الاسم أطول من ' + ar(36) + ' حرفًا');
    if (BR_MCP_SCOPE[inp.scopes] == null) return fail('scopes', 'اختر ما يسمح به الرمز');
    return { ok: true, field: '', error: '', body: { name: name, scopes: inp.scopes, confirmed: true } };
  }
  // أوراق التأكيد: {title, lead, go}. action: link-delete | link-test | token-revoke.
  function v2sBrainMcpSheet(action, row) {
    var t = '«' + (row && row.name ? row.name : '') + '»';
    if (action === 'link-delete') return { title: 'حذف النظام', go: 'نعم، احذفه', lead: 'يُحذف ' + t + ' من الأنظمة المتصلة ويُمسح رمزه المحفوظ. لا يتغيّر شيء عند النظام الآخر.' };
    if (action === 'token-revoke') return { title: 'إلغاء الرمز', go: 'نعم، ألغِه', lead: 'يتوقف ' + t + ' عن الدخول إلى هذه اللوحة فورًا، ولا يمكن إعادة تفعيل الرمز. تنشئ رمزًا جديدًا إن احتجت.' };
    return { title: 'جرّب الاتصال', go: 'نعم، جرّب', lead: 'يُطلب من ' + t + ' الاتصال وقائمة أدواته فقط. لا تُقرأ أرقام ولا يتغيّر شيء.' };
  }

  Object.assign(api, {
    v2sBrainTime: v2sBrainTime, v2sBrainSince: v2sBrainSince, v2sBrainEntries: v2sBrainEntries, v2sBrainLogFromInbox: v2sBrainLogFromInbox,
    v2sBrainLogText: v2sBrainLogText, v2sBrainLogParts: v2sBrainLogParts, v2sBrainLogRows: v2sBrainLogRows, v2sBrainRules: v2sBrainRules, v2sBrainRunText: v2sBrainRunText,
    v2sBrainStopped: v2sBrainStopped, v2sBrainStoppedAll: v2sBrainStoppedAll, v2sBrainLine: v2sBrainLine, v2sBrainHelpers: v2sBrainHelpers,
    v2sBrainAgentInfo: v2sBrainAgentInfo, v2sBrainCap: v2sBrainCap, v2sBrainHelpersLine: v2sBrainHelpersLine, v2sBrainConfirmAll: v2sBrainConfirmAll,
    v2sBrainSwitches: v2sBrainSwitches, v2sBrainSwitchSheet: v2sBrainSwitchSheet, v2sBrainTelegramSheet: v2sBrainTelegramSheet, v2sBrainItems: v2sBrainItems, v2sBrainItemRows: v2sBrainItemRows,
    v2sBrainProposed: v2sBrainProposed, v2sBrainRunState: v2sBrainRunState, v2sBrainRunInfo: v2sBrainRunInfo,
    v2sBrainWriterText: v2sBrainWriterText, v2sBrainWritesToday: v2sBrainWritesToday, v2sBrainWriterPick: v2sBrainWriterPick,
    v2sBrainKeys: v2sBrainKeys, v2sBrainKeyForm: v2sBrainKeyForm, v2sBrainKeySheet: v2sBrainKeySheet,
    v2sBrainLinks: v2sBrainLinks, v2sBrainLinkForm: v2sBrainLinkForm, v2sBrainMcpTokens: v2sBrainMcpTokens, v2sBrainMcpTokenForm: v2sBrainMcpTokenForm, v2sBrainMcpSheet: v2sBrainMcpSheet
  });
  // ===== /v2s:brain =====

  root.V2L = api;
  if (typeof module !== 'undefined' && module.exports) module.exports = api;

  // ===== v2s:reports =====
  // «التقارير» (الجولة النهائية): دوال نقية فقط. الأرقام نفسها تأتي من الخادم (`/api/v2/reports/*`) وهنا عرضها ومنطق الشاشة:
  // لا شبكة ولا DOM ولا ساعة خفية. ⛔ الرقم المجهول `null` يبقى «غير متاح بعد» ولا يتحوّل إلى صفر أبدًا.
  (function () {
    // عدّ بفاصل آلاف عربي (نفس `_ar` في الخادم): ٣ أرقام فما فوق تُجمَّع «١٬٨٤٠».
    function nf(n) { return fmt(n); }
    function UU(n, forms) {
      n = Math.round(Number(n) || 0);
      if (n === 1) return forms[0];
      if (n === 2) return forms[1];
      return nf(n) + ' ' + (n >= 3 && n <= 10 ? forms[2] : forms[3]);
    }
    function trendChip(t) {
      var k = t && t.key, p = t && t.pct;
      if (k === 'up') return { text: 'ينمو ' + nf(Math.abs(p)) + '٪', tone: 'up' };
      if (k === 'down') return { text: 'يتراجع ' + nf(Math.abs(p)) + '٪', tone: 'down' };
      if (k === 'flat') return { text: 'ثابت', tone: 'flat' };
      if (k === 'new') return { text: 'جديد', tone: 'up' };
      if (k === 'none') return { text: 'لا بيع', tone: 'mute' };
      return { text: NA, tone: 'na' };
    }
    var CONV = { asked: 'من الزوار', signed_up: 'ممن سألوا', opened: 'من المسجّلين', paid: 'ممن فتحوا' };
    // stage = {key, cur, prev}؛ prevKnown = المرحلة السابقة مباشرة إن كان لها رقم وإلا null.
    function stageView(st, prevKnown) {
      var out = { changeText: '', tone: '', convText: '' };
      if (!st || st.cur == null) return out;
      if (st.prev != null) {
        if (st.prev === 0) {
          if (st.cur > 0) { out.changeText = 'جديد'; out.tone = 'up'; } else { out.changeText = 'كما هو'; out.tone = 'flat'; }
        } else {
          var raw = (st.cur - st.prev) * 100 / st.prev;
          if (Math.abs(raw) < 1) { out.changeText = 'كما هو'; out.tone = 'flat'; }
          else {
            var p = Math.round(raw);
            if (p > 0) { out.changeText = '▲ ' + nf(p) + '٪'; out.tone = 'up'; } else { out.changeText = '▼ ' + nf(Math.abs(p)) + '٪'; out.tone = 'down'; }
          }
        }
      }
      if (prevKnown && prevKnown.cur != null && prevKnown.cur > 0 && CONV[st.key]) out.convText = nf(Math.round(st.cur * 100 / prevKnown.cur)) + '٪ ' + CONV[st.key];
      return out;
    }
    function missingText(n) {
      if (!n) return '';
      return UU(n, ['خطوة واحدة', 'خطوتان', 'خطوات', 'خطوة']) + (n === 2 ? ' تكتملان' : ' تكتمل') + ' حين تسجّل المنصة الزيارات';
    }
    function funnelCompact(stages) {
      var list = Array.isArray(stages) ? stages : [];
      var rows = list.filter(function (s) { return s && (s.cur != null || s.failed); });
      var missing = list.filter(function (s) { return s && s.cur == null && !s.failed; }).length;
      return { rows: rows, missing: missing, text: missingText(missing) };
    }
    // نقاط الرسم: x موزّعة بالتساوي، وكل سلسلة على مقياسها (الدخل يسارًا والحسابات يمينًا والزوار لوحدهم). سلسلة فيها قيمة مجهولة لا تُرسم.
    // سلسلة كلها أصفار تُرسم مسطّحة عند خط الأساس (لا تُخفى). الارتفاع الفعلي = h - أسفل - (قيمة / الأكبر) * (h - أعلى - أسفل).
    function chartPoints(rows, w, h) {
      rows = Array.isArray(rows) ? rows : [];
      var padT = 24, padB = 36, padX = 14, n = rows.length;
      var inner = h - padT - padB;
      function series(key) {
        var vals = rows.map(function (r) { return r[key]; });
        if (!n || vals.some(function (v) { return v == null || !isFinite(v); })) return null;
        var max = Math.max.apply(null, vals), min = Math.min.apply(null, vals);
        // سلسلة ثابتة (كل قيمها واحدة وأكبر من صفر) تُرسم في منتصف الارتفاع لا عند القمة، حتى لا تبدو أعلى من غيرها
        var constant = n > 1 && max > 0 && min === max;
        var pts = vals.map(function (v, i) {
          var x = n === 1 ? w / 2 : padX + (w - 2 * padX) * i / (n - 1);
          var y = constant ? padT + inner / 2 : (max > 0 ? padT + inner - (v / max) * inner : padT + inner);
          return [Math.round(x * 10) / 10, Math.round(y * 10) / 10];
        });
        return { key: key, pts: pts, max: max, flat: !(max > 0), constant: constant };
      }
      var out = { income: series('income_egp'), signups: series('signups'), visits: series('visits'), n: n, base: padT + inner, top: padT, padX: padX };
      out.grid = [0, 1, 2, 3].map(function (i) { return Math.round((padT + inner * i / 3) * 10) / 10; });
      return out;
    }
    // السلاسل المرسومة فقط تظهر في المفتاح، وما لم يُرسم يُقال مرة واحدة في الحاشية.
    function legendItems(daily, scope) {
      var d = daily || {}, items = [], notes = [];
      if (d.ledger !== false) items.push({ key: 'income', label: 'الدخل بالجنيه' }); else notes.push('الدخل بالجنيه: ' + NA);
      if (d.signups_available) items.push({ key: 'signups', label: 'حسابات جديدة' }); else if (!scope || scope === 'all') notes.push('الحسابات الجديدة: ' + NA);
      if (d.visits_available) items.push({ key: 'visits', label: 'الزوار' }); else notes.push('الزوار: ' + NA);
      // سلسلة بقيمة واحدة في كل الفترة: تُقال صراحة لأن رسمها في المنتصف بلا مقياس
      var rows = Array.isArray(d.rows) ? d.rows : [], per = d.bucket === 'week' ? 'أسبوعيًا' : 'يوميًا';
      [['income_egp', 'الدخل', d.ledger !== false], ['signups', 'الحسابات الجديدة', !!d.signups_available], ['visits', 'الزوار', !!d.visits_available]].forEach(function (c) {
        if (!c[2] || rows.length < 2) return;
        var vals = rows.map(function (r) { return r[c[0]]; });
        if (vals.some(function (v) { return v == null || !isFinite(v); })) return;
        var mx = Math.max.apply(null, vals);
        if (mx > 0 && Math.min.apply(null, vals) === mx) notes.push(c[1] + ' ثابت: ' + nf(mx) + ' ' + per);
      });
      return { items: items, notes: notes };
    }
    // تصفية «أحدث الأسئلة»: نفس سلوك الشاشة القديمة بالحرف (f = {seg, country, cat, ne, time}).
    function within(iso, days, now) { var t = Date.parse(iso || ''); return !isNaN(t) && (now - t) <= days * 86400000; }
    function demandFilter(recent, f, now) {
      f = f || {};
      return (Array.isArray(recent) ? recent : []).filter(function (r) {
        if (f.seg && f.seg !== 'all' && (r.segment || '') !== f.seg) return false;
        if (f.country && f.country !== 'all' && (r.country || 'unknown') !== f.country) return false;
        if (f.cat && f.cat !== 'all' && (r.category || '') !== f.cat) return false;
        if (f.ne === 'yes' && !r.needs_expert) return false;
        if (f.ne === 'no' && r.needs_expert) return false;
        if (f.time && f.time !== 'all' && !within(r.created_at, f.time === '7' ? 7 : 30, now)) return false;
        return true;
      });
    }
    function hiddenFilters(f) { f = f || {}; return ['seg', 'country', 'cat', 'time'].filter(function (k) { return f[k] && f[k] !== 'all'; }).length + (f.ne === 'no' ? 1 : 0); }
    function demandNumbers(d) {
      d = d || {};
      var countries = (Array.isArray(d.by_country) ? d.by_country : []).filter(function (c) { return c && c.country && c.country !== 'unknown' && (c.count || 0) > 0; }).length;
      var parts = [UU(d.total || 0, ['سؤال واحد', 'سؤالان', 'أسئلة', 'سؤالًا']),
        nf(d.needs_expert || 0) + ' تحتاج رأي خبير (' + nf(Math.round((d.needs_expert_rate || 0) * 100)) + '٪)',
        nf(d.authed || 0) + ' عضو و' + nf(d.anonymous || 0) + ' زائر'];
      var eo = d.expert_opinions;
      if (eo && typeof eo === 'object' && eo.requested != null && eo.paid != null) parts.push('دفع ' + nf(eo.paid) + ' من ' + nf(eo.requested) + ' مقابل رأي خبير (' + nf(Math.round((eo.conversion_rate || 0) * 100)) + '٪)');
      else parts.push('الدفع مقابل رأي خبير: ' + NA);
      parts.push('من ' + UU(countries, ['بلد واحد', 'بلدين', 'بلاد', 'بلدًا']));
      return parts.join(' · ');
    }
    function weekText(iso) {
      var m = /^(\d{4})-(\d{2})-(\d{2})$/.exec(String(iso || ''));
      return m ? ar(+m[3]) + ' ' + MONTHS[+m[2] - 1] : '';
    }
    function deliveryText(d) {
      d = d || {};
      if (d.bridge === 'absent') return 'الإرسال كل أحد: ' + NA + ' — ينتظر تجهيز الإرسال على المنصة';
      if (d.bridge === 'failed') return 'الإرسال كل أحد: تعذّر التحقق الآن';
      if (!d.setting) return 'الإرسال كل أحد: متوقف';
      if (d.platform_enabled) return 'يصلك هذا التقرير كل أحد ٨ صباحًا على تليجرام' + (d.last_sent_week && weekText(d.last_sent_week) ? ' · آخر إرسال: أسبوع ' + weekText(d.last_sent_week) : '');
      return 'الإرسال مفعّل هنا، والمنصة لم تفعّله بعد';
    }
    function periodLine(win, prev) { return (win && win.label ? win.label : '') + (prev && prev.label ? ' مقارنة ب' + prev.label : ''); }
    // زرّ الشريط الوحيد: أول سطر له فعل بترتيب واقف ثم فرصة ثم شغّال (يرسل الخادم `brain_primary` كذلك).
    function brainPrimary(lines) {
      var order = ['stalled', 'opportunity', 'working'];
      for (var i = 0; i < order.length; i++) {
        var ln = (lines || []).filter(function (x) { return x.key === order[i]; })[0];
        if (ln && ln.text && ln.action) return order[i];
      }
      return null;
    }
    var SCOPES = [['all', 'المنصة كلها'], ['files', 'الملفات'], ['courses', 'الدورات'], ['books', 'الكتب'], ['market', 'السوق'], ['content', 'المحتوى'], ['marketing', 'التسويق']];
    var PERIODS_R = [['week', 'الأسبوع'], ['month', 'الشهر'], ['quarter', '٣ أشهر']];
    api.v2r = { trendChip: trendChip, stageView: stageView, funnelCompact: funnelCompact, missingText: missingText, chartPoints: chartPoints, legendItems: legendItems,
      demandFilter: demandFilter, hiddenFilters: hiddenFilters, demandNumbers: demandNumbers, deliveryText: deliveryText, periodLine: periodLine, brainPrimary: brainPrimary,
      weekText: weekText, u: UU, n: nf, SCOPES: SCOPES, PERIODS: PERIODS_R, NA: NA };
  })();
  // ===== /v2s:reports =====
})(typeof window !== 'undefined' ? window : (typeof globalThis !== 'undefined' ? globalThis : this));

// ===== v2s:company =====
// «الشركة ورأس المال» — منطق نقي (لا DOM ولا شبكة). المصدر الذي تعذّر ⇒ null، ولا يتحوّل إلى صفر أبدًا. العملات لا تُجمع ولا تُحوَّل.
(function (root) {
  'use strict';
  var L = root.V2L;
  if (!L) return;
  var U = L.util, ar = U.ar, fmt = U.fmt, moneyText = U.moneyText;
  var NA = 'غير متاح بعد';
  var MONTHS = ['يناير', 'فبراير', 'مارس', 'أبريل', 'مايو', 'يونيو', 'يوليو', 'أغسطس', 'سبتمبر', 'أكتوبر', 'نوفمبر', 'ديسمبر'];
  var DAY_FORMS = ['يوم واحد', 'يومين', 'أيام', 'يومًا'];
  var ROLE_LABEL = { founder: 'مؤسس', cofounder: 'شريك مؤسس', investor: 'مستثمر', partner: 'شريك', pool: 'حصص غير موزّعة' };
  var CAT_LABEL = { computers: 'أجهزة كمبيوتر', phones: 'هواتف', camera: 'كاميرات', lenses: 'عدسات', microphone: 'صوت', lighting: 'إضاءة', tripod: 'حوامل',
                    teleprompter: 'جهاز قراءة النص', hardware: 'ملحقات', equipment: 'معدات', subscription: 'اشتراك', software: 'برنامج', tool: 'أداة', other: 'أخرى' };
  var STATUS_LABEL = { leased_to_company: 'مؤجَّر للشركة', owned_by_company: 'ملك الشركة', in_studio: 'في الاستوديو', with_person: 'مع أحد الفريق',
                       out_of_service: 'خارج الخدمة', other: 'أخرى' };
  var KIND_LABEL = { sponsor: 'راعٍ', content: 'اتفاق محتوى', book: 'اتفاق كتاب', company_paper: 'أوراق الشركة', other: 'أخرى' };
  var CYCLE_LABEL = { monthly: 'شهريًا', yearly: 'سنويًا' };
  var RESERVE_NAMES = ['غير موزّع', 'Unallocated / Option Pool'];
  var LEGACY_CATS = ['subscription', 'software', 'tool'];

  function num(v) { var n = typeof v === 'number' ? v : (typeof v === 'string' && v.trim() !== '' ? Number(v) : NaN); return isFinite(n) ? n : null; }
  function dayText(n) { return U.U(n, DAY_FORMS); }
  // أيام التقويم المحلي (لا نوافذ ٢٤ ساعة): iso = «YYYY-MM-DD». غير صالح ⇒ null.
  function daysUntil(iso, now) {
    var m = /^(\d{4})-(\d{2})-(\d{2})/.exec(String(iso || ''));
    if (!m) return null;
    var n = new Date(now || 0);
    var a = Date.UTC(+m[1], +m[2] - 1, +m[3]), b = Date.UTC(n.getFullYear(), n.getMonth(), n.getDate());
    return Math.round((a - b) / 86400000);
  }
  function monthText(period) {
    var m = /^(\d{4})-(\d{2})/.exec(String(period || ''));
    if (!m || +m[2] < 1 || +m[2] > 12) return '';
    return MONTHS[+m[2] - 1] + ' ' + ar(+m[1]);
  }
  function monthName(period) { var m = /^(\d{4})-(\d{2})/.exec(String(period || '')); return m && +m[2] >= 1 && +m[2] <= 12 ? MONTHS[+m[2] - 1] : ''; }
  function nowKey(now) { var d = new Date(now || 0); return d.getFullYear() + '-' + (d.getMonth() + 1 < 10 ? '0' : '') + (d.getMonth() + 1); }
  function sumLines(list) {
    return (Array.isArray(list) ? list : []).filter(function (x) { return x && num(x.amount) !== null && num(x.amount) !== 0; })
      .map(function (x) { return moneyText(x.amount, x.currency); }).join(' · ');
  }
  function amountOf(list, cur) {
    var a = (Array.isArray(list) ? list : []).filter(function (x) { return x.currency === cur; })[0];
    return a ? num(a.amount) || 0 : 0;
  }
  // الباقي لكل عملة عليها دفعة مسجّلة فقط. لا سالب: المدفوع الزائد أو المساوي لا يظهر.
  function remaining(agreed, paid) {
    var out = [];
    (Array.isArray(agreed) ? agreed : []).forEach(function (a) {
      var p = amountOf(paid, a.currency);
      if (!p) return;
      var r = Math.round(((num(a.amount) || 0) - p) * 100) / 100;
      if (r > 0) out.push({ currency: a.currency, amount: r });
    });
    return out;
  }
  function partnerChip(row) {
    if (!row || !Array.isArray(row.paid)) return null;                      // المدفوع مجهول (الملخّص تعذّر) ⇒ لا شارة
    if (!row.contributions && !row.paid.length) return { text: 'لم تُسجَّل دفعات', tone: 'neutral' };
    var agreed = Array.isArray(row.agreed) ? row.agreed : [];
    var rem = remaining(agreed, row.paid);
    if (rem.length) return { text: 'باقٍ ' + sumLines(rem), tone: 'soon' };
    var touched = agreed.filter(function (a) { return amountOf(row.paid, a.currency) > 0; });
    if (touched.length) return { text: 'دفع كاملًا', tone: 'ok' };
    return { text: 'دفع ' + sumLines(row.paid), tone: 'neutral' };
  }

  function agreementChip(row, now) {
    if (!row) return { text: '', tone: 'neutral', days: null };
    if (row.status === 'ended') return { text: 'انتهى', tone: 'neutral', days: null };
    if (row.status === 'draft') return { text: 'مسودة', tone: 'neutral', days: null };
    var d = daysUntil(row.ends_on, now);
    if (d === null) return { text: 'ساري', tone: 'ok', days: null };
    if (d < 0) return { text: 'انتهى', tone: 'neutral', days: d };
    if (d === 0) return { text: 'ينتهي اليوم', tone: 'late', days: 0 };
    if (d <= 7) return { text: 'ينتهي بعد ' + dayText(d), tone: 'late', days: d };
    if (d <= 30) return { text: 'ينتهي بعد ' + dayText(d), tone: 'soon', days: d };
    return { text: 'ساري', tone: 'ok', days: d };
  }
  function renewChip(row, now) {
    if (!row) return { text: '', tone: 'neutral', days: null };
    if (row.status === 'stopped') return { text: 'متوقف', tone: 'neutral', days: null };
    var d = daysUntil(row.renews_on, now);
    if (d === null) return { text: 'بلا موعد تجديد', tone: 'neutral', days: null };
    if (d < 0) return { text: 'فات موعد التجديد منذ ' + dayText(-d), tone: 'late', days: d };
    if (d === 0) return { text: 'يتجدد اليوم', tone: 'soon', days: 0 };
    if (d <= 7) return { text: 'يتجدد بعد ' + dayText(d), tone: 'soon', days: d };
    return { text: 'يتجدد ' + U.dateText(row.renews_on), tone: 'neutral', days: d };
  }
  function dealAction(row, now) {
    if (!row) return 'edit';
    if (row.status === 'ended') return 'renew';
    if (row.status === 'draft') return 'edit';
    var d = daysUntil(row.ends_on, now);
    if (d !== null && d <= 30) return 'renew';
    if (num(row.amount) > 0) return 'receive';
    return 'edit';
  }
  function subsSorted(list, now) {
    var act = [], stopped = [], undated = [];
    (Array.isArray(list) ? list : []).forEach(function (s) {
      if (s.status === 'stopped') stopped.push(s);
      else if (!s.renews_on) undated.push(s);
      else act.push(s);
    });
    act.sort(function (a, b) { return a.renews_on < b.renews_on ? -1 : a.renews_on > b.renews_on ? 1 : (a.id || 0) - (b.id || 0); });
    return act.concat(undated, stopped);
  }
  function agreementGroups(items, now) {
    var g = { ending: [], active: [], drafts: [], ended: [] };
    (Array.isArray(items) ? items : []).forEach(function (a) {
      if (a.status === 'ended') g.ended.push(a);
      else if (a.status === 'draft') g.drafts.push(a);
      else { var d = daysUntil(a.ends_on, now); (d !== null && d <= 30 ? g.ending : g.active).push(a); }
    });
    function byEnd(a, b) { var x = a.ends_on || '9999-12-31', y = b.ends_on || '9999-12-31'; return x < y ? -1 : x > y ? 1 : (a.id || 0) - (b.id || 0); }
    g.ending.sort(byEnd); g.active.sort(byEnd);
    return g;
  }
  function dealText(c) {
    if (!c) return '';
    var p = num(c.percent), f = num(c.fixed_amount);
    if (c.deal === 'percent') return 'نأخذ ' + fmt(p) + '٪ من دخل الحملة';
    if (c.deal === 'fixed_plus_percent') return 'مبلغ ثابت ' + moneyText(f, c.currency) + ' + ' + fmt(p) + '٪ من دخل الحملة';
    if (c.deal === 'fixed') return 'مبلغ ثابت ' + moneyText(f, c.currency);
    return 'أخرى: ' + (c.deal_other || '');
  }
  function dueOf(result) {
    var d = result && Array.isArray(result.due) ? result.due[0] : null;
    return d && num(d.amount) !== null ? d : null;
  }
  function statementText(c, r) {
    var due = dueOf(r), cnt = r && num(r.count);
    var lines = ['كشف حساب — ' + c.name, 'الفترة: ' + monthText(r.period), (c.count_label || 'عملاء جاؤوا من الحملة') + ': ' + (cnt === null || cnt === undefined ? 'غير مسجّل' : fmt(cnt))];
    if (c.deal !== 'fixed') lines.push('دخلكم من الحملة: ' + (num(r.income) === null ? 'غير مسجّل' : moneyText(r.income, c.currency)));
    lines.push('الاتفاق: ' + dealText(c));
    lines.push('المستحق للبروفيسور: ' + (due ? moneyText(due.amount, due.currency) : 'غير محسوب بعد'));
    lines.push('رقم الكشف: CO-' + c.id + '-' + r.period);
    return lines.join('\n');
  }

  // —— الشركاء: من الخام فقط (الملخّص تعذّر) ثم الدمج مع الملخّص
  function isReserve(p) { return p && (p.role === 'pool' || RESERVE_NAMES.indexOf(p.name) > -1); }
  function agreedOf(p) {
    var out = [];
    if (num(p.capital_egp) > 0) out.push({ currency: 'EGP', amount: num(p.capital_egp) });
    if (num(p.capital_usd) > 0) out.push({ currency: 'USD', amount: num(p.capital_usd) });
    return out;
  }
  function sumCur(pairs) {
    var acc = {};
    pairs.forEach(function (x) { if (x.amount) acc[x.currency] = (acc[x.currency] || 0) + Math.round(x.amount * 100); });
    return Object.keys(acc).sort(function (a, b) { return (a !== 'EGP') - (b !== 'EGP') || (a < b ? -1 : 1); }).map(function (k) { return { currency: k, amount: acc[k] / 100 }; });
  }
  function partnersFromRaw(partners) {
    if (!Array.isArray(partners)) return null;
    var rows = partners.map(function (p) {
      return { id: p.id, name: p.name, role: p.role, equity: num(p.equity_percent) || 0, reserve: !!isReserve(p), agreed: agreedOf(p), notes: p.notes || '' };
    });
    var all = []; rows.forEach(function (r) { r.agreed.forEach(function (a) { all.push(a); }); });
    return { rows: rows, equity_total: Math.round(rows.reduce(function (s, r) { return s + r.equity; }, 0) * 100) / 100, agreed_total: sumCur(all) };
  }
  // يدمج الخام مع الملخّص: الأسماء والأدوار من الخام، والمدفوع من الملخّص (إن وُجد). المدفوع مجهول ⇒ paidKnown=false ولا حقول مدفوع.
  function joinPartners(raw, summaryPartners) {
    var base = partnersFromRaw(raw);
    var sp = summaryPartners && Array.isArray(summaryPartners.rows) ? summaryPartners : null;
    if (!base && !sp) return null;
    if (!sp) { base.paidKnown = false; base.paid_total = null; base.any_contribution = null; return base; }
    if (!base) { return { rows: sp.rows.slice(), equity_total: sp.equity_total, agreed_total: sp.agreed_total, paid_total: sp.paid_total, any_contribution: !!sp.any_contribution, paidKnown: true }; }
    var byId = {}; sp.rows.forEach(function (r) { byId[r.id] = r; });
    base.rows.forEach(function (r) {
      var s = byId[r.id];
      r.paid = s ? s.paid : []; r.contributions = s ? s.contributions : 0; r.last_paid_at = s ? s.last_paid_at : null;
    });
    base.paid_total = sp.paid_total; base.any_contribution = !!sp.any_contribution; base.paidKnown = true;
    return base;
  }
  function legacySubs(assets) {
    return (Array.isArray(assets) ? assets : []).filter(function (a) { return LEGACY_CATS.indexOf(a.category) > -1 && num(a.monthly_rent_egp) > 0; });
  }

  // —— عقل الشركة: سطور من الحقائق فقط (حتى ٣)
  function brain(summary, now, extra) {
    var S = summary || {}, out = [];
    extra = extra || {};
    // ١) تغطية المصروف
    var mo = S.money;
    if (mo && num(mo.expenses) > 0 && num(mo.revenue) !== null) {
      var t;
      if (mo.revenue >= mo.expenses) {
        t = 'مصروف ' + monthText(mo.month) + ' كان ' + moneyText(mo.expenses, 'EGP') + '، والدخل غطّاه';
        if (mo.covered_since && mo.covered_since < mo.month) t += ' منذ ' + monthText(mo.covered_since);
        t += '.';
      } else {
        t = 'مصروف ' + monthText(mo.month) + ' كان ' + moneyText(mo.expenses, 'EGP') + '، والدخل غطّى ' + ar(Math.floor(mo.revenue / mo.expenses * 100)) + '٪ منه.';
      }
      out.push({ key: 'money', text: t, btn: 'افتح الفلوس', act: { section: 'money', tab: 'overview' } });
    }
    // ٢) اتفاق ينتهي خلال ٣٠ يومًا
    var ag = S.agreements && Array.isArray(S.agreements.ending) ? S.agreements.ending : null;
    var hit = null;
    if (ag) {
      ag.forEach(function (a) {
        var d = daysUntil(a.ends_on, now);
        if (d === null || d < 0 || d > 30) return;
        if (!hit || d < hit.d) hit = { a: a, d: d };
      });
    }
    if (hit) {
      var vis = extra.visits && hit.a.ref_code && num(extra.visits[hit.a.ref_code]) !== null ? num(extra.visits[hit.a.ref_code]) : null;
      var tx = 'اتفاق «' + hit.a.party + '» ' + (hit.d === 0 ? 'ينتهي اليوم' : 'ينتهي بعد ' + dayText(hit.d));
      if (vis !== null) tx += '، وجلب ' + U.U(vis, ['زيارة واحدة', 'زيارتين', 'زيارات', 'زيارة']);
      out.push({ key: 'agreement', text: tx + '.', btn: 'افتح الاتفاق', act: { tab: 'deals', id: hit.a.id } });
    } else {
      // ٢ب) اشتراك يتجدد خلال ٧ أيام أو فات موعده
      var nx = S.subscriptions && Array.isArray(S.subscriptions.next) ? S.subscriptions.next : null;
      var sh = null;
      if (nx) {
        nx.forEach(function (s) {
          var d = daysUntil(s.renews_on, now);
          if (d === null || d > 7) return;
          if (!sh || d < sh.d) sh = { s: s, d: d };
        });
      }
      if (sh) {
        var txt = sh.d < 0 ? 'فات موعد تجديد «' + sh.s.name + '» منذ ' + dayText(-sh.d) + '.'
          : 'اشتراك «' + sh.s.name + '» يتجدد ' + (sh.d === 0 ? 'اليوم' : 'بعد ' + dayText(sh.d)) + ' بمبلغ ' + moneyText(sh.s.amount, sh.s.currency) + '.';
        out.push({ key: 'subscription', text: txt, btn: 'سجّل الدفع', act: { tab: 'assets', id: sh.s.id, do: 'paid' } });
      }
    }
    // ٣) شركاء باقٍ عليهم
    var P = S.partners && Array.isArray(S.partners.rows) ? S.partners : null;
    if (P) {
      var owing = [], rest = [];
      P.rows.forEach(function (r) {
        if (r.reserve || !r.contributions) return;
        var rem = remaining(r.agreed, r.paid);
        if (rem.length) { owing.push(r); rem.forEach(function (x) { rest.push(x); }); }
      });
      if (owing.length) {
        var n = owing.length, sum = sumLines(sumCur(rest)), tp;
        if (n === 1) tp = 'شريك واحد باقٍ عليه ' + sum + ' من حصته.';
        else if (n === 2) tp = 'شريكان باقٍ عليهما ' + sum + ' من حصتيهما.';
        else tp = (n <= 10 ? ar(n) + ' شركاء' : ar(n) + ' شريكًا') + ' باقٍ عليهم ' + sum + ' من حصصهم.';
        out.push({ key: 'owing', text: tp, btn: 'سجّل دفعة', act: { tab: 'partners', do: 'contribution' } });
      } else if (!P.any_contribution && P.rows.some(function (r) { return !r.reserve; })) {
        out.push({ key: 'nopaid', text: 'لم تُسجَّل دفعات الشركاء بعد، فالمدفوع من رأس المال غير معروف.', btn: 'سجّل دفعة', act: { tab: 'partners', do: 'contribution' } });
      }
    }
    // ٤) كشوف حساب جاهزة
    var AC = S.ad_clients;
    if (AC && num(AC.unsent) > 0) {
      var k = AC.unsent, due = sumLines(AC.due_unsent);
      var head = k === 1 ? 'كشف حساب واحد جاهز' : k === 2 ? 'كشفا حساب جاهزان' : k <= 10 ? ar(k) + ' كشوف حساب جاهزة' : ar(k) + ' كشف حساب جاهزة';
      out.push({ key: 'statements', text: head + ' للإرسال' + (due ? '، والمستحق لنا ' + due : '') + '.', btn: 'جهّز الكشوف', act: { tab: 'ads', do: 'statements' } });
    }
    // ٥) مجموع الحصص
    if (P && P.rows.length && num(P.equity_total) !== null && Math.abs(P.equity_total - 100) > 0.05) {
      out.push({ key: 'equity', text: 'مجموع الحصص المسجّلة ' + fmt(P.equity_total) + '٪.', btn: 'راجع الحصص', act: { tab: 'partners' } });
    }
    return out.slice(0, 3);
  }

  // —— الأهداف الشهرية
  function fcRows(forecast) { return Array.isArray(forecast) ? forecast.filter(function (f) { return f && /^\d{4}-\d{2}$/.test(f.month || ''); }).sort(function (a, b) { return a.month < b.month ? -1 : 1; }) : null; }
  function currentTarget(forecast, now) {
    var rows = fcRows(forecast); if (!rows) return null;
    var k = nowKey(now), cur = rows.filter(function (r) { return r.month === k; })[0];
    if (cur) return cur;
    return rows.filter(function (r) { return r.month > k; })[0] || null;
  }
  function dashMonth(dash, key) {
    var m = dash && Array.isArray(dash.monthly) ? dash.monthly : null;
    if (!m) return undefined;                                                  // المصدر غير متاح
    var r = m.filter(function (x) { return x.month === key; })[0];
    if (!r && m.length >= 12) {                                                // النافذة آخر ١٢ شهرًا: شهر أقدم منها خارج المصدر لا «بلا دخل»
      var first = m.map(function (x) { return x.month; }).sort()[0];
      if (key < first) return undefined;
    }
    return r ? num(r.revenue) : null;                                          // null = لا صف لهذا الشهر
  }
  function monthLine(forecast, dash, now) {
    var rows = fcRows(forecast), k = nowKey(now);
    if (!dash || !Array.isArray(dash.monthly)) return { kind: 'na', text: 'دخل هذا الشهر غير متاح بعد.' };
    if (!rows) return { kind: 'na', text: 'الأهداف الشهرية غير متاحة بعد.' };
    var row = rows.filter(function (r) { return r.month === k; })[0];
    var target = row ? num(row.revenue_egp) : null;
    if (!row || !(target > 0)) return { kind: 'notarget', text: 'لم يُحدَّد هدف دخل لهذا الشهر.' };
    var actual = dashMonth(dash, k), name = monthName(k);
    if (actual === null) return { kind: 'target', text: 'لم يُسجَّل دخل في ' + name + ' حتى الآن، وهدفه ' + moneyText(target, 'EGP') + '.' };
    return { kind: 'target', text: 'دخل ' + name + ' حتى الآن ' + moneyText(actual, 'EGP') + ' من هدف ' + moneyText(target, 'EGP') + ' (' + ar(Math.round(actual / target * 100)) + '٪).' };
  }
  function targetRows(forecast, dash, now) {
    var rows = fcRows(forecast); if (!rows) return null;
    var k = nowKey(now);
    return rows.slice().map(function (f) {
      var future = f.month > k, actual;
      if (future) actual = undefined;
      else actual = dashMonth(dash, f.month);                                  // undefined ⇒ المصدر غير متاح · null ⇒ لا دخل مسجّل
      return { id: f.id, month: f.month, monthText: monthText(f.month), target: num(f.revenue_egp), actual: actual, future: future, na: !future && actual === undefined,
               courses: num(f.target_courses), students: num(f.target_students), raw: f };
    });
  }
  function monthOptions(now, mode) {
    var d = new Date(now || 0), y = d.getFullYear(), m = d.getMonth();
    var def, years;
    if (mode === 'target') { var nx = new Date(y, m + 1, 1); def = nx.getFullYear() + '-' + (nx.getMonth() + 1 < 10 ? '0' : '') + (nx.getMonth() + 1); years = [y]; if (nx.getFullYear() !== y) years.push(nx.getFullYear()); else years.push(y + 1); }
    else { var pv = new Date(y, m - 1, 1); def = pv.getFullYear() + '-' + (pv.getMonth() + 1 < 10 ? '0' : '') + (pv.getMonth() + 1); years = [y, y - 1]; }
    return { months: MONTHS.map(function (t, i) { return { v: (i + 1 < 10 ? '0' : '') + (i + 1), t: t }; }), years: years, def: def };
  }
  function currentCounts(dash, target) {
    var c = dash && dash.courses ? dash.courses : null;
    return c ? { courses: num(c.total_courses), students: num(c.total_students) } : null;
  }

  L.co = {
    NA: NA, naText: NA, MONTHS: MONTHS, ROLE_LABEL: ROLE_LABEL, CAT_LABEL: CAT_LABEL, STATUS_LABEL: STATUS_LABEL, KIND_LABEL: KIND_LABEL, CYCLE_LABEL: CYCLE_LABEL,
    daysUntil: daysUntil, dayText: dayText, monthText: monthText, monthName: monthName, nowKey: nowKey, sumLines: sumLines, remaining: remaining,
    partnerChip: partnerChip, agreementChip: agreementChip, renewChip: renewChip, dealAction: dealAction, subsSorted: subsSorted, agreementGroups: agreementGroups,
    dealText: dealText, statementText: statementText, dueOf: dueOf, partnersFromRaw: partnersFromRaw, joinPartners: joinPartners, isReserve: isReserve,
    legacySubs: legacySubs, brain: brain, currentTarget: currentTarget, monthLine: monthLine, targetRows: targetRows, monthOptions: monthOptions, currentCounts: currentCounts
  };
})(typeof window !== 'undefined' ? window : (typeof globalThis !== 'undefined' ? globalThis : this));

// ===== v2s:home =====
// «اللوحة + كل الوارد + الدرج + الجرس» (الجولة النهائية). ⛔ نقي: لا DOM ولا شبكة. عدد غير معروف ⇒ null/"" لا صفر.
(function (root) {
  'use strict';
  var L = root.V2L;
  if (!L) return;
  var ar = L.util.ar, U = L.util.U;
  function str(v) { return typeof v === 'string' ? v.trim() : ''; }
  function finite(n) { return typeof n === 'number' && isFinite(n); }
  function toArDigits(s) { return String(s).replace(/\d/g, function (d) { return '٠١٢٣٤٥٦٧٨٩'.charAt(+d); }); }

  // ---------------------------------------------------------------- الشرائح
  var CHIP_LABEL = { all: 'الكل', late: 'تجاوز المهلة', 't:files': 'ملفات الخبراء', 't:disputes': 'النزاعات', 't:legacy': 'استشارات قديمة',
    't:money': 'إيصالات التحويل', 't:decisions': 'طلبات انضمام واعتماد', 't:verify': 'توثيق', 't:messages': 'الرسائل', 't:other': 'أخرى',
    auto: 'عولجت تلقائيًا', attn: 'يحتاج تدخّلك', review: 'ينتظر مراجعتك', urgent: 'مستعجل', nocand: 'لا خبير متاح',
    contract: 'مراجعة عقود', 'case': 'قضايا عليها ملاحظة' };
  var CHIP_CTX = {
    home: { row1: ['all', 'late', 't:files', 't:disputes', 't:legacy', 't:money', 't:decisions', 't:verify', 't:messages', 't:other', 'auto'], row2: [] },
    files: { row1: ['t:files', 'late'], row2: ['attn', 'review', 'urgent', 'nocand', 'contract', 'case'] },
    disputes: { row1: ['t:disputes', 't:legacy'], row2: [] },
    messages: { row1: [], row2: [] }
  };
  var CTX_LABEL = { files: { 't:files': 'كل الملفات' } };
  function ctxOf(c) { return CHIP_CTX[c] ? c : 'home'; }
  function v2hChipKeys(ctx) { var d = CHIP_CTX[ctxOf(ctx)]; return d.row1.concat(d.row2); }
  function v2hChips(ctx, counts, active) {
    ctx = ctxOf(ctx); counts = counts || {};
    var d = CHIP_CTX[ctx];
    function mk(key) {
      var n = Number(counts[key]); if (!isFinite(n) || n < 0) n = 0;
      var on = key === active;
      if (n === 0 && !on && key !== 'all') return null;
      return { key: key, label: (CTX_LABEL[ctx] && CTX_LABEL[ctx][key]) || CHIP_LABEL[key] || 'أخرى', n: n, text: ar(n), on: on, tone: key === 'late' ? 'late' : '' };
    }
    return { row1: d.row1.map(mk).filter(Boolean), row2: d.row2.map(mk).filter(Boolean) };
  }

  // ---------------------------------------------------------------- التذكرة
  var MONEY_KINDS = { payout: 1, manual_payment: 1, stuck_payment: 1, unactivated: 1, legacy: 1 };
  function kindOfItem(row, card) { return (card && card.kind) || (row && row.apiKind) || ''; }
  function v2hTone(row, card, isLate) {
    if (isLate) return 'late';
    if (MONEY_KINDS[kindOfItem(row, card)]) return 'money';
    if (row && row.triage === 'auto') return 'done';
    return 'wait';
  }
  function v2hFlags(row) {
    var out = [];
    if (!row) return out;
    if (row.urgent) out.push({ t: 'مستعجل' });
    if (row.contract) out.push({ t: 'مراجعة عقد' });
    if (row.noCandidate) out.push({ t: 'لا خبير متاح' });
    if (row.needsAttention) out.push({ t: 'يحتاج تدخّلك' });
    if (row.licenceMissing) out.push({ t: 'خدمة مرخّصة بلا رقم قيد' });
    else if (row.licensed) out.push({ t: 'خدمة مرخّصة' });
    if (Array.isArray(row.flagLabels) && row.flagLabels.length) out.push({ t: 'حساب عليه علامات', tip: row.flagLabels.join(' · ') });
    if (row.msgSource === 'site') out.push({ t: 'من الموقع' });
    else if (row.msgSource) out.push({ t: 'من المنصة' });
    // شارات الصف القديم (أعلام السعر · «أقل من ١٢ ساعة» · «خبير اعتذر» · التخصص): كانت تظهر في القائمة فلا تضيع منها.
    // ما كررته أعلام الصف أعلاه (مستعجل · مراجعة عقد · لا خبير متاح · يحتاج تدخّلك) يُحذف، والتحذيرية (`w`) تأخذ نبرة التحذير.
    if (Array.isArray(row.badges)) {
      row.badges.forEach(function (b) {
        var t = b && str(b.t).replace(/^[^؀-ۿA-Za-z0-9]+/, '').trim();
        if (!t || b.attn) return;
        if (row.urgent && t.indexOf('مستعجل') > -1) return;
        if (row.noCandidate && t.indexOf('خبير متاح') > -1) return;
        if (row.contract && /عقد/.test(t + ' ' + str(b.tip))) return;
        t = copyOr(t);
        if (out.some(function (o) { return o.t === t; })) return;
        var f = { t: t };
        if (b.tip) f.tip = copyOr(str(b.tip));
        if (b.w) f.w = true;
        out.push(f);
      });
    }
    return out;
  }
  // سبب وقوف الفلوس (سطر أحمر في الصف القديم) — نص المنصة كما وصل، يُعرض في التذكرة سطرًا واحدًا.
  function v2hWarn(row) {
    var t = row ? str(row.warnLine) : '';
    var c = t && L.v2hCopy ? L.v2hCopy(t, true) : null;       // جمل المنصة المعروفة تُترجم بالعبارات الطويلة وحدها
    return c == null ? t : c;
  }
  var GROUP_LABEL = { late: 'متأخر', wait: 'ينتظر قرارك', auto: 'عولجت تلقائيًا' };
  var GROUP_ORDER = ['late', 'wait', 'auto'];
  function groupKeyOf(it) {
    var tone = it.tone || v2hTone(it.row, it.card, !!it.late);
    if (tone === 'late') return 'late';
    return (it.row && it.row.triage === 'auto') ? 'auto' : 'wait';
  }
  function v2hGroups(items) {
    var buckets = { late: [], wait: [], auto: [] };
    (items || []).forEach(function (it, idx) {
      var rank = it.card && finite(it.card.group) ? it.card.group : 999;
      var ts = it.card && finite(it.card.ts) ? it.card.ts : Infinity;
      buckets[groupKeyOf(it)].push({ it: it, rank: rank, ts: ts, idx: idx });
    });
    return GROUP_ORDER.map(function (k) {
      var arr = buckets[k].sort(function (a, b) {
        if (a.rank !== b.rank) return a.rank - b.rank;
        if (a.ts !== b.ts) return a.ts < b.ts ? -1 : 1;     // Infinity آخرًا
        return a.idx - b.idx;
      });
      return { key: k, label: GROUP_LABEL[k], items: arr.map(function (x) { return x.it; }) };
    }).filter(function (g) { return g.items.length; });
  }
  function v2hSegs(items, seg) {
    var n = { late: 0, wait: 0, auto: 0 };
    (items || []).forEach(function (it) { n[groupKeyOf(it)]++; });
    var active = seg;
    if (GROUP_ORDER.indexOf(active) < 0) {
      active = 'late';
      for (var i = 0; i < GROUP_ORDER.length; i++) if (n[GROUP_ORDER[i]]) { active = GROUP_ORDER[i]; break; }
    }
    return { segs: GROUP_ORDER.map(function (k) { return { key: k, label: GROUP_LABEL[k], n: n[k], text: ar(n[k]), on: k === active }; }), active: active };
  }

  // الزر الواحد في التذكرة
  // ملاحظة: في درج الوارد زرّا الإيصال هما approve/reject (pay_ok/pay_no في درج «الضمان» القديم وحده).
  var V2H_ACT_TO_DRAWER = { send: 'ef_pick', pay_confirm: 'approve', pay_reject: 'reject', decide: 'approve', resolve: 'resolve' };
  var DECISION_ACTS = { send: 1, decide: 1, resolve: 1, pay_confirm: 1, pay_reject: 1, payout_settle: 1, payout_reject: 1, offer_approve: 1, offer_reject: 1, escrow: 1 };
  var GENERIC_BTN = 'افتح وقرّر';
  function copyOr(s) { var c = L.v2hCopy ? L.v2hCopy(s) : null; return c == null ? s : c; }
  function v2hTicketBtn(card) {
    var p = card && card.primary;
    if (!p || !p.act || !str(p.label)) return { label: GENERIC_BTN, drawerA: null };
    var d = p.act.do;
    if (d === 'open' || DECISION_ACTS[d]) {
      return { label: copyOr(str(p.label)), drawerA: DECISION_ACTS[d] ? (V2H_ACT_TO_DRAWER[d] || null) : null };
    }
    return { label: GENERIC_BTN, drawerA: null };
  }

  // ---------------------------------------------------------------- البحث
  function v2hNorm(s) {
    return String(s == null ? '' : s).toLowerCase()
      .replace(/[ً-ٰٟـ]/g, '')
      .replace(/[أإآٱ]/g, 'ا').replace(/ة/g, 'ه').replace(/ى/g, 'ي')
      .replace(/[٠-٩]/g, function (d) { return String(d.charCodeAt(0) - 0x660); })
      .replace(/[۰-۹]/g, function (d) { return String(d.charCodeAt(0) - 0x6F0); })
      .replace(/\s+/g, ' ').trim();
  }
  function v2hSearchText(row, destLabel, card) {
    row = row || {};
    return [row.out, row.from, row.who, row.serviceLabel, row.email, row.searchText, destLabel, card && card.tag, card && card.title]
      .filter(function (x) { return x != null && x !== ''; }).join(' ');
  }

  // ---------------------------------------------------------------- سطر العقل
  function titleOf(it) { return (it.card && it.card.title) || (it.row && it.row.who) || 'بند ينتظر قرارك'; }
  function ageOf(it) { return (it.card && it.card.ageText) || ''; }
  function oldestOf(list) {
    var best = null;
    list.forEach(function (it) {
      var t = it.card && finite(it.card.ts) ? it.card.ts : Infinity;
      if (t !== Infinity && (!best || t < best.t)) best = { t: t, it: it };
    });
    return best && best.it;
  }
  function v2hBrainLine(items, brainLogLen, state) {
    if (state === 'error' || state === 'loading') return null;
    items = items || [];
    var late = items.filter(function (it) { return groupKeyOf(it) === 'late'; });
    var waiting = items.filter(function (it) { return groupKeyOf(it) !== 'auto'; });
    var base = null, o;
    if (late.length) {
      base = U(late.length, ['بند متأخر واحد', 'بندان متأخران', 'بنود متأخرة', 'بندًا متأخرًا']);
      o = oldestOf(late);
      if (o) base += ' — أقدمها «' + titleOf(o) + '»' + (ageOf(o) ? ' ' + ageOf(o) : '');
    } else if ((o = oldestOf(waiting))) {
      base = 'أقدم ما ينتظرك: «' + titleOf(o) + '»' + (ageOf(o) ? ' ' + ageOf(o) : '');
    } else if (!waiting.length && state === 'ready') {
      base = 'لا شيء ينتظرك في الوارد الآن';
    }
    var n = Number(brainLogLen);
    var suffix = (isFinite(n) && n > 0) ? 'وزّع العقل ' + U(n, ['ملفًا واحدًا', 'ملفين', 'ملفات', 'ملفًا']) + ' اليوم' : '';
    if (base && suffix) return base + ' · ' + suffix;
    return base || suffix || null;
  }

  // ---------------------------------------------------------------- أرقام المنصة
  var QUEUE_LABEL = {
    trainer_applications_pending: 'طلبات مدرّبين', courses_pending: 'دورات تنتظر الاعتماد', manual_payments_pending: 'إيصالات تحويل',
    expert_files_in_review: 'آراء تنتظر مراجعتك', expert_files_awaiting_assignment: 'ملفات تنتظر التوزيع',
    expert_files_assign_overdue: 'ملفات لم تُستلم منذ ١٢ ساعة', expert_files_late: 'آراء متأخرة',
    expert_files_disputed: 'ملفات عليها ملاحظة من صاحب الطلب', consultation_disputes: 'نزاعات على استشارات',
    consultations_legacy: 'استشارات قديمة تنتظر قرارك', expert_files_blocked: 'ملفات توقفت أموالها',
    expert_files_unactivated: 'ملفات دُفعت ولم تصل إلى التوزيع', wallet_payouts_pending: 'طلبات سحب من المحافظ',
    stuck_card_payments: 'دفعات بطاقة عالقة', course_interests_24h: 'اهتمام بالدورات في آخر ٢٤ ساعة',
    training_interests_24h: 'مهتمون بالتدريب في آخر ٢٤ ساعة', course_split_pending: 'اقتسام إيراد معلّق',
    testimonials_pending: 'شهادات تنتظر المراجعة', topics_drafts: 'مسودات موضوعات', founding_leads_new: 'طلبات خبير مؤسس جديدة',
    pending_users_requested: 'زوّار ينتظرون فتح المنصة', lead_magnet_awaiting_asset: 'ملفات وُعد بها ولم تُسلَّم',
    live_needs_decision: 'دورات حيّة تحتاج قرارًا'
  };
  function v2hQueueLabel(key) { return Object.prototype.hasOwnProperty.call(QUEUE_LABEL, key) ? QUEUE_LABEL[key] : 'بند من المنصة'; }

  // ---------------------------------------------------------------- الجرس
  function v2hAlertSection(text) {
    var s = String(text == null ? '' : text);
    if (/نزاع|استشار(ة|ات|تان)\s+قديم|حجز|حجوز/.test(s)) return 'disputes';
    if (/ملف|رأي|آراء/.test(s)) return 'files';
    if (/الالتحاق/.test(s)) return 'courses';
    return null;
  }
  var NOTIF_DEST = { message: { section: 'people', tab: 'messages' }, withdrawal: { section: 'company', tab: 'invest' },
    trainer_application: { section: 'courses', tab: 'trainers' }, program_request: { section: 'courses', tab: 'courses' },
    signup: { section: 'people', tab: 'users' } };
  var NOTIF_TITLE = { message: 'رسالة جديدة من نموذج التواصل', withdrawal: 'طلب سحب من مستثمر ينتظر المراجعة',
    trainer_application: 'طلب انضمام مدرّب جديد', program_request: 'طلب برنامج أو دورة ينتظر المراجعة', signup: 'حساب جديد على المنصة' };
  function v2hNotif(item) {
    item = item || {};
    var kind = str(item.kind), detail = str(item.detail);
    var title;
    if (NOTIF_TITLE[kind]) title = NOTIF_TITLE[kind];
    else { var t = str(item.title); title = (t && !/[A-Za-z]/.test(t)) ? t : 'إشعار'; }
    if (kind === 'withdrawal') {
      detail = toArDigits(detail.replace(/\s*USD\s*$/i, ' دولار').replace(/(\d)\.(\d)/g, '$1٫$2'));
    } else if (kind === 'trainer_application') detail = detail.replace(/\s*بانتظار الموافقة\s*$/, '');
    else if (kind === 'signup') detail = detail.replace(/\s*أنشأ حسابًا\s*$/, '');
    return { id: String(item.id == null ? '' : item.id), kind: kind, title: title, detail: detail, when: item.when || item.created_at || null,
      unread: item.unread !== false, dest: NOTIF_DEST[kind] ? { section: NOTIF_DEST[kind].section, tab: NOTIF_DEST[kind].tab } : null };
  }
  function v2hNotifList(reply) {
    var list = Array.isArray(reply) ? reply : (reply && Array.isArray(reply.items) ? reply.items : (reply && Array.isArray(reply.notifications) ? reply.notifications : null));
    if (!list) return null;
    return list.filter(function (x) { return x && typeof x === 'object'; }).map(v2hNotif);
  }
  function seenHas(seen, id) {
    if (!seen) return false;
    if (Array.isArray(seen)) return seen.indexOf(id) > -1;
    return !!seen[id];
  }
  function v2hBellBadge(health, notifs, seen) {
    var hFailed = !!(health && health.failed);
    var hAlerts = !!(health && !health.failed && health.alerts && health.alerts.length);
    var nFailed = notifs === null;
    var unseen = Array.isArray(notifs) ? notifs.filter(function (n) { return n.unread && !seenHas(seen, n.id); }).length : 0;
    if (hFailed && nFailed) return { text: '!', tone: 'warn', dot: false };
    var dot = hFailed || hAlerts || nFailed;
    var text = unseen > 0 ? ar(unseen) : '';
    return { text: text, tone: text ? 'count' : (dot ? 'warn' : 'none'), dot: dot };
  }

  // ---------------------------------------------------------------- سطر الصحة وشرائط الوارد
  function v2hHealthLine(src, health) {
    if (src === 'idle' || src === 'loading') return { text: 'حالة المنصة: جارٍ الفحص…', tone: 'ld' };
    if (src === 'error' || !health || health.failed) return { text: 'حالة المنصة: تعذّر الفحص — افتح التنبيهات', tone: 'bad' };
    if (health.ok) return { text: 'حالة المنصة: كل شيء يعمل', tone: 'ok' };
    return { text: 'حالة المنصة: ' + U(health.alerts.length, ['تنبيه واحد', 'تنبيهان', 'تنبيهات', 'تنبيهًا']) + ' — افتح التنبيهات', tone: 'warn' };
  }
  function v2hServiceLine(mode, n) {
    if (mode === 'closed') return 'خدمة «ملف للخبير» متوقفة للناس الآن، والأموال لا تتحرك تلقائيًا. الملفات المفتوحة ما زالت هنا: يمكنك إعادة أموالها أو حسم نزاعها، ولا يمكن إرسالها إلى خبير.';
    if (mode === 'allowlist') {
      var who = finite(n) && n >= 0 ? ' (' + U(n, ['حساب واحد', 'حسابان', 'حسابات', 'حسابًا']) + ')' : '';
      return 'الخدمة مفتوحة للتجربة فقط' + who + ' — يُرسل الملف فقط إلى خبير من قائمة التجربة، وترفض المنصة غير ذلك.';
    }
    return '';
  }
  function v2hAutoLine(on) {
    if (on === true) return { head: 'التوزيع التلقائي يعمل', body: 'يُرسل كل ملف مدفوع وحده إلى أنسب خبير متاح، ويمكنك تغيير الخبير في أي وقت.', btn: 'أوقفه',
      confirm: 'إذا أوقفت التوزيع التلقائي، سينتظر كل ملف يُدفع بعد الآن أن توزّعه بنفسك، ولن تُرسل الملفات المنتظرة الآن وحدها. هل توقفه؟' };
    if (on === false) return { head: 'التوزيع التلقائي متوقف', body: 'الملفات المدفوعة تنتظر أن توزّعها بنفسك. إذا شغّلته يُرسل كل ملف مدفوع ومنتظر وحده.', btn: 'شغّله', confirm: '' };
    return null;
  }
  function v2hFyiLine(n, autoOn, viewing) {
    if (viewing) return 'هذه ملفات أُرسلت إلى خبير وما زالت ضمن مهلته — لا تحتاج منك شيئًا الآن.';
    var tail = autoOn === true ? 'إن لم يُستلم يُرسل إلى خبير آخر تلقائيًا.' : 'إن لم يُستلم يعود إلى هنا.';
    return 'للعلم: ' + U(n, ['ملف واحد أُرسل', 'ملفان أُرسلا', 'ملفات أُرسلت', 'ملفًا أُرسل']) + ' إلى خبير وما زال ضمن مهلة الاثنتي عشرة ساعة، ولا يحتاج منك شيئًا الآن. ' + tail;
  }

  // ---------------------------------------------------------------- طبقة النصوص (فصحى بسيطة بدل العامية في الدرج والنوافذ)
  var V2H_COLLOQUIAL = ['مش ', 'دلوقتي', 'اتبعت', 'اتدفع', 'اتستلم', 'بتاع', 'عايز', 'هيت', 'ابعته', 'رجّع', 'مستني', 'لوحده', 'لوحدها', 'إيه', ' ليه', 'كده', 'اللي', 'تاني', 'مالهاش', 'بقى', 'إزاي', 'خالص', 'يقوّم', 'الحاجة الجاية', 'لسه مقفولة'];
  var COPY_EXACT = {};
  var COPY_RULES = [];
  var COPY_PHRASES = [];
  function exact(map) { Object.keys(map).forEach(function (k) { COPY_EXACT[k] = map[k]; }); }
  function rule(re, to) { COPY_RULES.push([re, to]); }
  function v2hCopy(text, strict) {
    if (typeof text !== 'string' || !text) return null;
    var m = /^(\s*)([\s\S]*?)(\s*)$/.exec(text);
    var lead = m[1], core = m[2], trail = m[3];
    if (!core) return null;
    if (Object.prototype.hasOwnProperty.call(COPY_EXACT, core)) {
      var ex = COPY_EXACT[core];
      return ex === core ? null : lead + ex + trail;
    }
    var cur = core, i;
    for (i = 0; i < COPY_RULES.length; i++) {           // قواعد التعبيرات على النص بلا فراغات الأطراف (لها ^ و$)
      var r = COPY_RULES[i];
      if (r[0].test(cur)) cur = cur.replace(r[0], r[1]);
      r[0].lastIndex = 0;
    }
    var full = lead + cur + trail;                       // العبارات تُطابَق على النص كاملًا (بفراغاته: «هترجّع » قبل المبلغ)
    for (i = 0; i < COPY_PHRASES.length; i++) {
      if (strict && COPY_PHRASES[i][0].trim().length < 12) continue;       // نصوص المنصة وكلام الناس: العبارات الطويلة وحدها
      if (full.indexOf(COPY_PHRASES[i][0]) > -1) full = full.split(COPY_PHRASES[i][0]).join(COPY_PHRASES[i][1]);
    }
    return full === text ? null : full;
  }
  L.__copyDict = { exact: exact, rule: rule, EXACT: COPY_EXACT, RULES: COPY_RULES, PHRASES: COPY_PHRASES };

  L.V2H_COLLOQUIAL = V2H_COLLOQUIAL;
  L.V2H_ACT_TO_DRAWER = V2H_ACT_TO_DRAWER;
  L.v2hChips = v2hChips; L.v2hChipKeys = v2hChipKeys; L.v2hTone = v2hTone; L.v2hFlags = v2hFlags; L.v2hWarn = v2hWarn; L.v2hGroups = v2hGroups; L.v2hSegs = v2hSegs;
  L.v2hTicketBtn = v2hTicketBtn; L.v2hNorm = v2hNorm; L.v2hSearchText = v2hSearchText; L.v2hBrainLine = v2hBrainLine;
  L.v2hQueueLabel = v2hQueueLabel; L.v2hAlertSection = v2hAlertSection; L.v2hNotif = v2hNotif; L.v2hNotifList = v2hNotifList;
  L.v2hBellBadge = v2hBellBadge; L.v2hHealthLine = v2hHealthLine; L.v2hServiceLine = v2hServiceLine; L.v2hAutoLine = v2hAutoLine;
  L.v2hFyiLine = v2hFyiLine; L.v2hCopy = v2hCopy; L.v2hToArDigits = toArDigits;
  L.V2H_GENERIC_BTN = GENERIC_BTN;
  // (قاموس النصوص في `v2s/home_copy.js`: بيسجّل مفاتيحه عبر `L.__copyDict`؛ الملف ده ما فيهوش عامية)
})(typeof window !== 'undefined' ? window : globalThis);
// ===== /v2s:home =====

// ===== v2s:courses =====
// «الدورات والمدرّبون» (الجولة الأخيرة): منطق نقي بلا DOM ولا شبكة. المصدر الذي تعذّر جلبه يصل `null` ويعود `null`/`na` — لا صفرًا.
// ⛔ لا حكم ولا رقم مخترع: كل سطر للعقل يُبنى من حقول موجودة، وما لا مصدر له يُكتب «غير متاح بعد».
(function (root) {
  var L = root.V2L || (typeof module !== 'undefined' && module.exports);
  if (!L) return;
  var U = L.util;
  var HOURMS = 3600e3;
  var WARN_H = 24, LATE_H = 72;
  L.v2s = L.v2s || {};

  function s(v) { return typeof v === 'string' ? v.trim() : ''; }
  function num(v) { var n = typeof v === 'number' ? v : (typeof v === 'string' && v.trim() !== '' ? Number(v) : NaN); return isFinite(n) ? n : null; }
  function tms(v) { if (typeof v === 'number') return isFinite(v) && v > 0 ? v : NaN; var t = Date.parse(v || ''); return isNaN(t) ? NaN : t; }
  function arr(v) { return Array.isArray(v) ? v : null; }
  function cmpAr(a, b) { return String(a || '').localeCompare(String(b || ''), 'ar'); }
  function nonEmpty(v) { return s(v) !== ''; }

  var NA = 'غير متاح بعد';
  var TYPE_LABEL = { recorded_paid: 'مسجّلة مدفوعة', recorded_free: 'مسجّلة مجانية', live_upcoming: 'حيّة' };
  var SOURCE_LABEL = { dashboard: 'أنشأتها الإدارة', native: 'من بناء المدرّب', 'story-seed': 'دورة تفاعلية', titch: 'منهج مكتوب' };
  var STATE_LABEL = { published: 'منشورة', review: 'في المراجعة', building: 'تحت البناء', rejected: 'أُعيدت', archived: 'مؤرشفة' };
  var SEG_LABEL = { individual: 'أفراد', employee: 'موظفون', government: 'حكومي', student: 'طلاب', lawyer: 'محامون', senior: 'محامٍ خبير', prof: 'أستاذ جامعة',
                    trainer: 'مدرّبون', company: 'شركات', firm: 'شركة محاماة', grad: 'خريج جديد', influencer: 'مؤثر/رائد أعمال', researcher: 'باحثون',
                    prosecutor: 'وكلاء نيابة', unknown: 'فرد' };

  // حالة الدورة على اللوحة (§3.3): review | published | building | rejected | archived
  function stateOf(c) {
    if (!c) return 'building';
    if (c.approval_status === 'pending') return 'review';
    if (c.is_active === true) return 'published';
    if (s(c.archived_at)) return 'archived';
    if (c.approval_status === 'rejected') return 'rejected';
    return 'building';
  }
  function lessonsOf(c) {
    var st = c && c.story;
    if (st && num(st.lessons) > 0) return num(st.lessons);
    var n = num(c && c.lesson_count);
    return n == null ? 0 : n;
  }
  // دورة منشورة لا تظهر للناس بعد: مسجّلة (مدفوعة أو مجانية) بلا درس واحد. الحيّة والتفاعلية لها طريقها.
  function hiddenFromPublic(c) { return !!c && c.type !== 'live_upcoming' && !c.story && lessonsOf(c) === 0; }
  function lessonsPhrase(n) { return n > 0 ? U.U(n, ['درس واحد', 'درسان', 'دروس', 'درسًا']) : 'لا دروس بعد'; }
  function trainerOf(c) {
    if (c && c.platform_owned === true) return 'البروفيسور';
    return s(c && c.instructor_name) || 'بلا اسم مدرّب';
  }
  function priceOf(c) {
    if (!c) return { free: false, text: NA, ok: null };
    if (c.type === 'recorded_free') return { free: true, text: 'مجانية', short: 'مجانية', ok: true };
    var a = num(c.price_amount);
    if (a != null && a > 0) return { free: false, text: U.fmt(a) + ' ' + U.curLong(c.price_currency || 'EGP'), short: U.moneyText(a, c.price_currency || 'EGP'), ok: true };
    return { free: false, text: 'بلا سعر', short: 'بلا سعر', ok: false };
  }
  function hoursSince(at, now) { var t = tms(at); return isNaN(t) ? null : Math.max(0, Math.floor(((now || 0) - t) / HOURMS)); }

  function tone(h) { return h < WARN_H ? 'ok' : (h <= LATE_H ? 'warn' : 'late'); }
  // العدّاد: الوقت المنتظَر لا يُحسب إلا من `submitted_at`؛ عمر الدورة (`created_at`) يُكتب عمرًا بلا لون.
  function reviewTimer(c, now) {
    if (!c) return null;
    var sub = tms(c.submitted_at);
    if (!isNaN(sub)) return { at: sub, label: L.v2TimerText({ mode: 'since', at: sub }, now), tone: tone(hoursSince(sub, now)) };
    var cr = tms(c.created_at);
    if (!isNaN(cr)) return { at: cr, label: 'أُنشئت ' + L.v2TimerText({ mode: 'since', at: cr }, now), tone: 'none' };
    return null;
  }
  function cover(title) {
    var m = String(title == null ? '' : title).match(/[ء-يٱ-ۓA-Za-z]/);
    return { letter: m ? m[0] : '؟' };
  }

  function summaryLine(counts) {
    if (!counts) return 'الدورات: ' + NA;
    var wait = counts.review > 0 ? U.U(counts.review, ['دورة واحدة تنتظرك', 'دورتان تنتظرانك', 'دورات تنتظرك', 'دورة تنتظرك']) : 'لا شيء ينتظرك';
    return [U.U(counts.published, ['دورة واحدة منشورة', 'دورتان منشورتان', 'دورات منشورة', 'دورة منشورة']), U.ar(counts.building) + ' تحت البناء', wait].join(' · ');
  }
  function board(courses, opts) {
    opts = opts || {};
    if (!arr(courses)) return { na: true, review: [], building: [], published: [], hidden: [], archived: [], rejected: [], counts: null, summary: summaryLine(null) };
    var out = { review: [], building: [], published: [], hidden: [], archived: [], rejected: [], na: false };
    courses.forEach(function (c) {
      if (!c || typeof c !== 'object') return;
      var st = stateOf(c), item = Object.assign({}, c, { state: st });
      if (st === 'review') out.review.push(item);
      else if (st === 'published') out.published.push(item);
      else if (st === 'archived') out.archived.push(item);
      else { out.building.push(item); if (st === 'rejected') out.rejected.push(item); }
      if (!c.is_active && !s(c.archived_at)) out.hidden.push(item);
    });
    // «في المراجعة»: الأقدم تقديمًا أولًا، ومن بلا `submitted_at` بعدهم بترتيب العنوان (لا نرتّب بالعمر).
    out.review.sort(function (a, b) {
      var x = tms(a.submitted_at), y = tms(b.submitted_at);
      if (!isNaN(x) && !isNaN(y)) return x - y;
      if (!isNaN(x)) return -1;
      if (!isNaN(y)) return 1;
      return cmpAr(a.title, b.title);
    });
    function upd(c) { var t = tms(c.updated_at); if (isNaN(t)) t = tms(c.created_at); return isNaN(t) ? 0 : t; }
    out.building.sort(function (a, b) { return upd(b) - upd(a); });
    out.published.sort(function (a, b) { return (num(b.total_enrolled) || 0) - (num(a.total_enrolled) || 0) || cmpAr(a.title, b.title); });
    out.counts = { review: out.review.length, building: out.building.length, published: out.published.length, hidden: out.hidden.length,
                   archived: out.archived.length, rejected: out.rejected.length, total: out.review.length + out.building.length + out.published.length + out.archived.length };
    out.summary = summaryLine(out.counts);
    return out;
  }

  // —— فحص النشر: كل بند ok:true|false|null (null = لا مصدر الآن). ctx = {schedule, checklist, now}؛ checklist = ردّ الجسر أو null.
  function courseFacts(c, ctx) {
    ctx = ctx || {};
    var live = c && c.type === 'live_upcoming', sch = ctx.schedule || null;
    var cl = ctx.checklist && Array.isArray(ctx.checklist.checklist) ? ctx.checklist : null;
    var items = [];
    var lessons = lessonsOf(c), pr = priceOf(c);
    function put(it) { items.push(it); }
    // المحتوى
    if (live) put({ key: 'content', ok: sch ? nonEmpty(sch.start_date) : null, label: 'بلا موعد بدء', pos: 'لها موعد بدء', name: 'موعد البدء', own: true });
    else put({ key: 'content', ok: lessons > 0, label: 'لا دروس فيها', pos: lessons > 0 ? 'فيها ' + lessonsPhrase(lessons) : 'فيها دروس', own: true });
    // السعر
    put({ key: 'price', ok: pr.ok, label: 'بلا سعر', pos: pr.free ? 'مجانية' : 'السعر ' + pr.short, own: true });
    // رابط اللقاء
    if (live) put({ key: 'zoom', ok: sch ? nonEmpty(sch.zoom_link) : null, label: 'بلا رابط للقاء', pos: 'رابط اللقاء موجود', name: 'رابط اللقاء', own: true });
    // الاتفاقية
    if (!(c && c.platform_owned === true)) {
      var ag = c && typeof c.agreement_signed === 'boolean' ? c.agreement_signed : null;
      put({ key: 'agreement', ok: ag, label: 'لم يوقّع صاحب الدورة الاتفاقية', pos: 'صاحب الدورة وقّع الاتفاقية', name: 'توقيع الاتفاقية', own: true });
    }
    if (cl) {
      // بنود المنصة تحلّ محل البند المحلي بنفس المفتاح، وما لا مقابل له يُضاف.
      var map = { pricing: 'price' };
      cl.checklist.forEach(function (x) {
        if (!x || !x.key) return;
        var key = map[x.key] || x.key;
        var text = s(x.item) || key;
        var at = -1;
        for (var i = 0; i < items.length; i++) if (items[i].key === key) at = i;
        var it = { key: key, ok: x.ok === true ? true : (x.ok === false ? false : null), label: text, pos: text, own: false, platform: true };
        if (at > -1) items[at] = it; else items.push(it);
      });
      if (s(cl.sale_block_reason)) items.push({ key: 'sale', ok: false, label: s(cl.sale_block_reason), pos: s(cl.sale_block_reason), own: false, platform: true });
    }
    var missing = items.filter(function (i) { return i.ok === false; }).map(function (i) { return i.label; });
    var unknown = items.filter(function (i) { return i.ok === null; }).map(function (i) { return i.name || i.label; });
    if (!cl) unknown.unshift('بنود الفحص');
    var complete = !!cl && cl.checklist.length > 0 && items.every(function (i) { return i.ok === true; });
    var parts = [];
    items.forEach(function (i) { if (i.own && i.ok === true && i.key !== 'agreement') parts.push(i.pos); });
    if (missing.length) parts.push('ينقصها: ' + missing.join('، '));
    else if (complete) parts.push('اجتازت الفحص: ' + U.ar(cl.checklist.length) + ' من ' + U.ar(cl.checklist.length));
    if (!cl && ctx.checklistState !== 'loading') parts.push('بقية بنود الفحص: ' + NA);
    var suggestion = missing.length ? 'return' : (complete ? 'publish' : 'open');
    return { items: items, line: parts.join(' · '), suggestion: suggestion, complete: complete, missing: missing, unknown: unknown,
             returnNote: missing.length ? 'ينقص الدورة قبل النشر: ' + missing.join('، ') + '.' : '' };
  }

  // —— طلبات المدرّبين
  function appTickets(apps, opts) {
    opts = opts || {};
    var now = opts.now || 0;
    if (!arr(apps)) return null;
    return apps.filter(function (a) { return a && typeof a === 'object'; }).map(function (a) {
      var exp = (Array.isArray(a.expertise) ? a.expertise : []).map(s).filter(Boolean);
      var summary = s(a.experience_summary);
      var li = s(a.linkedin_url), cv = s(a.cv_url), pf = s(a.portfolio_url);
      var facts = [exp.length ? U.U(exp.length, ['مجال واحد', 'مجالان', 'مجالات', 'مجالًا']) : 'بلا مجال محدّد'];
      var links = [];
      if (li) links.push('لينكدإن');
      if (cv) links.push('سيرة ذاتية');
      if (pf) links.push('نماذج أعمال');
      if (links.length) facts = facts.concat(links); else facts.push('بلا روابط');
      if (summary.length < 40) facts.push('نبذة الخبرة قصيرة');
      if (s(a.founding_lead_id)) facts.push('جاء من دعوة الخبراء المؤسسين');
      var missing = [];
      if (!(li || cv)) missing.push('سيرة ذاتية أو لينكدإن');
      if (summary.length < 40) missing.push('نبذة خبرة كافية');
      if (!exp.length) missing.push('مجال واحد على الأقل');
      var ok = !missing.length;
      var at = tms(a.created_at); if (isNaN(at)) at = tms(a.updated_at);
      var timer = isNaN(at) ? null : { at: at, mode: 'since' };
      var h = timer ? hoursSince(at, now) : null;
      return { id: s(a.id) || String(a.id || ''), name: s(a.user_name) || s(a.user_email) || 'مقدّم الطلب', email: s(a.user_email).toLowerCase(), headline: s(a.headline),
               expertise: exp, chips: exp.slice(0, 3), moreChips: Math.max(0, exp.length - 3), timer: timer, text: timer ? L.v2TimerText(timer, now) : '', tone: h == null ? 'none' : tone(h),
               line: facts.join(' · ') + (ok ? '' : ' · ينقص الطلب: ' + missing.join('، ')), suggestion: ok ? 'accept' : 'open', missing: missing,
               links: { linkedin: li, cv: cv, portfolio: pf }, summary: summary, createdAt: s(a.created_at) };
    }).sort(function (x, y) { return (x.timer ? x.timer.at : Infinity) - (y.timer ? y.timer.at : Infinity); });
  }

  // —— المدرّبون: خبراء معتمدون + دوراتهم (بالبريد إن وُجد، وإلا بالاسم كما هو بالتمام). experts فاشل ⇒ null.
  function trainerRows(experts, courses, opts) {
    opts = opts || {};
    var now = opts.now || 0;
    if (!arr(experts)) return null;
    var cs = arr(courses);
    return experts.filter(function (e) { return e && typeof e === 'object'; }).map(function (e) {
      var email = s(e.email).toLowerCase(), name = s(e.full_name) || email || 'مدرّب';
      var mine = cs ? cs.filter(function (c) {
        var ce = s(c && c.instructor_email).toLowerCase();
        return ce ? ce === email : (name && s(c && c.instructor_name) === name);
      }) : null;
      var st = mine ? mine.map(stateOf) : [];
      var inReview = mine ? st.indexOf('review') > -1 : null, rejected = mine ? st.indexOf('rejected') > -1 : null;
      var building = mine ? (st.indexOf('building') > -1 || st.indexOf('rejected') > -1) : null;
      var published = mine ? st.filter(function (x) { return x === 'published'; }).length : null;
      var cc = num(e.courses_count), sc = num(e.students_count);
      var line = '', lt = 'none';
      var due = tms(e.first_course_due_at);
      if (inReview) { line = 'دورة في المراجعة'; lt = 'warn'; }
      else if (rejected) { line = 'تُعدَّل ملاحظات المراجعة'; lt = 'warn'; }
      else if (building) { line = 'دورة تحت البناء'; }
      else if (e.agreement_signed === false) { line = 'لم يوقّع الاتفاقية بعد'; lt = 'warn'; }
      else if (!isNaN(due) && !(published > 0)) {
        if (due > now) { line = 'مهلة أول دورة بعد ' + U.durShort(due - now); lt = 'warn'; } else { line = 'انتهت مهلة أول دورة'; lt = 'late'; }
      }
      else if (e.is_test === true) { line = 'حساب تجريبي — مخفي عن الناس'; }
      else if (e.public_ready === false) { line = 'مخفي عن الدليل: الملف ناقص'; }
      else if (published != null) line = U.U(published, ['دورة منشورة واحدة', 'دورتان منشورتان', 'دورات منشورة', 'دورة منشورة']);
      else if (cc != null) line = U.U(cc, ['دورة واحدة', 'دورتان', 'دورات', 'دورة']);
      var anyBoard = mine ? mine.some(function (c) { return stateOf(c) !== 'archived'; }) : false;
      return { email: email, name: name, expertise: Array.isArray(e.expertise) ? e.expertise : [], coursesCount: cc, students: sc,
               countsText: [cc == null ? null : U.U(cc, ['دورة واحدة', 'دورتان', 'دورات', 'دورة']), sc == null ? null : U.U(sc, ['متعلّم واحد', 'متعلّمان', 'متعلّمين', 'متعلّمًا'])].filter(Boolean).join(' · '),
               statusLine: line, tone: lt, inReview: inReview, building: building, rejected: rejected, published: published,
               listed: (cc != null && cc > 0) || anyBoard, isTest: e.is_test === true, userId: s(e.user_id) };
    });
  }

  // —— الدورات الحيّة
  function liveTimeText(iso) {
    var t = tms(iso); if (isNaN(t)) return '';
    var d = new Date(t), h = d.getHours(), m = d.getMinutes(), ap = h >= 12 ? 'م' : 'ص';
    h = h % 12; if (h === 0) h = 12;
    return U.ar(h) + ':' + (m < 10 ? '٠' : '') + U.ar(m) + ' ' + ap;
  }
  var LIVE_STATUS = { reserving: 'يجمع الحجوزات', payment_window: 'نافذة الدفع', confirmed: 'مثبّتة', canceled: 'أُلغيت', needs_decision: 'تنتظر قرارك' };
  function liveTickets(schedules, queue, opts) {
    opts = opts || {};
    var now = opts.now || 0;
    var sc = arr(schedules), q = arr(queue);
    var by = {};
    (sc || []).forEach(function (r) { if (r && r.slug) by[r.slug] = r; });
    var decide = null;
    if (q) decide = q.filter(function (x) { return x && x.slug; }).map(function (x) {
      var r = by[x.slug] || null;
      var reserved = num(x.reserved_count), quorum = num(x.quorum);
      if (r) { if (reserved == null) reserved = num(r.reserved_count); if (quorum == null) quorum = num(r.quorum); }
      var status = s(x.live_status) || (r && s(r.live_status)) || 'needs_decision';
      var zoom = r ? nonEmpty(r.zoom_link) : null;
      var timer = null, label = 'تنتظر قرارك';
      if (status === 'payment_window' && r && s(r.payment_deadline)) { timer = { at: tms(r.payment_deadline), mode: 'over' }; label = ''; }
      else if (status === 'reserving' && r && s(r.registration_deadline)) { timer = { at: tms(r.registration_deadline), mode: 'over' }; label = ''; }
      var enough = reserved != null && quorum != null && reserved >= quorum;
      var line, main, second;
      if (reserved == null || quorum == null) {
        line = 'الحجوزات: ' + NA; main = { key: 'open', label: 'افتح الدورة' }; second = [{ key: 'cancel', label: 'ألغِ الدورة' }];
      } else if (enough && zoom === true) {
        line = 'اكتمل الحد الأدنى: ' + U.ar(reserved) + ' من ' + U.ar(quorum) + ' · رابط اللقاء موجود';
        main = { key: 'confirm', label: 'ثبّت الدورة' }; second = [{ key: 'cancel', label: 'ألغِ الدورة' }];
      } else if (enough && zoom === false) {
        line = 'اكتمل الحد الأدنى، وينقص رابط اللقاء';
        main = { key: 'zoom', label: 'أضف رابط اللقاء' }; second = [{ key: 'cancel', label: 'ألغِ الدورة' }];
      } else if (enough) {
        line = 'اكتمل الحد الأدنى: ' + U.ar(reserved) + ' من ' + U.ar(quorum) + ' · رابط اللقاء: ' + NA;
        main = { key: 'open', label: 'افتح الدورة' }; second = [{ key: 'cancel', label: 'ألغِ الدورة' }];
      } else {
        line = 'حجز ' + U.ar(reserved) + ' من ' + U.ar(quorum) + '، وانتهت مهلة ' + (status === 'payment_window' ? 'الدفع' : 'التسجيل');
        main = { key: 'extend', label: 'مدّد ٤٨ ساعة' }; second = [{ key: 'confirm', label: 'ثبّت رغم ذلك' }, { key: 'cancel', label: 'ألغِ الدورة' }];
      }
      var startIso = r ? s(r.start_date) : '';
      return { slug: x.slug, id: r ? s(r.id) : '', title: s(x.title) || (r && s(r.title)) || 'دورة حيّة', trainer: (r && s(r.instructor_name)) || '', status: status,
               reserved: reserved, quorum: quorum, zoom: zoom, timer: timer, timerText: timer ? L.v2TimerText(timer, now) : '', label: label,
               startText: startIso ? 'تبدأ ' + U.dateText(startIso) : '', line: line, main: main, secondary: second };
    });
    var all = null;
    if (sc) {
      all = sc.filter(function (r) { return r && typeof r === 'object'; }).map(function (r) {
        var status = s(r.live_status) || 'reserving';
        var t = LIVE_STATUS[status] || 'غير معروفة';
        if (status === 'payment_window' && s(r.payment_deadline)) t += ' حتى ' + U.dateText(r.payment_deadline);
        var at = tms(r.start_date);
        return { id: s(r.id), slug: s(r.slug), title: s(r.title) || 'دورة حيّة', trainer: s(r.instructor_name), dateText: isNaN(at) ? 'بلا موعد' : U.dateText(r.start_date),
                 timeText: isNaN(at) ? '' : liveTimeText(r.start_date), booked: num(r.booked_count), max: num(r.max_seats), quorum: num(r.quorum),
                 status: status, statusText: t, hasZoom: nonEmpty(r.zoom_link), canceled: status === 'canceled', at: isNaN(at) ? Infinity : at };
      }).sort(function (a, b) { return (a.canceled ? 1 : 0) - (b.canceled ? 1 : 0) || a.at - b.at; });
    }
    return { decide: decide, all: all };
  }

  // —— عروض الأسعار
  function offerTickets(offers, opts) {
    opts = opts || {};
    var now = opts.now || 0;
    if (!arr(offers)) return null;
    return offers.filter(function (o) { return o && typeof o === 'object'; }).map(function (o) {
      var cur = s(o.currency) || 'EGP';
      var off = num(o.offered_amount), sit = num(o.situational_amount), floor = num(o.floor_amount);
      var line, sug;
      if (off != null && floor != null && off < floor) { line = 'العرض أقل من الحد الأدنى'; sug = 'counter'; }
      else if (off != null && sit != null && sit > 0) {
        var pct = Math.round((sit - off) / sit * 100);
        line = pct > 0 ? 'العرض أقل من السعر المناسب بـ' + U.ar(pct) + '٪' + (floor != null ? '، وفوق الحد الأدنى' : '') : 'العرض يساوي السعر المناسب أو يزيد عليه';
        sug = 'approve';
      } else if (off != null) { line = 'السعر المناسب: ' + NA; sug = 'approve'; }
      else { line = 'مبلغ العرض: ' + NA; sug = 'counter'; }
      var at = tms(o.created_at), timer = isNaN(at) ? null : { at: at, mode: 'since' };
      var agreed = off != null ? (floor != null ? Math.max(off, floor) : off) : null;
      function m(v) { return v == null ? NA : U.moneyText(v, cur); }
      return { id: s(o.id), course: s(o.course_title) || s(o.course_slug) || 'دورة', buyer: s(o.buyer_email) || 'صاحب العرض', buyerEmail: s(o.buyer_email).toLowerCase(),
               segment: SEG_LABEL[s(o.segment)] || 'فرد', currency: cur, offered: off, situational: sit, floor: floor, agreed: agreed,
               amounts: [{ k: 'العرض', v: m(off) }, { k: 'السعر المناسب له', v: m(sit) }, { k: 'الحد الأدنى', v: m(floor) }],
               line: line, suggestion: sug, message: s(o.message), timer: timer, text: timer ? L.v2TimerText(timer, now) : '', belowFloor: off != null && floor != null && off < floor };
    }).sort(function (a, b) { return (a.timer ? a.timer.at : Infinity) - (b.timer ? b.timer.at : Infinity); });
  }

  // —— ما يطلبه الناس: stats = {stats:[{title,count}]} · requests = {requests:[…]} أو قائمة · analysis = ردّ تحليل الشات. المصدر الفاشل null.
  function demand(stats, requests, analysis, opts) {
    opts = opts || {};
    var now = opts.now || 0;
    var list = stats && arr(stats.stats) ? stats.stats : null;
    var counts = {};
    (list || []).forEach(function (x) { if (x && s(x.title)) counts[s(x.title)] = num(x.count) || 0; });
    var top = null, topLine = '';
    if (list) {
      var rows = list.filter(function (x) { return x && s(x.title); }).slice(0, 10);
      var max = Math.max.apply(null, [1].concat(rows.map(function (x) { return num(x.count) || 0; })));
      top = rows.map(function (x) { var c = num(x.count) || 0; return { title: s(x.title), count: c, countText: U.U(c, ['طلب واحد', 'طلبان', 'طلبات', 'طلبًا']), width: Math.max(4, Math.round(c / max * 100)) }; });
      if (top.length) topLine = 'أكثر ما يُطلب: «' + top[0].title + '» (' + U.ar(top[0].count) + ')';
    }
    var reqs = requests && !Array.isArray(requests) ? arr(requests.requests) : arr(requests);
    var programs = null;
    if (reqs) programs = reqs.filter(function (r) { return r && typeof r === 'object' && (!r.status || r.status === 'pending'); }).map(function (r) {
      var title = s(r.title) || s(r.program_id) || 'برنامج';
      var n = counts[title];
      var at = tms(r.created_at), timer = isNaN(at) ? null : { at: at, mode: 'since' };
      return { id: s(r.id), title: title, requester: s(r.user_name) || s(r.user_email) || 'صاحب الطلب', email: s(r.user_email).toLowerCase(), timer: timer,
               text: timer ? L.v2TimerText(timer, now) : '', line: n > 1 ? 'طلبه ' + U.U(n, ['شخص واحد', 'شخصان', 'أشخاص', 'شخصًا']) + ' بنفس العنوان' : 'أول طلب بهذا العنوان' };
    }).sort(function (a, b) { return (a.timer ? a.timer.at : Infinity) - (b.timer ? b.timer.at : Infinity); });
    var chat = null;
    var rq = analysis && arr(analysis.recent_questions);
    if (rq) {
      var map = {};
      rq.forEach(function (r) {
        if (!r || r.intent !== 'دورة') return;
        var k = s(r.category) || 'غير مصنّف';
        if (!map[k]) map[k] = { category: k, count: 0, example: s(r.question).slice(0, 90) };
        map[k].count++;
      });
      var groups = Object.keys(map).map(function (k) { return map[k]; }).sort(function (a, b) { return b.count - a.count; });
      groups.forEach(function (g) { g.countText = U.U(g.count, ['طلب واحد', 'طلبان', 'طلبات', 'طلبًا']); g.title = 'دورة في ' + g.category; });
      chat = { sample: rq.length, sampleText: 'من عيّنة آخر ' + U.ar(rq.length) + ' سؤالًا في الشات', groups: groups };
    }
    return { top: top, topLine: topLine, programs: programs, chat: chat };
  }

  // —— صفحة الدورة
  function statFor(stats, c) {
    var list = stats && arr(stats.courses);
    if (!list || !c) return null;
    for (var i = 0; i < list.length; i++) if (list[i] && (list[i].course_id === c.id || (c.slug && list[i].slug === c.slug))) return list[i];
    return null;
  }
  function pageModel(c, detail, stat, checklist, schedule, opts) {
    opts = opts || {};
    var now = opts.now || 0;
    var st = stateOf(c);
    var facts = courseFacts(c, { schedule: schedule, checklist: checklist, now: now });
    var story = c.story && num(c.story.lessons) > 0 ? c.story : null;
    var pr = priceOf(c);
    var lessons = story ? U.ar(story.lessons) + ' في ' + U.ar(story.units) + ' أجزاء · نحو ' + U.ar(story.minutes) + ' دقيقة' : U.ar(lessonsOf(c));
    var sales;
    if (stat && arr(stat.sales)) {
      var parts = stat.sales.filter(function (x) { return x && num(x.amount) != null; }).map(function (x) { return U.moneyText(x.amount, x.currency); });
      sales = { text: parts.length ? parts.join(' + ') : 'لا مبيعات بعد', na: false };
    } else sales = { text: NA, na: true };
    var comp = [];
    var pct = stat ? num(stat.completion_pct) : null;
    if (pct != null) comp.push('يكملها ' + U.ar(pct) + '٪');
    if (stat && stat.stall_lesson && num(stat.stall_lesson.index) != null) comp.push('يتوقف أغلبهم عند الدرس ' + U.ar(stat.stall_lesson.index) + (s(stat.stall_lesson.title) ? ': ' + s(stat.stall_lesson.title) : ''));
    var completion = comp.length ? comp.join(' · ') : 'نسبة الإكمال: ' + NA;
    var main = null, second = [], block = false;
    if (st === 'review') {
      if (opts.checklistState === 'error') { main = { key: 'refetch', label: 'أعد جلب الفحص' }; block = true; }
      else if (facts.suggestion === 'publish') { main = { key: 'publish', label: 'انشرها' }; second = [{ key: 'return', label: 'أعِدها بملاحظات' }]; }
      else if (facts.suggestion === 'return') { main = { key: 'return', label: 'أعِدها بملاحظات' }; second = [{ key: 'publish', label: 'انشرها' }]; }
      else block = true;
    } else if (st === 'building' || st === 'rejected') second = [{ key: 'publishNow', label: 'انشرها الآن' }];
    else if (st === 'published') second = [{ key: 'hide', label: 'أوقف ظهورها' }];
    else if (st === 'archived') main = { key: 'show', label: 'أعِد نشرها' };
    var canHard = !c.is_active && !s(c.archived_at) && !(num(c.total_enrolled) > 0);
    var live = null;
    if (c.type === 'live_upcoming') {
      var sc = schedule || null;
      live = sc ? { startText: s(sc.start_date) ? U.dateText(sc.start_date) : 'بلا موعد', timeText: liveTimeText(sc.start_date),
                    seats: num(sc.booked_count) != null && num(sc.max_seats) != null ? 'المقاعد: ' + U.ar(sc.booked_count) + ' من ' + U.ar(sc.max_seats) : 'المقاعد: ' + NA,
                    quorum: num(sc.quorum) != null ? 'الحد الأدنى للتشغيل: ' + U.ar(sc.quorum) : 'الحد الأدنى للتشغيل: ' + NA,
                    status: LIVE_STATUS[s(sc.live_status)] || '', zoom: nonEmpty(sc.zoom_link) ? 'رابط اللقاء: موجود' : 'رابط اللقاء: غير موجود', slug: s(sc.slug) || s(c.slug) } : { na: true, slug: s(c.slug) };
    }
    return { id: c.id, title: s(c.title) || 'دورة بلا عنوان', state: st, stateLabel: STATE_LABEL[st], typeLabel: TYPE_LABEL[c.type] || s(c.type), interactive: !!story,
             sourceLabel: SOURCE_LABEL[s(c.source)] || '', trainer: trainerOf(c), trainerEmail: s(c.instructor_email).toLowerCase(), hero: s(c.thumbnail_url), cover: cover(c.title),
             tiles: { learners: U.ar(num(c.total_enrolled) || 0), lessons: lessons, price: pr.ok === false ? 'بلا سعر' : pr.text, sales: sales },
             completion: completion, facts: facts, main: main, secondary: second, decisionBlock: block, bid: { show: st === 'published' && c.type !== 'recorded_free', enabled: c.bid_enabled === true },
             live: live, danger: st === 'archived' ? null : (canHard ? 'delete' : 'archive'), reviewNote: s(c.review_note), hasPreview: !!(story && s(c.slug)), enrolled: num(c.total_enrolled) || 0 };
  }

  L.v2s.courses = { tone: tone, reviewTimer: reviewTimer, cover: cover, board: board, summaryLine: summaryLine, courseFacts: courseFacts, appTickets: appTickets,
                    trainerRows: trainerRows, liveTickets: liveTickets, offerTickets: offerTickets, demand: demand, pageModel: pageModel, stateOf: stateOf,
                    lessonsOf: lessonsOf, hiddenFromPublic: hiddenFromPublic, lessonsPhrase: lessonsPhrase, trainerOf: trainerOf, priceOf: priceOf, statFor: statFor, liveTimeText: liveTimeText,
                    TYPE_LABEL: TYPE_LABEL, STATE_LABEL: STATE_LABEL, SOURCE_LABEL: SOURCE_LABEL, SEG_LABEL: SEG_LABEL, LIVE_STATUS: LIVE_STATUS, NA: NA, WARN_H: WARN_H, LATE_H: LATE_H };
})(typeof window !== 'undefined' ? window : (typeof globalThis !== 'undefined' ? globalThis : this));
// ===== /v2s:courses =====

// ===== v2s:market ===== «سوق الخدمات» (الجولة النهائية): منطق نقي لتذاكر الطلبات وسطر العقل والفلاتر وأرقام «ماذا يطلب الناس».
// ⛔ لا DOM ولا شبكة ولا ساعة خفية (`now` يُمرَّر). كل رقم من حقل في الصف؛ المجهول `undefined` لا صفر. المواصفة: docs/v2/final/SPEC-market.md
(function (root) {
  'use strict';
  var V = root.V2L;
  if (!V) return;
  var U = V.util, ar = U.ar, agoText = U.agoText, dateText = U.dateText, moneyText = U.moneyText;
  var HOUR = 3600e3, DAY = 86400e3;
  var STALE_REQUEST_DAYS = 7;          // = STALE_REQUEST_DAYS في marketplace.py (المنصة تُخفي من صفحة السوق العامة بعد ٧ أيام بلا أي نشاط)
  var DONE_WINDOW = 7 * DAY;
  var PAGE = 8;                        // تذاكر كل عمود قبل «اعرض الباقي»
  var COLS = ['new', 'waiting', 'offered', 'done'];
  var COL_LABEL = { 'new': 'طلب جديد', waiting: 'ينتظر خبيرًا', offered: 'وصله عرض', done: 'انتهى هذا الأسبوع' };
  var COL_EMPTY = { 'new': 'لا طلبات جديدة اليوم', waiting: 'لا طلب ينتظر خبيرًا', offered: 'لا طلبات عليها عروض الآن', done: 'لم يُغلق أي طلب هذا الأسبوع' };
  var NEED_LABEL = { expert: 'خبير', service: 'خدمة', course: 'دورة أو تدريب', book: 'كتاب أو معرفة', training_offer: 'عرض مدرّب', other: 'غير مصنّف' };
  var NEED_LANE = { course: 'course_request', service: 'public_service', expert: 'request', book: 'request', other: 'request' };   // = _NEED_KIND_LANE في marketplace.py
  var LANE_PLURAL = { request: 'طلبات الخبرة', course_request: 'طلبات الدورات', public_service: 'خدمات للجمهور', training_offer: 'عروض المدرّبين' };
  var LANE_ONE = { request: 'طلب خبرة', course_request: 'طلب دورة', public_service: 'خدمة للجمهور', training_offer: 'عرض مدرّب' };
  var DEMAND_LANES = ['request', 'course_request', 'public_service'];
  var EXTRA_KEYS = ['author_kind', 'open_demand', 'join_goal', 'joined_count', 'goal_reached_at', 'last_offer_at', 'updated_at', 'stale_unanswered',
                    'linked_course_id', 'linked_course_slug', 'source', 'catalog_name', 'last_activity_at', 'member_phone'];

  function ms(v) { var t = typeof v === 'number' ? v : Date.parse(v || ''); return isNaN(t) || !isFinite(t) || t <= 0 ? NaN : t; }
  function isNum(n) { return typeof n === 'number' && isFinite(n); }
  function arDigits(t) { return String(t == null ? '' : t).replace(/\d/g, function (d) { return '٠١٢٣٤٥٦٧٨٩'.charAt(+d); }); }
  function needLabel(k) { return NEED_LABEL[k] || NEED_LABEL.other; }
  function laneOf(need) { return NEED_LANE[need] || ''; }
  function lanePlural(k) { return LANE_PLURAL[k] || 'طلبات'; }
  function isOpen(r) { var s = r && r.status; return s === undefined || s === null || s === '' || s === 'open'; }
  function isDone(r) { return r && (r.status === 'matched' || r.status === 'closed'); }
  function offers(r) { return Number(r && r.offer_count) || 0; }
  function activityAt(r) { return (r && (r.last_activity_at || r.created_at)) || ''; }
  function joinText(r) {
    var j = r.joined_count, g = r.join_goal;
    if (!isNum(j)) return '';
    return g > 0 ? 'انضم ' + ar(j) + ' من ' + ar(g) : 'انضم ' + ar(j);
  }
  function sameDay(a, b) { var x = new Date(a), y = new Date(b); return x.getFullYear() === y.getFullYear() && x.getMonth() === y.getMonth() && x.getDate() === y.getDate(); }
  function hhmm(t) { var d = new Date(t), h = d.getHours(), m = d.getMinutes(), ap = h >= 12 ? 'م' : 'ص'; h = h % 12; if (h === 0) h = 12; return ar(h) + ':' + (m < 10 ? '٠' : '') + ar(m) + ' ' + ap; }
  function timerText(pre, ts, now) { var a = agoText(ts, now); return a ? (pre ? pre + a : a) : ''; }

  // الصف من محمّل الداشبورد ناقص حقولًا يرسلها الجسر: نكمّلها بالمعرّف من `raw` (الصفوف مرتّبة، فلا مطابقة بالموضع). غائب ⇒ undefined.
  function merge(rows, raw) {
    var by = {};
    (Array.isArray(raw) ? raw : []).forEach(function (q) { if (q && q.id != null) by[String(q.id)] = q; });
    return (Array.isArray(rows) ? rows : []).map(function (r) {
      var out = {}, q = by[String(r && r.id)];
      Object.keys(r || {}).forEach(function (k) { out[k] = r[k]; });
      if (q) EXTRA_KEYS.forEach(function (k) { if (q[k] !== undefined && q[k] !== null) out[k] = q[k]; });
      return out;
    });
  }

  // صف الجسر الخام (قائمة «كل الطلبات») على شكل صف لوحة السوق نفسه: نفس القيم الافتراضية التي يضعها المحمّل القديم + حقول الجسر الإضافية.
  var NEED_FOR_KIND = { request: 'expert', course_request: 'course', public_service: 'service', training_offer: 'training_offer', knowledge: 'book' };
  function norm(q) {
    q = q || {};
    var kind = q.kind || 'request';
    var r = { id: q.id || '', kind: kind, need_kind: q.need_kind || NEED_FOR_KIND[kind] || 'other', title: q.title || '', body: q.body || '', specialty: q.specialty || '',
              service: q.service || '', status: q.status || 'open', visibility: q.visibility || 'private', member_alias: q.member_alias || 'عضو', member_email: q.member_email || '',
              member_name: q.member_name || '', preferred_expert_email: q.preferred_expert_email || '', budget: q.budget || 0, currency: q.currency || '',
              offer_count: (q.offer_count != null ? q.offer_count : (q.offers_count || 0)) | 0, accepted_offer_id: q.accepted_offer_id || null,
              consultation_id: q.consultation_id || null, is_test: !!q.is_test, hidden: !!q.hidden, hidden_reason: q.hidden_reason || '', created_at: q.created_at || '' };
    EXTRA_KEYS.forEach(function (k) { if (q[k] !== undefined && q[k] !== null) r[k] = q[k]; });
    return r;
  }

  // ------------------------------------------------------------------ العقل: سطر وزرّ واحد لكل طلب
  function brain(r, now, opts) {
    var ro = !!(opts && opts.readOnly);
    var line, primary = null;
    function open(label) { return { label: label || 'افتح الطلب', act: 'open' }; }
    var cnt = offers(r), ago;
    if (r.status === 'matched') {
      ago = agoText(r.updated_at, now);
      return { line: 'اختار صاحب الطلب عرضًا' + (ago ? ' ' + ago : ''), primary: null };
    }
    if (r.status === 'closed') {
      ago = agoText(r.updated_at, now);
      return { line: 'أُغلق' + (ago ? ' ' + ago : ''), primary: null };
    }
    if (!isOpen(r)) return { line: 'حالته على المنصة غير معروفة؛ افتحه للتأكد', primary: open() };
    if (r.hidden) {
      return { line: 'مخفي عن صفحة السوق العامة' + (r.hidden_reason ? ' بسبب: «' + arDigits(r.hidden_reason) + '»' : '') + '؛ صاحبه ما زال يراه', primary: open() };
    }
    if (r.open_demand) {
      var jt = joinText(r);
      if (r.goal_reached_at && !r.linked_course_id) {
        ago = agoText(r.goal_reached_at, now);
        line = 'اكتمل العدد' + (ago ? ' ' + ago : '') + (jt ? ': ' + jt : '') + '، ولم تُربط دورة بعد';
        primary = ro ? open() : { label: 'اربط دورة', act: 'link' };
        return { line: line, primary: primary };
      }
      if (r.linked_course_id) {
        return { line: 'رُبطت به دورة، والحجز مفتوح لمن انضم' + (isNum(r.joined_count) ? ' (' + ar(r.joined_count) + ')' : ''), primary: open() };
      }
      return { line: 'طلب مفتوح من المنصة يجمع المنضمّين' + (jt ? ': ' + (r.join_goal > 0 ? ar(r.joined_count) + ' من ' + ar(r.join_goal) : jt) : ''), primary: open() };
    }
    var target = laneOf(r.need_kind);
    if (!cnt && target && DEMAND_LANES.indexOf(r.kind) > -1 && target !== r.kind) {
      line = 'نوعه «' + needLabel(r.need_kind) + '» لكنه معروض مع ' + lanePlural(r.kind);
      primary = ro ? open() : { label: 'انقله إلى ' + lanePlural(target), act: 'relane', target: target };
      return { line: line, primary: primary };
    }
    if (!cnt && r.stale_unanswered === true) {
      return { line: 'بلا أي عرض ' + agoText(activityAt(r), now) + '، لذلك لم يعد يظهر على صفحة السوق العامة', primary: open() };
    }
    if (cnt > 0) {
      ago = agoText(r.last_offer_at, now);
      return { line: 'وصله ' + U.U(cnt, ['عرض واحد', 'عرضان', 'عروض', 'عرضًا']) + (ago ? '، آخرها ' + ago : '') + '. الاختيار لصاحب الطلب',
               primary: { label: 'اعرض العروض', act: 'offers' } };
    }
    var created = ms(r.created_at), age = isNaN(created) ? NaN : (now || 0) - created;
    var isPublic = r.visibility === 'public';
    if (isPublic && age >= DAY) {
      var a2 = agoText(activityAt(r), now);
      if (!(r.join_goal > 0) && !(r.joined_count > 0) && !r.open_demand) {
        line = 'بلا عرض ' + a2 + '. يختفي من صفحة السوق العامة بعد ' + ar(STALE_REQUEST_DAYS) + ' أيام بلا عرض';
      } else {
        line = 'بلا عرض ' + a2 + '، ويبقى على صفحة السوق العامة ما دام يجمع المنضمّين' + (isNum(r.joined_count) ? ' (' + ar(r.joined_count) + ')' : '');
      }
      return { line: line, primary: open() };
    }
    if (!isPublic) {
      var when = agoText(r.created_at, now);
      return { line: (r.preferred_expert_email ? 'طلب خاص موجَّه إلى خبير بعينه' : 'طلب خاص لا يظهر على صفحة السوق العامة') + '، بلا عرض' + (when ? ' ' + when : ''), primary: open() };
    }
    if (age >= 0) return { line: 'وصل ' + agoText(r.created_at, now) + '، وهو ظاهر للخبراء على صفحة السوق العامة', primary: open() };
    return { line: 'لم يصله عرض بعد', primary: open() };
  }

  // ------------------------------------------------------------------ التذاكر
  function typeLabel(r) {
    var base = r.open_demand ? 'طلب مفتوح من المنصة' : (LANE_ONE[r.kind] || 'طلب');
    return base + (r.catalog_name ? ' · ' + r.catalog_name : '');
  }
  function whoOf(r) {
    var isPlat = r.author_kind === 'platform';
    return { name: r.member_name || r.member_alias || (isPlat ? 'المنصة' : 'صاحب الطلب'), email: isPlat ? '' : (r.member_email || '') };
  }
  function badgesOf(r) {
    var b = [];
    if (r.visibility !== undefined && r.visibility !== 'public') b.push({ k: 'private', label: 'خاص' });
    if (r.hidden) b.push({ k: 'hidden', label: 'مخفي عن صفحة السوق العامة' });
    if (r.is_test) b.push({ k: 'test', label: 'تجريبي' });
    if (r.source === 'chat') b.push({ k: 'chat', label: 'من محادثة بروف' });
    return b;
  }
  function ticketOf(r, col, now, opts) {
    var created = ms(r.created_at);
    var t = { id: String(r.id), col: col, row: r, title: r.title || 'طلب بلا عنوان', typeLabel: typeLabel(r), timer: null, text: '', tone: 'new', unknown: false };
    t.who = whoOf(r);
    t.specialty = r.specialty || '';
    t.badges = badgesOf(r);
    t.progress = null;
    if (r.open_demand && isNum(r.joined_count)) t.progress = { joined: r.joined_count, goal: r.join_goal > 0 ? r.join_goal : 0, pct: r.join_goal > 0 ? Math.max(0, Math.min(100, Math.round(r.joined_count * 100 / r.join_goal))) : 0 };
    if (col === 'done') {
      t.tone = 'done';
      t.typeLabel = r.status === 'matched' ? 'تمّت المطابقة' : 'أُغلق';
      var u = ms(r.updated_at); if (isNaN(u)) u = created;
      if (!isNaN(u)) t.text = sameDay(u, now) ? hhmm(u) : dateText(new Date(u).toISOString());
    } else if (col === 'offered') {
      t.tone = 'ok';
      var lo = ms(r.last_offer_at);
      if (!isNaN(lo)) { t.timer = { pre: 'آخر عرض ', ts: lo }; t.text = timerText('آخر عرض ', lo, now); } else t.text = 'وصله عرض';
    } else if (col === 'waiting') {
      var red = r.stale_unanswered === true || (!!r.goal_reached_at && !r.linked_course_id);
      t.tone = red ? 'late' : (r.open_demand && r.linked_course_id ? 'ok' : 'wait');
      if (!isOpen(r)) { t.unknown = true; t.typeLabel = 'حالة غير معروفة'; t.tone = 'wait'; }
      else if (r.open_demand && r.goal_reached_at && !isNaN(ms(r.goal_reached_at))) { t.timer = { pre: 'اكتمل العدد ', ts: ms(r.goal_reached_at) }; }
      else if (!isNaN(ms(activityAt(r)))) { t.timer = { pre: 'بلا عرض ', ts: ms(activityAt(r)) }; }
      if (t.timer) t.text = timerText(t.timer.pre, t.timer.ts, now);
    } else {
      t.tone = 'new';
      if (!isNaN(created)) { t.timer = { pre: '', ts: created }; t.text = timerText('', created, now); }
    }
    t.brain = brain(r, now, opts);
    return t;
  }
  function tileCount(rows) {
    return (rows || []).filter(function (r) { return r && r.status === 'open' && !r.hidden && !r.is_test && r.kind !== 'training_offer' && !r.offer_count; }).length;
  }
  // opts = {now, lane:'all'|…, showTest, expanded:{col:true}, readOnly}
  function tickets(rows, opts) {
    opts = opts || {};
    var now = opts.now || 0, lane = opts.lane || 'all';
    var cols = { 'new': [], waiting: [], offered: [], done: [] };
    var key = {}; // مفاتيح الترتيب
    var testCount = 0, hiddenCount = 0, doneOlder = 0;
    (rows || []).forEach(function (r) {
      if (!r || r.kind === 'training_offer') return;
      if (r.is_test) { testCount++; if (!opts.showTest) return; }
      if (lane !== 'all' && r.kind !== lane) return;
      if (r.hidden) hiddenCount++;
      var col, created = ms(r.created_at);
      if (isDone(r)) {
        var u = ms(r.updated_at); if (isNaN(u)) u = created;
        if (isNaN(u) || now - u > DONE_WINDOW) { doneOlder++; return; }
        col = 'done'; key[r.id] = -u;
      } else if (!isOpen(r)) { col = 'waiting'; key[r.id] = Infinity; }
      else if (offers(r) > 0) { col = 'offered'; var lo = ms(r.last_offer_at); key[r.id] = isNaN(lo) ? Infinity : lo; }
      else if (isNaN(created)) { col = 'waiting'; key[r.id] = Infinity; }
      else if (r.open_demand || now - created >= DAY) { col = 'waiting'; var a = ms(activityAt(r)); key[r.id] = isNaN(a) ? Infinity : a; }
      else { col = 'new'; key[r.id] = created; }
      cols[col].push(ticketOf(r, col, now, opts));
    });
    cols.waiting.sort(function (a, b) {
      var ra = a.tone === 'late' ? 0 : 1, rb = b.tone === 'late' ? 0 : 1;
      return ra - rb || (key[a.id] - key[b.id]) || 0;
    });
    ['new', 'offered', 'done'].forEach(function (c) { cols[c].sort(function (a, b) { return (key[a.id] - key[b.id]) || 0; }); });
    var counts = {}, shown = {}, more = {};
    COLS.forEach(function (c) {
      counts[c] = cols[c].length;
      var lim = opts.expanded && opts.expanded[c] ? cols[c].length : PAGE;
      shown[c] = cols[c].slice(0, lim);
      more[c] = cols[c].length - shown[c].length;
    });
    return { cols: cols, counts: counts, shown: shown, more: more, doneOlder: doneOlder, testCount: testCount, hiddenCount: hiddenCount, tileCount: tileCount(rows) };
  }
  // بطاقات القرار الجاهزة للعقل/اللوحة لاحقًا (اربط دورة · انقل الطلب)
  function cards(rows, now) {
    var out = [];
    (rows || []).forEach(function (r) {
      if (!r || r.kind === 'training_offer' || r.is_test || r.hidden) return;
      var b = brain(r, now, null);
      if (b.primary && (b.primary.act === 'link' || b.primary.act === 'relane')) out.push({ kind: 'market', id: String(r.id), title: r.title || 'طلب بلا عنوان', line: b.line, primary: b.primary });
    });
    return out;
  }

  // ------------------------------------------------------------------ رأس اللوحة
  function header(rows, counts, total, now) {
    var open = (rows || []).filter(function (r) { return r && r.kind !== 'training_offer' && !r.is_test; });
    var N = tileCount(rows), oldest = NaN;
    (rows || []).forEach(function (r) {
      if (r && r.status === 'open' && !r.hidden && !r.is_test && r.kind !== 'training_offer' && !r.offer_count) { var c = ms(r.created_at); if (!isNaN(c) && (isNaN(oldest) || c < oldest)) oldest = c; }
    });
    var pre, text;
    var openCount = open.filter(function (r) { return isOpen(r); }).length;
    if (N > 0) {
      pre = 'العقل: ' + U.U(N, ['طلب واحد بلا عرض', 'طلبان بلا عرض', 'طلبات بلا عرض', 'طلبًا بلا عرض']);
      if (!isNaN(oldest)) { pre += '، أقدمها '; text = pre + agoText(oldest, now); } else text = pre;
    } else if (openCount > 0) { text = 'العقل: كل طلب مفتوح وصله عرض أو يجمع المنضمّين'; pre = text; oldest = NaN; }
    else { text = 'العقل: لا طلبات مفتوحة الآن'; pre = text; oldest = NaN; }
    var bs = counts && counts.by_status ? counts.by_status : null, totals;
    if (bs) totals = 'في السوق الآن: ' + ar(bs.open || 0) + ' مفتوح · ' + ar(bs.matched || 0) + ' تمّت مطابقته · ' + ar(bs.closed || 0) + ' أُغلق' + ((rows || []).some(function (r) { return r && r.is_test && r.kind !== 'training_offer'; }) ? ' (يشمل التجريبي)' : '');
    else {
      var c = { open: 0, matched: 0, closed: 0 };
      open.forEach(function (r) { if (isOpen(r)) c.open++; else if (r.status === 'matched') c.matched++; else if (r.status === 'closed') c.closed++; });
      totals = 'في السوق الآن: ' + ar(c.open) + ' مفتوح · ' + ar(c.matched) + ' تمّت مطابقته · ' + ar(c.closed) + ' أُغلق (من المعروض فقط)';
    }
    var bl = counts && counts.by_lane ? counts.by_lane : null, lanes;
    if (bl) lanes = { request: bl.request || 0, course_request: bl.course_request || 0, public_service: bl.public_service || 0, training_offer: bl.training_offer || 0 };
    else {
      lanes = { request: 0, course_request: 0, public_service: 0, training_offer: 0 };
      (rows || []).forEach(function (r) { if (r && lanes[r.kind] !== undefined) lanes[r.kind]++; });
    }
    lanes.all = lanes.request + lanes.course_request + lanes.public_service;
    return { brainText: text, brainPre: pre, brainTs: isNaN(oldest) ? null : oldest, N: N, totals: totals, lanes: lanes,
             truncated: isNum(total) && total > (rows || []).length, shownRows: (rows || []).length, total: total };
  }

  // ------------------------------------------------------------------ كل الطلبات: الاستعلام وحالة الفلاتر
  function query(s) {
    s = s || {};
    var parts = [];
    function add(k, v) { parts.push(k + '=' + encodeURIComponent(v)); }
    if (s.lane && s.lane !== 'all') add('lane', s.lane);
    if (s.status && s.status !== 'all') add('status', s.status);
    if (s.need && s.need !== 'all') add('need_kind', s.need);
    if (s.author && s.author !== 'all') add('author_kind', s.author);
    var q = String(s.q == null ? '' : s.q).trim().slice(0, 80);
    if (q) add('q', q);
    add('include_test', s.showTest ? '1' : '0');
    add('limit', String(s.limit || 50));
    add('skip', String(s.skip || 0));
    return parts.join('&');
  }
  function activeFilters(s) {
    var out = [];
    if (s.status && s.status !== 'all') out.push({ k: 'status', label: { open: 'مفتوح', matched: 'تمّت المطابقة', closed: 'أُغلق' }[s.status] || s.status });
    if (s.need && s.need !== 'all') out.push({ k: 'need', label: needLabel(s.need) });
    if (s.author && s.author !== 'all') out.push({ k: 'author', label: s.author === 'platform' ? 'المنصة' : 'الأعضاء' });
    if (s.showTest) out.push({ k: 'test', label: 'يظهر التجريبي' });
    return out;
  }
  function allRow(r, now) {
    return { id: String(r.id), row: r, title: r.title || 'طلب بلا عنوان', lane: LANE_ONE[r.kind] || 'طلب', who: whoOf(r), badges: badgesOf(r), offersText: r.open_demand ? (isNum(r.joined_count) ? 'انضم ' + ar(r.joined_count) : '') : ar(offers(r)),
             status: r.status === 'matched' ? 'تمّت المطابقة' : r.status === 'closed' ? 'أُغلق' : (isOpen(r) ? 'مفتوح' : 'حالة غير معروفة'), statusKey: isOpen(r) ? 'open' : (r.status === 'matched' ? 'matched' : r.status === 'closed' ? 'closed' : 'unknown'),
             date: dateText(r.created_at), ago: agoText(r.created_at, now) };
  }

  // ------------------------------------------------------------------ أخطاء الربط
  var LINK_GENERIC = 'تعذّر ربط الدورة، حاول مرة أخرى';
  function linkErr(status, data) {
    var m = data && (data.error || data.detail);
    if (m && typeof m === 'object') m = m.message || m.error || '';
    m = typeof m === 'string' ? m : '';
    if (status === 404) return m.indexOf('الدورة') > -1 ? 'الدورة غير موجودة على المنصة' : 'هذا الطلب لم يعد موجودًا على المنصة';
    if (status === 422) {
      var t = arDigits(m);
      return /[؀-ۿ]/.test(t) ? t : LINK_GENERIC;
    }
    return LINK_GENERIC;
  }

  // ------------------------------------------------------------------ ماذا يطلب الناس
  function demand(d) {
    if (!d || d.missing) return null;
    var sg = d.signals || {}, out = { brain: '', platform: '', byNeed: [], specs: { title: 'حسب التخصص', fallback: false, items: [] }, courses: [], topBrain: '' };
    var parts = [];
    if (isNum(sg.unanswered_requests)) parts.push(U.U(sg.unanswered_requests, ['طلب مفتوح بلا عرض', 'طلبان مفتوحان بلا عرض', 'طلبات مفتوحة بلا عرض', 'طلبًا مفتوحًا بلا عرض']));
    if (parts.length) {
      out.brain = 'العقل: ' + parts[0] + (isNum(sg.total_requests) ? ' من ' + ar(sg.total_requests) : '') + (isNum(d.window_days) ? ' خلال آخر ' + ar(d.window_days) + ' يومًا' : '');
    } else if (isNum(sg.total_requests)) {
      out.brain = 'العقل: وصل ' + U.U(sg.total_requests, ['طلب واحد', 'طلبان', 'طلبات', 'طلبًا']) + (isNum(d.window_days) ? ' خلال آخر ' + ar(d.window_days) + ' يومًا' : '');
    }
    if (isNum(sg.open_demand_cards)) {
      out.platform = 'طلبات المنصة المفتوحة: ' + ar(sg.open_demand_cards) + (isNum(sg.open_demand_joins) ? '، انضم إليها ' + ar(sg.open_demand_joins) : '') + (isNum(sg.open_demand_goal_reached) ? '، واكتمل عدد ' + ar(sg.open_demand_goal_reached) : '');
    }
    var maxN = 0;
    var needs = Array.isArray(d.by_need_kind) ? d.by_need_kind : [];
    needs.forEach(function (n) { maxN = Math.max(maxN, Number(n.count) || 0); });
    out.byNeed = needs.map(function (n) {
      return { key: n.need_kind, label: needLabel(n.need_kind), count: Number(n.count) || 0, countText: ar(Number(n.count) || 0), zero: isNum(n.zero_offer) ? n.zero_offer : undefined,
               withOffers: isNum(n.with_offers) ? n.with_offers : undefined, total: isNum(n.total) ? n.total : undefined, pct: maxN ? Math.round((Number(n.count) || 0) * 100 / maxN) : 0 };
    });
    var courses = Array.isArray(d.suggested_courses) ? d.suggested_courses : [];
    var spec = {}, order = [];
    courses.forEach(function (c) { if (c.specialty) { if (spec[c.specialty] === undefined) { spec[c.specialty] = 0; order.push(c.specialty); } spec[c.specialty] += Number(c.signal_count) || 0; } });
    var items = order.map(function (k) { return { label: k, count: spec[k] }; });
    if (!items.length) {
      out.specs.title = 'مواضيع تتكرر'; out.specs.fallback = true;
      items = (Array.isArray(d.top_topics) ? d.top_topics : []).filter(function (t) { return t && t.term; }).map(function (t) { return { label: t.term, count: Number(t.count) || 0 }; });
    }
    items.sort(function (a, b) { return b.count - a.count; });
    items = items.slice(0, 8);
    var mx = items.length ? items[0].count : 0;
    out.specs.items = items.map(function (i) { return { label: i.label, count: i.count, countText: ar(i.count), pct: mx ? Math.round(i.count * 100 / mx) : 0 }; });
    var SRC = [['market_requests', 'طلب في السوق'], ['training_interests', 'اهتمام بالتدريب'], ['course_interests', 'اهتمام بدورة'], ['chat', 'من المحادثات'], ['open_demand_joins', 'انضمام لطلبات المنصة']];
    out.courses = courses.map(function (c) {
      var s = c.sources || {}, rs = [];
      SRC.forEach(function (p) { if (Number(s[p[0]]) > 0) rs.push(ar(s[p[0]]) + ' ' + p[1]); });
      var title = String(c.title_hint || '').trim();
      return { title: title || 'بلا عنوان', hint: title, explicit: c.origin === 'explicit', originLabel: c.origin === 'explicit' ? 'طلبها شخص صراحة' : 'مستنتجة من المحادثات',
               count: Number(c.signal_count) || 0, countText: ar(Number(c.signal_count) || 0) + ' إشارة', reason: rs.length ? rs.join(' · ') : (Array.isArray(c.samples) && c.samples[0] ? String(c.samples[0]) : ''),
               canCreate: !!title };
    });
    var top = out.courses[0];
    if (top && top.explicit && top.hint) out.topBrain = 'العقل: أكثر ما طُلب صراحةً «' + top.hint + '» (' + top.countText + ')';
    return out;
  }
  function training(resp) {
    if (!resp || resp.missing) return null;
    var rows = Array.isArray(resp.rows) ? resp.rows : [];
    var out = rows.map(function (t) {
      return { id: t.id, name: t.name || '', email: t.email || '', course: t.wanted_course || '', when: t.when || '', phone: String(t.phone || '').replace(/[^\d+]/g, '') };
    });
    return { rows: out, count: isNum(resp.count) ? resp.count : out.length, truncated: isNum(resp.count) && resp.count > out.length,
             noContact: rows.every(function (t) { return !t.status || t.status === 'new'; }) };
  }

  V.v2sMarket = { COLS: COLS, COL_LABEL: COL_LABEL, COL_EMPTY: COL_EMPTY, NEED_LABEL: NEED_LABEL, NEED_LANE: NEED_LANE, LANE_PLURAL: LANE_PLURAL, LANE_ONE: LANE_ONE,
                  STALE_REQUEST_DAYS: STALE_REQUEST_DAYS, PAGE: PAGE, merge: merge, norm: norm, brain: brain, tickets: tickets, cards: cards, header: header, tileCount: tileCount,
                  query: query, activeFilters: activeFilters, allRow: allRow, linkErr: linkErr, demand: demand, training: training, activityAt: activityAt,
                  needLabel: needLabel, laneOf: laneOf, lanePlural: lanePlural, timerText: timerText, arDigits: arDigits };
})(typeof window !== 'undefined' ? window : (typeof globalThis !== 'undefined' ? globalThis : this));
// ===== /v2s:market =====

// ===== v2s:books =====
/* ============================================================================
 * «الكتب والأعمال» (تبويب الكتب الأخير): المنطق النقي — لا DOM ولا شبكة. المدخل ردود المصادر كما وصلت (أو null لما المصدر فشل)،
 * والمخرج صفوف جاهزة للرسم: حالتها وممرّها ونص مبيعاتها وسطر العقل. ⛔ كل رقم من مصدر: المصدر الفاشل «غير متاح بعد» لا صفر.
 * ⛔ نصوص ظاهرة: فصحى بسيطة بلا مصطلحات تقنية، ولا عنوان يبدأ بـ«ذكاء» أو «AI».
 * ========================================================================== */
(function (root) {
  'use strict';
  var L = root.V2L;
  if (!L) return;
  var Un = L.util, ar = Un.ar, U = Un.U, NA = L.NA;
  var DAY = 86400e3;
  var EMAIL = /^[^@\s]{1,120}@[^@\s.]+(?:\.[^@\s.]+)+$/;
  var COPY_FORMS = ['نسخة واحدة', 'نسختان', 'نسخ', 'نسخة'];
  var WORK_FORMS = ['عمل واحد', 'عملان', 'أعمال', 'عملًا'];
  var BOOK_FORMS = ['كتاب واحد', 'كتابان', 'كتب', 'كتابًا'];
  var TYPE_TEXT = { book: 'كتاب', guide: 'دليل', research: 'بحث', memo: 'مذكرة', thesis: 'رسالة', dissertation: 'أطروحة', law: 'قانون', other: 'عمل' };
  var STATUS_TEXT = { review: 'في المراجعة', live: 'ظاهر للناس', hidden: 'مخفي', noprice: 'بلا سعر', rejected: 'مرفوض', unknown: 'الحالة: ' + NA };
  var LANES = ['review', 'noprice', 'hiddenSold', 'live', 'hidden', 'unknown', 'rejected'];
  var SALES_NA = 'المبيعات: ' + NA;
  var PLATFORM_FLOOR = 35;
  var PRICE_ERR = 'اكتب السعر رقمًا، مثل ١٥٠ أو ١٥٠٫٥٠';

  function str(v) { return typeof v === 'string' ? v.trim() : ''; }
  function ms(v) { var t = Date.parse(v || ''); return isNaN(t) ? null : t; }
  function num(v) { return typeof v === 'number' && isFinite(v) ? v : null; }
  function dateOf(t) { return t == null ? '' : Un.dateText(new Date(t).toISOString()); }
  function items(resp) { return resp && Array.isArray(resp.items) ? resp.items.filter(function (x) { return x && typeof x === 'object'; }) : null; }
  function mapBy(list, key) { var m = {}; (list || []).forEach(function (x) { var k = str(String(x[key] == null ? '' : x[key])); if (k) m[k] = x; }); return m; }
  function typeText(t) { return TYPE_TEXT[str(t)] || 'عمل'; }
  function splitText(o, p) { return 'صاحب العمل ' + ar(o) + '٪ · المنصة ' + ar(p) + '٪'; }
  function agreementOf(a) {
    if (!a || typeof a !== 'object') return '';
    var o = num(a.owner_pct), p = num(a.platform_pct);
    if (o == null || p == null) return '';
    var lab = str(a.plan_label);
    return (lab ? lab + ': ' : '') + splitText(o, p);
  }
  function ownerOf(name, email) {
    email = str(email).toLowerCase();
    var ok = EMAIL.test(email) ? email : '';
    var nm = str(name) || ok;
    return { name: nm, email: ok, na: !nm };
  }
  function cmpTitle(a, b) { return a.title.localeCompare(b.title, 'ar'); }

  // ------------------------------------------------------------------ نص المبيعات (حقائق فقط)
  function marketSales(forSale, sold) {
    if (sold == null) return SALES_NA;
    if (forSale) return sold > 0 ? 'بيعت منه ' + U(sold, COPY_FORMS) : 'لم تُبع منه نسخة بعد';
    if (sold === 0) return 'لم يأخذه أحد بعد';
    return (sold === 2 ? 'نسختان مجانيتان' : U(sold, COPY_FORMS) + ' مجانية');
  }
  function storeSales(item) {
    var n = item ? num(item.paid_owners) : null;
    if (n == null) return SALES_NA;
    return n > 0 ? 'بيعت منه ' + U(n, COPY_FORMS) : 'لم تُبع منه نسخة بعد';
  }
  function versionLine(item) {
    var n = item ? num(item.paid_owners) : null, bv = item && item.by_version;
    if (!(n > 0) || !bv || typeof bv !== 'object') return '';
    var rd = num(bv.read), pd = num(bv.pdf);
    if (rd == null || pd == null || (rd === 0 && pd === 0)) return '';
    var R = U(rd, COPY_FORMS) + ' للقراءة على المنصة', D = U(pd, COPY_FORMS) + ' للتحميل';
    if (rd > 0 && pd > 0) return 'منها ' + R + ' و' + D;
    if (rd > 0) return 'منها ' + R + ' ولا نسخة للتحميل';
    return 'منها ' + D + ' ولا نسخة للقراءة على المنصة';
  }

  // ------------------------------------------------------------------ سطر العقل لكل عمل (حقيقة واحدة بأساسها)
  function v2kBrainLine(row, now) {
    if (!row) return null;
    var forSale = row.kind === 'market' && row.forSale;
    var days = row.createdAt != null && now ? Math.floor((now - row.createdAt) / DAY) : null;
    if (row.kind === 'market' && row.status === 'review' && forSale && row.hasFile === false) {
      return { id: 'B1', text: 'لا يوجد ملف مرفق، والمنصة لا تنشر عملًا للبيع بلا ملف.', action: 'reject' };
    }
    if (row.kind === 'market' && row.status === 'hidden' && forSale && row.sold > 0) {
      return { id: 'B5', text: 'مخفي الآن. بيعت منه ' + U(row.sold, COPY_FORMS) + '، ولا يستطيع أصحابها تحميلها ما دام مخفيًا.', action: 'show' };
    }
    if (row.kind === 'store' && row.status === 'noprice') return { id: 'B3', text: 'لا سعر لهذا الكتاب بعد، فهو غير معروض للبيع.', action: 'price' };
    if (row.kind === 'store' && row.status === 'hidden') return { id: 'B4', text: 'له أسعار، لكنه مخفي عن الناس.', action: 'price' };
    if (row.kind === 'market' && row.status === 'review' && row.createdAt != null && now) {
      return { id: 'B2', text: 'ينتظر المراجعة ' + L.util.agoText(row.createdAt, now) + '.', action: 'approve' };
    }
    if (forSale && (row.status === 'live' || row.status === 'hidden') && row.legacySplit === true && row.platformPct != null && row.platformPct < PLATFORM_FLOOR) {
      return { id: 'B7', text: 'يُباع بالنسبة القديمة (المنصة ' + ar(row.platformPct) + '٪، أقل من الحد ' + ar(PLATFORM_FLOOR) + '٪) إلى أن يُنقل إلى قائمة الأسعار الموحّدة.', action: null };
    }
    if (forSale && row.status === 'live' && row.sold === 0 && days != null && days >= 30) {
      return { id: 'B6', text: 'لم تُبع منه نسخة منذ أُضيف قبل ' + ar(days) + ' يومًا.', action: null };
    }
    return null;
  }

  // ------------------------------------------------------------------ الصفوف والممرّات
  function marketRow(k, ctx, now) {
    var id = str(String(k.id == null ? '' : k.id));
    var rv = (ctx.pendMap && ctx.pendMap[id]) || (ctx.rejMap && ctx.rejMap[id]) || null;
    var st = str(k.status);
    var active = k.is_active === true;
    var status;
    if (st) status = st === 'pending_review' ? 'review' : (st === 'rejected' ? 'rejected' : (active ? 'live' : 'hidden'));
    else if (ctx.pendMap && ctx.pendMap[id]) status = 'review';
    else if (ctx.rejMap && ctx.rejMap[id]) status = 'rejected';
    else if (ctx.pendMap && ctx.rejMap) status = active ? 'live' : 'hidden';
    else status = 'unknown';
    var forSale = k.rights === 'owned_for_sale';
    var sold = num(k.total_acquired);
    var created = ms(k.created_at); if (created == null && rv) created = ms(rv.created_at);
    var updated = ms(k.updated_at); if (updated == null && rv) updated = ms(rv.updated_at);
    var hasFile = typeof k.has_file === 'boolean' ? k.has_file : (rv && typeof rv.has_file === 'boolean' ? rv.has_file : null);
    var note = str(k.review_note) || str(rv && rv.review_note);
    var legacy = typeof k.legacy_split === 'boolean' ? k.legacy_split : null;
    var ownerPct = num(k.owner_pct), platPct = num(k.platform_pct);
    var o = ownerOf(k.owner_name, k.owner_email);
    var agreement;
    if (!forSale) agreement = 'مجاني، لا بيع فيه';
    else if (legacy === true && ownerPct != null && platPct != null) agreement = splitText(ownerPct, platPct) + ' — النسبة القديمة، إلى أن يُنقل إلى قائمة الأسعار الموحّدة';
    else agreement = NA;
    var priceAmount = num(k.price_amount);
    var priceText = forSale ? (priceAmount != null ? Un.moneyText(priceAmount, k.price_currency || 'EGP') : NA) : 'مجاني للجميع';
    var lane = status === 'hidden' ? (forSale && sold > 0 ? 'hiddenSold' : 'hidden') : status;
    var row = {
      key: 'kn:' + id, kind: 'market', id: id, title: str(k.title) || 'عمل بلا عنوان', typeText: typeText(k.type),
      ownerName: o.name, ownerEmail: o.email, ownerNA: o.na, status: status, statusText: STATUS_TEXT[status], lane: lane,
      salesText: marketSales(forSale, sold), salesNA: sold == null, salesSub: '', priceText: priceText,
      createdText: dateOf(created), createdAt: created, updatedAt: updated, waitingSince: status === 'review' ? created : null, hasFile: hasFile, reviewNote: note,
      agreementText: agreement, legacySplit: legacy, platformPct: platPct, catalogId: null, brain: null, forSale: forSale, sold: sold,
      isActive: active, bid: k.bid_enabled === true, priceAmount: priceAmount, priceCurrency: str(k.price_currency) || 'EGP', slug: str(k.slug), raw: k
    };
    row.brain = v2kBrainLine(row, now);
    return row;
  }
  function storeRow(p, ctx, now) {
    var it = ctx.storeMap ? ctx.storeMap[p.id] || null : null;
    var off = ctx.liveOffers[p.id] || null;
    var src = it || off;
    var o = ownerOf(it ? (it.owner_name || (off && off.owner_name)) : (off && off.owner_name), it ? (it.owner_email || (off && off.owner_email)) : (off && off.owner_email));
    var status = !p.hasPrices ? 'noprice' : (p.visible ? 'live' : 'hidden');
    var agreement = '';
    if (it && it.source === 'ours') agreement = 'كتاب من البروفيسور';
    if (!agreement && it) agreement = agreementOf({ plan_label: it.plan_label, owner_pct: it.owner_pct, platform_pct: it.platform_pct });
    if (!agreement && off) agreement = agreementOf(off.agreement);
    var sold = it ? num(it.paid_owners) : null;
    var row = {
      key: 'st:' + p.id, kind: 'store', id: p.id, title: p.title || 'عمل بلا عنوان', typeText: (src && src.type ? typeText(src.type) : 'كتاب') + ' من المتجر',
      ownerName: o.name, ownerEmail: o.email, ownerNA: o.na, status: status, statusText: STATUS_TEXT[status], lane: status,
      salesText: storeSales(it), salesNA: sold == null, salesSub: versionLine(it), priceText: p.mins && p.mins.length ? p.minText : 'لا سعر بعد',
      createdText: '', createdAt: null, updatedAt: null, waitingSince: null, hasFile: null, reviewNote: '', agreementText: agreement || NA, legacySplit: null, platformPct: null,
      catalogId: (it && it.catalog_id) || (off && off.catalog_id) || null, brain: null, forSale: true, sold: sold, isActive: !!p.visible, bid: false,
      priceAmount: null, priceCurrency: '', slug: p.id, raw: p
    };
    row.brain = v2kBrainLine(row, now);
    return row;
  }
  function offerRow(o) {
    var ow = ownerOf(o.owner_name, o.owner_email);
    var sp = o.suggested_price, amount = sp && num(sp.amount) > 0 ? num(sp.amount) : null;
    var at = ms(o.reviewed_at) || ms(o.decided_at) || ms(o.updated_at) || ms(o.submitted_at);
    var sub = ms(o.submitted_at);
    return {
      key: 'of:' + str(String(o.id)), kind: 'offer', id: str(String(o.id)), title: str(o.title) || 'عمل بلا عنوان', typeText: typeText(o.type),
      ownerName: ow.name, ownerEmail: ow.email, ownerNA: ow.na, status: 'rejected', statusText: STATUS_TEXT.rejected, lane: 'rejected',
      salesText: '', salesNA: false, salesSub: '', priceText: amount != null ? Un.moneyText(amount, sp.currency) : 'لم يقترح سعرًا',
      createdText: dateOf(sub), createdAt: sub, updatedAt: at, waitingSince: null, hasFile: null, reviewNote: str(o.review_note), agreementText: agreementOf(o.agreement) || NA,
      legacySplit: null, platformPct: null, catalogId: null, brain: null, forSale: false, sold: null, isActive: false, bid: false, priceAmount: amount, priceCurrency: sp ? str(sp.currency) : '',
      slug: '', raw: o
    };
  }
  function soldDesc(a, b) {
    var x = a.sold == null ? -1 : a.sold, y = b.sold == null ? -1 : b.sold;
    return y - x || cmpTitle(a, b);
  }
  var SORTS = {
    review: function (a, b) {
      var x = a.waitingSince == null ? Infinity : a.waitingSince, y = b.waitingSince == null ? Infinity : b.waitingSince;
      if (x !== y) return x < y ? -1 : 1;
      return cmpTitle(a, b);
    },
    noprice: cmpTitle, hiddenSold: soldDesc, live: soldDesc, hidden: cmpTitle, unknown: cmpTitle,
    rejected: function (a, b) { return (b.updatedAt || 0) - (a.updatedAt || 0) || cmpTitle(a, b); }
  };

  function v2kWorks(src, now) {
    src = src || {};
    var kn = items(src.knowledge), pend = items(src.revPending), rej = items(src.revRejected);
    var pricesClosed = src.prices === 'closed', priceRes = pricesClosed ? null : L.v2Prices(src.prices);
    var offersClosed = src.offers === 'closed';
    var offList = !offersClosed && src.offers && Array.isArray(src.offers.offers) ? src.offers.offers.filter(function (o) { return o && o.id; }) : null;
    var storeClosed = src.store === 'closed', storeList = storeClosed ? null : items(src.store);
    if (!kn && !priceRes && !offList) return null;

    var ctx = { pendMap: pend ? mapBy(pend, 'id') : null, rejMap: rej ? mapBy(rej, 'id') : null,
                storeMap: storeList ? mapBy(storeList, 'slug') : null, liveOffers: {} };
    (offList || []).forEach(function (o) { if (o.status === 'live' && str(o.catalog_slug)) ctx.liveOffers[str(o.catalog_slug)] = o; });

    var rows = [], byKey = {};
    function add(r) { if (!byKey[r.key]) { byKey[r.key] = r; rows.push(r); } }
    var base = (kn || []).slice(), have = mapBy(base, 'id');
    // أعمال في قوائم المراجعة ولم تصل في قائمة السوق: تبقى ظاهرة (لا يضيع عمل ينتظر قرارًا)
    [pend, rej].forEach(function (lst) { (lst || []).forEach(function (r) { var id = str(String(r.id == null ? '' : r.id)); if (id && !have[id]) { have[id] = r; base.push(r); } }); });
    base.forEach(function (k) { if (str(String(k.id == null ? '' : k.id))) add(marketRow(k, ctx, now)); });
    (priceRes ? priceRes.rows : []).forEach(function (p) { add(storeRow(p, ctx, now)); });
    (offList || []).filter(function (o) { return o.status === 'rejected'; }).forEach(function (o) { add(offerRow(o)); });

    var lanes = {}, counts = {};
    LANES.forEach(function (l) {
      lanes[l] = rows.filter(function (r) { return r.lane === l; }).sort(SORTS[l]).map(function (r) { return r.key; });
      counts[l] = lanes[l].length;
    });
    var needsRev = !!(kn && kn.some(function (k) { return !str(k.status); }));
    var revFail = needsRev && (!pend || !rej);
    var failedK = !kn;
    var storeFail = !pricesClosed && !priceRes;
    var partial = {
      review: failedK || (needsRev && !pend) || (!kn && !pend),
      noprice: storeFail, hiddenSold: failedK || revFail, live: failedK || revFail || storeFail, hidden: failedK || revFail || storeFail,
      unknown: false, rejected: failedK || (needsRev && !rej) || (!offersClosed && !offList)
    };
    var failed = [];
    if (failedK) failed.push('أعمال السوق');
    if (revFail) failed.push('حالة المراجعة');
    if (storeFail) failed.push('كتب المتجر');
    if (!offersClosed && !offList) failed.push('عروض الكتب');
    if (!storeClosed && !storeList && priceRes) failed.push('بيانات المتجر');
    var waiting = offList ? offList.filter(function (o) { return o.status === 'in_review'; }).length : null;
    return { rows: rows, lanes: lanes, counts: counts, partial: partial, offersWaiting: waiting, storeClosed: pricesClosed, failed: failed };
  }

  // ------------------------------------------------------------------ البحث
  function v2kKey(text) {
    return String(text == null ? '' : text).toLowerCase()
      .replace(/[ً-ٰٟـ]/g, '')
      .replace(/[أإآٱ]/g, 'ا').replace(/ة/g, 'ه').replace(/ى/g, 'ي')
      .replace(/[٠-٩]/g, function (d) { return String(d.charCodeAt(0) - 0x660); })
      .replace(/[۰-۹]/g, function (d) { return String(d.charCodeAt(0) - 0x6F0); })
      .replace(/\s+/g, ' ').trim();
  }
  function v2kSearch(res, q) {
    if (!res) return {};
    var k = v2kKey(q);
    if (!k) return res.lanes;
    var by = {}; res.rows.forEach(function (r) { by[r.key] = r; });
    var out = {};
    LANES.forEach(function (l) {
      var hit = (res.lanes[l] || []).filter(function (key) { var r = by[key]; return r && v2kKey(r.title + ' ' + r.ownerName).indexOf(k) > -1; });
      if (hit.length) out[l] = hit;
    });
    return out;
  }

  // ------------------------------------------------------------------ ملخّص العقل
  function v2kBrainSummary(res) {
    if (!res) return null;
    var c = res.counts, p = res.partial, parts = [];
    if (c.review > 0) parts.push('في انتظار مراجعتك: ' + U(c.review, WORK_FORMS) + ' من السوق');
    if (c.noprice > 0) parts.push('بلا سعر: ' + U(c.noprice, BOOK_FORMS));
    if (c.hiddenSold > 0) parts.push('مخفي وبيعت منه نسخ: ' + U(c.hiddenSold, WORK_FORMS));
    var some = p.review || p.noprice || p.hiddenSold;
    var tail = ' — وبعض المصادر لم تصل، فقد يكون العدد أكبر';
    var lane = c.review > 0 ? 'review' : (c.noprice > 0 ? 'noprice' : (c.hiddenSold > 0 ? 'hiddenSold' : null));
    var label = { review: 'ابدأ المراجعة', noprice: 'اعرض الكتب بلا سعر', hiddenSold: 'اعرض المخفي المبيع' };
    if (!parts.length) return { text: some ? 'لا شيء ظاهرًا ينتظرك الآن' + tail : 'لا شيء ينتظرك في الكتب والأعمال الآن.', action: null };
    return { text: parts.join(' · ') + (some ? tail : ''), action: { label: label[lane], lane: lane } };
  }
  // ما تقرؤه الأقسام الأخرى بلا جلب: أعداد أو null لما لا يُعرف
  function v2kSummary(res) {
    if (!res) return { review: null, noprice: null, hiddenSold: null, legacySplit: null, offersWaiting: null, partial: true };
    var sale = res.rows.filter(function (r) { return r.kind === 'market' && r.forSale && (r.status === 'live' || r.status === 'hidden'); });
    var unknownSplit = sale.some(function (r) { return r.legacySplit === null; });
    var any = res.partial.review || res.partial.noprice || res.partial.hiddenSold;
    return { review: res.partial.review ? null : res.counts.review, noprice: res.partial.noprice ? null : res.counts.noprice, hiddenSold: res.partial.hiddenSold ? null : res.counts.hiddenSold,
             legacySplit: unknownSplit ? null : sale.filter(function (r) { return r.legacySplit === true; }).length, offersWaiting: res.offersWaiting, partial: !!any };
  }

  // ------------------------------------------------------------------ تعديل عمل من السوق (قبل ⇒ بعد)
  function bidText(b) { return b ? 'مفعّل' : 'غير مفعّل'; }
  function v2kEditDiff(row, input) {
    input = input || {};
    var title = str(input.title);
    if (!title) return { ok: false, error: 'اكتب عنوان العمل', changed: false, lines: [], body: {} };
    var lines = [], body = {};
    if (title !== row.title) { lines.push({ label: 'العنوان', from: row.title, to: title }); body.title = title; }
    if (row.forSale) {
      var n = Un.parseAmount(input.priceText);
      // سعر غير معروف الآن وحقل السعر فارغ: لا بند سعر (العنوان و«اعرض سعرك» يمرّان)؛ وإن كتب المؤسس سعرًا فيُفحص كالمعتاد
      var skipPrice = row.priceAmount == null && n === null;
      if (!skipPrice) {
        if (n === null || isNaN(n)) return { ok: false, error: PRICE_ERR, changed: false, lines: [], body: {} };
        if (!(n > 0)) return { ok: false, error: 'اكتب سعرًا أكبر من صفر', changed: false, lines: [], body: {} };
        if (row.priceAmount == null || Math.abs(n - row.priceAmount) > 1e-9) {
          lines.push({ label: 'السعر', from: row.priceAmount == null ? NA : Un.moneyText(row.priceAmount, row.priceCurrency), to: Un.moneyText(n, row.priceCurrency) });
          body.price_egp = n;
        }
      }
      var bid = !!input.bid;
      if (bid !== !!row.bid) { lines.push({ label: '«اعرض سعرك»', from: bidText(row.bid), to: bidText(bid) }); body.bid_enabled = bid; }
    }
    return { ok: true, error: '', changed: lines.length > 0, lines: lines, body: body };
  }

  // ------------------------------------------------------------------ إضافة كتاب
  function v2kAddBook(input) {
    input = input || {};
    var title = str(input.title), file = str(input.fileUrl), cover = str(input.coverUrl);
    function bad(e) { return { ok: false, error: e, body: null }; }
    if (!title) return bad('اكتب عنوان الكتاب');
    if (!/^https:\/\/\S+$/i.test(file)) return bad('الصق رابطًا يبدأ بـ \u2066https://\u2069');
    if (cover && !/^https:\/\/\S+$/i.test(cover)) return bad('رابط الصورة يجب أن يبدأ بـ \u2066https://\u2069');
    var price = Un.parseAmount(input.priceText);
    if (price !== null && isNaN(price)) return bad(PRICE_ERR);
    var cur = str(input.currency).toUpperCase() === 'USD' ? 'USD' : 'EGP';
    return { ok: true, error: '', body: { title: title.slice(0, 300), author: str(input.author).slice(0, 200), description: str(input.description).slice(0, 2000),
                                          price: price || 0, currency: cur, file_url: file, cover_url: cover, is_active: input.active !== false } };
  }

  // ------------------------------------------------------------------ مجلد Google Drive
  function v2kFolderId(text) {
    var t = str(text);
    if (!t) return '';
    var m = t.match(/\/folders\/([A-Za-z0-9_-]{10,})/) || t.match(/[?&]id=([A-Za-z0-9_-]{10,})/);
    if (m) return m[1];
    return /^[A-Za-z0-9_-]{10,}$/.test(t) ? t : '';
  }

  // ------------------------------------------------------------------ تحذير الإخفاء
  function v2kHideWarning(row) {
    if (!row || row.kind !== 'market' || !row.forSale || !(row.sold > 0)) return '';
    return 'بيعت منه ' + U(row.sold, COPY_FORMS) + '، ومن اشتراه لا يستطيع تحميله ما دام مخفيًا.';
  }

  L.v2kLanes = LANES;
  L.v2kWorks = v2kWorks; L.v2kSearch = v2kSearch; L.v2kKey = v2kKey; L.v2kBrainLine = v2kBrainLine; L.v2kBrainSummary = v2kBrainSummary;
  L.v2kSummary = v2kSummary; L.v2kEditDiff = v2kEditDiff; L.v2kAddBook = v2kAddBook; L.v2kFolderId = v2kFolderId; L.v2kHideWarning = v2kHideWarning;
})(typeof window !== 'undefined' ? window : globalThis);
// ===== /v2s:books =====

// ===== v2s:people =====
// «الناس والدعوات» (نهائي): طلبات الدخول · خط الدعوات · قائمة الحسابات · تذاكر الرسائل. ⛔ نقي: لا DOM ولا شبكة ولا ساعة خفية (`now` يُمرَّر).
// ⛔ الرقم المجهول `null` لا صفر. ⛔ لا نص من الذكاء الاصطناعي: سطر العقل يُبنى من حقول موجودة فقط. نصوص التذاكر الواردة من الوارد
// تُنسخ من `v2Card` بالحرف (فتقرأ «ابدأ القرارات» و«الطلبات» نفس الجملة).
(function (root) {
  'use strict';
  var L = root.V2L; if (!L) return;
  var UT = L.util, ar = UT.ar, UF = UT.U, agoText = UT.agoText, dateText = UT.dateText;
  var HOUR = 3600e3, DAY = 86400e3, NA = L.NA;

  function str(v) { return typeof v === 'string' ? v.trim() : ''; }
  function ms(v) {
    if (typeof v === 'number') return isFinite(v) && v > 0 ? v : NaN;
    var t = Date.parse(v || ''); return isNaN(t) ? NaN : t;
  }
  function shorten(s, n) { s = String(s == null ? '' : s).replace(/\s+/g, ' ').trim(); return s.length > n ? s.slice(0, n) + '…' : s; }
  function clean(a) { return a.filter(function (x) { return x; }); }
  function digitsOf(p) { return String(p == null ? '' : p).replace(/\D/g, ''); }
  function hasEmail(set, email) {
    if (!set) return false;
    email = String(email || '').toLowerCase();
    if (!email) return false;
    if (typeof set.has === 'function') return set.has(email);
    return Array.isArray(set) && set.indexOf(email) > -1;
  }
  function byOld(a, b) { var x = isNaN(a.ts) ? Infinity : a.ts, y = isNaN(b.ts) ? Infinity : b.ts; return x - y; }

  // ---------------------------------------------------------------- ألفاظ ثابتة
  var STAGE = { pending: 'لم تُفتح بعد', opened: 'فتح الرابط', roles_chosen: 'اختيار الصفة', pain_seen: 'مشاهدة التعريف', exercised: 'تجربة مثال',
                declared: 'الموافقة على الشروط', registered: 'الانضمام', expired: 'انتهت مهلتها', revoked: 'سُحبت', awaiting_approval: 'تنتظر موافقتك', rejected: 'رُفضت' };
  function stageLabel(stage) { return STAGE[stage] || ''; }
  var JOURNEY = ['opened', 'roles_chosen', 'pain_seen', 'exercised', 'declared'];

  function waText(kind, name, link) {
    var n = str(name), head = n ? 'أهلًا ' + n + '،' : 'أهلًا،';
    if (kind === 'remind') return head + '\nدعوتك إلى منصة البروفيسور ما زالت بانتظارك، ويمكنك إكمالها من الرابط نفسه:\n' + link;
    return head + '\nهذه دعوتك إلى منصة البروفيسور، وهي باسمك وحدك:\n' + link;
  }
  // رقم واتساب صالح للرابط: يبدأ بـ«+» أو «00» (رمز الدولة موجود) وطوله ٨–١٥ رقمًا. الرقم المحلي (٠١٠…) يُعطي رابطًا ميتًا
  // فلا يُبنى له رابط واتساب أبدًا — يرجع '' ويُعرض الرقم للنسخ أو يُستخدم البريد.
  function waNumber(phone) {
    var raw = String(phone == null ? '' : phone).replace(/[\s\-().]/g, '');
    if (raw.indexOf('00') === 0) raw = '+' + raw.slice(2);
    if (raw.charAt(0) !== '+') return '';
    var d = digitsOf(raw);
    return d.length >= 8 && d.length <= 15 ? d : '';
  }
  function waUrl(phone, text) {
    var d = waNumber(phone);
    return (d ? 'https://wa.me/' + d : 'https://wa.me/') + '?text=' + encodeURIComponent(text);
  }
  function inviterKey(r) {
    var id = r && typeof r.invitedByUserId === 'string' ? r.invitedByUserId.trim() : '';
    if (id) return 'u:' + id;
    var g = r ? r.generation : null;
    // المؤسس بلا معرّف مستخدم: جيله صفر/غائب، أو الجسر سمّاه «المؤسس» (نوع الداعي founder يصل إلى المحمّل كهذه التسمية). غير ذلك ⇒ بلا داعٍ محدد.
    return (g == null || g === 0 || (r && r.invitedByLabel === 'المؤسس')) ? 'founder' : 'none';
  }
  var PLAN_FALLBACK = { free: 'مجانية', pro: 'احترافية', premium: 'بريميوم' };
  function planLabel(planId, packages) {
    var id = str(planId);
    if (Array.isArray(packages)) for (var i = 0; i < packages.length; i++) if (packages[i] && packages[i].id === id && str(packages[i].name)) return packages[i].name;
    return PLAN_FALLBACK[id] || 'الباقة غير متاحة بعد';
  }
  var SEG = { individual: 'أفراد', employee: 'موظفون', government: 'حكومي', student: 'طلاب', lawyer: 'محامون', senior: 'محامٍ خبير', prof: 'أستاذ جامعة',
              trainer: 'مدرّبون', company: 'شركات', firm: 'شركة محاماة', grad: 'خريج جديد', influencer: 'مؤثر أو رائد أعمال', researcher: 'باحثون', prosecutor: 'وكلاء نيابة' };
  var ROLE = { admin: 'إدارة', staff: 'فريق العمل', member: 'عضو', investor: 'مستثمر' };

  // ---------------------------------------------------------------- الدعوات: خط الرحلة
  function stageOf(r) {
    var st = str(r.stage) || str(r.status) || 'pending';
    if (r.status === 'awaiting_approval' || r.status === 'rejected') st = r.status;
    else if (r.revoked && st !== 'registered') st = 'revoked';
    return st;
  }
  function expiryText(r, now) {
    var e = ms(r.expiresAt);
    if (isNaN(e)) return '';
    if (e <= now) return 'انتهت مهلتها';
    return 'تنتهي بعد ' + UF(Math.ceil((e - now) / DAY), ['يوم واحد', 'يومين', 'أيام', 'يومًا']);
  }
  function inviteItem(r, col, now) {
    var st = stageOf(r), at = ms(r.at), email = str(r.email), name = str(r.name);
    var link = str(r.link), phone = str(r.phone);
    var it = { id: String(r.id || ''), stage: st, name: name || 'بلا اسم', title: name || 'بلا اسم', email: email, phone: phone, inviteUrl: link, ts: at, ref: r,
               strip: st === 'rejected' ? 'رُفضت' : (stageLabel(st) || ''), ageText: isNaN(at) ? '' : 'أُرسلت ' + agoText(at, now),
               sub: clean([str(r.invitedByLabel) && r.invitedByLabel !== '—' ? 'الداعي: ' + r.invitedByLabel : '', r.rolesLabel && r.rolesLabel !== '—' ? r.rolesLabel : '',
                           r.specialtyLabel && r.specialtyLabel !== '—' ? r.specialtyLabel : '']).join(' · '),
               expiry: (col === 'waiting' || col === 'journey') ? expiryText(r, now) : '', docRequested: !!r.docRequested,
               teamNote: st === 'rejected' && str(r.approvalNote) ? 'ملاحظة الفريق: ' + str(r.approvalNote) : '', person: null, primary: null, secondary: [] };
    if (col === 'joined' && email) it.person = email;
    var detail = { label: 'التفاصيل', act: { do: 'sheet', sheet: 'invite' } }, revoke = { label: 'اسحب الدعوة', act: { do: 'sheet', sheet: 'revoke' } };
    if (col === 'waiting') {
      if (link) { it.primary = { label: 'انسخ الرابط', act: { do: 'copy' } }; it.secondary = [{ label: 'أرسل عبر واتساب', act: { do: 'wa', kind: 'invite' } }, revoke]; }
      else { it.primary = { label: 'الرابط غير متاح من المنصة', act: { do: 'none' }, disabled: true }; it.secondary = [revoke]; }
    } else if (col === 'journey') {
      if (link) { it.primary = { label: 'ذكّر عبر واتساب', act: { do: 'wa', kind: 'remind' } }; it.secondary = [detail, revoke]; }
      else { it.primary = detail; it.secondary = [revoke]; }
    } else if (col === 'joined') {
      it.primary = email ? { label: 'افتح صفحة الشخص', act: { do: 'person', email: email } } : detail;
    } else {
      it.primary = { label: 'أعِد إصدارها', act: { do: 'sheet', sheet: 'reissue' } }; it.secondary = [detail];
    }
    return it;
  }
  // pipeline(invData, invState, now, inviter) ⇒ بطاقات وأعمدة الدعوات. الحالة المجهولة ⇒ null لا صفر.
  function pipeline(inv, invState, now, inviter) {
    var empty = { state: 'loading', cards: { sent: null, opened: null, joined: null, awaiting: null }, pct: { opened: null, joined: null }, steps: [],
                  cols: { waiting: { items: [], total: 0, shown: 0 }, journey: { items: [], total: 0, shown: 0 }, joined: { items: [], total: 0, shown: 0 }, stopped: { items: [], total: 0, shown: 0 } },
                  inviters: [], stalled: null, expiring: null, brain: [], partial: null, awaitingRows: [] };
    var stepDefs = [['roles_chosen', 'اختيار الصفة'], ['exercised', 'تجربة مثال'], ['declared', 'الشروط']];
    empty.steps = stepDefs.map(function (d) { return { key: d[0], label: d[1], n: null }; });
    if (invState === 'idle' || invState === 'loading' || (!inv && invState !== 'error')) return empty;
    if (invState === 'error' || !inv || inv.missing) { empty.state = (inv && inv.missing) ? 'missing' : 'failed'; return empty; }
    var rows = Array.isArray(inv.rows) ? inv.rows : [];
    var counts = inv.counts || null;
    var out = empty; out.state = 'ready';
    var awaiting = [], board = [];
    rows.forEach(function (r) { var st = stageOf(r); if (st === 'awaiting_approval') awaiting.push(r); else board.push(r); });
    var rejected = board.filter(function (r) { return stageOf(r) === 'rejected'; }).length;
    var sent = rows.length - awaiting.length - rejected;
    var opened = rows.filter(function (r) { return r.opened; }).length, joined = rows.filter(function (r) { return r.registered; }).length;
    out.cards = { sent: sent, opened: opened, joined: joined, awaiting: awaiting.length };
    out.pct = { opened: sent > 0 ? ar(Math.round(opened * 100 / sent)) + '٪ مما أُرسل' : null, joined: sent > 0 ? ar(Math.round(joined * 100 / sent)) + '٪ مما أُرسل' : null };
    out.steps = stepDefs.map(function (d) { return { key: d[0], label: d[1], n: counts && counts[d[0]] != null ? counts[d[0]] : null }; });
    out.awaitingRows = awaiting;
    // الداعي
    var tally = {}, order = [];
    board.forEach(function (r) {
      var k = inviterKey(r);
      if (!tally[k]) { tally[k] = { key: k, n: 0, name: str(r.invitedByLabel) }; order.push(k); }
      tally[k].n++;
    });
    var members = order.filter(function (k) { return k.indexOf('u:') === 0; }).map(function (k) { return tally[k]; }).sort(function (a, b) { return b.n - a.n; });
    out.inviters = [{ key: 'all', label: 'كل الداعين (' + ar(board.length) + ')', n: board.length }];
    if (tally.founder) out.inviters.push({ key: 'founder', label: 'المؤسس (' + ar(tally.founder.n) + ')', n: tally.founder.n });
    members.forEach(function (m) { out.inviters.push({ key: m.key, label: (m.name && m.name !== '—' ? m.name : 'عضو') + ' (' + ar(m.n) + ')', n: m.n }); });
    if (tally.none) out.inviters.push({ key: 'none', label: 'بلا داعٍ محدد (' + ar(tally.none.n) + ')', n: tally.none.n });
    var pick = inviter && inviter !== 'all' ? inviter : '';
    var shownRows = pick ? board.filter(function (r) { return inviterKey(r) === pick; }) : board;
    var cols = { waiting: [], journey: [], joined: [], stopped: [] };
    shownRows.forEach(function (r) {
      var st = stageOf(r);
      if (st === 'pending') cols.waiting.push(r);
      else if (JOURNEY.indexOf(st) > -1) cols.journey.push(r);
      else if (st === 'registered') cols.joined.push(r);
      else if (st === 'expired' || st === 'revoked' || st === 'rejected') cols.stopped.push(r);
    });
    var newest = function (a, b) { var x = isNaN(ms(a.at)) ? 0 : ms(a.at), y = isNaN(ms(b.at)) ? 0 : ms(b.at); return y - x; };
    Object.keys(cols).forEach(function (c) {
      var list = cols[c].slice().sort(newest);
      var total = list.length;
      if (c === 'joined') {
        list = list.filter(function (r) { var t = ms(r.registeredAt); if (isNaN(t)) t = ms(r.at); return !isNaN(t) && now - t <= 7 * DAY; });
      }
      var items = list.map(function (r) { return inviteItem(r, c, now); });
      out.cols[c] = { items: items, total: c === 'joined' ? cols.joined.length : total, shown: (c === 'joined' || c === 'stopped') ? 3 : 6 };
      if (c === 'joined') out.cols.joined.all = cols.joined.slice().sort(newest).map(function (r) { return inviteItem(r, 'joined', now); });
    });
    // المتوقف والمنتهي قريبًا (على كل الصفوف لا على الفلتر)
    var stalled = 0, expiring = 0;
    board.forEach(function (r) {
      var st = stageOf(r), at = ms(r.at), ex = ms(r.expiresAt);
      if (JOURNEY.indexOf(st) > -1 && !isNaN(at) && now - at > 72 * HOUR) stalled++;
      if ((st === 'pending' || JOURNEY.indexOf(st) > -1) && !isNaN(ex) && ex > now && ex - now <= 48 * HOUR) expiring++;
    });
    out.stalled = stalled; out.expiring = expiring;
    out.brain = ['أُرسلت ' + ar(sent) + '، فُتح منها ' + ar(opened) + ' وانضمّ ' + ar(joined) + '.'];
    if (stalled > 0) out.brain.push(UF(stalled, ['دعوة واحدة فُتحت ولم تكتمل وقد مرّ على إرسالها أكثر من ٣ أيام', 'دعوتان فُتحتا ولم تكتملا وقد مرّ على إرسالهما أكثر من ٣ أيام',
      'دعوات فُتحت ولم تكتمل وقد مرّ على إرسالها أكثر من ٣ أيام', 'دعوة فُتحت ولم تكتمل وقد مرّ على إرسالها أكثر من ٣ أيام']) + ' — ذكّر أصحابها عبر واتساب.');
    if (expiring > 0) out.brain.push(UF(expiring, ['دعوة واحدة تنتهي مهلتها خلال يومين', 'دعوتان تنتهي مهلتهما خلال يومين', 'دعوات تنتهي مهلتها خلال يومين', 'دعوة تنتهي مهلتها خلال يومين']) + '.');
    out.partial = (inv.count != null && inv.count > rows.length) ? { shown: rows.length, total: inv.count } : null;
    return out;
  }

  // ---------------------------------------------------------------- الطلبات: من ينتظر الدخول
  var LBL_VISIT = 'زوّار ينتظرون الفتح', LBL_JOIN = 'طلبات تقديم الخدمة', LBL_FOUND = 'ليدات خبير مؤسس';
  function waDigits(row) {
    var d = Array.isArray(row.details) ? row.details : [];
    for (var i = 0; i < d.length; i++) if (d[i] && d[i].k === 'واتساب') { return waNumber(d[i].v); }
    return '';
  }
  function inboxHalf(inp, label) {
    var st = inp.inboxState;
    if (st === 'idle' || st === 'loading' || (!inp.inbox && st !== 'error')) return 'loading';
    if (st === 'error' || !inp.inbox) return 'failed';
    if ((inp.failed || []).indexOf(label) > -1) return 'failed';
    return 'ready';
  }
  function hasTrunc(inp, label) {
    return (inp.trunc || []).some(function (t) { return String(t).split(':')[0].trim() === label; });
  }
  function cardTicket(row, kind, now, userEmails) {
    var card = L.v2Card(row, { now: now });
    if (!card) return null;
    var t = { id: kind + ':' + (row.apiId != null ? row.apiId : row.ref), kind: kind, tag: card.tag, age: card.ageText, title: card.title, sub: card.sub, brain: card.brain,
              reason: card.reason, warn: card.warn, extra: [], link: null, primary: null, secondary: [], ref: row, ts: card.ts };
    var email = str(row.personEmail) || str(row.email);
    if (kind === 'visitor' || (kind === 'join' && email) || (kind === 'founding' && hasEmail(userEmails, email))) t.link = email.toLowerCase() || null;
    return { ticket: t, card: card };
  }
  function requests(inp, now) {
    inp = inp || {};
    var out = { cols: {}, later: { state: 'loading', rows: [], shown: 0, total: null }, head: { text: '', failedLabels: [], invitesLine: null } };
    var defs = { visitors: ['ينتظرون فتح المنصة', 'الزوّار', 'amber'], approval: ['دعوات تنتظر موافقتك', 'الدعوات', 'amber'],
                 join: ['طلبات تقديم خدمة', 'الخدمات', 'ink'], founding: ['خبراء مؤسسون', 'المؤسسون', 'green'] };
    Object.keys(defs).forEach(function (k) {
      out.cols[k] = { state: 'loading', count: null, countText: '…', partial: false, items: [], retry: [], label: defs[k][0], short: defs[k][1], tone: defs[k][2] };
    });
    var rows = Array.isArray(inp.inbox) ? inp.inbox : [];
    var failedLabels = [];
    function setState(col, state, items, extra) {
      var c = out.cols[col]; c.state = state; c.items = items || [];
      if (state === 'ready') { c.count = c.items.length; c.countText = ar(c.count); }
      else if (state === 'mixed') { c.count = c.items.length; c.countText = ar(c.count) + '+؟'; }
      else if (state === 'loading') { c.count = null; c.countText = '…'; }
      else { c.count = null; c.countText = '—'; }
      if (extra) Object.keys(extra).forEach(function (x) { c[x] = extra[x]; });
    }
    // —— العمود ١: زوّار (الوارد) + قائمة الانتظار
    var half1 = inboxHalf(inp, LBL_VISIT);
    var wlState = inp.waitlistState, wl = inp.waitlist;
    var half2 = (wlState === 'idle' || wlState === 'loading' || (!wl && wlState !== 'error')) ? 'loading' : (wlState === 'error' || !wl ? 'failed' : (wl.missing ? 'missing' : 'ready'));
    var visTickets = [], notePending = [];
    if (half1 === 'ready') {
      rows.filter(function (r) { return r && r.apiKind === 'pending_user'; }).forEach(function (r) {
        var x = cardTicket(r, 'visitor', now, inp.userEmails); if (!x) return;
        var t = x.ticket, flagged = !!(r.flagLabels && r.flagLabels.length);
        t.primary = flagged ? { label: x.card.primary.label, act: { do: 'sheet', sheet: 'visitor' } } : { label: x.card.primary.label, act: { do: 'decide', action: 'approve' } };
        t.secondary = flagged ? [] : [{ label: 'التفاصيل', act: { do: 'sheet', sheet: 'visitor' } }];
        visTickets.push(t);
      });
    }
    if (half2 === 'ready') {
      (wl.rows || []).filter(function (w) { return w && (w.status || 'new') === 'new'; }).forEach(function (w) {
        var at = ms(w.at);
        var sub = clean([w.roleLabel !== '—' ? w.roleLabel : '', w.specialtyLabel !== '—' ? w.specialtyLabel : '', w.countryLabel !== '—' ? w.countryLabel : '']).join(' · ');
        var extra = str(w.note) ? ['سبب الطلب: ' + shorten(w.note, 140)] : [];
        visTickets.push({ id: 'waitlist:' + w.id, kind: 'waitlist', tag: 'من قائمة الانتظار', age: isNaN(at) ? '' : agoText(at, now), title: str(w.name) || 'بلا اسم', sub: sub,
          brain: 'طلب دعوة من الموقع ولا يملك حسابًا بعد', reason: '', warn: '', extra: extra, link: null, ts: at, ref: w,
          primary: { label: 'أرسل دعوة', act: { do: 'sheet', sheet: 'phone' } }, secondary: [{ label: 'التفاصيل', act: { do: 'sheet', sheet: 'waitlist' } }] });
      });
    }
    visTickets.sort(byOld);
    var retry1 = [];
    if (half1 === 'failed') retry1.push({ key: 'inbox', label: 'الزوّار' });
    if (half2 === 'failed') retry1.push({ key: 'waitlist', label: 'قائمة الانتظار' });
    if (half2 === 'missing') retry1.push({ key: 'waitlist', label: 'قائمة الانتظار', missing: true });
    var s1;
    if (half1 === 'loading' || half2 === 'loading') s1 = 'loading';
    else if (half1 === 'ready' && half2 === 'ready') s1 = 'ready';
    else if (half1 !== 'ready' && half2 !== 'ready') s1 = 'failed';
    else s1 = 'mixed';
    if (s1 === 'loading') setState('visitors', 'loading', []);
    else setState('visitors', s1, visTickets, { retry: retry1 });
    out.cols.visitors.partial = hasTrunc(inp, LBL_VISIT);
    if (half1 === 'failed') failedLabels.push('الزوّار');
    if (half2 === 'failed') failedLabels.push('قائمة الانتظار');
    if (half2 === 'missing') failedLabels.push('قائمة الانتظار');
    // —— العمود ٢: دعوات تنتظر الموافقة
    var inv = inp.invites, invSt = inp.invitesState;
    var invHalf = (invSt === 'idle' || invSt === 'loading' || (!inv && invSt !== 'error')) ? 'loading' : (invSt === 'error' || !inv ? 'failed' : (inv.missing ? 'missing' : 'ready'));
    if (invHalf === 'ready') {
      var gen = inp.settings && inp.settings.invite_approval_from_generation != null ? inp.settings.invite_approval_from_generation : null;
      var items = [];
      (inv.rows || []).filter(function (r) { return stageOf(r) === 'awaiting_approval'; }).forEach(function (r) {
        var at = ms(r.at);
        var brain = gen != null ? 'دعوات الجيل ' + ar(gen) + ' وما بعده تحتاج موافقتك قبل أن يعمل رابطها' : 'تحتاج موافقتك قبل أن يعمل رابطها';
        items.push({ id: 'invite:' + r.id, kind: 'approval', tag: 'دعوة من عضو', age: isNaN(at) ? '' : agoText(at, now), title: str(r.name) || 'بلا اسم',
          sub: 'الداعي: ' + (str(r.invitedByLabel) || '—') + (r.generation != null ? ' · الجيل ' + ar(r.generation) : ''), brain: brain, reason: '', warn: '',
          extra: str(r.note) ? ['ملاحظة الداعي: ' + str(r.note)] : [], link: r.registered && r.email ? String(r.email).toLowerCase() : null, ts: at, ref: r,
          primary: { label: 'وافق على الدعوة', act: { do: 'approve_invite' } }, secondary: [{ label: 'ارفض', act: { do: 'sheet', sheet: 'reject_invite' } }] });
      });
      items.sort(byOld);
      setState('approval', 'ready', items);
      out.cols.approval.partial = inv.count != null && inv.count > (inv.rows || []).length;
    } else {
      setState('approval', invHalf, []);
      if (invHalf !== 'loading') failedLabels.push('الدعوات');
    }
    if (invHalf === 'failed') out.cols.approval.retry = [{ key: 'invites', label: 'الدعوات' }];
    // —— العمودان ٣ و٤ (الوارد)
    function inboxCol(col, kind, label, shortLabel, build) {
      var h = inboxHalf(inp, label);
      if (h === 'ready') {
        var items = [];
        rows.filter(function (r) { return r && r.apiKind === kind; }).forEach(function (r) {
          var x = cardTicket(r, col, now, inp.userEmails); if (!x) return; build(x.ticket, x.card, r); items.push(x.ticket);
        });
        items.sort(byOld);
        setState(col, 'ready', items);
        out.cols[col].partial = hasTrunc(inp, label);
      } else {
        setState(col, h, []);
        if (h === 'failed') { failedLabels.push(shortLabel); out.cols[col].retry = [{ key: 'inbox', label: shortLabel }]; }
      }
    }
    inboxCol('join', 'join', LBL_JOIN, 'طلبات تقديم الخدمة', function (t, card, r) {
      t.id = 'join:' + r.apiId;
      if (r.infoRequest) t.extra.push('طُلب من صاحب الطلب: ' + r.infoRequest + ' — بانتظار رده');
      t.primary = r.licenceMissing ? { label: card.primary.label, act: { do: 'sheet', sheet: 'join' } } : { label: card.primary.label, act: { do: 'decide', action: 'approve' } };
      t.secondary = [{ label: 'ارفض', act: { do: 'sheet', sheet: 'reject_join' } }, { label: 'اطلب استكمالًا', act: { do: 'sheet', sheet: 'info_join' } }];
    });
    inboxCol('founding', 'founding', LBL_FOUND, 'الخبراء المؤسسون', function (t, card, r) {
      t.id = 'founding:' + r.apiId;
      var exp = ''; (r.details || []).forEach(function (d) { if (d && d.k === 'الخبرة') exp = str(String(d.v)).replace(/\d/g, function (x) { return '٠١٢٣٤٥٦٧٨٩'.charAt(+x); }); });
      t.sub = exp ? 'الخبرة: ' + exp : '';       // نص الملاحظة القديم عامي («كلّمه على…») فلا يُعرض؛ والباقي في سطر العقل
      t.primary = { label: card.primary.label, act: { do: 'decide', action: 'approve' } };
      var wa = waDigits(r);
      t.secondary = clean([wa ? { label: 'واتساب', act: { do: 'link', url: 'https://wa.me/' + wa } } : null, { label: 'ليس مناسبًا', act: { do: 'sheet', sheet: 'reject_founding' } }]);
    });
    // —— «سجّلوا ولم يطلبوا الفتح بعد»
    var pend = inp.pending, pst = inp.pendingState;
    var pHalf = (pst === 'idle' || pst === 'loading' || (!pend && pst !== 'error')) ? 'loading' : (pst === 'error' || !pend ? 'failed' : (pend.missing ? 'missing' : 'ready'));
    out.later.state = pHalf;
    if (pHalf === 'ready') {
      var list = (pend.rows || []).filter(function (u) { return !u.requested; });
      out.later.rows = list.map(function (u) {
        var at = ms(u.at);
        return { id: u.id, name: str(u.name) || str(u.email) || 'بلا اسم', email: str(u.email), rejected: !!u.rejected, signedText: isNaN(at) ? '' : 'سجّل ' + agoText(at, now),
                 lastText: u.lastLoginAt ? 'آخر دخول ' + agoText(u.lastLoginAt, now) : (str(u.lastLogin) ? 'آخر دخول ' + u.lastLogin : 'لم يُسجَّل دخول بعد'),
                 aiText: 'الأسئلة المستعملة: ' + (u.aiUsed != null ? ar(u.aiUsed) : NA), ref: u };
      });
      out.later.shown = out.later.rows.length;
      out.later.total = pend.count != null ? pend.count : null;
    }
    // —— الترويسة (B1)
    var colsK = ['visitors', 'approval', 'join', 'founding'];
    var allLoaded = colsK.every(function (k) { return out.cols[k].state === 'ready'; });
    var total = 0, oldest = Infinity;
    colsK.forEach(function (k) { out.cols[k].items.forEach(function (t) { total++; if (!isNaN(t.ts) && t.ts < oldest) oldest = t.ts; }); });
    var parts = [];
    var cnt = function (k) { return out.cols[k].items.length; };
    var vis = out.cols.visitors.items.filter(function (t) { return t.kind === 'visitor'; }).length, wlN = out.cols.visitors.items.length - vis;
    if (vis > 0) parts.push(UF(vis, ['زائر واحد ينتظر الفتح', 'زائران ينتظران الفتح', 'زوّار ينتظرون الفتح', 'زائرًا ينتظر الفتح']));
    if (wlN > 0) parts.push(UF(wlN, ['واحد من قائمة الانتظار', 'اثنان من قائمة الانتظار', 'من قائمة الانتظار', 'من قائمة الانتظار']));
    if (cnt('approval') > 0) parts.push(UF(cnt('approval'), ['دعوة واحدة تنتظر موافقتك', 'دعوتان تنتظران موافقتك', 'دعوات تنتظر موافقتك', 'دعوة تنتظر موافقتك']));
    if (cnt('join') > 0) parts.push(UF(cnt('join'), ['طلب تقديم خدمة واحد', 'طلبا تقديم خدمة', 'طلبات تقديم خدمة', 'طلب تقديم خدمة']));
    if (cnt('founding') > 0) parts.push(UF(cnt('founding'), ['خبير مؤسس واحد', 'خبيران مؤسسان', 'خبراء مؤسسون', 'خبيرًا مؤسسًا']));
    var uniqF = failedLabels.filter(function (l, i) { return failedLabels.indexOf(l) === i; });
    out.head.failedLabels = uniqF;
    if (total > 0) {
      out.head.text = 'ينتظر قرارك ' + ar(total) + ': ' + parts.join('، ') + '.' + (isFinite(oldest) ? ' أقدمها ' + agoText(oldest, now) + '.' : '');
    } else if (allLoaded) out.head.text = 'لا أحد ينتظر قرارك الآن.';
    else if (!uniqF.length) out.head.text = '…جارٍ الجلب';
    if (uniqF.length) out.head.text += (out.head.text ? ' ' : '') + 'تعذّر جلب: ' + uniqF.join('، ') + ' — العدد ناقص.';
    // —— B1-g: دعوات متوقفة أو تنتهي قريبًا ⇒ رابط إلى «الدعوات»
    if (invHalf === 'ready') {
      var pl = pipeline(inv, invSt, now, '');
      var bits = [];
      if (pl.stalled > 0) bits.push(UF(pl.stalled, ['دعوة واحدة متوقفة', 'دعوتان متوقفتان', 'دعوات متوقفة', 'دعوة متوقفة']));
      if (pl.expiring > 0) bits.push(UF(pl.expiring, ['دعوة واحدة تنتهي مهلتها قريبًا', 'دعوتان تنتهي مهلتهما قريبًا', 'دعوات تنتهي مهلتها قريبًا', 'دعوة تنتهي مهلتها قريبًا']));
      if (bits.length) out.head.invitesLine = { text: bits.join(' و') + ' — انظر «الدعوات»', href: '#s/people/pipeline' };
    }
    return out;
  }

  // ---------------------------------------------------------------- الحسابات
  function adminGuard(user, metrics, raw, truncated) {
    if (!user || user.role !== 'admin') return { locked: false, note: '' };
    var n = null;
    if (metrics && typeof metrics.admins === 'number') n = metrics.admins;
    else if (!truncated && Array.isArray(raw)) n = raw.filter(function (u) { return u && u.role === 'admin'; }).length;
    var LINE = 'هذا آخر حساب إدارة، فلا يمكن تغيير دوره';
    if (n == null) return { locked: true, note: LINE + ' (تعذّر التأكد من عدد حسابات الإدارة)' };
    return n <= 1 ? { locked: true, note: LINE } : { locked: false, note: '' };
  }
  function userChips(u, pendingEmails, packages) {
    var c = [];
    if (u.role === 'admin') c.push({ key: 'admin', label: 'إدارة' });
    else if (u.role === 'staff') c.push({ key: 'staff', label: 'فريق العمل' });
    else if (u.role === 'investor') c.push({ key: 'investor', label: 'مستثمر' });
    else c.push({ key: 'member', label: 'عضو' });
    if (u.trainer_status === 'approved') c.push({ key: 'trainer', label: 'مدرّب' });
    else if (u.trainer_status === 'pending') c.push({ key: 'trainer_pending', label: 'طلب مدرّب' });
    if (hasEmail(pendingEmails, u.email)) c.push({ key: 'visitor', label: 'زائر' });
    if (u.is_test) c.push({ key: 'test', label: 'تجريبي' });
    if (u.is_active === false) c.push({ key: 'off', label: 'موقوف' });
    if (SEG[u.segment]) c.push({ key: 'seg', label: SEG[u.segment] });
    (Array.isArray(u.tags) ? u.tags : []).forEach(function (t) { if (str(t)) c.push({ key: 'tag', label: str(t), gold: true }); });
    return c;
  }
  function users(raw, o) {
    o = o || {};
    var out = { state: 'ready', rows: [], chips: [], filterOptions: { roles: [], segs: [] }, activeFilters: [], searchLine: null, empty: null, shown: 0, total: null, truncated: false, more: 0, head: '' };
    var st = o.usersState || (raw ? 'ready' : 'loading');
    if (st === 'idle' || st === 'loading') { out.state = 'loading'; return out; }
    if (st === 'error' || !Array.isArray(raw)) { out.state = 'failed'; return out; }
    var metrics = o.metrics || null;
    var pendingEmails = [];
    if (o.pending && Array.isArray(o.pending.rows)) pendingEmails = o.pending.rows.map(function (p) { return String(p.email || '').toLowerCase(); }).filter(Boolean);
    var total = metrics && typeof metrics.total === 'number' ? metrics.total : null;
    var truncated = total != null ? total > raw.length : raw.length >= 500;
    out.truncated = truncated; out.total = total;
    var cnt = function (key, fn) {
      if (metrics && typeof metrics[key] === 'number') return metrics[key];
      return truncated ? null : raw.filter(fn).length;
    };
    out.chips = [
      { key: 'all', label: 'الكل', n: total != null ? total : (truncated ? null : raw.length) },
      { key: 'member', label: 'أعضاء', n: cnt('members', function (u) { return u.role === 'member'; }) },
      { key: 'trainer', label: 'مدرّبون', n: cnt('trainers_approved', function (u) { return u.trainer_status === 'approved'; }) },
      { key: 'staff', label: 'فريق العمل', n: cnt('staff', function (u) { return u.role === 'staff'; }) },
      { key: 'visitor', label: 'زوّار', n: o.pending && o.pending.count != null ? o.pending.count : (o.pending ? (o.pending.rows || []).length : null) }
    ];
    out.filterOptions.roles = [
      { key: 'admin', label: 'الإدارة', n: cnt('admins', function (u) { return u.role === 'admin'; }) },
      { key: 'investor', label: 'مستثمرون', n: cnt('investors', function (u) { return u.role === 'investor'; }) },
      { key: 'trainer_pending', label: 'طلبات مدرّب', n: truncated ? null : raw.filter(function (u) { return u.trainer_status === 'pending'; }).length },
      { key: 'test', label: 'حسابات تجريبية', n: truncated ? null : raw.filter(function (u) { return u.is_test; }).length }
    ];
    var segCount = {};
    raw.forEach(function (u) { if (SEG[u.segment]) segCount[u.segment] = (segCount[u.segment] || 0) + 1; });
    Object.keys(segCount).forEach(function (k) { out.filterOptions.segs.push({ key: 's:' + k, label: SEG[k], n: segCount[k] }); });
    var tagCount = {};
    raw.forEach(function (u) { (Array.isArray(u.tags) ? u.tags : []).forEach(function (t) { if (str(t)) tagCount[str(t)] = (tagCount[str(t)] || 0) + 1; }); });
    Object.keys(tagCount).forEach(function (k) { out.filterOptions.segs.push({ key: 't:' + k, label: k, n: tagCount[k] }); });
    var f = o.filter || {}, chip = o.chip || 'all', q = String(o.q || '').trim().toLowerCase();
    if (f.role) { var ro = out.filterOptions.roles.filter(function (r) { return r.key === f.role; })[0]; if (ro) out.activeFilters.push({ key: 'role', label: ro.label }); }
    if (f.seg) { var sg = out.filterOptions.segs.filter(function (r) { return r.key === f.seg; })[0]; out.activeFilters.push({ key: 'seg', label: sg ? sg.label : String(f.seg).slice(2) }); }
    if (o.sort === 'login') out.activeFilters.push({ key: 'sort', label: 'آخر دخول' });
    var all = raw.slice();
    var seen = {}; raw.forEach(function (u) { seen[u.id] = 1; });
    (Array.isArray(o.searchExtra) ? o.searchExtra : []).forEach(function (u) { if (u && !seen[u.id]) { seen[u.id] = 1; all.push(Object.assign({}, u, { fromSearch: true })); } });
    var rows = all.filter(function (u) {
      if (chip === 'member' && u.role !== 'member') return false;
      if (chip === 'trainer' && u.trainer_status !== 'approved') return false;
      if (chip === 'staff' && u.role !== 'staff') return false;
      if (chip === 'visitor' && !hasEmail(pendingEmails, u.email)) return false;
      if (f.role === 'admin' && u.role !== 'admin') return false;
      if (f.role === 'investor' && u.role !== 'investor') return false;
      if (f.role === 'trainer_pending' && u.trainer_status !== 'pending') return false;
      if (f.role === 'test' && !u.is_test) return false;
      if (f.seg) {
        if (f.seg.indexOf('s:') === 0 && u.segment !== f.seg.slice(2)) return false;
        if (f.seg.indexOf('t:') === 0 && (!Array.isArray(u.tags) || u.tags.indexOf(f.seg.slice(2)) < 0)) return false;
      }
      if (q && (String(u.full_name || '').toLowerCase().indexOf(q) < 0 && String(u.email || '').toLowerCase().indexOf(q) < 0 && String(u.phone || '').toLowerCase().indexOf(q) < 0)) return false;
      return true;
    });
    var key = o.sort === 'login' ? 'last_login_at' : 'created_at';
    rows.sort(function (a, b) { var x = ms(a[key]), y = ms(b[key]); return (isNaN(y) ? 0 : y) - (isNaN(x) ? 0 : x); });
    var now = o.now || 0, limit = o.limit || 50;
    out.shown = Math.min(rows.length, limit);
    out.more = Math.max(0, Math.min(50, rows.length - limit));
    out.rows = rows.slice(0, limit).map(function (u) {
      var chips = userChips(u, pendingEmails, o.packages);
      var more = chips.length > 4 ? chips.length - 4 : 0;
      chips = chips.slice(0, 4);
      if (more) chips.push({ key: 'more', label: '+' + ar(more) });
      var name = str(u.full_name) || str(u.email) || '—';
      var last = ms(u.last_login_at);
      return { id: u.id, email: str(u.email), name: name, initial: name.charAt(0).toUpperCase(), chips: chips, role: u.role, trainer: u.trainer_status,
               planText: planLabel(u.plan_id, o.packages), joinedText: dateText(u.created_at) || NA, lastText: isNaN(last) ? 'غير متاح' : agoText(last, now),
               active: u.is_active !== false, isTest: !!u.is_test, segment: u.segment || '', tags: Array.isArray(u.tags) ? u.tags : [], fromSearch: !!u.fromSearch, ref: u };
    });
    if (o.searching) out.searchLine = '…نبحث في كل الحسابات';
    else if (o.searchFailed) out.searchLine = 'تعذّر البحث في كل الحسابات الآن — النتائج من المعروض فقط';
    if (!rows.length) {
      if (q && !o.searching) out.empty = { text: 'لا حساب يطابق «' + shorten(String(o.q).trim(), 40) + '»', hint: 'اكتب البريد كاملًا واضغط إدخال لفتح صفحة الشخص' };
      else if (!q && !f.role && !f.seg && chip === 'all' && !all.length) out.state = 'empty';
      else if (!q) out.empty = { text: 'لا حسابات في هذا التصنيف', hint: '' };
    }
    var m = metrics || {};
    var slot = function (v) { return typeof v === 'number' ? ar(v) : NA; };
    out.head = 'الحسابات ' + (total != null ? ar(total) : (truncated ? NA : ar(raw.length))) + ' · انضمّ هذا الأسبوع ' + slot(m.signups_7d) + ' · اليوم ' + slot(m.signups_today)
      + ' · مدرّبون معتمدون ' + slot(m.trainers_approved) + ' · باقات مدفوعة ' + slot(m.paid_plan);
    return out;
  }

  // ---------------------------------------------------------------- الرسائل
  function mailUrl(email, subject) {
    return 'mailto:' + encodeURIComponent(email).replace(/%40/g, '@') + '?subject=' + encodeURIComponent(subject);
  }
  function msgBrain(at, now) {
    var t = 'وصلت ' + agoText(at, now);
    return !isNaN(ms(at)) && now - ms(at) > DAY ? t + ' · مرّ عليها أكثر من يوم' : t;
  }
  function msgState(rows, st) {
    if (st === 'idle' || st === 'loading' || (!rows && st !== 'error')) return 'loading';
    return (st === 'error' || !Array.isArray(rows)) ? 'failed' : 'ready';
  }
  function messages(site, siteState, chat, chatState, follow, followState, now) {
    var out = { cols: {}, replied: [], head: { text: '' } };
    var defs = { site: ['رسائل الموقع', 'الموقع'], chat: ['رسائل من المحادثة', 'المحادثة'], follow: ['طلبات تواصل', 'تواصل'] };
    Object.keys(defs).forEach(function (k) { out.cols[k] = { state: 'loading', count: null, items: [], label: defs[k][0], short: defs[k][1] }; });
    var s1 = msgState(site, siteState), s2 = msgState(chat, chatState), s3 = msgState(follow, followState);
    out.cols.site.state = s1; out.cols.chat.state = s2; out.cols.follow.state = s3;
    if (s1 === 'ready') {
      out.cols.site.items = site.filter(function (m) { return m && m.status !== 'replied'; }).map(function (m) {
        var at = ms(m.at);
        return { id: 'site:' + m.id, src: 'site', rid: m.id, strip: 'من نموذج التواصل', old: !isNaN(at) && now - at > DAY, ageText: isNaN(at) ? '' : agoText(at, now), ts: at,
                 title: str(m.name) || 'زائر بلا اسم', sub: str(m.topic), body: str(m.body), email: str(m.email), phone: str(m.phone), brain: isNaN(at) ? '' : msgBrain(at, now),
                 primary: { label: 'ردّ', act: { do: 'sheet', sheet: 'reply' } }, secondary: [{ label: 'احذف', act: { do: 'sheet', sheet: 'delete' } }], ref: m };
      }).sort(byOld);
      out.replied = site.filter(function (m) { return m && m.status === 'replied'; }).sort(function (a, b) { return (ms(b.at) || 0) - (ms(a.at) || 0); }).slice(0, 20).map(function (m) {
        return { id: 'site:' + m.id, rid: m.id, name: str(m.name) || 'زائر بلا اسم', topic: str(m.topic), dateText: dateText(m.at) || '', ref: m };
      });
    }
    if (s2 === 'ready') {
      out.cols.chat.items = chat.filter(Boolean).map(function (m) {
        var at = ms(m.created_at != null ? m.created_at : m.at), email = str(m.from_email) || str(m.email) || str(m.user_email), phone = str(m.contact_phone) || str(m.phone);
        var subject = str(m.subject) || str(m.topic), id = m.id != null ? m.id : m._id;
        var it = { id: 'chat:' + id, src: 'chat', rid: id, strip: 'من المحادثة على المنصة', old: !isNaN(at) && now - at > DAY, ageText: isNaN(at) ? '' : agoText(at, now), ts: at,
                   title: str(m.from_name) || str(m.name) || str(m.user_name) || 'زائر بلا اسم', sub: subject, body: str(m.body) || str(m.text) || str(m.summary),
                   email: email, phone: phone, brain: isNaN(at) ? '' : msgBrain(at, now), secondary: [], ref: m };
        var resolve = { label: 'علّمها منتهية', act: { do: 'resolve' } };
        if (email) { it.primary = { label: 'ردّ بالبريد', act: { do: 'sent', url: mailUrl(email, 'ردًّا على رسالتك — البروفيسور') } }; it.secondary = [resolve]; }
        else if (waNumber(phone)) { it.primary = { label: 'واتساب', act: { do: 'sent', url: 'https://wa.me/' + waNumber(phone) } }; it.secondary = [resolve]; }
        else if (digitsOf(phone).length >= 6) { it.primary = { label: 'انسخ الرقم', act: { do: 'copy', text: phone } }; it.secondary = [resolve]; }
        else it.primary = resolve;
        return it;
      }).sort(byOld);
    }
    if (s3 === 'ready') {
      out.cols.follow.items = follow.filter(Boolean).map(function (m) {
        var at = ms(m.created_at != null ? m.created_at : m.at), email = str(m.from_email) || str(m.email), phone = str(m.phone), id = m.id != null ? m.id : m._id;
        var want = str(m.want) || str(m.need) || str(m.topic) || str(m.summary);
        var it = { id: 'follow:' + id, src: 'follow', rid: id, strip: 'طلب تواصل من المحادثة', old: false, ageText: isNaN(at) ? '' : agoText(at, now), ts: at,
                   title: str(m.full_name) || str(m.name) || 'بلا اسم', sub: want ? 'يريد: ' + want : '', body: str(m.experience) ? 'الخبرة: ' + str(m.experience) : '',
                   email: email, phone: phone, brain: 'طلب التواصل دون إنشاء حساب', secondary: [], ref: m };
        var done = { label: 'تمت المتابعة', act: { do: 'resolve' } };
        if (waNumber(phone)) { it.primary = { label: 'واتساب', act: { do: 'sent', url: 'https://wa.me/' + waNumber(phone) } }; it.secondary = [done]; }
        else if (email) { it.primary = { label: 'ردّ بالبريد', act: { do: 'sent', url: mailUrl(email, 'ردًّا على طلبك — البروفيسور') } }; it.secondary = [done]; }
        else if (digitsOf(phone).length >= 6) { it.primary = { label: 'انسخ الرقم', act: { do: 'copy', text: phone } }; it.secondary = [done]; }
        else it.primary = done;
        return it;
      }).sort(byOld);
    }
    ['site', 'chat', 'follow'].forEach(function (k) { var c = out.cols[k]; c.count = c.state === 'ready' ? c.items.length : null; });
    var all = [].concat(out.cols.site.items, out.cols.chat.items, out.cols.follow.items);
    var loaded = ['site', 'chat', 'follow'].every(function (k) { return out.cols[k].state === 'ready'; });
    var failed = [];
    if (s1 === 'failed') failed.push('رسائل الموقع');
    if (s2 === 'failed') failed.push('رسائل المحادثة');
    if (s3 === 'failed') failed.push('طلبات التواصل');
    out.head.failedLabels = failed;
    var oldest = Infinity; all.forEach(function (t) { if (!isNaN(t.ts) && t.ts < oldest) oldest = t.ts; });
    if (all.length) out.head.text = 'تنتظر الرد ' + ar(all.length) + ': ' + ar(out.cols.site.items.length) + ' من الموقع · ' + ar(out.cols.chat.items.length) + ' من المحادثة · '
      + (out.cols.follow.items.length ? UF(out.cols.follow.items.length, ['طلب تواصل واحد', 'طلبا تواصل', 'طلبات تواصل', 'طلب تواصل']) : '٠ طلبات تواصل') + '.' + (isFinite(oldest) ? ' أقدمها ' + agoText(oldest, now) + '.' : '');
    else if (loaded) out.head.text = 'لا رسائل تنتظر الرد.';
    else if (!failed.length) out.head.text = '…جارٍ الجلب';
    if (failed.length) out.head.text += (out.head.text ? ' ' : '') + 'تعذّر جلب: ' + failed.join('، ') + ' — العدد ناقص.';
    return out;
  }

  L.v2p = { requests: requests, pipeline: pipeline, users: users, messages: messages, stageLabel: stageLabel, waText: waText, waUrl: waUrl, waNumber: waNumber, adminGuard: adminGuard,
            planLabel: planLabel, inviterKey: inviterKey, SEG: SEG, ROLE: ROLE, STAGE: STAGE, mailUrl: mailUrl };
})(typeof window !== 'undefined' ? window : (typeof globalThis !== 'undefined' ? globalThis : this));
// ===== /v2s:people =====

// ===== v2s:content =====
// «المحتوى» (الجولة الأخيرة): منطق نقي لخط النشر والمقالات والموضوعات. ⛔ بلا DOM وبلا EP وبلا Date.now() (المنادي يمرّر `now`).
// المصدر الفاشل = `null` (يُكتب «غير متاح بعد» ولا يتحوّل صفرًا) · المصدر الجاري تحميله = `undefined`.
(function (root) {
  'use strict';
  var L = root.V2L;
  if (!L) return;
  var Uu = L.util, ar = Uu.ar, UU = Uu.U, DAY = 86400e3, HOUR = 3600e3, WEEK = 7 * DAY;
  var NA = L.NA;

  function str(v) { return typeof v === 'string' ? v.trim() : ''; }
  function ms(v) {
    if (typeof v === 'number') return isFinite(v) && v > 0 ? v : NaN;
    var t = Date.parse(v || '');
    return isNaN(t) ? NaN : t;
  }
  function shortText(s, n) { s = String(s == null ? '' : s).replace(/\s+/g, ' ').trim(); return s.length > n ? s.slice(0, n) + '…' : s; }
  function isArr(a) { return Array.isArray(a); }
  function sameDay(a, b) { var x = new Date(a), y = new Date(b); return x.getFullYear() === y.getFullYear() && x.getMonth() === y.getMonth() && x.getDate() === y.getDate(); }
  function within(at, now, span) { var t = ms(at); return !isNaN(t) && now - t >= 0 && now - t < span; }
  // «منذ …» بنحو سليم («منذ يومين» لا «منذ يومان»): دقائق ⇒ د · ساعات (حتى ٤٨) ⇒ س · بعدها أيام.
  function ageCore(d) {
    d = Math.max(0, d || 0);
    var m = Math.floor(d / 60e3);
    if (m < 60) return ar(Math.max(m, 1)) + ' د';
    var h = Math.floor(m / 60);
    if (h < 48) return ar(h) + ' س';
    return UU(Math.floor(h / 24), ['يوم', 'يومين', 'أيام', 'يومًا']);
  }
  function age(at, now) { var t = ms(at); return isNaN(t) ? '' : ageCore(now - t); }
  function since(at, now) { var t = ms(at); return isNaN(t) ? '' : (now - t < 60e3 ? 'الآن' : 'منذ ' + ageCore(now - t)); }

  var TAB_OF = { pipeline: 'pipeline', articles: 'articles', blog: 'articles', auto: 'articles',
                 pending: 'topics', ideas: 'topics', incoming: 'topics', working: 'topics', board: 'topics', rejected: 'topics', archived: 'topics',
                 news: 'news', comments: 'comments', tutorials: 'tutorials', site: 'site' };
  function v2ContentTabFor(topicsTab) { return TAB_OF[topicsTab] || 'pipeline'; }

  // ------------------------------------------------------------ حالة صفحات محركات البحث
  function v2ContentPrerender(p, now) {
    var state = p && p.state;
    var when = p && p.at ? L.util.agoText(ms(p.at), now) : '';
    if (state === 'ok') return { text: 'صفحات محركات البحث حُدّثت' + (when ? ' ' + when : ''), tone: 'ok', live: true };
    if (state === 'running') return { text: 'صفحات محركات البحث تتحدّث الآن', tone: 'neutral', live: true };
    if (state === 'error') return { text: 'تعذّر آخر تحديث لصفحات محركات البحث' + (when ? ' (' + when + ')' : '') + ' — يُعاد مع أول نشر', tone: 'bad', live: false };
    return { text: 'تحديث صفحات محركات البحث: ' + NA, tone: 'na', live: false };
  }
  function v2ContentPublishLead(title, prerender) {
    var live = !!(prerender && (prerender.state === 'ok' || prerender.state === 'running'));
    return 'سيظهر «' + title + '» على الموقع الآن' + (live ? '، وتتحدّث صفحته لمحركات البحث خلال دقائق.' : '.');
  }

  // ------------------------------------------------------------ حقائق مقال الموقع
  // articleMeta: صف `contentOverview.articles` (أي حقل ناقص ⇒ null) · publishedTitles: عناوين المنشور على الموقع (تطابق بالتساوي بعد القصّ فقط).
  function v2ContentFacts(articleMeta, publishedTitles) {
    var a = articleMeta || {};
    var title = str(a.title);
    var dup = a.status !== 'published' && !!title && (publishedTitles || []).some(function (t) { return str(t) === title; });
    var words = typeof a.words === 'number' ? a.words : null;
    var hasImage = typeof a.has_image === 'boolean' ? a.has_image : null;
    var hasMeta = typeof a.has_meta === 'boolean' ? a.has_meta : null;
    var reviewer = str(a.reviewed_by) || null;
    var known = a.words !== undefined || a.has_image !== undefined || a.has_meta !== undefined;
    var parts = [];
    if (words !== null) parts.push(ar(words) + ' كلمة');
    if (hasImage !== null) parts.push(hasImage ? 'بصورة' : 'بلا صورة');
    if (hasMeta !== null) parts.push(hasMeta ? 'بوصف لمحركات البحث' : 'بلا وصف لمحركات البحث');
    if (known) parts.push(reviewer ? 'راجعه ' + reviewer : 'لم يراجعه أحد');
    var factsLine = parts.join(' · ');
    return { words: words, hasImage: hasImage, hasMeta: hasMeta, reviewer: reviewer, dupTitle: dup, factsLine: factsLine,
             line: dup ? 'عنوانه مطابق لمقال منشور على الموقع' : factsLine };
  }

  // ------------------------------------------------------------ تعليق: ما قاله الفحص الآلي (حقيقة، لا حكم)
  function v2ContentCommentVerdict(mod) {
    mod = mod || {};
    if (mod.abusive === true) return { key: 'abusive', text: 'الفحص الآلي على المنصة: قد يحوي إساءة', suggest: 'reject' };
    if (mod.on_topic === false) return { key: 'offtopic', text: 'الفحص الآلي على المنصة: خارج الموضوع', suggest: 'reject' };
    return { key: 'open', text: 'لم يحسمه الفحص الآلي', suggest: 'read' };
  }

  // ------------------------------------------------------------ الزرّ الأساسي الواحد لكل عنصر
  function v2ContentSuggest(it) {
    it = it || {};
    switch (it.kind) {
      case 'memberTopic': return { label: 'اعتمد وبلّغ', act: 'approveMemberTopic' };
      case 'testimonial': return { label: 'افتح واقرأ', act: 'openTestimonial' };
      case 'comment': return v2ContentCommentVerdict(it.moderation).suggest === 'reject'
        ? { label: 'ارفض', act: 'rejectComment' } : { label: 'افتح واقرأ', act: 'openComment' };
      case 'creative': return { label: 'افتح وراجع', act: 'openCreative' };
      case 'siteDraft': return { label: it.dup ? 'افتح وقارن' : 'اقرأ وانشر', act: 'openArticle' };
      case 'platformDraft': return { label: it.dup ? 'افتح وقارن' : 'اقرأ وانشر', act: 'openPlatformArticle' };
      case 'working': return it.ready ? { label: 'انشر على اللوحة', act: 'publishTopic' } : { label: 'افتح', act: 'openTopic' };
      case 'idea': return it.hasAnswer ? { label: 'اعتمد للنقاش', act: 'approveIdea' } : { label: 'افتح وراجع', act: 'openTopic' };
      case 'newsDraft': return it.complete ? { label: 'انشر الخبر', act: 'publishNews' } : { label: 'أكمل الخبر', act: 'openNews' };
      case 'testimonialCount': return { label: 'أعد المحاولة', act: 'retry' };
      default: return null;
    }
  }

  // اسم الكاتب كما يظهر: ما فيه «الذكي/الذكاء» (مقالات قديمة خُزّنت بهذا النص) يظهر «فريق البروفيسور».
  function v2ContentByText(by) {
    var t = String(by == null ? '' : by).trim();
    if (!t) return 'الإدارة';
    return /الذكي|الذكاء|الآلي|آلي/.test(t) ? 'فريق البروفيسور' : t;
  }

  // ------------------------------------------------------------ موضوعات: نفس قاعدة topicTabOf القديمة بالحرف
  function topicTabOf(t) {
    var st = t.status || 'draft', src = t.source || 'human';
    if (st === 'pending_review') return 'pending';
    if (st === 'rejected') return 'rejected';
    if (st === 'published' || st === 'open') return 'board';
    if (st === 'merged') return 'working';
    if (st === 'archived') return 'archived';          // المؤرشف له شريحة «مؤرشفة» (تظهر حين يكون عددها فوق صفر)، لا يُعرض تحت «أفكار» للاعتماد
    if (src === 'expert') return 'incoming';
    return 'ideas';
  }
  var CHIP_LABELS = [['pending', 'من الأعضاء'], ['ideas', 'أفكار'], ['incoming', 'من الخبراء'], ['working', 'يُكتب'], ['board', 'على اللوحة'], ['rejected', 'مرفوضة'], ['archived', 'مؤرشفة']];
  // PTOPICS_PENDING === null ⇒ عدّ «من الأعضاء» null (لا يؤخذ من PTOPICS أبدًا) · PTOPICS === null ⇒ باقي العدّات null.
  function v2ContentTopicChips(topics, pending, active, generating) {
    var c = { pending: null, ideas: null, incoming: null, working: null, board: null, rejected: null, archived: null };
    if (isArr(pending)) c.pending = pending.length;
    if (isArr(topics)) {
      ['ideas', 'incoming', 'working', 'board', 'rejected', 'archived'].forEach(function (k) { c[k] = 0; });
      var gen = generating || {}, seen = {};
      topics.forEach(function (t) {
        var k = topicTabOf(t);
        if (k === 'pending') return;   // المعلّق يُعدّ من طابوره الخاص فقط
        if (k === 'working') seen[t.id] = 1;
        c[k]++;
      });
      Object.keys(gen).forEach(function (id) { if (!seen[id]) c.working++; });
    }
    return CHIP_LABELS.map(function (p) {
      return { key: p[0], label: p[1], count: c[p[0]], active: p[0] === active, hidden: (p[0] === 'rejected' || p[0] === 'archived') && !(c[p[0]] > 0) && p[0] !== active };
    }).filter(function (x) { return !x.hidden; });
  }
  // الحارات بترتيب المنصة المقفول، والأصفار تبقى. gap = أول حارة عددها صفر · low = أقل حارة (أول الأقل في الترتيب).
  function v2ContentSegments(analysis) {
    var list = analysis && isArr(analysis.by_segment) ? analysis.by_segment : null;
    if (!list) return null;
    var lanes = list.map(function (s) { return { id: s.segment || s.id || '', label: s.label || '', count: Number(s.count) || 0 }; });
    var gap = null, low = null;
    lanes.forEach(function (l) { if (gap === null && l.count === 0) gap = l.label; if (low === null || l.count < low.count) low = l; });
    return { lanes: lanes, gap: gap, low: low };
  }

  // ------------------------------------------------------------ لوحة خط النشر
  var SRC_LABEL = { news: 'من خبر', expert: 'من خبير', idea: 'فكرة', human: 'فكرة' };
  var IDEA_SRC = { news: 'خبر', expert: 'خبير', idea: 'فكرة', human: 'من الفريق' };
  var CREATIVE_KIND = { song: 'أغنية', video: 'فيديو', poem: 'قصيدة' };
  var PART_CAT = { feature: 'شرح المنصة', news: 'تحليل خبر', law: 'قانوني', guide: 'دليل', platform: 'المنصة', other: 'أخرى' };
  var COL_SOURCES = { wait: ['memberTopics', 'testimonials', 'comments', 'creative'], draft: ['siteArticles', 'platformArticles', 'topics'],
                      idea: ['topics', 'news'], done: ['siteArticles', 'news', 'approvedComments', 'approvedTestimonials'] };
  var COLS4 = ['wait', 'draft', 'idea', 'done'];
  var MAX_SHOWN = 6;
  var NO_DATE = 8.64e15;

  function srcState(v) { return v === undefined ? 'loading' : (v === null ? 'failed' : 'ok'); }
  function byAsc(a, b) { return a.sortAt - b.sortAt; }
  function byDesc(a, b) { return b.sortAt - a.sortAt; }
  function mk(o, now, tone) {
    o.at = isNaN(ms(o.at)) ? null : ms(o.at);
    o.sortAt = o.at === null ? NO_DATE : o.at;
    o.timer = o.at === null ? { mode: 'since', at: null } : { mode: 'since', at: o.at };
    o.text = o.at === null ? '' : since(o.at, now);
    o.tone = tone || 'ink';
    return o;
  }
  function opinionMod(o) { return (o && (o.ai_moderation || o.moderation)) || null; }

  function v2ContentBoard(src, now) {
    src = src || {};
    now = now || 0;
    var cols = { wait: [], draft: [], idea: [], done: [] };
    var counts = {}, partial = {}, failed = {}, loading = {};
    var siteTitlesPub = isArr(src.siteArticles) ? src.siteArticles.filter(function (a) { return a.status === 'published'; }).map(function (a) { return str(a.title); }) : [];
    var gen = src.generating || {};

    // —— ينتظرك
    var wait = [];
    if (isArr(src.memberTopics)) src.memberTopics.forEach(function (t) {
      var seg = t.segment_label ? 'الفئة: ' + t.segment_label + (t.segment_auto ? ' (اختيار آلي)' : '') : 'بلا فئة';
      wait.push(mk({ id: 'm:' + t.id, kind: 'memberTopic', col: 'wait', order: 0, ref: t, title: t.title || 'موضوع بلا عنوان', at: t.at,
        strip: 'موضوع من عضو', who: { text: t.category || t.specialty || 'بلا تخصص' },
        brain: 'القرار يصل إلى صاحب الموضوع · ' + seg, go: { tab: 'topics', st: 'pending' } }, now, 'wait'));
    });
    if (isArr(src.testimonials)) src.testimonials.forEach(function (r) {
      var b = [];
      b.push((r.course_title || 'دورة') + (r.rating != null && r.rating !== '' ? ' · التقييم ' + ar(r.rating) + ' من ٥' : ''));
      if (r.consent_public === true) b.push('وافق كاتبه على النشر باسمه');
      wait.push(mk({ id: 't:' + r.id, kind: 'testimonial', col: 'wait', order: 1, ref: r, title: shortText(r.text, 80) || 'رأي بلا نص', at: r.created_at,
        strip: 'رأي متعلّم', who: { text: r.name || 'متعلّم', email: r.user_email || '' }, brain: b.join(' · '), go: null }, now, 'wait'));
    });
    if (isArr(src.comments)) src.comments.forEach(function (o) {
      var v = v2ContentCommentVerdict(o.moderation);
      var it = mk({ id: 'c:' + o.id, kind: 'comment', col: 'wait', order: 2, ref: o, moderation: o.moderation, title: shortText(o.body, 80) || 'تعليق بلا نص', at: o.at,
        strip: 'تعليق', who: { text: 'على: ' + (o.topic_title || 'موضوع'), email: o.author_email || '' }, brain: v.text, verdict: v.key, go: { tab: 'comments' } }, now, 'wait');
      wait.push(it);
    });
    if (isArr(src.creative)) src.creative.forEach(function (w) {
      var kindText = CREATIVE_KIND[w.kind] || 'عمل آخر';
      wait.push(mk({ id: 'w:' + w.id, kind: 'creative', col: 'wait', order: 3, ref: w, title: w.title || 'عمل بلا عنوان', at: w.created_at,
        strip: 'عمل إبداعي', who: { text: w.creator_name || w.creator_email || 'صاحب العمل', email: w.creator_email || '' },
        brain: kindText + ' · ' + (w.media_url ? 'معه رابط' : 'بلا رابط'), go: null }, now, 'wait'));
    });
    var fallbackN = src.testimonials === null && typeof src.queueTestimonials === 'number' && src.queueTestimonials > 0 ? src.queueTestimonials : 0;
    wait.sort(function (a, b) { return a.order - b.order || a.sortAt - b.sortAt; });
    wait.forEach(function (it) { it.late = it.at !== null && now - it.at > 48 * HOUR; if (it.late) it.tone = 'late'; });
    if (fallbackN) wait.push({ id: 'tc', kind: 'testimonialCount', col: 'wait', order: 9, n: fallbackN, title: ar(fallbackN) + ' رأي متعلّم ينتظر المراجعة', at: null, sortAt: NO_DATE,
      text: '', tone: 'wait', strip: 'رأي متعلّم', who: null, brain: 'تعذّر جلب القائمة، وهذا العدد من المنصة مباشرة', go: null });
    cols.wait = wait;

    // —— مسودات
    var draft = [];
    var platTitles = {};
    Object.keys(gen).forEach(function (id) {
      var t = isArr(src.topics) ? src.topics.filter(function (x) { return x.id === id; })[0] : null;
      var item = mk({ id: 'g:' + id, kind: 'generating', col: 'draft', order: 0, ref: t || { id: id }, title: (t && t.title) || 'موضوع', at: gen[id],
        strip: 'يُكتب المقال الآن', who: { text: (t && (t.category || t.specialty)) || 'بلا تخصص' },
        brain: 'يكتب النظام مقالًا جديدًا من هذا الموضوع، ويظهر مسودة عند انتهائه', status: 'جارٍ الكتابة…', go: { tab: 'topics', st: 'working' } }, now, 'amber');
      item.text = 'الآن'; draft.push(item);
    });
    if (isArr(src.siteArticles)) src.siteArticles.forEach(function (a) {
      if (a.status !== 'draft') return;
      var f = v2ContentFacts(a, siteTitlesPub);
      draft.push(mk({ id: 's:' + a.id, kind: 'siteDraft', col: 'draft', order: 1, ref: a, dup: f.dupTitle, facts: f, title: a.title || 'مقال بلا عنوان', at: a.created_at,
        strip: 'مقال للموقع', who: { text: v2ContentByText(a.by) }, brain: f.line, go: { tab: 'articles', st: 'articles', filter: 'draft' } }, now, 'amber'));
    });
    if (isArr(src.platformArticles)) src.platformArticles.forEach(function (a) {
      if (a.status === 'published') return;
      var dup = !!str(a.title) && siteTitlesPub.indexOf(str(a.title)) > -1;
      draft.push(mk({ id: 'p:' + a.id, kind: 'platformDraft', col: 'draft', order: 1, ref: a, dup: dup, title: a.title || 'مقال بلا عنوان', at: a.created_at,
        strip: 'مقال على المنصة', who: { text: PART_CAT[a.category] || PART_CAT.other },
        brain: dup ? 'عنوانه مطابق لمقال منشور على الموقع' : 'تظهر في صفحة المقالات على المنصة بعد النشر', go: { tab: 'articles', st: 'auto' } }, now, 'amber'));
    });
    if (isArr(src.topics)) src.topics.forEach(function (t) {
      if (t.status !== 'merged' || gen[t.id]) return;
      var ready = !!(str(t.merged_article) || str(t.ai_answer));
      draft.push(mk({ id: 'k:' + t.id, kind: 'working', col: 'draft', order: 1, ref: t, ready: ready, title: t.title || 'موضوع بلا عنوان', at: t.at,
        strip: 'يُكتب من النقاش', who: { text: t.category || t.specialty || 'بلا تخصص' },
        brain: ready ? 'النص جاهز للمراجعة' : 'لم يُكتب النص بعد', go: { tab: 'topics', st: 'working' } }, now, 'amber'));
    });
    draft.sort(function (a, b) { return a.order - b.order || a.sortAt - b.sortAt; });
    cols.draft = draft;

    // —— أفكار
    var idea = [];
    if (isArr(src.topics)) src.topics.forEach(function (t) {
      if ((t.status || 'draft') !== 'draft') return;
      var seg = t.segment_label ? 'الفئة: ' + t.segment_label : 'بلا فئة';
      var src2 = t.source || 'human';
      idea.push(mk({ id: 'i:' + t.id, kind: 'idea', col: 'idea', ref: t, hasAnswer: !!str(t.ai_answer), title: t.title || 'موضوع بلا عنوان', at: t.at,
        strip: src2 === 'news' ? 'من خبر' : src2 === 'expert' ? 'من خبير' : 'فكرة', who: { text: t.category || t.specialty || 'بلا تخصص' },
        brain: [IDEA_SRC[src2] || 'فكرة', t.category || t.specialty || 'بلا تخصص', seg].join(' · ') + (str(t.ai_answer) ? ' · معه إجابة مقترحة' : ''),
        go: { tab: 'topics', st: topicTabOf(t) } }, now, 'ink'));
    });
    if (isArr(src.news)) src.news.forEach(function (n) {
      if (n.status !== 'draft') return;
      var cnt = isArr(n.sources) ? n.sources.length : 0;
      idea.push(mk({ id: 'n:' + n.id, kind: 'newsDraft', col: 'idea', ref: n, complete: cnt >= 1 && !!str(n.summary), title: n.title || 'خبر بلا عنوان', at: n.at,
        strip: 'خبر', who: { text: [n.country, n.specialty].filter(Boolean).join(' · ') || 'بلا دولة' },
        brain: (cnt ? ar(cnt) + ' ' + (cnt === 1 ? 'مصدر' : cnt === 2 ? 'مصدران' : cnt <= 10 ? 'مصادر' : 'مصدرًا') : 'بلا مصدر') + ' · ' + (str(n.summary) ? 'بملخص' : 'بلا ملخص'),
        go: { tab: 'news' } }, now, 'ink'));
    });
    idea.sort(byDesc);
    cols.idea = idea;

    // —— نُشر هذا الأسبوع: بتاريخ القرار الحقيقي فقط
    var done = [];
    if (isArr(src.siteArticles)) src.siteArticles.forEach(function (a) {
      if (a.status !== 'published' || !within(a.published_at, now, WEEK)) return;
      done.push(mk({ id: 'ds:' + a.id, kind: 'doneArticle', col: 'done', ref: a, title: a.title || 'مقال', at: a.published_at, strip: 'مقال نُشر', who: { text: v2ContentByText(a.by) }, brain: '',
        go: { tab: 'articles', st: 'articles', filter: 'published' } }, now, 'green'));
    });
    if (isArr(src.news)) src.news.forEach(function (n) {
      if (n.status !== 'published' || !within(n.published_at, now, WEEK)) return;
      done.push(mk({ id: 'dn:' + n.id, kind: 'doneNews', col: 'done', ref: n, title: n.title || 'خبر', at: n.published_at, strip: 'خبر نُشر', who: { text: [n.country, n.specialty].filter(Boolean).join(' · ') }, brain: '', go: { tab: 'news' } }, now, 'green'));
    });
    if (isArr(src.approvedComments)) src.approvedComments.forEach(function (o) {
      var m = opinionMod(o);
      if (!m || m.decided_by !== 'human' || !within(m.decided_at || o.decided_at, now, WEEK)) return;
      done.push(mk({ id: 'dc:' + o.id, kind: 'doneComment', col: 'done', ref: o, title: shortText(o.body, 80) || 'تعليق', at: m.decided_at || o.decided_at, strip: 'تعليق اعتُمد',
        who: { text: 'على: ' + (o.topic_title || 'موضوع') }, brain: '', go: { tab: 'comments' } }, now, 'green'));
    });
    if (isArr(src.approvedTestimonials)) src.approvedTestimonials.forEach(function (r) {
      if (!within(r.decided_at, now, WEEK)) return;
      done.push(mk({ id: 'dt:' + r.id, kind: 'doneTestimonial', col: 'done', ref: r, title: shortText(r.text, 80) || 'رأي', at: r.decided_at, strip: 'رأي اعتُمد',
        who: { text: r.course_title || 'دورة' }, brain: '', go: null }, now, 'green'));
    });
    done.sort(byDesc);
    cols.done = done;

    // —— العدّادات وحالة المصادر لكل عمود
    COLS4.forEach(function (c) {
      var states = COL_SOURCES[c].map(function (k) { return srcState(src[k]); });
      var anyFailed = states.indexOf('failed') > -1, anyLoading = states.indexOf('loading') > -1;
      var allFailed = states.every(function (s) { return s === 'failed'; }) && !(c === 'wait' && fallbackN);
      var allLoading = states.every(function (s) { return s === 'loading'; });
      loading[c] = anyLoading;
      failed[c] = allFailed;
      partial[c] = anyFailed && !allFailed;
      counts[c] = allFailed || allLoading ? null : cols[c].reduce(function (n, it) { return n + (it.kind === 'testimonialCount' ? it.n : 1); }, 0);
    });

    // —— كل المصادر + سطر العقل
    var allKeys = ['memberTopics', 'testimonials', 'comments', 'creative', 'siteArticles', 'platformArticles', 'topics', 'news', 'approvedComments', 'approvedTestimonials'];
    var anyLoadingAll = allKeys.some(function (k) { return src[k] === undefined; });
    var anyFailedAll = allKeys.some(function (k) { return src[k] === null; });
    var today = null, week = null;
    if (isArr(src.siteArticles)) {
      today = 0; week = 0;
      src.siteArticles.forEach(function (a) {
        if (a.status !== 'published') return;
        var t = ms(a.published_at);
        if (isNaN(t)) return;
        if (sameDay(t, now)) today++;
        if (within(t, now, WEEK)) week++;
      });
    }
    var members = isArr(src.memberTopics) ? src.memberTopics : null;
    var oldestMember = members && members.length ? members.reduce(function (m, t) { var a = ms(t.at); return !isNaN(a) && (m === null || a < m) ? a : m; }, null) : null;
    var otherWait = wait.filter(function (it) { return it.kind !== 'memberTopic' && it.kind !== 'testimonialCount'; }).length + (fallbackN ? fallbackN : 0);
    var siteDrafts = isArr(src.siteArticles) ? src.siteArticles.filter(function (a) { return a.status === 'draft'; }).length : null;
    var rule = 0, line;
    if (anyLoadingAll) { line = '…جارٍ جمع المحتوى'; }
    else if (members && members.length > 0) {
      rule = 1;
      line = 'ابدأ بموضوعات الأعضاء: ' + ar(members.length) + ' ينتظر صاحبه قرارك' + (oldestMember !== null ? '، أقدمها منذ ' + age(oldestMember, now) : '') + '.';
    } else if (otherWait > 0) { rule = 2; line = ar(otherWait) + ' ينتظر قرارك من الأعضاء والمتعلّمين.'; }
    else if (siteDrafts !== null && siteDrafts > 0) { rule = 3; line = ar(siteDrafts) + ' مسودة للموقع جاهزة للقراءة.'; }
    else if (!anyFailedAll) { rule = 4; line = 'لا شيء ينتظر قرارك الآن.'; }
    else { line = 'بعض المصادر لم تصل، فلا أستطيع القول إن لا شيء ينتظرك.'; }

    // —— الصفّ الظاهر وباقي القائمة
    var more = {};
    COLS4.forEach(function (c) {
      if (cols[c].length > MAX_SHOWN) {
        var hidden = cols[c].slice(MAX_SHOWN), first = hidden[0];
        more[c] = { n: hidden.length, go: first.go || null };
      }
    });
    return { order: COLS4.slice(), cols: cols, counts: counts, partial: partial, failed: failed, loading: loading, more: more, max: MAX_SHOWN,
             top: { rule: rule, line: line, today: today, week: week, loading: anyLoadingAll, failedAny: anyFailedAll } };
  }

  // ------------------------------------------------------------ «الموقع»: تعديل نصوص الموقع من اللوحة (SPEC-B §B6)
  // نقي: الكتل والنسخ تصل من الخادم، والتحقق هنا مرآة لتحقق الخادم (الخادم هو الحَكَم).
  var SITE_TAG = { title: 'عنوان التبويب', meta: 'وصف البحث', h1: 'عنوان رئيسي', h2: 'عنوان فرعي', h3: 'عنوان فرعي', p: 'فقرة', li: 'بند في قائمة', a: 'رابط', button: 'زر' };
  var SITE_KINDS = [{ key: 'all', label: 'الكل', tags: null }, { key: 'heads', label: 'العناوين', tags: ['title', 'meta', 'h1', 'h2', 'h3'] },
                    { key: 'paras', label: 'الفقرات والبنود', tags: ['p', 'li'] }, { key: 'links', label: 'الروابط والأزرار', tags: ['a', 'button'] }];
  var SITE_HEADS = ['title', 'h1', 'h2', 'h3'];
  var SITE_NEW_MAX = 600;
  var SITE_NOTE = { apply: 'قبل تعديل نُشر', before_restore: 'قبل إرجاع سابق' };
  var SITE_BANNED = new RegExp('ي[\\u064b-\\u0652]*ق[\\u064b-\\u0652]*و[\\u064b-\\u0652]*\\u0651[\\u064b-\\u0652]*م');
  var SITE_LEAD = new RegExp('^[\\s«"]*' + 'ال' + 'ذكاء');
  function v2SiteKinds() { return SITE_KINDS.map(function (k) { return { key: k.key, label: k.label }; }); }
  // صفوف الكتل للعرض: التصنيف بالنوع، والجزء من فقرة مختلطة يُعلَّم، وغير القابل للتعديل يحمل سببه.
  function v2SiteBlockRows(blocks, kind) {
    if (!isArr(blocks)) return [];
    var def = SITE_KINDS.filter(function (k) { return k.key === kind; })[0] || SITE_KINDS[0];
    var out = [];
    blocks.forEach(function (b, i) {
      if (!b || typeof b.text !== 'string' || !b.text) return;
      var tag = str(b.tag);
      if (def.tags && def.tags.indexOf(tag) < 0) return;
      var m = /#(\d+)$/.exec(str(b.path));
      out.push({ index: i, path: str(b.path), tag: tag, tagLabel: SITE_TAG[tag] || 'نص', text: b.text, editable: b.editable === true,
                 note: str(b.note) || (b.editable === true ? '' : 'لا يمكن تعديله'), part: m ? Number(m[1]) : 0 });
    });
    return out;
  }
  // يتحقق من النص الجديد قبل الإرسال. ok=false ⇒ error جملة عربية جاهزة. text = النص بعد التنظيف.
  function v2SiteCheckNew(oldText, text, tag) {
    var t = String(text == null ? '' : text).replace(/\s+/g, ' ').trim();
    if (!t) return { ok: false, text: t, error: 'اكتب النص الجديد' };
    if (t.length > SITE_NEW_MAX) return { ok: false, text: t, error: 'النص أطول من ' + ar(SITE_NEW_MAX) + ' حرف' };
    if (t.indexOf('<') > -1 || t.indexOf('>') > -1) return { ok: false, text: t, error: 'لا تكتب رمزَي الأقواس الزاوية' };
    if (t === String(oldText == null ? '' : oldText).replace(/\s+/g, ' ').trim()) return { ok: false, text: t, error: 'النص الجديد مطابق للقديم' };
    if (SITE_BANNED.test(t)) return { ok: false, text: t, error: 'في النص عبارة غير مقبولة. عدّلها ثم أعد المحاولة' };
    if (SITE_HEADS.indexOf(tag) > -1 && SITE_LEAD.test(t)) return { ok: false, text: t, error: 'لا يبدأ العنوان بكلمة «ال' + 'ذكاء». عدّل الصياغة' };
    return { ok: true, text: t, error: '' };
  }
  // قائمة النسخ السابقة: الأحدث أولًا كما يرسلها الخادم.
  function v2SiteBackupRows(backups, now) {
    if (!isArr(backups)) return [];
    return backups.map(function (b) {
      var kb = typeof b.size === 'number' && isFinite(b.size) ? Math.max(1, Math.round(b.size / 1024)) : null;
      return { id: b.id, when: since(b.created_at, now) || NA, who: str(b.created_by), kind: SITE_NOTE[str(b.note)] || 'نسخة سابقة', size: kb === null ? NA : ar(kb) + ' ك.ب' };
    });
  }

  L.v2SiteKinds = v2SiteKinds; L.v2SiteBlockRows = v2SiteBlockRows; L.v2SiteCheckNew = v2SiteCheckNew; L.v2SiteBackupRows = v2SiteBackupRows;
  L.v2ContentTabFor = v2ContentTabFor; L.v2ContentBoard = v2ContentBoard; L.v2ContentFacts = v2ContentFacts; L.v2ContentSuggest = v2ContentSuggest;
  L.v2ContentCommentVerdict = v2ContentCommentVerdict; L.v2ContentPrerender = v2ContentPrerender; L.v2ContentPublishLead = v2ContentPublishLead;
  L.v2ContentTopicChips = v2ContentTopicChips; L.v2ContentSegments = v2ContentSegments; L.v2ContentTopicTabOf = topicTabOf; L.v2ContentByText = v2ContentByText;
})(typeof window !== 'undefined' ? window : (typeof globalThis !== 'undefined' ? globalThis : this));
// ===== /v2s:content =====

// ===== v2s:marketing =====
// «التسويق» (الجولة النهائية): الجزء النقي. ⛔ لا DOM ولا شبكة ولا ساعة خفية — التاريخ يُمرَّر صراحةً (todayISO).
// يربط نفسه بـV2L.mk (المتصفح وnode معًا: module.exports هو نفس كائن V2L).
(function (root) {
  'use strict';
  var L = root.V2L;
  if (!L || !L.util) return;
  var U = L.util, Un = U.U;
  var NA = 'غير متاح بعد';
  var DAYMS = 86400e3;

  var STATUS_LABEL = { active: 'نشطة', paused: 'موقوفة', completed: 'انتهت', draft: 'مسودة' };
  var PLATFORM_LABEL = { facebook: 'فيسبوك', instagram: 'إنستجرام', facebook_instagram: 'فيسبوك وإنستجرام', google_ads: 'جوجل', linkedin: 'لينكدإن',
                         youtube: 'يوتيوب', tiktok: 'تيك توك' };
  var UTM_SRC = { facebook: 'facebook', instagram: 'instagram', facebook_instagram: 'meta', google_ads: 'google', linkedin: 'linkedin', youtube: 'youtube', tiktok: 'tiktok' };
  var UNIT = { EGP: 'جنيه', SAR: 'ريال', USD: 'دولار' };
  var PLATFORM_OPTS = [['facebook_instagram', 'فيسبوك وإنستجرام'], ['facebook', 'فيسبوك'], ['instagram', 'إنستجرام'], ['google_ads', 'جوجل'], ['linkedin', 'لينكدإن'],
                       ['youtube', 'يوتيوب'], ['tiktok', 'تيك توك'], ['other', 'أخرى']];
  var CURRENCY_OPTS = [['EGP', 'جنيه مصري'], ['SAR', 'ريال سعودي'], ['USD', 'دولار'], ['other', 'أخرى']];
  var SOCIAL = [{ key: 'facebook', label: 'فيسبوك', mark: 'ف', mate: 'إنستجرام' }, { key: 'instagram', label: 'إنستجرام', mark: 'إ', mate: 'فيسبوك' },
                { key: 'linkedin', label: 'لينكدإن', mark: 'ل' }, { key: 'youtube', label: 'يوتيوب', mark: 'ي' }, { key: 'tiktok', label: 'تيك توك', mark: 'ت' }];

  // كل النصوص الثابتة الظاهرة في مكان واحد (اختبار النص يقرأه). ⛔ بلا حروف لاتينية.
  var STR = {
    na: NA,
    tabCampaigns: 'الحملات', tabSocial: 'السوشيال ميديا', tabPlan: 'خطة النشر',
    segActive: 'النشطة الآن', segAll: 'كل الحملات', segLabel: 'عرض الحملات',
    newCampaign: 'حملة جديدة',
    newBlocked: 'تعذّر جلب الحملات — أعد المحاولة أولًا حتى لا تتكرر حملة',
    topNote: 'أرقام الحملات منذ بدايتها كما سُجّلت، ودخل المنصة بالشهر. لا يصل إلى هنا شيء من حسابات الإعلانات قبل ربط «مدار».',
    retry: 'أعد المحاولة',
    failedCampaigns: 'تعذّر جلب: الحملات — ما يظهر ناقص، وليس معناه أنه لا شيء',
    noCampaigns: 'لا حملات مسجّلة', noSpend: 'لم يُسجَّل صرف بعد', noRevenue: 'لم يُسجَّل دخل بعد',
    sincePeriod: 'منذ بداية كل حملة', campaignsFailedNote: 'تعذّر جلب الحملات',
    n1: 'صُرف على الإعلانات', n2: 'دخل جاء من الإعلانات', n3: 'دخل جاء بلا إعلانات', n4: 'كلفة العميل الواحد',
    n3NotReady: 'هذا الشهر: المنصة لا تسجّل بعد من أين جاء كل دافع.',
    n3Channels: 'من البحث والسوشيال والدعوات والدخول المباشر',
    n3NoIncome: 'لا دخل بعد هذا الشهر',
    n4Note: 'من الحملات التي سُجّل لها من دفع، منذ بدايتها',
    n4None: 'لم يُسجَّل بعد من دفع عن طريق حملة',
    othersPrefix: 'وبعملة أخرى: ',
    legacyText: 'سُجّلت من الشاشة القديمة، وكانت تلك الشاشة تحفظ كل حملة بعملة «دولار» مهما كُتب.',
    legacyBtn: 'راجع العملة', legacyTitle: 'عملة الحملات القديمة',
    legacyLead: 'هذه الحملات محفوظة بعملة «دولار». لا يُحوَّل أي رقم؛ تتغيّر العملة فقط.',
    legacyAllEgp: 'اجعلها كلها بالجنيه', legacyKeep: 'هي بالدولار فعلًا', legacyLater: 'سأراجعها واحدة واحدة',
    brainLabel: 'العقل يقترح', later: 'لاحقًا',
    brainEmpty: 'لا حملات مسجّلة. سجّل أول حملة لأرى ما صُرف وما جاء.',
    brainYoung: 'الحملات الجديدة ما زالت في أيامها الأولى، فلا اقتراح عليها الآن.',
    brainNone: 'لا اقتراح الآن. الحملات النشطة تسير كما سُجّلت.',
    sugEnded: 'أقترح تسجيلها منتهية.', sugStop: 'أقترح إيقافها.', sugNoResults: 'أقترح نقل نتائجها من حساب الإعلانات.', sugBudget: 'راجع الميزانية أو أوقفها.',
    btnEnded: 'سجّلها منتهية', btnStop: 'أوقفها', btnResults: 'سجّل النتائج', btnEdit: 'عدّل الحملة', btnOpen: 'افتح الحملة',
    confirmStopTitle: 'إيقاف حملة', confirmEndTitle: 'تسجيل حملة منتهية', confirmRunTitle: 'تشغيل حملة',
    confirmNoAd: 'هذا لا يوقف الإعلان نفسه. أوقفه من حساب الإعلانات حتى يُربط «مدار».',
    confirmNoAdRun: 'هذا لا يشغّل الإعلان نفسه. شغّله من حساب الإعلانات حتى يُربط «مدار».',
    confirm: 'أكّد', cancel: 'إلغاء', back: 'رجوع', ok: 'تمام', close: 'إغلاق',
    saveFailed: 'تعذّر الحفظ — أعد المحاولة',
    seenTitle: 'العقل يرى من', needsTitle: 'العقل يحتاج:',
    howLink: 'كيف تُربط هذه المصادر؟', howTitle: 'كيف تُربط هذه المصادر',
    srcCampaigns: 'الحملات المسجّلة هنا', srcIncome: 'دخل المنصة', srcAds: 'أرصدة إعلانات أصحاب الأعمال', srcAttr: 'من أين جاء كل شخص',
    srcMeta: 'إعلانات ميتا', srcGoogle: 'إعلانات جوجل', srcSocial: 'صفحات السوشيال', srcVisits: 'زيارات الموقع',
    cardTitle: 'الحملات: من الإعلان حتى الدفع', cardHint: 'اضغط أي حملة لتفاصيلها وأزرارها',
    colCampaign: 'الحملة', colPlatform: 'المنصة', colStatus: 'الحالة', colSpent: 'صُرف', colVisits: 'زيارات', colLeads: 'سجّلوا', colPaid: 'دفعوا', colRev: 'الدخل', colRatio: 'رجع',
    colVia: 'عبر الرابط', colAsTyped: 'كما سُجّل', colViaSub: 'من المنصة · هذا الشهر',
    typedTitle: 'الرقم كما كتبته في الحملة',
    noResultsChip: 'لم تُسجَّل نتائج',
    organicName: 'بلا إعلان', organicSub: 'من المنصة · هذا الشهر · البحث والسوشيال والدعوات والدخول المباشر',
    organicNa: 'غير متاح بعد — المنصة لا تسجّل بعد من أين جاء كل دافع', organicRatio: 'بلا صرف',
    emptyActive: 'لا حملات نشطة الآن.', showAll: 'اعرض كل الحملات', emptyAll: 'لا حملات مسجّلة بعد',
    loadingCampaigns: '…جارٍ جلب الحملات', unavailableCampaigns: 'الحملات: غير متاح بعد', unavailableHint: 'تعذّر الوصول إلى هذه البيانات الآن، فلا تعتبر الشاشة فارغة.',
    adsNone: 'لا أعمال لها رصيد إعلانات بعد', adsFailed: 'أرصدة إعلانات الأعمال: غير متاح بعد', adsLinkAds: 'إعلانات الأعمال', adsLinkClients: 'عملاء الإعلانات',
    ownerSelf: 'البروفيسور نفسه', ownerForSelf: 'للبروفيسور', ownerCurrent: 'الحالي',
    ownerAdsHint: 'قائمة الأعمال غير متاحة الآن، فلا يمكن تغيير صاحب الحملة', ownerOwnersHint: 'صاحب الحملة غير متاح الآن، فلا يمكن تغييره',
    kindCourse: 'دورة', kindBook: 'كتاب',
    madarTitle: 'بعد ربط مدار', madarBtn: 'ماذا سيظهر هنا؟',
    madarItems: ['نتائج إعلانات ميتا وجوجل لكل حملة يومًا بيوم', 'أرقام صفحات فيسبوك وإنستجرام ولينكدإن ويوتيوب وتيك توك', 'خطة النشر الأسبوعية وما ينتظر موافقتك',
                 'كشف «صُرف كم وجاء بماذا» لكل صاحب حملة'],
    madarCard: 'مدار هو نظام التسويق الذي سيجلب إلى هنا نتائج الإعلانات وأرقام الصفحات وخطة النشر، فلا تكتبها بيدك. الربط في جولة قادمة.',
    soon: 'قريبًا',
    detailLines: { platform: 'المنصة', status: 'الحالة', period: 'المدة', owner: 'لمن الحملة', audience: 'الجمهور' },
    detailNumbers: 'كما سُجّل منذ بداية الحملة',
    nBudget: 'الميزانية',
    linkTitle: 'الرابط الذي تضعه في الإعلان', copyLink: 'انسخ الرابط', copiedLink: 'نُسخ الرابط',
    linkSoon: 'سيُحتسب من جاء عبر هذا الرابط حين تبدأ المنصة تسجيل مصدر كل زائر.',
    viaLabel: 'من المنصة', viaNobody: 'لم يأتِ عبره أحد هذا الشهر',
    actEdit: 'عدّل الحملة', actStop: 'أوقفها', actRun: 'شغّلها', actCopyStatement: 'انسخ الكشف', actDelete: 'احذف',
    statementCopied: 'نُسخ الكشف — أرسله لصاحب الحملة',
    createTitle: 'حملة جديدة', editTitle: 'تعديل: ', createBtn: 'أنشئ الحملة', saveBtn: 'احفظ', saving: 'جارٍ الحفظ…',
    fName: 'اسم الحملة', fOwner: 'لمن الحملة', fPlatform: 'المنصة', fPlatformOther: 'اسم المنصة', fCurrency: 'العملة', fCurrencyOther: 'رمز العملة (ثلاثة أحرف)',
    fStatus: 'الحالة', fStart: 'تاريخ البدء', fEnd: 'تاريخ النهاية', fBudget: 'الميزانية', fSpent: 'صُرف', fClicks: 'الزيارات (النقرات على الإعلان)',
    fLeads: 'سجّلوا', fPaid: 'دفعوا', fRevenue: 'الدخل الذي جاء منها', fAudience: 'الجمهور',
    dateNote: 'لا يمكن مسح التاريخ بعد حفظه، غيّره فقط',
    errName: 'اكتب اسم الحملة', errNameLong: 'اسم الحملة أطول من ٢٥٥ حرفًا', errNeg: 'الأرقام لا تكون سالبة', errNum: 'اكتب رقمًا صحيحًا في خانة: ', errInt: 'اكتب عددًا صحيحًا في خانة: ',
    errEnd: 'تاريخ النهاية قبل البدء', errPlatform: 'اكتب اسم المنصة', errCur: 'اكتب رمز العملة من ثلاثة أحرف', errAudience: 'الجمهور أطول من ٥٠٠ حرف',
    ownerNoSave: 'حُفظت الحملة، وتعذّر حفظ صاحبها — أعد المحاولة من «عدّل الحملة»',
    deleteTitle: 'حذف حملة', deleteWarn: 'لا يمكن التراجع.', deleteBtn: 'احذف نهائيًا',
    socialCaption: 'صُرف على حملاتها منذ بداية كل حملة', socialNone: 'لا حملات مسجّلة على هذه المنصة', socialFollowers: 'المتابعون والوصول: غير متاح بعد',
    socialFailedNote: 'تعذّر جلب الحملات',
    planPublished: 'نُشر على الموقع هذا الأسبوع', planPublishedHint: 'آخر ٧ أيام', planOpenSite: 'افتح على الموقع', planNone: 'لم يُنشر مقال على الموقع في آخر ٧ أيام.',
    planDrafts: 'مسودات مقالات لم تُنشر بعد: ', planOpenContent: 'افتح المحتوى', planFailed: 'مقالات الموقع: غير متاح بعد', planLoading: '…جارٍ جلب المقالات',
    planSocial: 'خطة النشر على السوشيال', planSocialText: 'تُجهَّز خطة الأسبوع لكل منصة، وتنتظر موافقتك قبل النشر، بعد ربط «مدار».'
  };

  // ------------------------------------------------------------------ أدوات
  function numv(v) { var n = Number(v); return isFinite(n) ? n : 0; }
  function isoDay(s) { s = String(s == null ? '' : s).slice(0, 10); return /^\d{4}-\d{2}-\d{2}$/.test(s) ? s : ''; }
  function dayMs(s) { s = isoDay(s); return s ? Date.parse(s + 'T00:00:00Z') : NaN; }
  function unitOf(cur) { return UNIT[String(cur || '').toUpperCase()] || 'وحدة'; }
  function sumField(rows, f) { return U.sumByCurrency(rows.map(function (r) { return { currency: r.currency, amount: r[f] }; })); }
  function pickPrimary(sums) {
    var pos = sums.filter(function (s) { return s.amount > 0; });
    if (!pos.length) return null;
    var p = pos.filter(function (s) { return s.currency === 'EGP'; })[0] || pos.slice().sort(function (a, b) { return b.amount - a.amount; })[0];
    return { primary: p, others: pos.filter(function (s) { return s !== p; }) };
  }
  function othersText(others) { return others.length ? STR.othersPrefix + others.map(function (o) { return U.moneyText(o.amount, o.currency); }).join(' · ') : ''; }
  function ratio(rev, spent) { rev = numv(rev); spent = numv(spent); if (spent <= 0) return null; return Math.round(rev / spent * 10) / 10; }
  function ratioNum(r) { return U.fmt(r); }
  function ratioText(r, cur) { return r == null ? '' : 'كل ' + unitOf(cur) + ' رجع ' + ratioNum(r); }
  function money(n, cur) { return U.moneyText(n, cur); }
  function moneyListText(totals) { return (totals || []).map(function (t) { return U.moneyText(t.amount, t.currency); }).filter(Boolean).join(' · '); }
  function activeRows(rows) { return rows.filter(function (r) { return r.status === 'active'; }); }

  // ------------------------------------------------------------------ مدخل الحملات
  function norm(raw) {
    return (Array.isArray(raw) ? raw : []).filter(Boolean).map(function (c) {
      var status = STATUS_LABEL[c.status] ? c.status : 'paused';
      var platform = String(c.platform == null ? '' : c.platform).trim();
      var clicks = numv(c.clicks), leads = numv(c.leads), conv = numv(c.conversions), rev = numv(c.revenue_attributed), spent = numv(c.spent);
      var allZero = !(clicks || leads || conv || rev);
      return { id: Number(c.id), name: String(c.name == null ? '' : c.name).trim() || 'حملة بلا اسم', platform: platform,
               platformLabel: PLATFORM_LABEL[platform] || platform, status: status, statusLabel: STATUS_LABEL[status],
               currency: String(c.currency || '').trim().toUpperCase() || 'EGP', start: isoDay(c.start_date), end: isoDay(c.end_date),
               budget: numv(c.budget), spent: spent, clicks: clicks, leads: leads, conversions: conv, revenue: rev,
               audience: String(c.target_audience == null ? '' : c.target_audience).trim(), allZero: allZero, noResults: spent > 0 && allZero };
    });
  }

  // ------------------------------------------------------------------ مدخل المنصة (من أين جاء كل شخص)
  function attReady(att) { return !!(att && typeof att === 'object' && att.ok !== false && Array.isArray(att.channels)); }
  function organicChannels(att) { return att.channels.filter(function (c) { return c && c.paid === false; }); }
  function organicTotals(att) {
    var items = [];
    organicChannels(att).forEach(function (c) { (c.totals || []).forEach(function (t) { items.push({ currency: t.currency, amount: t.amount }); }); });
    return U.sumByCurrency(items);
  }
  function organicCount(att, f) { return organicChannels(att).reduce(function (s, c) { return s + numv(c[f]); }, 0); }
  function viaFor(att, id) {
    if (!attReady(att) || !Array.isArray(att.campaigns)) return null;
    var hit = att.campaigns.filter(function (c) { return c && c.campaign === 'c' + id; })[0];
    return hit ? { signups: numv(hit.signups), paid: numv(hit.paid_people), totals: Array.isArray(hit.totals) ? hit.totals : [] } : null;
  }

  // ------------------------------------------------------------------ الأرقام الأربعة
  function numObj(key, label) { return { key: key, label: label, value: '', na: false, primary: null, others: [], othersText: '', note: '' }; }
  function setMoney(n, sums, emptyText) {
    var pk = pickPrimary(sums);
    if (!pk) { n.value = emptyText; n.na = true; return null; }
    n.primary = pk.primary; n.others = pk.others; n.othersText = othersText(pk.others); n.value = U.moneyText(pk.primary.amount, pk.primary.currency);
    return pk;
  }
  // rows: صفوف norm() أو null لو مصدر الحملات فشل. extra: {income: [{currency,amount}]|null, attribution: ردّ المنصة|null}
  function board(rows, filter, extra) {
    extra = extra || {};
    var n1 = numObj('spent', STR.n1), n2 = numObj('revenue', STR.n2), n3 = numObj('organic', STR.n3), n4 = numObj('cost', STR.n4);
    var all = filter === 'all';
    if (!Array.isArray(rows)) {
      [n1, n2, n4].forEach(function (n) { n.value = NA; n.na = true; n.note = STR.campaignsFailedNote; });
    } else {
      var sel = all ? rows : activeRows(rows), cnt = sel.length;
      var countText = all ? 'من ' + Un(cnt, ['حملة واحدة مسجّلة', 'حملتين مسجّلتين', 'حملات مسجّلة', 'حملة مسجّلة']) : Un(cnt, ['حملة واحدة نشطة', 'حملتان نشطتان', 'حملات نشطة', 'حملة نشطة']);
      var spentSums = sumField(sel, 'spent'), revSums = sumField(sel, 'revenue');
      // ١) صُرف
      if (!cnt) { n1.value = STR.noCampaigns; n1.na = true; n1.note = STR.sincePeriod; }
      else { setMoney(n1, spentSums, STR.noSpend); n1.note = countText + ' · ' + STR.sincePeriod; }
      // ٢) دخل جاء من الإعلانات
      if (!cnt) { n2.value = STR.noCampaigns; n2.na = true; n2.note = STR.sincePeriod; }
      else {
        var pk2 = setMoney(n2, revSums, STR.noRevenue);
        if (!pk2) n2.note = STR.sincePeriod;
        else {
          var sp = spentSums.filter(function (s) { return s.currency === pk2.primary.currency; })[0];
          if (sp && sp.amount > 0) n2.note = 'كل ' + unitOf(pk2.primary.currency) + ' رجع ' + ratioNum(Math.round(pk2.primary.amount / sp.amount * 10) / 10) + ' · ' + STR.sincePeriod;
          else n2.note = 'كما سُجّل في كل حملة منذ بدايتها';
        }
      }
      // ٤) كلفة العميل
      var payers = sel.filter(function (r) { return r.conversions > 0; });
      if (!payers.length) { n4.value = NA; n4.na = true; n4.note = STR.n4None; }
      else {
        var per = {};
        payers.forEach(function (r) { var p = per[r.currency] || (per[r.currency] = { spent: 0, conv: 0 }); p.spent += r.spent; p.conv += r.conversions; });
        var costs = Object.keys(per).map(function (c) { return { currency: c, amount: Math.round(per[c].spent / per[c].conv), weight: per[c].spent }; });
        var cpos = costs.filter(function (c) { return c.amount > 0; });
        var p4 = cpos.filter(function (c) { return c.currency === 'EGP'; })[0] || cpos.slice().sort(function (a, b) { return b.weight - a.weight; })[0];
        if (!p4) { n4.value = NA; n4.na = true; n4.note = STR.n4None; }
        else {
          n4.primary = { currency: p4.currency, amount: p4.amount }; n4.value = U.moneyText(p4.amount, p4.currency);
          n4.others = cpos.filter(function (c) { return c !== p4; }).map(function (c) { return { currency: c.currency, amount: c.amount }; });
          n4.othersText = othersText(n4.others); n4.note = STR.n4Note;
        }
      }
    }
    // ٣) دخل جاء بلا إعلانات (هذا الشهر — من المنصة)
    var att = extra.attribution;
    if (attReady(att)) {
      var pk3 = setMoney(n3, organicTotals(att), STR.n3NoIncome);
      if (!pk3) n3.na = false;
      var since = att.captured_since ? U.dateText(att.captured_since) : '';
      n3.note = 'هذا الشهر' + (since ? '، منذ بدء التسجيل في ' + since : '') + ': ' + STR.n3Channels;
    } else {
      n3.value = NA; n3.na = true; n3.note = STR.n3NotReady;
      var inc = Array.isArray(extra.income) ? moneyListText(extra.income) : '';
      if (inc) n3.note += ' دخل المنصة كله هذا الشهر: ' + inc + '، ولا نعرف بعد كم منه جاء من إعلان.';
    }
    return { numbers: [n1, n2, n3, n4] };
  }

  // ------------------------------------------------------------------ الحملات القديمة بعملة الدولار
  function legacyUsd(rows, legacyMaxId) {
    var max = Number(legacyMaxId) || 0;
    if (max <= 0 || !Array.isArray(rows)) return [];
    return rows.filter(function (r) { return r.currency === 'USD' && r.id <= max; });
  }

  // ------------------------------------------------------------------ نضج الحملة + اقتراح العقل
  function mature(row, todayISO) {
    var t = dayMs(todayISO), s = dayMs(row.start);
    var oldEnough = isNaN(s) || isNaN(t) || s <= t - 7 * DAYMS;
    var spentEnough = row.budget <= 0 || row.spent >= row.budget * 0.25;
    return oldEnough && spentEnough;
  }
  function isSkipped(skipped, key) {
    if (!skipped) return false;
    if (Array.isArray(skipped)) return skipped.indexOf(key) > -1;
    if (typeof skipped.has === 'function') return skipped.has(key);
    return !!skipped[key];
  }
  function bySpent(a, b) { return b.spent - a.spent || (a.name < b.name ? -1 : 1); }
  function brain(rows, todayISO, skipped) {
    rows = Array.isArray(rows) ? rows : [];
    if (!rows.length) return { state: 'empty', items: [{ kind: 'empty', id: 0, text: STR.brainEmpty, line: '', btn: STR.newCampaign, action: 'create', later: false }], text: STR.brainEmpty };
    var act = activeRows(rows).slice().sort(bySpent), all = [];
    function item(kind, r, text, line, btn, action, later) { all.push({ kind: kind, id: r.id, text: text, line: line, btn: btn, action: action, later: later !== false }); }
    act.forEach(function (r) {
      if (r.end && r.end < isoDay(todayISO)) item('ended', r, 'حملة «' + r.name + '» انتهى موعدها في ' + U.dateText(r.end) + ' وما زالت «نشطة» هنا.', STR.sugEnded, STR.btnEnded, 'complete');
    });
    act.forEach(function (r) {
      if (mature(r, todayISO) && r.spent > 0 && !r.allZero && r.revenue < r.spent) {
        var text = r.revenue > 0
          ? 'حملة «' + r.name + '» صُرف عليها ' + money(r.spent, r.currency) + ' وسُجّل لها دخل ' + money(r.revenue, r.currency) + ': ' + ratioText(ratio(r.revenue, r.spent), r.currency) + '.'
          : 'حملة «' + r.name + '» صُرف عليها ' + money(r.spent, r.currency) + ' ولم يُسجَّل لها دخل بعد.';
        item('losing', r, text, STR.sugStop, STR.btnStop, 'pause');
      }
    });
    act.forEach(function (r) {
      if (mature(r, todayISO) && r.spent > 0 && r.allZero) item('no_results', r, 'حملة «' + r.name + '» صُرف عليها ' + money(r.spent, r.currency) + ' ولم تُسجَّل لها أي نتيجة بعد.', STR.sugNoResults, STR.btnResults, 'edit');
    });
    act.forEach(function (r) {
      if (r.budget > 0 && r.spent > r.budget) item('over_budget', r, 'حملة «' + r.name + '» صُرف عليها ' + money(r.spent, r.currency) + ' وميزانيتها ' + money(r.budget, r.currency) + '.', STR.sugBudget, STR.btnEdit, 'edit');
    });
    if (!all.length) {
      var best = act.filter(function (r) { var x = ratio(r.revenue, r.spent); return r.spent > 0 && x != null && x >= 3; })
        .sort(function (a, b) { return ratio(b.revenue, b.spent) - ratio(a.revenue, a.spent); })[0];
      if (best) item('best', best, 'أفضل حملة الآن «' + best.name + '»: ' + ratioText(ratio(best.revenue, best.spent), best.currency) + '.', '', STR.btnOpen, 'detail', false);
    }
    var items = all.filter(function (it) { return !isSkipped(skipped, it.kind + '_' + it.id); });
    if (items.length) return { state: 'items', items: items, text: '' };
    if (all.length) return { state: 'none', items: [], text: STR.brainNone };           // كلها مؤجّلة
    var young = act.some(function (r) { return !mature(r, todayISO) && r.spent > 0 && ((!r.allZero && r.revenue < r.spent) || r.allZero); });
    if (young) return { state: 'young', items: [], text: STR.brainYoung };
    return { state: 'none', items: [], text: STR.brainNone };
  }
  function mainButton(state) {
    if (state === 'items') return { main: 'brain', topHidden: false };
    if (state === 'empty') return { main: 'brain', topHidden: true };
    return { main: 'top', topHidden: false };
  }

  // ------------------------------------------------------------------ العقل يرى من / يحتاج
  var NEEDS = [
    { key: 'attribution', title: 'من أين جاء كل شخص يسجّل أو يدفع', why: 'لأعرف كم من الدخل جاء بلا إعلان', chip: 'يحتاج تعديلًا في المنصة',
      how: 'تحفظ المنصة عند أول زيارة من أين جاء الزائر (إعلان، بحث، سوشيال، دعوة)، وتربطه بحسابه وبكل دفعة. بعدها يظهر هنا الدخل بلا إعلان، ونتيجة كل حملة حتى الدفع.' },
    { key: 'ads_results', title: 'نتائج إعلانات ميتا وجوجل', why: 'لأرى نتيجة كل حملة دون كتابتها', chip: 'يأتي مع ربط «مدار»',
      how: 'يجلب «مدار» نتائج الحملات يومًا بيوم من حسابات الإعلانات. إلى أن يُربط، سجّل أرقام كل حملة من زر «عدّل الحملة».' },
    { key: 'social_pages', title: 'أرقام صفحات السوشيال', why: 'لأعرف أي منصة تجلب الناس', chip: 'يأتي مع ربط «مدار»',
      how: 'يجلب «مدار» المتابعين والوصول وأفضل منشور لكل منصة.' },
    { key: 'site_visits', title: 'زيارات الموقع', why: 'لأعرف كم زائرًا صار عميلًا', chip: 'يحتاج تعديلًا في الموقع',
      how: 'يُضاف عدّاد زيارات للموقع والمنصة يحترم اختيار الكوكيز، ويصل رقمه إلى هنا وإلى «التقارير».' }
  ];
  function sources(states) {
    states = states || {};
    function st(k) {
      var s = states[k];
      if (s === 'ready') return 'ready';
      if (s === 'error') return 'error';
      if (s === 'closed') return k === 'attribution' ? 'off' : 'error';
      return s === 'loading' ? 'loading' : 'off';
    }
    var seen = [
      { key: 'campaigns', label: STR.srcCampaigns, state: st('campaigns') },
      { key: 'income', label: STR.srcIncome, state: st('income') },
      { key: 'ads', label: STR.srcAds, state: st('ads') },
      { key: 'attribution', label: STR.srcAttr, state: st('attribution') },
      { key: 'meta', label: STR.srcMeta, state: 'off' }, { key: 'google', label: STR.srcGoogle, state: 'off' },
      { key: 'social', label: STR.srcSocial, state: 'off' }, { key: 'visits', label: STR.srcVisits, state: 'off' }
    ];
    var failed = seen.filter(function (s) { return s.state === 'error' && ['campaigns', 'income', 'ads', 'attribution'].indexOf(s.key) > -1; }).map(function (s) { return s.key; });
    var needs = NEEDS.filter(function (n) { return n.key !== 'attribution' || states.attribution !== 'ready'; });
    return { seen: seen, needs: needs, failed: failed };
  }

  // ------------------------------------------------------------------ جدول الحملات
  function ownerMap(owners) {
    var m = {};
    (Array.isArray(owners) ? owners : []).forEach(function (o) { if (o) m[o.campaign_id] = o; });
    return m;
  }
  // «ل» + الاسم بقاعدة العربية: «للإيجار» لا «لالإيجار»، وغير العربي يبقى «لـ».
  function lam(title) {
    title = String(title || '').trim();
    if (/^ال/.test(title)) return 'لل' + title.slice(2);
    return /^[؀-ۿ]/.test(title) ? 'ل' + title : 'لـ' + title;
  }
  function ownerTitleOf(owner) { return owner ? (owner.owner_title || owner.owner_id || '') : ''; }
  function ownerLine(owner) { return !owner || owner.owner_kind === 'platform' ? STR.ownerForSelf : lam(ownerTitleOf(owner)); }
  function rowsView(rows, owners, filter, attribution) {
    rows = Array.isArray(rows) ? rows : [];
    var sel = filter === 'all' ? rows : activeRows(rows);
    var om = ownerMap(owners), ownersOk = Array.isArray(owners), ready = attReady(attribution);
    var list = sel.slice().sort(function (a, b) {
      return (b.status === 'active') - (a.status === 'active') || b.spent - a.spent || (a.name < b.name ? -1 : a.name > b.name ? 1 : 0);
    }).map(function (r) {
      var ra = r.revenue > 0 ? ratio(r.revenue, r.spent) : null, via = ready ? viaFor(attribution, r.id) : null;
      return { id: r.id, name: r.name, owner: ownersOk ? ownerLine(om[r.id]) : '', platform: r.platformLabel, status: r.status, statusLabel: r.statusLabel,
               currency: r.currency, spentText: money(r.spent, r.currency), budgetText: money(r.budget, r.currency), clicks: U.ar(r.clicks), leads: U.ar(r.leads), conversions: U.ar(r.conversions),
               revenueText: money(r.revenue, r.currency), ratio: ra, ratioText: ra == null ? '—' : ratioNum(ra), ratioTone: ra == null ? '' : ra < 1 ? 'bad' : ra >= 3 ? 'good' : '',
               noResults: r.noResults, via: via, viaText: via ? 'سجّلوا ' + U.ar(via.signups) + ' · دفعوا ' + U.ar(via.paid) : (ready ? '—' : '') };
    });
    var organic = { name: STR.organicName, sub: STR.organicSub, na: !ready, naText: STR.organicNa, signups: '', paid: '', revenueText: '', ratioText: STR.organicRatio };
    if (ready) {
      organic.signups = U.ar(organicCount(attribution, 'signups')); organic.paid = U.ar(organicCount(attribution, 'paid_people'));
      organic.revenueText = moneyListText(organicTotals(attribution)) || '—';
    }
    return { rows: list, organic: organic, viaColumn: ready };
  }

  // ------------------------------------------------------------------ بطاقات السوشيال
  function byPlatform(rows) {
    var out = {};
    SOCIAL.forEach(function (p) {
      var mine = (Array.isArray(rows) ? rows : []).filter(function (r) { return r.platform === p.key || (r.platform === 'facebook_instagram' && (p.key === 'facebook' || p.key === 'instagram')); });
      var shared = mine.some(function (r) { return r.platform === 'facebook_instagram'; });
      var spent = sumField(mine, 'spent'), rev = sumField(mine, 'revenue');
      var conv = mine.reduce(function (s, r) { return s + r.conversions; }, 0);
      var o = { key: p.key, label: p.label, mark: p.mark, n: mine.length, spent: spent, revenue: rev, conversions: conv, shared: shared, sharedText: shared && p.mate ? '(مشتركة مع ' + p.mate + ')' : '',
                big: '', na: false, others: [], othersText: '', caption: STR.socialCaption, fact: '' };
      if (!mine.length) { o.big = STR.socialNone; o.na = true; o.caption = ''; }
      else {
        var pk = pickPrimary(spent);
        if (!pk) { o.big = STR.noSpend; o.na = true; }
        else { o.big = U.moneyText(pk.primary.amount, pk.primary.currency); o.others = pk.others; o.othersText = othersText(pk.others); }
        var fact = Un(mine.length, ['حملة واحدة', 'حملتان', 'حملات', 'حملة']) + ' · دفعوا ' + U.ar(conv);
        if (pk) {
          var rv = rev.filter(function (s) { return s.currency === pk.primary.currency; })[0];
          if (rv && rv.amount > 0) fact += ' · ' + ratioText(Math.round(rv.amount / pk.primary.amount * 10) / 10, pk.primary.currency);
          else fact += ' · ' + STR.noRevenue;
        }
        o.fact = fact;
      }
      out[p.key] = o;
    });
    return out;
  }

  // ------------------------------------------------------------------ صاحب الحملة (قائمة الاختيار)
  function ownerValue(o) { return !o || o.owner_kind === 'platform' || !o.owner_kind ? 'platform' : o.owner_kind + ':' + o.owner_id; }
  function kindWord(k) { return k === 'course' ? STR.kindCourse : STR.kindBook; }
  // adsState: حالة مصدر الأرصدة · adsItems: items[] · loadedOwner: {owner_kind, owner_id, owner_title}|null · ownersReady (افتراضي true)
  function ownerChoices(adsState, adsItems, loadedOwner, ownersReady) {
    var loaded = ownerValue(loadedOwner), hasOwner = loaded !== 'platform';
    var cur = hasOwner ? { value: loaded, label: (loadedOwner.owner_title || loadedOwner.owner_id) + ' — ' + STR.ownerCurrent, title: loadedOwner.owner_title || '' } : { value: 'platform', label: STR.ownerSelf, title: '' };
    if (ownersReady === false) return { disabled: true, options: [cur], selected: loaded, hint: STR.ownerOwnersHint };
    if (adsState !== 'ready') return { disabled: true, options: [cur], selected: loaded, hint: STR.ownerAdsHint };
    var opts = [{ value: 'platform', label: STR.ownerSelf, title: '' }];
    (Array.isArray(adsItems) ? adsItems : []).forEach(function (it) {
      if (!it) return;
      var val = it.owner_kind + ':' + it.owner_id;
      var title = String(it.title || '').trim() || (hasOwner && val === loaded ? String(loadedOwner.owner_title || '').trim() : '');
      opts.push({ value: val, label: (title || 'عمل بلا عنوان (' + it.owner_id + ')') + ' — ' + kindWord(it.owner_kind), title: title });
    });
    if (hasOwner && !opts.some(function (o) { return o.value === loaded; })) opts.push(cur);
    return { disabled: false, options: opts, selected: loaded, hint: '' };
  }

  // ------------------------------------------------------------------ الرابط والكشف
  function link(id, platform) {
    var src = UTM_SRC[String(platform || '')] || 'other';
    return 'https://elprofessor.net/?utm_source=' + src + '&utm_medium=paid&utm_campaign=c' + id;
  }
  function duration(r) {
    if (r.start && r.end) return 'من ' + U.dateText(r.start) + ' إلى ' + U.dateText(r.end);
    if (r.start) return 'من ' + U.dateText(r.start) + ' حتى الآن';
    return 'بلا تاريخ';
  }
  function statement(r, owner, todayISO) {
    var lines = [];
    lines.push('كشف حملة «' + r.name + '» — ' + ownerLine(owner && owner.owner_kind ? owner : null));
    lines.push([r.platformLabel ? 'المنصة: ' + r.platformLabel : '', duration(r)].filter(Boolean).join(' · '));
    lines.push('صُرف: ' + money(r.spent, r.currency) + ' من ميزانية ' + money(r.budget, r.currency));
    lines.push('زيارات: ' + U.ar(r.clicks) + ' · سجّلوا: ' + U.ar(r.leads) + ' · دفعوا: ' + U.ar(r.conversions));
    lines.push('الدخل المسجّل: ' + money(r.revenue, r.currency));
    lines.push('الأرقام كما سُجّلت في لوحة البروفيسور بتاريخ ' + U.dateText(todayISO) + '.');
    return lines.filter(Boolean).join('\n');
  }

  // ------------------------------------------------------------------ التحقق من نموذج الحملة
  function validate(form, loadedOwner) {
    form = form || {};
    var fail = function (e) { return { ok: false, error: e, body: null, ownerChanged: false }; };
    var name = String(form.name == null ? '' : form.name).trim();
    if (!name) return fail(STR.errName);
    if (name.length > 255) return fail(STR.errNameLong);
    var platform = String(form.platform || '').trim();
    if (platform === 'other') { platform = String(form.platformOther || '').trim(); if (!platform) return fail(STR.errPlatform); }
    var currency = String(form.currency || 'EGP').trim();
    if (currency === 'other') { currency = String(form.currencyOther || '').trim().toUpperCase(); if (!/^[A-Z]{3}$/.test(currency)) return fail(STR.errCur); }
    var start = isoDay(form.start), end = isoDay(form.end);
    if (start && end && end < start) return fail(STR.errEnd);
    var audience = String(form.audience == null ? '' : form.audience).trim();
    if (audience.length > 500) return fail(STR.errAudience);
    var out = {}, fields = [['budget', STR.fBudget, false], ['spent', STR.fSpent, false], ['clicks', STR.fClicks, true], ['leads', STR.fLeads, true],
                            ['conversions', STR.fPaid, true], ['revenue', STR.fRevenue, false]];
    for (var i = 0; i < fields.length; i++) {
      var f = fields[i], raw = String(form[f[0]] == null ? '' : form[f[0]]).trim();
      if (/^[-−–]/.test(raw)) return fail(STR.errNeg);
      var v = U.parseAmount(raw);
      if (v === null) v = 0;
      if (typeof v !== 'number' || isNaN(v)) return fail((f[2] ? STR.errInt : STR.errNum) + f[1]);
      if (f[2] && Math.floor(v) !== v) return fail(STR.errInt + f[1]);
      out[f[0]] = v;
    }
    var body = { name: name, platform: platform, status: STATUS_LABEL[form.status] ? form.status : 'active', budget: out.budget, spent: out.spent, currency: currency,
                 clicks: out.clicks, leads: out.leads, conversions: out.conversions, revenue_attributed: out.revenue, target_audience: audience };
    if (!form.edit) body.impressions = 0;
    if (start) body.start_date = start;
    if (end) body.end_date = end;
    var loaded = ownerValue(loadedOwner), chosen = String(form.ownerValue || 'platform');
    var ownerChanged = !form.ownerDisabled && (chosen !== loaded || !form.edit);   // الإنشاء يرسل الصاحب دائمًا فيُستبدل أي صف قديم بنفس الرقم
    var owner = null;
    if (ownerChanged) {
      if (chosen === 'platform') owner = { owner_kind: 'platform' };
      else { var ix = chosen.indexOf(':'); owner = { owner_kind: chosen.slice(0, ix), owner_id: chosen.slice(ix + 1), owner_title: String(form.ownerTitle || '').slice(0, 200) }; }
    }
    return { ok: true, error: '', body: body, ownerChanged: ownerChanged, owner: owner };
  }

  // اقتراحات العقل بشكل بطاقة القرار (للوحة الرئيسية لاحقًا).
  function cards(rows, todayISO, skipped) {
    var b = brain(rows, todayISO, skipped);
    return b.items.filter(function (it) { return it.kind !== 'empty'; }).map(function (it) { return { kind: 'mk_' + it.kind, id: it.id, title: it.text, line: it.line, btn: it.btn, action: it.action }; });
  }

  L.mk = {
    STR: STR, NA: NA, norm: norm, board: board, legacyUsd: legacyUsd, mature: mature, ratio: ratio, ratioText: ratioText, brain: brain, mainButton: mainButton,
    sources: sources, rows: rowsView, byPlatform: byPlatform, ownerChoices: ownerChoices, ownerValue: ownerValue, link: link, statement: statement, validate: validate,
    via: viaFor, attReady: attReady, organicTotals: organicTotals, organicCount: organicCount, duration: duration, cards: cards, unitOf: unitOf,
    PLATFORM_OPTS: PLATFORM_OPTS, CURRENCY_OPTS: CURRENCY_OPTS, PLATFORM_LABEL: PLATFORM_LABEL, STATUS_LABEL: STATUS_LABEL, SOCIAL: SOCIAL, NEEDS: NEEDS,
    ownerLine: ownerLine, ownerTitleOf: ownerTitleOf, lam: lam, ownerMap: ownerMap, kindWord: kindWord, moneyListText: moneyListText
  };
})(typeof window !== 'undefined' ? window : (typeof globalThis !== 'undefined' ? globalThis : this));
// ===== /v2s:marketing =====

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

// ===== v2s:experts =====
// «الخبراء» (ملفات الخبراء ‹ الخبراء): منطق نقي بلا DOM ولا شبكة. المصدر الذي تعذّر جلبه يصل `null` ويعود `null`/«غير متاح بعد» — لا صفرًا.
// ⛔ لا حكم ولا رقم مخترع: سطر العقل يُبنى من حقول موجودة فقط. ⛔ لا إنجليزية خام في التخصص: كل مفتاح يمرّ على قاموس عربي.
(function (root) {
  var L = root.V2L || (typeof module !== 'undefined' && module.exports);
  if (!L) return;
  var U = L.util;
  L.v2s = L.v2s || {};
  var NA = 'غير متاح بعد';
  function s(v) { return typeof v === 'string' ? v.trim() : ''; }
  function num(v) { var n = typeof v === 'number' ? v : (typeof v === 'string' && v.trim() !== '' ? Number(v) : NaN); return isFinite(n) ? n : null; }
  function tms(v) { if (typeof v === 'number') return isFinite(v) && v > 0 ? v : NaN; var t = Date.parse(v || ''); return isNaN(t) ? NaN : t; }

  // قاموس التخصصات: مفاتيح المنصة (والأسماء الإنجليزية الشائعة) ⇒ الاسم العربي الظاهر.
  var SPEC = {
    criminal: 'جنائي', penal: 'جنائي', civil: 'مدني وعقود', commercial: 'تجاري وشركات', business: 'تجاري وشركات', corporate: 'شركات',
    company: 'شركات', companies: 'شركات', labor: 'عمالي', labour: 'عمالي', employment: 'عمالي', family: 'أحوال شخصية', personal_status: 'أحوال شخصية',
    administrative: 'إداري', constitutional: 'دستوري', arbitration: 'تحكيم', ip: 'ملكية فكرية', intellectual_property: 'ملكية فكرية',
    real_estate: 'عقارات وإيجارات', realty: 'عقارات وإيجارات', notarization: 'توثيق', tax: 'ضرائب', taxes: 'ضرائب', marketing: 'تسويق ومحتوى',
    general: 'عام', other: 'أخرى'
  };
  function specialty(v) {
    var t = s(v);
    if (!t) return '';
    var k = t.toLowerCase().replace(/[\s-]+/g, '_');
    if (SPEC.hasOwnProperty(k)) return SPEC[k];
    return /[A-Za-z]/.test(t) ? 'تخصص آخر' : t;     // ما لا نعرفه بالإنجليزية لا يظهر خامًا
  }
  // قائمة أو نص واحد («civil, family» أو «مدني، جنائي») ⇒ أسماء عربية بلا تكرار.
  function specialties(v) {
    var parts = Array.isArray(v) ? v : String(v == null ? '' : v).split(/[,،؛;\/|]+/);
    var out = [];
    parts.forEach(function (p) { var l = specialty(p); if (l && out.indexOf(l) < 0) out.push(l); });
    return out;
  }

  var LEAD_STATUS = { 'new': 'جديد', contacted: 'تم التواصل', invited: 'تمت دعوته', converted: 'صار مدرّبًا', rejected: 'ليس مناسبًا', resolved: 'عولج' };
  var LEAD_TONE = { 'new': 'late', resolved: 'wait', contacted: 'wait', invited: 'ok', converted: 'done', rejected: 'done' };
  var LEAD_NEXT = { 'new': ['contacted', 'تم التواصل'], resolved: ['contacted', 'تم التواصل'], contacted: ['invited', 'تمت دعوته'], invited: ['converted', 'صار مدرّبًا'] };
  var LEAD_ORDER = { 'new': 0, resolved: 1, contacted: 2, invited: 3 };
  function phoneOf(p) { return String(p == null ? '' : p).replace(/[^0-9+]/g, ''); }
  function adig(t) { return String(t).replace(/\d/g, function (d) { return '٠١٢٣٤٥٦٧٨٩'.charAt(+d); }); }   // أرقام عربية في النص الحر (الخبرة)

  // تذكرة لكل ردّ على دعوة المؤسس: حالة · من هو · سطر العقل · زرّ رئيسي واحد وثانوي «ليس مناسبًا». المحوَّل والمرفوض نهاية فلا تذكرة لهما.
  function leadTicket(l, now) {
    if (!l || typeof l !== 'object') return null;
    var st = s(l.status) || 'new';
    if (!LEAD_STATUS.hasOwnProperty(st)) st = 'new';
    var at = tms(l.at), since = isNaN(at) ? '' : L.v2TimerText({ mode: 'since', at: at }, now);
    var nx = LEAD_NEXT[st] || null;
    var brain;
    if (st === 'new') brain = 'لم يتم التواصل معه بعد' + (since ? '. قدّم طلبه ' + since : '') + '.';
    else if (st === 'resolved') brain = 'عولج طلبه سابقًا دون تسجيل التواصل. سجّل التواصل ليبقى ملفه واضحًا.';
    else if (st === 'contacted') brain = 'تم التواصل معه. الخطوة التالية دعوته للانضمام.';
    else if (st === 'invited') brain = 'تمت دعوته. الخطوة التالية اعتماده مدرّبًا بعد تسجيله.';
    else brain = '';
    var email = s(l.email).toLowerCase();
    return {
      id: s(l.id), name: s(l.name) || 'بلا اسم', status: st, statusLabel: LEAD_STATUS[st], tone: LEAD_TONE[st], since: since, at: isNaN(at) ? null : at,
      specs: specialties(l.specialization), country: s(l.country) || s(l.governorate), years: adig(s(String(l.years == null ? '' : l.years))),
      phone: phoneOf(l.whatsapp), phoneText: s(String(l.whatsapp == null ? '' : l.whatsapp)), email: email, brain: brain,
      primary: nx ? { status: nx[0], label: nx[1] } : null, secondary: nx ? { status: 'rejected', label: 'ليس مناسبًا' } : null, row: l
    };
  }
  // اللوحة: التذاكر المفتوحة (من يحتاج فعلًا أولًا ثم الأقدم) وعدد ما عولج. المصدر الفاشل (null) ⇒ null.
  function leadBoard(rows, now) {
    if (!Array.isArray(rows)) return null;
    var open = [], closed = { converted: 0, rejected: 0 };
    rows.forEach(function (l) {
      var t = leadTicket(l, now);
      if (!t) return;
      if (t.status === 'converted' || t.status === 'rejected') closed[t.status]++;
      else open.push(t);
    });
    open.sort(function (a, b) {
      var d = LEAD_ORDER[a.status] - LEAD_ORDER[b.status];
      if (d) return d;
      var x = a.at == null ? Infinity : a.at, y = b.at == null ? Infinity : b.at;
      return x === y ? 0 : x < y ? -1 : 1;
    });
    return { open: open, converted: closed.converted, rejected: closed.rejected, total: rows.length };
  }

  // أسباب إخفاء الخبير عن الدليل العام (الحقول القادمة من المنصة فقط؛ المجهول لا يُحكم عليه).
  function hiddenReasons(e) {
    var r = [];
    if (e.is_test) r.push('الحساب مُعلَّم تجريبيًّا');
    if (e.public_ready === false) r.push('الملف ناقص: نبذة لا تقل عن ٢٠ حرفًا وسعر للجلسة');
    else if (e.public_ready == null && (!e.bio || String(e.bio).length < 20)) r.push('النبذة أقصر من ٢٠ حرفًا');
    return r;
  }
  function ratingText(e) {
    var a = num(e.rating_avg);
    if (a === null) return 'لا تقييم بعد';
    var c = num(e.rating_count);
    return U.fmt(Math.round(a * 10) / 10) + (c ? ' (' + U.ar(c) + ')' : '');
  }
  function expertRow(e) {
    if (!e || typeof e !== 'object') return null;
    var reasons = hiddenReasons(e), email = s(e.email).toLowerCase();
    var brain;
    if (reasons.length) brain = 'لا يظهر في دليل الخبراء للناس: ' + reasons.join('، ') + '.';
    else if (e.public_ready === true) brain = 'يظهر في دليل الخبراء للناس.';
    else brain = 'ظهوره في الدليل: ' + NA + '.';
    return {
      name: s(e.name) || email || 'بلا اسم', email: email, online: !!e.online, specs: specialties(e.expertise), rating: ratingText(e),
      referrals: num(e.referral_count), courses: num(e.courses_count), learners: num(e.students_count), hidden: reasons.length > 0, reasons: reasons,
      brain: brain
    };
  }
  // الخبراء: من لا يظهر للناس أولًا (يحتاج انتباهًا)، ثم الأكثر إحالات، ثم الاسم. المصدر الفاشل ⇒ null.
  function expertBoard(list) {
    if (!Array.isArray(list)) return null;
    var rows = list.map(expertRow).filter(Boolean);
    rows.sort(function (a, b) {
      if (a.hidden !== b.hidden) return a.hidden ? -1 : 1;
      var d = (b.referrals || 0) - (a.referrals || 0);
      return d || String(a.name).localeCompare(String(b.name), 'ar');
    });
    return { rows: rows, online: rows.filter(function (r) { return r.online; }).length, hidden: rows.filter(function (r) { return r.hidden; }).length };
  }
  function summaryLine(eb, lb) {
    if (!eb) return 'الخبراء: ' + NA;
    var p = [U.U(eb.rows.length, ['خبير معتمد واحد', 'خبيران معتمدان', 'خبراء معتمدون', 'خبيرًا معتمدًا'])];
    if (eb.online) p.push(U.U(eb.online, ['متصل الآن', 'متصلان الآن', 'متصلون الآن', 'متصلًا الآن']));
    if (eb.hidden) p.push(U.U(eb.hidden, ['خبير لا يظهر للناس', 'خبيران لا يظهران للناس', 'خبراء لا يظهرون للناس', 'خبيرًا لا يظهر للناس']));
    if (lb && lb.open.length) p.push(U.U(lb.open.length, ['رد على دعوة المؤسس ينتظرك', 'ردّان على دعوة المؤسس ينتظرانك', 'ردود على دعوة المؤسس تنتظرك', 'ردًّا على دعوة المؤسس ينتظرك']));
    return p.join(' · ');
  }

  L.v2s.experts = { NA: NA, SPEC: SPEC, specialty: specialty, specialties: specialties, LEAD_STATUS: LEAD_STATUS, LEAD_NEXT: LEAD_NEXT, leadTicket: leadTicket,
                    leadBoard: leadBoard, hiddenReasons: hiddenReasons, expertRow: expertRow, expertBoard: expertBoard, summaryLine: summaryLine };
  if (typeof module !== 'undefined' && module.exports) module.exports.v2s = L.v2s;
})(typeof window !== 'undefined' ? window : (typeof globalThis !== 'undefined' ? globalThis : this));
// ===== /v2s:experts =====

// ===== courses2 =====
// محرّر الدورات من الداشبورد (SPEC-C-courses §C1): دوال نقية فقط — قاموس الكتل وحقولها الرئيسية، عمليات قائمة الكتل (إضافة · تحريك · حذف)،
// فرق الهيكل وجسم الـPUT، أجسام حفظ الدرس لكل نوع، خطة رفع TUS على قطع ورافع بدالة `fetch` تُمرَّر، وأجسام مساعد الدورة.
// ⛔ لا DOM ولا شبكة ولا ساعة خفية (الرافع يأخذ `fetch` من المنادي). ⛔ لا سعر ولا نسبة هنا أبدًا.
(function (root) {
  'use strict';
  var L = root.V2L || (typeof module !== 'undefined' && module.exports);
  if (!L) return;
  var DIG = '٠١٢٣٤٥٦٧٨٩';
  function arN(n) { return String(Math.round(Number(n) || 0)).replace(/\d/g, function (d) { return DIG.charAt(+d); }); }
  function isObj(x) { return x && typeof x === 'object' && !Array.isArray(x); }
  function clone(x) { return x === undefined ? undefined : JSON.parse(JSON.stringify(x)); }
  function str(x) { return x == null ? '' : String(x); }

  // ------------------------------------------------------------------ قاموس الكتل
  // حقل: {k, l, t: text|area|lines|rows|int, cols: [{k, l, t: text|area|bool}], hint}
  var F = {
    text: function (k, l, h) { return { k: k, l: l, t: 'text', hint: h || '' }; },
    area: function (k, l, h) { return { k: k, l: l, t: 'area', hint: h || '' }; },
    lines: function (k, l, h) { return { k: k, l: l, t: 'lines', hint: h || 'سطر لكل عنصر' }; },
    rows: function (k, l, cols, h) { return { k: k, l: l, t: 'rows', cols: cols, hint: h || '' }; }
  };
  var C = {
    text: function (k, l) { return { k: k, l: l, t: 'text' }; },
    area: function (k, l) { return { k: k, l: l, t: 'area' }; },
    bool: function (k, l) { return { k: k, l: l, t: 'bool' }; }
  };
  var TYPES = [
    { type: 'text', ar: 'نص', main: true, fields: [F.area('md', 'النص')], blank: { type: 'text', md: '' } },
    { type: 'objectives', ar: 'الأهداف', main: true, fields: [F.lines('items', 'الأهداف')], blank: { type: 'objectives', items: [''] } },
    { type: 'situation', ar: 'موقف', main: true, fields: [F.area('text', 'الموقف', 'ثلاث جمل أو أربع'), F.text('question', 'السؤال'),
      F.rows('options', 'الاختيارات', [C.text('text', 'الاختيار'), C.text('comment', 'التعليق')], 'من اختيارين إلى ثلاثة')],
      blank: { type: 'situation', text: '', question: '', options: [{ text: '', comment: '' }, { text: '', comment: '' }] } },
    { type: 'decision', ar: 'قرار', main: true, fields: [F.area('text', 'الموقف'), F.text('question', 'السؤال'),
      F.rows('options', 'الاختيارات', [C.text('text', 'الاختيار'), C.text('result', 'النتيجة'), C.text('comment', 'التعليق')], 'من اختيارين إلى ثلاثة')],
      blank: { type: 'decision', text: '', question: '', options: [{ text: '', result: '', comment: '' }, { text: '', result: '', comment: '' }] } },
    { type: 'recall', ar: 'افتكر', main: true, fields: [F.text('key', 'مفتاح القرار (حروف إنجليزية)'), F.text('default', 'النص الافتراضي')], blank: { type: 'recall', key: '', follow: {}, default: '' } },
    { type: 'quiz', ar: 'اختبار قصير', main: true, fields: [F.text('question', 'السؤال'),
      F.rows('options', 'الاختيارات', [C.text('text', 'الاختيار'), C.bool('ok', 'صحيح'), C.text('feedback', 'التعليق')])],
      blank: { type: 'quiz', question: '', options: [{ text: '', ok: true, feedback: '' }, { text: '', ok: false, feedback: '' }] } },
    { type: 'example', ar: 'مثال', main: true, fields: [F.text('title', 'العنوان'), F.area('text', 'نص المثال')], blank: { type: 'example', title: '', text: '' } },
    { type: 'cards', ar: 'كروت', main: true, fields: [F.text('prompt', 'التعليمة'), F.rows('cards', 'الكروت', [C.text('front', 'الوجه'), C.text('back', 'الظهر')], 'من ثلاثة إلى ستة')],
      blank: { type: 'cards', prompt: '', cards: [{ front: '', back: '' }, { front: '', back: '' }, { front: '', back: '' }] } },
    { type: 'summary', ar: 'ملخّص', main: true, fields: [F.lines('items', 'نقاط الملخّص')], blank: { type: 'summary', items: [''] } },
    { type: 'order', ar: 'رتّب', main: true, fields: [F.text('prompt', 'التعليمة'), F.lines('items', 'العناصر بالترتيب الصحيح', 'من ثلاثة إلى ستة، سطر لكل عنصر'), F.text('comment', 'التعليق')],
      blank: { type: 'order', prompt: '', items: ['', '', ''], comment: '' } },
    { type: 'match', ar: 'طابق', main: true, fields: [F.text('prompt', 'التعليمة'), F.rows('pairs', 'الأزواج', [C.text('left', 'الأول'), C.text('right', 'الثاني')], 'من ثلاثة إلى خمسة'), F.text('comment', 'التعليق')],
      blank: { type: 'match', prompt: '', pairs: [{ left: '', right: '' }, { left: '', right: '' }, { left: '', right: '' }], comment: '' } },
    { type: 'before_after', ar: 'قبل وبعد', main: true, fields: [F.area('before', 'قبل'), F.area('after', 'بعد'), F.text('comment', 'التعليق')], blank: { type: 'before_after', before: '', after: '', comment: '' } },
    { type: 'icon_line', ar: 'سطر بأيقونة', main: true, fields: [F.text('icon', 'الأيقونة (bulb · warn · target · question · star · clock · heart · check · message · people)'), F.text('text', 'السطر')],
      blank: { type: 'icon_line', icon: 'bulb', text: '' } },
    { type: 'quote', ar: 'اقتباس', main: true, fields: [F.area('text', 'الاقتباس'), F.text('by', 'القائل')], blank: { type: 'quote', text: '', by: '' } },
    { type: 'steps', ar: 'خطوات', main: true, fields: [F.lines('items', 'الخطوات')], blank: { type: 'steps', items: [''] } },
    { type: 'accordion', ar: 'أكورديون', main: true, fields: [F.text('title', 'العنوان'), F.rows('items', 'العناصر', [C.text('term', 'المصطلح'), C.text('text', 'الشرح')])],
      blank: { type: 'accordion', title: '', items: [{ term: '', text: '' }] } },
    { type: 'image', ar: 'صورة', main: true, fields: [F.text('url', 'رابط الصورة (https)'), F.text('alt', 'وصف الصورة')], blank: { type: 'image', url: '', alt: '' } },
    { type: 'video', ar: 'فيديو مدمج', main: true, fields: [F.text('url', 'رابط الفيديو'), F.text('title', 'العنوان'), F.area('transcript', 'نص الفيديو')], blank: { type: 'video', url: '', title: '', transcript: '' } },
    // أنواع بحقول كثيرة: تُحرَّر من «متقدّم» (JSON) وتبدأ بهيكل جاهز
    { type: 'spot', ar: 'اضغط الغلط', main: false, fields: [], blank: { type: 'spot', shape: 'post', prompt: '', sentences: [{ text: '', wrong: false }, { text: '', wrong: false }, { text: '', wrong: true, why: '' }], comment: '' } },
    { type: 'predict', ar: 'توقّع', main: false, fields: [], blank: { type: 'predict', question: '', options: [{ text: '', ok: true }, { text: '', ok: false }], reveal: '' } },
    { type: 'line', ar: 'اكتب سطرًا', main: false, fields: [], blank: { type: 'line', prompt: '', criteria: [''], fallback: '' } },
    { type: 'gate', ar: 'أسئلة البوابة', main: false, fields: [], blank: { type: 'gate', pass: 1, questions: [{ text: '', options: [{ text: '', ok: true, explanation: '' }, { text: '', ok: false, explanation: '' }] }] } },
    { type: 'exercise', ar: 'تمرين', main: false, fields: [], blank: { type: 'exercise', n: 1, title: '', intro: '', checks: [''], hint: '' } },
    { type: 'ai_station', ar: 'محطة المساعد', main: false, fields: [], blank: { type: 'ai_station', attempts: 2, task: '', rubric: '' } },
    { type: 'audio', ar: 'صوت', main: false, fields: [], blank: { type: 'audio', url: '', title: '', transcript: '' } },
    { type: 'case_pick', ar: 'اختيار الحالة', main: false, fields: [], blank: { type: 'case_pick' } },
    { type: 'download', ar: 'تنزيل', main: false, fields: [], blank: { type: 'download', what: 'workbook', label: '' } },
    { type: 'goal', ar: 'هدفك', main: false, fields: [], blank: { type: 'goal' } },
    { type: 'eval', ar: 'تقييم', main: false, fields: [], blank: { type: 'eval' } },
    { type: 'chat', ar: 'محادثة موجّهة', main: false, fields: [], blank: { type: 'chat' } },
    { type: 'registered', ar: 'للمسجّلين', main: false, fields: [], blank: { type: 'registered' } },
    { type: 'sheet', ar: 'ورقة الملخّص', main: false, fields: [], blank: { type: 'sheet' } },
    { type: 'certificate', ar: 'شهادة', main: false, fields: [], blank: { type: 'certificate' } }
  ];
  var BY_TYPE = {};
  TYPES.forEach(function (t) { BY_TYPE[t.type] = t; });
  function typeAr(type) { return BY_TYPE[type] ? BY_TYPE[type].ar : str(type) || 'كتلة'; }
  function typeDef(type) { return BY_TYPE[type] || null; }
  function blankBlock(type) { return BY_TYPE[type] ? clone(BY_TYPE[type].blank) : { type: str(type) }; }

  // ------------------------------------------------------------------ عمليات القائمة (نقية: تعيد قائمة جديدة)
  function blocksAdd(blocks, block, at) {
    var a = (blocks || []).slice();
    var i = at == null || at < 0 || at > a.length ? a.length : at;
    a.splice(i, 0, block);
    return a;
  }
  function blocksMove(blocks, i, dir) {
    var a = (blocks || []).slice(), j = i + (dir < 0 ? -1 : 1);
    if (i < 0 || i >= a.length || j < 0 || j >= a.length) return a;
    var t = a[i]; a[i] = a[j]; a[j] = t;
    return a;
  }
  function blocksDelete(blocks, i) {
    var a = (blocks || []).slice();
    if (i >= 0 && i < a.length) a.splice(i, 1);
    return a;
  }
  // setIn(obj, 'options.1.text', v) ⇒ نسخة جديدة. المسار أرقام ومفاتيح مفصولة بنقطة.
  function setIn(obj, path, value) {
    var keys = String(path).split('.');
    var out = clone(obj);
    var cur = out;
    for (var i = 0; i < keys.length - 1; i++) {
      var k = /^\d+$/.test(keys[i]) ? +keys[i] : keys[i];
      if (cur[k] == null || typeof cur[k] !== 'object') cur[k] = /^\d+$/.test(keys[i + 1]) ? [] : {};
      cur = cur[k];
    }
    var last = keys[keys.length - 1];
    cur[/^\d+$/.test(last) ? +last : last] = value;
    return out;
  }
  function rowAdd(block, field, blankRow) {
    var arr = (block[field] || []).slice();
    arr.push(clone(blankRow));
    return setIn(block, field, arr);
  }
  function rowDelete(block, field, i) {
    var arr = (block[field] || []).slice();
    if (i >= 0 && i < arr.length) arr.splice(i, 1);
    return setIn(block, field, arr);
  }
  function linesToArr(s) { return str(s).replace(/\r/g, '').split('\n').map(function (x) { return x.trim(); }).filter(function (x) { return x; }); }
  function arrToLines(a) { return Array.isArray(a) ? a.map(str).join('\n') : ''; }
  // رأس الكتلة في القائمة: أول نص مفهوم منها
  function blockHead(b) {
    if (!isObj(b)) return '';
    var order = ['title', 'question', 'prompt', 'md', 'text', 'before', 'by', 'url'];
    for (var i = 0; i < order.length; i++) {
      var v = b[order[i]];
      if (typeof v === 'string' && v.trim()) return v.trim().replace(/\s+/g, ' ').slice(0, 70);
    }
    if (Array.isArray(b.items) && b.items.length) {
      var f = b.items[0];
      var t = typeof f === 'string' ? f : (f && (f.text || f.term)) || '';
      if (t) return str(t).trim().slice(0, 70);
    }
    return '';
  }
  // JSON «متقدّم»: نص ⇒ {ok, block} أو {ok:false, error}
  function parseBlockJson(text) {
    var v;
    try { v = JSON.parse(text); } catch (e) { return { ok: false, error: 'النص ليس JSON صالحًا' }; }
    if (!isObj(v)) return { ok: false, error: 'يجب أن تكون الكتلة كائنًا' };
    if (typeof v.type !== 'string' || !v.type) return { ok: false, error: 'تنقص الكتلة خانة «type»' };
    return { ok: true, block: v };
  }
  function blocksIssues(blocks) {
    var out = [];
    (blocks || []).forEach(function (b, i) {
      if (!isObj(b) || typeof b.type !== 'string' || !b.type) out.push('الكتلة ' + arN(i + 1) + ' بلا نوع');
    });
    return out;
  }

  // ------------------------------------------------------------------ زمن «د:ث»
  function parseT(s) {
    s = str(s).trim().replace(/[٠-٩]/g, function (d) { return DIG.indexOf(d); });
    if (!s) return null;
    var m = /^(\d+):([0-5]?\d)$/.exec(s);
    if (m) return (+m[1]) * 60 + (+m[2]);
    return /^\d+$/.test(s) ? +s : null;
  }
  function fmtT(n) {
    n = Math.max(0, Math.round(Number(n) || 0));
    var m = Math.floor(n / 60), s = n % 60;
    return m + ':' + (s < 10 ? '0' : '') + s;
  }

  // ------------------------------------------------------------------ أجسام حفظ الدرس
  function hasContent(l) {
    if (!isObj(l)) return false;
    if (l.kind === 'interactive') return Array.isArray(l.blocks) && l.blocks.length > 0;
    if (l.kind === 'recorded') return !!(l.has_video || (l.video && (l.video.bunny_video_id || l.video.url)) || (Array.isArray(l.summary) && l.summary.length) || str(l.transcript).trim());
    if (l.kind === 'live') return !!(l.starts_at || l.zoom_link || l.recording_url);
    return false;
  }
  function cleanOptions(opts) {
    return (opts || []).map(function (o) { return { text: str(o.text).trim(), ok: o.ok === true, explanation: str(o.explanation).trim() }; }).filter(function (o) { return o.text; });
  }
  // مسودة الفيديو: {touched, mode: 'upload'|'link'|'none', bunny_video_id, url}
  function videoBody(v) {
    if (!v || !v.touched) return undefined;
    if (v.mode === 'upload' && v.bunny_video_id) return { bunny_video_id: v.bunny_video_id };
    if (v.mode === 'link' && str(v.url).trim()) return { url: str(v.url).trim() };
    return {};
  }
  // lessonBody(lesson, draft) ⇒ جسم PUT الدرس (الحقول القابلة للتحرير فقط، لا مسودة غير مرسلة)
  function lessonBody(lesson, draft) {
    var d = draft || lesson, kind = lesson.kind, out = { title: str(d.title).trim() };
    if (kind === 'interactive') {
      out.blocks = clone(d.blocks || []);
      out.time = Math.max(0, parseInt(d.time, 10) || 0);
      out.for = Array.isArray(d.for) ? d.for.slice() : [];
      if (str(d.hero).trim() || str(lesson.hero).trim()) out.hero = str(d.hero).trim();
      if (str(d.motion).trim() || str(lesson.motion).trim()) out.motion = str(d.motion).trim();
    } else if (kind === 'recorded') {
      var vb = videoBody(d._video);
      if (vb !== undefined) out.video = vb;
      var secs = parseT(d.duration_seconds);
      out.duration_seconds = secs == null ? 0 : secs;
      out.is_preview = d.is_preview === true;
      out.chapters = (d.chapters || []).map(function (c) { return { t: parseT(c.t) || 0, title: str(c.title).trim() }; }).filter(function (c) { return c.title; });
      out.checkpoints = (d.checkpoints || []).map(function (c) { return { t: parseT(c.t) || 0, question: str(c.question).trim(), options: cleanOptions(c.options) }; }).filter(function (c) { return c.question; });
      out.summary = (Array.isArray(d.summary) ? d.summary : linesToArr(d.summary)).map(function (x) { return str(x).trim(); }).filter(Boolean).slice(0, 3);
      out.transcript = str(d.transcript).trim();
    } else if (kind === 'live') {
      out.starts_at = str(d.starts_at).trim();
      out.duration_min = Math.max(0, parseInt(d.duration_min, 10) || 0);
      out.zoom_link = str(d.zoom_link).trim();
      out.recording_url = str(d.recording_url).trim();
      out.status = str(d.status).trim() || 'scheduled';
      var q = d.quiz;
      out.quiz = q && str(q.question).trim() ? { question: str(q.question).trim(), options: cleanOptions(q.options) } : null;
    }
    return out;
  }
  function lessonIssues(lesson, draft) {
    var d = draft || lesson, out = [];
    if (!str(d.title).trim()) out.push('اكتب عنوان الدرس');
    if (lesson.kind === 'interactive') out = out.concat(blocksIssues(d.blocks));
    if (lesson.kind === 'recorded') {
      var sm = Array.isArray(d.summary) ? d.summary : linesToArr(d.summary);
      if (sm.filter(function (x) { return str(x).trim(); }).length > 3) out.push('الملخّص ثلاثة أسطر على الأكثر');
      (d.chapters || []).forEach(function (c, i) { if (str(c.t).trim() && parseT(c.t) == null) out.push('وقت الفصل ' + arN(i + 1) + ' غير مفهوم (اكتب مثل ١:٣٠)'); });
      (d.checkpoints || []).forEach(function (c, i) {
        if (str(c.t).trim() && parseT(c.t) == null) out.push('وقت سؤال التوقف ' + arN(i + 1) + ' غير مفهوم');
        if (str(c.question).trim() && cleanOptions(c.options).length < 2) out.push('سؤال التوقف ' + arN(i + 1) + ' يحتاج اختيارين');
      });
    }
    if (lesson.kind === 'live' && str(d.starts_at).trim() && isNaN(Date.parse(str(d.starts_at).trim()))) out.push('موعد البدء غير مفهوم');
    return out;
  }
  // مسودة محرّر من الدرس المخزّن (نسخة قابلة للتعديل)
  function draftFrom(lesson) {
    var d = clone(lesson) || {};
    if (lesson.kind === 'recorded') {
      d.duration_seconds = lesson.duration_seconds ? fmtT(lesson.duration_seconds) : '';
      d.chapters = (lesson.chapters || []).map(function (c) { return { t: fmtT(c.t), title: str(c.title) }; });
      d.checkpoints = (lesson.checkpoints || []).map(function (c) { return { t: fmtT(c.t), question: str(c.question), options: clone(c.options || []) }; });
      d.summary = (lesson.summary || []).slice();
      var v = lesson.video || {};
      d._video = { touched: false, mode: v.bunny_video_id ? 'upload' : (v.url ? 'link' : 'none'), bunny_video_id: v.bunny_video_id || '', url: v.bunny_video_id ? '' : (v.url || '') };
    }
    return d;
  }

  // ------------------------------------------------------------------ الهيكل
  function structFrom(course) {
    var units = ((course && course.outline && course.outline.units) || []).map(function (u) {
      return { id: u.id, title: str(u.title), lessons: (u.lessons || []).map(function (l) { return { id: l.id, title: str(l.title), kind: l.kind, hasContent: hasContent(l) }; }) };
    });
    return units;
  }
  function flat(units) {
    var out = [];
    (units || []).forEach(function (u) { (u.lessons || []).forEach(function (l) { out.push(l); }); });
    return out;
  }
  function structSig(units) {
    return JSON.stringify((units || []).map(function (u) {
      return [u.id || '+', str(u.title), (u.lessons || []).map(function (l) { return [l.id || '+', str(l.title), l.id ? '' : str(l.kind)]; })];
    }));
  }
  function structureDiff(prev, next) {
    var pm = {}, nm = {}, pu = {}, nu = {};
    flat(prev).forEach(function (l) { if (l.id) pm[l.id] = l; });
    (prev || []).forEach(function (u) { if (u.id) pu[u.id] = 1; });
    var kept = [], added = [], renamed = [], removed = [];
    flat(next).forEach(function (l) {
      if (l.id && pm[l.id]) { kept.push(l.id); nm[l.id] = true; if (str(pm[l.id].title) !== str(l.title)) renamed.push({ id: l.id, from: pm[l.id].title, to: l.title }); }
      else added.push({ title: l.title, kind: l.kind });
    });
    flat(prev).forEach(function (l) { if (l.id && !nm[l.id]) removed.push({ id: l.id, title: l.title, hasContent: !!l.hasContent }); });
    (next || []).forEach(function (u) { if (u.id && pu[u.id]) nu[u.id] = 1; });
    var prevOrder = flat(prev).map(function (l) { return l.id; }).filter(function (id) { return nm[id]; }).join(',');
    var prevUnitOrder = (prev || []).map(function (u) { return u.id; }).filter(function (id) { return nu[id]; }).join(',');
    var nextUnitOrder = (next || []).map(function (u) { return u.id; }).filter(function (id) { return id && nu[id]; }).join(',');
    var reordered = prevOrder !== kept.join(',') || prevUnitOrder !== nextUnitOrder;
    return { kept: kept, added: added, removed: removed, renamed: renamed, reordered: reordered,
             unitsAdded: (next || []).filter(function (u) { return !u.id || !pu[u.id]; }).length,
             unitsRemoved: (prev || []).filter(function (u) { return !nu[u.id]; }).length,
             changed: structSig(prev) !== structSig(next) };
  }
  function structureErrors(units) {
    var out = [];
    if (!(units || []).length) out.push('أضف وحدة واحدة على الأقل');
    if ((units || []).length > 30) out.push('الوحدات حتى ٣٠ وحدة');
    if (flat(units).length > 200) out.push('الدروس حتى ٢٠٠ درس');
    (units || []).forEach(function (u, i) {
      if (!str(u.title).trim()) out.push('الوحدة ' + arN(i + 1) + ' بلا عنوان');
      (u.lessons || []).forEach(function (l, j) {
        if (!str(l.title).trim()) out.push('الدرس ' + arN(j + 1) + ' في الوحدة ' + arN(i + 1) + ' بلا عنوان');
        if (!l.id && ['interactive', 'recorded', 'live'].indexOf(l.kind) < 0) out.push('اختر نوع الدرس «' + (str(l.title).trim() || 'الجديد') + '»: تفاعلي أو مسجّل أو مباشر');
      });
    });
    return out;
  }
  function structureBody(units, cases) {
    var body = { units: (units || []).map(function (u) {
      var o = { title: str(u.title).trim(), lessons: (u.lessons || []).map(function (l) {
        var x = { title: str(l.title).trim(), kind: l.kind };
        if (l.id) x.id = l.id;
        return x;
      }) };
      if (u.id) o.id = u.id;
      return o;
    }) };
    if (Array.isArray(cases)) body.cases = cases.slice();
    return body;
  }
  // يضيف وحدات مسودة «حوّل مادتي» إلى الهيكل الحالي (القديم يبقى بمعرّفاته)
  function mergeDraftIntoStructure(existing, draft) {
    var units = clone(existing) || [];
    ((draft && draft.units) || []).forEach(function (u) {
      units.push({ title: str(u.title).trim() || 'وحدة جديدة', lessons: (u.lessons || []).map(function (l) { return { title: str(l.title).trim() || 'درس جديد', kind: 'recorded' }; }) });
    });
    return units;
  }
  function draftLessons(draft) {
    var out = [];
    ((draft && draft.units) || []).forEach(function (u) { (u.lessons || []).forEach(function (l) { out.push(l); }); });
    return out;
  }
  // بعد الـPUT: الدروس الجديدة (ليست في المعرّفات القديمة) بترتيبها ⇒ تُقابَل بدروس المسودة بالترتيب
  function pairNewLessons(prevIds, course, draft) {
    var seen = {};
    (prevIds || []).forEach(function (id) { seen[id] = 1; });
    var fresh = flat(((course && course.outline && course.outline.units) || [])).filter(function (l) { return l.id && !seen[l.id]; });
    var dl = draftLessons(draft);
    return fresh.map(function (l, i) {
      var d = dl[i] || {};
      return { id: l.id, title: l.title, body: { summary: (d.summary || []).slice(0, 3).map(str), transcript: str(d.transcript) } };
    });
  }

  // ------------------------------------------------------------------ رفع TUS
  var CHUNK = 5 * 1024 * 1024;
  function tusPlan(size, chunk) {
    chunk = chunk || CHUNK;
    var out = [];
    for (var off = 0; off < size; off += chunk) out.push({ offset: off, length: Math.min(chunk, size - off) });
    return out;
  }
  function b64(s, enc) {
    if (enc) return enc(s);
    if (typeof btoa === 'function') return btoa(unescape(encodeURIComponent(s)));
    return Buffer.from(s, 'utf8').toString('base64');
  }
  function tusMetadata(meta, enc) {
    return Object.keys(meta).map(function (k) { return k + ' ' + b64(str(meta[k]), enc); }).join(',');
  }
  // رفع كامل: POST لإنشاء الرفع ثم PATCH لكل قطعة. up = ردّ المسار ١٢ (upload_url · headers). fetchFn(url, init) ⇒ Promise<{ok,status,headers:{get}}>
  function tusUpload(file, up, fetchFn, opts) {
    opts = opts || {};
    var plan = tusPlan(file.size, opts.chunk), auth = up.headers || {};
    var baseH = { 'Tus-Resumable': '1.0.0' };
    ['AuthorizationSignature', 'AuthorizationExpire', 'VideoId', 'LibraryId'].forEach(function (k) { if (auth[k] != null) baseH[k] = String(auth[k]); });
    var meta = { filetype: file.type || 'video/mp4', title: opts.title || file.name || 'video' };
    var createH = Object.assign({}, baseH, { 'Upload-Length': String(file.size), 'Upload-Metadata': tusMetadata(meta, opts.b64) });
    function fail(msg, status) { var e = new Error(msg); e.status = status || 0; return e; }
    return fetchFn(up.upload_url, { method: 'POST', headers: createH }).then(function (r) {
      if (!r || !(r.status >= 200 && r.status < 300)) throw fail('تعذّر بدء الرفع', r && r.status);
      var loc = r.headers && r.headers.get && r.headers.get('Location');
      var url = loc ? new URL(loc, up.upload_url).href : up.upload_url;
      var i = 0, sent = 0;
      if (opts.onProgress) opts.onProgress(0, file.size);
      function next() {
        if (i >= plan.length) { if (opts.onProgress) opts.onProgress(file.size, file.size); return Promise.resolve({ ok: true, chunks: plan.length }); }
        var p = plan[i];
        var h = Object.assign({}, baseH, { 'Content-Type': 'application/offset+octet-stream', 'Upload-Offset': String(p.offset) });
        return fetchFn(url, { method: 'PATCH', headers: h, body: file.slice(p.offset, p.offset + p.length) }).then(function (r2) {
          if (!r2 || !(r2.status >= 200 && r2.status < 300)) throw fail('انقطع الرفع عند القطعة ' + arN(i + 1) + ' من ' + arN(plan.length), r2 && r2.status);
          var off = r2.headers && r2.headers.get && r2.headers.get('Upload-Offset');
          sent = off != null && off !== '' && !isNaN(+off) ? +off : p.offset + p.length;
          i++;
          if (opts.onProgress) opts.onProgress(Math.min(sent, file.size), file.size);
          return next();
        });
      }
      return next();
    });
  }

  // ------------------------------------------------------------------ مساعد الدورة
  var ASSIST = [
    { kind: 'activity_decision', ar: 'حوّل إلى نشاط قرار', lesson: true, text: 'حوّل الفقرة إلى نشاط قرار', ask: false },
    { kind: 'shorter_title', ar: 'اقترح عناوين أقصر', lesson: true, text: 'اقترح عناوين أقصر للدرس', ask: false },
    { kind: 'video_script', ar: 'اكتب نص فيديو', lesson: true, text: 'اكتب نص فيديو للدرس', ask: false },
    { kind: 'free', ar: 'سؤال حر', lesson: false, text: '', ask: true },
    { kind: 'from_material', ar: 'حوّل مادتي إلى دروس', lesson: false, text: 'حوّل مادتي إلى دروس', ask: false, material: true }
  ];
  function assistKinds(inLesson) { return ASSIST.filter(function (a) { return inLesson ? a.kind !== 'from_material' : !a.lesson; }); }
  function assistErrors(kind, instruction, material, lessonId) {
    var a = ASSIST.filter(function (x) { return x.kind === kind; })[0];
    if (!a) return ['اختر ما تريده من المساعد'];
    if (a.lesson && !lessonId) return ['اختر درسًا أولًا'];
    if (a.ask && !str(instruction).trim()) return ['اكتب سؤالك'];
    if (a.material && str(material).trim().length < 80) return ['الصق مادة من ٨٠ حرفًا على الأقل'];
    return [];
  }
  function assistBody(kind, instruction, material, lessonId) {
    var a = ASSIST.filter(function (x) { return x.kind === kind; })[0] || {};
    var b = { instruction: str(instruction).trim() || a.text || '', kind: kind };
    if (a.lesson && lessonId) b.lesson_id = lessonId;
    if (a.material) b.material = str(material).trim();
    return b;
  }
  // يطبّق مسودة المساعد على مسودة الدرس (بلا حفظ). choice: رقم العنوان المختار.
  function applyDraft(lessonKind, draftLesson, kind, res, choice) {
    var d = clone(draftLesson), dr = (res && res.draft) || {};
    if (kind === 'activity_decision' && dr.block) { d.blocks = (d.blocks || []).concat([dr.block]); return { ok: true, lesson: d }; }
    if (kind === 'shorter_title' && Array.isArray(dr.titles) && dr.titles[choice || 0]) { d.title = str(dr.titles[choice || 0]); return { ok: true, lesson: d }; }
    if (kind === 'video_script' && typeof dr.transcript === 'string') {
      if (lessonKind === 'recorded') d.transcript = dr.transcript;
      else d.blocks = (d.blocks || []).concat([{ type: 'text', md: dr.transcript }]);
      return { ok: true, lesson: d };
    }
    return { ok: false, lesson: d };
  }

  // ------------------------------------------------------------------ القائمة والمراجعة
  function gapsLine(course) {
    var g = (course && course.gaps) || [];
    return g.length ? 'ينقصها: ' + g.join('، ') : 'جاهزة';
  }
  function c2Index(list) {
    var by = {};
    (list || []).forEach(function (c) { if (c && c.id) by[c.id] = c; if (c && c.slug) by[c.slug] = c; });
    return by;
  }
  // صف القائمة: [حالة المحرّر · الأنواع · عدد الدروس · الملاحظات المفتوحة]
  var KIND_AR = { interactive: 'تفاعلي', recorded: 'مسجّل', live: 'مباشر' };
  function c2Bits(c) {
    if (!c) return null;
    var kinds = (c.kinds || []).map(function (k) { return KIND_AR[k] || k; });
    return { status: str(c.status_ar), kinds: kinds, lessons: Number(c.lessons_count) || 0, open: Number(c.open_notes) || 0 };
  }
  function c2Line(c) {
    var b = c2Bits(c);
    if (!b) return '';
    var p = [];
    if (b.kinds.length) p.push(b.kinds.join(' · '));
    p.push(arN(b.lessons) + ' ' + (b.lessons === 1 ? 'درس' : (b.lessons === 2 ? 'درسان' : (b.lessons >= 3 && b.lessons <= 10 ? 'دروس' : 'درسًا'))));
    if (b.open) p.push(arN(b.open) + (b.open === 1 ? ' ملاحظة مفتوحة' : ' ملاحظات مفتوحة'));
    return p.join(' · ');
  }
  // الدورات التي في المحرّر فقط (لا مقابل لها في لوحة المنصّة)
  function c2Extras(c2list, boardRows) {
    var by = c2Index(boardRows);
    return (c2list || []).filter(function (c) { return c && c.id && !by[c.id] && !(c.slug && by[c.slug]); });
  }
  function returnBody(rows) {
    var notes = [];
    (rows || []).forEach(function (r) {
      var t = str(r.text).trim();
      if (r.on && t) notes.push({ target_kind: r.kind, target_id: r.kind === 'course' ? '' : str(r.id), text: t.slice(0, 600) });
    });
    return { notes: notes };
  }
  function returnIssues(rows) {
    var on = (rows || []).filter(function (r) { return r.on; });
    if (!on.length) return ['اختر هدفًا واحدًا على الأقل'];
    var out = [];
    on.forEach(function (r) { if (!str(r.text).trim()) out.push('اكتب ملاحظة «' + str(r.label) + '»'); if (str(r.text).length > 600) out.push('ملاحظة «' + str(r.label) + '» أطول من ٦٠٠ حرف'); });
    return out;
  }
  function idemKey(uuid) {
    var u = typeof uuid === 'function' ? uuid() : '';
    if (!u) { u = ''; for (var i = 0; i < 32; i++) u += Math.floor(Math.random() * 16).toString(16); }
    return 'c-' + String(u).replace(/[^A-Za-z0-9]/g, '').slice(0, 40);
  }
  function coverIssue(url) {
    url = str(url).trim();
    return url && !/^https:\/\/\S+$/.test(url) ? 'رابط الغلاف يبدأ بـ https://' : '';
  }
  function dataBody(d) {
    var out = { title: str(d.title).trim(), subtitle: str(d.subtitle).trim(), description: str(d.description).trim(), cover: str(d.cover).trim(), level: str(d.level), outcomes: linesToArr(Array.isArray(d.outcomes) ? d.outcomes.join('\n') : d.outcomes) };
    return out;
  }

  L.courses2 = {
    TYPES: TYPES, typeAr: typeAr, typeDef: typeDef, blankBlock: blankBlock,
    blocksAdd: blocksAdd, blocksMove: blocksMove, blocksDelete: blocksDelete, setIn: setIn, rowAdd: rowAdd, rowDelete: rowDelete,
    linesToArr: linesToArr, arrToLines: arrToLines, blockHead: blockHead, parseBlockJson: parseBlockJson, blocksIssues: blocksIssues,
    parseT: parseT, fmtT: fmtT, hasContent: hasContent, videoBody: videoBody, lessonBody: lessonBody, lessonIssues: lessonIssues, draftFrom: draftFrom,
    structFrom: structFrom, structureDiff: structureDiff, structureErrors: structureErrors, structureBody: structureBody,
    mergeDraftIntoStructure: mergeDraftIntoStructure, draftLessons: draftLessons, pairNewLessons: pairNewLessons,
    CHUNK: CHUNK, tusPlan: tusPlan, tusMetadata: tusMetadata, tusUpload: tusUpload,
    ASSIST: ASSIST, assistKinds: assistKinds, assistErrors: assistErrors, assistBody: assistBody, applyDraft: applyDraft,
    gapsLine: gapsLine, c2Index: c2Index, c2Bits: c2Bits, c2Line: c2Line, c2Extras: c2Extras, returnBody: returnBody, returnIssues: returnIssues,
    idemKey: idemKey, coverIssue: coverIssue, dataBody: dataBody, KIND_AR: KIND_AR
  };
  if (typeof module !== 'undefined' && module.exports && module.exports !== L) module.exports.courses2 = L.courses2;
})(typeof window !== 'undefined' ? window : (typeof globalThis !== 'undefined' ? globalThis : this));
// ===== /courses2 =====

// ===== brain2 =====
// «العقل» الجولة ٢ (SPEC docs/v2/brain2 §4.1): دوال نقية فقط — حقائق البطاقة المسموحة للرأي، وتزيين البطاقة برأي العقل أو بعلامة الجملة الثابتة،
// وبطاقة اقتراح العقل. ⛔ لا DOM ولا شبكة ولا ساعة خفية (`now` يُمرَّر). الاسم والبريد والهاتف لا يخرجون من هنا أبدًا.
(function (root) {
  'use strict';
  var L = root.V2L;
  if (!L) return;
  var UT = L.util;
  var CLIENT = 'صاحب الطلب';

  var MONEY = { payout: 1, manual_payment: 1, stuck_payment: 1, unactivated: 1, legacy: 1, file_attention: 1, dispute: 1 };
  var DECIDE = { trainer: 1, join: 1, pending_user: 1, book_offer: 1, book: 1, creative: 1, topic: 1, program: 1 };
  var INFO = { review: 1, lead: 1, message: 1, open_message: 1, course: 1, live: 1, verify: 1, founding: 1, other: 1 };
  var RECOMMEND = { decide: ['approve', 'reject', 'open'], info: ['open', 'wait'] };
  // المفاتيح المسموحة (SPEC §3.2): مشتركة + لكل نوع. الخادم يعيد التنقية بنفس القائمة.
  var COMMON_KEYS = ['tag', 'age', 'sub', 'warn', 'reason', 'static_line', 'facts', 'money_text'];
  var KIND_KEYS = {
    dispute: ['objection', 'expert_reply', 'hours_held'],
    trainer: ['headline', 'specialty', 'years', 'attachments'],
    payout: ['method', 'dispute_check', 'fx_alert'],
    book_offer: ['type', 'suggested_price', 'price_note'],
    join: ['service', 'licensed', 'licence_missing'],
    lead: ['body', 'topic'],
    message: ['body', 'topic']
  };
  var MAXLEN = { sub: 160, warn: 120, reason: 140, static_line: 200, objection: 300, expert_reply: 300, body: 400, headline: 160, price_note: 120 };

  function s_(v) { return typeof v === 'string' ? v.trim() : (typeof v === 'number' && isFinite(v) ? String(v) : ''); }
  function bytes(o) { try { return unescape(encodeURIComponent(JSON.stringify(o))).length; } catch (e) { return 0; } }

  // نص آمن: اسم العميل ⇒ «صاحب الطلب» · لا بريد · لا هاتف (٧ أرقام فأكثر متتالية) · لا «@».
  function scrub(v, names, max) {
    var s = s_(v);
    if (!s) return '';
    (names || []).forEach(function (n) { if (n && n.length >= 2) s = s.split(n).join(CLIENT); });
    s = s.replace(/[^\s@<>()،؛,;]+@[^\s@<>()،؛,;]+/g, ' ').replace(/@/g, ' ');
    s = s.replace(/\+?[0-9٠-٩](?:[\s\-().]*[0-9٠-٩])+/g, function (m) { return (m.match(/[0-9٠-٩]/g) || []).length >= 7 ? ' ' : m; });
    s = s.replace(/https?:\/\/\S+/g, ' ').replace(/\s+/g, ' ').replace(/(\s·){2,}/g, ' ·').replace(/^[\s·—-]+|[\s·—-]+$/g, '');
    if (max && s.length > max) s = s.slice(0, max).replace(/\s+\S*$/, '') + '…';
    return s;
  }
  function namesOf(card) {
    var r = (card && card.row) || {}, f = r.ef || {}, c = r.cons || {}, sk = r.stuck || {}, out = [];
    [r.who, f.client_first_name, c.client_first_name, f.client_name, c.client_name, sk.name].forEach(function (n) {
      n = s_(n);
      if (n && n.length >= 2 && n !== CLIENT && n !== 'عميل' && n !== '—' && out.indexOf(n) < 0) out.push(n);
    });
    return out;
  }
  // العمر بحبيبة اليوم حتى لا يتغيّر مفتاح الرأي كل ساعة (كل تغيّر في الحقائق = رأي جديد).
  function ageFact(t) {
    t = s_(t);
    if (!t) return '';
    return /(يوم|أيام|يومين|يومًا)/.test(t) ? t : 'أقل من يوم';
  }
  function heldFact(card, now) {
    var ts = Number(card && card.ts);
    if (!now || !isFinite(ts)) return '';
    var days = Math.floor(Math.max(0, now - ts) / 86400e3);
    return days >= 1 ? 'أكثر من ' + UT.U(days, ['يوم واحد', 'يومين', 'أيام', 'يومًا']) : 'أقل من يوم';
  }
  function moneyOf(card) {
    var r = (card && card.row) || {};
    switch (card.kind) {
      case 'payout': return UT.moneyText(r.raw && r.raw.amount != null ? r.raw.amount : r.amount, r.currency || 'EGP');
      case 'manual_payment': return UT.moneyText(r.amount, r.currency || 'EGP');
      case 'stuck_payment': return s_((r.stuck || {}).amountText);
      case 'book_offer': return s_((r.offerRow || {}).suggestedText);
      case 'dispute': case 'legacy': case 'unactivated': case 'file_attention': return s_(r.amountLabel);
      default: return '';
    }
  }

  // v2bFacts(card, now?) ⇒ {kind, card_id, facts} أو null لما لا يحمل رأيًا (ملفات الخبراء تبقى بمرشّحها القائم).
  function v2bFacts(card, now) {
    if (!card || !card.kind || !card.id) return null;
    var kind = card.kind;
    if (!MONEY[kind] && !DECIDE[kind] && !INFO[kind]) return null;
    var r = card.row || {}, f = r.ef || {}, c = r.cons || {}, names = namesOf(card), out = {};
    function put(k, v, max) {
      if (typeof v === 'boolean') { out[k] = v; return; }
      if (typeof v === 'number') { if (isFinite(v) && v > 0) out[k] = v; return; }
      var t = scrub(v, names, max || MAXLEN[k] || 120);
      if (t) out[k] = t;
    }
    put('tag', card.tag, 60);
    var age = ageFact(card.ageText); if (age) out.age = age;
    put('sub', card.sub); put('warn', card.warn); put('reason', card.reason); put('static_line', card.brain);
    var fl = (Array.isArray(card.facts) ? card.facts : []).map(function (x) {
      var v = x && scrub(s_(x.k) + ': ' + s_(x.v), names, 70);
      return x && x.k && x.v ? v : '';
    }).filter(Boolean).slice(0, 4);
    if (fl.length) out.facts = fl;
    var mt = moneyOf(card); if (mt) out.money_text = mt;
    switch (kind) {
      case 'dispute': {
        var d = f.dispute || {};
        put('objection', r.note || r.sub2);
        put('expert_reply', d.expert_reply || d.expert_note || f.expert_reply || c.expert_reply);
        var h = heldFact(card, now); if (h) out.hours_held = h;
        break;
      }
      case 'trainer': put('headline', r.trHeadline); put('specialty', r.trSpec, 80); put('years', s_(r.trYears), 30); put('attachments', Number(r.trAttach) || 0); break;
      case 'payout': {
        put('method', s_(r.raw && r.raw.method) || s_(r.dest), 80);
        out.dispute_check = /نزاع مفتوح/.test(card.warn || '') ? 'يوجد نزاع مفتوح على صاحب الطلب' : (/^روجعت النزاعات/.test(card.reason || '') ? 'لا نزاع مفتوحًا على صاحب الطلب كخبير' : 'لم يكتمل فحص النزاعات');
        if (r.fx_alert) out.fx_alert = 'العملة ليست الجنيه';
        break;
      }
      case 'book_offer': { var of = r.offerRow || {}; put('type', of.typeText, 40); put('suggested_price', of.suggestedText, 60); put('price_note', of.priceNote); break; }
      case 'join': put('service', r.serviceLabel || r.from, 80); out.licensed = !!r.licensed; out.licence_missing = !!r.licenceMissing; break;
      case 'lead': case 'message': put('body', r.body || r.note); put('topic', r.topic, 80); break;
    }
    // الأمان الأخير: لا مفتاح خارج القائمة، والحجم تحت الحد (الخادم يرفض فوق ٣ كيلوبايت).
    var allowed = COMMON_KEYS.concat(KIND_KEYS[kind] || []);
    Object.keys(out).forEach(function (k) { if (allowed.indexOf(k) < 0) delete out[k]; });
    var guard = 0;
    while (bytes(out) > 2400 && guard++ < 40) {
      var big = Object.keys(out).filter(function (k) { return typeof out[k] === 'string'; }).sort(function (a, b) { return out[b].length - out[a].length; })[0];
      if (!big) break;
      out[big] = out[big].length > 40 ? out[big].slice(0, Math.floor(out[big].length / 2)) + '…' : '';
      if (!out[big]) delete out[big];
    }
    return { kind: kind, card_id: card.id, facts: out };
  }

  var MARK = {
    failed: 'جملة ثابتة: تعذّرت كتابة رأي العقل الآن',
    cap: 'جملة ثابتة: بلغ العقل حدّ كتابته اليوم',
    off: 'جملة ثابتة: رأي العقل متوقّف من القواعد',
    busy: 'جملة ثابتة: العقل مشغول بكتابة أخرى الآن',
    loading: 'يكتب العقل رأيه…'
  };
  function isReject(a) { return !!a && (a.do === 'offer_reject' || a.do === 'payout_reject' || a.do === 'pay_reject' || (a.do === 'decide' && a.action === 'reject')); }
  function isOpenAct(a) { return !!a && (a.do === 'open' || a.do === 'goto' || a.do === 'section'); }
  function recGroup(kind) { return DECIDE[kind] ? 'decide' : (INFO[kind] ? 'info' : ''); }
  // يبدّل الزر الأساسي بالثانوي القائم فقط لو الثانوي هو الفعل المطلوب. لا فعل جديد يُخترع هنا أبدًا.
  function remap(c, rec) {
    var p = c.primary, s = c.secondary;
    var pred = rec === 'reject' ? isReject : (rec === 'open' ? isOpenAct : null);
    if (!pred || !p || !s || !p.act || !s.act || pred(p.act) || !pred(s.act) || (p.money || s.money)) return false;
    c.primary = s; c.secondary = p; c.remapped = rec;
    return true;
  }

  // v2bDecorate(card, entry, now) ⇒ نسخة من البطاقة. entry = {state:'none'|'loading'|'ready'|'off'|'cap'|'busy'|'failed', item, remap?}
  function v2bDecorate(card, entry, now) {
    var c = Object.assign({}, card || {});
    c.src = { text: '', tone: '' };
    if (!card || !(MONEY[card.kind] || DECIDE[card.kind] || INFO[card.kind])) return c;   // نوع بلا رأي (ملفات الخبراء · نوع غير معروف): كما هي
    entry = entry || { state: 'none' };
    var st = entry.state, it = entry.item, b = it && it.body && typeof it.body === 'object' ? it.body : null;
    if (st === 'ready' && b && s_(b.text)) {
      c.brain = s_(b.text);
      c.brainHead = 'رأي العقل';
      if (s_(b.why)) c.reason = s_(b.why);
      var ago = UT.agoText(it.created_at, now);
      c.src = { text: 'كتبه العقل ' + (ago || 'الآن'), tone: 'ai' };
      if (!MONEY[card.kind] && entry.remap !== false && c.primary && c.secondary) {
        var g = recGroup(card.kind), rec = s_(b.recommend);
        if (g && RECOMMEND[g].indexOf(rec) > -1 && (rec === 'reject' || rec === 'open')) remap(c, rec);
      }
      return c;
    }
    if (st === 'loading') c.src = { text: MARK.loading, tone: 'wait' };
    else if (MARK[st] && st !== 'loading') c.src = { text: MARK[st], tone: 'static' };
    return c;
  }

  var SEC_IMG = { home: 'brain', files: 'files', disputes: 'disputes', courses: 'courses', market: 'market', books: 'books', people: 'people', money: 'money',
                  content: 'content', marketing: 'marketing', reports: 'reports', brain: 'brain', company: 'company' };
  var FIELD_LABEL = { title: 'العنوان', body: 'النص' };
  // v2bItemCard(item, now) ⇒ بطاقة قرار لاقتراح العقل (مسودة: اعتمد/عدّل/ارفض · ملاحظة: احتفظ بها/احذفها).
  function v2bItemCard(item, now) {
    if (!item || !item.id) return null;
    var b = item.body && typeof item.body === 'object' ? item.body : {};
    var note = item.kind === 'note';
    var t = Date.parse(item.created_at || '');
    var fields = [];
    // اقتراحات الموقع تحمل قائمة تعديلات كاملة (القديم ⇒ الجديد + السبب): تُعرض كلها قبل الاعتماد، ولا يُعدَّل «نصها» هنا.
    var edits = [];
    if (Array.isArray(b.edits)) b.edits.forEach(function (e) {
      if (e && typeof e === 'object' && s_(e.old) && s_(e.new)) edits.push({ path: s_(e.path), old: s_(e.old), new: s_(e.new), why: s_(e.why) });
    });
    if (b.fields && typeof b.fields === 'object') Object.keys(b.fields).forEach(function (k) { if (FIELD_LABEL[k] && s_(b.fields[k])) fields.push({ k: FIELD_LABEL[k], v: s_(b.fields[k]) }); });
    var card = {
      id: 'brain_item|' + item.id, kind: 'brain_item', group: 900, tag: s_(item.tag) || (note ? 'ملاحظة العقل' : 'اقتراح العقل'),
      title: s_(item.target_label) || (note ? 'ملاحظة' : 'اقتراح'), sub: '', brain: s_(b.text), brainHead: 'ما كتبه العقل', reason: '', warn: '',
      ageText: isNaN(t) ? '' : UT.agoText(t, now), ts: isNaN(t) ? Infinity : t,
      primary: { label: note ? 'احتفظ بها' : (s_(item.approve_label) || 'اعتمد'), act: { do: 'brain_approve', id: item.id } },
      secondary: { label: note ? 'احذفها' : 'ارفض', act: { do: 'brain_reject', id: item.id } },
      edit: (note || edits.length) ? null : { label: 'عدّل', act: { do: 'brain_edit', id: item.id } },
      edits: edits,
      open: { do: 'open' }, link: null, facts: [], fields: fields, img: SEC_IMG[item.section] || 'brain',
      brainItem: item, src: { text: '', tone: '' }, row: { apiKind: 'brain_item', item: item }
    };
    return card;
  }

  L.v2bFacts = v2bFacts;
  L.v2bDecorate = v2bDecorate;
  L.v2bItemCard = v2bItemCard;
  L.v2bMarks = MARK;
  if (typeof module !== 'undefined' && module.exports) { module.exports.v2bFacts = v2bFacts; module.exports.v2bDecorate = v2bDecorate; module.exports.v2bItemCard = v2bItemCard; }
})(typeof window !== 'undefined' ? window : (typeof globalThis !== 'undefined' ? globalThis : this));
// ===== /brain2 =====

