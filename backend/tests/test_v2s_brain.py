# -*- coding: utf-8 -*-
"""الجولة الأخيرة · قسم «العقل» (القواعد وسجل اليوم · المساعدون). SPEC: docs/v2/final/SPEC-brain.md

Run:  cd backend && python3 -B -m pytest -q -p no:cacheprovider tests/test_v2s_brain.py

⛔ صفر شبكة حقيقية: المنصة جدول في الذاكرة (`uiharness/brain_fixtures.BrainPlatform`)، وأي عنوان برّه `https://platform.test` يوقّع الاختبار.
⛔ صفر نداء ذكاء مدفوع: `ai_call` و`call_anthropic` و`requests.post` لمضيفي الذكاء كلها تُستبدل بدالة ترمي — لو ناداها أي مسار هنا يفشل الاختبار.

اللي بيثبّته:
  ١. المسارات (pytest): أدمن بس · المفتاح مقفول ٤٠٤ بلا نداء للمنصة · `no-store` · قايمة بيضا بلا بيانات عميل ولا مبالغ ·
     الفاشل `null` لا `[]` · ٤٠١/٤٠٣ من المنصة لا يُخرج الأدمن · عدد نداءات المنصة · التأكيد الصريح · `created_by` من التوكن · التدقيق عند النجاح بس.
  ٢. المنطق (node): السجل والأعداد والاحتياط من الوارد · القواعد (مفتاح/شارة/«متوقّف») · سطر العقل بأولوياته · المساعدون · الوقت بلا منطقة · اتفاق رقم المربّع.
  ٣. ملفات: الإدخال في index.html · الموزّع مرة واحدة · Dockerfile · app.py · مسح النصوص الظاهرة.
"""
import copy
import datetime
import json
import os
import re
import sys

from urllib.parse import quote

import jwt
import pytest
from werkzeug.security import generate_password_hash

from app import app as flask_app, db, User, AuditLog  # noqa: E402

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(_HERE, 'uiharness'))
import brain_fixtures as bfx   # noqa: E402
import v2_node                 # noqa: E402

ROOT = os.path.dirname(os.path.dirname(_HERE))
PLATFORM = 'https://platform.test'
SECRET = 'test-metrics-secret'
NON_ADMIN_ROLES = ['employee', 'trainer', 'investor', 'viewer', 'pending']
needs_node = pytest.mark.skipif(not v2_node.NODE, reason='needs node')
ADMIN_EMAIL = 'v2brain-admin@x.test'
UTC = datetime.timezone.utc


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
        heads = {r: _bearer(_mkuser('v2brain-%s@x.test' % r, r)) for r in NON_ADMIN_ROLES}
        heads['admin'] = _bearer(_mkuser(ADMIN_EMAIL, 'admin'))
        yield {'heads': heads, 'client': flask_app.test_client()}


class Plat(object):
    """`requests.request` البديل: يسجّل كل نداء ويرد من `BrainPlatform`. أي عنوان برّه المنصة المزيّفة ⇒ ممنوع."""

    def __init__(self, **kw):
        self.ef = bfx.BrainPlatform(**kw)
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


def _no_ai(*a, **k):
    raise AssertionError('نداء ذكاء ممنوع في هذه الاختبارات')


@pytest.fixture
def plat(monkeypatch):
    import app as appmod
    p = Plat()
    monkeypatch.setattr(appmod, 'PLATFORM_METRICS_SECRET', SECRET)
    monkeypatch.setattr(appmod, 'PLATFORM_API_URL', PLATFORM)
    monkeypatch.setattr(appmod.requests, 'request', p)
    monkeypatch.setattr(appmod.requests, 'post', lambda url, *a, **k: _no_ai())
    for name in ('ai_call', 'call_anthropic'):
        if hasattr(appmod, name):
            monkeypatch.setattr(appmod, name, _no_ai)
    monkeypatch.setenv('DASH_V2_ENABLED', 'true')
    yield p
    assert p.blocked == [], 'طلب لسيرفر حقيقي: %r' % p.blocked


@pytest.fixture(autouse=True)
def clean_rules():
    import v2_brain_routes
    with flask_app.app_context():
        Rule = v2_brain_routes._model(db)
        Rule.query.delete()
        AuditLog.query.filter(AuditLog.action.in_(v2_brain_routes.HISTORY_ACTIONS)).delete(synchronize_session=False)
        db.session.commit()
    yield


def since_now():
    return quote(bfx.local_midnight().astimezone(UTC).isoformat(), safe='')


def get(ctx, path, role='admin', **kw):
    return ctx['client'].get(path, headers=ctx['heads'][role], **kw)


def send(ctx, method, path, body=None, role='admin'):
    return ctx['client'].open(path, method=method, headers=ctx['heads'][role], json=body)


def allkeys(o):
    out = set()
    if isinstance(o, dict):
        for k, v in o.items():
            out.add(k)
            out |= allkeys(v)
    elif isinstance(o, list):
        for v in o:
            out |= allkeys(v)
    return out


# ---------------------------------------------------------------- ١) المسارات

ENDPOINTS = [
    ('GET', '/api/v2/brain/today?since=2026-10-30T00:00:00Z', None),
    ('GET', '/api/v2/brain/rules', None),
    ('GET', '/api/v2/brain/helpers-status', None),
    ('POST', '/api/v2/brain/rules', {'text': 'لا توزّع ملفات الخليج على خبير من مصر', 'confirmed': True}),
    ('DELETE', '/api/v2/brain/rules/' + 'a' * 32, {'confirmed': True}),
]


@pytest.mark.parametrize('method,path,body', ENDPOINTS)
def test_admin_only_and_flag_closed(ctx, plat, monkeypatch, method, path, body):
    for role in NON_ADMIN_ROLES:
        r = send(ctx, method, path, body, role=role)
        assert r.status_code == 403, (role, path)
    anon = ctx['client'].open(path, method=method, json=body)
    assert anon.status_code in (401, 403)
    assert plat.seen == []
    monkeypatch.setenv('DASH_V2_ENABLED', 'false')
    r = send(ctx, method, path, body)
    assert r.status_code == 404
    assert r.headers.get('Cache-Control') == 'no-store'
    assert plat.seen == [], 'المفتاح مقفول ⇒ ولا نداء للمنصة'


@pytest.mark.parametrize('method,path,body', ENDPOINTS[:3])
def test_no_store_on_open(ctx, plat, method, path, body):
    r = send(ctx, method, path, body)
    assert r.status_code == 200
    assert r.headers.get('Cache-Control') == 'no-store'


def test_b1_shape_is_allow_list(ctx, plat):
    r = get(ctx, '/api/v2/brain/today?since=' + since_now())
    assert r.status_code == 200
    d = r.get_json()
    assert d['files_ok'] is True and d['service'] == 'open' and d['partial'] is False
    assert len(plat.calls()) == 1 and plat.seen[0]['path'] == '/api/bridge/expert-files' and plat.seen[0]['params'] == {'status': 'all'}
    es = d['entries']
    # الملفات الأربعة: A(١) B(١ — أمس مستبعد) C(١) D(٢: تلقائي ثم المؤسس) = ٥ مدخلات اليوم، ٤ منها تلقائية
    assert len(es) == 5 and sum(1 for e in es if e['by'] == 'auto') == 4
    assert all(set(e) == {'file_id', 'title', 'status', 'at', 'by', 'reason', 'why', 'to_email', 'to_name', 'pre_claim', 'current'} for e in es)
    bad = allkeys(d) & {'client_first_name', 'client_email', 'amount', 'expert_amount', 'platform_fee', 'currency', 'counterparty_name'}
    assert not bad, bad
    assert [e['at'] for e in es] == sorted([e['at'] for e in es], reverse=True)
    assert all(e['at'].endswith('+00:00') for e in es)
    by_title = {e['title']: e for e in es if e['by'] == 'auto'}
    a = by_title['عقد إيجار تجاري — بند الإخلاء']
    assert a['pre_claim'] is True and a['current'] is True and a['to_name'] and a['reason'] == 'paid'
    b = by_title['إنذار بسداد متأخرات الإيجار']
    assert b['reason'] == 'timeout' and b['to_email'] == bfx.KARIM, 'مدخل أمس خارج اليوم'
    c = by_title['نفقة زوجة بعد الانفصال']
    assert c['pre_claim'] is False and c['current'] is False
    founder = [e for e in es if e['by'] == 'founder']
    assert len(founder) == 1 and founder[0]['current'] is True and founder[0]['to_email'] == bfx.NADA


def test_b1_filter_and_since_validation(ctx, plat):
    soon = quote((datetime.datetime.now(UTC) - datetime.timedelta(seconds=1)).isoformat(), safe='')
    d = get(ctx, '/api/v2/brain/today?since=' + soon).get_json()
    assert d['files_ok'] is True and d['entries'] == []
    for bad in ('', 'nope', '2026-13-99'):
        assert get(ctx, '/api/v2/brain/today?since=' + bad).status_code == 400
    assert get(ctx, '/api/v2/brain/today').status_code == 400
    old = quote((datetime.datetime.now(UTC) - datetime.timedelta(days=60)).isoformat(), safe='')
    assert get(ctx, '/api/v2/brain/today?since=' + old).status_code == 200
    fut = quote((datetime.datetime.now(UTC) + datetime.timedelta(days=3)).isoformat(), safe='')
    assert get(ctx, '/api/v2/brain/today?since=' + fut).get_json()['entries'] == []
    z = quote(bfx.local_midnight().astimezone(UTC).strftime('%Y-%m-%dT%H:%M:%SZ'), safe='')
    assert get(ctx, '/api/v2/brain/today?since=' + z).get_json()['files_ok'] is True


