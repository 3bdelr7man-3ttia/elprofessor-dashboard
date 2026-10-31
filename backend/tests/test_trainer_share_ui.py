# -*- coding: utf-8 -*-
"""شاشة «نسبة المدرّب» (SPEC-C-courses C2b) — البروكسي `/api/v2/trainer-share*` + منطق الشاشة النقي (node) + توصيل الملفات.

Run:  cd backend && python3 -B -m pytest -q -p no:cacheprovider tests/test_trainer_share_ui.py

⛔ صفر شبكة حقيقية: المنصة جدول في الذاكرة، وأي عنوان برّه `https://platform.test` يوقّع الاختبار.
اللي بيثبّته:
  ١. المسارات (pytest): أدمن بس · المفتاح مقفول ٤٠٤ بلا نداء · `no-store` · الكتابة تطلب `confirmed:true` بالظبط · `by` من التوكن لا من الجسم ·
     القايمة البيضا (لا سقف ولا سعر ولا حقل زائد) · الحدود (٣٥–٦٥ صحيح · ٠–٢٥ · السبب ٣ حروف) قبل أي نداء · نص المنصة العربي يمرّ كما هو ·
     ٤٠١/٤٠٣ ⇒ ٥٠٢ · رد ضايع ⇒ ٥٠٢ `no_reply` بنداء واحد · التدقيق عند النجاح بس.
  ٢. المنطق (node): نصيب المدرّب `min(65, max(base, …)+bonus)` · مدة الزيادة · تحقق الورقة · قراءة الردود · إيداعات الإعلانات.
  ٣. التوصيل: app.py · Dockerfile · index.html · خطّاف courses.js.
"""
import datetime
import json
import os
import subprocess
import sys

import jwt
import pytest
from werkzeug.security import generate_password_hash

from app import app as flask_app, db, User, AuditLog  # noqa: E402

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(_HERE, 'uiharness'))
import v2_node  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(_HERE))
PLATFORM = 'https://platform.test'
SECRET = 'test-metrics-secret'
NON_ADMIN_ROLES = ['employee', 'trainer', 'investor', 'viewer', 'pending']
needs_node = pytest.mark.skipif(not v2_node.NODE, reason='needs node')
ADMIN_EMAIL = 'v2ts-admin@x.test'
CONFIRM_AR = 'لازم تأكّد الأول من الشاشة'
TRAINER = 'hala@example.test'
JS_PATH = os.path.join(ROOT, 'dashboard-cloud', 'v2s', 'trainer_share.js')


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
        heads = {r: _bearer(_mkuser('v2ts-%s@x.test' % r, r)) for r in NON_ADMIN_ROLES}
        heads['admin'] = _bearer(_mkuser(ADMIN_EMAIL, 'admin'))
        yield {'heads': heads, 'client': flask_app.test_client()}


ROW = {'email': TRAINER, 'name': 'هالة', 'base_pct': 50, 'ads_bonus_pts': 5, 'reason': 'إعلان ممول', 'from': '2026-11-01T00:00:00', 'until': '2026-11-30T23:59:59',
       'updated_at': '2026-10-31T10:00:00', 'updated_by': 'founder@x.test'}


class Plat(object):
    """المنصة في الذاكرة: تسجّل كل نداء، و`forced[(method, path)] = (status, body)` يفرض ردًّا."""

    def __init__(self):
        self.seen = []
        self.blocked = []
        self.forced = {}

    def __call__(self, method, url, params=None, json=None, headers=None, timeout=None):
        import copy
        self.seen.append({'method': method.upper(), 'path': url[len(PLATFORM):], 'json': copy.deepcopy(json), 'headers': dict(headers or {})})
        if not url.startswith(PLATFORM + '/'):
            self.blocked.append(url)
            raise RuntimeError('طلب حقيقي ممنوع: ' + url)
        key = (method.upper(), url[len(PLATFORM):])
        if key in self.forced:
            return _Resp(*self.forced[key])
        path = key[1]
        if path == '/api/bridge/trainer-share':
            return _Resp(200, {'items': [ROW]})
        if path.startswith('/api/bridge/trainer-share/'):
            if method.upper() == 'PUT':
                return _Resp(200, {'ok': True, 'item': dict(ROW, **{k: v for k, v in (json or {}).items() if k in ('base_pct', 'ads_bonus_pts', 'reason')})})
            return _Resp(200, dict(ROW, limits={'min': 35, 'max': 65, 'ads_bonus_max': 25}, history=[{'base_pct': 40, 'ads_bonus_pts': 0, 'reason': 'بداية', 'at': '2026-10-01T09:00:00', 'by': 'a@x.test'}]))
        if path == '/api/bridge/trainer-share-rules':
            if method.upper() == 'PUT':
                return _Resp(200, {'ok': True, 'code_min_pct': (json or {}).get('code_min_pct'), 'cap_pct': 65})
            return _Resp(200, {'code_min_pct': 50, 'cap_pct': 65, 'rev': 3, 'updated_at': '2026-10-30T10:00:00', 'updated_by': 'f@x.test'})
        return _Resp(404, {'detail': 'x'})

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


