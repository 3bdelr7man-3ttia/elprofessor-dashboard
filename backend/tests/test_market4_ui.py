# -*- coding: utf-8 -*-
"""واجهة «إدارة السوق» (docs/v2/market4/SPEC.md) — فحوص الملفات + المسار الكامل في متصفح حقيقي.

Run:  cd backend && python3 -B -m pytest -q -p no:cacheprovider tests/test_market4_ui.py

المسار الكامل بيشغّل `uiharness/v2_shots_market4.py` (كمبيوتر ٤٣٠ وموبايل): المربّعات · اقتراحات «أخرى» بالاعتماد والرفض · مدى الأسعار (البحث · الفلتر · سبع عملات · التحذير ·
المراجعة · المسح) · المكاتب («وثّق السجل») · الطلبات المفتوحة · بلاد القيد وملف الترخيص عند قبول الانضمام · سلّم السوق في النسب · المصدر الواقع والفاضي ·
المفتاح مقفول. ⛔ صفر شبكة: الداشبورد جوه العملية والمنصة بديل في الذاكرة. لو playwright أو المتصفح غير متاحين ⇒ يُتخطّى (فحوص الملفات بتشتغل دايمًا).
"""
import json
import os
import re
import subprocess
import sys

import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(_HERE))
SCRIPT = os.path.join(_HERE, 'uiharness', 'v2_shots_market4.py')


def _read(*parts):
    with open(os.path.join(ROOT, *parts), encoding='utf-8') as fh:
        return fh.read()


def _strip(src):
    src = re.sub(r'/\*.*?\*/', '', src, flags=re.S)
    return '\n'.join(re.sub(r'(^|\s)//.*$', '', ln) for ln in src.split('\n'))


def test_the_tab_the_module_and_the_registry_line_are_wired():
    logic = _read('dashboard-cloud', 'v2-logic.js')
    assert "T('manage', 'إدارة السوق', 'v2s_market_v4')" in logic
    js = _read('dashboard-cloud', 'v2s', 'market4.js')
    assert "var MOD = 'v2s_market_v4'" in js and ').market4 = { owns: M.owns, render: M.render }' in js
    assert "if (typeof window === 'undefined' || typeof document === 'undefined') return;" in js, 'الواجهة تتخطّى node'
    reg = _read('dashboard-cloud', 'v2s', '_registry.js')
    assert 'V2SEC.owner' in reg or 'owner' in reg


def test_every_mutation_goes_through_a_confirmation_sheet_with_the_exact_flag():
    code = _strip(_read('dashboard-cloud', 'v2s', 'market4.js'))
    for path in ("'/decide'", "'/anchor'", "'/verify-reg'"):
        assert path in code, path
    # كل كتابة (POST/PUT) جوه runWrite أو ورقة، و`confirmed` بقيمة true حرفيًا
    assert code.count('runWrite(') >= 5 and code.count('api(') >= 5
    vals = re.findall(r"confirmed\s*[:=]\s*(\S+)", code)
    assert vals and all(v.startswith('true') for v in vals), vals
    assert 'ep-b1' in code and 'ep-b2' in code and 'ep-bs' in code and not re.search(r'class="(btn|v3-btn1|v3-btn2|v2d-btn1)"', code)


def test_the_licence_block_is_hooked_into_both_join_approval_screens():
    people = _read('dashboard-cloud', 'v2s', 'people.js')
    assert 'V2S_MARKET4' in people and "licenceHtml(row, 'v2pmL')" in people and 'licensed_countries: lc.list' in people
    html = _read('dashboard-cloud', 'index.html')
    assert html.count("V2S_MARKET4.licenceHtml(i,'inl')") == 1 and "licensed_countries:lc.list" in html and "licenceWire(el,i,'inl')" in html
    api = _read('dashboard-cloud', 'dashboard-api.js')
    assert 'licence: jrLicence(jr.answers)' in api and 'jrAttachments(jr.attachments)' in api and 'JR_LICENCE_KEYS' in api
    assert 'licensed_countries' in _read('backend', 'app.py')


def test_the_licence_file_is_shown_as_data_or_a_download_never_as_a_blob_image():
    # CSP الداشبورد: `img-src 'self' data:` ⇒ الصورة من data: (FileReader)، وPDF تنزيل. blob: في src صورة = شاشة فاضية في الإنتاج.
    code = _strip(_read('dashboard-cloud', 'v2s', 'market4.js'))
    assert 'readAsDataURL' in code and "'<img class=\"m4-lic-img\"" in code
    assert not re.search(r'<img[^>]*src="\'?\s*\+\s*(href|URL\.createObjectURL)', code)
    assert 'download="licence.pdf"' in code
    app = _read('backend', 'app.py')
    assert "img-src 'self' data:;" in app


def test_the_markup_text_has_no_forbidden_visible_copy():
    js = _strip(_read('dashboard-cloud', 'v2s', 'market4.js'))
    strings = ' '.join(re.findall(r"'([^'\n]*[؀-ۿ][^'\n]*)'", js))
    assert 'أخرى' in strings and 'امسح المدى' in strings and 'وثّق السجل' in strings and 'عرض ملف الترخيص' in strings
    assert not re.search('ي[ً-ْ]*ق[ً-ْ]*و[ً-ْ]*ّ?[ً-ْ]*م', strings)
    assert not re.search(r'[\d٠-٩]\s*·|·\s*[\d٠-٩]', strings)


def test_full_flow_in_a_real_browser(tmp_path):
    try:
        import playwright  # noqa: F401
    except Exception:   # noqa: BLE001
        pytest.skip('playwright غير متاح')
    out = tmp_path / 'shots'
    p = subprocess.run([sys.executable, '-B', SCRIPT, str(out)], capture_output=True, text=True, timeout=1500, cwd=os.path.dirname(_HERE))
    blob = p.stdout + p.stderr
    if 'Executable doesn\'t exist' in blob or 'BrowserType.launch' in blob:
        pytest.skip('المتصفح غير متاح لـplaywright')
    assert '"problems"' in p.stdout, blob[-2000:]
    rep = json.loads(p.stdout[p.stdout.index('{\n'):])
    assert rep['problems'] == [], rep['problems']
    assert rep['unexpected'] == [] and rep['blocked_inproc'] == []
    assert p.returncode == 0, blob[-1500:]
    assert len(rep['shots']) >= 30