def test_b1_title_cut_and_names(ctx, plat):
    row = plat.ef.brain_rows[0]
    row['title'] = 'ع' * 120
    row['assign_log'][0]['to_name'] = 'د. هالة من السجل'
    d = get(ctx, '/api/v2/brain/today?since=' + since_now()).get_json()
    e = [x for x in d['entries'] if x['file_id'] == row['id']][0]
    assert len(e['title']) == 80 and e['to_name'] == 'د. هالة من السجل'
    row['assign_log'][0].pop('to_name')
    row['assign_log'][0]['to'] = 'ghost@experts.test'
    row['assigned_to'] = 'someone@else.test'
    d = get(ctx, '/api/v2/brain/today?since=' + since_now()).get_json()
    e = [x for x in d['entries'] if x['file_id'] == row['id']][0]
    assert e['to_name'] is None and e['to_email'] == 'ghost@experts.test', 'لا اسم مخترع'


def test_b1_partial_both_ways(ctx, plat):
    plat.ef.partial = True
    assert get(ctx, '/api/v2/brain/today?since=' + since_now()).get_json()['partial'] is True
    # أقدم تحديث في الصفحة أقدم من بداية اليوم ⇒ اليوم كله ظاهر ⇒ ليست ناقصة
    old = (datetime.datetime.now(UTC) - datetime.timedelta(days=5)).isoformat()
    files = [dict(f, updated_at=old) for f in plat.ef.brain_rows]
    plat.ef.today_status = (200, {'status': 'all', 'files': files, 'count': len(files), 'total': 500, 'service_mode': 'open'})
    assert get(ctx, '/api/v2/brain/today?since=' + since_now()).get_json()['partial'] is False
    plat.ef.today_status = (200, {'status': 'all', 'files': files, 'count': len(files), 'total': len(files), 'service_mode': 'closed'})
    d = get(ctx, '/api/v2/brain/today?since=' + since_now()).get_json()
    assert d['partial'] is False and d['service'] == 'closed'


@pytest.mark.parametrize('status', [500, 502, 503, 504])
def test_b1_failure_is_null_not_empty(ctx, plat, status):
    plat.ef.today_status = (status, {'detail': 'x'})
    r = get(ctx, '/api/v2/brain/today?since=' + since_now())
    d = r.get_json()
    assert r.status_code == 200 and d == {'files_ok': False, 'entries': None}


def test_b1_missing_and_auth_masking(ctx, plat):
    plat.ef.today_status = (404, {'detail': 'Not Found'})
    d = get(ctx, '/api/v2/brain/today?since=' + since_now()).get_json()
    assert d['files_ok'] is False and d['entries'] is None and d['missing'] is True
    for st in (401, 403):
        plat.ef.today_status = (st, {'detail': 'no'})
        r = get(ctx, '/api/v2/brain/today?since=' + since_now())
        assert r.status_code == 200 and r.get_json()['files_ok'] is False, 'رفض المنصة للمفتاح لا يُخرج الأدمن'


def test_b1_bad_body_shapes(ctx, plat):
    for body in ([], {'files': 'x'}, {'files': None}):
        plat.ef.today_status = (200, body)
        d = get(ctx, '/api/v2/brain/today?since=' + since_now()).get_json()
        assert d == {'files_ok': False, 'entries': None}


def test_b2_values_and_calls(ctx, plat):
    d = get(ctx, '/api/v2/brain/rules').get_json()
    a = d['auto_assign']
    assert a['value'] is True and a['explicit'] is True and a['updated_by'] == 'admin@local.test' and a['updated_at'].endswith('+00:00')
    assert d['release_hours'] == 72 and d['requested'] == [] and d['history'] == []
    assert sorted(c['path'] for c in plat.seen) == ['/api/bridge/expert-files/settings', '/api/policies'] and len(plat.seen) == 2


def test_b2_bad_auto_assign_type_and_missing(ctx, plat):
    for bad in ('yes', 1, None):
        plat.ef.auto_assign = bad
        assert get(ctx, '/api/v2/brain/rules').get_json()['auto_assign'] is None
    plat.ef.auto_assign = True
    plat.ef.settings_enabled = False
    d = get(ctx, '/api/v2/brain/rules').get_json()
    assert d['auto_assign'] is None and d['auto_assign_missing'] is True


@pytest.mark.parametrize('value,expect', [(72, 72), (24, 24), (0, None), (-5, None), ('72', None), (72.5, None), (True, None), (None, None), ([], None)])
def test_b2_release_hours_only_positive_int(ctx, plat, value, expect):
    plat.ef.policies_body = {'escrow': {'auto_release_hours': value}}
    assert get(ctx, '/api/v2/brain/rules').get_json()['release_hours'] == expect


def test_b2_each_source_fails_alone(ctx, plat):
    plat.ef.down.add('/api/bridge/expert-files/settings')
    d = get(ctx, '/api/v2/brain/rules')
    assert d.status_code == 200 and d.get_json()['auto_assign'] is None and d.get_json()['release_hours'] == 72
    plat.ef.down = {'/api/policies'}
    d = get(ctx, '/api/v2/brain/rules')
    assert d.status_code == 200 and d.get_json()['auto_assign']['value'] is True and d.get_json()['release_hours'] is None
    plat.ef.down = {'/api/policies', '/api/bridge/expert-files/settings'}
    plat.seen.clear()
    d = get(ctx, '/api/v2/brain/rules')
    j = d.get_json()
    assert d.status_code == 200 and j['auto_assign'] is None and j['release_hours'] is None and len(plat.seen) == 2, 'بلا إعادة محاولة'


def test_b2_history_filtered_with_zone(ctx, plat):
    with flask_app.app_context():
        for act in ('expert_file.auto_assign', 'v2_brain.rule_add', 'v2_brain.rule_delete', 'user.role_change', 'money.pay'):
            db.session.add(AuditLog(actor_email='a@x.test', action=act, target='t', meta_json=json.dumps({'auto_assign': False})))
        db.session.commit()
    h = get(ctx, '/api/v2/brain/rules').get_json()['history']
    assert sorted(x['action'] for x in h) == ['expert_file.auto_assign', 'v2_brain.rule_add', 'v2_brain.rule_delete']
    assert all(x['at'].endswith('+00:00') and x['actor_email'] == 'a@x.test' for x in h)
    assert [x for x in h if x['action'] == 'expert_file.auto_assign'][0]['meta'] == {'auto_assign': False}


def _usage(monkeypatch, **kw):
    import app as appmod
    st = {'day': '2026-10-30', 'cap': 40, 'used': 12, 'remaining': 28, 'blocked': False, 'alerted_80': False, 'alerted_100': False, 'counter_error': None}
    st.update(kw)
    monkeypatch.setattr(appmod, 'ai_daily_usage_state', lambda: st)


def test_b3_mapping_and_no_ai(ctx, plat, monkeypatch):
    monkeypatch.setenv('DEEPSEEK_API_KEY', 'not-a-real-key')
    _usage(monkeypatch)
    d = get(ctx, '/api/v2/brain/helpers-status').get_json()
    assert d == {'configured': True, 'cap': 40, 'used': 12, 'remaining': 28, 'blocked': False, 'writer': 'backup'}
    _usage(monkeypatch, cap=0, remaining=None, used=5)
    d = get(ctx, '/api/v2/brain/helpers-status').get_json()
    assert d['cap'] is None and d['remaining'] is None and d['used'] == 5 and d['blocked'] is False
    _usage(monkeypatch, counter_error='OperationalError')
    d = get(ctx, '/api/v2/brain/helpers-status').get_json()
    assert d['used'] is None and d['remaining'] is None and d['cap'] == 40
    _usage(monkeypatch, used=40, remaining=0, blocked=True)
    assert get(ctx, '/api/v2/brain/helpers-status').get_json()['blocked'] is True
    for k in ('ANTHROPIC_API_KEY', 'OPENAI_API_KEY', 'DEEPSEEK_API_KEY'):
        monkeypatch.delenv(k, raising=False)
    d = get(ctx, '/api/v2/brain/helpers-status').get_json()
    assert d['configured'] is False and d['writer'] is None
    monkeypatch.setenv('ANTHROPIC_API_KEY', 'not-a-real-key')
    assert get(ctx, '/api/v2/brain/helpers-status').get_json()['writer'] == 'main'
    assert plat.seen == [], 'B3 بلا نداء للمنصة'


def test_b4_requires_confirm_and_validates(ctx, plat):
    ok = 'لا توزّع ملفات الخليج على خبير من مصر'
    assert send(ctx, 'POST', '/api/v2/brain/rules', {'text': ok}).status_code == 400
    assert send(ctx, 'POST', '/api/v2/brain/rules', {'text': ok, 'confirmed': 'true'}).status_code == 400
    assert send(ctx, 'POST', '/api/v2/brain/rules', {'text': 'قصير', 'confirmed': True}).status_code == 400
    assert send(ctx, 'POST', '/api/v2/brain/rules', {'text': 'ا' * 301, 'confirmed': True}).status_code == 400
    assert send(ctx, 'POST', '/api/v2/brain/rules', {'text': 5, 'confirmed': True}).status_code == 400
    with flask_app.app_context():
        assert AuditLog.query.filter_by(action='v2_brain.rule_add').count() == 0, 'التدقيق عند النجاح فقط'
    r = send(ctx, 'POST', '/api/v2/brain/rules', {'text': '  لا\x00 توزّع\n\n  ملفات   الخليج‏  ', 'confirmed': True, 'by': 'evil@x.test', 'created_by': 'evil@x.test'})
    assert r.status_code == 200
    row = r.get_json()
    assert row['text'] == 'لا توزّع ملفات الخليج' and row['status'] == 'requested' and re.match(r'^[0-9a-f]{32}$', row['id'])
    assert row['created_by'] == ADMIN_EMAIL, 'الفاعل من التوكن لا من الجسم'
    assert row['created_at'].endswith('+00:00')
    with flask_app.app_context():
        a = AuditLog.query.filter_by(action='v2_brain.rule_add').all()
        assert len(a) == 1 and a[0].target == row['id'] and a[0].actor_email == ADMIN_EMAIL
    assert plat.seen == []
    d = get(ctx, '/api/v2/brain/rules').get_json()
    assert [x['id'] for x in d['requested']] == [row['id']]


