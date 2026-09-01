"""
Self-tests for «الدعوات وقائمة الانتظار» — the founder's invite desk proxies (2026-09-01).

Run:  cd backend && python -m pytest test_invites.py -v

The rows live on the platform (`db.invites` / `db.waitlist`) and are read/written over the
bridge (`/api/bridge/invites`, `/api/bridge/waitlist`). Nothing here re-implements the gate —
these routes are THIN proxies, and that is exactly why they need pinning:

  1. auth AND role — an invite row is an email address plus a token that CREATES AN ACCOUNT.
     An anonymous or non-staff request must never read it and must never mint one,
  2. the RIGHT bridge path — a typo 404s into an empty table that reads as «محدش اتدعى»
     instead of «الجسر مش منشور», which is the exact lie this desk exists to end,
  3. `limit` clamped HERE, so neither a typo nor a hostile value widens the read,
  4. the email is sanitized HERE (trim + lowercase) before it can reach the platform's unique
     index as a second row for the same person,
  5. a bad email is refused BEFORE the platform is called at all,
  6. revoke / waitlist-invite send NO invented body — an extra key is swallowed silently by
     the platform (as `admin_note` was on market close) and vanishes without a trace,
  7. the shared secret travels as an outbound header and never reaches the browser.

The platform is stubbed at the `requests` layer — no network, no live platform needed.
"""
import os
import tempfile

import jwt
import pytest

_tmpdir = tempfile.mkdtemp()
os.environ['DATABASE_URL'] = f"sqlite:///{os.path.join(_tmpdir, 'invites_test.db')}"
os.environ['SECRET_KEY'] = 'test-secret-key-for-invites'
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


INVITE_ROWS = {'invites': [
    {'id': 'inv-2', 'email': 'nour@example.com', 'name': 'نور حسن', 'status': 'opened',
     'created_at': '2026-08-31T10:00:00', 'opened_at': '2026-08-31T12:00:00',
     'registered_at': None, 'invited_by': 'admin@test.com'},
    {'id': 'inv-1', 'email': 'omar@example.com', 'name': 'عمر سعيد', 'status': 'registered',
     'created_at': '2026-08-30T10:00:00', 'opened_at': '2026-08-30T11:00:00',
     'registered_at': '2026-08-30T11:05:00', 'invited_by': 'admin@test.com'},
], 'count': 2}

WAITLIST_ROWS = {'waitlist': [
    {'id': 'w-1', 'name': 'سلمى', 'email': 'salma@example.com', 'note': 'محامية عقود',
     'status': 'new', 'created_at': '2026-08-31T09:00:00'},
], 'count': 1}

CREATED = {'id': 'inv-9', 'email': 'new@example.com', 'name': 'جديد',
           'status': 'pending', 'link': 'https://app.example.net/invite/TOK'}


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
    replies = {}       # (method, path) -> FakeResp

    def fake_request(method, url, params=None, json=None, headers=None, timeout=None):
        path = url.replace(appmod.PLATFORM_API_URL, '')
        sent.append({'method': method, 'path': path, 'params': params or {},
                     'json': json, 'headers': headers or {}})
        if (method, path) in replies:
            return replies[(method, path)]
        if path == '/api/bridge/invites' and method == 'GET':
            return FakeResp(200, INVITE_ROWS)
        if path == '/api/bridge/invites' and method == 'POST':
            return FakeResp(200, CREATED)
        if path == '/api/bridge/waitlist':
            return FakeResp(200, WAITLIST_ROWS)
        return FakeResp(200, {'ok': True})

    monkeypatch.setattr(appmod.requests, 'request', fake_request)

    yield {
        'client': flask_app.test_client(),
        'admin': {'Authorization': f'Bearer {_make_token(admin_id)}'},
        'emp': {'Authorization': f'Bearer {_make_token(emp_id)}'},
        'trainer': {'Authorization': f'Bearer {_make_token(trainer_id)}'},
        'sent': sent,
        'replies': replies,
    }


def _audits(action):
    with flask_app.app_context():
        return AuditLog.query.filter_by(action=action).all()


# ------------------------------------------------------------------- reading the invite rows

def test_invites_list_forwards_to_the_bridge_path(ctx):
    r = ctx['client'].get('/api/invites', headers=ctx['admin'])
    assert r.status_code == 200
    call = ctx['sent'][-1]
    assert call['method'] == 'GET'
    assert call['path'] == '/api/bridge/invites'


