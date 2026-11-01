/* ============================================================================
 * v2s/saha_diwan.js — لوحة «الديوان» (تبويب في قسم «المحتوى») على المحرّك المشترك `V2S_SAHA_KIT.board` من saha.js:
 *   الأعمال (اعتماد · رفض بسبب · تمييز · إخفاء · قفل التعليقات) · التعليقات (إخفاء) · التحديات (نموذج كامل · لجنة · جوائز · ورقة الفائزين) · التقرير.
 * ⛔ لا منطق عمل هنا: كل التحقق والنصوص من `V2L.v2sSaha`. ولا طلب شبكة إلا `/api/v2/diwan/*` (بروكسيات أدمن).
 * ⛔ كل كتابة تمرّ على ورقة مراجعة ثم تأكيد وتذهب بـ`confirmed: true`. مفيش confirm()/alert()/prompt() ولا حفظ في المتصفح.
 * ⛔ التقرير: الرقم الغايب «لا رقم بعد» لا صفر. المصدر الواقع «غير متاح بعد» + «أعد المحاولة».
 * ========================================================================== */
(function () {
  'use strict';
  if (typeof window === 'undefined' || typeof document === 'undefined') return;
  var L = window.V2L, Kit = window.V2S_SAHA_KIT;
  if (!L || !L.v2sSaha || !Kit || !Kit.board) return;
  var X = L.v2sSaha, U = L.util, ar = U.ar;
  var esc = Kit.esc, q1 = Kit.q1, qa = Kit.qa, fld = Kit.fld, inp = Kit.inp, txt = Kit.txt, sel = Kit.sel, chk = Kit.chk;

  var P = {
    works: function (st) { return '/v2/diwan/works?status=' + st; },
    comments: function (st) { return '/v2/diwan/comments?status=' + st; },
    ch: '/v2/diwan/challenges',
    report: function (d) { return '/v2/diwan/report?days=' + d; },
    entries: function (cid) { return '/v2/diwan/works?status=published&challenge_id=' + encodeURIComponent(cid); }
  };
  var HUB = [P.works('pending_review'), P.comments('visible'), P.ch, P.report(30)];
  var B = null;
  var now = function () { return Date.now(); };
  function row(rows, id) { for (var i = 0; i < (rows || []).length; i++) if (rows[i].id === id) return rows[i]; return null; }
  function worksView(st) { var d = B.data(P.works(st)); return d ? X.works(d, now()) : null; }
  function commView(st) { var d = B.data(P.comments(st)); return d ? X.comments(d, now()) : null; }
  function chView() { var d = B.data(P.ch); return d ? X.challenges(d, now()) : null; }
  function repView(days) { var d = B.data(P.report(days)); return d ? X.report(d) : null; }

  // —— المربّعات
  function tiles() {
    var w = Kit.count(B, P.works('pending_review'), function () { var v = worksView('pending_review'); return v ? { n: ar(v.rows.length), note: v.rows.length ? 'عمل ينتظر قرارك' : 'لا أعمال تنتظر', hot: v.rows.length > 0 } : null; });
    var c = Kit.count(B, P.comments('visible'), function () { var v = commView('visible'); return v ? { n: ar(v.rows.length), note: v.rows.length ? 'تعليق ظاهر للقرّاء' : 'لا تعليقات بعد' } : null; });
    var h = Kit.count(B, P.ch, function () { var v = chView(); return v ? { n: ar(v.open), note: v.open ? 'تحدٍّ مفتوح الآن' : 'لا تحدّيات مفتوحة', hot: v.open > 0 } : null; });
    var r = Kit.count(B, P.report(30), function () { var v = repView(30); var t = X.reportTile(v); return { n: t.n, note: t.sub, off: t.off }; });
    return [
      Object.assign({ sub: 'works', name: 'الأعمال', img: 'books' }, w), Object.assign({ sub: 'comments', name: 'التعليقات', img: 'disputes' }, c),
      Object.assign({ sub: 'challenges', name: 'التحديات', img: 'marketing' }, h), Object.assign({ sub: 'report', name: 'التقرير', img: 'reports' }, r)
    ];
  }

  // —— ١ · الأعمال
  function workCard(r) {
    var acts = X.workActions(r).map(function (a) { return '<button type="button" class="' + (a[2] === 1 ? 'ep-b1' : 'ep-b2') + '" data-a="work" data-w="' + a[0] + '" data-id="' + esc(r.id) + '">' + esc(a[1]) + '</button>'; }).join('');
    var counts = [r.likes != null ? U.U(r.likes, ['إعجاب واحد', 'إعجابان', 'إعجابات', 'إعجابًا']) : '', r.comments != null ? U.U(r.comments, ['تعليق واحد', 'تعليقان', 'تعليقات', 'تعليقًا']) : ''].filter(Boolean).join('، ');
    return '<li class="sh-card big" data-id="' + esc(r.id) + '"><div class="sh-ch"><h3>' + esc(r.title) + '</h3><span class="sh-pills">' + Kit.pill(r.statusText, r.status === 'pending_review' ? 'gold' : r.status === 'rejected' ? 'mute' : '')
      + (r.featured ? Kit.pill('مميَّز', 'gold') : '') + (r.locked ? Kit.pill('التعليقات مقفولة', 'mute') : '') + '</span></div>'
      + '<p class="sh-meta"><span>' + esc(r.kindText) + '</span><span>' + esc(r.creator || 'بلا اسم') + '</span>' + (r.email && r.email !== r.creator ? Kit.who(r.email) : '') + (r.when ? '<span>' + esc(r.when) + '</span>' : '') + '</p>'
      + (r.body ? '<p class="sh-body">' + esc(r.body) + '</p>' : '') + (r.about ? '<p class="sh-sub">' + esc(r.about) + '</p>' : '')
      + (r.ai ? '<p class="sh-fine">أعلن صاحب العمل أنه استعان بأداة ذكاء في إعداده.</p>' : '')
      + (r.rejectReason ? '<p class="sh-fine">سبب الرفض: ' + esc(r.rejectReason) + '</p>' : '')
      + '<p class="sh-meta">' + (Kit.link(r.mediaUrl, 'فتح العمل') || '') + (counts ? '<span>' + esc(counts) + '</span>' : '') + (r.featuredUntil ? '<span>التمييز حتى ' + esc(X.dayText(r.featuredUntil)) + '</span>' : '') + '</p>'
      + (acts ? '<div class="sh-acts">' + acts + '</div>' : '') + '</li>';
  }
  function screenWorks() {
    var st = B.f('wSt', 'pending_review'), p = P.works(st);
    B.need(p);
    var d = worksView(st), body;
    if (!d) body = B.stateBlock(p, 'الأعمال');
    else if (!d.rows.length) body = B.empty(st === 'pending_review' ? 'لا أعمال تنتظر قرارك' : 'لا أعمال هنا', st === 'pending_review' ? 'حين يرسل عضو عملًا يظهر هنا لتقرر فيه' : '');
    else body = '<p class="sh-count">' + esc(d.countText) + '</p><ul class="sh-cards big">' + d.rows.map(workCard).join('') + '</ul>';
    return { title: 'الأعمال', sub: d ? d.countText : '', img: 'books', html: B.chips('wSt', X.WORK_CHIPS, st) + body };
  }
  function workFlow(r, kind) {
    var base = X.workAction(kind, r, { reason: 'x' });
    var form = null;
    if (kind === 'reject') {
      form = function (v) {
        v = v || {};
        return fld('سبب الرفض', txt('reason', v.reason, 3, 140), 'reason', 'حتى ١٤٠ حرفًا') + fld('ملاحظة لصاحب العمل (اختياري)', txt('note', v.note, 4, 1000), 'note');
      };
    } else if (kind === 'feature') {
      form = function (v) { return fld('نهاية التمييز (اختياري)', inp('until', (v || {}).until, { type: 'date', ltr: true }), 'until', 'اتركها فارغة لتمييز بلا تاريخ نهاية'); };
    }
    var titles = { approve: 'اعتماد العمل', reject: 'رفض العمل', feature: 'تمييز العمل', unfeature: 'إلغاء تمييز العمل', hide: 'إخفاء العمل', show: 'إظهار العمل', lock: 'قفل التعليقات', unlock: 'فتح التعليقات' };
    B.flow({ title: titles[kind], form: form, init: { reason: '', note: '', until: '' }, nextLabel: 'راجع ثم أكِّد',
      check: function (v) { var x = X.workAction(kind, r, v); if (x.ok && !x.lines) x.lines = []; return x; },
      send: function (res) {
        var path = '/v2/diwan/works/' + encodeURIComponent(r.id);
        return res.op === 'decide' ? B.api(path + '/decide', Object.assign({}, res.body, { confirmed: true })) : B.api(path, Object.assign({}, res.body, { confirmed: true }), 'PUT');
      },
      done: function (out, res) { return res.done || base.done; } });
  }

  // —— ٢ · التعليقات
  function screenComments() {
    var st = B.f('cSt', 'visible'), p = P.comments(st);
    B.need(p);
    var d = commView(st), body;
    if (!d) body = B.stateBlock(p, 'التعليقات');
    else if (!d.rows.length) body = B.empty('لا تعليقات هنا', 'تظهر هنا التعليقات التي يكتبها القرّاء على الأعمال');
    else body = '<p class="sh-count">' + esc(d.countText) + '</p>' + B.list(d.rows, [
      { h: 'التعليق', c: function (r) { return '<span class="sh-body">' + esc(r.body.length > 280 ? r.body.slice(0, 280) + '…' : r.body) + '</span>'; } },
      { h: 'صاحبه', c: function (r) { return esc(r.name === r.email ? '' : r.name) + Kit.who(r.email); } },
      { h: 'العمل', c: function (r) { return esc(r.work); } },
      { h: 'الحالة', c: function (r) { return Kit.pill(r.statusText, r.hidden ? 'mute' : '') + (r.when ? '<span class="sh-sub">' + esc(r.when) + '</span>' : ''); } }
    ], function (r) { return r.hidden ? '' : '<button type="button" class="ep-b2" data-a="chide" data-id="' + esc(r.id) + '">أخفِ التعليق</button>'; });
    return { title: 'التعليقات', sub: d ? d.countText : '', img: 'disputes', html: B.chips('cSt', X.COMMENT_CHIPS, st) + body };
  }
  function commentFlow(r) {
    B.flow({ title: 'إخفاء التعليق', check: function () {
        return { ok: true, lead: 'سيُخفى هذا التعليق عن القرّاء:', goLabel: 'أخفِ التعليق', lines: [{ label: 'التعليق', to: r.body.length > 160 ? r.body.slice(0, 160) + '…' : r.body }, { label: 'صاحبه', to: r.email || r.name }] };
      },
      send: function () { return B.api('/v2/diwan/comments/' + encodeURIComponent(r.id) + '/hide', { confirmed: true }); }, done: function () { return 'أُخفي التعليق'; } });
  }

  // —— ٣ · التحديات
  function screenChallenges() {
    B.need(P.ch);
    var st = B.f('hSt', 'all'), d = chView(), body;
    if (!d) body = B.stateBlock(P.ch, 'التحديات');
    else {
      var rows = d.rows.filter(function (r) { return st === 'all' || r.status === st; });
      body = !d.rows.length ? B.empty('لا تحدّيات بعد', 'أنشئ أول تحدٍّ من الزرّ فوق')
        : !rows.length ? B.empty('لا تحدّيات بهذه الحالة', 'غيّر الحالة أو اختر «الكل»')
        : '<p class="sh-count">' + esc(d.countText) + '</p>' + B.list(rows, [
          { h: 'التحدّي', c: function (r) { return '<b class="sh-t">' + esc(r.title) + '</b>' + (r.kindsText ? '<span class="sh-sub">' + esc(r.kindsText) + '</span>' : ''); } },
          { h: 'الحالة', c: function (r) { return Kit.pill(r.statusText, r.status === 'open' ? 'green' : r.status === 'draft' ? 'gold' : ''); } },
          { h: 'المواعيد', c: function (r) { return esc(r.datesText); } },
          { h: 'المشاركات', c: function (r) { return r.entries == null ? '' : esc(U.U(r.entries, ['مشاركة واحدة', 'مشاركتان', 'مشاركات', 'مشاركة'])); } }
        ], function (r) {
          return '<button type="button" class="ep-b2" data-a="chedit" data-id="' + esc(r.id) + '">عدّل</button>'
            + (r.canWinners ? '<button type="button" class="ep-b1" data-a="chwin" data-id="' + esc(r.id) + '">اختر الفائزين</button>' : '');
        });
    }
    return { title: 'التحديات', sub: d ? d.countText : '', img: 'marketing',
      html: '<div class="sh-top"><button type="button" class="ep-b1" data-a="chnew">تحدٍّ جديد</button></div>' + B.chips('hSt', X.CH_CHIPS, st) + body };
  }
  function prizeRow(i, p, last) {
    return '<div class="sh-rowbox" data-row="prize" data-i="' + i + '"><div class="sh-rowgrid">'
      + fld('نوع الجائزة', sel('prize_type_' + i, p.type, X.PRIZE_TYPES), 'prize_type_' + i) + fld('اسم الجائزة', inp('prize_label_' + i, p.label, { max: 80 }), 'prize_label_' + i)
      + fld('المرجع (اختياري)', inp('prize_ref_' + i, p.ref, { max: 120, ltr: true }), 'prize_ref_' + i)
      + fld('المركز', sel('prize_place_' + i, p.place, [['1', 'الأول'], ['2', 'الثاني'], ['3', 'الثالث']], 'بلا مركز'), 'prize_place_' + i) + '</div>'
      + '<small class="ferr" data-e="prize' + i + '" role="alert"></small><button type="button" class="ep-bs" data-rm="prize" data-i="' + i + '">احذف الجائزة</button></div>';
  }
  function juryRow(i, j) {
    return '<div class="sh-rowbox" data-row="jury" data-i="' + i + '"><div class="sh-rowgrid two">'
      + fld('اسم المحكّم', inp('jury_name_' + i, j.name, { max: 80 }), 'jury_name_' + i) + fld('صفته', inp('jury_title_' + i, j.title, { max: 80 }), 'jury_title_' + i) + '</div>'
      + '<small class="ferr" data-e="jury' + i + '" role="alert"></small><button type="button" class="ep-bs" data-rm="jury" data-i="' + i + '">احذف المحكّم</button></div>';
  }
  function chFormHtml(create, results) {
    return function (v) {
      v = v || {};
      var kinds = v.kinds || [];
      var statusOpts = results ? [['results', 'أُعلنت النتائج']] : create ? [['draft', 'مسودة'], ['open', 'مفتوح للمشاركة']] : [['draft', 'مسودة'], ['open', 'مفتوح للمشاركة'], ['closed', 'مغلق']];
      return fld('عنوان التحدّي', inp('title', v.title, { max: 120 }), 'title') + fld('وصف التحدّي', txt('brief', v.brief, 4, 600), 'brief')
        + '<fieldset class="sh-scope"><legend>أنواع الأعمال المسموحة</legend><div class="sh-kinds">' + X.WORK_KINDS.map(function (k) {
          return '<label class="sh-chk"><input type="checkbox" data-fm="kinds" value="' + k[0] + '"' + (kinds.indexOf(k[0]) > -1 ? ' checked' : '') + '><span>' + esc(k[1]) + '</span></label>';
        }).join('') + '</div><small class="ferr" data-e="kinds" role="alert"></small></fieldset>'
        + fld('سقف الكلمات (اختياري)', inp('word_cap', v.word_cap, { mode: 'numeric', max: 6 }), 'word_cap')
        + '<div class="sh-rowgrid">' + fld('يبدأ في', inp('opens_at', v.opens_at, { type: 'date', ltr: true }), 'opens_at') + fld('يُغلق في', inp('closes_at', v.closes_at, { type: 'date', ltr: true }), 'closes_at')
        + fld('تُعلن النتائج في (اختياري)', inp('results_at', v.results_at, { type: 'date', ltr: true }), 'results_at') + '</div>'
        + fld('الحالة', sel('status', v.status, statusOpts), 'status')
        + '<fieldset class="sh-scope"><legend>الجوائز (حتى ٦)</legend>' + (v.prizes || []).map(function (p, i) { return prizeRow(i, p); }).join('')
        + '<small class="ferr" data-e="prizes" role="alert"></small>' + ((v.prizes || []).length < 6 ? '<button type="button" class="ep-b2" data-add="prize">أضف جائزة</button>' : '') + '</fieldset>'
        + '<fieldset class="sh-scope"><legend>لجنة التحكيم (ثلاثة لفتح التحدّي)</legend>' + (v.jury || []).map(function (j, i) { return juryRow(i, j); }).join('')
        + '<small class="ferr" data-e="jury" role="alert"></small>' + ((v.jury || []).length < 6 ? '<button type="button" class="ep-b2" data-add="jury">أضف محكّمًا</button>' : '') + '</fieldset>'
        + '<details class="sh-more"><summary>الراعي والغلاف</summary>' + fld('اسم الراعي', inp('sponsor_name', v.sponsor_name, { max: 80 }), 'sponsor_name')
        + fld('رابط شعار الراعي', inp('sponsor_logo', v.sponsor_logo, { ltr: true, type: 'url', ph: 'https://' }), 'sponsor_logo')
        + fld('رابط الغلاف', inp('cover_url', v.cover_url, { ltr: true, type: 'url', ph: 'https://' }), 'cover_url') + '</details>';
    };
  }
  function chCollect(root) {
    var f = Kit.collect(root), prizes = [], jury = [];
    qa('[data-row="prize"]', root).forEach(function (el) {
      var i = el.getAttribute('data-i');
      prizes.push({ type: f['prize_type_' + i], label: f['prize_label_' + i], ref: f['prize_ref_' + i], place: f['prize_place_' + i] });
    });
    qa('[data-row="jury"]', root).forEach(function (el) {
      var i = el.getAttribute('data-i');
      jury.push({ name: f['jury_name_' + i], title: f['jury_title_' + i] });
    });
    return { title: f.title, brief: f.brief, kinds: f.kinds || [], word_cap: f.word_cap, opens_at: f.opens_at, closes_at: f.closes_at, results_at: f.results_at, status: f.status,
             prizes: prizes, jury: jury, sponsor_name: f.sponsor_name, sponsor_logo: f.sponsor_logo, cover_url: f.cover_url };
  }
  function challengeFlow(r) {
    var create = !r, init = X.challengeForm(r);
    if (create) { init.prizes = [{ type: 'certificate', label: '', ref: '', place: '1' }]; init.jury = [{ name: '', title: '' }, { name: '', title: '' }, { name: '', title: '' }]; init.kinds = ['story']; }
    B.flow({ title: create ? 'تحدٍّ جديد' : 'تعديل التحدّي', form: chFormHtml(create, !create && r.status === 'results'), init: init, collect: chCollect,
      check: function (v) { return X.challengeCheck(v, create ? 'create' : 'edit', r); }, nextLabel: 'راجع ثم احفظ', goLabel: 'احفظ التحدّي',
      hook: function (c) {
        qa('[data-add]', c.root).forEach(function (b) {
          b.onclick = function () {
            var v = chCollect(c.s), k = b.getAttribute('data-add');
            if (k === 'prize') v.prizes.push({ type: 'certificate', label: '', ref: '', place: '' }); else v.jury.push({ name: '', title: '' });
            c.redo(v);
          };
        });
        qa('[data-rm]', c.root).forEach(function (b) {
          b.onclick = function () {
            var v = chCollect(c.s), k = b.getAttribute('data-rm'), i = Number(b.getAttribute('data-i'));
            (k === 'prize' ? v.prizes : v.jury).splice(i, 1);
            c.redo(v);
          };
        });
      },
      send: function (res) {
        return create ? B.api('/v2/diwan/challenges', Object.assign({}, res.body, { confirmed: true })) : B.api('/v2/diwan/challenges/' + encodeURIComponent(r.id), Object.assign({}, res.body, { confirmed: true }), 'PUT');
      },
      done: function () { return create ? 'تم إنشاء التحدّي' : 'حُفظت تعديلات التحدّي'; } });
  }
  function winnersForm(entries) {
    var opts = entries.map(function (e) { return [e.id, e.title + (e.creator ? ' (' + e.creator + ')' : '')]; });
    return function (v) {
      v = v || {};
      var rows = v.rows || [];
      return [1, 2, 3].map(function (n) {
        var r = rows[n - 1] || {};
        return '<div class="sh-rowbox"><b class="sh-place">المركز ' + esc(X.PLACES[n]) + '</b>' + fld('العمل الفائز', sel('w_work_' + n, r.work_id, opts, n === 1 ? 'اختر العمل' : 'بلا فائز بهذا المركز'), 'w_work_' + n)
          + fld('سطر اللجنة', inp('w_line_' + n, r.jury_line, { max: 140 }), 'w_line_' + n, 'جملة قصيرة تُكتب على الشهادة وفي النتيجة') + '</div>';
      }).join('') + '<small class="ferr" data-e="winners" role="alert"></small>';
    };
  }
  function winnersFlow(ch) {
    B.setNote('جارٍ جلب الأعمال المشاركة…'); B.redraw();
    window.EP.api(P.entries(ch.id)).then(function (d) {
      B.setNote(''); B.redraw();
      var v = X.works(d, now());
      if (!v || !v.rows.length) { B.setNote('لا أعمال منشورة في هذا التحدّي بعد، فلا يمكن اختيار فائزين'); B.redraw(); return; }
      B.flow({ title: 'اختيار الفائزين', intro: 'اختر من فائز إلى ثلاثة، واكتب لكل فائز سطر اللجنة. المركز الأول أولًا.', form: winnersForm(v.rows), init: { rows: [{}, {}, {}] },
        collect: function (root) { var f = Kit.collect(root); return { rows: [1, 2, 3].map(function (n) { return { work_id: f['w_work_' + n], jury_line: f['w_line_' + n] }; }) }; },
        check: function (f) { var r = X.winnersCheck(f, v.rows); if (!r.ok) r.errors = {}; return r; }, nextLabel: 'راجع ثم أعلن', goLabel: 'أعلن النتيجة',
        send: function (res) { return B.api('/v2/diwan/challenges/' + encodeURIComponent(ch.id) + '/winners', Object.assign({}, res.body, { confirmed: true })); },
        done: function (out) { return X.winnersDone(out); } });
    }).catch(function (e) {
      B.setNote(X.writeError(e && e.status, e && e.data) === 'تعذّر تنفيذ العملية، حاول مرة أخرى' ? 'تعذّر جلب الأعمال المشاركة، حاول مرة أخرى' : X.writeError(e && e.status, e && e.data)); B.redraw();
    });
  }

  // —— ٤ · التقرير
  function screenReport() {
    var days = Number(B.f('rDays', 30)), p = P.report(days);
    B.need(p);
    var v = repView(days), body;
    if (!v) body = B.stateBlock(p, 'التقرير');
    else {
      body = '<ul class="sh-stats">' + v.cards.map(function (c) {
        return '<li class="sh-stat-card' + (c.na ? ' na' : '') + '"><b class="sh-n">' + esc(c.text) + '</b><span class="sh-tname">' + esc(c.label) + '</span><small>' + esc(c.na ? 'يظهر حين يبدأ التتبّع' : c.hint) + '</small></li>';
      }).join('') + '<li class="sh-stat-card' + (v.acceptance.na ? ' na' : '') + '"><b class="sh-n">' + esc(v.acceptance.text) + '</b><span class="sh-tname">أعمال الأعضاء المقبولة</span><small>'
        + esc(v.acceptance.na ? 'يظهر بعد أول عمل من الأعضاء' : v.acceptance.pct) + '</small></li></ul>'
        + (v.challenges ? '<h3 class="sh-h3">المشاركات في كل تحدٍّ</h3>' + (v.challenges.length ? '<ul class="sh-nums">' + v.challenges.map(function (c) {
          return '<li><b>' + esc(c.n == null ? NO : ar(c.n)) + '</b><span>' + esc(c.title) + '</span></li>';
        }).join('') + '</ul>' : B.empty('لا تحدّيات منشورة بعد', '')) : '<p class="sh-fine">المشاركات في كل تحدٍّ: ' + esc(X.NO_NUM) + '.</p>');
    }
    return { title: 'التقرير', sub: v ? v.daysText : '', img: 'reports', html: B.chips('rDays', X.DAYS_CHIPS, days) + body };
  }
  var NO = X.NO_NUM;

  B = Kit.board({
    key: 'diwan', mod: 'v2s_diwan', label: 'الديوان', lead: 'اختر ما تريد إدارته في الديوان',
    hub: function () { return HUB; }, tiles: tiles,
    screens: { works: screenWorks, comments: screenComments, challenges: screenChallenges, report: screenReport },
    act: {
      work: function (b, a, id) { var r = row((worksView(b.f('wSt', 'pending_review')) || {}).rows, id); if (r) workFlow(r, a.getAttribute('data-w')); },
      chide: function (b, a, id) { var r = row((commView(b.f('cSt', 'visible')) || {}).rows, id); if (r) commentFlow(r); },
      chnew: function () { challengeFlow(null); },
      chedit: function (b, a, id) { var r = row((chView() || {}).rows, id); if (r) challengeFlow(r); },
      chwin: function (b, a, id) { var r = row((chView() || {}).rows, id); if (r && r.canWinners) winnersFlow(r); }
    }
  });
  window.V2S_DIWAN = B;
})();