def test_b4_cap_50(ctx, plat):
    for i in range(50):
        assert send(ctx, 'POST', '/api/v2/brain/rules', {'text': 'قاعدة رقم %d للاختبار' % i, 'confirmed': True}).status_code == 200
    r = send(ctx, 'POST', '/api/v2/brain/rules', {'text': 'قاعدة واحدة زائدة', 'confirmed': True})
    assert r.status_code == 409 and '٥٠' in r.get_json()['error']
    assert len(get(ctx, '/api/v2/brain/rules').get_json()['requested']) == 50


def test_b5_delete(ctx, plat):
    rid = send(ctx, 'POST', '/api/v2/brain/rules', {'text': 'قاعدة ستحذف قريبا', 'confirmed': True}).get_json()['id']
    assert send(ctx, 'DELETE', '/api/v2/brain/rules/' + rid, {}).status_code == 400
    assert send(ctx, 'DELETE', '/api/v2/brain/rules/not-an-id', {'confirmed': True}).status_code == 400
    assert send(ctx, 'DELETE', '/api/v2/brain/rules/' + 'b' * 32, {'confirmed': True}).status_code == 404
    with flask_app.app_context():
        assert AuditLog.query.filter_by(action='v2_brain.rule_delete').count() == 0
    r = send(ctx, 'DELETE', '/api/v2/brain/rules/' + rid, {'confirmed': True})
    assert r.status_code == 200
    assert get(ctx, '/api/v2/brain/rules').get_json()['requested'] == []
    with flask_app.app_context():
        a = AuditLog.query.filter_by(action='v2_brain.rule_delete').all()
        assert len(a) == 1 and a[0].target == rid
    assert send(ctx, 'DELETE', '/api/v2/brain/rules/' + rid, {'confirmed': True}).status_code == 404


def test_switch_path_goes_through_confirmed_put(ctx, plat):
    """المفتاح يستعمل الـPUT الموجود: القفل بلا `confirmed:true` ⇒ ٤٠٠ قبل أي رحلة، ومعه يمرّ والفاعل من التوكن."""
    r = send(ctx, 'PUT', '/api/platform-expert-files/settings', {'auto_assign': False})
    assert r.status_code == 400 and plat.seen == []
    r = send(ctx, 'PUT', '/api/platform-expert-files/settings', {'auto_assign': False, 'confirmed': True, 'by': 'evil'})
    assert r.status_code == 200 and plat.ef.auto_assign is False
    assert plat.ef.settings_puts[0] == {'auto_assign': False, 'by': ADMIN_EMAIL}


# ---------------------------------------------------------------- ٢) المنطق (node)

CAIRO_MID = '2026-10-29T22:00:00Z'      # منتصف ليل ٣٠ أكتوبر ٢٠٢٦ بتوقيت القاهرة (UTC+2 بعد انتهاء التوقيت الصيفي)


def _e(file_id, at, to='hala@experts.test', by='auto', reason='paid', **kw):
    d = {'file_id': file_id, 'title': 'ملف ' + file_id, 'status': 'assigned', 'at': at, 'by': by, 'reason': reason, 'why': '', 'to_email': to, 'to_name': None,
         'pre_claim': True, 'current': True}
    d.update(kw)
    return d


@needs_node
def test_time_without_zone_is_utc():
    f = lambda s: v2_node.logic('v2sBrainTime', s)
    assert f('2026-10-30T22:30:00') == f('2026-10-30T22:30:00Z')
    assert f('2026-10-30T22:30:00+02:00') == f('2026-10-30T20:30:00Z')
    assert f('2026-10-30') == f('2026-10-30T00:00:00Z')
    assert f('') is None and f(None) is None and f('غير تاريخ') is None
    assert f('2026-10-30T22:30:00.123456') == f('2026-10-30T22:30:00.123456Z')


@needs_node
def test_time_without_zone_is_not_read_as_cairo_local():
    """جهاز المؤسس بتوقيت القاهرة: تقرير بلا منطقة ٢٢:٣٠ UTC (= ٠٠:٣٠ بعد منتصف الليل محليًا) يقع في اليوم التالي لا اليوم."""
    since_next_day = '2026-10-30T22:00:00Z'
    agents = [{'agent': 'articles', 'summary': 'x', 'created_at': '2026-10-30T22:30:00'},
              {'agent': 'seo', 'summary': 'x', 'created_at': '2026-10-30T21:30:00'}]
    rows = v2_node._run('v2_apply.js', {'fn': 'v2sBrainLogRows', 'args': [{'entries': []}, agents, since_next_day]}, tz='Africa/Cairo')
    assert [r['agent'] for r in rows] == ['articles'], rows
    s = v2_node._run('v2_apply.js', {'fn': 'v2sBrainSince', 'args': [1793354400000]}, tz='Africa/Cairo')     # 2026-10-30T10:00Z
    assert s == v2_node.logic('v2sBrainTime', CAIRO_MID)


@needs_node
def test_entries_counts_dedupe_and_changed():
    resp = {'files_ok': True, 'partial': False, 'entries': [
        _e('f1', '2026-10-30T10:00:00+00:00'), _e('f1', '2026-10-30T10:00:00+00:00'),                       # مكرر
        _e('f2', '2026-10-30T09:00:00+00:00', to='a@x.test'), _e('f2', '2026-10-30T11:00:00+00:00', to='b@x.test', by='founder', reason='manual'),
        _e('f3', '2026-10-30T12:00:00+00:00', by='founder', reason='manual'),                                  # يدوي بلا تلقائي قبله
        _e('f4', '2026-10-30T13:00:00+00:00', by='founder'), _e('f4', '2026-10-30T12:30:00+00:00'),         # يدوي بعد التلقائي
        _e('old', '2026-10-28T12:00:00+00:00')]}
    r = v2_node.logic('v2sBrainEntries', resp, CAIRO_MID)
    assert r['autoCount'] == 3 and r['changedCount'] == 2 and r['partial'] is False and r['missing'] is False
    assert [e['file_id'] for e in r['entries']][:2] == ['f4', 'f4'] or r['entries'][0]['atMs'] >= r['entries'][-1]['atMs']
    assert len(r['entries']) == 6
    assert [e['atMs'] for e in r['entries']] == sorted([e['atMs'] for e in r['entries']], reverse=True)
    rows = v2_node.logic('v2sBrainLogRows', r, [], CAIRO_MID)
    assert len(rows) == 5, 'يدوي بلا تلقائي قبله لا يدخل سجل العقل'
    assert sum(1 for x in rows if x['muted']) == 2


@needs_node
def test_entries_null_on_failure_and_missing():
    assert v2_node.logic('v2sBrainEntries', None, CAIRO_MID) is None
    assert v2_node.logic('v2sBrainEntries', {'files_ok': False, 'entries': None}, CAIRO_MID) is None
    m = v2_node.logic('v2sBrainEntries', {'files_ok': False, 'entries': None, 'missing': True}, CAIRO_MID)
    assert m['missing'] is True and m['autoCount'] is None and m['entries'] == []
    p = v2_node.logic('v2sBrainEntries', {'files_ok': True, 'partial': True, 'entries': []}, CAIRO_MID)
    assert p['partial'] is True and p['autoCount'] == 0


@needs_node
def test_log_from_inbox_includes_fyi_rows():
    """ملف وُزّع قبل ساعة ما زال في مهلة الاستلام (fyi) — سجل D1 القديم كان يتلقى الصفوف بلا «للعلم» فيضيّعه."""
    ef = {'id': 'ef-fy', 'title': 'عقد', 'status': 'assigned', 'assigned_to': 'hala@experts.test', 'assigned_name': 'د. هالة',
          'assign_log': [{'at': '2026-10-30T09:00:00Z', 'to': 'hala@experts.test', 'by': 'auto', 'reason': 'paid', 'why': 'نفس التخصص'}]}
    rows = [{'fyi': True, 'apiKind': 'expert_file', 'ef': ef}, {'fyi': False, 'ef': {'id': 'x', 'assign_log': []}}, {}]
    r = v2_node.logic('v2sBrainLogFromInbox', rows, CAIRO_MID)
    assert r['autoCount'] == 1 and r['partial'] is True and r['fromInbox'] is True
    e = r['entries'][0]
    assert e['to_name'] == 'د. هالة' and e['pre_claim'] is True and e['current'] is True
    old = v2_node.logic('v2BrainLog', [r_ for r_ in rows if not r_.get('fyi')], 1793354400000)
    assert old == [], 'الاحتياط القديم يضيّع ملف «للعلم»'
    assert v2_node.logic('v2sBrainLogFromInbox', None, CAIRO_MID) is None


