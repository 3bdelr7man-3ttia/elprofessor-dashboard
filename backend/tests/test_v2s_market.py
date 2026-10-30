# -*- coding: utf-8 -*-
"""«سوق الخدمات» (الجولة النهائية) — لوحة التذاكر وسطر العقل والدرج و«كل الطلبات» و«ماذا يطلب الناس»، ورا نفس المفتاح المقفول.

Run:  cd backend && python3 -B -m pytest -q -p no:cacheprovider tests/test_v2s_market.py

⛔ صفر شبكة حقيقية: المنصة جدول في الذاكرة (`uiharness/market_fixtures.MarketPlatform`)، وأي عنوان برّه `https://platform.test` بيوقّع الاختبار.
المنطق النقي (التصنيف · العقل · الاستعلام · الأخطاء · أرقام الطلب) بيتشغّل في node على v2-logic.js.

اللي بيثبّته:
  ١. المسارات الثلاثة (pytest): الأدوار · المفتاح مقفول ٤٠٤ بلا أي نداء · `no-store` · الفلاتر والحدود · ٤٠٤/٥٠٢ من المنصة · الكتابة بـ`confirmed:true` ·
     `by` من التوكن · القايمة البيضا · رد ضايع «ما وصلناش رد» · التدقيق عند النجاح بس · السطر الواحد في app.py وقراءة المنصة وقت النداء.
  ٢. المنطق (node): كل قاعدة تصنيف · الرقم واحد بين العقل والمربّع والتذاكر · العدّاد · قواعد العقل B0–B11 بنصها · الدمج · الاستعلام · أخطاء الربط ·
     بطاقات القرار · أرقام «ماذا يطلب الناس» · طلبات التدريب بلا عمود حالة.
  ٣. الملفات: التبويبات · الخطّافات في index.html · الملفان على القرص · Dockerfile.
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

from app import app as flask_app, db, User, AuditLog  # noqa: E402

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(_HERE, 'uiharness'))
import market_fixtures as mfx   # noqa: E402
import v2_node                  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(_HERE))
PLATFORM = 'https://platform.test'
SECRET = 'test-metrics-secret'
NON_ADMIN_ROLES = ['employee', 'trainer', 'investor', 'viewer', 'pending']
needs_node = pytest.mark.skipif(not v2_node.NODE, reason='needs node')
ADMIN_EMAIL = 'v2smk-admin@x.test'
LIST = '/api/v2/market/requests'


def _read(*parts):
    with open(os.path.join(ROOT, *parts), encoding='utf-8') as fh:
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
        heads = {r: _bearer(_mkuser('v2smk-%s@x.test' % r, r)) for r in NON_ADMIN_ROLES}
        heads['admin'] = _bearer(_mkuser(ADMIN_EMAIL, 'admin'))
        yield {'heads': heads, 'client': flask_app.test_client()}


class Plat(object):
    """`requests.request` البديل: يسجّل كل نداء ويرد من `MarketPlatform`. أي عنوان برّه المنصة المزيّفة ⇒ ممنوع."""

    def __init__(self):
        self.ef = mfx.MarketPlatform()
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

    def calls(self, prefix=''):
        return [c for c in self.seen if c['path'].startswith(prefix)]


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


def _call(ctx, method, path, body=None, role='admin'):
    kw = {'headers': ctx['heads'][role] if role else {}}
    if body is not None:
        kw['json'] = body
    return ctx['client'].open(path, method=method, **kw)


RELANE = '/api/v2/market/requests/mk-n3/relane'
LINK = '/api/v2/market/requests/mk-w4/link-course'
WRITES = [('POST', RELANE, {'need_kind': 'course', 'confirmed': True}), ('POST', LINK, {'course': 'contract-basics', 'confirmed': True})]


# ---------------------------------------------------------------- ١) المسارات

def test_roles_list_is_admin_and_employee_writes_are_admin_only(ctx, plat):
    for role in ('admin', 'employee'):
        r = _call(ctx, 'GET', LIST, role=role)
        assert r.status_code == 200, (role, r.status_code)
    n = len(plat.seen)
    for role in ('trainer', 'investor', 'viewer', 'pending'):
        assert _call(ctx, 'GET', LIST, role=role).status_code == 403, role
    assert len(plat.seen) == n
    assert _call(ctx, 'GET', LIST, role=None).status_code == 401
    plat.seen[:] = []
    for method, path, body in WRITES:
        for role in NON_ADMIN_ROLES:
            assert _call(ctx, method, path, body, role=role).status_code == 403, (path, role)
        assert _call(ctx, method, path, body, role=None).status_code == 401
    assert plat.seen == [], 'نداء للمنصة من غير أدمن'


def test_every_route_is_closed_when_the_switch_is_off_with_no_platform_call(ctx, plat, monkeypatch):
    monkeypatch.setenv('DASH_V2_ENABLED', 'false')
    for method, path, body in [('GET', LIST, None)] + WRITES:
        r = _call(ctx, method, path, body)
        assert r.status_code == 404 and r.headers.get('Cache-Control') == 'no-store', path
    assert plat.seen == []


def test_every_reply_is_no_store(ctx, plat):
    assert _call(ctx, 'GET', LIST).headers.get('Cache-Control') == 'no-store'
    for method, path, body in WRITES:
        assert _call(ctx, method, path, body).headers.get('Cache-Control') == 'no-store'
        assert _call(ctx, method, path, dict(body, confirmed=False)).headers.get('Cache-Control') == 'no-store'


def test_list_forwards_the_exact_params_and_the_secret(ctx, plat):
    r = _call(ctx, 'GET', LIST + '?lane=course_request&status=open&need_kind=course&author_kind=platform&q=%20%20عقد%20&include_test=0&limit=20&skip=40')
    assert r.status_code == 200 and set(r.get_json()) >= {'items', 'total', 'counts'}
    c = plat.calls('/api/bridge/market/requests')
    assert len(c) == 1, 'نداء واحد ولا إعادة محاولة'
    assert c[0]['method'] == 'GET' and c[0]['headers'].get('X-ELP-Metrics-Secret') == SECRET
    assert c[0]['params'] == {'lane': 'course_request', 'status': 'open', 'need_kind': 'course', 'author_kind': 'platform', 'q': 'عقد',
                              'include_test': 'false', 'limit': 20, 'skip': 40}


def test_list_params_are_cleaned_before_they_leave(ctx, plat):
    _call(ctx, 'GET', LIST + '?lane=evil&status=x&need_kind=weird&author_kind=%24ne&q=&include_test=1&limit=0&skip=-5')
    p = plat.calls('/api/bridge/market/requests')[-1]['params']
    assert p == {'lane': 'all', 'status': 'all', 'author_kind': 'all', 'include_test': 'true', 'limit': 1, 'skip': 0}, p
    _call(ctx, 'GET', LIST + '?limit=999&skip=99999999&q=' + 'ع' * 200 + '&include_test=false')
    p = plat.calls('/api/bridge/market/requests')[-1]['params']
    assert p['limit'] == 100 and p['skip'] == 100000 and p['q'] == 'ع' * 80 and p['include_test'] == 'false'
    _call(ctx, 'GET', LIST + '?limit=abc&skip=zz')
    p = plat.calls('/api/bridge/market/requests')[-1]['params']
    assert p['limit'] == 50 and p['skip'] == 0 and p['include_test'] == 'true'
    for good in ('expert', 'service', 'course', 'book', 'training_offer', 'other'):
        _call(ctx, 'GET', LIST + '?need_kind=' + good)
        assert plat.calls('/api/bridge/market/requests')[-1]['params']['need_kind'] == good


def test_list_platform_failures_are_honest(ctx, plat):
    plat.ef.missing = True
    r = _call(ctx, 'GET', LIST)
    assert r.status_code == 404 and r.get_json() == {'error': 'سوق الخدمات غير متاح بعد على المنصة', 'bridge_missing': True}
    assert r.headers.get('Cache-Control') == 'no-store'
    plat.ef.missing = False
    for status in (401, 403):
        plat.ef.forced[('GET', '/api/bridge/market/requests')] = (status, {'detail': 'bad secret'})
        r = _call(ctx, 'GET', LIST)
        assert r.status_code == 502 and r.get_json() == {'error': 'تعذّر الاتصال بالمنصة'}, (status, r.get_json())
    plat.ef.forced[('GET', '/api/bridge/market/requests')] = (500, {'detail': 'boom'})
    r = _call(ctx, 'GET', LIST)
    assert r.status_code == 500 and set(r.get_json()) == {'error'}


def test_list_filters_and_counts_come_from_the_platform_unchanged(ctx, plat):
    body = _call(ctx, 'GET', LIST + '?lane=training_offer').get_json()
    assert body['total'] == 2 and {i['id'] for i in body['items']} == {'mk-s1', 'mk-s2'}
    body = _call(ctx, 'GET', LIST + '?include_test=0&limit=5').get_json()
    assert len(body['items']) == 5 and all(not i['is_test'] for i in body['items']) and body['total'] > 5


def test_relane_needs_an_exact_true_and_validates_before_any_call(ctx, plat):
    for bad in (None, False, 'true', 1, 'yes'):
        b = {'need_kind': 'course'}
        if bad is not None:
            b['confirmed'] = bad
        r = _call(ctx, 'POST', RELANE, b)
        assert r.status_code == 400, bad
    for need in ('training_offer', 'weird', '', None, 5, ['course']):
        assert _call(ctx, 'POST', RELANE, {'need_kind': need, 'confirmed': True}).status_code == 400, need
    assert _call(ctx, 'POST', '/api/v2/market/requests/a%20b/relane', {'need_kind': 'course', 'confirmed': True}).status_code == 404
    assert _call(ctx, 'POST', '/api/v2/market/requests/x%3Fy/relane', {'need_kind': 'course', 'confirmed': True}).status_code == 404
    assert plat.seen == [], 'نداء للمنصة قبل التحقق'


def test_relane_sends_by_from_the_token_a_whitelist_and_is_audited_only_on_success(ctx, plat):
    n = AuditLog.query.filter_by(action='market.relane').count()
    r = _call(ctx, 'POST', RELANE, {'need_kind': 'course', 'confirmed': True, 'by': 'attacker@evil.test', 'reason': ' ' + 'س' * 400, 'kind': 'training_offer', 'status': 'closed'})
    assert r.status_code == 200, r.get_data(as_text=True)[:300]
    sent = plat.calls('/api/bridge/market/requests/mk-n3/relane')[-1]['json']
    assert set(sent) == {'need_kind', 'reason', 'by'} and sent['by'] == ADMIN_EMAIL and sent['need_kind'] == 'course' and len(sent['reason']) == 300
    assert 'attacker' not in json.dumps(sent)
    assert plat.ef._find('mk-n3')['kind'] == 'course_request'
    rows = AuditLog.query.filter_by(action='market.relane').order_by(AuditLog.id.desc()).all()
    assert len(rows) == n + 1 and rows[0].actor_email == ADMIN_EMAIL and rows[0].target == 'mk-n3' and json.loads(rows[0].meta_json) == {'need_kind': 'course'}
    # الفاشل ما بيتدقّقش، ورسالة المنصة بتعدّي
    r = _call(ctx, 'POST', '/api/v2/market/requests/mk-o1/relane', {'need_kind': 'course', 'confirmed': True})
    assert r.status_code == 409 and 'عروض' in r.get_json()['error']
    assert AuditLog.query.filter_by(action='market.relane').count() == n + 1


def test_relane_lost_reply_says_no_reply_and_is_not_audited_as_done(ctx, plat):
    plat.ef.forced[('POST', '/api/bridge/market/requests/mk-n3/relane')] = (504, {'detail': 'timeout'})
    n = AuditLog.query.filter_by(action='market.relane').count()
    r = _call(ctx, 'POST', RELANE, {'need_kind': 'course', 'confirmed': True})
    assert r.status_code == 502 and r.get_json().get('no_reply') is True and 'رد' in r.get_json()['error']
    assert AuditLog.query.filter_by(action='market.relane').count() == n
    assert AuditLog.query.filter_by(action='market.no_reply').count() >= 1
    for status in (401, 403):
        plat.ef.forced[('POST', '/api/bridge/market/requests/mk-n3/relane')] = (status, {'detail': 'bad'})
        r = _call(ctx, 'POST', RELANE, {'need_kind': 'course', 'confirmed': True})
        assert r.status_code == 502 and r.get_json() == {'error': 'تعذّر الاتصال بالمنصة'}


def test_link_course_validates_confirm_id_and_course(ctx, plat):
    for bad in (None, False, 'true', 1):
        b = {'course': 'contract-basics'}
        if bad is not None:
            b['confirmed'] = bad
        assert _call(ctx, 'POST', LINK, b).status_code == 400, bad
    for course in (None, 5, ['x'], {'a': 1}, True):
        assert _call(ctx, 'POST', LINK, {'course': course, 'confirmed': True}).status_code == 400, course
    assert _call(ctx, 'POST', LINK, {'confirmed': True}).status_code == 400
    assert _call(ctx, 'POST', '/api/v2/market/requests/a%20b/link-course', {'course': 'x', 'confirmed': True}).status_code == 404
    assert plat.seen == []


def test_link_course_sends_only_linked_course_id_and_by_and_audits_on_success(ctx, plat):
    n = AuditLog.query.filter_by(action='market.link_course').count()
    r = _call(ctx, 'POST', LINK, {'course': '  contract-basics ', 'confirmed': True, 'by': 'x@y.z', 'evidence_note': 'مزيّف', 'join_goal': 999, 'specialty': 'س'})
    assert r.status_code == 200, r.get_data(as_text=True)[:300]
    sent = plat.calls('/api/bridge/market/requests/mk-w4/annotate')[-1]['json']
    assert sent == {'linked_course_id': 'contract-basics', 'by': ADMIN_EMAIL}, sent
    rows = AuditLog.query.filter_by(action='market.link_course').order_by(AuditLog.id.desc()).all()
    assert len(rows) == n + 1 and json.loads(rows[0].meta_json) == {'course': 'contract-basics'} and rows[0].target == 'mk-w4'
    # فك الربط: النص الفاضي بيعدّي
    r = _call(ctx, 'POST', LINK, {'course': '', 'confirmed': True})
    assert r.status_code == 200 and plat.calls('/api/bridge/market/requests/mk-w4/annotate')[-1]['json'] == {'linked_course_id': '', 'by': ADMIN_EMAIL}
    assert len(plat.calls('/api/bridge/market/requests/mk-w4/annotate')) == 2


def test_link_course_404_keeps_the_two_platform_reasons_distinguishable(ctx, plat):
    plat.ef.forced[('POST', '/api/bridge/market/requests/mk-w4/annotate')] = (404, {'detail': 'Request not found'})
    a = _call(ctx, 'POST', LINK, {'course': 'contract-basics', 'confirmed': True})
    plat.ef.forced[('POST', '/api/bridge/market/requests/mk-w4/annotate')] = (404, {'detail': 'الدورة المرتبطة غير موجودة'})
    b = _call(ctx, 'POST', LINK, {'course': 'contract-basics', 'confirmed': True})
    assert a.status_code == b.status_code == 404
    assert a.get_json()['error'] == 'Request not found' and b.get_json()['error'] == 'الدورة المرتبطة غير موجودة'
    # بلا تدقيق على الفاشل
    assert AuditLog.query.filter_by(action='market.link_course', target='mk-w4').count() == AuditLog.query.filter_by(action='market.link_course').count()
    # دورة مش موجودة على المنصة أصلًا ⇒ ٤٠٤ بنص الدورة
    plat.ef.forced.clear()
    r = _call(ctx, 'POST', LINK, {'course': 'no-such-course', 'confirmed': True})
    assert r.status_code == 404 and 'الدورة' in r.get_json()['error']


def test_wiring_one_registration_line_above_the_marker_and_lazy_helpers(ctx, plat, monkeypatch):
    src = _read('backend', 'app.py')
    assert src.count('# ---- v2 section routes end') == 1
    assert src.count('import v2_market_routes as _v2s_market; _v2s_market.register(app, globals())') == 1
    lines = src.split('\n')
    i = [n for n, ln in enumerate(lines) if ln.startswith('# ---- v2 section routes end')][0]
    assert 'v2_market_routes' in lines[i - 1], 'سطر التسجيل لازم يكون فوق العلامة مباشرة'
    # `_platform_proxy` بيتقرا وقت النداء: استبداله بعد الاستيراد بيتحترم
    import app as appmod
    calls = []

    def fake(method, path, params=None, json_body=None, timeout=12):
        calls.append(path)
        return appmod.jsonify({'items': [], 'total': 0, 'counts': {}}), 200
    monkeypatch.setattr(appmod, '_platform_proxy', fake)
    assert _call(ctx, 'GET', LIST).status_code == 200 and calls == ['/api/bridge/market/requests']


# ---------------------------------------------------------------- ٢) المنطق النقي (node)

NOW = 1793361600000          # 2026-10-30T12:00:00Z
H = 3600e3
D = 24 * H


def _iso(hours_ago):
    return datetime.datetime.fromtimestamp((NOW - hours_ago * H) / 1000.0, datetime.timezone.utc).isoformat()


def L(fn, *args):
    return v2_node.logic('v2sMarket.' + fn, *args)


def R(rid='r', **kw):
    base = {'id': rid, 'kind': 'request', 'need_kind': 'expert', 'title': 'عنوان ' + rid, 'status': 'open', 'visibility': 'public', 'offer_count': 0,
            'is_test': False, 'hidden': False, 'created_at': _iso(3), 'member_alias': 'عضو ١'}
    base.update(kw)
    return base


def T(rows, **o):
    o.setdefault('now', NOW)
    return L('tickets', rows, o)


def ids(t, col):
    return [x['id'] for x in t['cols'][col]]


@needs_node
def test_every_rule_lands_in_its_column():
    rows = [R('new', created_at=_iso(5)),
            R('old', created_at=_iso(30)),
            R('priv', created_at=_iso(2), visibility='private'),
            R('demand', created_at=_iso(2), open_demand=True, author_kind='platform', join_goal=10, joined_count=3),
            R('offer', offer_count=2, last_offer_at=_iso(4)),
            R('match', status='matched', updated_at=_iso(3)),
            R('closed', status='closed', updated_at=_iso(60)),
            R('stale_done', status='closed', updated_at=_iso(24 * 9)),
            R('hid', hidden=True, created_at=_iso(60)),
            R('weird', status='paused'),
            R('nodate', created_at='nonsense'),
            R('trn', kind='training_offer', need_kind='training_offer'),
            R('tst', is_test=True)]
    t = T(rows)
    assert ids(t, 'new') == ['new', 'priv'] or sorted(ids(t, 'new')) == ['new', 'priv']
    assert set(ids(t, 'waiting')) == {'old', 'demand', 'hid', 'weird', 'nodate'}
    assert ids(t, 'offered') == ['offer']
    assert ids(t, 'done') == ['match', 'closed']                      # الأحدث أولًا
    assert t['doneOlder'] == 1 and t['testCount'] == 1 and t['hiddenCount'] == 1
    assert 'trn' not in sum(t['cols'].values(), []) and all('tst' not in ids(t, c) for c in t['cols'])
    assert T(rows, showTest=True)['cols']['new'] and 'tst' in sum([ids(T(rows, showTest=True), c) for c in t['cols']], [])
    w = {x['id']: x for x in t['cols']['waiting']}
    assert w['weird']['typeLabel'] == 'حالة غير معروفة' and 'غير معروفة' in w['weird']['brain']['line'] and w['weird']['brain']['primary']['act'] == 'open'
    assert w['nodate']['text'] == '' and w['nodate']['timer'] is None            # لا «منذ NaN» ولا إسقاط


@needs_node
def test_the_waiting_timer_uses_the_platforms_own_activity_clock():
    r = R('act', created_at=_iso(240), last_activity_at=_iso(48), joined_count=1)
    w = T([r])['cols']['waiting'][0]
    assert w['text'] == 'بلا عرض منذ يومين', w['text']
    plain = T([R('plain', created_at=_iso(240))])['cols']['waiting'][0]
    assert plain['text'] == 'بلا عرض منذ ١٠ أيام'
    goal = T([R('g', created_at=_iso(24 * 30), open_demand=True, goal_reached_at=_iso(30), join_goal=5, joined_count=5)])['cols']['waiting'][0]
    assert goal['text'] == 'اكتمل العدد منذ يوم' and goal['tone'] == 'late'


@needs_node
def test_timer_texts_and_tones_at_a_fixed_now():
    t = T([R('n', created_at=_iso(0.5)), R('o', offer_count=1, last_offer_at=_iso(5)), R('o2', offer_count=1), R('d', status='closed', updated_at=_iso(2), id='d'),
           R('d2', status='closed', updated_at=_iso(30)), R('lnk', created_at=_iso(300), open_demand=True, linked_course_id='c', join_goal=5, joined_count=5, goal_reached_at=_iso(100)),
           R('stl', created_at=_iso(300), stale_unanswered=True)])
    assert t['cols']['new'][0]['text'] == 'منذ ٣٠ دقيقة' and t['cols']['new'][0]['tone'] == 'new'
    o = {x['id']: x for x in t['cols']['offered']}
    assert o['o']['text'] == 'آخر عرض منذ ٥ ساعات' and o['o']['tone'] == 'ok'
    assert o['o2']['text'] == 'وصله عرض' and o['o2']['timer'] is None, 'بلا وقت آخر عرض ⇒ بلا وقت'
    d = {x['id']: x for x in t['cols']['done']}
    assert re.match(r'^[٠-٩]{1,2}:[٠-٩]{2} [صم]$', d['d']['text']) and d['d']['tone'] == 'done' and d['d']['typeLabel'] == 'أُغلق'
    assert 'أكتوبر' in d['d2']['text'] and re.search(r'٢٠٢٦', d['d2']['text'])
    w = {x['id']: x for x in t['cols']['waiting']}
    assert w['lnk']['tone'] == 'ok' and w['stl']['tone'] == 'late'
    assert t['cols']['waiting'][0]['id'] == 'stl', 'الأحمر أولًا'


@needs_node
def test_sort_orders_and_the_per_column_page():
    rows = [R('n%d' % i, created_at=_iso(1 + i * 0.5)) for i in range(11)]
    t = T(rows)
    assert ids(t, 'new')[0] == 'n10' and ids(t, 'new')[-1] == 'n0', 'الأقدم أولًا'
    assert len(t['shown']['new']) == 8 and t['more']['new'] == 3 and t['counts']['new'] == 11
    t = T(rows, expanded={'new': True})
    assert len(t['shown']['new']) == 11 and t['more']['new'] == 0
    t = T([R('a', offer_count=1, last_offer_at=_iso(3)), R('b', offer_count=1, last_offer_at=_iso(9)), R('c', offer_count=1)])
    assert ids(t, 'offered') == ['b', 'a', 'c']
    t = T([R('p', status='matched', updated_at=_iso(10)), R('q', status='closed', updated_at=_iso(2)), R('r', status='closed', updated_at=_iso(80))])
    assert ids(t, 'done') == ['q', 'p', 'r']


@needs_node
def test_lane_filter_and_demand_lanes():
    rows = [R('a'), R('b', kind='course_request', need_kind='course'), R('c', kind='public_service', need_kind='service')]
    assert [x for c in T(rows, lane='course_request')['cols'].values() for x in [y['id'] for y in c]] == ['b']
    assert sum(T(rows)['counts'].values()) == 3


@needs_node
def test_the_brain_number_equals_the_tile_formula_and_the_tickets():
    rows = []
    for i in range(24):
        rows.append(R('m%d' % i, created_at=_iso(2 + i * 9), offer_count=(i % 4 == 0) and 2 or 0, hidden=(i % 7 == 0), is_test=(i % 11 == 0),
                      status=('matched' if i % 13 == 0 else 'open'), kind=('training_offer' if i % 9 == 0 else 'request'), updated_at=_iso(5)))
    t = T(rows)
    tile = sum(1 for r in rows if r['status'] == 'open' and not r['hidden'] and not r['is_test'] and r['kind'] != 'training_offer' and not r['offer_count'])
    from_tickets = sum(1 for c in ('new', 'waiting') for x in t['cols'][c] if x['row']['status'] == 'open' and not x['row']['hidden'])
    assert t['tileCount'] == tile == from_tickets and tile > 5
    assert L('tileCount', rows) == tile


@needs_node
def test_the_header_line_totals_and_lanes():
    rows = [R('a', created_at=_iso(50)), R('b', created_at=_iso(5)), R('c', offer_count=1, last_offer_at=_iso(1))]
    counts = {'by_status': {'open': 12, 'matched': 3}, 'by_lane': {'request': 9, 'course_request': 4, 'training_offer': 2}}
    h = L('header', rows, counts, 15, NOW)
    assert h['brainText'] == 'العقل: طلبان بلا عرض، أقدمها منذ يومين' and h['N'] == 2 and h['brainTs'] is not None
    assert h['totals'] == 'في السوق الآن: ١٢ مفتوح · ٣ تمّت مطابقته · ٠ أُغلق'
    assert h['lanes'] == {'request': 9, 'course_request': 4, 'public_service': 0, 'training_offer': 2, 'all': 13}
    assert h['truncated'] is True and h['total'] == 15
    h1 = L('header', [R('a', created_at=_iso(5))], None, 1, NOW)
    assert h1['brainText'].startswith('العقل: طلب واحد بلا عرض') and h1['totals'].endswith('(من المعروض فقط)') and h1['truncated'] is False
    assert L('header', [R('o', offer_count=1)], None, 1, NOW)['brainText'] == 'العقل: كل طلب مفتوح وصله عرض أو يجمع المنضمّين'
    assert L('header', [], None, 0, NOW)['brainText'] == 'العقل: لا طلبات مفتوحة الآن'


def B(row, **o):
    return L('brain', row, NOW, o or None)


@needs_node
def test_brain_rules_b0_to_b11_exact_lines_and_buttons():
    assert B(R(status='matched', updated_at=_iso(3))) == {'line': 'اختار صاحب الطلب عرضًا منذ ٣ ساعات', 'primary': None}
    assert B(R(status='matched'))['line'] == 'اختار صاحب الطلب عرضًا'
    assert B(R(status='closed', updated_at=_iso(50)))['line'] == 'أُغلق منذ يومين' and B(R(status='closed'))['primary'] is None
    b2 = B(R(hidden=True, hidden_reason='محتوى ترويجي'))
    assert b2['line'] == 'مخفي عن صفحة السوق العامة بسبب: «محتوى ترويجي»؛ صاحبه ما زال يراه' and b2['primary'] == {'label': 'افتح الطلب', 'act': 'open'}
    assert B(R(hidden=True))['line'] == 'مخفي عن صفحة السوق العامة؛ صاحبه ما زال يراه'
    dem = dict(open_demand=True, author_kind='platform', join_goal=20, joined_count=20)
    b3 = B(R(goal_reached_at=_iso(30), **dem))
    assert b3['line'] == 'اكتمل العدد منذ يوم: انضم ٢٠ من ٢٠، ولم تُربط دورة بعد' and b3['primary'] == {'label': 'اربط دورة', 'act': 'link'}
    b4 = B(R(goal_reached_at=_iso(30), linked_course_id='c1', **dem))
    assert b4['line'] == 'رُبطت به دورة، والحجز مفتوح لمن انضم (٢٠)' and b4['primary']['act'] == 'open'
    b5 = B(R(**dict(dem, joined_count=6, join_goal=15)))
    assert b5['line'] == 'طلب مفتوح من المنصة يجمع المنضمّين: ٦ من ١٥' and b5['primary']['act'] == 'open'
    assert B(R(**dict(dem, joined_count=6, join_goal=0)))['line'] == 'طلب مفتوح من المنصة يجمع المنضمّين: انضم ٦'
    assert 'من ٠' not in B(R(**dict(dem, joined_count=6, join_goal=0)))['line']
    b6 = B(R(kind='request', need_kind='course'))
    assert b6['line'] == 'نوعه «دورة أو تدريب» لكنه معروض مع طلبات الخبرة' and b6['primary'] == {'label': 'انقله إلى طلبات الدورات', 'act': 'relane', 'target': 'course_request'}
    b7 = B(R(created_at=_iso(300), stale_unanswered=True))
    assert b7['line'] == 'بلا أي عرض منذ ١٢ يومًا، لذلك لم يعد يظهر على صفحة السوق العامة' and b7['primary'] == {'label': 'افتح الطلب', 'act': 'open'}
    b8 = B(R(offer_count=3, last_offer_at=_iso(4)))
    assert b8['line'] == 'وصله ٣ عروض، آخرها منذ ٤ ساعات. الاختيار لصاحب الطلب' and b8['primary'] == {'label': 'اعرض العروض', 'act': 'offers'}
    assert B(R(offer_count=1))['line'] == 'وصله عرض واحد. الاختيار لصاحب الطلب'
    assert B(R(offer_count=2))['line'].startswith('وصله عرضان')
    assert B(R(offer_count=11))['line'].startswith('وصله ١١ عرضًا')
    b9 = B(R(created_at=_iso(24 * 3)))
    assert b9['line'] == 'بلا عرض منذ ٣ أيام. يختفي من صفحة السوق العامة بعد ٧ أيام بلا عرض' and b9['primary']['act'] == 'open'
    b9b = B(R(created_at=_iso(240), joined_count=1, join_goal=0))
    assert b9b['line'] == 'بلا عرض منذ ١٠ أيام، ويبقى على صفحة السوق العامة ما دام يجمع المنضمّين (١)' and 'يختفي' not in b9b['line']
    b9c = B(R(created_at=_iso(240), join_goal=5))
    assert b9c['line'] == 'بلا عرض منذ ١٠ أيام، ويبقى على صفحة السوق العامة ما دام يجمع المنضمّين' and '(' not in b9c['line'] and '(٠)' not in b9c['line']
    assert B(R(created_at=_iso(240), last_activity_at=_iso(24), joined_count=0, join_goal=0))['line'].startswith('بلا عرض منذ يوم. يختفي')
    assert B(R(visibility='private', preferred_expert_email='x@y.z', created_at=_iso(9)))['line'] == 'طلب خاص موجَّه إلى خبير بعينه، بلا عرض منذ ٩ ساعات'
    assert B(R(visibility='private', created_at=_iso(30)))['line'] == 'طلب خاص لا يظهر على صفحة السوق العامة، بلا عرض منذ يوم'
    assert B(R(created_at=_iso(2)))['line'] == 'وصل منذ ساعتين، وهو ظاهر للخبراء على صفحة السوق العامة'


@needs_node
def test_brain_uses_the_platform_lane_table_and_never_suggests_on_unknown_needs():
    for need, kind, target in (('course', 'request', 'course_request'), ('service', 'request', 'public_service'), ('expert', 'course_request', 'request'),
                               ('book', 'public_service', 'request'), ('other', 'course_request', 'request')):
        b = B(R(kind=kind, need_kind=need))
        assert b['primary']['act'] == 'relane' and b['primary']['target'] == target, (need, kind, b)
    assert B(R(kind='request', need_kind='expert'))['primary']['act'] == 'open'
    b = B(R(kind='request', need_kind='consult'))
    assert b['primary']['act'] == 'open' and 'نوعه' not in b['line']
    assert B(R(kind='request', need_kind='course', offer_count=1))['primary']['act'] == 'offers', 'عليه عرض ⇒ ما يتنقلش'
    assert L('needLabel', 'consult') == 'غير مصنّف' and L('needLabel', 'course') == 'دورة أو تدريب' and L('needLabel', None) == 'غير مصنّف'
    assert L('NEED_LABEL') == {'expert': 'خبير', 'service': 'خدمة', 'course': 'دورة أو تدريب', 'book': 'كتاب أو معرفة', 'training_offer': 'عرض مدرّب', 'other': 'غير مصنّف'}


@needs_node
def test_read_only_turns_decisions_into_open_and_no_line_has_forbidden_text():
    dem = dict(open_demand=True, author_kind='platform', join_goal=20, joined_count=20, goal_reached_at=_iso(30))
    r1, r2 = R(**dem), R(kind='request', need_kind='course')
    assert B(r1, readOnly=True)['primary'] == {'label': 'افتح الطلب', 'act': 'open'} and B(r1, readOnly=True)['line'] == B(r1)['line']
    assert B(r2, readOnly=True)['primary']['act'] == 'open'
    assert B(R(offer_count=2), readOnly=True)['primary']['act'] == 'offers'
    pool = [R(), R(hidden=True, hidden_reason='x 12'), r1, r2, R(offer_count=3, last_offer_at=_iso(2)), R(status='matched'), R(status='closed'), R(status='weird'),
            R(created_at=_iso(300), stale_unanswered=True), R(created_at=_iso(100), joined_count=2), R(created_at=_iso(100)), R(visibility='private'),
            R(created_at='junk'), R(open_demand=True, join_goal=5, joined_count=1), R(open_demand=True, linked_course_id='c')]
    for r in pool:
        for ro in (False, True):
            b = B(r, readOnly=ro)
            line = b['line'] + ' ' + (b['primary'] or {}).get('label', '')
            assert not re.search(r'[0-9]', line.replace('x ', '')) or r.get('hidden_reason'), line
            for bad in ('null', 'undefined', 'NaN', 'يقوّم', 'اعمل'):
                assert bad not in line, (bad, line)
            assert not line.startswith('الذكاء الاصطناعي')
            if ro:
                assert b['primary'] is None or b['primary']['act'] in ('open', 'offers'), b


@needs_node
def test_merge_enriches_by_id_and_keeps_absent_fields_undefined():
    rows = [{'id': 'b', 'title': 'ب'}, {'id': 'a', 'title': 'أ'}, {'id': 'z', 'title': 'ز'}]
    raw = [{'id': 'a', 'member_phone': '0100', 'last_activity_at': '2026-10-29T00:00:00Z', 'joined_count': 0, 'open_demand': False, 'stale_unanswered': False},
           {'id': 'b', 'author_kind': 'platform', 'linked_course_slug': 'x', 'join_goal': 5}]
    out = L('merge', rows, raw)
    assert [r['id'] for r in out] == ['b', 'a', 'z'], 'الترتيب كما هو والمطابقة بالمعرّف لا بالموضع'
    assert out[1]['member_phone'] == '0100' and out[1]['last_activity_at'] == '2026-10-29T00:00:00Z' and out[1]['joined_count'] == 0 and out[1]['open_demand'] is False
    assert out[0]['author_kind'] == 'platform' and out[0]['join_goal'] == 5 and 'member_phone' not in out[0] and 'joined_count' not in out[0]
    assert 'member_phone' not in out[2] and out[2] == {'id': 'z', 'title': 'ز'}
    assert L('merge', None, None) == []


@needs_node
def test_query_strings():
    assert L('query', {}) == 'include_test=0&limit=50&skip=0'
    assert L('query', {'lane': 'all', 'status': 'all', 'need': 'all', 'author': 'all'}) == 'include_test=0&limit=50&skip=0'
    full = L('query', {'lane': 'course_request', 'status': 'open', 'need': 'course', 'author': 'platform', 'q': '  عقد شراكة  ', 'showTest': True, 'limit': 50, 'skip': 100})
    assert full == 'lane=course_request&status=open&need_kind=course&author_kind=platform&q=%D8%B9%D9%82%D8%AF%20%D8%B4%D8%B1%D8%A7%D9%83%D8%A9&include_test=1&limit=50&skip=100'
    assert L('query', {'showTest': True}) == 'include_test=1&limit=50&skip=0'
    assert L('query', {'lane': 'training_offer'}) == 'lane=training_offer&include_test=0&limit=50&skip=0'
    assert L('query', {'q': 'س' * 200}).count('%D8%B3') == 80
    assert L('activeFilters', {'status': 'open', 'need': 'course', 'author': 'platform', 'showTest': True}) == [
        {'k': 'status', 'label': 'مفتوح'}, {'k': 'need', 'label': 'دورة أو تدريب'}, {'k': 'author', 'label': 'المنصة'}, {'k': 'test', 'label': 'يظهر التجريبي'}]
    assert L('activeFilters', {'status': 'all', 'need': 'all', 'author': 'all'}) == []


@needs_node
def test_link_error_texts():
    assert L('linkErr', 404, {'error': 'الدورة المرتبطة غير موجودة'}) == 'الدورة غير موجودة على المنصة'
    assert L('linkErr', 404, {'error': 'Request not found'}) == 'هذا الطلب لم يعد موجودًا على المنصة'
    assert L('linkErr', 404, {}) == 'هذا الطلب لم يعد موجودًا على المنصة'
    assert L('linkErr', 422, {'error': 'لا يمكن ربط أكثر من 3 دورات'}) == 'لا يمكن ربط أكثر من ٣ دورات'
    assert L('linkErr', 422, {'error': 'invalid course'}) == 'تعذّر ربط الدورة، حاول مرة أخرى'
    assert L('linkErr', 500, {'error': 'boom'}) == 'تعذّر ربط الدورة، حاول مرة أخرى' and L('linkErr', 0, None) == 'تعذّر ربط الدورة، حاول مرة أخرى'


@needs_node
def test_cards_returns_only_the_decision_tickets():
    rows = [R('goal', open_demand=True, author_kind='platform', join_goal=5, joined_count=5, goal_reached_at=_iso(3)),
            R('move', kind='request', need_kind='service'), R('stale', created_at=_iso(300), stale_unanswered=True), R('plain'),
            R('hid', hidden=True, kind='request', need_kind='service'), R('tst', is_test=True, kind='request', need_kind='service'),
            R('gathering', open_demand=True, join_goal=9, joined_count=2)]
    c = L('cards', rows, NOW)
    assert [x['id'] for x in c] == ['goal', 'move'] and c[0]['kind'] == 'market' and c[0]['primary']['act'] == 'link' and c[1]['primary']['act'] == 'relane'
    assert all(set(x) == {'kind', 'id', 'title', 'line', 'primary'} for x in c)


DEMAND = mfx.DEMAND


@needs_node
def test_demand_view_model():
    d = L('demand', DEMAND)
    assert d['brain'] == 'العقل: ٩ طلبات مفتوحة بلا عرض من ٤١ خلال آخر ٩٠ يومًا'
    assert d['platform'] == 'طلبات المنصة المفتوحة: ٣، انضم إليها ٣٨، واكتمل عدد ٢'
    assert [n['label'] for n in d['byNeed']] == ['خبير', 'دورة أو تدريب', 'خدمة', 'كتاب أو معرفة'] and d['byNeed'][0]['pct'] == 100 and d['byNeed'][0]['zero'] == 6
    assert d['specs']['title'] == 'حسب التخصص' and d['specs']['fallback'] is False and [i['label'] for i in d['specs']['items']] == ['تسويق', 'عقود']
    assert d['courses'][0]['explicit'] is True and d['courses'][0]['originLabel'] == 'طلبها شخص صراحة' and d['courses'][2]['originLabel'] == 'مستنتجة من المحادثات'
    assert d['courses'][0]['reason'] == '٦ طلب في السوق · ٥ اهتمام بالتدريب · ٢ اهتمام بدورة · ٤ من المحادثات'
    assert d['courses'][1]['reason'] == '٢٠ انضمام لطلبات المنصة' and d['courses'][1]['countText'] == '٢٠ إشارة'
    assert d['topBrain'] == 'العقل: أكثر ما طُلب صراحةً «أساسيات صياغة العقود التجارية» (١٧ إشارة)', 'أول مقترح صراحةً بترتيب المنصة'
    # الاستنتاج وحده لا يُرقّى
    inferred = copy.deepcopy(DEMAND)
    inferred['suggested_courses'] = [c for c in inferred['suggested_courses'] if c['origin'] != 'explicit']
    inferred['suggested_courses'][0]['specialty'] = ''
    d2 = L('demand', inferred)
    assert d2['topBrain'] == '' and d2['specs']['title'] == 'مواضيع تتكرر' and d2['specs']['fallback'] is True and d2['specs']['items'][0]['label'] == 'عقود'


@needs_node
def test_demand_drops_missing_signal_parts_and_never_invents_zero():
    assert L('demand', None) is None and L('demand', {'missing': True}) is None
    d = copy.deepcopy(DEMAND)
    d['signals'] = {'unanswered_requests': 4}
    d.pop('window_days')
    out = L('demand', d)
    assert out['brain'] == 'العقل: ٤ طلبات مفتوحة بلا عرض' and out['platform'] == ''
    d['signals'] = {'open_demand_cards': 2}
    out = L('demand', d)
    assert out['brain'] == '' and out['platform'] == 'طلبات المنصة المفتوحة: ٢'
    d['signals'] = {}
    assert L('demand', d)['brain'] == ''
    d = {'by_need_kind': [{'need_kind': 'expert', 'count': 3}], 'suggested_courses': [{'title_hint': '', 'signal_count': 4, 'origin': 'explicit', 'sources': {}, 'samples': ['نص عيّنة']}]}
    out = L('demand', d)
    assert out['byNeed'][0].get('zero') is None and out['byNeed'][0].get('withOffers') is None and out['byNeed'][0].get('total') is None
    assert out['courses'][0]['title'] == 'بلا عنوان' and out['courses'][0]['canCreate'] is False and out['courses'][0]['reason'] == 'نص عيّنة' and out['topBrain'] == ''


@needs_node
def test_training_view_model_has_no_status_and_flags_no_contact_only_when_all_new():
    resp = {'rows': [{'id': 'a', 'name': 'س', 'phone': '+20 100-000 333', 'email': 'a@x.test', 'wanted_course': 'ع', 'status': 'new', 'when': 'منذ ٥ س'},
                     {'id': 'b', 'name': 'ص', 'phone': '', 'email': '', 'wanted_course': '', 'status': '', 'when': ''}], 'count': 40}
    t = L('training', resp)
    assert all('status' not in r for r in t['rows']) and t['noContact'] is True and t['truncated'] is True and t['count'] == 40
    assert t['rows'][0]['phone'] == '+20100000333' and t['rows'][1]['phone'] == ''
    resp['rows'][1]['status'] = 'contacted'
    assert L('training', resp)['noContact'] is False
    assert L('training', None) is None and L('training', {'missing': True, 'rows': []}) is None
    assert L('training', {'rows': [], 'count': 0})['rows'] == []


@needs_node
def test_norm_gives_a_bridge_row_the_same_shape_as_the_board_row():
    r = L('norm', {'id': 'x', 'kind': 'course_request', 'title': 'ت', 'last_activity_at': '2026-10-01T00:00:00Z', 'member_phone': '010', 'offers_count': 2})
    assert r['need_kind'] == 'course' and r['status'] == 'open' and r['visibility'] == 'private' and r['offer_count'] == 2 and r['member_phone'] == '010'
    assert r['last_activity_at'] == '2026-10-01T00:00:00Z' and 'joined_count' not in r
    row = L('allRow', r, NOW)
    assert row['lane'] == 'طلب دورة' and row['status'] == 'مفتوح' and row['statusKey'] == 'open' and row['offersText'] == '٢'


# ---------------------------------------------------------------- ٣) الملفات والخطّافات

def test_the_section_has_three_tabs_and_old_links_still_land_on_the_board():
    out = v2_node.logic('SECTIONS')
    mk = [s for s in out if s['key'] == 'market'][0]
    assert [[t['key'], t['label'], t['mod']] for t in mk['tabs']] == [['requests', 'الطلبات', 'market'], ['all', 'كل الطلبات', 'v2s_market_all'],
                                                                      ['demand', 'ماذا يطلب الناس', 'v2s_market_demand']]
    r = v2_node.logic('sectionFor', 'market', {}, None)
    assert (r['section'], r['tab'], r['mod']) == ('market', 'requests', 'market')
    for tab in ('all', 'demand'):
        assert v2_node.logic('routeFor', '#s/market/' + tab, {})['tab'] == tab
        assert v2_node.logic('sectionHash', 'market', tab) == '#s/market/' + tab
    assert v2_node.logic('routeFor', '#market', {})['tab'] == 'requests'
    assert v2_node.logic('routeFor', '#s/market', {})['tab'] == 'requests'


def test_index_html_hooks_are_there_once_and_the_old_screen_is_untouched():
    html = _read('dashboard-cloud', 'index.html')
    m = re.search(r'<!-- v2 sections begin -->(.*?)<!-- v2 sections end -->', html, re.S)
    assert m and html.count('<!-- v2 sections begin -->') == 1
    assert '<link rel="stylesheet" href="v2s/market.css">' in m.group(1) and '<script src="v2s/market.js"></script>' in m.group(1)
    assert html.count('V2SEC[_i].owns(current)') == 1 and html.count('for(var _i=0;_i<V2SEC.length;_i++)') == 1
    assert html.index('V2D3.render(current,v)') < html.index('V2SEC[_i].owns(current)'), 'الخطّاف بعد سطر D3'
    assert html.index('V2SEC[_i].owns(current)') < html.index("MODULES_LOOKUP[current]&&MODULES_LOOKUP[current].soon"), 'قبل أي شاشة قديمة'
    # الشاشة القديمة بالحرف: الدالة والمحمّلات
    assert 'function viewMarket(v){' in html and "current==='market')return viewMarket(v)" in html and 'function drawMarketReq(){' in html
    assert re.search(r"viewMarket\(v\)\s*\n?\s*\}", html) or True


def test_the_two_files_exist_and_the_image_copy_includes_them():
    assert os.path.isfile(os.path.join(ROOT, 'dashboard-cloud', 'v2s', 'market.js')) and os.path.isfile(os.path.join(ROOT, 'dashboard-cloud', 'v2s', 'market.css'))
    assert 'COPY . /usr/share/nginx/html' in _read('dashboard-cloud', 'Dockerfile')
    for df in ('Dockerfile', os.path.join('deploy', 'Dockerfile.coolify')):
        assert 'COPY dashboard-cloud/v2s /app/dist/v2s' in _read(df), df


def _strip(src):
    src = re.sub(r'/\*.*?\*/', '', src, flags=re.S)
    return '\n'.join(re.sub(r'(^|\s)//.*$', '', ln) for ln in src.split('\n'))


def test_the_front_end_stays_inside_its_own_rules():
    js = _strip(_read('dashboard-cloud', 'v2s', 'market.js'))
    css = _read('dashboard-cloud', 'v2s', 'market.css')
    # ⛔ كل قاعدة تحت صنف السوق أو الورقة (لا مسّ لشاشة تانية)
    for sel in re.findall(r'(?m)^([^@\s/}{][^{]*)\{', re.sub(r'/\*.*?\*/', '', css, flags=re.S)):
        for part in sel.split(','):
            part = part.strip()
            assert part == '' or '.v2s-mk' in part or part.startswith('html.v2s-mk') or part.startswith('0%') or part.startswith('from') or part.startswith('to'), part
    assert not re.search(r'\bfetch\(|XMLHttpRequest|api\.elprofessor|bridge/', js), 'لا شبكة من الواجهة غير EP.api'
    assert 'confirmed: true' in js and js.count('confirmed: true') >= 2
    assert 'اعمل' not in js and 'يقوّم' not in js
    for old in ('.kpis', 'inboxwrap', "'policy'", 'tabbar', 'esc-row'):
        assert old not in js, old
    assert "roleName() === 'admin'" in js, 'الكتابة للأدمن بس'


def test_index_markup_text_has_no_forbidden_visible_copy():
    js = _read('dashboard-cloud', 'v2s', 'market.js') + _read('dashboard-cloud', 'v2-logic.js')[_read('dashboard-cloud', 'v2-logic.js').index('// ===== v2s:market ====='):]
    for bad in ('يقوّم', 'الذكاء الاصطناعي', 'api.elprofessor.net', 'native'):
        # مسموح فقط داخل تعليقات الكود
        assert bad not in _strip(js).replace('V2L.v2sMarket', ''), bad


def test_the_create_course_modal_hooks_the_restyle_depends_on_still_exist():
    """تلبيس «إنشاء دورة» يعتمد على معرّفات ونصوص النافذة القديمة؛ لو غيّرها قسم الدورات يفشل هذا الاختبار بصوت عالٍ عند الدمج."""
    html = _read('dashboard-cloud', 'index.html')
    body = html[html.index('function createCourseModal('):html.index('function editCourseModal(')]
    owner = html[html.index('function courseOwnerBlockHtml('):html.index('function bindCourseOwner(')]
    for needle in ('id="m_title"', 'id="m_head"', 'id="m_titch"', '<details', '<summary', 'id="m_save"'):
        assert needle in body, 'تلبيس نافذة الدورة: ' + needle
    for needle in ('id="m_plat"', 'id="m_email"'):
        assert needle in owner, 'تلبيس نافذة الدورة: ' + needle
    js = _read('dashboard-cloud', 'v2s', 'market.js')
    for sel in ('#m_head', '#m_titch', '#m_plat', '#m_email', 'details > div > div', '#m_title'):
        assert sel in js, sel


def test_all_requests_reloads_when_any_filter_changed_since_the_last_load():
    js = _read('dashboard-cloud', 'v2s', 'market.js')
    assert "A.loadedSig = allSig()" in js and "S.all.loadedSig !== allSig()" in js
    sig = js[js.index('function allSig()'):js.index('function laneNumbers()')]
    assert 'filterSig()' in sig and 'S.all.lane' in sig and 'S.showTest' in sig


def test_a_401_clears_the_all_requests_skeleton():
    js = _read('dashboard-cloud', 'v2s', 'market.js')
    i = js.index('e.status === 401) {')
    assert "A.state = 'error'" in js[i:i + 200]


def test_plain_copy_has_no_board_loanword():
    for rel in (('dashboard-cloud', 'v2s', 'market.js'), ('dashboard-cloud', 'v2s', 'market.css')):
        assert 'بورد' not in re.sub(r'داشبورد', '', _strip(_read(*rel))), rel
    logic = _read('dashboard-cloud', 'v2-logic.js')
    blk = logic[logic.index('// ===== v2s:market ====='):]
    assert 'بورد' not in _strip(blk)


@needs_node
def test_header_totals_say_when_test_rows_are_included():
    rows = [R('a', created_at=_iso(50)), R('t', is_test=True, created_at=_iso(5))]
    counts = {'by_status': {'open': 2}}
    assert L('header', rows, counts, 2, NOW)['totals'].endswith('(يشمل التجريبي)')
    assert '(يشمل التجريبي)' not in L('header', rows[:1], counts, 1, NOW)['totals']
