/* ============================================================================
 * v2s/reports.js — قسم «التقارير» (الجولة النهائية): «التقرير» · «ما يسأل عنه الناس» · «تقرير الأحد».
 * ⛔ لا منطق أرقام هنا: الأرقام وجمل العقل من `GET /api/v2/reports/summary|weekly` (الخادم يبنيها بقواعد ثابتة)، والعرض والتصفية من `V2L.v2r`
 *   (نقي في v2-logic.js). ⛔ الرقم المجهول يُكتب «غير متاح بعد» ولا يتحوّل إلى صفر أبدًا.
 * ⛔ الشبكة: مسارات `/api/v2/reports/*` · محمّل `analysis` الموجود · `/api/platform-chat-insights/<id>` و`.../classify` (الموجودان).
 * ⛔ الأوراق كلها من ورقة D3 الموجودة (`V2D3.openSheet` و`V2D3.twoStage`). لا حاوية ثالثة، ولا نداء مباشر لـ`openModal`.
 * ⛔ المفتاح مقفول افتراضيًا: الملف يتحمّل دائمًا لكنه لا يرسم شيئًا إلا لو index.html نادى `V2SEC.reports.render` (والغلاف الجديد شغّال).
 * ========================================================================== */
(function () {
  'use strict';
  var L = window.V2L;
  if (!L || !L.v2r) return;
  var U = L.util, V = L.v2r, NA = V.NA;
  window.V2SEC = window.V2SEC || {};
  var R = window.V2SEC.reports = {};
  var MODS = { analysis: 'report', v2r_demand: 'demand', v2r_sunday: 'sunday' };
  var DEF = { scope: 'all', period: 'month' };
  var SRC_LABEL = { ledger: 'دفتر الإيرادات', users: 'الحسابات الجديدة', market: 'طلبات السوق', content: 'مقالات الموقع', disputes: 'النزاعات',
                    chat: 'أسئلة المحادثة', funnel: 'رحلة الزائر', delivery: 'إرسال تقرير الأحد' };
  var SECTION_ORDER = ['files', 'courses', 'books', 'market', 'content', 'satisfaction'];
  var SCOPE_NAME = { all: 'المنصة كلها', files: 'الملفات', courses: 'الدورات', books: 'الكتب', market: 'السوق', content: 'المحتوى', marketing: 'التسويق' };
  var SCOPE_OPEN = { files: 'ملفات الخبراء', courses: 'الدورات', books: 'الكتب', market: 'سوق الخدمات', content: 'المحتوى' };
  var SEC_PHOTO = { files: 'files', courses: 'courses', books: 'books', market: 'market', content: 'content', satisfaction: 'people' };
  var BAR_COLORS = ['#9E2B4E', '#B44E6E', '#C97590', '#DB9DB1', '#EBC6D2'];
  var BAR_H = [70, 52, 38, 26, 18];
  var STALE_MS = 5 * 60 * 1000;

  var S = {
    view: null, mod: '', scope: DEF.scope, period: DEF.period, booted: false,
    cache: {},                 // 'scope|period' => {state, data, at, seq}
    why: false, note: null, noteT: null,
    weekly: { week: '', state: 'idle', data: null, seq: 0, at: 0 },
    d: { f: { seg: 'all', country: 'all', cat: 'all', ne: 'all', time: 'all' }, panel: false },
    poll: null, tick: null, tip: -1, nowOverride: 0
  };

  function esc(s) { return String(s == null ? '' : s).replace(/[&<>"']/g, function (c) { return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]; }); }
  function host() { return window.V2_HOST || {}; }
  function ep() { return window.EP || null; }
  function q(sel, root) { return (root || document).querySelector(sel); }
  function qa(sel, root) { return Array.prototype.slice.call((root || document).querySelectorAll(sel)); }
  function now() { return S.nowOverride || Date.now(); }
  function img(name) { return 'v2/img/' + name + '.jpg'; }
  function sheetApi() { return window.V2D3 || {}; }
  function isNum(v) { return typeof v === 'number' && isFinite(v); }
  function ar(n) { return U.fmt(n); }
  function UU(n, forms) { return V.u(n, forms); }
  function lskey(k) { try { return localStorage.getItem(k); } catch (e) { return null; } }
  function lsset(k, v) { try { localStorage.setItem(k, v); } catch (e) {} }
  function glob(name) { try { return (0, eval)('typeof ' + name + "!=='undefined'?" + name + ':null'); } catch (e) { return null; } }

  R.owns = function (mod) { return !!MODS[mod] && !!(window.V2SHELL && window.V2SHELL.on); };

  // ------------------------------------------------------------------ مسار العنوان: النطاق والفترة
  var VALID_SCOPE = V.SCOPES.map(function (x) { return x[0]; });
  var VALID_PERIOD = V.PERIODS.map(function (x) { return x[0]; });
  function routeQ() { var s = host().state ? host().state() : null; return (s && s.q) || null; }
  function syncFromRoute() {
    var rq = routeQ(), scope = DEF.scope, period = DEF.period;
    if (rq) {
      if (VALID_SCOPE.indexOf(rq.scope) > -1) scope = rq.scope;
      if (VALID_PERIOD.indexOf(rq.period) > -1) period = rq.period;
    } else if (!S.booted) {
      // أول دخول في هذه الجلسة بعنوان عادي: آخر اختيار محفوظ (راحة للمستخدم فقط) ويُكتب في العنوان فورًا ليبقى الرجوع صحيحًا.
      var ss = lskey('v2r_scope'), sp = lskey('v2r_period');
      if (VALID_SCOPE.indexOf(ss) > -1) scope = ss;
      if (VALID_PERIOD.indexOf(sp) > -1) period = sp;
    }
    var changed = scope !== S.scope || period !== S.period;
    S.scope = scope; S.period = period;
    if (!rq && !S.booted && (scope !== DEF.scope || period !== DEF.period) && S.mod === 'analysis' && host().openSection) {
      S.booted = true;
      host().openSection('reports', 'report', { replace: true, q: qOf(scope, period) });
      return 'redirect';
    }
    S.booted = true;
    return changed;
  }
  function qOf(scope, period) {
    var o = {};
    if (scope !== DEF.scope) o.scope = scope;
    if (period !== DEF.period) o.period = period;
    return o.scope || o.period ? o : null;
  }
  function navigate(scope, period) {
    lsset('v2r_scope', scope); lsset('v2r_period', period);
    if (scope === S.scope && period === S.period) return;
    S.why = false;
    if (host().openSection) host().openSection('reports', 'report', { q: qOf(scope, period) });
  }
  function openSec(section, tab) { if (host().openSection) host().openSection(section, tab || undefined); }

  // ------------------------------------------------------------------ الجلب
  function ckey() { return S.scope + '|' + S.period; }
  function entry(k) { return S.cache[k] || (S.cache[k] = { state: 'idle', data: null, at: 0, seq: 0 }); }
  function loadSummary(force) {
    var E = ep(), k = ckey(), e = entry(k);
    if (!E || !E.api || !E.authed) return;
    if (e.state === 'loading') return;
    if (!force && e.state === 'ready' && now() - e.at < 60 * 1000) return;
    e.state = e.data ? 'refresh' : 'loading';
    var seq = ++e.seq;
    var path = '/v2/reports/summary?period=' + S.period + '&scope=' + S.scope + (force === 'fresh' ? '&fresh=1' : '');
    E.api(path).then(function (d) {
      if (seq !== e.seq) return;
      e.state = 'ready'; e.data = d; e.at = Date.now(); redrawSoon();
    }).catch(function (err) {
      if (seq !== e.seq) return;
      if (err && err.status === 401) return;
      e.state = e.data && !force ? 'ready' : 'error'; if (e.state === 'error') e.data = null; redrawSoon();
    });
  }
  function loadWeekly(week) {
    var E = ep(), w = S.weekly;
    if (!E || !E.api || !E.authed) return;
    w.state = w.data ? 'refresh' : 'loading';
    var seq = ++w.seq;
    E.api('/v2/reports/weekly' + (week ? '?week=' + encodeURIComponent(week) : '')).then(function (d) {
      if (seq !== w.seq) return;
      w.state = 'ready'; w.data = d; w.week = d && d.week ? d.week.start : week; w.at = Date.now(); redrawSoon();
    }).catch(function (err) {
      if (seq !== w.seq) return;
      if (err && err.status === 401) return;
      w.state = 'error'; w.data = null; w.err = (err && err.data && err.data.error) || ''; redrawSoon();
    });
  }
  function ensureDemand() {
    var E = ep(); if (E && E.authed) E.ensure('analysis', redrawSoon);
  }
  var redrawT = null;
  function redrawSoon() { if (redrawT) return; redrawT = setTimeout(function () { redrawT = null; redraw(); }, 0); }
  function active() { var m = host().current ? host().current() : ''; return !!MODS[m] && R.owns(m); }

  // ------------------------------------------------------------------ أجزاء عامة
  function warnStrip(sources) {
    var bad = [], s = sources || {};
    Object.keys(SRC_LABEL).forEach(function (k) { if (s[k] === 'failed' || s[k] === 'partial') bad.push(SRC_LABEL[k]); });
    var out = '';
    if (s.window === 'failed') out += '<div class="v3-warn" role="status">التوقيت غير متاح، الأيام محسوبة بتوقيت جرينتش</div>';
    if (bad.length) out += '<div class="v3-warn" role="status">تعذّر الوصول إلى: ' + esc(bad.join(' · ')) + ' — ما يظهر ناقص، وليس معناه أنه لا شيء</div>';
    return out;
  }
  function noteStrip() { return S.note ? '<div class="v3-ok" role="status">' + esc(S.note) + '</div>' : ''; }
  function setNote(t) { S.note = t; clearTimeout(S.noteT); S.noteT = setTimeout(function () { S.note = null; redraw(); }, 9000); }
  function loadingBlock(t) { return '<div class="v3-empty"><b>…' + esc(t) + '</b></div>'; }
  function failBlock(title, a) {
    return '<div class="v3-empty"><b>' + esc(title) + ': ' + NA + '</b><p>تعذّر الجمع الآن، فلا تعتبر الأرقام صفرًا.</p><button type="button" class="v3-btn2" data-a="' + a + '">أعد المحاولة</button></div>';
  }
  function naText(t) { return '<span class="v2r-na">' + esc(t || NA) + '</span>'; }
  function numHtml(v, fmtFn) { return isNum(v) ? esc(fmtFn ? fmtFn(v) : ar(v)) : naText(); }
  function moneyOf(a) { return U.moneyText(a, 'EGP'); }
  function chipHtml(c) { return c ? '<span class="v2r-st t-' + esc(c.tone || 'mute') + '">' + esc(c.text) + '</span>' : ''; }
  function agoLine(at) {
    if (!at) return '';
    var t = U.agoText(at, now());
    return 'حُدّث ' + (t === 'الآن' ? 'الآن' : t.replace(/^منذ/, 'قبل'));
  }
  function nameOfScope(scope) { return SCOPE_NAME[scope] || SCOPE_NAME.all; }
  function timeText(h, m) {
    var ap = h >= 12 ? 'مساءً' : 'صباحًا', h12 = h % 12 || 12;
    return ar(h12) + ':' + (m < 10 ? '٠' : '') + ar(m) + ' ' + ap;
  }
  function printHead(d) {
    var g = /^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2})/.exec(d.generated_at || ''), at = '';
    if (g) at = 'أُعدّ في ' + V.weekText(g[1] + '-' + g[2] + '-' + g[3]) + ' ' + U.ar(+g[1]) + '، ' + timeText(+g[4], +g[5]);
    return '<div class="v2r-printhead"><b>البروفيسور · تقرير ' + esc(nameOfScope(d.scope)) + ' · ' + esc((d.window && d.window.label) || '') + '</b>' + (at ? '<span>' + esc(at) + '</span>' : '') + '</div>';
  }

  // ------------------------------------------------------------------ ملخص العقل
  function actLabel(a) { return a && a.label ? a.label : ''; }
  function brainStrip(brain, primary, w) {
    var lines = brain || [];
    var cols = lines.map(function (b) {
      var body;
      if (b.text) body = '<p>' + esc(b.text) + '</p>';
      else if (b.na_reason) body = '<p class="v2r-bgrey">' + esc(NA) + ': ' + esc(b.na_reason) + '</p>';
      else body = '<p class="v2r-bgrey">' + esc(b.empty_text || NA) + '</p>';
      var act = '';
      if (b.text && b.action) {
        if (b.key === primary) act = '<button type="button" class="v3-btn2 v2r-bbtn" data-a="open" data-sec="' + esc(b.action.section) + '" data-tab="' + esc(b.action.tab || '') + '">' + esc(actLabel(b.action)) + '</button>';
        else act = '<a class="v2r-inl" href="#" data-a="open" data-sec="' + esc(b.action.section) + '" data-tab="' + esc(b.action.tab || '') + '">← ' + esc(actLabel(b.action)) + '</a>';
      }
      return '<div class="v2r-bl k-' + esc(b.key) + '"><b>' + esc(b.label) + '</b>' + body + act + '</div>';
    }).join('');
    var basis = lines.map(function (b) {
      var items = (b.basis || []).map(function (x) { return '<li>' + esc(x.label) + ': <b>' + esc(x.value) + '</b> <small>(' + esc(x.source) + ')</small></li>'; }).join('');
      if (!items && !b.text) return '';
      return '<div class="v2r-bs k-' + esc(b.key) + '"><b>' + esc(b.label) + '</b><ul>' + items + '</ul></div>';
    }).join('');
    return '<section class="v2r-brain" aria-label="ملخص العقل"><img class="v2r-bav" src="' + img('brain-avatar') + '" alt="">'
      + '<div class="v2r-bcols">' + cols + '</div>'
      + '<div class="v2r-bwhy"><button type="button" class="v2r-whyt" data-a="why" aria-expanded="' + (S.why ? 'true' : 'false') + '">على أي أساس؟</button></div>'
      + '<div class="v2r-basis' + (S.why ? ' open' : '') + '"' + (S.why ? '' : ' hidden') + '><p class="v2r-bwin">' + esc(w || '') + '</p>' + basis + '</div></section>';
  }

  // ------------------------------------------------------------------ رحلة الزائر
  function stageCols(stages, funnel) {
    var maxCur = Math.max.apply(null, stages.map(function (s) { return isNum(s.cur) ? s.cur : 0; }).concat([1]));
    return stages.map(function (s, i) {
      var prevKnown = i > 0 && isNum(stages[i - 1].cur) ? stages[i - 1] : null;
      var v = V.stageView(s, prevKnown);
      var change = v.changeText ? '<span class="v2r-chg t-' + esc(v.tone) + '">' + esc(v.changeText) + (v.convText ? ' · ' + esc(v.convText) : '') + '</span>'
        : (v.convText ? '<span class="v2r-chg t-mute">' + esc(v.convText) + '</span>' : '');
      var h = BAR_H[i] != null ? BAR_H[i] : 18, w = isNum(s.cur) ? Math.max(4, Math.round(s.cur / maxCur * 100)) : 0;
      var bar = isNum(s.cur)
        ? '<span class="v2r-fbar" style="height:' + h + 'px;--w:' + w + '%;background:' + BAR_COLORS[Math.min(i, 4)] + '"></span>'
        : '<span class="v2r-fbar empty" style="height:' + h + 'px"></span>';
      return '<li class="v2r-fs"><span class="v2r-fl">' + esc(s.label) + '</span><b class="v2r-fn">' + (isNum(s.cur) ? esc(ar(s.cur)) : naText()) + '</b>' + change
        + (s.sub ? '<small class="v2r-fsub">' + esc(s.sub) + '</small>' : '') + bar + '</li>';
    }).join('');
  }
  function funnelCard(fn, win, prevLabel, shortPeriod) {
    if (!fn) return '';
    var head = '<header class="v3-ch"><h2>' + esc(fn.title) + '</h2><p>' + esc(shortPeriod) + '</p></header>';
    if (fn.mode === 'full') {
      return '<section class="v3-card v2r-card v2r-funnel" aria-label="' + esc(fn.title) + '">' + head + '<ol class="v2r-fcols n' + fn.stages.length + '">' + stageCols(fn.stages, fn) + '</ol></section>';
    }
    var c = V.funnelCompact(fn.stages);
    var rows = c.rows.map(function (s) {
      var idx = fn.stages.indexOf(s), prevKnown = idx > 0 && isNum(fn.stages[idx - 1].cur) ? fn.stages[idx - 1] : null;
      var v = V.stageView(s, prevKnown);
      return '<li class="v2r-cr"><span class="v2r-fl">' + esc(s.label) + '</span><b class="v2r-fn">' + (isNum(s.cur) ? esc(ar(s.cur)) : naText()) + '</b>'
        + (v.changeText ? '<span class="v2r-chg t-' + esc(v.tone) + '">' + esc(v.changeText) + (v.convText ? ' · ' + esc(v.convText) : '') + '</span>' : '')
        + (s.sub ? '<small class="v2r-fsub">' + esc(s.sub) + '</small>' : '') + '</li>';
    }).join('');
    return '<section class="v3-card v2r-card v2r-funnel compact" aria-label="' + esc(fn.title) + '">' + head
      + (rows ? '<ul class="v2r-crows">' + rows + '</ul>' : '<p class="v3-none">' + NA + '</p>')
      + (c.missing ? '<p class="v2r-cmiss">' + esc(c.text) + '</p>' : '') + '</section>';
  }

  // ------------------------------------------------------------------ يومًا بيوم
  function periodShort(d) { return d.period === 'week' ? 'آخر ٧ أيام' : d.period === 'quarter' ? 'آخر ١٣ أسبوعًا' : 'آخر ٣٠ يومًا'; }
  function chartCard(d) {
    var dl = d.daily || {}, title = dl.bucket === 'week' ? 'أسبوعًا بأسبوع' : 'يومًا بيوم';
    if (dl.na) {
      return '<section class="v3-card v2r-card v2r-chart"><header class="v3-ch"><h2>' + esc(title) + '</h2></header><div class="v3-empty"><b>' + NA + '</b><p>' + esc(dl.reason || '') + '</p></div></section>';
    }
    var rows = dl.rows || [], W = S.cw || 560, H = S.chh || 300;
    var pts = V.chartPoints(rows, W, H);
    var leg = V.legendItems(dl, d.scope);
    var noIncome = !pts.income, allZero = pts.income && pts.income.flat && (!pts.signups || pts.signups.flat) && !(pts.visits && !pts.visits.flat);
    var body;
    if (allZero && dl.ledger !== false && (pts.signups || d.scope !== 'all')) {
      body = '<div class="v3-empty"><b>' + (pts.signups ? 'لا دخل ولا حسابات جديدة في هذه الفترة' : 'لا دخل في هذه الفترة') + '</b></div>';
    } else if (noIncome && !pts.signups && !pts.visits) {
      body = '<div class="v3-empty"><b>' + NA + '</b><p>تعذّر الوصول إلى الأرقام اليومية الآن.</p></div>';
    } else {
      body = svgChart(d, rows, pts, W, H, leg);
    }
    var drawnChart = body.indexOf('<svg') > -1;
    var legend = leg.items.length && drawnChart ? '<ul class="v2r-legend' + (dl.visits_available ? ' hasv' : '') + '">' + leg.items.map(function (it) { return '<li class="k-' + it.key + '"><i></i>' + esc(it.label) + '</li>'; }).join('') + '</ul>' : '';
    var foot = [];
    if (leg.notes.length) foot.push(leg.notes.join(' · '));
    var other = (dl.income_other || []).map(function (x) { return U.moneyText(x.amount, x.currency); });
    if (other.length) foot.push('دخل بعملة أخرى في الفترة: ' + other.join(' · '));
    var td = d.today, tline = '';
    if (td) {
      var parts = [];
      parts.push(isNum(td.income_egp) ? moneyOf(td.income_egp) : NA);
      if (td.show_signups) parts.push(isNum(td.signups) ? UU(td.signups, ['حساب واحد', 'حسابان', 'حسابات', 'حسابًا']) : 'الحسابات: ' + NA);
      tline = '<p class="v2r-today">اليوم حتى الآن: ' + esc(parts.join(' · ')) + (td.income_other && td.income_other.length ? ' · وبعملة أخرى: ' + esc(td.income_other.map(function (x) { return U.moneyText(x.amount, x.currency); }).join(' · ')) : '') + '</p>';
    }
    return '<section class="v3-card v2r-card v2r-chart"><header class="v3-ch v2r-chh"><h2>' + esc(title) + '</h2>' + legend + '</header>' + body
      + tline + (foot.length ? '<p class="v3-fine">' + esc(foot.join(' · ')) + '</p>' : '') + '</section>';
  }
  function svgChart(d, rows, pts, W, H, leg) {
    var n = rows.length, g = '', line = '', labels = '';
    pts.grid.forEach(function (y) { g += '<line x1="0" y1="' + y + '" x2="' + W + '" y2="' + y + '" stroke="#F0EAE1" stroke-width="1"/>'; });
    function poly(s, color, w, dash) { return s ? '<polyline points="' + s.pts.map(function (p) { return p[0] + ',' + p[1]; }).join(' ') + '" fill="none" stroke="' + color + '" stroke-width="' + w + '"' + (dash ? ' stroke-dasharray="9 5"' : '') + ' stroke-linejoin="round" stroke-linecap="round"/>' : ''; }
    var area = '';
    if (pts.income && n > 1) {
      var p = pts.income.pts;
      area = '<path d="M' + p.map(function (x) { return x[0] + ' ' + x[1]; }).join(' L') + ' L' + p[p.length - 1][0] + ' ' + pts.base + ' L' + p[0][0] + ' ' + pts.base + ' Z" fill="rgba(33,38,46,0.07)"/>';
    }
    line += poly(pts.income, '#21262E', 2.5, false);
    var visitsOn = !!pts.visits;
    line += poly(pts.visits, '#9E2B4E', 3, false);
    line += poly(pts.signups, '#9E2B4E', visitsOn ? 2.5 : 3, visitsOn);
    [0, Math.floor((n - 1) / 2), n - 1].filter(function (v, i, a) { return n > 0 && a.indexOf(v) === i; }).forEach(function (i) {
      var x = (pts.income || pts.signups || pts.visits || { pts: [] }).pts[i];
      if (!x) return;
      var cx = Math.min(Math.max(x[0], 46), W - 46);
      labels += '<text x="' + cx + '" y="' + (H - 10) + '" text-anchor="middle" fill="#6B665C" font-size="13" font-family="IBM Plex Sans Arabic,sans-serif">' + esc(rows[i].label) + '</text>';
    });
    var step = n > 1 ? (W - 2 * pts.padX) / (n - 1) : W;
    var hits = rows.map(function (r, i) {
      var cx = n === 1 ? W / 2 : pts.padX + (W - 2 * pts.padX) * i / (n - 1);
      return '<rect class="v2r-hit" data-i="' + i + '" x="' + Math.max(cx - step / 2, 0) + '" y="0" width="' + step + '" height="' + H + '" fill="transparent"/>';
    }).join('');
    var label = 'الدخل' + (pts.signups ? ' والحسابات الجديدة' : '') + (pts.visits ? ' والزوار' : '') + ' في ' + periodShort(d);
    return '<svg class="v2r-svg" viewBox="0 0 ' + W + ' ' + H + '" role="img" tabindex="0" aria-label="' + esc(label) + '" data-n="' + n + '">'
      + g + area + line + labels + '<g class="v2r-tip" visibility="hidden"><circle r="6" fill="#9E2B4E"/><rect rx="10" height="44"/><text text-anchor="middle" fill="#fff" font-size="14" font-family="IBM Plex Sans Arabic,sans-serif"/></g>' + hits + '</svg>';
  }
  function tipText(d, i) {
    var r = (d.daily.rows || [])[i]; if (!r) return '';
    var t = (d.daily.bucket === 'week' ? 'أسبوع ' : '') + r.label + ': ' + (isNum(r.income_egp) ? moneyOf(r.income_egp) : NA);
    if (d.daily.signups_available && isNum(r.signups)) t += ' · ' + UU(r.signups, ['حساب واحد', 'حسابان', 'حسابات', 'حسابًا']);
    if (d.daily.visits_available && isNum(r.visits)) t += ' · ' + UU(r.visits, ['زيارة واحدة', 'زيارتان', 'زيارات', 'زيارة']);
    return t;
  }
  function showTip(root, d, i) {
    var svg = q('.v2r-svg', root); if (!svg) return;
    var n = +svg.getAttribute('data-n'), vb = svg.viewBox.baseVal, pts = V.chartPoints(d.daily.rows, vb.width, vb.height), g = q('.v2r-tip', svg);
    i = Math.max(0, Math.min(n - 1, i)); S.tip = i;
    var base = pts.income || pts.signups || pts.visits; if (!base || !g) return;
    var p = base.pts[i], text = tipText(d, i), wd = Math.min(360, Math.max(150, text.length * 8.2 + 26));
    var x = Math.min(Math.max(p[0], wd / 2 + 4), vb.width - wd / 2 - 4), y = Math.max(p[1] - 62, 4);
    var rect = q('rect', g), tx = q('text', g), c = q('circle', g);
    c.setAttribute('cx', p[0]); c.setAttribute('cy', p[1]);
    rect.setAttribute('x', x - wd / 2); rect.setAttribute('y', y); rect.setAttribute('width', wd); rect.setAttribute('fill', '#21262E');
    tx.setAttribute('x', x); tx.setAttribute('y', y + 28); tx.textContent = text;
    g.setAttribute('visibility', 'visible');
  }
  function wireChart(root, d) {
    var svg = q('.v2r-svg', root); if (!svg) return;
    qa('.v2r-hit', svg).forEach(function (h) {
      var i = +h.getAttribute('data-i');
      h.addEventListener('mouseenter', function () { showTip(root, d, i); });
      h.addEventListener('click', function () { showTip(root, d, i); });
    });
    svg.addEventListener('keydown', function (e) {
      var n = +svg.getAttribute('data-n');
      if (e.key === 'ArrowRight') { e.preventDefault(); showTip(root, d, S.tip < 0 ? 0 : S.tip + 1); }
      else if (e.key === 'ArrowLeft') { e.preventDefault(); showTip(root, d, S.tip < 0 ? n - 1 : S.tip - 1); }
    });
    svg.addEventListener('mouseleave', function () { var g = q('.v2r-tip', svg); if (g) g.setAttribute('visibility', 'hidden'); S.tip = -1; });
  }

  // ------------------------------------------------------------------ من أين يأتي الناس
  function originsBlock(o, layout) {
    if (!o || (!o.channels && !o.countries && !o.top_pages)) {
      return '<p class="v2r-origline"><b>من أين يأتي الناس</b> ' + naText() + ' <span>' + esc((o && o.note) || 'تكتمل حين تسجّل المنصة مصدر كل زائر وكل دفعة.') + '</span></p>';
    }
    var chan = o.channels ? '<div class="v2r-ob"><h3>القنوات</h3><ul class="v2r-bars">' + o.channels.map(function (c, i) {
      return '<li title="' + esc(isNum(c.signups) ? ar(c.signups) + ' حسابًا' : '') + '"><div class="v2r-bl2"><span>' + esc(c.label) + '</span><b>' + (isNum(c.pct) ? esc(ar(c.pct)) + '٪' : naText()) + '</b></div><span class="bar"><span style="width:' + (c.pct || 0) + '%;background:' + BAR_COLORS[Math.min(i, 4)] + '"></span></span></li>';
    }).join('') + '</ul></div>' : '<div class="v2r-ob"><h3>القنوات</h3>' + naText() + '</div>';
    var ctry = o.countries ? '<div class="v2r-ob"><h3>البلاد</h3><div class="v2r-chips">' + o.countries.map(function (c) {
      return '<span class="v2r-pill">' + esc(c.label) + (isNum(c.pct) ? ' ' + esc(ar(c.pct)) + '٪' : '') + '</span>'; }).join('') + '</div></div>' : '<div class="v2r-ob"><h3>البلاد</h3>' + naText() + '</div>';
    var pages = o.top_pages ? '<div class="v2r-ob"><h3>أكثر الصفحات التي جاءت بالناس</h3><ol class="v2r-pages">' + o.top_pages.map(function (p) {
      return '<li><span>' + esc(p.title || p.path) + '</span><b>' + esc(ar(p.visits)) + '</b></li>'; }).join('') + '</ol></div>' : '<div class="v2r-ob"><h3>أكثر الصفحات التي جاءت بالناس</h3>' + naText() + '</div>';
    return '<section class="v3-card v2r-card v2r-orig"><header class="v3-ch"><h2>من أين يأتي الناس</h2></header><div class="v2r-og">' + chan + ctry + pages + '</div></section>';
  }

  // ------------------------------------------------------------------ كل قسم في سطر
  function secValue(r) {
    if (!r.value) return naText();
    var t = r.value.kind === 'money' ? moneyOf(r.value.egp) : r.value.text;
    return esc(t) + (r.value.others && r.value.others.length ? ' <small class="v2r-oth" title="' + esc(r.value.others.map(function (x) { return U.moneyText(x.amount, x.currency); }).join(' · ')) + '">· وبعملة أخرى</small>' : '');
  }
  function secChip(r) {
    var c = ['files', 'courses', 'books'].indexOf(r.key) > -1 && r.trend ? V.trendChip(r.trend) : r.chip;
    var hint = r.chip_hint ? ' title="' + esc(r.chip_hint) + '"' : '';
    if (c && !r.value && c.text === NA) return '';   // «غير متاح بعد» مرة واحدة في القيمة، لا مرتين
    return c ? '<span class="v2r-st t-' + esc(c.tone) + '"' + hint + '>' + esc(c.text) + '</span>' : '';
  }
  function secRow(r, expanded) {
    var photo = '<span class="v2r-ph" style="background-image:url(' + img(SEC_PHOTO[r.key] || 'reports') + ')"></span>';
    var under = r.note ? '<small class="v2r-under">' + esc(r.note) + '</small>' : '';
    var inner = photo + '<span class="v2r-nm"><span>' + esc(r.label) + '</span>' + under + '</span><span class="v2r-vl">' + secValue(r) + '</span>' + secChip(r) + '<span class="v2r-chev" aria-hidden="true">‹</span>';
    if (expanded) return '<div class="v2r-row on">' + inner.replace('<span class="v2r-chev" aria-hidden="true">‹</span>', '') + '</div>';
    return '<button type="button" class="v2r-row" data-a="scope" data-scope="' + esc(r.key === 'satisfaction' ? 'all' : r.key) + '"' + (r.key === 'satisfaction' ? ' data-open="disputes"' : '') + '>' + inner + '</button>';
  }
  function secExtra(r) {
    var lines = [];
    if (r.value && r.value.kind === 'money') {
      lines.push('عمليات الدفع في الفترة: ' + UU(r.value.count, ['عملية واحدة', 'عمليتان', 'عمليات', 'عملية']));
      if (r.prev) lines.push('الفترة التي قبلها: ' + moneyOf(r.prev.egp) + ' (' + UU(r.prev.count, ['عملية واحدة', 'عمليتان', 'عمليات', 'عملية']) + ')');
      else lines.push('الفترة التي قبلها: ' + NA);
    }
    return lines.length ? '<ul class="v2r-xl">' + lines.map(function (x) { return '<li>' + esc(x) + '</li>'; }).join('') + '</ul>' : '';
  }
  function sectionsCard(d, delivery) {
    var rows = d.sections || [], scope = d.scope, body, title = 'كل قسم في سطر';
    if (scope === 'marketing') {
      body = '<div class="v2r-mk"><p><b>التسويق:</b> افتح قسم التسويق لأرقام الحملات</p><button type="button" class="v3-btn2" data-a="open" data-sec="marketing">افتح التسويق</button></div>';
      return '<section class="v3-card v2r-card v2r-secs"><header class="v3-ch"><h2>' + title + '</h2></header>' + body + '</section>';
    }
    if (scope !== 'all') {
      var key = scope, r = rows.filter(function (x) { return x.key === key; })[0];
      body = r ? secRow(r, true) + secExtra(r) + '<button type="button" class="v3-btn2 v2r-openbtn" data-a="open" data-sec="' + esc(r.open) + '">افتح ' + esc(SCOPE_OPEN[scope] || r.label) + '</button>' : '';
    } else {
      body = '<div class="v2r-rows">' + SECTION_ORDER.map(function (k) { var r2 = rows.filter(function (x) { return x.key === k; })[0]; return r2 ? secRow(r2, false) : ''; }).join('') + '</div>';
    }
    var foot = (delivery && delivery.text) ? '<p class="v2r-dline">' + esc(delivery.text) + ' <a href="#" class="v2r-inl" data-a="open" data-sec="reports" data-tab="sunday">افتح تقرير الأحد</a></p>' : '';
    return '<section class="v3-card v2r-card v2r-secs"><header class="v3-ch"><h2>' + title + '</h2>' + (scope !== 'all' ? '<p><a href="#" class="v2r-inl" data-a="scope" data-scope="all">← كل الأقسام</a></p>' : '') + '</header>' + body + foot + '</section>';
  }

  // ------------------------------------------------------------------ عناصر التحكم
  function controls(d) {
    var chips = V.SCOPES.map(function (s) {
      return '<button type="button" role="tab" class="v2r-chip' + (S.scope === s[0] ? ' on' : '') + '" aria-selected="' + (S.scope === s[0]) + '" data-a="scope" data-scope="' + s[0] + '">' + esc(s[1]) + '</button>';
    }).join('');
    var sel = '<select class="v2r-sel" data-a="scopesel" aria-label="القسم">' + V.SCOPES.map(function (s) {
      return '<option value="' + s[0] + '"' + (S.scope === s[0] ? ' selected' : '') + '>القسم: ' + esc(s[1]) + '</option>'; }).join('') + '</select>';
    var seg = '<div class="v3-seg" role="group" aria-label="الفترة">' + V.PERIODS.map(function (p) {
      return '<button type="button" class="v3-pb' + (S.period === p[0] ? ' on' : '') + '" aria-pressed="' + (S.period === p[0]) + '" data-a="period" data-period="' + p[0] + '">' + esc(p[1]) + '</button>'; }).join('') + '</div>';
    return '<div class="v2r-top"><div class="v2r-scope" role="tablist" aria-label="القسم">' + chips + '</div>' + sel + seg
      + '<button type="button" class="v3-btn1 v2r-print" data-a="print">نزّل التقرير</button></div>';
  }

  // ------------------------------------------------------------------ تبويب «التقرير»
  function drawReport(v) {
    var e = entry(ckey()), d = e.data;
    var head = noteStrip();
    if (!d) {
      var body = e.state === 'error' ? failBlock('التقرير', 'retry') : loadingBlock('جارٍ جمع التقرير');
      v.innerHTML = '<div class="v3 v2r" data-tab="report">' + controls(null) + head + body + '</div>';
      return wire(v, null);
    }
    var fresh = '<p class="v2r-fresh"><span class="v2r-fresh-t">' + esc(agoLine(e.at)) + '</span> · <a href="#" class="v2r-inl" data-a="refresh">حدّث الآن</a></p>';
    var period = '<p class="v3-ptxt v2r-ptxt">' + esc(V.periodLine(d.window, d.prev)) + '</p>';
    var w = d.window && d.window.label;
    var shortP = periodShort(d) + ' مقارنة بما قبلها';
    var cards;
    var funnel = funnelCard(d.funnel, d.window, d.prev && d.prev.label, shortP);
    if (d.scope === 'marketing') {
      cards = brainStrip(d.brain, null, w) + sectionsCard(d, d.delivery);
    } else if (d.layout === 'full') {
      cards = brainStrip(d.brain, d.brain_primary, w) + funnel
        + '<div class="v2r-low"><div class="v2r-lc">' + chartCard(d) + '</div><div class="v2r-lo">' + originsBlock(d.origins, 'full') + '</div><div class="v2r-ls">' + sectionsCard(d, d.delivery) + '</div></div>';
    } else {
      cards = brainStrip(d.brain, d.brain_primary, w) + sectionsCard(d, d.delivery) + chartCard(d) + funnel + (d.scope === 'all' ? originsBlock(d.origins, 'compact') : '');
    }
    v.innerHTML = '<div class="v3 v2r" data-tab="report">' + printHead(d) + controls(d) + fresh + period + head + warnStrip(d.sources) + cards + '</div>';
    wire(v, d);
  }

  // ------------------------------------------------------------------ تبويب «ما يسأل عنه الناس»
  function segLabel(c) { var m = glob('SEG_LABEL') || {}; var t = m[c] || ''; return (t || (c ? 'غير محدد' : 'غير محدد')).replace('مؤثر/رائد أعمال', 'مؤثر أو رائد أعمال'); }
  function countryLabel(c) { var m = glob('COUNTRY_LABEL') || {}; return m[c] || 'غير محدد'; }
  function catLabel(c) { var f = glob('catAr'); return typeof f === 'function' ? f(c) : c; }
  function intentLabel(c) { return c || 'غير محدد'; }
  function barList(items, keyField, labelFn, drill, color) {
    if (!items.length) return '';
    var max = Math.max.apply(null, items.map(function (x) { return x.count || 0; }).concat([1]));
    return '<ul class="v2r-dbars">' + items.map(function (x) {
      var val = x[keyField], wd = Math.round(((x.count || 0) / max) * 100);
      var inner = '<div class="v2r-bl2"><span>' + esc(labelFn(val)) + '</span><b>' + esc(ar(x.count || 0)) + '</b></div><span class="bar"><span style="width:' + wd + '%;background:' + color + '"></span></span>';
      return drill ? '<li><button type="button" class="v2r-dbar" data-a="drill" data-dim="' + drill + '" data-val="' + esc(String(val == null ? '' : val)) + '">' + inner + '</button></li>' : '<li><div class="v2r-dbar static">' + inner + '</div></li>';
    }).join('') + '</ul>';
  }
  function filterPanelHtml(d, inSheet) {
    var f = S.d.f, arr = function (x) { return Array.isArray(x) ? x : []; };
    var seg = arr(d.by_segment).filter(function (x) { return (x.segment || '') !== 'unknown' && (x.segment || '') !== ''; }).concat(arr(d.by_segment).filter(function (x) { return !x.segment || x.segment === 'unknown'; }));
    var country = arr(d.by_country), cat = arr(d.by_category);
    function sel(dim, all, items, vf, lf) {
      return '<label class="v2r-fl2"><span class="v2r-sr">' + esc(all) + '</span><select data-f="' + dim + '" aria-label="' + esc(all) + '"><option value="all">' + esc(all) + '</option>' + items.map(function (x) {
        var vv = String(x[vf]); return '<option value="' + esc(vv) + '"' + (f[dim] === vv ? ' selected' : '') + '>' + esc(lf(x[vf])) + '</option>'; }).join('') + '</select></label>';
    }
    function chip(dim, val, label) { return '<button type="button" class="v2r-chip' + (f[dim] === val ? ' on' : '') + '" data-f="' + dim + '" data-v="' + val + '" aria-pressed="' + (f[dim] === val) + '">' + esc(label) + '</button>'; }
    return '<div class="v2r-fp"><div class="v2r-fr">' + sel('seg', 'كل الشرائح', seg, 'segment', segLabel) + sel('country', 'كل البلاد', country, 'country', countryLabel)
      + (cat.length ? sel('cat', 'كل المجالات', cat, 'category', function (x) { return catLabel(x) || 'غير محدد'; }) : '') + '</div>'
      + '<div class="v2r-fr">' + chip('ne', 'no', 'لا تحتاج خبيرًا') + '</div>'
      + '<div class="v2r-fr">' + chip('time', 'all', 'كل الوقت') + chip('time', '7', 'آخر ٧ أيام') + chip('time', '30', 'آخر ٣٠ يومًا') + '</div>'
      + (inSheet ? '<button type="button" class="v3-btn1 v2r-go" data-a="applyf">اعرض النتائج</button>' : '') + '</div>';
  }
  function drawDemand(v) {
    var E = ep(), st = (E && E.state && E.state.analysis) || 'idle', d = (E && E.data && E.data.analysis) || {};
    if (st === 'idle' || st === 'loading') { v.innerHTML = '<div class="v3 v2r" data-tab="demand">' + noteStrip() + loadingBlock('جارٍ جلب الأسئلة') + '</div>'; return wire(v, null); }
    if (st === 'error') { v.innerHTML = '<div class="v3 v2r" data-tab="demand"><div class="v3-empty"><b>أسئلة المحادثة: ' + NA + '</b><p>تعذّر الوصول إلى هذه البيانات الآن، فلا تعتبر الشاشة فارغة.</p><button type="button" class="v3-btn2" data-a="dretry">أعد المحاولة</button></div></div>'; return wire(v, null); }
    var arr = function (x) { return Array.isArray(x) ? x : []; };
    if ((d.total || 0) === 0 && !arr(d.recent_questions).length) { v.innerHTML = '<div class="v3 v2r" data-tab="demand">' + noteStrip() + '<div class="v3-empty"><b>لم يصل أي سؤال بعد</b></div></div>'; return wire(v, null); }
    var recent = arr(d.recent_questions), unmet = arr(d.unmet), unclassified = d.unclassified || 0, f = S.d.f;
    var filtered = V.demandFilter(recent, f, now());
    var hidden = V.hiddenFilters(f);
    var numsLine = '<div class="v2r-nrow"><p class="v2r-nums">' + esc(V.demandNumbers(d)) + (unclassified ? '' : ' · كل الأسئلة مصنّفة') + '</p>'
      + (unclassified ? '<button type="button" class="v3-btn2" data-a="classify">صنّف الأسئلة الجديدة (' + esc(ar(unclassified)) + ')</button>' : '') + '</div>';
    var top = unmet[0], restU = unmet.slice(1);
    var opp = '<section class="v3-card v2r-card v2r-opp' + (top ? '' : ' empty') + '"><header class="v3-ch"><h2>خدمات يطلبها الناس ولا نقدّمها</h2></header>';
    if (!top) opp += '<p class="v3-none">لم يظهر طلب متكرّر لا نقدّم له خدمة حتى الآن.</p>';
    else {
      opp += '<div class="v2r-otop"><div><b class="v2r-ol">' + esc(top.label) + ': ' + esc(UU(top.count || 0, ['سؤال واحد', 'سؤالان', 'أسئلة', 'سؤالًا'])) + '</b>'
        + (top.sample_question ? '<p class="v2r-os">مثال: ' + esc(top.sample_question) + '</p>' : '') + '</div>'
        + '<button type="button" class="v3-btn1" data-a="open" data-sec="courses">افتح الدورات</button></div>'
        + restU.map(function (u) { return '<div class="v2r-orow"><span><b>' + esc(u.label) + '</b> · ' + esc(UU(u.count || 0, ['سؤال واحد', 'سؤالان', 'أسئلة', 'سؤالًا'])) + '</span><a href="#" class="v2r-inl" data-a="open" data-sec="courses">← افتح الدورات</a></div>'; }).join('');
    }
    opp += '<p class="v3-fine">من كل الأسئلة منذ البداية</p></section>';
    var rowsHtml = filtered.length ? filtered.map(function (r) {
      var chips = [segLabel(r.segment), countryLabel(r.country)];
      if (r.category) chips.push(catLabel(r.category));
      var meta = chips.map(function (c) { return '<span>' + esc(c) + '</span>'; }).join('')
        + (r.needs_expert ? '<span class="need">تحتاج خبيرًا</span>' : '') + '<span>' + (r.anonymous ? 'زائر' : 'عضو') + '</span>' + (r.id ? '<span class="go">افتح المحادثة ←</span>' : '');
      var inner = '<span class="v2r-qt">' + esc(r.question || '') + '</span><span class="v2r-qm">' + meta + '</span>';
      return r.id ? '<li><button type="button" class="v2r-q" data-a="thread" data-id="' + esc(r.id) + '">' + inner + '</button></li>' : '<li><div class="v2r-q static">' + inner + '</div></li>';
    }).join('') : '<li class="v3-none">' + (recent.length ? 'لا أسئلة تطابق التصفية' : 'لا أسئلة بعد') + '</li>';
    var recentCard = '<section class="v3-card v2r-card v2r-recent" id="v2rRecent"><header class="v3-ch v2r-rh"><h2>أحدث الأسئلة <span class="v3-cnt">' + esc(ar(filtered.length)) + '</span></h2><p>آخر ٤٠ سؤالًا تصل من المنصة</p></header>'
      + '<div class="v2r-fbar2"><button type="button" class="v2r-chip' + (f.ne === 'all' ? ' on' : '') + '" data-a="ne" data-v="all" aria-pressed="' + (f.ne === 'all') + '">الكل</button>'
      + '<button type="button" class="v2r-chip' + (f.ne === 'yes' ? ' on' : '') + '" data-a="ne" data-v="yes" aria-pressed="' + (f.ne === 'yes') + '">تحتاج خبيرًا</button>'
      + '<button type="button" class="v3-btn2 v2r-ftog" data-a="ftoggle" aria-expanded="' + (S.d.panel ? 'true' : 'false') + '">تصفية' + (hidden ? ' (' + esc(ar(hidden)) + ')' : '') + ' ▾</button>'
      + (hidden || f.ne === 'yes' ? '<a href="#" class="v2r-inl" data-a="fclear">امسح التصفية</a>' : '') + '</div>'
      + (S.d.panel ? '<div class="v2r-fpanel">' + filterPanelHtml(d, false) + '</div>' : '')
      + '<ul class="v2r-ql">' + rowsHtml + '</ul></section>';
    var emptyCls = unclassified ? 'لم تُصنَّف الأسئلة بعد — اضغط «صنّف الأسئلة الجديدة»' : 'لا بيانات بعد';
    var segs = arr(d.by_segment), segSorted = segs.filter(function (x) { return x.segment && x.segment !== 'unknown'; }).concat(segs.filter(function (x) { return !x.segment || x.segment === 'unknown'; }));
    var cats = arr(d.by_category), subs = arr(d.by_subcategory);
    var sub = subs.length ? '<div class="v2r-subs"><b>أكثر المجالات الفرعية</b><div class="v2r-chips">' + subs.slice(0, 10).map(function (x) { return '<span class="v2r-pill">' + esc(x.subcategory || 'غير محدد') + ' <b>' + esc(ar(x.count || 0)) + '</b></span>'; }).join('') + '</div></div>' : '';
    function dcard(title, inner) { return '<section class="v3-card v2r-card"><header class="v3-ch"><h3 class="v2r-h3">' + esc(title) + '</h3></header>' + (inner || '<p class="v3-none">' + esc(emptyCls) + '</p>') + '</section>'; }
    var openAttr = window.innerWidth >= 1024 && S.d.detailOpen !== false || S.d.detailOpen === true ? ' open' : '';
    var detail = '<details class="v2r-detail"' + openAttr + '><summary>التفصيل: حسب الشريحة والبلد والمجال والمطلوب</summary><p class="v3-fine">على كل الأسئلة · اضغط للتصفية</p><div class="v2r-dgrid">'
      + dcard('حسب الشريحة', barList(segSorted, 'segment', segLabel, 'seg', '#C8870E'))
      + dcard('حسب البلد', barList(arr(d.by_country), 'country', countryLabel, 'country', '#0E8E9B'))
      + dcard('حسب المجال القانوني', (cats.length ? barList(cats, 'category', function (x) { return catLabel(x) || 'غير محدد'; }, 'cat', '#6E59C7') + sub : ''))
      + dcard('حسب المطلوب', barList(arr(d.by_intent), 'intent', intentLabel, null, '#1C9A5B')) + '</div></details>';
    v.innerHTML = '<div class="v3 v2r v2r-demand" data-tab="demand">' + noteStrip() + numsLine + opp + recentCard + detail + '</div>';
    wire(v, d);
    var det = q('.v2r-detail', v); if (det) det.addEventListener('toggle', function () { S.d.detailOpen = det.open; });
  }

  // ------------------------------------------------------------------ تبويب «تقرير الأحد»
  function drawSunday(v) {
    var w = S.weekly, d = w.data;
    if (w.state === 'idle' || (w.state === 'loading' && !d)) { v.innerHTML = '<div class="v3 v2r" data-tab="sunday">' + loadingBlock('جارٍ جمع التقرير') + '</div>'; return wire(v, null); }
    if (!d) {
      v.innerHTML = '<div class="v3 v2r" data-tab="sunday"><div class="v3-empty"><b>التقرير: ' + NA + '</b><p>' + esc(w.err || 'تعذّر الجمع الآن، فلا تعتبر الأرقام صفرًا.') + '</p><button type="button" class="v3-btn2" data-a="wretry">أعد المحاولة</button></div></div>';
      return wire(v, null);
    }
    var dl = d.delivery || {};
    var nav = d.nav || {};
    var head = '<div class="v2r-wh"><div class="v2r-wt"><h2>تقرير الأسبوع</h2><p class="v3-ptxt">' + esc(d.week.label) + '، مقارنة بالأسبوع الذي قبله</p></div>'
      + '<div class="v2r-wn"><button type="button" class="v3-btn2" data-a="wprev"' + (nav.prev ? '' : ' disabled') + '>الأسبوع السابق</button><button type="button" class="v3-btn2" data-a="wnext"' + (nav.next ? '' : ' disabled') + '>الأسبوع التالي</button></div>'
      + '<div class="v2r-wa"><button type="button" class="v3-btn1 v2r-print" data-a="print">نزّل التقرير</button><button type="button" class="v3-btn2" data-a="copy">انسخ النص</button></div></div>';
    var absent = dl.bridge === 'absent';
    var panel = '<section class="v3-card v2r-card v2r-dp" aria-label="الإرسال كل أحد"><header class="v3-ch"><h2>الإرسال كل أحد</h2></header><p class="v2r-dstat">' + esc(V.deliveryText(dl)) + '</p>'
      + '<div class="v2r-dact"><button type="button" class="v3-btn2" data-a="dtoggle"' + (absent ? ' disabled' : '') + '>' + (dl.setting ? 'أوقف الإرسال' : 'شغّل الإرسال') + '</button>'
      + '<button type="button" class="v3-btn2" data-a="dsend"' + (absent ? ' disabled' : '') + '>أرسل الآن إلى تليجرام</button></div></section>';
    var nums = '';
    var fn = d.funnel;
    if (fn) {
      var c = V.funnelCompact(fn.stages);
      nums = '<section class="v2r-lt"><h3>الأرقام</h3><ul class="v2r-crows">' + c.rows.map(function (s) {
        var idx = fn.stages.indexOf(s), pk = idx > 0 && isNum(fn.stages[idx - 1].cur) ? fn.stages[idx - 1] : null, vw = V.stageView(s, pk);
        return '<li class="v2r-cr"><span class="v2r-fl">' + esc(s.label) + '</span><b class="v2r-fn">' + (isNum(s.cur) ? esc(ar(s.cur)) : naText()) + '</b>' + (vw.changeText ? '<span class="v2r-chg t-' + esc(vw.tone) + '">' + esc(vw.changeText) + '</span>' : '') + '</li>'; }).join('')
        + '</ul>' + (c.missing ? '<p class="v2r-cmiss">' + esc(c.text) + '</p>' : '') + '</section>';
    }
    var letter = '<article class="v2r-letter">' + printHead({ scope: 'all', window: { label: d.week.label }, generated_at: d.generated_at })
      + '<section class="v2r-lt"><h3>ملخص العقل</h3>' + brainStrip(d.brain, d.brain_primary, d.week.label).replace(/<section class="v2r-brain"/, '<div class="v2r-brain inline"').replace(/<\/section>$/, '</div>') + '</section>'
      + nums + '<section class="v2r-lt"><h3>كل قسم في سطر</h3><div class="v2r-rows">' + SECTION_ORDER.map(function (k) { var r = (d.sections || []).filter(function (x) { return x.key === k; })[0]; return r ? secRow(r, true) : ''; }).join('') + '</div></section></article>';
    v.innerHTML = '<div class="v3 v2r v2r-week" data-tab="sunday">' + noteStrip() + head + warnStrip(d.sources) + panel + letter + '</div>';
    wire(v, d);
  }

  // ------------------------------------------------------------------ الرسم والربط
  function redraw() {
    if (!S.view || !active()) return;
    if (document.getElementById('epModal')) return;                 // لا نعيد الرسم تحت ورقة مفتوحة
    var tab = MODS[host().current()];
    S.mod = host().current();
    var v = S.view, keepY = window.scrollY, ae = document.activeElement, sel = '';
    if (ae && ae.getAttribute && v.contains(ae) && ae.getAttribute('data-a')) {
      sel = '[data-a="' + ae.getAttribute('data-a') + '"]' + (ae.getAttribute('data-scope') ? '[data-scope="' + ae.getAttribute('data-scope') + '"]' : '') + (ae.getAttribute('data-period') ? '[data-period="' + ae.getAttribute('data-period') + '"]' : '');
    }
    if (tab === 'report') drawReport(v); else if (tab === 'demand') drawDemand(v); else drawSunday(v);
    var shell = q('.app'); if (shell) shell.classList.add('v2-bare');
    if (sel) { var again = q(sel, v); if (again && again.focus) { try { again.focus({ preventScroll: true }); } catch (e) {} } }
    if (window.scrollY !== keepY) window.scrollTo(0, keepY);
  }

  function wire(v, data) {
    qa('[data-a]', v).forEach(function (el) {
      var a = el.getAttribute('data-a');
      if (a === 'scopesel') { el.onchange = function () { navigate(el.value, S.period); }; return; }
      el.onclick = function (ev) { if (el.tagName === 'A') ev.preventDefault(); act(a, el, data); };
    });
    qa('[data-f]', v).forEach(function (el) {
      if (el.tagName === 'SELECT') el.onchange = function () { S.d.f[el.getAttribute('data-f')] = el.value; redraw(); };
      else el.onclick = function () {
        var dim = el.getAttribute('data-f'), val = el.getAttribute('data-v');
        S.d.f[dim] = (dim === 'ne' && S.d.f[dim] === val) ? 'all' : val; redraw();
      };
    });
    if (data && data.daily && !data.daily.na) { wireChart(v, data); fitChart(v); }
  }
  // مقاس الرسم = مقاس بطاقته بالبكسل (فلا يتمدّد الخط والنص): نقيس بعد الرسم ونعيد الرسم مرة واحدة لو اختلف.
  function fitChart(v) {
    var svg = q('.v2r-svg', v); if (!svg) return;
    var w = Math.round(svg.getBoundingClientRect().width), h = window.innerWidth <= 600 ? 220 : 300;
    if (w < 200) return;
    if (Math.abs(w - (S.cw || 560)) > 12 || h !== (S.chh || 300)) { S.cw = w; S.chh = h; redrawSoon(); }
  }

  function act(a, el, data) {
    var tab = MODS[host().current()];
    if (a === 'scope') { if (el.getAttribute('data-open')) return openSec(el.getAttribute('data-open')); return navigate(el.getAttribute('data-scope'), S.period); }
    if (a === 'period') return navigate(S.scope, el.getAttribute('data-period'));
    if (a === 'print') { try { window.print(); } catch (e) {} return; }
    if (a === 'why') { S.why = !S.why; return redraw(); }
    if (a === 'open') return openSec(el.getAttribute('data-sec'), el.getAttribute('data-tab'));
    if (a === 'refresh') return loadSummary('fresh');
    if (a === 'retry') return loadSummary('fresh');
    if (a === 'wretry') return loadWeekly(S.weekly.week);
    if (a === 'dretry') { var E = ep(); if (E) E.reload('analysis', redrawSoon); return; }
    if (a === 'ne') { S.d.f.ne = el.getAttribute('data-v'); return redraw(); }
    if (a === 'ftoggle') return openFilters(data);
    if (a === 'fclear') { S.d.f = { seg: 'all', country: 'all', cat: 'all', ne: 'all', time: 'all' }; return redraw(); }
    if (a === 'drill') {
      var dim = el.getAttribute('data-dim'), val = el.getAttribute('data-val');
      S.d.f[dim] = S.d.f[dim] === val ? 'all' : val; redraw();
      var rc = document.getElementById('v2rRecent'); if (rc && rc.scrollIntoView) rc.scrollIntoView({ behavior: 'smooth', block: 'start' });
      return;
    }
    if (a === 'thread') return openThread(el.getAttribute('data-id'));
    if (a === 'classify') return openClassify(data);
    if (a === 'wprev') return loadWeekly(data.nav.prev);
    if (a === 'wnext') return loadWeekly(data.nav.next);
    if (a === 'copy') return copyText(data);
    if (a === 'dtoggle') return toggleDelivery(data);
    if (a === 'dsend') return sendNow(data);
  }

  // ------------------------------------------------------------------ التصفية (ورقة على الموبايل)
  function openFilters(d) {
    if (window.innerWidth >= 1024) { S.d.panel = !S.d.panel; return redraw(); }
    var sh = sheetApi().openSheet; if (!sh) return;
    var s = sh('تصفية الأسئلة', filterPanelHtml(d, true));
    if (!s) return;
    s.classList.add('v2r-sheet');
    function readBack() {
      qa('[data-f]', s).forEach(function (el) { if (el.tagName === 'SELECT') S.d.f[el.getAttribute('data-f')] = el.value; });
    }
    qa('[data-f]', s).forEach(function (el) {
      if (el.tagName !== 'SELECT') el.onclick = function () {
        var dim = el.getAttribute('data-f'), val = el.getAttribute('data-v');
        S.d.f[dim] = (dim === 'ne' && S.d.f[dim] === val) ? 'all' : val;
        qa('[data-f="' + dim + '"][data-v]', s).forEach(function (b) { var on = S.d.f[dim] === b.getAttribute('data-v'); b.classList.toggle('on', on); b.setAttribute('aria-pressed', on ? 'true' : 'false'); });
      };
    });
    q('[data-a="applyf"]', s).onclick = function () { readBack(); window.closeModal(); redraw(); };
  }

  // ------------------------------------------------------------------ المحادثة
  function openThread(id) {
    var sh = sheetApi().openSheet, E = ep(); if (!sh || !E || !id) return;
    var s = sh('المحادثة', '<p class="v3-load">…جارٍ فتح المحادثة</p>');
    if (!s) return;
    s.classList.add('v2r-sheet', 'v2r-side');
    function onKey(e) { if (e.key === 'Escape') { window.closeModal(); } }
    document.addEventListener('keydown', onKey);
    var obs = new MutationObserver(function () { if (!document.body.contains(s)) { document.removeEventListener('keydown', onKey); obs.disconnect(); } });
    obs.observe(document.body, { childList: true });
    function load() {
      var mb = q('.v3m', s); if (mb) mb.innerHTML = '<p class="v3-load">…جارٍ فتح المحادثة</p>';
      E.api('/platform-chat-insights/' + encodeURIComponent(id)).then(function (d) {
        if (!document.body.contains(s)) return;
        var mb2 = q('.v3m', s); if (!mb2) return;
        var idn = d.identity, who;
        if (idn && idn.email) who = '<a class="v3-person" href="' + esc(L.sectionHash('people', 'person', idn.email)) + '" data-person="' + esc(idn.email) + '">' + esc(idn.full_name || idn.email) + '</a>';
        else who = 'زائر بلا حساب';
        var meta = [d.category ? catLabel(d.category) : '', /[\u0600-\u06ff]/.test(d.intent || '') ? d.intent : ''].filter(Boolean).map(esc).join(' · ');
        var msgs = Array.isArray(d.messages) ? d.messages : [];
        var turns = msgs.length ? msgs.map(function (m) {
          var me = m.role === 'user';
          return '<div class="v2r-tb ' + (me ? 'me' : 'bot') + '"><b>' + (me ? 'صاحب السؤال' : 'بروف') + '</b><p>' + esc(m.content || '') + '</p></div>';
        }).join('') : '<p class="v3-none">لا رسائل محفوظة</p>';
        mb2.innerHTML = (d.truncated ? '<div class="v3-warn">هذه نسخة محفوظة من الرد وليست المحادثة كاملة: جلسة الزائر لا تُحفظ، والأسئلة الأقدم بلا رد محفوظ.</div>' : '')
          + '<dl class="v2r-meta"><div><dt>صاحب السؤال</dt><dd>' + who + '</dd></div>' + (meta ? '<div><dt>التصنيف</dt><dd>' + meta + '</dd></div>' : '')
          + '<div><dt>التاريخ</dt><dd>' + esc(U.dateText(d.created_at) || NA) + '</dd></div></dl><div class="v2r-turns">' + turns + '</div>'
          + '<button type="button" class="v3-btn2 v2r-close" data-a="sclose">أغلق</button>';
        q('[data-a="sclose"]', mb2).onclick = function () { window.closeModal(); };
        var pl = q('[data-person]', mb2);
        if (pl) pl.onclick = function (e) { e.preventDefault(); var em = pl.getAttribute('data-person'); window.closeModal(); if (host().openPerson) host().openPerson(em); };
      }).catch(function () {
        var mb3 = q('.v3m', s); if (!mb3) return;
        mb3.innerHTML = '<div class="v3-err">تعذّر فتح المحادثة</div><button type="button" class="v3-btn2" data-a="sretry">أعد المحاولة</button>';
        q('[data-a="sretry"]', mb3).onclick = load;
      });
    }
    load();
  }

  // ------------------------------------------------------------------ تصنيف الأسئلة (له تكلفة: ورقة تأكيد)
  function openClassify(d) {
    var sh = sheetApi().openSheet, E = ep(); if (!sh || !E) return;
    var un = (d && d.unclassified) || 0, n = Math.min(un, 100);
    var s = sh('تصنيف الأسئلة الجديدة', '<p class="mc-lead">سيُصنَّف ' + esc(UU(n, ['سؤال واحد', 'سؤالان', 'أسئلة', 'سؤالًا'])) + ' جديدًا (١٠٠ بالكثير في المرة). التصنيف يعمل على المنصة وله تكلفة صغيرة.</p>'
      + '<div id="v2rcerr" role="alert"></div><div class="acts"><button type="button" class="v3-btn1" data-a="cgo">صنّف الآن</button><button type="button" class="v3-btn2" data-a="cno">رجوع</button></div>');
    if (!s) return;
    s.classList.add('v2r-sheet');
    q('[data-a="cno"]', s).onclick = function () { if (!s.dataset.busy) window.closeModal(); };
    var go = q('[data-a="cgo"]', s);
    go.onclick = function () {
      if (go.dataset.busy) return;
      go.dataset.busy = '1'; s.dataset.busy = '1'; go.disabled = true; go.textContent = '…جارٍ التصنيف';
      E.api('/platform-chat-insights/classify?limit=100', { method: 'POST', body: {} }).then(function (r) {
        delete s.dataset.busy;
        if (r && r.error) throw new Error('x');
        window.closeModal();
        var c = (r && r.classified) || 0, rem = r && r.remaining;
        setNote('صُنّف ' + UU(c, ['سؤال واحد', 'سؤالان', 'أسئلة', 'سؤالًا']) + ' جديدًا' + (rem ? ' · بقي ' + ar(rem) : ''));
        E.reload('analysis', redrawSoon);
      }).catch(function () {
        delete s.dataset.busy; delete go.dataset.busy; go.disabled = false; go.textContent = 'صنّف الآن';
        var ce = q('#v2rcerr', s); if (ce) ce.innerHTML = '<div class="v3-err">تعذّر التصنيف الآن، جرّب بعد قليل</div>';
      });
    };
  }

  // ------------------------------------------------------------------ تقرير الأحد: نسخ وإرسال
  function copyText(d) {
    var t = d && d.text; if (!t) return;
    function done() { setNote('نُسخ نص التقرير'); redraw(); }
    function fallback() {
      var ta = document.createElement('textarea'); ta.readOnly = true; ta.value = t; ta.className = 'v2r-copybox'; ta.setAttribute('aria-label', 'نص التقرير');
      var holder = q('.v2r-week'); if (holder) { holder.insertBefore(ta, holder.firstChild); ta.focus(); ta.select(); }
    }
    try {
      if (navigator.clipboard && navigator.clipboard.writeText) navigator.clipboard.writeText(t).then(done, fallback); else fallback();
    } catch (e) { fallback(); }
  }
  function toggleDelivery(d) {
    var tw = sheetApi().twoStage, E = ep(); if (!tw || !E) return;
    var on = !!(d.delivery && d.delivery.setting), target = !on;
    var s = tw({
      title: target ? 'تشغيل الإرسال كل أحد' : 'إيقاف الإرسال كل أحد',
      form: '<p class="mc-lead">' + (target ? 'سيصلك تقرير الأسبوع كل أحد ٨ صباحًا على تليجرام، بعد أن تجهّز المنصة الإرسال.' : 'لن يُرسل تقرير الأسبوع إلى تليجرام بعد الآن، ويبقى متاحًا هنا.') + '</p>',
      collect: function () { return { ok: true, payload: { enabled: target } }; },
      review: function (p) { return { lead: 'راجع ما سيتغير قبل التأكيد', lines: [{ label: 'الإرسال كل أحد', from: on ? 'يعمل' : 'متوقف', to: p.enabled ? 'يعمل' : 'متوقف' }], changed: true }; },
      btnReview: 'راجع', btnConfirm: 'أكّد', busy: 'جارٍ الحفظ…',
      send: function (p) { return E.api('/v2/reports/weekly/settings', { method: 'PUT', body: { enabled: p.enabled, confirmed: true } }); },
      onOk: function () { setNote(target ? 'تم تشغيل الإرسال كل أحد' : 'تم إيقاف الإرسال كل أحد'); loadWeekly(S.weekly.week); redraw(); }
    });
    if (s) s.classList.add('v2r-sheet');
  }
  function sendNow(d) {
    var tw = sheetApi().twoStage, E = ep(); if (!tw || !E) return;
    var first = String(d.text || '').split('\n').slice(0, 6).map(esc).join('<br>');
    var s = tw({
      title: 'إرسال تقرير الأسبوع',
      form: '<p class="mc-lead">سيُرسل تقرير ' + esc(d.week.label) + ' إلى تليجرام الآن.</p>',
      collect: function () { return { ok: true, payload: { week: d.week.start } }; },
      review: function (p) {
        var sentBefore = !!(d.delivery && d.delivery.last_sent_week && d.delivery.last_sent_week === d.week.start);
        return { lead: 'راجع ما سيُرسل قبل التأكيد', changed: true, heads: ['البند', 'الآن', 'بعد الإرسال'],
                 lines: [{ label: 'الأسبوع', from: sentBefore ? 'أُرسل من قبل' : 'لم يُرسل بعد', to: d.week.label }, { label: 'القناة', from: 'لا شيء', to: 'تليجرام' }],
                 extra: '<div class="v2r-preview">' + first + '</div>' };
      },
      btnReview: 'راجع', btnConfirm: 'أكّد الإرسال', busy: 'جارٍ الإرسال…',
      send: function (p) { return E.api('/v2/reports/weekly/send', { method: 'POST', body: { week: p.week, confirmed: true } }); },
      onOk: function (res) { setNote(res && res.already ? 'أُرسل تقرير هذا الأسبوع من قبل' : 'أُرسل التقرير'); loadWeekly(S.weekly.week); redraw(); }
    });
    if (s) s.classList.add('v2r-sheet');
  }

  // ------------------------------------------------------------------ نقطة الدخول
  R.render = function (mod, view) {
    S.view = view; S.mod = mod;
    var tab = MODS[mod];
    if (tab === 'report') {
      if (syncFromRoute() === 'redirect') return;
      loadSummary(false);
    } else if (tab === 'demand') { ensureDemand(); }
    else { if (S.weekly.state === 'idle' || S.weekly.state === 'error') loadWeekly(''); else if (Date.now() - S.weekly.at > 60000) loadWeekly(S.weekly.week); }
    redraw();
    if (!S.poll) {
      S.poll = setInterval(function () {
        if (!active()) return;
        var m = MODS[host().current()];
        if (m === 'report') {
          var e = entry(ckey());
          if (document.visibilityState !== 'hidden' && e.at && Date.now() - e.at > STALE_MS) loadSummary(false);
          var ft = q('.v2r-fresh-t'); if (ft && e.at) ft.textContent = agoLine(e.at);
        }
      }, 30000);
    }
  };
  R._state = S;
  R._tick = function (t) { S.nowOverride = t || 0; };
})();
