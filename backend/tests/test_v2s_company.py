# -*- coding: utf-8 -*-
"""الجولة الأخيرة · قسم «الشركة ورأس المال» (SPEC-company.md §10).

Run:  cd backend && python3 -B -m pytest -q -p no:cacheprovider tests/test_v2s_company.py

⛔ صفر شبكة حقيقية: أي نداء `requests.request` ممنوع، وبروكسي الزيارات الوحيد بيتختبر ضد `_platform_proxy` مزيّف.
اللي بيثبّته:
  ١. الخادم (pytest): المفتاح مقفول ⇒ ٤٠٤ على كل مسار وكل طريقة بلا كتابة · أدمن بس · `no-store` على كل رد · التحقق · الدفعات (cash/asset/duplicate) ·
     المبلغ المستلم · حساب المستحق · دفع الاشتراك · التجديد · نقل الاشتراكات القديمة · كشوف الحساب المُرسلة · الزيارات · الملخّص · الأهداف · التدقيق ·
     المسارات الموجودة ما اتغيّرتش.
  ٢. المنطق (node): السطور · الشارات · النصوص · الأهداف · الشهور · الشركاء من الخام · الاشتراكات القديمة · إجراء الاتفاق.
  ٣. الملفات: index.html · app.py · Dockerfile · محظورات company.js · خريطة الأقسام.
"""
import datetime
import json
import os
import re
import sys

import jwt
import pytest
from werkzeug.security import generate_password_hash

from app import app as flask_app, db, User, AuditLog, Partner, Asset, CashTransaction, Revenue, Expense, ForecastMonth  # noqa: E402

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(_HERE, 'uiharness'))
import v2_node   # noqa: E402

ROOT = os.path.dirname(os.path.dirname(_HERE))
NON_ADMIN_ROLES = ['employee', 'trainer', 'investor', 'viewer', 'pending']
needs_node = pytest.mark.skipif(not v2_node.NODE, reason='needs node')


def _read(*parts):
    with open(os.path.join(ROOT, *parts), encoding='utf-8') as fh:
        return fh.read()


def _mkuser(email, role):
    u = User.query.filter_by(email=email).first()
    if u:
        u.role = role
        u.dashboard_role = role
        u.is_active = True
        db.session.commit()
        return u
    u = User(email=email, password_hash=generate_password_hash('x', method='pbkdf2:sha256'), name=email.split('@')[0], role=role, dashboard_role=role,
             linked_to_name='', preferred_currency='AUTO', is_active=True)
    db.session.add(u)
    db.session.commit()
    return u


def _bearer(user):
    tok = jwt.encode({'user_id': user.id, 'exp': datetime.datetime.utcnow() + datetime.timedelta(days=1)}, flask_app.config['SECRET_KEY'], algorithm='HS256')
    return {'Authorization': 'Bearer ' + tok}


ADMIN_EMAIL = 'v2co-admin@x.test'


@pytest.fixture(scope='module')
def ctx():
    with flask_app.app_context():
        db.create_all()
        heads = {r: _bearer(_mkuser('v2co-%s@x.test' % r, r)) for r in NON_ADMIN_ROLES}
        heads['admin'] = _bearer(_mkuser(ADMIN_EMAIL, 'admin'))
        yield {'heads': heads, 'client': flask_app.test_client()}


@pytest.fixture(autouse=True)
def clean(ctx, monkeypatch):
    import app as appmod
    import v2_company_routes as co
    monkeypatch.setenv('DASH_V2_ENABLED', 'true')

    def no_net(*a, **k):
        raise AssertionError('نداء شبكة حقيقي ممنوع: %r' % (a[:2],))
    monkeypatch.setattr(appmod.requests, 'request', no_net)
    db.session.remove()
    for m in list(co.M.values()):
        db.session.query(m).delete()
    for m in (Partner, Asset, CashTransaction, Revenue, Expense, ForecastMonth, AuditLog):
        db.session.query(m).delete()
    db.session.commit()
    yield
    db.session.rollback()


def call(ctx, method, path, body=None, role='admin', **kw):
    h = dict(ctx['heads'].get(role, {}))
    c = ctx['client']
    fn = getattr(c, method.lower())
    if method in ('GET',):
        return fn(path, headers=h, **kw)
    return fn(path, headers=h, json=body if body is not None else {}, **kw)


def today():
    return datetime.date.today()


def iso(d):
    return d.isoformat()


def mkpartner(name='أحمد', role='founder', equity=40, egp=100000, usd=0):
    p = Partner(name=name, role=role, equity_percent=equity, profit_share_percent=equity, capital_egp=egp, capital_usd=usd, notes='')
    db.session.add(p)
    db.session.commit()
    return p.id


def contrib(ctx, pid, **over):
    b = {'partner_id': pid, 'kind': 'cash', 'amount': 25000, 'currency': 'EGP', 'date': iso(today()), 'record_cash': True, 'confirmed': True, 'op_id': 'op-%08d' % (len(over) + 12345678)}
    b.update(over)
    return call(ctx, 'POST', '/api/v2/company/contributions', b)


def mkclient(ctx, **over):
    b = {'name': 'مكتب الأمل', 'offer': 'إدارة حملات', 'deal': 'percent', 'percent': 10, 'currency': 'EGP'}
    b.update(over)
    r = call(ctx, 'POST', '/api/v2/company/ad-clients', b)
    assert r.status_code == 201, r.get_data(as_text=True)
    return r.get_json()['item']


# ---------------------------------------------------------------- المسارات كلها (طريقة · مسار · جسم)
ROUTES = [
    ('GET', '/api/v2/company/summary', None),
    ('GET', '/api/v2/company/contributions', None),
    ('POST', '/api/v2/company/contributions', {'partner_id': 1, 'kind': 'cash', 'amount': 5, 'currency': 'EGP', 'confirmed': True, 'op_id': 'op-abcdefgh'}),
    ('DELETE', '/api/v2/company/contributions/1', {'confirmed': True}),
    ('GET', '/api/v2/company/subscriptions', None),
    ('POST', '/api/v2/company/subscriptions', {'name': 'x', 'amount': 5, 'currency': 'EGP', 'cycle': 'monthly'}),
    ('PUT', '/api/v2/company/subscriptions/1', {'status': 'stopped'}),
    ('DELETE', '/api/v2/company/subscriptions/1', {'confirmed': True}),
    ('POST', '/api/v2/company/subscriptions/import', {'asset_ids': [1], 'confirmed': True}),
    ('POST', '/api/v2/company/subscriptions/1/paid', {'confirmed': True}),
    ('GET', '/api/v2/company/agreements', None),
    ('POST', '/api/v2/company/agreements', {'kind': 'sponsor', 'party': 'x'}),
    ('PUT', '/api/v2/company/agreements/1', {'status': 'ended'}),
    ('DELETE', '/api/v2/company/agreements/1', {'confirmed': True}),
    ('POST', '/api/v2/company/agreements/1/renew', {'starts_on': '2027-01-01', 'confirmed': True, 'op_id': 'op-abcdefgh'}),
    ('GET', '/api/v2/company/ad-clients', None),
    ('POST', '/api/v2/company/ad-clients', {'name': 'x', 'deal': 'fixed', 'fixed_amount': 5, 'currency': 'EGP'}),
    ('PUT', '/api/v2/company/ad-clients/1', {'status': 'ended'}),
    ('DELETE', '/api/v2/company/ad-clients/1', {'confirmed': True}),
    ('POST', '/api/v2/company/ad-clients/1/results', {'period': '2026-09'}),
    ('PUT', '/api/v2/company/ad-results/1', {'count': 1}),
    ('DELETE', '/api/v2/company/ad-results/1', {'confirmed': True}),
    ('GET', '/api/v2/company/ad-clients/1/statement', None),
    ('POST', '/api/v2/company/ad-results/sent', {'ids': [1]}),
    ('POST', '/api/v2/company/income', {'from_kind': 'agreement', 'from_id': 1, 'amount': 5, 'currency': 'EGP', 'method': 'cash', 'confirmed': True, 'op_id': 'op-abcdefgh'}),
    ('GET', '/api/v2/company/visits?codes=abc', None),
    ('POST', '/api/v2/company/forecast', {'month': '2027-01'}),
]


def test_switch_off_404_everywhere_and_writes_nothing(ctx, monkeypatch):
    monkeypatch.delenv('DASH_V2_ENABLED', raising=False)
    import v2_company_routes as co
    pid = mkpartner()
    before = {k: db.session.query(m).count() for k, m in co.M.items()}
    before_cash = CashTransaction.query.count()
    for method, path, body in ROUTES:
        r = call(ctx, method, path, body)
        assert r.status_code == 404, (method, path, r.status_code)
        assert r.get_json() == {'error': 'غير متاح'}
    assert {k: db.session.query(m).count() for k, m in co.M.items()} == before
    assert CashTransaction.query.count() == before_cash and pid


def test_unauthenticated_401_and_non_admin_403(ctx):
    c = ctx['client']
    for method, path, body in ROUTES:
        fn = getattr(c, method.lower())
        r = fn(path) if method == 'GET' else fn(path, json=body)
        assert r.status_code == 401, (method, path)
        assert r.headers.get('Cache-Control') == 'no-store'
    for role in NON_ADMIN_ROLES:
        for method, path, body in ROUTES:
            r = call(ctx, method, path, body, role=role)
            assert r.status_code == 403, (role, method, path, r.status_code)
            assert r.headers.get('Cache-Control') == 'no-store'


def test_no_store_on_success_and_error(ctx):
    for path in ('/api/v2/company/summary', '/api/v2/company/contributions', '/api/v2/company/subscriptions', '/api/v2/company/agreements', '/api/v2/company/ad-clients'):
        r = call(ctx, 'GET', path)
        assert r.status_code == 200 and r.headers['Cache-Control'] == 'no-store'
    r = call(ctx, 'POST', '/api/v2/company/subscriptions', {'name': ''})
    assert r.status_code == 422 and r.headers['Cache-Control'] == 'no-store'
    r = call(ctx, 'DELETE', '/api/v2/company/contributions/999', {'confirmed': True})
    assert r.status_code == 404 and r.headers['Cache-Control'] == 'no-store'


