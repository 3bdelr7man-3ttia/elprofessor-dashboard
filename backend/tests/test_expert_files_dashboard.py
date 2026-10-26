# -*- coding: utf-8 -*-
"""«ملف للخبير» في الداشبورد — المسارات التمانية فوق جسر المنصة (الجولة ٦).

Run:  cd backend && python3 -m pytest -q tests/test_expert_files_dashboard.py

⛔ المنصة متزيّفة بالكامل: `requests.request` بيرد من جدول في الذاكرة (أشكال الجسر بالحرف من
`ef_fixtures.py`)، وأي عنوان برّه `https://platform.test` بيتسجّل كطلب ممنوع ويوقع الاختبار.

اللي بيثبّته (docs/EXPERT-FILES-DASHBOARD-SPEC.md §١٠-أ):
  ١. الصلاحية: أدمن بس — الموظف وغيره ٤٠٣ **من غير أي نداء للمنصة**، ومن غير توكن ٤٠١.
  ٢. شكل النداء للمنصة بالحرف (المسار · المعاملات · الجسم من غير مفاتيح زيادة · السرّ في الرأس بس).
  ٣. الفعل مرة واحدة: نداء واحد للمنصة لكل ضغطة — ولا إعادة محاولة حتى لو الرد ضاع.
  ٤. أخطاء المنصة بتوصل للمؤسس بالعربي (الإنجليزي بيتترجم، والعربي بيعدّي زي ما هو).
  ٥. السجل: بعد النجاح بس، بإيميل اللي عمل الفعل، وبأرقام المنصة مش المتصفح.
"""
import copy
import datetime
import json
import os
import sys

import jwt
import pytest
import requests as _requests
from werkzeug.security import generate_password_hash

from app import app as flask_app, db, User, AuditLog  # noqa: E402

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), 'uiharness'))
import ef_fixtures as fx  # noqa: E402

PLATFORM = 'https://platform.test'
SECRET = 'test-metrics-secret'
NON_ADMIN_ROLES = ['employee', 'trainer', 'investor', 'viewer', 'pending']
FID = fx.F1['id']
CID = fx.D2['id']

ROUTES = [
    ('GET', '/api/platform-expert-files', None),
    ('GET', '/api/platform-expert-files/' + FID, None),
    ('POST', '/api/platform-expert-files/%s/assign' % FID, {'expert_email': 'hala@experts.test'}),
    ('POST', '/api/platform-expert-files/%s/reassign' % FID, {'expert_email': 'hala@experts.test'}),
    ('POST', '/api/platform-expert-files/%s/refund' % FID, {'confirmed': True}),
    ('POST', '/api/platform-expert-files/%s/resolve' % FID, {'action': 'release', 'confirmed': True}),
    ('GET', '/api/platform-consultation-disputes', None),
    ('POST', '/api/platform-consultation-disputes/%s/resolve' % CID, {'action': 'refund', 'confirmed': True}),
]


class _Resp(object):
    def __init__(self, status, payload):
        self.status_code = status
        self._p = payload
        self.content = json.dumps(payload).encode() if payload is not None else b''

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
    tok = jwt.encode({'user_id': user.id,
                      'exp': datetime.datetime.utcnow() + datetime.timedelta(days=1)},
                     flask_app.config['SECRET_KEY'], algorithm='HS256')
    return {'Authorization': 'Bearer ' + tok}


@pytest.fixture(scope='module')
def ctx():
    with flask_app.app_context():
        db.create_all()
        heads = {r: _bearer(_mkuser('ef-%s@x.test' % r, r)) for r in NON_ADMIN_ROLES}
        heads['admin'] = _bearer(_mkuser('ef-admin@x.test', 'admin'))
        yield {'heads': heads, 'client': flask_app.test_client()}


