# -*- coding: utf-8 -*-
"""R28 — الفلوس بالحقيقة بعد اختبار الشراء الحيّ (2026-11-15) + «استرداد» شراء دورة اندفع يدويًا.

Run:  cd backend && python3 -m pytest -q -p no:cacheprovider tests/test_r28_dash_money.py

اللي بيثبّته:
  ١. حدث البيع بيخزّن نصيب صاحب العمل ونصيب البروفيسور (والاسترداد بالسالب) و`/api/revenues` بيرجّعهم.
  ٢. «صافي البروفيسور» بيتحسب من نصيب المنصة لكل عملة، و«مستحق» من المحافظ (المحجوز + المتاح + سحب لم يُحوَّل).
  ٣. صفحة الدورة: المبيعات ونسبة الإكمال من شكل الجسر الحقيقي (`courses`/`items` · `course_id`).
  ٤. صفحة الشخص: رصيد المحفظة لكل عملة «منها … تُتاح للسحب يوم …» ومشتريات الدورات بزرار «استرداد».
  ٥. مسار الاسترداد: أدمن بس · المفتاح · تأكيد صريح · سبب · نوع شغل مقفول على «يسألك» في الخادم · `by` من التوكن · تدقيق بعد النجاح بس.
  ٦. التحديث الصامت: «دخل» بيتحدّث مع دورة `V2.refreshAll` وبعد أي قرار فلوس.

⛔ صفر شبكة: المنصة ردود في الذاكرة، والمنطق في node على الملفات الحقيقية.
"""
import copy
import datetime
import json
import os
import re
import sys

import jwt
import pytest
from werkzeug.security import generate_password_hash

import app as appmod  # noqa: E402
from app import app as flask_app, db, User, AuditLog, Revenue  # noqa: E402
from brain2 import levels  # noqa: E402

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(_HERE, 'uiharness'))
import v2_node  # noqa: E402

needs_node = pytest.mark.skipif(not v2_node.NODE, reason='needs node')
ROOT = os.path.dirname(os.path.dirname(_HERE))
PLATFORM = 'https://platform.test'
SECRET = os.environ.get('METRICS_SECRET', 'test-metrics-secret')
ADMIN_EMAIL = 'r28-admin@x.test'
NON_ADMIN = ['employee', 'trainer', 'investor', 'viewer', 'pending']
NOW = 1794787200000          # 2026-11-15T00:00:00Z
LATIN = re.compile(r'[A-Za-z]')


def _read(*p):
    with open(os.path.join(ROOT, *p), encoding='utf-8') as fh:
        return fh.read()


class _Resp(object):
    def __init__(self, status, payload):
        self.status_code = status
        self._p = payload
        self.content = json.dumps(payload, ensure_ascii=False).encode('utf-8') if payload is not None else b''
        self.headers = {'Content-Type': 'application/json'}

    def json(self):
        return self._p


def _mkuser(email, role):
    u = User.query.filter_by(email=email).first()
    if not u:
        u = User(email=email, password_hash=generate_password_hash('x', method='pbkdf2:sha256'), name=email.split('@')[0], role=role, dashboard_role=role,
                 linked_to_name='', preferred_currency='AUTO', is_active=True)
        db.session.add(u)
    u.role = role
    u.dashboard_role = role
    u.is_active = True
    db.session.commit()
    return u


def _bearer(user):
    tok = jwt.encode({'user_id': user.id, 'exp': datetime.datetime.utcnow() + datetime.timedelta(days=1)}, flask_app.config['SECRET_KEY'], algorithm='HS256')
    return {'Authorization': 'Bearer ' + tok}


@pytest.fixture(scope='module')
def ctx():
    with flask_app.app_context():
        db.create_all()
        heads = {r: _bearer(_mkuser('r28-%s@x.test' % r, r)) for r in NON_ADMIN}
        heads['admin'] = _bearer(_mkuser(ADMIN_EMAIL, 'admin'))
        yield {'heads': heads, 'client': flask_app.test_client()}


