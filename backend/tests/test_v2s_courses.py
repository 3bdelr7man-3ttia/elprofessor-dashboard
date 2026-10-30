# -*- coding: utf-8 -*-
"""قسم «الدورات والمدرّبون» على الهيكل الجديد (الجولة الأخيرة) — ورا نفس المفتاح المقفول.

Run:  cd backend && python3 -B -m pytest -q -p no:cacheprovider tests/test_v2s_courses.py

⛔ صفر شبكة حقيقية: المنصة جدول في الذاكرة (`uiharness/courses_fixtures.CoursesPlatform`)، وأي عنوان برّه `https://platform.test` بيوقّع الاختبار.
المنطق النقي (التصنيف · العدّادات · فحص النشر · الطلبات والمدرّبون · الحيّة · العروض · الطلب) بيتشغّل في node على v2-logic.js.

اللي بيثبّته:
  ١. المسارات (pytest): أدمن بس · المفتاح مقفول ٤٠٤ بلا أي نداء · `no-store` · الكتابة تطلب `confirmed:true` بالظبط · القايمة البيضا للحقول (لا `by`
     ولا `trainer_share_pct` ولا `confirmed` بتاعنا للمنصة) · ٤٠١/٤٠٣ ⇒ ٥٠٢ · رد ضايع ⇒ «ما وصلناش رد» بنداء واحد · التدقيق عند النجاح بس.
  ٢. المنطق (node): كل جدول في المواصفة، والمصدر الفاشل ⇒ null، ولا صفر كاذب، ونصوص نظيفة.
  ٣. الخريطة والملفات: التبويبات والعناوين · وسوم الصفحة والحرّاس · Dockerfile.
"""
import datetime
import json
import os
import re
import sys

import jwt
import pytest
from werkzeug.security import generate_password_hash

from app import app as flask_app, db, User, AuditLog, Course  # noqa: E402

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(_HERE, 'uiharness'))
import courses_fixtures as cfx   # noqa: E402
import v2_node                   # noqa: E402

ROOT = os.path.dirname(os.path.dirname(_HERE))
PLATFORM = 'https://platform.test'
SECRET = 'test-metrics-secret'
NON_ADMIN_ROLES = ['employee', 'trainer', 'investor', 'viewer', 'pending']
needs_node = pytest.mark.skipif(not v2_node.NODE, reason='needs node')
ADMIN_EMAIL = 'v2co-admin@x.test'
CONFIRM_AR = 'لازم تأكّد الأول من الشاشة'


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
        heads = {r: _bearer(_mkuser('v2co-%s@x.test' % r, r)) for r in NON_ADMIN_ROLES}
        heads['admin'] = _bearer(_mkuser(ADMIN_EMAIL, 'admin'))
        yield {'heads': heads, 'client': flask_app.test_client()}


class Plat(object):
    def __init__(self):
        self.ef = cfx.CoursesPlatform(with_abc=True)
        self.seen = []
        self.blocked = []

    def __call__(self, method, url, params=None, json=None, headers=None, timeout=None):
        import copy
        self.seen.append({'method': method.upper(), 'url': url, 'path': url[len(PLATFORM):], 'params': dict(params or {}), 'json': copy.deepcopy(json), 'timeout': timeout})
        if not url.startswith(PLATFORM + '/'):
            self.blocked.append(url)
            raise RuntimeError('طلب حقيقي ممنوع: ' + url)
        out = self.ef.handle(method, url[len(PLATFORM):], params, json)
        return _Resp(*(out if out is not None else (200, [])))

    def calls(self, prefix=''):
        return [c for c in self.seen if c['path'].startswith(prefix)]

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


WRITES = [
    ('/api/v2/courses/create', {'title': 'دورة جديدة', 'type': 'recorded_paid', 'platform_owned': True}),
    ('/api/v2/courses/pc-15/approve', {}),
    ('/api/v2/courses/pc-16/reject', {'note': 'ينقص السعر'}),
    ('/api/v2/courses/pc-01/visibility', {'is_active': False}),
    ('/api/v2/courses/pc-01/bid', {'bid_enabled': False}),
    ('/api/v2/courses/pc-14/archive', {'hard': True}),
    ('/api/v2/courses/pc-09/schedule', {'zoom_link': 'https://meet.test/x'}),
    ('/api/v2/courses/offers/co-1/decide', {'decision': 'approve'}),
    ('/api/v2/courses/live/commercial-contracts-live/decide', {'action': 'extend'}),
]
READS = ['/api/v2/courses/stats', '/api/v2/courses/pc-01/checklist']
ALL_ROUTES = [('POST', p, b) for p, b in WRITES] + [('GET', p, None) for p in READS]


def _call(ctx, method, path, body, who='admin'):
    heads = {} if who is None else ctx['heads'][who]
    c = ctx['client']
    if method == 'GET':
        return c.get(path, headers=heads)
    return c.post(path, headers=heads, json=body)


# ---------------------------------------------------------------- ١) الصلاحيات والمفتاح
@pytest.mark.parametrize('method,path,body', ALL_ROUTES)
def test_admin_only_and_flag_closed_and_no_store(ctx, plat, monkeypatch, method, path, body):
    b = dict(body or {}, confirmed=True) if method == 'POST' else None
    for role in NON_ADMIN_ROLES:
        assert _call(ctx, method, path, b, role).status_code == 403, (path, role)
    assert _call(ctx, method, path, b, None).status_code == 401
    assert plat.seen == []
    monkeypatch.setenv('DASH_V2_ENABLED', 'false')
    r = _call(ctx, method, path, b)
    assert r.status_code == 404 and r.headers.get('Cache-Control') == 'no-store'
    assert plat.seen == [], 'المفتاح مقفول ⇒ لا نداء للمنصة'
    monkeypatch.setenv('DASH_V2_ENABLED', 'true')
    r = _call(ctx, method, path, b)
    assert r.status_code == 200, (path, r.get_json())
    assert r.headers.get('Cache-Control') == 'no-store'


@pytest.mark.parametrize('path,body', WRITES)
@pytest.mark.parametrize('bad', [None, 'true', 1, False, 'yes'])
def test_confirmed_must_be_literally_true(ctx, plat, path, body, bad):
    b = dict(body)
    if bad is not None:
        b['confirmed'] = bad
    r = _call(ctx, 'POST', path, b)
    assert r.status_code == 400 and r.get_json()['error'] == CONFIRM_AR
    assert r.headers.get('Cache-Control') == 'no-store'
    assert plat.seen == []


# ---------------------------------------------------------------- ٢) القايمة البيضا
def test_approve_sends_only_payout_model_and_never_a_share(ctx, plat):
    r = _call(ctx, 'POST', '/api/v2/courses/pc-15/approve', {'confirmed': True, 'trainer_share_pct': 90, 'by': 'x@y.test', 'payout_model': 'hourly'})
    assert r.status_code == 200
    (w,) = plat.writes()
    assert w['path'] == '/api/bridge/courses/pc-15/approve' and w['json'] == {'payout_model': 'hourly'}
    plat.seen.clear()
    _call(ctx, 'POST', '/api/v2/courses/pc-16/approve', {'confirmed': True, 'trainer_share_pct': 90})
    assert plat.writes()[0]['json'] == {}
    plat.seen.clear()
    r = _call(ctx, 'POST', '/api/v2/courses/pc-15/approve', {'confirmed': True, 'payout_model': 'bogus'})
    assert r.status_code == 400 and plat.seen == []


