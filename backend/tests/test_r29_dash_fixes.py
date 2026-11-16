# -*- coding: utf-8 -*-
"""r29 — إصلاحات الاختبار الحيّ (2026-11-16) على «الفلوس» والدورات.

Run:  cd backend && python3 -m pytest -q -p no:cacheprovider tests/test_r29_dash_fixes.py

اللي بيثبّته:
  ١. «مستحق للخبراء والمدرّبين»: محفظة فيها محجوز بس (بيع مؤكَّد في مهلة الأيام) بتظهر بمبلغها لكل عملة + سطر «منها … بتتاح بعد مهلة الأيام»،
     حتى لو الحقل الكلّي `amount` ناقص أو صفر. فشل جلب المحافظ بيتقال في السطر (مش صفر كأنه كل المستحق).
  ٢. «صافي البروفيسور»: دخل الفترة صفر (بيع ثم استرداد كامل) ⇒ «٠ ج» مش «غير متاح بعد»، ومفيش جملة «لا يوجد مصدر».
  ٣. الاسترداد: مهلة نداء المنصة ٤٠ ثانية · رد ضاع ⇒ الجملة الصادقة (مش «تعذّر») · الواجهة تعيد الفحص وتعتبر «استُردّت» نجاحًا.
  ٤. بعد النجاح: الإيصال المؤكَّد يختفي ويتجدد المصدر، وصفحة الشخص تخفي زرار «استرداد».
  ٥. دورة اتوقّفت/اتنشرت قبل كده وأُعيد تقديمها ⇒ «أعاد المدرّب إرسالها بعد التعديل».
⛔ صفر شبكة: المنصة ردود في الذاكرة، والواجهة في node:vm.
"""
import json
import os
import re
import subprocess
import sys

import pytest

import app as appmod  # noqa: E402

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(_HERE, 'uiharness'))
import v2_node  # noqa: E402
import test_r28_dash_money as r28  # noqa: E402,F401  (fixtures: ctx · plat)
from test_r28_dash_money import ctx, plat, _call, PID, REFUND, PREVIEW, DONE  # noqa: E402,F401

needs_node = pytest.mark.skipif(not v2_node.NODE, reason='needs node')
ROOT = os.path.dirname(os.path.dirname(_HERE))
NOW = 1794787200000          # 2026-11-15T00:00:00Z
LATIN = re.compile(r'[A-Za-z]')
SLOW = 'المنصة بتاخد وقت — استنى ثواني وافتح الصفحة تاني قبل ما تجرّب، عشان ما يتكررش'


def _read(*p):
    with open(os.path.join(ROOT, *p), encoding='utf-8') as fh:
        return fh.read()


def _board(src):
    return {x['key']: x for x in v2_node.logic('v2MoneyBoard', dict({'revenues': [], 'escrow': [], 'payouts': []}, **src), 'month', NOW)['numbers']}


# ═══════════════════════════════════════════ ١) «مستحق للخبراء والمدرّبين»
@needs_node
def test_owed_shows_a_hold_only_wallet_in_the_real_bridge_shape():
    real = {'ok': True, 'people': 1, 'payouts_pending_count': 0,
            'totals': [{'currency': 'EGP', 'amount': 157.5, 'on_hold': 157.5, 'withdrawable': 0, 'payouts_pending': 0, 'people': 1}]}
    n = _board({'owed': real})['owed']
    assert n['na'] is False and n['text'] == '١٥٧٫٥٠ ج' and n['count'] == 1
    assert n['note'] == 'في محافظهم مع طلبات سحب لم تُحوَّل بعد، منها ١٥٧٫٥٠ ج بتتاح بعد مهلة الأيام'
    assert not LATIN.search(n['note'] + n['text'])
    # لا محجوز ⇒ لا سطر «منها»
    free = {'ok': True, 'people': 1, 'totals': [{'currency': 'EGP', 'amount': 60, 'on_hold': 0, 'withdrawable': 60, 'payouts_pending': 0}]}
    assert 'منها' not in _board({'owed': free})['owed']['note']


@needs_node
@pytest.mark.parametrize('amount', [0, None, 'x'])
def test_owed_does_not_depend_on_the_total_field_alone(amount):
    row = {'currency': 'EGP', 'on_hold': 157.5, 'withdrawable': 0, 'payouts_pending': 0}
    if amount is not None:
        row['amount'] = amount
    n = _board({'owed': {'ok': True, 'people': 1, 'totals': [row]}})['owed']
    assert n['text'] == '١٥٧٫٥٠ ج' and 'منها ١٥٧٫٥٠ ج بتتاح بعد مهلة الأيام' in n['note']


