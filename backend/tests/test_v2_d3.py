# -*- coding: utf-8 -*-
"""D3 — «الفلوس» على الهيكل الجديد (نظرة · التحويلات · الإيصالات والعالقة · الأسعار · النسب · إعلانات الأعمال) و«الكتب» (مراجعة العروض
وطلبات القرّاء)، ورا نفس المفتاح المقفول.

Run:  cd backend && python3 -B -m pytest -q -p no:cacheprovider tests/test_v2_d3.py

⛔ صفر شبكة حقيقية: المنصة جدول في الذاكرة (`uiharness/d3_fixtures.D3Platform`)، وأي عنوان برّه `https://platform.test` بيوقّع الاختبار.
المنطق النقي (الدخل · الأعداد · الفروق قبل/بعد · الشارة) بيتشغّل في node على v2-logic.js.

اللي بيثبّته:
  ١. البروكسيات (pytest): أدمن بس · المفتاح مقفول ٤٠٤ بلا أي نداء · `no-store` · الكتابة تطلب `confirmed:true` بالظبط · `by` من التوكن
     مش من الجسم · القايمة البيضا للحقول · رد المنصة (٤٢٢/٤٠٩/٤٠٤) بيعدّي كما هو · المصدر الفاشل خطأ بحالته (مش جسم مخترع ولا صفر) ·
     رد الكتابة الضايع «ما وصلناش رد» · التدقيق عند النجاح بس.
  ٢. المنطق (node): تنسيق المبالغ لكل عملة · عملة أجنبية ما بتتجمعش في الجنيه · المصدر الفاشل ⇒ null · «الكتب لا تُسترد» · فرق قبل⇒بعد
     للأسعار والنسب · عدّاد الشارة · كل رقم من الأربعة · صافي البروفيسور «غير متاح بعد».
  ٣. الملفات: الغلاف · Dockerfile · الخطّافات في index.html · المفتاح مقفول ⇒ لا أثر.
"""
import copy
import datetime
import json
import os
import re
import sys
import time

import jwt
import pytest
from werkzeug.security import generate_password_hash

from app import app as flask_app, db, User, AuditLog  # noqa: E402

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(_HERE, 'uiharness'))
import d3_fixtures as d3fx   # noqa: E402
import v2_node               # noqa: E402

ROOT = os.path.dirname(os.path.dirname(_HERE))
PLATFORM = 'https://platform.test'
SECRET = 'test-metrics-secret'
NON_ADMIN_ROLES = ['employee', 'trainer', 'investor', 'viewer', 'pending']
needs_node = pytest.mark.skipif(not v2_node.NODE, reason='needs node')
ADMIN_EMAIL = 'v2d3-admin@x.test'


def _read(*parts):
    with open(os.path.join(ROOT, *parts), encoding='utf-8') as fh:
        return fh.read()


# ---------------------------------------------------------------- أدوات

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
    if u:
        u.role = role
        u.dashboard_role = role
        u.is_active = True
        db.session.commit()
        return u
    u = User(email=email, password_hash=generate_password_hash('x', method='pbkdf2:sha256'),
             name=email.split('@')[0], role=role, dashboard_role=role, linked_to_name='',
             preferred_currency='AUTO', is_active=True)
    db.session.add(u)
    db.session.commit()
    return u


def _bearer(user):
    tok = jwt.encode({'user_id': user.id, 'exp': datetime.datetime.utcnow() + datetime.timedelta(days=1)},
                     flask_app.config['SECRET_KEY'], algorithm='HS256')
    return {'Authorization': 'Bearer ' + tok}


@pytest.fixture(scope='module')
def ctx():
    with flask_app.app_context():
        db.create_all()
        heads = {r: _bearer(_mkuser('v2d3-%s@x.test' % r, r)) for r in NON_ADMIN_ROLES}
        heads['admin'] = _bearer(_mkuser(ADMIN_EMAIL, 'admin'))
        yield {'heads': heads, 'client': flask_app.test_client()}


