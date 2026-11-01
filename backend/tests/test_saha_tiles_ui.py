# -*- coding: utf-8 -*-
"""واجهة مربّعات «الساحة» و«الديوان» (docs/v2/saha-tiles/SPEC.md) — فحوص الملفات + المسار الكامل في متصفح حقيقي.

Run:  cd backend && python3 -B -m pytest -q -p no:cacheprovider tests/test_saha_tiles_ui.py

المسار الكامل بيشغّل `uiharness/v2_shots_saha.py` (كمبيوتر ١٤٤٠ وموبايل ٤٣٠): مربّعات الساحة بأرقامها · الأخبار (مراجعة ثم نشر · سحب · جلب جديد) · طابور الفرص بالنوع ·
القائمة والنموذج الكامل (إضافة · تعديل بالفرق · حذف) · الاستيراد (تجربة ثم تأكيد · ملف مرفوع) · رابط دورة التحضير · الآراء · التذكير (مقفول ثم مفتوح) ·
الديوان (الأعمال · التعليقات · التحديات والفائزون · التقرير «لا رقم بعد») · المصدر الواقع والجسر الغايب · المفتاح مقفول.
⛔ صفر شبكة: الداشبورد جوه العملية والمنصة بديل في الذاكرة. لو playwright أو المتصفح غير متاحين ⇒ يُتخطّى (فحوص الملفات بتشتغل دايمًا).
"""
import json
import os
import re
import subprocess
import sys

import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(_HERE))
SCRIPT = os.path.join(_HERE, 'uiharness', 'v2_shots_saha.py')


def _read(*parts):
    with open(os.path.join(ROOT, *parts), encoding='utf-8') as fh:
        return fh.read()


def _strip(src):
    src = re.sub(r'/\*.*?\*/', '', src, flags=re.S)
    return '\n'.join(re.sub(r'(^|\s)//.*$', '', ln) for ln in src.split('\n'))


def _js():
    return _strip(_read('dashboard-cloud', 'v2s', 'saha.js')) + '\n' + _strip(_read('dashboard-cloud', 'v2s', 'saha_diwan.js'))


def test_the_two_tabs_the_modules_and_the_registry_lines_are_wired_inside_the_content_section():
    logic = _read('dashboard-cloud', 'v2-logic.js')
    assert "T('saha',      'الساحة',          'v2s_saha')" in logic and "T('diwan',     'الديوان',         'v2s_diwan')" in logic
    sec = logic[logic.index("{ key: 'content', label: 'المحتوى', img: 'content', desc:"):]
    sec = sec[:sec.index("{ key: 'marketing'")]
    assert "'v2s_saha'" in sec and "'v2s_diwan'" in sec, 'التبويبان داخل قسم المحتوى لا في القائمة الرئيسية'
    assert len(re.findall(r"\{ key: '[a-z]+', label: '", logic[logic.index('var SECTIONS = ['):logic.index('var ALIASES')])) == 13, 'القائمة الرئيسية ١٣ بند'
    saha, diwan = _read('dashboard-cloud', 'v2s', 'saha.js'), _read('dashboard-cloud', 'v2s', 'saha_diwan.js')
    assert "key: 'saha', mod: 'v2s_saha'" in saha and "(window.V2SEC = window.V2SEC || {})[cfg.key] = { owns: B.owns, render: B.render };" in saha
    assert "key: 'diwan', mod: 'v2s_diwan'" in diwan
    for f in (saha, diwan):
        assert "if (typeof window === 'undefined' || typeof document === 'undefined') return;" in f, 'الواجهة تتخطّى node'
    html = _read('dashboard-cloud', 'index.html')
    m = re.search(r'<!-- v2 sections.*?<!-- v2 sections end -->', html, re.S)
    block = m.group(0)
    assert '<link rel="stylesheet" href="v2s/saha.css">' in block and block.count('<script src="v2s/saha.js"></script>') == 1 and block.count('<script src="v2s/saha_diwan.js"></script>') == 1
    assert block.index('v2s/roles.js') < block.index('v2s/saha.js') < block.index('v2s/saha_diwan.js') < block.index('v2s/trainer_share.js'), 'الترتيب أبجدي والمحرّك قبل الديوان'
    assert html.index('v2-logic.js') < html.index('v2s/saha.js'), 'المنطق يتحمّل قبل'
    assert 'v2s_saha' not in _read('dashboard-cloud', 'dashboard-api.js')