class Platform(object):
    """المنصة المزيّفة: `EFPlatform` من الأداة + سجل لكل نداء بالحرف + ردود مفروضة لاختبار الأخطاء."""

    def __init__(self):
        self.ef = fx.EFPlatform()
        self.seen = []
        self.blocked = []
        self.forced = {}      # (method, path) -> (status, payload) | Exception

    def __call__(self, method, url, params=None, json=None, headers=None, timeout=None):
        self.seen.append({'method': method, 'url': url, 'params': params, 'json': copy.deepcopy(json),
                          'headers': dict(headers or {}), 'timeout': timeout})
        if not url.startswith(PLATFORM + '/'):
            self.blocked.append(url)
            raise RuntimeError('طلب حقيقي ممنوع: ' + url)
        path = url[len(PLATFORM):]
        forced = self.forced.get((method, path))
        if isinstance(forced, Exception):
            raise forced
        if forced is not None:
            return _Resp(*forced)
        out = self.ef.handle(method, path, params, json)
        if out is None:
            return _Resp(404, {'detail': 'Not Found'})
        return _Resp(*out)


@pytest.fixture
def plat(monkeypatch):
    import app as appmod
    p = Platform()
    monkeypatch.setattr(appmod, 'PLATFORM_METRICS_SECRET', SECRET)
    monkeypatch.setattr(appmod, 'PLATFORM_API_URL', PLATFORM)
    monkeypatch.setattr(appmod.requests, 'request', p)
    yield p
    assert p.blocked == [], 'طلب لسيرفر حقيقي: %r' % p.blocked


def _call(ctx, method, path, body=None, role='admin'):
    c = ctx['client']
    h = ctx['heads'][role] if role else {}
    if method == 'GET':
        return c.get(path, headers=h)
    return c.post(path, headers=h, json=body if body is not None else {})


def _audits(action, target=None):
    with flask_app.app_context():
        q = AuditLog.query.filter(AuditLog.action == action)
        if target is not None:
            q = q.filter(AuditLog.target == target)
        return [(r.actor_email, r.target, json.loads(r.meta_json) if r.meta_json else None)
                for r in q.order_by(AuditLog.id).all()]


def _clear_audits():
    with flask_app.app_context():
        AuditLog.query.filter(AuditLog.action.like('expert_file.%')).delete(synchronize_session=False)
        AuditLog.query.filter(AuditLog.action.like('consultation.%')).delete(synchronize_session=False)
        db.session.commit()


@pytest.fixture(autouse=True)
def _fresh_audits():
    _clear_audits()
    yield


# ---------------------------------------------------------------- ١) القراءات

def test_list_forwards_status_and_defaults_to_waiting(ctx, plat):
    _call(ctx, 'GET', '/api/platform-expert-files?status=late')
    assert plat.seen[-1]['url'] == PLATFORM + '/api/bridge/expert-files'
    assert plat.seen[-1]['params'] == {'status': 'late'}
    for q in ('', '?status=', '?status=all', '?status=xyz', '?status=followup'):
        _call(ctx, 'GET', '/api/platform-expert-files' + q)
        assert plat.seen[-1]['params'] == {'status': 'waiting'}, q
    _call(ctx, 'GET', '/api/platform-expert-files?status=DISPUTED')
    assert plat.seen[-1]['params'] == {'status': 'disputed'}


def test_list_payload_is_verbatim_plus_enabled(ctx, plat):
    r = _call(ctx, 'GET', '/api/platform-expert-files?status=waiting')
    assert r.status_code == 200
    body = r.get_json()
    expected = fx.list_payload('waiting', [fx.F2, fx.F4, fx.F3, fx.F1])
    assert body.pop('enabled') is True
    assert body == expected                       # ولا مفتاح بيتشال ولا بيتحسب


@pytest.mark.parametrize('path,key', [('/api/platform-expert-files?status=late', 'files'),
                                      ('/api/platform-consultation-disputes', 'consultations')])
def test_feature_off_404_is_enabled_false_not_a_failure(ctx, plat, path, key):
    plat.ef.enabled = False
    plat.ef.cons_enabled = False
    r = _call(ctx, 'GET', path)
    assert r.status_code == 200
    body = r.get_json()
    assert body['enabled'] is False and body[key] == [] and body['count'] == 0


def test_real_platform_error_passes_through(ctx, plat):
    plat.forced[('GET', '/api/bridge/expert-files')] = (500, {'detail': 'boom'})
    r = _call(ctx, 'GET', '/api/platform-expert-files')
    assert r.status_code == 500
    assert 'enabled' not in r.get_json()
    plat.forced[('GET', '/api/bridge/consultations')] = (503, {'detail': 'Database not available'})
    r = _call(ctx, 'GET', '/api/platform-consultation-disputes')
    assert r.status_code == 503
    assert r.get_json() == {'error': 'المنصة مش متاحة دلوقتي — جرّب بعد شوية'}


