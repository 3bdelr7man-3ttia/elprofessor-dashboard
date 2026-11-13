/* ============================================================================
 * v2-levels.js — R24 م٣: مستويات العقل لكل نوع شغل · «راجعت…» على البطاقة · سؤال التعلّم · «العقل عمل لوحده».
 * ⛔ مصدر الحقيقة في الخادم (`/api/v2/brain/levels|learn|alone-log|reviews` ⇐ backend/brain2/levels.py): هنا الشاشة بس.
 *   قفل الفلوس والنشر وقفل «اللي ما بيتعكسش» بيتفرضوا في الخادم (٤٠٩)؛ الواجهة بتعرضهم مقفولين بـ«دايمًا بموافقتك» ومش بتتخطّاهم.
 * الملف جزءان:
 *   ١) نقي (`V2L.lv`): صفوف الجدول · نص الإحصاء · جملة التعلّم · تجميع سجل «عمل لوحده» · نقط المراجعة · نوع شغل البطاقة — بلا DOM ولا شبكة (node بيختبره).
 *   ٢) `window.V2LEVELS`: الجلب والذاكرة المؤقتة والأوراق وتوصيل الأزرار. أي فشل ⇒ حالة «ما وصلتش البيانات» + «حاول تاني»، مش صفر.
 * نصوص ظاهرة: مصرية بسيطة، محايدة، بلا مصطلح تقني، ولا «·» جنب رقم عربي.
 * ========================================================================== */
