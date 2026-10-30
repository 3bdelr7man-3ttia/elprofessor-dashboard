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


# ---------------------------------------------------------------- ٢) المنطق النقي (node)

NOW = 1793361600000          # 2026-10-30T12:00:00Z (الجمعة)
H = 3600e3


def _iso(hours_ago):
    return datetime.datetime.fromtimestamp((NOW - hours_ago * H) / 1000.0, datetime.timezone.utc).isoformat()


def L(fn, *args):
    return v2_node.logic(fn, *args)


REV = [
    {'date': '2026-10-30', 'source': 'consultation', 'amount_egp': 500, 'amount_usd': 0},
    {'date': '2026-10-30', 'source': 'consultation', 'amount_egp': 500.5, 'amount_usd': 0},
    {'date': '2026-10-30', 'source': 'course', 'amount_egp': 0, 'amount_usd': 30},
    {'date': '2026-10-30', 'source': 'course', 'amount_egp': None, 'amount_usd': 0, 'needs_fx': True, 'currency': 'SAR', 'amount_original': 150},
    {'date': '2026-10-29', 'source': 'book', 'amount_egp': 100, 'amount_usd': 0},
    {'date': '2026-10-12', 'source': 'knowledge', 'amount_egp': 200, 'amount_usd': 0},
    {'date': '2026-09-20', 'source': 'sale', 'amount_egp': 900, 'amount_usd': 0},
    {'date': '2026-01-05', 'source': 'subscription', 'amount_egp': 70, 'amount_usd': 0},
]


def _amt(totals, cur):
    return next((t['amount'] for t in totals if t['currency'] == cur), None)


@needs_node
def test_periods_are_day_month_year_in_device_time():
    d, m, y = (L('v2Period', k, NOW) for k in ('day', 'month', 'year'))
    assert (d['from'], d['until'], d['label']) == ('2026-10-30', '2026-10-31', 'اليوم')
    assert (m['from'], m['until'], m['label']) == ('2026-10-01', '2026-11-01', 'الشهر')
    assert (y['from'], y['until'], y['label']) == ('2026-01-01', '2027-01-01', 'السنة')
    assert L('v2Period', 'nonsense', NOW)['key'] == 'month'
    assert [p['label'] for p in L('PERIODS')] == ['اليوم', 'الشهر', 'السنة']


@needs_node
def test_income_sums_each_currency_alone_and_never_converts_into_egp():
    day = L('v2Income', REV, 'day', NOW)
    assert _amt(day['totals'], 'EGP') == 1000.5, 'الجنيه من amount_egp فقط'
    assert _amt(day['totals'], 'USD') == 30 and _amt(day['totals'], 'SAR') == 150, 'الدولار والريال منفصلان'
    assert [t['currency'] for t in day['totals']] == ['EGP', 'SAR', 'USD'] and day['count'] == 4
    month = L('v2Income', REV, 'month', NOW)
    assert _amt(month['totals'], 'EGP') == 1300.5 and month['count'] == 6
    year = L('v2Income', REV, 'year', NOW)
    assert _amt(year['totals'], 'EGP') == 2270.5 and _amt(year['totals'], 'USD') == 30
    # الدولار ما بيدخلش في رقم الجنيه حتى لو الصف نفسه فيه الاتنين
    both = L('v2Income', [{'date': '2026-10-30', 'source': 'course', 'amount_egp': 100, 'amount_usd': 5}], 'day', NOW)
    assert _amt(both['totals'], 'EGP') == 100 and _amt(both['totals'], 'USD') == 5
    # total_egp (التحويل بسعر صرف) مش بتتقرأ أبدًا
    conv = L('v2Income', [{'date': '2026-10-30', 'source': 'course', 'amount_egp': 0, 'amount_usd': 0, 'total_egp': 9999}], 'day', NOW)
    assert conv['totals'] == [] and conv['count'] == 0


@needs_node
def test_income_by_service_follows_the_source_kind():
    svc = L('v2Income', REV, 'year', NOW)['services']
    assert _amt(svc['experts'], 'EGP') == 1000.5
    assert _amt(svc['courses'], 'USD') == 30 and _amt(svc['courses'], 'SAR') == 150
    assert _amt(svc['books'], 'EGP') == 300
    assert _amt(svc['other'], 'EGP') == 970 and [s['label'] for s in L('SERVICES')] == ['ملفات الخبراء', 'الدورات', 'الكتب', 'أخرى']


@needs_node
def test_a_failed_source_is_null_never_zero():
    assert L('v2Income', None, 'month', NOW) is None
    assert L('v2Held', None) is None and L('v2Owed', None) is None
    assert L('v2Stuck', None, NOW) is None and L('v2Stuck', {'items': 'x'}, NOW) is None
    assert L('v2Prices', None) is None and L('v2SharesView', None) is None and L('v2MinPayout', None, NOW) is None
    assert L('v2AdsLedger', None, NOW) is None and L('v2OffersQueue', None, None, NOW) is None and L('v2Requests', None, NOW) is None
    assert L('v2PayoutRows', None, NOW) is None and L('v2PayoutHistory', None, None, NOW) is None
    assert L('v2IncomeBars', None, None, 'month') is None
    # الصفر الحقيقي (المصدر وصل وقال لا شيء) شيء تاني: «٠ جنيه» مش «غير متاح»
    empty = L('v2MoneyBoard', {'revenues': [], 'escrow': [], 'payouts': []}, 'month', NOW)
    nums = {n['key']: n for n in empty['numbers']}
    assert nums['income']['na'] is False and nums['income']['text'] == '٠ جنيه'
    assert nums['held']['na'] is False and nums['owed']['na'] is False


@needs_node
def test_the_four_numbers_with_a_plain_line_each_and_the_net_is_not_available():
    escrow = [{'amount': 600, 'currency': 'EGP', 'status': 'held'}, {'amount': 1000.25, 'currency': 'EGP', 'status': 'confirm'},
              {'amount': 200, 'currency': 'USD', 'status': 'dispute'}, {'amount': 77, 'currency': 'EGP', 'status': 'released'}]
    payouts = [{'pid': 'p1', 'status': 'pending', 'raw': {'amount': 600.5, 'currency': 'EGP'}},
               {'pid': 'p2', 'status': 'pending', 'raw': {'amount': 3500.5, 'currency': 'SAR'}, 'fx_alert': True}]
    b = L('v2MoneyBoard', {'revenues': REV, 'escrow': escrow, 'payouts': payouts}, 'month', NOW)
    n = {x['key']: x for x in b['numbers']}
    assert [x['key'] for x in b['numbers']] == ['income', 'held', 'owed', 'net']
    assert [x['label'] for x in b['numbers']] == ['دخل', 'محجوز حتى يُسلَّم العمل', 'مستحق للخبراء والمدرّبين', 'صافي البروفيسور']
    assert n['income']['text'] == '١٬٣٠٠٫٥ جنيه' and 'بعملة أخرى' in n['income']['others'] and '٣٠ دولار' in n['income']['others']
    assert n['held']['text'] == '١٬٦٠٠٫٢٥ جنيه' and '٢٠٠ دولار' in n['held']['others'] and n['held']['count'] == 3, 'المحرَّر لا يُحسب'
    assert n['owed']['text'] == '٦٠٠٫٥ جنيه' and '٣٬٥٠٠٫٥ ريال' in n['owed']['others'], 'الكسور محفوظة والريال لا يدخل الجنيه'
    assert n['net']['na'] is True and n['net']['text'] == 'غير متاح بعد' and n['net']['why']
    for x in b['numbers']:
        assert x['note'] and re.search(r'[؀-ۿ]', x['note'])
    # فشل مصدر واحد ⇒ رقمه بس «غير متاح بعد» والباقي سليم
    b2 = L('v2MoneyBoard', {'revenues': REV, 'escrow': None, 'payouts': payouts}, 'day', NOW)
    n2 = {x['key']: x for x in b2['numbers']}
    assert n2['held']['na'] is True and n2['held']['text'] == 'غير متاح بعد' and n2['income']['na'] is False and n2['owed']['na'] is False


