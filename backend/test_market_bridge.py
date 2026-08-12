"""
Self-tests for the «السوق» (market) bridge proxies, the topics segment write path,
and the trainer-removal primitives added 2026-08-12.

Run:  cd backend && python -m pytest test_market_bridge.py -v

These routes are THIN proxies: every decision (what a lane means, how a trainer is
deactivated without the platform re-approving them on next boot) lives server-side on
the platform. What must be true HERE, and is what these tests pin down:

  1. the METRICS_SECRET never leaves the server (it is sent as a request header from
     Flask, never returned to the browser and never accepted from it),
  2. mutations are admin-gated and land in the audit log with the acting employee,
  3. a 404 from the platform on a market route is reported as «bridge not deployed yet»
     rather than a generic failure — the dashboard renders an honest «قيد النشر» card
     off that signal instead of a zero that reads as truth,
  4. query params are validated here so a typo can't widen a lane server-side.

The platform is stubbed at the `requests` layer — no network, no live platform needed.
"""
import os
import tempfile

import jwt
import pytest

_tmpdir = tempfile.mkdtemp()
os.environ['DATABASE_URL'] = f"sqlite:///{os.path.join(_tmpdir, 'market_test.db')}"
os.environ['SECRET_KEY'] = 'test-secret-key-for-market'
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


# --------------------------------------------------------------------- market: reads

def test_market_requests_forwards_lane_need_and_status(ctx):
    """The bridge's query parameter is `lane`. FastAPI IGNORES an unknown query name, so sending
    `kind=` filtered nothing and every request came back as lane «all» — a dead server-side
    filter that only looked fine because the browser re-filters what it happens to have."""
    r = ctx['client'].get(
        '/api/platform-market-requests?kind=course_request&need_kind=course&status=open',
        headers=ctx['admin'])
    assert r.status_code == 200
    call = ctx['sent'][-1]
    assert call['path'] == '/api/bridge/market/requests'
    assert call['params']['lane'] == 'course_request'
    assert 'kind' not in call['params']          # the platform would silently ignore it
    assert call['params']['need_kind'] == 'course'
    assert call['params']['status'] == 'open'


def test_market_requests_rejects_an_unknown_lane_locally(ctx):
    """A typo must not widen the lane server-side — it falls back to 'all', never passes through."""
    ctx['client'].get('/api/platform-market-requests?kind=course-request', headers=ctx['admin'])
    assert ctx['sent'][-1]['params']['lane'] == 'all'
    ctx['client'].get('/api/platform-market-requests?status=whatever', headers=ctx['admin'])
    assert ctx['sent'][-1]['params']['status'] == 'all'


def test_knowledge_is_not_a_market_lane_and_training_offer_is(ctx):
    """`knowledge` lives in `knowledge_items`, a collection the market bridge never reads: it is
    outside the bridge's `lane` pattern and would 422 now that the name is correct. The real
    fourth lane is `training_offer` (a trainer advertising) and it must reach the platform."""
    ctx['client'].get('/api/platform-market-requests?kind=knowledge', headers=ctx['admin'])
    assert ctx['sent'][-1]['params']['lane'] == 'all'
    ctx['client'].get('/api/platform-market-requests?kind=training_offer', headers=ctx['admin'])
    assert ctx['sent'][-1]['params']['lane'] == 'training_offer'


def test_market_need_kind_all_is_not_forwarded(ctx):
    """'all' is the dashboard's own «no filter» token, not a platform value."""
    ctx['client'].get('/api/platform-market-requests?need_kind=all', headers=ctx['admin'])
    assert 'need_kind' not in ctx['sent'][-1]['params']


def test_market_limit_is_clamped(ctx):
    ctx['client'].get('/api/platform-market-requests?limit=99999', headers=ctx['admin'])
    assert ctx['sent'][-1]['params']['limit'] == 500
    ctx['client'].get('/api/platform-market-requests?limit=abc', headers=ctx['admin'])
    assert ctx['sent'][-1]['params']['limit'] == 200


def test_market_secret_is_server_side_only(ctx):
    """The browser must never see the shared secret — it travels as an outbound header."""
    r = ctx['client'].get('/api/platform-market-requests', headers=ctx['admin'])
    assert ctx['sent'][-1]['headers']['X-ELP-Metrics-Secret'] == 'test-metrics-secret'
    assert 'test-metrics-secret' not in r.get_data(as_text=True)
    assert 'X-ELP-Metrics-Secret' not in dict(r.headers)


