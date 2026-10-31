# -*- coding: utf-8 -*-
"""بروكسيات محرّر الدورات `/api/v2/courses2/*` (SPEC-C-courses §C1) — ورا نفس المفتاح المقفول.

Run:  cd backend && python3 -B -m pytest -q -p no:cacheprovider tests/test_courses2_proxy.py

⛔ صفر شبكة حقيقية: المنصة في الذاكرة (`uiharness/course_editor_fixtures.Courses2Platform`)، وأي عنوان برّه `https://platform.test` بيوقّع الاختبار.

اللي بيثبّته:
  ١. أدمن بس · المفتاح مقفول ٤٠٤ بلا أي نداء · `no-store` على كل رد.
  ٢. كل كتابة تطلب `confirmed:true` بالظبط (إلا معاينة الدرس ومسودة المساعد)، و`by` من التوكن وحده، وقائمة بيضا للحقول.
  ٣. السعر والنسبة ما بيوصلوش المنصة أبدًا (أي مفتاح `price*` / `pricing` / `is_free` / نسبة مدرّب).
  ٤. نص `detail` العربي بيوصل `error` بنفس الكود (٤٠٠ · ٤٠٤ · ٤٠٩ · ٤٢٢) · الرد الضايع ⇒ ٥٠٢ + `no_reply` بنداء واحد · ٤٠١/٤٠٣ من المنصة ⇒ ٥٠٢.
  ٥. تدقيق `course2.<إجراء>` عند النجاح بس، والفاعل من التوكن.
"""
import copy
import datetime
import json
import os
import sys

import jwt
import pytest
from werkzeug.security import generate_password_hash

from app import app as flask_app, db, User, AuditLog  # noqa: E402

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(_HERE, 'uiharness'))
import course_editor_fixtures as cef   # noqa: E402

ROOT = os.path.dirname(os.path.dirname(_HERE))
PLATFORM = 'https://platform.test'
SECRET = 'test-metrics-secret'
NON_ADMIN_ROLES = ['employee', 'trainer', 'investor', 'viewer', 'pending']
ADMIN_EMAIL = 'v2c2-admin@x.test'
CONFIRM_AR = 'لازم تأكّد الأول من الشاشة'
NO_REPLY_AR = 'لم يصل رد. حدّث الصفحة وتأكّد مما حدث قبل أن تضغط مرة أخرى.'
IDEM = 'c-0123456789abcdef0123456789abcdef'


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
    u = User(email=email, password_hash=generate_password_hash('x', method='pbkdf2:sha256'), name=email.split('@')[0], role=role, dashboard_role=role,
             linked_to_name='', preferred_currency='AUTO', is_active=True)
    db.session.add(u)
    db.session.commit()
    return u


def _bearer(user):
    tok = jwt.encode({'user_id': user.id, 'exp': datetime.datetime.utcnow() + datetime.timedelta(days=1)}, flask_app.config['SECRET_KEY'], algorithm='HS256')
    return {'Authorization': 'Bearer ' + tok}


@pytest.fixture(scope='module')
def ctx():
    with flask_app.app_context():
        db.create_all()
        heads = {r: _bearer(_mkuser('v2c2-%s@x.test' % r, r)) for r in NON_ADMIN_ROLES}
        heads['admin'] = _bearer(_mkuser(ADMIN_EMAIL, 'admin'))
        yield {'heads': heads, 'client': flask_app.test_client()}


class Plat(object):
    def __init__(self):
        self.ef = cef.Courses2Platform()
        self.seen = []
        self.blocked = []

    def __call__(self, method, url, params=None, json=None, headers=None, timeout=None):
        self.seen.append({'method': method.upper(), 'url': url, 'path': url[len(PLATFORM):], 'params': dict(params or {}), 'json': copy.deepcopy(json), 'timeout': timeout})
        if not url.startswith(PLATFORM + '/'):
            self.blocked.append(url)
            raise RuntimeError('طلب حقيقي ممنوع: ' + url)
        out = self.ef.handle(method, url[len(PLATFORM):], params, json)
        return _Resp(*(out if out is not None else (200, [])))

    def writes(self):
        return [c for c in self.seen if c['method'] != 'GET']


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