# ---------------------------------------------------------------- ٤) التحقق
def test_validation_table(ctx):
    pid = mkpartner()
    base_sub = {'name': 'أدوبي', 'amount': 500, 'currency': 'EGP', 'cycle': 'monthly'}
    bad = [
        ('/api/v2/company/subscriptions', dict(base_sub, currency='SAR')),
        ('/api/v2/company/subscriptions', dict(base_sub, amount=0)),
        ('/api/v2/company/subscriptions', dict(base_sub, amount=-1)),
        ('/api/v2/company/subscriptions', dict(base_sub, amount=100000001)),
        ('/api/v2/company/subscriptions', dict(base_sub, amount='abc')),
        ('/api/v2/company/subscriptions', dict(base_sub, cycle='weekly')),
        ('/api/v2/company/subscriptions', dict(base_sub, cycle='other')),
        ('/api/v2/company/subscriptions', dict(base_sub, renews_on='2026-13-40')),
        ('/api/v2/company/subscriptions', dict(base_sub, name='x' * 121)),
        ('/api/v2/company/agreements', {'kind': 'sponsor', 'party': 'س', 'amount': 5, 'currency': 'JPY'}),
        ('/api/v2/company/agreements', {'kind': 'weird', 'party': 'س'}),
        ('/api/v2/company/agreements', {'kind': 'other', 'party': 'س'}),
        ('/api/v2/company/agreements', {'kind': 'sponsor', 'party': 'س', 'starts_on': '2026-10-10', 'ends_on': '2026-10-01'}),
        ('/api/v2/company/agreements', {'kind': 'sponsor', 'party': 'س', 'ref_code': 'AB'}),
        ('/api/v2/company/agreements', {'kind': 'sponsor', 'party': 'س', 'ref_code': 'Has Space'}),
        ('/api/v2/company/agreements', {'kind': 'sponsor', 'party': 'س' * 161}),
        ('/api/v2/company/ad-clients', {'name': 'x', 'deal': 'percent', 'currency': 'EGP'}),
        ('/api/v2/company/ad-clients', {'name': 'x', 'deal': 'percent', 'percent': 0, 'currency': 'EGP'}),
        ('/api/v2/company/ad-clients', {'name': 'x', 'deal': 'percent', 'percent': 101, 'currency': 'EGP'}),
        ('/api/v2/company/ad-clients', {'name': 'x', 'deal': 'fixed', 'currency': 'EGP'}),
        ('/api/v2/company/ad-clients', {'name': 'x', 'deal': 'fixed_plus_percent', 'percent': 5, 'currency': 'EGP'}),
        ('/api/v2/company/ad-clients', {'name': 'x', 'deal': 'other', 'currency': 'EGP'}),
        ('/api/v2/company/ad-clients', {'name': 'x', 'deal': 'fixed', 'fixed_amount': 5, 'currency': 'XXX'}),
        ('/api/v2/company/forecast', {'month': '2026-13'}),
        ('/api/v2/company/forecast', {'month': 'oct-2026'}),
        ('/api/v2/company/forecast', {'month': '2027-02', 'revenue_egp': -5}),
    ]
    for path, body in bad:
        r = call(ctx, 'POST', path, body)
        assert r.status_code == 422, (path, body, r.status_code, r.get_data(as_text=True))
        assert r.get_json().get('error')
    # contributions: SAR ⇒ 422 · amount bounds
    for over in ({'currency': 'SAR'}, {'amount': 0}, {'amount': 100000001}, {'kind': 'nope'}, {'kind': 'other'}, {'date': '2026-02-31'}):
        r = contrib(ctx, pid, **dict(over, op_id='op-val%05d' % abs(hash(str(over)) % 99999)))
        assert r.status_code == 422, (over, r.get_data(as_text=True))
    # other with its text ⇒ ok
    r = call(ctx, 'POST', '/api/v2/company/subscriptions', dict(base_sub, cycle='other', cycle_other='كل ٣ شهور'))
    assert r.status_code == 201
    r = call(ctx, 'POST', '/api/v2/company/agreements', {'kind': 'other', 'kind_other': 'ترخيص', 'party': 'جهة'})
    assert r.status_code == 201
    # ref_code unique among active agreements and clients
    assert call(ctx, 'POST', '/api/v2/company/agreements', {'kind': 'sponsor', 'party': 'أ', 'ref_code': 'smart-office'}).status_code == 201
    r = call(ctx, 'POST', '/api/v2/company/agreements', {'kind': 'sponsor', 'party': 'ب', 'ref_code': 'smart-office'})
    assert r.status_code == 409
    r = call(ctx, 'POST', '/api/v2/company/ad-clients', {'name': 'x', 'deal': 'fixed', 'fixed_amount': 5, 'currency': 'EGP', 'ref_code': 'smart-office'})
    assert r.status_code == 409


# ---------------------------------------------------------------- ٥) دفعات الشركاء
def test_contribution_needs_confirmation_and_op_id(ctx):
    pid = mkpartner()
    b = {'partner_id': pid, 'kind': 'cash', 'amount': 1000, 'currency': 'EGP', 'record_cash': True}
    assert call(ctx, 'POST', '/api/v2/company/contributions', dict(b, op_id='op-abcdefgh')).status_code == 400
    assert call(ctx, 'POST', '/api/v2/company/contributions', dict(b, confirmed='true', op_id='op-abcdefgh')).status_code == 400
    assert call(ctx, 'POST', '/api/v2/company/contributions', dict(b, confirmed=True)).status_code == 400
    assert call(ctx, 'POST', '/api/v2/company/contributions', dict(b, confirmed=True, op_id='short')).status_code == 400
    assert CashTransaction.query.count() == 0
    r = call(ctx, 'POST', '/api/v2/company/contributions', dict(b, confirmed=True, op_id='op-abcdefgh', partner_id=9999))
    assert r.status_code == 404


def test_contribution_cash_writes_one_ledger_move(ctx):
    pid = mkpartner('سارة')
    r = contrib(ctx, pid, op_id='op-cash0001')
    assert r.status_code == 201
    item = r.get_json()['item']
    assert item['cash_tx_id'] and item['asset_id'] is None
    tx = CashTransaction.query.all()
    assert len(tx) == 1 and tx[0].kind == 'capital_in' and tx[0].amount_egp == 25000 and not tx[0].amount_usd
    assert tx[0].source == 'شريك: سارة' and tx[0].notes == 'co:contribution:%d' % item['id']
    r = contrib(ctx, pid, op_id='op-cash0002', currency='USD', amount=300)
    assert r.status_code == 201
    usd = [t for t in CashTransaction.query.all() if t.amount_usd]
    assert len(usd) == 1 and usd[0].amount_usd == 300 and not usd[0].amount_egp
    # بدون record_cash لا حركة نقد
    r = contrib(ctx, pid, op_id='op-cash0003', record_cash=False)
    assert r.get_json()['item']['cash_tx_id'] is None and CashTransaction.query.count() == 2


def test_contribution_asset_creates_linked_asset_and_total_assets_grows(ctx):
    pid = mkpartner('منى')
    t0 = call(ctx, 'GET', '/api/dashboard').get_json()['financial']['total_assets']
    r = call(ctx, 'POST', '/api/v2/company/contributions', {'partner_id': pid, 'kind': 'asset', 'amount': 26000, 'currency': 'EGP', 'asset_name': 'كاميرا سوني', 'record_asset': True,
                                                             'date': iso(today()), 'confirmed': True, 'op_id': 'op-asset001'})
    assert r.status_code == 201
    item = r.get_json()['item']
    assert item['asset_id'] and item['cash_tx_id'] is None and CashTransaction.query.count() == 0          # المعدات لا تكتب حركة نقد أبدًا
    a = Asset.query.get(item['asset_id'])
    assert a.owner == 'منى' and a.value_egp == 26000 and a.name == 'كاميرا سوني' and a.category == 'equipment' and a.status == 'owned_by_company'
    assert call(ctx, 'GET', '/api/dashboard').get_json()['financial']['total_assets'] == t0 + 26000
    # دولار + record_asset ⇒ ٤٢٢
    r = call(ctx, 'POST', '/api/v2/company/contributions', {'partner_id': pid, 'kind': 'asset', 'amount': 500, 'currency': 'USD', 'asset_name': 'ميكروفون', 'record_asset': True,
                                                             'confirmed': True, 'op_id': 'op-asset002'})
    assert r.status_code == 422 and 'بالجنيه' in r.get_json()['error']
    # دولار بدون record_asset ⇒ دفعة بلا معدة
    r = call(ctx, 'POST', '/api/v2/company/contributions', {'partner_id': pid, 'kind': 'asset', 'amount': 500, 'currency': 'USD', 'asset_name': 'ميكروفون', 'record_asset': False,
                                                             'confirmed': True, 'op_id': 'op-asset003'})
    assert r.status_code == 201 and r.get_json()['item']['asset_id'] is None
    # اسم المعدة مطلوب
    r = call(ctx, 'POST', '/api/v2/company/contributions', {'partner_id': pid, 'kind': 'asset', 'amount': 5, 'currency': 'EGP', 'confirmed': True, 'op_id': 'op-asset004'})
    assert r.status_code == 422


def test_contribution_duplicate_op_id_survives_session_loss(ctx):
    pid = mkpartner()
    import v2_company_routes as co
    assert not [n for n in dir(co) if 'seen' in n.lower() or 'recent' in n.lower()]           # لا نافذة في الذاكرة
    r1 = contrib(ctx, pid, op_id='op-dup00001')
    assert r1.status_code == 201
    db.session.remove()                                                                      # جلسة جديدة تمامًا
    r2 = contrib(ctx, pid, op_id='op-dup00001')
    assert r2.status_code == 200 and r2.get_json()['duplicate'] is True
    assert r2.get_json()['item']['id'] == r1.get_json()['item']['id']
    assert co.M['Contribution'].query.count() == 1 and CashTransaction.query.count() == 1
    # عميل جديد تمامًا (حالة إعادة تشغيل): نفس النتيجة
    c2 = flask_app.test_client()
    r3 = c2.post('/api/v2/company/contributions', headers=ctx['heads']['admin'], json={'partner_id': pid, 'kind': 'cash', 'amount': 25000, 'currency': 'EGP',
                                                                                                          'record_cash': True, 'confirmed': True, 'op_id': 'op-dup00001'})
    assert r3.status_code == 200 and r3.get_json()['duplicate'] is True and CashTransaction.query.count() == 1


def test_contribution_integrity_race_returns_existing(ctx, monkeypatch):
    """سباق: الفحص الأول ما لقاش الصف ثم الفهرس الفريد رفض الإدراج ⇒ إعادة قراءة بـ`op_id` نفس الرد ٢٠٠."""
    pid = mkpartner()
    import v2_company_routes as co
    first = contrib(ctx, pid, op_id='op-race0001').get_json()['item']
    real = co.M['Contribution'].query.filter_by
    calls = {'n': 0}

    class Q(object):
        def __init__(self, inner):
            self.inner = inner

        def first(self):
            calls['n'] += 1
            return None if calls['n'] == 1 else self.inner.first()

    class Wrap(object):
        def filter_by(self, **kw):
            return Q(real(**kw))
    monkeypatch.setattr(co.M['Contribution'], 'query', Wrap())
    r = contrib(ctx, pid, op_id='op-race0001')
    assert r.status_code == 200 and r.get_json()['duplicate'] is True and r.get_json()['item']['id'] == first['id']


def test_contribution_delete_removes_cash_and_asset(ctx):
    pid = mkpartner()
    r = call(ctx, 'POST', '/api/v2/company/contributions', {'partner_id': pid, 'kind': 'asset', 'amount': 8000, 'currency': 'EGP', 'asset_name': 'عدسة', 'record_asset': True,
                                                             'confirmed': True, 'op_id': 'op-del00001'})
    rid = r.get_json()['item']['id']
    r2 = contrib(ctx, pid, op_id='op-del00002')
    cid = r2.get_json()['item']['id']
    assert call(ctx, 'DELETE', '/api/v2/company/contributions/%d' % rid, {}).status_code == 400
    assert Asset.query.count() == 1
    assert call(ctx, 'DELETE', '/api/v2/company/contributions/%d' % rid, {'confirmed': True}).status_code == 200
    assert Asset.query.count() == 0
    assert call(ctx, 'DELETE', '/api/v2/company/contributions/%d' % cid, {'confirmed': True}).status_code == 200
    assert CashTransaction.query.count() == 0
    assert call(ctx, 'DELETE', '/api/v2/company/contributions/%d' % cid, {'confirmed': True}).status_code == 404