def test_consultation_disputes_list_asks_for_disputed_only(ctx, plat):
    r = _call(ctx, 'GET', '/api/platform-consultation-disputes?status=all')
    assert plat.seen[-1]['url'] == PLATFORM + '/api/bridge/consultations'
    assert plat.seen[-1]['params'] == {'status': 'disputed'}
    body = r.get_json()
    assert body['enabled'] is True
    assert [c['id'] for c in body['consultations']] == [fx.D1_CONS['id'], fx.D2['id'], fx.D3['id']]


def test_detail_not_found_feature_off_message(ctx, plat):
    plat.ef.enabled = False
    r = _call(ctx, 'GET', '/api/platform-expert-files/' + FID)
    assert r.status_code == 404
    assert r.get_json() == {'error': 'خدمة «ملف للخبير» مقفولة على المنصة دلوقتي'}
    plat.ef.enabled = True
    r = _call(ctx, 'GET', '/api/platform-expert-files/no-such-file')
    assert r.status_code == 404
    assert r.get_json() == {'error': 'الملف ده مش موجود'}


def test_detail_carries_both_opinions_for_a_dispute(ctx, plat):
    r = _call(ctx, 'GET', '/api/platform-expert-files/' + fx.D1['id'])
    body = r.get_json()
    assert r.status_code == 200
    assert body['opinion']['answers'][0]['question'] == fx.D1_OPINION['answers'][0]['question']
    assert body['revision']['submitted_at'] == fx.D1_REVISION['submitted_at']


# ---------------------------------------------------------------- ٢) الصلاحية

@pytest.mark.parametrize('role', NON_ADMIN_ROLES)
@pytest.mark.parametrize('method,path,body', ROUTES)
def test_every_route_is_admin_only(ctx, plat, role, method, path, body):
    r = _call(ctx, method, path, body, role=role)
    assert r.status_code == 403, (role, path, r.status_code)
    assert plat.seen == []                       # ولا نداء للمنصة
    assert _audits('expert_file.assign') == [] and _audits('consultation.resolve') == []


@pytest.mark.parametrize('method,path,body', ROUTES)
def test_no_token_is_401_and_never_reaches_the_platform(ctx, plat, method, path, body):
    r = _call(ctx, method, path, body, role=None)
    assert r.status_code == 401
    assert plat.seen == []


@pytest.mark.parametrize('method,path,body', ROUTES)
def test_secret_in_header_never_in_body(ctx, plat, method, path, body):
    r = _call(ctx, method, path, body)
    assert plat.seen, 'ما اتناداش الجسر'
    assert plat.seen[-1]['headers'].get('X-ELP-Metrics-Secret') == SECRET
    assert SECRET not in r.get_data(as_text=True)
    assert SECRET not in json.dumps(plat.seen[-1]['json'] or {})
    assert SECRET not in json.dumps(plat.seen[-1]['params'] or {})


# ---------------------------------------------------------------- ٣) التوزيع

def test_assign_sends_exactly_the_bridge_model_and_audits(ctx, plat):
    r = _call(ctx, 'POST', '/api/platform-expert-files/%s/assign' % FID,
              {'expert_email': '  Hala@Experts.TEST ', 'note': ' ن ', 'amount': 1, 'confirmed': True})
    assert r.status_code == 200, r.get_json()
    sent = plat.seen[-1]
    assert sent['method'] == 'POST'
    assert sent['url'] == PLATFORM + '/api/bridge/expert-files/%s/assign' % FID
    assert sent['json'] == {'expert_email': 'hala@experts.test', 'note': 'ن'}   # ولا مفتاح زيادة
    assert len(plat.seen) == 1                                                     # الفعل مرة واحدة
    rows = _audits('expert_file.assign', FID)
    assert len(rows) == 1
    actor, target, meta = rows[0]
    assert actor == 'ef-admin@x.test'
    assert meta['assigned_to'] == 'hala@experts.test'
    assert meta['amount'] == 500.0 and meta['currency'] == 'EGP' and meta['note'] == 'ن'


