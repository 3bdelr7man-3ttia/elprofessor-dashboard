# -*- coding: utf-8 -*-
"""R31 — فلوس رجعت لمحفظة العميل ما تتحسبش «دخل» (قرار المؤسس 2026-11-17: «لا طبعا ما تحسبش دخل، خلاص طالما رجعت»).

Run:  cd backend && python3 -m pytest -q -p no:cacheprovider tests/test_r31_dash_wallet_refund.py

المنصة بقت تبعت حدث سالب لكل رد للمحفظة بمفتاح ثابت لنوع الرد (`<الدفعة>:wallet_partial` · `<الدفعة>:wallet_full`)، و`refund_of`
هو الدفعة الأصلية. الاختبار ده بيقفل العقد من ناحية اللوحة (من غير تغيير في الكود):
  ١. ردّين على نفس الدفعة (جزئي ثم الباقي) بيتسجّلوا الاتنين — مش التاني «تكرار» — ونفس الحدث لو اتبعت تاني ما بيتحسبش مرتين.
  ٢. «دخل» و«صافي البروفيسور» بيرجعوا صفر لملف مستعجل ٨٠٠ (خبير ٥٠٠ · منصة ٣٠٠) رجع كله للمحفظة على مرتين.

⛔ صفر شبكة: Flask في الذاكرة، والمنطق في node على الملفات الحقيقية.
"""
import datetime
import os
import sys

import jwt
import pytest
from werkzeug.security import generate_password_hash

import app as appmod  # noqa: E402
from app import app as flask_app, db, User, Revenue  # noqa: E402

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(_HERE, 'uiharness'))
import v2_node  # noqa: E402

needs_node = pytest.mark.skipif(not v2_node.NODE, reason='needs node')
SECRET = os.environ.get('METRICS_SECRET', 'test-metrics-secret')
NOW = 1794916800000          # 2026-11-17T12:00:00Z
TODAY = '2026-11-17T09:30:00+00:00'
PAY = 'r31-pay-urgent-1'


def _admin_headers():
    email = 'r31-admin@x.test'
    u = User.query.filter_by(email=email).first()
    if not u:
        u = User(email=email, password_hash=generate_password_hash('x', method='pbkdf2:sha256'), name='r31', role='admin', dashboard_role='admin',
                 linked_to_name='', preferred_currency='AUTO', is_active=True)
        db.session.add(u)
        db.session.commit()
    tok = jwt.encode({'user_id': u.id, 'exp': datetime.datetime.utcnow() + datetime.timedelta(days=1)}, flask_app.config['SECRET_KEY'], algorithm='HS256')
    return {'Authorization': 'Bearer ' + tok}


@pytest.fixture(scope='module')
def ctx():
    with flask_app.app_context():
        db.create_all()
        yield {'client': flask_app.test_client(), 'admin': _admin_headers()}


def _post(client, **body):
    base = {'currency': 'EGP', 'kind': 'consultation', 'source': 'native_payments', 'occurred_at': TODAY}
    base.update(body)
    return client.post('/api/metrics/finance-event', json=base, headers={'X-ELP-Metrics-Secret': SECRET})


@needs_node
def test_two_wallet_refunds_on_one_payment_both_count_and_income_nets_to_zero(ctx, monkeypatch):
    monkeypatch.setattr(appmod, 'METRICS_SECRET', SECRET, raising=False)
    c = ctx['client']
    # البيعة: مستعجل ٨٠٠ (خبير ٥٠٠ · منصة ٣٠٠)
    assert _post(c, payment_id=PAY, amount=800, seller_share=500, platform_share=300, share_currency='EGP').status_code == 200
    # تحوّل عادي ⇒ ٣٠٠ رجعت للمحفظة (خبير ٢٠٠ · منصة ١٠٠)
    partial = dict(payment_id=PAY + ':wallet_partial', refund_of=PAY, event='refund', full_refund=False, refund_to='wallet',
                   amount=-300, amount_original=-300, seller_share=-200, platform_share=-100, share_currency='EGP')
    assert _post(c, **partial).status_code == 200
    # وبعدها الباقي كله رجع ⇒ ٥٠٠ (خبير ٣٠٠ · منصة ٢٠٠) — مفتاح مختلف، مش «تكرار»
    full = dict(payment_id=PAY + ':wallet_full', refund_of=PAY, event='refund', full_refund=False, refund_to='wallet',
                amount=-500, amount_original=-500, seller_share=-300, platform_share=-200, share_currency='EGP')
    assert _post(c, **full).status_code == 200
    # نفس الحدث وصل تاني (إعادة إرسال) ⇒ ما يتحسبش مرتين
    again = _post(c, **full)
    assert again.status_code == 200 and again.get_json().get('duplicate') is True
    with flask_app.app_context():
        rows = Revenue.query.filter((Revenue.payment_id == PAY) | (Revenue.refund_of == PAY)).all()
        assert sorted(r.payment_id for r in rows) == sorted([PAY, 'refund:%s:wallet_partial' % PAY, 'refund:%s:wallet_full' % PAY])
        assert sum(r.amount_egp for r in rows) == 0
        assert sum(r.seller_share for r in rows) == 0 and sum(r.platform_share for r in rows) == 0
        assert {r.source for r in rows} == {'consultation'}
    listed = c.get('/api/revenues', headers=ctx['admin']).get_json()
    mine = [r for r in listed if r.get('refund_of') == PAY or (r.get('description') or '').endswith(PAY)]
    assert len(mine) == 3
    n = {x['key']: x for x in v2_node.logic('v2MoneyBoard', {'revenues': mine, 'escrow': [], 'payouts': []}, 'month', NOW)['numbers']}
    assert n['income']['text'] == '٠', 'فلوس رجعت للمحفظة مش دخل'
    assert n['net']['text'] == '٠ ج', 'ولا نصيب للمنصة من بيعة رجعت'


@needs_node
def test_only_the_difference_leaves_income_when_the_rest_is_still_paid_for(ctx, monkeypatch):
    monkeypatch.setattr(appmod, 'METRICS_SECRET', SECRET, raising=False)
    c = ctx['client']
    pay = 'r31-pay-urgent-2'
    assert _post(c, payment_id=pay, amount=800, seller_share=500, platform_share=300, share_currency='EGP').status_code == 200
    assert _post(c, payment_id=pay + ':wallet_partial', refund_of=pay, event='refund', full_refund=False, refund_to='wallet',
                 amount=-300, amount_original=-300, seller_share=-200, platform_share=-100, share_currency='EGP').status_code == 200
    listed = c.get('/api/revenues', headers=ctx['admin']).get_json()
    mine = [r for r in listed if r.get('refund_of') == pay or (r.get('description') or '').endswith(pay)]
    assert len(mine) == 2
    n = {x['key']: x for x in v2_node.logic('v2MoneyBoard', {'revenues': mine, 'escrow': [], 'payouts': []}, 'month', NOW)['numbers']}
    assert n['income']['text'] == '٥٠٠ ج' and n['net']['text'] == '٢٠٠ ج'
