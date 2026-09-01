"""
Self-tests for «مين ردّ على دعوة المؤسس» — the founding-expert leads proxy (2026-09-01).

Run:  cd backend && python -m pytest test_founding_leads.py -v

الصفوف نفسها تعيش على المنصة (`db.founding_expert_leads`، تكتبها بوّابة الدعوة
elprofessor.net/founders.html) وتُقرأ عبر الجسر GET /api/bridge/founding-expert-leads.
لا شيء هنا يعيد تنفيذ ذلك؛ هذا المسار وسيطٌ رفيع. قبل اليوم كان على المنصة مسار أدمن واحد
يقرأ الصفوف (GET /api/admin/founding-experts) محميّ بجلسة موظّف — واللوحة لا تحمل جلسة موظّف —
فلم تستهلكه واجهةٌ واحدة: كلّ من يردّ على دعوة المؤسس ينزل في درجٍ لا شاشةَ له.

ما يجب أن يكون صحيحًا **هنا**:
  1. المساران خلف مصادقة وخلف دور (الصفوف أسماء وأرقام وإيميلات — لا تُقرأ لمجهول ولا لغير الطاقم)،
  2. الوسيط يحوّل إلى مسار الجسر الصحيح — خطأٌ حرفيّ يعطي ٤٠٤ تُقرأ «محدش قدّم» بدل «الجسر ناقص»،
  3. `limit` يُتحقَّق ويُقصّ هنا، فلا قيمةٌ معادية توسّع القراءة،
  4. تعليم الحالة لا يقبل إلا الحالات المعرَّفة سلفًا (LEAD_BRIDGE_STATUSES) ولا يخترع واحدة،
  5. السرّ المشترك يسافر ترويسةً صادرة ولا يصل المتصفّح أبدًا،
  6. عطل المنصة يظهر عطلًا، لا ٢٠٠ فارغًا.

المنصة مُستبدَلة عند طبقة `requests` — لا شبكة ولا منصة حيّة.
"""
import os
import tempfile

import jwt
import pytest

_tmpdir = tempfile.mkdtemp()
os.environ['DATABASE_URL'] = f"sqlite:///{os.path.join(_tmpdir, 'founding_leads_test.db')}"
os.environ['SECRET_KEY'] = 'test-secret-key-for-founding-leads'
os.environ['METRICS_SECRET'] = 'test-metrics-secret'

import app as appmod  # noqa: E402
from app import app as flask_app, db, User  # noqa: E402
from werkzeug.security import generate_password_hash as _gph  # noqa: E402

BRIDGE = '/api/bridge/founding-expert-leads'


def generate_password_hash(pw):
    return _gph(pw, method='pbkdf2:sha256')


def _make_token(user_id):
    return jwt.encode({'user_id': user_id}, flask_app.config['SECRET_KEY'], algorithm='HS256')


class FakeResp:
    """Minimal stand-in for a requests.Response."""

    def __init__(self, status=200, payload=None):
        self.status_code = status
        self._payload = {} if payload is None else payload
        self.content = b'{}'
        self.text = str(self._payload)

    def json(self):
        return self._payload


ROWS = [
    {'id': 'fl-2', 'name': 'منى صالح', 'whatsapp': '+201000000002',
     'email': 'mona@example.com', 'specialization': 'تحكيم', 'governorate': 'القاهرة',
     'status': 'new', 'created_at': '2026-08-31T10:00:00'},
    {'id': 'fl-1', 'name': 'أحمد فؤاد', 'whatsapp': '+201000000001',
     'email': 'ahmed@example.com', 'specialization': 'تجاري وشركات', 'governorate': 'الإسكندرية',
     'status': 'contacted', 'created_at': '2026-08-30T10:00:00'},
]


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

    sent = []          # every outbound call to the platform
    replies = {}       # path -> FakeResp (default 200 ROWS)

    def fake_request(method, url, params=None, json=None, headers=None, timeout=None):
        path = url.replace(appmod.PLATFORM_API_URL, '')
        sent.append({'method': method, 'path': path, 'params': params or {},
                     'json': json, 'headers': headers or {}})
        return replies.get(path, FakeResp(200, ROWS))

    monkeypatch.setattr(appmod.requests, 'request', fake_request)

    client = flask_app.test_client()
    yield {
        'client': client,
        'admin': {'Authorization': f'Bearer {_make_token(admin_id)}'},
        'emp': {'Authorization': f'Bearer {_make_token(emp_id)}'},
        'trainer': {'Authorization': f'Bearer {_make_token(trainer_id)}'},
        'sent': sent,
        'replies': replies,
    }