class Plat(object):
    """`requests.request` البديل: يسجّل كل نداء ويرد من `D3Platform`. أي عنوان برّه المنصة المزيّفة ⇒ ممنوع."""

    def __init__(self):
        self.ef = d3fx.D3Platform(d2=True)
        self.seen = []
        self.blocked = []

    def __call__(self, method, url, params=None, json=None, headers=None, timeout=None):
        self.seen.append({'method': method.upper(), 'url': url, 'path': url[len(PLATFORM):], 'params': dict(params or {}),
                          'headers': dict(headers or {}), 'json': copy.deepcopy(json), 'timeout': timeout})
        if not url.startswith(PLATFORM + '/'):
            self.blocked.append(url)
            raise RuntimeError('طلب حقيقي ممنوع: ' + url)
        out = self.ef.handle(method, url[len(PLATFORM):], params, json)
        if out is None:
            return _Resp(200, [])
        return _Resp(*out)

    def calls(self, path_prefix=''):
        return [c for c in self.seen if c['path'].startswith(path_prefix)]


@pytest.fixture
def plat(monkeypatch):
    import app as appmod
    p = Plat()
    monkeypatch.setattr(appmod, 'PLATFORM_METRICS_SECRET', SECRET)
    monkeypatch.setattr(appmod, 'PLATFORM_API_URL', PLATFORM)
    monkeypatch.setattr(appmod.requests, 'request', p)
    monkeypatch.setenv('DASH_V2_ENABLED', 'true')
    yield p
    assert p.blocked == [], 'طلب لسيرفر حقيقي: %r' % p.blocked


# (method, dashboard path, platform path, body)
OFFER_BODY = {'versions': {'read': {'pricing': {'eg': {'amount': 300, 'currency': 'EGP'}}}, 'pdf': {'pricing': {}}}, 'confirmed': True}
PRICES_BODY = {'versions': {'read': {'eg': {'amount': 160, 'currency': 'EGP'}, 'default': {'amount': 9, 'currency': 'USD'}}, 'pdf': {}},
               'visible': True, 'confirmed': True, 'rev': 1}
ENDPOINTS = [
    ('GET', '/api/v2/money/settings', '/api/bridge/settings/money', None),
    ('PUT', '/api/v2/money/settings', '/api/bridge/settings/money', {'withdraw_min': 400, 'confirmed': True}),
    ('GET', '/api/v2/shares', '/api/bridge/shares', None),
    ('PUT', '/api/v2/shares', '/api/bridge/shares', {'changes': {'affiliate': {'rate': 12}}, 'version': 3, 'confirmed': True}),
    ('GET', '/api/v2/ads-ledger', '/api/bridge/ads-ledger', None),
    ('GET', '/api/v2/ads-ledger/bk-tenant-guide', '/api/bridge/ads-ledger/bk-tenant-guide', None),
    ('GET', '/api/v2/payments/stuck', '/api/bridge/payments/stuck', None),
    ('GET', '/api/v2/income/by-service', '/api/bridge/income/by-service', None),
    ('GET', '/api/v2/refunds/pending', '/api/bridge/refunds/pending', None),
    ('GET', '/api/v2/prices/book', '/api/bridge/prices/book', None),
    ('GET', '/api/v2/prices/book/bk-tenant-guide', '/api/bridge/prices/book/bk-tenant-guide', None),
    ('PUT', '/api/v2/prices/book/bk-tenant-guide', '/api/bridge/prices/book/bk-tenant-guide', PRICES_BODY),
    ('GET', '/api/v2/book-offers', '/api/bridge/book-offers', None),
    ('POST', '/api/v2/book-offers/off-1/approve', '/api/bridge/book-offers/off-1/approve', OFFER_BODY),
    ('POST', '/api/v2/book-offers/off-2/reject', '/api/bridge/book-offers/off-2/reject', {'reason': 'الملف غير مكتمل', 'confirmed': True}),
    ('GET', '/api/v2/book-requests', '/api/bridge/book-requests', None),
    ('PATCH', '/api/v2/book-requests/rq-1', '/api/bridge/book-requests/rq-1', {'status': 'seeking', 'apply_to_group': True}),
]
WRITES = [e for e in ENDPOINTS if e[0] in ('PUT', 'POST')]
READS = [e for e in ENDPOINTS if e[0] == 'GET']


