# -*- coding: utf-8 -*-
"""صفُّ «قائمة الانتظار» بعد F-166 — الصفة · البلد · الهاتف · المصدر، والقديمُ ما زال يُرسَم.

Run:  cd backend && python3 -m pytest -q tests/test_waitlist_row_fields.py

شكوى المؤسس (٢٠٢٦-٠٩-١٨): «الصفة مش موجودة، ما أعرفش الرقم ده من أنهي بلد، ولا أقدر أعرف
الناس دي جايّة منين». المنصّة صارت تُلزم الصفة والبلد والرقم وتحفظ اسمَ السطح — وهذا الملفّ
يحرس الطرفَ الآخر: أن اللوحة **ترسم** الأربعة، وأن الصفوفَ الخمسة القديمة (بلا صفةٍ ولا بلدٍ
ولا مصدر) تظلّ ظاهرةً كاملةً بـ«—» مكان الناقص.

⛔ «شاشة فاضية بتكدب»: الحقل الغائب لازم يُكتب «—» لا أن يُفرّغ الصفّ أو يُسقطه.
⛔ «مكتوبٌ ولا يُرسَم»: الاختبارُ لا يقرأ الملفّ فقط — يشغّل `waitlistPanel` في node على صفوفٍ
حقيقيّة ويقيس الناتج.
"""
import json
import os
import re
import shutil
import subprocess

import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(os.path.dirname(_HERE))
INDEX = os.path.join(_ROOT, 'dashboard-cloud', 'index.html')
API_JS = os.path.join(_ROOT, 'dashboard-cloud', 'dashboard-api.js')


@pytest.fixture(scope='module')
def html():
    with open(INDEX, encoding='utf-8') as fh:
        return fh.read()


@pytest.fixture(scope='module')
def apijs():
    with open(API_JS, encoding='utf-8') as fh:
        return fh.read()


# ---------------------------------------------------------------- ١) الجسر ⇒ الصفّ

def test_api_layer_maps_country_and_source_with_a_dash_fallback(apijs):
    """الحقلان الجديدان يُقرآن من صفّ المنصّة، والغائبُ منهما يصير «—» لا فراغًا."""
    block = apijs[apijs.index('waitlist: function ()'):apijs.index('// «باب المؤسسين»')]
    assert 'country: w.country || ""' in block
    assert 'countryLabel: w.country || "—"' in block
    assert 'sourcePage: w.source_page || ""' in block
    assert 'sourceLabel: w.source_page || "—"' in block
    assert 'ipLabel: w.ip || "—"' in block
    # والحقولُ التي كانت موجودة لم تُمسّ.
    for keep in ('roleLabel:', 'specialtyLabel:', 'phone: w.phone'):
        assert keep in block, keep


# ---------------------------------------------------------------- ٢) الرسم فعلًا (node)

NODE = shutil.which('node')

_HELPERS = r"""
const ICONS = {};
function svg(n,c){return '';}
function esc(s){return String(s==null?'':s).replace(/[&<>"']/g,function(c){return {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c];});}
const money = n => (n==null||isNaN(n)) ? '—' : Number(n).toLocaleString('ar-EG');
const WL_STATUS = {new:{t:'مستنّي',cls:'s-wait'},invited:{t:'اتدعى',cls:'s-auto'},declined:{t:'مش دلوقتي',cls:''}};
function invMissingCard(p){return 'MISSING:'+p;}
let ROWS = [];
function wlRows(){return ROWS;}
const EP = { state:{waitlist:'ready'}, data:{waitlist:{rows:[],count:0,missing:false}}, reload(){} };
const window = { EP };   // اللوحة تقرأ `window.EP` حارسًا ثم `EP` مباشرةً — الاثنان نفسُ الكائن.
"""


def _panel_source(html: str) -> str:
    start = html.index('function waitlistPanel()')
    end = html.index('function wireInvites(', start)
    return html[start:end]


def _render(html, rows):
    script = (_HELPERS + _panel_source(html)
              + "\nROWS = " + json.dumps(rows, ensure_ascii=False) + ";\n"
              + "EP.data.waitlist = {rows: ROWS, count: ROWS.length, missing:false};\n"
              + "process.stdout.write(waitlistPanel());\n")
    out = subprocess.run([NODE, '--input-type=module', '-e', script],
                         capture_output=True, text=True, timeout=30)
    assert out.returncode == 0, out.stderr
    return out.stdout


