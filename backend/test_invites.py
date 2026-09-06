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
  5b. wave 2 (2026-09-06 م٢): the NAME is required (≥2 chars) and the email is OPTIONAL — a
     name-only invite sends NO `email` key at all (the platform's unique index is partial on
     `email: {$type: "string"}`; an empty string IS a string and would collide the first two
     name-less invites),
  5c. «باب المؤسسين» (م٣): GET open to staff, POST admin-only, audited only on success,
  6. revoke / waitlist-invite send NO invented body — an extra key is swallowed silently by
     the platform (as `admin_note` was on market close) and vanishes without a trace,
  7. the shared secret travels as an outbound header and never reaches the browser.

The platform is stubbed at the `requests` layer — no network, no live platform needed.
"""
import json
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
    body = ctx['client'].post('/api/invites', json={'email': 'new@example.com', 'name': 'جديد'},
                              headers=ctx['admin']).get_json()
    assert body['link'] == 'https://app.example.net/invite/TOK'


def test_email_is_trimmed_and_lowercased_before_the_platform_sees_it(ctx):
    """Two rows for one human is what an un-sanitized email costs at a unique index."""
    ctx['client'].post('/api/invites', json={'email': '  Ali@Example.COM  ', 'name': 'علي'},
                       headers=ctx['admin'])
    assert ctx['sent'][-1]['json']['email'] == 'ali@example.com'


def test_a_bad_email_is_refused_here_and_never_reaches_the_platform(ctx):
    before = len(ctx['sent'])
    for bad in ('nope', 'a@', '@b.com', 'a@b'):
        r = ctx['client'].post('/api/invites', json={'email': bad, 'name': 'جديد'},
                               headers=ctx['admin'])
        assert r.status_code == 400, bad
    assert len(ctx['sent']) == before      # refused HERE, not by the platform


# ------------------------------------------------- wave 2 (م٢): name required, email optional

def test_a_name_only_invite_is_created_and_sends_no_email_key_at_all(ctx):
    """The platform's unique index on `email` is PARTIAL (`{email: {$type: "string"}}`). An
    empty string is a string: send `email: ''` and the SECOND name-only invite collides with
    the first. So the key must be absent — not empty, not null — for every blank spelling."""
    for blank in ({'name': 'علي'}, {'name': 'علي', 'email': ''}, {'name': 'علي', 'email': '   '},
                  {'name': 'علي', 'email': None}):
        r = ctx['client'].post('/api/invites', json=blank, headers=ctx['admin'])
        assert r.status_code == 200, blank
        call = ctx['sent'][-1]
        assert call['method'] == 'POST' and call['path'] == '/api/bridge/invites'
        assert 'email' not in call['json'], blank
        assert call['json']['name'] == 'علي'
        assert call['json']['invited_by'] == 'admin@test.com'


def test_a_name_only_invite_is_audited_by_name(ctx):
    ctx['client'].post('/api/invites', json={'name': 'علي'}, headers=ctx['admin'])
    rows = _audits('invite.create')
    assert len(rows) == 1
    assert rows[0].target == 'علي'
    assert json.loads(rows[0].meta_json) == {'name': 'علي', 'has_email': False}


def test_a_short_or_missing_name_is_refused_here_and_never_reaches_the_platform(ctx):
    before = len(ctx['sent'])
    for body in ({}, {'name': ''}, {'name': ' '}, {'name': 'x'}, {'name': ' x '},
                 {'email': 'new@example.com'}, {'email': 'new@example.com', 'name': 'x'}):
        r = ctx['client'].post('/api/invites', json=body, headers=ctx['admin'])
        assert r.status_code == 400, body
        assert 'الاسم' in r.get_json()['error']
    assert len(ctx['sent']) == before
    assert _audits('invite.create') == []


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
    r = ctx['client'].post('/api/invites', json={'email': 'dup@example.com', 'name': 'جديد'},
                           headers=ctx['admin'])
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
    assert ctx['client'].post('/api/invites', json={'email': 'x@y.com', 'name': 'جديد'}).status_code in (401, 403)
    assert ctx['client'].post('/api/invites/inv-1/revoke').status_code in (401, 403)
    assert ctx['client'].get('/api/invites/inv-1').status_code in (401, 403)
    assert ctx['client'].get('/api/waitlist').status_code in (401, 403)
    assert ctx['client'].post('/api/waitlist/w-1/invite').status_code in (401, 403)
    assert ctx['client'].get('/api/settings/founding').status_code in (401, 403)
    assert ctx['client'].post('/api/settings/founding', json={'open': False}).status_code in (401, 403)
    assert ctx['client'].get('/api/settings/invites').status_code in (401, 403)
    assert ctx['client'].post('/api/settings/invites', json={'welcome_video_url': 'x'}).status_code in (401, 403)
    assert len(ctx['sent']) == before


def test_admin_and_employee_may_work_the_desk(ctx):
    for who in ('admin', 'emp'):
        assert ctx['client'].get('/api/invites', headers=ctx[who]).status_code == 200
        assert ctx['client'].get('/api/waitlist', headers=ctx[who]).status_code == 200
        assert ctx['client'].get('/api/invites/inv-1', headers=ctx[who]).status_code == 200
        assert ctx['client'].get('/api/settings/invites', headers=ctx[who]).status_code == 200
        assert ctx['client'].post('/api/invites', json={'email': 'a@b.com', 'name': 'جديد'},
                                  headers=ctx[who]).status_code == 200


def test_a_non_staff_role_is_refused_and_never_reaches_the_platform(ctx):
    before = len(ctx['sent'])
    assert ctx['client'].get('/api/invites', headers=ctx['trainer']).status_code == 403
    assert ctx['client'].post('/api/invites', json={'email': 'a@b.com', 'name': 'جديد'},
                              headers=ctx['trainer']).status_code == 403
    assert ctx['client'].post('/api/invites/inv-1/revoke', headers=ctx['trainer']).status_code == 403
    assert ctx['client'].get('/api/invites/inv-1', headers=ctx['trainer']).status_code == 403
    assert ctx['client'].get('/api/waitlist', headers=ctx['trainer']).status_code == 403
    assert ctx['client'].post('/api/waitlist/w-1/invite', headers=ctx['trainer']).status_code == 403
    assert ctx['client'].get('/api/settings/founding', headers=ctx['trainer']).status_code == 403
    assert ctx['client'].post('/api/settings/founding', json={'open': False},
                              headers=ctx['trainer']).status_code == 403
    assert ctx['client'].get('/api/settings/invites', headers=ctx['trainer']).status_code == 403
    assert ctx['client'].post('/api/settings/invites', json={'welcome_video_url': 'x'},
                              headers=ctx['trainer']).status_code == 403
    assert len(ctx['sent']) == before


# --------------------------------------------------------- «تفصيل المدعوّ» (wave 3, د٨) drawer

INVITE_DETAIL_ROW = {
    'id': 'inv-2', 'email': 'nour@example.com', 'name': 'نور حسن', 'status': 'opened',
    'stage': 'exercised', 'roles': ['lawyer'], 'specialty': 'civil', 'years': 3,
    'invited_by': {'user_id': None, 'name': 'فريق البروفيسور', 'kind': 'founder', 'video_url': None},
    'inviter': {'user_id': None, 'name': 'فريق البروفيسور', 'kind': 'founder', 'video_url': None},
    'timeline': [{'key': 'created', 'at': '2026-09-06T10:00:00'}, {'key': 'opened', 'at': '2026-09-06T12:00:00'}],
    'exercises': [{'role': 'lawyer', 'prompt_id': 'p1', 'question': 'سؤال', 'ai_answer': 'إجابة',
                   'ai_source': 'live', 'verdict': 'correct', 'notes': ''}],
    'declaration': None, 'founding': False, 'user': None,
}


def test_invite_detail_forwards_to_the_right_bridge_path_and_body_reaches_the_browser_unchanged(ctx):
    """The drawer needs the FULL document — exercises, declaration, timeline, inviter — and the
    proxy must add no opinion of its own (a thin proxy over a per-invite bridge path)."""
    ctx['replies'][('GET', '/api/bridge/invites/inv-2')] = FakeResp(200, INVITE_DETAIL_ROW)
    r = ctx['client'].get('/api/invites/inv-2', headers=ctx['admin'])
    assert r.status_code == 200
    call = ctx['sent'][-1]
    assert call['method'] == 'GET' and call['path'] == '/api/bridge/invites/inv-2'
    body = r.get_json()
    assert body['exercises'][0]['question'] == 'سؤال'
    assert body['timeline'][1]['key'] == 'opened'
    assert body['inviter']['kind'] == 'founder'


GRADUATE_DETAIL_ROW = dict(
    INVITE_DETAIL_ROW, id='inv-3', roles=['graduate'], exercises=[],
    proposals=[{'role': 'graduate', 'label': 'خريج', 'proposal': 'عقود العمل أولًا'}],
)


def test_a_graduate_proposal_reaches_the_browser_with_no_exercise_to_carry_it(ctx):
    """The graduate has NO exercise (`EXERCISE_ROLES` excludes them) — their «تحب تتعلّم إيه
    أولًا؟» rides only in the bridge's top-level `proposals`. The proxy must pass that list
    through untouched, or the drawer has nothing to draw."""
    ctx['replies'][('GET', '/api/bridge/invites/inv-3')] = FakeResp(200, GRADUATE_DETAIL_ROW)
    r = ctx['client'].get('/api/invites/inv-3', headers=ctx['admin'])
    assert r.status_code == 200
    body = r.get_json()
    assert body['exercises'] == []
    assert body['proposals'] == [{'role': 'graduate', 'label': 'خريج', 'proposal': 'عقود العمل أولًا'}]


def test_invite_detail_404_is_surfaced_not_swallowed(ctx):
    """A revoked-or-gone invite id must read as «مش موجودة», never as an empty 200 that the
    drawer would render as a blank person."""
    ctx['replies'][('GET', '/api/bridge/invites/gone')] = FakeResp(404, {'detail': 'الدعوة دي مش موجودة.'})
    r = ctx['client'].get('/api/invites/gone', headers=ctx['admin'])
    assert r.status_code == 404
    assert r.get_json()['error'] == 'الدعوة دي مش موجودة.'


# ----------------------------------------------------- إعدادات الدعوة (wave 3, د٨) — ج٥

def test_invite_settings_read_forwards_to_the_bridge_and_is_open_to_staff(ctx):
    ctx['replies'][('GET', '/api/bridge/settings/invites')] = FakeResp(
        200, {'welcome_video_url': 'https://youtu.be/x', 'member_invite_quota': 5,
              'founder_name': None, 'updated_at': '2026-09-07T10:00:00'})
    for who in ('admin', 'emp'):
        r = ctx['client'].get('/api/settings/invites', headers=ctx[who])
        assert r.status_code == 200, who
        call = ctx['sent'][-1]
        assert call['method'] == 'GET' and call['path'] == '/api/bridge/settings/invites'
        assert r.get_json()['member_invite_quota'] == 5


def test_invite_settings_write_is_admin_only(ctx):
    """A platform-wide setting: an employee may SEE it, only an admin changes it — same
    protection level as «باب المؤسسين»."""
    before = len(ctx['sent'])
    r = ctx['client'].post('/api/settings/invites', json={'welcome_video_url': 'https://youtu.be/x'},
                           headers=ctx['emp'])
    assert r.status_code == 403
    assert len(ctx['sent']) == before


def test_invite_settings_write_forwards_only_the_fields_sent(ctx):
    """Omitting a field must mean «leave it alone» — sending it (even empty) would let one save
    of the welcome-video field silently wipe the OTHER admin's quota, or vice versa."""
    ctx['replies'][('POST', '/api/bridge/settings/invites')] = FakeResp(
        200, {'welcome_video_url': 'https://youtu.be/x', 'member_invite_quota': None,
              'founder_name': None, 'updated_at': '2026-09-07T10:00:00'})
    ctx['client'].post('/api/settings/invites', json={'welcome_video_url': 'https://youtu.be/x'},
                       headers=ctx['admin'])
    call = ctx['sent'][-1]
    assert call['method'] == 'POST' and call['path'] == '/api/bridge/settings/invites'
    assert call['json'] == {'welcome_video_url': 'https://youtu.be/x'}

    ctx['replies'][('POST', '/api/bridge/settings/invites')] = FakeResp(
        200, {'welcome_video_url': None, 'member_invite_quota': 8,
              'founder_name': None, 'updated_at': '2026-09-07T10:00:00'})
    ctx['client'].post('/api/settings/invites', json={'member_invite_quota': 8}, headers=ctx['admin'])
    call = ctx['sent'][-1]
    assert call['json'] == {'member_invite_quota': 8}