OK_PUT = {'base_pct': 55, 'ads_bonus_pts': 10, 'reason': 'زيادة بسبب إعلان ممول', 'from': '2026-11-01', 'until': '2026-11-30'}
ROUTES = [
    ('GET', '/api/v2/trainer-share', None),
    ('GET', '/api/v2/trainer-share/' + TRAINER, None),
    ('GET', '/api/v2/trainer-share-rules', None),
    ('PUT', '/api/v2/trainer-share/' + TRAINER, OK_PUT),
    ('PUT', '/api/v2/trainer-share-rules', {'code_min_pct': 55, 'reason': 'رفع الحد'}),
]


def _call(ctx, method, path, body, who='admin'):
    heads = {} if who is None else ctx['heads'][who]
    c = ctx['client']
    return c.get(path, headers=heads) if method == 'GET' else c.put(path, headers=heads, json=body)


# ---------------------------------------------------------------- ١) الصلاحيات والمفتاح
@pytest.mark.parametrize('method,path,body', ROUTES)
def test_admin_only_flag_and_no_store(ctx, plat, monkeypatch, method, path, body):
    b = dict(body or {}, confirmed=True) if method == 'PUT' else None
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
    assert all(c['headers'].get('X-ELP-Metrics-Secret') == SECRET for c in plat.seen)


def test_get_paths_map_to_bridge(ctx, plat):
    assert _call(ctx, 'GET', '/api/v2/trainer-share', None).get_json()['items'][0]['email'] == TRAINER
    one = _call(ctx, 'GET', '/api/v2/trainer-share/' + TRAINER.upper(), None).get_json()
    assert one['limits'] == {'min': 35, 'max': 65, 'ads_bonus_max': 25} and one['history'][0]['reason'] == 'بداية'
    assert _call(ctx, 'GET', '/api/v2/trainer-share-rules', None).get_json()['code_min_pct'] == 50
    assert [c['path'] for c in plat.seen] == ['/api/bridge/trainer-share', '/api/bridge/trainer-share/' + TRAINER.replace('@', '%40'), '/api/bridge/trainer-share-rules']
    assert all(c['method'] == 'GET' and c['json'] is None for c in plat.seen)


def test_bad_email_is_refused_before_any_call(ctx, plat):
    for bad in ('nobody', 'a@b', 'a b@x.test', 'a%20b@x.test', 'x' * 300 + '@x.test'):
        assert _call(ctx, 'GET', '/api/v2/trainer-share/' + bad, None).status_code in (400, 404), bad
        r = _call(ctx, 'PUT', '/api/v2/trainer-share/' + bad, dict(OK_PUT, confirmed=True))
        assert r.status_code in (400, 404), bad
    assert plat.seen == []


# ---------------------------------------------------------------- ٢) التأكيد و`by` والقايمة البيضا
@pytest.mark.parametrize('path,body', [(p, b) for m, p, b in ROUTES if m == 'PUT'])
@pytest.mark.parametrize('bad', [None, 'true', 1, False, 'yes'])
def test_confirmed_must_be_literally_true(ctx, plat, path, body, bad):
    b = dict(body)
    if bad is not None:
        b['confirmed'] = bad
    r = _call(ctx, 'PUT', path, b)
    assert r.status_code == 400 and r.get_json()['error'] == CONFIRM_AR
    assert r.headers.get('Cache-Control') == 'no-store'
    assert plat.seen == []