NEW_ROW = {
    'id': 'w-new', 'name': 'وفاء جيهان منصور', 'email': 'wafaa@test.com',
    'note': 'عايزة أوثّق إجاباتي', 'role': 'lawyer', 'roleLabel': 'محامٍ',
    'specialty': 'civil', 'specialtyLabel': 'مدني', 'phone': '+968 7784 6162',
    'country': 'عُمان', 'countryLabel': 'عُمان',
    'sourcePage': 'ستارة الدخول', 'sourceLabel': 'ستارة الدخول',
    'ipLabel': '197.45.10.9',
    'status': 'new', 'when': 'من ساعة', 'at': 2,
}
# الخمسةُ الموجودون فعلًا: بلا صفةٍ ولا تخصّصٍ ولا بلدٍ ولا مصدر — ومنهم اثنان بلا رقم.
OLD_ROW = {
    'id': 'w-old', 'name': 'محمد إبراهيم حسن', 'email': 'old@test.com',
    'note': '', 'role': '', 'roleLabel': '—', 'specialty': '', 'specialtyLabel': '—',
    'phone': '', 'country': '', 'countryLabel': '—', 'sourcePage': '', 'sourceLabel': '—',
    'ipLabel': '10.0.1.2',
    'status': 'new', 'when': 'من ١٤ يوم', 'at': 1,
}


@pytest.mark.skipif(NODE is None, reason='node غير متاح — اختبار الرسم يُتخطّى')
def test_the_row_shows_role_country_phone_and_source(html):
    out = _render(html, [NEW_ROW])
    for label in ('الصفة', 'البلد', 'جاي من فين'):
        assert label in out, label
    for value in ('وفاء جيهان منصور', 'محامٍ', 'عُمان', '+968 7784 6162', 'ستارة الدخول'):
        assert value in out, value


@pytest.mark.skipif(NODE is None, reason='node غير متاح — اختبار الرسم يُتخطّى')
def test_five_old_rows_without_the_new_fields_still_render_whole(html):
    rows = [dict(OLD_ROW, id=f'w-old-{i}', email=f'old{i}@test.com') for i in range(5)]
    out = _render(html, rows)
    assert out.count('class="trow"') == 5                # الخمسةُ كلُّهم مرسومون صفًّا صفًّا
    assert 'محمد إبراهيم حسن' in out
    assert out.count('ابعت دعوة') == 5                   # وزرُّ التحويل معهم
    assert 'محدش طلب دعوة لسه' not in out                # ولا تُقال «مفيش حد» كذبًا
    assert '—' in out                                    # والناقصُ مكتوبٌ لا مُفرَّغ
    for label in ('الصفة', 'البلد', 'جاي من فين'):
        assert out.count(label) == 5, label


@pytest.mark.skipif(NODE is None, reason='node غير متاح — اختبار الرسم يُتخطّى')
def test_a_row_value_cannot_inject_markup(html):
    """كلُّ قيمةٍ تمرّ من `esc` — الصفّ يأتي من زائرٍ مجهول."""
    out = _render(html, [dict(NEW_ROW, countryLabel='<img src=x onerror=alert(1)>',
                              sourceLabel='<script>bad()</script>')])
    assert '<img src=x' not in out and '<script>bad()' not in out
    assert '&lt;img src=x' in out and '&lt;script&gt;bad()' in out


@pytest.mark.skipif(NODE is None, reason='node غير متاح — اختبار الرسم يُتخطّى')
def test_empty_state_is_still_honest_when_there_is_truly_nobody(html):
    out = _render(html, [])
    assert 'محدش طلب دعوة لسه' in out


def test_no_technical_words_in_the_new_labels(html):
    """قاعدةُ المؤسس: لا كلمةَ تقنيّةً في أيّ نصٍّ ظاهر."""
    panel = _panel_source(html)
    labels = re.findall(r'font-weight:800">([^<]+)</div>', panel)
    assert 'البلد' in labels and 'جاي من فين' in labels
    for label in labels:
        assert not re.search(r'[A-Za-z]', label), label


# ---------------------------------------------------------------- ٣) عنوانُ الزائر يُرسَم

@pytest.mark.skipif(NODE is None, reason='node غير متاح — اختبار الرسم يُتخطّى')
def test_the_visitor_address_reaches_the_screen(html):
    """⛔ «مكتوبٌ ولا يُرسَم»: المنصّة صارت تحفظ عنوانَ الزائر الحقيقيّ بدل عنوان الوسيط، فلو
    لم يظهر على الشاشة فالمؤسس لسه ما يعرفش «جه منين» — والحفظُ بلا طريقٍ للعرض لا يُغني."""
    out = _render(html, [NEW_ROW])
    assert '197.45.10.9' in out


@pytest.mark.skipif(NODE is None, reason='node غير متاح — اختبار الرسم يُتخطّى')
def test_a_row_without_an_address_shows_a_dash_not_a_blank(html):
    out = _render(html, [dict(NEW_ROW, ipLabel='')])
    assert '197.45.10.9' not in out
    assert out.count('class="trow"') == 1        # والصفُّ يفضل ظاهرًا كاملًا