def test_invite_settings_empty_video_url_clears_it(ctx):
    """An empty string is how the admin removes the video — it must reach the platform as
    such (None), not be dropped as a falsy value."""
    ctx['replies'][('POST', '/api/bridge/settings/invites')] = FakeResp(
        200, {'welcome_video_url': None, 'member_invite_quota': None,
              'founder_name': None, 'updated_at': '2026-09-07T10:00:00'})
    ctx['client'].post('/api/settings/invites', json={'welcome_video_url': ''}, headers=ctx['admin'])
    assert ctx['sent'][-1]['json'] == {'welcome_video_url': None}


def test_invite_settings_rejects_a_non_numeric_or_negative_quota_before_the_platform(ctx):
    before = len(ctx['sent'])
    for bad in ('abc', -1, 3.5):
        r = ctx['client'].post('/api/settings/invites', json={'member_invite_quota': bad},
                               headers=ctx['admin'])
        assert r.status_code == 400, bad
    assert len(ctx['sent']) == before


def test_invite_settings_rejects_an_empty_body_before_the_platform(ctx):
    before = len(ctx['sent'])
    for body in ({}, {'member_invite_quota': None}):
        r = ctx['client'].post('/api/settings/invites', json=body, headers=ctx['admin'])
        assert r.status_code == 400, body
    assert len(ctx['sent']) == before