class Plat(object):
    """المنصة: جدول ردود بالمسار. أي عنوان برّه المنصة الوهمية بيوقّع الاختبار."""

    def __init__(self):
        self.replies = {}
        self.seen = []
        self.blocked = []

    def __call__(self, method, url, params=None, json=None, headers=None, timeout=None):
        self.seen.append({'method': method.upper(), 'path': url[len(PLATFORM):], 'params': dict(params or {}), 'json': copy.deepcopy(json), 'timeout': timeout})
        if not url.startswith(PLATFORM + '/'):
            self.blocked.append(url)
            raise RuntimeError('طلب حقيقي ممنوع: ' + url)
        rep = self.replies.get((method.upper(), url[len(PLATFORM):]))
        if rep is None:
            return _Resp(404, {'detail': 'Not Found'})
        if rep == 'boom':
            raise RuntimeError('timeout')
        return _Resp(*rep)


@pytest.fixture
def plat(monkeypatch):
    p = Plat()
    monkeypatch.setattr(appmod, 'PLATFORM_METRICS_SECRET', SECRET)
    monkeypatch.setattr(appmod, 'PLATFORM_API_URL', PLATFORM)
    monkeypatch.setattr(appmod.requests, 'request', p)
    monkeypatch.setenv('DASH_V2_ENABLED', 'true')
    yield p
    assert p.blocked == []


def _call(ctx, method, path, body=None, who='admin'):
    heads = {} if who is None else ctx['heads'][who]
    return ctx['client'].open(path, method=method, headers=heads, json=body) if body is not None else ctx['client'].open(path, method=method, headers=heads)


PID = 'pay-1'
REFUND = '/api/v2/purchases/%s/refund' % PID
PREVIEW = '/api/v2/purchases/%s/refund-preview' % PID
DONE = {'ok': True, 'already': False, 'payment_id': PID, 'status': 'refunded', 'title': 'أساسيات التسويق القانوني', 'amount': 450, 'currency': 'EGP',
        'buyer_email': 'buyer@x.test', 'clawback': 'clawed_back',
        'seller': {'email': 'trainer@x.test', 'amount': 157.5, 'currency': 'EGP', 'was_on_hold': True, 'outcome': 'clawed_back'}}


# ═══════════════════════════════════════════ ١) حدث البيع بالأنصبة
def _fe(ctx, **body):
    return ctx['client'].post('/api/metrics/finance-event', json=body, headers={'X-ELP-Metrics-Secret': SECRET})


def test_finance_event_stores_shares_and_the_refund_is_negative(ctx, monkeypatch):
    monkeypatch.setattr(appmod, 'METRICS_SECRET', SECRET, raising=False)
    r = _fe(ctx, payment_id='r28-sale-1', amount=450, currency='EGP', kind='course', seller_share=157.5, platform_share=292.5, share_currency='EGP',
            occurred_at='2026-11-15T10:00:00+00:00')
    assert r.status_code == 200, r.get_json()
    r2 = _fe(ctx, payment_id='r28-sale-1', amount=-450, currency='EGP', kind='course', event='refund', refund_of='r28-sale-1', full_refund=True,
             seller_share=-157.5, platform_share=-292.5, share_currency='EGP')
    assert r2.status_code == 200
    with flask_app.app_context():
        sale = Revenue.query.filter_by(payment_id='r28-sale-1').first()
        ref = Revenue.query.filter_by(payment_id='refund:r28-sale-1').first()
        assert (sale.seller_share, sale.platform_share, sale.share_currency) == (157.5, 292.5, 'EGP')
        assert (ref.seller_share, ref.platform_share, ref.amount_egp) == (-157.5, -292.5, -450)
    # بلا أنصبة (بيعة قديمة / استشارة) ⇒ NULL مش صفر
    _fe(ctx, payment_id='r28-sale-2', amount=100, currency='EGP', kind='consultation')
    _fe(ctx, payment_id='r28-sale-3', amount=100, currency='EGP', kind='course', seller_share='x', platform_share=10)
    with flask_app.app_context():
        for pid in ('r28-sale-2', 'r28-sale-3'):
            row = Revenue.query.filter_by(payment_id=pid).first()
            assert row.seller_share is None and row.platform_share is None and row.share_currency is None
    # استرداد لبيعة قديمة من غير أنصبة (زي بيعة الاختبار الحيّ قبل R28) ⇒ الاسترداد من غير أنصبة كمان، فالصافي ما يطلعش بالسالب
    _fe(ctx, payment_id='r28-old', amount=450, currency='EGP', kind='course')
    _fe(ctx, payment_id='r28-old', amount=-450, currency='EGP', kind='course', event='refund', refund_of='r28-old', full_refund=True,
        seller_share=-157.5, platform_share=-292.5)
    with flask_app.app_context():
        old_ref = Revenue.query.filter_by(payment_id='refund:r28-old').first()
        assert old_ref.amount_egp == -450 and old_ref.platform_share is None and old_ref.seller_share is None
    rows = ctx['client'].get('/api/revenues', headers=ctx['heads']['admin']).get_json()
    one = next(x for x in rows if x['id'] and x.get('platform_share') == 292.5)
    assert one['seller_share'] == 157.5 and one['share_currency'] == 'EGP'


