"""
Self-tests for «مين طلب التدريب» — the training-interest rows proxy (2026-09-01).

Run:  cd backend && python -m pytest test_training_interests.py -v

The rows themselves live on the platform (`db.training_interests`, written by
POST /api/training-interest) and are read back over the bridge at
GET /api/bridge/training-interests. Nothing here re-implements that; this route is a THIN
proxy. Until now the dashboard only ever saw the AGGREGATE («٧ اهتمام تدريب» inside the course
suggestions panel) — a number nobody can phone. What must be true HERE:

  1. the route is behind auth AND behind a role (the rows carry names, phones and emails —
     they must never be readable by an anonymous request or a non-staff role),
  2. it forwards to the RIGHT bridge path — a typo would 404 into an empty panel that reads
     as «مفيش طلبات» instead of «الجسر مش موجود»,
  3. `limit` is validated and clamped HERE, so neither a typo nor a hostile value can widen
     or break the read server-side,
  4. the shared secret travels as an outbound header and never reaches the browser.

The platform is stubbed at the `requests` layer — no network, no live platform needed.
"""
import os
import tempfile

import jwt
import pytest

_tmpdir = tempfile.mkdtemp()
os.environ['DATABASE_URL'] = f"sqlite:///{os.path.join(_tmpdir, 'training_interest_test.db')}"
os.environ['SECRET_KEY'] = 'test-secret-key-for-training-interests'
os.environ['METRICS_SECRET'] = 'test-metrics-secret'

import app as appmod  # noqa: E402
from app import app as flask_app, db, User  # noqa: E402
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


ROWS = {'interests': [
    {'id': 'ti-2', 'name': 'منى صالح', 'phone': '+201000000002',
     'email': 'mona@example.com', 'wanted_course': 'صياغة العقود',
     'status': 'new', 'created_at': '2026-08-31T10:00:00'},
    {'id': 'ti-1', 'name': 'أحمد فؤاد', 'phone': '+201000000001',
     'email': 'ahmed@example.com', 'wanted_course': 'التحكيم التجاري',
     'status': 'contacted', 'created_at': '2026-08-30T10:00:00'},
], 'count': 2}


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

def test_forwards_to_the_training_interests_bridge_path(ctx):
    """A wrong path 404s into an empty panel that reads as «no one asked» — the exact lie the
    rows exist to end. Pin the method and the path."""
    r = ctx['client'].get('/api/training-interests', headers=ctx['admin'])
    assert r.status_code == 200
    call = ctx['sent'][-1]
    assert call['method'] == 'GET'
    assert call['path'] == '/api/bridge/training-interests'


def test_rows_reach_the_browser_unchanged(ctx):
    """The proxy adds no opinion: what the platform returned is what the panel renders."""
    r = ctx['client'].get('/api/training-interests', headers=ctx['admin'])
    body = r.get_json()
    assert [x['id'] for x in body['interests']] == ['ti-2', 'ti-1']
    assert body['interests'][0]['wanted_course'] == 'صياغة العقود'


# ---------------------------------------------------------------------------- limit validation

def test_limit_defaults_and_is_forwarded(ctx):
    ctx['client'].get('/api/training-interests', headers=ctx['admin'])
    assert ctx['sent'][-1]['params']['limit'] == 100


def test_limit_is_clamped_and_a_bad_value_falls_back(ctx):
    ctx['client'].get('/api/training-interests?limit=99999', headers=ctx['admin'])
    assert ctx['sent'][-1]['params']['limit'] == 500
    ctx['client'].get('/api/training-interests?limit=0', headers=ctx['admin'])
    assert ctx['sent'][-1]['params']['limit'] == 1
    ctx['client'].get('/api/training-interests?limit=-5', headers=ctx['admin'])
    assert ctx['sent'][-1]['params']['limit'] == 1
    ctx['client'].get('/api/training-interests?limit=abc', headers=ctx['admin'])
    assert ctx['sent'][-1]['params']['limit'] == 100


def test_limit_is_honoured_when_sane(ctx):
    ctx['client'].get('/api/training-interests?limit=25', headers=ctx['admin'])
    assert ctx['sent'][-1]['params']['limit'] == 25


# -------------------------------------------------------------------------------- auth & roles

def test_requires_authentication(ctx):
    """These rows are names + phone numbers. Anonymous must never see them."""
    r = ctx['client'].get('/api/training-interests')
    assert r.status_code in (401, 403)
    assert not any(c['path'] == '/api/bridge/training-interests' for c in ctx['sent'])


def test_admin_and_employee_may_read(ctx):
    assert ctx['client'].get('/api/training-interests', headers=ctx['admin']).status_code == 200
    assert ctx['client'].get('/api/training-interests', headers=ctx['emp']).status_code == 200


def test_a_non_staff_role_is_refused_and_never_reaches_the_platform(ctx):
    before = len(ctx['sent'])
    r = ctx['client'].get('/api/training-interests', headers=ctx['trainer'])
    assert r.status_code == 403
    assert len(ctx['sent']) == before      # refused HERE, not by the platform


def test_the_route_is_read_only(ctx):
    """No decision lives on this surface — POST/DELETE must not exist."""
    assert ctx['client'].post('/api/training-interests', json={},
                              headers=ctx['admin']).status_code == 405
    assert ctx['client'].delete('/api/training-interests',
                                headers=ctx['admin']).status_code == 405


# ------------------------------------------------------------------------------ the secret

def test_secret_is_server_side_only(ctx):
    """The browser must never see the shared secret — it travels as an outbound header."""
    r = ctx['client'].get('/api/training-interests', headers=ctx['admin'])
    assert ctx['sent'][-1]['headers']['X-ELP-Metrics-Secret'] == 'test-metrics-secret'
    assert 'test-metrics-secret' not in r.get_data(as_text=True)
    assert 'X-ELP-Metrics-Secret' not in dict(r.headers)


def test_a_platform_failure_is_surfaced_not_swallowed_as_empty(ctx):
    """An error must NOT arrive as an empty 200 — that renders as «محدش طلب» and is a lie."""
    ctx['replies']['/api/bridge/training-interests'] = FakeResp(404, {'detail': 'Not Found'})
    r = ctx['client'].get('/api/training-interests', headers=ctx['admin'])
    assert r.status_code == 404

    ctx['replies']['/api/bridge/training-interests'] = FakeResp(500, {'detail': 'boom'})
    r = ctx['client'].get('/api/training-interests', headers=ctx['admin'])
    assert r.status_code == 500