def _call(ctx, method, path, body=None, who='admin'):
    heads = {} if who is None else ctx['heads'][who]
    return ctx['client'].open(path, method=method, headers=heads, json=body) if body is not None else ctx['client'].open(path, method=method, headers=heads)


A = '/api/v2/courses2'
LESSON_BODY = {'title': 'ما هو عقد المقاولة؟', 'blocks': [{'type': 'text', 'md': 'نص'}], 'time': 5}
STRUCT_BODY = {'units': [{'id': 'u1', 'title': 'الأساسيات', 'lessons': [{'id': 'L1', 'title': 'ما هو؟', 'kind': 'interactive'}]}]}

# (method, path, body, needs_confirmed)
ROUTES = [
    ('GET', A, None, False),
    ('POST', A, {'title': 'دورة', 'idem_key': IDEM, 'platform_owned': True}, True),
    ('GET', A + '/pc-12', None, False),
    ('PUT', A + '/pc-12/data', {'title': 'عنوان'}, True),
    ('PUT', A + '/pc-12/structure', STRUCT_BODY, True),
    ('PUT', A + '/pc-12/lessons/L1', LESSON_BODY, True),
    ('GET', A + '/pc-12/lessons/L1/preview', None, False),
    ('POST', A + '/pc-12/lessons/L1/preview', LESSON_BODY, False),
    ('POST', A + '/pc-15/publish', {}, True),
    ('POST', A + '/pc-01/pause', {}, True),
    ('POST', A + '/pc-15/return', {'notes': [{'target_kind': 'course', 'target_id': '', 'text': 'ملاحظة'}]}, True),
    ('POST', A + '/pc-12/brain/draft', {'instruction': 'سؤال'}, False),
    ('POST', A + '/pc-12/upload', {'title': 'درس'}, True),
]
WRITE_ROUTES = [r for r in ROUTES if r[3]]


def _body(r, **extra):
    b = copy.deepcopy(r[2]) if r[2] is not None else None
    if b is not None and r[3]:
        b['confirmed'] = True
    if b is not None:
        b.update(extra)
    return b


# ---------------------------------------------------------------- ١) الصلاحيات والمفتاح
@pytest.mark.parametrize('route', ROUTES, ids=lambda r: '%s %s' % (r[0], r[1][len(A):] or '/'))
def test_admin_only_flag_closed_and_no_store(ctx, plat, monkeypatch, route):
    method, path = route[0], route[1]
    for role in NON_ADMIN_ROLES:
        assert _call(ctx, method, path, _body(route), role).status_code == 403, (path, role)
    assert _call(ctx, method, path, _body(route), None).status_code == 401
    assert plat.seen == []
    monkeypatch.setenv('DASH_V2_ENABLED', 'false')
    r = _call(ctx, method, path, _body(route))
    assert r.status_code == 404 and r.headers.get('Cache-Control') == 'no-store'
    assert plat.seen == [], 'المفتاح مقفول ⇒ لا نداء للمنصة'
    monkeypatch.setenv('DASH_V2_ENABLED', 'true')
    r = _call(ctx, method, path, _body(route))
    assert r.status_code in (200, 409, 422), (path, r.status_code, r.get_json())   # جاء من المنصة نفسها
    assert r.headers.get('Cache-Control') == 'no-store'
    assert len(plat.seen) >= 1


@pytest.mark.parametrize('route', WRITE_ROUTES, ids=lambda r: '%s %s' % (r[0], r[1][len(A):]))
@pytest.mark.parametrize('bad', [None, 'true', 1, False, 'yes'])
def test_confirmed_must_be_literally_true(ctx, plat, route, bad):
    b = copy.deepcopy(route[2])
    if bad is not None:
        b['confirmed'] = bad
    r = _call(ctx, route[0], route[1], b)
    assert r.status_code == 400 and r.get_json()['error'] == CONFIRM_AR
    assert r.headers.get('Cache-Control') == 'no-store'
    assert plat.seen == []