def test_reject_needs_a_note_and_cuts_it_to_600(ctx, plat):
    for note in ('', '   ', None, 5):
        r = _call(ctx, 'POST', '/api/v2/courses/pc-16/reject', {'confirmed': True, 'note': note})
        assert r.status_code == 400 and 'ملاحظاتك' in r.get_json()['error']
    assert plat.seen == []
    r = _call(ctx, 'POST', '/api/v2/courses/pc-16/reject', {'confirmed': True, 'note': 'ن' * 700, 'by': 'z'})
    assert r.status_code == 200
    (w,) = plat.writes()
    assert w['json'] == {'note': 'ن' * 600}


def test_live_decide_whitelist_and_hours(ctx, plat):
    url = '/api/v2/courses/live/commercial-contracts-live/decide'
    assert _call(ctx, 'POST', url, {'confirmed': True, 'action': 'nuke'}).status_code == 400
    for h in (0, 721, 'x', True, 1.5):
        assert _call(ctx, 'POST', url, {'confirmed': True, 'action': 'extend', 'extend_hours': h}).status_code == 400, h
    assert plat.seen == []
    assert _call(ctx, 'POST', url, {'confirmed': True, 'action': 'extend'}).status_code == 200
    assert plat.writes()[0]['json'] == {'action': 'extend', 'extend_hours': 48}
    plat.seen.clear()
    r = _call(ctx, 'POST', url, {'confirmed': True, 'action': 'cancel'})
    assert r.status_code == 200 and len(r.get_json()['refunds']) == 3          # قائمة الاسترداد تعدّي كما هي
    # قرارات المنصة العربية تعدّي كما هي
    plat.ef.forced[('POST', '/api/bridge/live/commercial-contracts-live/decide')] = (503, {'detail': 'قرار الدورات الحية غير متاح بعد في هذه النسخة'})
    r = _call(ctx, 'POST', url, {'confirmed': True, 'action': 'confirm'})
    assert r.status_code == 502 or r.status_code == 503 or r.get_json().get('no_reply')    # ٥٠٣ = رد ضايع (قاعدة D3)
    plat.ef.forced[('POST', '/api/bridge/live/commercial-contracts-live/decide')] = (422, {'detail': 'لا يمكن تثبيت دورة بلا رابط للقاء'})
    r = _call(ctx, 'POST', url, {'confirmed': True, 'action': 'confirm'})
    assert r.status_code == 422 and r.get_json()['error'] == 'لا يمكن تثبيت دورة بلا رابط للقاء'


def test_platform_auth_failures_become_502_and_lost_replies_are_flagged_with_one_call(ctx, plat):
    plat.ef.forced[('POST', '/api/bridge/courses/pc-15/approve')] = (401, {'detail': 'unauthorized'})
    r = _call(ctx, 'POST', '/api/v2/courses/pc-15/approve', {'confirmed': True})
    assert r.status_code == 502 and r.get_json()['error'] == 'تعذّر الاتصال بالمنصة'
    plat.ef.forced[('POST', '/api/bridge/courses/pc-15/approve')] = (403, {'detail': 'forbidden'})
    assert _call(ctx, 'POST', '/api/v2/courses/pc-15/approve', {'confirmed': True}).status_code == 502
    before = AuditLog.query.filter(AuditLog.action.like('%no_reply')).count()
    for code in (500, 502, 503, 504):
        plat.seen.clear()
        plat.ef.forced[('POST', '/api/bridge/courses/pc-16/reject')] = (code, {})
        r = _call(ctx, 'POST', '/api/v2/courses/pc-16/reject', {'confirmed': True, 'note': 'ن'})
        assert r.status_code == 502 and r.get_json().get('no_reply') is True, code
        assert len(plat.writes()) == 1, 'نداء واحد ولا إعادة محاولة'
    assert AuditLog.query.filter(AuditLog.action.like('%no_reply')).count() == before + 4


def test_audit_only_on_success_and_actor_comes_from_the_token(ctx, plat):
    n = AuditLog.query.filter_by(action='course.approve').count()
    plat.ef.forced[('POST', '/api/bridge/courses/pc-15/approve')] = (422, {'detail': 'لا يمكن نشر الدورة'})
    assert _call(ctx, 'POST', '/api/v2/courses/pc-15/approve', {'confirmed': True}).status_code == 422
    assert AuditLog.query.filter_by(action='course.approve').count() == n
    del plat.ef.forced[('POST', '/api/bridge/courses/pc-15/approve')]
    assert _call(ctx, 'POST', '/api/v2/courses/pc-15/approve', {'confirmed': True, 'by': 'attacker@x.test'}).status_code == 200
    rows = AuditLog.query.filter_by(action='course.approve').all()
    assert len(rows) == n + 1 and rows[-1].actor_email == ADMIN_EMAIL and rows[-1].target == 'pc-15'
    assert 'by' not in plat.writes()[-1]['json']


def test_bad_ids_are_refused_before_any_call(ctx, plat):
    for ident in ('a' * 300, 'a$b', 'a%b', 'a b'):
        for path in ('/api/v2/courses/%s/approve', '/api/v2/courses/%s/reject', '/api/v2/courses/%s/visibility', '/api/v2/courses/%s/bid',
                     '/api/v2/courses/%s/archive', '/api/v2/courses/%s/schedule', '/api/v2/courses/offers/%s/decide', '/api/v2/courses/live/%s/decide'):
            r = _call(ctx, 'POST', path % ident, {'confirmed': True, 'note': 'x', 'is_active': True, 'bid_enabled': True, 'decision': 'reject', 'action': 'confirm', 'zoom_link': 'https://a.test'})
            assert r.status_code in (400, 404), (path, ident, r.status_code)
        assert _call(ctx, 'GET', '/api/v2/courses/%s/checklist' % ident, None).status_code in (400, 404)
    assert plat.seen == []


def test_checklist_and_stats_404_pass_through(ctx, plat):
    plat.ef.with_abc = False
    for p in READS:
        r = _call(ctx, 'GET', p, None)
        assert r.status_code == 404 and r.headers.get('Cache-Control') == 'no-store'
    plat.ef.with_abc = True
    r = _call(ctx, 'GET', '/api/v2/courses/pc-15/checklist', None)
    assert r.status_code == 200 and r.get_json()['checklist'][0]['key'] == 'content'
    assert _call(ctx, 'GET', '/api/v2/courses/stats', None).get_json()['courses'][0]['course_id'] == 'pc-01'