@needs_node
def test_log_text_and_actions():
    t = lambda **k: v2_node.logic('v2sBrainLogText', _e('f', '2026-10-30T10:00:00Z', title='عقد', to_name='د. هالة', **k))
    assert t() == 'وزّع «عقد» على د. هالة'
    assert t(reason='declined') == 'وزّع «عقد» على د. هالة بعد اعتذار خبير'
    assert t(reason='timeout') == 'نقل «عقد» إلى د. هالة لأن الملف لم يُستلم في وقته'
    assert t(by='founder') == 'أُرسل «عقد» يدويًا إلى د. هالة'
    assert v2_node.logic('v2sBrainLogText', _e('f', '2026-10-30T10:00:00Z', title='', to_name=None, to='sami@experts.test')) == 'وزّع «ملف» على sami'
    r = v2_node.logic('v2sBrainEntries', {'files_ok': True, 'entries': [
        _e('a', '2026-10-30T10:00:00Z'), _e('b', '2026-10-30T11:00:00Z', pre_claim=False), _e('c', '2026-10-30T12:00:00Z', current=False)]}, CAIRO_MID)
    rows = v2_node.logic('v2sBrainLogRows', r, [], CAIRO_MID)
    acts = {x['entry']['file_id']: x['action'] for x in rows}
    assert acts['a'] == {'kind': 'send', 'label': 'أرسله لخبير آخر'}
    assert acts['b']['label'] == 'اعرض' and acts['c']['label'] == 'اعرض'
    assert 'اعكس' not in json.dumps(rows, ensure_ascii=False)


QUEUE_OK = {'expert_files_awaiting_assignment': 3, 'alerts': [], 'heartbeats': {'sla_last': '2026-10-30T11:40:00Z', 'tick_last': '2026-10-30T11:00:00Z',
            'remind_last': '2026-10-30T11:30:00Z', 'invite_reminders_last': None, 'coach_stalled_last': '2026-10-30T07:00:00Z'}}
NOW = 1793361600000          # 2026-10-30T12:00:00Z
B2_OK = {'auto_assign': {'value': True, 'explicit': True, 'updated_at': '2026-10-30T10:00:00+00:00', 'updated_by': 'admin@local.test'},
         'release_hours': 72, 'requested': [], 'history': []}


def rules(settings=B2_OK, queue=QUEUE_OK, invite={'invite_approval_from_generation': 2}):
    return v2_node.logic('v2sBrainRules', {'settings': settings, 'queue': queue, 'invite': invite, 'now': NOW})


def rowmap(res):
    return {r['key']: r for r in res['rows']}


@needs_node
def test_rules_groups_and_chips():
    res = rules()
    assert [g['title'] for g in res['groups']] == ['ملفات الخبراء والاستشارات', 'الدورات', 'الناس والدعوات', 'المحتوى']
    assert [len(g['rows']) for g in res['groups']] == [9, 4, 2, 1]
    rm = rowmap(res)
    assert rm['assign']['control']['type'] == 'switch' and rm['assign']['control']['value'] is True
    assert rm['move']['control']['label'] == 'وحده'
    allowed = {'وحده', 'وحده دائمًا', 'يسألني', 'متوقّف', 'غير متاح بعد', 'لم تُبنَ بعد'}
    labels = {r['control']['label'] for r in res['rows']}
    assert labels <= allowed, labels
    assert 'يسألك' not in json.dumps(res, ensure_ascii=False)
    for k in ('unclaimed_refund', 'consult_refund', 'release', 'case_release', 'urgent'):
        assert rm[k]['control']['label'] == 'وحده دائمًا', k
    assert rm['first_review']['control']['label'] == 'يسألني' and rm['invite_approval']['control']['label'] == 'يسألني'
    for r in res['rows']:
        assert r['sentence'].startswith('عندما') and '⇒' not in r['sentence'], r['key']
    assert rm['assign']['line'] == 'آخر تغيير: منذ ساعتين بواسطة admin@local.test'


@needs_node
def test_rules_assign_unknown_and_missing():
    off = rowmap(rules(dict(B2_OK, auto_assign=dict(B2_OK['auto_assign'], value=False))))
    assert off['assign']['control'] == {'type': 'switch', 'value': False, 'label': 'يسألني', 'tone': 'ask'}
    assert off['move']['control']['label'] == 'يسألني' and 'يصلك تنبيه لترسله بنفسك' in off['move']['sentence']
    unk = rowmap(rules(dict(B2_OK, auto_assign=None)))
    assert unk['assign']['control']['type'] == 'chip' and unk['assign']['control']['label'] == 'غير متاح بعد' and unk['assign']['line'] == 'تعذّر جلب حالة التوزيع'
    assert unk['move']['control']['label'] == 'غير متاح بعد' and unk['move']['line'] == 'تعذّر جلب حالة التوزيع'
    assert 'يُرسل وحده إلى الخبير التالي' in unk['move']['sentence']
    miss = rowmap(rules(dict(B2_OK, auto_assign=None, auto_assign_missing=True)))
    assert miss['assign']['line'] == 'التوزيع التلقائي غير موجود على المنصة بعد'
    none = rowmap(rules(None))
    assert none['assign']['control']['label'] == 'غير متاح بعد'
    never = rowmap(rules(dict(B2_OK, auto_assign=dict(B2_OK['auto_assign'], explicit=False))))
    assert never['assign']['line'] == 'لم يُغيَّر من قبل'


@needs_node
def test_rules_stopped_marks_every_sla_rule():
    q = dict(QUEUE_OK, alerts=['⚠️ حارس المهلة والاسترداد: متوقّفة منذ 5 ساعة، والحدّ المسموح 2 ساعة'])
    rm = rowmap(rules(queue=q))
    for k in ('move', 'unclaimed_refund', 'consult_refund', 'release', 'case_release', 'urgent', 'reminders'):
        assert rm[k]['control']['label'] == 'متوقّف' and rm[k]['stopped'].startswith('حارس المهلة والاسترداد: متوقفة'), k
        assert rm[k]['line'] == rm[k]['stopped']
    assert rm['assign']['control']['type'] == 'switch' and rm['assign']['stopped'], 'التنبيه لا يخفي المفتاح'
    assert not rm['live']['stopped'] and rm['live']['control']['label'] == 'وحده'
    q2 = dict(QUEUE_OK, alerts=['⏰ ساعة الدورات الحيّة: لم تعمل ولا مرّة حتى الآن'])
    assert rowmap(rules(queue=q2))['live']['control']['label'] == 'متوقّف'


@needs_node
def test_rules_run_text_and_unavailable():
    rm = rowmap(rules())
    assert rm['move']['line'] == 'آخر تشغيل: منذ ٢٠ د'
    assert rm['invite_remind']['line'] == 'لم يعمل حتى الآن'
    assert rm['first_review']['line'] == 'في ملفات الخبراء' and rm['offer_accept']['line'] == 'يعمل لحظة العرض' and rm['comments']['line'] == 'يعمل لحظة التعليق'
    dead = rowmap(rules(queue=None))
    assert dead['move']['line'] == 'آخر تشغيل: غير متاح بعد' and dead['live']['line'] == 'آخر تشغيل: غير متاح بعد'
    f = lambda at, unavailable=False: v2_node.logic('v2sBrainRunText', at, NOW, unavailable)
    assert f('2026-10-30T11:59:40Z') == 'آخر تشغيل: الآن' and f(None) == 'لم يعمل حتى الآن' and f(None, True) == 'آخر تشغيل: غير متاح بعد'


@needs_node
@pytest.mark.parametrize('hours,expect', [(72, 'عندما تمر ٣ أيام على التسليم دون اعتراض، يتحرّر أجر الخبير.'),
                                          (36, 'عندما تمر ٣٦ ساعة على التسليم دون اعتراض، يتحرّر أجر الخبير.'),
                                          (48, 'عندما تمر يومان على التسليم دون اعتراض، يتحرّر أجر الخبير.'),
                                          (None, 'عندما تمر مهلة الاعتراض بعد التسليم دون اعتراض، يتحرّر أجر الخبير.')])
def test_rules_release_sentence_numbers_only_from_source(hours, expect):
    assert rowmap(rules(dict(B2_OK, release_hours=hours)))['release']['sentence'] == expect


@needs_node
def test_rules_invite_generation_and_no_invented_numbers():
    rm = rowmap(rules())
    assert rm['invite_approval']['sentence'] == 'عندما يدعو عضو من الجيل ٢ أو بعده، تنتظر الدعوة موافقتك.' and rm['invite_approval']['line'] == 'من الجيل ٢'
    nul = rowmap(rules(invite=None))['invite_approval']
    assert nul['line'] == 'الجيل: غير متاح بعد' and nul['sentence'] == 'عندما تأتي دعوة من جيل بعيد، تنتظر موافقتك.'
    assert rowmap(rules(invite={'missing': True}))['invite_approval']['line'] == 'الجيل: غير متاح بعد'
    assert rm['invite_approval']['link']['label'] == 'غيّرها من الدعوات'
    text = ' '.join(r['sentence'] for r in rules()['rows'] if r['key'] not in ('release', 'invite_approval'))
    assert not re.search(r'[0-9٠-٩]', text), 'رقم في جملة قاعدة بلا مصدر'


