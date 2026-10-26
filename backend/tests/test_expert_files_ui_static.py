# -*- coding: utf-8 -*-
"""«ملف للخبير» في الواجهة — حقائق ثابتة في المصدر (الجولة ٦ · SPEC §١٠-ب).

Run:  cd backend && python3 -m pytest -q tests/test_expert_files_ui_static.py

قراية ملفات بس (زي `test_dash_ia_structure.py`): القايمة ما كبرتش، الشرايح والعدّادات بأسماء مفاتيح
المنصة الحقيقية، ولا نافذة متصفح للتأكيد، وفعل الفلوس بيبعت `confirmed: true`، والسجل له أسماء عربي،
ولا كلمة بتختار «الرأي الرسمي»، ولا كلام تقني في النصوص الجديدة. السلوك نفسه في المتصفح:
`test_expert_files_ui.py`.
"""
import os
import re

import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(os.path.dirname(_HERE))
INDEX = os.path.join(_ROOT, 'dashboard-cloud', 'index.html')
API_JS = os.path.join(_ROOT, 'dashboard-cloud', 'dashboard-api.js')

NEW_UI_FUNCS = ('drawExpertFile', 'drawDispute', 'expertPickModal', 'moneyConfirmModal',
                'opinionsCompareModal', 'efRefundModal', 'efResolveModal', 'efOpinionPreview')
NEW_API_FUNCS = ('EP.expertFileDetail', 'EP.expertFileSend', 'EP.expertFileRefund', 'EP.disputeDecide')
NEW_ROW_FUNCS = ('efFileRow', 'efDisputeRow', 'consDisputeRow', 'efFlagBadges')


@pytest.fixture(scope='module')
def html():
    with open(INDEX, encoding='utf-8') as fh:
        return fh.read()


@pytest.fixture(scope='module')
def apijs():
    with open(API_JS, encoding='utf-8') as fh:
        return fh.read()


def _body(src, head):
    """من `function X(` (أو `EP.X = function`) لحد أول تعريف تاني على أول السطر/بعد مسافتين."""
    start = src.index(head)
    nxt = re.search(r'\n(?:function |/\* |  EP\.[A-Za-z]+ = function|  function |  var LOADERS)', src[start + len(head):])
    return src[start:start + len(head) + (nxt.start() if nxt else len(src))]


def _modules(html):
    body = html[html.index('const MODULES={'):html.index('const CO_PINNED=')]
    out = {}
    for mid, rest in re.findall(r"^\s{2}([a-z_]+):\{(.*)\},?$", body, re.M):
        g = re.search(r"grp:'([a-z]+)'", rest)
        out[mid] = g.group(1) if g else None
    return out


def test_menu_did_not_grow(html):
    mods = _modules(html)
    assert len([m for m, g in mods.items() if g and g != 'co']) == 12
    assert len([m for m, g in mods.items() if g == 'co']) == 4
    assert not any('ملف' in k or 'expert_file' in k for k in mods)


def test_inbox_types_files_and_disputes_exist(html):
    t = _body(html, 'function inboxType(')
    assert "i.apiKind==='expert_file')return 'files'" in t
    assert "i.apiKind==='dispute')return 'disputes'" in t
    # قبل «قرارات» — وإلا كل صفّ فيه apiKind كان هيقع في «قرارات».
    assert t.index("'files'") < t.index("return 'decisions'")
    r = _body(html, 'function renderInbox(')
    assert "['files','ملفات للخبير'" in r and "['disputes','نزاعات'" in r
    assert 'i.searchText' in r


def test_queue_counters_read_the_real_keys(html):
    c = _body(html, 'function opsQueueCounters(')
    for key in ('expert_files_waiting', 'expert_files_late', 'expert_files_disputed', 'expert_files_unactivated'):
        assert "'%s'" % key in c, key
    # «اتدفعت وما وصلتش للتوزيع» عدّاد من غير شاشة (د١٢) ⇒ الوجهة null.
    assert "n(Q.expert_files_unactivated),null,'expert_files_unactivated'" in c
    assert 'expert_files_awaiting_assignment' not in html
    for key in ('expert_files_waiting', 'expert_files_late', 'expert_files_disputed'):
        assert key + ':function(){activeFilter=' in html, key
    assert 'expert_files_awaiting_payment' in _body(html, 'function opsQueuePanel(')
    assert 'expert_files_open_total' in _body(html, 'function opsQueuePanel(')


def test_inbox_nav_item_keeps_opening_the_whole_inbox(html):
    a = _body(html, 'function applyNavCounts(')
    assert "c[2]!=='inbox'" in a


@pytest.mark.parametrize('fn', NEW_UI_FUNCS)
def test_no_browser_dialogs_in_the_new_ui(html, fn):
    body = _body(html, 'function %s(' % fn)
    for bad in ('confirm(', 'prompt(', 'alert('):
        assert bad not in body, (fn, bad)


@pytest.mark.parametrize('fn', NEW_API_FUNCS)
def test_no_browser_dialogs_in_the_new_actions(apijs, fn):
    body = _body(apijs, '%s = function' % fn)
    for bad in ('confirm(', 'prompt(', 'alert('):
        assert bad not in body, (fn, bad)


