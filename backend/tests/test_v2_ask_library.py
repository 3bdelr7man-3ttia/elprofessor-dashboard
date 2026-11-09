# -*- coding: utf-8 -*-
"""«أدخل قوانين المكتبة» (المحتوى ‹ أدخل قوانين المكتبة): مسارات الداشبورد فوق جسور المنصة `library-scan` و`ingest-library` و`corpus/stats`.

Run:  cd backend && python3 -B -m pytest -q -p no:cacheprovider tests/test_v2_ask_library.py

⛔ صفر شبكة وصفر ذكاء: المنصة بديل في الذاكرة، وأي عنوان برّه `https://platform.test` بيوقّع الاختبار. النصوص تجريبية مش قانون حقيقي.
اللي بيثبّته: القراءة من الجسر (قايمة بيضا) · المعاينة بلا كتابة ولا تدقيق · الإدخال بـ`confirmed:true` و`by` من التوكن وتدقيق `ask.ingest_library` ·
أدمن بس والمفتاح مقفول ٤٠٤ بلا نداء · ٤٠٤ الجسر ⇒ `bridge_missing` · ٤٠٤ عربي من المنصة يعدّي · التحقق قبل النداء · رد ضايع ⇒ ٥٠٢ `no_reply`.
"""
import datetime
import json
import os

import jwt
import pytest
from werkzeug.security import generate_password_hash

from app import app as flask_app, db, User, AuditLog  # noqa: E402

_HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(_HERE))
PLATFORM = 'https://platform.test'
SECRET = 'test-metrics-secret'
NON_ADMIN_ROLES = ['employee', 'trainer', 'investor', 'viewer', 'pending']
ADMIN_EMAIL = 'v2al-admin@x.test'
CONFIRM_AR = 'لازم تأكّد الأول من الشاشة'
MISSING_AR = 'الميزة لسه ما وصلتش المنصة'
AP = 'eg-administrative-prosecution'
A = '/api/v2/ask/library'

SCAN = {'items': [
    {'id': 'doc1', 'title': 'قانون تجريبي أول', 'law_number': '117 لسنة 1958', 'law_key': '117/1958', 'country': 'مصر', 'category': 'قانون',
     'specialization': 'إداري', 'chars': 12000, 'articles_found': 40, 'suggested_track': AP, 'secret_field': 'x',
     'ingested': {'total': 3, 'by_status': {'library': 3, 'weird': 9}}},
    {'id': 'doc2', 'title': 'لائحة تجريبية', 'law_number': '', 'law_key': '', 'country': '', 'category': '', 'specialization': '',
     'chars': 500, 'articles_found': 0, 'suggested_track': None, 'ingested': {'total': 0, 'by_status': {}}},
    {'id': 'bad id!', 'title': 'x'}],
    'tracks': [{'id': AP, 'label': 'النيابة الإدارية'}, {'id': 'BAD', 'label': 'x'}], 'count': 2}
STATS = {'articles': {AP: {'library': 3, 'verified': 10}}, 'corrections_approved': 2, 'served_statuses': ['verified'], 'secret': 'x'}
PREVIEW = {'articles': 40, 'preview': [{'article_no': i, 'text': 'نص تجريبي %d' % i} for i in range(1, 20)], 'duplicates': [{'article_no': 7}], 'applied': False,
           'law_key': '117/1958'}
APPLIED = dict(PREVIEW, applied=True, counts={'inserted': 30, 'updated': 2, 'kept': 8})


class _Resp(object):
    def __init__(self, status, payload):
        self.status_code = status
        self._p = payload
        self.content = json.dumps(payload, ensure_ascii=False).encode('utf-8') if payload is not None else b''
        self.headers = {'Content-Type': 'application/json'}

    def json(self):
        return self._p


class Plat(object):
    def __init__(self):
        self.seen = []
        self.blocked = []
        self.forced = {}       # path -> (status, payload)
        self.forced_write = {}  # path -> (status, payload) لنداء الكتابة (apply=true) فقط

    def __call__(self, method, url, params=None, json=None, headers=None, timeout=None, data=None, files=None):
        path = url[len(PLATFORM):] if url.startswith(PLATFORM) else url
        self.seen.append({'method': method.upper(), 'path': path, 'params': dict(params or {}), 'json': json, 'headers': dict(headers or {})})
        if not url.startswith(PLATFORM + '/'):
            self.blocked.append(url)
            raise RuntimeError('طلب حقيقي ممنوع: ' + url)
        if (json or {}).get('apply') and path in self.forced_write:
            return _Resp(*self.forced_write[path])
        if path in self.forced:
            f = self.forced[path]
            if isinstance(f, Exception):
                raise f
            return _Resp(*f)
        if path == '/api/bridge/ask/library-scan':
            return _Resp(200, SCAN)
        if path == '/api/bridge/ask/corpus/stats':
            return _Resp(200, STATS)
        if path == '/api/bridge/ask/ingest-library':
            return _Resp(200, APPLIED if (json or {}).get('apply') else PREVIEW)
        return _Resp(404, {'detail': 'Not Found'})

    def calls(self, prefix=''):
        return [c for c in self.seen if c['path'].startswith(prefix)]


