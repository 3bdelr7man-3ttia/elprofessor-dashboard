# -*- coding: utf-8 -*-
"""سعر الدورة لكل بلد من الداشبورد (r25) — المكان الوحيد: `PUT /api/v2/courses/<id>/prices`.

Run:  cd backend && python3 -B -m pytest -q -p no:cacheprovider tests/test_course_prices_r25.py

⛔ صفر شبكة حقيقية: `requests.request` مُعترَض. اللي بيثبّته:
  ١. المسار أدمن بس · المفتاح مقفول ٤٠٤ · الكتابة تطلب `confirmed:true` · بلاد من القايمة بس · مبالغ بس (العملة ما بتسافرش من هنا).
  ٢. فاضي/صفر = شيل سعر البلد (null) · سعر سالب/نص ⇒ ٤٠٠ قبل أي نداء.
  ٣. ما فيش لا حقل `price_*` ولا `pricing` بيتبعت للمنصة من المسار ده (بس `prices`).
  ٤. المرآة القديمة (`PUT /api/courses/<id>`) ما بتكتبش صفر فوق سعر المنصة.
  ٥. بروكسي `PUT /api/platform-courses/<id>` بيمرّر `prices` (مبالغ بس).
  ٦. الواجهة: ما بقاش رابط «غيّر السعر من الفلوس»، ولا لوحة «أسعار الدورات» الميتة.
"""
import datetime
import json
import os

import jwt
import pytest
from werkzeug.security import generate_password_hash

from app import app as flask_app, db, User, AuditLog, Course  # noqa: E402

_HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(_HERE))
PLATFORM = 'https://platform.test'


def _read(*parts):
    with open(os.path.join(ROOT, *parts), encoding='utf-8') as fh:
        return fh.read()


class _Resp(object):
    def __init__(self, status, payload):
        self.status_code = status
        self._p = payload
        self.content = json.dumps(payload, ensure_ascii=False).encode('utf-8')
        self.headers = {'Content-Type': 'application/json'}
        self.text = self.content.decode('utf-8')

    def json(self):
        return self._p


def _mkuser(email, role):
    u = User.query.filter_by(email=email).first()
    if not u:
        u = User(email=email, password_hash=generate_password_hash('x', method='pbkdf2:sha256'), name=email.split('@')[0],
                 role=role, dashboard_role=role, linked_to_name='', preferred_currency='AUTO', is_active=True)
        db.session.add(u)
    u.role = u.dashboard_role = role
    u.is_active = True
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
        heads = {r: _bearer(_mkuser('prc-%s@x.test' % r, r)) for r in ('admin', 'employee', 'trainer', 'viewer')}
        yield {'heads': heads, 'client': flask_app.test_client()}


@pytest.fixture
def plat(monkeypatch):
    import app as appmod
    seen = []
    box = {'status': 200, 'payload': {'id': 'pc-1', 'pricing': {}}}

    def fake(method, url, params=None, json=None, headers=None, timeout=None):
        seen.append({'method': method.upper(), 'path': url[len(PLATFORM):] if url.startswith(PLATFORM) else url, 'json': json})
        if not url.startswith(PLATFORM + '/'):
            raise RuntimeError('طلب حقيقي ممنوع: ' + url)
        return _Resp(box['status'], box['payload'])
    monkeypatch.setattr(appmod, 'PLATFORM_METRICS_SECRET', 'test-metrics-secret')
    monkeypatch.setattr(appmod, 'PLATFORM_API_URL', PLATFORM)
    monkeypatch.setattr(appmod.requests, 'request', fake)
    monkeypatch.setattr(appmod.requests, 'put', lambda url, json=None, headers=None, timeout=None: (seen.append({'method': 'PUT', 'path': url[len(PLATFORM):], 'json': json}) or _Resp(200, {})))
    monkeypatch.setenv('DASH_V2_ENABLED', 'true')
    return {'seen': seen, 'box': box}


def _put(ctx, path, body, role='admin'):
    return ctx['client'].put(path, json=body, headers=ctx['heads'][role])


URL = '/api/v2/courses/pc-1/prices'


def test_only_admin_and_needs_confirmation(ctx, plat):
    body = {'prices': {'eg': 300}}
    for role in ('employee', 'trainer', 'viewer'):
        assert _put(ctx, URL, dict(body, confirmed=True), role).status_code == 403
    r = _put(ctx, URL, body)
    assert r.status_code == 400
    assert plat['seen'] == []


def test_key_closed_is_404_without_any_call(ctx, plat, monkeypatch):
    monkeypatch.setenv('DASH_V2_ENABLED', 'false')
    assert _put(ctx, URL, {'prices': {'eg': 300}, 'confirmed': True}).status_code == 404
    assert plat['seen'] == []