def test_preview_post_and_brain_draft_need_no_confirmed_and_write_nothing(ctx, plat):
    n = AuditLog.query.filter(AuditLog.action.like('course2.%')).count()
    r = _call(ctx, 'POST', A + '/pc-12/lessons/L1/preview', LESSON_BODY)
    assert r.status_code == 200 and r.get_json()['saved'] is False
    r = _call(ctx, 'POST', A + '/pc-12/brain/draft', {'instruction': 'حوّل الفقرة إلى نشاط قرار', 'kind': 'activity_decision', 'lesson_id': 'L1'})
    assert r.status_code == 200 and r.get_json()['saved'] is False and r.get_json()['draft']['block']['type'] == 'decision'
    assert AuditLog.query.filter(AuditLog.action.like('course2.%')).count() == n, 'المعاينة والمسودة بلا تدقيق (لا كتابة)'
    pv, br = plat.seen
    assert 'confirmed' not in pv['json'] and 'by' not in pv['json'], 'جسم المعاينة بلا confirmed ولا by'
    assert 'confirmed' not in br['json'] and br['json']['by'] == ADMIN_EMAIL


# ---------------------------------------------------------------- ٢) by من التوكن وقايمة بيضا
def test_by_comes_from_the_token_and_confirmed_is_set_for_the_bridge(ctx, plat):
    for route in WRITE_ROUTES:
        plat.seen.clear()
        _call(ctx, route[0], route[1], _body(route, by='attacker@x.test'))
        (w,) = plat.writes()
        assert w['json']['by'] == ADMIN_EMAIL and w['json']['confirmed'] is True, route[1]
    plat.seen.clear()
    _call(ctx, 'POST', A + '/pc-12/brain/draft', {'instruction': 'سؤال', 'by': 'attacker@x.test'})
    assert plat.seen[0]['json']['by'] == ADMIN_EMAIL


def test_only_whitelisted_fields_reach_the_platform(ctx, plat):
    _call(ctx, 'PUT', A + '/pc-12/data', {'confirmed': True, 'title': 'ع', 'cover': 'https://x.test/a.jpg', 'status': 'published', 'owner': {'email': 'evil@x.test'}, 'id': 'zzz'})
    assert set(plat.writes()[-1]['json']) == {'confirmed', 'by', 'title', 'cover'}
    plat.seen.clear()
    _call(ctx, 'PUT', A + '/pc-12/lessons/L1', {'confirmed': True, 'title': 'ع', 'blocks': [], 'kind': 'live', 'id': 'L9', 'state': 'ready'})
    assert set(plat.writes()[-1]['json']) == {'confirmed', 'by', 'title', 'blocks'}
    plat.seen.clear()
    _call(ctx, 'POST', A, {'confirmed': True, 'title': 'دورة', 'idem_key': IDEM + 'x', 'owner_email': ' Hala@Example.Test ', 'status': 'published', 'slug': 'x'})
    assert plat.writes()[-1]['json'] == {'confirmed': True, 'by': ADMIN_EMAIL, 'title': 'دورة', 'idem_key': IDEM + 'x', 'owner_email': 'hala@example.test'}


