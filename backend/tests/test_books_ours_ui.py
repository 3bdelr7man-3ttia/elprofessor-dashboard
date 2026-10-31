# -*- coding: utf-8 -*-
"""واجهة «كتبنا» (docs/v2/books-ours/SPEC.md §ج د) — فحوص الملفات + المسار الكامل في متصفح حقيقي.

Run:  cd backend && python3 -B -m pytest -q -p no:cacheprovider tests/test_books_ours_ui.py

المسار الكامل بيشغّل `uiharness/v2_shots_books_ours.py` (كمبيوتر وموبايل): القائمة · كتاب جديد · الرفع · الأسعار · المتجر بتأكيد جوه الصفحة · العقل يكتب
وPDF · الأكواد · الفاضي والمصدر الواقع · المفتاح مقفول. ⛔ صفر شبكة: الداشبورد جوه العملية، والمنصة والكاتب والـPDF بدائل في الذاكرة.
لو playwright أو المتصفح غير متاحين ⇒ يُتخطّى (فحوص الملفات بتشتغل دايمًا).
"""
import json
import os
import re
import subprocess
import sys

import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(_HERE))
SCRIPT = os.path.join(_HERE, 'uiharness', 'v2_shots_books_ours.py')


def _read(*parts):
    with open(os.path.join(ROOT, *parts), encoding='utf-8') as fh:
        return fh.read()


def _ours_block():
    js = _read('dashboard-cloud', 'v2s', 'books.js')
    i = js.index("var OMOD = 'v2s_books_ours'")
    return js[i:js.index('R.mods.knowledge = {')]


def test_tab_is_registered_in_books_section_and_module():
    logic = _read('dashboard-cloud', 'v2-logic.js')
    assert "T('ours', 'كتبنا', 'v2s_books_ours')" in logic
    assert "R.mods[OMOD]" in _ours_block()


def test_no_browser_dialogs_no_price_form_no_storage():
    blk = _ours_block()
    assert not re.search(r'\b(alert|confirm|prompt)\s*\(', blk)
    assert 'localStorage' not in blk and 'sessionStorage' not in blk
    assert 'versions:' not in blk and 'visible:' not in blk and "'/v2/prices/book/' + " in blk            # القراءة بس؛ التعديل من ورقة الأسعار الموجودة
    assert 'V2D3.openPrice' in blk or "D3.openPrice" in blk
    assert "'/v2/books/ours/' + encodeURIComponent(b.slug) + '/status'" in blk


def test_unified_buttons_and_other_option():
    blk = _ours_block()
    assert 'ep-b1' in blk and 'ep-b2' in blk and 'ep-bs' in blk
    assert not re.search(r'class="(btn|v3-btn1|v3-btn2)"', blk.split('function openNewBook')[0])
    assert "['other', 'أخرى']" in blk
    assert 'confirmed: true' in blk and "fd.append('confirmed', 'true')" in blk


def test_visible_copy_rules():
    blk = _ours_block()
    strings = ' '.join(re.findall(r"'([^'\n]*[؀-ۿ][^'\n]*)'", blk))
    assert not re.search('ي[ً-ْ]*ق[ً-ْ]*و[ً-ْ]*ّ?[ً-ْ]*م', strings), 'كلمة ممنوعة'
    for word in ('API', 'JSON', 'weasyprint', 'DeepSeek', 'Claude', 'Anthropic'):
        assert word not in strings, word
    assert not re.search(r"<h[1-4][^>]*>\s*(الذكاء|AI)", blk)
    assert 'استرداد' not in strings


def test_dashboard_api_passes_form_data_untouched():
    js = _read('dashboard-cloud', 'dashboard-api.js')
    assert 'opts.body instanceof FormData' in js and 'isForm ? {}' in js


def test_css_scoped_and_ships():
    css = _read('dashboard-cloud', 'v2s', 'books.css')
    tail = css[css.index('«كتبنا» (v2s_books_ours)'):]
    for sel in [l.split('{')[0] for l in tail.splitlines() if '{' in l and not l.lstrip().startswith(('/*', '@', '*'))]:
        assert sel.strip().startswith('.v2s-ours') or sel.strip() == '', sel
    assert 'COPY dashboard-cloud/v2s /app/dist/v2s' in _read('Dockerfile')


def test_full_flow_in_a_real_browser(tmp_path):
    try:
        import playwright  # noqa: F401
    except Exception:   # noqa: BLE001
        pytest.skip('playwright غير متاح')
    out = tmp_path / 'shots'
    p = subprocess.run([sys.executable, '-B', SCRIPT, str(out)], capture_output=True, text=True, timeout=900, cwd=os.path.dirname(_HERE))
    blob = p.stdout + p.stderr
    if 'Executable doesn\'t exist' in blob or 'BrowserType.launch' in blob:
        pytest.skip('المتصفح غير متاح لـplaywright')
    m = re.search(r'^\{.*\}\s*$', p.stdout, re.S | re.M)
    assert m, blob[-2000:]
    rep = json.loads(p.stdout[p.stdout.index('{\n'):])
    assert rep['problems'] == [], rep['problems']
    assert rep['unexpected'] == [] and rep['blocked_inproc'] == []
    assert p.returncode == 0, blob[-1500:]
    assert len(rep['shots']) >= 10
