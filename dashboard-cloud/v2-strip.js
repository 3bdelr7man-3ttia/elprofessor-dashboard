/* ============================================================================
 * v2-strip.js — R24 م٢: شريط «محتاج قرارك (ن)» الواحد في أعلى كل قسم. ⛔ مكوّن واحد مشترك: كل الأقسام بترسم منه، ولا قسم له شريط تاني.
 * ⛔ لا منطق قرار هنا: البطاقات والعدّاد والبعدين من `V2.strip(key)` (v2-home.js ⇐ v2-logic.js `v2Strip`)، والأزرار بتنفّذ بنفس
 *   المنفّذ اللي بتنفّذ بيه بطاقة «ابدأ القرارات» (`V2.runCard`) — يعني نفس الفعل بالحرف في المكانين.
 * ⛔ تحته شغل القسم بلا أزرار قرار مكرّرة. فاضي ⇒ سطر واحد «مفيش حاجة مستنياك هنا».
 * ⛔ ولا طلب شبكة من هنا. المفتاح مقفول (الغلاف الجديد مش شغّال) ⇒ الملف بيتحمّل ومبيرسمش حاجة.
 * ========================================================================== */
(function () {
  'use strict';
  var L = window.V2L;
  if (!L) return;
  var U = L.util;
  var ST = window.V2STRIP = {};
  var S = { el: null, key: '', hide: false, open: '', all: {}, sig: '', timer: null, listening: false };
  var INFO = {};       // قسم ⇒ سطر «للعلم» واحد (حالة أو عدّ حقيقي بدل الشريط الكحلي القديم اللي كان تحت الشريط)
  var SHOWN = 6;     // أول ٦ بطاقات؛ والباقي «اعرض الكل»

  function esc(s) { return String(s == null ? '' : s).replace(/[&<>"']/g, function (c) { return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]; }); }
  function V() { return window.V2 || null; }
  function LVL() { return window.V2LEVELS && window.V2LEVELS.isOn && window.V2LEVELS.isOn() ? window.V2LEVELS : null; }
  function say(t) { try { (window.toast || window.notify || function () {})(t); } catch (e) {} }

  // ------------------------------------------------------------------ قطع مشتركة (الشريط وصفحة الشخص)
  function titleHtml(c) {
    return c.person && window.V2D2 && V2D2.link ? V2D2.link(c.title, c.person.email) : esc(c.title);
  }
  // أزرار البطاقة. `o.snooze` ⇒ «بعدين» و«تجاهل» (للشريط بس). كل زرار `data-a` + `data-id` والتوصيل في `wire`.
  function actionsHtml(c, o) {
    o = o || {};
    var busy = !!(V() && V2.isBusy && V2.isBusy());
    var dis = busy ? ' disabled' : '';
    var h = '';
    if (c.primary) h += '<button type="button" class="v2z-b1" data-a="p" data-id="' + esc(c.id) + '"' + dis + '>' + esc(c.primary.label) + '</button>';
    if (c.secondary) h += '<button type="button" class="v2z-b2" data-a="s" data-id="' + esc(c.id) + '"' + dis + '>' + esc(c.secondary.label) + '</button>';
    if (c.edit) h += '<button type="button" class="v2z-b2" data-a="e" data-id="' + esc(c.id) + '"' + dis + '>' + esc(c.edit.label) + '</button>';
    if (c.read) h += '<button type="button" class="v2z-b3" data-a="x" data-id="' + esc(c.id) + '"' + dis + '>' + esc(c.read.label) + '</button>';
    if (o.snooze && c.key) h += '<button type="button" class="v2z-b3" data-a="l" data-id="' + esc(c.id) + '"' + dis + '>بعدين</button>';
    if (o.snooze && c.dismiss) h += '<button type="button" class="v2z-b3" data-a="d" data-id="' + esc(c.id) + '"' + dis + '>تجاهل</button>';
    if (c.link && c.link.url) h += '<a class="v2z-b3" href="' + esc(c.link.url) + '" target="_blank" rel="noopener noreferrer">' + esc(c.link.label) + '</a>';
    return h;
  }
  // توصيل الأزرار. `byId` ⇒ البطاقة · `ctx.done(text)` بعد النجاح · `ctx.fail(msg)` عند الفشل. بنرجع للمنفّذ الواحد.
  function wire(root, byId, ctx) {
    ctx = ctx || {};
    var run = function (c, a) {
      if (!c || !a || !V() || !V2.runCard) return;
      V2.runCard(c, a, function (text) { if (ctx.done) ctx.done(text, c); else say(text); }, function (msg) { if (ctx.fail) ctx.fail(msg, c); });
    };
    root.querySelectorAll('[data-a]').forEach(function (b) {
      var c = byId[b.getAttribute('data-id')], a = b.getAttribute('data-a');
      if (!c) return;
      if (a === 'p') b.onclick = function () { run(c, c.primary && c.primary.act); };
      else if (a === 's') b.onclick = function () { run(c, c.secondary && c.secondary.act); };
      else if (a === 'e') b.onclick = function () { run(c, c.edit && c.edit.act); };
      else if (a === 'x') b.onclick = function () { run(c, c.read && c.read.act); };
      else if (a === 'l') b.onclick = function () { if (V() && V2.snooze) V2.snooze(c); };
      else if (a === 'd') b.onclick = function () { if (V() && V2.dismiss) V2.dismiss(c); };
    });
  }
  ST.actionsHtml = actionsHtml; ST.wire = wire; ST.titleHtml = titleHtml;

  // ------------------------------------------------------------------ البطاقة
  function cardHtml(c) {
    var err = V() && V2.errorOf ? V2.errorOf(c.id) : '';
    var chips = (c.chips && c.chips.length) ? '<div class="v2z-chips">' + c.chips.map(function (x) { return '<span class="v2z-chip">' + esc(x) + '</span>'; }).join('')
      + (c.merged > 1 ? '<span class="v2z-chip ok">بطاقة واحدة بدل ' + esc(U.ar(c.merged)) + '</span>' : '') + '</div>' : '';
    var open = '';
    if (c.person && c.kind !== 'person' && c.chips) open = '';       // الاسم نفسه رابط صفحة الشخص
    return '<article class="v2z-c' + (c.warn ? ' warn' : '') + '" data-id="' + esc(c.id) + '" data-bid="' + esc(c.id) + '" data-kind="' + esc(c.kind) + '">'
      + '<div class="v2z-top"><span class="v2z-tag">' + esc(c.tag) + '</span>' + (c.ageText ? '<time>' + esc(c.ageText) + '</time>' : '') + '</div>'
      + '<h3>' + titleHtml(c) + '</h3>'
      + (c.sub ? '<p class="v2z-sub">' + esc(c.sub) + '</p>' : '')
      + chips
      + (c.brain && c.kind !== 'person' ? '<p class="v2z-brain">' + esc(c.brain) + '</p>' : '')
      + (c.reason ? '<p class="v2z-reason">' + esc(c.reason) + '</p>' : '')
      + (LVL() ? LVL().reviewHtml(c) : '')      // R24 م٣: «راجعت…» (نقط ✓ و! + اقتراحي + ليه؟) لو العقل راجع البطاقة دي
      + (c.returned ? '<p class="v2z-returned">' + esc(c.returned) + '</p>' : '')
      + (c.warn ? '<p class="v2z-warn">' + esc(c.warn) + '</p>' : '')
      + (err ? '<p class="v2z-err" role="alert">' + esc(err) + '</p>' : '')
      + open + '<div class="v2z-acts">' + actionsHtml(c, { snooze: true }) + '</div>'
      + (LVL() ? LVL().learnHtml(c) : '') + '</article>';      // R24 م٣: سؤال «تخليني أعملها لوحدي؟» بعد ٨ موافقات متتالية من غير تعديل
  }
  function linesHtml(d) {
    var chip = function (k, label, n) { return n ? '<button type="button" class="v2z-lc' + (S.open === k ? ' on' : '') + '" data-l="' + k + '" aria-expanded="' + (S.open === k) + '">' + label + ' (' + esc(U.ar(n)) + ')</button>' : ''; };
    var h = chip('later', 'مؤجّلة', d.later.length) + chip('gone', 'اتشالت', d.gone.length);
    if (!h) return '';
    var list = S.open === 'later' ? d.later : S.open === 'gone' ? d.gone : null, panel = '';
    if (list && list.length) {
      panel = '<ul class="v2z-sl">' + list.map(function (x) {
        return '<li><span><b>' + esc(x.title) + '</b><small>' + esc([x.tag, x.kind === 'dismiss' ? ('السبب: ' + x.reason) : x.untilText].filter(Boolean).join('، ')) + '</small></span>'
          + '<button type="button" class="v2z-b1 sm" data-r="' + esc(x.key) + '">رجّعها</button></li>';
      }).join('') + '</ul>';
    }
    return '<div class="v2z-lines">' + h + '</div>' + panel;
  }
  function infoHtml() {
    var t = INFO[S.key];
    return t ? '<p class="v2z-fyi v2z-info"><b>للعلم:</b> ' + esc(t) + '</p>' : '';
  }
  function fyiHtml(d) {
    if (!d.fyi.length) return '';
    return '<p class="v2z-fyi"><b>للعلم:</b> ' + d.fyi.map(function (g) { return esc(g.label); }).join('، ') + '</p>';
  }

  // ------------------------------------------------------------------ الرسم
  function tileOf(key) {
    var t = null;
    try { (V().tiles() || []).forEach(function (x) { if (x.key === key) t = x; }); } catch (e) {}
    return t;
  }
  function render() {
    var el = S.el, v = V();
    if (!el) return '';
    if (S.hide || !S.key || S.key === 'home' || !v || !v.strip) { el.hidden = true; el.innerHTML = ''; return ''; }
    var d = v.strip(S.key), t = tileOf(S.key);
    var loading = false;
    try { loading = !!(v.tileLoading && v.tileLoading(S.key)); } catch (e) {}
    var head = '<header class="v2z-h"><h2>محتاج قرارك</h2>' + (d.n ? '<span class="v2z-n">' + esc(U.ar(d.n)) + '</span>' : '') + '</header>';
    var body;
    if (t && t.failed) {
      // ⛔ ما نقولش «مفيش حاجة مستنياك» فوق مصدر ما وصلش.
      body = '<p class="v2z-fail">تعذّر جلب قرارات هذا القسم — لا تعتبره فاضيًا. <button type="button" class="v2z-b2 sm" data-retry="1">حاول تاني</button></p>';
    } else if (loading && !d.n) {
      body = '<p class="v2z-empty">…جارٍ جلب القرارات</p>';
    } else if (!d.n) {
      body = '<p class="v2z-empty">' + esc(d.emptyText) + '</p>';
    } else {
      var all = !!S.all[S.key], shown = all ? d.cards : d.cards.slice(0, SHOWN);
      body = '<div class="v2z-grid">' + shown.map(cardHtml).join('') + '</div>'
        + (d.cards.length > SHOWN ? '<button type="button" class="v2z-b3 more" data-more="1">' + (all ? 'اعرض أقل' : 'اعرض الكل (' + esc(U.ar(d.cards.length)) + ')') + '</button>' : '');
    }
    var warn = t && t.partial && !t.failed ? '<p class="v2z-fail">العدد ناقص — تعذّر جلب بعض المصادر، فيه قرارات ممكن ما تظهرش هنا.</p>' : '';
    el.hidden = false;
    el.innerHTML = '<section class="v2z' + (d.n ? '' : ' empty') + '" data-sec="' + esc(S.key) + '" aria-label="محتاج قرارك">' + head + warn + body + linesHtml(d) + fyiHtml(d) + infoHtml() + '</section>';
    var byId = {};
    d.cards.forEach(function (c) { byId[c.id] = c; });
    wire(el, byId, { done: function (text) { say(text); draw(); }, fail: function () { draw(); } });
    if (LVL()) LVL().wire(el);
    el.querySelectorAll('[data-l]').forEach(function (b) { b.onclick = function () { var k = b.getAttribute('data-l'); S.open = S.open === k ? '' : k; draw(); }; });
    el.querySelectorAll('[data-r]').forEach(function (b) { b.onclick = function () { if (v.restore) v.restore(b.getAttribute('data-r')); }; });
    var rt = el.querySelector('[data-retry]'); if (rt) rt.onclick = function () { if (v.retry) v.retry(); };
    var mo = el.querySelector('[data-more]'); if (mo) mo.onclick = function () { S.all[S.key] = !S.all[S.key]; draw(); };
    return sigOf(d, t, loading);
  }
  function sigOf(d, t, loading) {
    return [S.key, S.hide, S.open, !!S.all[S.key], loading, t ? [t.failed, t.partial].join(',') : '', d.cards.map(function (c) { return c.id + ':' + (c.returned || '') + ':' + (c.fp || ''); }).join('|'),
            d.later.length, d.gone.length, d.fyi.map(function (g) { return g.key + g.n; }).join(','), (V() && V2.isBusy && V2.isBusy()) ? 'b' : '',
            d.cards.map(function (c) { return V() && V2.errorOf ? V2.errorOf(c.id) : ''; }).join(''), LVL() ? LVL().sig() : '', INFO[S.key] || ''].join('#');
  }
  function draw() { S.sig = render(); }
  function currentSig() {
    var v = V();
    if (S.hide || !S.key || S.key === 'home' || !v || !v.strip) return 'hidden:' + S.hide + S.key;
    var d = v.strip(S.key), t = tileOf(S.key), loading = false;
    try { loading = !!(v.tileLoading && v.tileLoading(S.key)); } catch (e) {}
    return sigOf(d, t, loading);
  }

  // `hide` = صفحة تفصيل (شخص · دورة): الشريط مش بيتعرض فوقها.
  ST.mount = function (key, el, hide) {
    S.el = el; S.key = key; S.hide = !!hide;
    if (!el) return;
    if (!S.listening && V() && V2.listen) { S.listening = true; V2.listen(function () { if (S.el && !document.getElementById('epModal')) draw(); }); }
    if (!S.lvl && LVL() && LVL().listen) { S.lvl = true; LVL().listen(function () { if (S.el && !document.getElementById('epModal')) draw(); }); }
    draw();
    if (!S.timer) {
      S.timer = setInterval(function () {
        if (!S.el || document.getElementById('epModal')) return;
        if (currentSig() !== S.sig) draw();
      }, 700);
    }
  };
  ST.refresh = draw;
  // R24 م٣: الأقسام بتبعت سطر «للعلم» بتاعها هنا (مرة لكل رسم) بدل شريط كحلي تحت الشريط. نص فاضي ⇒ يتشال. التغيير بس بيعيد رسم الشريط.
  ST.info = function (key, text) {
    text = String(text == null ? '' : text).trim();
    if ((INFO[key] || '') === text) return;
    INFO[key] = text;
    if (S.el && S.key === key) draw();
  };
  // الشاشات اللي تحت الشريط بتوصّل له بدل ما تكرّر أزراره.
  ST.scrollTo = function () {
    var el = S.el; if (!el) return;
    try { el.scrollIntoView({ block: 'start', behavior: 'smooth' }); } catch (e) {}
    var z = el.querySelector('.v2z'); if (z) { z.classList.add('v2z-flash'); setTimeout(function () { z.classList.remove('v2z-flash'); }, 1800); }
  };
  ST.sig = function () { return currentSig(); };
  ST._state = S;
})();