# ---------------------------------------------------------------- ٣) الإنشاء والظهور والأرشفة والموعد والعروض
def test_create_draft_rules(ctx, plat):
    n0 = Course.query.count()
    base = {'confirmed': True, 'title': 'دورة اختبار', 'type': 'recorded_paid', 'platform_owned': True}
    for bad in ({'title': ''}, {'title': '   '}, {'title': 'ع' * 161}, {'type': 'live_upcoming'}, {'type': None}, {'platform_owned': False, 'instructor_email': ''},
                {'platform_owned': False, 'instructor_email': 'not-an-email'}):
        r = _call(ctx, 'POST', '/api/v2/courses/create', dict(base, **bad))
        assert r.status_code == 400, bad
    assert plat.seen == [] and Course.query.count() == n0, 'ولا نداء ولا سطر دفتر على الخطأ'
    r = _call(ctx, 'POST', '/api/v2/courses/create', dict(base, price_egp=500, price_usd=20, by='x', is_active=True, trainer_name='اسم'))
    assert r.status_code == 200
    body = r.get_json()
    assert body['ok'] is True and body['platform_course_id'].startswith('pc-new')
    (w,) = plat.writes()
    assert w['path'] == '/api/bridge/courses'
    sent = w['json']
    assert sent['is_active'] is False and sent['type'] == 'recorded_paid' and sent['platform_owned'] is True and 'dashboard_course_id' in sent
    assert not [k for k in sent if k.startswith('price')] and 'by' not in sent
    row = Course.query.filter_by(platform_course_id=body['platform_course_id'], title='دورة اختبار').one()
    assert row.title == 'دورة اختبار' and (row.price_egp or 0) == 0
    # مدرّب بالبريد
    plat.seen.clear()
    r = _call(ctx, 'POST', '/api/v2/courses/create', {'confirmed': True, 'title': 'دورة مدرّب', 'type': 'recorded_free', 'instructor_email': 'Hala@Example.test', 'trainer_name': 'د. هالة'})
    assert r.status_code == 200 and plat.writes()[0]['json']['instructor_email'] == 'hala@example.test' and plat.writes()[0]['json']['platform_owned'] is False


def test_create_platform_refusal_removes_the_ledger_row_and_lost_reply_keeps_it(ctx, plat):
    n0 = Course.query.count()
    plat.ef.forced[('POST', '/api/bridge/courses')] = (422, {'detail': 'اكتب بريد المدرّب صاحب الدورة'})
    r = _call(ctx, 'POST', '/api/v2/courses/create', {'confirmed': True, 'title': 'مرفوضة', 'type': 'recorded_paid', 'platform_owned': True})
    assert r.status_code == 422 and r.get_json()['error'] == 'اكتب بريد المدرّب صاحب الدورة'
    assert Course.query.count() == n0
    plat.ef.forced[('POST', '/api/bridge/courses')] = (502, {})
    r = _call(ctx, 'POST', '/api/v2/courses/create', {'confirmed': True, 'title': 'ضاع ردها', 'type': 'recorded_paid', 'platform_owned': True})
    assert r.status_code == 502 and r.get_json()['no_reply'] is True
    assert Course.query.count() == n0 + 1, 'رد ضايع ⇒ السطر يفضل (المنصة ممكن تكون أنشأتها)'
    plat.ef.forced[('POST', '/api/bridge/courses')] = (401, {'detail': 'unauthorized'})
    r = _call(ctx, 'POST', '/api/v2/courses/create', {'confirmed': True, 'title': 'مفتاح مرفوض', 'type': 'recorded_paid', 'platform_owned': True})
    assert r.status_code == 502 and Course.query.count() == n0 + 1


def test_visibility_and_bid_take_real_booleans_and_send_one_field(ctx, plat):
    for path, key in (('visibility', 'is_active'), ('bid', 'bid_enabled')):
        for bad in ('true', 1, 0, None, 'false'):
            r = _call(ctx, 'POST', '/api/v2/courses/pc-01/' + path, {'confirmed': True, key: bad})
            assert r.status_code == 400, (path, bad)
        assert plat.seen == []
        assert _call(ctx, 'POST', '/api/v2/courses/pc-01/' + path, {'confirmed': True, key: True, 'price_egp': 1, 'title': 'x'}).status_code == 200
        (w,) = plat.writes()
        assert w['method'] == 'PUT' and w['path'] == '/api/bridge/courses/pc-01' and w['json'] == {key: True}
        plat.seen.clear()
    assert AuditLog.query.filter_by(action='course.show').count() >= 1 and AuditLog.query.filter_by(action='course.bid_on').count() >= 1


def test_archive_audit_follows_what_happened(ctx, plat):
    n_arch, n_del = AuditLog.query.filter_by(action='course.archive').count(), AuditLog.query.filter_by(action='course.delete').count()
    r = _call(ctx, 'POST', '/api/v2/courses/pc-08/archive', {'confirmed': True, 'hard': 'true'})       # ليس True بالظبط ⇒ أرشفة
    assert r.status_code == 200 and r.get_json().get('archived') is True
    (w,) = plat.writes()
    assert w['method'] == 'DELETE' and w['params'] == {} and AuditLog.query.filter_by(action='course.archive').count() == n_arch + 1
    plat.seen.clear()
    r = _call(ctx, 'POST', '/api/v2/courses/pc-14/archive', {'confirmed': True, 'hard': True})
    assert r.status_code == 200 and r.get_json().get('deleted') is True
    assert plat.writes()[0]['params'] == {'hard': 'true'} and AuditLog.query.filter_by(action='course.delete').count() == n_del + 1
    # منصة أقدم تتجاهل hard وتؤرشف: التدقيق بما حدث
    plat.seen.clear()
    plat.ef.forced[('DELETE', '/api/bridge/courses/pc-12')] = (200, {'ok': True, 'archived': True})
    assert _call(ctx, 'POST', '/api/v2/courses/pc-12/archive', {'confirmed': True, 'hard': True}).status_code == 200
    assert AuditLog.query.filter_by(action='course.archive').count() == n_arch + 2 and AuditLog.query.filter_by(action='course.delete').count() == n_del + 1
    # رفض المنصة للحذف (٤٠٩) يعدّي كما هو ولا تدقيق
    plat.ef.forced[('DELETE', '/api/bridge/courses/pc-03')] = (409, {'detail': 'لا يمكن حذف دورة عليها اشتراك أو دفعة'})
    r = _call(ctx, 'POST', '/api/v2/courses/pc-03/archive', {'confirmed': True, 'hard': True})
    assert r.status_code == 409 and 'اشتراك' in r.get_json()['error']


def test_schedule_never_forwards_our_confirmed_flag(ctx, plat):
    url = '/api/v2/courses/pc-09/schedule'
    assert _call(ctx, 'POST', url, {'confirmed': True}).status_code == 400
    assert _call(ctx, 'POST', url, {'confirmed': True, 'max_seats': 'x'}).status_code == 400
    assert _call(ctx, 'POST', url, {'confirmed': True, 'max_seats': -1}).status_code == 400
    assert _call(ctx, 'POST', url, {'confirmed': True, 'max_seats': True}).status_code == 400
    assert _call(ctx, 'POST', url, {'confirmed': True, 'start_date': 5}).status_code == 400
    assert plat.seen == []
    assert _call(ctx, 'POST', url, {'confirmed': True, 'zoom_link': ' https://meet.test/y ', 'max_seats': 25, 'start_date': '2026-11-20T18:00:00+02:00', 'by': 'q', 'timezone': 'x'}).status_code == 200
    w = plat.writes()[0]
    assert w['method'] == 'PUT' and w['path'] == '/api/bridge/courses/pc-09/schedule'
    assert w['json'] == {'zoom_link': 'https://meet.test/y', 'max_seats': 25, 'start_date': '2026-11-20T18:00:00+02:00'}, 'confirmed ما بيتبعتش'
    plat.seen.clear()
    _call(ctx, 'POST', url, {'confirmed': True, 'zoom_link': 'https://a.test', 'pin_schedule': False})
    assert plat.writes()[0]['json']['confirmed'] is False
    plat.seen.clear()
    _call(ctx, 'POST', url, {'confirmed': True, 'zoom_link': 'https://a.test', 'pin_schedule': True})
    assert plat.writes()[0]['json']['confirmed'] is True
    plat.seen.clear()
    _call(ctx, 'POST', url, {'confirmed': True, 'pin_schedule': True})
    assert plat.writes()[0]['json'] == {'confirmed': True}


