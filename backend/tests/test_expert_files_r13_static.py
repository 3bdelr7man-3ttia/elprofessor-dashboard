# -*- coding: utf-8 -*-
"""«ملف للخبير» الجولة ١٣ في الواجهة والخادم — حقائق ثابتة في المصدر (SPEC-R13 §٥ · docs/EXPERT-FILES-DASHBOARD-SPEC.md §١٩).

Run:  cd backend && python3 -m pytest -q tests/test_expert_files_r13_static.py

قراية ملفات بس: التأكيد جوه الدرج (مش `confirm()`)، فعل الفلوس بيبعت `confirmed: true`، الاسم `speed` مش `urgent_deadline`،
والنصوص الجديدة عربي بسيط من غير كلام تقني ولا «يقوّم». السلوك نفسه: `test_expert_files_r13_ui.py`.
"""
import os
import re

import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(os.path.dirname(_HERE))
INDEX = os.path.join(_ROOT, 'dashboard-cloud', 'index.html')
API_JS = os.path.join(_ROOT, 'dashboard-cloud', 'dashboard-api.js')
APP_PY = os.path.join(_ROOT, 'backend', 'app.py')
SPEC = os.path.join(_ROOT, 'docs', 'EXPERT-FILES-DASHBOARD-SPEC.md')

UI_FUNCS = ('efUrgentField', 'efPlanLine', 'efCaseOf', 'efQuoteHtml', 'efMsReady', 'efMsHtml', 'efCaseHtml', 'efCaseWire', 'drawCase',
            'efCaseUiReset', 'efNewest')
ROW_FUNCS = ('efUrgentOf', 'efFellBackOf', 'efWhen', 'efUrgentBadges', 'efCaseMilestones', 'efCaseDisputed', 'efCaseRow')
APP_FUNCS = ('_ef_s', '_ef_n', '_ef_urgent_out', '_ef_question_out', '_ef_quote_out', '_ef_problem_text',
             '_ef_milestone_out', '_ef_case_out', 'platform_expert_file_case_resolve')


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


def _new_rows(apijs):
    return ''.join(_body(apijs, 'function %s(' % n) for n in ROW_FUNCS) + _body(apijs, 'EP.caseResolve = function')


def test_new_functions_exist(html, apijs, app_src):
    for n in UI_FUNCS:
        assert 'function %s(' % n in html, n
    for n in ROW_FUNCS:
        assert 'function %s(' % n in apijs, n
    for n in APP_FUNCS:
        assert 'def %s(' % n in app_src, n
    assert 'EP.caseResolve = function' in apijs


def test_no_browser_dialogs_in_the_new_code(html, apijs):
    for src in (_new_ui(html), _new_rows(apijs)):
        for bad in ('confirm(', 'alert(', 'prompt(', 'window.confirm', 'window.alert'):
            assert bad not in src, bad


def test_the_confirmation_is_inside_the_drawer_not_a_modal(html):
    m = _body(html, 'function efMsHtml(')
    assert 'class="ef-conf"' in m and 'role="group"' in m and 'aria-live="polite"' in m
    assert 'moneyConfirmModal' not in m and 'openModal' not in m
    w = _body(html, 'function efCaseWire(')
    assert 'moneyConfirmModal' not in w and 'openModal' not in w
    assert 'EP.caseResolve(' in w and 'ui.busy||ui.final' in w                         # الضغطة التانية بتتمنع
    # الأزرار الأساسية بالأسماء اللي في SPEC §٥
    assert 'حوّل للخبير' in m and 'ردّ للعميل' in m


def test_the_resolve_action_sends_confirmed_true_to_the_one_route(apijs):
    f = _body(apijs, 'EP.caseResolve = function')
    assert 'confirmed: true' in f
    assert '"/platform-expert-files/" + encodeURIComponent(i.apiId) + "/case/milestones/" + encodeURIComponent(m.n) + "/resolve"' in f
    assert 'by:' not in f and 'by =' not in f                         # الخادم بياخده من التوكن
    assert 'action === "release" ? "release" : "refund"' in f
    assert 'efFailed(e, after)' in f and 'efDone(' in f


def test_the_case_lane_is_loaded_for_admins_only_and_a_422_is_not_a_failure(apijs):
    inbox = apijs[apijs.index('    inbox: function () {'):apijs.index('    // الضمان والنزاعات: /api/escrow')]
    assert '["case_disputed", "قضايا فيها ملاحظة"]' in inbox
    assert 'L[0] === "case_disputed") { realRows.push(efCaseRow(f)); return; }' in inbox
    assert 'e.status === 422' in inbox
    # جوه فرع الأدمن بس
    assert inbox.index('role || "").trim().toLowerCase() === "admin"') < inbox.index('"case_disputed"')


def test_the_two_filters_are_chips_over_real_rows_only(html):
    m = _body(html, 'function inboxMatches(')
    assert "if(f==='urgent')return !!i.urgent;" in m and "if(f==='case')return i.efLane==='case_disputed';" in m
    r = _body(html, 'function renderInbox(')
    assert "mk('urgent','⚡ مستعجل ('" in r and "mk('case','قضايا فيها ملاحظة ('" in r
    assert 'if(urgentN)' in r and 'if(caseN)' in r                        # من غير صفوف ⇒ من غير شريحة