def _call(ctx, method, path, body=None, role='admin'):
    c = ctx['client']
    heads = ctx['heads'][role] if role else {}
    kw = {'headers': heads}
    if body is not None:
        kw['json'] = body
    return c.open(path, method=method, **kw)


# ---------------------------------------------------------------- ١) البروكسيات

@pytest.mark.parametrize('method,path,_pp,body', ENDPOINTS)
def test_every_proxy_is_admin_only(ctx, plat, method, path, _pp, body):
    for role in NON_ADMIN_ROLES:
        r = _call(ctx, method, path, body, role=role)
        assert r.status_code == 403, (path, role, r.status_code)
    r = _call(ctx, method, path, body, role=None)
    assert r.status_code == 401
    assert plat.seen == [], 'نداء للمنصة من غير أدمن'


@pytest.mark.parametrize('method,path,_pp,body', ENDPOINTS)
def test_every_proxy_is_closed_when_the_switch_is_off(ctx, plat, monkeypatch, method, path, _pp, body):
    monkeypatch.setenv('DASH_V2_ENABLED', 'false')
    r = _call(ctx, method, path, body)
    assert r.status_code == 404 and plat.seen == []
    assert r.headers.get('Cache-Control') == 'no-store'


@pytest.mark.parametrize('method,path,pp,body', READS)
def test_reads_pass_through_with_the_secret_and_no_store(ctx, plat, method, path, pp, body):
    r = _call(ctx, method, path)
    assert r.status_code == 200, r.get_data(as_text=True)[:200]
    assert r.headers.get('Cache-Control') == 'no-store'
    calls = plat.calls('/api/bridge')
    assert len(calls) == 1, 'نداء واحد ولا إعادة محاولة'
    assert calls[0]['method'] == 'GET' and calls[0]['path'] == pp and calls[0]['headers'].get('X-ELP-Metrics-Secret') == SECRET


@pytest.mark.parametrize('method,path,pp,body', WRITES)
def test_writes_need_confirmed_true_exactly(ctx, plat, method, path, pp, body):
    for bad in (None, False, 'true', 1, 'yes'):
        b = copy.deepcopy(body)
        if bad is None:
            b.pop('confirmed', None)
        else:
            b['confirmed'] = bad
        r = _call(ctx, method, path, b)
        assert r.status_code == 400, (path, bad, r.status_code)
        assert r.headers.get('Cache-Control') == 'no-store'
    assert plat.seen == [], 'نداء للمنصة من غير تأكيد صريح'


@pytest.mark.parametrize('method,path,pp,body', WRITES)
def test_by_comes_from_the_token_never_from_the_body(ctx, plat, method, path, pp, body):
    b = copy.deepcopy(body)
    b['by'] = 'attacker@evil.test'
    r = _call(ctx, method, path, b)
    assert r.status_code == 200, r.get_data(as_text=True)[:300]
    calls = [c for c in plat.calls(pp) if c['method'] == method]
    assert len(calls) == 1
    assert calls[0]['json']['by'] == ADMIN_EMAIL
    assert 'attacker' not in json.dumps(calls[0]['json'])
    assert r.headers.get('Cache-Control') == 'no-store'


def test_the_platform_body_is_a_whitelist_not_the_browser_body(ctx, plat):
    b = {'withdraw_min': 400, 'confirmed': True, 'rev': 0, 'is_admin': True, 'role': 'root', 'by': 'x@y.z'}
    assert _call(ctx, 'PUT', '/api/v2/money/settings', b).status_code == 200
    sent = plat.calls('/api/bridge/settings')[-1]['json']
    assert set(sent) == {'withdraw_min', 'confirmed', 'rev', 'by'} and sent['confirmed'] is True and sent['withdraw_min'] == 400
    p = {'versions': PRICES_BODY['versions'], 'visible': True, 'confirmed': True, 'note': 'ن' * 900, 'title': 'عنوان', 'evil': 1}
    assert _call(ctx, 'PUT', '/api/v2/prices/book/bk-tenant-guide', p).status_code == 200
    sent = plat.calls('/api/bridge/prices')[-1]['json']
    assert set(sent) <= {'versions', 'visible', 'confirmed', 'note', 'title', 'rev', 'by'} and len(sent['note']) == 300 and 'evil' not in sent