@needs_node
def test_owed_each_currency_alone_and_never_summed():
    owed = {'ok': True, 'people': 3, 'totals': [{'currency': 'EGP', 'amount': 217.5, 'on_hold': 157.5, 'withdrawable': 0, 'payouts_pending': 60},
                                               {'currency': 'SAR', 'amount': 40, 'on_hold': 15, 'withdrawable': 25, 'payouts_pending': 0},
                                               {'currency': 'USD', 'amount': 0, 'on_hold': 0, 'withdrawable': 0, 'payouts_pending': 0}]}
    n = _board({'owed': owed})['owed']
    assert n['text'] == '٢١٧٫٥٠ ج و٤٠ ر.س' and n['lines'] == ['٢١٧٫٥٠ ج', '٤٠ ر.س']
    assert 'منها ١٥٧٫٥٠ ج و١٥ ر.س بتتاح بعد مهلة الأيام' in n['note']


@needs_node
def test_owed_failure_is_said_not_shown_as_a_plain_zero():
    n = _board({'owed': None})['owed']
    assert 'تعذّر جلب ما في المحافظ' in n['note'] and n['na'] is False       # الرقم = طلبات السحب بس، والسطر يقول إنه ناقص
    n2 = _board({'owed': None, 'payouts': None})['owed']
    assert n2['na'] is True and n2['why'] == 'تعذّر جلب المحافظ وطلبات السحب'


def test_owed_and_refund_calls_get_longer_platform_timeouts(ctx, plat):
    plat.replies[('GET', '/api/bridge/wallets/owed')] = (200, {'ok': True, 'totals': []})
    plat.replies[('GET', '/api/bridge/purchases/pay-1/refund-preview')] = (200, {'ok': True, 'refundable': True})
    plat.replies[('POST', '/api/bridge/purchases/pay-1/refund')] = (200, DONE)
    assert _call(ctx, 'GET', '/api/v2/money/owed').status_code == 200
    assert _call(ctx, 'GET', PREVIEW).status_code == 200
    assert _call(ctx, 'POST', REFUND, {'reason': 'س', 'confirmed': True}).status_code == 200
    t = {(c['method'], c['path']): c['timeout'] for c in plat.seen}
    assert t[('POST', '/api/bridge/purchases/pay-1/refund')] == 40
    assert t[('GET', '/api/bridge/wallets/owed')] == 30
    assert t[('GET', '/api/bridge/purchases/pay-1/refund-preview')] == 20


# ═══════════════════════════════════════════ ٢) «صافي البروفيسور»
SALE = {'date': '2026-11-15', 'source': 'course', 'amount_egp': 450, 'amount_usd': 0}
REFUNDED = dict(SALE, amount_egp=-450)


@needs_node
def test_net_is_zero_not_unavailable_when_the_period_nets_to_zero_without_shares():
    n = _board({'revenues': [SALE, REFUNDED]})
    assert n['income']['text'] == '٠'
    assert n['net']['na'] is False and n['net']['text'] == '٠ ج' and n['net']['lines'] == []
    assert 'مصدر' not in n['net']['note'] and 'لا يشمل' not in n['net']['note']
    # ولا صف أصلًا في الفترة ⇒ برضه «٠ ج»
    assert _board({'revenues': []})['net']['text'] == '٠ ج'


@needs_node
def test_net_keeps_the_leaves_out_line_and_never_claims_there_is_no_source():
    with_share = dict(SALE, seller_share=157.5, platform_share=292.5, share_currency='EGP')
    old = dict(SALE, date='2026-11-14', amount_egp=300, source='consultation')
    n = _board({'revenues': [with_share, old]})['net']
    assert n['text'] == '٢٩٢٫٥٠ ج' and 'ولا يشمل عملية واحدة بلا تفصيل للنصيب' in n['note']
    # كل الصفوف بلا نصيب ودخل الفترة مش صفر ⇒ «غير متاح بعد» بسبب صادق بعدد العمليات
    only_old = _board({'revenues': [old, dict(old, date='2026-11-13')]})['net']
    assert only_old['na'] is True and only_old['why'] == 'لم يُسجَّل نصيب البروفيسور بعد في عمليتين من هذه الفترة'
    for x in (n['note'], only_old['why'], only_old['note']):
        assert 'لا يوجد مصدر' not in x and not LATIN.search(x)
    assert 'لا يوجد مصدر' not in _read('dashboard-cloud', 'v2-logic.js')