def test_put_sends_exact_whitelisted_body_with_by_from_token(ctx, plat):
    r = _call(ctx, 'PUT', '/api/v2/trainer-share/' + TRAINER.upper(),
              dict(OK_PUT, confirmed=True, by='attacker@x.test', cap_pct=99, price_egp=5, trainer_share_pct=90, email='other@x.test', source='trainer_code'))
    assert r.status_code == 200
    (w,) = plat.writes()
    assert w['method'] == 'PUT' and w['path'] == '/api/bridge/trainer-share/' + TRAINER.replace('@', '%40')
    assert w['json'] == {'base_pct': 55, 'ads_bonus_pts': 10, 'reason': 'زيادة بسبب إعلان ممول', 'from': '2026-11-01', 'until': '2026-11-30',
                         'confirmed': True, 'by': ADMIN_EMAIL}


def test_put_without_bonus_period_and_default_bonus(ctx, plat):
    assert _call(ctx, 'PUT', '/api/v2/trainer-share/' + TRAINER, {'base_pct': 40, 'reason': '  سبب   مرتب  ', 'confirmed': True, 'from': '', 'until': None}).status_code == 200
    (w,) = plat.writes()
    assert w['json'] == {'base_pct': 40, 'ads_bonus_pts': 0, 'reason': 'سبب مرتب', 'confirmed': True, 'by': ADMIN_EMAIL}


@pytest.mark.parametrize('patch', [
    {'base_pct': 34}, {'base_pct': 66}, {'base_pct': 50.5}, {'base_pct': '50'}, {'base_pct': True}, {'base_pct': None}, {'base_pct': -1},
    {'ads_bonus_pts': -1}, {'ads_bonus_pts': 26}, {'ads_bonus_pts': 2.5}, {'ads_bonus_pts': '3'}, {'ads_bonus_pts': True},
    {'reason': ''}, {'reason': 'ab'}, {'reason': '  a  '}, {'reason': None}, {'reason': 5},
    {'from': 'غدًا'}, {'from': '2026-13-01'}, {'until': '2026/11/30'}, {'from': 5},
    {'from': '2026-12-01', 'until': '2026-11-01'},
])
def test_put_limits_refused_before_any_call(ctx, plat, patch):
    r = _call(ctx, 'PUT', '/api/v2/trainer-share/' + TRAINER, dict(OK_PUT, confirmed=True, **patch))
    assert r.status_code == 400 and r.headers.get('Cache-Control') == 'no-store'
    assert isinstance(r.get_json()['error'], str) and r.get_json()['error']
    assert plat.seen == []


def test_put_accepts_the_edges(ctx, plat):
    for base, bonus in ((35, 0), (65, 25), (65, 0), (35, 25)):
        assert _call(ctx, 'PUT', '/api/v2/trainer-share/' + TRAINER, dict(OK_PUT, base_pct=base, ads_bonus_pts=bonus, confirmed=True)).status_code == 200
    assert [w['json']['base_pct'] for w in plat.writes()] == [35, 65, 65, 35]
    plat.seen.clear()
    assert _call(ctx, 'PUT', '/api/v2/trainer-share/' + TRAINER, dict(OK_PUT, confirmed=True, **{'from': '2026-11-01T10:00:00', 'until': '2026-11-01T11:00:00'})).status_code == 200


def test_rules_put_body_limits_and_cap_is_read_only(ctx, plat):
    assert _call(ctx, 'PUT', '/api/v2/trainer-share-rules', {'code_min_pct': 55, 'reason': 'رفع الحد', 'confirmed': True, 'by': 'x@y.test', 'price': 1}).status_code == 200
    (w,) = plat.writes()
    assert w['path'] == '/api/bridge/trainer-share-rules' and w['json'] == {'code_min_pct': 55, 'reason': 'رفع الحد', 'confirmed': True, 'by': ADMIN_EMAIL}
    plat.seen.clear()
    assert _call(ctx, 'PUT', '/api/v2/trainer-share-rules', {'code_min_pct': 55, 'reason': 'سبب', 'confirmed': True, 'cap_pct': 65}).status_code == 200
    assert 'cap_pct' not in plat.writes()[0]['json'], 'السقف لا يُرسَل أبدًا'
    plat.seen.clear()
    for patch in ({'code_min_pct': 34}, {'code_min_pct': 66}, {'code_min_pct': 50.5}, {'code_min_pct': '50'}, {'code_min_pct': None},
                  {'reason': 'ab'}, {'reason': None}, {'cap_pct': 70}, {'cap_pct': 'x'}, {'cap_pct': 64}):
        r = _call(ctx, 'PUT', '/api/v2/trainer-share-rules', dict({'code_min_pct': 55, 'reason': 'سبب', 'confirmed': True}, **patch))
        assert r.status_code == 400, patch
    assert plat.seen == []