def test_money_settings_validate_the_number_before_any_call(ctx, plat):
    for v in ('400', 400.5, True, None, [1], {'a': 1}):
        r = _call(ctx, 'PUT', '/api/v2/money/settings', {'withdraw_min': v, 'confirmed': True})
        assert r.status_code == 400, v
    assert plat.seen == []
    r = _call(ctx, 'PUT', '/api/v2/money/settings', {'withdraw_min': 400.0, 'confirmed': True})
    assert r.status_code == 200 and plat.calls('/api/bridge/settings')[-1]['json']['withdraw_min'] == 400


def test_the_platforms_own_refusal_message_passes_through(ctx, plat):
    r = _call(ctx, 'PUT', '/api/v2/money/settings', {'withdraw_min': 10, 'confirmed': True})
    assert r.status_code == 422 and 'بين 50 و20000' in r.get_json()['error'], r.get_json()
    r = _call(ctx, 'PUT', '/api/v2/money/settings', {'withdraw_min': 600, 'confirmed': True, 'rev': 99})
    assert r.status_code == 409 and 'حدّث الشاشة' in r.get_json()['error']
    # النسب: الأرضية ٣٥ تحرسها المنصة؛ رسالتها بتوصل كما هي
    r = _call(ctx, 'PUT', '/api/v2/shares', {'changes': {'books': {'normal': {'owner': 70, 'platform': 30}}}, 'version': 3, 'confirmed': True})
    assert r.status_code == 422 and '35' in r.get_json()['error'], r.get_json()
    r = _call(ctx, 'PUT', '/api/v2/shares', {'changes': {'affiliate': {'rate': 12}}, 'version': 1, 'confirmed': True})
    assert r.status_code == 409
    r = _call(ctx, 'PUT', '/api/v2/prices/book/bk-tenant-guide', dict(PRICES_BODY, rev=77))
    assert r.status_code == 409 and 'اتعدّلت من مكان تاني' in r.get_json()['error']
    bad = copy.deepcopy(PRICES_BODY)
    bad['visible'] = True
    bad['versions'] = {'read': {'eg': {'amount': 100, 'currency': 'EGP'}}, 'pdf': {}}
    r = _call(ctx, 'PUT', '/api/v2/prices/book/bk-tenant-guide', bad)
    assert r.status_code == 422 and 'باقي البلاد' in r.get_json()['error']


def test_a_successful_write_changes_the_platform_state_and_is_audited(ctx, plat):
    before = db.session.query(AuditLog).count()
    r = _call(ctx, 'PUT', '/api/v2/money/settings', {'withdraw_min': 750, 'confirmed': True})
    assert r.status_code == 200 and r.get_json()['withdraw_min'] == 750 and r.get_json()['rev'] == 1
    got = _call(ctx, 'GET', '/api/v2/money/settings').get_json()
    assert got['withdraw_min'] == 750 and got['history'][0]['before'] == {'withdraw_min': 500} and got['history'][0]['by'] == ADMIN_EMAIL
    rows = AuditLog.query.filter_by(action='money_settings.update').order_by(AuditLog.id.desc()).all()
    assert rows[0].actor_email == ADMIN_EMAIL and json.loads(rows[0].meta_json)['withdraw_min'] == 750
    assert db.session.query(AuditLog).count() == before + 1
    # الفاشل ما بيتدقّقش
    n = db.session.query(AuditLog).count()
    assert _call(ctx, 'PUT', '/api/v2/money/settings', {'withdraw_min': 5, 'confirmed': True}).status_code == 422
    assert db.session.query(AuditLog).count() == n


