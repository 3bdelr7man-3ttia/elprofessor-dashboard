# -*- coding: utf-8 -*-
"""مسارات «السوق v4» في الداشبورد (docs/v2/market4/SPEC.md): اقتراحات «أخرى» · مدى الأسعار · المكاتب · ملف الترخيص · بلاد القيد عند قبول الانضمام ·
سلّم السوق في جدول النسب · الطلبات المفتوحة (المسار الموجود). الجسور على المنصة بديل في الذاكرة.

Run:  cd backend && python3 -B -m pytest -q -p no:cacheprovider tests/test_market4_routes.py

⛔ صفر شبكة حقيقية وصفر نداء حقيقي: المنصة في الذاكرة (`uiharness/m4_fixtures.Market4Platform`)، وأي عنوان برّه `https://platform.test` بيوقّع الاختبار.

اللي بيثبّته:
  ١. أدمن بس (ملف الترخيص: أدمن وموظف) · المفتاح مقفول ٤٠٤ بلا أي نداء · `no-store` على كل رد · السرّ يطلع مع كل نداء.
  ٢. كل كتابة تطلب `confirmed:true` بالظبط (قبل أي نداء) · `by` من التوكن وحده · قايمة بيضا للحقول والردود · تدقيق عند النجاح بس.
  ٣. التحقق من المدى قبل أي نداء (أعداد صحيحة · الأدنى < الأعلى · زوج كامل · العملات السبع · المسح بـnull) · رسائل المنصة العربية (٤٠٤ ٤٠٩ ٤٢٢) تعدّي كما هي.
  ٤. رد ضايع (٥٠٤) على كتابة ⇒ ٥٠٢ و`no_reply` · مصدر غاب (٤٠٤) على قراءة ⇒ `bridge_missing`.
  ٥. ملف الترخيص بايتات: النوع من البايتات (لا HTML متنكّر) · رؤوس الأمان · معرّف الملف بنمط صارم.
  ٦. قبول الانضمام: `licensed_countries` تتنضّف وتتبعت عند «اعتمد» وحدها، وبلد غلط ⇒ ٤٠٠ بلا نداء.
  ٧. جدول النسب: سلّم السوق يتحقق شكله وأرضيته (٢٥) قبل ما يطلع، والمنصة تعيد الفحص.
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
import m4_fixtures as m4fx   # noqa: E402

ROOT = os.path.dirname(os.path.dirname(_HERE))
PLATFORM = 'https://platform.test'
SECRET = 'test-metrics-secret'
NON_ADMIN_ROLES = ['employee', 'trainer', 'investor', 'viewer', 'pending']
ADMIN_EMAIL = 'v2m4-admin@x.test'
CONFIRM_AR = 'لازم تأكّد الأول من الشاشة'
NO_REPLY_AR = 'لم يصل رد. حدّث الصفحة وتأكّد مما حدث قبل أن تضغط مرة أخرى.'
FILE = '/api/v2/market/licence-files/' + m4fx.LICENCE_FILE_ID


def _read(*parts):
    with open(os.path.join(ROOT, *parts), encoding='utf-8') as fh:
        return fh.read()


class _Resp(object):
    def __init__(self, status, payload):
        self.status_code = status
        self._p = payload
        if isinstance(payload, tuple):
            self.content = payload[0]
            self.headers = {'Content-Type': payload[1]}
        else:
            self.content = json.dumps(payload, ensure_ascii=False).encode('utf-8') if payload is not None else b''
            self.headers = {'Content-Type': 'application/json'}

    def json(self):
        if isinstance(self._p, tuple):
            raise ValueError('bytes')
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
        heads = {r: _bearer(_mkuser('v2m4-%s@x.test' % r, r)) for r in NON_ADMIN_ROLES}
        heads['admin'] = _bearer(_mkuser(ADMIN_EMAIL, 'admin'))
        yield {'heads': heads, 'client': flask_app.test_client()}


class Plat(object):
    def __init__(self):
        self.ef = m4fx.Market4Platform()
        self.seen = []
        self.blocked = []

    def __call__(self, method, url, params=None, json=None, headers=None, timeout=None, data=None, files=None):
        self.seen.append({'method': method.upper(), 'url': url, 'path': url[len(PLATFORM):], 'params': dict(params or {}), 'headers': dict(headers or {}),
                          'json': copy.deepcopy(json), 'timeout': timeout})
        if not url.startswith(PLATFORM + '/'):
            self.blocked.append(url)
            raise RuntimeError('طلب حقيقي ممنوع: ' + url)
        out = self.ef.handle(method, url[len(PLATFORM):], params or {}, json or {})
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


def _call(ctx, method, path, body=None, role='admin'):
    kw = {'headers': ctx['heads'][role] if role else {}}
    if body is not None:
        kw['json'] = body
    return ctx['client'].open(path, method=method, **kw)


def _audits(prefix):
    with flask_app.app_context():
        return [(a.action, a.target, json.loads(a.meta_json or 'null'), a.actor_email) for a in AuditLog.query.filter(AuditLog.action.like(prefix + '%')).order_by(AuditLog.id).all()]


SUG = '/api/v2/market/suggestions'
CAT = '/api/v2/market/catalog'
ORG = '/api/v2/market/orgs'
READS = [SUG, CAT, ORG]
WRITES = [('POST', SUG + '/sg-1/decide', {'decision': 'reject', 'confirmed': True}),
          ('PUT', CAT + '/contract-draft/anchor', {'anchor_range': {'EGP': [1000, 2000]}, 'confirmed': True}),
          ('POST', ORG + '/org-1/verify-reg', {'confirmed': True})]


# ---------------------------------------------------------------- ١) الأدوار والمفتاح و no-store

@pytest.mark.parametrize('role', NON_ADMIN_ROLES)
def test_every_route_is_admin_only(ctx, plat, role):
    for path in READS:
        assert _call(ctx, 'GET', path, role=role).status_code == 403, (role, path)
    for m, path, body in WRITES:
        assert _call(ctx, 'POST' if m == 'POST' else 'PUT', path, body, role=role).status_code == 403, (role, path)
    for path in READS:
        assert _call(ctx, 'GET', path, role=None).status_code == 401
    assert plat.seen == []


def test_licence_file_is_for_admin_and_employee_only(ctx, plat):
    assert _call(ctx, 'GET', FILE, role='admin').status_code == 200
    assert _call(ctx, 'GET', FILE, role='employee').status_code == 200
    for role in ('trainer', 'investor', 'viewer', 'pending'):
        assert _call(ctx, 'GET', FILE, role=role).status_code == 403
    assert _call(ctx, 'GET', FILE, role=None).status_code == 401


def test_every_route_is_closed_when_the_switch_is_off_with_no_platform_call(ctx, plat, monkeypatch):
    monkeypatch.delenv('DASH_V2_ENABLED', raising=False)
    for path in READS + [FILE]:
        assert _call(ctx, 'GET', path).status_code == 404, path
    for m, path, body in WRITES:
        assert _call(ctx, m, path, body).status_code == 404, path
    assert plat.seen == []


def test_every_reply_is_no_store_and_the_secret_goes_out(ctx, plat):
    rs = [_call(ctx, 'GET', p) for p in READS + [FILE]] + [_call(ctx, m, p, b) for m, p, b in WRITES] + [_call(ctx, 'GET', SUG + '?status=zzz')]
    assert all(r.headers.get('Cache-Control') == 'no-store' for r in rs), [r.headers.get('Cache-Control') for r in rs]
    assert plat.seen and all(c['headers'].get('X-ELP-Metrics-Secret') == SECRET for c in plat.seen)


# ---------------------------------------------------------------- ٢) اقتراحات «أخرى»

def test_suggestions_list_forwards_a_clean_status_and_whitelists_the_fields(ctx, plat):
    plat.ef.suggestions[0]['internal_secret'] = 'x'
    d = _call(ctx, 'GET', SUG).get_json()
    assert plat.calls('/api/bridge/market/suggestions')[0]['params'] == {'status': 'pending', 'limit': 100}
    assert d['pending'] == 4 and len(d['items']) == 4 and 'internal_secret' not in d['items'][0]
    assert set(d['items'][0]) <= {'id', 'user_email', 'org_id', 'name', 'note', 'status', 'created_slug', 'decided_by', 'decided_at', 'created_at'}
    _call(ctx, 'GET', SUG + '?status=all')
    assert plat.calls('/api/bridge/market/suggestions')[-1]['params']['status'] == 'all'
    _call(ctx, 'GET', SUG + '?status=%3Bdrop')
    assert plat.calls('/api/bridge/market/suggestions')[-1]['params']['status'] == 'pending'


def test_a_read_that_the_platform_does_not_have_yet_says_bridge_missing(ctx, plat):
    plat.ef.m4_missing.add('/api/bridge/market/orgs')
    r = _call(ctx, 'GET', ORG)
    assert r.status_code == 404 and r.get_json()['bridge_missing'] is True and 'غير متاح' in r.get_json()['error']
    plat.ef.down.add('/api/bridge/market/catalog')
    assert _call(ctx, 'GET', CAT).status_code == 502


@pytest.mark.parametrize('method,path,body', WRITES)
def test_a_write_needs_an_exact_true_confirmation_before_any_call(ctx, plat, method, path, body):
    for bad in (None, False, 'true', 1, 'yes'):
        b = dict(body)
        if bad is None:
            b.pop('confirmed')
        else:
            b['confirmed'] = bad
        r = _call(ctx, method, path, b)
        assert r.status_code == 400 and CONFIRM_AR in r.get_json()['error'], (bad, r.get_json())
    assert plat.writes() == []


def test_approve_sends_the_three_choices_and_by_from_the_token_only(ctx, plat):
    r = _call(ctx, 'POST', SUG + '/sg-1/decide', {'decision': 'approve', 'service_type': 'memo', 'specialty': 'civil', 'scope': ' ترجمة ومراجعة ',
                                                    'by': 'attacker@evil.test', 'confirmed': True, 'status': 'approved', 'created_slug': 'x'})
    assert r.status_code == 200 and r.get_json()['claimed'] is True and r.get_json()['slug'].startswith('svc-')
    w = plat.writes()
    assert len(w) == 1 and w[0]['path'] == '/api/bridge/market/suggestions/sg-1/decide'
    assert w[0]['json'] == {'decision': 'approve', 'service_type': 'memo', 'specialty': 'civil', 'scope': 'ترجمة ومراجعة', 'by': ADMIN_EMAIL}
    a = _audits('market4.suggestion_approve')[-1]
    assert a[1] == 'sg-1' and a[2] == {'decision': 'approve', 'service_type': 'memo', 'specialty': 'civil'} and a[3] == ADMIN_EMAIL


def test_approve_with_other_everywhere_sends_empty_so_the_platform_uses_its_defaults(ctx, plat):
    r = _call(ctx, 'POST', SUG + '/sg-2/decide', {'decision': 'approve', 'service_type': '', 'specialty': '', 'scope': '', 'confirmed': True})
    assert r.status_code == 200
    assert plat.writes()[0]['json'] == {'decision': 'approve', 'service_type': '', 'specialty': '', 'scope': '', 'by': ADMIN_EMAIL}
    assert any(row['slug'] == r.get_json()['slug'] and row['service_type'] == 'written_opinion' and row['specialty'] == 'general' for row in plat.ef.catalog)
    assert _audits('market4.suggestion_approve')[-1][2]['service_type'] == 'default'


def test_reject_sends_the_decision_alone(ctx, plat):
    r = _call(ctx, 'POST', SUG + '/sg-3/decide', {'decision': 'reject', 'service_type': 'memo', 'scope': 'x', 'reason': 'x', 'confirmed': True})
    assert r.status_code == 200 and r.get_json()['status'] == 'rejected'
    assert plat.writes()[0]['json'] == {'decision': 'reject', 'by': ADMIN_EMAIL}
    assert _audits('market4.suggestion_reject')[-1][1] == 'sg-3'


def test_decide_validates_before_any_call(ctx, plat):
    for body in ({'decision': 'maybe'}, {}, {'decision': 'approve', 'service_type': 'Bad Type!'}, {'decision': 'approve', 'specialty': 'ا' * 3},
                 {'decision': 'approve', 'scope': 'x' * 601}, {'decision': 'approve', 'service_type': ['memo']}):
        r = _call(ctx, 'POST', SUG + '/sg-1/decide', dict(body, confirmed=True))
        assert r.status_code == 400 and r.get_json()['error'], body
    assert _call(ctx, 'POST', SUG + '/a%20b/decide', {'decision': 'reject', 'confirmed': True}).status_code in (400, 404)
    assert plat.writes() == []


def test_decide_platform_texts_pass_through_with_their_codes_and_only_success_is_audited(ctx, plat):
    n0 = len(_audits('market4.suggestion_'))
    r = _call(ctx, 'POST', SUG + '/sg-nope/decide', {'decision': 'reject', 'confirmed': True})
    assert r.status_code == 404 and 'الاقتراح مش موجود' in r.get_json()['error']
    r = _call(ctx, 'POST', SUG + '/sg-5/decide', {'decision': 'reject', 'confirmed': True})
    assert r.status_code == 409 and 'اتقرّر' in r.get_json()['error']
    r = _call(ctx, 'POST', SUG + '/sg-1/decide', {'decision': 'approve', 'service_type': 'not_a_type', 'confirmed': True})
    assert r.status_code == 422 and 'غير معروف' in r.get_json()['error']
    assert len(_audits('market4.suggestion_')) == n0


def test_a_lost_reply_says_no_reply_and_is_audited_as_an_attempt_not_as_done(ctx, plat):
    plat.ef.forced[('POST', '/api/bridge/market/suggestions/sg-4/decide')] = (504, {'detail': 'x'})
    n0 = len(_audits('market4.suggestion_'))
    r = _call(ctx, 'POST', SUG + '/sg-4/decide', {'decision': 'reject', 'confirmed': True})
    assert r.status_code == 502 and r.get_json() == {'error': NO_REPLY_AR, 'no_reply': True}
    assert len(_audits('market4.suggestion_')) == n0 and _audits('market4.no_reply')[-1][2] == {'attempt': 'market4.suggestion_reject'}
    assert len(plat.writes()) == 1, 'بلا إعادة محاولة'


# ---------------------------------------------------------------- ٣) مدى الأسعار

def test_catalog_forwards_the_filter_and_the_search_and_whitelists(ctx, plat):
    d = _call(ctx, 'GET', CAT + '?no_range=1&q=' + 'عقد').get_json()
    c = plat.calls('/api/bridge/market/catalog')[0]
    assert c['params'] == {'limit': 300, 'no_range': '1', 'q': 'عقد'}
    assert [i['slug'] for i in d['items']] == ['contract-draft'] and d['no_range_count'] == 9 and d['currencies'] == m4fx.CURRENCIES
    _call(ctx, 'GET', CAT + '?q=' + 'x' * 400)
    assert len(plat.calls('/api/bridge/market/catalog')[-1]['params']['q']) == 120
    _call(ctx, 'GET', CAT + '?no_range=0')
    assert 'no_range' not in plat.calls('/api/bridge/market/catalog')[-1]['params']


def test_catalog_drops_fields_and_currencies_it_does_not_know(ctx, plat):
    plat.ef.catalog[1]['anchor_range']['XXX'] = [1, 2]
    plat.ef.catalog[1]['seed_note'] = 'internal'
    row = [i for i in _call(ctx, 'GET', CAT).get_json()['items'] if i['slug'] == 'contract-review'][0]
    assert 'seed_note' not in row and sorted(row['anchor_range']) == ['EGP', 'SAR', 'USD']


GOOD = {'EGP': [2500, 6000], 'SAR': [400, 1100], 'AED': None}


def test_anchor_sends_only_filled_currencies_with_by_from_the_token(ctx, plat):
    r = _call(ctx, 'PUT', CAT + '/contract-draft/anchor', {'anchor_range': dict(GOOD, egp=None), 'by': 'x@evil.test', 'confirmed': True})
    assert r.status_code == 200 and r.get_json()['anchor_range'] == {'EGP': [2500, 6000], 'SAR': [400, 1100]}
    assert plat.writes()[0]['json'] == {'anchor_range': {'EGP': [2500, 6000], 'SAR': [400, 1100]}, 'by': ADMIN_EMAIL}
    assert _audits('market4.anchor')[-1][2] == {'currencies': ['EGP', 'SAR'], 'cleared': False}
    r = _call(ctx, 'PUT', CAT + '/contract-draft/anchor', {'anchor_range': {'USD': [20.0, 90.0]}, 'confirmed': True})
    assert r.status_code == 200 and plat.writes()[-1]['json']['anchor_range'] == {'USD': [20, 90]}


def test_anchor_null_clears_and_an_empty_dict_clears_too(ctx, plat):
    assert _call(ctx, 'PUT', CAT + '/contract-review/anchor', {'anchor_range': None, 'confirmed': True}).get_json()['anchor_range'] is None
    assert plat.writes()[-1]['json'] == {'anchor_range': None, 'by': ADMIN_EMAIL}
    assert _audits('market4.anchor')[-1][2] == {'currencies': [], 'cleared': True}
    assert _call(ctx, 'PUT', CAT + '/thesis-review/anchor', {'anchor_range': {'EGP': None}, 'confirmed': True}).status_code == 200
    assert plat.writes()[-1]['json']['anchor_range'] is None


@pytest.mark.parametrize('rng,why', [
    ({'EGP': [100, 100]}, 'الأدنى = الأعلى'), ({'EGP': [900, 100]}, 'الأدنى > الأعلى'), ({'EGP': [-5, 100]}, 'سالب'), ({'EGP': [1.5, 9]}, 'كسر'),
    ({'EGP': [True, 9]}, 'منطقي'), ({'EGP': ['100', '900']}, 'نص'), ({'EGP': [100]}, 'ناقص'), ({'EGP': [100, None]}, 'نصف زوج'), ({'EGP': [None, 100]}, 'نصف زوج'),
    ({'EGP': [1, 2, 3]}, 'ثلاثة'), ({'GBP': [1, 9]}, 'عملة غريبة'), ({'EGP': 'x'}, 'ليست قائمة'), ('EGP', 'ليس قاموسًا'), ([1, 2], 'قائمة'), ({'EGP': [1, 10 ** 12]}, 'ضخم'),
])
def test_anchor_is_validated_before_any_call(ctx, plat, rng, why):
    r = _call(ctx, 'PUT', CAT + '/contract-draft/anchor', {'anchor_range': rng, 'confirmed': True})
    assert r.status_code == 422 and r.get_json()['error'], why
    assert plat.writes() == []


def test_anchor_range_must_be_present_even_to_clear(ctx, plat):
    r = _call(ctx, 'PUT', CAT + '/contract-draft/anchor', {'confirmed': True})
    assert r.status_code == 400 and 'مطلوب' in r.get_json()['error'] and plat.writes() == []


def test_anchor_platform_refusals_keep_their_arabic_text_and_codes(ctx, plat):
    r = _call(ctx, 'PUT', CAT + '/family-opinion/anchor', {'anchor_range': {'EGP': [1, 2]}, 'confirmed': True})
    assert r.status_code == 409 and 'مالهاش مدى' in r.get_json()['error']
    r = _call(ctx, 'PUT', CAT + '/no-such-service/anchor', {'anchor_range': {'EGP': [1, 2]}, 'confirmed': True})
    assert r.status_code == 404 and 'مش في الكتالوج' in r.get_json()['error']
    plat.ef.forced[('PUT', '/api/bridge/market/catalog/legal-research/anchor')] = (422, {'detail': {'message': 'EGP: الأدنى لازم يكون أقل من الأعلى'}})
    r = _call(ctx, 'PUT', CAT + '/legal-research/anchor', {'anchor_range': {'EGP': [1, 2]}, 'confirmed': True})
    assert r.status_code == 422 and 'EGP' in r.get_json()['error']
    assert _audits('market4.anchor') == [] or all(a[1] != 'family-opinion' for a in _audits('market4.anchor'))
    assert _call(ctx, 'PUT', CAT + '/a%2Fb/anchor', {'anchor_range': None, 'confirmed': True}).status_code in (400, 404, 405)
    assert _call(ctx, 'PUT', CAT + '/-bad/anchor', {'anchor_range': None, 'confirmed': True}).status_code == 400


def test_anchor_lost_reply_is_no_reply(ctx, plat):
    plat.ef.forced[('PUT', '/api/bridge/market/catalog/legal-research/anchor')] = (502, {'detail': 'x'})
    r = _call(ctx, 'PUT', CAT + '/legal-research/anchor', {'anchor_range': {'EGP': [1, 2]}, 'confirmed': True})
    assert r.status_code == 502 and r.get_json()['no_reply'] is True and len(plat.writes()) == 1


# ---------------------------------------------------------------- ٤) المكاتب

def test_orgs_list_whitelists_and_drops_unsafe_links(ctx, plat):
    plat.ef.orgs[0]['commercial_reg']['url'] = 'javascript:alert(1)'
    plat.ef.orgs[0]['private_note'] = 'x'
    d = _call(ctx, 'GET', ORG).get_json()
    assert plat.calls('/api/bridge/market/orgs')[0]['params'] == {'status': 'pending'}
    assert [o['id'] for o in d['items']] == ['org-1', 'org-2', 'org-3'] and d['total'] == 3
    o1, o2, o3 = d['items']
    assert o1['commercial_reg']['url'] == '' and 'private_note' not in o1
    assert o2['commercial_reg']['url'].startswith('https://') and len(o2['members']) == 2 and o2['members'][0]['verified_lawyer'] is True
    assert o3['commercial_reg'] is None
    assert [o['id'] for o in _call(ctx, 'GET', ORG + '?status=all').get_json()['items']] == ['org-1', 'org-2', 'org-3', 'org-4']
    assert plat.calls('/api/bridge/market/orgs')[-1]['params'] == {'status': 'all'}
    _call(ctx, 'GET', ORG + '?status=bogus')
    assert plat.calls('/api/bridge/market/orgs')[-1]['params'] == {'status': 'pending'}


def test_verify_reg_sends_by_only_and_audits_only_on_success(ctx, plat):
    r = _call(ctx, 'POST', ORG + '/org-2/verify-reg', {'confirmed': True, 'by': 'x', 'status': 'active'})
    assert r.status_code == 200 and r.get_json()['already'] is False and r.get_json()['status'] == 'active'
    assert plat.writes()[0]['json'] == {'by': ADMIN_EMAIL}
    assert _audits('market4.verify_reg')[-1][1] == 'org-2'
    again = _call(ctx, 'POST', ORG + '/org-2/verify-reg', {'confirmed': True})
    assert again.status_code == 200 and again.get_json()['already'] is True
    n = len(_audits('market4.verify_reg'))
    r = _call(ctx, 'POST', ORG + '/org-3/verify-reg', {'confirmed': True})
    assert r.status_code == 422 and 'لم يرفع سجله' in r.get_json()['error']
    assert _call(ctx, 'POST', ORG + '/nope/verify-reg', {'confirmed': True}).status_code == 404
    assert len(_audits('market4.verify_reg')) == n


def test_verify_reg_lost_reply(ctx, plat):
    plat.ef.forced[('POST', '/api/bridge/market/orgs/org-1/verify-reg')] = (503, {'detail': 'x'})
    r = _call(ctx, 'POST', ORG + '/org-1/verify-reg', {'confirmed': True})
    assert r.status_code == 502 and r.get_json()['no_reply'] is True


# ---------------------------------------------------------------- ٥) ملف الترخيص

def test_licence_file_streams_the_bytes_with_safe_headers_and_audits(ctx, plat):
    r = _call(ctx, 'GET', FILE)
    assert r.status_code == 200 and r.mimetype == 'image/png' and r.data == plat.ef.file_png
    h = r.headers
    assert h['Cache-Control'] == 'no-store' and h['X-Content-Type-Options'] == 'nosniff' and h['Content-Security-Policy'] == "default-src 'none'; sandbox"
    c = plat.calls('/api/bridge/market/licence-files/')[0]
    assert c['path'].endswith(m4fx.LICENCE_FILE_ID) and c['headers']['X-ELP-Metrics-Secret'] == SECRET
    a = _audits('market4.licence_file_view')[-1]
    assert a[1] == m4fx.LICENCE_FILE_ID and a[2]['type'] == 'image/png'


def test_licence_file_type_comes_from_the_bytes_not_from_the_header(ctx, plat):
    plat.ef.file_png = b'<html><script>alert(1)</script></html>'
    r = _call(ctx, 'GET', FILE)
    assert r.status_code == 422 and r.mimetype == 'application/json'
    for ok, kind in ((b'%PDF-1.4\n%x', 'application/pdf'), (b'\xff\xd8\xff\xe0abc', 'image/jpeg'), (b'RIFF\x00\x00\x00\x00WEBPVP8 ', 'image/webp')):
        plat.ef.file_png = ok
        r = _call(ctx, 'GET', FILE)
        assert r.status_code == 200 and r.mimetype == kind, kind
    plat.ef.file_png = b''
    assert _call(ctx, 'GET', FILE).status_code == 422


def test_licence_file_missing_and_bad_ids(ctx, plat):
    plat.ef.file_missing = True
    r = _call(ctx, 'GET', FILE)
    assert r.status_code == 404 and 'غير متاح' in r.get_json()['error']
    n = len(plat.seen)
    for bad in ('a', 'x' * 80, 'a b c d e f g h', 'a..b..c..d..e', 'a.b.c.d.e.f.g.h'):
        assert _call(ctx, 'GET', '/api/v2/market/licence-files/' + bad).status_code in (400, 404), bad
    assert len(plat.seen) == n, 'المعرّف الغلط ما يوصلش للمنصة'
    plat.ef.down.add('/api/bridge/market/licence-files/' + m4fx.LICENCE_FILE_ID)
    plat.ef.file_missing = False
    assert _call(ctx, 'GET', FILE).status_code == 502


# ---------------------------------------------------------------- ٦) قبول الانضمام ببلاد القيد

JOIN = '/api/platform-join-requests/jr-lic-1/approve'


def test_approve_forwards_clean_deduped_uppercase_countries(ctx, plat):
    r = _call(ctx, 'POST', JOIN, {'admin_note': '', 'licensed_countries': ['sa', 'EG', 'SA', ' xx ']})
    assert r.status_code == 200
    w = plat.writes()
    assert len(w) == 1 and w[0]['path'] == '/api/bridge/join-requests/jr-lic-1/decide'
    assert w[0]['json'] == {'decision': 'approve', 'admin_note': '', 'licensed_countries': ['SA', 'EG', 'XX']}
    assert _audits('join_request.approve')[-1][2]['licensed_countries'] == ['SA', 'EG', 'XX']


def test_approve_without_countries_behaves_as_before(ctx, plat):
    assert _call(ctx, 'POST', '/api/platform-join-requests/jr-plain/approve', {'admin_note': ''}).status_code == 200
    assert plat.writes()[0]['json'] == {'decision': 'approve', 'admin_note': ''}
    assert 'licensed_countries' not in _audits('join_request.approve')[-1][2]


@pytest.mark.parametrize('bad', ['SA', 'SAU', [1], ['S'], ['SA', 'E1'], [['SA']], ['A' * 5], [None], list('ABCDEFGHIJKLM')])
def test_bad_countries_are_refused_before_any_call(ctx, plat, bad):
    r = _call(ctx, 'POST', JOIN, {'admin_note': '', 'licensed_countries': bad})
    assert r.status_code == 400 and r.get_json()['error']
    assert plat.writes() == []


def test_countries_are_not_sent_on_reject_or_request_info(ctx, plat):
    assert _call(ctx, 'POST', JOIN.replace('approve', 'reject'), {'admin_note': 'السبب', 'licensed_countries': ['SA']}).status_code == 200
    assert 'licensed_countries' not in plat.writes()[0]['json']
    assert _call(ctx, 'POST', '/api/platform-join-requests/jr-lic-2/request_info', {'admin_note': 'ابعت الكارنيه', 'licensed_countries': ['SA']}).status_code == 200
    assert 'licensed_countries' not in plat.writes()[1]['json']


def test_a_country_the_platform_does_not_know_keeps_the_row_open_with_its_text(ctx, plat):
    r = _call(ctx, 'POST', JOIN, {'admin_note': '', 'licensed_countries': ['ZZ']})
    assert r.status_code == 422 and 'بلد القيد غير مفهوم' in r.get_json()['error']
    assert any(j['id'] == 'jr-lic-1' for j in plat.ef.joins), 'ما اتمنحش'
    assert [a for a in _audits('join_request.approve') if a[1] == 'jr-lic-1' and a[2].get('licensed_countries') == ['ZZ']] == []


# ---------------------------------------------------------------- ٧) جدول النسب: سلّم السوق

SH = '/api/v2/shares'


def _ladder(**over):
    egp = [{'max': 10000, 'platform_pct': 35}, {'max': 30000, 'platform_pct': 30}, {'max': None, 'platform_pct': 25}]
    egp = over.get('EGP', egp)
    return {'market': {'ladder_by_currency': {'EGP': egp}}}


def test_shares_read_carries_the_market_ladder_and_the_floor(ctx, plat):
    d = _call(ctx, 'GET', SH).get_json()
    assert d['shares']['market']['ladder_by_currency']['EGP'][0] == {'max': 10000, 'platform_pct': 35} and d['shares']['case_floor'] == 25


def test_market_ladder_edit_goes_through_with_the_version_and_the_floor_holds(ctx, plat):
    ver = _call(ctx, 'GET', SH).get_json()['version']
    new = [{'max': 12000, 'platform_pct': 35}, {'max': 30000, 'platform_pct': 28}, {'max': None, 'platform_pct': 25}]
    r = _call(ctx, 'PUT', SH, {'changes': _ladder(EGP=new), 'version': ver, 'confirmed': True})
    assert r.status_code == 200 and r.get_json()['shares']['market']['ladder_by_currency']['EGP'] == new
    assert plat.writes()[0]['json']['changes'] == _ladder(EGP=new) and plat.writes()[0]['json']['version'] == ver
    assert r.get_json()['shares']['market']['ladder_by_currency']['SAR'][0]['max'] == 750, 'العملات التانية ما اتلمستش'
    assert r.get_json()['history'][0]['before']['market']['ladder_by_currency']['EGP'][0]['max'] == 10000


@pytest.mark.parametrize('egp,why', [
    ([{'max': 10000, 'platform_pct': 24}, {'max': None, 'platform_pct': 25}], 'تحت الأرضية'),
    ([{'max': 10000, 'platform_pct': 35}, {'max': None, 'platform_pct': 10}], 'الأخيرة تحت الأرضية'),
    ([{'max': 10000, 'platform_pct': 35}, {'max': 5000, 'platform_pct': 30}, {'max': None, 'platform_pct': 25}], 'حدود لا تزيد'),
    ([{'max': 10000, 'platform_pct': 35}, {'max': 20000, 'platform_pct': 30}], 'آخر درجة بسقف'),
    ([{'max': None, 'platform_pct': 35}, {'max': None, 'platform_pct': 25}], 'سقف ناقص في الوسط'),
    ([{'max': 10000, 'platform_pct': '35'}, {'max': None, 'platform_pct': 25}], 'نسبة نص'),
    ([{'max': 10000, 'platform_pct': 101}, {'max': None, 'platform_pct': 25}], 'فوق ١٠٠'),
    ([{'max': 10000, 'platform_pct': True}, {'max': None, 'platform_pct': 25}], 'منطقي'),
    ([{'max': 10000, 'platform_pct': 35, 'extra': 1}, {'max': None, 'platform_pct': 25}], 'مفتاح زيادة'),
    ([], 'فاضي'), ('x', 'ليس قائمة'),
])
def test_a_broken_market_ladder_never_leaves_the_dashboard(ctx, plat, egp, why):
    r = _call(ctx, 'PUT', SH, {'changes': _ladder(EGP=egp), 'version': 3, 'confirmed': True})
    assert r.status_code == 400 and r.get_json()['error'], why
    assert plat.writes() == []


def test_market_shape_errors_other_than_the_ladder(ctx, plat):
    for ch in ({'market': {}}, {'market': {'ladder_by_currency': {}}}, {'market': {'ladder_by_currency': {'GBP': [{'max': None, 'platform_pct': 30}]}}},
               {'market': {'ladder_by_currency': {'EGP': [{'max': None, 'platform_pct': 30}]}, 'other': 1}}, {'market': 'x'}):
        r = _call(ctx, 'PUT', SH, {'changes': ch, 'version': 3, 'confirmed': True})
        assert r.status_code == 400, ch
    assert plat.writes() == []


def test_the_platform_floor_message_still_reaches_the_screen(ctx, plat):
    plat.ef.forced[('PUT', '/api/bridge/shares')] = (422, {'detail': 'نصيب المنصّة في السوق ما ينزلش عن 25٪'})
    ver = 3
    r = _call(ctx, 'PUT', SH, {'changes': _ladder(), 'version': ver, 'confirmed': True})
    assert r.status_code == 422 and 'ما ينزلش عن 25' in r.get_json()['error']


def test_old_share_edits_are_untouched(ctx, plat):
    ver = _call(ctx, 'GET', SH).get_json()['version']
    r = _call(ctx, 'PUT', SH, {'changes': {'affiliate': {'rate': 12}}, 'version': ver, 'confirmed': True})
    assert r.status_code == 200 and plat.writes()[0]['json']['changes'] == {'affiliate': {'rate': 12}}


# ---------------------------------------------------------------- ٨) الطلبات المفتوحة: المسار الموجود بحقوله الجديدة

def test_open_requests_come_from_the_existing_route_with_the_v4_fields(ctx, plat):
    d = _call(ctx, 'GET', '/api/v2/market/requests?status=open&lane=all&limit=100').get_json()
    assert plat.calls('/api/bridge/market/requests')[0]['params']['status'] == 'open'
    row = [r for r in d['items'] if r['id'] == 'mk-w9'][0]
    assert (row['service_slug'], row['service_name'], row['applicable_country'], row['offer_count'], row['attachment_count'], row['attachment_access_count']) == \
        ('company-setup', 'تأسيس شركة ذات مسؤولية محدودة', 'QA', 0, 3, 7)
    assert _call(ctx, 'GET', '/api/v2/market/requests?status=open', role='employee').status_code == 200, 'القراءة للموظف زي لوحة السوق القديمة'


# ---------------------------------------------------------------- ٩) التوصيل في app.py

def test_wiring_is_one_guarded_registration_above_the_books_line(ctx, plat):
    src = _read('backend', 'app.py')
    reg = "import v2_market4_routes as _v2s_market4; _v2s_market4.register(app, globals())"
    assert src.count(reg) == 1
    books = "__import__('v2_books_routes').register(app, globals())"
    assert src.index("import v2_market_routes as _v2s_market; _v2s_market.register(app, globals())") < src.index(reg) < src.index(books) < src.index('# ---- v2 section routes end')
    i = src.index(reg)
    assert src[i - 150:i].count('try:') == 1 and 'except Exception: logger.exception' in src[i:i + 200]
    routes = {str(r) for r in flask_app.url_map.iter_rules() if '/api/v2/market/' in str(r)}
    for p in ('/api/v2/market/suggestions', '/api/v2/market/catalog', '/api/v2/market/orgs', '/api/v2/market/licence-files/<file_id>'):
        assert p in routes, p


def test_the_module_reads_the_platform_helpers_at_call_time_and_has_no_secrets():
    src = _read('backend', 'v2_market4_routes.py')
    assert 'PLATFORM_METRICS_SECRET' in src and "g['PLATFORM_METRICS_SECRET']" in src
    assert 'requests.get(' not in src and 'urlopen' not in src
