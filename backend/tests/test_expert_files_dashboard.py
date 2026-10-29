# -*- coding: utf-8 -*-
"""«ملف للخبير» في الداشبورد — المسارات فوق جسر المنصة (الجولة ٦، ومتحدّثة لأشكال الجولة ٧).

Run:  cd backend && python3 -m pytest -q tests/test_expert_files_dashboard.py

⛔ المنصة متزيّفة بالكامل: `requests.request` بيرد من جدول في الذاكرة (أشكال الجسر بالحرف من
`ef_fixtures.py`)، وأي عنوان برّه `https://platform.test` بيتسجّل كطلب ممنوع ويوقع الاختبار.

اللي بيثبّته (docs/EXPERT-FILES-DASHBOARD-SPEC.md §١٠-أ):
  ١. الصلاحية: أدمن بس — الموظف وغيره ٤٠٣ **من غير أي نداء للمنصة**، ومن غير توكن ٤٠١.
  ٢. شكل النداء للمنصة بالحرف (المسار · المعاملات · الجسم من غير مفاتيح زيادة · السرّ في الرأس بس).
  ٣. الفعل مرة واحدة: نداء واحد للمنصة لكل ضغطة — ولا إعادة محاولة حتى لو الرد ضاع.
  ٤. أخطاء المنصة بتوصل للمؤسس بالعربي (الإنجليزي بيتترجم، والعربي بيعدّي زي ما هو).
  ٥. السجل: بعد النجاح بس، بإيميل اللي عمل الفعل، وبأرقام المنصة مش المتصفح.
  ٦. الجولة ٧: كل كتابة بتبعت `by` = إيميل الأدمن (من التوكن) · «رجّع الفلوس» لملف اتدفع وما وصلش ·
     القوايم الجديدة (`blocked` · `unactivated`) · الخدمة مقفولة والجسر شغّال.
  ٧. الجولة ٨ (§١٧): مراجعة أول ملفات الخبير (اعتمد بتأكيد · رجّع بملاحظة لازمة) + «مبني على» بنفس قاعدة المنصة ·
     «استشارات قديمة محتاجة قرارك» (القايمة والقرار بتأكيد) · «للخبير» المرفوض بعد ما العميل خد فلوسه بكلام المنصة ·
     وضع الخدمة (التجربة) ورفضها بكلامها.
  ٨. الجولة ١٢ (رسالة الخبير الصوتية): بروكسي `GET /platform-expert-files/<id>/voice` — أدمن بس · بايتات الجسر بنفس النوع
     (قايمة بيضا) وترويسات `no-store` + `nosniff` + CSP محبوس · `voice` في التفاصيل ثلاث مفاتيح بس · صفر بيانات تانية.
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
UCID = fx.U1['consultation_id']
RID = fx.R1['id']            # الجولة ٨: رأي مستني مراجعة المؤسس
LID = fx.L1['id']            # الجولة ٨: استشارة قديمة محتاجة قرار
ADMIN = 'ef-admin@x.test'

ROUTES = [
    ('GET', '/api/platform-expert-files', None),
    ('GET', '/api/platform-expert-files/' + FID, None),
    ('GET', '/api/platform-expert-files/%s/voice' % RID, None),     # الجولة ١٢: رسالة الخبير الصوتية
    ('POST', '/api/platform-expert-files/%s/assign' % FID, {'expert_email': 'hala@experts.test'}),
    ('POST', '/api/platform-expert-files/%s/reassign' % FID, {'expert_email': 'hala@experts.test'}),
    ('POST', '/api/platform-expert-files/%s/refund' % FID, {'confirmed': True}),
    ('POST', '/api/platform-expert-files/unactivated/%s/refund' % UCID, {'confirmed': True}),
    ('POST', '/api/platform-expert-files/%s/resolve' % FID, {'action': 'release', 'confirmed': True}),
    ('GET', '/api/platform-consultation-disputes', None),
    ('POST', '/api/platform-consultation-disputes/%s/resolve' % CID, {'action': 'refund', 'confirmed': True}),
    # الجولة ٨
    ('POST', '/api/platform-expert-files/%s/review' % RID, {'action': 'approve', 'confirmed': True}),
    ('GET', '/api/platform-legacy-consultations', None),
    ('POST', '/api/platform-legacy-consultations/%s/decide' % LID, {'action': 'release', 'confirmed': True}),
]


class _Resp(object):
    def __init__(self, status, payload):
        self.status_code = status
        self._p = payload
        if isinstance(payload, bytes):         # رسالة الخبير الصوتية (الجولة ١٢): بايتات مش JSON
            self.content = payload
            self.headers = {'Content-Type': 'audio/webm'}
        else:
            self.content = json.dumps(payload).encode() if payload is not None else b''
            self.headers = {'Content-Type': 'application/json'}

    def json(self):
        if isinstance(self._p, bytes):
            raise ValueError('not json')
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
        self.ef = fx.EFPlatform(r8=True)          # الجولة ٨: فيها «مستنية مراجعتك» و«استشارات قديمة»
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
    for s_ in ('blocked', 'unactivated'):                        # الجولة ٧ (ب٢ · ب٩)
        _call(ctx, 'GET', '/api/platform-expert-files?status=' + s_)
        assert plat.seen[-1]['params'] == {'status': s_}
    for q in ('', '?status=', '?status=all', '?status=xyz', '?status=followup'):
        _call(ctx, 'GET', '/api/platform-expert-files' + q)
        assert plat.seen[-1]['params'] == {'status': 'waiting'}, q
    _call(ctx, 'GET', '/api/platform-expert-files?status=DISPUTED')
    assert plat.seen[-1]['params'] == {'status': 'disputed'}


def test_list_payload_is_verbatim_plus_enabled(ctx, plat):
    r = _call(ctx, 'GET', '/api/platform-expert-files?status=waiting')
    assert r.status_code == 200
    body = r.get_json()
    expected = fx.list_payload('waiting', [fx.F7, fx.F2, fx.F4, fx.F3, fx.F1])
    assert body.pop('enabled') is True
    assert body == expected                       # ولا مفتاح بيتشال ولا بيتحسب


@pytest.mark.parametrize('path,key', [('/api/platform-expert-files?status=late', 'files'),
                                      ('/api/platform-consultation-disputes', 'consultations')])
def test_bridge_not_deployed_404_is_enabled_false_not_a_failure(ctx, plat, path, key):
    plat.ef.deployed = False
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


def test_detail_bridge_not_deployed_message(ctx, plat):
    plat.ef.deployed = False
    r = _call(ctx, 'GET', '/api/platform-expert-files/' + FID)
    assert r.status_code == 404
    assert r.get_json() == {'error': 'ملفات «ملف للخبير» مش واصلة للداشبورد لسه'}
    plat.ef.deployed = True
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
    assert sent['json'] == {'expert_email': 'hala@experts.test', 'note': 'ن', 'by': ADMIN}   # ولا مفتاح زيادة
    assert len(plat.seen) == 1                                                     # الفعل مرة واحدة
    rows = _audits('expert_file.assign', FID)
    assert len(rows) == 1
    actor, target, meta = rows[0]
    assert actor == 'ef-admin@x.test'
    assert meta['assigned_to'] == 'hala@experts.test' and meta['assigned_name'] == 'أ. هالة سمير'
    assert meta['title'] == fx.F1['title']                           # السجل بيعرض اسم الملف مش رقمه
    assert meta['amount'] == 500.0 and meta['currency'] == 'EGP' and meta['note'] == 'ن'


def test_reassign_goes_to_reassign_and_records_previous_expert(ctx, plat):
    fid = fx.F5['id']
    r = _call(ctx, 'POST', '/api/platform-expert-files/%s/reassign' % fid, {'expert_email': 'faisal@experts.test'})
    assert r.status_code == 200, r.get_json()
    assert plat.seen[-1]['url'] == PLATFORM + '/api/bridge/expert-files/%s/reassign' % fid
    assert plat.seen[-1]['json'] == {'expert_email': 'faisal@experts.test', 'note': '', 'by': ADMIN}
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
    assert plat.seen[-1]['json'] == {'note': 'الخبير ما استلمش', 'by': ADMIN}   # ⛔ ولا confirmed ولا مبلغ
    assert len(plat.seen) == 1
    (actor, _t, meta), = _audits('expert_file.refund', fid)
    assert actor == 'ef-admin@x.test'
    assert meta['amount'] == 500.0 and meta['currency'] == 'EGP'     # من رد المنصة
    assert meta['status'] == 'refunded'


def test_note_is_text_only_and_clipped_to_the_bridge_limit(ctx, plat):
    _call(ctx, 'POST', '/api/platform-expert-files/%s/refund' % FID, {'confirmed': True, 'note': 'ن' * 1500})
    assert plat.seen[-1]['json'] == {'note': 'ن' * 1000, 'by': ADMIN}
    _call(ctx, 'POST', '/api/platform-expert-files/%s/resolve' % fx.D1['id'],
          {'action': 'refund', 'confirmed': True, 'note': {'x': 1}})
    assert plat.seen[-1]['json'] == {'action': 'refund', 'note': '', 'by': ADMIN}


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
    assert plat.seen[-1]['json'] == {'action': 'release', 'note': 'الخبير عدّل والتعديل كفاية', 'by': ADMIN}
    assert plat.seen[-1]['timeout'] >= 25
    (_a, _t, meta), = _audits('expert_file.resolve', fid)
    assert meta['action'] == 'release' and meta['expert_amount'] == 300.0 and meta['status'] == 'closed'


def test_resolve_forwards_action_and_note_for_a_consultation(ctx, plat):
    r = _call(ctx, 'POST', '/api/platform-consultation-disputes/%s/resolve' % CID,
              {'action': 'refund', 'confirmed': True, 'note': 'ملاحظة'})
    assert r.status_code == 200, r.get_json()
    assert plat.seen[-1]['url'] == PLATFORM + '/api/bridge/consultations/%s/resolve' % CID
    assert plat.seen[-1]['json'] == {'action': 'refund', 'note': 'ملاحظة', 'by': ADMIN}
    (actor, _t, meta), = _audits('consultation.resolve', CID)
    assert actor == 'ef-admin@x.test'
    assert meta == {'title': 'مراجعة عقد شراكة', 'kind': 'consultation', 'amount': 750, 'currency': 'EGP',
                    'expert_amount': 600, 'platform_fee': 150, 'status': 'refunded', 'expert_email': 'amr@experts.test',
                    'expert_name': 'أ. عمرو الشريف', 'action': 'refund', 'note': 'ملاحظة'}
    assert r.get_json() == {'ok': True, 'status': 'refunded'}         # ولا بيانات العميل للمتصفح


def test_second_click_reaches_the_platform_once_more_and_its_guard_answers(ctx, plat):
    """الضغطة التانية (تاب تاني مثلًا) بتوصل المنصة **مرة واحدة** بس، وحارسها هو اللي بيرد —
    والداشبورد ما بيسجّلش فعل ما حصلش. (الجولة ٨: على D2 — D3 فلوسه رجعت يدوي و«للخبير» فيه مرفوض من الأول.)"""
    did = fx.D2['id']
    _call(ctx, 'POST', '/api/platform-consultation-disputes/%s/resolve' % did, {'action': 'release', 'confirmed': True})
    r = _call(ctx, 'POST', '/api/platform-consultation-disputes/%s/resolve' % did, {'action': 'release', 'confirmed': True})
    assert len(plat.seen) == 2
    assert r.status_code == 404
    assert r.get_json() == {'error': 'النزاع ده مش موجود — حدّث الصفحة'}
    assert len(_audits('consultation.resolve', did)) == 1


# ---------------------------------------------------------------- ٥) أخطاء المنصة بالعربي

@pytest.mark.parametrize('detail', [fx.E_RESOLVE_GATEWAY, fx.E_RESOLVE_MANUAL, fx.E_RESOLVE_NOT_DISPUTED,
                                    fx.E_RESOLVE_MISSING])
def test_resolve_messages_now_come_in_arabic_and_pass_verbatim(ctx, plat, detail):
    """الجولة ٧ (ب٤): رسايل `resolve_disputed` بقت عربي على المنصة — بتعدّي زي ما هي (الترجمة هنا اتشالت)."""
    fid = fx.D1['id']
    plat.forced[('POST', '/api/bridge/expert-files/%s/resolve' % fid)] = (409, {'detail': detail})
    r = _call(ctx, 'POST', '/api/platform-expert-files/%s/resolve' % fid, {'action': 'refund', 'confirmed': True})
    assert r.status_code == 409
    assert r.get_json() == {'error': detail}
    plat.forced[('POST', '/api/bridge/consultations/%s/resolve' % CID)] = (409, {'detail': detail})
    r = _call(ctx, 'POST', '/api/platform-consultation-disputes/%s/resolve' % CID, {'action': 'refund', 'confirmed': True})
    assert r.get_json() == {'error': detail}


def test_the_english_translation_table_kept_only_the_bridge_guards():
    """اللي فاضل إنجليزي على المنصة حرّاس الجسر بس (`_guard` · ٤٠٤ الإطار) — ترجمة الحسم اتشالت."""
    import app as appmod
    assert sorted(appmod._EF_ERRORS_AR) == ['Database not available', 'Not Found', 'unauthorized']


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


def test_bridge_missing_mid_action_says_so(ctx, plat):
    plat.ef.deployed = False
    r = _call(ctx, 'POST', '/api/platform-expert-files/%s/refund' % FID, {'confirmed': True})
    assert r.status_code == 404
    assert r.get_json() == {'error': 'ملفات «ملف للخبير» مش واصلة للداشبورد لسه'}
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


# ---------------------------------------------------------------- ٧) مراجعة الجولة ٦: رد ضاع · بيانات العميل

@pytest.mark.parametrize('status', [500, 503])
def test_platform_crash_after_a_money_write_is_no_reply_not_a_refusal(ctx, plat, status):
    """المنصة وقعت بعد ما الفلوس ممكن تكون اتحرّكت (مثلًا `_audit` بعد الاسترداد) ⇒ «ما وصلناش رد» + سطر سجل،
    مش «اترفض» والزرار يرجع يتضغط."""
    path = '/api/bridge/expert-files/%s/refund' % FID
    plat.forced[('POST', path)] = (status, None)
    r = _call(ctx, 'POST', '/api/platform-expert-files/%s/refund' % FID, {'confirmed': True})
    assert r.status_code == 502 and r.get_json()['no_reply'] is True
    assert len(plat.seen) == 1
    (_a, target, meta), = _audits('expert_file.no_reply')
    assert target == FID and meta == {'attempt': 'refund'}
    plat.forced[('POST', '/api/bridge/consultations/%s/resolve' % CID)] = (status, {'detail': 'Internal Server Error'})
    r = _call(ctx, 'POST', '/api/platform-consultation-disputes/%s/resolve' % CID, {'action': 'refund', 'confirmed': True})
    assert r.status_code == 502 and r.get_json()['no_reply'] is True
    assert len(_audits('consultation.no_reply', CID)) == 1


def test_not_configured_is_a_plain_refusal_not_no_reply(ctx, plat, monkeypatch):
    """من غير سرّ مفيش نداء اتعمل أصلًا ⇒ رفض عادي (ولا سطر «ما وصلش رد»)."""
    import app as appmod
    monkeypatch.setattr(appmod, 'PLATFORM_METRICS_SECRET', '')
    r = _call(ctx, 'POST', '/api/platform-expert-files/%s/refund' % FID, {'confirmed': True})
    assert r.status_code == 503 and 'no_reply' not in r.get_json()
    assert plat.seen == [] and _audits('expert_file.no_reply') == []


def test_detail_reaches_the_browser_without_client_data(ctx, plat):
    r = _call(ctx, 'GET', '/api/platform-expert-files/' + fx.D1['id'])
    body = r.get_json()
    assert sorted(body) == ['based_on', 'case', 'client_tz', 'client_tz_label', 'dispute', 'file_no', 'id', 'opinion',
                            'pending_opinion', 'review', 'revision', 'speed', 'status', 'title', 'urgent', 'voice']
    assert body['file_no'] == 1042
    assert body['speed'] == 'normal' and body['urgent'] is None and body['case'] is None   # ملف قديم من غير الجولة ١٣
    assert body['based_on'] is None and body['pending_opinion'] is None   # «مبني على» للرأي اللي مستني مراجعة بس
    assert body['client_tz'] is None and body['client_tz_label'] is None  # توقيت العميل لدرج المراجعة بس
    raw = r.get_data(as_text=True)
    for leak in (fx.CLIENT_EMAILS['D1'], 'ريم عبد الله', 'pay-'):
        assert leak not in raw, leak


@pytest.mark.parametrize('method,path,body', [r for r in ROUTES if r[0] == 'POST'])
def test_action_replies_carry_ok_and_status_only(ctx, plat, method, path, body):
    if path.endswith('/reassign'):
        path = path.replace(FID, fx.F5['id'])
        body = {'expert_email': 'faisal@experts.test'}
    if path.endswith('/resolve') and 'expert-files' in path:
        path = path.replace(FID, fx.D1['id'])
    r = _call(ctx, method, path, body)
    assert r.status_code == 200, (path, r.get_json())
    out = r.get_json()
    assert sorted(out) == ['ok', 'status'] and out['ok'] is True and out['status']
    assert '@clients.test' not in r.get_data(as_text=True)


def test_consultation_disputes_list_hides_client_email_and_payment_id(ctx, plat):
    r = _call(ctx, 'GET', '/api/platform-consultation-disputes')
    rows = r.get_json()['consultations']
    assert rows and all('member_email' not in c and 'payment_id' not in c for c in rows)
    assert rows[1]['dispute_reason'] == fx.D2['dispute_reason']        # الباقي زي ما هو
    assert '@clients.test' not in r.get_data(as_text=True)


# ---------------------------------------------------------------- ٨) الجولة ٧: اللي الجسر بقى بيبعته

@pytest.mark.parametrize('method,path,body', [r for r in ROUTES if r[0] == 'POST'])
def test_by_is_the_signed_in_admin_never_what_the_browser_sent(ctx, plat, method, path, body):
    """`by` بيتاخد من التوكن في الخادم — `by` اللي في جسم المتصفح بيتجاهل (ب٥)."""
    if path.endswith('/reassign'):
        path, body = path.replace(FID, fx.F5['id']), {'expert_email': 'faisal@experts.test'}
    if path.endswith('/resolve') and 'expert-files' in path:
        path = path.replace(FID, fx.D1['id'])
    r = _call(ctx, method, path, dict(body, by='someone@evil.test'))
    assert r.status_code == 200, (path, r.get_json())
    assert plat.seen[-1]['json']['by'] == ADMIN


def test_blocked_and_unactivated_lists_are_verbatim(ctx, plat):
    body = _call(ctx, 'GET', '/api/platform-expert-files?status=blocked').get_json()
    assert body.pop('enabled') is True
    assert body == fx.list_payload('blocked', [fx.F7, fx.F6])
    f6 = body['files'][1]
    assert f6['needs_attention'] is True and f6['blocked'][0]['key'] == 'release_blocked_at'
    assert f6['blocked'][0]['label'] == fx.BLOCK_LABELS['release_blocked_at']
    body = _call(ctx, 'GET', '/api/platform-expert-files?status=unactivated').get_json()
    assert body.pop('enabled') is True
    assert body == fx.list_payload('unactivated', [fx.U2, fx.U1])
    assert body['files'][0]['file_found'] is False and body['files'][0]['id'] is None


def test_unactivated_refund_forwards_note_and_by_and_audits_the_platform_numbers(ctx, plat):
    r = _call(ctx, 'POST', '/api/platform-expert-files/unactivated/%s/refund' % UCID,
              {'confirmed': True, 'note': 'التفعيل وقع', 'amount': 1})
    assert r.status_code == 200, r.get_json()
    assert r.get_json() == {'ok': True, 'status': 'refunded'}
    sent = plat.seen[-1]
    assert sent['url'] == PLATFORM + '/api/bridge/expert-files/unactivated/%s/refund' % UCID
    assert sent['json'] == {'note': 'التفعيل وقع', 'by': ADMIN}          # ⛔ ولا confirmed ولا مبلغ
    assert sent['timeout'] >= 25 and len(plat.seen) == 1
    (actor, target, meta), = _audits('expert_file.refund_unactivated', UCID)
    assert actor == ADMIN and target == UCID
    assert meta['amount'] == 500.0 and meta['currency'] == 'EGP' and meta['money_status'] == 'refunded'
    assert meta['title'] == fx.U1['title'] and meta['consultation_id'] == UCID


def test_unactivated_refund_twice_is_refused_by_the_platform_and_audited_once(ctx, plat):
    path = '/api/platform-expert-files/unactivated/%s/refund' % UCID
    _call(ctx, 'POST', path, {'confirmed': True})
    r = _call(ctx, 'POST', path, {'confirmed': True})
    assert r.status_code == 409
    assert r.get_json() == {'error': fx.E_MONEY_MOVED}
    assert len(plat.seen) == 2 and len(_audits('expert_file.refund_unactivated', UCID)) == 1


@pytest.mark.parametrize('body', [{}, {'confirmed': 'true'}, {'confirmed': 1}])
def test_unactivated_refund_needs_the_confirm_window(ctx, plat, body):
    r = _call(ctx, 'POST', '/api/platform-expert-files/unactivated/%s/refund' % UCID, body)
    assert r.status_code == 400 and r.get_json() == {'error': 'لازم تأكّد الأول من الشاشة'}
    assert plat.seen == [] and _audits('expert_file.refund_unactivated') == []


@pytest.mark.parametrize('detail', [fx.E_NOT_PAID_YET, fx.E_ALREADY_LISTED, fx.E_REFUND_MANUAL, fx.E_REFUND_GATEWAY])
def test_unactivated_refund_refusals_pass_verbatim(ctx, plat, detail):
    plat.forced[('POST', '/api/bridge/expert-files/unactivated/%s/refund' % UCID)] = (409, {'detail': detail})
    r = _call(ctx, 'POST', '/api/platform-expert-files/unactivated/%s/refund' % UCID, {'confirmed': True})
    assert r.status_code == 409 and r.get_json() == {'error': detail}
    assert _audits('expert_file.refund_unactivated') == []


def test_unactivated_refund_no_reply_is_said_and_logged(ctx, plat):
    plat.forced[('POST', '/api/bridge/expert-files/unactivated/%s/refund' % UCID)] = _requests.Timeout('slow')
    r = _call(ctx, 'POST', '/api/platform-expert-files/unactivated/%s/refund' % UCID, {'confirmed': True})
    assert r.status_code == 502 and r.get_json()['no_reply'] is True
    (_a, target, meta), = _audits('expert_file.no_reply', UCID)
    assert meta == {'attempt': 'refund_unactivated'}


@pytest.mark.parametrize('bad', ['x' * 65, 'a.b', '..', 'a b', 'ملف'])
def test_unactivated_refund_validates_the_id_first(ctx, plat, bad):
    r = _call(ctx, 'POST', '/api/platform-expert-files/unactivated/%s/refund' % bad, {'confirmed': True})
    assert r.status_code in (404, 405) and plat.seen == []


def test_service_closed_lists_still_come_and_only_sending_is_refused(ctx, plat):
    """الجولة ٧ (ب١): الخدمة مقفولة للناس والجسر شغّال بالسرّ — الصفوف بتيجي (`service_open: false`)، والرجوع
    شغّال، و«ابعته لـ…» بيرجع برسالة المنصة زي ما هي."""
    plat.ef.service_open = False
    body = _call(ctx, 'GET', '/api/platform-expert-files?status=waiting').get_json()
    assert body['enabled'] is True and body['service_open'] is False and len(body['files']) == 5
    r = _call(ctx, 'POST', '/api/platform-expert-files/%s/assign' % FID, {'expert_email': 'hala@experts.test'})
    assert r.status_code == 409 and r.get_json() == {'error': fx.E_SERVICE_OFF}
    assert _audits('expert_file.assign') == []
    r = _call(ctx, 'POST', '/api/platform-expert-files/%s/refund' % FID, {'confirmed': True})
    assert r.status_code == 200 and len(_audits('expert_file.refund', FID)) == 1


def test_consultation_dispute_rows_name_who_gets_paid_and_still_hide_the_client(ctx, plat):
    rows = _call(ctx, 'GET', '/api/platform-consultation-disputes').get_json()['consultations']
    d2 = [c for c in rows if c['id'] == fx.D2['id']][0]
    assert d2['payee_email'] == 'amr@experts.test' and d2['payee_name'] == 'أ. عمرو الشريف'
    assert d2['release_amount'] == 600 and d2['reason_label'] == ''
    d1 = [c for c in rows if c['id'] == fx.D1_CONS['id']][0]
    assert d1['reason_label'] == 'الرأي ما ردّش على سؤالي'
    assert all('member_email' not in c and 'payment_id' not in c for c in rows)


def test_reassign_audit_names_the_previous_expert_from_the_platform_reply(ctx, plat):
    fid = fx.F5['id']
    _call(ctx, 'POST', '/api/platform-expert-files/%s/reassign' % fid, {'expert_email': 'faisal@experts.test'})
    (_a, _t, meta), = _audits('expert_file.reassign', fid)
    assert meta['previous_expert'] == meta['previous_expert_email'] == 'sami@experts.test'


# ---------------------------------------------------------------- ٩) الجولة ٨ — قرارات المؤسس (SPEC §١٧)
# م٩ مراجعة أول ملفات الخبير الجديد · م١٠/م١١ «استشارات قديمة محتاجة قرارك» · «للخبير» مقفول بسبب المنصة ·
# وضع الخدمة (open | allowlist | closed). الأشكال من `ef_fixtures` (كود المنصة على فرع الجولة ٨ بالحرف).

def test_review_list_is_forwarded_and_verbatim_with_the_service_mode(ctx, plat):
    r = _call(ctx, 'GET', '/api/platform-expert-files?status=review')
    assert plat.seen[-1]['params'] == {'status': 'review'}
    body = r.get_json()
    assert body.pop('enabled') is True
    assert body == fx.list_payload('review', [fx.R1, fx.R2])
    assert body['service_mode'] == 'open' and body['allowlist_size'] == 0
    r1 = body['files'][0]
    assert r1['status'] == 'in_review' and r1['status_label'] == 'بنراجع رأيك قبل ما يوصلك'
    assert r1['review']['submitted_at'] and r1['review']['returns'] == 0
    assert r1['pending_opinion']['answers'][0]['question'] == fx.R1_OPINION['answers'][0]['question']
    assert r1['expert_delivered_count'] == 0 and body['files'][1]['expert_delivered_count'] == 1


@pytest.mark.parametrize('body', [{'action': 'approve'}, {'action': 'approve', 'confirmed': 'true'},
                                  {'action': 'approve', 'confirmed': 1}])
def test_review_approve_needs_the_confirm_window(ctx, plat, body):
    r = _call(ctx, 'POST', '/api/platform-expert-files/%s/review' % RID, body)
    assert r.status_code == 400 and r.get_json() == {'error': 'لازم تأكّد الأول من الشاشة'}
    assert plat.seen == [] and _audits('expert_file.review_approve') == []


@pytest.mark.parametrize('note', [None, '', '   ', 5, ['x'], {'t': 'x'}])
def test_review_return_needs_a_note_for_the_expert(ctx, plat, note):
    r = _call(ctx, 'POST', '/api/platform-expert-files/%s/review' % RID, {'action': 'return', 'note': note})
    assert r.status_code == 400 and r.get_json() == {'error': 'اكتب ملاحظة للخبير'}
    assert plat.seen == [] and _audits('expert_file.review_return') == []


@pytest.mark.parametrize('action', [None, '', 'reject', 'APPROVE', 'release', 'approve '])
def test_review_action_is_validated_locally(ctx, plat, action):
    r = _call(ctx, 'POST', '/api/platform-expert-files/%s/review' % RID,
              {'action': action, 'confirmed': True, 'note': 'x'})
    assert r.status_code == 400 and r.get_json() == {'error': 'اختار: وافق ولا رجّعه للخبير'}
    assert plat.seen == []


def test_review_approve_forwards_the_bridge_model_and_audits_the_platform_numbers(ctx, plat):
    r = _call(ctx, 'POST', '/api/platform-expert-files/%s/review' % RID,
              {'action': 'approve', 'confirmed': True, 'note': ' ', 'amount': 1, 'by': 'x@evil.test'})
    assert r.status_code == 200, r.get_json()
    assert r.get_json() == {'ok': True, 'status': 'delivered'}
    sent = plat.seen[-1]
    assert sent['url'] == PLATFORM + '/api/bridge/expert-files/%s/review' % RID
    assert sent['json'] == {'action': 'approve', 'note': '', 'by': ADMIN}      # ⛔ ولا confirmed ولا مبلغ
    assert sent['timeout'] >= 25 and len(plat.seen) == 1
    (actor, target, meta), = _audits('expert_file.review_approve', RID)
    assert actor == ADMIN and target == RID
    assert meta['title'] == fx.R1['title'] and meta['amount'] == 500.0 and meta['currency'] == 'EGP'
    assert meta['expert_name'] == 'أ. رنا عادل' and meta['status'] == 'delivered' and meta['review_round'] == 1
    assert 'note' not in meta


def test_review_return_sends_the_note_to_the_expert_and_audits_it(ctx, plat):
    note = 'الإجابة الأولى محتاجة تذكر المادة اللي بتحدد مدة سقوط الدعوى.'
    r = _call(ctx, 'POST', '/api/platform-expert-files/%s/review' % RID, {'action': 'return', 'note': '  ' + note})
    assert r.status_code == 200 and r.get_json() == {'ok': True, 'status': 'writing'}
    assert plat.seen[-1]['json'] == {'action': 'return', 'note': note, 'by': ADMIN}
    (_a, _t, meta), = _audits('expert_file.review_return', RID)
    assert meta['note'] == note and meta['review_returns'] == 1 and meta['status'] == 'writing'
    assert _audits('expert_file.review_approve') == []


def test_review_note_is_clipped_to_the_bridge_limit(ctx, plat):
    _call(ctx, 'POST', '/api/platform-expert-files/%s/review' % RID, {'action': 'return', 'note': 'ن' * 1500})
    assert plat.seen[-1]['json']['note'] == 'ن' * 1000


@pytest.mark.parametrize('status,detail', [(409, fx.E_REVIEW_RETURNED), (409, fx.E_REVIEW_SLOTS),
                                           (409, fx.E_REVIEW_NOT_WAITING), (409, fx.E_MONEY_MOVED),
                                           (409, fx.E_CLOSED), (422, fx.E_REVIEW_NOTE)])
def test_review_refusals_reach_the_founder_verbatim_and_are_never_audited(ctx, plat, status, detail):
    plat.forced[('POST', '/api/bridge/expert-files/%s/review' % RID)] = (status, {'detail': detail})
    r = _call(ctx, 'POST', '/api/platform-expert-files/%s/review' % RID, {'action': 'approve', 'confirmed': True})
    assert r.status_code == status and r.get_json() == {'error': detail}
    assert _audits('expert_file.review_approve') == [] and _audits('expert_file.no_reply') == []


def test_a_second_return_is_refused_by_the_platform_in_its_words(ctx, plat):
    """R2 اترجع للخبير مرة قبل كده ⇒ المنصة بترفض الرجوع التاني بكلامها (والداشبورد ما بيقررش ده لوحده)."""
    r = _call(ctx, 'POST', '/api/platform-expert-files/%s/review' % fx.R2['id'], {'action': 'return', 'note': 'تاني'})
    assert r.status_code == 409 and r.get_json() == {'error': fx.E_REVIEW_RETURNED}
    assert len(plat.seen) == 1 and _audits('expert_file.review_return') == []


def test_review_twice_reaches_the_platform_guard(ctx, plat):
    path = '/api/platform-expert-files/%s/review' % RID
    _call(ctx, 'POST', path, {'action': 'approve', 'confirmed': True})
    r = _call(ctx, 'POST', path, {'action': 'approve', 'confirmed': True})
    assert r.status_code == 409 and r.get_json() == {'error': fx.E_REVIEW_NOT_WAITING}
    assert len(plat.seen) == 2 and len(_audits('expert_file.review_approve', RID)) == 1


def test_review_no_reply_is_said_and_logged(ctx, plat):
    plat.forced[('POST', '/api/bridge/expert-files/%s/review' % RID)] = _requests.Timeout('slow')
    r = _call(ctx, 'POST', '/api/platform-expert-files/%s/review' % RID, {'action': 'approve', 'confirmed': True})
    assert r.status_code == 502 and r.get_json()['no_reply'] is True
    assert len(plat.seen) == 1                                            # ⛔ ولا إعادة محاولة
    (_a, target, meta), = _audits('expert_file.no_reply', RID)
    assert meta == {'attempt': 'review', 'action': 'approve'}


@pytest.mark.parametrize('bad', ['x' * 65, 'a.b', '..', 'a b', 'ملف'])
def test_review_validates_the_id_first(ctx, plat, bad):
    r = _call(ctx, 'POST', '/api/platform-expert-files/%s/review' % bad, {'action': 'approve', 'confirmed': True})
    assert r.status_code in (404, 405) and plat.seen == []


def test_detail_of_a_file_in_review_carries_the_opinion_and_based_on_without_client_data(ctx, plat):
    r = _call(ctx, 'GET', '/api/platform-expert-files/' + RID)
    body = r.get_json()
    assert r.status_code == 200
    assert body['pending_opinion'] == fx.R1_OPINION and body['review']['round'] == 1
    import app as appmod
    det = fx.REVIEW_DETAIL[RID]
    expected = 'الرأي ده مبني على الوقائع اللي أكّدها سمر يوم %s، ومستندين، وعلى القانون المصري.' % (
        appmod._ef_ar_date(det['facts_confirmed_at'], 'eg'))
    assert body['based_on'] == expected
    raw = r.get_data(as_text=True)
    for leak in (fx.CLIENT_EMAILS['R1'], 'سمر ماهر', 'pay-', 'محضر الشرطة.pdf'):
        assert leak not in raw, leak


def test_based_on_counts_additions_and_no_documents_like_the_platform(ctx, plat):
    body = _call(ctx, 'GET', '/api/platform-expert-files/' + fx.R2['id']).get_json()
    import app as appmod
    det = fx.REVIEW_DETAIL[fx.R2['id']]
    assert body['based_on'] == ('الرأي ده مبني على الوقائع اللي أكّدها دينا يوم %s، من غير مستندات، وردّه يوم %s، '
                                'وعلى القانون المصري.' % (appmod._ef_ar_date(det['facts_confirmed_at'], 'eg'),
                                                         appmod._ef_ar_date(det['additions'][0]['at'], 'eg')))


@pytest.mark.parametrize('country,tz,label', [('eg', 'Africa/Cairo', 'بتوقيت مصر'),
                                              ('sa', 'Asia/Riyadh', 'بتوقيت السعودية'),
                                              ('ae', 'Asia/Dubai', 'بتوقيت الإمارات'),
                                              ('default', None, None)])
def test_review_detail_names_the_clients_time_zone_from_the_price_country(ctx, plat, monkeypatch, country, tz, label):
    """مراجعة الجولة ٨: مواعيد الجلسة في درج المراجعة بتوقيت العميل — المنطقة واسمها من بلد السعر (`price.country`) بنفس
    `expert_files.ZONES` (العميل بيشوفها بـ`price.tz`). بلد برّه القايمة ⇒ فاضي (المنصة بتعرضها بتوقيت جهازه).
    ⛔ بلد العميل نفسه وسعره ما بيوصلوش المتصفح — المنطقة واسمها بس."""
    rid = fx.R2['id']
    monkeypatch.setitem(fx.REVIEW_DETAIL, rid, dict(fx.REVIEW_DETAIL[rid], price={'country': country, 'currency': 'EGP'}))
    body = _call(ctx, 'GET', '/api/platform-expert-files/' + rid).get_json()
    assert body['client_tz'] == tz and body['client_tz_label'] == label
    assert 'price' not in body and 'country' not in json.dumps(body)


def test_based_on_prefers_the_platform_sentence_when_it_is_sent(ctx, plat):
    plat.ef.review[0]['pending_opinion']['based_on'] = 'جملة المنصة بالحرف.'
    body = _call(ctx, 'GET', '/api/platform-expert-files/' + plat.ef.review[0]['id']).get_json()
    assert body['based_on'] == 'جملة المنصة بالحرف.'


def test_based_on_mirror_matches_the_platform_rules():
    """`build_based_on` على المنصة بالحرف: عدّ المستندات · المنطقة الزمنية لبلد السعر · الأسئلة اللي ما اتردّش عليها."""
    import app as appmod
    base = {'client_name': 'منى عبد الله', 'law_label': 'القانون المصري', 'price': {'country': 'eg'},
            'facts_confirmed_at': '2026-10-26T22:30:00+00:00', 'additions': [], 'docs': [], 'info': None}
    # ٢٢:٣٠ UTC = ٠٠:٣٠ بتوقيت القاهرة ⇒ ٢٧ أكتوبر
    assert appmod._ef_based_on(base) == 'الرأي ده مبني على الوقائع اللي أكّدها منى يوم ٢٧ أكتوبر ٢٠٢٦، من غير مستندات، وعلى القانون المصري.'
    for n, phrase in ((1, 'ومستند واحد'), (2, 'ومستندين'), (5, 'و٥ مستندات'), (10, 'و١٠ مستندات'), (11, 'و١١ مستند')):
        assert phrase in appmod._ef_based_on(dict(base, docs=[{}] * n)), n
    sa = dict(base, price={'country': 'sa'}, facts_confirmed_at='2026-10-26T21:30:00+00:00')
    assert 'يوم ٢٧ أكتوبر ٢٠٢٦' in appmod._ef_based_on(sa)                    # +٣ الرياض
    us = dict(base, price={'country': 'default'}, facts_confirmed_at='2026-10-26T22:30:00+00:00')
    assert 'يوم ٢٦ أكتوبر ٢٠٢٦' in appmod._ef_based_on(us)                    # من غير منطقة ⇒ UTC
    exp = dict(base, info={'status': 'expired', 'questions': [{'text': 'العقد مكتوب؟'}, {'text': 'فيه شهود؟'}]})
    assert appmod._ef_based_on(exp).endswith(' وأسئلة الخبير اللي ما اتردّش عليها: «العقد مكتوب؟»، «فيه شهود؟».')
    assert 'أكّدها العميل' in appmod._ef_based_on(dict(base, client_name=''))
    assert 'وعلى القانون.' in appmod._ef_based_on(dict(base, law_label=''))
    assert appmod._ef_ar_date('2026-10-26T22:30:00Z', 'eg') == '٢٧ أكتوبر ٢٠٢٦'       # «Z» زي «+00:00»
    assert appmod._ef_ar_date('مش تاريخ', 'eg') == '' and appmod._ef_ar_date(None, 'eg') == ''


# ---- «استشارات قديمة محتاجة قرارك» (م١٠ · م١١)

def test_legacy_list_is_verbatim_minus_client_email_and_payment_id(ctx, plat):
    r = _call(ctx, 'GET', '/api/platform-legacy-consultations')
    assert plat.seen[-1]['url'] == PLATFORM + '/api/bridge/consultations/legacy'
    body = r.get_json()
    assert body.pop('enabled') is True
    expected = fx.legacy_payload([{k: v for k, v in c.items() if k not in ('member_email', 'payment_id')}
                                  for c in (fx.L1, fx.L2, fx.L3)])
    assert body == expected
    assert '@clients.test' not in r.get_data(as_text=True)
    l2 = body['consultations'][1]
    assert l2['release_blocked_reason'] == fx.E_RELEASE_MANUAL and l2['refund_blocked_reason'] == fx.E_RESOLVE_MANUAL
    assert body['consultations'][0]['due'] is True and body['consultations'][2]['due'] is False


@pytest.mark.parametrize('legacy_enabled,cons_enabled', [(False, True), (True, False)])
def test_legacy_list_not_on_the_platform_yet_is_enabled_false(ctx, plat, legacy_enabled, cons_enabled):
    plat.ef.legacy_enabled = legacy_enabled
    plat.ef.cons_enabled = cons_enabled
    r = _call(ctx, 'GET', '/api/platform-legacy-consultations')
    assert r.status_code == 200
    assert r.get_json() == {'enabled': False, 'since': None, 'consultations': [], 'count': 0, 'total': 0}


def test_legacy_list_real_errors_pass_through(ctx, plat):
    plat.forced[('GET', '/api/bridge/consultations/legacy')] = (503, {'detail': 'Database not available'})
    r = _call(ctx, 'GET', '/api/platform-legacy-consultations')
    assert r.status_code == 503 and r.get_json() == {'error': 'المنصة مش متاحة دلوقتي — جرّب بعد شوية'}


@pytest.mark.parametrize('body,err', [({'action': 'release'}, 'لازم تأكّد الأول من الشاشة'),
                                      ({'action': 'release', 'confirmed': 'true'}, 'لازم تأكّد الأول من الشاشة'),
                                      ({'action': 'split', 'confirmed': True}, 'اختار: للخبير ولا للعميل'),
                                      ({'confirmed': True}, 'اختار: للخبير ولا للعميل')])
def test_legacy_decide_is_validated_locally(ctx, plat, body, err):
    r = _call(ctx, 'POST', '/api/platform-legacy-consultations/%s/decide' % LID, body)
    assert r.status_code == 400 and r.get_json() == {'error': err}
    assert plat.seen == [] and _audits('consultation.legacy') == []


@pytest.mark.parametrize('action,status', [('release', 'released'), ('refund', 'refunded')])
def test_legacy_decide_forwards_and_audits_the_platform_numbers(ctx, plat, action, status):
    r = _call(ctx, 'POST', '/api/platform-legacy-consultations/%s/decide' % LID,
              {'action': action, 'confirmed': True, 'note': ' اتأكدت من الشغل ', 'amount': 1})
    assert r.status_code == 200 and r.get_json() == {'ok': True, 'status': status}
    sent = plat.seen[-1]
    assert sent['url'] == PLATFORM + '/api/bridge/consultations/%s/legacy' % LID
    assert sent['json'] == {'action': action, 'note': 'اتأكدت من الشغل', 'by': ADMIN}
    assert sent['timeout'] >= 25 and len(plat.seen) == 1
    (actor, target, meta), = _audits('consultation.legacy', LID)
    assert actor == ADMIN and target == LID
    assert meta == {'title': fx.L1['title'], 'kind': 'consultation', 'amount': 600, 'currency': 'EGP',
                    'expert_amount': 480, 'platform_fee': 120, 'status': status, 'expert_email': 'amr@experts.test',
                    'expert_name': 'أ. عمرو الشريف', 'action': action, 'note': 'اتأكدت من الشغل'}


@pytest.mark.parametrize('action,detail', [('release', fx.E_RELEASE_MANUAL), ('refund', fx.E_RESOLVE_MANUAL)])
def test_legacy_money_already_back_is_refused_by_the_platform_in_its_words(ctx, plat, action, detail):
    r = _call(ctx, 'POST', '/api/platform-legacy-consultations/%s/decide' % fx.L2['id'],
              {'action': action, 'confirmed': True})
    assert r.status_code == 409 and r.get_json() == {'error': detail}
    assert _audits('consultation.legacy') == []


@pytest.mark.parametrize('detail', [fx.E_LEGACY_SETTLED, fx.E_LEGACY_NOT_LEGACY, fx.E_LEGACY_FILE,
                                    fx.E_LEGACY_CANCELLED, fx.E_RELEASE_GATEWAY, fx.E_RESOLVE_GATEWAY])
def test_legacy_refusals_pass_verbatim(ctx, plat, detail):
    plat.forced[('POST', '/api/bridge/consultations/%s/legacy' % LID)] = (409, {'detail': detail})
    r = _call(ctx, 'POST', '/api/platform-legacy-consultations/%s/decide' % LID, {'action': 'release', 'confirmed': True})
    assert r.status_code == 409 and r.get_json() == {'error': detail}


def test_legacy_twice_reaches_the_platform_guard_and_is_audited_once(ctx, plat):
    path = '/api/platform-legacy-consultations/%s/decide' % LID
    _call(ctx, 'POST', path, {'action': 'release', 'confirmed': True})
    r = _call(ctx, 'POST', path, {'action': 'release', 'confirmed': True})
    assert r.status_code == 409 and r.get_json() == {'error': fx.E_LEGACY_SETTLED}
    assert len(plat.seen) == 2 and len(_audits('consultation.legacy', LID)) == 1


def test_legacy_no_reply_is_said_and_logged(ctx, plat):
    plat.forced[('POST', '/api/bridge/consultations/%s/legacy' % LID)] = _requests.ConnectionError('reset')
    r = _call(ctx, 'POST', '/api/platform-legacy-consultations/%s/decide' % LID, {'action': 'refund', 'confirmed': True})
    assert r.status_code == 502 and r.get_json()['no_reply'] is True and len(plat.seen) == 1
    (_a, target, meta), = _audits('consultation.no_reply', LID)
    assert meta == {'attempt': 'legacy', 'action': 'refund'}


def test_legacy_decide_on_a_platform_without_it_says_so(ctx, plat):
    plat.ef.legacy_enabled = False
    r = _call(ctx, 'POST', '/api/platform-legacy-consultations/%s/decide' % LID, {'action': 'release', 'confirmed': True})
    assert r.status_code == 404
    assert r.get_json() == {'error': 'القرار على الاستشارات القديمة من هنا لسه مش متاح على المنصة'}
    plat.ef.legacy_enabled = True
    r = _call(ctx, 'POST', '/api/platform-legacy-consultations/no-such/decide', {'action': 'release', 'confirmed': True})
    assert r.status_code == 404 and r.get_json() == {'error': fx.E_LEGACY_MISSING}


@pytest.mark.parametrize('bad', ['x' * 65, 'a.b', '..', 'a b', 'ملف'])
def test_legacy_decide_validates_the_id_first(ctx, plat, bad):
    r = _call(ctx, 'POST', '/api/platform-legacy-consultations/%s/decide' % bad, {'action': 'release', 'confirmed': True})
    assert r.status_code in (404, 405) and plat.seen == []


# ---- «للخبير» بعد ما العميل خد فلوسه (البند ٥)

def test_release_blocked_reason_reaches_the_browser_on_every_list(ctx, plat):
    plat.ef.disputed = [fx.release_locked(fx.D1, 'gateway_refund')]
    files = _call(ctx, 'GET', '/api/platform-expert-files?status=disputed').get_json()['files']
    assert files[0]['release_blocked'] == 'gateway_refund' and files[0]['release_blocked_reason'] == fx.E_RELEASE_GATEWAY
    cons = _call(ctx, 'GET', '/api/platform-consultation-disputes').get_json()['consultations']
    d3 = [c for c in cons if c['id'] == fx.D3['id']][0]
    assert d3['release_blocked'] == 'manual_refund' and d3['release_blocked_reason'] == fx.E_RELEASE_MANUAL
    legacy = _call(ctx, 'GET', '/api/platform-legacy-consultations').get_json()['consultations']
    assert legacy[1]['release_blocked_reason'] == fx.E_RELEASE_MANUAL
    waiting = _call(ctx, 'GET', '/api/platform-expert-files?status=waiting').get_json()['files']
    assert {f['release_blocked'] for f in waiting} == {'not_claimed'}       # الفلوس لسه على بريد المنصة


@pytest.mark.parametrize('detail', [fx.E_RELEASE_MANUAL, fx.E_RELEASE_GATEWAY])
def test_release_refused_at_decision_time_reaches_the_founder_verbatim(ctx, plat, detail):
    for bridge, mine in (('/api/bridge/expert-files/%s/resolve' % fx.D1['id'],
                          '/api/platform-expert-files/%s/resolve' % fx.D1['id']),
                         ('/api/bridge/consultations/%s/resolve' % CID,
                          '/api/platform-consultation-disputes/%s/resolve' % CID)):
        plat.forced[('POST', bridge)] = (409, {'detail': detail})
        r = _call(ctx, 'POST', mine, {'action': 'release', 'confirmed': True})
        assert r.status_code == 409 and r.get_json() == {'error': detail}
    assert _audits('expert_file.resolve') == [] and _audits('consultation.resolve') == []


def test_release_on_a_manually_refunded_consultation_is_refused_by_the_platform(ctx, plat):
    r = _call(ctx, 'POST', '/api/platform-consultation-disputes/%s/resolve' % fx.D3['id'],
              {'action': 'release', 'confirmed': True})
    assert r.status_code == 409 and r.get_json() == {'error': fx.E_RELEASE_MANUAL}


# ---- وضع الخدمة (البند ١٣)

def test_allowlist_mode_reaches_the_browser_and_the_trial_refusal_passes_verbatim(ctx, plat):
    plat.ef = fx.EFPlatform(r8=True, mode='allowlist')
    body = _call(ctx, 'GET', '/api/platform-expert-files?status=waiting').get_json()
    assert body['service_mode'] == 'allowlist' and body['allowlist_size'] == len(fx.ALLOWLIST)
    assert body['service_open'] is False and len(body['files']) == 5
    r = _call(ctx, 'POST', '/api/platform-expert-files/%s/assign' % FID, {'expert_email': 'sami@experts.test'})
    assert r.status_code == 409 and r.get_json() == {'error': fx.E_TRIAL_ONLY}
    assert _audits('expert_file.assign') == []
    r = _call(ctx, 'POST', '/api/platform-expert-files/%s/assign' % FID, {'expert_email': 'hala@experts.test'})
    assert r.status_code == 200 and len(_audits('expert_file.assign', FID)) == 1
    q = plat.ef.queue()
    assert q['expert_files_service_mode'] == 'allowlist' and q['expert_files_allowlist_size'] == len(fx.ALLOWLIST)


def test_the_new_queue_keys_pass_through_untouched(ctx, plat):
    body = _call(ctx, 'GET', '/api/platform-ops-queue').get_json()
    for key in ('expert_files_in_review', 'expert_files_service_mode', 'expert_files_allowlist_size',
                'consultations_legacy', 'escrow_auto_release_since'):
        assert key in body, key
    assert body['expert_files_in_review'] == 2 and body['consultations_legacy'] == 3
    assert '🔎 2 رأي مستني مراجعتك قبل ما يوصل للعميل' in body['alerts']
    assert '🗂️ 3 استشارة قديمة اتسلّمت ومستنية قرارك — للخبير ولا للعميل' in body['alerts']


# ---- الجولة ١٢: رسالة الخبير الصوتية (docs/expert-files/SPEC-R12-VOICE.md §٣) — صفر نداء حقيقي، الجسر متزيّف

VOICE_PATH = '/api/platform-expert-files/%s/voice' % RID


def test_voice_proxy_returns_the_bridge_bytes_with_a_locked_down_response(ctx, plat):
    r = _call(ctx, 'GET', VOICE_PATH)
    assert r.status_code == 200
    assert r.data == fx.VOICE_BYTES                                          # البايتات زي ما هي
    assert r.mimetype == 'audio/webm'
    assert r.headers['Cache-Control'] == 'private, no-store'
    assert r.headers['X-Content-Type-Options'] == 'nosniff'
    assert r.headers['Content-Security-Policy'] == "default-src 'none'; sandbox"
    assert r.headers['Content-Disposition'] == 'inline; filename="voice-%s.webm"' % RID
    sent, = plat.seen
    assert sent['method'] == 'GET' and sent['url'] == PLATFORM + '/api/bridge/expert-files/%s/voice' % RID
    assert sent['params'] is None and sent['json'] is None                   # ولا حاجة تانية بتتبعت
    assert sent['headers'] == {'X-ELP-Metrics-Secret': SECRET}               # السرّ في الرأس بس
    assert _audits('expert_file.voice') == []                                # قراية بس — مفيش سجل


@pytest.mark.parametrize('ctype,ext', [('audio/webm', 'webm'), ('audio/ogg', 'ogg'), ('audio/mp4', 'm4a'),
                                       ('audio/webm; codecs=opus', 'webm'), ('Audio/MP4', 'm4a')])
def test_voice_proxy_keeps_the_allowed_audio_types(ctx, plat, monkeypatch, ctype, ext):
    class R(object):
        status_code = 200
        content = fx.VOICE_BYTES
        headers = {'Content-Type': ctype}
    import app as appmod
    monkeypatch.setattr(appmod.requests, 'request', lambda *a, **k: R())
    r = _call(ctx, 'GET', VOICE_PATH)
    assert r.status_code == 200 and r.mimetype == ctype.split(';')[0].strip().lower()
    assert r.headers['Content-Disposition'].endswith('.%s"' % ext)


@pytest.mark.parametrize('ctype', ['text/html', 'application/json', 'image/png', 'audio/mpeg', 'video/webm', ''])
def test_voice_proxy_refuses_any_type_that_is_not_the_voice_whitelist(ctx, plat, monkeypatch, ctype):
    """النوع من القايمة البيضا بس — HTML أو صورة جاية من المنصة ما بتتقدّمش من أصل الداشبورد."""
    class R(object):
        status_code = 200
        content = b'<script>alert(1)</script>'
        headers = {'Content-Type': ctype}
    import app as appmod
    monkeypatch.setattr(appmod.requests, 'request', lambda *a, **k: R())
    r = _call(ctx, 'GET', VOICE_PATH)
    assert r.status_code == 502 and r.get_json() == {'error': 'تعذّر تشغيل الرسالة'}
    assert b'script' not in r.data


def test_voice_proxy_refuses_an_empty_or_oversized_body(ctx, plat, monkeypatch):
    import app as appmod
    for body in (b'', b'x' * (appmod._EF_VOICE_MAX_BYTES + 1)):
        class R(object):
            status_code = 200
            content = body
            headers = {'Content-Type': 'audio/webm'}
        monkeypatch.setattr(appmod.requests, 'request', lambda *a, **k: R())
        assert _call(ctx, 'GET', VOICE_PATH).status_code == 502


def test_voice_proxy_of_a_file_without_voice_is_the_platforms_arabic_404(ctx, plat):
    r = _call(ctx, 'GET', '/api/platform-expert-files/%s/voice' % fx.R2['id'])    # ملف قديم من غير صوت
    assert r.status_code == 404 and r.get_json() == {'error': fx.E_NOT_FOUND}
    assert len(plat.seen) == 1


def test_voice_proxy_when_the_bridge_is_not_published_says_so(ctx, plat):
    plat.forced[('GET', '/api/bridge/expert-files/%s/voice' % RID)] = (404, {'detail': 'Not Found'})
    r = _call(ctx, 'GET', VOICE_PATH)
    assert r.status_code == 404 and r.get_json() == {'error': 'ملفات «ملف للخبير» مش واصلة للداشبورد لسه'}


@pytest.mark.parametrize('status', [500, 502, 503])
def test_voice_proxy_maps_a_platform_crash_to_502_without_a_retry(ctx, plat, status):
    plat.forced[('GET', '/api/bridge/expert-files/%s/voice' % RID)] = (status, {'detail': 'boom'})
    r = _call(ctx, 'GET', VOICE_PATH)
    assert r.status_code == 502
    assert len(plat.seen) == 1                                                # ⛔ ولا إعادة محاولة


def test_voice_proxy_connection_failure_is_502_in_arabic(ctx, plat):
    plat.forced[('GET', '/api/bridge/expert-files/%s/voice' % RID)] = _requests.Timeout('slow')
    r = _call(ctx, 'GET', VOICE_PATH)
    assert r.status_code == 502 and r.get_json() == {'error': 'تعذر الاتصال بالمنصة'}


def test_voice_proxy_without_the_secret_never_calls_the_platform(ctx, plat, monkeypatch):
    import app as appmod
    monkeypatch.setattr(appmod, 'PLATFORM_METRICS_SECRET', '')
    r = _call(ctx, 'GET', VOICE_PATH)
    assert r.status_code == 503 and plat.seen == []


@pytest.mark.parametrize('bad', ['x' * 65, 'a.b', 'a b', 'ملف'])
def test_voice_proxy_validates_the_id_first(ctx, plat, bad):
    r = _call(ctx, 'GET', '/api/platform-expert-files/%s/voice' % bad)
    assert r.status_code == 404 and plat.seen == []


def test_detail_carries_the_voice_card_with_three_keys_only(ctx, plat):
    body = _call(ctx, 'GET', '/api/platform-expert-files/' + RID).get_json()
    assert body['voice'] == fx.VOICE_META
    assert sorted(body['voice']) == ['content_type', 'duration_sec', 'size']
    old = _call(ctx, 'GET', '/api/platform-expert-files/' + fx.R2['id']).get_json()
    assert old['voice'] is None                                               # الملف القديم: ولا مشغّل


@pytest.mark.parametrize('voice', [None, 'x', [], {}, {'duration_sec': 5},
                                   {'duration_sec': 'ab', 'size': 9, 'content_type': 'audio/webm'},
                                   {'duration_sec': True, 'size': 9, 'content_type': 'audio/webm'},
                                   {'duration_sec': 60, 'size': 9, 'content_type': 'text/html'}])
def test_detail_drops_a_malformed_voice_instead_of_passing_it_on(ctx, plat, monkeypatch, voice):
    rid = fx.R2['id']
    monkeypatch.setitem(fx.REVIEW_DETAIL, rid, dict(fx.REVIEW_DETAIL[rid], voice=voice))
    assert _call(ctx, 'GET', '/api/platform-expert-files/' + rid).get_json()['voice'] is None


def test_detail_never_carries_voice_bytes_or_extra_keys(ctx, plat, monkeypatch):
    monkeypatch.setattr(fx, 'VOICE_META', dict(fx.VOICE_META, data_b64='AAAA', expert_email='rana@experts.test'))
    body = _call(ctx, 'GET', '/api/platform-expert-files/' + RID).get_json()
    assert sorted(body['voice']) == ['content_type', 'duration_sec', 'size']
    raw = json.dumps(body)
    assert 'data_b64' not in raw and 'AAAA' not in raw