def test_invite_settings_write_is_audited_only_on_success(ctx):
    ctx['replies'][('POST', '/api/bridge/settings/invites')] = FakeResp(500, {'detail': 'boom'})
    assert ctx['client'].post('/api/settings/invites', json={'member_invite_quota': 5},
                              headers=ctx['admin']).status_code == 500
    assert _audits('settings.invites') == []
    ctx['replies'][('POST', '/api/bridge/settings/invites')] = FakeResp(
        200, {'welcome_video_url': None, 'member_invite_quota': 5,
              'founder_name': None, 'updated_at': '2026-09-07T10:00:00'})
    assert ctx['client'].post('/api/settings/invites', json={'member_invite_quota': 5},
                              headers=ctx['admin']).status_code == 200
    rows = _audits('settings.invites')
    assert len(rows) == 1
    assert rows[0].actor_email == 'admin@test.com'


# ---------------------------------------------- فيديو المنصّة على إعدادات الدعوة (ملحق ٣ب-٢)

def test_invite_settings_write_forwards_platform_video_url_alone(ctx):
    """`platform_video_url` must travel like `welcome_video_url` — its own key, untouched when
    the admin only means to change the OTHER video."""
    ctx['replies'][('POST', '/api/bridge/settings/invites')] = FakeResp(
        200, {'welcome_video_url': None, 'platform_video_url': 'https://youtu.be/p',
              'member_invite_quota': None, 'founder_name': None, 'updated_at': '2026-09-07T10:00:00'})
    ctx['client'].post('/api/settings/invites', json={'platform_video_url': 'https://youtu.be/p'},
                       headers=ctx['admin'])
    call = ctx['sent'][-1]
    assert call['method'] == 'POST' and call['path'] == '/api/bridge/settings/invites'
    assert call['json'] == {'platform_video_url': 'https://youtu.be/p'}


