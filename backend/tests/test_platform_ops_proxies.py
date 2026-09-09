# -*- coding: utf-8 -*-
"""الجسران المهملان: «كل اللي مستنيك» وتقرير الأرباح والخسائر (AUDIT/dash/02_data_sources.md ع-٧).

Run:  cd backend && python3 -m pytest -q tests/test_platform_ops_proxies.py

المنصّة تنشر `GET /api/bridge/ops/queue` (١٥ عدّادًا لكل ما ينتظر المؤسس + نبضات الحارس +
تنبيهاته) و`GET /api/bridge/ops/pnl` (بنود إيراد حقيقية بالعملات + تكاليف + صافٍ) — وكان
`grep 'ops/queue' elprofessor-dashboard/` يرجع **صفرًا**: حمولة حقيقية بلا قارئ.

ما يثبّته هذا الملف:
  ١. البروكسيان موجودان ويردّان حمولة المنصّة **كما هي** (لا إعادة اشتقاق في اللوحة — رقمٌ
     يُحسب مرّتين هو رقمان يختلفان يومًا ما، ودايجست تليجرام يقرأ نفس المصدر).
  ٢. السرّ المشترك يُرسَل في الترويسة، ولا يتسرّب إلى المتصفّح أبدًا.
  ٣. `month=` يمرّ للتقرير كما كتبه المستخدم.
  ٤. **من يقرأ**: أدمن فقط. الطابور يحمل مبالغ سحوبات ومراجع دفعات، والتقرير هو الدفتر
     نفسه — نفس مصفوفة F-095 التي تُبعد `employee` عن المال.
  ٥. عطل الجسر لا يُخترَع له بديل: ٥٠٢/٥٠٣ يعبران، فالشاشة تقول «تعذّر» بدل صفرٍ مطمئن.
"""
import datetime

import jwt
import pytest
from werkzeug.security import generate_password_hash

from app import app as flask_app, db, User  # noqa: E402

QUEUE_PAYLOAD = {
    'generated_at': '2026-09-09T08:00:00+00:00',
    'trainer_applications_pending': {'count': 3, 'oldest_hours': 51.2, 'names': ['أ', 'ب', 'ج']},
    'courses_pending': {'count': 1, 'titles': ['عقود المقاولات']},
    'manual_payments_pending': {'count': 2, 'oldest_hours': 30.0, 'ages_hours': [30.0, 4.0]},
    'wallet_payouts_pending': {'count': 1, 'total_amount': 1200.0, 'oldest_hours': 9.0},
    'stuck_card_payments': {'count': 0, 'orders': []},
    'course_interests_24h': 7,
    'training_interests_24h': 2,
    'course_split_pending': {'count': 0, 'rows': []},
    'testimonials_pending': 0,
    'topics_drafts': 311,
    'founding_leads_new': {'count': 9, 'oldest_hours': 1600.0},
    'lead_magnet_24h': {'count_24h': 4, 'awaiting_asset': 6},
    'lead_magnet_awaiting_asset': 6,
    'live_needs_decision': [{'slug': 'live-1', 'title': 'ورشة حيّة', 'live_status': 'needs_decision',
                             'reserved_count': 4, 'quorum': 8}],
    'heartbeats': {'tick_last': '2026-09-09T07:00:00', 'remind_last': None,
                   'sla_last': None, 'backup_last': None},
    'alerts': ['⏰ طلب بلا أول رد منذ 40 ساعة: مراجعة عقد إيجار'],
}

PNL_PAYLOAD = {
    'ok': True,
    'month': '2026-09',
    'revenue_lines': [
        {'key': 'consults', 'label': 'استشارات', 'currency': 'EGP', 'amount': 0.0, 'count': 0},
        {'key': 'courses', 'label': 'دورات', 'currency': 'SAR', 'amount': 750.0, 'count': 2},
    ],
    'totals_by_currency': {'EGP': 0.0, 'SAR': 750.0},
    'total': {'amount': 0.0, 'currency': 'EGP', 'label': 'إجمالي الإيراد بالجنيه'},
    'revenue_other_currencies': {'SAR': 750.0},
    'refunds_by_currency': {},
    'costs': {'lines': [{'key': 'infra', 'label': 'بنية تحتية واستضافة (تقديري/شهري)',
                         'amount': 800.0}], 'total': 801.4, 'currency': 'EGP'},
    'net': {'amount': -801.4, 'currency': 'EGP', 'label': 'الصافي بالجنيه (بعد التكاليف التقديرية)'},
    'notes': ['العملات لا تُجمع ولا تُحوَّل تلقائيًا'],
}

