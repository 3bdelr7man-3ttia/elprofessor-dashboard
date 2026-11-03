# -*- coding: utf-8 -*-
"""مسح الموبايل (جولة r6): يشغّل أي سكربت لقطات موجود كما هو، ويفحص كل لقطة موبايل (عرض ≤٤٦٠) فحصًا إضافيًا
ويكتب النتيجة في ملف JSON واحد، من غير ما يغيّر أي سكربت.

    cd backend && python3 -B tests/uiharness/r6_scan.py <script.py> <out_dir> <scan.json> [باقي الوسائط للسكربت]

الفحوص (في كل لقطة موبايل):
  dot      : «·» ملاصقة لرقم (عربي أو لاتيني)، في النص الظاهر أو في title وaria-label وplaceholder
  comma    : مسافة قبل الفاصلة العربية «،» بعد رقم (أثر استبدال «·» الخاطئ: «١٢٨ ، انضمّ»)
  tap      : هدف لمس ظاهر أقل من ٤٤px في الطول أو العرض (أزرار وروابط وخانات، ما عدا الرابط المضمّن في فقرة)
  font     : نص ظاهر أصغر من ١٢px
  tabs     : شريط تبويبات أعرض من الشاشة (ومعه هل فيه إشارة تلاشٍ)
  hscroll  : تمرير أفقي
⛔ صفر طلبات حقيقية: السكربتات نفسها تشغّل اللوحة جوه العملية على منصة وهمية.
"""
import json
import os
import re
import runpy
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)

from playwright.sync_api import Page  # noqa: E402

SCRIPT = os.path.abspath(sys.argv[1])
OUT = os.path.abspath(sys.argv[2])
SCAN = os.path.abspath(sys.argv[3])
sys.argv = [SCRIPT, OUT] + sys.argv[4:]
os.makedirs(OUT, exist_ok=True)

JS = r"""() => {
  const W = window.innerWidth;
  const vis = (e) => {
    if (!e.getClientRects().length) return false;
    const cs = getComputedStyle(e);
    if (cs.visibility === 'hidden' || cs.display === 'none' || parseFloat(cs.opacity) === 0) return false;
    const r = e.getBoundingClientRect();
    return r.width > 0 && r.height > 0;
  };
  const sel = (e) => {
    let s = e.tagName.toLowerCase();
    if (e.id) s += '#' + e.id;
    if (e.className && typeof e.className === 'string') s += '.' + e.className.trim().split(/\s+/).slice(0, 2).join('.');
    return s;
  };
  const out = {tap: [], font: [], tabs: [], hscroll: 0, dot: [], comma: []};
  const sw = Math.max(document.documentElement.scrollWidth, document.body.scrollWidth);
  if (sw > W + 1) out.hscroll = sw;
  const txt = document.body.innerText || '';
  const m = txt.match(/.{0,10}(?:[0-9٠-٩]\s*[·•]|[·•]\s*[0-9٠-٩]).{0,10}/g);
  if (m) out.dot = m.slice(0, 6);
  document.querySelectorAll('[title],[aria-label],[placeholder]').forEach((e) => {
    ['title', 'aria-label', 'placeholder'].forEach((a) => {
      const v = e.getAttribute(a) || '';
      const mm = v.match(/.{0,10}(?:[0-9٠-٩]\s*[·•]|[·•]\s*[0-9٠-٩]).{0,10}/);
      if (mm && out.dot.length < 6) out.dot.push('@' + a + ': ' + mm[0]);
    });
  });
  const mc = txt.match(/.{0,10}[0-9٠-٩٪%]\s+،.{0,10}/g);
  if (mc) out.comma = mc.slice(0, 6);
  // أهداف اللمس
  document.querySelectorAll('a[href],button,input:not([type=hidden]):not([type=checkbox]):not([type=radio]),select,textarea,[role=button],[role=tab],summary,[data-a],[onclick]').forEach((e) => {
    if (!vis(e)) return;
    if (e.closest('[aria-hidden=true]')) return;
    const cs = getComputedStyle(e);
    const r = e.getBoundingClientRect();
    if (r.right < 0 || r.left > W) return;
    if (e.tagName === 'A' && cs.display === 'inline') return;                       // رابط داخل فقرة
    if (e.tagName === 'INPUT' && e.type === 'file') return;
    const h = Math.round(r.height), w = Math.round(r.width);
    if (h < 44 || w < 44) {
      const t = (e.innerText || e.getAttribute('aria-label') || e.value || '').trim().slice(0, 30);
      out.tap.push({s: sel(e), t: t, w: w, h: h});
    }
  });
  // الخطوط الصغيرة
  const seen = new Set();
  const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
  let n;
  while ((n = walker.nextNode())) {
    const t = n.nodeValue.trim();
    if (!t) continue;
    const p = n.parentElement;
    if (!p || !vis(p) || /^(SCRIPT|STYLE|NOSCRIPT)$/.test(p.tagName)) continue;
    const fs = parseFloat(getComputedStyle(p).fontSize);
    if (fs < 12 && !seen.has(p)) { seen.add(p); out.font.push({s: sel(p) + (p.parentElement ? ' < ' + sel(p.parentElement) : ''), t: t.slice(0, 24), fs: fs}); }
  }
  // التبويبات
  document.querySelectorAll('.v2c-tabs,.tabs,[role=tablist]').forEach((e) => {
    if (!vis(e)) return;
    if (e.scrollWidth > e.clientWidth + 2) {
      const after = getComputedStyle(e, '::after').content, mask = getComputedStyle(e).maskImage || getComputedStyle(e).webkitMaskImage;
      out.tabs.push({s: sel(e), sw: e.scrollWidth, cw: e.clientWidth, fade: (mask && mask !== 'none') || (e.parentElement && e.parentElement.classList.contains('v2c-tabwrap')) || false});
    }
  });
  return out;
}"""

RESULTS = {}
_orig = Page.screenshot


def _patched(self, *a, **k):
    res = _orig(self, *a, **k)
    try:
        vp = self.viewport_size or {}
        path = k.get('path') or ''
        name = os.path.basename(path)
        if name and vp.get('width', 9999) <= 460:
            d = self.evaluate(JS)
            if d['dot'] or d['comma'] or d['tap'] or d['font'] or d['tabs'] or d['hscroll']:
                RESULTS[name] = d
            else:
                RESULTS.setdefault('__clean__', []).append(name)
    except Exception as e:  # الفحص ما يوقّفش اللقطات
        RESULTS.setdefault('__errors__', []).append(str(e)[:120])
    return res


Page.screenshot = _patched
try:
    runpy.run_path(SCRIPT, run_name='__main__')
except SystemExit as e:
    code = e.code
else:
    code = 0
finally:
    with open(SCAN, 'w', encoding='utf-8') as f:
        json.dump(RESULTS, f, ensure_ascii=False, indent=1)
    print('r6_scan: %d لقطات فيها ملاحظات، %d نظيفة' % (len([k for k in RESULTS if not k.startswith('__')]), len(RESULTS.get('__clean__', []))))
sys.exit(code)
