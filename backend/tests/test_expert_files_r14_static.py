# -*- coding: utf-8 -*-
"""«ملف للخبير» الجولة ١٤ في الواجهة والخادم — حقائق ثابتة في المصدر (SPEC-R14 §٤).

Run:  cd backend && python3 -m pytest -q tests/test_expert_files_r14_static.py

قراية ملفات بس: التأكيد جوه الصفحة (مش `confirm()`)، القفل بيبعت `confirmed: true`، قايمة التخصصات في الخادم والواجهة
واحدة، الاسم `kind`/`sign_date` مش `urgent_deadline`، والنصوص الجديدة عربي بسيط من غير كلام تقني ولا «يقوّم» ولا «الذكاء
الاصطناعي» في أول عنوان. السلوك نفسه: `test_expert_files_r14_ui.py` و`test_expert_files_r14_dashboard.py`.
"""
import os
import re

import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(os.path.dirname(_HERE))
INDEX = os.path.join(_ROOT, 'dashboard-cloud', 'index.html')
API_JS = os.path.join(_ROOT, 'dashboard-cloud', 'dashboard-api.js')
APP_PY = os.path.join(_ROOT, 'backend', 'app.py')

UI_FUNCS = ('efAutoOn', 'efAutoLine', 'efAutoWire', 'efChips', 'efAssignLogHtml', 'efDeclinedHtml', 'efCandTags',
            'efContractDocHtml', 'efNoCandStrip')
ROW_FUNCS = ('efIsContract', 'efPagesOf', 'efKindLabel', 'efSpecName', 'efSpecOf', 'efCandSpecs', 'efCandReviewsContracts',
             'efCandAway', 'efDeclineWhy', 'efAssignLog', 'efNoCandidate')
APP_FUNCS = ('_ef_pages', '_ef_clause_out', '_ef_contract_out', '_ef_contract_name', 'platform_expert_files_settings',
             'platform_expert_files_settings_set')


@pytest.fixture(scope='module')
def html():
    with open(INDEX, encoding='utf-8') as fh:
        return fh.read()


@pytest.fixture(scope='module')
def apijs():
    with open(API_JS, encoding='utf-8') as fh:
        return fh.read()


@pytest.fixture(scope='module')
def app_src():
    with open(APP_PY, encoding='utf-8') as fh:
        return fh.read()


def _body(src, head):
    start = src.index(head)
    nxt = re.search(r'\n(?:function |/\* |const |var |  EP\.[A-Za-z]+ = function|  function |  var LOADERS|def |@app\.route|# ---)',
                    src[start + len(head):])
    return src[start:start + len(head) + (nxt.start() if nxt else len(src))]


def _new_ui(html):
    return ''.join(_body(html, 'function %s(' % n) for n in UI_FUNCS)


def _new_api(apijs):
    return ''.join(_body(apijs, 'function %s(' % n) for n in ROW_FUNCS) + _body(apijs, 'EP.expertFileAutoAssign = function')


def test_new_functions_exist(html, apijs, app_src):
    for n in UI_FUNCS:
        assert 'function %s(' % n in html, n
    for n in ROW_FUNCS:
        assert 'function %s(' % n in apijs, n
    for n in APP_FUNCS:
        assert 'def %s(' % n in app_src, n
    assert 'EP.expertFileAutoAssign = function' in apijs


def test_no_browser_dialogs_in_the_new_code(html, apijs):
    for src in (_new_ui(html), _new_api(apijs)):
        for bad in ('confirm(', 'alert(', 'prompt(', 'window.confirm', 'window.alert'):
            assert bad not in src, bad


def test_closing_is_confirmed_inside_the_page_and_sends_the_flag(html, apijs):
    line = _body(html, 'function efAutoLine(')
    assert 'class="ef-conf" role="group"' in line and 'aria-live="polite"' in line
    assert 'data-auto="go"' in line and 'data-auto="x"' in line
    send = _body(apijs, 'EP.expertFileAutoAssign = function')
    assert 'confirmed: true' in send and '"PUT"' in send and '/platform-expert-files/settings' in send
    wire = _body(html, 'function efAutoWire(')
    assert "const value=a==='on'" in wire and "a==='off'" in wire and "a==='x'" in wire and 'moneyConfirmModal' not in wire and 'openModal' not in wire