# ---------------------------------------------------------------- ٣) أخطاء المنصة
def test_platform_arabic_detail_passes_through(ctx, plat):
    url = '/api/v2/trainer-share/' + TRAINER
    plat.forced[('PUT', '/api/bridge/trainer-share/' + TRAINER.replace('@', '%40'))] = (400, {'detail': 'الزيادة لا تزيد عن ٢٥ نقطة'})
    r = _call(ctx, 'PUT', url, dict(OK_PUT, confirmed=True))
    assert r.status_code == 400 and r.get_json()['error'] == 'الزيادة لا تزيد عن ٢٥ نقطة'
    plat.forced[('PUT', '/api/bridge/trainer-share/' + TRAINER.replace('@', '%40'))] = (404, {'detail': 'هذا المدرّب غير معتمد'})
    r = _call(ctx, 'PUT', url, dict(OK_PUT, confirmed=True))
    assert r.status_code == 404 and r.get_json()['error'] == 'هذا المدرّب غير معتمد'
    plat.forced[('GET', '/api/bridge/trainer-share')] = (404, {'detail': 'x'})
    assert _call(ctx, 'GET', '/api/v2/trainer-share', None).status_code == 404       # الجسر لسه ما اتنشرش ⇒ الشاشة تكتب «غير متاح بعد»


def test_platform_auth_failures_become_502(ctx, plat):
    for code in (401, 403):
        plat.forced[('PUT', '/api/bridge/trainer-share-rules')] = (code, {'detail': 'x'})
        plat.forced[('GET', '/api/bridge/trainer-share-rules')] = (code, {'detail': 'x'})
        r = _call(ctx, 'PUT', '/api/v2/trainer-share-rules', {'code_min_pct': 55, 'reason': 'سبب', 'confirmed': True})
        assert r.status_code == 502 and r.get_json()['error'] == 'تعذّر الاتصال بالمنصة'
        assert _call(ctx, 'GET', '/api/v2/trainer-share-rules', None).status_code == 502


def test_lost_reply_is_flagged_with_one_call_and_audit_only_on_success(ctx, plat):
    url = '/api/v2/trainer-share/' + TRAINER
    n_ok = AuditLog.query.filter_by(action='trainer_share.update').count()
    n_lost = AuditLog.query.filter(AuditLog.action.like('trainer_share.no_reply')).count()
    for code in (500, 502, 503, 504):
        plat.seen.clear()
        plat.forced[('PUT', '/api/bridge/trainer-share/' + TRAINER.replace('@', '%40'))] = (code, {})
        r = _call(ctx, 'PUT', url, dict(OK_PUT, confirmed=True))
        assert r.status_code == 502 and r.get_json().get('no_reply') is True, code
        assert len(plat.writes()) == 1, 'نداء واحد ولا إعادة محاولة'
    assert AuditLog.query.filter_by(action='trainer_share.update').count() == n_ok
    assert AuditLog.query.filter(AuditLog.action.like('trainer_share.no_reply')).count() == n_lost + 4
    plat.forced.clear()
    assert _call(ctx, 'PUT', url, dict(OK_PUT, confirmed=True)).status_code == 200
    rows = AuditLog.query.filter_by(action='trainer_share.update').all()
    assert len(rows) == n_ok + 1 and rows[-1].actor_email == ADMIN_EMAIL and rows[-1].target == TRAINER
    assert _call(ctx, 'PUT', '/api/v2/trainer-share-rules', {'code_min_pct': 52, 'reason': 'سبب', 'confirmed': True}).status_code == 200
    assert AuditLog.query.filter_by(action='trainer_share.rules').count() >= 1