@needs_node
def test_money_text_formats_each_currency_in_arabic_digits():
    cases = [((1200, 'EGP'), '١٬٢٠٠ جنيه'), ((600.5, 'EGP'), '٦٠٠٫٥ جنيه'), ((0.25, 'EGP'), '٠٫٢٥ جنيه'), ((30, 'USD'), '٣٠ دولار'),
             ((3500.5, 'SAR'), '٣٬٥٠٠٫٥ ريال'), ((99, 'AED'), '٩٩ درهم'), ((12, 'KWD'), '١٢ دينار'), ((5, 'XYZ'), '٥ XYZ'), ((1234567, 'EGP'), '١٬٢٣٤٬٥٦٧ جنيه')]
    got = [L('util.moneyText', a, c) for (a, c), _ in cases]
    assert got == [w for _, w in cases]
    line = L('v2MoneyLine', [{'currency': 'EGP', 'amount': 1000}, {'currency': 'USD', 'amount': 30}, {'currency': 'SAR', 'amount': 100}])
    assert line['main'] == '١٬٠٠٠ جنيه' and line['othersText'] == 'بعملة أخرى: ٣٠ دولار · ١٠٠ ريال'
    only_foreign = L('v2MoneyLine', [{'currency': 'USD', 'amount': 30}])
    assert only_foreign['main'] == '٠ جنيه' and only_foreign['othersText'] == 'بعملة أخرى: ٣٠ دولار'
    assert L('util.curLong', 'SAR') == 'ريال سعودي' and L('util.curLong', 'QAR') == 'ريال قطري' and L('util.curLong', 'KWD') == 'دينار كويتي'


@needs_node
def test_income_bars_use_the_payments_split_for_the_month_and_the_ledger_otherwise():
    inc = L('v2Income', REV, 'month', NOW)
    led = L('v2IncomeBars', inc, None, 'month')
    assert led['source'] == 'ledger' and [r['label'] for r in led['rows']] == ['ملفات الخبراء', 'الدورات', 'الكتب', 'أخرى']
    assert led['rows'][0]['amount'] == 1000.5 and led['rows'][0]['width'] == 100 and 'الاستشارات العادية' in led['note']
    assert {f['currency'] for f in led['foreign']} == {'USD', 'SAR'}, 'العملات الأجنبية خارج الأعمدة'
    bridge = {'services': [{'key': 'expert_files', 'totals': [{'currency': 'EGP', 'amount': 9300}]}, {'key': 'courses', 'totals': [{'currency': 'EGP', 'amount': 2700}, {'currency': 'SAR', 'amount': 300}]},
                           {'key': 'books', 'totals': [{'currency': 'EGP', 'amount': 1100}]}, {'key': 'other', 'totals': []}]}
    br = L('v2IncomeBars', inc, bridge, 'month')
    assert br['source'] == 'payments' and br['rows'][0]['amount'] == 9300 and br['rows'][3]['amount'] == 0 and br['foreign'] == [{'currency': 'SAR', 'amount': 300}]
    assert L('v2IncomeBars', inc, bridge, 'year')['source'] == 'ledger', 'اليوم والسنة من الدفتر (الجسر شهري)'
    assert L('v2IncomeBars', None, bridge, 'month')['source'] == 'payments', 'الجسر يكفي لو الدفتر وقع'
    assert L('v2IncomeBars', None, None, 'month') is None


def _payout(pid, name, amount, cur='EGP', hours=9, status='pending'):
    return {'kind': 'payout', 'who': name, 'email': pid + '@example.test', 'amount': round(amount), 'currency': cur, 'dest': 'إنستاباي', 'status': status,
            'fx_alert': cur != 'EGP', 'pid': pid, 'raw': {'id': pid, 'amount': amount, 'currency': cur, 'method': 'إنستاباي', 'user_email': pid + '@example.test',
                                                         'created_at': _iso(hours), 'status': status}}


@needs_node
def test_payout_rows_are_oldest_first_with_exact_amounts_and_a_since_timer():
    rows = L('v2PayoutRows', [_payout('po-a', 'منى', 600.5, hours=3), _payout('po-b', 'فيصل', 3500.5, 'SAR', hours=30), _payout('po-c', 'نور', 100, status='paid')], NOW)
    assert [r['id'] for r in rows] == ['po-b', 'po-a'], 'المسدَّد خارج، والأقدم أولًا'
    b, a = rows
    assert b['amountText'] == '٣٬٥٠٠٫٥ ريال' and b['fx'] is True and b['since'] == 'منذ ٣٠ س' and b['what'] == 'سحب من المحفظة'
    assert a['amountText'] == '٦٠٠٫٥ جنيه', 'المبلغ بالكسور مش مقرَّب'
    assert a['card']['primary']['act'] == {'do': 'payout_settle', 'id': 'po-a'} and a['card']['secondary']['act']['do'] == 'payout_reject'
    assert a['card']['primary']['money']['amount'] == 600.5 and a['email'] == 'po-a@example.test'
    assert L('v2PayoutRows', [], NOW) == []


@needs_node
def test_payout_history_is_this_month_only_and_a_failed_half_is_named():
    paid = [{'id': 'p1', 'user_name': 'هالة', 'user_email': 'h@x.test', 'amount': 950.5, 'currency': 'EGP', 'status': 'paid', 'settled_at': _iso(30), 'reference': 'IP-1'},
            {'id': 'p2', 'user_name': 'قديم', 'user_email': 'o@x.test', 'amount': 5, 'currency': 'EGP', 'status': 'paid', 'settled_at': _iso(24 * 40)}]
    rej = [{'id': 'p3', 'user_name': 'سامي', 'user_email': 's@x.test', 'amount': 100, 'currency': 'EGP', 'status': 'rejected', 'rejected_at': _iso(5)}]
    h = L('v2PayoutHistory', paid, rej, NOW)
    assert [r['id'] for r in h['rows']] == ['p3', 'p1'] and h['rows'][0]['statusText'] == 'رُفض' and h['rows'][1]['statusText'] == 'حُوِّل' and h['rows'][1]['ref'] == 'IP-1'
    assert h['rows'][1]['amountText'] == '٩٥٠٫٥ جنيه' and h['failed'] == []
    half = L('v2PayoutHistory', paid, None, NOW)
    assert [r['id'] for r in half['rows']] == ['p1'] and half['failed'] == ['التحويلات المرفوضة']
    assert L('v2PayoutHistory', None, None, NOW) is None


