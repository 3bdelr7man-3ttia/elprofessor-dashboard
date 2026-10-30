/* ============================================================================
 * v2-shell.js — الهيكل الجديد للداشبورد (D1-B): قائمة جانبية فاتحة بـ١٢ قسمًا بصورها وشاراتها، وشريط علوي وورقة قائمة في
 * الشاشات الأضيق، وترويسة القسم بتبويباته. ⛔ لا منطق عمل هنا: الأقسام والتبويبات من `V2L.SECTIONS` (نقية)، والأعداد من
 * `V2.tiles()` نفسها التي ترسم مربّعات اللوحة (تُعَدّ مرة واحدة)، والتنقّل كله يمرّ من `host.openSection` في index.html.
 *
 * ⛔ المفتاح مقفول افتراضيًا: الملف بيتحمّل دايمًا لكنه ما بيعمل شيئًا إلا لو index.html نادى `V2SHELL.boot(host)`
 * (وده ما بيحصل إلا لما `/api/v2/config` يرجّع enabled:true وللأدمن بس).
 * ========================================================================== */
(function () {
  'use strict';
  var L = window.V2L;
  if (!L) return;
  var U = L.util;
  var SH = window.V2SHELL = { on: false };
  var host = null, poll = null, lastSig = '', lastBadge = {}, sheetDirty = false, lastTabSig = '';

  function esc(s) { return String(s == null ? '' : s).replace(/[&<>"']/g, function (c) { return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]; }); }
  function q(sel, root) { return (root || document).querySelector(sel); }
  function img(name) { return 'v2/img/' + name + '.jpg'; }

  var RGB = { files: '158,43,78', disputes: '122,30,40', courses: '91,74,170', market: '176,118,12', books: '14,120,130',
              people: '24,126,78', money: '26,43,74', content: '190,88,48', marketing: '138,38,92', reports: '34,70,112',
              brain: '33,38,46', company: '58,60,72', home: '158,43,78' };
  var LOGO = '<svg viewBox="0 0 798 588" aria-hidden="true"><path fill="currentColor" d="M389 50 Q389 0 439 0 L672 0 Q762 0 762 90 L762 347 L675 347 L675 353 L572 353 L572 588 L496 588 L496 493 L462 493 L462 588 L386 588 L386 493 L302 493 L302 588 L228 588 L228 493 L201 493 L201 588 L104 588 L104 335 L76 335 L76 409 L0 409 L0 351 L40 351 L40 182 L108 182 L108 106 L389 106 Z"/><path fill="currentColor" d="M675 337 L762 337 L762 421 L798 421 L798 492 L675 492 Z"/></svg>';
  var GRID = '<svg viewBox="0 0 24 24" class="v2s-ic" aria-hidden="true"><rect x="3" y="3" width="7" height="7" rx="1.5"/><rect x="14" y="3" width="7" height="7" rx="1.5"/><rect x="3" y="14" width="7" height="7" rx="1.5"/><rect x="14" y="14" width="7" height="7" rx="1.5"/></svg>';
  var OUT = '<svg viewBox="0 0 24 24" class="v2s-ic" aria-hidden="true"><path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4"/><path d="m16 17 5-5-5-5"/><path d="M21 12H9"/></svg>';
  var CLOSE = '<svg viewBox="0 0 24 24" class="v2s-ic" aria-hidden="true"><path d="M6 6l12 12M18 6 6 18"/></svg>';

  // ------------------------------------------------------------------ الأعداد (من نفس v2Tiles)
  function tiles() {
    var out = {};
    try { (window.V2 && V2.tiles ? V2.tiles() : []).forEach(function (t) { out[t.key] = t; }); } catch (e) {}
    return out;
  }
  // شارة القسم: {txt, cls, title} أو null. الجاري جلبه يحتفظ بآخر شارة معروفة (لا وميض عند التحديث).
  function badgeOf(key, T) {
    var t = T[key];
    if (!t) return null;
    var loading = false;
    try { loading = !!(window.V2 && V2.tileLoading && V2.tileLoading(key)); } catch (e) {}
    var b = null;
    if (loading) return lastBadge[key] || null;
    if (t.failed) b = { txt: '!', cls: 'fail', title: L.FAILED_TEXT };
    else if (t.count) b = { txt: U.ar(t.count) + (t.partial ? '+' : ''), cls: t.hot ? 'hot' : '', title: t.partial ? 'العدد ناقص — تعذّر جلب بعض المصادر' : '' };
    lastBadge[key] = b;
    return b;
  }
  function badgeHtml(b) {
    return b ? '<span class="v2s-badge ' + b.cls + '"' + (b.title ? ' title="' + esc(b.title) + '"' : '') + '>' + esc(b.txt) + '</span>' : '';
  }

  // إعادة الرسم لا تُضيّع موضع لوحة المفاتيح: لو التركيز كان على بند/تبويب يرجع لنفس البند بعد الرسم.
  function keepFocus(root, fn) {
    var a = document.activeElement, sel = null;
    if (root && a && root.contains(a)) {
      if (a.getAttribute('data-tab')) sel = '[data-tab="' + a.getAttribute('data-tab') + '"]';
      else if (a.getAttribute('data-sec')) sel = '[data-sec="' + a.getAttribute('data-sec') + '"]';
    }
    fn();
    if (sel) { var n = root.querySelector(sel); if (n && n.focus) { try { n.focus({ preventScroll: true }); } catch (e) {} } }
  }

  // ------------------------------------------------------------------ القائمة الجانبية والورقة
  function userName() {
    try { return (host && host.userName && host.userName()) || 'الإدارة'; } catch (e) { return 'الإدارة'; }
  }
  function activeKey() { var s = host && host.state ? host.state() : null; return s ? s.section : 'home'; }

  function sideItem(sec, on, T) {
    var ph = sec.img
      ? '<span class="v2s-ph" style="background-image:url(' + img(sec.img) + ')"></span>'
      : '<span class="v2s-ph v2s-ph-home">' + GRID + '</span>';
    return '<a class="v2s-item' + (on ? ' on' : '') + '" href="' + L.sectionHash(sec.key, sec.tabs[0].key) + '" data-sec="' + sec.key + '"' + (on ? ' aria-current="page"' : '') + '>'
      + ph + '<span class="v2s-name">' + esc(sec.label) + '</span>' + badgeHtml(sec.img ? badgeOf(sec.key, T) : null) + '</a>';
  }
  function userBlock() {
    var n = userName();
    return '<div class="v2s-me"><span class="v2s-av">' + esc(String(n).trim().charAt(0) || '—') + '</span>'
      + '<span class="v2s-who"><b>' + esc(n) + '</b><small>الإدارة</small></span>'
      + '<button type="button" class="v2s-out" data-act="logout" aria-label="تسجيل الخروج" title="تسجيل الخروج">' + OUT + '</button></div>';
  }
  function drawSide(T) {
    var el = q('#v2Side'); if (!el) return;
    var act = activeKey();
    keepFocus(el, function () { el.innerHTML = '<div class="v2s-brand"><span class="v2s-mark">' + LOGO + '</span><span class="v2s-bt"><b>البروفيسور</b><small>غرفة التحكم</small></span></div>'
      + '<nav class="v2s-nav" aria-label="الأقسام">' + L.SECTIONS.map(function (s) { return sideItem(s, s.key === act, T); }).join('') + '</nav>'
      + userBlock(); });
  }
  function sheetTile(sec, on, T) {
    var b = sec.img ? badgeHtml(badgeOf(sec.key, T)) : '';
    return '<a class="v2s-tile' + (on ? ' on' : '') + (sec.img ? '' : ' home') + '" href="' + L.sectionHash(sec.key, sec.tabs[0].key) + '" data-sec="' + sec.key + '"'
      + ' style="--rgb:' + (RGB[sec.key] || '33,38,46') + (sec.img ? ';background-image:url(' + img(sec.img) + ')' : '') + '">'
      + (sec.img ? '' : GRID) + b + '<span class="v2s-tn">' + esc(sec.label) + '</span></a>';
  }
  function drawSheet(T) {
    var el = q('#v2Sheet'); if (!el) return;
    var act = activeKey();
    el.innerHTML = '<div class="v2s-scrim" data-act="close"></div><div class="v2s-box" role="dialog" aria-modal="true" aria-label="الأقسام">'
      + '<div class="v2s-bh"><b>الأقسام</b><button type="button" class="v2s-x" data-act="close" aria-label="إغلاق">' + CLOSE + '</button></div>'
      + '<div class="v2s-grid">' + L.SECTIONS.map(function (s) { return sheetTile(s, s.key === act, T); }).join('') + '</div>'
      + userBlock() + '</div>';
  }
  SH.nav = function () {
    if (!SH.on) return;
    var T = tiles();
    drawSide(T); drawHead(T);
    // الورقة المفتوحة لا تُعاد كتابتها (يضيع التركيز والتمرير)؛ تُرسم عند إغلاقها.
    if (SH.sheetOpen()) sheetDirty = true; else { drawSheet(T); sheetDirty = false; }
    wire();
  };

  // ------------------------------------------------------------------ ترويسة القسم
  function descOf(sec, T) {
    var t = T[sec.key];
    if (t && !t.failed && t.next) {
      var loading = false;
      try { loading = !!(window.V2 && V2.tileLoading && V2.tileLoading(sec.key)); } catch (e) {}
      if (!loading) return t.next;
    }
    return sec.desc;
  }
  function drawHead(T) {
    var el = q('#v2sec'); if (!el) return;
    var s = host && host.state ? host.state() : { section: 'home', tab: 'board' };
    var sec = L.sectionByKey(s.section) || L.SECTIONS[0];
    var oldStrip = q('.v2c-tabs', el), keepLeft = oldStrip ? oldStrip.scrollLeft : 0;
    keepFocus(el, function () { el.innerHTML = '<div class="v2c-h"><h1>' + esc(sec.label) + '</h1><p>' + esc(descOf(sec, T || tiles())) + '</p></div>'
      + '<div class="v2c-tabs" role="tablist" aria-label="' + esc(sec.label) + '">'
      + sec.tabs.map(function (t) {
          return '<button type="button" role="tab" class="v2c-tab' + (t.key === s.tab ? ' on' : '') + '" aria-selected="' + (t.key === s.tab) + '" data-sec="' + sec.key + '" data-tab="' + t.key + '">' + esc(t.label) + '</button>';
        }).join('')
      + '</div>'; });
    // شريط التبويبات: يحفظ موضعه عبر إعادة الرسم، ولا يتحرّك إلا حين يتغيّر التبويب (بلا أي تمرير رأسي للصفحة).
    try {
      var strip = q('.v2c-tabs', el), on = q('.v2c-tab.on', el), sig = s.section + '/' + s.tab;
      if (strip) {
        strip.scrollLeft = keepLeft;
        if (sig !== lastTabSig && on && strip.scrollWidth > strip.clientWidth + 1) {
          var sr = strip.getBoundingClientRect(), orr = on.getBoundingClientRect();
          strip.scrollLeft += (orr.left + orr.width / 2) - (sr.left + sr.width / 2);
        }
      }
      lastTabSig = sig;
    } catch (e) {}
  }
  SH.head = function () { if (SH.on) { drawHead(tiles()); wire(); } };

  // ------------------------------------------------------------------ الأحداث
  function wire() {
    var root = document;
    ['#v2Side', '#v2Sheet'].forEach(function (id) {
      var el = q(id); if (!el) return;
      el.querySelectorAll('[data-sec]').forEach(function (a) {
        a.onclick = function (e) {
          if (e.metaKey || e.ctrlKey || e.shiftKey || e.button === 1) return;
          e.preventDefault();
          SH.closeSheet();
          if (host) host.openSection(a.getAttribute('data-sec'));
        };
      });
      el.querySelectorAll('[data-act="logout"]').forEach(function (b) { b.onclick = function () { if (host && host.logout) host.logout(); }; });
      el.querySelectorAll('[data-act="close"]').forEach(function (b) { b.onclick = function () { SH.closeSheet(); }; });
    });
    var h = q('#v2sec');
    if (h) h.querySelectorAll('.v2c-tab').forEach(function (b) {
      b.onclick = function () { if (host) host.openSection(b.getAttribute('data-sec'), b.getAttribute('data-tab')); };
    });
  }
  SH.openSheet = function () {
    var el = q('#v2Sheet'); if (!el) return;
    el.classList.add('open'); el.setAttribute('aria-hidden', 'false');
    document.documentElement.classList.add('v2-noscroll');
    var f = q('.v2s-x', el); if (f && f.focus) { try { f.focus(); } catch (e) {} }
  };
  SH.closeSheet = function () {
    var el = q('#v2Sheet'); if (!el) return;
    el.classList.remove('open'); el.setAttribute('aria-hidden', 'true');
    document.documentElement.classList.remove('v2-noscroll');
    if (sheetDirty) { sheetDirty = false; try { drawSheet(tiles()); wire(); } catch (e) {} }
  };
  SH.sheetOpen = function () { var el = q('#v2Sheet'); return !!(el && el.classList.contains('open')); };

  // ------------------------------------------------------------------ الإقلاع
  SH.boot = function (h) {
    if (SH.on) return;
    host = h; SH.on = true;
    var app = q('.app'); if (!app) { SH.on = false; return; }
    app.classList.add('v2-shell');
    var rail = q('.rail');
    var side = document.createElement('aside');
    side.id = 'v2Side'; side.className = 'v2-side';
    if (rail && rail.parentNode) rail.parentNode.insertBefore(side, rail.nextSibling); else app.insertBefore(side, app.firstChild);
    var view = q('#view');
    if (view && view.parentNode) {
      var sec = document.createElement('div');
      sec.id = 'v2sec'; sec.className = 'v2-sec';
      view.parentNode.insertBefore(sec, view);
    }
    var sheet = document.createElement('div');
    sheet.id = 'v2Sheet'; sheet.className = 'v2-sheet'; sheet.setAttribute('aria-hidden', 'true');
    document.body.appendChild(sheet);
    var tb = q('.topbar'), ttl = tb && q('.ttl', tb);
    if (tb && ttl && !q('.v2-tb-logo', tb)) {
      var lg = document.createElement('span');
      lg.className = 'v2-tb-logo'; lg.innerHTML = LOGO;
      tb.insertBefore(lg, ttl);
    }
    var mb = q('#menuBtn');
    if (mb) mb.onclick = function () { if (SH.sheetOpen()) SH.closeSheet(); else SH.openSheet(); };
    document.addEventListener('keydown', function (e) {
      if (!SH.sheetOpen()) return;
      if (e.key === 'Escape') { SH.closeSheet(); return; }
      if (e.key !== 'Tab') return;
      // حبس التنقّل بـTab داخل الورقة المفتوحة (aria-modal).
      var box = q('#v2Sheet .v2s-box'); if (!box) return;
      var f = Array.prototype.slice.call(box.querySelectorAll('a[href],button:not([disabled])')).filter(function (n) { return n.offsetParent !== null; });
      if (!f.length) return;
      var first = f[0], last = f[f.length - 1], cur = document.activeElement;
      if (!box.contains(cur)) { e.preventDefault(); first.focus(); }
      else if (e.shiftKey && cur === first) { e.preventDefault(); last.focus(); }
      else if (!e.shiftKey && cur === last) { e.preventDefault(); first.focus(); }
    });
    window.addEventListener('resize', function () { if (window.innerWidth >= 1180) SH.closeSheet(); });
    // كل المصادر تُحمَّل مرة عند الإقلاع، والشارات تتحدّث حين تتغيّر الأعداد (بلا عدّ ثانٍ ولا طلب إضافي).
    try { if (window.V2 && V2.loadAll) V2.loadAll(function () { SH.refresh(); }); } catch (e) {}
    SH.nav();
    if (!poll) poll = setInterval(SH.refresh, 1000);
  };
  SH.refresh = function () {
    if (!SH.on) return;
    var T = tiles(), sig;
    try { sig = (window.V2 && V2.sourcesSignature ? V2.sourcesSignature() : '') + '|' + L.SECTIONS.map(function (s) { var t = T[s.key]; return t ? [t.count, t.failed, t.hot, t.partial, t.next].join(',') : ''; }).join(';') + '|' + userName(); } catch (e) { sig = ''; }
    if (sig === lastSig) return;
    lastSig = sig;
    SH.nav();
  };
})();