def test_reassign_goes_to_reassign_and_records_previous_expert(ctx, plat):
    fid = fx.F5['id']
    r = _call(ctx, 'POST', '/api/platform-expert-files/%s/reassign' % fid, {'expert_email': 'faisal@experts.test'})
    assert r.status_code == 200, r.get_json()
    assert plat.seen[-1]['url'] == PLATFORM + '/api/bridge/expert-files/%s/reassign' % fid
    assert plat.seen[-1]['json'] == {'expert_email': 'faisal@experts.test', 'note': ''}
    (actor, _t, meta), = _audits('expert_file.reassign', fid)
    assert meta['previous_expert'] == 'sami@experts.test'
    assert meta['assigned_to'] == 'faisal@experts.test'
    assert meta['currency'] == 'SAR'


@pytest.mark.parametrize('bad', [None, '', 'x', 'no-at.test', 'a@b', 'a b@c.test', 5, ['a@b.test'],
                                 'a' * 195 + '@x.test'])
def test_bad_expert_email_is_refused_locally(ctx, plat, bad):
    for act in ('assign', 'reassign'):
        r = _call(ctx, 'POST', '/api/platform-expert-files/%s/%s' % (FID, act), {'expert_email': bad})
        assert r.status_code == 400
        assert r.get_json() == {'error': 'اختار خبير الأول'}
    assert plat.seen == []
    assert _audits('expert_file.assign') == [] and _audits('expert_file.reassign') == []


# ---------------------------------------------------------------- ٤) الفلوس: رجوع وحسم

@pytest.mark.parametrize('body', [{}, {'confirmed': 'true'}, {'confirmed': 1}, {'confirmed': False}])
def test_refund_without_confirmed_is_refused_locally(ctx, plat, body):
    r = _call(ctx, 'POST', '/api/platform-expert-files/%s/refund' % FID, body)
    assert r.status_code == 400
    assert r.get_json() == {'error': 'لازم تأكّد الأول من الشاشة'}
    assert plat.seen == []
    assert _audits('expert_file.refund') == []


def test_refund_forwards_note_only_and_audits_platform_amounts(ctx, plat):
    fid = fx.F3['id']
    r = _call(ctx, 'POST', '/api/platform-expert-files/%s/refund' % fid,
              {'confirmed': True, 'note': 'الخبير ما استلمش', 'amount': 1, 'currency': 'USD'})
    assert r.status_code == 200, r.get_json()
    assert plat.seen[-1]['json'] == {'note': 'الخبير ما استلمش'}     # ⛔ ولا confirmed ولا مبلغ
    assert len(plat.seen) == 1
    (actor, _t, meta), = _audits('expert_file.refund', fid)
    assert actor == 'ef-admin@x.test'
    assert meta['amount'] == 500.0 and meta['currency'] == 'EGP'     # من رد المنصة
    assert meta['status'] == 'refunded'


def test_note_is_text_only_and_clipped_to_the_bridge_limit(ctx, plat):
    _call(ctx, 'POST', '/api/platform-expert-files/%s/refund' % FID, {'confirmed': True, 'note': 'ن' * 1500})
    assert plat.seen[-1]['json'] == {'note': 'ن' * 1000}
    _call(ctx, 'POST', '/api/platform-expert-files/%s/resolve' % fx.D1['id'],
          {'action': 'refund', 'confirmed': True, 'note': {'x': 1}})
    assert plat.seen[-1]['json'] == {'action': 'refund', 'note': ''}


@pytest.mark.parametrize('action', [None, '', 'split', 'RELEASE', 'release '])
def test_resolve_validates_action(ctx, plat, action):
    for path in ('/api/platform-expert-files/%s/resolve' % fx.D1['id'],
                 '/api/platform-consultation-disputes/%s/resolve' % CID):
        r = _call(ctx, 'POST', path, {'action': action, 'confirmed': True})
        assert r.status_code == 400
        assert r.get_json() == {'error': 'اختار: للخبير ولا للعميل'}
    assert plat.seen == []


def test_resolve_without_confirmed_is_refused_locally(ctx, plat):
    for path in ('/api/platform-expert-files/%s/resolve' % fx.D1['id'],
                 '/api/platform-consultation-disputes/%s/resolve' % CID):
        r = _call(ctx, 'POST', path, {'action': 'release'})
        assert r.status_code == 400
        assert r.get_json() == {'error': 'لازم تأكّد الأول من الشاشة'}
    assert plat.seen == []