@needs_node
def test_books_are_never_refundable_and_say_why():
    assert L('v2RefundRule', 'book') == {'refundable': False, 'text': 'الكتب لا تُسترد'}
    assert L('v2RefundRule', 'knowledge')['refundable'] is False and L('v2RefundRule', 'BOOK')['refundable'] is False
    for k in ('course', 'consultation', 'plan', '', None):
        assert L('v2RefundRule', k) == {'refundable': True, 'text': ''}
    stuck = L('v2Stuck', {'items': [{'order_id': 'a', 'kind': 'book', 'amount': 149, 'currency': 'EGP', 'age_hours': 5, 'buyer_email': 'o@x.test', 'buyer_name': 'عمر', 'provider': 'paymob'},
                                    {'order_id': 'b', 'kind': 'course', 'amount': 750, 'currency': 'EGP', 'age_hours': 26, 'buyer_email': 'n@x.test', 'buyer_name': '', 'provider': 'stripe'}]}, NOW)
    byid = {r['id']: r for r in stuck['rows']}
    assert byid['a']['refundable'] is False and byid['a']['noRefundText'] == 'الكتب لا تُسترد' and byid['b']['refundable'] is True
    assert [r['id'] for r in stuck['rows']] == ['b', 'a'], 'الأقدم أولًا'
    assert byid['b']['name'] == 'n@x.test' and byid['b']['person'] == {'email': 'n@x.test', 'name': 'n@x.test'}, 'بلا اسم ⇒ البريد، لا اسم مخترع'
    assert byid['a']['kindText'] == 'كتاب' and byid['b']['kindText'] == 'دورة' and byid['b']['provider'] == 'بطاقة بنكية' and byid['b']['ageText'] == 'منذ ٢٦ ساعة'
    assert byid['a']['amountText'] == '١٤٩ جنيه' and stuck['partial'] is False and stuck['deliveryNote'] == ''
    # المنصة بتقول صراحة إن نوع «مدفوع ولم يصل تسليمه» مش مسجَّل (null) ⇒ سطر «غير متاح بعد»، لا سكوت
    nul = L('v2Stuck', {'items': [], 'paid_without_delivery': None}, NOW)
    assert nul['rows'] == [] and nul['deliveryNote'] == 'دفعات تمّ سدادها ولم يصل تسليمها: غير متاح بعد'
    # لا زرّ استرداد في أي صف عالق (قراءة فقط): مفيش act ولا button
    assert all('act' not in r and 'button' not in r for r in stuck['rows'])


@needs_node
def test_refund_rows_come_from_both_sources_and_fail_separately():
    bridge = {'refunds': [{'consultation_id': 'c1', 'member_email': 'salma@x.test', 'amount': 450, 'currency': 'EGP', 'cancelled_at': _iso(52), 'full_refund': True, 'cancelled_by': 'member'},
                          {'consultation_id': 'c2', 'member_email': 'y@x.test', 'amount': 300, 'currency': 'EGP', 'cancelled_at': _iso(8), 'full_refund': False, 'cancelled_by': 'expert'}]}
    disp = [{'id': 'x|unactivated|1|', 'title': 'عقد إيجار', 'amount': '٥٠٠ جنيه', 'client': 'ليلى', 'text': 'مفتوح منذ ٣ س', 'sortAt': NOW - 3 * H, 'reason': 'دُفع المبلغ ولم يصل الملف',
             'row': {'ef': {'kind': 'contract'}}}]
    r = L('v2Refunds', bridge, disp, NOW)
    assert [x['id'] for x in r['rows']] == ['m|c1', 'm|c2', 'd|x|unactivated|1|'] and r['failed'] == []
    full, late, unact = r['rows']
    assert full['brain'].startswith('أُلغي الحجز بالكامل') and 'صاحب الحجز' in full['brain'] and full['act'] == {'do': 'escrow'} and full['button'] == 'افتح وقرّر'
    assert late['brain'].startswith('إلغاء متأخر') and 'الخبير' in late['brain']
    assert unact['act'] == {'do': 'row', 'id': 'x|unactivated|1|'} and unact['amountText'] == '٥٠٠ جنيه' and unact['brain'].startswith('دُفع المبلغ')
    half = L('v2Refunds', None, disp, NOW)
    assert half['failed'] == ['الاستردادات اليدوية'] and len(half['rows']) == 1
    both = L('v2Refunds', None, None, NOW)
    assert both['rows'] == [] and both['failed'] == ['الاستردادات اليدوية', 'الدفعات بلا ملف']


@needs_node
def test_a_truncated_refunds_page_is_flagged_and_a_complete_one_is_not():
    rows = [{'consultation_id': 'c%d' % i, 'member_email': 'a@x.test', 'amount': 100, 'currency': 'EGP', 'cancelled_at': _iso(5 + i), 'full_refund': True} for i in range(3)]
    cut = L('v2Refunds', {'refunds': rows, 'count': 3, 'total': 130, 'next_cursor': 'abc'}, [], NOW)
    assert cut['more'] == {'shown': 3, 'total': 130}
    only_cursor = L('v2Refunds', {'refunds': rows, 'count': 3, 'next_cursor': 'abc'}, [], NOW)
    assert only_cursor['more'] == {'shown': 3, 'total': None}
    full = L('v2Refunds', {'refunds': rows, 'count': 3, 'total': 3, 'next_cursor': ''}, [], NOW)
    assert full['more'] is None
    assert L('v2Refunds', None, [], NOW)['more'] is None
    js = _strip_comments(_read('dashboard-cloud', 'v2-d3.js'))
    assert 'refunds.more' in js, 'القائمة المقصوصة لازم يظهر لها تنبيه في الشاشة'


@needs_node
def test_a_consultation_stuck_payment_is_not_labelled_as_an_expert_file():
    r = L('v2Stuck', {'items': [{'order_id': 'k', 'kind': 'consultation', 'amount': 300, 'currency': 'EGP', 'age_hours': 3, 'buyer_email': 'k@x.test'}]}, NOW)['rows'][0]
    assert r['kindText'] == 'استشارة أو ملف خبير' and r['title'] == 'استشارة أو ملف خبير'


def test_a_course_ledger_row_never_asks_the_books_only_bridge(ctx, plat):
    r = _call(ctx, 'GET', '/api/v2/ads-ledger/c-1?kind=course')
    assert r.status_code == 404 and 'غير متاحة بعد' in r.get_json()['error'] and r.headers.get('Cache-Control') == 'no-store'
    assert plat.seen == [], 'الدورة لا تُسأل عنها المنصة أصلًا: رد الجسر لها ٢٠٠ فارغ كاذب'
    assert _call(ctx, 'GET', '/api/v2/ads-ledger/bk-1?kind=book').status_code == 200
    assert _call(ctx, 'GET', '/api/v2/ads-ledger/bk-1').status_code == 200


def test_the_ledger_drawer_shows_the_row_balance_for_a_course_instead_of_a_false_empty_ledger():
    js = _strip_comments(_read('dashboard-cloud', 'v2-d3.js'))
    body = js[js.index('function openAd('):]
    body = body[:body.index('\n  }\n')]
    course = body[:body.index("E.api('/v2/ads-ledger/'")]
    assert "kind === 'course'" in course and 'حركات الدورات غير متاحة بعد' in course and 'row.balanceText' in course
    assert 'E.api(' not in course, 'ولا نداء للجسر قبل فرع الدورة'
    assert "'?kind=' + encodeURIComponent(kind || 'book')" in body


def test_a_platform_401_or_403_never_logs_the_admin_out(ctx, plat):
    for status in (401, 403):
        plat.ef.forced[('GET', '/api/bridge/payments/stuck')] = (status, {'detail': 'bad secret'})
        r = _call(ctx, 'GET', '/api/v2/payments/stuck')
        assert r.status_code == 502 and r.get_json() == {'error': 'تعذّر الاتصال بالمنصة'} and r.headers.get('Cache-Control') == 'no-store', (status, r.get_json())
        plat.ef.forced[('PUT', '/api/bridge/settings/money')] = (status, {'detail': 'bad secret'})
        n = AuditLog.query.filter_by(action='money_settings.update').count()
        w = _call(ctx, 'PUT', '/api/v2/money/settings', {'withdraw_min': 800, 'confirmed': True})
        assert w.status_code == 502 and w.get_json() == {'error': 'تعذّر الاتصال بالمنصة'}, (status, w.get_json())
        assert AuditLog.query.filter_by(action='money_settings.update').count() == n
    # رفض حقيقي (٤٢٢/٤٠٩) يبقى بحاله
    plat.ef.forced[('GET', '/api/bridge/payments/stuck')] = (409, {'detail': 'x'})
    assert _call(ctx, 'GET', '/api/v2/payments/stuck').status_code == 409