# ---------------------------------------------------------------- ٤) التوصيل
def test_wiring_app_dockerfile_index_and_hook():
    app_src = _read('backend', 'app.py')
    i, j = app_src.index('import v2_courses_routes; v2_courses_routes.register(app, globals())'), app_src.index('import v2_trainer_share_routes as _v2ts')
    assert 0 < j - i < 200, 'سطر التسجيل بعد تسجيل الدورات مباشرة'
    assert "except Exception: logger.exception('v2 trainer share routes not loaded')" in app_src
    assert 'COPY backend/v2_trainer_share_routes.py /app/v2_trainer_share_routes.py' in _read('Dockerfile')
    html = _read('dashboard-cloud', 'index.html')
    assert '<link rel="stylesheet" href="v2s/trainer_share.css">\n<script src="v2s/trainer_share.js"></script>' in html
    assert html.index('v2s/trainer_share.js') < html.index('<!-- v2 sections end -->')
    courses_js = _read('dashboard-cloud', 'v2s', 'courses.js')
    assert courses_js.count('V2TS') == 2, 'خطّاف صغير واحد في courses.js'
    assert "window.V2TS.mount(q('.v2co', v))" in courses_js
    css = _read('dashboard-cloud', 'v2s', 'trainer_share.css')
    import re
    css = re.sub(r'/\*.*?\*/', '', css, flags=re.S)
    sels = [s.strip() for blk in re.findall(r'([^{}]+)\{', css) if not blk.strip().startswith('@') for s in blk.split(',')]
    assert all(s.startswith('.v2ts') for s in sels if s), [s for s in sels if s and not s.startswith('.v2ts')][:3]


def test_copy_rules_in_screen_text():
    src = _read('dashboard-cloud', 'v2s', 'trainer_share.js')
    for bad in ('يقوّم', 'استرداد', 'ضمان', 'اعكس', 'null)'):
        assert bad not in src, bad
    assert 'أغلب' not in src


# ---------------------------------------------------------------- ٥) المنطق النقي (node)
def _node(script):
    p = subprocess.run([v2_node.NODE, '-e', 'const H = require(%s);\n%s' % (json.dumps(JS_PATH), script)], capture_output=True, text=True, timeout=60)
    assert p.returncode == 0, p.stderr[-1500:]
    return json.loads(p.stdout)


@needs_node
def test_node_total_share_helper():
    out = _node("""
const t = (b, o, x) => H.shareTotals(b, o, x);
console.log(JSON.stringify({
  plain: t(50, 0), withBonus: t(50, 10), capped: t(60, 25), capEdge: t(65, 0), floor: t(35, 0),
  viaCode: t(40, 5, {viaCode: true, codeMin: 50}), viaCodeHigherBase: t(60, 0, {viaCode: true, codeMin: 50}), viaCodeCapped: t(55, 25, {viaCode: true, codeMin: 60}),
  codeIgnoredWhenNotViaCode: t(40, 0, {codeMin: 55}), inactive: t(50, 10, {bonusActive: false}), garbage: t('x', null), line: H.totalLine(t(55, 5)),
}));""")
    assert out['plain'] == {'trainer': 50, 'platform': 50}
    assert out['withBonus'] == {'trainer': 60, 'platform': 40}
    assert out['capped'] == {'trainer': 65, 'platform': 35} and out['capEdge'] == {'trainer': 65, 'platform': 35}
    assert out['floor'] == {'trainer': 35, 'platform': 65}
    assert out['viaCode'] == {'trainer': 55, 'platform': 45}          # max(40، 50) + 5
    assert out['viaCodeHigherBase'] == {'trainer': 60, 'platform': 40}
    assert out['viaCodeCapped'] == {'trainer': 65, 'platform': 35}    # min(65، max(55، 60) + 25)
    assert out['codeIgnoredWhenNotViaCode'] == {'trainer': 40, 'platform': 60}
    assert out['inactive'] == {'trainer': 50, 'platform': 50}
    assert out['garbage'] == {'trainer': 35, 'platform': 65}
    assert out['line'] == 'نصيب المدرّب الآن: ٦٠٪ · المنصة ٤٠٪'