# ------------------------------------------------------------------ the proxy hits the bridge

def test_forwards_to_the_founding_leads_bridge_path(ctx):
    """مسارٌ خطأ يعطي ٤٠٤ تُقرأ لوحةً فارغة تقول «محدش قدّم» — وهي الكذبة نفسها التي
    وُجدت هذه الصفوف لتنهيها. ثبّت الطريقة والمسار."""
    r = ctx['client'].get('/api/founding-leads', headers=ctx['admin'])
    assert r.status_code == 200
    call = ctx['sent'][-1]
    assert call['method'] == 'GET'
    assert call['path'] == BRIDGE


def test_rows_reach_the_browser_unchanged(ctx):
    """الوسيط لا يضيف رأيًا: ما أعادته المنصة هو ما ترسمه اللوحة، بترتيبه."""
    r = ctx['client'].get('/api/founding-leads', headers=ctx['admin'])
    body = r.get_json()
    assert [x['id'] for x in body] == ['fl-2', 'fl-1']
    assert body[0]['specialization'] == 'تحكيم'
    assert body[0]['whatsapp'] == '+201000000002'


# ---------------------------------------------------------------------------- limit validation

def test_limit_defaults_and_is_forwarded(ctx):
    ctx['client'].get('/api/founding-leads', headers=ctx['admin'])
    assert ctx['sent'][-1]['params']['limit'] == 100


def test_limit_is_clamped_and_a_bad_value_falls_back(ctx):
    ctx['client'].get('/api/founding-leads?limit=99999', headers=ctx['admin'])
    assert ctx['sent'][-1]['params']['limit'] == 500
    ctx['client'].get('/api/founding-leads?limit=0', headers=ctx['admin'])
    assert ctx['sent'][-1]['params']['limit'] == 1
    ctx['client'].get('/api/founding-leads?limit=-5', headers=ctx['admin'])
    assert ctx['sent'][-1]['params']['limit'] == 1
    ctx['client'].get('/api/founding-leads?limit=abc', headers=ctx['admin'])
    assert ctx['sent'][-1]['params']['limit'] == 100


def test_limit_is_honoured_when_sane(ctx):
    ctx['client'].get('/api/founding-leads?limit=25', headers=ctx['admin'])
    assert ctx['sent'][-1]['params']['limit'] == 25


# -------------------------------------------------------------------------------- auth & roles

def test_requires_authentication(ctx):
    """أسماء وأرقام تواصل. المجهول لا يراها أبدًا."""
    r = ctx['client'].get('/api/founding-leads')
    assert r.status_code in (401, 403)
    assert not any(c['path'] == BRIDGE for c in ctx['sent'])


def test_admin_and_employee_may_read(ctx):
    assert ctx['client'].get('/api/founding-leads', headers=ctx['admin']).status_code == 200
    assert ctx['client'].get('/api/founding-leads', headers=ctx['emp']).status_code == 200


def test_a_non_staff_role_is_refused_and_never_reaches_the_platform(ctx):
    before = len(ctx['sent'])
    r = ctx['client'].get('/api/founding-leads', headers=ctx['trainer'])
    assert r.status_code == 403
    assert len(ctx['sent']) == before      # مرفوض هنا، لا عند المنصة


def test_the_listing_route_is_read_only(ctx):
    """لا قرار على سطح القراءة — التعليم له مساره الخاص."""
    assert ctx['client'].post('/api/founding-leads', json={},
                              headers=ctx['admin']).status_code == 405
    assert ctx['client'].delete('/api/founding-leads',
                                headers=ctx['admin']).status_code == 405


# ------------------------------------------------------------------------------ the secret

def test_secret_is_server_side_only(ctx):
    """المتصفّح لا يرى السرّ أبدًا — يسافر ترويسةً صادرة."""
    r = ctx['client'].get('/api/founding-leads', headers=ctx['admin'])
    assert ctx['sent'][-1]['headers']['X-ELP-Metrics-Secret'] == 'test-metrics-secret'
    assert 'test-metrics-secret' not in r.get_data(as_text=True)
    assert 'X-ELP-Metrics-Secret' not in dict(r.headers)