@pytest.fixture(scope='module')
def ctx():
    with flask_app.app_context():
        db.create_all()

        def mk(email, role):
            u = User.query.filter_by(email=email).first() or User(
                email=email, password_hash=generate_password_hash('x', method='pbkdf2:sha256'), name=email.split('@')[0], role=role,
                dashboard_role=role, linked_to_name='', preferred_currency='AUTO', is_active=True)
            u.role = u.dashboard_role = role
            db.session.add(u)
            db.session.commit()
            tok = jwt.encode({'user_id': u.id, 'exp': datetime.datetime.utcnow() + datetime.timedelta(days=1)}, flask_app.config['SECRET_KEY'], algorithm='HS256')
            return {'Authorization': 'Bearer ' + tok}
        heads = {r: mk('v2al-%s@x.test' % r, r) for r in NON_ADMIN_ROLES}
        heads['admin'] = mk(ADMIN_EMAIL, 'admin')
        yield {'heads': heads, 'client': flask_app.test_client()}


@pytest.fixture
def plat(monkeypatch):
    import app as appmod
    p = Plat()
    monkeypatch.setattr(appmod, 'PLATFORM_METRICS_SECRET', SECRET)
    monkeypatch.setattr(appmod, 'PLATFORM_API_URL', PLATFORM)
    monkeypatch.setattr(appmod.requests, 'request', p)
    monkeypatch.setenv('DASH_V2_ENABLED', 'true')
    yield p
    assert p.blocked == [], p.blocked


def call(ctx, method, path, body=None, role='admin'):
    k = {'headers': ctx['heads'][role] if role else {}}
    if body is not None:
        k['json'] = body
    return ctx['client'].open(path, method=method, **k)


def audits():
    with flask_app.app_context():
        return [(a.action, a.target, json.loads(a.meta_json or 'null'), a.actor_email)
                for a in AuditLog.query.filter(AuditLog.action.like('ask.%')).order_by(AuditLog.id).all()]


def body(**kw):
    b = {'track': AP, 'ref_id': 'doc1'}
    b.update(kw)
    return b


# ---------------------------------------------------------------- القراءة

def test_scan_reads_the_bridge_and_whitelists_everything(ctx, plat):
    r = call(ctx, 'GET', A)
    d = r.get_json()
    assert r.status_code == 200 and r.headers['Cache-Control'] == 'no-store'
    assert [i['id'] for i in d['items']] == ['doc1', 'doc2'], 'معرّف غير صالح يُسقط'
    first = d['items'][0]
    assert 'secret_field' not in first and first['suggested_track'] == AP and first['law_key'] == '117/1958' and first['articles_found'] == 40
    assert first['ingested'] == {'total': 3, 'by_status': {'library': 3}}, 'حالات مجهولة تُسقط'
    assert d['items'][1]['suggested_track'] is None and d['items'][1]['law_key'] is None
    assert d['tracks'] == [{'id': AP, 'label': 'النيابة الإدارية'}]
    assert d['stats'] == {'articles': {AP: {'library': 3, 'verified': 10}}, 'corrections_approved': 2}
    scan = plat.calls('/api/bridge/ask/library-scan')[0]
    assert scan['params'] == {'limit': 500} and scan['headers'].get('X-ELP-Metrics-Secret') == SECRET
    assert plat.calls('/api/bridge/ask/corpus/stats')


def test_scan_survives_a_missing_stats_bridge(ctx, plat):
    plat.forced['/api/bridge/ask/corpus/stats'] = (404, {'detail': 'Not Found'})
    r = call(ctx, 'GET', A)
    assert r.status_code == 200 and r.get_json()['stats'] is None and len(r.get_json()['items']) == 2


def test_scan_404_is_the_quiet_bridge_missing_message(ctx, plat):
    plat.forced['/api/bridge/ask/library-scan'] = (404, {'detail': 'Not Found'})
    r = call(ctx, 'GET', A)
    assert r.status_code == 404 and r.get_json() == {'error': MISSING_AR, 'bridge_missing': True}


def test_scan_bad_shape_is_502_not_empty(ctx, plat):
    plat.forced['/api/bridge/ask/library-scan'] = (200, {'oops': 1})
    assert call(ctx, 'GET', A).status_code == 502


def test_scan_platform_rejecting_the_secret_never_logs_the_admin_out(ctx, plat):
    plat.forced['/api/bridge/ask/library-scan'] = (401, {'detail': 'x'})
    assert call(ctx, 'GET', A).status_code == 502


