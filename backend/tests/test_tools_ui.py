# -*- coding: utf-8 -*-
"""واجهة «الأدوات» (docs/v2/tools/SPEC.md) — فحوص الملفات + المسار الكامل في متصفح حقيقي.

Run:  cd backend && python3 -B -m pytest -q -p no:cacheprovider tests/test_tools_ui.py

المسار الكامل بيشغّل `uiharness/v2_shots_tools.py` (كمبيوتر ١٤٤٠ وموبايل ٤٣٠): لوحة الحالة والمربّعات · مفتاح الإيقاف · الأدوات (تشغيل · سعر · رسم تجريبي) ·
الأماكن (رفع · تعديل · إظهار · حذف) · العيّنات · التقرير · الإعدادات · المصدر الواقع والفاضي · المفتاح مقفول.
⛔ صفر شبكة: الداشبورد جوه العملية والمنصة بديل في الذاكرة والمزوّد تجريبي. لو playwright أو المتصفح غير متاحين ⇒ يُتخطّى (فحوص الملفات بتشتغل دايمًا).
"""
import json
import os
import re
import subprocess
import sys

import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(_HERE))
SCRIPT = os.path.join(_HERE, 'uiharness', 'v2_shots_tools.py')


def _read(*parts):
    with open(os.path.join(ROOT, *parts), encoding='utf-8') as fh:
        return fh.read()


def _strip(src):
    src = re.sub(r'/\*.*?\*/', '', src, flags=re.S)
    return '\n'.join(re.sub(r'(^|\s)//.*$', '', ln) for ln in src.split('\n'))


def test_the_tab_the_module_and_the_registry_line_are_wired():
    logic = _read('dashboard-cloud', 'v2-logic.js')
    assert "T('tools', 'الأدوات', 'v2s_tools')" in logic
    js = _read('dashboard-cloud', 'v2s', 'tools.js')
    assert "var MOD = 'v2s_tools'" in js and ').tools = { owns: T.owns, render: T.render }' in js
    assert "if (typeof window === 'undefined' || typeof document === 'undefined') return;" in js, 'الواجهة تتخطّى node'
    index = _read('dashboard-cloud', 'index.html')
    assert index.count('v2s/tools.css') == 1 and index.count('v2s/tools.js') == 1
    # لا مربّع جديد في اللوحة: خريطة المربّعات (١٢) والأقسام (١٣) كما هي
    assert 'key: \'tools\'' not in logic


def test_every_mutation_goes_through_a_confirmation_sheet_with_the_exact_flag():
    code = _strip(_read('dashboard-cloud', 'v2s', 'tools.js'))
    for path in ("'/v2/tools/kill'", "'/enable'", "'/v2/tools/recipes/'", "'/v2/tools/styles'", "'/visible'", "'/v2/tools/samples/'", "'/v2/tools/settings'"):
        assert path in code, path
    assert code.count('runWrite(') >= 5 and code.count('confirmSheet(') >= 6 and code.count('confirmed') >= 8, 'كل كتابة بورقة تأكيد'
    vals = re.findall(r"confirmed\s*[:=]\s*(\S+)", code)
    assert vals and all(v.startswith('true') or v.startswith("'true'") for v in vals), vals
    assert "fd.append('confirmed', 'true')" in code
    assert 'ep-b1' in code and 'ep-b2' in code and 'ep-bs' in code and not re.search(r'class="(btn|v3-btn1|v3-btn2|v2d-btn1)"', code)
    # الرسم التجريبي هو الاستثناء الوحيد (لا كتابة ولا تكلفة) ⇒ بلا ورقة تأكيد وبلا `confirmed`، ولا يرسل `real`
    assert "'/test-render'" in code and not re.search(r"\breal\b", code), 'المعاينة لا تبعت real أبدًا'


def test_no_browser_dialogs_no_browser_storage_and_no_technical_words_in_the_markup():
    code = _strip(_read('dashboard-cloud', 'v2s', 'tools.js'))
    assert not re.search(r'(?<![\w.])(alert|confirm|prompt)\(', code) and 'localStorage' not in code and 'sessionStorage' not in code
    assert 'innerHTML' in code and 'esc(' in code
    js = _strip(_read('dashboard-cloud', 'v2s', 'tools.js'))
    strings = ' '.join(s for s in re.findall(r"'([^'\n]*[؀-ۿ][^'\n]*)'", js) if not re.search(r'[();=]|function', s))
    assert not re.search('ي[ً-ْ]*ق[ً-ْ]*و[ً-ْ]*ّ?[ً-ْ]*م', strings)
    assert not re.search(r'[\d٠-٩]\s*·|·\s*[\d٠-٩]', strings)


def test_the_picture_is_read_as_a_data_url_never_as_a_blob_image():
    # CSP الداشبورد: `img-src 'self' data:` ⇒ صور الأماكن والعيّنات والمعاينة كلها data:، ومفيش blob: في أي src.
    code = _strip(_read('dashboard-cloud', 'v2s', 'tools.js'))
    assert 'readAsDataURL' in code and 'createObjectURL' not in code
    assert "img-src 'self' data:;" in _read('backend', 'app.py')


def test_the_stylesheet_scopes_everything_and_leaves_button_sizes_to_the_shared_system():
    css = _strip(_read('dashboard-cloud', 'v2s', 'tools.css'))
    sels = [s.strip() for blk in re.findall(r'([^{}]+)\{', css) for s in blk.split(',') if s.strip() and not s.strip().startswith('@') and not re.match(r'^(\d+%|from|to)$', s.strip())]
    for s in sels:
        assert re.search(r'\.v2s-tl|\.tl-|#epModal\.v2s-tl-sh|\.ep-b1\.tl-danger|\.ep-bs\.tl-del', s), 'قاعدة خارج النطاق: ' + s
    assert not re.search(r'\.ep-b[12s][^{]*\{[^}]*(min-height|padding|font-size|height)\s*:', css), 'قياسات الأزرار من النظام الموحّد'


def test_full_flow_in_a_real_browser(tmp_path):
    try:
        import playwright  # noqa: F401
    except Exception:   # noqa: BLE001
        pytest.skip('playwright غير متاح')
    out = tmp_path / 'shots'
    p = subprocess.run([sys.executable, '-B', SCRIPT, str(out)], capture_output=True, text=True, timeout=2400, cwd=os.path.dirname(_HERE))
    blob = p.stdout + p.stderr
    if 'Executable doesn\'t exist' in blob or 'BrowserType.launch' in blob:
        pytest.skip('المتصفح غير متاح لـplaywright')
    assert '"problems"' in p.stdout, blob[-2000:]
    rep = json.loads(p.stdout[p.stdout.index('{\n'):])
    assert rep['problems'] == [], rep['problems']
    assert rep['unexpected'] == [] and rep['blocked_inproc'] == []
    assert p.returncode == 0, blob[-1500:]
    assert len(rep['shots']) >= 40