# ---------------------------------------------------------------- ٦) المبلغ المستلم
def test_income_agreement_flow_and_currency_columns(ctx):
    ag = call(ctx, 'POST', '/api/v2/company/agreements', {'kind': 'sponsor', 'party': 'مكتب النيل'}).get_json()['item']          # بلا مبلغ ⇒ بلا عملة ⇒ يقبل أي عملة
    body = {'from_kind': 'agreement', 'from_id': ag['id'], 'amount': 12000, 'currency': 'EGP', 'date': iso(today()), 'method': 'bank_transfer', 'op_id': 'op-inc00001'}
    assert call(ctx, 'POST', '/api/v2/company/income', body).status_code == 400
    assert call(ctx, 'POST', '/api/v2/company/income', dict(body, confirmed='yes')).status_code == 400
    assert Revenue.query.count() == 0
    r = call(ctx, 'POST', '/api/v2/company/income', dict(body, confirmed=True))
    assert r.status_code == 201
    rev = Revenue.query.one()
    assert rev.amount_egp == 12000 and rev.source == 'sponsor' and rev.client_name == 'مكتب النيل' and rev.payment_id == 'co:agreement:%d:op-inc00001' % ag['id'] and not rev.needs_fx
    r = call(ctx, 'POST', '/api/v2/company/income', dict(body, confirmed=True))
    assert r.status_code == 200 and r.get_json()['duplicate'] is True and Revenue.query.count() == 1
    # دولار وريال
    call(ctx, 'POST', '/api/v2/company/income', dict(body, confirmed=True, currency='USD', amount=100, op_id='op-inc00002'))
    call(ctx, 'POST', '/api/v2/company/income', dict(body, confirmed=True, currency='SAR', amount=300, op_id='op-inc00003'))
    usd = Revenue.query.filter(Revenue.payment_id.like('%op-inc00002')).one()
    sar = Revenue.query.filter(Revenue.payment_id.like('%op-inc00003')).one()
    assert usd.amount_usd == 100 and not usd.amount_egp and not usd.needs_fx
    assert sar.needs_fx is True and sar.currency == 'SAR' and sar.amount_original == 300 and not sar.amount_egp and not sar.amount_usd
    # received في قائمة الاتفاقات، والحذف ممنوع
    got = call(ctx, 'GET', '/api/v2/company/agreements').get_json()['items'][0]
    cur = {x['currency']: x['amount'] for x in got['received']}
    assert cur == {'EGP': 12000, 'USD': 100, 'SAR': 300}
    r = call(ctx, 'DELETE', '/api/v2/company/agreements/%d' % ag['id'], {'confirmed': True})
    assert r.status_code == 409 and 'مبالغ مستلمة' in r.get_json()['error']
    # اتفاق مجهول ٤٠٤ · طريقة مجهولة ٤٢٢
    assert call(ctx, 'POST', '/api/v2/company/income', dict(body, confirmed=True, from_id=9999, op_id='op-inc00009')).status_code == 404
    assert call(ctx, 'POST', '/api/v2/company/income', dict(body, confirmed=True, method='barter', op_id='op-inc00008')).status_code == 422


def test_income_ad_result_flow(ctx):
    c = mkclient(ctx)
    r = call(ctx, 'POST', '/api/v2/company/ad-clients/%d/results' % c['id'], {'period': '2026-09', 'count': 14, 'income': 48000})
    res = r.get_json()['item']
    assert res['due'] == [{'currency': 'EGP', 'amount': 4800.0}]
    body = {'from_kind': 'ad_result', 'from_id': res['id'], 'amount': 4800, 'currency': 'EGP', 'date': iso(today()), 'method': 'cash', 'confirmed': True, 'op_id': 'op-ad000001'}
    assert call(ctx, 'POST', '/api/v2/company/income', dict(body, amount=4700, op_id='op-ad000002')).status_code == 422          # لا يطابق المستحق
    assert call(ctx, 'POST', '/api/v2/company/income', dict(body, currency='USD', op_id='op-ad000003')).status_code == 422
    assert Revenue.query.count() == 0
    r1 = call(ctx, 'POST', '/api/v2/company/income', body)
    assert r1.status_code == 201
    rev = Revenue.query.one()
    assert rev.source == 'ad_client' and rev.payment_id == 'co:adresult:%d' % res['id'] and 'مكتب الأمل' in rev.description and '2026-09' in rev.description
    r2 = call(ctx, 'POST', '/api/v2/company/income', dict(body, op_id='op-ad000004'))
    assert r2.status_code == 409 and Revenue.query.count() == 1
    # بعد التحصيل: لا تعديل ولا حذف
    assert call(ctx, 'PUT', '/api/v2/company/ad-results/%d' % res['id'], {'count': 1}).status_code == 409
    assert call(ctx, 'DELETE', '/api/v2/company/ad-results/%d' % res['id'], {'confirmed': True}).status_code == 409
    assert call(ctx, 'DELETE', '/api/v2/company/ad-clients/%d' % c['id'], {'confirmed': True}).status_code == 409
    row = call(ctx, 'GET', '/api/v2/company/ad-clients').get_json()['items'][0]['results'][0]
    assert row['collected'] is True and row['collected_on'] == iso(today())


def test_income_ad_result_without_income_has_no_due(ctx):
    c = mkclient(ctx)
    res = call(ctx, 'POST', '/api/v2/company/ad-clients/%d/results' % c['id'], {'period': '2026-08', 'count': 3}).get_json()['item']
    assert res['due'] is None
    body = {'from_kind': 'ad_result', 'from_id': res['id'], 'amount': 5, 'currency': 'EGP', 'method': 'cash', 'confirmed': True, 'op_id': 'op-nodue001'}
    assert call(ctx, 'POST', '/api/v2/company/income', body).status_code == 422 and Revenue.query.count() == 0


# ---------------------------------------------------------------- ٧) حساب المستحق
def test_due_math(ctx):
    def due(client_kw, res_kw):
        c = mkclient(ctx, **client_kw)
        r = call(ctx, 'POST', '/api/v2/company/ad-clients/%d/results' % c['id'], dict({'period': '2026-09'}, **res_kw))
        assert r.status_code == 201, r.get_data(as_text=True)
        return r.get_json()['item']['due']
    assert due({'name': 'a', 'deal': 'percent', 'percent': 10}, {'income': 48000}) == [{'currency': 'EGP', 'amount': 4800.0}]
    assert due({'name': 'b', 'deal': 'fixed_plus_percent', 'fixed_amount': 6000, 'percent': 5}, {'income': 31000}) == [{'currency': 'EGP', 'amount': 7550.0}]
    assert due({'name': 'c', 'deal': 'fixed', 'fixed_amount': 3000}, {}) == [{'currency': 'EGP', 'amount': 3000.0}]
    assert due({'name': 'd', 'deal': 'other', 'deal_other': 'اتفاق خاص'}, {'due_manual': 777}) == [{'currency': 'EGP', 'amount': 777.0}]
    assert due({'name': 'e', 'deal': 'other', 'deal_other': 'اتفاق خاص'}, {}) is None
    assert due({'name': 'f', 'deal': 'percent', 'percent': 10}, {}) is None                       # لا دخل مدخل ⇒ null لا صفر
    assert due({'name': 'g', 'deal': 'percent', 'percent': 10}, {'income': 0}) == [{'currency': 'EGP', 'amount': 0.0}]
    assert due({'name': 'h', 'deal': 'percent', 'percent': 5, 'currency': 'USD'}, {'income': 10.1}) == [{'currency': 'USD', 'amount': 0.51}]    # 0.505 ⇒ نصف لأعلى
    assert due({'name': 'i', 'deal': 'percent', 'percent': 10}, {'income': 0.05}) == [{'currency': 'EGP', 'amount': 0.01}]                     # 0.005 ⇒ 0.01


def test_statement_totals_per_currency(ctx):
    c = mkclient(ctx, deal='fixed', fixed_amount=1000, percent=None, currency='USD')
    ids = []
    for p in ('2026-07', '2026-08', '2026-09'):
        ids.append(call(ctx, 'POST', '/api/v2/company/ad-clients/%d/results' % c['id'], {'period': p}).get_json()['item']['id'])
    call(ctx, 'POST', '/api/v2/company/income', {'from_kind': 'ad_result', 'from_id': ids[0], 'amount': 1000, 'currency': 'USD', 'method': 'cash', 'confirmed': True, 'op_id': 'op-stmt0001'})
    s = call(ctx, 'GET', '/api/v2/company/ad-clients/%d/statement' % c['id']).get_json()
    assert [r['period'] for r in s['rows']] == ['2026-07', '2026-08', '2026-09']
    assert s['totals'] == {'due': [{'currency': 'USD', 'amount': 3000.0}], 'collected': [{'currency': 'USD', 'amount': 1000.0}], 'open': [{'currency': 'USD', 'amount': 2000.0}]}
    s2 = call(ctx, 'GET', '/api/v2/company/ad-clients/%d/statement?from=2026-08&to=2026-08' % c['id']).get_json()
    assert [r['period'] for r in s2['rows']] == ['2026-08']
    assert call(ctx, 'GET', '/api/v2/company/ad-clients/%d/statement?from=bad' % c['id']).status_code == 400


def test_duplicate_period_conflict(ctx):
    c = mkclient(ctx)
    path = '/api/v2/company/ad-clients/%d/results' % c['id']
    assert call(ctx, 'POST', path, {'period': '2026-09', 'income': 100}).status_code == 201
    r = call(ctx, 'POST', path, {'period': '2026-09', 'income': 200})
    assert r.status_code == 409 and 'عدّلها' in r.get_json()['error']
    assert call(ctx, 'POST', path, {'period': '2026-9'}).status_code == 422


# ---------------------------------------------------------------- ٨) دفع اشتراك
def test_subscription_paid_creates_expense_and_advances(ctx):
    s = call(ctx, 'POST', '/api/v2/company/subscriptions', {'name': 'أدوبي', 'amount': 800, 'currency': 'USD', 'cycle': 'monthly', 'renews_on': '2026-01-31', 'paid_by': 'المؤسس'}).get_json()['item']
    path = '/api/v2/company/subscriptions/%d/paid' % s['id']
    assert call(ctx, 'POST', path, {'date': '2026-01-31'}).status_code == 400
    assert Expense.query.count() == 0
    r = call(ctx, 'POST', path, {'date': '2026-01-31', 'confirmed': True, 'op_id': 'op-sub00001'})
    assert r.status_code == 200
    e = Expense.query.one()
    assert e.category == 'tools' and e.amount_usd == 800 and not e.amount_egp and e.is_business is True and e.description == 'اشتراك: أدوبي' and e.paid_by == 'المؤسس'
    assert r.get_json()['item']['renews_on'] == '2026-02-28' and r.get_json()['expense_id'] == e.id
    # نفس الفترة مرتين ⇒ ٤٠٩ (مفتاح الفترة المخزَّن في notes). نرجّع الموعد لنفس الفترة
    call(ctx, 'PUT', '/api/v2/company/subscriptions/%d' % s['id'], {'renews_on': '2026-01-31'})
    r = call(ctx, 'POST', path, {'date': '2026-01-31', 'confirmed': True, 'op_id': 'op-sub00002'})
    assert r.status_code == 409 and 'سُجّل دفع هذه الفترة' in r.get_json()['error'] and Expense.query.count() == 1