def test_a_platform_failure_is_surfaced_not_swallowed_as_empty(ctx):
    """العطل لا يصل ٢٠٠ فارغًا — ذاك يُرسم «محدش قدّم» وهو كذب."""
    ctx['replies'][BRIDGE] = FakeResp(404, {'detail': 'Not Found'})
    r = ctx['client'].get('/api/founding-leads', headers=ctx['admin'])
    assert r.status_code == 404

    ctx['replies'][BRIDGE] = FakeResp(500, {'detail': 'boom'})
    r = ctx['client'].get('/api/founding-leads', headers=ctx['admin'])
    assert r.status_code == 500


# --------------------------------------------------------------- «اتعالج»: تعليم حالة الليد

def test_status_forwards_to_the_lifecycle_bridge(ctx):
    r = ctx['client'].post('/api/founding-leads/fl-2/status', json={'status': 'contacted'},
                           headers=ctx['admin'])
    assert r.status_code == 200
    call = ctx['sent'][-1]
    assert call['method'] == 'POST'
    assert call['path'] == '/api/bridge/founding-leads/fl-2/status'
    assert call['json'] == {'status': 'contacted'}
    assert call['headers']['X-ELP-Metrics-Secret'] == 'test-metrics-secret'


def test_every_predefined_status_passes(ctx):
    """الحالات معرَّفة سلفًا على المنصة — نستعملها كلّها ولا نخترع واحدة."""
    for st in ('contacted', 'invited', 'converted', 'rejected'):
        r = ctx['client'].post('/api/founding-leads/fl-1/status', json={'status': st},
                               headers=ctx['admin'])
        assert r.status_code == 200, st
        assert ctx['sent'][-1]['json'] == {'status': st}


def test_an_invented_status_is_refused_before_the_platform_is_called(ctx):
    before = len(ctx['sent'])
    for bad in ('handled', 'done', 'resolved', '', 'new'):
        r = ctx['client'].post('/api/founding-leads/fl-1/status', json={'status': bad},
                               headers=ctx['admin'])
        assert r.status_code == 400, bad
    assert len(ctx['sent']) == before      # لم تُزعَج المنصة بقيمةٍ مرفوضة أصلًا


def test_status_requires_auth_and_a_staff_role(ctx):
    before = len(ctx['sent'])
    assert ctx['client'].post('/api/founding-leads/fl-1/status',
                              json={'status': 'contacted'}).status_code in (401, 403)
    assert ctx['client'].post('/api/founding-leads/fl-1/status', json={'status': 'contacted'},
                              headers=ctx['trainer']).status_code == 403
    assert len(ctx['sent']) == before


def test_a_failed_status_write_is_surfaced(ctx):
    """٤٠٤ (ليد غير موجود) و٥٠٠ لا يصيران نجاحًا صامتًا يترك الدرج ممتلئًا وهو يبدو مفروغًا."""
    path = '/api/bridge/founding-leads/fl-9/status'
    ctx['replies'][path] = FakeResp(404, {'detail': 'اللييد غير موجود'})
    r = ctx['client'].post('/api/founding-leads/fl-9/status', json={'status': 'contacted'},
                           headers=ctx['admin'])
    assert r.status_code == 404
    assert 'اللييد غير موجود' in r.get_data(as_text=True)

    ctx['replies'][path] = FakeResp(500, {'detail': 'boom'})
    r = ctx['client'].post('/api/founding-leads/fl-9/status', json={'status': 'contacted'},
                           headers=ctx['admin'])
    assert r.status_code == 500


def test_a_successful_status_write_is_audited(ctx):
    """من علّم على مَن ومتى — الفعل منسوبٌ لصاحبه."""
    from app import AuditLog
    ctx['client'].post('/api/founding-leads/fl-2/status', json={'status': 'invited'},
                       headers=ctx['admin'])
    with flask_app.app_context():
        rows = AuditLog.query.filter_by(action='founding_lead.status').all()
        assert len(rows) == 1
        assert rows[0].target == 'fl-2'
        assert rows[0].actor_email == 'admin@test.com'


def test_a_refused_status_write_is_not_audited(ctx):
    from app import AuditLog
    ctx['client'].post('/api/founding-leads/fl-2/status', json={'status': 'handled'},
                       headers=ctx['admin'])
    with flask_app.app_context():
        assert AuditLog.query.filter_by(action='founding_lead.status').count() == 0