def test_invite_settings_empty_platform_video_url_clears_it(ctx):
    ctx['replies'][('POST', '/api/bridge/settings/invites')] = FakeResp(
        200, {'welcome_video_url': None, 'platform_video_url': None,
              'member_invite_quota': None, 'founder_name': None, 'updated_at': '2026-09-07T10:00:00'})
    ctx['client'].post('/api/settings/invites', json={'platform_video_url': ''}, headers=ctx['admin'])
    assert ctx['sent'][-1]['json'] == {'platform_video_url': None}


def test_invite_settings_write_is_admin_only_for_platform_video_too(ctx):
    before = len(ctx['sent'])
    r = ctx['client'].post('/api/settings/invites', json={'platform_video_url': 'https://youtu.be/p'},
                           headers=ctx['emp'])
    assert r.status_code == 403
    assert len(ctx['sent']) == before


# ---------------------------------------------------- فيديوهات الألم لكل صفة (ملحق ٣ب-٢) — admin-only

def test_invite_videos_read_forwards_to_the_bridge_and_is_admin_only(ctx):
    """Unlike welcome/platform video settings, this desk is admin-only for READS too (this
    addendum's own decision) — an employee must see an explicit forbidden state, never a silent
    empty screen that reads as «no videos configured»."""
    ctx['replies'][('GET', '/api/bridge/settings/invite-videos')] = FakeResp(
        200, {'trainer': 'https://youtu.be/t', 'lawyer': None, 'consultant': None,
              'researcher': None, 'graduate': None, 'multi': None})
    r = ctx['client'].get('/api/settings/invite-videos', headers=ctx['admin'])
    assert r.status_code == 200
    call = ctx['sent'][-1]
    assert call['method'] == 'GET' and call['path'] == '/api/bridge/settings/invite-videos'
    assert r.get_json()['trainer'] == 'https://youtu.be/t'

    before = len(ctx['sent'])
    assert ctx['client'].get('/api/settings/invite-videos', headers=ctx['emp']).status_code == 403
    assert len(ctx['sent']) == before