def test_resolve_forwards_action_and_note_for_a_file(ctx, plat):
    fid = fx.D1['id']
    r = _call(ctx, 'POST', '/api/platform-expert-files/%s/resolve' % fid,
              {'action': 'release', 'confirmed': True, 'note': 'الخبير عدّل والتعديل كفاية'})
    assert r.status_code == 200, r.get_json()
    assert plat.seen[-1]['url'] == PLATFORM + '/api/bridge/expert-files/%s/resolve' % fid
    assert plat.seen[-1]['json'] == {'action': 'release', 'note': 'الخبير عدّل والتعديل كفاية'}
    assert plat.seen[-1]['timeout'] >= 25
    (_a, _t, meta), = _audits('expert_file.resolve', fid)
    assert meta['action'] == 'release' and meta['expert_amount'] == 300.0 and meta['status'] == 'closed'


def test_resolve_forwards_action_and_note_for_a_consultation(ctx, plat):
    r = _call(ctx, 'POST', '/api/platform-consultation-disputes/%s/resolve' % CID,
              {'action': 'refund', 'confirmed': True, 'note': 'ملاحظة'})
    assert r.status_code == 200, r.get_json()
    assert plat.seen[-1]['url'] == PLATFORM + '/api/bridge/consultations/%s/resolve' % CID
    assert plat.seen[-1]['json'] == {'action': 'refund', 'note': 'ملاحظة'}
    (actor, _t, meta), = _audits('consultation.resolve', CID)
    assert actor == 'ef-admin@x.test'
    assert meta == {'kind': 'consultation', 'amount': 750, 'currency': 'EGP', 'expert_amount': 600,
                    'status': 'refunded', 'expert_email': 'amr@experts.test', 'action': 'refund',
                    'note': 'ملاحظة'}


def test_second_click_reaches_the_platform_once_more_and_its_guard_answers(ctx, plat):
    """الضغطة التانية (تاب تاني مثلًا) بتوصل المنصة **مرة واحدة** بس، وحارسها هو اللي بيرد —
    والداشبورد ما بيسجّلش فعل ما حصلش."""
    did = fx.D3['id']
    _call(ctx, 'POST', '/api/platform-consultation-disputes/%s/resolve' % did, {'action': 'release', 'confirmed': True})
    r = _call(ctx, 'POST', '/api/platform-consultation-disputes/%s/resolve' % did, {'action': 'release', 'confirmed': True})
    assert len(plat.seen) == 2
    assert r.status_code == 404
    assert r.get_json() == {'error': 'النزاع ده مش موجود — حدّث الصفحة'}
    assert len(_audits('consultation.resolve', did)) == 1


# ---------------------------------------------------------------- ٥) أخطاء المنصة بالعربي

@pytest.mark.parametrize('detail,arabic', [
    ('Already refunded by the payment gateway', 'الفلوس دي رجعت للعميل من بوابة الدفع قبل كده'),
    ('Already refunded manually', 'الفلوس دي رجعت للعميل يدوي قبل كده'),
    ('Only a disputed consultation can be resolved', 'النزاع ده اتحسم قبل كده — حدّث الصفحة'),
])
def test_english_resolve_errors_reach_the_founder_in_arabic(ctx, plat, detail, arabic):
    fid = fx.D1['id']
    plat.forced[('POST', '/api/bridge/expert-files/%s/resolve' % fid)] = (409, {'detail': detail})
    r = _call(ctx, 'POST', '/api/platform-expert-files/%s/resolve' % fid, {'action': 'refund', 'confirmed': True})
    assert r.status_code == 409
    assert r.get_json() == {'error': arabic}
    plat.forced[('POST', '/api/bridge/consultations/%s/resolve' % CID)] = (409, {'detail': detail})
    r = _call(ctx, 'POST', '/api/platform-consultation-disputes/%s/resolve' % CID, {'action': 'refund', 'confirmed': True})
    assert r.get_json() == {'error': arabic}


def test_manual_refund_guard_on_a_consultation_is_arabic(ctx, plat):
    r = _call(ctx, 'POST', '/api/platform-consultation-disputes/%s/resolve' % fx.D3['id'],
              {'action': 'refund', 'confirmed': True})
    assert r.status_code == 409
    assert r.get_json() == {'error': 'الفلوس دي رجعت للعميل يدوي قبل كده'}