# ═══════════════════════════════════════════ ٢) اللوحة: الصافي والمستحق
REV = [
    {'date': '2026-11-15', 'source': 'course', 'amount_egp': 450, 'amount_usd': 0, 'seller_share': 157.5, 'platform_share': 292.5, 'share_currency': 'EGP'},
    {'date': '2026-11-14', 'source': 'course', 'amount_egp': None, 'amount_usd': 0, 'needs_fx': True, 'currency': 'SAR', 'amount_original': 100,
     'seller_share': 35, 'platform_share': 65, 'share_currency': 'SAR'},
    {'date': '2026-11-13', 'source': 'consultation', 'amount_egp': 300, 'amount_usd': 0},
]


@needs_node
def test_net_is_the_platform_share_per_currency_and_says_what_it_leaves_out():
    b = v2_node.logic('v2MoneyBoard', {'revenues': REV, 'escrow': [], 'payouts': []}, 'month', NOW)
    n = {x['key']: x for x in b['numbers']}
    assert n['net']['na'] is False and n['net']['text'] == '٢٩٢٫٥٠ ج و٦٥ ر.س', 'كل عملة لوحدها ولا جمع'
    assert 'ولا يشمل عملية واحدة بلا تفصيل للنصيب' in n['net']['note']
    # بيعة واسترداد كامل ⇒ الصافي صفر حقيقي «٠» مش «غير متاح»
    full = [REV[0], dict(REV[0], amount_egp=-450, seller_share=-157.5, platform_share=-292.5)]
    n2 = {x['key']: x for x in v2_node.logic('v2MoneyBoard', {'revenues': full, 'escrow': [], 'payouts': []}, 'month', NOW)['numbers']}
    assert n2['net']['na'] is False and n2['net']['text'] == '٠ ج' and n2['income']['text'] == '٠'
    # ولا صف معروف ⇒ «غير متاح بعد» بالسبب القديم
    n3 = {x['key']: x for x in v2_node.logic('v2MoneyBoard', {'revenues': [REV[2]], 'escrow': [], 'payouts': []}, 'month', NOW)['numbers']}
    assert n3['net']['na'] is True and n3['net']['why'] and 'مصدر' not in n3['net']['why'], 'ما ندّعيش إن مفيش مصدر'