# ═══════════════════════════════════════════ ٣-٤) ورقة الاسترداد (الواجهة الحقيقية في node)
def _sheet(refund, rechecks=None, who='receipts', rows=None):
    preview = {'ok': True, 'refundable': True, 'title': 'أساسيات التسويق القانوني', 'amount': 450, 'currency': 'EGP', 'method': 'instapay', 'buyer_name': 'عميل',
               'seller': {'name': 'مدرب', 'amount': 157.5, 'currency': 'EGP', 'on_hold': True, 'covered': True}}
    payload = {'preview': preview, 'refund': refund, 'rechecks': rechecks or [], 'who': who}
    if rows is not None:
        payload['confirmedRows'] = rows
    env = dict(os.environ, TZ='UTC')
    p = subprocess.run([v2_node.NODE, os.path.join(_HERE, 'uiharness', 'r29_refund.js')], input=json.dumps(payload, ensure_ascii=False),
                       capture_output=True, text=True, timeout=60, env=env)
    assert p.returncode == 0, p.stderr[-1500:]
    out = json.loads(p.stdout)
    assert 'error' not in out, out
    return out


ALREADY = {'ok': True, 'refundable': False, 'already_refunded': True, 'title': 'أساسيات التسويق القانوني'}
PENDING = {'ok': True, 'refundable': True, 'already_refunded': False}


@needs_node
@pytest.mark.parametrize('failure', [
    {'status': 502, 'data': {'no_reply': True, 'error': SLOW}},        # رد ضاع من الخادم
    {'status': 504, 'data': {}},                                       # البوابة قطعت بصفحة HTML (الجسم مش JSON)
    {'status': 0, 'data': {}},                                         # المتصفح ما وصلش للخادم
    {},                                                                # بلا حالة ولا جسم أصلًا
])
def test_a_lost_reply_is_rechecked_and_a_refunded_payment_counts_as_success(failure):
    out = _sheet({'fail': failure}, [ALREADY], who='person')
    assert out['closed'] is True and out['done'] is True and out['err'] == ''
    assert 'استُردّت دفعة «أساسيات التسويق القانوني»' in out['toast'] and 'تعذّر' not in out['toast']
    assert [c for c in out['calls'] if c.startswith('POST')] == ['POST /v2/purchases/pay-1/refund'], 'ضغطة واحدة = نداء استرداد واحد'
    assert out['calls'][-1] == 'REFRESH_ALL' and out['refunded'] == {'pay-1': True}


@needs_node
def test_a_late_refund_is_caught_by_the_second_recheck():
    out = _sheet({'fail': {'status': 502, 'data': {'no_reply': True}}}, [PENDING, ALREADY])
    assert out['done'] is True and out['closed'] is True
    assert len([c for c in out['calls'] if c.endswith('refund-preview')]) == 3        # الأولى للورقة + إعادتين


@needs_node
def test_when_the_platform_is_still_slow_the_message_is_honest_and_the_button_stays_locked():
    out = _sheet({'fail': {'status': 502, 'data': {'no_reply': True, 'error': SLOW}}}, [PENDING])
    assert out['closed'] is False and out['done'] is False
    assert SLOW in out['err'] and 'تعذّر تنفيذ العملية' not in out['err']
    assert out['go']['disabled'] is True and out['go']['text'] == 'أكّد الاسترداد'
    assert len([c for c in out['calls'] if c.startswith('POST')]) == 1


@needs_node
def test_a_platform_that_cannot_be_rechecked_gets_the_same_honest_message():
    out = _sheet({'fail': {'status': 504, 'data': {}}}, [{'fail': {'status': 504}}])
    assert SLOW in out['err'] and out['go']['disabled'] is True and out['done'] is False


@needs_node
def test_a_real_refusal_is_not_treated_as_a_timeout_and_can_be_retried():
    out = _sheet({'fail': {'status': 422, 'data': {'error': 'الدفعة بالبطاقة: أعِد المبلغ من لوحة سترايب'}}})
    assert out['err'].count('الدفعة بالبطاقة') == 1 and out['go']['disabled'] is False and out['closed'] is False
    assert not [c for c in out['calls'] if c.endswith('refund-preview')][1:], 'مفيش فحص بعد رفض صريح'