def test_blocks_and_units_pass_through_unchanged(ctx, plat):
    blocks = [{'type': 'decision', 'text': 'x', 'question': 'ص', 'options': [{'text': 'أ', 'result': 'ب', 'comment': 'ج'}, {'text': 'د', 'result': 'ه', 'comment': 'و'}], 'price': 5}]
    _call(ctx, 'PUT', A + '/pc-12/lessons/L1', {'confirmed': True, 'title': 'ع', 'blocks': blocks})
    assert plat.writes()[-1]['json']['blocks'] == blocks, 'المحتوى لا يُمسّ (لا نقص خفي) — الكتل أمانة'
    plat.seen.clear()
    _call(ctx, 'PUT', A + '/pc-12/structure', {'confirmed': True, 'cases': ['student'], 'units': STRUCT_BODY['units']})
    assert plat.writes()[-1]['json']['units'] == STRUCT_BODY['units'] and plat.writes()[-1]['json']['cases'] == ['student']


# ---------------------------------------------------------------- ٣) السعر والنسبة
MONEY = {'price': 100, 'price_egp': 450, 'price_usd': 20, 'priceSar': 5, 'pricing': {'is_free': True, 'price_egp': 9}, 'is_free': True, 'trainer_share_pct': 90, 'share_pct': 70, 'max_seats': 5, 'quorum': 3}


@pytest.mark.parametrize('route', WRITE_ROUTES, ids=lambda r: '%s %s' % (r[0], r[1][len(A):]))
def test_price_and_share_fields_never_reach_the_platform(ctx, plat, route):
    _call(ctx, route[0], route[1], _body(route, **MONEY))
    for w in plat.writes():
        flat = json.dumps(w['json'], ensure_ascii=False)
        for k in MONEY:
            assert '"%s"' % k not in flat, (route[1], k)


def test_price_fields_are_stripped_from_preview_and_assistant_bodies_too(ctx, plat):
    _call(ctx, 'POST', A + '/pc-12/lessons/L1/preview', dict(LESSON_BODY, **MONEY))
    _call(ctx, 'POST', A + '/pc-12/brain/draft', dict({'instruction': 'سؤال'}, **MONEY))
    for c in plat.seen:
        assert not (set(c['json']) & set(MONEY)), c['path']


def test_strip_money_is_case_insensitive_and_keeps_the_rest():
    import v2_courses2_routes as m
    out = m.strip_money({'Price_EGP': 1, 'PRICING': {}, 'title': 'ع', 'blocks': [{'price': 3}]})
    assert out == {'title': 'ع', 'blocks': [{'price': 3}]}, 'أول مستوى بس؛ كتلة المحتوى أمانة'


# ---------------------------------------------------------------- ٤) الأخطاء
@pytest.mark.parametrize('code,detail', [(400, 'المحتوى التفاعلي فيه أخطاء — الدرس «تفاعلي»: ::موقف لازم يكون فيه من 2 لـ3 اختيارات — الموجود 1'),
                                         (404, 'الدورة غير موجودة'), (409, 'دورة منشورة فيها متعلّمون: لا يمكن حذف درس منها'),
                                         (422, 'الدورة ناقصها: وصف الدورة')])
def test_platform_arabic_detail_passes_through_as_error_with_the_same_status(ctx, plat, code, detail):
    for route in WRITE_ROUTES + [r for r in ROUTES if r[0] == 'GET' or 'preview' in r[1] or 'brain' in r[1]]:
        plat.ef.forced[(route[0], '/api/bridge/courses2' + route[1][len(A):])] = (code, {'detail': detail})
        r = _call(ctx, route[0], route[1], _body(route))
        assert r.status_code == code and r.get_json() == {'error': detail}, (route[1], r.status_code, r.get_json())
        assert r.headers.get('Cache-Control') == 'no-store'
        del plat.ef.forced[(route[0], '/api/bridge/courses2' + route[1][len(A):])]


def test_structured_and_list_details_become_readable_text(ctx, plat):
    url = '/api/bridge/courses2/pc-12/data'
    plat.ef.forced[('PUT', url)] = (422, {'detail': {'error': 'bad', 'message': 'المستوى غير معروف'}})
    assert _call(ctx, 'PUT', A + '/pc-12/data', {'confirmed': True, 'title': 'ع'}).get_json() == {'error': 'المستوى غير معروف'}
    plat.ef.forced[('PUT', url)] = (422, {'detail': [{'loc': ['body', 'title'], 'msg': 'x'}]})
    r = _call(ctx, 'PUT', A + '/pc-12/data', {'confirmed': True, 'title': 'ع'})
    assert r.status_code == 422 and isinstance(r.get_json()['error'], str) and '[object' not in r.get_json()['error']