def test_invite_rows_reach_the_browser_unchanged(ctx):
    """The counters in the header are computed from THESE rows — the proxy adds no opinion."""
    body = ctx['client'].get('/api/invites', headers=ctx['admin']).get_json()
    assert [x['id'] for x in body['invites']] == ['inv-2', 'inv-1']
    assert body['invites'][1]['registered_at'] == '2026-08-30T11:05:00'


def test_invites_limit_defaults_clamps_and_falls_back(ctx):
    ctx['client'].get('/api/invites', headers=ctx['admin'])
    assert ctx['sent'][-1]['params']['limit'] == 100
    ctx['client'].get('/api/invites?limit=99999', headers=ctx['admin'])
    assert ctx['sent'][-1]['params']['limit'] == 500
    ctx['client'].get('/api/invites?limit=0', headers=ctx['admin'])
    assert ctx['sent'][-1]['params']['limit'] == 1
    ctx['client'].get('/api/invites?limit=-5', headers=ctx['admin'])
    assert ctx['sent'][-1]['params']['limit'] == 1
    ctx['client'].get('/api/invites?limit=abc', headers=ctx['admin'])
    assert ctx['sent'][-1]['params']['limit'] == 100
    ctx['client'].get('/api/invites?limit=25', headers=ctx['admin'])
    assert ctx['sent'][-1]['params']['limit'] == 25


def test_a_platform_failure_is_surfaced_not_swallowed_as_empty(ctx):
    """An error must NOT arrive as an empty 200 — «محدش اتدعى» is a lie the founder acts on."""
    ctx['replies'][('GET', '/api/bridge/invites')] = FakeResp(404, {'detail': 'Not Found'})
    assert ctx['client'].get('/api/invites', headers=ctx['admin']).status_code == 404
    ctx['replies'][('GET', '/api/bridge/invites')] = FakeResp(500, {'detail': 'boom'})
    assert ctx['client'].get('/api/invites', headers=ctx['admin']).status_code == 500


# ------------------------------------------------------------------------- creating an invite

def test_create_forwards_email_name_and_the_actor(ctx):
    r = ctx['client'].post('/api/invites', json={'email': 'new@example.com', 'name': 'جديد'},
                           headers=ctx['admin'])
    assert r.status_code == 200
    call = ctx['sent'][-1]
    assert call['method'] == 'POST' and call['path'] == '/api/bridge/invites'
    assert call['json']['email'] == 'new@example.com'
    assert call['json']['name'] == 'جديد'
    assert call['json']['invited_by'] == 'admin@test.com'


def test_the_link_the_platform_returns_reaches_the_browser(ctx):
    """The founder sends the link himself on WhatsApp — if it does not survive the proxy the
    whole desk is decorative."""
    body = ctx['client'].post('/api/invites', json={'email': 'new@example.com'},
                              headers=ctx['admin']).get_json()
    assert body['link'] == 'https://app.example.net/invite/TOK'


def test_email_is_trimmed_and_lowercased_before_the_platform_sees_it(ctx):
    """Two rows for one human is what an un-sanitized email costs at a unique index."""
    ctx['client'].post('/api/invites', json={'email': '  Ali@Example.COM  '}, headers=ctx['admin'])
    assert ctx['sent'][-1]['json']['email'] == 'ali@example.com'


def test_a_bad_email_is_refused_here_and_never_reaches_the_platform(ctx):
    before = len(ctx['sent'])
    for bad in ('', '   ', 'nope', 'a@', '@b.com', 'a@b'):
        r = ctx['client'].post('/api/invites', json={'email': bad}, headers=ctx['admin'])
        assert r.status_code == 400, bad
    assert len(ctx['sent']) == before      # refused HERE, not by the platform


def test_creating_an_invite_is_audited(ctx):
    ctx['client'].post('/api/invites', json={'email': 'new@example.com', 'name': 'جديد'},
                       headers=ctx['admin'])
    rows = _audits('invite.create')
    assert len(rows) == 1
    assert rows[0].target == 'new@example.com'
    assert rows[0].actor_email == 'admin@test.com'


def test_a_rejected_creation_is_not_audited(ctx):
    """A duplicate email 409s on the platform — an audit row for a write that never happened
    turns the log into fiction."""
    ctx['replies'][('POST', '/api/bridge/invites')] = FakeResp(409, {'detail': 'البريد مدعوٌّ سلفًا'})
    r = ctx['client'].post('/api/invites', json={'email': 'dup@example.com'}, headers=ctx['admin'])
    assert r.status_code == 409
    assert r.get_json()['error'] == 'البريد مدعوٌّ سلفًا'
    assert _audits('invite.create') == []


# --------------------------------------------------------------------------------- revoking