def test_dashboard_authored_proxy_errors_are_plain_arabic(ctx, plat):
    banned = ('مفيش', 'مش ', 'تاني', 'بيوصل', 'لسه', 'ده ')
    errs = [
        _call(ctx, 'PUT', '/api/v2/shares', {'changes': {}, 'version': 1, 'confirmed': True}).get_json()['error'],
        _call(ctx, 'PUT', '/api/v2/shares', {'changes': {'a': 1}, 'version': 'x', 'confirmed': True}).get_json()['error'],
        _call(ctx, 'GET', '/api/v2/ads-ledger/a%20b').get_json()['error'],
        _call(ctx, 'GET', '/api/v2/prices/book/a%20b').get_json()['error'],
        _call(ctx, 'POST', '/api/v2/book-offers/o1/reject', {'confirmed': True, 'reason': ''}).get_json()['error'],
        _call(ctx, 'PATCH', '/api/v2/book-requests/rq-1', {}).get_json()['error'],
    ]
    for e in errs:
        assert not any(b in e for b in banned), e
    assert errs[0] == 'لا تعديل' and errs[1] == 'حدّث الصفحة ثم أعد المحاولة' and errs[4] == 'اكتب سبب الرفض، فهو يصل إلى صاحب العرض'


def test_the_reader_request_approve_button_asks_one_line_first():
    js = _strip_comments(_read('dashboard-cloud', 'v2-d3.js'))
    body = js[js.index("var ok = b.getAttribute('data-a') === 'rqok';"):]
    body = body[:body.index('// ----')] if '// ----' in body else body[:2500]
    assert 'if (!ok) return run();' in body and 'v3_rqgo' in body
    assert body.index('v3_rqgo') < body.rindex('run();'), '«اعتمد» ينشر للأعضاء ⇒ تأكيد قبل النداء'


PRICES_LIST = {'ok': True, 'kind': 'book', 'countries': ['eg', 'sa', 'ae', 'kw', 'qa', 'default'], 'currencies': d3fx.CURRENCIES, 'count': 2, 'items': [
    {'id': 'b1', 'title': 'دليل المستأجر', 'visible': True, 'has_prices': True, 'min_price': {'eg': {'amount': 150, 'currency': 'EGP'}, 'default': {'amount': 9, 'currency': 'USD'}}, 'updated_at': _iso(5)},
    {'id': 'b2', 'title': 'دليل الميراث', 'visible': False, 'has_prices': False, 'min_price': {}, 'updated_at': None}]}
PRICE_DETAIL = {'ok': True, 'countries': PRICES_LIST['countries'], 'currencies': d3fx.CURRENCIES, 'versions_allowed': ['read', 'pdf'],
                'prices': {'kind': 'book', 'id': 'b1', 'title': 'دليل المستأجر', 'visible': True, 'rev': 4, 'updated_by': 'f@x.test', 'updated_at': _iso(5), 'history': [],
                           'versions': {'read': {'eg': {'amount': 150.0, 'currency': 'EGP'}, 'default': {'amount': 9.0, 'currency': 'USD'}}, 'pdf': {'eg': {'amount': 220.0, 'currency': 'EGP'}}}}}


@needs_node
def test_price_rows_show_the_lowest_price_per_country_and_visibility():
    p = L('v2Prices', PRICES_LIST)
    a, b = p['rows']
    assert a['visible'] is True and a['minText'] == 'مصر: ١٥٠ جنيه · باقي البلاد: ٩ دولار' and a['hasPrices'] is True
    assert b['visible'] is False and b['minText'] == 'لا أسعار بعد' and b['hasPrices'] is False


@needs_node
def test_price_form_has_versions_by_countries_with_each_currency_next_to_the_box():
    f = L('v2PriceForm', PRICE_DETAIL)
    assert f['rev'] == 4 and f['visible'] is True and [v['key'] for v in f['versions']] == ['read', 'pdf']
    assert [c['key'] for c in f['countries']] == ['eg', 'sa', 'ae', 'kw', 'qa', 'default']
    cur = {c['key']: (c['currency'], c['currencyName']) for c in f['countries']}
    assert cur['eg'] == ('EGP', 'جنيه مصري') and cur['sa'] == ('SAR', 'ريال سعودي') and cur['qa'] == ('QAR', 'ريال قطري') and cur['default'] == ('USD', 'دولار أمريكي')
    assert f['versions'][0]['cells'] == {'eg': '150', 'sa': '', 'ae': '', 'kw': '', 'qa': '', 'default': '9'} and f['versions'][1]['cells']['eg'] == '220'


@needs_node
def test_a_course_with_no_prices_yet_gets_one_standard_version_not_the_book_ones():
    resp = {'countries': PRICES_LIST['countries'], 'currencies': d3fx.CURRENCIES, 'versions_allowed': None,
            'prices': {'kind': 'course', 'id': 'c1', 'title': 'دورة', 'visible': False, 'rev': 0, 'versions': {}}}
    f = L('v2PriceForm', resp)
    assert [(v['key'], v['label']) for v in f['versions']] == [('standard', 'السعر العادي')]


@needs_node
def test_price_diff_shows_exactly_what_changes_before_to_after():
    f = L('v2PriceForm', PRICE_DETAIL)
    cells = copy.deepcopy({v['key']: v['cells'] for v in f['versions']})
    cells['read']['eg'] = '٢٥٠'            # أرقام عربية مقبولة
    cells['read']['sa'] = '40.5'
    cells['pdf']['eg'] = ''
    built = L('v2PriceBuild', f, {'visible': False, 'cells': cells})
    assert built['ok'] is True and built['visible'] is False
    assert built['versions']['read']['eg'] == {'amount': 250, 'currency': 'EGP'} and built['versions']['read']['sa'] == {'amount': 40.5, 'currency': 'SAR'}
    assert built['versions']['pdf'] == {}, 'خانة فاضية = لا سعر'
    d = L('v2PriceDiff', f, built)
    got = {x['label']: (x['from'], x['to']) for x in d['lines']}
    assert got == {'القراءة على المنصة · مصر': ('١٥٠ جنيه', '٢٥٠ جنيه'), 'القراءة على المنصة · السعودية': ('لا سعر', '٤٠٫٥ ريال'),
                   'نسخة PDF · مصر': ('٢٢٠ جنيه', 'لا سعر'), 'ظاهر للناس': ('نعم', 'لا')}, got
    assert d['changed'] is True
    # بلا تغيير ⇒ بلا سطور
    same = L('v2PriceBuild', f, {'visible': True, 'cells': {v['key']: v['cells'] for v in f['versions']}})
    assert L('v2PriceDiff', f, same) == {'lines': [], 'changed': False}
    # رقم غلط ⇒ رسالة بالبلد والنسخة، ولا إرسال
    bad = L('v2PriceBuild', f, {'visible': True, 'cells': {'read': {'eg': 'abc'}, 'pdf': {}}})
    assert bad['ok'] is False and 'مصر' in bad['error'] and 'لازم يكون رقمًا' in bad['error']
    assert L('v2PriceBuild', f, {'visible': True, 'cells': {'read': {'eg': '-5'}}})['ok'] is False
    assert L('util.parseAmount', '١٬٢٥٠٫٥٠') == 1250.5 and L('util.parseAmount', '') is None and L('util.parseAmount', '1e3') != 1000