@needs_node
def test_owed_comes_from_the_wallets_and_falls_back_to_payouts():
    owed = {'ok': True, 'people': 2, 'totals': [{'currency': 'EGP', 'amount': 217.5, 'on_hold': 157.5, 'withdrawable': 0, 'payouts_pending': 60},
                                               {'currency': 'SAR', 'amount': 40, 'on_hold': 0, 'withdrawable': 40, 'payouts_pending': 0}]}
    payouts = [{'pid': 'p', 'status': 'pending', 'raw': {'amount': 60, 'currency': 'EGP'}}]
    n = {x['key']: x for x in v2_node.logic('v2MoneyBoard', {'revenues': [], 'escrow': [], 'payouts': payouts, 'owed': owed}, 'month', NOW)['numbers']}
    assert n['owed']['text'] == '٢١٧٫٥٠ ج و٤٠ ر.س' and n['owed']['count'] == 2
    assert 'منها ١٥٧٫٥٠ ج بتتاح بعد مهلة الأيام' in n['owed']['note']
    n2 = {x['key']: x for x in v2_node.logic('v2MoneyBoard', {'revenues': [], 'escrow': [], 'payouts': payouts, 'owed': None}, 'month', NOW)['numbers']}
    assert n2['owed']['text'] == '٦٠ ج' and n2['owed']['note'] == 'طلبات سحب أُرسلت ولم تُحوَّل بعد، وتعذّر جلب ما في المحافظ فالرقم ناقص', 'فشل المحافظ يُصرَّح به'
    n3 = {x['key']: x for x in v2_node.logic('v2MoneyBoard', {'revenues': [], 'escrow': [], 'payouts': payouts}, 'month', NOW)['numbers']}
    assert n3['owed']['text'] == '٦٠ ج' and n3['owed']['note'] == 'طلبات سحب أُرسلت ولم تُحوَّل بعد', 'لسه بيتحمّل ≠ فشل'
    for x in n.values():
        assert not LATIN.search(x['note']) and not LATIN.search(x['text'])


# ═══════════════════════════════════════════ ٣) صفحة الدورة
COURSE = {'id': 'CRS_3E5B3C59', 'slug': 'marketing-basics', 'title': 'أساسيات التسويق القانوني', 'type': 'recorded_paid', 'is_active': True,
          'approval_status': 'approved', 'total_enrolled': 1, 'price_amount': 450, 'price_currency': 'EGP'}
STAT = {'id': 'CRS_3E5B3C59', 'course_id': 'CRS_3E5B3C59', 'slug': 'marketing-basics', 'enrolled': 1, 'paid_count': 1, 'sales_count': 1,
        'sales': [{'currency': 'EGP', 'amount': 450.0}], 'revenue_by_currency': {'EGP': 450.0}, 'completed': 1, 'completed_count': 1, 'completion_pct': 100,
        'stall_lesson': None}


@needs_node
def test_course_page_reads_the_real_bridge_shape():
    for stats in ({'ok': True, 'items': [STAT]}, {'ok': True, 'items': [STAT], 'courses': [STAT]}, {'courses': [dict(STAT, course_id=None)]}):
        st = v2_node.logic('v2s.courses.statFor', stats, COURSE)
        assert st and st['slug'] == 'marketing-basics', stats
        m = v2_node.logic('v2s.courses.pageModel', COURSE, None, st, None, None, {'now': NOW})
        assert m['tiles']['sales'] == {'text': 'بيعة واحدة: ٤٥٠ ج', 'na': False}
        assert m['completion'] == 'يكملها ١٠٠٪ (١ من ١)'
    assert v2_node.logic('v2s.courses.statFor', {'items': [dict(STAT, id='other', course_id='other', slug='other')]}, COURSE) is None


# ═══════════════════════════════════════════ ٤) صفحة الشخص
def _person_S(wallet):
    S = {k: None for k in ('invites', 'experts', 'courses', 'files', 'pending', 'req_trainer', 'req_join', 'req_founding', 'req_identity', 'req_signups')}
    S.update({'users': {'users': [{'id': 'u1', 'email': 'trainer@x.test', 'full_name': 'مدرّب', 'trainer_status': 'approved'}]},
              'payouts_pending': {'payouts': []}, 'payouts_paid': {'payouts': []}, 'enrollments': None, 'wallet': wallet})
    return S