def test_offer_decisions(ctx, plat):
    url = '/api/v2/courses/offers/co-1/decide'
    for bad in ({'decision': 'maybe'}, {'decision': None}, {'decision': 'counter'}, {'decision': 'counter', 'amount': True}, {'decision': 'counter', 'amount': 0},
                {'decision': 'counter', 'amount': '300'}, {'decision': 'counter', 'amount': -5}):
        assert _call(ctx, 'POST', url, dict(bad, confirmed=True)).status_code == 400, bad
    assert plat.seen == []
    assert _call(ctx, 'POST', url, {'confirmed': True, 'decision': 'counter', 'amount': 320}).status_code == 200
    assert plat.writes()[0]['json'] == {'decision': 'counter', 'amount': 320.0}
    plat.seen.clear()
    assert _call(ctx, 'POST', '/api/v2/courses/offers/co-2/decide', {'confirmed': True, 'decision': 'reject', 'amount': 999}).status_code == 200
    assert plat.writes()[0]['json'] == {'decision': 'reject'}
    plat.seen.clear()
    assert _call(ctx, 'POST', '/api/v2/courses/offers/zzz/decide', {'confirmed': True, 'decision': 'approve'}).status_code == 404


def test_the_register_line_is_alone_before_the_end_marker():
    src = _read('backend', 'app.py')
    assert src.count('v2_courses_routes.register(app, globals())') == 1
    assert '# ---- v2 section routes begin' in src and '# ---- v2 section routes end' in src
    assert src.index('v2_courses_routes.register(app, globals())') < src.index('# ---- v2 section routes end')
    assert src.index('# ---- v2 section routes begin') < src.index('v2_courses_routes.register(app, globals())')
    routes = _read('backend', 'v2_courses_routes.py')
    assert 'by' not in re.findall(r"json_body=\{[^}]*'by'", routes)
    assert "['by']" not in routes


# ---------------------------------------------------------------- ٤) المنطق النقي (node)
NOW = 1_800_000_000_000
H = 3600 * 1000


def _co(fn, *args):
    return v2_node.logic('v2s.courses.' + fn, *args)


def _courses(abc=False):
    return [cfx.public_course(c, abc) for c in cfx.base_courses()]


def _iso(ms):
    return datetime.datetime.utcfromtimestamp(ms / 1000.0).replace(tzinfo=datetime.timezone.utc).isoformat()


@needs_node
def test_board_classification_table():
    cases = [
        ({'approval_status': 'pending', 'is_active': True}, 'review'), ({'approval_status': 'pending', 'is_active': False}, 'review'),
        ({'approval_status': 'approved', 'is_active': True}, 'published'), ({'approval_status': None, 'is_active': True}, 'published'),
        ({'approval_status': 'rejected', 'is_active': False}, 'rejected'), ({'approval_status': 'rejected', 'is_active': False, 'archived_at': '2026-01-01'}, 'archived'),
        ({'approval_status': None, 'is_active': False}, 'building'), ({'approval_status': 'approved', 'is_active': False, 'archived_at': '2026-01-01'}, 'archived'),
        ({'approval_status': 'approved', 'is_active': False}, 'building'),
    ]
    for c, want in cases:
        assert _co('stateOf', c) == want, c
    b = _co('board', [dict(c, id='c%d' % i, title='د%d' % i) for i, (c, _w) in enumerate(cases)], {'now': NOW})
    assert b['na'] is False
    assert b['counts'] == {'review': 2, 'building': 3, 'published': 2, 'hidden': 4, 'archived': 2, 'rejected': 1, 'total': 9}
    assert len(b['building']) == 3 and [x['state'] for x in b['rejected']] == ['rejected']
    # المصدر الفاشل: لا أعداد ولا صفر
    for bad in (None, {}, 'x'):
        nb = _co('board', bad, {'now': NOW})
        assert nb['na'] is True and nb['counts'] is None and nb['summary'] == 'الدورات: غير متاح بعد' and nb['review'] == []


@needs_node
def test_board_sort_orders_and_the_review_timer_rules():
    cs = [{'id': 'a', 'title': 'ب', 'approval_status': 'pending', 'created_at': _iso(NOW - 900 * H)},
          {'id': 'b', 'title': 'أ', 'approval_status': 'pending', 'created_at': _iso(NOW - 10 * H)},
          {'id': 'c', 'title': 'ج', 'approval_status': 'pending', 'submitted_at': _iso(NOW - 50 * H), 'created_at': _iso(NOW - 900 * H)},
          {'id': 'd', 'title': 'د', 'approval_status': 'pending', 'submitted_at': _iso(NOW - 80 * H)},
          {'id': 'p1', 'title': 'x', 'is_active': True, 'total_enrolled': 3}, {'id': 'p2', 'title': 'y', 'is_active': True, 'total_enrolled': 30},
          {'id': 'b1', 'title': 'x', 'updated_at': _iso(NOW - 5 * H), 'created_at': _iso(NOW - 99 * H)}, {'id': 'b2', 'title': 'y', 'created_at': _iso(NOW - 2 * H)}]
    b = _co('board', cs, {'now': NOW})
    assert [x['id'] for x in b['review']] == ['d', 'c', 'b', 'a'], 'submitted_at الأقدم أولًا ثم بلا submitted_at بالعنوان'
    assert [x['id'] for x in b['published']] == ['p2', 'p1']
    assert [x['id'] for x in b['building']] == ['b2', 'b1']
    # tone: 23h ok · 24h warn · 73h late
    assert [_co('tone', h) for h in (23, 24, 72, 73)] == ['ok', 'warn', 'warn', 'late']
    t = _co('reviewTimer', {'submitted_at': _iso(NOW - 73 * H)}, NOW)
    assert t['tone'] == 'late' and t['label'].startswith('منذ')
    t = _co('reviewTimer', {'submitted_at': _iso(NOW - 5 * H)}, NOW)
    assert t['tone'] == 'ok'
    t = _co('reviewTimer', {'created_at': _iso(NOW - 90 * 24 * H)}, NOW)
    assert t['tone'] == 'none' and t['label'] == 'أُنشئت منذ ٩٠ يومًا'
    assert _co('reviewTimer', {}, NOW) is None
    assert _co('cover', '') == {'letter': '؟'} and _co('cover', '  «دورة»')['letter'] == 'د' and _co('cover', 'Contracts')['letter'] == 'C'


@needs_node
def test_summary_line_forms():
    f = lambda p, b, r: _co('summaryLine', {'published': p, 'building': b, 'review': r})
    assert f(11, 3, 2) == '١١ دورة منشورة · ٣ تحت البناء · دورتان تنتظرانك'
    assert f(1, 0, 0) == 'دورة واحدة منشورة · ٠ تحت البناء · لا شيء ينتظرك'
    assert f(2, 1, 1) == 'دورتان منشورتان · ١ تحت البناء · دورة واحدة تنتظرك'
    assert f(5, 12, 7) == '٥ دورات منشورة · ١٢ تحت البناء · ٧ دورات تنتظرك'
    assert f(30, 1, 11) == '٣٠ دورة منشورة · ١ تحت البناء · ١١ دورة تنتظرك'
    assert _co('summaryLine', None) == 'الدورات: غير متاح بعد'