def test_shares_update_round_trip_and_the_floor(ctx, plat):
    cur = _call(ctx, 'GET', '/api/v2/shares').get_json()
    assert cur['version'] == 3 and cur['shares']['platform_floor'] == 35
    ok = _call(ctx, 'PUT', '/api/v2/shares', {'changes': {'books': {'ads': {'owner': 65, 'platform': 35}}, 'affiliate': {'rate': 12}}, 'version': 3, 'confirmed': True})
    assert ok.status_code == 200 and ok.get_json()['version'] == 4 and ok.get_json()['shares']['affiliate']['rate'] == 12
    assert ok.get_json()['history'][0]['by'] == ADMIN_EMAIL
    assert _call(ctx, 'PUT', '/api/v2/shares', {'changes': {'cases': {'ladder': [{'max_egp': 10000, 'platform_pct': 20}, {'max_egp': None, 'platform_pct': 25}]}},
                                                 'version': 4, 'confirmed': True}).status_code == 422
    for bad in ({'changes': {}, 'version': 4}, {'changes': 'x', 'version': 4}, {'changes': {'a': 1}, 'version': 'x'}, {'changes': {'a': 1}, 'version': -1}):
        assert _call(ctx, 'PUT', '/api/v2/shares', dict(bad, confirmed=True)).status_code == 400


def test_prices_are_validated_by_kind_and_id_before_any_call(ctx, plat):
    assert _call(ctx, 'GET', '/api/v2/prices/movie').status_code == 404
    assert _call(ctx, 'GET', '/api/v2/prices/book/a%20b').status_code == 404
    assert _call(ctx, 'GET', '/api/v2/prices/book/x%3Fy').status_code == 404
    assert _call(ctx, 'PUT', '/api/v2/prices/video/x', dict(PRICES_BODY)).status_code == 404
    assert _call(ctx, 'PUT', '/api/v2/prices/book/x', dict(PRICES_BODY, visible='yes')).status_code == 400
    assert _call(ctx, 'PUT', '/api/v2/prices/book/x', dict(PRICES_BODY, versions=[1])).status_code == 400
    assert _call(ctx, 'GET', '/api/v2/income/by-service?month=2026-13').status_code == 400
    assert _call(ctx, 'GET', '/api/v2/ads-ledger/bk-1?month=oct').status_code == 400
    assert plat.seen == []
    assert _call(ctx, 'GET', '/api/v2/income/by-service?month=2026-10').status_code == 200
    assert plat.calls('/api/bridge/income')[-1]['params'] == {'month': '2026-10'}


def test_course_prices_return_the_platforms_closed_answer_as_is(ctx, plat):
    r = _call(ctx, 'GET', '/api/v2/prices/course')
    assert r.status_code == 404 and r.headers.get('Cache-Control') == 'no-store'
    plat.ef.course_prices = True
    r = _call(ctx, 'GET', '/api/v2/prices/course')
    assert r.status_code == 200 and r.get_json()['items'][0]['id'] == 'contract-basics'


def test_prices_for_the_course_kind_are_proxied_with_rev(ctx, plat):
    plat.ef.course_prices = True
    b = {'versions': {'standard': {'eg': {'amount': 500, 'currency': 'EGP'}, 'default': {'amount': 20, 'currency': 'USD'}}}, 'visible': True, 'confirmed': True, 'rev': 1}
    r = _call(ctx, 'PUT', '/api/v2/prices/course/contract-basics', b)
    assert r.status_code == 200
    assert plat.calls('/api/bridge/prices/course')[-1]['json']['rev'] == 1


def test_a_failed_source_is_an_error_with_its_status_never_a_fake_empty_body(ctx, plat):
    for path, pp in (('/api/v2/payments/stuck', '/api/bridge/payments/stuck'), ('/api/v2/ads-ledger', '/api/bridge/ads-ledger'),
                     ('/api/v2/refunds/pending', '/api/bridge/refunds/pending'), ('/api/v2/shares', '/api/bridge/shares'),
                     ('/api/v2/money/settings', '/api/bridge/settings/money'), ('/api/v2/book-offers', '/api/bridge/book-offers')):
        plat.ef.down = {pp}
        r = _call(ctx, 'GET', path)
        body = r.get_json()
        assert r.status_code == 502 and set(body) == {'error'}, (path, r.status_code, body)
        assert r.headers.get('Cache-Control') == 'no-store'
    # المنصة نفسها مش مضبوطة
    import app as appmod
    appmod.PLATFORM_METRICS_SECRET = ''
    try:
        r = _call(ctx, 'GET', '/api/v2/payments/stuck')
        assert r.status_code == 503 and r.headers.get('Cache-Control') == 'no-store'
    finally:
        appmod.PLATFORM_METRICS_SECRET = SECRET