def test_market_employee_may_read_but_not_mutate(ctx):
    assert ctx['client'].get('/api/platform-market-requests', headers=ctx['emp']).status_code == 200
    assert ctx['client'].get('/api/platform-market-demand', headers=ctx['emp']).status_code == 200
    assert ctx['client'].post('/api/platform-market-requests/r1/close',
                              json={}, headers=ctx['emp']).status_code == 403
    assert ctx['client'].post('/api/platform-market-requests/r1/hide',
                              json={'hidden': True}, headers=ctx['emp']).status_code == 403


def test_market_requires_authentication(ctx):
    assert ctx['client'].get('/api/platform-market-requests').status_code in (401, 403)
    assert ctx['client'].get('/api/platform-market-demand').status_code in (401, 403)


def test_market_demand_days_are_clamped(ctx):
    ctx['client'].get('/api/platform-market-demand?days=9999', headers=ctx['admin'])
    assert ctx['sent'][-1]['params']['days'] == 365
    ctx['client'].get('/api/platform-market-demand?days=nope', headers=ctx['admin'])
    assert ctx['sent'][-1]['params']['days'] == 90


def test_missing_market_bridge_is_reported_as_pending_deploy_not_a_failure(ctx):
    """The market bridge ships from the platform repo. Until it deploys, a 404 must be
    distinguishable so the dashboard can say «قيد النشر» instead of showing a lying zero."""
    ctx['replies']['/api/bridge/market/requests'] = FakeResp(404, {'detail': 'Not Found'})
    r = ctx['client'].get('/api/platform-market-requests', headers=ctx['admin'])
    assert r.status_code == 404
    assert r.get_json()['bridge_missing'] is True

    ctx['replies']['/api/bridge/market/demand'] = FakeResp(404, {'detail': 'Not Found'})
    r = ctx['client'].get('/api/platform-market-demand', headers=ctx['admin'])
    assert r.get_json()['bridge_missing'] is True


def test_real_platform_error_is_not_mislabelled_as_pending_deploy(ctx):
    ctx['replies']['/api/bridge/market/requests'] = FakeResp(500, {'detail': 'boom'})
    r = ctx['client'].get('/api/platform-market-requests', headers=ctx['admin'])
    assert r.status_code == 500
    assert 'bridge_missing' not in r.get_json()


# ------------------------------------------------------------------ market: mutations

def test_close_request_sends_the_model_the_platform_declares_and_audits(ctx):
    """BridgeMarketClose is {by, reason}. The old `admin_note` key was dropped by pydantic, so the
    note vanished and `closed_by` recorded the literal string "dashboard" instead of the admin."""
    r = ctx['client'].post('/api/platform-market-requests/req-9/close',
                           json={'admin_note': 'اتقفل يدويًّا'}, headers=ctx['admin'])
    assert r.status_code == 200
    call = ctx['sent'][-1]
    assert call['path'] == '/api/bridge/market/requests/req-9/close'
    assert call['json'] == {'by': 'admin@test.com', 'reason': 'اتقفل يدويًّا'}
    assert ('market.close_request', 'admin@test.com') in _audit_actions()


def test_hide_request_hits_the_route_the_platform_actually_built(ctx):
    """The moderation lever on the platform is `/hide` {hidden, by, reason} — reversible, audited
    and enforced in _public_gate/get_request/create_offer. The old button posted to `/flag-test`,
    a path that does not exist there, so every click 404'd and the UI blamed an «undeployed
    bridge». Asserting the PATH (not just the body) is what catches that class of drift."""
    ctx['client'].post('/api/platform-market-requests/req-9/hide',
                       json={'hidden': True, 'reason': 'سبام'}, headers=ctx['admin'])
    call = ctx['sent'][-1]
    assert call['path'] == '/api/bridge/market/requests/req-9/hide'
    assert call['json'] == {'hidden': True, 'by': 'admin@test.com', 'reason': 'سبام'}
    assert ('market.hide_request', 'admin@test.com') in _audit_actions()


def test_unhide_is_forwarded_as_a_real_false(ctx):
    """Un-hiding must send hidden=False, not fall back to the True default."""
    ctx['client'].post('/api/platform-market-requests/req-9/hide',
                       json={'hidden': False}, headers=ctx['admin'])
    assert ctx['sent'][-1]['json']['hidden'] is False