@pytest.mark.parametrize('detail', ['فات ميعاد استلام الملف', 'الملف اتغيّر — حدّث الصفحة',
                                    'الفلوس اتحرّكت على الملف ده — حدّث الصفحة'])
def test_arabic_platform_errors_pass_verbatim(ctx, plat, detail):
    plat.forced[('POST', '/api/bridge/expert-files/%s/assign' % FID)] = (409, {'detail': detail})
    r = _call(ctx, 'POST', '/api/platform-expert-files/%s/assign' % FID, {'expert_email': 'hala@experts.test'})
    assert r.status_code == 409
    assert r.get_json() == {'error': detail}


def test_unknown_expert_and_wrong_state_come_back_from_the_platform(ctx, plat):
    r = _call(ctx, 'POST', '/api/platform-expert-files/%s/assign' % FID, {'expert_email': 'ghost@experts.test'})
    assert r.status_code == 404 and r.get_json() == {'error': 'الخبير غير موجود أو غير معتمد'}
    r = _call(ctx, 'POST', '/api/platform-expert-files/%s/reassign' % FID, {'expert_email': 'hala@experts.test'})
    assert r.status_code == 409 and r.get_json() == {'error': 'الملف ده مش عند خبير دلوقتي'}


def test_pydantic_list_detail_is_not_object_object(ctx, plat):
    plat.forced[('POST', '/api/bridge/expert-files/%s/refund' % FID)] = (
        422, {'detail': [{'loc': ['body', 'note'], 'msg': 'too long'}]})
    r = _call(ctx, 'POST', '/api/platform-expert-files/%s/refund' % FID, {'confirmed': True})
    assert r.status_code == 422
    assert r.get_json() == {'error': 'المنصة رفضت البيانات المرسلة'}


def test_feature_switched_off_mid_action_says_so(ctx, plat):
    plat.ef.enabled = False
    r = _call(ctx, 'POST', '/api/platform-expert-files/%s/refund' % FID, {'confirmed': True})
    assert r.status_code == 404
    assert r.get_json() == {'error': 'خدمة «ملف للخبير» مقفولة على المنصة دلوقتي'}
    plat.ef.cons_enabled = False
    r = _call(ctx, 'POST', '/api/platform-consultation-disputes/%s/resolve' % CID, {'action': 'refund', 'confirmed': True})
    assert r.get_json() == {'error': 'حسم النزاعات من هنا لسه مش متاح على المنصة'}


def test_secret_rejected_by_the_platform_is_plain_arabic(ctx, plat):
    plat.forced[('GET', '/api/bridge/expert-files')] = (401, {'detail': 'unauthorized'})
    r = _call(ctx, 'GET', '/api/platform-expert-files')
    assert r.status_code == 401
    assert r.get_json() == {'error': 'الداشبورد مش قادر يكلّم المنصة دلوقتي'}


@pytest.mark.parametrize('method,path,body,action', [
    ('POST', '/api/platform-expert-files/%s/assign' % FID, {'expert_email': 'hala@experts.test'}, 'assign'),
    ('POST', '/api/platform-expert-files/%s/refund' % FID, {'confirmed': True, 'note': 'x'}, 'refund'),
    ('POST', '/api/platform-expert-files/%s/resolve' % fx.D1['id'], {'action': 'refund', 'confirmed': True}, 'resolve'),
    ('POST', '/api/platform-consultation-disputes/%s/resolve' % CID, {'action': 'release', 'confirmed': True}, 'resolve'),
])
def test_a_rejected_write_is_never_audited(ctx, plat, method, path, body, action):
    plat.forced[(method, path.replace('/api/platform-expert-files', '/api/bridge/expert-files')
                 .replace('/api/platform-consultation-disputes', '/api/bridge/consultations'))] = (
        409, {'detail': 'الفلوس اتحرّكت على الملف ده — حدّث الصفحة'})
    r = _call(ctx, method, path, body)
    assert r.status_code == 409
    for a in ('expert_file.assign', 'expert_file.refund', 'expert_file.resolve', 'consultation.resolve',
              'expert_file.no_reply', 'consultation.no_reply'):
        assert _audits(a) == [], a