def test_invite_videos_write_is_admin_only(ctx):
    before = len(ctx['sent'])
    r = ctx['client'].post('/api/settings/invite-videos', json={'trainer': 'https://youtu.be/t'},
                           headers=ctx['emp'])
    assert r.status_code == 403
    assert len(ctx['sent']) == before


def test_invite_videos_write_forwards_only_the_keys_sent(ctx):
    """Omitting a key must mean «leave it alone» — the same rule as every other settings write on
    this desk (invite settings, founding door)."""
    ctx['replies'][('POST', '/api/bridge/settings/invite-videos')] = FakeResp(
        200, {'trainer': 'https://youtu.be/t', 'lawyer': None, 'consultant': None,
              'researcher': None, 'graduate': None, 'multi': None})
    ctx['client'].post('/api/settings/invite-videos', json={'trainer': 'https://youtu.be/t'},
                       headers=ctx['admin'])
    call = ctx['sent'][-1]
    assert call['method'] == 'POST' and call['path'] == '/api/bridge/settings/invite-videos'
    assert call['json'] == {'trainer': 'https://youtu.be/t'}


def test_invite_videos_empty_value_clears_that_role_only(ctx):
    ctx['replies'][('POST', '/api/bridge/settings/invite-videos')] = FakeResp(
        200, {'trainer': None, 'lawyer': None, 'consultant': None,
              'researcher': None, 'graduate': None, 'multi': None})
    ctx['client'].post('/api/settings/invite-videos', json={'trainer': ''}, headers=ctx['admin'])
    assert ctx['sent'][-1]['json'] == {'trainer': None}