@needs_node
def test_line_priority_and_cases():
    ent = {'entries': [], 'autoCount': 4, 'changedCount': 1, 'partial': False, 'missing': False, 'fromInbox': False}
    stopped_q = dict(QUEUE_OK, alerts=['⚠️ حارس المهلة والاسترداد: متوقّفة منذ 5 ساعة، والحدّ المسموح 2 ساعة'])
    off = dict(B2_OK, auto_assign=dict(B2_OK['auto_assign'], value=False))
    line = lambda **k: v2_node.logic('v2sBrainLine', k)
    r = line(queue=stopped_q, settings=off, entries=ent)
    assert r['text'].startswith('حارس المهلة والاسترداد: متوقفة') and r['button'] is None
    r = line(queue=QUEUE_OK, settings=off, entries=ent)
    assert r['text'] == 'التوزيع التلقائي متوقّف، وينتظر توزيعك: ٣ ملفات' and r['button'] == {'label': 'افتح الملفات', 'section': 'files'}
    r = line(queue=dict(QUEUE_OK, expert_files_awaiting_assignment=0), settings=off, entries=ent)
    assert r['text'] == 'وُزّع اليوم ٤ ملفات وحده، وغُيّر خبير ملف واحد منها يدويًا.' and r['button'] is None
    r = line(queue=QUEUE_OK, settings=B2_OK, entries=dict(ent, changedCount=0, autoCount=1))
    assert r['text'] == 'وُزّع اليوم ملف واحد وحده.'
    r = line(queue=QUEUE_OK, settings=B2_OK, entries=dict(ent, partial=True))
    assert r['text'].startswith('وُزّع اليوم على الأقل ٤ ملفات')
    r = line(queue=QUEUE_OK, settings=B2_OK, entries=dict(ent, fromInbox=True, partial=True))
    assert 'على الأقل' in r['text']
    r = line(queue=QUEUE_OK, settings=B2_OK, entries=dict(ent, autoCount=0, changedCount=0))
    assert r['text'] == 'لم يوزّع العقل شيئًا اليوم، وكل ما يعمل وحده يعمل.'
    r = line(queue=dict(QUEUE_OK, alerts=['ملف بلا رد']), settings=B2_OK, entries=dict(ent, autoCount=0, changedCount=0))
    assert r['text'] == 'لم يوزّع العقل شيئًا اليوم.', 'تنبيه آخر ⇒ لا ندّعي أن كل شيء يعمل'
    r = line(queue=QUEUE_OK, settings=B2_OK, entries=None)
    assert r['text'] == 'تعذّر جلب بعض ما يفعله العقل: الملفات. لا نعرف الصورة كاملة.'
    r = line(queue=None, settings=None, entries=None)
    assert r['text'] == 'تعذّر جلب بعض ما يفعله العقل: الملفات، حالة ما يعمل وحده، القواعد. لا نعرف الصورة كاملة.'
    r = line(queue=None, settings=B2_OK, entries=dict(ent, autoCount=0, changedCount=0))
    assert r['text'].startswith('تعذّر جلب بعض ما يفعله العقل: حالة ما يعمل وحده')
    r = line(queue=QUEUE_OK, settings=B2_OK, entries={'entries': [], 'autoCount': None, 'changedCount': None, 'partial': False, 'missing': True, 'fromInbox': False})
    assert 'الملفات' in r['text'], 'سجل غير موجود على المنصة ⇒ لا «لم يوزّع شيئًا»'


def agents(n=11, **over):
    ids = ['articles', 'seo', 'automation', 'sales', 'marketing', 'platform', 'topics', 'incoming', 'dev', 'finance', 'master'][:n]
    out = [{'agent': i, 'label': 'x (Master) ' + i, 'desc': 'd', 'summary': 'ملخص ' + i, 'bullets': ['a'], 'actions': ['b'], 'created_at': '2026-10-30T10:00:00', 'source': None}
           for i in ids]
    for i in out:
        i.update(over.get(i['agent'], {}))
    return {'agents': out, 'ai_configured': True}


@needs_node
def test_helpers_labels_order_and_caps():
    H = v2_node.logic('v2sBrainHelpers', agents(), {'blocked': False, 'remaining': 28, 'cap': 40, 'used': 12, 'configured': True}, None)
    assert H['cards'][0]['id'] == 'master' and H['count'] == 11 and H['canRunAll'] is True and H['master']['label'] == 'الصورة الكاملة'
    assert not re.search(r'[A-Za-z]', ' '.join(c['label'] + c['desc'] for c in H['cards'])), 'اسم بحروف لاتينية'
    assert [c['label'] for c in H['cards']][1:4] == ['المقالات', 'الظهور في البحث', 'الأعمال المتكرّرة']
    short = v2_node.logic('v2sBrainHelpers', agents(), {'blocked': False, 'remaining': 10, 'cap': 40, 'used': 30}, None)
    assert short['canRunAll'] is False and short['runAllReason'] == 'لا يكفي المتبقي من تحديثات اليوم'
    four = v2_node.logic('v2sBrainHelpers', agents(4), {'blocked': False, 'remaining': 4, 'cap': 40, 'used': 36}, None)
    assert four['count'] == 4 and four['canRunAll'] is True
    assert v2_node.logic('v2sBrainHelpers', agents(4), {'blocked': False, 'remaining': 3, 'cap': 40, 'used': 37}, None)['canRunAll'] is False
    busy = v2_node.logic('v2sBrainHelpers', agents(), {'blocked': False, 'remaining': 28, 'cap': 40, 'used': 12}, 'seo')
    assert busy['canRunAll'] is False and all(not c['canRun'] for c in busy['cards']) and [c['id'] for c in busy['cards'] if c['running']] == ['seo']
    blocked = v2_node.logic('v2sBrainHelpers', agents(), {'blocked': True, 'remaining': 0, 'cap': 40, 'used': 40}, None)
    assert blocked['canRunAll'] is False and all(not c['canRun'] for c in blocked['cards'])
    nostatus = v2_node.logic('v2sBrainHelpers', agents(), None, None)
    assert nostatus['canRunAll'] is True and nostatus['remainingText'] == 'غير متاح بعد'
    assert v2_node.logic('v2sBrainHelpers', None, None, None) is None


@needs_node
def test_helpers_data_only_and_unknown_label():
    H = v2_node.logic('v2sBrainHelpers', agents(4, seo={'source': 'data'}, topics={'summary': 'تعذّر التحليل — هذه أرقام حقيقية بلا تحليل نصّي.'}), None, None)
    flags = {c['id']: c['dataOnly'] for c in H['cards']}
    assert flags['seo'] is True and flags['articles'] is False
    odd = v2_node.logic('v2sBrainHelpers', {'agents': [{'agent': 'zzz', 'label': 'اسم الخادم', 'desc': 'وصف', 'summary': ''}]}, None, None)
    assert odd['cards'][0]['label'] == 'اسم الخادم' and odd['cards'][0]['img'] == 'reports' and odd['cards'][0]['hasReport'] is False


@needs_node
def test_helpers_discs_and_lines():
    cap = lambda s: v2_node.logic('v2sBrainCap', s)
    assert cap({'cap': 40, 'used': 12}) == '١٢ من ٤٠' and cap({'cap': None, 'used': 5}) == 'بلا سقف' and cap(None) == 'غير متاح بعد' and cap({'cap': 40, 'used': None}) == 'غير متاح بعد'
    H = v2_node.logic('v2sBrainHelpers', agents(), {'blocked': False, 'remaining': 28, 'cap': 40, 'used': 12}, None)
    line = lambda st: v2_node.logic('v2sBrainHelpersLine', H, st, NOW)
    assert line({'blocked': True}).startswith('وصلت تحديثات اليوم إلى حدّها')
    assert line({'blocked': False, 'configured': False}) == 'التحليل المكتوب غير مفعّل الآن، فيكتب المساعدون الأرقام وحدها.'
    assert line({'blocked': False, 'configured': True}) == 'آخر صورة كاملة كُتبت منذ ساعتين.'
    empty = v2_node.logic('v2sBrainHelpers', agents(3), None, None)
    assert v2_node.logic('v2sBrainHelpersLine', empty, None, NOW) == 'لم تُكتب الصورة الكاملة بعد.'
    assert 'المتبقي: ٢٨' in v2_node.logic('v2sBrainConfirmAll', H) and '١١ مساعدًا' in v2_node.logic('v2sBrainConfirmAll', H)
    assert 'المتبقي: غير متاح بعد' in v2_node.logic('v2sBrainConfirmAll', v2_node.logic('v2sBrainHelpers', agents(), None, None))
    assert 'المتبقي: بلا سقف' in v2_node.logic('v2sBrainConfirmAll', v2_node.logic('v2sBrainHelpers', agents(), {'cap': None, 'remaining': None, 'blocked': False}, None))


def _tiles(extras):
    base = {'now': NOW, 'inbox': []}
    base.update(extras)
    return {t['key']: t for t in v2_node.logic('v2Tiles', QUEUE_OK, base)}['brain']


@needs_node
def test_tile_number_agrees_with_screen():
    ent = v2_node.logic('v2sBrainEntries', {'files_ok': True, 'entries': [_e('a', '2026-10-30T10:00:00Z'), _e('b', '2026-10-30T11:00:00Z')]}, CAIRO_MID)
    t = _tiles({'brainToday': ent['autoCount']})
    assert t['count'] == ent['autoCount'] == 2 and t['failed'] is False and t['next'] == 'وزّع ملفين وحده اليوم'
    z = _tiles({'brainToday': 0})
    assert z['count'] == 0 and z['next'] == 'لم يوزّع شيئًا اليوم'
    f = _tiles({'brainToday': None})
    assert f['failed'] is True and f['count'] is None
    legacy = _tiles({})
    assert legacy['count'] == 0 and legacy['failed'] is False, 'undefined ⇒ العدّ القديم'
    assert _tiles({'brainToday': 3, 'inbox': None})['count'] == 3, 'السجل الكامل مستقل عن فشل الوارد'
    assert _tiles({'brainToday': 3, 'brainTodayPartial': True})['partial'] is True