WALLET = {'ok': True, 'email': 'trainer@x.test',
          'balances': [{'currency': 'EGP', 'balance': 157.5, 'withdrawable': 0, 'on_hold': 157.5, 'next_release_at': '2026-11-29T10:00:00+00:00', 'next_release_amount': 157.5},
                       {'currency': 'SAR', 'balance': 40, 'withdrawable': 40, 'on_hold': 0, 'next_release_at': None, 'next_release_amount': 0}],
          'purchases': [{'payment_id': 'pay-1', 'kind': 'course', 'title': 'أساسيات التسويق القانوني', 'amount': 450, 'currency': 'EGP', 'gateway': 'manual',
                         'method': 'instapay', 'status': 'paid', 'paid_at': '2026-11-15T09:00:00+00:00', 'refundable': True, 'refund_block': ''},
                        {'payment_id': 'pay-2', 'kind': 'course', 'title': 'دورة بالبطاقة', 'amount': 20, 'currency': 'USD', 'gateway': 'stripe',
                         'method': '', 'status': 'paid', 'paid_at': '2026-11-10T09:00:00+00:00', 'refundable': False, 'refund_block': 'x'}]}


def test_person_build_carries_wallet_per_currency_and_purchases():
    out = appmod._v2_person_build('trainer@x.test', _person_S(WALLET))
    assert out['sources']['balance'] == 'ok'
    assert [b['currency'] for b in out['money']['balances']] == ['EGP', 'SAR'] and out['money']['balances'][0]['on_hold'] == 157.5
    assert out['purchases'][0]['refundable'] is True and out['purchases'][1]['refundable'] is False
    failed = appmod._v2_person_build('trainer@x.test', _person_S(None))
    assert failed['sources']['balance'] == 'failed' and failed['money']['balances'] is None and failed['purchases'] is None


@needs_node
def test_person_page_wallet_rows_and_purchase_buttons():
    resp = appmod._v2_person_build('trainer@x.test', _person_S(WALLET))
    vm = v2_node.logic('v2Person', resp, NOW, 'trainer@x.test')
    money = next(c for c in vm['cards'] if c['key'] == 'money')
    rows = {r['k']: r['v'] for r in money['rows']}
    assert rows['رصيد المحفظة (ج)'] == '١٥٧٫٥٠ ج، منها ١٥٧٫٥٠ ج تُتاح للسحب يوم ٢٩ نوفمبر ٢٠٢٦'
    assert rows['رصيد المحفظة (ر.س)'] == '٤٠ ر.س'
    learn = next(c for c in vm['cards'] if c['key'] == 'learning')
    p1, p2 = learn['purchases']
    assert p1['refundable'] is True and p1['meta'].startswith('إنستاباي، مدفوعة') and p1['amountText'] == '٤٥٠ ج'
    assert p2['refundable'] is False and p2['note'] == 'الدفع بالبطاقة يُستردّ من لوحة سترايب'
    # المصدر ما وصلش ⇒ «غير متاح بعد» (مش صفر)
    vm2 = v2_node.logic('v2Person', appmod._v2_person_build('trainer@x.test', _person_S(None)), NOW, 'trainer@x.test')
    m2 = next(c for c in vm2['cards'] if c['key'] == 'money')
    assert {'k': 'رصيد المحفظة', 'v': 'غير متاح بعد', 'na': True} in m2['rows']
    one = dict(WALLET, balances=[WALLET['balances'][0]])
    vm3 = v2_node.logic('v2Person', appmod._v2_person_build('trainer@x.test', _person_S(one)), NOW, 'trainer@x.test')
    assert any(r['k'] == 'رصيد المحفظة' and 'تُتاح للسحب' in r['v'] for r in next(c for c in vm3['cards'] if c['key'] == 'money')['rows'])


# ═══════════════════════════════════════════ ٥) مسار الاسترداد
@pytest.mark.parametrize('method,path,body', [('GET', PREVIEW, None), ('POST', REFUND, {'reason': 'س', 'confirmed': True}), ('GET', '/api/v2/money/owed', None)])
def test_admin_only_and_flag_closed(ctx, plat, monkeypatch, method, path, body):
    for role in NON_ADMIN:
        assert _call(ctx, method, path, body, who=role).status_code == 403
    assert _call(ctx, method, path, body, who=None).status_code == 401
    monkeypatch.setenv('DASH_V2_ENABLED', 'false')
    r = _call(ctx, method, path, body)
    assert r.status_code == 404 and r.headers.get('Cache-Control') == 'no-store'
    assert plat.seen == []