@pytest.mark.parametrize('code', [500, 502, 503, 504])
def test_lost_reply_is_flagged_with_one_call_and_the_exact_text(ctx, plat, code):
    n = AuditLog.query.filter_by(action='course2.no_reply').count()
    for route in WRITE_ROUTES + [r for r in ROUTES if r[0] == 'POST' and not r[3]]:
        plat.seen.clear()
        plat.ef.forced[(route[0], '/api/bridge/courses2' + route[1][len(A):])] = (code, {})
        r = _call(ctx, route[0], route[1], _body(route))
        assert r.status_code == 502 and r.get_json() == {'error': NO_REPLY_AR, 'no_reply': True}, (route[1], code, r.get_json())
        assert len(plat.seen) == 1, 'نداء واحد ولا إعادة محاولة'
        del plat.ef.forced[(route[0], '/api/bridge/courses2' + route[1][len(A):])]
    assert AuditLog.query.filter_by(action='course2.no_reply').count() == n + len(WRITE_ROUTES) + 2


def test_platform_auth_failures_become_502_not_a_session_logout(ctx, plat):
    for code in (401, 403):
        plat.ef.forced[('PUT', '/api/bridge/courses2/pc-12/data')] = (code, {'detail': 'x'})
        r = _call(ctx, 'PUT', A + '/pc-12/data', {'confirmed': True, 'title': 'ع'})
        assert r.status_code == 502 and r.get_json() == {'error': 'تعذّر الاتصال بالمنصة'}
        plat.ef.forced[('GET', '/api/bridge/courses2/pc-12')] = (code, {'detail': 'x'})
        r = _call(ctx, 'GET', A + '/pc-12')
        assert r.status_code == 502


def test_a_closed_bridge_404_passes_to_the_screen_for_its_unavailable_state(ctx, plat):
    plat.ef.forced[('GET', '/api/bridge/courses2')] = (404, {'detail': 'Not Found'})
    r = _call(ctx, 'GET', A)
    assert r.status_code == 404 and r.get_json()['error'] == 'Not Found' and r.headers.get('Cache-Control') == 'no-store'


# ---------------------------------------------------------------- ٥) التدقيق
def test_audit_only_on_success_with_the_real_action_and_actor(ctx, plat):
    base = {a: AuditLog.query.filter_by(action='course2.' + a).count() for a in ('data', 'lesson', 'structure', 'create', 'publish', 'pause', 'return', 'upload')}
    plat.ef.forced[('PUT', '/api/bridge/courses2/pc-12/data')] = (400, {'detail': 'رابط الغلاف لازم يبدأ بـ https://'})
    assert _call(ctx, 'PUT', A + '/pc-12/data', {'confirmed': True, 'cover': 'x'}).status_code == 400
    assert AuditLog.query.filter_by(action='course2.data').count() == base['data'], 'الفشل بلا سطر تدقيق'
    del plat.ef.forced[('PUT', '/api/bridge/courses2/pc-12/data')]
    plat.ef.c2[1]['meta']['description'] = 'وصف'
    plat.ef.c2[1]['units'][0]['lessons'][1]['has_video'] = True
    for route in sorted(WRITE_ROUTES, key=lambda x: not x[1].endswith('/return')):    # الإرجاع قبل النشر (يلزم «عند المراجعة»)
        r = _call(ctx, route[0], route[1], _body(route, by='attacker@x.test'))
        assert r.status_code == 200, (route[1], r.get_json())
    for a in base:
        rows = AuditLog.query.filter_by(action='course2.' + a).all()
        assert len(rows) == base[a] + 1, a
        assert rows[-1].actor_email == ADMIN_EMAIL, a
    row = AuditLog.query.filter_by(action='course2.lesson').all()[-1]
    assert row.target == 'pc-12' and 'L1' in (row.meta_json or '') and 'نص' not in (row.meta_json or ''), 'سطر التدقيق بمفاتيح الحقول لا بمحتوى الدرس'