def test_money_calls_send_confirmed_true(apijs):
    assert 'confirmed: true' in _body(apijs, 'EP.expertFileRefund = function')
    assert 'confirmed: true' in _body(apijs, 'EP.disputeDecide = function')
    # التوزيع مش فعل فلوس — ما بيبعتش confirmed.
    assert 'confirmed' not in _body(apijs, 'EP.expertFileSend = function')


def test_money_confirm_locks_the_button_and_the_close(html):
    m = _body(html, 'function moneyConfirmModal(')
    assert 'if(go.dataset.busy)return;' in m
    assert 'go.disabled=true' in m
    assert "s.dataset.busy='1'" in m and 'tryClose' in m
    p = _body(html, 'function expertPickModal(')
    assert "if(!pick||go.dataset.busy)return;" in p


def test_the_inbox_loader_is_admin_only_and_403_is_not_a_failure(apijs):
    inbox = apijs[apijs.index('    inbox: function () {'):apijs.index('    // الضمان والنزاعات: /api/escrow')]
    assert 'String(EP.role || "").trim().toLowerCase() === "admin"' in inbox
    assert 'e.status === 403' in inbox
    for path in ('/platform-expert-files?status=', '/platform-consultation-disputes'):
        assert path in inbox
        # كل النداءات الجديدة جوه حارس الأدمن
        assert inbox.index(path) > inbox.index('=== "admin"')


def test_a_file_dispute_is_listed_once(apijs):
    inbox = apijs[apijs.index('    inbox: function () {'):apijs.index('    // الضمان والنزاعات: /api/escrow')]
    assert 'c.expert_file_id && efDisputeIds[c.expert_file_id]' in inbox


def test_audit_labels_cover_the_new_actions(html):
    a = html[html.index('const AUDIT_LABEL={'):html.index('function auditModal(')]
    for key in ('expert_file.assign', 'expert_file.reassign', 'expert_file.refund', 'expert_file.resolve',
                'expert_file.no_reply', 'consultation.resolve', 'consultation.no_reply'):
        assert "'%s':" % key in a, key


def test_no_official_opinion_choice(html, apijs):
    for src in (html, apijs):
        for bad in ('الرأي الرسمي هو', 'اعتمد التعديل', 'اعتمد الأصلي', 'خلّي التعديل', 'الرأي المعتمد'):
            assert bad not in src, bad
    d = _body(html, 'function drawDispute(')
    assert 'القرار هنا على الفلوس بس — أنهي رأي يفضل هو الرسمي لسه هنتفق عليه.' in d
    c = _body(html, 'function opinionsCompareModal(')
    assert 'data-a=' not in c and 'disputeDecide' not in c      # المقارنة قراية بس


def _visible_strings(src):
    """النصوص العربي في الكود (بين علامات تنصيص) — اللي ممكن تتعرض."""
    return [m for m in re.findall(r"['\"`]([^'\"`]*[؀-ۿ][^'\"`]*)['\"`]", src)]


def test_no_tech_words_in_new_visible_strings(html, apijs):
    chunks = [_body(html, 'function %s(' % f) for f in NEW_UI_FUNCS]
    chunks += [_body(apijs, 'function %s(' % f) for f in NEW_ROW_FUNCS]
    chunks += [_body(apijs, '%s = function' % f) for f in NEW_API_FUNCS]
    for ch in chunks:
        for s in _visible_strings(ch):
            for bad in ('API', 'bridge', 'escrow', 'status', 'جسر', 'Bridge', 'endpoint', 'JSON'):
                assert bad not in s, (bad, s)


def test_browser_never_computes_the_hours(apijs):
    row = _body(apijs, 'function efFileRow(')
    assert 'Date.now' not in row and 'Date.parse' not in row
    assert 'hours_left' in row and 'assign_overdue' in row


def test_failures_never_show_raw_browser_or_http_text(apijs):
    """«Failed to fetch» / «HTTP 502» / «unauthorized» ما يوصلوش للمؤسس، والرد اللي مش رفض أكيد = «ما وصلناش رد»."""
    body = _body(apijs, 'function efFailed(')
    assert 'e.message' not in body
    assert '!status' in body and 'status >= 500' in body and 'noReply' in body


def test_money_windows_name_the_currency_in_words_and_the_audit_title_is_arabic(html):
    for fn in ('efRefundModal', 'efResolveModal'):
        b = _body(html, 'function %s(' % fn)
        assert "efCurName(" in b and "' ('+" not in b, fn
    assert 'Audit Log' not in html


def test_a_resolve_after_a_manual_refund_never_promises_a_platform_remainder(html):
    b = _body(html, 'function efResolveModal(')
    assert 'manual_refund_settled_at' in b and 'المنصة هتدفع' in b
    # المبلغ اللي هيتحوّل له رقم دايمًا (أجر الخبير أو المبلغ كله) — ولا «نصيب الخبير» من غير رقم
    assert 'نصيب الخبير' not in b and 'const pay=has?r.expert_amount:r.amount' in b