# ---------------------------------------------------------------- المعاينة (بلا كتابة)

def test_preview_sends_apply_false_and_returns_first_15_with_duplicates(ctx, plat):
    r = call(ctx, 'POST', A + '/preview', body(law=' 117/1958 '))
    d = r.get_json()
    assert r.status_code == 200 and d['applied'] is False and d['articles'] == 40 and len(d['preview']) == 15 and d['duplicates'] == ['7']
    sent = plat.calls('/api/bridge/ask/ingest-library')[-1]['json']
    assert sent == {'track': AP, 'ref_id': 'doc1', 'as_proposed': False, 'law': '117/1958', 'apply': False}
    assert 'by' not in sent
    n = len(audits())
    call(ctx, 'POST', A + '/preview', body())
    assert len(audits()) == n, 'المعاينة بلا تدقيق'


def test_preview_does_not_need_confirmation_but_validates_first(ctx, plat):
    for b in ({'ref_id': 'doc1'}, {'track': 'BAD TRACK', 'ref_id': 'doc1'}, body(ref_id='a b'), body(ref_id=''), body(law='x' * 61)):
        assert call(ctx, 'POST', A + '/preview', b).status_code == 400, b
    assert plat.seen == []


def test_preview_missing_law_422_text_from_platform_passes_through(ctx, plat):
    plat.forced['/api/bridge/ask/ingest-library'] = (422, {'detail': 'حدّد رقم القانون (مثال 117/1958)'})
    r = call(ctx, 'POST', A + '/preview', body())
    assert r.status_code == 422 and r.get_json()['error'] == 'حدّد رقم القانون (مثال 117/1958)'


def test_preview_arabic_404_is_not_the_bridge_missing(ctx, plat):
    plat.forced['/api/bridge/ask/ingest-library'] = (404, {'detail': 'المستند غير موجود'})
    r = call(ctx, 'POST', A + '/preview', body())
    assert r.status_code == 404 and r.get_json() == {'error': 'المستند غير موجود'}


def test_preview_generic_404_is_the_bridge_missing(ctx, plat):
    plat.forced['/api/bridge/ask/ingest-library'] = (404, {'detail': 'Not Found'})
    r = call(ctx, 'POST', A + '/preview', body())
    assert r.status_code == 404 and r.get_json().get('bridge_missing') is True and r.get_json()['error'] == MISSING_AR


# ---------------------------------------------------------------- الإدخال (كتابة)

def test_ingest_needs_exact_confirmation_before_any_call(ctx, plat):
    for c in (None, 'true', 1, False):
        b = body()
        if c is not None:
            b['confirmed'] = c
        r = call(ctx, 'POST', A + '/ingest', b)
        assert r.status_code == 400 and r.get_json()['error'] == CONFIRM_AR, c
    assert plat.seen == []


def test_ingest_writes_through_v2_write_with_by_from_token_and_audits(ctx, plat):
    before = len(audits())
    r = call(ctx, 'POST', A + '/ingest', body(confirmed=True, law='117/1958', by='attacker@x.test', apply=False, extra='x'))
    d = r.get_json()
    assert r.status_code == 200 and d['applied'] is True and d['counts'] == {'inserted': 30, 'updated': 2, 'kept': 8}
    sent = plat.calls('/api/bridge/ask/ingest-library')[-1]['json']
    assert sent == {'track': AP, 'ref_id': 'doc1', 'as_proposed': False, 'law': '117/1958', 'apply': True, 'by': ADMIN_EMAIL}, 'by من التوكن وapply مفروضة'
    new = audits()[before:]
    assert len(new) == 1 and new[0][0] == 'ask.ingest_library' and new[0][1] == 'doc1' and new[0][3] == ADMIN_EMAIL
    assert new[0][2] == {'track': AP, 'as_proposed': False}


def test_ingest_failure_writes_no_audit(ctx, plat):
    plat.forced['/api/bridge/ask/ingest-library'] = (422, {'detail': 'حدّد رقم القانون (مثال 117/1958)'})
    before = len(audits())
    r = call(ctx, 'POST', A + '/ingest', body(confirmed=True))
    assert r.status_code == 422 and len(audits()) == before


def test_ingest_lost_reply_is_502_no_reply(ctx, plat):
    plat.forced_write['/api/bridge/ask/ingest-library'] = (503, {'detail': 'x'})
    r = call(ctx, 'POST', A + '/ingest', body(confirmed=True))
    assert r.status_code == 502 and r.get_json().get('no_reply') is True


def test_ingest_bridge_missing_is_quiet(ctx, plat):
    plat.forced['/api/bridge/ask/ingest-library'] = (404, {'detail': 'Not Found'})
    r = call(ctx, 'POST', A + '/ingest', body(confirmed=True))
    assert r.status_code == 404 and r.get_json()['error'] == MISSING_AR


