"""
Self-tests for «طلبات تقديم الخدمة» — the service-provider queue proxy (2026-08-31).

Run:  cd backend && python -m pytest test_service_requests.py -v

The queue itself lives on the platform (`join_requests`): same collection, same
pending/granted/rejected states, same review surface the dashboard already had. Nothing here
re-implements it — these routes are THIN proxies. What must be true HERE:

  1. **رفضٌ بلا سبب ممنوع.** The platform hands `admin_note` straight back to the applicant as
     «سبب الرفض» (join_requests.serialize_request → `reason`). Rejecting with an empty note
     leaves him a bare «مرفوض» — the exact silence the founder's 2026-08-31 decision forbids.
     The browser guards it too, but a guard that lives only in the browser is not a guard.
  2. **the deciding employee is recorded.** The bridge stamps `by="dashboard"` for every
     dashboard-side decision, so the acting email exists NOWHERE but our audit log. Approving
     is what publishes a provider's name publicly — an unattributed approval is the worst
     accountability hole this queue can have.
  3. **a failed decision is never audited** — an audit row that claims an action the platform
     refused is worse than no row.
  4. the shared secret travels as an outbound header and never reaches the browser.

The platform is stubbed at the `requests` layer — no network, no live platform needed.
"""
import os
import tempfile

import jwt
import pytest

_tmpdir = tempfile.mkdtemp()
os.environ['DATABASE_URL'] = f"sqlite:///{os.path.join(_tmpdir, 'svcreq_test.db')}"
os.environ['SECRET_KEY'] = 'test-secret-key-for-service-requests'
os.environ['METRICS_SECRET'] = 'test-metrics-secret'

import app as appmod  # noqa: E402
from app import app as flask_app, db, User, AuditLog  # noqa: E402
from werkzeug.security import generate_password_hash as _gph  # noqa: E402


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


@pytest.fixture
def ctx(monkeypatch):
    with flask_app.app_context():
        db.drop_all()
        db.create_all()
        admin = User(email='admin@test.com', password_hash=generate_password_hash('x'),
                     name='Admin', role='admin', dashboard_role='admin', is_active=True)
        emp = User(email='emp@test.com', password_hash=generate_password_hash('x'),
                   name='Emp', role='employee', dashboard_role='employee', is_active=True)
        db.session.add_all([admin, emp])
        db.session.commit()
        admin_id, emp_id = admin.id, emp.id

    sent = []          # every outbound call to the platform
    replies = {}       # path -> FakeResp (default 200 {})

    def fake_request(method, url, params=None, json=None, headers=None, timeout=None):
        path = url.replace(appmod.PLATFORM_API_URL, '')
        sent.append({'method': method, 'path': path, 'params': params or {},
                     'json': json, 'headers': headers or {}})
        return replies.get(path, FakeResp(200, {'ok': True}))

    monkeypatch.setattr(appmod.requests, 'request', fake_request)

    client = flask_app.test_client()
    yield {
        'client': client,
        'admin': {'Authorization': f'Bearer {_make_token(admin_id)}'},
        'emp': {'Authorization': f'Bearer {_make_token(emp_id)}'},
        'sent': sent,
        'replies': replies,
    }


def _audit_actions():
    with flask_app.app_context():
        return [(a.action, a.actor_email) for a in AuditLog.query.all()]


def _audit_meta(action):
    with flask_app.app_context():
        row = AuditLog.query.filter_by(action=action).first()
        return row.meta_json if row else None


# --------------------------------------------------------------------- reading the queue

def test_queue_is_read_from_the_live_platform_not_a_local_copy(ctx):
    """The dashboard owns no copy of this queue: the read is a proxy to the platform bridge.
    A local mirror would drift the moment a request is decided from the SPA or Telegram."""
    r = ctx['client'].get('/api/platform-join-requests?status=pending', headers=ctx['admin'])
    assert r.status_code == 200
    call = ctx['sent'][-1]
    assert call['method'] == 'GET'
    assert call['path'] == '/api/bridge/join-requests'
    assert call['params']['status'] == 'pending'


def test_queue_read_forwards_the_section_filter(ctx):
    ctx['client'].get('/api/platform-join-requests?status=all&section=lawyer_offers',
                      headers=ctx['admin'])
    assert ctx['sent'][-1]['params']['section'] == 'lawyer_offers'


def test_queue_read_requires_a_signed_in_dashboard_user(ctx):
    """Anonymous read of who applied for what is a privacy leak, not just a missing feature."""
    r = ctx['client'].get('/api/platform-join-requests')
    assert r.status_code == 401
    assert ctx['sent'] == []          # nothing reached the platform either