@needs_node
def test_node_total_never_below_platform_floor():
    out = _node("""
let worst = 0, bad = 0;
for (let b = 35; b <= 65; b++) for (let o = 0; o <= 25; o++) for (const vc of [false, true]) {
  const t = H.shareTotals(b, o, {viaCode: vc, codeMin: 50});
  worst = Math.max(worst, t.trainer); if (t.platform < 35 || t.trainer + t.platform !== 100 || t.trainer < b) bad++;
}
console.log(JSON.stringify({worst, bad}));""")
    assert out == {'worst': 65, 'bad': 0}


@needs_node
def test_node_bonus_period():
    out = _node("""
const D = s => Date.parse(s);
const n = D('2026-11-15T12:00:00Z');
console.log(JSON.stringify({
  noPeriod: H.bonusActive('', '', n), inside: H.bonusActive('2026-11-01', '2026-11-30', n), beforeFrom: H.bonusActive('2026-11-20', '', n),
  afterUntil: H.bonusActive('', '2026-11-10', n), untilDayItself: H.bonusActive('', '2026-11-15', n), nextDay: H.bonusActive('', '2026-11-16', D('2026-11-15T23:00:00Z')),
  iso: H.bonusActive('2026-11-01T00:00:00Z', '2026-11-15T11:00:00Z', n), onlyFrom: H.bonusActive('2026-11-01', '', n),
}));""")
    assert out == {'noPeriod': True, 'inside': True, 'beforeFrom': False, 'afterUntil': False, 'untilDayItself': True, 'nextDay': True, 'iso': False, 'onlyFrom': True}


@needs_node
def test_node_sheet_validation():
    out = _node("""
const v = (o) => H.validateSheet(Object.assign({base: '50', bonus: '5', from: '2026-11-01', until: '2026-11-30', reason: 'سبب كافٍ'}, o));
const keys = r => Object.keys(r.errors).sort().join(',');
console.log(JSON.stringify({
  ok: v({}), arabicDigits: v({base: '٥٥', bonus: '١٠'}), emptyBonus: v({bonus: ''}), noDates: v({from: '', until: ''}),
  low: keys(v({base: '34'})), high: keys(v({base: '66'})), frac: keys(v({base: '50.5'})), text: keys(v({base: 'خمسون'})), empty: keys(v({base: ''})),
  bonusHigh: keys(v({bonus: '26'})), bonusNeg: keys(v({bonus: '-1'})), bonusFrac: keys(v({bonus: '2.5'})),
  badDate: keys(v({from: '2026-13-40'})), badUntil: keys(v({until: 'abc'})), range: keys(v({from: '2026-12-01', until: '2026-11-01'})), sameDay: keys(v({from: '2026-11-01', until: '2026-11-01'})),
  shortReason: keys(v({reason: 'ab'})), spacesReason: keys(v({reason: '   a  '})), trimmed: v({reason: '  سبب   مرتب  '}).payload.reason,
  many: keys(v({base: '1', bonus: '99', reason: ''})), edges: [v({base: '35', bonus: '0'}).ok, v({base: '65', bonus: '25'}).ok],
  rules: [H.validateRules({codeMin: '55', reason: 'سبب'}), H.validateRules({codeMin: '34', reason: 'سبب'}).errors, H.validateRules({codeMin: '٦٥', reason: 'ab'}).errors],
}));""")
    assert out['ok']['ok'] is True and out['ok']['payload'] == {'base_pct': 50, 'ads_bonus_pts': 5, 'reason': 'سبب كافٍ', 'from': '2026-11-01', 'until': '2026-11-30'}
    assert out['arabicDigits']['payload']['base_pct'] == 55 and out['arabicDigits']['payload']['ads_bonus_pts'] == 10
    assert out['emptyBonus']['payload']['ads_bonus_pts'] == 0
    assert 'from' not in out['noDates']['payload'] and 'until' not in out['noDates']['payload']
    assert out['low'] == out['high'] == out['frac'] == out['text'] == out['empty'] == 'base'
    assert out['bonusHigh'] == out['bonusNeg'] == out['bonusFrac'] == 'bonus'
    assert out['badDate'] == 'from' and out['badUntil'] == 'until' and out['range'] == 'until' and out['sameDay'] == ''
    assert out['shortReason'] == out['spacesReason'] == 'reason' and out['trimmed'] == 'سبب مرتب'
    assert out['many'] == 'base,bonus,reason'
    assert out['edges'] == [True, True]
    assert out['rules'][0]['payload'] == {'code_min_pct': 55, 'reason': 'سبب'}
    assert list(out['rules'][1]) == ['codeMin'] and list(out['rules'][2]) == ['reason']
    for msg in list(out['ok']['errors'].values()):
        assert msg