# ---------------------------------------------------------------- الصلاحية والمفتاح

PATHS = [('GET', A, None), ('POST', A + '/preview', body()), ('POST', A + '/ingest', body(confirmed=True))]


@pytest.mark.parametrize('role', NON_ADMIN_ROLES)
def test_admin_only(ctx, plat, role):
    for m, p, b in PATHS:
        assert call(ctx, m, p, b, role=role).status_code == 403, (role, p)
        assert call(ctx, m, p, b, role=None).status_code == 401
    assert plat.seen == []


def test_switch_off_is_404_with_no_platform_call(ctx, plat, monkeypatch):
    monkeypatch.delenv('DASH_V2_ENABLED', raising=False)
    for m, p, b in PATHS:
        r = call(ctx, m, p, b)
        assert r.status_code == 404 and r.headers.get('Cache-Control') == 'no-store', p
    assert plat.seen == []


# ---------------------------------------------------------------- الواجهة (ساكن)

def _read(*parts):
    with open(os.path.join(ROOT, *parts), encoding='utf-8') as fh:
        return fh.read()


def test_the_tab_the_files_and_the_dockerfile_are_wired():
    logic = _read('dashboard-cloud', 'v2-logic.js')
    sec = logic[logic.index("{ key: 'content', label: 'المحتوى', img: 'content', desc:"):]
    sec = sec[:sec.index("{ key: 'marketing'")]
    assert "T('asklib',    'أدخل قوانين المكتبة', 'v2s_asklib')" in sec and sec.index("'v2s_glossary'") < sec.index("'v2s_asklib'") < sec.index("topicsTab: 'tutorials'")
    html = _read('dashboard-cloud', 'index.html')
    block = html[html.index('<!-- v2 sections begin -->'):html.index('<!-- v2 sections end -->')]
    assert block.count('<script src="v2s/asklib.js"></script>') == 1 and '<link rel="stylesheet" href="v2s/asklib.css">' in block
    js = _read('dashboard-cloud', 'v2s', 'asklib.js')
    assert "(window.V2SEC = window.V2SEC || {}).asklib = { owns: A.owns, render: A.render };" in js
    assert "/v2/ask/library/preview" in js and "/v2/ask/library/ingest" in js and 'confirmed: true' in js and 'الميزة لسه ما وصلتش المنصة' in js
    assert 'confirm(' not in js.replace('confirmed', '') and 'prompt(' not in js
    assert 'COPY backend/v2_asklib_routes.py /app/v2_asklib_routes.py' in _read('Dockerfile')
    assert 'v2_asklib_routes' in _read('backend', 'app.py')


def test_ingest_with_zero_articles_is_refused_before_write_and_no_audit(ctx, plat):
    plat.forced['/api/bridge/ask/ingest-library'] = (200, {'articles': 0, 'preview': [], 'duplicates': [], 'applied': False, 'law_key': '117/1958'})
    before = len(audits())
    r = call(ctx, 'POST', A + '/ingest', body(confirmed=True))
    assert r.status_code == 400 and len(audits()) == before
    assert all(not c['json'].get('apply') for c in plat.calls('/api/bridge/ask/ingest-library'))


def test_law_number_over_twenty_chars_is_refused_in_arabic_before_the_platform(ctx, plat):
    r = call(ctx, 'POST', A + '/preview', body(law='القانون رقم 117 لسنة 1958'))
    assert r.status_code == 400 and r.get_json()['error'] == 'رقم القانون غير صالح (مثال 117/1958)' and plat.seen == []


def test_scan_passes_pending_and_waits_longer_than_default():
    import v2_asklib_routes as m
    v = m.view_scan({'items': [], 'tracks': [], 'count': 0, 'pending': 7})
    assert v['pending'] == 7
    assert m.view_scan({'items': []})['pending'] == 0
    src = open(m.__file__, encoding='utf-8').read()
    assert "'/api/bridge/ask/library-scan', params={'limit': SCAN_LIMIT}, timeout=30" in src


def test_asklib_js_declares_every_constant_it_uses():
    """SCAN_CAP كان مستخدم من غير تعريف ⇒ ReferenceError في رسم «جاهز» ⇒ «تعذّر جلب مستندات المكتبة» دايمًا."""
    import os, re
    src = open(os.path.join(os.path.dirname(__file__), '..', '..', 'dashboard-cloud', 'v2s', 'asklib.js'), encoding='utf-8').read()
    code = re.sub(r"//[^\n]*|'(?:\\.|[^'\\])*'", '', src)
    used = set(re.findall(r'(?<![.\w])([A-Z][A-Z_0-9]{2,})\b', code))   # مش خاصية (window.X)
    declared = set(re.findall(r'var\s+([A-Z][A-Z_0-9]+)', code))
    assert used <= declared, used - declared