def test_invite_videos_rejects_an_empty_body_before_the_platform(ctx):
    before = len(ctx['sent'])
    r = ctx['client'].post('/api/settings/invite-videos', json={}, headers=ctx['admin'])
    assert r.status_code == 400
    assert len(ctx['sent']) == before


def test_invite_videos_write_is_audited_only_on_success(ctx):
    ctx['replies'][('POST', '/api/bridge/settings/invite-videos')] = FakeResp(500, {'detail': 'boom'})
    assert ctx['client'].post('/api/settings/invite-videos', json={'trainer': 'https://youtu.be/t'},
                              headers=ctx['admin']).status_code == 500
    assert _audits('settings.invite_videos') == []
    ctx['replies'][('POST', '/api/bridge/settings/invite-videos')] = FakeResp(
        200, {'trainer': 'https://youtu.be/t', 'lawyer': None, 'consultant': None,
              'researcher': None, 'graduate': None, 'multi': None})
    assert ctx['client'].post('/api/settings/invite-videos', json={'trainer': 'https://youtu.be/t'},
                              headers=ctx['admin']).status_code == 200
    rows = _audits('settings.invite_videos')
    assert len(rows) == 1
    assert rows[0].actor_email == 'admin@test.com'


def test_invite_videos_requires_authentication(ctx):
    before = len(ctx['sent'])
    assert ctx['client'].get('/api/settings/invite-videos').status_code in (401, 403)
    assert ctx['client'].post('/api/settings/invite-videos', json={'trainer': 'x'}).status_code in (401, 403)
    assert len(ctx['sent']) == before


# ------------------------------------------------------- «باب المؤسسين» (wave 2, م٣) switch

def test_founding_switch_read_forwards_to_the_bridge_and_is_open_to_staff(ctx):
    ctx['replies'][('GET', '/api/bridge/settings/founding')] = FakeResp(
        200, {'open': True, 'updated_at': '2026-09-06T10:00:00'})
    for who in ('admin', 'emp'):
        r = ctx['client'].get('/api/settings/founding', headers=ctx[who])
        assert r.status_code == 200, who
        call = ctx['sent'][-1]
        assert call['method'] == 'GET' and call['path'] == '/api/bridge/settings/founding'
        assert r.get_json() == {'open': True, 'updated_at': '2026-09-06T10:00:00'}


def test_founding_switch_flip_is_admin_only_and_forwards_a_bool(ctx):
    """A platform-wide policy switch: an employee may SEE the door, only an admin flips it."""
    ctx['replies'][('POST', '/api/bridge/settings/founding')] = FakeResp(
        200, {'open': False, 'updated_at': '2026-09-06T10:00:00'})
    before = len(ctx['sent'])
    assert ctx['client'].post('/api/settings/founding', json={'open': False},
                              headers=ctx['emp']).status_code == 403
    assert len(ctx['sent']) == before
    r = ctx['client'].post('/api/settings/founding', json={'open': False}, headers=ctx['admin'])
    assert r.status_code == 200
    call = ctx['sent'][-1]
    assert call['method'] == 'POST' and call['path'] == '/api/bridge/settings/founding'
    assert call['json'] == {'open': False}
    assert r.get_json()['open'] is False