def test_subscription_cycles_and_stopped(ctx):
    def mk(cycle, renews, **kw):
        return call(ctx, 'POST', '/api/v2/company/subscriptions', dict({'name': 's-' + cycle + renews, 'amount': 10, 'currency': 'EGP', 'cycle': cycle, 'renews_on': renews}, **kw)).get_json()['item']

    def pay(s, d):
        return call(ctx, 'POST', '/api/v2/company/subscriptions/%d/paid' % s['id'], {'date': d, 'confirmed': True, 'op_id': 'op-cyc%05d' % s['id']})
    assert pay(mk('monthly', '2028-01-31'), '2028-01-31').get_json()['item']['renews_on'] == '2028-02-29'      # سنة كبيسة
    assert pay(mk('yearly', '2026-03-15'), '2026-03-15').get_json()['item']['renews_on'] == '2027-03-15'
    assert pay(mk('yearly', '2028-02-29'), '2028-02-29').get_json()['item']['renews_on'] == '2029-02-28'
    o = mk('other', '2026-05-05', cycle_other='كل ٣ شهور')
    assert pay(o, '2026-05-05').get_json()['item']['renews_on'] == '2026-05-05'
    st = mk('monthly', '2026-06-06')
    call(ctx, 'PUT', '/api/v2/company/subscriptions/%d' % st['id'], {'status': 'stopped'})
    n = Expense.query.count()
    r = pay(st, '2026-06-06')
    assert r.status_code == 409 and Expense.query.count() == n


# ---------------------------------------------------------------- ٩) التجديد
def test_renew_two_stage_idempotent(ctx):
    a = call(ctx, 'POST', '/api/v2/company/agreements', {'kind': 'sponsor', 'party': 'مكتب النيل', 'amount': 5000, 'currency': 'EGP', 'starts_on': '2026-01-01', 'ends_on': '2026-12-31',
                                                         'ref_code': 'nile-office'}).get_json()['item']
    path = '/api/v2/company/agreements/%d/renew' % a['id']
    body = {'starts_on': '2027-01-01', 'ends_on': '2027-12-31', 'amount': 6000, 'currency': 'EGP'}
    assert call(ctx, 'POST', path, body).status_code == 400
    assert call(ctx, 'POST', path, dict(body, confirmed=True)).status_code == 400
    assert call(ctx, 'POST', path, dict(body, op_id='op-ren00001')).status_code == 400
    items = call(ctx, 'GET', '/api/v2/company/agreements').get_json()['items']
    assert len(items) == 1 and items[0]['status'] == 'active'
    r = call(ctx, 'POST', path, dict(body, confirmed=True, op_id='op-ren00001'))
    assert r.status_code == 200
    j = r.get_json()
    assert j['item']['renewed_from'] == a['id'] and j['item']['status'] == 'active' and j['item']['amount'] == 6000 and j['item']['starts_on'] == '2027-01-01'
    assert j['item']['ref_code'] == 'nile-office' and j['previous']['status'] == 'ended'
    r2 = call(ctx, 'POST', path, dict(body, confirmed=True, op_id='op-ren00001'))
    assert r2.status_code == 200 and r2.get_json()['duplicate'] is True
    assert len(call(ctx, 'GET', '/api/v2/company/agreements').get_json()['items']) == 2


def test_agreement_end_and_delete_rules(ctx):
    a = call(ctx, 'POST', '/api/v2/company/agreements', {'kind': 'book', 'party': 'دار النشر'}).get_json()['item']
    r = call(ctx, 'PUT', '/api/v2/company/agreements/%d' % a['id'], {'status': 'ended'})
    assert r.status_code == 200 and r.get_json()['item']['status'] == 'ended'
    assert call(ctx, 'DELETE', '/api/v2/company/agreements/%d' % a['id'], {}).status_code == 400
    assert call(ctx, 'DELETE', '/api/v2/company/agreements/%d' % a['id'], {'confirmed': True}).status_code == 200


# ---------------------------------------------------------------- ٩ب) نقل الاشتراكات القديمة
def test_import_legacy_subscriptions(ctx):
    ids = {}
    for key, cat, rent in (('sub', 'subscription', 1800), ('soft', 'software', 500), ('cam', 'camera', 0), ('tool0', 'tool', 0)):
        a = Asset(name='بند-' + key, category=cat, owner='الشركة', value_egp=0, monthly_rent_egp=rent, status='leased_to_company', notes='ملاحظة ' + key)
        db.session.add(a)
        db.session.commit()
        ids[key] = a.id
    path = '/api/v2/company/subscriptions/import'
    assert call(ctx, 'POST', path, {'asset_ids': [ids['sub'], ids['soft']]}).status_code == 400
    assert call(ctx, 'POST', path, {'asset_ids': [ids['sub'], ids['soft']], 'confirmed': 'true'}).status_code == 400
    assert Asset.query.count() == 4
    r = call(ctx, 'POST', path, {'asset_ids': [ids['sub'], ids['soft'], ids['cam']], 'confirmed': True})        # الكاميرا ليست اشتراكًا
    assert r.status_code == 422 and 'ليس اشتراكًا قديمًا' in r.get_json()['error'] and Asset.query.count() == 4
    assert call(ctx, 'POST', path, {'asset_ids': [ids['tool0']], 'confirmed': True}).status_code == 422             # إيجار صفر
    r = call(ctx, 'POST', path, {'asset_ids': [ids['sub'], ids['soft']], 'confirmed': True})
    assert r.status_code == 200 and r.get_json()['moved'] == 2
    subs = call(ctx, 'GET', '/api/v2/company/subscriptions').get_json()['items']
    assert sorted((s['name'], s['amount'], s['currency'], s['cycle'], s['renews_on'], s['status']) for s in subs) == [
        ('بند-soft', 500, 'EGP', 'monthly', None, 'active'), ('بند-sub', 1800, 'EGP', 'monthly', None, 'active')]
    assert sorted(a.name for a in Asset.query.all()) == ['بند-cam', 'بند-tool0']
    assert call(ctx, 'POST', path, {'asset_ids': [ids['sub'], ids['soft']], 'confirmed': True}).status_code == 422       # الإعادة بعد النجاح
    assert len(call(ctx, 'GET', '/api/v2/company/subscriptions').get_json()['items']) == 2
    # التدقيق
    rows = AuditLog.query.filter_by(action='company.subscription.import').all()
    assert len(rows) == 1 and json.loads(rows[0].meta_json)['count'] == 2


# ---------------------------------------------------------------- ٩ج) كشوف الحساب المُرسلة
def test_statements_sent_bulk(ctx):
    c = mkclient(ctx)
    a = call(ctx, 'POST', '/api/v2/company/ad-clients/%d/results' % c['id'], {'period': '2026-08', 'income': 1000}).get_json()['item']['id']
    b = call(ctx, 'POST', '/api/v2/company/ad-clients/%d/results' % c['id'], {'period': '2026-09', 'income': 2000}).get_json()['item']['id']
    r = call(ctx, 'POST', '/api/v2/company/ad-results/sent', {'ids': [a, 999999]})
    assert r.status_code == 404
    got = {x['id']: x for x in call(ctx, 'GET', '/api/v2/company/ad-clients').get_json()['items'][0]['results']}
    assert got[a]['sent_at'] is None and got[b]['sent_at'] is None
    assert AuditLog.query.filter_by(action='company.adresult.sent').count() == 0
    r = call(ctx, 'POST', '/api/v2/company/ad-results/sent', {'ids': [a, b]})
    assert r.status_code == 200
    got = {x['id']: x for x in call(ctx, 'GET', '/api/v2/company/ad-clients').get_json()['items'][0]['results']}
    assert got[a]['sent_at'] and got[b]['sent_at']
    rows = AuditLog.query.filter_by(action='company.adresult.sent').all()
    assert len(rows) == 2 and {x.actor_email for x in rows} == {ADMIN_EMAIL}
    first = got[a]['sent_at']
    call(ctx, 'POST', '/api/v2/company/ad-results/sent', {'ids': [a]})                                        # المُرسل يبقى كما هو
    again = {x['id']: x for x in call(ctx, 'GET', '/api/v2/company/ad-clients').get_json()['items'][0]['results']}
    assert again[a]['sent_at'] == first and AuditLog.query.filter_by(action='company.adresult.sent').count() == 2
    assert call(ctx, 'POST', '/api/v2/company/ad-results/sent', {'ids': []}).status_code == 422
    assert call(ctx, 'POST', '/api/v2/company/ad-results/sent', {'ids': ['x']}).status_code == 422


# ---------------------------------------------------------------- ٩د) الزيارات
def test_visits_proxy(ctx, monkeypatch):
    import app as appmod
    from flask import jsonify
    seen = []
    mode = {'v': 404}

    def stub(method, path, params=None, json_body=None, timeout=12):
        seen.append((method, path, dict(params or {})))
        if mode['v'] == 404:
            return jsonify({'detail': 'Not Found'}), 404
        if mode['v'] == 200:
            return jsonify({'ok': True, 'items': [{'code': 'smart-office', 'tracked': True, 'visits': 180, 'signups': 12}, {'code': 'ghost-code', 'tracked': False}]})
        return jsonify({'error': 'boom'}), 500
    monkeypatch.setattr(appmod, '_platform_proxy', stub)
    q = '/api/v2/company/visits?codes=smart-office,ghost-code&from=2026-10-01&to=2026-10-30'
    r = call(ctx, 'GET', q)
    assert r.status_code == 200 and r.get_json() == {'enabled': False, 'items': []}
    assert seen[0] == ('GET', '/api/bridge/visits/by-ref', {'codes': 'smart-office,ghost-code', 'from': '2026-10-01', 'to': '2026-10-30'})
    mode['v'] = 200
    j = call(ctx, 'GET', q).get_json()
    assert j['enabled'] is True and j['items'][0]['visits'] == 180 and j['items'][1]['tracked'] is False
    mode['v'] = 500
    r = call(ctx, 'GET', q)
    assert r.status_code == 502 and r.get_json() != {'enabled': False, 'items': []} and 'الزيارات' in r.get_json()['error']
    n = len(seen)
    assert call(ctx, 'GET', '/api/v2/company/visits').get_json() == {'enabled': None, 'items': []} and len(seen) == n         # بلا أكواد ⇒ بلا نداء
    assert call(ctx, 'GET', '/api/v2/company/visits?codes=BAD CODE').status_code == 400
    assert call(ctx, 'GET', '/api/v2/company/visits?codes=' + ','.join('c%02d-x' % i for i in range(51))).status_code == 400


# ---------------------------------------------------------------- ١٠) الملخّص
def _month_back(d, n):
    y, m = d.year, d.month - n
    while m <= 0:
        y, m = y - 1, m + 12
    return datetime.date(y, m, 15)