# ---------------------------------------------------------------- ٦) الإنشاء والمعرّفات والمدخلات
def test_create_validation_and_idempotence(ctx, plat):
    for b in ({'title': ''}, {'title': '   '}, {'title': 'ن' * 161}, {'title': 5}):
        assert _call(ctx, 'POST', A, dict(b, confirmed=True, idem_key=IDEM, platform_owned=True)).status_code == 400
    for key in (None, '', 'short', 'a b c d e f g h', 'x' * 81, 7, 'مفتاح-عربي-طويل-جدا'):
        b = {'confirmed': True, 'title': 'دورة', 'platform_owned': True}
        if key is not None:
            b['idem_key'] = key
        assert _call(ctx, 'POST', A, b).status_code == 400, key
    assert plat.seen == []
    r1 = _call(ctx, 'POST', A, {'confirmed': True, 'title': 'دورة', 'idem_key': IDEM + 'a', 'platform_owned': True})
    r2 = _call(ctx, 'POST', A, {'confirmed': True, 'title': 'دورة', 'idem_key': IDEM + 'a', 'platform_owned': True})
    assert r1.get_json()['created'] is True and r2.get_json()['created'] is False
    assert r1.get_json()['course']['id'] == r2.get_json()['course']['id']
    # بلا مالك: قرار المنصة يعدّي بنصه (٤٢٢)
    r = _call(ctx, 'POST', A, {'confirmed': True, 'title': 'دورة', 'idem_key': IDEM + 'b'})
    assert r.status_code == 422 and 'بريد المدرّب' in r.get_json()['error']
    assert plat.writes()[-1]['json'].get('platform_owned') is None


def test_bad_ids_are_refused_before_any_call(ctx, plat):
    for ident in ('a' * 300, 'a$b', 'a%b', 'a b', 'a%3Fb', 'a%23b'):
        for method, tail, body in (('GET', '', None), ('PUT', '/data', {'confirmed': True, 'title': 'ع'}), ('PUT', '/structure', {'confirmed': True, 'units': []}),
                                   ('POST', '/publish', {'confirmed': True}), ('POST', '/pause', {'confirmed': True}), ('POST', '/return', {'confirmed': True, 'notes': []}),
                                   ('POST', '/upload', {'confirmed': True}), ('POST', '/brain/draft', {'instruction': 'س'})):
            r = _call(ctx, method, A + '/' + ident + tail, body)
            assert r.status_code in (400, 404, 405), (ident, tail, r.status_code)
        r = _call(ctx, 'PUT', A + '/pc-12/lessons/' + ident, {'confirmed': True, 'title': 'ع'})
        assert r.status_code in (400, 404, 405)
    assert plat.seen == []


def test_return_notes_are_validated_before_the_call(ctx, plat):
    url = A + '/pc-15/return'
    ok = {'target_kind': 'lesson', 'target_id': 'M2', 'text': 'ينقصه الفيديو.'}
    for notes in ([], None, 'x', [{}], [dict(ok, target_kind='x')], [dict(ok, text='')], [dict(ok, text='ن' * 601)], [ok] * 41, ['x']):
        assert _call(ctx, 'POST', url, {'confirmed': True, 'notes': notes}).status_code == 400, notes
    assert plat.seen == []
    r = _call(ctx, 'POST', url, {'confirmed': True, 'notes': [ok, {'target_kind': 'course', 'target_id': 'ignored', 'text': ' عامة '}, {'target_kind': 'unit', 'target_id': 'm1', 'text': 'x', 'junk': 1}]})
    assert r.status_code == 200 and r.get_json()['course']['status'] == 'changes'
    assert plat.writes()[-1]['json']['notes'] == [ok, {'target_kind': 'course', 'target_id': '', 'text': 'عامة'}, {'target_kind': 'unit', 'target_id': 'm1', 'text': 'x'}]
    # من غير «عند المراجعة»: ٤٠٩ بنص المنصة
    r = _call(ctx, 'POST', url, {'confirmed': True, 'notes': [ok]})
    assert r.status_code == 409 and 'عند المراجعة' in r.get_json()['error']