def test_founding_switch_refuses_a_body_without_open_before_the_platform(ctx):
    before = len(ctx['sent'])
    for body in ({}, {'opened': True}, {'value': False}):
        r = ctx['client'].post('/api/settings/founding', json=body, headers=ctx['admin'])
        assert r.status_code == 400, body
    assert len(ctx['sent']) == before
    assert _audits('settings.founding') == []


def test_founding_switch_is_audited_only_when_the_platform_accepted_it(ctx):
    ctx['replies'][('POST', '/api/bridge/settings/founding')] = FakeResp(500, {'detail': 'boom'})
    assert ctx['client'].post('/api/settings/founding', json={'open': False},
                              headers=ctx['admin']).status_code == 500
    assert _audits('settings.founding') == []
    ctx['replies'][('POST', '/api/bridge/settings/founding')] = FakeResp(
        200, {'open': False, 'updated_at': '2026-09-06T10:00:00'})
    assert ctx['client'].post('/api/settings/founding', json={'open': False},
                              headers=ctx['admin']).status_code == 200
    rows = _audits('settings.founding')
    assert len(rows) == 1
    assert rows[0].target == 'founding'
    assert rows[0].actor_email == 'admin@test.com'


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


# ------------------------------------- drawer + grouping additions (ملحق ٣ب) — grep-proof
# «مكتوبٌ صحيحًا وبلا طريقٍ للشاشة»: a field the backend returns is worthless if no line of
# index.html ever reads it. These pin the actual markers, not a re-implementation of the DOM.

def test_drawer_shows_focus_proposal_and_invite_video_source():
    with open(INDEX_HTML, encoding='utf-8') as fh:
        src = fh.read()
    assert 'full.focus' in src
    assert '<b>اقتراحه</b>' in src and 'ex.proposal' in src
    assert 'full.video_source' in src and 'full.video_url' in src
    assert '>فيديو الدعوة<' in src


def test_drawer_reads_top_level_proposals_not_only_exercise_proposals():
    """A graduate's suggestion lives ONLY in `full.proposals` (no exercise carries it). If no line
    of index.html reads that list, a stored answer renders as «—» — a screen that lies."""
    with open(INDEX_HTML, encoding='utf-8') as fh:
        src = fh.read()
    assert 'full.proposals' in src


def _render_invite_detail_body(full):
    """Run the REAL `inviteDetailBody` from index.html under node with the same helpers it uses
    (esc / money / fmtWhen / the INV_* maps), so the assertion is on what the drawer draws — not
    on a re-implementation. Skips when node is absent."""
    import shutil
    import subprocess
    import re
    node = shutil.which('node')
    if not node:
        pytest.skip('node not installed')
    with open(INDEX_HTML, encoding='utf-8') as fh:
        src = fh.read()
    start = src.index('function inviteDetailBody(i,full){')
    end = src.index('\nfunction drawInviteDetail(){', start)
    fn = src[start:end]
    # each map is `const X={...};` — `INV_TIMELINE_AR` spans lines, so read to the closing `};`
    consts = '\n'.join(re.findall(r'^const INV_(?:ROLE|VERDICT|TIMELINE)_AR=\{.*?\};', src, flags=re.M | re.S))
    esc_line = re.search(r'^function esc\(s\).*$', src, flags=re.M).group(0)
    script = (
        consts + '\n' + esc_line + '\n'
        'function money(v){return String(v);}\n'
        'function fmtWhen(iso){return iso?String(iso).slice(0,16):"—";}\n'
        + fn + '\n'
        'process.stdout.write(inviteDetailBody({}, ' + json.dumps(full, ensure_ascii=False) + '));'
    )
    out = subprocess.run([node, '-e', script], capture_output=True, text=True, timeout=30)
    assert out.returncode == 0, out.stderr
    return out.stdout


def test_drawer_draws_a_graduate_proposal_when_there_is_no_exercise_at_all():
    html = _render_invite_detail_body({'exercises': [], 'proposals': GRADUATE_DETAIL_ROW['proposals']})
    assert 'عقود العمل أولًا' in html
    assert 'خريج' in html
    assert '<b>اقتراحه</b>' in html