PAYOUTS_PAYLOAD = {
    'count': 1,
    'payouts': [
        {'id': 'po-1', 'user_email': 'hala@example.test', 'user_name': 'د. هالة سمير',
         'amount': 1200.0, 'currency': 'EGP', 'status': 'pending', 'method': 'إنستاباي',
         'destination': 'hala@instapay', 'created_at': '2026-09-09T00:00:00+00:00',
         'age_hours': 9.0, 'fx_alert': False},
    ],
}

ROUTES = {
    '/api/platform-ops-queue': ('/api/bridge/ops/queue', QUEUE_PAYLOAD),
    '/api/platform-pnl': ('/api/bridge/ops/pnl', PNL_PAYLOAD),
    # ⛔ نفس مصدر شارة «المالية»: عدّاد `wallet_payouts_pending` في الطابور يعدّ هذه الصفوف
    # بعينها. قبل هذا البروكسي كان تبويب «السحوبات» يسرد دفتر SQLite (سحوبات المستثمرين)،
    # فتقول الشارة ١ وتقول القائمة ٠ — رقمٌ صحيحٌ فوق قائمةٍ لا تحويه.
    '/api/platform-wallet-payouts': ('/api/bridge/wallet-payouts', PAYOUTS_PAYLOAD),
}
NON_ADMIN_ROLES = ['employee', 'trainer', 'investor', 'viewer', 'pending']


class _FakeResp:
    def __init__(self, payload, status=200):
        self._p = payload
        self.status_code = status
        self.content = b'x'

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
    u = User(email=email, password_hash=generate_password_hash('x', method='pbkdf2:sha256'),
             name=email.split('@')[0], role=role, dashboard_role=role, linked_to_name='',
             preferred_currency='AUTO', is_active=True)
    db.session.add(u)
    db.session.commit()
    return u


def _bearer(user):
    tok = jwt.encode({'user_id': user.id,
                      'exp': datetime.datetime.utcnow() + datetime.timedelta(days=1)},
                     flask_app.config['SECRET_KEY'], algorithm='HS256')
    return {'Authorization': 'Bearer ' + tok}


@pytest.fixture(scope='module')
def ctx():
    with flask_app.app_context():
        db.create_all()
        heads = {r: _bearer(_mkuser('ops-%s@x.test' % r, r)) for r in NON_ADMIN_ROLES}
        heads['admin'] = _bearer(_mkuser('ops-admin@x.test', 'admin'))
        yield {'heads': heads, 'client': flask_app.test_client()}


@pytest.fixture
def calls(monkeypatch):
    """يعترض `requests.request` (ما يستعمله `_platform_proxy`) ويسجّل ما أُرسل."""
    seen = []

    def _fake(method, url, params=None, json=None, headers=None, timeout=None):
        seen.append({'method': method, 'url': url, 'params': params, 'headers': headers or {}})
        for _, (bridge_path, payload) in ROUTES.items():
            if url.endswith(bridge_path):
                return _FakeResp(payload)
        return _FakeResp({}, 404)

    import app as appmod
    monkeypatch.setattr(appmod, 'PLATFORM_METRICS_SECRET', 'test-metrics-secret')
    monkeypatch.setattr(appmod.requests, 'request', _fake)
    return seen


# ---------------------------------------------------------------- ١) الحمولة تعبر كما هي

@pytest.mark.parametrize('route', sorted(ROUTES))
def test_proxy_returns_the_platform_payload_verbatim(ctx, calls, route):
    r = ctx['client'].get(route, headers=ctx['heads']['admin'])
    assert r.status_code == 200, r.get_data(as_text=True)[:300]
    assert r.get_json() == ROUTES[route][1]


def test_queue_keeps_every_counter_and_the_arabic_alerts(ctx, calls):
    body = ctx['client'].get('/api/platform-ops-queue', headers=ctx['heads']['admin']).get_json()
    # العدّادات التي تقرؤها لوحة «كل اللي مستنيك» — أيّ إسقاطٍ لواحدٍ منها يخفي شغلًا منتظرًا.
    for key in ('trainer_applications_pending', 'courses_pending', 'manual_payments_pending',
                'wallet_payouts_pending', 'stuck_card_payments', 'course_interests_24h',
                'training_interests_24h', 'course_split_pending', 'testimonials_pending',
                'topics_drafts', 'founding_leads_new', 'lead_magnet_awaiting_asset',
                'live_needs_decision', 'heartbeats', 'alerts'):
        assert key in body, key
    assert body['alerts'] == QUEUE_PAYLOAD['alerts']       # تُطبع حرفيًّا، بلا إعادة صياغة


