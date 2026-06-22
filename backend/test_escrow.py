"""
Self-tests for the Escrow & Disputes module.

Run:  cd backend && python -m pytest test_escrow.py -v

Uses the Flask test client against a fresh temp SQLite DB. Asserts the money-critical
invariants: net/commission math, idempotent release recording exactly one Revenue row,
refund path, dispute freeze + resolve (student/expert/split), employee read-only (403),
and process-auto-releases only touching past-due no-dispute sessions.
"""
import os
import datetime
import tempfile

import jwt
import pytest

# Point the app at a throwaway SQLite file BEFORE importing the app module.
_tmpdir = tempfile.mkdtemp()
_dbpath = os.path.join(_tmpdir, 'escrow_test.db')
os.environ['DATABASE_URL'] = f'sqlite:///{_dbpath}'
os.environ['SECRET_KEY'] = 'test-secret-key-for-escrow'
os.environ['METRICS_SECRET'] = 'test-metrics-secret'

import app as appmod  # noqa: E402
from app import app as flask_app, db, User, EscrowSession, Dispute, Revenue  # noqa: E402
from werkzeug.security import generate_password_hash as _gph  # noqa: E402


def generate_password_hash(pw):
    # This environment's Python lacks hashlib.scrypt (LibreSSL); use pbkdf2.
    return _gph(pw, method='pbkdf2:sha256')


def _make_token(user_id):
    return jwt.encode({'user_id': user_id}, flask_app.config['SECRET_KEY'], algorithm='HS256')


@pytest.fixture
def ctx():
    with flask_app.app_context():
        # Clean slate for every test.
        db.drop_all()
        db.create_all()
        admin = User(email='admin@test.com', password_hash=generate_password_hash('x'),
                     name='Admin', role='admin', dashboard_role='admin', is_active=True)
        emp = User(email='emp@test.com', password_hash=generate_password_hash('x'),
                   name='Emp', role='employee', dashboard_role='employee', is_active=True)
        db.session.add_all([admin, emp])
        db.session.commit()
        admin_id, emp_id = admin.id, emp.id
    client = flask_app.test_client()
    admin_h = {'Authorization': f'Bearer {_make_token(admin_id)}'}
    emp_h = {'Authorization': f'Bearer {_make_token(emp_id)}'}
    secret_h = {'X-ELP-Metrics-Secret': os.environ['METRICS_SECRET']}
    yield client, admin_h, emp_h, secret_h


def _hold(client, headers, amount=1000, **kw):
    body = {'student_name': 'Omar', 'student_email': 's@t.com',
            'expert_name': 'Expert', 'expert_email': 'e@t.com',
            'amount': amount, 'currency': 'EGP', 'ref': 'CONS-1'}
    body.update(kw)
    return client.post('/api/escrow/hold', json=body, headers=headers)


# ---------------------------------------------------------------------------

def test_hold_creates_held_session_with_correct_net_and_commission(ctx):
    client, admin_h, _, _ = ctx
    r = _hold(client, admin_h, amount=1000)
    assert r.status_code == 201
    s = r.get_json()['session']
    assert s['status'] == 'held'
    assert s['id'].startswith('ESC-')
    assert s['amount'] == 1000
    assert s['commission'] == 150.0   # 15%
    assert s['net'] == 850.0          # 85%
    assert s['release_at'] is not None


def test_hold_via_metrics_secret(ctx):
    client, _, _, secret_h = ctx
    r = _hold(client, secret_h, amount=500)
    assert r.status_code == 201
    assert r.get_json()['session']['status'] == 'held'


def test_hold_rejects_unauthorized(ctx):
    client, _, _, _ = ctx
    r = _hold(client, {}, amount=500)
    assert r.status_code in (401, 403)


def test_hold_rejects_nonpositive_amount(ctx):
    client, admin_h, _, _ = ctx
    assert _hold(client, admin_h, amount=0).status_code == 400


def test_hold_rejects_unsupported_currency(ctx):
    # The Revenue ledger only has amount_egp/amount_usd columns, so a SAR hold would
    # silently book commission as 0. It must be rejected at hold time with 400.
    client, admin_h, _, _ = ctx
    r = _hold(client, admin_h, amount=1000, currency='SAR')
    assert r.status_code == 400
    with flask_app.app_context():
        assert EscrowSession.query.count() == 0   # nothing held
    # USD (a supported currency) still works.
    assert _hold(client, admin_h, amount=1000, currency='USD').status_code == 201