def test_drawer_does_not_double_print_a_proposal_that_an_exercise_already_carries():
    """`proposals` mirrors each exercise's proposal too — the drawer must draw those once (inside
    the exercise block), and only the roles WITHOUT an exercise get the extra row."""
    ex = dict(INVITE_DETAIL_ROW['exercises'][0], proposal='قسم عقود')
    html = _render_invite_detail_body({
        'exercises': [ex],
        'proposals': [{'role': 'lawyer', 'label': 'محامٍ', 'proposal': 'قسم عقود'},
                      {'role': 'graduate', 'label': 'خريج', 'proposal': 'عقود العمل أولًا'}],
    })
    assert html.count('قسم عقود') == 1
    assert html.count('عقود العمل أولًا') == 1


def test_drawer_still_prints_a_dash_when_there_is_neither_exercise_nor_proposal():
    html = _render_invite_detail_body({'exercises': [], 'proposals': []})
    assert '<b>اقتراحه</b>' not in html
    assert 'التجربة</div><div style="color:var(--muted);font-size:12.5px">—</div>' in html


def test_grouping_keys_on_inviter_user_id_not_name(ctx):
    """Two different members named the same must land in two different groups — grouping on the
    label alone would merge them. `dashboard-api.js` is the source of `invitedByUserId`;
    `index.html` must key on it."""
    api_path = os.path.join(os.path.dirname(__file__), '..', 'dashboard-cloud', 'dashboard-api.js')
    with open(api_path, encoding='utf-8') as fh:
        api_src = fh.read()
    assert 'invitedByUserId' in api_src
    with open(INDEX_HTML, encoding='utf-8') as fh:
        html_src = fh.read()
    assert 'r.invitedByUserId||r.invitedByLabel' in html_src


def test_pain_videos_panel_is_wired_into_the_invites_screen():
    with open(INDEX_HTML, encoding='utf-8') as fh:
        src = fh.read()
    assert 'painVideosPanel()' in src
    assert 'wirePainVideos(root)' in src


def test_the_hardcoded_14_day_line_is_gone_from_the_policy_paragraph():
    """The comment trail above the paragraph is allowed to mention the retired «١٤ يوم» line as
    history — only the RENDERED policy paragraph itself must no longer hard-code it."""
    with open(INDEX_HTML, encoding='utf-8') as fh:
        src = fh.read()
    lines = [ln for ln in src.splitlines() if 'المنصّة مقفولة من الخادم' in ln]
    assert len(lines) == 1, lines
    assert '١٤ يوم' not in lines[0]
    assert 'ويقرّ ويختار كلمة سر' not in lines[0]


# ------------------------------------------------ drawer «الإقرار» line — the version is a TAG, not a number

INDEX_HTML = os.path.join(os.path.dirname(__file__), '..', 'dashboard-cloud', 'index.html')


def test_drawer_declaration_prints_a_string_terms_version_not_a_dash():
    """The platform stamps `declaration.terms_version = TERMS_VERSION` — an opaque tag like «v1»
    (a string, never a number). Routing it through the numeric `money()` formatter turned every
    real version into NaN ⇒ «—», so a field that EXISTS was rendered as absent (screens never
    lie). Guard the source: the version must be stringified, never money()-formatted, and the
    `!=null` guard must survive so a genuinely missing version still reads «—»."""
    with open(INDEX_HTML, encoding='utf-8') as fh:
        src = fh.read()
    lines = [ln for ln in src.splitlines() if 'نسخة الشروط' in ln]
    assert len(lines) == 1, lines
    line = lines[0]
    assert 'money(decl.terms_version)' not in line
    assert "decl.terms_version!=null?String(decl.terms_version):'—'" in line
    assert 'esc(' in line  # still escaped — a version tag comes from the platform, not trusted HTML