def test_the_switch_is_loaded_for_admins_only_and_failures_are_quiet(apijs):
    inbox = apijs[apijs.index('var efDisputeIds = {}'):]
    admin_block = inbox[:inbox.index('// تسليمات الشات')]
    assert 'String(EP.role || "").trim().toLowerCase() === "admin"' in admin_block
    assert '/platform-expert-files/settings' in admin_block
    settings = admin_block[admin_block.index('/platform-expert-files/settings'):][:520]
    assert 'EP.data.efSettings = null' in settings                               # الفشل ⇒ من غير مفتاح، مش «تعذّر»
    assert 'fail(' not in settings and 'failUnless403' not in settings


def test_old_files_behave_as_before_when_the_new_keys_are_missing(apijs):
    assert 'f.kind === "contract"' in _body(apijs, 'function efIsContract(')       # الغايب = سؤال
    assert 'Array.isArray(f.assign_log)' in _body(apijs, 'function efAssignLog(') or 'f.assign_log' in _body(apijs, 'function efAssignLog(')
    assert 'c.available === false' in _body(apijs, 'function efCandAway(')       # الغايب = متاح
    assert 'efNoCandidate(f)' in _body(apijs, 'function efFileRow(')


def test_the_specialty_list_is_one_list_on_the_server_and_in_the_browser(apijs, app_src):
    js = apijs[apijs.index('var EF_SPECIALTIES = {'):]
    js = js[:js.index('};')]
    py = app_src[app_src.index('_EF_SPECIALTIES = {'):]
    py = py[:py.index('}\n')]
    js_pairs = dict(re.findall(r'(\w+):\s*"([^"]+)"', js))
    py_pairs = dict(re.findall(r"'(\w+)':\s*'([^']+)'", py))
    assert js_pairs == py_pairs and len(js_pairs) == 11
    assert tuple(js_pairs)[-1] == 'other'


def test_the_urgent_deadline_field_and_sign_date_are_not_touched(html, apijs, app_src):
    """`urgent_deadline` (ميعاد المحكمة) و`sign_date` (موعد التوقيع) حاجات تانية — مفيش واحد فيهم بيتقري في الجولة دي."""
    for src in (_new_ui(html), _new_api(apijs)):
        assert 'urgent_deadline' not in src and 'sign_date' not in src
    for n in ('_ef_contract_out', '_ef_clause_out'):
        assert 'urgent_deadline' not in _body(app_src, 'def %s(' % n)


def test_the_proxy_is_admin_only_with_one_bridge_call_and_a_known_audit_name(app_src):
    for fn in ('platform_expert_files_settings', 'platform_expert_files_settings_set'):
        head = app_src[:app_src.index('def %s(' % fn)]
        decorators = head[head.rindex('@app.route'):]
        assert "@roles_required('admin')" in decorators and '@token_required' in decorators
    put = _body(app_src, 'def platform_expert_files_settings_set(')
    assert "_ef_bridge('PUT', '/api/bridge/expert-files/settings'" in put and 'by' in put and '_actor_email()' in put
    assert "_audit('expert_file.auto_assign'" in put and '_ef_no_reply' in put
    assert put.count('_ef_bridge(') == 1                                         # ولا إعادة محاولة


def test_new_visible_copy_is_plain_arabic_without_tech_words_or_forbidden_ones(html, apijs):
    text = _new_ui(html) + _new_api(apijs)
    strings = re.findall(r"""['"`]([^'"`\n]*[؀-ۿ][^'"`\n]*)['"`]""", text)
    assert strings, 'مفيش نصوص عربي اتلقطت'
    for t in strings:
        for bad in ('يقوّم', 'يقوم بتقييم', 'API', 'JSON', 'HTTP', 'bridge', 'token', 'التوكن', 'الخادم', 'السيرفر'):
            assert bad not in t, (bad, t)
        assert not t.strip().startswith('الذكاء الاصطناعي'), t
    for headline in ('التوزيع التلقائي شغّال', 'التوزيع التلقائي مقفول', 'مين اتبعتله الملف',
                     'مراجعة عقد من خبير معتمد لدى البروفيسور'):
        assert headline in html


def test_the_dashboard_copy_is_egyptian_and_the_numbers_are_arabic_digits(html):
    line = _body(html, 'function efAutoLine(')
    assert re.search(r'[0-9]', ''.join(re.findall(r'[؀-ۿ][^<`]*', line))) is None


def test_the_review_drawer_keeps_the_old_question_path_for_non_contract_files(html):
    d = _body(html, 'function drawReview(')
    assert 'const isContract=' in d and 'efContractDocHtml(cdoc,f,det)' in d
    assert "!po||!Array.isArray(po.answers)||!po.answers.length" in d             # الشكل القديم لسه موجود
    assert 'الرأي زي ما هيوصل لـ' in d