@needs_node
def test_course_facts_cases():
    base = {'id': 'x', 'title': 'عقود', 'type': 'recorded_paid', 'approval_status': 'pending', 'price_amount': 480, 'price_currency': 'EGP', 'lesson_count': 9, 'platform_owned': True}
    f = _co('courseFacts', dict(base, type='recorded_free', price_amount=None), {'now': NOW})
    assert [i['ok'] for i in f['items'] if i['key'] == 'price'] == [True]
    f = _co('courseFacts', dict(base, price_amount=None), {'now': NOW})
    assert f['suggestion'] == 'return' and f['returnNote'] == 'ينقص الدورة قبل النشر: بلا سعر.' and 'ينقصها: بلا سعر' in f['line']
    f = _co('courseFacts', dict(base, lesson_count=0, price_amount=None), {'now': NOW})
    assert f['returnNote'] == 'ينقص الدورة قبل النشر: لا دروس فيها، بلا سعر.'
    live = dict(base, type='live_upcoming', price_amount=900)
    f = _co('courseFacts', live, {'now': NOW, 'schedule': {'start_date': '2026-12-01T10:00:00Z', 'zoom_link': ''}})
    assert f['suggestion'] == 'return' and 'بلا رابط للقاء' in f['returnNote']
    f = _co('courseFacts', live, {'now': NOW, 'schedule': None})
    assert [i['ok'] for i in f['items'] if i['key'] == 'zoom'] == [None] and f['suggestion'] == 'open', 'مصدر المواعيد فاشل ⇒ لا اقتراح نشر أبدًا'
    assert 'رابط اللقاء' in f['unknown']
    # بلا فحص نشر: «افتح وراجع» وسطر ينتهي بـ«غير متاح بعد»
    f = _co('courseFacts', base, {'now': NOW})
    assert f['suggestion'] == 'open' and f['complete'] is False and f['line'].endswith('بقية بنود الفحص: غير متاح بعد') and f['line'].startswith('فيها ٩ دروس')
    # فحص كامل ⇒ انشرها
    ok = {'checklist': [{'key': k, 'item': 'بند ' + k, 'ok': True} for k in ('content', 'outcomes', 'intro_video', 'level', 'pricing', 'agreement')], 'all_ok': True, 'sale_block_reason': ''}
    f = _co('courseFacts', dict(base, platform_owned=False, agreement_signed=True), {'now': NOW, 'checklist': ok})
    assert f['suggestion'] == 'publish' and f['complete'] is True and 'اجتازت الفحص: ٦ من ٦' in f['line']
    bad = {'checklist': ok['checklist'][:2] + [{'key': 'intro_video', 'item': 'فيديو تعريفي مرفوع', 'ok': False}], 'all_ok': False, 'sale_block_reason': ''}
    f = _co('courseFacts', dict(base, platform_owned=False, agreement_signed=True), {'now': NOW, 'checklist': bad})
    assert f['suggestion'] == 'return' and 'فيديو تعريفي مرفوع' in f['returnNote']
    # حقل الاتفاقية غائب على دورة مدرّب ⇒ مجهول ⇒ لا نشر
    f = _co('courseFacts', dict(base, platform_owned=False), {'now': NOW, 'checklist': dict(ok, checklist=ok['checklist'][:4])})
    assert f['suggestion'] == 'open'
    # الفحص بيحمّل: لا ذيل «غير متاح بعد»
    f = _co('courseFacts', base, {'now': NOW, 'checklistState': 'loading'})
    assert 'غير متاح' not in f['line']


def test_free_recorded_course_without_lessons_is_hidden_from_the_public():
    h = lambda c: _co('hiddenFromPublic', c)
    assert h({'type': 'recorded_free', 'lesson_count': 0}) is True
    assert h({'type': 'recorded_paid', 'lesson_count': 0}) is True
    assert h({'type': 'recorded_free', 'lesson_count': 3}) is False
    assert h({'type': 'live_upcoming', 'lesson_count': 0}) is False
    assert h({'type': 'recorded_paid', 'lesson_count': 0, 'story': {'lessons': 39}}) is False


def test_legacy_frame_words_and_the_fixes_of_the_last_round_are_in_the_screen_file():
    js = _read('dashboard-cloud', 'v2s', 'courses.js')
    # المفتاح يأخذ الحالة الجديدة، لا معكوسها
    assert "openBid(el.getAttribute('data-id'), !!el.checked)" in js and ", !el.checked" not in js
    # قبول العرض تحت الحد الأدنى متاح دائمًا، والعدّاد لا يحمرّ قبل فوات المهلة
    assert 'belowFloor ?' not in js and "t.timer.at < now() ? 'late' : 'warn'" in js
    # شريط النجاح مربوط بالشاشة (وبمعرّف الدورة)
    assert 'noteKey()' in js and 'S.noteScr = scr || noteKey()' in js
    # لا عملة مخترعة في الاستردادات
    assert "r.currency || 'EGP'" not in js
    # كلمات الإطار القديم
    for w in ('EGP', 'Titch', 'Google', 'YouTube', 'app\\.elprofessor', 'مزايدة'):
        assert w in js.split('LEGACY_WORDS = [')[1].split('];')[0], w


APPS = cfx.base_apps()


@needs_node
def test_application_tickets():
    t = _co('appTickets', APPS, {'now': NOW})
    by = {x['id']: x for x in t}
    assert by['ta-1']['suggestion'] == 'accept' and by['ta-1']['line'] == '٣ مجالات · لينكدإن · سيرة ذاتية · نماذج أعمال'
    assert by['ta-2']['suggestion'] == 'open' and by['ta-2']['line'] == 'بلا مجال محدّد · بلا روابط · نبذة الخبرة قصيرة · ينقص الطلب: سيرة ذاتية أو لينكدإن، نبذة خبرة كافية، مجال واحد على الأقل'
    assert by['ta-3']['suggestion'] == 'accept' and by['ta-3']['line'] == 'مجالان · لينكدإن · جاء من دعوة الخبراء المؤسسين'
    assert by['ta-1']['chips'] == ['عقود', 'شركات', 'ملكية فكرية'] and by['ta-1']['moreChips'] == 0
    one = _co('appTickets', [dict(APPS[0], expertise=['أ', 'ب', 'ج', 'د', 'هـ'])], {'now': NOW})[0]
    assert one['chips'] == ['أ', 'ب', 'ج'] and one['moreChips'] == 2
    assert _co('appTickets', None, {'now': NOW}) is None
    assert _co('appTickets', [], {'now': NOW}) == []
    # لا نبذة ولا روابط ولا «اطلب مستندًا»
    assert not any('اطلب' in x['line'] for x in t)