def test_summary_blocks(ctx):
    pid = mkpartner('أحمد', 'founder', 40, 100000, 4500)
    pid2 = mkpartner('سارة', 'cofounder', 35, 50000, 0)
    mkpartner('غير موزّع', 'partner', 25, 0, 0)
    contrib(ctx, pid, op_id='op-sum00001', amount=75000)
    contrib(ctx, pid, op_id='op-sum00002', amount=300, currency='USD')
    contrib(ctx, pid2, op_id='op-sum00003', amount=50000)
    db.session.add_all([Asset(name='كاميرا', category='camera', value_egp=26000, monthly_rent_egp=0), Asset(name='لابتوب', category='computers', value_egp=14000, monthly_rent_egp=500)])
    db.session.commit()
    call(ctx, 'POST', '/api/v2/company/subscriptions', {'name': 'أدوبي', 'amount': 3400, 'currency': 'EGP', 'cycle': 'monthly', 'renews_on': iso(today() + datetime.timedelta(days=5))})
    call(ctx, 'POST', '/api/v2/company/subscriptions', {'name': 'دومين', 'amount': 20, 'currency': 'USD', 'cycle': 'yearly', 'renews_on': iso(today() - datetime.timedelta(days=2))})
    call(ctx, 'POST', '/api/v2/company/subscriptions', {'name': 'قديم', 'amount': 9, 'currency': 'USD', 'cycle': 'monthly', 'status': 'stopped'})
    call(ctx, 'POST', '/api/v2/company/agreements', {'kind': 'sponsor', 'party': 'قريب', 'ends_on': iso(today() + datetime.timedelta(days=12))})
    call(ctx, 'POST', '/api/v2/company/agreements', {'kind': 'sponsor', 'party': 'بعيد', 'ends_on': iso(today() + datetime.timedelta(days=90))})
    call(ctx, 'POST', '/api/v2/company/agreements', {'kind': 'sponsor', 'party': 'حد 45', 'ends_on': iso(today() + datetime.timedelta(days=45))})
    call(ctx, 'POST', '/api/v2/company/agreements', {'kind': 'sponsor', 'party': 'منتهٍ', 'status': 'ended', 'ends_on': iso(today() + datetime.timedelta(days=3))})
    cl = mkclient(ctx)
    call(ctx, 'POST', '/api/v2/company/ad-clients/%d/results' % cl['id'], {'period': '2026-09', 'count': 14, 'income': 48000})
    s = call(ctx, 'GET', '/api/v2/company/summary').get_json()
    P = s['partners']
    assert P['equity_total'] == 100 and P['any_contribution'] is True
    rows = {r['name']: r for r in P['rows']}
    assert rows['أحمد']['agreed'] == [{'currency': 'EGP', 'amount': 100000}, {'currency': 'USD', 'amount': 4500}]
    assert rows['أحمد']['paid'] == [{'currency': 'EGP', 'amount': 75000}, {'currency': 'USD', 'amount': 300}] and rows['أحمد']['contributions'] == 2
    assert rows['سارة']['paid'] == [{'currency': 'EGP', 'amount': 50000}] and rows['غير موزّع']['reserve'] is True and rows['غير موزّع']['contributions'] == 0
    assert P['agreed_total'] == [{'currency': 'EGP', 'amount': 150000}, {'currency': 'USD', 'amount': 4500}]
    assert P['paid_total'] == [{'currency': 'EGP', 'amount': 125000}, {'currency': 'USD', 'amount': 300}]
    assert s['assets'] == {'count': 2, 'value_egp': 40000, 'rent_egp_monthly': 500}
    assert len(s['capital_moves']) == 3 and s['capital_moves'][0]['currency'] in ('EGP', 'USD')
    sb = s['subscriptions']
    assert sb['active'] == 2 and sb['monthly'] == [{'currency': 'EGP', 'amount': 3400}] and sb['yearly'] == [{'currency': 'USD', 'amount': 20}]
    assert [n['name'] for n in sb['next']] == ['دومين', 'أدوبي']                                       # المتأخر أولًا
    assert [a['party'] for a in s['agreements']['ending']] == ['قريب', 'حد 45'] and s['agreements']['active'] == 3
    ac = s['ad_clients']
    assert ac['active'] == 1 and ac['unsent'] == 1 and ac['due_open'] == [{'currency': 'EGP', 'amount': 4800}] and ac['due_unsent'] == [{'currency': 'EGP', 'amount': 4800}]
    assert ac['latest'] == [{'client_id': cl['id'], 'name': 'مكتب الأمل', 'period': '2026-09', 'count': 14, 'income': 48000, 'due': [{'currency': 'EGP', 'amount': 4800}]}]


def test_summary_reserve_detection_by_role_and_name(ctx):
    mkpartner('احتياطي', 'pool', 10, 0, 0)
    mkpartner('Unallocated / Option Pool', 'partner', 5, 0, 0)
    mkpartner('عادي', 'founder', 85, 0, 0)
    rows = {r['name']: r for r in call(ctx, 'GET', '/api/v2/company/summary').get_json()['partners']['rows']}
    assert rows['احتياطي']['reserve'] and rows['Unallocated / Option Pool']['reserve'] and not rows['عادي']['reserve']


def test_summary_money_covered_since(ctx):
    t = today()
    m1, m2, m3 = _month_back(t, 1), _month_back(t, 2), _month_back(t, 3)

    def put(d, rev, exp):
        if rev:
            db.session.add(Revenue(date=d, source='course', amount_egp=rev, description='r'))
        if exp:
            db.session.add(Expense(date=d, category='tools', amount_egp=exp, is_business=True, description='e'))
    put(m3, 1000, 3000)
    put(m2, 5000, 4000)
    put(m1, 6000, 3400)
    put(t, 100, 100)                                                       # الشهر الحالي لا يُعدّ
    db.session.commit()
    mo = call(ctx, 'GET', '/api/v2/company/summary').get_json()['money']
    assert mo['month'] == m1.strftime('%Y-%m') and mo['revenue'] == 6000 and mo['expenses'] == 3400 and mo['covered_since'] == m2.strftime('%Y-%m')
    # الشهر نفسه غير مغطّى ⇒ null
    Revenue.query.delete()
    db.session.commit()
    put(m1, 1000, 3400)
    db.session.commit()
    assert call(ctx, 'GET', '/api/v2/company/summary').get_json()['money']['covered_since'] is None


def test_summary_failed_block_is_null_others_intact(ctx, monkeypatch):
    mkpartner()
    db.session.add(Asset(name='x', category='camera', value_egp=100))
    db.session.commit()

    class Dead(object):
        def all(self):
            raise RuntimeError('boom')
    monkeypatch.setattr(Asset, 'query', Dead(), raising=False)             # كتلة المعدات فقط هي اللي بتقرأ `Asset.query.all()` في الملخّص
    r = call(ctx, 'GET', '/api/v2/company/summary')
    assert r.status_code == 200
    j = r.get_json()
    assert j['assets'] is None
    assert j['partners'] is not None and j['partners']['equity_total'] == 40
    assert j['subscriptions'] == {'active': 0, 'monthly': [], 'yearly': [], 'next': []} and j['agreements'] == {'active': 0, 'ending': []}
    assert j['ad_clients'] == {'active': 0, 'unsent': 0, 'due_open': [], 'due_unsent': [], 'latest': []} and j['capital_moves'] == []


# ---------------------------------------------------------------- ١١) الأهداف
def test_forecast_post(ctx):
    r = call(ctx, 'POST', '/api/v2/company/forecast', {'month': '2027-01', 'revenue_egp': 50000, 'marketing_egp': 8000, 'target_courses': 4, 'target_students': 120, 'notes': 'هدف'})
    assert r.status_code == 201
    row = ForecastMonth.query.get(r.get_json()['id'])
    assert row.month == '2027-01' and row.revenue_egp == 50000 and row.target_courses == 4 and row.target_students == 120 and row.cogs_egp == 0
    assert call(ctx, 'POST', '/api/v2/company/forecast', {'month': '2027-01'}).status_code == 409
    assert call(ctx, 'POST', '/api/v2/company/forecast', {'month': '2027-1'}).status_code == 422
    assert call(ctx, 'POST', '/api/v2/company/forecast', {'month': '2027-02', 'target_courses': 1.5}).status_code == 422
    assert ForecastMonth.query.count() == 1
    # التعديل على المسار الموجود
    r = call(ctx, 'PUT', '/api/forecast/%d' % row.id, {'revenue_egp': 60000})
    assert r.status_code == 200 and ForecastMonth.query.get(row.id).revenue_egp == 60000


# ---------------------------------------------------------------- ١٢) التدقيق
def test_audit_rows_on_success_only_with_actor(ctx):
    pid = mkpartner()
    before = AuditLog.query.count()
    assert contrib(ctx, pid, op_id='op-aud00001', currency='SAR').status_code == 422
    assert call(ctx, 'POST', '/api/v2/company/subscriptions', {'name': ''}).status_code == 422
    assert call(ctx, 'POST', '/api/v2/company/agreements', {'kind': 'x', 'party': 'y'}).status_code == 422
    assert AuditLog.query.count() == before
    assert contrib(ctx, pid, op_id='op-aud00002').status_code == 201
    s = call(ctx, 'POST', '/api/v2/company/subscriptions', {'name': 'أ', 'amount': 5, 'currency': 'EGP', 'cycle': 'monthly'}).get_json()['item']
    call(ctx, 'PUT', '/api/v2/company/subscriptions/%d' % s['id'], {'status': 'stopped'})
    a = call(ctx, 'POST', '/api/v2/company/agreements', {'kind': 'content', 'party': 'ب'}).get_json()['item']
    call(ctx, 'POST', '/api/v2/company/income', {'from_kind': 'agreement', 'from_id': a['id'], 'amount': 5, 'currency': 'EGP', 'method': 'cash', 'confirmed': True, 'op_id': 'op-aud00003'})
    call(ctx, 'POST', '/api/v2/company/forecast', {'month': '2027-05'})
    acts = [r.action for r in AuditLog.query.order_by(AuditLog.id).all()]
    assert acts == ['company.contribution.add', 'company.subscription.add', 'company.subscription.update', 'company.agreement.add', 'company.income.add', 'company.forecast.add']
    assert {r.actor_email for r in AuditLog.query.all()} == {ADMIN_EMAIL}


# ---------------------------------------------------------------- ١٣) المسارات الموجودة ما اتغيّرتش
def test_existing_endpoints_untouched(ctx):
    mkpartner()
    db.session.add(Asset(name='x', category='camera', value_egp=1))
    db.session.add(ForecastMonth(month='2027-03', revenue_egp=1))
    db.session.commit()
    assert set(call(ctx, 'GET', '/api/partners').get_json()[0]) == {'id', 'name', 'role', 'equity_percent', 'profit_share_percent', 'capital_egp', 'capital_usd', 'total_capital_egp', 'notes'}
    assert set(call(ctx, 'GET', '/api/assets').get_json()[0]) == {'id', 'name', 'category', 'owner', 'value_egp', 'monthly_rent_egp', 'status', 'notes'}
    assert {'id', 'month', 'revenue_egp', 'cogs_egp', 'marketing_egp', 'payroll_egp', 'rent_egp', 'other_sga_egp', 'total_expenses', 'ebitda', 'target_courses', 'target_students', 'notes'} == set(call(ctx, 'GET', '/api/forecast').get_json()[0])
    assert call(ctx, 'GET', '/api/settings').status_code == 200