def test_market_list_envelope_reaches_the_browser_unchanged(ctx):
    """The board renders off {items, total, counts} — the keys the bridge really sends. Reading
    `requests`/`count` (a shape the platform never implemented) rendered «٠» + «مفيش طلبات»
    against a full board. Pin the envelope here so a contract drift fails a test, not a founder."""
    payload = {'items': [{'id': 'r1', 'kind': 'request', 'title': 'ت', 'status': 'open'}],
               'total': 1, 'counts': {'by_lane': {'request': 1}, 'by_need_kind': {}, 'by_status': {}},
               'lane': 'all', 'need_kind': '', 'status': 'all'}
    ctx['replies']['/api/bridge/market/requests'] = FakeResp(200, payload)
    body = ctx['client'].get('/api/platform-market-requests', headers=ctx['admin']).get_json()
    assert body['items'][0]['id'] == 'r1'
    assert body['total'] == 1
    assert body['counts']['by_lane']['request'] == 1


def test_a_failed_mutation_is_never_audited(ctx):
    ctx['replies']['/api/bridge/market/requests/req-9/close'] = FakeResp(409, {'detail': 'مقفول'})
    r = ctx['client'].post('/api/platform-market-requests/req-9/close', json={}, headers=ctx['admin'])
    assert r.status_code == 409
    assert _audit_actions() == []


# ------------------------------------------------------------------- topics: segment

def test_topic_segment_write_forwards_the_segment_key_and_audits(ctx):
    """⛔ The body key is `segment`, and the value is a LOCKED id from the platform's own
    vocabulary. BridgeSegmentIn reads `segment` only and treats an empty/absent one as «clear the
    human choice»: the old `target_audience` key was dropped by pydantic, arrived as "", WIPED the
    topic's stored lane — and still answered 200 while the dashboard toasted «اتسندت ✓»."""
    r = ctx['client'].post('/api/platform-topics/t1/segment',
                           json={'segment': 'new_grads'}, headers=ctx['admin'])
    assert r.status_code == 200
    call = ctx['sent'][-1]
    assert call['path'] == '/api/bridge/topics/t1/segment'
    assert call['json'] == {'segment': 'new_grads'}
    assert 'target_audience' not in call['json']   # a different (older, read-only) axis
    assert ('topic.set_segment', 'admin@test.com') in _audit_actions()


def test_topic_segment_legacy_body_key_is_still_sent_as_segment(ctx):
    """Older callers may post `target_audience`/`audience`; we re-key them, never forward them."""
    ctx['client'].post('/api/platform-topics/t1/segment',
                       json={'target_audience': 'criminal'}, headers=ctx['admin'])
    assert ctx['sent'][-1]['json'] == {'segment': 'criminal'}


def test_a_rejected_segment_is_not_audited_and_shows_the_platform_message(ctx):
    """An unknown value now 422s LOUDLY (it used to silently clear the lane and report success).
    The platform's structured detail must reach the operator as text, not «[object Object]»."""
    ctx['replies']['/api/bridge/topics/t1/segment'] = FakeResp(
        422, {'detail': {'error': 'unknown_segment',
                         'message': 'فئة غير معروفة — اختر واحدة من الفئات المعتمدة.',
                         'allowed': ['new_grads', 'general']}})
    r = ctx['client'].post('/api/platform-topics/t1/segment',
                           json={'segment': 'المحامون'}, headers=ctx['admin'])
    assert r.status_code == 422
    assert r.get_json()['error'] == 'فئة غير معروفة — اختر واحدة من الفئات المعتمدة.'
    assert _audit_actions() == []                  # no success recorded for a failed write


def test_segment_vocabulary_is_read_from_the_platform_not_defined_here(ctx):
    """The dropdown must be built from the platform's LOCKED list. Without this proxy the
    dashboard had no way to reach it, which is why it grew a second, incompatible taxonomy."""
    ctx['replies']['/api/bridge/topics/segments'] = FakeResp(
        200, [{'id': 'new_grads', 'label': 'خريجون جدد وبداية المهنة', 'count': 3}])
    r = ctx['client'].get('/api/platform-topic-segments', headers=ctx['emp'])
    assert r.status_code == 200
    assert ctx['sent'][-1]['path'] == '/api/bridge/topics/segments'
    assert r.get_json()[0]['id'] == 'new_grads'