def test_refund_needs_confirm_and_reason_before_any_call(ctx, plat):
    assert _call(ctx, 'POST', REFUND, {'reason': 'سبب'}).status_code == 400
    assert _call(ctx, 'POST', REFUND, {'reason': 'سبب', 'confirmed': 'true'}).status_code == 400
    r = _call(ctx, 'POST', REFUND, {'reason': '   ', 'confirmed': True})
    assert r.status_code == 400 and r.get_json()['error'] == 'اكتب سبب الاسترداد'
    assert _call(ctx, 'POST', '/api/v2/purchases/a%20b/refund', {'reason': 'س', 'confirmed': True}).status_code == 404
    assert plat.seen == []


def test_refund_sends_a_whitelisted_body_with_by_from_the_token_and_audits_on_success(ctx, plat):
    plat.replies[('POST', '/api/bridge/purchases/pay-1/refund')] = (200, DONE)
    r = _call(ctx, 'POST', REFUND, {'reason': 'تجربة من المؤسس', 'confirmed': True, 'by': 'someone@else', 'full': False, 'amount': 1})
    assert r.status_code == 200 and r.get_json()['status'] == 'refunded' and r.headers.get('Cache-Control') == 'no-store'
    assert plat.seen[-1]['json'] == {'reason': 'تجربة من المؤسس', 'full': True, 'confirmed': True, 'by': ADMIN_EMAIL}
    with flask_app.app_context():
        a = AuditLog.query.filter_by(action='purchase.refund', target=PID).order_by(AuditLog.id.desc()).first()
        meta = json.loads(a.meta_json)
        assert a.actor_email == ADMIN_EMAIL
        assert meta['seller_amount'] == 157.5 and meta['seller_currency'] == 'EGP' and meta['reason'] == 'تجربة من المؤسس'


def test_platform_refusal_passes_through_and_lost_reply_is_no_reply(ctx, plat):
    card_ar = 'هذه الدفعة تمت بالبطاقة: أعِد المبلغ من لوحة سترايب'
    plat.replies[('POST', '/api/bridge/purchases/pay-1/refund')] = (409, {'detail': card_ar})
    r = _call(ctx, 'POST', REFUND, {'reason': 'س', 'confirmed': True})
    assert r.status_code == 409 and r.get_json()['error'] == card_ar
    plat.replies[('POST', '/api/bridge/purchases/pay-1/refund')] = 'boom'
    r = _call(ctx, 'POST', REFUND, {'reason': 'س', 'confirmed': True})
    assert r.status_code == 502 and r.get_json()['no_reply'] is True
    plat.replies[('POST', '/api/bridge/purchases/pay-1/refund')] = (200, {'ok': True})      # ٢٠٠ من غير «refunded» ⇒ مش «اتردّت»
    r = _call(ctx, 'POST', REFUND, {'reason': 'س', 'confirmed': True})
    assert r.status_code == 502 and r.get_json()['no_reply'] is True
    assert len([c for c in plat.seen if c['method'] == 'POST']) == 3, 'نداء واحد لكل ضغطة ولا إعادة محاولة'


def test_course_refund_is_a_money_type_locked_to_ask_on_the_server(ctx, plat, monkeypatch):
    wt = levels.get_type('course_refund')
    assert wt and wt.lock == 'money' and wt.reversible is False and wt.levels == ('ask',) and wt.default == 'ask'
    assert levels.check_level(wt, 'alone')[1] == 409 and levels.check_level(wt, 'suggest')[1] == 400
    assert not levels.eligible(wt)
    # حتى لو المستوى المحسوب طلع غير «يسألك» (جدول اتعدّل غلط) ⇒ ٤٠٩ قبل أي نداء
    monkeypatch.setattr(levels, 'level_of', lambda ns, w: 'alone')
    r = _call(ctx, 'POST', REFUND, {'reason': 'س', 'confirmed': True})
    assert r.status_code == 409 and plat.seen == []
    # ومن مسار مستويات العقل نفسه ممنوع يتفتح
    monkeypatch.undo()
    monkeypatch.setenv('DASH_V2_ENABLED', 'true')
    r2 = ctx['client'].put('/api/v2/brain/levels/course_refund', json={'level': 'alone'}, headers=ctx['heads']['admin'])
    assert r2.status_code == 409