SHARES = {'ok': True, 'shares': d3fx.DEFAULT_SHARES, 'version': 3, 'history': [
    {'setting': 'shares', 'by': 'f@x.test', 'at': _iso(30), 'version_before': 2, 'version_after': 3, 'changes': {},
     'before': {'books': {'normal': {'owner': 55, 'platform': 45}, 'ads': {'owner': 65, 'platform': 35}}}, 'after': {'books': {'normal': {'owner': 60, 'platform': 40}, 'ads': {'owner': 65, 'platform': 35}}}}]}


@needs_node
def test_shares_read_in_plain_arabic_with_the_case_ladder():
    v = L('v2SharesView', SHARES)
    lines = {x['key']: x['text'] for x in v['lines']}
    assert lines['books'] == 'صاحب العمل ٦٠٪ · المنصة ٤٠٪' and lines['books_ads'] == 'صاحب العمل ٦٥٪ · المنصة ٣٥٪'
    assert 'من قيمة البيع' in lines['affiliate'] and '١٠٪' in lines['affiliate'] and 'الطرفين' in lines['affiliate']
    assert [x['editable'] for x in v['lines']] == [True, True, False, True], 'الدورات في جولتها'
    assert [r['upTo'] for r in v['ladder']] == ['أقل من ١٠٬٠٠٠ جنيه', 'من ١٠٬٠٠٠ إلى أقل من ٣٠٬٠٠٠ جنيه', 'من ٣٠٬٠٠٠ إلى أقل من ٥٠٬٠٠٠ جنيه', 'من ٥٠٬٠٠٠ جنيه فأكثر']
    assert [r['platformText'] for r in v['ladder']] == ['٣٥٪', '٣٠٪', '٢٥٪', '٢٥٪'] and [r['ownerText'] for r in v['ladder']][0] == '٦٥٪'
    assert v['version'] == 3 and 'لا ينزل عن ٣٥٪' in v['floorText'] and '٢٥٪' in v['floorText']
    hist = L('v2SharesHistory', SHARES, NOW)
    assert hist[0]['by'] == 'f@x.test' and hist[0]['lines'] == [{'label': 'الكتب · صاحب العمل', 'from': '٥٥٪', 'to': '٦٠٪'}, {'label': 'الكتب · المنصة', 'from': '٤٥٪', 'to': '٤٠٪'}]


@needs_node
def test_shares_diff_and_changes_send_only_what_changed():
    t = d3fx.DEFAULT_SHARES
    r = L('v2SharesChanges', t, {'booksOwner': '٦٢', 'booksAdsOwner': '65', 'ladder': ['35', '28', '25', '25'], 'affiliateRate': '12'})
    assert r['ok'] is True
    assert r['changes'] == {'books': {'normal': {'owner': 62, 'platform': 38}}, 'cases': {'ladder': [{'max_egp': 10000, 'platform_pct': 35}, {'max_egp': 30000, 'platform_pct': 28},
                                                                                                   {'max_egp': 50000, 'platform_pct': 25}, {'max_egp': None, 'platform_pct': 25}]},
                            'affiliate': {'rate': 12}}
    d = L('v2SharesDiff', t, r['after'])
    got = {x['label']: (x['from'], x['to']) for x in d['lines']}
    assert got == {'الكتب · صاحب العمل': ('٦٠٪', '٦٢٪'), 'الكتب · المنصة': ('٤٠٪', '٣٨٪'), 'القضايا · من ١٠٬٠٠٠ إلى أقل من ٣٠٬٠٠٠ جنيه': ('المنصة ٣٠٪', 'المنصة ٢٨٪'),
                   'عمولة الإحالة': ('١٠٪', '١٢٪')}, got
    # لا تغيير ⇒ لا إرسال. رقم برّه ٠–١٠٠ ⇒ رسالة. (الأرضية ٣٥ تحرسها المنصة ورسالتها بتتعرض)
    same = L('v2SharesChanges', t, {'booksOwner': '60', 'booksAdsOwner': '65', 'ladder': ['35', '30', '25', '25'], 'affiliateRate': '10'})
    assert same['ok'] is False and same['unchanged'] is True
    assert L('v2SharesChanges', t, {'booksOwner': '101'})['ok'] is False and L('v2SharesChanges', t, {'booksOwner': 'x'})['ok'] is False
    below = L('v2SharesChanges', t, {'booksOwner': '70'})
    assert below['ok'] is True and below['changes']['books']['normal'] == {'owner': 70, 'platform': 30}, 'الشاشة ما تحكمش في الأرضية — المنصة هي اللي ترفض'


@needs_node
def test_minimum_payout_view_and_input_rules():
    resp = {'ok': True, 'withdraw_min': 500, 'rev': 2, 'updated_at': _iso(30), 'updated_by': 'f@x.test', 'allowed': {'withdraw_min': {'min': 50, 'max': 20000}},
            'history': [{'by': 'f@x.test', 'at': _iso(30), 'before': {'withdraw_min': 400}, 'after': {'withdraw_min': 500}}]}
    v = L('v2MinPayout', resp, NOW)
    assert v['text'] == '٥٠٠ جنيه' and v['rev'] == 2 and v['min'] == 50 and v['max'] == 20000
    assert v['history'][0]['from'] == '٤٠٠ جنيه' and v['history'][0]['to'] == '٥٠٠ جنيه'
    assert L('v2MinPayoutInput', '٧٥٠', v) == {'ok': True, 'value': 750}
    for bad in ('', 'abc', '10.5', '49', '20001', '-3'):
        assert L('v2MinPayoutInput', bad, v)['ok'] is False, bad
    assert L('v2MinPayout', {'withdraw_min': '500'}, NOW) is None
    # ملاحظات التأثير بفصحى من عندنا (نص المنصة العامي ما بيتعرضش)، وبتظهر بس لو المنصة بعتت `notes`
    assert v['notes'] == []
    got = L('v2MinPayout', dict(resp, notes=d3fx.MONEY_NOTES), NOW)['notes']
    assert got == ['الحد الأدنى يظهر في اتفاقية المدرّبين. تغييره يغيّر نص الاتفاقية عند من وقّعها قبل ذلك أيضًا، ولا يُطلب منهم التوقيع من جديد.',
                   'سحب الرصيد كاملًا في طلب واحد مسموح دائمًا مهما كان الحد.', 'يسري التعديل فورًا، وقد يتأخر في بعض الحالات حتى ٣٠ ثانية.'], got
    assert 'بيظهر' not in ' '.join(got) and 'بتلحق' not in ' '.join(got), 'نص المنصة العامي ما بيتعرضش'