@needs_node
def test_sections_entry_and_aliases():
    secs = v2_node.logic('SECTIONS')
    brain = [s for s in secs if s['key'] == 'brain'][0]
    assert brain['label'] == 'العقل' and brain['desc'] == 'ما يفعله العقل وحده، وما ينتظر قرارك. ما له مفتاح تغيّره من هنا.'
    assert [(t['key'], t['label'], t['mod']) for t in brain['tabs']] == [('log', 'القواعد وسجل اليوم', 'v2s_brain'), ('helpers', 'المساعدون', 'ai')]
    assert v2_node.logic('sectionFor', 'ai')['section'] == 'brain' and v2_node.logic('sectionFor', 'ai')['tab'] == 'helpers'
    rt = v2_node.logic('routeFor', '#ai', {})
    assert (rt['section'], rt['tab']) == ('brain', 'helpers')
    assert v2_node.logic('sectionHash', 'brain', 'log') == '#s/brain/log'
    rt = v2_node.logic('routeFor', '#s/brain/log', {})
    assert (rt['section'], rt['tab']) == ('brain', 'log')
    assert v2_node.logic('sectionFor', 'v2s_brain')['tab'] == 'log'


# ---------------------------------------------------------------- ٣) ملفات

def test_index_html_block_and_dispatcher():
    html = _read('dashboard-cloud', 'index.html')
    m = re.search(r'<!-- v2 sections begin -->\n(.*?)<!-- v2 sections end -->', html, re.S)
    assert m, 'علامتا الكتلة'
    blk = m.group(1).strip().splitlines()   # بعد الدمج: كتلة واحدة لكل الأقسام؛ العقل سطراه متجاوران
    assert blk[blk.index('<link rel="stylesheet" href="v2s/brain.css">') + 1] == '<script src="v2s/brain.js"></script>'
    assert html.index('<script src="v2-d2.js"></script>') < html.index('<!-- v2 sections begin -->')
    # بعد الدمج: خطّاف واحد موحّد عبر السجلّ V2SEC.owner، والعقل مسجَّل فيه بمفتاحه (brain.js: V2SEC.brain)
    assert html.count('const _s=V2SEC.owner(current)') == 1
    d3 = html.index('V2D3.owns(current))return V2D3.render(current,v)')
    sec = html.index('const _s=V2SEC.owner(current)')
    assert 0 < d3 < sec
    assert 'window.V2S=' not in html


def test_brain_js_contract():
    js = _read('dashboard-cloud', 'v2s', 'brain.js')
    assert '<h1' not in js
    assert 'EP.runAgents' not in js and 'expertFileAutoAssign' not in js
    assert 'window.V2SEC = window.V2SEC || {}' in js and 'owns' in js
    assert "'/platform-expert-files/settings', { method: 'PUT', body: { auto_assign: toAuto, confirmed: true } }" in js
    assert "'/ai/agents/run?agent='" in js and js.count("'/ai/agents/run?agent='") == 1, 'مسار التشغيل في دالة واحدة فقط'
    assert 'اعكس' not in js
    assert 'window.V2S ' not in js and 'window.V2S=' not in js


def test_shared_edits_present():
    home = _read('dashboard-cloud', 'v2-home.js')
    assert 'brainToday = V2SEC.brain.tileCount()' in home
    d2 = _read('dashboard-cloud', 'v2-d2.js')
    assert 'V2SEC.brain.tileCount' in d2
    dock = _read('Dockerfile')
    assert 'COPY backend/v2_brain_routes.py /app/v2_brain_routes.py' in dock and 'COPY dashboard-cloud/v2s /app/dist/v2s' in dock   # بعد الدمج: سطر صريح لكل قسم
    app_src = _read('backend', 'app.py')
    end = app_src.index('# ---- v2 section routes end')
    reg = app_src.index('from v2_brain_routes import register as _v2_brain_register')
    assert 0 < reg < end
    assert "except Exception: logger.exception('v2 brain routes not loaded')" in app_src
    assert app_src.count('# ---- v2 section routes end') == 1


def _literals(src):
    out = []
    for m in re.finditer(r"'((?:[^'\\\n]|\\.)*)'", src):
        out.append(m.group(1))
    return out


FORBIDDEN = ['يقوّم', 'اعكس', 'لما ', '⇒', 'الكنسة', 'نداء', 'الوضع الافتراضي', 'التشغيلات', '✓']


def _visible_copy(src):
    """النصوص الظاهرة: كل حرفية فيها حرف عربي، بعد نزع وسوم HTML (الأصناف والسمات لاتينية بطبيعتها)."""
    out = []
    for lit in _literals(src):
        if re.search(r'[؀-ۿ]', lit):
            t = lit
            if '>' in t and ('<' not in t or t.index('>') < t.index('<')):
                t = t[t.index('>') + 1:]                  # ذيل وسم بدأ في حرفية سابقة
            for av in re.findall(r'="([^"]*[؀-ۿ][^"]*)"', t):   # نصوص السمات الظاهرة (placeholder · aria-label · title) تُفحص كما هي
                out.append(av)
            t = re.sub(r'<[^>]*(>|$)', ' ', t)            # وسوم كاملة أو مقطوعة في آخر الحرفية
            t = re.sub(r'[A-Za-z_][\w:-]*="[^"]*"', ' ', t)   # سمات بين حرفيتين
            out.append(t.replace('"', ' '))
    return out


def test_copy_scan_brain_js_and_logic_block():
    js = _read('dashboard-cloud', 'v2s', 'brain.js')
    logic = _read('dashboard-cloud', 'v2-logic.js')
    block = logic[logic.index('// ===== v2s:brain ====='):logic.index('// ===== /v2s:brain =====')]
    texts = _visible_copy(js) + _visible_copy(block)
    assert len(texts) > 150
    for t in texts:
        for bad in FORBIDDEN:
            assert not re.search(r'(?<![؀-ۿ])' + re.escape(bad), t), (bad, t)   # كلمة تبدأ بها، لا جزء من كلمة («كلما» ليست «لما»)
        assert not re.search(r'[A-Za-z0-9]', t), 'حرف أو رقم لاتيني في نص ظاهر: ' + t
        assert not re.match(r'^\s*(الذكاء|AI)', t), t
    # صيغة الاسم: بلا ضمير مذكر خاص بالمخاطَب في عناوين الأقسام
    assert 'يقوّم' not in js and 'يقوّم' not in block


def test_dashboard_untouched_old_screen_still_present():
    """الشاشة القديمة `viewAI` تبقى للمفتاح المقفول كما هي."""
    html = _read('dashboard-cloud', 'index.html')
    assert 'function viewAI(v)' in html and "if(current==='ai')" in html or 'viewAI(v)' in html


# ——— جولة التصليح ———
@needs_node
def test_line_waiting_phrase_is_grammatical_for_every_count():
    off = dict(B2_OK, auto_assign=dict(B2_OK['auto_assign'], value=False))
    for n, word in ((1, 'ملف واحد'), (2, 'ملفان'), (3, '٣ ملفات'), (9, '٩ ملفات'), (11, '١١ ملفًا')):
        r = v2_node.logic('v2sBrainLine', {'queue': dict(QUEUE_OK, expert_files_awaiting_assignment=n), 'settings': off, 'entries': None})
        assert r['text'] == 'التوزيع التلقائي متوقّف، وينتظر توزيعك: ' + word, (n, r['text'])


@needs_node
def test_missing_bridge_entries_are_unknown_not_zero():
    e = v2_node.logic('v2sBrainEntries', {'files_ok': False, 'entries': None, 'missing': True}, 0)
    assert e['missing'] is True and e['autoCount'] is None and e['changedCount'] is None and e['entries'] == []
    js = _read('dashboard-cloud', 'v2s', 'brain.js')
    # الحالة الناقصة تعرض «غير متاح بعد» بلا صندوق الفيل ولا «لم يحدث شيء» (الفحص الحي في لقطة 18)
    assert re.search(r"ent\.missing && !rows\.length\) body = '<div class=\"v3-empty v2sb-na\"><b>' \+ NA", js)
    assert js.index('v2sb-na') < js.index('لم يحدث شيء وحده اليوم')


@needs_node
def test_helper_images_are_scenes_and_never_repeat_among_agents():
    ids = ['articles', 'seo', 'automation', 'sales', 'marketing', 'platform', 'topics', 'incoming', 'dev', 'finance']
    imgs = [v2_node.logic('v2sBrainAgentInfo', i, '', '')['img'] for i in ids]
    assert len(set(imgs)) == len(imgs), imgs
    assert 'brain' not in imgs and 'brain-avatar' not in imgs
    for i in imgs:
        assert os.path.exists(os.path.join(ROOT, 'dashboard-cloud', 'v2', 'img', i + '.jpg')), i


def test_old_d1_brain_log_is_gone_and_old_link_redirects():
    home = _read('dashboard-cloud', 'v2-home.js')
    css = _read('dashboard-cloud', 'v2-home.css')
    assert 'drawBrain' not in home and "S.mode = 'brain'" not in home and "S.mode === 'brain'" not in home
    assert not re.search(r'\.v2-log[ {]', css)
    assert "host().openSection('brain', 'log')" in home


def test_rule_sheet_and_rows_isolate_emails_and_use_start_alignment():
    js = _read('dashboard-cloud', 'v2s', 'brain.js')
    css = _read('dashboard-cloud', 'v2s', 'brain.css')
    assert 'function bidi(' in js and '<bdi dir="ltr">' in js
    assert "bidi(r.line)" in js                                   # سطر صف القاعدة
    assert "sectionBlock('آخر تغيير'" in js                       # عنوان مستقل لا سطر بلا عنوان
    assert re.search(r'\.v2sbm \.v2sb-st\{grid-column:auto', css)  # لا يرث موضع الشبكة من صف القاعدة


def test_person_links_and_want_box_are_touch_sized_and_do_not_clip():
    css = _read('dashboard-cloud', 'v2s', 'brain.css')
    js = _read('dashboard-cloud', 'v2s', 'brain.js')
    assert re.search(r'\.v2sb-person\{display:inline-block;padding:11px 4px;margin:-11px -4px', css)
    assert '<textarea id="v2sbWant"' in js and '<input id="v2sbWant"' not in js
    assert re.search(r'\.v2sb-want textarea\{[^}]*resize:none', css)