def test_the_drawers_that_show_the_urgent_card_and_the_case(html):
    assert 'efUrgentField(f,det)' in _body(html, 'function drawReview(')
    assert 'efUrgentField(r,det)' in _body(html, 'function drawDispute(')
    d = _body(html, 'function drawExpertFile(')
    assert 'efUrgentField(f)' in d and 'efCaseHtml(i)' in d and 'efCaseWire(el,i' in d
    assert "i.apiKind==='expert_file'&&i.efLane==='case_disputed'){drawCase(el,i)" in _body(html, 'function drawInbox(')
    # بجنب مشغّل الصوت: الكارت قبله في درج المراجعة
    r = _body(html, 'function drawReview(')
    assert r.index('efUrgentField(f,det)') < r.index('efVoiceField(i.apiId')


def test_the_urgent_name_is_speed_never_the_courts_urgent_deadline(html, apijs, app_src):
    for src in (_new_ui(html), _new_rows(apijs)):
        assert 'urgent_deadline' not in src
    block = _body(app_src, 'def _ef_urgent_out(') + _body(app_src, 'def platform_expert_file_case_resolve(')
    assert 'urgent_deadline' not in block
    assert "out['speed'] = 'urgent' if f.get('speed') == 'urgent' else 'normal'" in app_src


def test_the_proxy_route_is_admin_only_and_uses_the_one_bridge_helper(app_src):
    head = "@app.route('/api/platform-expert-files/<file_id>/case/milestones/<n>/resolve', methods=['POST'])"
    assert head in app_src
    r = app_src[app_src.index(head):]
    r = r[:r.index("@app.route('/api/platform-consultation-disputes'")]
    assert r.splitlines()[1:3] == ['@token_required', "@roles_required('admin')"]
    assert "_ef_bridge('POST', f'/api/bridge/expert-files/{file_id}/case/milestones/{n}/resolve'" in r
    assert "json_body={'action': action, 'note': note, 'by': _actor_email()}" in r
    assert "body.get('confirmed') is not True" in r and "n not in ('1', '2')" in r
    assert 'requests.' not in r and 'stripe' not in r.lower() and 'paytabs' not in r.lower()   # ⛔ ولا بوابة دفع
    assert "_audit('expert_file.case_resolve'" in r and "_ef_no_reply_resp('expert_file', file_id, 'case_resolve', action)" in r


def test_the_new_list_filters_are_accepted(app_src):
    t = app_src[app_src.index('_EF_LIST_STATUSES = ('):]
    t = t[:t.index(')') + 1]
    for s in ('urgent', 'case_disputed', 'case_open'):
        assert "'%s'" % s in t, s


def test_the_detail_whitelists_the_new_keys_only(app_src):
    d = _body(app_src, 'def _ef_detail_out(')
    assert "out['urgent'] = _ef_urgent_out(f.get('urgent'))" in d and "out['case'] = _ef_case_out(f.get('case'))" in d
    assert "_EF_DETAIL_KEYS = ('id', 'title', 'status', 'file_no', 'dispute', 'opinion', 'revision', 'pending_opinion', 'review')" in app_src
    ms = _body(app_src, 'def _ef_milestone_out(')
    for banned in ('client_email', 'payment_id', 'member_email', 'phone'):
        assert banned not in ms and banned not in _body(app_src, 'def _ef_quote_out(')


def test_the_audit_title_is_arabic(html):
    a = html[html.index('const AUDIT_LABEL={'):html.index('function auditModal(')]
    assert "'expert_file.case_resolve':'حسم ملاحظة على مرحلة من قضية'" in a
    assert "a==='expert_file.case_resolve'&&m.milestone_label" in html


_AR_STR = re.compile(r"""(["'`])((?:\\.|(?!\1).)*?[؀-ۿ](?:\\.|(?!\1).)*?)\1""")


def _visible(src):
    return [m.group(2) for m in _AR_STR.finditer(src)]


def test_new_visible_text_is_plain_arabic_with_no_technical_words_and_no_forbidden_word(html, apijs):
    texts = _visible(_new_ui(html) + _new_rows(apijs))
    assert len(texts) > 40
    bad = ('API', 'JSON', 'bridge', 'endpoint', 'webhook', 'ledger', 'escrow', 'ESCROW', 'يقوّم', 'يقوم بتقييم', 'تقييم',
           'gateway', 'Stripe', 'stripe', 'PayTabs', 'Fawaterak', 'الجسر', 'سيرفر', 'كاش')
    for t in texts:
        for b in bad:
            assert b not in t, (b, t)
        assert not t.lstrip().startswith('الذكاء الاصطناعي'), t


def test_digits_shown_to_the_founder_come_from_arabic_formatters(html):
    """المبالغ والتواريخ بتعدّي على `efM`/`efFileNo`/`efSlot` (أرقام عربية) — مفيش رقم إنجليزي مطبوع على الشاشة."""
    m = _body(html, 'function efMsHtml(') + _body(html, 'function efQuoteHtml(') + _body(html, 'function efUrgentField(')
    assert 'efM(' in m and 'efFileNo(' in m and 'efSlot(' in m
    assert 'toFixed' not in m and 'Intl.NumberFormat' not in m


def test_spec_has_the_round_13_section(html):
    with open(SPEC, encoding='utf-8') as fh:
        s = fh.read()
    assert '§١٩' in s and 'الجولة ١٣' in s and 'case/milestones' in s
    assert 'speed' in s and 'urgent_deadline' in s