@needs_node
def test_ads_ledger_rows_and_entries():
    resp = {'items': [{'owner_kind': 'book', 'owner_id': 'a', 'balance': [{'currency': 'EGP', 'amount': 1850}], 'last_entry_at': _iso(4), 'owner_email': 'n@x.test', 'entries': 5, 'title': 'دليل المستأجر'},
                      {'owner_kind': 'course', 'owner_id': 'c', 'balance': [{'currency': 'SAR', 'amount': 600}, {'currency': 'EGP', 'amount': 5}], 'last_entry_at': _iso(200), 'owner_email': '', 'title': ''}]}
    rows = L('v2AdsLedger', resp, NOW)
    assert [r['id'] for r in rows] == ['a', 'c'] and rows[0]['balanceText'] == '١٬٨٥٠ جنيه' and rows[0]['last'] == 'منذ ٤ ساعات' and rows[0]['ownerEmail'] == 'n@x.test'
    assert rows[1]['title'] == 'عمل بلا عنوان' and rows[1]['kindText'] == 'دورة' and rows[1]['balanceText'] == '٥ جنيه · ٦٠٠ ريال' and rows[1]['ownerEmail'] == ''
    ent = L('v2AdsEntries', {'balance': [{'currency': 'EGP', 'amount': 1850}], 'entries': [
        {'entry': 'deposit', 'amount': 2000, 'currency': 'EGP', 'at': _iso(24 * 9)}, {'entry': 'spend', 'amount': 150, 'currency': 'EGP', 'at': _iso(24 * 3)}]}, NOW)
    assert [(e['entry'], e['sign']) for e in ent['rows']] == [('صرف على الإعلانات', '−'), ('إيداع', '+')] and ent['balance']['main'] == '١٬٨٥٠ جنيه'


@needs_node
def test_offer_line_is_facts_only_from_the_offer_fields():
    avg_eg = {'avg': 200.0, 'n': 3, 'currency': 'EGP'}
    offer = {'suggested_price': {'amount': 260, 'currency': 'EGP'}, 'agreement': {'platform_pct': 40, 'plan_label': 'نشر عادي'}}
    assert L('v2OfferLine', offer, {'eg': avg_eg}) == 'السعر أعلى من متوسط الكتب في مصر بـ٣٠٪ · اتفاقية البيع: نصيب المنصة ٤٠٪'
    assert L('v2OfferLine', dict(offer, suggested_price={'amount': 150, 'currency': 'EGP'}), {'eg': avg_eg}).startswith('السعر أقل من متوسط الكتب في مصر بـ٢٥٪')
    assert L('v2OfferLine', dict(offer, suggested_price={'amount': 202, 'currency': 'EGP'}), {'eg': avg_eg}).startswith('السعر قريب من متوسط الكتب في مصر')
    # لا شيء للمقارنة ⇒ لا سطر مقارنة (ولا حكم مخترع)
    assert L('v2OfferLine', offer, {}) == 'اتفاقية البيع: نصيب المنصة ٤٠٪'
    assert L('v2OfferLine', dict(offer, suggested_price={'amount': 20, 'currency': 'USD'}), {'eg': avg_eg}) == 'اتفاقية البيع: نصيب المنصة ٤٠٪', 'عملة بلا متوسط مطابق ⇒ لا مقارنة'
    assert L('v2OfferLine', {'suggested_price': None, 'agreement': None}, {}) == 'لم يقترح صاحب العرض سعرًا · لم يوافق صاحب العرض على اتفاقية البيع بعد'
    # المتوسط من كتابين ظاهرين على الأقل في نفس البلد
    one = {'items': [{'visible': True, 'min_price': {'eg': {'amount': 100, 'currency': 'EGP'}}}]}
    assert L('v2BookAverage', one, 'eg') is None
    two = {'items': [{'visible': True, 'min_price': {'eg': {'amount': 100, 'currency': 'EGP'}}}, {'visible': True, 'min_price': {'eg': {'amount': 300, 'currency': 'EGP'}}},
                     {'visible': False, 'min_price': {'eg': {'amount': 9000, 'currency': 'EGP'}}}]}
    assert L('v2BookAverage', two, 'eg') == {'avg': 200, 'n': 2, 'currency': 'EGP'}


@needs_node
def test_offers_queue_rows_and_the_prefilled_prices():
    resp = {'offers': d3fx.OFFERS}
    rows = L('v2OffersQueue', resp, PRICES_LIST, NOW)
    assert [r['id'] for r in rows] == ['off-1', 'off-2']
    a = rows[0]
    assert a['title'].startswith('عقد الوكالة') and a['ownerName'] == 'أ. مي حسن' and a['suggestedText'] == '٣٩٠ جنيه' and a['typeText'] == 'دليل' and a['agreementText'] == 'نشر عادي'
    assert rows[1]['suggestedText'] == '' and 'لم يقترح' in rows[1]['brain']
    form = L('v2PriceForm', PRICE_DETAIL)
    cells = L('v2OfferPrefill', a, form)
    assert cells['read']['eg'] == '390' and cells['read']['default'] == '' and cells['pdf']['eg'] == ''
    # يظهر في الطابور فقط ما هو «في المراجعة»
    done = L('v2OffersQueue', {'offers': [dict(d3fx.OFFERS[0], status='live')]}, None, NOW)
    assert done == []


@needs_node
def test_reader_requests_group_with_counts_and_state():
    resp = {'groups': d3fx._groups(d3fx.REQUESTS), 'requests': d3fx.REQUESTS}
    v = L('v2Requests', resp, NOW)
    assert [g['key'] for g in v['open']] == ['g-rent', 'g-sole'] and [g['key'] for g in v['approved']] == ['g-data']
    g = v['open'][0]
    assert g['countText'] == '٣ طلبات' and g['topic'] == 'كتاب عن قانون الإيجار القديم' and g['typeText'] == 'كتاب' and g['firstId'] == 'rq-1'
    assert v['approved'][0]['topic'] == 'حماية البيانات الشخصية', 'نص الإدارة المعتمد يغلب'
    hid = copy.deepcopy(resp)
    for r in hid['requests']:
        if r['group_key'] == 'g-sole':
            r['hidden'] = True
    assert [x['key'] for x in L('v2Requests', hid, NOW)['open']] == ['g-rent']


QUEUE = {'wallet_payouts_pending': {'count': 4, 'total_amount': 9}, 'manual_payments_pending': {'count': 1}, 'stuck_card_payments': {'count': 2},
         'manual_refunds_pending': 5, 'course_split_pending': {'count': 3}}


@needs_node
def test_the_money_badge_counts_payouts_receipts_stuck_and_refunds():
    b = L('v2MoneyBadge', QUEUE)
    # المجموع كما في المواصفة بالحرف: اقتسام الدورات المعلّق (course_split_pending) ليس منه، حتى لو جاء في الطابور
    assert b['parts'] == {'payouts': 4, 'receipts': 1, 'stuck': 2, 'refunds': 5} and b['total'] == 4 + 1 + 2 + 5
    assert L('v2MoneyBadge', None) is None
    ex = {'inbox': [], 'now': NOW}
    t = {x['key']: x for x in L('v2Tiles', QUEUE, ex)}['money']
    assert t['count'] == 12 and t['hot'] is True
    assert 'اقتسام' not in t['next'], t['next']
    assert '٥ استردادات تنتظر قرارك' in t['next'] and '٤ تحويلات' in t['next'] and 'إيصال' in t['next'] and 'دفعتان عالقتان' in t['next'], t['next']
    t2 = {x['key']: x for x in L('v2Tiles', None, ex)}['money']
    assert t2['count'] is None and t2['failed'] is True, 'الطابور تعذّر ⇒ لا رقم'
    q0 = {k: {'count': 0} if k != 'manual_refunds_pending' else 0 for k in QUEUE}
    assert {x['key']: x for x in L('v2Tiles', q0, ex)}['money']['count'] == 0