def test_pnl_never_sums_currencies_on_the_way_through(ctx, calls):
    body = ctx['client'].get('/api/platform-pnl', headers=ctx['heads']['admin']).get_json()
    assert body['totals_by_currency'] == {'EGP': 0.0, 'SAR': 750.0}
    assert body['total']['currency'] == 'EGP'
    assert body['revenue_other_currencies'] == {'SAR': 750.0}


# ---------------------------------------------------------------- ٢) السرّ والمعاملات

@pytest.mark.parametrize('route', sorted(ROUTES))
def test_shared_secret_travels_in_the_header_and_never_to_the_browser(ctx, calls, route):
    r = ctx['client'].get(route, headers=ctx['heads']['admin'])
    assert calls, 'لم يُنادَ الجسر أصلًا'
    assert calls[-1]['headers'].get('X-ELP-Metrics-Secret') == 'test-metrics-secret'
    assert 'test-metrics-secret' not in r.get_data(as_text=True)


def test_pnl_passes_the_requested_month(ctx, calls):
    ctx['client'].get('/api/platform-pnl?month=2026-07', headers=ctx['heads']['admin'])
    assert calls[-1]['params'] == {'month': '2026-07'}


def test_pnl_without_month_asks_the_platform_for_its_own_default(ctx, calls):
    ctx['client'].get('/api/platform-pnl', headers=ctx['heads']['admin'])
    assert calls[-1]['params'] is None


def test_wallet_payouts_default_to_the_pending_filter(ctx, calls):
    """الشارة تعدّ المعلَّق وحده — فالقائمة تسأل عن المعلَّق وحده. بلا هذا الافتراض تعرض
    الشاشة صفوفًا مسوّاة تحت شارةٍ تقول «بانتظارك»."""
    ctx['client'].get('/api/platform-wallet-payouts', headers=ctx['heads']['admin'])
    assert calls[-1]['params'] == {'status': 'pending'}


@pytest.mark.parametrize('status,sent', [('paid', 'paid'), ('rejected', 'rejected'),
                                         ('pending', 'pending'), ('junk', 'pending'),
                                         ('', 'pending')])
def test_wallet_payouts_status_is_whitelisted_before_it_travels(ctx, calls, status, sent):
    ctx['client'].get('/api/platform-wallet-payouts?status=' + status,
                      headers=ctx['heads']['admin'])
    assert calls[-1]['params'] == {'status': sent}


# ---------------------------------------------------------------- ٣) مَن يقرأ

@pytest.mark.parametrize('route', sorted(ROUTES))
@pytest.mark.parametrize('role', NON_ADMIN_ROLES)
def test_no_non_admin_role_may_read_the_ops_bridges(ctx, calls, route, role):
    r = ctx['client'].get(route, headers=ctx['heads'][role])
    assert r.status_code == 403, (role, route, r.status_code)


@pytest.mark.parametrize('route', sorted(ROUTES))
def test_anonymous_is_refused(ctx, calls, route):
    assert ctx['client'].get(route).status_code == 401


# ---------------------------------------------------------------- ٤) العطل يُعلَن ولا يُخترَع

@pytest.mark.parametrize('route', sorted(ROUTES))
def test_a_cold_bridge_surfaces_as_an_error_not_as_zeros(ctx, monkeypatch, route):
    """⛔ صفرٌ مطمئن أسوأ من خطأ: لو الجسر بارد لازم تصل الشاشة حالة عطل تُعلنها."""
    import app as appmod
    monkeypatch.setattr(appmod, 'PLATFORM_METRICS_SECRET', 'test-metrics-secret')

    def _boom(*a, **k):
        raise RuntimeError('connection refused')

    monkeypatch.setattr(appmod.requests, 'request', _boom)
    r = ctx['client'].get(route, headers=ctx['heads']['admin'])
    assert r.status_code == 502
    assert 'error' in r.get_json()


@pytest.mark.parametrize('route', sorted(ROUTES))
def test_unconfigured_bridge_says_so(ctx, monkeypatch, route):
    import app as appmod
    monkeypatch.setattr(appmod, 'PLATFORM_METRICS_SECRET', '')
    r = ctx['client'].get(route, headers=ctx['heads']['admin'])
    assert r.status_code == 503