def test_every_mutation_goes_through_the_review_sheet_with_the_exact_flag_and_the_preview_is_the_only_unconfirmed_call():
    code = _js()
    api_calls = [ln.strip() for ln in code.split('\n') if 'B.api(' in ln and 'B.api = ' not in ln]
    assert len(api_calls) >= 14, len(api_calls)
    for ln in api_calls:
        assert 'confirmed: true' in ln or '/seed/preview' in ln, ln          # كل نداء كتابة فيه confirmed، والتجربة وحدها بلا (لا تكتب)
    assert code.count('B.flow(') >= 14 and code.count('runWrite(') >= 2
    vals = re.findall(r"confirmed\s*[:=]\s*(\S+)", code)
    assert vals and all(v.startswith('true') for v in vals), vals
    assert code.count('send: function') >= 14, 'كل ورقة كتابة لها `send` واحد يمرّ على التأكيد'
    assert 'ep-b1' in code and 'ep-b2' in code and 'ep-bs' in code and not re.search(r'class="(btn|v3-btn1|v3-btn2|v2d-btn1|m4-)', code)
    assert not re.search(r'\b(confirm|alert|prompt)\(', code) and 'localStorage' not in code and 'sessionStorage' not in code and 'indexedDB' not in code
    assert not re.search(r"https?://(api|app|dashboard)\.elprofessor\.net", code), 'لا عنوان حقيقي في الواجهة'


def test_the_screens_only_call_their_own_admin_routes():
    paths = set(re.findall(r"'(/v2/(?:saha|diwan)/[^'?]*)", _js()))
    assert paths <= {'/v2/saha/news', '/v2/saha/news/run', '/v2/saha/opportunities', '/v2/saha/opportunities/seed/preview', '/v2/saha/opportunities/seed/import', '/v2/saha/settings',
                     '/v2/saha/reminders', '/v2/saha/reminders/run', '/v2/saha/topics', '/v2/saha/opinions', '/v2/saha/opinions/', '/v2/saha/news/', '/v2/saha/opportunities/',
                     '/v2/diwan/works', '/v2/diwan/works/', '/v2/diwan/comments', '/v2/diwan/comments/', '/v2/diwan/challenges', '/v2/diwan/challenges/', '/v2/diwan/report'}, paths
    assert '/v2/saha/reminders/cron' not in _js(), 'المسار الدوري للسرّ المشترك لا للمتصفح'
    assert 'seed/preview' in _js() and 'saha/opportunities/seed/import' in _js()


def test_the_markup_text_has_no_forbidden_visible_copy_and_every_picker_has_other():
    js = _js()
    strings = ' '.join(re.findall(r"'([^'\n]*[؀-ۿ][^'\n]*)'", js))
    assert 'أخرى' in strings and 'امسح الرابط' in strings and 'اختر الفائزين' in strings and 'شغّل الآن' in strings and 'شغّل جلب الأخبار' in strings and 'أعد المحاولة' in strings
    assert not re.search('ي[ً-ْ]*ق[ً-ْ]*و[ً-ْ]*ّ?[ً-ْ]*م', strings)
    assert not re.search(r'[\d٠-٩]\s*·|·\s*[\d٠-٩]', strings)
    assert '→ ' in js and "'← " not in js, 'زرّ الرجوع بسهم الرجوع في الاتجاه العربي'
    saha = _read('dashboard-cloud', 'v2s', 'saha.js')
    assert "sel('kind', v.kind, kinds, create" in saha and "X.COUNTRIES.concat([[X.OTHER, 'أخرى']])" in saha and "sel('language', v.language, X.LANGS" in saha and "sel('funding', v.funding, X.FUNDS" in saha
    diwan = _read('dashboard-cloud', 'v2s', 'saha_diwan.js')
    assert "X.WORK_KINDS.map(function (k)" in diwan and "sel('prize_type_' + i, p.type, X.PRIZE_TYPES)" in diwan


def test_the_css_is_scoped_has_no_yellow_and_keeps_the_touch_sizes():
    css = _strip(_read('dashboard-cloud', 'v2s', 'saha.css'))
    css_nm = re.sub(r'@media[^{]*\{', '', css)
    css_nm = re.sub(r'@keyframes [^{]+\{(?:[^{}]*\{[^{}]*\})*[^{}]*\}', '', css_nm)
    bad = []
    for sel in re.findall(r'([^{}]+)\{', css_nm):
        for part in sel.split(','):
            part = part.strip()
            if part and not re.match(r'^(\.v2s-sh|\.sh-|#epModal\.v2s-sh-sh|\.fld)', part):
                bad.append(part)
    assert not bad, bad[:5]
    for hexc in re.findall(r'#([0-9A-Fa-f]{6})\b', css):
        r, g, b = int(hexc[0:2], 16), int(hexc[2:4], 16), int(hexc[4:6], 16)
        assert not (r > 190 and g > 150 and b < 140 and abs(r - g) < 90), 'لون أصفر: #' + hexc
    assert 'min-height:44px' in css and 'min-height:48px' in css and 'font-size:16px' in css
    assert '@media (max-width:760px)' in css and '.sh-tbw{display:none}' in css and '.sh-cards.sh-m{display:grid}' in css


def test_the_route_module_and_the_dockerfile_ship_together():
    app = _read('backend', 'app.py')
    assert "import v2_saha_routes as _v2s_saha; _v2s_saha.register(app, globals())" in app
    assert 'COPY backend/v2_saha_routes.py /app/v2_saha_routes.py' in _read('Dockerfile')
    assert 'COPY dashboard-cloud/v2s /app/dist/v2s' in _read('Dockerfile')


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
    assert len(rep['shots']) >= 60