def test_release_records_exactly_one_commission_revenue_and_is_idempotent(ctx):
    client, admin_h, _, _ = ctx
    sid = _hold(client, admin_h, amount=1000).get_json()['session']['id']

    r1 = client.post(f'/api/escrow/{sid}/release', headers=admin_h)
    assert r1.status_code == 200
    assert r1.get_json()['session']['status'] == 'released'

    with flask_app.app_context():
        revs = Revenue.query.filter_by(source='escrow_commission').all()
        assert len(revs) == 1
        assert revs[0].amount_egp == 150.0   # commission only, taken at release

    # Second release must be rejected and must NOT record a second revenue row.
    r2 = client.post(f'/api/escrow/{sid}/release', headers=admin_h)
    assert r2.status_code == 409
    with flask_app.app_context():
        assert Revenue.query.filter_by(source='escrow_commission').count() == 1


def test_refund_path_no_commission(ctx):
    client, admin_h, _, _ = ctx
    sid = _hold(client, admin_h, amount=800).get_json()['session']['id']
    r = client.post(f'/api/escrow/{sid}/refund', headers=admin_h)
    assert r.status_code == 200
    assert r.get_json()['session']['status'] == 'refunded'
    with flask_app.app_context():
        assert Revenue.query.filter_by(source='escrow_commission').count() == 0
    # Cannot release a refunded session.
    assert client.post(f'/api/escrow/{sid}/release', headers=admin_h).status_code == 409


def test_dispute_freezes_and_blocks_double_dispute(ctx):
    client, admin_h, _, _ = ctx
    sid = _hold(client, admin_h, amount=1500).get_json()['session']['id']
    r = client.post(f'/api/escrow/{sid}/dispute', json={'party': 'student', 'reason': 'لم تتم'}, headers=admin_h)
    assert r.status_code == 201
    assert r.get_json()['session']['status'] == 'dispute'
    assert r.get_json()['dispute']['amount_frozen'] == 1500
    # No double dispute.
    assert client.post(f'/api/escrow/{sid}/dispute', json={'party': 'expert'}, headers=admin_h).status_code == 409
    # Cannot release while a dispute is open.
    assert client.post(f'/api/escrow/{sid}/release', headers=admin_h).status_code == 409


def test_dispute_resolve_student_refunds(ctx):
    client, admin_h, _, _ = ctx
    sid = _hold(client, admin_h, amount=1000).get_json()['session']['id']
    client.post(f'/api/escrow/{sid}/dispute', json={'party': 'student'}, headers=admin_h)
    did = client.get('/api/disputes', headers=admin_h).get_json()[0]['id']
    r = client.post(f'/api/dispute/{did}/resolve', json={'decision': 'student'}, headers=admin_h)
    assert r.status_code == 200
    assert r.get_json()['session']['status'] == 'refunded'
    with flask_app.app_context():
        assert Revenue.query.filter_by(source='escrow_commission').count() == 0
    # Already resolved -> reject re-resolve.
    assert client.post(f'/api/dispute/{did}/resolve', json={'decision': 'expert'}, headers=admin_h).status_code == 409


def test_dispute_resolve_expert_releases_with_commission(ctx):
    client, admin_h, _, _ = ctx
    sid = _hold(client, admin_h, amount=1000).get_json()['session']['id']
    client.post(f'/api/escrow/{sid}/dispute', json={'party': 'expert'}, headers=admin_h)
    did = client.get('/api/disputes', headers=admin_h).get_json()[0]['id']
    r = client.post(f'/api/dispute/{did}/resolve', json={'decision': 'expert'}, headers=admin_h)
    assert r.status_code == 200
    body = r.get_json()
    assert body['session']['status'] == 'released'
    assert body['result']['released_net'] == 850.0
    assert body['result']['commission'] == 150.0
    with flask_app.app_context():
        assert Revenue.query.filter_by(source='escrow_commission').count() == 1


def test_dispute_resolve_split(ctx):
    client, admin_h, _, _ = ctx
    sid = _hold(client, admin_h, amount=1000).get_json()['session']['id']
    client.post(f'/api/escrow/{sid}/dispute', json={'party': 'student'}, headers=admin_h)
    did = client.get('/api/disputes', headers=admin_h).get_json()[0]['id']
    r = client.post(f'/api/dispute/{did}/resolve', json={'decision': 'split', 'split_pct': 60}, headers=admin_h)
    assert r.status_code == 200
    res = r.get_json()['result']
    # 60% expert share = 600 gross; 15% commission on it = 90; expert net = 510; student refund = 400.
    assert res['commission'] == 90.0
    assert res['expert_net'] == 510.0
    assert res['student_refund'] == 400.0
    assert r.get_json()['session']['status'] == 'released'
    with flask_app.app_context():
        assert Revenue.query.filter_by(source='escrow_commission').count() == 1


