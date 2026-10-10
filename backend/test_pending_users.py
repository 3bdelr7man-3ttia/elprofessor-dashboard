"""
Self-tests for «زوّار مسجَّلون ينتظرون الفتح» — the pending-users bridge proxy (2026-10-10).

Run:  cd backend && python -m pytest test_pending_users.py -v

التسجيل المفتوح (قرار المؤسس 2026-10-10): الحساب الجديد بلا دعوة يدخل زائرًا (`access:"pending"`)
ويطلب دعوته من جوّه، والمؤسس يفتح له المنصّة من الداشبورد. الصفوف تعيش على المنصة وتُقرأ عبر
الجسر GET /api/bridge/pending-users، والقرار يسافر POST /api/bridge/users/{id}/access.

ما يجب أن يكون صحيحًا **هنا**:
  1. المساران خلف مصادقة ودور — القراءة للطاقم، والفتح (يحوّل زائرًا إلى عضو) للأدمن وحده،
  2. الوسيط يحوّل إلى مسار الجسر الصحيح بالطريقة الصحيحة،
  3. `limit` يُتحقَّق ويُقصّ هنا،
  4. `access` لا يقبل إلا `member|pending`؛ المجهول يُرفض بـ٤٠٠ **قبل** أي نداء للمنصة،
  5. الملاحظة تسافر فقط لو كُتبت (لا مفتاح فارغ يُبتلع صامتًا على المنصة)،
  6. السرّ المشترك يسافر ترويسةً صادرة ولا يصل المتصفّح، وعطل المنصة يظهر عطلًا لا ٢٠٠ فارغًا.

المنصة مُستبدَلة عند طبقة `requests` — لا شبكة ولا منصة حيّة.
"""
import os
import tempfile

import jwt
import pytest

_tmpdir = tempfile.mkdtemp()
os.environ['DATABASE_URL'] = f"sqlite:///{os.path.join(_tmpdir, 'pending_users_test.db')}"
os.environ['SECRET_KEY'] = 'test-secret-key-for-pending-users-0123456789abcdef'
os.environ['METRICS_SECRET'] = 'test-metrics-secret'

import app as appmod  # noqa: E402
from app import app as flask_app, db, User  # noqa: E402
from werkzeug.security import generate_password_hash as _gph  # noqa: E402

LIST_BRIDGE = '/api/bridge/pending-users'


def generate_password_hash(pw):
    return _gph(pw, method='pbkdf2:sha256')


def _make_token(user_id):
    return jwt.encode({'user_id': user_id}, flask_app.config['SECRET_KEY'], algorithm='HS256')


class FakeResp:
    def __init__(self, status=200, payload=None):
        self.status_code = status
        self._payload = {} if payload is None else payload
        self.content = b'x'

    def json(self):
        return self._payload


ROWS = {'count': 2, 'users': [
    {'id': 'pu-1', 'full_name': 'نور سالم', 'email': 'nour@example.com', 'phone': '+201000000011',
     'created_at': '2026-10-09T10:00:00', 'access': 'pending',
     'invite_request': {'status': 'requested', 'requested_at': '2026-10-09T11:00:00'},
     'role_requested': 'lawyer', 'country': 'مصر', 'specialty': 'civil', 'why': '', 'ai_used': 5},
    {'id': 'pu-2', 'full_name': 'ساكت', 'email': 'silent@example.com', 'phone': '',
     'created_at': '2026-10-10T10:00:00', 'access': 'pending', 'invite_request': {'status': 'none'},
     'role_requested': '', 'country': '', 'specialty': '', 'why': '', 'ai_used': 0},
]}


@pytest.fixture
def ctx(monkeypatch):
    with flask_app.app_context():
        db.drop_all()
        db.create_all()
        admin = User(email='admin@test.com', password_hash=generate_password_hash('x'),
                     name='Admin', role='admin', dashboard_role='admin', is_active=True)
        emp = User(email='emp@test.com', password_hash=generate_password_hash('x'),
                   name='Emp', role='employee', dashboard_role='employee', is_active=True)
        trainer = User(email='trainer@test.com', password_hash=generate_password_hash('x'),
                       name='Trainer', role='trainer', dashboard_role='trainer', is_active=True)
        db.session.add_all([admin, emp, trainer])
        db.session.commit()
        admin_id, emp_id, trainer_id = admin.id, emp.id, trainer.id

    sent = []
    replies = {}

    def fake_request(method, url, params=None, json=None, headers=None, timeout=None):
        path = url.replace(appmod.PLATFORM_API_URL, '')
        sent.append({'method': method, 'path': path, 'params': params or {},
                     'json': json, 'headers': headers or {}})
        return replies.get(path, FakeResp(200, ROWS if path == LIST_BRIDGE else {'ok': True}))

    monkeypatch.setattr(appmod.requests, 'request', fake_request)
    monkeypatch.setattr(appmod, 'PLATFORM_METRICS_SECRET', 'test-metrics-secret')

    yield {
        'client': flask_app.test_client(),
        'admin': {'Authorization': f'Bearer {_make_token(admin_id)}'},
        'emp': {'Authorization': f'Bearer {_make_token(emp_id)}'},
        'trainer': {'Authorization': f'Bearer {_make_token(trainer_id)}'},
        'sent': sent,
        'replies': replies,
    }


# ------------------------------------------------------------------ القراءة تمرّ من الجسر الصحيح