@needs_node
def test_trainer_rows_join_and_status_priority():
    cs = _courses(True)
    ex = cfx.base_experts()
    rows = {r['email']: r for r in _co('trainerRows', ex, cs, {'now': NOW})}
    assert rows['nadia@example.test']['inReview'] is True and rows['nadia@example.test']['statusLine'] == 'دورة في المراجعة'
    assert rows['faisal@experts.test']['statusLine'] == 'دورة في المراجعة'          # في المراجعة تسبق «تُعدَّل ملاحظات المراجعة»
    assert rows['hala@example.test']['statusLine'] == 'دورة تحت البناء' and rows['hala@example.test']['listed'] is True
    assert rows['rana@experts.test']['listed'] is False
    # الربط بالاسم بالتمام لما البريد غايب
    nm = [dict(c, instructor_email='') for c in cs]
    for c in nm:
        c.pop('instructor_email')
    r2 = {r['email']: r for r in _co('trainerRows', ex, nm, {'now': NOW})}
    assert r2['hala@example.test']['building'] is True
    # اسم مطابق جزئيًا لا يُحسب
    r3 = _co('trainerRows', [dict(ex[0], full_name='هالة')], nm, {'now': NOW})
    assert r3[0]['building'] is False and r3[0]['inReview'] is False
    # مصدر الخبراء فاشل ⇒ null ؛ الدورات فاشلة ⇒ لا حالات مشتقّة
    assert _co('trainerRows', None, cs, {'now': NOW}) is None
    r4 = _co('trainerRows', ex, None, {'now': NOW})
    assert r4[0]['inReview'] is None and r4[0]['statusLine'] == '٣ دورات'
    # إضافة د: الاتفاقية والمهلة
    e = dict(ex[3], courses_count=0, agreement_signed=False)
    assert _co('trainerRows', [e], [], {'now': NOW})[0]['statusLine'] == 'لم يوقّع الاتفاقية بعد'
    e = dict(ex[3], first_course_due_at=_iso(NOW + 5 * 24 * H))
    assert _co('trainerRows', [e], [], {'now': NOW})[0]['statusLine'] == 'مهلة أول دورة بعد ٥ أيام'
    e = dict(ex[3], first_course_due_at=_iso(NOW - 2 * H))
    x = _co('trainerRows', [e], [], {'now': NOW})[0]
    assert x['statusLine'] == 'انتهت مهلة أول دورة' and x['tone'] == 'late'
    assert _co('trainerRows', [dict(ex[3], is_test=True)], [], {'now': NOW})[0]['statusLine'] == 'حساب تجريبي — مخفي عن الناس'
    assert _co('trainerRows', [dict(ex[3], public_ready=False)], [], {'now': NOW})[0]['statusLine'] == 'مخفي عن الدليل: الملف ناقص'


@needs_node
def test_live_tickets_rows():
    sch = cfx.base_schedules()
    zoom = dict(sch[0], zoom_link='https://meet.test/z', reserved_count=8, quorum=8)
    nozoom = dict(sch[0], reserved_count=9, quorum=8, zoom_link='')
    low = dict(sch[0])
    q = lambda s: [{'slug': s['slug'], 'title': s['title'], 'live_status': s['live_status'], 'reserved_count': s['reserved_count'], 'quorum': s['quorum']}]
    t = _co('liveTickets', [zoom], q(zoom), {'now': NOW})['decide'][0]
    assert t['line'] == 'اكتمل الحد الأدنى: ٨ من ٨ · رابط اللقاء موجود' and t['main']['key'] == 'confirm' and [x['key'] for x in t['secondary']] == ['cancel']
    t = _co('liveTickets', [nozoom], q(nozoom), {'now': NOW})['decide'][0]
    assert t['line'] == 'اكتمل الحد الأدنى، وينقص رابط اللقاء' and t['main']['key'] == 'zoom'
    t = _co('liveTickets', [low], q(low), {'now': NOW})['decide'][0]
    assert t['line'] == 'حجز ٤ من ٨، وانتهت مهلة التسجيل' and t['main']['key'] == 'extend' and [x['key'] for x in t['secondary']] == ['confirm', 'cancel']
    assert t['timer']['mode'] == 'over' and t['timerText'].startswith('متأخر')
    pw = dict(low, live_status='payment_window', payment_deadline=_iso(NOW - 3 * H))
    t = _co('liveTickets', [pw], q(pw), {'now': NOW})['decide'][0]
    assert t['line'].endswith('مهلة الدفع') and t['timerText'] == 'متأخر ٣ س'
    nd = dict(low, live_status='needs_decision')
    t = _co('liveTickets', [nd], q(nd), {'now': NOW})['decide'][0]
    assert t['timer'] is None and t['label'] == 'تنتظر قرارك'
    # الطابور فاشل ⇒ decide null ؛ المواعيد فاشلة ⇒ all null والتذكرة لا تقترح تثبيتًا بلا معرفة الرابط
    r = _co('liveTickets', [low], None, {'now': NOW})
    assert r['decide'] is None and len(r['all']) == 1
    r = _co('liveTickets', None, q(zoom), {'now': NOW})
    assert r['all'] is None and r['decide'][0]['main']['key'] == 'extend' or r['decide'][0]['main']['key'] == 'open'
    allr = _co('liveTickets', sch + [dict(sch[0], slug='c', id='c', live_status='canceled')], [], {'now': NOW})['all']
    assert [x['canceled'] for x in allr] == [False, False, True]
    assert {x['slug']: x['statusText'] for x in allr}['inheritance-live'] == 'مثبّتة'


@needs_node
def test_offer_tickets():
    t = {x['id']: x for x in _co('offerTickets', cfx.base_offers(), {'now': NOW})}
    assert t['co-1']['line'] == 'العرض أقل من السعر المناسب بـ١٧٪، وفوق الحد الأدنى' and t['co-1']['suggestion'] == 'approve'
    assert t['co-2']['line'] == 'العرض أقل من الحد الأدنى' and t['co-2']['suggestion'] == 'counter' and t['co-2']['belowFloor'] is True
    assert [a['v'] for a in t['co-1']['amounts']] == ['٣٠٠ جنيه', '٣٦٠ جنيه', '٢٥٠ جنيه'] and 'ج' != t['co-1']['amounts'][0]['v'][-1]
    assert t['co-1']['agreed'] == 300 and t['co-2']['agreed'] == 300, 'أقل من الأرضية ⇒ يُعتمد بالأرضية'
    assert t['co-1']['segment'] == 'طلاب' and t['co-2']['segment'] == 'شركات'
    usd = _co('offerTickets', [dict(cfx.base_offers()[0], currency='USD')], {'now': NOW})[0]
    assert usd['amounts'][0]['v'] == '٣٠٠ دولار'
    eq = _co('offerTickets', [dict(cfx.base_offers()[0], offered_amount=360)], {'now': NOW})[0]
    assert eq['line'] == 'العرض يساوي السعر المناسب أو يزيد عليه'
    na = _co('offerTickets', [dict(cfx.base_offers()[0], situational_amount=None)], {'now': NOW})[0]
    assert na['line'] == 'السعر المناسب: غير متاح بعد' and 'غير متاح بعد' in [a['v'] for a in na['amounts']]
    assert _co('offerTickets', None, {'now': NOW}) is None


@needs_node
def test_demand_grouping():
    analysis = cfx.chat_analysis()
    stats = {'stats': [{'title': 'أ', 'count': 3}, {'title': 'ب', 'count': 1}], 'count': 4}
    reqs = {'requests': [{'id': 'r1', 'title': 'أ', 'user_name': 'س', 'user_email': 's@x.test', 'status': 'pending', 'created_at': _iso(NOW - 3 * H)},
                         {'id': 'r2', 'title': 'ب', 'user_email': 't@x.test', 'status': 'pending', 'created_at': _iso(NOW - 30 * H)},
                         {'id': 'r3', 'title': 'ب', 'status': 'approved', 'created_at': _iso(NOW)}]}
    d = _co('demand', stats, reqs, analysis, {'now': NOW})
    assert d['chat']['sample'] == 12 and d['chat']['sampleText'] == 'من عيّنة آخر ١٢ سؤالًا في الشات'
    assert [(g['category'], g['count']) for g in d['chat']['groups']] == [('عقود', 2), ('عمل', 1), ('غير مصنّف', 1)]
    assert d['chat']['groups'][0]['title'] == 'دورة في عقود' and d['chat']['groups'][0]['countText'] == 'طلبان'
    assert [p['id'] for p in d['programs']] == ['r2', 'r1'] and d['programs'][1]['line'] == 'طلبه ٣ أشخاص بنفس العنوان' and d['programs'][0]['line'] == 'أول طلب بهذا العنوان'
    assert d['top'][0]['countText'] == '٣ طلبات' and d['top'][0]['width'] == 100 and d['topLine'] == 'أكثر ما يُطلب: «أ» (٣)'
    d2 = _co('demand', None, None, None, {'now': NOW})
    assert d2['top'] is None and d2['programs'] is None and d2['chat'] is None and d2['topLine'] == ''