def test_dispute_resolve_split_zero_is_refund(ctx):
    # split_pct == 0 means the expert gets nothing -> effectively a full refund.
    client, admin_h, _, _ = ctx
    sid = _hold(client, admin_h, amount=1000).get_json()['session']['id']
    client.post(f'/api/escrow/{sid}/dispute', json={'party': 'student'}, headers=admin_h)
    did = client.get('/api/disputes', headers=admin_h).get_json()[0]['id']
    r = client.post(f'/api/dispute/{did}/resolve', json={'decision': 'split', 'split_pct': 0}, headers=admin_h)
    assert r.status_code == 200
    res = r.get_json()['result']
    assert res['commission'] == 0
    assert res['expert_net'] == 0
    assert res['student_refund'] == 1000.0
    assert r.get_json()['session']['status'] == 'refunded'   # not 'released'
    with flask_app.app_context():
        assert Revenue.query.filter_by(source='escrow_commission').count() == 0


def test_employee_cannot_write_but_can_read(ctx):
    client, admin_h, emp_h, _ = ctx
    sid = _hold(client, admin_h, amount=1000).get_json()['session']['id']
    # Writes -> 403.
    assert client.post(f'/api/escrow/{sid}/release', headers=emp_h).status_code == 403
    assert client.post(f'/api/escrow/{sid}/refund', headers=emp_h).status_code == 403
    assert client.post(f'/api/escrow/{sid}/dispute', json={'party': 'student'}, headers=emp_h).status_code == 403
    assert client.post('/api/escrow/process-auto-releases', headers=emp_h).status_code == 403
    # Hold via employee JWT (no secret, not admin) -> 403.
    assert _hold(client, emp_h, amount=100).status_code == 403
    # Reads -> 200.
    assert client.get('/api/escrow', headers=emp_h).status_code == 200
    assert client.get('/api/disputes', headers=emp_h).status_code == 200
    assert client.get('/api/escrow/metrics', headers=emp_h).status_code == 200


def test_process_auto_releases_only_past_due_no_dispute(ctx):
    client, admin_h, _, _ = ctx
    # Past-due, no dispute -> should release.
    due_id = _hold(client, admin_h, amount=1000).get_json()['session']['id']
    # Future release_at -> should NOT release.
    future_id = _hold(client, admin_h, amount=1000).get_json()['session']['id']
    # Past-due but with an open dispute -> should NOT release.
    disputed_id = _hold(client, admin_h, amount=1000).get_json()['session']['id']
    client.post(f'/api/escrow/{disputed_id}/dispute', json={'party': 'student'}, headers=admin_h)

    past = datetime.datetime.utcnow() - datetime.timedelta(hours=1)
    future = datetime.datetime.utcnow() + datetime.timedelta(hours=48)
    with flask_app.app_context():
        EscrowSession.query.get(due_id).release_at = past
        EscrowSession.query.get(future_id).release_at = future
        EscrowSession.query.get(disputed_id).release_at = past
        db.session.commit()

    r = client.post('/api/escrow/process-auto-releases', headers=admin_h)
    assert r.status_code == 200
    released = r.get_json()['released']
    assert due_id in released
    assert future_id not in released
    assert disputed_id not in released
    with flask_app.app_context():
        assert EscrowSession.query.get(due_id).status == 'released'
        assert EscrowSession.query.get(future_id).status == 'held'
        assert EscrowSession.query.get(disputed_id).status == 'dispute'
        # Exactly one commission revenue (only the due one).
        assert Revenue.query.filter_by(source='escrow_commission').count() == 1


def test_metrics_shape(ctx):
    client, admin_h, _, _ = ctx
    a = _hold(client, admin_h, amount=1000).get_json()['session']['id']
    _hold(client, admin_h, amount=2000)
    client.post(f'/api/escrow/{a}/release', headers=admin_h)
    m = client.get('/api/escrow/metrics', headers=admin_h).get_json()
    assert m['held_count'] == 1
    assert m['held_sum'] == 2000
    assert m['released_count'] == 1
    assert m['released_sum'] == 1000
    assert m['released_commission_sum'] == 150.0
    assert 'disputes_count' in m