# ---------------------------------------------------------------- عملاء الإعلانات وحقولهم
def test_ad_client_crud_and_results_order(ctx):
    c = mkclient(ctx, ledger_kind='course', ledger_owner_id='crs-1')
    assert c['count_label'] == 'عملاء جاؤوا من الحملة' and c['ledger_kind'] == 'course'
    r = call(ctx, 'PUT', '/api/v2/company/ad-clients/%d' % c['id'], {'deal': 'fixed_plus_percent', 'fixed_amount': 6000, 'percent': 5})
    assert r.status_code == 200 and r.get_json()['item']['deal'] == 'fixed_plus_percent'
    for p in ('2026-07', '2026-09', '2026-08'):
        call(ctx, 'POST', '/api/v2/company/ad-clients/%d/results' % c['id'], {'period': p, 'income': 1000})
    res = call(ctx, 'GET', '/api/v2/company/ad-clients').get_json()['items'][0]['results']
    assert [x['period'] for x in res] == ['2026-09', '2026-08', '2026-07']
    assert res[0]['due'] == [{'currency': 'EGP', 'amount': 6050.0}]
    # تعديل نتيجة لم تُحصَّل
    r = call(ctx, 'PUT', '/api/v2/company/ad-results/%d' % res[0]['id'], {'income': 2000})
    assert r.status_code == 200 and r.get_json()['item']['due'] == [{'currency': 'EGP', 'amount': 6100.0}]
    assert call(ctx, 'DELETE', '/api/v2/company/ad-results/%d' % res[0]['id'], {}).status_code == 400
    assert call(ctx, 'DELETE', '/api/v2/company/ad-results/%d' % res[0]['id'], {'confirmed': True}).status_code == 200
    assert call(ctx, 'DELETE', '/api/v2/company/ad-clients/%d' % c['id'], {'confirmed': True}).status_code == 200
    assert call(ctx, 'GET', '/api/v2/company/ad-clients').get_json()['items'] == []


def test_ad_client_put_without_ledger_keys_keeps_the_link(ctx):
    c = mkclient(ctx, ledger_kind='course', ledger_owner_id='crs-1')
    r = call(ctx, 'PUT', '/api/v2/company/ad-clients/%d' % c['id'], {'name': 'اسم جديد', 'note': 'ملاحظة'})
    it = r.get_json()['item']
    assert r.status_code == 200 and it['ledger_kind'] == 'course' and it['ledger_owner_id'] == 'crs-1' and it['name'] == 'اسم جديد'
    # مسح الربط صراحةً ما زال ممكنًا
    r = call(ctx, 'PUT', '/api/v2/company/ad-clients/%d' % c['id'], {'ledger_kind': None, 'ledger_owner_id': None})
    assert r.get_json()['item']['ledger_kind'] is None


def test_ad_client_terms_locked_after_sent_or_collected(ctx):
    c = mkclient(ctx)
    cid = c['id']
    res = call(ctx, 'POST', '/api/v2/company/ad-clients/%d/results' % cid, {'period': '2026-09', 'count': 14, 'income': 48000}).get_json()['item']
    # قبل أي إرسال: الشروط تتغير
    assert call(ctx, 'PUT', '/api/v2/company/ad-clients/%d' % cid, {'percent': 12}).status_code == 200
    assert call(ctx, 'POST', '/api/v2/company/ad-results/sent', {'ids': [res['id']]}).status_code == 200
    # بعد الإرسال: الشروط ثابتة (٤٠٩) لكن الاسم والملاحظة والحالة تتعدّل
    for body in ({'percent': 20}, {'currency': 'USD'}, {'deal': 'fixed', 'fixed_amount': 100}):
        r = call(ctx, 'PUT', '/api/v2/company/ad-clients/%d' % cid, body)
        assert r.status_code == 409, body
    assert call(ctx, 'PUT', '/api/v2/company/ad-clients/%d' % cid, {'percent': 12, 'name': 'اسم', 'status': 'ended'}).status_code == 200
    got = call(ctx, 'GET', '/api/v2/company/ad-clients').get_json()['items'][0]
    assert got['percent'] == 12 and got['results'][0]['due'] == [{'currency': 'EGP', 'amount': 5760.0}]


def test_income_agreement_currency_must_match(ctx):
    ag = call(ctx, 'POST', '/api/v2/company/agreements', {'kind': 'sponsor', 'party': 'راعٍ', 'amount': 500, 'currency': 'USD'}).get_json()['item']
    body = {'from_kind': 'agreement', 'from_id': ag['id'], 'amount': 500, 'currency': 'EGP', 'date': iso(today()), 'method': 'cash', 'confirmed': True, 'op_id': 'op-cur00001'}
    assert call(ctx, 'POST', '/api/v2/company/income', body).status_code == 422 and Revenue.query.count() == 0
    assert call(ctx, 'POST', '/api/v2/company/income', dict(body, currency='USD')).status_code == 201


def test_summary_due_unsent_only_counts_active_unsent(ctx):
    a = mkclient(ctx, name='نشط')
    b = mkclient(ctx, name='منتهٍ')
    ra = call(ctx, 'POST', '/api/v2/company/ad-clients/%d/results' % a['id'], {'period': '2026-09', 'income': 1000}).get_json()['item']
    call(ctx, 'POST', '/api/v2/company/ad-clients/%d/results' % b['id'], {'period': '2026-09', 'income': 5000})
    call(ctx, 'PUT', '/api/v2/company/ad-clients/%d' % b['id'], {'status': 'ended'})
    ac = call(ctx, 'GET', '/api/v2/company/summary').get_json()['ad_clients']
    assert ac['unsent'] == 1 and ac['due_unsent'] == [{'currency': 'EGP', 'amount': 100.0}] and ac['due_open'] == [{'currency': 'EGP', 'amount': 600.0}]
    call(ctx, 'POST', '/api/v2/company/ad-results/sent', {'ids': [ra['id']]})
    ac = call(ctx, 'GET', '/api/v2/company/summary').get_json()['ad_clients']
    assert ac['unsent'] == 0 and ac['due_unsent'] == []


# ================================================================ المنطق (node)
NOW = int(datetime.datetime(2026, 10, 30, 10, 0, tzinfo=datetime.timezone.utc).timestamp() * 1000)


def _lg(fn, *args):
    return v2_node.logic('co.' + fn, *args)


def _all_text(lines):
    return ' | '.join(l['text'] for l in lines)


@needs_node
def test_brain_lines_each_from_its_facts():
    mo = {'month': '2026-09', 'revenue': 6000, 'expenses': 3400, 'covered_since': '2026-07'}
    s = {'money': mo}
    ls = _lg('brain', s, NOW)
    assert ls[0]['text'] == 'مصروف سبتمبر ٢٠٢٦ كان ٣٬٤٠٠ جنيه، والدخل غطّاه منذ يوليو ٢٠٢٦.' and ls[0]['act'] == {'section': 'money', 'tab': 'overview'}
    s['money'] = dict(mo, covered_since='2026-09')
    assert _lg('brain', s, NOW)[0]['text'] == 'مصروف سبتمبر ٢٠٢٦ كان ٣٬٤٠٠ جنيه، والدخل غطّاه.'
    s['money'] = dict(mo, revenue=1700, covered_since=None)
    assert _lg('brain', s, NOW)[0]['text'] == 'مصروف سبتمبر ٢٦٠٢٦ كان'.replace('٢٦٠٢٦', '٢٠٢٦') + ' ٣٬٤٠٠ جنيه، والدخل غطّى ٥٠٪ منه.'
    s['money'] = dict(mo, expenses=0)
    assert _lg('brain', s, NOW) == []
    # الاتفاق: ينتهي بعد ١٢ يومًا وجلب ٨٠ زيارة · ينتهي اليوم
    ag = {'agreements': {'ending': [{'id': 7, 'party': 'مكتب النيل', 'ends_on': '2026-11-11', 'ref_code': 'nile'}, {'id': 8, 'party': 'آخر', 'ends_on': '2026-12-01'}]}}
    ls = _lg('brain', ag, NOW, {'visits': {'nile': 80}})
    assert ls[0]['text'] == 'اتفاق «مكتب النيل» ينتهي بعد ١٢ يومًا، وجلب ٨٠ زيارة.' and ls[0]['act'] == {'tab': 'deals', 'id': 7}
    assert _lg('brain', ag, NOW)[0]['text'] == 'اتفاق «مكتب النيل» ينتهي بعد ١٢ يومًا.'
    assert _lg('brain', {'agreements': {'ending': [{'id': 7, 'party': 'س', 'ends_on': '2026-10-30'}]}}, NOW)[0]['text'] == 'اتفاق «س» ينتهي اليوم.'
    assert _lg('brain', {'agreements': {'ending': [{'id': 7, 'party': 'س', 'ends_on': '2026-12-20'}]}}, NOW) == []             # أبعد من ٣٠ يومًا
    # الاشتراك: يتجدد بعد ٥ أيام · فات منذ يومين
    sub = {'subscriptions': {'next': [{'id': 3, 'name': 'أدوبي', 'renews_on': '2026-11-04', 'amount': 3400, 'currency': 'EGP'}]}}
    ls = _lg('brain', sub, NOW)
    assert ls[0]['text'] == 'اشتراك «أدوبي» يتجدد بعد ٥ أيام بمبلغ ٣٬٤٠٠ جنيه.' and ls[0]['act'] == {'tab': 'assets', 'id': 3, 'do': 'paid'}
    sub['subscriptions']['next'][0]['renews_on'] = '2026-10-28'
    assert _lg('brain', sub, NOW)[0]['text'] == 'فات موعد تجديد «أدوبي» منذ يومين.'
    sub['subscriptions']['next'][0]['renews_on'] = '2026-11-29'
    assert _lg('brain', sub, NOW) == []
    # الاتفاق يسبق الاشتراك (٢ ثم ٢ب بديل)
    both = dict(ag, **{'subscriptions': {'next': [{'id': 3, 'name': 'أدوبي', 'renews_on': '2026-11-02', 'amount': 5, 'currency': 'EGP'}]}})
    assert [l['key'] for l in _lg('brain', both, NOW)] == ['agreement']
    # الشركاء
    rows = [{'id': 1, 'name': 'أ', 'reserve': False, 'agreed': [{'currency': 'EGP', 'amount': 100000}], 'paid': [{'currency': 'EGP', 'amount': 75000}], 'contributions': 1},
            {'id': 2, 'name': 'ب', 'reserve': False, 'agreed': [{'currency': 'EGP', 'amount': 50000}], 'paid': [{'currency': 'EGP', 'amount': 50000}], 'contributions': 1}]
    P = {'partners': {'rows': rows, 'equity_total': 100, 'any_contribution': True}}
    assert _lg('brain', P, NOW)[0]['text'] == 'شريك واحد باقٍ عليه ٢٥٬٠٠٠ جنيه من حصته.'
    rows[1] = dict(rows[1], paid=[{'currency': 'EGP', 'amount': 20000}])
    assert _lg('brain', P, NOW)[0]['text'] == 'شريكان باقٍ عليهما ٥٥٬٠٠٠ جنيه من حصتيهما.'
    rows.append(dict(rows[0], id=3, name='ج'))
    assert _lg('brain', P, NOW)[0]['text'] == '٣ شركاء باقٍ عليهم ٨٠٬٠٠٠ جنيه من حصصهم.'
    P0 = {'partners': {'rows': [dict(rows[0], paid=[], contributions=0)], 'equity_total': 100, 'any_contribution': False}}
    assert _lg('brain', P0, NOW)[0]['text'] == 'لم تُسجَّل دفعات الشركاء بعد، فالمدفوع من رأس المال غير معروف.'
    # كشوف الحساب · مجموع الحصص
    A = {'ad_clients': {'unsent': 2, 'due_unsent': [{'currency': 'EGP', 'amount': 12350}]}}
    assert _lg('brain', A, NOW)[0]['text'] == 'كشفا حساب جاهزان للإرسال، والمستحق لنا ١٢٬٣٥٠ جنيه.'
    A['ad_clients']['unsent'] = 5
    assert _lg('brain', A, NOW)[0]['text'].startswith('٥ كشوف حساب جاهزة للإرسال')
    A['ad_clients']['unsent'] = 1
    assert _lg('brain', A, NOW)[0]['text'].startswith('كشف حساب واحد جاهز للإرسال')
    E = {'partners': {'rows': [dict(rows[0], contributions=0, paid=[])], 'equity_total': 95, 'any_contribution': True}}
    assert _lg('brain', E, NOW)[0]['text'] == 'مجموع الحصص المسجّلة ٩٥٪.'
    assert _lg('brain', {'partners': {'rows': [], 'equity_total': 0, 'any_contribution': False}}, NOW) == []