def test_a_write_whose_reply_was_lost_says_no_reply_and_is_logged_not_audited_as_done(ctx, plat):
    plat.ef.forced[('PUT', '/api/bridge/settings/money')] = (504, {'detail': 'timeout'})
    n_ok = AuditLog.query.filter_by(action='money_settings.update').count()
    r = _call(ctx, 'PUT', '/api/v2/money/settings', {'withdraw_min': 800, 'confirmed': True})
    body = r.get_json()
    assert r.status_code == 502 and body.get('no_reply') is True and 'رد' in body['error']
    assert AuditLog.query.filter_by(action='money_settings.update').count() == n_ok
    assert AuditLog.query.filter_by(action='money_settings.no_reply').count() >= 1
    assert r.headers.get('Cache-Control') == 'no-store'


def test_book_offers_and_requests_round_trip(ctx, plat):
    rows = _call(ctx, 'GET', '/api/v2/book-offers').get_json()
    assert [o['id'] for o in rows['offers']] == ['off-1', 'off-2']
    assert plat.calls('/api/bridge/book-offers')[-1]['params'] == {'status': 'in_review'}
    _call(ctx, 'GET', '/api/v2/book-offers?status=hack')
    assert plat.calls('/api/bridge/book-offers')[-1]['params'] == {'status': 'in_review'}
    # الرفض بلا سبب ممنوع قبل أي نداء
    n = len(plat.seen)
    assert _call(ctx, 'POST', '/api/v2/book-offers/off-1/reject', {'reason': '   ', 'confirmed': True}).status_code == 400
    assert len(plat.seen) == n
    ok = _call(ctx, 'POST', '/api/v2/book-offers/off-1/approve', OFFER_BODY)
    assert ok.status_code == 200 and plat.ef.offers[0]['status'] == 'live'
    sent = plat.calls('/api/bridge/book-offers/off-1/approve')[-1]['json']
    assert sent['by'] == ADMIN_EMAIL and sent['versions']['read']['pricing']['eg']['amount'] == 300
    again = _call(ctx, 'POST', '/api/v2/book-offers/off-1/approve', OFFER_BODY)
    assert again.status_code == 409 and 'مش في المراجعة' in again.get_json()['error']
    assert _call(ctx, 'POST', '/api/v2/book-offers/off-2/reject', {'reason': 'الملف غير مكتمل', 'confirmed': True}).status_code == 200
    assert plat.calls('/api/bridge/book-offers/off-2/reject')[-1]['json'] == {'reason': 'الملف غير مكتمل', 'by': ADMIN_EMAIL}
    # طلبات القرّاء: الحالة محصورة، والاعتماد للمجموعة
    r = _call(ctx, 'PATCH', '/api/v2/book-requests/rq-1', {'status': 'seeking', 'apply_to_group': True})
    assert r.status_code == 200 and {x['status'] for x in plat.ef.requests if x['group_key'] == 'g-rent'} == {'seeking'}
    assert _call(ctx, 'PATCH', '/api/v2/book-requests/rq-4', {'hidden': True}).status_code == 200
    assert plat.ef.requests[3]['hidden'] is True
    assert _call(ctx, 'PATCH', '/api/v2/book-requests/rq-4', {'status': 'fulfilled'}).status_code == 400
    assert _call(ctx, 'PATCH', '/api/v2/book-requests/rq-4', {'hidden': 'yes'}).status_code == 400
    assert _call(ctx, 'PATCH', '/api/v2/book-requests/rq-4', {}).status_code == 400
    sent = plat.calls('/api/bridge/book-requests/rq-4')[-1]['json']
    assert sent['by'] == ADMIN_EMAIL


def test_no_proxy_moves_money_or_calls_a_provider(ctx, plat):
    for method, path, pp, body in ENDPOINTS:
        _call(ctx, method, path, copy.deepcopy(body) if body else None)
    paths = {c['path'] for c in plat.seen}
    assert all(p.startswith('/api/bridge/') for p in paths), paths
    assert not [p for p in paths if re.search(r'settle|reject-payout|refund/(settle|execute)|stripe|paymob|telegram|email', p)], paths