def test_listing_forwards_to_the_pending_users_bridge_verbatim(ctx):
    r = ctx['client'].get('/api/pending-users', headers=ctx['admin'])
    assert r.status_code == 200
    call = ctx['sent'][-1]
    assert call['method'] == 'GET' and call['path'] == LIST_BRIDGE
    assert call['params']['limit'] == 100
    assert r.get_json() == ROWS                       # الوسيط لا يضيف رأيًا ولا يعيد الترتيب


def test_limit_is_clamped_here(ctx):
    ctx['client'].get('/api/pending-users?limit=99999', headers=ctx['admin'])
    assert ctx['sent'][-1]['params']['limit'] == 500
    ctx['client'].get('/api/pending-users?limit=0', headers=ctx['admin'])
    assert ctx['sent'][-1]['params']['limit'] == 1
    ctx['client'].get('/api/pending-users?limit=abc', headers=ctx['admin'])
    assert ctx['sent'][-1]['params']['limit'] == 100
    ctx['client'].get('/api/pending-users?limit=200', headers=ctx['admin'])
    assert ctx['sent'][-1]['params']['limit'] == 200


def test_listing_requires_staff_and_refuses_the_anonymous_and_the_trainer(ctx):
    assert ctx['client'].get('/api/pending-users').status_code in (401, 403)
    before = len(ctx['sent'])
    assert ctx['client'].get('/api/pending-users', headers=ctx['trainer']).status_code == 403
    assert len(ctx['sent']) == before                 # مرفوض هنا، لا عند المنصة
    assert ctx['client'].get('/api/pending-users', headers=ctx['emp']).status_code == 200
    assert ctx['client'].get('/api/pending-users', headers=ctx['admin']).status_code == 200


# ------------------------------------------------------------------ الفتح والرفض

def test_open_sends_access_member_to_the_users_access_bridge(ctx):
    r = ctx['client'].post('/api/pending-users/pu-1/access', json={'access': 'member'},
                           headers=ctx['admin'])
    assert r.status_code == 200, r.get_data(as_text=True)
    call = ctx['sent'][-1]
    assert call['method'] == 'POST' and call['path'] == '/api/bridge/users/pu-1/access'
    assert call['json'] == {'access': 'member'}       # لا `note` فارغة تُبتلع على المنصة


def test_reject_sends_access_pending_with_the_note(ctx):
    r = ctx['client'].post('/api/pending-users/pu-1/access',
                           json={'access': 'pending', 'note': 'مش دلوقتي'}, headers=ctx['admin'])
    assert r.status_code == 200
    assert ctx['sent'][-1]['json'] == {'access': 'pending', 'note': 'مش دلوقتي'}


def test_an_unknown_access_value_is_refused_before_the_platform_is_called(ctx):
    before = len(ctx['sent'])
    for bad in ('admin', '', None, 'MEMBER ', 'deleted'):
        r = ctx['client'].post('/api/pending-users/pu-1/access', json={'access': bad},
                               headers=ctx['admin'])
        if bad == 'MEMBER ':
            assert r.status_code == 200               # قصّ وتصغير: نفس تطهير بقية البروكسيات
            continue
        assert r.status_code == 400, bad
        assert 'member' in r.get_json()['error'] and 'pending' in r.get_json()['error']
    assert len([c for c in ctx['sent'][before:] if c['path'].endswith('/access')]) == 1


def test_opening_an_account_is_an_admin_decision_not_an_employee_one(ctx):
    """الفتح يحوّل زائرًا إلى عضو كامل — نفس قاعدة اعتماد الدعوة: قرارُ مؤسسٍ لا موظّف."""
    before = len(ctx['sent'])
    r = ctx['client'].post('/api/pending-users/pu-1/access', json={'access': 'member'},
                           headers=ctx['emp'])
    assert r.status_code == 403
    r = ctx['client'].post('/api/pending-users/pu-1/access', json={'access': 'member'},
                           headers=ctx['trainer'])
    assert r.status_code == 403
    assert ctx['client'].post('/api/pending-users/pu-1/access',
                              json={'access': 'member'}).status_code in (401, 403)
    assert len(ctx['sent']) == before


# ------------------------------------------------------------------ السرّ والعطل

def test_secret_travels_in_the_header_and_never_reaches_the_browser(ctx):
    r = ctx['client'].get('/api/pending-users', headers=ctx['admin'])
    assert ctx['sent'][-1]['headers']['X-ELP-Metrics-Secret'] == 'test-metrics-secret'
    assert 'test-metrics-secret' not in r.get_data(as_text=True)
    assert 'X-ELP-Metrics-Secret' not in dict(r.headers)


def test_a_platform_failure_is_surfaced_not_swallowed_as_empty(ctx):
    """٤٠٤ = الجسر لسه ما اتنشرش — اللوحة تقرأه «قيد النشر» لا «محدش سجّل»."""
    ctx['replies'][LIST_BRIDGE] = FakeResp(404, {'detail': 'Not Found'})
    assert ctx['client'].get('/api/pending-users', headers=ctx['admin']).status_code == 404
    ctx['replies']['/api/bridge/users/pu-1/access'] = FakeResp(409, {'detail': 'حسابه عضو بالفعل'})
    r = ctx['client'].post('/api/pending-users/pu-1/access', json={'access': 'member'},
                           headers=ctx['admin'])
    assert r.status_code == 409
    assert r.get_json()['error'] == 'حسابه عضو بالفعل'