def test_queue_secret_is_server_side_only(ctx):
    r = ctx['client'].get('/api/platform-join-requests', headers=ctx['admin'])
    assert ctx['sent'][-1]['headers']['X-ELP-Metrics-Secret'] == 'test-metrics-secret'
    assert 'test-metrics-secret' not in r.get_data(as_text=True)


def test_the_row_the_platform_sends_reaches_the_browser_whole(ctx):
    """The five facts the reviewer decides on — من · أي خدمة · متى · أمرخَّصة · وحالته — are
    serialized by the platform (join_requests.serialize_request). The proxy must not strip
    them: the dashboard row renders `service_label`/`licensed`/`submitted_at`/`status_label`
    directly, and a silently dropped key would render an empty row that still looks fine."""
    payload = {'requests': [{
        'id': 'jr-1', 'user_name': 'أحمد', 'user_email': 'a@x.com', 'section': 'lawyer_offers',
        'section_label': 'الخدمات القانونية', 'service': 'litigation',
        'service_label': 'المرافعة أمام المحاكم', 'licensed': True,
        'submitted_at': '2026-08-29T10:00:00', 'status': 'pending',
        'status_label': 'قيد المراجعة — قُدِّم يوم 2026-08-29',
        'attachments': ['https://example.com/cv'], 'answers': {'proof': 'قيد 12345'},
    }], 'count': 1}
    ctx['replies']['/api/bridge/join-requests'] = FakeResp(200, payload)
    body = ctx['client'].get('/api/platform-join-requests', headers=ctx['admin']).get_json()
    row = body['requests'][0]
    assert body['count'] == 1
    assert row['user_name'] == 'أحمد'                       # من
    assert row['service_label'] == 'المرافعة أمام المحاكم'   # أي خدمة
    assert row['submitted_at'] == '2026-08-29T10:00:00'      # متى
    assert row['licensed'] is True                           # أمرخَّصة
    assert row['status_label'].startswith('قيد المراجعة')     # وحالته
    assert row['attachments'] == ['https://example.com/cv']
    assert row['answers']['proof'] == 'قيد 12345'


# --------------------------------------------------------------------- deciding

def test_reject_without_a_reason_never_leaves_the_dashboard(ctx):
    """⛔ «صمت الانتظار وعدٌ مكسور»: `admin_note` IS the applicant's «سبب الرفض» on the platform.
    An empty one ships him a bare «مرفوض». Refused here — before the platform is touched at all,
    so a rejection can never be half-applied."""
    r = ctx['client'].post('/api/platform-join-requests/jr-1/reject',
                           json={'admin_note': '   '}, headers=ctx['admin'])
    assert r.status_code == 400
    assert 'سبب الرفض' in r.get_json()['error']
    assert ctx['sent'] == []
    assert _audit_actions() == []


def test_reject_with_no_body_at_all_is_refused_too(ctx):
    r = ctx['client'].post('/api/platform-join-requests/jr-1/reject', headers=ctx['admin'])
    assert r.status_code == 400
    assert ctx['sent'] == []


def test_reject_reason_travels_verbatim_and_is_audited(ctx):
    """The reason is not an internal note — it is the text the applicant reads. It must arrive
    exactly as written, on the bridge's declared {decision, admin_note} model."""
    reason = 'إثبات الصفة غير مقروء — أرفق صورة أوضح لبطاقة النقابة'
    r = ctx['client'].post('/api/platform-join-requests/jr-1/reject',
                           json={'admin_note': reason}, headers=ctx['emp'])
    assert r.status_code == 200
    call = ctx['sent'][-1]
    assert call['path'] == '/api/bridge/join-requests/jr-1/decide'
    assert call['json'] == {'decision': 'reject', 'admin_note': reason}
    assert ('join_request.reject', 'emp@test.com') in _audit_actions()
    assert reason in _audit_meta('join_request.reject')


def test_approve_needs_no_reason_and_records_who_published_the_name(ctx):
    """Approving is what makes the provider's name public (the platform's grant flips
    trainer_status → the expert directory). The bridge records by="dashboard" for us all,
    so the acting employee exists only in this audit row."""
    r = ctx['client'].post('/api/platform-join-requests/jr-2/approve',
                           json={}, headers=ctx['emp'])
    assert r.status_code == 200
    assert ctx['sent'][-1]['json'] == {'decision': 'approve', 'admin_note': ''}
    assert ('join_request.approve', 'emp@test.com') in _audit_actions()


def test_an_approval_note_is_still_forwarded(ctx):
    ctx['client'].post('/api/platform-join-requests/jr-2/approve',
                       json={'admin_note': 'تحقّقنا من القيد هاتفيًّا'}, headers=ctx['admin'])
    assert ctx['sent'][-1]['json']['admin_note'] == 'تحقّقنا من القيد هاتفيًّا'