def test_topic_segment_rejects_an_empty_audience_without_calling_the_platform(ctx):
    before = len(ctx['sent'])
    r = ctx['client'].post('/api/platform-topics/t1/segment', json={'target_audience': '  '},
                           headers=ctx['admin'])
    assert r.status_code == 400
    assert len(ctx['sent']) == before          # nothing forwarded
    assert _audit_actions() == []


def test_pending_topic_decision_uses_the_notifying_route_and_is_audited(ctx):
    """approve/reject must hit /topics/{id}/approve|reject — the PUT/DELETE pair skips the
    author notification and hard-deletes a member's topic with its comments."""
    ctx['client'].post('/api/platform-pending-topics/t7/approve', headers=ctx['emp'])
    assert ctx['sent'][-1]['path'] == '/api/bridge/topics/t7/approve'
    assert ('topic.approve', 'emp@test.com') in _audit_actions()

    ctx['client'].post('/api/platform-pending-topics/t7/reject', headers=ctx['admin'])
    assert ctx['sent'][-1]['path'] == '/api/bridge/topics/t7/reject'
    assert ('topic.reject', 'admin@test.com') in _audit_actions()


def test_unknown_topic_decision_is_refused(ctx):
    r = ctx['client'].post('/api/platform-pending-topics/t7/purge', headers=ctx['admin'])
    assert r.status_code == 400


# ------------------------------------------------------- trainer removal («محمد افندي»)

def test_trainer_deactivate_is_admin_only(ctx):
    assert ctx['client'].post('/api/platform-trainers/u1/deactivate', json={},
                              headers=ctx['emp']).status_code == 403
    assert ctx['client'].post('/api/platform-users/u1/flag-test', json={'is_test': True},
                              headers=ctx['emp']).status_code == 403


def test_trainer_deactivate_forwards_reason_and_test_flag_and_audits(ctx):
    r = ctx['client'].post('/api/platform-trainers/u1/deactivate',
                           json={'reason': 'حساب ديمو', 'is_test': True,
                                 'email': 'admin@demo.com'},
                           headers=ctx['admin'])
    assert r.status_code == 200
    call = ctx['sent'][-1]
    assert call['path'] == '/api/bridge/trainers/u1/deactivate'
    assert call['json'] == {'reason': 'حساب ديمو', 'is_test': True}
    actions = _audit_actions()
    assert ('trainer.deactivate', 'admin@test.com') in actions
    with flask_app.app_context():
        row = AuditLog.query.filter_by(action='trainer.deactivate').first()
        assert 'admin@demo.com' in (row.meta_json or '')   # WHO was removed is recorded


def test_flag_user_test_defaults_to_true_and_can_be_cleared(ctx):
    ctx['client'].post('/api/platform-users/u1/flag-test', json={}, headers=ctx['admin'])
    assert ctx['sent'][-1]['json'] == {'is_test': True}
    ctx['client'].post('/api/platform-users/u1/flag-test', json={'is_test': False},
                       headers=ctx['admin'])
    assert ctx['sent'][-1]['json'] == {'is_test': False}
    assert [a for a, _ in _audit_actions()].count('user.flag_test') == 2


def test_deactivate_not_yet_on_platform_surfaces_the_platform_status(ctx):
    """Until the platform ships the endpoint the dashboard degrades gracefully: a real 404
    reaches the client (the JS turns it into «لسه ما اتنشرش»), and nothing is audited."""
    ctx['replies']['/api/bridge/trainers/u1/deactivate'] = FakeResp(404, {'detail': 'Not Found'})
    r = ctx['client'].post('/api/platform-trainers/u1/deactivate', json={}, headers=ctx['admin'])
    assert r.status_code == 404
    assert _audit_actions() == []


def test_no_route_can_be_driven_by_a_browser_supplied_secret(ctx):
    """Metrics-secret auth is for the PLATFORM calling us; these dashboard routes are
    session-authenticated only. A caller presenting the secret must still be rejected."""
    h = {'X-ELP-Metrics-Secret': 'test-metrics-secret'}
    for path in ('/api/platform-market-requests', '/api/platform-market-demand'):
        assert ctx['client'].get(path, headers=h).status_code in (401, 403)
    assert ctx['client'].post('/api/platform-trainers/u1/deactivate', json={},
                              headers=h).status_code in (401, 403)