@needs_node
def test_node_parsers_and_unavailable_sources():
    out = _node("""
const one = {email: 'Hala@Example.test', name: 'هالة', base_pct: 50, ads_bonus_pts: 5, reason: 'سبب', from: '2026-11-01T00:00:00', until: '2026-11-30',
  limits: {min: 35, max: 65, ads_bonus_max: 25}, history: [{base_pct: 40, ads_bonus_pts: 0, reason: 'بداية', at: '2026-10-01T09:00:00', by: 'a@x.test'}, null, 5]};
console.log(JSON.stringify({
  list: H.parseList({items: [one, null, {name: 'بلا بريد'}, {email: 'b@x.test', base_pct: 'x'}]}), noList: [H.parseList(null), H.parseList({}), H.parseList({items: 'x'})],
  one: H.parseOne(one), noOne: [H.parseOne(null), H.parseOne({name: 'x'})],
  rules: H.parseRules({code_min_pct: 50, cap_pct: 65, updated_by: 'f@x.test'}), noRules: [H.parseRules(null), H.parseRules({code_min_pct: 'x'}), H.parseRules({})],
  period: [H.periodText('2026-11-01T00:00:00', '2026-11-30'), H.periodText('2026-11-01', ''), H.periodText('', '2026-11-30'), H.periodText('', '')],
  date: [H.dateText('2026-11-01T10:00:00'), H.dateText(''), H.dateText('x')],
}));""")
    assert [r['email'] for r in out['list']] == ['hala@example.test', 'b@x.test']
    assert out['list'][1]['base'] == 35, 'بلا سجل ⇒ الأساس ٣٥'
    assert out['noList'] == [None, None, None]
    assert out['one']['row']['base'] == 50 and out['one']['limits'] == {'min': 35, 'max': 65, 'adsBonusMax': 25} and len(out['one']['history']) == 1
    assert out['noOne'] == [None, None]
    assert out['rules']['codeMin'] == 50 and out['rules']['cap'] == 65 and out['noRules'] == [None, None, None]
    assert out['period'] == ['من ١ نوفمبر ٢٠٢٦ إلى ٣٠ نوفمبر ٢٠٢٦', 'من ١ نوفمبر ٢٠٢٦', 'حتى ٣٠ نوفمبر ٢٠٢٦', '']
    assert out['date'] == ['١ نوفمبر ٢٠٢٦', '', '']