@needs_node
def test_success_closes_notes_and_refreshes_the_confirmed_receipts():
    rows = [{'status': 'confirmed', 'order_ref': 'pay-1', 'product_type': 'course', 'amount': 450, 'currency': 'EGP', 'user_email': 'b@x.test'},
            {'status': 'confirmed', 'order_ref': 'pay-2', 'product_type': 'course', 'amount': 300, 'currency': 'EGP', 'user_email': 'c@x.test'}]
    out = _sheet({'ok': dict(DONE)}, rows=rows, who='person')
    assert out['closed'] is True and out['done'] is True and out['refunded'] == {'pay-1': True}
    assert 'GET /platform-manual-payments?status=confirmed' in out['calls'], 'مصدر الإيصالات المؤكَّدة بيتجدّد فورًا'
    assert 'REFRESH_ALL' in out['calls']
    assert 'وعُكس نصيب المدرّب' in out['toast']


def test_the_two_after_money_functions_do_not_shadow_each_other():
    d3 = _read('dashboard-cloud', 'v2-d3.js')
    assert len(re.findall(r'function afterMoney\(', d3)) == 1, 'نسختين بنفس الاسم كانتا تدوسان على بعض (الأخيرة كانت بتسود)'
    assert 'function refreshMoneyViews(' in d3 and 'S.refunded[String(pid)] = true' in d3
    assert "!S.refunded[String(p.order_ref)]" in d3, 'الإيصال المردود يختفي من القايمة فورًا'
    d2 = _read('dashboard-cloud', 'v2-d2.js')
    assert 'S.refunded[String(pid)] = true' in d2 and 'markRefunded(S.person.resp)' in d2 and "P.resp = markRefunded(r)" in d2


@needs_node
def test_person_purchase_loses_the_refund_button_after_a_refund():
    resp = appmod._v2_person_build('trainer@x.test', r28._person_S(r28.WALLET))
    learn = next(c for c in v2_node.logic('v2Person', resp, NOW, 'trainer@x.test')['cards'] if c['key'] == 'learning')
    assert learn['purchases'][0]['refundable'] is True
    resp['purchases'][0].update({'status': 'refunded', 'refundable': False, 'refund_block': ''})      # بالظبط اللي بتعمله markRefunded في v2-d2.js
    learn2 = next(c for c in v2_node.logic('v2Person', resp, NOW, 'trainer@x.test')['cards'] if c['key'] == 'learning')
    p = learn2['purchases'][0]
    assert p['refundable'] is False and 'استُردّت' in p['meta'], p


# ═══════════════════════════════════════════ ٥) دورة أُعيد إرسالها
def _split(courses, items):
    queue = {'courses_pending': {'count': len(items), 'titles': [i['title'] for i in items], 'items': items}}
    out = v2_node.logic('v2Split', [], [], queue, {'courses': courses, 'now': NOW})
    return [c for c in out['decisions'] if c.get('tag') == 'دورة تنتظر الاعتماد']


ITEM = {'id': 'c1', 'slug': 's', 'title': 'دورة', 'instructor_name': 'مدرب تجريبي', 'submitted_at': '2026-11-15T00:00:00Z'}


@needs_node
@pytest.mark.parametrize('marker', [{'stop_reason': 'تعديل المحتوى'}, {'archived_at': '2026-11-01T00:00:00Z'}, {'published_at': '2026-10-01T00:00:00Z'}])
def test_a_course_stopped_or_published_before_says_the_trainer_resubmitted_it(marker):
    cards = _split([dict({'id': 'c1', 'approval_status': 'pending', 'is_active': False}, **marker)], [ITEM])
    assert len(cards) == 1 and cards[0]['brain'] == 'أعاد المدرّب إرسالها بعد التعديل — مدرب تجريبي'


@needs_node
def test_a_first_time_course_keeps_the_new_course_line_and_so_does_a_missing_list():
    fresh = {'id': 'c1', 'approval_status': 'pending', 'is_active': False, 'stop_reason': '', 'archived_at': ''}
    for courses in ([fresh], None, []):
        cards = _split(courses, [ITEM])
        assert cards[0]['brain'] == 'دورة جديدة مستنية قرارك من مدرب تجريبي'


@needs_node
def test_the_courses_board_strip_says_it_too():
    js = _read('dashboard-cloud', 'v2s', 'courses.js')
    assert "again ? 'أُعيد إرسالها' : 'دورة جديدة'" in js and "esc(L.V2_RESUBMIT_AR)" in js and 'CO.rows = function' in js
    assert "V2CO.rows()" in _read('dashboard-cloud', 'v2-home.js')