# ——— الجولة الثانية (P5): ما يكتبه العقل · السجل · المساعدون — SPEC brain2 §4.4 ———
def _sw_resp(**over):
    base = [
        {'id': 'opinion', 'section': 'home', 'kind': 'opinion', 'label': 'رأي العقل في كل قرار', 'sentence': 'جملة الرأي.', 'lock_reason': '', 'may_run_alone': True, 'mode': 'alone', 'updated_at': None, 'updated_by': ''},
        {'id': 'reply_draft', 'section': 'people', 'kind': 'draft', 'label': 'مسودات الرد على الرسائل', 'sentence': 'جملة الرد.', 'lock_reason': 'يسألك دائمًا لأن الرد يصل إلى صاحب الرسالة.', 'may_run_alone': False, 'mode': 'ask', 'updated_at': None, 'updated_by': ''},
        {'id': 'seo_notes', 'section': 'content', 'kind': 'note', 'label': 'ملاحظات الظهور', 'sentence': 'جملة البحث.', 'lock_reason': '', 'may_run_alone': True, 'mode': 'alone', 'updated_at': '2026-10-30T10:00:00+00:00', 'updated_by': 'admin@local.test'},
    ]
    d = {'switches': base, 'writer': 'main', 'brain_today': {'used': 12, 'cap': 60}}
    d.update(over)
    return d


@needs_node
def test_switch_rows_options_lock_and_lines():
    r = v2_node.logic('v2sBrainSwitches', _sw_resp(), NOW)
    rows = {x['id']: x for x in r['rows']}
    lab = lambda x: [(o['label'], o['on']) for o in x['options']]
    assert lab(rows['opinion']) == [('وحده', True), ('متوقّف', False)]                       # الرأي: وحده | متوقّف
    assert lab(rows['reply_draft']) == [('يسألني', True), ('متوقّف', False)]                 # المقفول لا يعرض «وحده» أبدًا
    assert lab(rows['seo_notes']) == [('وحده', True), ('يسألني', False), ('متوقّف', False)]
    assert rows['reply_draft']['line'] == 'يسألك دائمًا لأن الرد يصل إلى صاحب الرسالة.' and rows['reply_draft']['locked'] is True
    assert rows['opinion']['line'] == 'لم يُغيَّر من قبل'
    assert rows['seo_notes']['line'] == 'آخر تغيير: منذ ساعتين بواسطة admin@local.test'
    assert rows['reply_draft']['link'] == {'label': 'افتح الناس والدعوات', 'section': 'people'} and rows['opinion']['link']['label'] == 'افتح اللوحة'
    assert r['writer'] == 'main' and r['brainToday'] == {'used': 12, 'cap': 60}
    # صف محجوب بيد «وحده» في قاعدة معبوث بها ⇒ يُعرض «يسألني» (الخادم يفرضه أيضًا)، ولا يُعرض اختيار ممنوع
    t = _sw_resp()
    t['switches'][1]['mode'] = 'alone'
    assert lab({x['id']: x for x in v2_node.logic('v2sBrainSwitches', t, NOW)['rows']}['reply_draft']) == [('يسألني', True), ('متوقّف', False)]
    t['switches'][0]['mode'] = 'ask'
    assert lab({x['id']: x for x in v2_node.logic('v2sBrainSwitches', t, NOW)['rows']}['opinion']) == [('وحده', True), ('متوقّف', False)]


@needs_node
def test_switch_source_failure_is_null_not_empty_and_writer_states():
    sw = lambda r: v2_node.logic('v2sBrainSwitches', r, NOW)
    assert sw(None) is None and sw({}) is None and sw({'switches': 'x'}) is None
    assert sw(_sw_resp(writer='backup'))['writer'] == 'backup'
    assert sw(_sw_resp(writer=None))['writer'] is None                      # لا كاتب مفعّل
    nowriter = _sw_resp()
    del nowriter['writer']
    assert 'writer' not in sw(nowriter) or sw(nowriter)['writer'] is None   # غير معروف (undefined في JS يسقط من JSON)
    assert sw(_sw_resp(brain_today=None))['brainToday'] == {'used': None, 'cap': None}
    assert sw(_sw_resp(brain_today={'used': 'x', 'cap': 0}))['brainToday'] == {'used': None, 'cap': None}
    w = lambda writer, known: v2_node.logic('v2sBrainWriterText', writer, known)
    assert w('main', True) == 'الكاتب الأساسي' and w('backup', True) == 'الكاتب الاحتياطي' and w(None, True) == 'لا أحد' and w(None, False) == 'غير متاح بعد'
    t = lambda bt: v2_node.logic('v2sBrainWritesToday', bt)
    assert t({'used': 12, 'cap': 60}) == '١٢ من ٦٠' and t({'used': None, 'cap': 60}) == 'غير متاح بعد' and t({'used': 3, 'cap': None}) == 'غير متاح بعد' and t(None) == 'غير متاح بعد'


@needs_node
def test_switch_confirm_sheet_texts():
    rows = {x['id']: x for x in v2_node.logic('v2sBrainSwitches', _sw_resp(), NOW)['rows']}
    s = lambda i, m: v2_node.logic('v2sBrainSwitchSheet', rows[i], m)
    assert s('seo_notes', 'off') == {'title': 'ملاحظات الظهور', 'lead': 'يتوقف العقل عن كتابة «ملاحظات الظهور». ويبقى ما كتبه من قبل كما هو.', 'go': 'نعم، أوقفه'}
    assert 'وحده' in s('seo_notes', 'alone')['lead'] and s('seo_notes', 'alone')['go'] == 'نعم، وحده'
    assert 'لا يُنفَّذ شيء إلا بعد موافقتك' in s('seo_notes', 'ask')['lead'] and s('seo_notes', 'ask')['go'] == 'نعم، يسألني'
    assert 'الجملة الثابتة' in s('opinion', 'off')['lead']
    for i in rows:
        for m in ('alone', 'ask', 'off'):
            assert not re.search(r'[A-Za-z]', s(i, m)['lead'] + s(i, m)['go'])


def _it(iid, status, kind='note', label='مقال', tag='', at='2026-10-30T10:00:00Z', decided=None, section='content'):
    return {'id': iid, 'producer': 'seo_notes', 'section': section, 'kind': kind, 'target_label': label, 'body': {'text': 'نص'}, 'status': status, 'source': 'ai',
            'created_at': at, 'decided_at': decided, 'decided_by': '', 'tag': tag, 'approve_label': '', 'last_error': ''}


@needs_node
def test_log_rows_exact_texts_actions_and_opinion_summary():
    resp = {'items': [
        _it('a', 'done_alone', label='م١', at='2026-10-30T11:00:00Z'),
        _it('b', 'proposed', 'draft', 'رسالة منى', 'مسودة رد', at='2026-10-30T10:50:00Z', section='people'),
        _it('c', 'approved', 'draft', 'طلب س', 'ربط بدورة', at='2026-10-30T09:00:00Z', decided='2026-10-30T10:40:00Z'),
        _it('d', 'edited', 'draft', 'طلب ص', 'مسودة رد', at='2026-10-30T09:00:00Z', decided='2026-10-30T10:30:00Z'),
        _it('e', 'rejected', 'draft', 'رسالة كريم', 'مسودة رد', decided='2026-10-30T10:20:00Z'),
        _it('f', 'discarded', label='م٢', decided='2026-10-30T10:10:00Z'),
        _it('g', 'failed', label='الأسبوع الماضي', at='2026-10-30T10:05:00Z'),
        _it('h', 'unknown', 'draft', 'رسالة ل', 'مسودة رد', at='2026-10-30T10:01:00Z'),
        _it('i', 'expired', 'draft', 'قديم', 'مسودة رد'), _it('j', 'applying', 'draft', 'جارٍ', 'مسودة رد'),
        _it('o1', 'done_alone', 'opinion', 'ق١', at='2026-10-30T08:00:00Z'), _it('o2', 'done_alone', 'opinion', 'ق٢', at='2026-10-30T08:30:00Z'),
        _it('o3', 'failed', 'opinion', 'ق٣', at='2026-10-30T08:40:00Z'),
        _it('old', 'done_alone', label='أمس', at='2026-10-29T10:00:00Z'),
    ]}
    items = v2_node.logic('v2sBrainItems', resp)
    rows = v2_node.logic('v2sBrainItemRows', items, '2026-10-30T00:00:00Z')
    got = [(r['text'], (r['action'] or {}).get('label', '')) for r in sorted(rows, key=lambda r: -r['atMs'])]
    assert got == [
        ('كتب ملاحظة على «م١»', 'احذفها'),
        ('اقترح «مسودة رد» على «رسالة منى»', 'افتح'),
        ('نُفّذ «ربط بدورة» على «طلب س» بموافقتك', ''),
        ('نُفّذ «مسودة رد» على «طلب ص» بموافقتك', ''),
        ('رُفض اقتراح على «رسالة كريم»', ''),
        ('حُذفت ملاحظة على «م٢»', ''),
        ('تعذّرت الكتابة عن «الأسبوع الماضي»', ''),
        ('لم نتأكد من نتيجة «مسودة رد» على «رسالة ل»', ''),
        ('كتب رأيه في قرارين', ''),
    ], got
    one = v2_node.logic('v2sBrainItemRows', v2_node.logic('v2sBrainItems', {'items': [_it('o', 'done_alone', 'opinion')]}), '2026-10-30T00:00:00Z')
    assert one[0]['text'] == 'كتب رأيه في قرار واحد' and one[0]['action'] is None
    many = v2_node.logic('v2sBrainItems', {'items': [_it('o%d' % n, 'done_alone', 'opinion') for n in range(11)]})
    assert v2_node.logic('v2sBrainItemRows', many, '2026-10-30T00:00:00Z')[0]['text'] == 'كتب رأيه في ١١ قرارًا'
    # الآراء وحدها لا صفوف فردية، والفاشل لا يُحسب
    assert [r['kind'] for r in rows].count('opinions') == 1 and not [r for r in rows if r.get('id') in ('o1', 'o2', 'o3')]
    # اقتراح ينتظر ⇒ يُعدّ، والآراء لا تُعدّ
    assert v2_node.logic('v2sBrainProposed', items) == 1
    assert v2_node.logic('v2sBrainProposed', None) is None
    # مصدر فاشل ⇒ null لا قائمة فاضية
    assert v2_node.logic('v2sBrainItems', None) is None and v2_node.logic('v2sBrainItems', {'items': 'x'}) is None


