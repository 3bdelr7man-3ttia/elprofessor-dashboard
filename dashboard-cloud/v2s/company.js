/* ============================================================================
 * v2s/company.js — الجولة الأخيرة: قسم «الشركة ورأس المال» (نظرة · الشركاء ورأس المال · المعدات والاشتراكات · الاتفاقات والرعاة ·
 * عملاء الإعلانات · الإعدادات). ⛔ لا منطق عمل هنا: الأرقام والشارات والسطور من `V2L.co` (نقي)، والحساب الوحيد للمستحق على الخادم.
 * ⛔ المفتاح مقفول افتراضيًا: الملف بيتحمّل دايمًا لكنه ما بيرسم شيئًا إلا لو index.html نادى `V2SEC.company.render` (والغلاف الجديد شغّال).
 * ⛔ كل حركة فلوس بتعدّي على ورقة بمرحلتين «راجع ⇒ أكّد» والتأكيد الصريح `confirmed:true` بيروح للخادم.
 * ⛔ مصدر فشل ⇒ «غير متاح بعد» (data-na) — لا صفر. وكل مصدر بيفشل لوحده.
 * ========================================================================== */
(function () {
  'use strict';
  var L = window.V2L;
  if (!L || !L.co) return;
  var CO = L.co, U = L.util, NA = CO.NA;
  var SECS = window.V2SEC = window.V2SEC || {};
  var MODS = { investment: 1, targets: 1, settings: 1, v2c_partners: 1, v2c_assets: 1, v2c_deals: 1, v2c_ads: 1 };
  var S = { view: null, mod: '', sig: '', poll: null, minute: null, note: null, noteT: null, jump: null, hl: null, filt: 'all', nowOverride: 0, sheetBusy: false,
            oldTargets: false, auditN: 20, auditOpen: false, redirected: '' };
  var SESSION_AR = 'انتهت الجلسة — سجّل الدخول من جديد ثم جرّب';
  var FAIL_AR = 'تعذّر تنفيذ العملية';
  var LOST_AR = 'لم يصلنا رد — تأكّد من القائمة قبل المحاولة مرة أخرى.';
  var COLORS = ['#9E2B4E', '#1F4E79', '#2E6B5A', '#8F5F00', '#5A4E8C'];
  var RESERVE_COLOR = '#D9CFC2';

  function esc(s) { return String(s == null ? '' : s).replace(/[&<>"']/g, function (c) { return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]; }); }
  function host() { return window.V2_HOST || {}; }
  function ep() { return window.EP || null; }
  function img(n) { return 'v2/img/' + n + '.jpg'; }
  function now() { return S.nowOverride || Date.now(); }
  function q(sel, root) { return (root || document).querySelector(sel); }
  function qa(sel, root) { return Array.prototype.slice.call((root || document).querySelectorAll(sel)); }
  function na() { return '<span class="co-na" data-na="1">' + NA + '</span>'; }
  function lines(list) { return CO.sumLines(list); }
  function money(a, c) { return U.moneyText(a, c || 'EGP'); }
  function arN(n) { return U.ar(n); }
  function rid() { var a = new Uint8Array(12), s = ''; try { (window.crypto || window.msCrypto).getRandomValues(a); } catch (e) { for (var i = 0; i < 12; i++) a[i] = Math.floor(Math.random() * 256); } for (var j = 0; j < a.length; j++) s += (a[j] + 256).toString(16).slice(1); return 'co' + s; }
  function todayIso() { var d = new Date(now()); return d.getFullYear() + '-' + ('0' + (d.getMonth() + 1)).slice(-2) + '-' + ('0' + d.getDate()).slice(-2); }
  function addDaysIso(iso, n) { var m = /^(\d{4})-(\d{2})-(\d{2})$/.exec(iso || ''); if (!m) return ''; var d = new Date(+m[1], +m[2] - 1, +m[3] + n); return d.getFullYear() + '-' + ('0' + (d.getMonth() + 1)).slice(-2) + '-' + ('0' + d.getDate()).slice(-2); }
  function diffDays(a, b) { var x = /^(\d{4})-(\d{2})-(\d{2})$/.exec(a || ''), y = /^(\d{4})-(\d{2})-(\d{2})$/.exec(b || ''); if (!x || !y) return null; return Math.round((Date.UTC(+y[1], +y[2] - 1, +y[3]) - Date.UTC(+x[1], +x[2] - 1, +x[3])) / 86400000); }

  // ------------------------------------------------------------------ المصادر (كلٌّ تفشل لوحدها)
  var SRC = {};
  var PATHS = {
    summary: '/v2/company/summary', partners: '/partners', contribs: '/v2/company/contributions', cash: '/cashflow', invest: '/investments',
    opps: '/investment-opportunities', wd: '/admin/withdrawals', assets: '/assets', subs: '/v2/company/subscriptions', deals: '/v2/company/agreements',
    ads: '/v2/company/ad-clients', ledger: '/v2/ads-ledger', forecast: '/forecast', dash: '/dashboard'
  };
  var LABEL = { summary: 'ملخّص الشركة', partners: 'الشركاء', contribs: 'دفعات الشركاء', cash: 'حركات رأس المال', invest: 'سجل الاستثمارات', assets: 'المعدات',
                subs: 'الاشتراكات', deals: 'الاتفاقات', ads: 'عملاء الإعلانات', ledger: 'أرصدة الإعلانات', forecast: 'الأهداف الشهرية', dash: 'الدفتر المالي', visits: 'الزيارات' };
  var SILENT = { opps: 1, wd: 1 };
  function srcOf(k) { return SRC[k] || (SRC[k] = { state: 'idle', data: null, status: 0, seq: 0 }); }
  function load(k, force) {
    var s = srcOf(k), E = ep();
    if (!E || !E.api || !E.authed || !PATHS[k]) return;
    if (s.state === 'loading' && !force) return;
    if (!force && s.state !== 'idle') return;
    s.state = 'loading';
    var seq = ++s.seq;
    E.api(PATHS[k]).then(function (d) {
      if (seq !== s.seq) return;
      s.state = 'ready'; s.data = d; changed();
    }).catch(function (e) {
      if (seq !== s.seq) return;
      if (e && e.status === 401) return;
      s.state = e && e.status === 404 ? 'closed' : 'error'; s.status = (e && e.status) || 0; s.data = null; changed();
    });
  }
  function data(k) { var s = srcOf(k); return s.state === 'ready' ? s.data : null; }
  function srcState(k) { return srcOf(k).state; }
  function isLoad(k) { var t = srcState(k); return t === 'idle' || t === 'loading'; }
  function loadMany(keys, force) { keys.forEach(function (k) { load(k, force); }); }
  function items(k) { var d = data(k); return d && Array.isArray(d.items) ? d.items : null; }
  function listOf(k) { var d = data(k); return Array.isArray(d) ? d : null; }
  function failed(keys) { return keys.filter(function (k) { return !SILENT[k] && (srcState(k) === 'error' || srcState(k) === 'closed'); }).map(function (k) { return LABEL[k]; }); }
  function retryFailed() {
    Object.keys(PATHS).forEach(function (k) { if (srcState(k) === 'error' || srcState(k) === 'closed') load(k, true); });
    if (V.state === 'error') loadVisits(true);
  }

  // زيارات الأكواد (جسر المنصة: قد لا يكون مفعّلًا بعد ⇒ enabled:false وهذا ليس فشلًا)
  var V = { state: 'idle', key: '', map: {} };
  function visitCodes() {
    var c = [];
    (items('deals') || []).forEach(function (a) { if (a.status === 'active' && a.ref_code && c.indexOf(a.ref_code) < 0) c.push(a.ref_code); });
    (items('ads') || []).forEach(function (a) { if (a.status === 'active' && a.ref_code && c.indexOf(a.ref_code) < 0) c.push(a.ref_code); });
    return c;
  }
  function loadVisits(force) {
    var E = ep();
    if (!E || !E.api || !E.authed) return;
    if (!items('deals') && !items('ads')) return;
    var codes = visitCodes();
    if (!codes.length) { if (V.state !== 'none') { V.state = 'none'; V.key = ''; } return; }
    var key = codes.join(',');
    if (!force && V.key === key && V.state !== 'idle') return;
    var from = todayIso().slice(0, 8) + '01';
    (items('deals') || []).forEach(function (a) { if (a.status === 'active' && a.ref_code && a.starts_on && a.starts_on < from) from = a.starts_on; });
    (items('ads') || []).forEach(function (a) { var d = (a.created_at || '').slice(0, 10); if (a.status === 'active' && a.ref_code && d && d < from) from = d; });
    V.key = key; V.state = 'loading';
    var seq = V.seq = (V.seq || 0) + 1;
    E.api('/v2/company/visits?codes=' + encodeURIComponent(key) + '&from=' + from + '&to=' + todayIso()).then(function (d) {
      if (seq !== V.seq) return;
      V.map = {};
      ((d && d.items) || []).forEach(function (x) { if (x && x.code) V.map[x.code] = x; });
      V.state = d && d.enabled === true ? 'on' : (d && d.enabled === false ? 'off' : 'none');
      changed();
    }).catch(function (e) { if (seq !== V.seq) return; if (e && e.status === 401) return; V.state = 'error'; changed(); });
  }
  function visitCounts() {
    var o = {};
    if (V.state === 'on') Object.keys(V.map).forEach(function (k) { if (V.map[k].tracked !== false && typeof V.map[k].visits === 'number') o[k] = V.map[k].visits; });
    return o;
  }
  function visitLine(code) {
    if (!code) return '';
    if (V.state === 'error') return '<span class="co-vis">الزيارات: ' + na() + '</span>';
    if (V.state !== 'on') return '';
    var it = V.map[code];
    if (!it || it.tracked === false) return '<span class="co-vis">لم يظهر هذا الكود في المنصة بعد</span>';
    return '<span class="co-vis">الزيارات: ' + esc(arN(it.visits || 0)) + '</span>';
  }
  function visitsStrip() {
    if (V.state === 'off') return '<div class="co-info" role="status">عدّ الزيارات بالكود لم يُفعَّل بعد.</div>';
    if (V.state === 'error') return warnStrip(['الزيارات']);
    return '';
  }

  // مصادر الداشبورد الموجودة
  function epState(k) { var E = ep(); return (E && E.state && E.state[k]) || 'idle'; }
  function epEnsure(keys) { var E = ep(); if (E && E.authed) keys.forEach(function (k) { E.ensure(k, null); }); }

  function signature() {
    return Object.keys(PATHS).map(function (k) { return srcOf(k).state + srcOf(k).seq; }).join(',') + '|' + V.state + V.key + '|'
      + ['settings', 'dashUsers', 'usage', 'aiModels', 'audit', 'users'].map(epState).join(',') + '|' + S.filt + '|' + S.auditN + '|' + S.auditOpen;
  }
  var redrawT = null;
  function changed() {
    try { if (window.V2SHELL && V2SHELL.on && V2SHELL.refresh) V2SHELL.refresh(); } catch (e) {}
    try { var nd = NEEDS[host().current ? host().current() : '']; if (nd && nd.visits) loadVisits(false); } catch (e) {}
    if (redrawT) return;
    redrawT = setTimeout(function () { redrawT = null; if (!document.getElementById('epModal')) redraw(); }, 0);
  }

  // ------------------------------------------------------------------ أجزاء مشتركة
  function warnStrip(labels) {
    if (!labels.length) return '';
    return '<div class="co-warn" role="status"><span>تعذّر جلب: ' + esc(labels.join('، ')) + ' — الأرقام الناقصة مكتوب مكانها «' + NA + '».</span>'
      + '<button type="button" class="co-btn2" data-a="retry">أعد المحاولة</button></div>';
  }
  function noteStrip() { return S.note ? '<div class="co-ok" role="status">' + esc(S.note) + '</div>' : ''; }
  function setNote(t) { S.note = t; clearTimeout(S.noteT); S.noteT = setTimeout(function () { S.note = null; redraw(); }, 12000); }
  function loadingBlock(t) { return '<div class="co-empty"><b>…جارٍ جلب ' + esc(t) + '</b></div>'; }
  function chip(c) { return c ? '<span class="co-st t-' + esc(c.tone || 'neutral') + '">' + esc(c.text) + '</span>' : ''; }
  function btn1(label, a, attrs) { return '<button type="button" class="co-btn1" data-a="' + a + '"' + (attrs || '') + '>' + esc(label) + '</button>'; }
  function btn2(label, a, attrs) { return '<button type="button" class="co-btn2" data-a="' + a + '"' + (attrs || '') + '>' + esc(label) + '</button>'; }
  function lnkc(label, a, cls, attrs) { return '<button type="button" class="co-link ' + cls + '" data-a="' + a + '"' + (attrs || '') + '>' + esc(label) + '</button>'; }
  function lnk(label, a, attrs) { return '<button type="button" class="co-link" data-a="' + a + '"' + (attrs || '') + '>' + esc(label) + '</button>'; }
  function card(title, head, body, cls, id) {
    return '<section class="co-card' + (cls ? ' ' + cls : '') + '"' + (id ? ' id="' + id + '"' : '') + '><header class="co-ch"><h2>' + esc(title) + '</h2>' + (head || '') + '</header>' + body + '</section>';
  }
  function stat(label, valueHtml, hint) {
    return '<div class="co-stat"><span>' + esc(label) + '</span><b>' + valueHtml + '</b>' + (hint ? '<small>' + esc(hint) + '</small>' : '') + '</div>';
  }
  function brainBlock(text, btnLabel, a, attrs) {
    return '<div class="co-bl"><img class="co-bav" src="' + img('brain-avatar') + '" alt=""><p>' + esc(text) + '</p>' + (btnLabel ? '<button type="button" class="co-blb" data-a="' + a + '"' + (attrs || '') + '>' + esc(btnLabel) + '</button>' : '') + '</div>';
  }
  function colorOf(rows, i, row) { return row && row.reserve ? RESERVE_COLOR : COLORS[i % COLORS.length]; }
  function equityBar(parts) {
    var idx = 0, segs = parts.rows.filter(function (r) { return r.equity > 0; }).map(function (r) {
      var c = r.reserve ? RESERVE_COLOR : COLORS[idx++ % COLORS.length];
      return '<i style="width:' + Math.min(100, r.equity) + '%;background:' + c + '" title="' + esc(r.name + ' ' + U.fmt(r.equity) + '٪') + '"></i>';
    }).join('');
    return '<div class="co-eq" role="img" aria-label="توزيع الحصص">' + segs + '</div>';
  }
  function partnerColor(parts, id) {
    var idx = 0, out = COLORS[0];
    parts.rows.forEach(function (r) { if (r.equity > 0) { var c = r.reserve ? RESERVE_COLOR : COLORS[idx++ % COLORS.length]; if (r.id === id) out = c; } });
    return out;
  }
  function moreBtn(title, kind, id) { return lnk('المزيد', 'more', ' data-k="' + kind + '" data-id="' + esc(id) + '"'); }

  // ------------------------------------------------------------------ الأوراق
  function arDigits(t) { return String(t).replace(/\d/g, function (d) { return '٠١٢٣٤٥٦٧٨٩'.charAt(+d); }); }
  function lost(e) { return !!e && (e.status == null || e.status === 0 || e.status === 500 || e.status === 502 || e.status === 503 || e.status === 504); }
  function errMsg(e) {
    if (e && e.status === 401) return SESSION_AR;
    if (lost(e)) return LOST_AR;
    var d = (e && e.data) || {};
    if (typeof d.error === 'string' && d.error) return arDigits(d.error);
    return FAIL_AR;
  }
  function openSheet(title, html) {
    if (typeof window.openModal !== 'function') return null;
    var s = window.openModal(title, '<div class="com">' + html + '</div>');
    var x = q('[data-x]', s);
    if (x) x.onclick = function () { if (!s.dataset.busy) window.closeModal(); };
    s.onclick = function (e) { if (e.target === s && !s.dataset.busy) window.closeModal(); };
    return s;
  }
  function rowsTable(rows) {
    return '<table class="co-diff"><thead><tr><th>البند</th><th>الآن</th><th>بعد</th></tr></thead><tbody>' + rows.map(function (r) {
      return '<tr><td>' + esc(r.label) + '</td><td>' + esc(r.from) + '</td><td><b>' + esc(r.to) + '</b></td></tr>'; }).join('') + '</tbody></table>';
  }
  // ورقة: نموذج ثم (اختياريًا) مراجعة ثم تأكيد. o: {title, form, wire(s), collect(s)→{ok,payload|error}, review(payload)→{lead, rows|items}, send(payload, opId)→Promise,
  //   onOk(res), onLost(), btnReview, btnConfirm, btnSave, danger:{label, run(s)}, wide}
  function sheet(o) {
    var s = openSheet(o.title, '<div class="co-s1"></div><div class="co-s2" hidden></div><div class="co-err" role="alert"></div><div class="co-acts"></div>');
    if (!s) return null;
    var s1 = q('.co-s1', s), s2 = q('.co-s2', s), er = q('.co-err', s), acts = q('.co-acts', s), op = rid(), payload = null, stage = 1;
    s1.innerHTML = o.form;
    function showErr(m) { er.innerHTML = m ? '<div class="co-errbox">' + esc(m) + '</div>' : ''; }
    function goStage1() {
      stage = 1; s1.hidden = false; s2.hidden = true; showErr('');
      acts.innerHTML = '<button type="button" class="co-btn1" data-s="go">' + esc(o.review ? (o.btnReview || 'راجع') : (o.btnSave || 'احفظ')) + '</button>'
        + '<button type="button" class="co-btn2" data-s="cancel">إلغاء</button>' + (o.danger ? '<button type="button" class="co-link co-del" data-s="danger">' + esc(o.danger.label) + '</button>' : '');
    }
    function goStage2(r) {
      stage = 2; s1.hidden = true; s2.hidden = false; showErr('');
      s2.innerHTML = '<p class="co-lead">' + esc(r.lead || 'راجع ما سيحدث قبل التأكيد') + '</p>'
        + (r.rows ? rowsTable(r.rows) : '') + (r.items ? '<ul class="co-rv">' + r.items.map(function (t) { return '<li>' + esc(t) + '</li>'; }).join('') + '</ul>' : '');
      acts.innerHTML = '<button type="button" class="co-btn1" data-s="confirm">' + esc(o.btnConfirm || 'أكّد') + '</button><button type="button" class="co-btn2" data-s="back">رجوع</button>';
    }
    function lock(on, label) {
      var b = q('[data-s="go"],[data-s="confirm"]', s);
      if (on) { s.dataset.busy = '1'; S.sheetBusy = true; qa('button', acts).forEach(function (x) { x.disabled = true; }); if (b) b.textContent = 'جارٍ الحفظ…'; }
      else { delete s.dataset.busy; S.sheetBusy = false; qa('button', acts).forEach(function (x) { x.disabled = false; }); if (b && label) b.textContent = label; }
    }
    function send() {
      var label = stage === 2 ? (o.btnConfirm || 'أكّد') : (o.btnSave || 'احفظ');
      lock(true); showErr('');
      Promise.resolve(o.send(payload, op)).then(function (res) { lock(false); window.closeModal(); o.onOk && o.onOk(res || {}); })
        .catch(function (e) { lock(false, label); showErr(errMsg(e)); if (lost(e) && o.onLost) o.onLost(); });
    }
    s.addEventListener('click', function (e) {
      var b = e.target.closest ? e.target.closest('[data-s]') : null;
      if (!b || !s.contains(b) || s.dataset.busy) return;
      var a = b.getAttribute('data-s');
      if (a === 'cancel') window.closeModal();
      else if (a === 'back') goStage1();
      else if (a === 'danger') o.danger.run(s);
      else if (a === 'go') {
        var c = o.collect(s);
        if (!c.ok) { showErr(c.error); return; }
        payload = c.payload;
        if (!o.review) { send(); return; }
        var r = o.review(payload);
        if (r.skip) { send(); return; }
        if (r.changed === false) { showErr('لم تغيّر أي شيء'); return; }
        goStage2(r);
      } else if (a === 'confirm') send();
    });
    goStage1();
    if (o.wire) o.wire(s);
    return s;
  }
  // سطر تأكيد واحد (إنهاء اتفاق · إيقاف حساب …): o: {title, lead, btn, danger, send(opId), onOk}
  function confirmSheet(o) {
    return sheet({ title: o.title, form: '<p class="co-lead">' + esc(o.lead) + '</p>', collect: function () { return { ok: true, payload: 1 }; }, btnSave: o.btn || 'أكّد', send: o.send, onOk: o.onOk, onLost: o.onLost });
  }
  // حذف سجل مالي: مرحلتان «راجع ⇒ أكّد»
  function delSheet(o) {
    return sheet({ title: o.title, form: '<p class="co-lead">' + esc(o.lead) + '</p>', collect: function () { return { ok: true, payload: 1 }; }, btnReview: 'راجع', btnConfirm: o.btn || 'أكّد الحذف',
      review: function () { return { lead: 'راجع قبل التأكيد', items: [o.lead] }; }, send: o.send, onOk: o.onOk, onLost: o.onLost });
  }
  // قائمة «المزيد»: أفعال كاملة العرض، والمدمّر آخرًا بنص أحمر
  function moreSheet(title, actions) {
    var s = openSheet(title, '<div class="co-more">' + actions.map(function (a, i) {
      return '<button type="button" class="co-btn2' + (a.danger ? ' co-dng' : '') + '" data-m="' + i + '">' + esc(a.label) + '</button>'; }).join('') + '</div>');
    if (!s) return;
    qa('[data-m]', s).forEach(function (b) { b.onclick = function () { var a = actions[+b.getAttribute('data-m')]; window.closeModal(); a.run(); }; });
  }

  // —— حقول النماذج
  function fld(label, inner, hint, id) { return '<div class="co-f"' + (id ? ' id="' + id + '"' : '') + '><label>' + esc(label) + '</label>' + inner + (hint ? '<small>' + esc(hint) + '</small>' : '') + '</div>'; }
  function inp(id, val, attrs) { return '<input id="' + id + '" type="text" autocomplete="off" value="' + esc(val == null ? '' : val) + '" ' + (attrs || '') + '>'; }
  function numInp(id, val, attrs) { return '<input id="' + id + '" type="text" inputmode="decimal" autocomplete="off" dir="ltr" value="' + esc(val == null ? '' : val) + '" ' + (attrs || '') + '>'; }
  function dateInp(id, val) { return '<input id="' + id + '" type="date" dir="ltr" value="' + esc(val || '') + '">'; }
  function area(id, val, max) { return '<textarea id="' + id + '" rows="2" maxlength="' + (max || 300) + '">' + esc(val || '') + '</textarea>'; }
  function sel(id, opts, cur, attrs) {
    return '<select id="' + id + '" ' + (attrs || '') + '>' + opts.map(function (o) { return '<option value="' + esc(o[0]) + '"' + (String(o[0]) === String(cur) ? ' selected' : '') + '>' + esc(o[1]) + '</option>'; }).join('') + '</select>';
  }
  function monthPick(id, mo, cur) {
    var m = /^(\d{4})-(\d{2})$/.exec(cur || mo.def) || /^(\d{4})-(\d{2})$/.exec(mo.def);
    var ys = mo.years.slice(); if (m && ys.indexOf(+m[1]) < 0) ys.unshift(+m[1]);
    return '<div class="co-mp">' + sel(id + '_m', mo.months.map(function (x) { return [x.v, x.t]; }), m ? m[2] : '01', 'aria-label="الشهر"')
      + sel(id + '_y', ys.map(function (y) { return [String(y), U.ar(y)]; }), m ? m[1] : String(ys[0]), 'aria-label="السنة"') + '</div>';
  }
  function readMonth(s, id) { return (q('#' + id + '_y', s).value || '') + '-' + (q('#' + id + '_m', s).value || ''); }
  function val(s, id) { var e = q('#' + id, s); return e ? String(e.value || '').trim() : ''; }
  function checked(s, id) { var e = q('#' + id, s); return !!(e && e.checked && !e.disabled); }
  // رقم من خانة: {ok, v, error}
  function readNum(s, id, label, o) {
    o = o || {};
    var t = val(s, id);
    if (t === '') return o.req ? { ok: false, error: 'اكتب ' + label } : { ok: true, v: null };
    var n = U.parseAmount(t);
    if (n === null || n !== n) return { ok: false, error: label + ' غير صالح — اكتب أرقامًا فقط' };
    if (o.pos && n <= 0) return { ok: false, error: label + ' لازم يكون أكبر من صفر' };
    if (o.max != null && n > o.max) return { ok: false, error: label + ' أكبر من الحد المسموح' };
    return { ok: true, v: n };
  }
  var CURS = [['EGP', 'جنيه'], ['USD', 'دولار']];
  var CURS_ALL = [['EGP', 'جنيه'], ['USD', 'دولار'], ['SAR', 'ريال سعودي'], ['AED', 'درهم'], ['KWD', 'دينار كويتي'], ['QAR', 'ريال قطري'], ['EUR', 'يورو'], ['GBP', 'جنيه إسترليني']];
  function pairOf(map) { return Object.keys(map).map(function (k) { return [k, map[k]]; }); }
  function afterWrite(text, keys) {
    setNote(text);
    loadMany((keys || []).concat(['summary']), true);
    var E = ep();
    redraw();
  }
  function api(method, path, body) { var E = ep(); return E.api(path, { method: method, body: body }); }
  function jumpTo(tab) { if (host().openSection) host().openSection('company', tab); }

  // ------------------------------------------------------------------ مساعدات العرض المشتركة
  function roleLabel(r) { return CO.ROLE_LABEL[r] || r || 'شريك'; }
  function sumPairs(pairs) {
    var acc = {};
    pairs.forEach(function (x) { if (x.amount) acc[x.currency] = (acc[x.currency] || 0) + Math.round(x.amount * 100); });
    return Object.keys(acc).sort(function (a, b) { return (a !== 'EGP') - (b !== 'EGP') || (a < b ? -1 : 1); }).map(function (k) { return { currency: k, amount: acc[k] / 100 }; });
  }
  function subsMonthly(subs) { return sumPairs((subs || []).filter(function (s) { return s.status === 'active' && s.cycle === 'monthly'; }).map(function (s) { return { currency: s.currency, amount: s.amount }; })); }
  function subsYearly(subs) { return sumPairs((subs || []).filter(function (s) { return s.status === 'active' && s.cycle === 'yearly'; }).map(function (s) { return { currency: s.currency, amount: s.amount }; })); }
  function subAmountText(s) {
    var c = s.cycle === 'monthly' ? 'شهريًا' : s.cycle === 'yearly' ? 'سنويًا' : (s.cycle_other || '');
    return money(s.amount, s.currency) + (c ? ' ' + c : '');
  }
  function brainStrip(sum) {
    var st = srcState('summary');
    if (!sum) {
      if (st === 'idle' || st === 'loading') return '<div class="co-brain">' + '<img class="co-bav" src="' + img('brain-avatar') + '" alt=""><p>…جارٍ جلب ملخّص الشركة</p></div>';
      return '<div class="co-brain"><img class="co-bav" src="' + img('brain-avatar') + '" alt=""><p>ملخّص الشركة ' + na() + '.</p><button type="button" class="co-blb" data-a="retry">أعد المحاولة</button></div>';
    }
    var ls = CO.brain(sum, now(), { visits: visitCounts() });
    S.brainLines = ls;
    if (!ls.length) return '<div class="co-brain"><img class="co-bav" src="' + img('brain-avatar') + '" alt=""><p>لا شيء يحتاج قرارك في الشركة الآن.</p></div>';
    return '<div class="co-brain n' + ls.length + '">' + ls.map(function (l, i) {
      return '<div class="co-bl"><img class="co-bav" src="' + img('brain-avatar') + '" alt=""><p>' + esc(l.text) + '</p><button type="button" class="co-blb" data-a="brain" data-i="' + i + '">' + esc(l.btn) + '</button></div>'; }).join('') + '</div>';
  }
  function brainOnly(sum, key) {                                  // سطر العقل المفرد في رأس تبويب (لو صحّت حقائقه)
    if (!sum) return '';
    var ls = CO.brain(sum, now(), { visits: visitCounts() });
    S.brainLines = ls;
    var i = -1; ls.forEach(function (l, n) { if (l.key === key) i = n; });
    return i < 0 ? '' : '<div class="co-brain one"><div class="co-bl"><img class="co-bav" src="' + img('brain-avatar') + '" alt=""><p>' + esc(ls[i].text) + '</p><button type="button" class="co-blb" data-a="brain" data-i="' + i + '">' + esc(ls[i].btn) + '</button></div></div>';
  }

  // ------------------------------------------------------------------ نظرة
  function partnerRow(r, parts, compactNoChip) {
    if (r.reserve) {
      return '<div class="co-pr res"><span class="co-av" style="background:' + RESERVE_COLOR + ';color:#3D4652">' + esc(arN(r.equity)) + '٪</span><div class="co-pt"><b>' + esc(r.name) + '</b><small>'
        + esc(r.notes || 'حصص غير موزّعة') + '</small></div></div>';
    }
    var agreed = lines(r.agreed), paid = parts.paidKnown ? lines(r.paid || []) : '', amount = '';
    if (parts.paidKnown && paid) amount = agreed && paid !== agreed ? paid + ' من ' + agreed : (agreed || paid);
    else if (agreed) amount = 'المتفق عليه ' + agreed;
    var ch = parts.paidKnown ? CO.partnerChip(r) : null;
    return '<div class="co-pr"><span class="co-av" style="background:' + partnerColor(parts, r.id) + '">' + esc((r.name || '?').trim().charAt(0)) + '</span>'
      + '<div class="co-pt"><b>' + esc(r.name) + '</b><small>' + esc(roleLabel(r.role) + ' · ' + U.fmt(r.equity) + '٪') + '</small></div>'
      + '<div class="co-pa">' + (amount ? '<span>' + esc(amount) + '</span>' : '') + (compactNoChip ? '' : chip(ch)) + '</div></div>';
  }
  function partnersCard(b) {
    var parts = b.parts, body;
    if (!parts) {
      body = isLoad('partners') && isLoad('summary') ? loadingBlock('الشركاء') : '<div class="co-empty"><b>الشركاء ' + na() + '.</b>' + btn2('أعد المحاولة', 'retry') + '</div>';
    } else if (!parts.rows.length) {
      body = '<div class="co-empty"><b>لا شركاء مسجّلون بعد.</b>' + btn2('أضف شريكًا', 'addPartner') + '</div>';
    } else {
      var paidBox = !parts.paidKnown ? na() : (!parts.any_contribution ? 'لم تُسجَّل دفعات بعد' : esc(lines(parts.paid_total)));
      var agreedBox = lines(parts.agreed_total) ? esc(lines(parts.agreed_total)) : 'لم يُسجَّل بعد';
      var shown = parts.rows.slice(0, 5);
      var moves = b.sum && b.sum.capital_moves ? b.sum.capital_moves.slice(0, 3) : null;
      body = '<div class="co-stats">' + stat('رأس المال المتفق عليه', agreedBox) + stat('دُفع منه', paidBox) + '</div>' + equityBar(parts)
        + '<div class="co-prs">' + shown.map(function (r) { return partnerRow(r, parts); }).join('') + '</div>'
        + (parts.rows.length > 5 ? lnk('الكل (' + arN(parts.rows.length) + ')', 'goto', ' data-t="partners"') : '')
        + '<div class="co-foot"><b>آخر الحركات</b>' + (moves === null ? '<span>' + na() + '</span>' : (moves.length ? moves.map(function (m) {
            return '<p><span>' + esc(m.description || 'حركة') + '</span><em>' + esc(U.dateText(m.date) + ' · ' + money(m.amount, m.currency)) + '</em></p>'; }).join('') : '<p><span>لا حركات مسجّلة</span></p>')) + '</div>';
    }
    return card('المؤسسون والشركاء', lnkc('أضف شريكًا', 'addPartner', 'co-hd') , body + '<div class="co-btm">' + btn2('أضف شريكًا', 'addPartner') + '</div>', 'co-c-partners');
  }
  function equipRows(b) {
    var out = [], t = now();
    var subs = b.subs ? b.subs.filter(function (s) { return s.status === 'active' && s.renews_on; })
      : (b.sum && b.sum.subscriptions ? b.sum.subscriptions.next : []);
    subs.filter(function (s) { var d = CO.daysUntil(s.renews_on, t); return d !== null && d <= 14; }).sort(function (a, c) { return a.renews_on < c.renews_on ? -1 : 1; }).forEach(function (s) {
      out.push({ name: s.name, amount: subAmountText(s), chip: CO.renewChip(s, t) });
    });
    (b.assets || []).slice().sort(function (a, c) { return (c.value_egp || 0) - (a.value_egp || 0); }).forEach(function (a) {
      out.push({ name: a.name, amount: money(a.value_egp, 'EGP'), chip: { text: CO.STATUS_LABEL[a.status] || a.status || 'معدة', tone: 'neutral' } });
    });
    return out.slice(0, 4);
  }
  function equipFoot(b) {
    var v = b.assets ? money(b.assets.reduce(function (s, a) { return s + (a.value_egp || 0); }, 0), 'EGP') : null;
    var sm = b.subs ? subsMonthly(b.subs) : (b.sum && b.sum.subscriptions ? b.sum.subscriptions.monthly : null);
    return '<div class="co-foot one"><span>قيمة المعدات ' + (v === null ? na() : esc(v)) + '</span><span>اشتراكات ' + (sm === null ? na() : (lines(sm) ? esc(lines(sm)) + ' شهريًا' : 'لا اشتراكات شهرية')) + '</span></div>';
  }
  function equipCard(b) {
    var body;
    if (!b.assets && !b.subs) body = isLoad('assets') ? loadingBlock('المعدات') : '<div class="co-empty"><b>المعدات ' + na() + '.</b>' + btn2('أعد المحاولة', 'retry') + '</div>';
    else {
      var rows = equipRows(b);
      body = (rows.length ? '<div class="co-mini">' + rows.map(function (r) {
        return '<div class="co-mr"><b>' + esc(r.name) + '</b><span>' + esc(r.amount) + '</span>' + chip(r.chip) + '</div>'; }).join('') + '</div>'
        : '<p class="co-none">لا معدات ولا اشتراكات بعد.</p>') + equipFoot(b) + lnk('الكل', 'goto', ' data-t="assets"');
    }
    return card('المعدات والاشتراكات', lnkc('أضف', 'addAssetChoice', 'co-hd'), body + '<div class="co-btm">' + btn2('أضف', 'addAssetChoice') + '</div>', 'co-c-assets');
  }
  function dealRowMini(a) {
    var c = CO.agreementChip(a, now());
    return '<div class="co-mr"><b>' + esc((CO.KIND_LABEL[a.kind] || a.kind) + (a.kind === 'other' && a.kind_other ? ' (' + a.kind_other + ')' : '') + ': ' + a.party) + '</b>'
      + (a.summary ? '<small>' + esc(a.summary) + '</small>' : '') + (a.amount ? '<span>' + esc(money(a.amount, a.currency)) + '</span>' : '') + chip(c) + '</div>';
  }
  function dealsCard(b) {
    var body;
    if (!b.deals) body = isLoad('deals') ? loadingBlock('الاتفاقات') : '<div class="co-empty"><b>الاتفاقات ' + na() + '.</b>' + btn2('أعد المحاولة', 'retry') + '</div>';
    else {
      var act = b.deals.filter(function (a) { return a.status === 'active'; }).sort(function (x, y) { var p = x.ends_on || '9999-12-31', r = y.ends_on || '9999-12-31'; return p < r ? -1 : p > r ? 1 : 0; });
      body = (act.length ? '<div class="co-mini">' + act.slice(0, 4).map(dealRowMini).join('') + '</div>' : '<p class="co-none">لا اتفاقات سارية.</p>') + lnk('الكل', 'goto', ' data-t="deals"');
    }
    return card('الاتفاقات والرعاة', lnkc('أضف اتفاقًا', 'addDeal', 'co-hd'), body + '<div class="co-btm">' + btn2('أضف اتفاقًا', 'addDeal') + '</div>', 'co-c-deals');
  }
  function kv(label, valueHtml, cls) { return '<p class="co-kv' + (cls ? ' ' + cls : '') + '"><span>' + esc(label) + '</span><b>' + valueHtml + '</b></p>'; }
  function adMini(c) {
    var r = (c.results || [])[0], inner = '';
    if (!r) inner = '<p class="co-none">لم تُسجَّل نتائج بعد.</p>';
    else {
      var due = CO.dueOf(r);
      inner = '<p class="co-per">' + esc(CO.monthText(r.period)) + '</p>'
        + kv(c.count_label || 'عملاء جاؤوا من الحملة', r.count == null ? na() : esc(U.fmt(r.count)))
        + (c.deal !== 'fixed' ? kv('دخلهم منها', r.income == null ? na() : esc(money(r.income, c.currency))) : '')
        + (c.deal === 'fixed' || c.deal === 'fixed_plus_percent' ? kv('المبلغ الثابت', esc(money(c.fixed_amount, c.currency))) : '')
        + kv('مستحق لنا', due ? esc(money(due.amount, due.currency)) : na(), 'due');
    }
    return '<article class="co-adm"><h3>' + esc(c.name) + '</h3><p class="co-deal">' + esc((c.offer ? c.offer + ' · ' : '') + CO.dealText(c)) + '</p>' + inner + '</article>';
  }
  function unsentResults(ads) {
    var out = [];
    (ads || []).forEach(function (c) {
      if (c.status !== 'active') return;
      (c.results || []).forEach(function (r) { if (!r.sent_at && !r.revenue_id && CO.dueOf(r)) out.push({ c: c, r: r }); });
    });
    return out;
  }
  function adsCard(b) {
    var body;
    if (!b.ads) body = isLoad('ads') ? loadingBlock('عملاء الإعلانات') : '<div class="co-empty"><b>عملاء الإعلانات ' + na() + '.</b>' + btn2('أعد المحاولة', 'retry') + '</div>';
    else {
      var act = b.ads.filter(function (c) { return c.status === 'active'; }), un = unsentResults(b.ads);
      body = (act.length ? '<div class="co-adg">' + act.slice(0, 4).map(adMini).join('') + '</div>' + (act.length > 4 ? lnk('الكل', 'goto', ' data-t="ads"') : '') : '<p class="co-none">لا عملاء إعلانات بعد.</p>')
        + (un.length ? '<div class="co-bar">' + btn1('جهّز كشوف الحساب (' + arN(un.length) + ')', 'statements') + '</div>' : '');
    }
    return card('عملاء الإعلانات: نحسب لهم بالنتيجة', lnkc('أضف عميلًا', 'addClient', 'co-hd'), body + '<div class="co-btm">' + btn2('أضف عميلًا', 'addClient') + '</div>', 'co-c-ads');
  }
  function targetsCard() {
    var fc = listOf('forecast'), dash = data('dash'), body;
    if (srcState('forecast') === 'error' || srcState('forecast') === 'closed') body = '<div class="co-empty"><b>الأهداف الشهرية ' + na() + '.</b>' + btn2('أعد المحاولة', 'retry') + '</div>';
    else if (!fc) body = loadingBlock('الأهداف الشهرية');
    else {
      var ml = CO.monthLine(fc, dash, now());
      var cur = CO.currentTarget(fc, now()), cc = CO.currentCounts(dash);
      var nowLine;
      var cnt = !cc ? null : 'الآن: ' + [cc.courses == null ? 'الدورات ' + NA : U.U(cc.courses, ['دورة مسجّلة واحدة', 'دورتان مسجّلتان', 'دورات مسجّلة', 'دورة مسجّلة']),
        cc.students == null ? 'الطلاب ' + NA : U.U(cc.students, ['طالب واحد', 'طالبان', 'طلاب', 'طالبًا'])].join(' · ');
      if (!cc) nowLine = 'الآن: دورات وطلاب ' + NA;
      else if (cur) nowLine = cnt + ' — هدف ' + CO.monthName(cur.month) + ': ' + U.U(cur.target_courses || 0, ['دورة واحدة', 'دورتان', 'دورات', 'دورة']) + ' · ' + U.U(cur.target_students || 0, ['طالب واحد', 'طالبان', 'طلاب', 'طالبًا']) + '.';
      else nowLine = cnt + ' — لم يُحدَّد هدف.';
      var rows = CO.targetRows(fc, dash, now()) || [];
      var shown = S.oldTargets ? rows : rows.slice(-6);
      var thead = '<div class="co-tr head"><span>الشهر</span><span>هدف الدخل</span><span>الدخل الفعلي</span><span>هدف الدورات</span><span>هدف الطلاب</span><span></span></div>';
      body = '<div class="co-brain one tg"><div class="co-bl"><img class="co-bav sm" src="' + img('brain-avatar') + '" alt=""><p>' + (ml.kind === 'na' ? esc(ml.text).replace(NA, na()) : esc(ml.text)) + '</p>'
        + (ml.kind === 'notarget' ? '<button type="button" class="co-blb" data-a="forecastNow">حدّد الهدف</button>' : '') + '</div></div>'
        + '<p class="co-nowline">' + esc(nowLine).split(NA).join(na()) + '</p>'
        + (rows.length ? '<div class="co-tbl">' + thead + shown.map(function (r) {
          var act = r.future ? '—' : r.na ? na() : (r.actual === null ? 'لا دخل مسجّل' : esc(money(r.actual, 'EGP')));
          return '<div class="co-tr"><span data-l="الشهر"><b>' + esc(r.monthText) + '</b></span><span data-l="هدف الدخل">' + (r.target ? esc(money(r.target, 'EGP')) : '—') + '</span><span data-l="الدخل الفعلي">' + act + '</span>'
            + '<span data-l="هدف الدورات">' + esc(r.courses == null ? '—' : arN(r.courses)) + '</span><span data-l="هدف الطلاب">' + esc(r.students == null ? '—' : arN(r.students)) + '</span>'
            + '<span class="act">' + lnk('عدّل', 'editForecast', ' data-id="' + esc(r.id) + '"') + '</span></div>'; }).join('') + '</div>'
          + (rows.length > 6 ? lnk(S.oldTargets ? 'أخفِ الأقدم' : 'الأقدم', 'oldTargets') : '')
          : '<p class="co-none">لا أهداف شهرية بعد.</p>')
        + '<div class="co-bar">' + btn2('أضف شهرًا', 'addForecast') + '</div>';
    }
    return card('الأهداف الشهرية', '', body, 'co-c-targets', 'coTargets');
  }
  function drawBoard(v) {
    var sum = data('summary'), parts = CO.joinPartners(listOf('partners'), sum && sum.partners);
    var b = { sum: sum, parts: parts, assets: listOf('assets'), subs: items('subs'), deals: items('deals'), ads: items('ads') };
    var fl = failed(['summary', 'partners', 'assets', 'subs', 'deals', 'ads', 'forecast', 'dash']);
    var ready = ['partners', 'assets', 'subs', 'deals', 'ads'].every(function (k) { return srcState(k) === 'ready'; });
    var empty = ready && !(listOf('partners') || []).length && !b.assets.length && !b.subs.length && !b.deals.length && !b.ads.length;
    var main;
    if (empty) {
      main = '<section class="co-hero"><div class="co-hero-ph" style="background-image:url(' + img('company') + ')" role="img" aria-label="الشركة"></div><div class="co-hero-t"><h2>سجّل الشركة هنا مرة واحدة</h2>'
        + '<p>الشركاء وما دفعه كل واحد، والمعدات والاشتراكات، والاتفاقات وعملاء الإعلانات — في مكان واحد يراه العقل.</p>' + btn1('ابدأ بالشركاء', 'addPartner') + '</div></section>';
    } else {
      main = '<div class="co-grid">' + partnersCard(b) + equipCard(b) + dealsCard(b) + adsCard(b) + '</div>';
    }
    v.innerHTML = '<div class="co" data-board="invest">' + noteStrip() + warnStrip(fl) + brainStrip(sum) + main + targetsCard() + '</div>';
    if (S.jump === 'targets' && ['summary', 'partners', 'assets', 'subs', 'deals', 'ads', 'forecast', 'dash'].every(function (k) { return !isLoad(k); })) { S.jump = null; setTimeout(function () { var t = document.getElementById('coTargets'); if (t && t.scrollIntoView) t.scrollIntoView({ block: 'start' }); }, 30); }
  }

  // ------------------------------------------------------------------ الشركاء ورأس المال
  function kindText(c) {
    if (c.kind === 'cash') return 'نقدًا';
    if (c.kind === 'asset') return 'معدات أو أصول' + (c.asset_name ? ': ' + c.asset_name : '');
    return 'أخرى' + (c.kind_other ? ': ' + c.kind_other : '');
  }
  function drawPartners(v) {
    var sum = data('summary'), raw = listOf('partners'), parts = CO.joinPartners(raw, sum && sum.partners);
    var fl = failed(['summary', 'partners', 'contribs', 'cash', 'invest']);
    var hasP = !!(parts && parts.rows.some(function (r) { return !r.reserve; }));
    var top = '<div class="co-top"><p>ما اتفق عليه كل شريك، وما دفعه فعلًا.</p><div class="co-ta">'
      + (hasP ? btn1('سجّل دفعة', 'contribution') + btn2('أضف شريكًا', 'addPartner') : btn1('أضف شريكًا', 'addPartner')) + '</div></div>';
    var body = '';
    if (!parts) {
      body = isLoad('partners') && isLoad('summary') ? loadingBlock('الشركاء') : '<div class="co-empty"><b>الشركاء ' + na() + '.</b>' + btn2('أعد المحاولة', 'retry') + '</div>';
    } else {
      var paidV, remV, remHint = '';
      if (!parts.paidKnown) { paidV = na(); remV = na(); }
      else {
        paidV = parts.any_contribution ? esc(lines(parts.paid_total)) : 'لم تُسجَّل دفعات بعد';
        if (!parts.any_contribution) { remV = na(); remHint = 'سجّل دفعات الشركاء لتعرف الباقي'; }
        else { var rem = CO.remaining(parts.agreed_total, parts.paid_total); remV = rem.length ? esc(lines(rem)) : 'لا شيء باقٍ'; }
      }
      var idx = 0;
      var legend = '<ul class="co-leg">' + parts.rows.filter(function (r) { return r.equity > 0; }).map(function (r) {
        var c = r.reserve ? RESERVE_COLOR : COLORS[idx++ % COLORS.length];
        return '<li><i style="background:' + c + '"></i>' + esc(r.name) + ' <b>' + esc(U.fmt(r.equity)) + '٪</b></li>'; }).join('') + '</ul>';
      var eqWarn = parts.rows.length && Math.abs(parts.equity_total - 100) > 0.05 ? '<div class="co-amber">مجموع الحصص المسجّلة ' + esc(U.fmt(parts.equity_total)) + '٪.</div>' : '';
      body += '<div class="co-stats three">' + stat('رأس المال المتفق عليه', lines(parts.agreed_total) ? esc(lines(parts.agreed_total)) : 'لم يُسجَّل بعد')
        + stat('دُفع منه', paidV) + stat('الباقي', remV, remHint) + '</div>' + (parts.rows.length ? equityBar(parts) + legend : '') + eqWarn;
      // قائمة الشركاء
      var list;
      if (!parts.rows.length) list = '<div class="co-empty"><b>لا شركاء مسجّلون بعد.</b></div>';
      else list = '<div class="co-tbl pt"><div class="co-tr head"><span>الشريك</span><span>الحصة</span><span>المتفق عليه</span><span>دُفع</span><span>الحالة</span><span></span></div>'
        + parts.rows.map(function (r) {
          if (r.reserve) return '<div class="co-tr res"><span data-l="الشريك"><b>' + esc(r.name) + '</b><small>' + esc(r.notes || 'حصص غير موزّعة') + '</small></span><span data-l="الحصة">' + esc(U.fmt(r.equity)) + '٪</span><span></span><span></span><span></span><span class="act">' + lnk('عدّل', 'editPartner', ' data-id="' + esc(r.id) + '"') + '</span></div>';
          var ch = parts.paidKnown ? CO.partnerChip(r) : null;
          return '<div class="co-tr"><span data-l="الشريك"><b>' + esc(r.name) + '</b><small>' + esc(roleLabel(r.role)) + '</small></span><span data-l="الحصة">' + esc(U.fmt(r.equity)) + '٪</span>'
            + '<span data-l="المتفق عليه">' + (lines(r.agreed) ? esc(lines(r.agreed)) : '—') + '</span>'
            + '<span data-l="دُفع">' + (!parts.paidKnown ? na() : (lines(r.paid || []) ? esc(lines(r.paid)) : '—')) + '</span>'
            + '<span data-l="الحالة">' + chip(ch) + '</span>'
            + '<span class="act">' + btn2('سجّل دفعة', 'contribution', ' data-id="' + esc(r.id) + '"') + lnk('عدّل', 'editPartner', ' data-id="' + esc(r.id) + '"') + '</span></div>'; }).join('') + '</div>';
      body += card('الشركاء', '<span class="co-cnt">' + esc(arN(parts.rows.length)) + '</span>', list);
    }
    // دفعات الشركاء
    var cs = items('contribs'), cbody;
    if (!cs) cbody = isLoad('contribs') ? loadingBlock('دفعات الشركاء') : '<div class="co-empty"><b>دفعات الشركاء ' + na() + '.</b>' + btn2('أعد المحاولة', 'retry') + '</div>';
    else {
      var chips = '<div class="co-fcs" role="group" aria-label="تصفية">' + '<button type="button" class="co-fc' + (S.filt === 'all' ? ' on' : '') + '" data-a="filt" data-v="all">الكل</button>'
        + (parts ? parts.rows.filter(function (r) { return !r.reserve; }).map(function (r) {
          return '<button type="button" class="co-fc' + (S.filt === String(r.id) ? ' on' : '') + '" data-a="filt" data-v="' + esc(r.id) + '">' + esc(r.name) + '</button>'; }).join('') : '') + '</div>';
      var shown = cs.filter(function (c) { return S.filt === 'all' || String(c.partner_id) === S.filt; });
      cbody = chips + (shown.length ? '<div class="co-tbl ct"><div class="co-tr head"><span>التاريخ</span><span>الشريك</span><span>النوع</span><span>المبلغ</span><span>أين سُجّلت</span><span></span></div>' + shown.map(function (c) {
        return '<div class="co-tr"><span data-l="التاريخ">' + esc(U.dateText(c.date)) + '</span><span data-l="الشريك"><b>' + esc(c.partner_name || '') + '</b></span><span data-l="النوع">' + esc(kindText(c)) + (c.note ? '<small>' + esc(c.note) + '</small>' : '') + '</span>'
          + '<span data-l="المبلغ"><b>' + esc(money(c.amount, c.currency)) + '</b></span><span data-l="أين سُجّلت">' + (c.cash_tx_id ? '<em class="co-bdg">في حركة النقد</em>' : '') + (c.asset_id ? '<em class="co-bdg">في المعدات</em>' : '') + '</span>'
          + '<span class="act">' + lnk('احذف', 'delContribution', ' data-id="' + esc(c.id) + '"') + '</span></div>'; }).join('') + '</div>' : '<p class="co-none">لا دفعات مسجّلة.</p>');
    }
    body += card('دفعات الشركاء', '', cbody);
    // حركات رأس المال
    var cash = data('cash'), mbody;
    if (!cash || !Array.isArray(cash.transactions)) mbody = isLoad('cash') ? loadingBlock('حركات رأس المال') : '<div class="co-empty"><b>حركات رأس المال ' + na() + '.</b>' + btn2('أعد المحاولة', 'retry') + '</div>';
    else {
      var tx = cash.transactions.slice(0, 10);
      mbody = tx.length ? '<div class="co-tbl mv">' + tx.map(function (t) {
        var inn = t.kind === 'capital_in' || t.kind === 'adjustment_in', eg = t.amount_egp || 0, amt = eg ? money(Math.abs(eg), 'EGP') : money(Math.abs(t.amount_usd || 0), 'USD');
        return '<div class="co-tr"><span data-l="التاريخ">' + esc(U.dateText(t.date)) + '</span><span data-l="البيان">' + esc(t.description || t.source || 'حركة') + '</span><span data-l="الاتجاه"><em class="co-bdg ' + (inn ? 'in' : 'out') + '">' + (inn ? 'داخل' : 'خارج') + '</em></span><span data-l="المبلغ"><b>' + esc(amt) + '</b></span></div>'; }).join('') + '</div>' : '<p class="co-none">لا حركات مسجّلة.</p>';
    }
    body += card('حركات رأس المال', '<span class="co-sub">آخر ١٠ حركات</span>', mbody);
    // المستثمرون
    var inv = listOf('invest');
    if (inv && inv.length) {
      var by = {};
      inv.forEach(function (it) { var n = it.investor_name || '—'; var o = by[n] || (by[n] = { name: n, invested: 0, due: 0 }); o.invested += it.invested_total_egp || 0; o.due += it.due_egp || 0; });
      var wd = (listOf('wd') || []).filter(function (w) { return w.status === 'pending'; });
      body += card('المستثمرون', '<span class="co-sub">من سجل الاستثمارات</span>', '<div class="co-tbl iv">' + Object.keys(by).map(function (k) {
        var o = by[k]; return '<div class="co-tr"><span data-l="المستثمر"><b>' + esc(o.name) + '</b></span><span data-l="استثمر">استثمر ' + esc(money(o.invested, 'EGP')) + '</span><span data-l="مستحق له">مستحق له ' + esc(money(o.due, 'EGP')) + '</span></div>'; }).join('') + '</div>'
        + (wd.length ? lnk('طلبات سحب المستثمرين (' + arN(wd.length) + ') — في «الفلوس»', 'investorWd') : ''));
    }
    // فرص الاستثمار — فقط لو فيه صفوف
    var op = listOf('opps');
    if (op && op.length) {
      body += '<details class="co-card co-det"><summary>فرص الاستثمار (' + esc(arN(op.length)) + ')</summary><div class="co-tbl op">' + op.map(function (o) {
        return '<div class="co-tr"><span data-l="الدورة"><b>' + esc(o.course_title || 'فرصة') + '</b></span><span data-l="التمويل">' + esc(money(o.current_funded || 0, 'EGP') + ' من ' + money(o.target_amount || 0, 'EGP')) + '</span>'
          + '<span data-l="العائد المتوقع">' + (o.expected_roi != null ? 'العائد المتوقع ' + esc(U.fmt(o.expected_roi)) + '٪' : '—') + '</span><span class="act">' + lnk('احذف', 'delOpp', ' data-id="' + esc(o.id) + '"') + '</span></div>'; }).join('') + '</div></details>';
    }
    v_html(top + body);
    function v_html(h) { S.view.innerHTML = '<div class="co" data-board="partners">' + noteStrip() + warnStrip(fl) + h + '</div>'; }
  }

  // ------------------------------------------------------------------ المعدات والاشتراكات
  function drawAssets(v) {
    var assets = listOf('assets'), subs = items('subs'), sum = data('summary');
    var fl = failed(['assets', 'subs']);
    var legacy = CO.legacySubs(assets);
    var t = now();
    var sorted = subs ? CO.subsSorted(subs, t) : null;
    var firstPrimary = false;
    if (sorted && sorted.length && !legacy.length) {
      var f0 = sorted[0], d0 = f0.status === 'active' && f0.renews_on ? CO.daysUntil(f0.renews_on, t) : null;
      firstPrimary = d0 !== null && d0 <= 7;
    }
    var strip = legacy.length ? '<div class="co-amber strip"><span>' + esc(U.U(legacy.length, ['اشتراك واحد مسجّل', 'اشتراكان مسجّلان', 'اشتراكات مسجّلة', 'اشتراكًا مسجّلًا'])) + ' بالطريقة القديمة بين المعدات.</span>' + btn1('انقلها إلى الاشتراكات', 'importSubs') + '</div>' : '';
    // المعدات
    var eq;
    if (!assets) eq = isLoad('assets') ? loadingBlock('المعدات') : '<div class="co-empty"><b>المعدات ' + na() + '.</b>' + btn2('أعد المحاولة', 'retry') + '</div>';
    else {
      var totV = assets.reduce(function (s, a) { return s + (a.value_egp || 0); }, 0), totR = assets.reduce(function (s, a) { return s + (a.monthly_rent_egp || 0); }, 0);
      eq = '<p class="co-sumline">' + esc(U.U(assets.length, ['بند واحد', 'بندان', 'بنود', 'بندًا']) + ' · القيمة ' + money(totV, 'EGP') + ' · إيجار شهري للشركة ' + money(totR, 'EGP')) + '</p>'
        + (assets.length ? '<div class="co-list">' + assets.map(function (a) {
          return '<div class="co-lr" data-id="a' + esc(a.id) + '"><div class="co-lm"><b>' + esc(a.name) + '</b><small>' + esc((CO.CAT_LABEL[a.category] || a.category || 'معدة') + ' · ملك: ' + (a.owner || 'الشركة')) + '</small></div>'
            + '<div class="co-la"><b>' + ((a.value_egp || 0) > 0 ? esc(money(a.value_egp, 'EGP')) : 'بلا قيمة مسجّلة') + '</b>' + ((a.monthly_rent_egp || 0) > 0 ? '<small>إيجار ' + esc(money(a.monthly_rent_egp, 'EGP')) + ' شهريًا</small>' : '') + chip({ text: CO.STATUS_LABEL[a.status] || a.status || 'معدة', tone: 'neutral' }) + '</div>'
            + '<div class="co-ra">' + btn2('عدّل', 'editAsset', ' data-id="' + esc(a.id) + '"') + '</div></div>'; }).join('') + '</div>' : '<p class="co-none">لا معدات مسجّلة بعد.</p>')
        + '<div class="co-bar">' + btn2('أضف معدة', 'addAsset') + '</div>';
    }
    // الاشتراكات
    var sb;
    if (!sorted) sb = isLoad('subs') ? loadingBlock('الاشتراكات') : '<div class="co-empty"><b>الاشتراكات ' + na() + '.</b>' + btn2('أعد المحاولة', 'retry') + '</div>';
    else {
      var m = lines(subsMonthly(sorted)), y = lines(subsYearly(sorted));
      sb = '<p class="co-sumline">' + (sorted.length ? 'شهريًا: ' + esc(m || '—') + ' · سنويًا: ' + esc(y || '—') : 'لا اشتراكات مسجّلة بعد.') + '</p>'
        + (sorted.length ? '<div class="co-list">' + sorted.map(function (s, i) {
          var rc = CO.renewChip(s, t), stopped = s.status === 'stopped';
          var vis = stopped ? btn2('أعد تشغيله', 'resumeSub', ' data-id="' + esc(s.id) + '"')
            : (i === 0 && firstPrimary ? btn1('سجّل الدفع', 'paySub', ' data-id="' + esc(s.id) + '"') : btn2('سجّل الدفع', 'paySub', ' data-id="' + esc(s.id) + '"'));
          return '<div class="co-lr' + (stopped ? ' stopped' : '') + (S.hl === 'assets:' + s.id ? ' hl' : '') + '" data-id="s' + esc(s.id) + '"><div class="co-lm"><b>' + esc(s.name) + '</b><small>' + (s.paid_by ? 'يدفعه: ' + esc(s.paid_by) : '') + '</small></div>'
            + '<div class="co-la"><b>' + esc(subAmountText(s)) + '</b>' + chip(rc) + '</div><div class="co-ra">' + vis + moreBtn('', 'sub', s.id) + '</div></div>'; }).join('') + '</div>' : '')
        + '<div class="co-bar">' + btn2('أضف اشتراكًا', 'addSub') + '</div>';
    }
    S.view.innerHTML = '<div class="co" data-board="assets">' + noteStrip() + warnStrip(fl) + brainOnly(sum, 'subscription') + strip
      + '<div class="co-two">' + card('المعدات والأصول', '<span class="co-cnt">' + (assets ? esc(arN(assets.length)) : '—') + '</span>', eq) + card('الاشتراكات', '<span class="co-cnt">' + (sorted ? esc(arN(sorted.length)) : '—') + '</span>', sb) + '</div></div>';
    scrollHl('s');
  }
  function scrollHl() {
    if (!S.hl) return;
    setTimeout(function () { var e = q('.hl'); if (e && e.scrollIntoView) e.scrollIntoView({ block: 'center' }); S.hl = null; }, 30);
  }

  // ------------------------------------------------------------------ الاتفاقات والرعاة
  function dealRange(a) {
    var s = a.starts_on ? U.dateText(a.starts_on) : '', e = a.ends_on ? U.dateText(a.ends_on) : '';
    if (!s && !e) return 'بلا تواريخ';
    return (s ? 'من ' + s + ' ' : '') + (e ? 'إلى ' + e : 'بلا تاريخ انتهاء');
  }
  function dealRow(a) {
    var t = now(), ch = CO.agreementChip(a, t), act = CO.dealAction(a, t);
    var visible = act === 'renew' ? btn2('جدّد', 'renewDeal', ' data-id="' + esc(a.id) + '"') : act === 'receive' ? btn2('سجّل مبلغًا مستلمًا', 'receiveDeal', ' data-id="' + esc(a.id) + '"') : btn2('عدّل', 'editDeal', ' data-id="' + esc(a.id) + '"');
    var kind = (CO.KIND_LABEL[a.kind] || a.kind) + (a.kind === 'other' && a.kind_other ? ' (' + a.kind_other + ')' : '');
    var recv = a.received && a.received.length ? '<span>استلمنا ' + esc(lines(a.received)) + '</span>' : '';
    return '<div class="co-lr deal' + (S.hl === 'deals:' + a.id ? ' hl' : '') + '" data-id="d' + esc(a.id) + '"><div class="co-lm"><b>' + esc(kind + ': ' + a.party) + '</b>'
      + (a.summary ? '<small>' + esc(a.summary) + '</small>' : '') + (a.terms ? '<small>' + esc(a.terms) + '</small>' : '') + '<small>' + esc(dealRange(a)) + '</small>'
      + '<div class="co-meta">' + recv + (a.status === 'active' ? visitLine(a.ref_code) : '') + '</div></div>'
      + '<div class="co-la">' + (a.amount ? '<b>' + esc(money(a.amount, a.currency)) + '</b>' : '') + chip(ch) + '</div>'
      + '<div class="co-ra">' + visible + moreBtn('', 'deal', a.id) + '</div></div>';
  }
  function drawDeals(v) {
    var deals = items('deals'), fl = failed(['deals']);
    var body;
    if (!deals) body = isLoad('deals') ? loadingBlock('الاتفاقات') : '<div class="co-empty"><b>الاتفاقات ' + na() + '.</b>' + btn2('أعد المحاولة', 'retry') + '</div>';
    else if (!deals.length) body = '<div class="co-empty"><b>لا اتفاقات مسجّلة بعد.</b></div>';
    else {
      var g = CO.agreementGroups(deals, now());
      function grp(title, rows, cls) { return rows.length ? card(title, '<span class="co-cnt">' + esc(arN(rows.length)) + '</span>', '<div class="co-list">' + rows.map(dealRow).join('') + '</div>', cls) : ''; }
      body = grp('تنتهي خلال ٣٠ يومًا', g.ending, 'soon') + grp('سارية', g.active) + grp('مسودات', g.drafts)
        + (g.ended.length ? '<details class="co-card co-det"><summary>انتهت (' + esc(arN(g.ended.length)) + ')</summary><div class="co-list">' + g.ended.map(dealRow).join('') + '</div></details>' : '');
    }
    S.view.innerHTML = '<div class="co" data-board="deals">' + noteStrip() + warnStrip(fl) + visitsStrip()
      + '<div class="co-top"><p>رعاة واتفاقات المحتوى والكتب وأوراق الشركة.</p><div class="co-ta">' + btn1('أضف اتفاقًا', 'addDeal') + '</div></div>' + body + '</div>';
    scrollHl();
  }

  // ------------------------------------------------------------------ عملاء الإعلانات
  function ledgerLine(c) {
    if (!c.ledger_kind || !c.ledger_owner_id) return '';
    var rows = L.v2AdsLedger(data('ledger'), now());
    if (!rows) return '<p class="co-ledger">رصيد إعلاناته عندنا: ' + na() + '</p>';
    var r = rows.filter(function (x) { return x.kind === c.ledger_kind && x.id === c.ledger_owner_id; })[0];
    if (!r) return '<p class="co-ledger">رصيد إعلاناته عندنا: ' + na() + '</p>';
    return '<p class="co-ledger">رصيد إعلاناته عندنا: <b>' + esc(lines(r.balances) || '٠ جنيه') + '</b></p>';
  }
  function resultStatus(r) {
    if (r.revenue_id) return '<span class="co-st t-ok">حُصّل' + (r.collected_on ? ' ' + esc(U.dateText(r.collected_on)) : '') + '</span>';
    if (r.sent_at) return '<span class="co-st t-soon">أُرسل الكشف ' + esc(U.dateText((r.sent_at || '').slice(0, 10))) + '</span>';
    return '<span class="co-st t-neutral">لم يُرسل الكشف</span>';
  }
  S.oldAds = {};
  function clientCard(c) {
    var res = c.results || [], showAll = !!S.oldAds[c.id], shown = showAll ? res : res.slice(0, 6);
    var thead = '<div class="co-tr head"><span>الشهر</span><span>' + esc(c.count_label || 'العدد') + '</span><span>دخلهم منها</span><span>مستحق لنا</span><span>الحالة</span><span></span></div>';
    var tbl = res.length ? '<div class="co-tbl rs">' + thead + shown.map(function (r) {
      var due = CO.dueOf(r);
      return '<div class="co-tr"><span data-l="الشهر"><b>' + esc(CO.monthText(r.period)) + '</b></span><span data-l="' + esc(c.count_label || 'العدد') + '">' + (r.count == null ? na() : esc(U.fmt(r.count))) + '</span>'
        + '<span data-l="دخلهم منها">' + (c.deal === 'fixed' ? '—' : (r.income == null ? na() : esc(money(r.income, c.currency)))) + '</span>'
        + '<span data-l="مستحق لنا">' + (due ? '<b>' + esc(money(due.amount, due.currency)) + '</b>' : na()) + '</span><span data-l="الحالة">' + resultStatus(r) + '</span>'
        + '<span class="act">' + btn2('كشف الحساب', 'statement', ' data-id="' + esc(r.id) + '" data-c="' + esc(c.id) + '"') + '</span></div>'; }).join('') + '</div>'
      + (res.length > 6 ? lnk(showAll ? 'أخفِ الأقدم' : 'الأقدم', 'oldAds', ' data-c="' + esc(c.id) + '"') : '') : '<p class="co-none">لم تُسجَّل نتائج بعد.</p>';
    return '<section class="co-card co-cl"><header class="co-ch"><div><h2>' + esc(c.name) + '</h2><p class="co-deal">' + esc((c.offer ? c.offer + ' · ' : '') + CO.dealText(c)) + '</p></div></header>'
      + ledgerLine(c) + (c.status === 'active' ? visitLine(c.ref_code) : '') + tbl
      + '<div class="co-bar">' + btn2('سجّل نتيجة شهر', 'addResult', ' data-c="' + esc(c.id) + '"') + lnk('عدّل الاتفاق', 'editClient', ' data-c="' + esc(c.id) + '"') + '</div></section>';
  }
  function drawAds(v) {
    var ads = items('ads');
    var linkedAny = (ads || []).some(function (c) { return c.ledger_kind && c.ledger_owner_id; });
    var linkedActive = (ads || []).some(function (c) { return c.status === 'active' && c.ledger_kind && c.ledger_owner_id; });
    if (linkedAny && srcState('ledger') === 'idle') load('ledger', false);                 // الأرصدة لا تُجلب إلا لو فيه عميل مربوط بعمل
    var fl = failed(linkedActive ? ['ads', 'ledger'] : ['ads']);
    var un = unsentResults(ads);
    var body;
    if (!ads) body = isLoad('ads') ? loadingBlock('عملاء الإعلانات') : '<div class="co-empty"><b>عملاء الإعلانات ' + na() + '.</b>' + btn2('أعد المحاولة', 'retry') + '</div>';
    else if (!ads.length) body = '<div class="co-empty"><b>لا عملاء إعلانات بعد.</b></div>';
    else {
      var act = ads.filter(function (c) { return c.status === 'active'; }), ended = ads.filter(function (c) { return c.status !== 'active'; });
      body = act.map(clientCard).join('') + (ended.length ? '<details class="co-card co-det"><summary>عملاء انتهى الاتفاق معهم (' + esc(arN(ended.length)) + ')</summary>' + ended.map(clientCard).join('') + '</details>' : '');
    }
    var prim = un.length ? btn1('جهّز كشوف الحساب (' + arN(un.length) + ')', 'statements') + btn2('أضف عميلًا', 'addClient') : btn1('أضف عميلًا', 'addClient');
    S.view.innerHTML = '<div class="co" data-board="ads">' + noteStrip() + warnStrip(fl) + visitsStrip()
      + '<div class="co-top"><p>نحسب لكل عميل بالنتيجة: نسبة من دخل الحملة أو مبلغ ثابت أو الاثنان.</p><div class="co-ta">' + prim + '</div></div>' + body + '</div>';
  }

  // ------------------------------------------------------------------ الإعدادات
  var DASH_ROLE = { admin: 'مدير', employee: 'موظف متابعة', viewer: 'بانتظار التفعيل' };
  var PERM_MODS = [['users', 'المستخدمون'], ['courses', 'الدورات'], ['topics', 'المحتوى'], ['tutorials', 'دليل الاستخدام']];
  var AUDIT_CO = { 'company.contribution.add': 'تسجيل دفعة شريك', 'company.contribution.delete': 'حذف دفعة شريك', 'company.subscription.add': 'إضافة اشتراك', 'company.subscription.update': 'تعديل اشتراك',
                   'company.subscription.delete': 'حذف اشتراك', 'company.subscription.paid': 'تسجيل دفع اشتراك', 'company.subscription.import': 'نقل اشتراكات من المعدات', 'company.agreement.add': 'إضافة اتفاق',
                   'company.agreement.update': 'تعديل اتفاق', 'company.agreement.delete': 'حذف اتفاق', 'company.agreement.renew': 'تجديد اتفاق', 'company.agreement.end': 'إنهاء اتفاق',
                   'company.adclient.add': 'إضافة عميل إعلانات', 'company.adclient.update': 'تعديل عميل إعلانات', 'company.adclient.delete': 'حذف عميل إعلانات', 'company.adresult.add': 'إضافة نتيجة شهر',
                   'company.adresult.update': 'تعديل نتيجة شهر', 'company.adresult.delete': 'حذف نتيجة شهر', 'company.adresult.sent': 'إرسال كشف حساب', 'company.income.add': 'تسجيل مبلغ مستلم',
                   'company.forecast.add': 'إضافة هدف شهر' };
  function rolePerms(settings) {
    var raw = settings && settings.role_permissions;
    if (!raw) return {};
    try { return typeof raw === 'string' ? (JSON.parse(raw) || {}) : raw; } catch (e) { return {}; }
  }
  function auditLabel(r) {
    var m = typeof AUDIT_LABEL !== 'undefined' ? AUDIT_LABEL : null;
    return (m && m[r.action]) || AUDIT_CO[r.action] || 'عملية';
  }
  function auditDetail(r) {
    var f = typeof auditEfDetail === 'function' ? auditEfDetail : null, d = '';
    try { if (typeof f === 'function') d = f(r) || ''; } catch (e) {}
    if (!d && r.action === 'company.contribution.add' && r.meta && r.meta.asset_id) d = 'وإضافة معدة';
    return d;
  }
  function whenText(iso) {
    try { if (typeof auditWhen === 'function') return auditWhen(iso); } catch (e) {}
    return U.dateText(iso);
  }
  function drawSettings(v) {
    var E = ep(), D = (E && E.data) || {};
    var stS = epState('settings'), set = stS === 'ready' ? (D.settings || {}) : null;
    var fl = [];
    if (stS === 'error') fl.push('الإعدادات');
    if (epState('dashUsers') === 'error') fl.push('فريق الإدارة');
    var users = epState('dashUsers') === 'ready' && Array.isArray(D.dashUsers) ? D.dashUsers : null;
    var models = epState('aiModels') === 'ready' && Array.isArray(D.aiModels) ? D.aiModels : null;
    var usage = epState('usage') === 'ready' ? D.usage : null;
    // بيانات الشركة
    var coBody;
    if (!set) coBody = stS === 'error' ? '<div class="co-empty"><b>بيانات الشركة ' + na() + '.</b>' + btn2('أعد المحاولة', 'retrySet') + '</div>' : loadingBlock('بيانات الشركة');
    else {
      var dom = set.company_domain || (window.location && location.host) || '';
      coBody = fld('الاسم', inp('co_name', set.company_name || '')) + fld('بداية السنة المالية', inp('co_fy', set.fiscal_year_start || '')) + fld('يوم التقرير الشهري', inp('co_rd', set.monthly_report_day || ''))
        + '<p class="co-kv"><span>عنوان اللوحة</span><b dir="ltr">' + esc(dom) + '</b></p><div class="co-bar">' + btn1('احفظ بيانات الشركة', 'saveCompany') + '</div>';
    }
    // العملة
    var fx = set && set.exchange_rate != null && set.exchange_rate !== '' ? set.exchange_rate : null;
    var fxBody = set ? '<p class="co-kv big"><span>سعر الدولار بالجنيه</span><b>' + (fx === null ? na() : esc(U.fmt(Number(fx)))) + '</b></p><div class="co-bar">'
      + '<button type="button" class="co-btn2" data-a="rate"' + (fx === null ? ' disabled' : '') + '>غيّر</button></div>' : (stS === 'error' ? '<p class="co-kv"><span>سعر الدولار بالجنيه</span><b>' + na() + '</b></p>' : loadingBlock('سعر الدولار'));
    // الفريق
    var teamBody;
    if (!users) teamBody = epState('dashUsers') === 'error' ? '<div class="co-empty"><b>فريق الإدارة ' + na() + '.</b>' + btn2('أعد المحاولة', 'retrySet') + '</div>' : loadingBlock('فريق الإدارة');
    else {
      var admins = users.filter(function (u) { return u.is_active && (u.dashboard_role === 'admin' || u.role === 'admin'); });
      teamBody = (users.length ? '<div class="co-list">' + users.map(function (u) {
        var rl = u.dashboard_role || u.role || 'viewer', last = rl === 'admin' && u.is_active && admins.length <= 1;
        return '<div class="co-lr"><div class="co-lm"><b>' + esc(u.name || u.email || '—') + '</b><small dir="ltr">' + esc(u.email || '') + '</small></div>'
          + '<div class="co-la"><span>' + esc(DASH_ROLE[rl] || rl) + '</span>' + chip({ text: u.is_active ? 'مفعّل' : 'موقوف', tone: u.is_active ? 'ok' : 'neutral' }) + '</div>'
          + '<div class="co-ra">' + btn2('عدّل', 'editStaff', ' data-id="' + esc(u.id) + '"') + (last ? '<small class="co-prot">آخر مدير — محميّ</small>' : lnk(u.is_active ? 'أوقف' : 'فعّل', 'toggleStaff', ' data-id="' + esc(u.id) + '"')) + '</div></div>'; }).join('') + '</div>'
        : '<p class="co-none">لا حسابات إدارية بعد.</p>') + '<div class="co-bar">' + btn2('أضف مديرًا أو موظفًا', 'addStaff') + '</div>';
    }
    // الصلاحيات
    var permBody;
    if (!set) permBody = stS === 'error' ? '<p class="co-none">' + na() + '</p>' : loadingBlock('الصلاحيات');
    else {
      var map = rolePerms(set), entry = map.employee && (map.employee.modules || map.employee), allowed = Array.isArray(entry) ? entry : PERM_MODS.map(function (m) { return m[0]; });
      permBody = '<p class="co-lead sm">الأقسام المسموحة لموظف المتابعة (المدير يرى كل شيء).</p><div class="co-perms">' + PERM_MODS.map(function (m) {
        return '<label class="co-ck"><input type="checkbox" class="co-pm" value="' + m[0] + '"' + (allowed.indexOf(m[0]) > -1 ? ' checked' : '') + '><span>' + esc(m[1]) + '</span></label>'; }).join('') + '</div><div class="co-bar">' + btn2('احفظ الصلاحيات', 'savePerms') + '</div>';
    }
    // خدمة الذكاء
    var aiBody = models ? (models.length ? '<div class="co-list">' + models.map(function (m) {
      return '<div class="co-lr"><div class="co-lm"><b>' + esc(m.label || 'خدمة') + '</b></div><div class="co-la">' + chip({ text: m.configured ? 'جاهزة' : 'غير جاهزة', tone: m.configured ? 'ok' : 'neutral' }) + '</div></div>'; }).join('') + '</div>' : '<p class="co-none">لا خدمات مسجّلة.</p>')
      + '<p class="co-fine">الإعداد من إدارة النظام.</p>' : loadingBlock('حالة الخدمة');
    // الاستخدام
    var useBody;
    if (!usage) useBody = epState('usage') === 'error' ? '<p class="co-none">' + na() + '</p>' : loadingBlock('الاستخدام');
    else useBody = '<div class="co-stats three">' + stat('طلبات للعقل', usage.ai_calls == null ? na() : esc(U.fmt(usage.ai_calls)), usage.ai_errors ? 'تعذّر منها ' + U.fmt(usage.ai_errors) : '')
      + stat('مرات الدخول', usage.logins_7d == null ? na() : esc(U.fmt(usage.logins_7d))) + stat('عمليات', usage.actions_7d == null ? na() : esc(U.fmt(usage.actions_7d))) + '</div>';
    // سجل العمليات
    var auditBody;
    if (!S.auditOpen) auditBody = '<div class="co-bar">' + btn2('اعرض سجل العمليات', 'auditOpen') + '</div>';
    else {
      var rows = epState('audit') === 'ready' && Array.isArray(D.audit) ? D.audit : null;
      if (!rows) auditBody = epState('audit') === 'error' ? '<div class="co-empty"><b>سجل العمليات ' + na() + '.</b>' + btn2('أعد المحاولة', 'auditOpen') + '</div>' : loadingBlock('سجل العمليات');
      else if (!rows.length) auditBody = '<p class="co-none">لا عمليات مسجّلة بعد.</p>';
      else auditBody = '<div class="co-list au">' + rows.slice(0, S.auditN).map(function (r) {
        var det = auditDetail(r);
        return '<div class="co-lr au"><div class="co-lm"><b>' + esc(auditLabel(r)) + '</b>' + (det ? '<small>' + esc(det) + '</small>' : '') + '<small dir="ltr" class="au-e">' + esc(r.actor_email || '') + '</small></div><div class="co-la"><small>' + esc(whenText(r.created_at)) + '</small></div></div>'; }).join('') + '</div>'
        + (rows.length > S.auditN ? lnk('المزيد', 'auditMore') : '') + '<div class="co-bar">' + btn2('أخفِ السجل', 'auditClose') + '</div>';
    }
    S.view.innerHTML = '<div class="co" data-board="settings">' + noteStrip() + warnStrip(fl) + '<div class="co-two">'
      + '<div class="co-col">' + card('بيانات الشركة', '', coBody) + card('العملة', '', fxBody) + card('صلاحيات الموظف', '', permBody) + card('الاستخدام في آخر ٧ أيام', '', useBody) + '</div>'
      + '<div class="co-col">' + card('فريق الإدارة', '', teamBody) + card('خدمة الذكاء', '', aiBody) + card('سجل العمليات', '', auditBody) + '</div></div></div>';
  }

  // ------------------------------------------------------------------ الأوراق
  function byId(list, id) { return (list || []).filter(function (x) { return String(x.id) === String(id); })[0]; }
  function realPartners() { return (listOf('partners') || []).filter(function (p) { return !CO.isReserve(p); }); }
  function reloadP() { load('partners', true); var E = ep(); if (E) { E.reload('partners', null); E.reload('investment', null); } }
  function notReady(what) { setNote(what + ' لم تصل بعد — حاول بعد لحظات.'); redraw(); }

  // —— شريك
  var ROLE_KEYS = [['founder', 'مؤسس'], ['cofounder', 'شريك مؤسس'], ['investor', 'مستثمر'], ['partner', 'شريك'], ['pool', 'حصص غير موزّعة'], ['other', 'أخرى']];
  function openPartner(row) {
    var E = ep(), edit = row || null, e = edit || {};
    epEnsure(['users']);
    function getUsers() { return (window.USERS || []).filter(function (u) { return u && u.name; }); }
    function userLabel(u) { return u.email ? u.name + ' · ' + u.email : u.name; }
    function userOpts() { return getUsers().map(function (u) { return '<option value="' + esc(userLabel(u)) + '"></option>'; }).join(''); }
    var knownRole = ROLE_KEYS.some(function (r) { return r[0] === e.role && r[0] !== 'other'; });
    var curRole = edit ? (knownRole ? e.role : 'other') : 'partner';
    var nameFld = edit ? fld('الاسم', inp('co_pn', e.name || '', 'maxlength="255"'))
      : '<p class="co-lead sm">التسجيل من المنصة فقط: اختر شخصًا <b>مسجّلًا</b> لإضافته كشريك.</p>' + fld('اختر من المستخدمين المسجّلين',
        '<input id="co_pn" type="text" list="co_pul" autocomplete="off" placeholder="ابحث بالاسم أو البريد"><datalist id="co_pul">' + userOpts() + '</datalist>', getUsers().length ? '' : 'جارٍ جلب المسجّلين…', 'co_pun');
    var contrib = edit && (e.contributions || 0) > 0;
    var form = nameFld + fld('الصفة', sel('co_pr', ROLE_KEYS, curRole)) + '<div id="co_pro_w" class="co-f"' + (curRole === 'other' ? '' : ' hidden') + '><label>اكتب الصفة</label>' + inp('co_pro', knownRole ? '' : (e.role || ''), 'maxlength="100"') + '</div>'
      + '<div class="co-f2">' + fld('الحصة ٪', numInp('co_pe', edit ? e.equity : '')) + fld('رأس المال المتفق عليه بالجنيه', numInp('co_pc', edit && e.agreed ? amountOfList(e.agreed, 'EGP') || '' : '')) + '</div>'
      + fld('رأس المال المتفق عليه بالدولار', numInp('co_pd', edit && e.agreed ? amountOfList(e.agreed, 'USD') || '' : '')) + fld('ملاحظة', area('co_pnote', e.notes || '', 300))
      + (contrib ? '<p class="co-fine">للشريك دفعات مسجّلة — احذف دفعاته أولًا لتتمكن من حذفه.</p>' : '');
    function amountOfList(l, c) { var a = (l || []).filter(function (x) { return x.currency === c; })[0]; return a ? a.amount : 0; }
    sheet({
      title: edit ? 'تعديل شريك' : 'أضف شريكًا', form: form, btnReview: 'راجع', btnConfirm: 'أكّد الحفظ',
      wire: function (s) {
        var r = q('#co_pr', s); r.onchange = function () { q('#co_pro_w', s).hidden = r.value !== 'other'; };
        if (!edit && !getUsers().length) {                                   // القائمة لم تصل بعد: ننتظرها ثم نملأ الخيارات
          var tries = 0, t = setInterval(function () {
            var dl = q('#co_pul', s);
            if (!dl || ++tries > 40) { clearInterval(t); var h0 = q('#co_pun small', s); if (h0 && dl && !getUsers().length) h0.textContent = 'تعذّر جلب المسجّلين.'; return; }
            if (getUsers().length) { clearInterval(t); dl.innerHTML = userOpts(); var h = q('#co_pun small', s); if (h) h.remove(); }
          }, 400);
        }
      },
      collect: function (s) {
        var name = val(s, 'co_pn');
        if (!edit) {
          var us = getUsers(), u = us.filter(function (x) { return userLabel(x) === name; })[0];
          if (!u) { var byName = us.filter(function (x) { return x.name === name; }); if (byName.length === 1) u = byName[0]; }
          if (!u && !us.length) return { ok: false, error: 'جارٍ جلب المسجّلين — انتظر لحظة ثم حاول مرة أخرى' };
          if (!u) return { ok: false, error: 'اختر شخصًا مسجّلًا من القائمة (وإن تشابهت الأسماء فاختر بالبريد)' };
          name = u.name;
        } else if (!name) return { ok: false, error: 'اكتب الاسم' };
        var role = val(s, 'co_pr'); if (role === 'other') { role = val(s, 'co_pro'); if (!role) return { ok: false, error: 'اكتب الصفة' }; }
        var eq = readNum(s, 'co_pe', 'الحصة', { req: true, max: 100 }); if (!eq.ok) return eq;
        var c1 = readNum(s, 'co_pc', 'رأس المال بالجنيه', { max: 100000000 }); if (!c1.ok) return c1;
        var c2 = readNum(s, 'co_pd', 'رأس المال بالدولار', { max: 100000000 }); if (!c2.ok) return c2;
        return { ok: true, payload: { name: name, role: role, equity_percent: eq.v, capital_egp: c1.v || 0, capital_usd: c2.v || 0, notes: val(s, 'co_pnote') } };
      },
      review: function (p) {
        if (!edit) return { lead: 'راجع قبل التأكيد', items: ['سيُضاف الشريك «' + p.name + '» بحصة ' + U.fmt(p.equity_percent) + '٪' + (p.capital_egp || p.capital_usd ? ' ورأس مال متفق عليه ' + (lines([{ currency: 'EGP', amount: p.capital_egp }, { currency: 'USD', amount: p.capital_usd }]) || '') : '') + '.'] };
        var rows = [], oe = e.equity || 0, oc = amountOfList(e.agreed, 'EGP'), od = amountOfList(e.agreed, 'USD');
        if (oe !== p.equity_percent) rows.push({ label: 'الحصة', from: U.fmt(oe) + '٪', to: U.fmt(p.equity_percent) + '٪' });
        if (oc !== p.capital_egp) rows.push({ label: 'رأس المال بالجنيه', from: money(oc, 'EGP'), to: money(p.capital_egp, 'EGP') });
        if (od !== p.capital_usd) rows.push({ label: 'رأس المال بالدولار', from: money(od, 'USD'), to: money(p.capital_usd, 'USD') });
        if (e.role !== p.role) rows.push({ label: 'الصفة', from: roleLabel(e.role), to: roleLabel(p.role) });
        return rows.length ? { lead: 'ستتغيّر بيانات «' + e.name + '». راجع قبل التأكيد:', rows: rows } : { skip: true };
      },
      send: function (p) { return edit ? api('PUT', '/partners/' + edit.id, p) : api('POST', '/partners', p); },
      onOk: function () { reloadP(); afterWrite(edit ? 'حُدّث الشريك.' : 'أُضيف الشريك.', ['partners']); },
      onLost: function () { reloadP(); },
      danger: edit && !contrib ? { label: 'احذف الشريك', run: function () { window.closeModal(); delSheet({ title: 'حذف شريك', lead: 'سيُحذف الشريك «' + e.name + '» من القائمة.', btn: 'احذف الشريك',
        send: function () { return api('DELETE', '/partners/' + edit.id); }, onOk: function () { reloadP(); afterWrite('حُذف الشريك.', ['partners']); } }); } } : null
    });
  }

  // —— دفعة شريك
  function openContribution(pid) {
    var plist = realPartners();
    if (!plist.length) { setNote('أضف شريكًا أولًا.'); redraw(); return; }
    var form = fld('الشريك', sel('co_cp', plist.map(function (p) { return [p.id, p.name]; }), pid || plist[0].id))
      + fld('نوع الدفعة', sel('co_ck', [['cash', 'نقدًا'], ['asset', 'معدات أو أصول'], ['other', 'أخرى']], 'cash'))
      + '<div id="co_cko_w" class="co-f" hidden><label>اكتب النوع</label>' + inp('co_cko', '', 'maxlength="60"') + '</div>'
      + '<div class="co-f2">' + fld('المبلغ', numInp('co_ca', '')) + fld('العملة', sel('co_cc', CURS, 'EGP')) + '</div>'
      + fld('التاريخ', dateInp('co_cd', todayIso()))
      + '<div id="co_cn_w" class="co-f" hidden><label>اسم المعدة</label>' + inp('co_cn', '', 'maxlength="255"') + '</div>'
      + '<label class="co-ck" id="co_cashw"><input type="checkbox" id="co_cash" checked><span>سجّلها في حركة النقد كرأس مال داخل</span></label>'
      + '<label class="co-ck" id="co_assw" hidden><input type="checkbox" id="co_ass" checked><span>سجّلها في المعدات</span></label><p class="co-fine" id="co_usdn" hidden>المعدات تُسجَّل بالجنيه فقط — سجّل الدفعة بالجنيه لتُضاف إلى المعدات.</p>'
      + fld('ملاحظة', area('co_cnote', '', 300));
    sheet({
      title: 'سجّل دفعة', form: form, btnReview: 'راجع', btnConfirm: 'أكّد التسجيل',
      wire: function (s) {
        function sync() {
          var k = q('#co_ck', s).value, usd = q('#co_cc', s).value === 'USD';
          q('#co_cko_w', s).hidden = k !== 'other'; q('#co_cn_w', s).hidden = k !== 'asset';
          q('#co_cashw', s).hidden = k !== 'cash'; q('#co_assw', s).hidden = k !== 'asset';
          var a = q('#co_ass', s); a.disabled = usd; if (usd) a.checked = false; else if (k === 'asset' && !a.dataset.t) { a.checked = true; }
          q('#co_usdn', s).hidden = !(k === 'asset' && usd);
        }
        ['co_ck', 'co_cc'].forEach(function (i) { q('#' + i, s).onchange = sync; }); sync();
      },
      collect: function (s) {
        var kind = val(s, 'co_ck'), amt = readNum(s, 'co_ca', 'المبلغ', { req: true, pos: true, max: 100000000 });
        if (!amt.ok) return amt;
        var kind_other = kind === 'other' ? val(s, 'co_cko') : '';
        if (kind === 'other' && !kind_other) return { ok: false, error: 'اكتب نوع الدفعة' };
        var asset_name = kind === 'asset' ? val(s, 'co_cn') : '';
        if (kind === 'asset' && !asset_name) return { ok: false, error: 'اكتب اسم المعدة' };
        var date = val(s, 'co_cd'); if (!date) return { ok: false, error: 'اختر التاريخ' };
        var p = byId(plist, val(s, 'co_cp'));
        return { ok: true, payload: { partner_id: p.id, partner_name: p.name, kind: kind, kind_other: kind_other || undefined, amount: amt.v, currency: val(s, 'co_cc'), date: date, note: val(s, 'co_cnote'),
                 record_cash: kind === 'cash' && checked(s, 'co_cash'), asset_name: asset_name || undefined, record_asset: kind === 'asset' && checked(s, 'co_ass') } };
      },
      review: function (p) {
        var t = 'دفعة ' + money(p.amount, p.currency) + ' من ' + p.partner_name + ' بتاريخ ' + U.dateText(p.date) + (p.record_cash ? '، وتدخل حركة النقد' : '') + (p.record_asset ? '، وتُضاف «' + p.asset_name + '» إلى المعدات بقيمة ' + money(p.amount, p.currency) : '');
        return { lead: 'سيُسجَّل:', items: [t + '.'] };
      },
      send: function (p, op) {
        var b = { partner_id: p.partner_id, kind: p.kind, kind_other: p.kind_other, date: p.date, amount: p.amount, currency: p.currency, note: p.note, record_cash: p.record_cash, asset_name: p.asset_name, record_asset: p.record_asset, confirmed: true, op_id: op };
        return api('POST', '/v2/company/contributions', b);
      },
      onOk: function () { afterWrite('سُجّلت الدفعة.', ['contribs', 'cash', 'assets', 'partners']); }, onLost: function () { loadMany(['contribs', 'cash', 'assets', 'summary'], true); }
    });
  }
  function delContribution(id) {
    var c = byId(items('contribs'), id);
    if (!c) return;
    delSheet({ title: 'حذف دفعة', lead: 'ستُحذف دفعة ' + money(c.amount, c.currency) + ' من ' + (c.partner_name || 'الشريك') + (c.cash_tx_id ? ' وحركة النقد المرتبطة بها' : '') + (c.asset_id ? ' و«' + (c.asset_name || 'المعدة') + '» من المعدات' : '') + '.',
      btn: 'أكّد الحذف', send: function () { return api('DELETE', '/v2/company/contributions/' + c.id, { confirmed: true }); },
      onOk: function () { afterWrite('حُذفت الدفعة.', ['contribs', 'cash', 'assets']); }, onLost: function () { loadMany(['contribs', 'cash', 'assets', 'summary'], true); } });
  }
  function delOpp(id) {
    var o = byId(listOf('opps'), id), E = ep();
    if (!o) return;
    delSheet({ title: 'حذف فرصة', lead: 'ستُحذف فرصة «' + (o.course_title || 'فرصة') + '».', btn: 'احذف الفرصة', send: function () { return api('DELETE', '/investment-opportunities/' + o.id); },
      onOk: function () { load('opps', true); if (E) E.reload('investment', null); setNote('حُذفت الفرصة.'); redraw(); } });
  }

  // —— معدة
  function openAssetChoice() {
    var s = openSheet('أضف', '<div class="co-more"><button type="button" class="co-btn2" data-c="a">معدة أو أصل</button><button type="button" class="co-btn2" data-c="s">اشتراك</button></div>');
    if (!s) return;
    q('[data-c="a"]', s).onclick = function () { window.closeModal(); openEquipment(null); };
    q('[data-c="s"]', s).onclick = function () { window.closeModal(); openSubscription(null); };
  }
  function openEquipment(row) {
    var e = row || {}, edit = !!row;
    var cats = Object.keys(CO.CAT_LABEL).map(function (k) { return [k, CO.CAT_LABEL[k]]; });
    var form = fld('الاسم', inp('co_an', e.name || '', 'maxlength="255"')) + fld('النوع', sel('co_ac', cats, e.category || 'equipment')) + fld('المالك', inp('co_ao', edit ? (e.owner || '') : 'الشركة', 'maxlength="255"'))
      + '<div class="co-f2">' + fld('القيمة بالجنيه', numInp('co_av', edit ? e.value_egp : '')) + fld('إيجار شهري للشركة بالجنيه (اختياري)', numInp('co_ar', edit && e.monthly_rent_egp ? e.monthly_rent_egp : '')) + '</div>'
      + fld('الحالة', sel('co_as', pairOf(CO.STATUS_LABEL), e.status || 'owned_by_company')) + fld('ملاحظة', area('co_anote', e.notes || '', 300));
    sheet({
      title: edit ? 'تعديل معدة' : 'أضف معدة', form: form,
      collect: function (s) {
        var name = val(s, 'co_an'); if (!name) return { ok: false, error: 'اكتب اسم المعدة' };
        var v = readNum(s, 'co_av', 'القيمة', { req: true, max: 100000000 }); if (!v.ok) return v;
        var r = readNum(s, 'co_ar', 'الإيجار الشهري', { max: 100000000 }); if (!r.ok) return r;
        return { ok: true, payload: { name: name, category: val(s, 'co_ac'), owner: val(s, 'co_ao') || 'الشركة', value_egp: v.v, monthly_rent_egp: r.v || 0, status: val(s, 'co_as'), notes: val(s, 'co_anote') } };
      },
      send: function (p) { return edit ? api('PUT', '/assets/' + e.id, p) : api('POST', '/assets', p); },
      onOk: function () { var E = ep(); if (E) E.reload('dashboard', null); afterWrite(edit ? 'حُدّثت المعدة.' : 'أُضيفت المعدة.', ['assets']); }, onLost: function () { load('assets', true); },
      danger: edit ? { label: 'احذف المعدة', run: function () { window.closeModal(); delSheet({ title: 'حذف معدة', lead: 'ستُحذف «' + e.name + '» من المعدات.', btn: 'احذف المعدة', send: function () { return api('DELETE', '/assets/' + e.id); },
        onOk: function () { afterWrite('حُذفت المعدة.', ['assets']); } }); } } : null
    });
  }

  // —— اشتراك
  function openSubscription(row) {
    var e = row || {}, edit = !!row;
    var cyc = e.cycle || 'monthly';
    var form = fld('الاسم', inp('co_sn', e.name || '', 'maxlength="120"')) + '<div class="co-f2">' + fld('المبلغ', numInp('co_sa', edit ? e.amount : '')) + fld('العملة', sel('co_sc', CURS, e.currency || 'EGP')) + '</div>'
      + fld('كل', sel('co_sy', [['monthly', 'شهر'], ['yearly', 'سنة'], ['other', 'أخرى']], cyc)) + '<div id="co_syo_w" class="co-f"' + (cyc === 'other' ? '' : ' hidden') + '><label>اكتب المدة</label>' + inp('co_syo', e.cycle_other || '', 'maxlength="60"') + '</div>'
      + fld('موعد التجديد القادم', dateInp('co_sr', e.renews_on || '')) + fld('يدفعه', inp('co_sp', e.paid_by || '', 'maxlength="120"')) + fld('ملاحظة', area('co_snote', e.note || '', 300));
    sheet({
      title: edit ? 'تعديل اشتراك' : 'أضف اشتراكًا', form: form,
      wire: function (s) { var y = q('#co_sy', s); y.onchange = function () { q('#co_syo_w', s).hidden = y.value !== 'other'; }; },
      collect: function (s) {
        var name = val(s, 'co_sn'); if (!name) return { ok: false, error: 'اكتب اسم الاشتراك' };
        var a = readNum(s, 'co_sa', 'المبلغ', { req: true, pos: true, max: 100000000 }); if (!a.ok) return a;
        var cy = val(s, 'co_sy'), other = val(s, 'co_syo'); if (cy === 'other' && !other) return { ok: false, error: 'اكتب مدة الاشتراك' };
        return { ok: true, payload: { name: name, amount: a.v, currency: val(s, 'co_sc'), cycle: cy, cycle_other: cy === 'other' ? other : null, renews_on: val(s, 'co_sr') || null, paid_by: val(s, 'co_sp') || null, note: val(s, 'co_snote') } };
      },
      send: function (p) { return edit ? api('PUT', '/v2/company/subscriptions/' + e.id, p) : api('POST', '/v2/company/subscriptions', p); },
      onOk: function () { afterWrite(edit ? 'حُدّث الاشتراك.' : 'أُضيف الاشتراك.', ['subs']); }, onLost: function () { load('subs', true); }
    });
  }
  function nextRenewal(s, dateIso) {
    var base = s.renews_on || dateIso;
    if (s.cycle !== 'monthly' && s.cycle !== 'yearly') return s.renews_on || null;
    var m = /^(\d{4})-(\d{2})-(\d{2})$/.exec(base); if (!m) return null;
    var add = s.cycle === 'monthly' ? 1 : 12, y = +m[1], mo = +m[2] - 1 + add, d = +m[3];
    y += Math.floor(mo / 12); mo = mo % 12;
    var last = new Date(y, mo + 1, 0).getDate();
    return y + '-' + ('0' + (mo + 1)).slice(-2) + '-' + ('0' + Math.min(d, last)).slice(-2);
  }
  function openPaid(id) {
    var sub = byId(items('subs'), id);
    if (!sub) { notReady('الاشتراكات'); return; }
    sheet({
      title: 'سجّل الدفع', form: '<p class="co-lead sm">اشتراك «' + esc(sub.name) + '» — ' + esc(subAmountText(sub)) + '</p>' + fld('تاريخ الدفع', dateInp('co_pd2', todayIso())),
      btnReview: 'راجع', btnConfirm: 'أكّد الدفع',
      collect: function (s) { var d = val(s, 'co_pd2'); return d ? { ok: true, payload: { date: d } } : { ok: false, error: 'اختر التاريخ' }; },
      review: function (p) {
        var nx = nextRenewal(sub, p.date);
        return { lead: 'سيُسجَّل:', items: ['مصروف ' + money(sub.amount, sub.currency) + ' لـ«' + sub.name + '» بتاريخ ' + U.dateText(p.date) + (nx ? '، وموعد التجديد يصبح ' + U.dateText(nx) : '، وموعد التجديد لا يتغيّر') + '.'] };
      },
      send: function (p, op) { return api('POST', '/v2/company/subscriptions/' + sub.id + '/paid', { date: p.date, confirmed: true, op_id: op }); },
      onOk: function () { afterWrite('سُجّل الدفع.', ['subs']); var E = ep(); if (E) E.reload('dashboard', null); }, onLost: function () { loadMany(['subs', 'summary'], true); }
    });
  }
  function toggleSub(sub, status) {
    api('PUT', '/v2/company/subscriptions/' + sub.id, { status: status }).then(function () { afterWrite(status === 'stopped' ? 'أُوقف الاشتراك.' : 'أُعيد تشغيل الاشتراك.', ['subs']); })
      .catch(function (e) { setNote(errMsg(e)); redraw(); });
  }
  function openImportSubs() {
    var rows = CO.legacySubs(listOf('assets'));
    if (!rows.length) return;
    sheet({
      title: 'انقلها إلى الاشتراكات', btnReview: 'راجع', btnConfirm: 'أكّد النقل',
      form: '<p class="co-lead sm">اختر البنود التي ستنتقل:</p><div class="co-perms one">' + rows.map(function (a) {
        return '<label class="co-ck"><input type="checkbox" class="co-imp" value="' + esc(a.id) + '" checked><span>' + esc(a.name + ' · ' + money(a.monthly_rent_egp, 'EGP') + ' شهريًا') + '</span></label>'; }).join('') + '</div>',
      collect: function (s) { var ids = qa('.co-imp:checked', s).map(function (c) { return +c.value; }); return ids.length ? { ok: true, payload: { ids: ids } } : { ok: false, error: 'اختر بندًا واحدًا على الأقل' }; },
      review: function (p) { return { lead: 'راجع قبل التأكيد', items: ['ستُنقل ' + U.U(p.ids.length, ['بند واحد', 'بندان', 'بنود', 'بندًا']) + ' من المعدات إلى الاشتراكات (شهريًا، بالجنيه، بلا موعد تجديد — أضف الموعد بعدها).'] }; },
      send: function (p) { return api('POST', '/v2/company/subscriptions/import', { asset_ids: p.ids, confirmed: true }); },
      onOk: function (r) { var E = ep(); if (E) E.reload('dashboard', null); afterWrite('نُقلت الاشتراكات.', ['assets', 'subs']); }, onLost: function () { loadMany(['assets', 'subs', 'summary'], true); }
    });
  }

  // —— اتفاق
  var KINDS = [['sponsor', 'راعٍ'], ['content', 'اتفاق محتوى'], ['book', 'اتفاق كتاب'], ['company_paper', 'أوراق الشركة'], ['other', 'أخرى']];
  function openAgreement(row) {
    var e = row || {}, edit = !!row;
    var form = fld('النوع', sel('co_gk', KINDS, e.kind || 'sponsor')) + '<div id="co_gko_w" class="co-f"' + (e.kind === 'other' ? '' : ' hidden') + '><label>اكتب النوع</label>' + inp('co_gko', e.kind_other || '', 'maxlength="60"') + '</div>'
      + fld('الطرف الآخر', inp('co_gp', e.party || '', 'maxlength="160"')) + fld('ماذا نقدّم', inp('co_gs', e.summary || '', 'maxlength="300"')) + fld('المقابل أو القسمة', inp('co_gt', e.terms || '', 'maxlength="300" placeholder="مثلًا: نصف الدخل لكل طرف"'))
      + '<div class="co-f2">' + fld('المبلغ (اختياري)', numInp('co_ga', e.amount || '')) + fld('العملة', sel('co_gc', CURS_ALL, e.currency || 'EGP')) + '</div>'
      + '<div class="co-f2">' + fld('يبدأ', dateInp('co_gb', e.starts_on || '')) + fld('ينتهي (اختياري)', dateInp('co_ge', e.ends_on || '')) + '</div>'
      + fld('الحالة', sel('co_gst', [['active', 'ساري'], ['draft', 'مسودة']].concat(e.status === 'ended' ? [['ended', 'انتهى']] : []), e.status || 'active'))
      + fld('كود التتبّع (يُستخدم عند تفعيل عدّ الزيارات)', inp('co_gr', e.ref_code || '', 'dir="ltr" maxlength="40" placeholder="smart-office"'), 'حروف إنجليزية صغيرة وأرقام وشرطة فقط') + fld('ملاحظة', area('co_gn', e.note || '', 500));
    sheet({
      title: edit ? 'تعديل اتفاق' : 'أضف اتفاقًا', form: form,
      wire: function (s) { var k = q('#co_gk', s); k.onchange = function () { q('#co_gko_w', s).hidden = k.value !== 'other'; }; },
      collect: function (s) {
        var party = val(s, 'co_gp'); if (!party) return { ok: false, error: 'اكتب اسم الطرف الآخر' };
        var kind = val(s, 'co_gk'), ko = val(s, 'co_gko'); if (kind === 'other' && !ko) return { ok: false, error: 'اكتب نوع الاتفاق' };
        var a = readNum(s, 'co_ga', 'المبلغ', { pos: true, max: 100000000 }); if (!a.ok) return a;
        var b = val(s, 'co_gb'), en = val(s, 'co_ge'); if (b && en && en < b) return { ok: false, error: 'تاريخ الانتهاء قبل تاريخ البداية' };
        var ref = val(s, 'co_gr'); if (ref && !/^[a-z0-9-]{3,40}$/.test(ref)) return { ok: false, error: 'كود التتبّع: حروف إنجليزية صغيرة وأرقام وشرطة فقط (٣ إلى ٤٠)' };
        return { ok: true, payload: { kind: kind, kind_other: kind === 'other' ? ko : null, party: party, summary: val(s, 'co_gs'), terms: val(s, 'co_gt'), amount: a.v, currency: a.v != null ? val(s, 'co_gc') : null,
                 starts_on: b || null, ends_on: en || null, status: val(s, 'co_gst'), ref_code: ref || null, note: val(s, 'co_gn') } };
      },
      send: function (p) { return edit ? api('PUT', '/v2/company/agreements/' + e.id, p) : api('POST', '/v2/company/agreements', p); },
      onOk: function () { afterWrite(edit ? 'حُدّث الاتفاق.' : 'أُضيف الاتفاق.', ['deals']); }, onLost: function () { load('deals', true); }
    });
  }
  function openRenew(a) {
    var st0 = a.ends_on ? addDaysIso(a.ends_on, 1) : todayIso();
    var dur = a.starts_on && a.ends_on ? diffDays(a.starts_on, a.ends_on) : null;
    var en0 = dur !== null ? addDaysIso(st0, dur) : '';
    var form = '<p class="co-lead sm">تجديد اتفاق «' + esc(a.party) + '»</p><div class="co-f2">' + fld('يبدأ', dateInp('co_rs', st0)) + fld('ينتهي (اختياري)', dateInp('co_re', en0)) + '</div>'
      + '<div class="co-f2">' + fld('المبلغ (اختياري)', numInp('co_ra', a.amount || '')) + fld('العملة', sel('co_rc', CURS_ALL, a.currency || 'EGP')) + '</div>';
    sheet({
      title: 'تجديد اتفاق', form: form, btnReview: 'راجع', btnConfirm: 'أكّد التجديد',
      collect: function (s) {
        var b = val(s, 'co_rs'), en = val(s, 'co_re'); if (!b) return { ok: false, error: 'اختر تاريخ البداية' };
        if (en && en < b) return { ok: false, error: 'تاريخ الانتهاء قبل تاريخ البداية' };
        var am = readNum(s, 'co_ra', 'المبلغ', { pos: true, max: 100000000 }); if (!am.ok) return am;
        return { ok: true, payload: { starts_on: b, ends_on: en || null, amount: am.v, currency: am.v != null ? val(s, 'co_rc') : null } };
      },
      review: function (p) { return { lead: 'راجع قبل التأكيد', items: ['سيُنهى اتفاق «' + a.party + '» الحالي، ويُسجَّل اتفاق جديد من ' + U.dateText(p.starts_on) + ' إلى ' + (p.ends_on ? U.dateText(p.ends_on) : 'بلا تاريخ انتهاء') + (p.amount ? ' بمبلغ ' + money(p.amount, p.currency) : '') + '.'] }; },
      send: function (p, op) { var b = { starts_on: p.starts_on, confirmed: true, op_id: op }; if (p.ends_on) b.ends_on = p.ends_on; if (p.amount != null) { b.amount = p.amount; b.currency = p.currency; } return api('POST', '/v2/company/agreements/' + a.id + '/renew', b); },
      onOk: function () { afterWrite('جُدّد الاتفاق.', ['deals']); }, onLost: function () { loadMany(['deals', 'summary'], true); }
    });
  }
  var METHODS = [['bank_transfer', 'تحويل بنكي'], ['cash', 'نقدًا'], ['other', 'أخرى']];
  // سجّل مبلغًا مستلمًا: kind = 'agreement' | 'ad_result'
  function openReceive(kind, a, client) {
    var isAd = kind === 'ad_result', due = isAd ? CO.dueOf(a) : null;
    var party = isAd ? client.name : a.party, cur = isAd ? client.currency : (a.currency || 'EGP');
    if (isAd && !due) { setNote('المستحق غير محسوب بعد — سجّل دخلهم من الحملة أولًا.'); redraw(); return; }
    var form = '<p class="co-lead sm">' + esc(isAd ? 'تحصيل كشف ' + CO.monthText(a.period) + ' من ' + client.name : 'مبلغ مستلم من ' + a.party) + '</p>'
      + '<div class="co-f2">' + fld('المبلغ', numInp('co_ia', isAd ? due.amount : (a.amount || ''), isAd ? 'readonly' : '')) + fld('العملة', sel('co_ic', (isAd || a.currency) ? [[cur, U.curName(cur)]] : CURS_ALL, cur)) + '</div>'
      + fld('التاريخ', dateInp('co_id', todayIso())) + fld('طريقة الاستلام', sel('co_im', METHODS, 'bank_transfer'));
    sheet({
      title: isAd ? 'سجّل التحصيل' : 'سجّل مبلغًا مستلمًا', form: form, btnReview: 'راجع', btnConfirm: 'أكّد التسجيل',
      collect: function (s) {
        var am = readNum(s, 'co_ia', 'المبلغ', { req: true, pos: true, max: 100000000 }); if (!am.ok) return am;
        var d = val(s, 'co_id'); if (!d) return { ok: false, error: 'اختر التاريخ' };
        return { ok: true, payload: { amount: am.v, currency: val(s, 'co_ic'), date: d, method: val(s, 'co_im') } };
      },
      review: function (p) { return { lead: 'سيُسجَّل:', items: ['دخل ' + money(p.amount, p.currency) + ' من ' + party + ' بتاريخ ' + U.dateText(p.date) + '.'] }; },
      send: function (p, op) { return api('POST', '/v2/company/income', { from_kind: kind, from_id: a.id, amount: p.amount, currency: p.currency, date: p.date, method: p.method, confirmed: true, op_id: op }); },
      onOk: function () { var E = ep(); if (E) E.reload('dashboard', null); afterWrite('سُجّل الدخل.', ['deals', 'ads']); load('dash', true); }, onLost: function () { loadMany(['deals', 'ads', 'summary'], true); }
    });
  }
  function endDeal(a) {
    confirmSheet({ title: 'أنهِ الاتفاق', lead: 'سيُنهى اتفاق «' + a.party + '».', btn: 'أنهِ الاتفاق', send: function () { return api('PUT', '/v2/company/agreements/' + a.id, { status: 'ended' }); },
      onOk: function () { afterWrite('أُنهي الاتفاق.', ['deals']); }, onLost: function () { load('deals', true); } });
  }
  function delDeal(a) {
    sheet({ title: 'حذف اتفاق', form: '<p class="co-lead">ستُحذف اتفاقية «' + esc(a.party) + '».</p>', collect: function () { return { ok: true, payload: 1 }; }, btnReview: 'راجع', btnConfirm: 'أكّد الحذف',
      review: function () { return { lead: 'راجع قبل التأكيد', items: ['سيُحذف اتفاق «' + a.party + '» نهائيًا.'] }; },
      send: function () { return api('DELETE', '/v2/company/agreements/' + a.id, { confirmed: true }); }, onOk: function () { afterWrite('حُذف الاتفاق.', ['deals']); }, onLost: function () { load('deals', true); } });
  }
  function dealMore(a) {
    var vis = CO.dealAction(a, now()), acts = [];
    if (a.status === 'active' && vis !== 'receive') acts.push({ label: 'سجّل مبلغًا مستلمًا', run: function () { openReceive('agreement', a); } });
    if (vis !== 'renew') acts.push({ label: 'جدّد', run: function () { openRenew(a); } });
    if (vis !== 'edit') acts.push({ label: 'عدّل', run: function () { openAgreement(a); } });
    if (a.status === 'active') acts.push({ label: 'أنهِ الاتفاق', danger: true, run: function () { endDeal(a); } });
    if (a.status === 'draft' || !(a.received && a.received.length)) acts.push({ label: 'احذف', danger: true, run: function () { delDeal(a); } });
    moreSheet((CO.KIND_LABEL[a.kind] || '') + ': ' + a.party, acts);
  }
  function subMore(s) {
    var acts = [{ label: 'عدّل', run: function () { openSubscription(s); } }];
    if (s.status === 'active') acts.push({ label: 'أوقفه', run: function () { toggleSub(s, 'stopped'); } });
    acts.push({ label: 'احذف', danger: true, run: function () {
      sheet({ title: 'حذف اشتراك', form: '<p class="co-lead">سيُحذف اشتراك «' + esc(s.name) + '».</p>', collect: function () { return { ok: true, payload: 1 }; }, btnReview: 'راجع', btnConfirm: 'أكّد الحذف',
        review: function () { return { lead: 'راجع قبل التأكيد', items: ['سيُحذف اشتراك «' + s.name + '» نهائيًا (المصروفات المسجّلة سابقًا تبقى).'] }; },
        send: function () { return api('DELETE', '/v2/company/subscriptions/' + s.id, { confirmed: true }); }, onOk: function () { afterWrite('حُذف الاشتراك.', ['subs']); }, onLost: function () { load('subs', true); } }); } });
    moreSheet(s.name, acts);
  }

  // —— كشف الحساب
  function copyText(text, btn) {
    function fallback() {
      var ta = document.createElement('textarea'); ta.value = text; ta.setAttribute('readonly', ''); ta.style.cssText = 'position:fixed;top:0;opacity:0';
      document.body.appendChild(ta); ta.select(); var ok = false; try { ok = document.execCommand('copy'); } catch (e) {} ta.remove();
      return ok;
    }
    function done(ok) { if (btn) { var t = btn.textContent; btn.textContent = ok ? 'تم النسخ' : 'حدّد النص وانسخه'; setTimeout(function () { btn.textContent = t; }, 1800); } }
    try { if (navigator.clipboard && navigator.clipboard.writeText) { navigator.clipboard.writeText(text).then(function () { done(true); }, function () { done(fallback()); }); return; } } catch (e) {}
    done(fallback());
  }
  function printTexts(texts) {
    var old = document.getElementById('coPrint'); if (old) old.remove();
    var d = document.createElement('div'); d.id = 'coPrint';
    d.innerHTML = texts.map(function (t) { return '<pre class="co-stmt">' + esc(t) + '</pre>'; }).join('');
    document.body.appendChild(d); document.body.classList.add('co-printing');
    function clean() { document.body.classList.remove('co-printing'); var x = document.getElementById('coPrint'); if (x) x.remove(); window.removeEventListener('afterprint', clean); }
    window.addEventListener('afterprint', clean);
    try { window.print(); } catch (e) {}
    setTimeout(function () { if (document.body.classList.contains('co-printing') && !window.matchMedia('print').matches) clean(); }, 1500);
  }
  function markSent(ids, text) {
    return api('POST', '/v2/company/ad-results/sent', { ids: ids }).then(function () { window.closeModal(); afterWrite(text, ['ads']); }).catch(function (e) { setNote(errMsg(e)); window.closeModal(); redraw(); });
  }
  function openStatement(cid, rid) {
    var c = byId(items('ads'), cid), r = c && byId(c.results, rid);
    if (!c || !r) return;
    var text = CO.statementText(c, r), due = CO.dueOf(r), collected = !!r.revenue_id, sent = !!r.sent_at;
    var prim = '', second = '';
    if (!sent) prim = due ? '<button type="button" class="co-btn1" data-s="sent">علّمه مُرسلًا</button>' : '';
    else if (due && !collected) prim = '<button type="button" class="co-btn1" data-s="collect">سجّل التحصيل</button>';
    var links = '';
    if (due && !collected && !(sent)) links += '<button type="button" class="co-link" data-s="collect">سجّل التحصيل</button>';
    if (!collected) links += '<button type="button" class="co-link" data-s="edit">عدّل النتيجة</button><button type="button" class="co-link co-del" data-s="del">احذف النتيجة</button>';
    var s = openSheet('كشف حساب — ' + c.name, '<pre class="co-stmt" id="coStmt">' + esc(text) + '</pre>' + (due ? '' : '<p class="co-fine">سجّل دخلهم من الحملة أولًا ليُحسب المستحق قبل تعليم الكشف مُرسلًا.</p>')
      + '<div class="co-acts">' + prim + '<button type="button" class="co-btn2" data-s="copy">انسخ</button><button type="button" class="co-btn2" data-s="print">اطبع</button></div><div class="co-acts links">' + links + '</div>');
    if (!s) return;
    s.addEventListener('click', function (e) {
      var b = e.target.closest ? e.target.closest('[data-s]') : null; if (!b) return;
      var a = b.getAttribute('data-s');
      if (a === 'copy') copyText(text, b);
      else if (a === 'print') printTexts([text]);
      else if (a === 'sent') markSent([r.id], 'عُلّم الكشف مُرسلًا.');
      else if (a === 'collect') { window.closeModal(); openReceive('ad_result', r, c); }
      else if (a === 'edit') { window.closeModal(); openResult(c, r); }
      else if (a === 'del') { window.closeModal(); delResult(c, r); }
    });
  }
  function openAllStatements() {
    var un = unsentResults(items('ads'));
    if (!un.length) { setNote('لا كشوف حساب جاهزة للإرسال.'); redraw(); return; }
    var texts = un.map(function (x) { return CO.statementText(x.c, x.r); });
    var s = openSheet('كشوف الحساب', '<div class="co-stmts">' + texts.map(function (t) { return '<pre class="co-stmt">' + esc(t) + '</pre>'; }).join('') + '</div>'
      + '<div class="co-acts"><button type="button" class="co-btn1" data-s="sent">علّمها مُرسلة (' + esc(arN(un.length)) + ')</button><button type="button" class="co-btn2" data-s="copy">انسخ الكل</button><button type="button" class="co-btn2" data-s="print">اطبع الكل</button></div>');
    if (!s) return;
    s.addEventListener('click', function (e) {
      var b = e.target.closest ? e.target.closest('[data-s]') : null; if (!b) return;
      var a = b.getAttribute('data-s');
      if (a === 'copy') copyText(texts.join('\n\n'), b);
      else if (a === 'print') printTexts(texts);
      else if (a === 'sent') markSent(un.map(function (x) { return x.r.id; }), 'عُلّمت الكشوف مُرسلة.');
    });
  }
  function delResult(c, r) {
    sheet({ title: 'حذف نتيجة', form: '<p class="co-lead">ستُحذف نتيجة ' + esc(CO.monthText(r.period)) + ' لعميل «' + esc(c.name) + '».</p>', collect: function () { return { ok: true, payload: 1 }; }, btnReview: 'راجع', btnConfirm: 'أكّد الحذف',
      review: function () { return { lead: 'راجع قبل التأكيد', items: ['ستُحذف نتيجة ' + CO.monthText(r.period) + ' نهائيًا.'] }; },
      send: function () { return api('DELETE', '/v2/company/ad-results/' + r.id, { confirmed: true }); }, onOk: function () { afterWrite('حُذفت النتيجة.', ['ads']); }, onLost: function () { load('ads', true); } });
  }

  // —— عميل إعلانات
  var DEAL_OPTS = [['percent', 'نسبة من دخل الحملة'], ['fixed_plus_percent', 'مبلغ ثابت + نسبة'], ['fixed', 'مبلغ ثابت'], ['other', 'أخرى']];
  function openClient(row) {
    if (isLoad('ledger')) {                                                                  // نجلب الأرصدة أولًا ليظهر ربط العمل في الورقة
      load('ledger', false);
      var tries = 0, t = setInterval(function () { if (!isLoad('ledger') || ++tries > 27) { clearInterval(t); openClient0(row); } }, 150);
      return;
    }
    openClient0(row);
  }
  function openClient0(row) {
    var e = row || {}, edit = !!row, deal0 = e.deal || 'percent';
    var led = L.v2AdsLedger(data('ledger'), now());
    var locked = edit && (e.results || []).some(function (r) { return r.sent_at || r.revenue_id; });
    var form = (locked ? '<p class="co-info" role="status">أُرسلت كشوف لهذا العميل أو حُصّلت مبالغ منه، فلا تتغير طريقة الحساب ولا النسبة ولا المبلغ ولا العملة. لتغييرها أنهِ هذا الاتفاق وأضف اتفاقًا جديدًا.</p>' : '')
      + fld('الاسم', inp('co_kn', e.name || '', 'maxlength="160"')) + fld('البريد (اختياري)', inp('co_ke', e.email || '', 'dir="ltr" maxlength="200"')) + fld('ماذا نقدّم لهم', inp('co_ko', e.offer || '', 'maxlength="300"'))
      + fld('طريقة الحساب', sel('co_kd', DEAL_OPTS, deal0))
      + '<div id="co_kdo_w" class="co-f"' + (deal0 === 'other' ? '' : ' hidden') + '><label>اكتب طريقة الحساب</label>' + inp('co_kdo', e.deal_other || '', 'maxlength="120"') + '</div>'
      + '<div class="co-f2"><div id="co_kp_w" class="co-f"><label>النسبة ٪</label>' + numInp('co_kp', e.percent || '') + '</div><div id="co_kf_w" class="co-f"><label>المبلغ الثابت</label>' + numInp('co_kf', e.fixed_amount || '') + '</div></div>'
      + '<div class="co-f2">' + fld('العملة', sel('co_kc', CURS_ALL, e.currency || 'EGP')) + fld('اسم العدد في الكشف', inp('co_kl', e.count_label || 'عملاء جاؤوا من الحملة', 'maxlength="60"')) + '</div>'
      + fld('كود التتبّع (يُستخدم عند تفعيل عدّ الزيارات)', inp('co_kr', e.ref_code || '', 'dir="ltr" maxlength="40"'), 'حروف إنجليزية صغيرة وأرقام وشرطة فقط')
      + (led ? '<div class="co-f2">' + fld('مرتبط برصيد إعلانات عمل على المنصة', sel('co_klk', [['', 'غير مرتبط'], ['course', 'دورة'], ['book', 'كتاب']], e.ledger_kind || '')) + '<div class="co-f" id="co_klw_w"><label>العمل</label><select id="co_klw"></select></div></div>'
        : '<p class="co-fine">أرصدة الإعلانات غير متاحة الآن، فلا يمكن ربط العميل بعمل.</p>')
      + (edit ? fld('الحالة', sel('co_kst', [['active', 'نشط'], ['ended', 'انتهى']], e.status || 'active')) : '') + fld('ملاحظة', area('co_kn2', e.note || '', 500));
    sheet({
      title: edit ? 'عدّل الاتفاق' : 'أضف عميلًا', form: form,
      wire: function (s) {
        var d = q('#co_kd', s);
        function sync() {
          var v = d.value; q('#co_kdo_w', s).hidden = v !== 'other'; q('#co_kp_w', s).hidden = !(v === 'percent' || v === 'fixed_plus_percent'); q('#co_kf_w', s).hidden = !(v === 'fixed' || v === 'fixed_plus_percent');
        }
        d.onchange = sync; sync();
        if (locked) ['co_kd', 'co_kp', 'co_kf', 'co_kc'].forEach(function (i) { var el = q('#' + i, s); if (el) el.disabled = true; });
        var lk = q('#co_klk', s), lw = q('#co_klw', s);
        if (lk && lw) {
          var fill = function () {
            var kind = lk.value, rows = (led || []).filter(function (x) { return x.kind === kind; });
            q('#co_klw_w', s).hidden = !kind;
            lw.innerHTML = rows.map(function (x) { return '<option value="' + esc(x.id) + '"' + (x.id === e.ledger_owner_id ? ' selected' : '') + '>' + esc(x.title) + '</option>'; }).join('');
          };
          lk.onchange = fill; fill();
        }
      },
      collect: function (s) {
        var name = val(s, 'co_kn'); if (!name) return { ok: false, error: 'اكتب اسم العميل' };
        var deal = val(s, 'co_kd'), pct = null, fx = null, dother = val(s, 'co_kdo');
        if (deal === 'other' && !dother) return { ok: false, error: 'اكتب طريقة الحساب' };
        if (deal === 'percent' || deal === 'fixed_plus_percent') { var p = readNum(s, 'co_kp', 'النسبة', { req: true, pos: true, max: 100 }); if (!p.ok) return p; pct = p.v; }
        if (deal === 'fixed' || deal === 'fixed_plus_percent') { var f = readNum(s, 'co_kf', 'المبلغ الثابت', { req: true, pos: true, max: 100000000 }); if (!f.ok) return f; fx = f.v; }
        var ref = val(s, 'co_kr'); if (ref && !/^[a-z0-9-]{3,40}$/.test(ref)) return { ok: false, error: 'كود التتبّع: حروف إنجليزية صغيرة وأرقام وشرطة فقط (٣ إلى ٤٠)' };
        var lk = q('#co_klk', s), kind = lk ? lk.value : '', own = kind ? val(s, 'co_klw') : '';
        if (kind && !own) return { ok: false, error: 'اختر العمل المرتبط' };
        var out = { name: name, email: val(s, 'co_ke') || null, offer: val(s, 'co_ko'), deal: deal, deal_other: deal === 'other' ? dother : null, percent: pct, fixed_amount: fx, currency: val(s, 'co_kc'),
                 count_label: val(s, 'co_kl') || 'عملاء جاؤوا من الحملة', ref_code: ref || null, status: edit ? val(s, 'co_kst') : 'active', note: val(s, 'co_kn2') };
        if (lk) { out.ledger_kind = kind || null; out.ledger_owner_id = own || null; }          // خانة الربط غير مرسومة = لا نلمس الربط الحالي
        return { ok: true, payload: out };
      },
      send: function (p) { return edit ? api('PUT', '/v2/company/ad-clients/' + e.id, p) : api('POST', '/v2/company/ad-clients', p); },
      onOk: function () { afterWrite(edit ? 'حُدّث الاتفاق.' : 'أُضيف العميل.', ['ads']); }, onLost: function () { load('ads', true); }
    });
  }
  // —— نتيجة شهر
  function openResult(c, row) {
    var e = row || {}, edit = !!row, mo = CO.monthOptions(now(), 'result');
    var form = '<p class="co-lead sm">' + esc(c.name) + ' — ' + esc(CO.dealText(c)) + '</p>'
      + (edit ? '<p class="co-kv"><span>الشهر</span><b>' + esc(CO.monthText(e.period)) + '</b></p>' : fld('الشهر', monthPick('co_rm', mo, mo.def)))
      + fld(c.count_label || 'العدد', numInp('co_rn', e.count == null ? '' : e.count))
      + (c.deal === 'fixed' ? '' : fld('دخلهم من الحملة', numInp('co_ri', e.income == null ? '' : e.income), c.deal === 'other' ? '' : 'مطلوب لحساب المستحق'))
      + (c.deal === 'other' ? fld('المستحق', numInp('co_rd2', e.due_manual == null ? '' : e.due_manual)) : '') + fld('ملاحظة', area('co_rnote', e.note || '', 300));
    sheet({
      title: edit ? 'تعديل نتيجة' : 'سجّل نتيجة شهر', form: form,
      collect: function (s) {
        var n = readNum(s, 'co_rn', c.count_label || 'العدد', { max: 1000000000 }); if (!n.ok) return n;
        if (n.v != null && n.v !== Math.floor(n.v)) return { ok: false, error: (c.count_label || 'العدد') + ' لازم يكون عددًا صحيحًا' };
        var inc = { ok: true, v: null }, dm = { ok: true, v: null };
        if (c.deal !== 'fixed') { inc = readNum(s, 'co_ri', 'دخلهم من الحملة', { max: 100000000 }); if (!inc.ok) return inc; }
        if (c.deal === 'other') { dm = readNum(s, 'co_rd2', 'المستحق', { max: 100000000 }); if (!dm.ok) return dm; }
        var p = { count: n.v, income: inc.v, due_manual: dm.v, note: val(s, 'co_rnote') };
        if (!edit) p.period = readMonth(s, 'co_rm');
        return { ok: true, payload: p };
      },
      send: function (p) { return edit ? api('PUT', '/v2/company/ad-results/' + e.id, p) : api('POST', '/v2/company/ad-clients/' + c.id + '/results', p); },
      onOk: function () { afterWrite(edit ? 'حُدّثت النتيجة.' : 'سُجّلت النتيجة.', ['ads']); }, onLost: function () { load('ads', true); }
    });
  }
  // —— هدف شهر
  var FC_FIELDS = [['revenue_egp', 'هدف الدخل بالجنيه'], ['cogs_egp', 'تكلفة التنفيذ'], ['marketing_egp', 'التسويق'], ['payroll_egp', 'الرواتب'], ['rent_egp', 'الإيجار'], ['other_sga_egp', 'مصروفات أخرى']];
  function openForecast(row, preset) {
    var e = row || {}, edit = !!row, mo = CO.monthOptions(now(), 'target');
    var form = (edit ? '<p class="co-kv"><span>الشهر</span><b>' + esc(CO.monthText(e.month)) + '</b></p>' : fld('الشهر', monthPick('co_fm', mo, preset || mo.def)))
      + '<div class="co-f2">' + FC_FIELDS.map(function (f, i) { return fld(f[1], numInp('co_f' + i, e[f[0]] || '')); }).join('') + '</div>'
      + '<div class="co-f2">' + fld('عدد الدورات المستهدف', numInp('co_fc', e.target_courses || '')) + fld('عدد الطلاب المستهدف', numInp('co_fs', e.target_students || '')) + '</div>' + fld('ملاحظة', area('co_fnote', e.notes || '', 500));
    sheet({
      title: edit ? 'تعديل هدف شهر' : 'أضف شهرًا', form: form,
      collect: function (s) {
        var p = {};
        for (var i = 0; i < FC_FIELDS.length; i++) { var r = readNum(s, 'co_f' + i, FC_FIELDS[i][1], { max: 100000000 }); if (!r.ok) return r; p[FC_FIELDS[i][0]] = r.v || 0; }
        var c = readNum(s, 'co_fc', 'عدد الدورات', { max: 1000000 }), st = readNum(s, 'co_fs', 'عدد الطلاب', { max: 100000000 });
        if (!c.ok) return c; if (!st.ok) return st;
        if ((c.v || 0) !== Math.floor(c.v || 0) || (st.v || 0) !== Math.floor(st.v || 0)) return { ok: false, error: 'عدد الدورات والطلاب لازم يكون عددًا صحيحًا' };
        p.target_courses = c.v || 0; p.target_students = st.v || 0; p.notes = val(s, 'co_fnote');
        if (!edit) p.month = readMonth(s, 'co_fm');
        return { ok: true, payload: p };
      },
      send: function (p) { return edit ? api('PUT', '/forecast/' + e.id, p) : api('POST', '/v2/company/forecast', p); },
      onOk: function () { load('forecast', true); load('dash', true); afterWrite(edit ? 'حُدّث هدف الشهر.' : 'أُضيف الشهر.', []); }, onLost: function () { load('forecast', true); }
    });
  }

  // —— الإعدادات: العملة · الفريق
  function openRate() {
    var E = ep(), set = E && E.data && E.data.settings, cur = set && set.exchange_rate != null ? Number(set.exchange_rate) : null;
    if (cur === null || !isFinite(cur)) return;
    sheet({
      title: 'سعر الدولار بالجنيه', form: fld('السعر الجديد', numInp('co_xr', cur)), btnReview: 'راجع', btnConfirm: 'أكّد التغيير',
      collect: function (s) { var r = readNum(s, 'co_xr', 'السعر', { req: true, pos: true, max: 10000 }); return r.ok ? { ok: true, payload: { v: r.v } } : r; },
      review: function (p) { return { lead: 'يغيّر هذا تحويل الدولار إلى الجنيه في التقارير.', changed: p.v !== cur, rows: [{ label: 'سعر الدولار بالجنيه', from: U.fmt(cur), to: U.fmt(p.v) }] }; },
      send: function (p) { return api('PUT', '/settings', { exchange_rate: p.v }); },
      onOk: function () { var E2 = ep(); if (E2) E2.reload('settings', null); setNote('تغيّر سعر الدولار.'); redraw(); }, onLost: function () { var E2 = ep(); if (E2) E2.reload('settings', null); }
    });
  }
  function openStaff(u) {
    var E = ep(), edit = !!u, e = u || {}, rl = e.dashboard_role || e.role || 'employee';
    sheet({
      title: edit ? 'تعديل حساب إداري' : 'أضف مديرًا أو موظفًا',
      form: fld('الاسم', inp('co_un', e.name || '', 'maxlength="120"')) + fld('البريد الإلكتروني', inp('co_ue', e.email || '', 'dir="ltr" type="email"' + (edit ? ' disabled' : '')))
        + fld('الدور', sel('co_ur', [['admin', 'مدير (تحكم كامل)'], ['employee', 'موظف متابعة']], rl === 'admin' ? 'admin' : 'employee'))
        + fld(edit ? 'كلمة مرور جديدة (اختياري)' : 'كلمة مرور مؤقتة', inp('co_up', '', 'dir="ltr" autocomplete="new-password"'), '٨ أحرف على الأقل'),
      collect: function (s) {
        var name = val(s, 'co_un'), email = val(s, 'co_ue').toLowerCase(), pass = (q('#co_up', s).value || ''), role = val(s, 'co_ur');
        if (edit) {
          if (pass && pass.length < 8) return { ok: false, error: 'كلمة المرور ٨ أحرف على الأقل' };
          var b = { name: name, role: role, dashboard_role: role }; if (pass) b.password = pass;
          return { ok: true, payload: { body: b } };
        }
        if (!name) return { ok: false, error: 'اكتب الاسم' };
        if (!email || email.indexOf('@') < 0) return { ok: false, error: 'اكتب بريدًا إلكترونيًا صحيحًا' };
        if (pass.length < 8) return { ok: false, error: 'كلمة المرور المؤقتة ٨ أحرف على الأقل' };
        return { ok: true, payload: { body: { name: name, email: email, password: pass, dashboard_role: role } } };
      },
      send: function (p) { return edit ? api('PUT', '/users/' + e.id, p.body) : api('POST', '/users', p.body); },
      onOk: function () { var E2 = ep(); if (E2) E2.reload('dashUsers', null); setNote(edit ? 'حُدّث الحساب.' : 'أُضيف الحساب.'); redraw(); }, onLost: function () { var E2 = ep(); if (E2) E2.reload('dashUsers', null); }
    });
  }
  function toggleStaff(u) {
    var on = !u.is_active;
    confirmSheet({ title: on ? 'تفعيل حساب' : 'إيقاف حساب', lead: (on ? 'سيُفعَّل حساب «' : 'سيُوقَف حساب «') + (u.name || u.email) + '».', btn: on ? 'فعّل الحساب' : 'أوقف الحساب',
      send: function () { return api('PUT', '/users/' + u.id, { is_active: on }); },
      onOk: function () { var E2 = ep(); if (E2) E2.reload('dashUsers', null); setNote(on ? 'فُعّل الحساب.' : 'أُوقف الحساب.'); redraw(); } });
  }

  // ------------------------------------------------------------------ الأحداث
  function joinedRow(id) {
    var sum = data('summary'), parts = CO.joinPartners(listOf('partners'), sum && sum.partners);
    return parts ? byId(parts.rows, id) : null;
  }
  function runAct(act) {
    if (!act) return;
    if (act.do === 'contribution') { if (listOf('partners')) openContribution(); else jumpTo('partners'); return; }
    if (act.do === 'statements') { if (items('ads')) openAllStatements(); else jumpTo('ads'); return; }
    if (act.do === 'paid' && items('subs')) { openPaid(act.id); return; }
    S.hl = act.id ? (act.tab + ':' + act.id) : null;
    if (act.section && host().openSection) host().openSection(act.section, act.tab);
    else jumpTo(act.tab);
  }
  function wireView(v) {
    v.onclick = function (e) {
      var b = e.target.closest ? e.target.closest('[data-a]') : null;
      if (!b || !v.contains(b) || b.disabled) return;
      var a = b.getAttribute('data-a'), id = b.getAttribute('data-id'), E = ep();
      switch (a) {
        case 'retry': retryFailed(); break;
        case 'retrySet': if (E) ['settings', 'dashUsers', 'usage', 'aiModels'].forEach(function (k) { E.reload(k, null); }); break;
        case 'goto': jumpTo(b.getAttribute('data-t')); break;
        case 'brain': runAct((S.brainLines || [])[+b.getAttribute('data-i')] && S.brainLines[+b.getAttribute('data-i')].act); break;
        case 'addPartner': openPartner(null); break;
        case 'editPartner': { var r = joinedRow(id); if (r) openPartner(r); break; }
        case 'contribution': openContribution(id ? +id : null); break;
        case 'delContribution': delContribution(id); break;
        case 'filt': S.filt = b.getAttribute('data-v'); redraw(); break;
        case 'investorWd':
          try { go('finance'); finTab = 'investorwd'; viewFinance(document.getElementById('view')); } catch (x) { if (host().openSection) host().openSection('money', 'all'); }
          break;
        case 'delOpp': delOpp(id); break;
        case 'addAssetChoice': openAssetChoice(); break;
        case 'addAsset': openEquipment(null); break;
        case 'editAsset': openEquipment(byId(listOf('assets'), id)); break;
        case 'addSub': openSubscription(null); break;
        case 'paySub': openPaid(id); break;
        case 'resumeSub': { var sb = byId(items('subs'), id); if (sb) toggleSub(sb, 'active'); break; }
        case 'more': {
          var k = b.getAttribute('data-k');
          if (k === 'sub') { var s1 = byId(items('subs'), id); if (s1) subMore(s1); }
          else { var d1 = byId(items('deals'), id); if (d1) dealMore(d1); }
          break;
        }
        case 'importSubs': openImportSubs(); break;
        case 'addDeal': openAgreement(null); break;
        case 'editDeal': { var d2 = byId(items('deals'), id); if (d2) openAgreement(d2); break; }
        case 'renewDeal': { var d3 = byId(items('deals'), id); if (d3) openRenew(d3); break; }
        case 'receiveDeal': { var d4 = byId(items('deals'), id); if (d4) openReceive('agreement', d4); break; }
        case 'addClient': openClient(null); break;
        case 'editClient': openClient(byId(items('ads'), b.getAttribute('data-c'))); break;
        case 'addResult': { var c1 = byId(items('ads'), b.getAttribute('data-c')); if (c1) openResult(c1, null); break; }
        case 'statement': openStatement(b.getAttribute('data-c'), id); break;
        case 'statements': openAllStatements(); break;
        case 'oldAds': { var cc = b.getAttribute('data-c'); S.oldAds[cc] = !S.oldAds[cc]; redraw(); break; }
        case 'oldTargets': S.oldTargets = !S.oldTargets; redraw(); break;
        case 'addForecast': openForecast(null); break;
        case 'forecastNow': openForecast(null, CO.nowKey(now())); break;
        case 'editForecast': { var f = byId(listOf('forecast'), id); if (f) openForecast(f); break; }
        case 'saveCompany': {
          var body = { company_name: val(v, 'co_name'), fiscal_year_start: val(v, 'co_fy'), monthly_report_day: val(v, 'co_rd') };
          b.disabled = true; b.textContent = 'جارٍ الحفظ…';
          api('PUT', '/settings', body).then(function () { if (E) E.reload('settings', null); setNote('حُفظت بيانات الشركة.'); redraw(); })
            .catch(function (x) { setNote(errMsg(x)); redraw(); });
          break;
        }
        case 'rate': openRate(); break;
        case 'addStaff': openStaff(null); break;
        case 'editStaff': { var u = byId(E && E.data.dashUsers, id); if (u) openStaff(u); break; }
        case 'toggleStaff': { var u2 = byId(E && E.data.dashUsers, id); if (u2) toggleStaff(u2); break; }
        case 'savePerms': {
          var mods = qa('.co-pm:checked', v).map(function (c) { return c.value; }), map = rolePerms(E && E.data.settings);
          map.employee = { modules: mods };
          api('PUT', '/settings', { role_permissions: JSON.stringify(map) }).then(function () {
            if (E) E.reload('settings', null); setNote('حُفظت الصلاحيات.'); redraw();
            try { if (typeof renderNav === 'function') renderNav(); } catch (x) {}
          }).catch(function (x) { setNote(errMsg(x)); redraw(); });
          break;
        }
        case 'auditOpen': S.auditOpen = true; S.auditN = 20; if (E) E.reload('audit', null); redraw(); break;
        case 'auditClose': S.auditOpen = false; redraw(); break;
        case 'auditMore': S.auditN = 120; redraw(); break;
      }
    };
  }

  // ------------------------------------------------------------------ نقطة الدخول
  var NEEDS = {
    investment: { src: ['summary', 'partners', 'assets', 'subs', 'deals', 'ads', 'forecast', 'dash'], ep: ['users'], visits: true },
    v2c_partners: { src: ['summary', 'partners', 'contribs', 'cash', 'invest', 'opps', 'wd'], ep: ['users'] },
    v2c_assets: { src: ['assets', 'subs', 'summary'], ep: [] },
    v2c_deals: { src: ['deals'], ep: [], visits: true },
    v2c_ads: { src: ['ads'], ep: [], visits: true },
    settings: { src: [], ep: ['settings', 'dashUsers', 'usage', 'aiModels'] },
    targets: { src: [], ep: [] }
  };
  function ensureFor(mod) {
    var n = NEEDS[mod]; if (!n) return;
    epEnsure(n.ep); loadMany(n.src, false);
    if (n.visits) loadVisits(false);
  }
  var DRAW = { investment: drawBoard, v2c_partners: drawPartners, v2c_assets: drawAssets, v2c_deals: drawDeals, v2c_ads: drawAds, settings: drawSettings };
  function curMod() { return host().current ? host().current() : ''; }
  function goTargets() {
    // الأهداف: لا شاشة لها. الرابط القديم #foundation ⇒ «المعدات والاشتراكات»، وغيره ⇒ «نظرة» عند «الأهداف الشهرية».
    var legacy = ''; try { legacy = typeof tgTab !== 'undefined' ? tgTab : ''; } catch (e) {}
    if (S.redirected) return;
    S.redirected = '1';
    setTimeout(function () { S.redirected = ''; }, 800);
    if (legacy === 'foundation') { if (host().openSection) host().openSection('company', 'assets', { replace: true }); return; }
    S.jump = 'targets';
    if (host().openSection) host().openSection('company', 'invest', { replace: true });
  }
  function redraw() {
    if (!S.view || !host().current) return;
    var mod = curMod();
    if (!SECS.company.owns(mod)) return;
    S.mod = mod;
    if (document.getElementById('epModal')) return;                       // لا نعيد رسم الشاشة وتحت نافذة مفتوحة
    if (!document.body.contains(S.view)) return;
    if (mod === 'targets') { goTargets(); return; }
    S.dirty = false;
    DRAW[mod](S.view);
    wireView(S.view);
    S.sig = signature();
  }
  // الرسم من المؤقّتات يتأجل لو المستخدم يكتب أو عنده تعديل لم يُحفظ (حتى لا يضيع ما كتبه)
  function userEditing() {
    var a = document.activeElement;
    if (a && S.view && S.view.contains(a) && /^(INPUT|SELECT|TEXTAREA)$/.test(a.tagName)) return true;
    return !!S.dirty;
  }
  function watchDirty(view) {
    if (!view || view.__coDirty) return;
    view.__coDirty = 1;
    var f = function (e) { var t = e.target; if (t && /^(INPUT|SELECT|TEXTAREA)$/.test(t.tagName) && document.body.contains(t)) S.dirty = true; };
    view.addEventListener('input', f); view.addEventListener('change', f);
  }
  SECS.company = {
    owns: function (mod) { return !!(window.V2_ON && window.V2SHELL && V2SHELL.on && MODS[mod]); },
    render: function (mod, view) {
      S.view = view; S.mod = mod; watchDirty(view);
      if (mod !== 'targets') ensureFor(mod);
      redraw();
      if (!S.poll) {
        S.poll = setInterval(function () {
          if (!SECS.company.owns(curMod())) { S.mod = ''; return; }
          if (document.getElementById('epModal') || userEditing()) return;
          if (signature() !== S.sig) redraw();
        }, 400);
      }
      if (!S.minute) S.minute = setInterval(function () { var m = curMod(); if (SECS.company.owns(m) && m !== 'settings' && !document.getElementById('epModal') && !userEditing()) redraw(); }, 60000);
    },
    _state: S, _src: SRC, _visits: V, _tick: function (t) { S.nowOverride = t || 0; redraw(); }
  };
})();