def test_brain_draft_requires_an_instruction_and_a_valid_lesson_id(ctx, plat):
    assert _call(ctx, 'POST', A + '/pc-12/brain/draft', {'instruction': '  '}).status_code == 400
    assert _call(ctx, 'POST', A + '/pc-12/brain/draft', {'instruction': 'س', 'lesson_id': 'a b'}).status_code == 400
    assert plat.seen == []
    r = _call(ctx, 'POST', A + '/pc-12/brain/draft', {'instruction': 'حوّل مادتي', 'kind': 'from_material', 'material': 'م' * 100, 'extra': 'x'})
    assert r.status_code == 200 and r.get_json()['lessons'] == 3
    assert set(plat.seen[-1]['json']) == {'instruction', 'kind', 'material', 'by'}


def test_preview_get_passes_a_clean_case_and_reads_never_write(ctx, plat):
    r = _call(ctx, 'GET', A + '/pc-12/lessons/L1/preview?case=student')
    assert r.status_code == 200 and plat.seen[-1]['params'] == {'case': 'student'}
    plat.seen.clear()
    _call(ctx, 'GET', A + '/pc-12/lessons/L1/preview?case=a b;c')
    assert plat.seen[-1]['params'] == {}
    assert all(c['method'] == 'GET' for c in plat.seen)


def test_upload_returns_the_tus_headers_and_the_unconfigured_answer(ctx, plat):
    r = _call(ctx, 'POST', A + '/pc-12/upload', {'confirmed': True, 'title': 'درس'})
    j = r.get_json()
    assert r.status_code == 200 and j['configured'] is True and j['upload_url'] == 'https://video.bunnycdn.com/tusupload'
    assert set(j['headers']) == {'AuthorizationSignature', 'AuthorizationExpire', 'VideoId', 'LibraryId'}
    plat.ef.bunny = False
    assert _call(ctx, 'POST', A + '/pc-12/upload', {'confirmed': True, 'title': 'درس'}).get_json() == {'ok': True, 'configured': False}


# ---------------------------------------------------------------- ٧) الملفات
def test_wiring_dockerfiles_and_csp():
    app_src = _read('backend', 'app.py')
    assert "import v2_courses2_routes; v2_courses2_routes.register(app, globals())" in app_src
    assert app_src.index('v2_courses_routes.register(app, globals())') < app_src.index('v2_courses2_routes.register(app, globals())')
    for d in (_read('Dockerfile'), _read('deploy', 'Dockerfile.coolify')):
        assert 'COPY backend/v2_courses2_routes.py /app/v2_courses2_routes.py' in d
    assert "connect-src 'self' https://video.bunnycdn.com;" in app_src
    html = _read('dashboard-cloud', 'index.html')
    assert html.index('v2s/course_editor.js') < html.index('v2s/courses.js') and 'v2s/course_editor.css' in html


def test_a_get_to_a_write_only_route_is_not_a_second_door(ctx, plat):
    for tail in ('/data', '/structure', '/publish', '/pause', '/return', '/upload', '/brain/draft'):
        r = _call(ctx, 'GET', A + '/pc-12' + tail)       # الواجهة الثابتة تردّ على أي GET مجهول؛ المهم أنه لا يصل المنصة
        assert 'application/json' not in (r.headers.get('Content-Type') or '') or r.status_code in (404, 405), tail
    assert plat.seen == []