@needs_node
def test_the_books_tile_adds_the_offers_and_a_failed_offers_source_is_partial_not_zero():
    ex = {'inbox': [{'apiKind': 'book', 'ref': 'K1'}], 'now': NOW}
    base = {x['key']: x for x in L('v2Tiles', QUEUE, ex)}['books']
    assert base['count'] == 1 and base['partial'] is False
    with_offers = {x['key']: x for x in L('v2Tiles', QUEUE, dict(ex, bookOffers=2))}['books']
    assert with_offers['count'] == 3 and with_offers['next'].startswith('عرضان ينتظران المراجعة')
    failed = {x['key']: x for x in L('v2Tiles', QUEUE, dict(ex, bookOffers=None))}['books']
    assert failed['count'] == 1 and failed['partial'] is True and failed['next'].startswith('العدد ناقص')
    zero = {x['key']: x for x in L('v2Tiles', QUEUE, dict(ex, bookOffers=0))}['books']
    assert zero['count'] == 1 and zero['partial'] is False


@needs_node
def test_two_new_decision_cards_a_stuck_payment_and_a_book_offer():
    stuck = L('v2Stuck', {'items': d3fx.STUCK_ITEMS}, NOW)['rows']
    offers = L('v2OffersQueue', {'offers': d3fx.OFFERS}, PRICES_LIST, NOW)
    cards = L('v2Decisions', [], [], None, {'now': NOW, 'stuck': stuck, 'offers': offers})
    kinds = [c['kind'] for c in cards]
    assert kinds.count('stuck_payment') == 3 and kinds.count('book_offer') == 2
    assert kinds.index('stuck_payment') < kinds.index('book_offer'), 'المال قبل مراجعة الكتب'
    sp = next(c for c in cards if c['kind'] == 'stuck_payment' and c['title'] == 'نور الهدى سالم')
    assert sp['tag'] == 'دفعة عالقة' and sp['primary'] == {'label': 'افتح الشخص', 'act': {'do': 'person', 'email': 'nour@example.test'}}
    assert sp['person'] == {'email': 'nour@example.test', 'name': 'نور الهدى سالم'} and 'money' not in json.dumps(sp['primary']) and sp['secondary'] is None
    book = next(c for c in cards if c['kind'] == 'stuck_payment' and 'دليل' in c['brain'] + c['sub'])
    assert book['warn'] == 'الكتب لا تُسترد'
    off = next(c for c in cards if c['kind'] == 'book_offer')
    assert off['tag'] == 'عرض كتاب للمراجعة' and off['primary']['label'] == 'اعتمد بالأسعار دي' and off['primary']['act'] == {'do': 'offer_approve', 'id': 'off-1'}
    assert off['secondary']['label'] == 'ارفض' and off['secondary']['act']['do'] == 'offer_reject' and off['open'] == {'do': 'section', 'section': 'books', 'tab': 'offers'}
    # الاستردادات ما فيهاش زرّ فلوس في بطاقة الدفعة العالقة
    assert all('money' not in json.dumps(c['primary']) for c in cards if c['kind'] == 'stuck_payment')


@needs_node
def test_the_stuck_source_can_fall_back_to_the_queue_orders():
    q = {'stuck_card_payments': {'count': 2, 'orders': [{'id': 'o1', 'user_email': 'a@x.test', 'amount': 750, 'currency': 'EGP', 'kind': 'course', 'gateway': 'paytabs', 'created_at': _iso(26)}]}}
    r = L('v2StuckFromQueue', q)
    assert r['rows'][0]['id'] == 'o1' and r['rows'][0]['email'] == 'a@x.test' and r['rows'][0]['name'] == 'a@x.test'
    assert L('v2StuckFromQueue', {'stuck_card_payments': {'count': 2}}) is None and L('v2StuckFromQueue', None) is None


# ---------------------------------------------------------------- الأقسام والتبويبات

@needs_node
def test_the_money_and_books_sections_have_the_new_tabs_and_the_old_ones_last():
    secs = {s['key']: s for s in L('SECTIONS')}
    vis = lambda k: [(t['key'], t['label'], t['mod']) for t in secs[k]['tabs'] if not t.get('hidden')]
    assert vis('money') == [('overview', 'نظرة', 'v2m_overview'), ('payouts', 'التحويلات', 'v2m_payouts'), ('receipts', 'الإيصالات والمدفوعات العالقة', 'v2m_receipts'),
                            ('prices', 'الأسعار', 'v2m_prices'), ('shares', 'النسب والإعدادات', 'v2m_shares'), ('ads', 'إعلانات الأعمال', 'v2m_ads'), ('all', 'كل السجلات', 'finance')]
    assert vis('books') == [('offers', 'مراجعة العروض', 'v2b_offers'), ('requests', 'طلبات القرّاء', 'v2b_requests'), ('books', 'الكتب والأعمال', 'knowledge')]
    assert secs['money']['tabs'][0]['key'] == 'overview' and secs['books']['tabs'][0]['key'] == 'offers'


@needs_node
def test_old_links_still_land_somewhere_sensible():
    land = lambda mod, st: (lambda r: (r['section'], r['tab']))(L('sectionFor', mod, st))
    assert land('finance', {'finTab': 'summary'}) == ('money', 'all') and land('finance', {'finTab': 'packages'}) == ('money', 'all')
    assert land('finance', {'finTab': 'withdrawals'}) == ('money', 'all') and land('finance', {'finTab': 'stuck'}) == ('money', 'all')
    assert land('escrow', {'escTab': 'manual'}) == ('money', 'manual') and land('escrow', {'escTab': 'sessions'}) == ('disputes', 'escrow')
    assert land('knowledge', {}) == ('books', 'books')
    assert L('routeFor', '#s/money', {})['tab'] == 'overview' and L('routeFor', '#s/money/prices', {})['mod'] == 'v2m_prices'
    assert L('routeFor', '#s/books', {})['mod'] == 'v2b_offers' and L('routeFor', '#packages', {})['section'] == 'money'
    assert L('parseSectionHash', '#s/money/manual')['tab'] == 'overview', 'التبويب المخفي ما بيتفتحش بالعنوان'


# ---------------------------------------------------------------- نصوص ظاهرة

BANNED = ['يقوّم', 'يقوم بتقييم', 'الذكاء الاصطناعي', 'Stripe', 'Paymob', 'endpoint', 'JSON', 'Backend', 'طابور', 'API']


@needs_node
def test_visible_texts_are_plain_and_nothing_starts_with_ai():
    texts = []
    b = L('v2MoneyBoard', {'revenues': REV, 'escrow': [{'amount': 5, 'currency': 'USD', 'status': 'held'}], 'payouts': []}, 'month', NOW)
    for n in b['numbers']:
        texts += [n['label'], n['note'], n['text'], n['others'], n['why']]
    texts += [x['label'] for x in L('v2IncomeBars', L('v2Income', REV, 'month', NOW), None, 'month')['rows']]
    v = L('v2SharesView', SHARES)
    texts += [x['title'] + x['text'] + x.get('note', '') for x in v['lines']] + [v['floorText']]
    for t in L('SECTIONS'):
        if t['key'] in ('money', 'books'):
            texts += [t['label'], t['desc']] + [x['label'] for x in t['tabs']]
    for s in L('v2Stuck', {'items': d3fx.STUCK_ITEMS}, NOW)['rows']:
        texts += [s['kindText'], s['provider'], s['ageText'], s['noRefundText']]
    for t in texts:
        for bad in BANNED:
            assert bad not in t, (bad, t)
        assert not re.match(r'^\s*(ذكاء|AI)\b', t), t
        assert not re.search(r'(?<![\w@./-])(null|undefined|NaN)(?![\w@./-])', t), t
    src = _read('dashboard-cloud', 'v2-logic.js')
    code = _strip_comments(src[src.index('«الفلوس» على الهيكل الجديد (D3)'):src.index('  var api = {')])
    for bad in ('يقوّم', 'يقوم'):
        assert bad not in code