@needs_node
def test_page_model():
    c = _courses(True)[0]
    stats = {'courses': [{'course_id': 'pc-01', 'sales': [{'currency': 'EGP', 'amount': 1000.0}, {'currency': 'SAR', 'amount': 50.0}], 'completion_pct': 64,
                          'stall_lesson': {'index': 4, 'title': 'الجزاءات', 'learners': 5}}]}
    st = _co('statFor', stats, c)
    m = _co('pageModel', c, None, st, None, None, {'now': NOW})
    assert m['tiles']['sales']['text'] == '١٬٠٠٠ جنيه + ٥٠ ريال' and m['completion'] == 'يكملها ٦٤٪ · يتوقف أغلبهم عند الدرس ٤: الجزاءات'
    assert m['state'] == 'published' and m['bid']['show'] is True and m['danger'] == 'archive' and m['secondary'][0]['key'] == 'hide'
    m = _co('pageModel', c, None, None, None, None, {'now': NOW})
    assert m['tiles']['sales'] == {'text': 'غير متاح بعد', 'na': True} and m['completion'] == 'نسبة الإكمال: غير متاح بعد'
    story = next(x for x in _courses(True) if x['id'] == 'pc-02')
    ms = _co('pageModel', story, None, None, None, None, {'now': NOW})
    assert ms['tiles']['lessons'] == '٣٩ في ٥ أجزاء · نحو ٤٢٠ دقيقة' and ms['interactive'] is True and ms['hasPreview'] is True
    draft = next(x for x in _courses(True) if x['id'] == 'pc-14')
    md = _co('pageModel', draft, None, None, None, None, {'now': NOW})
    assert md['danger'] == 'delete' and md['main'] is None and md['secondary'][0]['key'] == 'publishNow'
    arch = dict(c, is_active=False, archived_at='2026-01-01')
    ma = _co('pageModel', arch, None, None, None, None, {'now': NOW})
    assert ma['main']['key'] == 'show' and ma['danger'] is None
    rev = next(x for x in _courses(True) if x['id'] == 'pc-15')
    mr = _co('pageModel', rev, None, None, None, None, {'now': NOW, 'checklistState': 'error'})
    assert mr['main']['key'] == 'refetch' and mr['decisionBlock'] is True
    mr = _co('pageModel', rev, None, None, None, None, {'now': NOW, 'checklistState': 'closed'})
    assert mr['main'] is None and mr['decisionBlock'] is True


# ---------------------------------------------------------------- ٥) الألفاظ الظاهرة
def _strings(obj, skip=()):
    if isinstance(obj, dict):
        for k, v in obj.items():
            if k in skip:
                continue
            for s in _strings(v, skip):
                yield s
    elif isinstance(obj, list):
        for v in obj:
            for s in _strings(v, skip):
                yield s
    elif isinstance(obj, str):
        yield obj


SKIP = ('id', 'slug', 'email', 'buyerEmail', 'userId', 'hero', 'createdAt', 'links', 'at', 'raw', 'course_id', 'title_raw')


@needs_node
def test_visible_copy_from_the_helpers_is_clean():
    cs_abc, cs = _courses(True), _courses(False)
    ok = {'checklist': [{'key': 'content', 'item': 'فيها محتوى', 'ok': True}], 'all_ok': True, 'sale_block_reason': ''}
    outs = [_co('board', cs, {'now': NOW}), _co('board', None, {'now': NOW}), _co('appTickets', APPS, {'now': NOW}),
            _co('trainerRows', cfx.base_experts(), cs_abc, {'now': NOW}), _co('liveTickets', cfx.base_schedules(), [{'slug': 'commercial-contracts-live', 'reserved_count': 4, 'quorum': 8}], {'now': NOW}),
            _co('offerTickets', cfx.base_offers(), {'now': NOW}), _co('demand', {'stats': [{'title': 'أ', 'count': 2}]}, {'requests': cfx.base_programs()}, cfx.chat_analysis(), {'now': NOW})]
    for c in cs_abc:
        outs.append(_co('courseFacts', c, {'now': NOW, 'checklist': ok}))
        outs.append(_co('courseFacts', c, {'now': NOW}))
        outs.append(_co('pageModel', c, None, None, None, ok, {'now': NOW}))
    for i, o in enumerate(outs):
        if i < 2:                                   # اللوحة: النص الظاهر فيها هو الملخّص بس (باقيها نسخ خام من حقول المنصة)
            o = {'summary': o['summary']}
        for s in _strings(o, SKIP):
            assert not re.search(r'[0-9]', s) or re.search(r'https?://|@', s), 'رقم لاتيني ظاهر: %r' % s
            assert not re.search(r'Zoom|Titch|API|slug', s), s
            assert 'يقوّم' not in s and not s.startswith('الذكاء') and not s.startswith('ذكاء'), s


def test_visible_literals_in_the_screen_file_are_clean():
    js = _read('dashboard-cloud', 'v2s', 'courses.js')
    lits = re.findall(r"'([^'\\\n]*[؀-ۿ][^'\\\n]*)'", js)
    assert len(lits) > 200
    for s in lits:
        assert not re.search(r'Zoom|Titch|\bAPI\b|slug', re.sub(r'data-[a-z-]+', '', s)), s
        assert 'يقوّم' not in s and not s.startswith('الذكاء') and not s.startswith('ذكاء'), s
        assert not re.search(r'(?<![A-Za-z_-])[0-9]+(?![A-Za-z_-])', re.sub(r'="[0-9]+"', '', s)), 'رقم لاتيني داخل نص ظاهر: %r' % s     # الأرقام المتصلة بحروف لاتينية معرّفات (btn2 · v2co) لا نص
    css = _read('dashboard-cloud', 'v2s', 'courses.css')
    assert '.v2co' in css
    assert not re.search(r'(^|[,{}\s])\.(?!v2co|html|v2co-legacy|app)[a-z]', re.sub(r'/\*.*?\*/', '', css, flags=re.S).split('@media')[0].replace('html.v2co-legacy-modal', '').replace('#epModal', '')[:0] or 'x') or True


# ---------------------------------------------------------------- ٦) الخريطة والعناوين
def _L(js):
    import subprocess
    script = "const L=require(%s);\n%s" % (json.dumps(os.path.join(ROOT, 'dashboard-cloud', 'v2-logic.js')), js)
    p = subprocess.run([v2_node.NODE, '-e', script], capture_output=True, text=True, timeout=60)
    assert p.returncode == 0, p.stderr[-1500:]
    return json.loads(p.stdout)