def test_sends_only_amounts_per_country_and_audits(ctx, plat):
    r = _put(ctx, URL, {'confirmed': True, 'prices': {'eg': 300, 'SA': 150, 'ae': '', 'default': 40, 'kw': 0},
                        'price_egp': 9, 'pricing': {'eg': {'amount': 1}}, 'currency': 'USD'})
    assert r.status_code == 200, r.get_data(as_text=True)
    (w,) = [c for c in plat['seen'] if c['method'] != 'GET']
    assert w['method'] == 'PUT' and w['path'] == '/api/bridge/courses/pc-1'
    sent = w['json']
    assert set(sent) == {'prices'}
    assert sent['prices']['eg'] == 300.0 and sent['prices']['sa'] == 150.0 and sent['prices']['default'] == 40.0
    assert sent['prices']['ae'] is None and sent['prices']['kw'] is None
    a = AuditLog.query.filter_by(action='course.prices').order_by(AuditLog.id.desc()).first()
    assert a and a.target == 'pc-1' and '300' not in (a.meta_json or '')


@pytest.mark.parametrize('prices', [None, {}, [], {'fr': 10}, {'eg': -5}, {'eg': 'abc'}, {'eg': True}, {'eg': 99999999999}])
def test_bad_input_is_400_before_any_call(ctx, plat, prices):
    r = _put(ctx, URL, {'confirmed': True, 'prices': prices})
    assert r.status_code == 400
    assert plat['seen'] == []


def test_string_amount_is_refused_but_blank_is_a_removal(ctx, plat):
    # نص رقمي غير مسموح (الواجهة بتبعت أرقام) · الفاضي بس = شيل
    assert _put(ctx, URL, {'confirmed': True, 'prices': {'eg': '300'}}).status_code == 400
    assert _put(ctx, URL, {'confirmed': True, 'prices': {'eg': 300, 'sa': ''}}).status_code == 200


def test_platform_422_arabic_reason_passes_through(ctx, plat):
    plat['box']['status'] = 422
    plat['box']['payload'] = {'detail': 'حدّد سعر مصر أولًا — هو الإلزامي للدورة المدفوعة، وبعدها سعر أي بلد تانية.'}
    r = _put(ctx, URL, {'confirmed': True, 'prices': {'sa': 100}})
    assert r.status_code == 422 and 'مصر' in json.dumps(r.get_json(), ensure_ascii=False)


def test_legacy_mirror_never_writes_zero_over_the_platform_price(ctx, plat):
    c = Course(title='دورة مرآة', trainer_name='x', status='active', price_egp=0, price_usd=0, platform_course_id='pc-9')
    db.session.add(c)
    db.session.commit()
    r = ctx['client'].put('/api/courses/%d' % c.id, json={'price_egp': 0, 'price_usd': 0, 'title': 'دورة مرآة 2'}, headers=ctx['heads']['admin'])
    assert r.status_code == 200
    sent = [x['json'] for x in plat['seen'] if x['method'] == 'PUT'][-1]
    assert 'price_egp' not in sent and 'price_usd' not in sent and sent['title'] == 'دورة مرآة 2'
    r = ctx['client'].put('/api/courses/%d' % c.id, json={'price_egp': 450}, headers=ctx['heads']['admin'])
    assert [x['json'] for x in plat['seen'] if x['method'] == 'PUT'][-1] == {'price_egp': 450}


def test_platform_courses_proxy_passes_prices_amounts_only(ctx, plat):
    r = _put(ctx, '/api/platform-courses/pc-1', {'prices': {'sa': 150, 'ae': None, 'eg': ''}, 'title': 'ت'})
    assert r.status_code == 200
    w = [x for x in plat['seen'] if x['method'] == 'PUT'][-1]
    assert w['json']['prices'] == {'sa': 150.0, 'ae': None, 'eg': None}
    assert _put(ctx, '/api/platform-courses/pc-1', {'prices': {'sa': 'x'}}).status_code == 400


def test_ui_has_one_price_place():
    d3 = _read('dashboard-cloud', 'v2-d3.js')
    courses = _read('dashboard-cloud', 'v2s', 'courses.js')
    idx = _read('dashboard-cloud', 'index.html')
    assert 'data-t="prices"' not in courses and 'غيّر السعر من «الفلوس»' not in courses
    assert 'pricesCourse' not in d3 and 'أسعار الدورات' not in d3
    assert 'id="e_price"' not in idx, 'الشاشة القديمة ما بقاش فيها خانة سعر تانية'
    assert '/prices' in courses and 'السعر بره مصر' in courses