def _strip_comments(src):
    src = re.sub(r'/\*.*?\*/', '', src, flags=re.S)
    return '\n'.join(re.sub(r'(^|\s)//.*$', '', ln) for ln in src.split('\n'))


# ---------------------------------------------------------------- ٣) الملفات والخطّافات

DC = os.path.join(ROOT, 'dashboard-cloud')


def test_the_files_are_wired_and_shipped():
    html = _read('dashboard-cloud', 'index.html')
    assert '<link rel="stylesheet" href="v2-d3.css">' in html and '<script src="v2-d3.js"></script>' in html
    assert html.index('v2-d2.js') < html.index('v2-d3.js') and html.index('v2-d2.css') < html.index('v2-d3.css')
    for df in ('Dockerfile', os.path.join('deploy', 'Dockerfile.coolify')):
        txt = _read(df)
        assert 'dashboard-cloud/v2-d3.js' in txt and 'dashboard-cloud/v2-d3.css' in txt, df
    for f in ('v2-d3.js', 'v2-d3.css'):
        assert os.path.getsize(os.path.join(DC, f)) > 5000


def test_the_hooks_do_nothing_when_the_switch_is_off():
    html = _read('dashboard-cloud', 'index.html')
    assert "if(window.V2_ON&&window.V2D3&&V2D3.owns(current))return V2D3.render(current,v);" in html
    assert "if(window.V2D3&&V2D3.owns(current))ap.classList.add('v2-bare');" in html
    # الموديولات الوهمية ما لها تعريف في القائمة القديمة
    mods = html[html.index('const MODULES={'):html.index('// موديولات الأدوار غير-الأدمن')]
    for m in ('v2m_overview', 'v2m_payouts', 'v2m_receipts', 'v2m_prices', 'v2m_shares', 'v2m_ads', 'v2b_offers', 'v2b_requests'):
        assert m not in mods
    api = _read('dashboard-cloud', 'dashboard-api.js')
    assert 'V2D3' not in api and 'v2m_' not in api
    home = _read('dashboard-cloud', 'v2-home.js')
    assert "window.V2D3 && window.V2SHELL && V2SHELL.on" in home, 'عدّاد عروض الكتب مشروط بالغلاف'
    shell = _read('dashboard-cloud', 'v2-shell.js')
    assert 'V2D3' not in shell


def test_the_money_sheets_reuse_the_existing_confirmation_and_add_no_new_decision_path():
    home = _read('dashboard-cloud', 'v2-home.js')
    assert 'V2.openMoney = function (c, a, onDone)' in home
    assert 'alt: S.ext ? { label:' in home, '«ارفض» جوه ورقة التسجيل بس لما الفتح من شاشة الفلوس'
    assert re.search(r"function run\(c, a\) \{[^}]*?S\.ext = null;", home, re.S), 'الفتح من اللوحة يلغي أي فتح خارجي معلّق'
    assert "if (S.ext && S.ext.id === c.id)" in home
    # المسارات الجديدة: كل كتابة PUT/POST بتبعت confirmed:true، والـPATCH (طلبات القرّاء) بلا فلوس
    js = _strip_comments(_read('dashboard-cloud', 'v2-d3.js'))
    calls = re.findall(r"E\.api\([^;]*?method: '(PUT|POST|PATCH)'[^;]*?\}\s*\)", js, re.S)
    assert calls.count('PUT') == 3 and calls.count('POST') == 2 and calls.count('PATCH') == 1, calls
    for m in re.finditer(r"E\.api\(([^;]*?method: '(PUT|POST)'[^;]*?)\)\.then|E\.api\(([^;]*?method: '(PUT|POST)'[^;]*?)\);\s*\}", js, re.S):
        assert 'confirmed: true' in (m.group(1) or m.group(3)), m.group(0)[:160]
    assert 'fetch(' not in js and 'XMLHttpRequest' not in js
    paths = set(re.findall(r"E\.api\('(/[^'?]*)", js)) | set(re.findall(r"'(/v2/[^'?]*)", js)) | set(re.findall(r"function \(\) \{ return '(/[^'?]*)", js))
    assert all(p.startswith('/v2/') or p in ('/revenues', '/platform-wallet-payouts') for p in paths), paths


def test_no_money_decision_is_made_from_a_row_without_the_sheet():
    js = _strip_comments(_read('dashboard-cloud', 'v2-d3.js'))
    # أزرار التحويل والإيصال بتفتح V2.openMoney بس (ورقة التأكيد القديمة)، مفيش E.post مباشر لتحويل أو إيصال
    assert 'E.post(' not in js and 'platform-wallet-payouts/' not in js and 'decideInboxItem' not in js
    assert js.count('V2.openMoney(') == 2


def test_touch_targets_and_mobile_rules_are_in_the_css():
    css = _read('dashboard-cloud', 'v2-d3.css')
    assert re.search(r'\.v3-btn1,\.v3-btn2\{[^}]*min-height:48px', css)
    mob = css[css.index('@media(max-width:760px)'):]
    assert 'min-height:52px' in mob and '.v3-nums{grid-template-columns:minmax(0,1fr)}' in mob and '.v3m .acts .btn{min-height:52px' in mob
    assert '.v3-twocol,.v3-tgrid{grid-template-columns:minmax(0,1fr)}' in mob
    assert 'prefers-reduced-motion' in css
    # كل القواعد تحت `.v3`/`.v3m`/`#epModal` (مفيش أثر على أي شاشة قديمة)
    bare = re.sub(r'/\*.*?\*/', '', css, flags=re.S)
    for sel in re.findall(r'([^{}]+)\{', bare):
        sel = sel.strip()
        if sel.startswith('@') or re.match(r'^[\d.]+%|^from$|^to$', sel):
            continue
        for part in sel.split(','):
            assert part.strip().startswith(('.v3', '#epModal')), part


BANNED_IN_D3 = ['يقوّم', 'يقوم بتقييم', 'طابور', 'Backend', 'endpoint', 'JSON', 'بروف', 'الذكاء الاصطناعي']


def test_visible_text_in_the_screens_is_plain_and_never_starts_with_ai():
    code = _strip_comments(_read('dashboard-cloud', 'v2-d3.js'))
    for bad in BANNED_IN_D3:
        assert bad not in code, bad
    for m in re.finditer(r"'([^']*[؀-ۿ][^']*)'", code):
        assert not re.match(r'^\s*(ذكاء|AI)\b', m.group(1)), m.group(1)
    for w in ('ملفاته', 'دوراته', 'فلوسه', 'راسله', 'ينشر اسمه', 'عليه نزاع'):
        assert not re.search(r'(?<![؀-ۿ])%s(?![؀-ۿ])' % w, code), w


def test_every_failed_source_has_a_visible_na_path_in_the_screens():
    js = _read('dashboard-cloud', 'v2-d3.js')
    assert js.count("غير متاح بعد") >= 1 and "function unavailable(" in js
    for fn in ('drawOverview', 'drawPayouts', 'drawReceipts', 'drawPrices', 'drawShares', 'drawAds', 'drawOffers', 'drawRequests'):
        body = js[js.index('function %s(' % fn):]
        body = body[:body.index('\n  }\n')]
        if fn == 'drawPrices':
            body += js[js.index('function priceBlock('):js.index('function drawPrices(')]     # الرسالة في الدالة المشتركة بين الكتب والدورات
        assert 'unavailable(' in body or 'warnStrip(' in body, fn + ': مصدر ممكن يفشل بلا رسالة'