@needs_node
def test_brain_priority_max_three_null_blocks_no_zero():
    full = {'money': {'month': '2026-09', 'revenue': 1000, 'expenses': 2000, 'covered_since': None},
            'agreements': {'ending': [{'id': 1, 'party': 'س', 'ends_on': '2026-11-05'}]}, 'subscriptions': {'next': []},
            'partners': {'rows': [{'id': 1, 'name': 'أ', 'reserve': False, 'agreed': [{'currency': 'EGP', 'amount': 10}], 'paid': [{'currency': 'EGP', 'amount': 5}], 'contributions': 1}], 'equity_total': 90, 'any_contribution': True},
            'ad_clients': {'unsent': 1, 'due_unsent': [{'currency': 'EGP', 'amount': 5}]}}
    ls = _lg('brain', full, NOW)
    assert [l['key'] for l in ls] == ['money', 'agreement', 'owing']
    nulls = {k: None for k in ('money', 'agreements', 'subscriptions', 'partners', 'ad_clients', 'assets', 'capital_moves')}
    assert _lg('brain', nulls, NOW) == [] and _lg('brain', None, NOW) == []
    for l in ls:
        assert not re.search(r'(?<![٠-٩٬٫])٠(?![٠-٩٬٫])', l['text']) and 'NaN' not in l['text'] and 'undefined' not in l['text'] and 'null' not in l['text']


@needs_node
def test_plural_days():
    for n, want in ((1, 'يوم واحد'), (2, 'يومين'), (3, '٣ أيام'), (10, '١٠ أيام'), (12, '١٢ يومًا')):
        assert _lg('dayText', n) == want


@needs_node
def test_partner_chip_and_remaining():
    agreed = [{'currency': 'EGP', 'amount': 100000}, {'currency': 'USD', 'amount': 4500}]
    assert _lg('remaining', agreed, [{'currency': 'EGP', 'amount': 75000}]) == [{'currency': 'EGP', 'amount': 25000}]
    assert _lg('remaining', agreed, [{'currency': 'EGP', 'amount': 120000}]) == []                         # الزيادة لا تظهر سالبة
    assert _lg('remaining', agreed, []) == []
    row = {'agreed': agreed, 'paid': [{'currency': 'EGP', 'amount': 75000}], 'contributions': 1}
    assert _lg('partnerChip', row) == {'text': 'باقٍ ٢٥٬٠٠٠ جنيه', 'tone': 'soon'}
    assert _lg('partnerChip', dict(row, paid=[{'currency': 'EGP', 'amount': 100000}])) == {'text': 'دفع كاملًا', 'tone': 'ok'}
    assert _lg('partnerChip', dict(row, paid=[{'currency': 'EGP', 'amount': 150000}])) == {'text': 'دفع كاملًا', 'tone': 'ok'}
    assert _lg('partnerChip', dict(row, paid=[], contributions=0)) == {'text': 'لم تُسجَّل دفعات', 'tone': 'neutral'}
    assert _lg('partnerChip', {'agreed': agreed}) is None                                                      # المدفوع مجهول ⇒ لا شارة
    assert _lg('partnerChip', dict(row, paid=[{'currency': 'SAR', 'amount': 5}]))['tone'] == 'neutral'


@needs_node
def test_chips_thresholds():
    ag = lambda d, st='active': _lg('agreementChip', {'status': st, 'ends_on': d}, NOW)           # noqa: E731
    assert ag(None)['text'] == 'ساري' and ag('2026-12-30')['tone'] == 'ok' and ag('2026-12-30')['days'] == 61
    assert ag('2026-11-29') == {'text': 'ينتهي بعد ٣٠ يومًا', 'tone': 'soon', 'days': 30}
    assert ag('2026-11-06') == {'text': 'ينتهي بعد ٧ أيام', 'tone': 'late', 'days': 7}
    assert ag('2026-11-01') == {'text': 'ينتهي بعد يومين', 'tone': 'late', 'days': 2}
    assert ag('2026-10-30') == {'text': 'ينتهي اليوم', 'tone': 'late', 'days': 0}
    assert ag('2026-10-29')['text'] == 'انتهى' and ag('2026-11-20', 'ended')['text'] == 'انتهى' and ag('2026-11-20', 'draft')['text'] == 'مسودة'
    rn = lambda d, st='active': _lg('renewChip', {'status': st, 'renews_on': d}, NOW)             # noqa: E731
    assert rn(None)['text'] == 'بلا موعد تجديد' and rn('2026-11-04') == {'text': 'يتجدد بعد ٥ أيام', 'tone': 'soon', 'days': 5}
    assert rn('2026-10-28') == {'text': 'فات موعد التجديد منذ يومين', 'tone': 'late', 'days': -2}
    assert rn('2026-10-30')['text'] == 'يتجدد اليوم' and rn('2026-11-06')['tone'] == 'soon' and rn('2026-11-07')['tone'] == 'neutral' and rn('2026-11-07')['text'].startswith('يتجدد ')
    assert rn('2026-11-04', 'stopped') == {'text': 'متوقف', 'tone': 'neutral', 'days': None}


@needs_node
def test_chips_use_local_calendar_days():
    late_night = int(datetime.datetime(2026, 10, 30, 23, 30, tzinfo=datetime.timezone.utc).timestamp() * 1000)
    assert _lg('agreementChip', {'status': 'active', 'ends_on': '2026-10-31'}, late_night)['days'] == 1            # لا نافذة ٢٤ ساعة


@needs_node
def test_deal_text_and_statement_exact():
    c = {'id': 5, 'name': 'مكتب الأمل', 'deal': 'percent', 'percent': 10, 'currency': 'EGP', 'count_label': 'عملاء جاؤوا من الحملة'}
    r = {'period': '2026-10', 'count': 14, 'income': 48000, 'due': [{'currency': 'EGP', 'amount': 4800}]}
    assert _lg('dealText', c) == 'نأخذ ١٠٪ من دخل الحملة'
    assert _lg('dealText', dict(c, deal='fixed_plus_percent', fixed_amount=6000, percent=5)) == 'مبلغ ثابت ٦٬٠٠٠ جنيه + ٥٪ من دخل الحملة'
    assert _lg('dealText', dict(c, deal='fixed', fixed_amount=3000)) == 'مبلغ ثابت ٣٬٠٠٠ جنيه'
    assert _lg('dealText', dict(c, deal='other', deal_other='اتفاق خاص')) == 'أخرى: اتفاق خاص'
    assert _lg('statementText', c, r) == '\n'.join(['كشف حساب — مكتب الأمل', 'الفترة: أكتوبر ٢٠٢٦', 'عملاء جاؤوا من الحملة: ١٤', 'دخلكم من الحملة: ٤٨٬٠٠٠ جنيه',
                                                      'الاتفاق: نأخذ ١٠٪ من دخل الحملة', 'المستحق للبروفيسور: ٤٬٨٠٠ جنيه', 'رقم الكشف: CO-5-2026-10'])
    fixed = dict(c, deal='fixed', fixed_amount=3000, currency='USD')
    t = _lg('statementText', fixed, {'period': '2026-09', 'count': None, 'income': None, 'due': [{'currency': 'USD', 'amount': 3000}]})
    assert 'دخلكم من الحملة' not in t and 'عملاء جاؤوا من الحملة: غير مسجّل' in t and 'المستحق للبروفيسور: ٣٬٠٠٠ دولار' in t
    assert 'غير محسوب بعد' in _lg('statementText', c, {'period': '2026-09', 'count': 1, 'income': None, 'due': None})


@needs_node
def test_target_rows_current_target_month_line():
    fc = [{'id': 1, 'month': '2026-08', 'revenue_egp': 40000, 'target_courses': 3, 'target_students': 90},
          {'id': 2, 'month': '2026-10', 'revenue_egp': 50000, 'target_courses': 4, 'target_students': 120},
          {'id': 3, 'month': '2026-12', 'revenue_egp': 60000, 'target_courses': 5, 'target_students': 150}]
    dash = {'monthly': [{'month': '2026-10', 'revenue': 31000}, {'month': '2026-08', 'revenue': 42000}], 'courses': {'total_courses': 6, 'total_students': 410}}
    rows = _lg('targetRows', fc, dash, NOW)
    assert [r['month'] for r in rows] == ['2026-08', '2026-10', '2026-12']
    r08, r10, r12 = rows
    assert r12['future'] is True and r12.get('actual') is None and r12['na'] is False and r10['actual'] == 31000 and r08['actual'] == 42000
    rows2 = _lg('targetRows', fc, {'monthly': [{'month': '2026-10', 'revenue': 1}]}, NOW)
    assert [r['actual'] for r in rows2 if r['month'] == '2026-08'] == [None] and [r['na'] for r in rows2 if r['month'] == '2026-08'] == [False]
    rows3 = _lg('targetRows', fc, None, NOW)
    assert [r['na'] for r in rows3] == [True, True, False]
    assert _lg('currentTarget', fc, NOW)['month'] == '2026-10'
    assert _lg('currentTarget', [fc[0], fc[2]], NOW)['month'] == '2026-12'
    assert _lg('currentTarget', [fc[0]], NOW) is None and _lg('currentTarget', None, NOW) is None
    assert _lg('monthLine', fc, dash, NOW)['text'] == 'دخل أكتوبر حتى الآن ٣١٬٠٠٠ جنيه من هدف ٥٠٬٠٠٠ جنيه (٦٢٪).'
    assert _lg('monthLine', [fc[0]], dash, NOW) == {'kind': 'notarget', 'text': 'لم يُحدَّد هدف دخل لهذا الشهر.'}
    assert _lg('monthLine', fc, None, NOW) == {'kind': 'na', 'text': 'دخل هذا الشهر غير متاح بعد.'}
    assert _lg('monthLine', fc, {'monthly': []}, NOW)['text'].startswith('لم يُسجَّل دخل في أكتوبر')