@needs_node
def test_log_rows_merge_with_files_and_reports():
    ent = v2_node.logic('v2sBrainEntries', {'files_ok': True, 'entries': [_e('a', '2026-10-30T10:00:00Z')]}, CAIRO_MID)
    items = v2_node.logic('v2sBrainItems', {'items': [_it('a', 'done_alone', label='م١', at='2026-10-30T11:00:00Z')]})
    rows = v2_node.logic('v2sBrainLogRows', ent, [], CAIRO_MID, items)
    assert [r['kind'] for r in rows] == ['item', 'file']
    assert len(v2_node.logic('v2sBrainLogRows', ent, [], CAIRO_MID)) == 1, 'بلا عناصر ⇒ السلوك القديم كما هو'
    assert [r['kind'] for r in v2_node.logic('v2sBrainLogRows', None, [], CAIRO_MID, items)] == ['item'], 'سجل الملفات الفاشل لا يُخفي عناصر العقل'


@needs_node
def test_run_state_and_run_info():
    rs = lambda r, now=NOW: v2_node.logic('v2sBrainRunState', r, now)
    assert rs(None) == {'known': False, 'active': False}
    assert rs({'run': None}) == {'known': True, 'active': False}
    assert rs({'run': {'started_at': '2026-10-30T11:55:00Z', 'finished_at': None}})['active'] is True
    assert rs({'run': {'started_at': '2026-10-30T11:55:00Z', 'finished_at': '2026-10-30T11:58:00Z'}})['active'] is False
    assert rs({'run': {'started_at': '2026-10-30T11:00:00Z', 'finished_at': None}})['active'] is False, 'جولة عالقة منذ أكثر من ١٥ دقيقة لا تقفل الزرّ'
    sw = v2_node.logic('v2sBrainSwitches', _sw_resp(), NOW)
    info = lambda s, r: v2_node.logic('v2sBrainRunInfo', s, r, NOW)
    ok = info(sw, {'known': True, 'active': False})
    assert ok == {'canStart': True, 'active': False, 'reason': '', 'n': 20, 'lead': 'يكتب العقل الآن ما ينقص من اقتراحات، بحد أقصى ٢٠ كتابة.'}
    assert info(sw, {'known': True, 'active': True})['canStart'] is False and info(sw, {'known': True, 'active': True})['reason'] == 'العقل يكتب الآن'
    low = v2_node.logic('v2sBrainSwitches', _sw_resp(brain_today={'used': 58, 'cap': 60}), NOW)
    assert info(low, None)['n'] == 2 and info(low, None)['lead'].endswith('بحد أقصى كتابتين.')
    full = v2_node.logic('v2sBrainSwitches', _sw_resp(brain_today={'used': 60, 'cap': 60}), NOW)
    assert info(full, None)['canStart'] is False and info(full, None)['reason'] == 'بلغ العقل حدّ كتابته اليوم'
    nowriter = v2_node.logic('v2sBrainSwitches', _sw_resp(writer=None), NOW)
    assert info(nowriter, None)['canStart'] is False and info(nowriter, None)['reason'] == 'لا كاتب مفعّل الآن'
    unknown = v2_node.logic('v2sBrainSwitches', _sw_resp(brain_today=None), NOW)
    assert info(unknown, None)['canStart'] is True and 'بحد أقصى' not in info(unknown, None)['lead'], 'عدّاد غير معروف ⇒ لا رقم مخترع'


@needs_node
def test_line_case_2b_waiting_proposals_sits_between_off_and_counts():
    ent = {'entries': [], 'autoCount': 4, 'changedCount': 0, 'partial': False, 'missing': False, 'fromInbox': False}
    off = dict(B2_OK, auto_assign=dict(B2_OK['auto_assign'], value=False))
    line = lambda **k: v2_node.logic('v2sBrainLine', k)
    for n, word in ((1, 'اقتراح واحد'), (2, 'اقتراحان'), (3, '٣ اقتراحات'), (11, '١١ اقتراحًا')):
        r = line(queue=QUEUE_OK, settings=B2_OK, entries=ent, proposed=n)
        assert r['text'] == 'ينتظرك من العقل: ' + word and r['button'] == {'label': 'ابدأ القرارات', 'section': 'home', 'deck': True}, r
    # التوزيع المتوقّف مع ملفات تنتظر أهم، والتنبيه المتوقّف أهم منهما
    assert line(queue=QUEUE_OK, settings=off, entries=ent, proposed=2)['text'].startswith('التوزيع التلقائي متوقّف')
    stopped = dict(QUEUE_OK, alerts=['⚠️ حارس المهلة والاسترداد: متوقّفة منذ 5 ساعة، والحدّ المسموح 2 ساعة'])
    assert line(queue=stopped, settings=B2_OK, entries=ent, proposed=2)['text'].startswith('حارس المهلة والاسترداد')
    # لا اقتراحات (٠ أو غير معروف) ⇒ السطر القديم بلا تغيير
    for p in (0, None):
        assert line(queue=QUEUE_OK, settings=B2_OK, entries=ent, proposed=p)['text'] == 'وُزّع اليوم ٤ ملفات وحده.'


def test_brain2_wiring_in_brain_js():
    js = _read('dashboard-cloud', 'v2s', 'brain.js')
    # المسارات والتأكيد: كل كتابة ببدن confirmed:true، والمسارات من SPEC §2.5
    assert "'/v2/brain/switches'" in js and "'/v2/brain/runs/latest'" in js and "'/v2/brain/items?status=all&since='" in js
    assert "'/v2/brain/switches/' + encodeURIComponent(id), { method: 'PUT', body: { mode: mode, confirmed: true } }" in js
    assert "'/v2/brain/items/' + encodeURIComponent(id) + '/discard', { method: 'POST', body: { confirmed: true } }" in js
    assert "'/v2/brain/run', { method: 'POST', body: { confirmed: true } }" in js and js.count("'/v2/brain/run'") == 1
    for t in ('حُفظ الاختيار', 'بدأ العقل الكتابة', 'حُذفت الملاحظة', 'اكتب الاقتراحات الآن', 'نعم، ابدأ', 'ما يكتبه العقل', 'اقتراحات يكتبها العقل من بيانات حقيقية',
              'أين ترى نتيجته', 'من يكتب الآن', 'كتابات العقل اليوم', 'تُحذف هذه الملاحظة. لم تغيّر شيئًا في المنصة.'):
        assert t in js, t
    assert 'role="radiogroup"' in js and 'role="radio"' in js and 'openSection(r.link.section)' in js
    # «ابدأ القرارات» تفتح الرئيسية ثم تضغط زرّ البدء الموجود، لا مدخل آخر
    assert "openSection('home')" in js and '[data-a="start"]' in js
    # الزرّ يعطَّل أثناء جولة نشطة: من حالة المصدر لا من حالة محلية فقط
    assert 'L.v2sBrainRunInfo(sw, runState(), now())' in js and '(ri.canStart ? \'\' : \' disabled\')' in js
    # لا نعرض صفرًا ولا null: القرصان يمرّان على «غير متاح بعد»
    assert 'L.v2sBrainWriterText(' in js and 'L.v2sBrainWritesToday(' in js
    css = _read('dashboard-cloud', 'v2s', 'brain.css')
    assert '.v2sb-md button{min-height:44px' in css and re.search(r'\.v2sb-row\.has-md \.v2sb-md button\{flex:1;min-width:0;min-height:52px', css)


def test_brain2_new_copy_passes_the_rules():
    """SPEC §4.5 على نصوص الجولة الثانية: فصحى محايدة · بلا «يقوّم/اعكس/⇒/✓/لما » · بلا لاتينية · لا عنوان يبدأ بـ«الذكاء» · لا «0/null/undefined»."""
    js = _read('dashboard-cloud', 'v2s', 'brain.js')
    logic = _read('dashboard-cloud', 'v2-logic.js')
    block = logic[logic.index('// ===== v2s:brain ====='):logic.index('// ===== /v2s:brain =====')]
    fresh = block[block.index('// —— ما يكتبه العقل (الجولة الثانية)'):block.index('// —— القواعد')]
    texts = _visible_copy(fresh) + _visible_copy(js[js.index('// —— مجموعة «ما يكتبه العقل»') if '// —— مجموعة «ما يكتبه العقل»' in js else 0:])
    assert len(texts) > 60
    for t in texts:
        for bad in FORBIDDEN + ['null', 'undefined']:
            assert not re.search(r'(?<![؀-ۿ])' + re.escape(bad), t), (bad, t)
        assert not re.search(r'[A-Za-z0-9]', t), t
        assert not re.match(r'^\s*(الذكاء|AI)', t), t
    # لا ادعاء أن رد الموقع أُرسل بالبريد
    assert not re.search(r'(أُرسل|أرسلنا|وصل)[^.]{0,20}(بريد|إيميل)', ' '.join(texts))