@needs_node
def test_node_ads_for_trainer():
    out = _node("""
const led = {items: [
  {owner_id: 'c1', owner_kind: 'course', owner_email: 'HALA@example.test', title: 'دورة ١', balance: [{currency: 'EGP', amount: 1500}, {currency: 'USD', amount: 20}], entries: 3},
  {owner_id: 'c2', owner_kind: 'course', owner_email: 'hala@example.test', title: 'دورة ٢', balance: [{currency: 'EGP', amount: 500.5}], entries: 1},
  {owner_id: 'b1', owner_kind: 'book', owner_email: 'hala@example.test', title: 'كتاب', balance: [{currency: 'EGP', amount: 99999}]},
  {owner_id: 'c3', owner_kind: 'course', owner_email: 'other@example.test', title: 'غيرها', balance: [{currency: 'SAR', amount: 7}]},
]};
const dep = {items: [{owner_id: 'c1', owner_kind: 'course', owner_email: 'hala@example.test', deposits: [{currency: 'SAR', amount: 300, country: 'السعودية'}, {currency: 'SAR', amount: 200}, {currency: 'EGP', amount: 100}], sales_before: 4, sales_after: 11}]};
console.log(JSON.stringify({
  balance: H.adsFor(led, 'hala@example.test'), none: H.adsFor(led, 'nobody@example.test'), down: [H.adsFor(null, 'a'), H.adsFor({}, 'a'), H.adsFor({items: 'x'}, 'a')],
  deposits: H.adsFor(dep, 'hala@example.test'), money: [H.moneyText(1500, 'EGP'), H.moneyText(1234567.5, 'USD'), H.moneyText('x', 'EGP'), H.moneyText(5, 'xyz')],
}));""")
    b = out['balance']
    assert b['owners'] == 2 and b['kind'] == 'balance' and b['sales'] is None, 'الجسر الحالي بلا مبيعات قبل/بعد ⇒ غير متاح بعد'
    assert [(r['currency'], r['country'], r['amount']) for r in b['rows']] == [('EGP', 'مصر', 2000.5), ('USD', 'دول أخرى', 20)]
    assert b['rows'][0]['text'] == '٢٠٠٠٫٥ جنيه مصري'.replace('٢٠٠٠', '٢٬٠٠٠')
    assert out['none'] == {'owners': 0, 'kind': 'balance', 'rows': [], 'sales': None}
    assert out['down'] == [None, None, None]
    d = out['deposits']
    assert d['kind'] == 'deposits' and d['sales'] == {'before': 4, 'after': 11}
    assert [(r['currency'], r['country'], r['amount']) for r in d['rows']] == [('SAR', 'السعودية', 500), ('EGP', 'مصر', 100)]
    assert out['money'] == ['١٬٥٠٠ جنيه مصري', '١٬٢٣٤٬٥٦٧٫٥ دولار أمريكي', '', '٥ XYZ']


@needs_node
def test_node_module_loads_without_dom_and_ui_mounts_in_a_stub_dom():
    """الملف يتحمّل بلا DOM، وفي متصفح مزيّف: `mount` يرسم القسم ويقرأ المصدرين (القواعد والقائمة) ولا يكتب شيئًا."""
    script = r"""
const vm = require('vm'), fs = require('fs');
const src = fs.readFileSync(%s, 'utf8');
const calls = [];
const nodes = [];
function mk() { const n = { children: [], attrs: {}, className: '', _html: '', appendChild(c) { this.children.push(c); c.parent = this; }, setAttribute(k, v) { this.attrs[k] = v; },
  querySelectorAll(sel) { return sel === '[data-ts-host]' ? this.children.filter(c => c.attrs['data-ts-host']) : []; }, querySelector() { return null; }, remove() {} };
  Object.defineProperty(n, 'innerHTML', { get() { return this._html; }, set(v) { this._html = v; } }); return n; }
const doc = { createElement: () => mk(), querySelector: () => null, querySelectorAll: () => [] };
const parent = mk();
const win = { document: doc, EP: { authed: true, api: (p, o) => { calls.push([p, o && o.method || 'GET']); return Promise.resolve(p === '/v2/trainer-share' ? { items: [{ email: 'hala@example.test', name: 'هالة', base_pct: 50, ads_bonus_pts: 5, reason: 'إعلان', from: '2026-11-01', until: '2026-11-30' }] } : { code_min_pct: 50, cap_pct: 65 }); } } };
vm.createContext(win); vm.runInContext(src, win);
const sec = win.V2TS.mount(parent);
const first = sec.innerHTML;
setTimeout(() => {
  const st = win.V2TS._state;
  console.log(JSON.stringify({ calls, firstHasLoading: /جارٍ جلب/.test(first), hasTitle: /نسبة المدرّب/.test(first), listState: st.list.st, rulesState: st.rules.st, hostAttr: sec.attrs['data-ts-host'], parentKids: parent.children.length }));
}, 20);
""" % json.dumps(JS_PATH)
    p = subprocess.run([v2_node.NODE, '-e', script], capture_output=True, text=True, timeout=60)
    assert p.returncode == 0, p.stderr[-1500:]
    out = json.loads(p.stdout)
    assert sorted(c[0] for c in out['calls']) == ['/v2/trainer-share', '/v2/trainer-share-rules'] and all(c[1] == 'GET' for c in out['calls'])
    assert out['firstHasLoading'] and out['hasTitle'] and out['listState'] == 'ready' and out['rulesState'] == 'ready'
    assert out['hostAttr'] == '1' and out['parentKids'] == 1