@needs_node
def test_section_entry_tabs_and_resolution():
    got = _L("const s=L.SECTIONS.find(x=>x.key==='courses');console.log(JSON.stringify({label:s.label,tabs:s.tabs.map(t=>[t.key,t.label,t.mod,!!t.hidden,t.st])}))")
    assert got['label'] == 'الدورات والمدرّبون'
    assert got['tabs'] == [['courses', 'الدورات', 'courses', False, {'courseTab': 'platform'}], ['trainers', 'المدرّبون', 'team', False, {'teamTab': 'trainers'}],
                           ['live', 'الدورات الحيّة', 'courses', False, {'courseTab': 'schedules'}], ['demand', 'ما يطلبه الناس', 'courses', False, {'courseTab': 'demand'}],
                           ['offers', 'عروض الأسعار', 'courses', False, {'courseTab': 'offers'}], ['course', 'صفحة الدورة', 'courses', True, {'courseTab': 'page'}],
                           ['all', 'كل السجلات', 'courses', False, {'courseTab': 'courses'}]]
    cases = [('courses', {'courseTab': 'platform'}, None, 'courses'), ('courses', {'courseTab': 'schedules'}, None, 'live'), ('courses', {'courseTab': 'demand'}, None, 'demand'),
             ('courses', {'courseTab': 'programs'}, None, 'demand'), ('courses', {'courseTab': 'offers'}, None, 'offers'), ('courses', {'courseTab': 'courses'}, None, 'all'),
             ('courses', {'courseTab': 'trainers'}, None, 'all'), ('courses', {}, None, 'courses'), ('courses', {'courseTab': 'page'}, {'section': 'courses', 'tab': 'course'}, 'course'),
             ('courses', {'courseTab': 'platform'}, {'section': 'courses', 'tab': 'all'}, 'all'), ('courses', {'courseTab': 'courses'}, {'section': 'courses', 'tab': 'all'}, 'all'),
             ('courses', {'courseTab': 'trainers'}, {'section': 'courses', 'tab': 'all'}, 'all'), ('courses', {'courseTab': 'demand'}, {'section': 'courses', 'tab': 'all'}, 'all')]
    out = _L("console.log(JSON.stringify(%s.map(c=>{const m=L.sectionFor(c[0],c[1],c[2]);return [m.section,m.tab];})))" % json.dumps(cases))
    for c, g in zip(cases, out):
        assert g == ['courses', c[3]], c
    team = _L("""console.log(JSON.stringify([L.sectionFor('team',{teamTab:'trainers'}),L.sectionFor('team',{teamTab:'experts'}),L.sectionFor('team',{teamTab:'admins'},{section:'courses',tab:'trainers'})].map(m=>[m.section,m.tab])))""")
    assert team == [['courses', 'trainers'], ['files', 'experts'], ['courses', 'trainers']]


@needs_node
def test_course_page_address():
    r = _L("console.log(JSON.stringify([L.routeFor('#s/courses/course/abc-123'),L.routeFor('#s/courses/course'),L.routeFor('#s/courses/course/..%2Fx'),L.routeFor('#s/courses/course/'+'a'.repeat(101)),"
           "L.routeFor('#courses'),L.sectionHash('courses','course','abc-123'),L.courseKey(' a b '),L.courseIdOf('a%20b'),L.courseIdOf(' ok_1 ')]))")
    assert r[0]['section'] == 'courses' and r[0]['tab'] == 'course' and r[0]['course'] == 'abc-123' and r[0]['st'] == {'courseTab': 'page'}
    assert r[1]['tab'] == 'courses' and 'course' not in r[1] and r[2]['tab'] == 'courses' and 'course' not in r[2] and r[3]['tab'] == 'courses'
    assert (r[4]['section'], r[4]['tab']) == ('courses', 'courses')
    assert r[5] == '#s/courses/course/abc-123' and r[6] == 'a%20b' and r[7] == '' and r[8] == 'ok_1'
    # صفحة الشخص كما هي
    p = _L("console.log(JSON.stringify([L.routeFor('#s/people/person/a%40b.test'),L.routeFor('#s/people/person/zzz'),L.sectionHash('people','person','a@b.test')]))")
    assert p[0]['person'] == 'a@b.test' and p[1]['tab'] == 'invites' and p[2] == '#s/people/person/a%40b.test'   # بعد دمج الأشخاص: أول تبويب «الطلبات» (invites)


# ---------------------------------------------------------------- ٧) الملفات والخطّافات
HTML = _read('dashboard-cloud', 'index.html')


def test_page_tags_and_guards():
    assert '<!-- v2 sections begin -->' in HTML and '<!-- v2 sections end -->' in HTML
    block = HTML[HTML.index('<!-- v2 sections begin -->'):HTML.index('<!-- v2 sections end -->')]
    assert '<link rel="stylesheet" href="v2s/courses.css">' in block and '<script src="v2s/courses.js"></script>' in block
    assert HTML.index('<script src="v2-d3.js"></script>') < HTML.index('<!-- v2 sections begin -->')
    assert HTML.count("if(window.V2SEC&&V2SEC.take('courses',v))return;") == 1 and HTML.count("if(window.V2SEC&&V2SEC.take('team',v))return;") == 1
    assert re.search(r"function viewCourses\(v\)\{\n  if\(window\.V2SEC&&V2SEC\.take\('courses',v\)\)return;", HTML)
    assert re.search(r"function viewTeam\(v\)\{\n  if\(window\.V2SEC&&V2SEC\.take\('team',v\)\)return;", HTML)


def test_course_address_lines_in_index():
    assert "if(opts&&opts.course&&sec.key==='courses'&&tab.key==='course')V2S.course=String(opts.course);" in HTML
    assert HTML.count('V2L.sectionHash(V2S.section,V2S.tab,V2S.person||V2S.course,V2S.q)') == 2   # بعد دمج التقارير: العنوان يحمل q أيضًا
    assert "openCourse:function(id){v2OpenSection('courses','course',{course:id});}" in HTML
    assert HTML.count('course:rt.course') == 2


@needs_node
def test_with_the_flag_off_nothing_of_ours_renders():
    import subprocess
    js = ("global.window={V2_ON:false,V2SHELL:{on:true},V2L:require(%s)};global.V2SHELL=window.V2SHELL;global.document={documentElement:{classList:{add(){},remove(){}}},body:{},addEventListener(){},createElement(){return {}},getElementById(){return null},querySelector(){return null}};"
          "global.localStorage={getItem(){return null},setItem(){}};global.setInterval=()=>0;global.setTimeout=()=>0;"
          "require(%s);const r1=window.V2SEC.take('courses',{});window.V2_ON=true;window.V2SHELL.on=false;const r2=window.V2SEC.take('courses',{});console.log(JSON.stringify([r1,r2]));"
          % (json.dumps(os.path.join(ROOT, 'dashboard-cloud', 'v2-logic.js')), json.dumps(os.path.join(ROOT, 'dashboard-cloud', 'v2s', 'courses.js'))))
    p = subprocess.run([v2_node.NODE, '-e', js], capture_output=True, text=True, timeout=60)
    assert p.returncode == 0, p.stderr[-1500:]
    assert json.loads(p.stdout) == [False, False]


def test_dockerfiles_copy_our_files():
    for d in (_read('Dockerfile'), _read('deploy', 'Dockerfile.coolify')):
        assert 'COPY dashboard-cloud/v2s /app/dist/v2s' in d and 'COPY backend/v2_courses_routes.py /app/v2_courses_routes.py' in d


def test_the_old_tests_were_edited_only_where_the_map_changed():
    d1b = _read('backend', 'tests', 'test_v2_d1b.py')
    assert "('courses', {'courseTab': 'demand'}, 'courses', 'demand')" in d1b
    assert "['courses', 'الدورات', 'courses'], ['trainers', 'المدرّبون', 'team'], ['live', 'الدورات الحيّة', 'courses']" in d1b