(function () {
  'use strict';
  var L = window.V2L;
  if (!L || !L.util) return;
  var U = L.util;
  var LV = L.lv = {};

  var LEVEL_LABEL = { alone: 'لوحده', suggest: 'يقترح وانت توافق', ask: 'يسألك' };
  var LEVEL_ORDER = ['alone', 'suggest', 'ask'];
  var LOCK_TEXT = 'دايمًا بموافقتك';
  var NEEDED = 8;
  var FAIL_TEXT = 'تعذّر تنفيذ العملية';
  var SESSION_TEXT = 'انتهت الجلسة — سجّل الدخول من جديد ثم جرّب';
  var NA = 'ما وصلتش البيانات';
  LV.LEVEL_LABEL = LEVEL_LABEL; LV.LOCK_TEXT = LOCK_TEXT;

  function s_(v) { return typeof v === 'string' ? v.trim() : ''; }
  function esc(s) { return String(s == null ? '' : s).replace(/[&<>"']/g, function (c) { return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]; }); }
  function ar(n) { return U.ar(n); }

  // ------------------------------------------------------------------ ١) نقي
  // نص إحصاء آخر ٣٠ يوم: «وافقت ٨ من ٨» · «٢٣ مرة» · «دايمًا بموافقتك» · «حسب إعداد التوزيع في المنصة».
  LV.statText = function (row) {
    var st = row && row.stats ? row.stats : {};
    if (row && row.locked) return LOCK_TEXT;
    if (st.kind === 'external') return 'حسب إعداد التوزيع التلقائي في المنصة';
    if (st.kind === 'approvals' && st.of > 0) return 'وافقت ' + ar(st.n) + ' من ' + ar(st.of);
    if (st.kind === 'times') return st.n > 0 ? (st.n === 1 ? 'مرة واحدة' : ar(st.n) + ' مرة') : 'لسه ما حصلش حاجة';
    return 'لسه ما حصلش حاجة';
  };
  // صفوف الجدول من ردّ GET /levels ⇒ {groups:[{key,title,rows[]}]} أو null لو الشكل مش مفهوم.
  LV.rows = function (resp) {
    var list = resp && Array.isArray(resp.types) ? resp.types : null;
    if (!list) return null;
    var order = resp && Array.isArray(resp.groups) ? resp.groups : [];
    var groups = order.map(function (g) { return { key: s_(g.key), title: s_(g.title), rows: [] }; });
    var by = {};
    groups.forEach(function (g) { by[g.key] = g; });
    list.forEach(function (t) {
      if (!t || typeof t !== 'object' || !s_(t.id)) return;
      var locked = t.locked === true;
      var allowed = Array.isArray(t.levels) ? t.levels : [];
      var level = LEVEL_ORDER.indexOf(t.level) > -1 ? t.level : 'suggest';
      var learn = t.learn && typeof t.learn === 'object' ? t.learn : {};
      var row = {
        id: s_(t.id), group: s_(t.group), title: s_(t.title), hint: s_(t.hint), level: level, locked: locked,
        lockText: locked ? (s_(t.lock_text) || LOCK_TEXT) : '', eligible: t.eligible === true, reversible: t.reversible === true, external: s_(t.external),
        stat: LV.statText(t), stats: t.stats || {}, learnHint: !locked && t.eligible === true && level === 'suggest' && learn.show === true,
        learnN: Number(learn.n) || 0, updatedBy: s_(t.updated_by), updatedAt: s_(t.updated_at),
        options: LEVEL_ORDER.map(function (v) {
          var disabled = locked || allowed.indexOf(v) < 0 || (v === 'alone' && t.reversible !== true);
          return { value: v, label: LEVEL_LABEL[v], on: v === level, disabled: disabled };
        })
      };
      (by[row.group] || (by[row.group] = groups[groups.push({ key: row.group, title: row.group, rows: [] }) - 1])).rows.push(row);
    });
    return { groups: groups.filter(function (g) { return g.rows.length; }), needed: Number(resp.streak_needed) || NEEDED };
  };
  var UNIT_DEFAULT = ['عناصر', 'عنصرًا'];
  LV.learnText = function (p) {
    var n = Math.max(NEEDED, Number(p && p.n) || NEEDED);
    var unit = p && Array.isArray(p.unit) && p.unit.length >= 2 ? p.unit : UNIT_DEFAULT;
    return 'وافقت على اقتراحي في ' + ar(n) + ' ' + (n <= 10 ? unit[0] : unit[1]) + ' من غير ما تغيّر حاجة. تخليني أعملها لوحدي وأقولك بعدها؟';
  };
  LV.LEARN_YES = 'آه، خليها لوحده';
  LV.LEARN_NO = 'لا، فضّل اسألني';

  // نوع شغل البطاقة (لسؤال التعلّم). اقتراح عقل ⇒ منتجه. زائر عادي من غير علامة ⇒ فتح المنصة. غير كده ⇒ ''.
  LV.cardWorkType = function (c) {
    if (!c) return '';
    if (c.brainItem && s_(c.brainItem.producer)) return s_(c.brainItem.producer);
    if (c.kind === 'pending_user' && !(c.row && Array.isArray(c.row.flagLabels) && c.row.flagLabels.length)) return 'visitor_open';
    return '';
  };
  // قرار على بطاقة مش اقتراح عقل ⇒ النوع اللي بيتعلّم منه (الاقتراحات بتتعلّم من صفوفها في الخادم).
  LV.reportable = function (c) { return !!c && !c.brainItem && c.kind === 'pending_user' && LV.cardWorkType(c) === 'visitor_open'; };

  // مراجعة «راجعت…»: من جسم اقتراح (`item.body`) أو من `/reviews`. نقط سليمة بس.
  var REVIEW_HEAD = { application_review: 'راجعت ملف الطلب', file_review: 'راجعت رأي الخبير', ask_correction: 'راجعت التصحيح' };
  LV.reviewHead = function (producer) { return REVIEW_HEAD[producer] || 'راجعت الطلب'; };
  LV.reviewOf = function (body, producer) {
    if (!body || typeof body !== 'object' || !Array.isArray(body.points)) return null;
    var pts = body.points.filter(function (p) { return p && typeof p === 'object' && typeof p.ok === 'boolean' && s_(p.text); })
      .map(function (p) { return { ok: p.ok, text: s_(p.text) }; });
    if (!pts.length) return null;
    return { head: LV.reviewHead(producer), points: pts, suggestion: s_(body.text), why: s_(body.why) };
  };
  // مفتاح مراجعة طلب الانضمام لبطاقة: `trainer:<معرّف الطلب>`.
  LV.reviewRefOf = function (c) {
    if (!c) return '';
    if (c.kind === 'trainer' && c.row && c.row.apiId != null) return 'trainer:' + c.row.apiId;
    if (c.kind === 'person' && Array.isArray(c.parts)) {
      for (var i = 0; i < c.parts.length; i++) { var p = c.parts[i]; if (p && p.kind === 'trainer' && p.row && p.row.apiId != null) return 'trainer:' + p.row.apiId; }
    }
    return '';
  };

  // سجل «عمل لوحده» مجمّع للعرض: كل نوع في مجموعة واحدة («فتح المنصة لـ٦ زوّار جدد») والرجوع بيمشي على كل صفوفها.
  var GROUP_TEXT = {
    visitor_open: function (n, first) {
      return n === 1 ? first.what : 'فتح المنصة ' + (n === 2 ? 'لزائرين جدد' : 'لـ' + U.U(n, ['زائر جديد', 'زائرين جدد', 'زوّار جدد', 'زائرًا جديدًا'])) + ' (إيميلات عادية، من غير علامة اشتباه)';
    },
    comment_reject_abusive: function (n, first) { return n === 1 ? first.what : 'إخفاء ' + U.U(n, ['تعليق مسيء', 'تعليقين مسيئين', 'تعليقات مسيئة', 'تعليقًا مسيئًا']) + ' بوضوح'; }
  };
  function clock(t) {
    var d = new Date(t), h = d.getHours(), m = d.getMinutes(), ap = h >= 12 ? 'م' : 'ص';
    h = h % 12; if (h === 0) h = 12;
    return ar(h) + ':' + (m < 10 ? '٠' : '') + ar(m) + ' ' + ap;
  }
  LV.aloneGroups = function (rows) {
    if (!Array.isArray(rows)) return null;
    var out = [], idx = {};
    rows.forEach(function (r) {
      if (!r || !s_(r.id)) return;
      var key = r.work_type + (r.undone ? ':u' : '');
      if (r.work_type === 'visitor_open' || r.work_type === 'comment_reject_abusive') {
        if (idx[key] == null) { idx[key] = out.length; out.push({ key: key, type: r.work_type, rows: [], undone: !!r.undone }); }
        out[idx[key]].rows.push(r);
      } else {
        out.push({ key: key + ':' + r.id, type: r.work_type, rows: [r], undone: !!r.undone });
      }
    });
    return out.map(function (g) {
      var first = g.rows[0], fn = GROUP_TEXT[g.type];
      var text = fn ? fn(g.rows.length, first) : s_(first.what);
      var can = !g.undone && g.rows.every(function (r) { return r.can_undo; });
      var t = Date.parse(first.at || '');
      return { key: g.key, type: g.type, ids: g.rows.map(function (r) { return r.id; }), n: g.rows.length, text: text, undone: g.undone,
               canUndo: can, note: g.undone ? 'اترجّعت' : (can ? '' : (s_(first.undo_note) || 'مينفعش ترجّعها دلوقتي')),
               time: isNaN(t) ? '' : clock(t), at: isNaN(t) ? 0 : t };
    });
  };

  // ------------------------------------------------------------------ HTML (نقي)
  var BRAIN_IMG = '<img class="v2lv-av" src="v2/img/brain-avatar.jpg" alt="">';
  LV.reviewHtml = function (rv) {
    if (!rv) return '';
    return '<div class="v2lv-rv" data-lv-review="1">' + BRAIN_IMG + '<div class="v2lv-rvb"><b>' + esc(rv.head) + '</b>'
      + '<ul>' + rv.points.map(function (p) { return '<li class="' + (p.ok ? 'ok' : 'no') + '"><i aria-hidden="true">' + (p.ok ? '✓' : '!') + '</i><span>' + esc(p.text) + '</span></li>'; }).join('') + '</ul>'
      + (rv.suggestion ? '<p class="v2lv-sg"><b>اقتراحي:</b> ' + esc(rv.suggestion) + '</p>' : '')
      + (rv.why ? '<details class="v2lv-why"><summary>ليه؟</summary><p>' + esc(rv.why) + '</p></details>' : '') + '</div></div>';
  };
  LV.learnHtml = function (p, id) {
    if (!p) return '';
    return '<div class="v2lv-bar" data-lv-bar="' + esc(p.work_type) + '" role="group" aria-label="سؤال من العقل">' + BRAIN_IMG
      + '<p>' + esc(LV.learnText(p)) + '</p><div class="v2lv-barb"><button type="button" class="v2lv-y" data-lv="yes" data-wt="' + esc(p.work_type) + '">' + esc(LV.LEARN_YES) + '</button>'
      + '<button type="button" class="v2lv-n" data-lv="no" data-wt="' + esc(p.work_type) + '">' + esc(LV.LEARN_NO) + '</button></div></div>';
  };
  LV.aloneListHtml = function (groups, opts) {
    opts = opts || {};
    return '<ul class="v2lv-al">' + groups.map(function (g) {
      var btn = g.canUndo ? '<button type="button" class="v2lv-undo" data-lv="undo" data-ids="' + esc(g.ids.join(',')) + '"' + (opts.busy ? ' disabled' : '') + '>رجّعها</button>'
        : '<span class="v2lv-un">' + esc(g.note) + '</span>';
      return '<li class="' + (g.undone ? 'undone' : '') + '"><span class="v2lv-dot" aria-hidden="true"></span><span class="v2lv-tx">' + esc(g.text)
        + (opts.times && g.time ? '<small>' + esc(g.time) + '</small>' : '') + '</span>' + btn + '</li>';
    }).join('') + '</ul>';
  };
  LV.aloneBoxHtml = function (st) {
    // st = {state:'idle'|'loading'|'ready'|'error', groups}
    var head = '<div class="v2-boxh"><h3>العقل عمل لوحده النهارده</h3><button type="button" class="v2-link wine" data-a="brainlog">السجل كله</button></div>';
    var body;
    if (st.state === 'error') body = '<p class="v2-boxempty">' + NA + '. <button type="button" class="v2lv-retry" data-lv="retry-alone">حاول تاني</button></p>';
    else if (st.state !== 'ready') body = '<p class="v2-boxempty">…جارٍ الجلب</p>';
    else if (!st.groups.length) body = '<p class="v2-boxempty">لسه مفيش حاجة اتعملت لوحدها. لما تخلّي نوع شغل على «لوحده» هتلاقي هنا كل حاجة عملها، وجنبها «رجّعها» لو عايز تلغيها.</p>';
    else body = LV.aloneListHtml(st.groups.slice(0, 6), { busy: st.busy }) + (st.groups.length > 6 ? '<p class="v2-boxempty">والباقي في «السجل كله»</p>' : '');
    return '<section class="v2-box v2-brainbox" aria-label="العقل عمل لوحده النهارده">' + head + body + (st.note ? '<p class="v2lv-note" role="status">' + esc(st.note) + '</p>' : '') + '</section>';
  };
  // جدول المستويات (تبويب «العقل وقواعده»). st = {state, model, busy, note, error}
  LV.tableHtml = function (st) {
    var intro = '<section class="v2lv-intro">' + BRAIN_IMG + '<div><p class="v2lv-lead">كل شغل ليه واحدة من تلاتة، وتقدر تغيّرها في أي وقت. الفلوس والنشر للناس دايمًا بموافقتك.</p>'
      + '<p class="v2lv-defs"><b>لوحده:</b> بيعملها ويقولك بعدها، وتقدر ترجّعها. <b>يقترح:</b> بيراجع ويجهّزلك اقتراحه بضغطة. <b>يسألك:</b> بيجمع الورق ويسيبلك القرار.</p></div></section>';
    if (st.state === 'error') return intro + '<div class="v3-warn" role="status">' + NA + '. ما نعرفش مستويات العقل دلوقتي. <button type="button" class="v2lv-retry" data-lv="retry-levels">حاول تاني</button></div>';
    if (st.state !== 'ready' || !st.model) return intro + '<p class="v2-boxempty">…جارٍ الجلب</p>';
    var rows = st.model.groups.map(function (g) {
      return '<tr class="v2lv-grp"><th colspan="4">' + esc(g.title) + '</th></tr>' + g.rows.map(function (r) {
        var seg = '<div class="v2lv-seg' + (r.locked ? ' locked' : '') + '" role="radiogroup" aria-label="' + esc(r.title) + '">' + r.options.map(function (o) {
          var dis = r.locked || st.busy || (o.disabled && !o.on);
          return '<button type="button" role="radio" class="' + o.value + (o.on ? ' on' : '') + '" aria-checked="' + o.on + '" data-lv="set" data-wt="' + esc(r.id) + '" data-level="' + o.value + '"'
            + (dis ? ' disabled' : '') + '>' + esc(o.label) + '</button>';
        }).join('') + '</div>';
        return '<tr class="v2lv-row' + (r.locked ? ' locked' : '') + '" data-wt="' + esc(r.id) + '"><td class="v2lv-t"><b>' + esc(r.title) + '</b>' + (r.hint ? '<small>' + esc(r.hint) + '</small>' : '') + '</td>'
          + '<td class="v2lv-c">' + seg + '</td><td class="v2lv-s' + (r.locked ? ' lk' : '') + '">' + esc(r.stat) + '</td>'
          + '<td class="v2lv-h">' + (r.learnHint ? '<button type="button" class="v2lv-hint" data-lv="hint" data-wt="' + esc(r.id) + '">تخليها لوحده؟</button>' : '') + '</td></tr>';
      }).join('');
    }).join('');
    return intro + (st.note ? '<div class="v3-ok" role="status">' + esc(st.note) + '</div>' : '') + (st.error ? '<div class="v3-err" role="alert">' + esc(st.error) + '</div>' : '')
      + '<div class="v2lv-tw"><table class="v2lv-tb"><thead><tr><th>الشغل</th><th>العقل بيعمل إيه</th><th>آخر ٣٠ يوم</th><th></th></tr></thead><tbody>' + rows + '</tbody></table></div>';
  };
  LV.logHtml = function (st) {
    var head = '<section class="v2lv-intro">' + BRAIN_IMG + '<div><p class="v2lv-lead">كل حاجة عملها العقل لوحده، بالأحدث. جنب كل واحدة «رجّعها» لو فعلها يتعكس.</p></div></section>';
    if (st.state === 'error') return head + '<div class="v3-warn" role="status">' + NA + '. <button type="button" class="v2lv-retry" data-lv="retry-alone-all">حاول تاني</button></div>';
    if (st.state !== 'ready') return head + '<p class="v2-boxempty">…جارٍ الجلب</p>';
    if (!st.groups.length) return head + '<p class="v2-boxempty">لسه مفيش حاجة اتعملت لوحدها.</p>';
    return head + (st.note ? '<div class="v3-ok" role="status">' + esc(st.note) + '</div>' : '') + '<div class="v2lv-lg">' + LV.aloneListHtml(st.groups, { times: true, busy: st.busy }) + '</div>';
  };
  if (typeof module !== 'undefined' && module.exports) module.exports.lv = LV;

  // ------------------------------------------------------------------ ٢) الجلب والشاشة
  var CACHE_MS = 60000;
  var ST = { levels: src(), learn: src(), reviews: src(), aloneToday: src(), aloneAll: src() };
  var ver = 0, listeners = [], busy = false, note = '', noteT = null, errMsg = '';
  function src() { return { state: 'idle', data: null, at: 0, loading: false }; }
  function ep() { return window.EP || null; }
  function on() { return !!(window.V2SHELL && window.V2SHELL.on && ep() && ep().authed && typeof ep().api === 'function'); }
  function call(method, path, body) { return ep().api(path, body === undefined ? { method: method } : { method: method, body: body }); }
  function toast(t) { try { if (typeof window.toast === 'function') window.toast(t); } catch (e) {} }
  function changed() { ver++; listeners.slice().forEach(function (fn) { try { fn(); } catch (e) {} }); }
  function errText(e) {
    if (e && e.status === 401) return SESSION_TEXT;
    var d = (e && e.data) || {};
    return typeof d.error === 'string' && d.error ? d.error : FAIL_TEXT;
  }
  var PATH = { levels: '/v2/brain/levels', learn: '/v2/brain/learn', reviews: '/v2/brain/reviews', aloneToday: '/v2/brain/alone-log?day=today', aloneAll: '/v2/brain/alone-log?day=all' };
  function load(k, force) {
    if (!on()) return;
    var s = ST[k];
    if (s.loading) return;
    if (!force && s.state === 'ready' && Date.now() - s.at < CACHE_MS) return;
    s.loading = true; if (s.state === 'idle') s.state = 'loading';
    call('GET', PATH[k]).then(function (d) { s.loading = false; s.at = Date.now(); s.data = d; s.state = d && typeof d === 'object' ? 'ready' : 'error'; changed(); })
      .catch(function () { s.loading = false; s.at = Date.now(); s.state = 'error'; changed(); });
  }
  function ensure(k) {
    if (!on()) return;
    var s = ST[k];
    if (s.state === 'idle') load(k, true);
    else if (!s.loading && s.state !== 'loading' && Date.now() - s.at > CACHE_MS) load(k, true);
  }
  function setNote(t) {
    note = t; clearTimeout(noteT);
    noteT = setTimeout(function () { note = ''; changed(); }, 9000);
    changed();
  }

  var V = window.V2LEVELS = {};
  V.isOn = on;
  V.listen = function (fn) { listeners.push(fn); return function () { listeners = listeners.filter(function (x) { return x !== fn; }); }; };
  V.sig = function () { return on() ? String(ver) + (busy ? 'b' : '') : ''; };
  V.state = ST;
  V.ensure = ensure;
  V.reload = function (k) { if (k) load(k, true); else Object.keys(ST).forEach(function (x) { if (ST[x].state !== 'idle') load(x, true); }); };

  // —— قراءات للرسم
  V.levelsModel = function () { var s = ST.levels; return { state: s.state, model: s.state === 'ready' ? LV.rows(s.data) : null }; };
  V.tableState = function () { var m = V.levelsModel(); if (m.state === 'ready' && !m.model) m.state = 'error'; m.busy = busy; m.note = note; m.error = errMsg; return m; };
  V.promptFor = function (c) {
    var wt = LV.cardWorkType(c);
    if (!wt || ST.learn.state !== 'ready' || !ST.learn.data) return null;
    var list = Array.isArray(ST.learn.data.prompts) ? ST.learn.data.prompts : [];
    for (var i = 0; i < list.length; i++) if (list[i].work_type === wt) return list[i];
    return null;
  };
  V.reviewFor = function (c) {
    if (!c) return null;
    if (c.brainItem) return LV.reviewOf(c.brainItem.body, c.brainItem.producer);
    var ref = LV.reviewRefOf(c);
    var map = ST.reviews.state === 'ready' && ST.reviews.data && ST.reviews.data.reviews;
    if (!ref || !map || !map[ref]) return null;
    return LV.reviewOf(map[ref], map[ref].producer || 'application_review');
  };
  V.reviewHtml = function (c) { ensure('reviews'); return LV.reviewHtml(V.reviewFor(c)); };
  V.learnHtml = function (c) { ensure('learn'); var p = V.promptFor(c); return p ? LV.learnHtml(p) : ''; };
  V.aloneState = function (which) {
    var s = ST[which === 'all' ? 'aloneAll' : 'aloneToday'];
    var rows = s.state === 'ready' && s.data && Array.isArray(s.data.rows) ? s.data.rows : null;
    var groups = rows ? LV.aloneGroups(rows) : [];
    return { state: s.state === 'ready' && !rows ? 'error' : s.state, groups: groups, busy: busy, note: note };
  };
  V.aloneBox = function () { ensure('aloneToday'); return LV.aloneBoxHtml(V.aloneState('today')); };
  V.aloneLog = function () { ensure('aloneAll'); return LV.logHtml(V.aloneState('all')); };

  // —— أفعال
  function sheet(title, html) {
    if (typeof window.openModal !== 'function') return null;
    var s = window.openModal(title, '<div class="v2lv-m">' + html + '</div>');
    var close = function () { if (!s.dataset.busy) window.closeModal(); };
    var x = s.querySelector('[data-x]'); if (x) x.onclick = close;
    s.onclick = function (e) { if (e.target === s) close(); };
    return s;
  }
  function doSet(id, level, title) {
    if (busy) return Promise.resolve();
    busy = true; errMsg = ''; changed();
    return call('PUT', '/v2/brain/levels/' + encodeURIComponent(id), { level: level }).then(function () {
      busy = false;
      setNote('اتغيّر: «' + title + '» بقى «' + LEVEL_LABEL[level] + '»');
      load('levels', true); load('learn', true);
      return { ok: true };
    }).catch(function (e) {
      busy = false; errMsg = errText(e); changed();
      load('levels', true);
      return { ok: false, error: errMsg };
    });
  }
  function findRow(id) {
    var m = LV.rows(ST.levels.data), hit = null;
    if (m) m.groups.forEach(function (g) { g.rows.forEach(function (r) { if (r.id === id) hit = r; }); });
    return hit;
  }
  // تغيير مستوى من الجدول. «لوحده» بورقة تأكيد؛ الباقي مباشرة. الخادم هو الحَكَم (٤٠٩ ⇒ جملته تتعرض).
  V.setLevel = function (id, level) {
    var r = findRow(id); if (!r) return;
    if (level === r.level) return;
    if (level !== 'alone') return doSet(id, level, r.title);
    var s = sheet('تشغّل «' + r.title + '» لوحده؟',
      '<p class="v2lv-p">العقل هيعملها بنفسه ويسجّلها في «اللي عمله لوحده»، وتقدر ترجّع أي واحدة بعد ما تتعمل. الفلوس والنشر للناس دايمًا بموافقتك.</p>'
      + '<div id="v2lv_err"></div><div class="acts"><button type="button" class="btn btn-primary" id="v2lv_go">آه، لوحده</button><button type="button" class="btn btn-ghost" id="v2lv_x">رجوع</button></div>');
    if (!s) return doSet(id, level, r.title);
    s.querySelector('#v2lv_x').onclick = function () { if (!s.dataset.busy) window.closeModal(); };
    var go = s.querySelector('#v2lv_go');
    go.onclick = function () {
      if (go.dataset.busy) return;
      go.dataset.busy = '1'; s.dataset.busy = '1'; go.disabled = true; go.textContent = 'جارٍ التنفيذ…';
      doSet(id, level, r.title).then(function (res) {
        delete s.dataset.busy;
        if (res && res.ok) { window.closeModal(); return; }
        delete go.dataset.busy; go.disabled = false; go.textContent = 'آه، لوحده';
        var er = s.querySelector('#v2lv_err'); if (er) er.innerHTML = '<div class="v2lv-err" role="alert">' + esc((res && res.error) || FAIL_TEXT) + '</div>';
      });
    };
  };
  V.answer = function (wt, yes) {
    if (busy) return Promise.resolve();
    busy = true; changed();
    return call('POST', '/v2/brain/learn/' + encodeURIComponent(wt) + '/answer', { answer: yes ? 'yes' : 'no' }).then(function () {
      busy = false;
      toast(yes ? 'تمام، هنفّذها لوحدي وأقولك بعدها' : 'تمام، هفضل أسألك');
      load('learn', true); load('levels', true); load('aloneToday', true);
      return { ok: true };
    }).catch(function (e) { busy = false; toast(errText(e)); changed(); load('learn', true); return { ok: false }; });
  };
  // رجوع مجموعة صفوف بالترتيب؛ يقف عند أول فشل ويقول اللي اتعمل (الجملة العربية من الخادم لو الرجوع مستحيل).
  V.undo = function (ids) {
    if (busy || !ids || !ids.length) return Promise.resolve();
    busy = true; changed();
    var done = 0;
    function step(i) {
      if (i >= ids.length) { busy = false; setNote(done === 1 ? 'اترجّعت' : 'اترجّعت ' + ar(done)); reloadAlone(); return Promise.resolve({ ok: true }); }
      return call('POST', '/v2/brain/alone-log/' + encodeURIComponent(ids[i]) + '/undo', {}).then(function () { done++; return step(i + 1); });
    }
    return step(0).catch(function (e) {
      busy = false;
      setNote((done ? 'اترجّع ' + ar(done) + ' بس. ' : '') + errText(e));
      reloadAlone();
      return { ok: false };
    });
  };
  function reloadAlone() { load('aloneToday', true); if (ST.aloneAll.state !== 'idle') load('aloneAll', true); load('levels', true); }
  // قرار على بطاقة مش اقتراح عقل (زائر عادي): يتسجّل للتعلّم. فشله ما بيكسرش القرار نفسه.
  V.report = function (c, outcome) {
    if (!on() || !LV.reportable(c) || ['approved', 'edited', 'rejected'].indexOf(outcome) < 0) return;
    call('POST', '/v2/brain/learn', { work_type: LV.cardWorkType(c), outcome: outcome, ref: String(c.id || '') }).then(function () { load('learn', true); load('levels', true); }).catch(function () {});
  };
  V.reportComment = function (o, action) {
    var m = o && o.moderation;
    if (!on() || !m || m.ai_checked !== true || m.abusive !== true) return;
    call('POST', '/v2/brain/learn', { work_type: 'comment_reject_abusive', outcome: action === 'reject' ? 'approved' : 'rejected', ref: 'op:' + String(o.id || '') })
      .then(function () { load('learn', true); }).catch(function () {});
  };

  // توصيل أزرار `data-lv` داخل عنصر. `opts.redraw` يُنادى بعد أي تغيّر (الشاشة اللي رسمت بتعيد الرسم).
  V.wire = function (root) {
    if (!root || !root.querySelectorAll) return;
    Array.prototype.forEach.call(root.querySelectorAll('[data-lv]'), function (b) {
      var a = b.getAttribute('data-lv');
      if (a === 'yes' || a === 'no') b.onclick = function () { V.answer(b.getAttribute('data-wt'), a === 'yes'); };
      else if (a === 'undo') b.onclick = function () { V.undo(String(b.getAttribute('data-ids') || '').split(',').filter(Boolean)); };
      else if (a === 'set') b.onclick = function () { V.setLevel(b.getAttribute('data-wt'), b.getAttribute('data-level')); };
      else if (a === 'hint') b.onclick = function () { V.setLevel(b.getAttribute('data-wt'), 'alone'); };
      else if (a === 'retry-levels') b.onclick = function () { load('levels', true); };
      else if (a === 'retry-alone') b.onclick = function () { load('aloneToday', true); };
      else if (a === 'retry-alone-all') b.onclick = function () { load('aloneAll', true); };
    });
  };
})();