def test_preview_and_owed_are_thin_reads(ctx, plat):
    plat.replies[('GET', '/api/bridge/purchases/pay-1/refund-preview')] = (200, {'ok': True, 'refundable': True})
    plat.replies[('GET', '/api/bridge/wallets/owed')] = (200, {'ok': True, 'totals': []})
    assert _call(ctx, 'GET', PREVIEW).get_json() == {'ok': True, 'refundable': True}
    assert _call(ctx, 'GET', '/api/v2/money/owed').get_json() == {'ok': True, 'totals': []}
    plat.replies[('GET', '/api/bridge/wallets/owed')] = (401, {'detail': 'unauthorized'})
    assert _call(ctx, 'GET', '/api/v2/money/owed').status_code == 502, 'رفض السرّ مش خروج الأدمن'


# ═══════════════════════════════════════════ ٦) الواجهة: التحديث الصامت + ورقة الاسترداد
def test_money_numbers_refresh_silently_and_after_any_money_decision():
    home, d3 = _read('dashboard-cloud', 'v2-home.js'), _read('dashboard-cloud', 'v2-d3.js')
    refresh_all = home[home.index('V2.refreshAll = function'):home.index('function autoRefresh')]
    assert 'V2D3.refresh(!!force)' in refresh_all
    reload_fn = home[home.index('function reload()'):home.index('function dropRows')]
    assert 'V2D3.refresh(true)' in reload_fn
    assert "D3.refresh = function (force)" in d3 and "['revenues', 'owed', 'income', 'refunds', 'stuck', 'confirmed']" in d3
    body = d3[d3.index('function refreshSrc(k)'):d3.index('function refreshSrc(k)') + 900]
    assert "s.state = 'loading'" not in body, 'التحديث الصامت ما بيدخلش «جارٍ الجلب» (لا وميض)'


def test_refund_sheet_is_two_steps_and_says_exactly_what_happens():
    d3 = _read('dashboard-cloud', 'v2-d3.js')
    for s in ('بنفسك خارج المنصة', 'تُغلق دورة «', 'يُعكس نصيب المدرّب', 'ينقص الدخل في «الفلوس» بمقدار', 'لن تصل رسالة إلى المشتري من المنصة',
              'راجع الاسترداد', 'تأكيد أخير: هذا الاسترداد لا يُتراجع عنه.', 'أكّد الاسترداد', "'/v2/purchases/' + encodeURIComponent(pid) + '/refund'",
              "body: { reason: reason, confirmed: true }", 'إيصالات مؤكَّدة', 'data-a="mrefund"'):
        assert s in d3, s
    d2 = _read('dashboard-cloud', 'v2-d2.js')
    assert 'data-a="prefund"' in d2 and 'V2D3.openRefund(' in d2


@needs_node
def test_purchase_lines_and_visible_copy_are_plain_arabic():
    resp = appmod._v2_person_build('trainer@x.test', _person_S(WALLET))
    vm = v2_node.logic('v2Person', resp, NOW, 'trainer@x.test')
    texts = []
    for c in vm['cards']:
        texts += [r['k'] for r in c.get('rows') or []] + [r['v'] for r in c.get('rows') or []]
        for p in c.get('purchases') or []:
            texts += [p['title'], p['amountText'], p['meta'], p['note']]
    assert not [t for t in texts if LATIN.search(t or '')], texts
    assert not [t for t in texts if re.search(r'·\s*[٠-٩]|[٠-٩]\s*·', t or '')]