@pytest.mark.parametrize('exc', [_requests.Timeout('slow'), _requests.ConnectionError('reset')])
def test_no_reply_on_a_money_write_is_said_and_logged(ctx, plat, exc):
    path = '/api/bridge/expert-files/%s/refund' % FID
    plat.forced[('POST', path)] = exc
    r = _call(ctx, 'POST', '/api/platform-expert-files/%s/refund' % FID, {'confirmed': True})
    assert r.status_code == 502
    assert r.get_json() == {'error': 'ما وصلناش رد من المنصة — حدّث الصفحة وشوف حصل إيه قبل ما تضغط تاني',
                            'no_reply': True}
    assert len(plat.seen) == 1                         # ⛔ ولا إعادة محاولة على فعل فلوس
    (_a, target, meta), = _audits('expert_file.no_reply')
    assert target == FID and meta == {'attempt': 'refund'}
    assert _audits('expert_file.refund') == []


def test_no_reply_on_a_consultation_resolve_names_the_action(ctx, plat):
    plat.forced[('POST', '/api/bridge/consultations/%s/resolve' % CID)] = _requests.Timeout('slow')
    r = _call(ctx, 'POST', '/api/platform-consultation-disputes/%s/resolve' % CID,
              {'action': 'release', 'confirmed': True})
    assert r.status_code == 502 and r.get_json()['no_reply'] is True
    (_a, target, meta), = _audits('consultation.no_reply')
    assert target == CID and meta == {'attempt': 'resolve', 'action': 'release'}


def test_gateway_timeout_in_front_of_the_platform_is_also_no_reply(ctx, plat):
    plat.forced[('POST', '/api/bridge/expert-files/%s/assign' % FID)] = (504, None)
    r = _call(ctx, 'POST', '/api/platform-expert-files/%s/assign' % FID, {'expert_email': 'hala@experts.test'})
    assert r.status_code == 502 and r.get_json()['no_reply'] is True


# ---------------------------------------------------------------- ٦) المعرّفات والمهلة

@pytest.mark.parametrize('bad', ['x' * 65, 'a.b', 'a%2Fb', '..', '%2E%2E', 'a b', 'ملف'])
def test_ids_are_validated_before_the_url_is_built(ctx, plat, bad):
    for method, tmpl, body in (
            ('GET', '/api/platform-expert-files/%s', None),
            ('POST', '/api/platform-expert-files/%s/refund', {'confirmed': True}),
            ('POST', '/api/platform-expert-files/%s/assign', {'expert_email': 'hala@experts.test'}),
            ('POST', '/api/platform-expert-files/%s/resolve', {'action': 'refund', 'confirmed': True}),
            ('POST', '/api/platform-consultation-disputes/%s/resolve', {'action': 'refund', 'confirmed': True})):
        r = _call(ctx, method, tmpl % bad, body)
        # `a/b` ما بيطابقش المسار أصلًا (Flask ما بيعدّيش «/» في المعرّف): GET بيقع على صفحة
        # الواجهة العامة، وPOST ٤٠٥. الحَكَم إن المنصة ما اتنادتش.
        assert plat.seen == [], (tmpl, bad)
        if method == 'POST':
            assert r.status_code in (404, 405), (tmpl, bad, r.status_code)
        if r.status_code == 404 and r.is_json:
            assert r.get_json()['error'] in ('الملف ده مش موجود', 'النزاع ده مش موجود')


def test_a_long_id_gets_the_arabic_not_found(ctx, plat):
    r = _call(ctx, 'POST', '/api/platform-expert-files/%s/refund' % ('x' * 65), {'confirmed': True})
    assert r.status_code == 404 and r.get_json() == {'error': 'الملف ده مش موجود'}
    r = _call(ctx, 'POST', '/api/platform-consultation-disputes/%s/resolve' % ('x' * 65),
              {'action': 'refund', 'confirmed': True})
    assert r.status_code == 404 and r.get_json() == {'error': 'النزاع ده مش موجود'}


def test_writes_use_the_long_timeout_and_reads_the_short_one(ctx, plat):
    for method, path, body in ROUTES:
        plat.seen.clear()
        _call(ctx, method, path, body)
        t = plat.seen[-1]['timeout']
        assert (t >= 25) if method == 'POST' else (t == 12), (path, t)
