"""
Self-tests for the platform -> dashboard finance-event bridge
(/api/metrics/finance-event, the money-in branch only — escrow mirroring is
covered by test_escrow.py).

Run:  cd backend && python -m pytest test_finance_event.py -v

Uses the Flask test client against a fresh temp SQLite DB. Asserts the three
fixes this bridge needed: (1) occurred_at lands the Revenue row in the right
month instead of receive-time, (2) a non-EGP/USD event keeps its true amount
(amount_original/currency/needs_fx) instead of being silently zeroed, and
(3) an event carrying course_id/course_slug/course_title attaches to the real
Course row instead of only being findable by the description substring scan.
"""
import os
import datetime
import tempfile

import pytest

# Point the app at a throwaway SQLite file BEFORE importing the app module.
_tmpdir = tempfile.mkdtemp()
_dbpath = os.path.join(_tmpdir, 'finance_event_test.db')
os.environ['DATABASE_URL'] = f'sqlite:///{_dbpath}'
os.environ['SECRET_KEY'] = 'test-secret-key-for-finance-event'
os.environ['METRICS_SECRET'] = 'test-metrics-secret'

import app as appmod  # noqa: E402
from app import app as flask_app, db, Course, Revenue  # noqa: E402


@pytest.fixture
def ctx():
    with flask_app.app_context():
        db.drop_all()
        db.create_all()
    client = flask_app.test_client()
    secret_h = {'X-ELP-Metrics-Secret': os.environ['METRICS_SECRET']}
    yield client, secret_h


def _post(client, headers, **body):
    return client.post('/api/metrics/finance-event', json=body, headers=headers)


# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------

def test_rejects_without_secret(ctx):
    client, _ = ctx
    r = _post(client, {}, payment_id='PAY-1', amount=100, currency='EGP')
    assert r.status_code == 401


# ---------------------------------------------------------------------------
# occurred_at -> correct month (not receive-time)
# ---------------------------------------------------------------------------

def test_occurred_at_sets_the_ledger_date_not_receive_time(ctx):
    client, secret_h = ctx
    r = _post(client, secret_h, payment_id='PAY-OCC-1', amount=500, currency='EGP',
              occurred_at='2026-05-14T10:00:00Z')
    assert r.status_code == 200
    with flask_app.app_context():
        rev = Revenue.query.filter_by(payment_id='PAY-OCC-1').first()
        assert rev.date == datetime.date(2026, 5, 14)


def test_missing_occurred_at_falls_back_to_today(ctx):
    client, secret_h = ctx
    r = _post(client, secret_h, payment_id='PAY-OCC-2', amount=500, currency='EGP')
    assert r.status_code == 200
    with flask_app.app_context():
        rev = Revenue.query.filter_by(payment_id='PAY-OCC-2').first()
        assert rev.date == datetime.date.today()


# ---------------------------------------------------------------------------
# Currency honesty
# ---------------------------------------------------------------------------

def test_egp_event_books_amount_egp_untouched(ctx):
    client, secret_h = ctx
    _post(client, secret_h, payment_id='PAY-EGP-1', amount=1200, currency='EGP')
    with flask_app.app_context():
        rev = Revenue.query.filter_by(payment_id='PAY-EGP-1').first()
        assert rev.amount_egp == 1200
        assert rev.amount_usd == 0
        assert rev.needs_fx is False
        assert rev.amount_original is None
        assert rev.currency is None


def test_usd_event_books_amount_usd_untouched(ctx):
    client, secret_h = ctx
    _post(client, secret_h, payment_id='PAY-USD-1', amount=40, currency='USD')
    with flask_app.app_context():
        rev = Revenue.query.filter_by(payment_id='PAY-USD-1').first()
        assert rev.amount_usd == 40
        assert rev.amount_egp == 0
        assert rev.needs_fx is False


def test_foreign_currency_is_not_zeroed_and_flags_needs_fx(ctx):
    client, secret_h = ctx
    r = _post(client, secret_h, payment_id='PAY-GBP-1', amount=99, amount_original=99,
              currency='GBP')
    assert r.status_code == 200
    with flask_app.app_context():
        rev = Revenue.query.filter_by(payment_id='PAY-GBP-1').first()
        assert rev.needs_fx is True
        assert rev.currency == 'GBP'
        assert rev.amount_original == 99
        # No guessed conversion — the ledger's EGP/USD totals stay honest (0), not 99.
        assert not rev.amount_egp
        assert rev.amount_usd == 0


def test_foreign_currency_falls_back_to_amount_when_amount_original_missing(ctx):
    client, secret_h = ctx
    _post(client, secret_h, payment_id='PAY-SAR-1', amount=250, currency='SAR')
    with flask_app.app_context():
        rev = Revenue.query.filter_by(payment_id='PAY-SAR-1').first()
        assert rev.needs_fx is True
        assert rev.amount_original == 250
        assert rev.currency == 'SAR'