@needs_node
def test_target_rows_month_older_than_12_month_window_is_na():
    months = ['2025-%02d' % m for m in range(11, 13)] + ['2026-%02d' % m for m in range(1, 11)]          # ١٢ شهرًا: 2025-11 … 2026-10
    dash = {'monthly': [{'month': m, 'revenue': 100} for m in months if m != '2026-03']}
    dash['monthly'] = dash['monthly'] + [{'month': '2026-03', 'revenue': 0}]
    fc = [{'id': 1, 'month': '2025-06', 'revenue_egp': 1, 'target_courses': 0, 'target_students': 0},
          {'id': 2, 'month': '2026-03', 'revenue_egp': 1, 'target_courses': 0, 'target_students': 0}]
    r = _lg('targetRows', fc, dash, NOW)
    assert r[0]['na'] is True and r[1]['na'] is False and r[1]['actual'] == 0
    short = {'monthly': [{'month': '2026-09', 'revenue': 5}]}                                         # أقل من ١٢ ⇒ التاريخ كله موجود: «لا دخل»
    r2 = _lg('targetRows', fc, short, NOW)
    assert r2[0]['na'] is False and r2[0]['actual'] is None


@needs_node
def test_month_options():
    jan = int(datetime.datetime(2026, 1, 15, 12, tzinfo=datetime.timezone.utc).timestamp() * 1000)
    dec = int(datetime.datetime(2026, 12, 3, 12, tzinfo=datetime.timezone.utc).timestamp() * 1000)
    r = _lg('monthOptions', jan, 'result')
    assert r['def'] == '2025-12' and r['years'] == [2026, 2025] and r['months'][0] == {'v': '01', 't': 'يناير'} and r['months'][11] == {'v': '12', 't': 'ديسمبر'} and len(r['months']) == 12
    t = _lg('monthOptions', dec, 'target')
    assert t['def'] == '2027-01' and t['years'] == [2026, 2027]


@needs_node
def test_partners_from_raw_and_join():
    raw = [{'id': 1, 'name': 'أحمد', 'role': 'founder', 'equity_percent': 40, 'capital_egp': 100000, 'capital_usd': 4500, 'notes': ''},
           {'id': 2, 'name': 'خزينة', 'role': 'pool', 'equity_percent': 10, 'capital_egp': 0, 'capital_usd': 0, 'notes': 'للتوظيف'},
           {'id': 3, 'name': 'غير موزّع', 'role': 'partner', 'equity_percent': 5, 'capital_egp': 0, 'capital_usd': 0, 'notes': ''}]
    p = _lg('partnersFromRaw', raw)
    assert p['equity_total'] == 55 and [r['reserve'] for r in p['rows']] == [False, True, True]
    assert p['rows'][0]['agreed'] == [{'currency': 'EGP', 'amount': 100000}, {'currency': 'USD', 'amount': 4500}] and 'paid' not in p['rows'][0]
    assert p['agreed_total'] == [{'currency': 'EGP', 'amount': 100000}, {'currency': 'USD', 'amount': 4500}]
    j = _lg('joinPartners', raw, None)
    assert j['paidKnown'] is False and j['paid_total'] is None
    j2 = _lg('joinPartners', raw, {'rows': [{'id': 1, 'paid': [{'currency': 'EGP', 'amount': 5}], 'contributions': 1, 'last_paid_at': '2026-10-01'}], 'equity_total': 55, 'agreed_total': [], 'paid_total': [{'currency': 'EGP', 'amount': 5}], 'any_contribution': True})
    assert j2['paidKnown'] is True and j2['rows'][0]['paid'] == [{'currency': 'EGP', 'amount': 5}] and j2['rows'][1]['contributions'] == 0
    assert _lg('joinPartners', None, None) is None and _lg('partnersFromRaw', None) is None


@needs_node
def test_legacy_subs_deal_action_sum_lines_sorting():
    assets = [{'category': 'subscription', 'monthly_rent_egp': 1800}, {'category': 'software', 'monthly_rent_egp': 500}, {'category': 'tool', 'monthly_rent_egp': 0}, {'category': 'camera', 'monthly_rent_egp': 900}]
    assert len(_lg('legacySubs', assets)) == 2 and _lg('legacySubs', None) == []
    da = lambda **kw: _lg('dealAction', kw, NOW)                                                      # noqa: E731
    assert da(status='active', ends_on='2026-11-20', amount=5) == 'renew'
    assert da(status='active', ends_on='2027-06-01', amount=5) == 'receive'
    assert da(status='active', ends_on='2027-06-01') == 'edit' and da(status='active') == 'edit'
    assert da(status='draft', ends_on='2026-11-01', amount=5) == 'edit' and da(status='ended') == 'renew' and da(status='active', ends_on='2026-10-01') == 'renew'
    assert _lg('sumLines', [{'currency': 'EGP', 'amount': 400000}, {'currency': 'USD', 'amount': 4500}]) == '٤٠٠٬٠٠٠ جنيه · ٤٬٥٠٠ دولار'
    assert _lg('sumLines', None) == '' and _lg('sumLines', [{'currency': 'EGP', 'amount': 0}]) == ''
    subs = [{'id': 1, 'status': 'stopped', 'renews_on': '2026-01-01'}, {'id': 2, 'status': 'active', 'renews_on': None}, {'id': 3, 'status': 'active', 'renews_on': '2026-12-01'},
            {'id': 4, 'status': 'active', 'renews_on': '2026-10-01'}]
    assert [s['id'] for s in _lg('subsSorted', subs, NOW)] == [4, 3, 2, 1]
    deals = [{'id': 1, 'status': 'active', 'ends_on': '2027-05-01'}, {'id': 2, 'status': 'active', 'ends_on': '2026-11-10'}, {'id': 3, 'status': 'draft'}, {'id': 4, 'status': 'ended'}, {'id': 5, 'status': 'active'}]
    g = _lg('agreementGroups', deals, NOW)
    assert [x['id'] for x in g['ending']] == [2] and [x['id'] for x in g['active']] == [1, 5] and [x['id'] for x in g['drafts']] == [3] and [x['id'] for x in g['ended']] == [4]
    assert _lg('NA') == 'غير متاح بعد' and _lg('naText') == 'غير متاح بعد'


# ================================================================ الملفات
def test_static_index_hooks():
    s = _read('dashboard-cloud', 'index.html')
    blk = re.search(r'<!-- v2 sections begin -->(.*?)<!-- v2 sections end -->', s, re.S)
    assert blk, 'كتلة الأقسام ناقصة'
    assert s.count('<!-- v2 sections begin -->') == 1
    assert [l.strip() for l in blk.group(1).strip().splitlines() if 'company' in l] == ['<link rel="stylesheet" href="v2s/company.css">', '<script src="v2s/company.js"></script>']
    assert s.index('v2-d2.js') < s.index('<!-- v2 sections begin -->')
    hook = "const _s=V2SEC.owner(current);if(_s){"   # بعد الدمج: خطّاف واحد موحّد عبر السجلّ V2SEC.owner (v2s/_registry.js)
    assert s.count(hook) == 1
    assert s.index("return V2D3.render(current,v);") < s.index(hook) < s.index("if(MODULES_LOOKUP[current]&&MODULES_LOOKUP[current].soon)")
    assert 'openSection:function(key,tab,opts){v2OpenSection(key,tab,opts);}' in s


def test_static_app_and_dockerfile():
    a = _read('backend', 'app.py')
    assert a.count("v2_company_routes") == 1
    lines = a.splitlines()
    i = [n for n, l in enumerate(lines) if 'v2_company_routes' in l][0]
    assert lines[i].strip() == "__import__('v2_company_routes').register(app, globals())  # v2s:company"
    end = [n for n, l in enumerate(lines) if l.strip() == '# ---- v2 section routes end']
    assert len(end) == 1 and i < end[0]   # بعد الدمج: سطور الأقسام الأخرى قد تتبع سطر الشركة قبل العلامة
    d = _read('Dockerfile')
    assert 'COPY backend/v2_company_routes.py /app/v2_company_routes.py' in d and 'COPY dashboard-cloud/v2s /app/dist/v2s' in d


def test_static_company_js_fix_round_rules():
    js = _read('dashboard-cloud', 'v2s', 'company.js')
    css = _read('dashboard-cloud', 'v2s', 'company.css')
    assert "if (lk) { out.ledger_kind" in js and 'ledger_kind: kind || null, ledger_owner_id: own || null, status' not in js     # الربط لا يُمسح بصمت
    assert 'userEditing()' in js and "m !== 'settings'" in js                                                                  # المؤقّتات لا تمسح ما كُتب
    assert 'تُضبط من الخادم' not in js
    assert js.count('delSheet({') == 4 and 'confirmSheet({ title: \'حذف' not in js                                            # كل حذف بمرحلتين
    assert "ep: ['users']" in js
    assert '.mh' not in css and '#21262E' in css   # ترويسة الأوراق قاعدة واحدة في v2-shell.css (ورقة القرار الموحّدة)


def test_static_company_js_rules():
    js = _read('dashboard-cloud', 'v2s', 'company.js')
    for bad in ('goals-advisor', 'ANTHROPIC', 'OPENAI', 'DEEPSEEK', 'api_key', 'type="month"', "type='month'", 'dashboard.elprofessor.net', 'يقوّم', 'الكاش', 'زوم', 'eval('):
        assert bad not in js, bad
    assert 'localStorage' not in js and 'sessionStorage' not in js
    assert 'input[type=month]' not in js
    # لا عنوان مرئي يبدأ بـ«الذكاء» أو «AI»
    heads = re.findall(r"card\('([^']+)'", js)
    assert heads and not [h for h in heads if h.startswith('الذكاء') or h.startswith('AI')]
    assert 'confirmed: true' in js and 'op_id' in js
    css = _read('dashboard-cloud', 'v2s', 'company.css')
    assert '.co-btn1' in css and '@media (max-width:699px)' in css and '#9E2B4E' in css


def test_static_sections_map():
    lg = _read('dashboard-cloud', 'v2-logic.js')
    assert "T('invest', 'نظرة', 'investment')" in lg and "hiddenTab(T('targets', 'الأهداف', 'targets'))" in lg
    assert lg.count('// ===== v2s:company =====') == 1


@needs_node
def test_sections_company_entry_and_old_links():
    secs = v2_node.logic('SECTIONS')
    co = [s for s in secs if s['key'] == 'company'][0]
    assert [(t['key'], t['label'], t['mod']) for t in co['tabs'] if not t.get('hidden')] == [
        ('invest', 'نظرة', 'investment'), ('partners', 'الشركاء ورأس المال', 'v2c_partners'), ('assets', 'المعدات والاشتراكات', 'v2c_assets'),
        ('deals', 'الاتفاقات والرعاة', 'v2c_deals'), ('ads', 'عملاء الإعلانات', 'v2c_ads'), ('settings', 'الإعدادات', 'settings')]
    tg = [t for t in co['tabs'] if t['key'] == 'targets'][0]
    assert tg['hidden'] is True and tg['st'] == {} and tg['mod'] == 'targets'
    for mod, tab in (('investment', 'invest'), ('targets', 'targets'), ('settings', 'settings'), ('partners', 'targets' if False else None), ('foundation', 'targets')):
        r = v2_node.logic('sectionFor', mod, {}, None)
        assert r and r['section'] == 'company', mod
        if tab:
            assert r['tab'] == tab, (mod, r)
    assert v2_node.logic('sectionFor', 'partners', {}, None)['tab'] == 'invest'
    assert v2_node.logic('routeFor', '#s/company/ads', {})['mod'] == 'v2c_ads'
