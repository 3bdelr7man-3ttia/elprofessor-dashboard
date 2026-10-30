/* ============================================================================
 * v2s/marketing.js — «التسويق» (الجولة النهائية): الحملات من الإعلان حتى الدفع · السوشيال ميديا · خطة النشر.
 * ⛔ لا منطق عمل هنا: الأرقام والاقتراحات والصفوف والتحقق كلها من `V2L.mk` (نقي، في v2-logic.js). هذا الملف يجلب ويرسم ويفتح الأوراق.
 * ⛔ المفتاح مقفول افتراضيًا: الملف يتحمّل دايمًا لكنه ما يرسم شيئًا إلا لو index.html نادى `V2SEC_RENDER` (والغلاف الجديد شغّال).
 * ⛔ ولا طلب شبكة من هنا غير: `/campaigns` (الموجود) · مسارات `/v2/*` (بروكسيات أدمن بس). كل مصدر يفشل لوحده: رقمه «غير متاح بعد» لا صفر.
 * ⛔ تعديل الحملة أو إيقافها سجلّ هنا فقط: لا يوقف الإعلان نفسه ولا يحرّك فلوسًا (والتأكيد ورقة صريحة).
 * ========================================================================== */
(function () {
  'use strict';
  window.V2SEC = window.V2SEC || {};
  window.V2SEC_OWNS = window.V2SEC_OWNS || function (m) { for (var k in window.V2SEC) if (window.V2SEC[k] && window.V2SEC[k].owns(m)) return true; return false; };
  window.V2SEC_RENDER = window.V2SEC_RENDER || function (m, v) { for (var k in window.V2SEC) if (window.V2SEC[k] && window.V2SEC[k].owns(m)) return window.V2SEC[k].render(m, v); };

  var L = window.V2L;
  if (!L || !L.mk) return;
  var U = L.util, Un = U.U, MK = L.mk, T = MK.STR;
  var MODS = { marketing: 'campaigns', v2mk_social: 'social', v2mk_plan: 'plan' };
  var S = { view: null, mod: '', sig: '', poll: null, minute: null, filter: 'active', note: null, noteT: null, skipped: [], legacyLater: false, busy: false, sheetBusy: false };
  var SRC = {};

  function esc(s) { return String(s == null ? '' : s).replace(/[&<>"']/g, function (c) { return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]; }); }
  function host() { return window.V2_HOST || {}; }
  function ep() { return window.EP || null; }
  function img(n) { return 'v2/img/' + n + '.jpg'; }
  function now() { return S.nowOverride || Date.now(); }
  function q(sel, root) { return (root || document).querySelector(sel); }
  function qa(sel, root) { return Array.prototype.slice.call((root || document).querySelectorAll(sel)); }
  function pad(n) { return (n < 10 ? '0' : '') + n; }
  function todayISO(t) { var d = new Date(t); return d.getFullYear() + '-' + pad(d.getMonth() + 1) + '-' + pad(d.getDate()); }
  function money(n, c) { return U.moneyText(n, c); }
  function store(kind, key, val) {
    try {
      var st = kind === 's' ? window.sessionStorage : window.localStorage;
      if (val === undefined) return st.getItem(key);
      st.setItem(key, val);
    } catch (e) { return null; }
    return null;
  }

  // ------------------------------------------------------------------ مصادر (كلٌّ تفشل لوحدها)
  var PATHS = {
    campaigns: function () { return '/campaigns'; },
    owners: function () { return '/v2/marketing/owners'; },
    income: function () { return '/v2/income/by-service?month=' + L.v2Period('month', now()).month; },
    ads: function () { return '/v2/ads-ledger'; },
    attribution: function () { return '/v2/marketing/attribution?month=' + L.v2Period('month', now()).month; },
    published: function () { return '/v2/marketing/published?days=7'; }
  };
  var NEEDS = { campaigns: ['campaigns', 'owners', 'income', 'ads', 'attribution'], social: ['campaigns'], plan: ['published'] };
  function srcOf(k) { return SRC[k] || (SRC[k] = { state: 'idle', data: null, status: 0, seq: 0 }); }
  function load(k, force) {
    var s = srcOf(k), E = ep();
    if (!E || !E.api || !E.authed || !PATHS[k]) return;
    if (s.state === 'loading') return;
    if (!force && s.state !== 'idle') return;
    s.state = 'loading';
    var seq = ++s.seq;
    E.api(PATHS[k]()).then(function (d) {
      if (seq !== s.seq) return;
      s.state = 'ready'; s.data = d; s.at = Date.now(); changed();
    }).catch(function (e) {
      if (seq !== s.seq) return;
      if (e && e.status === 401) return;
      s.state = e && e.status === 404 ? 'closed' : 'error'; s.status = (e && e.status) || 0; s.data = null; changed();
    });
  }
  function state(k) { return srcOf(k).state; }
  function data(k) { var s = srcOf(k); return s.state === 'ready' ? s.data : null; }
  function signature() {
    return Object.keys(PATHS).map(function (k) { return srcOf(k).state + srcOf(k).seq; }).join(',') + '|' + S.filter + '|' + S.skipped.length + '|' + (S.legacyLater ? 1 : 0) + '|' + (S.note || '');
  }
  var redrawT = null;
  function changed() {
    try { if (window.V2SHELL && V2SHELL.on && V2SHELL.refresh) V2SHELL.refresh(); } catch (e) {}
    if (redrawT) return;
    redrawT = setTimeout(function () { redrawT = null; if (!document.getElementById('epModal') || !S.sheetBusy) redraw(); }, 0);
  }
  // ما يدخل الرسم: لقطة من المصادر والحالة (نقية لتُختبر في node)
  function model() {
    var m = { now: now(), filter: S.filter, skipped: S.skipped.slice(), legacyLater: S.legacyLater, note: S.note, src: {} };
    Object.keys(PATHS).forEach(function (k) { var s = srcOf(k); m.src[k] = { state: s.state, data: s.state === 'ready' ? s.data : null }; });
    return m;
  }

  // ------------------------------------------------------------------ أجزاء مشتركة
  function noteStrip(m) { return m.note ? '<div class="v3-ok" role="status">' + esc(m.note) + '</div>' : ''; }
  function retryBtn() { return '<button type="button" class="v3-btn2" data-a="retry">' + esc(T.retry) + '</button>'; }
  function isReady(m, k) { return m.src[k].state === 'ready'; }
  function isFailed(m, k) { return m.src[k].state === 'error' || m.src[k].state === 'closed'; }
  function isLoading(m, k) { return m.src[k].state === 'idle' || m.src[k].state === 'loading'; }
  function section(title, hint, body, extra) {
    return '<section class="v3-card' + (extra ? ' ' + extra : '') + '"><header class="v3-ch"><h2>' + esc(title) + '</h2>' + (hint ? '<p>' + esc(hint) + '</p>' : '') + '</header>' + body + '</section>';
  }
  function campaignRows(m) { return isReady(m, 'campaigns') && Array.isArray(m.src.campaigns.data) ? MK.norm(m.src.campaigns.data) : null; }
  function ownersItems(m) { return isReady(m, 'owners') && m.src.owners.data && Array.isArray(m.src.owners.data.items) ? m.src.owners.data.items : null; }
  function incomeTotals(m) {
    if (!isReady(m, 'income')) return null;
    var d = m.src.income.data, items = [];
    ((d && d.services) || []).forEach(function (s) { (s.totals || []).forEach(function (t) { items.push({ currency: t.currency, amount: t.amount }); }); });
    return U.sumByCurrency(items);
  }
  function attData(m) { return isReady(m, 'attribution') && MK.attReady(m.src.attribution.data) ? m.src.attribution.data : null; }
  function adsItems(m) { return isReady(m, 'ads') && m.src.ads.data && Array.isArray(m.src.ads.data.items) ? m.src.ads.data.items : null; }

  // ------------------------------------------------------------------ تبويب الحملات
  function numbersHtml(board) {
    return '<div class="v3-nums">' + board.numbers.map(function (n) {
      return '<article class="v3-num k-' + n.key + (n.na ? ' na' : '') + '"><h3>' + esc(n.label) + '</h3><p class="v3-big' + (n.na ? ' na' : '') + '">' + esc(n.value) + '</p>'
        + (n.othersText ? '<p class="v3-oth">' + esc(n.othersText) + '</p>' : '') + '<p class="v3-note">' + esc(n.note) + '</p></article>';
    }).join('') + '</div>';
  }
  function brainHtml(b, total) {
    if (b.state === 'items') {
      var it = b.items[0], idx = total - b.items.length + 1;
      return '<section class="mk-brainstrip" aria-label="' + esc(T.brainLabel) + '"><img class="mk-bav" src="' + img('brain-avatar') + '" alt="">'
        + '<div class="mk-bt"><small>' + esc(T.brainLabel) + (total > 1 ? ' · اقتراح ' + U.ar(idx) + ' من ' + U.ar(total) : '') + '</small><p class="mk-bs">' + esc(it.text) + '</p>'
        + (it.line ? '<p class="mk-bl">' + esc(it.line) + '</p>' : '') + '</div>'
        + '<div class="mk-bb"><button type="button" class="v3-btn1" data-a="brain" data-kind="' + esc(it.kind) + '" data-id="' + esc(it.id) + '">' + esc(it.btn) + '</button>'
        + (it.later ? '<button type="button" class="mk-later" data-a="later" data-kind="' + esc(it.kind) + '" data-id="' + esc(it.id) + '">' + esc(T.later) + '</button>' : '') + '</div></section>';
    }
    if (b.state === 'empty') {
      return '<section class="mk-brainstrip" aria-label="' + esc(T.brainLabel) + '"><img class="mk-bav" src="' + img('brain-avatar') + '" alt="">'
        + '<div class="mk-bt"><small>' + esc(T.brainLabel) + '</small><p class="mk-bs">' + esc(b.items[0].text) + '</p></div>'
        + '<div class="mk-bb"><button type="button" class="v3-btn1" data-a="new">' + esc(b.items[0].btn) + '</button></div></section>';
    }
    return '<section class="mk-brainstrip" aria-label="' + esc(T.brainLabel) + '"><img class="mk-bav" src="' + img('brain-avatar') + '" alt="">'
      + '<div class="mk-bt"><small>' + esc(T.brainLabel) + '</small><p class="mk-bs">' + esc(b.text) + '</p></div></section>';
  }
  function statusChip(r) { return '<span class="mk-chip st-' + esc(r.status) + '">' + esc(r.statusLabel) + '</span>'; }
  function ratioCell(r) { return r.noResults ? '—' : '<span class="mk-r ' + r.ratioTone + '">' + esc(r.ratioText) + '</span>'; }
  // الصف كله اختصار للفأرة فقط (بلا role)، والاسم زرّ حقيقي يفتح التفاصيل للوحة المفاتيح وقارئات الشاشة
  function rowAttrs(r) { return ' class="mk-row" data-a="rowopen" data-id="' + esc(r.id) + '"'; }
  function nameBtn(r) { return '<button type="button" class="mk-namebtn" data-a="open" data-id="' + esc(r.id) + '">' + esc(r.name) + '</button>'; }
  function moneyLines(t) {
    var parts = String(t || '').split(' · ').filter(Boolean);
    return parts.length > 1 ? '<span class="mk-ml">' + parts.map(function (x) { return '<span>' + esc(x) + '</span>'; }).join('') + '</span>' : esc(t);
  }
  function deskTable(vm) {
    var head = '<thead><tr><th style="width:' + (vm.viaColumn ? '18' : '31') + '%">' + esc(T.colCampaign) + '</th><th style="width:9%">' + esc(T.colPlatform) + '</th><th style="width:8%">' + esc(T.colStatus) + '</th>'
      + '<th style="width:11%">' + esc(T.colSpent) + '</th><th style="width:7%">' + esc(T.colVisits) + '</th>'
      + '<th style="width:8%" title="' + esc(T.typedTitle) + '">' + esc(T.colLeads) + '<small>' + esc(T.colAsTyped) + '</small></th>'
      + '<th style="width:8%" title="' + esc(T.typedTitle) + '">' + esc(T.colPaid) + '<small>' + esc(T.colAsTyped) + '</small></th>'
      + '<th style="width:11%">' + esc(T.colRev) + '</th><th style="width:7%">' + esc(T.colRatio) + '</th>'
      + (vm.viaColumn ? '<th class="mk-via-c" style="width:13%">' + esc(T.colVia) + '<small>' + esc(T.colViaSub) + '</small></th>' : '') + '</tr></thead>';
    var body = vm.rows.map(function (r) {
      return '<tr' + rowAttrs(r) + '><td><div class="mk-name"><b>' + nameBtn(r) + '</b>' + (r.owner ? '<span class="mk-sub">' + esc(r.owner) + '</span>' : '') + '</div></td>'
        + '<td>' + esc(r.platform) + '</td><td>' + statusChip(r) + '</td><td>' + esc(r.spentText) + '</td>'
        + (r.noResults ? '<td colspan="4"><span class="mk-chip nores">' + esc(T.noResultsChip) + '</span></td>'
          : '<td>' + esc(r.clicks) + '</td><td>' + esc(r.leads) + '</td><td>' + esc(r.conversions) + '</td><td>' + esc(r.revenueText) + '</td>')
        + '<td>' + ratioCell(r) + '</td>' + (vm.viaColumn ? '<td class="mk-via-c">' + esc(r.viaText) + '</td>' : '') + '</tr>';
    }).join('');
    var o = vm.organic;
    var org = '<tr class="mk-organic"><td><div class="mk-name"><b>' + esc(o.name) + '</b><span class="mk-sub">' + esc(o.sub) + '</span></div></td><td></td><td></td><td></td>'
      + (o.na ? '<td colspan="' + (vm.viaColumn ? 6 : 5) + '" class="mk-na">' + esc(o.naText) + '</td>'
        : '<td></td><td>' + esc(o.signups) + '</td><td>' + esc(o.paid) + '</td><td>' + moneyLines(o.revenueText) + '</td><td>' + esc(o.ratioText) + '</td>' + (vm.viaColumn ? '<td></td>' : '')) + '</tr>';
    return '<table class="mk-table mk-desk">' + head + '<tbody>' + body + org + '</tbody></table>';
  }
  function tabTable(vm) {
    var head = '<thead><tr><th style="width:34%">' + esc(T.colCampaign) + '</th><th style="width:14%">' + esc(T.colSpent) + '</th><th style="width:11%" title="' + esc(T.typedTitle) + '">' + esc(T.colLeads)
      + '<small>' + esc(T.colAsTyped) + '</small></th><th style="width:11%" title="' + esc(T.typedTitle) + '">' + esc(T.colPaid) + '<small>' + esc(T.colAsTyped) + '</small></th><th style="width:19%">' + esc(T.colRev)
      + '</th><th style="width:11%">' + esc(T.colRatio) + '</th></tr></thead>';
    var body = vm.rows.map(function (r) {
      var fold = '<span class="mk-sub">' + esc([r.platform, r.statusLabel].filter(Boolean).join(' · ')) + (r.owner ? ' · ' + esc(r.owner) : '') + '</span>';
      var via = r.via ? '<span class="mk-via">عبر الرابط هذا الشهر: ' + esc(r.viaText) + '</span>' : '';
      return '<tr' + rowAttrs(r) + '><td><div class="mk-name"><b>' + nameBtn(r) + '</b>' + fold + via + '</div></td><td>' + esc(r.spentText) + '</td>'
        + (r.noResults ? '<td colspan="3"><span class="mk-chip nores">' + esc(T.noResultsChip) + '</span></td>'
          : '<td>' + esc(r.leads) + '</td><td>' + esc(r.conversions) + '</td><td>' + esc(r.revenueText) + '</td>') + '<td>' + ratioCell(r) + '</td></tr>';
    }).join('');
    var o = vm.organic;
    var org = '<tr class="mk-organic"><td><div class="mk-name"><b>' + esc(o.name) + '</b><span class="mk-sub">' + esc(o.sub) + '</span></div></td>'
      + (o.na ? '<td colspan="5" class="mk-na">' + esc(o.naText) + '</td>'
        : '<td></td><td>' + esc(o.signups) + '</td><td>' + esc(o.paid) + '</td><td>' + moneyLines(o.revenueText) + '</td><td>' + esc(o.ratioText) + '</td>') + '</tr>';
    return '<table class="mk-table mk-tab">' + head + '<tbody>' + body + org + '</tbody></table>';
  }
  function cardList(vm) {
    var cards = vm.rows.map(function (r) {
      var grid = r.noResults
        ? '<div><span>' + esc(T.colSpent) + '</span><b>' + esc(r.spentText) + '</b></div><div class="mk-nores-row"><span class="mk-chip nores">' + esc(T.noResultsChip) + '</span></div>'
        : '<div><span>' + esc(T.colSpent) + '</span><b>' + esc(r.spentText) + '</b></div><div><span>' + esc(T.colVisits) + '</span><b>' + esc(r.clicks) + '</b></div><div><span>' + esc(T.colLeads) + '</span><b>' + esc(r.leads) + '</b></div>'
          + '<div><span>' + esc(T.colPaid) + '</span><b>' + esc(r.conversions) + '</b></div><div><span>' + esc(T.colRev) + '</span><b>' + esc(r.revenueText) + '</b></div><div><span>' + esc(T.colRatio) + '</span><b>' + ratioCell(r) + '</b></div>';
      return '<article class="mk-ccard" data-a="rowopen" data-id="' + esc(r.id) + '"><div class="mk-ch"><b>' + nameBtn(r) + '</b>' + statusChip(r) + '</div>'
        + '<p class="mk-sub">' + esc([r.owner, r.platform].filter(Boolean).join(' · ')) + '</p><div class="mk-mg">' + grid + '</div>'
        + (r.via ? '<p class="mk-viarow">عبر الرابط هذا الشهر: ' + esc(r.viaText) + '</p>' : '') + '</article>';
    }).join('');
    var o = vm.organic;
    cards += '<article class="mk-ccard mk-organic"><div class="mk-ch"><b>' + esc(o.name) + '</b></div><p class="mk-sub">' + esc(o.sub) + '</p>'
      + (o.na ? '<p class="mk-na">' + esc(o.naText) + '</p>' : '<div class="mk-mg"><div><span>' + esc(T.colLeads) + '</span><b>' + esc(o.signups) + '</b></div><div><span>' + esc(T.colPaid) + '</span><b>' + esc(o.paid) + '</b></div>'
        + '<div><span>' + esc(T.colRev) + '</span><b>' + moneyLines(o.revenueText) + '</b></div></div>') + '</article>';
    return '<div class="mk-cards">' + cards + '</div>';
  }
  function adsLineHtml(m) {
    var items = adsItems(m), text;
    if (items) {
      if (!items.length) text = T.adsNone;
      else {
        var all = [];
        items.forEach(function (it) { (it.balance || []).forEach(function (b) { all.push({ currency: b.currency, amount: b.amount }); }); });
        text = Un(items.length, ['عمل واحد له رصيد إعلانات عندنا', 'عملان لهما رصيد إعلانات عندنا', 'أعمال لها رصيد إعلانات عندنا', 'عملًا له رصيد إعلانات عندنا']) + ': ' + (MK.moneyListText(U.sumByCurrency(all)) || '—');
      }
    } else text = isLoading(m, 'ads') ? '…جارٍ جلب أرصدة الإعلانات' : T.adsFailed;
    return '<div class="mk-adsline"><p>' + esc(text) + '</p><button type="button" class="v3-link" data-a="goto" data-s="money" data-t="ads">' + esc(T.adsLinkAds)
      + '</button><button type="button" class="v3-link" data-a="goto" data-s="company" data-t="ads">' + esc(T.adsLinkClients) + '</button></div>';
  }
  function tailHtml(m) {
    var st = { campaigns: m.src.campaigns.state, income: m.src.income.state, ads: m.src.ads.state, attribution: m.src.attribution.state };
    var sv = MK.sources(st);
    var chips = sv.seen.map(function (s) { return '<li class="mk-src s-' + s.state + '"><i></i>' + esc(s.label) + '</li>'; }).join('');
    var needs = sv.needs.map(function (n) { return '<li class="mk-need"><span class="mk-nt">' + esc(n.title) + '</span><span class="mk-nw">' + esc(n.why) + '</span><span class="mk-nc">' + esc(n.chip) + '</span></li>'; }).join('');
    return '<footer class="mk-tail"><div class="mk-seen"><b>' + esc(T.seenTitle) + '</b><ul class="mk-srcs">' + chips + '</ul>'
      + (sv.failed.length ? '<button type="button" class="v3-link" data-a="retry">' + esc(T.retry) + '</button>' : '') + '</div>'
      + '<div class="mk-needs"><b>' + esc(T.needsTitle) + '</b><ul class="mk-needlist">' + needs + '</ul><button type="button" class="v3-link" data-a="how">' + esc(T.howLink) + '</button></div></footer>';
  }
  function tableCard(m, rows) {
    var body;
    if (rows === null) {
      body = isLoading(m, 'campaigns') ? '<div class="v3-empty"><b>' + esc(T.loadingCampaigns) + '</b></div>'
        : '<div class="v3-empty"><b>' + esc(T.unavailableCampaigns) + '</b><p>' + esc(T.unavailableHint) + '</p>' + retryBtn() + '</div>';
    } else {
      var vm = MK.rows(rows, ownersItems(m), m.filter, attData(m));
      if (!vm.rows.length) {
        body = (m.filter === 'active' && rows.length ? '<div class="v3-empty"><b>' + esc(T.emptyActive) + '</b><button type="button" class="v3-link" data-a="showall">' + esc(T.showAll) + '</button></div>'
          : '<div class="v3-empty"><b>' + esc(T.emptyAll) + '</b></div>');
        body += '<div class="mk-tw">' + deskTable(vm) + tabTable(vm) + cardList(vm) + '</div>';
      } else body = '<div class="mk-tw">' + deskTable(vm) + tabTable(vm) + cardList(vm) + '</div>';
    }
    return '<section class="v3-card mk-card"><header class="v3-ch"><h2>' + esc(T.cardTitle) + '</h2><p>' + esc(T.cardHint) + '</p></header>' + body + adsLineHtml(m) + tailHtml(m) + '</section>';
  }
  function legacyHtml(m, rows) {
    var items = ownersItems(m) !== null && rows ? MK.legacyUsd(rows, isReady(m, 'owners') ? m.src.owners.data.legacy_max_id : 0) : [];
    if (!items.length || m.legacyLater) return '';
    return '<div class="v3-warn mk-legacy" role="status"><span>' + esc(Un(items.length, ['حملة واحدة', 'حملتان', 'حملات', 'حملة']) + ' ' + T.legacyText) + '</span>'
      + '<button type="button" class="v3-btn2" data-a="legacy">' + esc(T.legacyBtn) + '</button></div>';
  }
  function campaignsHtml(m) {
    var rows = campaignRows(m), today = todayISO(m.now);
    var failedC = isFailed(m, 'campaigns');
    var b = rows ? MK.brain(rows, today, m.skipped) : null;
    var total = rows ? MK.brain(rows, today, []).items.length : 0;
    var mb = b ? MK.mainButton(b.state) : { main: 'top', topHidden: false };
    var seg = [['active', T.segActive], ['all', T.segAll]].map(function (p) {
      return '<button type="button" role="tab" class="v3-pb' + (m.filter === p[0] ? ' on' : '') + '" aria-selected="' + (m.filter === p[0]) + '" data-a="filter" data-f="' + p[0] + '">' + esc(p[1]) + '</button>';
    }).join('');
    var newBtn = '';
    if (!mb.topHidden) {
      var can = !!rows;
      newBtn = '<button type="button" class="mk-new ' + (mb.main === 'top' && can ? 'v3-btn1' : 'v3-btn2') + '" data-a="new"' + (can ? '' : ' disabled') + '>' + esc(T.newCampaign) + '</button>';
    }
    var warn = failedC ? '<div class="v3-warn" role="status">' + esc(T.failedCampaigns) + ' <button type="button" class="v3-btn2" data-a="retry">' + esc(T.retry) + '</button></div>' : '';
    var board = MK.board(rows, m.filter, { income: incomeTotals(m), attribution: attData(m) });
    return '<div class="v3 mk" data-board="campaigns">' + noteStrip(m) + warn
      + '<div class="v3-top"><div class="v3-seg" role="tablist" aria-label="' + esc(T.segLabel) + '">' + seg + '</div>' + newBtn + '</div>'
      + (failedC ? '<p class="mk-hint">' + esc(T.newBlocked) + '</p>' : '')
      + '<p class="v3-ptxt v3-lead">' + esc(T.topNote) + '</p>'
      + legacyHtml(m, rows) + numbersHtml(board) + (b ? brainHtml(b, total) : '') + tableCard(m, rows) + '</div>';
  }

  // ------------------------------------------------------------------ تبويب السوشيال
  function socialHtml(m) {
    var rows = campaignRows(m), failedC = isFailed(m, 'campaigns');
    var cards = '';
    if (rows || failedC || isLoading(m, 'campaigns')) {
      var by = rows ? MK.byPlatform(rows) : null;
      cards = '<div class="mk-social">' + MK.SOCIAL.map(function (p) {
        var o = by ? by[p.key] : null, big, caption, fact = '', oth = '', na;
        if (!o) { big = failedC ? T.na : T.loadingCampaigns; caption = failedC ? T.socialFailedNote : ''; na = true; }
        else { big = o.big; caption = o.caption; fact = o.fact; oth = o.othersText; na = o.na; }
        return '<article class="mk-sc" data-p="' + p.key + '"><div class="mk-sh"><span class="mk-mark" aria-hidden="true">' + esc(p.mark) + '</span><b>' + esc(p.label) + '</b></div>'
          + '<p class="mk-sbig' + (na ? ' na' : '') + '">' + esc(big) + '</p>' + (oth ? '<p class="v3-oth">' + esc(oth) + '</p>' : '')
          + (caption ? '<p class="mk-mute">' + esc(caption) + '</p>' : '') + (fact ? '<p class="mk-fact">' + esc(fact) + '</p>' : '')
          + (o && o.sharedText ? '<p class="mk-shared">' + esc(o.sharedText) + '</p>' : '') + '<p class="mk-mute">' + esc(T.socialFollowers) + '</p></article>';
      }).join('') + '</div>';
    }
    var warn = failedC ? '<div class="v3-warn" role="status">' + esc(T.failedCampaigns) + ' <button type="button" class="v3-btn2" data-a="retry">' + esc(T.retry) + '</button></div>' : '';
    var madar = '<section class="mk-madar"><img src="' + img('marketing') + '" alt=""><div class="mk-madar-b"><span class="mk-soon">' + esc(T.soon) + '</span><p>' + esc(T.madarCard) + '</p>'
      + '<button type="button" class="v3-btn2" data-a="madar">' + esc(T.madarBtn) + '</button></div></section>';
    return '<div class="v3 mk" data-board="social">' + noteStrip(m) + madar + warn + cards + '</div>';
  }

  // ------------------------------------------------------------------ تبويب خطة النشر
  function planHtml(m) {
    var pub = m.src.published, body;
    if (pub.state === 'ready' && pub.data && Array.isArray(pub.data.items)) {
      var d = pub.data;
      body = (d.items.length ? '<ul class="v3-list">' + d.items.map(function (a) {
        return '<li class="mk-pub"><div class="v3-pid"><b>' + esc(a.title || '') + '</b><time>' + esc(U.dateText(a.published_at) + ' · ' + U.agoText(a.published_at, m.now)) + '</time></div>'
          + '<a class="v3-btn2" href="https://elprofessor.net/article.html?id=' + encodeURIComponent(a.id) + '" target="_blank" rel="noopener">' + esc(T.planOpenSite) + '</a></li>';
      }).join('') + '</ul>' : '<p class="v3-none">' + esc(T.planNone) + '</p>')
        + (Number(d.drafts) > 0 ? '<div class="mk-drafts"><span>' + esc(T.planDrafts + U.ar(d.drafts)) + '</span><button type="button" class="v3-btn2" data-a="goto" data-s="content" data-t="">' + esc(T.planOpenContent) + '</button></div>' : '');
    } else if (isLoading(m, 'published')) body = '<div class="v3-empty"><b>' + esc(T.planLoading) + '</b></div>';
    else body = '<div class="v3-empty"><b>' + esc(T.planFailed) + '</b><p>' + esc(T.unavailableHint) + '</p>' + retryBtn() + '</div>';
    var plan = '<section class="v3-card"><header class="v3-ch"><h2>' + esc(T.planSocial) + '</h2></header><div class="mk-planbox"><span class="mk-soon">' + esc(T.soon) + '</span><p>' + esc(T.planSocialText)
      + '</p><button type="button" class="v3-link" data-a="madar">' + esc(T.madarBtn) + '</button></div></section>';
    return '<div class="v3 mk" data-board="plan">' + noteStrip(m) + '<div class="v3-two">' + section(T.planPublished, T.planPublishedHint, body) + plan + '</div></div>';
  }

  // ------------------------------------------------------------------ الأوراق
  function openSheet(title, html) {
    if (typeof window.openModal !== 'function') return null;
    var s = window.openModal(title, '<div class="v3m mkm">' + html + '</div>');
    var x = q('[data-x]', s);
    if (x) x.onclick = function () { if (!s.dataset.busy) window.closeModal(); };
    s.onclick = function (e) { if (e.target === s && !s.dataset.busy) window.closeModal(); };
    return s;
  }
  function errBox(s, msg) { var e = q('#mkerr', s); if (e) e.innerHTML = msg ? '<div class="v3-err">' + esc(msg) + '</div>' : ''; }
  function errMsg(e) {
    if (e && e.status === 401) return 'انتهت الجلسة — سجّل الدخول من جديد ثم جرّب';
    var d = (e && e.data) || {};
    if (typeof d.error === 'string' && d.error) return d.error.replace(/\d/g, function (c) { return '٠١٢٣٤٥٦٧٨٩'.charAt(+c); });
    return T.saveFailed;
  }
  function setNote(text) { S.note = text; clearTimeout(S.noteT); S.noteT = setTimeout(function () { S.note = null; redraw(); }, 12000); }
  function reloadAll() { load('campaigns', true); load('owners', true); }
  function rowById(id) { var rows = campaignRows(model()) || []; return rows.filter(function (r) { return String(r.id) === String(id); })[0] || null; }
  function ownerOf(id) { var it = ownersItems(model()); return (it || []).filter(function (o) { return String(o.campaign_id) === String(id); })[0] || null; }
  function lockBusy(s, on) { if (on) s.dataset.busy = '1'; else delete s.dataset.busy; S.sheetBusy = !!on; }

  // —— تأكيد: إيقاف · تسجيل منتهية · تشغيل  (سجلّ فقط، ولا فلوس)
  var CONFIRM = {
    paused: { title: T.confirmStopTitle, word: 'موقوفة', done: 'أُوقفت', warn: T.confirmNoAd },
    completed: { title: T.confirmEndTitle, word: 'منتهية', done: 'سُجّلت منتهية', warn: T.confirmNoAd },
    active: { title: T.confirmRunTitle, word: 'نشطة', done: 'شُغّلت', warn: T.confirmNoAdRun }
  };
  function openStatus(row, status) {
    var C = CONFIRM[status];
    var s = openSheet(C.title, '<p class="mc-lead">ستصبح حملة «' + esc(row.name) + '» ' + esc(C.word) + ' في سجلّ الحملات هنا.</p><div class="v3-warn">' + esc(C.warn) + '</div><div id="mkerr" role="alert"></div>'
      + '<div class="acts"><button type="button" class="btn btn-primary" id="mk_go">' + esc(T.confirm) + '</button><button type="button" class="btn btn-ghost" id="mk_x">' + esc(T.cancel) + '</button></div>');
    if (!s) return;
    q('#mk_x', s).onclick = function () { if (!s.dataset.busy) window.closeModal(); };
    var go = q('#mk_go', s);
    go.onclick = function () {
      if (go.dataset.busy) return;
      go.dataset.busy = '1'; lockBusy(s, true); go.disabled = true; go.textContent = T.saving; errBox(s, '');
      ep().api('/campaigns/' + encodeURIComponent(row.id), { method: 'PUT', body: { status: status } }).then(function () {
        lockBusy(s, false); window.closeModal(); setNote('تم: حملة «' + row.name + '» ' + C.done); reloadAll(); redraw();
      }).catch(function (e) {
        lockBusy(s, false); delete go.dataset.busy; go.disabled = false; go.textContent = T.confirm; errBox(s, errMsg(e));
      });
    };
  }

  // —— حذف
  function openDelete(row) {
    var s = openSheet(T.deleteTitle, '<p class="mc-lead">ستُحذف حملة «' + esc(row.name) + '» وأرقامها من السجل نهائيًا.</p><div class="v3-warn">' + esc(T.deleteWarn) + '</div><div id="mkerr" role="alert"></div>'
      + '<div class="acts"><button type="button" class="btn btn-warn" id="mk_go">' + esc(T.deleteBtn) + '</button><button type="button" class="btn btn-ghost" id="mk_x">' + esc(T.cancel) + '</button></div>');
    if (!s) return;
    q('#mk_x', s).onclick = function () { if (!s.dataset.busy) window.closeModal(); };
    var go = q('#mk_go', s);
    go.onclick = function () {
      if (go.dataset.busy) return;
      go.dataset.busy = '1'; lockBusy(s, true); go.disabled = true; go.textContent = T.saving; errBox(s, '');
      ep().api('/campaigns/' + encodeURIComponent(row.id), { method: 'DELETE' }).then(function () {
        lockBusy(s, false); window.closeModal(); setNote('حُذفت حملة «' + row.name + '»'); reloadAll(); redraw();
      }).catch(function (e) {
        lockBusy(s, false); delete go.dataset.busy; go.disabled = false; go.textContent = T.deleteBtn; errBox(s, errMsg(e));
      });
    };
  }

  // —— التفاصيل
  function copyText(text, done) {
    function fallback() {
      var ta = document.createElement('textarea'); ta.value = text; ta.setAttribute('readonly', ''); ta.style.position = 'fixed'; ta.style.opacity = '0'; document.body.appendChild(ta); ta.select();
      try { document.execCommand('copy'); } catch (e) {} ta.remove(); done();
    }
    try {
      if (navigator.clipboard && navigator.clipboard.writeText) navigator.clipboard.writeText(text).then(done, fallback); else fallback();
    } catch (e) { fallback(); }
  }
  function toast(t) { try { (window.toast || window.notify || function () {})(t); } catch (e) {} }
  function openDetail(id) {
    var row = rowById(id), m = model();
    if (!row) return;
    var owner = ownerOf(id), ownersOk = ownersItems(m) !== null, att = attData(m);
    var ownerText = !ownersOk ? T.na : (owner && owner.owner_kind !== 'platform' ? MK.ownerTitleOf(owner) : T.ownerSelf);
    var via = att ? MK.via(att, row.id) : null;
    var url = MK.link(row.id, row.platform);
    var lines = [[T.detailLines.platform, row.platformLabel || '—'], [T.detailLines.status, row.statusLabel], [T.detailLines.period, MK.duration(row)], [T.detailLines.owner, ownerText]];
    if (row.audience) lines.push([T.detailLines.audience, row.audience]);
    var r = MK.ratio(row.revenue, row.spent);
    var cells = [[T.nBudget, money(row.budget, row.currency)], [T.colSpent, money(row.spent, row.currency)], [T.colVisits, U.ar(row.clicks)], [T.colLeads, U.ar(row.leads)],
                 [T.colPaid, U.ar(row.conversions)], [T.colRev, money(row.revenue, row.currency)], [T.colRatio, row.noResults || r == null ? '—' : U.fmt(r)]];
    var viaBox = att ? '<div class="mk-viabox"><b>' + esc(T.viaLabel) + ':</b> ' + esc(via ? 'جاء عبره هذا الشهر: سجّلوا ' + U.ar(via.signups) + ' · دفعوا ' + U.ar(via.paid) + (via.totals.length ? ' · دخل ' + MK.moneyListText(via.totals) : '') : T.viaNobody) + '</div>'
      : '<p class="v3-fine">' + esc(T.linkSoon) + '</p>';
    var runWord = row.status === 'active' ? T.actStop : T.actRun;
    var s = openSheet('حملة: ' + row.name, '<dl class="mk-dl">' + lines.map(function (l) { return '<dt>' + esc(l[0]) + '</dt><dd>' + esc(l[1]) + '</dd>'; }).join('') + '</dl>'
      + '<h3 class="mk-h">' + esc(T.detailNumbers) + '</h3><div class="mk-grid">' + cells.map(function (c) { return '<div><span>' + esc(c[0]) + '</span><b>' + esc(c[1]) + '</b></div>'; }).join('') + '</div>'
      + '<h3 class="mk-h">' + esc(T.linkTitle) + '</h3><div class="mk-linkrow"><input type="text" readonly id="mk_url" value="' + esc(url) + '" aria-label="' + esc(T.linkTitle) + '"><button type="button" class="v3-btn2" id="mk_copy">' + esc(T.copyLink) + '</button></div>' + viaBox
      + '<div class="acts mk-acts4"><button type="button" class="btn btn-primary" id="mk_edit">' + esc(T.actEdit) + '</button><button type="button" class="btn" id="mk_run">' + esc(runWord) + '</button>'
      + '<button type="button" class="btn btn-ghost" id="mk_stm">' + esc(T.actCopyStatement) + '</button><button type="button" class="btn btn-warn" id="mk_del">' + esc(T.actDelete) + '</button></div>');
    if (!s) return;
    q('#mk_copy', s).onclick = function () { var f = q('#mk_url', s); copyText(url, function () { toast(T.copiedLink); }); try { f.select(); } catch (e) {} };
    q('#mk_edit', s).onclick = function () { window.closeModal(); openForm(row); };
    q('#mk_run', s).onclick = function () { window.closeModal(); openStatus(row, row.status === 'active' ? 'paused' : 'active'); };
    q('#mk_stm', s).onclick = function () { copyText(MK.statement(row, owner, todayISO(now())), function () { toast(T.statementCopied); }); };
    q('#mk_del', s).onclick = function () { window.closeModal(); openDelete(row); };
  }

  // —— الإضافة والتعديل
  function numField(id, label, val) { return '<div class="fld"><label for="' + id + '">' + esc(label) + '</label><input id="' + id + '" type="text" inputmode="decimal" autocomplete="off" dir="ltr" value="' + esc(val) + '"></div>'; }
  function selectField(id, label, opts, sel) {
    return '<div class="fld"><label for="' + id + '">' + esc(label) + '</label><select id="' + id + '">' + opts.map(function (o) {
      return '<option value="' + esc(o[0]) + '"' + (o[0] === sel ? ' selected' : '') + '>' + esc(o[1]) + '</option>'; }).join('') + '</select></div>';
  }
  function openForm(row) {
    var m = model(), edit = !!row, loaded = row ? ownerOf(row.id) : null, ownersOk = ownersItems(m) !== null;
    var oc = MK.ownerChoices(m.src.ads.state, adsItems(m), loaded, edit ? ownersOk : true);
    var plat = row ? row.platform : 'facebook_instagram', platOk = MK.PLATFORM_OPTS.some(function (o) { return o[0] === plat; });
    var platSel = platOk ? plat : 'other', platOther = platOk ? '' : plat;
    var cur = row ? row.currency : 'EGP', curOk = ['EGP', 'SAR', 'USD'].indexOf(cur) > -1, curSel = curOk ? cur : 'other', curOther = curOk ? '' : cur;
    var f = row || { name: '', status: 'active', start: '', end: '', budget: '', spent: '', clicks: '', leads: '', conversions: '', revenue: '', audience: '' };
    var v = function (x) { return row ? String(x) : ''; };
    var ownerSelect = '<div class="fld"><label for="mk_owner">' + esc(T.fOwner) + '</label><select id="mk_owner"' + (oc.disabled ? ' disabled' : '') + '>' + oc.options.map(function (o) {
      return '<option value="' + esc(o.value) + '" data-title="' + esc(o.title) + '"' + (o.value === oc.selected ? ' selected' : '') + '>' + esc(o.label) + '</option>'; }).join('') + '</select></div>'
      + (oc.hint ? '<p class="mk-hintline">' + esc(oc.hint) + '</p>' : '');
    var html = '<div class="fld"><label for="mk_name">' + esc(T.fName) + '</label><input id="mk_name" type="text" maxlength="255" value="' + esc(f.name) + '"></div>' + ownerSelect
      + '<div class="mk-f2"><div class="mk-fc">' + selectField('mk_plat', T.fPlatform, MK.PLATFORM_OPTS, platSel)
      + '<div class="fld" id="mk_plat_o"' + (platSel === 'other' ? '' : ' hidden') + '><label for="mk_plat_t">' + esc(T.fPlatformOther) + '</label><input id="mk_plat_t" type="text" maxlength="50" value="' + esc(platOther) + '"></div></div>'
      + '<div class="mk-fc">' + selectField('mk_cur', T.fCurrency, MK.CURRENCY_OPTS, curSel) + '<div class="fld" id="mk_cur_o"' + (curSel === 'other' ? '' : ' hidden') + '><label for="mk_cur_t">' + esc(T.fCurrencyOther) + '</label><input id="mk_cur_t" type="text" maxlength="3" dir="ltr" value="' + esc(curOther) + '"></div></div></div>'
      + '<div class="mk-f2">' + selectField('mk_st', T.fStatus, [['active', 'نشطة'], ['paused', 'موقوفة'], ['completed', 'انتهت'], ['draft', 'مسودة']], f.status)
      + '<div class="fld"><label for="mk_aud">' + esc(T.fAudience) + '</label><input id="mk_aud" type="text" maxlength="500" value="' + esc(f.audience || '') + '"></div></div>'
      + '<div class="mk-f2"><div class="fld"><label for="mk_d1">' + esc(T.fStart) + '</label><input id="mk_d1" type="date" value="' + esc(f.start || '') + '"></div>'
      + '<div class="fld"><label for="mk_d2">' + esc(T.fEnd) + '</label><input id="mk_d2" type="date" value="' + esc(f.end || '') + '"></div></div>'
      + (edit ? '<p class="mk-hintline">' + esc(T.dateNote) + '</p>' : '')
      + '<div class="mk-f2">' + numField('mk_bud', T.fBudget, v(f.budget)) + numField('mk_sp', T.fSpent, v(f.spent)) + numField('mk_clk', T.fClicks, v(f.clicks)) + numField('mk_ld', T.fLeads, v(f.leads))
      + numField('mk_cv', T.fPaid, v(f.conversions)) + numField('mk_rev', T.fRevenue, v(f.revenue)) + '</div>'
      + '<div id="mkerr" role="alert"></div><div class="acts"><button type="button" class="btn btn-primary" id="mk_save">' + esc(edit ? T.saveBtn : T.createBtn) + '</button><button type="button" class="btn btn-ghost" id="mk_x">' + esc(T.cancel) + '</button></div>';
    var s = openSheet(edit ? T.editTitle + row.name : T.createTitle, html);
    if (!s) return;
    function toggle() {
      q('#mk_plat_o', s).hidden = q('#mk_plat', s).value !== 'other';
      q('#mk_cur_o', s).hidden = q('#mk_cur', s).value !== 'other';
    }
    q('#mk_plat', s).onchange = toggle; q('#mk_cur', s).onchange = toggle;
    q('#mk_x', s).onclick = function () { if (!s.dataset.busy) window.closeModal(); };
    var save = q('#mk_save', s);
    save.onclick = function () {
      if (save.dataset.busy) return;
      var ownerEl = q('#mk_owner', s), opt = ownerEl.options[ownerEl.selectedIndex];
      var res = MK.validate({
        name: q('#mk_name', s).value, ownerValue: ownerEl.value, ownerDisabled: ownerEl.disabled, ownerTitle: opt ? opt.getAttribute('data-title') : '',
        platform: q('#mk_plat', s).value, platformOther: q('#mk_plat_t', s).value, currency: q('#mk_cur', s).value, currencyOther: q('#mk_cur_t', s).value,
        status: q('#mk_st', s).value, start: q('#mk_d1', s).value, end: q('#mk_d2', s).value, budget: q('#mk_bud', s).value, spent: q('#mk_sp', s).value,
        clicks: q('#mk_clk', s).value, leads: q('#mk_ld', s).value, conversions: q('#mk_cv', s).value, revenue: q('#mk_rev', s).value, audience: q('#mk_aud', s).value, edit: edit
      }, loaded);
      if (!res.ok) { errBox(s, res.error); return; }
      save.dataset.busy = '1'; lockBusy(s, true); save.disabled = true; save.textContent = T.saving; errBox(s, '');
      var E = ep();
      var call = edit ? E.api('/campaigns/' + encodeURIComponent(row.id), { method: 'PUT', body: res.body }) : E.api('/campaigns', { method: 'POST', body: res.body });
      call.then(function (out) {
        var cid = edit ? row.id : (out && out.id);
        if (res.ownerChanged && cid) {
          return E.api('/v2/marketing/campaigns/' + encodeURIComponent(cid) + '/owner', { method: 'PUT', body: res.owner }).then(function () { return { ownerOk: true }; }, function () { return { ownerOk: false }; });
        }
        return { ownerOk: true };
      }).then(function (st) {
        lockBusy(s, false);
        reloadAll();
        if (st.ownerOk) { window.closeModal(); setNote('حُفظت حملة «' + res.body.name + '»'); redraw(); }
        else { delete save.dataset.busy; save.disabled = false; save.textContent = T.saveBtn; errBox(s, T.ownerNoSave); }
      }).catch(function (e) {
        lockBusy(s, false); delete save.dataset.busy; save.disabled = false; save.textContent = edit ? T.saveBtn : T.createBtn; errBox(s, errMsg(e));
      });
    };
    setTimeout(function () { try { q('#mk_name', s).focus(); } catch (e) {} }, 30);
  }

  // —— عملة الحملات القديمة
  function openLegacy() {
    var m = model(), rows = campaignRows(m), items = rows ? MK.legacyUsd(rows, isReady(m, 'owners') ? m.src.owners.data.legacy_max_id : 0) : [];
    if (!items.length) return;
    var s = openSheet(T.legacyTitle, '<p class="mc-lead">' + esc(T.legacyLead) + '</p><ul class="mk-leg">' + items.map(function (r) {
      return '<li><b>' + esc(r.name) + '</b><span>صُرف ' + esc(U.fmt(r.spent)) + ' · الميزانية ' + esc(U.fmt(r.budget)) + '</span></li>'; }).join('') + '</ul><div id="mkerr" role="alert"></div>'
      + '<div class="acts"><button type="button" class="btn btn-primary" id="mk_all">' + esc(T.legacyAllEgp) + '</button><button type="button" class="btn" id="mk_keep">' + esc(T.legacyKeep) + '</button>'
      + '<button type="button" class="btn btn-ghost" id="mk_later">' + esc(T.legacyLater) + '</button></div>');
    if (!s) return;
    var E = ep();
    function busy(on) { lockBusy(s, on); qa('.acts .btn', s).forEach(function (b) { b.disabled = on; }); }
    q('#mk_later', s).onclick = function () { if (s.dataset.busy) return; S.legacyLater = true; store('s', 'mk_legacy_later', '1'); window.closeModal(); redraw(); };
    q('#mk_keep', s).onclick = function () {
      if (s.dataset.busy) return;
      busy(true); errBox(s, '');
      E.api('/v2/marketing/legacy-checked', { method: 'POST', body: {} }).then(function () { busy(false); window.closeModal(); load('owners', true); redraw(); })
        .catch(function (e) { busy(false); errBox(s, errMsg(e)); });
    };
    q('#mk_all', s).onclick = function () {
      if (s.dataset.busy) return;
      busy(true); errBox(s, '');
      var failed = [], p = Promise.resolve();
      items.forEach(function (r) {
        p = p.then(function () { return E.api('/campaigns/' + encodeURIComponent(r.id), { method: 'PUT', body: { currency: 'EGP' } }).catch(function () { failed.push(r.name); }); });
      });
      p.then(function () {
        busy(false); load('campaigns', true);
        if (failed.length) errBox(s, 'تعذّر تعديل: ' + failed.join('، ') + ' — أعد المحاولة');
        else { window.closeModal(); setNote('تم: ' + Un(items.length, ['حملة واحدة', 'حملتان', 'حملات', 'حملة']) + ' صارت بالجنيه'); redraw(); }
      });
    };
  }

  // —— كيف تُربط المصادر · بعد ربط مدار
  function openHow() {
    var m = model(), needs = MK.sources({ attribution: m.src.attribution.state }).needs;
    var s = openSheet(T.howTitle, '<div class="mk-how">' + needs.map(function (n) { return '<div><h4>' + esc(n.title) + '</h4><p>' + esc(n.how) + '</p></div>'; }).join('') + '</div>'
      + '<div class="acts"><button type="button" class="btn btn-primary" id="mk_ok">' + esc(T.ok) + '</button></div>');
    if (s) q('#mk_ok', s).onclick = function () { window.closeModal(); };
  }
  function openMadar() {
    var s = openSheet(T.madarTitle, '<ul class="mk-madlist">' + T.madarItems.map(function (t) { return '<li>' + esc(t) + '</li>'; }).join('') + '</ul>'
      + '<div class="acts"><button type="button" class="btn btn-primary" id="mk_ok">' + esc(T.ok) + '</button></div>');
    if (s) q('#mk_ok', s).onclick = function () { window.closeModal(); };
  }

  // ------------------------------------------------------------------ ربط الأحداث
  function activate(el, fn) {
    el.addEventListener('click', fn);
    el.addEventListener('keydown', function (e) { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); fn(e); } });
  }
  function retryAll() {
    Object.keys(PATHS).forEach(function (k) { if (state(k) === 'error' || state(k) === 'closed' && k !== 'attribution') load(k, true); });
    if (state('attribution') === 'error') load('attribution', true);
  }
  function brainItem(kind, id) {
    var m = model(), rows = campaignRows(m);
    return rows ? MK.brain(rows, todayISO(m.now), []).items.filter(function (it) { return it.kind === kind && String(it.id) === String(id); })[0] : null;
  }
  function wire(v) {
    qa('[data-a="retry"]', v).forEach(function (b) { b.onclick = retryAll; });
    qa('[data-a="filter"]', v).forEach(function (b) { b.onclick = function () { S.filter = b.getAttribute('data-f'); redraw(); }; });
    qa('[data-a="showall"]', v).forEach(function (b) { b.onclick = function () { S.filter = 'all'; redraw(); }; });
    qa('[data-a="new"]', v).forEach(function (b) { b.onclick = function () { openForm(null); }; });
    qa('[data-a="open"]', v).forEach(function (el) { el.onclick = function (e) { e.stopPropagation(); openDetail(el.getAttribute('data-id')); }; });
    qa('[data-a="rowopen"]', v).forEach(function (el) { el.onclick = function () { openDetail(el.getAttribute('data-id')); }; });
    qa('[data-a="legacy"]', v).forEach(function (b) { b.onclick = openLegacy; });
    qa('[data-a="how"]', v).forEach(function (b) { b.onclick = openHow; });
    qa('[data-a="madar"]', v).forEach(function (b) { b.onclick = openMadar; });
    qa('[data-a="goto"]', v).forEach(function (b) { b.onclick = function () { if (host().openSection) host().openSection(b.getAttribute('data-s'), b.getAttribute('data-t') || undefined); }; });
    qa('[data-a="later"]', v).forEach(function (b) {
      b.onclick = function () {
        var key = b.getAttribute('data-kind') + '_' + b.getAttribute('data-id');
        if (S.skipped.indexOf(key) < 0) S.skipped.push(key);
        store('s', 'mk_later_' + key, '1'); redraw();
      };
    });
    qa('[data-a="brain"]', v).forEach(function (b) {
      b.onclick = function () {
        var it = brainItem(b.getAttribute('data-kind'), b.getAttribute('data-id')), row = it ? rowById(it.id) : null;
        if (!it || !row) return;
        if (it.action === 'complete') openStatus(row, 'completed');
        else if (it.action === 'pause') openStatus(row, 'paused');
        else if (it.action === 'edit') openForm(row);
        else if (it.action === 'detail') openDetail(row.id);
      };
    });
  }

  // ------------------------------------------------------------------ نقطة الدخول
  function drawFor(mod, m) { return mod === 'v2mk_social' ? socialHtml(m) : mod === 'v2mk_plan' ? planHtml(m) : campaignsHtml(m); }
  function redraw() {
    if (!S.view || !host().current || !MODS[host().current()]) return;
    S.mod = host().current();
    if (document.getElementById('epModal')) return;           // لا نعيد الرسم تحت ورقة مفتوحة (ما كُتب فيها يضيع)
    S.view.innerHTML = drawFor(S.mod, model());
    wire(S.view);
    S.sig = signature();
  }
  function restoreSession() {
    var rows = campaignRows(model());
    if (store('s', 'mk_legacy_later') === '1') S.legacyLater = true;
    if (!rows) return;
    var m = model(), all = MK.brain(rows, todayISO(m.now), []).items;
    all.forEach(function (it) { var k = it.kind + '_' + it.id; if (store('s', 'mk_later_' + k) === '1' && S.skipped.indexOf(k) < 0) S.skipped.push(k); });
  }
  function render(mod, view) {
    S.view = view; S.mod = mod;
    (NEEDS[MODS[mod]] || []).forEach(function (k) { load(k, false); });
    restoreSession();
    redraw();
    if (!S.poll) {
      S.poll = setInterval(function () {
        if (!(host().current && MODS[host().current()])) { S.mod = ''; return; }
        S.mod = host().current();
        if (document.getElementById('epModal')) return;
        restoreSession();
        if (signature() !== S.sig) redraw();
      }, 400);
    }
    if (!S.minute) S.minute = setInterval(function () { if (host().current && MODS[host().current()] && !document.getElementById('epModal')) redraw(); }, 60000);
  }

  function cardsFor(m) {
    var rows = campaignRows(m);
    if (!rows) return [];
    return MK.cards(rows, todayISO(m.now), m.skipped).map(function (c) {
      return { kind: c.kind, title: c.title, line: c.line, btn: c.btn, open: function () { if (host().openSection) host().openSection('marketing', 'campaigns'); } };
    });
  }

  window.V2SEC.marketing = {
    owns: function (mod) { return !!MODS[mod]; },
    render: render,
    // اقتراحات العقل بشكل بطاقة قرار (اللوحة الرئيسية تلتقطها لاحقًا بلا تعديل هنا)
    cards: function () { return cardsFor(model()); },
    _state: S, _src: SRC, _tick: function (t) { S.nowOverride = t || 0; redraw(); },
    _html: function (tab, m) { return drawFor(tab === 'social' ? 'v2mk_social' : tab === 'plan' ? 'v2mk_plan' : 'marketing', m); },
    _model: model, _cards: cardsFor
  };
})();