def test_revoke_hits_the_right_path_with_no_invented_body(ctx):
    r = ctx['client'].post('/api/invites/inv-2/revoke', headers=ctx['admin'])
    assert r.status_code == 200
    call = ctx['sent'][-1]
    assert call['method'] == 'POST'
    assert call['path'] == '/api/bridge/invites/inv-2/revoke'
    assert call['json'] is None          # an extra key is swallowed silently — send none
    assert len(_audits('invite.revoke')) == 1


def test_a_failed_revoke_is_not_audited(ctx):
    ctx['replies'][('POST', '/api/bridge/invites/inv-2/revoke')] = FakeResp(404, {'detail': 'مش موجودة'})
    assert ctx['client'].post('/api/invites/inv-2/revoke', headers=ctx['admin']).status_code == 404
    assert _audits('invite.revoke') == []


# --------------------------------------------------------------------------- the waitlist

def test_waitlist_list_forwards_to_the_bridge_path_with_a_clamped_limit(ctx):
    r = ctx['client'].get('/api/waitlist?limit=99999', headers=ctx['admin'])
    assert r.status_code == 200
    call = ctx['sent'][-1]
    assert call['method'] == 'GET' and call['path'] == '/api/bridge/waitlist'
    assert call['params']['limit'] == 500
    assert r.get_json()['waitlist'][0]['email'] == 'salma@example.com'


def test_waitlist_invite_converts_the_row_by_id_only(ctx):
    """The row on the platform is the truth; re-posting an email from the browser would let a
    tampered payload invite someone else under the guise of «promote this row»."""
    r = ctx['client'].post('/api/waitlist/w-1/invite', json={'email': 'attacker@evil.com'},
                           headers=ctx['admin'])
    assert r.status_code == 200
    call = ctx['sent'][-1]
    assert call['path'] == '/api/bridge/waitlist/w-1/invite'
    assert call['json'] is None
    assert len(_audits('waitlist.invite')) == 1


# -------------------------------------------------------------------------------- auth & roles

def test_every_route_requires_authentication(ctx):
    """An invite token creates an ACCOUNT. Anonymous must never read one or mint one."""
    before = len(ctx['sent'])
    assert ctx['client'].get('/api/invites').status_code in (401, 403)
    assert ctx['client'].post('/api/invites', json={'email': 'x@y.com'}).status_code in (401, 403)
    assert ctx['client'].post('/api/invites/inv-1/revoke').status_code in (401, 403)
    assert ctx['client'].get('/api/waitlist').status_code in (401, 403)
    assert ctx['client'].post('/api/waitlist/w-1/invite').status_code in (401, 403)
    assert len(ctx['sent']) == before


def test_admin_and_employee_may_work_the_desk(ctx):
    for who in ('admin', 'emp'):
        assert ctx['client'].get('/api/invites', headers=ctx[who]).status_code == 200
        assert ctx['client'].get('/api/waitlist', headers=ctx[who]).status_code == 200
        assert ctx['client'].post('/api/invites', json={'email': 'a@b.com'},
                                  headers=ctx[who]).status_code == 200


def test_a_non_staff_role_is_refused_and_never_reaches_the_platform(ctx):
    before = len(ctx['sent'])
    assert ctx['client'].get('/api/invites', headers=ctx['trainer']).status_code == 403
    assert ctx['client'].post('/api/invites', json={'email': 'a@b.com'},
                              headers=ctx['trainer']).status_code == 403
    assert ctx['client'].post('/api/invites/inv-1/revoke', headers=ctx['trainer']).status_code == 403
    assert ctx['client'].get('/api/waitlist', headers=ctx['trainer']).status_code == 403
    assert ctx['client'].post('/api/waitlist/w-1/invite', headers=ctx['trainer']).status_code == 403
    assert len(ctx['sent']) == before


def test_the_desk_has_no_delete(ctx):
    """Revoke is reversible-by-re-inviting and attributed; DELETE is neither, so it must not
    exist on this surface."""
    assert ctx['client'].delete('/api/invites', headers=ctx['admin']).status_code == 405
    assert ctx['client'].delete('/api/waitlist', headers=ctx['admin']).status_code == 405
    assert ctx['client'].post('/api/waitlist', json={}, headers=ctx['admin']).status_code == 405


# ------------------------------------------------------------------------------ the secret

def test_secret_is_server_side_only(ctx):
    r = ctx['client'].get('/api/invites', headers=ctx['admin'])
    assert ctx['sent'][-1]['headers']['X-ELP-Metrics-Secret'] == 'test-metrics-secret'
    assert 'test-metrics-secret' not in r.get_data(as_text=True)
    assert 'X-ELP-Metrics-Secret' not in dict(r.headers)