def test_a_refused_decision_is_never_audited(ctx):
    """An audit row for an action the platform rejected reads as a decision that happened."""
    ctx['replies']['/api/bridge/join-requests/jr-9/decide'] = FakeResp(404, {'detail': 'غير موجود'})
    r = ctx['client'].post('/api/platform-join-requests/jr-9/approve', json={}, headers=ctx['admin'])
    assert r.status_code == 404
    assert _audit_actions() == []


def test_an_unknown_action_is_refused_locally(ctx):
    """Only approve/reject exist. A typo must not become a path on the platform."""
    r = ctx['client'].post('/api/platform-join-requests/jr-1/grant', json={}, headers=ctx['admin'])
    assert r.status_code == 400
    assert ctx['sent'] == []


def test_deciding_requires_a_signed_in_dashboard_user(ctx):
    r = ctx['client'].post('/api/platform-join-requests/jr-1/approve', json={})
    assert r.status_code == 401
    assert ctx['sent'] == []
    assert _audit_actions() == []


def test_the_reason_is_clamped_to_the_platform_limit(ctx):
    """The bridge model caps admin_note at 1000 chars; a longer note would 422 the whole
    decision — losing the ACTION to save the tail of a sentence."""
    ctx['client'].post('/api/platform-join-requests/jr-1/reject',
                       json={'admin_note': 'ب' * 5000}, headers=ctx['admin'])
    assert len(ctx['sent'][-1]['json']['admin_note']) == 1000


# --------------------------------------------------------------------- trainer applications
# نفس الحارس، الطابور الآخر: «قدّم كمدرّب» يسكن `trainer_applications` لا `join_requests`،
# وشاشة المنصة صارت تعرض لصاحبه خانة «سبب الرفض» (SectionGate ← /api/my/trainer-application).
# فالرفض الصامت هنا كان يترك الخانة خاوية فوق كلمة «مرفوض» — نفس الصمت المنهيّ عنه.

def test_trainer_reject_without_a_reason_never_leaves_the_dashboard(ctx):
    r = ctx['client'].post('/api/platform-trainer-applications/tr-1/reject',
                           json={'admin_note': '  '}, headers=ctx['admin'])
    assert r.status_code == 400
    assert 'سبب الرفض' in r.get_json()['error']
    assert ctx['sent'] == []
    assert _audit_actions() == []


def test_trainer_reject_with_no_body_returns_the_sentence_not_a_415(ctx):
    """`request.json` على جسمٍ غائب يرفع 415 في Flask 3 — صفحةٌ لا يستطيع المراجِع التصرّف
    حيالها. الرفض بلا جسم هو بالضبط الحالة التي يجب أن تعود بالجملة."""
    r = ctx['client'].post('/api/platform-trainer-applications/tr-1/reject', headers=ctx['admin'])
    assert r.status_code == 400
    assert 'سبب الرفض' in r.get_json()['error']
    assert ctx['sent'] == []


def test_trainer_reject_reason_travels_verbatim_and_is_audited(ctx):
    reason = 'خبرتك التدريبية غير موثّقة — أرفق دورتين سابقتين بروابطهما'
    r = ctx['client'].post('/api/platform-trainer-applications/tr-1/reject',
                           json={'admin_note': reason}, headers=ctx['emp'])
    assert r.status_code == 200
    call = ctx['sent'][-1]
    assert call['path'] == '/api/bridge/trainer-applications/tr-1/reject'
    assert call['json'] == {'admin_note': reason}
    assert ('trainer_application.reject', 'emp@test.com') in _audit_actions()
    assert reason in _audit_meta('trainer_application.reject')


def test_trainer_approve_needs_no_reason_and_is_audited(ctx):
    """الاعتماد هو ما يرفع `trainer_status` فيظهر الاسم في الدليل — والجسر يختم
    by="dashboard" للجميع، فهوية من اعتمد لا تعيش إلا في سجلّنا."""
    r = ctx['client'].post('/api/platform-trainer-applications/tr-2/approve',
                           json={}, headers=ctx['emp'])
    assert r.status_code == 200
    assert ctx['sent'][-1]['json'] == {'admin_note': ''}
    assert ('trainer_application.approve', 'emp@test.com') in _audit_actions()


def test_a_refused_trainer_decision_is_never_audited(ctx):
    ctx['replies']['/api/bridge/trainer-applications/tr-9/approve'] = FakeResp(404, {'detail': 'x'})
    r = ctx['client'].post('/api/platform-trainer-applications/tr-9/approve',
                           json={}, headers=ctx['admin'])
    assert r.status_code == 404
    assert _audit_actions() == []


def test_trainer_reason_is_clamped_to_the_platform_limit(ctx):
    ctx['client'].post('/api/platform-trainer-applications/tr-1/reject',
                       json={'admin_note': 'ب' * 5000}, headers=ctx['admin'])
    assert len(ctx['sent'][-1]['json']['admin_note']) == 1000