# ---------------------------------------------------------------------------
# Course attach
# ---------------------------------------------------------------------------

def test_attaches_by_platform_course_id(ctx):
    client, secret_h = ctx
    with flask_app.app_context():
        c = Course(title='دورة العقود التجارية', platform_course_id='mongo-abc123')
        db.session.add(c)
        db.session.commit()
        course_id = c.id

    r = _post(client, secret_h, payment_id='PAY-CID-1', amount=300, currency='EGP',
              course_id='mongo-abc123')
    assert r.status_code == 200
    with flask_app.app_context():
        rev = Revenue.query.filter_by(payment_id='PAY-CID-1').first()
        assert rev.course_id == course_id
        # And the course's own `.revenues` relationship (used by revenues_for_course)
        # picks it up directly — no title-in-description scan needed.
        course = Course.query.get(course_id)
        assert rev in list(course.revenues)


def test_attaches_by_platform_course_slug(ctx):
    client, secret_h = ctx
    with flask_app.app_context():
        c = Course(title='دورة صياغة العقود', platform_course_slug='contract-drafting')
        db.session.add(c)
        db.session.commit()
        course_id = c.id

    _post(client, secret_h, payment_id='PAY-SLUG-1', amount=300, currency='EGP',
          course_slug='contract-drafting')
    with flask_app.app_context():
        rev = Revenue.query.filter_by(payment_id='PAY-SLUG-1').first()
        assert rev.course_id == course_id


def test_attaches_by_exact_course_title(ctx):
    client, secret_h = ctx
    with flask_app.app_context():
        c = Course(title='دورة التحكيم الدولي')
        db.session.add(c)
        db.session.commit()
        course_id = c.id

    _post(client, secret_h, payment_id='PAY-TITLE-1', amount=300, currency='EGP',
          course_title='دورة التحكيم الدولي')
    with flask_app.app_context():
        rev = Revenue.query.filter_by(payment_id='PAY-TITLE-1').first()
        assert rev.course_id == course_id


def test_course_fields_inside_meta_also_match(ctx):
    client, secret_h = ctx
    with flask_app.app_context():
        c = Course(title='دورة قانون الشركات', platform_course_id='mongo-xyz')
        db.session.add(c)
        db.session.commit()
        course_id = c.id

    _post(client, secret_h, payment_id='PAY-META-1', amount=300, currency='EGP',
          meta={'course_id': 'mongo-xyz'})
    with flask_app.app_context():
        rev = Revenue.query.filter_by(payment_id='PAY-META-1').first()
        assert rev.course_id == course_id


def test_no_matching_course_leaves_course_id_null(ctx):
    client, secret_h = ctx
    _post(client, secret_h, payment_id='PAY-NOCOURSE-1', amount=300, currency='EGP',
          course_id='does-not-exist')
    with flask_app.app_context():
        rev = Revenue.query.filter_by(payment_id='PAY-NOCOURSE-1').first()
        assert rev.course_id is None


# ---------------------------------------------------------------------------
# Idempotency still holds with the new fields
# ---------------------------------------------------------------------------

def test_redelivery_is_a_noop(ctx):
    client, secret_h = ctx
    r1 = _post(client, secret_h, payment_id='PAY-DUP-1', amount=100, currency='EGP')
    r2 = _post(client, secret_h, payment_id='PAY-DUP-1', amount=100, currency='EGP')
    assert r1.get_json()['revenue_id'] == r2.get_json()['revenue_id']
    assert r2.get_json()['duplicate'] is True
    with flask_app.app_context():
        assert Revenue.query.filter_by(payment_id='PAY-DUP-1').count() == 1


# ---------------------------------------------------------------------------
# Listing endpoint serializer
# ---------------------------------------------------------------------------

def test_list_revenues_exposes_fx_fields(ctx):
    client, secret_h = ctx
    from werkzeug.security import generate_password_hash as _gph
    import jwt as _jwt

    def _gen(pw):
        return _gph(pw, method='pbkdf2:sha256')

    with flask_app.app_context():
        from app import User
        admin = User(email='admin@fx-test.com', password_hash=_gen('x'),
                     name='Admin', role='admin', dashboard_role='admin', is_active=True)
        db.session.add(admin)
        db.session.commit()
        admin_id = admin.id
    admin_h = {'Authorization': f'Bearer {_jwt.encode({"user_id": admin_id}, flask_app.config["SECRET_KEY"], algorithm="HS256")}'}

    _post(client, secret_h, payment_id='PAY-LIST-1', amount=75, amount_original=75, currency='AED')
    with flask_app.app_context():
        target_id = Revenue.query.filter_by(payment_id='PAY-LIST-1').first().id
    rows = client.get('/api/revenues', headers=admin_h).get_json()
    row = next(r for r in rows if r['id'] == target_id)
    assert row['needs_fx'] is True
    assert row['currency'] == 'AED'
    assert row['amount_original'] == 75
